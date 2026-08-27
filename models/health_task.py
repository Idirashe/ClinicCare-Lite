"""
HealthTask model for ClinicCare-Lite.

A "health task" is something a clinician assigns to a patient, e.g.
"log your blood pressure daily for a week". It is NOT a diagnosis or
treatment plan - just an administrative assignment with a due date.

Owned by: Jolene (Clinician Services lead)
"""

import json
import os
from datetime import datetime

TASKS_FILE = os.path.join("data", "health_tasks.json")


class HealthTask:
       
    def __init__(self, task_id, title, description, due_date, clinic_id,
                 assigned_patient_id, attachment_path=None,
                 required_fields=None, field_types=None):
        """
        task_id: unique string ID, e.g. "task_0001"
        title: short name, e.g. "Weekly blood pressure log"
        description: instructions for the patient
        due_date: string in "YYYY-MM-DD" format
        clinic_id: which clinic this task belongs to
        assigned_patient_id: the patient's user_id this task is for
        attachment_path: optional file the clinician attaches (e.g. a
                          template form) - None if there isn't one
        required_fields: optional list of column names expected in a
                          .csv/.txt submission for this task, e.g.
                          ["date", "reading"]. Leave as None/empty if
                          this task doesn't need completeness checking
                          (e.g. PDF-only tasks).
        field_types: optional dict mapping a column name to a basic
                      expected format - "date" or "number" - used only
                      for FORMAT checking, never for interpreting what
                      the value means. e.g. {"date": "date"}
        """
        self.task_id = task_id
        self.title = title
        self.description = description
        self.due_date = due_date
        self.clinic_id = clinic_id
        self.assigned_patient_id = assigned_patient_id
        self.attachment_path = attachment_path
        self.required_fields = required_fields or []
        self.field_types = field_types or {}
        # created_at records when the task was made, useful for sorting
        # and for the "monthly task volume" analytics metric later.
        self.created_at = datetime.now().isoformat() 

    def is_overdue(self):
        """
        Returns True if today's date is past the due date.
        Used to flag overdue tasks on both dashboards.
        """
        today = datetime.now().date()
        due = datetime.strptime(self.due_date, "%Y-%m-%d").date()
        return today > due

    def save(self):
        """
        Save this task into data/health_tasks.json.
        Same truncate-after-seek pattern as User.save() - see the long
        comment in models/user.py if you want the full explanation of
        why this matters.
        """

    
        with open(TASKS_FILE, "r+") as f:
            data = json.load(f)
            data[self.task_id] = {
                "title": self.title,
                "description": self.description,
                "due_date": self.due_date,
                "clinic_id": self.clinic_id,
                "assigned_patient_id": self.assigned_patient_id,
                "attachment_path": self.attachment_path,
                "required_fields": self.required_fields,
                "field_types": self.field_types,
                "created_at": self.created_at,
            }
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    @staticmethod
    def get_all_for_patient(patient_id):
        """
        Return a list of (task_id, task_dict) tuples for every task
        assigned to a given patient. Used to populate the patient
        dashboard's "assigned tasks" list.
        """
        with open(TASKS_FILE, "r") as f:
            data = json.load(f)
        return [
            (task_id, task)
            for task_id, task in data.items()
            if task["assigned_patient_id"] == patient_id
        ]

    @staticmethod
    def get_all_for_clinic(clinic_id):
        """
        Return every task belonging to a clinic, regardless of patient.
        Used by the clinician dashboard to show/filter all tasks they've
        created for their clinic.
        """
        with open(TASKS_FILE, "r") as f:
            data = json.load(f)
        return [
            (task_id, task)
            for task_id, task in data.items()
            if task["clinic_id"] == clinic_id
        ]
