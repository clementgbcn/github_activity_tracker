#!/usr/bin/env python3
"""
Utility to repair corrupted jobs.json file.

This script can be run directly or imported as a module to recover from job
storage corruption that may occur due to application crashes or unexpected shutdowns.
"""

import json
import logging
import os
import shutil
import sys
from datetime import datetime

# Set up logging
logger = logging.getLogger("github_activity_tracker")


def repair_jobs_file(jobs_file_path=None):
    """
    Repair the corrupted jobs file.

    Args:
        jobs_file_path (str, optional): Path to the jobs file.
        If None, the default path will be used.

    Returns:
        bool: True if repair was successful or not needed, False otherwise.
    """
    # Determine the jobs file location
    if jobs_file_path is None:
        jobs_file_path = os.path.join(
            os.path.expanduser("~"), ".github_activity_tracker", "jobs.json"
        )

    backup_file = jobs_file_path + f".bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"

    logger.info(f"Checking jobs file: {jobs_file_path}")

    if not os.path.exists(jobs_file_path):
        logger.info("Jobs file does not exist. Nothing to repair.")
        return True

    # Create a backup
    try:
        shutil.copy2(jobs_file_path, backup_file)
        logger.info(f"Created backup at {backup_file}")
    except Exception as e:
        logger.warning(f"Could not create backup: {e}")

    # Read the file content
    try:
        with open(jobs_file_path, "r") as f:
            content = f.read()

        # Try to parse the JSON
        try:
            json.loads(content)
            logger.info("Jobs file is valid JSON. No repair needed.")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Found JSON error: {e}")

            # Attempt repair by replacing the file with an empty jobs object
            try:
                with open(jobs_file_path, "w") as f:
                    json.dump({}, f, indent=2)
                logger.info("Repaired jobs file by replacing it with an empty jobs object.")
                return True
            except Exception as write_error:
                logger.error(f"Error writing repaired file: {write_error}")
                return False

    except Exception as e:
        logger.error(f"Error reading jobs file: {e}")
        return False


def main():
    """Run the repair utility from the command line."""
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("GitHub Activity Tracker - Jobs File Repair Utility")
    print("=================================================")

    if repair_jobs_file():
        print("✅ Jobs file repair complete.")
        return 0
    else:
        print("❌ Failed to repair jobs file.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
