#!/usr/bin/env python3
"""Script to migrate plaintext passwords to secure bcrypt hashes."""

import logging
import os
import sys

from github_activity_tracker.web.auth.user_manager import UserManager

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("password_migration")


def main():
    """Main function to migrate passwords."""
    logger.info("Starting password migration")

    # Get users.json path
    if len(sys.argv) > 1:
        users_file = sys.argv[1]
    else:
        # Try to find users.json in the default locations
        possible_paths = [
            os.path.join("github_activity_tracker", "data", "users.json"),
            os.path.join("data", "users.json"),
            "users.json",
        ]

        users_file = None
        for path in possible_paths:
            if os.path.exists(path):
                users_file = path
                break

        if not users_file:
            logger.error("Could not find users.json file. Please specify the path as argument.")
            print("Usage: python migrate_passwords.py [path/to/users.json]")
            return 1

    logger.info(f"Using users file: {users_file}")

    # Create user manager and load users
    try:
        user_manager = UserManager(users_file)

        if not user_manager.needs_migration:
            logger.info("No passwords need migration. All passwords are already hashed.")
            return 0

        # Perform migration
        user_manager.migrate_passwords()

        # Save users file
        if user_manager.save_users():
            logger.info("Password migration completed successfully!")
        else:
            logger.error("Failed to save users file after migration.")
            return 1

    except Exception as e:
        logger.error(f"Error during password migration: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
