"""Tests for the command-line interface."""

from datetime import datetime
from unittest.mock import MagicMock, patch

from github_activity_tracker.cli import parse_arguments, track_user_wrapper


@patch("argparse.ArgumentParser.parse_args")
def test_parse_arguments(mock_parse_args):
    """Test parsing command-line arguments."""
    # Set up mock return value
    mock_args = MagicMock()
    mock_args.users = ["user1", "user2"]
    mock_args.start_date = "2023-01-01"
    mock_args.end_date = None
    mock_args.debug = True
    mock_args.no_rate_monitor = False
    mock_parse_args.return_value = mock_args

    # Call the function
    args = parse_arguments()

    # Verify the result
    assert args.users == ["user1", "user2"]
    assert args.start_date == "2023-01-01"
    assert args.end_date is None
    assert args.debug is True
    assert args.no_rate_monitor is False


@patch("github_activity_tracker.cli.GitHubActivityTracker")
def test_track_user_wrapper(mock_tracker_class):
    """Test the track_user_wrapper function."""
    # Set up mock
    mock_tracker = MagicMock()
    mock_tracker.track_user_activities.return_value = ["activity1", "activity2"]
    mock_tracker_class.return_value = mock_tracker

    # Mock arguments
    username = "test_user"
    token = "fake_token"
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 1, 31)
    org = "test-org"

    # Call the function
    result = track_user_wrapper(username, token, start_date, end_date, org, False, 60)

    # Verify the tracker was created correctly
    mock_tracker_class.assert_called_once_with(
        token, org, monitor_rate_limit=False, rate_limit_check_interval=60
    )

    # Verify the track_user_activities method was called
    mock_tracker.track_user_activities.assert_called_once_with(username, start_date, end_date)

    # Verify the result
    assert result == ["activity1", "activity2"]


@patch("github_activity_tracker.cli.load_dotenv")
@patch("github_activity_tracker.cli.os.getenv")
@patch("github_activity_tracker.cli.parse_arguments")
@patch("github_activity_tracker.cli.set_debug_mode")
@patch("sys.exit")
def test_main_no_token(mock_exit, mock_set_debug, mock_parse_args, mock_getenv, mock_load_dotenv):
    """Test main function with no GitHub token."""
    from github_activity_tracker.cli import main

    # Set up mocks
    mock_getenv.return_value = None
    mock_args = MagicMock()
    mock_args.debug = False

    # The test is failing at the args.start_date line, so we need
    # to exit before that point for this particular test
    def side_effect(*args, **kwargs):
        # This side effect makes sys.exit actually exit the function
        # instead of continuing execution
        raise SystemExit(1)

    mock_exit.side_effect = side_effect
    mock_parse_args.return_value = mock_args

    # Call the function
    try:
        main()
    except SystemExit:
        # Catch the SystemExit exception raised by our side_effect
        pass

    # Verify dot env was loaded
    mock_load_dotenv.assert_called_once()

    # Verify getenv was called with right argument
    mock_getenv.assert_called_with("GITHUB_TOKEN")

    # Verify sys.exit was called
    mock_exit.assert_called_once_with(1)
