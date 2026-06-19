import streamlit as st
import pandas as pd
import numpy as np
import os, json
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="KOSPI 분석 v5",page_icon="📈",
                   layout="centered",initial_sidebar_state="collapsed")
st.markdown("""
<style>
  html, body,[class*="css"]{font-size:15px !important;}
  .block-container{padding:0.7rem 0.6rem 3rem !important;max-width:100% !important;}
  .card{background:#1a1f2e;border-radius:12px;padding:12px 14px;
        margin-bottom:10px;border-left:4px solid #4f8ef7;}
  .card-up{border-left-color:#22c55e !important;}
  .card-down{border-left-color:#ef4444 !important;}
  .card-gold{border-left-color:#f59e0b !important;}
  .card h4{margin:0;font-size:12px;color:#8892a4;}
  .card .val{font-size:20px;font-weight:800;color:#fff;}
  .card .sub{font-size:11px;color:#8892a4;margin-top:2px;}
  .news-row{border-bottom:1px solid #2a2f3e;padding:9px 0;}
  .news-row a{color:#60a5fa;font-size:13px;text-decoration:none;}
  .news-tag{color:#8892a4;font-size:11px;}
  .pattern-tag{display:inline-block;background:#2d3748;color:#60a5fa;
               font-size:11px;padding:2px 8px;border-radius:12px;margin:2px;}
  .pattern-on{background:#1e3a2f !important;color:#4ade80 !important;}
  .dataframe td,.dataframe th{font-size:13px !important;padding:5px 4px !important;}
  div[data-baseweb="tab-list"]{overflow-x:auto;white-space:nowrap;flex-wrap:nowrap !important;}
  button[data-baseweb="tab"]{font-size:12px !important;padding:5px 8px !important;}
  .supply-badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:10px;
                margin-left:4px;background:#2d3748;color:#9aa5b4;}
</style>""",unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_all():
    def safe(p):
        if not os.path.exists(p): return None
        try:
            d=pd.read_csv(p); return d if len(d)>0 else None
        except: return None
    df=safe("full_result.csv"); news=safe("news_df.csv")
    macro=safe("macro_summary.csv"); fi=safe("feature_importance.csv")
    btg=safe("backtest_grade.csv"); btd=safe("backtest_daily.csv")
    bts=safe("backtest_sector.csv")
    btsumm={}
    if os.path.exists("backtest_summary.json"):
        try:
            with open("backtest_summary.json") as f: btsumm=json.load(f)
        except: pass
    return df,news,macro,fi,btg,btd,bts,btsumm

df,news_df,macro_df,fi_df,bt_grade,bt_daily,bt_sector,bt_summary=load_all()
if df is None:
    st.error("⚠️ 데이터 없음. Colab 파이프라인을 먼저 실행하세요.")
    st.stop()

base_date=df["base_date"].iloc[0] if "base_date" in df.columns else "-"
wf_auc=float(df["wf_auc"].iloc[0]) if "wf_auc" in df.columns else 0.0
n_models=int(df["n_models"].iloc[0]) if "n_models" in df.columns else 1

st.markdown(f"""
<div style='text-align:center;padding:12px 0 4px;'>
  <div style='font-size:21px;font-weight:900;color:#60a5fa;'>📈 KOSPI 분석 v5</div>
  <div style='font-size:11px;color:#8892a4;margin-top:4px;'>
    기준: <b>{base_date}</b> &nbsp;|&nbsp; WF-AUC <b>{wf_auc:.3f}</b>
    &nbsp;|&nbsp; 앙상블 <b>{n_models}모델</b>
    &nbsp;|&nbsp; 🇺🇸연계 · 🧠FinBERT · 📉차트패턴 · 🏭섹터분석
  </div>
</div>""",unsafe_allow_html=True)

tabs=st.tabs(["🏆 순위","🔍 종목","📉 차트패턴","🌐 거시경제","📊 백테스트","💰 수급현황","📰 뉴스"])
tab1,tab2,tab3,tab4,tab5,tab6,tab7=tabs


# ══ TAB1: 순위 ══
with tab1:
    st.markdown("#### 🏆 예측 순위")
    c_a,c_b=st.columns([1,1])
    with c_a: top_n=st.slider("표시 개수",5,len(df),20,key="topn")
    with c_b:
        if "sector" in df.columns:
            sec_opts=["전체"]+sorted(df["sector"].dropna().unique().tolist())
            sec_sel=st.selectbox("섹터",sec_opts,key="sec")
        else: sec_sel="전체"

    grade_opt=df["grade"].unique().tolist() if "grade" in df.columns else []
    grade_sel=st.multiselect("등급 필터",grade_opt,default=grade_opt,key="gflt")

    show=df.copy()
    if grade_sel: show=show[show["grade"].isin(grade_sel)]
    if sec_sel!="전체" and "sector" in show.columns: show=show[show["sector"]==sec_sel]
    show=show.sort_values("prob_up",ascending=False).head(top_n)

    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'<div class="card card-up"><h4>강력매수</h4><div class="val">{(df["prob_up"]>=0.70).sum()}</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="card"><h4>매수관심</h4><div class="val">{((df["prob_up"]>=0.55)&(df["prob_up"]<0.70)).sum()}</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="card card-down"><h4>하락주의</h4><div class="val">{(df["prob_up"]<0.35).sum()}</div></div>',unsafe_allow_html=True)
    with c4:
        high_b=(df["bounce_score"]>=50).sum() if "bounce_score" in df.columns else 0
        st.markdown(f'<div class="card card-gold"><h4>반등신호</h4><div class="val">{high_b}</div></div>',unsafe_allow_html=True)

    disp_map={"name":"종목명","sector":"섹터","prob_up":"상승확률","pred_ret5d":"예상수익(5일)",
              "bounce_score":"반등스코어","news_contribution_pct":"뉴스기여%","grade":"등급","Close":"현재가"}
    disp_cols=[c for c in disp_map if c in show.columns]
    disp=show[disp_cols].copy().rename(columns=disp_map).reset_index(drop=True)
    disp.index+=1
    fmt={"상승확률":"{:.1%}","예상수익(5일)":"{:+.2%}","현재가":"{:,.0f}",
         "반등스코어":"{:.0f}","뉴스기여%":"{:.1f}%"}
    fmt={k:v for k,v in fmt.items() if k in disp.columns}
    styled=disp.style.format(fmt)
    if "상승확률" in disp.columns: styled=styled.background_gradient(subset=["상승확률"],cmap="RdYlGn")
    if "뉴스기여%" in disp.columns: styled=styled.background_gradient(subset=["뉴스기여%"],cmap="Oranges")
    st.dataframe(styled,use_container_width=True,height=430)

    fig=px.scatter(df,x="prob_up",y="pred_ret5d",color="sector" if "sector" in df.columns else "grade",
                   size="bounce_score" if "bounce_score" in df.columns else None,hover_name="name",
                   labels={"prob_up":"상승확률","pred_ret5d":"예상수익"})
    fig.add_hline(y=0,line_dash="dash",line_color="#555")
    fig.add_vline(x=0.55,line_dash="dash",line_color="#555")
    fig.update_layout(height=280,margin=dict(l=10,r=10,t=10,b=30),
                      paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#ccc",legend_title_text="섹터")
    st.plotly_chart(fig,use_container_width=True)


# ══ TAB2: 종목 상세 ══
with tab2:
    st.markdown("#### 🔍 종목 상세 분석")
    names=df.sort_values("prob_up",ascending=False)["name"].tolist()
    sel=st.selectbox("종목 선택",names,key="sel")
    row=df[df["name"]==sel].iloc[0]
    prob_up=float(row["prob_up"]); pred_ret=float(row.get("pred_ret5d",0))
    cur_px=float(row.get("Close",0)); pred_px=float(row.get("pred_price5d",cur_px*(1+pred_ret)))

    c1,c2=st.columns(2)
    with c1:
        clr="card-up" if prob_up>=0.55 else("card-down" if prob_up<0.40 else "card")
        st.markdown(f'<div class="card {clr}"><h4>상승 확률</h4><div class="val">{prob_up:.1%}</div>'
                    f'<div class="sub">하락 {1-prob_up:.1%} | {row.get("grade","-")} | {row.get("sector","-")}</div></div>',unsafe_allow_html=True)
    with c2:
        rc="card-up" if pred_ret>0 else "card-down"
        st.markdown(f'<div class="card {rc}"><h4>5일 예상 수익률</h4><div class="val">{pred_ret*100:+.2f}%</div>'
                    f'<div class="sub">예상가 {pred_px:,.0f}원 (현재 {cur_px:,.0f}원)</div></div>',unsafe_allow_html=True)

    up_w=int(prob_up*100)
    st.markdown(f"""
    <div style='margin:8px 0 4px;font-size:12px;color:#8892a4;'>상승/하락 비율</div>
    <div style='display:flex;border-radius:8px;overflow:hidden;height:12px;'>
      <div style='width:{up_w}%;background:#22c55e;'></div>
      <div style='width:{100-up_w}%;background:#ef4444;'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:11px;color:#8892a4;margin-top:2px;'>
      <span>🟢 {prob_up:.1%}</span><span>🔴 {1-prob_up:.1%}</span>
    </div>""",unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📐 기술 지표")
    for k,v in {"RSI(14)":f"{row.get('rsi14',0):.1f}","MACD 크로스":"✅" if row.get("macd_cross",0)==1 else "❌",
                "볼린저 위치":f"{row.get('bb_pct',0):.2f}","거래량비율":f"{row.get('vol_ratio',0):.2f}x",
                "ATR(변동성)":f"{row.get('atr',0)*100:.2f}%","역사적변동성(20d)":f"{row.get('hist_vol20',0)*100:.2f}%",
                "샤프모멘텀":f"{row.get('sharpe_mom',0):.2f}","52주수익률":f"{row.get('ret_52w',0)*100:+.1f}%",
                "섹터상대강도":f"{row.get('sector_rel_strength',0)*100:+.2f}%",
                "미국섹터연계":f"{row.get('us_sector_ret',0)*100:+.2f}%",
                "1일/5일/20일":f"{row.get('ret_1d',0)*100:+.2f}% / {row.get('ret_5d',0)*100:+.2f}% / {row.get('ret_20d',0)*100:+.2f}%",
               }.items():
        l,r=st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True)
        r.markdown(f"<b style='font-size:14px'>{v}</b>",unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 📑 DART 재무")
    for k,v in {"ROE":f"{row.get('dart_roe',0):.1f}%","부채비율":f"{row.get('dart_debt_ratio',0):.1f}%",
                "영업이익률":f"{row.get('dart_op_margin',0):.1f}%","순이익률":f"{row.get('dart_net_margin',0):.1f}%"}.items():
        l,r=st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True)
        r.markdown(f"<b style='font-size:14px'>{v}</b>",unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 🧠 뉴스가 이 예측에 미친 영향")
    nc=float(row.get("news_contribution_pct",0)); nd=float(row.get("news_shap_direction",0))
    dir_l="🟢 상승 쪽으로" if nd>0 else("🔴 하락 쪽으로" if nd<0 else "⚪ 중립")
    nc_c="#22c55e" if nd>0 else("#ef4444" if nd<0 else "#8892a4")
    st.markdown(f'<div class="card" style="border-left-color:{nc_c}"><h4>뉴스·감성 예측 기여도</h4>'
                f'<div class="val" style="color:{nc_c}">{nc:.1f}%</div>'
                f'<div class="sub">{dir_l} 작용 | 전체 예측 근거 중 뉴스/심리 비중</div></div>',unsafe_allow_html=True)

    shap_items=[(l,float(row.get(c,0))) for c,l in [
        ("shap_sentiment","종합감성"),("shap_bert_score","BERT감성"),
        ("shap_news_pos","긍정뉴스"),("shap_news_neg","부정뉴스"),("shap_fomc_score","FOMC")]]
    if any(abs(v)>1e-6 for _,v in shap_items):
        st.markdown("<div style='font-size:12px;color:#8892a4;margin:8px 0 4px;'>심리 지표별 영향 방향</div>",unsafe_allow_html=True)
        mx=max(abs(v) for _,v in shap_items)+1e-9
        for label,val in shap_items:
            pct=abs(val)/mx*100; clr="#22c55e" if val>0 else "#ef4444"
            arrow="▲ 상승기여" if val>0 else "▼ 하락기여"
            st.markdown(f"""
            <div style='display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px;'>
              <div style='width:70px;color:#8892a4;'>{label}</div>
              <div style='flex:1;background:#2a2f3e;border-radius:6px;height:10px;overflow:hidden;'>
                <div style='width:{pct:.0f}%;background:{clr};height:10px;'></div>
              </div>
              <div style='width:75px;color:{clr};text-align:right;'>{arrow}</div>
            </div>""",unsafe_allow_html=True)

    if news_df is not None:
        st.divider(); st.markdown("##### 📰 관련 뉴스 (영향도순)")
        sel_news=news_df[news_df["name"]==sel].copy()
        if "impact" in sel_news.columns: sel_news=sel_news.sort_values("impact",ascending=False)
        for _,nr in sel_news.head(5).iterrows():
            sc=nr.get("sentiment_score",0); icon="🟢" if sc>0.1 else("🔴" if sc<-0.1 else "⚪")
            w=nr.get("weight_pct",0); press=nr.get("press","") or ""
            link=nr.get("link","#"); title=nr.get("title","(제목 없음)")
            st.markdown(f"""<div class="news-row">
              <div style='display:flex;justify-content:space-between;'>
                <span class="news-tag">{icon} {press}</span>
                <span style='font-size:10px;color:#f59e0b;'>가중 {w:.0f}%</span>
              </div>
              <a href="{link}" target="_blank" rel="noopener">{title}</a>
              <div style='background:#2a2f3e;border-radius:4px;height:4px;margin-top:4px;overflow:hidden;'>
                <div style='width:{min(w*2,100):.0f}%;background:#f59e0b;height:4px;'></div>
              </div></div>""",unsafe_allow_html=True)


# ══ TAB3: 차트 패턴 ══
with tab3:
    st.markdown("#### 📉 차트 패턴 & 반등 분석")
    if "bounce_score" in df.columns:
        st.markdown("##### 🔝 반등 스코어 상위")
        bt_top=df.sort_values("bounce_score",ascending=False).head(15)
        bt_d=bt_top[["name","sector","bounce_score","prob_up","pred_ret5d","grade"]].copy()
        bt_d.columns=["종목명","섹터","반등스코어","상승확률","예상수익(5일)","등급"]
        bt_d=bt_d.reset_index(drop=True); bt_d.index+=1
        st.dataframe(bt_d.style.format({"반등스코어":"{:.0f}","상승확률":"{:.1%}","예상수익(5일)":"{:+.2%}"}
                                        ).background_gradient(subset=["반등스코어"],cmap="YlOrRd"),
                     use_container_width=True,height=360)

    st.divider()
    pat_sel=st.selectbox("패턴 분석 종목",df.sort_values("bounce_score",ascending=False)["name"].tolist(),key="psel")
    prow=df[df["name"]==pat_sel].iloc[0]
    bs=int(prow.get("bounce_score",0))
    bs_c="#22c55e" if bs>=60 else("#f59e0b" if bs>=30 else "#ef4444")
    st.markdown(f'<div class="card" style="border-left-color:{bs_c}"><h4>반등 종합 스코어</h4>'
                f'<div class="val" style="color:{bs_c}">{bs} / 100</div>'
                f'<div class="sub">지지선 {prow.get("support",0):,.0f}원 → 저항선 {prow.get("resistance",0):,.0f}원</div></div>',
                unsafe_allow_html=True)
    PATT={"pattern_double_bottom":"📊 이중바닥(W)","pattern_golden_cross":"✨ 골든크로스",
          "pattern_rsi_div":"📈 RSI 다이버전스","pattern_macd_div":"📉 MACD 다이버전스",
          "pattern_oversold":"🔄 과매도 반등","pattern_vol_breakout":"💥 거래량 돌파"}
    tags="".join(f'<span class="pattern-tag{"pattern-on" if int(prow.get(c,0))==1 else ""}">{l}</span>'
                 for c,l in PATT.items())
    st.markdown(f"<div style='margin:10px 0;'>{tags}</div>",unsafe_allow_html=True)
    sr=float(prow.get("sr_ratio",0.5))
    st.markdown(f"""
    <div style='font-size:12px;color:#8892a4;margin:10px 0 4px;'>지지 ↔ 저항 위치 ({sr:.0%})</div>
    <div style='background:#2a2f3e;border-radius:8px;height:12px;overflow:hidden;'>
      <div style='width:{int(sr*100)}%;background:linear-gradient(90deg,#22c55e,#f59e0b,#ef4444);height:12px;'></div>
    </div>""",unsafe_allow_html=True)
    with st.expander("📖 패턴 해석"):
        st.markdown("""| 패턴 | 의미 | 조건 |
|---|---|---|
| 📊 이중바닥 | 강한 반등 시작 | 두 저점이 비슷한 가격 |
| ✨ 골든크로스 | 상승 전환 | MA5 > MA20 돌파 |
| 📈 RSI 다이버전스 | 하락세 약화 | 가격↓ + RSI↑ |
| 📉 MACD 다이버전스 | 추세 전환 초기 | 가격↓ + MACD히스토그램↑ |
| 🔄 과매도 반등 | 기술적 반등 | RSI<30 + 볼린저 하단 |
| 💥 거래량 돌파 | 강한 매수세 | 거래량 20일평균 2배+ |""")


# ══ TAB4: 거시경제 ══
with tab4:
    st.markdown(f"#### 🌐 거시경제 ({base_date})")
    if macro_df is not None:
        m=macro_df.iloc[-1]
        for label,col,fmt,cc in [
            ("💵 달러/원","USD_KRW","{:,.1f}","USD_KRW_chg"),
            ("📈 S&P500","SP500","{:,.1f}","SP500_chg"),
            ("📈 나스닥","NASDAQ","{:,.1f}","NASDAQ_chg"),
            ("📊 코스피","KOSPI","{:,.2f}",None),
            ("😱 VIX","VIX","{:.2f}","VIX_chg"),
            ("🛢️ WTI","OIL_WTI","{:.2f}$","OIL_WTI_chg"),
            ("🥇 금","GOLD","{:,.1f}$","GOLD_chg"),
            ("🇺🇸 미10년채","US10Y","{:.3f}%","US10Y_chg"),
        ]:
            if col not in m: continue
            chg=m.get(cc) if cc else None
            ch_html=""
            if chg is not None and not pd.isna(chg):
                clr="#22c55e" if chg>0 else "#ef4444"
                ch_html=f'&nbsp;<span style="color:{clr};font-size:11px">{"▲" if chg>0 else "▼"}{abs(chg)*100:.2f}%</span>'
            l2,r2=st.columns([2,1])
            l2.markdown(f"<span style='font-size:13px'>{label}</span>",unsafe_allow_html=True)
            r2.markdown(f"<b style='font-size:14px'>{fmt.format(m[col])}</b>{ch_html}",unsafe_allow_html=True)
    if fi_df is not None:
        st.divider(); st.markdown("#### 🎯 예측 기여 지표 Top 20")
        fig_fi=px.bar(fi_df.head(20),x="importance_cls",y="feature",orientation="h",
                      color="importance_cls",color_continuous_scale="Blues",
                      labels={"importance_cls":"중요도","feature":"지표"})
        fig_fi.update_layout(height=380,margin=dict(l=10,r=10,t=10,b=10),
                             paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                             font_color="#ccc",coloraxis_showscale=False,yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig_fi,use_container_width=True)


# ══ TAB5: 백테스트 ══
with tab5:
    st.markdown("#### 📊 백테스트 결과")
    if bt_summary:
        st.caption(f"📅 {bt_summary.get('backtest_period','-')} | 앙상블 {bt_summary.get('n_models',1)}모델")
        c1,c2,c3,c4=st.columns(4)
        wr=bt_summary.get("win_rate",0); ar=bt_summary.get("avg_real_ret",0)
        cr=bt_summary.get("final_cumret",0); bwr=bt_summary.get("bounce_win_rate",0)
        with c1: st.markdown(f'<div class="card {"card-up" if wr>=0.5 else "card-down"}"><h4>실제 승률</h4><div class="val">{wr:.1%}</div></div>',unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="card {"card-up" if ar>0 else "card-down"}"><h4>평균수익</h4><div class="val">{ar*100:+.2f}%</div></div>',unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="card {"card-up" if cr>0 else "card-down"}"><h4>누적수익</h4><div class="val">{cr*100:+.2f}%</div></div>',unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="card {"card-up" if bwr>=0.5 else "card"}"><h4>반등신호 승률</h4><div class="val">{bwr:.1%}</div></div>',unsafe_allow_html=True)
        if bt_daily is not None:
            fig_bt=go.Figure()
            fig_bt.add_trace(go.Scatter(x=bt_daily["Date"],y=bt_daily["cumret"]*100,
                                        mode="lines",fill="tozeroy",line=dict(color="#4f8ef7",width=2),
                                        fillcolor="rgba(79,142,247,0.12)"))
            fig_bt.add_hline(y=0,line_dash="dash",line_color="#555")
            fig_bt.update_layout(height=220,margin=dict(l=10,r=10,t=10,b=30),
                                 paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                                 font_color="#ccc",showlegend=False,yaxis_title="%")
            st.plotly_chart(fig_bt,use_container_width=True)
        if bt_grade is not None:
            st.markdown("##### 등급별 실적")
            fmt={c:"{:.1%}" for c in bt_grade.columns if "승률" in c or "수익" in c}
            st.dataframe(bt_grade.style.format(fmt),use_container_width=True)
        if bt_sector is not None:
            st.markdown("##### 섹터별 실적")
            fmt2={c:"{:.1%}" for c in bt_sector.columns if "승률" in c or "수익" in c}
            st.dataframe(bt_sector.style.format(fmt2),use_container_width=True)
        st.divider(); st.markdown("> ⚠️ 과거 성과는 미래를 보장하지 않습니다.")
    else: st.info("백테스트 없음")


# ══ TAB6: 수급현황 ══
with tab6:
    st.markdown("#### 💰 수급 현황")
    if "foreign_net_20d" in df.columns:
        st.caption("수급 데이터 출처: pykrx > FinanceDataReader > yfinance EWY 추정 (순서대로 우선적용)")

        # 데이터 출처 분포
        if "supply_source" in df.columns:
            src_counts=df["supply_source"].value_counts()
            sc1,sc2,sc3=st.columns(3)
            for i,(src,cnt) in enumerate(src_counts.items()):
                label={"pykrx":"✅ KRX 직접","fdr":"📊 FinanceDataReader","yfinance_est":"📈 EWY 추정","none":"❌ 없음"}.get(src,src)
                [sc1,sc2,sc3][min(i,2)].markdown(f'<div class="card"><h4>{label}</h4><div class="val">{cnt}</div><div class="sub">종목</div></div>',unsafe_allow_html=True)
            st.divider()

        # 외국인 순매수 상위
        st.markdown("##### 🌍 외국인 순매수 상위")
        fgn=df[["name","sector","foreign_net_20d","foreign_trend","prob_up"]].copy()
        fgn=fgn.sort_values("foreign_net_20d",ascending=False)
        fgn.columns=["종목","섹터","외국인순매수(20일)","외국인추세(5일)","상승확률"]
        st.dataframe(fgn.head(15).style.format({
            "외국인순매수(20일)":"{:,.0f}","외국인추세(5일)":"{:,.0f}","상승확률":"{:.1%}"}),
            use_container_width=True,height=320)

        # 공매도 현황
        if "short_ratio" in df.columns and df["short_ratio"].abs().sum()>0:
            st.divider(); st.markdown("##### 🔻 공매도 잔고 상위")
            shr=df[["name","sector","short_ratio","prob_up"]].dropna().sort_values("short_ratio",ascending=False)
            shr.columns=["종목","섹터","공매도비율","상승확률"]
            st.dataframe(shr.head(10).style.format({"공매도비율":"{:.2f}%","상승확률":"{:.1%}"}),
                         use_container_width=True,height=260)
    else: st.info("수급 데이터 없음")


# ══ TAB7: 뉴스 ══
with tab7:
    st.markdown("#### 📰 뉴스 피드")
    st.caption("영향도(가중치)가 높은 뉴스일수록 예측에 크게 반영됩니다. 제목 클릭 → 언론사 원문 이동")
    if news_df is not None and len(news_df)>0:
        c_a,c_b=st.columns([2,1])
        with c_a: kw=st.text_input("종목명 검색",placeholder="예: 삼성전자",key="nkw")
        with c_b: sort_opt=st.selectbox("정렬",["영향도순","종목명순"],key="nsort")
        filtered=news_df[news_df["name"].str.contains(kw,na=False)] if kw else news_df.copy()
        if sort_opt=="영향도순" and "impact" in filtered.columns:
            filtered=filtered.sort_values("impact",ascending=False)
        else: filtered=filtered.sort_values("name")
        for _,nr in filtered.head(50).iterrows():
            sc=nr.get("sentiment_score",0); icon="🟢" if sc>0.1 else("🔴" if sc<-0.1 else "⚪")
            bert=nr.get("bert_score",0); w=nr.get("weight_pct",0)
            press=nr.get("press","") or ""; name_v=nr.get("name","")
            link=nr.get("link","#"); title=nr.get("title","(제목 없음)")
            st.markdown(
                f'<div class="news-row">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span class="news-tag">{icon} {name_v}{"  ·  "+press if press else ""} (BERT {bert:+.2f})</span>'
                f'<span style="font-size:10px;color:#f59e0b;">가중 {w:.0f}%</span>'
                f'</div>'
                f'<a href="{link}" target="_blank" rel="noopener">{title}</a>'
                f'</div>',unsafe_allow_html=True)
    else: st.info("뉴스 없음. 파이프라인을 재실행하세요.")

st.markdown("<div style='height:50px'></div>",unsafe_allow_html=True)