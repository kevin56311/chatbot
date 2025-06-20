import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from openai import OpenAI
import json

# 페이지 설정
st.set_page_config(
    page_title="📈 주식 분석 전문 챗봇",
    page_icon="📈",
    layout="wide"
)

# 제목과 설명
st.title("📈 주식 분석 전문 챗봇")
st.write(
    "한국 및 미국 주식 종목을 전문적으로 분석하는 AI 챗봇입니다. "
    "실시간 주가 데이터, 기술적 분석, 재무 지표 분석 등을 제공합니다. "
    "OpenAI API 키가 필요합니다. [여기서 발급받으세요](https://platform.openai.com/account/api-keys)."
)

# 사이드바에 API 키 입력
with st.sidebar:
    st.header("🔧 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    
    # 주요 지수 표시
    st.header("📊 주요 지수")
    try:
        # 주요 지수 데이터 가져오기
        indices = {
            "코스피": "^KS11",
            "코스닥": "^KQ11", 
            "S&P 500": "^GSPC",
            "나스닥": "^IXIC"
        }
        
        for name, symbol in indices.items():
            try:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d")
                if not data.empty:
                    current_price = data['Close'].iloc[-1]
                    prev_close = data['Open'].iloc[0]
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100
                    
                    color = "green" if change >= 0 else "red"
                    arrow = "↗️" if change >= 0 else "↘️"
                    
                    st.metric(
                        label=f"{arrow} {name}",
                        value=f"{current_price:,.2f}",
                        delta=f"{change_pct:+.2f}%"
                    )
            except:
                st.write(f"{name}: 데이터 로딩 중...")
    except:
        st.write("지수 데이터를 불러오는 중...")

# 주식 데이터 가져오기 함수
@st.cache_data(ttl=300)  # 5분 캐시
def get_stock_data(symbol, period="1y"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        info = ticker.info
        return data, info
    except Exception as e:
        return None, None

# 기술적 지표 계산 함수
def calculate_technical_indicators(data):
    if data is None or data.empty:
        return None
    
    # 이동평균
    data['MA5'] = data['Close'].rolling(window=5).mean()
    data['MA20'] = data['Close'].rolling(window=20).mean()
    data['MA60'] = data['Close'].rolling(window=60).mean()
    
    # RSI 계산
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    data['RSI'] = 100 - (100 / (1 + rs))
    
    # 볼린저 밴드
    data['BB_Middle'] = data['Close'].rolling(window=20).mean()
    bb_std = data['Close'].rolling(window=20).std()
    data['BB_Upper'] = data['BB_Middle'] + (bb_std * 2)
    data['BB_Lower'] = data['BB_Middle'] - (bb_std * 2)
    
    return data

# 주식 분석 시스템 프롬프트
STOCK_ANALYSIS_PROMPT = """
당신은 주식 투자 전문가입니다. 다음 역할을 수행해주세요:

1. **종목 분석**: 제공된 주식 데이터를 바탕으로 기술적, 기본적 분석을 수행
2. **투자 조언**: 현재 시장 상황을 고려한 실용적인 투자 조언 제공
3. **리스크 관리**: 투자 리스크와 주의사항을 명확히 안내
4. **데이터 해석**: 주가 차트, 거래량, 재무지표 등을 종합적으로 분석

**중요 원칙**:
- 객관적이고 균형잡힌 분석 제공
- 투자는 본인 책임임을 항상 명시
- 구체적인 매수/매도 시점보다는 분석 근거 중심으로 설명
- 한국어로 친근하고 전문적인 톤으로 응답

사용자의 질문에 대해 전문적이면서도 이해하기 쉽게 답변해주세요.
"""

if not openai_api_key:
    st.info("사이드바에서 OpenAI API 키를 입력해주세요.", icon="🗝️")
else:
    # OpenAI 클라이언트 생성
    client = OpenAI(api_key=openai_api_key)
    
    # 세션 상태 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # 메인 컨텐츠 영역을 두 개 컬럼으로 분할
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 채팅")
        
        # 기존 채팅 메시지 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # 채팅 입력
        if prompt := st.chat_input("종목명이나 주식 관련 질문을 입력하세요 (예: 삼성전자, AAPL, 현재 시장 상황)"):
            # 사용자 메시지 저장 및 표시
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 주식 종목 코드 추출 시도
            stock_data = None
            stock_info = None
            stock_symbol = None
            
            # 한국 주식 코드 매핑 (일부 예시)
            korean_stocks = {
                "삼성전자": "005930.KS",
                "sk하이닉스": "000660.KS", 
                "네이버": "035420.KS",
                "카카오": "035720.KS",
                "lg화학": "051910.KS",
                "현대차": "005380.KS",
                "기아": "000270.KS",
                "포스코홀딩스": "005490.KS",
                "삼성바이오로직스": "207940.KS",
                "lg에너지솔루션": "373220.KS"
            }
            
            # 종목명 또는 코드 확인
            prompt_lower = prompt.lower()
            for name, code in korean_stocks.items():
                if name in prompt_lower:
                    stock_symbol = code
                    break
            
            # 미국 주식 코드 직접 입력된 경우
            if not stock_symbol:
                words = prompt.upper().split()
                for word in words:
                    if len(word) <= 5 and word.isalpha():
                        # 미국 주식 코드로 시도
                        test_data, test_info = get_stock_data(word)
                        if test_data is not None and not test_data.empty:
                            stock_symbol = word
                            break
            
            # 한국 주식 코드 직접 입력된 경우
            if not stock_symbol:
                words = prompt.split()
                for word in words:
                    if ".KS" in word or ".KQ" in word:
                        stock_symbol = word
                        break
            
            # 주식 데이터 가져오기
            if stock_symbol:
                stock_data, stock_info = get_stock_data(stock_symbol)
                if stock_data is not None and not stock_data.empty:
                    stock_data = calculate_technical_indicators(stock_data)
            
            # AI 응답 생성
            with st.chat_message("assistant"):
                # 시스템 메시지와 주식 데이터를 포함한 메시지 구성
                messages = [{"role": "system", "content": STOCK_ANALYSIS_PROMPT}]
                
                # 주식 데이터가 있으면 추가 정보 제공
                if stock_data is not None and stock_info:
                    current_price = stock_data['Close'].iloc[-1]
                    prev_close = stock_data['Close'].iloc[-2] if len(stock_data) > 1 else current_price
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100
                    
                    volume = stock_data['Volume'].iloc[-1]
                    avg_volume = stock_data['Volume'].rolling(20).mean().iloc[-1]
                    
                    rsi = stock_data['RSI'].iloc[-1] if 'RSI' in stock_data.columns else None
                    
                    stock_context = f"""
현재 분석 중인 종목: {stock_symbol}
현재가: {current_price:.2f}
전일대비: {change:+.2f} ({change_pct:+.2f}%)
거래량: {volume:,.0f} (20일 평균: {avg_volume:,.0f})
RSI: {rsi:.2f if rsi else 'N/A'}

최근 주가 동향:
- 5일 이평: {stock_data['MA5'].iloc[-1]:.2f}
- 20일 이평: {stock_data['MA20'].iloc[-1]:.2f}
- 60일 이평: {stock_data['MA60'].iloc[-1]:.2f}

기업 정보:
- 회사명: {stock_info.get('longName', 'N/A')}
- 섹터: {stock_info.get('sector', 'N/A')}
- 시가총액: {stock_info.get('marketCap', 'N/A')}
"""
                    messages.append({"role": "system", "content": stock_context})
                
                # 대화 히스토리 추가
                for msg in st.session_state.messages:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                
                # OpenAI API 호출
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    stream=True,
                    temperature=0.7
                )
                
                response = st.write_stream(stream)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    with col2:
        st.header("📊 종목 정보")
        
        # 종목 검색
        search_symbol = st.text_input(
            "종목 코드 입력", 
            placeholder="예: 005930.KS, AAPL",
            help="한국주식: 종목코드.KS, 미국주식: 티커심볼"
        )
        
        if search_symbol:
            with st.spinner("데이터 로딩 중..."):
                data, info = get_stock_data(search_symbol)
                
                if data is not None and not data.empty:
                    data = calculate_technical_indicators(data)
                    
                    # 기본 정보
                    st.subheader("📋 기본 정보")
                    if info:
                        st.write(f"**회사명**: {info.get('longName', 'N/A')}")
                        st.write(f"**섹터**: {info.get('sector', 'N/A')}")
                        st.write(f"**시가총액**: {info.get('marketCap', 'N/A'):,}" if info.get('marketCap') else "**시가총액**: N/A")
                    
                    # 현재 주가 정보
                    current_price = data['Close'].iloc[-1]
                    prev_close = data['Close'].iloc[-2] if len(data) > 1 else current_price
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100
                    
                    st.metric(
                        label="현재가",
                        value=f"{current_price:,.2f}",
                        delta=f"{change_pct:+.2f}%"
                    )
                    
                    # 차트 생성
                    st.subheader("📈 주가 차트")
                    fig = go.Figure()
                    
                    # 캔들스틱 차트
                    fig.add_trace(go.Candlestick(
                        x=data.index,
                        open=data['Open'],
                        high=data['High'],
                        low=data['Low'],
                        close=data['Close'],
                        name="주가"
                    ))
                    
                    # 이동평균선 추가
                    fig.add_trace(go.Scatter(
                        x=data.index, y=data['MA5'],
                        name='MA5', line=dict(color='blue', width=1)
                    ))
                    fig.add_trace(go.Scatter(
                        x=data.index, y=data['MA20'],
                        name='MA20', line=dict(color='red', width=1)
                    ))
                    
                    fig.update_layout(
                        height=400,
                        xaxis_title="날짜",
                        yaxis_title="가격",
                        xaxis_rangeslider_visible=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 기술적 지표
                    st.subheader("🔧 기술적 지표")
                    
                    col_rsi, col_vol = st.columns(2)
                    
                    with col_rsi:
                        if 'RSI' in data.columns:
                            rsi_value = data['RSI'].iloc[-1]
                            rsi_color = "red" if rsi_value > 70 else ("green" if rsi_value < 30 else "blue")
                            st.metric("RSI (14일)", f"{rsi_value:.2f}")
                    
                    with col_vol:
                        volume_ratio = data['Volume'].iloc[-1] / data['Volume'].rolling(20).mean().iloc[-1]
                        st.metric("거래량 비율", f"{volume_ratio:.2f}x")
                    
                    # 이동평균 정보
                    st.write("**이동평균**")
                    ma_data = {
                        "구분": ["5일선", "20일선", "60일선"],
                        "가격": [
                            f"{data['MA5'].iloc[-1]:.2f}",
                            f"{data['MA20'].iloc[-1]:.2f}",
                            f"{data['MA60'].iloc[-1]:.2f}"
                        ],
                        "현재가 대비": [
                            f"{((current_price / data['MA5'].iloc[-1] - 1) * 100):+.2f}%",
                            f"{((current_price / data['MA20'].iloc[-1] - 1) * 100):+.2f}%",
                            f"{((current_price / data['MA60'].iloc[-1] - 1) * 100):+.2f}%"
                        ]
                    }
                    st.dataframe(pd.DataFrame(ma_data), hide_index=True)
                    
                else:
                    st.error("종목 데이터를 찾을 수 없습니다. 올바른 종목 코드를 입력해주세요.")

# 사용 가이드
with st.expander("📖 사용 가이드"):
    st.markdown("""
    ### 🎯 주요 기능
    - **종목 분석**: 실시간 주가 및 기술적 지표 분석
    - **AI 상담**: 투자 관련 질문과 조언
    - **시장 동향**: 주요 지수 및 시장 상황 모니터링
    
    ### 💡 사용 팁
    - 한국 주식: "삼성전자", "005930.KS" 형태로 입력
    - 미국 주식: "AAPL", "TSLA" 등 티커 심볼로 입력
    - "현재 시장 상황은?", "리스크 관리 방법" 등 일반적인 질문도 가능
    
    ### ⚠️ 주의사항
    - 제공되는 정보는 투자 참고용이며, 투자 결정은 본인 책임입니다
    - 실시간 데이터에 약간의 지연이 있을 수 있습니다
    - 투자 전 충분한 조사와 리스크 검토를 권장합니다
    """)
