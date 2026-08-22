"""
Test isolation helper for ClinicCare-Lite.

Backs up and restores data/*.json so running tests never leaves your
real app unable to run afterward.
"""

import os
import shutil

DATA_DIR = "data"
BACKUP_DIR = "data_test_backup"


def backup_data():
    """
    Copy the current contents of data/ into a backup folder, so they
    can be restored later.
    """
    if os.path.exists(BACKUP_DIR):
        try:
            shutil.rmtree(BACKUP_DIR)
        except (PermissionError, OSError):
            pass

    if os.path.exists(DATA_DIR):
        if os.path.exists(BACKUP_DIR):
            for filename in os.listdir(DATA_DIR):
                src = os.path.join(DATA_DIR, filename)
                dst = os.path.join(BACKUP_DIR, filename)
                if os.path.isfile(src):
                    shutil.copy(src, dst)
        else:
            shutil.copytree(DATA_DIR, BACKUP_DIR)


def restore_data():
    """
    Restore data/ to exactly whatever was backed up by backup_data().

    Copies files back individually rather than deleting/recreating the
    whole data/ folder - this avoids a Windows PermissionError that
    can happen if a file handle inside the folder hasn't been fully
    released yet right after tests finish running.
    """
    if not os.path.exists(BACKUP_DIR):
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    backed_up_files = set(os.listdir(BACKUP_DIR))

    for existing_file in os.listdir(DATA_DIR):
        if existing_file not in backed_up_files:
            existing_path = os.path.join(DATA_DIR, existing_file)
            if os.path.isfile(existing_path):
                os.remove(existing_path)

    for filename in backed_up_files:
        src = os.path.join(BACKUP_DIR, filename)
        dst = os.path.join(DATA_DIR, filename)
        if os.path.isfile(src):
            shutil.copy(src, dst)

    try:
        shutil.rmtree(BACKUP_DIR)
    except (PermissionError, OSError):
        pass