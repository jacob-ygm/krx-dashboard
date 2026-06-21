"""
실주문 전 콘솔 승인 요청
DRY_RUN=true 이면 자동 승인(실제 전송 없음) 처리
"""
from __future__ import annotations
from .signals import Signal
from . import config


def request_approval(signal: Signal, qty: int) -> bool:
    """
    주문 전 사람에게 확인을 요청한다.
    DRY_RUN 모드에서는 자동으로 False를 반환해 주문을 막는다.

    Returns
    -------
    bool  True = 승인, False = 거부/스킵
    """
    mode_tag = f"[{config.TRADING_MODE.upper()}]"
    dry_tag  = "[DRY-RUN]" if config.DRY_RUN else ""

    print(
        f"\n{'='*55}\n"
        f" {mode_tag}{dry_tag} 매수 주문 승인 요청\n"
        f"  종목: {signal.name} ({signal.code})\n"
        f"  수량: {qty}주  × {signal.current_price:,.0f}원 "
        f"= {qty * signal.current_price:,.0f}원\n"
        f"  상승확률: {signal.prob_up:.1%} | 예상수익(5일): {signal.pred_ret5d:+.2%}\n"
        f"  등급: {signal.grade} | 섹터: {signal.sector}\n"
        f"{'='*55}"
    )

    if config.DRY_RUN:
        print("  → DRY_RUN=true: 주문 전송 생략\n")
        return False

    answer = input("  주문을 실행하겠습니까? [y/N]: ").strip().lower()
    return answer == "y"
