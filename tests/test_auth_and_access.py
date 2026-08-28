"""
Tests: authentication, ID validation, password strength, and
unauthorised URL access - Section D (Member 4), matching the spec's
required test list:
    - Invalid clinician IDs
    - Invalid patient IDs
    - Weak passwords
    - Incorrect login credentials
    - Unauthorised URL access
"""

import unittest
from tests.test_data_reset import reset_to_empty_data
from models.user import User
from app import app


class TestIdValidation(unittest.TestCase):
    """Invalid clinician IDs / Invalid patient IDs"""

    def setUp(self):
        reset_to_empty_data()

    def test_valid_clinician_id_accepted(self):
        # Clinician IDs must be 8 digits ending in "0000".
        self.assertTrue(User.validate_id("12350000", "clinician"))

    def test_clinician_id_wrong_ending_rejected(self):
        # Doesn't end in 0000 - invalid clinician ID.
        self.assertFalse(User.validate_id("12351234", "clinician"))

    def test_clinician_id_wrong_length_rejected(self):
        # Only 7 digits, not 8 - invalid regardless of role.
        self.assertFalse(User.validate_id("1235000", "clinician"))

    def test_valid_patient_id_accepted(self):
        # Patient IDs end in a valid registration year, e.g. 2024.
        self.assertTrue(User.validate_id("12342024", "patient"))

    def test_patient_id_year_out_of_range_rejected(self):
        # 1999 is not inside the accepted 2022-2028 range.
        self.assertFalse(User.validate_id("12341999", "patient"))

    def test_patient_id_non_numeric_rejected(self):
        # Letters snuck into an ID should never pass the digit check.
        self.assertFalse(User.validate_id("1234abcd", "patient"))

    def test_id_with_correct_length_but_unknown_role_rejected(self):
        # An unrecognised role string should never validate, since we
        # don't know which rule (clinician vs patient) to apply.
        self.assertFalse(User.validate_id("12342024", "administrator"))


class TestPasswordStrength(unittest.TestCase):
    """Weak passwords"""

    def setUp(self):
        reset_to_empty_data()

    def test_strong_password_accepted(self):
        self.assertTrue(User.validate_password("Str0ng!Pass"))

    def test_too_short_rejected(self):
        self.assertFalse(User.validate_password("Sh0rt!"))

    def test_missing_uppercase_rejected(self):
        self.assertFalse(User.validate_password("weakpass1!"))

    def test_missing_lowercase_rejected(self):
        self.assertFalse(User.validate_password("WEAKPASS1!"))

    def test_missing_digit_rejected(self):
        self.assertFalse(User.validate_password("WeakPass!"))

    def test_missing_special_character_rejected(self):
        self.assertFalse(User.validate_password("WeakPass1"))

    def test_empty_password_rejected(self):
        self.assertFalse(User.validate_password(""))


class TestLoginCredentials(unittest.TestCase):
    """Incorrect login credentials"""

    def setUp(self):
        reset_to_empty_data()
        self.client = app.test_client()
        # Create one known-good account to test against.
        user = User("12342024", "Test Patient", "test@example.com",
                    "GoodPass1!", "patient")
        user.save()

    def test_correct_credentials_log_in_successfully(self):
        self.assertTrue(
            User.check_password_for_login("12342024", "GoodPass1!")
        )

    def test_wrong_password_rejected(self):
        self.assertFalse(
            User.check_password_for_login("12342024", "WrongPass1!")
        )

    def test_nonexistent_user_id_rejected(self):
        self.assertFalse(
            User.check_password_for_login("99999999", "AnyPass1!")
        )

    def test_login_route_shows_error_on_wrong_password(self):
        # End-to-end: actually POST to /login and check the app
        # doesn't let a wrong password through to the dashboard.
        response = self.client.post("/login", data={
            "user_id": "12342024", "password": "WrongPass1!"
        }, follow_redirects=True)
        self.assertIn(b"Invalid ID or password", response.data)

    def test_login_route_succeeds_with_correct_password(self):
        response = self.client.post("/login", data={
            "user_id": "12342024", "password": "GoodPass1!"
        }, follow_redirects=True)
        # A successful login redirects to the dashboard, which greets
        # the user by name.
        self.assertIn(b"Test Patient", response.data)


class TestUnauthorisedUrlAccess(unittest.TestCase):
    """Unauthorised URL access"""

    def setUp(self):
        reset_to_empty_data()
        self.client = app.test_client()

    def test_dashboard_requires_login(self):
        # Hitting /dashboard with NO session at all should bounce back
        # to the login page, never show dashboard content.
        response = self.client.get("/dashboard", follow_redirects=True)
        self.assertNotIn(b"Welcome,", response.data)

    def test_analytics_requires_login(self):
        response = self.client.get("/analytics", follow_redirects=True)
        self.assertNotIn(b"Task completion rate", response.data)

    def test_analytics_blocked_for_patient_role(self):
        # A logged-in PATIENT (not a clinician) should never see
        # clinic-wide analytics, even though they do have a valid
        # session - this is a ROLE check, not just a login check.
        user = User("12342024", "Test Patient", "test@example.com",
                    "GoodPass1!", "patient")
        user.save()
        self.client.post("/login", data={
            "user_id": "12342024", "password": "GoodPass1!"
        })
        response = self.client.get("/analytics", follow_redirects=True)
        self.assertNotIn(b"Task completion rate", response.data)

    def test_submit_task_requires_patient_session(self):
        # Nobody logged in at all - should redirect, not crash or leak
        # a partially-rendered page.
        response = self.client.post("/submit_task/task_0001",
                                     follow_redirects=True)
        self.assertNotIn(b"Weekly BP log", response.data)


if __name__ == "__main__":
    unittest.main()
