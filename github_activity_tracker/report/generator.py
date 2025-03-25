"""Report generation module for GitHub Activity Tracker.

This module provides functionality to generate reports from GitHub activity data
in various formats (CSV, HTML, DataFrame). It includes visualization generation
and templating for rich HTML reports.
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union, overload

import jinja2
import pandas as pd

from ..utils.file_utils import create_report_directory
from ..utils.logging_config import logger
from .visualization import ActivityVisualizer


class ReportGenerator:
    """Generates GitHub activity reports in various formats.

    This class provides static methods to create different types of reports
    from GitHub activity data, including CSV files, interactive HTML reports
    with visualizations, or pandas DataFrames for further analysis.

    The HTML reports include:
    - Activity trends over time
    - Distribution of activity types
    - User comparison visualizations
    - Interactive filtering and sorting of activities
    - Detailed activity information
    """

    @staticmethod
    @overload
    def generate_report(
        activities: Union[List[Dict[str, Any]], pd.DataFrame], output_format: Literal["csv", "html"]
    ) -> Optional[str]: ...

    @staticmethod
    @overload
    def generate_report(
        activities: Union[List[Dict[str, Any]], pd.DataFrame], output_format: Literal["dataframe"]
    ) -> Optional[pd.DataFrame]: ...

    @staticmethod
    def generate_report(
        activities: Union[List[Dict[str, Any]], pd.DataFrame], output_format: str = "csv"
    ) -> Optional[Union[str, pd.DataFrame]]:
        """Generate a report of GitHub activities.

        Creates a report from GitHub activity data in the specified format.

        Args:
            activities: List of GitHub activities or a DataFrame containing activity data
            output_format: Format of the report ('csv', 'html', or 'dataframe')

        Returns:
            Path to the report file (string) for 'csv' or 'html' formats,
            or a DataFrame for 'dataframe' format. Returns None if no activities
            are provided or if the report generation fails.

        Raises:
            ValueError: If an invalid output format is specified
        """
        # Convert to DataFrame if needed
        if not isinstance(activities, pd.DataFrame):
            if not activities:
                logger.warning("No activities to report.")
                return None

            # Log activity counts by user for debugging
            user_counts = {}
            for activity in activities:
                user = activity.get("user", "unknown")
                user_counts[user] = user_counts.get(user, 0) + 1

            logger.debug(f"Activities by user: {user_counts}")
            logger.info(
                f"Generating report with {len(activities)}"
                f" activities from {len(user_counts)} unique users"
            )

            # Create DataFrame from activities list
            df = pd.DataFrame(activities)
            logger.debug(f"Created DataFrame with {len(df)} rows from {len(activities)} activities")
        else:
            df = activities
            logger.debug(f"Using provided DataFrame with {len(df)} rows")

        logger.debug(
            f"Creating report with {len(df)} activities from {df['user'].nunique()} unique users"
        )

        # Sort by date
        df = df.sort_values("date", ascending=False)

        # Generate the appropriate format
        if output_format == "csv":
            return ReportGenerator._generate_csv_report(df)
        elif output_format == "html":
            return ReportGenerator._generate_html_report(df)
        else:
            logger.info("Returning DataFrame without saving to file")
            return df

    @staticmethod
    def _generate_csv_report(df):
        """Generate a CSV report from a DataFrame."""
        filename = f"github_activity_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        logger.info(f"Saving CSV report to {filename}")
        df.to_csv(filename, index=False)
        logger.info(f"Report saved to {filename}")
        return filename

    @staticmethod
    def _generate_html_report(df):  # noqa: C901
        """Generate an HTML report with visualizations."""
        # Create output directory for the report and assets
        report_dir = create_report_directory()

        # Try to find and copy the logo (checking multiple formats)
        logo_found = False
        logo_filename = "logo.jpg"  # Default filename for template

        # Check for logo files in various formats
        for ext in ["jpg", "jpeg", "png", "webp"]:
            logo_path = Path(__file__).parent.parent.parent / f"logo.{ext}"
            if logo_path.exists():
                logo_dest = Path(report_dir) / f"logo.{ext}"
                logger.debug(f"Found logo in {ext} format, copying from {logo_path} to {logo_dest}")
                shutil.copy2(logo_path, logo_dest)
                logo_found = True
                logo_filename = f"logo.{ext}"  # Store for template
                break

        if not logo_found:
            logger.warning("No logo file found in any supported format (jpg, jpeg, png, webp)")

        # Generate the insights with graphs
        logger.info("Generating insights and visualizations...")
        insights = ActivityVisualizer.generate_insights(df, report_dir)

        # Create a more readable HTML report with clickable links
        filename = os.path.join(report_dir, "index.html")
        logger.debug(f"Creating HTML report at {filename}")

        # Define PDF filename for later use with WeasyPrint
        logger.debug("Setting up for PDF generation with WeasyPrint")
        pdf_filename = os.path.join(report_dir, "github_activity_report.pdf")

        # Convert URLs to clickable HTML links
        def make_clickable(val):
            return f'<a href="{val}" target="_blank">Link</a>'

        # Apply formatting
        html_df = df.copy()
        html_df["url"] = html_df["url"].apply(make_clickable)

        # Format activity details for better readability
        def format_details(details):
            if details is None:
                return ""
            if isinstance(details, dict):
                result = "<ul>"
                for key, value in details.items():
                    result += f"<li><strong>{key}:</strong> {value}</li>"
                result += "</ul>"
                return result
            return str(details)

        # Store the original details for state extraction
        html_df["original_details"] = html_df["details"]
        html_df["details"] = html_df["details"].apply(format_details)

        # Extract PR state to its own column for better filtering and display
        def get_pr_state(row):
            if not isinstance(row["original_details"], dict):
                return "unknown"

            details = row["original_details"]

            # Check for direct state field
            if "state" in details:
                return details["state"]

            # Check for pr_state field
            if "pr_state" in details:
                return details["pr_state"]

            # Return unknown if no state information is found
            return "unknown"

        # Add new state column
        html_df["state"] = html_df.apply(get_pr_state, axis=1)

        # Extract other details into separate columns
        def extract_title(row):
            if not isinstance(row["original_details"], dict):
                return ""
            details = row["original_details"]
            return details.get("title", details.get("pr_title", ""))

        def extract_number(row):
            if not isinstance(row["original_details"], dict):
                return ""
            details = row["original_details"]
            return str(details.get("number", details.get("pr_number", "")))

        def extract_comments(row):
            if not isinstance(row["original_details"], dict):
                return ""
            details = row["original_details"]
            return str(details.get("comments", ""))

        def extract_jira_id(row):
            """Extract JIRA ticket ID (e.g., SEC-1243, K9-1345) from the title."""
            # Get the title from the row
            title = extract_title(row)
            if not title:
                return ""

            # Look for pattern: letters, hyphen, numbers
            # (e.g., abd-1243, efg-1345, p8-123)
            # Match both uppercase and lowercase with
            # at least one letter followed by hyphen and digits
            jira_pattern = re.compile(r"([A-Za-z][A-Za-z0-9]*-\d+)")
            match = jira_pattern.search(title)

            if match:
                return match.group(1)
            return ""

        def create_jira_link(row):
            """Create a clickable JIRA link if a ticket ID is found."""
            jira_id = extract_jira_id(row)
            if not jira_id:
                return ""

            # Get JIRA URL prefix from environment or use a default
            jira_url_prefix = os.getenv("JIRA_URL_PREFIX", "https://jira.example.com/browse/")

            # Create clickable link
            return f'<a href="{jira_url_prefix}{jira_id}" target="_blank">{jira_id}</a>'

        # Add new detailed columns
        html_df["title"] = html_df.apply(extract_title, axis=1)
        html_df["number"] = html_df.apply(extract_number, axis=1)
        html_df["comments"] = html_df.apply(extract_comments, axis=1)
        html_df["jira_link"] = html_df.apply(create_jira_link, axis=1)

        # Add ID to the table for JavaScript to reference
        display_columns = [
            "user",
            "date",
            "type",
            "state",
            "repo",
            "title",
            "number",
            "comments",
            "jira_link",
            "url",
        ]

        # Remove details column from display since we're now showing individual fields
        if "details" in html_df.columns:
            del html_df["details"]

        # Generate table HTML
        table_html = html_df[display_columns].to_html(escape=False, render_links=True, index=False)
        table_html = table_html.replace(
            "<table", '<table id="activity-table" class="resizable-table"'
        )

        # Load the HTML template
        template_loader = jinja2.FileSystemLoader(
            searchpath=str(Path(__file__).parent.parent / "templates")
        )
        template_env = jinja2.Environment(loader=template_loader)
        template = template_env.get_template("report.html")

        # Render the template with data
        start_date = (datetime.now() - pd.Timedelta(days=30)).strftime("%b %d, %Y")
        end_date = datetime.now().strftime("%b %d, %Y")

        # logo_filename was determined earlier when searching for the logo

        # Make sure we're using just the filenames for images
        # (Flask URL handling will be done at runtime)
        html_output = template.render(
            start_date=start_date,
            end_date=end_date,
            total_activities=insights["total_activities"],
            users=insights["users"],
            repos=insights["repositories"],
            # Use just the filenames
            trends=os.path.basename(insights["graphs"]["trends"]),
            types=os.path.basename(insights["graphs"]["types"]),
            user_comparison=os.path.basename(insights["graphs"]["users"]),
            table_html=table_html,
            logo_path=logo_filename,
            generation_date=datetime.now().strftime("%B %d, %Y at %H:%M"),
        )

        # Write the HTML file
        logger.debug("Writing HTML content to file...")
        with open(filename, "w") as f:
            f.write(html_output)

        logger.info(f"HTML report saved to {filename}")

        # Generate PDF from HTML using WeasyPrint
        if pdf_filename:
            try:
                from weasyprint import CSS, HTML
                from weasyprint.text.fonts import FontConfiguration

                logger.info(f"Generating PDF report with WeasyPrint: {pdf_filename}")

                # Get absolute file path for input file
                abs_html_path = os.path.abspath(filename)

                # Set up font configuration
                font_config = FontConfiguration()

                # Custom CSS for PDF output with enhanced landscape settings
                pdf_css = CSS(
                    string="""
                    @page {
                        size: 11in 8.5in landscape;
                        margin: 0.5in;
                    }
                    body {
                        width: 10in;
                        height: 7.5in;
                        max-width: 100%;
                        margin: 0 auto;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    }
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 0.85em;
                        table-layout: auto;
                    }
                    th, td {
                        padding: 6px;
                        border: 1px solid #ddd;
                    }
                    th {
                        background-color: #f2f2f2;
                    }
                    * {
                        -webkit-print-color-adjust: exact;
                        color-adjust: exact;
                    }
                """,  # noqa: E501
                    font_config=font_config,
                )

                # Generate PDF with custom styling
                HTML(abs_html_path).write_pdf(
                    pdf_filename, stylesheets=[pdf_css], font_config=font_config
                )

                logger.info(f"PDF report successfully generated: {pdf_filename}")
            except ImportError:
                logger.warning("WeasyPrint not installed - PDF generation skipped")
            except Exception as e:
                logger.error(f"Failed to generate PDF with WeasyPrint: {e}")
                logger.exception("Detailed PDF generation error:")

        return filename
