"""
Shared validation helpers for ClinicCare-Lite.

Keeping these in one place means every route uses the SAME rules,
instead of each person re-writing (and possibly getting slightly
wrong) their own validation logic.

Owned by: Louange (Architecture & Security lead) - everyone may add
helpers here as needed, just talk to Louange first so we don't end up
with duplicate/contradictory validators.
"""

import re
import os


def is_valid_email(email):
    """
    Very basic email format check - not perfect, but good enough to
    catch obvious typos like a missing '@' before we try to send mail.
    """
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def is_safe_filename(filename):
    """
    Prevents "path traversal" attacks, where someone names a file
    something like "../../etc/passwd" to try to make the app read or
    write outside the intended folder. os.path.basename() strips any
    directory parts, so if the result doesn't match the original
    filename, something suspicious was in there.
    """
    return os.path.basename(filename) == filename


def is_required_field_present(form_data, field_name):
    """
    Checks that a form field exists AND isn't just empty/whitespace.
    Used for the "missing required fields" validation the spec asks
    for on task creation, registration, etc.
    """
    value = form_data.get(field_name, "")
    return value is not None and value.strip() != ""
