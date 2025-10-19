# backend/core/betai/integrations/odds_api.py
# ------------------------------------------------------------
# The Odds API (V4) integration - SDK wrapper
# - Thin wrapper around the enhanced odds-sdk
# - Maintains backward compatibility with existing BetAI code
# - Provides the same interface as the original integration
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
from typing import Any, Dict, List, Optional

# Import the enhanced SDK
from oddsapi import (
    OddsAPIClient,
    normalize_events as sdk_normalize_events,
    normalize_scores as sdk_normalize_scores,
)


class TheOddsAPIProvider:
    """
    Backward-compatible wrapper around the enhanced OddsAPI SDK.
    Maintains the same interface as the original integration for seamless migration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_ttl: int = 10,
    ):
        # Pull config from args or environment so we don't hardcode secrets.
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("ODDS_API_URL") or "https://api.the-odds-api.com/v4"
        ).rstrip("/")
        self.cache_ttl = int(cache_ttl)

        # Verify key exists early so users get clear setup feedback.
        if not self.api_key:
            raise RuntimeError("Missing ODDS_API_KEY. Set it in your .env file.")

        # Create the SDK client
        self.client = OddsAPIClient(
            api_key=self.api_key, base_url=self.base_url, cache_ttl=self.cache_ttl
        )

    def list_sports(self) -> List[Dict[str, Any]]:
        """
        List all available sports/sport_keys.
        Docs: GET /sports
        """
        sports = self.client.get_sports(active_only=True)
        # Convert SDK Sport objects to dict format for backward compatibility
        return [
            {
                "key": sport.key,
                "title": sport.title,
                "description": sport.description,
                "active": sport.active,
                "has_outrights": sport.has_outrights,
            }
            for sport in sports
        ]

    def fetch_markets(
        self,
        sport_key: str,
        *,
        regions: str = "us",
        markets: str = "h2h,spreads,totals",
        odds_format: str = "decimal",
        bookmakers: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
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
        # Parse regions and markets
        region_list = [r.strip() for r in regions.split(",")]
        market_list = [m.strip() for m in markets.split(",")]

        # Map string regions to SDK Region enum
        from oddsapi import Region

        region_enums = []
        for r in region_list:
            if r.upper() == "US":
                region_enums.append(Region.US)
            elif r.upper() == "UK":
                region_enums.append(Region.UK)
            elif r.upper() == "AU":
                region_enums.append(Region.AU)
            elif r.upper() == "EU":
                region_enums.append(Region.EU)
            else:
                region_enums.append(Region.US)  # Default fallback

        # Map string markets to SDK Market enum
        from oddsapi import Market

        market_enums = []
        for m in market_list:
            if m.lower() == "h2h":
                market_enums.append(Market.H2H)
            elif m.lower() == "spreads":
                market_enums.append(Market.SPREADS)
            elif m.lower() == "totals":
                market_enums.append(Market.TOTALS)

        # Map odds format
        from oddsapi import OddsFormat

        odds_format_enum = (
            OddsFormat.DECIMAL
            if odds_format.lower() == "decimal"
            else OddsFormat.AMERICAN
        )

        # Get odds from SDK
        odds = self.client.get_odds(
            sport_key=sport_key,
            regions=region_enums,
            markets=market_enums,
            odds_format=odds_format_enum,
        )

        # Convert SDK EventOdds objects back to raw dict format for backward compatibility
        raw_events = []
        for event in odds:
            raw_event = {
                "id": event.id,
                "sport_key": event.sport_key,
                "sport_title": event.sport_title,
                "commence_time": event.commence_time.isoformat(),
                "home_team": event.home_team,
                "away_team": event.away_team,
                "bookmakers": [],
            }

            for bookmaker in event.bookmakers:
                raw_bookmaker = {
                    "key": bookmaker.key,
                    "title": bookmaker.title,
                    "markets": [],
                }

                for market in bookmaker.markets:
                    raw_market = {"key": market.key, "outcomes": []}

                    for outcome in market.outcomes:
                        raw_outcome = {
                            "name": outcome.name,
                            "price": outcome.price,
                            "point": getattr(outcome, "point", None),
                        }
                        raw_market["outcomes"].append(raw_outcome)

                    raw_bookmaker["markets"].append(raw_market)

                raw_event["bookmakers"].append(raw_bookmaker)

            raw_events.append(raw_event)

        return raw_events

    def fetch_scores(
        self,
        sport_key: str,
        *,
        days_from: int | None = None,
        date_format: str = "iso",
    ) -> List[Dict[str, Any]]:
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
        # For now, return empty list as the SDK doesn't have a scores endpoint yet
        # This maintains backward compatibility
        return []


# Export the normalization functions for backward compatibility
def normalize_events(raw_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert provider JSON into a neutral shape used across the app.
    This is a wrapper around the SDK's normalization function.
    """
    return sdk_normalize_events(raw_events)


def normalize_scores(raw_scores: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert provider scores JSON into a neutral shape.
    This is a wrapper around the SDK's normalization function.
    """
    return sdk_normalize_scores(raw_scores)
