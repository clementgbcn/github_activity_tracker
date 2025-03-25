"""Tests for the report modules."""

import os
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from github_activity_tracker.report.generator import ReportGenerator
from github_activity_tracker.report.visualization import ActivityVisualizer


@pytest.fixture
def sample_data():
    """Create a sample DataFrame for testing."""
    data = [
        {
            "user": "user1",
            "date": datetime(2023, 1, 1),
            "type": "PullRequestEvent",
            "repo": "repo1",
            "id": "1",
            "url": "https://github.com/org/repo1/pull/1",
            "details": {"title": "PR 1", "state": "open", "number": 1, "comments": 2},
        },
        {
            "user": "user1",
            "date": datetime(2023, 1, 2),
            "type": "PullRequestReviewEvent",
            "repo": "repo2",
            "id": "2",
            "url": "https://github.com/org/repo2/pull/2",
            "details": {"pr_number": 2, "pr_title": "PR 2", "state": "closed"},
        },
        {
            "user": "user2",
            "date": datetime(2023, 1, 3),
            "type": "PullRequestEvent",
            "repo": "repo1",
            "id": "3",
            "url": "https://github.com/org/repo1/pull/3",
            "details": {"title": "PR 3", "state": "closed", "number": 3, "comments": 0},
        },
    ]
    return pd.DataFrame(data)


@patch("matplotlib.pyplot.savefig")
@patch("matplotlib.pyplot.close")
def test_plot_activity_trends(mock_close, mock_savefig, sample_data, tmp_path):
    """Test plotting activity trends."""
    # Create a temporary directory for testing
    output_dir = str(tmp_path)

    # Call the method
    filename = ActivityVisualizer.plot_activity_trends(sample_data, output_dir)

    # Verify savefig was called
    mock_savefig.assert_called_once()

    # Verify close was called at least once (it's called multiple times in the code)
    assert mock_close.call_count > 0

    # Verify the returned filename
    assert filename == os.path.join(output_dir, "activity_trends.png")


@patch("matplotlib.pyplot.savefig")
@patch("matplotlib.pyplot.close")
def test_plot_activity_types(mock_close, mock_savefig, sample_data, tmp_path):
    """Test plotting activity types."""
    # Create a temporary directory for testing
    output_dir = str(tmp_path)

    # Call the method
    filename = ActivityVisualizer.plot_activity_types(sample_data, output_dir)

    # Verify savefig was called
    mock_savefig.assert_called_once()

    # Verify close was called at least once (it's called multiple times in the code)
    assert mock_close.call_count > 0

    # Verify the returned filename
    assert filename == os.path.join(output_dir, "activity_types.png")


@patch("github_activity_tracker.report.generator.ActivityVisualizer.generate_insights")
@patch("github_activity_tracker.report.generator.shutil.copy2")
@patch("github_activity_tracker.report.generator.Path.exists", return_value=True)
@patch("weasyprint.HTML", side_effect=ImportError("Mocked WeasyPrint Import"))
def test_generate_html_report(
    mock_html, mock_path_exists, mock_copy2, mock_generate_insights, sample_data, tmp_path
):
    """Test generating an HTML report."""
    # Mock the insights return value
    mock_insights = {
        "total_activities": 3,
        "users": 2,
        "repositories": 2,
        "graphs": {
            "trends": str(tmp_path / "activity_trends.png"),
            "types": str(tmp_path / "activity_types.png"),
            "users": str(tmp_path / "user_comparison.png"),
        },
    }
    mock_generate_insights.return_value = mock_insights

    # Create a template directory for testing
    os.makedirs(str(tmp_path / "templates"), exist_ok=True)

    # Mock jinja2 template loader and other dependencies
    with patch("github_activity_tracker.report.generator.jinja2.FileSystemLoader"), patch(
        "github_activity_tracker.report.generator.jinja2.Environment"
    ), patch(
        "github_activity_tracker.report.generator.create_report_directory"
    ) as mock_create_dir, patch("builtins.open", create=True), patch(
        "github_activity_tracker.report.generator.os.path.join",
        return_value=str(tmp_path / "index.html"),
    ):
        # Mock the report directory
        mock_create_dir.return_value = str(tmp_path)

        # Call the method
        result = ReportGenerator._generate_html_report(sample_data)

        # Verify insights were generated
        mock_generate_insights.assert_called_once()

        # Verify logo copy was attempted
        mock_copy2.assert_called()

        # Verify the returned path
        assert result == str(tmp_path / "index.html")
