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
  html,body,[class*="css"]{font-size:15px!important;}
  .block-container{padding:.7rem .6rem 3rem!important;max-width:100%!important;}
  .card{background:#1a1f2e;border-radius:12px;padding:12px 14px;
        margin-bottom:10px;border-left:4px solid #4f8ef7;}
  .card-up  {border-left-color:#22c55e!important;}
  .card-down{border-left-color:#ef4444!important;}
  .card-gold{border-left-color:#f59e0b!important;}
  .card h4{margin:0;font-size:12px;color:#8892a4;}
  .card .val{font-size:20px;font-weight:800;color:#fff;}
  .card .sub{font-size:11px;color:#8892a4;margin-top:2px;}
  .nr{border-bottom:1px solid #2a2f3e;padding:9px 0;}
  .nr a{color:#60a5fa;font-size:13px;text-decoration:none;}
  .nt{color:#8892a4;font-size:11px;}
  .pt{display:inline-block;background:#2d3748;color:#60a5fa;
      font-size:11px;padding:2px 8px;border-radius:12px;margin:2px;}
  .pt-on{background:#1e3a2f!important;color:#4ade80!important;}
  .df td,.df th{font-size:13px!important;padding:5px 4px!important;}
  div[data-baseweb="tab-list"]{overflow-x:auto;white-space:nowrap;flex-wrap:nowrap!important;}
  button[data-baseweb="tab"]{font-size:12px!important;padding:5px 8px!important;}
  .badge-closed{background:#1e3a2f;color:#4ade80;border-radius:6px;
                padding:2px 8px;font-size:11px;font-weight:700;}
  .badge-open{background:#3a2a1e;color:#f59e0b;border-radius:6px;
              padding:2px 8px;font-size:11px;font-weight:700;}
</style>""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load():
    def sc(p):
        if not os.path.exists(p): return None
        try:
            d=pd.read_csv(p); return d if len(d)>0 else None
        except: return None
    bs={}
    for fn in ["bt_summary.json","backtest_summary.json"]:
        if os.path.exists(fn):
            try:
                with open(fn) as f: bs=json.load(f); break
            except: pass
    return (sc("full_result.csv"),sc("news_df.csv"),sc("macro_summary.csv"),
            sc("feature_importance.csv"),
            sc("bt_grade.csv"),sc("bt_daily.csv"),sc("bt_sector.csv"),bs)

df,news,macro,fi,btg,btd,bts,bts_j=load()
if df is None:
    st.error("⚠️ 데이터 없음 — Colab 파이프라인을 먼저 실행하세요"); st.stop()

base      = df.get("base_date",  pd.Series(["-"])).iloc[0]
data_note = df.get("data_note",  pd.Series([""])).iloc[0] if "data_note" in df.columns else ""
wauc      = float(df.get("wf_auc",  pd.Series([0])).iloc[0])
vauc      = float(df.get("val_auc", pd.Series([0])).iloc[0])
nm        = int(df.get("n_models",  pd.Series([1])).iloc[0])

# 장 마감 배지
is_closed = "장 마감 후" in data_note or "주말" in data_note
badge_cls = "badge-closed" if is_closed else "badge-open"
badge_txt = "✅ 당일 데이터 포함" if is_closed else "⏳ 전일 데이터 (장 중)"

st.markdown(f"""
<div style='text-align:center;padding:12px 0 4px;'>
  <div style='font-size:21px;font-weight:900;color:#60a5fa;'>📈 KOSPI 100 분석</div>
  <div style='font-size:11px;color:#8892a4;margin-top:4px;'>
    기준 <b>{base}</b> &nbsp;<span class="{badge_cls}">{badge_txt}</span><br>
    WF-AUC <b>{wauc:.3f}</b> | Val-AUC <b>{vauc:.3f}</b> | {nm}모델 앙상블
  </div>
</div>""", unsafe_allow_html=True)

T=st.tabs(["🏆 순위","🔍 종목","📉 패턴","🌐 거시경제","📊 백테스트","💰 수급","📰 뉴스"])
t1,t2,t3,t4,t5,t6,t7=T

# ── TAB1 순위 ──────────────────────────────────────────
with t1:
    st.markdown("#### 🏆 예측 순위")
    ca,cb=st.columns(2)
    with ca: tn=st.slider("개수",5,len(df),20,key="tn")
    with cb:
        secs=(["전체"]+sorted(df["sector"].dropna().unique().tolist())
              if "sector" in df.columns else ["전체"])
        ss=st.selectbox("섹터",secs,key="ss")
    gopt=df["grade"].unique().tolist() if "grade" in df.columns else []
    gsel=st.multiselect("등급",gopt,default=gopt,key="gf")
    show=df.copy()
    if gsel: show=show[show["grade"].isin(gsel)]
    if ss!="전체" and "sector" in show.columns: show=show[show["sector"]==ss]
    show=show.sort_values("prob_up",ascending=False).head(tn)

    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'<div class="card card-up"><h4>강력매수</h4><div class="val">{(df.prob_up>=0.70).sum()}</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="card"><h4>매수관심</h4><div class="val">{((df.prob_up>=0.55)&(df.prob_up<0.70)).sum()}</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="card card-down"><h4>하락주의</h4><div class="val">{(df.prob_up<0.35).sum()}</div></div>',unsafe_allow_html=True)
    with c4:
        hb=(df["bounce_score"]>=50).sum() if "bounce_score" in df.columns else 0
        st.markdown(f'<div class="card card-gold"><h4>반등신호</h4><div class="val">{hb}</div></div>',unsafe_allow_html=True)

    CM={"name":"종목","sector":"섹터","prob_up":"상승확률","pred_ret5d":"예상수익(5일)",
        "bounce_score":"반등","news_contrib_pct":"뉴스기여%",
        "dist_52w_high":"52w고가괴리","grade":"등급","Close":"현재가"}
    dc=[c for c in CM if c in show.columns]
    dp=show[dc].rename(columns=CM).reset_index(drop=True); dp.index+=1
    fm={"상승확률":"{:.1%}","예상수익(5일)":"{:+.2%}","현재가":"{:,.0f}",
        "반등":"{:.0f}","뉴스기여%":"{:.1f}%","52w고가괴리":"{:+.1%}"}
    fm={k:v for k,v in fm.items() if k in dp.columns}
    st2=dp.style.format(fm)
    if "상승확률" in dp.columns: st2=st2.background_gradient(subset=["상승확률"],cmap="RdYlGn")
    if "뉴스기여%" in dp.columns: st2=st2.background_gradient(subset=["뉴스기여%"],cmap="Oranges")
    st.dataframe(st2,use_container_width=True,height=430)

    fig=px.scatter(df,x="prob_up",y="pred_ret5d",
                   color="sector" if "sector" in df.columns else "grade",
                   size="bounce_score" if "bounce_score" in df.columns else None,
                   hover_name="name",labels={"prob_up":"상승확률","pred_ret5d":"예상수익"})
    fig.add_hline(y=0,line_dash="dash",line_color="#555")
    fig.add_vline(x=0.55,line_dash="dash",line_color="#555")
    fig.update_layout(height=260,margin=dict(l=10,r=10,t=10,b=20),
                      paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font_color="#ccc",legend_title_text="")
    st.plotly_chart(fig,use_container_width=True)

# ── TAB2 종목 ──────────────────────────────────────────
with t2:
    st.markdown("#### 🔍 종목 상세")
    sel=st.selectbox("종목",df.sort_values("prob_up",ascending=False)["name"].tolist(),key="sel")
    row=df[df["name"]==sel].iloc[0]
    pu=float(row.prob_up); pr=float(row.get("pred_ret5d",0))
    cp=float(row.get("Close",0)); pp=float(row.get("pred_price5d",cp*(1+pr)))

    c1,c2=st.columns(2)
    with c1:
        clr="card-up" if pu>=0.55 else("card-down" if pu<0.40 else "card")
        st.markdown(f'<div class="card {clr}"><h4>상승확률</h4><div class="val">{pu:.1%}</div>'
                    f'<div class="sub">하락 {1-pu:.1%} | {row.get("grade","")} | {row.get("sector","")}</div></div>',unsafe_allow_html=True)
    with c2:
        rc="card-up" if pr>0 else "card-down"
        st.markdown(f'<div class="card {rc}"><h4>5일 예상수익</h4><div class="val">{pr*100:+.2f}%</div>'
                    f'<div class="sub">예상가 {pp:,.0f}원 (현재 {cp:,.0f}원)</div></div>',unsafe_allow_html=True)

    uw=int(pu*100)
    st.markdown(f"""
    <div style='margin:8px 0 3px;font-size:12px;color:#8892a4;'>상승/하락 비율</div>
    <div style='display:flex;border-radius:8px;overflow:hidden;height:12px;'>
      <div style='width:{uw}%;background:#22c55e;'></div>
      <div style='width:{100-uw}%;background:#ef4444;'></div>
    </div>
    <div style='display:flex;justify-content:space-between;font-size:11px;color:#8892a4;margin-top:2px;'>
      <span>🟢 {pu:.1%}</span><span>🔴 {1-pu:.1%}</span>
    </div>""",unsafe_allow_html=True)

    st.divider(); st.markdown("##### 📐 기술지표")
    for k,v in {"RSI(14)":f"{row.get('rsi14',0):.1f}",
                "MACD크로스":"✅" if row.get("macd_cross",0)==1 else "❌",
                "볼린저위치":f"{row.get('bb_pct',0):.2f}",
                "거래량비율":f"{row.get('vol_ratio',0):.2f}x",
                "샤프모멘텀":f"{row.get('sharpe_mom',0):.2f}",
                "52주수익":f"{row.get('ret_52w',0)*100:+.1f}%",
                "52주고가괴리":f"{row.get('dist_52w_high',0)*100:+.1f}%",
                "52주저가반등":f"{row.get('dist_52w_low',0)*100:+.1f}%",
                "섹터상대강도":f"{row.get('sector_rel',0)*100:+.2f}%",
                "미국섹터연계":f"{row.get('us_sector_ret',0)*100:+.2f}%",
                "1d/5d/20d":f"{row.get('ret_1d',0)*100:+.2f}%/{row.get('ret_5d',0)*100:+.2f}%/{row.get('ret_20d',0)*100:+.2f}%"}.items():
        l,r2=st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True)
        r2.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    st.divider(); st.markdown("##### 📑 DART 재무")
    for k,v in {"ROE":f"{row.get('dart_roe',0):.1f}%",
                "부채비율":f"{row.get('dart_debt_ratio',0):.1f}%",
                "영업이익률":f"{row.get('dart_op_margin',0):.1f}%",
                "순이익률":f"{row.get('dart_net_margin',0):.1f}%",
                "매출 YoY":f"{row.get('dart_rev_growth',0)*100:+.1f}%",
                "영업이익 YoY":f"{row.get('dart_oi_growth',0)*100:+.1f}%"}.items():
        l,r2=st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True)
        r2.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    st.divider(); st.markdown("##### 🌐 거시 스냅샷")
    for k,v in {"한미금리차":f"{row.get('rate_diff_kr_us',0):+.3f}%p",
                "SOX(반도체)":f"{row.get('SOX',0):,.1f}",
                "KTB10Y":f"{row.get('KTB10Y',0):.3f}%",
                "US10Y":f"{row.get('US10Y',0):.3f}%",
                "달러/원":f"{row.get('USD_KRW',0):,.1f}"}.items():
        l,r2=st.columns([2,1])
        l.markdown(f"<span style='color:#8892a4;font-size:13px'>{k}</span>",unsafe_allow_html=True)
        r2.markdown(f"<b>{v}</b>",unsafe_allow_html=True)

    st.divider(); st.markdown("##### 🧠 뉴스 예측 기여도")
    nc=float(row.get("news_contrib_pct",0)); nd=float(row.get("news_direction",0))
    nc_c="#22c55e" if nd>0 else("#ef4444" if nd<0 else "#8892a4")
    dl="🟢 상승기여" if nd>0 else("🔴 하락기여" if nd<0 else "⚪ 중립")
    sm3=float(row.get("sent_ma3",0)); smom=float(row.get("sent_momentum",0))
    st.markdown(f'<div class="card" style="border-left-color:{nc_c}"><h4>뉴스·감성 기여도</h4>'
                f'<div class="val" style="color:{nc_c}">{nc:.1f}%</div>'
                f'<div class="sub">{dl} | 3일평균감성 {sm3:+.3f} | 모멘텀 {smom:+.3f}</div></div>',unsafe_allow_html=True)
    _si=[(l,float(row.get(c,0))) for c,l in [
        ("shap_sentiment","종합감성"),("shap_bert_score","BERT"),
        ("shap_news_pos","긍정"),("shap_news_neg","부정"),
        ("shap_sent_ma3","감성MA"),("shap_sent_momentum","감성모멘텀"),
        ("shap_fomc","FOMC")]]
    if any(abs(v)>1e-6 for _,v in _si):
        mx=max(abs(v) for _,v in _si)+1e-9
        for lb,val in _si:
            pct=abs(val)/mx*100; clr="#22c55e" if val>0 else "#ef4444"
            st.markdown(f"""<div style='display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px;'>
              <div style='width:70px;color:#8892a4;'>{lb}</div>
              <div style='flex:1;background:#2a2f3e;border-radius:6px;height:10px;overflow:hidden;'>
                <div style='width:{pct:.0f}%;background:{clr};height:10px;'></div></div>
              <div style='width:70px;color:{clr};text-align:right;'>{"▲" if val>0 else "▼"}{abs(val):.3f}</div>
            </div>""",unsafe_allow_html=True)

    if news is not None:
        st.divider(); st.markdown("##### 📰 관련 뉴스 (영향도순)")
        sn=news[news["name"]==sel].copy()
        if "impact" in sn.columns: sn=sn.sort_values("impact",ascending=False)
        for _,nr in sn.head(5).iterrows():
            sc2=nr.get("sentiment_score",0); ic="🟢" if sc2>0.1 else("🔴" if sc2<-0.1 else "⚪")
            w=nr.get("weight_pct",0); press=nr.get("press","") or ""; lk=nr.get("link","#")
            st.markdown(f"""<div class="nr">
              <div style='display:flex;justify-content:space-between;'>
                <span class="nt">{ic} {press}</span>
                <span style='font-size:10px;color:#f59e0b;'>가중 {w:.0f}%</span>
              </div>
              <a href="{lk}" target="_blank" rel="noopener">{nr.get("title","")}</a>
              <div style='background:#2a2f3e;border-radius:3px;height:3px;margin-top:4px;'>
                <div style='width:{min(w*2,100):.0f}%;background:#f59e0b;height:3px;'></div>
              </div></div>""",unsafe_allow_html=True)

# ── TAB3 차트패턴 ──────────────────────────────────────
with t3:
    st.markdown("#### 📉 차트패턴 & 반등")
    if "bounce_score" in df.columns:
        bt2=df.sort_values("bounce_score",ascending=False).head(15)
        d2=bt2[["name","sector","bounce_score","prob_up","pred_ret5d",
                "dist_52w_low","grade"]].copy()
        d2.columns=["종목","섹터","반등스코어","상승확률","예상수익","52w저가반등","등급"]
        d2=d2.reset_index(drop=True); d2.index+=1
        st.dataframe(d2.style.format({"반등스코어":"{:.0f}","상승확률":"{:.1%}",
                                      "예상수익":"{:+.2%}","52w저가반등":"{:+.1%}"}
                                    ).background_gradient(subset=["반등스코어"],cmap="YlOrRd"),
                     use_container_width=True,height=350)
    st.divider()
    ps2=st.selectbox("패턴분석",df.sort_values("bounce_score",ascending=False)["name"].tolist(),key="ps")
    pr2=df[df["name"]==ps2].iloc[0]
    bs=int(pr2.get("bounce_score",0))
    bc="#22c55e" if bs>=60 else("#f59e0b" if bs>=30 else "#ef4444")
    st.markdown(f'<div class="card" style="border-left-color:{bc}"><h4>반등 종합 스코어</h4>'
                f'<div class="val" style="color:{bc}">{bs}/100</div>'
                f'<div class="sub">지지 {pr2.get("support",0):,.0f}원 → 저항 {pr2.get("resistance",0):,.0f}원 | '
                f'52주저가 대비 +{pr2.get("dist_52w_low",0)*100:.1f}%</div></div>',
                unsafe_allow_html=True)
    PT={"p_db":"📊 이중바닥","p_gc":"✨ 골든크로스","p_rd":"📈 RSI다이버전스",
        "p_md":"📉 MACD다이버전스","p_os":"🔄 과매도","p_vb":"💥 거래량돌파"}
    tg="".join(f'<span class="pt{" pt-on" if int(pr2.get(c,0))==1 else ""}">{l}</span>'
               for c,l in PT.items())
    st.markdown(f"<div style='margin:10px 0;'>{tg}</div>",unsafe_allow_html=True)

# ── TAB4 거시경제 ──────────────────────────────────────
with t4:
    st.markdown(f"#### 🌐 거시경제 ({base})")
    if macro is not None:
        m=macro.iloc[-1]
        for lb,col,fmt,cc in [
            ("💵 달러/원","USD_KRW","{:,.1f}","USD_KRW_chg"),
            ("💶 유로/원","EUR_KRW","{:,.1f}",None),
            ("💴 엔/원","JPY_KRW","{:.4f}",None),
            ("🇨🇳 위안/원","CNY_KRW","{:.4f}",None),
            ("📈 S&P500","SP500","{:,.1f}","SP500_chg"),
            ("📈 나스닥","NASDAQ","{:,.1f}","NASDAQ_chg"),
            ("🇯🇵 니케이","NIKKEI","{:,.1f}","NIKKEI_chg"),
            ("🇨🇳 상해종합","SHANGHAI","{:,.2f}",None),
            ("🇭🇰 항셍","HSI","{:,.1f}","HSI_chg"),
            ("📊 코스피","KOSPI","{:,.2f}",None),
            ("😱 VIX","VIX","{:.2f}","VIX_chg"),
            ("🛢️ WTI원유","OIL_WTI","{:.2f}$","OIL_WTI_chg"),
            ("🛢️ 브렌트","OIL_BRENT","{:.2f}$",None),
            ("🥇 금","GOLD","{:,.1f}$","GOLD_chg"),
            ("🇺🇸 미10년채","US10Y","{:.3f}%","US10Y_chg"),
            ("🇰🇷 한10년채","KTB10Y","{:.3f}%","KTB10Y_chg"),
            ("📊 한미금리차","rate_diff_kr_us","{:+.3f}%p",None),
            ("💻 SOX반도체","SOX","{:,.1f}","SOX_chg"),
            ("💲 달러인덱스","DXY","{:.2f}",None)]:
            if col not in m: continue
            ch=""
            if cc and cc in m and not pd.isna(m[cc]):
                clr="#22c55e" if m[cc]>0 else "#ef4444"
                ch=f'&nbsp;<span style="color:{clr};font-size:11px">{"▲" if m[cc]>0 else "▼"}{abs(m[cc])*100:.2f}%</span>'
            la,ra=st.columns([2,1])
            la.markdown(f"<span style='font-size:13px'>{lb}</span>",unsafe_allow_html=True)
            ra.markdown(f"<b style='font-size:14px'>{fmt.format(m[col])}</b>{ch}",unsafe_allow_html=True)
    if fi is not None:
        st.divider(); st.markdown("#### 🎯 예측 기여 지표 Top 20")
        fig2=px.bar(fi.head(20),x="importance_cls",y="feature",orientation="h",
                    color="importance_cls",color_continuous_scale="Blues")
        fig2.update_layout(height=380,margin=dict(l=10,r=10,t=10,b=10),
                           paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#ccc",coloraxis_showscale=False,yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig2,use_container_width=True)

# ── TAB5 백테스트 ──────────────────────────────────────
with t5:
    st.markdown("#### 📊 백테스트 결과")
    if bts_j:
        st.caption(f"📅 {bts_j.get('period','-')} | {bts_j.get('n_models',1)}모델 | WF-AUC {bts_j.get('wf_auc',0):.3f}")
        wr=bts_j.get("win_rate",0); ar=bts_j.get("avg_ret",0); cr=bts_j.get("cumret",0)
        c1,c2,c3=st.columns(3)
        with c1: st.markdown(f'<div class="card {"card-up" if wr>=0.5 else "card-down"}"><h4>실제 승률</h4><div class="val">{wr:.1%}</div><div class="sub">prob≥0.60 기준</div></div>',unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="card {"card-up" if ar>0 else "card-down"}"><h4>평균 수익</h4><div class="val">{ar*100:+.2f}%</div><div class="sub">5일 후 평균</div></div>',unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="card {"card-up" if cr>0 else "card-down"}"><h4>누적 수익</h4><div class="val">{cr*100:+.2f}%</div><div class="sub">2.5개월</div></div>',unsafe_allow_html=True)
        if btd is not None and len(btd)>0:
            fg=go.Figure()
            fg.add_trace(go.Scatter(x=btd["Date"],y=btd["cumret"]*100,mode="lines",fill="tozeroy",
                                    line=dict(color="#4f8ef7",width=2),fillcolor="rgba(79,142,247,.12)"))
            fg.add_hline(y=0,line_dash="dash",line_color="#555")
            fg.update_layout(height=200,margin=dict(l=10,r=10,t=10,b=20),
                             paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                             font_color="#ccc",showlegend=False,yaxis_title="%")
            st.plotly_chart(fg,use_container_width=True)
        if btg is not None:
            st.markdown("##### 등급별")
            fm2={c:"{:.1%}" for c in btg.columns if "승률" in c or "수익" in c}
            st.dataframe(btg.style.format(fm2),use_container_width=True)
        if bts is not None:
            st.markdown("##### 섹터별")
            fm3={c:"{:.1%}" for c in bts.columns if "승률" in c or "수익" in c}
            st.dataframe(bts.style.format(fm3),use_container_width=True)
        ps_d=bts_j.get("pattern_stats",{})
        if ps_d:
            st.markdown("##### 패턴별")
            ps_df=pd.DataFrame(ps_d).T.reset_index()
            ps_df.columns=["패턴","신호수","승률","평균수익"]
            st.dataframe(ps_df.style.format({"승률":"{:.1%}","평균수익":"{:+.2%}"}),use_container_width=True)
        st.divider(); st.markdown("> ⚠️ 과거 성과는 미래를 보장하지 않습니다. 수수료/슬리피지 미반영.")
    else: st.info("백테스트 없음 — 파이프라인을 실행하세요")

# ── TAB6 수급 ──────────────────────────────────────────
with t6:
    st.markdown("#### 💰 수급 현황")
    if "foreign_net" in df.columns:
        if "supply_source" in df.columns:
            sc2=df["supply_source"].value_counts()
            lm2={"naver":"🟢 네이버","krx":"✅ KRX직접","pykrx":"📊 pykrx","ewy_est":"📈 EWY추정","none":"❌ 없음"}
            cols2=st.columns(min(len(sc2),4))
            for i,(k,v) in enumerate(sc2.items()):
                cols2[min(i,len(cols2)-1)].markdown(
                    f'<div class="card"><h4>{lm2.get(k,k)}</h4><div class="val">{v}</div></div>',unsafe_allow_html=True)
            st.divider()
        st.markdown("##### 🌍 외국인 순매수 상위")
        fg2=df[["name","sector","foreign_net","foreign_trend","prob_up"]].sort_values("foreign_net",ascending=False)
        fg2.columns=["종목","섹터","외국인순매수","5일추세","상승확률"]
        st.dataframe(fg2.head(15).style.format({"외국인순매수":"{:,.0f}","5일추세":"{:,.0f}","상승확률":"{:.1%}"}),
                     use_container_width=True,height=320)
        if "short_ratio" in df.columns and df.short_ratio.abs().sum()>0:
            st.divider(); st.markdown("##### 🔻 공매도 잔고")
            sh2=df[["name","sector","short_ratio","prob_up"]].sort_values("short_ratio",ascending=False).head(10)
            sh2.columns=["종목","섹터","공매도비율","상승확률"]
            st.dataframe(sh2.style.format({"공매도비율":"{:.2f}%","상승확률":"{:.1%}"}),use_container_width=True)
    else: st.info("수급 데이터 없음")

# ── TAB7 뉴스 ──────────────────────────────────────────
with t7:
    st.markdown("#### 📰 뉴스 피드")
    st.caption("영향도 높은 뉴스 → 예측에 더 크게 반영됨 | 제목 클릭 → 원문 이동")
    if news is not None and len(news)>0:
        ca2,cb2=st.columns([2,1])
        with ca2: kw=st.text_input("종목 검색",placeholder="예: 삼성전자",key="nkw")
        with cb2: srt=st.selectbox("정렬",["영향도순","종목명순"],key="ns")
        fl=news[news["name"].str.contains(kw,na=False)] if kw else news.copy()
        if srt=="영향도순" and "impact" in fl.columns: fl=fl.sort_values("impact",ascending=False)
        for _,nr in fl.head(50).iterrows():
            sc3=nr.get("sentiment_score",0); ic2="🟢" if sc3>0.1 else("🔴" if sc3<-0.1 else "⚪")
            b=nr.get("bert_score",0); w=nr.get("weight_pct",0)
            press2=nr.get("press","") or ""; nv=nr.get("name","")
            st.markdown(
                f'<div class="nr">'
                f'<div style="display:flex;justify-content:space-between;">'
                f'<span class="nt">{ic2} {nv}{" · "+press2 if press2 else ""} (BERT {b:+.2f})</span>'
                f'<span style="font-size:10px;color:#f59e0b;">가중 {w:.0f}%</span>'
                f'</div>'
                f'<a href="{nr.get("link","#")}" target="_blank" rel="noopener">{nr.get("title","")}</a>'
                f'</div>',unsafe_allow_html=True)
    else: st.info("뉴스 없음 — 파이프라인을 재실행하세요")

st.markdown("<div style='height:50px'></div>",unsafe_allow_html=True)