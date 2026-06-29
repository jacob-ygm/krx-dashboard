# config.py
import pytz

KST = pytz.timezone("Asia/Seoul")

# ── KOSPI 워치리스트 ────────────────────────────────────────────────────────
KOSPI_WATCHLIST = {
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
    "263750": "펄어비스",
    "112040": "위메이드",
}

# ── S&P 500 Top 50 ──────────────────────────────────────────────────────────
SP500_TOP50 = {
    "AAPL":  "Apple",
    "MSFT":  "Microsoft",
    "NVDA":  "NVIDIA",
    "AMZN":  "Amazon",
    "GOOGL": "Alphabet A",
    "META":  "Meta",
    "BRK-B": "Berkshire Hathaway",
    "LLY":   "Eli Lilly",
    "AVGO":  "Broadcom",
    "TSLA":  "Tesla",
    "JPM":   "JPMorgan Chase",
    "WMT":   "Walmart",
    "V":     "Visa",
    "UNH":   "UnitedHealth",
    "XOM":   "ExxonMobil",
    "ORCL":  "Oracle",
    "MA":    "Mastercard",
    "COST":  "Costco",
    "HD":    "Home Depot",
    "PG":    "Procter & Gamble",
    "JNJ":   "Johnson & Johnson",
    "ABBV":  "AbbVie",
    "BAC":   "Bank of America",
    "KO":    "Coca-Cola",
    "NFLX":  "Netflix",
    "CRM":   "Salesforce",
    "CVX":   "Chevron",
    "MRK":   "Merck",
    "AMD":   "AMD",
    "ACN":   "Accenture",
    "PEP":   "PepsiCo",
    "TMO":   "Thermo Fisher",
    "LIN":   "Linde",
    "MCD":   "McDonald's",
    "CSCO":  "Cisco",
    "ABT":   "Abbott",
    "GE":    "GE Aerospace",
    "IBM":   "IBM",
    "TXN":   "Texas Instruments",
    "INTU":  "Intuit",
    "AMGN":  "Amgen",
    "PM":    "Philip Morris",
    "RTX":   "RTX Corp",
    "SPGI":  "S&P Global",
    "GS":    "Goldman Sachs",
    "CAT":   "Caterpillar",
    "NOW":   "ServiceNow",
    "BKNG":  "Booking Holdings",
    "DHR":   "Danaher",
    "BLK":   "BlackRock",
}

# ── NASDAQ Top 50 (SP500 미포함) ─────────────────────────────────────────────
NASDAQ_TOP50 = {
    "ADBE":  "Adobe",
    "QCOM":  "Qualcomm",
    "AMAT":  "Applied Materials",
    "MU":    "Micron",
    "LRCX":  "Lam Research",
    "KLAC":  "KLA Corp",
    "SNPS":  "Synopsys",
    "CDNS":  "Cadence Design",
    "MRVL":  "Marvell Tech",
    "FTNT":  "Fortinet",
    "PANW":  "Palo Alto Networks",
    "CRWD":  "CrowdStrike",
    "SNOW":  "Snowflake",
    "DDOG":  "Datadog",
    "ZS":    "Zscaler",
    "WDAY":  "Workday",
    "TEAM":  "Atlassian",
    "MELI":  "MercadoLibre",
    "ASML":  "ASML",
    "AZN":   "AstraZeneca",
    "GILD":  "Gilead Sciences",
    "VRTX":  "Vertex Pharma",
    "REGN":  "Regeneron",
    "BIIB":  "Biogen",
    "IDXX":  "IDEXX Labs",
    "ILMN":  "Illumina",
    "ALGN":  "Align Technology",
    "DXCM":  "DexCom",
    
    
    "TTD":   "The Trade Desk",
    "ROKU":  "Roku",
    "ZM":    "Zoom",
    "DOCU":  "DocuSign",
    "PTON":  "Peloton",
    "LYFT":  "Lyft",
    "UBER":  "Uber",
    "ABNB":  "Airbnb",
    "DASH":  "DoorDash",
    "COIN":  "Coinbase",
    "HOOD":  "Robinhood",
    "RBLX":  "Roblox",
    "U":     "Unity Software",
    "PATH":  "UiPath",
    "AI":    "C3.ai",
    "PLTR":  "Palantir",
    "SOFI":  "SoFi Technologies",
    "AFRM":  "Affirm",
    "LCID":  "Lucid Motors",
    "RIVN":  "Rivian",
}

# ── ETF (매크로 참조용) ──────────────────────────────────────────────────────
ETF_WATCHLIST = {
    "SPY":  "S&P500 ETF",
    "QQQ":  "NASDAQ ETF",
    "SOXL": "반도체 3x ETF",
    "TLT":  "미국장기채 ETF",
}

# ── 전체 통합 ────────────────────────────────────────────────────────────────
WATCHLIST = {**KOSPI_WATCHLIST, **SP500_TOP50, **NASDAQ_TOP50, **ETF_WATCHLIST}

KRX_TICKERS = [t for t in WATCHLIST if t.isdigit()]
YF_TICKERS  = [t for t in WATCHLIST if not t.isdigit()]

# ── Signal weights ───────────────────────────────────────────────────────────
WEIGHTS = {
    "macro":         0.25,
    "fundamental":   0.20,
    "supply_demand": 0.20,
    "technical":     0.20,
    "momentum":      0.15,
}

# ── Signal thresholds ────────────────────────────────────────────────────────
SIGNAL_BANDS = [
    (75, 100, "STRONG BUY"),
    (58,  75, "BUY"),
    (43,  58, "HOLD"),
    (28,  43, "SELL"),
    (  0, 28, "STRONG SELL"),
]

CONFIDENCE_BANDS = [
    (70, "HIGH"),
    (45, "MEDIUM"),
    (0,  "LOW"),
]

# ── GitHub ───────────────────────────────────────────────────────────────────
GITHUB_REPO   = "jacob-ygm/krx-dashboard"
GITHUB_BRANCH = "main"
DATA_FILE     = "data/signals_latest.csv.gz"

# ── Macro tickers (yfinance) ─────────────────────────────────────────────────
MACRO_YF = {
    "^GSPC":   "S&P500",
    "^IXIC":   "NASDAQ",
    "^VIX":    "VIX",
    "DX-Y.NYB":"DXY",
    "CL=F":    "WTI",
    "HG=F":    "Copper",
    "^KS11":   "KOSPI",
    "^KQ11":   "KOSDAQ",
    "KRW=X":   "USD/KRW",
}
