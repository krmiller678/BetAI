"""
Spread coordinator — minimal wrapper.

This mirrors `MoneylineCoordinator`: the coordinator constructs the
`Spread` ensemble and exposes `recommend(context)` which returns a
simple dict with `p_model` and `model_name`.
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path

from ..models.spread.spread_ensemble import Spread

Registry_DIR = Path(__file__).resolve().parents[2] / "betai" / "registry"

FEATURES_FILE = Registry_DIR / "spread_ensemble_features.txt"

class SpreadCoordinator:
    """Thin coordinator delegating to the `Spread` ensemble."""

    def __init__(self) -> None:
        self.model = Spread()

    def recommend(self, context: Dict[str, Any]) -> Dict[str, Any]:
        p = float(self.model.predict_proba(context))
        return {"p_model": p, "model_name": "spread_ensemble"}

