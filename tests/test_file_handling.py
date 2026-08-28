"""
Tests: file upload validation and JSON persistence - Section D
(Member 4), matching the spec's required test list:
    - Unsupported file types
    - Oversized files
    - Empty or malformed JSON files
    - JSON save-and-load round trips (including checking that
      rewritten JSON files are properly truncated)
"""

import unittest
import os
import json
import shutil

from tests.test_data_reset import reset_to_empty_data, safe_rmtree
from utils.file_handler import (
    validate_file, is_safe_filename, save_submission_file,
)
from models.user import User


class TestFileTypeValidation(unittest.TestCase):
    """Unsupported file types"""

    def setUp(self):
        reset_to_empty_data()
        os.makedirs("temp_uploads", exist_ok=True)

    def tearDown(self):
        # Using safe_rmtree() instead of a raw shutil.rmtree() call -
        # see its docstring in tests/test_data_reset.py for why this
        # matters on Windows/OneDrive.
        safe_rmtree("temp_uploads")

    def _make_temp_file(self, filename, content=b"sample content"):
        path = os.path.join("temp_uploads", filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_allowed_csv_passes(self):
        path = self._make_temp_file("data.csv")
        is_valid, message = validate_file(path, "data.csv")
        self.assertTrue(is_valid)

    def test_allowed_txt_passes(self):
        path = self._make_temp_file("log.txt")
        is_valid, message = validate_file(path, "log.txt")
        self.assertTrue(is_valid)

    def test_allowed_pdf_passes(self):
        path = self._make_temp_file("report.pdf")
        is_valid, message = validate_file(path, "report.pdf")
        self.assertTrue(is_valid)

    def test_unsupported_exe_rejected(self):
        path = self._make_temp_file("virus.exe")
        is_valid, message = validate_file(path, "virus.exe")
        self.assertFalse(is_valid)
        self.assertIn("not allowed", message)

    def test_unsupported_docx_rejected(self):
        path = self._make_temp_file("notes.docx")
        is_valid, message = validate_file(path, "notes.docx")
        self.assertFalse(is_valid)

    def test_no_extension_rejected(self):
        path = self._make_temp_file("mysteryfile")
        is_valid, message = validate_file(path, "mysteryfile")
        self.assertFalse(is_valid)


class TestOversizedFiles(unittest.TestCase):
    """Oversized files"""

    def setUp(self):
        reset_to_empty_data()
        os.makedirs("temp_uploads", exist_ok=True)

    def tearDown(self):
        safe_rmtree("temp_uploads")

    def test_file_under_limit_passes(self):
        path = os.path.join("temp_uploads", "small.csv")
        with open(path, "wb") as f:
            f.write(b"x" * 1024)  # 1 KB - well under the 5MB limit
        is_valid, message = validate_file(path, "small.csv")
        self.assertTrue(is_valid)

    def test_file_over_limit_rejected(self):
        path = os.path.join("temp_uploads", "huge.csv")
        # Write slightly over 5MB (5 * 1024 * 1024 bytes) to trigger
        # the MAX_FILE_SIZE_BYTES check.
        with open(path, "wb") as f:
            f.write(b"x" * (5 * 1024 * 1024 + 100))
        is_valid, message = validate_file(path, "huge.csv")
        self.assertFalse(is_valid)
        self.assertIn("too large", message)


class TestPathTraversalProtection(unittest.TestCase):
    """
    Not explicitly named in the spec's test list, but directly required
    by the "safe file-path construction" deliverable Idi built - tests
    that a malicious filename can't escape the intended folder.
    """

    def test_forward_slash_rejected(self):
        self.assertFalse(is_safe_filename("../../etc/passwd"))

    def test_backslash_rejected(self):
        # Explicitly testing the Windows-style separator too, since
        # file_handler.py's own comment explains os.path.basename()
        # alone wouldn't catch this on a Linux server.
        self.assertFalse(is_safe_filename("..\\..\\Windows\\System32\\x"))

    def test_plain_filename_accepted(self):
        self.assertTrue(is_safe_filename("bp_log.csv"))


class TestJsonRoundTrips(unittest.TestCase):
    """
    JSON save-and-load round trips, including checking that rewritten
    JSON files are properly truncated (the spec explicitly calls this
    out, and user.py's own comments flag it as a real bug class).
    """

    def setUp(self):
        reset_to_empty_data()

    def test_user_save_then_load_round_trip(self):
        # Save a user, then load it back and check every field matches.
        user = User("12342024", "Round Trip Patient", "rt@example.com",
                    "GoodPass1!", "patient")
        user.save()

        loaded = User.load("12342024")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["name"], "Round Trip Patient")
        self.assertEqual(loaded["email"], "rt@example.com")
        self.assertEqual(loaded["role"], "patient")

    def test_rewritten_json_file_has_no_leftover_bytes(self):
        """
        THE SPECIFIC BUG THIS GUARDS AGAINST: opening a file in "r+"
        mode and writing LESS data than was there before leaves old
        bytes trailing at the end, corrupting the JSON. We test this
        by saving a user with a LONG name first (a big file), then
        saving a DIFFERENT user with a SHORT name (a smaller file),
        and confirming the file is still valid, parseable JSON with
        no leftover characters after it.
        """
        long_name_user = User("12342024", "A" * 500, "a@example.com",
                              "GoodPass1!", "patient")
        long_name_user.save()

        short_name_user = User("12342024", "B", "b@example.com",
                               "GoodPass1!", "patient")
        short_name_user.save()

        # If truncate() wasn't called correctly, this file would have
        # trailing garbage after the final "}" and json.load would
        # raise a JSONDecodeError right here.
        with open(os.path.join("data", "users.json"), "r") as f:
            data = json.load(f)  # would raise if corrupted

        self.assertEqual(data["12342024"]["name"], "B")

    def test_empty_dict_json_file_loads_cleanly(self):
        # An empty {} file (the starting state for every JSON store)
        # must load as an empty dict, not raise an error.
        with open(os.path.join("data", "users.json"), "r") as f:
            data = json.load(f)
        self.assertEqual(data, {})


class TestMalformedJson(unittest.TestCase):
    """Empty or malformed JSON files"""

    def setUp(self):
        reset_to_empty_data()

    def test_completely_empty_file_raises_decode_error(self):
        # A truly EMPTY file (0 bytes, not even "{}") is invalid JSON
        # and should raise, not silently return something misleading.
        with open(os.path.join("data", "users.json"), "w") as f:
            f.write("")  # zero bytes - not valid JSON

        with self.assertRaises(json.JSONDecodeError):
            with open(os.path.join("data", "users.json"), "r") as f:
                json.load(f)

    def test_truncated_json_raises_decode_error(self):
        # Simulates a crash mid-write: the file cuts off partway
        # through an object, e.g. "{"12342024": {"name": "A"".
        with open(os.path.join("data", "users.json"), "w") as f:
            f.write('{"12342024": {"name": "A"')

        with self.assertRaises(json.JSONDecodeError):
            with open(os.path.join("data", "users.json"), "r") as f:
                json.load(f)


if __name__ == "__main__":
    unittest.main()
