"""
@file        session_state.py
@brief       Centralized Streamlit session_state initialization and accessors.
@details
  - Provides a single source of truth for all Streamlit session_state keys.
  - Initializes keys on first run and exposes `get_*` accessors for consistent usage.
  - Replaces private _ensure_* helpers with public agent() and collections() functions
    so initialization can be easily understood and extended.
  - Safe to call init_session() on every rerun — no duplicate initialization occurs.
"""

# ============================================================
# Imports (inline comments for clarity)
# ============================================================

from __future__ import annotations              # Allow forward references in type hints
import os                                       # Access environment variables for defaults
from typing import Any, Dict, List              # Type hints for generic containers
import streamlit as st                          # Streamlit session_state management


# ============================================================
# Module Constants (configurable defaults)
# ============================================================

# Default bankroll for a new BettingAgent, overridable via environment variable
DEFAULT_BANKROLL: float = float(os.getenv("BETAI_STARTING_BANKROLL", "1000.0"))


# ============================================================
# Public API — main initialization entry point
# ============================================================

def init_session() -> None:
    """
    @brief Ensure all required session_state keys exist (idempotent).
    @details
      - Calls agent() to ensure a BettingAgent is created and stored.
      - Calls collections() to ensure all shared lists and dicts are initialized.
      - Designed to be called once from app.py after set_page_config().
    """
    # Ensure the BettingAgent exists
    agent()

    # Ensure all supporting collections exist
    collections()


# ============================================================
# Initialization Helpers (called internally by init_session)
# ============================================================

def agent() -> None:
    """
    @brief Ensure a BettingAgent exists in session_state.
    @details
      - Performs a lazy import of BettingAgent to avoid circular dependencies.
      - Creates a new agent with a default bankroll if missing.
    """
    # Check if the agent has already been created
    if "agent" not in st.session_state:

        # Lazy import to avoid circular import errors during module load
        from betai.agents.agent_v2 import BettingAgent

        # Create a new BettingAgent and store in session_state
        st.session_state.agent = BettingAgent(starting_bankroll=DEFAULT_BANKROLL)


def collections() -> None:
    """
    @brief Ensure that all standard collections exist in session_state.
    @details
      - Initializes all lists and dictionaries used by the UI.
      - Prevents key errors and maintains consistency across reruns.
    """
    # Initialize the list of normalized events (from The Odds API) Type: List[Dict[str, Any]] 
    if "events" not in st.session_state:
        st.session_state.events = []

    # Initialize the timestamp of the last odds fetch (0 means never) Type: float 
    if "last_fetch" not in st.session_state: 
        st.session_state.last_fetch = 0.0

    # Initialize the list of recent model recommendations Type: List[Dict[str, Any]] 
    if "last_recs" not in st.session_state:
        st.session_state.last_recs = []

    # Initialize the dictionary of open paper-traded bets Type: Dict[str, Dict[str, Any]]
    if "open_bets" not in st.session_state:
        st.session_state.open_bets = {}

    # Initialize the list of settled bets (for History tab) Type: List[Dict[str, Any]] 
    if "history" not in st.session_state:
        st.session_state.history = []


# ============================================================
# Accessor Functions (get_* naming for clarity)
# ============================================================

def get_agent():
    """
    @brief Retrieve the BettingAgent instance from session_state.
    @return The BettingAgent object stored in session_state.
    """
    # Return the agent reference
    return st.session_state.agent


def get_events() -> List[Dict[str, Any]]:
    """
    @brief Retrieve the list of normalized event dictionaries.
    @return List of events representing live matchups and odds data.
    """
    # Return the events list for read/write
    return st.session_state.events


def get_open_bets() -> Dict[str, Dict[str, Any]]:
    """
    @brief Retrieve the dictionary of open paper-traded bets.
    @return Mapping of bet_id -> bet record for active open positions.
    """
    # Return the open bets dictionary
    return st.session_state.open_bets


def get_history() -> List[Dict[str, Any]]:
    """
    @brief Retrieve the list of settled bet records.
    @return List of dicts representing past results (used for History view).
    """
    # Return the history list for read/write
    return st.session_state.history


def get_last_recs() -> List[Dict[str, Any]]:
    """
    @brief Retrieve the list of the most recent model recommendations.
    @return List of recommendation dicts used by the Recommendations view.
    """
    # Return the last recommendations list
    return st.session_state.last_recs


# ============================================================
# Optional Development Helper
# ============================================================

def reset_session(keep_agent: bool = True) -> None:
    """
    @brief Clear and reinitialize the Streamlit session_state.
    @param keep_agent Whether to retain the current BettingAgent instance.
    @details
      - Clears all keys in session_state.
      - Optionally preserves the BettingAgent object.
      - Calls collections() to recreate empty lists and dicts.
      - Helpful for development testing between sessions.
    """
    # Store a reference to the agent if preservation requested
    saved_agent = st.session_state.get("agent", None) if keep_agent else None

    # Clear the entire session_state dictionary
    st.session_state.clear()

    # If keeping agent and one was previously saved, restore it
    if keep_agent and saved_agent is not None:
        st.session_state.agent = saved_agent
    else:
        # Otherwise, reinitialize a new agent
        agent()

    # Recreate the supporting collections
    collections()