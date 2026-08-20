"""
ClinicCare-Lite - main Flask application.

This is the entry point that ties all the models and routes together.
Run it with: python app.py

SCOPE REMINDER: this app is administrative and communication only.
No route here may interpret medical meaning, diagnose, or recommend
treatment - only structural checks (is a field filled in? is the file
type allowed?) are permitted.
"""

from flask import Flask, render_template, request, session, redirect, url_for, flash
import os
from dotenv import load_dotenv

from models.user import User
from models.health_task import HealthTask
from models.task_submission import TaskSubmission
from models.clinic import Clinic
from patient_routes_snippet import build_patient_dashboard_data
import json

# Load SECRET_KEY and email credentials from .env before anything else runs.
load_dotenv()

app = Flask(__name__)
# The secret key is what Flask uses to cryptographically sign session
# cookies, so users can't tamper with their own session data (e.g. to
# fake being a different user_id). Falling back to "dev-key" only
# matters for quick local testing - always set a real SECRET_KEY in
# .env before deploying or demoing.
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")


# ----------------------------------------------------------------------
# A tiny helper used by several routes below: confirms someone is
# logged in before letting them see a protected page. Not using Flask
# extensions like flask-login yet to keep this scaffold dependency-light
# - feel free to swap in a proper decorator library later if useful.
# ----------------------------------------------------------------------
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

        # Validate ID format for the chosen role.
        if not User.validate_id(user_id, role):
            flash("Invalid ID format for the selected role.")
            return render_template("register.html")

        # Validate password strength.
        if not User.validate_password(password):
            flash("Password must be at least 8 characters and include "
                  "an uppercase letter, a lowercase letter, a digit, "
                  "and a special character (!@#$%^&*).")
            return render_template("register.html")

        # Reject duplicate IDs - two users can't share the same ID.
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
        # Store the essentials in the session - never store the password
        # or password hash in the session, only what's needed to look
        # things up later.
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
# DASHBOARD ROUTING - sends each role to their own dashboard template.
# The actual dashboard content/routes are built out by Idirashe
# (patient) and Jolene (clinician) in their own route files/blueprints.
# ----------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("index"))

    if session["role"] == "clinician":
        return render_template("clinician_dashboard.html", name=session["name"])

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
# PATIENT ROUTES (Done by Idirashe- Member 2: Patient Services, File Handling
# and Engagement Lead)
# ----------------------------------------------------------------------

@app.route("/submit_task/<task_id>", methods=["POST"])
def submit_task(task_id):
    """
    Handle a patient uploading a file for a specific assigned task.

    SECURITY: only allows submission if the task actually belongs to
    the logged-in patient - this stops anyone from submitting a file
    to a task_id that isn't theirs, even if they guess or edit the URL.

    RESUBMISSION RULE: a patient may resubmit while their submission is
    still "Pending" (not yet looked at) or "Needs Follow-up" (clinician
    asked for more/updated info). Once a clinician has recorded
    "Reviewed - Normal" or "Escalated", that's treated as a completed
    decision and resubmission is blocked - overwriting a finalised
    review silently would undermine the audit trail.
    """
    if "user_id" not in session or session["role"] != "patient":
        return redirect(url_for("index"))

    patient_id = session["user_id"]

    # --- Authorisation check: does this task actually belong to this
    # patient? Without this, anyone logged in as a patient could POST
    # to /submit_task/<any_task_id> and submit a file against a task
    # that was never assigned to them. ---
    task_record = None
    with open(os.path.join("data", "health_tasks.json"), "r") as f:
        all_tasks = json.load(f)
    if task_id in all_tasks:
        task_record = all_tasks[task_id]

    if task_record is None or task_record["assigned_patient_id"] != patient_id:
        # Deliberately vague message - we don't want to confirm to an
        # attacker whether a given task_id exists at all.
        flash("That task could not be found or is not assigned to you.")
        return redirect(url_for("dashboard"))

    # --- Resubmission rule check ---
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
        submission = TaskSubmission(patient_id, task_id, temp_path)
        submission.save_file()
        submission.save()
        flash("Your file was submitted successfully.")
    except ValueError as error:
        flash(str(error))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return redirect(url_for("dashboard"))


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
# Everyone: add your own routes below this line, or better, split them
# into Flask Blueprints in separate files once this file starts getting
# long. 
# ----------------------------------------------------------------------


if __name__ == "__main__":
    # debug=True gives helpful error pages during development - turn
    # this off before any real demonstration or deployment.
    app.run(debug=True)
