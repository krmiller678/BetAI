"""
Main client for The Odds API
"""

from typing import List, Optional
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
    ):
        """
        Initialize the Odds API client

        Args:
            api_key: Your Odds API key
            base_url: Base URL for the API (default: https://api.the-odds-api.com/v4)
            requests_per_minute: Rate limit for requests (default: 30 - conservative)
        """
        self.http = HTTPClient(api_key, base_url, requests_per_minute)

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
