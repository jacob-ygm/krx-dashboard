
import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="xAI 분석 대시보드", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 xAI 분석기")

# 파일 존재 여부 먼저 확인
files = ["full_result.csv", "feature_importance.csv"]
missing_files = [f for f in files if not os.path.exists(f)]

if missing_files:
    st.error(f"⚠️ 다음 데이터 파일이 아직 업로드되지 않았습니다: {missing_files}")
    st.info("Colab 코드가 완전히 끝났는지 확인하고, 1~2분 후 새로고침(F5) 해주세요.")
else:
    try:
        df = pd.read_csv("full_result.csv")
        imp_df = pd.read_csv("feature_importance.csv")

        st.subheader("💡 AI의 판단 근거 (xAI)")
        fig_imp = px.bar(imp_df, x='Importance', y='Feature', orientation='h', color='Importance')
        st.plotly_chart(fig_imp, use_container_width=True)

        st.divider()
        st.subheader("📈 전체 분석 결과 (50개 종목)")
        st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}).background_gradient(subset=['prob'], cmap='RdYlGn'), use_container_width=True)

        st.divider()
        selected = st.selectbox("종목 상세 해석", df['name'].tolist())
        row = df[df['name'] == selected].iloc[0]
        st.success(f"**{selected}**의 상승 확률은 **{row['prob']*100:.1f}%**입니다. 주요 변수: **{imp_df.iloc[0]['Feature']}**")
    except Exception as e:
        st.error(f"데이터 처리 중 에러 발생: {e}")
