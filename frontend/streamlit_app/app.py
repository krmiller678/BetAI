"""
@file        app.py
@brief       BetAI Streamlit UI — main router and shell (modular views)
@details
  - Initializes Streamlit page and session state (via lib/session_state.py)
  - Renders sidebar controls (via views/sidebar.py)
  - Fetches live odds and normalizes them through lib/api.py
  - Handles manual fetch and optional auto-refresh
  - Routes to modular views: Live Board, Recommendations, Open Bets, and History
"""

# ============================================================
# Imports
# ============================================================

# Enable postponed evaluation of annotations (cleaner forward refs)
from __future__ import annotations

# Standard library imports
import os                                           # Access environment variables (API keys, config)
import re                                           # Used to sanitize Streamlit widget keys
import time                                         # Provides timestamps for odds fetch and refresh logic
from datetime import date, datetime, timezone       # Date handling for slate selection + filtering
from typing import Any, Callable, Dict, List        # Typing for clarity

# Third-party imports
import streamlit as st                              # Core Streamlit library for UI rendering
from streamlit_autorefresh import st_autorefresh    # Provides periodic auto-rerun capability

# Internal libs — Odds API (normalized) + session state
from lib.api import fetch_and_normalize_events      # Fetches odds from The Odds API and normalizes data
from lib import session_state as ss                 # Handles all st.session_state initialization and accessors

# Internal views — modular renderers
from views.sidebar import render_sidebar                                # Sidebar (provider + agent controls)
from views.live_board import render_live_board                          # Live Board tab (live events + odds)
from views.recommendations import render_recommendations                # Recommendations tab (EV-based suggestions)
from views.open_bets import render_open_bets                            # Open Bets tab (active simulated bets)
from views.history import render_history                                # History tab (performance tracking)
from views.paper_trading import render_paper_trading                    # Paper trading tab
from views.scoreboard.scoreboard_router import render_scoreboard        # ESPN scoreboard + details

# Internal ESPN integration — scoreboard normalization
from betai.integrations.pbp_api import fetch_scoreboard, normalize_scoreboard

# Internal API linker — connects ESPN event_id ↔ OddsAPI game_id by team names
from lib.api_linker import build_api_link_map

# ============================================================
# Helper Function: skey
# ============================================================

def skey(*parts: Any) -> str:
    """
    @brief Build a safe Streamlit widget key from multiple parts.
    @details
      - Joins all parts with underscores.
      - Replaces unsupported characters (spaces, slashes, etc.) with underscores.
    @param parts One or more identifiers to combine into a unique key.
    @return A sanitized key string safe for Streamlit widgets.
    """

    # Join all provided parts into a single string separated by underscores
    raw_key = "_".join(str(p) for p in parts)

    # Replace invalid characters (anything not alphanumeric, dot, underscore, or dash)
    safe_key = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_key)

    # Return the sanitized version
    return safe_key

# ============================================================
# Helper: ESPN 'YYYYMMDD' formatter
# ============================================================

def _yyyymmdd(d: date) -> str:
    """
    @brief Convert a date to ESPN 'YYYYMMDD' string (e.g., 20251029).
    @param d  Python date object.
    @return ESPN date string in YYYYMMDD format.
    """
    # Format incoming date into ESPN-compatible YYYYMMDD
    return d.strftime("%Y%m%d")

# ============================================================
# Helper: Same-calendar-day test for OddsAPI commence_time
# ============================================================

def _same_calendar_day(local_iso: str | None, target: date) -> bool:
    """
    @brief Check if an ISO timestamp falls on the target local calendar date.
    @details
      - Interprets the ISO (with or without 'Z') into local time.
      - Compares only .date() component against target date.
    @param local_iso  ISO 8601 timestamp string from OddsAPI (may end with 'Z').
    @param target     The selected slate date (local).
    @return True if the commence_time lands on target date locally; else False.
    """
    # Early-out when timestamp missing
    if not local_iso:
        return False

    try:
        # Normalize 'Z' to explicit UTC offset so fromisoformat can parse it
        iso = local_iso.replace("Z", "+00:00")
        # Parse the ISO string into a datetime
        dt = datetime.fromisoformat(iso)
        # If naive, assume UTC then convert to local time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()  # Convert to local system timezone
        # Compare only the calendar day component
        return local_dt.date() == target
    except Exception:
        # Fail-safe (do not include when parsing fails)
        return False


# ============================================================
# Helper: Filter OddsAPI events to the selected slate date
# ============================================================

def _filter_events_by_date(events: List[Dict[str, Any]] | None, target: date) -> List[Dict[str, Any]]:
    """
    @brief Select only events whose commence_time falls on the target local date.
    @param events  List of normalized OddsAPI events (may be None/empty).
    @param target  The selected slate date (local).
    @return Filtered list of events for the chosen date.
    """
    # Guard against None; always return a list
    if not events:
        return []
    # Keep only those whose commence_time matches the target calendar day
    return [ev for ev in events if _same_calendar_day(ev.get("commence_time"), target)]


# ============================================================
# Streamlit Page Configuration
# ============================================================

# Configure the Streamlit page title and layout mode
st.set_page_config(page_title="BetAI — Live Odds", layout="wide")


# ============================================================
# Session State Initialization
# ============================================================

# Initialize all Streamlit session_state variables (idempotent call)
# This ensures we always have: agent, events, open_bets, history, last_fetch, etc.
ss.init_session()

# Retrieve a short reference to the BettingAgent stored in session_state
agent = ss.get_agent()


# ============================================================
# Sidebar Controls
# ============================================================

# Render sidebar controls (sport key, regions, markets, refresh, EV threshold, agent risk knobs)
# This function also updates the agent's parameters directly from sliders.
sidebar_cfg = render_sidebar(agent=agent)

# Unpack the configuration dictionary returned by the sidebar
sport_key   = sidebar_cfg["sport_key"]          # Sport identifier (e.g., americanfootball_nfl)
regions     = sidebar_cfg["regions"]            # Region(s) to fetch from (e.g., us, uk)
markets     = sidebar_cfg["markets"]            # Market types (e.g., h2h, spreads, totals)
refresh_s   = sidebar_cfg["refresh_s"]          # Auto-refresh interval in seconds (0 disables)
ev_threshold = sidebar_cfg["ev_threshold"]      # Minimum EV for recommendations to appear

# Add a Slate Date picker (keeps ESPN and OddsAPI aligned to the same calendar day)
# - Stored in session_state so other tabs/components can reuse
slate_date = st.sidebar.date_input(
    label="Slate date",
    value=st.session_state.get("slate_date", date.today()),
    help="Pick the calendar day to display. ESPN will fetch this date; Odds will be filtered to this date."
)
st.session_state["slate_date"] = slate_date

# ============================================================
# Fetch Button and Timestamp Display
# ============================================================

# Create responsive columns for the fetch button and the last fetch timestamp
col_fetch, col_time, _ = st.columns([1, 1, 3])

# ------------------------------------------------------------
# Manual "Fetch Odds" button (left column)
# ------------------------------------------------------------
with col_fetch:
    # Render a wide fetch button to retrieve fresh odds
    if st.button("Fetch odds now", use_container_width=True):

        # Call the API wrapper to fetch and normalize event data
        st.session_state.events = fetch_and_normalize_events(
            sport_key=sport_key,
            regions=regions,
            markets=markets,
        )

        # Record the current timestamp to display later and track freshness
        st.session_state.last_fetch = time.time()

# ------------------------------------------------------------
# Last Fetch Timestamp display (right column)
# ------------------------------------------------------------
with col_time:
    # Retrieve the stored timestamp from session_state
    last_ts = st.session_state.last_fetch

    # Format timestamp into a readable time string, or use a placeholder if no data fetched yet
    ts_display = time.strftime("%H:%M:%S", time.localtime(last_ts)) if last_ts else "—"

    # Display the last fetch time in the UI
    st.write(f"Last fetch: {ts_display}")


# ============================================================
# Optional Auto-Refresh Logic
# ============================================================

# Check if auto-refresh is enabled
if (refresh_s > 0):

    # Schedule periodic reruns using the chosen interval (milliseconds)
    st_autorefresh(interval=refresh_s * 1000, key="auto_refresh")

    # Check if our last fetch is older than the selected refresh window
    if time.time() - st.session_state.last_fetch > refresh_s:

        # Fetch fresh odds data automatically using the same parameters
        st.session_state.events = fetch_and_normalize_events(
            sport_key=sport_key,
            regions=regions,
            markets=markets,
        )

        # Update the last fetch timestamp to the current time
        st.session_state.last_fetch = time.time()


# ============================================================
# Main Tabs (View Routing)
# ============================================================

# Create five tabs: Live Board, Paper Trading, Recommendations, Open Bets, and History
tab_scores, tab_live, tab_pt, tab_reco, tab_open, tab_hist = st.tabs([
    "Scoreboard", "Live Odds", "Paper Trading", "Recommendations", "Open Bets", "History"
])


# ------------------------------------------------------------
# Scoreboard Tab (ESPN-backed list + details, linked to Odds)
# ------------------------------------------------------------
with tab_scores:
    # Convert selected date into ESPN format
    espn_dates = _yyyymmdd(st.session_state["slate_date"])

    # Fetch raw scoreboard for that date from ESPN (network or provider cache)
    raw_sb = fetch_scoreboard(dates=espn_dates)

    # Normalize to uniform game dicts consumed by views.scoreboard
    games = normalize_scoreboard(raw_sb) or []

    # Filter OddsAPI events to the same local calendar day (may be empty)
    events_same_day = _filter_events_by_date(st.session_state.events, st.session_state["slate_date"])

    # Build the dictionary connecting ESPN event IDs ↔ OddsAPI game IDs (by full team names)
    # - This allows downstream UI (e.g., details pane) to pull odds for the selected ESPN event.
    espn_to_odds_map: Dict[str, str] = build_api_link_map(
        espn_games=games,
        odds_events=events_same_day,
    )

    # Store in session_state so any view can use it later
    st.session_state["espn_to_odds"] = espn_to_odds_map

    # Small caption to make provider overlap visible to the user
    st.caption(
        f"Slate: {st.session_state['slate_date'].strftime('%a %b %d, %Y')}  •  "
        f"ESPN games: {len(games)}  •  Odds games: {len(events_same_day)}  •  Linked: {len(espn_to_odds_map)}"
    )

    # Call the router with (games, agent, ev_threshold, skey)
    selected_eid = render_scoreboard(
        games=games,               # ESPN normalized games (for this date)
        agent=agent,               # BettingAgent instance used by Details view
        ev_threshold=ev_threshold, # Same threshold you set in the sidebar
        skey=skey,                 # Your widget key helper
        show_details_header=True,  # (optional) show big logos in details
        header_logo_size=96,       # (optional) size of those logos
    )

# ------------------------------------------------------------
# Live Odds Tab (OddsAPI-backed market cards + actions)
# ------------------------------------------------------------
with tab_live:
    # Filter OddsAPI events to the same local calendar day as the scoreboard
    events_same_day = _filter_events_by_date(st.session_state.events, st.session_state["slate_date"])

    # Render the Live Board (logos, odds, evaluate/place actions)
    render_live_board(
        events=events_same_day,        # Only the chosen slate date
        agent=agent,                   # BettingAgent instance
        ev_threshold=ev_threshold,     # EV gate for recs
        skey=skey,                     # Widget key helper
        sport_key=sport_key,           # Sport type pass-through from sidebar
    )


# ------------------------------------------------------------
# Paper Trading Tab (place + manage paper bets)
# ------------------------------------------------------------
with tab_pt:
    render_paper_trading(
        agent=agent,
        events=st.session_state.events,
        open_bets=st.session_state.open_bets,
        history=st.session_state.history,
        ev_threshold=ev_threshold,
        skey=skey,
    )

# ------------------------------------------------------------
# Recommendations Tab (EV suggestions based on latest odds)
# ------------------------------------------------------------
with tab_reco:
    # Render the Recommendations view (high-EV bets)
    render_recommendations(
        last_recs=st.session_state.last_recs,
        open_bets=st.session_state.open_bets,
        ev_threshold=ev_threshold,
        skey=skey,
    )

# ------------------------------------------------------------
# Open Bets Tab (active paper trades)
# ------------------------------------------------------------
with tab_open:
    # Render the Open Bets view (paper trades awaiting settlement)
    render_open_bets(
        agent=agent,
        open_bets=st.session_state.open_bets,
    )

# ------------------------------------------------------------
# History Tab (settled bets, bankroll curve, KPIs)
# ------------------------------------------------------------
with tab_hist:
    # Render the History view (settled bets, bankroll curve, KPIs)
    render_history(
        agent=agent,
        history=st.session_state.history,
    )