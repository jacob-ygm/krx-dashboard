# config.py
import pytz

KST = pytz.timezone("Asia/Seoul")

# ── Watchlist (34 tickers) ──────────────────────────────────────────────────
WATCHLIST = {
    # KOSPI 블루칩
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "000270": "기아",
    "051910": "LG화학",
    "068270": "셀트리온",
    "035420": "NAVER",
    "035720": "카카오",
    "105560": "KB금융",
    "055550": "신한지주",
    "086790": "하나금융지주",
    "316140": "우리금융지주",
    "003550": "LG",
    "096770": "SK이노베이션",
    "017670": "SK텔레콤",
    "030200": "KT",
    "032830": "삼성생명",
    "010950": "S-Oil",
    "009150": "삼성전기",
    "006400": "삼성SDI",
    "207940": "삼성바이오로직스",
    "028260": "삼성물산",
    "012330": "현대모비스",
    "011170": "롯데케미칼",
    "010140": "삼성중공업",
    "042660": "한화오션",
    "329180": "HD현대중공업",
    # KOSDAQ
    "091990": "셀트리온헬스케어",
    "263750": "펄어비스",
    "112040": "위메이드",
    # 미국 ETF / 지수 (yfinance)
    "SPY":   "S&P500 ETF",
    "QQQ":   "NASDAQ ETF",
    "SOXL":  "반도체 3x ETF",
    "TLT":   "미국장기채 ETF",
}

# KRX vs yfinance 구분
KRX_TICKERS  = [t for t in WATCHLIST if t.isdigit()]
YF_TICKERS   = [t for t in WATCHLIST if not t.isdigit()]

# ── Signal weights ──────────────────────────────────────────────────────────
WEIGHTS = {
    "macro":        0.25,
    "fundamental":  0.20,
    "supply_demand":0.20,
    "technical":    0.20,
    "momentum":     0.15,
}

# ── Signal thresholds ───────────────────────────────────────────────────────
SIGNAL_BANDS = [
    (80, 100, "STRONG BUY"),
    (65,  80, "BUY"),
    (40,  65, "HOLD"),
    (25,  40, "SELL"),
    (  0, 25, "STRONG SELL"),
]

CONFIDENCE_BANDS = [
    (70, "HIGH"),
    (45, "MEDIUM"),
    (0,  "LOW"),
]

# ── GitHub storage (set your own repo) ─────────────────────────────────────
GITHUB_REPO  = "jacob-ygm/krx-dashboard"
GITHUB_BRANCH= "main"
DATA_FILE    = "data/signals_latest.csv.gz"

# ── Macro tickers (yfinance) ────────────────────────────────────────────────
MACRO_YF = {
    "^GSPC":  "S&P500",
    "^IXIC":  "NASDAQ",
    "^VIX":   "VIX",
    "DX-Y.NYB":"DXY",
    "CL=F":   "WTI",
    "HG=F":   "Copper",
    "^KS11":  "KOSPI",
    "^KQ11":  "KOSDAQ",
    "KRW=X":  "USD/KRW",
}
