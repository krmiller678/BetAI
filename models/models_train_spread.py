"""
models_train_spread.py

Train 3 spread models (Logistic Regression, Naive Bayes, Random Forest)
to predict home cover probability (ATS) using pre-game stats only.

Mirrors models_train_moneyline.py structure for familiarity.

Target definition (home ATS):
    home_margin = home_score - away_score
    spread_line: home team's point spread (negative if favored, positive if underdog)
    push if (home_margin + spread_line == 0)
    home_cover = 1 if (home_margin + spread_line > 0) else 0

This matches common conventions where a home favorite (spread_line = -3)
covers if they win by 4+; a home underdog (+3) covers if they lose by <= 2 or win.
"""

from pathlib import Path
import joblib
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import nflreadpy as nfl


# ============================================================
# Setup
# ============================================================

MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Data Loading and Feature Engineering
# ============================================================


def load_game_level_data_spread(seasons=[2023, 2024, 2025]):
    """Build a per-game dataset with features and ATS target (home_cover).

    Returns:
        df: pandas DataFrame with one row per game, feature columns, and 'home_cover'
        features: list of feature column names
        meta_cols: minimal identifiers helpful for inspection (game_id, teams, week)
    """
    print("Loading schedules and team stats…")

    # Load schedules and team stats
    schedules = nfl.load_schedules(seasons=seasons)
    try:
        schedules = schedules.to_pandas()
    except Exception:
        pass

    stats = nfl.load_team_stats(seasons=seasons)
    try:
        stats = stats.to_pandas()
    except Exception:
        pass

    # Team stats columns to keep (same as moneyline script for now)
    keep_cols = [
        "season",
        "week",
        "team",
        "passing_epa",
        "rushing_epa",
        "passing_yards",
        "rushing_yards",
        "def_sacks",
        "def_interceptions",
        "def_fumbles_forced",
        "fg_pct",
        "penalty_yards",
    ]
    stats = stats[keep_cols].copy()

    # --- Lag and smooth team stats (leakage-safe) ---
    # For each team and season, shift metrics by 1 week so we only use information
    # available BEFORE the current game. Also compute a rolling-3 average on the
    # shifted series to smooth early-season noise.
    stats = stats.sort_values(["team", "season", "week"]).reset_index(
        drop=True
    )
    group = stats.groupby(["team", "season"], sort=False, group_keys=False)

    metric_cols = [
        "passing_epa",
        "rushing_epa",
        "passing_yards",
        "rushing_yards",
        "def_sacks",
        "def_interceptions",
        "def_fumbles_forced",
        "fg_pct",
        "penalty_yards",
    ]

    for col in metric_cols:
        shifted = group[col].shift(1)
        stats[f"{col}_lag1"] = shifted
        # rolling mean of the last up-to-3 prior weeks (excludes current week)
        stats[f"{col}_roll3"] = shifted.groupby(
            [stats["team"], stats["season"]]
        ).transform(lambda s: s.rolling(3, min_periods=1).mean())

    # Prepare home/away copies for merge
    # Use the smoothed prior-week (roll3) features for modeling
    roll3_cols = [f"{c}_roll3" for c in metric_cols]
    stats_roll3 = stats[["season", "week", "team"] + roll3_cols].copy()

    home_stats = stats_roll3.rename(
        columns=lambda c: c if c in ["season", "week", "team"] else c + "_home"
    )
    away_stats = stats_roll3.rename(
        columns=lambda c: c if c in ["season", "week", "team"] else c + "_away"
    )

    # Merge home stats
    df = schedules.merge(
        home_stats,
        left_on=["season", "week", "home_team"],
        right_on=["season", "week", "team"],
        how="left",
    )

    # Merge away stats
    df = df.merge(
        away_stats,
        left_on=["season", "week", "away_team"],
        right_on=["season", "week", "team"],
        how="left",
    )

    # Compute ATS target
    # Require spread_line and final scores
    required_cols = ["home_score", "away_score", "spread_line"]
    missing_req = [c for c in required_cols if c not in df.columns]
    if missing_req:
        raise RuntimeError(
            f"Missing required columns for ATS target: {missing_req}"
        )

    df = df.dropna(subset=required_cols).copy()

    df["home_margin"] = df["home_score"] - df["away_score"]
    # push: exactly equals zero after applying spread
    df["ats_delta"] = df["home_margin"] + df["spread_line"]
    df["push"] = df["ats_delta"] == 0
    df = df.loc[~df["push"]].copy()
    df["home_cover"] = (df["ats_delta"] > 0).astype(int)

    # Compute differentials (same pattern as moneyline for initial features)
    def safe_diff(df_in, home_col, away_col, new_col):
        if home_col in df_in.columns and away_col in df_in.columns:
            df_in[new_col] = df_in[home_col] - df_in[away_col]
        else:
            df_in[new_col] = 0

    diffs = {
        "passing_epa_diff": (
            "passing_epa_roll3_home",
            "passing_epa_roll3_away",
        ),
        "rushing_epa_diff": (
            "rushing_epa_roll3_home",
            "rushing_epa_roll3_away",
        ),
        "passing_yards_diff": (
            "passing_yards_roll3_home",
            "passing_yards_roll3_away",
        ),
        "rushing_yards_diff": (
            "rushing_yards_roll3_home",
            "rushing_yards_roll3_away",
        ),
        "sacks_diff": ("def_sacks_roll3_home", "def_sacks_roll3_away"),
        "interceptions_diff": (
            "def_interceptions_roll3_home",
            "def_interceptions_roll3_away",
        ),
        "fumbles_forced_diff": (
            "def_fumbles_forced_roll3_home",
            "def_fumbles_forced_roll3_away",
        ),
        "fg_pct_diff": ("fg_pct_roll3_home", "fg_pct_roll3_away"),
        "penalty_yards_diff": (
            "penalty_yards_roll3_home",
            "penalty_yards_roll3_away",
        ),
    }

    for new_col, (h, a) in diffs.items():
        safe_diff(df, h, a, new_col)

    # Initial feature set (now includes the market spread line)
    # Sign convention: negative = home favored, positive = home underdog.
    # Including this conditions predictions on the actual posted line.
    features = list(diffs.keys()) + ["week", "spread_line"]

    # Drop rows with missing feature values just for our first pass
    df = df.dropna(subset=features + ["home_cover"]).reset_index(drop=True)

    meta_cols = [
        c
        for c in [
            "game_id",
            "season",
            "week",
            "home_team",
            "away_team",
            "spread_line",
        ]
        if c in df.columns
    ]

    print(f"Built ATS dataset: {len(df)} games, features={len(features)}")
    print(
        "Class balance (home_cover):",
        df["home_cover"].value_counts(normalize=True).to_dict(),
    )

    return df, features, meta_cols


def select_k_best(X, y, k=8, force_include: list[str] | None = None):
    """Select the top K features based on univariate F-test."""
    selector = SelectKBest(score_func=f_classif, k=min(k, X.shape[1]))
    selector.fit(X, y)
    selected = list(X.columns[selector.get_support()])

    # Ensure certain features are always included (e.g., spread_line)
    force_include = force_include or []
    for col in force_include:
        if col not in selected and col in X.columns:
            selected.append(col)

    # Reduce X to selected columns (maintain order: selected first)
    X_selected = X[selected]
    print("Selected features:", selected)
    return X_selected, selected


def train_and_save(model, model_name, X_train, y_train, X_test, y_test):
    print(f"Training {model_name} …")
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    path = MODEL_DIR / f"{model_name}.pkl"
    joblib.dump(model, path)
    print(f"Saved {model_name} to {path}, accuracy = {acc:.4f}")
    return acc


def save_feature_list(feature_names, model_name):
    path = MODEL_DIR / f"{model_name}_features.txt"
    with open(path, "w") as f:
        for feat in feature_names:
            f.write(f"{feat}\n")
    print(f"Saved {model_name} feature list to {path}")


def main():
    # 1) Define season-based split
    train_seasons = [2023, 2024]
    test_seasons = [2025]
    all_seasons = sorted(set(train_seasons + test_seasons))

    # 2) Load and preprocess data for all seasons
    df, candidate_features, _ = load_game_level_data_spread(
        seasons=all_seasons
    )
    X = df[candidate_features]
    y = df["home_cover"]

    # 3) Create season-based partitions
    train_mask = df["season"].isin(train_seasons)
    test_mask = df["season"].isin(test_seasons)
    X_train_full, y_train = X.loc[train_mask], y.loc[train_mask]
    X_test_full, y_test = X.loc[test_mask], y.loc[test_mask]

    print(
        f"Season split: train {train_seasons} -> {len(X_train_full)} rows, test {test_seasons} -> {len(X_test_full)} rows"
    )
    if len(X_train_full) == 0 or len(X_test_full) == 0:
        raise RuntimeError(
            "Train/test split by season produced empty partition(s). Adjust seasons."
        )

    # 4) Fit feature selection on TRAIN ONLY, then apply to TEST
    X_train_sel, selected_feats = select_k_best(
        X_train_full,
        y_train,
        k=min(8, len(candidate_features)),
        force_include=["spread_line"],
    )
    # Align test to selected columns (missing columns shouldn't happen but guard anyway)
    for col in selected_feats:
        if col not in X_test_full.columns:
            X_test_full[col] = 0
    X_test_sel = X_test_full[selected_feats]

    # Save selected features for each model
    for name in ["lr_spread", "nb_spread", "rf_spread"]:
        save_feature_list(selected_feats, name)

    # 5) Train models
    accs = {}
    accs["lr_spread"] = train_and_save(
        LogisticRegression(max_iter=500),
        "lr_spread",
        X_train_sel,
        y_train,
        X_test_sel,
        y_test,
    )
    accs["nb_spread"] = train_and_save(
        GaussianNB(), "nb_spread", X_train_sel, y_train, X_test_sel, y_test
    )
    accs["rf_spread"] = train_and_save(
        RandomForestClassifier(n_estimators=100, random_state=42),
        "rf_spread",
        X_train_sel,
        y_train,
        X_test_sel,
        y_test,
    )

    # 6) Summary
    print("\n=== Summary ===")
    for m, a in accs.items():
        print(f"{m}: {a:.4f}")


if __name__ == "__main__":
    main()
