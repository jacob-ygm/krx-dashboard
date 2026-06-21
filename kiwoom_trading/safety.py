"""
중복매수 방지 / 한도 체크
"""
from __future__ import annotations
from . import config
from .signals import Signal


def check_duplicate(signal: Signal, positions: list[dict]) -> bool:
    """
    이미 해당 종목을 보유 중이면 True (중복매수 차단).
    positions: account.get_positions() 반환값
    """
    held_codes = {p.get("stk_cd", "") for p in positions}
    return signal.code in held_codes


def check_order_limit(signal: Signal, deposit: dict) -> tuple[bool, int]:
    """
    주문 가능 여부 확인 및 주문 수량 산출.

    Returns
    -------
    (ok: bool, qty: int)
        ok=False 이면 주문 불가
    """
    available_cash = float(deposit.get("ord_psbl_cash", 0))
    price          = signal.current_price
    if price <= 0:
        return False, 0

    # 1회 주문 금액 상한 & 비중 한도
    max_by_abs   = config.MAX_ORDER_AMOUNT
    max_by_ratio = available_cash * config.MAX_POSITION_RATIO
    budget       = min(max_by_abs, max_by_ratio)

    qty = int(budget // price)
    if qty < 1:
        return False, 0

    return True, qty
