"""
Tests for the OddsAPIClient
"""

import json
import pytest
from unittest.mock import patch
from datetime import datetime

from oddsapi import (
    OddsAPIClient,
    Region,
    Market,
    OddsFormat,
    Sport,
    EventOdds,
    AuthenticationError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)


class TestOddsAPIClient:
    """Test cases for OddsAPIClient"""

    def setup_method(self):
        """Set up test fixtures"""
        self.client = OddsAPIClient(api_key="test-key")
        with open("tests/fixtures/sports.json") as f:
            self.sports_data = json.load(f)
        with open("tests/fixtures/odds.json") as f:
            self.odds_data = json.load(f)

    def test_init(self):
        """Test client initialization"""
        client = OddsAPIClient(api_key="test-key")
        assert client.http.api_key == "test-key"
        assert client.http.base_url == "https://api.the-odds-api.com/v4"
        assert client.http.rate_limiter.requests_per_minute == 30

        # Test custom parameters
        client = OddsAPIClient(
            api_key="test-key",
            base_url="https://custom.api.com",
            requests_per_minute=30,
        )
        assert client.http.base_url == "https://custom.api.com"
        assert client.http.rate_limiter.requests_per_minute == 30

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_get_sports_with_retry(self, mock_get):
        """Test get_sports with retry enabled"""
        mock_get.return_value = self.sports_data

        sports = self.client.get_sports(active_only=True, use_retry=True)

        assert len(sports) == 3
        assert isinstance(sports[0], Sport)
        assert sports[0].key == "americanfootball_nfl"
        assert sports[0].title == "NFL"
        assert sports[0].active is True

        mock_get.assert_called_once_with("/sports", {"active": "true"})

    @patch("oddsapi.client.HTTPClient.get")
    def test_get_sports_without_retry(self, mock_get):
        """Test get_sports with retry disabled"""
        mock_get.return_value = self.sports_data

        sports = self.client.get_sports(active_only=False, use_retry=False)

        assert len(sports) == 3
        mock_get.assert_called_once_with("/sports", {})

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_get_odds(self, mock_get):
        """Test get_odds method"""
        mock_get.return_value = self.odds_data

        odds = self.client.get_odds(
            sport_key="americanfootball_nfl",
            regions=[Region.US],
            markets=[Market.H2H, Market.SPREADS],
            odds_format=OddsFormat.AMERICAN,
        )

        assert len(odds) == 1
        assert isinstance(odds[0], EventOdds)
        assert odds[0].sport_key == "americanfootball_nfl"
        assert odds[0].home_team == "Kansas City Chiefs"
        assert odds[0].away_team == "Buffalo Bills"
        assert len(odds[0].bookmakers) == 1

        # Check the call parameters
        expected_params = {
            "regions": "us",
            "markets": "h2h,spreads",
            "oddsFormat": "american",
            "dateFormat": "iso",
        }
        mock_get.assert_called_once_with(
            "/sports/americanfootball_nfl/odds", expected_params
        )

    @patch("oddsapi.client.HTTPClient.get")
    def test_get_odds_with_optional_params(self, mock_get):
        """Test get_odds with optional parameters"""
        mock_get.return_value = self.odds_data

        start_time = datetime(2024, 1, 15, 18, 0, 0)
        end_time = datetime(2024, 1, 15, 22, 0, 0)

        self.client.get_odds(
            sport_key="americanfootball_nfl",
            regions=[Region.US, Region.UK],
            markets=[Market.H2H],
            event_ids=["event1", "event2"],
            bookmakers=["draftkings", "fanduel"],
            commence_time_from=start_time,
            commence_time_to=end_time,
            use_retry=False,
        )

        expected_params = {
            "regions": "us,uk",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
            "eventIds": "event1,event2",
            "bookmakers": "draftkings,fanduel",
            "commenceTimeFrom": "2024-01-15T18:00:00",
            "commenceTimeTo": "2024-01-15T22:00:00",
        }
        mock_get.assert_called_once_with(
            "/sports/americanfootball_nfl/odds", expected_params
        )

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_get_event_odds(self, mock_get):
        """Test get_event_odds method"""
        mock_get.return_value = self.odds_data[0]  # Single event

        event_odds = self.client.get_event_odds(
            sport_key="americanfootball_nfl",
            event_id="a512a48a58c4329048174217b2cc7ce0",
            regions=[Region.US],
            markets=[Market.H2H, Market.TOTALS],
        )

        assert isinstance(event_odds, EventOdds)
        assert event_odds.id == "a512a48a58c4329048174217b2cc7ce0"
        assert event_odds.sport_key == "americanfootball_nfl"

        expected_params = {
            "regions": "us",
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        }
        mock_get.assert_called_once_with(
            "/sports/americanfootball_nfl/events/a512a48a58c4329048174217b2cc7ce0/odds",
            expected_params,
        )

    def test_parse_event_odds(self):
        """Test _parse_event_odds method"""
        event_data = self.odds_data[0]
        event_odds = self.client._parse_event_odds(event_data)

        assert isinstance(event_odds, EventOdds)
        assert event_odds.id == "a512a48a58c4329048174217b2cc7ce0"
        assert event_odds.sport_key == "americanfootball_nfl"
        assert event_odds.home_team == "Kansas City Chiefs"
        assert event_odds.away_team == "Buffalo Bills"

        # Check bookmaker
        assert len(event_odds.bookmakers) == 1
        bookmaker = event_odds.bookmakers[0]
        assert bookmaker.key == "draftkings"
        assert bookmaker.title == "DraftKings"

        # Check markets
        assert len(bookmaker.markets) == 3

        # Check H2H market
        h2h_market = bookmaker.markets[0]
        assert h2h_market.key == "h2h"
        assert len(h2h_market.outcomes) == 2
        assert h2h_market.outcomes[0].name == "Kansas City Chiefs"
        assert h2h_market.outcomes[0].price == 1.85

        # Check spreads market
        spreads_market = bookmaker.markets[1]
        assert spreads_market.key == "spreads"
        assert spreads_market.outcomes[0].point == -3.5

        # Check totals market
        totals_market = bookmaker.markets[2]
        assert totals_market.key == "totals"
        assert totals_market.outcomes[0].point == 48.5


class TestErrorHandling:
    """Test error handling scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.client = OddsAPIClient(api_key="test-key")

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_authentication_error(self, mock_get):
        """Test authentication error handling"""
        mock_get.side_effect = AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError):
            self.client.get_sports()

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_quota_exceeded_error(self, mock_get):
        """Test quota exceeded error handling"""
        mock_get.side_effect = QuotaExceededError("API quota exceeded")

        with pytest.raises(QuotaExceededError):
            self.client.get_sports()

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_rate_limit_error(self, mock_get):
        """Test rate limit error handling"""
        mock_get.side_effect = RateLimitError("Rate limit exceeded", retry_after=60)

        with pytest.raises(RateLimitError) as exc_info:
            self.client.get_sports()

        assert exc_info.value.retry_after == 60

    @patch("oddsapi.client.HTTPClient.get_with_retry")
    def test_server_error(self, mock_get):
        """Test server error handling"""
        mock_get.side_effect = ServerError("Server error: 500")

        with pytest.raises(ServerError):
            self.client.get_sports()
