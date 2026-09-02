"""End-to-end verification of the EKKAA logo integration.
Writes progress to final_verify.txt after EVERY step (capture-failure safety net).
Steps: disk assets -> pixel transparency -> server -> HTTP assets -> rendered pages -> test suite -> cleanup.
"""
import os
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "final_verify.txt")
ASSETS = ["ekkaa-logo-full.png", "ekkaa-mark.png", "favicon.png"]
TREES = [os.path.join("static", "img"), os.path.join("deploy-ready", "static", "img")]
BASE = "http://127.0.0.1:5001"

_lines = []


def log(msg):
    _lines.append(str(msg))
    with open(LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(_lines) + "\n")


def http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


# --- Step 0: assets on disk -------------------------------------------------
log("=== STEP 0: ASSETS ON DISK ===")
all_ok = True
for tree in TREES:
    for name in ASSETS:
        p = os.path.join(ROOT, tree, name)
        if os.path.exists(p):
            log(f"DISK OK   {tree}/{name}  ({os.path.getsize(p)} bytes)")
        else:
            all_ok = False
            log(f"DISK MISS {tree}/{name}")
if not all_ok:
    log("MISSING ASSETS -> generating via process_logo.py + copy")
    subprocess.run([sys.executable, os.path.join(ROOT, "process_logo.py")], cwd=ROOT, timeout=120)
    for tree in TREES[1:]:
        dst = os.path.join(ROOT, tree)
        os.makedirs(dst, exist_ok=True)
        for name in ASSETS:
            src = os.path.join(ROOT, "static", "img", name)
            if os.path.exists(src):
                with open(src, "rb") as fi, open(os.path.join(dst, name), "wb") as fo:
                    fo.write(fi.read())
    for tree in TREES:
        for name in ASSETS:
            p = os.path.join(ROOT, tree, name)
            log(f"DISK NOW  {tree}/{name}: {'OK' if os.path.exists(p) else 'STILL MISSING'}")

# --- Step 1: pixel-level transparency check ---------------------------------
log("=== STEP 1: PIXEL TRANSPARENCY ===")
try:
    from PIL import Image
    for tree in TREES:
        p = os.path.join(ROOT, tree, "ekkaa-mark.png")
        im = Image.open(p).convert("RGBA")
        corner = im.getpixel((0, 0))
        log(f"PIXEL {tree}/ekkaa-mark.png size={im.size} corner_alpha={corner[3]} "
            f"({'transparent bg OK' if corner[3] == 0 else 'OPAQUE bg'})")
except Exception as e:
    log(f"PIXEL CHECK ERROR: {e}")

# --- Step 2: server ----------------------------------------------------------
log("=== STEP 2: SERVER ===")
proc = None
pre_existing = False
try:
    http_get(BASE + "/api/health", timeout=3)
    pre_existing = True
    log("SERVER: already running on :5001 (using it)")
except Exception:
    env = dict(os.environ, PORT="5001", USE_MOCK_DATA="true", FLASK_DEBUG="0")
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    up = False
    for _ in range(60):
        time.sleep(0.5)
        try:
            http_get(BASE + "/api/health", timeout=2)
            up = True
            break
        except Exception:
            pass
    log(f"SERVER: started pid={proc.pid} up={up}")

try:
    # --- Step 3: HTTP asset checks ------------------------------------------
    log("=== STEP 3: HTTP ASSETS ===")
    for name in ASSETS:
        try:
            st, ct, body = http_get(f"{BASE}/static/img/{name}")
            log(f"HTTP /static/img/{name}: {st} {ct} len={len(body)}")
        except Exception as e:
            log(f"HTTP /static/img/{name}: ERROR {e}")

    # --- Step 4: rendered pages ---------------------------------------------
    log("=== STEP 4: RENDERED PAGES ===")
    for page in ["/dashboard", "/login"]:
        try:
            st, ct, body = http_get(BASE + page, timeout=15)
            html = body.decode("utf-8", "ignore")
            log(f"PAGE {page}: {st} | full-logo={'ekkaa-logo-full.png' in html} "
                f"| mark={'ekkaa-mark.png' in html} | favicon={'favicon.png' in html}")
        except Exception as e:
            log(f"PAGE {page}: ERROR {e}")

    # --- Step 5: full API test suite ----------------------------------------
    log("=== STEP 5: TEST SUITE ===")
    r = subprocess.run([sys.executable, "test_api.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    keep = [l for l in out.splitlines()
            if ("FAIL" in l or "RESULT" in l or "TAG BALANCE" in l)]
    for l in keep:
        log("  " + l.strip())
    log(f"TESTS EXIT CODE: {r.returncode}")
finally:
    if proc is not None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
        log("SERVER: stopped (tree kill)")
    else:
        log("SERVER: left running (was pre-existing)")

log("=== VERIFY COMPLETE ===")
print("\n".join(_lines))
