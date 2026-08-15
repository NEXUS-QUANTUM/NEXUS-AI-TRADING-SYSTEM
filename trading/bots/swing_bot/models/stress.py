"""
Swing Bot Stress Model
========================

This module provides stress testing models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy import stats


@dataclass
class StressScenario:
    """Stress scenario data structure."""
    name: str
    description: str
    shock_type: str  # 'market', 'volatility', 'liquidity', 'correlation'
    shock_magnitude: float
    impact: Dict[str, float]
    probability: float
    severity: str  # 'low', 'medium', 'high', 'extreme'
    timestamp: datetime


@dataclass
class StressResult:
    """Stress test result data structure."""
    scenario: StressScenario
    portfolio_value_change: float
    max_drawdown: float
    var_breach: bool
    confidence: float
    recovery_time: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)


@dataclass
class StressSignal:
    """Stress trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    scenario: StressScenario
    indicators: Dict[str, Any] = field(default_factory=dict)


class StressModel:
    """
    Stress testing model for portfolio resilience.
    
    Implements stress testing and scenario analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the stress model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.scenarios: List[StressScenario] = []
        self.results: List[StressResult] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Register default scenarios
        self._register_default_scenarios()
        
    def _register_default_scenarios(self) -> None:
        """Register default stress scenarios."""
        default_scenarios = [
            StressScenario(
                name='market_crash',
                description='Sudden market crash of 20%',
                shock_type='market',
                shock_magnitude=-0.20,
                impact={},
                probability=0.05,
                severity='extreme',
                timestamp=datetime.now()
            ),
            StressScenario(
                name='volatility_spike',
                description='Volatility spike of 50%',
                shock_type='volatility',
                shock_magnitude=0.50,
                impact={},
                probability=0.10,
                severity='high',
                timestamp=datetime.now()
            ),
            StressScenario(
                name='liquidity_crisis',
                description='Liquidity crisis with 30% drop',
                shock_type='liquidity',
                shock_magnitude=-0.30,
                impact={},
                probability=0.08,
                severity='high',
                timestamp=datetime.now()
            ),
            StressScenario(
                name='correlation_breakdown',
                description='Correlation breakdown of 40%',
                shock_type='correlation',
                shock_magnitude=0.40,
                impact={},
                probability=0.12,
                severity='medium',
                timestamp=datetime.now()
            )
        ]
        
        self.scenarios.extend(default_scenarios)
    
    def add_scenario(self, scenario: StressScenario) -> None:
        """
        Add a stress scenario.
        
        Args:
            scenario: StressScenario object
        """
        self.scenarios.append(scenario)
    
    def run_stress_test(self, portfolio: Dict[str, Any],
                       market_data: Dict[str, pd.DataFrame]) -> List[StressResult]:
        """
        Run stress tests on portfolio.
        
        Args:
            portfolio: Portfolio data
            market_data: Market data
            
        Returns:
            List of StressResult objects
        """
        results = []
        
        for scenario in self.scenarios:
            result = self._run_scenario(portfolio, market_data, scenario)
            results.append(result)
        
        self.results.extend(results)
        
        return results
    
    def _run_scenario(self, portfolio: Dict[str, Any],
                     market_data: Dict[str, pd.DataFrame],
                     scenario: StressScenario) -> StressResult:
        """
        Run a single stress scenario.
        
        Args:
            portfolio: Portfolio data
            market_data: Market data
            scenario: StressScenario object
            
        Returns:
            StressResult object
        """
        # Calculate impact
        impact = self._calculate_impact(portfolio, market_data, scenario)
        scenario.impact = impact
        
        # Calculate portfolio value change
        total_value = portfolio.get('total_value', 0)
        value_change = impact.get('total_change', 0)
        portfolio_value_change = value_change / total_value if total_value > 0 else 0
        
        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(market_data, scenario)
        
        # Check VaR breach
        var_breach = self._check_var_breach(market_data, scenario)
        
        # Calculate confidence
        confidence = 1 - scenario.probability
        
        # Generate recommendations
        recommendations = self._generate_recommendations(scenario, portfolio_value_change)
        
        return StressResult(
            scenario=scenario,
            portfolio_value_change=portfolio_value_change,
            max_drawdown=max_drawdown,
            var_breach=var_breach,
            confidence=confidence,
            recovery_time=self._estimate_recovery_time(scenario),
            recommendations=recommendations
        )
    
    def _calculate_impact(self, portfolio: Dict[str, Any],
                         market_data: Dict[str, pd.DataFrame],
                         scenario: StressScenario) -> Dict[str, float]:
        """
        Calculate impact of stress scenario.
        
        Args:
            portfolio: Portfolio data
            market_data: Market data
            scenario: StressScenario object
            
        Returns:
            Impact dictionary
        """
        impact = {}
        
        # Get positions
        positions = portfolio.get('positions', {})
        
        # Calculate impact on each position
        for symbol, position in positions.items():
            if symbol in market_data:
                df = market_data[symbol]
                if len(df) > 0:
                    current_price = df['close'].iloc[-1]
                    
                    # Apply shock
                    if scenario.shock_type == 'market':
                        shocked_price = current_price * (1 + scenario.shock_magnitude)
                    elif scenario.shock_type == 'volatility':
                        shocked_price = current_price * (1 + np.random.normal(0, scenario.shock_magnitude * 0.1))
                    elif scenario.shock_type == 'liquidity':
                        shocked_price = current_price * (1 + scenario.shock_magnitude * 0.5)
                    else:
                        shocked_price = current_price
                    
                    # Calculate impact
                    position_value = position.get('quantity', 0) * current_price
                    shocked_value = position.get('quantity', 0) * shocked_price
                    impact[symbol] = shocked_value - position_value
        
        # Calculate total impact
        impact['total_change'] = sum(impact.values())
        
        return impact
    
    def _calculate_max_drawdown(self, market_data: Dict[str, pd.DataFrame],
                              scenario: StressScenario) -> float:
        """
        Calculate maximum drawdown under stress.
        
        Args:
            market_data: Market data
            scenario: StressScenario object
            
        Returns:
            Maximum drawdown
        """
        drawdowns = []
        
        for symbol, df in market_data.items():
            if len(df) > 0:
                close = df['close'].values
                drawdown = MathUtils.max_drawdown(close)[0]
                drawdowns.append(drawdown)
        
        if not drawdowns:
            return 0.0
        
        return np.max(drawdowns)
    
    def _check_var_breach(self, market_data: Dict[str, pd.DataFrame],
                         scenario: StressScenario) -> bool:
        """
        Check if VaR is breached under stress.
        
        Args:
            market_data: Market data
            scenario: StressScenario object
            
        Returns:
            True if breached, False otherwise
        """
        returns = []
        
        for symbol, df in market_data.items():
            if len(df) > 1:
                ret = np.diff(np.log(df['close'].values))
                returns.extend(ret)
        
        if not returns:
            return False
        
        # Calculate VaR
        var_95 = np.percentile(returns, 5)
        
        # Check if scenario breaches VaR
        if scenario.shock_type == 'market':
            return scenario.shock_magnitude < var_95
        elif scenario.shock_type == 'volatility':
            return np.std(returns) * np.sqrt(252) > 0.30
        elif scenario.shock_type == 'liquidity':
            return np.percentile(returns, 1) < -0.05
        
        return False
    
    def _estimate_recovery_time(self, scenario: StressScenario) -> Optional[float]:
        """
        Estimate recovery time for stress scenario.
        
        Args:
            scenario: StressScenario object
            
        Returns:
            Recovery time in days or None
        """
        if scenario.severity == 'low':
            return 5.0
        elif scenario.severity == 'medium':
            return 15.0
        elif scenario.severity == 'high':
            return 30.0
        elif scenario.severity == 'extreme':
            return 60.0
        else:
            return None
    
    def _generate_recommendations(self, scenario: StressScenario,
                                portfolio_value_change: float) -> List[str]:
        """
        Generate recommendations based on stress test.
        
        Args:
            scenario: StressScenario object
            portfolio_value_change: Portfolio value change
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if portfolio_value_change < -0.20:
            recommendations.append("Reduce position sizes immediately")
            recommendations.append("Increase cash allocation")
            recommendations.append("Consider hedging strategies")
        elif portfolio_value_change < -0.10:
            recommendations.append("Review portfolio diversification")
            recommendations.append("Adjust stop-loss levels")
            recommendations.append("Consider partial hedging")
        elif portfolio_value_change < -0.05:
            recommendations.append("Monitor portfolio risk closely")
            recommendations.append("Review position concentration")
        else:
            recommendations.append("Portfolio appears resilient to this scenario")
        
        if scenario.severity == 'extreme':
            recommendations.append("Prepare for potential black swan events")
            recommendations.append("Maintain sufficient liquidity")
        
        return recommendations
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[StressSignal]:
        """
        Generate trading signal from stress analysis.
        
        Args:
            df: OHLCV data
            
        Returns:
            StressSignal or None
        """
        if not self.results:
            return None
        
        # Get latest stress result
        latest_result = self.results[-1]
        
        if latest_result.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on stress result
        if latest_result.portfolio_value_change < -0.15:
            signal_type = 'sell'
            reason = f"Stress scenario {latest_result.scenario.name} indicates high risk"
            target = current_price * 0.95
            stop_loss = current_price * 1.02
        elif latest_result.portfolio_value_change < -0.05:
            signal_type = 'sell'
            reason = f"Stress scenario {latest_result.scenario.name} indicates moderate risk"
            target = current_price * 0.97
            stop_loss = current_price * 1.01
        else:
            return None
        
        return StressSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=latest_result.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            scenario=latest_result.scenario,
            indicators={
                'portfolio_value_change': latest_result.portfolio_value_change,
                'max_drawdown': latest_result.max_drawdown,
                'var_breach': latest_result.var_breach
            }
        )
    
    def get_stress_summary(self) -> Dict[str, Any]:
        """
        Get stress testing summary.
        
        Returns:
            Stress summary dictionary
        """
        if not self.results:
            return {'status': 'no_tests_run'}
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_scenarios': len(self.scenarios),
            'tests_run': len(self.results),
            'worst_case': max(self.results, key=lambda r: abs(r.portfolio_value_change)),
            'best_case': min(self.results, key=lambda r: abs(r.portfolio_value_change)),
            'average_impact': np.mean([r.portfolio_value_change for r in self.results]),
            'var_breaches': sum(1 for r in self.results if r.var_breach),
            'recommendations': self.results[-1].recommendations if self.results else []
        }


def create_stress_model(config: Optional[Dict[str, Any]] = None) -> StressModel:
    """
    Create a stress model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        StressModel instance
    """
    return StressModel(config)


__all__ = [
    'StressScenario',
    'StressResult',
    'StressSignal',
    'StressModel',
    'create_stress_model'
]
