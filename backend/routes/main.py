"""
backend/routes/main.py

Core app routes — dashboards for each role.
These are placeholders: Member 2 (patient features) and Member 3
(clinician features) should build out the real dashboard logic here.
"""
from flask import Blueprint, render_template, session, redirect, url_for

routes_bp = Blueprint("routes", __name__, template_folder="../../frontend/templates")


def login_required(role=None):
    """Basic access-control check. TODO: turn into a proper decorator
    once Member 1 finalizes the auth/session approach (Task D)."""
    if "user_id" not in session:
        return False
    if role and session.get("role") != role:
        return False
    return True


@routes_bp.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    if session["role"] == "clinician":
        return redirect(url_for("routes.clinician_dashboard"))
    return redirect(url_for("routes.patient_dashboard"))


@routes_bp.route("/clinician/dashboard")
def clinician_dashboard():
    if not login_required(role="clinician"):
        return redirect(url_for("auth.login"))
    # TODO (Member 3): pull real health tasks / submissions here
    return render_template("clinician_dashboard.html")


@routes_bp.route("/patient/dashboard")
def patient_dashboard():
    if not login_required(role="patient"):
        return redirect(url_for("auth.login"))
    # TODO (Member 2): pull real assigned tasks / submission status here
    return render_template("patient_dashboard.html")
