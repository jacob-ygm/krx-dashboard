"""
계좌 잔고 / 보유종목 조회
- get_deposit   : 예수금 잔고 (kt00001, 예수금상세요청)
- get_positions : 보유종목 목록 (kt00005, 체결잔고요청)
"""
from . import kiwoom_client as client
from . import config

# ── API ID ───────────────────────────────────────────────────
_API_DEPOSIT   = "kt00001"   # 예수금상세요청
_API_POSITIONS = "kt00005"   # 체결잔고요청

# ── URL 경로 ─────────────────────────────────────────────────
_PATH_ACNT = "/api/dostk/acnt"


def get_deposit() -> dict:
    """
    예수금(주문 가능 현금) 조회.

    Returns
    -------
    dict
        {
          "dnca_tot_amt"  : "10000000",   # 예수금 총액
          "ord_psbl_cash" : "8000000",    # 주문가능현금
          ...
        }
    """
    body = {"acnt_no": config.ACCOUNT_NO, "qry_tp": "1"}
    resp = client.post(_API_DEPOSIT, _PATH_ACNT, body)
    return resp.get("body", resp)


def get_positions() -> list[dict]:
    """
    보유종목 전체 조회 (연속조회 포함).

    Returns
    -------
    list[dict]  각 dict 는 보유종목 1건
        {
          "stk_cd"     : "005930",    # 종목코드
          "stk_nm"     : "삼성전자",  # 종목명
          "hldg_qty"   : "10",        # 보유수량
          "pchs_avg_pric" : "70000",  # 매입평균가
          "evlu_amt"   : "750000",    # 평가금액
          "evlu_pfls_amt" : "50000",  # 평가손익
          ...
        }
    """
    # 모의투자에서는 kt00005 미지원 → 빈 리스트 반환
    if config.TRADING_MODE == "mock":
        import logging
        logging.getLogger(__name__).info("모의투자 모드: 보유종목 조회 미지원, 빈 리스트 반환")
        return []

    body = {"acnt_no": config.ACCOUNT_NO, "dmst_stex_tp": "KRX"}

    results: list[dict] = []
    cont_yn  = "N"
    next_key = ""

    while True:
        resp = client.post(_API_POSITIONS, _PATH_ACNT, body,
                           cont_yn=cont_yn, next_key=next_key)
        rows = resp.get("body", [])
        if isinstance(rows, list):
            results.extend(rows)
        elif rows:
            results.append(rows)

        cont_yn  = resp.get("cont_yn", "N")
        next_key = resp.get("next_key", "")
        if cont_yn != "Y":
            break

    return results
