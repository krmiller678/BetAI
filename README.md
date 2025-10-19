![made-with-python](https://img.shields.io/badge/Made_with-Python-yellow)

<!-- LOGO -->
<br />
<h1>
<p align="center">
  <img src="" alt="Logo", width="50%", height ="auto">
  <br>
</h1>
  <p align="center">
    BetAI
    <br />
    </p>
</p>
<p align="center">
  • <a href="#about-the-project">About The Project</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#manually-build">Build</a> •
  <a href="#usage">How to Use</a> •
  <a href="#planned-features">Planned Features</a> •
  <a href="#acknowledgements">Acknowledgements</a> •
</p>

<p align="center">

<img src="">
</p>

## About The Project
Agentic AI Application with Streamlit frontend implementing supervised machine learning models to predict win probabilities of live football wagers.

<a id="quick-start"></a>
## Quick Start 🚀

Requirements:
- Python 3.11 or later

Clone from GitHub:
```bash
git clone https://github.com/krmiller678/BetAI.git
cd BetAI
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the application:
```bash
streamlit run application.py
```

The dashboard will open in your browser at `http://localhost:8501`


<a id="manually-build"></a>
## Manually Build 🛠️

Requirements:
- Python 3.11 or later

Clone from GitHub:
```bash
git clone https://github.com/krmiller678/BetAI.git
cd BetAI
```

Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install Dependencies:
```bash
pip install -r requirements.txt
```

Run the Streamlit application:
```bash
streamlit run application.py
```

## Usage

### Dashboard Features

**Live Match Analysis**
- Enter match details including home/away teams and relevant features
- Input bookmaker odds to get AI-powered predictions
- View model probability vs implied odds probability
- Get recommended bet actions with confidence levels

**Betting Recommendations**
- **BET**: Model identifies positive expected value above threshold
- **NO BET**: Insufficient edge detected
- Recommended stake size calculated using Kelly Criterion
- Confidence score based on expected value magnitude

**Paper Trading Simulation**
- Simulate bet outcomes to track performance
- No real money involved - educational purposes only
- Track bankroll changes over time

**Performance Dashboard**
- Real-time bankroll curve visualization
- Win/loss statistics and distribution
- ROI and profit tracking
- Detailed bet history with all transactions

### Configuration Options

Access the sidebar to adjust:
- Initial bankroll amount
- Kelly fraction (risk management)
- Expected value threshold for bet recommendations

**NOTE:** This is a paper trading simulation for educational purposes. No real bets are placed.

## OddsAPI SDK

This project includes a custom-built Python SDK for The Odds API, providing a robust and type-safe interface for fetching live sports betting odds.

### Features

- ✅ **Type Safety**: Full type hints and dataclasses for all API responses
- ✅ **Rate Limiting**: Built-in token bucket algorithm to respect API limits
- ✅ **Retry Logic**: Exponential backoff with jitter for transient failures
- ✅ **Error Handling**: Custom exceptions with clear error messages
- ✅ **Thread Safe**: Safe for concurrent applications
- ✅ **Configurable**: Customizable rate limits and retry behavior

### Quick Example

```python
from oddsapi import OddsAPIClient, Region, Market, OddsFormat

# Initialize client
client = OddsAPIClient(api_key="your-api-key")

# Get available sports
sports = client.get_sports(active_only=True)

# Get NFL odds with all markets
odds = client.get_odds(
    sport_key="americanfootball_nfl",
    regions=[Region.US],
    markets=[Market.H2H, Market.SPREADS, Market.TOTALS],
    odds_format=OddsFormat.AMERICAN
)
```

### Installation

The SDK is included in this project and can be used directly:

```bash
# The SDK is located in odds-sdk/ directory
# Install in development mode if needed
cd odds-sdk
pip install -e .
```

### Documentation

For detailed documentation, API reference, and advanced usage examples, see the [OddsAPI SDK README](odds-sdk/README.md).

The SDK is designed as a reusable component and can be used independently of the main BetAI application.

## Planned Features
- [ ] Integration with live odds APIs
- [ ] Advanced model ensembling strategies
- [ ] Historical backtesting capabilities
- [ ] Calibration plots and Brier score analysis
- [ ] Multi-league support
- [ ] Real-time model retraining pipeline

## Acknowledgements
- [Streamlit](https://streamlit.io/) - For the amazing web framework
- [scikit-learn](https://scikit-learn.org/) - For machine learning tools
- [Plotly](https://plotly.com/) - For interactive visualizations
