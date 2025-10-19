#!/bin/bash
# --------------------------------------------
# File: scripts/run.sh
# Purpose: Run the Streamlit app (Mac)
# --------------------------------------------

set -e

# Go to repo root
cd "$(dirname "$0")/.."

# Ensure venv exists
if [ ! -d ".venv" ]; then
  echo "Error: virtual environment not found. Run ./scripts/setup.sh first."
  exit 1
fi

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

# Load .env if present (export each line KEY=VALUE, ignore comments/blank lines)
if [ -f ".env" ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | grep -v '^\s*$' | xargs)
fi

# Fallback PYTHONPATH if not set in .env
export PYTHONPATH="${PYTHONPATH:-backend/core}"

# App file and port (overridable)
APP_FILE="${APP_FILE:-frontend/streamlit_app/app.py}"
PORT="${PORT:-8501}"

echo "--------------------------------------------"
echo " Running Streamlit"
echo "  - App:  $APP_FILE"
echo "  - Port: $PORT"
echo "  - PYTHONPATH: $PYTHONPATH"
echo "--------------------------------------------"

streamlit run "$APP_FILE" --server.port="$PORT" --server.headless=true