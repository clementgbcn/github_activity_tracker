"""Shared fixtures for tests."""

import os
import tempfile

import pytest


@pytest.fixture
def mock_env_variables():
    """Mock environment variables for testing."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ["GITHUB_TOKEN"] = "test_token"
    os.environ["GITHUB_ORG"] = "test-org"
    os.environ["GITHUB_USERS"] = "user1,user2,user3"

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_users_file():
    """Create a temporary users file for testing."""
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp:
        temp.write("user1\nuser2\nuser3\n")
        temp_name = temp.name

    yield temp_name

    # Clean up
    if os.path.exists(temp_name):
        os.unlink(temp_name)
