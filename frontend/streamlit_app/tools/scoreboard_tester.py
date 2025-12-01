#!/usr/bin/env python3
# frontend/streamlit_app/demo/scoreboard_tester.py
# ------------------------------------------------------------
# Purpose:
#   End-to-end sanity test for the ESPN integration (pbp_api).
#   - Verifies we can fetch live/dated scoreboard data.
#   - Normalizes games and validates key fields.
#   - Demonstrates cache behavior by timing back-to-back calls.
#   - Optionally fetches summary and play-by-play for a sample game.
#
# Usage:
#   # Default (current slate)
#   python3 frontend/streamlit_app/demo/scoreboard_tester.py
#
#   # Specific date (YYYYMMDD), e.g., Oct 12, 2025
#   python3 frontend/streamlit_app/demo/scoreboard_tester.py --dates 20251012
#
#   # Specific week (regular season)
#   python3 frontend/streamlit_app/demo/scoreboard_tester.py --week 6 --seasontype 2
#
#   # Force a specific ESPN event id for summary/pbp tests
#   python3 frontend/streamlit_app/demo/scoreboard_tester.py --event 401671234
#
# Notes:
#   - Run from repo root or anywhere; this script bootstraps sys.path to the repo root.
#   - Exits with code 0 on success; non-zero if validations fail.
# ------------------------------------------------------------

# --- repo path bootstrap (lets this script run from anywhere) ---
# Add the repository root to sys.path so "backend.core.betai..." can be imported.
import sys, pathlib
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]  # BetAI/ (repo root)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# ---------------------------------------------------------------

# Import argparse for CLI flags
import argparse

# Import time for timing cache hits
import time

# Import typing helpers for clear type hints
from typing import Any, Dict, List, Optional, Tuple

# Import pprint for nicer debug printing
from pprint import pprint

# Import our ESPN integration functions
from backend.core.betai.integrations.pbp_api import (
    fetch_scoreboard,
    normalize_scoreboard,
    fetch_summary,
    fetch_playbyplay,
    normalize_summary,
    normalize_playbyplay,
    compute_seconds_left,
)

import json


# -----------------------------------------------------------------------------
# helper: truncate a string nicely
# -----------------------------------------------------------------------------
def _clip(s: Any, n: int = 120) -> str:
    # Convert value to string
    s = "" if s is None else str(s)
    # Return clipped string with ellipsis if too long
    return s if len(s) <= n else s[: n - 1] + "…"

# -----------------------------------------------------------------------------
# helper: safely get a nested field
# -----------------------------------------------------------------------------
def _g(obj: Dict, *path, default=None):
    # Start from given object
    cur = obj
    # Walk each key in path
    for k in path:
        # If current is dict, try normal get
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        # If current is list and key is int, try index
        elif isinstance(cur, list) and isinstance(k, int):
            if 0 <= k < len(cur):
                cur = cur[k]
            else:
                return default
        else:
            return default
        # If a missing value is reached early, return default
        if cur is None:
            return default
    # Return located value
    return cur

# -----------------------------------------------------------------------------
# /** @brief Create a human-readable overview of ESPN /summary payload.
#  *
#  *  @param summary_json  Raw JSON dict returned by ESPN /summary.
#  *  @param max_players_per_cat  Limit rows per player table for readability.
#  *  @param max_value_len  Clip long text fields to keep output compact.
#  *  @return str  A formatted multi-line report.
#  *
#  *  @details
#  *   - Prints game meta (status, venue), teams, and scores.
#  *   - Prints team boxscore "statistics" pairs (e.g., firstDowns, totalYards).
#  *   - Prints each player-category table with its column headers and a sample
#  *     of rows (Passing, Rushing, Receiving, Defense, etc.).
#  *   - Prints leaders, broadcasts, and any other high-level keys if present.
#  *   - Defensive against missing fields so you can run it on any game.
#  */
# -----------------------------------------------------------------------------
def describe_summary(summary_json: Dict[str, Any],
                     max_players_per_cat: int = 8,
                     max_value_len: int = 80) -> str:
    # Initialize a list of lines to join later
    out: List[str] = []

    # Header line
    out.append("—— ESPN Summary Overview ——")

    # ----- Basic matchup / status ------------------------------------------------
    # Read competitions[0] which holds game-level info
    comp = _g(summary_json, "header", "competitions", 0, default={})
    # Read teams (competitors)
    comps = _g(comp, "competitors", default=[]) or [] # type: ignore
    # Build a quick map side->team
    sides = {"home": None, "away": None}
    for c in comps:
        side = (c.get("homeAway") or "").lower()
        if side in sides:
            sides[side] = c

    # Extract names and scores for the header line
    home_name = _clip(_g(sides["home"] or {}, "team", "displayName", default="Home"))
    away_name = _clip(_g(sides["away"] or {}, "team", "displayName", default="Away"))
    home_score = _clip(_g(sides["home"] or {}, "score", default="0"))
    away_score = _clip(_g(sides["away"] or {}, "score", default="0"))

    # Read status block
    status = _g(summary_json, "header", "competitions", 0, "status", default={})
    state = _clip(_g(status, "type", "state", default="unknown")) # type: ignore
    period = _g(status, "period", default=None) # type: ignore
    dclock = _clip(_g(status, "displayClock", default="")) # type: ignore

    # Add header with matchup and status
    out.append(f"Matchup: {away_name} {away_score} @ {home_name} {home_score}")
    out.append(f"Status : {state.upper()} • Q{period if period else '?'} • {dclock or '—'}")

    # Venue info (if present)
    venue_name = _g(comp, "venue", "fullName", default=None) # type: ignore
    if venue_name:
        out.append(f"Venue  : {venue_name}")

    out.append("")

    # ----- Boxscore: Team statistics --------------------------------------------
    # Get the boxscore node
    boxscore = _g(summary_json, "boxscore", default={})
    teams = _g(boxscore, "teams", default=[]) or [] # type: ignore

    if teams:
        out.append("— Team Boxscore Statistics —")
        for t in teams:
            # Read side
            side = (t.get("homeAway") or "").capitalize()
            # Read team display name
            team_label = _g(t, "team", "displayName", default=side)
            # Print team header
            out.append(f"  [{side}] {team_label}")

            # Print key-value stats (statistics list)
            stats_list = t.get("statistics") or []
            if stats_list:
                for s in stats_list:
                    name = _clip(s.get("name", ""), max_value_len)
                    val = _clip(s.get("displayValue", ""), max_value_len)
                    out.append(f"    • {name}: {val}")
            else:
                out.append("    • (no team-level statistics)")

            out.append("")

    # ----- Boxscore: Player categories (Passing, Rushing, etc.) -----------------
    if teams:
        out.append("— Player Categories —")
        for t in teams:
            # Label each side section
            side = (t.get("homeAway") or "").capitalize()
            team_label = _g(t, "team", "displayName", default=side)
            out.append(f"  [{side}] {team_label}")

            # Read categories list
            cats = t.get("categories") or []
            if not cats:
                out.append("    • (no player categories)")
                out.append("")
                continue

            # Iterate each category table
            for cat in cats:
                cat_name = _clip(cat.get("name", "Category"), max_value_len)
                labels = cat.get("labels") or []
                athletes = cat.get("athletes") or []

                # Print category header and columns
                out.append(f"    > {cat_name}")
                if labels:
                    out.append(f"      Columns: {', '.join(_clip(x, 30) for x in labels)}")
                else:
                    out.append("      Columns: (none)")

                # Show a sample of players/rows
                if athletes:
                    # Compute how many rows to show
                    n = min(len(athletes), max_players_per_cat)
                    for i in range(n):
                        a = athletes[i]
                        # Athlete display name
                        aname = _clip(_g(a, "athlete", "displayName", default="(Player)"), 40)
                        # Stats row aligned with labels
                        stats = [ _clip(v, 20) for v in (a.get("stats") or []) ]
                        out.append(f"      - {aname}: {', '.join(stats)}")
                    # Note if truncated
                    if len(athletes) > n:
                        out.append(f"      - … (+{len(athletes)-n} more)")
                else:
                    out.append("      - (no rows)")

                out.append("")

    # ----- Leaders (if present) -------------------------------------------------
    leaders = _g(summary_json, "leaders", default=[]) or _g(summary_json, "header", "competitions", 0, "leaders", default=[]) or []
    if leaders:
        out.append("— Leaders —")
        for ld in leaders:
            cat = _clip(ld.get("name") or ld.get("category", ""), max_value_len)
            entries = ld.get("leaders") or []
            for e in entries:
                val = _clip(e.get("displayValue", ""), max_value_len)
                who = _clip(_g(e, "athlete", "displayName", default="(Athlete)"), 40)
                team = _clip(_g(e, "team", "displayName", default=""), 30)
                out.append(f"  • {cat}: {who} ({team}) — {val}")
        out.append("")

    # ----- Broadcasts (if present) ----------------------------------------------
    broadcasts = _g(summary_json, "header", "competitions", 0, "broadcasts", default=[]) or []
    if broadcasts:
        out.append("— Broadcasts —")
        for b in broadcasts:
            names = ", ".join(b.get("names") or [])
            out.append(f"  • {names or '(unknown)'}")
        out.append("")

    # ----- Officials / gameInfo (if present) ------------------------------------
    game_info = _g(summary_json, "gameInfo", default={})
    if game_info:
        out.append("— Game Info —")
        # Print a shallow key preview
        keys = ", ".join(sorted(game_info.keys()))
        out.append(f"  keys: {keys}")
        out.append("")

    # ----- Any other high-level keys not covered (preview only) -----------------
    # List top-level keys and note which we printed in detail
    printed_keys = {"header", "boxscore", "leaders", "gameInfo"}
    remaining = [k for k in (summary_json or {}).keys() if k not in printed_keys]
    if remaining:
        out.append("— Other top-level sections (preview) —")
        for k in sorted(remaining):
            # Print key name and a shallow shape hint
            val = summary_json.get(k)
            shape = type(val).__name__
            out.append(f"  • {k}: {shape}")
        out.append("")

    # Join lines and return
    return "\n".join(out)

# -----------------------------------------------------------------------------
# /** @brief Print the summary overview directly (wrapper around describe_summary).
#  *
#  *  @param summary_json  Raw JSON dict returned by ESPN /summary.
#  */
# -----------------------------------------------------------------------------
def print_summary_overview(summary_json: Dict[str, Any]) -> None:
    # Build overview text
    txt = describe_summary(summary_json)
    # Print a blank line before
    print("")
    # Print the overview
    print(txt)
    # Print a blank line after
    print("")



def _ok(msg: str) -> None:
    """Print a green-ish PASS line."""
    print(f"✅ {msg}")


def _warn(msg: str) -> None:
    """Print a yellow-ish WARN line."""
    print(f"⚠️  {msg}")


def _fail(msg: str) -> None:
    """Print a red-ish FAIL line."""
    print(f"❌ {msg}")


def _validate_game_schema(game: Dict[str, Any]) -> List[str]:
    """
    /**
     * @brief Validate a single normalized game dict for required keys/types.
     *
     * @param game  One normalized game (from normalize_scoreboard()).
     *
     * @return List of error strings; empty list means validation passed.
     */
    """
    # Initialize an empty list to accumulate error messages
    errors: List[str] = []

    # Validate top-level required keys
    required_top = ["espn_event_id", "commence_time", "state", "home", "away"]
    for k in required_top:
        if k not in game:
            errors.append(f"missing key: {k}")

    # Validate home/away blocks exist and are dicts
    for side in ("home", "away"):
        if side in game and not isinstance(game[side], dict):
            errors.append(f"{side} should be dict")

        # Validate expected keys inside team blocks
        expected_team_keys = {"name", "abbr", "logo", "score"}
        if isinstance(game.get(side), dict):
            missing = expected_team_keys - set(game[side].keys())
            if missing:
                errors.append(f"{side} missing subkeys: {sorted(missing)}")

            # Validate score is int or None
            score_val = game[side].get("score")
            if score_val is not None and not isinstance(score_val, int):
                errors.append(f"{side}.score should be int or None, got {type(score_val).__name__}")

    # Validate period is int or None
    period = game.get("period")
    if period is not None and not isinstance(period, int):
        errors.append(f"period should be int or None, got {type(period).__name__}")

    # Validate display_clock is str or None
    clock = game.get("display_clock")
    if clock is not None and not isinstance(clock, str):
        errors.append(f"display_clock should be str or None, got {type(clock).__name__}")

    # Validate situation block keys (if present)
    sit = game.get("situation")
    if sit is not None and not isinstance(sit, dict):
        errors.append("situation should be dict or None")

    return errors


def _print_game_brief(game: Dict[str, Any]) -> None:
    """
    /**
     * @brief Print a concise, human-friendly one-liner for a game.
     *
     * @param game  One normalized game.
     */
    """
    # Read basic identifiers
    eid = game.get("espn_event_id")
    state = (game.get("state") or "").upper()
    period = game.get("period") or "-"
    clock = game.get("display_clock") or "--:--"

    # Read team blocks
    home = game["home"]
    away = game["away"]
    hs = home["score"] if home["score"] is not None else 0
    as_ = away["score"] if away["score"] is not None else 0

    # Compute seconds_left when possible
    sec_left = compute_seconds_left(game.get("period"), game.get("display_clock"))

    # Build a friendly line
    line = f"[{eid}] {away['name']} {as_} @ {home['name']} {hs}  |  {state} • Q{period} • {clock}"
    if sec_left is not None:
        line += f" • {sec_left}s left"

    # Print the summary line
    print("   ", line)


def _pick_event_id(games: List[Dict[str, Any]]) -> Optional[str]:
    """
    /**
     * @brief Pick a sample ESPN event id from normalized games.
     *
     * @param games  List of normalized game dicts.
     *
     * @return One event id string or None if list is empty.
     */
    """
    # Return the first event id if available
    if not games:
        return None
    return games[0].get("espn_event_id")

# ------------------------------------------------------------
# Summary pretty-printers (schema-agnostic, safe fallbacks)
# ------------------------------------------------------------

def _print_summary_brief(event_id: str, raw_summary: dict) -> None:
    """
    // Pretty Summary (resilient for POST games too)
    //  - header: teams + score + status description
    //  - venue (if present)
    //  - basic situation if available (possession, down&distance)
    //  - concise “final lines” when state is POST
    """
    # Pull the root json safely
    root = raw_summary.get("gamepackageJSON") if isinstance(raw_summary, dict) and "gamepackageJSON" in raw_summary else raw_summary

    # Bail if not a dict
    if not isinstance(root, dict):
        print(f"\n—— Summary (event={event_id}) ——")
        print("  • Unexpected JSON shape.")
        return

    # Print section header
    print(f"\n—— Summary (event={event_id}) ——")

    # Get header block
    header = root.get("header") or {}

    # Get first competition safely
    competitions = header.get("competitions") or [{}]
    comp = competitions[0] if competitions else {}

    # Extract competitors (home/away)
    teams = comp.get("competitors") or []

    # Helper to pick team by side
    def pick(side: str):
        for c in teams:
            if c.get("homeAway") == side:
                team = c.get("team") or {}
                name = team.get("displayName") or side.upper()
                abbr = team.get("abbreviation") or side[:3].upper()
                score = c.get("score")
                record = None
                recs = c.get("records") or []
                if recs and isinstance(recs, list) and recs[0].get("summary"):
                    record = recs[0]["summary"]
                winner = c.get("winner")
                return name, abbr, score, record, winner
        return side.upper(), side[:3].upper(), None, None, None

    # Collect team lines
    away_nm, away_abbr, away_sc, away_rec, away_win = pick("away")
    home_nm, home_abbr, home_sc, home_rec, home_win = pick("home")

    # Extract status bits
    status = comp.get("status") or {}
    status_type = status.get("type") or {}
    state = (status_type.get("state") or "").upper()         # PRE | IN | POST
    desc  = status_type.get("description") or state          # “Final”, “In Progress”, etc.
    period = status.get("period")
    clock  = status.get("displayClock") or "0:00"

    # Print main header line
    print(f"  {away_nm} {away_sc} @ {home_nm} {home_sc}")
    # Print human description of status
    if period:
        print(f"  Status: {desc} • Q{period} • {clock}")
    else:
        print(f"  Status: {desc} • {clock}")

    # Venue & weather if present
    gi = root.get("gameInfo") or {}
    venue = (gi.get("venue") or {}).get("fullName")
    weather = (gi.get("weather") or {}).get("displayValue")
    venue_line_bits = []
    if venue: venue_line_bits.append(f"Venue: {venue}")
    if weather: venue_line_bits.append(f"Weather: {weather}")
    if venue_line_bits:
        print("  " + " | ".join(venue_line_bits))

    # If post-game, show quick result line with records
    if state == "POST":
        away_flag = "W" if away_win else "L" if away_win is not None else "-"
        home_flag = "W" if home_win else "L" if home_win is not None else "-"
        away_rec_str = f" ({away_rec})" if away_rec else ""
        home_rec_str = f" ({home_rec})" if home_rec else ""
        print(f"  Final: {away_abbr} {away_sc}{away_rec_str} {away_flag}  |  {home_abbr} {home_sc}{home_rec_str} {home_flag}")

    # Situation (possession / down & distance) if ESPN provides it
    sit = comp.get("situation") or {}
    poss_id = sit.get("possession")
    down = sit.get("down")
    dist = sit.get("distance")
    yardline = sit.get("yardLine")
    is_red = sit.get("isRedZone")

    # Map possession id → abbr
    poss_abbr = None
    if poss_id is not None:
        for c in teams:
            tid = ((c.get("team") or {}).get("id"))
            if str(tid) == str(poss_id):
                poss_abbr = ((c.get("team") or {}).get("abbreviation"))
                break

    # Build situation line
    bits = []
    if poss_abbr: bits.append(f"Poss: {poss_abbr}")
    if down is not None and dist is not None: bits.append(f"{down}&{dist}")
    if yardline is not None: bits.append(f"YdLn: {yardline}")
    if is_red: bits.append("RedZone")
    if bits:
        print("  " + " • ".join(bits))

    # Last scoring plays (from drives) for more interesting recap
    drives = root.get("drives") or {}
    prev = drives.get("previous") or []
    cur = drives.get("current") or {}

    # Helper to extract scoring plays out of a drive
    def last_scoring_from_drive(drive: dict, max_scoring: int = 3) -> list[str]:
        out = []
        plays = drive.get("plays") or []
        for p in plays:
            if p.get("scoringPlay"):
                clk = (p.get("clock") or {}).get("displayValue") or ""
                txt = (p.get("text") or p.get("description") or "").strip()
                out.append(f"{clk}  {txt}")
        return out[-max_scoring:]

    # Gather a few scoring bullets (prefer current, then previous)
    scoring_bullets = []
    scoring_bullets += last_scoring_from_drive(cur, max_scoring=3)
    for d in reversed(prev[-3:]):
        if len(scoring_bullets) >= 3:
            break
        scoring_bullets[:0] = last_scoring_from_drive(d, max_scoring=3)  # prepend older

    if scoring_bullets:
        print("  Recent scoring:")
        for b in scoring_bullets[-3:]:
            print("    - " + b)

    # Finally: fall back to a couple of last generic plays when nothing scored recently
    if not scoring_bullets:
        recent = []
        plays_cur = cur.get("plays") or []
        if plays_cur:
            for p in plays_cur[-3:]:
                clk = (p.get("clock") or {}).get("displayValue") or ""
                txt = (p.get("text") or p.get("description") or "").strip()
                if txt:
                    recent.append(f"{clk}  {txt}")
        elif prev:
            last_drive = prev[-1]
            plays = last_drive.get("plays") or []
            if plays:
                for p in plays[-3:]:
                    clk = (p.get("clock") or {}).get("displayValue") or ""
                    txt = (p.get("text") or p.get("description") or "").strip()
                    if txt:
                        recent.append(f"{clk}  {txt}")
        if recent:
            print("  Recent plays:")
            for r in recent:
                print("    - " + r)

# ------------------------------------------------------------
# Play-by-Play pretty-printer (last plays, possession, spot)
# ------------------------------------------------------------

def _print_pbp_brief(event_id: str, raw_pbp: dict, raw_summary_fallback: dict | None = None,
                     max_scoring: int = 5, max_recent: int = 5) -> None:
    """
    // PBP with smart fallback and emphasis on scoring:
    //  - print last scoring plays (TD/FG/2PT/SAF) if present
    //  - then a few recent non-scoring plays
    //  - if PBP is missing, fall back to Summary.drives
    """
    # Print section header
    print(f"\n—— Play-by-Play (event={event_id}) ——")

    # Prefer PBP root if present
    root = raw_pbp.get("gamepackageJSON") if isinstance(raw_pbp, dict) and "gamepackageJSON" in raw_pbp else raw_pbp
    drives = (root or {}).get("drives") if isinstance(root, dict) else None

    # Fall back to summary drives if needed
    if not drives and raw_summary_fallback:
        sr = raw_summary_fallback.get("gamepackageJSON") if isinstance(raw_summary_fallback, dict) and "gamepackageJSON" in raw_summary_fallback else raw_summary_fallback
        drives = (sr or {}).get("drives") if isinstance(sr, dict) else None
        if drives:
            print("  • Using Summary drives (fallback).")

    # If still nothing, bail
    if not drives:
        print("  • No drives available.")
        return

    # Pull current and previous drives
    cur = drives.get("current") or {}
    prev = drives.get("previous") or []

    # Small helper to collect scoring / recent plays from any list of plays
    def collect_scoring(plays: list, limit: int) -> list[str]:
        out = []
        for p in plays:
            if p.get("scoringPlay"):
                clk = (p.get("clock") or {}).get("displayValue") or ""
                txt = (p.get("text") or p.get("description") or "").strip()
                if txt:
                    out.append(f"{clk}  {txt}")
        return out[-limit:]

    def collect_recent(plays: list, limit: int) -> list[str]:
        out = []
        for p in plays[-limit:]:
            clk = (p.get("clock") or {}).get("displayValue") or ""
            txt = (p.get("text") or p.get("description") or "").strip()
            if txt:
                out.append(f"{clk}  {txt}")
        return out

    # Build lists from current drive first
    plays_cur = cur.get("plays") or []
    scoring = collect_scoring(plays_cur, max_scoring)
    recent = collect_recent(plays_cur, max_recent)

    # If little/no scoring, pull from last previous drives
    if len(scoring) < max_scoring and prev:
        for d in reversed(prev[-3:]):
            plays = d.get("plays") or []
            if not plays:
                continue
            extra = collect_scoring(plays, max_scoring - len(scoring))
            scoring.extend(extra)
            if len(scoring) >= max_scoring:
                break

    # Print scoring first if any
    if scoring:
        print("  Scoring plays:")
        for s in scoring[-max_scoring:]:
            print("    - " + s)

    # If no recent yet, fetch from last previous drive
    if not recent and prev:
        last = prev[-1]
        recent = collect_recent(last.get("plays") or [], max_recent)

    # Print recent (non-filtered) small tail
    if recent:
        print("  Recent plays:")
        for r in recent[-max_recent:]:
            print("    - " + r)

# ------------------------------------------------------------
# Expanded /summary explorer for "Other top-level sections"
# (skips Leaders and Broadcasts as requested)
# ------------------------------------------------------------
def _safe_clip(v, n=120):
    # Convert to string for printing
    s = "" if v is None else str(v)
    # Truncate long strings for readability
    return s if len(s) <= n else s[: n - 1] + "…"

def print_other_sections(summary_json: Dict[str, Any], limit: int = 6) -> None:
    # Prefer ESPN's "gamepackageJSON" root if present
    root = summary_json.get("gamepackageJSON") if isinstance(summary_json, dict) and "gamepackageJSON" in summary_json else summary_json
    if not isinstance(root, dict):
        print("\n— Other sections: unexpected JSON shape —")
        return

    # Small finder
    def g(*path, default=None):
        cur = root
        for k in path:
            if isinstance(cur, dict):
                cur = cur.get(k, default)
            elif isinstance(cur, list) and isinstance(k, int) and 0 <= k < len(cur):
                cur = cur[k]
            else:
                return default
            if cur is None:
                return default
        return cur

    # Little utility to show list length and sample
    def _show_list(name: str, items: list, render_item) -> None:
        print(f"\n— {name} —  ({len(items)} item(s))")
        n = min(len(items), limit)
        if not items:
            print("  (empty)")
            return
        for i in range(n):
            try:
                render_item(items[i], idx=i)
            except Exception as e:
                print(f"  • [{i}] (render error: {e})")
        if len(items) > n:
            print(f"  … (+{len(items)-n} more)")

    # ---------- againstTheSpread (list) ----------
    ats = g("againstTheSpread", default=[])
    if isinstance(ats, list):
        def _render_ats(x, idx=0):
            # Provider/line/result style varies by game; show shallow fields safely
            prov = _safe_clip(x.get("provider", ""), 40)
            line = _safe_clip(x.get("details", x.get("displayValue", "")), 60)
            res  = _safe_clip(x.get("result", x.get("winner", "")), 24)
            print(f"  • [{idx}] provider={prov or '-'} | details={line or '-'} | result={res or '-'}")
        _show_list("Against The Spread", ats, _render_ats)

    # ---------- article (dict) ----------
    article = g("article", default={})
    if isinstance(article, dict) and article:
        hed = _safe_clip(article.get("headline") or article.get("title") or "", 100)
        by  = _safe_clip(article.get("byline") or "", 60)
        lnk = _safe_clip(article.get("links", {}).get("web", {}).get("href") or "", 120)
        print("\n— Article —")
        print(f"  headline: {hed or '(none)'}")
        if by:  print(f"  byline  : {by}")
        if lnk: print(f"  url     : {lnk}")

    # ---------- drives (dict) ----------
    drives = g("drives", default={})
    if isinstance(drives, dict) and drives:
        prev = drives.get("previous") or []
        cur  = drives.get("current") or {}
        print("\n— Drives —")
        print(f"  previous: {len(prev)}  | current: {'present' if cur else 'none'}")

        # Show info for the last previous drive
        if prev:
            d = prev[-1]
            desc = d.get("description") or d.get("displayResult") or "-"
            yd   = d.get("yards")
            ply  = d.get("plays")
            dur  = (d.get("timeElapsed") or {}).get("displayValue", "")

            # ✅ FIX: remove the raw {d.get('plays')} which dumped JSON
            print(f"  last drive: {len(ply)} plays, {yd} yards, {dur} — {desc}")

            # Print every play (nicely formatted)
            if ply:
                print("  plays:")
                for p in ply:
                    print(describe_play(p))
            else:
                print("  (no plays)")

        # Show current drive if exists
        plays_cur = (cur.get("plays") or []) if cur else []
        if plays_cur:
            print("\n  current drive:")
            for p in plays_cur:
                print(describe_play(p))

    # ---------- format (dict) ----------
    fmt = g("format", default={})
    status = g("header", "competitions", 0, "status", default={})
    comp = fmt.get("competition", {}) if isinstance(fmt, dict) else {}
    periods = (comp.get("regulation") or {}).get("periods")
    dispclk = (comp.get("clock") or {}).get("displayValue")
    period  = comp.get("period")

    if not periods:
        periods = (status.get("type") or {}).get("completedPeriods") or (status.get("period")) # type: ignore
    if not dispclk:
        dispclk = status.get("displayClock") # type: ignore
    if not period:
        period = status.get("period") # type: ignore

    print("\n— Format —")
    print(f"  regulation periods: {periods if periods is not None else '-'}")
    print(f"  clock (display)   : {dispclk or '-'}")
    print(f"  period (current)  : {period if period is not None else '-'}")

    # ---------- injuries (list) ----------
    injuries = g("injuries", default=[])
    if isinstance(injuries, list):
        print(f"\n— Injuries —  ({len(injuries)} item(s))")
        if not injuries:
            print("  (empty)")
        else:
            for i, x in enumerate(injuries[:limit]):
                team = _safe_clip((x.get("team") or {}).get("displayName") or "", 40)
                # ESPN sometimes stores a list of athletes per team injury node
                athlete = ""
                if isinstance(x.get("athletes"), list) and x["athletes"]:
                    athlete = _safe_clip((x["athletes"][0].get("athlete") or {}).get("displayName") or "", 40)
                else:
                    athlete = _safe_clip((x.get("athlete") or {}).get("displayName") or "", 40)
                stat = _safe_clip(x.get("status") or (x.get("type") or {}).get("text") or x.get("shortStatus") or "", 60)
                note = _safe_clip(x.get("description") or "", 100)
                line = f"  • [{i}] {team}: {athlete or '(player n/a)'} — {stat or 'status unknown'}"
                print(line if not note else line + f" | {note}")
            if len(injuries) > limit:
                print(f"  … (+{len(injuries)-limit} more)")

    # ---------- meta (dict) ----------
    meta = g("meta", default={})
    if isinstance(meta, dict) and meta:
        print("\n— Meta —")
        keys = ", ".join(sorted(meta.keys()))
        print(f"  keys: {keys}")

    # ---------- news (dict) ----------
    news = g("news", default={})
    if isinstance(news, dict) and news:
        arts = news.get("articles") or []
        print(f"\n— News —  ({len(arts)} item(s))")
        if not arts:
            print("  (empty)")
        else:
            for i, a in enumerate(arts[:limit]):
                hed = _safe_clip(a.get("headline") or a.get("title") or "", 100)
                src = _safe_clip(a.get("source", ""), 30)
                url = ""
                ln  = a.get("links") or {}
                if isinstance(ln, dict):
                    web = ln.get("web") or {}
                    url = web.get("href") or ""
                url = _safe_clip(url, 120)
                print(f"  • [{i}] {hed}  ({src})" + (f"\n       {url}" if url else ""))
            if len(arts) > limit:
                print(f"  … (+{len(arts)-limit} more)")

    # ---------- odds (list) ----------
    odds = g("odds", default=[])
    if isinstance(odds, list):
        def _render_odds(x, idx=0):
            prov = _safe_clip(x.get("provider", {}).get("name") or "", 40)
            spread = x.get("spread", x.get("details"))
            ou     = x.get("overUnder", x.get("total"))
            mh = x.get("moneyline", {}).get("home") if isinstance(x.get("moneyline"), dict) else x.get("homeMoneyLine")
            ma = x.get("moneyline", {}).get("away") if isinstance(x.get("moneyline"), dict) else x.get("awayMoneyLine")
            print(f"  • [{idx}] {prov or '-'} | spread={_safe_clip(spread,40)} | O/U={ou} | ML(home)={mh} ML(away)={ma}")
        _show_list("Odds", odds, _render_odds)

    # ---------- pickcenter (list) ----------
    pickcenter = g("pickcenter", default=[])
    if isinstance(pickcenter, list):
        def _render_pc(x, idx=0):
            prov = _safe_clip(x.get("provider", {}).get("name") or "", 40)
            pol  = _safe_clip(x.get("pickcenterText") or x.get("details") or "", 60)
            print(f"  • [{idx}] {prov or '-'} | {pol or '-'}")
        _show_list("PickCenter", pickcenter, _render_pc)

    # ---------- scoringPlays (list) ----------
    sps = g("scoringPlays", default=[])
    if isinstance(sps, list):
        def _render_sp(x, idx=0):
            clk = (x.get("clock") or {}).get("displayValue") or ""
            txt = x.get("text") or x.get("description") or ""
            h   = x.get("homeScore")
            a   = x.get("awayScore")
            per = x.get("period", {}).get("number")
            print(f"  • [{idx}] Q{per or '?'} {clk:>5}  {txt}  |  {a}-{h}")
        _show_list("Scoring Plays", sps, _render_sp)

    # ---------- standings (dict) ----------
    standings = g("standings", default={})
    if isinstance(standings, dict) and standings:
        print("\n— Standings —")
        # Just preview structure without exploding it
        confs = standings.get("groups") or standings.get("children") or []
        print(f"  sections: {len(confs)} (preview only)")

    # ---------- videos (list) ----------
    vids = g("videos", default=[])
    if isinstance(vids, list):
        def _render_vid(x, idx=0):
            t = _safe_clip(x.get("headline") or x.get("title") or "", 100)
            print(f"  • [{idx}] {t}")
        _show_list("Videos", vids, _render_vid)

    # ---------- wallclockAvailable (bool) ----------
    if "wallclockAvailable" in root:
        print("\n— Wallclock —")
        print(f"  wallclockAvailable: {bool(root.get('wallclockAvailable'))}")

    # ---------- winprobability (list) ----------
    wp = g("winprobability", default=[])
    if isinstance(wp, list):
        print("\n— Win Probability —")
        if not wp:
            print("  (empty)")
        else:
            last = wp[-1] or {}
            home = last.get("homeWinPercentage")
            away = last.get("awayWinPercentage")
            print(f"  points: {len(wp)} | last → home={home} away={away}")
            # Show a few evenly spaced samples across the series for context
            sample_idx = [0, len(wp)//3, (2*len(wp))//3, len(wp)-1]
            seen = set()
            for idx in sample_idx:
                if idx < 0 or idx >= len(wp) or idx in seen: 
                    continue
                seen.add(idx)
                p   = wp[idx] or {}
                per = p.get("period") or (p.get("type") or {}).get("period")
                clk = (p.get("clock") or {}).get("displayValue") if isinstance(p.get("clock"), dict) else p.get("displayClock")
                hw  = p.get("homeWinPercentage")
                aw  = p.get("awayWinPercentage")
                print(f"    - #{idx:>3}  Q{per if per is not None else '?'} {clk or ''}  home={hw} away={aw}")

def _abbr_map_from_header(root: dict) -> dict:
    # Build team id -> abbreviation map from header.competitions[0].competitors
    comp = (root.get("header") or {}).get("competitions") or []
    comp0 = comp[0] if comp else {}
    out = {}
    for c in comp0.get("competitors", []):
        tid = str(((c.get("team") or {}).get("id")))
        ab  = (c.get("team") or {}).get("abbreviation")
        if tid and ab:
            out[tid] = ab
    return out

def _fmt_down_dist(play: dict) -> str:
    # Use ESPN’s prebuilt strings when present
    sd = (((play.get("start") or {}).get("shortDownDistanceText")) or
          ((play.get("start") or {}).get("downDistanceText")) or "")
    return sd

def _fmt_spot(play: dict) -> str:
    # “possessionText” already combines team side + yard (e.g., PHI 33)
    pos = ((play.get("start") or {}).get("possessionText")) or ""
    return pos

def _fmt_clock_period(play: dict) -> str:
    per = ((play.get("period") or {}).get("number"))
    clk = ((play.get("clock") or {}).get("displayValue")) or ""
    if per is None:
        return clk or ""
    return f"Q{per} {clk}".strip()

def _fmt_score_tail(play: dict) -> str:
    # Away–Home matches ESPN top-level notation
    a = play.get("awayScore")
    h = play.get("homeScore")
    if a is None or h is None:
        return ""
    return f" | {a}-{h}"

def _fmt_play_line(play: dict) -> str:
    # Compose: Qx mm:ss  2&7 at PHI 33 — text  |  away-home
    head = _fmt_clock_period(play)
    dd   = _fmt_down_dist(play)
    spot = _fmt_spot(play)
    txt  = (play.get("text") or play.get("description") or "").strip()
    score= _fmt_score_tail(play)
    parts = []
    if head: parts.append(head)
    if dd:   parts.append(dd)
    if spot: parts.append(f"at {spot}")
    lead = "  ".join(parts) if parts else ""
    if lead:
        return f"  • {lead} — {txt}{score}"
    return f"  • {txt}{score}"

def describe_play(play: dict) -> str:
    """
    Return a detailed but readable one-line summary of a single play.
    Avoids dumping raw JSON.
    """
    # Quarter & clock
    period = (play.get("period") or {}).get("number", "?")
    clock = (play.get("clock") or {}).get("displayValue", "")

    # Down, distance, yard line
    start = play.get("start", {})
    down = start.get("down")
    dist = start.get("distance")
    spot = start.get("possessionText") or ""
    down_dist = f"{down}&{dist}" if down and dist else ""
    yardline = f"at {spot}" if spot else ""

    # Play type
    ptype = (play.get("type") or {}).get("text", "")
    ptxt = (play.get("text") or play.get("description") or "").strip()

    # Scoring, penalty, yardage
    yards = play.get("statYardage")
    pen = (play.get("penalty") or {}).get("type", {}).get("text")
    pen_yards = (play.get("penalty") or {}).get("yards")

    # Score after play
    a = play.get("awayScore")
    h = play.get("homeScore")
    score_str = f"  |  {a}-{h}" if a is not None and h is not None else ""

    # Assemble pieces
    parts = [f"Q{period} {clock}".strip()]
    if down_dist:
        parts.append(down_dist)
    if yardline:
        parts.append(yardline)
    if ptype:
        parts.append(f"({ptype})")

    header = " ".join(p for p in parts if p)
    desc = ptxt or "(no description)"

    # Append yards / penalties for quick insight
    tail = []
    if yards is not None:
        tail.append(f"{yards:+} yds")
    if pen:
        pen_str = f"Penalty: {pen}"
        if pen_yards:
            pen_str += f" ({pen_yards} yds)"
        tail.append(pen_str)

    tail_text = " | ".join(tail)
    if tail_text:
        desc += f" — {tail_text}"

    return f"  • {header} — {desc}{score_str}"

def main() -> int:
    """
    /**
     * @brief Run the scoreboard, summary, and play-by-play test suite.
     *
     * @return Exit code: 0 on success; non-zero if validations fail.
     *
     * @details
     *   - Validates ESPN API integration (scoreboard, summary, PBP).
     *   - Tests caching behavior and normalization schemas.
     *   - Provides compact readable summaries for quick inspection.
     */
    """

    # ------------------------------------------------------------
    # 1. Parse any CLI arguments for custom test configuration
    # ------------------------------------------------------------
    parser = argparse.ArgumentParser(description="ESPN integration test (scoreboard/summary/pbp).")
    parser.add_argument("--dates", type=str, default=None, help="YYYYMMDD (e.g., 20251012)")
    parser.add_argument("--week", type=int, default=None, help="NFL week number (int)")
    parser.add_argument("--seasontype", type=int, choices=[1, 2, 3], default=None, help="1=Pre, 2=Reg, 3=Post")
    parser.add_argument("--event", type=str, default=None, help="Explicit ESPN event id for summary/pbp tests")
    parser.add_argument("--full", action="store_true", help="Print the full ESPN /summary overview (long).")
    args = parser.parse_args()

    # Print header showing what configuration is being used for this run
    print("---- ESPN Integration Test ----")
    print(f"dates={args.dates}  week={args.week}  seasontype={args.seasontype}  event={args.event}")
    print("--------------------------------")

    # ------------------------------------------------------------
    # 2. Fetch scoreboard twice (tests network call + cache)
    # ------------------------------------------------------------
    t0 = time.time()
    raw_1 = fetch_scoreboard(dates=args.dates, week=args.week, seasontype=args.seasontype)
    dt1 = time.time() - t0
    _ok(f"fetch_scoreboard() #1 completed in {dt1:.2f}s")

    # Perform a second immediate fetch to confirm cache behavior
    t1 = time.time()
    raw_2 = fetch_scoreboard(dates=args.dates, week=args.week, seasontype=args.seasontype)
    dt2 = time.time() - t1
    _ok(f"fetch_scoreboard() #2 (cache) completed in {dt2:.2f}s")

    # ------------------------------------------------------------
    # 3. Normalize scoreboard payload
    # ------------------------------------------------------------
    games = normalize_scoreboard(raw_2)
    _ok(f"normalize_scoreboard() returned {len(games)} games")

    # Validate schema for each normalized game
    all_errors: List[Tuple[str, List[str]]] = []
    for g in games:
        errs = _validate_game_schema(g)
        if errs:
            all_errors.append((g.get("espn_event_id"), errs)) # type: ignore

    # Print schema validation results
    if all_errors:
        _fail(f"Schema validation failed for {len(all_errors)} game(s):")
        for eid, errs in all_errors:
            print(f"   Event {eid}:")
            for e in errs:
                print(f"     - {e}")
    else:
        _ok("Schema validation passed for all games")

    # ------------------------------------------------------------
    # 4. Print a compact summary for the first several games
    # ------------------------------------------------------------
    print("\n---- Games (brief) ----")
    for g in games[:20]:
        _print_game_brief(g)
    if len(games) > 20:
        print(f"   ... (+{len(games)-20} more)")

    # ------------------------------------------------------------
    # 5. Pick an event for summary + PBP testing
    # ------------------------------------------------------------
    target_event = args.event or _pick_event_id(games)
    if not target_event:
        _warn("No games found to test summary/pbp. Skipping those calls.")
        return 0 if not all_errors else 2

    # ------------------------------------------------------------
    # 6. Fetch and print the game summary
    # ------------------------------------------------------------
    ts0 = time.time()
    raw_summary = fetch_summary(target_event)
    ds = time.time() - ts0
    _ok(f"fetch_summary(event={target_event}) in {ds:.2f}s")

    # Print detailed readable summary breakdown
    _print_summary_brief(target_event, raw_summary)

    # ------------------------------------------------------------
    # 7. Fetch and print play-by-play information
    # ------------------------------------------------------------
    tp0 = time.time()
    raw_pbp = fetch_playbyplay(target_event)
    dp = time.time() - tp0
    _ok(f"fetch_playbyplay(event={target_event}) in {dp:.2f}s")

    # Print compact readable play-by-play snapshot
    _print_pbp_brief(target_event, raw_pbp, raw_summary_fallback=raw_summary, max_scoring=5, max_recent=5)

    # ------------------------------------------------------------
    # 8. Optional deep-dive: full /summary explorer (long)
    # ------------------------------------------------------------
    if args.full:
        print("\n==== FULL SUMMARY (long) ====\n")
        print_summary_overview(raw_summary)
        print("\n==== EXPANDED ESPN SUMMARY SECTIONS ====\n")
        print_other_sections(raw_summary, limit=8)  # <- drills into the previewed sections

    # ------------------------------------------------------------
    # 9. Return success code for CI or manual verification
    # ------------------------------------------------------------
    return 0 if not all_errors else 2


if __name__ == "__main__":
    # Call main() and exit with the returned code
    sys.exit(main())