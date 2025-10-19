#!/bin/bash
# --------------------------------------------
# File: scripts/setup.sh
# Purpose: Setup the Python environment (Mac)
# --------------------------------------------

set -e

# Go to repo root
cd "$(dirname "$0")/.."

echo "--------------------------------------------"
echo " Setting up project environment"
echo "--------------------------------------------"

# Choose a python executable
PY="python3"
if ! command -v $PY >/dev/null 2>&1; then
  echo "python3 not found. Trying 'python'..."
  PY="python"
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  $PY -m venv .venv
else
  echo "Virtual environment already exists."
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Upgrade pip and install requirements
echo "Upgrading pip..."
python -m pip install --upgrade pip

if [ -f "requirements.txt" ]; then
  echo "Installing packages from requirements.txt..."
  pip install -r requirements.txt
else
  echo "No requirements.txt found, skipping install."
fi

# Create standard folders (safe if they already exist)
echo "Creating data/model folders..."
mkdir -p backend/data backend/trained_models
mkdir -p backend/core/betai/registry

# Optional: create a minimal .env if missing (used by run.sh)
if [ ! -f ".env" ]; then
  echo "Creating .env with sensible defaults..."
  cat > .env <<'ENV'
# Runtime configuration
PYTHONPATH=backend/core

# Betting defaults
KELLY_FRACTION=0.25
EV_THRESHOLD=0.02
MAX_STAKE_PCT=0.10
STARTING_BANKROLL=1000.0


# Model store root (local folder for now, later can be an s3:// path)
MODEL_STORE_ROOT=backend/trained_models

# Integrations (fill in your actual API key below)
ODDS_API_KEY=
ODDS_API_URL=https://api.the-odds-api.com/v4
ENV
else
  echo ".env already exists (leaving it as-is)."
fi

echo "--------------------------------------------"
echo " ✅ Setup complete!"
echo " Next:"
echo "   1) ./scripts/run.sh"
echo
echo " Tips (Mac):"
echo "   - If you see compiler errors from SciPy/NumPy, run: xcode-select --install"
echo "   - If python3 is missing: brew install python (Homebrew)"
echo "--------------------------------------------"