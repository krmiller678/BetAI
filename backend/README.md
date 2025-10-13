# 🧭 BetAI Backend — Architecture & Integration Guide

This backend powers the core logic for **BetAI** — fetching and normalizing real-time betting data, making agent-based decisions, and tracking paper trades.  
It’s designed for modularity so the frontend (Streamlit UI) can plug directly into clean, well-defined components.

---

## 🗂️ Folder Structure

```
backend/
└── core/
    └── betai/
        ├── agents/                # BettingAgent and helpers
        ├── coordinators/          # Market-specific coordinators (moneyline, spread, total)
        ├── models/                # ML models (stub now, real later)
        ├── integrations/          # External data providers (The Odds API v4)
        │   └── odds_api.py        # odds + scores + normalization + cache
        ├── registry/              # feature lists, model metadata
        └── __init__.py
```

---

## ⚙️ Integrations Overview

### 🎯 The Odds API Provider (`integrations/odds_api.py`)

The **Odds API** serves as our unified source for both **odds** and **scores**.  
This means consistent `game_id`, team names, and timestamps across the app.

#### ✅ Features

- Fetch **live odds** and **scores** from the same provider  
- In-memory **cache** (default 10s) to limit API calls during auto-refresh  
- Unified **normalization** layer — downstream modules don’t depend on vendor format  
- Robust to missing fields (graceful fallbacks for incomplete data)

---

### 🧩 Key Methods

#### `list_sports()`
Returns available sports and their sport keys.

#### `fetch_markets(sport_key, regions, markets, odds_format, bookmakers)`
Fetches market odds for a given sport.

#### `fetch_scores(sport_key, days_from=None)`
Fetches current or recent game scores.

---

### 🧮 Normalization Helpers

#### `normalize_events(raw_events)`

Converts vendor JSON into our unified internal schema:

```python
{
  "game_id": str,
  "commence_time": str,       # ISO timestamp
  "home": str,
  "away": str,
  "offers": [
    {
      "bookmaker": str,
      "market": "moneyline" | "spread" | "total",
      "side": str,            # "DET ML", "DET -3.5", "Over 46.5"
      "decimal_odds": float,
      "context": {
        "home_team": str,
        "away_team": str,
        "bookmaker": str,
        "provider_market_key": "h2h"|"spreads"|"totals",
        "point": float|None
      }
    },
    ...
  ]
}
```

#### `normalize_scores(raw_scores)`

Standardized shape for score tracking:

```python
{
  "game_id": str,
  "commence_time": str,       # ISO
  "completed": bool,
  "home": str,
  "away": str,
  "home_score": int|None,
  "away_score": int|None,
  "last_update": str|None
}
```

---

## 🧠 Betting Agent System

### 🏈 BettingAgent (in `agents/agent_v2.py`)

Acts as the **head coach** — evaluates bets, manages bankroll, and applies Kelly/EV rules.

**Responsibilities:**
- Manage bankroll + open bets  
- Route evaluations to the correct Coordinator  
- Calculate Expected Value (EV) and stake sizing  
- Return normalized recommendations for the frontend

**Example Output**
```python
{
  "decision": "BET" | "PASS",
  "ev": float,
  "stake": float,
  "p_model": float,
  "p_implied": float,
  "model_used": str,
  "context": {...}
}
```

---

## ⚙️ Coordinators & Models

Each market type (Moneyline, Spread, Total) has a **Coordinator** that prepares features and calls a model.

### MoneylineCoordinator
- Converts odds + context → feature row  
- Uses model’s `feature_list` for consistency  
- Falls back to defaults if registry file is missing

### MoneylineLR (stub model)
- Simplified heuristic (home advantage, possession, score diff)  
- Later to be replaced by trained sklearn model (plug-compatible)

---

## 🧩 Integration with the Frontend

The frontend imports backend modules directly:

| Action | Backend Function |
|--------|------------------|
| Fetch odds | `TheOddsAPIProvider.fetch_markets()` + `normalize_events()` |
| Fetch live scores | `TheOddsAPIProvider.fetch_scores()` + `normalize_scores()` |
| Evaluate bet | `BettingAgent.make_recommendation()` |
| Place/settle bet | `BettingAgent.record_result()` |

Front and back communicate through **shared Python imports**, not HTTP — this keeps the MVP fast and easy to debug.

---