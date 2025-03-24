# Contributing to GitHub Activity Tracker

Thank you for your interest in contributing to GitHub Activity Tracker! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue with:

1. A clear, descriptive title
2. A detailed description of the bug
3. Steps to reproduce the issue
4. Expected and actual results
5. Any relevant logs, screenshots, or other information

### Suggesting Enhancements

For feature suggestions, please create an issue with:

1. A clear, descriptive title
2. A detailed description of the proposed feature
3. Any relevant examples, mockups, or diagrams
4. The rationale behind the suggestion

### Pull Requests

1. Fork the repository
2. Create a new branch from `main`
3. Make your changes
4. Add or update tests as appropriate
5. Ensure all tests pass
6. Submit a pull request to the `main` branch

#### Pull Request Process

1. Update the README.md and documentation as needed
2. Follow the existing code style and conventions
3. Include appropriate tests for your changes
4. Link the pull request to any related issues
5. The maintainers will review your PR and may request changes
6. Once approved, your PR will be merged

## Development Environment Setup

1. Clone the repository
2. Install development dependencies:
   ```
   pip install -e ".[dev]"
   ```
3. Install pre-commit hooks:
   ```
   pre-commit install
   ```

## Testing

- Write unit tests for new functionality
- Run tests with pytest:
  ```
  pytest
  ```
- Ensure coverage is maintained or improved

## Coding Standards

- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Include docstrings for all modules, classes, and functions
- Use descriptive variable and function names
- Keep functions small and focused on a single responsibility

## License

By contributing to GitHub Activity Tracker, you agree that your contributions will be licensed under the project's MIT License.

Thank you for your contributions!
