"""
Unit tests for utils/file_handler.py.

Covers the previously-missing Section C requirements:
- Safe file-path construction (path traversal rejected)
- Patient- and clinic-specific directories
- Duplicate-file handling / versioning
"""

import unittest
import os
import shutil

from utils.file_handler import (
    is_safe_filename,
    validate_file,
    build_submission_path,
    save_submission_file,
)

TEST_TEMP_DIR = "test_temp_files"
TEST_SUBMISSIONS_DIR = "submissions"


class TestFileHandler(unittest.TestCase):

    def setUp(self):
        os.makedirs(TEST_TEMP_DIR, exist_ok=True)

    def test_safe_filename_accepts_normal_names(self):
        self.assertTrue(is_safe_filename("report.csv"))
        self.assertTrue(is_safe_filename("blood_pressure_log.txt"))

    def test_safe_filename_rejects_path_traversal(self):
        self.assertFalse(is_safe_filename("../../etc/passwd"))
        self.assertFalse(is_safe_filename("..\\..\\Windows\\System32\\evil.txt"))

    def test_build_submission_path_is_clinic_and_patient_specific(self):
        path = build_submission_path("clinic_A", "12342024", "12342024_task1.csv")
        self.assertIn("clinic_A", path)
        self.assertIn("12342024", path)

    def test_build_submission_path_handles_missing_clinic_id(self):
        path = build_submission_path(None, "12342024", "file.csv")
        self.assertNotIn("None", path)
        self.assertIn("unassigned_clinic", path)

    def test_validate_file_rejects_disallowed_extension(self):
        temp_path = os.path.join(TEST_TEMP_DIR, "virus.exe")
        with open(temp_path, "w") as f:
            f.write("fake content")

        is_valid, message = validate_file(temp_path, "virus.exe")
        self.assertFalse(is_valid)
        self.assertIn("not allowed", message)

    def test_validate_file_accepts_csv(self):
        temp_path = os.path.join(TEST_TEMP_DIR, "data.csv")
        with open(temp_path, "w") as f:
            f.write("date,reading\n2026-01-01,120/80\n")

        is_valid, message = validate_file(temp_path, "data.csv")
        self.assertTrue(is_valid)

    def test_duplicate_submission_archives_old_file_not_deletes_it(self):
        first_temp = os.path.join(TEST_TEMP_DIR, "first.csv")
        with open(first_temp, "w") as f:
            f.write("date,reading\n2026-01-01,first-version\n")

        path1 = save_submission_file(first_temp, "first.csv", "clinic_X", "77772024", "task_dup")
        self.assertTrue(os.path.exists(path1))

        second_temp = os.path.join(TEST_TEMP_DIR, "second.csv")
        with open(second_temp, "w") as f:
            f.write("date,reading\n2026-01-02,second-version\n")

        path2 = save_submission_file(second_temp, "second.csv", "clinic_X", "77772024", "task_dup")

        with open(path2) as f:
            content = f.read()
        self.assertIn("second-version", content)

        submission_dir = os.path.dirname(path2)
        archived_files = [
            f for f in os.listdir(submission_dir) if "replaced" in f
        ]
        self.assertEqual(len(archived_files), 1)
        with open(os.path.join(submission_dir, archived_files[0])) as f:
            archived_content = f.read()
        self.assertIn("first-version", archived_content)

    def tearDown(self):
        if os.path.exists(TEST_TEMP_DIR):
            shutil.rmtree(TEST_TEMP_DIR)
        for folder in ["clinic_A", "clinic_X", "unassigned_clinic"]:
            path = os.path.join(TEST_SUBMISSIONS_DIR, folder)
            if os.path.exists(path):
                shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()