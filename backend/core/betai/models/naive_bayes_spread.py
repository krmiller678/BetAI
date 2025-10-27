import joblib
import pandas as pd
from pathlib import Path

# Trained artifacts live in `backend/trained_models/spread` (not inside the
# package folder). Resolve that directory relative to this file by walking
# up to the repository `backend` folder and into `trained_models/spread`.
MODEL_DIR = Path(__file__).resolve().parents[3] / "trained_models" / "spread"
MODEL_PATH = MODEL_DIR / "nb_spread.pkl"
FEATURES_PATH = MODEL_DIR / "nb_spread_features.txt"


class NBSpread:
    def __init__(self):
        self.model = joblib.load(MODEL_PATH)
        with open(FEATURES_PATH, "r") as f:
            self.feature_list = [line.strip() for line in f if line.strip()]

    def _prepare_input(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
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
