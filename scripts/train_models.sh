#!/bin/bash
# --------------------------------------------
# File: scripts/train_models.sh
# Purpose: Train BetAI ML models (moneyline + spread)
# --------------------------------------------

# Exit immediately on error
set -e

# --------------------------------------------
# Move to repo root (one level above scripts/)
# --------------------------------------------
cd "$(dirname "$0")/.."

echo "--------------------------------------------"
echo " Training BetAI models"
echo "  - Moneyline"
echo "  - Spread"
echo "--------------------------------------------"

# --------------------------------------------
# Choose a Python executable
# --------------------------------------------
PY="python3"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Trying 'python'..."
  PY="python"
fi

# --------------------------------------------
# Ensure virtual environment exists
# --------------------------------------------
if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found. Run ./scripts/setup.sh first."
  exit 1
fi

# --------------------------------------------
# Activate virtual environment
# --------------------------------------------
# shellcheck disable=SC1091
source .venv/bin/activate

# --------------------------------------------
# Ensure backend/core is on PYTHONPATH
# (so 'betai.*' modules import correctly)
# --------------------------------------------
export PYTHONPATH="backend/core:${PYTHONPATH}"

# --------------------------------------------
# Train MONEYLINE models
# --------------------------------------------
echo
echo ">>> Training MONEYLINE models..."
$PY -m betai.models.moneyline.models_train_moneyline

# --------------------------------------------
# Train SPREAD models
# --------------------------------------------
echo
echo ">>> Training SPREAD models..."
$PY -m betai.models.spread.models_train_spread

echo
echo "--------------------------------------------"
echo " ✅ Model training complete!"
echo "   - Moneyline + Spread .pkl files updated"
echo "--------------------------------------------"