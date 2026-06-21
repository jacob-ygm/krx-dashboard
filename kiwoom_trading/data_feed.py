"""
시세 / 차트 조회
- get_current_price : 현재가 (ka10004, 주식호가요청)
- get_daily_chart   : 일봉 OHLCV (ka10081, 주식일봉차트조회)
"""
from . import kiwoom_client as client

# ── API ID 상수 ──────────────────────────────────────────────
_API_PRICE = "ka10004"   # 주식호가요청
_API_CHART = "ka10081"   # 주식일봉차트조회

# ── URL 경로 ─────────────────────────────────────────────────
_PATH_PRICE = "/api/dostk/mrkcond"   # 시세조건 (호가)
_PATH_CHART = "/api/dostk/chart"     # 차트


def get_current_price(stk_cd: str) -> dict:
    """
    종목 현재가 조회.

    Parameters
    ----------
    stk_cd : str
        종목코드 (예: "005930")

    Returns
    -------
    dict
        {
          "stk_cd"    : "005930",
          "stck_prpr" : "75000",     # 현재가
          "prdy_vrss" : "500",       # 전일 대비
          "prdy_ctrt" : "0.67",      # 전일 대비율(%)
          ...                        # 기타 호가 필드
        }
    """
    body = {"stk_cd": stk_cd}
    resp = client.post(_API_PRICE, _PATH_PRICE, body)
    return resp.get("body", resp)


def get_daily_chart(stk_cd: str,
                    base_dt: str = "00000000",
                    adj_price: bool = True) -> list[dict]:
    """
    일봉 OHLCV 조회 (최대 600일, 연속조회로 전부 수집).

    Parameters
    ----------
    stk_cd    : 종목코드
    base_dt   : 기준일 "YYYYMMDD", "00000000" = 오늘
    adj_price : True → 수정주가 적용

    Returns
    -------
    list[dict]  각 dict 는 1일치 봉 데이터
        {
          "dt"        : "20260619",  # 날짜
          "open_pric" : "372500",    # 시가
          "high_pric" : "374500",    # 고가
          "low_pric"  : "346250",    # 저가
          "cur_prc"   : "354000",    # 종가(현재가)
          "trde_qty"  : "43284898",  # 거래량
          "pred_pre"  : "-8500",     # 전일대비
          ...
        }
    """
    body = {
        "stk_cd":       stk_cd,
        "base_dt":      base_dt,
        "upd_stkpc_tp": "1" if adj_price else "0",
    }

    results: list[dict] = []
    cont_yn  = "N"
    next_key = ""

    while True:
        resp = client.post(_API_CHART, _PATH_CHART, body,
                           cont_yn=cont_yn, next_key=next_key)
        # 실제 응답 키: stk_dt_pole_chart_qry
        rows = resp.get("stk_dt_pole_chart_qry", resp.get("body", []))
        if isinstance(rows, list):
            results.extend(rows)
        elif rows:
            results.append(rows)

        cont_yn  = resp.get("cont_yn", "N")
        next_key = resp.get("next_key", "")
        if cont_yn != "Y":
            break

    return results
