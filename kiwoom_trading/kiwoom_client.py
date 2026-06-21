"""
키움 REST API 저수준 클라이언트
- 토큰 발급 / 자동 갱신
- GET / POST 래퍼 (헤더, 에러 공통 처리)
"""
import time
import requests
from . import config

# ── 엔드포인트 ───────────────────────────────────────────────
TOKEN_PATH = "/oauth2/token"          # 토큰 발급 (au10001)

# ── 내부 상태 ────────────────────────────────────────────────
_token: str | None = None
_token_expires: float = 0.0           # unix timestamp


def _issue_token() -> str:
    """appkey + secretkey → access token 발급."""
    url = config.BASE_URL + TOKEN_PATH
    payload = {
        "grant_type": "client_credentials",
        "appkey":    config.APP_KEY,
        "secretkey": config.SECRET_KEY,
    }
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("return_code", -1) != 0:
        raise RuntimeError(f"토큰 발급 실패: {data.get('return_msg')}")

    # expires_dt 형식: "20241107083713" (YYYYMMDDHHmmss)
    raw = data["expires_dt"]
    import datetime
    dt = datetime.datetime.strptime(raw, "%Y%m%d%H%M%S")
    expires_ts = dt.timestamp()

    return data["token"], expires_ts


def get_token() -> str:
    """캐시된 토큰 반환; 만료 5분 전이면 자동 재발급."""
    global _token, _token_expires
    if _token is None or time.time() > _token_expires - 300:
        _token, _token_expires = _issue_token()
    return _token


def _headers(api_id: str, cont_yn: str = "N", next_key: str = "") -> dict:
    h = {
        "Content-Type":  "application/json",
        "authorization": f"Bearer {get_token()}",
        "api-id":        api_id,
    }
    if cont_yn == "Y":
        h["cont-yn"] = "Y"
        h["next-key"] = next_key
    return h


def post(api_id: str, path: str, body: dict,
         cont_yn: str = "N", next_key: str = "") -> dict:
    """POST 요청 공통 래퍼. return_code != 0 이면 RuntimeError."""
    url = config.BASE_URL + path
    resp = requests.post(url, json=body,
                         headers=_headers(api_id, cont_yn, next_key),
                         timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("return_code", -1) != 0:
        raise RuntimeError(
            f"[{api_id}] API 오류 {data.get('return_code')}: {data.get('return_msg')}"
        )
    return data


def get(api_id: str, path: str, params: dict | None = None) -> dict:
    """GET 요청 공통 래퍼."""
    url = config.BASE_URL + path
    resp = requests.get(url, params=params,
                        headers=_headers(api_id), timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("return_code", -1) != 0:
        raise RuntimeError(
            f"[{api_id}] API 오류 {data.get('return_code')}: {data.get('return_msg')}"
        )
    return data
