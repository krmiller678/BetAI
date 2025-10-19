"""
@file        history.py
@brief       History view — settled bets, bankroll curve, and KPIs.
@details
  - Renders high-level KPIs (bankroll, hit rate, ROI) derived from settled bets.
  - Plots bankroll-over-time (using 'bankroll_after' snapshots).
  - Displays a sortable table of settled bets (most recent first).
  - Defensive against missing or partial fields in historical records.
"""

# ============================================================
# Imports (inline comments for clarity)
# ============================================================

from __future__ import annotations              # Enable postponed type hints for cleaner forward refs
from typing import Any, Dict, List             # Precise typing for collections and records
import streamlit as st                         # Streamlit UI primitives
import pandas as pd                            # Tabular ops, datetime parsing, simple plotting


# ============================================================
# Public API — render function for the History tab
# ============================================================

def render_history(*, agent: Any, history: List[Dict[str, Any]]) -> None:
    """
    @brief Render the History tab (KPIs, bankroll chart, and settled bets table).
    @param agent   The BettingAgent instance (for current bankroll).
    @param history The list of settled bet records (dicts) stored in session_state.
    """

    # ------------------------------------------------------------
    # Write section header to identify the view
    # ------------------------------------------------------------
    st.subheader("Performance")

    # ------------------------------------------------------------
    # If there are no settled records yet, show a helpful message and exit
    # ------------------------------------------------------------
    if not history:
        st.info("No settled bets yet. Place paper bets and settle them to build history.")
        return

    # ------------------------------------------------------------
    # Convert raw list of dicts into a DataFrame for easier analysis
    # ------------------------------------------------------------
    df = pd.DataFrame(history)

    # ------------------------------------------------------------
    # Ensure a datetime column exists from Unix seconds (defensive: missing/invalid -> NaT)
    # ------------------------------------------------------------
    if "ts" in df.columns:
        df["date"] = pd.to_datetime(df["ts"], unit="s", errors="coerce")
    else:
        df["date"] = pd.NaT

    # ------------------------------------------------------------
    # Compute KPIs with defensive defaults for missing columns
    # ------------------------------------------------------------
    total_stake = float(df["stake"].sum()) if "stake" in df else 0.0
    total_pnl   = float(df["pnl"].sum())   if "pnl"   in df else 0.0
    roi         = (total_pnl / total_stake) if total_stake > 0 else 0.0

    # ------------------------------------------------------------
    # Compute hit rate (fraction of wins among settled results)
    # ------------------------------------------------------------
    if "result" in df:
        hit_rate = float((df["result"] == "win").mean())
    else:
        hit_rate = 0.0

    # ------------------------------------------------------------
    # Show KPI metrics in a three-column layout
    # ------------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Bankroll", f"${getattr(agent, 'bankroll', 0.0):,.2f}")
    c2.metric("Hit Rate", f"{hit_rate:.1%}")
    c3.metric("ROI", f"{roi:.1%}")

    # ------------------------------------------------------------
    # Prepare bankroll-over-time series if we have snapshots
    # ------------------------------------------------------------
    if "bankroll_after" in df.columns and "date" in df.columns:
        # Drop rows with missing values and set index to date for plotting
        curve = df.dropna(subset=["bankroll_after", "date"]).set_index("date")["bankroll_after"]

        # If there is at least one data point, render the line chart
        if not curve.empty:
            st.caption("Bankroll over time")
            st.line_chart(curve)

    # ------------------------------------------------------------
    # Choose and order columns for the history table (show recent first)
    # ------------------------------------------------------------
    preferred_cols = [
        "date", "side", "market", "decimal_odds",
        "stake", "result", "pnl", "bankroll_after", "model_used",
    ]

    # ------------------------------------------------------------
    # Build a safe view using whichever of the preferred columns are present
    # ------------------------------------------------------------
    display_cols = [c for c in preferred_cols if c in df.columns]

    # ------------------------------------------------------------
    # If we have a date column, sort by date descending for recency
    # ------------------------------------------------------------
    if "date" in display_cols:
        table = df[display_cols].sort_values("date", ascending=False)
    else:
        table = df[display_cols]

    # ------------------------------------------------------------
    # Render the table using Streamlit's dataframe widget
    # ------------------------------------------------------------
    st.caption("Settled bets")
    st.dataframe(table, use_container_width=True)