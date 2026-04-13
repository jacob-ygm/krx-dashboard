
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="xAI 주식 분석 센터", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 xAI 대시보드")

try:
    df = pd.read_csv("full_result.csv")
    importance_df = pd.read_csv("feature_importance.csv")

    st.subheader("💡 인공지능의 판단 근거 (xAI)")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("분석 모델이 현재 시장에서 중요하게 평가하는 지표 순위입니다.")
        st.table(importance_df)
    with col2:
        fig_imp = px.bar(importance_df, x='Importance', y='Feature', orientation='h', color='Importance')
        st.plotly_chart(fig_imp, use_container_width=True)

    st.divider()
    st.subheader("📈 전체 50개 종목 AI 분석 결과")
    st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}).background_gradient(subset=['prob'], cmap='RdYlGn'), use_container_width=True)

    st.divider()
    selected = st.selectbox("상세 해석 종목 선택", df['name'].tolist())
    row = df[df['name'] == selected].iloc[0]
    st.info(f"**{selected}**의 상승 확률은 **{row['prob']*100:.1f}%**입니다. 이는 주로 **{importance_df.iloc[0]['Feature']}** 지표의 영향이 컸습니다.")

except Exception as e:
    st.warning("데이터 파일(CSV)을 읽어오는 중입니다. 잠시 후 새로고침(F5) 해주세요.")
    st.write(f"상세 에러: {e}")
