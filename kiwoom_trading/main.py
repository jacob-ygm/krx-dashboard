"""
키움 자동매매 엔트리포인트

실행:
  python -m kiwoom_trading.main

설정:
  .env 에서 TRADING_MODE, DRY_RUN 등을 설정한다.
  (기본값: TRADING_MODE=mock, DRY_RUN=true)
"""
import logging
import pandas as pd

from . import config
from .signals      import generate_signals
from .order_engine import run_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "키움 자동매매 시작 | mode=%s | dry_run=%s",
        config.TRADING_MODE, config.DRY_RUN
    )

    # ── 예측 결과 로드 ────────────────────────────────────────
    # full_result.csv 는 Colab 파이프라인이 생성하는 파일
    try:
        df = pd.read_csv("full_result.csv")
    except FileNotFoundError:
        logger.error("full_result.csv 없음 — Colab 파이프라인을 먼저 실행하세요")
        return

    # ── 시그널 생성 ───────────────────────────────────────────
    signals = generate_signals(df)
    buy_cnt = sum(1 for s in signals if s.action == "BUY")
    logger.info("시그널 생성 완료: BUY=%d / 전체=%d", buy_cnt, len(signals))

    for s in signals[:5]:
        logger.info(
            "  [%s] %s(%s) prob=%.1f%% ret5d=%+.2f%%",
            s.action, s.name, s.code, s.prob_up * 100, s.pred_ret5d * 100
        )

    # ── 주문 실행 ─────────────────────────────────────────────
    run_all(signals)

    logger.info("처리 완료")


if __name__ == "__main__":
    main()
