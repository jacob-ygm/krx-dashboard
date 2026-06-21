"""
키움 REST API 설정 로더
모든 인증정보와 리스크 파라미터는 .env에서 읽는다.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── 인증 ────────────────────────────────────────────────────
APP_KEY    = os.environ.get("KIWOOM_APP_KEY", "")
SECRET_KEY = os.environ.get("KIWOOM_SECRET_KEY", "")
ACCOUNT_NO = os.environ.get("KIWOOM_ACCOUNT_NO", "")

# ── 거래 모드 ────────────────────────────────────────────────
# "mock" → 모의투자 서버, "real" → 실거래 서버
TRADING_MODE = os.environ.get("TRADING_MODE", "mock")

# true: 주문 직전 단계까지만 실행, 실제 API 전송 없음
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# ── 베이스 URL ───────────────────────────────────────────────
if TRADING_MODE == "real":
    BASE_URL = "https://api.kiwoom.com"
else:
    BASE_URL = "https://mockapi.kiwoom.com"

# ── 리스크 파라미터 ──────────────────────────────────────────
MAX_ORDER_AMOUNT   = int(os.environ.get("MAX_ORDER_AMOUNT",   "500000"))
MAX_POSITION_RATIO = float(os.environ.get("MAX_POSITION_RATIO", "0.05"))
MAX_PORTFOLIO_RATIO = float(os.environ.get("MAX_PORTFOLIO_RATIO", "0.50"))
