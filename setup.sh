#!/usr/bin/env bash
set -e

echo "=== Job Search Agent Setup ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium browser..."
playwright install chromium

echo ""
echo "NOTE: If Playwright fails to launch, install system deps with:"
echo "  sudo playwright install --with-deps chromium"
echo ""

PROFILE_DIR="$HOME/.linkedin_agent_profile"
mkdir -p "$PROFILE_DIR"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Activate venv:  source venv/bin/activate"
echo "  2. Login once:     python scripts/interactive_login.py"
echo "  3. Launch UI:      python ui/app.py"
echo ""
