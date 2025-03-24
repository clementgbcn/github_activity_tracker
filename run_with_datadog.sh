#!/bin/bash
# Run the GitHub Activity Tracker with DataDog tracing enabled

export DATADOG_ENABLED=true

export DEBUG=false
export FLASK_DEBUG=false

# Configure log file path
export LOG_FILE_PATH="/tmp/github-activity-tracker.json"

# Configure DataDog environment variables
export DD_SERVICE="github-activity-tracker"
export DD_ENV="development"
export DD_VERSION="1.0.0"
export DD_LOGS_INJECTION=true
export DD_TRACE_SAMPLE_RATE=1
export DD_PROFILING_ENABLED=true

# Log DataDog agent information for debugging
echo "Starting application with DataDog tracing enabled"
echo "Logs will be written to console and $LOG_FILE_PATH"

# Run with ddtrace-run
exec ddtrace-run python run_web_ui.py "$@"
