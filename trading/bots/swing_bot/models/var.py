"""
Swing Bot VaR Model
======================

This module provides Value at Risk (VaR) models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from scipy import stats
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class VaRResult:
    """VaR calculation result."""
    method: str  # 'historical', 'parametric', 'monte_carlo'
    confidence_level: float
    time_horizon: int
    value: float
    expected_shortfall: float
    timestamp: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VaRReport:
    """VaR report data structure."""
    timestamp: datetime
    portfolio_value: float
    var_results: List[VaRResult]
    stress_scenarios: Dict[str, float]
    risk_limits: Dict[str, Any]
    breaches: List[Dict[str, Any]]


class VaRModel:
    """
    Value at Risk (VaR) model for risk assessment.
    
    Supports multiple VaR calculation methods:
    - Historical Simulation
    - Parametric (Variance-Covariance)
    - Monte Carlo Simulation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the VaR model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.default_confidence = self.config.get('default_confidence', 0.95)
        self.default_horizon = self.config.get('default_horizon', 1)
        self.historical_window = self.config.get('historical_window', 252)
        self.monte_carlo_iterations = self.config.get('monte_carlo_iterations', 10000)
        self.random_seed = self.config.get('random_seed', 42)
        
    def calculate_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence: Optional[float] = None,
        horizon: Optional[int] = None,
        method: str = 'historical'
    ) -> VaRResult:
        """
        Calculate Value at Risk.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            confidence: Confidence level (default: 0.95)
            horizon: Time horizon in days (default: 1)
            method: Calculation method ('historical', 'parametric', 'monte_carlo')
            
        Returns:
            VaRResult object
        """
        confidence = confidence or self.default_confidence
        horizon = horizon or self.default_horizon
        
        if method == 'historical':
            return self._calculate_historical_var(returns, portfolio_value, confidence, horizon)
        elif method == 'parametric':
            return self._calculate_parametric_var(returns, portfolio_value, confidence, horizon)
        elif method == 'monte_carlo':
            return self._calculate_monte_carlo_var(returns, portfolio_value, confidence, horizon)
        else:
            raise ValueError(f"Unsupported method: {method}")
    
    def _calculate_historical_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence: float,
        horizon: int
    ) -> VaRResult:
        """
        Calculate VaR using historical simulation.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            confidence: Confidence level
            horizon: Time horizon in days
            
        Returns:
            VaRResult object
        """
        if len(returns) < 2:
            return VaRResult(
                method='historical',
                confidence_level=confidence,
                time_horizon=horizon,
                value=0.0,
                expected_shortfall=0.0,
                timestamp=datetime.now()
            )
        
        # Calculate portfolio returns
        portfolio_returns = returns * portfolio_value
        
        # Scale to horizon
        scaled_returns = portfolio_returns * np.sqrt(horizon)
        
        # Calculate VaR as percentile
        var_value = np.percentile(scaled_returns, (1 - confidence) * 100)
        var_value = abs(var_value)
        
        # Calculate Expected Shortfall (CVaR)
        tail_returns = scaled_returns[scaled_returns <= -var_value]
        expected_shortfall = abs(np.mean(tail_returns)) if len(tail_returns) > 0 else var_value
        
        return VaRResult(
            method='historical',
            confidence_level=confidence,
            time_horizon=horizon,
            value=var_value,
            expected_shortfall=expected_shortfall,
            timestamp=datetime.now(),
            parameters={
                'window': len(returns),
                'mean_return': np.mean(returns),
                'std_return': np.std(returns)
            }
        )
    
    def _calculate_parametric_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence: float,
        horizon: int
    ) -> VaRResult:
        """
        Calculate VaR using parametric (variance-covariance) method.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            confidence: Confidence level
            horizon: Time horizon in days
            
        Returns:
            VaRResult object
        """
        if len(returns) < 2:
            return VaRResult(
                method='parametric',
                confidence_level=confidence,
                time_horizon=horizon,
                value=0.0,
                expected_shortfall=0.0,
                timestamp=datetime.now()
            )
        
        # Calculate parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Calculate z-score for confidence level
        z_score = stats.norm.ppf(1 - confidence)
        
        # Calculate VaR
        var_value = (mean_return - z_score * std_return) * portfolio_value * np.sqrt(horizon)
        var_value = abs(var_value)
        
        # Calculate Expected Shortfall (CVaR)
        # For normal distribution: ES = -mean + (std * phi(z) / (1 - confidence))
        phi_z = stats.norm.pdf(z_score)
        es_value = (mean_return + std_return * phi_z / (1 - confidence)) * portfolio_value * np.sqrt(horizon)
        es_value = abs(es_value)
        
        return VaRResult(
            method='parametric',
            confidence_level=confidence,
            time_horizon=horizon,
            value=var_value,
            expected_shortfall=es_value,
            timestamp=datetime.now(),
            parameters={
                'mean_return': mean_return,
                'std_return': std_return,
                'z_score': z_score
            }
        )
    
    def _calculate_monte_carlo_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence: float,
        horizon: int
    ) -> VaRResult:
        """
        Calculate VaR using Monte Carlo simulation.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            confidence: Confidence level
            horizon: Time horizon in days
            
        Returns:
            VaRResult object
        """
        if len(returns) < 2:
            return VaRResult(
                method='monte_carlo',
                confidence_level=confidence,
                time_horizon=horizon,
                value=0.0,
                expected_shortfall=0.0,
                timestamp=datetime.now()
            )
        
        # Set random seed for reproducibility
        np.random.seed(self.random_seed)
        
        # Calculate parameters
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Generate scenarios
        n = self.monte_carlo_iterations
        simulations = np.random.normal(mean_return, std_return, (n, horizon))
        
        # Calculate portfolio values
        portfolio_returns = np.sum(simulations, axis=1)
        final_values = portfolio_value * (1 + portfolio_returns)
        
        # Calculate VaR
        var_value = np.percentile(final_values, (1 - confidence) * 100)
        var_loss = portfolio_value - var_value
        
        # Calculate Expected Shortfall (CVaR)
        tail_values = final_values[final_values <= var_value]
        expected_shortfall = portfolio_value - np.mean(tail_values) if len(tail_values) > 0 else var_loss
        
        return VaRResult(
            method='monte_carlo',
            confidence_level=confidence,
            time_horizon=horizon,
            value=var_loss,
            expected_shortfall=expected_shortfall,
            timestamp=datetime.now(),
            parameters={
                'iterations': n,
                'mean_return': mean_return,
                'std_return': std_return,
                'horizon': horizon
            }
        )
    
    def calculate_portfolio_var(
        self,
        returns_data: np.ndarray,
        weights: np.ndarray,
        portfolio_value: float,
        confidence: Optional[float] = None,
        horizon: Optional[int] = None,
        method: str = 'historical'
    ) -> VaRResult:
        """
        Calculate VaR for a portfolio of assets.
        
        Args:
            returns_data: Returns matrix (n_assets x n_observations)
            weights: Asset weights
            portfolio_value: Portfolio value
            confidence: Confidence level
            horizon: Time horizon in days
            method: Calculation method
            
        Returns:
            VaRResult object
        """
        confidence = confidence or self.default_confidence
        horizon = horizon or self.default_horizon
        
        # Calculate portfolio returns
        portfolio_returns = np.dot(weights, returns_data)
        
        return self.calculate_var(
            portfolio_returns,
            portfolio_value,
            confidence,
            horizon,
            method
        )
    
    def stress_test(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        scenarios: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Perform stress testing scenarios.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            scenarios: Dictionary of scenario names and shock values
            
        Returns:
            Dictionary of scenario results
        """
        results = {}
        
        for scenario_name, shock in scenarios.items():
            # Apply shock to returns
            shocked_returns = returns + shock
            
            # Calculate VaR under shock
            var_result = self._calculate_historical_var(
                shocked_returns,
                portfolio_value,
                self.default_confidence,
                self.default_horizon
            )
            
            results[scenario_name] = var_result.value
        
        return results
    
    def generate_report(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        risk_limits: Optional[Dict[str, float]] = None
    ) -> VaRReport:
        """
        Generate a VaR report.
        
        Args:
            returns: Returns array
            portfolio_value: Portfolio value
            risk_limits: Risk limits dictionary
            
        Returns:
            VaRReport object
        """
        risk_limits = risk_limits or {}
        
        # Calculate VaR using multiple methods
        var_results = []
        
        for method in ['historical', 'parametric', 'monte_carlo']:
            result = self.calculate_var(returns, portfolio_value, method=method)
            var_results.append(result)
        
        # Stress test scenarios
        stress_scenarios = {
            'market_crash': -0.20,
            'volatility_spike': 0.30,
            'liquidity_crisis': -0.10,
            'correlation_breakdown': 0.50
        }
        
        stress_results = self.stress_test(returns, portfolio_value, stress_scenarios)
        
        # Check breaches
        breaches = []
        for limit_name, limit_value in risk_limits.items():
            for result in var_results:
                if result.value > limit_value:
                    breaches.append({
                        'limit': limit_name,
                        'value': result.value,
                        'limit_value': limit_value,
                        'method': result.method,
                        'excess_percent': (result.value / limit_value - 1) * 100
                    })
        
        return VaRReport(
            timestamp=datetime.now(),
            portfolio_value=portfolio_value,
            var_results=var_results,
            stress_scenarios=stress_results,
            risk_limits=risk_limits,
            breaches=breaches
        )
    
    def validate_var(self, returns: np.ndarray, var_result: VaRResult) -> Dict[str, Any]:
        """
        Validate VaR calculation using backtesting.
        
        Args:
            returns: Returns array
            var_result: VaRResult object
            
        Returns:
            Validation results
        """
        # Count exceptions (returns exceeding VaR)
        var_value = var_result.value / np.sqrt(var_result.time_horizon)
        exceptions = np.sum(np.abs(returns) > var_value) / len(returns)
        
        # Calculate Kupiec test
        expected_exceptions = 1 - var_result.confidence_level
        z_score = (exceptions - expected_exceptions) / np.sqrt(
            expected_exceptions * (1 - expected_exceptions) / len(returns)
        )
        
        # Calculate Christoffersen test
        first_order = np.sum(returns[1:] > var_value) / (len(returns) - 1)
        independence = np.sum(np.abs(returns[1:]) > var_value) / (len(returns) - 1)
        
        return {
            'exception_rate': exceptions,
            'expected_rate': expected_exceptions,
            'kupiec_z_score': z_score,
            'kupiec_p_value': 1 - stats.norm.cdf(abs(z_score)),
            'first_order_autocorrelation': first_order,
            'independence_ratio': independence,
            'is_valid': abs(z_score) < 1.96  # 95% confidence level
        }


def create_var_model(config: Optional[Dict[str, Any]] = None) -> VaRModel:
    """
    Create a VaR model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        VaRModel instance
    """
    return VaRModel(config)


__all__ = [
    'VaRResult',
    'VaRReport',
    'VaRModel',
    'create_var_model'
]
