"""Tests for the GitHub client module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from github_activity_tracker.api.github_client import GitHubActivityTracker


@pytest.fixture
def mock_github():
    """Fixture for a mocked GitHub API client."""
    with patch("github_activity_tracker.api.github_client.Github") as mock_github:
        # Mock rate limit
        rate_limit = MagicMock()
        core_limit = MagicMock()
        core_limit.limit = 5000
        core_limit.remaining = 4000
        core_limit.reset.timestamp.return_value = datetime.now().timestamp() + 3600

        search_limit = MagicMock()
        search_limit.limit = 30
        search_limit.remaining = 25
        search_limit.reset.timestamp.return_value = datetime.now().timestamp() + 3600

        rate_limit.core = core_limit
        rate_limit.search = search_limit

        mock_github.return_value.get_rate_limit.return_value = rate_limit

        # Return the mock
        yield mock_github


def test_init(mock_github):
    """Test initializing the tracker."""
    tracker = GitHubActivityTracker("fake_token", org="test-org")

    # Verify the GitHub API was initialized
    mock_github.assert_called_once_with("fake_token")

    # Verify rate limit was checked (at least once)
    assert mock_github.return_value.get_rate_limit.call_count > 0

    # Verify org is set
    assert tracker.org == "test-org"


@patch("github_activity_tracker.api.github_client.threading.Thread")
def test_rate_limit_monitor(mock_thread, mock_github):
    """Test rate limit monitoring."""
    # Create tracker with rate limit monitoring
    GitHubActivityTracker("fake_token", monitor_rate_limit=True)

    # Verify thread was created and started
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()


def test_check_rate_limit(mock_github):
    """Test checking rate limits."""
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)

    # Reset mock to clear initialization calls
    mock_github.reset_mock()

    # Call the method
    result = tracker._check_rate_limit()

    # Verify rate limit was checked
    mock_github.return_value.get_rate_limit.assert_called_once()

    # Verify result
    assert result is True


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_empty(mock_logger, mock_github):
    """Test tracking activities with mocked responses."""
    # Mock user
    mock_user = MagicMock()
    mock_user.name = "Test User"
    mock_user.id = 12345
    mock_user.location = "Test Location"
    mock_user.public_repos = 10

    # Mock API calls
    mock_github.return_value.get_user.return_value = mock_user
    mock_github.return_value.search_issues.return_value = []

    # Create tracker and track activities
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 31, tzinfo=timezone.utc)

    activities = tracker.track_user_activities("test_user", start_date, end_date)

    # Verify user was fetched
    mock_github.return_value.get_user.assert_called_once_with("test_user")

    # Verify search was performed
    assert mock_github.return_value.search_issues.call_count == 2

    # Verify results
    assert isinstance(activities, list)
    assert len(activities) == 0
    assert len(tracker.activities) == 0
