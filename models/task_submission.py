"""
TaskSubmission model for ClinicCare-Lite.

Represents a file a patient uploads in response to a health task.
Tracks the clinician's review status and delegates all actual file
operations (validation, storage, renaming, versioning) to
utils/file_handler.py, keeping this file focused on the SUBMISSION
RECORD itself rather than filesystem details.

IMPORTANT SCOPE RULE: the "review outcome" here is an ADMINISTRATIVE
status assigned by a human clinician - Pending / Reviewed-Normal /
Needs Follow-up / Escalated. This code must never try to interpret
the medical meaning of what's inside the file. It only checks
structural things (is the file type allowed? is it empty? etc).

Owned by: Idirashe (Patient Services lead)
"""

import json
import os
from datetime import datetime

from utils.file_handler import save_submission_file, get_submission_file_path

SUBMISSIONS_FILE = os.path.join("data", "task_submissions.json")


class TaskSubmission:
    # Valid categorical review outcomes. Using a class-level tuple like
    # this means every part of the app references the SAME list instead
    # of typing the strings out repeatedly and risking a typo somewhere.
    REVIEW_STATUSES = ("Pending", "Reviewed - Normal", "Needs Follow-up", "Escalated")

    def __init__(self, patient_id, task_id, uploaded_file_path, clinic_id=None,
                 original_filename=None):
        """
        patient_id: who is submitting
        task_id: which task this answers
        uploaded_file_path: the TEMPORARY path of the file right after
                             upload, before we've moved/renamed it
        clinic_id: which clinic this submission belongs to - used to
                   build the clinic-specific storage directory
        original_filename: the file's original name (needed to check
                            its extension) - if not given, we fall back
                            to reading it from uploaded_file_path itself
        """
        self.patient_id = patient_id
        self.task_id = task_id
        self.uploaded_file_path = uploaded_file_path
        self.clinic_id = clinic_id
        self.original_filename = original_filename or os.path.basename(uploaded_file_path)
        self.final_file_path = None  # set once save_file() runs
        self.timestamp = datetime.now().isoformat()
        self.review_status = "Pending"
        self.reviewer_id = None
        self.review_notes = None
        self.notification_sent = False

    def save_file(self):
        """
        Validate and move the uploaded file into its permanent home
        via utils/file_handler.py, which handles extension/size
        validation, safe-filename checking, clinic+patient-specific
        directory placement, and duplicate/versioning logic.

        Raises ValueError (from file_handler) with a clear message if
        the file fails validation - the calling Flask route should
        catch this and show it to the user.
        """
        self.final_file_path = save_submission_file(
            temp_file_path=self.uploaded_file_path,
            original_filename=self.original_filename,
            clinic_id=self.clinic_id,
            patient_id=self.patient_id,
            task_id=self.task_id,
        )
        return self.final_file_path

    def save(self):
        """
        Save this submission's metadata into task_submissions.json.
        Uses patient_id + task_id as the combined key so each patient
        can only have one active submission per task (resubmission
        replaces the metadata here, while save_file() above handles
        keeping a version of the old file rather than deleting it).
        """
        with open(SUBMISSIONS_FILE, "r+") as f:
            data = json.load(f)
            key = f"{self.patient_id}_{self.task_id}"
            data[key] = {
                "patient_id": self.patient_id,
                "task_id": self.task_id,
                "clinic_id": self.clinic_id,
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


def check_form_completeness(file_path, required_fields, field_types=None):
    """
    Automated form-completeness check for .csv/.txt submissions.

    This is a STRUCTURAL check only - it looks at whether expected
    columns/fields exist, aren't empty, and (optionally) match a basic
    expected FORMAT. It must NEVER look at what a value actually means
    medically. For example it's fine to say "the date field is not a
    valid date" - it is NOT okay to say anything like "this
    blood-pressure reading is dangerous".

    file_path: path to the uploaded .csv file
    required_fields: list of column names we expect, e.g. ["date", "reading"]
    field_types: optional dict mapping a column name to a simple type
                 check, e.g. {"date": "date"}. Currently supports:
                 "date" - must parse as YYYY-MM-DD
                 "number" - must parse as a float
                 Any field not listed here only gets the
                 presence/emptiness checks above, no format check.

    Returns a list of plain-language problem strings. Empty list means
    the form looks structurally complete.
    """
    import csv

    field_types = field_types or {}
    problems = []

    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        # Check every required column is present at all.
        for field in required_fields:
            if field not in headers:
                problems.append(f"The '{field}' column is missing.")

        # Check no row has an empty cell in a required column, and
        # check basic FORMAT (never meaning) where a type is specified.
        row_count = 0
        for row_number, row in enumerate(reader, start=1):
            row_count += 1
            for field in required_fields:
                if field not in row:
                    continue
                value = row[field]
                if value is None or value.strip() == "":
                    problems.append(f"Row {row_number} is missing a value for '{field}'.")
                    continue  # no point format-checking an empty value

                expected_type = field_types.get(field)
                if expected_type == "date":
                    try:
                        datetime.strptime(value.strip(), "%Y-%m-%d")
                    except ValueError:
                        problems.append(
                            f"Row {row_number}: '{field}' should be a date in "
                            f"YYYY-MM-DD format."
                        )
                elif expected_type == "number":
                    try:
                        float(value.strip())
                    except ValueError:
                        problems.append(
                            f"Row {row_number}: '{field}' should be a number."
                        )

        # A file with only a header row (no actual data) technically
        # has the right columns but contains nothing to review - flag
        # this separately so it isn't silently treated as "complete".
        if row_count == 0:
            problems.append("The file has no data rows - only a header row was found.")

    return problems