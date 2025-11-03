"""
HTTP client with rate limiting and retry logic for The Odds API
"""

import requests
import time
from typing import Dict, Any, Optional, Tuple
from threading import Lock
from .errors import (
    OddsAPIError,
    AuthenticationError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    ClientError,
)


class SimpleRateLimiter:
    """Simple rate limiter using token bucket algorithm"""

    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.tokens = requests_per_minute
        self.last_update = time.time()
        self.lock = Lock()

    def wait(self):
        """Wait if necessary to respect rate limits"""
        with self.lock:
            now = time.time()
            # Add tokens based on time elapsed
            time_passed = now - self.last_update
            self.tokens = min(
                self.requests_per_minute,
                self.tokens + (time_passed * self.requests_per_minute / 60),
            )
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
            else:
                # Wait for next token
                wait_time = (1 - self.tokens) * 60 / self.requests_per_minute
                time.sleep(wait_time)
                self.tokens = 0


class HTTPClient:
    """HTTP client with rate limiting, retry logic, and caching"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.the-odds-api.com/v4",
        requests_per_minute: int = 30,
        cache_ttl: int = 10,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 10
        self.rate_limiter = SimpleRateLimiter(requests_per_minute)
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Any]] = {}

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle HTTP response and raise appropriate exceptions"""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise AuthenticationError("Invalid API key")
        elif response.status_code == 402:
            raise QuotaExceededError("API quota exceeded")
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                retry_after = int(retry_after)
            raise RateLimitError("Rate limit exceeded", retry_after)
        elif 400 <= response.status_code < 500:
            raise ClientError(f"Client error: {response.status_code}")
        elif 500 <= response.status_code < 600:
            raise ServerError(f"Server error: {response.status_code}")
        else:
            raise OddsAPIError(f"Unexpected error: {response.status_code}")

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a GET request with rate limiting and caching"""
        if params is None:
            params = {}

        # Build cache key
        cache_key = f"{endpoint}|{tuple(sorted(params.items()))}"
        current_time = time.time()

        # Check cache first
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                return cached_data

        # Cache miss or expired, make request
        self.rate_limiter.wait()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        params["apiKey"] = self.api_key

        response = self.session.get(url, params=params)
        data = self._handle_response(response)

        # Store in cache
        self._cache[cache_key] = (current_time, data)

        return data

    def get_with_retry(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Make a GET request with retry logic for transient failures"""
        if params is None:
            params = {}

        # Check cache first (same logic as get method)
        cache_key = f"{endpoint}|{tuple(sorted(params.items()))}"
        current_time = time.time()

        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if current_time - cached_time < self.cache_ttl:
                return cached_data

        # Cache miss or expired, proceed with retry logic
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self.get(endpoint, params)
            except (RateLimitError, ServerError) as e:
                last_exception = e
                if attempt == max_retries - 1:
                    break

                # Exponential backoff with jitter
                wait_time = (2**attempt) + (time.time() % 1)
                time.sleep(wait_time)

        # Re-raise the last exception if all retries failed
        raise last_exception
