"""User management module for the GitHub Activity Tracker."""

import json
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import bcrypt

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class User:
    """User model for authentication and authorization."""

    user_id: str
    username: str
    is_admin: bool = False
    email: Optional[str] = None
    full_name: Optional[str] = None
    password_hash: Optional[str] = None

    def set_password(self, plain_password: str) -> None:
        """Hash and set the user's password.

        Args:
            plain_password: The plaintext password to hash and store
        """
        # Generate a salt and hash the password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
        self.password_hash = hashed.decode("utf-8")

    def verify_password(self, plain_password: str) -> bool:
        """Verify if the provided password matches the stored hash.

        Args:
            plain_password: The plaintext password to check

        Returns:
            bool: True if the password matches, False otherwise
        """
        if not self.password_hash:
            return False

        return bcrypt.checkpw(plain_password.encode("utf-8"), self.password_hash.encode("utf-8"))


class UserManager:
    """Manages user authentication and authorization."""

    def __init__(self, users_file: str = None):
        """Initialize the user manager.

        Args:
            users_file: Path to the JSON file containing user data.
                       If None, uses the default path.
        """
        if users_file is None:
            # Default path - relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            users_file = os.path.join(base_dir, "data", "users.json")

        self.users_file = users_file
        self.users: Dict[str, Dict[str, Any]] = {}
        self.needs_migration = False
        self.load_users()

        # Check if passwords need to be migrated
        if self.needs_migration:
            logger.info("Plain text passwords detected. Migrating to secure hashed passwords.")
            self.migrate_passwords()
            self.save_users()

    def load_users(self) -> bool:
        """Load users from the JSON file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            if not os.path.exists(self.users_file):
                logger.warning(f"Users file not found: {self.users_file}")
                return False

            with open(self.users_file, "r") as f:
                data = json.load(f)

            if not isinstance(data, dict) or "users" not in data:
                logger.error(f"Invalid users file format: {self.users_file}")
                return False

            # Create a lookup by user_id
            self.users = {user["user_id"]: user for user in data["users"]}

            # Check if any users have plaintext passwords
            for _, user_data in self.users.items():
                # If 'password' exists but 'password_hash' doesn't, we need migration
                if "password" in user_data and "password_hash" not in user_data:
                    self.needs_migration = True
                    break

            logger.info(f"Loaded {len(self.users)} users from {self.users_file}")

            if self.needs_migration:
                logger.warning(
                    "Detected plaintext passwords in users file. Will migrate to secure hashes."
                )

            return True

        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return False

    def save_users(self) -> bool:
        """Save users to the JSON file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)

            # Format for JSON file
            data = {"users": list(self.users.values())}

            with open(self.users_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self.users)} users to {self.users_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving users: {e}")
            return False

    def migrate_passwords(self) -> None:
        """Migrate plaintext passwords to secure hashed passwords."""
        migration_count = 0

        for _, user_data in self.users.items():
            # Skip users that already have password_hash
            if "password_hash" in user_data:
                continue

            # Get plaintext password
            if "password" in user_data:
                plaintext_password = user_data["password"]

                # Generate salt and hash password
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(plaintext_password.encode("utf-8"), salt)

                # Store password hash
                user_data["password_hash"] = password_hash.decode("utf-8")

                # Create a backup of the original password with a different key
                user_data["_old_password"] = user_data["password"]

                # Remove plaintext password
                del user_data["password"]

                migration_count += 1

        # Log migration results
        if migration_count > 0:
            logger.info(f"Successfully migrated {migration_count} user passwords to secure hashes")
        else:
            logger.info("No passwords needed migration")

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: The user ID to look up.

        Returns:
            User object if found, None otherwise.
        """
        user_data = self.users.get(user_id)
        if not user_data:
            return None

        user = User(
            user_id=user_data["user_id"],
            username=user_data["username"],
            is_admin=user_data.get("is_admin", False),
            email=user_data.get("email"),
            full_name=user_data.get("full_name"),
            password_hash=user_data.get("password_hash"),
        )

        return user

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password.

        Args:
            username: The username to authenticate.
            password: The password to verify.

        Returns:
            User object if authentication succeeds, None otherwise.
        """
        # Find user by username
        user_data = None
        for _, data in self.users.items():
            if data.get("username") == username:
                user_data = data
                break

        if not user_data:
            logger.warning(f"User not found: {username}")
            return None

        authenticated = False

        # Check for password hash first
        if "password_hash" in user_data:
            try:
                # Verify using bcrypt
                if bcrypt.checkpw(
                    password.encode("utf-8"), user_data["password_hash"].encode("utf-8")
                ):
                    authenticated = True
                else:
                    logger.warning(f"Invalid password (hash) for user: {username}")
            except Exception as e:
                logger.error(f"Error verifying password hash: {e}")

        # Fallback to plaintext password if hash verification failed or not available
        # This ensures backward compatibility during migration
        elif "password" in user_data and user_data.get("password") == password:
            authenticated = True
            logger.warning(
                f"User {username} authenticated with plaintext password. Migration needed."
            )

            # Automatically migrate this user
            try:
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
                user_data["password_hash"] = password_hash.decode("utf-8")
                user_data["_old_password"] = user_data["password"]
                del user_data["password"]
                self.save_users()
                logger.info(f"Automatically migrated password for user {username}")
            except Exception as e:
                logger.error(f"Auto-migration failed for user {username}: {e}")
        else:
            logger.warning(f"Invalid password for user: {username}")

        if not authenticated:
            return None

        # Return user object
        user = User(
            user_id=user_data["user_id"],
            username=user_data["username"],
            is_admin=user_data.get("is_admin", False),
            email=user_data.get("email"),
            full_name=user_data.get("full_name"),
            password_hash=user_data.get("password_hash"),
        )

        return user

    def add_user(self, user_data: Dict[str, Any]) -> Optional[User]:
        """Add a new user.

        Args:
            user_data: Dictionary containing user information.
                      Must include user_id, username, and password.

        Returns:
            New User object if successful, None otherwise.
        """
        # Validate required fields
        required_fields = ["user_id", "username"]
        if "password" not in user_data and "password_hash" not in user_data:
            required_fields.append("password")  # Either password or password_hash must be provided

        for field in required_fields:
            if field not in user_data:
                logger.error(f"Missing required field for new user: {field}")
                return None

        # Check if user_id already exists
        if user_data["user_id"] in self.users:
            logger.error(f"User ID already exists: {user_data['user_id']}")
            return None

        # Create a copy of the user data so we don't modify the original
        new_user_data = user_data.copy()

        # If plaintext password is provided, hash it
        if "password" in new_user_data and "password_hash" not in new_user_data:
            try:
                # Hash the password
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(new_user_data["password"].encode("utf-8"), salt)
                new_user_data["password_hash"] = password_hash.decode("utf-8")

                # Store original password as backup and then remove it
                new_user_data["_old_password"] = new_user_data["password"]
                del new_user_data["password"]
            except Exception as e:
                logger.error(f"Error hashing password: {e}")
                return None

        # Add user
        self.users[new_user_data["user_id"]] = new_user_data

        # Save users file
        self.save_users()

        # Return user object
        return User(
            user_id=new_user_data["user_id"],
            username=new_user_data["username"],
            is_admin=new_user_data.get("is_admin", False),
            email=new_user_data.get("email"),
            full_name=new_user_data.get("full_name"),
            password_hash=new_user_data.get("password_hash"),
        )

    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
        """Update an existing user.

        Args:
            user_id: The ID of the user to update.
            user_data: Dictionary containing updated user information.

        Returns:
            Updated User object if successful, None otherwise.
        """
        # Check if user exists
        if user_id not in self.users:
            logger.error(f"User not found for update: {user_id}")
            return None

        # Update user data
        current_data = self.users[user_id]

        # Handle password updates separately
        if "password" in user_data:
            try:
                # Hash the new password
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(user_data["password"].encode("utf-8"), salt)

                # Store the hash
                current_data["password_hash"] = password_hash.decode("utf-8")

                # Store original password as backup
                current_data["_old_password"] = user_data["password"]

                # Remove the password key from data to update
                user_data_copy = user_data.copy()
                del user_data_copy["password"]

                # Update other fields
                for key, value in user_data_copy.items():
                    current_data[key] = value
            except Exception as e:
                logger.error(f"Error updating password for user {user_id}: {e}")
                return None
        else:
            # No password update, just update other fields
            for key, value in user_data.items():
                current_data[key] = value

        # Save users file
        self.save_users()

        # Return updated user object
        return User(
            user_id=current_data["user_id"],
            username=current_data["username"],
            is_admin=current_data.get("is_admin", False),
            email=current_data.get("email"),
            full_name=current_data.get("full_name"),
            password_hash=current_data.get("password_hash"),
        )

    def delete_user(self, user_id: str) -> bool:
        """Delete a user.

        Args:
            user_id: The ID of the user to delete.

        Returns:
            True if successful, False otherwise.
        """
        if user_id not in self.users:
            logger.error(f"User not found for deletion: {user_id}")
            return False

        # Remove user
        del self.users[user_id]

        # Save users file
        self.save_users()

        return True

    def list_users(self) -> List[User]:
        """List all users.

        Returns:
            List of User objects.
        """
        return [
            User(
                user_id=data["user_id"],
                username=data["username"],
                is_admin=data.get("is_admin", False),
                email=data.get("email"),
                full_name=data.get("full_name"),
                password_hash=data.get("password_hash"),
            )
            for data in self.users.values()
        ]

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Change a user's password.

        Args:
            user_id: ID of the user whose password to change
            new_password: New plaintext password

        Returns:
            True if successful, False otherwise
        """
        # Check if user exists
        if user_id not in self.users:
            logger.error(f"User not found for password change: {user_id}")
            return False

        try:
            # Hash the new password
            salt = bcrypt.gensalt()
            password_hash = bcrypt.hashpw(new_password.encode("utf-8"), salt)

            # Update the user data
            self.users[user_id]["password_hash"] = password_hash.decode("utf-8")

            # If there was an old plaintext password, back it up
            if "password" in self.users[user_id]:
                self.users[user_id]["_old_password"] = self.users[user_id]["password"]
                del self.users[user_id]["password"]

            # Save users file
            self.save_users()
            logger.info(f"Password changed successfully for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error changing password for user {user_id}: {e}")
            return False

    def generate_random_password(self, length: int = 12) -> str:
        """Generate a secure random password.

        Args:
            length: Length of the password to generate (default: 12)

        Returns:
            A secure random password
        """
        # Use secrets module for cryptographically strong random numbers
        return secrets.token_urlsafe(length)


# Global user manager instance
user_manager = UserManager()


# Convenience functions
def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user."""
    return user_manager.authenticate(username, password)


def get_user_by_id(user_id: str) -> Optional[User]:
    """Get a user by ID."""
    return user_manager.get_user(user_id)


def add_user(user_data: Dict[str, Any]) -> Optional[User]:
    """Add a new user."""
    return user_manager.add_user(user_data)


def list_users() -> List[User]:
    """List all users."""
    return user_manager.list_users()


def create_user(
    username: str, password: str, email: Optional[str] = None, is_admin: bool = False
) -> Optional[User]:
    """Create a new user with the given credentials.

    Args:
        username: Username for the new user
        password: Password for the new user
        email: Optional email address
        is_admin: Whether the user should have admin privileges

    Returns:
        The newly created User object if successful, None otherwise
    """
    user_id = username.lower()  # Use lowercase username as user_id for simplicity
    user_data = {
        "user_id": user_id,
        "username": username,
        "password": password,  # Will be hashed by add_user
        "email": email,
        "is_admin": is_admin,
    }
    return user_manager.add_user(user_data)


def change_password(user_id: str, new_password: str) -> bool:
    """Change a user's password.

    Args:
        user_id: ID of the user
        new_password: New plaintext password

    Returns:
        True if successful, False otherwise
    """
    return user_manager.change_password(user_id, new_password)


def generate_random_password(length: int = 12) -> str:
    """Generate a secure random password.

    Args:
        length: Length of the password (default: 12)

    Returns:
        A secure random password
    """
    return user_manager.generate_random_password(length)
