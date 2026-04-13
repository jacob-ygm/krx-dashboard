import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="AI & 뉴스 통합 분석", layout="wide")
st.title("📡 2026 AI 인프라 뉴스-데이터 통합 리포트")

if os.path.exists("full_result.csv"):
    df = pd.read_csv("full_result.csv")
    
    st.subheader("💡 뉴스 심리 vs AI 예측 확률 비교")
    # 버블 차트로 시각화 (X: 뉴스 점수, Y: 상승 확률, 크기: 종가)
    fig = px.scatter(df, x="news_score", y="prob", size="Close", color="name",
                     hover_name="name", text="name", size_max=40,
                     labels={"news_score": "뉴스 감성 지수 (높을수록 호재)", "prob": "AI 예측 상승 확률"},
                     title="시장 심리와 기술적 지표의 상관관계")
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 AI 추천 TOP 5")
        st.dataframe(df[['name', 'prob', 'news_score']].head(5).style.format({'prob': '{:.2%}'}))
    with col2:
        st.subheader("📰 실시간 뉴스 호재 순위")
        st.dataframe(df.sort_values('news_score', ascending=False)[['name', 'news_score']].head(5))

    st.info("※ 뉴스 지수는 실시간 헤드라인의 긍정/부정 단어 빈도를 분석한 결과입니다.")