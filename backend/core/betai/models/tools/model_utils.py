import joblib
import os
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_DIR.mkdir(exist_ok=True)

def save_model(model, filename):
    path = MODEL_DIR / filename
    joblib.dump(model, path)
    print(f"✅ Model saved at {path}")

def load_model(filename):
    path = MODEL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")
    return joblib.load(path)