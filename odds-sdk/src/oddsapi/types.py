"""
Type definitions and enums for The Odds API responses
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


class Region(str, Enum):
    """Available regions for odds data"""

    US = "us"
    US2 = "us2"
    UK = "uk"
    AU = "au"
    EU = "eu"


class Market(str, Enum):
    """Available betting markets"""

    H2H = "h2h"
    SPREADS = "spreads"
    TOTALS = "totals"
    OUTRIGHTS = "outrights"


class OddsFormat(str, Enum):
    """Available odds formats"""

    DECIMAL = "decimal"
    AMERICAN = "american"


class DateFormat(str, Enum):
    """Available date formats"""

    ISO = "iso"
    UNIX = "unix"


@dataclass
class Sport:
    """Represents a sport available in The Odds API"""

    key: str
    group: str
    title: str
    description: str
    active: bool
    has_outrights: bool


@dataclass
class Outcome:
    """Represents a betting outcome with odds"""

    name: str
    price: float
    point: Optional[float] = None


@dataclass
class MarketOdds:
    """Represents odds for a specific market"""

    key: str
    last_update: datetime
    outcomes: List[Outcome]


@dataclass
class Bookmaker:
    """Represents a bookmaker with their odds"""

    key: str
    title: str
    last_update: datetime
    markets: List[MarketOdds]


@dataclass
class EventOdds:
    """Represents odds for a specific event across multiple bookmakers"""

    id: str
    sport_key: str
    sport_title: str
    commence_time: datetime
    home_team: str
    away_team: str
    bookmakers: List[Bookmaker]
