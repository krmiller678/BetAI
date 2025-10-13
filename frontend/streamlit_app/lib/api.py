"""
@file        api.py
@brief       Thin API wrappers for BetAI UI.
@details
  - Centralizes calls into betai.integrations (The Odds API provider).
  - Exposes a stable, UI-friendly surface for fetching odds and scores.
  - Handles provider construction once and reuses it across calls.
  - Avoids Streamlit imports to keep this layer framework-agnostic.
"""

# ============================================================
# Imports (inline comments for clarity)
# ============================================================

from __future__ import annotations                  # Enable postponed type hints for cleaner signatures
from typing import Any, Dict, List                  # Precise type hints for collections and records

# Import the odds provider and event normalizer from your integrations layer
from betai.integrations.odds_api import (          # Provider + helpers maintained in backend/core/betai/integrations/
    TheOddsAPIProvider,                            # Concrete provider for The Odds API
    normalize_events,                              # Function to normalize raw provider events to internal schema
    normalize_scores,                              # Function to normalize raw provider scores to internal schema
)

# ============================================================
# Module-level Provider (simple singleton)
# ============================================================

# Declare a module-scoped cache for the provider instance (created on first use)
PROVIDER: TheOddsAPIProvider | None = None


def get_provider() -> TheOddsAPIProvider:
    """
    @brief Return a shared TheOddsAPIProvider instance (create on first use).
    @details
      - Reads required config (e.g., ODDS_API_KEY) from environment internally (provider responsibility).
      - Keeps UI thin by hiding provider construction details.
    @return A ready-to-use TheOddsAPIProvider.
    """
    # Use the cached provider if already created
    global PROVIDER                           # Declare we are using the module-scoped variable

    # If no provider exists yet, construct one now
    if PROVIDER is None:
        # Create a new provider instance (may raise if env/config invalid)
        PROVIDER = TheOddsAPIProvider()

    # Return the cached provider
    return PROVIDER


# ============================================================
# Public API — Odds (markets) fetch
# ============================================================

def fetch_and_normalize_events(*, sport_key: str, regions: str, markets: str) -> List[Dict[str, Any]]:
    """
    @brief Fetch events/markets from The Odds API and normalize to internal schema.
    @param sport_key The Odds API sport key (e.g., "americanfootball_nfl").
    @param regions   Comma-separated bookmaker regions (e.g., "us").
    @param markets   Comma-separated markets to include (e.g., "h2h,spreads,totals").
    @return List of normalized event dictionaries suitable for UI consumption.
    @throws RuntimeError If the provider call fails or returns an unexpected payload.
    """
    # Obtain the shared provider instance
    prov = get_provider()

    # Perform the raw fetch from the provider (may raise provider-specific exceptions)
    raw = prov.fetch_markets(
        sport_key=sport_key,     # Pass through sport key
        regions=regions,         # Pass through target regions
        markets=markets,         # Pass through requested markets
    )

    # Normalize raw payload into the app's stable event shape
    events = normalize_events(raw)

    # Return the normalized list (empty list is valid if no events available)
    return events


# ============================================================
# Public API — Scores fetch (optional, prepared for Live Board wiring)
# ============================================================

def fetch_scores(*, sport_key: str, days_from: int | None = None) -> List[Dict[str, Any]]:
    """
    @brief Fetch recent/ongoing game scores and normalize to internal schema.
    @details
      - Thin wrapper over provider.fetch_scores() + normalize_scores().
      - UI can render period-by-period later if needed; for now we track totals.
    @param sport_key  The Odds API sport key (e.g., "americanfootball_nfl").
    @param days_from  Optional lookback window in days (small positive int).
    @return List of normalized score records:
            [
              {
                "game_id": str,
                "commence_time": str,   # ISO
                "completed": bool,
                "home": str,
                "away": str,
                "home_score": Optional[int],
                "away_score": Optional[int],
                "last_update": Optional[str],
              },
              ...
            ]
    """
    # Obtain a shared provider instance
    prov = get_provider()

    # Fetch raw scores from the provider (provider returns vendor-shaped payload)
    raw_scores = prov.fetch_scores(
        sport_key=sport_key,     # e.g. "americanfootball_nfl"
        days_from=days_from,     # optional lookback
        date_format="iso",       # we prefer iso timestamps for readability
    )

    # Normalize to our compact, internal score shape
    return normalize_scores(raw_scores)