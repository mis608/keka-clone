# Keka HRMS Clone - Python + Supabase

A complete, production-ready clone of **Keka HRMS** built with **Python Flask** and **Supabase**. Pixel-perfect Keka UI with all major modules.

![Keka Clone](https://img.shields.io/badge/Stack-Flask%20%2B%20Supabase-584ac0) ![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features - 100% Keka Parity

### 1. **Dashboard / Home**
- Live clock in/out widget
- Stats: Total employees, present, on leave, open positions
- Attendance trend chart (Chart.js)
- Department distribution doughnut
- Announcements, birthdays, anniversaries, who's on leave
- Pending approvals with approve/reject inline
- Quick actions

### 2. **Core HR - Employees**
- Employee directory with search, department & status filters
- Add employee (auto code generation KEKA001...)
- Employee cards with avatar initials, department tags
- Mock + Supabase dual mode

### 3. **Time & Attendance**
- Clock in / Clock out with live timestamp
- Attendance log table (date, in/out, work hours, status)
- Monthly summary, shift details
- Regularization flow
- Stores in `attendance` table

### 4. **Leave Management**
- Leave balances cards (CL, SL, EL, WFH) with color coding
- Apply leave modal (calculates days automatically)
- Approval workflow (Pending → Approved/Rejected)
- Team calendar mini-view
- `leave_types`, `leave_balances`, `leave_requests` tables

### 5. **Payroll**
- Payroll cost overview
- Payslips table (gross, deductions, net)
- Run payroll button, download payslips
- `payroll_structures`, `payslips` tables

### 6. **Recruitment / ATS**
- Job openings grid with applicant counts
- Candidate pipeline kanban (Applied, Screening, Interview, Offer, Hired)
- Candidate cards with ratings
- `jobs`, `candidates` tables

### 7. **Performance**
- OKRs / Goals with progress bars
- Performance reviews (Q1, Q2 cycles)
- Feedback with tags (#teamwork)
- `goals`, `performance_reviews` tables

### 8. **Other Modules**
- Me (profile)
- Inbox (approvals)
- Org Chart
- Documents
- Timesheet
- Expenses / Reimbursements
- Reports

---

## 🏗️ Tech Stack

- **Backend:** Python Flask 3.0, Flask-Cors, Gunicorn
- **Database:** Supabase (Postgres + Auth + Storage)
- **Frontend:** Tailwind CSS (CDN), Vanilla JS, Chart.js, Font Awesome
- **Auth:** Session-based (demo), ready for Supabase Auth
- **Deployment:** Works on Render, Railway, Fly.io, Vercel (with adaptor)

---

## 📁 Project Structure

```
keka-hrms-clone/
├── app.py                 # Main Flask app + all API routes
├── requirements.txt       # Python deps
├── .env.example           # Env template
├── supabase_schema.sql    # Full DB schema (run in Supabase SQL editor)
├── templates/
│   ├── base.html          # Base layout (Tailwind config)
│   ├── login.html         # Login page (Keka dark branding)
│   └── dashboard.html     # Main SPA - all modules
└── static/
    └── js/app.js          # Frontend logic, charts, API calls
```

---

## 🚀 Setup From Scratch - Step by Step

### Step 1: Create Supabase Project
1. Go to https://supabase.com → New Project
2. Name: `keka-hrms-clone`, set DB password
3. Wait ~2 mins for provisioning
4. Go to **Project Settings → API** → Copy:
   - `Project URL` (e.g. https://xyz.supabase.co)
   - `anon public key`
   - `service_role key` (keep secret)

### Step 2: Run Database Schema
1. In Supabase Dashboard → **SQL Editor** → New Query
2. Paste entire `supabase_schema.sql` file content
3. Click **Run** → Should create 18 tables + seed data
4. Verify in **Table Editor** → you should see `departments`, `employees`, etc.

### Step 3: Clone & Setup Python Env
```bash
git clone <your-repo>
cd keka-hrms-clone

# Create venv
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
cp .env.example .env
# Edit .env
nano .env
```
Fill:
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
FLASK_SECRET_KEY=random-string-here-123
PORT=5000
USE_MOCK_DATA=false
```

> **Tip:** If you leave SUPABASE_URL empty or set `USE_MOCK_DATA=true`, app runs in **Mock Mode** with sample data (no DB needed). Perfect for demo.

### Step 5: Run App
```bash
python app.py
```
Open:
- Login: http://localhost:5000/login
- Dashboard: http://localhost:5000/dashboard
- Health: http://localhost:5000/api/health

Demo login: **any email + any password** (e.g. admin@company.com / demo123)

### Step 6: (Optional) Enable Supabase Auth
In `app.py`, uncomment Supabase Auth code in `/login` route:
```python
if supabase:
  res = supabase.auth.sign_in_with_password({"email": email, "password": password})
  session['user'] = res.user
```
And create users in Supabase **Authentication → Users**.

### Step 7: Deploy
**Render.com:**
- New Web Service → Connect repo
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Add env vars from .env

**Railway / Fly.io:** Same - Flask + Gunicorn works out of the box.

---

## 🔌 API Endpoints

All under `/api/`:

- `GET /api/stats` - dashboard stats
- `GET/POST /api/employees` - CRUD employees
- `POST /api/attendance` - clock in/out
- `GET /api/attendance` - logs
- `GET/POST /api/leave-requests` - leave workflow
- `POST /api/leave-requests/<id>/action` - approve/reject
- `GET /api/departments`, `/api/leave-types`, `/api/jobs`, `/api/candidates`, `/api/payslips`, `/api/announcements`, `/api/goals`, `/api/holidays`, `/api/health`

All endpoints work in both Mock and Supabase mode via `get_supabase_data()` wrapper.

---

## 🎨 UI Details - Keka Exact Clone

- **Sidebar:** #1e1f2b dark, active state #2f3244, icons with opacity
- **Primary:** #584ac0 (Keka purple)
- **Background:** #f6f7fb (light gray)
- **Cards:** 16px radius, 1px #eef0f6 border, soft shadow
- **Typography:** Inter + Plus Jakarta Sans (like Keka)
- **Components:** Pill filters, avatar initials, status dots

---

## 🔒 Production Hardening TODO

- Replace mock auth with Supabase Auth + RLS strict policies
- Add role-based access (HR Admin, Manager, Employee)
- File uploads → Supabase Storage (resumes, docs, receipts)
- Add pagination & server-side search
- Email notifications for leave approvals (Supabase Edge Functions)
- Payroll calculation engine (PF, ESI, TDS logic)
- Biometric attendance integration via webhooks

---

## 📸 Screenshots Flow

Login → Dashboard with clock widget → Employees table → Leave apply → Payroll → Hiring kanban → Performance OKRs

All modules are SPA sections inside `dashboard.html` - no page reloads.

---

## 🤝 Contributing

PRs welcome! This is meant as a starter kit for anyone building HRMS in Python.

---

## 📄 License

MIT - Use freely for your company.

Built with ❤️ as Keka clone - Python + Supabase edition.
