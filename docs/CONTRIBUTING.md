# Contributing to JustIRC

Thank you for your interest in contributing to JustIRC! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Community](#community)

---

## Code of Conduct

This project follows a Code of Conduct that all contributors are expected to adhere to. Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before contributing.

**Summary:**
- Be respectful and inclusive
- Welcome newcomers
- Assume good intent
- No harassment or discrimination
- Keep discussions constructive

---

## Getting Started

### Prerequisites

- **Python**: 3.9 - 3.13
- **Git**: For version control
- **Basic knowledge of**:
  - Python asyncio
  - Cryptography concepts
  - IRC protocol basics

### First Contributions

Good first issues are labeled with `good first issue`. These are great starting points for new contributors:
- Documentation improvements
- Test coverage expansion
- Bug fixes
- Code quality improvements

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/justIRC.git
cd justIRC
```

### 2. Create Virtual Environment

```bash
# Linux/Mac
python3 -m venv build-env
source build-env/bin/activate

# Windows
python -m venv build-env
build-env\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install runtime dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 mypy pylint pytest pytest-asyncio pytest-cov pre-commit
```

### 4. Set Up Pre-commit Hooks

```bash
pre-commit install
```

This will automatically run code quality checks before each commit.

### 5. Verify Setup

```bash
# Run tests to verify everything works
python run_tests.py

# Should see: "144 tests passed"
```

### 6. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

---

## How to Contribute

### Types of Contributions

We welcome many types of contributions:

**📝 Documentation**
- Fix typos or improve clarity
- Add examples and tutorials
- Translate documentation
- Write blog posts or guides

**🐛 Bug Reports**
- Report bugs with clear reproduction steps
- Include system information
- Provide logs and error messages

**✨ Feature Requests**
- Suggest new features
- Discuss improvements
- Provide use cases

**💻 Code Contributions**
- Fix bugs
- Implement new features
- Improve performance
- Refactor code

**🧪 Testing**
- Add test coverage
- Improve test quality
- Test new features

**🎨 Design**
- UI/UX improvements for GUI client
- Logo and branding
- Documentation formatting

---

## Coding Standards

### Style Guidelines

JustIRC follows **PEP 8** with these specifications:

**Line Length:**
- Maximum 100 characters
- Break long lines logically

**Naming Conventions:**
```python
# Classes: PascalCase
class MessageRouter:
    pass

# Functions and methods: snake_case
def handle_message():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_MESSAGE_SIZE = 65536

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

**Type Hints:**
All public functions should have type hints:
```python
def encrypt(self, peer_id: str, plaintext: str) -> Tuple[str, str]:
    """Encrypt data for a specific peer"""
    ...
```

**Docstrings:**
Use Google-style docstrings:
```python
def create_account(self, username: str, password: str, 
                  email: Optional[str] = None) -> bool:
    """
    Create a new user account.
    
    Args:
        username: Unique username (3-50 characters)
        password: Password (8-256 characters)
        email: Optional email address
        
    Returns:
        True if account created successfully, False otherwise
        
    Raises:
        ValueError: If username or password invalid
    """
```

### Code Formatting

**Automatic Formatting:**
```bash
# Format all Python files
black .

# Check formatting without changes
black --check .
```

**Linting:**
```bash
# Run flake8
flake8 .

# Run pylint
pylint *.py
```

**Type Checking:**
```bash
# Run mypy
mypy *.py
```

**Run All Checks:**
```bash
./quality_check.sh
```

### Import Organization

```python
# Standard library imports
import asyncio
import json
from typing import Dict, List, Optional

# Third-party imports
from cryptography.hazmat.primitives import hashes

# Local imports
from protocol import Protocol
from crypto_layer import CryptoLayer
```

---

## Testing Guidelines

### Writing Tests

**Test Structure:**
```python
import unittest

class TestFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.instance = FeatureClass()
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_basic_functionality(self):
        """Test basic feature works"""
        # Arrange
        input_data = "test"
        
        # Act
        result = self.instance.process(input_data)
        
        # Assert
        self.assertEqual(result, expected_output)
```

**Test Requirements:**
- Each public method should have at least one test
- Test both success and failure cases
- Test edge cases and boundary conditions
- Use descriptive test names
- Include docstrings explaining what is tested

**Async Tests:**
```python
import asyncio

def test_async_feature(self):
    """Test async functionality"""
    async def run_test():
        result = await async_function()
        self.assertEqual(result, expected)
    
    asyncio.run(run_test())
```

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run specific test file
python -m unittest tests.test_crypto_layer

# Run specific test
python -m unittest tests.test_crypto_layer.TestCryptoLayer.test_encryption

# Run with coverage
pytest --cov=. --cov-report=html
# View coverage report: open htmlcov/index.html
```

### Test Coverage

- Aim for **80%+ coverage** for new code
- Critical modules should have **90%+ coverage**:
  - crypto_layer.py
  - protocol.py
  - auth_manager.py
  - server.py

---

## Pull Request Process

### Before Submitting

1. **Run all tests:**
   ```bash
   python run_tests.py
   ```

2. **Run quality checks:**
   ```bash
   ./quality_check.sh
   ```

3. **Update documentation:**
   - Update relevant docs in `docs/`
   - Update docstrings
   - Update README if needed

4. **Write clear commit messages:**
   ```
   Fix: Correct key rotation timing issue (#123)
   
   - Fixed bug where keys rotated too early
   - Added test for rotation timing
   - Updated documentation
   
   Fixes #123
   ```

### Commit Message Format

```
<type>: <subject> (<issue-number>)

<body>

<footer>
```

**Types:**
- `Fix`: Bug fix
- `Feature`: New feature
- `Docs`: Documentation changes
- `Test`: Test additions or changes
- `Refactor`: Code refactoring
- `Style`: Formatting changes
- `Perf`: Performance improvements

**Examples:**
```
Feature: Add key rotation statistics (#45)

Added methods to track key rotation stats including:
- Time since last rotation
- Message count
- Rotation reason

Closes #45
```

```
Fix: Prevent race condition in channel join (#78)

Added lock to prevent multiple clients from creating
the same channel simultaneously.

Fixes #78
```

### Pull Request Template

When creating a PR, include:

**Description:**
- What does this PR do?
- Why is this change needed?
- What issue does it fix?

**Changes:**
- List of files changed
- New features added
- Bug fixes

**Testing:**
- What tests were added?
- How was this tested?

**Documentation:**
- What docs were updated?

**Checklist:**
- [ ] Tests pass
- [ ] Code formatted with black
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Changelog updated (if applicable)
- [ ] Follows coding standards

### Review Process

1. **Automated checks run:** Tests, linting, formatting
2. **Code review:** Maintainers review code
3. **Changes requested:** Address feedback
4. **Approval:** PR approved by maintainer
5. **Merge:** PR merged into main branch

**Review Timeline:**
- Initial review: Within 3-5 days
- Follow-up: Within 2-3 days
- Please be patient with reviewers

---

## Issue Guidelines

### Reporting Bugs

Use the bug report template and include:

**Required Information:**
- Python version
- Operating system
- JustIRC version
- Steps to reproduce
- Expected behavior
- Actual behavior
- Error messages and logs

**Example:**
```
**Python Version:** 3.10.5
**OS:** Ubuntu 22.04
**JustIRC Version:** 1.0.1

**Steps to Reproduce:**
1. Start server with default config
2. Connect two clients
3. Send message from alice to bob
4. Observe error

**Expected:** Message decrypts successfully
**Actual:** DecryptionError raised

**Error Log:**
```
Traceback (most recent call last):
  ...
```
```

### Feature Requests

Use the feature request template and include:

- **Problem:** What problem does this solve?
- **Proposed Solution:** How should it work?
- **Alternatives:** Other solutions considered
- **Use Cases:** When would this be used?

### Security Issues

**DO NOT** open public issues for security vulnerabilities!

Instead:
1. Email security contact (see SECURITY.md)
2. Include detailed description
3. Wait for private response
4. Coordinate disclosure timing

---

## Community

### Communication Channels

- **GitHub Issues:** Bug reports and feature requests
- **GitHub Discussions:** Questions, ideas, and community
- **Pull Requests:** Code contributions

### Getting Help

**Questions about:**
- **Using JustIRC:** Check docs/, README.md, or open a discussion
- **Contributing:** Read this guide or ask in discussions
- **Bug reports:** Open an issue with bug report template
- **Feature ideas:** Open an issue with feature request template

### Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes for significant contributions
- Special thanks in README for major features

---

## Development Workflow

### Typical Workflow

1. **Pick an issue** or identify a need
2. **Discuss approach** in issue comments (for large changes)
3. **Create branch** with descriptive name
4. **Write code** following standards
5. **Write tests** for new code
6. **Update documentation** as needed
7. **Run quality checks** and fix issues
8. **Commit changes** with clear messages
9. **Push to fork** and create pull request
10. **Address feedback** during review
11. **Merge** when approved

### Branch Naming

- `feature/description` - New features
- `fix/issue-number-description` - Bug fixes
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `test/description` - Test additions

### Release Process

**For Maintainers:**

1. Update version in relevant files
2. Update RELEASE_NOTES.md
3. Create git tag: `v1.x.x`
4. Build packages
5. Create GitHub release
6. Announce release

---

## License

By contributing to JustIRC, you agree that your contributions will be licensed under the same license as the project (see LICENSE file).

---

## Questions?

- **General questions:** Open a discussion on GitHub
- **Specific issues:** Comment on the relevant issue
- **Security concerns:** Email security contact (see SECURITY.md)

Thank you for contributing to JustIRC! 🎉
