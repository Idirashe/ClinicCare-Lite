"""
backend/storage.py

Shared JSON storage helper. All model classes (User, Clinic, HealthTask,
TaskSubmission, Message) read and write through this module, so there's
one single, consistent way of reading/writing our JSON data files.

Per the project spec, ClinicCare-Lite uses JSON files instead of a
database (users.json, health_tasks.json, task_submissions.json,
messages.json, clinics.json).
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _path(filename):
    return os.path.join(DATA_DIR, filename)


def load_json(filename):
    """Load a JSON file from backend/data/. Returns [] if it doesn't exist yet."""
    path = _path(filename)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def save_json(filename, data):
    """Save data (a list of dicts) to a JSON file in backend/data/."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _path(filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
