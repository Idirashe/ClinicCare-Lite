"""
Safe test runner for ClinicCare-Lite. Use this INSTEAD of running
unittest directly - it backs up your data/ folder before tests run
and restores it afterward, so you never lose real data or need to
manually recreate empty JSON files again.

Run with: python run_tests.py
"""

import unittest
import sys
from tests.test_helpers import backup_data, restore_data

if __name__ == "__main__":
    backup_data()
    try:
        loader = unittest.TestLoader()
        suite = loader.discover("tests")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        exit_code = 0 if result.wasSuccessful() else 1
    finally:
        restore_data()
        print("\n[Test runner] data/ has been restored - you can run 'python app.py' now.")

    sys.exit(exit_code)
    