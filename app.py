"""
Ekkaa HRMS - Python Flask + Supabase
Complete HRMS with all core HR features
"""
import os
import uuid
from datetime import datetime, date, timedelta
from functools import wraps
from dotenv import load_dotenv

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "keka-clone-secret-key-2026-super-secure")
CORS(app)

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SECRET_KEY")
USE_MOCK = os.getenv("USE_MOCK_DATA", "false").lower() == "true"

supabase = None
supabase_key_source = None
supabase_error = None

if SUPABASE_URL and not USE_MOCK:
    key_candidates = []
    if SUPABASE_SERVICE_KEY:
        key_candidates.append(("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY))
    if SUPABASE_KEY:
        key_candidates.append(("SUPABASE_KEY", SUPABASE_KEY))

    if not key_candidates:
        print("⚠️ Using MOCK DATA (SUPABASE_KEY not found). Set SUPABASE_URL and SUPABASE_KEY in .env to use real DB")
    else:
        for key_name, key_value in key_candidates:
            try:
                from supabase import create_client
                supabase = create_client(SUPABASE_URL, key_value)
                supabase_key_source = key_name
                print(f"✅ Connected to Supabase using {key_name}: {SUPABASE_URL}")
                break
            except Exception as e:
                supabase_error = str(e)
                print(f"⚠️ {key_name} rejected by Supabase for {SUPABASE_URL}: {e}")

        if supabase is None:
            print("⚠️ Supabase credentials invalid or project unreachable; using mock data")
else:
    print("⚠️ Using MOCK DATA (Supabase disabled or USE_MOCK_DATA=true). Set SUPABASE_URL and SUPABASE_KEY in .env to use real DB")

# ---------------- MOCK DATA STORE (Fallback when Supabase not configured) ----------------
mock_db = {
    "departments": [
        {"id": "d1", "name": "Engineering", "description": "Product and Engineering", "employee_count": 42},
        {"id": "d2", "name": "Human Resources", "description": "HR and People Ops", "employee_count": 8},
        {"id": "d3", "name": "Sales", "description": "Sales and Business Dev", "employee_count": 25},
        {"id": "d4", "name": "Marketing", "description": "Marketing and Growth", "employee_count": 12},
        {"id": "d5", "name": "Finance", "description": "Finance and Accounting", "employee_count": 6},
        {"id": "d6", "name": "Design", "description": "Product Design", "employee_count": 9},
    ],
    "employees": [
        {"id": "e1", "employee_code": "KEKA001", "full_name": "Aarav Sharma", "email": "aarav.sharma@company.com", "phone": "+91 98765 43210", "department_id": "d1", "department": "Engineering", "designation": "Senior Software Engineer", "manager": "Priya Nair", "date_of_joining": "2022-03-15", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "AS", "salary_ctc": 1800000, "date_of_birth": "1997-09-02"},
        {"id": "e2", "employee_code": "KEKA002", "full_name": "Priya Nair", "email": "priya.nair@company.com", "phone": "+91 98765 43211", "department_id": "d1", "department": "Engineering", "designation": "Engineering Manager", "manager": "Vikram Singh", "date_of_joining": "2020-01-10", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "PN", "salary_ctc": 3200000, "date_of_birth": "1994-09-02"},
        {"id": "e3", "employee_code": "KEKA003", "full_name": "Rohan Mehta", "email": "rohan.mehta@company.com", "phone": "+91 98765 43212", "department_id": "d3", "department": "Sales", "designation": "Sales Executive", "manager": "Ananya Gupta", "date_of_joining": "2023-06-01", "status": "Active", "employment_type": "Full-time", "work_location": "Mumbai", "avatar": "RM", "salary_ctc": 1200000, "date_of_birth": "1996-03-15"},
        {"id": "e4", "employee_code": "KEKA004", "full_name": "Ananya Gupta", "email": "ananya.gupta@company.com", "phone": "+91 98765 43213", "department_id": "d2", "department": "Human Resources", "designation": "HR Business Partner", "manager": "Vikram Singh", "date_of_joining": "2021-08-20", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "AG", "salary_ctc": 1500000, "date_of_birth": "1998-11-20"},
        {"id": "e5", "employee_code": "KEKA005", "full_name": "Vikram Singh", "email": "vikram.singh@company.com", "phone": "+91 98765 43214", "department_id": "d1", "department": "Engineering", "designation": "CTO", "manager": "-", "date_of_joining": "2019-09-02", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "VS", "salary_ctc": 5000000, "date_of_birth": "1991-05-01"},
        {"id": "e6", "employee_code": "KEKA006", "full_name": "Sneha Reddy", "email": "sneha.reddy@company.com", "phone": "+91 98765 43215", "department_id": "d6", "department": "Design", "designation": "Product Designer", "manager": "Priya Nair", "date_of_joining": "2022-11-12", "status": "On Leave", "employment_type": "Full-time", "work_location": "Hyderabad", "avatar": "SR", "salary_ctc": 1400000, "date_of_birth": "1997-07-22"},
        {"id": "e7", "employee_code": "KEKA007", "full_name": "Kabir Khan", "email": "kabir.khan@company.com", "phone": "+91 98765 43216", "department_id": "d1", "department": "Engineering", "designation": "DevOps Engineer", "manager": "Priya Nair", "date_of_joining": "2023-02-18", "status": "Active", "employment_type": "Full-time", "work_location": "Remote", "avatar": "KK", "salary_ctc": 1600000, "date_of_birth": "1993-12-10"},
        {"id": "e8", "employee_code": "KEKA008", "full_name": "Ishita Patel", "email": "ishita.patel@company.com", "phone": "+91 98765 43217", "department_id": "d4", "department": "Marketing", "designation": "Content Strategist", "manager": "Ananya Gupta", "date_of_joining": "2023-09-05", "status": "Probation", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "IP", "salary_ctc": 900000, "date_of_birth": "2000-04-18"},
    ],
    "attendance": [
        {"id": "a1", "employee_id": "e1", "date": str(date.today()), "clock_in": "09:32 AM", "clock_out": "06:45 PM", "work_hours": 8.2, "status": "Present"},
        {"id": "a2", "employee_id": "e2", "date": str(date.today()), "clock_in": "09:15 AM", "clock_out": "07:10 PM", "work_hours": 9.0, "status": "Present"},
        {"id": "a3", "employee_id": "e3", "date": str(date.today()), "clock_in": "10:05 AM", "clock_out": None, "work_hours": 4.5, "status": "Present"},
        {"id": "a4", "employee_id": "e4", "date": str(date.today()), "clock_in": "09:28 AM", "clock_out": "06:30 PM", "work_hours": 8.0, "status": "Present"},
        {"id": "a5", "employee_id": "e6", "date": str(date.today()), "clock_in": None, "clock_out": None, "work_hours": 0, "status": "On Leave"},
    ],
    "leave_requests": [
        {"id": "l1", "employee_id": "e1", "employee_name": "Aarav Sharma", "leave_type": "Casual Leave", "start_date": "2026-09-02", "end_date": "2026-09-03", "days": 2, "reason": "Personal work", "status": "Pending", "applied_at": "2026-08-28"},
        {"id": "l2", "employee_id": "e3", "employee_name": "Rohan Mehta", "leave_type": "Sick Leave", "start_date": "2026-08-29", "end_date": "2026-08-29", "days": 1, "reason": "Fever", "status": "Approved", "applied_at": "2026-08-28"},
        {"id": "l3", "employee_id": "e6", "employee_name": "Sneha Reddy", "leave_type": "Earned Leave", "start_date": "2026-08-28", "end_date": "2026-08-30", "days": 3, "reason": "Family function", "status": "Approved", "applied_at": "2026-08-25"},
        {"id": "l4", "employee_id": "e8", "employee_name": "Ishita Patel", "leave_type": "Work From Home", "start_date": "2026-08-29", "end_date": "2026-08-29", "days": 1, "reason": "WFH", "status": "Pending", "applied_at": "2026-08-29"},
    ],
    "leave_balances": [
        {"employee_id": "e1", "CL": 8, "SL": 10, "EL": 15, "WFH": 20},
    ],
    "jobs": [
        {"id": "j1", "title": "Senior Frontend Engineer", "department": "Engineering", "location": "Bangalore", "openings": 2, "applicants": 47, "status": "Open"},
        {"id": "j2", "title": "Product Marketing Manager", "department": "Marketing", "location": "Mumbai", "openings": 1, "applicants": 23, "status": "Open"},
        {"id": "j3", "title": "HR Intern", "department": "Human Resources", "location": "Bangalore", "openings": 3, "applicants": 112, "status": "Open"},
        {"id": "j4", "title": "Sales Development Rep", "department": "Sales", "location": "Remote", "openings": 5, "applicants": 34, "status": "On Hold"},
    ],
    "candidates": [
        {"id": "c1", "job_id": "j1", "full_name": "Aditya Verma", "email": "aditya@example.com", "stage": "Interview", "rating": 4, "experience": "5 yrs"},
        {"id": "c2", "job_id": "j1", "full_name": "Neha Singh", "email": "neha@example.com", "stage": "Screening", "rating": 3, "experience": "3 yrs"},
        {"id": "c3", "job_id": "j2", "full_name": "Rahul Bose", "email": "rahul@example.com", "stage": "Offer", "rating": 5, "experience": "6 yrs"},
    ],
    "payslips": [
        {"id": "p1", "employee_id": "e1", "month": 7, "year": 2026, "gross": 150000, "deductions": 18000, "net": 132000, "status": "Paid"},
        {"id": "p2", "employee_id": "e1", "month": 8, "year": 2026, "gross": 150000, "deductions": 18000, "net": 132000, "status": "Generated"},
    ],
    "announcements": [
        {"id": "an1", "title": "🎉 Independence Day Celebration", "content": "Join us on 15th Aug at 4 PM in Cafeteria for flag hoisting and sweets distribution.", "type": "Event", "date": "2026-08-28", "is_pinned": True},
        {"id": "an2", "title": "New Leave Policy Update", "content": "WFH quota increased from 12 to 24 days per year effective Sep 1st. Check HR portal for details.", "type": "Policy", "date": "2026-08-27", "is_pinned": True},
        {"id": "an3", "title": "Welcome New Joiners - August", "content": "Please welcome 8 new members who joined us this month across Engineering and Sales.", "type": "General", "date": "2026-08-25", "is_pinned": False},
    ],
    "goals": [
        {"id": "g1", "employee_id": "e1", "title": "Launch Performance Module v2", "progress": 75, "status": "In Progress", "due_date": "2026-09-30"},
        {"id": "g2", "employee_id": "e1", "title": "Reduce API latency by 30%", "progress": 40, "status": "In Progress", "due_date": "2026-10-15"},
        {"id": "g3", "employee_id": "e2", "title": "Hire 5 engineers for backend team", "progress": 100, "status": "Completed", "due_date": "2026-08-15"},
    ],
    "reimbursements": [
        {"id": "r1", "employee_id": "e1", "employee_name": "Aarav Sharma", "category": "Travel", "amount": 4500, "date": "2026-08-20", "description": "Client visit - Mumbai", "status": "Approved"},
        {"id": "r2", "employee_id": "e2", "employee_name": "Priya Nair", "category": "Internet", "amount": 1200, "date": "2026-08-24", "description": "Monthly broadband reimbursement", "status": "Pending"},
        {"id": "r3", "employee_id": "e3", "employee_name": "Rohan Mehta", "category": "Food", "amount": 800, "date": "2026-08-26", "description": "Team lunch", "status": "Pending"},
    ],
    "holidays": [
        {"id": "h1", "name": "Ganesh Chaturthi", "date": "2026-09-14", "day": "Monday", "type": "Public"},
        {"id": "h2", "name": "Gandhi Jayanti", "date": "2026-10-02", "day": "Friday", "type": "Public"},
        {"id": "h3", "name": "Dussehra", "date": "2026-10-20", "day": "Tuesday", "type": "Public"},
        {"id": "h4", "name": "Diwali", "date": "2026-11-08", "day": "Sunday", "type": "Public"},
        {"id": "h5", "name": "Christmas", "date": "2026-12-25", "day": "Friday", "type": "Public"},
    ]
}

def get_supabase_data(table, filters=None):
    """Unified data fetcher: Supabase if available else mock"""
    if supabase:
        try:
            query = supabase.table(table).select("*")
            if filters:
                for k, v in filters.items():
                    query = query.eq(k, v)
            res = query.execute()
            return res.data
        except Exception as e:
            print(f"Supabase error on {table}: {e}")
            return mock_db.get(table, [])
    else:
        data = mock_db.get(table, [])
        if filters:
            filtered = []
            for item in data:
                match = True
                for k, v in filters.items():
                    if item.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            return filtered
        return data

def insert_supabase_data(table, payload, mock_enrich=None):
    """Insert into Supabase when available, otherwise (or on failure) fall back to the in-memory
    mock store so nothing is silently lost. `mock_enrich` adds display-only fields in mock mode."""
    data = dict(payload)
    if mock_enrich:
        data.update(mock_enrich)
    if supabase:
        try:
            res = supabase.table(table).insert(payload).execute()
            return res.data[0] if res.data else payload
        except Exception as e:
            print(f"Insert error {table}: {e} -> falling back to mock store")
            data["id"] = data.get("id") or str(uuid.uuid4())[:8]
            mock_db.setdefault(table, []).append(data)
            return data
    else:
        data["id"] = data.get("id") or str(uuid.uuid4())[:8]
        mock_db.setdefault(table, []).append(data)
        return data

def api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status

def first_supabase_employee_id(employee_id=None):
    """Use a real employee UUID when the demo client sends its mock ID."""
    if not supabase:
        return employee_id or "e1"
    employees = supabase.table("employees").select("id").order("created_at").limit(1).execute().data
    if not employees:
        return None
    if employee_id:
        match = supabase.table("employees").select("id").eq("id", employee_id).limit(1).execute().data
        if match:
            return match[0]["id"]
    return employees[0]["id"]

def resolve_department_id(department_id):
    if not supabase or not department_id or len(str(department_id)) > 10:
        return department_id
    department = next((d for d in mock_db["departments"] if d["id"] == department_id), None)
    if not department:
        return department_id
    result = supabase.table("departments").select("id").eq("name", department["name"]).limit(1).execute()
    return result.data[0]["id"] if result.data else department_id

# ---------------- AUTH MIDDLEWARE ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # For demo, allow all - in production check session
        # if 'user' not in session:
        #     return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------------- ROUTES ----------------
@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        email = data.get('email')
        password = data.get('password')
        # Demo login - accept any email, in production verify with Supabase Auth
        # For Supabase Auth:
        # if supabase:
        #   res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        session['user'] = {
            "email": email or "admin@company.com",
            "name": "Admin User",
            "role": "HR Admin",
            "avatar": "AU"
        }
        if request.is_json:
            return jsonify({"success": True, "redirect": "/dashboard"})
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=session.get('user', {"name": "Admin", "email": "admin@company.com"}))

# ---------------- API ENDPOINTS ----------------

@app.route('/api/stats')
def api_stats():
    employees = get_supabase_data("employees")
    attendance_today = get_supabase_data("attendance")
    leaves = get_supabase_data("leave_requests")
    jobs = get_supabase_data("jobs")
    
    total_emp = len(employees)
    present_today = len([a for a in attendance_today if a.get('status') == 'Present'])
    on_leave = len([a for a in attendance_today if a.get('status') == 'On Leave'])
    pending_leaves = len([l for l in leaves if l.get('status') == 'Pending'])
    open_jobs = len([j for j in jobs if j.get('status') == 'Open'])
    
    # "Today" widget data - birthdays, work anniversaries, who's on leave (computed for current date)
    today = date.today()

    def _avatar(e):
        av = (e.get('avatar') or '' ).strip()
        if av:
            return av[:2].upper()
        parts = (e.get('full_name') or '' ).strip().split()
        return ''.join(w[0] for w in parts[:2]).upper() if parts else '?'

    birthday_people, anniversary_people = [], []
    for e in employees:
        dob = e.get('date_of_birth')
        if dob:
            try:
                dob_d = date.fromisoformat(str(dob)[:10])
            except ValueError:
                dob_d = None
            if dob_d and (dob_d.month, dob_d.day) == (today.month, today.day):
                birthday_people.append({'name': e.get('full_name'), 'avatar': _avatar(e), 'employee_id': e.get('id')})
        doj = e.get('date_of_joining')
        if doj:
            try:
                doj_d = date.fromisoformat(str(doj)[:10])
            except ValueError:
                doj_d = None
            if doj_d and (doj_d.month, doj_d.day) == (today.month, today.day):
                anniversary_people.append({'name': e.get('full_name'), 'years': today.year - doj_d.year, 'avatar': _avatar(e), 'employee_id': e.get('id')})

    approved_leaves = {}
    for l in leaves:
        if l.get('status') == 'Approved' and l.get('employee_id')and l.get('leave_type'):
            approved_leaves.setdefault(l['employee_id'], l['leave_type'])
    on_leave_today = []
    for e in employees:
        if (e.get('status') or '' ).lower() == 'on leave':
            on_leave_today.append({
                'name': e.get('full_name'),
                'leave_type': approved_leaves.get(e.get('id')) or 'On Leave',
                'avatar': _avatar(e),
                'employee_id': e.get('id')
            })

    # Department distribution
    dept_count = {}
    for e in employees:
        dept = e.get('department') or e.get('department_id') or 'Unknown'
        # If department_id, try to resolve name from departments table
        if isinstance(dept, str) and len(dept) < 5:  # it's an ID like d1
            dept_obj = next((d for d in get_supabase_data("departments") if d['id'] == dept), None)
            dept = dept_obj['name'] if dept_obj else dept
        dept_count[dept] = dept_count.get(dept, 0) + 1

    return jsonify({
        "total_employees": total_emp,
        "present_today": present_today,
        "on_leave": on_leave,
        "pending_leaves": pending_leaves,
        "open_positions": open_jobs,
        "attendance_rate": round((present_today / total_emp * 100) if total_emp else 0, 1),
        "department_distribution": dept_count,
        "today": {
            "date_label": today.strftime("%d %b"),
            "birthdays": birthday_people,
            "anniversaries": anniversary_people,
            "on_leave": on_leave_today
        }
    })

@app.route('/api/employees', methods=['GET', 'POST'])
def api_employees():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        full_name = (data.get('full_name') or '').strip()
        email = (data.get('email') or '').strip()
        if not full_name or not email:
            return api_error("Full name and email are required")
        # Generate employee code
        emp_code = f"KEKA{len(get_supabase_data('employees'))+1:03d}"
        department_id = resolve_department_id(data.get('department_id'))
        payload = {
            "employee_code": emp_code,
            "full_name": full_name,
            "email": email,
            "phone": data.get('phone'),
            "department_id": department_id,
            "employment_type": data.get('employment_type', 'Full-time'),
            "work_location": data.get('work_location', 'Bangalore'),
            "status": "Active",
            "date_of_joining": data.get('date_of_joining') or str(date.today()),
            "salary_ctc": data.get('salary_ctc') or 0
        }
        designation = (data.get('designation') or '').strip()
        if supabase and designation:
            designation_result = supabase.table("designations").select("id").eq("title", designation).eq("department_id", department_id).limit(1).execute()
            if designation_result.data:
                payload["designation_id"] = designation_result.data[0]["id"]
            else:
                designation_result = supabase.table("designations").insert({"title": designation, "department_id": department_id}).execute()
                if not designation_result.data:
                    return api_error("Could not create designation")
                payload["designation_id"] = designation_result.data[0]["id"]
        elif not supabase:
            payload["designation"] = designation
        # Map for mock
        if not supabase:
            payload["id"] = str(uuid.uuid4())[:8]
            payload["department"] = next((d["name"] for d in mock_db["departments"] if d["id"] == data.get('department_id')), "Engineering")
            payload["avatar"] = "".join([w[0] for w in payload["full_name"].split()[:2]]).upper()
            payload["manager"] = "Priya Nair"
        if supabase:
            try:
                result = supabase.table("employees").insert(payload).execute()
                return jsonify(result.data[0] if result.data else payload)
            except Exception as e:
                print(f"Insert error employees: {e}")
                return api_error(str(e), 400)
        result = insert_supabase_data("employees", payload)
        return jsonify(result or payload)
    
    # GET with search/filter
    search = request.args.get('search', '').lower()
    dept_filter = request.args.get('department')
    status_filter = request.args.get('status')
    
    employees = get_supabase_data("employees")
    if search:
        employees = [e for e in employees if search in e.get('full_name','').lower() or search in e.get('email','').lower() or search in e.get('employee_code','').lower()]
    if dept_filter and dept_filter != 'All':
        employees = [e for e in employees if (e.get('department') == dept_filter or e.get('department_id') == dept_filter)]
    if status_filter and status_filter != 'All':
        employees = [e for e in employees if e.get('status') == status_filter]
    
    return jsonify(employees)

@app.route('/api/employees/<emp_id>', methods=['GET', 'PUT', 'DELETE'])
def api_employee_detail(emp_id):
    if request.method == 'GET':
        emps = get_supabase_data("employees")
        emp = next((e for e in emps if e['id'] == emp_id), None)
        return jsonify(emp or {})
    elif request.method == 'DELETE':
        if supabase:
            supabase.table("employees").delete().eq("id", emp_id).execute()
        else:
            mock_db["employees"] = [e for e in mock_db["employees"] if e["id"] != emp_id]
        return jsonify({"success": True})
    elif request.method == 'PUT':
        data = request.get_json()
        if supabase:
            res = supabase.table("employees").update(data).eq("id", emp_id).execute()
            return jsonify(res.data[0] if res.data else {})
        else:
            for i, e in enumerate(mock_db["employees"]):
                if e["id"] == emp_id:
                    mock_db["employees"][i].update(data)
                    return jsonify(mock_db["employees"][i])
        return jsonify({})

@app.route('/api/attendance', methods=['GET', 'POST'])
def api_attendance():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        action = data.get('action')  # clock_in / clock_out
        if action not in ('clock_in', 'clock_out'):
            return api_error("Invalid attendance action")
        try:
            employee_id = first_supabase_employee_id(data.get('employee_id'))
        except Exception as e:
            print(f"Employee lookup error: {e}")
            return api_error(str(e), 400)
        if not employee_id:
            return api_error("Add an employee before recording attendance", 404)
        today = str(date.today())
        
        if supabase:
            try:
                existing = supabase.table("attendance").select("*").eq("employee_id", employee_id).eq("date", today).execute()
                if existing.data:
                    att = existing.data[0]
                    if action == 'clock_out':
                        result = supabase.table("attendance").update({"clock_out": datetime.now().isoformat(), "work_hours": 8.0}).eq("id", att["id"]).execute()
                        return jsonify({"message": "Clocked out", "attendance": result.data[0] if result.data else att})
                    return jsonify({"message": "Already clocked in", "attendance": att})
                payload = {"employee_id": employee_id, "date": today, "clock_in": datetime.now().isoformat(), "status": "Present"}
                res = supabase.table("attendance").insert(payload).execute()
                return jsonify({"message": "Clocked in", "attendance": res.data[0] if res.data else payload})
            except Exception as e:
                print(f"Attendance error: {e}")
                return api_error(str(e), 400)
        else:
            # Mock logic
            existing = next((a for a in mock_db["attendance"] if a["employee_id"] == employee_id and a["date"] == today), None)
            if existing:
                if action == 'clock_out':
                    existing["clock_out"] = datetime.now().strftime("%I:%M %p")
                    existing["work_hours"] = 8.5
                    return jsonify({"message": "Clocked out successfully", "attendance": existing})
                return jsonify({"message": "Already clocked in today", "attendance": existing})
            else:
                new_att = {"id": str(uuid.uuid4())[:8], "employee_id": employee_id, "date": today, "clock_in": datetime.now().strftime("%I:%M %p"), "clock_out": None, "work_hours": 0, "status": "Present"}
                mock_db["attendance"].append(new_att)
                return jsonify({"message": "Clocked in successfully", "attendance": new_att})
    
    # GET
    employee_id = request.args.get('employee_id')
    filters = {}
    if employee_id:
        filters["employee_id"] = employee_id
    data = get_supabase_data("attendance", filters if filters else None)
    # Sort by date desc
    try:
        data = sorted(data, key=lambda x: x.get('date',''), reverse=True)[:50]
    except:
        pass
    return jsonify(data)

@app.route('/api/leave-requests', methods=['GET', 'POST'])
def api_leave_requests():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        start_date = (data.get('start_date') or '').strip()
        end_date = (data.get('end_date') or '').strip()
        if not start_date or not end_date:
            return api_error("Start date and end date are required")

        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
            if end_dt < start_dt:
                return api_error("End date must be on or after start date")
            days = int(data.get('days') or (end_dt - start_dt).days + 1)
        except ValueError:
            return api_error("Invalid date format. Use YYYY-MM-DD")

        employee_id = data.get('employee_id') or 'e1'
        employees = get_supabase_data('employees')
        employee = next((e for e in employees if e.get('id') == employee_id), None)
        employee_name = (data.get('employee_name') or (employee.get('full_name') if employee else 'Current User')).strip() or 'Current User'

        leave_type_value = (data.get('leave_type') or 'Casual Leave').strip()
        leave_type_name = leave_type_value.split(' (')[0].strip() or 'Casual Leave'

        payload = {
            "employee_id": employee_id,
            "leave_type_id": data.get('leave_type_id') or leave_type_name,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "reason": (data.get('reason') or '').strip(),
            "status": "Pending"
        }

        mock_enrich = {
            "employee_name": employee_name,
            "leave_type": leave_type_name,
            "applied_at": str(date.today())
        }

        result = insert_supabase_data("leave_requests", payload, mock_enrich=mock_enrich)
        return jsonify(result or payload)

    status_filter = request.args.get('status')
    data = get_supabase_data("leave_requests")
    if status_filter and status_filter != 'All':
        data = [d for d in data if d.get('status') == status_filter]
    return jsonify(data)

@app.route('/api/leave-requests/<req_id>/action', methods=['POST'])
def api_leave_action(req_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')  # Approved / Rejected
    if new_status not in ('Approved', 'Rejected'):
        return api_error("Status must be Approved or Rejected")
    if supabase:
        try:
            res = supabase.table("leave_requests").update({"status": new_status, "actioned_at": datetime.now().isoformat()}).eq("id", req_id).execute()
            return jsonify(res.data[0] if res.data else {"success": True})
        except Exception as e:
            print(f"Leave action error: {e} -> falling back to mock store")
    for req in mock_db.get("leave_requests", []):
        if req["id"] == req_id:
            req["status"] = new_status
            return jsonify(req)
    return api_error("Leave request not found", 404)

@app.route('/api/departments')
def api_departments():
    return jsonify(get_supabase_data("departments"))

@app.route('/api/jobs', methods=['GET', 'POST'])
def api_jobs():
    if request.method == 'POST':
        data = request.get_json()
        payload = {
            "title": data.get('title'),
            "department_id": data.get('department_id'),
            "location": data.get('location'),
            "openings": data.get('openings', 1),
            "description": data.get('description'),
            "status": "Open"
        }
        mock_enrich = {
            "department": data.get('department', 'Engineering'),
            "applicants": 0
        }
        result = insert_supabase_data("jobs", payload, mock_enrich=mock_enrich)
        return jsonify(result or payload)
    return jsonify(get_supabase_data("jobs"))

@app.route('/api/candidates')
def api_candidates():
    job_id = request.args.get('job_id')
    filters = {"job_id": job_id} if job_id else None
    return jsonify(get_supabase_data("candidates", filters))

@app.route('/api/payslips')
def api_payslips():
    emp_id = request.args.get('employee_id')
    filters = {"employee_id": emp_id} if emp_id else None
    return jsonify(get_supabase_data("payslips", filters))

@app.route('/api/announcements', methods=['GET', 'POST'])
def api_announcements():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        content = (data.get('content') or '').strip()
        if not title:
            return api_error("Announcement title is required")
        if not content:
            return api_error("Announcement content is required")
        payload = {
            "title": title,
            "content": content,
            "type": (data.get('type') or 'General').strip(),
            "date": data.get('date') or str(date.today()),
            "is_pinned": bool(data.get('is_pinned'))
        }
        result = insert_supabase_data("announcements", payload)
        return jsonify(result or payload)
    return jsonify(get_supabase_data("announcements"))

@app.route('/api/announcements/<ann_id>', methods=['PUT', 'DELETE'])
def api_announcement_detail(ann_id):
    if request.method == 'DELETE':
        if supabase:
            try:
                supabase.table("announcements").delete().eq("id", ann_id).execute()
                return jsonify({"success": True})
            except Exception as e:
                print(f"Announcement delete error: {e} -> falling back to mock store")
        before = len(mock_db.get("announcements", []))
        mock_db["announcements"] = [a for a in mock_db.get("announcements", []) if a.get("id") != ann_id]
        if len(mock_db.get("announcements", [])) < before:
            return jsonify({"success": True})
        return api_error("Announcement not found", 404)

    data = request.get_json(silent=True) or {}
    updates = {}
    if 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            return api_error("Announcement title cannot be empty")
        updates['title'] = title
    if 'content' in data:
        content = (data.get('content') or '').strip()
        if not content:
            return api_error("Announcement content cannot be empty")
        updates['content'] = content
    if 'type' in data:
        updates['type'] = (data.get('type') or 'General').strip()
    if 'date' in data and data.get('date'):
        updates['date'] = data.get('date')
    if 'is_pinned' in data:
        updates['is_pinned'] = bool(data.get('is_pinned'))
    if not updates:
        return api_error("No valid fields to update")

    if supabase:
        try:
            res = supabase.table("announcements").update(updates).eq("id", ann_id).execute()
            if res.data:
                return jsonify(res.data[0])
        except Exception as e:
            print(f"Announcement update error: {e} -> falling back to mock store")
    for ann in mock_db.get("announcements", []):
        if ann.get("id") == ann_id:
            ann.update(updates)
            return jsonify(ann)
    return api_error("Announcement not found", 404)

@app.route('/api/goals', methods=['GET', 'POST'])
def api_goals():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        if not title:
            return api_error("Goal title is required")
        try:
            progress = int(data.get('progress') or 0)
        except (TypeError, ValueError):
            progress = 0
        progress = max(0, min(progress, 100))
        status = (data.get('status') or ('Completed' if progress == 100 else 'In Progress')).strip()
        payload = {
            "employee_id": data.get('employee_id') or 'e1',
            "title": title,
            "progress": progress,
            "status": status,
            "due_date": data.get('due_date') or str(date.today() + timedelta(days=90))
        }
        result = insert_supabase_data("goals", payload)
        return jsonify(result or payload)
    emp_id = request.args.get('employee_id')
    filters = {"employee_id": emp_id} if emp_id else None
    return jsonify(get_supabase_data("goals", filters))

@app.route('/api/holidays')
def api_holidays():
    return jsonify(get_supabase_data("holidays"))

@app.route('/api/leave-types')
def api_leave_types():
    # Return default leave types if supabase not configured
    if supabase:
        return jsonify(get_supabase_data("leave_types"))
    return jsonify([
        {"id": "lt1", "name": "Casual Leave", "code": "CL", "color": "#6c5ce7", "yearly_quota": 12},
        {"id": "lt2", "name": "Sick Leave", "code": "SL", "color": "#00b894", "yearly_quota": 12},
        {"id": "lt3", "name": "Earned Leave", "code": "EL", "color": "#0984e3", "yearly_quota": 18},
        {"id": "lt4", "name": "Work From Home", "code": "WFH", "color": "#fdcb6e", "yearly_quota": 24},
    ])

@app.route('/api/reimbursements', methods=['GET','POST'])
def api_reimbursements():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        category = (data.get('category') or '').strip()
        amount = data.get('amount')
        expense_date = data.get('date') or str(date.today())
        if not category:
            return api_error("Category is required")
        try:
            amount = round(float(amount), 2)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return api_error("A valid amount is required")

        employee_id = data.get('employee_id') or 'e1'
        employees = get_supabase_data('employees')
        employee = next((e for e in employees if e.get('id') == employee_id), None)
        employee_name = (data.get('employee_name') or (employee.get('full_name') if employee else 'Current User')).strip() or 'Current User'

        payload = {
            "employee_id": employee_id,
            "category": category,
            "amount": amount,
            "date": expense_date,
            "description": (data.get('description') or '').strip(),
            "status": "Pending"
        }
        mock_enrich = {"employee_name": employee_name}
        result = insert_supabase_data("reimbursements", payload, mock_enrich=mock_enrich)
        return jsonify(result or payload)

    data = get_supabase_data("reimbursements")
    return jsonify(data if isinstance(data, list) else [])

# Health check
@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "supabase_connected": supabase is not None,
        "mock_mode": supabase is None,
        "supabase_key_source": supabase_key_source,
        "supabase_error": supabase_error,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"""
    🚀 Ekkaa HRMS Starting...
    ---------------------------------
    Dashboard: http://localhost:{port}/dashboard
    Login: http://localhost:{port}/login
    API Health: http://localhost:{port}/api/health
    Supabase: {'Connected ✅' if supabase else 'Mock Mode ⚠️ (Set .env to enable Supabase)'}
    ---------------------------------
    Demo Login: any email + any password
    """)
    app.run(host='0.0.0.0', port=port, debug=True)
