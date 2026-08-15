"""
Swing Bot Simulation Model
============================

This module provides simulation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class SimulationScenario:
    """Simulation scenario data structure."""
    name: str
    description: str
    parameters: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MonteCarloResult:
    """Monte Carlo simulation result."""
    timestamp: datetime
    iterations: int
    mean_return: float
    std_return: float
    var_95: float
    expected_shortfall: float
    max_drawdown: float
    probability_loss: float
    probability_profit: float
    confidence_interval: Tuple[float, float]


@dataclass
class SimulationSignal:
    """Simulation trading signal."""
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


class SimulationModel:
    """
    Simulation model for trading strategies.
    
    Implements Monte Carlo and scenario simulations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the simulation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.scenarios: List[SimulationScenario] = []
        self.results: List[MonteCarloResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.default_iterations = self.config.get('default_iterations', 10000)
        
    def monte_carlo_simulation(self, returns: np.ndarray,
                              iterations: Optional[int] = None) -> MonteCarloResult:
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
        simulated_returns = np.random.normal(mean_return, std_return, (iterations, 252))
        cumulative_returns = np.cumprod(1 + simulated_returns, axis=1)
        
        # Calculate metrics
        final_returns = cumulative_returns[:, -1] - 1
        
        # Calculate VaR
        var_95 = np.percentile(final_returns, 5)
        
        # Calculate Expected Shortfall
        tail_returns = final_returns[final_returns <= var_95]
        expected_shortfall = np.mean(tail_returns) if len(tail_returns) > 0 else var_95
        
        # Calculate drawdown
        max_drawdowns = []
        for path in cumulative_returns:
            drawdown = (path - np.maximum.accumulate(path)) / np.maximum.accumulate(path)
            max_drawdowns.append(np.min(drawdown))
        max_drawdown = np.mean(max_drawdowns)
        
        # Calculate probabilities
        probability_loss = np.mean(final_returns < 0)
        probability_profit = np.mean(final_returns > 0)
        
        # Calculate confidence interval
        lower_bound = np.percentile(final_returns, 2.5)
        upper_bound = np.percentile(final_returns, 97.5)
        
        result = MonteCarloResult(
            timestamp=datetime.now(),
            iterations=iterations,
            mean_return=np.mean(final_returns),
            std_return=np.std(final_returns),
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            max_drawdown=max_drawdown,
            probability_loss=probability_loss,
            probability_profit=probability_profit,
            confidence_interval=(lower_bound, upper_bound)
        )
        
        self.results.append(result)
        
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
            expected_shortfall=0.0,
            max_drawdown=0.0,
            probability_loss=0.5,
            probability_profit=0.5,
            confidence_interval=(0.0, 0.0)
        )
    
    def scenario_analysis(self, base_case: Dict[str, Any],
                         scenarios: List[Dict[str, Any]]) -> List[SimulationScenario]:
        """
        Run scenario analysis.
        
        Args:
            base_case: Base case parameters
            scenarios: List of scenario parameters
            
        Returns:
            List of SimulationScenario objects
        """
        results = []
        
        # Run base case
        base_result = self._run_scenario(base_case)
        
        # Run scenarios
        for scenario_data in scenarios:
            scenario = SimulationScenario(
                name=scenario_data.get('name', 'Scenario'),
                description=scenario_data.get('description', ''),
                parameters=scenario_data,
                results=self._run_scenario(scenario_data),
                timestamp=datetime.now()
            )
            results.append(scenario)
        
        self.scenarios.extend(results)
        
        return results
    
    def _run_scenario(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single scenario.
        
        Args:
            params: Scenario parameters
            
        Returns:
            Scenario results
        """
        # Generate returns based on parameters
        mean_return = params.get('mean_return', 0.0)
        std_return = params.get('std_return', 0.02)
        iterations = params.get('iterations', 1000)
        
        returns = np.random.normal(mean_return, std_return, iterations)
        
        # Calculate metrics
        mean = np.mean(returns)
        std = np.std(returns)
        var = np.percentile(returns, 5)
        
        return {
            'mean_return': mean,
            'std_return': std,
            'var_95': var,
            'sharpe_ratio': mean / std if std > 0 else 0,
            'probability_loss': np.mean(returns < 0),
            'probability_profit': np.mean(returns > 0)
        }
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[SimulationSignal]:
        """
        Generate trading signal from simulation.
        
        Args:
            df: OHLCV data
            
        Returns:
            SimulationSignal or None
        """
        if len(df) < 20:
            return None
        
        # Calculate returns
        returns = df['close'].pct_change().dropna().values
        
        # Run Monte Carlo simulation
        result = self.monte_carlo_simulation(returns)
        
        if result.probability_profit < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on simulation
        if result.probability_profit > 0.6:
            signal_type = 'buy'
            reason = f"Monte Carlo simulation shows {result.probability_profit:.1%} probability of profit"
            target = current_price * (1 + result.mean_return)
            stop_loss = current_price * (1 - 0.02)
        elif result.probability_loss > 0.6:
            signal_type = 'sell'
            reason = f"Monte Carlo simulation shows {result.probability_loss:.1%} probability of loss"
            target = current_price * (1 + result.mean_return)
            stop_loss = current_price * (1 + 0.02)
        else:
            return None
        
        return SimulationSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=result.probability_profit if signal_type == 'buy' else result.probability_loss,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            simulation=result,
            indicators={
                'mean_return': result.mean_return,
                'std_return': result.std_return,
                'var_95': result.var_95,
                'max_drawdown': result.max_drawdown,
                'confidence_interval': result.confidence_interval
            }
        )
    
    def get_simulation_summary(self) -> Dict[str, Any]:
        """
        Get simulation summary.
        
        Returns:
            Simulation summary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total_scenarios': len(self.scenarios),
            'monte_carlo_runs': len(self.results),
            'latest_monte_carlo': self.results[-1] if self.results else None,
            'scenarios': [
                {
                    'name': s.name,
                    'description': s.description,
                    'results': s.results
                }
                for s in self.scenarios
            ],
            'summary_stats': {
                'avg_mean_return': np.mean([r.mean_return for r in self.results]) if self.results else 0,
                'avg_std_return': np.mean([r.std_return for r in self.results]) if self.results else 0,
                'avg_var_95': np.mean([r.var_95 for r in self.results]) if self.results else 0,
                'avg_probability_profit': np.mean([r.probability_profit for r in self.results]) if self.results else 0
            }
        }


def create_simulation_model(config: Optional[Dict[str, Any]] = None) -> SimulationModel:
    """
    Create a simulation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SimulationModel instance
    """
    return SimulationModel(config)


__all__ = [
    'SimulationScenario',
    'MonteCarloResult',
    'SimulationSignal',
    'SimulationModel',
    'create_simulation_model'
]
