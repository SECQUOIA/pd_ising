#!/bin/bash

# Setup script for IL-RXTOR-SEP-OPT dependencies
# This script installs both Julia and Python dependencies

set -e  # Exit on any error

echo "Setting up dependencies for IL-RXTOR-SEP-OPT project..."
echo "=================================================="

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Found Python version: $PYTHON_VERSION"

# Check if Julia is available
if ! command -v julia &> /dev/null; then
    echo "Warning: Julia not found. Please install Julia 1.11.5 or higher."
    echo "You can download it from: https://julialang.org/downloads/"
    echo "Continuing with Python setup only..."
    JULIA_AVAILABLE=false
else
    JULIA_VERSION=$(julia --version | grep -o 'Julia [0-9.]*' | cut -d' ' -f2)
    echo "Found Julia version: $JULIA_VERSION"
    JULIA_AVAILABLE=true
fi

echo ""
echo "Setting up Python dependencies..."
echo "--------------------------------"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✓ Python dependencies installed from requirements.txt"
else
    echo "Warning: requirements.txt not found"
fi

# Install from pyproject.toml if available
if [ -f "pyproject.toml" ]; then
    echo "Installing from pyproject.toml..."
    pip install -e .
    echo "✓ Python dependencies installed from pyproject.toml"
fi

echo ""
echo "Setting up Julia dependencies..."
echo "-------------------------------"

if [ "$JULIA_AVAILABLE" = true ]; then
    # Install Julia dependencies
    echo "Installing Julia dependencies..."
    julia --project=. -e 'using Pkg; Pkg.instantiate()'
    echo "✓ Julia dependencies installed"
else
    echo "Skipping Julia setup (Julia not available)"
fi

echo ""
echo "Setup complete!"
echo "=============="
echo ""
echo "To activate the Python environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To install additional Python packages:"
echo "  pip install package_name"
echo ""
echo "To update Julia packages:"
echo "  julia --project=. -e 'using Pkg; Pkg.update()'"
echo ""
echo "For more information, see DEPENDENCIES.md" 