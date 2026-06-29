# data_collector.py v2 - FinanceDataReader 기반
import time, requests, warnings
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
        tag = soup.select_one("strong#_nowVal")
        if tag:
            result["current_price"] = int(tag.text.strip().replace(",",""))
        for tr in soup.select("table.no_info tr"):
            tds = tr.select("td")
            for i in range(0, len(tds)-1, 2):
                key = tds[i].get_text(strip=True)
                val = tds[i+1].get_text(strip=True).replace(",","").replace("억원","").strip()
                if "PER" in key:
                    try: result["PER"] = float(val.replace("배",""))
                    except: pass
                elif "PBR" in key:
                    try: result["PBR"] = float(val.replace("배",""))
                    except: pass
    except Exception as e:
        print(f"[Naver Price] {ticker}: {e}")
    return result

def get_naver_investor_flow(ticker):
    soup = _naver_get(f"https://finance.naver.com/item/frgn.naver?code={ticker}")
    if not soup: return pd.DataFrame()
    try:
        rows = []
        table = soup.select_one("table.type2")
        if not table: return pd.DataFrame()
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) < 5: continue
            date_str = tds[0].get_text(strip=True).replace(".","-")
            if not date_str or len(date_str) < 8: continue
            try:
                def pn(s): s=s.replace(",","").replace("+","").strip(); return float(s) if s and s!="-" else 0.0
                rows.append({"date": pd.to_datetime(date_str), "foreign": pn(tds[3].get_text(strip=True))})
            except: continue
        if not rows: return pd.DataFrame()
        return pd.DataFrame(rows).set_index("date").sort_index()
    except Exception as e:
        print(f"[Naver Investor] {ticker}: {e}")
        return pd.DataFrame()

def get_naver_financials(ticker):
    soup = _naver_get(f"https://finance.naver.com/item/coinfo.naver?code={ticker}&target=finsum_more")
    result = {}
    if not soup: return result
    try:
        for tbl in soup.select("table.tb_type1"):
            for row in tbl.select("tr"):
                th = row.select_one("th")
                tds = row.select("td")
                if not th or not tds: continue
                label = th.get_text(strip=True)
                latest = None
                for td in reversed(tds):
                    v = td.get_text(strip=True).replace(",","")
                    try: latest = float(v); break
                    except: continue
                if latest is None: continue
                if "ROE" in label: result["ROE"] = latest
                elif "영업이익률" in label: result["operating_margin"] = latest
                elif "부채비율" in label: result["debt_ratio"] = latest
                elif "유동비율" in label: result["current_ratio"] = latest
    except Exception as e:
        print(f"[Naver Fin] {ticker}: {e}")
    return result

def get_naver_foreign_ratio(ticker):
    soup = _naver_get(f"https://finance.naver.com/item/frgn.naver?code={ticker}")
    if not soup: return 0.0
    try:
        table = soup.select_one("table.type2")
        if table:
            trs = table.select("tr")
            if len(trs) > 1:
                tds = trs[1].select("td")
                if len(tds) >= 6:
                    return float(tds[5].get_text(strip=True).replace("%",""))
    except: pass
    return 0.0

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
        data["ohlcv"]         = get_fdr_ohlcv(ticker)
        nv_price              = get_naver_current_price(ticker)
        nv_fin                = get_naver_financials(ticker)
        data["fundamental"]   = {"PER": nv_price.get("PER",0), "PBR": nv_price.get("PBR",0)}
        data["naver"]         = {**nv_price, **nv_fin}
        data["investor"]      = get_naver_investor_flow(ticker)
        data["foreign_ratio"] = get_naver_foreign_ratio(ticker)
        time.sleep(0.5)
    else:
        data["ohlcv"]         = get_yf_ohlcv(ticker)
        data["fundamental"]   = {}
        data["investor"]      = pd.DataFrame()
        data["naver"]         = {}
        data["foreign_ratio"] = 0.0
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
        print(f"→ {len(ohlcv)}행" if not ohlcv.empty else "→ OHLCV 없음")
    for ticker in yf_list:
        print(f"  [yf] {ticker} {watchlist[ticker]}", end=" ")
        results[ticker] = collect_stock_data(ticker, is_krx=False)
        ohlcv = results[ticker]["ohlcv"]
        print(f"→ {len(ohlcv)}행" if not ohlcv.empty else "→ 없음")
    return results
