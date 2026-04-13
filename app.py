import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="2026 AI & SMR 분석", layout="wide")
st.title("🛡️ 2026 AI 인프라/SMR 성능 리포트")

if os.path.exists("model_perf.csv"):
    perf = pd.read_csv("model_perf.csv")
    acc_v, prec_v = perf['Score'].values[0], perf['Score'].values[1]
    m1, m2 = st.columns(2)
    m1.metric("예측 정확도", f"{acc_v*100:.1f}%")
    m2.metric("상승 적중 정밀도", f"{prec_v*100:.1f}%")

st.divider()

if os.path.exists("full_result.csv"):
    df = pd.read_csv("full_result.csv")
    imp_df = pd.read_csv("feature_importance.csv")
    top10 = df.head(10)
    
    st.subheader("🔥 AI 인프라/SMR 상승 예측 TOP 10")
    fig = px.bar(top10, x='name', y='prob', text_auto='.1%', color='prob', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🧐 개별 종목 xAI 분석")
    sel = st.selectbox("종목 선택", top10['name'].tolist())
    row = top10[top10['name'] == sel].iloc[0]
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"### {sel}")
        st.write(f"5일 내 상승 확률: **{row['prob']*100:.1f}%**")
        st.info(f"이 결과는 과거 데이터 시험 정답률 {acc_v*100:.1f}%를 기반으로 산출되었습니다.")
    with c2:
        fig_p = px.pie(imp_df, values='Importance', names='Feature', hole=0.4, title="예측 근거 비중")
        st.plotly_chart(fig_p, use_container_width=True)