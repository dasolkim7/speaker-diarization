import whisper
import os
import streamlit as st
import yt_dlp
import google.generativeai as genai  # ✅ Gemini API 라이브러리 추가
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 및 API 클라이언트 생성
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ Gemini API 키 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def get_youtube_video_info(video_url):
    ydl_opts = {
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        video_info = ydl.extract_info(video_url, download=False)
        video_id = video_info.get('id')
        title = video_info.get('title')
        upload_date = video_info.get('upload_date')
        channel = video_info.get('channel')
        duration = video_info.get('duration_string')  # 일부 환경에서는 'duration'일 수 있음
    return video_id, title, upload_date, channel, duration

# 페이지 설정
st.set_page_config(page_title="YouTube 영상 정보 & 화자 분할", layout="wide")

# 커스텀 CSS 추가
custom_css = """
<style>
body {
    background-color: #f0f2f6;
    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
}
h1, h2, h3 {
    color: #333333;
}
.stTextInput>div>div>input {
    border: 2px solid #ccc;
    border-radius: 4px;
    padding: 8px;
}
.stButton>button {
    background-color: #4CAF50; /* 버튼 배경색 녹색 */
    color: white;
    padding: 10px 24px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}
.stButton>button:hover {
    background-color: #333333; /* hover 시 어두운 회색 */
}
.stRadio>div>div {
    margin: 10px 0;
}
.stTextArea>div>textarea {
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 8px;
    background-color: #ffffff;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

st.title("YouTube 영상 정보, 자막 및 화자 분할")

with st.container():
    st.markdown("### 영상 링크 입력")
    video_url = st.text_input("영상 링크를 입력하세요:")

with st.container():
    st.markdown("### 자막 및 화자 분할 옵션")
    col1, col2 = st.columns(2)
    with col1:
        subtitle_source = st.radio("자막 가져오기 방법 선택", ("youtube 자막 가져오기", "whisper"))
    with col2:
        model_choice = st.radio("화자 분할 모델 선택", ("ChatGPT", "Gemini"))

if st.button("영상 정보 가져오기 및 화자 분할 실행"):
    if not video_url:
        st.error("유효한 YouTube URL을 입력하세요.")
    else:
        # 1. 영상 정보 가져오기
        with st.spinner("영상 정보를 가져오는 중..."):
            try:
                video_id, title, upload_date, channel, duration = get_youtube_video_info(video_url)
                st.subheader("영상 정보")
                st.markdown(f"""
                **영상 ID:** {video_id}  
                **제목:** {title}  
                **업로드 날짜:** {upload_date}  
                **채널:** {channel}  
                **영상 길이:** {duration}  
                """)
            except Exception as e:
                st.error(f"영상 정보를 가져오는 중 오류 발생: {e}")
                st.stop()
        
        # 2. 자막 추출
        text_formatted = ""
        if subtitle_source == "youtube 자막 가져오기":
            with st.spinner("YouTube 자막을 가져오는 중..."):
                try:
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                    available_transcripts = "\n".join(
                        [f"- [자막언어] {t.language}, [자막 언어 코드] {t.language_code}" for t in transcript_list]
                    )
                    st.subheader("사용 가능한 자막 언어 (YouTube)")
                    st.text(available_transcripts)
                    
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
                    text_formatted = "\n".join(entry.get("text", "") for entry in transcript)
                    
                    st.subheader("자막 내용 (YouTube)")
                    st.text_area("자막", text_formatted, height=300)
                except Exception as e:
                    st.error(f"YouTube 자막을 가져오는 중 오류 발생: {e}")
                    st.stop()
        elif subtitle_source == "whisper":
            with st.spinner("Whisper를 통한 자막 생성 중..."):
                try:
                    audio_download_folder = "audio"
                    os.makedirs(audio_download_folder, exist_ok=True)
                    audio_file_template = os.path.join(audio_download_folder, f"{video_id}.%(ext)s")
                    audio_file = os.path.join(audio_download_folder, f"{video_id}.mp3")

                    ydl_opts_audio = {
                        'format': 'bestaudio/best',
                        'outtmpl': audio_file_template,
                        'quiet': True,
                        'no_warnings': True,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                    }

                    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
                        ydl.download([video_url])
                    
                    model = whisper.load_model("base")
                    result_whisper = model.transcribe(audio_file)
                    text_formatted = result_whisper["text"]
                    
                    st.subheader("자막 내용 (Whisper)")
                    st.text_area("자막", text_formatted, height=300)
                except Exception as e:
                    st.error(f"Whisper를 통한 자막 생성 중 오류 발생: {e}")
                    st.stop()
        else:
            st.error("자막 가져오기 방법을 선택하세요.")
            st.stop()
        
        # 3. 자막 저장 (subtitles 폴더에 텍스트 파일로 저장)
        try:
            download_folder = "subtitles"
            os.makedirs(download_folder, exist_ok=True)
            text_file = os.path.join(download_folder, f"{video_id}.txt")
            with open(text_file, 'w', encoding='utf-8') as f:
                f.write(text_formatted)
            st.success(f"자막이 파일로 저장되었습니다: {text_file}")
        except Exception as e:
            st.error(f"자막 파일 저장 중 오류 발생: {e}")
            st.stop()
        
        # 4. 화자 분할 실행 (선택한 API 호출)
        with st.spinner("화자 분할을 수행하는 중..."):
            try:
                prompt = f"""- 화자 분할 해줘
                - 영상 제목: {title}
                - 출력 형식: [화자] 대사

                자막 내용:
                {text_formatted}
                """
                if model_choice == "ChatGPT":
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "당신은 화자 분할 전문가입니다."},
                            {"role": "user", "content": prompt}
                        ],
                        model="gpt-4o",
                        temperature=0.2,
                        max_tokens=1024
                    )
                    result = response.choices[0].message.content
                else:  # Gemini 선택 시
                    try:
                        gemini_model = genai.GenerativeModel("gemini-1.5-pro")  # ✅ 최신 모델 사용
                        response = gemini_model.generate_content(prompt)
                        result = response.text
                    except Exception as e:
                        st.error(f"Gemini API 호출 중 오류 발생: {e}")
                        st.stop()

                st.subheader("화자 분할 결과")
                st.text_area("화자 분할 결과", result, height=300)
            except Exception as e:
                st.error(f"API 호출 중 오류 발생: {e}")
