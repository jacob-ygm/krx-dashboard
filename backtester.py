# backtester.py
"""
백테스트 모듈
- 과거 신호 기록 누적 (GitHub에 signals_history.csv.gz 저장)
- 신호 발생일 종가 매수 → 5일/20일 후 종가 매도
- 승률, 평균수익률, Sharpe ratio 계산
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import yfinance as yf

try:
    import FinanceDataReader as fdr
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "finance-datareader"])
    import FinanceDataReader as fdr

KST = pytz.timezone("Asia/Seoul")
HISTORY_FILE = "data/signals_history.csv.gz"


# ────────────────────────────────────────────────────────────────────────────
# 1. 신호 히스토리 누적 저장
# ────────────────────────────────────────────────────────────────────────────

def append_signal_history(df_today: pd.DataFrame, repo=None, branch="main"):
    """
    오늘 신호를 누적 히스토리에 추가
    df_today: run_pipeline.py의 df 출력값
    """
    today_str = datetime.now(KST).strftime("%Y-%m-%d")
    df_today = df_today.copy()
    df_today["signal_date"] = today_str

    # GitHub에서 기존 히스토리 로드
    existing = _load_history_from_github(repo, branch)

    if existing is not None and not existing.empty:
        # 오늘 날짜 중복 제거 후 합치기
        existing = existing[existing["signal_date"] != today_str]
        combined = pd.concat([existing, df_today], ignore_index=True)
    else:
        combined = df_today

    # 로컬 저장
    local_path = "/content/signals_history.csv.gz"
    combined.to_csv(local_path, index=False, compression="gzip", encoding="utf-8-sig")
    print(f"✅ 히스토리 저장: {len(combined)}행 ({combined['signal_date'].nunique()}일치)")

    # GitHub 업로드
    if repo:
        try:
            content = open(local_path, "rb").read()
            try:
                existing_file = repo.get_contents(HISTORY_FILE, ref=branch)
                repo.update_file(HISTORY_FILE,
                    f"History: {today_str}",
                    content, existing_file.sha, branch=branch)
            except:
                repo.create_file(HISTORY_FILE,
                    f"Init history: {today_str}",
                    content, branch=branch)
            print(f"✅ GitHub 히스토리 업로드 완료")
        except Exception as e:
            print(f"⚠️ 히스토리 업로드 실패: {e}")

    return combined


def _load_history_from_github(repo=None, branch="main"):
    """GitHub에서 히스토리 로드"""
    if repo is None:
        return None
    try:
        import base64, io
        file = repo.get_contents(HISTORY_FILE, ref=branch)
        content = base64.b64decode(file.content)
        return pd.read_csv(io.BytesIO(content), compression="gzip")
    except:
        return None


# ────────────────────────────────────────────────────────────────────────────
# 2. 실제 수익률 계산
# ────────────────────────────────────────────────────────────────────────────

def get_price_after_n_days(ticker: str, signal_date: str, n: int, is_krx: bool) -> float:
    """신호일 + n 거래일 후 종가 반환"""
    try:
        start = pd.to_datetime(signal_date)
        end   = start + timedelta(days=n * 2 + 10)  # 충분한 여유
        end_str   = end.strftime("%Y-%m-%d")
        start_str = start.strftime("%Y-%m-%d")

        if is_krx:
            df = fdr.DataReader(ticker, start=start_str, end=end_str)
        else:
            df = yf.download(ticker, start=start_str, end=end_str,
                           progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        if df.empty or len(df) <= n:
            return None

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # 신호일 당일 종가 (진입가)
        signal_rows = df[df.index >= pd.to_datetime(signal_date)]
        if signal_rows.empty:
            return None
        entry_price = float(signal_rows["Close"].iloc[0] if "Close" in signal_rows.columns
                           else signal_rows["close"].iloc[0])

        # n 거래일 후 종가
        if len(signal_rows) <= n:
            return None
        exit_col = "Close" if "Close" in signal_rows.columns else "close"
        exit_price = float(signal_rows[exit_col].iloc[n])

        return round((exit_price - entry_price) / entry_price * 100, 2)

    except Exception as e:
        return None


# ────────────────────────────────────────────────────────────────────────────
# 3. 백테스트 실행
# ────────────────────────────────────────────────────────────────────────────

def run_backtest(history_df: pd.DataFrame, holding_days: int = 5) -> dict:
    """
    history_df: 누적 신호 히스토리
    holding_days: 5 또는 20
    """
    today = datetime.now(KST).date()
    results = []

    # 평가 가능한 행만 (오늘 기준 holding_days 거래일 이상 지난 것)
    cutoff = (datetime.now(KST) - timedelta(days=holding_days * 2)).strftime("%Y-%m-%d")
    df = history_df[history_df["signal_date"] < cutoff].copy()

    if df.empty:
        return {"error": f"평가 가능한 데이터 없음 (최소 {holding_days * 2}일 이상 필요)"}

    print(f"[백테스트] {holding_days}일 보유 | 평가 대상: {len(df)}건")

    for _, row in df.iterrows():
        ticker      = row["ticker"]
        signal      = row["signal"]
        signal_date = row["signal_date"]
        is_krx      = str(ticker).isdigit()

        # BUY/SELL 신호만 평가
        if signal not in ("STRONG BUY", "BUY", "SELL", "STRONG SELL"):
            continue

        ret = get_price_after_n_days(ticker, signal_date, holding_days, is_krx)
        if ret is None:
            continue

        # BUY면 수익률 그대로, SELL이면 반대
        actual_ret = ret if signal in ("STRONG BUY", "BUY") else -ret
        is_correct = actual_ret > 0

        results.append({
            "ticker":      ticker,
            "name":        row.get("name", ticker),
            "signal":      signal,
            "signal_date": signal_date,
            "score":       row.get("overall_score", 0),
            "return_pct":  actual_ret,
            "correct":     is_correct,
            "holding_days": holding_days,
        })

    if not results:
        return {"error": "평가된 신호 없음"}

    result_df = pd.DataFrame(results)

    # 통계
    win_rate    = result_df["correct"].mean() * 100
    avg_return  = result_df["return_pct"].mean()
    std_return  = result_df["return_pct"].std()
    sharpe      = (avg_return / std_return * np.sqrt(252 / holding_days)) if std_return > 0 else 0

    # 신호 종류별 통계
    by_signal = result_df.groupby("signal").agg(
        count=("correct", "count"),
        win_rate=("correct", lambda x: round(x.mean() * 100, 1)),
        avg_return=("return_pct", lambda x: round(x.mean(), 2)),
    ).to_dict("index")

    # 점수 구간별 통계
    result_df["score_band"] = pd.cut(result_df["score"],
        bins=[0, 40, 50, 60, 70, 100],
        labels=["<40", "40-50", "50-60", "60-70", ">70"])
    by_score = result_df.groupby("score_band", observed=True).agg(
        count=("correct", "count"),
        win_rate=("correct", lambda x: round(x.mean() * 100, 1)),
        avg_return=("return_pct", lambda x: round(x.mean(), 2)),
    ).to_dict("index")

    return {
        "holding_days": holding_days,
        "total_signals": len(result_df),
        "win_rate":     round(win_rate, 1),
        "avg_return":   round(avg_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "by_signal":    by_signal,
        "by_score":     {str(k): v for k, v in by_score.items()},
        "detail_df":    result_df,
    }


def run_full_backtest(repo=None, branch="main") -> dict:
    """5일 + 20일 동시 백테스트"""
    history = _load_history_from_github(repo, branch)
    if history is None or history.empty:
        print("⚠️ 히스토리 데이터 없음 — 신호를 며칠 쌓은 후 실행하세요")
        return {}

    print(f"총 히스토리: {len(history)}행, {history['signal_date'].nunique()}일치")

    result_5  = run_backtest(history, holding_days=5)
    result_20 = run_backtest(history, holding_days=20)

    return {"5d": result_5, "20d": result_20, "history": history}
