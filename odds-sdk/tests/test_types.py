"""
Tests for type definitions and enums
"""

from datetime import datetime

from oddsapi import (
    Region,
    Market,
    OddsFormat,
    DateFormat,
    Sport,
    Outcome,
    MarketOdds,
    Bookmaker,
    EventOdds,
)


class TestEnums:
    """Test enum classes"""

    def test_region_enum(self):
        """Test Region enum values"""
        assert Region.US == "us"
        assert Region.UK == "uk"
        assert Region.AU == "au"
        assert Region.EU == "eu"
        assert Region.US2 == "us2"

    def test_market_enum(self):
        """Test Market enum values"""
        assert Market.H2H == "h2h"
        assert Market.SPREADS == "spreads"
        assert Market.TOTALS == "totals"
        assert Market.OUTRIGHTS == "outrights"

    def test_odds_format_enum(self):
        """Test OddsFormat enum values"""
        assert OddsFormat.DECIMAL == "decimal"
        assert OddsFormat.AMERICAN == "american"

    def test_date_format_enum(self):
        """Test DateFormat enum values"""
        assert DateFormat.ISO == "iso"
        assert DateFormat.UNIX == "unix"


class TestDataClasses:
    """Test dataclass definitions"""

    def test_sport_dataclass(self):
        """Test Sport dataclass"""
        sport = Sport(
            key="americanfootball_nfl",
            group="American Football",
            title="NFL",
            description="US Football",
            active=True,
            has_outrights=False,
        )

        assert sport.key == "americanfootball_nfl"
        assert sport.group == "American Football"
        assert sport.title == "NFL"
        assert sport.description == "US Football"
        assert sport.active is True
        assert sport.has_outrights is False

    def test_outcome_dataclass(self):
        """Test Outcome dataclass"""
        # Test with point
        outcome_with_point = Outcome(name="Kansas City Chiefs", price=1.85, point=-3.5)

        assert outcome_with_point.name == "Kansas City Chiefs"
        assert outcome_with_point.price == 1.85
        assert outcome_with_point.point == -3.5

        # Test without point
        outcome_without_point = Outcome(name="Kansas City Chiefs", price=1.85)

        assert outcome_without_point.name == "Kansas City Chiefs"
        assert outcome_without_point.price == 1.85
        assert outcome_without_point.point is None

    def test_market_odds_dataclass(self):
        """Test MarketOdds dataclass"""
        outcome1 = Outcome(name="Team A", price=1.85)
        outcome2 = Outcome(name="Team B", price=1.95)

        market_odds = MarketOdds(
            key="h2h",
            last_update=datetime(2024, 1, 15, 19, 30, 0),
            outcomes=[outcome1, outcome2],
        )

        assert market_odds.key == "h2h"
        assert market_odds.last_update == datetime(2024, 1, 15, 19, 30, 0)
        assert len(market_odds.outcomes) == 2
        assert market_odds.outcomes[0].name == "Team A"
        assert market_odds.outcomes[1].name == "Team B"

    def test_bookmaker_dataclass(self):
        """Test Bookmaker dataclass"""
        outcome = Outcome(name="Team A", price=1.85)
        market_odds = MarketOdds(
            key="h2h", last_update=datetime(2024, 1, 15, 19, 30, 0), outcomes=[outcome]
        )

        bookmaker = Bookmaker(
            key="draftkings",
            title="DraftKings",
            last_update=datetime(2024, 1, 15, 19, 30, 0),
            markets=[market_odds],
        )

        assert bookmaker.key == "draftkings"
        assert bookmaker.title == "DraftKings"
        assert bookmaker.last_update == datetime(2024, 1, 15, 19, 30, 0)
        assert len(bookmaker.markets) == 1
        assert bookmaker.markets[0].key == "h2h"

    def test_event_odds_dataclass(self):
        """Test EventOdds dataclass"""
        outcome = Outcome(name="Team A", price=1.85)
        market_odds = MarketOdds(
            key="h2h", last_update=datetime(2024, 1, 15, 19, 30, 0), outcomes=[outcome]
        )
        bookmaker = Bookmaker(
            key="draftkings",
            title="DraftKings",
            last_update=datetime(2024, 1, 15, 19, 30, 0),
            markets=[market_odds],
        )

        event_odds = EventOdds(
            id="event123",
            sport_key="americanfootball_nfl",
            sport_title="NFL",
            commence_time=datetime(2024, 1, 15, 20, 0, 0),
            home_team="Kansas City Chiefs",
            away_team="Buffalo Bills",
            bookmakers=[bookmaker],
        )

        assert event_odds.id == "event123"
        assert event_odds.sport_key == "americanfootball_nfl"
        assert event_odds.sport_title == "NFL"
        assert event_odds.commence_time == datetime(2024, 1, 15, 20, 0, 0)
        assert event_odds.home_team == "Kansas City Chiefs"
        assert event_odds.away_team == "Buffalo Bills"
        assert len(event_odds.bookmakers) == 1
        assert event_odds.bookmakers[0].key == "draftkings"
