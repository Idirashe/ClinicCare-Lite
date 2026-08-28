"""
ClinicCare-Lite - main Flask application.

This is the entry point that ties all the models and routes together.
Run it with: python app.py

SCOPE REMINDER: this app is administrative and communication only.
No route here may interpret medical meaning, diagnose, or recommend
treatment - only structural checks (is a field filled in? is the file
type allowed?) are permitted.
"""

from flask import Flask, render_template, request, session, redirect, url_for, flash, send_file
import os
import json
from dotenv import load_dotenv

from models.user import User
from utils.email_handler import notify_submission_received, notify_review_complete
from models.health_task import HealthTask
from models.task_submission import TaskSubmission, check_form_completeness
from models.clinic import Clinic
from models.health_task import HealthTask
from models.message import Message
from utils.patient_dashboard import build_patient_dashboard_data
from utils.analytics import build_analytics_summary

# Load SECRET_KEY and email credentials from .env before anything else runs.
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")



def login_required():
    return "user_id" in session


# ----------------------------------------------------------------------
# AUTH ROUTES (Louange)
# ----------------------------------------------------------------------

@app.route("/")
def index():
    """Landing page - shows the login form."""
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registration page. On POST, validates the ID format and password
    strength BEFORE creating the account - never save an invalid user.
    """
    if request.method == "POST":
        user_id = request.form["user_id"]
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]  # "clinician" or "patient"

        if not User.validate_id(user_id, role):
            flash("Invalid ID format for the selected role.")
            return render_template("register.html")

        if not User.validate_password(password):
            flash("Password must be at least 8 characters and include "
                  "an uppercase letter, a lowercase letter, a digit, "
                  "and a special character (!@#$%^&*).")
            return render_template("register.html")

        if User.load(user_id) is not None:
            flash("An account with this ID already exists.")
            return render_template("register.html")

        new_user = User(user_id, name, email, password, role)
        new_user.save()

        flash("Registration successful. Please log in.")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["POST"])
def login():
    """
    Log a user in. We check credentials with check_password_for_login()
    rather than comparing plain text, since passwords are stored hashed.
    """
    user_id = request.form["user_id"]
    password = request.form["password"]

    if User.check_password_for_login(user_id, password):
        user_record = User.load(user_id)
        session["user_id"] = user_id
        session["role"] = user_record["role"]
        session["name"] = user_record["name"]
        return redirect(url_for("dashboard"))

    flash("Invalid ID or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    """Clear the session, logging the user out."""
    session.clear()
    return redirect(url_for("index"))


# ----------------------------------------------------------------------
# DASHBOARD ROUTING
# ----------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("index"))

    if session["role"] == "clinician":
        return clinician_dashboard_view()

    # --- Patient branch: gather real dashboard data ---
    dashboard_data = build_patient_dashboard_data(session["user_id"])
    user_record = User.load(session["user_id"])
    theme = user_record.get("theme", "colourful") if user_record else "colourful"

    return render_template(
        "patient_dashboard.html",
        name=session["name"],
        theme=theme,
        tasks=dashboard_data["tasks"],
        messages=dashboard_data["messages"],
        overdue_count=dashboard_data["overdue_count"],
        pending_count=dashboard_data["pending_count"],
        engagement=dashboard_data["engagement"],
        upcoming_appointments=dashboard_data["upcoming_appointments"],
    )


# ----------------------------------------------------------------------
# PATIENT ROUTES (Idirashe - Member 2: Patient Services, File Handling
# and Engagement Lead)
# ----------------------------------------------------------------------

@app.route("/submit_task/<task_id>", methods=["POST"])
def submit_task(task_id):
    if "user_id" not in session or session["role"] != "patient":
        return redirect(url_for("index"))

    patient_id = session["user_id"]

    task_record = None
    with open(os.path.join("data", "health_tasks.json"), "r") as f:
        all_tasks = json.load(f)
    if task_id in all_tasks:
        task_record = all_tasks[task_id]

    if task_record is None or task_record["assigned_patient_id"] != patient_id:
        flash("That task could not be found or is not assigned to you.")
        return redirect(url_for("dashboard"))

    with open(os.path.join("data", "task_submissions.json"), "r") as f:
        all_submissions = json.load(f)
    existing = all_submissions.get(f"{patient_id}_{task_id}")

    LOCKED_STATUSES = ("Reviewed - Normal", "Escalated")
    if existing is not None and existing["review_status"] in LOCKED_STATUSES:
        flash("This task has already been reviewed and can no longer be resubmitted.")
        return redirect(url_for("dashboard"))

    uploaded_file = request.files.get("submission_file")

    if uploaded_file is None or uploaded_file.filename == "":
        flash("Please choose a file to upload.")
        return redirect(url_for("dashboard"))

    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded_file.filename)
    uploaded_file.save(temp_path)

    try:
        submission = TaskSubmission(
            patient_id, task_id, temp_path,
            clinic_id=task_record.get("clinic_id"),
            original_filename=uploaded_file.filename,
        )
        submission.save_file()
        submission.save()

        required_fields = task_record.get("required_fields") or []
        _, ext = os.path.splitext(uploaded_file.filename)
        if required_fields and ext.lower() in (".csv", ".txt"):
            field_types = task_record.get("field_types") or {}
            problems = check_form_completeness(
                submission.final_file_path, required_fields, field_types
            )
            if problems:
                for problem in problems:
                    flash(f"Form check: {problem}")
            else:
                flash("Your file was submitted successfully and passed the completeness check.")
        else:
            flash("Your file was submitted successfully.")

        notify_clinician_of_submission(task_record.get("clinic_id"), patient_id, task_record)

    except ValueError as error:
        flash(str(error))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return redirect(url_for("dashboard"))

@app.route("/download_submission/<task_id>")
def download_submission(task_id):
    """
    Let a patient securely download their own previously submitted
    file. Access is restricted to the task's assigned patient only.
    """
    if "user_id" not in session:
        return redirect(url_for("index"))

    patient_id = session["user_id"]

    with open(os.path.join("data", "task_submissions.json"), "r") as f:
        all_submissions = json.load(f)

    submission = all_submissions.get(f"{patient_id}_{task_id}")
    if submission is None or submission["patient_id"] != patient_id:
        flash("That submission could not be found.")
        return redirect(url_for("dashboard"))

    file_path = submission["file_path"]
    if not file_path or not os.path.exists(file_path):
        flash("The file for this submission is no longer available.")
        return redirect(url_for("dashboard"))

    return send_file(file_path, as_attachment=True)


@app.route("/toggle_theme", methods=["POST"])
def toggle_theme():
    """Flip the logged-in patient's theme between colourful and dark."""
    if "user_id" not in session:
        return redirect(url_for("index"))

    user_record = User.load(session["user_id"])
    if user_record is None:
        return redirect(url_for("dashboard"))

    current_theme = user_record.get("theme", "colourful")
    new_theme = "dark" if current_theme != "dark" else "colourful"

    with open(os.path.join("data", "users.json"), "r+") as f:
        data = json.load(f)
        data[session["user_id"]]["theme"] = new_theme
        f.seek(0)
        f.truncate()
        json.dump(data, f, indent=4)

    return redirect(url_for("dashboard"))


# ----------------------------------------------------------------------
# ANALYTICS ROUTE (Naomi - Member 4: UI, Analytics, Testing and
# Deployment Lead) - Section C: Operational analytics dashboard
# ----------------------------------------------------------------------

@app.route("/analytics")
def analytics_dashboard():
    """
    Clinician-facing operational analytics. Restricted to logged-in
    CLINICIANS only - a patient hitting this URL directly is redirected
    away rather than shown clinic-wide data, since that data isn't
    meant for a patient's eyes even in aggregate form.
    """
    if not login_required() or session.get("role") != "clinician":
        flash("You must be logged in as a clinician to view analytics.")
        return redirect(url_for("index"))

    clinic_id, clinic_record = Clinic.get_clinic_for_clinician(session["user_id"])
    if clinic_id is None:
        flash("No clinic is currently associated with your account.")
        return redirect(url_for("dashboard"))

    summary = build_analytics_summary(clinic_id)
    return render_template("analytics_dashboard.html", summary=summary)


# ----------------------------------------------------------------------
# ERROR HANDLERS (Naomi - Member 4) - Section A: Error pages
# ----------------------------------------------------------------------

@app.errorhandler(404)
def handle_not_found(error):
    """Shown when a URL doesn't match any route at all."""
    return render_template(
        "error.html", code=404, title="Page not found",
        message="The page you're looking for doesn't exist or may have moved."
    ), 404


@app.errorhandler(403)
def handle_forbidden(error):
    """Shown when a logged-in user tries to access something they're
    not allowed to (e.g. a patient hitting a clinician-only route)."""
    return render_template(
        "error.html", code=403, title="Access denied",
        message="You don't have permission to view this page."
    ), 403


@app.errorhandler(500)
def handle_server_error(error):
    """
    Shown for unexpected server errors. Deliberately generic wording -
    never leak internal details (file paths, stack traces) to the
    user, since that could expose information useful to an attacker.
    """
    return render_template(
        "error.html", code=500, title="Something went wrong",
        message="An unexpected error occurred on our end. Please try again shortly."
    ), 500


"""
ROUTES TO ADD TO app.py — Member 3 (Jolene): Clinician Services,
Messaging and Notification Lead.

HOW TO USE THIS FILE:
1. Add these two import lines near the top of app.py, next to the
   existing model imports:

       from models.health_task import HealthTask
       from models.message import Message

2. Copy everything below the line of dashes into app.py, anywhere
   after the existing routes (e.g. right after the /analytics route,
   before the error handlers at the bottom).

3. REPLACE the placeholder clinician branch inside the existing
   /dashboard route:

       if session["role"] == "clinician":
           return render_template("clinician_dashboard.html", name=session["name"])

   with:

       if session["role"] == "clinician":
           return clinician_dashboard_view()

   (This keeps the existing /dashboard URL working, but now shows the
   real dashboard instead of the placeholder.)

4. Also drop the four new template files (clinician_dashboard.html —
   overwriting the placeholder, create_task.html, review_submission.html,
   messages.html, create_announcement.html) into your templates/ folder.

Everything below follows the exact same patterns already used
elsewhere in app.py: read-modify-write JSON with r+/seek/truncate,
session-based access control, and flash() for user feedback.
"""

import json
import os
from datetime import datetime
from flask import render_template, request, session, redirect, url_for, flash

from models.health_task import HealthTask
from models.message import Message
from models.clinic import Clinic


# ----------------------------------------------------------------------
# CLINICIAN DASHBOARD (Jolene — Member 3)
# ----------------------------------------------------------------------

def clinician_dashboard_view():
    """
    Builds the real clinician dashboard: clinic info, registered
    patients, this clinic's health tasks, and pending submissions
    awaiting review. Called from the /dashboard route above.
    """
    clinician_id = session["user_id"]
    clinic_id, clinic_record = Clinic.get_clinic_for_clinician(clinician_id)

    if clinic_id is None:
        flash("No clinic is currently associated with your account.")
        return render_template("clinician_dashboard.html", name=session["name"],
                                clinic=None, tasks=[], submissions=[],
                                announcements=[])

    tasks = HealthTask.get_all_for_clinic(clinic_id)

    # Pull every submission for this clinic's tasks so the clinician can
    # filter/review them. Submissions are keyed "patientID_taskID".
    with open(os.path.join("data", "task_submissions.json"), "r") as f:
        all_submissions = json.load(f)
    task_ids_for_clinic = {task_id for task_id, _ in tasks}
    submissions = [
        (key, sub) for key, sub in all_submissions.items()
        if sub.get("task_id") in task_ids_for_clinic
    ]
    # Pending first, so the clinician sees what needs attention immediately.
    submissions.sort(key=lambda item: item[1].get("review_status") != "Pending")

    announcements = Message.get_announcements(clinic_id)

    return render_template(
        "clinician_dashboard.html",
        name=session["name"],
        clinic=clinic_record,
        clinic_id=clinic_id,
        tasks=tasks,
        submissions=submissions,
        announcements=announcements,
    )


# ----------------------------------------------------------------------
# A. HEALTH TASK CREATION & ASSIGNMENT
# ----------------------------------------------------------------------

@app.route("/create_task", methods=["GET", "POST"])
def create_task():
    """
    Lets a clinician create a health task and assign it to one of
    their registered patients. GET shows the form; POST creates it.
    """
    if not login_required() or session.get("role") != "clinician":
        flash("You must be logged in as a clinician to create tasks.")
        return redirect(url_for("index"))

    clinic_id, clinic_record = Clinic.get_clinic_for_clinician(session["user_id"])
    if clinic_id is None:
        flash("No clinic is associated with your account.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        patient_id = request.form["patient_id"]

        # Access control: only allow assigning to a patient who is
        # actually registered under THIS clinic.
        if not Clinic.patient_belongs_to_clinic(patient_id, clinic_id):
            flash("That patient is not registered under your clinic.")
            return redirect(url_for("create_task"))

        title = request.form["title"]
        description = request.form["description"]
        due_date = request.form["due_date"]

        # required_fields is optional — a clinician can leave it blank
        # for tasks that don't need automated completeness checking
        # (e.g. a PDF-only submission).
        raw_fields = request.form.get("required_fields", "")
        required_fields = [f.strip() for f in raw_fields.split(",") if f.strip()]

        # Generate a simple unique task ID.
        with open(os.path.join("data", "health_tasks.json"), "r") as f:
            existing = json.load(f)
        task_id = f"task_{len(existing) + 1:04d}"

        new_task = HealthTask(
            task_id=task_id,
            title=title,
            description=description,
            due_date=due_date,
            clinic_id=clinic_id,
            assigned_patient_id=patient_id,
            required_fields=required_fields,
        )
        new_task.save()

        flash(f"Task '{title}' created and assigned.")
        return redirect(url_for("dashboard"))

    # GET: show the form with the clinic's registered patients to choose from.
    return render_template("create_task.html", patients=clinic_record["patient_ids"])


# ----------------------------------------------------------------------
# B. SUBMISSION REVIEW WORKFLOW
# ----------------------------------------------------------------------

VALID_OUTCOMES = ("Pending", "Reviewed - Normal", "Needs Follow-up", "Escalated")


@app.route("/review_submission/<submission_key>", methods=["GET", "POST"])
def review_submission(submission_key):
    """
    Lets a clinician record a categorical review outcome (never a
    numeric grade — this is health data) plus optional notes for one
    patient submission. submission_key is "patientID_taskID".
    """
    if not login_required() or session.get("role") != "clinician":
        flash("You must be logged in as a clinician to review submissions.")
        return redirect(url_for("index"))

    clinic_id, _ = Clinic.get_clinic_for_clinician(session["user_id"])

    with open(os.path.join("data", "task_submissions.json"), "r") as f:
        all_submissions = json.load(f)
    submission = all_submissions.get(submission_key)

    if submission is None:
        flash("That submission could not be found.")
        return redirect(url_for("dashboard"))

    # Access control: the submission's task must belong to this clinic.
    with open(os.path.join("data", "health_tasks.json"), "r") as f:
        all_tasks = json.load(f)
    task_record = all_tasks.get(submission["task_id"])
    if task_record is None or task_record["clinic_id"] != clinic_id:
        flash("That submission does not belong to your clinic.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        outcome = request.form["outcome"]
        notes = request.form.get("notes", "")

        if outcome not in VALID_OUTCOMES:
            flash("Invalid review outcome selected.")
            return redirect(url_for("review_submission", submission_key=submission_key))

        with open(os.path.join("data", "task_submissions.json"), "r+") as f:
            data = json.load(f)
            data[submission_key]["review_status"] = outcome
            data[submission_key]["review_notes"] = notes
            data[submission_key]["reviewer_id"] = session["user_id"]
            data[submission_key]["reviewed_at"] = datetime.now().isoformat()
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

        # Notify the patient in-app via a message so they see the
        # outcome without needing email set up to test the workflow.
        notification = Message(
            sender_id=session["user_id"],
            recipient_id=submission["patient_id"],
            content=f"Your submission for '{task_record['title']}' has been "
                     f"reviewed: {outcome}." + (f" Note: {notes}" if notes else ""),
        )
        notification.save()
        patient_record = User.load(submission["patient_id"])
        if patient_record and patient_record.get("email"):
            notify_review_complete(patient_record["email"], task_record["title"], outcome, notes)

        flash(f"Review recorded: {outcome}.")
        return redirect(url_for("dashboard"))

    return render_template("review_submission.html", submission=submission,
                            task=task_record, submission_key=submission_key,
                            outcomes=VALID_OUTCOMES)


# ----------------------------------------------------------------------
# C. MESSAGING
# ----------------------------------------------------------------------

@app.route("/messages/<other_user_id>", methods=["GET", "POST"])
def messages_view(other_user_id):
    """
    Shows (and lets a user post to) a 1-to-1 conversation between the
    logged-in user and another user (patient<->clinician). Works for
    both roles since Message.get_conversation() only ever returns
    messages where the logged-in user is a real participant.
    """
    if not login_required():
        return redirect(url_for("index"))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            new_message = Message(
                sender_id=session["user_id"],
                recipient_id=other_user_id,
                content=content,
            )
            new_message.save()
        return redirect(url_for("messages_view", other_user_id=other_user_id))

    conversation = Message.get_conversation(session["user_id"], other_user_id)
    return render_template("messages.html", conversation=conversation,
                            other_user_id=other_user_id, my_id=session["user_id"])


# ----------------------------------------------------------------------
# E. CLINIC ANNOUNCEMENTS
# ----------------------------------------------------------------------

@app.route("/create_announcement", methods=["GET", "POST"])
def create_announcement():
    """
    Lets a clinician post a clinic-wide announcement, optionally
    marked urgent. Stored as a Message with is_announcement=True and
    recipient_id set to the clinic_id (not a single patient).
    """
    if not login_required() or session.get("role") != "clinician":
        flash("You must be logged in as a clinician to post announcements.")
        return redirect(url_for("index"))

    clinic_id, _ = Clinic.get_clinic_for_clinician(session["user_id"])
    if clinic_id is None:
        flash("No clinic is associated with your account.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        urgent = request.form.get("urgent") == "on"

        if not content:
            flash("Announcement text cannot be empty.")
            return redirect(url_for("create_announcement"))

        prefix = "[URGENT] " if urgent else ""
        announcement = Message(
            sender_id=session["user_id"],
            recipient_id=clinic_id,
            content=prefix + content,
            is_announcement=True,
        )
        announcement.save()

        flash("Announcement posted.")
        return redirect(url_for("dashboard"))

    return render_template("create_announcement.html")




if __name__ == "__main__":
    app.run(debug=True)
