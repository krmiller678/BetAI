"""
@file        views/scoreboard/game_details.py
@brief       Single-game Details view (ESPN-backed) with live odds + agent actions.
@details
  Responsibilities
  - Fetch and memo-cache ESPN `/summary` for a given `event_id` (short TTL).
  - Normalize ESPN's payload shape (handles optional `gamepackageJSON` wrapper).
  - Render:
      • Optional large header (logos + centered score/status)
      • Compact title/status/venue/final line
      • Team boxscore (expanders)
      • Scoring plays (expander)
  - Match the corresponding OddsAPI event using session maps (fast path) with a
    team-name fallback, then display all available offers grouped by market.
  - Provide Evaluate / Place (paper) buttons per offer that call the BettingAgent.
    Odds are sent as AMERICAN (+145 / -110); the agent converts to decimal internally.

  Inputs (function params)
  - event_id (str): ESPN event identifier to display.
  - show_header (bool): Whether to render the large logo header row.
  - header_logo_size (int): Size of header logos (square).
  - agent (BettingAgent): Agent instance used for EV/kelly/placement logic.
  - ev_threshold (float): Minimum EV required to classify as BET.
  - skey (Callable[..., str]): Helper to build stable Streamlit widget keys.

  Session State (read/write)
  - events: List of normalized OddsAPI events (for matching + offers).
  - espn_to_odds: Dict[event_id -> game_id] fast map for ESPN↔Odds linking.
  - last_recs: List of recent recommendation dicts (appended here).
  - open_bets: Dict[id -> bet_record] (paper trades; appended on Place).

  Key Helpers (defined in this module)
  - get_summary_cached(): in-memory TTL cache for ESPN /summary.
  - parse_summary_root(): normalizes ESPN root + first competition node.
  - pick_side(): extracts (name/abbr/score/winner) for 'home'/'away'.
  - american_from_offer(), _american_from_decimal(): robust odds extraction/convert.
  - group_offers_by_market(): buckets offers into moneyline/spread/total/other.
  - match_odds_event(): resolves OddsAPI event payload for this ESPN `event_id`.
  - render_header(), render_title_and_status(), render_team_stats(), render_scoring_plays():
    focused UI sections that keep the main render small and readable.
  - render_offers_bucket(): lists offers with Evaluate/Place buttons and context.

  Notes
  - Designed to be called from the scoreboard router when switching into "detail" mode.
  - Fails soft on missing fields; unknown values render as em dashes or are omitted.
  - Memo TTL defaults to 15s to reduce network calls while keeping UI fresh enough.
"""

# ============================================================
# Imports
# ============================================================

# Enable postponed evaluation of annotations (cleaner forward refs)
from __future__ import annotations

# Standard library imports
import time                                                                 # Memoize ESPN /summary responses with a short TTL
from typing import Any, Callable, Dict, List, Optional, Tuple, Literal      # Typing for clarity

# Third-party imports
import streamlit as st                                                      # Core Streamlit library for UI rendering

# Internal libs — ESPN summary + team logos
from betai.integrations.pbp_api import fetch_summary                        # Fetches ESPN /summary for a specific event_id
from lib.utils import load_team_logo_from_name                              # Loads PNG logos by exact team display name


# ============================================================
# In-memory cache (ESPN /summary)
# ============================================================

# Create in-memory cache: event_id -> (timestamp, payload)
_SUMMARY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


# ============================================================
# Helpers — Data Fetching / Root Normalization
# ============================================================

def get_summary_cached(event_id: str, ttl_s: int = 15) -> Dict[str, Any]:
    """
    @brief      Return ESPN `/summary` payload with a short TTL to reduce network calls.
    @details
      - Uses an in-memory dict keyed by `event_id` to store (timestamp, payload).
      - If the cached entry is not older than `ttl_s` seconds, the cached value is returned.
      - Otherwise, a fresh call to `fetch_summary(event_id)` is made and saved.

    @param      event_id   ESPN event identifier string.
    @param      ttl_s      Time-to-live for the memoized object (seconds).

    @return     Dict[str, Any]  Raw payload from ESPN (possibly carrying `gamepackageJSON`).
    """
    # Read current time
    now: float = time.time()

    # Lookup cached entry
    entry: Optional[Tuple[float, Dict[str, Any]]] = _SUMMARY_CACHE.get(event_id)

    # Return cached payload when fresh
    if entry is not None and (now - entry[0] <= ttl_s):

        return entry[1]
    
    # Fetch fresh payload
    raw: Dict[str, Any] = fetch_summary(event_id)

    # Store timestamp + payload
    _SUMMARY_CACHE[event_id] = (now, raw)

    # Return payload
    return raw


def parse_summary_root(summary: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    @brief      Normalize the ESPN `/summary` structure into a consistent pair.
    @details
      - ESPN sometimes wraps content under `gamepackageJSON`; other times fields are at the root.
      - This helper returns a unified `root` plus the first competition node `comp`.

    @param      summary   Raw dict returned by `fetch_summary(event_id)`.

    @return     Tuple[Dict[str, Any], Dict[str, Any]]
               - root: unified object carrying `header`, `boxscore`, `scoringPlays`, etc.
               - comp: the first competition node (or `{}` if missing).
    """
    # Choose nested or flat root
    root: Dict[str, Any] = summary["gamepackageJSON"] if "gamepackageJSON" in summary else summary

    # Read header map
    header: Dict[str, Any] = root.get("header") or {}

    # Read competitions list
    competitions: List[Dict[str, Any]] = header.get("competitions") or [{}]

    # Pick first competition safely
    comp: Dict[str, Any] = competitions[0] if competitions else {}

    # Return normalized pair
    return root, comp


def pick_side(comp: Dict[str, Any], side: Literal["home", "away"]) -> Tuple[str, str, Optional[int], Optional[bool]]:
    """
    @brief      Extract display-friendly fields for one side of the competition.
    @details
      - Scans `comp["competitors"]` to find the entry with `homeAway == side`.
      - Returns a tuple suitable for title + header rendering.

    @param      comp    Competition node obtained from `parse_summary_root`.
    @param      side    'home' or 'away'.

    @return     Tuple[str, str, Optional[int], Optional[bool]]
               (display_name, abbreviation, score, winner_flag)
    """
    # Read competitor list
    competitors: List[Dict[str, Any]] = comp.get("competitors", []) or []

    # Scan for requested side
    for c in competitors:
        if c.get("homeAway") == side:
            team: Dict[str, Any] = c.get("team") or {}
            name: str = team.get("displayName", side)
            abbr: str = team.get("abbreviation", side[:3].upper())
            score: Optional[int] = c.get("score")
            winner: Optional[bool] = c.get("winner")
            return name, abbr, score, winner
        
    # Fallback tuple when structure is unexpected
    return side, side[:3].upper(), None, None


# ============================================================
# Helpers — Odds (American format) and Grouping
# ============================================================

def american_from_offer(offer: Dict[str, Any]) -> Optional[int]:
    """
    @brief      Extract an American-odds integer (+145 / -110) from a normalized offer.
    @details
      This function normalizes heterogeneous price fields into a single American integer.
      It checks, in order:
        1) offer["american"]      -> already American-odds; coerce to int if needed
        2) offer["price"] (str)   -> strings like "+145" or "-110"; parse as int
        3) offer["decimal_odds"]  -> convert from decimal to American
        4) offer["price"] (num)   -> numeric that looks like decimal (>= 1.01); convert
      Returns None when no usable odds are present.

    @param      offer   Normalized offer dictionary with bookmaker pricing fields.

    @return     Optional[int]  American-odds integer (e.g., +145, -110) or None if unavailable.
    """

    # Read a direct American-odds field when present
    if "american" in offer:
        # Capture the raw value (int/float/str)
        v = offer.get("american")
        # Return directly when already an int
        if isinstance(v, int):
            return v
        # Round floats to nearest int (rare but safe)
        if isinstance(v, float):
            return int(round(v))
        # Parse strings like "+145" or "-110"
        if isinstance(v, str):
            try:
                return int(v.strip())
            except Exception:
                pass  # fall through to other sources

    # Inspect a generic string "price" like "+145" / "-110"
    p = offer.get("price")
    # If it's a signed string, attempt integer parse
    if isinstance(p, str) and (p.startswith("+") or p.startswith("-")):
        try:
            return int(p.strip())
        except Exception:
            pass  # continue to decimal paths

    # Read canonical decimal odds when present (float or int)
    d = offer.get("decimal_odds")
    # If decimal is plausible (>= 1.01), convert to American
    if isinstance(d, (int, float)) and float(d) >= 1.01:
        return _american_from_decimal(float(d))

    # If "price" is numeric and looks like decimal (>= 1.01), convert to American
    if isinstance(p, (int, float)) and float(p) >= 1.01:
        return _american_from_decimal(float(p))

    # No usable price found; return None
    return None


def _american_from_decimal(dec: float) -> Optional[int]:
    """
    @brief      Convert decimal odds to an American-odds integer.
    @details
      Implements the standard mapping:
        - For dec >= 2.0:
              american = round((dec - 1) * 100)
          (e.g., 2.50 -> +150)
        - For 1.01 <= dec < 2.0:
              american = round(-100 / (dec - 1))
          (e.g., 1.83 -> -120)
      Values under 1.01 are invalid for odds and produce None.

    @param      dec   Decimal odds value (>= 1.01).

    @return     Optional[int]  American-odds integer or None if invalid input.
    """

    # Reject invalid tiny decimals
    if dec < 1.01:
        return None

    # Compute the profit multiple b = dec - 1 (used by both branches)
    b: float = dec - 1.0

    # If the decimal is 2.0 or higher, it maps to positive American odds
    if dec >= 2.0:
        # Multiply by 100 and round to nearest integer
        return int(round(b * 100.0))

    # For decimals in [1.01, 2.0), map to negative American odds
    if b <= 0.0:
        # Defensive guard; should not happen given dec >= 1.01
        return None

    # Compute negative American by inverting b
    return int(round(-100.0 / b))


def group_offers_by_market(offers: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    @brief      Group normalized offers by market bucket.
    @details
      - Buckets: 'moneyline' | 'spread' | 'total' | 'other'
      - Any unexpected `offer["market"]` falls into 'other'.

    @param      offers   List of normalized offer dicts.

    @return     Dict[str, List[Dict[str, Any]]]  Buckets keyed by market.
    """
    # Initialize buckets
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "moneyline": [],
        "spread": [],
        "total": [],
        "other": [],
    }

    # Distribute offers
    for off in offers or []:
        m = (off.get("market") or "other")
        if m not in buckets:
            m = "other"
        buckets[m].append(off)

    # Return buckets
    return buckets


# ============================================================
# Helpers — Odds/Events Matching + UI Sections
# ============================================================

def match_odds_event(event_id: str, away_name: str, home_name: str) -> Optional[Dict[str, Any]]:
    """
    @brief      Find the OddsAPI event payload matched to this ESPN event.
    @details
      - Fast path: use `st.session_state["espn_to_odds"][event_id] -> game_id`.
      - Fallback: case-insensitive equality on away/home full names.

    @param      event_id    ESPN event id string.
    @param      away_name   Away team full display name from ESPN.
    @param      home_name   Home team full display name from ESPN.

    @return     Optional[Dict[str, Any]]  Matched odds event payload, or None if not found.
    """
    # Read events from session
    odds_events: List[Dict[str, Any]] = st.session_state.get("events", []) or []

    # Read id map from session
    link_map: Dict[str, str] = st.session_state.get("espn_to_odds", {}) or {}

    # Attempt id-based match
    game_id: Optional[str] = link_map.get(event_id)

    # Fallback by name equality
    if not game_id and odds_events:
        a_lc: str = (away_name or "").strip().lower()
        h_lc: str = (home_name or "").strip().lower()

        for ev in odds_events:
            ev_away: str = (ev.get("away") or ev.get("away_team") or "").strip().lower()
            ev_home: str = (ev.get("home") or ev.get("home_team") or "").strip().lower()
            
            if ev_away == a_lc and ev_home == h_lc:
                game_id = ev.get("game_id")
                break

    # Return payload by matched id
    return next((e for e in odds_events if e.get("game_id") == game_id), None) if game_id else None


def render_header(away_name: str,
                  home_name: str,
                  away_score: Optional[int],
                  home_score: Optional[int],
                  is_pregame: bool,
                  desc: str,
                  period: Optional[int],
                  clock: str,
                  header_logo_size: int) -> None:
    """
    @brief      Render the optional large header row (logos + centered score/status).
    @details
      - Logos are loaded by full display name via `load_team_logo_from_name`.
      - Scores show em-dashes when pre-game or missing.

    @param      away_name         Away team full display name.
    @param      home_name         Home team full display name.
    @param      away_score        Away current score (or None).
    @param      home_score        Home current score (or None).
    @param      is_pregame        True if state == 'PRE'.
    @param      desc              Status description (e.g., "Final", "In Progress").
    @param      period            Period/quarter number (or None).
    @param      clock             Display clock string (e.g., "12:34").
    @param      header_logo_size  Pixel size for logos (square).
    """
    # Compute safe score strings
    left_score: str = "—" if is_pregame else (str(away_score) if away_score is not None else "—")
    right_score: str = "—" if is_pregame else (str(home_score) if home_score is not None else "—")

    # Build columns
    c1, c2, c3 = st.columns([1, 1, 1])

    # Left logo + name
    with c1:
        a_logo = load_team_logo_from_name(away_name, size=header_logo_size)
        if a_logo is not None:
            st.image(a_logo, width=header_logo_size)
        st.markdown(f"**{away_name}**")

    # Center score + status
    with c2:
        st.markdown(
            f"<div style='text-align:center; font-size:22px; font-weight:800; margin-top:8px;'>"
            f"{left_score} : {right_score}</div>",
            unsafe_allow_html=True,
        )
        if period is not None:
            st.markdown(
                f"<div style='text-align:center; color:#bdc3c7;'>{desc} • Q{period} • {clock}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='text-align:center; color:#bdc3c7;'>{desc}</div>",
                unsafe_allow_html=True,
            )

    # Right logo + name
    with c3:
        h_logo = load_team_logo_from_name(home_name, size=header_logo_size)
        if h_logo is not None:
            st.image(h_logo, width=header_logo_size)
        st.markdown(f"**{home_name}**")

    # Divider
    st.markdown("---")


def render_title_and_status(away_name: str,
                            home_name: str,
                            away_score: Optional[int],
                            home_score: Optional[int],
                            is_pregame: bool,
                            desc: str,
                            period: Optional[int],
                            clock: str,
                            venue: Optional[str],
                            state: str,
                            away_abbr: str,
                            home_abbr: str,
                            away_win: Optional[bool],
                            home_win: Optional[bool]) -> None:
    """
    @brief      Render the compact title, status, venue, and final line (if POST).
    @details
      - Title shows "Away @ Home" for pre-game, and "Away X @ Home Y" otherwise.
      - Status line includes period + clock when available.

    @param      away_name   Away display name.
    @param      home_name   Home display name.
    @param      away_score  Away score or None.
    @param      home_score  Home score or None.
    @param      is_pregame  True when state == 'PRE'.
    @param      desc        Status description ("Final", etc.).
    @param      period      Period number or None.
    @param      clock       Clock string (e.g., "0:00").
    @param      venue       Venue full name or None.
    @param      state       State code ('PRE'/'IN'/'POST').
    @param      away_abbr   Away 3-letter abbreviation.
    @param      home_abbr   Home 3-letter abbreviation.
    @param      away_win    Away winner flag or None.
    @param      home_win    Home winner flag or None.

    @return     None
    """
    # Title
    if is_pregame:
        st.subheader(f"{away_name} @ {home_name}")

    else:
        a_txt: str = str(away_score) if away_score is not None else "—"
        h_txt: str = str(home_score) if home_score is not None else "—"
        st.subheader(f"{away_name} {a_txt} @ {home_name} {h_txt}")

    # Status
    if period is not None:
        st.write(f"**Status:** {desc} • Q{period} • {clock}")

    else:
        st.write(f"**Status:** {desc}")

    # Venue
    if venue:
        st.write(f"**Venue:** {venue}")

    # Final line
    if state == "POST":
        aflag: str = "W" if away_win else "L" if away_win is not None else "-"
        hflag: str = "W" if home_win else "L" if home_win is not None else "-"
        st.write(f"**Final:** {away_abbr} {away_score} {aflag}  |  {home_abbr} {home_score} {hflag}")


def render_team_stats(root: Dict[str, Any]) -> None:
    """
    @brief      Render team boxscore stats inside expanders.
    @details
      - Scans `root["boxscore"]["teams"]` for two entries (home/away).
      - Each team list is printed as "metric: value" bullets.

    @param      root   Unified ESPN root from `parse_summary_root`.

    @return     None
    """
    # Pull teams list
    teams: List[Dict[str, Any]] = (root.get("boxscore") or {}).get("teams") or []

    # Exit early when absent
    if not teams:
        return
    
    # Section header
    st.markdown("### Team Stats")

    # Expanders per team
    for t in teams:
        side: str = (t.get("homeAway") or "").capitalize()
        label: str = ((t.get("team") or {}).get("displayName")) or side
        with st.expander(f"{side}: {label}", expanded=False):
            for s in (t.get("statistics") or []):
                st.write(f"- **{s.get('name')}**: {s.get('displayValue')}")


def render_scoring_plays(root: Dict[str, Any]) -> None:
    """
    @brief      Render scoring plays list inside an expander.
    @details
      - Shows period + clock + text, and post-play score snapshot.

    @param      root   Unified ESPN root from `parse_summary_root`.

    @return     None
    """
    # Pull scoring list
    scoring: List[Dict[str, Any]] = root.get("scoringPlays") or []
    # Exit when empty
    if not scoring:
        return
    # Header
    st.markdown("### Scoring Plays")
    # Expander with count
    with st.expander(f"All scoring plays ({len(scoring)})", expanded=False):
        for sp in scoring:
            per = ((sp.get("period") or {}).get("number")) or "?"
            clk = ((sp.get("clock") or {}).get("displayValue")) or ""
            txt = sp.get("text") or sp.get("description") or ""
            a = sp.get("awayScore")
            h = sp.get("homeScore")
            st.write(f"- **Q{per} {clk}** — {txt}  |  {a}-{h}")


def render_offers_bucket(title: str,
                         items: List[Dict[str, Any]],
                         game_id: str,
                         agent: Any,
                         ev_threshold: float,
                         skey: Callable[..., str],
                         home_team: str,
                         away_team: str) -> None:
    """
    @brief      Render one market bucket of offers with Evaluate / Place actions.
    @details
      - Each "bucket" represents a market type (Moneyline, Spread, Total, Other).
      - Inside each bucket, every bookmaker offer is displayed in a uniform row layout:
            [Bookmaker | Market | Side @ +145] [Evaluate] [Place] [Context ▼]
      - The function also handles interaction logic:
            - 'Evaluate' passes the odds to the agent for an EV (expected value) calculation.
            - 'Place' simulates placing a bet (paper trading), logging it to session_state.
      - All odds are displayed and sent as AMERICAN format (+145 / -110).
        The agent converts them internally into decimal odds.

    @param      title         Section header label (e.g., "Moneyline").
    @param      items         List of normalized offers for this market.
    @param      game_id       Unique game identifier (used for stable widget keys).
    @param      agent         Instance of BettingAgent handling EV and bet logic.
    @param      ev_threshold  EV threshold that determines if a bet qualifies ("BET" vs "NO BET").
    @param      skey          Helper function that builds unique Streamlit widget keys.

    @return     None
    """

    # ------------------------------------------------------------
    # If there are no offers in this market bucket, skip rendering
    # ------------------------------------------------------------
    if not items:
        return

    # ------------------------------------------------------------
    # Display the section header for this market (e.g., **Moneyline**)
    # ------------------------------------------------------------
    st.markdown(f"**{title}**")

    # ------------------------------------------------------------
    # Iterate through every bookmaker offer inside this bucket
    # ------------------------------------------------------------
    for idx, offer in enumerate(items):

        # --------------------------------------------------------
        # Create four columns for layout:
        #   c0 -> Offer info (book, market, side, odds)
        #   c1 -> Evaluate button
        #   c2 -> Place (paper) button
        #   c3 -> Context expander (raw JSON details)
        # --------------------------------------------------------
        c0, c1, c2 = st.columns([3, 1, 1])

        # --------------------------------------------------------
        # Extract relevant offer information
        # --------------------------------------------------------
        book: str = offer.get("bookmaker", "—")         # Bookmaker name
        market: str = offer.get("market", "—")          # Market type (moneyline, spread, etc.)
        side: str = offer.get("side", "—")              # Team or bet side label

        # --------------------------------------------------------
        # Convert or extract AMERICAN odds (+145 / -110)
        # --------------------------------------------------------
        am: Optional[int] = american_from_offer(offer)

        # --------------------------------------------------------
        # Format odds as "+145" / "-110" / "—" for display
        # --------------------------------------------------------
        am_str: str = f"{am:+d}" if isinstance(am, int) else "—"

        # --------------------------------------------------------
        # Render the offer summary in the first column
        # Example: **FanDuel** — moneyline — **Detroit Lions ML** @ +145
        # --------------------------------------------------------
        c0.markdown(f"**{book}** — {market} — **{side}** @ {am_str}")

        # --------------------------------------------------------
        # Add an expandable JSON viewer in the last column
        # so users can inspect the raw offer context (debug or info)
        # --------------------------------------------------------
        # with c3.expander("Context", expanded=False):
        #     st.json(offer.get("context", {}))

        # --------------------------------------------------------
        # Generate unique Streamlit keys for each button
        # This prevents duplicate-widget errors when multiple games render
        # --------------------------------------------------------
        eval_key: str = skey("det-eval", game_id, market, book, idx)
        place_key: str = skey("det-place", game_id, market, book, idx)

        # ========================================================
        # Evaluate Button — Calls agent to compute Expected Value
        # ========================================================
        if c1.button("Evaluate", key=eval_key, width='stretch'):

            # Guard against missing or invalid odds
            if am is None:
                st.warning("No usable American odds on this offer.")

            else:
                # ------------------------------------------------
                # Pass offer information to the agent for EV logic
                # Agent handles probability model + bankroll sizing
                # ------------------------------------------------

                base_ctx = offer.get("context", {}) or {}
                ctx = {**base_ctx, "home_team": home_team, "away_team": away_team}

                rec: Dict[str, Any] = agent.make_recommendation(
                    market=market.lower(),                              # Normalize market name
                    side=side,                                          # Side label ("DET ML")
                    context=ctx,                                        # Context dictionary (team stats, game info)
                    odds_value=float(am),                               # American odds as float
                    odds_type="american",                               # Format type (agent will convert internally)
                    ev_threshold=ev_threshold,                          # EV threshold for "BET"/"NO BET"
                )

                # ------------------------------------------------
                # Log this recommendation to Streamlit session_state
                # ------------------------------------------------
                st.session_state.last_recs.append(rec)

                # ------------------------------------------------
                # Display a quick feedback toast summarizing result
                # Example: "BET — EV +0.043 — stake $23.45"
                # ------------------------------------------------
                st.toast(f"{rec['decision']} — EV {rec['ev']:.3f} — stake ${rec['stake']:.2f}")

        # ========================================================
        # Place (paper) Button — Simulates placing a virtual bet
        # ========================================================
        if c2.button("Place (paper)", key=place_key, width='stretch'):

            # Guard against missing odds
            if am is None:
                st.warning("No usable American odds on this offer.")

            else:
                # ------------------------------------------------
                # Generate the same recommendation record for placing
                # ------------------------------------------------
                base_ctx = offer.get("context", {}) or {}
                ctx = {**base_ctx, "home_team": home_team, "away_team": away_team}
                
                rec: Dict[str, Any] = agent.make_recommendation(
                    market=market.lower(),
                    side=side,
                    context=ctx,
                    odds_value=float(am),
                    odds_type="american",
                    ev_threshold=ev_threshold,
                )

                # ------------------------------------------------
                # Add this record to the Open Bets list (active paper trades)
                # ------------------------------------------------
                st.session_state.open_bets[rec["id"]] = rec

                # ------------------------------------------------
                # Also append to the recommendations log for continuity
                # ------------------------------------------------
                st.session_state.last_recs.append(rec)

                # ------------------------------------------------
                # Show success message to confirm paper placement
                # ------------------------------------------------
                st.success("Placed (paper). See 'Open Bets' tab.")


# ============================================================
# Public Render — depends on helpers above
# ============================================================

def render_game_details(
    *,
    event_id: str,
    show_header: bool = False,
    header_logo_size: int = 96,
    agent: Any,                  
    ev_threshold: float,         
    skey: Callable[..., str],    
) -> None:
    """
    @brief      Render the expanded Details view for a single game.
    @details
      - Fetches + memo-caches ESPN `/summary` (15s TTL).
      - Renders header (optional), title/status/venue/final, team stats, scoring plays.
      - Matches OddsAPI event and lists offers with Evaluate / Place actions (American odds).

    @param      event_id          ESPN event id for the selected game.
    @param      show_header       When True, draws the large logo header.
    @param      header_logo_size  Pixel size for header logos.
    @param      agent             BettingAgent instance.
    @param      ev_threshold      EV threshold to classify BET vs NO BET.
    @param      skey              Helper for stable Streamlit widget keys.

    @return     None
    """
    # Fetch summary (cached)
    summary: Dict[str, Any] = get_summary_cached(event_id, ttl_s=15)

    # Normalize root + competition
    root, comp = parse_summary_root(summary)

    # Pick both sides
    away_name, away_abbr, away_score, away_win = pick_side(comp, "away")
    home_name, home_abbr, home_score, home_win = pick_side(comp, "home")

    # Status fields
    status_type: Dict[str, Any] = (comp.get("status") or {}).get("type") or {}
    state: str = (status_type.get("state") or "").upper()
    desc: str = status_type.get("description") or status_type.get("state", "")
    period: Optional[int] = (comp.get("status") or {}).get("period")
    clock: str = (comp.get("status") or {}).get("displayClock") or "0:00"
    is_pregame: bool = (state == "PRE")

    # Venue (prefer gameInfo.venue)
    gi: Dict[str, Any] = root.get("gameInfo") or {}
    venue: Optional[str] = (gi.get("venue") or {}).get("fullName") or (comp.get("venue") or {}).get("fullName")

    # Optional header
    if show_header:
        render_header(
            away_name=away_name,
            home_name=home_name,
            away_score=away_score,
            home_score=home_score,
            is_pregame=is_pregame,
            desc=desc,
            period=period,
            clock=clock,
            header_logo_size=header_logo_size,
        )

    # Title + status
    render_title_and_status(
        away_name=away_name,
        home_name=home_name,
        away_score=away_score,
        home_score=home_score,
        is_pregame=is_pregame,
        desc=desc,
        period=period,
        clock=clock,
        venue=venue,
        state=state,
        away_abbr=away_abbr,
        home_abbr=home_abbr,
        away_win=away_win,
        home_win=home_win,
    )

    # Team stats
    render_team_stats(root)

    # Scoring plays
    render_scoring_plays(root)

    # Odds matching
    odds_payload: Optional[Dict[str, Any]] = match_odds_event(event_id, away_name, home_name)

    # Offers (Live-Board style)
    if odds_payload is not None:
        st.markdown("### Live Odds Offers")
        offers: List[Dict[str, Any]] = odds_payload.get("offers", []) or []
        buckets: Dict[str, List[Dict[str, Any]]] = group_offers_by_market(offers)
        game_id: str = odds_payload.get("game_id", "—")
        render_offers_bucket("Moneyline", buckets.get("moneyline", []), game_id, agent, ev_threshold, skey, home_team=home_name, away_team=away_name)
        render_offers_bucket("Spread",    buckets.get("spread",    []), game_id, agent, ev_threshold, skey, home_team=home_name, away_team=away_name)
        #render_offers_bucket("Total",     buckets.get("total",     []), game_id, agent, ev_threshold, skey, home_team=home_name, away_team=away_name)
        #render_offers_bucket("Other",     buckets.get("other",     []), game_id, agent, ev_threshold, skey, home_team=home_name, away_team=away_name)
    else:
        st.caption("No matching OddsAPI event found for this game (yet).")

