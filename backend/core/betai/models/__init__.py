"""Model package for BetAI.

Expose the model subpackages so callers import explicitly, e.g.:

	from backend.core.betai.models.moneyline import LRMoneyLine

Keeping imports lightweight at package import time avoids loading heavy
dependencies until a specific model is requested.
"""

# Import only the model subpackages that actually exist in this repo.
# The 'total' module is not present (coordinator may exist elsewhere),
# so avoid importing it here to prevent ImportError / circular import.
from . import moneyline, spread
from . import abbreviations

__all__ = ["moneyline", "spread", "abbreviations"]