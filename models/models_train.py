import os
import joblib
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

import nflreadpy as nfl  # uses Polars internally per docs :contentReference[oaicite:0]{index=0}

# Where to save your trained models
MODEL_DIR = Path(__file__).resolve().parent / "trained_models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ========== 1. Load & Preprocess Data ==========

def load_and_merge_data(seasons = [2022, 2023]):
    """
    Loads the play-by-play and team stats from nflreadpy, merges them,
    filters clean plays, returns a DataFrame.
    """
    # Load play-by-play
    pbp = nfl.load_pbp(seasons)  # returns Polars DF; convert to pandas
    pbp = pbp.to_pandas()
    
    # Load team stats (you’ll merge offense & defense)  
    team_stats = nfl.load_team_stats(seasons=True).to_pandas()

    # Filter to regular-season plays (if season_type exists)
    if "season_type" in pbp.columns:
        pbp = pbp[pbp["season_type"] == "REG"]
    
    # Drop plays with missing essential info
    essential_cols = ["yardline_100", "down", "ydstogo", "posteam", "defteam", "total_home_score", "total_away_score"]
    pbp = pbp.dropna(subset=essential_cols)

    # Create some basic features
    # score differential from offense perspective
    pbp["score_differential"] = pbp["total_home_score"] - pbp["total_away_score"]
    # Make a feature is_home for posteam
    pbp["is_home"] = (pbp["posteam"] == pbp["home_team"]).astype(int)

    # Merge team stats for offense (posteam) and defense (defteam)
    # Columns that should NOT be renamed
    key_cols = ["season", "week", "team"]
    
    off = team_stats.rename(
        columns=lambda c: c + "_off" if c not in key_cols else c
    )
    defn = team_stats.rename(
        columns=lambda c: c + "_def" if c not in key_cols else c
    )
    
    # Then merge correctly
    pbp = pbp.merge(off, left_on=["season","week","posteam"],
                         right_on=["season","week","team"], how="left")
    pbp = pbp.merge(defn, left_on=["season","week","defteam"],
                         right_on=["season","week","team"], how="left")
    print(off.columns.tolist())

    # Engineer differential stats
    # Example: passing_epa_off - passing_epa_def
    for stat in ["passing_epa", "rushing_epa"]:
        off_col = stat + "_off"
        def_col = stat + "_def"
        if off_col in pbp.columns and def_col in pbp.columns:
            pbp[f"{stat}_diff"] = pbp[off_col] - pbp[def_col]

    # Label: did the posteam win?
    pbp["win_label"] = (pbp["posteam_score_post"] > pbp["defteam_score_post"]).astype(int)

    return pbp

def build_feature_matrix(pbp: pd.DataFrame, feature_cols: list):
    """
    Given the merged pbp DataFrame and a list of feature columns,
    returns X (features) and y (labels), dropping any rows with NaNs in features.
    """
    df = pbp.copy()
    # Only keep rows where all feature_cols are present
    df = df.dropna(subset=feature_cols + ["win_label"])
    X = df[feature_cols].reset_index(drop=True)
    y = df["win_label"].reset_index(drop=True)
    return X, y

# ========== 2. Feature Selection ==========

def select_k_best(X: pd.DataFrame, y: pd.Series, k: int = 10):
    """Select top k features using univariate F-test."""
    selector = SelectKBest(score_func=f_classif, k=min(k, X.shape[1]))
    X_sel = selector.fit_transform(X, y)
    selected = X.columns[selector.get_support()]
    print("Selected features:", list(selected))
    # Return DataFrame with those features
    return pd.DataFrame(X_sel, columns=selected), list(selected)

# ========== 3. Train & Save ==========

def train_and_save(model, model_name: str, X_train, y_train, X_test, y_test):
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
    # 1. Load & merge
    print("Loading and merging data...")
    pbp = load_and_merge_data(seasons=[2022, 2023])

    # 2. Build feature matrix
    # Define your candidate features (filter out ones you cannot use live)
    candidate_features = [
        "quarter_seconds_remaining", "game_seconds_remaining",
        "yardline_100", "down", "ydstogo", "goal_to_go",
        "score_differential", "is_home",
        "passing_epa_diff", "rushing_epa_diff"
    ]
    X, y = build_feature_matrix(pbp, candidate_features)

    # 3. Feature selection
    X_sel, selected_feats = select_k_best(X, y, k=8)

    # Save feature list for later inference
    save_feature_list(selected_feats, "logistic_regression")
    save_feature_list(selected_feats, "naive_bayes")
    save_feature_list(selected_feats, "random_forest")

    # 4. Split train/test
    X_train, X_test, y_train, y_test = train_test_split(X_sel, y, test_size=0.2, random_state=42)

    # 5. Train models
    accs = {}
    accs["logistic_regression"] = train_and_save(LogisticRegression(max_iter=500), "logistic_regression", X_train, y_train, X_test, y_test)
    accs["naive_bayes"] = train_and_save(GaussianNB(), "naive_bayes", X_train, y_train, X_test, y_test)
    accs["random_forest"] = train_and_save(RandomForestClassifier(n_estimators=100, random_state=42), "random_forest", X_train, y_train, X_test, y_test)

    print("\n=== Summary ===")
    for m, a in accs.items():
        print(f"{m}: {a:.4f}")

if __name__ == "__main__":
    main()