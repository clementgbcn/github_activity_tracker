"""Command-line interface for GitHub Activity Tracker.

This module provides the main entry point for the GitHub Activity Tracker application.
It handles command-line arguments, environment variables, and coordinates the tracking
of GitHub activities for multiple users, optionally in parallel.
"""

import argparse
import multiprocessing
import os
import sys
from datetime import datetime
from functools import partial
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from .api import GitHubActivityTracker
from .report import ReportGenerator
from .utils import DEFAULT_USERS_FILE, load_users_from_file, logger, set_debug_mode
from .utils.email_sender import EmailSender


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Defines and processes the command-line arguments for the GitHub Activity Tracker.
    Includes options for user selection, date range, output format, and other settings.

    Returns:
        An argparse.Namespace object containing the parsed command-line arguments
    """
    parser = argparse.ArgumentParser(description="Track GitHub activities for a list of users.")

    # User selection options
    user_group = parser.add_mutually_exclusive_group()
    user_group.add_argument(
        "--users", nargs="+", help="GitHub usernames to track (overrides GITHUB_USERS in .env)"
    )
    user_group.add_argument(
        "--users-file",
        help=f"Path to a file containing GitHub usernames "
        f"(one per line, defaults to {DEFAULT_USERS_FILE})",
    )

    # Date range
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format (defaults to today)")

    # Output options
    parser.add_argument(
        "--output",
        choices=["csv", "html", "dataframe"],
        default="html",
        help="Output format for the report (csv, html, or dataframe)",
    )
    parser.add_argument(
        "--email",
        action="store_true",
        help="Send the report via email to recipients defined in the .env file",
    )

    # Organization options
    parser.add_argument(
        "--org",
        help="Filter results to a specific GitHub organization (overrides GITHUB_ORG in .env)",
    )
    parser.add_argument(
        "--no-org-filter", action="store_true", help="Disable organization filtering"
    )

    # Logging and monitoring options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging for detailed GitHub API operations",
    )
    parser.add_argument(
        "--no-rate-monitor",
        action="store_true",
        help="Disable background monitoring of GitHub API rate limits",
    )
    parser.add_argument(
        "--rate-check-interval",
        type=int,
        default=15,
        help="Seconds between GitHub API rate limit checks (default: 15)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=0,
        help="Maximum number of parallel workers for processing users (0 means auto-detect)",
    )

    return parser.parse_args()


def track_user_wrapper(
    username: str,
    token: str,
    start_date: datetime,
    end_date: datetime,
    org: Optional[str] = None,
    monitor_rate_limit: bool = False,
    rate_check_interval: int = 15,
) -> List[Dict[str, Any]]:
    """Wrapper function for multiprocessing that creates its own tracker instance.

    This function is designed to be called by multiprocessing.Pool to track
    activities for a single user in a separate process. It creates a dedicated
    GitHubActivityTracker instance for each user to ensure thread safety.

    Args:
        username: GitHub username to track
        token: GitHub API token
        start_date: Start date for activity search
        end_date: End date for activity search
        org: Optional organization name to filter activities by
        monitor_rate_limit: Whether to monitor rate limits in this process
        rate_check_interval: Seconds between rate limit checks

    Returns:
        List of activity dictionaries for the specified user
    """
    logger.info(f"Starting tracker process for {username}...")
    # Create a new tracker instance for each process
    # Only enable rate limit monitoring in the main process, not in worker processes
    tracker = GitHubActivityTracker(
        token,
        org,
        monitor_rate_limit=monitor_rate_limit,
        rate_limit_check_interval=rate_check_interval,
    )
    return tracker.track_user_activities(username, start_date, end_date)


def main() -> None:  # noqa: C901
    """Main entry point for the application.

    This function orchestrates the entire GitHub Activity Tracker workflow:

    1. Loads environment variables and validates GitHub token
    2. Parses command-line arguments
    3. Sets up logging configuration
    4. Determines which users to track (from CLI, file, or environment)
    5. Validates and parses date range
    6. Determines organization filtering settings
    7. Initializes parallel processing for tracking multiple users
    8. Aggregates and processes all activity data
    9. Generates the appropriate report format

    The function handles all error conditions, including:
    - Missing GitHub token
    - Invalid date formats
    - Missing or invalid user information
    - API errors during execution

    Exits with error code 1 if critical errors are encountered.
    """
    # Load environment variables
    load_dotenv()
    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token:
        logger.error("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
        logger.error("Create a .env file based on .env.example with your GitHub token.")
        sys.exit(1)

    args = parse_arguments()

    # Configure logging based on debug flag
    if args.debug:
        set_debug_mode(True)
        logger.debug("Debug logging enabled")

    logger.info("🚀 GitHub Activity Tracker starting...")
    logger.debug(f"Arguments: {args}")

    # Check for JIRA_URL_PREFIX
    jira_url_prefix = os.getenv("JIRA_URL_PREFIX")
    if jira_url_prefix:
        logger.debug(f"JIRA URL prefix found: {jira_url_prefix}")
    else:
        logger.info("No JIRA_URL_PREFIX found in environment. Using default.")

    # Get users from command line, specified file, environment, or default file
    users = None

    if args.users:
        # 1. Command-line arguments take priority
        users = args.users
        logger.debug(f"Using {len(users)} users from command line arguments")
    elif args.users_file:
        # 2. Explicitly specified file
        file_path = args.users_file
        logger.debug(f"Loading users from specified file: {file_path}")
        users = load_users_from_file(file_path)
        if users is None:
            logger.error(f"Specified users file '{file_path}' not found or couldn't be read.")
            sys.exit(1)
    else:
        # 3. Check environment variable
        github_users_env = os.getenv("GITHUB_USERS")
        if github_users_env:
            # Split by comma, and strip whitespace from each user
            users = [user.strip() for user in github_users_env.split(",") if user.strip()]
            logger.debug(f"Using {len(users)} users from GITHUB_USERS environment variable")
        else:
            # 4. Fall back to default file
            logger.debug(f"Loading users from default file: {DEFAULT_USERS_FILE}")
            users = load_users_from_file(DEFAULT_USERS_FILE)

            # If we couldn't load users from the default file
            if users is None:
                logger.error(f"Default users file '{DEFAULT_USERS_FILE}' not found.")
                logger.error("Please create this file with GitHub usernames (one per line)")
                logger.error(
                    "Or specify users via --users, --users-file, "
                    "or GITHUB_USERS environment variable."
                )
                sys.exit(1)

    if not users:
        logger.error("No users specified. Please provide GitHub usernames.")
        sys.exit(1)

    logger.info(f"Processing {len(users)} GitHub users")

    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(
            tzinfo=datetime.now().astimezone().tzinfo
        )

        if args.end_date:
            end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(
                tzinfo=datetime.now().astimezone().tzinfo
            )
        else:
            end_date = datetime.now().astimezone()

        logger.info(
            f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
    except ValueError:
        logger.error("Error: Dates should be in YYYY-MM-DD format.")
        sys.exit(1)

    # Handle organization filtering
    if args.no_org_filter:
        org = None
        logger.debug("Organization filtering disabled via --no-org-filter")
    else:
        # Check command line first, then environment, defaulting to None if neither specified
        org = args.org
        if org is None:
            # Check environment variable
            org = os.getenv("GITHUB_ORG")
            if org:
                logger.debug(f"Using organization from environment: {org}")
            else:
                logger.debug("No organization specified in arguments or environment")
        else:
            logger.debug(f"Using organization from command line: {org}")

    # Determine if we should monitor rate limits
    monitor_rate_limit = not args.no_rate_monitor
    rate_check_interval = args.rate_check_interval

    # Initialize main tracker (this one will monitor rate limits if enabled)
    _ = GitHubActivityTracker(
        github_token,
        org,
        monitor_rate_limit=monitor_rate_limit,
        rate_limit_check_interval=rate_check_interval,
    )

    if monitor_rate_limit:
        logger.info(
            f"Rate limit monitoring enabled (check interval: {rate_check_interval} seconds)"
        )

    # Display organization filter information
    if org:
        logger.info(f"Filtering activities to the {org} organization")
    else:
        logger.info(
            "Organization filtering is disabled. Showing activities across all organizations"
        )

    # Determine number of workers
    if args.max_workers > 0:
        worker_count = min(args.max_workers, len(users))
    else:
        worker_count = min(multiprocessing.cpu_count(), len(users))

    logger.info(f"Starting parallel tracking with {worker_count} workers for {len(users)} users")

    # Create a partial function with fixed parameters
    # Worker processes should NOT monitor rate limits - only the main process does that
    track_func = partial(
        track_user_wrapper,
        token=github_token,
        start_date=start_date,
        end_date=end_date,
        org=org,
        monitor_rate_limit=False,  # Workers don't need to monitor
        rate_check_interval=rate_check_interval,  # Still pass the interval for consistency
    )

    # Use multiprocessing to track users in parallel
    with multiprocessing.Pool(processes=worker_count) as pool:
        results = pool.map(track_func, users)

    # Debug log each user's activity count
    for i, user_activities in enumerate(results):
        activity_count = len(user_activities) if user_activities else 0
        logger.debug(f"User '{users[i]}' returned {activity_count} activities")

    # Count total activities found
    total_activities = sum(len(user_acts) for user_acts in results if user_acts)
    logger.info(f"✅ Parallel processing complete. Found {total_activities} total activities")

    # Combine all results
    all_activities = []
    for i, user_activities in enumerate(results):
        if user_activities:
            logger.debug(
                f"Adding {len(user_activities)} activities "
                f"from user '{users[i]}' to the combined results"
            )
            all_activities.extend(user_activities)
        else:
            logger.debug(f"No activities to add from user '{users[i]}'")

    logger.info(f"Combined results include {len(all_activities)} total activities")

    # Generate report
    logger.info(f"📊 Generating {args.output} report")

    report_file = None
    if args.output in ["csv", "html"]:
        if not all_activities:
            logger.warning(
                f"No activities found for the specified users and date range. "
                f"No {args.output} report will be generated."
            )
        else:
            logger.debug(f"Generating {args.output} report for {len(all_activities)} activities")
            report_file = ReportGenerator.generate_report(all_activities, args.output)

            # If report generation was successful
            if report_file:
                if args.output == "html":
                    report_dir = os.path.dirname(report_file)
                    html_path = os.path.abspath(report_file)
                    file_url = f"file://{html_path}"

                    logger.info(f"Report generated in: {report_dir}")
                    logger.info(f"Open this file in your browser: {report_file}")
                    logger.info(f"Or click this link: {file_url}")
            else:
                logger.error(f"Failed to generate {args.output} report. Check logs for details.")
    else:
        # Just generate insights directly from the ActivityVisualizer
        from .report.visualization import ActivityVisualizer

        df = pd.DataFrame(all_activities)
        ActivityVisualizer.generate_insights(df)

    # Send email if requested and we have a report file
    if args.email and report_file and args.output in ["csv", "html"]:
        logger.info("📧 Sending report via email...")
        email_sender = EmailSender()
        if email_sender.enabled:
            success = email_sender.send_report(
                report_path=report_file,
                start_date=start_date,
                end_date=end_date,
                user_count=len(users),
                activity_count=total_activities,
            )
            if success:
                logger.info("✅ Report sent successfully via email")
            else:
                logger.error("❌ Failed to send report via email")
        else:
            logger.warning("⚠️ Email sending is disabled or not properly configured")

    logger.info("🎉 GitHub Activity Tracker completed successfully")


if __name__ == "__main__":
    main()
