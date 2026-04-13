import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="xAI 분석 대시보드", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 xAI 분석기")

if not os.path.exists("full_result.csv"):
    st.error("⚠️ 데이터 파일이 없습니다. Colab 분석을 기다려주세요.")
else:
    df = pd.read_csv("full_result.csv")
    imp_df = pd.read_csv("feature_importance.csv")

    st.subheader("💡 AI의 판단 근거 (xAI)")
    fig_imp = px.bar(imp_df, x='Importance', y='Feature', orientation='h', color='Importance', color_continuous_scale='Viridis')
    st.plotly_chart(fig_imp, use_container_width=True)

    st.divider()
    st.subheader("📈 전체 50개 종목 분석 결과")
    st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}).background_gradient(subset=['prob'], cmap='RdYlGn'), use_container_width=True, height=500)

    st.divider()
    selected = st.selectbox("종목 상세 해석", df['name'].tolist())
    row = df[df['name'] == selected].iloc[0]
    st.success(f"**{selected}**의 상승 확률은 **{row['prob']*100:.1f}%**입니다.")
    st.info(f"이 예측은 주로 **{imp_df.iloc[0]['Feature']}** 지표의 패턴을 분석한 결과입니다.")