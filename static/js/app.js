// Keka HRMS Clone - Frontend Logic

let currentModule = 'home';
let employeesCache = [];
let attendanceCache = [];
let leaveCache = [];

// ---------- INIT ----------
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initClock();
  loadDashboard();
  loadEmployees();
  loadAttendance();
  loadLeave();
  loadPayroll();
  loadHiring();
  loadAnnouncements();
  loadGoals();
  setupSearchAndFilters();
});

function initNavigation() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const mod = el.dataset.module;
      if (mod) switchModule(mod);
    });
  });
}

function switchModule(mod) {
  currentModule = mod;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const activeNav = document.querySelector(`.nav-item[data-module="${mod}"]`);
  if (activeNav) activeNav.classList.add('active');

  document.querySelectorAll('.module-section').forEach(s => s.classList.remove('active'));
  const target = document.getElementById(`module-${mod}`);
  if (target) target.classList.add('active');
  else document.getElementById('module-home').classList.add('active');

  const titles = {
    home: ['Home', "Good morning, Admin! Here's what's happening today."],
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
    timesheet: ['Timesheet', 'Project time tracking'],
    expenses: ['Expenses', 'Reimbursements and claims'],
    reports: ['Reports', 'Analytics and custom reports']
  };
  const t = titles[mod] || titles.home;
  document.getElementById('pageTitle').textContent = t[0];
  document.getElementById('pageSubtitle').textContent = t[1];

  // Lazy load
  if (mod === 'employees') loadEmployees();
  if (mod === 'attendance') loadAttendance();
  if (mod === 'leave') loadLeave();
  if (mod === 'payroll') loadPayroll();
  if (mod === 'hiring') loadHiring();
}
window.switchModule = switchModule;

// ---------- CLOCK ----------
function initClock() {
  const updateClock = () => {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    const clockEl = document.getElementById('liveClock');
    const dateEl = document.getElementById('liveDate');
    if (clockEl) clockEl.textContent = timeStr;
    if (dateEl) dateEl.textContent = dateStr;
  };
  updateClock();
  setInterval(updateClock, 1000);

  document.getElementById('btnClockIn')?.addEventListener('click', () => clockAction('clock_in'));
  document.getElementById('btnClockOut')?.addEventListener('click', () => clockAction('clock_out'));
}

async function clockAction(action) {
  const btnIn = document.getElementById('btnClockIn');
  const btnOut = document.getElementById('btnClockOut');
  const statusEl = document.getElementById('clockStatus');
  const origIn = btnIn.innerHTML, origOut = btnOut.innerHTML;
  btnIn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
  try {
    const res = await fetch('/api/attendance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action })
    });
    const responseText = await res.text();
    let data;
    try {
      data = JSON.parse(responseText);
    } catch {
      throw new Error(`Server returned HTTP ${res.status} instead of JSON`);
    }
    if (!res.ok) throw new Error(data.error || 'Attendance request failed');
    if (statusEl) {
      statusEl.innerHTML = `<div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div><span class="text-sm">${data.message} • ${data.attendance.clock_in || ''}</span>`;
    }
    loadAttendance();
    loadDashboard();
    showToast(data.message, 'success');
  } catch (e) {
    showToast(e.message || 'Failed to clock', 'error');
  } finally {
    btnIn.innerHTML = origIn;
    btnOut.innerHTML = origOut;
  }
}

// ---------- DASHBOARD ----------
async function loadDashboard() {
  try {
    const [statsRes, annRes, leaveRes] = await Promise.all([
      fetch('/api/stats').then(r => r.json()),
      fetch('/api/announcements').then(r => r.json()),
      fetch('/api/leave-requests').then(r => r.json())
    ]);

    document.getElementById('statTotalEmp').textContent = statsRes.total_employees;
    document.getElementById('statPresent').textContent = statsRes.present_today;
    document.getElementById('statOnLeave').textContent = statsRes.on_leave;
    document.getElementById('statOpenJobs').textContent = statsRes.open_positions;
    document.getElementById('statAttendanceRate').textContent = statsRes.attendance_rate + '%';

    // Charts
    renderAttendanceChart();
    renderDeptChart(statsRes.department_distribution);

    // Pending approvals
    const pending = leaveRes.filter(l => l.status === 'Pending').slice(0, 4);
    const pendingEl = document.getElementById('pendingApprovals');
    if (pendingEl) {
      pendingEl.innerHTML = pending.map(l => `
        <div class="flex items-center gap-3 p-3 rounded-xl hover:bg-[#f6f7fb] transition cursor-pointer">
          <div class="w-9 h-9 rounded-full bg-[#eef0ff] flex items-center justify-center text-[#584ac0] font-bold text-xs">${(l.employee_name||'U').split(' ').map(w=>w[0]).join('').slice(0,2)}</div>
          <div class="flex-1 min-w-0">
            <div class="text-[13px] font-medium truncate">${l.employee_name || 'Employee'} • ${l.leave_type || 'Leave'}</div>
            <div class="text-xs text-[#8b8fa3]">${l.days} day(s) • ${l.start_date}</div>
          </div>
          <div class="flex gap-1">
            <button onclick="handleLeaveAction('${l.id}','Approved')" class="w-7 h-7 rounded-full bg-[#e6f9f0] text-[#00b894] flex items-center justify-center hover:bg-[#00b894] hover:text-white transition"><i class="fas fa-check text-xs"></i></button>
            <button onclick="handleLeaveAction('${l.id}','Rejected')" class="w-7 h-7 rounded-full bg-[#ffecec] text-[#ff5a5a] flex items-center justify-center hover:bg-[#ff5a5a] hover:text-white transition"><i class="fas fa-times text-xs"></i></button>
          </div>
        </div>
      `).join('') || '<div class="text-sm text-[#8b8fa3] text-center py-4">No pending requests 🎉</div>';
    }

    // Inbox
    const inboxEl = document.getElementById('inboxList');
    if (inboxEl) inboxEl.innerHTML = pending.map(l => `
      <div class="p-4 rounded-xl border border-[#eef0f6] flex justify-between items-center">
        <div class="flex gap-3"><div class="w-10 h-10 rounded-full bg-[#584ac0] text-white flex items-center justify-center font-bold text-sm">${(l.employee_name||'U')[0]}</div><div><div class="font-medium text-sm">${l.employee_name} requested ${l.leave_type}</div><div class="text-xs text-[#8b8fa3]">${l.reason} • ${l.start_date} to ${l.end_date}</div></div></div>
        <div class="flex gap-2"><button onclick="handleLeaveAction('${l.id}','Approved')" class="px-3 py-1.5 rounded-full bg-[#1e1f2b] text-white text-xs">Approve</button><button onclick="handleLeaveAction('${l.id}','Rejected')" class="px-3 py-1.5 rounded-full border text-xs">Reject</button></div>
      </div>
    `).join('');

  } catch (e) { console.error('Dashboard load error', e); }
}

function renderAttendanceChart() {
  const ctx = document.getElementById('attendanceChart');
  if (!ctx) return;
  if (ctx.chart) ctx.chart.destroy();
  ctx.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Today'],
      datasets: [{
        label: 'Present %',
        data: [88, 92, 85, 90, 94, 60, 92],
        borderColor: '#584ac0',
        backgroundColor: (context) => {
          const bg = context.chart.ctx.createLinearGradient(0,0,0,200);
          bg.addColorStop(0, 'rgba(88,74,192,0.2)');
          bg.addColorStop(1, 'rgba(88,74,192,0)');
          return bg;
        },
        fill: true,
        tension: 0.4,
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { grid: { display: false } }, y: { display: false, min: 50, max: 100 } }
    }
  });
}

function renderDeptChart(dist) {
  const ctx = document.getElementById('deptChart');
  const legendEl = document.getElementById('deptLegend');
  if (!ctx) return;
  const labels = Object.keys(dist || { Engineering: 42, Sales: 25, Design: 9, Marketing: 12 });
  const values = Object.values(dist || { Engineering: 42, Sales: 25, Design: 9, Marketing: 12 });
  const colors = ['#584ac0', '#00b894', '#fdcb6e', '#e17055', '#0984e3', '#6c5ce7'];
  if (ctx.chart) ctx.chart.destroy();
  ctx.chart = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '68%', plugins: { legend: { display: false } } }
  });
  if (legendEl) {
    legendEl.innerHTML = labels.map((l,i) => `
      <div class="flex justify-between items-center"><div class="flex items-center gap-2"><span class="w-2.5 h-2.5 rounded-full" style="background:${colors[i%colors.length]}"></span><span class="text-[#1e1f2b]">${l}</span></div><span class="font-semibold">${values[i]}</span></div>
    `).join('');
  }
}

// ---------- EMPLOYEES ----------
async function loadEmployees() {
  try {
    const search = document.getElementById('empSearch')?.value || '';
    const dept = document.getElementById('deptFilter')?.value || 'All';
    const status = document.getElementById('statusFilter')?.value || 'All';
    const res = await fetch(`/api/employees?search=${encodeURIComponent(search)}&department=${encodeURIComponent(dept)}&status=${encodeURIComponent(status)}`);
    const data = await res.json();
    employeesCache = data;
    renderEmployeesTable(data);
    document.getElementById('empCount').textContent = `${data.length} employees`;

    // Populate dept select in modal
    const deptRes = await fetch('/api/departments').then(r=>r.json());
    const modalSelect = document.getElementById('modalDeptSelect');
    if (modalSelect) {
      modalSelect.innerHTML = deptRes.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
    }
  } catch (e) { console.error(e); }
}

function renderEmployeesTable(employees) {
  const tbody = document.getElementById('employeesTable');
  if (!tbody) return;
  tbody.innerHTML = employees.map(emp => `
    <tr class="hover:bg-[#f9fafe] transition">
      <td class="px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center font-bold text-xs">${emp.avatar || (emp.full_name||'U').split(' ').map(w=>w[0]).join('').slice(0,2)}</div>
          <div><div class="font-semibold text-[#1e1f2b]">${emp.full_name}</div><div class="text-xs text-[#8b8fa3]">${emp.employee_code} • ${emp.email}</div></div>
        </div>
      </td>
      <td class="px-4 py-4"><span class="px-2.5 py-1 rounded-full bg-[#f6f7fb] text-xs font-medium">${emp.department || 'Engineering'}</span></td>
      <td class="px-4 py-4 text-[#1e1f2b]">${emp.designation || emp.designation_id || '-'}</td>
      <td class="px-4 py-4">${emp.work_location || 'Bangalore'}</td>
      <td class="px-4 py-4"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(emp.status)}">${emp.status}</span></td>
      <td class="px-4 py-4 text-[#8b8fa3] text-xs">${emp.date_of_joining || '-'}</td>
      <td class="px-6 py-4 text-right"><button class="w-8 h-8 rounded-full hover:bg-[#f6f7fb]"><i class="fas fa-ellipsis-h text-[#8b8fa3] text-xs"></i></button></td>
    </tr>
  `).join('');
}

function statusColor(s) {
  if (s === 'Active') return 'bg-[#e6f9f0] text-[#00b894]';
  if (s === 'On Leave') return 'bg-[#fff4e6] text-[#e17055]';
  if (s === 'Probation') return 'bg-[#eef0ff] text-[#584ac0]';
  return 'bg-[#f6f7fb] text-[#8b8fa3]';
}

function setupSearchAndFilters() {
  document.getElementById('empSearch')?.addEventListener('input', debounce(loadEmployees, 300));
  document.getElementById('deptFilter')?.addEventListener('change', loadEmployees);
  document.getElementById('statusFilter')?.addEventListener('change', loadEmployees);
  document.getElementById('globalSearch')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase();
    if (q.length > 1) {
      const filtered = employeesCache.filter(emp => emp.full_name.toLowerCase().includes(q));
      if (filtered.length) { switchModule('employees'); renderEmployeesTable(filtered); }
    }
  });

  document.querySelectorAll('.leave-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.leave-tab').forEach(t=>t.classList.remove('active','bg-[#1e1f2b]','text-white'));
      document.querySelectorAll('.leave-tab').forEach(t=>t.classList.add('bg-[#f6f7fb]'));
      tab.classList.add('active','bg-[#1e1f2b]','text-white');
      tab.classList.remove('bg-[#f6f7fb]');
      loadLeave(tab.dataset.status);
    });
  });

  // Forms
  document.getElementById('addEmployeeForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    try {
      const res = await fetch('/api/employees', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const responseText = await res.text();
      let data;
      try {
        data = JSON.parse(responseText);
      } catch {
        throw new Error(`Server returned HTTP ${res.status} instead of JSON`);
      }
      if (!res.ok) throw new Error(data.error || 'Employee creation failed');
      closeAddEmployeeModal();
      loadEmployees();
      loadDashboard();
      showToast('Employee added successfully', 'success');
      e.target.reset();
    } catch (err) { showToast(err.message || 'Failed to add employee', 'error'); }
  });

  document.getElementById('leaveForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = Object.fromEntries(fd.entries());
    const start = new Date(payload.start_date), end = new Date(payload.end_date);
    const days = Math.ceil((end - start)/ (1000*60*60*24)) + 1;
    payload.days = days;
    payload.employee_name = 'Admin User';
    payload.leave_type = document.getElementById('leaveTypeSelect').selectedOptions[0]?.text || 'Casual Leave';
    try {
      await fetch('/api/leave-requests', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      closeLeaveModal();
      loadLeave();
      loadDashboard();
      showToast('Leave applied successfully', 'success');
      e.target.reset();
    } catch (err) { showToast('Failed to apply leave', 'error'); }
  });
}

function debounce(fn, delay) {
  let t; return (...args) => { clearTimeout(t); t = setTimeout(()=>fn(...args), delay); };
}

// ---------- ATTENDANCE ----------
async function loadAttendance() {
  try {
    const res = await fetch('/api/attendance');
    const data = await res.json();
    attendanceCache = data;
    const tbody = document.getElementById('attendanceTable');
    if (!tbody) return;
    tbody.innerHTML = data.slice(0,15).map(a => `
      <tr>
        <td class="py-3 font-medium">${a.date}</td>
        <td class="py-3"><span class="px-2 py-1 rounded-full bg-[#e6f9f0] text-[#00b894] text-xs">${a.clock_in || '--'}</span></td>
        <td class="py-3">${a.clock_out ? `<span class="px-2 py-1 rounded-full bg-[#eef0ff] text-[#584ac0] text-xs">${a.clock_out}</span>` : '<span class="text-[#8b8fa3]">--</span>'}</td>
        <td class="py-3 font-semibold">${a.work_hours ? a.work_hours + 'h' : '--'}</td>
        <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${statusColor(a.status)}">${a.status}</span></td>
        <td class="py-3"><button class="text-xs text-[#584ac0] font-medium">Regularize</button></td>
      </tr>
    `).join('');
  } catch (e) { console.error(e); }
}

// ---------- LEAVE ----------
async function loadLeave(filterStatus = 'All') {
  try {
    const [leaveRes, typesRes] = await Promise.all([
      fetch(`/api/leave-requests${filterStatus !== 'All' ? `?status=${filterStatus}` : ''}`).then(r=>r.json()),
      fetch('/api/leave-types').then(r=>r.json())
    ]);
    leaveCache = leaveRes;

    // Balances
    const balancesEl = document.getElementById('leaveBalances');
    if (balancesEl) {
      balancesEl.innerHTML = typesRes.map(t => `
        <div class="keka-card p-5 border-l-4" style="border-left-color:${t.color}">
          <div class="flex justify-between items-start"><div class="w-9 h-9 rounded-xl flex items-center justify-center text-white text-sm" style="background:${t.color}"><i class="far fa-calendar"></i></div><span class="text-xs px-2 py-1 rounded-full bg-[#f6f7fb]">${t.yearly_quota} / year</span></div>
          <div class="mt-3"><div class="font-semibold">${t.name}</div><div class="text-2xl font-bold mt-1">${Math.floor(Math.random()*6)+6} <span class="text-sm font-normal text-[#8b8fa3]">left</span></div></div>
          <div class="w-full bg-[#f6f7fb] h-1.5 rounded-full mt-3"><div class="h-1.5 rounded-full" style="width:${60+Math.random()*30}%; background:${t.color}"></div></div>
        </div>
      `).join('');
    }

    // Table
    const tbody = document.getElementById('leaveTable');
    if (tbody) {
      tbody.innerHTML = leaveRes.map(l => `
        <tr>
          <td class="py-3"><div class="flex items-center gap-2"><div class="w-7 h-7 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center text-[10px] font-bold">${(l.employee_name||'U')[0]}</div><span class="font-medium">${l.employee_name || 'Employee'}</span></div></td>
          <td class="py-3"><span class="px-2 py-1 rounded-full bg-[#f6f7fb] text-xs">${l.leave_type || 'Casual Leave'}</span></td>
          <td class="py-3 text-xs">${l.start_date} → ${l.end_date}</td>
          <td class="py-3 font-semibold">${l.days}d</td>
          <td class="py-3 text-xs text-[#8b8fa3] max-w-[150px] truncate">${l.reason || '-'}</td>
          <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs font-medium ${l.status==='Approved'?'bg-[#e6f9f0] text-[#00b894]': l.status==='Pending'?'bg-[#fff4e6] text-[#e17055]':'bg-[#ffecec] text-[#ff5a5a]'}">${l.status}</span></td>
          <td class="py-3 text-right">
            ${l.status==='Pending' ? `<div class="flex gap-1 justify-end"><button onclick="handleLeaveAction('${l.id}','Approved')" class="px-2.5 py-1 rounded-full bg-[#1e1f2b] text-white text-xs">Approve</button><button onclick="handleLeaveAction('${l.id}','Rejected')" class="px-2.5 py-1 rounded-full border text-xs">Reject</button></div>` : '<span class="text-xs text-[#8b8fa3]">—</span>'}
          </td>
        </tr>
      `).join('');
    }

    // Leave type select
    const typeSelect = document.getElementById('leaveTypeSelect');
    if (typeSelect) {
      typeSelect.innerHTML = typesRes.map(t => `<option value="${t.id}">${t.name} (${t.code}) - ${t.yearly_quota} days/year</option>`).join('');
    }

    // Mini calendar
    renderMiniCalendar();
  } catch (e) { console.error(e); }
}

async function handleLeaveAction(id, status) {
  try {
    await fetch(`/api/leave-requests/${id}/action`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) });
    loadLeave();
    loadDashboard();
    showToast(`Leave ${status.toLowerCase()}`, 'success');
  } catch (e) { showToast('Action failed', 'error'); }
}
window.handleLeaveAction = handleLeaveAction;

function renderMiniCalendar() {
  const el = document.getElementById('miniCalendar');
  if (!el) return;
  const daysInMonth = 31;
  let html = '';
  for (let i=1;i<=daysInMonth;i++) {
    const isToday = i===29;
    const hasLeave = [5,12,20].includes(i);
    html += `<div class="h-8 flex items-center justify-center rounded-full ${isToday?'bg-[#1e1f2b] text-white font-bold': hasLeave?'bg-[#eef0ff] text-[#584ac0] font-semibold':''}">${i}</div>`;
  }
  el.innerHTML = html;
}

// ---------- PAYROLL ----------
async function loadPayroll() {
  try {
    const res = await fetch('/api/payslips');
    const data = await res.json();
    const tbody = document.getElementById('payslipTable');
    if (!tbody) return;
    // Merge with employees for display
    const emps = employeesCache.length ? employeesCache : await fetch('/api/employees').then(r=>r.json());
    const display = data.length ? data : emps.slice(0,5).map((e,i)=>({ employee_name: e.full_name, month: 8, year: 2026, gross: 150000, deductions: 18000, net: 132000, status: i%2?'Generated':'Paid' }));
    tbody.innerHTML = display.map(p => `
      <tr>
        <td class="py-3 font-medium">${p.employee_name || p.employee_id || 'Employee'}</td>
        <td class="py-3">${p.month}/${p.year}</td>
        <td class="py-3">₹${(p.gross||p.gross_earnings||0).toLocaleString()}</td>
        <td class="py-3 text-[#e17055]">-₹${(p.deductions||p.total_deductions||0).toLocaleString()}</td>
        <td class="py-3 font-bold">₹${(p.net||p.net_pay||0).toLocaleString()}</td>
        <td class="py-3"><span class="px-2.5 py-1 rounded-full text-xs ${p.status==='Paid'?'bg-[#e6f9f0] text-[#00b894]':'bg-[#eef0ff] text-[#584ac0]'}">${p.status}</span></td>
        <td class="py-3 text-right"><button class="px-3 py-1 rounded-full border text-xs hover:bg-[#f6f7fb]">View</button></td>
      </tr>
    `).join('');
  } catch (e) { console.error(e); }
}

// ---------- HIRING ----------
async function loadHiring() {
  try {
    const [jobsRes, candRes] = await Promise.all([
      fetch('/api/jobs').then(r=>r.json()),
      fetch('/api/candidates').then(r=>r.json())
    ]);
    const grid = document.getElementById('jobsGrid');
    if (grid) {
      grid.innerHTML = jobsRes.map(j => `
        <div class="keka-card p-5 hover:shadow-lg transition cursor-pointer">
          <div class="flex justify-between items-start"><h4 class="font-semibold">${j.title}</h4><span class="px-2 py-1 rounded-full text-xs ${j.status==='Open'?'bg-[#e6f9f0] text-[#00b894]':'bg-[#fff4e6] text-[#e17055]'}">${j.status}</span></div>
          <div class="text-xs text-[#8b8fa3] mt-1">${j.department} • ${j.location} • ${j.openings} opening(s)</div>
          <div class="flex items-center gap-2 mt-4"><div class="flex -space-x-1"><div class="w-6 h-6 rounded-full bg-[#eef0ff] border-2 border-white"></div><div class="w-6 h-6 rounded-full bg-[#ffeaa7] border-2 border-white"></div></div><span class="text-xs text-[#8b8fa3]">${j.applicants || 0} applicants</span></div>
        </div>
      `).join('');
    }
    const candEl = document.getElementById('candidatesList');
    if (candEl) {
      candEl.innerHTML = candRes.map(c => `
        <div class="flex items-center justify-between p-3 rounded-xl border border-[#eef0f6] hover:bg-[#f9fafe] transition">
          <div class="flex items-center gap-3"><div class="w-9 h-9 rounded-full bg-[#1e1f2b] text-white flex items-center justify-center font-bold text-xs">${c.full_name.split(' ').map(w=>w[0]).join('').slice(0,2)}</div><div><div class="font-medium text-sm">${c.full_name}</div><div class="text-xs text-[#8b8fa3]">${c.email} • ${c.experience||c.experience_years||''} exp</div></div></div>
          <div class="flex items-center gap-3"><span class="px-2.5 py-1 rounded-full bg-[#f6f7fb] text-xs">${c.stage}</span><div class="flex text-amber-400 text-xs">${'★'.repeat(c.rating)}${'☆'.repeat(5-c.rating)}</div></div>
        </div>
      `).join('');
    }
  } catch (e) { console.error(e); }
}

// ---------- ANNOUNCEMENTS & GOALS ----------
async function loadAnnouncements() {
  try {
    const res = await fetch('/api/announcements').then(r=>r.json());
    const el = document.getElementById('announcementsList');
    if (!el) return;
    el.innerHTML = res.map(a => `
      <div class="p-3 rounded-xl border ${a.is_pinned ? 'bg-[#fffbeb] border-amber-200' : 'bg-[#f9fafe] border-[#eef0f6]'}">
        <div class="flex gap-2"><span class="text-xs px-2 py-0.5 rounded-full ${a.type==='Policy'?'bg-[#eef0ff] text-[#584ac0]': a.type==='Event'?'bg-[#e6f9f0] text-[#00b894]':'bg-white border text-[#8b8fa3]'}">${a.type}</span>${a.is_pinned ? '<span class="text-xs">📌 Pinned</span>' : ''}</div>
        <div class="font-medium text-sm mt-2">${a.title}</div>
        <div class="text-xs text-[#8b8fa3] mt-1 line-clamp-2">${a.content}</div>
        <div class="text-[11px] text-[#8b8fa3] mt-2">${a.date || a.created_at?.slice(0,10) || ''}</div>
      </div>
    `).join('');
  } catch (e) {}
}

async function loadGoals() {
  try {
    const res = await fetch('/api/goals').then(r=>r.json());
    const el = document.getElementById('goalsList');
    if (!el) return;
    el.innerHTML = res.map(g => `
      <div class="p-4 rounded-xl border border-[#eef0f6]">
        <div class="flex justify-between items-start"><div class="font-medium">${g.title}</div><span class="px-2 py-1 rounded-full text-xs ${g.status==='Completed'?'bg-[#e6f9f0] text-[#00b894]': g.status==='At Risk'?'bg-[#ffecec] text-[#ff5a5a]':'bg-[#eef0ff] text-[#584ac0]'}">${g.status}</span></div>
        <div class="w-full bg-[#f6f7fb] h-2 rounded-full mt-3"><div class="bg-[#584ac0] h-2 rounded-full" style="width:${g.progress}%"></div></div>
        <div class="flex justify-between text-xs mt-2"><span class="text-[#8b8fa3]">Progress</span><span class="font-semibold">${g.progress}%</span></div>
        <div class="text-xs text-[#8b8fa3] mt-2">Due: ${g.due_date}</div>
      </div>
    `).join('');
  } catch (e) {}
}

// ---------- MODALS ----------
function openAddEmployeeModal() {
  document.getElementById('addEmployeeModal').classList.remove('hidden');
  document.getElementById('addEmployeeModal').classList.add('flex');
}
function closeAddEmployeeModal() {
  document.getElementById('addEmployeeModal').classList.add('hidden');
  document.getElementById('addEmployeeModal').classList.remove('flex');
}
function openLeaveModal() {
  document.getElementById('leaveModal').classList.remove('hidden');
  document.getElementById('leaveModal').classList.add('flex');
}
function closeLeaveModal() {
  document.getElementById('leaveModal').classList.add('hidden');
  document.getElementById('leaveModal').classList.remove('flex');
}
window.openAddEmployeeModal = openAddEmployeeModal;
window.closeAddEmployeeModal = closeAddEmployeeModal;
window.openLeaveModal = openLeaveModal;
window.closeLeaveModal = closeLeaveModal;

function openJobModal() {
  showToast('Job creation modal - Implement form similar to employee', 'info');
}
window.openJobModal = openJobModal;

// ---------- TOAST ----------
function showToast(msg, type='info') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'fixed bottom-6 right-6 z-[100] space-y-2';
    document.body.appendChild(container);
  }
  const colors = { success: 'bg-[#00b894] text-white', error: 'bg-[#ff5a5a] text-white', info: 'bg-[#1e1f2b] text-white' };
  const toast = document.createElement('div');
  toast.className = `px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${colors[type]||colors.info} flex items-center gap-2 animate-[fadeIn_0.3s]`;
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(()=>{ toast.style.opacity='0'; toast.style.transform='translateY(10px)'; setTimeout(()=>toast.remove(),300); }, 3000);
}
