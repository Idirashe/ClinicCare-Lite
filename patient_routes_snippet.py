"""
Patient dashboard route for ClinicCare-Lite.

This is Idirashe's core file for Member 2's responsibilities:
"Design the patient workflow. Define submission and engagement data."

Covers the full patient dashboard feature list from the project brief:
- View assigned health tasks, descriptions, due dates
- See pending / submitted / reviewed / overdue status
- View submission timestamps and clinician review outcomes/notes
- Access personal messages
- View upcoming appointments/reminders
- Switch between colourful and dark themes

SCOPE REMINDER: nothing here interprets medical meaning. Status is
purely administrative (has a file been uploaded? has a clinician
looked at it?) - never a judgement about the patient's health.
"""

from datetime import datetime
from models.health_task import HealthTask
from models.task_submission import TaskSubmission
from models.message import Message
from models.appointment import Appointment
from engagement_tracker import get_engagement_summary
import json
import os

SUBMISSIONS_FILE = os.path.join("data", "task_submissions.json")


def get_task_status(task_id, patient_id, due_date_str):
    """
    Work out the administrative status of a single task for a patient:
    "Pending"    - no submission yet, not overdue
    "Overdue"    - no submission yet, AND past the due date
    "Submitted"  - a submission exists but hasn't been reviewed yet
    Otherwise    - whatever the clinician's review_status says
                   (Reviewed - Normal / Needs Follow-up / Escalated)

    This is a pure status label - it never says anything about what
    the patient's actual health data means.
    """
    with open(SUBMISSIONS_FILE, "r") as f:
        submissions = json.load(f)

    key = f"{patient_id}_{task_id}"
    submission = submissions.get(key)

    if submission is None:
        # No file uploaded yet - check whether the due date has passed.
        due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        if today > due:
            return "Overdue", None
        return "Pending", None

    # A submission exists - report its current review status and
    # timestamp so the template can show both.
    return submission["review_status"], submission


def build_patient_dashboard_data(patient_id):
    """
    Gather everything the patient dashboard template needs into one
    dictionary. Keeping this logic in one function (rather than
    scattering queries across the template) makes it much easier to
    test and to reuse if we ever add an API endpoint later.
    """
    tasks = HealthTask.get_all_for_patient(patient_id)

    # Build a rich list combining each task with its live status,
    # since the raw HealthTask data alone doesn't know about
    # submissions or review outcomes.
    task_rows = []
    for task_id, task in tasks:
        status, submission = get_task_status(task_id, patient_id, task["due_date"])
        task_rows.append({
            "task_id": task_id,
            "title": task["title"],
            "description": task["description"],
            "due_date": task["due_date"],
            "status": status,
            # These stay None until a submission exists - the template
            # checks for None before trying to display them.
            "submitted_at": submission["timestamp"] if submission else None,
            "review_notes": submission["review_notes"] if submission else None,
        })

    # Sort so overdue and pending tasks surface at the top - patients
    # should see what needs action before what's already handled.
    status_priority = {"Overdue": 0, "Pending": 1, "Needs Follow-up": 2,
                        "Escalated": 2, "Reviewed - Normal": 3}
    task_rows.sort(key=lambda t: status_priority.get(t["status"], 4))

    # Pull personal messages - Message.get_conversation needs the OTHER
    # party's ID, so in a real build this would loop over the patient's
    # assigned clinician(s). For now this is left as a hook for Jolene's
    # messaging feature to plug into once clinician IDs are wired up.
    messages = []

    # Private engagement stats - personal to this patient only, never
    # compared against anyone else. See engagement_tracker.py for the
    # calculation logic and the hard rules around what this may/may
    # not measure.
    engagement = get_engagement_summary(patient_id)

    # Upcoming appointments/reminders - soonest first. This satisfies
    # the "View upcoming appointments or reminders" requirement in the
    # patient dashboard spec.
    upcoming_appointments_raw = Appointment.get_upcoming_for_patient(patient_id)
    upcoming_appointments = [
        {
            "appointment_id": appt_id,
            "date": appt["date"],
            "time": appt["time"],
            "reason": appt["reason"],
        }
        for appt_id, appt in upcoming_appointments_raw
    ]

    return {
        "tasks": task_rows,
        "messages": messages,
        "overdue_count": sum(1 for t in task_rows if t["status"] == "Overdue"),
        "pending_count": sum(1 for t in task_rows if t["status"] == "Pending"),
        "engagement": engagement,
        "upcoming_appointments": upcoming_appointments,
    }
