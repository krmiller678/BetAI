"""Model package for BetAI.

Expose the model subpackages so callers import explicitly, e.g.:

	from backend.core.betai.models.moneyline import LRMoneyLine

Keeping imports lightweight at package import time avoids loading heavy
dependencies until a specific model is requested.
"""

from . import moneyline, spread, total
from . import model_utils, abbreviations

__all__ = ["moneyline", "spread", "total", "model_utils", "abbreviations"]
