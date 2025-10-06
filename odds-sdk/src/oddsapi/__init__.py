"""
Minimal typed Python SDK for The Odds API

A simple, well-typed Python SDK for The Odds API that provides clean abstractions
for the core endpoints with proper error handling and type safety.
"""

from .client import OddsAPIClient
from .types import (
    Region,
    Market,
    OddsFormat,
    DateFormat,
    Sport,
    EventOdds,
    Bookmaker,
    MarketOdds,
    Outcome,
)
from .errors import (
    OddsAPIError,
    AuthenticationError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    ClientError,
)

__version__ = "0.1.0"
__author__ = "BetAI Team"

__all__ = [
    "OddsAPIClient",
    "Region",
    "Market",
    "OddsFormat",
    "DateFormat",
    "Sport",
    "EventOdds",
    "Bookmaker",
    "MarketOdds",
    "Outcome",
    "OddsAPIError",
    "AuthenticationError",
    "QuotaExceededError",
    "RateLimitError",
    "ServerError",
    "ClientError",
]
