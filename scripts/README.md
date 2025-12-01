# 🧰 BetAI Scripts Guide  
### Environment Setup • Model Training • App Execution

This guide explains how to use the helper scripts inside the `/scripts` directory to fully set up and run the BetAI application.  
These scripts ensure **any user can install, train models, and launch the app with a single command**, without manual Python or dependency management.

Designed for **macOS** and **Linux** environments.

---

# 📁 Included Scripts

| Script | Purpose |
|--------|---------|
| **setup.sh** | Creates the virtual environment, installs dependencies, installs the odds-sdk, trains ML models automatically, generates `.env` |
| **run.sh** | Activates the environment and launches the Streamlit application |
| **train_models.sh** | (Called automatically by setup) Trains moneyline & spread models from scratch |

---

# ⚙️ 1. Make Scripts Executable (Required Once)

Before running anything:

```bash
chmod +x scripts/setup.sh
chmod +x scripts/run.sh
chmod +x scripts/train_models.sh
```

This allows macOS/Linux to run the scripts as programs.

---

# 🚀 2. Full Environment Setup

Run this **once per machine** or whenever dependencies change:

```bash
./scripts/setup.sh
```

The setup script performs:

### ✔ Virtual environment creation (`.venv`)
If `.venv/` does not exist, it creates one.  
If it *does* exist, it reuses it.

### ✔ Repairs pip if needed  
Handles corrupted or missing pip installations automatically.

### ✔ Installs Python packages from `requirements.txt`  
Into the local `.venv`, isolated from your system Python.

### ✔ Installs the included Odds API SDK (`odds-sdk/`)  
In editable mode:
```bash
pip install -e ./odds-sdk
```

### ✔ Generates the `.env` file automatically  
With fields like:

```
PYTHONPATH=backend/core:odds-sdk/src
KELLY_FRACTION=0.25
EV_THRESHOLD=0.02
MODEL_STORE_ROOT=backend/trained_models
ODDS_API_KEY=
ODDS_API_URL=https://api.the-odds-api.com/v4
```

### ✔ **Automatically trains all machine learning models**  
Runs:
- `models_train_moneyline.py`
- `models_train_spread.py`

using the new `train_models.sh` helper script.

### ✔ Final recap message  
Shows everything setup successfully.

---

# 🔑 3. Add Your API Key (Required)

Open `.env` and fill in:

```
ODDS_API_KEY=YOUR_REAL_KEY
```

Without a key, odds will not load.

---

# ▶️ 4. Run the Application

After setup is complete:

```bash
./scripts/run.sh
```

This script:

1. Activates `.venv`
2. Loads `.env` variables
3. Sets `PYTHONPATH` correctly:
   ```
   backend/core : odds-sdk/src
   ```
4. Launches Streamlit:
   ```
   frontend/streamlit_app/app.py
   ```
5. Opens the app at:
   ```
   http://localhost:8501
   ```

### Change the port:
```bash
PORT=8700 ./scripts/run.sh
```

---

# 🧩 5. Using the Virtual Environment Manually (Optional)

If you want to run Python commands manually:

```bash
source .venv/bin/activate
```

Prompt becomes:

```
(.venv)
```

Deactivate anytime with:

```bash
deactivate
```

---

# 🛠️ 6. Troubleshooting

| Issue | Fix |
|------|------|
| `streamlit: command not found` | Re-run `./scripts/setup.sh` |
| API errors | Ensure `.env` contains a valid `ODDS_API_KEY` |
| IDE cannot import modules | Ensure `PYTHONPATH` is set; run via terminal |
| Missing models | Rerun: `./scripts/train_models.sh` |
| Pip broken | Setup script automatically repairs with ensurepip + get-pip |

---

# 🔄 7. Reset Everything (Clean Reinstall)

If something becomes misconfigured:

```bash
rm -rf .venv backend/trained_models
./scripts/setup.sh
```

This recreates everything from scratch.

---

# ✅ Example Full Workflow

```bash
# 1. Give script permissions
chmod +x scripts/*.sh

# 2. Setup environment + train models
./scripts/setup.sh

# 3. Run the app
./scripts/run.sh
```

---

# 🎉 That’s It!

The `scripts` folder provides a **zero-setup**, **zero-configuration**, **one-command** workflow to easily run BetAI