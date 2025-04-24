import streamlit as st
import requests
import datetime
import urllib3
import time
from openai import OpenAI

# ✅ API 키 불러오기
client = OpenAI(api_key=st.secrets["openai"]["api_key"])
bot_token = st.secrets["telegram"]["bot_token"]
chat_id = st.secrets["telegram"]["chat_id"]
did_api_key = st.secrets["d_id"]["api_key"]
image_url = st.secrets["d_id"]["image_url"]
service_key = st.secrets["kma"]["service_key"]

# ✅ 대전 KAIST 격자 좌표
nx, ny = 67, 100

# ✅ SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ✅ base_time 계산
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

# ✅ 실황 + 예보 불러오기
def get_weather():
    now = datetime.datetime.now()
    base_date = now.strftime("%Y%m%d")
    base_time = now.strftime("%H%M")
    fcst_date, fcst_time = get_base_time()
    current_hour = now.strftime("%H")

    weather = {"기온": "?", "습도": "?", "바람": "?"}
    forecast = {"하늘": "?", "강수형태": "?", "강수확률": "?"}

    try:
        r = requests.get("http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
                         params={
                             "serviceKey": service_key,
                             "pageNo": "1",
                             "numOfRows": "100",
                             "dataType": "JSON",
                             "base_date": base_date,
                             "base_time": base_time,
                             "nx": nx,
                             "ny": ny,
                         }, verify=False)
        items = r.json()['response']['body']['items']['item']
        for i in items:
            if i['category'] == 'T1H': weather['기온'] = f"{i['obsrValue']}℃"
            elif i['category'] == 'REH': weather['습도'] = f"{i['obsrValue']}%"
            elif i['category'] == 'WSD': weather['바람'] = f"{i['obsrValue']}m/s"
    except: pass

    try:
        r = requests.get("http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
                         params={
                             "serviceKey": service_key,
                             "pageNo": "1",
                             "numOfRows": "1000",
                             "dataType": "JSON",
                             "base_date": fcst_date,
                             "base_time": fcst_time,
                             "nx": nx,
                             "ny": ny,
                         }, verify=False)
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

    data = {}
    data.update(weather)
    data.update(forecast)
    summary = f"{now.strftime('%H')}시 기준 | 🌡️ {data['기온']} | {data['하늘']} | {data['강수형태']} | 확률 {data['강수확률']} | 💧습도 {data['습도']} | 🍃바람 {data['바람']}"
    return summary

# ✅ GPT 대본 생성
def generate_gpt_ment(summary):
    prompt = f"""
    다음은 오늘 대전 KAIST 지역의 기상청 요약입니다:
    {summary}
    이 정보를 바탕으로 친근하고 간결한 아나운서 멘트를 작성해주세요.
    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ✅ D-ID 영상 생성
def create_did_video(text):
    res = requests.post("https://api.d-id.com/talks",
                        headers={"Authorization": f"Basic {did_api_key}"},
                        json={
                            "script": {"type": "text", "input": text,
                                       "provider": {"type": "microsoft", "voice_id": "ko-KR-SunHiNeural"}},
                            "source_url": image_url
                        })
    return res.json().get("id")

def get_video_url(talk_id):
    while True:
        res = requests.get(f"https://api.d-id.com/talks/{talk_id}",
                           headers={"Authorization": f"Basic {did_api_key}"})
        data = res.json()
        if data.get("status") == "done":
            return data.get("result_url")
        time.sleep(2)

# ✅ Streamlit UI
st.title("🌤️ 대전 KAIST AI 날씨 리포터")

if st.button("▶️ 오늘 날씨 영상 생성"):
    summary = get_weather()
    st.success("✅ 요약 완료:")
    st.text(summary)

    ment = generate_gpt_ment(summary)
    st.success("🗣️ GPT 멘트:")
    st.text(ment)

    talk_id = create_did_video(ment)
    st.info("🎥 영상 생성 중...")

    video_url = get_video_url(talk_id)
    st.video(video_url)
    st.success("✅ 영상 생성 완료!")
