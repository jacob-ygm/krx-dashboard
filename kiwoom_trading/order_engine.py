"""
주문 오케스트레이션
사이징 → 중복/한도 검증 → 승인 → 실행 순서로 처리
"""
from __future__ import annotations
import logging

from . import config
from . import kiwoom_client as client
from .signals  import Signal
from .safety   import check_duplicate, check_order_limit
from .notifier import request_approval
from . import account

logger = logging.getLogger(__name__)

# ── 매수 주문 API ────────────────────────────────────────────
_API_BUY  = "kt10000"   # 주식매수주문
_API_SELL = "kt10001"   # 주식매도주문
_PATH_ORDER = "/api/dostk/ordr"

# 주문유형: "0" = 지정가, "3" = 시장가
_ORDER_TYPE_MARKET = "3"
_ORDER_TYPE_LIMIT  = "0"

# 거래소 구분 (기본값: KRX)
_EXCHANGE = "KRX"


def _place_buy(signal: Signal, qty: int) -> dict:
    """실제 매수 주문 전송 (DRY_RUN=false 일 때만 호출됨)."""
    body = {
        "acnt_no":     config.ACCOUNT_NO,
        "stk_cd":      signal.code,
        "ord_qty":     str(qty),
        "ord_uv":      "0",               # 시장가: 0
        "trde_tp":     _ORDER_TYPE_MARKET,
        "dmst_stex_tp": _EXCHANGE,
    }
    return client.post(_API_BUY, _PATH_ORDER, body)


def run_order(signal: Signal) -> None:
    """
    단일 시그널에 대해 매수 프로세스 전체를 실행한다.
    1. 보유종목 조회 → 중복 체크
    2. 예수금 조회 → 주문 수량 계산
    3. 승인 요청
    4. 주문 전송 (DRY_RUN=false 이고 승인된 경우만)
    """
    logger.info("주문 처리 시작: %s (%s)", signal.name, signal.code)

    positions = account.get_positions()
    if check_duplicate(signal, positions):
        logger.warning("%s 이미 보유 중 — 중복매수 차단", signal.code)
        return

    deposit = account.get_deposit()
    ok, qty = check_order_limit(signal, deposit)
    if not ok:
        logger.warning("%s 한도 초과 또는 자금 부족 — 주문 불가", signal.code)
        return

    approved = request_approval(signal, qty)
    if not approved:
        logger.info("%s 주문 미승인 또는 DRY_RUN — 스킵", signal.code)
        return

    result = _place_buy(signal, qty)
    logger.info(
        "매수 주문 완료: %s %d주 | 주문번호=%s",
        signal.code, qty, result.get("ord_no", "?")
    )


def place_top_orders(top_df, price_map: dict, qty_per_stock: int = 1) -> list[dict]:
    """
    예측 상위 종목 직접 매수 (모의투자 테스트용, DRY_RUN 무관하게 전송).
    top_df : final_score 기준 정렬된 DataFrame (code 컬럼 필요)
    price_map : {code: price}
    qty_per_stock : 종목당 주문 수량
    """
    results = []
    for _, row in top_df.iterrows():
        code = row["code"]
        body = {
            "acnt_no":      config.ACCOUNT_NO,
            "stk_cd":       code,
            "ord_qty":      str(qty_per_stock),
            "ord_uv":       "0",
            "trde_tp":      _ORDER_TYPE_MARKET,
            "dmst_stex_tp": _EXCHANGE,
        }
        try:
            resp = client.post(_API_BUY, _PATH_ORDER, body)
            results.append({
                "code":   code,
                "status": "성공",
                "ord_no": resp.get("ord_no", resp.get("return_msg", "?")),
            })
            logger.info("모의매수 완료: %s %d주", code, qty_per_stock)
        except Exception as e:
            results.append({"code": code, "status": f"실패: {e}", "ord_no": "-"})
            logger.error("모의매수 실패: %s — %s", code, e)
    return results


def run_all(signals: list[Signal]) -> None:
    """BUY 시그널 전체에 대해 순차적으로 주문을 처리한다."""
    buy_signals = [s for s in signals if s.action == "BUY"]
    logger.info("총 %d개 매수 시그널 처리 시작", len(buy_signals))
    for sig in buy_signals:
        try:
            run_order(sig)
        except Exception as exc:
            logger.error("%s 주문 처리 중 오류: %s", sig.code, exc)
