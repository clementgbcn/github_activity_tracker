"""Werkzeug logging configuration for GitHub Activity Tracker.

This module redirects Werkzeug logs to our application logger by
replacing the default Werkzeug logger implementation.
"""

import logging

from werkzeug.serving import WSGIRequestHandler

from .logging_config import logger as app_logger


# Create a wrapper function that will redirect Werkzeug logs to our application logger
class CustomWSGIRequestHandler(WSGIRequestHandler):
    """Custom WSGI request handler that uses our application logger for Werkzeug logs."""

    def log(self, logger_type, message, *args):
        """Override the default log method to use our application logger."""
        # Map Werkzeug log types to logging levels
        level_mapping = {"info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}

        # Get the corresponding logging level or default to INFO
        level = level_mapping.get(logger_type, logging.INFO)

        # Format message with any provided args
        if args:
            message = message % args

        # Log the message using our application logger
        app_logger.log(level, f"[Werkzeug] {message}")


def init_werkzeug_logging():
    """Initialize Werkzeug to use our application logger.

    This function should be called before starting the Flask application
    to ensure that all Werkzeug logs are redirected to our application logger.
    """
    # Disable the default Werkzeug logger
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.disabled = True
    werkzeug_logger.propagate = False

    # Clear any existing handlers
    if werkzeug_logger.handlers:
        werkzeug_logger.handlers.clear()

    # Add a NullHandler to prevent any warnings about no handlers
    werkzeug_logger.addHandler(logging.NullHandler())

    # Log the initialization
    app_logger.info("Initialized Werkzeug logging redirection")

    return CustomWSGIRequestHandler
