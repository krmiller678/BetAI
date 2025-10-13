# 🧠 BetAI — Streamlit App (Frontend)

This folder contains the **Streamlit-based user interface** for the BetAI project.  
It provides a modular, readable, and expandable prototype for live sports betting analysis — including odds fetching, game boards, agent recommendations, and paper-trading simulation.

---

## 🗂 Folder Structure

```
frontend/streamlit_app/
├── app.py                     # Main entry point (UI router)
├── lib/                       # Helper modules shared across views
│   ├── api.py                 # Wrapper for The Odds API provider (fetch & normalize)
│   ├── session_state.py       # Initializes and manages Streamlit session state
│   ├── utils.py               # Shared UI helpers (logos, keys, formatting)
├── views/                     # Modular UI pages (each one handles its own layout)
│   ├── sidebar.py             # Sidebar controls for API + agent settings
│   ├── live_board.py          # Live odds board (logos, scores, grouped offers)
│   ├── paper_trading.py       # Legacy-style combined offers + open bets + performance
│   ├── recommendations.py     # High-EV ideas based on agent evaluations
│   ├── open_bets.py           # Shows current paper bets + manual settle actions
│   ├── history.py             # Bankroll, hit-rate, ROI, and settled bet table
└── assets/
    └── team-logos/            # Local PNGs for all NFL teams
```

---

## 🚀 How the App Works

### 1️⃣ Overview
The app is a **modular Streamlit UI** designed to interact with the BetAI backend’s integrations and agent logic.

Each tab (Live Board, Paper Trading, Recommendations, Open Bets, History) operates on shared data in `st.session_state` — ensuring persistence between reruns.

---

### 2️⃣ Data Flow Summary

```
   ┌────────────────────────────┐
   │ The Odds API (external)   │
   │  • /sports/{sport}/odds   │
   │  • /sports/{sport}/scores │
   └────────────┬──────────────┘
                │
        (via lib/api.py)
                │
   ┌────────────▼────────────┐
   │  Normalized Events &    │
   │  Scores in SessionState │
   └────────────┬────────────┘
                │
        ┌───────▼────────┐
        │ Streamlit Views│
        │ (Live Board, …)│
        └────────────────┘
                │
       ┌────────▼────────┐
       │ Betting Agent v2│
       │ (make_recommend)│
       └─────────────────┘
```

**Key idea:**  
- The UI pulls fresh data from the API layer (`lib/api.py`).  
- That data is normalized into a consistent structure (`normalize_events`).  
- The `BettingAgent` evaluates offers to produce recommendations (EV + stake).  
- These are stored in `session_state` and surfaced across multiple tabs.

---

### 3️⃣ Main Components

#### 🧩 `app.py`
- Configures Streamlit (wide layout, title).  
- Initializes session state (`lib/session_state.init_session()`).  
- Renders sidebar (via `views/sidebar.render_sidebar`).  
- Fetches odds + auto-refreshes based on sidebar config.  
- Routes to main tabs:
  - **Live Board** — show games, odds, and evaluate/place buttons.  
  - **Paper Trading** — legacy layout combining filters + performance.  
  - **Recommendations** — sorted list of recent positive-EV bets.  
  - **Open Bets** — active paper trades with manual settle buttons.  
  - **History** — bankroll chart, ROI, and settled bets.

#### ⚙️ `lib/session_state.py`
Centralizes all persistent variables:
- `agent` — BettingAgent instance  
- `events` — normalized games from odds API  
- `last_fetch` — timestamp of last refresh  
- `last_recs` — recent recommendations  
- `open_bets`, `history` — current and past paper trades  

Ensures that state is always initialized exactly once.

#### 🌐 `lib/api.py`
- Wraps the backend’s The Odds API provider.  
- Handles fetching and normalization of events (`fetch_and_normalize_events`).  
- Optionally supports fetching scores (`fetch_scores`), short-cached.  
- Keeps this layer UI-agnostic (no Streamlit imports).

#### 🧰 `lib/utils.py`
- Loads team logos from `/assets/team-logos/`.  
- Creates placeholder badges if a logo is missing.  
- Provides `make_safe_key()` for consistent Streamlit widget keys.

#### 🧮 `views/` modules
Each file encapsulates one view/tab.  
They follow a consistent pattern:
```python
def render_<page_name>(*, agent: Any, ...):
    st.subheader("Page Title")
    ...
```
- `live_board.py`: shows games, logos, scores, and organizes offers by market type.  
- `paper_trading.py`: flatten & filter offers, includes Open Bets + KPIs side-by-side.  
- `recommendations.py`: filters recent agent calls by EV threshold.  
- `open_bets.py`: lists active paper bets with settle buttons.  
- `history.py`: shows settled bets, bankroll curve, hit rate, and ROI.

#### 🎨 `views/sidebar.py`
- Displays provider + agent controls:
  - Sport key, regions, markets, auto-refresh.
  - Agent parameters (EV threshold, Kelly fraction, max stake %).  
- Returns a simple config dict to `app.py`.

---

## 🧩 Shared State Schema

| Key | Type | Purpose |
|-----|------|----------|
| `agent` | `BettingAgent` | Handles recommendation + bankroll logic |
| `events` | `List[Dict]` | Normalized odds data for current sport |
| `last_fetch` | `float` | Unix timestamp of last API call |
| `last_recs` | `List[Dict]` | Cached recommendations for display |
| `open_bets` | `Dict[str, Dict]` | Active paper bets (id → bet dict) |
| `history` | `List[Dict]` | Settled bets (for History tab) |

---

## 🧭 User Flow

1. **Fetch odds** → populates `events` from the odds API.  
2. **View Live Board** → shows all current games with grouped offers.  
3. **Evaluate** → agent calculates EV and stake → stored in `last_recs`.  
4. **Place (paper)** → adds record to `open_bets`.  
5. **Settle (✓ / ✗)** → moves bet to `history`, updates bankroll.  
6. **View History tab** → see PnL curve, ROI, hit rate.  

---

## 🧠 Design Notes

- **Modular architecture:** each view is self-contained, can be replaced or extended.  
- **Streamlit-friendly imports:** avoids circular dependencies and heavy globals.  
- **Lightweight API wrapper:** all provider access goes through `lib/api.py`.  
- **Local assets:** logos stored in `/assets/team-logos/` to ensure fast offline load.  
- **Consistent styling:** inline comments + docstrings follow Doxygen format.  

---

## 🧩 Future Enhancements

- Integrate `/scores` feed once period/clock fields become available.  
- Add auto-settle logic (Results Provider).  
- Introduce richer visualization (bankroll progression, bet distribution).  
- Move agent logic to a backend API (FastAPI microservice).  
- Allow user authentication and persistent history.

---

## ✅ Quick Start

```bash
# Activate environment
source .venv/bin/activate

# Run the Streamlit app
streamlit run frontend/streamlit_app/app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.
