"""Utility for persistent storage of job data."""

import json
import os
import shutil
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from .logging_config import logger


# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that can handle datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Let the base class handle any other types
        return super().default(obj)


# File to store job session data
JOBS_DATA_FILE = os.path.join(os.path.expanduser("~"), ".github_activity_tracker", "jobs.json")

# Lock for thread-safe operations
_lock = threading.Lock()


def _ensure_jobs_file() -> None:
    """Ensure the jobs data file exists."""
    jobs_dir = os.path.dirname(JOBS_DATA_FILE)

    # Create directory if it doesn't exist
    if not os.path.exists(jobs_dir):
        try:
            os.makedirs(jobs_dir, exist_ok=True)
            logger.debug(f"Created jobs directory: {jobs_dir}")
        except Exception as e:
            logger.error(f"Failed to create jobs directory: {e}")
            return

    # Create empty jobs file if it doesn't exist
    if not os.path.exists(JOBS_DATA_FILE):
        try:
            with open(JOBS_DATA_FILE, "w") as f:
                json.dump({}, f, indent=2, cls=DateTimeEncoder)
            logger.info(f"Created empty jobs data file: {JOBS_DATA_FILE}")
        except Exception as e:
            logger.error(f"Failed to create jobs data file: {e}")


def _load_jobs_internal() -> Dict[str, Any]:  # noqa: C901
    """Internal function to load job data without acquiring the lock.

    Returns:
        Dictionary of job data indexed by job ID
    """
    _ensure_jobs_file()

    try:
        # First, check if the file is valid JSON
        try:
            with open(JOBS_DATA_FILE, "r") as f:
                content = f.read()

            try:
                jobs_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Jobs file contains invalid JSON: {e}")
                logger.info("Attempting to repair jobs file by creating a backup and resetting it")

                # Create a backup of the corrupted file
                backup_file = JOBS_DATA_FILE + f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                try:
                    shutil.copy2(JOBS_DATA_FILE, backup_file)
                    logger.info(f"Created backup of corrupted jobs file at {backup_file}")
                except Exception as copy_error:
                    logger.warning(f"Could not create backup of jobs file: {copy_error}")

                # Reset the file with an empty object
                try:
                    with open(JOBS_DATA_FILE, "w") as f:
                        json.dump({}, f, indent=2, cls=DateTimeEncoder)
                    logger.info("Reset jobs file to empty object")
                    return {}
                except Exception as write_error:
                    logger.error(f"Could not reset jobs file: {write_error}")
                    return {}
        except Exception as read_error:
            logger.error(f"Error reading jobs file: {read_error}")
            return {}

        # If jobs_data is not a dictionary, reset it
        if not isinstance(jobs_data, dict):
            logger.error("Jobs data is not a dictionary, resetting to empty object")
            with open(JOBS_DATA_FILE, "w") as f:
                json.dump({}, f, indent=2)
            return {}

        # Convert datetime strings back to datetime objects
        for job_id, job in jobs_data.items():
            if isinstance(job, dict):  # Make sure job is a dictionary
                if job.get("start_time"):
                    try:
                        job["start_time"] = datetime.fromisoformat(job["start_time"])
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error converting start_time for job {job_id}: {e}")
                        # Don't fail - keep as string if can't convert

                if job.get("end_time"):
                    try:
                        job["end_time"] = datetime.fromisoformat(job["end_time"])
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Error converting end_time for job {job_id}: {e}")
                        # Don't fail - keep as string if can't convert

                # Make sure activities is always a list
                if "activities" in job and not isinstance(job["activities"], list):
                    job["activities"] = []

                # Validate report_path exists if present
                if "report_path" in job and job["report_path"]:
                    if not os.path.exists(job["report_path"]):
                        logger.warning(
                            f"Report path for job {job_id} does not exist: {job['report_path']}"
                        )
            else:
                logger.warning(f"Invalid job data found for job {job_id}, replacing with empty job")
                jobs_data[job_id] = {
                    "status": "unknown",
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "processed_users": 0,
                    "total_users": 0,
                    "activities": [],
                    "errors": ["Invalid job data recovered"],
                    "report_path": None,
                }

        logger.debug(f"Loaded {len(jobs_data)} jobs from storage")
        return jobs_data
    except Exception as e:
        logger.error(f"Error loading jobs data: {e}")
        return {}


def load_jobs() -> Dict[str, Any]:
    """Load job data from persistent storage.

    Returns:
        Dictionary of job data indexed by job ID
    """
    with _lock:
        return _load_jobs_internal()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific job from persistent storage.

    Args:
        job_id: The ID of the job to retrieve

    Returns:
        The job data if found, None otherwise
    """
    with _lock:
        jobs = _load_jobs_internal()
        return jobs.get(job_id)


def _save_jobs_internal(jobs_data: Dict[str, Any]) -> bool:  # noqa: C901
    """Internal function to save job data without acquiring the lock.

    Args:
        jobs_data: Dictionary of job data indexed by job ID

    Returns:
        True if successful, False otherwise
    """
    _ensure_jobs_file()

    try:
        # Create a copy of the jobs data for serialization
        jobs_to_save = {}

        for job_id, job in jobs_data.items():
            if not isinstance(job, dict):
                logger.warning(f"Skipping job {job_id} as it's not a dictionary")
                continue

            try:
                # Create a serializable copy of the job
                job_copy = job.copy()

                # Convert datetime objects to strings for JSON serialization
                if isinstance(job_copy.get("start_time"), datetime):
                    job_copy["start_time"] = job_copy["start_time"].isoformat()

                if isinstance(job_copy.get("end_time"), datetime):
                    job_copy["end_time"] = job_copy["end_time"].isoformat()

                # Handle activities - make sure it's serializable
                if "activities" in job_copy:
                    if not isinstance(job_copy["activities"], list):
                        job_copy["activities"] = []
                    else:
                        # Make a copy of activities to avoid modification problems
                        activities = []
                        for activity in job_copy["activities"]:
                            if isinstance(activity, dict):
                                activities.append(activity.copy())
                        job_copy["activities"] = activities

                # Store the serializable job
                jobs_to_save[job_id] = job_copy
            except Exception as inner_e:
                logger.error(f"Error preparing job {job_id} for saving: {inner_e}")

        # Make sure we have data to save
        if not jobs_to_save and jobs_data:
            logger.warning("No valid jobs to save from non-empty input")
            return False

        # Create a temporary file for safe writing
        temp_file = JOBS_DATA_FILE + ".temp"
        try:
            # Write to temp file first using custom encoder to handle datetime objects
            with open(temp_file, "w") as f:
                json.dump(jobs_to_save, f, indent=2, cls=DateTimeEncoder)

            # Verify the JSON is valid
            try:
                with open(temp_file, "r") as f:
                    json.load(f)  # This will raise an exception if invalid
            except json.JSONDecodeError as e:
                logger.error(f"Generated invalid JSON file: {e}")
                os.remove(temp_file)  # Remove the invalid file
                return False
            except Exception as e:
                logger.error(f"Error validating JSON file: {e}")
                os.remove(temp_file)  # Remove the potentially invalid file
                return False

            # If valid, atomically replace the original file
            try:
                # On non-Windows systems we can use atomic rename
                os.replace(temp_file, JOBS_DATA_FILE)
            except Exception as _:
                # Fall back to non-atomic replace, with backup
                backup_file = JOBS_DATA_FILE + ".bak"
                if os.path.exists(JOBS_DATA_FILE):
                    try:
                        shutil.copy2(JOBS_DATA_FILE, backup_file)
                    except Exception as backup_error:
                        logger.warning(f"Could not create backup file: {backup_error}")

                # Now copy the temp file
                shutil.copy2(temp_file, JOBS_DATA_FILE)
                os.remove(temp_file)

            logger.debug(f"Saved {len(jobs_to_save)} jobs to storage")
            return True
        except Exception as file_error:
            logger.error(f"Error writing jobs file: {file_error}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as _:
                    pass
            return False
    except Exception as e:
        logger.error(f"Error saving jobs data: {e}")
        return False


def save_jobs(jobs_data: Dict[str, Any]) -> bool:
    """Save job data to persistent storage.

    Args:
        jobs_data: Dictionary of job data indexed by job ID

    Returns:
        True if successful, False otherwise
    """
    with _lock:
        return _save_jobs_internal(jobs_data)


def save_job(job_id: str, job_data: Dict[str, Any]) -> bool:
    """Save a single job to persistent storage.

    Args:
        job_id: The job ID
        job_data: The job data to save

    Returns:
        True if successful, False otherwise
    """
    logger.debug(f"Saving job {job_id} to storage")
    with _lock:
        # Load existing jobs directly without lock (we already have it)
        jobs = _load_jobs_internal()

        # Update or add the specified job
        jobs[job_id] = job_data

        # Save all jobs directly without lock (we already have it)
        result = _save_jobs_internal(jobs)
        logger.debug(f"Job {job_id} saved to storage: {result}")
        return result


def get_all_jobs() -> Dict[str, Any]:
    """Get all jobs from persistent storage.

    Returns:
        Dictionary of all job data indexed by job ID
    """
    return load_jobs()


def delete_job(job_id: str) -> bool:
    """Delete a job and its associated files from storage.

    Args:
        job_id: The ID of the job to delete

    Returns:
        True if successful, False otherwise
    """
    with _lock:
        # Load existing jobs directly without lock (we already have it)
        jobs = _load_jobs_internal()

        # Check if job exists
        if job_id not in jobs:
            logger.warning(f"Job {job_id} not found for deletion")
            return False

        # Get job data before removing
        job_data = jobs.get(job_id, {})

        # Remove job from storage
        try:
            jobs.pop(job_id)
            # Save directly without lock (we already have it)
            result = _save_jobs_internal(jobs)

            # Delete associated report directory if it exists
            report_path = job_data.get("report_path")
            if report_path and os.path.exists(report_path):
                try:
                    shutil.rmtree(report_path)
                    logger.info(f"Deleted report directory for job {job_id}: {report_path}")
                except Exception as e:
                    logger.error(f"Error deleting report directory for job {job_id}: {e}")

            logger.info(f"Deleted job {job_id}")
            return result
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            return False


def clean_old_jobs(max_age_days: int = 30) -> int:  # noqa: C901
    """Remove jobs older than specified number of days.

    Args:
        max_age_days: Maximum age in days for jobs to keep

    Returns:
        Number of jobs removed
    """
    logger.debug(f"Starting clean_old_jobs with max_age_days={max_age_days}")

    # Start with empty jobs if anything goes wrong
    jobs = {}
    jobs_to_remove = []
    removed_count = 0

    # Attempt to acquire lock - with timeout to prevent hanging
    lock_acquired = False
    try:
        # Non-blocking lock acquisition with 2-second timeout
        lock_acquired = _lock.acquire(timeout=2)
        if not lock_acquired:
            logger.warning("Timed out waiting for lock in clean_old_jobs - cleanup aborted")
            return 0

        logger.debug("Acquired lock for clean_old_jobs")

        # Load existing jobs directly without nested lock
        try:
            logger.debug("Loading jobs for cleanup...")
            jobs = _load_jobs_internal()
            logger.debug(f"Loaded {len(jobs)} jobs for cleanup")
        except Exception as e:
            logger.error(f"Error loading jobs for cleanup: {e}")
            return 0

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        logger.debug(f"Cutoff date for cleanup: {cutoff_date.isoformat()}")

        # Identify jobs to remove - with safety checks
        try:
            # Only process if we have valid jobs
            if not isinstance(jobs, dict):
                logger.warning("Jobs data is not a dictionary - aborting cleanup")
                return 0

            for job_id, job_data in list(jobs.items()):
                # First check if the data is valid
                if not isinstance(job_data, dict):
                    logger.debug(f"Job {job_id} not a dictionary, marking for removal")
                    jobs_to_remove.append(job_id)
                    continue

                # Get end time or start time with validation
                job_time = None
                if "end_time" in job_data and job_data["end_time"]:
                    job_time = job_data["end_time"]
                elif "start_time" in job_data and job_data["start_time"]:
                    job_time = job_data["start_time"]

                # Skip if no valid time
                if not job_time:
                    logger.debug(f"Job {job_id} has no valid time, skipping")
                    continue

                # Check if job is old enough to remove
                if isinstance(job_time, datetime) and job_time < cutoff_date:
                    logger.debug(f"Job {job_id} is old, marking for removal")
                    jobs_to_remove.append(job_id)

            logger.debug(f"Identified {len(jobs_to_remove)} jobs to remove")
        except Exception as e:
            logger.error(f"Error identifying jobs to remove: {e}")
            return 0

        # Process removals with safety checks
        try:
            # Remove jobs directly from the dictionary for efficiency
            for job_id in jobs_to_remove:
                if job_id in jobs:
                    jobs.pop(job_id)
                    removed_count += 1

            logger.debug(f"Removed {removed_count} jobs from dictionary")
        except Exception as e:
            logger.error(f"Error removing jobs from dictionary: {e}")
            return 0

        # Save changes if needed
        if removed_count > 0:
            try:
                # Save directly without nested lock
                _save_jobs_internal(jobs)
                logger.debug(f"Saved updated jobs dictionary after removing {removed_count} jobs")
            except Exception as e:
                logger.error(f"Error saving jobs after cleanup: {e}")
                # Don't return here - still report the counts even if save failed

        logger.info(f"Cleaned {removed_count} jobs older than {max_age_days} days")
        return removed_count

    except Exception as e:
        logger.error(f"Unexpected error in clean_old_jobs: {e}")
        return 0
    finally:
        # Always release the lock if we acquired it
        if lock_acquired:
            try:
                _lock.release()
                logger.debug("Released lock for clean_old_jobs")
            except Exception:
                # This should never happen, but just in case
                logger.error("Error releasing lock in clean_old_jobs")


def debug_jobs_file():  # noqa: C901
    """Print debug information about the jobs file.

    This function is for debugging purposes only.
    """
    try:
        logger.info(f"Jobs file path: {JOBS_DATA_FILE}")

        if not os.path.exists(JOBS_DATA_FILE):
            logger.info("Jobs file does not exist")
            return

        # Get file stats
        file_size = os.path.getsize(JOBS_DATA_FILE)
        last_modified = datetime.fromtimestamp(os.path.getmtime(JOBS_DATA_FILE))

        logger.info(f"Jobs file size: {file_size} bytes")
        logger.info(f"Last modified: {last_modified.isoformat()}")

        # Read raw content without lock - this is just diagnostic code
        with open(JOBS_DATA_FILE, "r") as f:
            content = f.read()

        logger.info(f"File content length: {len(content)} characters")

        # Try parsing JSON
        try:
            jobs = json.loads(content)
            logger.info(f"Successfully parsed JSON with {len(jobs)} job entries")

            # Basic validation of job entries
            for job_id, job in jobs.items():
                if not isinstance(job, dict):
                    logger.warning(f"Job {job_id} is not a dictionary: {type(job)}")
                    continue

                # Check required keys
                required_keys = ["status", "start_time", "end_time", "activities"]
                missing_keys = [key for key in required_keys if key not in job]
                if missing_keys:
                    logger.warning(f"Job {job_id} is missing keys: {missing_keys}")

                # Check date formats
                if "start_time" in job:
                    try:
                        datetime.fromisoformat(job["start_time"])
                    except (ValueError, TypeError):
                        logger.warning(
                            f"Job {job_id} has invalid start_time: {job.get('start_time')}"
                        )

                if "end_time" in job and job["end_time"]:
                    try:
                        datetime.fromisoformat(job["end_time"])
                    except (ValueError, TypeError):
                        logger.warning(f"Job {job_id} has invalid end_time: {job.get('end_time')}")

                # Check activities
                if "activities" in job and not isinstance(job["activities"], list):
                    logger.warning(
                        f"Job {job_id} has non-list activities: {type(job.get('activities'))}"
                    )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")

    except Exception as e:
        logger.error(f"Error debugging jobs file: {e}")
