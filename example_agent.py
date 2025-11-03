"""
example_agent.py
Run win probability predictions for a given home/away matchup
using the trained Logistic Regression, Naive Bayes, and Random Forest models.
Stats are pulled live via nflreadpy (no CSV required).
"""

import pandas as pd
import nflreadpy as nfl
from models.logistic_regression import LogisticRegressionModel
from models.naive_bayes import NaiveBayesModel
from models.random_forest import RandomForestModel

# ============================================================
# Feature Builder
# ============================================================

def build_matchup_features(home_team: str, away_team: str, week: int, season: int) -> pd.DataFrame:
    """
    Construct a single-row dataframe of home-minus-away pregame stats
    pulled live from NFL API using nflreadpy.
    """

    # Load up-to-date team stats for the season
    stats = nfl.load_team_stats(seasons=[season]).to_pandas()

    # Filter rows for home and away teams for the given week
    home = stats[(stats["team"] == home_team) & (stats["week"] == week)]
    away = stats[(stats["team"] == away_team) & (stats["week"] == week)]

    if home.empty or away.empty:
        raise ValueError(f"Could not find stats for {home_team} vs {away_team} (Week {week}, Season {season})")

    # Safe differential helper
    def safe_diff(col_home, col_away):
        return float(home[col_home].values[0] - away[col_away].values[0]) \
            if col_home in home.columns and col_away in away.columns else 0.0

    # Compute the features used in model training
    sample = pd.DataFrame([{
        "week": week,
        "passing_epa_diff": safe_diff("passing_epa", "passing_epa"),
        "rushing_epa_diff": safe_diff("rushing_epa", "rushing_epa"),
        "total_epa_diff": safe_diff("off_epa", "def_epa"),
        "success_rate_diff": safe_diff("off_success_rate", "def_success_rate"),
        "turnover_diff": safe_diff("turnovers", "turnovers"),
    }])

    return sample

# ============================================================
# Example Run
# ============================================================

if __name__ == "__main__":
    season = 2025
    week = 4 # make this the most recent week that just occurred, need to add error handling
             # for the event that the stats are not completely up to date
    home_team = "WAS"
    away_team = "CHI"

    # Build features directly from NFL API
    features = build_matchup_features(home_team, away_team, week, season)

    # Load models
    rf = RandomForestModel()
    nb = NaiveBayesModel()
    lr = LogisticRegressionModel()

    # Predict win probabilities
    rf_prob = rf.predict_proba(features)[0]
    nb_prob = nb.predict_proba(features)[0]
    lr_prob = lr.predict_proba(features)[0]

    # Display results
    
    print(f"\n=== Win Probability Predictions ({home_team}) ===")
    print(f"Matchup: {away_team} @ {home_team} (Week {week}, Season {season})")
    print(f"Random Forest:       {rf_prob:.3f}")
    print(f"Naive Bayes:         {nb_prob:.3f}")
    print(f"Logistic Regression: {lr_prob:.3f}")

    ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3
    print(f"Ensemble Average:    {ensemble_prob:.3f}\n")
