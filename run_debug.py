#!/usr/bin/env python3
"""
Debug launcher for GitHub Activity Tracker.

This script starts the application with enhanced debugging
options enabled for easier troubleshooting.
"""

import logging
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

# Import app creator after configuring environment
from github_activity_tracker.utils import set_debug_mode
from github_activity_tracker.web import create_app

# Add the project root to the Python path to ensure modules can be found
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Set environment variables for debugging
os.environ["DEBUG"] = "true"
os.environ["FLASK_DEBUG"] = "true"

# Configure enhanced logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("debug.log", mode="w")],
)

logger = logging.getLogger("debug_launcher")
logger.info("Starting Debug Mode launcher")

# Load environment variables
load_dotenv()
logger.info("Loaded environment variables from .env")

# Enable debug mode
set_debug_mode(True)
logger.info("Debug mode enabled")

# Ensure data directory exists
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
Path(data_dir).mkdir(parents=True, exist_ok=True)
logger.info(f"Ensured data directory exists: {data_dir}")

# Set a debug secret key if not already set
if not os.getenv("SECRET_KEY"):
    secret_key = secrets.token_hex(24)
    os.environ["SECRET_KEY"] = secret_key
    logger.info("Generated debug secret key")

# Create the Flask application with additional debug configuration
logger.info("Creating Flask application in debug mode...")
app = create_app()


# Add additional debug-only routes
@app.route("/debug-console")
def debug_console():
    """Debug console to examine application state."""
    from github_activity_tracker.utils.job_storage import debug_jobs_file, load_jobs

    # Get job information
    debug_jobs_file()
    jobs = load_jobs()

    # Generate job summary
    job_summary = [
        f"<strong>Job ID:</strong> {job_id}<br>"
        f"<strong>Status:</strong> {job.get('status', 'unknown')}<br>"
        f"<strong>Users:</strong> {job.get('total_users', 0)}<br>"
        f"<strong>Start:</strong> {job.get('start_time', 'N/A')}<br>"
        f"<hr>"
        for job_id, job in jobs.items()
    ]

    # Generate debug information
    debug_info = {
        "Environment": {
            k: v for k, v in os.environ.items() if k.startswith(("GITHUB_", "DEBUG", "FLASK"))
        },
        "Job Count": len(jobs),
        "Modules": list(sys.modules.keys()),
        "Python Path": sys.path,
    }

    debug_html = "<h2>Debug Information</h2>"
    for section, data in debug_info.items():
        debug_html += f"<h3>{section}</h3>"
        debug_html += "<pre>"
        if isinstance(data, dict):
            for k, v in data.items():
                debug_html += f"{k}: {v}\n"
        elif isinstance(data, list):
            debug_html += "\n".join(data[:100]) + ("..." if len(data) > 100 else "")
        else:
            debug_html += str(data)
        debug_html += "</pre>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Console</title>
        <style>
            body {{ font-family: monospace; padding: 20px; }}
            h1, h2, h3 {{ color: #0366d6; }}
            pre {{ background: #f6f8fa; padding: 15px; border-radius: 5px; overflow: auto; }}
            .jobs {{ display: flex; flex-wrap: wrap; gap: 10px; }}
            .job-card {{ border: 1px solid #e1e4e8; border-radius: 5px; padding: 10px; width: 300px; }}
        </style>
    </head>
    <body>
        <h1>GitHub Activity Tracker Debug Console</h1>

        <h2>Jobs ({len(jobs)})</h2>
        <div class="jobs">
            {"".join([f'<div class="job-card">{summary}</div>' for summary in job_summary])}
        </div>

        {debug_html}

        <div style="margin-top: 20px">
            <a href="/" style="color: #0366d6">Back to Application</a>
        </div>
    </body>
    </html>
    """  # noqa: E501


if __name__ == "__main__":
    # Run with enhanced debug settings
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 5000))

    logger.info(f"Starting server on http://{host}:{port} with DEBUG=True")
    logger.info("Visit /debug-console to access the debug interface")

    app.run(host=host, port=port, debug=True, use_reloader=True, use_debugger=True, threaded=True)
