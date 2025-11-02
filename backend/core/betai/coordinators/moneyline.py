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
from ..models.moneyline_ensemble import Moneyline

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
        self.model = Moneyline()

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
        # Get the ensemble probability
        
        p = float(self.model.predict_proba(context))

        return {
            "p_model": p,                # The probability from the model (0–1)
            "model_name": "ml_ensemble",  # Name of the model used (for logging/display)
        }