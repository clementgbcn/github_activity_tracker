"""Logging configuration for the GitHub Activity Tracker."""

import datetime
import json
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

import colorlog
import json_log_formatter

# Configure logging with colors
logger = logging.getLogger("github_activity_tracker")

# Prevent propagation to root logger to avoid duplicate logs
logger.propagate = False

# Remove any existing handlers (in case the module is reloaded)
if logger.handlers:
    logger.handlers = []

# Create console handler with color formatting
console_handler = colorlog.StreamHandler(stream=sys.stdout)

# Create a colorlog formatter for console
colored_formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
    secondary_log_colors={},
    style="%",
)

console_handler.setFormatter(colored_formatter)
logger.addHandler(console_handler)


# Custom JSON formatter using json-log-formatter
class CustomJSONFormatter(json_log_formatter.JSONFormatter):
    """
    JSON formatter that produces structured logs with enhanced metadata.
    """

    def json_record(self, message, extra, record):
        # Create the base log record
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": message,
            "logger_name": record.name,
            "filename": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": "".join(traceback.format_exception(*record.exc_info)),
            }

        # Add any extra fields provided
        if extra:
            log_data.update(extra)

        # Add custom fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "id",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
                # Skip fields that are already included or not needed
                "msg_fmt",
                "args_fmt",
                "exc_text_fmt",
            ):
                try:
                    # Check if the value is JSON serializable
                    json.dumps({key: value})
                    log_data[key] = value
                except (TypeError, OverflowError):
                    # If value can't be JSON serialized, convert to string
                    log_data[key] = str(value)

        return log_data


# Create file handler for logging to /tmp/github-activity-tracker.json (JSON format)
log_file_path = os.environ.get("LOG_FILE_PATH", "/tmp/github-activity-tracker.json")

# Create the log directory if it doesn't exist (for non-standard paths)
log_dir = os.path.dirname(log_file_path)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create log directory {log_dir}: {e}")

try:
    # Use RotatingFileHandler to prevent the log file from growing too large
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )

    # JSON formatter using json-log-formatter
    json_formatter = CustomJSONFormatter()

    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)

    # Log information about logging setup (only to console)
    console_handler.handle(
        logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg=f"Logging to file (JSON format): {log_file_path}",
            args=(),
            exc_info=None,
        )
    )
except Exception as e:
    print(f"Warning: Could not set up file logging to {log_file_path}: {e}")

# Set default log level
logger.setLevel(logging.INFO)  # Default level, can be changed with --debug flag


def set_debug_mode(enable_debug=True):
    """Set the logger to debug mode if enabled."""
    if enable_debug:
        logger.setLevel(logging.DEBUG)

        # Create a special debug message (only to console)
        console_handler.handle(
            logging.LogRecord(
                name=logger.name,
                level=logging.DEBUG,
                pathname=__file__,
                lineno=0,
                msg=f"Debug logging enabled - logs will be written to console and {log_file_path}",
                args=(),
                exc_info=None,
            )
        )

        # Set debug level for all handlers to ensure they all show debug messages
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

        # Reset handler levels
        for handler in logger.handlers:
            handler.setLevel(logging.NOTSET)  # Use the logger's level
