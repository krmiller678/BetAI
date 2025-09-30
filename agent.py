# Agent that is called out to by application.py and selects from the models at inference time

import numpy as np
from typing import Dict, List, Tuple, Optional
import random


class BettingAgent:
    """
    Agent that selects from a pool of trained models to predict outcomes
    and manages paper trading.
    """
    
    def __init__(self, initial_bankroll: float = 1000.0, kelly_fraction: float = 0.25):
        """
        Initialize the betting agent.
        
        Args:
            initial_bankroll: Starting bankroll for paper trading
            kelly_fraction: Fraction of Kelly criterion to use for stake sizing
        """
        self.initial_bankroll = initial_bankroll
        self.bankroll = initial_bankroll
        self.kelly_fraction = kelly_fraction
        self.bet_history = []
        self.models = ['logistic_regression', 'naive_bayes', 'random_forest']
        
    def select_model(self) -> str:
        """
        Select a model from the pool for prediction.
        For now, uses simple random selection.
        """
        return random.choice(self.models)
    
    def predict_probability(self, match_features: Dict) -> Tuple[float, str]:
        """
        Predict win probability for a match using selected model.
        
        Args:
            match_features: Dictionary containing match features
            
        Returns:
            Tuple of (probability, model_name)
        """
        model_name = self.select_model()
        
        # Simulate model prediction - in real implementation, this would call actual models
        # Using simplified simulation based on mock features
        base_prob = 0.5
        if 'home_advantage' in match_features:
            base_prob += match_features['home_advantage'] * 0.1
        if 'recent_form' in match_features:
            base_prob += match_features['recent_form'] * 0.15
            
        # Add model-specific variation
        if model_name == 'logistic_regression':
            probability = np.clip(base_prob + np.random.normal(0, 0.05), 0.1, 0.9)
        elif model_name == 'naive_bayes':
            probability = np.clip(base_prob + np.random.normal(0, 0.08), 0.1, 0.9)
        else:  # random_forest
            probability = np.clip(base_prob + np.random.normal(0, 0.06), 0.1, 0.9)
            
        return probability, model_name
    
    def calculate_expected_value(self, model_prob: float, odds: float) -> float:
        """
        Calculate expected value of a bet.
        
        Args:
            model_prob: Model's predicted probability
            odds: Decimal odds offered
            
        Returns:
            Expected value as a percentage
        """
        implied_prob = 1 / odds
        ev = (model_prob * odds) - 1
        return ev * 100
    
    def calculate_kelly_stake(self, model_prob: float, odds: float) -> float:
        """
        Calculate optimal stake size using Kelly criterion.
        
        Args:
            model_prob: Model's predicted probability
            odds: Decimal odds offered
            
        Returns:
            Stake amount
        """
        # Kelly formula: f = (bp - q) / b
        # where b = odds - 1, p = probability, q = 1 - p
        b = odds - 1
        p = model_prob
        q = 1 - p
        
        kelly = (b * p - q) / b
        kelly = max(0, kelly)  # No negative stakes
        
        # Apply fractional Kelly for safety
        stake = self.bankroll * kelly * self.kelly_fraction
        
        # Cap stake at reasonable percentage of bankroll
        max_stake = self.bankroll * 0.1
        stake = min(stake, max_stake)
        
        return round(stake, 2)
    
    def make_recommendation(self, match_features: Dict, odds: float, 
                          ev_threshold: float = 5.0) -> Dict:
        """
        Make a betting recommendation based on model prediction and odds.
        
        Args:
            match_features: Dictionary containing match features
            odds: Decimal odds offered
            ev_threshold: Minimum expected value percentage to recommend bet
            
        Returns:
            Dictionary containing recommendation details
        """
        model_prob, model_name = self.predict_probability(match_features)
        ev = self.calculate_expected_value(model_prob, odds)
        
        should_bet = ev > ev_threshold
        stake = self.calculate_kelly_stake(model_prob, odds) if should_bet else 0
        
        confidence = min(abs(ev) / 10, 1.0)  # Normalize to 0-1
        
        return {
            'action': 'BET' if should_bet else 'NO BET',
            'model_probability': round(model_prob, 3),
            'implied_probability': round(1/odds, 3),
            'expected_value': round(ev, 2),
            'confidence': round(confidence, 3),
            'stake': stake,
            'model_used': model_name,
            'current_bankroll': round(self.bankroll, 2)
        }
    
    def place_paper_bet(self, stake: float, odds: float, won: bool):
        """
        Record a paper trade bet result.
        
        Args:
            stake: Amount bet
            odds: Decimal odds
            won: Whether the bet won
        """
        if won:
            profit = stake * (odds - 1)
            self.bankroll += profit
        else:
            self.bankroll -= stake
            
        self.bet_history.append({
            'stake': stake,
            'odds': odds,
            'won': won,
            'profit': stake * (odds - 1) if won else -stake,
            'bankroll': self.bankroll
        })
    
    def get_performance_stats(self) -> Dict:
        """
        Calculate performance statistics for paper trading.
        
        Returns:
            Dictionary containing performance metrics
        """
        if not self.bet_history:
            return {
                'total_bets': 0,
                'win_rate': 0.0,
                'total_profit': 0.0,
                'roi': 0.0,
                'current_bankroll': self.bankroll
            }
        
        total_bets = len(self.bet_history)
        wins = sum(1 for bet in self.bet_history if bet['won'])
        total_staked = sum(bet['stake'] for bet in self.bet_history)
        total_profit = self.bankroll - self.initial_bankroll
        
        return {
            'total_bets': total_bets,
            'win_rate': round(wins / total_bets * 100, 2) if total_bets > 0 else 0.0,
            'total_profit': round(total_profit, 2),
            'roi': round(total_profit / self.initial_bankroll * 100, 2) if self.initial_bankroll > 0 else 0.0,
            'current_bankroll': round(self.bankroll, 2),
            'total_staked': round(total_staked, 2)
        }
    
    def reset_bankroll(self):
        """Reset bankroll and betting history."""
        self.bankroll = self.initial_bankroll
        self.bet_history = []
