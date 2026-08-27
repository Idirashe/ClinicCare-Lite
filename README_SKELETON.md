# ClinicCare-Lite — App Skeleton

This is the starting skeleton for the team to build on. Registration,
login, ID validation, and password hashing are already working —
everything else is a placeholder marked with `TODO` comments for whoever
owns that feature.

## How to run it

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser. You can register a
test patient (ID ending in a year 2022-2028, e.g. `12342024`) or a
test clinician (ID ending in `0000`, e.g. `12340000`).

## Folder structure

```
app.py                          # entry point — run this
backend/
  storage.py                    # shared JSON read/write helper
  data/                         # users.json, health_tasks.json, etc. (auto-created)
  models/
    user.py                     # User model — registration, login, validation (DONE)
    clinic.py                   # Clinic model — basic CRUD skeleton
    health_task.py               # HealthTask model — basic CRUD skeleton
    task_submission.py          # TaskSubmission model — file upload + review skeleton
    message.py                  # Message model — messaging skeleton
  auth/
    routes.py                   # /register, /login, /logout (DONE, working)
  routes/
    main.py                     # dashboard routes (placeholders)
frontend/
  templates/                    # HTML pages (Jinja2)
  static/css/style.css          # basic starter styling
submissions/                    # uploaded patient files go here (per clinic/patient)
tests/                          # put your tests here
```

## What's already working
- User registration with ID format validation (clinician `...0000`,
  patient `...2022`-`2028`) and password complexity rules
- Passwords hashed with bcrypt — never stored in plaintext
- Login with session-based auth
- Role-based redirect to clinician or patient dashboard

## What each member should build next (see PROJECT_PLAN.md for full task list)
- **Member 2 (Patient Services):** file upload route using
  `TaskSubmission.is_allowed_file()` / `build_filename()`, wellness
  tracker, patient dashboard content
- **Member 3 (Clinician Services):** task creation form using
  `HealthTask.create()`, submission review UI using
  `TaskSubmission.review()`, messaging UI using `Message.send()`
- **Member 4 (UI/Analytics/Testing):** styling, analytics dashboard
  (Plotly/Matplotlib), tests in `tests/`
- **Member 1 (this skeleton):** session/access-control hardening,
  email notifications (smtplib), deployment config

## Data storage
Per the project spec, this uses **JSON files**, not a database. Files
are created automatically in `backend/data/` the first time they're
needed — you won't see them until you register a user or create a task.
Do not commit real user data to GitHub — `backend/data/*.json` should
stay in `.gitignore`.
