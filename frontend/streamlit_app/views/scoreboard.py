"""
@file        views/scoreboard.py
@brief       Live scoreboard + details selector (ESPN-backed) with logo card grid
@details
  - Default "cards" mode: glanceable 3-up grid with team logos, score, state badge, clock.
  - Legacy "list" mode kept for fallback/testing (radio selector).
  - Clicking a card's **Details** sets st.session_state["selected_event"] for the details pane.
  - Optionally shows tiny ML(A)/ML(H) chips when Odds API data for the same slate is provided.
  - NOTE: render_game_details() is intentionally left **unchanged** at the end of this file.
"""

# ======================
# Imports
# ======================

# Enable postponed type hints for forward refs
from __future__ import annotations

# Import typing helpers
from typing import Any, Dict, List, Optional, Tuple

# Access time for tiny memo cache TTLs
import time

# Streamlit UI primitives
import streamlit as st

# ESPN helpers (your integration layer)
from betai.integrations.pbp_api import (
    fetch_scoreboard,
    normalize_scoreboard,
    fetch_summary,
    compute_seconds_left,
)

# Optional linker (kept here for completeness; not used by the scoreboard itself)
from lib.api_linker import build_api_link_map

# Team logo loader (same helper you use in live_board.py)
from lib.utils import load_team_logo_from_name


# ============================================================
# One-time CSS injection for scoreboard cards
# ============================================================

def _inject_sb_css_once() -> None:
    """
    @brief Inject the scoreboard CSS (only once per session).
    @details
      - Uses st.session_state guard to avoid duplicate <style> blocks on reruns.
      - Styles:
          * .sb-card      -> card shell (padding, border, hover)
          * .sb-score     -> centered big score
          * .sb-small     -> subtle, small text
          * .sb-names     -> centered team names (uniform height)
      - Safe to call on every render; no-ops after first injection.
    """
    # Check session flag to avoid duplicate injection
    if st.session_state.get("_sb_css_injected"):
        return

    # Mark as injected for the remainder of this session
    st.session_state["_sb_css_injected"] = True

    # Inject the CSS styles used by the scoreboard cards
    st.markdown(
        """
        <style>
            /* Primary scoreboard card container styling */
            .sb-card {
                padding: 12px 14px;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px;
                transition: border-color .15s ease, background .15s ease;
                background: rgba(255,255,255,0.02);
                min-height: 200px;                /* uniform height across cards */
                display: flex;
                flex-direction: column;           /* lets the button sit at the bottom */
                justify-content: space-between;
                min-height: 220px;                 /* a bit taller for centered middle block */
            }

            /* Hover effect to highlight card */
            .sb-card:hover {
                border-color: rgba(255,255,255,0.30);
                background: rgba(255,255,255,0.04);
            }

            /* Styling for the score line (large bold centered text) */
            .sb-score {
                font-size: 20px;
                font-weight: 800;
                text-align: center;
                margin-top: 4px;
            }

            /* Smaller text used for game clock and period information */
            .sb-small {
                color: #bdc3c7;
                font-size: 12px;
            }

            /* Styling for team names; height keeps rows aligned */
            .sb-names {
                font-weight: 600;
                text-align: center;
                margin-top: 6px;
                min-height: 22px; /* keeps consistent height even if names wrap differently */
            }

            /* Make logo images sit off the top edge a bit and center nicely */
            .sb-card img {
                display: block;
                margin: 6px auto 6px;            /* top spacing so logos don't touch the top */
            }

          .sb-top {                              /* the top row (logos + middle block) */
                display: grid;
                grid-template-columns: 1fr 1fr 1fr;/* L | M | R */
                align-items: center;               /* vertically center all three cells */
                gap: 8px;                          /* small spacing between columns */
            }

            .sb-mid {                              /* the middle column content */
                text-align: center;
            }

            .sb-vs {                               /* "vs" text styling */
                font-weight: 600;
                margin: 4px 0 6px;
            }

            .sb-meta {                             /* small line under score: state/period/clock */
                color: #bdc3c7;
                font-size: 12px;
                margin-top: 2px;
            }


        </style>
        """,
        unsafe_allow_html=True,
    )

# ======================
# Tiny memo cache for summaries
# ======================

# Create in-memory cache map for event_id -> (timestamp, payload)
_SUMMARY_CACHE: dict[str, Tuple[float, dict]] = {}

def get_summary_cached(event_id: str, ttl_s: int = 15) -> dict:
    """
    @brief  Return ESPN /summary payload with a short TTL to reduce network calls.
    @param  event_id  ESPN event id string.
    @param  ttl_s     Time-to-live in seconds for the memoized payload.
    @return dict      Raw summary JSON.
    """
    # Read current epoch time
    now = time.time()
    # Read existing entry (timestamp, payload) if present
    entry = _SUMMARY_CACHE.get(event_id)
    # If entry exists and is fresh, return cached payload
    if entry and (now - entry[0] <= ttl_s):
        return entry[1]
    # Otherwise fetch fresh payload from ESPN
    raw = fetch_summary(event_id)
    # Store timestamp + payload back to the memo cache
    _SUMMARY_CACHE[event_id] = (now, raw)
    # Return the newly fetched payload
    return raw


# ===================================
# View routing helpers for scoreboard
# ===================================
# Two simple modes for the Scoreboard tab:
MODE_GRID   = "grid"     # Show the scoreboard grid of cards
MODE_DETAIL = "detail"   # Show a single game's expanded details

def _go_to_detail(eid: str) -> None:
    # Save selected game and flip into detail-only mode
    st.session_state["selected_event"] = eid
    st.session_state["sb_mode"] = MODE_DETAIL
    st.rerun()

def _back_to_grid() -> None:
    # Clear mode back to grid (keep last selection if you want)
    st.session_state["sb_mode"] = MODE_GRID
    st.rerun()


# ======================
# Small formatting helpers
# ======================

def _fmt_game_line(g: Dict[str, Any]) -> str:
    """
    @brief  Build a compact one-line summary for legacy list mode.
    @param  g  One normalized game dict from normalize_scoreboard().
    @return str Readable summary line.
    """
    # Read ESPN event id or fallback to "?"
    eid = g.get("espn_event_id") or "?"
    # Uppercase state (PRE/IN/POST); default to empty string when missing
    state = (g.get("state") or "").upper()
    # Read current period or fallback
    per = g.get("period") or "-"
    # Read display clock or fallback
    clk = g.get("display_clock") or "--:--"
    # Pull away/home sub-dicts with {} fallbacks
    away = g.get("away") or {}
    home = g.get("home") or {}
    # Use score value when present; otherwise treat as 0 in this compact view
    ascore = away.get("score", 0) if away.get("score") is not None else 0
    hscore = home.get("score", 0) if home.get("score") is not None else 0
    # Pull display names
    aname = away.get("name", "Away")
    hname = home.get("name", "Home")
    # Compute seconds-left for optional tail
    sec_left = compute_seconds_left(g.get("period"), g.get("display_clock"))
    # Build tail text when seconds-left computed
    tail = f" • {sec_left}s left" if sec_left is not None else ""
    # Return the final line
    return f"{aname} {ascore} @ {hname} {hscore}   ·   {state} · Q{per} · {clk}{tail}"


def _best_odds_for_event(odds_events: List[Dict[str, Any]], espn_event_id: str) -> str:
    """
    @brief  Produce a tiny ML(A)/ML(H) chip string for a given ESPN event (optional).
    @param  odds_events     List of normalized Odds API events (same-slate).
    @param  espn_event_id   ESPN event id to match (when present in odds_events).
    @return str             Short "ML(A) +110 • ML(H) -105" or "" if not available.
    """
    # Return empty string if there is no odds data
    if not odds_events:
        return ""
    try:
        # Filter to odds rows that already carry espn_event_id (best path)
        matches = [e for e in odds_events if e.get("espn_event_id") == espn_event_id]
        # Fallback to scanning all odds events if mapping not present
        pool = matches if matches else odds_events
        # Initialize best price trackers for both sides
        best_home = None
        best_away = None
        # Scan moneyline offers across the pool
        for e in pool:
            ml = (e.get("markets") or {}).get("h2h") or []
            for offer in ml:
                if offer.get("outcome") == "home":
                    best_home = max(best_home or float("-inf"), offer.get("price", float("-inf")))
                if offer.get("outcome") == "away":
                    best_away = max(best_away or float("-inf"), offer.get("price", float("-inf")))
        # Build chip parts when at least one price was found
        parts = []
        if best_away and best_away != float("-inf"):
            parts.append(f"ML(A) {int(best_away):+d}")
        if best_home and best_home != float("-inf"):
            parts.append(f"ML(H) {int(best_home):+d}")
        # Join chips or return empty string when nothing found
        return " • ".join(parts) if parts else ""
    except Exception:
        # Return empty string on any parsing error to keep UI resilient
        return ""


def _state_badge(state: str) -> str:
    """
    @brief  Return a small colored HTML badge for game state.
    @param  state  One of PRE/IN/POST (case-insensitive).
    @return str    HTML snippet (safe for unsafe_allow_html=True).
    """
    # Normalize to upper-case
    s = (state or "").upper()
    # Pick color by state (subtle, readable on dark)
    color = {"IN": "#2ecc71", "PRE": "#3498db", "POST": "#95a5a6"}.get(s, "#7f8c8d")
    # Return a pill-like span
    return (
        f"<span style='background:{color};color:#000;"
        f"padding:2px 6px;border-radius:10px;font-size:11px;font-weight:600'>{s or '-'}</span>"
    )


def _score_str(v: Optional[int]) -> str:
    """
    @brief  Normalize score display to a string with em dash when missing.
    @param  v  Score value or None.
    @return str "—" when None else str(v).
    """
    # Return em dash when value missing
    if v is None:
        return "—"
    # Cast number to string for display
    return str(v)


# ------------------------------------------------------------------
# Moneyline helper for *normalized* Odds API events (your schema).
# Scans offers[] where market=="moneyline" and side is "<Team> ML".
# Returns: (best_away_dec, away_book, best_home_dec, home_book)
# ------------------------------------------------------------------
def _best_ml_from_normalized_offers(
    offers: list[dict],
    *,
    away_name: str,
    home_name: str,
) -> tuple[float | None, str | None, float | None, str | None]:
    best_away = best_home = None
    book_away = book_home = None

    a = (away_name or "").casefold().strip()
    h = (home_name or "").casefold().strip()

    for off in offers or []:
        # only look at moneyline offers (your normalized market key)
        if off.get("market") != "moneyline":
            continue

        # side label is "<Team> ML" per your normalizer
        side_label = (off.get("side") or "").strip()
        # fast path: avoid split failures
        if not side_label.lower().endswith(" ml"):
            continue

        team_label = side_label[:-3].strip().casefold()  # remove trailing " ML"
        price = off.get("decimal_odds")
        if not isinstance(price, (int, float)):
            # if something slipped through, try to coerce
            try:
                price = float(price) # type: ignore
            except Exception:
                continue

        bk = off.get("bookmaker", "—")

        if team_label == a:
            if (best_away is None) or (price > best_away):
                best_away, book_away = price, bk
        elif team_label == h:
            if (best_home is None) or (price > best_home):
                best_home, book_home = price, bk

    return best_away, book_away, best_home, book_home

# ======================
# Card-grid scoreboard (default)
# ======================

def render_scoreboard_cards(
    *,
    games: List[Dict[str, Any]],
    odds_events: Optional[List[Dict[str, Any]]],
    skey,                          # Helper for creating Streamlit widget keys (from app.py)
    cards_per_row: int = 3,        # Number of cards per row in the scoreboard grid
    logo_size: int = 72,           # Pixel size of the team logos (can be increased for clarity)
) -> Optional[str]:
    """
    @brief  Render a logo card grid scoreboard with clickable team matchups.
    @details
      - Displays all current ESPN games as visual cards organized in a grid.
      - Each card shows the away and home team logos, names, and score.
      - Includes the game state (PRE, IN, POST) and time information.
      - When an OddsAPI dataset is passed, shows best Moneyline chips for each game.
      - Clicking "Details" for a specific game switches to a focused detail view
        (render_game_details) and hides the full scoreboard grid.
    @param  games          List of normalized ESPN games (from normalize_scoreboard()).
    @param  odds_events    Optional list of normalized OddsAPI events (for odds chips).
    @param  skey           Helper used to generate unique Streamlit widget keys.
    @param  cards_per_row  Number of cards displayed per row (default = 3).
    @param  logo_size      Size of team logos in pixels (default = 72).
    @return Optional[str]  ESPN event ID of the last selected game, or None if unchanged.
    """

    # ============================================================
    # 1. Ensure CSS for cards is present (inject once per session)
    # ============================================================

    _inject_sb_css_once()

    # ============================================================
    # 2. Render the top-level state filter (ALL / IN / PRE / POST)
    # ============================================================

    # Allows users to quickly view only games in a certain state (in-progress, upcoming, final, etc.)
    state_filter = st.radio(
        "State",                           # Label shown above the radio buttons
        options=["ALL", "IN", "PRE", "POST"],  # Available game states
        index=0,                            # Default selection = "ALL"
        horizontal=True,                    # Display radio buttons horizontally
        key=skey("sb_state_cards"),         # Unique widget key to avoid collisions
    )

    # ============================================================
    # 3. Filter the list of games based on the selected state
    # ============================================================

    # If a specific filter is selected, include only those games
    # Otherwise, include all games (for default view)
    if state_filter != "ALL":
        filtered = [g for g in games if (g.get("state") or "").upper() == state_filter]
    else:
        filtered = list(games)

    # ============================================================
    # 4. Sort games logically by (state, seconds_left)
    # ============================================================

    # Priority order for states:
    #   IN  -> currently in progress (top priority)
    #   POST -> finished
    #   PRE  -> scheduled / not started
    # Sorting ensures that live games always appear first.
    def sort_key(g: Dict[str, Any]):
        # Read and normalize game state
        s = (g.get("state") or "").upper()
        # Compute seconds left in the current period (if available)
        sec = compute_seconds_left(g.get("period"), g.get("display_clock"))
        # Assign rank based on state importance
        rank = {"IN": 0, "POST": 1, "PRE": 2}.get(s, 3)
        # Return tuple (rank, seconds_left) for sorting priority
        return (rank, sec if sec is not None else 99999)

    # Apply sort ordering directly to the filtered list
    filtered.sort(key=sort_key)

    # ============================================================
    # 5. Handle empty slate (no games found)
    # ============================================================

    # Retrieve current selection from session_state if present
    selected = st.session_state.get("selected_event")

    # If there are no games to show, display an informational hint and exit early
    if not filtered:
        st.info("No games available.")
        return selected

    # ============================================================
    # 6. Render the game cards in a grid layout
    # ============================================================

    # The scoreboard is divided into rows, each containing a fixed number
    # of columns (cards_per_row). Streamlit automatically handles resizing.
    for i in range(0, len(filtered), cards_per_row):

        # Slice out the subset of games for the current row
        row_games = filtered[i : i + cards_per_row]

        # Create a Streamlit column group (1 column per game)
        cols = st.columns(len(row_games))

        # Iterate through each column and its corresponding game
        for col, g in zip(cols, row_games):
            with col:
                # Extract event identifiers and team info with safe fallbacks
                eid   = g.get("espn_event_id") or "?"
                away  = g.get("away") or {}
                home  = g.get("home") or {}
                aname = away.get("name", "Away")
                hname = home.get("name", "Home")
                ascr  = away.get("score")
                hscr  = home.get("score")
                state = (g.get("state") or "").upper()
                per   = g.get("period") or "-"
                clk   = g.get("display_clock") or "--:--"

                # ====================================================
                # 6A. Load and render team logos at the desired size
                # ====================================================

                # The helper load_team_logo_from_name() searches your logo assets folder.
                # Returns a PIL image or None if the file isn't found.
                a_logo = load_team_logo_from_name(aname, size=logo_size)
                h_logo = load_team_logo_from_name(hname, size=logo_size)

                # ====================================================
                # 6B. Build the card layout for this matchup
                # ====================================================

                # Streamlit containers allow grouped rendering inside bordered sections.
                # Here we use a custom HTML <div> so we can style the card more freely.
                with st.container(border=False):
                    # Open the styled card div (uses CSS injected above)
                    st.markdown("<div class='sb-card'>", unsafe_allow_html=True)

                    # Create a 3-column internal layout for logos + "vs" text
                    l, m, r = st.columns([1, 1, 1])

                    # ---------- Left Column (Away team) ----------
                    with l:
                        # Display away team logo if found
                        if a_logo is not None:
                            st.image(a_logo, width=logo_size)
                        # Show away team name below the logo
                        st.markdown(f"<div class='sb-names'>{aname}</div>", unsafe_allow_html=True)

                    # ---------- Middle Column ("vs" label) ----------
                    with m:
                        # Small centered "vs" label between logos
                        st.markdown("<div style='text-align:center;margin-top:12px;'>vs</div>", unsafe_allow_html=True)

                    # ---------- Right Column (Home team) ----------
                    with r:
                        # Display home team logo if found
                        if h_logo is not None:
                            st.image(h_logo, width=logo_size)
                        # Show home team name below the logo
                        st.markdown(f"<div class='sb-names'>{hname}</div>", unsafe_allow_html=True)

                    # ====================================================
                    # 6C. Display the score and state/clock information
                    # ====================================================

                    # Render formatted score (use "—" when not started)
                    st.markdown(
                        f"<div class='sb-score'>{_score_str(ascr)} : {_score_str(hscr)}</div>",
                        unsafe_allow_html=True,
                    )

                    # Render state badge (colored) + period and clock info
                    st.markdown(
                        f"{_state_badge(state)} <span class='sb-small'>• Q{per} • {clk}</span>",
                        unsafe_allow_html=True,
                    )

                    # ====================================================
                    # 6D. Render best-odds chips (if odds data available)
                    # ====================================================

                    # Uses _best_odds_for_event() helper to show tiny text like:
                    # "ML(A) +110 • ML(H) -105"
                    chips = _best_odds_for_event(odds_events or [], eid)
                    if chips:
                        # Display the odds chips as caption (smaller text)
                        st.caption(chips)

                    # ====================================================
                    # 6E. Add "Details" button to drill into single-game view
                    # ====================================================

                    # Clicking this button switches the entire scoreboard to "detail" mode
                    # and re-renders the app to display only the selected game's summary.
                    if st.button("Details", key=f"sb_det_{eid}", use_container_width=True):
                        # Call helper to save state and rerun app in detail view
                        _go_to_detail(eid)

                    # ====================================================
                    # 6F. Close the custom card div wrapper
                    # ====================================================

                    st.markdown("</div>", unsafe_allow_html=True)

    # ============================================================
    # 7. Return the most recent selected game (if any)
    # ============================================================

    # Returning the selected event id allows app.py to track state or
    # use this information elsewhere if needed.
    return selected

# ======================
# Legacy radio-list scoreboard (kept for fallback/testing)
# ======================

def render_scoreboard_list(
    *,
    games: List[Dict[str, Any]],
    odds_events: Optional[List[Dict[str, Any]]] = None,
    skey=None,
    sidebar_width_cols: Tuple[int, int] = (3, 9),
) -> Optional[str]:
    """
    @brief  Render the original radio-list scoreboard and return the selected ESPN event id.
    @param  games               List of normalized ESPN games.
    @param  odds_events         Optional normalized Odds API events for chips.
    @param  skey                Key helper from app.py (optional here).
    @param  sidebar_width_cols  Two-column width ratios for filters vs list.
    @return Optional[str]       Selected ESPN event id or existing selection.
    """
    # Create a two-column layout (filters | list)
    col_l, col_r = st.columns(sidebar_width_cols)

    # Render the state filter on the left
    with col_l:
        state_filter = st.radio(
            "State",
            options=["ALL", "IN", "PRE", "POST"],
            index=0,
            horizontal=True,
            key=(skey("sb_state_list") if skey else "sb_state_list"),
        )

    # Render the scoreboard list on the right
    with col_r:
        # Filter by chosen state (or keep all)
        if state_filter != "ALL":
            filtered = [g for g in games if (g.get("state") or "").upper() == state_filter]
        else:
            filtered = list(games)

        # Sort to prioritize live games
        def sort_key(g: Dict[str, Any]):
            s = (g.get("state") or "").upper()
            sec = compute_seconds_left(g.get("period"), g.get("display_clock"))
            rank = {"IN": 0, "POST": 1, "PRE": 2}.get(s, 3)
            return (rank, (sec if sec is not None else 99999))

        # Apply sort order
        filtered.sort(key=sort_key)

        # Build label/value arrays for the radio widget
        labels: List[str] = []
        values: List[str] = []
        for g in filtered:
            eid = g.get("espn_event_id") or "?"
            line = _fmt_game_line(g)
            line += ("   |   " + _best_odds_for_event(odds_events or [], eid)) if odds_events else ""
            labels.append(line)
            values.append(eid)

        # Handle empty slate
        if not labels:
            st.info("No games available.")
            return st.session_state.get("selected_event")

        # Compute default selection index consistent with prior session state
        default_idx = 0
        if "selected_event" in st.session_state:
            if st.session_state["selected_event"] in values:
                default_idx = max(0, values.index(st.session_state["selected_event"]))

        # Render the radio list and capture selection
        sel = st.radio(
            "Scoreboard",
            options=values,
            format_func=lambda eid: labels[values.index(eid)],
            index=default_idx,
            key=(skey("sb_select_list") if skey else "sb_select_list"),
        )

        # Persist current selection to session state
        st.session_state["selected_event"] = sel

        # Return the selected id
        return sel


# ======================
# Public entry point (mode switch)
# ======================

def render_scoreboard(
    *,
    games: List[Dict[str, Any]],
    odds_events: Optional[List[Dict[str, Any]]] = None,
    skey,                              # key helper from app.py
    sidebar_width_cols: Tuple[int, int] = (3, 9),
) -> Optional[str]:
    """
    @brief Router that decides whether to render the grid or the single-game detail.
    @details
      - Reads st.session_state["sb_mode"] (grid/detail).
      - 'grid'  -> render_scoreboard_cards()
      - 'detail'-> render_game_details() with a Back button and a logo header.
    @return Optional[str] currently selected ESPN event id (for app-level awareness).
    """



    # Read mode from session or default to grid
    mode = st.session_state.get("sb_mode", MODE_GRID)
    # Read last selected event (if any)
    selected_eid = st.session_state.get("selected_event")

    # ---------- DETAIL MODE ----------
    if mode == MODE_DETAIL and selected_eid:
        # Back button at the top to return to the scoreboard grid
        if st.button("← Back to scoreboard", key=skey("sb_back"), use_container_width=False):
            _back_to_grid()

        # Render single-game details with a rich header (logos + clean title)
        render_game_details(event_id=selected_eid, show_header=True, header_logo_size=110)
        return selected_eid

    # ---------- GRID MODE ----------
    # Fall back to the card grid (no inline details beneath it)
    return render_scoreboard_cards(
        games=games,
        odds_events=odds_events,
        skey=skey,
        cards_per_row=3,
        logo_size=84,        # you can bump to 96/110 if you want even bigger logos
    )


def render_game_details(*, event_id: str, show_header: bool = False, header_logo_size: int = 96) -> None:
    """
    @brief Render the expanded details for the selected game.
    @details
      - Uses cached /summary (15s TTL) to avoid hammering ESPN.
      - Top header supports large team logos + clean score line (optional via show_header).
      - Hides 'None' in titles by using em-dash for unknown/pre-game scores.
      - Prints status (PRE/IN/POST) + period/clock when present.
      - Venue is shown when available (prefers gameInfo.venue).
      - Team boxscore is displayed inside expanders (away/home).
      - Scoring plays are shown in a single expander (mirrors boxscore UX).
      - OddsAPI data is matched via st.session_state["espn_to_odds"] (fast path)
        and falls back to away/home full-name equality if the map is missing.
    """

    # ------------------------------------------------------------
    # 1) Fetch summary (memoized) and unpack a safe root
    # ------------------------------------------------------------
    # Get a fresh-enough ESPN summary payload for this event id
    summary = get_summary_cached(event_id, ttl_s=15)

    # Prefer ESPN's nested "gamepackageJSON" shape when present
    root = summary["gamepackageJSON"] if "gamepackageJSON" in summary else summary

    # Pull the single competition node safely (header->competitions[0])
    comp = (root.get("header") or {}).get("competitions", [{}])[0]

    # ------------------------------------------------------------
    # 2) Helper to pick one side's friendly bits (name/abbr/score/winner)
    # ------------------------------------------------------------
    def _pick(side: str):
        # Iterate competitors to find the requested side ('home' or 'away')
        for c in comp.get("competitors", []):
            if c.get("homeAway") == side:
                team = c.get("team") or {}
                # Return: full display name, abbreviation, score, winner flag
                return (
                    team.get("displayName", side),
                    team.get("abbreviation", side[:3].upper()),
                    c.get("score"),
                    c.get("winner"),
                )
        # Fallback when structure is unexpected
        return side, side[:3].upper(), None, None

    # Pull both sides now for display + downstream matching
    away_name, away_abbr, away_score, away_win = _pick("away")
    home_name, home_abbr, home_score, home_win = _pick("home")

    # ------------------------------------------------------------
    # 3) Extract status, clock, and venue for compact lines
    # ------------------------------------------------------------
    # Read status from competition node (PRE | IN | POST)
    status_type = (comp.get("status") or {}).get("type") or {}
    state  = (status_type.get("state") or "").upper()                      # PRE | IN | POST
    desc   = status_type.get("description") or status_type.get("state", "")# "Final", "In Progress", etc.
    period = (comp.get("status") or {}).get("period")
    clock  = (comp.get("status") or {}).get("displayClock") or "0:00"

    # Compute whether we are pre-game to control score rendering
    is_pregame = (state == "PRE")

    # ------------------------------------------------------------
    # 4) Optional logo header (large, centered)
    # ------------------------------------------------------------
    if show_header:
        # Attempt to load your PNG logos by full team name (fallback no-op if util missing)
        try:
            from lib.utils import load_team_logo_from_name
        except Exception:
            load_team_logo_from_name = lambda *_a, **_k: None  # safe fallback: no image

        # Compute displayable score for the header
        # - Pre-game: show em-dashes instead of 'None'
        # - Live/Final: show actual numbers, defaulting to em-dash if missing
        left_score  = "—" if is_pregame else (away_score if away_score is not None else "—")
        right_score = "—" if is_pregame else (home_score if home_score is not None else "—")

        # Build a clean, centered row with large logos and names
        c1, c2, c3 = st.columns([1, 1, 1])

        # Left: away logo + name
        with c1:
            a_logo = load_team_logo_from_name(away_name, size=header_logo_size)
            if a_logo is not None:
                st.image(a_logo, width=header_logo_size)
            st.markdown(f"**{away_name}**")

        # Middle: score + status
        with c2:
            # Center the main score line
            st.markdown(
                f"<div style='text-align:center; font-size:22px; font-weight:800; margin-top:8px;'>"
                f"{left_score} : {right_score}</div>",
                unsafe_allow_html=True,
            )
            # Compact status line beneath score (with clock when period exists)
            if period:
                st.markdown(
                    f"<div style='text-align:center; color:#bdc3c7;'>{desc} • Q{period} • {clock}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='text-align:center; color:#bdc3c7;'>{desc}</div>",
                    unsafe_allow_html=True,
                )

        # Right: home logo + name
        with c3:
            h_logo = load_team_logo_from_name(home_name, size=header_logo_size)
            if h_logo is not None:
                st.image(h_logo, width=header_logo_size)
            st.markdown(f"**{home_name}**")

        # Add a thin separator before the body sections
        st.markdown("---")

    # ------------------------------------------------------------
    # 5) Title line (avoid 'None' in pre-game)
    # ------------------------------------------------------------
    # If pre-game, omit scores from the title; otherwise show safe numbers.
    if is_pregame:
        st.subheader(f"{away_name} @ {home_name}")
    else:
        st.subheader(
            f"{away_name} {away_score if away_score is not None else '—'} @ "
            f"{home_name} {home_score if home_score is not None else '—'}"
        )

    # ------------------------------------------------------------
    # 6) Status / Venue / Final lines
    # ------------------------------------------------------------
    # Status: prefer including period/clock when present
    if period:
        st.write(f"**Status:** {desc} • Q{period} • {clock}")
    else:
        st.write(f"**Status:** {desc}")

    # Venue: prefer gameInfo.venue, fallback to comp.venue
    gi = root.get("gameInfo") or {}
    venue = (gi.get("venue") or {}).get("fullName") or (comp.get("venue") or {}).get("fullName")
    if venue:
        st.write(f"**Venue:** {venue}")

    # Final line: only when POST (show W/L flags if present)
    if state == "POST":
        aflag = "W" if away_win else "L" if away_win is not None else "-"
        hflag = "W" if home_win else "L" if home_win is not None else "-"
        st.write(f"**Final:** {away_abbr} {away_score} {aflag}  |  {home_abbr} {home_score} {hflag}")

    # ------------------------------------------------------------
    # 7) Team boxscore (per team) — in expanders
    # ------------------------------------------------------------
    teams = (root.get("boxscore") or {}).get("teams") or []
    if teams:
        st.markdown("### Team Stats")
        # Iterate away/home payloads and render each as an expander
        for t in teams:
            # Compute expander label: "[Home] Team Name" or "[Away] Team Name"
            side = (t.get("homeAway") or "").capitalize()
            label = ((t.get("team") or {}).get("displayName")) or side
            # Wrap the stats list in an expander for compactness
            with st.expander(f"{side}: {label}", expanded=False):
                for s in (t.get("statistics") or []):
                    # Display "metric: value" in a readable bullet list
                    st.write(f"- **{s.get('name')}**: {s.get('displayValue')}")

    # ------------------------------------------------------------
    # 8) Scoring plays — in an expander (parallel to boxscore UX)
    # ------------------------------------------------------------
    scoring = (root.get("scoringPlays") or [])
    if scoring:
        # Top-level section header to mirror Team Stats section
        st.markdown("### Scoring Plays")
        # Compact expander that holds the entire scoring list
        with st.expander(f"All scoring plays ({len(scoring)})", expanded=False):
            # Print each scoring play with period/clock and post-play score
            for sp in scoring:
                per = ((sp.get("period") or {}).get("number")) or "?"
                clk = ((sp.get("clock") or {}).get("displayValue")) or ""
                txt = sp.get("text") or sp.get("description") or ""
                a   = sp.get("awayScore")
                h   = sp.get("homeScore")
                st.write(f"- **Q{per} {clk}** — {txt}  |  {a}-{h}")

    # ------------------------------------------------------------
    # 9) Matched Odds (OddsAPI) — via map or name fallback
    # ------------------------------------------------------------
    # Read normalized OddsAPI events (as loaded by the app)
    odds_events = st.session_state.get("events", []) or []

    # Fast path: use prebuilt map from app.py (espn_event_id -> odds game_id)
    link_map = st.session_state.get("espn_to_odds", {}) or {}
    odds_game_id = link_map.get(event_id)

    # Fallback path: simple lowercased full-name equality on (away, home)
    if not odds_game_id and odds_events:
        a_lc = (away_name or "").strip().lower()
        h_lc = (home_name or "").strip().lower()
        for ev in odds_events:
            ev_away = (ev.get("away") or ev.get("away_team") or "").strip().lower()
            ev_home = (ev.get("home") or ev.get("home_team") or "").strip().lower()
            if ev_away == a_lc and ev_home == h_lc:
                odds_game_id = ev.get("game_id")
                break

    # If a matching OddsAPI event exists, pull the payload for display
    odds_payload = next((e for e in odds_events if e.get("game_id") == odds_game_id), None) if odds_game_id else None

    # Render a compact odds section if we have matched data
    if odds_payload:
        # Section header for odds
        st.markdown("### Live Odds (Matched from The Odds API)")

        # ------------------------------------------------------------
        # A) Canonicalize markets + group offers safely
        # ------------------------------------------------------------

        # -- helper: normalize various market labels into canonical buckets
        def _canonical_market(m: str | None) -> str:
            """
            @brief Map provider-specific market labels into our canonical buckets.
            @details
              - Many providers use 'h2h' for moneyline, 'spreads' for spread, 'totals' for total.
              - We coerce a variety of synonyms into: 'moneyline' | 'spread' | 'total' | 'other'.
            """
            if not m:
                return "other"
            m_lc = str(m).strip().lower()
            # Moneyline aliases
            if m_lc in {"h2h", "ml", "moneyline", "money_line"}:
                return "moneyline"
            # Spread aliases
            if m_lc in {"spread", "spreads", "point_spread", "handicap"}:
                return "spread"
            # Total (over/under) aliases
            if m_lc in {"total", "totals", "over_under", "ou"}:
                return "total"
            # Everything else
            return "other"

        # -- helper: access numeric odds regardless of field naming/format
        def _as_decimal_odds(offer: dict) -> float | None:
            """
            @brief Return a numeric decimal-odds value for an offer if possible.
            @details
              - Tries 'decimal_odds' directly when provided.
              - Falls back to 'price' (some normalizations use this) if numeric.
              - If 'price' looks like an American line (+145 / -110), convert to decimal:
                    +X => 1 + X/100
                    -Y => 1 + 100/Y
            """
            # 1) direct decimal
            v = offer.get("decimal_odds", None)
            if isinstance(v, (int, float)):
                return float(v)

            # 2) a generic 'price' that might be decimal or american
            p = offer.get("price", None)
            if isinstance(p, (int, float)):
                # Treat as decimal if > 1.01; else if in typical american range convert
                if float(p) >= 1.01:
                    return float(p)
                # Rare/odd edge case: very small float—ignore
                return None

            # 3) strings (e.g., "+145" or "-110" or "1.91")
            if isinstance(p, str):
                ps = p.strip()
                # Try decimal string
                try:
                    val = float(ps)
                    if val >= 1.01:
                        return val
                except Exception:
                    pass
                # Try American string
                if ps.startswith("+") or ps.startswith("-"):
                    try:
                        a = int(ps)
                        if a > 0:
                            return 1.0 + (a / 100.0)
                        if a < 0:
                            return 1.0 + (100.0 / abs(a))
                    except Exception:
                        return None

            # Nothing usable found
            return None

        # -- build buckets with canonical market names
        offers = odds_payload.get("offers", []) or []
        buckets: dict[str, list[dict]] = {"moneyline": [], "spread": [], "total": [], "other": []}
        for off in offers:
            canon = _canonical_market(off.get("market"))
            buckets[canon].append(off)

        # (Optional) quick visibility to confirm what we actually got; comment out once happy
        # st.caption(
        #     f"Offers: ML={len(buckets['moneyline'])}  |  Spread={len(buckets['spread'])}  |  Total={len(buckets['total'])}  |  Other={len(buckets['other'])}"
        # )

        # ------------------------------------------------------------
        # B) MONEYLINE — robust best-price selection (away/home)
        # ------------------------------------------------------------
        with st.expander("Moneyline", expanded=True):
            ml_away, ml_away_bk, ml_home, ml_home_bk = _best_ml_from_normalized_offers(
                odds_payload.get("offers", []),
                away_name=away_name,
                home_name=home_name,
            )
            c1, c2 = st.columns(2)
            c1.write(f"- **Away ({away_name})**: {ml_away:.2f} ({ml_away_bk})" if ml_away else "- **Away:** —")
            c2.write(f"- **Home ({home_name})**: {ml_home:.2f} ({ml_home_bk})" if ml_home else "- **Home:** —")

        # ------------------------------------------------------------
        # C) SPREAD — unchanged except for canonicalization
        # ------------------------------------------------------------
        if buckets["spread"]:
            with st.expander("Spread", expanded=False):
                for off in buckets["spread"][:6]:
                    bk   = off.get("bookmaker", "—")
                    side = off.get("side", "—")                  # home / away
                    line = off.get("line", "—")                  # e.g., -3.5
                    dec  = _as_decimal_odds(off) or "—"          # show decimal if available
                    st.write(f"- **{bk}** — {side} {line} @ {dec}")

        # ------------------------------------------------------------
        # D) TOTAL — unchanged except for canonicalization
        # ------------------------------------------------------------
        if buckets["total"]:
            with st.expander("Total", expanded=False):
                for off in buckets["total"][:6]:
                    bk   = off.get("bookmaker", "—")
                    side = off.get("side", "—")                  # Over / Under
                    line = off.get("line", "—")                  # e.g., 44.5
                    dec  = _as_decimal_odds(off) or "—"
                    st.write(f"- **{bk}** — {side} {line} @ {dec}")

        # ------------------------------------------------------------
        # E) OTHER — keep around for completeness/QA
        # ------------------------------------------------------------
        if buckets["other"]:
            with st.expander("Other Markets", expanded=False):
                for off in buckets["other"][:8]:
                    bk   = off.get("bookmaker", "—")
                    mkt  = off.get("market", "—")
                    side = off.get("side", "—")
                    dec  = _as_decimal_odds(off) or "—"
                    st.write(f"- **{bk}** — {mkt} — {side} @ {dec}")
    else:
        # If no odds matched, show a soft hint (keeps UI clean)
        st.caption("No matching OddsAPI event found for this game (yet).")