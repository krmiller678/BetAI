"""Spread coordinator — thin wrapper.

Delegates feature building and ensemble logic to
`backend.core.betai.models.spread.spread_ensemble.Spread`.

Public API:
- `SpreadCoordinator()`
- `recommend(context)` -> {"p_model": float, "model_name": str}
"""

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path

from ..models.spread.spread_ensemble import Spread

# Registry paths (kept for consistency; not used by this thin wrapper)
Registry_DIR = Path(__file__).resolve().parents[2] / "betai" / "registry"
FEATURES_FILE = Registry_DIR / "spread_ensemble_features.txt"


class SpreadCoordinator:
    """Thin coordinator that forwards context to the Spread ensemble."""

    def __init__(self) -> None:
        # Construct the ensemble once and reuse it.
        self.model = Spread()

    def recommend(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return model probability for the given context.

        The coordinator does minimal work: it forwards `context` to the
        ensemble and returns a small mapping expected by the Agent/UI.
        """
        p = float(self.model.predict_proba(context))
        return {"p_model": p, "model_name": "spread_ensemble"}

