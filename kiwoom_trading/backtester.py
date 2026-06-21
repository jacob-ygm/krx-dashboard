"""
백테스트 — 수집된 차트 데이터 + 학습된 모델로 전략 성과 측정

흐름:
  chart_data (dict) + model → run_backtest() → {equity_curve, trades, stats}

전략 규칙:
  - 모델 예측 확률 > threshold 인 날 시가 매수
  - 5거래일 후 종가 매도 (hold_days)
  - 동시에 여러 종목 보유 가능 (동일 비중)
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from .feature_builder import build_features, FEATURE_COLS
from .predictor import predict_ml, rule_score, combined_score


def run_backtest(
    chart_data: dict[str, list[dict]],
    model: dict,
    ml_weight: float = 0.6,
    rule_weight: float = 0.4,
    threshold: float = 0.55,
    hold_days: int = 5,
) -> dict:
    """
    Parameters
    ----------
    chart_data : {code: rows}  — fetch_chart_data() 반환값
    model      : train() 반환값
    threshold  : final_score 이상이면 매수 신호
    hold_days  : 매수 후 보유 일수

    Returns
    -------
    {
      "equity_curve": DataFrame(date, strategy, benchmark),
      "trades":       DataFrame(code, entry_date, exit_date, entry_px, exit_px, ret),
      "stats":        dict(total_ret, ann_ret, sharpe, max_dd, win_rate, n_trades),
    }
    """
    # ── 1. 전종목 피처 계산 ───────────────────────────────────
    feat_frames = {}
    for code, rows in chart_data.items():
        f = build_features(code, rows)
        if f is None or len(f) < hold_days + 5:
            continue
        feat_frames[code] = f

    if not feat_frames:
        return {}

    # ── 2. 날짜 범위 수집 ─────────────────────────────────────
    all_dates = sorted(
        set(d for f in feat_frames.values() for d in f["date"].tolist())
    )

    # ── 3. 날짜별 시뮬레이션 ──────────────────────────────────
    trades: list[dict] = []

    for code, f in feat_frames.items():
        f = f.reset_index(drop=True)
        close = f["close"].values
        dates = f["date"].values

        # 피처로 ML 예측
        feat_subset = f.dropna(subset=FEATURE_COLS)
        if len(feat_subset) == 0:
            continue

        pred_df = predict_ml(feat_subset, model)
        pred_df = rule_score(pred_df)
        pred_df = combined_score(pred_df, ml_weight, rule_weight)

        score_map = dict(zip(feat_subset.index, pred_df["final_score"].values))

        for idx in feat_subset.index:
            if idx + hold_days >= len(close):
                continue   # 매도일 데이터 없음
            score = score_map.get(idx, 0)
            if score < threshold:
                continue

            entry_px = close[idx]
            exit_px  = close[idx + hold_days]
            if entry_px == 0:
                continue

            ret = (exit_px / entry_px) - 1
            trades.append({
                "code":       code,
                "entry_date": dates[idx],
                "exit_date":  dates[idx + hold_days],
                "entry_px":   entry_px,
                "exit_px":    exit_px,
                "ret":        ret,
            })

    if not trades:
        return {}

    trades_df = pd.DataFrame(trades)
    trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"])
    trades_df["exit_date"]  = pd.to_datetime(trades_df["exit_date"])

    # ── 4. 일별 수익률 집계 (동일 비중) ──────────────────────
    date_range = pd.date_range(
        trades_df["entry_date"].min(),
        trades_df["exit_date"].max(),
        freq="B",
    )
    daily_rets = pd.Series(0.0, index=date_range)

    for _, tr in trades_df.iterrows():
        # 보유 기간 동안 daily contribution
        hold_dates = pd.date_range(tr["entry_date"], tr["exit_date"], freq="B")
        if len(hold_dates) == 0:
            continue
        daily_r = (1 + tr["ret"]) ** (1 / len(hold_dates)) - 1
        for d in hold_dates:
            if d in daily_rets.index:
                daily_rets[d] += daily_r

    # 동시 보유 종목 수로 나눠 포트폴리오 수익률 근사
    concurrent = pd.Series(0, index=date_range)
    for _, tr in trades_df.iterrows():
        hold_dates = pd.date_range(tr["entry_date"], tr["exit_date"], freq="B")
        for d in hold_dates:
            if d in concurrent.index:
                concurrent[d] += 1
    concurrent = concurrent.replace(0, 1)
    port_rets = daily_rets / concurrent

    # ── 5. 벤치마크: 전종목 단순 평균 수익률 ────────────────
    bm_rets = pd.Series(0.0, index=date_range)
    bm_count = pd.Series(0, index=date_range)
    for code, f in feat_frames.items():
        f2 = f.set_index("date")["close"].resample("B").last().ffill()
        dr = f2.pct_change()
        for d in date_range:
            if d in dr.index and not np.isnan(dr[d]):
                bm_rets[d] += dr[d]
                bm_count[d] += 1
    bm_count = bm_count.replace(0, 1)
    bm_rets = bm_rets / bm_count

    # ── 6. 누적 수익률 곡선 ───────────────────────────────────
    equity = pd.DataFrame({
        "date":      date_range,
        "strategy":  (1 + port_rets).cumprod() - 1,
        "benchmark": (1 + bm_rets).cumprod() - 1,
    })

    # ── 7. 통계 ───────────────────────────────────────────────
    total_ret  = float(equity["strategy"].iloc[-1])
    n_days     = len(port_rets)
    ann_factor = 252 / n_days if n_days > 0 else 1
    ann_ret    = (1 + total_ret) ** ann_factor - 1
    sharpe     = (port_rets.mean() / port_rets.std() * np.sqrt(252)
                  if port_rets.std() > 0 else 0)
    cum        = (1 + port_rets).cumprod()
    max_dd     = float(((cum / cum.cummax()) - 1).min())
    win_rate   = float((trades_df["ret"] > 0).mean()) if len(trades_df) > 0 else 0

    stats = {
        "total_ret":  total_ret,
        "ann_ret":    ann_ret,
        "sharpe":     sharpe,
        "max_dd":     max_dd,
        "win_rate":   win_rate,
        "n_trades":   len(trades_df),
    }

    return {
        "equity_curve": equity,
        "trades":       trades_df,
        "stats":        stats,
    }
