# 필요한 라이브러리 자동 설치
import subprocess
import sys

def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except:
        pass

# 필요한 패키지들 자동 설치
packages = ["streamlit", "openai", "yfinance", "pandas", "plotly"]
for package in packages:
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        install_package(package)

# 라이브러리 임포트
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from openai import OpenAI
import warnings
warnings.filterwarnings('ignore')

# 페이지 설정
st.set_page_config(
    page_title="📈 주식 분석 전문 챗봇",
    page_icon="📈",
    layout="wide"
)

# 제목
st.title("📈 주식 분석 전문 챗봇")
st.write("한국 및 미국 주식을 AI로 분석하는 챗봇입니다. 실시간 데이터와 전문 분석을 제공합니다.")

# 한국 주식 매핑
KOREAN_STOCKS = {
    "삼성전자": "005930.KS", "sk하이닉스": "000660.KS", "네이버": "035420.KS",
    "카카오": "035720.KS", "lg화학": "051910.KS", "현대차": "005380.KS",
    "기아": "000270.KS", "포스코홀딩스": "005490.KS", "삼성바이오로직스": "207940.KS",
    "lg에너지솔루션": "373220.KS", "셀트리온": "068270.KS", "하이브": "352820.KS",
    "kb금융": "105560.KS", "신한지주": "055550.KS"
}

# 캐시된 데이터 가져오기
@st.cache_data(ttl=300)
def get_stock_data(symbol, period="6mo"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        info = ticker.info
        return data, info
    except:
        return None, None

# 기술적 지표 계산
def add_indicators(data):
    if data is None or data.empty:
        return None
    
    df = data.copy()
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # RSI 계산
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

# 종목 찾기
def find_symbol(query):
    query = query.lower()
    
    # 한국 주식명 검색
    for name, symbol in KOREAN_STOCKS.items():
        if name in query:
            return symbol
    
    # 영문 티커 검색
    words = query.upper().split()
    for word in words:
        if 2 <= len(word) <= 5 and word.isalpha():
            test_data, _ = get_stock_data(word, "1d")
            if test_data is not None and not test_data.empty:
                return word
    
    # 한국 코드 직접 입력
    for word in query.split():
        if ".KS" in word or ".KQ" in word:
            return word.upper()
    
    return None

# 사이드바 설정
with st.sidebar:
    st.header("🔧 설정")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    if api_key:
        st.success("✅ API 키 설정됨")
    
    st.header("📊 주요 지수")
    indices = {"코스피": "^KS11", "코스닥": "^KQ11", "S&P 500": "^GSPC", "나스닥": "^IXIC"}
    
    for name, symbol in indices.items():
        try:
            data, _ = get_stock_data(symbol, "1d")
            if data is not None and not data.empty:
                current = data['Close'].iloc[-1]
                prev = data['Close'].iloc[0]
                change_pct = ((current - prev) / prev) * 100
                st.metric(name, f"{current:,.0f}", f"{change_pct:+.2f}%")
        except:
            st.metric(name, "로딩중...", "")

# 메인 컨텐츠
col1, col2 = st.columns([3, 2])

with col1:
    st.header("💬 AI 주식 분석")
    
    # API 키 체크
    if not api_key:
        st.info("사이드바에서 OpenAI API 키를 입력하세요.")
    else:
        try:
            client = OpenAI(api_key=api_key)
            
            # 세션 상태 초기화
            if "messages" not in st.session_state:
                st.session_state.messages = []
            
            # 채팅 히스토리 표시
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
            
            # 채팅 입력
            if prompt := st.chat_input("종목명이나 질문을 입력하세요 (예: 삼성전자, AAPL)"):
                # 사용자 메시지 추가
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                # 종목 검색
                symbol = find_symbol(prompt)
                context = ""
                
                if symbol:
                    data, info = get_stock_data(symbol)
                    if data is not None and not data.empty:
                        data = add_indicators(data)
                        current = data['Close'].iloc[-1]
                        prev = data['Close'].iloc[-2] if len(data) > 1 else current
                        change_pct = ((current - prev) / prev) * 100
                        
                        context = f"""
종목: {symbol}
현재가: {current:.2f}
변동률: {change_pct:+.2f}%
RSI: {data['RSI'].iloc[-1]:.1f if not pd.isna(data['RSI'].iloc[-1]) else 'N/A'}
5일 이평: {data['MA5'].iloc[-1]:.2f}
20일 이평: {data['MA20'].iloc[-1]:.2f}
"""
                
                # AI 응답
                with st.chat_message("assistant"):
                    system_msg = f"""당신은 전문 주식 애널리스트입니다. 
다음 주식 데이터를 분석해주세요:
{context}

한국어로 친근하게 답변하고, 투자는 개인 책임임을 명시하세요."""
                    
                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ]
                    
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=messages,
                            stream=True,
                            temperature=0.7
                        )
                        
                        reply = st.write_stream(response)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                        
                    except Exception as e:
                        error_msg = f"AI 응답 오류: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        except Exception as e:
            st.error(f"API 키 오류: {str(e)}")

with col2:
    st.header("📈 종목 차트")
    
    # 종목 입력
    search_input = st.text_input("종목 검색", placeholder="예: 삼성전자, AAPL")
    
    if search_input:
        search_symbol = find_symbol(search_input)
        
        if not search_symbol:
            search_symbol = search_input.upper()
        
        chart_data, chart_info = get_stock_data(search_symbol)
        
        if chart_data is not None and not chart_data.empty:
            chart_data = add_indicators(chart_data)
            
            # 기본 정보
            current = chart_data['Close'].iloc[-1]
            prev = chart_data['Close'].iloc[-2] if len(chart_data) > 1 else current
            change = current - prev
            change_pct = (change / prev) * 100
            
            st.metric("현재가", f"{current:,.2f}", f"{change_pct:+.2f}%")
            
            # 차트 생성
            fig = go.Figure()
            
            # 캔들스틱
            fig.add_trace(go.Candlestick(
                x=chart_data.index,
                open=chart_data['Open'],
                high=chart_data['High'],
                low=chart_data['Low'],
                close=chart_data['Close'],
                name="주가"
            ))
            
            # 이동평균선
            for ma, color in [('MA5', 'blue'), ('MA20', 'red'), ('MA60', 'green')]:
                if ma in chart_data.columns:
                    fig.add_trace(go.Scatter(
                        x=chart_data.index,
                        y=chart_data[ma],
                        name=ma,
                        line=dict(color=color, width=1)
                    ))
            
            fig.update_layout(
                title=f"{search_symbol} 차트",
                height=400,
                xaxis_rangeslider_visible=False
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 기술 지표
            st.subheader("기술 지표")
            if not pd.isna(chart_data['RSI'].iloc[-1]):
                rsi = chart_data['RSI'].iloc[-1]
                rsi_status = "과매수" if rsi > 70 else ("과매도" if rsi < 30 else "보통")
                st.write(f"RSI: {rsi:.1f} ({rsi_status})")
            
            st.write(f"5일선: {chart_data['MA5'].iloc[-1]:.2f}")
            st.write(f"20일선: {chart_data['MA20'].iloc[-1]:.2f}")
            st.write(f"60일선: {chart_data['MA60'].iloc[-1]:.2f}")
            
        else:
            st.error("종목을 찾을 수 없습니다.")

# 사용법
with st.expander("📖 사용법"):
    st.markdown("""
    ### 🎯 기능
    - AI 주식 분석 및 상담
    - 실시간 주가 차트
    - 기술적 지표 분석
    
    ### 💡 사용법
    - 한국주식: "삼성전자", "005930.KS"
    - 미국주식: "AAPL", "TSLA"
    - AI 질문: "삼성전자 어때?", "시장 전망은?"
    
    ### ⚠️ 주의
    - 투자 참고용 정보입니다
    - 투자 결정은 본인 책임입니다
    """)

st.markdown("---")
st.markdown("📈 **주식 분석 전문 챗봇** | OpenAI GPT 기반")
