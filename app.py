
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="AI 주식 추천 대시보드", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 AI 추천 리스트")

try:
    df = pd.read_csv("top10_data.csv")
    cols = st.columns(5)
    for i in range(min(5, len(df))):
        row = df.iloc[i]
        cols[i].metric(row['name'], f"{row['Close']:,.0f}원", f"{row['prob']*100:.1f}% 상승예측")

    st.divider()
    st.subheader("📊 종목별 상승 예측 확률")
    fig = px.bar(df, x='name', y='prob', color='prob', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}))
except:
    st.error("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")
