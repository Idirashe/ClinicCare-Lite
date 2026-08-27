"""
backend/models/clinic.py

Clinic model — groups a clinician with their registered patients.
Stored in clinics.json: clinic ID, name, assigned clinician ID,
registered patient IDs.

TODO (Member 1 / whoever owns clinic setup): flesh out clinic
creation/management routes once the admin flow is decided.
"""
from backend.storage import load_json, save_json

CLINICS_FILE = "clinics.json"


class Clinic:
    def __init__(self, clinic_id, name, clinician_id, patient_ids=None):
        self.clinic_id = clinic_id
        self.name = name
        self.clinician_id = clinician_id
        self.patient_ids = patient_ids or []

    def to_dict(self):
        return {
            "clinic_id": self.clinic_id,
            "name": self.name,
            "clinician_id": self.clinician_id,
            "patient_ids": self.patient_ids,
        }

    @staticmethod
    def create(clinic_id, name, clinician_id):
        clinics = load_json(CLINICS_FILE)
        if any(c["clinic_id"] == clinic_id for c in clinics):
            return None, "A clinic with this ID already exists."
        clinic = Clinic(clinic_id, name, clinician_id)
        clinics.append(clinic.to_dict())
        save_json(CLINICS_FILE, clinics)
        return clinic, None

    @staticmethod
    def find_by_id(clinic_id):
        clinics = load_json(CLINICS_FILE)
        record = next((c for c in clinics if c["clinic_id"] == clinic_id), None)
        return Clinic(**record) if record else None

    @staticmethod
    def add_patient(clinic_id, patient_id):
        clinics = load_json(CLINICS_FILE)
        for c in clinics:
            if c["clinic_id"] == clinic_id and patient_id not in c["patient_ids"]:
                c["patient_ids"].append(patient_id)
        save_json(CLINICS_FILE, clinics)
