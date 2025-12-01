# BetAI — Project Structure Overview 

High–level layout of the BetAI repository and what each piece does.

```text
BetAI/
│
├── backend/                               # All core AI, models, and integrations
│   └── core/
│       └── betai/
│           ├── agents/                                     # Agent "brain" that decides BET vs NO BET
│           │   ├── __init__.py
│           │   └── agent_v2.py                             # Main BettingAgent used by the Streamlit app
│           │
│           ├── coordinators/                               # Market-specific coordinators
│           │   ├── __init__.py
│           │   ├── moneyline.py                            # Moneyline coordinator (uses moneyline models)
│           │   ├── spread.py                               # Spread coordinator (uses spread models)
│           │   └── total.py                                # Stub / experimental total-market logic
│           │
│           ├── integrations/                               # External data integrations
│           │   ├── __init__.py
│           │   ├── odds_api.py                             # Wrapper around the local odds-sdk (The Odds API)
│           │   ├── pbp_api.py                              # ESPN scoreboard + summary APIs
│           │   └── results_api.py                          # Hooks for settlement / results (not fully used)
│           │
│           ├── models/                                     # ML models + training scripts
│           │   ├── __init__.py
│           │   │
│           │   ├── moneyline/                              # Moneyline win-probability models
│           │   │   ├── __init__.py
│           │   │   ├── trained_models/
│           │   │   │   ├── lr_moneyline.pkl
│           │   │   │   ├── lr_moneyline_features.txt
│           │   │   │   ├── nb_moneyline.pkl
│           │   │   │   ├── nb_moneyline_features.txt
│           │   │   │   ├── rf_moneyline.pkl
│           │   │   │   └── rf_moneyline_features.txt
│           │   │   ├── logistic_regression_moneyline.py
│           │   │   ├── naive_bayes_moneyline.py
│           │   │   ├── random_forest_moneyline.py
│           │   │   ├── moneyline_ensemble.py               # Combines LR / NB / RF predictions
│           │   │   └── models_train_moneyline.py           # Script to (re)train moneyline models
│           │   │
│           │   ├── spread/                                 # Spread-cover probability models
│           │   │   ├── __init__.py
│           │   │   ├── trained_models/
│           │   │   │   ├── lr_spread.pkl
│           │   │   │   ├── lr_spread_features.txt
│           │   │   │   ├── nb_spread.pkl
│           │   │   │   ├── nb_spread_features.txt
│           │   │   │   ├── rf_spread.pkl
│           │   │   │   └── rf_spread_features.txt
│           │   │   ├── logistic_regression_spread.py
│           │   │   ├── naive_bayes_spread.py
│           │   │   ├── random_forest_spread.py
│           │   │   └── spread_ensemble.py                  # Combines LR / NB / RF predictions
│           │   │
│           │   ├── total/                                  # Tools to evaluate models
│           │   │   ├── __init__.py
│           │   │   └── tools/
│           │   │       ├── agent_eval.py
│           │   │       ├── model_utils.py
│           │   │       ├── moneyline_eval.py
│           │   │       └── spread_eval.py
│           │   │
│           │   ├── abbreviations.py                        # Team abbreviation lookups (NFL)
│           │   └── nflreadpy_features.txt                  # Feature list extracted from nflreadpy dataset
│           │
│           ├── __init__.py
│           └── README.md                                   # Backend-focused notes / docs
│
├── frontend/                                               # Streamlit UI (what users actually see)
│   └── streamlit_app/
│       ├── app.py                                          # Main app router (tabs + layout)
│       │
│       ├── assets/                                         # Static assets (logos, images, etc.)
│       │   └── team-logos/                                 # NFL team logos used in UI 
│       │
│       ├── lib/                                            # Shared helpers for the Streamlit layer
│       │   ├── __init__.py
│       │   ├── api.py                                      # Frontend odds/scoreboard glue helpers
│       │   ├── api_linker.py                               # Links ESPN event_id ↔ OddsAPI game_id
│       │   ├── session_state.py                            # Centralized session_state init + accessors
│       │   └── utils.py                                    # Misc utilities (logos, formatting, etc.)
│       │
│       ├── views/                                          # Individual Streamlit “tabs” / views
│       │   ├── __init__.py
│       │   ├── live_board.py                               # Live Odds tab (logo strip + offers)
│       │   ├── paper_trading.py                            # Paper Trading tab (place/manage bets)
│       │   ├── recommendations.py                          # Recommendations tab (recent EV suggestions)
│       │   ├── open_bets.py                                # Open Bets tab (active paper trades)
│       │   ├── history.py                                  # History tab (bankroll curve + stats)
│       │   ├── sidebar.py                                  # Sidebar controls (sport, EV threshold, Kelly)
│       │   │
│       │   └── scoreboard/                                 # Scoreboard tab + detail view
│       │       ├── __init__.py
│       │       ├── scorecard.py                            # Grid of games with logos/scores + Details buttons
│       │       ├── scorecard_css.py                        # CSS injection helper for scorecard styling
│       │       ├── game_details.py                         # Single-game view (stats + odds + Evaluate/Place)
│       │       └── scoreboard_router.py                    # Router between grid view and details view
│       │
│       └── tools/                                          # Old prototypes / playground apps (not used in final)
│           ├── app_v1.py
│           ├── app_v2.py
│           ├── scoreboard_tester.py
│           └── scoreboard_tester_v2.py
│
├── odds-sdk/                                               # Local editable SDK for The Odds API
│   ├── pyproject.toml                                      # Defines the oddsapi-sdk Python package
│   ├── README.md
│   ├── src/
│   │   └── oddsapi/
│   │       ├── __init__.py                                 # Exposes OddsAPIClient and type helpers
│   │       ├── client.py                                   # Typed OddsAPIClient used by backend.core
│   │       ├── http.py                                     # Low-level HTTP client with caching / retry
│   │       ├── types.py                                    # Typed models for sports, events, markets, odds
│   │       └── errors.py                                   # Custom exception types
│   │
│   └── tests/                                              # Unit tests for the SDK (from teammate’s work)
│       ├── __init__.py
│       ├── fixtures/
│       │   ├── odds.json
│       │   └── sports.json
│       ├── test_client.py
│       └── test_types.py
│
├── scripts/                                                # Helper scripts (developer + TA entry points)
│   ├── setup.sh                                            # Create venv, install deps, install odds-sdk, write .env
│   ├── run.sh                                              # Activate venv + run Streamlit app with correct PYTHONPATH
│   └── train_models.sh                                     # Retrain moneyline + spread models (saves .pkl files)
│
├── .env                                                    # Local environment configuration (ignored by git)
├── requirements.txt                                        # Project-wide Python dependencies
├── README.md                                               # Top-level project description + quickstart
├── LICENSE
└── .gitignore