"""
backend/auth/routes.py

Authentication routes: register and login.
This is a working starting point — Member 1's job for Task C is to
extend this with session management, logout, and password reset if needed.
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from backend.models.user import User

auth_bp = Blueprint("auth", __name__, template_folder="../../frontend/templates")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")  # "clinician" or "patient"

        user, error = User.register(user_id, name, email, password, role)
        if error:
            flash(error, "error")
            return render_template("register.html")

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form.get("user_id", "").strip()
        password = request.form.get("password", "")

        user, error = User.login(user_id, password)
        if error:
            flash(error, "error")
            return render_template("login.html")

        # Store minimal info in the session — never the password/hash.
        session["user_id"] = user.user_id
        session["role"] = user.role
        session["theme"] = user.theme

        if user.role == "clinician":
            return redirect(url_for("routes.clinician_dashboard"))
        return redirect(url_for("routes.patient_dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
