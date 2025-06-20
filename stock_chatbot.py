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

# CSS 스타일링
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1rem;
        background: linear-gradient(90deg, #4CAF50, #2196F3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
    }
</style>
""", unsafe_allow_html=True)

# 제목과 설명
st.markdown('<h1 class="main-header">📈 주식 분석 전문 챗봇</h1>', unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; margin-bottom: 2rem; font-size: 1.1rem; color: #666;">
한국 및 미국 주식을 전문적으로 분석하는 AI 챗봇입니다.<br>
실시간 주가 데이터, 기술적 분석, 재무 지표를 제공합니다.
</div>
""", unsafe_allow_html=True)

# 한국 주식 매핑 딕셔너리
KOREAN_STOCKS = {
    "삼성전자": "005930.KS", "sk하이닉스": "000660.KS", "네이버": "035420.KS",
    "카카오": "035720.KS", "lg화학": "051910.KS", "현대차": "005380.KS",
    "기아": "000270.KS", "포스코홀딩스": "005490.KS", "삼성바이오로직스": "207940.KS",
    "lg에너지솔루션": "373220.KS", "셀트리온": "068270.KS", "하이브": "352820.KS",
    "kb금융": "105560.KS", "신한지주": "055550.KS", "삼성물산": "028260.KS",
    "naver": "035420.KS", "samsung": "005930.KS", "hyundai": "005380.KS"
}

# 주식 데이터 가져오기 함수
@st.cache_data(ttl=300, show_spinner=False)
def get_stock_data(symbol, period="1y"):
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period)
        info = ticker.info
        return data, info
    except:
        return None, None

# 기술적 지표 계산
def calculate_indicators(data):
    if data is None or data.empty:
        return None
    
    df = data.copy()
    # 이동평균
    df['MA5'] = df['Close'].rolling(5).mean()
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA60'] = df['Close'].rolling(60).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 볼린저 밴드
    df['BB_MA'] = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['BB_MA'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_MA'] - (bb_std * 2)
    
    return df

# 종목 심볼 찾기
def find_stock_symbol(query):
    query = query.lower().strip()
    
    # 한국 주식명 검색
    for name, symbol in KOREAN_STOCKS.items():
        if name in query:
            return symbol
    
    # 영문 티커 검색
    words = query.upper().split()
    for word in words:
        if 2 <= len(word) <= 5 and word.isalpha():
            test_data, _ = get_stock_data(word)
            if test_data is not None and not test_data.empty:
                return word
    
    # 한국 코드 직접 입력
    for word in query.split():
        if ".KS" in word or ".KQ" in word:
            return word.upper()
    
    return None

# AI 시스템 프롬프트
SYSTEM_PROMPT = """당신은 전문 주식 애널리스트입니다. 다음 역할을 수행하세요:

1. 주식 데이터 분석: 기술적/기본적 분석 수행
2. 투자 조언: 객관적이고 균형잡힌 관점 제공  
3. 리스크 안내: 투자 위험성을 명확히 설명
4. 시장 해석: 차트와 지표를 종합적으로 분석

**응답 원칙**:
- 한국어로 친근하고 전문적인 어조 사용
- 구체적 매수/매도 추천보다는 분석 근거 중심
- 투자는 개인 책임임을 항상 명시
- 데이터 기반의 객관적 분석 제공"""

# 사이드바
with st.sidebar:
    st.header("🔧 설정")
    openai_api_key = st.text_input("OpenAI API Key", type="password", key="api_key")
    
    if openai_api_key:
        st.success("✅ API 키가 설정되었습니다")
    else:
        st.warning("⚠️ API 키를 입력해주세요")
    
    st.header("📊 주요 지수")
    indices = {"코스피": "^KS11", "코스닥": "^KQ11", "S&P 500": "^GSPC", "나스닥": "^IXIC"}
    
    for name, symbol in indices.items():
        try:
            data, _ = get_stock_data(symbol, "1d")
            if data is not None and not data.empty:
                current = data['Close'].iloc[-1]
                prev = data['Close'].iloc[0] if len(data) > 1 else current
                change_pct = ((current - prev) / prev) * 100
                
                color = "normal" if abs(change_pct) < 0.1 else ("inverse" if change_pct < 0 else "normal")
                st.metric(
                    name, 
                    f"{current:,.0f}", 
                    f"{change_pct:+.2f}%",
                    delta_color=color
                )
        except:
            st.metric(name, "로딩중...", "")

# 메인 화면
if not openai_api_key:
    st.info("🗝️ 사이드바에서 OpenAI API 키를 입력하면 AI 분석 기능을 사용할 수 있습니다.", icon="💡")
else:
    # OpenAI 클라이언트 생성
    try:
        client = OpenAI(api_key=openai_api_key)
        
        # 세션 상태 초기화
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # 채팅 인터페이스
        st.header("💬 AI 주식 분석 상담")
        
        # 채팅 히스토리 표시
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # 채팅 입력
        if prompt := st.chat_input("종목명 또는 주식 관련 질문을 입력하세요 (예: 삼성전자, AAPL, 시장 전망)"):
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # 종목 분석
            stock_symbol = find_stock_symbol(prompt)
            stock_context = ""
            
            if stock_symbol:
                with st.spinner("주식 데이터 분석 중..."):
                    stock_data, stock_info = get_stock_data(stock_symbol)
                    
                    if stock_data is not None and not stock_data.empty:
                        stock_data = calculate_indicators(stock_data)
                        
                        # 현재 가격 정보
                        current_price = stock_data['Close'].iloc[-1]
                        prev_close = stock_data['Close'].iloc[-2] if len(stock_data) > 1 else current_price
                        change = current_price - prev_close
                        change_pct = (change / prev_close) * 100
                        
                        # 기술적 지표
                        volume = stock_data['Volume'].iloc[-1]
                        avg_volume = stock_data['Volume'].rolling(20).mean().iloc[-1]
                        rsi = stock_data['RSI'].iloc[-1] if not pd.isna(stock_data['RSI'].iloc[-1]) else None
                        
                        # 컨텍스트 구성
                        stock_context = f"""
**분석 종목**: {stock_symbol}
**기업명**: {stock_info.get('longName', 'N/A') if stock_info else 'N/A'}
**현재가**: {current_price:.2f}
**전일대비**: {change:+.2f} ({change_pct:+.2f}%)
**거래량**: {volume:,.0f} (평균 대비: {volume/avg_volume:.2f}배)
**RSI**: {rsi:.1f if rsi else 'N/A'}

**이동평균선 현황**:
- 5일선: {stock_data['MA5'].iloc[-1]:.2f}
- 20일선: {stock_data['MA20'].iloc[-1]:.2f}  
- 60일선: {stock_data['MA60'].iloc[-1]:.2f}

**추가 정보**:
- 섹터: {stock_info.get('sector', 'N/A') if stock_info else 'N/A'}
- 시가총액: {stock_info.get('marketCap', 'N/A') if stock_info else 'N/A'}
"""
            
            # AI 응답 생성
            with st.chat_message("assistant"):
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"현재 분석할 주식 데이터:\n{stock_context}" if stock_context else "일반적인 주식 투자 상담을 진행하세요."}
                ]
                
                # 최근 대화 히스토리 추가 (토큰 제한 고려)
                recent_messages = st.session_state.messages[-10:] if len(st.session_state.messages) > 10 else st.session_state.messages
                for msg in recent_messages:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                
                try:
                    stream = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        stream=True,
                        temperature=0.7,
                        max_tokens=1000
                    )
                    response = st.write_stream(stream)
                    
                except Exception as e:
                    response = f"죄송합니다. AI 응답 생성 중 오류가 발생했습니다: {str(e)}"
                    st.error(response)
            
            # 응답 저장
            st.session_state.messages.append({"role": "assistant", "content": response})
            
    except Exception as e:
        st.error(f"API 키 오류: {str(e)}")
        st.info("올바른 OpenAI API 키를 입력했는지 확인해주세요.")

# 종목 차트 섹션
st.header("📈 실시간 종목 차트")

col1, col2 = st.columns([3, 1])

with col1:
    # 종목 입력
    symbol_input = st.text_input(
        "종목 검색", 
        placeholder="예: 삼성전자, AAPL, 005930.KS",
        help="한국 주식: 회사명 또는 종목코드.KS, 미국 주식: 티커 심볼"
    )
    
    if symbol_input:
        search_symbol = find_stock_symbol(symbol_input)
        
        if not search_symbol:
            # 직접 입력된 심볼 시도
            search_symbol = symbol_input.upper()
        
        if search_symbol:
            with st.spinner("차트 데이터 로딩 중..."):
                chart_data, chart_info = get_stock_data(search_symbol, "6mo")
                
                if chart_data is not None and not chart_data.empty:
                    chart_data = calculate_indicators(chart_data)
                    
                    # 차트 생성
                    fig = go.Figure()
                    
                    # 캔들스틱
                    fig.add_trace(go.Candlestick(
                        x=chart_data.index,
                        open=chart_data['Open'],
                        high=chart_data['High'], 
                        low=chart_data['Low'],
                        close=chart_data['Close'],
                        name="주가",
                        increasing_line_color='red',
                        decreasing_line_color='blue'
                    ))
                    
                    # 이동평균선
                    colors = ['orange', 'purple', 'brown']
                    mas = ['MA5', 'MA20', 'MA60']
                    
                    for ma, color in zip(mas, colors):
                        if ma in chart_data.columns:
                            fig.add_trace(go.Scatter(
                                x=chart_data.index,
                                y=chart_data[ma],
                                name=ma,
                                line=dict(color=color, width=1),
                                opacity=0.7
                            ))
                    
                    fig.update_layout(
                        title=f"{search_symbol} 주가 차트",
                        height=500,
                        xaxis_title="날짜",
                        yaxis_title="가격",
                        xaxis_rangeslider_visible=False,
                        template="plotly_white"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("❌ 해당 종목의 데이터를 찾을 수 없습니다.")

with col2:
    if 'chart_data' in locals() and chart_data is not None and not chart_data.empty:
        st.subheader("📊 현재 상태")
        
        # 현재 가격
        current = chart_data['Close'].iloc[-1]
        prev = chart_data['Close'].iloc[-2] if len(chart_data) > 1 else current
        change = current - prev
        change_pct = (change / prev) * 100
        
        st.metric(
            "현재가", 
            f"{current:,.2f}",
            f"{change:+.2f} ({change_pct:+.2f}%)"
        )
        
        # 거래량
        volume = chart_data['Volume'].iloc[-1]
        st.metric("거래량", f"{volume:,.0f}")
        
        # 기술적 지표
        st.subheader("🔧 기술 지표")
        
        if 'RSI' in chart_data.columns and not pd.isna(chart_data['RSI'].iloc[-1]):
            rsi_val = chart_data['RSI'].iloc[-1]
            rsi_status = "과매수" if rsi_val > 70 else ("과매도" if rsi_val < 30 else "중립")
            st.metric("RSI", f"{rsi_val:.1f}", rsi_status)
        
        # 이동평균 비교
        st.subheader("📈 이동평균")
        for ma in ['MA5', 'MA20', 'MA60']:
            if ma in chart_data.columns and not pd.isna(chart_data[ma].iloc[-1]):
                ma_val = chart_data[ma].iloc[-1]
                ma_diff = ((current / ma_val - 1) * 100)
                st.write(f"**{ma}**: {ma_val:.2f} ({ma_diff:+.1f}%)")

# 사용법 안내
with st.expander("📚 사용법 및 주요 기능"):
    st.markdown("""
    ### 🎯 주요 기능
    - **AI 분석 상담**: OpenAI 기반 전문적인 주식 분석 및 투자 조언
    - **실시간 차트**: 캔들스틱 차트와 기술적 지표 표시
    - **종목 검색**: 한국/미국 주식 통합 검색
    - **시장 모니터링**: 주요 지수 실시간 추적
    
    ### 💡 사용 팁
    - **한국 주식**: "삼성전자", "005930.KS" 등으로 검색
    - **미국 주식**: "AAPL", "TSLA" 등 티커 심볼 사용
    - **AI 상담**: "삼성전자 분석해줘", "시장 전망은?" 등 자유롭게 질문
    
    ### ⚠️ 면책사항
    - 본 서비스는 투자 참고용 정보만 제공합니다
    - 모든 투자 결정과 손익은 본인 책임입니다
    - 충분한 조사와 신중한 판단을 권장합니다
    """)

# 푸터
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 0.9rem;'>"
    "📈 주식 분석 전문 챗봇 | OpenAI GPT-4 기반 | 실시간 데이터 제공"
    "</div>", 
    unsafe_allow_html=True
)
