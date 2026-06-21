"""
mockapi 연결 테스트 — cmd에서 실행:
  python test_api.py
"""
import os, sys, time, requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL   = "https://mockapi.kiwoom.com"
APP_KEY    = os.getenv("APP_KEY", "")
SECRET_KEY = os.getenv("SECRET_KEY", "")
ACCOUNT_NO = os.getenv("ACCOUNT_NO", "")

print(f"BASE_URL   : {BASE_URL}")
print(f"APP_KEY    : {APP_KEY[:8]}...")
print(f"SECRET_KEY : {SECRET_KEY[:8]}...")
print(f"ACCOUNT_NO : {ACCOUNT_NO}")
print()

# 1) 토큰 발급
print("▶ 1. 토큰 발급 (POST /oauth2/token)")
try:
    r = requests.post(f"{BASE_URL}/oauth2/token", json={
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "secretkey": SECRET_KEY,
    }, timeout=10)
    print(f"   status: {r.status_code}")
    data = r.json()
    print(f"   return_code: {data.get('return_code')}")
    token = data.get("token", "")
    print(f"   token: {token[:20]}..." if token else "   token: NONE")
except Exception as e:
    print(f"   ERROR: {e}")
    sys.exit(1)

if not token:
    print("토큰 없음 — 종료")
    sys.exit(1)

headers_base = {
    "Content-Type": "application/json",
    "authorization": f"Bearer {token}",
}

# 2) 종목 목록 (ka10099)
print()
print("▶ 2. 종목 목록 (ka10099 — stkinfo)")
time.sleep(1)
try:
    r = requests.post(f"{BASE_URL}/api/dostk/stkinfo",
                      json={"mrkt_tp": "0"},
                      headers={**headers_base, "api-id": "ka10099"},
                      timeout=10)
    print(f"   status: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"   return_code: {d.get('return_code')}")
        items = d.get("stk_list_qry", [])
        print(f"   종목 수: {len(items)}")
    else:
        print(f"   body: {r.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

# 3) 차트 (ka10081) — 삼성전자
print()
print("▶ 3. 일봉 차트 (ka10081 — 005930 삼성전자)")
time.sleep(1)
try:
    r = requests.post(f"{BASE_URL}/api/dostk/chart",
                      json={"stk_cd": "005930", "base_dt": "00000000", "upd_stkpc_tp": "1"},
                      headers={**headers_base, "api-id": "ka10081"},
                      timeout=10)
    print(f"   status: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"   return_code: {d.get('return_code')}")
        rows = d.get("stk_dt_pole_chart_qry", [])
        print(f"   행 수: {len(rows)}")
        if rows:
            print(f"   첫 행: {rows[0]}")
    else:
        print(f"   body: {r.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

# 4) 예수금 (kt00001)
print()
print("▶ 4. 예수금 (kt00001 — acnt)")
time.sleep(1)
try:
    r = requests.post(f"{BASE_URL}/api/dostk/acnt",
                      json={"acnt_no": ACCOUNT_NO, "qry_tp": "1"},
                      headers={**headers_base, "api-id": "kt00001"},
                      timeout=10)
    print(f"   status: {r.status_code}")
    if r.status_code == 200:
        d = r.json()
        print(f"   return_code: {d.get('return_code')}")
        print(f"   return_msg : {d.get('return_msg')}")
    else:
        print(f"   body: {r.text[:200]}")
except Exception as e:
    print(f"   ERROR: {e}")

print()
print("테스트 완료.")
