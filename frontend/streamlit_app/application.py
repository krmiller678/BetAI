# Streamlit application for OddsAPI SDK integration

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from betai.agents.agent_v1 import BettingAgent
import numpy as np
import sys
import os
from datetime import datetime, timedelta

# Add the odds-sdk to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "odds-sdk", "src"))

# Cache configuration
SPORTS_CACHE_DURATION_MINUTES = 60  # Cache sports for 1 hour


def get_sports_with_cache(odds_client, force_refresh=False):
    """
    Get sports list with caching. Returns cached data if available and not expired,
    otherwise fetches from API and caches the result.

    Args:
        odds_client: The OddsAPIClient instance
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of Sport objects
    """
    current_time = datetime.now()

    # Check if we have valid cached data
    if (
        not force_refresh
        and st.session_state.cached_sports is not None
        and st.session_state.sports_cache_timestamp is not None
    ):
        # Check if cache is still valid (not expired)
        cache_age = current_time - st.session_state.sports_cache_timestamp
        if cache_age < timedelta(minutes=SPORTS_CACHE_DURATION_MINUTES):
            return st.session_state.cached_sports

    # Cache is empty or expired, fetch from API
    sports = odds_client.get_sports(active_only=True)

    # Cache the results
    st.session_state.cached_sports = sports
    st.session_state.sports_cache_timestamp = current_time

    return sports


# Page configuration
st.set_page_config(
    page_title="BetAI - Live Odds Dashboard", page_icon="🤖", layout="wide"
)

# Initialize session state
if "odds_client" not in st.session_state:
    st.session_state.odds_client = None
if "selected_sport" not in st.session_state:
    st.session_state.selected_sport = None
if "live_odds" not in st.session_state:
    st.session_state.live_odds = []
if "selected_region" not in st.session_state:
    st.session_state.selected_region = None
if "selected_format" not in st.session_state:
    st.session_state.selected_format = None
if "cached_sports" not in st.session_state:
    st.session_state.cached_sports = None
if "sports_cache_timestamp" not in st.session_state:
    st.session_state.sports_cache_timestamp = None

# Title and description
st.title("🤖 BetAI - Live Odds Dashboard")
st.markdown("### Real-time Sports Betting Odds from Multiple Bookmakers")
st.markdown("---")

# Sidebar for configuration
with st.sidebar:
    st.header("Configuration")

    # API Key input
    api_key = st.text_input(
        "Odds API Key",
        type="password",
        help="Get your free API key from https://the-odds-api.com/",
    )

    if api_key and api_key != "your-api-key-here":
        try:
            from oddsapi import OddsAPIClient, Region, Market, OddsFormat

            if st.session_state.odds_client is None:
                st.session_state.odds_client = OddsAPIClient(api_key=api_key)
                # Clear cache when connecting with new API key
                st.session_state.cached_sports = None
                st.session_state.sports_cache_timestamp = None
                st.success("✅ Connected to Odds API!")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
            st.session_state.odds_client = None
    else:
        st.info("👆 Enter your API key to get started")
        st.session_state.odds_client = None

    # Region selection
    if st.session_state.odds_client:
        st.subheader("Region")
        region_options = {
            "US": Region.US,
            "UK": Region.UK,
            "Australia": Region.AU,
            "Europe": Region.EU,
        }
        selected_region = st.selectbox("Select Region", list(region_options.keys()))
        st.session_state.selected_region = region_options[selected_region]

        # Odds format selection
        st.subheader("Odds Format")
        odds_format_options = {
            "American": OddsFormat.AMERICAN,
            "Decimal": OddsFormat.DECIMAL,
        }
        selected_format = st.selectbox(
            "Select Format", list(odds_format_options.keys()), index=0
        )
        st.session_state.selected_format = odds_format_options[selected_format]


# Main content area
if (
    st.session_state.odds_client
    and st.session_state.selected_region
    and st.session_state.selected_format
):
    try:
        # Get available sports
        with st.spinner("Loading available sports..."):
            sports = get_sports_with_cache(st.session_state.odds_client)

        # Sport selection
        st.markdown("---")
        st.subheader("Select Sport")

        # Create sport options with better names
        sport_options = {}

        for sport in sports:
            if sport.active:
                # Create a better display name
                display_name = sport.title
                if sport.group:
                    display_name = f"{sport.title} ({sport.group})"

                sport_options[display_name] = sport.key

        # Check if we have any sports loaded
        if not sport_options:
            st.warning(
                "⚠️ No active sports found. Please check your API key and region settings."
            )
            st.stop()

        # Sort sports alphabetically by display name
        sorted_sports = sorted(sport_options.keys())

        nfl_index = 0
        for i, sport in enumerate(sorted_sports):
            if (
                "NFL" in sport
                or "American Football" in sport
                or "americanfootball_nfl" in sport_options.get(sport, "")
            ):
                nfl_index = i
                break

        # Create sports selection row with dropdown and refresh button
        col1, col2 = st.columns([4, 1])

        with col1:
            selected_sport_display = st.selectbox(
                "Choose a sport:",
                sorted_sports,
                index=nfl_index,
                help="Select a sport to view live odds",
                label_visibility="collapsed",
            )

        with col2:
            if st.button("Refresh", help="Refresh live odds", use_container_width=True):
                if st.session_state.selected_sport:
                    with st.spinner("Fetching live odds..."):
                        try:
                            live_odds = st.session_state.odds_client.get_odds(
                                sport_key=st.session_state.selected_sport,
                                regions=[st.session_state.selected_region],
                                markets=[Market.H2H, Market.SPREADS, Market.TOTALS],
                                odds_format=st.session_state.selected_format,
                            )
                            st.session_state.live_odds = live_odds
                        except Exception as e:
                            st.error(f"❌ Failed to fetch odds: {e}")
                            st.session_state.live_odds = []
                    st.rerun()

        st.markdown("---")

        # Set the selected sport when dropdown changes
        if selected_sport_display:
            new_sport_key = sport_options[selected_sport_display]

            # Check if sport has changed and clear existing odds
            if st.session_state.selected_sport != new_sport_key:
                st.session_state.selected_sport = new_sport_key
                st.session_state.live_odds = []  # Clear existing odds
                st.rerun()

        # Set the sport key for processing
        if st.session_state.selected_sport:
            new_sport_key = st.session_state.selected_sport

            # Auto-fetch odds when sport is selected (if no odds exist)
            if not st.session_state.live_odds:
                with st.spinner("Fetching live odds..."):
                    try:
                        live_odds = st.session_state.odds_client.get_odds(
                            sport_key=st.session_state.selected_sport,
                            regions=[st.session_state.selected_region],
                            markets=[Market.H2H, Market.SPREADS, Market.TOTALS],
                            odds_format=st.session_state.selected_format,
                        )
                        st.session_state.live_odds = live_odds
                    except Exception as e:
                        st.error(f"❌ Failed to fetch odds: {e}")
                        st.session_state.live_odds = []

        # Display live odds
        if st.session_state.live_odds:
            # Get the display name for the selected sport
            selected_display_name = None
            for display_name, sport_key in sport_options.items():
                if sport_key == st.session_state.selected_sport:
                    selected_display_name = display_name
                    break

            sport_title = selected_display_name or "Selected Sport"
            st.header(f"Live {sport_title} Odds")

            # Region and format info with better spacing
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.markdown(
                    f"<div style='text-align: center; margin: 10px 0;'>"
                    f"<strong>Region:</strong> {selected_region} | <strong>Format:</strong> {selected_format}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Show events
            for i, event in enumerate(st.session_state.live_odds):
                with st.expander(
                    f"🏟️ {event.home_team} vs {event.away_team}", expanded=i < 1
                ):
                    # Event info with better alignment
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.markdown(
                            f"**Start Time:** {event.commence_time.strftime('%Y-%m-%d %H:%M UTC')}"
                        )
                    with col2:
                        st.markdown(f"**Sport:** {event.sport_title}")
                    with col3:
                        st.markdown(f"**Bookmakers:** {len(event.bookmakers)}")

                    st.markdown("---")

                    # Show odds from each bookmaker
                    for bookmaker in event.bookmakers:
                        st.subheader(f"{bookmaker.title}")

                        # Create columns for the three main markets
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown("### **Head-to-Head (Moneyline)**")
                            h2h_market = next(
                                (m for m in bookmaker.markets if m.key == "h2h"), None
                            )
                            if h2h_market:
                                for outcome in h2h_market.outcomes:
                                    st.write(f"**{outcome.name}:** {outcome.price}")
                            else:
                                st.write("No moneyline odds available")

                        with col2:
                            st.markdown("### **Point Spreads (Handicap)**")
                            spreads_market = next(
                                (m for m in bookmaker.markets if m.key == "spreads"),
                                None,
                            )
                            if spreads_market:
                                for outcome in spreads_market.outcomes:
                                    point_display = (
                                        f"{outcome.point:+.1f}"
                                        if outcome.point
                                        else "N/A"
                                    )
                                    st.write(
                                        f"**{outcome.name} {point_display}:** {outcome.price}"
                                    )
                            else:
                                st.write("No spread odds available")

                        with col3:
                            st.markdown("### **Totals (Over/Under)**")
                            totals_market = next(
                                (m for m in bookmaker.markets if m.key == "totals"),
                                None,
                            )
                            if totals_market:
                                for outcome in totals_market.outcomes:
                                    point_display = (
                                        f"{outcome.point:.1f}"
                                        if outcome.point
                                        else "N/A"
                                    )
                                    st.write(
                                        f"**{outcome.name} {point_display}:** {outcome.price}"
                                    )
                            else:
                                st.write("No totals odds available")

                        st.markdown("---")

                    # Best odds comparison
                    st.subheader("Best Odds Comparison")

                    # Find best odds for each market
                    best_odds = {
                        "h2h": {"odds": 0, "bookmaker": "", "outcome": ""},
                        "spreads": {
                            "odds": 0,
                            "bookmaker": "",
                            "outcome": "",
                            "point": 0,
                        },
                        "totals": {
                            "odds": 0,
                            "bookmaker": "",
                            "outcome": "",
                            "point": 0,
                        },
                    }

                    for bookmaker in event.bookmakers:
                        for market in bookmaker.markets:
                            if market.key in best_odds:
                                for outcome in market.outcomes:
                                    if outcome.price > best_odds[market.key]["odds"]:
                                        best_odds[market.key]["odds"] = outcome.price
                                        best_odds[market.key]["bookmaker"] = (
                                            bookmaker.title
                                        )
                                        best_odds[market.key]["outcome"] = outcome.name
                                        if outcome.point is not None:
                                            best_odds[market.key]["point"] = (
                                                outcome.point
                                            )

                    # Display best odds
                    best_col1, best_col2, best_col3 = st.columns(3)

                    with best_col1:
                        if best_odds["h2h"]["odds"] > 0:
                            st.success(
                                f"**Best Moneyline:** {best_odds['h2h']['outcome']} {best_odds['h2h']['odds']} @ {best_odds['h2h']['bookmaker']}"
                            )

                    with best_col2:
                        if best_odds["spreads"]["odds"] > 0:
                            point_display = f"{best_odds['spreads']['point']:+.1f}"
                            st.success(
                                f"**Best Spread:** {best_odds['spreads']['outcome']} {point_display} {best_odds['spreads']['odds']} @ {best_odds['spreads']['bookmaker']}"
                            )

                    with best_col3:
                        if best_odds["totals"]["odds"] > 0:
                            point_display = f"{best_odds['totals']['point']:.1f}"
                            st.success(
                                f"**Best Total:** {best_odds['totals']['outcome']} {point_display} {best_odds['totals']['odds']} @ {best_odds['totals']['bookmaker']}"
                            )

        else:
            st.info("👆 Click 'Refresh' to fetch current odds for the selected sport")

    except Exception as e:
        st.error(f"❌ Error loading sports: {e}")
        st.info("Please check your API key and try again")

elif st.session_state.odds_client:
    st.info("👆 Please select a region and odds format in the sidebar to view sports")
else:
    # Welcome screen
    st.markdown("""

    ### **Getting Started:**
    1. Get your free API key from [The Odds API](https://the-odds-api.com/)
    2. Enter your API key in the sidebar
    3. Select your preferred region (odds format defaults to American)
    4. Choose a sport and click "Refresh" to load odds
    5. View live odds from multiple bookmakers

    ### **Supported Markets:**
    - **Head-to-Head (H2H)**: Direct win/loss betting
    - **Spreads**: Handicap betting with point spreads
    - **Totals**: Over/under betting on total points/goals

    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "BetAI - Live Odds Dashboard | "
    "Powered by The Odds API | "
    "(c) 2025 Groberg, Miller, Velez Ramirez"
    "</div>",
    unsafe_allow_html=True,
)
