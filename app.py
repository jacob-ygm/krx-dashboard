
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="AI 주식 분석 센터", layout="wide")

st.title("🛡️ 국방/모빌리티 테크 AI 분석 대시보드")
st.sidebar.header("🔍 필터 및 검색")

try:
    # 데이터 로드 (Colab에서 넘겨준 전체 데이터)
    # top10_data.csv 대신 모든 예측값이 담긴 full_result.csv를 쓰도록 Colab 코드도 살짝 바꿀게요.
    df = pd.read_csv("full_result.csv") 
    
    # 1. 상단 요약 (가장 확률 높은 TOP 5)
    st.subheader("🔥 실시간 상승 확률 TOP 5")
    top5 = df.head(5)
    cols = st.columns(5)
    for i in range(len(top5)):
        row = top5.iloc[i]
        cols[i].metric(row['name'], f"{row['Close']:,.0f}원", f"{row['prob']*100:.1f}%")

    st.divider()

    # 2. 전체 종목 분석 현황 (필터 및 검색)
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📈 전체 분석 결과 (확률순)")
        search_query = st.text_input("종목명 검색", "")
        
        display_df = df.copy()
        if search_query:
            display_df = display_df[display_df['name'].str.contains(search_query)]
        
        # 전체 리스트 출력
        st.dataframe(
            display_df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'})
            .background_gradient(subset=['prob'], cmap='RdYlGn'),
            height=500,
            use_container_width=True
        )

    with col2:
        st.subheader("📊 섹터 내 에너지 분포")
        # 전체 50개 종목의 확률 분포를 히스토그램으로 시각화
        fig = px.histogram(df, x="prob", nbins=20, 
                           labels={'prob':'상승 예측 확률'},
                           title="전체 분석 종목의 확률 분포",
                           color_discrete_sequence=['#2ecc71'])
        st.plotly_chart(fig, use_container_width=True)

    # 3. 하단 상세 차트
    st.divider()
    selected_stock = st.selectbox("상세 정보를 확인하고 싶은 종목을 선택하세요.", df['name'].tolist())
    stock_info = df[df['name'] == selected_stock].iloc[0]
    
    st.info(f"💡 **{selected_stock}**의 현재 AI 분석 결과, 5일 이내 2% 이상 상승할 확률은 **{stock_info['prob']*100:.1f}%**입니다.")

except Exception as e:
    st.error(f"데이터를 불러오는 중입니다... (에러 내용: {e})")
