# ------------------------------------------------------------
# @file        moneyline.py
# @brief       Coordinator module for moneyline predictions
# @details
# This module represents the "offensive coordinator" in our football analogy.
# Its job is to handle **moneyline bets**, which are about who will win,
# not by how much. It takes the current game situation (context),
# converts it into model-friendly features, passes it into the model
# to get a win probability, and returns that information to the Agent.
#
# The agent (head coach) then uses this probability to calculate expected
# value (EV), apply bankroll management, and decide whether to bet.
#
# The coordinator uses a simple placeholder model (MoneylineLR) that can
# later be swapped out for a trained logistic regression model.
# ------------------------------------------------------------

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import pandas as pd

# Import the simple logistic regression model (can be swapped for a real one later)
from ..models.logistic_regression import LogisticRegressionModel as MoneylineLR

# Define the path to the registry folder where our feature lists or configs might live
REGISTRY_DIR = Path(__file__).resolve().parents[2] / "betai" / "registry"

# Define the specific file that lists which features are used by this model
FEATURES_FILE = REGISTRY_DIR / "moneyline_lr_features.txt"


# ------------------------------------------------------------
# @class MoneylineCoordinator
# @brief Handles all logic for moneyline bet predictions.
# @details
# The MoneylineCoordinator acts like the Offensive Coordinator:
# - It receives the current game context (situation)
# - Converts that into structured numeric features
# - Calls the model to get a win probability (p_model)
# - Returns this to the Agent for further decision-making
# ------------------------------------------------------------
class MoneylineCoordinator:
    """Handles the process of generating a model-based probability for moneyline bets."""

    def __init__(self):
        # Create an instance of our logistic regression model
        # (This could later load a trained sklearn model instead.)
        self.model = MoneylineLR()

        # --------------------------------------------------------
        # Feature resolution logic (simple & safe):
        # 1) Prefer the model's declared feature_list (single source of truth).
        # 2) If the features file exists AND has at least one non-comment line,
        #    use that to override (lets you tweak without code changes).
        # 3) If neither provides anything, fall back to a sensible default list.
        # --------------------------------------------------------

        # 1) Start from the model's own feature list (if provided)
        self.feature_list = list(getattr(self.model, "feature_list", []) or [])

        # 2) Optional file override (only if the file actually contains features)
        try:
            lines = FEATURES_FILE.read_text().splitlines()
            file_features = [
                ln.strip()
                for ln in lines
                if ln.strip() and not ln.startswith("#")
            ]
            if file_features:  # only override if non-empty
                self.feature_list = file_features
        except FileNotFoundError:
            # Silently ignore; we'll use model/defaults
            pass

        # 3) Final fallback (guarantee columns exist)
        if not self.feature_list:
            self.feature_list = [
                "seconds_left",  # How much time remains in the game
                "score_diff",  # Current score difference (positive = team is winning)
                "is_home",  # Whether the team is playing at home
                "pregame_elo_diff",  # Pre-game Elo rating difference
                "has_possession",  # Whether the team currently has possession
            ]

    # --------------------------------------------------------
    # @function _build_row
    # @brief Converts a context dictionary into a single model row.
    # @param context A dictionary containing live game data.
    # @return A pandas DataFrame with one row of numeric features.
    # @details
    # Think of this step like creating a scouting report for the current play.
    # Each feature (like score_diff or is_home) is one "box" we fill in with numbers
    # before we ask the model to make its judgment.
    # --------------------------------------------------------
    def _build_row(self, context: Dict[str, Any]) -> pd.DataFrame:
        # Convert all expected features into floats, using 0.0 for any missing values
        row = {f: float(context.get(f, 0.0)) for f in self.feature_list}

        # Build a DataFrame because our model expects tabular input
        df = pd.DataFrame([row], columns=self.feature_list)

        # Return the structured single-row DataFrame
        return df

    # --------------------------------------------------------
    # @function recommend
    # @brief Generates a model probability for the given context.
    # @param context A dictionary of live game information (the current situation).
    # @return A dictionary with:
    #   - p_model: predicted probability of winning
    #   - model_name: which model was used for the prediction
    # @details
    # The Agent (head coach) calls this to get the model’s estimate
    # for how likely a team is to win based on the current features.
    #
    # Example return:
    #   {
    #     "p_model": 0.64,         # Model predicts 64% win chance
    #     "model_name": "ml_lr_stub"
    #   }
    # --------------------------------------------------------
    def recommend(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Step 1: Build the feature row from the context
        X = self._build_row(context)

        # Step 2: Ask the model for its predicted probability
        # (currently uses our simple stub model that adds small bonuses for good conditions)
        p = float(self.model.predict_proba(X))

        # Step 3: Return a clean, structured response for the Agent
        return {
            "p_model": p,  # The probability from the model (0–1)
            "model_name": "ml_lr_stub",  # Name of the model used (for logging/display)
        }
