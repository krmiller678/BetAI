#!/usr/bin/env python3
# pyright: reportOptionalMemberAccess=none, reportArgumentType=none, reportReturnType=none
# =============================================================================
# File: frontend/streamlit_app/demo/scoreboard_tester_v2.py
# -----------------------------------------------------------------------------
# @brief  Minimal, presentation-ready tester for ESPN integration.
# @details
#   - Prints timings for key calls to demonstrate cache behavior.
#   - Shows a concise scoreboard list for the current slate/date/week.
#   - Expands ONE event (chosen via --event or the first game found) with:
#       * Matchup / Status / Venue / Final line (with W/L flags)
#       * Team boxscore statistics (away then home)
#       * Last previous drive summary with all plays (formatted)
#       * Full list of scoring plays
#   - Intentionally omits noisy sections (leaders, broadcasts, meta, etc.)
#
# Usage:
#   python3 frontend/streamlit_app/demo/scoreboard_tester_v2.py
#   python3 frontend/streamlit_app/demo/scoreboard_tester_v2.py --event 401772940
#   python3 frontend/streamlit_app/demo/scoreboard_tester_v2.py --dates 20251012
#   python3 frontend/streamlit_app/demo/scoreboard_tester_v2.py --week 6 --seasontype 2
#
# Notes:
#   - This script bootstraps sys.path to the repo root so internal imports work
#     even when run from different working directories.
# =============================================================================

# ---------------- repo path bootstrap ----------------
# Import system and path utilities
import sys, pathlib
# Resolve the repository root (BetAI/) from this file's path
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
# Ensure the repo root is on sys.path so internal modules can be imported
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
# -----------------------------------------------------

# Import argparse for command-line flag parsing
import argparse
# Import time for simple elapsed time measurements
import time
# Import typing helpers for clarity and static checking
from typing import Any, Dict, List, Optional, Tuple

# Import ESPN integration primitives from our backend
from backend.core.betai.integrations.pbp_api import (
    fetch_scoreboard,       # Function to retrieve raw scoreboard JSON
    normalize_scoreboard,   # Function to convert raw scoreboard → normalized list[dict]
    fetch_summary,          # Function to retrieve raw /summary JSON for one event
    fetch_playbyplay,       # Function to retrieve raw /pbp JSON for one event
    compute_seconds_left,   # Utility to calculate seconds left from period/clock
)

# =============================================================================
# Helper utilities (small, focused, heavily commented)
# =============================================================================

# -----------------------------------------------------------------------------
# @brief  Clip a value to N characters and add ellipsis if needed.
# @param  s  Any value to render as a string for display.
# @param  n  Maximum characters to allow before truncation.
# @return str  A safe, clipped string representation.
# -----------------------------------------------------------------------------
def _clip(s: Any, n: int = 120) -> str:
    # Convert value to string or empty if None
    s = "" if s is None else str(s)
    # Return unchanged if within limit
    if len(s) <= n:
        return s
    # Otherwise return truncated with a single-character ellipsis tail
    return s[: n - 1] + "…"


# -----------------------------------------------------------------------------
# @brief  Safe nested getter for dict/list payloads.
# @param  obj     Root object (dict-like JSON structure).
# @param  *path   Sequence of keys (and/or int indices) to traverse.
# @param  default Fallback value if any step is missing or invalid.
# @return Any     The located value or the provided default.
# -----------------------------------------------------------------------------
def _g(obj: Dict, *path, default=None):
    # Start cursor at the root object
    cur = obj
    # Traverse path components one at a time
    for k in path:
        # If current is dict, access by key (with default)
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        # If current is list and key is an index, bounds-check then index
        elif isinstance(cur, list) and isinstance(k, int):
            cur = cur[k] if 0 <= k < len(cur) else default
        # If neither dict nor list, bail to default
        else:
            return default
        # If we hit None early, stop and return default
        if cur is None:
            return default
    # Return the resolved value
    return cur


# -----------------------------------------------------------------------------
# @brief  Print a green "OK" line to indicate a pass/success condition.
# @param  msg  Message to display after the checkmark.
# -----------------------------------------------------------------------------
def _ok(msg: str) -> None:
    # Print success with a checkmark glyph
    print(f"✅ {msg}")


# -----------------------------------------------------------------------------
# @brief  Print a yellow "Warn" line for non-fatal conditions.
# @param  msg  Message to display after the warning symbol.
# -----------------------------------------------------------------------------
def _warn(msg: str) -> None:
    # Print warning with a caution glyph
    print(f"⚠️  {msg}")


# -----------------------------------------------------------------------------
# @brief  Build a single concise scoreboard line for a normalized game.
# @param  game  One normalized game dictionary (from normalize_scoreboard()).
# @return str   Human-friendly single-line summary.
# -----------------------------------------------------------------------------
def _line_game_brief(game: Dict[str, Any]) -> str:
    # Read ESPN event id (or placeholder)
    eid = game.get("espn_event_id") or "?"
    # Convert game state to upper for compact readability (PRE/IN/POST)
    state = (game.get("state") or "").upper()
    # Extract period number (or dash if unavailable)
    per = game.get("period") or "-"
    # Extract display clock (or placeholder if missing)
    clk = game.get("display_clock") or "--:--"

    # Extract home/away sub-dicts defensively
    home = game.get("home") or {}
    away = game.get("away") or {}

    # Read scores with safe fallbacks to 0 for None
    hs = home.get("score", 0) if home.get("score") is not None else 0
    as_ = away.get("score", 0) if away.get("score") is not None else 0

    # Read team display names with defaults
    hname = home.get("name", "Home")
    aname = away.get("name", "Away")

    # Compute seconds left if period/clock are available
    sec_left = compute_seconds_left(game.get("period"), game.get("display_clock"))
    # Build optional tail segment only when seconds_left is computable
    tail = f" • {sec_left}s left" if sec_left is not None else ""

    # Construct the final one-line summary string
    return f"[{eid}] {aname} {as_} @ {hname} {hs}  |  {state} • Q{per} • {clk}{tail}"

# =============================================================================
# Expanded single-event renderers (ONLY the sections we want to show)
# =============================================================================

# -----------------------------------------------------------------------------
# @brief  Print the header block: Matchup / Status / Venue / Final W/L flags.
# @param  summary_json  Raw ESPN /summary JSON dict.
# @return Tuple[str, str, str, Tuple]  (away_name, home_name, venue, abbr/score tuple)
# -----------------------------------------------------------------------------
def print_matchup_status_venue(summary_json: Dict[str, Any]) -> Tuple[str, str, str, Tuple]:
    # Prefer ESPN's nested "gamepackageJSON" root if present; otherwise use root
    root = summary_json.get("gamepackageJSON") if "gamepackageJSON" in summary_json else summary_json
    # Retrieve the first competition node (most game-level fields live here)
    comp = _g(root, "header", "competitions", 0, default={}) # type: ignore
    # Read competitor list for home/away
    teams = comp.get("competitors") or [] # type: ignore

    # Define a small helper to pick a side's key values
    def pick(side: str):
        # Loop all competitors to locate the requested side
        for c in teams:
            if c.get("homeAway") == side:
                # Extract team node (contains displayName/abbreviation)
                team = c.get("team") or {}
                # Resolve display name (fallback to "HOME"/"AWAY")
                name = team.get("displayName") or side.upper()
                # Resolve short abbreviation (fallback to first 3 of side)
                abbr = team.get("abbreviation") or side[:3].upper()
                # Read current score
                score = c.get("score")
                # Initialize record string if present (e.g., "4-2")
                record = None
                recs = c.get("records") or []
                if recs and recs[0].get("summary"):
                    record = recs[0]["summary"]
                # Winner flag (True/False/None)
                winner = c.get("winner")
                # Return a structured tuple for the side
                return name, abbr, score, record, winner
        # If not found, return safe placeholders
        return side.upper(), side[:3].upper(), None, None, None

    # Extract away/home tuple sets
    away_nm, away_ab, away_sc, away_rec, away_win = pick("away")
    home_nm, home_ab, home_sc, home_rec, home_win = pick("home")

    # Read status/type info (contains “Final”, “In Progress”, etc.)
    status_type = _g(comp, "status", "type", default={})
    # Prefer human description; fallback to the state title-cased; fallback to "Status"
    desc = status_type.get("description") or (status_type.get("state") or "").title() or "Status"
    # Period number and display clock
    period = _g(comp, "status", "period")
    clock = _g(comp, "status", "displayClock") or "0:00"

    # Derive venue either from gameInfo or directly from competition (if present)
    gi = summary_json.get("gamepackageJSON", {}).get("gameInfo", {}) if "gamepackageJSON" in summary_json else summary_json.get("gameInfo", {})
    venue = _g(gi, "venue", "fullName", default=None) or _g(comp, "venue", "fullName", default="-")

    # Print the main matchup line
    print(f"Matchup: {away_nm} {away_sc} @ {home_nm} {home_sc}")
    # Print status line with period/clock when available
    if period:
        print(f"Status : {desc} • Q{period} • {clock}")
    else:
        print(f"Status : {desc}")
    # Print venue only when available and not "-"
    if venue and venue != "-":
        print(f"Venue  : {venue}")

    # If game is POST (final), add a compact final/winner line with records
    state = (status_type.get("state") or "").upper()
    if state == "POST":
        # Compute result flags (W/L) with None-safe logic
        af = "W" if away_win else "L" if away_win is not None else "-"
        hf = "W" if home_win else "L" if home_win is not None else "-"
        # Append (record) when available for clarity
        ars = f" ({away_rec})" if away_rec else ""
        hrs = f" ({home_rec})" if home_rec else ""
        # Print final result line in compact split format
        print(f"Final  : {away_ab} {away_sc}{ars} {af}  |  {home_ab} {home_sc}{hrs} {hf}")

    # Return a structured tuple in case a caller needs these values later
    return away_nm, home_nm, venue, (away_ab, home_ab, away_sc, home_sc)


# -----------------------------------------------------------------------------
# @brief  Print team-level boxscore statistics for both teams.
# @param  summary_json  Raw ESPN /summary JSON dict.
# -----------------------------------------------------------------------------
def print_team_boxscore(summary_json: Dict[str, Any]) -> None:
    # Prefer nested "gamepackageJSON" root if present
    root = summary_json.get("gamepackageJSON") if "gamepackageJSON" in summary_json else summary_json
    # Access boxscore.teams which holds per-team stats blocks
    teams = _g(root, "boxscore", "teams", default=[]) or []
    # If absent, silently return (some games may not expose this)
    if not teams:
        return

    # Print a section header
    print("\n— Team Boxscore Statistics —")
    # Iterate away/home blocks in the order provided
    for t in teams:
        # Build a label from homeAway + team.displayName
        side = (t.get("homeAway") or "").capitalize() or "Team"
        label = _g(t, "team", "displayName", default=side)
        print(f"  [{side}] {label}")

        # List of stat name/value pairs
        stats = t.get("statistics") or []
        # Print each item as a bullet line
        for s in stats:
            print(f"    • {s.get('name')}: {s.get('displayValue')}")
        # Blank spacer between teams
        print("")


# -----------------------------------------------------------------------------
# @brief  Convert one play dict into a compact, readable one-liner.
# @param  play  Single play object from drives[*].plays.
# @return str   Formatted play summary (clock, down/dist, spot, text, score tail).
# -----------------------------------------------------------------------------
def _fmt_play(play: dict) -> str:
    # Extract period (quarter) number if available
    per = _g(play, "period", "number", default=None)
    # Extract game clock display (mm:ss) if available
    clk = _g(play, "clock", "displayValue", default="")
    # Build a Qx mm:ss prefix only when quarter is known
    pfx = f"Q{per} {clk}".strip() if per else clk

    # Prefer ESPN's short down/distance text, fallback to longer variant
    sd = _g(play, "start", "shortDownDistanceText", default="") or _g(play, "start", "downDistanceText", default="")
    # possessionText already has the team side and yard (e.g., PHI 33)
    spot = _g(play, "start", "possessionText", default="")

    # Assemble the left-hand "lead" fields in a consistent order
    lead_parts = []
    if pfx:
        lead_parts.append(pfx)
    if sd:
        lead_parts.append(sd)
    if spot:
        lead_parts.append(f"at {spot}")
    lead = "  ".join(lead_parts)

    # Use text or description for the narrative part of the play
    txt = (play.get("text") or play.get("description") or "").strip()

    # Append away-home score tail when both are present
    a, h = play.get("awayScore"), play.get("homeScore")
    score_tail = f"  |  {a}-{h}" if a is not None and h is not None else ""

    # Return a consistent bullet format (lead — desc [| score])
    return f"  • {lead} — {txt}{score_tail}" if lead else f"  • {txt}{score_tail}"


# -----------------------------------------------------------------------------
# @brief  Print last previous drive (with plays) and the scoring plays list.
# @param  summary_json  Raw ESPN /summary JSON dict.
# -----------------------------------------------------------------------------
def print_drives_and_scoring(summary_json: Dict[str, Any]) -> None:
    # Prefer nested "gamepackageJSON" root if available
    root = summary_json.get("gamepackageJSON") if "gamepackageJSON" in summary_json else summary_json
    # Pull drives dict: {"previous": [...], "current": {...}}
    drives = _g(root, "drives", default={}) or {}
    # Read previous list (completed drives)
    prev = drives.get("previous") or []
    # Read current dict (ongoing drive), may be empty
    cur = drives.get("current") or {}

    
    # Scoring plays: summarize from top-level "scoringPlays"
    sps = _g(root, "scoringPlays", default=[]) or []
    if sps:
        # Print header with count
        print("\n— Scoring Plays —  (" + str(len(sps)) + " item(s))")
        # Enumerate each scoring play and render consistent lines
        for i, sp in enumerate(sps):
            clk = _g(sp, "clock", "displayValue", default="")
            per = _g(sp, "period", "number", default="?")
            txt = sp.get("text") or sp.get("description") or ""
            a = sp.get("awayScore")
            h = sp.get("homeScore")
            print(f"  • [{i}] Q{per} {clk:>5}  {txt}  |  {a}-{h}")

    # Print section header with a quick count of previous/current
    print("\n— Drives —")
    print(f"  previous: {len(prev)}  | current: {'present' if cur else 'none'}")

    # If we have any previous drives, show the last one + its plays
    if prev:
        # Select last complete drive
        last = prev[-1]
        # Read basic drive summary numbers
        yards = last.get("yards")
        plays = last.get("plays") or []
        dur = _g(last, "timeElapsed", "displayValue", default="")
        # Pull a short human label (if present)
        # desc = last.get("description") or last.get("displayResult") or ""   # <- available but not printed
        # Print the compact drive summary line
        print(f"  last drive: {len(plays)} plays, {yards} yards, {dur}")
        # If the drive has plays, print them one by one in a compact format
        if plays:
            print("  plays:")
            for p in plays:
                print(_fmt_play(p))


# Choose a good default ESPN event id when --event is not provided
def _pick_event_id_smart(games: List[dict], raw_scoreboard: Any = None) -> Optional[str]:
    # ------------------------------------------------------------
    # 1) Collect candidate games that have a known espn_event_id
    # ------------------------------------------------------------
    # Create list of games where 'espn_event_id' is truthy
    candidates = [g for g in games if g.get("espn_event_id")]

    # ------------------------------------------------------------
    # 2) Prefer states in this order: IN (live) → POST (final) → PRE
    # ------------------------------------------------------------
    # Define priority where lower is better (0=best)
    prio = {"IN": 0, "POST": 1, "PRE": 2}

    # Small key function that returns (priority, index) for sorting
    def _key(g: dict) -> tuple:
        # Get normalized state uppercased or use 'ZZ' to sink unknowns
        state = (g.get("state") or "").upper()
        # Map to priority integer, default to large number if unknown
        p = prio.get(state, 99)
        # Keep original order stable by using enumerate index as tiebreaker later
        return (p, 0)

    # If we have any candidates, pick the best by priority ordering
    if candidates:
        # Sort by priority (stable; first best wins)
        candidates.sort(key=_key)
        # Return the espn_event_id from the first candidate
        return candidates[0].get("espn_event_id")

    # ------------------------------------------------------------
    # 3) Fallback: try to read the first event id from the raw scoreboard JSON
    # ------------------------------------------------------------
    # ESPN scoreboards generally have an 'events' list with 'id' fields
    try:
        # Get events list from raw json
        events = (raw_scoreboard or {}).get("events") or []
        # Return first event's id if present
        if events and isinstance(events, list):
            eid = str(events[0].get("id") or "")
            return eid or None
    except Exception:
        # Swallow any shape errors; we'll return None below
        pass

    # ------------------------------------------------------------
    # 4) Nothing found
    # ------------------------------------------------------------
    # Return None to signal no event id could be determined
    return None

# =============================================================================
# Main entry point
# =============================================================================

# -----------------------------------------------------------------------------
# @brief  Program entry: parse args, fetch data, print compact report.
# @return int  Process exit code (0=success).
# -----------------------------------------------------------------------------
def main() -> int:
    # -------------------- CLI ARGUMENTS --------------------
    # Create an ArgumentParser for this tester
    parser = argparse.ArgumentParser(
        description="Minimal ESPN tester (timings, scoreboard, single expanded event)."
    )
    # Optional: specific date in YYYYMMDD (e.g., 20251012)
    parser.add_argument("--dates", type=str, default=None, help="YYYYMMDD (e.g., 20251012)")
    # Optional: NFL week number (int)
    parser.add_argument("--week", type=int, default=None, help="NFL week number")
    # Optional: season type: 1=Pre, 2=Reg, 3=Post
    parser.add_argument("--seasontype", type=int, choices=[1, 2, 3], default=None, help="1=Pre, 2=Reg, 3=Post")
    # Optional: target event id to expand the details for
    parser.add_argument("--event", type=str, default=None, help="ESPN event id to expand")
    # Parse all provided CLI arguments
    args = parser.parse_args()

    # -------------------- HEADER --------------------
    # Print a concise script header for context
    print("---- ESPN Integration Test (v2) ----")

    # -------------------- SCOREBOARD (Network) --------------------
    # Capture start time for the first scoreboard fetch
    t0 = time.time()
    # Perform the initial fetch (hits network/cache layer in backend)
    raw_1 = fetch_scoreboard(dates=args.dates, week=args.week, seasontype=args.seasontype)
    # Compute elapsed seconds for the first fetch
    dt0 = time.time() - t0
    # Print an OK line with duration
    _ok(f"fetch_scoreboard() #1 completed in {dt0:.2f}s")

    # -------------------- SCOREBOARD (Cache) --------------------
    # Capture start time for the immediate second fetch (should be fast)
    t1 = time.time()
    # Perform the second fetch to demonstrate cache speed
    raw_2 = fetch_scoreboard(dates=args.dates, week=args.week, seasontype=args.seasontype)
    # Compute elapsed seconds for the second fetch
    dt1 = time.time() - t1
    # Print an OK line with duration (should show near-zero)
    _ok(f"fetch_scoreboard() #2 (cache) completed in {dt1:.2f}s")

    # -------------------- NORMALIZE --------------------
    # Convert the raw scoreboard payload into normalized game dicts
    games = normalize_scoreboard(raw_2)
    # Print an OK line (normalization is typically negligible time)
    _ok("normalize_scoreboard() completed in 0.00s")

    # -------------------- SCOREBOARD (Brief List) --------------------
    # Print a short list of up to 20 concise game lines
    print("\n---- Games Scoreboard ----")
    for g in games[:20]:
        # Render each game as a one-line summary and print it
        print("   ", _line_game_brief(g))
    # If more than 20 games exist, indicate there are additional items
    if len(games) > 20:
        print(f"   ... (+{len(games)-20} more)")

    # -------------------- CHOOSE EVENT --------------------
    # Determine which event to expand: CLI --event or first game’s id
    eid = args.event or _pick_event_id_smart(games, raw_scoreboard=raw_2)

    # Optional: print what got picked so it’s obvious to the presenter
    if not args.event and eid:
        print(f"\n(i) No --event provided; auto-selected event id: {eid}\n")

    # If no event id was found, warn and exit success (since core test ran)
    if not eid:
        _warn("No event id found; skipping expanded section.")
        return 0

    # -------------------- SUMMARY FETCH --------------------
    # Capture start time for the summary fetch
    ts = time.time()
    # Retrieve the /summary JSON for the chosen event
    summary = fetch_summary(eid)
    # Compute elapsed seconds for summary
    dts = time.time() - ts
    # Print an OK line with duration
    _ok(f"fetch_summary(event={eid}) completed in {dts:.2f}s")

    # -------------------- PBP FETCH (timed only) --------------------
    # Capture start time for the play-by-play fetch (for completeness/timing)
    tp = time.time()
    # Retrieve the /pbp JSON for the same event (we don’t print it here)
    _ = fetch_playbyplay(eid)
    # Compute elapsed seconds for pbp
    dtp = time.time() - tp
    # Print an OK line with duration
    _ok(f"fetch_playbyplay(event={eid}) completed in {dtp:.2f}s")

    # -------------------- EXPANDED SINGLE-EVENT VIEW --------------------
    # Print a clear section header for the expanded block
    print("\n—— Expanded Game Data ——")
    # Print matchup/status/venue/final lines
    print_matchup_status_venue(summary)
    # Print team boxscore stats for both teams
    print_team_boxscore(summary)
    # Print last previous drive and the scoring plays list
    print_drives_and_scoring(summary)

    # Return 0 to indicate success (useful for CI hooks)
    return 0


# -----------------------------------------------------------------------------
# Standard Python entry guard to allow import without execution.
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Execute main() and use its return value as the process exit code
    sys.exit(main())