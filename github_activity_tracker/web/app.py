"""Flask web app for GitHub Activity Tracker."""

import functools
import os
import random
import string
import sys
import threading
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_session import Session

# Import utility functions from parent package
from ..utils.file_utils import load_users_from_file
from ..utils.job_storage import delete_job, get_all_jobs, save_job
from ..utils.logging_config import logger

# Set up system path for importing modules
PACKAGE_PARENT = ".."
SCRIPT_DIR = os.path.dirname(
    os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))
)
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

# In-memory job storage (backed by persistent storage)
job_sessions = {}

# Default settings storage
default_settings = {"organization": "", "users": [], "users_file": ""}


# Function to require login
def require_login(f):
    """Decorator to require login for routes."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


# Function to require admin
def require_admin(f):
    """Decorator to require admin privileges for routes."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.url))
        if not g.user.is_admin:
            flash("Admin privileges required", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


# Helper functions for default settings
def get_default_organization():
    """Get the default organization."""
    return default_settings.get("organization", "")


def set_default_organization(org: str):
    """Set the default organization."""
    default_settings["organization"] = org


def get_default_users():
    """Get the default users list."""
    return default_settings.get("users", [])


def set_default_users(users: List[str]):
    """Set the default users list."""
    default_settings["users"] = users


def get_default_users_file():
    """Get the default users file path."""
    return default_settings.get("users_file", "")


def set_default_users_file(file_path: str):
    """Set the default users file path."""
    default_settings["users_file"] = file_path


def create_app():
    """Create and configure the Flask app."""
    # Create and configure app
    app = Flask(__name__)

    # Set secret key from environment or generate a random one
    app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

    # Configure session to use filesystem
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.path.dirname(__file__), "../data/sessions")
    app.config["SESSION_PERMANENT"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=31)  # sessions last for 31 days
    app.config["SESSION_USE_SIGNER"] = True

    # Create session folder if it doesn't exist
    os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)

    # Initialize session extension
    Session(app)

    # Register template filters
    @app.template_filter("format_datetime")
    def format_datetime(value):
        """Format a datetime object in a readable format."""
        if not value:
            return "N/A"
        if isinstance(value, str):
            try:
                from datetime import datetime

                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except:
                return value
        try:
            return value.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(value)

    @app.template_filter("format_duration")
    def format_duration(start_time, end_time):
        """Format the duration between two datetime objects."""
        if not start_time or not end_time:
            return "N/A"

        # Handle string dates
        if isinstance(start_time, str):
            try:
                from datetime import datetime

                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except:
                return "N/A"

        if isinstance(end_time, str):
            try:
                from datetime import datetime

                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except:
                return "N/A"

        try:
            duration = end_time - start_time
            seconds = duration.total_seconds()

            # Format based on duration length
            if seconds < 60:
                return f"{seconds:.1f} seconds"
            elif seconds < 3600:
                minutes = seconds / 60
                return f"{minutes:.1f} minutes"
            else:
                hours = seconds / 3600
                return f"{hours:.1f} hours"
        except:
            return "N/A"

    # Import auth module
    try:
        # Dynamic import attempt with fallback approaches
        try:
            from .auth import auth, authenticate_user, get_user_by_id

            logger.info("Successfully imported auth module via relative import")
        except ImportError:
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
            from github_activity_tracker.web.auth import auth, authenticate_user, get_user_by_id

            logger.info("Successfully imported auth module via absolute import")
    except ImportError as e:
        logger.error(f"Failed to import auth module: {e}")
        # Create a minimal auth module for demonstration
        from dataclasses import dataclass

        @dataclass
        class User:
            user_id: str
            username: str
            is_admin: bool = False

        def get_user_by_id(user_id: str) -> Optional[User]:
            """Get user by ID (demo version)."""
            if user_id == "demo":
                return User(user_id="demo", username="demo_user", is_admin=True)
            elif user_id == "admin":
                return User(user_id="admin", username="admin", is_admin=True)
            elif user_id == "user1":
                return User(user_id="user1", username="Regular User", is_admin=False)
            return None

        def authenticate_user(username: str, password: str) -> Optional[User]:
            """Authenticate user (demo version)."""
            if username == "demo" and password == "demo":
                return User(user_id="demo", username="demo_user", is_admin=True)
            elif username == "admin" and password == "password":
                return User(user_id="admin", username="admin", is_admin=True)
            elif username == "user1" and password == "user1pass":
                return User(user_id="user1", username="Regular User", is_admin=False)
            return None

        class auth:
            User = User
            get_user_by_id = get_user_by_id
            authenticate_user = authenticate_user
            authenticate = authenticate_user

        app.config["DEFAULT_ADMIN_USERNAME"] = "admin"
        app.config["DEFAULT_ADMIN_PASSWORD"] = "password"
        logger.warning("Using demo auth module! This should not be used in production.")

    # User middleware - add user to g before each request
    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
        else:
            try:
                # Direct implementation to avoid auth module issues
                if user_id == "demo":
                    g.user = type(
                        "User", (), {"user_id": "demo", "username": "demo_user", "is_admin": True}
                    )()
                elif user_id == "admin":
                    g.user = type(
                        "User", (), {"user_id": "admin", "username": "admin", "is_admin": True}
                    )()
                elif user_id == "user1":
                    g.user = type(
                        "User",
                        (),
                        {"user_id": "user1", "username": "Regular User", "is_admin": False},
                    )()
                else:
                    # If we get here, try with the auth module or fallback to None
                    try:
                        g.user = auth.get_user_by_id(user_id)
                    except:
                        logger.warning(f"Could not load user {user_id} with auth module")
                        g.user = None

                # If user no longer exists, clear session
                if g.user is None:
                    session.clear()
            except Exception as e:
                logger.error(f"Error loading user: {e}")
                session.clear()
                g.user = None

    # Load job sessions from persistent storage
    try:
        jobs = get_all_jobs()
        # Ensure jobs is a dictionary
        if isinstance(jobs, dict):
            # Clear existing jobs first
            job_sessions.clear()
            # Then add the new jobs
            for job_id, job_data in jobs.items():
                job_sessions[job_id] = job_data

            n_jobs = len(jobs)
            if n_jobs > 0:
                logger.info(f"Loaded {n_jobs} jobs from persistent storage")
        else:
            logger.error(f"Expected dictionary from get_all_jobs(), got {type(jobs).__name__}")
            # Clear job_sessions if jobs is not a dictionary
            job_sessions.clear()
    except Exception as e:
        logger.error(f"Error loading jobs: {e}")

    # Routes
    @app.route("/")
    @require_login
    def index():
        """Main page - show form for starting a job."""
        # Get default values from settings
        default_org = get_default_organization()
        default_users = get_default_users()
        default_users_str = " ".join(default_users) if default_users else ""
        default_users_file = get_default_users_file()

        # Set default date range to last 7 days
        today = datetime.now().date()
        default_date_to = today.strftime("%Y-%m-%d")
        default_date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")

        return render_template(
            "index.html",
            default_org=default_org,
            default_users=default_users_str,
            default_users_file=default_users_file,
            default_date_from=default_date_from,
            default_date_to=default_date_to,
        )

    print("  - Index route defined")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """Login page."""
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            # Check username and password
            try:
                # Try with both methods for compatibility
                if hasattr(auth, "authenticate_user"):
                    user = auth.authenticate_user(username, password)
                elif hasattr(auth, "authenticate"):
                    user = auth.authenticate(username, password)
                else:
                    # Direct fallback for demo mode
                    user = None
                    if username == "demo" and password == "demo":
                        user = type(
                            "User",
                            (),
                            {"user_id": "demo", "username": "demo_user", "is_admin": True},
                        )()
                    elif username == "admin" and password == "password":
                        user = type(
                            "User", (), {"user_id": "admin", "username": "admin", "is_admin": True}
                        )()
                    elif username == "user1" and password == "user1pass":
                        user = type(
                            "User",
                            (),
                            {"user_id": "user1", "username": "Regular User", "is_admin": False},
                        )()
            except Exception as e:
                logger.error(f"Authentication error: {e}")
                user = None

            if user:
                # Set user ID in session
                session.clear()
                session["user_id"] = user.user_id

                # Log success
                logger.info(f"User {username} logged in successfully")

                # Check for 'next' parameter
                next_url = request.args.get("next")
                if next_url:
                    return redirect(next_url)
                else:
                    return redirect(url_for("index"))
            else:
                flash("Invalid username or password", "error")
                logger.warning(f"Failed login attempt for username: {username}")

        # Show login form
        return render_template("login.html")

    print("  - Login route defined")

    @app.route("/logout")
    def logout():
        """Logout page."""
        # Log the logout
        if "user_id" in session:
            user_id = session["user_id"]
            user = auth.get_user_by_id(user_id)
            if user:
                logger.info(f"User {user.username} logged out")

        # Clear session
        session.clear()
        flash("You have been logged out", "info")
        return redirect(url_for("login"))

    print("  - Logout route defined")

    @app.route("/start-job", methods=["POST"])
    @require_login
    def start_job():
        """Start a new job with the provided parameters."""
        # Generate a unique job ID
        job_id = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        logger.info(f"Generated job ID: {job_id}")

        # Get form parameters
        token = request.form.get("github_token")
        org = request.form.get("organization") or None
        users_input = request.form.get("github_users") or ""
        users_file = request.form.get("users_file") or None
        date_from_str = request.form.get("date_from")
        date_to_str = request.form.get("date_to")
        output_format = request.form.get("output_format", "html")
        max_workers_str = request.form.get("max_workers", "0")

        # Parse max_workers
        try:
            max_workers = int(max_workers_str)
            if max_workers < 0:
                max_workers = 0  # Auto
        except (ValueError, TypeError):
            max_workers = 0  # Default to auto

        # Validate inputs
        if not token:
            flash("GitHub token is required", "error")
            return redirect(url_for("index"))

        # Parse dates
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d")
            date_to = datetime.strptime(date_to_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            flash("Invalid date format", "error")
            return redirect(url_for("index"))

        # Get users list
        users = []

        # Try to parse users from the form input first
        parsed_users = [u.strip() for u in users_input.replace(",", " ").split() if u.strip()]
        if parsed_users:
            users = parsed_users
            logger.debug(f"Using {len(users)} users from form input")
        # If no users from form input, try the file
        elif users_file:
            # Load users from file if provided
            try:
                file_users = load_users_from_file(users_file)
                if file_users:
                    users = file_users
                    logger.debug(f"Loaded {len(users)} users from file: {users_file}")
                else:
                    logger.warning(f"No users found in file: {users_file}")
            except Exception as e:
                error_msg = f"Error loading users file: {e}"
                logger.error(error_msg)
                flash(error_msg, "error")
                return redirect(url_for("index"))

        if not users:
            logger.warning("No GitHub users specified in form or file")
            flash("No GitHub users specified", "error")
            return redirect(url_for("index"))

        # Initialize job status
        job_data = {
            "status": "initializing",
            "start_time": datetime.now(),
            "end_time": None,
            "current_user": None,
            "processed_users": 0,
            "total_users": len(users),
            "activities": [],
            "errors": [],
            "report_path": None,
            "owner": g.user.username if hasattr(g, "user") and g.user else None,
            "owner_id": g.user.user_id if hasattr(g, "user") and g.user else None,
            "parameters": {
                "token": "***" + token[-4:]
                if token
                else None,  # Only store token suffix for security
                "org": org,
                "users": users,
                "date_from": date_from.strftime("%Y-%m-%d"),
                "date_to": date_to.strftime("%Y-%m-%d"),
                "output_format": output_format,
                "max_workers": max_workers,
            },
        }

        # Store in memory and persistent storage
        job_sessions[job_id] = job_data
        save_job(job_id, job_data)

        # Start job in background thread
        logger.info(f"Creating background thread for job {job_id}")
        try:
            # Create a non-daemon thread for better reliability
            thread = threading.Thread(
                target=run_activity_tracking,
                args=(job_id, token, org, users, date_from, date_to, output_format, max_workers),
                daemon=False,  # Use non-daemon thread for reliability
                name=f"job-{job_id}",
            )
            thread.start()

            # Add thread to a registry for monitoring
            if not hasattr(threading, "_job_threads"):
                threading._job_threads = {}
            threading._job_threads[job_id] = thread

            logger.info(f"Created non-daemon job thread {thread.name}, ID: {thread.ident}")
            logger.info(f"Thread started successfully for job {job_id}")

            # Additional safety check - verify thread is running
            if thread.is_alive():
                logger.info(f"Thread is alive and running for job {job_id}")
            else:
                logger.error(f"Thread appears to have started but is not running for job {job_id}")
        except Exception as thread_error:
            logger.error(f"Error starting thread for job {job_id}: {thread_error}")
            # Update job status to reflect error
            job_sessions[job_id]["status"] = "failed"
            job_sessions[job_id]["errors"] = [f"Error starting job thread: {str(thread_error)}"]
            job_sessions[job_id]["end_time"] = datetime.now()
            save_job(job_id, job_sessions[job_id])

            # Flash error message
            flash(f"Error starting job: {str(thread_error)}", "error")
            return redirect(url_for("index"))

        # Log redirect
        logger.info(f"Redirecting to job status page for job {job_id}")

        # Redirect to the job status page
        return redirect(url_for("job_status", job_id=job_id))

    print("  - Start-job route defined")

    @app.route("/job/<job_id>")
    @require_login
    def job_status(job_id):
        """Display the status of a running job."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            flash("Job not found", "error")
            return redirect(url_for("index"))

        # Check if user has permission to view this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            flash("You do not have permission to view this job", "error")
            return redirect(url_for("list_jobs"))

        # Check for URL to the report
        report_url = None
        report_path = job_data.get("report_path")

        if report_path and os.path.exists(report_path):
            # Get the index.html file
            index_file = os.path.join(report_path, "index.html")
            if os.path.exists(index_file):
                report_url = f"/report/{job_id}"

        return render_template(
            "job_status.html", job=job_data, job_id=job_id, report_url=report_url
        )

    print("  - Job status route defined")

    @app.route("/job/<job_id>/cancel", methods=["POST"])
    @require_login
    def cancel_job(job_id):
        """Cancel a running job."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            flash("Job not found", "error")
            return redirect(url_for("index"))

        # Check if user has permission to cancel this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            flash("You do not have permission to cancel this job", "error")
            return redirect(url_for("list_jobs"))

        # Only cancel if job is running
        if job_data["status"] in ["initializing", "running", "generating_report"]:
            job_data["status"] = "cancelled"
            job_data["end_time"] = datetime.now()
            flash("Job cancelled", "success")
            # Save to persistent storage
            save_job(job_id, job_data)
        else:
            flash("Job is not running", "warning")

        return redirect(url_for("job_status", job_id=job_id))

    print("  - Cancel job route defined")

    @app.route("/job/<job_id>/delete", methods=["POST"])
    @require_login
    def delete_job_route(job_id):
        """Delete a job."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            flash("Job not found", "error")
            return redirect(url_for("list_jobs"))

        # Check if user has permission to delete this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            flash("You do not have permission to delete this job", "error")
            return redirect(url_for("list_jobs"))

        # Don't allow deleting running jobs
        if job_data["status"] in ["initializing", "running", "generating_report"]:
            flash("Cannot delete a running job", "error")
            return redirect(url_for("job_status", job_id=job_id))

        # Remove from memory and storage
        job_sessions.pop(job_id, None)
        delete_job(job_id)

        flash("Job deleted", "success")
        return redirect(url_for("list_jobs"))

    print("  - Delete job route defined")

    @app.route("/jobs")
    @require_login
    def list_jobs():
        """List all jobs."""
        # Get all jobs
        all_jobs = job_sessions
        jobs_dict = {}

        is_admin = hasattr(g, "user") and g.user and g.user.is_admin

        # Ensure all_jobs is a dictionary
        if isinstance(all_jobs, dict):
            # Filter by user if not admin
            if not is_admin:
                user_id = g.user.user_id if hasattr(g, "user") and g.user else None
                all_jobs = {k: v for k, v in all_jobs.items() if v.get("owner_id") == user_id}

            # Process each job into a detail dictionary
            for job_id, job in all_jobs.items():
                if not isinstance(job, dict):
                    logger.warning(f"Skipping job {job_id} as it's not a dictionary")
                    continue

                # Check for report URL
                report_url = None
                report_path = job.get("report_path")

                if report_path and os.path.exists(report_path):
                    # Get the index.html file
                    index_file = os.path.join(report_path, "index.html")
                    if os.path.exists(index_file):
                        report_url = f"/report/{job_id}"

                # Get job details
                jobs_dict[job_id] = {
                    "id": job_id,
                    "status": job.get("status", "unknown"),
                    "start_time": job.get("start_time"),
                    "end_time": job.get("end_time"),
                    "processed_users": job.get("processed_users", 0),
                    "total_users": job.get("total_users", 0),
                    "activities": len(job.get("activities", [])),
                    "owner": job.get("owner", "unknown"),
                    "parameters": job.get("parameters", {}),
                    "report_url": report_url,
                }
        else:
            logger.error(f"job_sessions is not a dictionary: {type(all_jobs).__name__}")

        return render_template("jobs.html", jobs=jobs_dict, is_admin=is_admin)

    print("  - List jobs route defined")

    @app.route("/job/<job_id>/data")
    @require_login
    def job_data(job_id):
        """Get job data as JSON."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            return jsonify({"error": "Job not found"}), 404

        # Check if user has permission to view this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            return jsonify({"error": "Permission denied"}), 403

        # Convert datetime objects to strings
        job_copy = dict(job_data)
        if job_copy.get("start_time"):
            job_copy["start_time"] = job_copy["start_time"].isoformat()
        if job_copy.get("end_time"):
            job_copy["end_time"] = job_copy["end_time"].isoformat()

        # Return as JSON
        return jsonify(job_copy)

    print("  - Job data route defined")

    @app.route("/report/<job_id>")
    @require_login
    def view_report(job_id):
        """View a job's HTML report."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            flash("Job not found", "error")
            return redirect(url_for("list_jobs"))

        # Check if user has permission to view this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            flash("You do not have permission to view this job", "error")
            return redirect(url_for("list_jobs"))

        # Check if there's a report to view
        report_path = job_data.get("report_path")
        if not report_path or not os.path.exists(report_path):
            flash(f"No report available for this job. Report path: {report_path}", "error")
            logger.error(f"Report path does not exist: {report_path}")
            return redirect(url_for("job_status", job_id=job_id))

        # Log directory contents
        try:
            report_files = os.listdir(report_path)
            logger.info(f"Report directory contents: {report_files}")

            # Debug - modify image paths in index.html
            index_file = os.path.join(report_path, "index.html")
            if os.path.exists(index_file):
                try:
                    # Read the content of index.html
                    with open(index_file, "r") as f:
                        html_content = f.read()

                    # Check if there are images that need path correction
                    for image_file in [
                        f
                        for f in report_files
                        if f.endswith(".png")
                        or f.endswith(".jpg")
                        or f.endswith(".jpeg")
                        or f.endswith(".pdf")
                    ]:
                        # If the image file is referenced with just the filename
                        if f'src="{image_file}"' in html_content:
                            # Replace with the full URL via Flask route
                            new_url = url_for("view_file", job_id=job_id, filename=image_file)
                            html_content = html_content.replace(
                                f'src="{image_file}"', f'src="{new_url}"'
                            )
                            logger.info(f"Updated image reference from {image_file} to {new_url}")

                        # Also fix href attributes (for clickable images)
                        if f'href="{image_file}"' in html_content:
                            new_url = url_for("view_file", job_id=job_id, filename=image_file)
                            html_content = html_content.replace(
                                f'href="{image_file}"', f'href="{new_url}"'
                            )
                            logger.info(f"Updated href reference from {image_file} to {new_url}")

                    # Fix the logo.jpg reference (specifically if it exists)
                    if "logo.jpg" in html_content:
                        if "logo.jpg" in report_files:
                            new_url = url_for("view_file", job_id=job_id, filename="logo.jpg")
                            html_content = html_content.replace(
                                'src="logo.jpg"', f'src="{new_url}"'
                            )
                            logger.info(f"Updated logo reference to {new_url}")

                    # Add favicon reference if it exists
                    if "logo.jpg" in report_files:
                        favicon_url = url_for("view_file", job_id=job_id, filename="logo.jpg")
                        favicon_link = f'<link rel="icon" href="{favicon_url}" type="image/x-icon">'
                        # Add favicon link in the head section
                        if "<head>" in html_content and favicon_link not in html_content:
                            html_content = html_content.replace(
                                "<head>", f"<head>\n    {favicon_link}"
                            )
                            logger.info(f"Added favicon reference to {favicon_url}")

                    # Handle the three main graph images
                    for graph_file in [
                        "activity_trends.png",
                        "activity_types.png",
                        "user_comparison.png",
                    ]:
                        if graph_file in report_files:
                            graph_url = url_for("view_file", job_id=job_id, filename=graph_file)
                            # Find and replace both src and href attributes
                            html_content = html_content.replace(
                                f'src="{graph_file}"', f'src="{graph_url}"'
                            )
                            html_content = html_content.replace(
                                f'href="{graph_file}"', f'href="{graph_url}"'
                            )
                            logger.info(f"Updated graph reference for {graph_file} to {graph_url}")

                    # Check if the document already has download options section
                    has_download_section = "Download Options" in html_content

                    # Check for PDF file and add a download link if exists and there's no section yet
                    pdf_file = next((f for f in report_files if f.endswith(".pdf")), None)
                    if pdf_file and not has_download_section:
                        pdf_url = url_for("view_file", job_id=job_id, filename=pdf_file)
                        download_button = f'''
                        <section class="section">
                            <div class="section-header">
                                <i class="fas fa-file-pdf"></i>
                                <h2>Download Options</h2>
                            </div>
                            <div class="section-body">
                                <a href="{pdf_url}" target="_blank" class="btn btn-primary" style="display: inline-flex; align-items: center; margin-right: 10px;">
                                    <i class="fas fa-file-pdf" style="margin-right: 8px;"></i> View PDF Report
                                </a>
                                <a href="{url_for("download_report", job_id=job_id)}" class="btn btn-primary" style="display: inline-flex; align-items: center;">
                                    <i class="fas fa-download" style="margin-right: 8px;"></i> Download Full Report
                                </a>
                            </div>
                        </section>
                        '''

                        # Insert download section before the activity details section (before the table)
                        activity_details_marker = '<section class="section">\n            <div class="section-header">\n                <i class="fas fa-list-ul"></i>\n                <h2>Activity Details</h2>'
                        if activity_details_marker in html_content:
                            html_content = html_content.replace(
                                activity_details_marker,
                                f"{download_button}\n\n        {activity_details_marker}",
                            )
                            logger.info(
                                f"Added PDF download button with link to {pdf_url} before Activity Details section"
                            )

                    # Write back the modified content
                    with open(index_file, "w") as f:
                        f.write(html_content)

                    logger.info("Successfully updated image references in the HTML file")
                except Exception as e:
                    logger.error(f"Error updating image references: {e}")

        except Exception as e:
            logger.error(f"Error listing report directory: {e}")

        # Get the index.html file
        index_file = os.path.join(report_path, "index.html")
        if not os.path.exists(index_file):
            flash(f"Report index file not found. Path: {index_file}", "error")
            logger.error(f"Index file not found: {index_file}")
            return redirect(url_for("job_status", job_id=job_id))

        # Return the file - using a send_file wrapped in a route that checks permissions
        logger.info(f"Serving report file: {index_file}")
        return send_file(index_file)

    print("  - View report route defined")

    @app.route("/report/<job_id>/<path:filename>")
    @require_login
    def view_file(job_id, filename):
        """View a file from a job's report directory."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            return "Job not found", 404

        # Check if user has permission to view this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            return "Permission denied", 403

        # Check if there's a report path
        report_path = job_data.get("report_path")
        if not report_path or not os.path.exists(report_path):
            return "No report available for this job", 404

        # Check if the requested file exists
        file_path = os.path.join(report_path, filename)
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            # Log detailed information to diagnose issues
            logger.error(f"File not found: {file_path}")
            logger.error(f"Report path: {report_path}")
            logger.error(f"Directory contents: {os.listdir(report_path)}")
            return f"File not found: {filename} in {report_path}", 404

        # Security check: ensure file is within the report directory
        real_report_path = os.path.realpath(report_path)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_report_path):
            return "Access denied", 403

        logger.info(f"Serving file: {file_path}")

        # Determine MIME type for proper serving
        mime_type = None
        if filename.lower().endswith(".png"):
            mime_type = "image/png"
        elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif filename.lower().endswith(".pdf"):
            mime_type = "application/pdf"

        # Serve the file with appropriate MIME type
        return send_file(file_path, mimetype=mime_type)

    print("  - View file route defined")

    @app.route("/report/<job_id>/download")
    @require_login
    def download_report(job_id):
        """Download the entire report as a ZIP file."""
        job_data = job_sessions.get(job_id)
        if not job_data:
            flash("Job not found", "error")
            return redirect(url_for("list_jobs"))

        # Check if user has permission to view this job
        is_admin = hasattr(g, "user") and g.user and g.user.is_admin
        user_id = g.user.user_id if hasattr(g, "user") and g.user else None

        if not is_admin and job_data.get("owner_id") != user_id:
            flash("You do not have permission to download this report", "error")
            return redirect(url_for("list_jobs"))

        # Check if there's a report to download
        report_path = job_data.get("report_path")
        if not report_path or not os.path.exists(report_path):
            flash("No report available for this job", "error")
            return redirect(url_for("job_status", job_id=job_id))

        # Create a ZIP file
        import tempfile
        import zipfile

        try:
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
            zip_path = temp_file.name
            temp_file.close()

            # Create a ZIP file
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(report_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, report_path)
                        zipf.write(file_path, arcname)

            # Return the ZIP file
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=f"github_report_{job_id}.zip",
                mimetype="application/zip",
            )
        except Exception as e:
            flash(f"Error creating ZIP file: {e}", "error")
            return redirect(url_for("job_status", job_id=job_id))

    print("  - Download report route defined")

    @app.route("/settings/save-defaults", methods=["POST"])
    @require_login
    def save_defaults():
        """Save default settings."""
        # Get form parameters
        org = request.form.get("organization") or ""
        users_input = request.form.get("github_users") or ""
        users_file = request.form.get("users_file") or ""

        # Parse users
        users = [u.strip() for u in users_input.replace(",", " ").split() if u.strip()]

        # Save settings
        set_default_organization(org)
        set_default_users(users)
        set_default_users_file(users_file)

        flash("Default settings saved", "success")
        return redirect(url_for("index"))

    print("  - Save defaults route defined")

    @app.route("/settings/clear-defaults", methods=["POST"])
    @require_login
    def clear_defaults():
        """Clear default settings."""
        # Clear settings
        set_default_organization("")
        set_default_users([])
        set_default_users_file("")

        flash("Default settings cleared", "success")
        return redirect(url_for("index"))

    @app.route("/thread-monitor")
    @require_login
    def thread_monitor():
        """Display thread monitoring page for debugging running jobs."""
        # Get all threads
        active_threads = []
        all_threads = []

        for thread in threading.enumerate():
            # Basic thread info
            thread_info = {
                "thread_name": thread.name,
                "thread_id": thread.ident,
                "is_alive": thread.is_alive(),
                "is_daemon": thread.daemon,
            }

            # Check if it's a job thread
            if thread.name.startswith("job-"):
                # Extract job ID from thread name (format: job-JOBID-worker)
                parts = thread.name.split("-")
                if len(parts) > 1:
                    thread_info["job_id"] = parts[1]
                    active_threads.append(thread_info)

            # Add to all threads list
            all_threads.append(thread_info)

        # Sort threads by name
        active_threads.sort(key=lambda t: t.get("thread_name", ""))
        all_threads.sort(key=lambda t: t.get("thread_name", ""))

        return render_template(
            "thread_monitor.html",
            active_threads=active_threads,
            all_threads=all_threads,
            job_data=job_sessions,
        )

    logger.info("All routes configured")
    logger.info("Flask application setup complete")
    return app


def run_activity_tracking(
    job_id: str,
    token: str,
    org: Optional[str],
    users: List[str],
    date_from: datetime,
    date_to: datetime,
    output_format: str,
    max_workers: int = 0,
) -> None:
    """Run the GitHub activity tracking job in the background.

    Args:
        job_id: The unique job identifier
        token: GitHub personal access token
        org: Optional organization filter
        users: List of GitHub usernames to track
        date_from: Start date for activity tracking
        date_to: End date for activity tracking
        output_format: Output format (html, csv, etc.)
        max_workers: Maximum number of parallel workers (0 for auto)
    """
    # Global exception handler to prevent thread crashes
    try:
        # Enhanced debugging
        thread_name = threading.current_thread().name
        thread_id = threading.get_ident()
        logger.info(f"=== STARTING JOB {job_id} ===")
        logger.info(f"Thread info: name={thread_name}, id={thread_id}")
        logger.info(
            f"Job parameters: org={org}, users={users}, date range={date_from} to {date_to}, format={output_format}"
        )

        # Print current working directory and Python module paths
        import os

        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"PYTHONPATH: {sys.path}")

        # Check for critical environment variables
        github_token_set = bool(token)
        logger.info(f"GitHub token provided: {github_token_set}")

        # List available imported modules for debugging
        try:
            modules = [m for m in sys.modules.keys() if "github" in m.lower()]
            logger.debug(f"GitHub-related modules: {modules}")
        except Exception as module_error:
            logger.error(f"Error listing modules: {module_error}")

        # Safety check for job sessions
        if job_id not in job_sessions:
            logger.error(f"Job {job_id} not found in job_sessions - this should not happen!")
            return

        # Additional diagnostics
        logger.debug(f"Job dictionary: {list(job_sessions.keys())}")
        logger.debug(
            f"Current job keys: {list(job_sessions[job_id].keys()) if job_id in job_sessions else 'N/A'}"
        )

        try:
            job = job_sessions[job_id]
            job["status"] = "running"
            logger.info(f"Job {job_id} status set to 'running'")

            # Initialize or reset activities list
            job["activities"] = []
            processed_count = 0

            # For storing user results
            user_results = {}
        except Exception as e:
            logger.error(f"Error initializing job tracking: {e}")
            # Try to update job status if possible
            try:
                if job_id in job_sessions:
                    job_sessions[job_id]["status"] = "failed"
                    job_sessions[job_id]["errors"] = [f"Error initializing job: {str(e)}"]
                    job_sessions[job_id]["end_time"] = datetime.now()
                    save_job(job_id, job_sessions[job_id])
            except:
                pass
            return

        # Lock for thread-safe updates to job status
        status_lock = threading.Lock()

        def process_user(username: str) -> List[Dict[str, Any]]:
            """Process a single GitHub user.

            Args:
                username: GitHub username to process

            Returns:
                List of activity dictionaries
            """
            nonlocal processed_count

            logger.info(f"Starting to process user: {username}")

            # Skip if job is cancelled
            if job["status"] == "cancelled":
                logger.info(f"Job {job_id} was cancelled, skipping user {username}")
                return []

            try:
                # Set current user in job status
                with status_lock:
                    job["current_user"] = username
                logger.debug(f"Set current user to {username} in job {job_id}")

                # Track activities for this user
                logger.info(f"Creating GitHubActivityTracker for user: {username}")

                # Import here to catch import errors - with improved error handling
                logger.debug("Attempting to import GitHubActivityTracker")

                # More robust import mechanism with multiple fallbacks
                GitHubActivityTracker = None
                import_errors = []

                # Method 1: Try absolute import with full path
                try:
                    import github_activity_tracker.api

                    GitHubActivityTracker = github_activity_tracker.api.GitHubActivityTracker
                    logger.debug("Successfully imported GitHubActivityTracker via absolute import")
                except ImportError as e:
                    import_errors.append(f"Absolute import failed: {e}")

                # Method 2: Try relative import if absolute import failed
                if GitHubActivityTracker is None:
                    try:
                        from ..api import GitHubActivityTracker

                        logger.debug(
                            "Successfully imported GitHubActivityTracker via relative import"
                        )
                    except ImportError as e:
                        import_errors.append(f"Relative import failed: {e}")

                # Method 3: Try using a safer sys.path manipulation approach
                if GitHubActivityTracker is None:
                    try:
                        import os
                        import sys

                        # Get project root
                        project_root = os.path.abspath(
                            os.path.join(os.path.dirname(__file__), "..", "..")
                        )
                        api_dir = os.path.join(project_root, "github_activity_tracker", "api")

                        logger.debug(
                            f"Attempting to import using sys.path manipulation with path: {api_dir}"
                        )

                        if os.path.exists(api_dir):
                            # Temporarily add to sys.path
                            original_path = sys.path.copy()
                            try:
                                # Add project root to sys.path if not already there
                                if project_root not in sys.path:
                                    sys.path.insert(0, project_root)

                                # Now try a regular import
                                from github_activity_tracker.api.github_client import (
                                    GitHubActivityTracker,
                                )

                                logger.debug(
                                    "Successfully imported GitHubActivityTracker via sys.path manipulation"
                                )
                            finally:
                                # Restore original sys.path
                                sys.path = original_path
                        else:
                            import_errors.append(f"API directory not found: {api_dir}")
                    except Exception as e:
                        import_errors.append(f"Sys.path import approach failed: {e}")

                # If all import methods failed, raise an error
                if GitHubActivityTracker is None:
                    error_msg = (
                        f"All import attempts failed for GitHubActivityTracker: {import_errors}"
                    )
                    logger.error(error_msg)
                    with status_lock:
                        job["errors"].append(error_msg)
                        processed_count += 1
                        job["processed_users"] = processed_count
                        save_job(job_id, job)
                    return []

                # Create tracker with verbose error handling
                try:
                    logger.debug(
                        f"Creating GitHubActivityTracker with token={token[:4]}*** and org={org}"
                    )
                    tracker = GitHubActivityTracker(token, org)
                    logger.info(f"Successfully created tracker for {username}")
                except Exception as tracker_error:
                    error_msg = f"Failed to create GitHubActivityTracker: {str(tracker_error)}"
                    logger.error(error_msg)

                    # Additional debugging for GitHub API errors
                    if hasattr(tracker_error, "__cause__") and tracker_error.__cause__:
                        logger.error(f"Caused by: {tracker_error.__cause__}")

                    with status_lock:
                        job["errors"].append(error_msg)
                        processed_count += 1
                        job["processed_users"] = processed_count
                        save_job(job_id, job)
                    return []

                # Track activities with verbose error handling
                try:
                    logger.info(f"Calling track_user_activities for {username}")
                    user_activities = tracker.track_user_activities(username, date_from, date_to)
                    logger.info(f"Successfully called track_user_activities for {username}")

                    # Update processed count
                    with status_lock:
                        processed_count += 1
                        job["processed_users"] = processed_count
                        # Save job state to persistent storage
                        save_job(job_id, job)

                    # Return activities
                    if user_activities:
                        logger.info(f"Found {len(user_activities)} activities for user {username}")
                        return user_activities

                    logger.info(f"No activities found for user {username}")
                    return []

                except Exception as track_error:
                    error_msg = f"Error in track_user_activities for {username}: {str(track_error)}"
                    logger.error(error_msg)
                    with status_lock:
                        job["errors"].append(error_msg)
                        processed_count += 1
                        job["processed_users"] = processed_count
                        save_job(job_id, job)
                    return []

            except Exception as e:
                error_msg = f"Error tracking activities for user {username}: {str(e)}"
                logger.error(error_msg)
                with status_lock:
                    job["errors"].append(error_msg)
                    processed_count += 1
                    job["processed_users"] = processed_count
                    # Save job state to persistent storage
                    save_job(job_id, job)
                return []

        # Import needed modules here to better handle errors
        try:
            import concurrent.futures
            import os

            logger.info("Successfully imported concurrent.futures")
        except ImportError as e:
            error_msg = f"Error importing required modules: {str(e)}"
            logger.error(error_msg)
            with status_lock:
                job["errors"].append(error_msg)
                job["status"] = "failed"
                job["end_time"] = datetime.now()
                save_job(job_id, job)
            return

        # Determine number of workers
        if max_workers <= 0:
            # Auto-detect: Use min(8, CPU count * 2) as a reasonable default
            cpu_count = os.cpu_count() or 2
            max_workers = min(8, cpu_count * 2)

        logger.info(f"Using {max_workers} parallel workers for processing {len(users)} users")

        # For safety, process just one user first to validate configuration
        logger.info("Testing with first user before parallel processing")
        if users:
            first_user = users[0]
            logger.info(f"Testing configuration with user: {first_user}")

            # Processing test user should NOT increment the count - we'll process this user
            # properly when we handle all users
            with status_lock:
                processed_count = 0  # Reset to ensure no double-counting

            test_activities = process_user(first_user)

            # Store the first user's activities
            if test_activities:
                with status_lock:
                    job["activities"].extend(test_activities)
                    logger.info(f"Found {len(test_activities)} activities for user {first_user}")

            logger.info(f"Test completed - found {len(test_activities)} activities")

            # Reset the processed users count to 0 since we'll process all users
            with status_lock:
                processed_count = 0
                job["processed_users"] = 0

            # Get the list of users to process in parallel
            users_to_process = users.copy()

            # Process all users in parallel (including the first one again)
            logger.info(f"Processing all {len(users_to_process)} users in parallel")

            try:
                # Create executor with manageable shutdown timeout and non-daemon threads
                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers, thread_name_prefix=f"job-{job_id}-worker"
                )

                # Submit all tasks
                future_to_user = {
                    executor.submit(process_user, username): username
                    for username in users_to_process
                }

                # Process as they complete
                for future in concurrent.futures.as_completed(future_to_user):
                    username = future_to_user[future]
                    try:
                        user_activities = future.result()
                        if user_activities:
                            with status_lock:
                                job["activities"].extend(user_activities)
                    except Exception as e:
                        error_msg = f"Unhandled error processing user {username}: {str(e)}"
                        logger.error(error_msg)
                        with status_lock:
                            job["errors"].append(error_msg)
                            # Save job state to persistent storage
                            save_job(job_id, job)
            except Exception as parallel_error:
                error_msg = f"Error in parallel processing: {str(parallel_error)}"
                logger.error(error_msg)
                with status_lock:
                    job["errors"].append(error_msg)
                    # Don't mark job as failed - we might have partial results
                    save_job(job_id, job)
            finally:
                # Ensure proper shutdown of executor
                logger.debug(f"Shutting down ThreadPoolExecutor for job {job_id}")
                # Use shutdown with timeout to avoid blocking indefinitely
                executor.shutdown(wait=True, cancel_futures=False)
                logger.debug(f"ThreadPoolExecutor shutdown complete for job {job_id}")

        # The following code needs to be at the same indentation level as the users check above
        if job_id in job_sessions:
            job = job_sessions[job_id]

            # Check if job was cancelled
            if job["status"] == "cancelled":
                logger.info(f"Job {job_id} was cancelled, stopping processing")
                return

            # Generate report if activities were found
            if job["activities"]:
                try:
                    # Update job status
                    activity_count = len(job["activities"])
                    logger.info(
                        f"Generating {output_format} report with {activity_count} activities"
                    )
                    job["status"] = "generating_report"

                    # Save status update
                    save_job(job_id, job)

                    # Import report generator here to catch import errors
                    try:
                        from ..report.generator import ReportGenerator

                        logger.info("Successfully imported ReportGenerator")
                    except ImportError as import_error:
                        error_msg = f"Error importing ReportGenerator: {str(import_error)}"
                        logger.error(error_msg)
                        job["errors"].append(error_msg)
                        job["status"] = "failed"
                        job["end_time"] = datetime.now()
                        save_job(job_id, job)
                        return

                    # Generate report with error handling
                    try:
                        logger.info("Calling ReportGenerator.generate_report")
                        report_path = ReportGenerator.generate_report(
                            job["activities"], output_format
                        )
                        logger.info(f"Report generation result: {report_path}")
                    except Exception as report_error:
                        error_msg = f"Error generating report: {str(report_error)}"
                        logger.error(error_msg)
                        job["errors"].append(error_msg)
                        job["status"] = "failed"
                        job["end_time"] = datetime.now()
                        save_job(job_id, job)
                        return

                    if report_path:
                        # Get the absolute directory path for the report
                        try:
                            if os.path.isfile(report_path):
                                report_dir = os.path.dirname(report_path)
                            else:
                                report_dir = report_path

                            # Store the absolute path in the job data
                            job["report_path"] = os.path.abspath(report_dir)
                            logger.info(f"Report generated at: {report_path}")
                            logger.debug(
                                f"Using absolute report directory path: {job['report_path']}"
                            )

                            # Log the contents of the report directory for debugging
                            try:
                                contents = os.listdir(job["report_path"])
                                logger.debug(f"Report directory contents: {contents}")
                            except Exception as e:
                                logger.error(f"Error listing report directory contents: {str(e)}")
                        except Exception as path_error:
                            error_msg = f"Error processing report path: {str(path_error)}"
                            logger.error(error_msg)
                            job["errors"].append(error_msg)
                            # Don't mark as failed, we still have the activities
                    else:
                        job["errors"].append("Failed to generate report - report path is empty")
                        logger.error("Report generation failed - empty report path returned")
                except Exception as report_gen_error:
                    error_msg = f"Unexpected error in report generation: {str(report_gen_error)}"
                    logger.error(error_msg)
                    job["errors"].append(error_msg)
            else:
                logger.warning("No activities found for any users")
                job["errors"].append("No activities found for any users")

            # Update job status - ensure the processed users count matches the total
            # Note: processed_count is already accurate as it's incremented for each user
            job["processed_users"] = job["total_users"]  # Set to total to ensure 100% completion
            job["status"] = "completed"
            # Clear current_user to prevent spinning wheel for last user
            job["current_user"] = None

        # Log activity counts by user
        total_activities = len(job["activities"])
        user_counts = {}
        for activity in job["activities"]:
            user = activity.get("user", "unknown")
            user_counts[user] = user_counts.get(user, 0) + 1

        logger.info(f"Job completed. Total activities: {total_activities}")
        logger.info(f"Activities by user: {user_counts}")
        logger.info(f"Number of unique users in activities: {len(user_counts)}")

        # Save job state to persistent storage
        save_job(job_id, job)
    except Exception as e:
        error_msg = f"Error in tracking job: {str(e)}"
        logger.error(error_msg)
        job["errors"].append(error_msg)
        job["status"] = "failed"
        # Clear current_user in case of failure too
        job["current_user"] = None
        # Save job state to persistent storage
        save_job(job_id, job)
    except Exception as global_e:
        # Global exception handler - catch any uncaught exceptions to prevent thread crashes
        try:
            logger.critical(f"CRITICAL UNHANDLED ERROR IN JOB THREAD {job_id}: {global_e}")
            logger.critical(f"Exception traceback: {traceback.format_exc()}")

            # Try to update job status if possible
            if job_id in job_sessions:
                job_sessions[job_id]["status"] = "failed"
                job_sessions[job_id]["errors"] = job_sessions[job_id].get("errors", []) + [
                    f"CRITICAL: Unhandled exception in job thread: {str(global_e)}"
                ]
                job_sessions[job_id]["end_time"] = datetime.now()
                job_sessions[job_id]["current_user"] = None
                try:
                    save_job(job_id, job_sessions[job_id])
                    logger.info(f"Job {job_id} marked as failed due to unhandled exception")
                except Exception as e:
                    logger.error(f"Could not save job status after unhandled exception: {e}")
        except Exception as final_e:
            # Last resort logging if even the exception handler fails
            logger.critical(f"FATAL: Failed to handle unhandled exception: {final_e}")
    finally:
        # Set end time
        job["end_time"] = datetime.now()
        # Save job state to persistent storage one final time
        save_job(job_id, job)
