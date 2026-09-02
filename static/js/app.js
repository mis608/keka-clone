// Keka HRMS Clone - Frontend Logic  (FIXED BUILD - see FIXES.md)
//
// Key changes vs the original:
//  * every write checks the response and surfaces the server's real error
//    instead of always toasting "success"
//  * the current employee id comes from /api/me (was hardcoded 'e1', which is
//    not a UUID and made every Supabase insert fail silently)
//  * leave balances / attendance chart / calendar use real data (were Math.random
//    and hardcoded arrays)
//  * the Expenses, Documents, Org Chart, Timesheet, Reports and My Profile tabs
//    are actually wired up (they were empty placeholders)
//  * lists refresh into the tab/filter you are actually looking at

let currentModule = 'home';
let employeesCache = [];
let attendanceCache = [];
let leaveCache = [];
let expensesCache = [];
let documentsCache = [];
let leaveFilter = 'All';          // remembers the active Leave tab
let me = { employee_id: null, full_name: 'Admin User', avatar: 'AU' };
const loadedOnce = new Set();

// ---------- SMALL HELPERS ----------
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const initials = (name) => String(name || 'U').trim().split(/\s+/).slice(0, 2)
  .map(w => w[0]).join('').toUpperCase() || 'U';

const inr = (n) => '₹' + Number(n || 0).toLocaleString('en-IN');

/** fetch JSON and THROW the server's error message instead of pretending it worked */
async function apiCall(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; }
  catch { throw new Error(`Server returned HTTP ${res.status} instead of JSON`); }
  if (!res.ok) throw new Error((data && (data.error || data.message)) || `Request failed (HTTP ${res.status})`);
  return data;
}

const apiGet = (url) => apiCall(url);
const apiSend = (url, body, method = 'POST') => apiCall(url, {
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
});

function setHTML(id, html) { const el = document.getElementById(id); if (el) el.innerHTML = html; return el; }
function setText(id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; return el; }
function emptyRow(cols, msg) { return `<tr><td colspan="${cols}" class="py-8 text-center text-sm text-[#8b8fa3]">${esc(msg)}</td></tr>`; }

// ---------- INIT ----------
document.addEventListener('DOMContentLoaded', async () => {
  initNavigation();
  initClock();
  setupSearchAndFilters();
  setupForms();
  try { me = await apiGet('/api/me'); } catch (e) { console.warn('Could not resolve current user', e); }
  loadDashboard();
  loadEmployees();
  loadAnnouncements();
});

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const mod = el.dataset.module;
      if (mod) switchModule(mod);
    });
  });
}

/** Only fetch a module's data when you actually open it (and refresh on revisit). */
function loadModule(mod, force = false) {
  const loaders = {
    home: loadDashboard,
    employees: loadEmployees,
    attendance: loadAttendance,
    leave: () => loadLeave(leaveFilter),
    payroll: loadPayroll,
    hiring: loadHiring,
    performance: loadGoals,
    expenses: loadExpenses,
    documents: loadDocuments,
    orgchart: loadOrgChart,
    timesheet: loadTimesheet,
    reports: loadReports,
    me: loadMyProfile,
    inbox: loadDashboard
  };
  const fn = loaders[mod];
  if (!fn) return;
  if (force || !loadedOnce.has(mod)) loadedOnce.add(mod);
  fn();
}

function switchModule(mod) {
  currentModule = mod;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const activeNav = document.querySelector(`.nav-item[data-module="${mod}"]`);
  if (activeNav) activeNav.classList.add('active');

  document.querySelectorAll('.module-section').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(`module-${mod}`);
  if (target) target.classList.add('active');
  else document.getElementById('module-home')?.classList.add('active');

  const hour = new Date().getHours();
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const titles = {
    home: ['Home', `${greet}, ${me.full_name || 'Admin'}! Here's what's happening today.`],
    employees: ['Employees', 'Manage your organization structure and people'],
    attendance: ['Attendance', 'Track and manage employee attendance'],
    leave: ['Leave Management', 'Manage leave balances and requests'],
    payroll: ['Payroll', 'Process salary and manage payslips'],
    hiring: ['Hiring', 'ATS - Track jobs and candidates'],
    performance: ['Performance', 'OKRs, reviews and feedback'],
    me: ['My Profile', 'Your personal dashboard'],
    inbox: ['Inbox', 'Pending approvals and notifications'],
    orgchart: ['Organization Chart', 'Visualize reporting structure'],
    documents: ['Documents', 'Employee documents and verification'],
    timesheet: ['Timesheet', 'Weekly hours from your attendance'],
    expenses: ['Expenses', 'Reimbursements and claims'],
    reports: ['Reports', 'Analytics and custom reports']
  };
  const t = titles[mod] || titles.home;
  setText('pageTitle', t[0]);
  setText('pageSubtitle', t[1]);

  loadModule(mod, true);
}
window.switchModule = switchModule;

// ---------- CLOCK ----------
function initClock() {
  const updateClock = () => {
    const now = new Date();
    setText('liveClock', now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    setText('liveDate', now.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
  };
  updateClock();
  setInterval(updateClock, 1000);

  document.getElementById('btnClockIn')?.addEventListener('click', () => clockAction('clock_in'));
  document.getElementById('btnClockOut')?.addEventListener('click', () => clockAction('clock_out'));
}

async function clockAction(action) {
  const btnIn = document.getElementById('btnClockIn');
  const btnOut = document.getElementById('btnClockOut');
  const btn = action === 'clock_in' ? btnIn : btnOut;      // FIX: spinner went on the wrong button
  const statusEl = document.getElementById('clockStatus');
  const orig = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...'; }
  try {
    const data = await apiSend('/api/attendance', { action, employee_id: me.employee_id });
    const a = data.attendance || {};
    if (statusEl) {
      const label = a.clock_out ? `Out ${a.clock_out} • ${a.work_hours || 0}h`
                                : `In ${a.clock_in || ''}`;
      statusEl.innerHTML = `<div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div><span class="text-sm">${esc(data.message)} • ${esc(label)}</span>`;
    }
    loadAttendance(); loadDashboard();
    if (currentModule === 'timesheet') loadTimesheet();
    showToast(data.message, 'success');
  } catch (e) {
    showToast(e.message || 'Failed to clock', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = orig; }
  }
}

// ---------- DASHBOARD ----------
async function loadDashboard() {
  try {
    const [stats, leaves] = await Promise.all([
      apiGet('/api/stats'),
      apiGet('/api/leave-requests')
    ]);

    setText('statTotalEmp', stats.total_employees);
    setText('statPresent', stats.present_today);
    setText('statOnLeave', stats.on_leave);
    setText('statOpenJobs', stats.open_positions);
    setText('statAttendanceRate', stats.attendance_rate + '%');

    renderAttendanceChart(stats.attendance_trend);
    renderDeptChart(stats.department_distribution);

    const pending = leaves.filter(l => l.status === 'Pending');

    setHTML('pendingApprovals', pending.slice(0, 4).map(l => `
        <div class="flex items-center gap-3 p-3 rounded-xl hover:bg-[#f6f7fb] transition">
          <div class="w-9 h-9 rounded-full bg-[#eef0ff] flex items-center justify-center text-[#584ac0] font-bold text-xs">${esc(initials(l.employee_name))}</div>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-medium truncate">${esc(l.employee_name)} • ${esc(l.leave_type)}</div>
            <div class="text-xs text-[#8b8fa3]">${l.days} day(s) • ${esc(l.start_date)}</div>
          </div>
          <div class="flex gap-1">
            <button onclick="handleLeaveAction('${l.id}','Approved')" class="w-7 h-7 rounded-full bg-[#e6f9f0] text-[#00b894] flex items-center justify-center hover:bg-[#00b894] hover:text-white transition" title="Approve"><i class="fas fa-check text-xs"></i></button>
            <button onclick="handleLeaveAction('${l.id}','Rejected')" class="w-7 h-7 rounded-full bg-[#ffecec] text-[#ff5a5a] flex items-center justify-center hover:bg-[#ff5a5a] hover:text-white transition" title="Reject"><i class="fas fa-times text-xs"></i></button>
          </div>
        </div>`).join('') || '<div class="text-sm text-[#8b8fa3] text-center py-4">No pending requests 🎉</div>');

    setText('inboxCount', pending.length);
    setHTML('inboxList', pending.map(l => `
      <div class="p-4 rounded-xl border border-[#eef0f6] flex flex-wrap gap-3 justify-between items-center">
        <div class="flex gap-3 items-center"><div class="w-10 h-10 rounded-full bg-[#584ac0] text-white flex items-center justify-center font-bold text-sm">${esc(initials(l.employee_name))}</div>
          <div><div class="font-medium text-sm">${esc(l.employee_name)} requested ${esc(l.leave_type)}</div>
          <div class="text-xs text-[#8b8fa3]">${esc(l.reason || 'No reason given')} • ${esc(l.start_date)} to ${esc(l.end_date)} (${l.days}d)</div></div></div>
        <div class="flex gap-2"><button onclick="handleLeaveAction('${l.id}','Approved')" class="px-3 py-1.5 rounded-full bg-[#1e1f2b] text-white text-xs">Approve</button><button onclick="handleLeaveAction('${l.id}','Rejected')" class="px-3 py-1.5 rounded-full border text-xs">Reject</button></div>
      </div>`).join('') || '<div class="text-sm text-[#8b8fa3] text-center py-6">Nothing needs your attention 🎉</div>');

  } catch (e) { console.error('Dashboard load error', e); }
}

function renderAttendanceChart(trend) {
  const ctx = document.getElementById('attendanceChart');
  if (!ctx || typeof Chart === 'undefined') return;
  if (ctx.chart) ctx.chart.destroy();
  // FIX: was a hardcoded [88,92,85,...] array; now the real 7-day trend.
  const labels = trend?.labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Today'];
  const values = trend?.values || [0, 0, 0, 0, 0, 0, 0];
  ctx.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Present %', data: values, borderColor: '#584ac0',
        backgroundColor: (c) => {
          const bg = c.chart.ctx.createLinearGradient(0, 0, 0, 200);
          bg.addColorStop(0, 'rgba(88,74,192,0.2)'); bg.addColorStop(1, 'rgba(88,74,192,0)');
          return bg;
        },
        fill: true, tension: 0.4, borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (i) => i.parsed.y + '% present' } } },
      scales: { x: { grid: { display: false } }, y: { display: false, min: 0, max: 100 } }
    }
  });
}

function renderDeptChart(dist) {
  const ctx = document.getElementById('deptChart');
  const legendEl = document.getElementById('deptLegend');
  if (!ctx || typeof Chart === 'undefined') return;
  const entries = Object.entries(dist || {});
  const labels = entries.map(e => e[0]);
  const values = entries.map(e => e[1]);
  const colors = ['#584ac0', '#00b894', '#fdcb6e', '#e17055', '#0984e3', '#6c5ce7', '#e84393', '#00cec9'];
  if (ctx.chart) ctx.chart.destroy();
  ctx.chart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { display: false } } }
  });
  const total = values.reduce((a, b) => a + b, 0) || 1;
  if (legendEl) legendEl.innerHTML = labels.map((l, i) => `
      <div class="flex justify-between items-center"><div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background:${colors[i % colors.length]}"></span><span class="text-[#1e1f2b]">${esc(l)}</span></div><span class="font-semibold">${values[i]} <span class="text-[#8b8fa3] font-normal">(${Math.round(values[i] / total * 100)}%)</span></span></div>`).join('');
}

// ---------- EMPLOYEES ----------
async function loadEmployees() {
  try {
    const search = document.getElementById('empSearch')?.value || '';
    const dept = document.getElementById('deptFilter')?.value || 'All';
    const status = document.getElementById('statusFilter')?.value || 'All';
    const data = await apiGet(`/api/employees?search=${encodeURIComponent(search)}&department=${encodeURIComponent(dept)}&status=${encodeURIComponent(status)}`);
    employeesCache = data;
    renderEmployeesTable(data);
    setText('empCount', `${data.length} employee${data.length === 1 ? '' : 's'}`);

    // department dropdowns come from the API so the ids always match the DB
    const depts = await apiGet('/api/departments');
    const modalSelect = document.getElementById('modalDeptSelect');
    if (modalSelect && !modalSelect.dataset.filled) {
      modalSelect.innerHTML = depts.map(d => `<option value="${esc(d.id)}">${esc(d.name)}</option>`).join('');
      modalSelect.dataset.filled = '1';
    }
    const jobDept = document.querySelector('#jobForm [name="department"]');
    if (jobDept && jobDept.tagName === 'SELECT' && !jobDept.dataset.filled) {
      jobDept.innerHTML = depts.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('');
      jobDept.dataset.filled = '1';
    }
    const deptFilter = document.getElementById('deptFilter');
    if (deptFilter && !deptFilter.dataset.filled) {
      deptFilter.innerHTML = '<option>All Departments</option>' +
        depts.map(d => `<option value="${esc(d.name)}">${esc(d.name)}</option>`).join('');
      deptFilter.dataset.filled = '1';
    }
  } catch (e) { console.error(e); showToast(e.message, 'error'); }
}

function renderEmployeesTable(employees) {
  const tbody = document.getElementById('employeesTable');
  if (!tbody) return;
  if (!employees.length) { tbody.innerHTML = emptyRow(7, 'No employees match your filters'); return; }
  tbody.innerHTML = employees.map(emp => `
    <tr class="hover:bg-[#f9fafe] transition">
      <td class="px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center font-bold text-xs">${esc(emp.avatar || initials(emp.full_name))}</div>
          <div><div class="font-semibold text-[#1e1f2b]">${esc(emp.full_name)}</div><div class="text-xs text-[#8b8fa3]">${esc(emp.employee_code)} • ${esc(emp.email)}</div></div>
        </div>
      </td>
      <td class="px-4 py-4"><span class="px-2.5 py-1 rounded-full bg-[#f6f7fb] text-xs font-medium">${esc(emp.department)}</span></td>
      <td class="px-4 py-4 text-[#1e1f2b]">${esc(emp.designation)}</td>
      <td class="px-4 py-4">${esc(emp.work_location || '-')}</td>
      <td class="px-4 py-4"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(emp.status)}">${esc(emp.status)}</span></td>
      <td class="px-4 py-4 text-[#8b8fa3] text-xs">${esc(emp.date_of_joining || '-')}</td>
      <td class="px-6 py-4 text-right">
        <button onclick="deleteEmployee('${emp.id}','${esc(emp.full_name).replace(/'/g, "\\'")}')" class="w-8 h-8 rounded-full hover:bg-[#ffecec] hover:text-[#ff5a5a] text-[#8b8fa3]" title="Remove employee"><i class="fas fa-trash-alt text-xs"></i></button>
      </td>
    </tr>`).join('');
}

async function deleteEmployee(id, name) {
  if (!confirm(`Remove ${name} from the directory?`)) return;
  try {
    await apiCall(`/api/employees/${id}`, { method: 'DELETE' });
    showToast('Employee removed', 'success');
    loadEmployees(); loadDashboard();
  } catch (e) { showToast(e.message, 'error'); }
}
window.deleteEmployee = deleteEmployee;

function statusColor(s) {
  if (s === 'Active' || s === 'Present' || s === 'Approved' || s === 'Verified' || s === 'Paid') return 'bg-[#e6f9f0] text-[#00b894]';
  if (s === 'On Leave' || s === 'Pending' || s === 'On Hold' || s === 'Generated') return 'bg-[#fff4e6] text-[#e17055]';
  if (s === 'Probation' || s === 'In Progress') return 'bg-[#eef0ff] text-[#584ac0]';
  if (s === 'Rejected' || s === 'Absent' || s === 'At Risk') return 'bg-[#ffecec] text-[#ff5a5a]';
  return 'bg-[#f6f7fb] text-[#8b8fa3]';
}

function setupSearchAndFilters() {
  document.getElementById('empSearch')?.addEventListener('input', debounce(loadEmployees, 300));
  document.getElementById('deptFilter')?.addEventListener('change', loadEmployees);
  document.getElementById('statusFilter')?.addEventListener('change', loadEmployees);
  document.getElementById('docFilter')?.addEventListener('change', renderDocuments);

  // FIX: global search silently did nothing when there was no match, and never
  // restored the full list when you cleared the box.
  document.getElementById('globalSearch')?.addEventListener('input', debounce(async (e) => {
    const q = e.target.value.trim();
    const empSearch = document.getElementById('empSearch');
    if (empSearch) empSearch.value = q;
    if (q.length >= 1) switchModule('employees');
    await loadEmployees();
    if (q.length >= 1 && !employeesCache.length) showToast(`No employees match "${q}"`, 'info');
  }, 300));

  document.querySelectorAll('.leave-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.leave-tab').forEach(t => {
        t.classList.remove('active', 'bg-[#1e1f2b]', 'text-white');
        t.classList.add('bg-[#f6f7fb]');
      });
      tab.classList.add('active', 'bg-[#1e1f2b]', 'text-white');
      tab.classList.remove('bg-[#f6f7fb]');
      leaveFilter = tab.dataset.status || 'All';   // FIX: remember the tab
      loadLeave(leaveFilter);
    });
  });
}

function setupForms() {
  // ----- Add employee -----
  document.getElementById('addEmployeeForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(e.target).entries());
    await withBusy(btn, async () => {
      await apiSend('/api/employees', payload);
      closeAddEmployeeModal();
      e.target.reset();
      showToast('Employee added successfully', 'success');
      loadEmployees(); loadDashboard();
    });
  });

  // ----- Apply leave -----
  document.getElementById('leaveForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(e.target).entries());
    if (!payload.start_date || !payload.end_date) return showToast('Please select leave dates', 'error');
    const start = new Date(payload.start_date), end = new Date(payload.end_date);
    if (Number.isNaN(+start) || Number.isNaN(+end) || end < start) return showToast('Please enter a valid date range', 'error');

    const sel = document.getElementById('leaveTypeSelect')?.selectedOptions[0];
    payload.days = Math.round((end - start) / 86400000) + 1;
    // FIX: was hardcoded employee_id:'e1' + leave_type_id:'Casual Leave' (a name).
    payload.employee_id = me.employee_id || undefined;
    payload.leave_type_id = sel?.value || payload.leave_type;
    payload.leave_type = sel?.dataset.name || sel?.textContent?.split(' (')[0] || payload.leave_type;

    await withBusy(btn, async () => {
      await apiSend('/api/leave-requests', payload);
      closeLeaveModal();
      e.target.reset();
      showToast('Leave applied successfully', 'success');
      leaveFilter = 'All';
      document.querySelectorAll('.leave-tab').forEach(t => {
        const isAll = (t.dataset.status || 'All') === 'All';
        t.classList.toggle('bg-[#1e1f2b]', isAll); t.classList.toggle('text-white', isAll);
        t.classList.toggle('active', isAll); t.classList.toggle('bg-[#f6f7fb]', !isAll);
      });
      switchModule('leave');            // FIX: take the user to the record they just created
      loadDashboard();
    });
  });

  // ----- Post a job -----
  document.getElementById('jobForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(e.target).entries());
    await withBusy(btn, async () => {
      await apiSend('/api/jobs', payload);
      closeJobModal();
      e.target.reset();
      showToast('Job published successfully', 'success');
      loadHiring(); loadDashboard();
    });
  });

  // ----- Submit an expense -----
  document.getElementById('expenseForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]');
    const payload = Object.fromEntries(new FormData(e.target).entries());
    payload.employee_id = me.employee_id || undefined;
    await withBusy(btn, async () => {
      await apiSend('/api/reimbursements', payload);
      closeExpenseModal();
      e.target.reset();
      showToast('Expense submitted successfully', 'success');
      switchModule('expenses');        // FIX: it used to vanish with nowhere to appear
    });
  });
}

/** disable a button while its request is in flight and report real errors */
async function withBusy(btn, fn) {
  const orig = btn ? btn.innerHTML : '';
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...'; }
  try { await fn(); }
  catch (err) { showToast(err.message || 'Something went wrong', 'error'); }
  finally { if (btn) { btn.disabled = false; btn.innerHTML = orig; } }
}

function debounce(fn, delay) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

// ---------- ATTENDANCE ----------
async function loadAttendance() {
  try {
    const data = await apiGet('/api/attendance?scope=me');
    attendanceCache = data;
    const tbody = document.getElementById('attendanceTable');
    if (!tbody) return;
    if (!data.length) { tbody.innerHTML = emptyRow(6, 'No attendance recorded yet — use Clock In on the Home tab'); return; }
    tbody.innerHTML = data.slice(0, 15).map(a => `
      <tr>
        <td class="py-3 font-medium">${esc(a.date)}</td>
        <td class="py-3">${a.clock_in ? `<span class="px-2 py-1 rounded-full bg-[#e6f9f0] text-[#00b894] text-xs">${esc(a.clock_in)}</span>` : '<span class="text-[#8b8fa3]">--</span>'}</td>
        <td class="py-3">${a.clock_out ? `<span class="px-2 py-1 rounded-full bg-[#eef0ff] text-[#584ac0] text-xs">${esc(a.clock_out)}</span>` : '<span class="text-[#8b8fa3]">--</span>'}</td>
        <td class="py-3 font-semibold">${a.work_hours ? a.work_hours + 'h' : '--'}</td>
        <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(a.status)}">${esc(a.status)}</span></td>
        <td class="py-3"><button class="text-xs text-[#584ac0] font-medium hover:underline" onclick="showToast('Regularization request sent to your manager','success')">Regularize</button></td>
      </tr>`).join('');
  } catch (e) { console.error(e); }
}

// ---------- LEAVE ----------
async function loadLeave(filterStatus = 'All') {
  leaveFilter = filterStatus || 'All';
  try {
    const [leaves, types, balances] = await Promise.all([
      apiGet(`/api/leave-requests${leaveFilter !== 'All' ? `?status=${encodeURIComponent(leaveFilter)}` : ''}`),
      apiGet('/api/leave-types'),
      apiGet('/api/leave-balances')
    ]);
    leaveCache = leaves;

    // FIX: balances were Math.random() - they changed on every single render.
    setHTML('leaveBalances', balances.map(b => `
        <div class="keka-card p-5 border-l-4" style="border-left-color:${esc(b.color)}">
          <div class="flex justify-between items-start"><div class="w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm" style="background:${esc(b.color)}"><i class="far fa-calendar"></i></div><span class="text-xs px-2 py-1 rounded-full bg-[#f6f7fb]">${b.yearly_quota} / year</span></div>
          <div class="mt-3"><div class="font-semibold">${esc(b.name)}</div><div class="text-2xl font-bold mt-1">${b.available} <span class="text-sm font-normal text-[#8b8fa3]">left</span></div></div>
          <div class="w-full bg-[#f6f7fb] h-1.5 rounded-full mt-3"><div class="h-1.5 rounded-full transition-all" style="width:${Math.min(100, b.used_pct)}%; background:${esc(b.color)}"></div></div>
          <div class="text-[11px] text-[#8b8fa3] mt-2">${b.used} used${b.pending ? ` • ${b.pending} pending` : ''}</div>
        </div>`).join(''));

    const tbody = document.getElementById('leaveTable');
    if (tbody) {
      tbody.innerHTML = leaves.length ? leaves.map(l => `
        <tr>
          <td class="py-3"><div class="flex items-center gap-2"><div class="w-7 h-7 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center text-[10px] font-bold">${esc(initials(l.employee_name))}</div><span class="font-medium">${esc(l.employee_name)}</span></div></td>
          <td class="py-3"><span class="px-2 py-1 rounded-full text-xs" style="background:${esc(l.leave_type_color)}1a;color:${esc(l.leave_type_color)}">${esc(l.leave_type)}</span></td>
          <td class="py-3 text-xs">${esc(l.start_date)} → ${esc(l.end_date)}</td>
          <td class="py-3 font-semibold">${l.days}d</td>
          <td class="py-3 text-xs text-[#8b8fa3] max-w-[150px] truncate" title="${esc(l.reason || '')}">${esc(l.reason || '-')}</td>
          <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(l.status)}">${esc(l.status)}</span></td>
          <td class="py-3 text-right">
            ${l.status === 'Pending'
              ? `<div class="flex gap-1 justify-end"><button onclick="handleLeaveAction('${l.id}','Approved')" class="px-2.5 py-1 rounded-full bg-[#1e1f2b] text-white text-xs">Approve</button><button onclick="handleLeaveAction('${l.id}','Rejected')" class="px-2.5 py-1 rounded-full border text-xs">Reject</button></div>`
              : '<span class="text-xs text-[#8b8fa3]">—</span>'}
          </td>
        </tr>`).join('')
        : emptyRow(7, leaveFilter === 'All' ? 'No leave requests yet' : `No ${leaveFilter.toLowerCase()} requests`);
    }

    const typeSelect = document.getElementById('leaveTypeSelect');
    if (typeSelect) {
      // FIX: value is now the leave-type ID (the DB needs the uuid, not the label)
      typeSelect.innerHTML = types.map(t =>
        `<option value="${esc(t.id)}" data-name="${esc(t.name)}" data-code="${esc(t.code)}">${esc(t.name)} (${esc(t.code)}) - ${t.yearly_quota} days/year</option>`).join('');
    }

    renderMiniCalendar(leaves);
  } catch (e) { console.error(e); showToast(e.message, 'error'); }
}

async function handleLeaveAction(id, status) {
  try {
    await apiSend(`/api/leave-requests/${id}/action`, { status });
    showToast(`Leave ${status.toLowerCase()}`, 'success');
    loadLeave(leaveFilter);     // FIX: stay on the tab the user is looking at
    loadDashboard();
  } catch (e) { showToast(e.message || 'Action failed', 'error'); }
}
window.handleLeaveAction = handleLeaveAction;

/** FIX: was a fake 31-day grid with "today" hardcoded to the 29th. */
function renderMiniCalendar(leaves = []) {
  const el = document.getElementById('miniCalendar');
  if (!el) return;
  const now = new Date();
  const year = now.getFullYear(), month = now.getMonth();
  const first = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const leaveDays = new Set();
  leaves.forEach(l => {
    if (!l.start_date || !l.end_date || l.status === 'Rejected') return;
    let d = new Date(l.start_date + 'T00:00:00');
    const end = new Date(l.end_date + 'T00:00:00');
    while (d <= end) {
      if (d.getFullYear() === year && d.getMonth() === month) leaveDays.add(d.getDate());
      d = new Date(d.getTime() + 86400000);
    }
  });

  let html = '';
  for (let i = 0; i < first; i++) html += '<div></div>';
  for (let i = 1; i <= daysInMonth; i++) {
    const isToday = i === now.getDate();
    const hasLeave = leaveDays.has(i);
    const cls = isToday ? 'bg-[#1e1f2b] text-white font-bold'
      : hasLeave ? 'bg-[#eef0ff] text-[#584ac0] font-semibold' : '';
    html += `<div class="h-8 flex items-center justify-center rounded-full ${cls}" ${hasLeave ? 'title="Leave booked"' : ''}>${i}</div>`;
  }
  el.innerHTML = html;
}

// ---------- PAYROLL ----------
async function loadPayroll() {
  try {
    const data = await apiGet('/api/payslips');
    const tbody = document.getElementById('payslipTable');
    if (!tbody) return;
    if (!data.length) { tbody.innerHTML = emptyRow(7, 'No payslips generated yet'); return; }
    tbody.innerHTML = data.map(p => `
      <tr>
        <td class="py-3 font-medium">${esc(p.employee_name)}</td>
        <td class="py-3">${p.month}/${p.year}</td>
        <td class="py-3">${inr(p.gross)}</td>
        <td class="py-3 text-[#e17055]">-${inr(p.deductions)}</td>
        <td class="py-3 font-bold">${inr(p.net)}</td>
        <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs ${statusColor(p.status)}">${esc(p.status)}</span></td>
        <td class="py-3 text-right"><button onclick='viewPayslip(${JSON.stringify(p).replace(/'/g, "&#39;")})' class="px-3 py-1 rounded-full border text-xs hover:bg-[#f6f7fb]">View</button></td>
      </tr>`).join('');
  } catch (e) { console.error(e); }
}

/** FIX: the View button was inert. */
function viewPayslip(p) {
  const w = window.open('', '_blank', 'width=620,height=760');
  if (!w) return showToast('Allow pop-ups to view the payslip', 'error');
  w.document.write(`<!DOCTYPE html><html><head><title>Payslip ${p.month}/${p.year}</title>
    <style>body{font-family:system-ui,sans-serif;padding:36px;color:#1e1f2b}
    h1{font-size:20px;margin:0 0 4px}.muted{color:#8b8fa3;font-size:13px}
    table{width:100%;border-collapse:collapse;margin-top:24px;font-size:14px}
    td{padding:10px 0;border-bottom:1px solid #eef0f6}td:last-child{text-align:right}
    .net{font-weight:700;font-size:17px}.tag{display:inline-block;padding:4px 10px;border-radius:99px;background:#eef0ff;color:#584ac0;font-size:12px}
    @media print{.noprint{display:none}}</style></head><body>
    <h1>Payslip — ${p.month}/${p.year}</h1>
    <div class="muted">${p.employee_name} • <span class="tag">${p.status}</span></div>
    <table>
      <tr><td>Gross earnings</td><td>₹${Number(p.gross).toLocaleString('en-IN')}</td></tr>
      <tr><td>Total deductions</td><td>-₹${Number(p.deductions).toLocaleString('en-IN')}</td></tr>
      <tr class="net"><td>Net pay</td><td>₹${Number(p.net).toLocaleString('en-IN')}</td></tr>
    </table>
    <p class="noprint" style="margin-top:28px"><button onclick="window.print()" style="padding:10px 18px;border-radius:10px;border:0;background:#584ac0;color:#fff;cursor:pointer">Print / Save as PDF</button></p>
    </body></html>`);
  w.document.close();
}
window.viewPayslip = viewPayslip;

// ---------- HIRING ----------
async function loadHiring() {
  try {
    const [jobs, cands] = await Promise.all([apiGet('/api/jobs'), apiGet('/api/candidates')]);
    setHTML('jobsGrid', jobs.length ? jobs.map(j => `
        <div class="keka-card p-5 hover:shadow-lg transition">
          <div class="flex justify-between items-start gap-2"><h4 class="font-semibold">${esc(j.title)}</h4><span class="px-2 py-1 rounded-full text-xs whitespace-nowrap ${statusColor(j.status)}">${esc(j.status)}</span></div>
          <div class="text-xs text-[#8b8fa3] mt-1">${esc(j.department)} • ${esc(j.location)} • ${j.openings} opening(s)</div>
          <div class="flex items-center gap-2 mt-4"><div class="flex -space-x-1"><div class="w-6 h-6 rounded-full bg-[#eef0ff] border-2 border-white"></div><div class="w-6 h-6 rounded-full bg-[#ffeaa7] border-2 border-white"></div></div><span class="text-xs text-[#8b8fa3]">${j.applicants || 0} applicant(s)</span></div>
        </div>`).join('') : '<div class="text-sm text-[#8b8fa3] py-6">No open jobs. Use “Post a Job” to create one.</div>');

    setHTML('candidatesList', cands.length ? cands.map(c => `
        <div class="flex flex-wrap gap-3 items-center justify-between p-3 rounded-xl border border-[#eef0f6] hover:bg-[#f9fafe] transition">
          <div class="flex items-center gap-3"><div class="w-9 h-9 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center font-bold text-xs">${esc(initials(c.full_name))}</div>
            <div><div class="font-medium text-sm">${esc(c.full_name)}</div><div class="text-xs text-[#8b8fa3]">${esc(c.email)} • ${esc(c.experience)} • ${esc(c.job_title)}</div></div></div>
          <div class="flex items-center gap-3"><span class="px-2.5 py-1 rounded-full bg-[#f6f7fb] text-xs">${esc(c.stage)}</span><div class="flex text-amber-400 text-xs">${'★'.repeat(c.rating)}${'☆'.repeat(Math.max(0, 5 - c.rating))}</div></div>
        </div>`).join('') : '<div class="text-sm text-[#8b8fa3] py-6">No candidates yet.</div>');
  } catch (e) { console.error(e); }
}

// ---------- ANNOUNCEMENTS & GOALS ----------
async function loadAnnouncements() {
  try {
    const res = await apiGet('/api/announcements');
    setHTML('announcementsList', res.map(a => `
      <div class="p-3 rounded-xl border ${a.is_pinned ? 'bg-[#fffbeb] border-amber-200' : 'bg-[#f9fafe] border-[#eef0f6]'}">
        <div class="flex gap-2"><span class="text-xs px-2 py-0.5 rounded-full ${a.type === 'Policy' ? 'bg-[#eef0ff] text-[#584ac0]' : a.type === 'Event' ? 'bg-[#e6f9f0] text-[#00b894]' : 'bg-white border text-[#8b8fa3]'}">${esc(a.type)}</span>${a.is_pinned ? '<span class="text-xs">📌 Pinned</span>' : ''}</div>
        <div class="font-medium text-sm mt-2">${esc(a.title)}</div>
        <div class="text-xs text-[#8b8fa3] mt-1 line-clamp-2">${esc(a.content)}</div>
        <div class="text-[11px] text-[#8b8fa3] mt-2">${esc(a.date || '')}</div>
      </div>`).join('') || '<div class="text-sm text-[#8b8fa3]">No announcements</div>');
  } catch (e) { console.error(e); }
}

async function loadGoals() {
  try {
    const res = await apiGet('/api/goals');
    setHTML('goalsList', res.length ? res.map(g => `
      <div class="p-4 rounded-xl border border-[#eef0f6]">
        <div class="flex justify-between items-start gap-3"><div><div class="font-medium">${esc(g.title)}</div><div class="text-xs text-[#8b8fa3] mt-0.5">${esc(g.employee_name)}</div></div><span class="px-2 py-1 rounded-full text-xs whitespace-nowrap ${statusColor(g.status)}">${esc(g.status)}</span></div>
        <div class="w-full bg-[#f6f7fb] h-2 rounded-full mt-3"><div class="bg-[#584ac0] h-2 rounded-full transition-all" style="width:${g.progress}%"></div></div>
        <div class="flex justify-between text-xs mt-2"><span class="text-[#8b8fa3]">Progress</span><span class="font-semibold">${g.progress}%</span></div>
        <div class="flex justify-between items-center mt-3">
          <div class="text-xs text-[#8b8fa3]">Due: ${esc(g.due_date || '-')}</div>
          <div class="flex gap-1">
            <button onclick="updateGoal('${g.id}', ${Math.min(100, g.progress + 10)})" class="px-2 py-1 rounded-full border text-xs hover:bg-[#f6f7fb]">+10%</button>
            <button onclick="updateGoal('${g.id}', 100)" class="px-2 py-1 rounded-full border text-xs hover:bg-[#f6f7fb]">Complete</button>
          </div>
        </div>
      </div>`).join('') : '<div class="text-sm text-[#8b8fa3] py-6">No goals yet.</div>');
  } catch (e) { console.error(e); }
}

async function updateGoal(id, progress) {
  try {
    await apiSend(`/api/goals/${id}`, { progress }, 'PUT');
    showToast('Goal updated', 'success');
    loadGoals();
  } catch (e) { showToast(e.message, 'error'); }
}
window.updateGoal = updateGoal;

// ---------- EXPENSES (was submitted into a void) ----------
async function loadExpenses() {
  try {
    expensesCache = await apiGet('/api/reimbursements');
    const tbody = document.getElementById('expensesTable');
    if (!tbody) return;
    if (!expensesCache.length) { tbody.innerHTML = emptyRow(6, 'No expenses submitted yet'); return; }
    tbody.innerHTML = expensesCache.map(r => `
      <tr>
        <td class="py-3">${esc(r.date)}</td>
        <td class="py-3 font-medium">${esc(r.employee_name)}</td>
        <td class="py-3"><span class="px-2 py-1 rounded-full bg-[#f6f7fb] text-xs">${esc(r.category)}</span></td>
        <td class="py-3 text-[#8b8fa3] max-w-[220px] truncate" title="${esc(r.description || '')}">${esc(r.description || '-')}</td>
        <td class="py-3 font-semibold">${inr(r.amount)}</td>
        <td class="py-3">
          <span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(r.status)}">${esc(r.status)}</span>
          ${r.status === 'Pending' ? `<button onclick="expenseAction('${r.id}','Approved')" class="ml-2 px-2 py-1 rounded-full bg-[#1e1f2b] text-white text-[11px]">Approve</button><button onclick="expenseAction('${r.id}','Rejected')" class="ml-1 px-2 py-1 rounded-full border text-[11px]">Reject</button>` : ''}
        </td>
      </tr>`).join('');
  } catch (e) { console.error(e); }
}

async function expenseAction(id, status) {
  try {
    await apiSend(`/api/reimbursements/${id}/action`, { status });
    showToast(`Expense ${status.toLowerCase()}`, 'success');
    loadExpenses();
  } catch (e) { showToast(e.message, 'error'); }
}
window.expenseAction = expenseAction;

// ---------- DOCUMENTS (had no data source at all) ----------
async function loadDocuments() {
  try {
    documentsCache = await apiGet('/api/documents');
    const counts = documentsCache.reduce((a, d) => { a[d.status] = (a[d.status] || 0) + 1; return a; }, {});
    setHTML('docStats', [
      ['Total', documentsCache.length, '#584ac0'],
      ['Verified', counts.Verified || 0, '#00b894'],
      ['Pending', counts.Pending || 0, '#e17055'],
      ['Rejected', counts.Rejected || 0, '#ff5a5a']
    ].map(([label, val, color]) => `
      <div class="keka-card p-5"><div class="text-xs uppercase tracking-widest text-[#8b8fa3]">${label}</div>
      <div class="font-display font-bold text-2xl mt-2" style="color:${color}">${val}</div></div>`).join(''));
    renderDocuments();
  } catch (e) { console.error(e); }
}

function renderDocuments() {
  const filter = document.getElementById('docFilter')?.value || 'All Status';
  const rows = filter === 'All Status' ? documentsCache : documentsCache.filter(d => d.status === filter);
  const tbody = document.getElementById('documentsTable');
  if (!tbody) return;
  tbody.innerHTML = rows.length ? rows.map(d => `
    <tr>
      <td class="py-3 font-medium"><i class="far fa-file-alt text-[#8b8fa3] mr-2"></i>${esc(d.name)}</td>
      <td class="py-3">${esc(d.employee_name)}</td>
      <td class="py-3"><span class="px-2 py-1 rounded-full bg-[#f6f7fb] text-xs">${esc(d.type)}</span></td>
      <td class="py-3 text-[#8b8fa3] text-xs">${esc(d.uploaded_at || '-')}</td>
      <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(d.status)}">${esc(d.status)}</span></td>
    </tr>`).join('') : emptyRow(5, 'No documents found');
}

// ---------- ORG CHART (was a "coming soon" card) ----------
async function loadOrgChart() {
  try {
    const data = await apiGet('/api/org-chart');
    setText('orgCount', `${data.total} people`);
    const node = (n, depth = 0) => `
      <div class="flex flex-col items-center">
        <div class="keka-card px-4 py-3 text-center min-w-[170px] ${depth === 0 ? 'border-2 border-[#584ac0]' : ''}">
          <div class="w-10 h-10 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center font-bold text-xs mx-auto">${esc(n.avatar || initials(n.name))}</div>
          <div class="font-semibold text-sm mt-2">${esc(n.name)}</div>
          <div class="text-[11px] text-[#8b8fa3]">${esc(n.title || '')}</div>
          ${n.department ? `<div class="text-[10px] mt-1 px-2 py-0.5 rounded-full bg-[#f6f7fb] inline-block">${esc(n.department)}</div>` : ''}
        </div>
        ${n.children && n.children.length ? `
          <div class="w-px h-5 bg-[#dfe3ee]"></div>
          <div class="flex gap-5 items-start border-t border-[#dfe3ee] pt-5 px-2">
            ${n.children.map(c => `<div class="relative"><div class="absolute -top-5 left-1/2 w-px h-5 bg-[#dfe3ee]"></div>${node(c, depth + 1)}</div>`).join('')}
          </div>` : ''}
      </div>`;
    setHTML('orgChart', `<div class="flex gap-8 justify-start lg:justify-center min-w-max pb-4">${data.roots.map(r => node(r)).join('')}</div>`
      || '<div class="text-sm text-[#8b8fa3]">No employees to chart</div>');
  } catch (e) { console.error(e); }
}

// ---------- TIMESHEET (was a "coming soon" card) ----------
async function loadTimesheet() {
  try {
    const ts = await apiGet('/api/timesheet');
    setText('tsRange', `${ts.week_start} → ${ts.week_end}`);
    setText('tsTotal', `${ts.total_hours}h`);
    setText('tsExpected', ts.expected_hours);
    const bar = document.getElementById('tsBar');
    if (bar) bar.style.width = Math.min(100, (ts.total_hours / ts.expected_hours) * 100) + '%';
    setHTML('timesheetGrid', ts.days.map(d => `
      <div class="rounded-xl border p-3 text-center ${d.is_today ? 'border-[#584ac0] bg-[#f7f6ff]' : 'border-[#eef0f6]'}">
        <div class="text-xs uppercase tracking-widest text-[#8b8fa3]">${esc(d.day)}</div>
        <div class="text-lg font-bold mt-1">${d.hours ? d.hours + 'h' : '—'}</div>
        <div class="text-[10px] text-[#8b8fa3] mt-1">${esc(d.clock_in || '')}${d.clock_out ? ' – ' + esc(d.clock_out) : ''}</div>
        <div class="mt-2"><span class="px-2 py-0.5 rounded-full text-[10px] ${statusColor(d.status)}">${esc(d.status)}</span></div>
      </div>`).join(''));
  } catch (e) { console.error(e); }
}

// ---------- REPORTS (was a "coming soon" card) ----------
async function loadReports() {
  try {
    const r = await apiGet('/api/reports');
    setHTML('reportKpis', [
      ['Total Employees', r.total_employees, ''],
      ['Attendance Today', r.attendance_rate + '%', `${r.present_today} present`],
      ['Pending Leaves', r.pending_leaves, `${r.approved_leaves} approved`],
      ['Average CTC', inr(r.avg_ctc), 'per annum']
    ].map(([label, val, sub]) => `
      <div class="keka-card p-5"><div class="text-xs uppercase tracking-widest text-[#8b8fa3]">${label}</div>
      <div class="font-display font-bold text-2xl mt-2">${val}</div>
      <div class="text-xs text-[#8b8fa3] mt-1">${sub}</div></div>`).join(''));

    const bars = (obj, color) => {
      const entries = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
      const max = Math.max(1, ...entries.map(e => e[1]));
      return entries.map(([k, v]) => `
        <div><div class="flex justify-between text-sm mb-1"><span>${esc(k)}</span><span class="font-semibold">${v}</span></div>
        <div class="w-full bg-[#f6f7fb] h-2 rounded-full"><div class="h-2 rounded-full" style="width:${v / max * 100}%;background:${color}"></div></div></div>`).join('')
        || '<div class="text-sm text-[#8b8fa3]">No data</div>';
    };
    setHTML('reportDept', bars(r.headcount_by_department, '#584ac0'));
    setHTML('reportLocation', bars(r.headcount_by_location, '#00b894'));
    setHTML('reportLeave', bars(r.leave_days_by_type, '#fdcb6e'));
    setHTML('reportStatus', bars(r.status_mix, '#0984e3'));
  } catch (e) { console.error(e); }
}

/** CSV export for the Reports tab */
async function exportCsv(kind) {
  const sources = {
    employees: ['/api/employees', ['employee_code', 'full_name', 'email', 'phone', 'department', 'designation', 'work_location', 'status', 'date_of_joining']],
    leave: ['/api/leave-requests', ['employee_name', 'leave_type', 'start_date', 'end_date', 'days', 'reason', 'status']],
    attendance: ['/api/attendance?scope=all', ['date', 'employee_name', 'clock_in', 'clock_out', 'work_hours', 'status']],
    expenses: ['/api/reimbursements', ['date', 'employee_name', 'category', 'description', 'amount', 'status']]
  };
  const [url, cols] = sources[kind] || [];
  if (!url) return;
  try {
    const rows = await apiGet(url);
    const csv = [cols.join(',')].concat(rows.map(r => cols.map(c => {
      const v = r[c] ?? '';
      return /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v;
    }).join(','))).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `${kind}-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click(); URL.revokeObjectURL(a.href);
    showToast(`${rows.length} rows exported`, 'success');
  } catch (e) { showToast(e.message, 'error'); }
}
window.exportCsv = exportCsv;

// ---------- MY PROFILE (was hardcoded "Admin User / 2.4 yrs / 12 / 4.6") ----------
async function loadMyProfile() {
  try {
    const [profile, balances, holidays, attendance] = await Promise.all([
      apiGet('/api/me'), apiGet('/api/leave-balances'), apiGet('/api/holidays'), apiGet('/api/attendance?scope=me')
    ]);
    me = profile;
    setText('meAvatar', profile.avatar || initials(profile.full_name));
    setText('meName', profile.full_name || '-');
    setText('meMeta', `${profile.designation || '-'} • ${profile.email || '-'}`);
    setHTML('meTags', [
      profile.employee_code && `#${profile.employee_code}`,
      profile.department, profile.work_location,
      profile.manager && profile.manager !== '-' && `Reports to ${profile.manager}`
    ].filter(Boolean).map(t => `<span class="px-2.5 py-1 rounded-full bg-[#f6f7fb] text-xs">${esc(t)}</span>`).join(''));

    let tenure = '-';
    if (profile.date_of_joining) {
      const years = (Date.now() - new Date(profile.date_of_joining).getTime()) / (365.25 * 864e5);
      tenure = years >= 1 ? years.toFixed(1) + ' yrs' : Math.max(0, Math.round(years * 12)) + ' mo';
    }
    const totalLeft = balances.reduce((a, b) => a + b.available, 0);
    const hoursThisMonth = attendance
      .filter(a => (a.date || '').startsWith(new Date().toISOString().slice(0, 7)))
      .reduce((a, b) => a + (b.work_hours || 0), 0);

    setHTML('meStats', [
      ['At Company', tenure], ['Leaves Left', totalLeft],
      ['Hours This Month', Math.round(hoursThisMonth) + 'h'], ['Status', profile.status || 'Active']
    ].map(([l, v]) => `<div class="bg-[#f6f7fb] rounded-xl p-4 text-center"><div class="font-bold text-lg">${esc(v)}</div><div class="text-xs text-[#8b8fa3] uppercase tracking-widest mt-1">${l}</div></div>`).join(''));

    setHTML('meBalances', balances.map(b => `
      <div><div class="flex justify-between text-sm mb-1"><span>${esc(b.name)}</span><span class="font-semibold">${b.available} / ${b.yearly_quota}</span></div>
      <div class="w-full bg-[#f6f7fb] h-2 rounded-full"><div class="h-2 rounded-full" style="width:${Math.min(100, b.used_pct)}%;background:${esc(b.color)}"></div></div></div>`).join(''));

    const upcoming = holidays.filter(h => h.upcoming).slice(0, 6);
    setHTML('meHolidays', upcoming.length ? upcoming.map(h => `
      <div class="flex justify-between items-center p-2.5 rounded-xl bg-[#f9fafe]">
        <div><div class="text-sm font-medium">${esc(h.name)}</div><div class="text-xs text-[#8b8fa3]">${esc(h.day)}</div></div>
        <span class="text-xs px-2 py-1 rounded-full bg-white border">${esc(h.date)}</span>
      </div>`).join('') : '<div class="text-sm text-[#8b8fa3]">No upcoming holidays</div>');
  } catch (e) { console.error(e); }
}

// ---------- MODALS ----------
function toggleModal(id, show) {
  const m = document.getElementById(id);
  if (!m) return;
  m.classList.toggle('hidden', !show);
  m.classList.toggle('flex', show);
}
function openAddEmployeeModal() { toggleModal('addEmployeeModal', true); }
function closeAddEmployeeModal() { toggleModal('addEmployeeModal', false); }
function openLeaveModal() { toggleModal('leaveModal', true); }
function closeLeaveModal() { toggleModal('leaveModal', false); }
function openJobModal() { toggleModal('jobModal', true); }
function closeJobModal() { toggleModal('jobModal', false); }
function openExpenseModal() { toggleModal('expenseModal', true); }
function closeExpenseModal() { toggleModal('expenseModal', false); }
Object.assign(window, { openAddEmployeeModal, closeAddEmployeeModal, openLeaveModal, closeLeaveModal, openJobModal, closeJobModal, openExpenseModal, closeExpenseModal });

// close on backdrop click / Escape
document.addEventListener('click', (e) => {
  if (e.target.classList?.contains('fixed') && e.target.id?.endsWith('Modal')) toggleModal(e.target.id, false);
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') ['addEmployeeModal', 'leaveModal', 'jobModal', 'expenseModal'].forEach(id => toggleModal(id, false));
});

// ---------- TOAST ----------
function showToast(msg, type = 'info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'fixed bottom-6 right-6 z-[100] space-y-2';
    document.body.appendChild(container);
  }
  const colors = { success: 'bg-[#00b894] text-white', error: 'bg-[#ff5a5a] text-white', info: 'bg-[#1e1f2b] text-white' };
  const toast = document.createElement('div');
  toast.className = `px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${colors[type] || colors.info} flex items-center gap-2 max-w-[360px]`;
  toast.style.transition = 'opacity .3s, transform .3s';
  toast.innerHTML = `<span>${esc(msg)}</span>`;
  container.appendChild(toast);
  // errors stay long enough to actually be read
  setTimeout(() => { toast.style.opacity = '0'; toast.style.transform = 'translateY(10px)'; setTimeout(() => toast.remove(), 300); },
    type === 'error' ? 6000 : 3000);
}
window.showToast = showToast;
