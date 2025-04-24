import streamlit as st
import requests
import datetime
import time
import urllib3
from openai import OpenAI

# 🚨 시크릿에서 API 키 불러오기
client = OpenAI(api_key=st.secrets["openai"]["api_key"])
bot_token = st.secrets["telegram"]["bot_token"]
chat_id = st.secrets["telegram"]["chat_id"]
did_api_key = st.secrets["d_id"]["api_key"]
image_url = st.secrets["d_id"]["image_url"]
nx, ny = 60, 121

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 💡 base_time 계산
def get_base_time():
    now = datetime.datetime.now()
    hour = now.hour
    if hour < 2: return (now - datetime.timedelta(days=1)).strftime("%Y%m%d"), "2300"
    elif hour < 5: return now.strftime("%Y%m%d"), "0200"
    elif hour < 8: return now.strftime("%Y%m%d"), "0500"
    elif hour < 11: return now.strftime("%Y%m%d"), "0800"
    elif hour < 14: return now.strftime("%Y%m%d"), "1100"
    elif hour < 17: return now.strftime("%Y%m%d"), "1400"
    elif hour < 20: return now.strftime("%Y%m%d"), "1700"
    elif hour < 23: return now.strftime("%Y%m%d"), "2000"
    else: return now.strftime("%Y%m%d"), "2300"

# 🌤️ 날씨 데이터 가져오기
def get_weather():
    now = datetime.datetime.now()
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H%M")
    fcst_date, fcst_time = get_base_time()
    current_hour = now.strftime("%H")

    weather = {"기온": "?", "습도": "?", "바람": "?"}
    forecast = {"하늘": "?", "강수형태": "?", "강수확률": "?"}

    try:
        r = requests.get(
            "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
            params={"serviceKey": st.secrets["kma"]["service_key"], "pageNo": "1", "numOfRows": "100",
                    "dataType": "JSON", "base_date": base_date, "base_time": base_time,
                    "nx": nx, "ny": ny}, verify=False)
        items = r.json()['response']['body']['items']['item']
        for i in items:
            if i['category'] == 'T1H': weather['기온'] = f"{i['obsrValue']}℃"
            elif i['category'] == 'REH': weather['습도'] = f"{i['obsrValue']}%"
            elif i['category'] == 'WSD': weather['바람'] = f"{i['obsrValue']}m/s"
    except: pass

    try:
        r = requests.get(
            "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
            params={"serviceKey": st.secrets["kma"]["service_key"], "pageNo": "1", "numOfRows": "1000",
                    "dataType": "JSON", "base_date": fcst_date, "base_time": fcst_time,
                    "nx": nx, "ny": ny}, verify=False)
        items = r.json()['response']['body']['items']['item']
        for item in items:
            if item['fcstTime'][:2] == current_hour:
                if item['category'] == 'SKY':
                    forecast['하늘'] = {"1": "☀️ 맑음", "3": "⛅️ 구름 많음", "4": "☁️ 흐림"}.get(item['fcstValue'], "?")
                elif item['category'] == 'PTY':
                    forecast['강수형태'] = {"0": "비 없음", "1": "비", "2": "비/눈", "3": "눈", "4": "소나기"}.get(item['fcstValue'], "?")
                elif item['category'] == 'POP':
                    forecast['강수확률'] = f"{item['fcstValue']}%"
    except: pass

    data = {**weather, **forecast}
    return f"{now.strftime('%H')}시 기준 | 🌡️ {data['기온']} | {data['하늘']} | {data['강수형태']} | 확률 {data['강수확률']} | 💧습도 {data['습도']} | 🍃바람 {data['바람']}"

# 🧠 GPT로 멘트 생성
def generate_gpt_ment(summary):
    prompt = f"""
    다음은 수원시의 실시간 날씨 요약입니다:
    {summary}
    이 내용을 바탕으로 15초 내외의 짧고 친근한 뉴스 앵커 멘트를 작성해주세요.
    """
    res = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content.strip()

# 🎥 D-ID 영상 생성
def create_did_video(text):
    res = requests.post(
        "https://api.d-id.com/talks",
        headers={"Authorization": f"Basic {did_api_key}"},
        json={
            "script": {"type": "text", "input": text, "provider": {"type": "microsoft", "voice_id": "ko-KR-SunHiNeural"}},
            "source_url": image_url
        }
    )
    return res.json().get("id")

def get_video_url(talk_id):
    while True:
        res = requests.get(f"https://api.d-id.com/talks/{talk_id}", headers={"Authorization": f"Basic {did_api_key}"})
        data = res.json()
        if data.get("status") == "done":
            return data.get("result_url")
        time.sleep(3)

# 🌐 Streamlit 인터페이스
st.title("🌤️ 수원 날씨 AI 리포터")

if st.button("날씨 영상 생성"):
    summary = get_weather()
    st.success("✅ 요약 완료:")
    st.text(summary)

    ment = generate_gpt_ment(summary)
    st.success("🗣️ 멘트 생성 완료:")
    st.text(ment)

    talk_id = create_did_video(ment)
    st.info("📡 영상 생성 중입니다. 잠시만 기다려주세요...")

    video_url = get_video_url(talk_id)
    st.video(video_url)
    st.success("✅ 영상 생성 완료!")
