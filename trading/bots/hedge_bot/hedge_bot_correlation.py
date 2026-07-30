# trading/bots/hedge_bot/hedge_bot_correlation.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Correlation Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Correlation Module

This module provides comprehensive correlation analysis capabilities
for the NEXUS Hedge Bot system. It calculates and analyzes correlations
between assets, portfolios, and market factors.

The module covers:
- Correlation Matrix Calculation
- Rolling Correlation Analysis
- Partial Correlation
- Dynamic Correlation
- Correlation Forecasting
- Correlation Regime Detection
- Correlation-Based Risk Assessment
- Portfolio Correlation Analysis
- Factor Correlation Analysis
- Correlation Visualization
- Correlation Metrics
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from scipy import stats
from scipy.optimize import minimize

logger = logging.getLogger(__name__)


# ============================================================
# CORRELATION ENUMS
# ============================================================

class CorrelationMethod(Enum):
    """Correlation calculation methods"""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"
    PARTIAL = "partial"
    DYNAMIC = "dynamic"


class CorrelationRegime(Enum):
    """Correlation regimes"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGATIVE = "negative"
    BREAKING = "breaking"


@dataclass
class CorrelationMetrics:
    """Correlation metrics"""
    asset1: str
    asset2: str
    correlation: float
    p_value: float
    confidence_lower: float
    confidence_upper: float
    method: CorrelationMethod
    period: int
    regime: CorrelationRegime
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "asset1": self.asset1,
            "asset2": self.asset2,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "method": self.method.value,
            "period": self.period,
            "regime": self.regime.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class CorrelationMatrix:
    """Correlation matrix"""
    assets: List[str]
    matrix: np.ndarray
    p_values: np.ndarray
    method: CorrelationMethod
    period: int
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "assets": self.assets,
            "matrix": self.matrix.tolist(),
            "p_values": self.p_values.tolist(),
            "method": self.method.value,
            "period": self.period,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class CorrelationRegimeDetector:
    """Correlation regime detector"""
    current_regime: CorrelationRegime
    previous_regime: Optional[CorrelationRegime] = None
    regime_probability: float = 1.0
    transition_probability: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "current_regime": self.current_regime.value,
            "previous_regime": self.previous_regime.value if self.previous_regime else None,
            "regime_probability": self.regime_probability,
            "transition_probability": self.transition_probability,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CORRELATION ENGINE
# ============================================================

class CorrelationEngine:
    """
    Comprehensive correlation engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the correlation engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_period = self.config.get("default_period", 252)
        self.default_method = self.config.get("default_method", "pearson")
        self.rolling_window = self.config.get("rolling_window", 60)
        
        # State
        self.correlation_cache: Dict[str, CorrelationMetrics] = {}
        self.matrix_cache: Dict[str, CorrelationMatrix] = {}
        self.regime_cache: Dict[str, CorrelationRegimeDetector] = {}
        self.rolling_correlations: Dict[str, List[CorrelationMetrics]] = {}
        
        logger.info("Correlation engine initialized")
    
    # ============================================================
    # CORRELATION CALCULATION
    # ============================================================
    
    def calculate_correlation(
        self,
        returns1: Union[List[float], np.ndarray],
        returns2: Union[List[float], np.ndarray],
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        period: Optional[int] = None,
        asset1: str = "asset1",
        asset2: str = "asset2"
    ) -> CorrelationMetrics:
        """
        Calculate correlation between two assets
        
        Args:
            returns1: First asset returns
            returns2: Second asset returns
            method: Correlation method
            period: Lookback period
            asset1: First asset name
            asset2: Second asset name
            
        Returns:
            CorrelationMetrics
        """
        if period is None:
            period = self.default_period
        
        # Convert to numpy arrays
        if isinstance(returns1, list):
            returns1 = np.array(returns1)
        if isinstance(returns2, list):
            returns2 = np.array(returns2)
        
        # Trim to period
        if len(returns1) > period:
            returns1 = returns1[-period:]
            returns2 = returns2[-period:]
        
        # Calculate correlation
        if method == CorrelationMethod.PEARSON:
            correlation, p_value = stats.pearsonr(returns1, returns2)
        elif method == CorrelationMethod.SPEARMAN:
            correlation, p_value = stats.spearmanr(returns1, returns2)
        elif method == CorrelationMethod.KENDALL:
            correlation, p_value = stats.kendalltau(returns1, returns2)
        elif method == CorrelationMethod.PARTIAL:
            correlation, p_value = self._calculate_partial_correlation(returns1, returns2)
        else:
            correlation, p_value = stats.pearsonr(returns1, returns2)
        
        # Calculate confidence intervals
        n = len(returns1)
        z = np.arctanh(correlation)
        se = 1 / np.sqrt(n - 3)
        z_crit = stats.norm.ppf(0.975)
        ci_lower = np.tanh(z - z_crit * se)
        ci_upper = np.tanh(z + z_crit * se)
        
        # Determine regime
        regime = self._determine_regime(correlation)
        
        metrics = CorrelationMetrics(
            asset1=asset1,
            asset2=asset2,
            correlation=correlation,
            p_value=p_value,
            confidence_lower=ci_lower,
            confidence_upper=ci_upper,
            method=method,
            period=period,
            regime=regime,
            details={
                "n_observations": len(returns1),
                "variance1": float(np.var(returns1)),
                "variance2": float(np.var(returns2)),
            }
        )
        
        cache_key = f"{asset1}_{asset2}_{period}"
        self.correlation_cache[cache_key] = metrics
        return metrics
    
    def _calculate_partial_correlation(
        self,
        x: np.ndarray,
        y: np.ndarray,
        z: Optional[np.ndarray] = None
    ) -> Tuple[float, float]:
        """
        Calculate partial correlation
        
        Args:
            x: First variable
            y: Second variable
            z: Control variable
            
        Returns:
            (correlation, p_value)
        """
        if z is None:
            # Use rolling correlation as control
            z = np.convolve(x, np.ones(20)/20, mode='same')[:len(x)]
        
        # Regression residuals
        model_x = stats.linregress(z, x)
        model_y = stats.linregress(z, y)
        
        residual_x = x - (model_x.slope * z + model_x.intercept)
        residual_y = y - (model_y.slope * z + model_y.intercept)
        
        # Correlation of residuals
        return stats.pearsonr(residual_x, residual_y)
    
    def _determine_regime(self, correlation: float) -> CorrelationRegime:
        """Determine correlation regime"""
        if correlation > 0.7:
            return CorrelationRegime.HIGH
        elif correlation > 0.3:
            return CorrelationRegime.MEDIUM
        elif correlation > -0.3:
            return CorrelationRegime.LOW
        else:
            return CorrelationRegime.NEGATIVE
    
    # ============================================================
    # CORRELATION MATRIX
    # ============================================================
    
    def calculate_correlation_matrix(
        self,
        returns_dict: Dict[str, Union[List[float], np.ndarray]],
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        period: Optional[int] = None
    ) -> CorrelationMatrix:
        """
        Calculate correlation matrix for multiple assets
        
        Args:
            returns_dict: Dictionary of returns by asset
            method: Correlation method
            period: Lookback period
            
        Returns:
            CorrelationMatrix
        """
        if period is None:
            period = self.default_period
        
        assets = list(returns_dict.keys())
        n = len(assets)
        
        # Prepare returns matrix
        returns_matrix = []
        for asset in assets:
            returns = returns_dict[asset]
            if isinstance(returns, list):
                returns = np.array(returns)
            if len(returns) > period:
                returns = returns[-period:]
            returns_matrix.append(returns)
        
        returns_matrix = np.array(returns_matrix)
        
        # Calculate correlation matrix
        if method == CorrelationMethod.PEARSON:
            matrix = np.corrcoef(returns_matrix)
        else:
            # For non-Pearson methods, calculate pairwise
            matrix = np.zeros((n, n))
            p_values = np.zeros((n, n))
            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix[i, j] = 1.0
                        p_values[i, j] = 0.0
                    else:
                        if method == CorrelationMethod.SPEARMAN:
                            corr, p = stats.spearmanr(returns_matrix[i], returns_matrix[j])
                        elif method == CorrelationMethod.KENDALL:
                            corr, p = stats.kendalltau(returns_matrix[i], returns_matrix[j])
                        else:
                            corr, p = stats.pearsonr(returns_matrix[i], returns_matrix[j])
                        matrix[i, j] = corr
                        p_values[i, j] = p
        
        matrix_result = CorrelationMatrix(
            assets=assets,
            matrix=matrix,
            p_values=p_values,
            method=method,
            period=period,
            timestamp=datetime.now(),
        )
        
        self.matrix_cache[f"{'_'.join(assets)}_{period}"] = matrix_result
        return matrix_result
    
    # ============================================================
    # ROLLING CORRELATION
    # ============================================================
    
    def calculate_rolling_correlation(
        self,
        returns1: Union[List[float], np.ndarray],
        returns2: Union[List[float], np.ndarray],
        window: Optional[int] = None,
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        asset1: str = "asset1",
        asset2: str = "asset2"
    ) -> List[CorrelationMetrics]:
        """
        Calculate rolling correlation between two assets
        
        Args:
            returns1: First asset returns
            returns2: Second asset returns
            window: Rolling window
            method: Correlation method
            asset1: First asset name
            asset2: Second asset name
            
        Returns:
            List of CorrelationMetrics
        """
        if window is None:
            window = self.rolling_window
        
        if isinstance(returns1, list):
            returns1 = np.array(returns1)
        if isinstance(returns2, list):
            returns2 = np.array(returns2)
        
        results = []
        
        for i in range(window, len(returns1)):
            period_returns1 = returns1[i-window:i]
            period_returns2 = returns2[i-window:i]
            
            try:
                metrics = self.calculate_correlation(
                    period_returns1,
                    period_returns2,
                    method=method,
                    period=window,
                    asset1=asset1,
                    asset2=asset2,
                )
                results.append(metrics)
            except:
                continue
        
        cache_key = f"{asset1}_{asset2}_rolling"
        self.rolling_correlations[cache_key] = results
        return results
    
    # ============================================================
    # REGIME DETECTION
    # ============================================================
    
    def detect_correlation_regime(
        self,
        correlation_history: List[float],
        threshold: float = 0.3
    ) -> CorrelationRegimeDetector:
        """
        Detect correlation regime
        
        Args:
            correlation_history: Historical correlations
            threshold: Regime threshold
            
        Returns:
            CorrelationRegimeDetector
        """
        if not correlation_history:
            return CorrelationRegimeDetector(
                current_regime=CorrelationRegime.MEDIUM,
                regime_probability=0.0,
            )
        
        current = correlation_history[-1]
        previous = correlation_history[-2] if len(correlation_history) > 1 else current
        
        # Determine current regime
        if current > 0.7:
            current_regime = CorrelationRegime.HIGH
        elif current > 0.3:
            current_regime = CorrelationRegime.MEDIUM
        elif current > -0.3:
            current_regime = CorrelationRegime.LOW
        else:
            current_regime = CorrelationRegime.NEGATIVE
        
        # Determine previous regime
        if previous > 0.7:
            previous_regime = CorrelationRegime.HIGH
        elif previous > 0.3:
            previous_regime = CorrelationRegime.MEDIUM
        elif previous > -0.3:
            previous_regime = CorrelationRegime.LOW
        else:
            previous_regime = CorrelationRegime.NEGATIVE
        
        # Calculate regime probability
        regime_counts = {}
        for corr in correlation_history:
            if corr > 0.7:
                regime = CorrelationRegime.HIGH
            elif corr > 0.3:
                regime = CorrelationRegime.MEDIUM
            elif corr > -0.3:
                regime = CorrelationRegime.LOW
            else:
                regime = CorrelationRegime.NEGATIVE
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        total = len(correlation_history)
        regime_probability = regime_counts.get(current_regime, 0) / total
        
        # Calculate transition probability
        transitions = 0
        for i in range(1, len(correlation_history)):
            if (correlation_history[i] > threshold and correlation_history[i-1] <= threshold) or \
               (correlation_history[i] <= threshold and correlation_history[i-1] > threshold):
                transitions += 1
        transition_probability = transitions / len(correlation_history)
        
        detector = CorrelationRegimeDetector(
            current_regime=current_regime,
            previous_regime=previous_regime if len(correlation_history) > 1 else None,
            regime_probability=regime_probability,
            transition_probability=transition_probability,
        )
        
        self.regime_cache[f"regime_{int(time.time())}"] = detector
        return detector
    
    # ============================================================
    # CORRELATION FORECASTING
    # ============================================================
    
    def forecast_correlation(
        self,
        correlation_history: List[float],
        horizon: int = 10
    ) -> List[float]:
        """
        Forecast future correlations
        
        Args:
            correlation_history: Historical correlations
            horizon: Forecast horizon
            
        Returns:
            Forecasted correlations
        """
        if len(correlation_history) < 20:
            return [correlation_history[-1]] * horizon
        
        # Simple EWMA forecast
        lambda_val = 0.94
        forecast = [correlation_history[-1]]
        
        for _ in range(horizon - 1):
            next_val = lambda_val * forecast[-1] + (1 - lambda_val) * np.mean(correlation_history[-20:])
            forecast.append(next_val)
        
        return forecast
    
    # ============================================================
    # RISK ASSESSMENT
    # ============================================================
    
    def assess_correlation_risk(
        self,
        correlation_matrix: np.ndarray,
        weights: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Assess correlation risk
        
        Args:
            correlation_matrix: Correlation matrix
            weights: Portfolio weights
            
        Returns:
            Risk assessment
        """
        n = correlation_matrix.shape[0]
        
        if weights is None:
            weights = np.ones(n) / n
        
        # Average correlation
        upper_tri = correlation_matrix[np.triu_indices(n, k=1)]
        avg_correlation = np.mean(upper_tri)
        
        # Max correlation
        max_correlation = np.max(upper_tri)
        
        # Concentration risk
        concentration = np.max(weights)
        
        # Diversification ratio
        weighted_corr = np.dot(weights.T, np.dot(correlation_matrix, weights))
        diversification = 1 - weighted_corr
        
        # Risk score
        risk_score = (avg_correlation * 0.4 + max_correlation * 0.3 + concentration * 0.3)
        
        return {
            "avg_correlation": avg_correlation,
            "max_correlation": max_correlation,
            "concentration": concentration,
            "diversification": diversification,
            "risk_score": risk_score,
            "regime": self._determine_regime(avg_correlation).value,
        }
    
    # ============================================================
    # VISUALIZATION
    # ============================================================
    
    def get_correlation_heatmap_data(
        self,
        correlation_matrix: CorrelationMatrix
    ) -> Dict[str, Any]:
        """
        Get data for correlation heatmap
        
        Args:
            correlation_matrix: Correlation matrix
            
        Returns:
            Heatmap data
        """
        return {
            "assets": correlation_matrix.assets,
            "matrix": correlation_matrix.matrix.tolist(),
            "p_values": correlation_matrix.p_values.tolist(),
            "annotations": [
                [f"{corr:.2f}" for corr in row]
                for row in correlation_matrix.matrix
            ],
        }
    
    def get_correlation_timeline_data(
        self,
        correlation_metrics: List[CorrelationMetrics]
    ) -> Dict[str, Any]:
        """
        Get data for correlation timeline
        
        Args:
            correlation_metrics: List of correlation metrics
            
        Returns:
            Timeline data
        """
        return {
            "timestamps": [m.timestamp.isoformat() for m in correlation_metrics],
            "correlations": [m.correlation for m in correlation_metrics],
            "regimes": [m.regime.value for m in correlation_metrics],
            "confidence_lower": [m.confidence_lower for m in correlation_metrics],
            "confidence_upper": [m.confidence_upper for m in correlation_metrics],
        }
    
    # ============================================================
    # GETTER METHODS
    # ============================================================
    
    def get_correlation(
        self,
        asset1: str,
        asset2: str,
        period: Optional[int] = None
    ) -> Optional[CorrelationMetrics]:
        """
        Get cached correlation
        
        Args:
            asset1: First asset name
            asset2: Second asset name
            period: Lookback period
            
        Returns:
            CorrelationMetrics or None
        """
        if period is None:
            period = self.default_period
        
        cache_key = f"{asset1}_{asset2}_{period}"
        return self.correlation_cache.get(cache_key)
    
    def get_rolling_correlations(
        self,
        asset1: str,
        asset2: str
    ) -> List[CorrelationMetrics]:
        """
        Get rolling correlations
        
        Args:
            asset1: First asset name
            asset2: Second asset name
            
        Returns:
            List of CorrelationMetrics
        """
        cache_key = f"{asset1}_{asset2}_rolling"
        return self.rolling_correlations.get(cache_key, [])
    
    def get_regime(self) -> List[CorrelationRegimeDetector]:
        """
        Get correlation regimes
        
        Returns:
            List of CorrelationRegimeDetector
        """
        return list(self.regime_cache.values())
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_correlations": len(self.correlation_cache),
            "total_matrices": len(self.matrix_cache),
            "total_regimes": len(self.regime_cache),
            "rolling_correlations": len(self.rolling_correlations),
            "default_period": self.default_period,
            "default_method": self.default_method.value,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CorrelationMethod",
    "CorrelationRegime",
    
    # Dataclasses
    "CorrelationMetrics",
    "CorrelationMatrix",
    "CorrelationRegimeDetector",
    
    # Classes
    "CorrelationEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
