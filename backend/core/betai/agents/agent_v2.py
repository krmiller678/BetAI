# backend/core/betai/agents/agent_v2.py
# ------------------------------------------------------------
# Agent v2 (simple + readable):
# - Keeps the agent "thin": do odds math, call coordinators, size bet, log history.
# - Coordinators own the model choice and feature row (agent doesn't pick features).
# - Works with Streamlit or an API because it returns plain dicts.
# ------------------------------------------------------------

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Literal

# Import the coordinator(s) we currently support.
# You can add SpreadCoordinator / TotalCoordinator later the same way.
from ..coordinators.moneyline import MoneylineCoordinator


# ------------------------------------------------------------
# Bet record = a single "play" we considered/placed.
# We keep it simple and explicit so it's easy to show in Streamlit.
# ------------------------------------------------------------
@dataclass
class BetRecord:
    id: str                         # unique bet id
    ts: float                       # timestamp
    market: Literal["moneyline", "spread", "total"]
    side: str                       # e.g., "DET ML", "DET -3.5", "Over 45.5"
    model_used: str                 # which model playbook was used
    decimal_odds: float             # price we used for the EV math
    p_model: float                  # model probability (0..1)
    p_implied: float                # implied probability from the odds (naive)
    ev: float                       # expected value of the bet (unit stake)
    stake: float                    # dollars to stake (paper trade)
    context: Dict[str, Any]         # raw inputs we used (for debugging/trace)
    result: Literal["open", "win", "loss"] = "open"
    pnl: float = 0.0                # profit/loss when settled
    bankroll_after: float | None = None  # bankroll after settlement


class BettingAgent:
    """
    The "Head Coach". Keeps things simple:
      1) Convert odds to decimal, compute implied prob.
      2) Ask the market coordinator for a model probability (p_model).
      3) Compute EV, run Kelly, decide BET/NO BET.
      4) Record the bet in history; allow settlement later.
    """

    def __init__(self, starting_bankroll: float = 1000.0):
        # Bankroll and policy can come from env (easy to tune later without code changes)
        self.bankroll = float(starting_bankroll)
        self.kelly_fraction = float(os.getenv("KELLY_FRACTION", 0.25))  # 25% Kelly by default
        self.max_stake_pct = float(os.getenv("MAX_STAKE_PCT", 0.10))    # hard cap per bet (10%)
        self.default_ev_threshold = float(os.getenv("EV_THRESHOLD", 0.02))  # need +2% EV to fire by default

        # Coordinators = "Offense/Defense/Special Teams".
        # Start with Moneyline only; add others as you build them.
        self.coordinators = {
            "moneyline": MoneylineCoordinator(),
            # "spread": SpreadCoordinator(),
            # "total": TotalCoordinator(),
        }

        # In-memory paper-trade ledger
        self.history: list[BetRecord] = []

    # ---------------------------
    # Basic pricing helpers
    # ---------------------------

    @staticmethod
    def odds_to_decimal(odds_value: float, odds_type: str) -> float:
        """
        Convert different odds formats to decimal odds.
        Supported: 'decimal', 'american' (you can add more later).
        """
        t = odds_type.lower()
        if t == "decimal":
            return float(odds_value)
        if t == "american":
            o = float(odds_value)
            # +150 -> 2.50 ; -120 -> 1.8333...
            return (1.0 + o / 100.0) if o > 0 else (1.0 + 100.0 / abs(o))
        raise ValueError(f"Unsupported odds_type: {odds_type}")

    @staticmethod
    def implied_prob(decimal_odds: float) -> float:
        """
        Naive implied probability from decimal odds.
        (Later you can add "vig removal" to be book-fair rather than naive.)
        """
        return 1.0 / float(decimal_odds)

    @staticmethod
    def expected_value(p: float, dec: float) -> float:
        """
        EV for unit stake:
          EV = p * (dec - 1) - (1 - p)
        """
        b = dec - 1.0
        return p * b - (1.0 - p)

    def kelly_stake(self, p: float, dec: float) -> float:
        """
        Fractional Kelly sizing with a hard per-bet cap.
        Kelly fraction (0..1) is read from env or defaults to 0.25.
        """
        b = dec - 1.0
        # Kelly fraction f* = (bp - q) / b where q = 1 - p
        raw_k = ((b * p) - (1.0 - p)) / b if b > 0 else 0.0
        raw_k = max(0.0, raw_k)                # never negative stake
        f = raw_k * self.kelly_fraction        # use a fraction of full Kelly
        # dollar stake capped by bankroll and a hard percentage limit
        stake = self.bankroll * f
        cap = self.bankroll * self.max_stake_pct
        return max(0.0, min(stake, cap))

    # ---------------------------
    # Main public API
    # ---------------------------

    def make_recommendation(
        self,
        market: Literal["moneyline", "spread", "total"],
        side: str,
        context: Dict[str, Any],
        odds_value: float,
        odds_type: str = "decimal",
        ev_threshold: float | None = None,
    ) -> Dict[str, Any]:
        """
        Build a recommendation for a single bet opportunity.
        - market: which lane we're evaluating ("moneyline" for v1).
        - side: a human-friendly label for the bet (e.g., "DET ML").
        - context: raw inputs (the "roster" of signals).
        - odds_value/odds_type: price information (american or decimal).
        - ev_threshold: overrides default threshold if provided.

        Returns a dict ready for the UI with decision + stake and full details.
        """

        # 1) Price math
        dec = self.odds_to_decimal(odds_value, odds_type)
        p_imp = self.implied_prob(dec)

        # 2) Ask the coordinator to run the right playbook (model)
        if market not in self.coordinators:
            raise ValueError(f"No coordinator registered for market '{market}'")

        coord = self.coordinators[market]
        coord_out = coord.recommend(context)  # must return {"p_model": float, "model_name": str}
        p_model = float(coord_out["p_model"])
        model_name = str(coord_out["model_name"])

        # 3) EV and decision
        ev = self.expected_value(p_model, dec)
        threshold = self.default_ev_threshold if ev_threshold is None else float(ev_threshold)
        decision = "BET" if ev >= threshold else "NO BET"

        # 4) Sizing (Kelly with caps)
        stake = self.kelly_stake(p_model, dec) if decision == "BET" else 0.0

        # 5) Record the outcome in our ledger (still "open")
        record = BetRecord(
            id=str(uuid.uuid4()),
            ts=time.time(),
            market=market,
            side=side,
            model_used=model_name,
            decimal_odds=dec,
            p_model=p_model,
            p_implied=p_imp,
            ev=ev,
            stake=stake,
            context=context,
        )
        self.history.append(record)

        # 6) Return a UI-friendly dict (Streamlit can show this as a card/table)
        out = asdict(record)
        out["decision"] = decision
        out["bankroll_now"] = self.bankroll  # current bankroll before placing
        return out

    def record_result(self, bet_id: str, outcome: Literal["win", "loss"]) -> Dict[str, Any]:
        """
        Settle an existing bet:
          - Win: PnL = stake * (decimal_odds - 1)
          - Loss: PnL = -stake
        Updates bankroll and returns the settled record as a dict.
        """
        for rec in self.history:
            if rec.id == bet_id and rec.result == "open":
                rec.result = outcome
                if outcome == "win":
                    rec.pnl = rec.stake * (rec.decimal_odds - 1.0)
                else:
                    rec.pnl = -rec.stake
                self.bankroll += rec.pnl
                rec.bankroll_after = self.bankroll
                return asdict(rec)

        raise ValueError(f"Bet id {bet_id} not found or already settled.")