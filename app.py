# app.py  ──  Streamlit Community Cloud 대시보드
"""
streamlit.app 배포용 대시보드
─────────────────────────────
데이터 소스: GitHub RAW (Colab이 매일 업로드한 signals_detail.json)

배포 설정:
  requirements.txt에 추가:
    streamlit>=1.32
    pandas
    requests
    plotly
"""

import json, requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime

# ════════════════════════════════════════════════════════════════════════════
# 설정
# ════════════════════════════════════════════════════════════════════════════

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/jacob-ygm/krx-dashboard/main"
JSON_URL  = f"{GITHUB_RAW_BASE}/data/signals_detail.json"
CSV_URL   = f"{GITHUB_RAW_BASE}/data/signals_latest.csv.gz"

def get_currency(ticker: str):
    """KRX면 ₩/,.0f, 미국이면 $/.2f"""
    if str(ticker).isdigit():
        return "₩", ",.0f"
    return "$", ",.2f"

def fmt_price(ticker: str, price) -> str:
    """가격 포맷팅"""
    try:
        if price in (None, "", "?", 0): return "—"
        sym, fmt = get_currency(ticker)
        return f"{sym}{float(price):{fmt}}"
    except:
        return "—"

SIGNAL_COLOR = {
    "STRONG BUY":  "#00C853",
    "BUY":         "#69F0AE",
    "HOLD":        "#FFD600",
    "SELL":        "#FF6D00",
    "STRONG SELL": "#D50000",
}
CONF_ICON = {"HIGH": "🔵", "MEDIUM": "🟡", "LOW": "⚪"}

# ════════════════════════════════════════════════════════════════════════════
# 데이터 로드
# ════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)   # 30분 캐시
def load_data():
    """GitHub에서 신호 JSON 로드"""
    try:
        r = requests.get(JSON_URL, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}\n\nColab 파이프라인을 먼저 실행해주세요.")
        return None


def signals_to_df(data: dict) -> pd.DataFrame:
    rows = []
    for s in data.get("signals", []):
        rows.append({
            "ticker":         s["ticker"],
            "name":           s["name"],
            "signal":         s["signal"],
            "confidence":     s["confidence"],
            "score":          s["overall_score"],
            "매크로":          s["scores"]["macro"],
            "펀더멘털":         s["scores"]["fundamental"],
            "수급":            s["scores"]["supply_demand"],
            "기술":            s["scores"]["technical"],
            "모멘텀":          s["scores"]["momentum"],
            "현재가":          s.get("current_price"),
            "진입하단":         s["entry_zone"]["low"],
            "진입상단":         s["entry_zone"]["high"],
            "목표가":          s.get("target_price"),
            "손절가":          s.get("stop_loss"),
            "근거":            "\n".join(s.get("top_reasons", [])),
            "리스크":          "\n".join(s.get("risk_flags", [])),
        })
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════════════════════════
# 레이아웃 컴포넌트
# ════════════════════════════════════════════════════════════════════════════

def regime_badge(regime: str) -> str:
    colors = {"RISK-ON": "#00C853", "NEUTRAL": "#FFD600", "RISK-OFF": "#D50000"}
    icons  = {"RISK-ON": "🟢", "NEUTRAL": "🟡", "RISK-OFF": "🔴"}
    c = colors.get(regime, "#888")
    icon = icons.get(regime, "⚪")
    return f"{icon} **{regime}**"


def macro_cards(macro: dict):
    """매크로 지표 카드 행"""
    keys = [
        ("VIX",       "VIX 공포지수", "↓낮을수록 호"),
        ("S&P500",    "S&P500",       ""),
        ("NASDAQ",    "NASDAQ",       ""),
        ("USD/KRW",   "USD/KRW",      "↓낮을수록 호"),
        ("DXY",       "달러인덱스",   "↓낮을수록 호"),
        ("WTI",       "WTI 유가",     ""),
        ("Copper",    "구리",         "경기선행"),
        ("KOSPI",     "KOSPI",        ""),
    ]
    cols = st.columns(len(keys))
    for col, (k, label, hint) in zip(cols, keys):
        d = macro.get(k, {})
        val = d.get("value", 0)
        chg = d.get("chg_pct", 0)
        arrow = "▲" if chg >= 0 else "▼"
        color = "normal" if chg >= 0 else "inverse"
        col.metric(label=f"{label}", value=f"{val:,.2f}",
                   delta=f"{arrow}{abs(chg):.2f}%", delta_color=color,
                   help=hint)


def score_radar(signal: dict):
    """레이더 차트 (개별 종목 점수)"""
    cats   = ["매크로","펀더멘털","수급","기술","모멘텀"]
    scores = signal[cats].values.tolist()
    maxs   = [25, 20, 20, 20, 15]
    pct    = [s / m * 100 for s, m in zip(scores, maxs)]

    fig = go.Figure(go.Scatterpolar(
        r=pct + [pct[0]],
        theta=cats + [cats[0]],
        fill="toself",
        fillcolor="rgba(99,179,237,0.3)",
        line_color="#63B3ED",
        name="점수",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=280,
        margin=dict(l=30, r=30, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def score_bar_chart(df: pd.DataFrame):
    """전체 종목 점수 수평 바 차트"""
    df_sorted = df.sort_values("score", ascending=True).tail(30)
    colors = [SIGNAL_COLOR.get(s, "#888") for s in df_sorted["signal"]]
    fig = go.Figure(go.Bar(
        x=df_sorted["score"],
        y=df_sorted["name"],
        orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}" for s in df_sorted["score"]],
        textposition="outside",
    ))
    fig.update_layout(
        height=max(400, len(df_sorted) * 22),
        xaxis=dict(range=[0, 100], title="종합 점수"),
        yaxis=dict(tickfont=dict(size=11)),
        margin=dict(l=10, r=60, t=10, b=30),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#F8FAFC",
        font=dict(color="#0F172A"),
    )
    return fig


def signal_distribution(df: pd.DataFrame):
    """신호 분포 파이 차트"""
    counts = df["signal"].value_counts().reset_index()
    counts.columns = ["signal", "count"]
    fig = px.pie(counts, names="signal", values="count",
                 color="signal",
                 color_discrete_map=SIGNAL_COLOR,
                 hole=0.45)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(showlegend=False, height=250,
                      margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="#FFFFFF")
    return fig


# ════════════════════════════════════════════════════════════════════════════
# 메인 앱
# ════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="KRX Signal Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # ── 스타일 ────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@300;400;600&family=IBM+Plex+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] { font-family: 'IBM Plex Sans KR', sans-serif; }
    .stApp { background: #FFFFFF; color: #0F172A; }

    .sig-badge {
        display: inline-block; padding: 3px 12px; border-radius: 6px;
        font-family: 'IBM Plex Mono', monospace; font-size: 0.78rem;
        font-weight: 700; letter-spacing: 0.08em;
    }
    .card {
        background: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 8px; padding: 16px; margin-bottom: 8px;
    }
    .ticker-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem; color: #64748B; letter-spacing: 0.1em;
    }
    .price-big {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.6rem; font-weight: 600; color: #0F172A;
    }
    .reason-list { font-size: 0.82rem; color: #475569; line-height: 1.8; }
    .risk-flag { font-size: 0.78rem; color: #DC2626; font-weight: 600; }
    div[data-testid="metric-container"] {
        background: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 8px; padding: 12px 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    div[data-testid="metric-container"] label {
        color: #64748B !important; font-size: 0.8rem !important;
    }
    div[data-testid="metric-container"] div[data-testid="metric-value"] {
        color: #0F172A !important; font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600; color: #475569;
    }
    .stTabs [aria-selected="true"] {
        color: #1D4ED8 !important;
    }
    [data-testid="stSidebar"] {
        background: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── 헤더 ─────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:4px; padding:8px 0;">
        <span style="font-size:1.8rem; font-weight:700; letter-spacing:-0.02em; color:#0F172A;">📈 KRX Signal</span>
        <span style="font-size:0.85rem; color:#64748B; font-family:'IBM Plex Mono',monospace;">KOSPI · NASDAQ · S&P500</span>
    </div>
    """, unsafe_allow_html=True)

    # ── 데이터 로드 ───────────────────────────────────────────────────────
    with st.spinner("데이터 로딩 중..."):
        data = load_data()

    if not data:
        st.info("📌 **첫 사용 안내**: Colab에서 `run_pipeline.py`를 실행하면 GitHub에 데이터가 업로드되고 이 대시보드에 표시됩니다.")
        return

    df = signals_to_df(data)
    macro = data.get("macro", {})
    regime = data.get("regime", "NEUTRAL")
    updated = data.get("updated", "—")

    # ── 사이드바 ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🎛 필터")
        sig_filter = st.multiselect(
            "신호 필터",
            ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
            default=["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"],
        )
        conf_filter = st.multiselect(
            "신뢰도",
            ["HIGH", "MEDIUM", "LOW"],
            default=["HIGH", "MEDIUM", "LOW"],
        )
        st.markdown("---")
        st.markdown(f"**마지막 업데이트**\n\n`{updated}`")
        st.markdown(f"**매크로 레짐**\n\n{regime_badge(regime)}")
        st.markdown("---")
        if st.button("🔄 데이터 새로고침"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.markdown("**가중치 (현재)**")
        st.caption("매크로 25% · 펀더멘털 20%\n수급 20% · 기술 20% · 모멘텀 15%")

    # ── 매크로 섹션 ───────────────────────────────────────────────────────
    st.markdown(f"#### 🌐 매크로 환경  {regime_badge(regime)}")
    macro_cards(macro)
    st.markdown("---")

    # ── 필터 적용 ─────────────────────────────────────────────────────────
    df_filt = df[df["signal"].isin(sig_filter) & df["confidence"].isin(conf_filter)]

    # ── 요약 메트릭 ──────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    for col, sig in zip([c1, c2, c3, c4, c5],
                         ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]):
        cnt = (df["signal"] == sig).sum()
        col.metric(sig, cnt)

    st.markdown("---")

    # ── 탭 레이아웃 ──────────────────────────────────────────────────────
    df_filt = df_filt.copy()
    df_filt["market"] = df_filt["ticker"].apply(lambda x: "KR" if str(x).isdigit() else "US")

    tab_kr, tab_us, tab_watch, tab2, tab3, tab4 = st.tabs(["🇰🇷 한국", "🇺🇸 미국", "👀 관찰 대상", "📊 점수 분석", "🔍 종목 상세", "🧪 백테스트"])

    # ─── 탭1: 신호 리스트 ────────────────────────────────────────────────
    def render_signal_list(df_filt):
        if df_filt.empty:
            st.info("선택한 조건에 해당하는 종목이 없습니다.")
        else:
            for _, row in df_filt.iterrows():
                sig   = row["signal"]
                color = SIGNAL_COLOR.get(sig, "#888")
                conf  = CONF_ICON.get(row["confidence"], "⚪")
                price = row.get("현재가")
                price_str = (lambda v: f"₩{float(v):,.0f}" if v not in (None,"","?") else "—")(float(price)) if price not in (None, "", "?") else "—"

                with st.container():
                    c_main, c_price, c_zone = st.columns([3, 2, 3])

                    with c_main:
                        st.markdown(
                            f'<span class="ticker-label">{row["ticker"]}</span>  '
                            f'**{row["name"]}**  '
                            f'<span class="sig-badge" style="background:{color}22;color:{color};border:1px solid {color}66">{sig}</span>  '
                            f'{conf} **{row["score"]:.0f}점**',
                            unsafe_allow_html=True
                        )
                        reasons = row["근거"].split("\n") if row["근거"] else []
                        reason_html = "  ".join([f"· {r}" for r in reasons[:3] if r])
                        st.markdown(f'<div class="reason-list">{reason_html}</div>',
                                    unsafe_allow_html=True)

                    with c_price:
                        st.markdown(f'<div class="price-big">{price_str}</div>',
                                    unsafe_allow_html=True)
                        if row.get("목표가"):
                            st.caption(f"목표 {fmt_price(row['ticker'], row['목표가'])}")

                    with c_zone:
                        if row.get("진입하단") and row.get("진입상단"):
                            try:
                                st.caption(
                                    f"진입: {fmt_price(row['ticker'], row['진입하단'])} ~ "
                                    f"{fmt_price(row['ticker'], row['진입상단'])}  |  "
                                    f"손절: {fmt_price(row['ticker'], row['손절가'])}"
                                )
                            except: pass
                        if row["리스크"]:
                            for rf in row["리스크"].split("\n")[:1]:
                                if rf:
                                    st.markdown(f'<div class="risk-flag">⚠ {rf}</div>',
                                                unsafe_allow_html=True)

                    st.divider()

    # ─── 탭2: 점수 분석 ──────────────────────────────────────────────────
    with tab_kr:
        kr_df = df_filt[df_filt["market"] == "KR"]
        st.caption(f"한국 주식 {len(kr_df)}종목")
        render_signal_list(kr_df)

    with tab_us:
        us_df = df_filt[df_filt["market"] == "US"]
        st.caption(f"미국 주식 {len(us_df)}종목")
        render_signal_list(us_df)

    with tab_watch:
        st.markdown("#### 👀 관찰 대상 — 게이트 대기 종목")
        st.caption("BUY 조건(60점)을 넘었지만 검증된 안전 게이트에 걸려 대기 중인 종목입니다.")
        watch_rows = [s for s in data.get("signals", []) if s.get("gate_reason")]
        if not watch_rows:
            st.info("현재 게이트 대기 종목이 없습니다.")
        else:
            for s in sorted(watch_rows, key=lambda x: -x["overall_score"]):
                mkt = "🇰🇷" if str(s["ticker"]).isdigit() else "🇺🇸"
                st.markdown(f'{mkt} **{s["name"]}** `{s["ticker"]}` — {s["overall_score"]:.1f}점')
                st.markdown(f'<span style="color:#DC2626; font-size:0.85rem;">⛔ {s.get("gate_reason","")}</span>', unsafe_allow_html=True)
                st.divider()

    with tab2:
        col_bar, col_pie = st.columns([3, 1])
        with col_bar:
            st.markdown("**종목별 종합 점수**")
            st.plotly_chart(score_bar_chart(df_filt), use_container_width=True)
        with col_pie:
            st.markdown("**신호 분포**")
            st.plotly_chart(signal_distribution(df), use_container_width=True)

        st.markdown("---")
        st.markdown("**점수 상세 테이블**")
        display_cols = ["ticker","name","signal","confidence","score","매크로","펀더멘털","수급","기술","모멘텀","현재가","목표가","손절가"]
        st.dataframe(
            df_filt[display_cols].sort_values("score", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "score":   st.column_config.ProgressColumn("종합", min_value=0, max_value=100),
                "매크로":  st.column_config.NumberColumn(format="%.1f"),
                "펀더멘털": st.column_config.NumberColumn(format="%.1f"),
                "수급":    st.column_config.NumberColumn(format="%.1f"),
                "기술":    st.column_config.NumberColumn(format="%.1f"),
                "모멘텀":  st.column_config.NumberColumn(format="%.1f"),
                "현재가":  st.column_config.NumberColumn(format="₩%,.0f"),
                "목표가":  st.column_config.NumberColumn(format="₩%,.0f"),
                "손절가":  st.column_config.NumberColumn(format="₩%,.0f"),
            }
        )

    # ─── 탭3: 종목 상세 ──────────────────────────────────────────────────
    with tab3:
        ticker_list = df_filt["name"].tolist()
        if not ticker_list:
            st.info("필터 조건을 조정해주세요.")
        else:
            sel_name = st.selectbox("종목 선택", ticker_list)
            row = df_filt[df_filt["name"] == sel_name].iloc[0]
            sig_data = next(
                (s for s in data["signals"] if s["name"] == sel_name), None
            )

            col_radar, col_detail = st.columns([1, 2])

            with col_radar:
                st.markdown(f"**{row['name']}** `{row['ticker']}`")
                sig   = row["signal"]
                color = SIGNAL_COLOR.get(sig, "#888")
                st.markdown(
                    f'<span class="sig-badge" style="font-size:1rem;background:{color}22;color:{color};border:1px solid {color}66">{sig}</span>  '
                    f'{CONF_ICON.get(row["confidence"],"⚪")} {row["confidence"]}',
                    unsafe_allow_html=True
                )
                st.plotly_chart(score_radar(row), use_container_width=True)

            with col_detail:
                st.markdown("**📌 핵심 근거**")
                for r in row["근거"].split("\n"):
                    if r: st.markdown(f"- {r}")

                if row["리스크"]:
                    st.markdown("**⚠️ 리스크 요인**")
                    for r in row["리스크"].split("\n"):
                        if r: st.markdown(f"- :orange[{r}]")

                st.markdown("**💰 가격 레벨**")
                pc1, pc2, pc3, pc4 = st.columns(4)
                pc1.metric("현재가",   fmt_price(row["ticker"], row.get('현재가')))
                pc2.metric("진입 하단", fmt_price(row["ticker"], row.get('진입하단')))
                pc3.metric("목표가",   fmt_price(row["ticker"], row.get('목표가')))
                pc4.metric("손절가",   fmt_price(row["ticker"], row.get('손절가')))

                if sig_data and sig_data.get("indicators"):
                    with st.expander("🔧 기술적 지표 상세"):
                        ind = sig_data["indicators"]
                        tc1, tc2 = st.columns(2)
                        tc1.metric("RSI(14)", f"{ind.get('rsi', '—')}")
                        tc1.metric("MACD Hist", f"{ind.get('macd_hist', '—')}")
                        tc1.metric("BB %", f"{ind.get('bb_pct', '—')}%")
                        tc2.metric("거래량 배율", f"{ind.get('vol_ratio', '—')}x")
                        tc2.metric("추세 강도", f"{ind.get('trend_strength', '—')}")
                        flags = []
                        if ind.get("golden_cross"): flags.append("✅ 골든크로스")
                        if ind.get("dead_cross"):   flags.append("❌ 데드크로스")
                        if ind.get("ma_aligned_up"): flags.append("✅ MA 정배열")
                        if ind.get("macd_cross_up"): flags.append("✅ MACD 골든크로스")
                        if ind.get("macd_bull_divergence"): flags.append("✅ 강세 다이버전스")
                        if flags:
                            st.markdown("  ".join(flags))

    # ─── 탭4: 백테스트 ──────────────────────────────────────────────────────
    with tab4:
        st.markdown("#### 🧪 신호 정확도 백테스트")
        st.caption("신호 발생일 종가 매수 → n일 후 종가 매도 기준")

        # GitHub에서 히스토리 로드
        HIST_URL = f"{GITHUB_RAW_BASE}/data/signals_history.csv.gz"

        @st.cache_data(ttl=3600)
        def load_history():
            try:
                import io
                r = requests.get(HIST_URL, timeout=15)
                r.raise_for_status()
                return pd.read_csv(io.BytesIO(r.content), compression="gzip")
            except:
                return None

        history = load_history()

        if history is None or history.empty:
            st.info("📌 아직 히스토리 데이터가 없습니다. 며칠간 파이프라인을 실행하면 백테스트가 가능합니다.")
        else:
            n_days  = history["signal_date"].nunique()
            n_sigs  = len(history)
            st.markdown(f"**누적 데이터**: {n_days}일치 · {n_sigs}건")

            # 날짜별 신호 분포
            sig_counts = history.groupby(["signal_date","signal"]).size().reset_index(name="count")
            fig_hist = px.bar(sig_counts, x="signal_date", y="count", color="signal",
                color_discrete_map=SIGNAL_COLOR, barmode="stack",
                title="날짜별 신호 분포")
            fig_hist.update_layout(height=250, margin=dict(t=30,b=20),
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#E0E0E0"))
            st.plotly_chart(fig_hist, use_container_width=True)

            st.markdown("---")

            # 평가 가능한 신호만 필터
            today = pd.Timestamp.now()
            buy_sell = history[history["signal"].isin(["STRONG BUY","BUY","SELL","STRONG SELL"])].copy()
            buy_sell["signal_date"] = pd.to_datetime(buy_sell["signal_date"])

            col5, col20 = st.columns(2)

            for col, n, label in [(col5, 5, "5일 단기"), (col20, 20, "20일 장기")]:
                with col:
                    st.markdown(f"**{label} 백테스트**")
                    cutoff = today - pd.Timedelta(days=n*2)
                    eval_df = buy_sell[buy_sell["signal_date"] <= cutoff]

                    if eval_df.empty:
                        st.info(f"최소 {n*2}일 이상 데이터 필요")
                        continue

                    # return_pct 컬럼 있으면 사용
                    if f"return_{n}d" in eval_df.columns:
                        ret_col = f"return_{n}d"
                        valid = eval_df[eval_df[ret_col].notna()]
                        if valid.empty:
                            st.info("수익률 데이터 없음")
                            continue

                        win_rate   = (valid[ret_col] > 0).mean() * 100
                        avg_ret    = valid[ret_col].mean()
                        std_ret    = valid[ret_col].std()
                        sharpe     = avg_ret / std_ret * (252/n)**0.5 if std_ret > 0 else 0

                        m1, m2, m3 = st.columns(3)
                        m1.metric("승률",        f"{win_rate:.1f}%")
                        m2.metric("평균수익률",   f"{avg_ret:+.2f}%")
                        m3.metric("Sharpe",      f"{sharpe:.2f}")

                        # 신호별 승률
                        by_sig = valid.groupby("signal").agg(
                            건수=(ret_col,"count"),
                            승률=(ret_col, lambda x: f"{(x>0).mean()*100:.0f}%"),
                            평균수익률=(ret_col, lambda x: f"{x.mean():+.2f}%")
                        )
                        st.dataframe(by_sig, use_container_width=True)
                    else:
                        st.info(f"수익률 컬럼 없음 — 파이프라인 재실행 후 데이터 쌓이면 자동 계산됩니다")
                        st.metric("평가 대상 신호", f"{len(eval_df)}건")

    # ── 푸터 ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.caption(
        f"📡 데이터: pykrx · Naver Finance · yfinance  |  "
        f"⏱ 업데이트: {updated}  |  "
        f"⚠️ 본 신호는 참고용이며 투자 조언이 아닙니다."
    )


if __name__ == "__main__":
    main()
