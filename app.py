"""
KOSPI 대시보드 — 키움 REST API + pykrx
탭 1: 현재가 순위  탭 2: 계좌 현황  탭 3: 기술지표 스크리너
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pykrx import stock as pykrx_stock

st.set_page_config(page_title="KOSPI 대시보드", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  html,body,[class*="css"]{font-size:14px!important;}
  .block-container{padding:1rem 1.2rem 3rem!important;}
  .card{background:#1a1f2e;border-radius:10px;padding:14px 16px;
        margin-bottom:10px;border-left:4px solid #4f8ef7;}
  .card-up{border-left-color:#22c55e!important;}
  .card-down{border-left-color:#ef4444!important;}
  .card-gold{border-left-color:#f59e0b!important;}
  .card h4{margin:0;font-size:11px;color:#8892a4;}
  .card .val{font-size:22px;font-weight:800;color:#fff;}
  .card .sub{font-size:11px;color:#8892a4;margin-top:3px;}
</style>""", unsafe_allow_html=True)


# ── 날짜 헬퍼 ───────────────────────────────────────────────
def _trading_days(n: int) -> tuple[str, str]:
    """오늘 기준 n 영업일 전 ~ 오늘 날짜를 YYYYMMDD 문자열로 반환."""
    end = datetime.today()
    # 충분한 캘린더 일수 (n*2 를 넉넉히 가져감)
    start = end - timedelta(days=n * 2)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


# ── RSI 계산 ─────────────────────────────────────────────────
def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.rolling(period).mean().iloc[-1]
    avg_l = loss.rolling(period).mean().iloc[-1]
    if avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


# ── 시장 데이터 로드 (캐시, 수동 갱신) ──────────────────────
@st.cache_data(show_spinner=False)
def load_market_data(refresh_key: int) -> pd.DataFrame:
    """
    pykrx로 코스피 전 종목 최근 25일치 OHLCV 수집.
    RSI(14), 거래량비율, 52주 고저 거리 계산 후 반환.
    """
    fromdate, todate = _trading_days(25)

    # 오늘 종가 기준 전체 종목 스냅샷
    today_str = datetime.today().strftime("%Y%m%d")
    try:
        snap = pykrx_stock.get_market_ohlcv(today_str, market="KOSPI")
    except Exception:
        # 장 마감 전이면 전일 사용
        prev = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")
        snap = pykrx_stock.get_market_ohlcv(prev, market="KOSPI")

    if snap is None or len(snap) == 0:
        return pd.DataFrame()

    snap = snap.reset_index().rename(columns={
        "티커": "code", "종목명": "name",
        "시가": "open", "고가": "high", "저가": "low",
        "종가": "close", "거래량": "volume", "거래대금": "value",
        "등락률": "chg_pct",
    })
    # pykrx 컬럼명 대응 (버전별 차이)
    if "name" not in snap.columns:
        name_map = pykrx_stock.get_market_ticker_name
        snap["name"] = snap["code"].apply(lambda c: _safe_name(c, name_map))

    snap["code"] = snap["code"].astype(str).str.zfill(6)

    # 25일치 개별 히스토리로 RSI·거래량비율 계산
    rsi_vals, vol_ratio_vals = {}, {}
    from52_high, from52_low = {}, {}

    fromdate_52, _ = _trading_days(260)

    for code in snap["code"].tolist():
        try:
            hist = pykrx_stock.get_market_ohlcv(fromdate, todate, code)
            if hist is None or len(hist) < 15:
                continue
            rsi_vals[code] = _rsi(hist["종가"])
            avg_vol = hist["거래량"].mean()
            cur_vol = hist["거래량"].iloc[-1]
            vol_ratio_vals[code] = round(cur_vol / avg_vol, 2) if avg_vol > 0 else 0

            hist52 = pykrx_stock.get_market_ohlcv(fromdate_52, todate, code)
            if hist52 is not None and len(hist52) > 0:
                h52 = hist52["고가"].max()
                l52 = hist52["저가"].min()
                cur = hist["종가"].iloc[-1]
                from52_high[code] = round((cur / h52 - 1) * 100, 2) if h52 > 0 else 0
                from52_low[code]  = round((cur / l52 - 1) * 100, 2) if l52 > 0 else 0
        except Exception:
            continue

    snap["rsi14"]         = snap["code"].map(rsi_vals)
    snap["vol_ratio"]     = snap["code"].map(vol_ratio_vals)
    snap["dist_52w_high"] = snap["code"].map(from52_high)
    snap["dist_52w_low"]  = snap["code"].map(from52_low)

    # 섹터 정보
    try:
        sector_df = pykrx_stock.get_market_sector_classifications(today_str, market="KOSPI")
        sector_df = sector_df.reset_index()
        if "티커" in sector_df.columns and "계정" in sector_df.columns:
            sector_map = dict(zip(sector_df["티커"].str.zfill(6), sector_df["계정"]))
            snap["sector"] = snap["code"].map(sector_map).fillna("기타")
        else:
            snap["sector"] = "기타"
    except Exception:
        snap["sector"] = "기타"

    return snap


def _safe_name(code: str, fn) -> str:
    try:
        return fn(code)
    except Exception:
        return code


# ── 계좌 데이터 ──────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_account(refresh_key: int) -> tuple[dict, list]:
    try:
        from kiwoom_trading import account
        dep = account.get_deposit()
        pos = account.get_positions()
        return dep, pos
    except Exception as e:
        return {"error": str(e)}, []


# ── 새로고침 상태 ─────────────────────────────────────────────
if "refresh_key" not in st.session_state:
    st.session_state.refresh_key = 0

# ── 헤더 ─────────────────────────────────────────────────────
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.markdown("## 📈 KOSPI 대시보드")
with col_btn:
    st.markdown("<div style='padding-top:12px'>", unsafe_allow_html=True)
    if st.button("🔄 새로고침", use_container_width=True):
        st.session_state.refresh_key += 1
        st.cache_data.clear()
    st.markdown("</div>", unsafe_allow_html=True)

# ── 데이터 로드 ───────────────────────────────────────────────
with st.spinner("시장 데이터 로딩 중..."):
    df = load_market_data(st.session_state.refresh_key)

dep, pos = load_account(st.session_state.refresh_key)

if df is None or len(df) == 0:
    st.error("시장 데이터를 불러오지 못했습니다.")
    st.stop()

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
st.caption(f"기준: {now_str} | 종목 수: {len(df):,}개")

T = st.tabs(["🏆 현재가 순위", "💰 계좌 현황", "🔍 기술지표 스크리너"])
t1, t2, t3 = T


# ── TAB1: 현재가 순위 ─────────────────────────────────────────
with t1:
    st.markdown("#### 🏆 코스피 전종목 순위")

    ca, cb, cc = st.columns(3)
    with ca:
        sort_by = st.selectbox("정렬 기준", ["등락률↑", "등락률↓", "거래량↑", "거래대금↑"], key="sort")
    with cb:
        sectors = ["전체"] + sorted(df["sector"].dropna().unique().tolist()) if "sector" in df.columns else ["전체"]
        sel_sec = st.selectbox("섹터", sectors, key="sec")
    with cc:
        top_n = st.slider("표시 종목 수", 20, 200, 50, key="topn")

    show = df.copy()
    if sel_sec != "전체":
        show = show[show["sector"] == sel_sec]

    sort_map = {
        "등락률↑": ("chg_pct", False),
        "등락률↓": ("chg_pct", True),
        "거래량↑":  ("volume",  False),
        "거래대금↑": ("value",   False),
    }
    s_col, s_asc = sort_map[sort_by]
    if s_col in show.columns:
        show = show.sort_values(s_col, ascending=s_asc)
    show = show.head(top_n)

    # 요약 카드
    up_cnt   = (df["chg_pct"] > 0).sum() if "chg_pct" in df.columns else 0
    down_cnt = (df["chg_pct"] < 0).sum() if "chg_pct" in df.columns else 0
    flat_cnt = len(df) - up_cnt - down_cnt

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card card-up"><h4>상승</h4><div class="val">{up_cnt}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card card-down"><h4>하락</h4><div class="val">{down_cnt}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><h4>보합</h4><div class="val">{flat_cnt}</div></div>', unsafe_allow_html=True)
    with c4:
        avg_chg = df["chg_pct"].mean() if "chg_pct" in df.columns else 0
        clr = "card-up" if avg_chg >= 0 else "card-down"
        st.markdown(f'<div class="card {clr}"><h4>평균 등락률</h4><div class="val">{avg_chg:+.2f}%</div></div>', unsafe_allow_html=True)

    # 등락률 산포도
    if "chg_pct" in df.columns and "volume" in df.columns:
        fig = go.Figure(go.Scatter(
            x=df["chg_pct"], y=np.log1p(df["volume"]),
            mode="markers",
            marker=dict(
                color=df["chg_pct"],
                colorscale="RdYlGn",
                size=6, opacity=0.6,
                colorbar=dict(title="등락률%"),
            ),
            text=df.get("name", df["code"]),
            hovertemplate="%{text}<br>등락률: %{x:.2f}%<extra></extra>",
        ))
        fig.add_vline(x=0, line_dash="dash", line_color="#555")
        fig.update_layout(
            height=220, margin=dict(l=10, r=10, t=10, b=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", xaxis_title="등락률(%)", yaxis_title="거래량(log)",
        )
        st.plotly_chart(fig, use_container_width=True)

    # 테이블
    disp_cols = {c: c for c in ["name", "sector", "close", "chg_pct", "volume", "value", "rsi14", "vol_ratio"] if c in show.columns}
    label_map = {"name": "종목명", "sector": "섹터", "close": "현재가",
                 "chg_pct": "등락률%", "volume": "거래량", "value": "거래대금",
                 "rsi14": "RSI(14)", "vol_ratio": "거래량비율"}
    disp = show[[c for c in disp_cols]].rename(columns=label_map).reset_index(drop=True)
    disp.index += 1
    fmt = {}
    if "현재가"  in disp.columns: fmt["현재가"]  = "{:,.0f}"
    if "등락률%" in disp.columns: fmt["등락률%"] = "{:+.2f}%"
    if "거래량"  in disp.columns: fmt["거래량"]  = "{:,.0f}"
    if "거래대금" in disp.columns: fmt["거래대금"] = "{:,.0f}"
    if "RSI(14)" in disp.columns: fmt["RSI(14)"] = "{:.1f}"
    if "거래량비율" in disp.columns: fmt["거래량비율"] = "{:.2f}x"

    styled = disp.style.format(fmt)
    if "등락률%" in disp.columns:
        styled = styled.background_gradient(subset=["등락률%"], cmap="RdYlGn")
    st.dataframe(styled, use_container_width=True, height=480)


# ── TAB2: 계좌 현황 ──────────────────────────────────────────
with t2:
    st.markdown("#### 💰 계좌 현황")

    if "error" in dep:
        st.error(f"계좌 조회 실패: {dep['error']}")
    else:
        ord_alow  = int(dep.get("ord_alow_amt",  "0").lstrip("0") or "0")
        d2_pymn   = int(dep.get("d2_pymn_alow_amt", "0").lstrip("0") or "0")
        entr      = int(dep.get("entr", "0").lstrip("0") or "0")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="card"><h4>예수금</h4><div class="val">{entr:,}원</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="card card-up"><h4>주문가능금액</h4><div class="val">{ord_alow:,}원</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="card"><h4>D+2 출금가능</h4><div class="val">{d2_pymn:,}원</div></div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("#### 📋 보유 종목")
    if not pos:
        st.info("보유 종목 없음 (모의투자 모드에서는 조회 불가)")
    else:
        pos_df = pd.DataFrame(pos)
        st.dataframe(pos_df, use_container_width=True)


# ── TAB3: 기술지표 스크리너 ──────────────────────────────────
with t3:
    st.markdown("#### 🔍 기술지표 스크리너")
    st.caption("RSI·거래량비율 기준으로 종목 필터링")

    sc = df.dropna(subset=["rsi14"]).copy()

    ca, cb, cc = st.columns(3)
    with ca:
        rsi_range = st.slider("RSI(14) 범위", 0, 100, (0, 40), key="rsi_range")
    with cb:
        vol_min = st.number_input("거래량비율 최소 (x)", 0.0, 20.0, 1.5, 0.1, key="vol_min")
    with cc:
        chg_range = st.slider("등락률% 범위", -30.0, 30.0, (-30.0, 30.0), 0.5, key="chg_range")

    mask = (
        sc["rsi14"].between(*rsi_range) &
        (sc["vol_ratio"] >= vol_min) &
        sc["chg_pct"].between(*chg_range)
    )
    result = sc[mask].sort_values("vol_ratio", ascending=False)

    st.markdown(f"**{len(result)}개** 종목 조건 충족")

    if len(result) > 0:
        disp2_cols = [c for c in ["name", "sector", "close", "chg_pct", "rsi14", "vol_ratio", "dist_52w_high", "dist_52w_low"] if c in result.columns]
        label2 = {"name": "종목명", "sector": "섹터", "close": "현재가",
                  "chg_pct": "등락률%", "rsi14": "RSI(14)", "vol_ratio": "거래량비율",
                  "dist_52w_high": "52주고가%", "dist_52w_low": "52주저가%"}
        disp2 = result[disp2_cols].rename(columns=label2).reset_index(drop=True)
        disp2.index += 1
        fmt2 = {}
        if "현재가"   in disp2.columns: fmt2["현재가"]   = "{:,.0f}"
        if "등락률%"  in disp2.columns: fmt2["등락률%"]  = "{:+.2f}%"
        if "RSI(14)"  in disp2.columns: fmt2["RSI(14)"]  = "{:.1f}"
        if "거래량비율" in disp2.columns: fmt2["거래량비율"] = "{:.2f}x"
        if "52주고가%" in disp2.columns: fmt2["52주고가%"] = "{:+.1f}%"
        if "52주저가%" in disp2.columns: fmt2["52주저가%"] = "{:+.1f}%"

        styled2 = disp2.style.format(fmt2)
        if "RSI(14)" in disp2.columns:
            styled2 = styled2.background_gradient(subset=["RSI(14)"], cmap="RdYlGn_r")
        if "거래량비율" in disp2.columns:
            styled2 = styled2.background_gradient(subset=["거래량비율"], cmap="Oranges")
        st.dataframe(styled2, use_container_width=True, height=500)

        # RSI 분포 히스토그램
        fig2 = go.Figure(go.Histogram(
            x=result["rsi14"], nbinsx=20,
            marker_color="#4f8ef7", opacity=0.8,
        ))
        fig2.update_layout(
            height=180, margin=dict(l=10, r=10, t=10, b=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", xaxis_title="RSI(14)", yaxis_title="종목 수",
            bargap=0.1,
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("조건에 맞는 종목이 없습니다. 필터를 조정해보세요.")
