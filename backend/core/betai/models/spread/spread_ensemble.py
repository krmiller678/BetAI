import pandas as pd
import nflreadpy as nfl
from .logistic_regression_spread import LRSpread
from .naive_bayes_spread import NBSpread
from .random_forest_spread import RFSpread
from ..abbreviations import nfl_team_abbr


class Spread:
    """Ensemble wrapper for spread models mirroring the moneyline ensemble API."""

    def build_matchup_features(self, home_team: str, away_team: str, week: int, season: int) -> pd.DataFrame:
        """
        Build the same feature set used by the spread-trained models.
        Copied/adapted from the coordinator's _compute_features implementation.
        """
        stats = nfl.load_team_stats(seasons=[season]).to_pandas()

        home = stats[(stats["team"] == home_team) & (stats["week"] == week)]
        away = stats[(stats["team"] == away_team) & (stats["week"] == week)]

        def _fallback_team_row(team_code: str, req_week: int):
            tw = stats[stats["team"] == team_code]
            if tw.empty:
                return pd.DataFrame(), None
            available = sorted(set(int(x) for x in tw["week"].tolist() if pd.notna(x)))
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
        """
        Compute an ensemble spread-cover probability from the provided context.

        Behavior mirrors `moneyline_ensemble.Moneyline.predict_proba`:
        - Map display names via `nfl_team_abbr` when available.
        - Try weeks 10..1 until matchup features can be built from nflreadpy.
        - Query LR/NB/RF spread models and average their cover probabilities.
        """
        # Season default mirrors moneyline (easy to change later)
        season = int(context.get("season") or 2025)

        # Map display names to abbreviations when possible
        home_key = context.get("home_team") or context.get("home")
        away_key = context.get("away_team") or context.get("away")
        home_team = nfl_team_abbr.get(home_key, home_key)
        away_team = nfl_team_abbr.get(away_key, away_key)

        # Use provided week if present, otherwise try recent weeks
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

        # If the context carries a spread point, ensure the feature contains it
        if "point" in context or "spread" in context:
            spread_val = context.get("point") or context.get("spread")
            try:
                features["spread_line"] = float(spread_val)
            except Exception:
                pass

        # Load models
        rf = RFSpread()
        nb = NBSpread()
        lr = LRSpread()

        # Each model's predict_proba is expected to return an array-like
        rf_prob = float(rf.predict_proba(features)[0])
        nb_prob = float(nb.predict_proba(features)[0])
        lr_prob = float(lr.predict_proba(features)[0])

        ensemble_prob = (rf_prob + nb_prob + lr_prob) / 3.0

        # Show features and model outputs for local debugging (similar to Moneyline)
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(features)

        print(f"\n=== Spread Cover Predictions ===")
        print(f"Matchup: {away_team} @ {home_team} (Week {used_week}, Season {season})")
        print(f"Random Forest (cover): {rf_prob:.3f}")
        print(f"Naive Bayes (cover):   {nb_prob:.3f}")
        print(f"Logistic Regression:    {lr_prob:.3f}")

        print(f"Ensemble Average:       {ensemble_prob:.3f}\n")

        # Simple, actionable recommendation
        side = "HOME (cover)" if ensemble_prob >= 0.5 else "AWAY (cover)"
        print(f"Recommendation: TAKE {side} (ensemble p = {ensemble_prob:.3f})")

        return ensemble_prob
