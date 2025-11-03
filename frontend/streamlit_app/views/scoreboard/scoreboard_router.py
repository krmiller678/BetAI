"""
@file        views/scoreboard/scoreboard_router.py
@brief       Router for the Scoreboard tab: card grid ↔ single-game details.
@details
  Responsibilities
  - Orchestrates which subview to render based on session state:
      • "grid"   -> render the Scorecard overview (clickable matchup cards)
      • "detail" -> render the single-game Details screen (with odds + actions)
  - Persists/reads UI state via Streamlit session_state:
      • 'sb_mode'         : "grid" | "detail"
      • 'selected_event'  : ESPN event id currently selected
  - Wires the Scorecard selection to the Details screen using a simple callback.

  Inputs (function params)
  - games (List[Dict[str, Any]])      : Normalized ESPN scoreboard rows (from normalize_scoreboard()).
  - agent (Any)                        : BettingAgent instance (used by game_details for Evaluate/Place).
  - ev_threshold (float)               : EV threshold used by the agent (passed through to details).
  - skey (Callable[..., str])          : Helper to build stable Streamlit widget keys.
  - show_details_header (bool, opt)    : If True, details view shows the large logo header (default: True).
  - header_logo_size (int, opt)        : Pixel size for header logos when header is shown (default: 96).

  Dependencies
  - streamlit
  - views.scoreboard.scorecard.render_scorecard
  - views.scoreboard.game_details.render_game_details

  Notes
  - The subviews (scorecard / game_details) own their rendering + UI specifics.
  - This router only switches views, handles selection, and shows a Back button.
"""

# ============================================================
# Imports
# ============================================================

# Enable postponed evaluation of annotations (cleaner forward refs)
from __future__ import annotations

# Standard library imports
from typing import Any, Callable, Dict, List, Optional              # Typing for clarity

# Third-party imports
import streamlit as st                                              # Core Streamlit library for UI rendering

# Internal views — submodules (overview grid + details screen)
from views.scoreboard.scorecard import render_scorecard             # Scorecard grid (cards with logos/scores)
from views.scoreboard.game_details import render_game_details       # Single-game details (odds + actions)




# ============================================================
# Helpers — session-state wiring
# ============================================================

def _ensure_defaults() -> None:
    """
    @brief      Ensure default scoreboard session keys exist.
    @details
      - Initializes 'sb_mode' to 'grid' if missing.
      - Leaves existing values untouched to preserve navigation history.

    @return     None
    """
    # Initialize the mode key if it doesn't exist
    if "sb_mode" not in st.session_state:

        st.session_state["sb_mode"] = "grid"


def _back_to_grid() -> None:
    """
    @brief      Navigate back to the Scorecard grid view.
    @details
      - Keeps 'selected_event' intact (so the user can return to the same game later).
      - Sets 'sb_mode' to 'grid' and reruns.

    @return     None
    """
    # Switch back to grid mode
    st.session_state["sb_mode"] = "grid"

    # Trigger a rerun to render the grid immediately
    st.rerun()


# ============================================================
# Public API — router entrypoint
# ============================================================

def render_scoreboard(
    *,
    games: List[Dict[str, Any]],
    agent: Any,
    ev_threshold: float,
    skey: Callable[..., str],
    show_details_header: bool = True,
    header_logo_size: int = 96,
) -> Optional[str]:
    """
    @brief      Router for the Scoreboard tab (grid ↔ details).
    @details
      - Reads 'sb_mode' and 'selected_event' from session_state to decide which subview to show.
      - In "grid" mode, renders the scorecard and wires a selection callback to show details.
      - In "detail" mode, renders the Details screen with a Back button.
      - Returns the currently selected ESPN event id (if any), for app-level awareness.

    @param      games               Normalized ESPN games (from normalize_scoreboard()).
    @param      agent               BettingAgent instance (used by Details view).
    @param      ev_threshold        EV threshold forwarded to the Details view.
    @param      skey                Helper for stable Streamlit widget keys.
    @param      show_details_header Whether to show large logos header in Details view.
    @param      header_logo_size    Pixel size for header logos when header is shown.

    @return     Optional[str]       Currently selected ESPN event id, or None if no selection yet.
    """
    # Ensure router defaults exist
    _ensure_defaults()

    # Read current mode and last selection from session_state
    mode: str = st.session_state.get("sb_mode", "grid")
    selected_eid: Optional[str] = st.session_state.get("selected_event")

    # -------------------------
    # DETAIL MODE
    # -------------------------
    if mode == "detail" and selected_eid:
        # Back button above the details view for navigation
        if st.button("← Back to Scoreboard", key=skey("sb_back_to_grid"), use_container_width=False):
            _back_to_grid()

        # Render the single-game details (handles odds + Evaluate/Place buttons)
        render_game_details(
            event_id=selected_eid,
            show_header=show_details_header,
            header_logo_size=header_logo_size,
            agent=agent,
            ev_threshold=ev_threshold,
            skey=skey,
        )

        # Return the active selection for upstream visibility
        return selected_eid

    # -------------------------
    # GRID MODE (default)
    # -------------------------

    # Render the scorecard overview (the scorecard will invoke _on_select on click)
    render_scorecard(
        games=games,
        skey=skey,
    )

    # Return the last-known selection (may be None if nothing clicked yet)
    return selected_eid