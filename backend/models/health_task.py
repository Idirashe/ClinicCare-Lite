"""
backend/models/health_task.py

HealthTask model — a task a clinician assigns to a patient
(e.g. "log your blood pressure daily for a week").
Stored in health_tasks.json.

TODO (Member 3 / Clinician Services lead): build the "create task" form
and the clinician dashboard task list on top of this.
"""
import uuid
from datetime import datetime
from backend.storage import load_json, save_json

TASKS_FILE = "health_tasks.json"


class HealthTask:
    def __init__(self, task_id, title, description, due_date, clinic_id,
                 patient_id, attachment_path=None, created_at=None):
        self.task_id = task_id
        self.title = title
        self.description = description
        self.due_date = due_date
        self.clinic_id = clinic_id
        self.patient_id = patient_id
        self.attachment_path = attachment_path
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def create(title, description, due_date, clinic_id, patient_id, attachment_path=None):
        tasks = load_json(TASKS_FILE)
        task = HealthTask(
            task_id=str(uuid.uuid4())[:8],
            title=title,
            description=description,
            due_date=due_date,
            clinic_id=clinic_id,
            patient_id=patient_id,
            attachment_path=attachment_path,
        )
        tasks.append(task.to_dict())
        save_json(TASKS_FILE, tasks)
        return task

    @staticmethod
    def find_by_patient(patient_id):
        tasks = load_json(TASKS_FILE)
        return [t for t in tasks if t["patient_id"] == patient_id]

    @staticmethod
    def find_by_clinic(clinic_id):
        tasks = load_json(TASKS_FILE)
        return [t for t in tasks if t["clinic_id"] == clinic_id]
