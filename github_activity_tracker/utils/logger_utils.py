"""Logging utilities for GitHub Activity Tracker.

This module provides specialized logging adapters and utilities to enhance
the logging capabilities of the application.
"""

import logging
from typing import Any, Dict, Union


class LevelOffsetLogger:
    """A logger adapter that shifts log levels up by one level.

    This class provides a wrapper around a standard logger that increases the
    severity of each log message. For example, messages logged at DEBUG level
    will be sent to the underlying logger at INFO level. This is useful when
    integrating with third-party libraries whose logging levels do not align
    with the application's desired verbosity.

    Attributes:
        LEVEL_MAP: A mapping of standard logging levels to their higher counterparts
    """

    # Map each level to one level higher
    LEVEL_MAP: Dict[int, int] = {
        logging.DEBUG: logging.INFO,
        logging.INFO: logging.WARNING,
        logging.WARNING: logging.ERROR,
        logging.ERROR: logging.CRITICAL,
        logging.CRITICAL: logging.CRITICAL,  # No level above CRITICAL
    }

    def __init__(self, base_logger: Union[logging.Logger, "LevelOffsetLogger"]) -> None:
        """Initialize the LevelOffsetLogger with a base logger.

        Args:
            base_logger: The underlying logger to which messages will be delegated
                         with increased severity levels
        """
        self._logger = base_logger

    def _log_with_offset(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a message at the specified level with an offset applied.

        Args:
            level: The original logging level
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        new_level = self.LEVEL_MAP.get(level, level)
        self._logger.log(new_level, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a DEBUG level message (will be logged at INFO level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an INFO level message (will be logged at WARNING level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a WARNING level message (will be logged at ERROR level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an ERROR level message (will be logged at CRITICAL level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a CRITICAL level message (remains at CRITICAL level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(logging.CRITICAL, msg, *args, **kwargs)

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a message at the specified level with an offset applied.

        Args:
            level: The original logging level
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        self._log_with_offset(level, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an exception with traceback (at CRITICAL level).

        Args:
            msg: The message to log
            *args: Additional positional arguments to pass to the logger
            **kwargs: Additional keyword arguments to pass to the logger
        """
        # Exception is typically logged at ERROR level, so we map it to CRITICAL
        exc_info = kwargs.get("exc_info", True)
        kwargs["exc_info"] = exc_info
        self._log_with_offset(logging.ERROR, msg, *args, **kwargs)

    # Optional: expose any other attributes/methods from the base logger
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the underlying logger.

        Args:
            name: The name of the attribute to access

        Returns:
            The attribute from the base logger
        """
        return getattr(self._logger, name)


def configure_github_retry_logger(github_retry_instance: Any, base_logger: logging.Logger) -> None:
    """Configure a GithubRetry instance to use a LevelOffsetLogger.

    This function configures a GithubRetry instance to use a LevelOffsetLogger
    adapter for its internal logging, which helps reduce noise in application logs
    by shifting GitHub retry messages to higher severity levels.

    Args:
        github_retry_instance: An instance of github.GithubRetry
        base_logger: The base logger to be adapted with level offset
    """
    try:
        # Create a LevelOffsetLogger adapter for the base logger
        offset_logger = LevelOffsetLogger(base_logger)

        # Set the logger on the GithubRetry instance
        # Note: Using a private attribute with double underscore mangling
        github_retry_instance._GithubRetry__logger = offset_logger
    except AttributeError as e:
        # Handle case where GithubRetry's internal structure has changed
        base_logger.error(f"Failed to configure GithubRetry logger: {e}")
        base_logger.warning("GithubRetry will use its default logging behavior")
