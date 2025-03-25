"""Email sending module for GitHub Activity Tracker.

This module provides functionality to send emails with GitHub activity reports
as attachments, supporting both HTML and CSV formats.
"""

import mimetypes
import os
import pathlib
import re
import shutil
import smtplib
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import sleep
from typing import Dict, List, Optional, Tuple, Union

try:
    from weasyprint import CSS, HTML
    from weasyprint.fonts import FontConfiguration

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

from ..utils.logging_config import logger


class EmailSender:
    """Email sender for GitHub Activity reports.

    This class provides functionality to send emails with GitHub activity
    reports attached, with support for both HTML and plain text emails.
    """

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        use_tls: bool = True,
        default_sender: str = None,
    ):
        """Initialize the email sender with SMTP settings.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            username: SMTP authentication username
            password: SMTP authentication password
            use_tls: Whether to use TLS encryption (default: True)
            default_sender: Default sender email address
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.default_sender = default_sender or username
        logger.debug(f"EmailSender initialized with server: {smtp_server}:{smtp_port}")

    def send_report(  # noqa: C901
        self,
        recipient: str,
        subject: str = "GitHub Activity Report",
        sender: str = None,
        report_path: str = None,
        activities: List[Dict] = None,
        date_from: str = None,
        date_to: str = None,
        format_name: str = "html",
        cc: List[str] = None,
        bcc: List[str] = None,
    ) -> bool:
        """Send an email with a GitHub activity report.

        Sends an email with a GitHub activity report attached. The report can
        be either a pre-generated report file, or can be generated from provided
        activity data.

        Args:
            recipient: Recipient email address
            subject: Email subject
            sender: Sender email address (uses default if not provided)
            report_path: Path to the report file or directory
            activities: List of GitHub activities (optional, for generated reports)
            date_from: Start date for the report (optional)
            date_to: End date for the report (optional)
            format_name: Format of the report ('html' or 'csv')
            cc: List of CC recipients
            bcc: List of BCC recipients

        Returns:
            True if the email was sent successfully, False otherwise
        """
        global plain_content, html_content, embedded_images, attachments
        try:
            sender = sender or self.default_sender

            # Create the email
            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient

            if cc:
                msg["Cc"] = ", ".join(cc)
            if bcc:
                msg["Bcc"] = ", ".join(bcc)

            # Get full recipient list for sending
            all_recipients = [recipient]
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)

            # Get current date if not provided
            if not date_from or not date_to:
                date_from = (datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
                date_to = datetime.now().strftime("%Y-%m-%d")

            # Start with report path validation
            if report_path:
                # Convert to Path object for easier manipulation
                report_dir = pathlib.Path(report_path)

                # Check if it's a directory or a file
                if report_dir.is_dir():
                    # For HTML reports, there should be an index.html file
                    if format_name.lower() == "html":
                        html_path = report_dir / "index.html"
                        if not html_path.exists():
                            logger.error(f"HTML report not found at {html_path}")
                            return False

                        # Generate email content from HTML report
                        html_content, plain_content, attachments, embedded_images = (
                            self._prepare_html_report_email(html_path, report_dir)
                        )

                    else:  # CSV reports
                        # For CSV reports, the report_path itself should be a CSV file
                        # or a directory containing a CSV file
                        csv_files = list(report_dir.glob("*.csv"))
                        if not csv_files:
                            logger.error(f"No CSV files found in {report_dir}")
                            return False

                        # Use the first CSV file found
                        csv_path = csv_files[0]

                        # Generate email content for CSV report
                        html_content, plain_content, attachments = self._prepare_csv_report_email(
                            csv_path
                        )

                else:  # It's a file
                    # For CSV reports, the file should exist and be a CSV
                    if format_name.lower() == "csv" and report_dir.suffix.lower() == ".csv":
                        csv_path = report_dir
                        html_content, plain_content, attachments = self._prepare_csv_report_email(
                            csv_path
                        )
                    else:
                        logger.error(f"Invalid report path: {report_path}")
                        return False

            # Add the email body
            text_part = MIMEText(plain_content, "plain")
            html_part = MIMEText(html_content, "html")

            # Add parts to the email
            msg.attach(text_part)
            msg.attach(html_part)

            # Add any embedded images
            if format_name.lower() == "html" and "embedded_images" in locals():
                for cid, (img_path, _) in embedded_images.items():
                    with open(img_path, "rb") as img:
                        img_data = img.read()
                        image = MIMEImage(img_data)
                        image.add_header("Content-ID", f"<{cid}>")
                        image.add_header("Content-Disposition", "inline")
                        msg.attach(image)

            # Add attachments
            if "attachments" in locals():
                for attachment in attachments:
                    if isinstance(attachment, dict):
                        # New format with additional metadata
                        file_path = attachment["path"]
                        label = attachment.get("label", os.path.basename(file_path))
                        mime_type = attachment.get("mime_type")
                    else:
                        # Old format - just a path string
                        file_path = attachment
                        label = os.path.basename(file_path)
                        mime_type = None

                    # Determine mime type if not provided
                    if not mime_type:
                        mime_type, _ = mimetypes.guess_type(file_path)
                        if not mime_type:
                            # Default to octet-stream if we can't determine the type
                            mime_type = "application/octet-stream"

                    with open(file_path, "rb") as f:
                        attachment_data = f.read()

                        # Create MIME attachment
                        if mime_type.startswith("application/"):
                            part = MIMEApplication(attachment_data, Name=label)
                        else:
                            # For other types, use the base MIME type
                            part = MIMEBase(*mime_type.split("/", 1))
                            part.set_payload(attachment_data)

                        # Add header
                        part.add_header("Content-Disposition", f'attachment; filename="{label}"')
                        msg.attach(part)

            # Send the email
            for attempt in range(3):  # Try up to 3 times
                try:
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        if self.use_tls:
                            server.starttls()

                        server.login(self.username, self.password)
                        server.sendmail(sender, all_recipients, msg.as_string())
                        logger.info(f"Email sent to {recipient}")
                        return True

                except Exception as e:
                    if attempt < 2:  # Not the last attempt
                        logger.warning(f"Email send attempt {attempt + 1} failed: {e}. Retrying...")
                        sleep(2)  # Short delay before retry
                    else:
                        logger.error(f"Failed to send email after 3 attempts: {e}")
                        return False

        except Exception as e:
            logger.exception(f"Error preparing email: {e}")
            return False

    def _prepare_html_report_email(
        self, html_path: Union[str, pathlib.Path], report_dir: Union[str, pathlib.Path]
    ) -> Tuple[str, str, List[Dict], Dict]:
        """Prepare email content for an HTML report.

        Args:
            html_path: Path to the HTML report file
            report_dir: Directory containing the report and related files

        Returns:
            Tuple containing (html_content, text_content, attachments, embedded_images)
        """
        # Convert paths to Path objects
        html_path = pathlib.Path(html_path)
        report_dir = pathlib.Path(report_dir)
        logger.debug(f"Preparing email from HTML report: {html_path}")

        # Read the HTML content
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Parse the HTML to extract information for the text version
        stats = self._extract_stats_from_html(html_content)

        # Create a simplified HTML version for the email
        email_html, embedded_images = self._create_email_friendly_html(html_content, report_dir)

        # Create a plain text version
        text_content = f"""GitHub Activity Report

Period: {stats.get("Period", "Not specified")}

EXECUTIVE SUMMARY:
This report tracks GitHub activity across {stats.get("Repositories", "?")} repositories by {stats.get("Users", "?")} users, with a total of {stats.get("Total Activities", "?")} activities recorded.

The full report is attached to this email.
"""  # noqa: E501

        # Prepare attachments
        attachments = []

        # Add the HTML report
        attachments.append(
            {
                "path": str(html_path),
                "label": "github_activity_report.html",
                "mime_type": "text/html",
            }
        )

        # Add visualization images
        for img_path in report_dir.glob("*.png"):
            if img_path.name in [
                "activity_trends.png",
                "activity_types.png",
                "user_comparison.png",
            ]:
                attachments.append(
                    {"path": str(img_path), "label": img_path.name, "mime_type": "image/png"}
                )

        # Add PDF if it exists
        pdf_path = report_dir / "github_activity_report.pdf"
        if not pdf_path.exists():
            # Try to generate a PDF version of the report
            generated_pdf = self._generate_pdf_from_html(html_path, report_dir)
            if generated_pdf:
                pdf_path = pathlib.Path(generated_pdf)

        if pdf_path.exists():
            attachments.append(
                {
                    "path": str(pdf_path),
                    "label": "github_activity_report.pdf",
                    "mime_type": "application/pdf",
                }
            )

        return email_html, text_content, attachments, embedded_images

    def _extract_stats_from_html(self, html_content: str) -> Dict[str, str]:
        """Extract key statistics from the HTML report.

        Args:
            html_content: HTML content of the report

        Returns:
            Dictionary with extracted statistics
        """
        stats = {}

        # Extract the period
        period_match = re.search(r"<span[^>]*>\s*Period:\s*([^<]+)\s*</span>", html_content)
        if period_match:
            stats["Period"] = period_match.group(1).strip()

        # Extract total activities
        activities_match = re.search(
            r"<div[^>]*>\s*(\d+)\s*</div>\s*<div[^>]*>\s*Activities\s*</div>", html_content
        )
        if activities_match:
            stats["Total Activities"] = activities_match.group(1).strip()

        # Extract user count
        users_match = re.search(
            r"<div[^>]*>\s*(\d+)\s*</div>\s*<div[^>]*>\s*Users\s*</div>", html_content
        )
        if users_match:
            stats["Users"] = users_match.group(1).strip()

        # Extract repository count
        repos_match = re.search(
            r"<div[^>]*>\s*(\d+)\s*</div>\s*<div[^>]*>\s*Repositories\s*</div>", html_content
        )
        if repos_match:
            stats["Repositories"] = repos_match.group(1).strip()

        logger.debug(f"Extracted stats from HTML: {stats}")
        return stats

    def _create_email_friendly_html(
        self, html_content: str, report_dir: pathlib.Path
    ) -> Tuple[str, Dict]:
        """Create a simplified HTML version that is email-client friendly.

        Args:
            html_content: Original HTML content
            report_dir: Directory containing the report and image files

        Returns:
            Tuple of (simplified_html, embedded_images) where embedded_images
            is a dictionary mapping Content-IDs to (image_path, mime_type) tuples
        """
        # Extract useful parts from the HTML
        summary_match = re.search(
            r'<div[^>]*class="summary-section[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
            html_content,
            re.DOTALL,
        )

        summary_html = ""
        if summary_match:
            summary_html = summary_match.group(1).strip()

        # Check for logo
        embedded_images = {}
        logo_cid = None

        # Find logo files
        for ext in ["jpg", "jpeg", "png", "webp"]:
            logo_path = report_dir / f"logo.{ext}"
            if logo_path.exists():
                # Generate a unique Content-ID
                logo_cid = f"logo_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                mime_type = mimetypes.guess_type(str(logo_path))[0]
                embedded_images[logo_cid] = (str(logo_path), mime_type)
                logger.debug(f"Found logo: {logo_path}")

                # Create the HTML for the logo
                logo_html = (
                    f'<div style="text-align: center; margin-bottom: 20px;">'
                    f'<img src="cid:{logo_cid}" alt="Logo" '
                    f'style="max-width: 200px; max-height: 100px;"></div>'
                )
                break

        if logo_cid is None:
            logo_html = ""

        # Create a simplified HTML for the email
        simplified_html = f"""<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GitHub Activity Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            img {{ max-width: 100%; height: auto; }}
            h1, h2, h3 {{ color: #0366d6; }}
            .footer {{ margin-top: 30px; font-size: 0.9em; color: #666; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            {logo_html}
            <h1>GitHub Activity Report</h1>
            {summary_html}
            <div class="footer">
                <p>Generated by GitHub Activity Tracker</p>
            </div>
        </div>
    </body>
    </html>
        """  # noqa: E501

        logger.debug(f"Embedded {len(embedded_images)} images in the email")
        return simplified_html, embedded_images

    def _simplify_css_for_email(self, css: str) -> str:
        """Simplify CSS for email clients by keeping only essential styles.

        Args:
            css: Original CSS content

        Returns:
            Simplified CSS
        """
        simplified_css = []

        # Select only the most important styling rules for email clients
        important_selectors = [
            "body",
            "h1",
            "h2",
            "h3",
            "p",
            "table",
            "th",
            "td",
            ".container",
            ".summary",
            ".footer",
            "img",
        ]

        for selector in important_selectors:
            # Match the selector and its rules
            selector_pattern = re.escape(selector) + r"\s*\{[^}]*\}"
            matches = re.finditer(selector_pattern, css, re.DOTALL)
            for match in matches:
                simplified_css.append(match.group(0))

        return "\n".join(simplified_css)

    def _generate_pdf_from_html(
        self, html_path: Union[str, pathlib.Path], report_dir: Union[str, pathlib.Path]
    ) -> Optional[str]:
        """Generate a PDF version of the HTML report using WeasyPrint.

        Converts the HTML report to PDF using the WeasyPrint library.

        Args:
            html_path: Path to the HTML file
            report_dir: Directory containing the report and images

        Returns:
            Path to the generated PDF file, or None if generation failed
        """
        # Create a unique name for this PDF generation attempt to avoid conflicts
        timestamp = datetime.now().strftime("%H%M%S")

        # Convert paths to Path objects to handle both string and Path inputs
        report_dir_path = pathlib.Path(report_dir)
        html_path = pathlib.Path(html_path)

        pdf_path = report_dir_path / f"github_activity_report_{timestamp}.pdf"
        final_pdf_path = report_dir_path / "github_activity_report.pdf"

        # Only use WeasyPrint for PDF generation
        if WEASYPRINT_AVAILABLE:
            try:
                logger.info(f"Generating PDF with WeasyPrint: {pdf_path}")

                # Get absolute file path for the HTML
                abs_html_path = str(html_path.resolve())

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

                # Generate PDF with enhanced styling
                HTML(abs_html_path).write_pdf(
                    str(pdf_path), stylesheets=[pdf_css], font_config=font_config
                )

                # Verify the PDF was generated successfully
                if pdf_path.exists() and pdf_path.stat().st_size > 0:
                    # Create a copy with a standard name for consistency
                    shutil.copy2(pdf_path, final_pdf_path)
                    logger.info(f"PDF successfully generated: {final_pdf_path}")
                    return str(final_pdf_path)
                else:
                    logger.warning(f"Generated PDF file is empty: {pdf_path}")
                    return None
            except Exception as e:
                logger.exception(f"Error generating PDF with WeasyPrint: {e}")
                return None
        else:
            logger.warning("WeasyPrint is not available - PDF generation skipped")
            return None

    def _prepare_csv_report_email(
        self, csv_path: Union[str, pathlib.Path]
    ) -> Tuple[str, str, List]:
        """Prepare email content for a CSV report.

        Args:
            csv_path: Path to the CSV report file

        Returns:
            Tuple containing (html_content, text_content, attachments)
        """
        # Convert to Path object
        csv_path = pathlib.Path(csv_path)
        logger.debug(f"Preparing email from CSV report: {csv_path}")

        # Determine activity count and user count
        user_count = 0
        activity_count = 0

        try:
            import pandas as pd

            # Read the CSV to extract statistics
            df = pd.read_csv(csv_path)
            activity_count = len(df)
            if "user" in df.columns:
                user_count = df["user"].nunique()
        except Exception as e:
            logger.warning(f"Could not extract statistics from CSV: {e}")
            # Fallback: count lines and assume the first line is a header
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    # Count lines but subtract 1 for the header
                    activity_count = sum(1 for _ in f) - 1
            except Exception as inner_e:
                logger.warning(f"Could not count lines in CSV: {inner_e}")

        # Guess the date range - for simplicity, assume it's the last 30 days
        end_date = datetime.now()
        start_date = end_date - datetime.timedelta(days=30)

        # Create HTML content
        html_content = f"""<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>GitHub Activity Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #0366d6; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            p {{ line-height: 1.5; }}
            .stats {{ background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px; padding: 15px; margin: 20px 0; }}
            .footer {{ margin-top: 30px; color: #586069; font-size: 12px; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <h1>GitHub Activity Report</h1>
        <p>GitHub activity summary for the period {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}.</p>

        <div class="stats">
            <p><strong>Users:</strong> {user_count}</p>
            <p><strong>Total activities:</strong> {activity_count}</p>
        </div>

        <p>The full report is attached as a CSV file for detailed analysis.</p>

        <div class="footer">
            <p>Generated by GitHub Activity Tracker on {datetime.now().strftime("%Y-%m-%d at %H:%M")}</p>
        </div>
    </body>
</html>
        """  # noqa: E501

        # Create text content
        text_content = f"""GitHub Activity Report

Period: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}

SUMMARY:
- Users: {user_count}
- Total activities: {activity_count}

The full report is attached as a CSV file for detailed analysis.

Generated by GitHub Activity Tracker on {datetime.now().strftime("%Y-%m-%d at %H:%M")}
        """

        # Create multipart/alternative part for both text and HTML
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(text_content, "plain"))
        alt_part.attach(MIMEText(html_content, "html"))

        # Add the CSV as an attachment
        attachments = [
            {"path": str(csv_path), "label": "github_activity_report.csv", "mime_type": "text/csv"}
        ]

        return html_content, text_content, attachments
