#!/bin/bash
# Quality Check Script for JustIRC
# Runs all code quality tools

set -e

echo "================================"
echo "JustIRC Code Quality Check"
echo "================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track if any check failed
FAILED=0

# Python files to check
PYTHON_FILES="*.py tests/*.py"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "Checking Python code quality tools..."
echo ""

# Check Black
echo "1. Running Black (code formatter)..."
if command_exists black; then
    if black --check --diff $PYTHON_FILES; then
        echo -e "${GREEN}✓ Black: Code formatting is correct${NC}"
    else
        echo -e "${YELLOW}⚠ Black: Code needs formatting. Run 'black *.py tests/*.py' to fix${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Black not installed. Install with: pip install black${NC}"
fi
echo ""

# Check Flake8
echo "2. Running Flake8 (linter)..."
if command_exists flake8; then
    if flake8 $PYTHON_FILES; then
        echo -e "${GREEN}✓ Flake8: No linting errors${NC}"
    else
        echo -e "${RED}✗ Flake8: Linting errors found${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Flake8 not installed. Install with: pip install flake8${NC}"
fi
echo ""

# Check MyPy
echo "3. Running MyPy (type checker)..."
if command_exists mypy; then
    if mypy $PYTHON_FILES --config-file=pyproject.toml; then
        echo -e "${GREEN}✓ MyPy: No type errors${NC}"
    else
        echo -e "${YELLOW}⚠ MyPy: Type checking issues found${NC}"
        # Don't fail on mypy errors yet
    fi
else
    echo -e "${YELLOW}⚠ MyPy not installed. Install with: pip install mypy${NC}"
fi
echo ""

# Run tests
echo "4. Running test suite..."
if python3 tests/run_tests.py; then
    echo -e "${GREEN}✓ Tests: All tests passed${NC}"
else
    echo -e "${RED}✗ Tests: Some tests failed${NC}"
    FAILED=1
fi
echo ""

echo "================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some quality checks failed${NC}"
    exit 1
fi
