"""Tests for the GitHub client module."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException, RateLimitExceededException

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

    # Verify the GitHub API was initialized with retry parameter
    mock_github.assert_called_once()  # Just check it was called once
    args, kwargs = mock_github.call_args
    assert args[0] == "fake_token"  # Check the token is correct
    assert "retry" in kwargs  # Check retry parameter is included

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
def test_check_rate_limit_low_warning(mock_logger, mock_github):
    """Test rate limit warning when running low."""
    # Set up rate limit to be low
    rate_limit = mock_github.return_value.get_rate_limit.return_value
    rate_limit.core.limit = 5000
    rate_limit.core.remaining = 900  # 18% remaining
    rate_limit.search.limit = 30
    rate_limit.search.remaining = 25

    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)

    # Reset mocks
    mock_github.reset_mock()
    mock_logger.reset_mock()

    # Call method
    result = tracker._check_rate_limit()

    # Verify warning was logged
    mock_logger.warning.assert_called()
    # Check warning message contains appropriate info
    warning_args = mock_logger.warning.call_args_list[0][0][0]
    assert "Core API rate limit running low" in warning_args

    # Verify result
    assert result is True


@patch("github_activity_tracker.api.github_client.logger")
def test_check_rate_limit_critical_warning(mock_logger, mock_github):
    """Test rate limit critical warning when almost depleted."""
    # Set up rate limit to be critically low
    rate_limit = mock_github.return_value.get_rate_limit.return_value
    rate_limit.core.limit = 5000
    rate_limit.core.remaining = 100  # 2% remaining
    rate_limit.search.limit = 30
    rate_limit.search.remaining = 1  # 3.3% remaining

    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)

    # Reset mocks
    mock_github.reset_mock()
    mock_logger.reset_mock()

    # Call method
    result = tracker._check_rate_limit()

    # Verify critical warnings were logged
    assert mock_logger.warning.call_count >= 2

    # Check both core and search warnings
    warning_messages = [args[0][0] for args in mock_logger.warning.call_args_list]
    core_warning = any("CRITICAL: Core API rate limit" in msg for msg in warning_messages)
    search_warning = any("CRITICAL: Search API rate limit" in msg for msg in warning_messages)

    assert core_warning
    assert search_warning

    # Verify result
    assert result is True


@patch("github_activity_tracker.api.github_client.logger")
def test_check_rate_limit_error(mock_logger, mock_github):
    """Test rate limit check with error."""
    # Configure get_rate_limit to raise an exception
    mock_github.return_value.get_rate_limit.side_effect = GithubException(500, "Test error")

    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)

    # Reset mocks
    mock_github.reset_mock()
    mock_logger.reset_mock()

    # Call method
    result = tracker._check_rate_limit()

    # Verify error was logged
    mock_logger.error.assert_called_once()

    # Verify result is False due to error
    assert result is False


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_empty(mock_logger, mock_github):
    """Test tracking activities with empty responses."""
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


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_with_data(mock_logger, mock_github):
    """Test tracking activities with PRs and reviews."""
    # Mock user
    mock_user = MagicMock()
    mock_user.name = "Test User"
    mock_user.id = 12345
    mock_user.location = "Test Location"
    mock_user.public_repos = 10

    # Mock PR data
    pr1 = MagicMock()
    pr1.id = 101
    pr1.number = 42
    pr1.title = "Test PR 1"
    pr1.state = "open"
    pr1.created_at = datetime(2023, 1, 15, tzinfo=timezone.utc)
    pr1.comments = 3
    pr1.pull_request = True  # Flag to identify it as a PR
    pr1.repository = MagicMock()
    pr1.repository.full_name = "test-org/test-repo-1"

    pr2 = MagicMock()
    pr2.id = 102
    pr2.number = 43
    pr2.title = "Test PR 2"
    pr2.state = "closed"
    pr2.created_at = datetime(2023, 1, 20, tzinfo=timezone.utc)
    pr2.comments = 0
    pr2.pull_request = True
    pr2.repository = MagicMock()
    pr2.repository.full_name = "test-org/test-repo-2"

    # Non-PR issue that should be skipped
    issue = MagicMock()
    issue.pull_request = None
    issue.repository = MagicMock()
    issue.repository.full_name = "test-org/test-repo-1"

    # PR from a different org that should be skipped when filtering by org
    pr_other_org = MagicMock()
    pr_other_org.id = 103
    pr_other_org.number = 44
    pr_other_org.title = "Test PR Other Org"
    pr_other_org.state = "open"
    pr_other_org.created_at = datetime(2023, 1, 25, tzinfo=timezone.utc)
    pr_other_org.comments = 1
    pr_other_org.pull_request = True
    pr_other_org.repository = MagicMock()
    pr_other_org.repository.full_name = "other-org/test-repo"

    # Mock review data
    review1 = MagicMock()
    review1.id = 201
    review1.number = 45
    review1.title = "Review PR 1"
    review1.state = "closed"
    review1.updated_at = datetime(2023, 1, 18, tzinfo=timezone.utc)
    review1.pull_request = True
    review1.repository = MagicMock()
    review1.repository.full_name = "test-org/test-repo-3"

    # Mock API calls
    mock_github.return_value.get_user.return_value = mock_user

    # For the first call (PRs created), return a mix of PRs and a non-PR
    pr_search_result = [pr1, pr2, issue, pr_other_org]
    # For the second call (reviews), return reviews
    review_search_result = [review1]

    # Configure search_issues to return different results based on query
    mock_github.return_value.search_issues.side_effect = lambda **kwargs: (
        pr_search_result if "author:" in kwargs.get("query", "") else review_search_result
    )

    # Create tracker and track activities with org filter
    tracker = GitHubActivityTracker("fake_token", org="test-org", monitor_rate_limit=False)
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 31, tzinfo=timezone.utc)

    activities = tracker.track_user_activities("test_user", start_date, end_date)

    # Verify user was fetched
    mock_github.return_value.get_user.assert_called_once_with("test_user")

    # Verify search was performed for both PRs and reviews
    assert mock_github.return_value.search_issues.call_count == 2

    # Verify results - should include 2 PRs from test-org and 1 review
    assert isinstance(activities, list)
    assert len(activities) == 3

    # Check PRs were added correctly
    pr_activities = [a for a in activities if a["type"] == "PullRequestEvent"]
    assert len(pr_activities) == 2

    # Check reviews were added correctly
    review_activities = [a for a in activities if a["type"] == "PullRequestReviewEvent"]
    assert len(review_activities) == 1

    # Verify the activities were also stored in the tracker
    assert len(tracker.activities) == 3


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_no_org_filter(mock_logger, mock_github):
    """Test tracking activities without org filter."""
    # Mock user
    mock_user = MagicMock()
    mock_user.name = "Test User"

    # Mock PR from a different org that should be included when not filtering
    pr_other_org = MagicMock()
    pr_other_org.id = 103
    pr_other_org.number = 44
    pr_other_org.title = "Test PR Other Org"
    pr_other_org.state = "open"
    pr_other_org.created_at = datetime(2023, 1, 25, tzinfo=timezone.utc)
    pr_other_org.comments = 1
    pr_other_org.pull_request = True
    pr_other_org.repository = MagicMock()
    pr_other_org.repository.full_name = "other-org/test-repo"

    # Mock API calls
    mock_github.return_value.get_user.return_value = mock_user

    # Configure search_issues to return PR results for first call, empty for second
    mock_github.return_value.search_issues.side_effect = [
        [pr_other_org],  # First call - PRs
        [],  # Second call - reviews
    ]

    # Create tracker WITHOUT org filter
    tracker = GitHubActivityTracker("fake_token", org=None, monitor_rate_limit=False)
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 31, tzinfo=timezone.utc)

    activities = tracker.track_user_activities("test_user", start_date, end_date)

    # Verify results should include the PR from other-org
    assert len(activities) == 1
    assert activities[0]["repo"] == "other-org/test-repo"


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_with_rate_limit_exception(mock_logger, mock_github):
    """Test tracking activities with rate limit exception."""
    # Mock user
    mock_user = MagicMock()
    mock_user.name = "Test User"

    # Mock API calls
    mock_github.return_value.get_user.return_value = mock_user

    # Create a RateLimitExceededException object with reset time in the headers
    reset_timestamp = int(datetime.now().timestamp()) + 3600
    headers = {"X-RateLimit-Reset": reset_timestamp}
    rate_ex = RateLimitExceededException(429, "API rate limit exceeded", headers)

    # Configure search_issues to raise rate limit exception on first call
    mock_github.return_value.search_issues.side_effect = [
        rate_ex,  # First call raises exception
        [],  # Second call returns empty list (for reviews)
    ]

    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 31, tzinfo=timezone.utc)

    # Should continue despite rate limit exception
    activities = tracker.track_user_activities("test_user", start_date, end_date)

    # Verify warning was logged
    mock_logger.error.assert_called()

    # Print the errors being logged for debugging
    print("Log errors:", [args[0][0] for args in mock_logger.error.call_args_list])

    # At least one error message should contain "Rate Limit Exceeded"
    error_found = False
    for call_args in mock_logger.error.call_args_list:
        if "Rate Limit Exceeded" in call_args[0][0]:
            error_found = True
            break
    assert error_found, "Rate limit exceeded message not found in logger.error calls"

    # Verify empty results were returned (after handling the exception)
    assert isinstance(activities, list)
    assert len(activities) == 0


@patch("github_activity_tracker.api.github_client.logger")
def test_track_user_activities_with_github_exception(mock_logger, mock_github):
    """Test tracking activities with GitHub exception."""
    # Configure get_user to raise exception
    mock_github.return_value.get_user.side_effect = GithubException(404, "User not found")

    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)
    start_date = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 31, tzinfo=timezone.utc)

    # Should handle the exception gracefully
    activities = tracker.track_user_activities("nonexistent_user", start_date, end_date)

    # Verify error was logged
    mock_logger.error.assert_called()
    error_message = mock_logger.error.call_args_list[0][0][0]
    assert "GitHub API error" in error_message

    # Verify empty results were returned
    assert isinstance(activities, list)
    assert len(activities) == 0


def test_get_data_frame(mock_github):
    """Test converting activities to DataFrame."""
    # Create tracker
    tracker = GitHubActivityTracker("fake_token", monitor_rate_limit=False)

    # Add sample activities
    sample_activities = [
        {
            "user": "user1",
            "date": datetime(2023, 1, 15),
            "type": "PullRequestEvent",
            "repo": "org/repo1",
            "id": "1",
            "url": "https://github.com/org/repo1/pull/1",
        },
        {
            "user": "user1",
            "date": datetime(2023, 1, 20),
            "type": "PullRequestReviewEvent",
            "repo": "org/repo2",
            "id": "2",
            "url": "https://github.com/org/repo2/pull/2",
        },
    ]
    tracker.activities = sample_activities

    # Get DataFrame
    df = tracker.get_data_frame()

    # Verify DataFrame
    assert df is not None
    assert len(df) == 2
    assert list(df.columns) == ["user", "date", "type", "repo", "id", "url"]

    # Verify sorted by date
    assert df.iloc[0]["date"] == datetime(2023, 1, 20)
    assert df.iloc[1]["date"] == datetime(2023, 1, 15)
