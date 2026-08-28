"""
Operational analytics for ClinicCare-Lite - Section C (Member 4).

WHAT THIS FILE DOES:
Builds clinician-facing, CLINIC-WIDE statistics like "how many tasks
are overdue this month" or "average time to review a submission".

HARD PRIVACY RULE (from the spec):
"Operational visualisations should not reveal one patient's
confidential information to another patient." That means:
- Every function here is CLINIC-scoped (needs a clinic_id), never
  patient-scoped in a way that singles someone out by name.
- We only ever return AGGREGATE numbers (counts, rates, averages) -
  never a table of "patient X submitted late 3 times" that a clinician
  could screenshot and show another patient.
- This whole module is meant to be called from CLINICIAN-facing
  routes only. It is never wired into the patient dashboard.

Owned by: Naomi (Member 4 - UI, Analytics, Testing and Deployment Lead)
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

from models.health_task import HealthTask

TASKS_FILE = os.path.join("data", "health_tasks.json")
SUBMISSIONS_FILE = os.path.join("data", "task_submissions.json")
APPOINTMENTS_FILE = os.path.join("data", "appointments.json")


def _load_json(path):
    """Small shared helper so every function below doesn't repeat the
    same open/json.load lines."""
    with open(path, "r") as f:
        return json.load(f)


def get_clinic_tasks_and_submissions(clinic_id):
    """
    Internal helper: pull every task belonging to this clinic, paired
    with its submission if one exists.

    Returns a list of dicts:
    {
        "task_id": ..., "due_date": ..., "created_at": ...,
        "submission": <submission dict or None>
    }
    """
    all_tasks = _load_json(TASKS_FILE)
    all_submissions = _load_json(SUBMISSIONS_FILE)

    rows = []
    for task_id, task in all_tasks.items():
        if task.get("clinic_id") != clinic_id:
            continue

        # A submission's key is "<patient_id>_<task_id>" (see
        # TaskSubmission.save()), so we rebuild that same key here.
        submission_key = f"{task['assigned_patient_id']}_{task_id}"
        submission = all_submissions.get(submission_key)

        rows.append({
            "task_id": task_id,
            "due_date": task["due_date"],
            "created_at": task.get("created_at"),
            "submission": submission,
        })
    return rows


def task_completion_rate(clinic_id):
    """
    'Task-completion rate' metric from the spec.
    Returns the percentage of this clinic's tasks that have ANY
    submission recorded (on time or late), rounded to 1 decimal place.
    """
    rows = get_clinic_tasks_and_submissions(clinic_id)
    if not rows:
        return 0.0
    completed = sum(1 for r in rows if r["submission"] is not None)
    return round((completed / len(rows)) * 100, 1)


def pending_reviews_count(clinic_id):
    """
    'Number of pending reviews' metric.
    Counts submissions that exist but haven't been given a final
    clinician decision yet - i.e. still "Pending" or bounced back as
    "Needs Follow-up" (which still needs another look eventually).
    """
    rows = get_clinic_tasks_and_submissions(clinic_id)
    count = 0
    for r in rows:
        sub = r["submission"]
        if sub is not None and sub["review_status"] in ("Pending", "Needs Follow-up"):
            count += 1
    return count


def average_review_turnaround(clinic_id):
    """
    'Average review turnaround time' metric, in hours.

    NOTE ON DATA MODEL: task_submission.py's current JSON schema only
    stores ONE timestamp (submission time) and does not yet record a
    separate "reviewed_at" timestamp. Turnaround = review_time - submit
    time, so this can't be computed until that field exists.

    This function is written to work AS SOON AS a "reviewed_at" field
    is added to the submission record (a one-line addition to
    set_review() in task_submission.py) - it deliberately does not
    guess or fake a number in the meantime, since a wrong analytics
    figure is worse than an honest "not available yet".

    Returns a float (hours) if enough data exists, or None if the data
    needed isn't being recorded yet.
    """
    rows = get_clinic_tasks_and_submissions(clinic_id)
    turnaround_hours = []

    for r in rows:
        sub = r["submission"]
        if sub is None:
            continue
        # Only counts once the submission has actually been reviewed
        # (not still "Pending") AND has a reviewed_at timestamp on it.
        if sub["review_status"] == "Pending":
            continue
        reviewed_at = sub.get("reviewed_at")
        if not reviewed_at:
            continue
        submitted = datetime.fromisoformat(sub["timestamp"])
        reviewed = datetime.fromisoformat(reviewed_at)
        hours = (reviewed - submitted).total_seconds() / 3600
        turnaround_hours.append(hours)

    if not turnaround_hours:
        return None
    return round(sum(turnaround_hours) / len(turnaround_hours), 1)


def submission_count_by_task(clinic_id):
    """
    'Submission count by task' metric.
    Returns a dict of {task_id: number_of_submissions} - either 0 or 1
    per task under the CURRENT one-submission-per-task-per-patient
    model, but written generically in case group/multi-patient tasks
    are added later.
    """
    rows = get_clinic_tasks_and_submissions(clinic_id)
    counts = {}
    for r in rows:
        counts[r["task_id"]] = 1 if r["submission"] is not None else 0
    return counts


def overdue_task_count(clinic_id):
    """
    'Overdue-task count' metric.
    Counts tasks with NO submission yet where the due date has passed.
    Reuses HealthTask logic indirectly by comparing dates the same way
    HealthTask.is_overdue() does, so the definition of "overdue" stays
    consistent across the whole app.
    """
    rows = get_clinic_tasks_and_submissions(clinic_id)
    today = datetime.now().date()
    count = 0
    for r in rows:
        if r["submission"] is not None:
            continue
        due = datetime.strptime(r["due_date"], "%Y-%m-%d").date()
        if today > due:
            count += 1
    return count


def monthly_appointment_volume(clinic_id, months_back=6):
    """
    'Monthly appointment volume' metric.
    Returns an ORDERED list of (month_label, appointment_count) tuples
    for the last `months_back` months, e.g.:
        [("2026-03", 12), ("2026-04", 9), ...]
    Ordered oldest-to-newest so a chart drawn from this reads left-to-right
    correctly on a timeline.
    """
    all_appointments = _load_json(APPOINTMENTS_FILE)

    # Build the list of month labels we want to report on, oldest first.
    today = datetime.now().replace(day=1)
    month_buckets = []
    for i in range(months_back - 1, -1, -1):
        # Subtracting whole months safely: go back i months from today
        # by subtracting (i * ~30 days) then formatting to "YYYY-MM" -
        # since we only need the LABEL, not an exact calendar day, this
        # simple approach is accurate enough for a monthly bucket.
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_buckets.append(f"{year:04d}-{month:02d}")

    counts = defaultdict(int)
    for appt in all_appointments.values():
        if appt.get("clinic_id") != clinic_id:
            continue
        month_label = appt["date"][:7]  # "YYYY-MM-DD" -> "YYYY-MM"
        counts[month_label] += 1

    return [(label, counts.get(label, 0)) for label in month_buckets]


def completion_rate_by_clinic(all_clinic_ids):
    """
    'Completion rate by clinic' metric - a cross-clinic comparison for
    an admin/multi-clinic view. Takes a LIST of clinic_ids and returns
    {clinic_id: completion_rate} so several clinics can be compared
    side by side on one chart.

    This is the ONE metric in this module that compares across clinics
    - note it compares CLINICS, never individual PATIENTS, so it does
    not violate the patient-privacy rule above.
    """
    return {
        clinic_id: task_completion_rate(clinic_id)
        for clinic_id in all_clinic_ids
    }


def appointment_no_show_rate_by_week(clinic_id, weeks_back=8):
    """
    'Appointment no-show rate by week' metric - the FIRST bullet point
    the spec lists under Section C, so it gets its own clearly-named
    function even though it's conceptually similar to the attendance
    stats in engagement_tracker.py (that file computes PER-PATIENT
    private stats; this one aggregates per-CLINIC for the clinician view).

    Returns an ordered list of (week_label, no_show_rate_percent) tuples,
    oldest week first. A week with no MARKED appointments (nobody has
    recorded attendance yet) reports a rate of None rather than 0, so
    a chart doesn't misleadingly show a "perfect" week that's actually
    just missing data.
    """
    all_appointments = _load_json(APPOINTMENTS_FILE)

    today = datetime.now().date()
    # Build 8 weekly buckets ending with the current week, oldest first.
    week_buckets = []
    for i in range(weeks_back - 1, -1, -1):
        week_start = today - timedelta(days=today.weekday(), weeks=i)
        week_buckets.append(week_start)

    marked_per_week = defaultdict(int)
    no_shows_per_week = defaultdict(int)

    for appt in all_appointments.values():
        if appt.get("clinic_id") != clinic_id:
            continue
        if appt.get("attended") is None:
            continue  # not yet marked - excluded from the rate entirely

        appt_date = datetime.strptime(appt["date"], "%Y-%m-%d").date()
        appt_week_start = appt_date - timedelta(days=appt_date.weekday())

        # Only count it if it falls inside one of our tracked weeks.
        if appt_week_start in week_buckets:
            marked_per_week[appt_week_start] += 1
            if appt["attended"] is False:
                no_shows_per_week[appt_week_start] += 1

    results = []
    for week_start in week_buckets:
        label = week_start.strftime("%Y-%m-%d")
        marked = marked_per_week.get(week_start, 0)
        if marked == 0:
            results.append((label, None))
        else:
            rate = round((no_shows_per_week.get(week_start, 0) / marked) * 100, 1)
            results.append((label, rate))
    return results


def build_analytics_summary(clinic_id):
    """
    Convenience function: gather EVERY metric above into one dict, so
    the analytics route can call just this one function instead of
    calling each metric function individually. This is the same
    "gather everything the template needs in one place" pattern
    Idi's utils/patient_dashboard.py already uses.
    """
    return {
        "task_completion_rate": task_completion_rate(clinic_id),
        "pending_reviews": pending_reviews_count(clinic_id),
        "average_review_turnaround_hours": average_review_turnaround(clinic_id),
        "submission_count_by_task": submission_count_by_task(clinic_id),
        "overdue_task_count": overdue_task_count(clinic_id),
        "monthly_appointment_volume": monthly_appointment_volume(clinic_id),
        "no_show_rate_by_week": appointment_no_show_rate_by_week(clinic_id),
    }
