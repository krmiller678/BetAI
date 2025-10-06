from models import LogisticRegressionModel, NaiveBayesModel, RandomForestModel

import pandas as pd

sample = pd.DataFrame([{
    "quarter_seconds_remaining": 400,
    "game_seconds_remaining": 1200,
    "yardline_100": 45,
    "down": 2,
    "ydstogo": 6,
    "goal_to_go": 0,
    "score_differential": 3,
    "is_home": 1,
    "passing_epa_diff": 0.12,
    "rushing_epa_diff": -0.05,
}])

rf = RandomForestModel()
print("RF win prob:", rf.predict_proba(sample))

nb = NaiveBayesModel()
print("NB win prob:", nb.predict_proba(sample))

lr = LogisticRegressionModel()
print("LR win prob:", lr.predict_proba(sample))