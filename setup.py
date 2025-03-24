from setuptools import find_packages, setup

setup(
    name="github-activity-tracker",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "github_activity_tracker": ["templates/*.html"],
    },
    install_requires=[
        "pygithub",
        "pandas",
        "matplotlib",
        "python-dotenv",
        "jinja2",
    ],
    entry_points={
        "console_scripts": [
            "github-activity-tracker=github_activity_tracker.cli:main",
        ],
    },
    author="Clement Gaboriau Couanau",
    author_email="N/A",
    description="Track and visualize GitHub user activities",
    keywords="github, tracking, visualization, activity",
    python_requires=">=3.7",
)
