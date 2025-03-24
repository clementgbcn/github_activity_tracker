# GitHub Activity Tracker

[![Tests](https://github.com/your-username/github-activity-tracker/actions/workflows/tests.yml/badge.svg)](https://github.com/your-username/github-activity-tracker/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/your-username/github-activity-tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/github-activity-tracker)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python application to track GitHub activities (PRs, comments, reviews, approvals) for a list of users within a specified time period.

## Features

- Track multiple GitHub users' activities
- Filter by date range and organization
- Load users from a file (default or custom location)
- Generate comprehensive reports in CSV and HTML formats
- Interactive HTML reports with filtering and sorting
- Clickable visualizations for better data exploration
- Visualize activity trends, distribution, and user comparisons
- Provide detailed insights about user contributions
- Email reports to specified recipients
- Advanced logging and GitHub API rate limit monitoring
- Web UI for easy job management and report viewing
- Secure user authentication with bcrypt password hashing
- User management with admin and regular user roles
- Command-line tools for user management and password migration

## Prerequisites

- Python 3.7+
- GitHub Personal Access Token with appropriate permissions

## Installation

### Option 1: Install from source

1. Clone this repository
2. Install in development mode:

```bash
pip install -e .
```

### Option 2: Install dependencies only

1. Clone this repository
2. Install required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example` and add your GitHub Personal Access Token and optional settings:

```
# Required token
GITHUB_TOKEN=your_github_personal_access_token_here

# Optional organization to filter by
GITHUB_ORG=optional_github_organization_name

# Optional comma-separated list of users to track
GITHUB_USERS=user1,user2,user3

# Optional JIRA URL prefix for linking tickets (e.g., SEC-1234) found in PR titles
JIRA_URL_PREFIX=https://your-jira-instance.atlassian.net/browse/

# Email configuration (optional)
EMAIL_ENABLED=true
EMAIL_SENDER=your_email@example.com
EMAIL_PASSWORD=your_email_password_or_app_password
EMAIL_SMTP_SERVER=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
EMAIL_SUBJECT_PREFIX=[GitHub Activity]
```

4. You can specify users in one of three ways (in order of precedence):

   a. Via command-line arguments: `--users user1 user2`

   b. Via the GITHUB_USERS environment variable in `.env`:
   ```
   GITHUB_USERS=user1,user2,user3
   ```

   c. Via a text file (default is `github_users.txt` in the root directory):
   ```
   octocat
   torvalds
   gvanrossum
   defunkt
   ```

## Project Structure

The project is now organized into modules:

```
github_activity_tracker/
├── api/                    # GitHub API interaction
├── report/                 # Report generation and visualization
├── templates/              # HTML templates for reports
├── utils/                  # Utility functions and logging
├── __init__.py             # Package initialization
└── cli.py                  # Command-line interface
```

## Usage

You can run the application in two ways: via the command line or using the web UI.

### Command Line Interface

Run the application with one of the following methods:

#### If installed via pip:

```bash
github-activity-tracker --start-date 2023-01-01 [options]
```

#### Using the main.py script:

```bash
python main.py --start-date 2023-01-01 [options]
```

#### Using the module directly:

```bash
python -m github_activity_tracker.cli --start-date 2023-01-01 [options]
```

### Web User Interface

The application includes a web-based UI that allows you to:
- Fill parameters through a user-friendly form
- See real-time job progress
- View and download generated reports
- Manage multiple tracking jobs

To start the web UI:

```bash
python run_web_ui.py
```

Then open your browser and navigate to: http://127.0.0.1:5000

You can customize the host and port using environment variables:
```
HOST=0.0.0.0
PORT=8080
FLASK_DEBUG=true  # Enable Flask debug mode
```

### Running with DataDog Monitoring

To run the application with DataDog monitoring enabled:

```bash
bash run_with_datadog.sh
```

This script:
- Enables DataDog tracing, profiling, and log injection
- Configures the log file path with appropriate permissions
- Sets DataDog environment variables

For DataDog agent to collect logs properly:

1. Make sure DataDog agent is installed and running
2. Enable log collection in `/etc/datadog-agent/datadog.yaml`:
   ```yaml
   logs_enabled: true
   ```
3. Create a custom configuration file:
   ```bash
   sudo mkdir -p /etc/datadog-agent/conf.d/github_activity_tracker.d/
   sudo cp datadog_agent_config.yaml /etc/datadog-agent/conf.d/github_activity_tracker.d/conf.yaml
   ```
4. Restart the DataDog agent:
   ```bash
   sudo systemctl restart datadog-agent  # Linux
   # or
   sudo launchctl stop com.datadoghq.agent  # macOS
   sudo launchctl start com.datadoghq.agent
   ```

## Command-line Options

### Basic Options:

- `--users`: List of GitHub usernames to track (space-separated, overrides GITHUB_USERS in .env)
- `--users-file`: Path to a file containing GitHub usernames (one per line)
- `--start-date`: Start date in YYYY-MM-DD format (required)
- `--end-date`: End date in YYYY-MM-DD format (defaults to today)
- `--output`: Output format (`csv`, `html`, or `dataframe`, defaults to `html`)
- `--email`: Send the report via email to recipients defined in the .env file

### Organization Options:

- `--org`: Filter results to a specific GitHub organization (overrides GITHUB_ORG in .env)
- `--no-org-filter`: Disable organization filtering (show activities across all organizations)

### Advanced Options:

- `--debug`: Enable debug logging for detailed GitHub API operations
- `--no-rate-monitor`: Disable background monitoring of GitHub API rate limits
- `--rate-check-interval`: Seconds between GitHub API rate limit checks (default: 15)
- `--max-workers`: Maximum number of parallel workers for processing users (0 means auto-detect)

## Examples

### Generate an HTML report for specific users:

```bash
python main.py --users octocat torvalds --start-date 2023-01-01 --output html
```

### Generate a CSV report for users in a file with debugging enabled:

```bash
python main.py --users-file custom_users.txt --start-date 2023-01-01 --output csv --debug
```

### Track activities for users in a custom organization:

```bash
python main.py --start-date 2023-01-01 --org microsoft
```

This overrides any organization set in the .env file.

### Track activities across all organizations:

```bash
python main.py --start-date 2023-01-01 --no-org-filter
```

### Generate a report and send it via email:

```bash
python main.py --start-date 2023-01-01 --output html --email
```

This sends the HTML report to recipients defined in the EMAIL_RECIPIENTS environment variable.

#### Gmail Configuration Example

To use Gmail as your email provider, add these settings to your `.env` file:

```
EMAIL_ENABLED=true
EMAIL_SENDER=your.email@gmail.com
EMAIL_PASSWORD=your_app_password  # Create an App Password in your Google Account
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
```

Note: For Gmail with 2-factor authentication enabled, you'll need to create an [App Password](https://myaccount.google.com/apppasswords) instead of using your regular password.

## Generated Reports & Visualizations

The application generates:

1. An HTML report with:
   - Interactive filtering and sorting
   - Clickable visualizations
   - Summary statistics
   - Detailed activity table

2. OR a CSV report with detailed activity information

3. Three visualization charts:
   - Activity trends over time
   - Distribution of activity types
   - Activity comparison between users

## Limitations

- The GitHub API has rate limits that may affect the retrieval of large amounts of data
- Some activity types may not be visible depending on repository permissions
- Historical data beyond 90 days may be limited for certain activity types

## Development

### Running Tests

Tests are written using pytest and can be run with:

```bash
pytest
```

This will automatically run all tests in the `tests/` directory.

### Code Coverage

The project uses pytest-cov to generate test coverage reports. Running the tests will automatically generate coverage reports in multiple formats:

```bash
# Terminal, HTML, and XML reports are generated by default
pytest
```

To view the HTML coverage report:

1. After running the tests, open the `htmlcov/index.html` file in your browser
2. This interactive report shows coverage for each module
3. You can click on individual files to see which lines are covered and which are missed
4. Green lines are covered by tests, red lines are not covered

The HTML report provides a visual representation of code coverage that helps identify areas needing additional testing.

### Continuous Integration

This project uses GitHub Actions for continuous integration:

- Tests run automatically on push to main branch and on pull requests
- Tests run against multiple Python versions (3.7-3.11)
- Code coverage reports are uploaded to Codecov
- Ruff linting is enforced

The workflow configuration is in `.github/workflows/tests.yml`.

### Pre-commit Hooks

Pre-commit hooks are configured to run automatically before each commit:

```bash
# Install the pre-commit hooks
pre-commit install
```

This ensures code quality is maintained by running linters and formatters automatically.

### Linting and Formatting

The project uses Ruff for linting and formatting:

```bash
# Check code for issues
ruff check .

# Format code automatically
ruff format .
```

Ruff configuration is in `pyproject.toml` under the `[tool.ruff]` section.

### Type Hints

The project uses Python type hints throughout the codebase to improve code quality and IDE support. Type checking can be performed using mypy:

```bash
# Install mypy
pip install mypy

# Run type checking
mypy github_activity_tracker
```

Type hints make the code more maintainable and help catch type-related bugs early.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The MIT License is a permissive license that is short and to the point. It lets people do anything they want with your code as long as they provide attribution back to you and don't hold you liable.

### Key points of the MIT License:
- Commercial use is allowed
- Modification is allowed
- Distribution is allowed
- Private use is allowed
- License and copyright notice must be included with the software
- No warranty is provided
- The authors are not liable for any claim, damages, or other liability

## User Management

The application includes a secure user management system with the following features:

- Secure password hashing using bcrypt
- Role-based access control (admin and regular users)
- Password migration from plaintext to secure hashes
- User management via command line or web interface

### Password Migration

When you first run the application after upgrading, it will automatically migrate
any plaintext passwords to secure bcrypt hashes. You can also manually migrate passwords
using the provided script:

```bash
# Migrate passwords in the default users.json file
python migrate_passwords.py

# Or specify a custom path
python migrate_passwords.py path/to/users.json
```

### Command-line User Management

A command-line tool is provided for managing users:

```bash
# List all users
python manage_users.py list

# Add a new user (interactive)
python manage_users.py add

# Add a new admin user with a random password
python manage_users.py add --username john --email john@example.com --admin --random-password

# Reset a user's password
python manage_users.py reset-password --username john

# Delete a user (requires confirmation)
python manage_users.py delete --username john

# Force delete a user without confirmation
python manage_users.py delete --username john --force
```

### Web-based User Management

Administrators can manage users through the web interface:
- Navigate to "User Management" in the menu
- Add, edit, or delete users
- Reset passwords
- Manage user roles

For security, all passwords are stored using bcrypt hashing, and plaintext passwords
are never stored in the database.
