#!/usr/bin/env python3
"""Generate supabase_schema.sql (fresh install) and supabase_migrate.sql (upgrade).

The schema is *derived*, not hand-written: the column list comes from SUPA_COLUMNS in app.py
(the whitelist the app actually writes), the types from the rules below, and the seed rows from
mock_data.py, so the demo data and the SQL can never drift apart.

The generator also validates the result against the seeded demo data:
  * every column the app can write must exist in the schema
  * every UNIQUE constraint emitted here must hold on the demo data
  * reference-table seeds must be consistent with the same rows the demo uses

Usage:  python tools/gen_schema.py
"""
from __future__ import annotations

import ast
import re
import datetime as dt
import os
import sys

try:
    from pglast import parse_sql
except ImportError:                                        # grammar check is optional
    parse_sql = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)

import mock_data  # noqa: E402

# ---------------------------------------------------------------- SUPA_COLUMNS
src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
tree = ast.parse(src)
SUPA = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SUPA_COLUMNS":
        for key, value in zip(node.value.keys, node.value.values):
            SUPA[key.value] = {e.value for e in value.elts}
if not SUPA:
    raise SystemExit("could not read SUPA_COLUMNS from app.py")

LEGACY_EMPLOYEE_COLUMNS = {"designation", "department", "manager", "avatar"}

# --------------------------------------------------------------- type rules
# columns that reference another table -> (referenced table, delete rule)
FK = {
    "department_id": ("departments", "set null"),
    "designation_id": ("designations", "set null"),
    "shift_id": ("shifts", "set null"),
    "leave_type_id": ("leave_types", "cascade"),
    "job_id": ("jobs", "cascade"),
    "project_id": ("projects", "set null"),
    "timesheet_id": ("timesheets", "cascade"),
    "fulfilled_document_id": ("documents", "set null"),
    "converted_employee_id": ("employees", "set null"),
    "head_id": ("employees", "set null"),
}
EMPLOYEE_FK = ("employees", "cascade")
EMPLOYEE_FK_SET_NULL = ("employees", "set null")
# A reference to a person in an *actor* role - who manages, reviews, approves or owns the row.
# These must never take the row with them: `employees.manager_id` used to be ON DELETE CASCADE,
# so deleting one employee in Supabase mode also deleted every employee reporting to that person,
# plus those people's attendance, leave and payroll rows. `employee_id` (the subject of the row)
# keeps CASCADE, because those records belong to the person being removed.
ACTOR_EMPLOYEE_COLS = {"manager_id", "reviewer_id", "approver_id", "owner_id", "hiring_manager_id",
                       "approved_by", "from_employee_id"}
TIME_COLS = {"clock_in", "clock_out", "start_time", "end_time", "clock_in_correction", "clock_out_correction"}
DATE_COLS = {"date", "day", "start_date", "end_date", "due_date", "valid_from", "valid_till", "exit_date",
             "date_of_birth", "date_of_joining", "effective_from", "week_starting", "cycle_start", "cycle_end",
             "paid_on"}
INT_COLS = {"year", "month", "total", "used", "pending", "yearly_quota", "progress", "level", "openings",
            "experience_years", "grace_minutes", "break_minutes", "file_size", "days"}
NUM_COLS = {"work_hours", "hours", "total_hours", "billable_hours", "rating", "self_rating", "manager_rating",
            "final_rating", "days", "lop_days", "payable_days", "working_days"}
BOOL_COLS = {"is_paid", "requires_approval", "is_anonymous", "is_pinned", "half_day", "billable", "is_late"}
JSONB_COLS = {"competencies", "allowances"}
BIG_COLS = {"address", "description", "content", "message", "notes", "reason", "comments", "strengths",
            "improvements", "agenda", "next_steps", "reviewer_remark", "admin_remark", "closure_reason",
            "purpose", "task", "salary_range", "experience", "target", "metric", "regulatization_placeholder"}
NOT_NULL = {
    "departments": ["name"], "designations": ["title"], "employees": ["full_name", "email", "employee_code"],
    "attendance": ["date", "status"], "attendance_regularizations": ["date", "reason", "status"],
    "leave_types": ["name", "code"], "leave_requests": ["start_date", "status"],
    "holidays": ["name", "date"], "payslips": ["month", "year", "net_pay"],
    "documents": ["title", "doc_type", "purpose"], "document_requests": ["doc_type", "reason", "status"],
    "jobs": ["title", "status"], "candidates": ["full_name", "stage"], "goals": ["title", "progress"],
    "performance_reviews": ["period", "status"], "feedbacks": ["message"], "checkins": ["date"],
    "projects": ["code", "name"], "timesheets": ["week_starting", "status"],
    "timesheet_entries": ["date", "hours"], "announcements": ["title", "content"],
    "reimbursements": ["amount", "date", "status"], "shifts": ["name", "start_time", "end_time"],
    "leave_balances": ["year", "total"], "payroll_structures": ["ctc"],
}
UNIQUE = {
    "departments": [["name"]],
    "designations": [["title", "department_id"]],
    "employees": [["email"], ["employee_code"]],
    "leave_types": [["code"]],
    "holidays": [["name", "date"]],
    "attendance": [["employee_id", "date"]],
    "leave_balances": [["employee_id", "leave_type_id", "year"]],
    "timesheets": [["employee_id", "week_starting"]],
    "projects": [["code"]],
    "shifts": [["name"]],
    "payroll_structures": [["employee_id", "effective_from"]],
    "payslips": [["employee_id", "month", "year"]],
}
INDEX = {
    "attendance": [["employee_id"], ["date"], ["status"]],
    "attendance_regularizations": [["employee_id", "status"]],
    "leave_requests": [["employee_id", "status"], ["start_date"]],
    "leave_balances": [["employee_id"]],
    "documents": [["employee_id", "status"], ["doc_type"], ["valid_till"]],
    "document_requests": [["employee_id", "status"]],
    "payslips": [["year", "month"]],
    "reimbursements": [["employee_id", "status"]],
    "candidates": [["job_id", "stage"], ["stage"]],
    "jobs": [["status"]],
    "goals": [["employee_id", "status"]],
    "performance_reviews": [["employee_id"], ["reviewer_id", "status"]],
    "feedbacks": [["to_employee_id"]],
    "checkins": [["employee_id", "date"]],
    "timesheet_entries": [["timesheet_id"], ["employee_id", "date"], ["project_id"]],
    "timesheets": [["employee_id", "week_starting"], ["status"]],
    "employees": [["department_id"], ["manager_id"], ["status"]],
    "announcements": [["date"]],
    "holidays": [["date"]],
}
TABLE_COMMENTS = {
    "departments": "Org structure - departments and their head.",
    "designations": "Job titles, optionally scoped to a department.",
    "employees": "Core people record. `department`/`designation`/`manager` are optional display copies.",
    "shifts": "Working hours + grace period used for lateness.",
    "attendance": "One row per employee per day. clock_in / clock_out are TIME values (the date lives in `date`).",
    "attendance_regularizations": "Employee requests to fix a punch; `reason` is mandatory.",
    "leave_types": "Configurable quotas (Casual, Sick, Earned, WFH, Optional Holiday).",
    "leave_balances": "Per employee, per type, per year quota. `pending` is recomputed from requests on read.",
    "leave_requests": "Applications and their approval trail.",
    "holidays": "Company calendar; blocks leave bookings and attendance expectations.",
    "payroll_structures": "Monthly components per employee, effective from a date.",
    "payslips": "One row per employee per month; the PDF lives in Storage (`payslip_url`).",
    "reimbursements": "Expense claims with receipt links.",
    "jobs": "Open requisitions.",
    "candidates": "Pipeline rows; `converted_employee_id` links a hire back to `employees`.",
    "goals": "OKR-style objectives with a progress percentage.",
    "performance_reviews": "Self + manager review per cycle; competencies are a jsonb score card.",
    "feedbacks": "Peer-to-peer kudos. `tags` is a comma separated list; `is_anonymous` hides the sender.",
    "checkins": "1:1 notes between a manager and an employee.",
    "announcements": "Company-wide notices shown on Home.",
    "documents": "Employee files: why they were collected, who uploaded them and who may see them.",
    "document_requests": "HR chasing a document from an employee, with a due date.",
    "projects": "Where timesheets are booked, plus the billing rate used for utilisation value.",
    "timesheets": "Weekly roll-up (Draft -> Submitted -> Approved/Rejected).",
    "timesheet_entries": "The individual day/project rows behind a timesheet.",
}


# Postgres refuses these as bare identifiers (SQL grammar), so the DDL quotes them.
RESERVED = {
    "all", "analyse", "analyze", "and", "any", "array", "as", "asc", "authorization", "binary", "both", "case",
    "cast", "check", "collate", "collation", "column", "concurrently", "constant", "create", "cross", "current_catalog",
    "current_date", "current_role", "current_schema", "current_time", "current_timestamp", "current_user", "default",
    "deferrable", "desc", "distinct", "do", "else", "end", "except", "false", "fetch", "filter", "for", "foreign",
    "freeze", "from", "full", "grant", "group", "having", "ilike", "in", "initially", "inner", "intersect", "into",
    "is", "isnull", "join", "lateral", "leading", "left", "like", "limit", "localtime", "localtimestamp", "natural",
    "not", "notnull", "null", "offset", "on", "only", "or", "order", "outer", "overlaps", "placing", "primary",
    "references", "returning", "right", "select", "session_user", "similar", "some", "symmetric", "table", "tablesample",
    "then", "to", "trailing", "true", "union", "unique", "user", "using", "variadic", "verbose", "when", "where", "window", "with",
}


def ident(col: str) -> str:
    return f'"{col}"' if col in RESERVED else col


def sql_type(table: str, col: str) -> str:
    """The bare Postgres type for a column.

    Nullability and defaults are NOT decided here - they live in column_parts(), which is the
    only place that composes a column definition. When both functions decorated a column, a
    boolean came out as `is_paid boolean not null default false default true` and Postgres
    answered 42601 "multiple default values specified for column".
    """
    if col == "id":
        return "uuid"
    if col in ("created_at", "updated_at"):
        return "timestamptz"
    if col in JSONB_COLS:
        return "jsonb"
    if col == "tags":
        return "text"
    if col in TIME_COLS:
        return "time"
    if col in DATE_COLS:
        return "date"
    if col.endswith("_at"):
        return "timestamptz"
    if col in ("rating", "self_rating", "manager_rating", "final_rating"):
        return "numeric(4,2)"
    if col.endswith(("_ctc", "_amount", "amount", "ctc", "basic", "hra", "special_allowance", "pf", "esi",
                     "professional_tax", "tds", "gross_earnings", "total_deductions", "net_pay", "billing_rate",
                     "bonus", "deductions", "employer_pf")):
        return "numeric(14,2)"
    if col in NUM_COLS:
        return "numeric(8,2)"
    if col in INT_COLS:
        return "integer"
    if col in BOOL_COLS:
        return "boolean"
    if col in BIG_COLS or col.endswith(("_url", "_remark", "_reason", "_notes", "description", "content")):
        return "text"
    if fk_for(table, col):
        return "uuid"
    return "text"


DEFAULTS = {
    ("employees", "status"): "'Active'", ("employees", "employment_type"): "'Full-time'",
    ("employees", "work_location"): "'Bangalore'", ("employees", "salary_ctc"): "0",
    ("employees", "nationality"): "'Indian'",
    ("attendance", "status"): "'Present'", ("attendance", "regularization_status"): "'None'",
    ("attendance", "break_minutes"): "45",
    ("leave_requests", "status"): "'Pending'", ("leave_requests", "days"): "1",
    ("leave_balances", "used"): "0", ("leave_balances", "pending"): "0",
    ("attendance_regularizations", "status"): "'Pending'",
    ("documents", "status"): "'Pending'", ("documents", "visibility"): "'Self + HR'",
    ("document_requests", "status"): "'Pending'",
    ("reimbursements", "status"): "'Pending'", ("payslips", "status"): "'Draft'",
    ("jobs", "status"): "'Open'", ("jobs", "openings"): "1",
    ("candidates", "stage"): "'Applied'", ("candidates", "rating"): "0",
    ("goals", "progress"): "0", ("goals", "status"): "'On Track'",
    ("performance_reviews", "status"): "'Self Review Pending'",
    ("checkins", "status"): "'Scheduled'", ("announcements", "type"): "'Update'",
    ("announcements", "is_pinned"): "false", ("shifts", "grace_minutes"): "15",
    ("leave_types", "is_paid"): "true", ("leave_types", "requires_approval"): "true",
    ("projects", "status"): "'Active'", ("timesheets", "status"): "'Draft'",
    ("timesheets", "total_hours"): "0", ("timesheets", "billable_hours"): "0",
    ("timesheet_entries", "billable"): "false", ("designations", "level"): "1",
    ("payroll_structures", "pf"): "0", ("payroll_structures", "esi"): "0",
    ("payroll_structures", "professional_tax"): "0", ("payroll_structures", "tds"): "0",
}


def fk_for(table: str, col: str):
    """(target_table, on_delete) for a reference column, or None."""
    if col == "id":
        return None
    if col in FK:
        return FK[col]
    if col.endswith("_id") or col in {"approved_by"}:
        return EMPLOYEE_FK_SET_NULL if col in ACTOR_EMPLOYEE_COLS else EMPLOYEE_FK
    return None


def column_parts(table: str, col: str):
    """type / not-null / default for one column, decided exactly once."""
    if col == "id":
        return {"type": "uuid", "not_null": False, "default": "gen_random_uuid()", "primary_key": True}
    if col in ("created_at", "updated_at"):
        return {"type": "timestamptz", "not_null": True, "default": "now()"}
    if col in JSONB_COLS:
        return {"type": "jsonb", "not_null": True, "default": "'{}'::jsonb"}
    if col in BOOL_COLS:
        # the app treats these as flags, so they are non-null with an explicit fallback
        return {"type": "boolean", "not_null": True, "default": DEFAULTS.get((table, col), "false")}
    return {"type": sql_type(table, col),
            "not_null": col in NOT_NULL.get(table, []),
            "default": DEFAULTS.get((table, col))}


def column_def(table: str, col: str) -> str:
    """One `create table` line: type, not-null and a default where the app relies on one.

    Foreign keys are deliberately NOT declared here. A table that inlines
    `references employees(id)` cannot be created before `employees` exists, and the
    table order cannot satisfy every cycle (departments.head_id <-> employees.department_id),
    so Postgres answered with `42P01 relation "employees" does not exist`. They are added
    in their own section once every table is present.
    """
    p = column_parts(table, col)
    out = f"  {ident(col)} {p['type']}"
    if p.get("primary_key"):
        out += " primary key"
    elif p["not_null"]:
        out += " not null"
    if p["default"]:
        out += f" default {p['default']}"
    return out


def columns_for(table: str):
    cols = ["id", "created_at", "updated_at"] + sorted(SUPA[table])
    seen, ordered = set(), []
    for c in cols:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    if table == "employees":                       # optional display copies (older deployments keep them)
        for c in sorted(LEGACY_EMPLOYEE_COLUMNS):
            if c not in seen:
                ordered.append(c)
    return ordered


# ------------------------------------------------------------------- seed data
db = mock_data.build_mock_db()


def lit(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


SEED_TABLES = ["departments", "leave_types", "shifts", "holidays", "projects", "designations"]


SET_UPDATED_AT = """create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;"""


def seed_sql():
    """Reference data, in `do $$ ... $$` blocks that only insert while the table is empty.

    A guard per table (instead of ON CONFLICT) because a natural unique key is not
    guaranteed for every seed table, and because re-running the file must not create
    duplicate departments, shifts or holidays.
    """
    lines = []
    nat_key = {"departments": "name", "leave_types": "code", "shifts": "name", "projects": "code",
               "holidays": "name", "designations": None}
    for table in SEED_TABLES:
        rows = db.get(table, [])
        if not rows:
            continue
        cols = [c for c in columns_for(table) if c in rows[0] or c in SUPA[table]]
        cols = [c for c in cols if c not in ("id", "created_at", "updated_at")]
        lines.append(f"-- {table} ({len(rows)} rows) - inserted only while the table is empty")
        body = []
        for r in rows:
            vals = {}
            for c in cols:
                v = r.get(c)
                if c.endswith("_id") and v:
                    ref_table = FK.get(c, EMPLOYEE_FK)[0]
                    if ref_table == "employees":
                        continue                                    # demo ids do not survive into SQL
                    key = nat_key.get(ref_table)
                    ref = next((x for x in db.get(ref_table, []) if str(x.get("id")) == str(v)), None)
                    if not key or not ref:
                        continue
                    vals[c] = f"(select id from {ref_table} where {key} = {lit(ref[key])} limit 1)"
                    continue
                if v is None:
                    continue                                        # nullable, or covered by a default
                vals[c] = lit(v)
            if not vals:
                continue
            cols_sql = ", ".join(ident(c) for c in vals)            # a dict: a column can never repeat
            vals_sql = ", ".join(str(v) for v in vals.values())
            body.append(f"  insert into {table} ({cols_sql}) values ({vals_sql});")
        if not body:
            continue
        lines.append("do $$ begin")
        lines.append(f"  if exists (select 1 from {table} limit 1) then return; end if;")
        lines.extend(body)
        lines.append("end $$;")
        lines.append("")
    return lines


# ------------------------------------------------------------------ emit files
def lint_sql(name: str, sql: str):
    """Static dependency check for the generated DDL.

    Every relation a statement touches must already be created above it, and no
    create-table / add-column line may inline a `references` clause. This is the
    class of bug that makes Supabase answer `relation "employees" does not exist`.
    """
    created, problems, in_create = set(), [], False
    for raw in sql.split("\n"):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        m = re.match(r"create table (?:if not exists )?([a-z_]+) \(", line)
        if m:
            if m.group(1) in created and "if not exists" not in line:
                problems.append(f"re-creates {m.group(1)} without IF NOT EXISTS")
            created.add(m.group(1))
            in_create = not line.endswith(");")
            continue
        if in_create or "add column if not exists" in line:
            for label, pat in (("default values", r"\bdefault\b"), ("not-null clauses", r"\bnot null\b")):
                hits = re.findall(pat, line)
                if len(hits) > 1:
                    problems.append(f"{line[:40]}: {len(hits)} {label} on one column")
        if in_create:
            if re.search(r"\breferences\b", line):
                problems.append(f"create table body still declares an inline reference: {line[:70]}")
            if line.startswith(");") or line.endswith(");"):
                in_create = False
            continue
        if "execute format(" in line:
            continue                                        # dynamic SQL inside the RLS DO block
        m_ins = re.match(r"insert into ([a-z_]+) \(([^)]*)\)", line)
        if m_ins:
            listed = [c.strip() for c in m_ins.group(2).split(",")]
            if len(set(listed)) != len(listed):
                dupes = sorted({c for c in listed if listed.count(c) > 1})
                problems.append(f"{line[:60]}: column(s) {dupes} specified more than once")
        for pat in (r"alter table (?:if exists )?([a-z_]+)",
                    r"references ([a-z_]+)\s*\(",
                    r"create (?:unique )?index (?:if not exists )?[a-z0-9_]+ on ([a-z_]+) \(",
                    r"comment on table ([a-z_]+)",
                    r"insert into ([a-z_]+)",
                    r"^update ([a-z_]+) ",
                    r"delete from ([a-z_]+)"):
            for t in re.findall(pat, line):
                if t in ("public", "if", "table"):
                    continue
                if t not in created:
                    problems.append(f"uses {t!r} before it is created: {line[:78]}")
    for m in re.finditer(r"foreign key \((\w+)\) references employees \(id\) on delete cascade", sql):
        if m.group(1) in ACTOR_EMPLOYEE_COLS:
            problems.append(f"{m.group(1)} is an actor reference and may not cascade to employees")
    if "create trigger" in sql:
        if "create or replace function set_updated_at" not in sql.split("create trigger")[0]:
            problems.append("creates a trigger before set_updated_at() is defined")
    if "add column if not exists" in sql:
        for raw in sql.split("\n"):
            line = raw.strip()
            if "add column if not exists" in line and "not null" in line and " default " not in line:
                problems.append(f"adds a NOT NULL column with no default (aborts on a populated table): {line[:78]}")
    return [f"{name}: {p}" for p in problems]


def written(name):
    return open(os.path.join(ROOT, name), encoding="utf-8").read()


def main():
    stamp = dt.date.today().isoformat()
    order = [t for t in ["departments", "designations", "employees", "shifts", "attendance",
                         "attendance_regularizations", "leave_types", "leave_balances", "leave_requests",
                         "holidays", "payroll_structures", "payslips", "reimbursements", "jobs", "candidates",
                         "projects", "timesheets", "timesheet_entries", "goals", "performance_reviews",
                         "feedbacks", "checkins", "announcements", "documents", "document_requests"] if t in SUPA]
    missing_tables = sorted(set(SUPA) - set(order))
    if missing_tables:
        raise SystemExit(f"SUPA_COLUMNS tables not in the generator order: {missing_tables}")

    fresh, migrate, checks = [], [], []
    fk_stmts = []
    fresh.append("-- Ekkaa HRMS - Supabase / Postgres schema")
    fresh.append("-- Generated by tools/gen_schema.py - do not edit by hand, change app.py's SUPA_COLUMNS instead.")
    fresh.append(f"-- Generated {stamp}   ·   demo data version {mock_data.MOCK_VERSION}")
    fresh.append("-- Run in the Supabase SQL editor (or `psql $DATABASE_URL -f supabase_schema.sql`).")
    fresh.append("")
    fresh.append('create extension if not exists "pgcrypto";')
    fresh.append("")
    fresh.append(SET_UPDATED_AT)

    for table in order:
        cols = columns_for(table)
        fresh.append(f"-- ---------------------------------------------------------------- {table}")
        refs = [(c, fk_for(table, c)) for c in cols]
        refs = [(c, t) for c, t in refs if t]
        for c, (target, action) in refs:
            name = f"{table}_{c}_fkey"
            deltype = {"cascade": "c", "set null": "s", "set default": "d", "restrict": "r"}[action]
            guard = (f"select 1 from pg_constraint c join pg_class r on r.oid = c.conrelid\n"
                     f"                 where r.relname = '{table}' and c.conname = '{name}'")
            fk_stmts.append(
                "do $$ begin\n"
                f"  if exists ({guard} and c.confdeltype <> '{deltype}') then\n"
                f"    execute 'alter table {table} drop constraint {name}';   -- wrong ON DELETE, rebuild it\n"
                "  end if;\n"
                f"  if not exists ({guard}) then\n"
                "    begin\n"
                f"      alter table {table} add constraint {name}\n"
                f"        foreign key ({ident(c)}) references {target} (id) on delete {action};\n"
                "    exception when foreign_key_violation then\n"
                f"      raise notice '{table}.{c} has rows that do not match {target}(id) - the foreign key"
                " was not created; clean the orphan ids and run this file again';\n"
                f"      raise warning '{table}.{c}: foreign key skipped because existing rows violate it';\n"
                "    end;\n"
                "  end if;\n"
                "end $$;")
        if TABLE_COMMENTS.get(table):
            fresh.append(f"-- {TABLE_COMMENTS[table]}")
        fresh.append(f"create table if not exists {table} (")
        body = [column_def(table, c) for c in cols]
        for parts in UNIQUE.get(table, []):
            fresh_cols = [c for c in parts if c in cols]
            if len(fresh_cols) == len(parts):
                body.append(f"  unique ({', '.join(ident(p) for p in parts)})")
        fresh.append(",\n".join(body))
        fresh.append(");")
        fresh.append("")
        if TABLE_COMMENTS.get(table):
            checks.append(f"comment on table {table} is '{TABLE_COMMENTS[table].replace(chr(39), chr(39)*2)}';")
        checks.append(f"drop trigger if exists {table}_updated_at on {table};")
        checks.append(f"create trigger {table}_updated_at before update on {table} for each row execute function set_updated_at();")
        for idx_cols in INDEX.get(table, []):
            if all(c in cols for c in idx_cols):
                name = f"{table}_{'_'.join(idx_cols)}_idx"
                fresh.append(f"create index if not exists {name} on {table} ({', '.join(idx_cols)});")
                checks.append(f"create index if not exists {name} on {table} ({', '.join(idx_cols)});")
        for parts in UNIQUE.get(table, []):
            if all(c in cols for c in parts):
                fresh.append(f"-- unique({', '.join(parts)}) is enforced by a constraint above")
        fresh.append("")
        # migration file: same tables, but additive only
        migrate.append(f"-- {table}")
        migrate.append(f"create table if not exists {table} (")
        migrate.append(",\n".join(body))
        migrate.append(");")
        for c in cols:
            if c == "id":
                continue
            parts = column_parts(table, c)
            type_sql, strict, default = parts["type"], parts["not_null"], parts["default"]
            if strict and default:
                migrate.append(f"alter table {table} add column if not exists {ident(c)} {type_sql} not null default {default};")
            elif strict:
                # A NOT NULL column with no default cannot be added to a table that already
                # has rows (23502 "column contains null values"). Upgrades stay permissive and
                # invent no data; supabase_schema.sql enforces NOT NULL for fresh databases.
                migrate.append(f"alter table {table} add column if not exists {ident(c)} {type_sql};"
                               f"  -- left nullable on upgrade: existing rows have no value here")
            else:
                migrate.append(f"alter table {table} add column if not exists {ident(c)} {type_sql};")
        for parts in UNIQUE.get(table, []):
            if all(c in cols for c in parts):
                name = f"{table}_{'_'.join(parts)}_uq"
                cols_sql = ", ".join(ident(c) for c in parts)
                migrate.append(f"do $$ begin\n"
                               f"  if exists (select {cols_sql} from {table} group by {cols_sql} having count(*) > 1) then\n"
                               f"    raise notice '{table} has duplicate rows on ({cols_sql}) - unique index {name} skipped';\n"
                               f"  else\n"
                               f"    execute 'create unique index if not exists {name} on {table} ({cols_sql})';\n"
                               f"  end if;\n"
                               f"end $$;")
        migrate.append("")

    fk_header = ["-- ---------------------------------------------------------------- foreign keys",
                 "-- added last, so this file runs on an empty database in any table order",
                 "-- and every statement is guarded - re-running it changes nothing. An existing\n"
                 "-- constraint with a different ON DELETE action is rebuilt, so an older project\n"
                 "-- picks up the safer 'set null' behaviour for manager/reviewer/approver columns.",
                 ""]
    fresh += fk_header + fk_stmts + [""]
    migrate += fk_header + fk_stmts + [""]

    rls = []
    rls.append("-- RLS: the Flask server is the only client and it uses the service_role key (which bypasses RLS),")
    rls.append("-- so the tables stay private to the API by default. Add authenticated policies if you ever query")
    rls.append("-- these tables straight from a browser.")
    tables_sql = ", ".join(f"'{x}'" for x in order)
    rls.append("do $$")
    rls.append("declare t text;")
    rls.append("begin")
    rls.append(f"  for t in select unnest(array[{tables_sql}])::text loop")
    rls.append("    execute format('alter table %I enable row level security', t);")
    rls.append("""    execute format('drop policy if exists "hrms_service_role" on %I', t);""")
    rls.append("""    execute format('create policy "hrms_service_role" on %I for all to service_role using (true) with check (true)', t);""")
    rls.append("  end loop;")
    rls.append("end $$;")
    rls.append("")
    rls.append("grant usage on schema public to anon, authenticated, service_role;")
    rls.append("grant select, insert, update, delete on all tables in schema public to service_role;")
    rls.append("")

    data = ["-- triggers + indexes are re-created idempotently", *checks, "",
            "-- reference data: inserted only while a table is still empty, so nothing you already",
            "-- have on file is duplicated or overwritten.",
            *seed_sql()]

    def write(name, lines):
        open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="\n").write("\n".join(lines).replace("\n\n\n", "\n\n") + "\n")

    write("supabase_schema.sql", fresh + rls + data)

    mig_head = [f"-- Ekkaa HRMS - upgrade an existing Supabase project to the current schema ({stamp}).",
                "-- Generated by tools/gen_schema.py. Safe to re-run: everything below is IF NOT EXISTS,",
                "-- guarded, and never rewrites data you already have.",
                "-- Run this once after pulling the new code, before starting the app.",
                "-- Adding a column? It stays nullable unless a default can fill existing rows -",
                "-- a NOT NULL with no default would abort the whole migration.",
                "", 'create extension if not exists "pgcrypto";', "", SET_UPDATED_AT, ""]
    write("supabase_migrate.sql", mig_head + migrate + data)

    # ------------------------------------------------------------------ the one file
    setup_head = [
        f"-- Ekkaa HRMS - complete database setup, one script ({stamp}, demo data version {mock_data.MOCK_VERSION}).",
        "-- Generated by tools/gen_schema.py; do not edit by hand.",
        "",
        "-- Run this ONE file in the Supabase SQL editor. It is correct whether the project is",
        "-- brand new or already has the older hrms tables:",
        "--   * creates any missing table",
        "--   * adds any missing column (nullable unless a default can fill existing rows)",
        "--   * adds foreign keys last, so table order cannot matter, and rebuilds one whose",
        "--     ON DELETE action differs; an orphan-row violation is a NOTICE, not an abort",
        "--   * recreates triggers, indexes, unique constraints, RLS policies and grants",
        "--   * seeds departments / leave types / shifts / holidays / projects / designations only",
        "--     where those tables are empty",
        "-- Re-running it is a no-op. It never deletes or updates a row you already have.",
        "",
        'create extension if not exists "pgcrypto";',
        "",
        SET_UPDATED_AT,
        "",
    ]
    write("supabase_setup.sql", setup_head + migrate + rls + data)

    # ------------------------------------------------------------- validations
    schema_cols = {t: set(columns_for(t)) for t in order}
    dropped = {}
    for table in order:
        for row in db.get(table, []):
            allowed = SUPA[table] | {"id"} | (LEGACY_EMPLOYEE_COLUMNS if table == "employees" else set())
            for k in row:
                if k.startswith("_") or k in allowed:
                    continue
                dropped.setdefault(table, set()).add(k)
    unwritten = {t: sorted(v) for t, v in dropped.items()}
    extra = {t: sorted(schema_cols[t] - (SUPA[t] | {"id", "created_at", "updated_at"}
                                         | (LEGACY_EMPLOYEE_COLUMNS if t == "employees" else set())))
             for t in order}
    extra = {t: v for t, v in extra.items() if v}
    viol = {}
    for table, constraints in UNIQUE.items():
        rows = db.get(table, [])
        for parts in constraints:
            seen, dup = set(), []
            for r in rows:
                key = tuple(str(r.get(c)) for c in parts)
                if key in seen:
                    dup.append(key)
                seen.add(key)
            if dup:
                viol[f"{table} unique({','.join(parts)})"] = dup[:3]

    FILES = ("supabase_setup.sql", "supabase_schema.sql", "supabase_migrate.sql")
    problems = [x for f_ in FILES for x in lint_sql(f_, written(f_))]
    for f_ in FILES:
        stmts = len(parse_sql(written(f_))) if parse_sql else -1
        print(f"{f_}: {len(written(f_).splitlines())} lines, " +
              (f"{stmts} statements - grammar OK" if stmts >= 0 else "statements (install pglast to grammar-check)"))
    if problems:
        print("\n".join("  " + x for x in problems[:10]))
        raise SystemExit(f"schema lint found {len(problems)} ordering problem(s) - not shipping this")
    print("statement order: every relation referenced after it is created  OK")

    print(f"tables: {len(order)}   columns: {sum(len(v) for v in schema_cols.values())}")
    print("demo rows whose columns the app would drop:", {k: v for k, v in unwritten.items() if v} or "none")
    print("schema columns with no SUPA_COLUMNS entry:", extra or "none")
    print("unique-constraint violations in demo data:", viol or "none")
    if viol:
        raise SystemExit("fix the seed or the constraint")
    print("wrote supabase_schema.sql and supabase_migrate.sql")


if __name__ == "__main__":
    main()
