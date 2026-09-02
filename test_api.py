"""End-to-end API test for the dashboard - runs against mock data on port 5001."""
import json
import urllib.request
import re

BASE = 'http://127.0.0.1:5001'
PASS, FAIL = [], []


def check_html_balance():
    """Naive tag balance check for dashboard.html"""
    html = open('templates/dashboard.html', encoding='utf-8').read()
    counts = {}
    for tag in ('div', 'aside', 'main', 'header', 'nav', 'form', 'table', 'span', 'button'):
        opens = len(re.findall(r'<' + tag + r'[\s>]', html))
        closes = len(re.findall(r'</' + tag + r'>', html))
        counts[tag] = opens - closes
    bad = {k: v for k, v in counts.items() if v != 0}
    print('HTML TAG BALANCE:', 'OK' if not bad else f'MISMATCH {bad}')



def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data) as r:
            raw = r.read().decode()
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw  # non-JSON (HTML page)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'} | {name} {('- ' + str(detail)) if detail and not cond else ''}")


# 1. Health - must be mock mode (no Supabase)
s, d = call('GET', '/api/health')
check('health 200', s == 200, s)
check('mock mode active', d.get('mock_mode') is True and d.get('supabase_connected') is False, d)

# 2. Dashboard page renders (HTML)
s, d = call('GET', '/dashboard')
check('dashboard page 200', s == 200 and isinstance(d, str) and 'module-home' in d, s)
check_html_balance()

# 3. Stats
s, d = call('GET', '/api/stats')
check('stats 200', s == 200, s)
check('stats has total_employees', isinstance(d.get('total_employees'), int), d)

# 4. Employees GET + POST
s, emps = call('GET', '/api/employees')
check('employees GET 200', s == 200 and isinstance(emps, list) and len(emps) > 0, s)
s, new_emp = call('POST', '/api/employees', {'full_name': 'Test Person', 'email': 'test.person@company.com', 'department_id': 'd1', 'designation': 'QA Engineer'})
check('employees POST ok', s == 200 and new_emp.get('id'), (s, new_emp))
s, emps2 = call('GET', '/api/employees?search=Test')
check('new employee searchable', any(e.get('email') == 'test.person@company.com' for e in emps2), emps2)

# 5. Leave: the user's main complaint - apply leave then verify it shows
s, leaves_before = call('GET', '/api/leave-requests')
count_before = len(leaves_before)
s, new_leave = call('POST', '/api/leave-requests', {
    'start_date': '2026-09-10', 'end_date': '2026-09-12', 'days': 3,
    'reason': 'Family function', 'employee_id': 'e1', 'employee_name': 'Admin User',
    'leave_type': 'Casual Leave', 'leave_type_id': 'Casual Leave'
})
check('leave POST ok + has id', s == 200 and new_leave.get('id'), (s, new_leave))
check('leave status Pending', new_leave.get('status') == 'Pending', new_leave.get('status'))
s, leaves_after = call('GET', '/api/leave-requests')
check('applied leave now shows in list', len(leaves_after) == count_before + 1 and any(l.get('id') == new_leave.get('id') for l in leaves_after), (count_before, len(leaves_after)))
s, pending = call('GET', '/api/leave-requests?status=Pending')
check('leave status filter works', any(l.get('id') == new_leave.get('id') for l in pending), len(pending))

# 6. Leave approve/reject action
s, acted = call('POST', f"/api/leave-requests/{new_leave['id']}/action", {'status': 'Approved'})
check('leave approve action', s == 200 and acted.get('status') == 'Approved', (s, acted))

# 7. Attendance GET + clock in/out
s, att = call('GET', '/api/attendance')
check('attendance GET 200', s == 200 and isinstance(att, list), s)
s, d = call('POST', '/api/attendance', {'action': 'clock_in'})
check('clock in ok', s == 200 and d.get('attendance', {}).get('clock_in'), (s, d))
s, d = call('POST', '/api/attendance', {'action': 'clock_out'})
check('clock out ok', s == 200 and d.get('attendance', {}).get('clock_out'), (s, d))

# 8. Departments
s, d = call('GET', '/api/departments')
check('departments 200', s == 200 and len(d) >= 6, s)

# 9. Jobs GET + POST
s, jobs = call('GET', '/api/jobs')
check('jobs GET 200', s == 200 and len(jobs) > 0, s)
s, new_job = call('POST', '/api/jobs', {'title': 'DevOps Engineer', 'department': 'Engineering', 'location': 'Bangalore', 'openings': 2, 'description': 'K8s + CI/CD'})
check('jobs POST ok + has id', s == 200 and new_job.get('id'), (s, new_job))
s, jobs2 = call('GET', '/api/jobs')
check('new job shows in list', any(j.get('title') == 'DevOps Engineer' for j in jobs2), len(jobs2))

# 10-12. Candidates, Payslips, Announcements
s, cands = call('GET', '/api/candidates')
check('candidates 200', s == 200 and len(cands) > 0, s)
s, ps = call('GET', '/api/payslips')
check('payslips 200', s == 200 and len(ps) > 0, s)
s, ann = call('GET', '/api/announcements')
check('announcements 200', s == 200 and len(ann) > 0, s)

# 13. Goals GET + POST
s, goals = call('GET', '/api/goals')
check('goals GET 200', s == 200 and len(goals) > 0, s)
s, new_goal = call('POST', '/api/goals', {'title': 'Ship dashboard fixes', 'progress': 50})
check('goals POST ok + has id', s == 200 and new_goal.get('id'), (s, new_goal))
s, goals2 = call('GET', '/api/goals')
check('new goal shows in list', any(g.get('title') == 'Ship dashboard fixes' for g in goals2), len(goals2))

# 14. Reimbursements GET + POST (expenses module)
s, rexp = call('GET', '/api/reimbursements')
check('reimbursements GET has mock data', s == 200 and len(rexp) > 0, (s, rexp))
s, new_exp = call('POST', '/api/reimbursements', {'category': 'Travel', 'amount': '2500', 'date': '2026-09-01', 'description': 'Airport taxi', 'employee_id': 'e1', 'employee_name': 'Admin User'})
check('reimbursement POST ok + has id', s == 200 and new_exp.get('id'), (s, new_exp))
check('reimbursement amount numeric', new_exp.get('amount') == 2500.0, new_exp.get('amount'))
s, rexp2 = call('GET', '/api/reimbursements')
check('new expense shows in list', any(x.get('id') == new_exp.get('id') for x in rexp2), len(rexp2))
s, _ = call('POST', '/api/reimbursements', {'category': 'Food', 'amount': 'bad'})
check('reimbursement rejects bad amount', s == 400, s)

# 15. Leave types + holidays
s, lt = call('GET', '/api/leave-types')
check('leave types 200', s == 200 and len(lt) >= 4, s)
s, hol = call('GET', '/api/holidays')
check('holidays has mock data', s == 200 and len(hol) > 0, (s, hol))

# 16. Employee DELETE (cleanup test employee)
if new_emp.get('id'):
    s, d = call('DELETE', f"/api/employees/{new_emp['id']}")
    check('employee DELETE ok', s == 200 and d.get('success'), (s, d))

print('\n==============================')
print(f'RESULT: {len(PASS)} passed, {len(FAIL)} failed')
if FAIL:
    print('FAILED:', ', '.join(FAIL))
print('==============================')
