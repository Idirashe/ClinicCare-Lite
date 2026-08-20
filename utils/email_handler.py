"""
Email notification helper for ClinicCare-Lite.

Sends emails for: submission confirmations, review outcomes,
appointment reminders, and clinic announcements.

SECURITY NOTE: email credentials come from environment variables
(loaded via python-dotenv from a .env file), never hardcoded here.
This means the real password never ends up in the git history.

Owned by: Jolene (Clinician Services & Notification lead)
"""

import smtplib
import os
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load variables from the .env file into the environment when this
# module is first imported.
load_dotenv()

SENDER_EMAIL = os.environ.get("EMAIL_ADDRESS")
SENDER_PASSWORD = os.environ.get("EMAIL_PASSWORD")


def send_email(recipient_email, subject, body):
    """
    Send a plain-text email. Returns True if it sent successfully,
    False if something went wrong (so the caller can decide whether to
    retry, log it, or just continue without crashing the app - email
    failures should never take down the whole application).
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        # Missing config is a setup problem, not a runtime crash -
        # print a clear warning instead of raising an exception.
        print("WARNING: EMAIL_ADDRESS / EMAIL_PASSWORD not set in .env - email not sent.")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient_email

    try:
        # "with" automatically closes the connection when we're done,
        # even if something goes wrong partway through.
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # upgrade the connection to an encrypted one
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as error:
        # Catching the general Exception here is intentional - lots of
        # things can go wrong with email (network down, wrong password,
        # server rejects us) and we want the app to keep running
        # regardless of which one happens. We just log it.
        print(f"Failed to send email to {recipient_email}: {error}")
        return False


def notify_submission_received(clinician_email, patient_name, task_title):
    """Convenience wrapper: email a clinician when a patient submits a task."""
    subject = f"New submission from {patient_name}"
    body = (
        f"{patient_name} has submitted their response for the task "
        f"'{task_title}'. Please log in to ClinicCare-Lite to review it."
    )
    return send_email(clinician_email, subject, body)


def notify_review_complete(patient_email, task_title, outcome, notes):
    """Convenience wrapper: email a patient once their submission is reviewed."""
    subject = f"Your submission for '{task_title}' has been reviewed"
    body = (
        f"Outcome: {outcome}\n\n"
        f"Notes from your clinician: {notes or '(no additional notes)'}\n\n"
        f"Log in to ClinicCare-Lite to see the full details."
    )
    return send_email(patient_email, subject, body)
