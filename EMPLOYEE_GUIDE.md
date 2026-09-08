Ekkaa HRMS — how to use your dashboard
Written for someone signing in as a team member (not HR). Section 9 is for HR.
Everything below is what the app actually does today — every number on screen comes from the API.
---
1. First sign-in
Go to `/login` and use your work email plus the password HR gave you (in the demo it is
`demo123`; on your own deployment it is the `EMPLOYEE_PASSWORD` value).
You will see a yellow bar at the top of the dashboard: "You signed in with the shared HR
password. Set your own…". Click Set my password.
Enter the password you just used, then your new one twice. Minimum 8 characters (that floor is
`MIN_PASSWORD_LENGTH`), and it must differ from the one you used.
From now on only your own password opens your account — the shared one stops working for
you, which is exactly the point.
Forgotten password? There is no self-service reset. Ask HR: they open your card and click
Issue password / Reset password, which prints a one-time password once.
Signing in is by email + password only. There is no Google/Microsoft button behind these screens.
2. What you get, and what you don't
Your sidebar shows only what concerns you:
You can open	You cannot open
Home, Me, Inbox	Employees (the HR directory)
Attendance, Leave, Timesheet	Hiring (jobs, candidates, pipeline)
Payroll, Expenses, Documents	Reports (including the custom report builder)
Performance, Org Chart	within Documents: the Compliance tab
	within Timesheet: the Team and Projects tabs
This is not just cosmetic: the HR endpoints answer `403` for your login, so a bookmark, a pasted
URL or the global search box cannot get you in. If something tries, you get "… is only available
to HR Admins" and you land back on Home. What you can still see about other people is the org
chart and a colleague's card (name, role, department, location, who they report to) — no salary,
no documents, no leave reasons.
3. Home
Five cards about you: My day (live status of today's punch), Waiting on approval (your
leave / expenses / documents that are stuck with someone else), On leave today (how many
people are away — a company aggregate), Attendance rate, Holidays ahead. Below them: the
today panel (birthdays, anniversaries, who is off), your timesheet tracker, announcements.
4. The daily loop
Clock in / Clock out are the two buttons in the dark tracker strip at the top of Home.
The tracker next to them
shows worked hours, break, overtime, whether you were late, and how many minutes you still need
against your shift (`09:30–18:30`, 15 min grace, 45 min break by default).
Times are the office timezone (`APP_TIMEZONE` on the server, default `Asia/Kolkata`) — never
the web host's clock, so a punch made in the cloud reads the same as one made on a laptop.
One Clock in and one Clock out per day. While you are in, the first button reads
Clocked in and clicking it again changes nothing; once both punches exist the strip reads
Day closed and both buttons go grey. That is deliberate — a closed day is corrected through
Regularization (below) or by HR, never by punching again, so your morning time cannot be
overwritten by an extra click.
Timesheet → My week: type hours into any day/project cell (0–16 h per day, half-hour steps —
a bigger number is rejected with a toast), use Save draft
any time, then Submit for approval. A submitted week is locked for you; the tab History
keeps every week with its status, and each week's rejection/approval note is shown there.
Working on something that is not on the list? In a row's project dropdown the last entry is
+ Type a new project name… — or press New project under the grid. Give it a name, a client
and a ₹/hour rate if a client is paying (0 means internal time), and the row is logging against it
straight away with the hours you had typed still in place. Leave Code blank and one is made
from the name; codes are unique, so the app checks before saving rather than after.
A project you added is yours to fix: edit and remove sit under it in the row. Renaming or
deleting it is open to its manager and to HR only, and anything that already has hours on it cannot
be deleted at all — mark it Completed or Closed instead, so the time people claimed keeps
somewhere to live. A closed project disappears from the dropdown for new entries but stays on the
row that still carries its hours.
5. Time off and missed punches
Leave → Apply for leave: pick type, dates, reason. The card shows your balance per leave type
and how much is already used; pending days are already subtracted so you cannot double-book.
Attendance → Regularization (the same button appears inside any day you open): pick the day,
choose missing punch-in / punch-out / both, and type a reason. The reason is mandatory —
the submit button stays disabled until you write one, because that text is what your approver
reads. You will see the day's actual punches next to the form, so you can describe the gap.
What an approval does: the times you proposed replace the punches on that day, the worked hours
and the late mark are recomputed from them, and a day that was `Absent` becomes `Present`
(`Half day` under 4 h). You never type the hours yourself — that is HR's edit screen.
Status per day: `Present`, `WFH`, `Half day`, `On leave`, `Absent`. A correction in flight keeps
the day's own status and adds a separate `Pending` pill next to it, so you can see both.
6. Money
Payroll → Payslips lists one row per month you have been paid for: period, gross, deductions,
net pay, days, status, the date it was paid, and View. Opening a slip gives you the real
document — every earning line, every deduction line (a `Loss of pay` line appears only when an
absent or half-day is in that month's attendance), the days used
(`22 working · 21 payable · 1 loss of pay`), the net amount written out in words, your bank
details, and Print / save PDF. Nothing on that page is editable by you; if a number looks
wrong, raise it with HR, because the row you see is what was paid.
Payroll → My structure is your salary structure as HR maintains it: basic, HRA, every named
allowance, then deductions (PF, ESI, professional tax, TDS), the monthly gross, what you keep
after deductions (`net before attendance`), the employer's PF and the annual CTC. It is
read-only — this is the page to check before you ask a question about a payslip. If HR keeps a
second revision on file for a future date, this card shows the one in force today.
A payslip you have run but HR has not published yet is not shown to you at all: the list is
empty and the period says it is still being prepared. That is deliberate — draft numbers move.
Expenses → New claim: date, category, amount, what it was for, and the receipt file. A claim
with a receipt goes faster; the row keeps its status (`Pending`, `Approved`, `Rejected`, `Paid`)
and the approver's note. Approved amounts appear as a reimbursement line in a later payslip.
7. Documents
Documents → Document vault → Upload document. You fill in what it is, why you are filing
it (purpose) and who may see it (visibility, e.g. `Employee & HR`, `Self + HR`). Those two
fields are why the record is useful later — you and HR both know what it was for.
Requests: HR can ask you for something (offer letter, PAN, address proof). It shows up in your
Inbox with a due date; open it, upload the file, and it goes back to HR for verification.
Verified documents get a tick in Me; an expiring one (passport, visa, licence) shows its
validity so you renew before HR has to chase you.
8. Performance and people
Performance: your goals with progress bars — update progress with a note, and your manager
sees it live. Self review, your rating, feedback received and 1:1 check-ins are all in this
module. Only your reviewer/HR can set a rating.
Org Chart: the reporting tree and a department view. Use it to find who to ask, or to reach a
colleague's card. If your manager row looks wrong, tell HR — you cannot change reporting lines
yourself. Departments themselves are HR's to create (Org chart → Add department): if your
team is missing from the list, ask HR to add it and to move you onto it.
9. For HR: giving and taking away access
Admins are the emails in `ADMIN_EMAILS` (comma separated). Everyone else is an Employee.
Onboarding someone: Employees → Add employee, and in First sign-in type a starter
password (or leave it empty to use the shared one). The confirmation tells you exactly how that
person signs in.
Handing out a new password: open their card → Issue password / Reset password. A one-time
password is generated and shown once — copy it, send it, and ask them to change it in Me.
Locking someone out properly: set their status to Exited; the login page then refuses them
with "This account is not active any more".
Policy: `MIN_PASSWORD_LENGTH` (default 8, never below 6), `EMPLOYEE_PASSWORD` for the bootstrap,
`ADMIN_PASSWORD` for admins. Set these as environment variables; they are not stored in the code.
Timesheet → Projects is the billing view: rate, hours this week, all-time hours and billable
value per project, with edit and remove on every row. Rename, close, or reassign the manager —
reassigning is how a project passes to someone new when its manager leaves. `POST /api/projects` is
open to everyone on purpose (anyone can add a project to log against); `PUT`/`DELETE` are not.
Employees can export their own attendance / leave / payslip rows as CSV. Every other export
(directory, hiring, org) stays with HR.
Before anything else, Payroll → Salary structures needs one structure per employee — the
tab lists every active employee, flags the ones with none, and filters to exactly those when you
press Without a structure (the notice bar calls the same thing Fix that). New structure opens the form: basic, HRA, special allowance, any
number of named allowance lines, then PF / ESI / professional tax / TDS. The strip under the fields
keeps the monthly gross, net and the annual CTC in front of you while you type, and the CTC is
computed from the components (an annual CTC you disagree with can be typed in, and the save is
refused with a sentence if the two do not agree). Revisions are dated: add a row with a future
`Effective from` and the older one still governs the months before it.
Running the month (HR Admin only, Payroll tab): Run payroll pre-fills the month the server
is in, and the modal tells you how many slips already exist for it and how many employees will be
skipped for having no structure. Run it for everyone or for the one employee in the filter. Each
slip is built from the structure in force for that month, `days worked`, and attendance: an absent
day costs a full day's gross, a half day half of it, and unpaid leave in that month is docked the
same way — that shows up as a `Loss of pay` line, never as a silent change to basic. It lands as a
Draft; tick Publish to employees immediately to skip a step, or press Publish after
checking. When the money has left the bank, Mark paid stamps a date on every published slip. A period can be re-run: published slips are left
alone unless you tick Rebuild published slips, which overwrites them.
Correcting one person: View on their slip → Edit (bonus, remarks, or the days). A published
or paid slip will not change quietly — use Revoke, give a reason of at least 8 characters, and
the slip becomes a draft again: hidden from the employee, editable, then published once more.
Register CSV in the toolbar downloads the bank file for the period on screen: employee code,
days, bonus, gross, deductions, net, status, paid-on date, plus account number, IFSC, bank name
and branch from each person's record.
Supabase deployments: run `supabase_setup.sql` once, because per-person passwords need the
`employees.password_hash` column it adds.
10. House rules the app enforces
You never see another person's password hash, and no page ever shows a password to anyone.
Your edits in Me → Edit my profile are limited to contact details, address, emergency
contact and work location. Salary, department, manager, leave balances and bank details are
HR-only (locked fields are shown greyed, so you know they exist).
Anything you submit that needs approval lands in that person's Inbox — not in yours. Your Inbox
lists what you must approve and what you are waiting on.
The demo reset button (bottom of the sidebar, demo mode only) wipes test changes. It is
admin-only, and it does nothing at all once the app is connected to a real database.
