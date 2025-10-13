"""
@file        sidebar.py
@brief       Sidebar controls for BetAI Streamlit UI.
@details
  - Renders provider settings (sport_key, regions, markets, auto-refresh).
  - Renders agent policy controls (EV threshold, Kelly fraction, max stake %).
  - Applies agent slider values directly to the provided agent instance.
  - Returns a dict of sidebar configuration values for app.py.
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations          # Enable postponed type hints for forward references
import os                                   # Read default values from environment variables
from typing import Any, Dict                # Precise typing for agent object and config dictionary
import streamlit as st                      # Streamlit primitives to render the sidebar UI


# ============================================================
# Public API — render function for the sidebar
# ============================================================

def render_sidebar(*, agent: Any) -> Dict[str, Any]:
    """
    @brief Render the sidebar controls and return chosen configuration.
    @details
      - Provider settings are read with environment-backed defaults.
      - Agent risk knobs (kelly_fraction, max_stake_pct) are applied in place.
      - Returns a configuration dict used by app.py to fetch odds and route behavior.
    @param agent The BettingAgent instance stored in session_state.
    @return Dict with keys: sport_key, regions, markets, refresh_s, ev_threshold
    """

    # ------------------------------------------------------------
    # Write a header so users immediately recognize the section
    # ------------------------------------------------------------
    st.sidebar.header("Live Odds Settings")

    # ------------------------------------------------------------
    # Sport key input (defaults to NFL) — controls which sport we fetch from the provider
    # ------------------------------------------------------------
    sport_key = st.sidebar.text_input(
        label="Sport key",
        value=os.getenv("SPORT_KEY", "americanfootball_nfl"),
        help="Provider sport identifier (e.g., americanfootball_nfl).",
    )

    # ------------------------------------------------------------
    # Regions input — which bookmaker regions to include (comma-separated)
    # ------------------------------------------------------------
    regions = st.sidebar.text_input(
        label="Regions",
        value=os.getenv("ODDS_REGIONS", "us"),
        help="Comma-separated bookmaker regions (e.g., us,uk,eu).",
    )

    # ------------------------------------------------------------
    # Markets input — which market groups to request (comma-separated)
    # ------------------------------------------------------------
    markets = st.sidebar.text_input(
        label="Markets",
        value=os.getenv("ODDS_MARKETS", "h2h,spreads,totals"),
        help="Comma-separated market keys (e.g., h2h,spreads,totals).",
    )

    # ------------------------------------------------------------
    # Auto-refresh seconds (0 = off). When > 0, app.py schedules periodic reruns.
    # ------------------------------------------------------------
    refresh_s = st.sidebar.number_input(
        label="Auto refresh (sec)",
        min_value=0,
        max_value=300,
        value=int(os.getenv("UI_AUTO_REFRESH_SEC", "0")),
        step=1,
        help="Automatically refetch odds at this interval (0 disables).",
    )

    # ------------------------------------------------------------
    # EV threshold — only show/place recommendations with EV ≥ threshold
    # ------------------------------------------------------------
    ev_threshold = st.sidebar.number_input(
        label="EV threshold",
        min_value=0.0,
        max_value=0.20,
        value=float(os.getenv("AGENT_EV_THRESHOLD", "0.02")),
        step=0.005,
        help="Minimum expected value required for a recommendation to qualify.",
    )

    # ------------------------------------------------------------
    # Kelly fraction — fraction of Kelly stake to use (0 = off, 1 = full Kelly)
    # ------------------------------------------------------------
    agent.kelly_fraction = st.sidebar.slider(
        label="Kelly fraction",
        min_value=0.0,
        max_value=1.0,
        value=float(getattr(agent, "kelly_fraction", 0.25)),
        step=0.05,
        help="0 disables Kelly sizing; 1 uses full Kelly stake.",
    )

    # ------------------------------------------------------------
    # Max stake % — cap stake as a fraction of current bankroll to limit risk
    # ------------------------------------------------------------
    agent.max_stake_pct = st.sidebar.slider(
        label="Max stake %",
        min_value=0.0,
        max_value=1.0,
        value=float(getattr(agent, "max_stake_pct", 0.05)),
        step=0.01,
        help="Upper bound on stake size as a fraction of bankroll (risk cap).",
    )

    # ------------------------------------------------------------
    # Return a simple configuration dictionary back to app.py
    # ------------------------------------------------------------
    return {
        "sport_key": sport_key,      # Provider sport identifier
        "regions": regions,          # Bookmaker regions to include
        "markets": markets,          # Market groups to request
        "refresh_s": refresh_s,      # Auto-refresh interval (seconds)
        "ev_threshold": ev_threshold # Minimum EV threshold for recommendations
    }