# 🧠 BetAI — Streamlit App (Frontend)

This directory contains the **Streamlit-based user interface** for BetAI — an AI-powered sports betting assistant that integrates live sportsbook odds, live game data, model predictions, and agent-based recommendations.

The frontend is designed to be clear, modular, and maintainable, with each UI component isolated into its own view module.

---

## 📁 Folder Structure

```
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
```

---

## 🚀 How the Frontend Works

### 1️⃣ Overview
The app is a **modular Streamlit UI** designed to interact with the BetAI backend’s integrations and agent logic.

The frontend is a multi-tab Streamlit application that coordinates:

- **Odds API SDK** (via backend integration wrapper)
- **ESPN Scoreboard metadata**
- **Supervised ML model predictions**
- **BettingAgent v2** for EV + stake recommendations
- **Session state** for persistence across reruns

The app does *not* directly call ML models or raw API endpoints — those are handled in backend/core/ and surfaced through `lib/api.py`.

---

### 2️⃣ Data Flow Overview

```
    ┌───────────────────────────┐
    │ The Odds API (external)   │
    │  • /sports/{sport}/odds   │
    │  • /sports/{sport}/scores │
    └────────────┬──────────────┘
                 │
(via lib/api.py → normalize_events())
                 │
    ┌────────────▼────────────┐
    │  Normalized Events &    │
    │  Scores in SessionState │
    └────────────┬────────────┘
                 │
  ┌──────────────▼─────────────-──┐
  │ Streamlit Views (UI Pages)    │
  │ scoreboard, game details,     │
  │ live board, open bets, history│
  └──────────────┬───────────-────┘
                 │
        ┌────────▼────────┐
        │ Betting Agent v2│
        │ (make_recommend)│
        └─────────────────┘
```
## 3️⃣ Main Components

The frontend is organized into clearly separated modules — routing, shared helpers, views, and UI logic.  

---

### 🧩 `app.py` — Main Router & Application Shell

The top-level Streamlit file:

- Sets Streamlit config (wide layout, centered title, sidebar collapsed by default)
- Initializes session state via `lib/session_state.init_session()`
- Renders the sidebar controls (`views/sidebar.py`)
- Triggers data fetch (OddsAPI + ESPN)
- Reads user settings (EV threshold, Kelly fraction, etc.)
- Routes to each main tab:

  - **Scoreboard** (grid of games → drill-down view)
  - **Live Board** (all offers grouped by market)
  - **Paper Trading** (legacy combined view)
  - **Recommendations** (positive-EV ideas)
  - **Open Bets** (active paper trades)
  - **History** (bankroll curve & full stats)

This file is the orchestrator that connects UI actions to backend logic.

---

### ⚙️ `lib/session_state.py` — Centralized State Manager

Initializes and stores the global state for the entire UI:

- `agent` — BettingAgent instance
- `events` — normalized OddsAPI output
- `last_fetch` — timestamp of last odds fetch
- `last_recs` — list of all Evaluate() results
- `open_bets` — dictionary of active un-settled bets
- `history` — list of settled bets (bankroll progression)

This guarantees **consistent, predictable state** throughout the app.

---

### 🌐 `lib/api.py` — Odds & Scoreboard Integration

Performs *frontend-facing* data integration:

- Fetches sportsbook odds via backend `odds_api` provider
- Fetches ESPN Scoreboard game metadata
- Returns **normalized events** in a uniform schema
- Handles:
  - bookmaker offers  
  - game IDs  
  - team names  
  - commence times  
  - metadata required for ML model context  

Everything returned here is preprocessed for immediate UI usage.

---

### 🔗 `lib/api_linker.py` — Game-ID Matching (ESPN ↔ OddsAPI)

Because the two APIs label games differently:

- ESPN uses `event_id`
- OddsAPI uses `id` (game_id)

This module:
- Compares team names
- Validates dates
- Builds a stable mapping of  
  **espn_event_id → oddsapi_game_id**

This mapping powers the Game Details page.

---

### 🧰 `lib/utils.py` — Common UI Utilities

Includes:

- Team logo loader from `/assets/team-logos/`
- Safe widget key generator (`make_safe_key`)
- Formatting helpers (scores, kickoff times, badges)
- Misc View utilities

Shared by **all** scoreboard and live-board components.

---

## 🧮 `views/` — All Streamlit Tabs

Each view follows a consistent pattern:

```python
def render_<page>(*, agent, events, ...):
    st.subheader("...")
    ...
```

### 🟦 `views/sidebar.py`
Renders user controls:
- Sport selection  
- Auto-refresh interval  
- EV threshold  
- Kelly fraction  
- Max stake %  
- API status  

Returns a config dict consumed by `app.py`.

---

### 🟩 `views/live_board.py`
Full-screen odds board for all games:
- Logos + matchups  
- Score strip (if available)  
- All offers grouped by market  
- Evaluate / Place (paper) controls  

Uses the BettingAgent for instant recommendations.

---

### 🟧 `views/paper_trading.py`
Legacy-style combined page with:
- Offers list  
- Open bets  
- Performance indicators  
- Recent evaluations  

Still included for feature completeness.

---

### 🟪 `views/recommendations.py`
Shows a sorted list of:
- All Evaluate() outputs  
- Filtered by EV threshold  
- Displays details + context  
- Links back to game details  

Useful for spotting “best EV” ideas at a glance.

---

### 🟥 `views/open_bets.py`
Displays active un-settled bets:
- Stake  
- Odds  
- Side  
- Market  
- Manual settle buttons (WIN / LOSS)

Settling updates the bankroll and moves the bet to History.

---

### 🟫 `views/history.py`
Comprehensive analytics:
- Bankroll curve chart  
- Hit rate  
- ROI  
- EV averages  
- Complete settled bet table  

This view shows long-term performance progression.

---

## 🏈 Scoreboard System (`views/scoreboard/`)

The scoreboard consists of **four tightly integrated modules**:

### 1️⃣ `scoreboard_router.py`
Controls navigation:
- No selection → show game grid
- Selection exists → show game details

Uses `st.session_state.selected_event`.

---

### 2️⃣ `scorecard.py`
Renders each game as a tile:
- Logos  
- Team names  
- Live scores  
- State badge (IN, PRE, POST)  
- “Details” button  

Uses custom CSS for aesthetic card layout.

---

### 3️⃣ `scorecard_css.py`
Injects all HTML/CSS used by scorecards:
- Layout grid  
- Icon sizing  
- Hover effects  
- Spacing and typography  

Loaded only once per session.

---

### 4️⃣ `game_details.py`
The deep-dive view:
- Team logos (large)  
- Live score / period / clock  
- Side-by-side stats (ESPN data)  
- Bookmaker offers grouped by market  
- Evaluate and Place (paper) buttons  
- ML model integration via BettingAgent  

Also manages the back-navigation behavior.

---

## 🧩 Shared State Schema

| Key | Type | Purpose |
|-----|------|---------|
| `agent` | BettingAgent | EV + Kelly decision logic |
| `events` | list[dict] | Normalized odds + game data |
| `last_fetch` | float | Timestamp of most recent fetch |
| `last_recs` | list | All Evaluate() outputs |
| `open_bets` | dict | Active paper trades |
| `history` | list | Settled bets for History view |
| `selected_event` | str \| None | Current scoreboard selection |

---

## 🧭 User Flow

1. **Sidebar → Fetch Odds**  
2. **Scoreboard → select game**  
3. **Game Details → Evaluate / Place bet**  
4. **Open Bets → settle manually**  
5. **History → see bankroll curve**  
6. **Recommendations → browse high-EV ideas**  

Everything persists across reruns via session_state.

---

## 🧠 Design Notes

- Each view is isolated and testable  
- The router architecture avoids complicated if/else logic  
- Logo system is optimized for local file access  
- API access is centralized (never from view files)  
- Scalable to additional markets or sports  

---

## 🧩 Future Enhancements

- Auto-settlement using ESPN play-by-play  
- In-game live prediction models  
- User authentication and persistent storage  
- Deployment via Streamlit Community Cloud or AWS  

---

## ✅ Quick Start

```bash
# Ensure venv is active
source .venv/bin/activate

# Run the app
streamlit run frontend/streamlit_app/app.py
```

Open:  
http://localhost:8501
