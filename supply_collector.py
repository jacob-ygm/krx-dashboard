# supply_collector.py — 수급 2년치 병렬 수집
import time, requests, pickle, os
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com",
}

_fail_lock = Lock()
_fail_count = {"n": 0}

def fetch_investor_pages(ticker, pages=50, delay=0.15):
    """단일 종목 수급 N페이지 수집 (페이지당 약 10거래일)"""
    rows = []
    consecutive_empty = 0
    for page in range(1, pages + 1):
        try:
            url = "https://finance.naver.com/item/frgn.naver?code=" + ticker + "&page=" + str(page)
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                with _fail_lock:
                    _fail_count["n"] += 1
                time.sleep(1.0)
                continue
            r.encoding = "euc-kr"
            soup = BeautifulSoup(r.text, "html.parser")
            target = None
            for tbl in soup.select("table.type2"):
                if len(tbl.select("tr")) > 20:
                    target = tbl
                    break
            if not target:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                continue
            page_rows = 0
            for tr in target.select("tr"):
                tds = tr.select("td")
                if len(tds) < 7:
                    continue
                ds = tds[0].get_text(strip=True)
                if not ds or "." not in ds:
                    continue
                try:
                    def pn(s):
                        s = s.replace(",", "").replace("+", "").strip()
                        return float(s) if s and s != "-" else 0.0
                    rows.append({
                        "date": pd.to_datetime(ds.replace(".", "-")),
                        "foreign": pn(tds[5].get_text(strip=True)),
                        "institutional": pn(tds[6].get_text(strip=True)),
                    })
                    page_rows += 1
                except:
                    continue
            if page_rows == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
            else:
                consecutive_empty = 0
            time.sleep(delay)
        except Exception:
            with _fail_lock:
                _fail_count["n"] += 1
            time.sleep(0.5)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("date").sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[~df.index.duplicated()]


def collect_supply_history(krx_tickers, pages=50, workers=8,
                           save_path="/content/supply_history.pkl"):
    """전 종목 병렬 수집 + 중간 저장"""
    result = {}
    if os.path.exists(save_path):
        with open(save_path, "rb") as f:
            result = pickle.load(f)
        print("기존 수급 데이터 로드: " + str(len(result)) + "종목")

    todo = [t for t in krx_tickers if t not in result]
    if not todo:
        print("모든 종목 수집 완료 상태")
        return result

    print("수집 대상: " + str(len(todo)) + "종목 x " + str(pages) + "페이지 (병렬 " + str(workers) + ")")
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(fetch_investor_pages, t, pages): t for t in todo}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                result[t] = fut.result()
            except Exception as e:
                print("  [오류] " + t + ": " + str(e))
                result[t] = pd.DataFrame()
            done += 1
            if done % 10 == 0:
                avg = sum(len(v) for v in result.values()) / max(1, len(result))
                print("  진행 " + str(done) + "/" + str(len(todo)) +
                      " | 평균 " + str(round(avg)) + "행 | 실패 " + str(_fail_count["n"]))
                with open(save_path, "wb") as f:
                    pickle.dump(result, f)
            # 차단 징후 감지 → 속도 자동 감속
            if _fail_count["n"] > 50:
                print("  ⚠️ 실패 누적 — 5초 대기 후 계속")
                time.sleep(5)
                _fail_count["n"] = 0

    with open(save_path, "wb") as f:
        pickle.dump(result, f)
    ok = sum(1 for v in result.values() if not v.empty)
    avg = sum(len(v) for v in result.values()) / max(1, len(result))
    print("완료: " + str(ok) + "/" + str(len(result)) + "종목 | 평균 " + str(round(avg)) + "행")
    return result
