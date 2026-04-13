import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="2026 AI 인프라 통합 분석", layout="wide")
st.title("📡 AI·SMR·국방 통합 데이터 센터")

if os.path.exists("full_result.csv") and os.path.exists("news_info.csv"):
    df = pd.read_csv("full_result.csv")
    news = pd.read_csv("news_info.csv")
    
    st.subheader("🏁 종합 예측 순위 (경제지수+차트+심리 반영)")
    top_df = df.sort_values("prob", ascending=False).head(10)
    st.dataframe(top_df[['name', 'prob', 'Close', 'USD_KRW', 'SP500']].style.format({'prob': '{:.2%}'}), use_container_width=True)

    st.divider()
    
    sel = st.selectbox("상세 분석 종목 선택", df['name'].unique())
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"### 📊 {sel} 기술적/경제 지표")
        row = df[df['name'] == sel].iloc[0]
        st.write(f"- **상승 확률**: {row['prob']*100:.1f}%")
        st.write(f"- **현재가**: {row['Close']:,}원 / **RSI**: {row['rsi']:.1f}")
        st.write(f"- **시장환경**: 환율 {row['USD_KRW']:.1f} / S&P500 {row['SP500']:.1f}")
        
    with col2:
        st.write(f"### 📰 {sel} 관련 최신 뉴스")
        s_news = news[news['name'] == sel]
        for _, n_row in s_news.iterrows():
            st.markdown(f"- [{n_row['title']}]({n_row['link']})")