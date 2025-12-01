# 🧭 BetAI Backend — Final Architecture & Developer Guide

The backend of **BetAI** powers all AI logic, machine learning models, probability estimation, and decision-making.  
It contains:

- Supervised ML models (moneyline + spread)  
- Coordinators that convert sportsbook offers → ML features  
- BettingAgent that computes EV + Kelly staking  
- Integrations for **ESPN Scoreboard** and **The Odds API**  
- Data normalization and feature registry  
- Training scripts to regenerate all model files  

The frontend Streamlit UI imports backend modules **directly**, with no networking layer required.

---

# 🗂️ Final Backend Folder Structure

```
backend/
└── core/
    └── betai/
        ├── agents/                                     # Agent "brain"
        │   ├── __init__.py
        │   └── agent_v2.py                             # Main BettingAgent (EV, Kelly, routing)
        │
        ├── coordinators/                               # Market-specific feature builders + routing
        │   ├── __init__.py
        │   ├── moneyline.py                            # MoneylineCoordinator
        │   ├── spread.py                               # SpreadCoordinator
        │   └── total.py                                # Experimental (not used in final app)
        │
        ├── integrations/                               # External data integrations
        │   ├── __init__.py
        │   ├── odds_api.py                             # Wrapper around local odds-sdk (The Odds API)
        │   ├── pbp_api.py                              # ESPN scoreboard + metadata
        │   └── results_api.py                          # Hooks for auto-settlement (not fully used)
        │
        ├── models/                                     # Machine learning models + training
        │   ├── __init__.py
        │   │
        │   ├── moneyline/                              # Moneyline win-probability models
        │   │   ├── __init__.py
        │   │   ├── trained_models/                     # Git-ignored — regenerated during setup
        │   │   │   ├── lr_moneyline.pkl
        │   │   │   ├── lr_moneyline_features.txt
        │   │   │   ├── nb_moneyline.pkl
        │   │   │   ├── nb_moneyline_features.txt
        │   │   │   ├── rf_moneyline.pkl
        │   │   │   └── rf_moneyline_features.txt
        │   │   ├── logistic_regression_moneyline.py
        │   │   ├── naive_bayes_moneyline.py
        │   │   ├── random_forest_moneyline.py
        │   │   ├── moneyline_ensemble.py               # Combines LR + NB + RF
        │   │   └── models_train_moneyline.py           # Offline training script
        │   │
        │   ├── spread/                                 # Spread-cover probability models
        │   │   ├── __init__.py
        │   │   ├── trained_models/                     # Git-ignored — regenerated during setup
        │   │   │   ├── lr_spread.pkl
        │   │   │   ├── lr_spread_features.txt
        │   │   │   ├── nb_spread.pkl
        │   │   │   ├── nb_spread_features.txt
        │   │   │   ├── rf_spread.pkl
        │   │   │   └── rf_spread_features.txt
        │   │   ├── logistic_regression_spread.py
        │   │   ├── naive_bayes_spread.py
        │   │   ├── random_forest_spread.py
        │   │   └── spread_ensemble.py                  # Combines LR + NB + RF
        │   │
        │   ├── total/                                  # Analysis utilities (not for UI)
        │   │   ├── __init__.py
        │   │   └── tools/
        │   │       ├── agent_eval.py
        │   │       ├── model_utils.py
        │   │       ├── moneyline_eval.py
        │   │       └── spread_eval.py
        │   │
        │   ├── abbreviations.py                        # NFL team abbreviation lookup
        │   └── nflreadpy_features.txt                  # Full feature list extracted from nflreadpy
        │
        ├── __init__.py
        └── README.md
```

---

# ⚙️ Backend Overview

The backend is composed of four clean layers:

1. **Integrations Layer**  
   Talks to external APIs (OddsAPI SDK + ESPN) and normalizes raw data.

2. **Models Layer**  
   Trains supervised ML models + loads them for inference.

3. **Coordinators Layer**  
   Turns sportsbook offers → ML-ready feature vectors → model predictions.

4. **BettingAgent Layer**  
   Computes expected value (EV), implied probability, Kelly stake sizing,  
   and produces `"BET"` / `"PASS"` recommendations.

The architecture is intentionally modular to support future reinforcement learning, new markets, more sports, or cloud deployment.

---

# 1️⃣ Integrations Layer

## 🔗 OddsAPI (via odds-sdk)

The local odds-sdk provides a clean, typed wrapper over The Odds API.

Used for:
- Moneyline odds  
- Spread odds  
- Multi-bookmaker offers  
- Normalized game IDs  
- Odds format conversions  

Imported as:

```python
from oddsapi import OddsAPIClient, Region, Market, OddsFormat
```

All odds shown in the UI come through this path.

---

## 🏈 ESPN Scoreboard (pbp_api.py)

Provides:
- Team names + logos  
- Scores  
- Period / clock  
- Game state (PRE, IN, POST)  
- ESPN `event_id`  
- Basic team stats (passing, rushing, TOs, etc.)  

UI → Scoreboard View uses this for:

- Game cards  
- Headers in Game Details  
- Live scoring  
- Stat summaries  

---

# 2️⃣ ML Models Layer

Stored under:

```
backend/core/betai/models/{moneyline,spread}
```

## Supported Models

Both Moneyline and Spread use:

- **Logistic Regression**
- **Random Forest**
- **Naive Bayes**

## Features

Sourced from:
- nflreadpy  
- play-by-play statistics  
- team performance aggregates  

Feature files (`*_features.txt`) ensure all models use the same ordered inputs.

## Ensemble Logic

Each prediction uses:

```
p_model = (p_rf + p_nb + p_lr) / 3
```

This smooths variance across model families.

## Training Pipeline

Scripts:

```
models_train_moneyline.py
models_train_spread.py
```

Executed automatically by:

```
scripts/train_models.sh
```

Models are output into:

```
models/moneyline/trained_models/
models/spread/trained_models/
```

These directories are **ignored by git**, so every user generates fresh models.

---

# 3️⃣ Coordinators Layer

Converts an offer into the correct model features.

### MoneylineCoordinator
- Builds feature row using (home stats, away stats, context metadata)
- Calls LR / NB / RF models
- Applies ensemble
- Returns `{"p_model", "model_name"}`

### SpreadCoordinator
- Same structure, but includes point spread adjustments

### TotalCoordinator
Present but unused — totals removed from final UI.

---

# 4️⃣ BettingAgent

Location:

```
agents/agent_v2.py
```

The BettingAgent is the "brain" of BetAI.

### Responsibilities

- Choose correct coordinator (moneyline or spread)
- Compute **implied probability** from sportsbook odds
- Compute **EV**  
- Compute **Kelly stake**:

```
stake = bankroll * kelly_fraction
```

- Output a **normalized recommendation**
- Manage **open bets** and results (used by frontend session_state)

### Output Schema

```python
{
  "id": "...",
  "market": "moneyline",
  "side": "home",
  "ev": 0.058,
  "stake": 22.40,
  "p_model": 0.63,
  "p_implied": 0.57,
  "decision": "BET",
  "context": {...}
}
```

---

# 🛰️ Frontend Integration

Frontend accesses backend modules *directly* through imports.

| UI Action | Backend Layer |
|----------|----------------|
| Fetch Odds | odds-sdk via `lib/api.py` |
| Fetch Scoreboard | `integrations/pbp_api` |
| Link games | `api_linker.py` |
| Evaluate bet | `BettingAgent.make_recommendation()` |
| Place Paper Bet | BettingAgent → session_state |
| Settle Bet | `agent.record_result()` |

No HTTP servers, no serialization — everything stays in Python.

---

# 🧪 Training + Setup Automation

The entire backend ML pipeline rebuilds automatically during setup:

```
scripts/train_models.sh
```

setup.sh handles:

1. Installing odds-sdk  
2. Installing dependencies  
3. Creating `.env`  
4. Training ML models automatically  

No user intervention required besides supplying `ODDS_API_KEY`.

---

# 🚧 Backend Limitations

- No auto-settlement using ESPN scores  
- No persistent DB (session_state only)  
- In-game ML not implemented  
- Local-only deployment  
- No reinforcement learning agent (supervised only)

---

# 📌 Summary

The backend provides a complete, modular AI pipeline:

- ESPN + OddsAPI integration  
- Model training + prediction  
- Moneyline + spread coordinators  
- Ensemble ML models  
- EV + Kelly decision engine  
- Paper trading infrastructure  

It serves as the core intelligence powering the BetAI application and is ready for future expansion into RL, cloud microservices, or multi-sport betting intelligence.