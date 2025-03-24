"""Configuration utilities for GitHub Activity Tracker."""

import json
import os
from typing import Any, Dict, List

from .logging_config import logger

# Default configuration file path
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".github_activity_tracker", "config.json")

# Default configuration values
DEFAULT_CONFIG = {
    "default_organization": "",
    "default_users_file": "",
    "default_users": [],
    "date_range_days": 30,
    "output_format": "html",
    "max_workers": 0,
}


def ensure_config_file() -> None:
    """Ensure the configuration file exists, creating it if needed."""
    config_dir = os.path.dirname(CONFIG_FILE)

    # Create the config directory if it doesn't exist
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
            logger.debug(f"Created configuration directory: {config_dir}")
        except Exception as e:
            logger.error(f"Failed to create configuration directory: {e}")
            return

    # Create the config file with default values if it doesn't exist
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            logger.info(f"Created default configuration file: {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to create configuration file: {e}")


def load_config() -> Dict[str, Any]:
    """Load the configuration from file.

    Returns:
        The configuration dictionary with all settings
    """
    ensure_config_file()

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        # Ensure all default keys exist
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value

        logger.debug(f"Loaded configuration from {CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration, using defaults: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> bool:
    """Save the configuration to file.

    Args:
        config: The configuration dictionary to save

    Returns:
        True if successful, False otherwise
    """
    ensure_config_file()

    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.debug(f"Saved configuration to {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False


def get_default_organization() -> str:
    """Get the default organization from config.

    Returns:
        The default organization name or empty string if not set
    """
    config = load_config()
    return config.get("default_organization", "")


def set_default_organization(organization: str) -> bool:
    """Set the default organization in config.

    Args:
        organization: The organization name to set as default

    Returns:
        True if successful, False otherwise
    """
    config = load_config()
    config["default_organization"] = organization
    return save_config(config)


def get_default_users() -> List[str]:
    """Get the default users list from config.

    Returns:
        List of default GitHub usernames
    """
    config = load_config()

    # If default_users_file is set and exists, use that
    default_users_file = config.get("default_users_file", "")
    if default_users_file and os.path.exists(default_users_file):
        try:
            from .file_utils import load_users_from_file

            users = load_users_from_file(default_users_file)
            if users:
                return users
        except Exception as e:
            logger.error(f"Error loading default users from file: {e}")

    # Fall back to the list in the config
    return config.get("default_users", [])


def set_default_users(users: List[str]) -> bool:
    """Set the default users list in config.

    Args:
        users: List of GitHub usernames to set as default

    Returns:
        True if successful, False otherwise
    """
    config = load_config()
    config["default_users"] = users
    return save_config(config)


def get_default_users_file() -> str:
    """Get the default users file path from config.

    Returns:
        Path to the default users file or empty string if not set
    """
    config = load_config()
    return config.get("default_users_file", "")


def set_default_users_file(file_path: str) -> bool:
    """Set the default users file path in config.

    Args:
        file_path: Path to the users file to set as default

    Returns:
        True if successful, False otherwise
    """
    config = load_config()
    config["default_users_file"] = file_path
    return save_config(config)
