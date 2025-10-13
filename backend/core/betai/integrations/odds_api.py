# backend/core/betai/integrations/odds_api.py
# ------------------------------------------------------------
# The Odds API (V4) integration
# - Small, readable client that fetches live odds.
# - Returns plain Python dicts/lists (easy for Streamlit, API, or DB).
# - Normalizes vendor JSON into a stable internal schema so the
#   rest of your app doesn't care which provider you use.
#
# Env vars (set these in .env):
#   ODDS_API_KEY=your_key_here
#   ODDS_API_URL=https://api.the-odds-api.com/v4   (default used if unset)
#
# Example usage (Streamlit / any Python):
#   from betai.integrations.odds_api import TheOddsAPIProvider, normalize_events
#   prov = TheOddsAPIProvider()
#   raw = prov.fetch_markets(sport_key="americanfootball_nfl", regions="us", markets="h2h,spreads,totals")
#   events = normalize_events(raw)
#   # 'events' is now a list of clean game/offer dicts your app/agent can use.
# ------------------------------------------------------------

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests


class TheOddsAPIProvider:
    """
    Tiny client for The Odds API (https://the-odds-api.com).
    We keep it *very* simple, with:
      - env-driven base URL + API key
      - small in-memory cache to reduce quota usage
      - two main calls you need right now: list_sports() and fetch_markets()
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, cache_ttl: int = 10):
        # Pull config from args or environment so we don't hardcode secrets.
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self.base_url = (base_url or os.getenv("ODDS_API_URL") or "https://api.the-odds-api.com/v4").rstrip("/")
        
        # The cache_ttl defines how long (in seconds) a cached API response remains valid before we fetch fresh data again.
        # Example: if ttl=10, then calling fetch_markets() twice within 10s will use the same cached data and avoid another HTTP request.
        self.cache_ttl = int(cache_ttl)

        # Simple in-memory cache structure:
        #   { cache_key: (timestamp, response_data) }
        # This avoids re-hitting the API when Streamlit auto-refreshes rapidly.
        # Note: It’s not meant for production persistence—just a local memory throttle.
        self._cache: Dict[str, Tuple[float, Any]] = {}

        # Verify key exists early so users get clear setup feedback.
        if not self.api_key:

            # Streamlit can catch and show a friendly error; FastAPI can 500 + log.
            raise RuntimeError("Missing ODDS_API_KEY. Set it in your .env file.")

    # ------------------------------------------------------------
    # Internal helper function for GET requests (with simple cache)
    # ------------------------------------------------------------
    def _get(self, path: str, params: Dict[str, Any]) -> Any:
        """
        Core GET method used by list_sports() and fetch_markets().

        How the caching logic works:
          1. We build a cache_key based on the URL and parameters.
          2. If that exact request was made less than 'cache_ttl' seconds ago,
             we return the stored response instead of calling the API again.
          3. Otherwise, we make a fresh HTTP request and overwrite the cache.

        This helps prevent blowing through free-tier API quotas when the
        Streamlit app auto-refreshes or the user presses refresh repeatedly.
        """
        # Combine base URL with the endpoint path.
        url = f"{self.base_url}{path}"

        # Always include our API key in params.
        full_params = dict(params or {})
        full_params["apiKey"] = self.api_key

        # Build a unique cache key for this request.
        # The tuple(sorted(...)) part ensures parameter order doesn’t affect the key.
        cache_key = f"{url}|{tuple(sorted(full_params.items()))}"

        # Current time (seconds since epoch).
        ts = time.time()

        # --- Check for valid cached data ---
        if cache_key in self._cache:
            cached_ts, cached_data = self._cache[cache_key]

            # If the cached entry is still fresh (younger than cache_ttl seconds),
            # we skip the network call and just return the stored data.
            if ts - cached_ts < self.cache_ttl:
                # Uncomment this for debugging:
                # print(f"[CACHE HIT] {path} (age: {ts - cached_ts:.1f}s)")
                return cached_data

        # --- Otherwise, make a new HTTP GET call ---
        resp = requests.get(url, params=full_params, timeout=15)

        # Raise an exception if the provider returns an error (e.g., bad key, 429 rate limit).
        resp.raise_for_status()

        # Parse JSON payload.
        data = resp.json()

        # Store in cache with current timestamp.
        self._cache[cache_key] = (ts, data)

        # Uncomment for debugging:
        # print(f"[CACHE MISS] New request made to {url}")

        return data

    # -------------------------------
    # Public API calls
    # -------------------------------
    def list_sports(self) -> List[Dict[str, Any]]:
        """
        List all available sports/sport_keys.
        Docs: GET /sports
        """
        return self._get("/sports", {})

    def fetch_markets(self, sport_key: str, *, regions: str = "us", markets: str = "h2h,spreads,totals", odds_format: str = "decimal", bookmakers: Optional[str] = None,) -> List[Dict[str, Any]]:
        """
        Fetch odds for a given sport_key.
        Docs: GET /sports/{sport_key}/odds

        Args:
          sport_key: e.g., "americanfootball_nfl", "basketball_nba", etc.
          regions:   "us", "us2", "eu", "uk", "au" (see provider docs)
          markets:   CSV of market keys, e.g. "h2h,spreads,totals"
          odds_format: "decimal" (recommended) or "american"
          bookmakers: optional CSV of specific books to include

        Returns:
          Provider-shaped JSON (we normalize it with normalize_events()).
        """
        params: Dict[str, Any] = {
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        return self._get(f"/sports/{sport_key}/odds", params)
    
    def fetch_scores(self, sport_key: str, *, days_from: int | None = None, date_format: str = "iso",) -> List[Dict[str, Any]]:
        """
        Fetch recent/ongoing game scores for a given sport_key.
        Docs: GET /sports/{sport_key}/scores

        Args:
          sport_key:   e.g., "americanfootball_nfl"
          days_from:   Optional integer lookback window (provider supports a small window)
          date_format: "iso" recommended (provider also supports "unix" but we stick to ISO)

        Returns:
          Provider-shaped list of score records (use normalize_scores(...) to standardize).
        """
        # Build query parameters for scores endpoint
        params: Dict[str, Any] = {
            "dateFormat": date_format,    # Prefer ISO timestamps for readability
        }
        # Only include daysFrom if the caller provided it
        if days_from is not None:
            params["daysFrom"] = int(days_from)

        # Perform the GET to the scores endpoint
        return self._get(f"/sports/{sport_key}/scores", params)


# ------------------------------------------------------------
# Normalization helpers
# ------------------------------------------------------------

def _map_market_key(provider_key: str) -> Optional[str]:
    """
    Map provider market keys to our internal three lanes.
      provider 'h2h'    -> 'moneyline'
      provider 'spreads'-> 'spread'
      provider 'totals' -> 'total'
    Unknown keys return None (ignored).
    """
    if provider_key == "h2h":
        return "moneyline"
    if provider_key == "spreads":
        return "spread"
    if provider_key == "totals":
        return "total"
    return None


def normalize_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert provider JSON into a neutral shape used across the app.

    Output schema (list of games):
    [
      {
        "game_id": str,
        "commence_time": str,     # ISO timestamp
        "home": str,
        "away": str,
        "offers": [               # list of priced sides across markets/books
          {
            "bookmaker": str,
            "market": "moneyline" | "spread" | "total",
            "side": str,          # e.g. "DET ML", "DET -3.5", "Over 46.5"
            "decimal_odds": float,
            "context": { ... }    # minimal info the agent/coordinator may need
          },
          ...
        ]
      },
      ...
    ]
    """
    games: List[Dict[str, Any]] = []

    for ev in raw_events or []:
        game = {
            "game_id": ev.get("id"),
            "commence_time": ev.get("commence_time"),
            "home": ev.get("home_team"),
            "away": ev.get("away_team"),
            "offers": [],
        }

        # Walk all bookmakers and markets to collect offers
        for bm in ev.get("bookmakers", []):
            book_title = bm.get("title") or bm.get("key") or "Unknown"
            for mk in bm.get("markets", []):
                provider_key = mk.get("key")  # 'h2h' | 'spreads' | 'totals' | ...
                internal_market = _map_market_key(provider_key)
                if not internal_market:
                    # Ignore any market types we don't support yet.
                    continue

                # Each 'outcomes' entry is a priced side of this market.
                for out in mk.get("outcomes", []):
                    # Build a friendly 'side' label and minimal context.
                    # NOTE: The Odds API returns:
                    #   - for h2h: name = team name
                    #   - for spreads/totals: name = team OR "Over"/"Under", plus 'point'
                    name = out.get("name")  # team or "Over"/"Under"
                    price = out.get("price")  # price already decimal if oddsFormat=decimal
                    point = out.get("point", None)

                    if internal_market == "moneyline":
                        side_label = f"{name} ML"
                        ctx = {"market_key": "h2h"}
                    elif internal_market == "spread":
                        # Example: "DET -3.5"
                        side_label = f"{name} {point}"
                        ctx = {"market_key": "spreads", "point": point}
                    else:  # "total"
                        # Example: "Over 46.5"
                        side_label = f"{name} {point}"
                        ctx = {"market_key": "totals", "point": point}

                    offer = {
                        "bookmaker": book_title,
                        "market": internal_market,
                        "side": side_label,
                        "decimal_odds": float(price),
                        # Minimal context:
                        # Keep it light; your coordinators can enrich with team stats later.
                        "context": {
                            "home_team": game["home"],
                            "away_team": game["away"],
                            "bookmaker": book_title,
                            "provider_market_key": provider_key,
                            "point": point,
                        },
                    }
                    game["offers"].append(offer)

        games.append(game)

    return games

def normalize_scores(raw_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert provider score JSON into a neutral, compact shape.

    Output schema (list of games):
    [
      {
        "game_id": str,
        "commence_time": str,     # ISO timestamp
        "completed": bool,
        "home": str,
        "away": str,
        "home_score": Optional[int],
        "away_score": Optional[int],
        "last_update": Optional[str],  # provider last-update ISO if present
      },
      ...
    ]
    """
    games: List[Dict[str, Any]] = []

    # Walk each score item returned by the provider
    for ev in raw_scores or []:
        # Read home/away team names directly from provider payload
        home = ev.get("home_team")
        away = ev.get("away_team")

        # The Odds API returns a 'scores' list with entries like:
        #   [{"name": "Detroit Lions", "score": 34}, {"name": "Green Bay Packers", "score": 20}]
        scores_list = ev.get("scores") or []

        # Initialize home/away numeric scores as None
        home_score = None
        away_score = None

        # Attempt to map provider scores to home/away by matching names
        for s in scores_list:
            name = s.get("name")
            val = s.get("score")
            # Ensure we coerce values to int when possible (provider may return str)
            try:
                val_int = int(val) if val is not None else None
            except Exception:
                val_int = None

            if name == home:
                home_score = val_int
            elif name == away:
                away_score = val_int

        # Build normalized game record
        game = {
            "game_id": ev.get("id"),
            "commence_time": ev.get("commence_time"),
            "completed": bool(ev.get("completed", False)),
            "home": home,
            "away": away,
            "home_score": home_score,
            "away_score": away_score,
            "last_update": ev.get("last_update"),  # may be missing
        }

        games.append(game)

    return games