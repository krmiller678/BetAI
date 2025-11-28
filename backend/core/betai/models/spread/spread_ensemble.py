import pandas as pd
import nflreadpy as nfl
from .logistic_regression_spread import LRSpread
from .naive_bayes_spread import NBSpread
from .random_forest_spread import RFSpread
from ..abbreviations import nfl_team_abbr


class Spread:
    """Ensemble wrapper for spread models.

    This class builds matchup features (home minus away stats) and queries
    three trained models (LR, NB, RF). It averages their "cover"
    probabilities and returns a single ensemble estimate.
    """

    def build_matchup_features(self, home_team: str, away_team: str, week: int, season: int) -> pd.DataFrame:
        """Return a one-row DataFrame of features for the given matchup.

        The features are simple differences (home - away) for the stats used
        by the trained spread models. If exact week rows are missing, the
        function will try to fall back to the most recent available week
        for each team.
        """
        # Load team-level stats for the requested season
        stats = nfl.load_team_stats(seasons=[season]).to_pandas()

        # Select rows for the exact week; fallback logic below will handle
        # cases where week-level rows are not yet available.
        home = stats[(stats["team"] == home_team) & (stats["week"] == week)]
        away = stats[(stats["team"] == away_team) & (stats["week"] == week)]

        # Helper: when exact-week rows are missing, pick the best fallback week
        def _fallback_team_row(team_code: str, req_week: int):
            tw = stats[stats["team"] == team_code]
            if tw.empty:
                return pd.DataFrame(), None
            available = sorted(set(int(x) for x in tw["week"].tolist() if pd.notna(x)))
            # Prefer the latest week <= requested week, otherwise use max available
            candidates = [w for w in available if w <= int(req_week)]
            use_week = max(candidates) if candidates else max(available)
            return tw[tw["week"] == use_week], use_week

        if home.empty or away.empty:
            home_rows, home_week_used = _fallback_team_row(home_team, week)
            away_rows, away_week_used = _fallback_team_row(away_team, week)
            if not home_rows.empty and not away_rows.empty:
                home = home_rows
                away = away_rows
            else:
                raise ValueError(
                    f"Could not find stats for {home_team} vs {away_team} (Week {week}, Season {season})"
                )

        # Safe subtraction helper: return 0.0 if either column is missing
        def safe_diff(col_home, col_away):
            return (
                float(home[col_home].values[0] - away[col_away].values[0])
                if col_home in home.columns and col_away in away.columns
                else 0.0
            )

        sample = pd.DataFrame(
            [
                {
                    "passing_epa_diff": safe_diff("passing_epa", "passing_epa"),
                    "rushing_epa_diff": safe_diff("rushing_epa", "rushing_epa"),
                    "passing_yards_diff": safe_diff("passing_yards", "passing_yards"),
                    "rushing_yards_diff": safe_diff("rushing_yards", "rushing_yards"),
                    "sacks_diff": safe_diff("def_sacks", "def_sacks"),
                    "interceptions_diff": safe_diff("def_interceptions", "def_interceptions"),
                    "fumbles_forced_diff": safe_diff("def_fumbles_forced", "def_fumbles_forced"),
                    "fg_pct_diff": safe_diff("fg_pct", "fg_pct"),
                    "penalty_yards_diff": safe_diff("penalty_yards", "penalty_yards"),
                    "week": int(week),
                    "spread_line": 0.0,  # placeholder; caller may inject actual spread if needed
                }
            ]
        )

        return sample

    def predict_proba(self, context: dict) -> float:
        """Return ensemble cover probability for the provided context.

        Steps:
        1. Resolve season and team identifiers (map display names to
           abbreviations when possible).
        2. Try candidate weeks (provided week or recent weeks) and call
           `build_matchup_features` until features are available.
        3. If a spread line is present in `context`, insert it into the
           features DataFrame.
        4. Load each model, get per-model cover probabilities, and return
           their arithmetic mean.
        """

        # 1) Basic context normalization
        season = int(context.get("season") or 2025)
        home_key = context.get("home_team") or context.get("home")
        away_key = context.get("away_team") or context.get("away")
        home_team = nfl_team_abbr.get(home_key, home_key)
        away_team = nfl_team_abbr.get(away_key, away_key)

        # 2) Candidate weeks: respect provided week, else try recent weeks
        provided_week = context.get("week")
        candidates = [int(provided_week)] if provided_week is not None else list(range(10, 0, -1))

        features = None
        used_week = None
        last_exc = None
        for wk in candidates:
            try:
                features = self.build_matchup_features(home_team, away_team, int(wk), season)
                used_week = wk
                break
            except Exception as exc:
                last_exc = exc
                continue

        if features is None:
            raise ValueError(f"Could not build features for {away_team} @ {home_team}. Last error: {last_exc}")

        # 3) Inject spread_line into features if provided by caller
        if "point" in context or "spread" in context:
            spread_val = context.get("point") or context.get("spread")
            try:
                features["spread_line"] = float(spread_val)
            except Exception:
                pass

        # 4) Load models and get per-model probabilities
        rf = RFSpread()
        nb = NBSpread()
        lr = LRSpread()

        rf_prob = float(rf.predict_proba(features)[0])
        nb_prob = float(nb.predict_proba(features)[0])
        lr_prob = float(lr.predict_proba(features)[0])

        ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3.0

        # 5) Debug prints
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(features)

        print("\n=== Spread Cover Predictions ===")
        print(f"Matchup: {away_team} @ {home_team} (Week {used_week}, Season {season})")
        print(f"Random Forest (cover): {rf_prob:.3f}")
        print(f"Naive Bayes (cover):   {nb_prob:.3f}")
        print(f"Logistic Regression:    {lr_prob:.3f}")

        print(f"Ensemble Average:       {ensemble_prob:.3f}\n")

        side = "HOME (cover)" if ensemble_prob >= 0.5 else "AWAY (cover)"
        print(f"Recommendation: TAKE {side} (ensemble p = {ensemble_prob:.3f})")

        return ensemble_prob
