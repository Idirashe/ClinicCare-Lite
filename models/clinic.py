"""
Clinic model for ClinicCare-Lite.

A Clinic groups one clinician with the patients registered under them.
Used mainly to enforce access control - a clinician should only ever
see patients who belong to THEIR clinic, never another clinician's
patients.

Owned by: Louange (Architecture & Security lead) - shared with Member 3
"""

import json
import os

CLINICS_FILE = os.path.join("data", "clinics.json")


class Clinic:
    def __init__(self, clinic_id, name, clinician_id, patient_ids=None):
        self.clinic_id = clinic_id
        self.name = name
        self.clinician_id = clinician_id
        # patient_ids is a list of patient user_ids registered here.
        # Default to an empty list rather than None so callers can
        # immediately do things like `clinic.patient_ids.append(...)`.
        self.patient_ids = patient_ids or []

    def save(self):
        with open(CLINICS_FILE, "r+") as f:
            data = json.load(f)
            data[self.clinic_id] = {
                "name": self.name,
                "clinician_id": self.clinician_id,
                "patient_ids": self.patient_ids,
            }
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    @staticmethod
    def patient_belongs_to_clinic(patient_id, clinic_id):
        """
        Access-control helper: returns True only if this patient is
        registered under this specific clinic. Call this before letting
        a clinician view/review a patient's submission, so a clinician
        can never pull up a patient from a different clinic by guessing
        an ID in the URL.
        """
        with open(CLINICS_FILE, "r") as f:
            data = json.load(f)
        clinic = data.get(clinic_id)
        if clinic is None:
            return False
        return patient_id in clinic["patient_ids"]

    @staticmethod
    def get_clinic_for_clinician(clinician_id):
        """
        Find which clinic a given clinician runs. Returns (clinic_id,
        clinic_dict) or (None, None) if not found.
        """
        with open(CLINICS_FILE, "r") as f:
            data = json.load(f)
        for clinic_id, clinic in data.items():
            if clinic["clinician_id"] == clinician_id:
                return clinic_id, clinic
        return None, None
