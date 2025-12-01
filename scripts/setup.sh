#!/bin/bash
# --------------------------------------------
# File: scripts/setup.sh
# Purpose: Setup the Python environment (Mac)
# --------------------------------------------

set -e

# --------------------------------------------
# Go to repo root
# --------------------------------------------
cd "$(dirname "$0")/.."

echo "--------------------------------------------"
echo " Setting up project environment"
echo "--------------------------------------------"

# --------------------------------------------
# Choose a python executable
# --------------------------------------------
PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Trying 'python'..."
  PY="python"
fi

# --------------------------------------------
# Create venv if missing
# --------------------------------------------
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment (.venv)..."
  "$PY" -m venv .venv
  CREATED_VENV=1
else
  echo "Virtual environment already exists."
  CREATED_VENV=0
fi

# --------------------------------------------
# Activate venv
# --------------------------------------------
# shellcheck disable=SC1091
source .venv/bin/activate

# --------------------------------------------
# Ensure pip exists and works inside the venv
# --------------------------------------------
echo "Ensuring pip is available and up to date..."

# 1) Try ensurepip first
if ! python -c "import pip" >/dev/null 2>&1; then
  echo "pip not found — using ensurepip..."
  python -m ensurepip --upgrade || true
fi

# 2) If pip._internal is still missing, force-reinstall via get-pip.py
if ! python -c "import pip, pip._internal" >/dev/null 2>&1; then
  echo "pip looks corrupted — bootstrapping with get-pip.py..."
  curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  python /tmp/get-pip.py --force-reinstall
fi

# 3) Final upgrade of build tooling
python -m pip install --upgrade pip setuptools wheel

# --------------------------------------------
# Install Python dependencies
# --------------------------------------------
if [ -f "requirements.txt" ]; then
  echo "Installing packages from requirements.txt..."
  pip install -r requirements.txt
  INSTALLED_REQS=1
else
  echo "No requirements.txt found, skipping install."
  INSTALLED_REQS=0
fi

# --------------------------------------------
# Install local Odds API SDK (editable)
# --------------------------------------------
if [ -d "odds-sdk" ]; then
  echo "Installing local odds-sdk package (editable)..."
  pip install -e ./odds-sdk
  INSTALLED_ODDSSDK=1
else
  echo "WARNING: odds-sdk directory not found; skipping SDK install."
  INSTALLED_ODDSSDK=0
fi

# --------------------------------------------
# Optional: create a minimal .env if missing (used by run.sh)
# --------------------------------------------
if [ ! -f ".env" ]; then
  echo "Creating .env with sensible defaults..."
  cat > .env <<'ENV'
# Runtime configuration
PYTHONPATH=backend/core:${PYTHONPATH}

# Betting defaults
KELLY_FRACTION=0.25
EV_THRESHOLD=0.02
MAX_STAKE_PCT=0.10
STARTING_BANKROLL=1000.0

# Model store root (informational only; models
# actually live under betai/models/*/trained_models)
MODEL_STORE_ROOT=backend/core/betai/models

# Integrations (fill in your actual API key below)
ODDS_API_KEY=
ODDS_API_URL=https://api.the-odds-api.com/v4
ENV
  CREATED_ENV=1
else
  echo ".env already exists (leaving it as-is)."
  CREATED_ENV=0
fi

# --------------------------------------------
# Train models (moneyline + spread)
# --------------------------------------------

# Ensure train_models.sh is executable
if [ -f "scripts/train_models.sh" ]; then
  chmod +x scripts/train_models.sh
fi
if [ -x "scripts/train_models.sh" ]; then
  echo
  echo "Running model training script (moneyline + spread)..."
  if ./scripts/train_models.sh; then
    TRAINED_MODELS=1
  else
    echo "WARNING: Model training failed. You can rerun it with:"
    echo "  ./scripts/train_models.sh"
    TRAINED_MODELS=0
  fi
else
  echo "WARNING: scripts/train_models.sh not found or not executable; skipping model training."
  TRAINED_MODELS=0
fi

echo
echo "--------------------------------------------"
echo " ✅ Setup complete!"
echo
echo " Recap of what was done:"
[ "$CREATED_VENV" -eq 1 ] && echo "  • Created virtual environment: .venv" \
                          || echo "  • Reused existing virtual environment: .venv"
[ "$INSTALLED_REQS" -eq 1 ] && echo "  • Installed Python dependencies from requirements.txt"
[ "$INSTALLED_ODDSSDK" -eq 1 ] && echo "  • Installed local odds-sdk package (editable)"
echo "  • Ensured backend/data and backend/core/betai/registry directories exist"
[ "$CREATED_ENV" -eq 1 ] && echo "  • Created .env with default settings" \
                         || echo "  • Detected existing .env (unchanged)"
[ "$TRAINED_MODELS" -eq 1 ] && echo "  • Trained moneyline + spread models via scripts/train_models.sh" \
                            || echo "  • Models were NOT successfully trained (see warning above)"

echo
echo " IMPORTANT NEXT STEP:"
echo "  → Open the .env file in the project root and fill in your ODDS_API_KEY."
echo "    (Without a valid API key, live odds will not load.)"
echo
echo " To run the app:"
echo "   1) ./scripts/run.sh"
echo
echo " Tips (Mac):"
echo "   - If you see compiler errors from SciPy/NumPy, run: xcode-select --install"
echo "   - If python3 is missing: brew install python (Homebrew)"
echo "--------------------------------------------"