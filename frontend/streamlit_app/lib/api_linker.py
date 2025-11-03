# frontend/streamlit_app/lib/api_linker.py
from __future__ import annotations
from typing import Dict, List, Any

def build_api_link_map(espn_games: List[Dict[str, Any]], odds_events: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    @brief Create a mapping between ESPN event IDs and OddsAPI game IDs.
    @details
      - Matches purely by team names (exact match).
      - Returns { espn_event_id -> odds_game_id }.
    """
    link_map: Dict[str, str] = {}

    # Quick index: (away_name, home_name) -> game_id for OddsAPI
    odds_index: Dict[tuple[str, str], str] = {}
    for ev in odds_events or []:
        away = ev.get("away") or ev.get("away_team")
        home = ev.get("home") or ev.get("home_team")
        gid  = ev.get("game_id")
        if away and home and gid:
            odds_index[(away.strip().lower(), home.strip().lower())] = gid

    # Now match ESPN → OddsAPI
    for g in espn_games or []:
        eid = g.get("espn_event_id")
        away = (g.get("away") or {}).get("name", "").strip().lower()
        home = (g.get("home") or {}).get("name", "").strip().lower()
        if not eid or not away or not home:
            continue
        gid = odds_index.get((away, home))
        if gid:
            link_map[eid] = gid

    return link_map