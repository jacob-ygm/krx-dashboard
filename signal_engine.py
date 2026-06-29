# signal_engine.py
"""
신호 생성 엔진
- 기술적 지표 계산 (MA, RSI, MACD, 지지/저항)
- 5개 카테고리 점수화 (매크로/펀더멘털/수급/기술/모멘텀)
- BUY/SELL 신호 + 신뢰도 + 진입/목표/손절 가격
"""

import numpy as np
import pandas as pd
from config import WEIGHTS, SIGNAL_BANDS, CONFIDENCE_BANDS


# ════════════════════════════════════════════════════════════════════════════
# A. 기술적 지표 계산
# ════════════════════════════════════════════════════════════════════════════

def calc_indicators(df: pd.DataFrame) -> dict:
    """OHLCV DataFrame → 기술적 지표 딕셔너리"""
    if df.empty or len(df) < 20:
        return {}

    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    vol   = df["volume"]

    ind = {}

    # ── 이동평균 ──────────────────────────────────────────────────────────
    for n in [5, 20, 60, 120]:
        if len(close) >= n:
            ind[f"ma{n}"] = close.rolling(n).mean().iloc[-1]

    cur = close.iloc[-1]
    ind["current_price"] = cur

    # MA 정배열 여부
    mas = [ind.get(f"ma{n}") for n in [5, 20, 60, 120] if ind.get(f"ma{n}")]
    ind["ma_aligned_up"]   = all(mas[i] > mas[i+1] for i in range(len(mas)-1)) if len(mas) >= 2 else False
    ind["ma_aligned_down"] = all(mas[i] < mas[i+1] for i in range(len(mas)-1)) if len(mas) >= 2 else False

    # 가격 대비 MA 위치
    for n in [5, 20, 60, 120]:
        k = f"ma{n}"
        if ind.get(k):
            ind[f"pct_vs_ma{n}"] = (cur / ind[k] - 1) * 100

    # ── 골든/데드크로스 ──────────────────────────────────────────────────
    if len(close) >= 21:
        ma5  = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()
        cross_now  = ma5.iloc[-1]  > ma20.iloc[-1]
        cross_prev = ma5.iloc[-2]  < ma20.iloc[-2]
        death_now  = ma5.iloc[-1]  < ma20.iloc[-1]
        death_prev = ma5.iloc[-2]  > ma20.iloc[-2]
        ind["golden_cross"] = cross_now and cross_prev
        ind["dead_cross"]   = death_now and death_prev

    # ── RSI (14일) ────────────────────────────────────────────────────────
    if len(close) >= 15:
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        ind["rsi"] = round(rsi.iloc[-1], 1)
        ind["rsi_oversold"]   = ind["rsi"] < 30
        ind["rsi_overbought"] = ind["rsi"] > 70
        # RSI 회복 (전일 <35, 오늘 >35)
        if len(rsi) >= 2:
            ind["rsi_recovering"] = rsi.iloc[-2] < 35 and rsi.iloc[-1] >= 35

    # ── MACD (12, 26, 9) ─────────────────────────────────────────────────
    if len(close) >= 27:
        ema12  = close.ewm(span=12).mean()
        ema26  = close.ewm(span=26).mean()
        macd   = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        hist   = macd - signal
        ind["macd"]         = round(macd.iloc[-1], 2)
        ind["macd_signal"]  = round(signal.iloc[-1], 2)
        ind["macd_hist"]    = round(hist.iloc[-1], 2)
        ind["macd_cross_up"]   = macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]
        ind["macd_cross_down"] = macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]
        # 다이버전스 (간단 근사: 가격 신저 but MACD 신저 아닌 경우)
        if len(close) >= 40:
            price_low_recent = close.iloc[-10:].min()
            price_low_before = close.iloc[-30:-10].min()
            macd_low_recent  = macd.iloc[-10:].min()
            macd_low_before  = macd.iloc[-30:-10].min()
            ind["macd_bull_divergence"] = (
                price_low_recent < price_low_before and
                macd_low_recent  > macd_low_before
            )

    # ── 볼린저 밴드 (20, 2σ) ─────────────────────────────────────────────
    if len(close) >= 20:
        ma20  = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        ind["bb_upper"] = round((ma20 + 2 * std20).iloc[-1], 0)
        ind["bb_lower"] = round((ma20 - 2 * std20).iloc[-1], 0)
        ind["bb_pct"]   = round(
            (cur - (ma20 - 2*std20).iloc[-1]) /
            (4 * std20.iloc[-1] + 1e-9) * 100, 1
        )   # 0%=하단, 100%=상단

    # ── 지지/저항 (52주 고저, 최근 20일 고저) ───────────────────────────
    if len(close) >= 20:
        ind["resistance_20d"] = round(high.iloc[-20:].max(), 0)
        ind["support_20d"]    = round(low.iloc[-20:].min(), 0)
    if len(close) >= 120:
        ind["resistance_120d"] = round(high.iloc[-120:].max(), 0)
        ind["support_120d"]    = round(low.iloc[-120:].min(), 0)

    # ── 거래량 확인 ──────────────────────────────────────────────────────
    if len(vol) >= 20:
        avg_vol = vol.rolling(20).mean().iloc[-1]
        ind["vol_ratio"] = round(vol.iloc[-1] / avg_vol, 2) if avg_vol else 1.0
        ind["vol_surge"] = ind["vol_ratio"] > 1.5

    # ── 추세 강도 (ADX 근사) ─────────────────────────────────────────────
    if len(close) >= 15:
        returns = close.pct_change().iloc[-14:]
        trend_score = returns.mean() / (returns.std() + 1e-9)
        ind["trend_strength"] = round(float(trend_score), 3)

    return ind


# ════════════════════════════════════════════════════════════════════════════
# B. 매크로 점수 (0-25점)
# ════════════════════════════════════════════════════════════════════════════

def score_macro(macro_snap: dict) -> tuple[float, list[str]]:
    """매크로 환경 점수 산출"""
    score = 12.5   # 중립 시작
    reasons = []

    vix   = macro_snap.get("VIX", {}).get("value", 20)
    dxy   = macro_snap.get("DXY", {}).get("value", 104)
    krw   = macro_snap.get("USD/KRW", {}).get("value", 1350)
    sp500 = macro_snap.get("S&P500", {}).get("chg_pct", 0)
    wti   = macro_snap.get("WTI", {}).get("value", 75)

    # VIX
    if vix < 15:
        score += 3; reasons.append(f"VIX {vix:.1f} — 공포지수 낮음(리스크온)")
    elif vix < 20:
        score += 1.5
    elif vix > 30:
        score -= 4; reasons.append(f"VIX {vix:.1f} — 공포지수 높음(리스크오프)")
    elif vix > 25:
        score -= 2

    # S&P500 방향
    if sp500 > 0.5:
        score += 2; reasons.append(f"S&P500 +{sp500:.1f}% 상승")
    elif sp500 < -1.0:
        score -= 2.5; reasons.append(f"S&P500 {sp500:.1f}% 하락")

    # USD/KRW
    if krw < 1300:
        score += 2; reasons.append(f"USD/KRW {krw:.0f} — 원화 강세")
    elif krw > 1400:
        score -= 2.5; reasons.append(f"USD/KRW {krw:.0f} — 원화 약세 경고")
    elif krw > 1380:
        score -= 1.5

    # DXY
    if dxy < 100:
        score += 1.5
    elif dxy > 106:
        score -= 1.5; reasons.append(f"DXY {dxy:.1f} — 달러 강세 부담")

    # WTI (에너지 비용)
    if 60 < wti < 85:
        score += 1   # 적정
    elif wti > 100:
        score -= 2; reasons.append(f"WTI {wti:.1f} — 유가 고공 비용 부담")

    score = max(0, min(25, score))
    return round(score, 1), reasons


def get_macro_regime(macro_snap: dict) -> str:
    """RISK-ON / NEUTRAL / RISK-OFF 판별"""
    vix = macro_snap.get("VIX", {}).get("value", 20)
    dxy = macro_snap.get("DXY", {}).get("value", 104)
    krw = macro_snap.get("USD/KRW", {}).get("value", 1350)
    sp500_chg = macro_snap.get("S&P500", {}).get("chg_pct", 0)

    risk_off = (vix > 25) or (krw > 1400) or (sp500_chg < -1.5)
    risk_on  = (vix < 17) and (krw < 1330) and (sp500_chg > 0)

    if risk_off:
        return "RISK-OFF"
    elif risk_on:
        return "RISK-ON"
    return "NEUTRAL"


# ════════════════════════════════════════════════════════════════════════════
# C. 펀더멘털 점수 (0-20점)
# ════════════════════════════════════════════════════════════════════════════

def score_fundamental(fund: dict, naver: dict) -> tuple[float, list[str]]:
    score = 10.0
    reasons = []

    per  = fund.get("PER", 0)
    pbr  = fund.get("PBR", 0)
    roe  = naver.get("ROE", 0)
    op_m = naver.get("operating_margin", 0)
    debt = naver.get("debt_ratio", 100)
    cr   = naver.get("current_ratio", 1)

    # PER
    if 0 < per < 10:
        score += 2.5; reasons.append(f"PER {per:.1f} — 저평가")
    elif 10 <= per <= 20:
        score += 1
    elif per > 40:
        score -= 2; reasons.append(f"PER {per:.1f} — 고평가")

    # PBR
    if 0 < pbr < 1:
        score += 2; reasons.append(f"PBR {pbr:.2f} — 자산 대비 저평가")
    elif pbr > 4:
        score -= 1.5

    # ROE
    if roe > 20:
        score += 2.5; reasons.append(f"ROE {roe:.1f}% — 우수한 자기자본수익률")
    elif roe > 10:
        score += 1
    elif roe < 0:
        score -= 2; reasons.append(f"ROE {roe:.1f}% — 적자")

    # 영업이익률
    if op_m > 15:
        score += 2; reasons.append(f"영업이익률 {op_m:.1f}%")
    elif op_m < 0:
        score -= 2

    # 부채비율
    if debt < 50:
        score += 1
    elif debt > 200:
        score -= 2; reasons.append(f"부채비율 {debt:.0f}% — 재무 위험")

    # 유동비율
    if cr > 2:
        score += 1
    elif cr < 1:
        score -= 1.5

    score = max(0, min(20, score))
    return round(score, 1), reasons


# ════════════════════════════════════════════════════════════════════════════
# D. 수급 점수 (0-20점)
# ════════════════════════════════════════════════════════════════════════════

def score_supply_demand(investor_df: pd.DataFrame, foreign_ratio: float) -> tuple[float, list[str]]:
    score = 10.0
    reasons = []

    if investor_df.empty:
        return score, reasons

    recent = investor_df.tail(10)   # 최근 10거래일

    # 외국인 누적 순매수
    if "foreign" in recent.columns:
        f_sum = recent["foreign"].sum()
        f_consec = (recent["foreign"] > 0).sum()   # 순매수 일수
        if f_sum > 0:
            score += min(4, f_sum / 1e10)   # 규모 비례 (최대 +4)
            if f_consec >= 7:
                score += 2; reasons.append(f"외국인 {f_consec}일 연속 순매수")
            elif f_consec >= 4:
                score += 1; reasons.append(f"외국인 {f_consec}일 순매수")
        else:
            consec_sell = (recent["foreign"] < 0).sum()
            if consec_sell >= 7:
                score -= 3; reasons.append(f"외국인 {consec_sell}일 연속 순매도")
            elif consec_sell >= 4:
                score -= 1.5

    # 기관 순매수
    if "institutional" in recent.columns:
        i_sum = recent["institutional"].sum()
        if i_sum > 0:
            score += min(3, i_sum / 1e10)
            reasons.append("기관 순매수 우위")
        elif i_sum < -5e9:
            score -= 2

    # 외국인+기관 동반 매수
    if "foreign" in recent.columns and "institutional" in recent.columns:
        joint = ((recent["foreign"] > 0) & (recent["institutional"] > 0)).sum()
        if joint >= 6:
            score += 2; reasons.append(f"외국인+기관 {joint}일 동반 매수")

    # 외국인 보유비율
    if foreign_ratio > 40:
        score += 1; reasons.append(f"외국인 보유비율 {foreign_ratio:.1f}%")

    score = max(0, min(20, score))
    return round(score, 1), reasons


# ════════════════════════════════════════════════════════════════════════════
# E. 기술적 점수 (0-20점)
# ════════════════════════════════════════════════════════════════════════════

def score_technical(ind: dict) -> tuple[float, list[str]]:
    score = 10.0
    reasons = []

    if not ind:
        return score, reasons

    # MA 정배열
    if ind.get("ma_aligned_up"):
        score += 3; reasons.append("MA 정배열 (5>20>60>120일)")
    elif ind.get("ma_aligned_down"):
        score -= 3; reasons.append("MA 역배열")

    # 골든/데드크로스
    if ind.get("golden_cross"):
        score += 2; reasons.append("골든크로스 발생")
    if ind.get("dead_cross"):
        score -= 2.5; reasons.append("데드크로스 발생")

    # RSI
    rsi = ind.get("rsi", 50)
    if ind.get("rsi_recovering"):
        score += 2; reasons.append(f"RSI 과매도 회복 ({rsi:.0f})")
    elif ind.get("rsi_oversold"):
        score += 1; reasons.append(f"RSI 과매도 ({rsi:.0f}) — 반등 가능")
    elif ind.get("rsi_overbought"):
        score -= 2; reasons.append(f"RSI 과매수 ({rsi:.0f}) — 단기 부담")

    # MACD
    if ind.get("macd_cross_up"):
        score += 2; reasons.append("MACD 골든크로스")
    if ind.get("macd_cross_down"):
        score -= 2; reasons.append("MACD 데드크로스")
    if ind.get("macd_bull_divergence"):
        score += 1.5; reasons.append("MACD 강세 다이버전스")

    # 볼린저밴드 위치
    bb_pct = ind.get("bb_pct", 50)
    if bb_pct < 20:
        score += 1.5; reasons.append(f"볼린저밴드 하단 근접 ({bb_pct:.0f}%)")
    elif bb_pct > 85:
        score -= 1.5; reasons.append(f"볼린저밴드 상단 돌파 ({bb_pct:.0f}%) — 과열")

    # 거래량 서지
    if ind.get("vol_surge"):
        vr = ind.get("vol_ratio", 1)
        reasons.append(f"거래량 급증 ({vr:.1f}배)")
        # 방향성과 결합
        if ind.get("ma_aligned_up") or ind.get("macd_cross_up"):
            score += 1
        else:
            score -= 0.5

    # MA 대비 위치
    pct_ma20 = ind.get("pct_vs_ma20", 0)
    if -5 < pct_ma20 < 0:
        score += 1   # MA20 근방 약간 아래 — 지지 확인 가능 구간
    elif pct_ma20 < -15:
        score -= 1   # 심하게 이탈

    score = max(0, min(20, score))
    return round(score, 1), reasons


# ════════════════════════════════════════════════════════════════════════════
# F. 모멘텀/촉매 점수 (0-15점)
# ════════════════════════════════════════════════════════════════════════════

def score_momentum(ind: dict, macro_snap: dict) -> tuple[float, list[str]]:
    score = 7.5
    reasons = []

    if not ind:
        return score, reasons

    # 추세 강도 (t-stat 근사)
    ts = ind.get("trend_strength", 0)
    if ts > 0.3:
        score += 2; reasons.append(f"강한 상승 모멘텀 (추세강도 {ts:.2f})")
    elif ts > 0.1:
        score += 1
    elif ts < -0.3:
        score -= 2; reasons.append(f"강한 하락 모멘텀 (추세강도 {ts:.2f})")
    elif ts < -0.1:
        score -= 1

    # 52주 고저 위치
    cur   = ind.get("current_price", 0)
    h120  = ind.get("resistance_120d", cur * 1.3)
    l120  = ind.get("support_120d", cur * 0.7)
    if cur and h120 and l120:
        pos = (cur - l120) / (h120 - l120 + 1e-9)
        if pos < 0.2:
            score += 2; reasons.append("52주 저점 근방 — 역발산 기회")
        elif pos > 0.85:
            score -= 1.5; reasons.append("52주 고점 근방 — 차익실현 주의")

    # 코퍼 (글로벌 경기선행)
    copper_chg = macro_snap.get("Copper", {}).get("chg_pct", 0)
    if copper_chg > 1:
        score += 1; reasons.append(f"구리 +{copper_chg:.1f}% — 경기 개선 시그널")
    elif copper_chg < -2:
        score -= 1

    # KOSPI 방향
    kospi_chg = macro_snap.get("KOSPI", {}).get("chg_pct", 0)
    if kospi_chg > 0.5:
        score += 0.5
    elif kospi_chg < -1:
        score -= 0.5

    score = max(0, min(15, score))
    return round(score, 1), reasons


# ════════════════════════════════════════════════════════════════════════════
# G. 종합 신호 생성
# ════════════════════════════════════════════════════════════════════════════

def _band(val: float, bands: list) -> str:
    for lo, hi, label in bands:
        if lo <= val <= hi:
            return label
    return bands[-1][2]


def generate_signal(
    ticker: str,
    name: str,
    stock_data: dict,
    macro_snap: dict,
) -> dict:
    """단일 종목 신호 생성"""

    ohlcv     = stock_data.get("ohlcv", pd.DataFrame())
    fund      = stock_data.get("fundamental", {})
    investor  = stock_data.get("investor", pd.DataFrame())
    naver     = stock_data.get("naver", {})
    f_ratio   = stock_data.get("foreign_ratio", 0.0)

    # 지표 계산
    ind = calc_indicators(ohlcv)
    cur = ind.get("current_price") or naver.get("current_price", 0)

    # 개별 점수 (각 최대치 기준)
    s_mac, r_mac = score_macro(macro_snap)
    s_fun, r_fun = score_fundamental(fund, naver)
    s_snd, r_snd = score_supply_demand(investor, f_ratio)
    s_tec, r_tec = score_technical(ind)
    s_mom, r_mom = score_momentum(ind, macro_snap)

    # 가중 합산 → 0-100
    raw_score = (
        s_mac * (25 / 25) +
        s_fun * (25 / 20) +   # 각 카테고리 만점을 25점으로 정규화
        s_snd * (25 / 20) +
        s_tec * (25 / 20) +
        s_mom * (25 / 15)
    )
    # 각 가중치 적용
    overall = (
        s_mac   / 25 * 100 * WEIGHTS["macro"] +
        s_fun   / 20 * 100 * WEIGHTS["fundamental"] +
        s_snd   / 20 * 100 * WEIGHTS["supply_demand"] +
        s_tec   / 20 * 100 * WEIGHTS["technical"] +
        s_mom   / 15 * 100 * WEIGHTS["momentum"]
    )
    overall = round(overall, 1)

    signal     = _band(overall, SIGNAL_BANDS)
    confidence = _band(overall, [(h, 100, c) if i == 0 else (0, h-0.1, c) for i, (h, c) in enumerate(CONFIDENCE_BANDS)])
    # 신뢰도 재계산 (단순화)
    if overall >= 70:   confidence = "HIGH"
    elif overall >= 45: confidence = "MEDIUM"
    else:               confidence = "LOW"

    # 진입/목표/손절 가격
    if cur and cur > 0:
        support  = ind.get("support_20d", cur * 0.94)
        resist   = ind.get("resistance_20d", cur * 1.12)
        ma20     = ind.get("ma20", cur)
        bb_lower = ind.get("bb_lower", cur * 0.95)

        entry_low  = round(min(ma20, bb_lower) * 0.99, -1)
        entry_high = round(cur * 1.01, -1)
        target     = round(resist * 1.02, -1)
        stop_loss  = round(support * 0.97, -1)
    else:
        entry_low = entry_high = target = stop_loss = None

    # 리스크 플래그
    risk_flags = []
    krw = macro_snap.get("USD/KRW", {}).get("value", 0)
    if krw > 1380:
        risk_flags.append(f"USD/KRW {krw:.0f} 이상 — 외환 리스크 모니터링")
    if ind.get("rsi_overbought"):
        risk_flags.append(f"RSI {ind.get('rsi', 0):.0f} 과매수 — 단기 조정 가능")
    if ind.get("dead_cross"):
        risk_flags.append("데드크로스 발생 — 추세 전환 주의")
    vix = macro_snap.get("VIX", {}).get("value", 0)
    if vix > 25:
        risk_flags.append(f"VIX {vix:.1f} — 시장 변동성 확대")

    # 상위 3개 근거
    all_reasons = r_mac + r_fun + r_snd + r_tec + r_mom
    top_reasons = all_reasons[:3] if all_reasons else ["데이터 부족 — 신호 신뢰도 낮음"]

    return {
        "ticker":        ticker,
        "name":          name,
        "signal":        signal,
        "confidence":    confidence,
        "overall_score": overall,
        "scores": {
            "macro":        s_mac,
            "fundamental":  s_fun,
            "supply_demand":s_snd,
            "technical":    s_tec,
            "momentum":     s_mom,
        },
        "entry_zone":  {"low": entry_low, "high": entry_high},
        "target_price":stop_loss if signal in ("SELL","STRONG SELL") else target,
        "stop_loss":   stop_loss,
        "top_reasons": top_reasons,
        "risk_flags":  risk_flags,
        "indicators":  {k: v for k, v in ind.items() if not isinstance(v, bool) or v},
        "current_price": cur,
    }


def generate_all_signals(
    collected: dict,
    watchlist: dict,
    macro_snap: dict,
) -> list[dict]:
    """전체 워치리스트 신호 생성"""
    signals = []
    for ticker, name in watchlist.items():
        data = collected.get(ticker, {})
        try:
            sig = generate_signal(ticker, name, data, macro_snap)
            signals.append(sig)
            lvl = sig["signal"]
            sc  = sig["overall_score"]
            print(f"  {ticker} {name:12s} → {lvl:12s} {sc:.0f}점 [{sig['confidence']}]")
        except Exception as e:
            print(f"  [오류] {ticker} {name}: {e}")
    return sorted(signals, key=lambda x: -x["overall_score"])
