"""
TaskSubmission model for ClinicCare-Lite.

Represents a file a patient uploads in response to a health task.
Handles: validating the file type, renaming/storing it safely, and
tracking the clinician's review status.

IMPORTANT SCOPE RULE: the "review outcome" here is an ADMINISTRATIVE
status assigned by a human clinician - Pending / Reviewed-Normal /
Needs Follow-up / Escalated. This code must never try to interpret
the medical meaning of what's inside the file. It only checks
structural things (is the file type allowed? is it empty? etc).

Owned by: Idirashe (Patient Services lead)
"""

import os
import shutil
import json
from datetime import datetime

SUBMISSIONS_FILE = os.path.join("data", "task_submissions.json")
SUBMISSIONS_DIR = "submissions"

# Only these file types are ever accepted, per the project spec.
ALLOWED_EXTENSIONS = (".txt", ".csv", ".pdf")

# Simple size cap (5 MB) to stop someone uploading something huge.
# Adjust if your test files legitimately need to be bigger.
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class TaskSubmission:
    # Valid categorical review outcomes. Using a class-level tuple like
    # this means every part of the app references the SAME list instead
    # of typing the strings out repeatedly and risking a typo somewhere.
    REVIEW_STATUSES = ("Pending", "Reviewed - Normal", "Needs Follow-up", "Escalated")

    def __init__(self, patient_id, task_id, uploaded_file_path):
        """
        patient_id: who is submitting
        task_id: which task this answers
        uploaded_file_path: the TEMPORARY path of the file right after
                             upload, before we've moved/renamed it
        """
        self.patient_id = patient_id
        self.task_id = task_id
        self.uploaded_file_path = uploaded_file_path
        self.final_file_path = None  # set once save_file() runs
        self.timestamp = datetime.now().isoformat()
        self.review_status = "Pending"
        self.reviewer_id = None
        self.review_notes = None
        self.notification_sent = False

    def validate_file(self):
        """
        Check the file extension is one of the allowed types AND that
        the file isn't over the size limit. Returns (True, "") if okay,
        or (False, "reason") if not - so the caller can show a helpful
        error message to the patient instead of a generic failure.
        """
        _, ext = os.path.splitext(self.uploaded_file_path)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' is not allowed. Use .txt, .csv, or .pdf."

        size = os.path.getsize(self.uploaded_file_path)
        if size > MAX_FILE_SIZE_BYTES:
            return False, "File is too large. Maximum size is 5 MB."

        return True, ""

    def save_file(self):
        """
        Move the uploaded file into its permanent home:
        submissions/<clinic_or_patient_id>/<patientID_taskID.ext>

        We rename it systematically so filenames never collide and so
        it's obvious at a glance which patient/task a file belongs to,
        matching the spec's "patientID_taskID.extension" naming rule.
        """
        is_valid, error_message = self.validate_file()
        if not is_valid:
            # Raising an exception here means the calling Flask route
            # can catch it and show the error_message to the user,
            # rather than the app crashing.
            raise ValueError(error_message)

        _, ext = os.path.splitext(self.uploaded_file_path)
        new_filename = f"{self.patient_id}_{self.task_id}{ext}"

        # Store files inside a folder named after the patient, so each
        # patient's submissions are grouped together and easy to find.
        dest_dir = os.path.join(SUBMISSIONS_DIR, self.patient_id)
        os.makedirs(dest_dir, exist_ok=True)

        dest_path = os.path.join(dest_dir, new_filename)
        shutil.copy(self.uploaded_file_path, dest_path)

        self.final_file_path = dest_path
        return dest_path

    def save(self):
        """
        Save this submission's metadata into task_submissions.json.
        Uses patient_id + task_id as the combined key so each patient
        can only have one active submission per task (unless you build
        resubmission logic on top of this later).
        """
        with open(SUBMISSIONS_FILE, "r+") as f:
            data = json.load(f)
            key = f"{self.patient_id}_{self.task_id}"
            data[key] = {
                "patient_id": self.patient_id,
                "task_id": self.task_id,
                "file_path": self.final_file_path,
                "timestamp": self.timestamp,
                "review_status": self.review_status,
                "reviewer_id": self.reviewer_id,
                "review_notes": self.review_notes,
                "notification_sent": self.notification_sent,
            }
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    def set_review(self, reviewer_id, status, notes=""):
        """
        Called by the clinician-review route. Updates this submission's
        review fields IN MEMORY - you still need to call .save() after
        this to persist the change to disk.

        status MUST be one of REVIEW_STATUSES - this stops a typo or a
        rogue value turning into a numeric "score", which the spec
        explicitly forbids.
        """
        if status not in TaskSubmission.REVIEW_STATUSES:
            raise ValueError(f"'{status}' is not a valid review status.")
        self.reviewer_id = reviewer_id
        self.review_status = status
        self.review_notes = notes


def check_form_completeness(file_path, required_fields):
    """
    Automated form-completeness check for .csv/.txt submissions.

    This is a STRUCTURAL check only - it looks at whether expected
    columns/fields exist and aren't empty. It must NEVER look at the
    actual values and comment on what they mean medically. For example
    it's fine to say "the date column is missing" - it is NOT okay to
    say anything like "this reading looks concerning".

    file_path: path to the uploaded .csv file
    required_fields: list of column names we expect, e.g. ["date", "reading"]

    Returns a list of plain-language problem strings. Empty list means
    the form looks structurally complete.
    """
    import csv

    problems = []

    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Check every required column is present at all.
        for field in required_fields:
            if field not in headers:
                problems.append(f"The '{field}' column is missing.")

        # Check no row has an empty cell in a required column, and
        # keep count of how many data rows exist at all.
        row_count = 0
        for row_number, row in enumerate(reader, start=1):
            row_count += 1
            for field in required_fields:
                if field in row and (row[field] is None or row[field].strip() == ""):
                    problems.append(f"Row {row_number} is missing a value for '{field}'.")

        # A file with only a header row (no actual data) technically
        # has the right columns but contains nothing to review - flag
        # this separately so it isn't silently treated as "complete".
        if row_count == 0:
            problems.append("The file has no data rows - only a header row was found.")

    return problems
