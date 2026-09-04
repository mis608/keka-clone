"""Filter sweep: call every public GET /api route with junk query values and demand a 400, never a 500.

    .venv/bin/python tools/filter_sweep.py

Why this exists: `int(request.args.get("month"))` and `parse_day(...)`-then-`.strftime()` both
raise on a nonsense filter, which surfaced as an internal error on the payroll and attendance
endpoints while the UI - which only ever sends well-formed values - stayed green. The screen
cannot catch that, so this does: it walks every parameter-less GET route in `app.py` (plus the
`<row_id>` ones filled from live data) and probes each with the filter shapes users type by hand
into a URL, a Postman collection or a shared bookmark.

Exit code is 0 when no route returns 5xx; each failure is printed with the exact params.
"""
import argparse
import re
import sys
from pathlib import Path

import requests

BASE_DEFAULT = "http://localhost:5000"
APP_PY = Path(__file__).resolve().parent.parent / "app.py"

# values that must never produce a 500: wrong type, out of range, empty, injection-ish, ISO shapes
JUNK = {
    "month": ["nonsense", "13", "0", "8", "2026-08", "2026/08", "2026-13", ""],
    "year": ["abcd", "1", "2026", "0000"],
    "date": ["nope", "2026-13-45", "2026-09-01"],
    "from": ["junk", "2026-09-01"],
    "to": ["junk", "2026-09-30"],
    "week": ["junk", "2026-08-31"],
    "status": ["zzz", "", "Pending"],
    "employee_id": ["nope", "999999"],
    "department": ["zzz"],
    "job_id": ["zzz"],
    "type": ["zzz"],
    "doc_type": ["zzz"],
    "expiry": ["zzz"],
    "group_by": ["zzz"],
    "sort": ["zzz"],
    "order": ["zzz"],
    "tab": ["zzz"],
    "view": ["zzz"],
    "period": ["junk"],
    "q": ["\"><svg", "'", "%25"],
    "search": ["%", "zz-no-such-row"],
    "page": ["x", "-1", "0"],
    "limit": ["x", "0", "-5"],
    "format": ["zzz", "csv"],
}
GET_ONLY = re.compile(r'@app\.route\("(/api/[^"]+)"(?:,\s*methods=\[([^\]]+)\])?\)')


def get_routes(source):
    """Every /api path that answers GET, with <params> filled from live rows by the caller."""
    plain, paramed = [], []
    for match in GET_ONLY.finditer(source):
        path, methods = match.group(1), match.group(2) or "GET"
        if "GET" not in methods.upper():
            continue
        if "<" in path:
            paramed.append(path)
        elif "upload" not in path.lower():        # needs multipart, covered by tests_api.py
            plain.append(path)
    return sorted(set(plain)), sorted(set(paramed))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--email", action="append", default=None,
                    help="account to sign in as; repeatable (default: ADMIN_EMAILS entry + first employee)")
    ap.add_argument("--password", default="demo123")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    source = APP_PY.read_text(encoding="utf-8")
    plain, paramed = get_routes(source)

    sessions = []
    probe = requests.Session()
    try:
        probe.get(args.base + "/api/health", timeout=15)
    except requests.RequestException:
        print(f"server not answering on {args.base} - start it first (tools/domcheck/restart.sh)")
        return 2
    emails = list(args.email or [])
    if not emails:
        # the demo HR account, plus whatever /api/login-hint offers as the signed-in employee
        emails = ["admin@company.com"]
        hint = probe.get(args.base + "/api/login-hint", timeout=15)
        if hint.ok and hint.headers.get("Content-Type", "").startswith("application/json"):
            who = (hint.json() or {}).get("email")
            if who and who not in emails:
                emails.append(who)
        if probe.post(args.base + "/login", json={"email": "admin@company.com",
                                                  "password": args.password}, timeout=30).status_code == 401:
            print("  (no admin@company.com in this deployment - pass --email for a real account)")
            emails = emails[1:] or emails

    for email in emails:
        s = requests.Session()
        res = s.post(args.base + "/login", json={"email": email, "password": args.password}, timeout=30)
        if not res.ok:
            print(f"  !! login failed for {email}: {res.status_code}")
            continue
        sessions.append((email, s))

    ids = {}
    for key, path in (("employee_id", "/api/employees"), ("id", "/api/documents"),
                      ("row_id", "/api/leave-requests"), ("job_id", "/api/jobs")):
        body = sessions[0][1].get(args.base + path, timeout=30).json()
        rows = body.get("rows", body) if isinstance(body, dict) else body
        if isinstance(rows, list) and rows:
            ids[key] = rows[0].get("id")
    filled = [p.replace("<int:row_id>", str(ids.get("row_id") or 1)).replace("<row_id>", str(ids.get("row_id") or 1))
              .replace("<employee_id>", str(ids.get("employee_id") or 1)).replace("<job_id>", str(ids.get("job_id") or 1))
              .replace("<doc_id>", str(ids.get("id") or 1)).replace("<path:filename>", "favicon.ico")
              for p in paramed]
    targets = plain + [p for p in filled if "<" not in p]

    bad = []
    probes = 0
    for email, s in sessions:
        for path in targets:
            for key, values in JUNK.items():
                for value in values:
                    probes += 1
                    try:
                        res = s.get(args.base + path, params={key: value}, timeout=60)
                    except requests.RequestException as exc:
                        bad.append((email, path, {key: value}, f"no response ({type(exc).__name__})"))
                        continue
                    if res.status_code >= 500:
                        bad.append((email, path, {key: value}, res.status_code))

    if not args.quiet:
        print(f"swept {len(targets)} GET route(s) x {sum(len(v) for v in JUNK.values())} junk values "
              f"x {len(sessions)} role(s) = {probes} requests")
    if bad:
        print(f"{len(bad)} route returned a 5xx:")
        for email, path, params, code in bad[:40]:
            print(f"  {code}  {path}  {params}  (as {email})")
        return 1
    print("no 5xx anywhere - every junk filter was answered with a clean status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
