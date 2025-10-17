"""
example_agent_spread.py
Run home cover (ATS) probability predictions for a given home/away matchup
using the trained Logistic Regression, Naive Bayes, and Random Forest spread models.
Stats are pulled live via nflreadpy (no CSV required).

Note on sign convention: spread_line is from the home team's perspective.
Negative = home favored, positive = home underdog.
"""

import argparse
import pandas as pd
import nflreadpy as nfl
from models import LRSpread, NBSpread, RFSpread

# ============================================================
# Feature Builder
# ============================================================


def build_matchup_features(
    home_team: str, away_team: str, week: int, season: int, spread_line: float
) -> pd.DataFrame:
    """
    Construct a single-row dataframe of home-minus-away pregame stats
    pulled live from NFL API using nflreadpy.
    Includes 'week' to match the training feature space.
    """

    # Load up-to-date team stats for the season
    stats = nfl.load_team_stats(seasons=[season]).to_pandas()

    # Filter rows for home and away teams for the given week
    home = stats[(stats["team"] == home_team) & (stats["week"] == week)]
    away = stats[(stats["team"] == away_team) & (stats["week"] == week)]

    if home.empty or away.empty:
        raise ValueError(
            f"Could not find stats for {home_team} vs {away_team} (Week {week}, Season {season})"
        )

    # Safe differential helper
    def safe_diff(col_home, col_away):
        return (
            float(home[col_home].values[0] - away[col_away].values[0])
            if col_home in home.columns and col_away in away.columns
            else 0.0
        )

    # Compute the features used in model training
    sample = pd.DataFrame(
        [
            {
                "passing_epa_diff": safe_diff("passing_epa", "passing_epa"),
                "rushing_epa_diff": safe_diff("rushing_epa", "rushing_epa"),
                "passing_yards_diff": safe_diff(
                    "passing_yards", "passing_yards"
                ),
                "rushing_yards_diff": safe_diff(
                    "rushing_yards", "rushing_yards"
                ),
                "sacks_diff": safe_diff("def_sacks", "def_sacks"),
                "interceptions_diff": safe_diff(
                    "def_interceptions", "def_interceptions"
                ),
                "fumbles_forced_diff": safe_diff(
                    "def_fumbles_forced", "def_fumbles_forced"
                ),
                "fg_pct_diff": safe_diff("fg_pct", "fg_pct"),
                "penalty_yards_diff": safe_diff(
                    "penalty_yards", "penalty_yards"
                ),
                "week": int(week),
                "spread_line": float(spread_line),
            }
        ]
    )

    return sample


# ============================================================
# Betting Utilities
# ============================================================

def american_break_even_prob(odds: float) -> float:
    """Break-even win probability for given American odds.
    Example: -110 -> 52.38%, +120 -> 45.45%.
    """
    if odds < 0:
        x = abs(odds)
        return x / (x + 100)
    else:
        return 100 / (odds + 100)


def expected_value_per_dollar(prob_win: float, odds: float) -> float:
    """Expected profit per $1 stake for an event with prob_win at given American odds.
    Pushes are treated as 0 EV and ignored.
    For -110: profit if win per $1 is 100/110 ≈ 0.9091; loss if lose is -1.
    """
    if odds < 0:
        x = abs(odds)
        payout_per_dollar = 100 / x
    else:
        payout_per_dollar = odds / 100
    return prob_win * payout_per_dollar - (1 - prob_win) * 1.0


# ============================================================
# CLI + Example Run
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATS home-cover probability and betting advice")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--week", type=int, default=6)
    parser.add_argument("--home_team", type=str, default="CIN")
    parser.add_argument("--away_team", type=str, default="PIT")
    parser.add_argument("--spread_line", type=float, default=-3.0, help="Home perspective: negative=favored")
    parser.add_argument("--home_odds", type=int, default=-110, help="American odds for betting HOME ATS")
    parser.add_argument("--away_odds", type=int, default=-110, help="American odds for betting AWAY ATS")
    args = parser.parse_args()

    season = args.season
    week = args.week
    home_team = args.home_team.upper()
    away_team = args.away_team.upper()
    spread_line = float(args.spread_line)
    home_odds = int(args.home_odds)
    away_odds = int(args.away_odds)

    # Build features directly from NFL API
    features = build_matchup_features(home_team, away_team, week, season, spread_line)

    # Load models
    rf = RFSpread()
    nb = NBSpread()
    lr = LRSpread()

    # Predict home-cover probabilities
    rf_prob = rf.predict_proba(features)[0]
    nb_prob = nb.predict_proba(features)[0]
    lr_prob = lr.predict_proba(features)[0]

    # Display results
    print(f"\n=== Home Cover (ATS) Probability for {away_team} @ {home_team} (Line {spread_line:+.1f}) ===")
    print(f"Random Forest:       {rf_prob:.3f}")
    print(f"Naive Bayes:         {nb_prob:.3f}")
    print(f"Logistic Regression: {lr_prob:.3f}")

    ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3
    print(f"Ensemble Average:    {ensemble_prob:.3f}")

    # Betting advice
    away_line = -spread_line
    home_be = american_break_even_prob(home_odds)
    away_be = american_break_even_prob(away_odds)
    ev_home = expected_value_per_dollar(ensemble_prob, home_odds)
    ev_away = expected_value_per_dollar(1 - ensemble_prob, away_odds)

    print("\n--- Market & EV ---")
    print(f"Home ATS {home_team} {spread_line:+.1f} at {home_odds:+d}: break-even {home_be:.3f}, EV per $100 = {ev_home*100:+.2f}")
    print(f"Away ATS {away_team} {away_line:+.1f} at {away_odds:+d}: break-even {away_be:.3f}, EV per $100 = {ev_away*100:+.2f}")

    rec = "NO BET"
    if ev_home > 0 or ev_away > 0:
        rec = f"BET HOME {home_team} {spread_line:+.1f} ({home_odds:+d})" if ev_home >= ev_away else f"BET AWAY {away_team} {away_line:+.1f} ({away_odds:+d})"
    print(f"\nRecommendation: {rec}\n")
