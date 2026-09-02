"""Static verification of dashboard assets: JS syntax, HTML tag balance, handler wiring."""
import re
import esprima

html = open('templates/dashboard.html', encoding='utf-8').read()
js = open('static/js/app.js', encoding='utf-8').read()

# 1. JS syntax (esprima only knows ES2017; normalize newer tokens for the parse check)
check = re.sub(r'catch\s*\{', 'catch (e) {', js)
check = check.replace('?.', '.').replace('??', '||')
esprima.parseScript(check)
print('1. JS SYNTAX: OK')

# 2. HTML tag balance
counts = {}
for tag in ('div', 'aside', 'main', 'header', 'nav', 'form', 'table', 'span', 'button'):
    opens = len(re.findall(r'<' + tag + r'[\s>]', html))
    closes = len(re.findall(r'</' + tag + r'>', html))
    counts[tag] = opens - closes
bad = {k: v for k, v in counts.items() if v != 0}
print('2. HTML TAG BALANCE:', 'OK' if not bad else f'MISMATCH {bad}')

# 3. All inline handlers have a matching JS function
handlers = set()
for m in re.finditer(r'on(?:click|change|submit|input)="([^"\s(]+)\(', html):
    handlers.add(m.group(1))
for m in re.finditer(r'on(?:click|change)=\\?"([a-zA-Z_$][\w$]*)\\?\(', js):
    handlers.add(m.group(1))
missing = [h for h in sorted(handlers) if h not in ('document', 'window') and not (
    re.search(r'function\s+' + re.escape(h) + r'\b', js)
    or re.search(r'window\.' + re.escape(h) + r'\s*=', js))]
print('3. HANDLERS:', 'ALL WIRED (%d)' % len(handlers) if not missing else f'MISSING {missing}')


js = open('static/js/app.js', encoding='utf-8').read()

# --- 1. Definitive JS syntax check (esprima understands ES2017; normalize newer tokens) ---
check = re.sub(r'catch\s*\{', 'catch (e) {', js)
check = check.replace('?.', '.').replace('??', '||')
esprima.parseScript(check)
print('1. JS SYNTAX: OK')

js = open('static/js/app.js', encoding='utf-8').read()

# --- 2. Inline handler wiring check ---
# All inline handlers in HTML
handlers = set()
for m in re.finditer(r'on(?:click|change|submit|input)="([^"\s(]+)\(', html):
    handlers.add(m.group(1))
# Handlers injected inside JS template literals (escaped quotes)
for m in re.finditer(r'on(?:click|change)=\\?"([a-zA-Z_$][\w$]*)\\?\(', js):
    handlers.add(m.group(1))

missing = []
for h in sorted(handlers):
    if h in ('document', 'window'):
        continue
    defined = (
        re.search(r'function\s+' + re.escape(h) + r'\b', js)
        or re.search(r'window\.' + re.escape(h) + r'\s*=', js)
        or re.search(r'const\s+' + re.escape(h) + r'\b', js)
    )
    if not defined:
        missing.append(h)
print('HANDLERS:', ', '.join(sorted(handlers)))
print('MISSING FUNCTIONS:', missing if missing else 'NONE - all wired!')

# Check element ids referenced in JS exist in HTML or are created dynamically
ids_js = set(re.findall(r"getElementById\('([\w-]+)'\)", js))
ids_html = set(re.findall(r'id="([\w-]+)"', html))
dyn = set(re.findall(r"\.id\s*=\s*'([\w-]+)'", js)) | set(re.findall(r"id='([\w-]+)'", js))
dyn |= {'toastContainer'}  # created programmatically in showToast
missing_ids = [i for i in sorted(ids_js) if i not in ids_html and i not in dyn]
print('IDS REFERENCED IN JS:', len(ids_js))
print('MISSING IDS:', missing_ids if missing_ids else 'NONE')

# --- 3. Brace balance (naive) - superseded by esprima parse; kept for reference ---
def strip_js(src):
    out = []
    i, n = 0, len(src)
    in_s = None
    while i < n:
        c = src[i]
        if in_s:
            if c == '\\':
                i += 2
                continue
            if c == in_s:
                in_s = None
            i += 1
            continue
        if c in ('"', "'", '`'):
            in_s = c
            i += 1
            continue
        if src.startswith('//', i):
            while i < n and src[i] != '\n':
                i += 1
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)

code = strip_js(js)
for open_c, close_c, name in [('{', '}', 'braces'), ('(', ')', 'parens'), ('[', ']', 'brackets')]:
    diff = code.count(open_c) - code.count(close_c)
    print(f'{name} balance: {diff} {"OK" if diff == 0 else "MISMATCH!"}')
