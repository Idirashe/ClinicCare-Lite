"""
test_data_reset.py - a small LOCAL helper used only by Member 4's own
test files (test_analytics.py, test_auth_and_access.py,
test_file_handling.py, test_submission_workflow.py).

WHY THIS FILE EXISTS SEPARATELY:
The team's real tests/test_helpers.py provides backup_data() and
restore_data() - these protect your REAL data across the WHOLE test
run (back it up once at the start, restore it once at the end).

What it does NOT provide is a way to reset data/ to a known EMPTY
state BETWEEN individual tests while the suite is running - which
Member 4's tests need, since each test wants to start from a clean,
predictable slate rather than depending on leftover data from whatever
test ran before it.

Rather than editing the team's real test_helpers.py (which Louange/
whoever owns it might not want changed), this is a SEPARATE file that
only Member 4's own tests import. It doesn't touch backup_data() or
restore_data() at all, so it can't conflict with them.
"""

import json
import os
import shutil
import time

DATA_DIR = "data"
SUBMISSIONS_DIR = "submissions"
TEMP_UPLOADS_DIR = "temp_uploads"


def safe_rmtree(folder_path, retries=5, delay_seconds=0.2):
    """
    A Windows-safe version of shutil.rmtree().

    WHY THIS EXISTS: on Windows - especially inside a OneDrive-synced
    folder like this project's - a file handle isn't always released
    by the operating system the exact instant a `with open(...)` block
    exits, and OneDrive's own background sync process can also briefly
    hold a lock on a folder right after a file inside it changes. This
    causes shutil.rmtree() to raise "PermissionError: [WinError 5]
    Access is denied" even though nothing in OUR code still has the
    file open - it clears up on its own within a fraction of a second.

    This function just tries again a few times with a short pause in
    between, which is enough time for Windows/OneDrive to let go. If
    it STILL can't delete the folder after several tries, it gives up
    quietly rather than crashing the whole test suite over a folder
    cleanup step that isn't the actual thing being tested.

    This is the same class of problem the team's real
    tests/test_helpers.py already works around in restore_data() -
    this just applies the same idea inside individual test cases'
    tearDown() methods.
    """
    if not os.path.exists(folder_path):
        return

    for attempt in range(retries):
        try:
            shutil.rmtree(folder_path)
            return  # success - no need to retry further
        except (PermissionError, OSError):
            if attempt < retries - 1:
                time.sleep(delay_seconds)
            # On the final attempt, silently give up - a leftover temp
            # test folder is harmless clutter, not a real test failure.

# The exact starting shape for each JSON file. Users/tasks/submissions/
# clinics/appointments are all stored as dicts (keyed by ID); messages
# is stored as a list (see models/message.py's own comment on why).
EMPTY_DATA_SHAPES = {
    "users.json": {},
    "health_tasks.json": {},
    "task_submissions.json": {},
    "clinics.json": {},
    "appointments.json": {},
    "messages.json": [],
}


def reset_to_empty_data():
    """
    Overwrite data/*.json with empty shapes, and wipe submissions/ and
    temp_uploads/ so leftover files from a previous test can't leak
    into the next one. Call this from a test case's setUp().

    NOTE: this does NOT back up/restore your REAL data - that's what
    backup_data()/restore_data() in test_helpers.py already do, once,
    around the ENTIRE test run via run_tests.py. This function only
    resets the WORKING copy of data/ WHILE the suite is running, in
    between individual tests.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    for filename, empty_shape in EMPTY_DATA_SHAPES.items():
        with open(os.path.join(DATA_DIR, filename), "w") as f:
            json.dump(empty_shape, f, indent=4)

    for folder in (SUBMISSIONS_DIR, TEMP_UPLOADS_DIR):
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder, exist_ok=True)
