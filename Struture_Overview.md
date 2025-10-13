BetAI/
│
├── backend/                           # All server-side logic (API, models, data, business logic)
│   ├── api/                           # FastAPI or Flask REST API service
│   │   ├── main.py                    # App entrypoint (FastAPI)
│   │   ├── routes/                    # Organized API endpoints
│   │   │   ├── bets.py
│   │   │   ├── metrics.py
│   │   │   └── models.py
│   │   ├── db/                        # Database layer
│   │   │   ├── models.py              # SQLAlchemy ORM models
│   │   │   ├── crud.py                # Create/Read/Update/Delete functions
│   │   │   ├── schema.py              # Pydantic validation schemas
│   │   │   ├── alembic/               # Migrations folder
│   │   │   └── __init__.py
│   │   ├── services/                  # API-level service logic
│   │   │   └── bets_service.py
│   │   ├── dependencies/              # FastAPI dependencies (auth, db session, etc.)
│   │   ├── settings.py                # loads env vars / config
│   │   ├── logging_config.py          # standard logging setup
│   │   ├── __init__.py
│   │   └── Dockerfile                 # optional container for API
│   │
│   ├── core/                          # Core ML and agent logic (pure Python library)
│   │   ├── betai/                     # installable package: "from betai.agent import ..."
│   │   │   ├── __init__.py
|   |   ├── agents/                    # agent logic (brain/coach)
|   |   │   ├── __init__.py
|   |   │   ├── agent_v1.py            # legacy version
|   |   │   ├── agent_v2.py            # new structured one
│   │   │   ├── coordinators/          # market-specific strategy modules
│   │   │   │   ├── moneyline.py
│   │   │   │   ├── spread.py
│   │   │   │   └── total.py
│   │   │   ├── models/                # ML model loaders + utils
│   │   │   │   ├── logistic_regression.py
│   │   │   │   ├── random_forest.py
│   │   │   │   ├── naive_bayes.py
│   │   │   │   └── model_utils.py
│   │   │   ├── registry/              # model registry, features, metadata
│   │   │   │   ├── registry.json
│   │   │   │   └── moneyline_lr_features.txt
│   │   │   └── utils/                 # common math/stats/helper functions
│   │   ├── tests/                     # unit tests for betai core
│   │   ├── pyproject.toml             # allows installing betai as a package
│   │   └── setup.cfg
│   │
│   ├── data/                          # local or remote datasets (if applicable)
│   │   ├── raw/
│   │   ├── processed/
│   │   ├── etl/                       # data cleaning, merging, or collection scripts
│   │   │   └── nfl_data_loader.py
│   │   └── README.md
│   │
│   ├── trained_models/                # versioned model artifacts (.pkl, .onnx, etc.)
│   │   ├── moneyline/
│   │   │   ├── lr_model.pkl
│   │   │   ├── rf_model.pkl
│   │   │   └── features.txt
│   │   └── README.md
│   │
│   ├── notebooks/                     # research, exploration, experiments
│   │   ├── EDA.ipynb
│   │   └── model_training.ipynb
│   │
│   ├── tests/                         # integration tests for backend services
│   └── README.md
│
├── frontend/                          # User interface(s)
│   ├── streamlit_app/                 # Streamlit UI (modular BetAI frontend)
│   │   ├── app.py                     # Main entry point / router for all views
│   │   ├── application.py             # Legacy UI
│   │   │
│   │   ├── views/                     # Individual Streamlit views (tabs)
│   │   │   ├── live_board.py          # Displays live games, odds, and team logos
│   │   │   ├── paper_trading.py       # Paper trading dashboard (legacy layout + dropdowns)
│   │   │   ├── recommendations.py     # AI-driven bet recommendations
│   │   │   ├── open_bets.py           # Active bets with live updates
│   │   │   └── history.py             # Bet history and performance analytics
│   │   │
│   │   ├── lib/                       # Shared helper modules
│   │   │   ├── __init__.py            # Marks directory as a Python package
│   │   │   ├── api.py                 # Handles external API calls (The Odds API, etc.)
│   │   │   ├── session_state.py       # Centralized session state management
│   │   │   └── utils.py               # Common utilities (e.g., logo lookups, formatting)
│   │   │
│   │   ├── assets/                    # Static resources for the UI
│   │   │   └── team-logos/            # Local team logo images (e.g., nfl_det.png, nba_bos.png)
│   │   │
│   │   ├── .streamlit/                # Streamlit configuration (theme, server, etc.)
│   │   │   └── config.toml            # Custom theme and server options
│   │   │
│   │   ├── requirements.txt           # Streamlit dependencies and helper libraries
│   │   └── README.md                  # Frontend usage guide, setup, and structure notes
│   │
│   └── web_app/                       # future production frontend (React/Next.js)
│       ├── src/
│       ├── package.json
│       ├── tsconfig.json
│       └── README.md
│
├── scripts/                           # helper scripts
│   ├── setup.sh                       # create venv, install deps
│   ├── run.sh                         # run Streamlit app
│   ├── train_models.sh                # retrain + save models
│   └── seed_db.sh                     # load initial DB data
│
├── docker-compose.yml                 # orchestrate db/api/ui
├── requirements.txt                   # dev-only Python deps
├── .env.example                       # environment variable template
├── .gitignore
└── README.md                          # polished project overview