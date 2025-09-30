# Streamlit application that calls out to agent

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from agent import BettingAgent
import numpy as np

# Page configuration
st.set_page_config(
    page_title="BetAI - Football Betting Agent",
    page_icon="⚽",
    layout="wide"
)

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = BettingAgent(initial_bankroll=1000.0)
    
if 'match_results' not in st.session_state:
    st.session_state.match_results = []

# Title and description
st.title("⚽ BetAI - Football Betting Agent Dashboard")
st.markdown("### AI-Powered Sports Betting Analysis with Paper Trading")

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    initial_bankroll = st.number_input(
        "Initial Bankroll ($)",
        min_value=100.0,
        max_value=10000.0,
        value=1000.0,
        step=100.0
    )
    
    kelly_fraction = st.slider(
        "Kelly Fraction",
        min_value=0.1,
        max_value=1.0,
        value=0.25,
        step=0.05,
        help="Fraction of Kelly criterion to use (lower = more conservative)"
    )
    
    ev_threshold = st.slider(
        "EV Threshold (%)",
        min_value=0.0,
        max_value=20.0,
        value=5.0,
        step=1.0,
        help="Minimum expected value to recommend a bet"
    )
    
    if st.button("🔄 Reset Bankroll"):
        st.session_state.agent = BettingAgent(initial_bankroll=initial_bankroll, kelly_fraction=kelly_fraction)
        st.session_state.match_results = []
        st.success("Bankroll reset!")
        st.rerun()

# Main dashboard layout
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📊 Live Match Analysis")
    
    # Match input section
    with st.expander("📥 Enter Match Details", expanded=True):
        match_col1, match_col2 = st.columns(2)
        
        with match_col1:
            home_team = st.text_input("Home Team", value="Team A")
            home_advantage = st.slider("Home Advantage", -1.0, 1.0, 0.3, 0.1)
        
        with match_col2:
            away_team = st.text_input("Away Team", value="Team B")
            recent_form = st.slider("Recent Form", -1.0, 1.0, 0.2, 0.1)
        
        odds = st.number_input("Decimal Odds", min_value=1.01, max_value=20.0, value=2.5, step=0.1)
        
        if st.button("🔮 Get Prediction", use_container_width=True):
            match_features = {
                'home_advantage': home_advantage,
                'recent_form': recent_form
            }
            
            recommendation = st.session_state.agent.make_recommendation(
                match_features, 
                odds, 
                ev_threshold
            )
            
            st.session_state.current_recommendation = recommendation
            st.session_state.current_match = {
                'home_team': home_team,
                'away_team': away_team,
                'odds': odds
            }
    
    # Display recommendation
    if 'current_recommendation' in st.session_state:
        st.subheader("💡 Recommendation")
        rec = st.session_state.current_recommendation
        
        # Action indicator
        if rec['action'] == 'BET':
            st.success(f"### ✅ {rec['action']}")
        else:
            st.warning(f"### ❌ {rec['action']}")
        
        # Metrics display
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            st.metric("Model Probability", f"{rec['model_probability']:.1%}")
        
        with metric_col2:
            st.metric("Implied Odds Prob", f"{rec['implied_probability']:.1%}")
        
        with metric_col3:
            ev_color = "green" if rec['expected_value'] > 0 else "red"
            st.metric("Expected Value", f"{rec['expected_value']:.2f}%")
        
        with metric_col4:
            st.metric("Confidence", f"{rec['confidence']:.1%}")
        
        # Additional details
        detail_col1, detail_col2 = st.columns(2)
        
        with detail_col1:
            st.info(f"**Recommended Stake:** ${rec['stake']:.2f}")
        
        with detail_col2:
            st.info(f"**Model Used:** {rec['model_used']}")
        
        # Probability comparison chart
        st.subheader("📈 Probability Comparison")
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=['Model Prediction', 'Implied by Odds'],
            y=[rec['model_probability'], rec['implied_probability']],
            marker_color=['#1f77b4', '#ff7f0e'],
            text=[f"{rec['model_probability']:.1%}", f"{rec['implied_probability']:.1%}"],
            textposition='auto',
        ))
        fig.update_layout(
            yaxis_title="Probability",
            yaxis_range=[0, 1],
            showlegend=False,
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Simulate bet result
        st.subheader("🎲 Simulate Bet Result")
        
        sim_col1, sim_col2 = st.columns(2)
        
        with sim_col1:
            if st.button("✅ Mark as WON", use_container_width=True):
                if rec['stake'] > 0:
                    st.session_state.agent.place_paper_bet(rec['stake'], st.session_state.current_match['odds'], True)
                    st.session_state.match_results.append({
                        'home_team': st.session_state.current_match['home_team'],
                        'away_team': st.session_state.current_match['away_team'],
                        'stake': rec['stake'],
                        'odds': st.session_state.current_match['odds'],
                        'result': 'Won',
                        'profit': rec['stake'] * (st.session_state.current_match['odds'] - 1)
                    })
                    st.success("Bet marked as won!")
                    st.rerun()
        
        with sim_col2:
            if st.button("❌ Mark as LOST", use_container_width=True):
                if rec['stake'] > 0:
                    st.session_state.agent.place_paper_bet(rec['stake'], st.session_state.current_match['odds'], False)
                    st.session_state.match_results.append({
                        'home_team': st.session_state.current_match['home_team'],
                        'away_team': st.session_state.current_match['away_team'],
                        'stake': rec['stake'],
                        'odds': st.session_state.current_match['odds'],
                        'result': 'Lost',
                        'profit': -rec['stake']
                    })
                    st.warning("Bet marked as lost!")
                    st.rerun()

with col2:
    st.header("💰 Paper Trading Performance")
    
    # Current bankroll
    stats = st.session_state.agent.get_performance_stats()
    
    bankroll_change = stats['current_bankroll'] - initial_bankroll
    bankroll_pct = (bankroll_change / initial_bankroll * 100) if initial_bankroll > 0 else 0
    
    st.metric(
        "Current Bankroll",
        f"${stats['current_bankroll']:.2f}",
        f"{bankroll_change:+.2f} ({bankroll_pct:+.1f}%)"
    )
    
    # Performance metrics
    st.subheader("📈 Statistics")
    
    st.metric("Total Bets", stats['total_bets'])
    st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    st.metric("Total Profit", f"${stats['total_profit']:.2f}")
    st.metric("ROI", f"{stats['roi']:.2f}%")
    
    # Quick info
    with st.expander("ℹ️ How It Works"):
        st.markdown("""
        **BetAI** uses machine learning models to predict football match outcomes:
        
        1. **Model Selection**: Agent selects from Logistic Regression, Naive Bayes, or Random Forest
        2. **Probability Prediction**: Models predict win probability based on match features
        3. **Expected Value**: Calculates EV by comparing model probability to bookmaker odds
        4. **Kelly Criterion**: Determines optimal stake size based on edge and bankroll
        5. **Paper Trading**: Simulates betting without real money to track performance
        
        **Actions:**
        - ✅ **BET**: When EV exceeds threshold
        - ❌ **NO BET**: When edge is insufficient
        """)

# Bottom section - Full width
st.header("📊 Performance Dashboard")

tab1, tab2 = st.tabs(["💹 Bankroll Curve", "📋 Bet History"])

with tab1:
    if st.session_state.agent.bet_history:
        # Create bankroll curve
        bankroll_data = pd.DataFrame(st.session_state.agent.bet_history)
        bankroll_data['bet_number'] = range(1, len(bankroll_data) + 1)
        
        fig = px.line(
            bankroll_data, 
            x='bet_number', 
            y='bankroll',
            title='Bankroll Evolution Over Time',
            labels={'bet_number': 'Bet Number', 'bankroll': 'Bankroll ($)'}
        )
        fig.add_hline(y=initial_bankroll, line_dash="dash", line_color="gray", 
                      annotation_text="Initial Bankroll")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Additional performance charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Profit distribution
            fig_profit = px.histogram(
                bankroll_data,
                x='profit',
                title='Profit Distribution per Bet',
                labels={'profit': 'Profit ($)', 'count': 'Frequency'},
                nbins=20
            )
            fig_profit.update_layout(height=300)
            st.plotly_chart(fig_profit, use_container_width=True)
        
        with col2:
            # Win/Loss pie chart
            results = bankroll_data['won'].value_counts()
            fig_pie = px.pie(
                values=results.values,
                names=['Won' if x else 'Lost' for x in results.index],
                title='Win/Loss Distribution',
                color_discrete_map={'Won': '#00CC96', 'Lost': '#EF553B'}
            )
            fig_pie.update_layout(height=300)
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("📊 No bets placed yet. Start analyzing matches to see your bankroll curve!")

with tab2:
    if st.session_state.match_results:
        df = pd.DataFrame(st.session_state.match_results)
        df['match'] = df['home_team'] + ' vs ' + df['away_team']
        
        # Format for display
        display_df = df[['match', 'stake', 'odds', 'result', 'profit']].copy()
        display_df['stake'] = display_df['stake'].apply(lambda x: f"${x:.2f}")
        display_df['odds'] = display_df['odds'].apply(lambda x: f"{x:.2f}")
        display_df['profit'] = display_df['profit'].apply(lambda x: f"${x:.2f}")
        display_df.columns = ['Match', 'Stake', 'Odds', 'Result', 'Profit/Loss']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Summary statistics
        st.subheader("📈 Summary Statistics")
        
        total_staked = df['stake'].sum()
        total_profit = df['profit'].sum()
        avg_odds = df['odds'].mean()
        
        sum_col1, sum_col2, sum_col3 = st.columns(3)
        
        with sum_col1:
            st.metric("Total Staked", f"${total_staked:.2f}")
        
        with sum_col2:
            st.metric("Net Profit/Loss", f"${total_profit:.2f}")
        
        with sum_col3:
            st.metric("Avg Odds", f"{avg_odds:.2f}")
    else:
        st.info("📋 No bet history yet. Simulate some bets to see your history!")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "BetAI - Educational Paper Trading Only | "
    "Not Real Money Betting | "
    "© 2025 Groberg, Miller, Velez Ramirez"
    "</div>",
    unsafe_allow_html=True
)
