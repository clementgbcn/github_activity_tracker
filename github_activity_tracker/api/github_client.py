"""GitHub API client for tracking user activities.

This module provides functionality to interact with the GitHub API to retrieve
user activities such as pull requests, reviews, and comments. It includes rate limit
monitoring and can filter activities by organization.
"""

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from github import Github, GithubException, GithubRetry, RateLimitExceededException

from ..utils.logger_utils import configure_github_retry_logger
from ..utils.logging_config import logger


class GitHubActivityTracker:
    """Tracks GitHub activities for specified users.

    This class provides methods to retrieve and analyze GitHub activities for given
    users, including pull requests, reviews, and comments. It supports filtering by
    organization and date range, and includes built-in rate limit monitoring to
    prevent API quota exhaustion.

    Attributes:
        github: The PyGithub client instance
        activities: List of tracked activities
        org: Organization name to filter by
        token: GitHub API token
        rate_limit_monitor: Thread for monitoring rate limits
        rate_limit_check_interval: Seconds between rate limit checks
        github_urls: Templates for GitHub URLs
    """

    def __init__(
        self,
        token: str,
        org: Optional[str] = None,
        monitor_rate_limit: bool = True,
        rate_limit_check_interval: int = 15,
    ) -> None:
        """Initialize the GitHub API client.

        Args:
            token: GitHub personal access token with appropriate permissions
            org: Optional organization name to filter activities by
            monitor_rate_limit: Whether to monitor GitHub API rate limit in background
            rate_limit_check_interval: Seconds between rate limit checks

        Raises:
            GithubException: If authentication fails or the token is invalid
        """
        # Configure GitHub with retry functionality and custom logger
        default_retry = GithubRetry()
        configure_github_retry_logger(default_retry, logger)
        self.github = Github(token, retry=default_retry)
        self.activities: List[Dict[str, Any]] = []
        self.org = org
        self.token = token
        self.rate_limit_monitor: Optional[threading.Thread] = None
        self.rate_limit_check_interval = rate_limit_check_interval

        # GitHub URL templates for different activities
        self.github_urls: Dict[str, str] = {
            "repo": "https://github.com/{repo}",
            "pr": "https://github.com/{repo}/pull/{number}",
        }

        # Check rate limit on startup
        self._check_rate_limit()

        # Start background rate limit monitoring if requested
        if monitor_rate_limit:
            self._start_rate_limit_monitor(self.rate_limit_check_interval)

    def _check_rate_limit(self) -> bool:
        """Check and log the current rate limit status.

        Retrieves the current GitHub API rate limit status and logs warnings
        if the remaining quota is running low.

        Returns:
            bool: True if rate limit check was successful, False otherwise

        Raises:
            GithubException: If there's an issue with the GitHub API
        """
        try:
            logger.debug("Checking GitHub API rate limits...")
            rate_limit = self.github.get_rate_limit()
            core_limit = rate_limit.core
            search_limit = rate_limit.search

            core_remaining_percent = (core_limit.remaining / core_limit.limit) * 100
            search_remaining_percent = (search_limit.remaining / search_limit.limit) * 100

            # Calculate time until reset
            core_reset_time = datetime.fromtimestamp(core_limit.reset.timestamp())
            search_reset_time = datetime.fromtimestamp(search_limit.reset.timestamp())

            core_reset_minutes = (core_reset_time - datetime.now()).total_seconds() / 60
            search_reset_minutes = (search_reset_time - datetime.now()).total_seconds() / 60

            logger.debug(
                f"Rate Limit Status - Core: {core_limit.remaining}/{core_limit.limit} "
                f"({core_remaining_percent:.1f}% remaining)"
            )
            logger.debug(
                f"Core rate limit resets in {core_reset_minutes:.1f} minutes (at {core_reset_time.strftime('%H:%M:%S')})"
            )

            logger.debug(
                f"Rate Limit Status - Search: {search_limit.remaining}/{search_limit.limit} "
                f"({search_remaining_percent:.1f}% remaining)"
            )
            logger.debug(
                f"Search rate limit resets in {search_reset_minutes:.1f} minutes (at {search_reset_time.strftime('%H:%M:%S')})"
            )

            # Check if we're running low on rate limit and log a warning
            if core_remaining_percent < 20:
                if core_remaining_percent < 5:
                    logger.warning(
                        f"🚨 CRITICAL: Core API rate limit almost depleted: {core_limit.remaining}/{core_limit.limit}. "
                        f"Resets at {core_reset_time.strftime('%H:%M:%S')} ({core_reset_minutes:.1f} minutes)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Core API rate limit running low: {core_limit.remaining}/{core_limit.limit}. "
                        f"Resets at {core_reset_time.strftime('%H:%M:%S')} ({core_reset_minutes:.1f} minutes)"
                    )

            if search_remaining_percent < 20:
                if search_remaining_percent < 5:
                    logger.warning(
                        f"🚨 CRITICAL: Search API rate limit almost depleted: {search_limit.remaining}/{search_limit.limit}. "
                        f"Resets at {search_reset_time.strftime('%H:%M:%S')} ({search_reset_minutes:.1f} minutes)"
                    )
                else:
                    logger.warning(
                        f"⚠️ Search API rate limit running low: {search_limit.remaining}/{search_limit.limit}. "
                        f"Resets at {search_reset_time.strftime('%H:%M:%S')} ({search_reset_minutes:.1f} minutes)"
                    )

            return True

        except Exception as e:
            logger.error(f"❌ Error checking rate limit: {e}")
            return False

    def _monitor_rate_limit(self, check_interval: int = 60) -> None:
        """Background thread function to monitor rate limit.

        This method runs in a separate thread to periodically check
        the GitHub API rate limit and log warnings if it's running low.

        Args:
            check_interval: Seconds between rate limit checks
        """
        logger.debug("Rate limit monitoring started")

        while True:
            try:
                self._check_rate_limit()
                time.sleep(check_interval)
            except Exception as e:
                logger.error(f"❌ Error in rate limit monitor: {e}")
                time.sleep(check_interval * 2)  # Wait longer if there was an error

    def _start_rate_limit_monitor(self, check_interval: int = 15) -> None:
        """Start a background thread to monitor the GitHub API rate limit.

        Creates and starts a daemon thread that periodically checks
        the GitHub API rate limit status.

        Args:
            check_interval: Seconds between rate limit checks (default: 15)
        """
        self.rate_limit_monitor = threading.Thread(
            target=self._monitor_rate_limit,
            args=(check_interval,),  # Pass the check interval to the thread function
            daemon=True,  # Thread will exit when main program exits
            name="rate-limit-monitor",
        )
        self.rate_limit_monitor.start()
        logger.debug(
            f"Rate limit monitoring thread started (check interval: {check_interval} seconds)"
        )

    def track_user_activities(
        self, username: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Track activities for a specific user within the given date range.

        Retrieves and processes GitHub activities for the specified user,
        including pull requests and code reviews, within the specified date range.

        Args:
            username: GitHub username to track
            start_date: Start date for activity search (inclusive)
            end_date: End date for activity search (inclusive)

        Returns:
            List of activity dictionaries containing details about each activity

        Raises:
            GithubException: If there's an issue with the GitHub API
            RateLimitExceededException: If the GitHub API rate limit is exceeded
        """
        try:
            logger.info(f"🔍 Starting activity tracking for user: {username}")

            # Log the date range we're searching
            logger.debug(
                f"📅 Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )
            logger.debug(
                f"🏢 Organization filter: {self.org if self.org else 'None (tracking across all orgs)'}"
            )

            # Fetch user data
            logger.debug(f"👤 Fetching user data for {username}...")
            user = self.github.get_user(username)
            logger.debug(
                f"👤 User info: Name={user.name}, ID={user.id}, Location={user.location}, Public repos={user.public_repos}"
            )

            user_activities = []
            logger.debug(
                f"🏁 Initialized activity tracking for {username} (will search for PRs and reviews)"
            )

            # Helper function to check if a repo belongs to the specified organization
            def is_in_org(repo_name):
                if not self.org:
                    return True  # No org filter, include all repos
                return repo_name.startswith(f"{self.org}/")

            # Get pull requests
            try:
                logger.info(f"📥 Fetching pull requests for {username}...")

                # Construct the search query
                query = f"author:{username} created:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"

                # Add org filter if specified
                if self.org:
                    query += f" org:{self.org}"

                logger.debug(f"Pull request search query: '{query}'")

                # Execute the search
                pulls_count = 0
                added_count = 0

                try:
                    pulls = self.github.search_issues(query=query, sort="created", order="desc")

                    # Process each pull request
                    for pull in pulls:
                        pulls_count += 1
                        logger.debug(f"Processing PR #{pull.number}: Starting evaluation")

                        # Skip non-pull request issues
                        if not pull.pull_request:
                            logger.debug(f"Skipping issue #{pull.number} (not a pull request)")
                            continue

                        # Apply organization filter if needed
                        if not is_in_org(pull.repository.full_name):
                            logger.debug(
                                f"Skipping PR in repo {pull.repository.full_name} (not in org {self.org})"
                            )
                            continue

                        # Generate PR URL
                        url = self.github_urls["pr"].format(
                            repo=pull.repository.full_name, number=pull.number
                        )
                        logger.debug(f"PR #{pull.number}: Generated URL {url}")

                        # Log PR details before processing
                        logger.debug(f"PR #{pull.number}: Title: {pull.title}")
                        logger.debug(f"PR #{pull.number}: State: {pull.state}")
                        logger.debug(f"PR #{pull.number}: Created: {pull.created_at}")
                        logger.debug(f"PR #{pull.number}: Comments: {pull.comments}")

                        # Create activity record
                        activity = {
                            "user": username,
                            "date": pull.created_at,
                            "type": "PullRequestEvent",
                            "repo": pull.repository.full_name,
                            "id": str(pull.id),
                            "url": url,
                            "details": {
                                "title": pull.title,
                                "state": pull.state,
                                "number": pull.number,
                                "comments": pull.comments,
                                # Omit PR specific details to avoid extra API calls
                                # 'commits': pr_obj.commits,
                                # 'additions': pr_obj.additions,
                                # 'deletions': pr_obj.deletions,
                                # 'changed_files': pr_obj.changed_files
                            },
                        }

                        user_activities.append(activity)
                        added_count += 1

                        # Log details about the pull request
                        logger.debug(
                            f"Added PR #{pull.number} in {pull.repository.full_name}: {pull.title[:40]}..."
                        )
                        logger.debug(
                            f"PR #{pull.number}: Successfully processed and added to activities"
                        )

                    logger.info(
                        f"Processed {pulls_count} PRs for {username}, added {added_count} to results"
                    )

                except RateLimitExceededException as e:
                    # Special handling for rate limit errors
                    reset_time = datetime.fromtimestamp(e.headers.get("X-RateLimit-Reset", 0))
                    logger.error(f"⚠️ GitHub Rate Limit Exceeded while fetching PRs for {username}!")
                    logger.error(f"Rate limit will reset at {reset_time.strftime('%H:%M:%S')}")

                    # Continue with what we have (don't re-raise)
                    logger.warning("Continuing with partial data due to rate limit")

                except GithubException as e:
                    logger.error(f"❌ Error searching pull requests for {username}: {e}")
                    # Continue with reviews to get at least some data

            except Exception as e:
                logger.error(f"❌ Unexpected error fetching pull requests for {username}: {e}")

            # Get reviews
            try:
                logger.info(f"🔎 Fetching reviews for {username}...")

                # Construct the search query
                query = f"reviewed-by:{username} updated:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"

                # Add org filter if specified
                if self.org:
                    query += f" org:{self.org}"

                logger.debug(f"Review search query: '{query}'")

                reviews_count = 0
                added_count = 0

                try:
                    # Execute the search
                    reviews = self.github.search_issues(query=query, sort="updated", order="desc")

                    # Process each review
                    for review_issue in reviews:
                        reviews_count += 1
                        logger.debug(
                            f"Processing review for PR #{review_issue.number}: Starting evaluation"
                        )

                        # Skip non-pull request issues
                        if not review_issue.pull_request:
                            logger.debug(
                                f"Skipping issue #{review_issue.number} (not a pull request)"
                            )
                            continue

                        # Apply organization filter if needed
                        if not is_in_org(review_issue.repository.full_name):
                            logger.debug(
                                f"Skipping review in repo {review_issue.repository.full_name} (not in org {self.org})"
                            )
                            continue

                        # Generate a generic review URL for the PR (no specific review ID)
                        url = self.github_urls["pr"].format(
                            repo=review_issue.repository.full_name, number=review_issue.number
                        )
                        logger.debug(f"Review for PR #{review_issue.number}: Generated URL {url}")

                        # Log review details
                        logger.debug(
                            f"Review for PR #{review_issue.number}: Title: {review_issue.title}"
                        )
                        logger.debug(
                            f"Review for PR #{review_issue.number}: State: {review_issue.state}"
                        )
                        logger.debug(
                            f"Review for PR #{review_issue.number}: Updated: {review_issue.updated_at}"
                        )
                        logger.debug(
                            f"Review for PR #{review_issue.number}: Repository: {review_issue.repository.full_name}"
                        )

                        # Create activity record
                        activity = {
                            "user": username,
                            "date": review_issue.updated_at,  # Use the issue update date instead
                            "type": "PullRequestReviewEvent",
                            "repo": review_issue.repository.full_name,
                            "id": str(review_issue.id),  # Using the issue ID instead of review ID
                            "url": url,
                            "details": {
                                "pr_number": review_issue.number,
                                "pr_title": review_issue.title,
                                "state": review_issue.state,
                            },
                        }

                        user_activities.append(activity)
                        added_count += 1

                        # Log details about the review
                        logger.debug(
                            f"Added review for PR #{review_issue.number} in {review_issue.repository.full_name}"
                        )
                        logger.debug(
                            f"Review for PR #{review_issue.number}: Successfully processed and added to activities"
                        )

                    logger.info(
                        f"Processed {reviews_count} reviews for {username}, added {added_count} to results"
                    )

                except RateLimitExceededException as e:
                    # Special handling for rate limit errors
                    reset_time = datetime.fromtimestamp(e.headers.get("X-RateLimit-Reset", 0))
                    logger.error(
                        f"⚠️ GitHub Rate Limit Exceeded while fetching reviews for {username}!"
                    )
                    logger.error(f"Rate limit will reset at {reset_time.strftime('%H:%M:%S')}")

                except GithubException as e:
                    logger.error(f"❌ Error searching reviews for {username}: {e}")

            except Exception as e:
                logger.error(f"❌ Unexpected error fetching reviews for {username}: {e}")

            # Log a debug message containing the first activity (if present) for debugging
            if user_activities and len(user_activities) > 0:
                first_activity = user_activities[0]
                logger.debug(
                    f"Sample activity for {username}: type={first_activity.get('type')}, date={first_activity.get('date')}, repo={first_activity.get('repo')}"
                )

            # Update the main activities list with this user's activities
            self.activities.extend(user_activities)

            logger.debug(
                f"Activity tracker instance now has {len(self.activities)} total activities after adding {username}'s activities"
            )
            logger.info(
                f"✅ Completed activity tracking for {username}: found {len(user_activities)} activities"
            )

            # Make a deep copy of the activities to ensure they're properly returned
            import copy

            return copy.deepcopy(user_activities)

        except GithubException as e:
            logger.error(f"❌ GitHub API error while fetching data for {username}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error processing user {username}: {e}")
            return []

    def get_data_frame(self):
        """Convert activities to a pandas DataFrame."""
        if not self.activities:
            logger.warning("No activities to convert to DataFrame.")
            return None

        logger.debug(f"Creating DataFrame with {len(self.activities)} activities")
        df = pd.DataFrame(self.activities)

        # Sort by date
        df = df.sort_values("date", ascending=False)
        return df
