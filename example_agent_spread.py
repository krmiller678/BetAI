"""
example_agent_spread.py (simple)
Run home cover (ATS) probability predictions for a single matchup
using the trained Logistic Regression, Naive Bayes, and Random Forest spread models.
Stats are pulled live via nflreadpy (no CSV required).

Note on sign: spread_line is from the HOME team's perspective (negative = home favored).
"""

import pandas as pd
import nflreadpy as nfl
from models import LRSpread, NBSpread, RFSpread


# ============================================================
# Feature Builder
# ============================================================


def build_matchup_features(
    home_team: str, away_team: str, week: int, season: int, spread_line: float
) -> pd.DataFrame:
    """Construct a single-row dataframe of home-minus-away pregame stats
    for the specified week and season. Includes 'week' and 'spread_line'."""

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
# Example Run (single game)
# ============================================================

if __name__ == "__main__":
    season = 2025
    week = 6  # Set this to the most recent completed week
    home_team = "ARI"
    away_team = "GB"
    spread_line = 2.5  # Home perspective

    # Build features directly from NFL API
    features = build_matchup_features(
        home_team, away_team, week, season, spread_line
    )

    # Load models
    rf = RFSpread()
    nb = NBSpread()
    lr = LRSpread()

    # Predict home-cover probabilities
    rf_prob = rf.predict_proba(features)[0]
    nb_prob = nb.predict_proba(features)[0]
    lr_prob = lr.predict_proba(features)[0]

    # Display results
    print(
        f"\n=== ATS Home-Cover Probability Predictions (Home line {spread_line:+.1f}) ==="
    )
    print(f"Matchup: {away_team} @ {home_team} (Week {week}, Season {season})")
    print(f"Random Forest:       {rf_prob:.3f}")
    print(f"Naive Bayes:         {nb_prob:.3f}")
    print(f"Logistic Regression: {lr_prob:.3f}")

    ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3
    print(f"Ensemble Average:    {ensemble_prob:.3f}\n")

    # Simple recommendation: Home if p >= 0.5 else Away (flip line for away)
    if ensemble_prob >= 0.5:
        print(f"Recommendation: Take HOME {home_team} {spread_line:+.1f}")
    else:
        print(f"Recommendation: Take AWAY {away_team} {-spread_line:+.1f}")
