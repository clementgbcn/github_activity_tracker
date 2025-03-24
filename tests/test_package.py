"""Tests for package structure and imports."""

import importlib.util


def test_package_structure():
    """Test that the package structure is correct."""
    # Check core modules
    core_modules = [
        "github_activity_tracker",
        "github_activity_tracker.cli",
        "github_activity_tracker.api",
        "github_activity_tracker.api.github_client",
        "github_activity_tracker.report",
        "github_activity_tracker.report.visualization",
        "github_activity_tracker.report.generator",
        "github_activity_tracker.utils",
        "github_activity_tracker.utils.logging_config",
        "github_activity_tracker.utils.file_utils",
    ]

    for module_name in core_modules:
        spec = importlib.util.find_spec(module_name)
        assert spec is not None, f"Module {module_name} not found"


def test_version():
    """Test that the package has a version."""
    import github_activity_tracker

    assert hasattr(github_activity_tracker, "__version__")
    assert isinstance(github_activity_tracker.__version__, str)
    assert github_activity_tracker.__version__ != ""


def test_main_exports():
    """Test that main modules export expected classes and functions."""
    # Test GitHub client exports
    from github_activity_tracker.api import GitHubActivityTracker

    assert callable(GitHubActivityTracker)

    # Test visualization exports
    from github_activity_tracker.report import ActivityVisualizer

    assert hasattr(ActivityVisualizer, "generate_insights")
    assert hasattr(ActivityVisualizer, "plot_activity_trends")

    # Test report generator exports
    from github_activity_tracker.report import ReportGenerator

    assert hasattr(ReportGenerator, "generate_report")

    # Test CLI exports
    from github_activity_tracker.cli import main, parse_arguments

    assert callable(main)
    assert callable(parse_arguments)
