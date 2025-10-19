"""
@file        open_bets.py
@brief       Open Bets view — list active paper trades and allow manual settle.
@details
  - Displays each open bet with key fields (side, odds, stake, EV at entry).
  - Provides buttons to settle as WIN or LOSS (manual testing flow).
  - On settle, the bet is removed from open_bets and appended to history.
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations              # Enable postponed type hints for forward references
from typing import Any, Dict                   # Precise typing for agent and bet records
import streamlit as st                         # Streamlit UI primitives


# ============================================================
# Public API — render function for the Open Bets tab
# ============================================================

def render_open_bets(*, agent: Any, open_bets: Dict[str, Dict[str, Any]]) -> None:
    """
    @brief Render the Open Bets tab (active paper positions with settle actions).
    @param agent     The BettingAgent instance (handles result recording / bankroll updates).
    @param open_bets Dict of open bet records keyed by bet_id (mutable mapping).
    """

    # ------------------------------------------------------------
    # Write a clear subheader for the section
    # ------------------------------------------------------------
    st.subheader("Open Bets")

    # ------------------------------------------------------------
    # If there are no open positions, show an informative message and exit
    # ------------------------------------------------------------
    if not open_bets:
        st.info("No open bets. Evaluate and place paper bets from the Live Board or Recommendations.")
        return

    # ------------------------------------------------------------
    # Iterate a *copy* of the mapping since we will mutate it on settle
    # ------------------------------------------------------------
    for bet_id, bet in list(open_bets.items()):
        # Create a responsive row of columns for the bet summary and actions
        c0, c1, c2, c3, c4 = st.columns([3, 1, 1, 1, 1])

        # Column 0: summarize the key bet info (market/side/model/price)
        c0.markdown(
            f"**{bet.get('side', '—')}** @ {bet.get('decimal_odds', '—')} — "
            f"{bet.get('market', '—')} — {bet.get('model_used', 'model')}"
        )

        # Column 1: stake amount (formatted with 2 decimals)
        c1.write(f"Stake: ${float(bet.get('stake', 0.0)):.2f}")

        # Column 2: EV at entry (3 decimals)
        c2.write(f"EV@entry: {float(bet.get('ev', 0.0)):.3f}")

        # Build unique Streamlit keys for the action buttons using the bet_id
        win_key  = f"win_{bet_id}"
        lose_key = f"lose_{bet_id}"

        # Column 3: settle as WIN — records result via agent, updates history, removes from open_bets
        if c3.button("Settle ✓", key=win_key):
            # Ask the agent to record a 'win' (returns a settled record with pnl/bankroll_after/ts)
            settled = agent.record_result(bet_id, "win")

            # Append the settled record to the history list stored in session_state
            st.session_state.history.append(settled)

            # Remove this bet from the open positions map
            open_bets.pop(bet_id, None)

            # Inform the user of the resulting PnL and bankroll
            st.success(f"WIN: +${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")

        # Column 4: settle as LOSS — records result via agent, updates history, removes from open_bets
        if c4.button("Settle ✗", key=lose_key):
            # Ask the agent to record a 'loss'
            settled = agent.record_result(bet_id, "loss")

            # Append the settled record to history
            st.session_state.history.append(settled)

            # Remove this bet from the open positions map
            open_bets.pop(bet_id, None)

            # Inform the user of the resulting PnL and bankroll
            st.error(f"LOSS: ${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")