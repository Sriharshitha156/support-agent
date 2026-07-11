#!/usr/bin/env bash
# Customer Support Resolution Agent — Unix/macOS setup script
# Usage: chmod +x setup.sh && ./setup.sh

set -euo pipefail

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating virtual environment..."
# shellcheck source=/dev/null
source venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

echo ""
echo "Setup complete."
echo "Next steps:"
echo "  1. Copy .env.example to .env and add your API keys"
echo "  2. Activate: source venv/bin/activate"
echo "  3. Run API:  uvicorn app:app --reload"
echo "  4. Run UI:   streamlit run ui.py"
