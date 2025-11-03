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


# Create convenience functions for normalization
def normalize_events(raw_events):
    """Convenience function to normalize events using a default client"""
    client = OddsAPIClient(api_key="dummy")  # Will be overridden by actual client
    return client.normalize_events(raw_events)


def normalize_scores(raw_scores):
    """Convenience function to normalize scores using a default client"""
    client = OddsAPIClient(api_key="dummy")  # Will be overridden by actual client
    return client.normalize_scores(raw_scores)


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
    "normalize_events",
    "normalize_scores",
]
