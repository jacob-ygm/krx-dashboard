# sector_engine.py — 섹터 동적 상대강도 + 고도화 모멘텀 팩터
import numpy as np
import pandas as pd
from sector_map import SECTOR_MAP, get_sector

def calc_stock_factors(ohlcv, as_of=None):
    """Tier1 팩터: 20/60일 수익률, 변동성조정 모멘텀, 52주 신고가 근접도"""
    if ohlcv.empty or len(ohlcv) < 21:
        return {}
    df = ohlcv if as_of is None else ohlcv[ohlcv.index <= pd.Timestamp(as_of)]
    if len(df) < 21:
        return {}
    close = df["close"]
    cur = float(close.iloc[-1])
    f = {}
    f["ret_20d"] = (cur / float(close.iloc[-21]) - 1) * 100
    f["ret_60d"] = (cur / float(close.iloc[-61]) - 1) * 100 if len(close) >= 61 else f["ret_20d"]
    daily = close.pct_change().iloc[-60:]
    vol = float(daily.std()) * np.sqrt(252) * 100
    f["volatility"] = vol
    f["risk_adj_mom"] = f["ret_20d"] / (vol / np.sqrt(252/20)) if vol > 0 else 0
    high_52w = float(df["high"].iloc[-252:].max()) if len(df) >= 60 else float(df["high"].max())
    f["pct_from_high"] = (cur / high_52w - 1) * 100
    f["near_high"] = f["pct_from_high"] > -10
    return f

def calc_sector_strength(historical, as_of=None):
    """섹터별 20/60일 상대강도 — 매일 동적 계산"""
    rows = []
    for ticker, data in historical.items():
        sector = get_sector(ticker)
        if sector in ("ETF", "기타"):
            continue
        fac = calc_stock_factors(data.get("ohlcv", pd.DataFrame()), as_of)
        if not fac:
            continue
        rows.append({"ticker": ticker, "sector": sector,
                     "ret_20d": fac["ret_20d"], "ret_60d": fac["ret_60d"]})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    sec = df.groupby("sector").agg(
        n=("ticker", "count"),
        ret_20d=("ret_20d", "median"),
        ret_60d=("ret_60d", "median"),
    ).reset_index()
    # 시장 전체 중앙값 대비 상대강도
    sec["rs_20d"] = sec["ret_20d"] - df["ret_20d"].median()
    sec["rs_60d"] = sec["ret_60d"] - df["ret_60d"].median()
    # 이중 확인: 20일·60일 모두 양수 = 확정 강세 / 모두 음수 = 확정 약세
    sec["trend"] = "반등시도"
    sec.loc[(sec["rs_20d"] > 0) & (sec["rs_60d"] > 0), "trend"] = "강세"
    sec.loc[(sec["rs_20d"] < 0) & (sec["rs_60d"] < 0), "trend"] = "약세"
    sec.loc[(sec["rs_20d"] < 0) & (sec["rs_60d"] > 0), "trend"] = "눌림목"
    return sec.sort_values("rs_20d", ascending=False).reset_index(drop=True)

def get_dynamic_sector_sets(historical, as_of=None):
    """SECTOR_STRONG/WEAK 하드코딩 대체 — 동적 강세/약세 종목 집합"""
    sec = calc_sector_strength(historical, as_of)
    if sec.empty:
        return set(), set()
    # 강세 + 눌림목(장기상승 중 단기조정 = R6+F5 최적 구간) 모두 매수 우호
    strong_sectors = set(sec[sec["trend"].isin(["강세","눌림목"])]["sector"])
    weak_sectors   = set(sec[sec["trend"] == "약세"]["sector"])
    strong = {t for t, s in SECTOR_MAP.items() if s in strong_sectors}
    weak   = {t for t, s in SECTOR_MAP.items() if s in weak_sectors}
    return strong, weak

def cross_sectional_rank(factor_dict):
    """종목별 팩터 → 그날 횡단면 백분위 (0~100)"""
    if not factor_dict:
        return {}
    s = pd.Series(factor_dict)
    return (s.rank(pct=True) * 100).to_dict()
