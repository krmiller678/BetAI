"""
example_agent_spread.py
Run home cover (ATS) probability predictions for a given home/away matchup
using the trained Logistic Regression, Naive Bayes, and Random Forest spread models.
Stats are pulled live via nflreadpy (no CSV required).

Note on sign convention: spread_line is from the home team's perspective.
Negative = home favored, positive = home underdog.
"""

import argparse
from typing import Optional
import pandas as pd
import nflreadpy as nfl
from models import LRSpread, NBSpread, RFSpread

# ============================================================
# Feature Builder
# ============================================================

# Normalize common team abbreviation variants to the codes used by nflreadpy datasets
TEAM_ALIASES = {
    # Los Angeles teams
    "LAR": "LA",  # Rams
    "STL": "LA",  # legacy Rams
    # Chargers
    "SD": "LAC",
    "SDG": "LAC",
    "SDC": "LAC",
    # Jacksonville
    "JAC": "JAX",
    "JAGS": "JAX",
    # Washington
    "WSH": "WAS",
    "WFT": "WAS",
    # Arizona
    "ARZ": "ARI",
    # Tampa Bay
    "TBB": "TB",
    # San Francisco
    "SFO": "SF",
    # Kansas City
    "KCC": "KC",
    # New Orleans
    "NOR": "NO",
    # Green Bay
    "GBP": "GB",
    # New England
    "NWE": "NE",
    # Las Vegas
    "LVR": "LV",
    "OAK": "LV",
}


def normalize_team(code: str) -> str:
    c = str(code).upper().strip()
    return TEAM_ALIASES.get(c, c)


def _choose_stats_week(
    stats: pd.DataFrame,
    season: int,
    home_team: str,
    away_team: str,
    target_week: int,
    use_prev_week: bool,
) -> Optional[int]:
    """Pick the latest common stats week available for both teams.
    If use_prev_week=True, prefer weeks <= target_week-1; otherwise <= target_week.
    Returns None if no common week exists.
    """
    s = stats[stats["season"] == season]
    hw = set(s[s["team"] == home_team]["week"].unique().tolist())
    aw = set(s[s["team"] == away_team]["week"].unique().tolist())
    common = sorted(hw.intersection(aw))
    if not common:
        return None
    cutoff = target_week - 1 if use_prev_week else target_week
    eligible = [w for w in common if w <= max(1, cutoff)]
    if eligible:
        return max(eligible)
    # fallback: use the latest common week available
    return common[-1]


def build_matchup_features(
    home_team: str,
    away_team: str,
    week: int,
    season: int,
    spread_line: float,
    use_prev_week: bool = True,
) -> pd.DataFrame:
    """
    Construct a single-row dataframe of home-minus-away pregame stats
    pulled live from NFL API using nflreadpy.
    Includes 'week' to match the training feature space.
    """

    # Normalize team abbreviations
    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    # Load up-to-date team stats for the season
    stats = nfl.load_team_stats(seasons=[season]).to_pandas()

    # Choose a resilient stats week available for BOTH teams
    stat_week = _choose_stats_week(
        stats, season, home_team, away_team, week, use_prev_week
    )
    if stat_week is None:
        raise ValueError(
            f"No common stats week found for {home_team} vs {away_team} in season {season}."
        )

    # Filter rows for home and away teams for the chosen stats week
    home = stats[(stats["team"] == home_team) & (stats["week"] == stat_week)]
    away = stats[(stats["team"] == away_team) & (stats["week"] == stat_week)]

    if home.empty or away.empty:
        raise ValueError(
            f"Could not find stats for {home_team} vs {away_team} (Using stats week {stat_week}, Target week {week}, Season {season})"
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
                "passing_epa_diff": safe_diff("passing_epa", "passing_epa"),
                "rushing_epa_diff": safe_diff("rushing_epa", "rushing_epa"),
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


def load_week_slate(season: int, week: int) -> pd.DataFrame:
    sched = nfl.load_schedules(seasons=[season]).to_pandas()
    slate = sched[(sched["season"] == season) & (sched["week"] == week)].copy()
    # Keep only games with a spread_line available
    slate = slate.dropna(subset=["spread_line"]).reset_index(drop=True)
    return slate[["home_team", "away_team", "spread_line", "game_id"]]


# ============================================================
# Betting Utilities
# ============================================================


def american_break_even_prob(odds: float) -> float:
    """Break-even win probability for given American odds.
    Example: -110 -> 52.38%, +120 -> 45.45%.
    """
    if odds < 0:
        x = abs(odds)
        return x / (x + 100)
    else:
        return 100 / (odds + 100)


def expected_value_per_dollar(prob_win: float, odds: float) -> float:
    """Expected profit per $1 stake for an event with prob_win at given American odds.
    Pushes are treated as 0 EV and ignored.
    For -110: profit if win per $1 is 100/110 ≈ 0.9091; loss if lose is -1.
    """
    if odds < 0:
        x = abs(odds)
        payout_per_dollar = 100 / x
    else:
        payout_per_dollar = odds / 100
    return prob_win * payout_per_dollar - (1 - prob_win) * 1.0


def prob_to_american_odds(p: float) -> int:
    """Convert win probability to fair American odds (no vig)."""
    p = max(1e-6, min(1 - 1e-6, p))
    if p >= 0.5:
        # favorite -> negative odds
        return int(round(-100 * (p / (1 - p))))
    else:
        # underdog -> positive odds
        return int(round(100 * ((1 - p) / p)))


def print_card(
    home_team: str,
    away_team: str,
    line: float,
    p_home_cover: float,
    home_odds: int,
    away_odds: int,
):
    p_away_cover = 1.0 - p_home_cover
    be_home = american_break_even_prob(home_odds)
    be_away = american_break_even_prob(away_odds)
    ev_home = expected_value_per_dollar(p_home_cover, home_odds)
    ev_away = expected_value_per_dollar(p_away_cover, away_odds)
    fair_home = prob_to_american_odds(p_home_cover)
    fair_away = prob_to_american_odds(p_away_cover)

    rec_side = "HOME" if ev_home >= ev_away else "AWAY"
    rec_ev = max(ev_home, ev_away)
    rec_odds = home_odds if rec_side == "HOME" else away_odds
    rec_line = line if rec_side == "HOME" else -line

    # Card-like output
    print("-" * 72)
    print(f"{away_team} @ {home_team} | Home line {line:+.1f}")
    print(
        f"Home: {home_team} {line:+.1f} ({home_odds:+d})  |  Away: {away_team} {-line:+.1f} ({away_odds:+d})"
    )
    print(
        f"Model P(cover): Home {p_home_cover:.3f} | Away {p_away_cover:.3f}  |  Fair odds: Home {fair_home:+d}, Away {fair_away:+d}"
    )
    print(
        f"Break-even: Home {be_home:.3f} | Away {be_away:.3f}  |  EV per $100: Home {ev_home*100:+.2f}, Away {ev_away*100:+.2f}"
    )
    final = (
        f"BET {rec_side} {home_team if rec_side=='HOME' else away_team} {rec_line:+.1f} ({rec_odds:+d})"
        if rec_ev > 0
        else "NO BET"
    )
    print(f"Recommendation: {final}")
    print("-" * 72)


# ============================================================
# CLI + Example Run
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ATS home-cover probability and betting advice"
    )
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--week", type=int, default=6)
    parser.add_argument("--home_team", type=str, default="CIN")
    parser.add_argument("--away_team", type=str, default="PIT")
    parser.add_argument(
        "--spread_line",
        type=float,
        default=-3.0,
        help="Home perspective: negative=favored",
    )
    parser.add_argument(
        "--home_odds",
        type=int,
        default=-110,
        help="American odds for betting HOME ATS",
    )
    parser.add_argument(
        "--away_odds",
        type=int,
        default=-110,
        help="American odds for betting AWAY ATS",
    )
    parser.add_argument(
        "--slate",
        action="store_true",
        help="Evaluate the entire week slate instead of a single game",
    )
    parser.add_argument(
        "--no_prev_week",
        action="store_true",
        help="Use same-week stats instead of prior-week",
    )
    args = parser.parse_args()

    season = args.season
    week = args.week
    home_team = normalize_team(args.home_team)
    away_team = normalize_team(args.away_team)
    spread_line = float(args.spread_line)
    home_odds = int(args.home_odds)
    away_odds = int(args.away_odds)
    use_prev_week = not args.no_prev_week

    # Load models once
    rf = RFSpread()
    nb = NBSpread()
    lr = LRSpread()

    # No CSV collection; console output only

    if args.slate:
        slate = load_week_slate(season, week)
        print(
            f"\n=== ATS Recommendations for Season {season}, Week {week} ==="
        )
        total_games = 0
        pos_bets = 0
        sum_ev_per_100 = 0.0
        for _, g in slate.iterrows():
            h = str(g["home_team"]).upper()
            a = str(g["away_team"]).upper()
            line = float(g["spread_line"])  # home perspective
            gid = g.get("game_id", "")

            feats = build_matchup_features(
                h, a, week, season, line, use_prev_week=use_prev_week
            )
            rf_prob = rf.predict_proba(feats)[0]
            nb_prob = nb.predict_proba(feats)[0]
            lr_prob = lr.predict_proba(feats)[0]
            p = (rf_prob + nb_prob + lr_prob) / 3

            ev_home = expected_value_per_dollar(p, home_odds)
            ev_away = expected_value_per_dollar(1 - p, away_odds)
            rec_side = "HOME" if ev_home >= ev_away else "AWAY"
            rec_ev = max(ev_home, ev_away)
            rec_odds = home_odds if rec_side == "HOME" else away_odds
            rec_line = line if rec_side == "HOME" else -line

            # Card-like print per game
            print_card(h, a, line, p, home_odds, away_odds)
            total_games += 1
            if rec_ev > 0:
                pos_bets += 1
                # Track EV per $100 for the recommended side only
                sum_ev_per_100 += (
                    (ev_home * 100) if rec_side == "HOME" else (ev_away * 100)
                )

        # Slate summary (console only)
        print(
            f"\nTotal recommended bets: {pos_bets} / {total_games} | Sum EV per $100 across bets: {sum_ev_per_100:+.2f}"
        )

    else:
        # Single-game path
        feats = build_matchup_features(
            home_team,
            away_team,
            week,
            season,
            spread_line,
            use_prev_week=use_prev_week,
        )
        rf_prob = rf.predict_proba(feats)[0]
        nb_prob = nb.predict_proba(feats)[0]
        lr_prob = lr.predict_proba(feats)[0]
        p = (rf_prob + nb_prob + lr_prob) / 3

        print_card(home_team, away_team, spread_line, p, home_odds, away_odds)
