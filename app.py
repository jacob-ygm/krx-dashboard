"""
KOSPI 대시보드 — 키움 REST API 전용
탭 1: 전종목 현재가 목록  탭 2: 계좌 현황  탭 3: 기술지표 스크리너  탭 4: 예측 순위
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="KOSPI 대시보드", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  html,body,[class*="css"]{font-size:14px!important;}
  .block-container{padding:1rem 1.2rem 3rem!important;}
  .card{background:#1a1f2e;border-radius:10px;padding:14px 16px;
        margin-bottom:10px;border-left:4px solid #4f8ef7;}
  .card-up  {border-left-color:#22c55e!important;}
  .card-down{border-left-color:#ef4444!important;}
  .card h4{margin:0;font-size:11px;color:#8892a4;}
  .card .val{font-size:22px;font-weight:800;color:#fff;}
  .card .sub{font-size:11px;color:#8892a4;margin-top:3px;}
</style>""", unsafe_allow_html=True)


# ── RSI 계산 ─────────────────────────────────────────────────
def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.rolling(period).mean().iloc[-1]
    avg_l = loss.rolling(period).mean().iloc[-1]
    if pd.isna(avg_l) or avg_l == 0:
        return 100.0
    return round(100 - 100 / (1 + avg_g / avg_l), 2)


# ── 데이터 로드 ───────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_stock_list(refresh_key: int) -> pd.DataFrame:
    """ka10099: 코스피 전종목 리스트 + 현재가."""
    from kiwoom_trading import kiwoom_client
    resp = kiwoom_client.post("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "0"})
    rows = resp.get("list", [])
    df = pd.DataFrame(rows)
    df["lastPrice"] = pd.to_numeric(df["lastPrice"], errors="coerce").fillna(0)
    df["listCount"]  = pd.to_numeric(df["listCount"],  errors="coerce").fillna(0)
    df["market_cap"] = df["lastPrice"] * df["listCount"]
    return df


@st.cache_data(show_spinner=False)
def load_sector_chart(sector: str, refresh_key: int) -> pd.DataFrame:
    """
    선택 섹터 종목들의 일봉 25일치를 가져와 RSI·거래량비율 계산.
    returns DataFrame with columns: code, name, rsi14, vol_ratio, last_close, last_vol
    """
    from kiwoom_trading import kiwoom_client

    stock_list = load_stock_list(refresh_key)
    codes = stock_list[stock_list["upName"] == sector]["code"].tolist()

    records = []
    prog = st.progress(0, text=f"{sector} 차트 조회 중...")
    for i, code in enumerate(codes):
        try:
            body = {"stk_cd": code, "base_dt": "00000000", "upd_stkpc_tp": "1"}
            resp = kiwoom_client.post("ka10081", "/api/dostk/chart", body)
            rows = resp.get("stk_dt_pole_chart_qry", [])
            if not rows or len(rows) < 15:
                continue
            hist = pd.DataFrame(rows)
            closes  = pd.to_numeric(hist["cur_prc"],  errors="coerce").dropna()
            volumes = pd.to_numeric(hist["trde_qty"], errors="coerce").dropna()
            if len(closes) < 15:
                continue
            rsi       = _rsi(closes)
            avg_vol   = volumes.mean()
            last_vol  = volumes.iloc[0]
            vol_ratio = round(last_vol / avg_vol, 2) if avg_vol > 0 else 0
            records.append({
                "code":       code,
                "rsi14":      rsi,
                "vol_ratio":  vol_ratio,
                "last_close": float(closes.iloc[0]),
                "last_vol":   int(last_vol),
            })
        except Exception:
            continue
        prog.progress((i + 1) / len(codes),
                      text=f"{sector} 차트 조회 중... ({i+1}/{len(codes)})")

    prog.empty()
    if not records:
        return pd.DataFrame()

    result = pd.DataFrame(records)
    name_map = stock_list.set_index("code")["name"].to_dict()
    result["name"] = result["code"].map(name_map)
    return result


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

# ── 종목 목록 로드 ────────────────────────────────────────────
with st.spinner("종목 데이터 로딩 중..."):
    df = load_stock_list(st.session_state.refresh_key)

if df is None or len(df) == 0:
    st.error("종목 데이터를 불러오지 못했습니다.")
    st.stop()

dep, pos = load_account(st.session_state.refresh_key)

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
st.caption(f"기준: {now_str} | 코스피 {len(df):,}개 종목")

T = st.tabs(["🏆 전종목 현재가", "💰 계좌 현황", "🔍 기술지표 스크리너", "🎯 예측 순위"])
t1, t2, t3, t4 = T


# ── TAB1: 전종목 현재가 ───────────────────────────────────────
with t1:
    st.markdown("#### 🏆 코스피 전종목 현재가")

    ca, cb, cc, cd = st.columns(4)
    with ca:
        sectors = ["전체"] + sorted(df["upName"].dropna().unique().tolist())
        sel_sec = st.selectbox("섹터", sectors, key="sec1")
    with cb:
        sizes = ["전체"] + sorted(df["upSizeName"].dropna().unique().tolist())
        sel_size = st.selectbox("규모", sizes, key="size1")
    with cc:
        sort_by = st.selectbox("정렬", ["시가총액↓", "현재가↓", "현재가↑", "종목명"], key="sort1")
    with cd:
        top_n = st.slider("표시 수", 20, 500, 100, key="topn1")

    show = df.copy()
    if sel_sec  != "전체": show = show[show["upName"]     == sel_sec]
    if sel_size != "전체": show = show[show["upSizeName"] == sel_size]

    sort_map = {
        "시가총액↓": ("market_cap", False),
        "현재가↓":  ("lastPrice",  False),
        "현재가↑":  ("lastPrice",  True),
        "종목명":   ("name",       True),
    }
    s_col, s_asc = sort_map[sort_by]
    show = show.sort_values(s_col, ascending=s_asc).head(top_n)

    # 요약 카드
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card"><h4>조회 종목</h4><div class="val">{len(show):,}</div><div class="sub">전체 {len(df):,}개</div></div>', unsafe_allow_html=True)
    with c2:
        top_cap = show.nlargest(1, "market_cap").iloc[0] if len(show) > 0 else None
        cap_str = f"{top_cap['name']}" if top_cap is not None else "-"
        cap_val = f"{top_cap['market_cap']/1e12:.1f}조" if top_cap is not None else "-"
        st.markdown(f'<div class="card"><h4>시총 1위</h4><div class="val" style="font-size:16px">{cap_str}</div><div class="sub">{cap_val}</div></div>', unsafe_allow_html=True)
    with c3:
        avg_price = show["lastPrice"].mean()
        st.markdown(f'<div class="card"><h4>평균 현재가</h4><div class="val">{avg_price:,.0f}원</div></div>', unsafe_allow_html=True)
    with c4:
        sector_cnt = show["upName"].nunique()
        st.markdown(f'<div class="card"><h4>섹터 수</h4><div class="val">{sector_cnt}</div></div>', unsafe_allow_html=True)

    # 섹터별 종목 수 bar chart
    sec_counts = df["upName"].value_counts().head(15)
    fig = go.Figure(go.Bar(
        x=sec_counts.values, y=sec_counts.index,
        orientation="h", marker_color="#4f8ef7", opacity=0.8,
    ))
    fig.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#ccc", yaxis=dict(autorange="reversed"),
        xaxis_title="종목 수",
    )
    st.plotly_chart(fig, use_container_width=True)

    # 테이블
    disp = show[["code", "name", "upName", "upSizeName", "lastPrice", "market_cap", "state"]].copy()
    disp.columns = ["코드", "종목명", "섹터", "규모", "현재가", "시가총액", "상태"]
    disp["시가총액"] = disp["시가총액"].apply(lambda x: f"{x/1e8:,.0f}억")
    disp["현재가"]   = disp["현재가"].apply(lambda x: f"{x:,.0f}")
    disp = disp.reset_index(drop=True)
    disp.index += 1
    st.dataframe(disp, use_container_width=True, height=500)


# ── TAB2: 계좌 현황 ──────────────────────────────────────────
with t2:
    st.markdown("#### 💰 계좌 현황")

    if "error" in dep:
        st.error(f"계좌 조회 실패: {dep['error']}")
    else:
        def _int(val: str) -> int:
            try: return int(val.lstrip("0") or "0")
            except: return 0

        entr     = _int(dep.get("entr",           "0"))
        ord_alow = _int(dep.get("ord_alow_amt",   "0"))
        d2_pymn  = _int(dep.get("d2_pymn_alow_amt","0"))

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
        st.dataframe(pd.DataFrame(pos), use_container_width=True)


# ── TAB3: 기술지표 스크리너 ──────────────────────────────────
with t3:
    st.markdown("#### 🔍 기술지표 스크리너")
    st.caption("섹터 선택 후 해당 종목들의 RSI·거래량비율을 계산합니다")

    sectors_list = sorted(df["upName"].dropna().unique().tolist())
    sel_sector = st.selectbox("섹터 선택", sectors_list, key="sec3")
    sector_cnt = len(df[df["upName"] == sel_sector])
    st.caption(f"선택 섹터 종목 수: {sector_cnt}개 — 조회에 약 {sector_cnt//3 + 5}초 소요")

    if st.button("📊 분석 실행", key="run_screener"):
        sc_df = load_sector_chart(sel_sector, st.session_state.refresh_key)

        if sc_df is None or len(sc_df) == 0:
            st.warning("데이터를 가져오지 못했습니다.")
        else:
            ca, cb, cc = st.columns(3)
            with ca:
                rsi_range = st.slider("RSI(14) 범위", 0, 100, (0, 40), key="rsi_s")
            with cb:
                vol_min = st.number_input("거래량비율 최소 (x)", 0.0, 20.0, 1.0, 0.1, key="vol_s")
            with cc:
                price_min = st.number_input("현재가 최소 (원)", 0, 1000000, 0, 1000, key="price_s")

            mask = (
                sc_df["rsi14"].between(*rsi_range) &
                (sc_df["vol_ratio"] >= vol_min) &
                (sc_df["last_close"] >= price_min)
            )
            result = sc_df[mask].sort_values("vol_ratio", ascending=False)
            st.markdown(f"**{len(result)}개** 종목 조건 충족 / 전체 {len(sc_df)}개 분석")

            if len(result) > 0:
                disp3 = result[["name", "code", "last_close", "rsi14", "vol_ratio", "last_vol"]].copy()
                disp3.columns = ["종목명", "코드", "현재가", "RSI(14)", "거래량비율", "거래량"]
                disp3 = disp3.reset_index(drop=True)
                disp3.index += 1
                styled3 = disp3.style.format({
                    "현재가": "{:,.0f}", "RSI(14)": "{:.1f}",
                    "거래량비율": "{:.2f}x", "거래량": "{:,.0f}",
                }).background_gradient(subset=["RSI(14)"], cmap="RdYlGn_r")\
                  .background_gradient(subset=["거래량비율"], cmap="Oranges")
                st.dataframe(styled3, use_container_width=True, height=450)

                # RSI 분포
                fig2 = go.Figure(go.Histogram(
                    x=sc_df["rsi14"], nbinsx=20,
                    marker_color="#4f8ef7", opacity=0.8,
                ))
                fig2.add_vline(x=rsi_range[0], line_dash="dash", line_color="#22c55e")
                fig2.add_vline(x=rsi_range[1], line_dash="dash", line_color="#ef4444")
                fig2.update_layout(
                    height=180, margin=dict(l=10, r=10, t=10, b=20),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#ccc", xaxis_title="RSI(14)", yaxis_title="종목 수",
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("조건에 맞는 종목이 없습니다. 필터를 조정해보세요.")


# ── TAB4: 예측 순위 ───────────────────────────────────────────
with t4:
    st.markdown("#### 🎯 예측 순위")
    st.caption("XGBoost + LightGBM 앙상블 × 기술지표 룰 결합 → 5일 수익률 예측")

    from kiwoom_trading import predictor

    # ── 설정 ───────────────────────────────────────────────
    ca, cb = st.columns(2)
    with ca:
        top_n_pred = st.slider("학습·예측 종목 수 (시총 상위)", 50, 300, 150, 50,
                               key="top_n_pred")
    with cb:
        ml_w = st.slider("ML 가중치", 0.0, 1.0, 0.6, 0.1, key="ml_w")
        rule_w = round(1.0 - ml_w, 1)
        st.caption(f"룰 가중치: {rule_w}")

    col_run, col_load = st.columns(2)
    run_train  = col_run.button("🚀 데이터 수집 & 모델 학습", key="run_train",
                                use_container_width=True)
    load_model = col_load.button("📂 저장된 모델로 예측", key="load_model",
                                 use_container_width=True)

    # ── 대상 종목 선정 (시총 상위 N) ─────────────────────────
    target_codes = (
        df.sort_values("market_cap", ascending=False)
          .head(top_n_pred)["code"].tolist()
    )

    if run_train:
        st.info(f"시총 상위 {top_n_pred}개 종목 120일치 차트 수집 중... (수 분 소요)")
        prog_bar = st.progress(0)
        status   = st.empty()

        def _cb(i, total, code):
            prog_bar.progress((i + 1) / total)
            status.caption(f"수집 중: {code} ({i+1}/{total})")

        chart_data = predictor.fetch_chart_data(target_codes, progress_cb=_cb)
        st.session_state["chart_data_cache"] = chart_data
        prog_bar.empty(); status.empty()
        st.success(f"차트 수집 완료: {len(chart_data)}개 종목")

        with st.spinner("피처 생성 중..."):
            train_df, latest_df = predictor.build_dataset(chart_data)

        if len(train_df) < 100:
            st.error("학습 데이터 부족. 종목 수를 늘리거나 나중에 다시 시도하세요.")
        else:
            st.info(f"학습 데이터: {len(train_df):,}행 | 예측 대상: {len(latest_df)}종목")
            with st.spinner("XGBoost + LightGBM 학습 중..."):
                model = predictor.train(train_df)
            st.success("모델 학습 완료!")

            # 예측 & 스코어 계산
            pred_df = predictor.predict_ml(latest_df, model)
            pred_df = predictor.rule_score(pred_df)
            pred_df = predictor.combined_score(pred_df, ml_w, rule_w)
            st.session_state["pred_result"] = pred_df

    elif load_model:
        model = predictor.load_model()
        if model is None:
            st.warning("저장된 모델이 없습니다. 먼저 '데이터 수집 & 모델 학습'을 실행하세요.")
        else:
            st.info(f"시총 상위 {top_n_pred}개 종목 차트 수집 중...")
            prog_bar = st.progress(0)
            status   = st.empty()

            def _cb2(i, total, code):
                prog_bar.progress((i + 1) / total)
                status.caption(f"수집 중: {code} ({i+1}/{total})")

            chart_data = predictor.fetch_chart_data(target_codes, progress_cb=_cb2)
            prog_bar.empty(); status.empty()

            with st.spinner("피처 생성 & 예측 중..."):
                _, latest_df = predictor.build_dataset(chart_data)
                pred_df = predictor.predict_ml(latest_df, model)
                pred_df = predictor.rule_score(pred_df)
                pred_df = predictor.combined_score(pred_df, ml_w, rule_w)
            st.session_state["pred_result"] = pred_df
            st.success("예측 완료!")

    # ── 결과 표시 ─────────────────────────────────────────
    if "pred_result" in st.session_state:
        pred_df = st.session_state["pred_result"]
        name_map = df.set_index("code")["name"].to_dict()
        sec_map  = df.set_index("code")["upName"].to_dict()
        price_map= df.set_index("code")["lastPrice"].to_dict()

        result = pred_df.copy()
        result["name"]   = result["code"].map(name_map)
        result["sector"] = result["code"].map(sec_map)
        result["price"]  = result["code"].map(price_map)

        top_buy = result.head(20)

        # 요약 카드
        c1, c2, c3, c4 = st.columns(4)
        strong = (result["final_score"] >= 0.65).sum()
        mid    = ((result["final_score"] >= 0.50) & (result["final_score"] < 0.65)).sum()
        with c1:
            st.markdown(f'<div class="card card-up"><h4>강력매수 후보</h4><div class="val">{strong}</div><div class="sub">스코어 ≥ 0.65</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="card"><h4>매수관심</h4><div class="val">{mid}</div><div class="sub">스코어 0.50~0.65</div></div>', unsafe_allow_html=True)
        with c3:
            avg_ml = result["prob_ml"].mean() if "prob_ml" in result.columns else 0
            st.markdown(f'<div class="card"><h4>평균 ML 확률</h4><div class="val">{avg_ml:.1%}</div></div>', unsafe_allow_html=True)
        with c4:
            avg_rule = result["rule_score"].mean() if "rule_score" in result.columns else 0
            st.markdown(f'<div class="card"><h4>평균 룰 스코어</h4><div class="val">{avg_rule:.2f}</div></div>', unsafe_allow_html=True)

        # 스코어 산포도
        fig3 = go.Figure(go.Scatter(
            x=result["prob_ml"] if "prob_ml" in result.columns else result["rule_score"],
            y=result["rule_score"],
            mode="markers",
            marker=dict(color=result["final_score"], colorscale="RdYlGn",
                        size=7, opacity=0.7, colorbar=dict(title="최종스코어")),
            text=result["name"].fillna(result["code"]),
            hovertemplate="%{text}<br>ML: %{x:.2f} | 룰: %{y:.2f}<extra></extra>",
        ))
        fig3.update_layout(
            height=250, margin=dict(l=10, r=10, t=10, b=20),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#ccc", xaxis_title="ML 확률", yaxis_title="룰 스코어",
        )
        st.plotly_chart(fig3, use_container_width=True)

        # 상위 20종목 테이블
        st.markdown("##### 📋 상위 20 종목")
        show_cols = ["name", "sector", "price", "final_score", "prob_ml",
                     "rule_score", "rsi14", "vol_ratio", "macd_cross"]
        show_cols = [c for c in show_cols if c in top_buy.columns]
        disp4 = top_buy[show_cols].copy()
        disp4.columns = [{"name":"종목명","sector":"섹터","price":"현재가",
                          "final_score":"최종스코어","prob_ml":"ML확률",
                          "rule_score":"룰스코어","rsi14":"RSI(14)",
                          "vol_ratio":"거래량비율","macd_cross":"MACD크로스"
                         }.get(c, c) for c in show_cols]
        disp4 = disp4.reset_index(drop=True); disp4.index += 1
        fmt4 = {}
        if "현재가"   in disp4.columns: fmt4["현재가"]   = "{:,.0f}"
        if "최종스코어" in disp4.columns: fmt4["최종스코어"] = "{:.3f}"
        if "ML확률"   in disp4.columns: fmt4["ML확률"]   = "{:.1%}"
        if "룰스코어"  in disp4.columns: fmt4["룰스코어"]  = "{:.2f}"
        if "RSI(14)"  in disp4.columns: fmt4["RSI(14)"]  = "{:.1f}"
        if "거래량비율" in disp4.columns: fmt4["거래량비율"] = "{:.2f}x"

        styled4 = disp4.style.format(fmt4)
        if "최종스코어" in disp4.columns:
            styled4 = styled4.background_gradient(subset=["최종스코어"], cmap="RdYlGn")
        if "ML확률" in disp4.columns:
            styled4 = styled4.background_gradient(subset=["ML확률"], cmap="Blues")
        st.dataframe(styled4, use_container_width=True, height=500)

        # ── 모의 자동매수 (상위 3종목) ────────────────────────
        st.divider()
        st.markdown("#### 🛒 모의 자동매수 — 상위 3종목")
        st.caption("최종스코어 1·2·3위 종목에 시장가 1주씩 모의 매수합니다.")
        top3 = result.head(3)[["code", "name", "final_score"]].copy()
        st.dataframe(top3.reset_index(drop=True), use_container_width=True, height=160)
        if st.button("🚀 상위 3종목 모의매수 실행", type="primary"):
            from kiwoom_trading import order_engine
            price_map2 = df.set_index("code")["lastPrice"].to_dict()
            order_results = order_engine.place_top_orders(top3, price_map2, qty_per_stock=1)
            for r in order_results:
                if "실패" in r["status"]:
                    st.error(f"{r['code']} — {r['status']}")
                else:
                    st.success(f"{r['code']} 매수 완료 | 주문번호: {r['ord_no']}")

        # ── 백테스트 ──────────────────────────────────────────
        st.divider()
        st.markdown("#### 📊 백테스트")
        st.caption("수집된 차트 데이터와 학습된 모델로 전략 성과를 시뮬레이션합니다.")

        bt_threshold = st.slider("매수 신호 임계값 (final_score ≥)", 0.40, 0.80, 0.55, 0.05)
        bt_hold      = st.slider("보유 일수", 3, 20, 5)

        if st.button("▶ 백테스트 실행"):
            if "chart_data_cache" not in st.session_state:
                st.warning("먼저 '데이터 수집 & 모델 학습'을 실행하세요.")
            else:
                from kiwoom_trading import backtester
                loaded_model = predictor.load_model()
                if loaded_model is None:
                    st.warning("저장된 모델이 없습니다. 먼저 학습을 실행하세요.")
                else:
                    with st.spinner("백테스트 실행 중..."):
                        bt = backtester.run_backtest(
                            st.session_state["chart_data_cache"],
                            loaded_model,
                            threshold=bt_threshold,
                            hold_days=bt_hold,
                        )
                    if not bt:
                        st.warning("백테스트 결과 없음 — 신호 임계값을 낮춰보세요.")
                    else:
                        stats = bt["stats"]
                        s1, s2, s3, s4, s5 = st.columns(5)
                        s1.metric("누적수익률", f"{stats['total_ret']:.1%}")
                        s2.metric("연환산수익률", f"{stats['ann_ret']:.1%}")
                        s3.metric("샤프비율", f"{stats['sharpe']:.2f}")
                        s4.metric("최대낙폭(MDD)", f"{stats['max_dd']:.1%}")
                        s5.metric("승률 / 거래수", f"{stats['win_rate']:.1%} / {stats['n_trades']}")

                        eq = bt["equity_curve"]
                        fig_bt = go.Figure()
                        fig_bt.add_trace(go.Scatter(
                            x=eq["date"], y=eq["strategy"] * 100,
                            name="전략", line=dict(color="#4f8ef7", width=2)))
                        fig_bt.add_trace(go.Scatter(
                            x=eq["date"], y=eq["benchmark"] * 100,
                            name="벤치마크(전종목평균)", line=dict(color="#aaa", width=1, dash="dot")))
                        fig_bt.update_layout(
                            height=320, margin=dict(l=10, r=10, t=20, b=20),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#ccc", yaxis_title="누적수익률(%)",
                            legend=dict(orientation="h", y=1.1),
                        )
                        st.plotly_chart(fig_bt, use_container_width=True)

                        with st.expander("거래 내역 보기"):
                            td = bt["trades"].copy()
                            td["수익률"] = td["ret"].map("{:.2%}".format)
                            td["entry_date"] = td["entry_date"].dt.strftime("%Y-%m-%d")
                            td["exit_date"]  = td["exit_date"].dt.strftime("%Y-%m-%d")
                            st.dataframe(td[["code","entry_date","exit_date",
                                            "entry_px","exit_px","수익률"]]
                                         .rename(columns={"code":"종목","entry_date":"매수일",
                                                          "exit_date":"매도일","entry_px":"매수가",
                                                          "exit_px":"매도가"}),
                                         use_container_width=True, height=300)

        st.caption("⚠️ 본 예측은 투자 참고용이며, 실제 투자 결과를 보장하지 않습니다.")
