"""
@file        views/scoreboard/scorecard.py
@brief       Scoreboard grid of game cards (logos + score + state) with Details drill-in.
@details
  Responsibilities
  - Render a glanceable grid of ESPN games as cards (N per row).
  - Each card shows:
      • Team logos and names
      • Current score or dashes pre-game
      • State badge (PRE/IN/POST) and period/clock when available
      • “Details” button that switches the router into the single-game view
  - Provide a state filter (ALL/IN/PRE/POST) and sensible sorting:
      IN first, POST next, PRE last; ties broken by seconds remaining.

  Inputs (function params)
  - games (List[dict]): Normalized ESPN scoreboard rows (from `normalize_scoreboard()`).
  - skey (Callable[..., str]): Helper to build stable Streamlit widget keys.
  - cards_per_row (int): Number of cards per grid row (default 3).
  - logo_size (int): Pixel size for team logos (default 84).

  Session State (read/write)
  - _scorecard_css_injected: One-time flag to avoid duplicate <style> injection.
  - selected_event: Last selected ESPN event id (preserved across reruns).
  - sb_mode: Router mode string; set to "detail" when a card's Details is clicked.

  Key Helpers (defined in this module)
  - scorecard_css(): injects the CSS used by scorecard cards (once per session).
  - state_badge(): small colored HTML badge for PRE/IN/POST.
  - sort_key_for_game(): sorting function prioritizing live games (uses seconds left).
  - go_to_detail(): writes `selected_event`, sets `sb_mode="detail"`, and reruns.

  Notes
  - This module is intentionally odds-agnostic; it's an overview only.
  - Images are loaded by exact team display names via `load_team_logo_from_name()`.
  - Expects upstream router to call the `game_details` view when `sb_mode == "detail"`.
"""

# ============================================================
# Imports
# ============================================================

# Enable postponed evaluation of annotations (cleaner forward refs)
from __future__ import annotations

# Standard library imports
from typing import Any, Callable, Dict, List, Optional, Tuple      # Typing for clarity

# Third-party imports
import streamlit as st                                             # Core Streamlit UI primitives

# Internal libs — ESPN helpers used by the scoreboard
from betai.integrations.pbp_api import compute_seconds_left        # Derives seconds left from period/clock
from lib.utils import load_team_logo_from_name                     # Loads PNG logos by exact team display name


# ============================================================
# Module-level state (one-time CSS injector flag)
# ============================================================

# Guard flag so our <style> block is injected only once per session
_SCORECARD_CSS_KEY: str = "_scorecard_css_injected"


# ============================================================
# Helpers — UI Styling + Small Formatters
# ============================================================

def scorecard_css() -> None:
    """
    @brief      Inject the minimal CSS block for Scorecard visuals.
    @details
      - Adds hover, border, and grid styles for each game card.
      - Uses a session flag to prevent duplicate <style> blocks across reruns.

    @param      None

    @return     None
    """
    # Exit early if CSS has already been injected this session
    if st.session_state.get(_SCORECARD_CSS_KEY):
        return

    # Mark as injected
    st.session_state[_SCORECARD_CSS_KEY] = True

    # Inject inline CSS styles for the Scorecard layout
    st.markdown(
        """
        <style>
            .scorecard {
                padding: 12px 14px;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                transition: border-color .15s ease, background .15s ease;
                background: rgba(255,255,255,0.02);
                min-height: 220px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
            .scorecard:hover {
                border-color: rgba(255,255,255,0.30);
                background: rgba(255,255,255,0.04);
            }
            .scorecard-score {
                font-size: 20px;
                font-weight: 800;
                text-align: center;
                margin-top: 4px;
            }
            .scorecard-meta {
                color: #bdc3c7;
                font-size: 12px;
            }
            .scorecard-names {
                font-weight: 600;
                text-align: center;
                margin-top: 6px;
                min-height: 22px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def state_badge(state: str) -> str:
    """
    @brief      Return a small colored HTML badge representing game state.
    @details
      - PRE  → blue
      - IN   → green
      - POST → gray
      - Default → muted gray

    @param      state   One of 'PRE' | 'IN' | 'POST' (case-insensitive).

    @return     str     HTML <span> snippet (safe for use with unsafe_allow_html=True).
    """
    # Normalize input to uppercase and select a color mapping
    s: str = (state or "").upper()
    color_map: Dict[str, str] = {"IN": "#2ecc71", "PRE": "#3498db", "POST": "#95a5a6"}
    color: str = color_map.get(s, "#7f8c8d")

    # Return formatted badge
    return (
        f"<span style='background:{color};color:#000;padding:2px 6px;"
        f"border-radius:10px;font-size:11px;font-weight:600'>{s or '-'}</span>"
    )


def sort_key_for_game(g: Dict[str, Any]) -> Tuple[int, int]:
    """
    @brief      Compute a sort key that prioritizes live games.
    @details
      - Orders by (state_rank, seconds_remaining):
          IN → 0, POST → 1, PRE → 2, unknown → 3
      - Uses compute_seconds_left(period, display_clock) for secondary ordering.

    @param      g   One normalized game dictionary (from normalize_scoreboard()).

    @return     Tuple[int, int]  Sort key used by Python's sort().
    """
    # Determine state rank
    s: str = (g.get("state") or "").upper()
    rank_map: Dict[str, int] = {"IN": 0, "POST": 1, "PRE": 2}
    rank: int = rank_map.get(s, 3)

    # Compute remaining seconds
    sec_left: Optional[int] = compute_seconds_left(g.get("period"), g.get("display_clock"))
    sec_key: int = sec_left if isinstance(sec_left, int) else 99999

    return (rank, sec_key)


def go_to_detail(event_id: str) -> None:
    """
    @brief      Switch the Scoreboard view into 'detail' mode for a selected event.
    @details
      - Sets session state values:
          • 'selected_event' = event_id
          • 'sb_mode' = 'detail'
      - Calls st.rerun() to trigger the transition to details view.

    @param      event_id   ESPN event identifier string.

    @return     None
    """
    st.session_state["selected_event"] = event_id
    st.session_state["sb_mode"] = "detail"
    st.rerun()


# ============================================================
# Public Render — Scorecard Grid
# ============================================================

def render_scorecard(*,
                     games: List[Dict[str, Any]],
                     skey: Callable[..., str],
                     cards_per_row: int = 3,
                     logo_size: int = 84) -> Optional[str]:
    """
    @brief      Render the grid of game scorecards for the Scoreboard tab.
    @details
      - Displays N cards per row, each with:
          • Team logos and names
          • Current score or em dash when unavailable
          • State badge, period, and clock
          • 'Details' button to open the detailed game view
      - Keeps this module focused on high-level overview (no odds).

    @param      games          List of normalized ESPN games (from normalize_scoreboard()).
    @param      skey           Helper to generate unique Streamlit widget keys.
    @param      cards_per_row  Number of cards per grid row.
    @param      logo_size      Pixel size for team logos.

    @return     Optional[str]  The selected ESPN event_id, if any.
    """
    # ------------------------------------------------------------
    # Ensure scorecard CSS is injected (only once per session)
    # ------------------------------------------------------------
    scorecard_css()

    # ------------------------------------------------------------
    # Read last selection for reference
    # ------------------------------------------------------------
    selected: Optional[str] = st.session_state.get("selected_event")

    # ------------------------------------------------------------
    # Handle no available games
    # ------------------------------------------------------------
    if not games:
        st.info("No games available.")
        return selected

    # ------------------------------------------------------------
    # Add a quick state filter toggle (ALL, IN, PRE, POST)
    # ------------------------------------------------------------
    state_filter: str = st.radio(
        "State",
        options=["ALL", "IN", "PRE", "POST"],
        index=0,
        horizontal=True,
        key=skey("sb_state_cards"),
    )

    # ------------------------------------------------------------
    # Apply filter selection
    # ------------------------------------------------------------
    filtered: List[Dict[str, Any]] = (
        [g for g in games if (g.get("state") or "").upper() == state_filter]
        if state_filter != "ALL" else list(games)
    )

    # ------------------------------------------------------------
    # Sort games so LIVE appear first, then POST, then PRE
    # ------------------------------------------------------------
    filtered.sort(key=sort_key_for_game)

    # ------------------------------------------------------------
    # Render grid with given cards_per_row
    # ------------------------------------------------------------
    for i in range(0, len(filtered), cards_per_row):
        row: List[Dict[str, Any]] = filtered[i : i + cards_per_row]
        cols = st.columns(len(row))

        for col, g in zip(cols, row):
            with col:
                # Extract key fields
                eid: str = g.get("espn_event_id") or "?"
                away: Dict[str, Any] = g.get("away") or {}
                home: Dict[str, Any] = g.get("home") or {}
                aname: str = away.get("name", "Away")
                hname: str = home.get("name", "Home")
                ascr: Optional[int] = away.get("score")
                hscr: Optional[int] = home.get("score")
                state: str = (g.get("state") or "").upper()
                per: Optional[int] = g.get("period")
                clk: str = g.get("display_clock") or "--:--"

                # --------------------------------------------------------
                # Card shell container
                # --------------------------------------------------------
                st.markdown("<div class='scorecard'>", unsafe_allow_html=True)

                # --- Top: Team logos + names (centered) ---
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1:
                    a_logo = load_team_logo_from_name(aname, size=logo_size)
                    if a_logo is not None:
                        st.image(a_logo, width=logo_size)
                    st.markdown(f"<div class='scorecard-names'>{aname}</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown("<div style='text-align:center;margin-top:12px;'>vs</div>", unsafe_allow_html=True)
                with c3:
                    h_logo = load_team_logo_from_name(hname, size=logo_size)
                    if h_logo is not None:
                        st.image(h_logo, width=logo_size)
                    st.markdown(f"<div class='scorecard-names'>{hname}</div>", unsafe_allow_html=True)

                # --- Middle: Score + state/clock line ---
                left_score = "—" if ascr is None else str(ascr)
                right_score = "—" if hscr is None else str(hscr)
                st.markdown(
                    f"<div class='scorecard-score'>{left_score} : {right_score}</div>",
                    unsafe_allow_html=True,
                )

                meta_bits: List[str] = [state_badge(state)]
                if per is not None:
                    meta_bits.append(f"<span class='scorecard-meta'>• Q{per} • {clk}</span>")
                st.markdown(" ".join(meta_bits), unsafe_allow_html=True)

                # --- Bottom: Details button ---
                if st.button("Details", key=skey("sb_det", eid), use_container_width=True):
                    go_to_detail(eid)

                # Close card container
                st.markdown("</div>", unsafe_allow_html=True)

    # Return the selected event id (if any)
    return selected