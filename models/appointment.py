"""
Appointment model for ClinicCare-Lite.

Represents a scheduled appointment or reminder between a patient and
their clinic. Kept intentionally simple - this is administrative
scheduling data only (date, time, reason label), never clinical
content or notes about what will be discussed.

Owned by: Idirashe (Member 2 - Patient Services, File Handling and
Engagement Lead) - part of the "upcoming appointments or reminders"
requirement in the patient dashboard spec.
"""

import json
import os
from datetime import datetime

APPOINTMENTS_FILE = os.path.join("data", "appointments.json")


class Appointment:
    def __init__(self, appointment_id, patient_id, clinic_id, date, time,
                 reason, clinician_id=None):
        """
        appointment_id: unique string, e.g. "appt_0001"
        patient_id: which patient this is for
        clinic_id: which clinic it belongs to
        date: "YYYY-MM-DD" string
        time: "HH:MM" 24-hour string, e.g. "14:30"
        reason: short administrative label, e.g. "Follow-up check-in"
                - NOT a place for clinical details, just a scheduling
                  label so the patient knows what the appointment is
                  broadly about.
        clinician_id: optional, which clinician it's with
        """
        self.appointment_id = appointment_id
        self.patient_id = patient_id
        self.clinic_id = clinic_id
        self.date = date
        self.time = time
        self.reason = reason
        self.clinician_id = clinician_id
        self.created_at = datetime.now().isoformat()

    def is_upcoming(self):
        """
        Returns True if this appointment's date/time is still in the
        future (or right now). Past appointments are excluded from
        the "upcoming" list shown on the dashboard.
        """
        appt_datetime = datetime.strptime(
            f"{self.date} {self.time}", "%Y-%m-%d %H:%M"
        )
        return appt_datetime >= datetime.now()

    def save(self):
        """
        Save this appointment into data/appointments.json.
        Same read-modify-write-with-truncate pattern used everywhere
        else in the project, to avoid the JSON corruption bug covered
        in models/user.py's comments.
        """
        with open(APPOINTMENTS_FILE, "r+") as f:
            data = json.load(f)
            data[self.appointment_id] = {
                "patient_id": self.patient_id,
                "clinic_id": self.clinic_id,
                "date": self.date,
                "time": self.time,
                "reason": self.reason,
                "clinician_id": self.clinician_id,
                "created_at": self.created_at,
            }
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    @staticmethod
    def get_upcoming_for_patient(patient_id):
        """
        Return every future appointment for this patient, sorted so
        the SOONEST appointment appears first - that's what a patient
        actually wants to see at the top of their dashboard.

        Returns a list of (appointment_id, appointment_dict) tuples.
        """
        with open(APPOINTMENTS_FILE, "r") as f:
            data = json.load(f)

        now = datetime.now()
        upcoming = []
        for appt_id, appt in data.items():
            if appt["patient_id"] != patient_id:
                continue
            appt_datetime = datetime.strptime(
                f"{appt['date']} {appt['time']}", "%Y-%m-%d %H:%M"
            )
            if appt_datetime >= now:
                upcoming.append((appt_id, appt, appt_datetime))

        # Sort by the actual datetime (soonest first), then drop the
        # sort key before returning since callers don't need it.
        upcoming.sort(key=lambda item: item[2])
        return [(appt_id, appt) for appt_id, appt, _ in upcoming]
