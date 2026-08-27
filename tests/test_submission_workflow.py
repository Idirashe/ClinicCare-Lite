"""
Tests: task submission workflow - Section D (Member 4), matching the
spec's required test list:
    - Missing form fields
    - Duplicate submissions
    - Attempted access to another patient's records
"""

import unittest
import os
import csv

from tests.test_data_reset import reset_to_empty_data, safe_rmtree
from models.task_submission import check_form_completeness
from models.clinic import Clinic


class TestFormCompletenessChecking(unittest.TestCase):
    """
    Missing form fields - this is Idi's Section D
    (check_form_completeness), re-verified here as part of Member 4's
    overall QA coordination duty ("Coordinate: ... Regression testing").
    """

    def setUp(self):
        reset_to_empty_data()
        os.makedirs("temp_uploads", exist_ok=True)

    def _write_csv(self, filename, headers, rows):
        path = os.path.join("temp_uploads", filename)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
        return path

    def test_complete_form_has_no_problems(self):
        path = self._write_csv(
            "complete.csv", ["date", "reading"],
            [["2026-01-15", "120"], ["2026-01-16", "118"]]
        )
        problems = check_form_completeness(
            path, ["date", "reading"], {"date": "date", "reading": "number"}
        )
        self.assertEqual(problems, [])

    def test_missing_column_detected(self):
        # "reading" column doesn't exist at all in the header.
        path = self._write_csv("missing_col.csv", ["date"], [["2026-01-15"]])
        problems = check_form_completeness(path, ["date", "reading"])
        self.assertTrue(any("reading" in p and "missing" in p for p in problems))

    def test_empty_required_field_detected(self):
        # "reading" column exists but the value is blank on row 1.
        path = self._write_csv(
            "empty_field.csv", ["date", "reading"], [["2026-01-15", ""]]
        )
        problems = check_form_completeness(path, ["date", "reading"])
        self.assertTrue(any("Row 1" in p and "reading" in p for p in problems))

    def test_no_data_rows_detected(self):
        # Header-only file - technically has the right columns but
        # nothing to actually review.
        path = self._write_csv("header_only.csv", ["date", "reading"], [])
        problems = check_form_completeness(path, ["date", "reading"])
        self.assertTrue(any("no data rows" in p.lower() for p in problems))

    def test_bad_date_format_detected(self):
        path = self._write_csv(
            "bad_date.csv", ["date", "reading"], [["15/01/2026", "120"]]
        )
        problems = check_form_completeness(
            path, ["date", "reading"], {"date": "date"}
        )
        self.assertTrue(any("date" in p.lower() for p in problems))

    def test_bad_number_format_detected(self):
        path = self._write_csv(
            "bad_number.csv", ["date", "reading"], [["2026-01-15", "abc"]]
        )
        problems = check_form_completeness(
            path, ["date", "reading"], {"reading": "number"}
        )
        self.assertTrue(any("number" in p.lower() for p in problems))

    def test_never_reports_clinical_meaning(self):
        """
        CRITICAL SCOPE TEST: even with an extreme-looking numeric value,
        the completeness checker must ONLY validate that it parses as a
        number - it must never comment on whether the number itself is
        good, bad, dangerous, or any other clinical judgement.
        """
        path = self._write_csv(
            "extreme_value.csv", ["date", "reading"],
            [["2026-01-15", "999"]]
        )
        problems = check_form_completeness(
            path, ["date", "reading"], {"date": "date", "reading": "number"}
        )
        # A valid number, on a valid date -> no problems reported.
        self.assertEqual(problems, [])
        # Belt-and-suspenders: scan any problems that DO exist (in other
        # test cases this matters most) for clinical language.
        forbidden_words = ["dangerous", "high", "low", "abnormal", "unsafe"]
        for problem in problems:
            for word in forbidden_words:
                self.assertNotIn(word, problem.lower())


class TestDuplicateSubmissions(unittest.TestCase):
    """Duplicate submissions"""

    def setUp(self):
        reset_to_empty_data()
        os.makedirs("temp_uploads", exist_ok=True)

    def tearDown(self):
        # safe_rmtree() retries a few times before giving up, instead
        # of crashing on a transient Windows/OneDrive file lock - see
        # tests/test_data_reset.py for the full explanation.
        for folder in ("temp_uploads", "submissions"):
            safe_rmtree(folder)
            os.makedirs(folder, exist_ok=True)

    def test_resubmission_archives_previous_file_instead_of_deleting(self):
        """
        Confirms save_submission_file()'s versioning behaviour: submitting
        TWICE for the same patient+task doesn't destroy the first file,
        it archives it with a timestamp - satisfying "file replacement
        or versioning" from the file-handling deliverable.
        """
        from utils.file_handler import save_submission_file

        first_path = os.path.join("temp_uploads", "first.csv")
        with open(first_path, "w") as f:
            f.write("date,reading\n2026-01-15,120\n")

        final_path_1 = save_submission_file(
            temp_file_path=first_path, original_filename="first.csv",
            clinic_id="clinic_01", patient_id="12342024", task_id="task_0001",
        )
        self.assertTrue(os.path.exists(final_path_1))

        second_path = os.path.join("temp_uploads", "second.csv")
        with open(second_path, "w") as f:
            f.write("date,reading\n2026-01-16,118\n")

        final_path_2 = save_submission_file(
            temp_file_path=second_path, original_filename="second.csv",
            clinic_id="clinic_01", patient_id="12342024", task_id="task_0001",
        )

        # The "live" path is the same location both times...
        self.assertEqual(final_path_1, final_path_2)
        # ...but an archived copy of the FIRST submission should now
        # also exist somewhere in the same directory.
        directory = os.path.dirname(final_path_2)
        archived_files = [
            f for f in os.listdir(directory) if "_replaced_" in f
        ]
        self.assertEqual(len(archived_files), 1)


class TestCrossPatientAccess(unittest.TestCase):
    """Attempted access to another patient's records"""

    def setUp(self):
        reset_to_empty_data()
        clinic = Clinic("clinic_01", "Test Clinic", "12350000",
                        patient_ids=["12342024"])
        clinic.save()

    def test_patient_belongs_to_own_clinic(self):
        self.assertTrue(
            Clinic.patient_belongs_to_clinic("12342024", "clinic_01")
        )

    def test_patient_not_in_clinic_rejected(self):
        # "99992024" was never added to clinic_01's patient list.
        self.assertFalse(
            Clinic.patient_belongs_to_clinic("99992024", "clinic_01")
        )

    def test_unknown_clinic_id_rejected(self):
        # A clinic_id that doesn't exist at all should return False,
        # never raise an exception a route handler forgot to catch.
        self.assertFalse(
            Clinic.patient_belongs_to_clinic("12342024", "nonexistent_clinic")
        )


if __name__ == "__main__":
    unittest.main()
