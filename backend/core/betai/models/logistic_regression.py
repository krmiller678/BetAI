class MoneylineLR:
    """Very simple placeholder; replace with real sklearn model later."""
    feature_list = ["seconds_left","score_diff","is_home","pregame_elo_diff","has_possession"]
    def predict_proba(self, df) -> float:
        base = 0.5
        base += 0.04 * float(df["is_home"].iloc[0])
        base += 0.05 * float(df["has_possession"].iloc[0])
        base += 0.02 * (float(df["score_diff"].iloc[0]) / 3.0)
        return max(0.01, min(0.99, base))