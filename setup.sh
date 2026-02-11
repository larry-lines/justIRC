#!/bin/bash
# Setup script for JustIRC

echo "==================================="
echo "JustIRC - Secure IRC Setup"
echo "==================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "To start using JustIRC:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Start the server:"
echo "   python server.py"
echo ""
echo "3. Start a client (in another terminal):"
echo "   python client.py --nickname YourName"
echo "   OR"
echo "   python client_gui.py"
echo ""
echo "For more information, see README.md"
echo ""
