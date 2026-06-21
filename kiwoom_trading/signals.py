"""
예측 결과 → 매매 신호 변환

colab_pipeline_final.py 가 출력하는 full_result.csv 포맷:
  columns: code, name, sector, prob_up, prob_down, pred_ret5d,
           pred_price5d, grade, Close, bounce_score, ...

generate_signals() 는 위 DataFrame을 받아
Signal 리스트를 반환한다.
"""
from __future__ import annotations
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class Signal:
    code: str            # 6자리 종목코드
    name: str            # 종목명
    action: str          # "BUY" | "HOLD" | "SELL"
    prob_up: float       # 상승확률 (0–1)
    pred_ret5d: float    # 5일 예상수익률
    current_price: float # 현재가 (Close)
    grade: str           # 등급 (A+, A, B, ...)
    sector: str          # 섹터
    bounce_score: float  # 반등 스코어 (0–100)
    meta: dict = field(default_factory=dict)


# ── 시그널 기준 ──────────────────────────────────────────────
BUY_PROB_THRESHOLD    = 0.55   # prob_up ≥ 이 값이면 매수 고려
STRONG_BUY_PROB       = 0.70   # prob_up ≥ 이 값이면 강력매수
MIN_PRED_RET          = 0.005  # 최소 예상수익률 (0.5%)
SELL_PROB_THRESHOLD   = 0.35   # prob_up < 이 값이면 매도 고려
MAX_SIGNALS           = 10     # 반환할 최대 매수 시그널 수


def adapt_pipeline_output(df: pd.DataFrame) -> pd.DataFrame:
    """
    full_result.csv DataFrame을 signals 모듈이 기대하는 형태로 정규화.
    컬럼명 불일치 / 타입 오류를 방어적으로 처리한다.
    """
    required = {"code", "name", "prob_up", "pred_ret5d", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"full_result.csv에 필수 컬럼 없음: {missing}")

    out = df.copy()
    out["code"]         = out["code"].astype(str).str.zfill(6)
    out["prob_up"]      = pd.to_numeric(out["prob_up"],    errors="coerce").fillna(0.0)
    out["pred_ret5d"]   = pd.to_numeric(out["pred_ret5d"], errors="coerce").fillna(0.0)
    out["Close"]        = pd.to_numeric(out["Close"],      errors="coerce").fillna(0.0)
    out["grade"]        = out.get("grade",        pd.Series(["?"] * len(out))).fillna("?")
    out["sector"]       = out.get("sector",       pd.Series(["기타"] * len(out))).fillna("기타")
    out["bounce_score"] = pd.to_numeric(
        out.get("bounce_score", pd.Series([0.0] * len(out))), errors="coerce"
    ).fillna(0.0)

    return out


def generate_signals(predictions: pd.DataFrame | list[dict]) -> list[Signal]:
    """
    Parameters
    ----------
    predictions : pd.DataFrame 또는 list[dict]
        full_result.csv 를 읽은 DataFrame (또는 동일 구조의 dict 리스트)

    Returns
    -------
    list[Signal]
        BUY / SELL / HOLD 시그널 리스트
        BUY는 prob_up 내림차순으로 MAX_SIGNALS 개 이하
    """
    if isinstance(predictions, list):
        predictions = pd.DataFrame(predictions)

    df = adapt_pipeline_output(predictions)
    signals: list[Signal] = []

    for _, row in df.iterrows():
        pu  = float(row["prob_up"])
        ret = float(row["pred_ret5d"])

        if pu >= BUY_PROB_THRESHOLD and ret >= MIN_PRED_RET:
            action = "BUY"
        elif pu < SELL_PROB_THRESHOLD:
            action = "SELL"
        else:
            action = "HOLD"

        signals.append(Signal(
            code          = str(row["code"]),
            name          = str(row["name"]),
            action        = action,
            prob_up       = pu,
            pred_ret5d    = ret,
            current_price = float(row["Close"]),
            grade         = str(row.get("grade", "?")),
            sector        = str(row.get("sector", "기타")),
            bounce_score  = float(row.get("bounce_score", 0)),
            meta          = {
                "pred_price5d": row.get("pred_price5d", 0),
                "prob_down":    row.get("prob_down", 1 - pu),
            },
        ))

    # BUY 시그널: prob_up 내림차순 상위 N개, 나머지는 유지
    buy_signals  = sorted(
        [s for s in signals if s.action == "BUY"],
        key=lambda s: s.prob_up, reverse=True
    )[:MAX_SIGNALS]
    other_signals = [s for s in signals if s.action != "BUY"]

    return buy_signals + other_signals
