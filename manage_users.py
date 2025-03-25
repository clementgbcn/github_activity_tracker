#!/usr/bin/env python3
"""Script to manage users from the command line."""

import argparse
import logging
import os
import sys
from getpass import getpass
from typing import Optional

from github_activity_tracker.web.auth.user_manager import (
    UserManager,
    change_password,
    create_user,
    generate_random_password,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("user_management")


def find_users_file() -> Optional[str]:
    """Find the users.json file in default locations."""
    possible_paths = [
        os.path.join("github_activity_tracker", "data", "users.json"),
        os.path.join("data", "users.json"),
        "users.json",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def list_all_users(user_manager: UserManager):
    """List all users in the system."""
    users = user_manager.list_users()

    if not users:
        print("No users found.")
        return

    print("\nUsers:")
    print("{:<15} {:<20} {:<30} {:<10}".format("User ID", "Username", "Email", "Admin"))
    print("-" * 75)

    for user in users:
        print(
            "{:<15} {:<20} {:<30} {:<10}".format(
                user.user_id, user.username, user.email or "-", "Yes" if user.is_admin else "No"
            )
        )
    print()


def add_new_user(user_manager: UserManager, args):
    """Add a new user."""
    username = args.username or input("Enter username: ")

    # Check if username already exists
    for user in user_manager.list_users():
        if user.username.lower() == username.lower():
            print(f"Error: User '{username}' already exists.")
            return False

    email = args.email or input("Enter email (optional): ")
    is_admin = args.admin or input("Make user admin? (y/N): ").lower() == "y"

    password = None
    if args.random_password:
        password = generate_random_password()
        print(f"Generated random password: {password}")
    else:
        password = getpass("Enter password: ")
        confirm = getpass("Confirm password: ")

        if password != confirm:
            print("Error: Passwords do not match.")
            return False

    # Create user
    user = create_user(username, password, email, is_admin)

    if user:
        print(f"User '{username}' created successfully.")
        return True
    else:
        print(f"Error creating user '{username}'.")
        return False


def reset_user_password(user_manager: UserManager, args):
    """Reset a user's password."""
    username = args.username or input("Enter username: ")

    # Find user
    user = None
    for u in user_manager.list_users():
        if u.username.lower() == username.lower():
            user = u
            break

    if not user:
        print(f"Error: User '{username}' not found.")
        return False

    password = None
    if args.random_password:
        password = generate_random_password()
        print(f"Generated random password: {password}")
    else:
        password = getpass("Enter new password: ")
        confirm = getpass("Confirm new password: ")

        if password != confirm:
            print("Error: Passwords do not match.")
            return False

    # Change password
    if change_password(user.user_id, password):
        print(f"Password for user '{username}' reset successfully.")
        return True
    else:
        print(f"Error resetting password for user '{username}'.")
        return False


def delete_existing_user(user_manager: UserManager, args):
    """Delete an existing user."""
    username = args.username or input("Enter username: ")

    # Find user
    user = None
    for u in user_manager.list_users():
        if u.username.lower() == username.lower():
            user = u
            break

    if not user:
        print(f"Error: User '{username}' not found.")
        return False

    # Confirm deletion
    if not args.force:
        confirm = input(
            f"Are you sure you want to delete user '{username}'? This cannot be undone. (y/N): "
        )
        if confirm.lower() != "y":
            print("Deletion cancelled.")
            return False

    # Delete user
    if user_manager.delete_user(user.user_id):
        print(f"User '{username}' deleted successfully.")
        return True
    else:
        print(f"Error deleting user '{username}'.")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Manage users for GitHub Activity Tracker")
    parser.add_argument("--users-file", help="Path to users.json file")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Add user command
    add_parser = subparsers.add_parser("add", help="Add a new user")
    add_parser.add_argument("--username", help="Username for the new user")
    add_parser.add_argument("--email", help="Email for the new user")
    add_parser.add_argument("--admin", action="store_true", help="Make the user an admin")
    add_parser.add_argument(
        "--random-password", action="store_true", help="Generate a random password"
    )

    # Reset password command
    reset_parser = subparsers.add_parser("reset-password", help="Reset a user's password")
    reset_parser.add_argument("--username", help="Username of the user")
    reset_parser.add_argument(
        "--random-password", action="store_true", help="Generate a random password"
    )

    # Delete user command
    delete_parser = subparsers.add_parser("delete", help="Delete a user")
    delete_parser.add_argument("--username", help="Username of the user to delete")
    delete_parser.add_argument("--force", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 1

    # Find users file
    users_file = args.users_file or find_users_file()
    if not users_file:
        print("Error: Could not find users.json file. Please specify with --users-file.")
        return 1

    logger.info(f"Using users file: {users_file}")

    # Create user manager
    user_manager = UserManager(users_file)

    # Run command
    if args.command == "list":
        list_all_users(user_manager)
        return 0
    elif args.command == "add":
        return 0 if add_new_user(user_manager, args) else 1
    elif args.command == "reset-password":
        return 0 if reset_user_password(user_manager, args) else 1
    elif args.command == "delete":
        return 0 if delete_existing_user(user_manager, args) else 1
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
