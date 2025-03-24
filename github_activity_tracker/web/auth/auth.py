"""Authentication functions and classes for the GitHub Activity Tracker web UI."""

import json
import logging
import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

# Setup logging
logger = logging.getLogger(__name__)


# Define User class
class User:
    """User class for authentication and session management."""

    def __init__(
        self,
        username: str,
        password_hash: str,
        email: Optional[str] = None,
        is_admin: bool = False,
        user_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        """Initialize a user.

        Args:
            username: The username for the user
            password_hash: The hashed password for the user
            email: Optional email address for the user
            is_admin: Whether the user has admin privileges
            user_id: Optional user ID (will be generated if not provided)
            created_at: Optional creation timestamp (will be set to now if not provided)
        """
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.is_admin = is_admin
        self.user_id = user_id or str(uuid.uuid4())
        self.created_at = created_at or datetime.now()

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash.

        Args:
            password: The plaintext password to check

        Returns:
            bool: True if the password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)

    @classmethod
    def create(
        cls, username: str, password: str, email: Optional[str] = None, is_admin: bool = False
    ) -> "User":
        """Create a new user with a hashed password.

        Args:
            username: The username for the new user
            password: The plaintext password to hash and store
            email: Optional email address for the user
            is_admin: Whether the user has admin privileges

        Returns:
            User: A new User instance
        """
        password_hash = generate_password_hash(password)
        return cls(username, password_hash, email, is_admin)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the user to a dictionary for serialization.

        Returns:
            Dict[str, Any]: User data as a dictionary
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password_hash": self.password_hash,
            "email": self.email,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Create a User instance from a dictionary.

        Args:
            data: Dictionary containing user data

        Returns:
            User: A User instance populated with the provided data
        """
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                created_at = datetime.now()

        return cls(
            username=data["username"],
            password_hash=data["password_hash"],
            email=data.get("email"),
            is_admin=data.get("is_admin", False),
            user_id=data.get("user_id"),
            created_at=created_at,
        )


class UserManager:
    """Manages user authentication and persistence."""

    def __init__(self, users_file: str):
        """Initialize the user manager.

        Args:
            users_file: Path to the JSON file storing user data
        """
        self.users_file = users_file
        self.users: Dict[str, User] = {}
        self._load_users()

    def _load_users(self) -> None:
        """Load users from the users file."""
        self.users = {}

        # Create the users file if it doesn't exist
        users_path = Path(self.users_file)
        if not users_path.exists():
            users_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_users()
            return

        try:
            with open(self.users_file, "r") as f:
                users_data = json.load(f)

            for user_data in users_data:
                user = User.from_dict(user_data)
                self.users[user.username] = user

            logger.info(f"Loaded {len(self.users)} users from {self.users_file}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading users from {self.users_file}: {e}")
            self.users = {}

    def _save_users(self) -> None:
        """Save users to the users file."""
        users_data = [user.to_dict() for user in self.users.values()]

        # Ensure directory exists
        users_path = Path(self.users_file)
        users_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.users_file, "w") as f:
                json.dump(users_data, f, indent=2)
            logger.info(f"Saved {len(self.users)} users to {self.users_file}")
        except Exception as e:
            logger.error(f"Error saving users to {self.users_file}: {e}")

    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username.

        Args:
            username: The username to look up

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        return self.users.get(username.lower())

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: The user ID to look up

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        for user in self.users.values():
            if user.user_id == user_id:
                return user
        return None

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password.

        Args:
            username: The username to authenticate
            password: The password to check

        Returns:
            Optional[User]: The authenticated user if successful, None otherwise
        """
        user = self.get_user(username.lower())
        if user and user.check_password(password):
            return user
        return None

    # Alias for compatibility with app.py
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Alias for authenticate() for compatibility."""
        return self.authenticate(username, password)

    def add_user(
        self, username: str, password: str, email: Optional[str] = None, is_admin: bool = False
    ) -> User:
        """Add a new user.

        Args:
            username: The username for the new user
            password: The plaintext password for the new user
            email: Optional email address for the user
            is_admin: Whether the user has admin privileges

        Returns:
            User: The newly created user

        Raises:
            ValueError: If the username already exists
        """
        username = username.lower()
        if username in self.users:
            raise ValueError(f"User '{username}' already exists")

        user = User.create(username, password, email, is_admin)
        self.users[username] = user
        self._save_users()
        return user

    def update_user(self, user: User) -> None:
        """Update an existing user.

        Args:
            user: The user to update

        Raises:
            ValueError: If the user doesn't exist
        """
        username = user.username.lower()
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")

        self.users[username] = user
        self._save_users()

    def delete_user(self, username: str) -> None:
        """Delete a user.

        Args:
            username: The username of the user to delete

        Raises:
            ValueError: If the user doesn't exist
        """
        username = username.lower()
        if username not in self.users:
            raise ValueError(f"User '{username}' does not exist")

        del self.users[username]
        self._save_users()

    def change_password(self, username: str, new_password: str) -> None:
        """Change a user's password.

        Args:
            username: The username of the user to update
            new_password: The new plaintext password

        Raises:
            ValueError: If the user doesn't exist
        """
        username = username.lower()
        user = self.get_user(username)
        if not user:
            raise ValueError(f"User '{username}' does not exist")

        user.password_hash = generate_password_hash(new_password)
        self.update_user(user)

    def has_users(self) -> bool:
        """Check if there are any users.

        Returns:
            bool: True if there are users, False otherwise
        """
        return len(self.users) > 0

    def get_all_users(self) -> List[User]:
        """Get all users.

        Returns:
            List[User]: List of all users
        """
        return list(self.users.values())

    def create_default_admin(self, username: str = "admin", password: Optional[str] = None) -> User:
        """Create a default admin user if no users exist.

        Args:
            username: The username for the default admin (default: 'admin')
            password: The password for the default admin (default: randomly generated)

        Returns:
            User: The newly created admin user
        """
        if self.has_users():
            admin_user = next((u for u in self.users.values() if u.is_admin), None)
            if admin_user:
                return admin_user

        # Generate a random password if none is provided
        if not password:
            password = uuid.uuid4().hex[:12]
            logger.info(f"Generated random password for default admin user: {password}")

        admin_user = self.add_user(username, password, is_admin=True)
        logger.info(f"Created default admin user '{username}'")
        return admin_user


# Create auth blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle login requests."""
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("auth/login.html")

        user = current_app.user_manager.authenticate(username, password)
        if user:
            # Set session variables
            session["user_id"] = user.user_id
            session["username"] = user.username
            session["is_admin"] = user.is_admin

            # Get the next URL or default to index
            next_url = request.args.get("next") or url_for("index")

            # Redirect to the requested page
            return redirect(next_url)
        else:
            flash("Invalid username or password", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    """Handle logout requests."""
    # Clear session
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("is_admin", None)

    flash("You have been logged out", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile")
def profile():
    """Display user profile."""
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.url))

    user = current_app.user_manager.get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    return render_template("auth/profile.html", user=user)


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    """Handle password change requests."""
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=request.url))

    user = current_app.user_manager.get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_password or not new_password or not confirm_password:
            flash("All fields are required", "error")
            return render_template("auth/change_password.html")

        if not user.check_password(current_password):
            flash("Current password is incorrect", "error")
            return render_template("auth/change_password.html")

        if new_password != confirm_password:
            flash("New passwords do not match", "error")
            return render_template("auth/change_password.html")

        # Change password
        current_app.user_manager.change_password(user.username, new_password)
        flash("Password changed successfully", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html")


@auth_bp.route("/admin/users")
def admin_users():
    """Admin page for managing users."""
    if "user_id" not in session or not session.get("is_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("index"))

    users = current_app.user_manager.get_all_users()
    return render_template("auth/admin_users.html", users=users)


@auth_bp.route("/admin/add-user", methods=["GET", "POST"])
def admin_add_user():
    """Admin page for adding a new user."""
    if "user_id" not in session or not session.get("is_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        email = request.form.get("email", "").strip() or None
        is_admin = request.form.get("is_admin") == "on"

        if not username or not password:
            flash("Username and password are required", "error")
            return render_template("auth/add_user.html")

        try:
            current_app.user_manager.add_user(username, password, email, is_admin)
            flash(f"User {username} added successfully", "success")
            return redirect(url_for("auth.admin_users"))
        except ValueError as e:
            flash(str(e), "error")

    return render_template("auth/add_user.html")


@auth_bp.route("/admin/edit-user/<user_id>", methods=["GET", "POST"])
def admin_edit_user(user_id):
    """Admin page for editing a user."""
    if "user_id" not in session or not session.get("is_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("index"))

    user = current_app.user_manager.get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("auth.admin_users"))

    if request.method == "POST":
        email = request.form.get("email", "").strip() or None
        is_admin = request.form.get("is_admin") == "on"

        user.email = email
        user.is_admin = is_admin

        current_app.user_manager.update_user(user)
        flash(f"User {user.username} updated successfully", "success")
        return redirect(url_for("auth.admin_users"))

    return render_template("auth/edit_user.html", user=user)


@auth_bp.route("/admin/delete-user/<user_id>", methods=["POST"])
def admin_delete_user(user_id):
    """Admin route for deleting a user."""
    if "user_id" not in session or not session.get("is_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("index"))

    user = current_app.user_manager.get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("auth.admin_users"))

    if user.user_id == session["user_id"]:
        flash("You cannot delete your own account", "error")
        return redirect(url_for("auth.admin_users"))

    current_app.user_manager.delete_user(user.username)
    flash(f"User {user.username} deleted successfully", "success")
    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/reset-password/<user_id>", methods=["POST"])
def admin_reset_password(user_id):
    """Admin route for resetting a user's password."""
    if "user_id" not in session or not session.get("is_admin"):
        flash("Admin access required", "error")
        return redirect(url_for("index"))

    user = current_app.user_manager.get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("auth.admin_users"))

    new_password = uuid.uuid4().hex[:12]
    current_app.user_manager.change_password(user.username, new_password)

    flash(f"Password for {user.username} reset to: {new_password}", "success")
    return redirect(url_for("auth.admin_users"))


def require_login(f: Callable) -> Callable:
    """Decorator to require login for a route.

    Args:
        f: The function to decorate

    Returns:
        Callable: The decorated function
    """
    logger.debug(f"Applying require_login decorator to {f.__name__}")

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        logger.debug(f"Executing require_login for {f.__name__}")

        if "user_id" not in session:
            logger.debug("No user_id in session, redirecting to login")
            return redirect(url_for("auth.login", next=request.url))

        # Load user into g for easy access in templates
        if hasattr(current_app, "user_manager"):
            user_id = session["user_id"]
            logger.debug(f"Looking up user with id {user_id}")
            g.user = current_app.user_manager.get_user_by_id(user_id)
            if not g.user:
                logger.warning(f"No user found with id {user_id}, clearing session")
                session.clear()
                return redirect(url_for("auth.login", next=request.url))
        else:
            logger.warning("current_app has no user_manager attribute!")

        logger.debug(f"User authenticated, executing route {f.__name__}")
        return f(*args, **kwargs)

    return decorated_function


def require_admin(f: Callable) -> Callable:
    """Decorator to require admin privileges for a route.

    Args:
        f: The function to decorate

    Returns:
        Callable: The decorated function
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session or not session.get("is_admin"):
            flash("Admin access required", "error")
            if "user_id" in session:
                return redirect(url_for("index"))
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def init_auth(app: Any, users_file: Optional[str] = None) -> None:
    """Initialize authentication for the app.

    Args:
        app: The Flask application to initialize auth for
        users_file: Path to the JSON file storing user data
    """
    logger.info("Starting auth initialization")

    if users_file is None:
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        users_file = os.path.join(data_dir, "users.json")
        logger.debug(f"No users file provided, using default: {users_file}")
    else:
        logger.debug(f"Using provided users file: {users_file}")

    # Create user manager
    logger.debug("Creating UserManager")
    app.user_manager = UserManager(users_file)

    # Check if we need to create a default admin user
    logger.debug("Checking for existing users")
    if not app.user_manager.has_users():
        logger.info("No users found, creating default admin")
        # Generate a random password
        admin_password = uuid.uuid4().hex[:12]

        # Get admin username from environment or use default
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")

        # Create admin user
        admin_user = app.user_manager.create_default_admin(admin_username, admin_password)
        logger.info(f"Created default admin user: {admin_user.username} (ID: {admin_user.user_id})")

        # Log the generated admin credentials
        logger.info(f"Default admin password: {admin_password}")

        # Store the admin password in the app for first-time setup
        app.config["DEFAULT_ADMIN_USERNAME"] = admin_username
        app.config["DEFAULT_ADMIN_PASSWORD"] = admin_password
        logger.debug("Admin credentials stored in app config")
    else:
        logger.info(f"Found {len(app.user_manager.users)} existing users")

    # Register the auth blueprint
    logger.debug("Registering auth blueprint")
    app.register_blueprint(auth_bp)

    # Make user available in templates
    logger.debug("Setting up before_request handler")

    @app.before_request
    def load_user():
        if "user_id" in session:
            user_id = session["user_id"]
            logger.debug(f"Loading user {user_id} from session")
            g.user = app.user_manager.get_user_by_id(user_id)
            if g.user:
                logger.debug(f"User loaded: {g.user.username}")
            else:
                logger.warning(f"No user found with ID {user_id}")
        else:
            logger.debug("No user_id in session")
            g.user = None

    # Add template context
    logger.debug("Setting up context processor")

    @app.context_processor
    def inject_user():
        context = {
            "current_user": g.user if hasattr(g, "user") else None,
            "current_year": datetime.now().year,
            "favicon_url": url_for("static", filename="logo.jpg")
            if app.config.get("HAS_LOGO")
            else None,
        }
        if logger.isEnabledFor(logging.DEBUG):
            username = context["current_user"].username if context["current_user"] else None
            logger.debug(f"Injecting context: current_user={username}")
        return context

    logger.info("Auth initialization complete")

    # Log auth system status at debug level
    logger.debug("Auth system status:")
    logger.debug(f"  - Has user_manager: {hasattr(app, 'user_manager')}")
    logger.debug(f"  - Number of users: {len(app.user_manager.users)}")
    logger.debug(f"  - Has admin user: {any(u.is_admin for u in app.user_manager.users.values())}")
    logger.debug(f"  - Auth blueprint registered: {'auth.login' in app.view_functions}")
    logger.debug(f"  - Has before_request handler: {bool(app.before_request_funcs)}")

    # No need for the module-level function here, it's defined in __init__.py
