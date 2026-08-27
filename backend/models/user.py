"""
backend/models/user.py

The User model — represents both Clinicians and Patients.

ID rules (from project spec, Section 1):
- Clinician: 8-digit numeric ID ending in "0000" (e.g. 12350000)
- Patient:   8-digit numeric ID ending in a registration year 2022-2028
             (e.g. 12342024)

Passwords are hashed with bcrypt before ever being stored — plaintext
passwords must NEVER be saved to users.json.
"""
import re
import bcrypt
from backend.storage import load_json, save_json

USERS_FILE = "users.json"

ID_PATTERN = re.compile(r"^\d{8}$")
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$"
)


def validate_id(user_id: str, role: str) -> bool:
    """Check the ID matches the format rules for the given role."""
    if not ID_PATTERN.match(user_id):
        return False
    if role == "clinician":
        return user_id.endswith("0000")
    if role == "patient":
        year = user_id[-4:]
        return year.isdigit() and 2022 <= int(year) <= 2028
    return False


def validate_password(password: str) -> bool:
    """
    Check the password meets the complexity rules:
    min 8 chars, at least one uppercase, one lowercase, one digit,
    one special character.
    """
    return bool(PASSWORD_PATTERN.match(password))


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a string safe to store."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class User:
    def __init__(self, user_id, name, email, role, password_hash, theme="colorful"):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.role = role  # "clinician" or "patient"
        self.password_hash = password_hash
        # Clinicians always default to dark theme (per spec); patients choose.
        self.theme = "dark" if role == "clinician" else theme

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "password_hash": self.password_hash,
            "theme": self.theme,
        }

    @staticmethod
    def register(user_id, name, email, password, role):
        """
        Create and persist a new user. Returns (User, None) on success,
        or (None, error_message) if validation fails.
        """
        if not validate_id(user_id, role):
            return None, f"Invalid ID format for role '{role}'."
        if not validate_password(password):
            return None, (
                "Password must be at least 8 characters and include an "
                "uppercase letter, a lowercase letter, a digit, and a "
                "special character."
            )

        users = load_json(USERS_FILE)
        if any(u["user_id"] == user_id for u in users):
            return None, "A user with this ID already exists."

        new_user = User(user_id, name, email, role, hash_password(password))
        users.append(new_user.to_dict())
        save_json(USERS_FILE, users)
        return new_user, None

    @staticmethod
    def login(user_id, password):
        """
        Verify credentials. Returns (User, None) on success,
        or (None, error_message) on failure.
        """
        users = load_json(USERS_FILE)
        record = next((u for u in users if u["user_id"] == user_id), None)
        if record is None:
            return None, "No account found with that ID."
        if not check_password(password, record["password_hash"]):
            return None, "Incorrect password."
        return User(**record), None

    @staticmethod
    def find_by_id(user_id):
        users = load_json(USERS_FILE)
        record = next((u for u in users if u["user_id"] == user_id), None)
        return User(**record) if record else None
