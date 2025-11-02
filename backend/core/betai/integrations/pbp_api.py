# backend/core/betai/integrations/pbp_api.py
# ------------------------------------------------------------
# Purpose:
#   Single integration client for ESPN NFL data (scoreboard, summary, play-by-play).
#   Mirrors the odds_api integration pattern used elsewhere in the repo.
#
# Design:
#   - One generic _get() that builds URLs, adds query params, handles a small TTL cache,
#     performs the HTTP request via requests.get(..., params=...), and returns parsed JSON.
#   - Public fetch_*() functions per endpoint that only specify path + params.
#   - Normalization helpers that convert ESPN's verbose JSON into compact, stable dicts
#     used by the rest of the app (frontend views, agent, feature builder).
#
# Notes:
#   - No API key required for these ESPN endpoints.
#   - Situation fields on the scoreboard can be missing; normalization tolerates that.
#   - Keep normalization minimal here; richer feature derivations happen elsewhere
#     (e.g., in a feature builder).
# ------------------------------------------------------------

from __future__ import annotations

# Import typing for explicit and readable type hints
from typing import Any, Dict, List, Optional, Tuple

# Import time for timestamping cache entries
import time

# Import requests to perform HTTP GET calls; it handles querystring encoding for us
import requests


# =========================
# Constants and Cache
# =========================

# Base URL constant for all ESPN NFL endpoints
ESPN_BASE: str = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# In-memory cache dictionary: key -> (timestamp, data)
_CACHE: Dict[str, Tuple[float, Any]] = {}

# Default TTL (seconds) controlling how long a cached response is considered fresh
_DEFAULT_TTL: int = 8


# =========================
# Internal HTTP Helper
# =========================

def _get(path: str, params: Optional[Dict[str, Any]] = None, *, ttl: int = _DEFAULT_TTL) -> Any:
    """
    /**
     * @brief Perform a cached HTTP GET to ESPN.
     *
     * @param path    Relative endpoint path (e.g., "/scoreboard").
     * @param params  Optional query parameters (e.g., {"dates": "20251012"}).
     * @param ttl     Cache time-to-live (seconds) before refreshing.
     *
     * @return Parsed JSON (Python dict/list) from ESPN.
     *
     * @details
     *   - Builds the full URL by concatenating ESPN_BASE + path.
     *   - Lets requests.get(..., params=...) handle proper querystring encoding.
     *   - Uses a small in-memory cache keyed by (url + sorted(params)) to reduce calls.
     *   - Raises for HTTP errors and returns resp.json() on success.
     */
    """
    # Build the full URL by combining the base and the endpoint path
    url: str = f"{ESPN_BASE}{path}"

    # Normalize params to an empty dict if None for consistent handling
    query: Dict[str, Any] = params or {}

    # Build a cache key that uniquely identifies this request (URL + sorted params)
    cache_key: str = f"{url}|{tuple(sorted(query.items()))}"

    # Record the current time to compare against cache timestamps
    now: float = time.time()

    # Check if a fresh cached entry exists for this request
    if cache_key in _CACHE:
        cached_ts, cached_data = _CACHE[cache_key]
        # If the cached data is still within TTL, return it immediately
        if now - cached_ts < ttl:
            return cached_data

    # If no fresh cache is available, perform the HTTP GET call
    # NOTE: requests.get(..., params=query) internally builds:
    #       URL + "?" + urlencode(query) safely and correctly.
    resp = requests.get(url, params=query, timeout=15)

    # Raise an HTTPError for non-2xx responses (e.g., 404, 500)
    resp.raise_for_status()

    # Parse the JSON body into Python types (dict/list)
    data: Any = resp.json()

    # Store the response and timestamp in the cache for subsequent calls
    _CACHE[cache_key] = (now, data)

    # Return the parsed JSON payload to the caller
    return data


# =========================
# Public Fetch Functions
# =========================

def fetch_scoreboard(*, dates: Optional[str] = None, week: Optional[int] = None, seasontype: Optional[int] = None) -> Dict[str, Any]:
    """
    /**
     * @brief Fetch ESPN NFL scoreboard (many games).
     *
     * @param dates       Optional YYYYMMDD string (e.g., "20251012") to select a day.
     * @param week        Optional integer NFL week number.
     * @param seasontype  Optional season type: 1=Pre, 2=Reg, 3=Post.
     *
     * @return Raw ESPN JSON (dict) for the scoreboard endpoint.
     *
     * @details
     *   - When params are omitted, ESPN returns the current day's slate.
     *   - Only includes parameters that are provided (no "None" in querystring).
     */
    """
    # Initialize an empty params dictionary
    params: Dict[str, Any] = {}

    # Add 'dates' to params only if provided
    if dates:
        params["dates"] = dates

    # Add 'week' to params only if provided
    if week is not None:
        params["week"] = int(week)

    # Add 'seasontype' to params only if provided
    if seasontype is not None:
        params["seasontype"] = int(seasontype)

    # Delegate to the internal GET helper with the composed path and params
    return _get("/scoreboard", params=params)


def fetch_summary(event_id: str) -> Dict[str, Any]:
    """
    /**
     * @brief Fetch ESPN NFL game summary (single game).
     *
     * @param event_id  ESPN event id string (e.g., "401671234").
     *
     * @return Raw ESPN JSON (dict) for the summary endpoint.
     */
    """
    # Call internal GET helper with path and 'event' query parameter
    return _get("/summary", params={"event": event_id})


def fetch_playbyplay(event_id: str) -> Dict[str, Any]:
    """
    /**
     * @brief Fetch ESPN NFL play-by-play (single game).
     *
     * @param event_id  ESPN event id string (e.g., "401671234").
     *
     * @return Raw ESPN JSON (dict) for the play-by-play endpoint.
     */
    """
    # Call internal GET helper with path and 'event' query parameter
    return _get("/playbyplay", params={"event": event_id})


# =========================
# Normalization Helpers
# =========================

def normalize_scoreboard(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    /**
     * @brief Convert ESPN scoreboard JSON to a compact, stable schema.
     *
     * @param raw  Raw ESPN JSON as returned by fetch_scoreboard().
     *
     * @return List of normalized game dicts with keys:
     *   - espn_event_id: str
     *   - commence_time: str (ISO timestamp)
     *   - state: str ("pre" | "in" | "post")
     *   - period: Optional[int] quarter number
     *   - display_clock: Optional[str] "MM:SS" during live games
     *   - home: { name:str|None, abbr:str|None, logo:str|None, score:int|None }
     *   - away: { name:str|None, abbr:str|None, logo:str|None, score:int|None }
     *   - situation: {
     *       down:int|None, distance:int|None, yardLine:int|None,
     *       isRedZone:bool|None, possession:str|None, lastPlay:str|None
     *     }
     *
     * @details
     *   - Handles missing or partially present fields gracefully.
     *   - Only extracts fields needed by the UI and the agent's feature builder.
     */
    """
    # Prepare the output list for normalized games
    games: List[Dict[str, Any]] = []

    # Safely get the 'events' list from the raw payload
    for ev in (raw or {}).get("events", []):
        # Read the ESPN event id (string) for this game
        event_id: Optional[str] = ev.get("id")

        # Read the scheduled/actual start time in ISO format
        date_iso: Optional[str] = ev.get("date")

        # Extract the first 'competition' block which contains game-level details
        competitions: List[Dict[str, Any]] = ev.get("competitions") or []
        comp: Dict[str, Any] = competitions[0] if competitions else {}

        # Extract status and nested type information (state, period, clock)
        status: Dict[str, Any] = comp.get("status", {})
        status_type: Dict[str, Any] = status.get("type") or {}
        state: Optional[str] = status_type.get("state")           # "pre" | "in" | "post"
        period: Optional[int] = status.get("period")              # quarter number (1..4; OT also possible)
        display_clock: Optional[str] = status.get("displayClock") # live clock string "MM:SS" or None

        # Initialize compact home/away team blocks to ensure keys always exist
        home: Dict[str, Any] = {"name": None, "abbr": None, "logo": None, "score": None}
        away: Dict[str, Any] = {"name": None, "abbr": None, "logo": None, "score": None}

        # Iterate the competitors to fill in home/away blocks
        for team in comp.get("competitors", []):
            # Read whether this competitor is the home or away team
            side: Optional[str] = team.get("homeAway")  # "home" | "away"

            # Read the nested team info dict
            tinfo: Dict[str, Any] = team.get("team") or {}

            # Extract display name (full name), abbreviation, and logo url
            name: Optional[str] = tinfo.get("displayName")
            abbr: Optional[str] = tinfo.get("abbreviation")
            logos: List[Dict[str, Any]] = tinfo.get("logos") or []
            logo_href: Optional[str] = (logos[0] or {}).get("href") if logos else None

            # Extract the current score; coerce to int when possible
            raw_score = team.get("score")
            try:
                score_int: Optional[int] = int(raw_score) if raw_score is not None else None
            except Exception:
                score_int = None

            # Assign values into the correct team block by side
            if side == "home":
                home.update({"name": name, "abbr": abbr, "logo": logo_href, "score": score_int})
            elif side == "away":
                away.update({"name": name, "abbr": abbr, "logo": logo_href, "score": score_int})

        # Extract the optional 'situation' block (down/distance etc.)
        sit: Dict[str, Any] = comp.get("situation") or {}

        # Build a compact situation dict with only fields we care about
        situation: Dict[str, Any] = {
            "down": sit.get("down"),
            "distance": sit.get("distance"),
            "yardLine": sit.get("yardLine"),
            "isRedZone": sit.get("isRedZone"),
            "possession": sit.get("possession"),             # team name string if present
            "lastPlay": (sit.get("lastPlay") or {}).get("text"),
        }

        # Assemble the normalized game record
        game: Dict[str, Any] = {
            "espn_event_id": event_id,
            "commence_time": date_iso,
            "state": state,
            "period": period,
            "display_clock": display_clock,
            "home": home,
            "away": away,
            "situation": situation,
        }

        # Append the normalized game record to the result list
        games.append(game)

    # Return the full list of normalized games
    return games


def normalize_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    /**
     * @brief Placeholder for summary normalization.
     *
     * @param raw  Raw ESPN JSON from fetch_summary(event_id).
     *
     * @return A dict that will eventually be a compact 'summary' schema.
     *
     * @details
     *   - Keep as-is for now so we can wire the fetch path.
     *   - Later, extract stable fields (e.g., leaders, team stats, drives snapshot).
     */
    """
    # Return the raw payload for now; to be refined later
    return raw or {}


def normalize_playbyplay(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    /**
     * @brief Placeholder for play-by-play normalization.
     *
     * @param raw  Raw ESPN JSON from fetch_playbyplay(event_id).
     *
     * @return A dict that will eventually be a compact 'pbp' schema.
     *
     * @details
     *   - Keep as-is for now so we can wire the fetch path.
     *   - Later, extract stable fields (e.g., current drive, last N plays, possession).
     */
    """
    # Return the raw payload for now; to be refined later
    return raw or {}


# =========================
# Optional Utility
# =========================

def compute_seconds_left(period: Optional[int], display_clock: Optional[str], state: Optional[str] = None,) -> Optional[int]:
    """
    /**
     * @brief Compute the number of regulation seconds remaining in the game.
     *
     * @param period          Quarter number (1..4 for regulation; OT handled as 0).
     * @param display_clock   "MM:SS" game clock string as returned by ESPN.
     * @param state           Game state ("pre", "in", "post", "halftime", etc.)
     *
     * @return Seconds left in regulation (0..3600), or None if unavailable.
     *
     * @details
     *   - NFL regulation = 4 x 15-minute quarters = 3600 total seconds.
     *   - Returns 3600 for pregame, 0 for postgame.
     *   - Returns 0 for halftime (treated as end of first half).
     *   - Gracefully parses "MM:SS" clock values during active play.
     *   - Keeps values bounded to [0, 3600] for safety.
     *   - This unified metric is used for model features and agent timing.
     */
    """

    # --- Handle game state first ---
    # Return full duration if pregame (no play yet)
    if state == "pre":
        return 3600

    # Return zero if game is over (post) or at halftime
    if state in ("post", "halftime"):
        return 0

    # If period or clock are missing, we can't compute remaining time
    if period is None or not display_clock:
        return None

    # --- Attempt to parse the "MM:SS" clock format safely ---
    try:
        # Split the clock into minutes and seconds
        mm_str, ss_str = display_clock.split(":")
        mm, ss = int(mm_str), int(ss_str)
    except Exception:
        # If parsing fails (e.g., display_clock="--:--"), return None
        return None

    # --- Compute base time values ---
    # Define total regulation seconds (4 quarters * 15 minutes)
    total_regulation_seconds: int = 4 * 15 * 60  # 3600 seconds

    # Compute seconds elapsed in the current quarter
    elapsed_in_q: int = (15 * 60) - (mm * 60 + ss)

    # Compute total seconds elapsed so far in regulation
    completed_quarters: int = max(0, (int(period) - 1))
    total_elapsed: int = (completed_quarters * 15 * 60) + elapsed_in_q

    # --- Compute and clamp remaining time ---
    # Calculate how many seconds remain in regulation
    seconds_left: int = total_regulation_seconds - total_elapsed

    # Clamp value to valid range [0, 3600]
    return max(0, min(seconds_left, total_regulation_seconds))