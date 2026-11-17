import requests
import re
import sys
import time
import concurrent.futures
from datetime import datetime

# ============================================================
# CONFIG & INPUTS
# ============================================================

print()
print("==========================================")
print("       BULK FIREBASE HEALTH CHECKER")
# ============================================================
print("==========================================")
print()

print("Paste Firebase URLs (press ENTER twice when done):")

raw_lines = []
while True:
    try:
        line = input()
        if not line.strip():
            break
        raw_lines.append(line.strip())
    except EOFError:
        break

raw_text = " ".join(raw_lines)
raw_urls = re.split(r'[\s,]+', raw_text.strip())
firebase_urls = []
seen = set()

for u in raw_urls:
    u = u.strip()
    if not u:
        continue
    if not u.startswith("http"):
        u = f"https://{u}"
    u = u.rstrip('/')
    if u not in seen:
        seen.add(u)
        firebase_urls.append(u)

if not firebase_urls:
    print("No valid Firebase URLs provided.")
    sys.exit(1)

REQUEST_TIMEOUT = 8
MAX_WORKERS = 20

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=100)
session.mount("http://", adapter)
session.mount("https://", adapter)


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


# ============================================================
# CHECK SINGLE FIREBASE
# ============================================================

def check_firebase(base_url):
    short_name = base_url.replace("https://", "").split(".")[0]
    test_url = f"{base_url}/clients.json?shallow=true"
    start = time.time()

    try:
        r = session.get(test_url, timeout=REQUEST_TIMEOUT)
        elapsed = time.time() - start

        if r.status_code == 200:
            data = r.json()
            online_count = len(data) if isinstance(data, dict) else 0
            log(f"[WORKING] {short_name} ({elapsed:.2f}s) -> Clients keys: {online_count}")
            return base_url, True, "OK"

        elif r.status_code == 423:
            log(f"[DEAD - 423 LOCKED] {short_name} ({elapsed:.2f}s)")
            return base_url, False, "423 Locked"

        elif r.status_code in (401, 403):
            log(f"[DEAD - {r.status_code} DENIED] {short_name} ({elapsed:.2f}s)")
            return base_url, False, f"{r.status_code} Permission Denied"

        elif r.status_code == 404:
            log(f"[DEAD - 404 NOT FOUND] {short_name} ({elapsed:.2f}s)")
            return base_url, False, "404 Not Found"

        else:
            log(f"[DEAD - HTTP {r.status_code}] {short_name} ({elapsed:.2f}s)")
            return base_url, False, f"HTTP {r.status_code}"

    except requests.exceptions.Timeout:
        log(f"[DEAD - TIMEOUT] {short_name}")
        return base_url, False, "Timeout"
    except Exception as e:
        log(f"[DEAD - ERROR] {short_name} -> {type(e).__name__}")
        return base_url, False, type(e).__name__


# ============================================================
# MAIN EXECUTION
# ============================================================

print(f"\n[+] Checking {len(firebase_urls)} unique Firebase URL(s)...\n")

working_urls = []
dead_count = 0

with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(firebase_urls), MAX_WORKERS)) as executor:
    futures = [executor.submit(check_firebase, url) for url in firebase_urls]

    for future in concurrent.futures.as_completed(futures):
        url, is_working, reason = future.result()
        if is_working:
            working_urls.append(url)
        else:
            dead_count += 1

# Preserve original paste order for clean copy-paste
working_ordered = [u for u in firebase_urls if u in set(working_urls)]

print("\n==========================================")
print(f"SUMMARY: {len(working_ordered)} WORKING | {dead_count} DEAD")
print("==========================================")

print("\n--- COPY WORKING FIREBASES BELOW ---\n")
if working_ordered:
    for url in working_ordered:
        print(url)
else:
    print("No working Firebase URLs found.")

print("\n------------------------------------")