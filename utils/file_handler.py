"""
Secure file handling for ClinicCare-Lite.

Covers everything in the project brief's "C. Secure file handling"
section:
- Automatic file renaming
- Patient- and clinic-specific directories
- Safe file-path construction
- Duplicate-file handling
- File-size restrictions
- Secure file download
- File replacement or versioning
- Submission metadata recording (timestamp - handled in the model,
  this file focuses on the physical file operations)

Owned by: Idirashe (Member 2 - Patient Services, File Handling and
Engagement Lead)
"""

import os
import shutil
from datetime import datetime

SUBMISSIONS_DIR = "submissions"
ALLOWED_EXTENSIONS = (".txt", ".csv", ".pdf")
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def is_safe_filename(filename):
    """
    Guards against path traversal attacks - where someone names a file
    something like "../../etc/passwd" or "..\\..\\Windows\\System32\\x"
    to try to make the app read or write outside the folder it should
    be confined to.

    We check for BOTH forward slashes and backslashes explicitly,
    rather than relying only on os.path.basename(). That's because
    os.path.basename() only recognises the path separator native to
    whatever operating system Python is currently running on - on
    Linux/Mac it ignores backslashes entirely, which would let a
    Windows-style traversal attempt slip through undetected on a
    non-Windows server. Checking for both characters directly makes
    this safe regardless of which OS the app is deployed on.
    """
    if "/" in filename or "\\" in filename:
        return False
    # Belt-and-suspenders: also confirm basename() doesn't change the
    # filename (catches any other separator-like edge cases).
    return os.path.basename(filename) == filename


def validate_file(file_path, original_filename):
    """
    Check a file meets the upload rules before it's accepted:
    - Extension must be .txt, .csv, or .pdf
    - Filename must be "safe" (no path traversal attempts)
    - Size must be under the 5 MB limit

    Returns (True, "") if the file passes all checks, or
    (False, "human-readable reason") if it fails one.
    """
    if not is_safe_filename(original_filename):
        return False, "The filename contains invalid characters."

    _, ext = os.path.splitext(original_filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False, f"File type '{ext}' is not allowed. Use .txt, .csv, or .pdf."

    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE_BYTES:
        return False, "File is too large. Maximum size is 5 MB."

    return True, ""


def build_submission_path(clinic_id, patient_id, patient_task_filename):
    """
    Build the correct storage path for a submission, organised by
    CLINIC first, then PATIENT - matching the brief's requirement for
    "patient- and clinic-specific directories":

        submissions/<clinic_id>/<patient_id>/<patientID_taskID.ext>

    This keeps every clinic's data physically separated, which matters
    if this project ever needs to support multiple clinics that
    shouldn't be able to see each other's patient files at the
    filesystem level, not just at the application level.
    """
    # Guard against a missing/unknown clinic_id producing a weird path
    # like "submissions/None/..." - fall back to a clearly-labelled
    # folder instead, so it's obvious something needs fixing rather
    # than silently creating a folder literally named "None".
    safe_clinic_id = clinic_id if clinic_id else "unassigned_clinic"

    return os.path.join(SUBMISSIONS_DIR, safe_clinic_id, patient_id, patient_task_filename)


def save_submission_file(temp_file_path, original_filename, clinic_id, patient_id, task_id):
    """
    Validate and move an uploaded file into its permanent, correctly
    organised home. Handles duplicate submissions by keeping a
    versioned history rather than silently overwriting the previous
    file - this satisfies both "duplicate-file handling" and "file
    replacement or versioning" from the brief.

    Returns the final saved file path on success.
    Raises ValueError with a clear message if validation fails.
    """
    is_valid, error_message = validate_file(temp_file_path, original_filename)
    if not is_valid:
        raise ValueError(error_message)

    _, ext = os.path.splitext(original_filename)
    base_filename = f"{patient_id}_{task_id}{ext}"

    dest_dir = os.path.dirname(
        build_submission_path(clinic_id, patient_id, base_filename)
    )
    os.makedirs(dest_dir, exist_ok=True)

    final_path = build_submission_path(clinic_id, patient_id, base_filename)

    # DUPLICATE / VERSIONING HANDLING: if a submission already exists
    # for this patient+task, don't silently overwrite it - move the
    # OLD one into a timestamped backup first, so the previous
    # submission is never lost. This gives a simple version history:
    # the current file is always the "live" one, and older versions
    # sit alongside it with a timestamp in their name.
    if os.path.exists(final_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archived_name = f"{patient_id}_{task_id}_replaced_{timestamp}{ext}"
        archived_path = os.path.join(dest_dir, archived_name)
        shutil.move(final_path, archived_path)

    shutil.copy(temp_file_path, final_path)
    return final_path


def get_submission_file_path(clinic_id, patient_id, task_id, ext):
    """
    Build the expected path to an existing submission, for use when
    a clinician or the patient themselves wants to DOWNLOAD/view a
    previously submitted file. This is a read-only lookup - it doesn't
    create or modify anything, just tells the caller where the file
    should be if it exists.
    """
    filename = f"{patient_id}_{task_id}{ext}"
    return build_submission_path(clinic_id, patient_id, filename)