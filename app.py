import streamlit as st
import pandas as pd
import numpy as np
import os, json
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="KOSPI 분석",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  html, body, [class*="css"] { font-size:15px !important; }
  .block-container { padding:0.7rem 0.6rem 3rem !important; max-width:100% !important; }
  .card {
    background:#1a1f2e; border-radius:12px;
    padding:12px 14px; margin-bottom:10px;
    border-left:4px solid #4f8ef7;
  }
  .card-up   { border-left-color:#22c55e !important; }
  .card-down { border-left-color:#ef4444 !important; }
  .card h4  { margin:0; font-size:12px; color:#8892a4; }
  .card .val { font-size:21px; font-weight:800; color:#fff; }
  .card .sub { font-size:12px; color:#8892a4; margin-top:2px; }
  .dataframe td, .dataframe th { font-size:13px !important; padding:5px 4px !important; }
  div[data-baseweb="tab-list"] { overflow-x:auto; white-space:nowrap; flex-wrap:nowrap !important; }
  button[data-baseweb="tab"]   { font-size:13px !important; padding:6px 10px !important; }
  .news-row { border-bottom:1px solid #2a2f3e; padding:9px 0; }
  .news-row a { color:#60a5fa; font-size:13px; text-decoration:none; }
  .news-tag   { color:#8892a4; font-size:11px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_all():
    def safe_read(path):
        """빈 파일이어도 None 대신 빈 DataFrame 반환"""
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path)
            return df if len(df) > 0 else None
        except Exception:
            return None

    df    = safe_read("full_result.csv")
    news  = safe_read("news_df.csv")
    macro = safe_read("macro_summary.csv")
    fi    = safe_read("feature_importance.csv")

    bt_summary = {}
    if os.path.exists("backtest_summary.json"):
        try:
            with open("backtest_summary.json") as f:
                bt_summary = json.load(f)
        except:
            pass

    bt_grade = safe_read("backtest_grade.csv")
    bt_daily = safe_read("backtest_daily.csv")

    return df, news, macro, fi, bt_summary, bt_grade, bt_daily

df, news_df, macro_df, fi_df, bt_summary, bt_grade, bt_daily = load_all()

if df is None:
    st.error("⚠️ 데이터 없음. Colab 파이프라인을 먼저 실행하세요.")
    st.stop()

base_date = df["base_date"].iloc[0] if "base_date" in df.columns else "-"
clf_auc   = float(df["clf_auc"].iloc[0]) if "clf_auc" in df.columns else 0.0
reg_mae   = float(df["reg_mae"].iloc[0]) if "reg_mae" in df.columns else 0.0

st.markdown(f"""
<div style='text-align:center; padding:14px 0 6px;'>
  <div style='font-size:22px; font-weight:900; color:#60a5fa;'>📈 KOSPI 분석 대시보드</div>
  <div style='font-size:12px; color:#8892a4; margin-top:5px;'>
    기준: <b>{base_date} 마감</b> &nbsp;|&nbsp;
    AUC <b>{clf_auc:.3f}</b> &nbsp;|&nbsp;
    MAE <b>{reg_mae*100:.2f}%p</b>
  </div>
</div>
""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏆 순위", "🔍 종목", "🌐 거시경제", "📊 백테스트", "📰 뉴스"])


# ── TAB1: 순위 ──
with tab1:
    st.markdown("#### 🏆 상승 확률 순위")
    top_n = st.slider("표시 개수", 5, len(df), 20, key="topn")
    grade_opt = df["grade"].unique().tolist() if "grade" in df.columns else []
    grade_sel = st.multiselect("등급 필터", grade_opt, default=grade_opt, key="gflt")
    show = df.copy()
    if grade_sel:
        show = show[show["grade"].isin(grade_sel)]
    show = show.sort_values("prob_up", ascending=False).head(top_n)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        n = (df["prob_up"] >= 0.70).sum()
        st.markdown(f'<div class="card card-up"><h4>강력매수</h4><div class="val">{n}</div></div>', unsafe_allow_html=True)
    with c2:
        n = ((df["prob_up"] >= 0.55) & (df["prob_up"] < 0.70)).sum()
        st.markdown(f'<div class="card"><h4>매수관심</h4><div class="val">{n}</div></div>', unsafe_allow_html=True)
    with c3:
        n = (df["prob_up"] < 0.35).sum()
        st.markdown(f'<div class="card card-down"><h4>하락주의</h4><div class="val">{n}</div></div>', unsafe_allow_html=True)
    with c4:
        avg = df["pred_ret5d"].mean()
        st.markdown(f'<div class="card"><h4>평균예상수익</h4><div class="val">{avg*100:+.1f}%</div></div>', unsafe_allow_html=True)

    disp = show[["name","prob_up","prob_down","pred_ret5d","grade","Close","rsi14"]].copy()
    disp.columns = ["종목명","상승확률","하락확률","예상수익(5일)","등급","현재가","RSI"]
    disp = disp.reset_index(drop=True)
    disp.index += 1
    st.dataframe(
        disp.style.format({
            "상승확률":"{:.1%}","하락확률":"{:.1%}",
            "예상수익(5일)":"{:+.2%}","현재가":"{:,.0f}","RSI":"{:.1f}",
        }).background_gradient(subset=["상승확률"], cmap="RdYlGn"),
        use_container_width=True, height=430,
    )

    fig = px.scatter(
        df, x="prob_up", y="pred_ret5d", color="grade", hover_name="name",
        labels={"prob_up":"상승확률","pred_ret5d":"예상 5일 수익률"},
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#555")
    fig.add_vline(x=0.55, line_dash="dash", line_color="#555")
    fig.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=30),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#ccc", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


# ── TAB2: 종목 상세 ──
with tab2:
    st.markdown("#### 🔍 종목 상세 분석")
    names = df.sort_values("prob_up", ascending=False)["name"].tolist()
    sel   = st.selectbox("종목 선택", names, key="sel")
    row   = df[df["name"] == sel].iloc[0]

    prob_up   = float(row["prob_up"])
    prob_down = float(row["prob_down"])
    pred_ret  = float(row.get("pred_ret5d", 0))
    cur_price = float(row.get("Close", 0))
    pred_px   = float(row.get("pred_price5d", cur_price * (1 + pred_ret)))
    grade_v   = row.get("grade", "-")

    c1, c2 = st.columns(2)
    with c1:
        color = "card-up" if prob_up >= 0.55 else ("card-down" if prob_up < 0.40 else "card")
        st.markdown(
            f'<div class="card {color}"><h4>상승 확률</h4>'
            f'<div class="val">{prob_up:.1%}</div>'
            f'<div class="sub">하락 {prob_down:.1%} | {grade_v}</div></div>',
            unsafe_allow_html=True)
    with c2:
        rc = "card-up" if pred_ret > 0 else "card-down"
        st.markdown(
            f'<div class="card {rc}"><h4>5일 예상 수익률</h4>'
            f'<div class="val">{pred_ret*100:+.2f}%</div>'
            f'<div class="sub">예상가 {pred_px:,.0f}원 (현재 {cur_price:,.0f}원)</div></div>',
            unsafe_allow_html=True)

    # 확률 게이지
    up_w = int(prob_up * 100)
    st.markdown(f"""
    <div style='margin:8px 0 4px;font-size:12px;color:#8892a4;'>상승/하락 확률 비율</div>
    <div style='display:flex;border-radius:8px;overflow:hidden;height:14px;'>
      <div style='width:{up_w}%;background:#22c55e;'></div>
      <div style='width:{100-up_w}%;background:#ef4444;'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:11px;color:#8892a4;margin-top:3px;'>
      <span>🟢 {prob_up:.1%}</span><span>🔴 {prob_down:.1%}</span>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📐 기술 지표")
    tech = {
        "RSI(14)":f"{row.get('rsi14',0):.1f}","MACD 골든크로스":"✅" if row.get("macd_cross",0)==1 else "❌",
        "볼린저 위치":f"{row.get('bb_pct',0):.2f}","거래량 비율":f"{row.get('vol_ratio',0):.2f}x",
        "ATR":f"{row.get('atr',0)*100:.2f}%","1일수익률":f"{row.get('ret_1d',0)*100:+.2f}%",
        "5일수익률":f"{row.get('ret_5d',0)*100:+.2f}%","20일수익률":f"{row.get('ret_20d',0)*100:+.2f}%",
    }
    for k, v in tech.items():
        l, r = st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>", unsafe_allow_html=True)
        r.markdown(f"<b style='font-size:14px'>{v}</b>", unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📑 DART 재무지표")
    fin_items = {
        "ROE":f"{row.get('dart_roe',0):.1f}%",
        "부채비율":f"{row.get('dart_debt_ratio',0):.1f}%",
        "영업이익률":f"{row.get('dart_op_margin',0):.1f}%",
        "순이익률":f"{row.get('dart_net_margin',0):.1f}%",
    }
    for k, v in fin_items.items():
        l, r = st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>", unsafe_allow_html=True)
        r.markdown(f"<b style='font-size:14px'>{v}</b>", unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📰 관련 뉴스")
    if news_df is not None:
        s_news = news_df[news_df["name"] == sel].head(5)
        for _, nr in s_news.iterrows():
            st.markdown(
                f'<div class="news-row"><a href="{nr.get("link","#")}" target="_blank">{nr.get("title","")}</a></div>',
                unsafe_allow_html=True)
    else:
        st.info("뉴스 데이터 없음")


# ── TAB3: 거시경제 ──
with tab3:
    st.markdown(f"#### 🌐 거시경제 ({base_date})")
    if macro_df is not None:
        m = macro_df.iloc[-1]
        MACRO_ROWS = [
            ("💵 달러/원","USD_KRW","{:,.1f}","USD_KRW_chg"),
            ("💶 유로/원","EUR_KRW","{:,.1f}",None),
            ("💴 엔/원","JPY_KRW","{:.4f}",None),
            ("📈 S&P500","SP500","{:,.1f}","SP500_chg"),
            ("📈 나스닥","NASDAQ","{:,.1f}","NASDAQ_chg"),
            ("📊 코스피","KOSPI","{:,.2f}",None),
            ("💹 코스닥","KOSDAQ","{:,.2f}",None),
            ("😱 VIX","VIX","{:.2f}","VIX_chg"),
            ("🛢️ WTI","OIL_WTI","{:.2f}$","OIL_WTI_chg"),
            ("🥇 금","GOLD","{:,.1f}$","GOLD_chg"),
            ("🇺🇸 미10년채","US10Y","{:.3f}%","US10Y_chg"),
            ("💲 달러인덱스","DXY","{:.2f}",None),
        ]
        for label, col, fmt, chg_col in MACRO_ROWS:
            if col not in m: continue
            val = m[col]
            chg = m.get(chg_col) if chg_col else None
            chg_html = ""
            if chg is not None and not pd.isna(chg):
                arrow = "▲" if chg > 0 else "▼"
                color = "#22c55e" if chg > 0 else "#ef4444"
                chg_html = f'&nbsp;<span style="color:{color};font-size:11px">{arrow}{abs(chg)*100:.2f}%</span>'
            l, r = st.columns([2,1])
            l.markdown(f"<span style='font-size:13px'>{label}</span>", unsafe_allow_html=True)
            r.markdown(f"<b style='font-size:14px'>{fmt.format(val)}</b>{chg_html}", unsafe_allow_html=True)

        st.divider()
        fomc = int(df["fomc_score"].iloc[0]) if "fomc_score" in df.columns else 0
        icon = "🕊️ 완화" if fomc > 0 else ("🦅 긴축" if fomc < 0 else "⚖️ 중립")
        st.markdown(f"**FOMC 감성**: `{fomc:+d}` {icon}")

    if fi_df is not None:
        st.divider()
        st.markdown("#### 🎯 예측 기여 지표 Top 15")
        fig_fi = px.bar(fi_df.head(15), x="importance_cls", y="feature",
                        orientation="h", color="importance_cls",
                        color_continuous_scale="Blues",
                        labels={"importance_cls":"중요도","feature":"지표"})
        fig_fi.update_layout(height=320, margin=dict(l=10,r=10,t=10,b=10),
                             paper_bgcolor="rgba(0,0,0,0)",
                             plot_bgcolor="rgba(0,0,0,0)",
                             font_color="#ccc", coloraxis_showscale=False,
                             yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_fi, use_container_width=True)


# ── TAB4: 백테스트 ──
with tab4:
    st.markdown("#### 📊 백테스트 결과 (최근 2개월)")

    if bt_summary:
        period = bt_summary.get("backtest_period","-")
        st.caption(f"📅 분석 기간: {period}")

        c1, c2, c3, c4 = st.columns(4)
        wr  = bt_summary.get("win_rate", 0)
        ar  = bt_summary.get("avg_real_ret", 0)
        cr  = bt_summary.get("final_cumret", 0)
        cor = bt_summary.get("pred_real_corr", 0)

        with c1:
            color = "card-up" if wr >= 0.5 else "card-down"
            st.markdown(f'<div class="card {color}"><h4>실제 승률</h4><div class="val">{wr:.1%}</div><div class="sub">prob_up≥0.60 신호 기준</div></div>', unsafe_allow_html=True)
        with c2:
            color = "card-up" if ar > 0 else "card-down"
            st.markdown(f'<div class="card {color}"><h4>평균 실제수익</h4><div class="val">{ar*100:+.2f}%</div><div class="sub">5일 후 평균</div></div>', unsafe_allow_html=True)
        with c3:
            color = "card-up" if cr > 0 else "card-down"
            st.markdown(f'<div class="card {color}"><h4>누적 수익률</h4><div class="val">{cr*100:+.2f}%</div><div class="sub">2개월 시뮬레이션</div></div>', unsafe_allow_html=True)
        with c4:
            color = "card-up" if cor > 0.3 else "card"
            st.markdown(f'<div class="card {color}"><h4>예측-실제 상관</h4><div class="val">{cor:.3f}</div><div class="sub">1에 가까울수록 정확</div></div>', unsafe_allow_html=True)

        # 누적 수익 차트
        if bt_daily is not None and len(bt_daily) > 0:
            st.markdown("##### 📈 누적 수익률 추이")
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(
                x=bt_daily["Date"], y=bt_daily["cumret"] * 100,
                mode="lines", fill="tozeroy",
                line=dict(color="#4f8ef7", width=2),
                fillcolor="rgba(79,142,247,0.15)",
                name="누적수익률(%)",
            ))
            fig_bt.add_hline(y=0, line_dash="dash", line_color="#555")
            fig_bt.update_layout(
                height=240, margin=dict(l=10,r=10,t=10,b=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ccc", showlegend=False,
                yaxis_title="%",
            )
            st.plotly_chart(fig_bt, use_container_width=True)

        # 등급별 실적
        if bt_grade is not None:
            st.markdown("##### 🎯 등급별 실적")
            fmt_cols = {}
            for col in bt_grade.columns:
                if "승률" in col or "수익률" in col:
                    fmt_cols[col] = "{:.1%}"
            st.dataframe(
                bt_grade.style.format(fmt_cols),
                use_container_width=True,
            )

        st.divider()
        st.markdown("""
        > **⚠️ 백테스트 해석 주의사항**
        > - 과거 성과가 미래 수익을 보장하지 않습니다
        > - 거래 수수료 및 슬리피지 미반영
        > - 모든 투자 결정은 본인 판단 하에 이루어져야 합니다
        """)
    else:
        st.info("백테스트 데이터가 없습니다. 파이프라인을 재실행하세요.")


# ── TAB5: 뉴스 ──
with tab5:
    st.markdown("#### 📰 뉴스 피드")
    if news_df is not None and len(news_df) > 0:
        kw = st.text_input("종목명 검색", placeholder="예: 삼성전자", key="nkw")
        filtered = news_df[news_df["name"].str.contains(kw, na=False)] if kw else news_df
        for _, nr in filtered.head(40).iterrows():
            sc   = nr.get("sentiment_score", 0)
            icon = "🟢" if sc > 0.1 else ("🔴" if sc < -0.1 else "⚪")
            st.markdown(
                f'<div class="news-row">'
                f'<span class="news-tag">{icon} {nr.get("name","")}</span><br>'
                f'<a href="{nr.get("link","#")}" target="_blank">{nr.get("title","")}</a>'
                f'</div>', unsafe_allow_html=True)
    else:
        st.info("수집된 뉴스가 없습니다.")

st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)