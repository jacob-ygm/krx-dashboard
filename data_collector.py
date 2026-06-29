# data_collector.py
"""
데이터 수집 모듈
- KRX 주가/거래량: pykrx
- 글로벌 매크로: yfinance
- 수급/재무: Naver Finance 스크래핑
"""

import time
import requests
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

import yfinance as yf
from pykrx import stock as krx

from config import KST, KRX_TICKERS, YF_TICKERS, MACRO_YF

warnings.filterwarnings("ignore")


# ────────────────────────────────────────────────────────────────────────────
# 1. KRX 주가 데이터
# ────────────────────────────────────────────────────────────────────────────

def get_krx_ohlcv(ticker: str, lookback_days: int = 130) -> pd.DataFrame:
    """pykrx로 OHLCV 수집 (KST 기준)"""
    today = datetime.now(KST)
    start = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end   = today.strftime("%Y%m%d")
    try:
        df = krx.get_market_ohlcv_by_date(start, end, ticker)
        df.index = pd.to_datetime(df.index)
        df.columns = ["open","high","low","close","volume","trading_value","fluctuation"]
        return df.dropna()
    except Exception as e:
        print(f"[KRX OHLCV] {ticker} 오류: {e}")
        return pd.DataFrame()


def get_krx_fundamental(ticker: str) -> dict:
    """pykrx로 PER, PBR, 배당수익률 수집"""
    today = datetime.now(KST).strftime("%Y%m%d")
    try:
        df = krx.get_market_fundamental(today, today, ticker)
        if df.empty:
            # T-1 시도
            yesterday = (datetime.now(KST) - timedelta(days=1)).strftime("%Y%m%d")
            df = krx.get_market_fundamental(yesterday, yesterday, ticker)
        if df.empty:
            return {}
        row = df.iloc[-1]
        return {
            "PER":   round(float(row.get("PER", 0) or 0), 2),
            "PBR":   round(float(row.get("PBR", 0) or 0), 2),
            "DIV":   round(float(row.get("DIV", 0) or 0), 2),
            "EPS":   round(float(row.get("EPS", 0) or 0), 0),
            "BPS":   round(float(row.get("BPS", 0) or 0), 0),
        }
    except Exception as e:
        print(f"[KRX Fundamental] {ticker} 오류: {e}")
        return {}


def get_krx_investor_flow(ticker: str, lookback_days: int = 20) -> pd.DataFrame:
    """pykrx 투자자별 매매동향 (외국인/기관/개인)"""
    today = datetime.now(KST)
    start = (today - timedelta(days=lookback_days)).strftime("%Y%m%d")
    end   = today.strftime("%Y%m%d")
    try:
        df = krx.get_market_trading_value_by_date(start, end, ticker)
        df.index = pd.to_datetime(df.index)
        # 컬럼: 기관합계, 기타법인, 개인, 외국인합계, 전체
        col_map = {}
        for c in df.columns:
            if "외국인" in c: col_map[c] = "foreign"
            elif "기관" in c: col_map[c] = "institutional"
            elif "개인" in c: col_map[c] = "retail"
        df = df.rename(columns=col_map)
        keep = [c for c in ["foreign","institutional","retail"] if c in df.columns]
        return df[keep].dropna()
    except Exception as e:
        print(f"[KRX Investor] {ticker} 오류: {e}")
        return pd.DataFrame()


# ────────────────────────────────────────────────────────────────────────────
# 2. Naver Finance 스크래핑 (수급 + 재무)
# ────────────────────────────────────────────────────────────────────────────

NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def _naver_get(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=NAVER_HEADERS, timeout=10)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"[Naver] GET 오류 {url}: {e}")
        return None


def get_naver_summary(ticker: str) -> dict:
    """Naver Finance 종목 요약 (시가총액, 52주 고저, 거래대금 등)"""
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    soup = _naver_get(url)
    if not soup:
        return {}
    result = {}
    try:
        # 현재가
        price_tag = soup.select_one("p.no_today span.blind")
        if price_tag:
            result["current_price"] = int(price_tag.text.replace(",",""))
        # 시가총액, 거래대금 등 (dl.blind 또는 테이블)
        for dl in soup.select("div.sub_section dl"):
            key_tag = dl.select_one("dt")
            val_tag = dl.select_one("dd")
            if key_tag and val_tag:
                k = key_tag.text.strip()
                v = val_tag.text.strip().replace(",","").replace("억","").strip()
                if "시가총액" in k:
                    try: result["market_cap_100m"] = float(v)
                    except: pass
                elif "52주" in k and "최고" in k:
                    try: result["high_52w"] = float(v)
                    except: pass
                elif "52주" in k and "최저" in k:
                    try: result["low_52w"] = float(v)
                    except: pass
    except Exception as e:
        print(f"[Naver Summary] {ticker}: {e}")
    return result


def get_naver_foreigner_ratio(ticker: str) -> float:
    """Naver Finance 외국인 보유비율(%)"""
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    soup = _naver_get(url)
    if not soup:
        return 0.0
    try:
        # "외국인" 포함 span 찾기
        for tag in soup.select("em"):
            parent = tag.find_parent()
            if parent and "외국인" in parent.get_text():
                txt = tag.text.strip().replace("%","")
                return float(txt)
    except:
        pass
    return 0.0


def get_naver_financials(ticker: str) -> dict:
    """Naver Finance 재무제표 페이지에서 ROE, 영업이익률 등"""
    url = f"https://finance.naver.com/item/coinfo.naver?code={ticker}&target=finsum_more"
    soup = _naver_get(url)
    result = {}
    if not soup:
        return result
    try:
        tables = soup.select("table.tb_type1")
        for tbl in tables:
            rows = tbl.select("tr")
            for row in rows:
                th = row.select_one("th")
                tds = row.select("td")
                if not th or not tds:
                    continue
                label = th.text.strip()
                vals = [td.text.strip().replace(",","") for td in tds]
                # 가장 최근 컬럼(마지막)
                latest = None
                for v in reversed(vals):
                    try:
                        latest = float(v)
                        break
                    except:
                        continue
                if latest is None:
                    continue
                if "ROE" in label:
                    result["ROE"] = latest
                elif "영업이익률" in label:
                    result["operating_margin"] = latest
                elif "부채비율" in label:
                    result["debt_ratio"] = latest
                elif "유동비율" in label:
                    result["current_ratio"] = latest
    except Exception as e:
        print(f"[Naver Financials] {ticker}: {e}")
    return result


# ────────────────────────────────────────────────────────────────────────────
# 3. yfinance 글로벌 매크로
# ────────────────────────────────────────────────────────────────────────────

def get_yf_ohlcv(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """yfinance OHLCV"""
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        df.columns = [c.lower() for c in df.columns]
        return df[["open","high","low","close","volume"]].dropna()
    except Exception as e:
        print(f"[yfinance] {ticker}: {e}")
        return pd.DataFrame()


def get_macro_snapshot() -> dict:
    """매크로 지표 현재값 딕셔너리"""
    snap = {}
    for sym, name in MACRO_YF.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="5d")
            if hist.empty:
                continue
            latest = float(hist["Close"].iloc[-1])
            prev   = float(hist["Close"].iloc[-2]) if len(hist) > 1 else latest
            snap[name] = {
                "value":  round(latest, 4),
                "chg_pct": round((latest - prev) / prev * 100, 2) if prev else 0,
            }
        except Exception as e:
            print(f"[Macro] {sym} ({name}): {e}")
    return snap


# ────────────────────────────────────────────────────────────────────────────
# 4. 통합 수집 함수
# ────────────────────────────────────────────────────────────────────────────

def collect_stock_data(ticker: str, is_krx: bool = True) -> dict:
    """단일 종목 데이터 전체 수집"""
    data = {"ticker": ticker, "is_krx": is_krx}

    if is_krx:
        data["ohlcv"]       = get_krx_ohlcv(ticker)
        data["fundamental"] = get_krx_fundamental(ticker)
        data["investor"]    = get_krx_investor_flow(ticker)
        nv_sum              = get_naver_summary(ticker)
        nv_fin              = get_naver_financials(ticker)
        data["naver"]       = {**nv_sum, **nv_fin}
        data["foreign_ratio"] = get_naver_foreigner_ratio(ticker)
        time.sleep(0.3)   # Naver 부하 방지
    else:
        df = get_yf_ohlcv(ticker)
        data["ohlcv"] = df
        data["fundamental"] = {}
        data["investor"]    = pd.DataFrame()
        data["naver"]       = {}

    return data


def collect_all(watchlist: dict) -> dict:
    """전체 워치리스트 수집"""
    results = {}
    krx_tickers = [t for t in watchlist if t.isdigit()]
    yf_tickers  = [t for t in watchlist if not t.isdigit()]

    print(f"[수집] KRX {len(krx_tickers)}개 + yfinance {len(yf_tickers)}개")

    for i, ticker in enumerate(krx_tickers, 1):
        print(f"  [{i}/{len(krx_tickers)}] KRX {ticker} {watchlist[ticker]}")
        results[ticker] = collect_stock_data(ticker, is_krx=True)

    for ticker in yf_tickers:
        print(f"  [yf] {ticker} {watchlist[ticker]}")
        results[ticker] = collect_stock_data(ticker, is_krx=False)

    return results
