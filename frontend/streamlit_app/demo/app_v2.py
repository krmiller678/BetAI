# ------------------------------------------------------------
# @file        app.py
# @brief       Streamlit UI (new entry point)
# @details
# This is the new, clean starting point for the app UI.
# What it does (simple & readable):
#   1) Pulls live odds from our integrations layer (The Odds API).
#   2) Normalizes that data into a stable internal shape.
#   3) Shows a "Live Board" of events and bookmaker offers.
#   4) Lets the Agent v2 evaluate an offer (EV + Kelly) and place paper bets.
#   5) Tracks Open Bets and allows manual settle (win/loss) for now.
#   6) Shows History (PnL, bankroll chart, basic KPIs).
#
# Notes:
#   - Odds/API config comes from .env (ODDS_API_KEY, ODDS_API_URL, etc.)
#   - We keep state in st.session_state so it persists across reruns.
#   - We use unique, sanitized keys for Streamlit widgets to avoid collisions.
#
# Later:
#   - Add results provider to auto-settle.
#   - Add more coordinators (spread/total) and better models.
#   - Optionally move Agent/state to a FastAPI backend.
# ------------------------------------------------------------

from __future__ import annotations

import os
import re
import time
from typing import Dict, Any

import streamlit as st

# Odds provider + normalizer (integrations layer)
from betai.integrations.odds_api import TheOddsAPIProvider, normalize_events

# Agent v2 (head coach)
from betai.agents.agent_v2 import BettingAgent

# auto-refresh helper
from streamlit_autorefresh import st_autorefresh


# -----------------------------
# Streamlit page configuration
# -----------------------------
st.set_page_config(page_title="BetAI — Live Odds", layout="wide")

# -----------------------------
# Small helper: build safe, unique keys for Streamlit widgets
# We combine multiple parts (like game_id, bookmaker, market, index) and
# strip any characters Streamlit might dislike into underscores.
# -----------------------------
def skey(*parts) -> str:
    raw = "_".join(str(p) for p in parts)
    return re.sub(r"[^A-Za-z0-9_.-]", "_", raw)

# -----------------------------
# One-time initialization of state
# -----------------------------
if "agent" not in st.session_state:
    # Starting bankroll can be set here or pulled from .env later
    st.session_state.agent = BettingAgent(starting_bankroll=1000.0)

if "events" not in st.session_state:
    # Latest normalized events from the odds provider
    st.session_state.events = []

if "last_fetch" not in st.session_state:
    # Timestamp of last odds fetch (for display + auto-refresh logic)
    st.session_state.last_fetch = 0

if "last_recs" not in st.session_state:
    # Most recent recommendations (so we can show "Recommendations" tab)
    st.session_state.last_recs = []

if "open_bets" not in st.session_state:
    # Dict of open bets by bet_id (paper trading for now) type: Dict[str, Dict[str, Any]]
    st.session_state.open_bets = {}

if "history" not in st.session_state:
    # List of settled bet records
    st.session_state.history = []

agent = st.session_state.agent  # short alias

# -----------------------------
# Sidebar controls (simple, obvious)
# -----------------------------
st.sidebar.header("Live Odds Settings")

# Sport + fetch options come from .env (with sane defaults)
sport_key = st.sidebar.text_input("Sport key", os.getenv("SPORT_KEY", "americanfootball_nfl"))
regions   = st.sidebar.text_input("Regions",   os.getenv("ODDS_REGIONS", "us"))
markets   = st.sidebar.text_input("Markets",   os.getenv("ODDS_MARKETS", "h2h,spreads,totals"))
refresh_s = st.sidebar.number_input("Auto refresh (sec)", min_value=0, max_value=300, value=0, step=1)

# Agent policy knobs (EV threshold + Kelly/risk caps)
ev_threshold = st.sidebar.number_input("EV threshold", min_value=0.0, max_value=0.20, value=0.02, step=0.005)
agent.kelly_fraction = st.sidebar.slider("Kelly fraction", min_value=0.0, max_value=1.0, value=float(agent.kelly_fraction), step=0.05)
agent.max_stake_pct  = st.sidebar.slider("Max stake %",   min_value=0.0, max_value=1.0, value=float(agent.max_stake_pct),  step=0.01)

# -----------------------------
# Create our odds provider (raises useful error if ODDS_API_KEY missing)
# -----------------------------
try:
    prov = TheOddsAPIProvider()
except Exception as e:
    st.error(f"Odds provider error: {e}")
    st.stop()

# -----------------------------
# Top-of-page controls (fetch + timestamp)
# -----------------------------
colA, colB, colC = st.columns([1, 1, 2])

with colA:
    if st.button("Fetch odds now", use_container_width=True):
        # Pull raw provider data, then normalize it to our internal schema
        raw = prov.fetch_markets(sport_key=sport_key, regions=regions, markets=markets)
        st.session_state.events = normalize_events(raw)
        st.session_state.last_fetch = time.time()

with colB:
    # Human-readable "last fetch" display
    ts = st.session_state.last_fetch
    st.write(f"Last fetch: {time.strftime('%H:%M:%S', time.localtime(ts))}" if ts else "Last fetch: —")

# Optional auto-refresh (uses streamlit-autorefresh if installed)
if refresh_s > 0:
    st_autorefresh(interval=refresh_s * 1000, key="auto_refresh")
    # Only refetch if our last fetch is older than the chosen refresh period
    if time.time() - st.session_state.last_fetch > refresh_s:
        raw = prov.fetch_markets(sport_key=sport_key, regions=regions, markets=markets)
        st.session_state.events = normalize_events(raw)
        st.session_state.last_fetch = time.time()

# -----------------------------
# Tabs for main views
# -----------------------------
tab_live, tab_reco, tab_open, tab_hist = st.tabs(
    ["Live Board", "Recommendations", "Open Bets", "History"]
)

# ============================================================
# TAB: Live Board
# - Shows all current events + bookmaker offers.
# - "Evaluate" asks Agent for a decision (uses EV + Kelly).
# - "Place (paper)" evaluates (if needed) and moves to Open Bets.
# ============================================================
with tab_live:
    events = st.session_state.events or []
    st.caption(f"Events loaded: {len(events)}")

    if not events:
        st.info("Click 'Fetch odds now' to load events.")
    else:
        for ev in events:
            st.markdown(f"### {ev['away']} @ {ev['home']}  •  *{ev['game_id']}*")

            # Iterate offers within the event (bookmaker x market x side)
            for i, offer in enumerate(ev["offers"]):
                cols = st.columns([3, 1, 1, 2])

                # Show the core price line (bookmaker, market, side, odds)
                cols[0].markdown(
                    f"**{offer['bookmaker']}** — {offer['market']} — "
                    f"**{offer['side']}** @ {offer['decimal_odds']}"
                )

                # Show minimal context for transparency (you can add more later)
                with cols[3].expander("Context", expanded=False):
                    st.json(offer["context"])

                # Build globally unique keys for Streamlit buttons (no collisions)
                eval_key  = skey("eval",  ev["game_id"], offer["market"], offer["bookmaker"], i)
                place_key = skey("place", ev["game_id"], offer["market"], offer["bookmaker"], i)

                # Evaluate (Agent v2): produces a dict with decision, EV, stake, etc.
                if cols[1].button("Evaluate", key=eval_key):
                    rec = agent.make_recommendation(
                        market=offer["market"],
                        side=offer["side"],
                        context=offer["context"],       # minimal context for now
                        odds_value=offer["decimal_odds"],
                        odds_type="decimal",
                        ev_threshold=ev_threshold,
                    )
                    st.session_state.last_recs.append(rec)
                    st.toast(f"{rec['decision']} — EV {rec['ev']:.3f} — stake ${rec['stake']:.2f}")

                # Place (paper): evaluates if needed, then adds to Open Bets
                if cols[2].button("Place (paper)", key=place_key):
                    rec = agent.make_recommendation(
                        market=offer["market"],
                        side=offer["side"],
                        context=offer["context"],
                        odds_value=offer["decimal_odds"],
                        odds_type="decimal",
                        ev_threshold=ev_threshold,
                    )
                    st.session_state.open_bets[rec["id"]] = rec
                    st.session_state.last_recs.append(rec)
                    st.success("Placed (paper). See 'Open Bets' tab.")

# ============================================================
# TAB: Recommendations
# - Filters last recommendations where EV >= threshold.
# - Lets you place a paper bet from here too.
# ============================================================
with tab_reco:
    st.subheader("Recommended edges (EV ≥ threshold)")
    recs = st.session_state.get("last_recs", [])
    good = [r for r in recs if r["ev"] >= ev_threshold]

    if not good:
        st.info("No qualifying recommendations yet. Evaluate some markets on the Live Board.")
    else:
        # Sort by EV high → low
        good.sort(key=lambda r: r["ev"], reverse=True)
        for r in good:
            cols = st.columns([3, 1, 1, 1, 1])

            cols[0].markdown(f"**{r['side']}** — {r['market']} — {r['model_used']}")
            cols[1].write(f"p_model: {r['p_model']:.3f}")
            cols[2].write(f"EV: {r['ev']:.3f}")
            cols[3].write(f"Stake: ${r['stake']:.2f}")

            # Ensure a unique key here as well (different namespace from Live tab)
            place_key = skey("place_rec", r["id"])
            if cols[4].button("Place (paper)", key=place_key):
                st.session_state.open_bets[r["id"]] = r
                st.success("Placed (paper). See 'Open Bets' tab.")

# ============================================================
# TAB: Open Bets
# - Shows open positions (paper).
# - For now, we manually settle (win/loss) to test the pipeline.
# - Later, add results provider to auto-settle.
# ============================================================
with tab_open:
    st.subheader("Open Bets")
    opens = st.session_state.open_bets

    if not opens:
        st.info("No open bets.")
    else:
        # Show each open bet with quick settle buttons
        for bid, b in list(opens.items()):
            cols = st.columns([3, 1, 1, 1, 1])

            cols[0].markdown(f"**{b['side']}** @ {b['decimal_odds']} — {b['model_used']}")
            cols[1].write(f"Stake: ${b['stake']:.2f}")
            cols[2].write(f"EV@entry: {b['ev']:.3f}")

            # Unique keys for settle actions
            win_key  = skey("win",  bid)
            lose_key = skey("lose", bid)

            if cols[3].button("Settle ✓", key=win_key):
                settled = agent.record_result(bid, "win")
                st.session_state.history.append(settled)
                opens.pop(bid, None)
                st.success(f"WIN: +${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")

            if cols[4].button("Settle ✗", key=lose_key):
                settled = agent.record_result(bid, "loss")
                st.session_state.history.append(settled)
                opens.pop(bid, None)
                st.error(f"LOSS: ${settled['pnl']:.2f} • Bankroll ${settled['bankroll_after']:.2f}")

# ============================================================
# TAB: History
# - Shows settled bets, bankroll line, and simple KPIs.
# - This is your basic performance dashboard.
# ============================================================
with tab_hist:
    st.subheader("Performance")
    hist = st.session_state.get("history", [])

    if not hist:
        st.info("No settled bets yet.")
    else:
        import pandas as pd

        df = pd.DataFrame(hist)
        df["date"] = pd.to_datetime(df["ts"], unit="s")

        # Simple KPIs
        total_stake = float(df["stake"].sum()) if "stake" in df else 0.0
        total_pnl = float(df["pnl"].sum()) if "pnl" in df else 0.0
        roi = (total_pnl / total_stake) if total_stake > 0 else 0.0
        hit = float((df["result"] == "win").mean()) if "result" in df else 0.0

        k1, k2, k3 = st.columns(3)
        k1.metric("Bankroll", f"${agent.bankroll:,.2f}")
        k2.metric("Hit Rate", f"{hit:.1%}")
        k3.metric("ROI", f"{roi:.1%}")

        # Bankroll curve over time (only rows where bankroll_after exists)
        curve = df.dropna(subset=["bankroll_after"]).set_index("date")["bankroll_after"]
        if not curve.empty:
            st.line_chart(curve)

        # Show recent history table
        st.dataframe(
            df[
                ["date", "side", "market", "decimal_odds", "stake", "result", "pnl", "bankroll_after", "model_used"]
            ].sort_values("date", ascending=False),
            use_container_width=True
        )