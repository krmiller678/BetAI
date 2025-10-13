# 🧰 BetAI Setup & Run Guide (Mac)

This guide explains how to set up and run the BetAI project from scratch using the helper scripts in the `/scripts` folder.  
These steps are designed for **macOS** users and will work in **any IDE or terminal**.

---

## 🪜 Step-by-Step Instructions

### 1️⃣ Give the scripts permission to run

Before running anything, make the scripts executable (you only need to do this once):

```bash
chmod +x scripts/setup.sh
chmod +x scripts/run.sh
```

> 💡 *This tells macOS that these `.sh` files can be executed as programs.*

---

### 2️⃣ Set up your development environment

Run the setup script to prepare everything:

```bash
./scripts/setup.sh
```

This script will:

1. Create a **virtual environment** in `.venv/` if one doesn’t exist.  
2. Activate that environment.  
3. Upgrade `pip` to the latest version.  
4. Install all dependencies listed in the main `requirements.txt`.  
5. Create the following folders (if missing):
   ```
   backend/data/
   backend/trained_models/
   backend/core/betai/registry/
   ```
6. Generate a `.env` file with sensible defaults:
   ```bash
   PYTHONPATH=backend/core
   KELLY_FRACTION=0.25
   EV_THRESHOLD=0.02
   MAX_STAKE_PCT=0.10
   MODEL_STORE_ROOT=backend/trained_models
   ODDS_API_KEY=
   ODDS_API_URL=https://api.the-odds-api.com/v4
   ```

> 🧠 After setup, your environment is ready and all Python packages are installed locally inside `.venv`.

---

### 3️⃣ 🧩 (Optional) Using the Virtual Environment Manually

⚠️ The setup script (setup.sh) creates and uses the virtual environment during installation,
but the activation only applies inside that script.
Once it finishes, your terminal session goes back to the system Python.

If you plan to:
	•	run Python commands manually (python, streamlit run, etc.),
	•	test or debug modules from the terminal,
	•	or use the environment interactively in VS Code / PyCharm,

you’ll need to activate the venv yourself first:

```bash
source .venv/bin/activate
```

You’ll know it worked if your prompt looks like:

```bash
(.venv)
```

To deactivate it later:
```bash
deactivate
```

---

### 4️⃣ Run the app

Once setup is complete, launch the Streamlit app with:

```bash
./scripts/run.sh
```

This script will:

1. Activate the `.venv` environment.  
2. Load environment variables from `.env`.  
3. Set `PYTHONPATH` to point to the backend core package.  
4. Start Streamlit using the main app file:

   ```
   frontend/streamlit_app/application.py
   ```

5. Default port is **8501**, but you can override it like this:
   ```bash
   PORT=8600 ./scripts/run.sh
   ```

6. When successful, you’ll see:
   ```
   You can now view your Streamlit app in your browser.
   Network URL: http://localhost:8501
   ```

---

### 5️⃣ (Optional) Common Troubleshooting Tips

| Issue | Fix |
|-------|-----|
| `command not found: python3` | Install via Homebrew: `brew install python` |
| `xcode-select error` | Run: `xcode-select --install` to add developer tools |
| `Permission denied` | Ensure `chmod +x` was run on both scripts |
| `streamlit: command not found` | Run setup again to reinstall dependencies |
| Import errors for `betai` | Ensure `.env` exists and has `PYTHONPATH=backend/core` |
| Virtual env not activated in IDE | Run the app via terminal instead of IDE’s run button |

---

### 6️⃣ (Optional) Clean setup (start fresh)

If you ever need to wipe and reinstall everything:

```bash
rm -rf .venv
./scripts/setup.sh
```

---

## ⚙️ Script Summary

| Script | Purpose | Usage |
|---------|----------|--------|
| **setup.sh** | Creates and configures the development environment (installs dependencies, creates folders, adds `.env`) | `./scripts/setup.sh` |
| **run.sh** | Runs the Streamlit app (auto-loads `.env`, activates `.venv`, and starts app) | `./scripts/run.sh` |

---

## ✅ Example Full Workflow

```bash
# 1. Give permission once
chmod +x scripts/setup.sh scripts/run.sh

# 2. Set up your environment
./scripts/setup.sh

# 3. Run the app
./scripts/run.sh
```

That’s it — you should see the Streamlit app running locally.

---