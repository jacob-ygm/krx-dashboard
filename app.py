import streamlit as st
import pandas as pd
import plotly.express as px
import os

st.set_page_config(page_title="xAI 국방/모빌리티 분석", layout="wide")
st.title("🛡️ 국방/모빌리티 AI 분석 리포트")

if not os.path.exists("full_result.csv"):
    st.error("데이터 파일이 없습니다.")
else:
    df = pd.read_csv("full_result.csv")
    imp_df = pd.read_csv("feature_importance.csv")
    top10 = df.head(10)

    # [시각화 1] TOP 10 종목별 확률 차트
    st.subheader("🔥 금주 상승 예측 TOP 10")
    fig_top10 = px.bar(top10, x='name', y='prob', text_auto='.1%', color='prob',
                       labels={'prob':'상승 확률', 'name':'종목명'},
                       color_continuous_scale='RdYlGn')
    st.plotly_chart(fig_top10, use_container_width=True)

    # [시각화 2] TOP 10 개별 심층 xAI 분석
    st.divider()
    st.subheader("🧐 TOP 10 추천 근거 분석 (xAI)")
    
    selected = st.selectbox("분석할 추천 종목을 선택하세요.", top10['name'].tolist())
    row = top10[top10['name'] == selected].iloc[0]
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.write(f"### **{selected}**")
        st.metric("예측 확률", f"{row['prob']*100:.1f}%")
        st.write(f"현재가: {row['Close']:,.0f}원")
        st.info(f"이 추천은 주로 **{imp_df.iloc[0]['Feature']}**와 **{imp_df.iloc[1]['Feature']}** 지표의 기술적 패턴을 근거로 도출되었습니다.")
    
    with col2:
        fig_pie = px.pie(imp_df, values='Importance', names='Feature', hole=0.4,
                         title=f"{selected} 분석 시 중요 지표 비중")
        st.plotly_chart(fig_pie, use_container_width=True)

    # [시각화 3] 전체 리스트
    st.divider()
    st.subheader(f"📋 전체 분석 결과 ({len(df)}개 종목)")
    st.dataframe(df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'}).background_gradient(subset=['prob'], cmap='RdYlGn'), 
                 use_container_width=True, height=500)