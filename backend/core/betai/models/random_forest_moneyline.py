# random forest model
import joblib
import pandas as pd
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_PATH = MODEL_DIR / "rf_moneyline.pkl"
FEATURES_PATH = MODEL_DIR / "rf_moneyline_features.txt"

class RFMoneyLine:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        with open(FEATURES_PATH, "r") as f:
            self.feature_list = [line.strip() for line in f if line.strip()]

    def _prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Add missing features with 0
        for col in self.feature_list:
            if col not in df.columns:
                df[col] = 0
        return df[self.feature_list]

    def predict_proba(self, df: pd.DataFrame):
        X = self._prepare_input(df)
        return self.model.predict_proba(X)[:, 1]

    def predict(self, df: pd.DataFrame):
        X = self._prepare_input(df)
        return self.model.predict(X)
