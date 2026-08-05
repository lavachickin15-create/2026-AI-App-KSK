import streamlit as st
import pandas as pd
import plotly.express as px
from google import genai
from PIL import Image
from pydantic import BaseModel

# ==========================================
# 1. AI 응답을 정밀하게 규정하는 구조 정의
# ==========================================
# Pydantic을 사용하여 AI가 엉뚱한 답변을 하지 않고 
# 반드시 우리가 원하는 규격(분류, 이름, 방법)의 데이터만 반환하도록 강제합니다.
class RecycleAnalysis(BaseModel):
    분류: str  # 반드시 '플라스틱', '철', '기타' 중 하나로 반환
    이름: str  # 쓰레기의 구체적인 이름 (예: 부탄가스통, 우유팩, 페트병)
    방법: str  # 어떻게 어디에 버려야 하는지 상세 조치법 (예: 구멍을 뚫어서 캔 수거함에)

# ==========================================
# 2. 페이지 초기 설정 및 스타일 정의
# ==========================================
st.set_page_config(
    page_title="재활용 도우미",
    page_icon="♻️",
    layout="centered"
)

# 처음 실행 시 빈 표(이력 데이터프레임)로 출발합니다.
if "history" not in st.session_state:
    st.session_state.history = pd.DataFrame(columns=["분류", "이름", "방법"])

# 최근 스캔 결과를 보존하는 변수
if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

# 카메라 촬영창 제어 변수
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False

# 원그래프 토글 제어 변수
if "chart_visible" not in st.session_state:
    st.session_state.chart_visible = False


# ==========================================
# 3. Google Gemini API 클라이언트 초기화 (비밀번호 안전 검사)
# ==========================================
api_key = None
is_api_ready = False

try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = None

if api_key:
    # 발급된 키를 통해 인공지능 통신용 클라이언트를 초기화합니다.
    client = genai.Client(api_key=api_key)
    is_api_ready = True


# ==========================================
# 4. 상단 헤더 및 [📈 통계 보기] 버튼 영역
# ==========================================
st.write("### 책임감 있는 소비와 생산(SDG 12)을 위한")
col_title, col_btn = st.columns([3, 1])

with col_title:
    st.title("♻️ 재활용 도우미")

with col_btn:
    show_chart = st.button("📈 통계 보기", use_container_width=True)

if show_chart:
    st.session_state.chart_visible = not st.session_state.chart_visible


# ==========================================
# 5. 통계 원그래프 및 80% 이상 조건부 경고 메시지
# ==========================================
if st.session_state.chart_visible:
    st.write("---")
    st.subheader("📊 나의 쓰레기 배출 통계")
    
    df = st.session_state.history
    
    if not df.empty:
        summary = df["분류"].value_counts().reset_index()
        summary.columns = ["분류", "개수"]
        
        # 원그래프 시각화
        fig = px.pie(
            summary, 
            values="개수", 
            names="분류", 
            hole=0.4,
            color_discrete_map={"플라스틱": "#FF4B4B", "철": "#0068C9", "기타": "#83C9FF"}
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 플라스틱 비중 계산
        total_count = summary["개수"].sum()
        plastic_row = summary[summary["분류"] == "플라스틱"]
        plastic_count = plastic_row["개수"].values[0] if not plastic_row.empty else 0
        plastic_ratio = (plastic_count / total_count) * 100
        
        # 기획 3: 플라스틱의 비중이 80% 이상인 경우 강력 알림
        if plastic_ratio >= 80:
            st.error(
                f"🚨 **플라스틱 사용을 줄이세요!** (현재 플라스틱 비율: {plastic_ratio:.1f}%)\n\n"
                "당신이 배출한 쓰레기 대부분이 일회용 플라스틱입니다. "
                "생수 대신 정수기를 이용하고 포장 시 개인 용기를 사용하는 습관을 길러보세요!"
            )
        else:
            st.success(
                f"🌱 **안정적인 배출 흐름입니다.** (현재 플라스틱 비율: {plastic_ratio:.1f}%)\n\n"
                "올바른 분리배출 습관을 계속 이어나가 주세요."
            )
            
        with st.expander("📝 전체 배출 이력 목록 보기"):
            st.dataframe(df, use_container_width=True)
    else:
        st.info("아직 스캔하여 기록된 쓰레기 데이터가 없습니다. 먼저 아래 스캔 버튼을 눌러 촬영해 보세요!")
    st.write("---")


# ==========================================
# 6. 최근 스캔 결과 표시 영역
# ==========================================
if st.session_state.last_scan:
    st.subheader("💡 최근 분리배출 분석 결과")
    
    detected_cat = st.session_state.last_scan["분류"]
    detected_name = st.session_state.last_scan["이름"]
    detected_way = st.session_state.last_scan["방법"]
    
    # 요구하신 포맷: "이것은 [플라스틱](페트병)이며, [~] 버려야 합니다."
    st.info(
        f"이것은 **{detected_cat}**({detected_name})이며, "
        f"**{detected_way}** 버려야 합니다."
    )
    st.write("---")


# ==========================================
# 7. 카메라 인식 및 AI 자동 분석 처리 영역
# ==========================================
if st.session_state.camera_active:
    st.write("### 📸 쓰레기를 카메라 중앙에 놓고 촬영해 주세요")
    captured_file = st.camera_input("카메라")
    
    if captured_file is not None:
        st.success("사진 촬영 성공! 인공지능이 분석 중입니다...")
        
        # 1) API 키가 있는 경우 (실제 AI 자동 연동)
        if is_api_ready:
            try:
                raw_image = Image.open(captured_file)
                
                # Gemini 2.5 Flash와 정밀 구조화 데이터 응답 연동
                # response_schema를 통해 정해둔 Pydantic 구조로 데이터를 즉시 돌려받습니다.
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        raw_image, 
                        "이 이미지 속 쓰레기를 식별하고 분리 배출 분류와 이름을 작성하세요. "
                        "그리고 어떤 통에 어떻게 구체적으로 버려야 하는지 배출 방법도 한국어로 자세히 제안해 주세요."
                    ],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": RecycleAnalysis,
                    }
                )
                
                # 강제 변환된 JSON 형식을 클래스 데이터로 안전하게 매핑합니다.
                analysis: RecycleAnalysis = response.parsed
                detected_cat = analysis.분류
                detected_name = analysis.이름
                detected_way = analysis.방법
                S
            except Exception as e:
                st.error(f"AI 호출 또는 판독 실패: {e}")
                detected_cat, detected_name, detected_way = "기타", "판별 에러 품목", "일반 쓰레기봉투에 담아 배출해야"
                
        # 2) API 키가 없는 경우 (체험형 데모 모드 작동)
        else:
            st.warning("⚠️ API 키 미등록 상태이므로 시뮬레이션 데이터로만 작동합니다.")
            detected_cat = "플라스틱"
            detected_name = "테스트용 페트병"
            detected_way = "라벨을 완전히 제거하고 깨끗이 물로 헹군 후 찌그러뜨려서 플라스틱 수거함에"
        
        # 변수 저장 및 누적 진행
        st.session_state.last_scan = {
            "분류": detected_cat,
            "이름": detected_name,
            "방법": detected_way
        }
        
        new_row = {"분류": detected_cat, "이름": detected_name, "방법": detected_way}
        st.session_state.history = pd.concat([
            st.session_state.history, 
            pd.DataFrame([new_row])
        ], ignore_index=True)
        
        st.session_state.camera_active = False
        st.rerun()


# ==========================================
# 8. 정가운데 최하단 대형 [📷 스캔 시작] 버튼
# ==========================================
st.write("\n" * 4)
st.write("---")

left_space, center_col, right_space = st.columns([1, 2, 1])

with center_col:
    scan_clicked = st.button("📷 스캔 시작하기", use_container_width=True, type="primary")

if scan_clicked:
    st.session_state.camera_active = not st.session_state.camera_active
    st.rerun()
#python -m streamlit run app.py