"""
@file        utils.py
@brief       Shared utility functions for BetAI Streamlit UI.
@details
  - Loads team logos by exact API team name (PNG format).
  - Provides graceful fallback if a logo file is missing.
  - Includes a small in-memory cache to avoid reloading the same images.
  - Provides general helper functions (e.g., safe key builder).
"""

# ============================================================
# Imports
# ============================================================

from __future__ import annotations               # Allow forward-declared type hints
import re                                        # Regex for safe key sanitization
from pathlib import Path                         # Path handling for local assets
from typing import Any, Dict, Optional           # Type hints for readability
from PIL import Image, ImageDraw, ImageFont      # Pillow for image loading and badge generation
import streamlit as st                           # Used for st.cache_data decorator (optional caching)


# ============================================================
# Module constants
# ============================================================

# Resolve the absolute path to the team-logos folder under Streamlit app assets
LOGO_DIR: Path = (Path(__file__).resolve().parent.parent / "assets" / "team-logos").resolve()

# Small in-memory logo cache to prevent reloading the same file multiple times
_LOGO_CACHE: Dict[str, Image.Image] = {}


# ============================================================
# Public API — load_team_logo_from_name
# ============================================================

def load_team_logo_from_name(team_name: str, size: int = 40) -> Optional[Image.Image]:
    """
    @brief Load a team logo image by its exact team name (case-sensitive match to file name).
    @details
      - Looks for a PNG file in assets/team-logos/ with the same name as team_name.
      - Example: "Detroit Lions" -> "assets/team-logos/Detroit Lions.png"
      - Returns a resized Pillow Image or a generated placeholder badge if missing.
    @param team_name The exact name of the team (matches API-provided string).
    @param size       Optional resize height in pixels (width auto-adjusted).
    @return Pillow Image instance or None if the file cannot be loaded.
    """

    # ------------------------------------------------------------
    # Defensive: if input missing or not a string, abort early
    # ------------------------------------------------------------
    if not isinstance(team_name, str) or not team_name.strip():
        return _create_placeholder_logo("?", size)

    # ------------------------------------------------------------
    # If this logo has already been loaded, return cached version
    # ------------------------------------------------------------
    if team_name in _LOGO_CACHE:
        return _LOGO_CACHE[team_name]

    # ------------------------------------------------------------
    # Build the expected file path (use exact team name + ".png")
    # ------------------------------------------------------------
    logo_path = LOGO_DIR / f"{team_name}.png"

    # ------------------------------------------------------------
    # Try to open and resize the image using Pillow
    # ------------------------------------------------------------
    if logo_path.exists():
        try:
            # Open the image file safely
            img = Image.open(logo_path)

            # Maintain aspect ratio when resizing
            w, h = img.size
            aspect = (w / h) if h else 1.0
            new_w = max(1, int(round(size * aspect)))
            img = img.resize((new_w, size))

            # Cache and return the loaded image
            _LOGO_CACHE[team_name] = img
            return img
        except Exception as exc:
            # Log warning (useful in Streamlit terminal)
            print(f"[WARN] Failed to load logo for {team_name}: {exc}")

    # ------------------------------------------------------------
    # If file not found or failed to open, create a fallback badge
    # ------------------------------------------------------------
    placeholder = _create_placeholder_logo(team_name, size)
    _LOGO_CACHE[team_name] = placeholder
    return placeholder


# ============================================================
# Internal helper — generate placeholder badge
# ============================================================

def _create_placeholder_logo(team_name: str, size: int) -> Image.Image:
    """
    @brief Generate a simple placeholder image with team initials.
    @param team_name The team name used to derive initials.
    @param size      Target image height in pixels.
    @return A Pillow Image containing the initials.
    """

    # Extract uppercase initials (first letters of each word)
    initials = "".join([word[0].upper() for word in team_name.split() if word]) or "?"

    # Create a blank RGBA image (gray background)
    img = Image.new("RGBA", (size, size), color=(200, 200, 200, 255))

    # Create a drawing context
    draw = ImageDraw.Draw(img)

    # Load a built-in default font (guaranteed to exist)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # ------------------------------------------------------------
    # Compute text width and height depending on Pillow version
    # ------------------------------------------------------------
    if hasattr(draw, "textbbox"):
        # Pillow ≥10 uses textbbox() -> returns (x0, y0, x1, y1)
        bbox = draw.textbbox((0, 0), initials, font=font)  # type: ignore[attr-defined]
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    else:
        # Older Pillow versions have textsize()
        text_w, text_h = draw.textsize(initials, font=font)  # type: ignore[attr-defined]

    # ------------------------------------------------------------
    # Compute text coordinates to roughly center the initials
    # ------------------------------------------------------------
    text_x = (size - text_w) / 2
    text_y = (size - text_h) / 2

    # ------------------------------------------------------------
    # Draw the initials text in black on gray background
    # ------------------------------------------------------------
    draw.text((text_x, text_y), initials, fill="black", font=font)

    # Return the final image
    return img


# ============================================================
# Public utility — make_safe_key
# ============================================================

def make_safe_key(*parts: Any) -> str:
    """
    @brief Build a safe, unique key by concatenating arbitrary parts.
    @details
      - Converts parts to strings and joins them with underscores.
      - Replaces characters outside [A-Za-z0-9_.-] with underscores.
      - Can be used anywhere unique widget keys or IDs are needed.
    @param parts Arbitrary values to concatenate.
    @return A safe string suitable for Streamlit keys or filenames.
    """

    # Join all parts into a single string separated by underscores
    raw = "_".join(str(p) for p in parts)

    # Replace unsafe characters with underscores
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", raw)

    # Return the sanitized result
    return safe


# ============================================================
# Optional caching decorator for data functions
# ============================================================

@st.cache_data(show_spinner=False)
def cached_read_image(path: Path) -> Optional[Image.Image]:
    """
    @brief Cached image reader — useful if you call load_team_logo_from_name() outside this module.
    @param path Path to an image file.
    @return Pillow Image or None if load fails.
    """
    try:
        # Open image and return as Pillow object
        return Image.open(path)
    except Exception:
        # Return None gracefully on failure
        return None