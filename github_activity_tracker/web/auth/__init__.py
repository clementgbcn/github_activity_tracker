"""Authentication module for the GitHub Activity Tracker web UI."""

from .auth import User, UserManager, init_auth, require_admin, require_login
from .user_manager import authenticate_user as user_manager_authenticate
from .user_manager import change_password, create_user, generate_random_password, list_users
from .user_manager import get_user_by_id as user_manager_get_user


# Add aliases for compatibility with app.py
def authenticate_user(username, password):
    """Alias for authenticate() for compatibility."""
    from flask import current_app

    if hasattr(current_app, "user_manager"):
        return current_app.user_manager.authenticate(username, password)

    # Try the user_manager module as fallback
    try:
        return user_manager_authenticate(username, password)
    except Exception as _:
        pass

    return None


def get_user_by_id(user_id):
    """Alias for get_user_by_id() for compatibility."""
    from flask import current_app

    if hasattr(current_app, "user_manager"):
        return current_app.user_manager.get_user_by_id(user_id)

    # Try the user_manager module as fallback
    try:
        return user_manager_get_user(user_id)
    except Exception as _:
        pass

    # Fallback for demo mode
    if user_id == "demo":
        return type("User", (), {"user_id": "demo", "username": "demo_user", "is_admin": True})()
    elif user_id == "admin":
        return type("User", (), {"user_id": "admin", "username": "admin", "is_admin": True})()
    return None
