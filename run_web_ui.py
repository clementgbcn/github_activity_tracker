#!/usr/bin/env python3
"""
Run the GitHub Activity Tracker Web UI.

This script starts a Flask web server for the GitHub Activity Tracker UI.
"""

import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add the project root to the Python path to ensure modules can be found
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Setup DataDog tracing if DATADOG_ENABLED environment variable is set
if os.getenv("DATADOG_ENABLED", "false").lower() == "true":
    try:
        import ddtrace

        logging.info("DataDog tracing enabled")
    except ImportError:
        logging.warning("DataDog tracing requested but ddtrace package not installed")

from github_activity_tracker.utils import set_debug_mode
from github_activity_tracker.utils.logging_config import logger
from github_activity_tracker.utils.werkzeug_logging import init_werkzeug_logging

# Import web app after utils to ensure all dependencies are loaded
from github_activity_tracker.web import create_app

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Set debug mode if specified in environment
if os.getenv("DEBUG", "false").lower() == "true":
    set_debug_mode()

# Ensure data directory exists
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
Path(data_dir).mkdir(parents=True, exist_ok=True)

# Generate a secret key for the app if not already set in environment
if not os.getenv("SECRET_KEY"):
    secret_key = secrets.token_hex(24)
    os.environ["SECRET_KEY"] = secret_key

    # Add to .env file if possible
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        try:
            with open(env_file, "r") as f:
                env_lines = f.readlines()

            # Check if SECRET_KEY is already in .env
            has_secret_key = any(line.startswith("SECRET_KEY=") for line in env_lines)

            if not has_secret_key:
                with open(env_file, "a") as f:
                    f.write(
                        f"\n# Auto-generated secret key for Flask sessions\nSECRET_KEY={secret_key}\n"
                    )
        except:
            logging.warning("Could not update .env file with secret key")

# Create the Flask application
try:
    print("Creating Flask application...")
    app = create_app()
    print("Flask application created successfully")
except Exception as e:
    import traceback

    print(f"ERROR: Failed to create Flask application: {e}")
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description="Run the GitHub Activity Tracker Web UI")
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("PORT", 5000)),
            help="Port to run the server on (default: 5000 or PORT env var)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default=os.getenv("HOST", "127.0.0.1"),
            help="Host to run the server on (default: 127.0.0.1 or HOST env var)",
        )
        args = parser.parse_args()

        # Get port from args or environment
        port = args.port

        # Get host from args or environment
        host = args.host

        # Run the app
        print(f"Starting GitHub Activity Tracker Web UI on http://{host}:{port}")

        # Display default admin credentials if they exist
        if (
            hasattr(app, "config")
            and "DEFAULT_ADMIN_USERNAME" in app.config
            and "DEFAULT_ADMIN_PASSWORD" in app.config
        ):
            print("\n==============================================================")
            print("  FIRST TIME SETUP: DEFAULT ADMIN CREDENTIALS CREATED")
            print("==============================================================")
            print(f"  Username: {app.config['DEFAULT_ADMIN_USERNAME']}")
            print(f"  Password: {app.config['DEFAULT_ADMIN_PASSWORD']}")
            print("\n  IMPORTANT: Log in and change this password immediately!")
            print("==============================================================\n")

        debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
        print(f"Debug mode: {debug_mode}")

        # Initialize custom Werkzeug logging handler
        logger.info("Initializing custom Werkzeug logging")
        custom_request_handler = init_werkzeug_logging()

        # Run the Flask app with custom request handler
        app.run(host=host, port=port, debug=debug_mode, request_handler=custom_request_handler)
    except Exception as e:
        import traceback

        print(f"ERROR: Failed to start Flask application: {e}")
        traceback.print_exc()
        sys.exit(1)
