# digital_twin.py
import os, sys, time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import pytz
import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
try:
    import FinanceDataReader as fdr
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable,"-m","pip","install","-q","finance-datareader"])
    import FinanceDataReader as fdr

from scipy.optimize import minimize
KST = pytz.timezone("Asia/Seoul")

def fetch_historical_ohlcv(ticker, is_krx, years=2):
    start = (datetime.now(KST) - timedelta(days=365*years)).strftime("%Y-%m-%d")
    try:
        if is_krx:
            df = fdr.DataReader(ticker, start=start)
        else:
            df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
        if df.empty: return pd.DataFrame()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.columns = [c.lower() for c in df.columns]
        keep = [c for c in ["open","high","low","close","volume"] if c in df.columns]
        return df[keep].dropna()
    except:
        return pd.DataFrame()

def fetch_historical_investor(ticker, pages=5):
    import requests
    from bs4 import BeautifulSoup
    headers = {"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0 Safari/537.36", "Referer": "https://finance.naver.com"}
    rows_data = []
    for page in range(1, pages+1):
        try:
            url = "https://finance.naver.com/item/frgn.naver?code=" + ticker + "&page=" + str(page)
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = "euc-kr"
            soup = BeautifulSoup(r.text, "html.parser")
            tables = soup.select("table.type2")
            target = None
            for tbl in tables:
                if len(tbl.select("tr")) > 20:
                    target = tbl
                    break
            if not target: break
            for tr in target.select("tr"):
                tds = tr.select("td")
                if len(tds) < 7: continue
                date_str = tds[0].get_text(strip=True)
                if not date_str or "." not in date_str: continue
                try:
                    date = pd.to_datetime(date_str.replace(".","-"))
                    def pn(s):
                        s = s.replace(",","").replace("+","").strip()
                        return float(s) if s and s != "-" else 0.0
                    rows_data.append({
                        "date": date,
                        "foreign": pn(tds[5].get_text(strip=True)),
                        "institutional": pn(tds[6].get_text(strip=True))
                    })
                except: continue
            time.sleep(0.3)
        except: break
    if not rows_data: return pd.DataFrame()
    df = pd.DataFrame(rows_data).set_index("date").sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[~df.index.duplicated()]

def collect_historical_data(watchlist, years=2, save_path="/content/historical_data.pkl"):
    import pickle
    if os.path.exists(save_path):
        print("기존 데이터 로드: " + save_path)
        with open(save_path, "rb") as f:
            return pickle.load(f)
    historical = {}
    krx_list = [t for t in watchlist if t.isdigit()]
    yf_list  = [t for t in watchlist if not t.isdigit()]
    print("과거 " + str(years) + "년치 수집: KRX " + str(len(krx_list)) + "개 + yf " + str(len(yf_list)) + "개")
    for i, ticker in enumerate(krx_list, 1):
        print("  [" + str(i) + "/" + str(len(krx_list)) + "] " + ticker + " " + watchlist[ticker], end=" ")
        ohlcv    = fetch_historical_ohlcv(ticker, is_krx=True, years=years)
        investor = fetch_historical_investor(ticker, pages=8)
        historical[ticker] = {"ohlcv": ohlcv, "investor": investor}
        print("-> OHLCV " + str(len(ohlcv)) + "행 | 수급 " + str(len(investor)) + "행")
        time.sleep(0.4)
    for ticker in yf_list:
        print("  [yf] " + ticker, end=" ")
        ohlcv = fetch_historical_ohlcv(ticker, is_krx=False, years=years)
        historical[ticker] = {"ohlcv": ohlcv, "investor": pd.DataFrame()}
        print("-> " + str(len(ohlcv)) + "행")
    with open(save_path, "wb") as f:
        pickle.dump(historical, f)
    print("저장 완료: " + save_path)
    return historical

def fetch_macro_history(years=2):
    MACRO_SYMBOLS = {
        "^GSPC":"S&P500","^IXIC":"NASDAQ","^VIX":"VIX",
        "DX-Y.NYB":"DXY","CL=F":"WTI","HG=F":"Copper",
        "^KS11":"KOSPI","KRW=X":"USD/KRW",
    }
    start = (datetime.now(KST) - timedelta(days=365*years)).strftime("%Y-%m-%d")
    macro_cache = {}
    for sym, name in MACRO_SYMBOLS.items():
        try:
            df = yf.download(sym, start=start, progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            macro_cache[name] = df[["close"]].dropna()
            print("  매크로 " + name + ": " + str(len(df)) + "행")
        except Exception as e:
            print("  매크로 " + name + " 오류: " + str(e))
    return macro_cache

def get_macro_on_date(date_str, macro_cache):
    snap = {}
    date = pd.Timestamp(date_str)
    for name, df in macro_cache.items():
        if df.empty: continue
        rows = df[df.index <= date]
        if rows.empty: continue
        latest = float(rows["close"].iloc[-1])
        prev   = float(rows["close"].iloc[-2]) if len(rows) > 1 else latest
        snap[name] = {
            "value": round(latest,4),
            "chg_pct": round((latest-prev)/prev*100,2) if prev else 0
        }
    return snap

def simulate_signals_on_date(date_str, historical, watchlist, macro_snap, weights, lookback=120):
    from signal_engine import calc_indicators, score_macro, score_fundamental, score_supply_demand, score_technical, score_momentum
    from config import SIGNAL_BANDS
    date = pd.Timestamp(date_str)
    rows = []
    for ticker, name in watchlist.items():
        data     = historical.get(ticker, {})
        ohlcv    = data.get("ohlcv", pd.DataFrame())
        investor = data.get("investor", pd.DataFrame())
        if ohlcv.empty: continue
        hist = ohlcv[ohlcv.index <= date].tail(lookback)
        if len(hist) < 20: continue
        inv_hist = investor[investor.index <= date].tail(20) if not investor.empty else pd.DataFrame()
        ind = calc_indicators(hist)
        if not ind: continue
        s_mac, _ = score_macro(macro_snap)
        s_fun, _ = score_fundamental({}, {})
        s_snd, _ = score_supply_demand(inv_hist, 0)
        s_tec, _ = score_technical(ind)
        s_mom, _ = score_momentum(ind, macro_snap)
        overall = (
            s_mac/25*100*weights["macro"] +
            s_fun/20*100*weights["fundamental"] +
            s_snd/20*100*weights["supply_demand"] +
            s_tec/20*100*weights["technical"] +
            s_mom/15*100*weights["momentum"]
        )
        signal = "HOLD"
        for lo, hi, label in SIGNAL_BANDS:
            if lo <= overall <= hi:
                signal = label
                break
        rows.append({
            "date": date_str, "ticker": ticker, "name": name,
            "signal": signal, "score": round(overall,1),
            "s_mac": s_mac, "s_fun": s_fun, "s_snd": s_snd,
            "s_tec": s_tec, "s_mom": s_mom,
            "price": ind.get("current_price", 0)
        })
    return pd.DataFrame(rows)

def calc_forward_returns(signal_df, historical, holding_days_list=[5,20]):
    results = []
    for _, row in signal_df.iterrows():
        if row["signal"] not in ("STRONG BUY","BUY","SELL","STRONG SELL"): continue
        ticker  = row["ticker"]
        date    = pd.Timestamp(row["date"])
        is_buy  = row["signal"] in ("STRONG BUY","BUY")
        ohlcv   = historical.get(ticker,{}).get("ohlcv", pd.DataFrame())
        if ohlcv.empty: continue
        future     = ohlcv[ohlcv.index > date]
        entry_rows = ohlcv[ohlcv.index >= date]
        if entry_rows.empty: continue
        entry_price = float(entry_rows["close"].iloc[0])
        ret_dict = {
            "date": row["date"], "ticker": ticker, "name": row["name"],
            "signal": row["signal"], "score": row["score"],
            "s_mac": row["s_mac"], "s_fun": row["s_fun"],
            "s_snd": row["s_snd"], "s_tec": row["s_tec"], "s_mom": row["s_mom"],
            "entry_price": entry_price
        }
        for n in holding_days_list:
            if len(future) >= n:
                exit_price = float(future["close"].iloc[n-1])
                raw_ret    = (exit_price - entry_price) / entry_price * 100
                actual_ret = raw_ret if is_buy else -raw_ret
                ret_dict["ret_" + str(n) + "d"]     = round(actual_ret, 2)
                ret_dict["correct_" + str(n) + "d"] = actual_ret > 0
            else:
                ret_dict["ret_" + str(n) + "d"]     = None
                ret_dict["correct_" + str(n) + "d"] = None
        results.append(ret_dict)
    return pd.DataFrame(results) if results else pd.DataFrame()

def optimize_weights(result_df, holding_days=5, method="sharpe"):
    ret_col = "ret_" + str(holding_days) + "d"
    valid = result_df[result_df[ret_col].notna()].copy()
    if len(valid) < 20:
        print("최적화 데이터 부족 (최소 20건)")
        return None
    score_cols = ["s_mac","s_fun","s_snd","s_tec","s_mom"]
    max_vals   = [25, 20, 20, 20, 15]
    for col, mx in zip(score_cols, max_vals):
        valid[col + "_norm"] = valid[col] / mx
    def neg_obj(w):
        w = np.array(w)
        w = w / w.sum()
        norm_cols = [c + "_norm" for c in score_cols]
        scores = valid[norm_cols].values @ w * 100
        is_buy  = (scores >= 55) & valid["signal"].isin(["STRONG BUY","BUY"])
        is_sell = (scores <= 43) & valid["signal"].isin(["SELL","STRONG SELL"])
        active  = is_buy | is_sell
        if active.sum() < 5: return 0
        rets = valid.loc[active, ret_col]
        if method == "sharpe":
            mu, std = rets.mean(), rets.std()
            return -(mu/std*(252/holding_days)**0.5) if std > 0 else 0
        return -(rets > 0).mean()
    w0 = np.array([0.25,0.20,0.20,0.20,0.15])
    constraints = {"type":"eq","fun":lambda w: np.sum(w)-1}
    bounds = [(0.05,0.50)]*5
    res = minimize(neg_obj, w0, method="SLSQP", bounds=bounds, constraints=constraints, options={"maxiter":1000})
    if res.success:
        w_opt = res.x / res.x.sum()
        return {
            "macro":         round(float(w_opt[0]),3),
            "fundamental":   round(float(w_opt[1]),3),
            "supply_demand": round(float(w_opt[2]),3),
            "technical":     round(float(w_opt[3]),3),
            "momentum":      round(float(w_opt[4]),3)
        }
    print("최적화 실패: " + str(res.message))
    return None

def update_config_weights(new_weights):
    import re, subprocess
    content = open("/content/repo/config.py").read()
    new_w_str = "WEIGHTS = {\n"
    for k, v in new_weights.items():
        new_w_str += '    "' + k + '":         ' + str(v) + ",\n"
    new_w_str += "}"
    content = re.sub(r"WEIGHTS = \{.*?\}", new_w_str, content, flags=re.DOTALL)
    open("/content/repo/config.py","w").write(content)
    print("가중치 업데이트: " + str(new_weights))
    import os
    os.chdir("/content/repo")
    os.system("git add config.py && git commit -m 'auto: Digital Twin 가중치 최적화' && git push origin main --force")

def run_digital_twin(watchlist, years=2, sim_interval_days=5, holding_days_list=[5,20], save_path="/content/historical_data.pkl"):
    from config import WEIGHTS
    print("\n" + "="*60)
    print("  Digital Twin 시뮬레이터")
    print("="*60)

    print("\n▶ 1단계: 과거 데이터 수집")
    historical = collect_historical_data(watchlist, years=years, save_path=save_path)

    print("\n▶ 2단계: 매크로 히스토리")
    macro_cache = fetch_macro_history(years=years)

    print("\n▶ 3단계: 신호 시뮬레이션")
    end_date   = pd.Timestamp(datetime.now(KST).strftime("%Y-%m-%d")) - pd.Timedelta(days=max(holding_days_list)*2)
    start_date = pd.Timestamp(datetime.now(KST).strftime("%Y-%m-%d")) - pd.Timedelta(days=365*years)

    sample_ticker = list(watchlist.keys())[0]
    sample_ohlcv  = historical.get(sample_ticker,{}).get("ohlcv", pd.DataFrame())
    if sample_ohlcv.empty:
        print("오류: 기준 OHLCV 없음")
        return None

    trading_days = sample_ohlcv.index[
        (sample_ohlcv.index >= start_date) &
        (sample_ohlcv.index <= end_date)
    ]
    sim_dates = trading_days[::sim_interval_days]
    print("  시뮬레이션: " + str(len(sim_dates)) + "개 (" + str(sim_dates[0].date()) + " ~ " + str(sim_dates[-1].date()) + ")")

    all_signals = []
    for i, date in enumerate(sim_dates):
        date_str   = date.strftime("%Y-%m-%d")
        macro_snap = get_macro_on_date(date_str, macro_cache)
        sig_df     = simulate_signals_on_date(date_str, historical, watchlist, macro_snap, WEIGHTS)
        if not sig_df.empty:
            all_signals.append(sig_df)
        if (i+1) % 10 == 0:
            print("  진행: " + str(i+1) + "/" + str(len(sim_dates)) + " (" + date_str + ")")

    if not all_signals:
        print("시뮬레이션 결과 없음")
        return None

    full_signal_df = pd.concat(all_signals, ignore_index=True)
    print("  총 신호: " + str(len(full_signal_df)) + "건")

    print("\n▶ 4단계: 수익률 계산")
    result_df = calc_forward_returns(full_signal_df, historical, holding_days_list)
    print("  평가 신호: " + str(len(result_df)) + "건")
    if result_df.empty:
        print("수익률 계산 결과 없음")
        return None

    print("\n▶ 5단계: 성과 분석")
    for n in holding_days_list:
        ret_col = "ret_" + str(n) + "d"
        cor_col = "correct_" + str(n) + "d"
        valid   = result_df[result_df[ret_col].notna()]
        if valid.empty: continue
        win_rate = valid[cor_col].mean()*100
        avg_ret  = valid[ret_col].mean()
        std_ret  = valid[ret_col].std()
        sharpe   = avg_ret/std_ret*(252/n)**0.5 if std_ret > 0 else 0
        print("  [" + str(n) + "일] 평가:" + str(len(valid)) + "건 | 승률:" + str(round(win_rate,1)) + "% | 평균:" + str(round(avg_ret,2)) + "% | Sharpe:" + str(round(sharpe,2)))

    print("\n▶ 6단계: 가중치 최적화")
    opt_5d  = optimize_weights(result_df, holding_days=5,  method="sharpe")
    opt_20d = optimize_weights(result_df, holding_days=20, method="sharpe")
    print("  현재: " + str(WEIGHTS))
    if opt_5d:  print("  최적(5일):  " + str(opt_5d))
    if opt_20d: print("  최적(20일): " + str(opt_20d))

    best = opt_20d or opt_5d
    if best:
        update_config_weights(best)

    result_df.to_csv("/content/twin_results.csv", index=False, encoding="utf-8-sig")
    print("\n완료! 결과: /content/twin_results.csv")
    return {"signal_df": full_signal_df, "result_df": result_df, "opt_5d": opt_5d, "opt_20d": opt_20d}
