"""
Swing Bot Monte Carlo Model
=============================

This module provides Monte Carlo simulation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result data structure."""
    timestamp: datetime
    iterations: int
    mean_return: float
    std_return: float
    var_95: float
    var_99: float
    expected_shortfall_95: float
    expected_shortfall_99: float
    max_drawdown: float
    probability_loss: float
    probability_profit: float
    confidence_interval_95: Tuple[float, float]
    confidence_interval_99: Tuple[float, float]
    best_case: float
    worst_case: float
    median_return: float


@dataclass
class MonteCarloSignal:
    """Monte Carlo trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    simulation: MonteCarloResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class MonteCarloModel:
    """
    Monte Carlo simulation model for risk analysis.
    
    Implements Monte Carlo simulations for price forecasting and risk assessment.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Monte Carlo model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.default_iterations = self.config.get('default_iterations', 10000)
        self.time_horizon = self.config.get('time_horizon', 252)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.simulations: List[MonteCarloResult] = []
        
    def simulate(self, returns: np.ndarray, iterations: Optional[int] = None) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Args:
            returns: Returns array
            iterations: Number of iterations
            
        Returns:
            MonteCarloResult object
        """
        if len(returns) < 2:
            return self._get_default_result()
        
        iterations = iterations or self.default_iterations
        
        # Calculate parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Generate simulated paths
        simulated_returns = np.random.normal(mean_return, std_return, (iterations, self.time_horizon))
        
        # Calculate cumulative returns
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        final_returns = cumulative_returns[:, -1] - 1
        
        # Calculate metrics
        mean_final_return = np.mean(final_returns)
        std_final_return = np.std(final_returns)
        median_return = np.median(final_returns)
        
        # Calculate VaR
        var_95 = np.percentile(final_returns, 5)
        var_99 = np.percentile(final_returns, 1)
        
        # Calculate Expected Shortfall
        tail_returns_95 = final_returns[final_returns <= var_95]
        expected_shortfall_95 = np.mean(tail_returns_95) if len(tail_returns_95) > 0 else var_95
        
        tail_returns_99 = final_returns[final_returns <= var_99]
        expected_shortfall_99 = np.mean(tail_returns_99) if len(tail_returns_99) > 0 else var_99
        
        # Calculate max drawdown
        max_drawdowns = []
        for path in cumulative_returns:
            drawdown = (path - np.maximum.accumulate(path)) / np.maximum.accumulate(path)
            max_drawdowns.append(np.min(drawdown))
        max_drawdown = np.mean(max_drawdowns)
        
        # Calculate probabilities
        probability_loss = np.mean(final_returns < 0)
        probability_profit = np.mean(final_returns > 0)
        
        # Calculate confidence intervals
        ci_95_lower = np.percentile(final_returns, 2.5)
        ci_95_upper = np.percentile(final_returns, 97.5)
        ci_99_lower = np.percentile(final_returns, 0.5)
        ci_99_upper = np.percentile(final_returns, 99.5)
        
        result = MonteCarloResult(
            timestamp=datetime.now(),
            iterations=iterations,
            mean_return=mean_final_return,
            std_return=std_final_return,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall_95=expected_shortfall_95,
            expected_shortfall_99=expected_shortfall_99,
            max_drawdown=max_drawdown,
            probability_loss=probability_loss,
            probability_profit=probability_profit,
            confidence_interval_95=(ci_95_lower, ci_95_upper),
            confidence_interval_99=(ci_99_lower, ci_99_upper),
            best_case=np.max(final_returns),
            worst_case=np.min(final_returns),
            median_return=median_return
        )
        
        self.simulations.append(result)
        
        return result
    
    def _get_default_result(self) -> MonteCarloResult:
        """
        Get default Monte Carlo result.
        
        Returns:
            Default MonteCarloResult object
        """
        return MonteCarloResult(
            timestamp=datetime.now(),
            iterations=0,
            mean_return=0.0,
            std_return=0.0,
            var_95=0.0,
            var_99=0.0,
            expected_shortfall_95=0.0,
            expected_shortfall_99=0.0,
            max_drawdown=0.0,
            probability_loss=0.5,
            probability_profit=0.5,
            confidence_interval_95=(0.0, 0.0),
            confidence_interval_99=(0.0, 0.0),
            best_case=0.0,
            worst_case=0.0,
            median_return=0.0
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Monte Carlo simulation results.
        
        Args:
            df: OHLCV data
            
        Returns:
            Analysis results
        """
        if len(df) < 20:
            return {'simulation': self._get_default_result(), 'signals': []}
        
        # Calculate returns
        returns = df['close'].pct_change().dropna().values
        
        # Run simulation
        simulation = self.simulate(returns)
        
        # Generate signals
        signals = self._generate_signals(df, simulation)
        
        return {
            'simulation': simulation,
            'signals': signals,
            'status': self._get_status(simulation),
            'market_character': self._get_market_character(df, simulation)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         simulation: MonteCarloResult) -> List[MonteCarloSignal]:
        """
        Generate trading signals from Monte Carlo simulation.
        
        Args:
            df: OHLCV data
            simulation: MonteCarloResult object
            
        Returns:
            List of MonteCarloSignal objects
        """
        signals = []
        
        if simulation.probability_profit < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Generate signal based on simulation results
        if simulation.probability_profit > 0.6:
            signal_type = 'buy'
            reason = f"Monte Carlo simulation shows {simulation.probability_profit:.1%} probability of profit"
            confidence = simulation.probability_profit
            target = current_price * (1 + simulation.median_return)
            stop_loss = current_price * (1 - simulation.var_95 * 0.5)
            
            signals.append(MonteCarloSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                simulation=simulation,
                indicators={
                    'mean_return': simulation.mean_return,
                    'var_95': simulation.var_95,
                    'expected_shortfall': simulation.expected_shortfall_95,
                    'max_drawdown': simulation.max_drawdown,
                    'confidence_interval': simulation.confidence_interval_95
                }
            ))
        elif simulation.probability_loss > 0.6:
            signal_type = 'sell'
            reason = f"Monte Carlo simulation shows {simulation.probability_loss:.1%} probability of loss"
            confidence = simulation.probability_loss
            target = current_price * (1 + simulation.median_return)
            stop_loss = current_price * (1 + simulation.var_95 * 0.5)
            
            signals.append(MonteCarloSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                simulation=simulation,
                indicators={
                    'mean_return': simulation.mean_return,
                    'var_95': simulation.var_95,
                    'expected_shortfall': simulation.expected_shortfall_95,
                    'max_drawdown': simulation.max_drawdown,
                    'confidence_interval': simulation.confidence_interval_95
                }
            ))
        
        return signals
    
    def _get_status(self, simulation: MonteCarloResult) -> str:
        """
        Get status from simulation results.
        
        Args:
            simulation: MonteCarloResult object
            
        Returns:
            Status string
        """
        if simulation.probability_profit > 0.7:
            return 'bullish'
        elif simulation.probability_profit > 0.55:
            return 'moderately_bullish'
        elif simulation.probability_loss > 0.7:
            return 'bearish'
        elif simulation.probability_loss > 0.55:
            return 'moderately_bearish'
        else:
            return 'neutral'
    
    def _get_market_character(self, df: pd.DataFrame,
                            simulation: MonteCarloResult) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            simulation: MonteCarloResult object
            
        Returns:
            Market character description
        """
        if simulation.probability_profit > 0.7:
            return f"Bullish - {simulation.probability_profit:.1%} profit probability"
        elif simulation.probability_profit > 0.55:
            return f"Moderately Bullish - {simulation.probability_profit:.1%} profit probability"
        elif simulation.probability_loss > 0.7:
            return f"Bearish - {simulation.probability_loss:.1%} loss probability"
        elif simulation.probability_loss > 0.55:
            return f"Moderately Bearish - {simulation.probability_loss:.1%} loss probability"
        else:
            return "Neutral - balanced probabilities"
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """
        Get simulation summary.
        
        Returns:
            Simulation summary
        """
        if not self.simulations:
            return {'status': 'no_simulations'}
        
        latest = self.simulations[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_simulation': latest,
            'total_simulations': len(self.simulations),
            'average_probability_profit': np.mean([s.probability_profit for s in self.simulations]),
            'average_probability_loss': np.mean([s.probability_loss for s in self.simulations]),
            'average_var_95': np.mean([s.var_95 for s in self.simulations]),
            'average_max_drawdown': np.mean([s.max_drawdown for s in self.simulations]),
            'status': self._get_status(latest)
        }


def create_monte_carlo_model(config: Optional[Dict[str, Any]] = None) -> MonteCarloModel:
    """
    Create a Monte Carlo model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MonteCarloModel instance
    """
    return MonteCarloModel(config)


__all__ = [
    'MonteCarloResult',
    'MonteCarloSignal',
    'MonteCarloModel',
    'create_monte_carlo_model'
]
