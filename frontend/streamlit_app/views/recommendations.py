"""
@file        recommendations.py
@brief       Recommendations view — high-EV signals with quick place actions.
@details
  - Reads the recent recommendations buffer (from session_state.last_recs).
  - Filters rows by the current EV threshold (sidebar-controlled).
  - Sorts by EV (descending) to surface the best opportunities first.
  - Allows placing a paper trade directly from this tab.
  - Defensive against missing fields; renders cleanly even with partial data.
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations                  # Enable postponed type hints for forward references
from typing import Any, Callable, Dict, List        # Precise typing for collections and callables
import streamlit as st                              # Streamlit UI primitives


# ============================================================
# Public API — render function for the Recommendations tab
# ============================================================

def render_recommendations(
    *,
    last_recs: List[Dict[str, Any]],               # Recent recommendations (append-only buffer)
    open_bets: Dict[str, Dict[str, Any]],          # Mutable mapping of open paper trades
    ev_threshold: float,                           # Minimum EV to display/place
    skey: Callable[..., str],                      # Safe widget key builder
) -> None:
    """
    @brief Render the Recommendations tab (filtered by EV threshold).
    """

    # ------------------------------------------------------------
    # Write a clear subheader for the section
    # ------------------------------------------------------------
    st.subheader("Recommended edges (EV ≥ threshold)")

    # ------------------------------------------------------------
    # Defensive copy of incoming list (avoid accidental mutation)
    # ------------------------------------------------------------
    recs = list(last_recs or [])

    # ------------------------------------------------------------
    # Filter by EV threshold (fallback to 0.0 if missing)
    # ------------------------------------------------------------
    good = [r for r in recs if float(r.get("ev", 0.0)) >= float(ev_threshold)]

    # ------------------------------------------------------------
    # If none pass the filter, show a helpful message and exit
    # ------------------------------------------------------------
    if not good:
        st.info("No qualifying recommendations yet. Evaluate markets on the Live Board or Paper Trading.")
        return

    # ------------------------------------------------------------
    # Sort by EV descending to surface best opportunities first
    # ------------------------------------------------------------
    good.sort(key=lambda r: float(r.get("ev", 0.0)), reverse=True)

    # ------------------------------------------------------------
    # Optional: quick summary line
    # ------------------------------------------------------------
    st.caption(f"Found {len(good)} ideas at EV ≥ {ev_threshold:.3f}")

    # ------------------------------------------------------------
    # Render each recommendation row with details and a Place action
    # ------------------------------------------------------------
    for rec in good:
        # Create a compact row with columns for summary, stats, stake, action
        c0, c1, c2, c3, c4 = st.columns([3, 1, 1, 1, 1])

        # Column 0: readable summary (side — market — model)
        c0.markdown(f"**{rec.get('side', '—')}** — {rec.get('market', '—')} — {rec.get('model_used', 'model')}")

        # Column 1: modeled probability (if available)
        if "p_model" in rec:
            c1.write(f"p_model: {float(rec['p_model']):.3f}")
        else:
            c1.write("p_model: —")

        # Column 2: EV (always formatted with 3 decimals)
        c2.write(f"EV: {float(rec.get('ev', 0.0)):.3f}")

        # Column 3: stake suggestion (from agent)
        c3.write(f"Stake: ${float(rec.get('stake', 0.0)):.2f}")

        # Build a unique Streamlit key for the Place button using the rec id
        place_key = skey("place_rec", rec.get("id", "unknown"))

        # Column 4: place the paper bet (copy rec into open_bets)
        if c4.button("Place (paper)", key=place_key):
            # Store under its id so Open Bets can address it easily
            open_bets[rec["id"]] = rec

            # Show success notification and guide user to Open Bets
            st.success("Placed (paper). See 'Open Bets' tab.")

        # --------------------------------------------------------
        # Optional: show a little more detail under a collapsible pane
        # --------------------------------------------------------
        with st.expander("Details", expanded=False):
            # Include the odds, any context, and the agent fields for transparency
            st.write(f"Odds (decimal): {rec.get('decimal_odds', '—')}")
            if "context" in rec:
                st.json(rec["context"])