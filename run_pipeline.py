# run_pipeline.py
"""
Google Colab 실행 메인 파이프라인
─────────────────────────────────
셀 1개로 전체 실행:
  !python run_pipeline.py

또는 노트북에서:
  exec(open("run_pipeline.py").read())
"""

# ════════════════════════════════════════════════════════════════════════════
# 0. 패키지 설치 (Colab 환경)
# ════════════════════════════════════════════════════════════════════════════

import subprocess, sys

def _install(pkg):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-q", pkg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

REQUIRED = ["pykrx", "yfinance", "beautifulsoup4", "requests", "pytz",
            "pandas", "numpy", "PyGithub"]

for p in REQUIRED:
    try:
        __import__(p.replace("-","_").split("[")[0])
    except ImportError:
        print(f"[설치] {p}")
        _install(p)

# ════════════════════════════════════════════════════════════════════════════
# 1. 임포트
# ════════════════════════════════════════════════════════════════════════════

import io, gzip, json, os
from datetime import datetime
import pandas as pd
import pytz

KST = pytz.timezone("Asia/Seoul")

from config import WATCHLIST, KRX_TICKERS, YF_TICKERS, MACRO_YF, GITHUB_REPO, GITHUB_BRANCH, DATA_FILE
from data_collector import collect_all, get_macro_snapshot
from signal_engine import generate_all_signals, get_macro_regime

# ════════════════════════════════════════════════════════════════════════════
# 2. 실행
# ════════════════════════════════════════════════════════════════════════════

def run(github_token: str = None, verbose: bool = True):
    now_kst = datetime.now(KST)
    print(f"\n{'='*60}")
    print(f"  KRX Signal Pipeline  |  {now_kst.strftime('%Y-%m-%d %H:%M KST')}")
    print(f"{'='*60}\n")

    # ── 2-1. 매크로 수집 ────────────────────────────────────────────────
    print("▶ 매크로 데이터 수집 중...")
    macro_snap = get_macro_snapshot()
    regime = get_macro_regime(macro_snap)
    print(f"  매크로 레짐: {regime}")
    for k, v in macro_snap.items():
        print(f"  {k:12s}: {v['value']:>10.3f}  ({v['chg_pct']:+.2f}%)")

    # ── 2-2. 종목 데이터 수집 ───────────────────────────────────────────
    print("\n▶ 종목 데이터 수집 중...")
    collected = collect_all(WATCHLIST)

    # ── 2-3. 신호 생성 ──────────────────────────────────────────────────
    print("\n▶ 신호 생성 중...")
    signals = generate_all_signals(collected, WATCHLIST, macro_snap)

    # ── 2-4. DataFrame 변환 ─────────────────────────────────────────────
    rows = []
    for s in signals:
        rows.append({
            "datetime_kst":   now_kst.strftime("%Y-%m-%d %H:%M"),
            "ticker":         s["ticker"],
            "name":           s["name"],
            "signal":         s["signal"],
            "confidence":     s["confidence"],
            "overall_score":  s["overall_score"],
            "score_macro":    s["scores"]["macro"],
            "score_fund":     s["scores"]["fundamental"],
            "score_sd":       s["scores"]["supply_demand"],
            "score_tech":     s["scores"]["technical"],
            "score_mom":      s["scores"]["momentum"],
            "current_price":  s.get("current_price", None),
            "entry_low":      s["entry_zone"]["low"],
            "entry_high":     s["entry_zone"]["high"],
            "target_price":   s.get("target_price"),
            "stop_loss":      s.get("stop_loss"),
            "top_reasons":    " | ".join(s["top_reasons"]),
            "risk_flags":     " | ".join(s["risk_flags"]),
            "macro_regime":   regime,
            # 매크로 스냅샷 요약
            "vix":     macro_snap.get("VIX", {}).get("value"),
            "dxy":     macro_snap.get("DXY", {}).get("value"),
            "usdkrw":  macro_snap.get("USD/KRW", {}).get("value"),
            "sp500_chg":macro_snap.get("S&P500", {}).get("chg_pct"),
            "wti":     macro_snap.get("WTI", {}).get("value"),
        })

    df = pd.DataFrame(rows)

    # ── 2-5. 결과 출력 ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  레짐: {regime}  |  종목수: {len(signals)}")
    print(f"{'='*60}")

    buy_signals  = df[df["signal"].isin(["STRONG BUY", "BUY"])]
    sell_signals = df[df["signal"].isin(["STRONG SELL", "SELL"])]
    print(f"\n🟢 BUY 신호 ({len(buy_signals)}개):")
    for _, r in buy_signals.iterrows():
        print(f"   {r['ticker']} {r['name']:12s}  {r['signal']:12s}  {r['overall_score']:.0f}점")
        print(f"     → 진입: {r['entry_low']:,.0f}~{r['entry_high']:,.0f}  목표: {r['target_price']:,.0f}  손절: {r['stop_loss']:,.0f}")

    print(f"\n🔴 SELL 신호 ({len(sell_signals)}개):")
    for _, r in sell_signals.iterrows():
        print(f"   {r['ticker']} {r['name']:12s}  {r['signal']:12s}  {r['overall_score']:.0f}점")

    # ── 2-6. 저장 ────────────────────────────────────────────────────────
    # 로컬 저장 (Colab /content)
    local_path = "/content/signals_latest.csv.gz"
    df.to_csv(local_path, index=False, compression="gzip", encoding="utf-8-sig")
    print(f"\n✅ 로컬 저장: {local_path}")

    # JSON 저장 (Streamlit용 상세 데이터)
    json_path = "/content/signals_detail.json"
    # 한글 포함 데이터 ASCII 인코딩으로 저장
    export_data = {
        "regime": regime,
        "macro": macro_snap,
        "signals": signals,
        "updated": now_kst.strftime("%Y-%m-%d %H:%M KST")
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"✅ JSON 저장: {json_path}")

    # ── 2-7. GitHub 업로드 (토큰 제공 시) ───────────────────────────────
    if github_token:
        try:
            from github import Github
            g  = Github(github_token)
            repo = g.get_repo(GITHUB_REPO)

            # CSV.GZ 업로드
            with open(local_path, "rb") as f:
                content = f.read()
            try:
                existing = repo.get_contents(DATA_FILE, ref=GITHUB_BRANCH)
                repo.update_file(DATA_FILE, f"Auto: signals {now_kst.strftime('%Y-%m-%d %H:%M')}",
                                 content, existing.sha, branch=GITHUB_BRANCH)
            except:
                repo.create_file(DATA_FILE, f"Init: signals {now_kst.strftime('%Y-%m-%d')}",
                                 content, branch=GITHUB_BRANCH)

            # JSON 업로드 (utf-8 바이트로 인코딩)
            json_github = "data/signals_detail.json"
            with open(json_path, "r", encoding="utf-8") as f:
                jcontent = f.read()
            jbytes = jcontent.encode("utf-8")
            import base64
            jb64 = base64.b64encode(jbytes).decode("ascii")
            try:
                existing_j = repo.get_contents(json_github, ref=GITHUB_BRANCH)
                repo._Github__requester.requestJsonAndCheck(
                    "PUT",
                    repo.url + "/contents/" + json_github,
                    input={
                        "message": f"Auto: detail {now_kst.strftime('%Y-%m-%d %H:%M')}",
                        "content": jb64,
                        "sha": existing_j.sha,
                        "branch": GITHUB_BRANCH,
                    }
                )
            except Exception as je:
                repo.create_file(json_github, "Init: detail", jcontent.encode("utf-8"), branch=GITHUB_BRANCH)

            print(f"✅ GitHub 업로드 완료: {GITHUB_REPO}/{DATA_FILE}")
        except Exception as e:
            print(f"⚠️  GitHub 업로드 실패: {e}")
    else:
        print("\n💡 GitHub 업로드 건너뜀 (github_token 미제공)")
        print("   사용법: run(github_token='ghp_xxxx...')")

    return df, signals, macro_snap, regime


# ════════════════════════════════════════════════════════════════════════════
# 3. 백테스팅 (간단 버전)
# ════════════════════════════════════════════════════════════════════════════

def simple_backtest(signal_history_csv: str, forward_days: int = 5) -> pd.DataFrame:
    """
    signal_history_csv: 과거 신호 CSV (run()이 매일 저장한 누적 파일)
    forward_days: 신호 후 n일 수익률로 평가
    """
    try:
        df = pd.read_csv(signal_history_csv, compression="gzip")
    except:
        print("백테스팅 데이터 없음 (누적 신호 파일 필요)")
        return pd.DataFrame()

    # 신호별 통계
    stats = df.groupby("signal").agg(
        count=("overall_score", "count"),
        avg_score=("overall_score", "mean"),
    ).round(1)
    print("\n📊 신호 분포:")
    print(stats.to_string())
    return stats


# ════════════════════════════════════════════════════════════════════════════
# 4. 직접 실행
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # ⚙️ 여기에 GitHub Personal Access Token 입력 (없으면 None)
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", None)
    
    df, signals, macro, regime = run(github_token=GITHUB_TOKEN)
    print(f"\n완료. 총 {len(signals)}개 신호 생성.")
