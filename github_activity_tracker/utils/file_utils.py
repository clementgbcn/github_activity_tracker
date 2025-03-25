"""Utility functions for file handling."""

import os
from datetime import datetime

from .logging_config import logger

# Default location for users file
DEFAULT_USERS_FILE = "github_users.txt"


def load_users_from_file(file_path):
    """Load GitHub usernames from a file, one username per line.

    Lines starting with # are treated as comments and ignored.
    """
    try:
        with open(file_path, "r") as f:
            # Read lines, strip whitespace, filter out empty lines and comments
            users = []
            for line in f.readlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    users.append(line)

            if not users:
                logger.warning(f"⚠️ No users found in {file_path}")
            else:
                logger.debug(f"👥 Loaded {len(users)} users from {file_path}")
            return users
    except FileNotFoundError:
        logger.error(f"User file {file_path} not found.")
        return None
    except Exception as e:
        logger.error(f"Error reading user file: {e}")
        return None


def create_report_directory(parent_dir=""):  # noqa: C901
    """
    Create a new directory for the report with timestamp.

    Args:
        parent_dir (str): The parent directory where all reports will be stored.
                         If empty, uses current working directory.

    Returns:
        str: The absolute path to the newly created report directory.
    """
    # Use current directory if parent_dir is not specified
    if not parent_dir:
        parent_dir = os.path.join(os.getcwd(), "github_report")

    # Create parent reports directory if it doesn't exist
    parent_abs_path = os.path.abspath(parent_dir)
    os.makedirs(parent_abs_path, exist_ok=True)

    # Create timestamped subdirectory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_subdir = f"github_report_{timestamp}"
    abs_report_dir = os.path.join(parent_abs_path, report_subdir)

    # Create report directory
    os.makedirs(abs_report_dir, exist_ok=True)
    logger.info(f"Created report directory: {abs_report_dir}")

    # Copy default logo to the report directory
    try:
        # First try logo in parent directory
        default_logo_paths = [
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "logo.jpg"
            ),  # Look in package root
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logo.jpg"
            ),  # Look in project root
            os.path.join(os.getcwd(), "logo.jpg"),  # Look in current working directory
        ]

        # Add a simple default logo
        logo_copied = False
        for logo_path in default_logo_paths:
            if os.path.exists(logo_path):
                import shutil

                shutil.copy2(logo_path, os.path.join(abs_report_dir, "logo.jpg"))
                logger.info(f"Copied logo from {logo_path} to report directory")
                logo_copied = True
                break

        if not logo_copied:
            # Create a simple default logo (a colored rectangle) using PIL
            try:
                from PIL import Image, ImageDraw, ImageFont

                # Create a new image with a blue background
                img = Image.new("RGB", (200, 100), color=(0, 102, 204))
                d = ImageDraw.Draw(img)

                # Try to add text
                try:
                    font = ImageFont.load_default()
                    d.text((20, 40), "GitHub Activity", fill=(255, 255, 255), font=font)
                except Exception as font_error:
                    logger.warning(f"Couldn't add text to default logo: {font_error}")

                # Save the image as logo.jpg
                default_logo_path = os.path.join(abs_report_dir, "logo.jpg")
                img.save(default_logo_path)
                logger.info(f"Created default logo at {default_logo_path}")

                # Create a favicon from the same image but resized
                try:
                    favicon = img.resize((32, 32))
                    favicon_path = os.path.join(abs_report_dir, "favicon.ico")
                    favicon.save(favicon_path)
                    logger.info(f"Created favicon at {favicon_path}")
                except Exception as e:
                    logger.warning(f"Could not create favicon: {e}")

            except ImportError:
                logger.warning("PIL not available for creating default logo")
            except Exception as img_error:
                logger.warning(f"Failed to create default logo: {img_error}")
    except Exception as e:
        logger.error(f"Error handling logo: {e}")

    # Log directory contents for debugging
    try:
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Report directory contents: {os.listdir(abs_report_dir)}")
    except Exception as e:
        logger.error(f"Error listing directory: {e}")

    return abs_report_dir
