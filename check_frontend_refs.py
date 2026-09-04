"""Static check: every DOM id / data-hook / inline handler the SPA touches must exist.

Ids come from three places: dashboard.html, base/login templates, or HTML app.js builds
itself (including through the fieldRow/needValue helpers). Anything referenced but defined
nowhere is a dead selector, which is exactly the class of bug that shows up as a blank panel.
"""
import re

JS = open("static/js/app.js", encoding="utf-8").read()
DASH = open("templates/dashboard.html", encoding="utf-8").read()
BASE = open("templates/base.html", encoding="utf-8").read()
LOGIN = open("templates/login.html", encoding="utf-8").read()
TEMPLATES = DASH + BASE + LOGIN
APP_PY = open("app.py", encoding="utf-8").read()

ID = r"A-Za-z0-9_\-\.\[\]"


def ids_in(text):
    out = set(re.findall(r'id="([' + ID + r']+)"', text))
    out |= set(re.findall(r"id='([" + ID + r"]+)'", text))
    return out


html_ids = ids_in(TEMPLATES)
js_ids = ids_in(JS)

# ids the JS creates through helpers, e.g. fieldRow('Label', 'reg_reason', ...)
helper_label = r"(?:'[^']*'|\"[^\"]*\"|`[^`]*`)"
js_ids |= set(re.findall(r"fieldRow\(\s*" + helper_label + r"\s*,\s*'([" + ID + r"]+)'", JS))
js_ids |= set(re.findall(r"needValue\(\s*'([" + ID + r"]+)'", JS))
js_ids |= set(re.findall(r"fillSelect\(\s*'#([" + ID + r"]+)'", JS))
js_ids |= set(re.findall(r"getElementById\(\s*'([" + ID + r"]+)'", JS))
# ids built as a prefix plus a loop index: id="tsRowTotal${i}", '#gp' + id
prefixes = set(re.findall(r"id=\"([A-Za-z0-9_\-\.]+)\$\{", JS))
prefixes |= set(re.findall(r"\$\('#([A-Za-z0-9_\-\.]+)'\s*\+", JS))
refs = set()
refs |= set(re.findall(r"\$\(\s*['\"]#([" + ID + r"]+)", JS))
refs |= set(re.findall(r"getElementById\(\s*['\"]([" + ID + r"]+)", JS))
refs |= set(re.findall(r"querySelector(?:All)?\(\s*['\"]#([" + ID + r"]+)", JS))

known = html_ids | js_ids | prefixes
missing = sorted(r for r in refs
                 if r not in known and not any(r.startswith(p) and p != r for p in prefixes))

data_hooks = sorted(set(re.findall(r"querySelector(?:All)?\(\s*['\"]\[data-([a-z-]+)", JS)))
hook_gaps = {h: False for h in data_hooks if f'data-{h}' not in TEMPLATES and f'data-{h}' not in JS}

# inline handlers referenced from generated HTML must be real, top-level functions
called = set(re.findall(r"on(?:click|change|input|keyup|submit|focus|blur)=\"([A-Za-z_][A-Za-z0-9_]*)\(", JS))
called |= set(re.findall(r"on(?:click|change|input|keyup|submit)=\"([A-Za-z_][A-Za-z0-9_]*)\(", TEMPLATES))
defined = set(re.findall(r"(?:^|\n)\s*(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", JS))
defined |= set(re.findall(r"(?:^|\n)\s*(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*\(|function)", JS))
defined |= set(re.findall(r"window\.([A-Za-z_][A-Za-z0-9_]*)\s*=", JS))
js_keywords = {"if", "for", "return", "typeof", "event", "this", "switch", "while"}
undefined = sorted(f for f in called if f not in defined and f not in js_keywords)

# every fetch()/api() path in the JS must exist as a Flask route
routes = set(re.findall(r'@app\.route\("([^"]+)"', APP_PY))
route_params = {re.sub(r"<[^>]+>", "*", r) for r in routes}
calls = set(re.findall(r"api(?:Quiet)?\(\s*[`'\"](/api[^`'\"?]*)", JS))
unrouted = []
for c in sorted(calls):
    probe = re.sub(r"\$\{[^}]*\}", "*", c)
    if probe in routes:
        continue
    if any(re.fullmatch(re.escape(p).replace(r"\*", "[^/]*"), probe) for p in route_params):
        continue
    if "*" in probe:                       # built from a variable, e.g. '/api/documents/' + id
        continue
    unrouted.append(c)

print(f"ids referenced by JS: {len(refs)}  defined in templates: {len(html_ids)}  built by JS: {len(js_ids)}")
print("MISSING IDS:", missing or "none")
print("DATA HOOKS:", hook_gaps or "all present")
print("UNDEFINED inline handlers:", undefined or "none")
print("JS api() paths with no Flask route:", unrouted or "none")
print("Chart.js in base.html:", bool(re.search(r"Chart\.js|chart\.umd", BASE)))
