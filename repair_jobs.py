#!/usr/bin/env python3
"""
Command-line utility to repair corrupted jobs.json file.

This script is a convenience wrapper around github_activity_tracker.utils.jobs_repair.
"""

import os
import sys

# Add the project root to the Python path to ensure modules can be found
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from github_activity_tracker.utils.jobs_repair import main

if __name__ == "__main__":
    sys.exit(main())
