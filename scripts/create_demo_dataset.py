"""
Demo dataset generator for ClinicCare-Lite - Section E (Member 4).

WHAT THIS DOES:
Wipes data/ and submissions/ and rebuilds them with a small, realistic
set of demo accounts and records, so anyone on the team (or a marker/
demonstrator) can start the app and immediately see a working system
instead of an empty one.

HOW TO RUN THIS:
From the project's root folder (where app.py lives):
    python scripts/create_demo_dataset.py

WARNING: this OVERWRITES whatever is currently in data/ and
submissions/. Don't run this if you have real work saved there that
you want to keep - back it up first (or just use run_tests.py's
approach as a model if you want a non-destructive version later).

DEMO ACCOUNTS CREATED (for the final presentation / markers):
    Clinician - ID: 12350000   Password: ClinicPass1!
    Patient   - ID: 12342024   Password: PatientPass1!
"""

import json
import os
import sys
import bcrypt
from datetime import datetime, timedelta

# Allow running this script from the scripts/ folder while still
# writing to data/ at the PROJECT ROOT, not inside scripts/ itself.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)


def hash_password(plain_password):
    """Same hashing approach as models/user.py, kept identical on
    purpose so these accounts can log in through the real /login route."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def build_demo_data():
    today = datetime.now().date()

    users = {
        "12350000": {
            "name": "Dr. Ama Owusu", "email": "ama.owusu@democlinic.test",
            "password_hash": hash_password("ClinicPass1!"),
            "role": "clinician", "theme": "dark",
        },
        "12342024": {
            "name": "Kwame Asante", "email": "kwame.asante@example.test",
            "password_hash": hash_password("PatientPass1!"),
            "role": "patient", "theme": "colourful",
        },
        "12352024": {
            "name": "Efua Boateng", "email": "efua.boateng@example.test",
            "password_hash": hash_password("PatientPass1!"),
            "role": "patient", "theme": "dark",
        },
    }

    clinics = {
        "clinic_01": {
            "name": "Ashesi Community Clinic",
            "clinician_id": "12350000",
            "patient_ids": ["12342024", "12352024"],
        }
    }

    tasks = {
        "task_0001": {
            "title": "Weekly blood pressure log",
            "description": "Log your blood pressure readings daily using the attached form.",
            "due_date": str(today - timedelta(days=2)),  # deliberately overdue, for the demo
            "clinic_id": "clinic_01", "assigned_patient_id": "12342024",
            "attachment_path": None,
            "required_fields": ["date", "reading"],
            "field_types": {"date": "date", "reading": "number"},
            "created_at": (datetime.now() - timedelta(days=10)).isoformat(),
        },
        "task_0002": {
            "title": "Medication adherence check-in",
            "description": "Confirm you've taken your prescribed medication this week.",
            "due_date": str(today + timedelta(days=5)),
            "clinic_id": "clinic_01", "assigned_patient_id": "12342024",
            "attachment_path": None, "required_fields": [], "field_types": {},
            "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
        },
        "task_0003": {
            "title": "Weekly blood pressure log",
            "description": "Log your blood pressure readings daily using the attached form.",
            "due_date": str(today + timedelta(days=2)),
            "clinic_id": "clinic_01", "assigned_patient_id": "12352024",
            "attachment_path": None,
            "required_fields": ["date", "reading"],
            "field_types": {"date": "date", "reading": "number"},
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
        },
    }

    # One already-reviewed submission, so the demo shows every status
    # colour (Pending/Overdue/Reviewed) rather than just empty tasks.
    submissions = {
        "12352024_task_0003": {
            "patient_id": "12352024", "task_id": "task_0003", "clinic_id": "clinic_01",
            "file_path": None,  # no real file needed for a demo record
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "review_status": "Reviewed - Normal",
            "reviewer_id": "12350000",
            "review_notes": "Looks complete, thank you.",
            "notification_sent": True,
        }
    }

    appointments = {
        "appt_0001": {
            "patient_id": "12342024", "clinic_id": "clinic_01",
            "date": str(today + timedelta(days=4)), "time": "10:00",
            "reason": "Follow-up check-in", "clinician_id": "12350000",
            "attended": None, "created_at": datetime.now().isoformat(),
        },
        "appt_0002": {
            "patient_id": "12342024", "clinic_id": "clinic_01",
            "date": str(today - timedelta(days=14)), "time": "09:30",
            "reason": "Routine visit", "clinician_id": "12350000",
            "attended": True, "created_at": datetime.now().isoformat(),
        },
        "appt_0003": {
            "patient_id": "12352024", "clinic_id": "clinic_01",
            "date": str(today - timedelta(days=7)), "time": "13:00",
            "reason": "Routine visit", "clinician_id": "12350000",
            "attended": False, "created_at": datetime.now().isoformat(),  # a no-show, for the analytics demo
        },
    }

    messages = [
        {
            "sender_id": "clinic_01", "recipient_id": "clinic_01",
            "content": "Welcome to ClinicCare-Lite! Reminder: this channel is not "
                       "monitored 24/7 - for emergencies, call your clinic directly.",
            "is_announcement": True,
            "timestamp": (datetime.now() - timedelta(days=1)).isoformat(),
            "read": False,
        }
    ]

    return {
        "users.json": users,
        "clinics.json": clinics,
        "health_tasks.json": tasks,
        "task_submissions.json": submissions,
        "appointments.json": appointments,
        "messages.json": messages,
    }


def main():
    os.makedirs("data", exist_ok=True)
    os.makedirs("submissions", exist_ok=True)
    os.makedirs("temp_uploads", exist_ok=True)

    demo_data = build_demo_data()
    for filename, content in demo_data.items():
        path = os.path.join("data", filename)
        with open(path, "w") as f:
            json.dump(content, f, indent=4)
        print(f"  wrote {path}")

    print("\nDemo dataset created successfully.")
    print("Demo accounts:")
    print("  Clinician - ID: 12350000   Password: ClinicPass1!")
    print("  Patient   - ID: 12342024   Password: PatientPass1!")
    print("  Patient   - ID: 12352024   Password: PatientPass1!")
    print("\nStart the app with: python app.py")


if __name__ == "__main__":
    main()
