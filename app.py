
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pickle

st.set_page_config(page_title="KRX Intelligence", page_icon="⚡", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background-color: #070d14; }
[data-testid="stSidebar"] { background-color: #0a1520; }
h1,h2,h3 { color: #00e5cc; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    master   = pd.read_csv("master_dataset.csv.gz", parse_dates=["date"],
                            compression="gzip", low_memory=False)
    backtest = pd.read_csv("backtest_results.csv")
    tickers  = pd.read_csv("tickers_kospi200.csv", dtype={"ticker": str})
    tickers["ticker"] = tickers["ticker"].str.zfill(6)
    return master, backtest, tickers

@st.cache_resource
def load_model():
    with open("xgb_model.pkl","rb")  as f: model    = pickle.load(f)
    with open("scaler.pkl","rb")     as f: scaler   = pickle.load(f)
    with open("features.pkl","rb")   as f: features = pickle.load(f)
    return model, scaler, features

master, backtest, tickers = load_data()
model, scaler, features   = load_model()

# ── 사이드바 ────────────────────────────────────────────
st.sidebar.title("⚡ KRX Intelligence")
st.sidebar.caption("코스피 200 AI 분석 대시보드")
st.sidebar.markdown("---")

options = [f"{r.ticker} - {r.name}" for _, r in tickers.iterrows()]
selected      = st.sidebar.selectbox("종목 선택", options)
sel_ticker    = selected.split(" - ")[0].zfill(6)
sel_name      = selected.split(" - ")[1]

stock_df = master[master["ticker"]==sel_ticker].sort_values("date").reset_index(drop=True)

# ── 탭 ──────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📈 주가 분석","🌐 외부요인","🤖 AI 예측","📋 성과 평가"])

# ═══════════════════════════════════════════════
with tab1:
    st.title(f"📈 {sel_name}  ({sel_ticker})")
    if stock_df.empty:
        st.warning("데이터 없음")
    else:
        latest = stock_df.iloc[-1]
        prev   = stock_df.iloc[-2]
        chg    = (latest["close"]-prev["close"])/prev["close"]*100
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("현재가",  f"₩{int(latest['close']):,}")
        c2.metric("등락률",  f"{chg:+.2f}%", delta=f"{chg:+.2f}%")
        c3.metric("거래량",  f"{int(latest['volume']):,}")
        c4.metric("RSI",    f"{latest.get('RSI',0):.1f}" if pd.notna(latest.get('RSI')) else "N/A")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=stock_df["date"], y=stock_df["close"],
            name="종가", line=dict(color="#00e5cc",width=2)))
        for col, color in [("MA5","#ffd700"),("MA20","#a78bfa"),("MA60","#fb923c")]:
            if col in stock_df.columns:
                fig.add_trace(go.Scatter(x=stock_df["date"], y=stock_df[col],
                    name=col, line=dict(color=color,width=1,dash="dot")))
        fig.update_layout(template="plotly_dark", height=420,
            paper_bgcolor="#0a1520", plot_bgcolor="#0a1520",
            title="주가 & 이동평균")
        st.plotly_chart(fig, use_container_width=True)

        fig2 = go.Figure(go.Bar(x=stock_df["date"], y=stock_df["volume"],
            marker_color="#00e5cc44", name="거래량"))
        fig2.update_layout(template="plotly_dark", height=200,
            paper_bgcolor="#0a1520", plot_bgcolor="#0a1520", title="거래량")
        st.plotly_chart(fig2, use_container_width=True)

# ═══════════════════════════════════════════════
with tab2:
    st.title("🌐 외부요인 분석")
    macro_cols = ["USD_KRW","SP500","VIX","NASDAQ","OIL","GOLD","기준금리","CPI"]
    available  = [c for c in macro_cols if c in stock_df.columns]

    if available:
        sel_macro = st.selectbox("지표 선택", available)
        fig3 = go.Figure(go.Scatter(x=stock_df["date"], y=stock_df[sel_macro],
            line=dict(color="#00e5cc",width=2)))
        fig3.update_layout(template="plotly_dark", height=350,
            paper_bgcolor="#0a1520", plot_bgcolor="#0a1520",
            title=f"{sel_macro} 추이")
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("📊 주가 상관관계")
        corr_list = []
        for col in available:
            tmp = stock_df[["close",col]].dropna()
            if len(tmp) > 30:
                corr_list.append({"지표":col, "상관계수":round(tmp["close"].corr(tmp[col]),3)})
        if corr_list:
            cdf = pd.DataFrame(corr_list).sort_values("상관계수")
            fig4 = px.bar(cdf, x="상관계수", y="지표", orientation="h",
                color="상관계수",
                color_continuous_scale=["#ff4d6d","#1a2a3a","#00e5cc"])
            fig4.update_layout(template="plotly_dark", height=300,
                paper_bgcolor="#0a1520", plot_bgcolor="#0a1520")
            st.plotly_chart(fig4, use_container_width=True)

# ═══════════════════════════════════════════════
with tab3:
    st.title("🤖 AI 예측")
    try:
        feat_clean = [f for f in features if f in stock_df.columns]
        pdf = stock_df[feat_clean].copy()
        pdf = pdf.loc[:, ~pdf.columns.duplicated()]
        feat_clean = [f for f in feat_clean if f in pdf.columns][:scaler.n_features_in_]
        pdf = pdf[feat_clean].ffill().bfill().dropna()

        X      = scaler.transform(pdf.values)
        preds  = model.predict(X)
        latest_pred = preds[-1]*100
        signal = "🟢 매수" if latest_pred>1 else "🔴 매도" if latest_pred<-1 else "🟡 중립"

        c1,c2,c3 = st.columns(3)
        c1.metric("AI 신호",        signal)
        c2.metric("예측 5일 수익률", f"{latest_pred:+.2f}%")
        c3.metric("현재가",          f"₩{int(stock_df.iloc[-1]['close']):,}")

        if "target_5d" in stock_df.columns:
            cmp = stock_df.iloc[-len(preds):][["date","target_5d"]].copy()
            cmp["predicted"] = preds
            fig5 = go.Figure()
            fig5.add_trace(go.Scatter(x=cmp["date"], y=cmp["target_5d"]*100,
                name="실제", line=dict(color="#00e5cc",width=2)))
            fig5.add_trace(go.Scatter(x=cmp["date"], y=cmp["predicted"]*100,
                name="예측", line=dict(color="#ffd700",width=2,dash="dot")))
            fig5.add_hline(y=0, line_color="#445566")
            fig5.update_layout(template="plotly_dark", height=400,
                paper_bgcolor="#0a1520", plot_bgcolor="#0a1520",
                title="예측 vs 실제 수익률 (%)")
            st.plotly_chart(fig5, use_container_width=True)

        # 피처 중요도
        st.subheader("📊 피처 중요도")
        imp_df = pd.DataFrame({
            "feature":    feat_clean,
            "importance": model.feature_importances_[:len(feat_clean)]
        }).sort_values("importance", ascending=True).tail(10)
        fig6 = px.bar(imp_df, x="importance", y="feature", orientation="h",
            color_discrete_sequence=["#00e5cc"])
        fig6.update_layout(template="plotly_dark", height=300,
            paper_bgcolor="#0a1520", plot_bgcolor="#0a1520")
        st.plotly_chart(fig6, use_container_width=True)

    except Exception as e:
        st.error(f"예측 오류: {e}")

# ═══════════════════════════════════════════════
with tab4:
    st.title("📋 성과 평가")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("평균 수익률",    f"{backtest['total_ret'].mean():.1f}%")
    c2.metric("평균 Hit Rate", f"{backtest['hit_rate'].mean():.1f}%")
    c3.metric("평균 Sharpe",   f"{backtest['sharpe'].mean():.2f}")
    c4.metric("평균 MDD",      f"{backtest['mdd'].mean():.1f}%")

    fig7 = px.histogram(backtest, x="total_ret", nbins=30,
        title="전체 종목 수익률 분포",
        color_discrete_sequence=["#00e5cc"])
    fig7.update_layout(template="plotly_dark", height=300,
        paper_bgcolor="#0a1520", plot_bgcolor="#0a1520")
    st.plotly_chart(fig7, use_container_width=True)

    st.subheader(f"📌 {sel_name} 백테스팅")
    sbt = backtest[backtest["ticker"]==sel_ticker]
    if not sbt.empty:
        r = sbt.iloc[0]
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("총 수익률", f"{r['total_ret']:.1f}%")
        c2.metric("승률",      f"{r['win_rate']:.1f}%")
        c3.metric("Sharpe",    f"{r['sharpe']:.2f}")
        c4.metric("MDD",       f"{r['mdd']:.1f}%")

    st.subheader("📊 전체 종목 순위")
    st.dataframe(backtest.sort_values("total_ret",ascending=False).reset_index(drop=True),
                 use_container_width=True)
