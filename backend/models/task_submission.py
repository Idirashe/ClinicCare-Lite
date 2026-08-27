"""
backend/models/task_submission.py

TaskSubmission model — a patient's uploaded response to a HealthTask.
Stored in task_submissions.json.

Only .txt, .csv, .pdf files are allowed (Section 4 of spec).
Files are renamed to patientID_taskID.extension and stored under
submissions/<clinicID>/<patientID>/.

Review outcome is categorical, NOT a numeric score:
"Reviewed - Normal" / "Needs Follow-up" / "Escalated"

TODO (Member 2 / Patient Services lead): wire this up to the actual
file upload route and the automated form-completeness check (Section 7).
"""
import os
import uuid
from datetime import datetime
from backend.storage import load_json, save_json

SUBMISSIONS_FILE = "task_submissions.json"
ALLOWED_EXTENSIONS = {".txt", ".csv", ".pdf"}
SUBMISSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "submissions")

VALID_OUTCOMES = {"Pending", "Reviewed - Normal", "Needs Follow-up", "Escalated"}


class TaskSubmission:
    def __init__(self, submission_id, patient_id, task_id, clinic_id,
                 file_path, timestamp=None, review_status="Pending", notes=""):
        self.submission_id = submission_id
        self.patient_id = patient_id
        self.task_id = task_id
        self.clinic_id = clinic_id
        self.file_path = file_path
        self.timestamp = timestamp or datetime.now().isoformat()
        self.review_status = review_status
        self.notes = notes

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def is_allowed_file(filename):
        ext = os.path.splitext(filename)[1].lower()
        return ext in ALLOWED_EXTENSIONS

    @staticmethod
    def build_filename(patient_id, task_id, original_filename):
        ext = os.path.splitext(original_filename)[1].lower()
        return f"{patient_id}_{task_id}{ext}"

    @staticmethod
    def create(patient_id, task_id, clinic_id, file_path):
        submissions = load_json(SUBMISSIONS_FILE)
        submission = TaskSubmission(
            submission_id=str(uuid.uuid4())[:8],
            patient_id=patient_id,
            task_id=task_id,
            clinic_id=clinic_id,
            file_path=file_path,
        )
        submissions.append(submission.to_dict())
        save_json(SUBMISSIONS_FILE, submissions)
        return submission

    @staticmethod
    def review(submission_id, outcome, notes=""):
        """Clinician reviews a submission with a categorical outcome (not a numeric score)."""
        if outcome not in VALID_OUTCOMES:
            return None, f"Invalid outcome. Must be one of {VALID_OUTCOMES}."
        submissions = load_json(SUBMISSIONS_FILE)
        for s in submissions:
            if s["submission_id"] == submission_id:
                s["review_status"] = outcome
                s["notes"] = notes
        save_json(SUBMISSIONS_FILE, submissions)
        return True, None

    @staticmethod
    def find_by_patient(patient_id):
        submissions = load_json(SUBMISSIONS_FILE)
        return [s for s in submissions if s["patient_id"] == patient_id]

    @staticmethod
    def find_by_clinic(clinic_id):
        submissions = load_json(SUBMISSIONS_FILE)
        return [s for s in submissions if s["clinic_id"] == clinic_id]
