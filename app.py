
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="xAI 주식 분석 센터", layout="wide")
st.title("🛡️ 국방/모빌리티 테크 xAI 대시보드")

try:
    df = pd.read_csv("full_result.csv")
    importance_df = pd.read_csv("feature_importance.csv")

    # [상단] AI의 판단 근거 (xAI 섹션)
    st.subheader("💡 인공지능은 무엇을 중요하게 보았나? (xAI)")
    col_exp1, col_exp2 = st.columns([1, 2])
    
    with col_exp1:
        st.write("인공지능이 현재 시장에서 상승 종목을 고를 때 가장 비중을 높게 둔 지표들입니다.")
        st.table(importance_df)

    with col_exp2:
        fig_imp = px.bar(importance_df, x='Importance', y='Feature', orientation='h',
                         title="AI 알고리즘 내 변수 기여도",
                         color='Importance', color_continuous_scale='Viridis')
        st.plotly_chart(fig_imp, use_container_width=True)

    st.divider()

    # [중단] 전체 종목 순위 (이전 코드와 동일)
    st.subheader("📈 전체 50개 종목 분석 결과")
    st.dataframe(
        df.style.format({'prob': '{:.2%}', 'Close': '{:,.0f}원'})
        .background_gradient(subset=['prob'], cmap='RdYlGn'),
        use_container_width=True
    )

    # [하단] 개별 종목 xAI 해석
    st.divider()
    selected_stock = st.selectbox("상세 해석", df['name'].tolist())
    prob_val = df[df['name'] == selected_stock]['prob'].values[0]
    
    st.write(f"### 🤖 {selected_stock} 분석 리포트")
    st.write(f"현재 이 종목의 상승 확률은 **{prob_val*100:.1f}%**입니다.")
    st.info(f"이 예측은 주로 **{importance_df.iloc[0]['Feature']}**와 **{importance_df.iloc[1]['Feature']}**의 패턴을 분석한 결과입니다.")

except Exception as e:
    st.error(f"데이터 로딩 중... {e}")
