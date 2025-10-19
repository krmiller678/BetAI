"""
@file        live_board.py
@brief       Live Board view — logos, live/finished scores, and bookmaker offers.
@details
  - Displays each matchup with team logos and a compact score/status badge.
  - Pulls normalized scores via lib.api.fetch_scores() (short-cached by provider).
  - Lists bookmaker offers and allows Evaluate / Place (paper) actions with the agent.
  - Uses exact team-name PNGs in assets/team-logos (e.g., "Detroit Lions.png").
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations                  # Enable postponed type hints for forward refs
from typing import Any, Callable, Dict, List        # Precise typing for collections and callables
from datetime import datetime, timezone             # Parse ISO times and compare with "now"
import streamlit as st                              # Streamlit UI primitives
from zoneinfo import ZoneInfo

from lib.api import fetch_scores                    # UI-facing wrapper for /scores (normalized shape)
from lib.utils import load_team_logo_from_name      # Helper to load exact-name PNGs or fallback badge


# ============================================================
# Public API — render function for the Live Board tab
# ============================================================

def render_live_board(
    *,
    events: List[Dict[str, Any]],
    agent: Any,
    ev_threshold: float,
    skey: Callable[..., str],
    sport_key: str = "americanfootball_nfl",   # Optional: pass through from app.py for clarity
    days_from: int | None = 2,                 # Short lookback to cover today's + recent games
) -> None:
    """
    @brief Render the Live Board tab: logos, scores, and bookmaker offers.
    @param events       Normalized event list from fetch_and_normalize_events().
    @param agent        The BettingAgent instance (for Evaluate/Place actions).
    @param ev_threshold Threshold used by the agent to recommend edges.
    @param skey         Helper to build unique Streamlit widget keys.
    @param sport_key    The Odds API sport key (default: NFL).
    @param days_from    Optional scores lookback window in days.
    """

    # ------------------------------------------------------------
    # Show a small count of loaded events for debug/clarity
    # ------------------------------------------------------------
    st.caption(f"Events loaded: {len(events) if events else 0}")

    # ------------------------------------------------------------
    # If there are no events yet, guide the user to fetch and exit early
    # ------------------------------------------------------------
    if not events:
        st.info("Click 'Fetch odds now' in the header to load events.")
        return

    # ------------------------------------------------------------
    # Attempt to fetch normalized scores for quick status display
    # (Provider has an in-memory cache, so this is lightweight.)
    # ------------------------------------------------------------
    try:
        # Fetch scores for the configured sport (normalized to internal schema)
        score_rows = fetch_scores(sport_key=sport_key, days_from=days_from) or []
    except Exception as exc:
        # If the scores endpoint fails, log a warning and continue without scores
        st.warning(f"Scores unavailable right now ({exc}). Showing odds only.")
        score_rows = []

    # ------------------------------------------------------------
    # Index the scores by game_id for O(1) lookup during event rendering
    # ------------------------------------------------------------
    scores_by_id: Dict[str, Dict[str, Any]] = {row["game_id"]: row for row in score_rows if row.get("game_id")}

    # ------------------------------------------------------------
    # Iterate every event (matchup) and render a compact card with logos + offers
    # ------------------------------------------------------------
    for ev in events:
        # Read names + id
        away_name = ev.get("away", "Away")
        home_name = ev.get("home", "Home")
        game_id   = ev.get("game_id", "—")

        # Scores + status
        srow = scores_by_id.get(game_id, {})
        commence_iso = ev.get("commence_time")
        commence_dt  = _safe_parse_iso(commence_iso)
        status       = _compute_status_label(completed=bool(srow.get("completed", False)), commence_dt=commence_dt)
        away_score   = srow.get("away_score")
        home_score   = srow.get("home_score")

        # Kickoff (local)
        kickoff_str = _format_kickoff_local(commence_iso)

        # Logos row (same as before, now with a visible "vs")
        lc1, lc2, lc3 = st.columns([1, 7, 2])
        with lc1:
            st.write(" ")
        with lc2:
            t1, mid, t2 = st.columns([2, 1, 2])
            with t1:
                img = load_team_logo_from_name(away_name, size=40)
                if img is not None: st.image(img, width=32)
                st.markdown(f"**{away_name}**")
            with mid:
                st.markdown("<div style='text-align:center; font-size: 18px;'>vs</div>", unsafe_allow_html=True)
            with t2:
                img = load_team_logo_from_name(home_name, size=40)
                if img is not None: st.image(img, width=32)
                st.markdown(f"**{home_name}**")
        with lc3:
            # score + status + kickoff time
            if (away_score is not None) or (home_score is not None):
                st.markdown(
                    f"<div style='text-align:right'><b>{away_score if away_score is not None else '—'}</b>"
                    f"  :  <b>{home_score if home_score is not None else '—'}</b></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown("<div style='text-align:right'>— : —</div>", unsafe_allow_html=True)
            st.caption(f"{status} • {kickoff_str}")

        # One-line header WITHOUT the GUID
        st.markdown(f"### {away_name} vs {home_name}")

        # ---- Offers in a single dropdown (organized by market) ----
        with st.expander("Show offers", expanded=False):
            # Small caption with the game id (if you want to keep it around)
            st.caption(f"Game ID: {game_id}")

            grouped = _group_offers_by_market(ev.get("offers", []))

            def _render_bucket(title: str, items: list[dict]):
                if not items:
                    return
                st.markdown(f"**{title}**")
                for idx, offer in enumerate(items):
                    c0, c1, c2, c3 = st.columns([3, 1, 1, 2])

                    # Offer summary
                    c0.markdown(
                        f"**{offer.get('bookmaker', '—')}** — {offer.get('market', '—')} — "
                        f"**{offer.get('side', '—')}** @ {offer.get('decimal_odds', '—')}"
                    )

                    # Details expander
                    with c3.expander("Context", expanded=False):
                        st.json(offer.get("context", {}))

                    # Keys
                    eval_key  = skey("eval",  game_id, offer.get("market"), offer.get("bookmaker"), idx)
                    place_key = skey("place", game_id, offer.get("market"), offer.get("bookmaker"), idx)

                    # Actions
                    if c1.button("Evaluate", key=eval_key):
                        rec = agent.make_recommendation(
                            market=offer["market"],
                            side=offer["side"],
                            context=offer.get("context", {}),
                            odds_value=offer["decimal_odds"],
                            odds_type="decimal",
                            ev_threshold=ev_threshold,
                        )
                        st.session_state.last_recs.append(rec)
                        st.toast(f"{rec['decision']} — EV {rec['ev']:.3f} — stake ${rec['stake']:.2f}")

                    if c2.button("Place (paper)", key=place_key):
                        rec = agent.make_recommendation(
                            market=offer["market"],
                            side=offer["side"],
                            context=offer.get("context", {}),
                            odds_value=offer["decimal_odds"],
                            odds_type="decimal",
                            ev_threshold=ev_threshold,
                        )
                        st.session_state.open_bets[rec["id"]] = rec
                        st.session_state.last_recs.append(rec)
                        st.success("Placed (paper). See 'Open Bets' tab.")

            # Render buckets in a consistent order
            _render_bucket("Moneyline", grouped.get("moneyline", []))
            _render_bucket("Spread",    grouped.get("spread", []))
            _render_bucket("Total",     grouped.get("total", []))
            _render_bucket("Other",     grouped.get("other", []))

        # Horizontal divider between games
        st.divider()


# ============================================================
# Small internal helpers (pure functions, easy to test)
# ============================================================

def _safe_parse_iso(value: str | None) -> datetime | None:
    """
    @brief Safely parse an ISO 8601 timestamp string to a timezone-aware datetime.
    @param value The ISO string to parse (or None).
    @return A timezone-aware datetime in UTC, or None if parsing fails.
    """
    # Return None if value missing
    if not value:
        return None

    try:
        # Parse using fromisoformat if it carries offset; else assume UTC 'Z'
        if value.endswith("Z"):
            # Strip the 'Z' and set tzinfo=UTC
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        # Let Python parse timestamps with explicit offsets
        dt = datetime.fromisoformat(value)
        # Ensure timezone-aware (assume UTC if naive)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        # If parsing fails, return None gracefully
        return None


def _compute_status_label(*, completed: bool, commence_dt: datetime | None) -> str:
    """
    @brief Compute a simple status label given completion flag and start time.
    @param completed  Whether the provider marks the game as completed/final.
    @param commence_dt Parsed commence datetime (UTC) or None.
    @return One of: 'FINAL', 'LIVE', 'SCHEDULED'.
    """
    # If provider explicitly marks the game as completed, call it FINAL
    if completed:
        return "FINAL"

    # If we have a commence time, determine if the game should be considered LIVE or SCHEDULED
    if commence_dt is not None:
        # Compare to current UTC time to decide the label
        now_utc = datetime.now(timezone.utc)
        return "LIVE" if now_utc >= commence_dt else "SCHEDULED"

    # If we lack both completion info and commence time, default to SCHEDULED
    return "SCHEDULED"

def _format_kickoff_local(iso_str: str | None) -> str:
    """
    Convert commence_time ISO string to a local, human-friendly time.
    Example: 'Sun 5:20 PM'. Returns 'TBD' if missing or unparsable.
    """
    dt = _safe_parse_iso(iso_str)
    if not dt:
        return "TBD"
    # convert to local timezone of the machine running Streamlit
    local = dt.astimezone()  # default local tz
    return local.strftime("%a %-I:%M %p")  # e.g., "Sun 5:20 PM" (use %#I on Windows)
    

def _group_offers_by_market(offers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """
    Group offers by market type: moneyline, spread, total.
    Unknown / missing markets are grouped under 'other'.
    """
    buckets: dict[str, list[dict[str, Any]]] = {
        "moneyline": [],
        "spread": [],
        "total": [],
        "other": [],
    }

    for off in offers or []:
        # Ensure we pass a str, never Optional[str], to satisfy the type checker
        market = (off.get("market") or "other")
        if market not in buckets:        # anything unexpected => 'other'
            market = "other"
        buckets[market].append(off)

    return buckets