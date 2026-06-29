# data_collector.py v4
import time, requests, warnings, re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import yfinance as yf

try:
    import FinanceDataReader as fdr
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "finance-datareader"])
    import FinanceDataReader as fdr

from config import KST, MACRO_YF
warnings.filterwarnings("ignore")

NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

def get_fdr_ohlcv(ticker, lookback_days=130):
    today = datetime.now(KST)
    start = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    try:
        df = fdr.DataReader(ticker, start=start)
        if df.empty: return pd.DataFrame()
        df.index = pd.to_datetime(df.index)
        df.columns = [c.lower() for c in df.columns]
        keep = [c for c in ["open","high","low","close","volume"] if c in df.columns]
        return df[keep].dropna()
    except Exception as e:
        print(f"[FDR] {ticker}: {e}")
        return pd.DataFrame()

def _naver_get(url):
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=10)
        r.raise_for_status()
        r.encoding = "euc-kr"
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[Naver GET] {url}: {e}")
        return None

def get_naver_current_price(ticker):
    soup = _naver_get(f"https://finance.naver.com/item/main.naver?code={ticker}")
    result = {}
    if not soup: return result
    try:
        # 현재가
        for tag in soup.select("span.blind"):
            txt = tag.get_text(strip=True).replace(",","")
            if txt.isdigit() and 100 < int(txt) < 10000000:
                result["current_price"] = int(txt)
                break
        # 52주 고저
        rwidth = soup.select_one("table.rwidth")
        if rwidth:
            nums = [int(n.replace(",","")) for n in re.findall(r"[\d,]+", rwidth.get_text()) if int(n.replace(",","")) > 100]
            if len(nums) >= 2:
                result["high_52w"] = max(nums)
                result["low_52w"]  = min(nums)
        # PER — per_table의 첫 번째 td 숫자값
        per_tbl = soup.select_one("table.per_table")
        if per_tbl:
            for td in per_tbl.select("td"):
                v = td.get_text(strip=True).replace(",","").replace("배","")
                try:
                    val = float(v)
                    # PER은 0~500 범위여야 함 (연도값 2026 등 필터)
                    if 0 < val < 500:
                        result["PER"] = val
                        break
                except: continue
        # 외국인 보유비율
        lwidth = soup.select_one("table.lwidth")
        if lwidth:
            m = re.search(r"([\d.]+)%", lwidth.get_text())
            if m: result["foreign_ratio"] = float(m.group(1))
    except Exception as e:
        print(f"[Naver Price] {ticker}: {e}")
    return result

def get_naver_investor_flow(ticker):
    """
    frgn 페이지 rows=33 테이블
    컬럼: 날짜[0] 종가[1] 등락[2] 등락률[3] 거래량[4] 외국인순매수[5] 기관순매수[6] 보유수[7] 보유율[8]
    """
    soup = _naver_get(f"https://finance.naver.com/item/frgn.naver?code={ticker}")
    if not soup: return pd.DataFrame()
    try:
        rows_data = []
        tables = soup.select("table.type2")
        target = None
        for tbl in tables:
            if len(tbl.select("tr")) > 20:
                target = tbl
                break
        if not target: return pd.DataFrame()

        for tr in target.select("tr"):
            tds = tr.select("td")
            if len(tds) < 7: continue
            date_str = tds[0].get_text(strip=True)
            if not date_str or "." not in date_str: continue
            try:
                date = pd.to_datetime(date_str.replace(".","-"))
                def pn(s):
                    s = s.replace(",","").replace("+","").strip()
                    return float(s) if s and s != "-" and s != "" else 0.0
                foreign_net = pn(tds[5].get_text(strip=True))  # 외국인순매수
                inst_net    = pn(tds[6].get_text(strip=True))  # 기관순매수
                hold_ratio  = pn(tds[8].get_text(strip=True).replace("%",""))
                rows_data.append({
                    "date": date,
                    "foreign": foreign_net,
                    "institutional": inst_net,
                    "foreign_ratio": hold_ratio,
                })
            except: continue

        if not rows_data: return pd.DataFrame()
        df = pd.DataFrame(rows_data).set_index("date").sort_index()
        return df
    except Exception as e:
        print(f"[Naver Investor] {ticker}: {e}")
        return pd.DataFrame()

def get_naver_financials(ticker):
    """
    main.naver th 클래스명으로 재무지표 수집
    th_cop_anal13 = ROE
    th_cop_anal11 = 영업이익률
    th_cop_anal14 = 부채비율
    th_cop_anal15 = 유동비율
    """
    try:
        r = requests.get(
            f"https://finance.naver.com/item/main.naver?code={ticker}",
            headers=NAVER_HEADERS, timeout=10
        )
        r.encoding = "cp949"
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[Naver Fin GET] {ticker}: {e}")
        return {}

    result = {}
    # th 클래스 → 지표명 매핑
    CLASS_MAP = {
        "th_cop_anal11": "operating_margin",  # 영업이익률
        "th_cop_anal12": "net_margin",         # 당기순이익률
        "th_cop_anal13": "ROE",                # ROE
        "th_cop_anal14": "debt_ratio",         # 부채비율
        "th_cop_anal15": "current_ratio",      # 유동비율
        "th_cop_anal9":  "revenue",            # 매출액
        "th_cop_anal10": "operating_profit",   # 영업이익
    }
    try:
        for cls, key in CLASS_MAP.items():
            th = soup.select_one(f"th.{cls}")
            if not th: continue
            tr = th.find_parent("tr")
            if not tr: continue
            tds = tr.select("td")
            # 첫 번째 유효한 숫자값 (가장 최근 연도)
            for td in tds:
                v = td.get_text(strip=True).replace(",","")
                try:
                    result[key] = float(v)
                    break
                except: continue
    except Exception as e:
        print(f"[Naver Fin] {ticker}: {e}")
    return result

def get_yf_ohlcv(ticker, period="6mo"):
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty: return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        keep = [c for c in ["open","high","low","close","volume"] if c in df.columns]
        return df[keep].dropna()
    except Exception as e:
        print(f"[yf] {ticker}: {e}")
        return pd.DataFrame()

def get_macro_snapshot():
    snap = {}
    for sym, name in MACRO_YF.items():
        try:
            hist = yf.Ticker(sym).history(period="5d")
            if hist.empty: continue
            latest = float(hist["Close"].iloc[-1])
            prev   = float(hist["Close"].iloc[-2]) if len(hist) > 1 else latest
            snap[name] = {"value": round(latest,4), "chg_pct": round((latest-prev)/prev*100,2) if prev else 0}
        except Exception as e:
            print(f"[Macro] {sym}: {e}")
    return snap

def collect_stock_data(ticker, is_krx=True):
    data = {"ticker": ticker, "is_krx": is_krx}
    if is_krx:
        data["ohlcv"]        = get_fdr_ohlcv(ticker)
        nv_price             = get_naver_current_price(ticker)
        nv_fin               = get_naver_financials(ticker)
        data["fundamental"]  = {"PER": nv_price.get("PER",0), "PBR": nv_price.get("PBR",0)}
        data["naver"]        = {**nv_price, **nv_fin}
        data["investor"]     = get_naver_investor_flow(ticker)
        data["foreign_ratio"]= nv_price.get("foreign_ratio", 0.0)
        time.sleep(0.5)
    else:
        data["ohlcv"]        = get_yf_ohlcv(ticker)
        data["fundamental"]  = {}
        data["investor"]     = pd.DataFrame()
        data["naver"]        = {}
        data["foreign_ratio"]= 0.0
    return data

def collect_all(watchlist):
    results = {}
    krx_list = [t for t in watchlist if t.isdigit()]
    yf_list  = [t for t in watchlist if not t.isdigit()]
    print(f"[수집] KRX {len(krx_list)}개 + yfinance {len(yf_list)}개")
    for i, ticker in enumerate(krx_list, 1):
        print(f"  [{i}/{len(krx_list)}] {ticker} {watchlist[ticker]}", end=" ")
        results[ticker] = collect_stock_data(ticker, is_krx=True)
        ohlcv = results[ticker]["ohlcv"]
        inv   = results[ticker]["investor"]
        price = results[ticker]["naver"].get("current_price","?")
        per   = results[ticker]["fundamental"].get("PER","?")
        print(f"→ OHLCV {len(ohlcv)}행 | 현재가 {price} | PER {per} | 수급 {len(inv)}행")
    for ticker in yf_list:
        print(f"  [yf] {ticker} {watchlist[ticker]}", end=" ")
        results[ticker] = collect_stock_data(ticker, is_krx=False)
        print(f"→ {len(results[ticker]['ohlcv'])}행")
    return results
