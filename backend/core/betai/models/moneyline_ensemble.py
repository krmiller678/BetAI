import pandas as pd
import nflreadpy as nfl
from .logistic_regression_moneyline import LRMoneyLine
from .naive_bayes_moneyline import NBMoneyLine
from .random_forest_moneyline import RFMoneyLine
from .abbreviations import nfl_team_abbr

class Moneyline:
    """Using API from moneyline_ensemble.py"""

    # ============================================================
    # Feature Builder
    # ============================================================

    def build_matchup_features(self, home_team: str, away_team: str, week: int, season: int) -> pd.DataFrame:
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
            "passing_epa_diff": safe_diff("passing_epa", "passing_epa"),
            "rushing_epa_diff": safe_diff("rushing_epa", "rushing_epa"),
            "passing_yards_diff": safe_diff("passing_yards", "passing_yards"),
            "rushing_yards_diff": safe_diff("rushing_yards", "rushing_yards"),
            "sacks_diff": safe_diff("def_sacks", "def_sacks"),
            "interceptions_diff": safe_diff("def_interceptions", "def_interceptions"),
            "fumbles_forced_diff": safe_diff("def_fumbles_forced", "def_fumbles_forced"),
            "fg_pct_diff": safe_diff("fg_pct", "fg_pct"),
            "penalty_yards_diff": safe_diff("penalty_yards", "penalty_yards")
        }])

        return sample

    # ============================================================
    # Example Run
    # ============================================================

    def predict_proba(self, context) -> float:
        season = 2025
        home_team = nfl_team_abbr[context.get("home_team")]
        away_team = nfl_team_abbr[context.get("away_team")]
        for i in range(10, 0, -1):
            try:
                week = i
                # Build features directly from NFL API
                features = self.build_matchup_features(home_team, away_team, week, season)
                print(f"Data pulled up through week {i}")
                break
            except Exception as e:
                print(f"Tried week {i}, data not yet available")

        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(features)

        # Load models
        rf = RFMoneyLine()
        nb = NBMoneyLine()
        lr = LRMoneyLine()

        # Predict win probabilities
        rf_prob = rf.predict_proba(features)[0]
        nb_prob = nb.predict_proba(features)[0]
        lr_prob = lr.predict_proba(features)[0]

        # Display results

        print(f"\n=== Win Probability Predictions for ({home_team}) ===")
        print(f"Matchup: {away_team} @ {home_team} (Week {week}, Season {season})")
        print(f"Random Forest:       {rf_prob:.3f}")
        print(f"Naive Bayes:         {nb_prob:.3f}")
        print(f"Logistic Regression: {lr_prob:.3f}")

        ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3

        print(f"Ensemble Average:    {ensemble_prob:.3f}\n")

        print(f"\n=== MoneyLine Recommendations ===")
        if ensemble_prob >= 0.5:
            moneyline_home = -1*(ensemble_prob/(1-ensemble_prob))*100
            print(f"Bet on {home_team} if MoneyLine is closer to 0 than {moneyline_home:.0f}")
            moneyline_away = ((1-(1-ensemble_prob))/(1-ensemble_prob))*100
            print(f"Bet on {away_team} if MoneyLine is greater than {moneyline_away:.0f}\n")
        else:
            moneyline_home = ((1-ensemble_prob)/ensemble_prob)*100
            print(f"Bet on {home_team} if MoneyLine is greater than {moneyline_home:.0f}")
            moneyline_away = -1*((1-ensemble_prob)/(1-(1-ensemble_prob)))*100
            print(f"Bet on {away_team} if MoneyLine is closer to 0 than {moneyline_away:.0f}\n")

        return ensemble_prob