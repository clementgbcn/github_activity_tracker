"""Unit tests for logger utility classes and functions."""

import logging
import unittest
from unittest.mock import Mock, patch

from github_activity_tracker.utils.logger_utils import (
    LevelOffsetLogger,
    configure_github_retry_logger,
)


class TestLevelOffsetLogger(unittest.TestCase):
    """Tests for the LevelOffsetLogger adapter."""

    def setUp(self):
        # Create a mock logger for testing
        self.mock_logger = Mock(spec=logging.Logger)
        self.offset_logger = LevelOffsetLogger(self.mock_logger)

    def test_debug_to_info(self):
        """Test DEBUG message is logged at INFO level."""
        self.offset_logger.debug("test message")
        self.mock_logger.log.assert_called_once_with(logging.INFO, "test message")

    def test_info_to_warning(self):
        """Test INFO message is logged at WARNING level."""
        self.offset_logger.info("test message")
        self.mock_logger.log.assert_called_once_with(logging.WARNING, "test message")

    def test_warning_to_error(self):
        """Test WARNING message is logged at ERROR level."""
        self.offset_logger.warning("test message")
        self.mock_logger.log.assert_called_once_with(logging.ERROR, "test message")

    def test_error_to_critical(self):
        """Test ERROR message is logged at CRITICAL level."""
        self.offset_logger.error("test message")
        self.mock_logger.log.assert_called_once_with(logging.CRITICAL, "test message")

    def test_critical_remains_critical(self):
        """Test CRITICAL message remains at CRITICAL level."""
        self.offset_logger.critical("test message")
        self.mock_logger.log.assert_called_once_with(logging.CRITICAL, "test message")

    def test_log_method_with_offset(self):
        """Test the generic log method applies the level offset."""
        self.offset_logger.log(logging.DEBUG, "test message")
        self.mock_logger.log.assert_called_once_with(logging.INFO, "test message")

    def test_exception_with_offset(self):
        """Test the exception method applies the level offset."""
        # The exception method typically logs at ERROR level, so should be CRITICAL
        self.offset_logger.exception("test message")
        self.mock_logger.log.assert_called_once()
        args, kwargs = self.mock_logger.log.call_args
        self.assertEqual(args[0], logging.CRITICAL)  # First arg is the level
        self.assertEqual(args[1], "test message")  # Second arg is the message
        self.assertTrue(kwargs.get("exc_info"))  # Should have exc_info=True

    def test_attribute_delegation(self):
        """Test that other attributes are delegated to the base logger."""
        # Set a test attribute on the mock logger
        self.mock_logger.test_attr = "test_value"
        # Access it via the offset logger
        value = self.offset_logger.test_attr
        self.assertEqual(value, "test_value")


class TestConfigureGithubRetryLogger(unittest.TestCase):
    """Tests for the configure_github_retry_logger function."""

    def test_configure_github_retry_logger(self):
        """Test configuring a GithubRetry instance with LevelOffsetLogger."""
        # Create a mock GithubRetry instance
        mock_github_retry = Mock()
        # Mock getattr to control access to _GithubRetry__logger
        mock_logger = Mock(spec=logging.Logger)

        # Call the function
        configure_github_retry_logger(mock_github_retry, mock_logger)

        # Verify the logger was set
        self.assertTrue(hasattr(mock_github_retry, "_GithubRetry__logger"))

        # Check that the logger is a LevelOffsetLogger
        github_retry_logger = mock_github_retry._GithubRetry__logger
        self.assertIsInstance(github_retry_logger, LevelOffsetLogger)

        # Verify it's using our mock logger
        self.assertEqual(github_retry_logger._logger, mock_logger)

    def test_configure_github_retry_logger_handles_errors(self):
        """Test error handling when configuring the logger fails."""
        # Create a mock GithubRetry that will raise AttributeError
        mock_github_retry = Mock()
        del mock_github_retry._GithubRetry__logger  # Ensure the attribute doesn't exist

        # Make sure setting the attribute raises AttributeError
        type(mock_github_retry).__setattr__ = Mock(side_effect=AttributeError)

        mock_logger = Mock(spec=logging.Logger)

        # Call the function - it should handle the exception
        with patch(
            "github_activity_tracker.utils.logger_utils.LevelOffsetLogger"
        ) as mock_level_logger:
            configure_github_retry_logger(mock_github_retry, mock_logger)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            mock_logger.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
