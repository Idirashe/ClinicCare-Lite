"""
User model for ClinicCare-Lite.

Handles the two roles in the system: clinician and patient.
Responsible for:
- Validating ID format (different rules for clinician vs patient)
- Validating password strength
- Hashing passwords with bcrypt before they are ever saved
- Saving/loading user records to and from data/users.json

Owned by: Louange (Architecture & Security lead)
"""

import bcrypt
import json
import re
import os

# Path to the JSON file that stores all users. Kept as a constant so it's
# easy to change later (e.g. if we ever move to a real database).
USERS_FILE = os.path.join("data", "users.json")


class User:
    def __init__(self, user_id, name, email, password, role, theme=None):
        """
        Create a new User object in memory (does NOT save to disk yet -
        call .save() separately once you're ready to persist it).

        user_id: 8-digit string, e.g. "12342024"
        name: full name, e.g. "Jane Doe"
        email: used for notifications
        password: the PLAIN TEXT password - we hash it immediately below,
                   so the plain text never gets stored anywhere.
        role: either "clinician" or "patient"
        theme: "dark" for clinicians (default), "colorful" or "dark" for
               patients (patients can choose)
        """
        self.user_id = user_id
        self.name = name
        self.email = email

        # bcrypt.hashpw needs bytes, not a string, so we encode first.
        # bcrypt.gensalt() creates a random "salt" so that even two users
        # with the identical password get different hashes in storage.
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        self.role = role
        # Clinicians always start on the dark theme (per spec); patients
        # default to colorful but can change it later in their profile.
        self.theme = theme or ("dark" if role == "clinician" else "colorful")

    # ------------------------------------------------------------------
    # VALIDATION - these are @staticmethod because they don't need an
    # actual User object to run; we call them BEFORE creating the user,
    # while checking a registration form.
    # ------------------------------------------------------------------

    @staticmethod
    def validate_id(user_id, role):
        """
        Check that a user ID follows the correct format for its role.

        Rules from the project spec:
        - Must be exactly 8 digits, e.g. "12342024"
        - Clinician IDs must end in "0000", e.g. "12350000"
        - Patient IDs must end in a valid registration year 2022-2028,
          e.g. "12342024" (ends in 2024)

        Returns True if valid, False otherwise.
        """
        # re.match with ^\d{8}$ means: start of string, exactly 8 digits, end of string.
        if not re.match(r"^\d{8}$", user_id):
            return False

        if role == "clinician":
            return user_id[-4:] == "0000"

        if role == "patient":
            # Take the last 4 characters and check they form a year in range.
            year = int(user_id[-4:])
            return 2022 <= year <= 2028

        # Unknown role - reject.
        return False

    @staticmethod
    def validate_password(password):
        """
        Check password strength requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character from !@#$%^&*

        Returns True if all conditions are met, False otherwise.
        """
        if len(password) < 8:
            return False
        if not re.search(r"[A-Z]", password):
            return False
        if not re.search(r"[a-z]", password):
            return False
        if not re.search(r"\d", password):
            return False
        if not re.search(r"[!@#$%^&*]", password):
            return False
        return True

    def check_password(self, plain_password):
        """
        Compare a plain-text password (typed at login) against the stored
        hash. Returns True if they match. This is how login verification
        works - we never decrypt the hash, we just check if hashing the
        typed password produces the same result.
        """
        return bcrypt.checkpw(plain_password.encode("utf-8"), self.password_hash)

    # ------------------------------------------------------------------
    # PERSISTENCE - saving to and loading from users.json
    # ------------------------------------------------------------------

    def save(self):
        """
        Save this user into data/users.json.

        IMPORTANT BUG TO AVOID: if you open a file in "r+" mode and write
        LESS data than was there before, leftover old bytes stay at the
        end of the file and corrupt the JSON. That's why we call
        f.seek(0) then f.truncate() before writing - seek(0) moves back
        to the start of the file, and truncate() deletes everything after
        wherever we are, so old content can't linger.
        """
        with open(USERS_FILE, "r+") as f:
            data = json.load(f)
            data[self.user_id] = {
                "name": self.name,
                "email": self.email,
                # password_hash is bytes; decode to a normal string so it
                # can be stored in JSON (JSON doesn't support raw bytes).
                "password_hash": self.password_hash.decode("utf-8"),
                "role": self.role,
                "theme": self.theme,
            }
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=4)

    @staticmethod
    def load(user_id):
        """
        Load a single user's raw dictionary from users.json by their ID.
        Returns None if the user doesn't exist.

        Note: this returns a plain dict, not a User object, because we'd
        need the plain-text password to rebuild a real User object (and
        we deliberately never store that). Use check_password_for_login()
        below for login checks instead.
        """
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        return data.get(user_id)

    @staticmethod
    def check_password_for_login(user_id, plain_password):
        """
        Convenience function used by the /login route.
        Looks up the user, then checks their password directly against
        the stored hash - without needing to construct a full User object.

        Returns True/False.
        """
        user_record = User.load(user_id)
        if user_record is None:
            return False
        stored_hash = user_record["password_hash"].encode("utf-8")
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash)
