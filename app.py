import streamlit as st
import pandas as pd
import numpy as np
import os, json
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="KOSPI 분석", page_icon="📈",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  html, body, [class*="css"] { font-size:15px !important; }
  .block-container { padding:0.7rem 0.6rem 3rem !important; max-width:100% !important; }
  .card { background:#1a1f2e; border-radius:12px; padding:12px 14px;
          margin-bottom:10px; border-left:4px solid #4f8ef7; }
  .card-up   { border-left-color:#22c55e !important; }
  .card-down { border-left-color:#ef4444 !important; }
  .card-gold { border-left-color:#f59e0b !important; }
  .card h4  { margin:0; font-size:12px; color:#8892a4; }
  .card .val { font-size:20px; font-weight:800; color:#fff; }
  .card .sub { font-size:11px; color:#8892a4; margin-top:2px; }
  .pattern-tag { display:inline-block; background:#2d3748; color:#60a5fa;
                 font-size:11px; padding:2px 8px; border-radius:12px; margin:2px; }
  .pattern-on  { background:#1e3a2f !important; color:#4ade80 !important; }
  .dataframe td, .dataframe th { font-size:13px !important; padding:5px 4px !important; }
  div[data-baseweb="tab-list"] { overflow-x:auto; white-space:nowrap; flex-wrap:nowrap !important; }
  button[data-baseweb="tab"]   { font-size:12px !important; padding:5px 8px !important; }
  .news-row { border-bottom:1px solid #2a2f3e; padding:8px 0; }
  .news-row a { color:#60a5fa; font-size:13px; text-decoration:none; }
  .news-tag   { color:#8892a4; font-size:11px; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_all():
    def safe_csv(path):
        if not os.path.exists(path): return None
        try:
            df = pd.read_csv(path)
            return df if len(df) > 0 else None
        except: return None

    df    = safe_csv("full_result.csv")
    news  = safe_csv("news_df.csv")
    macro = safe_csv("macro_summary.csv")
    fi    = safe_csv("feature_importance.csv")
    bt_g  = safe_csv("backtest_grade.csv")
    bt_d  = safe_csv("backtest_daily.csv")

    bt_s = {}
    if os.path.exists("backtest_summary.json"):
        try:
            with open("backtest_summary.json") as f: bt_s = json.load(f)
        except: pass
    return df, news, macro, fi, bt_g, bt_d, bt_s

df, news_df, macro_df, fi_df, bt_grade, bt_daily, bt_summary = load_all()

if df is None:
    st.error("⚠️ 데이터 없음. Colab 파이프라인을 먼저 실행하세요.")
    st.stop()

base_date = df["base_date"].iloc[0] if "base_date" in df.columns else "-"
wf_auc    = float(df["wf_auc"].iloc[0])  if "wf_auc"  in df.columns else 0.0
wf_mae    = float(df["wf_mae"].iloc[0])  if "wf_mae"  in df.columns else 0.0

st.markdown(f"""
<div style='text-align:center;padding:12px 0 4px;'>
  <div style='font-size:21px;font-weight:900;color:#60a5fa;'>📈 KOSPI 분석 v4</div>
  <div style='font-size:11px;color:#8892a4;margin-top:4px;'>
    기준: <b>{base_date}</b> &nbsp;|&nbsp;
    WF-AUC <b>{wf_auc:.3f}</b> &nbsp;|&nbsp;
    WF-MAE <b>{wf_mae*100:.2f}%p</b> &nbsp;|&nbsp;
    🇺🇸미국연계 · 🧠KR-FinBERT · 📉차트패턴
  </div>
</div>""", unsafe_allow_html=True)

tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs(
    ["🏆 순위","🔍 종목","📉 차트패턴","🌐 거시경제","📊 백테스트","📰 뉴스"])


# ══ TAB1: 순위 ══
with tab1:
    st.markdown("#### 🏆 예측 순위")
    top_n = st.slider("표시 개수", 5, len(df), 20, key="topn")
    grade_opt = df["grade"].unique().tolist() if "grade" in df.columns else []
    grade_sel = st.multiselect("등급 필터", grade_opt, default=grade_opt, key="gflt")
    show = df.copy()
    if grade_sel: show = show[show["grade"].isin(grade_sel)]
    show = show.sort_values("prob_up", ascending=False).head(top_n)

    c1,c2,c3,c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card card-up"><h4>강력매수</h4><div class="val">{(df["prob_up"]>=0.70).sum()}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><h4>매수관심</h4><div class="val">{((df["prob_up"]>=0.55)&(df["prob_up"]<0.70)).sum()}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card card-down"><h4>하락주의</h4><div class="val">{(df["prob_up"]<0.35).sum()}</div></div>', unsafe_allow_html=True)
    with c4:
        high_bounce = (df["bounce_score"]>=50).sum() if "bounce_score" in df.columns else 0
        st.markdown(f'<div class="card card-gold"><h4>반등신호</h4><div class="val">{high_bounce}</div></div>', unsafe_allow_html=True)

    disp_cols = ["name","prob_up","pred_ret5d","bounce_score","news_contribution_pct","grade","Close"]
    disp_cols = [c for c in disp_cols if c in show.columns]
    disp = show[disp_cols].copy()
    col_names = {"name":"종목명","prob_up":"상승확률","pred_ret5d":"예상수익(5일)",
                 "bounce_score":"반등스코어","news_contribution_pct":"뉴스기여%",
                 "grade":"등급","Close":"현재가"}
    disp.columns = [col_names.get(c, c) for c in disp_cols]
    disp = disp.reset_index(drop=True); disp.index += 1
    fmt_map = {"상승확률":"{:.1%}","예상수익(5일)":"{:+.2%}",
               "현재가":"{:,.0f}","반등스코어":"{:.0f}","뉴스기여%":"{:.1f}%"}
    fmt_map = {k:v for k,v in fmt_map.items() if k in disp.columns}
    styled = disp.style.format(fmt_map)
    if "상승확률" in disp.columns:
        styled = styled.background_gradient(subset=["상승확률"], cmap="RdYlGn")
    if "뉴스기여%" in disp.columns:
        styled = styled.background_gradient(subset=["뉴스기여%"], cmap="Oranges")
    st.dataframe(styled, use_container_width=True, height=430)

    fig = px.scatter(df, x="prob_up", y="pred_ret5d", color="grade",
                     size="bounce_score" if "bounce_score" in df.columns else None,
                     hover_name="name",
                     labels={"prob_up":"상승확률","pred_ret5d":"예상수익률","bounce_score":"반등스코어"})
    fig.add_hline(y=0, line_dash="dash", line_color="#555")
    fig.add_vline(x=0.55, line_dash="dash", line_color="#555")
    fig.update_layout(height=280, margin=dict(l=10,r=10,t=10,b=30),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#ccc", legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)


# ══ TAB2: 종목 상세 ══
with tab2:
    st.markdown("#### 🔍 종목 상세")
    names = df.sort_values("prob_up", ascending=False)["name"].tolist()
    sel   = st.selectbox("종목 선택", names, key="sel")
    row   = df[df["name"] == sel].iloc[0]

    prob_up  = float(row["prob_up"])
    pred_ret = float(row.get("pred_ret5d", 0))
    cur_px   = float(row.get("Close", 0))
    pred_px  = float(row.get("pred_price5d", cur_px*(1+pred_ret)))

    c1,c2 = st.columns(2)
    with c1:
        clr = "card-up" if prob_up>=0.55 else ("card-down" if prob_up<0.40 else "card")
        st.markdown(f'<div class="card {clr}"><h4>상승 확률</h4><div class="val">{prob_up:.1%}</div>'
                    f'<div class="sub">하락 {1-prob_up:.1%} | {row.get("grade","-")}</div></div>',
                    unsafe_allow_html=True)
    with c2:
        rc = "card-up" if pred_ret>0 else "card-down"
        st.markdown(f'<div class="card {rc}"><h4>5일 예상 수익률</h4><div class="val">{pred_ret*100:+.2f}%</div>'
                    f'<div class="sub">예상가 {pred_px:,.0f}원 (현 {cur_px:,.0f}원)</div></div>',
                    unsafe_allow_html=True)

    up_w = int(prob_up*100)
    st.markdown(f"""
    <div style='margin:8px 0 4px;font-size:12px;color:#8892a4;'>상승/하락 비율</div>
    <div style='display:flex;border-radius:8px;overflow:hidden;height:12px;'>
      <div style='width:{up_w}%;background:#22c55e;'></div>
      <div style='width:{100-up_w}%;background:#ef4444;'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:11px;color:#8892a4;margin-top:2px;'>
      <span>🟢 {prob_up:.1%}</span><span>🔴 {1-prob_up:.1%}</span>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📐 기술 지표")
    for k,v in {
        "RSI(14)":f"{row.get('rsi14',0):.1f}",
        "MACD 골든크로스":"✅" if row.get("macd_cross",0)==1 else "❌",
        "볼린저 위치":f"{row.get('bb_pct',0):.2f}",
        "거래량 비율":f"{row.get('vol_ratio',0):.2f}x",
        "1일/5일/20일":f"{row.get('ret_1d',0)*100:+.2f}% / {row.get('ret_5d',0)*100:+.2f}% / {row.get('ret_20d',0)*100:+.2f}%",
        "미국섹터 연계수익":f"{row.get('us_sector_ret',0)*100:+.2f}%",
    }.items():
        l,r = st.columns([2,1]); l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True); r.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📑 DART 재무")
    for k,v in {
        "ROE":f"{row.get('dart_roe',0):.1f}%","부채비율":f"{row.get('dart_debt_ratio',0):.1f}%",
        "영업이익률":f"{row.get('dart_op_margin',0):.1f}%","순이익률":f"{row.get('dart_net_margin',0):.1f}%",
    }.items():
        l,r = st.columns([2,1]); l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True); r.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 💰 수급 & 심리")
    for k,v in {
        "외국인 순매수(20일)":f"{row.get('foreign_net_20d',0):,.0f}",
        "기관 순매수(20일)":f"{row.get('inst_net_20d',0):,.0f}",
        "공매도 잔고":f"{row.get('short_ratio',0):.2f}%",
        "감성 점수":f"{row.get('sentiment',0):.2f} (BERT: {row.get('bert_score',0):.2f})",
    }.items():
        l,r = st.columns([2,1]); l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True); r.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    # ── 뉴스가 예측에 얼마나 반영됐는지 ──
    st.divider()
    st.markdown("##### 🧠 뉴스가 이 예측에 미친 영향")
    news_contrib = float(row.get("news_contribution_pct", 0))
    news_dir     = float(row.get("news_shap_direction", 0))
    dir_label    = "🟢 상승 쪽으로" if news_dir > 0 else ("🔴 하락 쪽으로" if news_dir < 0 else "⚪ 중립")
    contrib_color = "#22c55e" if news_dir > 0 else ("#ef4444" if news_dir < 0 else "#8892a4")

    st.markdown(f"""
    <div class="card" style="border-left-color:{contrib_color}">
      <h4>뉴스·감성의 예측 기여도</h4>
      <div class="val" style="color:{contrib_color}">{news_contrib:.1f}%</div>
      <div class="sub">전체 예측 근거 중 뉴스/심리가 차지한 비중 · {dir_label} 작용</div>
    </div>""", unsafe_allow_html=True)

    # 감성 지표별 SHAP 분해 (어떤 심리 지표가 영향 컸는지)
    shap_items = []
    for col, label in [("shap_sentiment","종합 감성"),("shap_bert_score","BERT 감성"),
                       ("shap_news_pos","긍정 뉴스 수"),("shap_news_neg","부정 뉴스 수"),
                       ("shap_fomc_score","FOMC 심리")]:
        if col in row.index:
            shap_items.append((label, float(row.get(col, 0))))
    if shap_items and any(abs(v) > 1e-6 for _, v in shap_items):
        st.markdown("<div style='font-size:12px;color:#8892a4;margin:8px 0 4px;'>심리 지표별 영향 방향</div>", unsafe_allow_html=True)
        max_abs = max(abs(v) for _, v in shap_items) + 1e-9
        for label, val in shap_items:
            pct   = abs(val) / max_abs * 100
            clr   = "#22c55e" if val > 0 else "#ef4444"
            arrow = "▲ 상승기여" if val > 0 else "▼ 하락기여"
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px;'>
              <div style='width:80px;color:#8892a4;'>{label}</div>
              <div style='flex:1;background:#2a2f3e;border-radius:6px;height:10px;overflow:hidden;'>
                <div style='width:{pct:.0f}%;background:{clr};height:10px;'></div>
              </div>
              <div style='width:70px;color:{clr};text-align:right;'>{arrow}</div>
            </div>""", unsafe_allow_html=True)

    # ── 관련 뉴스 (영향도 weight + 언론사 + 원문 링크) ──
    if news_df is not None:
        st.divider(); st.markdown("##### 📰 관련 뉴스 (영향도순)")
        sel_news = news_df[news_df["name"]==sel].copy()
        if "impact" in sel_news.columns:
            sel_news = sel_news.sort_values("impact", ascending=False)
        sel_news = sel_news.head(5)

        if not sel_news.empty:
            for _,nr in sel_news.iterrows():
                sc      = nr.get("sentiment_score", 0)
                icon    = "🟢" if sc>0.1 else ("🔴" if sc<-0.1 else "⚪")
                weight  = nr.get("weight_pct", 0)
                press   = nr.get("press","") or "언론사"
                link    = nr.get("link","#")
                title   = nr.get("title","(제목 없음)")
                # weight 바
                st.markdown(f"""
                <div class="news-row">
                  <div style='display:flex;justify-content:space-between;align-items:center;'>
                    <span class="news-tag">{icon} {press}</span>
                    <span style='font-size:10px;color:#f59e0b;'>가중 {weight:.0f}%</span>
                  </div>
                  <a href="{link}" target="_blank" rel="noopener">{title}</a>
                  <div style='background:#2a2f3e;border-radius:4px;height:4px;margin-top:5px;overflow:hidden;'>
                    <div style='width:{min(weight*2,100):.0f}%;background:#f59e0b;height:4px;'></div>
                  </div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("관련 뉴스 없음")


# ══ TAB3: 차트 패턴 ══
with tab3:
    st.markdown("#### 📉 차트 패턴 & 반등 분석")

    # 반등 스코어 상위 종목
    if "bounce_score" in df.columns:
        st.markdown("##### 🔝 반등 스코어 상위 종목")
        bounce_top = df.sort_values("bounce_score", ascending=False).head(15)
        bt_disp = bounce_top[["name","bounce_score","prob_up","pred_ret5d","grade"]].copy()
        bt_disp.columns = ["종목명","반등스코어","상승확률","예상수익(5일)","등급"]
        bt_disp = bt_disp.reset_index(drop=True); bt_disp.index += 1
        st.dataframe(
            bt_disp.style.format({
                "반등스코어":"{:.0f}","상승확률":"{:.1%}","예상수익(5일)":"{:+.2%}",
            }).background_gradient(subset=["반등스코어"], cmap="YlOrRd"),
            use_container_width=True, height=360)

    st.divider()
    st.markdown("##### 🔍 종목별 패턴 분석")
    pat_sel = st.selectbox("종목 선택", df.sort_values("bounce_score",ascending=False)["name"].tolist(), key="pat_sel")
    prow    = df[df["name"]==pat_sel].iloc[0]

    bs = int(prow.get("bounce_score",0))
    bs_color = "#22c55e" if bs>=60 else ("#f59e0b" if bs>=30 else "#ef4444")
    st.markdown(f"""
    <div class="card" style="border-left-color:{bs_color}">
      <h4>반등 종합 스코어</h4>
      <div class="val" style="color:{bs_color}">{bs} / 100</div>
      <div class="sub">지지선 {prow.get('support',0):,.0f}원 → 저항선 {prow.get('resistance',0):,.0f}원</div>
    </div>""", unsafe_allow_html=True)

    # 패턴 태그
    PATTERN_LABELS = {
        "pattern_double_bottom": "📊 이중바닥(W)",
        "pattern_golden_cross":  "✨ 골든크로스",
        "pattern_rsi_div":       "📈 RSI 다이버전스",
        "pattern_macd_div":      "📉 MACD 다이버전스",
        "pattern_oversold":      "🔄 과매도 반등",
        "pattern_vol_breakout":  "💥 거래량 돌파",
    }
    tag_html = ""
    for col, label in PATTERN_LABELS.items():
        is_on = int(prow.get(col, 0)) == 1
        cls   = "pattern-tag pattern-on" if is_on else "pattern-tag"
        tag_html += f'<span class="{cls}">{label}</span>'
    st.markdown(f"<div style='margin:10px 0;'>{tag_html}</div>", unsafe_allow_html=True)

    # 지지/저항 위치 게이지
    sr = float(prow.get("sr_ratio", 0.5))
    st.markdown(f"""
    <div style='font-size:12px;color:#8892a4;margin:10px 0 4px;'>지지선 ↔ 저항선 위치 ({sr:.0%})</div>
    <div style='background:#2a2f3e;border-radius:8px;height:12px;overflow:hidden;'>
      <div style='width:{int(sr*100)}%;background:linear-gradient(90deg,#22c55e,#f59e0b,#ef4444);height:12px;'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:11px;color:#8892a4;margin-top:2px;'>
      <span>🟢 지지선</span><span>🔴 저항선</span>
    </div>""", unsafe_allow_html=True)

    st.divider()

    # 패턴 설명
    with st.expander("📖 패턴 해석 가이드"):
        st.markdown("""
| 패턴 | 신호 의미 | 참고 조건 |
|------|----------|----------|
| 📊 이중바닥(W) | 강한 반등 시작점 | 두 저점이 비슷한 가격에서 형성 |
| ✨ 골든크로스 | 단기 상승 전환 | MA5가 MA20 상향 돌파 |
| 📈 RSI 다이버전스 | 하락세 약화 | 가격↓ + RSI↑ 동시 발생 |
| 📉 MACD 다이버전스 | 추세 전환 초기 | 가격↓ + MACD 히스토그램↑ |
| 🔄 과매도 반등 | 기술적 반등 가능 | RSI<30 + 볼린저 하단 |
| 💥 거래량 돌파 | 강한 매수세 유입 | 거래량 20일평균 2배 이상 |
        """)


# ══ TAB4: 거시경제 ══
with tab4:
    st.markdown(f"#### 🌐 거시경제 ({base_date})")
    if macro_df is not None:
        m = macro_df.iloc[-1]
        for label,col,fmt,chg_col in [
            ("💵 달러/원","USD_KRW","{:,.1f}","USD_KRW_chg"),
            ("📈 S&P500","SP500","{:,.1f}","SP500_chg"),
            ("📈 나스닥","NASDAQ","{:,.1f}","NASDAQ_chg"),
            ("📊 코스피","KOSPI","{:,.2f}",None),
            ("😱 VIX","VIX","{:.2f}","VIX_chg"),
            ("🛢️ WTI","OIL_WTI","{:.2f}$","OIL_WTI_chg"),
            ("🥇 금","GOLD","{:,.1f}$","GOLD_chg"),
            ("🇺🇸 미10년채","US10Y","{:.3f}%","US10Y_chg"),
            ("💲 달러인덱스","DXY","{:.2f}",None),
        ]:
            if col not in m: continue
            chg = m.get(chg_col) if chg_col else None
            chg_html = ""
            if chg is not None and not pd.isna(chg):
                clr = "#22c55e" if chg>0 else "#ef4444"
                chg_html = f'&nbsp;<span style="color:{clr};font-size:11px">{"▲" if chg>0 else "▼"}{abs(chg)*100:.2f}%</span>'
            l,r = st.columns([2,1])
            l.markdown(f"<span style='font-size:13px'>{label}</span>",unsafe_allow_html=True)
            r.markdown(f"<b style='font-size:14px'>{fmt.format(m[col])}</b>{chg_html}",unsafe_allow_html=True)

    if fi_df is not None:
        st.divider(); st.markdown("#### 🎯 예측 기여 지표 Top 15")
        fig_fi = px.bar(fi_df.head(15), x="importance_cls", y="feature", orientation="h",
                        color="importance_cls", color_continuous_scale="Blues",
                        labels={"importance_cls":"중요도","feature":"지표"})
        fig_fi.update_layout(height=320, margin=dict(l=10,r=10,t=10,b=10),
                             paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             font_color="#ccc", coloraxis_showscale=False,
                             yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_fi, use_container_width=True)


# ══ TAB5: 백테스트 ══
with tab5:
    st.markdown("#### 📊 백테스트 & 모델 검증")
    if bt_summary:
        period = bt_summary.get("backtest_period","-")
        st.caption(f"📅 {period} | Walk-forward {bt_summary.get('wf_auc_mean',0):.3f} AUC")

        c1,c2,c3,c4 = st.columns(4)
        wr  = bt_summary.get("win_rate",0)
        ar  = bt_summary.get("avg_real_ret",0)
        cr  = bt_summary.get("final_cumret",0)
        bwr = bt_summary.get("bounce_win_rate",0)
        with c1:
            clr = "card-up" if wr>=0.5 else "card-down"
            st.markdown(f'<div class="card {clr}"><h4>실제 승률</h4><div class="val">{wr:.1%}</div><div class="sub">prob≥0.60</div></div>',unsafe_allow_html=True)
        with c2:
            clr = "card-up" if ar>0 else "card-down"
            st.markdown(f'<div class="card {clr}"><h4>평균수익</h4><div class="val">{ar*100:+.2f}%</div><div class="sub">5일 후</div></div>',unsafe_allow_html=True)
        with c3:
            clr = "card-up" if cr>0 else "card-down"
            st.markdown(f'<div class="card {clr}"><h4>누적수익</h4><div class="val">{cr*100:+.2f}%</div><div class="sub">2개월</div></div>',unsafe_allow_html=True)
        with c4:
            clr = "card-up" if bwr>=0.5 else "card"
            st.markdown(f'<div class="card {clr}"><h4>반등신호 승률</h4><div class="val">{bwr:.1%}</div><div class="sub">bounce≥50</div></div>',unsafe_allow_html=True)

        if bt_daily is not None and len(bt_daily)>0:
            st.markdown("##### 📈 누적 수익 추이")
            fig_bt = go.Figure()
            fig_bt.add_trace(go.Scatter(
                x=bt_daily["Date"], y=bt_daily["cumret"]*100,
                mode="lines", fill="tozeroy",
                line=dict(color="#4f8ef7",width=2),
                fillcolor="rgba(79,142,247,0.12)"))
            fig_bt.add_hline(y=0, line_dash="dash", line_color="#555")
            fig_bt.update_layout(height=220, margin=dict(l=10,r=10,t=10,b=30),
                                 paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                 font_color="#ccc", showlegend=False, yaxis_title="%")
            st.plotly_chart(fig_bt, use_container_width=True)

        if bt_grade is not None:
            st.markdown("##### 🎯 등급별 실적")
            fmt_map = {c:"{:.1%}" for c in bt_grade.columns if "승률" in c or "수익" in c}
            st.dataframe(bt_grade.style.format(fmt_map), use_container_width=True)

        # 패턴별 실적
        ps = bt_summary.get("pattern_stats",{})
        if ps:
            st.markdown("##### 📉 패턴별 실적")
            ps_df = pd.DataFrame(ps).T.reset_index()
            ps_df.columns = ["패턴","신호수","승률","평균수익"]
            st.dataframe(
                ps_df.style.format({"승률":"{:.1%}","평균수익":"{:+.2%}"}),
                use_container_width=True)

        st.divider()
        st.markdown("> ⚠️ 과거 성과는 미래를 보장하지 않습니다. 수수료/슬리피지 미반영.")
    else:
        st.info("백테스트 데이터 없음. 파이프라인을 실행하세요.")


# ══ TAB6: 뉴스 ══
with tab6:
    st.markdown("#### 📰 뉴스 피드")
    st.caption("영향도(가중치)가 높은 뉴스일수록 예측에 크게 반영됩니다. 제목을 누르면 원문 기사로 이동합니다.")
    if news_df is not None and len(news_df)>0:
        c_a, c_b = st.columns([2,1])
        with c_a:
            kw = st.text_input("종목명 검색", placeholder="예: 삼성전자", key="nkw")
        with c_b:
            sort_opt = st.selectbox("정렬", ["영향도순","최신 종목순"], key="nsort")

        filtered = news_df[news_df["name"].str.contains(kw,na=False)] if kw else news_df.copy()
        if sort_opt == "영향도순" and "impact" in filtered.columns:
            filtered = filtered.sort_values("impact", ascending=False)

        for _,nr in filtered.head(40).iterrows():
            sc     = nr.get("sentiment_score",0)
            icon   = "🟢" if sc>0.1 else ("🔴" if sc<-0.1 else "⚪")
            bert   = nr.get("bert_score",0)
            weight = nr.get("weight_pct",0)
            press  = nr.get("press","") or ""
            name_v = nr.get("name","")
            link   = nr.get("link","#")
            title  = nr.get("title","(제목 없음)")
            press_str = f" · {press}" if press else ""
            st.markdown(
                f'<div class="news-row">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span class="news-tag">{icon} {name_v}{press_str} (BERT {bert:+.2f})</span>'
                f'<span style="font-size:10px;color:#f59e0b;">가중 {weight:.0f}%</span>'
                f'</div>'
                f'<a href="{link}" target="_blank" rel="noopener">{title}</a>'
                f'</div>', unsafe_allow_html=True)
    else:
        st.info("수집된 뉴스가 없습니다. 파이프라인을 재실행하세요.")

st.markdown("<div style='height:50px'></div>", unsafe_allow_html=True)