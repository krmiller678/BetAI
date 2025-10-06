# OddsAPI SDK

A minimal, well-typed Python SDK for The Odds API that provides clean abstractions for the core endpoints with proper error handling and type safety.

## Features

- ✅ **Type Safety**: Full type hints and dataclasses for all models
- ✅ **Rate Limiting**: Built-in token bucket algorithm to respect API limits
- ✅ **Retry Logic**: Exponential backoff with jitter for transient failures
- ✅ **Error Handling**: Custom exceptions with clear error messages
- ✅ **Simple API**: Intuitive method names and parameter handling
- ✅ **Configurable**: Optional retry and rate limiting for different use cases

## Installation

```bash
pip install -e .
```

## Quick Start

```python
from oddsapi import OddsAPIClient, Region, Market, OddsFormat

# Initialize client (uses conservative 30 requests/minute default)
client = OddsAPIClient(api_key="your-api-key")

# Or customize rate limiting if needed
client = OddsAPIClient(
    api_key="your-api-key",
    requests_per_minute=50  # Higher rate limit
)

# Get available sports (with retry by default)
sports = client.get_sports(active_only=True)
print(f"Available sports: {[sport.title for sport in sports]}")

# Get NFL odds with all three markets
nfl_odds = client.get_odds(
    sport_key="americanfootball_nfl",
    regions=[Region.US],
    markets=[Market.H2H, Market.SPREADS, Market.TOTALS],
    odds_format=OddsFormat.AMERICAN
)

# Get specific event odds (disable retry for faster response)
event_odds = client.get_event_odds(
    sport_key="americanfootball_nfl",
    event_id="event-id-here",
    regions=[Region.US],
    markets=[Market.H2H],
    use_retry=False  # Skip retry for single requests
)
```

## Error Handling

```python
from oddsapi import RateLimitError, QuotaExceededError, AuthenticationError

try:
    odds = client.get_odds(
        sport_key="americanfootball_nfl",
        regions=[Region.US],
        markets=[Market.H2H]
    )
    print(f"Found {len(odds)} events")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except QuotaExceededError:
    print("API quota exceeded. Upgrade your plan.")
except AuthenticationError:
    print("Invalid API key.")
```

## API Reference

### OddsAPIClient

#### `__init__(api_key, base_url, requests_per_minute)`
Initialize the client with your API key and optional configuration.

#### `get_sports(active_only=True, use_retry=True)`
Get list of available sports.

#### `get_odds(sport_key, regions, markets=None, ...)`
Get odds for a specific sport with various filtering options.

#### `get_event_odds(sport_key, event_id, regions, markets, ...)`
Get odds for a specific event.

### Types

- **Region**: US, UK, AU, EU, US2
- **Market**: H2H, SPREADS, TOTALS, OUTRIGHTS
- **OddsFormat**: DECIMAL, AMERICAN
- **DateFormat**: ISO, UNIX

### Data Models

- **Sport**: Sport information
- **EventOdds**: Event with odds from multiple bookmakers
- **Bookmaker**: Bookmaker with their odds
- **MarketOdds**: Odds for a specific market
- **Outcome**: Individual betting outcome with price

## Development

### Setup

```bash
# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Code formatting
black src/ tests/
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=oddsapi

# Run specific test file
pytest tests/test_client.py
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions, please open an issue on GitHub.
