"""
models_train.py
Train 3 models (Logistic Regression, Naive Bayes, Random Forest)
to predict home team win probability using pre-game stats only.
"""

import os
from pathlib import Path
import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

import nflreadpy as nfl


# ============================================================
# Setup
# ============================================================

MODEL_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent / "trained_models"
)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Data Loading and Feature Engineering
# ============================================================


def load_game_level_data(seasons=[2024, 2025]):
    """
    Load team stats and schedules, merge into one game-level dataset.
    Each row = 1 game, with home and away team stats joined.
    Only uses pre-game stats.
    """
    print("Loading game-level data...")

    # Load schedules and team stats
    schedules = nfl.load_schedules(seasons=seasons).to_pandas()
    stats = nfl.load_team_stats(seasons=seasons).to_pandas()

    # Keep only relevant columns from team stats
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
    ]
    stats = stats[keep_cols]

    # Rename for home and away before merging
    home_stats = stats.rename(
        columns=lambda c: c if c in ["season", "week", "team"] else c + "_home"
    )
    away_stats = stats.rename(
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

    # Target variable: home win
    df["home_win"] = (df["home_score"] > df["away_score"]).astype(int)

    # Compute differentials
    def safe_diff(df, home_col, away_col, new_col):
        if home_col in df.columns and away_col in df.columns:
            df[new_col] = df[home_col] - df[away_col]
        else:
            df[new_col] = 0  # default to 0 if missing

    diffs = {
        "passing_epa_diff": ("passing_epa_home", "passing_epa_away"),
        "rushing_epa_diff": ("rushing_epa_home", "rushing_epa_away"),
        "passing_yards_diff": ("passing_yards_home", "passing_yards_away"),
        "rushing_yards_diff": ("rushing_yards_home", "rushing_yards_away"),
        "sacks_diff": ("def_sacks_home", "def_sacks_away"),
        "interceptions_diff": (
            "def_interceptions_home",
            "def_interceptions_away",
        ),
        "fumbles_forced_diff": (
            "def_fumbles_forced_home",
            "def_fumbles_forced_away",
        ),
    }

    for new_col, (home_col, away_col) in diffs.items():
        safe_diff(df, home_col, away_col, new_col)

    # Feature list for modeling
    features = list(diffs.keys()) + ["week"]

    # Drop rows with missing values
    df = df.dropna(subset=features + ["home_win"]).reset_index(drop=True)

    print(f"Loaded {len(df)} games with {len(features)} features.")
    return df, features


# ============================================================
# Feature Selection
# ============================================================


def select_k_best(X, y, k=6):
    """Select the top K features based on univariate F-test."""
    selector = SelectKBest(score_func=f_classif, k=min(k, X.shape[1]))
    X_new = selector.fit_transform(X, y)
    selected = X.columns[selector.get_support()]
    print("Selected features:", list(selected))
    return pd.DataFrame(X_new, columns=selected), list(selected)


# ============================================================
# Training Utilities
# ============================================================


def train_and_save(model, model_name, X_train, y_train, X_test, y_test):
    print(f"Training {model_name} ...")
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)

    model_path = MODEL_DIR / f"{model_name}.pkl"
    joblib.dump(model, model_path)
    print(f"Saved {model_name} to {model_path}, accuracy = {acc:.4f}")
    return acc


def save_feature_list(feature_names, model_name):
    path = MODEL_DIR / f"{model_name}_features.txt"
    with open(path, "w") as f:
        for feat in feature_names:
            f.write(f"{feat}\n")
    print(f"Saved {model_name} feature list to {path}")


# ============================================================
# Main Pipeline
# ============================================================


def main():
    # 1. Load and preprocess data
    df, candidate_features = load_game_level_data(seasons=[2024, 2025])

    X = df[candidate_features]
    y = df["home_win"]

    # 2. Feature selection
    X_sel, selected_feats = select_k_best(
        X, y, k=min(6, len(candidate_features))
    )

    # Save selected features
    for name in ["logistic_regression", "naive_bayes", "random_forest"]:
        save_feature_list(selected_feats, name)

    # 3. Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X_sel, y, test_size=0.2, random_state=42
    )

    # 4. Train models
    accs = {}
    accs["logistic_regression"] = train_and_save(
        LogisticRegression(max_iter=500),
        "logistic_regression",
        X_train,
        y_train,
        X_test,
        y_test,
    )

    accs["naive_bayes"] = train_and_save(
        GaussianNB(), "naive_bayes", X_train, y_train, X_test, y_test
    )

    accs["random_forest"] = train_and_save(
        RandomForestClassifier(n_estimators=100, random_state=42),
        "random_forest",
        X_train,
        y_train,
        X_test,
        y_test,
    )

    # 5. Summary
    print("\n=== Summary ===")
    for m, a in accs.items():
        print(f"{m}: {a:.4f}")


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()
