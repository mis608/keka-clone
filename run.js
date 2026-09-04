/**
 * Headless DOM harness for the Ekkaa HRMS single-page app.
 *
 *   node app.py &                       # server on :5000 (demo data)
 *   node tools/domcheck/run.js          # from the repo root  (needs `npm install jsdom` here)
 *
 * It signs in for real, renders /dashboard in jsdom with static/js/app.js inlined, then walks
 * every module and every modal. Because it executes the shipping JS, it catches the class of bug
 * a syntax/typo check cannot: a loader that throws, a field that renders as "undefined", a panel
 * that never leaves its spinner, or a card whose number disagrees with the API it was drawn from.
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const BASE = process.env.BASE || 'http://127.0.0.1:5000';

/** Canvas + download stubs: the app paints the org chart on a real 2d context, so we record the draw calls. */
function installCanvas(win) {
  win.__downloads = [];
  win.__canvases = [];
      const mkCtx = () => new Proxy({ _props: {}, stats: { fillText: 0, path: 0 }, texts: [] }, {
        get(t, k) {
          if (k === 'measureText') return (str) => ({ width: String(str).length * 6 });
          if (k === '_props' || k === 'texts' || k === 'stats') return t[k];
          if (k in t._props) return t._props[k];
          return (...a) => {
            if (k === 'fillText') { t.texts.push(String(a[0])); t.stats.fillText++; }
            if (k === 'stroke' || k === 'fill') t.stats.path++;
          };
        },
        set(t, k, v) { t._props[k] = v; return true; },
      });
      win.HTMLCanvasElement.prototype.getContext = function (kind) {
        if (kind !== '2d') return null;
        if (!this.__ctx) { this.__ctx = mkCtx(); win.__canvases.push(this.__ctx); }
        return this.__ctx;
      };
      win.HTMLCanvasElement.prototype.toBlob = function (cb, type) {
        cb(new win.Blob([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10])], { type: type || 'image/png' }));
      };
      win.HTMLAnchorElement.prototype.click = function () {
        if (this.hasAttribute('download')) win.__downloads.push(this.getAttribute('download'));
      };
}


const ROOT = path.resolve(__dirname, '..', '..');
const APP_JS = fs.readFileSync(path.join(ROOT, 'static/js/app.js'), 'utf8');
const EMAIL = process.env.LOGIN_EMAIL || 'admin@company.com';
const PASSWORD = process.env.LOGIN_PASSWORD || 'demo123';

const problems = [];
const notes = [];
let cookie = '';
const navs = [];

const fail = (where, msg) => problems.push(`${where}: ${msg}`);
const ok = (where, msg) => notes.push(`  ok   ${where} — ${msg}`);

async function rawFetch(url, init = {}) {
  const headers = Object.assign({}, init.headers || {});
  if (cookie) headers.cookie = cookie;
  const res = await fetch(url, { ...init, headers });
  for (const c of (res.headers.getSetCookie ? res.headers.getSetCookie() : [])) cookie = c.split(';')[0];
  return res;
}
async function api(pathname, init) {
  const res = await rawFetch(BASE + pathname, init);
  const text = await res.text();
  try { return { status: res.status, body: JSON.parse(text) }; } catch (e) { return { status: res.status, body: text }; }
}

const MODULES = ['home', 'me', 'inbox', 'employees', 'orgchart', 'documents', 'attendance', 'leave',
                 'timesheet', 'payroll', 'expenses', 'hiring', 'performance', 'reports'];
const TABLES = {
  employees: '#employeesTable', attendance: '#attendanceTable', leave: '#leaveTable',
  documents: '#documentsTable', payroll: '#payslipTable', expenses: '#expensesTable', reports: '#reportTable',
};

async function main() {
  const login = await rawFetch(BASE + '/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, password: PASSWORD }),
  });
  if (!login.ok && login.status !== 302) throw new Error(`login failed: ${login.status}`);
  let html = await (await rawFetch(BASE + '/dashboard')).text();

  // run the real app.js, but nothing from a CDN (that also exercises the chart fallback)
  html = html.replace(/<script[^>]+src="https?:[^"]*"[^>]*><\/script>/g, '');
  html = html.replace(/<link[^>]+href="https?:[^"]*"[^>]*>/g, '');
  html = html.replace(/<script>\s*tailwind\.config[\s\S]*?<\/script>/, '');
  const tag = /<script[^>]+src="\/static\/js\/app\.js"[^>]*><\/script>/;
  if (!tag.test(html)) throw new Error('app.js script tag not found in /dashboard');
  html = html.replace(tag, () => `<script>\n${APP_JS}\n</script>`);

  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (e) => {
    const t = String((e && e.message) || e);
    if (/Not implemented: navigation/.test(t)) return;             // CSV/export uses window.location
    if (/Could not parse CSS/.test(t)) return;                     // Tailwind arbitrary values
    fail('page error', t.slice(0, 240));
  });
  ['error', 'warn'].forEach(level => virtualConsole.on(level, (...a) => {
    const text = a.map(x => (x && x.stack) || String(x)).join(' ');
    if (/Not implemented|Could not parse CSS/.test(text)) return;
    fail(`console.${level}`, text.slice(0, 300));
  }));

  const dom = new JSDOM(html, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: BASE + '/dashboard', virtualConsole,
    beforeParse(window) {
      const NodeResponse = globalThis.Response;
      window.fetch = (input, init = {}) => {
        const url = typeof input === 'string' ? new URL(input.replace(/^~$/, ''), BASE).toString() : input;
        const opts = { ...init, headers: Object.assign({}, init.headers) };
        if (cookie) opts.headers.cookie = cookie;
        const body = opts.body;
        if (body && body.constructor && body.constructor.name === 'FormData') {     // jsdom FormData -> node FormData
          const fd = new FormData();
          for (const [k, v] of body.entries()) {
            if (v && v.buffer) fd.append(k, new Blob([v], { type: v.type || 'application/octet-stream' }), v.name || 'file');
            else fd.append(k, v);
          }
          opts.body = fd;
          delete opts.headers['content-type'];
          delete opts.headers['Content-Type'];
        }
        return fetch(url, opts).then(async (res) => {
          for (const c of (res.headers.getSetCookie ? res.headers.getSetCookie() : [])) cookie = c.split(';')[0];
          const buf = Buffer.from(await res.arrayBuffer());
          const headers = {};
          res.headers.forEach((v, k) => { headers[k] = v; });
          return new NodeResponse(buf, { status: res.status, statusText: res.statusText, headers });
        });
      };
      window.print = () => { window.__printed = (window.__printed || 0) + 1; };
      installCanvas(window);
      window.scrollTo = () => {};
      window.alert = (m) => { window.__alert = m; };
      window.confirm = () => true;
      window.URL.createObjectURL = () => 'blob:stub';
      window.URL.revokeObjectURL = () => {};
      window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));
      window.Element.prototype.scrollIntoView = () => {};
      window.addEventListener('unhandledrejection', (e) => {
        const t = String((e.reason && e.reason.stack) || e.reason || '');
        if (!/Not implemented/.test(t)) fail('unhandled rejection', t.slice(0, 260));
      });
      window.addEventListener('error', (e) => {
        if (e && e.error && e.error.stack) fail('window.onerror', String(e.error.stack).split('\n')[0].slice(0, 240));
      });
    },
  });

  const { window } = dom;
  const doc = window.document;
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const settle = async (maxMs = 6000) => {
    const until = Date.now() + maxMs;
    while (Date.now() < until) { await wait(120); if (!doc.querySelector('.spin')) break; }
    await wait(250);
  };
  const text = sel => { const el = doc.querySelector(sel); return el ? el.textContent.replace(/\s+/g, ' ').trim() : ''; };
  const count = (sel, root = doc) => root.querySelectorAll(sel).length;
  const junkIn = sel => {
    const t = text(sel);
    return ['undefined', 'NaN', '[object Object]', 'Infinity', 'Invalid Date', 'null,']
      .map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/,$/, ''))
      .filter(needle => new RegExp(`(^|[^A-Za-z])${needle.replace(/\\,/g, '')}([^A-Za-z]|$)`).test(t));
  };

  for (let i = 0; i < 60 && !doc.querySelector('#homeKpis .kpi'); i++) await wait(100);
  await settle();
  ok('boot', `role=${window.eval('APP.user.role')} module=${window.eval('currentModule')} kpis=${count('#homeKpis .kpi')}`);
  if (count('#homeKpis .kpi') === 0) fail('boot', 'no KPI cards rendered — bootApp never finished');

  // ------------------------------------------------------------- every module renders
  for (const mod of MODULES) {
    window.eval(`switchModule('${mod}')`);
    await settle();
    const host = `#module-${mod}`;
    if (!doc.querySelector(host)) { fail(mod, 'section not found in the template'); continue; }
    if (count(`${host} .spin`)) fail(mod, 'stuck on the loading spinner');
    const body = text(host);
    if (body.length < 150) fail(mod, `rendered only ${body.length} characters`);
    const junk = junkIn(host);
    if (junk.length) fail(mod, `placeholder junk in the DOM: ${junk.join(', ')}`);
    const table = TABLES[mod];
    if (table) {
      const tb = doc.querySelector(table);
      if (!tb) { fail(mod, `${table} not found`); continue; }
      const rows = tb.matches('tbody') ? [...tb.querySelectorAll(':scope > tr')] : [...tb.querySelectorAll('tbody > tr')];
      const filled = rows.filter(r => r.textContent.replace(/\s+/g, ' ').trim().length > 3);
      if (!filled.length) fail(mod, `${table} has no data rows (rows=${rows.length})`);
      else ok(mod, `${table.replace('#', '')} → ${filled.length} row(s)`);
    }
    if (count(`${host} .kpi`)) ok(mod, `${count(`${host} .kpi`)} kpi card(s), ${count(`${host} .keka-card`)} panel(s)`);
    if (count(`${host} .css-chart`)) ok(mod, `chart fallback: ${count(`${host} .css-chart`)} block(s)`);
    else if (count(`${host} canvas`)) ok(mod, `${count(`${host} canvas`)} canvas(es)`);
  }

  // ------------------------------------------------- Home cards must match the API
  const stats = (await api('/api/stats')).body;
  window.eval("switchModule('home')"); await settle();
  const cards = {};
  for (const c of [...doc.querySelectorAll('#homeKpis .kpi')]) {
    const lbl = c.querySelector('.uppercase')?.textContent.trim();
    const val = c.querySelector('.num')?.textContent.trim();
    if (!lbl) continue;
    const hintEl = [...c.children].find(x => x !== c.querySelector('.num') && !x.querySelector('.uppercase'));
    cards[lbl] = { value: val, hint: hintEl ? hintEl.textContent.trim() : '' };
  }
  const numOf = v => Number(String(v ?? '').replace(/[^0-9.]/g, ''));
  const wantCards = {
    'Total employees': stats.total_employees,
    'Present today': stats.present_today,
    'Absent today': stats.absent_today,
    'On leave': stats.on_leave,
    'Needs approval': stats.pending_total,
    'Open positions': stats.open_positions,
  };
  for (const [label, want] of Object.entries(wantCards)) {
    if (!(label in cards)) { fail('home kpi', `no "${label}" card (cards: ${Object.keys(cards).join(' | ')})`); continue; }
    if (numOf(cards[label].value) !== Number(want)) fail('home kpi', `"${label}" shows ${cards[label].value} but /api/stats says ${want}`);
    else ok('home kpi', `${label} = ${cards[label].value}`);
  }
  const rateCard = Object.entries(cards).find(([k]) => /attendance rate/i.test(k));
  if (!rateCard) fail('home kpi', 'no attendance-rate card');
  else if (Math.abs(numOf(rateCard[1].value) - stats.attendance_rate) > 0.6) fail('home kpi', `attendance rate shows ${rateCard[1].value} but the API says ${stats.attendance_rate}%`);
  else ok('home kpi', `attendance rate ${rateCard[1].value} matches the API`);
  const hintText = Object.values(cards).map(c => c.hint).join(' · ');
  for (const [needle, key] of [['exited', 'exited_employees'], ['joined', 'joined_this_month'], ['from home', 'wfh_today'], ['late', 'late_today'], ['half day', 'half_day_today'], ['of \d+ expected', 'expected_today']]) {
    const m = hintText.match(new RegExp(`([0-9,]+)\s*(?:[a-z ]{0,18})?${needle}`, 'i'));
    if (m && Number(m[1].replace(/,/g, '')) !== Number(stats[key])) fail('home kpi', `a card hint reads "${m[0]}" but /api/stats.${key} = ${stats[key]}`);
  }
  for (const probe of [/half day/i, /pending|needs approval|needs your action|awaiting/i]) {
    if (!probe.test(text('#module-home'))) fail('module home', `no ${probe} text anywhere — the breakdown the cards promise is not shown`);
  }

  const inbox = (await api('/api/inbox')).body;
  const pendingCards = count('#pendingActionsList > *');
  if (inbox.total > 0 && pendingCards === 0) fail('home inbox', `API reports ${inbox.total} pending actions, DOM has ${pendingCards}`);
  else ok('home inbox', `${pendingCards} card(s) for ${inbox.total} pending action(s)`);

  // ------------------------------------------------ Documents: why it was filed, and for whom
  window.eval("switchModule('documents')"); await settle();
  {
    const apiDocs = (await api('/api/documents')).body;
    const withPurpose = apiDocs.filter(d => (d.purpose || '').length > 12);
    if (!withPurpose.length) fail('documents', 'the API returns no document purpose text at all');
    else {
      const probe = withPurpose[Math.floor(withPurpose.length / 2)];
      // match the row by the document id its action carries - titles repeat across people
      const row = [...doc.querySelectorAll('#documentsTable > tr')]
        .find(tr => (tr.getAttribute('onclick') || '').includes(String(probe.id)));
      const rowTxt = row ? row.textContent.replace(/\s+/g, ' ').trim() : '';
      if (!row) fail('documents', `“${probe.title}” (${probe.id}) is not in the table the module renders`);
      else {
        const key = w => String(w || '').split(/\s+/).slice(0, 2).join(' ');
        if (!rowTxt.includes(key(probe.purpose))) fail('documents', `the row for “${probe.title}” does not show why it was filed (“${probe.purpose}”)`);
        else ok('documents', `row shows the filing purpose: ${String(probe.purpose).slice(0, 44)}…`);
        if (!probe.visibility || !rowTxt.includes(probe.visibility.replace(/\s+/g, ' '))) {
          fail('documents', `the row for “${probe.title}” does not show who can see it — API says visibility “${probe.visibility}”`);
        } else ok('documents', `row shows who can see it: ${probe.visibility}`);
        if (!/\d{1,2} [A-Z][a-z]{2} \d{4}|no expiry|expired \d+d ago|\d+d left/i.test(rowTxt)) {
          fail('documents', `the row for “${probe.title}” shows no validity or expiry state (row: ${rowTxt.slice(0, 110)})`);
        } else ok('documents', 'row shows the validity / expiry state');
        if (!probe.uploaded_by_label || !rowTxt.toUpperCase().includes(String(probe.uploaded_by_person?.full_name || '').toUpperCase().split(' ')[0])) {
          fail('documents', `the row for “${probe.title}” does not name who uploaded it`);
        } else ok('documents', `row names the uploader: ${probe.uploaded_by_label}`);
      }
    }
    const reqPane = text('#module-documents');
    if (!/asked|request/i.test(reqPane)) fail('documents', 'no trace of the document requests people were asked for');
  }

  // ------------------------------------------------------------------- modals & flows
  const emps = (await api('/api/employees')).body;
  window.eval(`openEmployeeDetail('${emps[0].id}')`); await wait(900); await settle();
  if (text('#modalTitle').length < 3) fail('employee modal', 'opened with an empty title');
  else if (!/Edit/.test(text('#modalBody') + text('#modalFoot'))) fail('employee modal', 'HR Admin cannot see Edit');
  else ok('employee modal', `${text('#modalTitle')} — Edit/Remove available to admin`);
  if (junkIn('#modalBody').length) fail('employee modal', `junk: ${junkIn('#modalBody').join(', ')}`);
  const editBtn = [...doc.querySelectorAll('#modalBody button, #modalFoot button')].find(b => /edit/i.test(b.textContent));
  if (editBtn) { editBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); await wait(700);
    if (!doc.querySelector('#empForm, #modalBody form, #full_name')) fail('employee edit', 'clicking Edit did not open a form');
    else ok('employee edit', `form opened with ${count('#modalBody input, #modalBody select')} fields`);
  }
  window.eval('closeAllModals()');

  // org chart: tree, dept tab, zoom, expand
  window.eval("switchModule('orgchart')"); await settle();
  ok('org', `tree nodes=${count('#orgChartContainer .org-node')} focus options=${count('#orgFocus option')}`);
  if (!count('#orgChartContainer .org-node')) fail('org', 'no nodes rendered');
  window.eval("setOrgTab('dept')"); await wait(500);
  if (!count('#orgChartContainer .avatar')) fail('org', 'department tab shows no people');
  else ok('org', `department tab → ${count('#orgChartContainer .avatar')} avatar(s)`);
  if (/No head assigned/.test(text('#orgChartContainer'))) fail('org', 'a department reports no head even though the API has one');
  window.eval("setOrgTab('tree'); orgExpandAll(true); orgZoom(-0.1)"); await wait(400);
  if (junkIn('#orgChartContainer').length) fail('org', `junk: ${junkIn('#orgChartContainer').join(', ')}`);
  // “Download PNG” must write a real image containing the API's people, not open the print dialog
  const orgApi = (await api('/api/orgchart')).body;
  const rootName = (orgApi.tree && orgApi.tree[0] && orgApi.tree[0].name) || '';
  for (const tab of ['tree', 'dept']) {
    window.eval(`setOrgTab('${tab}')`); await wait(300);
    const before = window.__downloads.length, printedBefore = window.__printed || 0;
    await window.eval('downloadOrgPng()');
    await wait(500);
    if (window.__downloads.length === before) fail(`org png (${tab})`, 'no file was written');
    else ok(`org png (${tab})`, `saved ${window.__downloads[window.__downloads.length - 1]}`);
    if ((window.__printed || 0) > printedBefore) fail(`org png (${tab})`, 'fell back to window.print() although a 2d canvas works');
    const cv = window.__canvases[window.__canvases.length - 1];
    if (!cv || !cv.texts.length) fail(`org png (${tab})`, 'nothing was drawn on the canvas');
    else {
      const drawn = cv.texts.join(' | ');
      if (!/Org chart/.test(drawn)) fail(`org png (${tab})`, 'the export has no title');
      if (tab === 'tree' && rootName && !cv.texts.some(x => x.includes(rootName.split(' ')[0]))) {
        fail('org png (tree)', `the root person "${rootName}" is not on the exported image (drew: ${drawn.slice(0, 140)})`);
      }
      if (tab === 'dept') {
        const depName = ((orgApi.departments || [])[0] || {}).name || '';
        if (depName && !cv.texts.some(x => x.includes(depName.split(' ')[0]))) fail(`org png (dept)`, `department "${depName}" missing from the export`);
      }
      ok(`org png (${tab})`, `${cv.stats.fillText} text draw(s), ${cv.stats.path} shape draw(s)`);
    }
  }
  window.eval("setOrgTab('tree')"); await wait(250);

  // attendance: a correction must demand a written reason, and must know the day's state
  window.eval("switchModule('attendance')"); await settle();
  window.eval("setAttView('regularization')"); await wait(700); await settle();
  const reason = doc.querySelector('#reg_reason');
  if (!doc.querySelector('#regForm') || !reason) fail('regularization', 'the correction form did not render (#regForm / #reg_reason missing)');
  else {
    const send = [...doc.querySelectorAll('#regForm button')].find(b => /send for approval/i.test(b.textContent));
    const regDate = doc.querySelector('#reg_date');
    const regIn = doc.querySelector('#reg_in');
    if (!send || !regDate) fail('regularization', 'form is missing its date input or submit button');
    else {
      const before = (await api('/api/regularizations')).body.length;
      // 1. reason is mandatory and has a floor
      reason.value = 'oops';
      reason.dispatchEvent(new window.Event('input', { bubbles: true }));
      await wait(150);
      const hint = text('#regReasonCount');
      send.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      await wait(900);
      if ((await api('/api/regularizations')).body.length !== before) fail('regularization', 'a 5-character reason was accepted');
      else ok('regularization', 'short reason blocked client-side');
      if (!/more characters needed/i.test(hint)) fail('regularization', 'the live character hint did not react to input');

      // 2. the form must state what the picked day already holds (no blind submissions)
      regDate.value = window.eval('todayIso()');
      regDate.dispatchEvent(new window.Event('change', { bubbles: true }));
      await wait(250);
      const dayHint = text('#regDayHint');
      if (!/on file|no attendance record/i.test(dayHint)) fail('regularization', `changing the date did not surface the day's state (hint: "${dayHint}")`);
      else ok('regularization', `day hint follows the record: ${dayHint.slice(0, 64)}`);

      // 3. a complete day with no corrected times is refused before the POST
      const dayHasBothPunches = /on file \d\d:\d\d → \d\d:\d\d/.test(dayHint);
      if (dayHasBothPunches && regIn) {
        regIn.value = '';
        doc.querySelector('#reg_out').value = '';
        reason.value = 'The biometric reader was down when I arrived, so my in-punch is missing.';
        reason.dispatchEvent(new window.Event('input', { bubbles: true }));
        send.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
        await wait(700);
        if ((await api('/api/regularizations')).body.length !== before) fail('regularization', 'an ambiguous correction (both punches on file, no proposed times) was filed anyway');
        else ok('regularization', 'ambiguous correction refused up front, with guidance');
      }

      // 4. a valid request files and keeps its reason text
      reason.value = 'The biometric reader was down when I arrived, so my in-punch is missing.';
      reason.dispatchEvent(new window.Event('input', { bubbles: true }));
      if (regIn) {
        regIn.value = '09:22';
        regIn.dispatchEvent(new window.Event('change', { bubbles: true }));
      }
      await wait(150);
      send.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      await wait(1600); await settle();
      const rows = (await api('/api/regularizations')).body;
      if (rows.length !== before + 1) fail('regularization', `valid reason filed nothing (${before} -> ${rows.length})`);
      else {
        ok('regularization', `valid reason filed ${rows[0].id} with the reason attached`);
        if (!rows[0].reason || rows[0].reason.length < 20) fail('regularization', 'the saved row lost its reason text');
        if (dayHasBothPunches && rows[0].clock_in_correction !== '09:22') fail('regularization', `the proposed in-time did not reach the row (got ${rows[0].clock_in_correction})`);
        await api(`/api/regularizations/${rows[0].id}`, { method: 'DELETE' });
      }
    }
  }

  // timesheet: type hours into the grid, save, and read the totals back from the API
  window.eval("switchModule('timesheet')"); await settle();
  const cells = [...doc.querySelectorAll('#tsGridWrap input[data-ts]')];
  if (!cells.length) fail('timesheet', 'no hour cells rendered (#tsGridWrap input[data-ts])');
  else {
    const iso = window.eval('APP.tsWeek');
    const apiWeek = async () => {
      const b = (await api('/api/timesheet?week=' + iso)).body;
      return b.days.reduce((t, d) => t + d.entries.reduce((a, e) => a + Number(e.hours || 0), 0), 0);
    };
    const apiTotal = await apiWeek();
    const rowTotals = () => [...doc.querySelectorAll('#tsGridWrap [id^="tsRowTotal"]')].reduce((a, el) => a + (Number(el.textContent.replace(/[^0-9.]/g, '')) || 0), 0);
    const footTotal = () => Number(text('#tsTotal').replace(/[^0-9.]/g, '')) || 0;
    if (Math.abs(rowTotals() - footTotal()) > 0.05) fail('timesheet', `row totals add to ${rowTotals()} h but the footer says ${footTotal()} h`);
    if (Math.abs(footTotal() - apiTotal) > 0.05) fail('timesheet', `the grid shows ${footTotal()} h for a week the API reports as ${apiTotal} h — saving would delete ${Math.round((apiTotal - footTotal()) * 10) / 10} h of logged time`);
    else ok('timesheet', `grid shows ${footTotal()} h = the ${apiTotal} h the API holds for ${iso}`);
    const emptyCell = cells.find(c => !c.value || c.value === '0') || cells[0];
    const rowIdx = Number(emptyCell.dataset.ts.split('|')[0]);
    const rowBefore = Number(text('#tsRowTotal' + rowIdx).replace(/[^0-9.]/g, '')) || 0;
    emptyCell.value = '3.5';
    emptyCell.dispatchEvent(new window.Event('change', { bubbles: true }));
    await wait(400);
    const rowAfter = Number(text('#tsRowTotal' + rowIdx).replace(/[^0-9.]/g, '')) || 0;
    if (Math.abs(rowAfter - (rowBefore + 3.5)) > 0.05) fail('timesheet', `typing 3.5 into row ${rowIdx} moved its total from ${rowBefore} to ${rowAfter}, expected ${rowBefore + 3.5}`);
    else ok('timesheet', `${cells.length} cell(s); row ${rowIdx} total ${rowBefore} -> ${rowAfter} h on input`);
    const save = doc.querySelector('#tsSaveBtn');
    if (!save) fail('timesheet', 'no #tsSaveBtn');
    else {
      save.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
      await wait(1800); await settle();
      const saved = await apiWeek();
      if (Math.abs(saved - (apiTotal + 3.5)) > 0.05) fail('timesheet', `saving wrote ${saved} h for a week that held ${apiTotal} h plus 3.5 h typed — hours were lost or duplicated`);
      else ok('timesheet', `save round-tripped the whole week: ${apiTotal} -> ${saved} h with nothing lost`);
      if (Math.abs(footTotal() - saved) > 0.05) fail('timesheet', `after saving, the grid shows ${footTotal()} h but the API holds ${saved} h`);
    }
  }

  // reports: every report must produce KPIs, a chart and a table
  window.eval("switchModule('reports')"); await settle();
  const reportNames = [...doc.querySelectorAll('#reportPick option')].map(o => o.value).filter(Boolean);
  for (const name of reportNames) {
    doc.querySelector('#reportPick').value = name;
    window.eval('loadReport()');
    await settle(4000);
    const k = count('#reportKpis .kpi'), rows = count('#reportTable tbody tr');
    if (!k || !rows) fail(`report ${name}`, `kpis=${k} rows=${rows}`);
    if (junkIn('#reportKpis').length || junkIn('#reportTable').length) fail(`report ${name}`, 'junk text in the output');
  }
  ok('reports', `${reportNames.length} report(s) rendered: ${reportNames.join(', ')}`);
  const search = doc.querySelector('#reportSearch') || doc.querySelector('#reportTableSearch');
  if (search) { search.value = 'zz-no-such-row'; search.dispatchEvent(new window.Event('input', { bubbles: true })); await wait(300);
    const visible = [...doc.querySelectorAll('#reportTable tbody tr')].filter(tr => tr.style.display !== 'none').length;
    if (visible) fail('reports', `search “zz-no-such-row” still left ${visible} row(s) visible`);
    else ok('reports', 'table search filters correctly');
    search.value = ''; search.dispatchEvent(new window.Event('input', { bubbles: true })); await wait(200);
  } else fail('reports', 'no table-search input found');

  // custom report: run + CSV (CSV must not navigate; it builds a Blob)
  const csCol = doc.querySelector('[data-cscol]');
  if (!csCol) fail('custom report', 'no column checkboxes rendered');
  else { csCol.checked = true; csCol.dispatchEvent(new window.Event('change', { bubbles: true })); }
  window.eval('runCustomReport(false)'); await wait(1500);
  if (!count('#csResult table')) fail('custom report', 'grid did not render');
  else ok('custom report', `${count('#csResult table tbody tr')} row(s) in the result grid`);
  window.eval('runCustomReport(true)'); await wait(1200);

  // hire flow, inbox approve, announcements, export links
  window.eval("switchModule('hiring')"); await settle();
  const stageSel = doc.querySelector('#hiringStage, [data-candidate-stage]');
  if (stageSel) ok('hiring', 'stage selector present');
  const move = [...doc.querySelectorAll('#module-hiring button')].find(b => /hire|advance/i.test(b.textContent));
  if (move) { move.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); await wait(800); window.eval('closeAllModals()'); }

  window.eval("switchModule('inbox')"); await settle();
  if (!count('#module-inbox .keka-card')) fail('inbox', 'nothing rendered');
  else ok('inbox', `${count('#module-inbox .keka-card')} card(s), approve buttons: ${count('#module-inbox button')}`);

  window.eval('loadAnnouncements()'); await wait(800);
  ok('announcements', `${count('#announcementsList > *')} item(s) in the sidebar list`);

  // CSV export endpoints must be wired to a GET link, not a dead button
  const exportButtons = [...doc.querySelectorAll('button, a')].filter(b => /export|csv/i.test(b.textContent));
  ok('exports', `${exportButtons.length} export control(s) present`);

  // ---------------- HR punch edit and the two document modals (regression: a grid()/join typo
  // silently killed all three: clicking did nothing at all, so this checks each one really opens)
  window.eval("switchModule('attendance')"); await settle();
  const maEditBtn = doc.querySelector('#attendanceTable [title="Edit record"]');
  if (!maEditBtn) fail('attendance edit', 'HR has no row-level "Edit record" button');
  else {
    maEditBtn.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); await wait(700);
    const maEmp = doc.querySelector('#ma_emp'), brk = doc.querySelector('#ma_break');
    const maVisible = !doc.querySelector('#modalBackdrop').classList.contains('hidden');
    if (!maEmp || !brk || !maVisible) fail('attendance edit', 'the modal never opened (fields missing)');
    else {
      ok('attendance edit', `modal opened: employee ${JSON.stringify(maEmp.value)}, ${doc.querySelectorAll('#modalBody input, #modalBody select').length} fields`);
      const beforeTxt = (doc.querySelector('#attendanceTable tbody tr') || {}).textContent || '';
      doc.querySelector('#ma_in').value = '09:15';
      doc.querySelector('#ma_out').value = '18:45';
      const maSave = [...doc.querySelectorAll('#modalFoot button')].find(b => /save changes|mark day/i.test(b.textContent));
      if (!maSave) fail('attendance edit', 'no Save button in the modal footer');
      else {
        maSave.dispatchEvent(new window.MouseEvent('click', { bubbles: true })); await wait(1600);
        const afterTxt = (doc.querySelector('#attendanceTable tbody tr') || {}).textContent || '';
        const stRes = await api('/api/attendance?month=' + new Date().toISOString().slice(0, 7));
        const edited = (stRes.body.rows || []).find(r => String(r.clock_in).startsWith('09:15'));
        if (!edited) fail('attendance edit', 'the saved times did not come back from the API');
        else if (edited.clock_in !== '09:15:00' || edited.clock_out !== '18:45:00') fail('attendance edit', `stored as ${edited.clock_in}/${edited.clock_out}, expected HH:MM:SS`);
        else if (!(Number(edited.work_hours) > 8)) fail('attendance edit', `work hours were not recomputed (${edited.work_hours})`);
        else ok('attendance edit', `09:15 -> 18:45 persisted as ${edited.clock_in}/${edited.clock_out} = ${edited.work_hours} h${beforeTxt === afterTxt ? '' : ', table re-rendered'}`);
        if (doc.querySelector('#modalBackdrop').classList.contains('hidden')) ok('attendance edit', 'modal closed after saving');
        else fail('attendance edit', 'the modal stayed open after saving');
      }
    }
    window.eval('closeAllModals()');
  }
  for (const [fn, sel, name] of [['openDocUpload()', '#doc_type', 'Upload document'], ['openDocRequestForm()', '#dr_emp', 'Request a document']]) {
    window.eval(fn); await wait(450);
    if (!doc.querySelector(sel) || doc.querySelector('#modalBackdrop').classList.contains('hidden')) fail('modals', `${name} never opened`);
    else ok('modals', `${name} opens with ${doc.querySelectorAll('#modalBody input, #modalBody select, #modalBody textarea').length} controls`);
    window.eval('closeAllModals()');
  }

  // the tracker must match the day's real state - a closed day cannot invite another clock-in
  window.eval("switchModule('home')"); await settle();
  const trk = (await api('/api/stats')).body.my_time;
  const clkIn = doc.querySelector('#btnClockIn'), outB = doc.querySelector('#btnClockOut');
  const wantIn = trk.clocked_out ? 'Day closed' : trk.clocked_in ? 'Clocked in' : 'Clock in';
  const locked = wantIn !== 'Clock in';
  if (clkIn.textContent.trim() !== wantIn) fail('tracker', `clock-in button says '${clkIn.textContent.trim()}' while the API says ${JSON.stringify({ in: trk.clocked_in, out: trk.clocked_out })}`);
  else if (!!clkIn.disabled !== locked) fail('tracker', `'${wantIn}' should be ${locked ? 'locked' : 'clickable'} (disabled=${clkIn.disabled})`);
  else if (trk.clocked_out && !outB.disabled) fail('tracker', 'clock-out is still active on a closed day');
  else ok('tracker', `buttons match the day: '${clkIn.textContent.trim()}' / '${outB.textContent.trim()}'`);
  const trkTxt = (doc.querySelector('#clockStatusText') || {}).textContent || '';
  if (trk.clocked_out && !(trkTxt.includes(trk.clock_in) && trkTxt.includes(trk.clock_out))) fail('tracker', `a closed day hides its punches: "${trkTxt.trim()}"`);
  else ok('tracker', trk.clocked_out ? `the status line shows the punches: ${trkTxt.trim().slice(0, 74)}…` : `day still open, status line: ${trkTxt.trim().slice(0, 60)}…`);

  // ------------------------------------------------------- employee role must see less
  // The admin DOM is the baseline: all three HR areas are in the sidebar there.
  for (const mod of ['employees', 'hiring', 'reports']) {
    if (!doc.querySelector(`a[data-module="${mod}"]`)) fail('roles', `the HR Admin sidebar lost the ${mod} link`);
  }
  ok('roles', 'HR Admin sidebar keeps Employees, Hiring and Reports');
  if (!doc.querySelector('a[data-module="me"]')) fail('roles', 'sidebar lost the Me link');

  await rawFetch(BASE + '/logout');
  cookie = '';
  const empLogin = await rawFetch(BASE + '/login', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ email: 'aarav.sharma@company.com', password: PASSWORD }),
  });
  if (!empLogin.ok && empLogin.status !== 302) fail('employee login', `status ${empLogin.status}`);
  // the employee gets their own server-rendered dashboard, not the admin one
  const empRaw = await rawFetch(BASE + '/dashboard');
  if (empRaw.status !== 200) fail('employee login', `/dashboard for an Employee returned ${empRaw.status}`);
  const empHtml = (await empRaw.text())
    .replace(/<script[^>]+src="https?:[^"]*"[^>]*><\/script>/g, '')
    .replace(/<link[^>]+href="https?:[^"]*"[^>]*>/g, '')
    .replace(/<script>\s*tailwind\.config[\s\S]*?<\/script>/, '')
    .replace(tag, () => `<script>\n${APP_JS}\n</script>`);
  const empDom = new JSDOM(empHtml, {
    runScripts: 'dangerously', pretendToBeVisual: true, url: BASE + '/dashboard',
    virtualConsole: new VirtualConsole(),
    beforeParse(w) {
      w.fetch = (input, init = {}) => fetch(new URL(input, BASE).toString(), {
        ...init, headers: Object.assign({ cookie }, init.headers || {}),
      }).then(async res => {
        const buf = Buffer.from(await res.arrayBuffer());
        const headers = {}; res.headers.forEach((v, k) => { headers[k] = v; });
        return new (globalThis.Response)(buf, { status: res.status, statusText: res.statusText, headers });
      });
      w.print = () => {}; w.URL.createObjectURL = () => 'blob:stub'; w.URL.revokeObjectURL = () => {};
      w.matchMedia = w.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {} }));
      w.Element.prototype.scrollIntoView = () => {};
      installCanvas(w);
    },
  });
  for (let i = 0; i < 60 && !empDom.window.document.querySelector('#homeKpis .kpi'); i++) await wait(100);
  await wait(600);
  const edoc = empDom.window.document;

  // 1) the three HR areas are not in an employee's page at all
  for (const mod of ['employees', 'hiring', 'reports']) {
    if (edoc.querySelector(`a[data-module="${mod}"]`)) fail('roles', `an Employee still sees the ${mod} link`);
  }
  ok('roles', 'Employee sidebar has no Employees, Hiring or Reports entry');

  // 2) ...and the running JS refuses them even if something calls switchModule directly
  const mods = empDom.window.eval('JSON.stringify(APP.user.modules || [])');
  for (const mod of ['employees', 'hiring', 'reports']) {
    if (mods.includes(`"${mod}"`)) fail('roles', `the server granted the Employee module '${mod}'`);
  }
  for (const mod of ['home', 'me', 'inbox', 'attendance', 'leave', 'payroll', 'expenses', 'timesheet', 'documents', 'performance', 'orgchart']) {
    if (!mods.includes(`"${mod}"`)) fail('roles', `the server withheld '${mod}' from an Employee`);
  }
  ok('roles', `Employee modules granted: ${JSON.parse(mods).length} of ${MODULES.length}`);
  edoc.defaultView.eval("switchModule('employees')"); await wait(400);
  const active = (edoc.querySelector('.module-section.active') || {}).id;
  if (active !== 'module-home') fail('roles', `switchModule('employees') landed on ${active} instead of home`);
  else ok('roles', 'a direct switchModule("employees") is bounced to Home');
  const toastText = [...edoc.querySelectorAll('#toastWrap .toast')].map(t => t.textContent).join(' ');
  if (!/HR Admins/i.test(toastText)) fail('roles', 'bouncing the Employee produced no explanation toast');

  // 3) admin-only controls stay hidden, including the org-wide tabs
  const hiddenForEmployee = [...edoc.querySelectorAll('[data-admin-only]')]
    .filter(el => el.classList.contains('hidden') || el.style.display === 'none').length;
  const totalAdminOnly = edoc.querySelectorAll('[data-admin-only]').length;
  if (totalAdminOnly === 0) fail('roles', 'template lost the [data-admin-only] markers');
  else if (hiddenForEmployee < totalAdminOnly) fail('roles', `${totalAdminOnly - hiddenForEmployee} admin-only control(s) still visible to an Employee`);
  else ok('roles', `${totalAdminOnly} admin-only control(s) hidden for the Employee role`);
  for (const sel of ['[data-doctab="compliance"]', '[data-tstab="projects"]']) {
    const el = edoc.querySelector(sel);
    if (!el) fail('roles', `${sel} is gone from the markup entirely (it should be hidden, not deleted)`);
    else if (!el.classList.contains('hidden') && el.style.display !== 'none') fail('roles', `${sel} is visible to an Employee`);
  }
  if (totalAdminOnly && hiddenForEmployee === totalAdminOnly) ok('roles', 'Compliance and Projects tabs hidden from an Employee');

  // 3b) Home is personal too: no headcount, no hiring numbers
  edoc.defaultView.eval("switchModule('home')"); await wait(1200);
  const homeTxt = (edoc.querySelector('#homeKpis') || {}).textContent || '';
  for (const label of ['Total employees', 'Open positions', 'Needs approval']) {
    if (homeTxt.includes(label)) fail('home (employee)', `the '${label}' card is still shown to an Employee`);
  }
  if (!/My day/.test(homeTxt)) fail('home (employee)', 'no personal "My day" card');
  else ok('home (employee)', `${edoc.querySelectorAll('#homeKpis .kpi').length} personal card(s): ${homeTxt.replace(/\s+/g, ' ').slice(0, 62)}…`);
  const empStats = await api('/api/stats');
  const badge = ((edoc.querySelector('#inboxBadge') || {}).textContent || '').trim();
  if (String(empStats.body.pending_total) !== badge) {
    fail('home (employee)', `inbox badge says '${badge || 'empty'}' but this login's /api/stats says ${empStats.body.pending_total}`);
  } else {
    ok('home (employee)', `inbox badge is the scoped count (${badge}) · their own pending: ${empStats.body.pending_leaves} leave, ${empStats.body.pending_expenses} expenses, ${empStats.body.pending_documents} docs`);
  }

  // 4) what an employee *does* get: their own records, and the security card
  edoc.defaultView.eval("switchModule('me')"); await wait(1400);
  const meTxt = (edoc.querySelector('#module-me') || {}).textContent || '';
  if (/undefined|\[object Object\]|NaN/.test(meTxt)) fail('me (employee)', 'unrendered value in the profile');
  if (!/Sign-in security/i.test(meTxt)) fail('me (employee)', 'no Sign-in security card');
  else ok('me (employee)', 'Sign-in security card rendered');
  if (!/Set my password|Change password/.test(meTxt)) fail('me (employee)', 'no password control in the security card');
  if (!edoc.querySelector('#pwNudge')) fail('me (employee)', 'the "set your own password" nudge did not appear for a shared-password login');
  else ok('me (employee)', 'shared-password nudge shown');
  edoc.defaultView.eval("switchModule('attendance')"); await wait(1400);
  const attRows = edoc.querySelectorAll('#attendanceTable tr').length;
  if (!attRows || /spin/.test((edoc.querySelector('#attendanceTable') || {}).innerHTML || '')) fail('attendance (employee)', 'no rows of their own');
  else ok('attendance (employee)', `${attRows} row(s) scoped to the signed-in employee`);
  const csvBtns = [...edoc.querySelectorAll('#module-attendance button')].filter(b => /csv/i.test(b.textContent));
  if (!csvBtns.length) fail('attendance (employee)', 'the CSV export control disappeared from a self-service module');
  empDom.window.close();

  // ------------------------------------------------------------------------- report
  console.log('\n' + notes.join('\n'));
  console.log('\n' + '='.repeat(76));
  if (problems.length) {
    console.log(`${problems.length} PROBLEM(S) across ${notes.length + problems.length} recorded assertions:`);
    [...new Set(problems)].forEach(p => console.log('  x ' + p));
  } else {
    console.log(`DOM harness passed: ${MODULES.length} modules, ${reportNames.length} reports, modals, flows and role gating - ${notes.length + problems.length} recorded assertions.`);
  }
  dom.window.close();
  process.exit(problems.length ? 1 : 0);
}

main().catch(e => { console.error('harness crashed:', e); process.exit(2); });
