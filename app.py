import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="검증된 xAI 주식 분석", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 AI 분석 성적표")

if os.path.exists("model_perf.csv"):
    perf = pd.read_csv("model_perf.csv")
    acc_val = perf[perf['Metric'] == 'Accuracy']['Score'].values[0]
    prec_val = perf[perf['Metric'] == 'Precision']['Score'].values[0]

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("모델 예측 정확도", f"{acc_val*100:.1f}%")
    col_m2.metric("상승 적중 정밀도(Precision)", f"{prec_val*100:.1f}%")
    col_m3.info("정밀도는 AI가 상승을 예측했을 때 실제로 맞춘 확률을 의미합니다.")

st.divider()

if os.path.exists("full_result.csv"):
    df = pd.read_csv("full_result.csv")
    imp_df = pd.read_csv("feature_importance.csv")
    top10 = df.head(10)

    st.subheader("🔥 검증 데이터 기반 TOP 10 추천")
    fig_top10 = px.bar(top10, x='name', y='prob', text_auto='.1%', color='prob', color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_top10, use_container_width=True)

    st.divider()
    st.subheader("🧐 종목별 xAI 판단 근거")
    selected = st.selectbox("분석 종목 선택", top10['name'].tolist())
    row = top10[top10['name'] == selected].iloc[0]
    
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"### {selected}")
        st.write(f"상승 확률: **{row['prob']*100:.1f}%**")
        st.write(f"현재 모델의 정밀도({prec_val*100:.1f}%)를 고려할 때 신뢰도가 높습니다.")
    with c2:
        fig_pie = px.pie(imp_df, values='Importance', names='Feature', hole=0.4, title="예측 기여 지표")
        st.plotly_chart(fig_pie, use_container_width=True)