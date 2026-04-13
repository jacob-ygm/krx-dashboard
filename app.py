import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="검증된 xAI 분석", layout="wide")
st.title("🛡️ 국방/모빌리티 AI 분석 성적표")

if os.path.exists("model_perf.csv"):
    perf = pd.read_csv("model_perf.csv")
    acc_v = perf[perf['Metric'] == 'Accuracy']['Score'].values[0]
    prec_v = perf[perf['Metric'] == 'Precision']['Score'].values[0]
    m1, m2 = st.columns(2)
    m1.metric("예측 정확도", f"{acc_v*100:.1f}%")
    m2.metric("상승 적중 정밀도", f"{prec_v*100:.1f}%")

st.divider()

if os.path.exists("full_result.csv"):
    df = pd.read_csv("full_result.csv")
    imp_df = pd.read_csv("feature_importance.csv")
    top10 = df.head(10)
    st.subheader("🔥 금주 상승 예측 TOP 10")
    fig = px.bar(top10, x='name', y='prob', text_auto='.1%', color='prob', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    st.subheader("🧐 종목별 xAI 상세 분석")
    sel = st.selectbox("종목 선택", top10['name'].tolist())
    row = top10[top10['name'] == sel].iloc[0]
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"### {sel}")
        st.write(f"상승 확률: **{row['prob']*100:.1f}%**")
        st.info(f"정밀도({prec_v*100:.1f}%) 기반 신뢰도 분석 완료.")
    with c2:
        fig_p = px.pie(imp_df, values='Importance', names='Feature', hole=0.4, title="지표별 기여도")
        st.plotly_chart(fig_p, use_container_width=True)
    
    st.divider()
    st.subheader(f"📋 전체 {len(df)}개 종목 분석 결과")
    st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}).background_gradient(subset=['prob'], cmap='RdYlGn'), use_container_width=True)