"""
Keka HRMS Clone - Python Flask + Supabase
Complete HRMS with all Keka features

------------------------------------------------------------------------------
FIXED BUILD - see FIXES.md for the full list. Core principle applied here:

  The API must return the SAME SHAPE whether it is backed by Supabase or by the
  in-memory mock, and it must NEVER report success for a write that failed.

The original code leaked raw Supabase foreign keys (UUIDs) to the browser and
returned HTTP 200 for inserts that Postgres had rejected, which is why records
"applied" but never appeared.
------------------------------------------------------------------------------
"""
import os
import re
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

UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)


def is_uuid(value):
    return bool(value) and bool(UUID_RE.match(str(value)))


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
        {"id": "e1", "employee_code": "KEKA001", "full_name": "Aarav Sharma", "email": "aarav.sharma@company.com", "phone": "+91 98765 43210", "department_id": "d1", "department": "Engineering", "designation": "Senior Software Engineer", "manager": "Priya Nair", "manager_id": "e2", "date_of_joining": "2022-03-15", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "AS", "salary_ctc": 1800000},
        {"id": "e2", "employee_code": "KEKA002", "full_name": "Priya Nair", "email": "priya.nair@company.com", "phone": "+91 98765 43211", "department_id": "d1", "department": "Engineering", "designation": "Engineering Manager", "manager": "Vikram Singh", "manager_id": "e5", "date_of_joining": "2020-01-10", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "PN", "salary_ctc": 3200000},
        {"id": "e3", "employee_code": "KEKA003", "full_name": "Rohan Mehta", "email": "rohan.mehta@company.com", "phone": "+91 98765 43212", "department_id": "d3", "department": "Sales", "designation": "Sales Executive", "manager": "Ananya Gupta", "manager_id": "e4", "date_of_joining": "2023-06-01", "status": "Active", "employment_type": "Full-time", "work_location": "Mumbai", "avatar": "RM", "salary_ctc": 1200000},
        {"id": "e4", "employee_code": "KEKA004", "full_name": "Ananya Gupta", "email": "ananya.gupta@company.com", "phone": "+91 98765 43213", "department_id": "d2", "department": "Human Resources", "designation": "HR Business Partner", "manager": "Vikram Singh", "manager_id": "e5", "date_of_joining": "2021-08-20", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "AG", "salary_ctc": 1500000},
        {"id": "e5", "employee_code": "KEKA005", "full_name": "Vikram Singh", "email": "vikram.singh@company.com", "phone": "+91 98765 43214", "department_id": "d1", "department": "Engineering", "designation": "CTO", "manager": "-", "manager_id": None, "date_of_joining": "2019-05-01", "status": "Active", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "VS", "salary_ctc": 5000000},
        {"id": "e6", "employee_code": "KEKA006", "full_name": "Sneha Reddy", "email": "sneha.reddy@company.com", "phone": "+91 98765 43215", "department_id": "d6", "department": "Design", "designation": "Product Designer", "manager": "Priya Nair", "manager_id": "e2", "date_of_joining": "2022-11-12", "status": "On Leave", "employment_type": "Full-time", "work_location": "Hyderabad", "avatar": "SR", "salary_ctc": 1400000},
        {"id": "e7", "employee_code": "KEKA007", "full_name": "Kabir Khan", "email": "kabir.khan@company.com", "phone": "+91 98765 43216", "department_id": "d1", "department": "Engineering", "designation": "DevOps Engineer", "manager": "Priya Nair", "manager_id": "e2", "date_of_joining": "2023-02-18", "status": "Active", "employment_type": "Full-time", "work_location": "Remote", "avatar": "KK", "salary_ctc": 1600000},
        {"id": "e8", "employee_code": "KEKA008", "full_name": "Ishita Patel", "email": "ishita.patel@company.com", "phone": "+91 98765 43217", "department_id": "d4", "department": "Marketing", "designation": "Content Strategist", "manager": "Ananya Gupta", "manager_id": "e4", "date_of_joining": "2023-09-05", "status": "Probation", "employment_type": "Full-time", "work_location": "Bangalore", "avatar": "IP", "salary_ctc": 900000},
    ],
    "attendance": [
        {"id": "a1", "employee_id": "e1", "date": str(date.today()), "clock_in": "09:32 AM", "clock_out": "06:45 PM", "work_hours": 8.2, "status": "Present"},
        {"id": "a2", "employee_id": "e2", "date": str(date.today()), "clock_in": "09:15 AM", "clock_out": "07:10 PM", "work_hours": 9.0, "status": "Present"},
        {"id": "a3", "employee_id": "e3", "date": str(date.today()), "clock_in": "10:05 AM", "clock_out": None, "work_hours": 4.5, "status": "Present"},
        {"id": "a4", "employee_id": "e4", "date": str(date.today()), "clock_in": "09:28 AM", "clock_out": "06:30 PM", "work_hours": 8.0, "status": "Present"},
        {"id": "a5", "employee_id": "e6", "date": str(date.today()), "clock_in": None, "clock_out": None, "work_hours": 0, "status": "On Leave"},
        {"id": "a6", "employee_id": "e1", "date": str(date.today() - timedelta(days=1)), "clock_in": "09:20 AM", "clock_out": "06:35 PM", "work_hours": 8.4, "status": "Present"},
        {"id": "a7", "employee_id": "e2", "date": str(date.today() - timedelta(days=1)), "clock_in": "09:05 AM", "clock_out": "06:50 PM", "work_hours": 8.8, "status": "Present"},
        {"id": "a8", "employee_id": "e1", "date": str(date.today() - timedelta(days=2)), "clock_in": "09:45 AM", "clock_out": "06:15 PM", "work_hours": 7.5, "status": "Present"},
    ],
    "leave_requests": [
        {"id": "l1", "employee_id": "e1", "employee_name": "Aarav Sharma", "leave_type": "Casual Leave", "leave_type_id": "lt1", "start_date": "2026-09-02", "end_date": "2026-09-03", "days": 2, "reason": "Personal work", "status": "Pending", "applied_at": "2026-08-28"},
        {"id": "l2", "employee_id": "e3", "employee_name": "Rohan Mehta", "leave_type": "Sick Leave", "leave_type_id": "lt2", "start_date": "2026-08-29", "end_date": "2026-08-29", "days": 1, "reason": "Fever", "status": "Approved", "applied_at": "2026-08-28"},
        {"id": "l3", "employee_id": "e6", "employee_name": "Sneha Reddy", "leave_type": "Earned Leave", "leave_type_id": "lt3", "start_date": "2026-08-28", "end_date": "2026-08-30", "days": 3, "reason": "Family function", "status": "Approved", "applied_at": "2026-08-25"},
        {"id": "l4", "employee_id": "e8", "employee_name": "Ishita Patel", "leave_type": "Work From Home", "leave_type_id": "lt4", "start_date": "2026-08-29", "end_date": "2026-08-29", "days": 1, "reason": "WFH", "status": "Pending", "applied_at": "2026-08-29"},
    ],
    "leave_types": [
        {"id": "lt1", "name": "Casual Leave", "code": "CL", "color": "#6c5ce7", "yearly_quota": 12},
        {"id": "lt2", "name": "Sick Leave", "code": "SL", "color": "#00b894", "yearly_quota": 12},
        {"id": "lt3", "name": "Earned Leave", "code": "EL", "color": "#0984e3", "yearly_quota": 18},
        {"id": "lt4", "name": "Work From Home", "code": "WFH", "color": "#fdcb6e", "yearly_quota": 24},
    ],
    "holidays": [
        {"id": "h1", "name": "Independence Day", "date": "2026-08-15", "type": "National", "is_optional": False},
        {"id": "h2", "name": "Gandhi Jayanti", "date": "2026-10-02", "type": "National", "is_optional": False},
        {"id": "h3", "name": "Diwali", "date": "2026-10-20", "type": "Festival", "is_optional": False},
        {"id": "h4", "name": "Christmas", "date": "2026-12-25", "type": "National", "is_optional": False},
    ],
    "jobs": [
        {"id": "j1", "title": "Senior Frontend Engineer", "department_id": "d1", "department": "Engineering", "location": "Bangalore", "openings": 2, "applicants": 47, "status": "Open"},
        {"id": "j2", "title": "Product Marketing Manager", "department_id": "d4", "department": "Marketing", "location": "Mumbai", "openings": 1, "applicants": 23, "status": "Open"},
        {"id": "j3", "title": "HR Intern", "department_id": "d2", "department": "Human Resources", "location": "Bangalore", "openings": 3, "applicants": 112, "status": "Open"},
        {"id": "j4", "title": "Sales Development Rep", "department_id": "d3", "department": "Sales", "location": "Remote", "openings": 5, "applicants": 34, "status": "On Hold"},
    ],
    "candidates": [
        {"id": "c1", "job_id": "j1", "full_name": "Aditya Verma", "email": "aditya@example.com", "stage": "Interview", "rating": 4, "experience_years": 5},
        {"id": "c2", "job_id": "j1", "full_name": "Neha Singh", "email": "neha@example.com", "stage": "Screening", "rating": 3, "experience_years": 3},
        {"id": "c3", "job_id": "j2", "full_name": "Rahul Bose", "email": "rahul@example.com", "stage": "Offer", "rating": 5, "experience_years": 6},
    ],
    "payslips": [
        {"id": "p1", "employee_id": "e1", "month": 7, "year": 2026, "gross_earnings": 150000, "total_deductions": 18000, "net_pay": 132000, "status": "Paid"},
        {"id": "p2", "employee_id": "e1", "month": 8, "year": 2026, "gross_earnings": 150000, "total_deductions": 18000, "net_pay": 132000, "status": "Generated"},
        {"id": "p3", "employee_id": "e2", "month": 8, "year": 2026, "gross_earnings": 266000, "total_deductions": 41000, "net_pay": 225000, "status": "Paid"},
    ],
    "reimbursements": [
        {"id": "r1", "employee_id": "e1", "category": "Travel", "amount": 4500, "date": "2026-08-20", "description": "Client visit cab fare", "status": "Approved"},
        {"id": "r2", "employee_id": "e3", "category": "Food", "amount": 1200, "date": "2026-08-24", "description": "Team lunch", "status": "Pending"},
    ],
    "documents": [
        {"id": "doc1", "employee_id": "e1", "name": "PAN Card", "type": "Identity", "status": "Verified", "uploaded_at": "2026-02-01"},
        {"id": "doc2", "employee_id": "e1", "name": "Offer Letter", "type": "Employment", "status": "Verified", "uploaded_at": "2026-02-01"},
        {"id": "doc3", "employee_id": "e2", "name": "Aadhaar Card", "type": "Identity", "status": "Pending", "uploaded_at": "2026-03-01"},
        {"id": "doc4", "employee_id": "e3", "name": "Degree Certificate", "type": "Education", "status": "Verified", "uploaded_at": "2026-06-10"},
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
    ]
}


# ============================================================================
# DATA ACCESS LAYER
# ============================================================================

class DataError(Exception):
    """Raised when a write is rejected by the database."""


def get_supabase_data(table, filters=None):
    """Unified data fetcher: Supabase if available else mock."""
    if supabase:
        try:
            query = supabase.table(table).select("*")
            if filters:
                for k, v in filters.items():
                    query = query.eq(k, v)
            res = query.execute()
            return res.data or []
        except Exception as e:
            print(f"Supabase error on {table}: {e}")
            return []
    data = mock_db.get(table, [])
    if filters:
        out = []
        for item in data:
            if all(str(item.get(k)) == str(v) for k, v in filters.items()):
                out.append(item)
        return out
    return list(data)


def insert_supabase_data(table, payload):
    """
    FIX: previously this swallowed Supabase errors and returned None, and the
    caller then returned the un-saved payload with HTTP 200 - the root cause of
    "it says applied but nothing shows up". Now failures raise DataError.
    """
    if supabase:
        try:
            res = supabase.table(table).insert(payload).execute()
            if not res.data:
                raise DataError(f"{table}: insert returned no row (check RLS policies on '{table}')")
            return res.data[0]
        except DataError:
            raise
        except Exception as e:
            print(f"Insert error {table}: {e}")
            raise DataError(str(e))
    payload = dict(payload)
    payload.setdefault("id", str(uuid.uuid4())[:8])
    mock_db.setdefault(table, []).append(payload)
    return payload


def update_row(table, row_id, patch):
    if supabase:
        try:
            res = supabase.table(table).update(patch).eq("id", row_id).execute()
            if not res.data:
                raise DataError(f"{table}: no row updated for id={row_id}")
            return res.data[0]
        except DataError:
            raise
        except Exception as e:
            raise DataError(str(e))
    for row in mock_db.get(table, []):
        if str(row.get("id")) == str(row_id):
            row.update(patch)
            return row
    raise DataError(f"{table}: id {row_id} not found")


def api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status


# ---------------- LOOKUP HELPERS (name <-> id in both modes) ----------------

def _index(table, key="id"):
    return {str(r.get(key)): r for r in get_supabase_data(table)}


def department_name_map():
    return {str(d["id"]): d.get("name") for d in get_supabase_data("departments")}


def designation_title_map():
    if supabase:
        return {str(d["id"]): d.get("title") for d in get_supabase_data("designations")}
    return {}


def employee_name_map():
    return {str(e["id"]): e.get("full_name") for e in get_supabase_data("employees")}


def leave_type_map():
    return {str(t["id"]): t for t in get_supabase_data("leave_types")}


def resolve_department_id(value):
    """Accept a department id OR a department name and return a valid id."""
    if not value:
        return None
    depts = get_supabase_data("departments")
    for d in depts:
        if str(d["id"]) == str(value):
            return d["id"]
    for d in depts:
        if (d.get("name") or "").lower() == str(value).lower():
            return d["id"]
    return None


def resolve_leave_type_id(value):
    """
    FIX: the browser sends a leave-type NAME ("Casual Leave"). Postgres needs the
    leave_types UUID. Previously the name was written straight into the uuid FK.
    """
    if not value:
        return None
    types = get_supabase_data("leave_types")
    for t in types:
        if str(t["id"]) == str(value):
            return t["id"]
    label = str(value).split(" (")[0].strip().lower()
    for t in types:
        if (t.get("name") or "").lower() == label or (t.get("code") or "").lower() == label:
            return t["id"]
    return None


def current_employee(employee_id=None):
    """
    Resolve who the request is acting as.
    FIX: the browser hardcoded 'e1', which is not a UUID and blew up every
    Supabase insert. Match on the logged-in email first, then fall back.
    """
    employees = get_supabase_data("employees")
    if not employees:
        return None
    if employee_id:
        for e in employees:
            if str(e["id"]) == str(employee_id):
                return e
    email = (session.get("user") or {}).get("email")
    if email:
        for e in employees:
            if (e.get("email") or "").lower() == email.lower():
                return e
    return employees[0]


def current_employee_id(employee_id=None):
    emp = current_employee(employee_id)
    return emp["id"] if emp else None


# ---------------- NORMALISERS (make Supabase rows look like mock rows) -------

def _fmt_time(value):
    """'2026-09-01T09:32:00' -> '09:32 AM'. Leaves already-formatted values alone."""
    if not value:
        return None
    s = str(value)
    if re.match(r'^\d{1,2}:\d{2}\s*(AM|PM)$', s, re.I):
        return s.upper()
    try:
        s2 = s.replace("Z", "+00:00")
        if "T" in s2:
            dt = datetime.fromisoformat(s2)
        else:
            dt = datetime.fromisoformat(f"{date.today()}T{s2}")
        return dt.strftime("%I:%M %p")
    except Exception:
        return s


def _fmt_date(value):
    if not value:
        return None
    s = str(value)
    return s[:10] if "T" in s else s


def _initials(name):
    parts = [p for p in str(name or "U").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "U"


def norm_employee(e, depts=None, desigs=None, emp_names=None):
    depts = depts if depts is not None else department_name_map()
    desigs = desigs if desigs is not None else designation_title_map()
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(e)
    out["department"] = e.get("department") or depts.get(str(e.get("department_id"))) or "-"
    out["designation"] = e.get("designation") or desigs.get(str(e.get("designation_id"))) or "-"
    out["manager"] = e.get("manager") or emp_names.get(str(e.get("manager_id"))) or "-"
    out["avatar"] = e.get("avatar") or _initials(e.get("full_name"))
    out["date_of_joining"] = _fmt_date(e.get("date_of_joining"))
    out["status"] = e.get("status") or "Active"
    return out


def norm_attendance(a, emp_names=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(a)
    out["date"] = _fmt_date(a.get("date"))
    out["clock_in"] = _fmt_time(a.get("clock_in"))
    out["clock_out"] = _fmt_time(a.get("clock_out"))
    out["employee_name"] = a.get("employee_name") or emp_names.get(str(a.get("employee_id"))) or "Employee"
    out["work_hours"] = round(float(a.get("work_hours") or 0), 2)
    out["status"] = a.get("status") or "Present"
    return out


def norm_leave(l, emp_names=None, types=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    types = types if types is not None else leave_type_map()
    out = dict(l)
    lt = types.get(str(l.get("leave_type_id")))
    out["employee_name"] = l.get("employee_name") or emp_names.get(str(l.get("employee_id"))) or "Employee"
    out["leave_type"] = l.get("leave_type") or (lt.get("name") if lt else None) or "Leave"
    out["leave_type_code"] = (lt or {}).get("code", "")
    out["leave_type_color"] = (lt or {}).get("color", "#6c5ce7")
    out["start_date"] = _fmt_date(l.get("start_date"))
    out["end_date"] = _fmt_date(l.get("end_date"))
    out["applied_at"] = _fmt_date(l.get("applied_at"))
    out["days"] = int(l.get("days") or 0)
    out["status"] = l.get("status") or "Pending"
    return out


def norm_payslip(p, emp_names=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(p)
    out["employee_name"] = p.get("employee_name") or emp_names.get(str(p.get("employee_id"))) or "Employee"
    out["gross"] = float(p.get("gross") or p.get("gross_earnings") or 0)
    out["deductions"] = float(p.get("deductions") or p.get("total_deductions") or 0)
    out["net"] = float(p.get("net") or p.get("net_pay") or 0)
    out["status"] = p.get("status") or "Generated"
    return out


def norm_job(j, depts=None, applicant_counts=None):
    depts = depts if depts is not None else department_name_map()
    out = dict(j)
    out["department"] = j.get("department") or depts.get(str(j.get("department_id"))) or "-"
    if applicant_counts is not None:
        out["applicants"] = applicant_counts.get(str(j.get("id")), j.get("applicants") or 0)
    else:
        out["applicants"] = j.get("applicants") or 0
    out["status"] = j.get("status") or "Open"
    return out


def norm_candidate(c, jobs=None):
    jobs = jobs if jobs is not None else {}
    out = dict(c)
    years = c.get("experience_years")
    out["experience"] = c.get("experience") or (f"{years} yrs" if years is not None else "-")
    out["job_title"] = jobs.get(str(c.get("job_id")), "-")
    out["rating"] = int(c.get("rating") or 0)
    return out


def norm_announcement(a):
    out = dict(a)
    out["date"] = _fmt_date(a.get("date") or a.get("created_at"))
    out["is_pinned"] = bool(a.get("is_pinned"))
    return out


def norm_reimbursement(r, emp_names=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(r)
    out["employee_name"] = r.get("employee_name") or emp_names.get(str(r.get("employee_id"))) or "Employee"
    out["date"] = _fmt_date(r.get("date"))
    out["amount"] = float(r.get("amount") or 0)
    out["status"] = r.get("status") or "Pending"
    return out


def norm_document(d, emp_names=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(d)
    out["employee_name"] = emp_names.get(str(d.get("employee_id"))) or "Employee"
    out["uploaded_at"] = _fmt_date(d.get("uploaded_at"))
    out["status"] = d.get("status") or "Pending"
    return out


def norm_goal(g, emp_names=None):
    emp_names = emp_names if emp_names is not None else employee_name_map()
    out = dict(g)
    out["employee_name"] = emp_names.get(str(g.get("employee_id"))) or "Employee"
    out["progress"] = int(g.get("progress") or 0)
    out["due_date"] = _fmt_date(g.get("due_date"))
    out["status"] = g.get("status") or "In Progress"
    return out


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

@app.route('/api/me')
def api_me():
    """Who the dashboard is acting as - the frontend needs a REAL employee id."""
    emp = current_employee()
    user = session.get('user') or {}
    if not emp:
        return jsonify({"employee_id": None, "full_name": user.get("name", "Admin User"),
                        "email": user.get("email", ""), "avatar": "AU", "department": "-",
                        "designation": "-", "employee_code": "-"})
    e = norm_employee(emp)
    return jsonify({
        "employee_id": e["id"], "full_name": e.get("full_name"), "email": e.get("email"),
        "avatar": e.get("avatar"), "department": e.get("department"), "designation": e.get("designation"),
        "employee_code": e.get("employee_code"), "work_location": e.get("work_location"),
        "date_of_joining": e.get("date_of_joining"), "manager": e.get("manager"),
        "phone": e.get("phone"), "status": e.get("status"),
    })


@app.route('/api/stats')
def api_stats():
    employees = get_supabase_data("employees")
    attendance = get_supabase_data("attendance")
    leaves = get_supabase_data("leave_requests")
    jobs = get_supabase_data("jobs")

    today = str(date.today())
    # FIX: previously counted EVERY attendance row ever recorded as "today".
    today_rows = [a for a in attendance if _fmt_date(a.get("date")) == today]

    total_emp = len(employees)
    present_today = len([a for a in today_rows if a.get('status') == 'Present'])
    on_leave = len([a for a in today_rows if a.get('status') == 'On Leave'])
    pending_leaves = len([l for l in leaves if l.get('status') == 'Pending'])
    open_jobs = len([j for j in jobs if j.get('status') == 'Open'])

    # FIX: resolve department UUIDs to names so the donut chart is readable.
    depts = department_name_map()
    dept_count = {}
    for e in employees:
        name = e.get('department') or depts.get(str(e.get('department_id'))) or 'Unassigned'
        dept_count[name] = dept_count.get(name, 0) + 1

    # Real 7-day attendance trend instead of hardcoded numbers
    trend_labels, trend_values = [], []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        ds = str(d)
        rows = [a for a in attendance if _fmt_date(a.get("date")) == ds]
        present = len([a for a in rows if a.get('status') == 'Present'])
        trend_labels.append("Today" if i == 0 else d.strftime("%a"))
        trend_values.append(round(present / total_emp * 100, 1) if total_emp else 0)

    return jsonify({
        "total_employees": total_emp,
        "present_today": present_today,
        "on_leave": on_leave,
        "pending_leaves": pending_leaves,
        "open_positions": open_jobs,
        "attendance_rate": round((present_today / total_emp * 100) if total_emp else 0, 1),
        "department_distribution": dept_count,
        "attendance_trend": {"labels": trend_labels, "values": trend_values},
    })


@app.route('/api/employees', methods=['GET', 'POST'])
def api_employees():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        full_name = (data.get('full_name') or '').strip()
        email = (data.get('email') or '').strip()
        if not full_name or not email:
            return api_error("Full name and email are required")

        existing = get_supabase_data("employees")
        if any((e.get('email') or '').lower() == email.lower() for e in existing):
            return api_error(f"An employee with the email {email} already exists")

        # FIX: derive next code from the highest existing code, not the row count
        # (deleting a row used to produce duplicate employee codes).
        max_num = 0
        for e in existing:
            m = re.search(r'(\d+)$', str(e.get('employee_code') or ''))
            if m:
                max_num = max(max_num, int(m.group(1)))
        emp_code = f"KEKA{max_num + 1:03d}"

        department_id = resolve_department_id(data.get('department_id') or data.get('department'))
        if not department_id:
            return api_error("Please choose a valid department")

        payload = {
            "employee_code": emp_code,
            "full_name": full_name,
            "email": email,
            "phone": data.get('phone'),
            "department_id": department_id,
            "employment_type": data.get('employment_type') or 'Full-time',
            "work_location": data.get('work_location') or 'Bangalore',
            "status": "Active",
            "date_of_joining": data.get('date_of_joining') or str(date.today()),
            "salary_ctc": int(float(data.get('salary_ctc') or 0)),
        }

        designation = (data.get('designation') or '').strip()
        if supabase:
            if designation:
                try:
                    found = supabase.table("designations").select("id").eq("title", designation).eq("department_id", department_id).limit(1).execute()
                    if found.data:
                        payload["designation_id"] = found.data[0]["id"]
                    else:
                        created = supabase.table("designations").insert({"title": designation, "department_id": department_id}).execute()
                        if not created.data:
                            return api_error("Could not create designation")
                        payload["designation_id"] = created.data[0]["id"]
                except Exception as e:
                    return api_error(f"Designation lookup failed: {e}")
        else:
            payload["designation"] = designation or "-"
            payload["department"] = next((d["name"] for d in mock_db["departments"] if d["id"] == department_id), "-")
            payload["avatar"] = _initials(full_name)
            payload["manager"] = "-"

        try:
            created = insert_supabase_data("employees", payload)
        except DataError as e:
            return api_error(f"Could not save employee: {e}", 400)
        return jsonify(norm_employee(created))

    # ---- GET with search/filter ----
    search = (request.args.get('search') or '').lower().strip()
    dept_filter = request.args.get('department')
    status_filter = request.args.get('status')

    depts, desigs, emp_names = department_name_map(), designation_title_map(), employee_name_map()
    employees = [norm_employee(e, depts, desigs, emp_names) for e in get_supabase_data("employees")]

    if search:
        employees = [e for e in employees
                     if search in (e.get('full_name') or '').lower()
                     or search in (e.get('email') or '').lower()
                     or search in (e.get('employee_code') or '').lower()
                     or search in (e.get('designation') or '').lower()]
    # FIX: the dropdown sends a department NAME; rows only carried department_id.
    if dept_filter and dept_filter not in ('All', 'All Departments'):
        employees = [e for e in employees
                     if e.get('department') == dept_filter or str(e.get('department_id')) == dept_filter]
    if status_filter and status_filter not in ('All', 'All Status'):
        employees = [e for e in employees if e.get('status') == status_filter]

    employees.sort(key=lambda e: (e.get('full_name') or '').lower())
    return jsonify(employees)


@app.route('/api/employees/<emp_id>', methods=['GET', 'PUT', 'DELETE'])
def api_employee_detail(emp_id):
    if request.method == 'GET':
        emp = next((e for e in get_supabase_data("employees") if str(e['id']) == str(emp_id)), None)
        if not emp:
            return api_error("Employee not found", 404)
        return jsonify(norm_employee(emp))

    if request.method == 'DELETE':
        if supabase:
            try:
                supabase.table("employees").delete().eq("id", emp_id).execute()
            except Exception as e:
                return api_error(str(e), 400)
        else:
            mock_db["employees"] = [e for e in mock_db["employees"] if str(e["id"]) != str(emp_id)]
        return jsonify({"success": True})

    data = request.get_json(silent=True) or {}
    # never let the client rewrite the primary key or unknown columns
    allowed = {"full_name", "email", "phone", "department_id", "designation_id", "manager_id",
               "date_of_joining", "employment_type", "work_location", "status", "salary_ctc"}
    patch = {k: v for k, v in data.items() if k in allowed}
    if not patch:
        return api_error("Nothing to update")
    if "department_id" in patch:
        patch["department_id"] = resolve_department_id(patch["department_id"])
    try:
        row = update_row("employees", emp_id, patch)
    except DataError as e:
        return api_error(str(e), 400)
    return jsonify(norm_employee(row))


@app.route('/api/attendance', methods=['GET', 'POST'])
def api_attendance():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        action = data.get('action')
        if action not in ('clock_in', 'clock_out'):
            return api_error("Invalid attendance action")

        emp = current_employee(data.get('employee_id'))
        if not emp:
            return api_error("Add an employee before recording attendance", 404)
        employee_id = emp["id"]
        today = str(date.today())
        now = datetime.now()

        rows = get_supabase_data("attendance", {"employee_id": employee_id})
        existing = next((a for a in rows if _fmt_date(a.get("date")) == today), None)

        if existing:
            if action == 'clock_out':
                # FIX: work_hours was hardcoded to 8.0 - compute it for real.
                hours = existing.get("work_hours") or 0
                try:
                    ci = existing.get("clock_in")
                    if ci:
                        s = str(ci).replace("Z", "+00:00")
                        if "T" in s:
                            ci_dt = datetime.fromisoformat(s)
                        else:
                            ci_dt = datetime.strptime(f"{today} {_fmt_time(ci)}", "%Y-%m-%d %I:%M %p")
                        hours = round(max(0.0, (now - ci_dt).total_seconds() / 3600.0), 2)
                except Exception:
                    pass
                patch = {"clock_out": now.isoformat() if supabase else now.strftime("%I:%M %p"),
                         "work_hours": hours}
                try:
                    row = update_row("attendance", existing["id"], patch)
                except DataError as e:
                    return api_error(str(e), 400)
                return jsonify({"success": True, "message": "Clocked out successfully",
                                "attendance": norm_attendance(row)})
            return jsonify({"success": True, "message": "Already clocked in today",
                            "attendance": norm_attendance(existing)})

        if action == 'clock_out':
            return api_error("You have not clocked in yet today")

        payload = {"employee_id": employee_id, "date": today,
                   "clock_in": now.isoformat() if supabase else now.strftime("%I:%M %p"),
                   "status": "Present", "work_hours": 0}
        try:
            row = insert_supabase_data("attendance", payload)
        except DataError as e:
            return api_error(f"Could not record attendance: {e}", 400)
        return jsonify({"success": True, "message": "Clocked in successfully",
                        "attendance": norm_attendance(row)})

    # ---- GET ----
    employee_id = request.args.get('employee_id')
    scope = request.args.get('scope', 'me')  # me | all
    emp_names = employee_name_map()
    rows = get_supabase_data("attendance")

    if employee_id:
        rows = [a for a in rows if str(a.get("employee_id")) == str(employee_id)]
    elif scope == 'me':
        # FIX: "My Attendance" used to list every employee's punches.
        me = current_employee_id()
        if me:
            rows = [a for a in rows if str(a.get("employee_id")) == str(me)]

    rows = [norm_attendance(a, emp_names) for a in rows]
    rows.sort(key=lambda x: x.get('date') or '', reverse=True)
    return jsonify(rows[:60])


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
        except ValueError:
            return api_error("Invalid date format. Use YYYY-MM-DD")
        if end_dt < start_dt:
            return api_error("End date must be on or after start date")
        days = int(data.get('days') or (end_dt - start_dt).days + 1)

        emp = current_employee(data.get('employee_id'))
        if not emp:
            return api_error("No employee record found to apply leave against", 404)

        # FIX: map the leave-type NAME coming from the dropdown to its real id.
        leave_type_id = resolve_leave_type_id(data.get('leave_type_id') or data.get('leave_type'))
        if not leave_type_id:
            return api_error("Please choose a valid leave type")

        # Overlap guard - the original let you book the same dates repeatedly.
        for l in get_supabase_data("leave_requests", {"employee_id": emp["id"]}):
            if l.get("status") in ("Pending", "Approved"):
                try:
                    s = datetime.strptime(_fmt_date(l.get("start_date")), "%Y-%m-%d").date()
                    e = datetime.strptime(_fmt_date(l.get("end_date")), "%Y-%m-%d").date()
                except Exception:
                    continue
                if start_dt <= e and end_dt >= s:
                    return api_error(f"You already have a {l.get('status','').lower()} leave "
                                     f"from {s} to {e} that overlaps these dates")

        payload = {
            "employee_id": emp["id"],
            "leave_type_id": leave_type_id,
            "start_date": start_date,
            "end_date": end_date,
            "days": days,
            "reason": (data.get('reason') or '').strip(),
            "status": "Pending",
        }
        if not supabase:
            lt = next((t for t in get_supabase_data("leave_types") if str(t["id"]) == str(leave_type_id)), {})
            payload["employee_name"] = emp.get("full_name")
            payload["leave_type"] = lt.get("name")
            payload["applied_at"] = str(date.today())

        try:
            created = insert_supabase_data("leave_requests", payload)
        except DataError as e:
            # FIX: this used to return HTTP 200 with the unsaved payload.
            return api_error(f"Could not save leave request: {e}", 400)
        return jsonify(norm_leave(created))

    # ---- GET ----
    status_filter = request.args.get('status')
    employee_id = request.args.get('employee_id')
    scope = request.args.get('scope')
    emp_names, types = employee_name_map(), leave_type_map()
    rows = [norm_leave(l, emp_names, types) for l in get_supabase_data("leave_requests")]

    if employee_id:
        rows = [r for r in rows if str(r.get("employee_id")) == str(employee_id)]
    elif scope == 'me':
        me = current_employee_id()
        if me:
            rows = [r for r in rows if str(r.get("employee_id")) == str(me)]
    if status_filter and status_filter != 'All':
        rows = [r for r in rows if r.get('status') == status_filter]

    rows.sort(key=lambda r: (r.get('applied_at') or '', r.get('start_date') or ''), reverse=True)
    return jsonify(rows)


@app.route('/api/leave-requests/<req_id>/action', methods=['POST'])
def api_leave_action(req_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ('Approved', 'Rejected', 'Cancelled'):
        return api_error("Status must be Approved, Rejected or Cancelled")

    patch = {"status": new_status}
    if supabase:
        patch["actioned_at"] = datetime.now().isoformat()
    try:
        row = update_row("leave_requests", req_id, patch)
    except DataError as e:
        return api_error(str(e), 400)
    return jsonify(norm_leave(row))


@app.route('/api/leave-balances')
def api_leave_balances():
    """
    FIX: the UI invented balances with Math.random() on every render, so the
    numbers changed each time you opened the page. These are computed.
    """
    emp_id = request.args.get('employee_id') or current_employee_id()
    year = date.today().year
    types = get_supabase_data("leave_types")
    requests_ = [l for l in get_supabase_data("leave_requests")
                 if str(l.get("employee_id")) == str(emp_id)]

    out = []
    for t in types:
        used = 0
        pending = 0
        for l in requests_:
            if str(l.get("leave_type_id")) != str(t["id"]):
                continue
            sd = _fmt_date(l.get("start_date")) or ""
            if not sd.startswith(str(year)):
                continue
            if l.get("status") == "Approved":
                used += int(l.get("days") or 0)
            elif l.get("status") == "Pending":
                pending += int(l.get("days") or 0)
        quota = int(t.get("yearly_quota") or 0)
        out.append({
            "id": t["id"], "name": t.get("name"), "code": t.get("code"),
            "color": t.get("color") or "#6c5ce7", "yearly_quota": quota,
            "used": used, "pending": pending,
            "available": max(0, quota - used),
            "used_pct": round(used / quota * 100, 1) if quota else 0,
        })
    return jsonify(out)


@app.route('/api/departments')
def api_departments():
    depts = get_supabase_data("departments")
    employees = get_supabase_data("employees")
    out = []
    for d in depts:
        count = len([e for e in employees if str(e.get("department_id")) == str(d["id"])])
        row = dict(d)
        row["employee_count"] = count
        out.append(row)
    return jsonify(out)


@app.route('/api/jobs', methods=['GET', 'POST'])
def api_jobs():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        if not title:
            return api_error("Job title is required")
        # FIX: the form posts a department NAME; the column is a uuid FK.
        department_id = resolve_department_id(data.get('department_id') or data.get('department'))
        if not department_id:
            return api_error("Please choose a valid department")
        try:
            openings = int(data.get('openings') or 1)
        except (TypeError, ValueError):
            return api_error("Openings must be a number")

        status = data.get('status') or 'Open'
        if status not in ('Open', 'On Hold', 'Closed'):
            status = 'Open'

        payload = {
            "title": title,
            "department_id": department_id,
            "location": data.get('location') or 'Bangalore',
            "openings": openings,
            "description": data.get('description') or '',
            "status": status,   # FIX: the chosen status used to be ignored
        }
        if not supabase:
            payload["department"] = next((d["name"] for d in mock_db["departments"] if d["id"] == department_id), "-")
            payload["applicants"] = 0
        try:
            created = insert_supabase_data("jobs", payload)
        except DataError as e:
            return api_error(f"Could not create job: {e}", 400)
        return jsonify(norm_job(created))

    depts = department_name_map()
    candidates = get_supabase_data("candidates")
    counts = {}
    for c in candidates:
        k = str(c.get("job_id"))
        counts[k] = counts.get(k, 0) + 1
    jobs = [norm_job(j, depts, counts if supabase else None) for j in get_supabase_data("jobs")]
    return jsonify(jobs)


@app.route('/api/candidates')
def api_candidates():
    job_id = request.args.get('job_id')
    jobs = {str(j["id"]): j.get("title") for j in get_supabase_data("jobs")}
    rows = get_supabase_data("candidates", {"job_id": job_id} if job_id else None)
    return jsonify([norm_candidate(c, jobs) for c in rows])


@app.route('/api/payslips')
def api_payslips():
    emp_id = request.args.get('employee_id')
    scope = request.args.get('scope')
    emp_names = employee_name_map()
    rows = get_supabase_data("payslips")
    if emp_id:
        rows = [p for p in rows if str(p.get("employee_id")) == str(emp_id)]
    elif scope == 'me':
        me = current_employee_id()
        if me:
            rows = [p for p in rows if str(p.get("employee_id")) == str(me)]
    rows = [norm_payslip(p, emp_names) for p in rows]
    rows.sort(key=lambda p: (p.get('year') or 0, p.get('month') or 0), reverse=True)
    return jsonify(rows)


@app.route('/api/announcements')
def api_announcements():
    rows = [norm_announcement(a) for a in get_supabase_data("announcements")]
    rows.sort(key=lambda a: (a.get('is_pinned', False), a.get('date') or ''), reverse=True)
    return jsonify(rows)


@app.route('/api/goals', methods=['GET', 'POST'])
def api_goals():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        title = (data.get('title') or '').strip()
        if not title:
            return api_error("Goal title is required")
        emp = current_employee(data.get('employee_id'))
        if not emp:
            return api_error("No employee record found", 404)
        try:
            progress = max(0, min(100, int(data.get('progress') or 0)))
        except (TypeError, ValueError):
            progress = 0
        payload = {
            "employee_id": emp["id"], "title": title,
            "description": data.get('description') or '',
            "progress": progress,
            "status": data.get('status') or ('Completed' if progress >= 100 else 'In Progress'),
            "due_date": data.get('due_date') or str(date.today() + timedelta(days=30)),
        }
        try:
            created = insert_supabase_data("goals", payload)
        except DataError as e:
            return api_error(f"Could not create goal: {e}", 400)
        return jsonify(norm_goal(created))

    emp_id = request.args.get('employee_id')
    scope = request.args.get('scope')
    emp_names = employee_name_map()
    rows = get_supabase_data("goals")
    if emp_id:
        rows = [g for g in rows if str(g.get("employee_id")) == str(emp_id)]
    elif scope == 'me':
        me = current_employee_id()
        if me:
            rows = [g for g in rows if str(g.get("employee_id")) == str(me)]
    return jsonify([norm_goal(g, emp_names) for g in rows])


@app.route('/api/goals/<goal_id>', methods=['PUT'])
def api_goal_update(goal_id):
    data = request.get_json(silent=True) or {}
    patch = {}
    if 'progress' in data:
        try:
            patch['progress'] = max(0, min(100, int(data['progress'])))
        except (TypeError, ValueError):
            return api_error("Progress must be a number 0-100")
        patch['status'] = 'Completed' if patch['progress'] >= 100 else 'In Progress'
    if 'status' in data:
        patch['status'] = data['status']
    if not patch:
        return api_error("Nothing to update")
    try:
        row = update_row("goals", goal_id, patch)
    except DataError as e:
        return api_error(str(e), 400)
    return jsonify(norm_goal(row))


@app.route('/api/holidays')
def api_holidays():
    rows = get_supabase_data("holidays")
    out = []
    for h in rows:
        r = dict(h)
        r["date"] = _fmt_date(h.get("date"))
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d").date()
            r["day"] = d.strftime("%A")
            r["upcoming"] = d >= date.today()
        except Exception:
            r["day"], r["upcoming"] = "", False
        out.append(r)
    out.sort(key=lambda h: h.get("date") or "")
    return jsonify(out)


@app.route('/api/leave-types')
def api_leave_types():
    return jsonify(get_supabase_data("leave_types"))


@app.route('/api/reimbursements', methods=['GET', 'POST'])
def api_reimbursements():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        category = (data.get('category') or '').strip()
        if not category:
            return api_error("Category is required")
        try:
            amount = float(data.get('amount') or 0)
        except (TypeError, ValueError):
            return api_error("Amount must be a number")
        if amount <= 0:
            return api_error("Amount must be greater than zero")

        emp = current_employee(data.get('employee_id'))
        if not emp:
            return api_error("No employee record found", 404)

        payload = {
            "employee_id": emp["id"],
            "category": category,
            "amount": amount,
            "date": data.get('date') or str(date.today()),
            "description": data.get('description') or '',
            "status": "Pending",
        }
        try:
            created = insert_supabase_data("reimbursements", payload)
        except DataError as e:
            return api_error(f"Could not submit expense: {e}", 400)
        return jsonify(norm_reimbursement(created))

    emp_names = employee_name_map()
    scope = request.args.get('scope')
    rows = get_supabase_data("reimbursements")
    if scope == 'me':
        me = current_employee_id()
        if me:
            rows = [r for r in rows if str(r.get("employee_id")) == str(me)]
    rows = [norm_reimbursement(r, emp_names) for r in rows]
    rows.sort(key=lambda r: r.get('date') or '', reverse=True)
    return jsonify(rows)


@app.route('/api/reimbursements/<rid>/action', methods=['POST'])
def api_reimbursement_action(rid):
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    if status not in ('Approved', 'Rejected', 'Paid'):
        return api_error("Status must be Approved, Rejected or Paid")
    try:
        row = update_row("reimbursements", rid, {"status": status})
    except DataError as e:
        return api_error(str(e), 400)
    return jsonify(norm_reimbursement(row))


@app.route('/api/documents')
def api_documents():
    """Previously the Documents tab had no endpoint at all - it was a blank page."""
    emp_names = employee_name_map()
    scope = request.args.get('scope')
    rows = get_supabase_data("documents")
    if scope == 'me':
        me = current_employee_id()
        if me:
            rows = [d for d in rows if str(d.get("employee_id")) == str(me)]
    return jsonify([norm_document(d, emp_names) for d in rows])


@app.route('/api/org-chart')
def api_org_chart():
    """Reporting tree for the Organisation Chart tab (was an empty placeholder)."""
    depts = department_name_map()
    desigs = designation_title_map()
    names = employee_name_map()
    employees = [norm_employee(e, depts, desigs, names) for e in get_supabase_data("employees")]

    by_id = {str(e["id"]): e for e in employees}
    nodes = {str(e["id"]): {
        "id": str(e["id"]), "name": e.get("full_name"), "title": e.get("designation"),
        "department": e.get("department"), "avatar": e.get("avatar"),
        "email": e.get("email"), "children": []
    } for e in employees}

    roots = []
    for e in employees:
        mid = str(e.get("manager_id")) if e.get("manager_id") else None
        node = nodes[str(e["id"])]
        if mid and mid in nodes and mid != str(e["id"]):
            nodes[mid]["children"].append(node)
        else:
            roots.append(node)

    # No manager_id data at all -> group by department so the tab still renders.
    if len(roots) == len(employees) and employees:
        grouped = {}
        for e in employees:
            grouped.setdefault(e.get("department") or "Unassigned", []).append(nodes[str(e["id"])])
        roots = [{"id": f"dept-{n}", "name": n, "title": f"{len(v)} member(s)",
                  "department": n, "avatar": _initials(n), "email": "", "children": v}
                 for n, v in sorted(grouped.items())]

    return jsonify({"roots": roots, "total": len(employees)})


@app.route('/api/timesheet')
def api_timesheet():
    """Weekly hours derived from attendance (the tab had no data source)."""
    emp_id = request.args.get('employee_id') or current_employee_id()
    rows = [a for a in get_supabase_data("attendance") if str(a.get("employee_id")) == str(emp_id)]

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    week = []
    total = 0.0
    for i in range(7):
        d = monday + timedelta(days=i)
        ds = str(d)
        row = next((a for a in rows if _fmt_date(a.get("date")) == ds), None)
        hours = float(row.get("work_hours") or 0) if row else 0.0
        total += hours
        week.append({
            "date": ds, "day": d.strftime("%a"), "hours": round(hours, 2),
            "clock_in": _fmt_time(row.get("clock_in")) if row else None,
            "clock_out": _fmt_time(row.get("clock_out")) if row else None,
            "status": (row or {}).get("status") or ("Weekend" if i >= 5 else ("Upcoming" if d > today else "Absent")),
            "is_today": d == today,
        })
    return jsonify({"week_start": str(monday), "week_end": str(monday + timedelta(days=6)),
                    "days": week, "total_hours": round(total, 2), "expected_hours": 40})


@app.route('/api/reports')
def api_reports():
    """Aggregates for the Reports tab (was an empty placeholder)."""
    employees = get_supabase_data("employees")
    attendance = get_supabase_data("attendance")
    leaves = get_supabase_data("leave_requests")
    payslips = get_supabase_data("payslips")
    depts = department_name_map()
    types = leave_type_map()

    headcount = {}
    location = {}
    status_mix = {}
    ctc_total = 0
    for e in employees:
        dn = e.get("department") or depts.get(str(e.get("department_id"))) or "Unassigned"
        headcount[dn] = headcount.get(dn, 0) + 1
        loc = e.get("work_location") or "-"
        location[loc] = location.get(loc, 0) + 1
        st = e.get("status") or "Active"
        status_mix[st] = status_mix.get(st, 0) + 1
        try:
            ctc_total += float(e.get("salary_ctc") or 0)
        except (TypeError, ValueError):
            pass

    leave_by_type = {}
    for l in leaves:
        lt = types.get(str(l.get("leave_type_id")))
        n = l.get("leave_type") or (lt.get("name") if lt else "Leave")
        leave_by_type[n] = leave_by_type.get(n, 0) + int(l.get("days") or 0)

    today = str(date.today())
    present_today = len([a for a in attendance if _fmt_date(a.get("date")) == today and a.get("status") == "Present"])
    total_payroll = sum(float(p.get("net_pay") or p.get("net") or 0) for p in payslips)

    return jsonify({
        "headcount_by_department": headcount,
        "headcount_by_location": location,
        "status_mix": status_mix,
        "leave_days_by_type": leave_by_type,
        "total_employees": len(employees),
        "present_today": present_today,
        "attendance_rate": round(present_today / len(employees) * 100, 1) if employees else 0,
        "pending_leaves": len([l for l in leaves if l.get("status") == "Pending"]),
        "approved_leaves": len([l for l in leaves if l.get("status") == "Approved"]),
        "avg_ctc": round(ctc_total / len(employees)) if employees else 0,
        "total_ctc": round(ctc_total),
        "payroll_processed": round(total_payroll),
    })


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


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Endpoint not found"}), 404
    return redirect(url_for('dashboard'))


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": "Internal server error"}), 500
    return "Internal server error", 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"""
    🚀 Keka HRMS Clone Starting...
    ---------------------------------
    Dashboard: http://localhost:{port}/dashboard
    Login: http://localhost:{port}/login
    API Health: http://localhost:{port}/api/health
    Supabase: {'Connected ✅' if supabase else 'Mock Mode ⚠️ (Set .env to enable Supabase)'}
    ---------------------------------
    Demo Login: any email + any password
    """)
    app.run(host='0.0.0.0', port=port, debug=True)
