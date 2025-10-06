# logistic regression model
import joblib
import pandas as pd
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_PATH = MODEL_DIR / "logistic_regression.pkl"
FEATURES_PATH = MODEL_DIR / "logistic_regression_features.txt"


class LogisticRegressionModel:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        with open(FEATURES_PATH, "r") as f:
            self.feature_list = [line.strip() for line in f if line.strip()]

    def predict_proba(self, df: pd.DataFrame):
        """Return positive-class probabilities (win probability)."""
        X = df[self.feature_list]
        return self.model.predict_proba(X)[:, 1]

    def predict(self, df: pd.DataFrame):
        """Return binary predictions (0/1 for lose/win)."""
        X = df[self.feature_list]
        return self.model.predict(X)