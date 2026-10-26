#!/bin/bash

# Setup script for IL-RXTOR-SEP-OPT dependencies
# Installs the locked Python/Conda/PyPI environment via pixi and instantiates Julia packages

set -euo pipefail

echo "Setting up dependencies for IL-RXTOR-SEP-OPT project..."
echo "=================================================="

if ! command -v pixi &> /dev/null; then
    echo "Error: pixi not found. Install pixi from https://pixi.sh/ before running this script."
    exit 1
fi

echo "Installing locked Python and Julia toolchain via pixi..."
pixi install
pixi run verify-python
echo "✓ Pixi environment installed and verified"

echo ""
echo "Setting up Julia dependencies (Julia 1.11.5)..."
echo "-----------------------------------------------"
if command -v julia &> /dev/null; then
    julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.status()'
    echo "✓ Julia dependencies instantiated from Project.toml and Manifest.toml"
else
    pixi run setup-julia
    echo "✓ Julia 1.11.5 and project dependencies installed via juliaup"
fi

echo ""
echo "Setup complete!"
echo "=============="
echo "Run commands inside the locked environment with:"
echo "  pixi run python <script.py>"
echo "  pixi run jupyter lab"
echo "  julia --project=. <script.jl>"
