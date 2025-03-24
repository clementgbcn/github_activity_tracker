"""Tests for utility functions in the github_activity_tracker.utils package."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from github_activity_tracker.utils import load_users_from_file
from github_activity_tracker.utils.email_sender import EmailSender


def test_load_users_from_nonexistent_file():
    """Test loading users from a nonexistent file."""
    result = load_users_from_file("nonexistent_file.txt")
    assert result is None


def test_load_users_from_empty_file():
    """Test loading users from an empty file."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        pass  # Create empty file

    try:
        result = load_users_from_file(f.name)
        assert result == []
    finally:
        # Clean up the file
        os.unlink(f.name)


def test_load_users_from_file():
    """Test loading users from a file with valid content."""
    expected_users = ["user1", "user2", "user3"]

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write("\n".join(expected_users))
        f.flush()

    try:
        result = load_users_from_file(f.name)
        assert result == expected_users
    finally:
        # Clean up the file
        os.unlink(f.name)


def test_load_users_with_comments_and_blanks():
    """Test loading users from a file with comments and blank lines."""
    file_content = """
    # This is a comment
    user1

    # Another comment
    user2
    user3
    """
    expected_users = ["user1", "user2", "user3"]

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        f.write(file_content)
        f.flush()

    try:
        result = load_users_from_file(f.name)
        assert result == expected_users
    finally:
        # Clean up the file
        os.unlink(f.name)


@patch.dict(
    os.environ,
    {
        "EMAIL_ENABLED": "true",
        "EMAIL_SENDER": "test@example.com",
        "EMAIL_PASSWORD": "password123",
        "EMAIL_SMTP_SERVER": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_RECIPIENTS": "recipient1@example.com,recipient2@example.com",
        "EMAIL_SUBJECT_PREFIX": "[Test]",
    },
)
def test_email_sender_initialization():
    """Test EmailSender initialization with environment variables."""
    sender = EmailSender()

    assert sender.enabled is True
    assert sender.sender == "test@example.com"
    assert sender.password == "password123"
    assert sender.smtp_server == "smtp.example.com"
    assert sender.smtp_port == 587
    assert sender.recipients == ["recipient1@example.com", "recipient2@example.com"]
    assert sender.subject_prefix == "[Test]"


@patch.dict(os.environ, {"EMAIL_ENABLED": "false"})
def test_email_sender_disabled():
    """Test EmailSender when disabled."""
    sender = EmailSender()
    assert sender.enabled is False


@patch.dict(
    os.environ,
    {
        "EMAIL_ENABLED": "true",
        "EMAIL_SENDER": "test@example.com",
        "EMAIL_PASSWORD": "password123",
        "EMAIL_SMTP_SERVER": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_RECIPIENTS": "recipient@example.com",
    },
)
@patch("smtplib.SMTP")
def test_send_html_report(mock_smtp):
    """Test sending an HTML report via email."""
    # Create a mock SMTP instance
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

    # Create a temporary directory to simulate an HTML report
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock HTML file
        html_path = os.path.join(temp_dir, "index.html")
        with open(html_path, "w") as f:
            f.write("<html><body>Test report</body></html>")

        # Create the sender and send the report
        sender = EmailSender()
        result = sender.send_report(
            report_path=temp_dir,
            start_date=MagicMock(strftime=lambda fmt: "2023-01-01"),
            end_date=MagicMock(strftime=lambda fmt: "2023-01-31"),
            user_count=5,
            activity_count=100,
        )

        # Assert the email was sent successfully
        assert result is True
        mock_smtp_instance.send_message.assert_called_once()


@patch.dict(
    os.environ,
    {
        "EMAIL_ENABLED": "true",
        "EMAIL_SENDER": "test@example.com",
        "EMAIL_PASSWORD": "password123",
        "EMAIL_SMTP_SERVER": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_RECIPIENTS": "recipient@example.com",
    },
)
@patch("smtplib.SMTP")
def test_send_csv_report(mock_smtp):
    """Test sending a CSV report via email."""
    # Create a mock SMTP instance
    mock_smtp_instance = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_smtp_instance

    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_file.write(b"user,date,type\nuser1,2023-01-01,PR\n")

    try:
        # Create the sender and send the report
        sender = EmailSender()
        result = sender.send_report(
            report_path=temp_file.name,
            start_date=MagicMock(strftime=lambda fmt: "2023-01-01"),
            end_date=MagicMock(strftime=lambda fmt: "2023-01-31"),
            user_count=5,
            activity_count=100,
        )

        # Assert the email was sent successfully
        assert result is True
        mock_smtp_instance.send_message.assert_called_once()
    finally:
        # Clean up the file
        os.unlink(temp_file.name)


@patch.dict(
    os.environ,
    {
        "EMAIL_ENABLED": "true",
        "EMAIL_SENDER": "test@example.com",
        "EMAIL_PASSWORD": "password123",
        "EMAIL_SMTP_SERVER": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_RECIPIENTS": "recipient@example.com",
    },
)
@patch("smtplib.SMTP")
def test_send_report_nonexistent_file(mock_smtp):
    """Test sending a nonexistent report."""
    # Create the sender and try to send a nonexistent report
    sender = EmailSender()
    result = sender.send_report(
        report_path="/nonexistent/file.csv",
        start_date=MagicMock(strftime=lambda fmt: "2023-01-01"),
        end_date=MagicMock(strftime=lambda fmt: "2023-01-31"),
        user_count=5,
        activity_count=100,
    )

    # Assert the email was not sent
    assert result is False
    mock_smtp.assert_not_called()
