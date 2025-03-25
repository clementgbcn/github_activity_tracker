"""Visualization module for creating graphs and charts."""

import os

# Set the Matplotlib backend to 'Agg' for non-interactive mode (thread-safe)
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from ..utils.logging_config import logger


class ActivityVisualizer:
    """Class for creating visualizations from GitHub activity data."""

    @staticmethod
    def generate_insights(df, output_dir=""):
        """Generate insights and visualizations from activity data."""
        if df is None or df.empty:
            logger.warning("No activities to analyze.")
            return None

        logger.debug(f"Generating insights from {len(df)} activities")

        # Overview statistics
        total_activities = len(df)
        user_count = df["user"].nunique()
        repo_count = df["repo"].nunique()
        event_counts = df["type"].value_counts()
        user_activity_counts = df["user"].value_counts()
        repo_activity_counts = df["repo"].value_counts().head(10)

        logger.info("\n===== GITHUB ACTIVITY INSIGHTS =====")
        logger.info(f"Total activities: {total_activities}")
        logger.info(f"Users: {user_count}")
        logger.info(f"Repositories: {repo_count}")

        logger.info("\n--- Activity Types ---")
        for event_type, count in event_counts.items():
            logger.info(f"{event_type}: {count}")

        logger.info("\n--- User Activities ---")
        for user, count in user_activity_counts.items():
            logger.info(f"{user}: {count} activities")

            # User-specific PR and review counts
            user_df = df[df["user"] == user]
            prs = user_df[user_df["type"] == "PullRequestEvent"]
            reviews = user_df[user_df["type"] == "PullRequestReviewEvent"]

            if not prs.empty:
                logger.info(f"  - Pull Requests: {len(prs)}")
            if not reviews.empty:
                logger.info(f"  - Reviews: {len(reviews)}")

        logger.info("\n--- Top Repositories ---")
        for repo, count in repo_activity_counts.items():
            logger.info(f"{repo}: {count} activities")

        logger.debug("Generating visualizations...")

        # Create visualizations
        trends_graph = ActivityVisualizer.plot_activity_trends(df, output_dir)
        types_graph = ActivityVisualizer.plot_activity_types(df, output_dir)
        user_graph = ActivityVisualizer.plot_user_comparison(df, output_dir)

        return {
            "total_activities": total_activities,
            "users": user_count,
            "repositories": repo_count,
            "activity_types": event_counts.to_dict(),
            "user_activities": user_activity_counts.to_dict(),
            "top_repos": repo_activity_counts.to_dict(),
            "graphs": {"trends": trends_graph, "types": types_graph, "users": user_graph},
        }

    @staticmethod
    def plot_activity_trends(df, output_dir=""):
        """Plot activity trends over time."""
        logger.debug("Generating activity trends plot")

        plt.figure(figsize=(12, 6))
        plt.style.use("ggplot")

        # Convert to datetime and group by day
        df["date"] = pd.to_datetime(df["date"])
        daily_activity = df.groupby(df["date"].dt.date).size()

        logger.debug(f"Plotting activity trends across {len(daily_activity)} days")

        # Use a color gradient
        line_color = "#0366d6"
        marker_color = "#2188ff"

        # Plot with enhanced styling
        ax = daily_activity.plot(
            kind="line",
            marker="o",
            linewidth=3,
            color=line_color,
            markerfacecolor=marker_color,
            markeredgecolor="white",
            markersize=8,
        )

        # Add grid but with custom styling
        ax.grid(True, linestyle="--", alpha=0.7)

        # Add area under the curve with transparency
        ax.fill_between(daily_activity.index, daily_activity.values, color=line_color, alpha=0.1)

        # Customize title and labels
        plt.title("Daily GitHub Activity", fontsize=16, fontweight="bold")
        plt.xlabel("Date", fontsize=12)
        plt.ylabel("Number of Activities", fontsize=12)

        # Optimize figure
        plt.tight_layout()

        # Add a subtle border
        for spine in ax.spines.values():
            spine.set_edgecolor("#dddddd")

        filename = os.path.join(output_dir, "activity_trends.png")
        plt.savefig(filename, dpi=100, bbox_inches="tight")
        plt.close()

        logger.debug(f"Activity trends plot saved to {filename}")
        return filename

    @staticmethod
    def plot_activity_types(df, output_dir=""):
        """Plot distribution of activity types."""
        logger.debug("Generating activity types plot")

        plt.figure(figsize=(10, 6))
        plt.style.use("ggplot")

        # Get event counts
        event_counts = df["type"].value_counts()
        logger.debug(f"Found {len(event_counts)} different activity types")

        # Define a custom color palette
        colors = ["#2188ff", "#0366d6", "#6f42c1", "#ea4aaa", "#28a745"]

        # Ensure we have enough colors by cycling if needed
        if len(event_counts) > len(colors):
            colors = colors * (len(event_counts) // len(colors) + 1)

        # Create the plot with enhanced styling
        ax = event_counts.plot(
            kind="bar",
            color=colors[: len(event_counts)],
            edgecolor="white",
            linewidth=1.5,
            width=0.7,
        )

        # Add value labels on top of each bar
        for i, v in enumerate(event_counts):
            ax.text(i, v + 0.5, str(v), ha="center", fontweight="bold")

        # Customize the grid
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        # Remove top and right spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Add subtle border to remaining spines
        for spine in ["bottom", "left"]:
            ax.spines[spine].set_edgecolor("#dddddd")

        # Customize title and labels
        plt.title("GitHub Activity Types", fontsize=16, fontweight="bold")
        plt.xlabel("Event Type", fontsize=12)
        plt.ylabel("Count", fontsize=12)
        plt.xticks(rotation=30, ha="right")

        # Adjust layout
        plt.tight_layout()

        filename = os.path.join(output_dir, "activity_types.png")
        plt.savefig(filename, dpi=100, bbox_inches="tight")
        plt.close()

        logger.debug(f"Activity types plot saved to {filename}")
        return filename

    @staticmethod
    def plot_user_comparison(df, output_dir=""):
        """Plot activity comparison between users."""
        logger.debug("Generating user comparison plot")

        plt.figure(figsize=(12, 8))
        plt.style.use("ggplot")

        # Get counts for each user and activity type
        user_event_counts = pd.crosstab(df["user"], df["type"])

        # Sort users by total activity count for better visualization
        user_totals = user_event_counts.sum(axis=1).sort_values(ascending=False)
        sorted_user_event_counts = user_event_counts.loc[user_totals.index]

        logger.debug(
            f"Comparing {len(user_totals)} users with"
            f" {len(user_event_counts.columns)} activity types"
        )

        # Define a custom color palette
        colors = ["#2188ff", "#0366d6", "#6f42c1", "#ea4aaa", "#28a745", "#f9c513", "#cb2431"]

        # Ensure we have enough colors
        if len(user_event_counts.columns) > len(colors):
            colors = colors * (len(user_event_counts.columns) // len(colors) + 1)

        # Plot stacked bar chart with enhanced styling
        ax = sorted_user_event_counts.plot(
            kind="bar",
            stacked=True,
            figsize=(12, 8),
            color=colors[: len(user_event_counts.columns)],
            edgecolor="white",
            linewidth=0.6,
            width=0.75,
        )

        # Add total count labels at the top of each bar
        for i, total in enumerate(user_totals):
            ax.text(i, total + 0.5, str(total), ha="center", fontweight="bold")

        # Customize grid
        ax.grid(axis="y", linestyle="--", alpha=0.7)

        # Remove top and right spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        # Customize remaining spines
        for spine in ["bottom", "left"]:
            ax.spines[spine].set_edgecolor("#dddddd")

        # Customize title and labels with better styling
        plt.title("User Activity Comparison", fontsize=16, fontweight="bold")
        plt.xlabel("GitHub User", fontsize=12)
        plt.ylabel("Number of Activities", fontsize=12)

        # Improve legend styling
        plt.legend(
            title="Activity Type",
            bbox_to_anchor=(1.05, 1),
            loc="upper left",
            frameon=True,
            framealpha=0.9,
            edgecolor="#dddddd",
        )

        # Add a subtle background color
        ax.set_facecolor("#f8f9fa")

        # Optimize figure layout
        plt.tight_layout()

        filename = os.path.join(output_dir, "user_comparison.png")
        plt.savefig(filename, dpi=100, bbox_inches="tight")
        plt.close()

        logger.debug(f"User comparison plot saved to {filename}")
        return filename
