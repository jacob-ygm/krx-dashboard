"""
ML 예측 + 룰 기반 신호 결합 → 종목 스코어 생성

학습 → 예측 흐름:
  1. fetch_training_data()  : 상위 N종목 120일치 차트 수집
  2. train()                : XGBoost + LightGBM 앙상블 학습
  3. predict_all()          : 최신 피처로 전종목 예측
  4. rule_score()           : RSI·MACD·거래량 룰 스코어 계산
  5. combined_score()       : ML + 룰 합산
"""
from __future__ import annotations
import pickle
import logging
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .feature_builder import build_features, FEATURE_COLS

logger = logging.getLogger(__name__)

MODEL_PATH = Path("kiwoom_model.pkl")

# ── 데이터 수집 ───────────────────────────────────────────────
def fetch_chart_data(
    codes: list[str],
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> dict[str, list[dict]]:
    """
    codes 리스트에 대해 ka10081 120일치 일봉 수집.
    Returns: {code: chart_rows}
    """
    from . import kiwoom_client as client

    result = {}
    for i, code in enumerate(codes):
        if progress_cb:
            progress_cb(i, len(codes), code)
        try:
            body = {"stk_cd": code, "base_dt": "00000000", "upd_stkpc_tp": "1"}
            resp = client.post("ka10081", "/api/dostk/chart", body)
            rows = resp.get("stk_dt_pole_chart_qry", [])
            if rows:
                result[code] = rows[:120]   # 최근 120일
        except Exception as e:
            logger.warning("차트 조회 실패 %s: %s", code, e)
    return result


def build_dataset(
    chart_data: dict[str, list[dict]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    chart_data → (train_df, latest_df)
    train_df  : 전체 일별 피처+레이블 (학습용)
    latest_df : 종목별 최신 피처 1행 (예측용)
    """
    all_feats, latest_rows = [], []

    for code, rows in chart_data.items():
        feat_df = build_features(code, rows)
        if feat_df is None or len(feat_df) < 10:
            continue
        all_feats.append(feat_df)

        # 레이블이 없는(미래) 마지막 행 = 예측 대상
        latest = feat_df.iloc[-1:].copy()
        latest_rows.append(latest)

    train_df  = pd.concat(all_feats,  ignore_index=True) if all_feats else pd.DataFrame()
    latest_df = pd.concat(latest_rows, ignore_index=True) if latest_rows else pd.DataFrame()
    return train_df, latest_df


# ── 모델 학습 ─────────────────────────────────────────────────
def train(train_df: pd.DataFrame) -> dict:
    """
    RandomForest + GradientBoosting 학습 (sklearn, Python 3.14 호환).
    Returns model dict (저장 후 재사용 가능).
    """
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier

    df = train_df.dropna(subset=["label"] + FEATURE_COLS)
    X  = df[FEATURE_COLS].values
    y  = df["label"].values

    if len(np.unique(y)) < 2:
        raise ValueError(f"레이블 클래스가 1개뿐입니다 (unique={np.unique(y)}). 데이터를 늘려주세요.")

    logger.info("학습 데이터: %d행, 상승비율=%.1f%%", len(df), y.mean() * 100)

    rf_model = RandomForestClassifier(
        n_estimators=200, max_depth=6, min_samples_leaf=5,
        random_state=42, n_jobs=-1,
    )
    rf_model.fit(X, y)

    gb_model = GradientBoostingClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, random_state=42,
    )
    gb_model.fit(X, y)

    model = {"rf": rf_model, "gb": gb_model}
    MODEL_PATH.write_bytes(pickle.dumps(model))
    logger.info("모델 저장 완료: %s", MODEL_PATH)
    return model


def load_model() -> dict | None:
    if MODEL_PATH.exists():
        return pickle.loads(MODEL_PATH.read_bytes())
    return None


# ── 예측 ─────────────────────────────────────────────────────
def predict_ml(latest_df: pd.DataFrame, model: dict) -> pd.DataFrame:
    """
    최신 피처 DataFrame → ML 상승확률 컬럼 추가.
    """
    df = latest_df.copy()
    valid = df.dropna(subset=FEATURE_COLS)
    if len(valid) == 0:
        df["prob_ml"] = np.nan
        return df

    X = valid[FEATURE_COLS].values
    prob_rf  = model["rf"].predict_proba(X)[:, 1]
    prob_gb  = model["gb"].predict_proba(X)[:, 1]
    prob_avg = (prob_rf + prob_gb) / 2

    df.loc[valid.index, "prob_ml"] = prob_avg
    return df


# ── 룰 기반 스코어 ────────────────────────────────────────────
def rule_score(latest_df: pd.DataFrame) -> pd.DataFrame:
    """
    RSI·MACD·거래량 룰 → 0~1 스코어 (rule_score 컬럼 추가).
    """
    df = latest_df.copy()
    score = pd.Series(0.0, index=df.index)

    # RSI 과매도 (0~30): +0.3
    if "rsi14" in df.columns:
        score += (df["rsi14"] < 30).astype(float) * 0.30
        # RSI 30~50 반등 구간: +0.15
        score += ((df["rsi14"] >= 30) & (df["rsi14"] < 50)).astype(float) * 0.15

    # MACD 골든크로스: +0.25
    if "macd_cross" in df.columns:
        score += df["macd_cross"].fillna(0) * 0.25

    # 볼린저 하단 근처 (bb_pct < 0.2): +0.20
    if "bb_pct" in df.columns:
        score += (df["bb_pct"] < 0.2).astype(float) * 0.20

    # 거래량 급등 (vol_ratio > 2): +0.15
    if "vol_ratio" in df.columns:
        score += (df["vol_ratio"] > 2).astype(float) * 0.15

    # 단기 모멘텀 양전환 (ret_1d > 0 & ret_5d < 0): +0.10
    if "ret_1d" in df.columns and "ret_5d" in df.columns:
        score += ((df["ret_1d"] > 0) & (df["ret_5d"] < 0)).astype(float) * 0.10

    df["rule_score"] = score.clip(0, 1)
    return df


# ── 최종 스코어 결합 ──────────────────────────────────────────
def combined_score(df: pd.DataFrame,
                   ml_weight: float = 0.6,
                   rule_weight: float = 0.4) -> pd.DataFrame:
    """
    prob_ml * ml_weight + rule_score * rule_weight → final_score
    prob_ml 없는 종목은 rule_score만 사용.
    """
    out = df.copy()
    has_ml = out["prob_ml"].notna()

    out["final_score"] = np.where(
        has_ml,
        out["prob_ml"].fillna(0) * ml_weight + out["rule_score"] * rule_weight,
        out["rule_score"],
    )
    return out.sort_values("final_score", ascending=False)
