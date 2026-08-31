-- Keka HRMS Clone - Supabase Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- DEPARTMENTS
create table if not exists departments (
  id uuid primary key default uuid_generate_v4(),
  name text not null unique,
  description text,
  head_id uuid,
  created_at timestamptz default now()
);

-- DESIGNATIONS
create table if not exists designations (
  id uuid primary key default uuid_generate_v4(),
  title text not null,
  department_id uuid references departments(id),
  level int default 1,
  created_at timestamptz default now()
);

-- EMPLOYEES (Core HR)
create table if not exists employees (
  id uuid primary key default uuid_generate_v4(),
  employee_code text unique not null,
  full_name text not null,
  email text unique not null,
  phone text,
  avatar_url text,
  department_id uuid references departments(id),
  designation_id uuid references designations(id),
  manager_id uuid references employees(id),
  date_of_joining date default current_date,
  date_of_birth date,
  gender text check (gender in ('Male','Female','Other')),
  employment_type text default 'Full-time' check (employment_type in ('Full-time','Part-time','Contract','Intern')),
  work_location text default 'Bangalore',
  status text default 'Active' check (status in ('Active','On Leave','Probation','Notice Period','Exited')),
  salary_ctc numeric default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- SHIFTS
create table if not exists shifts (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  start_time time not null,
  end_time time not null,
  grace_minutes int default 15,
  created_at timestamptz default now()
);

-- ATTENDANCE
create table if not exists attendance (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  date date not null default current_date,
  clock_in timestamptz,
  clock_out timestamptz,
  work_hours numeric default 0,
  status text default 'Present' check (status in ('Present','Absent','Half Day','Work From Home','On Leave','Week Off')),
  shift_id uuid references shifts(id),
  location text,
  regularization_status text default 'None' check (regularization_status in ('None','Pending','Approved','Rejected')),
  regularization_reason text,
  created_at timestamptz default now(),
  unique(employee_id, date)
);

-- LEAVE TYPES
create table if not exists leave_types (
  id uuid primary key default uuid_generate_v4(),
  name text not null unique,
  code text not null unique,
  color text default '#6c5ce7',
  yearly_quota int default 12,
  is_paid boolean default true,
  requires_approval boolean default true
);

-- LEAVE BALANCES
create table if not exists leave_balances (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  leave_type_id uuid references leave_types(id),
  year int default extract(year from now()),
  total int default 0,
  used int default 0,
  pending int default 0,
  remaining int generated always as (total - used - pending) stored,
  unique(employee_id, leave_type_id, year)
);

-- LEAVE REQUESTS
create table if not exists leave_requests (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  leave_type_id uuid references leave_types(id),
  start_date date not null,
  end_date date not null,
  days int not null,
  reason text,
  status text default 'Pending' check (status in ('Pending','Approved','Rejected','Cancelled')),
  approver_id uuid references employees(id),
  applied_at timestamptz default now(),
  actioned_at timestamptz
);

-- HOLIDAYS
create table if not exists holidays (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  date date not null unique,
  type text default 'Public' check (type in ('Public','Optional','Company')),
  created_at timestamptz default now()
);

-- PAYROLL STRUCTURES
create table if not exists payroll_structures (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade unique,
  basic numeric default 0,
  hra numeric default 0,
  special_allowance numeric default 0,
  pf numeric default 0,
  esi numeric default 0,
  professional_tax numeric default 0,
  tds numeric default 0,
  ctc numeric default 0,
  effective_from date default current_date
);

-- PAYSLIPS
create table if not exists payslips (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  month int not null,
  year int not null,
  gross_earnings numeric default 0,
  total_deductions numeric default 0,
  net_pay numeric default 0,
  status text default 'Generated' check (status in ('Draft','Generated','Paid')),
  payslip_url text,
  generated_at timestamptz default now(),
  unique(employee_id, month, year)
);

-- REIMBURSEMENTS
create table if not exists reimbursements (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  category text not null,
  amount numeric not null,
  date date not null,
  description text,
  receipt_url text,
  status text default 'Pending' check (status in ('Pending','Approved','Rejected','Paid')),
  created_at timestamptz default now()
);

-- JOBS (ATS)
create table if not exists jobs (
  id uuid primary key default uuid_generate_v4(),
  title text not null,
  department_id uuid references departments(id),
  location text default 'Bangalore',
  employment_type text default 'Full-time',
  experience text,
  openings int default 1,
  description text,
  status text default 'Open' check (status in ('Draft','Open','Closed','On Hold')),
  posted_at timestamptz default now()
);

-- CANDIDATES
create table if not exists candidates (
  id uuid primary key default uuid_generate_v4(),
  job_id uuid references jobs(id) on delete cascade,
  full_name text not null,
  email text not null,
  phone text,
  resume_url text,
  experience_years numeric default 0,
  current_ctc numeric,
  expected_ctc numeric,
  stage text default 'Applied' check (stage in ('Applied','Screening','Interview','Offer','Hired','Rejected')),
  rating int default 0 check (rating between 0 and 5),
  applied_at timestamptz default now()
);

-- GOALS / OKRs
create table if not exists goals (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  title text not null,
  description text,
  category text default 'Performance',
  progress int default 0 check (progress between 0 and 100),
  status text default 'In Progress' check (status in ('Not Started','In Progress','Completed','At Risk')),
  due_date date,
  created_at timestamptz default now()
);

-- PERFORMANCE REVIEWS
create table if not exists performance_reviews (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  reviewer_id uuid references employees(id),
  period text not null,
  rating numeric default 0 check (rating between 0 and 5),
  strengths text,
  improvements text,
  status text default 'Pending' check (status in ('Pending','In Review','Completed')),
  created_at timestamptz default now()
);

-- ANNOUNCEMENTS
create table if not exists announcements (
  id uuid primary key default uuid_generate_v4(),
  title text not null,
  content text not null,
  type text default 'General' check (type in ('General','Policy','Event','Celebration')),
  created_by uuid references employees(id),
  is_pinned boolean default false,
  created_at timestamptz default now()
);

-- DOCUMENTS
create table if not exists documents (
  id uuid primary key default uuid_generate_v4(),
  employee_id uuid references employees(id) on delete cascade,
  name text not null,
  type text not null,
  file_url text,
  status text default 'Pending' check (status in ('Pending','Verified','Rejected')),
  uploaded_at timestamptz default now()
);

-- INSERT DEFAULT DATA
insert into departments (name, description) values 
('Engineering','Product and Engineering'),
('Human Resources','HR and People Ops'),
('Sales','Sales and Business Development'),
('Marketing','Marketing and Growth'),
('Finance','Finance and Accounting'),
('Design','Product Design')
on conflict (name) do nothing;

insert into shifts (name, start_time, end_time) values
('General Shift','09:30:00','18:30:00'),
('Morning Shift','06:00:00','15:00:00'),
('Night Shift','21:00:00','06:00:00'),
('Flexible','10:00:00','19:00:00')
on conflict do nothing;

insert into leave_types (name, code, color, yearly_quota) values
('Casual Leave','CL','#6c5ce7',12),
('Sick Leave','SL','#00b894',12),
('Earned Leave','EL','#0984e3',18),
('Work From Home','WFH','#fdcb6e',24),
('Optional Holiday','OH','#e17055',2)
on conflict (name) do nothing;

insert into holidays (name, date, type) values
('New Year','2026-01-01','Public'),
('Republic Day','2026-01-26','Public'),
('Holi','2026-03-03','Public'),
('Independence Day','2026-08-15','Public'),
('Diwali','2026-10-20','Public'),
('Christmas','2026-12-25','Public')
on conflict (date) do nothing;

-- Enable RLS (Row Level Security) - For demo we make it permissive, you can tighten later
alter table employees enable row level security;
alter table attendance enable row level security;
alter table leave_requests enable row level security;
alter table departments enable row level security;
alter table designations enable row level security;
alter table shifts enable row level security;
alter table leave_types enable row level security;
alter table leave_balances enable row level security;
alter table holidays enable row level security;
alter table payroll_structures enable row level security;
alter table payslips enable row level security;
alter table reimbursements enable row level security;
alter table jobs enable row level security;
alter table candidates enable row level security;
alter table goals enable row level security;
alter table performance_reviews enable row level security;
alter table announcements enable row level security;
alter table documents enable row level security;

-- Permissive policies for anon and authenticated (replace with strict policies in production)
do $$
declare
  t text;
begin
  foreach t in array array[
    'employees','departments','designations','shifts','attendance','leave_types','leave_balances','leave_requests','holidays','payroll_structures','payslips','reimbursements','jobs','candidates','goals','performance_reviews','announcements','documents'
  ] loop
    execute format('drop policy if exists "Allow all for anon" on %I', t);
    execute format('drop policy if exists "Allow all for authenticated" on %I', t);
    execute format('create policy "Allow all for anon" on %I for all using (true) with check (true)', t);
    execute format('create policy "Allow all for authenticated" on %I for all to authenticated using (true) with check (true)', t);
  end loop;
end $$;

-- The Flask server uses the service_role key. Keep these grants in sync with
-- the permissive demo policies above so PostgREST can access the tables.
grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on all tables in schema public to anon, authenticated, service_role;
grant usage, select on all sequences in schema public to anon, authenticated, service_role;

-- Function to auto-update updated_at
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists employees_updated_at on employees;
create trigger employees_updated_at before update on employees for each row execute function update_updated_at();
