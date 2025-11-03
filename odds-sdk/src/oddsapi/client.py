"""
Main client for The Odds API
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from .http import HTTPClient
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
# Error classes are imported by HTTPClient and raised automatically


class OddsAPIClient:
    """Main client for interacting with The Odds API"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.the-odds-api.com/v4",
        requests_per_minute: int = 30,
        cache_ttl: int = 10,
    ):
        """
        Initialize the Odds API client

        Args:
            api_key: Your Odds API key
            base_url: Base URL for the API (default: https://api.the-odds-api.com/v4)
            requests_per_minute: Rate limit for requests (default: 30 - conservative)
            cache_ttl: Cache time-to-live in seconds (default: 10)
        """
        self.http = HTTPClient(api_key, base_url, requests_per_minute, cache_ttl)

    def get_sports(
        self, active_only: bool = True, use_retry: bool = True
    ) -> List[Sport]:
        """
        Get list of available sports

        Args:
            active_only: Only return active sports (default: True)
            use_retry: Use retry logic for transient failures (default: True)

        Returns:
            List of Sport objects

        Raises:
            AuthenticationError: Invalid API key
            QuotaExceededError: API quota exceeded
            RateLimitError: Rate limit exceeded
            ServerError: Server error
        """
        params = {}
        if active_only:
            params["active"] = "true"

        if use_retry:
            response = self.http.get_with_retry("/sports", params)
        else:
            response = self.http.get("/sports", params)

        return [Sport(**sport) for sport in response]

    def get_odds(
        self,
        sport_key: str,
        regions: List[Region],
        markets: List[Market] = None,
        odds_format: OddsFormat = OddsFormat.DECIMAL,
        date_format: DateFormat = DateFormat.ISO,
        event_ids: Optional[List[str]] = None,
        bookmakers: Optional[List[str]] = None,
        commence_time_from: Optional[datetime] = None,
        commence_time_to: Optional[datetime] = None,
        use_retry: bool = True,
    ) -> List[EventOdds]:
        """
        Get odds for a specific sport

        Args:
            sport_key: The sport key (e.g., 'americanfootball_nfl')
            regions: List of regions to get odds for
            markets: List of markets (default: [Market.H2H])
            odds_format: Format for odds (default: OddsFormat.DECIMAL)
            date_format: Format for dates (default: DateFormat.ISO)
            event_ids: Optional list of specific event IDs
            bookmakers: Optional list of specific bookmakers
            commence_time_from: Optional start time for events
            commence_time_to: Optional end time for events
            use_retry: Use retry logic for transient failures (default: True)

        Returns:
            List of EventOdds objects

        Raises:
            AuthenticationError: Invalid API key
            QuotaExceededError: API quota exceeded
            RateLimitError: Rate limit exceeded
            ServerError: Server error
        """
        if markets is None:
            markets = [Market.H2H]

        params = {
            "regions": ",".join([r.value for r in regions]),
            "markets": ",".join([m.value for m in markets]),
            "oddsFormat": odds_format.value,
            "dateFormat": date_format.value,
        }

        if event_ids:
            params["eventIds"] = ",".join(event_ids)
        if bookmakers:
            params["bookmakers"] = ",".join(bookmakers)
        if commence_time_from:
            params["commenceTimeFrom"] = commence_time_from.isoformat()
        if commence_time_to:
            params["commenceTimeTo"] = commence_time_to.isoformat()

        if use_retry:
            response = self.http.get_with_retry(f"/sports/{sport_key}/odds", params)
        else:
            response = self.http.get(f"/sports/{sport_key}/odds", params)

        return [self._parse_event_odds(event) for event in response]

    def get_event_odds(
        self,
        sport_key: str,
        event_id: str,
        regions: List[Region],
        markets: List[Market],
        odds_format: OddsFormat = OddsFormat.DECIMAL,
        date_format: DateFormat = DateFormat.ISO,
        use_retry: bool = True,
    ) -> EventOdds:
        """
        Get odds for a specific event

        Args:
            sport_key: The sport key (e.g., 'americanfootball_nfl')
            event_id: The specific event ID
            regions: List of regions to get odds for
            markets: List of markets
            odds_format: Format for odds (default: OddsFormat.DECIMAL)
            date_format: Format for dates (default: DateFormat.ISO)
            use_retry: Use retry logic for transient failures (default: True)

        Returns:
            EventOdds object

        Raises:
            AuthenticationError: Invalid API key
            QuotaExceededError: API quota exceeded
            RateLimitError: Rate limit exceeded
            ServerError: Server error
        """
        params = {
            "regions": ",".join([r.value for r in regions]),
            "markets": ",".join([m.value for m in markets]),
            "oddsFormat": odds_format.value,
            "dateFormat": date_format.value,
        }

        if use_retry:
            response = self.http.get_with_retry(
                f"/sports/{sport_key}/events/{event_id}/odds", params
            )
        else:
            response = self.http.get(
                f"/sports/{sport_key}/events/{event_id}/odds", params
            )

        return self._parse_event_odds(response)

    def _parse_event_odds(self, data: dict) -> EventOdds:
        """
        Parse event odds from API response

        Args:
            data: Raw API response data

        Returns:
            Parsed EventOdds object
        """
        # Parse bookmakers
        bookmakers = []
        for bookmaker_data in data.get("bookmakers", []):
            markets = []
            for market_data in bookmaker_data.get("markets", []):
                outcomes = []
                for outcome_data in market_data.get("outcomes", []):
                    outcome = Outcome(
                        name=outcome_data["name"],
                        price=outcome_data["price"],
                        point=outcome_data.get("point"),
                    )
                    outcomes.append(outcome)

                market = MarketOdds(
                    key=market_data["key"],
                    last_update=datetime.fromisoformat(
                        market_data["last_update"].replace("Z", "+00:00")
                    ),
                    outcomes=outcomes,
                )
                markets.append(market)

            bookmaker = Bookmaker(
                key=bookmaker_data["key"],
                title=bookmaker_data["title"],
                last_update=datetime.fromisoformat(
                    bookmaker_data["last_update"].replace("Z", "+00:00")
                ),
                markets=markets,
            )
            bookmakers.append(bookmaker)

        return EventOdds(
            id=data["id"],
            sport_key=data["sport_key"],
            sport_title=data["sport_title"],
            commence_time=datetime.fromisoformat(
                data["commence_time"].replace("Z", "+00:00")
            ),
            home_team=data["home_team"],
            away_team=data["away_team"],
            bookmakers=bookmakers,
        )

    def normalize_events(
        self, raw_events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                    internal_market = self._map_market_key(provider_key)
                    if not internal_market:
                        # Ignore any market types we don't support yet.
                        continue

                    # Each 'outcomes' entry is a priced side of this market.
                    for out in mk.get("outcomes", []):
                        # Build a friendly 'side' label and minimal context.
                        side_label = self._build_side_label(out, internal_market)
                        context = self._build_context(out, internal_market)

                        offer = {
                            "bookmaker": book_title,
                            "market": internal_market,
                            "side": side_label,
                            "decimal_odds": float(out.get("price", 0)),
                            "context": context,
                        }
                        game["offers"].append(offer)

            games.append(game)

        return games

    def normalize_scores(
        self, raw_scores: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert provider scores JSON into a neutral shape.

        Output schema (list of games):
        [
          {
            "game_id": str,
            "commence_time": str,
            "home": str,
            "away": str,
            "completed": bool,
            "scores": {
              "home": int,
              "away": int
            }
          },
          ...
        ]
        """
        games: List[Dict[str, Any]] = []

        for score in raw_scores or []:
            game = {
                "game_id": score.get("id"),
                "commence_time": score.get("commence_time"),
                "home": score.get("home_team"),
                "away": score.get("away_team"),
                "completed": score.get("completed", False),
                "scores": {
                    "home": score.get("scores", [{}])[0].get("score", 0)
                    if score.get("scores")
                    else 0,
                    "away": score.get("scores", [{}])[1].get("score", 0)
                    if len(score.get("scores", [])) > 1
                    else 0,
                },
            }
            games.append(game)

        return games

    def _map_market_key(self, provider_key: str) -> Optional[str]:
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

    def _build_side_label(self, outcome: Dict[str, Any], market: str) -> str:
        """Build a friendly side label for display."""
        name = outcome.get("name", "")
        point = outcome.get("point", "")

        if market == "moneyline":
            return f"{name} ML"
        elif market == "spread":
            return f"{name} {point}"
        elif market == "total":
            return f"{name} {point}"
        else:
            return name

    def _build_context(self, outcome: Dict[str, Any], market: str) -> Dict[str, Any]:
        """Build minimal context for the agent/coordinator."""
        context = {
            "outcome_name": outcome.get("name", ""),
            "point": outcome.get("point"),
        }

        if market == "spread":
            context["spread"] = outcome.get("point")
        elif market == "total":
            context["total"] = outcome.get("point")

        return context
