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
from ..coordinators.spread import SpreadCoordinator


# ------------------------------------------------------------
# Bet record = a single "play" we considered/placed.
# We keep it simple and explicit so it's easy to show in Streamlit.
# ------------------------------------------------------------
@dataclass
class BetRecord:
    id: str                                             # unique bet id
    ts: float                                           # timestamp
    market: Literal["moneyline", "spread", "total"]     # which market type
    side: str                                           # e.g., "DET ML", "DET -3.5", "Over 45.5"
    model_used: str                                     # which model playbook was used
    decimal_odds: float                                 # price we used for the EV math
    p_model: float                                      # model probability (0..1)
    p_implied: float                                    # implied probability from the odds (naive)
    ev: float                                           # expected value of the bet (unit stake)
    stake: float                                        # dollars to stake (paper trade)
    context: Dict[str, Any]                             # raw inputs we used (for debugging/trace)
    result: Literal["open", "win", "loss"] = "open"     # current status
    pnl: float = 0.0                                    # profit/loss when settled
    bankroll_after: float | None = None                 # bankroll after settlement


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
            "spread": SpreadCoordinator(),
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
        ------------------------------------------------------------
        @staticmethod
        @brief Convert betting odds into decimal format.
        @details
        Supports two input types:
          1. "decimal"  – already in decimal form (e.g., 1.8333)
          2. "american" – U.S. moneyline format (e.g., -120 or +150)
        
        Decimal odds express the total return per $1 bet (including stake).
        Example:
            -120  -> 1.8333  → means "bet $1, get $1.8333 total back if you win"
            +150  -> 2.5000  → means "bet $1, get $2.50 total back if you win"
        American odds describe payout per $100 in two cases:
          - Positive (e.g., +150): profit $150 when you bet $100 (underdog).
          - Negative (e.g., -120): must bet $120 to profit $100 (favorite).
        This function standardizes all odds into that "per $1" decimal system.

        @param odds_value The numeric odds value.
        @param odds_type  The format of the odds_value ("decimal" or "american").
        @return A float representing the decimal odds.
        ------------------------------------------------------------
        """
        # Normalize the odds type to lowercase for consistency.
        odds_type = odds_type.lower()

        # If the odds are already in decimal format, just ensure they're float and return.
        if odds_type == "decimal":
            return float(odds_value)

        # If the odds are given in American format:
        elif odds_type == "american":
            american_odds = float(odds_value)

            # ---------------------------
            # Positive American odds (underdog):
            # e.g., +150 means "profit $150 for every $100 bet"
            # Convert to per-$1: profit_per_dollar = 150 / 100 = 1.5
            # Total return = 1 (stake) + 1.5 = 2.5
            # ---------------------------
            if american_odds > 0:
                decimal_odds = 1.0 + (american_odds / 100.0)
                return decimal_odds

            # ---------------------------
            # Negative American odds (favorite):
            # e.g., -120 means "must risk $120 to profit $100"
            # Convert to per-$1: profit_per_dollar = 100 / 120 = 0.8333
            # Total return = 1 (stake) + 0.8333 = 1.8333
            # ---------------------------
            elif american_odds < 0:
                decimal_odds = 1.0 + (100.0 / abs(american_odds))
                return decimal_odds

            # ---------------------------
            # Edge case: +100 is "even money" → decimal = 2.0
            # ---------------------------
            else:
                return 2.0

        # If we encounter any unsupported odds format, raise an error for clarity.
        else:
            raise ValueError(f"Unsupported odds_type: {odds_type}")
    
    @staticmethod
    def implied_prob(decimal_odds: float) -> float:
        """
        ------------------------------------------------------------
        @staticmethod
        @brief Compute the implied probability from decimal odds.
        @details
        The implied probability is the "break-even" win rate embedded in
        the bookmaker's price. It answers:
        "How often would I need to win at these odds to break even?"
        
        Formula:
          implied_probability = 1 / decimal_odds
        
        Examples:
           (EVEN)     decimal 2.00  -> 1/2.00 = 0.50 → must win 50% to break even
           (FAVORITE) decimal 1.833 -> 1/1.833 = 0.545 → must win 54.5% to break even
           (UNDERDOG) decimal 2.50  -> 1/2.50 = 0.40 → must win 40% to break even
        
        @param decimal_odds The decimal odds value.
        @return A float between 0 and 1 representing the implied probability.
        ------------------------------------------------------------
        """
        # Defensive check to avoid dividing by zero or invalid odds.
        if decimal_odds <= 0:
            raise ValueError("Decimal odds must be greater than 0 to compute implied probability.")

        # Compute the book's break-even win rate.
        implied_probability = 1.0 / float(decimal_odds)

        # Return as a float between 0 and 1.
        return implied_probability

    @staticmethod
    def expected_value(prob_win: float, decimal_odds: float) -> float:
        """ 
        ------------------------------------------------------------
        @staticmethod
        @brief Compute expected value (EV) per $1 stake.
        @details
        EV answers: "If I made this same bet many times, on average, how much would I win or lose per $1 bet?"
        
                        or more simply:
        
                        "How much profit (or loss) can I expect on average for each $1 I wager?"
        
        More formally, EV is the average profit (or loss) you can expect per bet if you placed the same wager 
        repeatedly under identical conditions.
        
        Inputs:
            prob_win     - Our model's probability of winning the bet (0..1).
            decimal_odds - Sportsbook's decimal odds for THIS side
                            (total returned per $1 if you win, includes stake).
        
        Equivalent plain-English formula:
            expected profit per $1 = (chance you win × profit if win) − (chance you lose × loss if lose)
        
        Notes:
            - profit_if_win per $1 is (decimal_odds - 1) because the "1" is your stake being returned.
            - loss_if_lose per $1 is always 1 (you lose your stake).
            - EV > 0 means profitable long-run bet; EV < 0 means losing long-run bet.
            - The book’s break-even win rate is 1 / decimal_odds. If your prob_win exceeds that, EV turns positive.
        
        @param prob_win The model's estimated probability of winning (0..1).
        @param decimal_odds The decimal odds for the bet.
        @return A float representing expected profit per $1 bet (e.g., 0.10 means +10 cents per $1 on average).
        ------------------------------------------------------------
        """
        # Compute how many dollars of profit you make per $1 bet if you win (stake is returned separately).
        profit_if_win = decimal_odds - 1.0

        # Compute your chance of losing the bet.
        prob_lose = 1.0 - prob_win

        # Compute expected profit per $1 using: EV = p * profit_if_win - (1 - p) * 1
        expected_profit_per_dollar = (prob_win * profit_if_win) - (prob_lose * 1.0)

        # Return the expected profit per $1 (e.g., 0.10 means +10 cents per $1 on average).
        return expected_profit_per_dollar

    def kelly_stake(self, prob_win: float, decimal_odds: float) -> float:
        """
        ------------------------------------------------------------
        @function kelly_stake
        @brief Calculate how much of the bankroll to bet using the Kelly Criterion.
        @details
        The Kelly Criterion tells us what fraction of our bankroll to risk on a bet
        in order to maximize long-term growth (compounding returns).
        
        Inputs:
            prob_win       - your model's probability of winning (0..1)
            decimal_odds   - sportsbook's decimal odds for the bet
        Steps:
           1. Convert odds into "profit per $1 bet" → b = decimal_odds - 1
           2. Compute the full Kelly fraction: f* = (b * p - q) / b
               - p = prob_win
               - q = 1 - p (probability of losing)
               - b = net profit per $1 if win
           3. The agent uses a *fractional Kelly* (e.g., 25%) to be less aggressive.
           4. Apply bankroll limits: never bet more than a fixed % of bankroll.
        
        Returns:
            stake_dollars - how many dollars to bet given your bankroll and edge.

        Example:
           prob_win = 0.60
           decimal_odds = 1.8333 (favorite at -120)
           bankroll = $1000
           Kelly says full fraction = 0.09 (9%)
           Using 25% Kelly (default) → 0.0225 (2.25%)
           Stake = 1000 * 0.0225 = $22.50
        ------------------------------------------------------------
        """
        # --------------------------------------------------------
        # Step 1. Calculate "b", the net profit per $1 if you win.
        # Example: decimal 1.8333 → profit_if_win = 0.8333 per $1
        # --------------------------------------------------------
        profit_if_win = decimal_odds - 1.0

        # If decimal_odds is invalid or <= 1, we can’t compute a meaningful Kelly.
        if profit_if_win <= 0:
            return 0.0

        # --------------------------------------------------------
        # Step 2. Compute full Kelly fraction (f*).
        #
        # Formula: f* = (b*p - q) / b
        #   p = probability of winning
        #   q = 1 - p = probability of losing
        #   b = profit per $1 if win
        #
        # Interpretation:
        #   - The numerator (b*p - q) is your "edge" (expected net per $1)
        #   - Dividing by b normalizes it to a bankroll fraction
        # --------------------------------------------------------
        prob_lose = 1.0 - prob_win
        full_kelly_fraction = ((profit_if_win * prob_win) - prob_lose) / profit_if_win

        # Kelly fraction can be negative if no edge (means don't bet).
        # We cap the minimum at 0.
        full_kelly_fraction = max(0.0, full_kelly_fraction)

        # --------------------------------------------------------
        # Step 3. Apply a fractional Kelly multiplier for safety.
        #   - self.kelly_fraction defaults to 0.25 (25% Kelly)
        #   - This smooths volatility and reduces bankroll swings.
        # --------------------------------------------------------
        fractional_kelly_fraction = full_kelly_fraction * self.kelly_fraction

        # --------------------------------------------------------
        # Step 4. Convert that fraction into a dollar stake.
        #   stake = bankroll * fraction
        #   Example: 0.025 × $1000 = $25 bet
        # --------------------------------------------------------
        raw_stake_dollars = self.bankroll * fractional_kelly_fraction

        # --------------------------------------------------------
        # Step 5. Apply an absolute cap on bet size (risk control).
        #   - self.max_stake_pct defaults to 0.10 (10% of bankroll)
        #   - Prevents oversized bets even with strong edges.
        # --------------------------------------------------------
        max_allowed_stake = self.bankroll * self.max_stake_pct

        # Return the stake value, respecting both lower and upper bounds.
        stake_dollars = max(0.0, min(raw_stake_dollars, max_allowed_stake))
        return stake_dollars

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