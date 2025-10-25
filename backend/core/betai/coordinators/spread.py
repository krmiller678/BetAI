# ------------------------------------------------------------
# spread.py
# Coordinator for spread-bet predictions
#
# This module implements the SpreadCoordinator: a small orchestration layer
# that converts live game context (teams, timestamp, market line) into the
# numeric features expected by our trained spread models, queries each model
# for a cover probability, and returns an ensemble probability back to the
# calling Agent. The Agent is responsible for applying betting logic (EV,
# sizing, bankroll management) based on the probabilities produced here.
#
# Responsibilities:
# - Normalize provider team identifiers to the abbreviations used by
#   nflreadpy.
# - Infer week/season information when not supplied in the provider context
#   using nflreadpy schedules.
# - Build a single-row feature DataFrame for the models using nflreadpy
#   team statistics (with a sensible fallback when the exact week is missing).
# - Query multiple model implementations (LR, NB, RF) and aggregate results
#   into a simple ensemble response.
#
# The coordinator is intentionally lightweight and side-effect free except
# for informative debug prints used while developing and troubleshooting.
# ------------------------------------------------------------

from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import pandas as pd
from datetime import datetime
import nflreadpy as nfl

# Import the trained spread models
from ..models.logistic_regression import LogisticRegressionModel as LRSpread
from ..models.naive_bayes import NaiveBayesModel as NBSpread
from ..models.random_forest import RandomForestModel as RFSpread

# Define the path to the registry folder where our feature lists or configs might live
REGISTRY_DIR = Path(__file__).resolve().parents[2] / "betai" / "registry"

# Define the specific file that lists which features are used by these models
FEATURES_FILE = REGISTRY_DIR / "spread_features.txt"


# ------------------------------------------------------------
# @class SpreadCoordinator
# @brief Handles all logic for spread bet predictions.
# @details
# The SpreadCoordinator acts like the Offensive Coordinator:
# - It receives the current game context (situation)
# - Converts that into structured numeric features
# - Calls the models to get cover probabilities
# - Returns this to the Agent for further decision-making
# ------------------------------------------------------------
class SpreadCoordinator:
    """
    SpreadCoordinator

    Orchestrates the end-to-end workflow for spread (against-the-spread)
    probability predictions.

    Public contract:
        - Input: a context dict describing a game/offer (teams, commence_time,
            provider price/point, optional week/season).
        - Output: a mapping containing per-model probabilities and an
            ensemble probability (simple mean across models).

    Implementation notes:
        - Models are instantiated in the constructor and must provide a
            `predict_proba` method that accepts a single-row DataFrame.
        - Team & schedule lookups use `nflreadpy` utilities; the coordinator
            normalizes provider team strings to the abbreviations used by
            nflreadpy (e.g., 'Atlanta Falcons' -> 'ATL').
        - If exact week-level team stats are not yet available (common in
            pregame contexts), the coordinator falls back to the most recent
            available week for each team so predictions can still be produced.
    """

    def __init__(self):
        # Create instances of our trained models
        self.models = {
            "logistic_regression": LRSpread(),
            "naive_bayes": NBSpread(),
            "random_forest": RFSpread(),
        }

        # --------------------------------------------------------
        # Feature resolution logic (simple & safe):
        # 1) Prefer the model's declared feature_list (single source of truth).
        # 2) If the features file exists AND has at least one non-comment line,
        #    use that to override (lets you tweak without code changes).
        # 3) If neither provides anything, fall back to a sensible default list.
        # --------------------------------------------------------

        # 1) Start from the first model's feature list (if provided)
        self.feature_list = list(
            getattr(next(iter(self.models.values())), "feature_list", []) or []
        )

        # 2) Optional file override (only if the file actually contains features)
        try:
            lines = FEATURES_FILE.read_text().splitlines()
            file_features = [
                ln.strip()
                for ln in lines
                if ln.strip() and not ln.startswith("#")
            ]
            if file_features:  # only override if non-empty
                self.feature_list = file_features
        except FileNotFoundError:
            # Silently ignore; we'll use model/defaults
            pass

        # 3) Final fallback (guarantee columns exist)
        if not self.feature_list:
            self.feature_list = [
                "passing_epa_diff",
                "rushing_epa_diff",
                "passing_yards_diff",
                "rushing_yards_diff",
                "sacks_diff",
                "interceptions_diff",
                "fumbles_forced_diff",
                "fg_pct_diff",
                "penalty_yards_diff",
                "week",
                "spread_line",
            ]

    def _build_row(self, context: Dict[str, Any]) -> pd.DataFrame:
        """
        Build a single-row DataFrame of numeric features for the models.

        The function reads the coordinator's resolved `feature_list` and
        extracts each value from the provided `context`, coercing missing
        values to 0.0. The resulting pandas DataFrame (one row) matches the
        column order expected by the trained models.

        Args:
            context: Mapping containing numeric or serializable feature values.

        Returns:
            pandas.DataFrame: one-row DataFrame with columns defined in
            `self.feature_list`.
        """

        # Assemble row values, using 0.0 as a safe default for missing keys
        row = {f: float(context.get(f, 0.0)) for f in self.feature_list}

        # Create a single-row DataFrame in the canonical column order
        df = pd.DataFrame([row], columns=self.feature_list)

        return df

    def _compute_features(
        self,
        home_team: str,
        away_team: str,
        week: int,
        season: int,
        spread_line: float,
    ) -> pd.DataFrame:
        """
        Construct model features for a matchup using nflreadpy team statistics.

        This routine loads team-level statistics for the given `season` and
        attempts to locate the rows for `home_team` and `away_team` at the
        requested `week`. If exact week-level rows are not available (common
        in pregame contexts), the function falls back to the most recent
        available week for each team so the models can still be evaluated.

        Args:
            home_team: Three-letter team abbreviation used by nflreadpy.
            away_team: Three-letter team abbreviation used by nflreadpy.
            week: Requested NFL week number.
            season: NFL season year.
            spread_line: The market spread (home perspective; negative means
                home is favored).

        Returns:
            pandas.DataFrame: single-row DataFrame containing the computed
            feature differences and the `week` and `spread_line` columns.
        """

        # Retrieve team statistics for the requested season using nflreadpy
        stats = nfl.load_team_stats(seasons=[season]).to_pandas()

        # Filter rows for home and away teams for the given week. If that
        # week's data isn't available yet (e.g. pregame for a future week),
        # fall back to the most recent available week for each team.
        home = stats[(stats["team"] == home_team) & (stats["week"] == week)]
        away = stats[(stats["team"] == away_team) & (stats["week"] == week)]

        def _fallback_team_row(team_code: str):
            tw = stats[stats["team"] == team_code]
            if tw.empty:
                return pd.DataFrame()
            # weeks available for this team
            available = sorted(
                set(int(x) for x in tw["week"].tolist() if pd.notna(x))
            )
            # prefer the latest week <= requested week, otherwise the max available
            candidates = [w for w in available if w <= int(week)]
            use_week = max(candidates) if candidates else max(available)
            return tw[tw["week"] == use_week], use_week

        if home.empty or away.empty:
            home_rows, home_week_used = _fallback_team_row(home_team)
            away_rows, away_week_used = _fallback_team_row(away_team)
            if not home_rows.empty and not away_rows.empty:
                home = home_rows
                away = away_rows
                print(
                    f"Using fallback team-week data: {home_team} week {home_week_used}, {away_team} week {away_week_used}"
                )
            else:
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
                    "passing_epa_diff": safe_diff(
                        "passing_epa", "passing_epa"
                    ),
                    "rushing_epa_diff": safe_diff(
                        "rushing_epa", "rushing_epa"
                    ),
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

    def recommend(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce spread-cover probabilities for a single game context.

        The method performs the following high-level steps:
          1. Normalize team identifiers (full names -> abbreviations).
          2. Infer missing `season` or `week` from the provider `commence_time`
             and nflreadpy schedules when necessary.
          3. Build the numeric feature row for the models via `_compute_features`.
          4. Query each model's `predict_proba` to obtain per-model probabilities.
          5. Aggregate the results into a simple ensemble (arithmetic mean).

        Args:
            context: Mapping with keys such as `home_team`, `away_team`,
                `commence_time`, `point` (spread), optional `week` and `season`,
                and (optionally) provider odds under `decimal_odds`.

        Returns:
            dict: {"model_probs": {...}, "ensemble_prob": float, ...}
        """
        # (No top-level debug print here — we'll print a full summary after evaluation)

        # Extract necessary fields from context
        home_team = context.get("home_team")
        away_team = context.get("away_team")
        week = context.get("week")
        season = context.get("season")
        spread_line = context.get("point")

        # Normalize team identifiers to abbreviations used by nflreadpy
        try:
            home_team = self._team_to_abbrev(
                home_team, int(season or nfl.get_current_season())
            )
        except Exception:
            # leave as-is; later checks will raise clear errors
            pass
        try:
            away_team = self._team_to_abbrev(
                away_team, int(season or nfl.get_current_season())
            )
        except Exception:
            pass

        # Infer season and week if missing. Prefer explicit values in context.
        if season is None:
            # nflreadpy exposes a helper to get the current season when needed
            try:
                season = int(context.get("season") or nfl.get_current_season())
            except Exception:
                season = int(nfl.get_current_season())

        if week is None:
            # Try to infer week from the event time and teams. Use commence_time
            # when available; otherwise fall back to current time.
            commence = context.get("commence_time")
            try:
                if commence:
                    dt = pd.to_datetime(commence)
                else:
                    dt = pd.Timestamp.now()
            except Exception:
                dt = pd.Timestamp.now()

            week = self._get_week_for_date(dt, season, home_team, away_team)

        # Debugging: Print which fields are missing
        missing_fields = [
            field
            for field, value in {
                "home_team": home_team,
                "away_team": away_team,
                "week": week,
                "season": season,
                "spread_line": spread_line,
            }.items()
            if value is None
        ]
        if missing_fields:
            print("Missing fields in context:", missing_fields)
            raise ValueError(
                f"Context is missing required fields for feature computation: {missing_fields}"
            )

        # Step 1: Dynamically compute the feature row
        X = self._compute_features(
            home_team, away_team, week, season, spread_line
        )

        # Step 2: Ask each model for its predicted probability
        model_probs = {
            name: float(model.predict_proba(X)[0])
            for name, model in self.models.items()
        }

        # Step 3: Compute the ensemble average probability
        ensemble_prob = sum(model_probs.values()) / len(model_probs)

        # Concise user-requested summary
        print("\n=== Spread Recommendation ===")
        # Teams, week and season
        print(f"Matchup: {away_team} @ {home_team}")
        print(f"Week: {week}, Season: {season}")

        # Each model's prediction
        print("\nModel predictions:")
        for name, p in model_probs.items():
            print(f"  {name}: {p:.3f}")

        # Final recommendation
        side = "HOME" if ensemble_prob >= 0.5 else "AWAY"
        print(
            f"\nFinal recommendation: TAKE {side} (ensemble p = {ensemble_prob:.3f})"
        )
        print("==============================\n")

        # Step 4: Return a clean, structured response for the Agent
        return {
            "model_probs": model_probs,  # Probabilities from each model
            "ensemble_prob": ensemble_prob,  # Average probability across models
            "p_model": ensemble_prob,  # Add p_model for compatibility
            "model_name": "ensemble",  # Add model_name to indicate ensemble usage
        }

    def get_week_for_date(date: datetime, season: int) -> int:
        """
        Determine the NFL week for a given date and season.

        Args:
            date (datetime): The date of the game.
            season (int): The NFL season year.

        Returns:
            int: The week number corresponding to the given date.
        """
        # Deprecated free function kept for backward-compatibility. Use
        # the instance helper `_get_week_for_date` instead.
        raise RuntimeError(
            "Use SpreadCoordinator._get_week_for_date(self, date, season, home_team=None, away_team=None)"
        )

    def _get_week_for_date(
        self,
        date: datetime,
        season: int,
        home_team: str | None = None,
        away_team: str | None = None,
    ) -> int:
        """
        Determine the NFL week for a given datetime and season.

        Strategy:
        - Load the schedule for the season via `nfl.load_schedules`.
        - Build a timezone-naive timestamp from 'gameday' + 'gametime' when
          available.
        - If both teams are provided, try to match that game exactly.
        - Otherwise, return the week for the schedule row with the closest
          start time to the provided `date`.
        """
        sched = nfl.load_schedules(seasons=[season]).to_pandas()
        if sched.empty:
            raise ValueError(f"No schedule rows found for season {season}")

        # Construct a game start timestamp column. 'gameday' contains a
        # YYYY-MM-DD date and 'gametime' contains time like '13:00' or may
        # be missing for TBD entries.
        if "gametime" in sched.columns:
            times = sched["gametime"].fillna("00:00")
            sched["_start"] = pd.to_datetime(
                sched["gameday"].astype(str) + " " + times, errors="coerce"
            )
        else:
            sched["_start"] = pd.to_datetime(sched["gameday"], errors="coerce")

        # Prefer exact team match when available
        if home_team and away_team:
            mask = (sched["home_team"] == home_team) & (
                sched["away_team"] == away_team
            )
            matched = sched[mask]
            if not matched.empty:
                return int(matched.iloc[0]["week"])

        # Fallback: closest start time to the provided date
        target = pd.Timestamp(date)
        if pd.isna(target):
            raise ValueError(
                "Provided date could not be parsed into a timestamp"
            )

        # Normalize timezone handling: make both schedule starts and target
        # timezone-aware in UTC so subtraction doesn't raise on tz-naive/vs-aware.
        if getattr(sched["_start"].dt, "tz", None) is None:
            sched["_start"] = sched["_start"].dt.tz_localize("UTC")

        if target.tzinfo is None:
            target = target.tz_localize("UTC")
        else:
            target = target.tz_convert("UTC")

        diffs = (sched["_start"] - target).abs()
        idx = diffs.idxmin()
        return int(sched.loc[idx, "week"])

    def _team_to_abbrev(self, team: str, season: int) -> str:
        """Normalize a team identifier to the NFL abbreviation used by team stats.

        Accepts already-correct abbreviations (e.g. 'ATL', 'MIA'), full names
        like 'Atlanta Falcons', or nicknames/location strings. Uses
        `nfl.load_teams` to build a mapping for the given season.
        """
        if not team:
            return team

        t = team.strip()
        # If it's already a short uppercase code (2-3 letters) return as-is
        if len(t) <= 3 and t.upper() == t:
            return t

        # nfl.load_teams does not accept a seasons kwarg; load all and filter
        teams = nfl.load_teams().to_pandas()
        # Build lookup maps
        by_abbrev = {row["team"]: row["team"] for _, row in teams.iterrows()}
        by_full = {
            row["full"].lower(): row["team"]
            for _, row in teams.iterrows()
            if row.get("full")
        }
        by_nick = {
            row["nickname"].lower(): row["team"]
            for _, row in teams.iterrows()
            if row.get("nickname")
        }
        by_loc = {
            row["location"].lower(): row["team"]
            for _, row in teams.iterrows()
            if row.get("location")
        }

        key = t.lower()
        if t in by_abbrev:
            return t
        if key in by_full:
            return by_full[key]
        if key in by_nick:
            return by_nick[key]
        if key in by_loc:
            # location match may be ambiguous; return first match
            return by_loc[key]

        parts = key.split()
        if parts:
            last = parts[-1]
            if last in by_nick:
                return by_nick[last]

        # As a fallback, attempt case-insensitive substring match on 'full'
        for full_name, abbr in by_full.items():
            if key in full_name:
                return abbr

        # If nothing matched, return original input (caller will detect missing data)
        return team


# Example usage
# print(get_week_for_date(datetime(2025, 10, 27), 2025))
