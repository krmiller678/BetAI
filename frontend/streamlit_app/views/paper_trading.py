"""
@file        paper_trading.py
@brief       Paper Trading view — legacy-style controls + offers + Open Bets + Performance.
@details
  - Renders filter controls (team, market, bookmaker) to quickly find offers.
  - Displays a filterable list of priced sides with Evaluate / Place (paper) actions.
  - Shows Open Bets (with manual settle) and Performance KPIs on the same page.
  - Uses data already normalized by lib/api.fetch_and_normalize_events().
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations                  # Enable postponed type hints for forward refs
from typing import Any, Callable, Dict, List        # Precise typing for collections and callables
import streamlit as st                              # Streamlit UI primitives
import pandas as pd                                 # Tabular transforms and quick summaries


# ============================================================
# Public API — render function for the Paper Trading page
# ============================================================

def render_paper_trading(
    *,
    agent: Any,                                     # BettingAgent instance (bankroll, staking, settle)
    events: List[Dict[str, Any]],                   # Normalized events with offers (from odds API)
    open_bets: Dict[str, Dict[str, Any]],           # Mutable mapping of open paper trades
    history: List[Dict[str, Any]],                  # Settled bet records (for performance KPIs)
    ev_threshold: float,                            # EV floor for agent recommendations
    skey: Callable[..., str],                       # Safe widget key builder
) -> None:
    """
    @brief Render Paper Trading controls + offers + open bets + performance.
    """

    # ------------------------------------------------------------
    # Write a page title/subheader to match legacy "single-page" feel
    # ------------------------------------------------------------
    st.subheader("Paper Trading")

    # ------------------------------------------------------------
    # Quick guard: if no events loaded yet, guide the user and exit
    # ------------------------------------------------------------
    if not events:
        st.info("No markets loaded. Use the 'Fetch odds now' button first.")
        return

    # ------------------------------------------------------------
    # Flatten normalized events → rows (one row per priced side/offer)
    # ------------------------------------------------------------
    offers_rows = _flatten_offers(events)

    # ------------------------------------------------------------
    # Build a DataFrame for filtering and display convenience
    # ------------------------------------------------------------
    df = pd.DataFrame(offers_rows)

    # ------------------------------------------------------------
    # Create filter choices from available data (unique values)
    # ------------------------------------------------------------
    teams = sorted(set(list(df["home"]) + list(df["away"])))
    markets = sorted(df["market"].dropna().unique().tolist())
    books = sorted(df["bookmaker"].dropna().unique().tolist())

    # ------------------------------------------------------------
    # Layout: left = controls + offers table; right = Open Bets + Performance
    # ------------------------------------------------------------
    left, right = st.columns([3, 2])

    # ========================= LEFT PANE =========================
    with left:
        # --------------------------------------------------------
        # Filters (dropdowns / multiselects) similar to legacy layout
        # --------------------------------------------------------
        sel_team = st.selectbox(
            "Team",
            options=["(All teams)"] + teams,
            index=0,
            help="Filter offers by team (home or away).",
        )

        sel_market = st.selectbox(
            "Market",
            options=["(All markets)"] + markets,
            index=0,
            help="Select a market type to filter (moneyline, spread, total).",
        )

        sel_books = st.multiselect(
            "Bookmakers",
            options=books,
            default=books[:3] if len(books) > 3 else books,
            help="Choose one or more books to include.",
        )

        # --------------------------------------------------------
        # Apply filters to the offers DataFrame (defensive on empty)
        # --------------------------------------------------------
        view = df.copy()

        # If a specific team is selected (not "(All teams)"), match against home or away
        if sel_team != "(All teams)":
            view = view[(view["home"] == sel_team) | (view["away"] == sel_team)]

        # If a specific market selected, filter by it
        if sel_market != "(All markets)":
            view = view[view["market"] == sel_market]

        # If specific books selected, filter to those
        if sel_books:
            view = view[view["bookmaker"].isin(sel_books)]

        # --------------------------------------------------------
        # Show a compact count of remaining offers
        # --------------------------------------------------------
        st.caption(f"Offers found: {len(view)}")

        # --------------------------------------------------------
        # Render each filtered offer line with Evaluate / Place actions
        # --------------------------------------------------------
        for idx, row in view.reset_index(drop=True).iterrows():
            # Build a row of columns to show offer details and actions
            c0, c1, c2, c3 = st.columns([3, 1, 1, 2])

            # Column 0: readable summary (book, market, side, odds)
            c0.markdown(
                f"**{row['bookmaker']}** — {row['market']} — "
                f"**{row['side']}** @ {row['decimal_odds']}"
            )

            # Column 3: collapsible context payload for transparency
            with c3.expander("Context", expanded=False):
                st.json(row.get("context", {}))

            # Unique keys for buttons using game/market/book/row index
            eval_key  = skey("pt_eval",  row["game_id"], row["market"], row["bookmaker"], idx)
            place_key = skey("pt_place", row["game_id"], row["market"], row["bookmaker"], idx)

            # Column 1: Evaluate — ask agent for decision with current EV threshold
            if c1.button("Evaluate", key=eval_key):
                # Call the agent with the minimal context required
                rec = agent.make_recommendation(
                    market=row["market"],
                    side=row["side"],
                    context=row.get("context", {}),
                    odds_value=float(row["decimal_odds"]),
                    odds_type="decimal",
                    ev_threshold=ev_threshold,
                )
                # Append to the recent recommendations cache
                st.session_state.last_recs.append(rec)
                # Toast the outcome (decision, EV, stake)
                st.toast(f"{rec['decision']} — EV {rec['ev']:.3f} — stake ${rec['stake']:.2f}")

            # Column 2: Place (paper) — evaluate (if needed) then store in open_bets
            if c2.button("Place (paper)", key=place_key):
                # Evaluate with the agent
                rec = agent.make_recommendation(
                    market=row["market"],
                    side=row["side"],
                    context=row.get("context", {}),
                    odds_value=float(row["decimal_odds"]),
                    odds_type="decimal",
                    ev_threshold=ev_threshold,
                )
                # Store by recommendation id for easy lookup/settle
                st.session_state.open_bets[rec["id"]] = rec
                # Keep a copy in recent recs
                st.session_state.last_recs.append(rec)
                # Success message with pointer to Open Bets panel on the right
                st.success("Placed (paper). See Open Bets panel →")

    # ========================= RIGHT PANE ========================
    with right:
        # --------------------------------------------------------
        # Open Bets panel (with manual settle buttons)
        # --------------------------------------------------------
        st.markdown("### Open Bets")

        # If no open positions, show an info message
        if not open_bets:
            st.info("No open bets yet.")
        else:
            # Iterate a copy since we mutate on settle
            for bid, b in list(open_bets.items()):
                # Build columns for summary and actions
                o0, o1, o2, o3, o4 = st.columns([3, 1, 1, 1, 1])

                # Summary: side, odds, market, model
                o0.markdown(
                    f"**{b.get('side', '—')}** @ {b.get('decimal_odds', '—')} — "
                    f"{b.get('market', '—')} — {b.get('model_used', 'model')}"
                )

                # Stake amount
                o1.write(f"Stake: ${float(b.get('stake', 0.0)):.2f}")

                # EV at entry
                o2.write(f"EV@entry: {float(b.get('ev', 0.0)):.3f}")

                # Build unique keys for settle actions using bet id
                win_key  = f"pt_win_{bid}"
                lose_key = f"pt_lose_{bid}"

                # Settle as WIN: record via agent, append to history, remove from open_bets
                if o3.button("✓", key=win_key, help="Settle as WIN"):
                    settled = agent.record_result(bid, "win")
                    st.session_state.history.append(settled)
                    open_bets.pop(bid, None)
                    st.success(f"WIN: +${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")

                # Settle as LOSS: record via agent, append to history, remove from open_bets
                if o4.button("✗", key=lose_key, help="Settle as LOSS"):
                    settled = agent.record_result(bid, "loss")
                    st.session_state.history.append(settled)
                    open_bets.pop(bid, None)
                    st.error(f"LOSS: ${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")

        # --------------------------------------------------------
        # Performance panel (KPIs + quick table)
        # --------------------------------------------------------
        st.markdown("### Performance")

        # If no history yet, show placeholder KPIs and exit panel
        if not history:
            c1, c2, c3 = st.columns(3)
            c1.metric("Bankroll", f"${getattr(agent, 'bankroll', 0.0):,.2f}")
            c2.metric("Hit Rate", "—")
            c3.metric("ROI", "—")
        else:
            # Build a DataFrame for simple metrics
            hdf = pd.DataFrame(history)

            # Parse timestamp to date if present
            if "ts" in hdf.columns:
                hdf["date"] = pd.to_datetime(hdf["ts"], unit="s", errors="coerce")

            # Compute KPIs (defensive on missing data)
            total_stake = float(hdf["stake"].sum()) if "stake" in hdf else 0.0
            total_pnl   = float(hdf["pnl"].sum())   if "pnl"   in hdf else 0.0
            roi         = (total_pnl / total_stake) if total_stake > 0 else 0.0
            hit_rate    = float((hdf["result"] == "win").mean()) if "result" in hdf else 0.0

            # Show KPIs
            c1, c2, c3 = st.columns(3)
            c1.metric("Bankroll", f"${getattr(agent, 'bankroll', 0.0):,.2f}")
            c2.metric("Hit Rate", f"{hit_rate:.1%}")
            c3.metric("ROI", f"{roi:.1%}")

            # Optional: mini recent-settles table (last 5)
            cols = [c for c in ["date", "side", "market", "decimal_odds", "stake", "result", "pnl"] if c in hdf.columns]
            if cols:
                st.caption("Recent settles")
                st.dataframe(hdf[cols].sort_values(cols[0], ascending=False).head(5), use_container_width=True)


# ============================================================
# Small helper: flatten normalized events into offer rows
# ============================================================

def _flatten_offers(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    @brief Expand each event into a list of offers with convenient columns.
    @return List of rows containing bookmaker, market, side, odds, game metadata, and context.
    """
    # Prepare an output list to collect rows
    rows: List[Dict[str, Any]] = []

    # Walk each normalized event from the odds API
    for ev in events or []:
        # Extract basic matchup info
        game_id = ev.get("game_id")
        home = ev.get("home")
        away = ev.get("away")
        commence_time = ev.get("commence_time")

        # Each offer represents a priced side at a bookmaker/market
        for off in ev.get("offers", []):
            # Create a merged row with both offer and event context
            rows.append({
                "game_id": game_id,
                "home": home,
                "away": away,
                "commence_time": commence_time,
                "bookmaker": off.get("bookmaker"),
                "market": off.get("market"),
                "side": off.get("side"),
                "decimal_odds": float(off.get("decimal_odds", 0.0)),
                "context": off.get("context", {}),
            })

    # Return the full flattened list
    return rows