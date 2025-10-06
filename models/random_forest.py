# random forest
import joblib
import pandas as pd
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_PATH = MODEL_DIR / "random_forest.pkl"
FEATURES_PATH = MODEL_DIR / "random_forest_features.txt"

class RandomForestModel:
    def __init__(self):
        # Load the trained model
        self.model = joblib.load(MODEL_PATH)

        # Load the feature list used during training
        with open(FEATURES_PATH, "r") as f:
            self.feature_list = [line.strip() for line in f if line.strip()]

    def _prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure df has all training features in the correct order and fill missing cols."""
        df = df.copy()
        # Add missing features with default 0
        for col in self.feature_list:
            if col not in df.columns:
                df[col] = 0
        # Reorder columns to match training
        return df[self.feature_list]

    def predict_proba(self, df: pd.DataFrame):
        X = self._prepare_input(df)
        return self.model.predict_proba(X)[:, 1]  # probability of win

    def predict(self, df: pd.DataFrame):
        X = self._prepare_input(df)
        return self.model.predict(X)
