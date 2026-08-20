"""
Engagement tracker for ClinicCare-Lite.

Calculates PRIVATE, PERSONAL statistics about a single patient's own
task-completion habits over time - e.g. "you completed 8 out of 10
tasks on time this month" or "your current on-time streak is 4 tasks".

HARD RULES (from the project spec, do not violate these):
1. This is NEVER shown to any other patient, and NEVER used to compare
   one patient against another. No leaderboards, no rankings, no
   "you're in the top 10%" type messaging.
2. This only measures ADMINISTRATIVE behaviour (did they submit on
   time?) - it never scores or comments on the CONTENT of what they
   submitted. A patient who submits messy data on time still counts
   as "on time" - we are not judging quality, only punctuality.
3. Stats are informational, not motivational manipulation - avoid
   guilt-inducing language like "you're falling behind" or shame-based
   framing. Neutral, factual tone only.

Owned by: Idirashe (Member 2 - Patient Services, File Handling and
Engagement Lead)
"""

import json
import os
from datetime import datetime, timedelta

TASKS_FILE = os.path.join("data", "health_tasks.json")
SUBMISSIONS_FILE = os.path.join("data", "task_submissions.json")


def _load_patient_task_history(patient_id):
    """
    Internal helper: pull every task assigned to this patient, paired
    with its submission (if any exists), sorted oldest to newest.

    Returns a list of dicts like:
    {
        "task_id": "...",
        "due_date": "2026-01-15",
        "submitted_at": "2026-01-14T10:00:00" or None,
        "was_on_time": True / False / None (None = not submitted yet)
    }
    """
    with open(TASKS_FILE, "r") as f:
        all_tasks = json.load(f)
    with open(SUBMISSIONS_FILE, "r") as f:
        all_submissions = json.load(f)

    history = []
    for task_id, task in all_tasks.items():
        if task["assigned_patient_id"] != patient_id:
            continue

        submission_key = f"{patient_id}_{task_id}"
        submission = all_submissions.get(submission_key)

        entry = {
            "task_id": task_id,
            "due_date": task["due_date"],
            "submitted_at": None,
            "was_on_time": None,
        }

        if submission is not None:
            entry["submitted_at"] = submission["timestamp"]
            # Compare the submission date against the due date to work
            # out punctuality. Both are compared as dates (not exact
            # times) since "on time" should mean "the same day or
            # earlier", not down-to-the-second precision.
            due_date = datetime.strptime(task["due_date"], "%Y-%m-%d").date()
            submitted_date = datetime.fromisoformat(submission["timestamp"]).date()
            entry["was_on_time"] = submitted_date <= due_date

        history.append(entry)

    # Sort oldest-first by due date so streak calculations below read
    # the timeline in the correct chronological order.
    history.sort(key=lambda e: e["due_date"])
    return history


def get_engagement_summary(patient_id):
    """
    Build the full private engagement summary for one patient.

    Returns a dictionary with:
    - total_tasks: how many tasks have ever been assigned to them
    - completed_tasks: how many have been submitted (on time or late)
    - on_time_tasks: how many were submitted by their due date
    - completion_rate: percentage of assigned tasks that were submitted
    - on_time_rate: percentage of assigned tasks submitted ON TIME
    - current_on_time_streak: consecutive most-recent tasks submitted
                                on time (breaks on a late or missed one)
    - last_30_days_completed: tasks submitted in the last 30 days

    All figures describe ONLY this one patient - this function takes a
    single patient_id and has no way to compare against anyone else.
    """
    history = _load_patient_task_history(patient_id)

    total_tasks = len(history)
    completed = [e for e in history if e["submitted_at"] is not None]
    on_time = [e for e in completed if e["was_on_time"]]

    completion_rate = round((len(completed) / total_tasks) * 100, 1) if total_tasks else 0.0
    on_time_rate = round((len(on_time) / total_tasks) * 100, 1) if total_tasks else 0.0

    # Streak: walk backwards from the most recent task. Stop counting
    # the moment we hit a task that was either not submitted or late.
    streak = 0
    for entry in reversed(history):
        if entry["was_on_time"] is True:
            streak += 1
        else:
            break

    # Count submissions within the last 30 days, useful for a simple
    # "recent activity" figure on the dashboard.
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_completed = [
        e for e in completed
        if datetime.fromisoformat(e["submitted_at"]) >= thirty_days_ago
    ]

    return {
        "total_tasks": total_tasks,
        "completed_tasks": len(completed),
        "on_time_tasks": len(on_time),
        "completion_rate": completion_rate,
        "on_time_rate": on_time_rate,
        "current_on_time_streak": streak,
        "last_30_days_completed": len(recent_completed),
    }
