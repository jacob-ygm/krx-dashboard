"""
키움 ka10081 일봉 데이터 → ML 피처 + 5일 수익률 레이블 생성
"""
from __future__ import annotations
import pandas as pd
import numpy as np


# ── 기술지표 계산 ─────────────────────────────────────────────
def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_l = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema12  = close.ewm(span=12, min_periods=12).mean()
    ema26  = close.ewm(span=26, min_periods=26).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, min_periods=9).mean()
    return macd, signal


def _bollinger(close: pd.Series, period: int = 20) -> pd.Series:
    mid  = close.rolling(period).mean()
    std  = close.rolling(period).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    denom = (upper - lower).replace(0, np.nan)
    return (close - lower) / denom   # 0~1, 0.5 = 중간


def _parse_chart(rows: list[dict]) -> pd.DataFrame | None:
    """ka10081 응답 rows → 정규화된 OHLCV DataFrame (날짜 오름차순)."""
    if not rows:
        return None
    df = pd.DataFrame(rows)
    rename = {
        "dt":       "date",
        "open_pric":"open",
        "high_pric":"high",
        "low_pric": "low",
        "cur_prc":  "close",
        "trde_qty": "volume",
    }
    df = df.rename(columns=rename)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def build_features(code: str, rows: list[dict]) -> pd.DataFrame | None:
    """
    단일 종목의 차트 rows → 일별 피처 DataFrame.
    각 행 = 해당 날짜의 피처 + 5일 후 수익률(label, 훈련용).

    Returns None if insufficient data.
    """
    df = _parse_chart(rows)
    if df is None or len(df) < 40:
        return None

    close  = df["close"]
    volume = df["volume"]

    f = pd.DataFrame(index=df.index)
    f["date"]   = df["date"]
    f["code"]   = code
    f["close"]  = close

    # ── 모멘텀 ───────────────────────────────────────────────
    f["ret_1d"]  = close.pct_change(1)
    f["ret_5d"]  = close.pct_change(5)
    f["ret_20d"] = close.pct_change(20)

    # ── RSI ──────────────────────────────────────────────────
    f["rsi14"] = _rsi(close, 14)

    # ── MACD ─────────────────────────────────────────────────
    macd, signal = _macd(close)
    f["macd"]       = macd
    f["macd_signal"]= signal
    f["macd_hist"]  = macd - signal
    f["macd_cross"] = ((macd > signal) & (macd.shift(1) <= signal.shift(1))).astype(int)

    # ── 볼린저 ───────────────────────────────────────────────
    f["bb_pct"] = _bollinger(close, 20)

    # ── 거래량 ───────────────────────────────────────────────
    vol_ma20       = volume.rolling(20).mean()
    f["vol_ratio"] = volume / vol_ma20.replace(0, np.nan)

    # ── 변동성 ───────────────────────────────────────────────
    f["volatility"] = close.pct_change().rolling(20).std()

    # ── 52주 고저 거리 ────────────────────────────────────────
    high_52w       = close.rolling(min(252, len(close))).max()
    low_52w        = close.rolling(min(252, len(close))).min()
    f["dist_52w_high"] = (close / high_52w.replace(0, np.nan)) - 1
    f["dist_52w_low"]  = (close / low_52w.replace(0, np.nan)) - 1

    # ── 레이블: 5일 후 수익률 ─────────────────────────────────
    f["ret_5d_fwd"] = close.pct_change(5).shift(-5)
    # 중앙값 기준으로 상/하 분류 → 항상 균형잡힌 레이블
    median_ret = f["ret_5d_fwd"].median()
    f["label"] = (f["ret_5d_fwd"] > median_ret).astype(int)

    f = f.dropna(subset=["rsi14", "bb_pct", "vol_ratio", "ret_20d"])
    return f.reset_index(drop=True)


FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_20d",
    "rsi14", "macd_hist", "macd_cross",
    "bb_pct", "vol_ratio", "volatility",
    "dist_52w_high", "dist_52w_low",
]
