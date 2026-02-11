#!/bin/bash
# Build script for Linux (.deb package)

set -e

echo "========================================"
echo "JustIRC Linux Package Builder"
echo "========================================"
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Error: This script must be run on Linux"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $PYTHON_VERSION"

# Check if required packages are installed
echo ""
echo "Checking dependencies..."

# Install build dependencies if needed
if ! dpkg -l | grep -q python3-stdeb; then
    echo "Installing python3-stdeb..."
    sudo apt-get update
    sudo apt-get install -y python3-stdeb dh-python
fi

if ! dpkg -l | grep -q python3-tk; then
    echo "Installing python3-tk..."
    sudo apt-get install -y python3-tk
fi

echo "✓ Build dependencies installed"

# Create virtual environment for building
echo ""
echo "Setting up build environment..."
python3 -m venv build-env
source build-env/bin/activate

# Install Python dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install stdeb

echo "✓ Build environment ready"

# Clean previous builds
echo ""
echo "Cleaning previous builds..."
rm -rf deb_dist/ dist/ *.egg-info/ build/
echo "✓ Cleaned"

# Build .deb package
echo ""
echo "Building .deb package..."
python3 setup.py --command-packages=stdeb.command bdist_deb

# Find the generated .deb file
DEB_FILE=$(find deb_dist -name "*.deb" | head -n 1)

if [ -f "$DEB_FILE" ]; then
    echo ""
    echo "========================================"
    echo "✓ SUCCESS! Package built:"
    echo "  $DEB_FILE"
    echo "========================================"
    echo ""
    echo "To install:"
    echo "  sudo dpkg -i $DEB_FILE"
    echo "  sudo apt-get install -f  # Fix any dependency issues"
    echo ""
    echo "To run after installation:"
    echo "  justirc-gui    # GUI client"
    echo "  justirc-cli    # CLI client"
    echo "  justirc-server # Server"
    echo ""
else
    echo ""
    echo "Error: .deb package not found"
    exit 1
fi

# Deactivate virtual environment
deactivate
