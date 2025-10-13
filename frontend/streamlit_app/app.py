"""
@file        app_v2.py
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

from __future__ import annotations                  # Enables postponed type hint evaluation for cleaner forward declarations
import os                                           # Access environment variables (API keys, config)
import re                                           # Used to sanitize Streamlit widget keys
import time                                         # Provides timestamps for odds fetch and refresh logic
from typing import Any                              # Generic typing for helper functions
import streamlit as st                              # Core Streamlit library for UI rendering
from streamlit_autorefresh import st_autorefresh    # Provides periodic auto-rerun capability

# Import odds provider wrapper and event normalizer
from lib.api import fetch_and_normalize_events      # Fetches odds from The Odds API and normalizes data

# Import centralized session state manager
from lib import session_state as ss                 # Handles all st.session_state initialization and accessors

# Import modular view renderers
from views.sidebar import render_sidebar                    # Sidebar (provider + agent controls)
from views.live_board import render_live_board              # Live Board tab (live events + odds)
from views.recommendations import render_recommendations    # Recommendations tab (EV-based suggestions)
from views.open_bets import render_open_bets                # Open Bets tab (active simulated bets)
from views.history import render_history                    # History tab (performance tracking)
from views.paper_trading import render_paper_trading        # Paper trading tab

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
tab_live, tab_pt, tab_reco, tab_open, tab_hist = st.tabs([
    "Live Board", "Paper Trading", "Recommendations", "Open Bets", "History"
])

# ------------------------------------------------------------
# Live Board Tab
# ------------------------------------------------------------
with tab_live:
    # Render the Live Board (events, logos, odds, evaluate/place actions)
    render_live_board(
        events=st.session_state.events,     # normalized events
        agent=agent,                        # BettingAgent instance
        ev_threshold=ev_threshold,          # EV gate for recs
        skey=skey,                          # widget key helper
        sport_key=sport_key,                # Sport type pass through from sidebar
    )

# ------------------------------------------------------------
# Paper Trading Tab
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
# Recommendations Tab
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
# Open Bets Tab
# ------------------------------------------------------------
with tab_open:
    # Render the Open Bets view (paper trades awaiting settlement)
    render_open_bets(
        agent=agent,
        open_bets=st.session_state.open_bets,
    )

# ------------------------------------------------------------
# History Tab
# ------------------------------------------------------------
with tab_hist:
    # Render the History view (settled bets, bankroll curve, KPIs)
    render_history(
        agent=agent,
        history=st.session_state.history,
    )