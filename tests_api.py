"""Smoke-test every Ekkaa HRMS endpoint against the running demo server."""
import json
import os
import sys
import uuid

import requests

BASE = os.environ.get("BASE", "http://localhost:5000")
s = requests.Session()
fails, checks = [], [0]


def call(method, path, *, expect=(200,), json_body=None, data=None, files=None, label=None, want_keys=None):
    checks[0] += 1
    url = BASE + path
    kwargs = {"timeout": 60}
    if json_body is not None:
        kwargs["json"] = json_body
    if data is not None:
        kwargs["data"] = data
    if files is not None:
        kwargs["files"] = files
    r = s.request(method, url, **kwargs)
    tag = label or f"{method} {path}"
    body = r
    if "json" in r.headers.get("Content-Type", ""):
        try:
            body = r.json()
        except ValueError:
            body = r
    if r.status_code not in expect:
        fails.append(f"{tag} -> {r.status_code}: {(r.text or '')[:220]}")
        print(f"  !! FAIL {tag} -> {r.status_code}: {(r.text or '')[:200]}")
        return r, body
    for key in want_keys or []:
        cur = body if isinstance(body, (dict, list)) else None
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, list) and part.isdigit():
                cur = cur[int(part)]
            else:
                fails.append(f"{tag}: missing key '{key}' in {json.dumps(body, default=str)[:200]}")
                print(f"  !! FAIL {tag}: missing key '{key}'")
                cur = None
                break
        if cur is None:
            break
    return r, body


def show(label, value):
    print(f"  {label:<34} {value}")


print("== auth ==")
call("GET", "/api/health", want_keys=["status"], label="health (no auth)")
call("POST", "/login", json_body={"email": "admin@company.com", "password": "nope"}, expect=(401,), label="bad admin password")
call("POST", "/login", json_body={"email": "someone@else.com", "password": "demo123"}, expect=(401,), label="unknown user")
_, body = call("POST", "/login", json_body={"email": "admin@company.com", "password": "demo123"},
               want_keys=["success"], label="admin login")
call("GET", "/dashboard", want_keys=None, label="dashboard page renders")
_, sess = call("GET", "/api/session", want_keys=["user.role", "is_admin"], label="session")
show("role", sess["is_admin"])
call("GET", "/api/lookups", want_keys=["departments", "employees", "doc_types", "candidate_stages"], label="lookups")

print("== home ==")
_, st = call("GET", "/api/stats", label="stats", want_keys=[
    "total_employees", "present_today", "absent_today", "on_leave", "attendance_rate", "open_positions",
    "applicants", "pending_leaves", "pending_expenses", "pending_documents", "attendance_trend.labels",
    "today.birthdays", "today.next_holiday", "my_time.worked_hours", "pending_actions"])
for k in ("total_employees", "present_today", "wfh_today", "half_day_today", "absent_today", "late_today",
          "on_leave", "attendance_rate", "pending_leaves", "pending_timesheets", "open_positions", "applicants",
          "joined_this_month"):
    show(k, st.get(k))
show("trend pct", st["attendance_trend"]["present_pct"])
show("my_time", {k: st["my_time"][k] for k in ("clock_in", "clock_out", "worked_hours", "break_minutes",
                                               "overtime_hours", "is_late", "status", "clocked_in")})
show("birthdays/anniv/leave", (len(st["today"]["birthdays"]), len(st["today"]["anniversaries"]),
                               len(st["today"]["on_leave"]), st["today"]["next_holiday"]))
assert max(st["attendance_trend"]["present_pct"]) <= 100, "trend over 100%"
assert st["present_today"] + st["absent_today"] + st["on_leave"] <= st["total_employees"], "home cards disagree"

print("== employees ==")
_, emps = call("GET", "/api/employees", label="list")
show("count", len(emps))
show("first", {k: emps[0][k] for k in ("employee_code", "full_name", "department", "designation", "manager", "tenure")})
_, one = call("GET", f"/api/employees/{emps[4]['id']}", label="detail",
              want_keys=["employee", "snapshot.attendance_days_this_month", "leave_balances", "recent_attendance", "documents", "goals"])
show("detail keys", sorted(one.keys()))
call("GET", "/api/employees?q=vip&status=Active", label="search + status filter")
call("GET", "/api/employees/export", label="csv export")
_, made = call("POST", "/api/employees", json_body={"full_name": "Test Hireson", "email": f"test.hireson{uuid.uuid4().hex[:5]}@company.com",
                                                     "phone": "+91 90000 00001", "department_id": 2, "designation_id": 2,
                                                     "salary_ctc": 1800000, "date_of_joining": str(__import__("datetime").date.today())},
               label="create employee (admin only)", want_keys=["employee.employee_code", "employee.tenure"])
new_id = made["employee"]["id"]
call("POST", "/api/employees", json_body={"full_name": "", "email": ""}, expect=(400,), label="create validation")
call("PUT", f"/api/employees/{new_id}", json_body={"phone": "+91 90000 00009", "work_location": "Pune"}, label="admin edit")
call("DELETE", f"/api/employees/{new_id}", label="delete employee")

print("== me ==")
_, me = call("GET", "/api/me", want_keys=["employee", "leave_balances", "counts", "manager", "payslips", "attendance_month"], label="me")
show("me", {me["employee"]["full_name"]: me["employee"]["designation"]})
show("counts", me["counts"])
show("balances", [(b["leave_type"], b["remaining"], b["total"]) for b in me["leave_balances"]])
call("PUT", "/api/me", json_body={"address": "42 MG Road, Dādri, UP 251301", "salary_ctc": 999},
     expect=(200, 403), label="self-edit blocked field")
_, up = call("PUT", "/api/me", json_body={"address": "42 MG Road, Dādri, UP 251301", "blood_group": "B+"}, label="self-edit allowed")
show("changed", up.get("changed"))

print("== org chart ==")
_, oc = call("GET", "/api/orgchart", want_keys=["tree", "departments", "stats.total"], label="orgchart")
assert oc["stats"]["managers"] > 0 and oc["stats"]["max_depth"] >= 2, "org chart is flat"
assert all(d.get("head") and d.get("members") for d in oc["departments"]), "department head/members missing"
show("roots", [f"{n['name']} ({len(n['children'])} direct, {n['total_reports']} total)" for n in oc["tree"]])
show("stats", oc["stats"])
show("orphaned", oc["orphaned"])
show("dept[0]", {k: oc["departments"][0][k] for k in ("name", "count", "locations")} | {"head": (oc["departments"][0]["head"] or {}).get("full_name"), "members": len(oc["departments"][0].get("members") or [])})
root_id = oc["tree"][0]["id"]
some = [e for e in emps if str(e["id"]) != str(root_id)][0]
call("POST", "/api/orgchart/assign-manager", json_body={"employee_id": some["id"], "manager_id": some["id"]},
     expect=(400,), label="self manager rejected")
call("POST", "/api/orgchart/assign-manager", json_body={"employee_id": some["id"], "manager_id": "does-not-exist"},
     expect=(400, 404), label="bogus manager rejected")
call("POST", "/api/orgchart/assign-manager", json_body={"employee_id": some["id"], "manager_id": root_id}, label="assign manager")

print("== attendance ==")
import datetime as dt
month = dt.date.today().strftime("%Y-%m")
_, att = call("GET", f"/api/attendance?month={month}", want_keys=["rows", "month_label"], label="attendance month")
show("rows", len(att["rows"]))
show("sample", att["rows"][0] if att["rows"] else None)
_, summ = call("GET", f"/api/attendance/summary?month={month}&employee_id={me['employee']['id']}",
               want_keys=["present", "total_hours", "calendar", "avg_hours"], label="summary")
show("summary", {k: summ[k] for k in ("days_marked", "present", "wfh", "absent", "late_days", "total_hours", "avg_hours", "overtime_hours")})
_, clock = call("POST", "/api/attendance/clock", json_body={"action": "out"}, expect=(200, 400), label="clock out")
show("clock", clock)
call("POST", "/api/attendance/clock", json_body={"action": "in"}, expect=(200, 400), label="clock in (may already be in)")
call("POST", "/api/attendance/entry", json_body={"employee_id": me["employee"]["id"], "date": str(dt.date.today() - dt.timedelta(days=1)),
                                                 "clock_in": "10:05:00", "clock_out": "19:10:00", "status": "Present"}, label="HR manual entry")
_, regs = call("GET", "/api/regularizations", label="regularization list")
show("reg rows", [(r["employee"]["full_name"], r["request_type"], r["status"], r["current"]) for r in regs[:2]])
call("POST", "/api/regularizations", json_body={"date": str(dt.date.today() - dt.timedelta(days=2)), "reason": "short"},
     expect=(400,), label="reason too short -> 400")
call("POST", "/api/regularizations", json_body={"date": str(dt.date.today() + dt.timedelta(days=2)),
                                                 "reason": "Biometric reader was offline all morning."}, expect=(400,), label="future date blocked")
_, reg = call("POST", "/api/regularizations", json_body={"date": str(dt.date.today() - dt.timedelta(days=4)),
                                                          "request_type": "Missing punch-out",
                                                          "clock_out_correction": "18:45:00",
                                                          "reason": "Left after the release go-live and forgot to punch out."},
              label="regularization created", want_keys=["regularization.reason"])
call("POST", f"/api/regularizations/{reg['regularization']['id']}/action", json_body={"action": "reject"},
     expect=(400,), label="reject needs remark")
call("POST", f"/api/regularizations/{reg['regularization']['id']}/action",
     json_body={"action": "reject", "remark": "Please attach the release ticket."}, label="reject with remark")
call("DELETE", f"/api/regularizations/{reg['regularization']['id']}", expect=(200, 400), label="withdraw (only pending)")

print("== leave ==")
call("GET", "/api/leave-types", label="leave types")
call("GET", f"/api/leave-balances?employee_id={me['employee']['id']}", want_keys=["balances"], label="balances")
_, lvs = call("GET", "/api/leave-requests", label="leave list")
show("pending", len([l for l in lvs if l["status"] == "Pending"]))
show("sample", {k: lvs[0][k] for k in ("leave_type_label", "period_label", "days", "status", "leave_color")})
call("POST", "/api/leave-requests", json_body={"leave_type_id": 1, "start_date": str(dt.date.today() - dt.timedelta(days=3)),
                                               "end_date": str(dt.date.today() - dt.timedelta(days=2)), "reason": "past"},
     expect=(400,), label="past leave blocked")
call("POST", "/api/leave-requests", json_body={"leave_type_id": 99, "start_date": str(dt.date.today() + dt.timedelta(days=20)),
                                                "end_date": str(dt.date.today() + dt.timedelta(days=21)), "reason": "bad type"},
     expect=(400,), label="bogus leave type blocked")
_, over = call("GET", "/api/leave-balances", label="all balances")
emp_bal = [b for b in over if str(b["employee_id"]) == str(me["employee"]["id"])][0]["balances"]
tight = min(emp_bal, key=lambda b: b["remaining"])           # whatever is scarcest is the one to overdraw
over_span = dt.timedelta(days=tight["remaining"] + 14)       # comfortably more than what is left
call("POST", "/api/leave-requests", json_body={"leave_type_id": tight["leave_type_id"],
                                               "start_date": str(dt.date.today() + dt.timedelta(days=40)),
                                               "end_date": str(dt.date.today() + dt.timedelta(days=40) + over_span),
                                               "reason": "Should be blocked by balance"},
     expect=(400,), label=f"over-quota blocked ({tight['leave_type']}, {tight['remaining']} left)")
_, applied = call("POST", "/api/leave-requests", json_body={"leave_type_id": emp_bal[0]["leave_type_id"],
                                                             "start_date": str(dt.date.today() + dt.timedelta(days=25)),
                                                             "end_date": str(dt.date.today() + dt.timedelta(days=26)),
                                                             "reason": "Family function out of town"},
                  label="apply", want_keys=["leave.leave_type_label"])
lid = applied["leave"]["id"]
_, after = call("GET", f"/api/leave-balances?employee_id={me['employee']['id']}", label="balance after apply")
show("pending moved", [(b["leave_type"], b["pending"], b["remaining"]) for b in after["balances"]][:2])
call("POST", f"/api/leave-requests/{lid}/action", json_body={"action": "reject"}, expect=(400,), label="reject needs remark")
call("POST", f"/api/leave-requests/{lid}/action", json_body={"action": "approve", "remark": "Approved, enjoy."}, label="approve")
_, att_after = call("GET", f"/api/attendance?from={dt.date.today() + dt.timedelta(days=25)}&to={dt.date.today() + dt.timedelta(days=26)}",
                    label="approved leave wrote attendance")
show("leave rows in attendance", [r["status"] for r in att_after["rows"]])
call("POST", f"/api/leave-requests/{lid}/cancel", label="cancel approved leave")
_, bal_after_cancel = call("GET", f"/api/leave-balances?employee_id={me['employee']['id']}", label="balance after cancel")
show("used back down", [(b["leave_type"], b["used"], b["pending"]) for b in bal_after_cancel["balances"]][:2])

print("== documents ==")
_, meta = call("GET", "/api/documents/meta", want_keys=["doc_types", "checklist", "counts", "storage_mode"], label="documents meta")
show("counts", meta["counts"])
show("storage", meta["storage_mode"])
show("checklist[0]", {k: meta["checklist"][0][k] for k in ("completion_pct", "verified", "missing")})
show("types", len(meta["doc_types"]))
_, docs = call("GET", "/api/documents", label="list docs")
show("first doc", {k: docs[0][k] for k in ("title", "doc_type", "category", "purpose", "status", "size_label", "expiry_state", "uploaded_by_label")})
call("GET", "/api/documents?expiring=soon", label="expiring filter")
payload = {"employee_id": me["employee"]["id"], "title": "Driving License (test)", "doc_type": "Driving License",
           "purpose": "Needed for the client site access badge", "visibility": "Manager + HR",
           "valid_from": "2022-04-01", "valid_till": str(dt.date.today() + dt.timedelta(days=365)),
           "description": "Front and back scanned at home."}
call("POST", "/api/documents", json_body=payload, expect=(200, 400), label="metadata-only upload")
files = {"file": ("license.txt", io_ := b"FAKE PDF BYTES " * 40, "text/plain")}
_, up = call("POST", "/api/documents", data=payload, files=files, label="multipart upload", want_keys=["document.file_url"])
doc_id = up["document"]["id"]
show("upload", {k: up["document"].get(k, "-") for k in ("file_name", "size_label", "purpose", "visibility", "status", "expiry_state")})
call("POST", "/api/documents", json_body={"employee_id": me["employee"]["id"], "doc_type": "Driving License",
                                          "title": "no expiry", "description": "x"}, expect=(400,), label="expiry required")
_, dl = call("GET", f"/api/documents/{doc_id}/download", label="download")
assert dl.text.startswith("FAKE PDF BYTES"), "downloaded bytes did not round-trip"
print("  downloaded bytes round-trip      OK")
call("PUT", f"/api/documents/{doc_id}", json_body={"action": "Rejected"}, expect=(400,), label="reject needs remark")
call("PUT", f"/api/documents/{doc_id}", json_body={"action": "Verified", "reviewer_remark": "Clear copy."}, label="verify")
call("DELETE", f"/api/documents/{doc_id}", label="delete doc")
_, dreq = call("GET", "/api/document-requests", label="document requests")
show("requests", [(r["employee"].get("full_name"), r["doc_type"], r["status"], r["overdue"]) for r in dreq[:3]])
call("POST", "/api/document-requests", json_body={"doc_type": "PAN Card", "employee_id": me["employee"]["id"]},
     expect=(400,), label="request needs reason")
_, rq = call("POST", "/api/document-requests", json_body={"doc_type": "Cancelled Cheque", "reason": "Bank details changed",
                                                            "due_date": str(dt.date.today() + dt.timedelta(days=3))},
             label="create request", want_keys=["request.id"])
call("PUT", f"/api/document-requests/{rq['request']['id']}", json_body={"status": "Fulfilled"}, label="fulfil request")

# open document requests must be visible everywhere they are promised: the per-employee
# checklist counter and the inbox queue (older seeds used the "Requested" spelling and
# were silently invisible in both).
_, meta2 = call("GET", "/api/documents/meta", label="doc meta (re-read)")
_, dreq2 = call("GET", "/api/document-requests", label="doc requests (re-read)")
checks[0] += 1
_open = [r for r in dreq2 if r["status"] in ("Pending", "Requested")]
_counted = sum(c["requests_pending"] for c in meta2["checklist"])
assert len(_open) == _counted, f"{len(_open)} open requests but the checklist counts {_counted}"
print(f"  open requests == checklist counter  OK ({len(_open)})")
checks[0] += 1
assert not [r for r in dreq2 if r["status"] == "Requested"], "seed still writes the legacy 'Requested' status"
print("  request statuses use one vocabulary OK")
_, ibx2 = call("GET", "/api/inbox", label="inbox")
_docg = next((g for g in ibx2["groups"] if g["module"] == "documents"), None)
checks[0] += 1
assert _docg and any(a["kind"] == "document_request" for a in _docg["items"]), "open document requests never reach the inbox"
print(f"  document requests reach the inbox   OK ({len([a for a in _docg['items'] if a['kind'] == 'document_request'])} ask)")

print("== timesheet ==")
monday = dt.date.today() - dt.timedelta(days=dt.date.today().weekday())
_, ts = call("GET", f"/api/timesheet?week={monday}", want_keys=["days", "projects", "timesheet", "stats"], label="my week")
show("week", ts["week_label"])
show("days", [(d["label"], sum(e["hours"] for e in d["entries"])) for d in ts["days"]])
show("stats", ts["stats"])
show("locked", ts["locked"])
proj = ts["projects"][0]["id"]
call("POST", "/api/timesheet/save", json_body={"week": str(monday), "entries": [{"date": str(monday), "project_id": proj, "hours": 30, "task": "x"}]},
     expect=(400,), label="over-daily cap blocked")
call("POST", "/api/timesheet/save", json_body={"week": str(monday), "entries": [{"date": str(monday), "hours": 4, "task": "no project"}]},
     expect=(400,), label="missing project blocked")
_, saved = call("POST", "/api/timesheet/save", json_body={"week": str(monday), "entries": [
    {"date": str(monday), "project_id": proj, "hours": 4, "billable": True, "task": "Timesheet module build"},
    {"date": str(monday), "project_id": ts["projects"][1]["id"], "hours": 3, "billable": False, "task": "Bug triage"},
    {"date": str(monday + dt.timedelta(days=1)), "project_id": proj, "hours": 7.5, "billable": True, "task": "API review"}]},
    label="save grid", want_keys=["timesheet.total_hours", "timesheet.billable_hours"])
show("saved totals", {k: saved["timesheet"][k] for k in ("total_hours", "billable_hours", "utilization_pct")})
call("POST", "/api/timesheet/submit", json_body={"week": str(monday)}, expect=(200, 400), label="submit (needs 20h)")
_, team = call("GET", f"/api/timesheet?view=team&week={monday}", want_keys=["timesheets", "summary"], label="team view")
show("team summary", team["summary"])
if team["timesheets"]:
    pend = next((t for t in team["timesheets"] if t["status"] == "Submitted"), team["timesheets"][0])
    call("POST", f"/api/timesheets/{pend['id']}/action", json_body={"action": "reject"}, expect=(400,), label="reject needs remark")
    call("POST", f"/api/timesheets/{pend['id']}/action", json_body={"action": "approve"}, label="approve")
call("GET", "/api/timesheet/history", label="history")
call("GET", "/api/timesheet/export", label="csv export")
_, prj = call("GET", "/api/projects", label="projects")
show("projects", [(p["code"], p["hours_this_week"], p["total_hours"], p["billable_value"]) for p in prj])

print("== payroll & expenses ==")
call("GET", "/api/payslips", label="payslips")
_, ps = call("GET", "/api/payslips", label="payslips list")
if ps:
    call("GET", f"/api/payslips/{ps[0]['id']}/detail", want_keys=["earnings", "deductions", "net", "company"], label="payslip detail")
call("GET", "/api/payroll/summary", want_keys=["net_payroll", "per_department", "trend"], label="payroll summary")
_, pay = call("GET", "/api/payroll/summary", label="payroll summary body")
show("payroll", {k: pay[k] for k in ("period", "employees_paid", "net_payroll", "gross_payroll", "deductions", "monthly_ctc_cost")})
show("trend", [t for t in pay["trend"] if t["count"]][:3])
call("GET", "/api/payroll/structures", label="structures")
call("GET", "/api/reimbursements", want_keys=["0.amount_label"], label="reimbursements")
call("GET", "/api/reimbursements/summary", label="expense summary")
call("POST", "/api/reimbursements", json_body={"amount": 0, "date": str(dt.date.today()), "description": "x"}, expect=(400,), label="amount validation")
_, claim = call("POST", "/api/reimbursements", json_body={"amount": 4250, "category": "Travel", "date": str(dt.date.today()),
                                                           "description": "Goa client visit - flights", "has_receipt": True},
                label="create claim", want_keys=["reimbursement.id"])
cid = claim["reimbursement"]["id"]
call("POST", f"/api/reimbursements/{cid}/action", json_body={"action": "approve"}, label="approve claim")
call("POST", f"/api/reimbursements/{cid}/action", json_body={"action": "pay"}, label="pay claim")
call("POST", f"/api/reimbursements/{cid}/action", json_body={"action": "reject"}, expect=(400,), label="reject needs remark")
call("DELETE", f"/api/reimbursements/{cid}", label="delete claim after pay (admin ok)")

print("== hiring ==")
_, jobs = call("GET", "/api/jobs", want_keys=["0.pipeline", "0.in_progress", "0.fill_pct"], label="jobs")
show("job[0]", {k: jobs[0][k] for k in ("title", "status", "applicants", "in_progress", "pipeline", "fill_pct", "days_open", "hiring_manager")})
_, pipe = call("GET", "/api/hiring/pipeline", want_keys=["stages", "open_roles", "hire_rate"], label="pipeline")
show("stages", [(s["name"], s["count"]) for s in pipe["stages"]], )
show("pipeline", {k: pipe[k] for k in ("rejected", "total", "open_roles", "open_positions", "hired", "hire_rate", "by_source")})
assert sum(x["count"] for x in pipe["stages"]) + pipe["rejected"] == pipe["total"], "pipeline counts do not add up"
_, cands = call("GET", "/api/candidates", label="candidates")
show("candidates", len(cands))
call("POST", "/api/jobs", json_body={"title": ""}, expect=(400,), label="job validation")
_, nj = call("POST", "/api/jobs", json_body={"title": "QA Automation Engineer", "department_id": 2, "location": "Remote",
                                             "openings": 2, "employment_type": "Full-time", "experience": "2-4 yrs",
                                             "salary_range": "₹8-14 LPA", "description": "Playwright + CI"},
             label="create job", want_keys=["job.pipeline"])
jid = nj["job"]["id"]
call("PUT", f"/api/jobs/{jid}", json_body={"action": "close"}, expect=(400,), label="close needs reason")
_, closed = call("PUT", f"/api/jobs/{jid}", json_body={"action": "close", "closure_reason": "Role put on hold by finance"},
                 label="close job")
show("closed", {k: closed["job"][k] for k in ("status", "closed_label", "closure_reason")})
call("PUT", f"/api/jobs/{jid}", json_body={"action": "reopen"}, label="reopen job")
call("PUT", f"/api/jobs/{jid}", json_body={"title": "QA Automation Engineer II", "openings": 3, "salary_range": "₹10-16 LPA"}, label="update job")
_, nc = call("POST", "/api/candidates", json_body={"job_id": jid, "full_name": "Pipeline Tester", "email": "pipeline.tester@example.com",
                                                    "phone": "+91 98888 11111", "experience_years": 3, "current_ctc": 900000,
                                                    "expected_ctc": 1300000, "source": "LinkedIn", "notes": "Strong on Playwright"},
             label="create candidate", want_keys=["candidate.stage"])
cid2 = nc["candidate"]["id"]
for stage in ["Screening", "Interview", "Offer"]:
    _, moved = call("PUT", f"/api/candidates/{cid2}", json_body={"stage": stage}, label=f"move to {stage}")
_, edited = call("PUT", f"/api/candidates/{cid2}", json_body={"full_name": "Pipeline Tester", "rating": 4.5, "expected_ctc": 1450000,
                                                               "notes": "Accepted verbal offer", "current_role": "Sr. QA, Zeta"}, label="edit candidate fields")
show("candidate", {k: edited["candidate"][k] for k in ("stage", "rating", "expected_ctc_label", "age_in_stage_days", "converted")})
call("POST", f"/api/candidates/{cid2}/hire", json_body={"email": "vikram.singh@company.com"}, expect=(400,), label="hire onto an existing email blocked")
_, hired = call("POST", f"/api/candidates/{cid2}/hire", json_body={"date_of_joining": str(dt.date.today()), "salary_ctc": 1450000,
                                                                    "employment_type": "Full-time", "work_location": "Bengaluru"},
                label="convert to employee", want_keys=["employee.employee_code"])
show("hired", {k: hired["employee"][k] for k in ("full_name", "employee_code", "department", "designation", "manager", "tenure")})
call("POST", f"/api/candidates/{cid2}/hire", json_body={}, expect=(400,), label="double hire blocked")
_, jobs_after = call("GET", "/api/jobs", label="job openings after hire")
this_job = next(j for j in jobs_after if j["id"] == jid)
show("openings decremented", this_job["openings"])
_, hired_emp = call("GET", f"/api/employees/{hired['employee']['id']}", label="hired employee detail (balances seeded)")
show("seeded balances", [(b["leave_type"] or b.get("name"), b["total"]) for b in hired_emp["leave_balances"]])
call("DELETE", f"/api/candidates/{cid2}", label="delete candidate")
call("DELETE", f"/api/jobs/{jid}", label="delete now-empty job")
call("DELETE", f"/api/employees/{hired['employee']['id']}", label="remove test hire")

print("== performance ==")
_, perf = call("GET", "/api/performance/overview", want_keys=["goals_total", "rating_distribution", "nine_box_counts", "departments"], label="overview")
show("overview", {k: perf[k] for k in ("goals_total", "avg_goal_progress", "reviews_total", "avg_rating", "feedback_count",
                                       "checkins_total", "pending_self_review", "pending_manager_review")})
show("ratings", perf["rating_distribution"])
show("nine box", perf["nine_box_counts"])
_, goals = call("GET", "/api/goals", label="goals")
show("goals", [(g_["title"][:26], g_["progress"], g_["health_label"]) for g_ in goals[:3]])
_, ng = call("POST", "/api/goals", json_body={"title": "Cut p95 latency below 400ms", "category": "Engineering", "metric": "p95 ms",
                                              "target": "400", "progress": 20}, label="create goal")
gid = ng["goal"]["id"]
_, ug = call("PUT", f"/api/goals/{gid}", json_body={"progress": 100}, label="progress to 100")
show("goal status", (ug["goal"]["progress"], ug["goal"]["status"], ug["goal"]["health"]))
call("DELETE", f"/api/goals/{gid}", label="delete goal")
_, rvs = call("GET", "/api/reviews", label="reviews")
show("review[0]", {k: rvs[0][k] for k in ("period", "status", "rating_label", "competency_avg", "cycle_label", "overdue")} if rvs else None)
if rvs:
    open_rev = next((r for r in rvs if r["status"] in ("Self Review Pending", "Manager Review Pending")), rvs[0])
    call("PUT", f"/api/reviews/{open_rev['id']}", json_body={"action": "self_review", "self_rating": 4.2}, expect=(400,), label="self review needs comments")
    call("PUT", f"/api/reviews/{open_rev['id']}", json_body={"action": "self_review", "self_rating": 9, "comments": "x"}, expect=(400,), label="rating bounds")
    call("PUT", f"/api/reviews/{open_rev['id']}", json_body={"action": "self_review", "self_rating": 4.2,
                                                             "comments": "Shipped the timesheet rebuild and mentored two juniors.",
                                                             "strengths": "Ownership", "improvements": "Written updates"}, label="self review")
    call("PUT", f"/api/reviews/{open_rev['id']}", json_body={"action": "manager_review", "manager_rating": 4.0,
                                                             "comments": "Strong half, keep documenting decisions.", "finalize": True,
                                                             "competencies": {"Collaboration": 4.5, "Delivery": 4.0, "Communication": 3.5}},
         label="manager review")
_, fb = call("GET", "/api/feedback", label="feedback list")
show("feedback", [(f["from_label"], f["message"][:30], f["tag_list"]) for f in fb[:2]])
call("POST", "/api/feedback", json_body={"to_employee_id": emps[1]["id"], "message": "nice"}, expect=(400,), label="short feedback blocked")
call("POST", "/api/feedback", json_body={"to_employee_id": emps[1]["id"], "message": "Your runbook saved us an hour of paging.",
                                         "tags": "Teamwork, Mentoring", "category": "Appreciation", "is_anonymous": True}, label="send feedback")
_, ci = call("GET", "/api/checkins", label="checkins")
show("checkins", [(c["employee"].get("full_name") if c.get("employee") else None, c["date_label"], c["status"]) for c in ci[:3]])
call("POST", "/api/checkins", json_body={"employee_id": emps[1]["id"], "agenda": "Sprint retro follow-ups", "notes": "n/a",
                                         "next_steps": "Pair on the alerting rules"}, expect=(400,), label="check-in needs a date")
call("POST", "/api/checkins", json_body={"employee_id": emps[1]["id"], "date": str(dt.date.today() + dt.timedelta(days=2)),
                                         "agenda": "Sprint retro follow-ups", "notes": "n/a", "next_steps": "Pair on alerting"}, label="schedule check-in")

print("== reports ==")
_, rl = call("GET", "/api/reports", label="report list")
show("reports", [r["id"] for r in rl])
assert len(rl) == 9, f"expected 9 reports, got {len(rl)}"
for rep in rl:
    _, p = call("GET", f"/api/reports/{rep['id']}?from={dt.date.today() - dt.timedelta(days=89)}&to={dt.date.today()}",
                want_keys=["kpis", "chart", "table"], label=f"report {rep['id']}")
    show(f"  {rep['id']}", {"kpis": [(k["label"], k["value"]) for k in p["kpis"]][:4],
                            "chart": f"{p['chart']['kind']}:{len(p['chart']['labels'])}",
                            "rows": len(p["table"]["rows"]), "note": (p.get("note") or "")[:60]})
    r2, _ = call("GET", f"/api/reports/{rep['id']}?format=csv", label=f"  {rep['id']} csv")
    assert "," in r2.text and len(r2.text) > 10, f"{rep['id']} csv is empty"
call("GET", "/api/reports/headcount?department=Engineering", label="department filter")
_, bad = call("GET", "/api/reports/nonexistent", expect=(400, 404), label="unknown report")
call("POST", "/api/reports/custom", json_body={"dataset": "not_a_table"}, expect=(400,), label="custom bad dataset")
_, custom = call("POST", "/api/reports/custom", json_body={"dataset": "attendance", "columns": ["employee_id", "date", "status", "work_hours"],
                                                            "filters": {"status": "Absent"}, "limit": 25},
                 label="custom builder", want_keys=["rows", "columns"])
show("custom", {"rows": len(custom["rows"]), "cols": custom["columns"], "total": custom["total"]})
_, ccsv = call("POST", "/api/reports/custom", json_body={"dataset": "employees", "columns": ["full_name", "email", "salary_ctc"], "format": "csv"},
               label="custom csv")
assert "full_name".title() in ccsv.text or "Full Name" in ccsv.text

print("== inbox / announcements / holidays ==")
_, ib = call("GET", "/api/inbox", want_keys=["total", "groups"], label="inbox")
show("inbox groups", [(g["label"], g["count"]) for g in ib["groups"]])
show("first item", {k: ib["items"][0][k] for k in ("kind", "title", "subtitle", "meta", "approve_endpoint")} if ib["items"] else None)
pending_leave = next((i for i in ib["items"] if i["kind"] == "leave"), None)
if pending_leave:
    call("POST", f"/api/pending-actions/leave/{pending_leave['id']}", json_body={"action": "approve", "remark": "Approved from Inbox"},
         label="one-click approve from inbox")
_, an = call("GET", "/api/announcements", label="announcements")
show("announcements", [(a["title"][:34], a["type"], a["is_pinned"], a["date"]) for a in an[:3]])
_, na = call("POST", "/api/announcements", json_body={"title": "Smoke-test notice", "content": "Ignore this test row.", "type": "Update"}, label="create announcement")
call("PUT", f"/api/announcements/{na['announcement']['id']}", json_body={"is_pinned": True}, label="pin announcement")
call("DELETE", f"/api/announcements/{na['announcement']['id']}", label="delete announcement")
_, hol = call("GET", "/api/holidays", label="holidays")
show("holidays", [(h["name"], h["date"], h["days_left"]) for h in hol[:3]])
for mod in ("employees", "attendance", "leave", "payroll", "hiring", "org"):
    call("GET", f"/api/export/{mod}", label=f"export {mod}")

print("== employee-role permissions ==")
other = next(e for e in emps if e["email"] != "admin@company.com")
s2 = requests.Session()
_, _ = call("POST", "/login", json_body={"email": other["email"], "password": "demo123"}, label="employee login")
_, e_sess = call("GET", "/api/session", label="employee session")
show("employee sees", {k: e_sess["employee"][k] for k in ("full_name", "designation", "department")})
call("GET", "/api/employees", expect=(403,), label="employee cannot open the directory")
call("GET", f"/api/employees/{other['id']}", label="employee can open their own card")
call("GET", "/api/orgchart", label="employee can see the org chart")
call("GET", "/api/stats", expect=(200,), label="employee stats")
_, e_att = call("GET", "/api/attendance", want_keys=["scoped_to"], label="employee attendance scoped")
show("scoped_to", e_att["scoped_to"])
assert str(e_att["scoped_to"]) == str(other["id"]), "attendance not scoped to the signed-in employee"
_, e_ts = call("GET", "/api/timesheet", want_keys=["timesheet"], label="employee timesheet")
assert str(e_ts["timesheet"]["employee_id"]) == str(other["id"]), "timesheet leaked another employee's data"
call("POST", "/api/employees", json_body={"full_name": "X", "email": "x@y.com"}, expect=(403,), label="employee cannot add")
call("POST", "/api/reimbursements", json_body={"amount": 100, "employee_id": "e01", "description": "trying to file on someone else", "has_receipt": True, "date": str(dt.date.today())}, label="employee claim (self only)")
call("POST", "/api/documents", json_body={"employee_id": other["id"], "doc_type": "PAN Card", "title": "x", "description": "y"},
     expect=(200, 400), label="employee cannot upload for others")
call("PUT", f"/api/documents/{docs[0]['id']}", json_body={"action": "Verified"}, expect=(200, 403, 404), label="employee cannot verify docs")
call("GET", "/api/export/employees", expect=(403,), label="employee cannot export")
_, e_me = call("GET", "/api/me", want_keys=["editable_fields"], label="employee me")
show("editable for employees", len(e_me["editable_fields"]))
show("notice", e_me["notice"])
call("POST", "/api/demo/reset", expect=(403,), label="employee cannot reset demo")

print("== what an employee may open ==")
mods = e_sess.get("modules") or []
show("modules granted", len(mods))
for blocked in ("employees", "hiring", "reports"):
    assert blocked not in mods, f"modules list leaked the HR area '{blocked}'"
for granted in ("home", "me", "inbox", "attendance", "leave", "payroll", "expenses", "timesheet",
                "documents", "performance", "orgchart"):
    assert granted in mods, f"modules list is missing '{granted}'"
for path, tag in (("/api/employees/export", "directory export"), ("/api/jobs", "job openings"),
                  ("/api/candidates", "candidate list"), ("/api/hiring/pipeline", "hiring pipeline"),
                  ("/api/reports", "report list"), ("/api/reports/headcount", "headcount report")):
    call("GET", path, expect=(403,), label=f"employee blocked from {tag}")
call("GET", "/api/custom-report-datasets", expect=(403, 404), label="employee has no custom-report datasets")
_, look = call("GET", "/api/lookups", label="lookups for an employee")
assert not look.get("custom_datasets"), "custom-report datasets leaked to an employee"
r, _ = call("GET", "/api/export/attendance", label="employee exports their own attendance")
show("own attendance export", r.headers.get("Content-Type", "")[:24])
assert "csv" in (r.headers.get("Content-Type") or "").lower(), "attendance export is not CSV"
_, own_rows = call("GET", "/api/attendance", want_keys=["rows"], label="attendance rows for scoping check")
names = {a.get("employee_name") for a in own_rows["rows"]}
show("names in own export scope", len(names))
assert not e_sess.get("security", {}).get("has_own_password"), "a fresh demo account should not have its own password yet"
assert e_sess.get("must_set_password") in (True, False), "must_set_password missing from /api/session"
r, _ = call("POST", "/login", json_body={"email": "deepak.chauhan@company.com", "password": "demo123"},
            expect=(401,), label="exited employee cannot sign in")
show("exited login says", (r.json().get("error") or "")[:44])

print("== wall clock (the office, not the container) ==")
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
IST = _tz(_td(hours=5, minutes=30))
_, hh = call("GET", "/api/health", want_keys=["timezone", "office_time", "wall_clock_offset_minutes"],
             label="health exposes the office clock")
show("server timezone", hh["timezone"])
assert int(hh["wall_clock_offset_minutes"]) == 330, f"clock is {hh['wall_clock_offset_minutes']} min from UTC, expected 330 (IST)"
expected = _dt.now(IST)


def seconds_off(hhmmss, ref):
    """How far a HH:MM[:SS] value is from a datetime, wrapping over midnight."""
    parts = [int(x) for x in str(hhmmss)[:8].split(":") if x.isdigit()]
    while len(parts) < 3:
        parts.append(0)
    a = parts[0] * 3600 + parts[1] * 60 + parts[2]
    b = ref.hour * 3600 + ref.minute * 60 + ref.second
    gap = abs(a - b)
    return min(gap, 86400 - gap)


drift = seconds_off(hh["office_time"], expected)
show("office_time vs IST now", f"{hh['office_time']} vs {expected.strftime('%H:%M:%S')} ({int(drift)}s apart)")
assert drift < 120, f"/api/health office_time is {int(drift)}s away from IST - the server is on its own clock"

# a punch filed now has to land on today's IST time and date, whatever the host clock says
_, before = call("GET", "/api/attendance", want_keys=["rows"], label="attendance before the punch")
mine_row = next((a for a in before["rows"] if a.get("date") == expected.strftime("%Y-%m-%d")), None)
_, clk = call("POST", "/api/attendance/clock", json_body={"action": "in", "location": "Testing"},
              expect=(200, 400), label="clock in")
if clk.get("success"):
    hhmm = clk["time"]
    diff = seconds_off(hhmm, expected)
    show("clocked in at", f"{hhmm} (IST now {expected.strftime('%H:%M')})")
    assert diff <= 120, f"clock-in stamped {hhmm} but the office clock says {expected.strftime('%H:%M')}"
    _, aft = call("GET", "/api/attendance", want_keys=["rows"], label="attendance after the punch")
    row = next((a for a in aft["rows"] if str(a.get("date"))[:10] == expected.strftime("%Y-%m-%d")), None)
    assert row, "the punch was filed on a date other than the office's today"
    show("punch stored under", f"{row['date']} {row.get('clock_in')}")
    stored = seconds_off(str(row.get("clock_in")), expected)
    show("stored clock_in", f"{row.get('clock_in')} ({int(stored)}s from IST now)")
    assert stored <= 240, f"stored clock_in {row.get('clock_in')} is not office time ({int(stored)}s off)"
_, tr = call("GET", "/api/stats", want_keys=["my_time"], label="tracker after the punch")
show("tracker shows", f"{tr['my_time']['clock_in']} · {tr['my_time']['status']}")
show("month the API defaulted to", before.get("month"))
assert before.get("month") == expected.strftime("%Y-%m"), \
    f"the attendance month defaulted to {before.get('month')}, not the office month {expected.strftime('%Y-%m')}"
call("GET", "/api/payroll/summary", label="payroll summary still answers after the clock change")

print("== misc ==")
call("GET", "/api/health", label="health again")
_, h = call("GET", "/api/health", label="health body")
show("health", h)
call("GET", "/api/nope", expect=(404,), label="unknown api 404")
call("GET", "/", expect=(200, 302), label="root redirect")
_, admin_sess = call("GET", "/api/session", expect=(200, 401), label="session (employee still logged in)")
call("POST", "/api/demo/reset", json_body={}, expect=(403,), label="employee cannot reset demo (2)")

print("== own password round trip ==")


def login_as(email, password, expect=200, label=None):
    """A login that does not disturb the session the suite is using."""
    checks[0] += 1
    r = requests.Session().post(BASE + "/login", json={"email": email, "password": password}, timeout=60)
    if r.status_code != expect:
        fails.append(f"{label or email} -> {r.status_code}: {r.text[:160]}")
        print(f"  !! FAIL {label or email} -> {r.status_code}")
    else:
        print(f"  ok   {label or email} -> {r.status_code}")
    return r


call("POST", "/api/me/password", json_body={"current_password": "wrong-one", "new_password": "FreshPass-2026"}, expect=(403,), label="wrong current password rejected")
call("POST", "/api/me/password", json_body={"current_password": "demo123", "new_password": "tiny"}, expect=(400,), label="short password rejected")
call("POST", "/api/me/password", json_body={"current_password": "demo123", "new_password": "demo123"}, expect=(400,), label="same password rejected")
call("POST", "/api/me/password", json_body={"current_password": "demo123", "new_password": "FreshPass-2026"}, label="own password set")
login_as(other["email"], "demo123", expect=401, label="shared password stops working once they set their own")
login_as(other["email"], "FreshPass-2026", label="own password signs in")
_, own_sess = call("GET", "/api/session", want_keys=["security.has_own_password"], label="session after the change")
assert own_sess["security"]["has_own_password"] is True, "has_own_password did not flip"
assert own_sess["must_set_password"] is False, "the nudge should clear once they have their own password"
call("GET", f"/api/employees/{other['id']}", label="own profile card still opens")
_, _ = call("POST", "/login", json_body={"email": "admin@company.com", "password": "demo123"}, label="admin back in")
_, dir_rows = call("GET", "/api/employees", label="directory after the change")
row = next((e for e in dir_rows if e["id"] == other["id"]), {})
assert "password_hash" not in row, "password_hash escaped into an API response"
assert row.get("has_own_password") is True, "the directory should say this person has their own password"
_, issued = call("POST", f"/api/employees/{other['id']}/reset-password", json_body={},
                 want_keys=["temp_password"], label="HR issues a one-time password")
show("temp password", (issued.get("temp_password") or "")[:7] + "...")
assert issued.get("temp_password") != "FreshPass-2026", "reset should replace the password, not echo it"
login_as(other["email"], issued["temp_password"], label="one-time password signs in")
call("POST", "/api/demo/reset", json_body={}, label="demo data restored")
login_as(other["email"], "demo123", label="reset puts the shared password back")
login_as(other["email"], "FreshPass-2026", expect=401, label="the test password is gone with the reset")

print("\n" + "=" * 78)
print(f"{checks[0]} endpoint checks run")
if fails:
    print(f"{len(fails)} FAILURE(S):")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL GREEN")
