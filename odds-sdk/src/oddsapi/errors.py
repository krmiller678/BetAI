"""
Custom exceptions for The Odds API SDK
"""

from typing import Optional


class OddsAPIError(Exception):
    """Base exception for all Odds API errors"""

    pass


class AuthenticationError(OddsAPIError):
    """401 - Invalid API key"""

    pass


class QuotaExceededError(OddsAPIError):
    """402 - Quota exceeded"""

    pass


class RateLimitError(OddsAPIError):
    """429 - Rate limit exceeded"""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ServerError(OddsAPIError):
    """5xx - Server errors"""

    pass


class ClientError(OddsAPIError):
    """4xx - Client errors"""

    pass
