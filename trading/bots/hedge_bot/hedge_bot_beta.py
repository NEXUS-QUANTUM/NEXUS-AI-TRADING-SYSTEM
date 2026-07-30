# trading/bots/hedge_bot/hedge_bot_beta.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Beta Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Beta Module

This module provides comprehensive beta calculation and analysis
capabilities for the NEXUS Hedge Bot system. It covers various
beta metrics, volatility analysis, and correlation measurements.

The module covers:
- Beta Calculation
- Volatility Analysis
- Correlation Analysis
- Beta Regression Models
- Rolling Beta
- Conditional Beta
- Downside Beta
- Upside Beta
- Beta Regime Detection
- Portfolio Beta
- Sector Beta
- Factor Beta
- Beta Forecasting
"""

import os
import sys
import json
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from scipy import stats
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


# ============================================================
# BETA ENUMS
# ============================================================

class BetaMethod(Enum):
    """Beta calculation methods"""
    OLS = "ols"
    RIDGE = "ridge"
    LASSO = "lasso"
    ROBUST = "robust"
    BAYESIAN = "bayesian"
    ROLLING = "rolling"
    EWMA = "ewma"
    CONDITIONAL = "conditional"


class BetaType(Enum):
    """Beta types"""
    HISTORICAL = "historical"
    FORWARD = "forward"
    DOWNSIDE = "downside"
    UPSIDE = "upside"
    CONDITIONAL = "conditional"
    ROLLING = "rolling"
    SECTOR = "sector"
    FACTOR = "factor"
    PORTFOLIO = "portfolio"


# ============================================================
# BETA DATACLASSES
# ============================================================

@dataclass
class BetaMetrics:
    """Beta metrics"""
    symbol: str
    beta: float
    alpha: float
    r_squared: float
    p_value: float
    standard_error: float
    confidence_lower: float
    confidence_upper: float
    method: BetaMethod
    period: int
    benchmark: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "beta": self.beta,
            "alpha": self.alpha,
            "r_squared": self.r_squared,
            "p_value": self.p_value,
            "standard_error": self.standard_error,
            "confidence_lower": self.confidence_lower,
            "confidence_upper": self.confidence_upper,
            "method": self.method.value,
            "period": self.period,
            "benchmark": self.benchmark,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class BetaRegime:
    """Beta regime"""
    name: str
    beta: float
    alpha: float
    volatility: float
    correlation: float
    start_date: datetime
    end_date: datetime
    condition: str
    data_points: int
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "beta": self.beta,
            "alpha": self.alpha,
            "volatility": self.volatility,
            "correlation": self.correlation,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "condition": self.condition,
            "data_points": self.data_points,
            "details": self.details,
        }


@dataclass
class VolatilityMetrics:
    """Volatility metrics"""
    symbol: str
    historical_vol: float
    realized_vol: float
    implied_vol: float
    ewma_vol: float
    rolling_vol: float
    volatility_of_vol: float
    skewness: float
    kurtosis: float
    period: int
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "historical_vol": self.historical_vol,
            "realized_vol": self.realized_vol,
            "implied_vol": self.implied_vol,
            "ewma_vol": self.ewma_vol,
            "rolling_vol": self.rolling_vol,
            "volatility_of_vol": self.volatility_of_vol,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "period": self.period,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class CorrelationMetrics:
    """Correlation metrics"""
    asset1: str
    asset2: str
    correlation: float
    p_value: float
    covariance: float
    period: int
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "asset1": self.asset1,
            "asset2": self.asset2,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "covariance": self.covariance,
            "period": self.period,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


# ============================================================
# BETA ENGINE
# ============================================================

class BetaEngine:
    """
    Comprehensive beta calculation engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the beta engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_period = self.config.get("default_period", 252)
        self.default_benchmark = self.config.get("default_benchmark", "SPY")
        self.risk_free_rate = self.config.get("risk_free_rate", 0.04)
        
        # Cache
        self.beta_cache: Dict[str, BetaMetrics] = {}
        self.volatility_cache: Dict[str, VolatilityMetrics] = {}
        self.correlation_cache: Dict[str, CorrelationMetrics] = {}
        self.regime_cache: Dict[str, List[BetaRegime]] = {}
        
        logger.info("Beta engine initialized")
    
    # ============================================================
    # BETA CALCULATION
    # ============================================================
    
    def calculate_beta(
        self,
        returns: Union[List[float], np.ndarray],
        benchmark_returns: Union[List[float], np.ndarray],
        method: BetaMethod = BetaMethod.OLS,
        period: Optional[int] = None,
        benchmark: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> BetaMetrics:
        """
        Calculate beta
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            method: Calculation method
            period: Lookback period
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            BetaMetrics
        """
        if period is None:
            period = self.default_period
        
        if benchmark is None:
            benchmark = self.default_benchmark
        
        if symbol is None:
            symbol = "unknown"
        
        # Convert to numpy arrays
        if isinstance(returns, list):
            returns = np.array(returns)
        if isinstance(benchmark_returns, list):
            benchmark_returns = np.array(benchmark_returns)
        
        # Trim to period
        if len(returns) > period:
            returns = returns[-period:]
            benchmark_returns = benchmark_returns[-period:]
        
        # Calculate beta based on method
        if method == BetaMethod.OLS:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._ols_beta(
                returns, benchmark_returns
            )
        elif method == BetaMethod.RIDGE:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._ridge_beta(
                returns, benchmark_returns
            )
        elif method == BetaMethod.LASSO:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._lasso_beta(
                returns, benchmark_returns
            )
        elif method == BetaMethod.ROBUST:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._robust_beta(
                returns, benchmark_returns
            )
        elif method == BetaMethod.EWMA:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._ewma_beta(
                returns, benchmark_returns
            )
        else:
            beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper = self._ols_beta(
                returns, benchmark_returns
            )
        
        metrics = BetaMetrics(
            symbol=symbol,
            beta=beta,
            alpha=alpha,
            r_squared=r_squared,
            p_value=p_value,
            standard_error=std_err,
            confidence_lower=ci_lower,
            confidence_upper=ci_upper,
            method=method,
            period=period,
            benchmark=benchmark,
            details={
                "n_observations": len(returns),
                "returns_mean": float(np.mean(returns)),
                "benchmark_mean": float(np.mean(benchmark_returns)),
                "returns_std": float(np.std(returns)),
                "benchmark_std": float(np.std(benchmark_returns)),
            }
        )
        
        self.beta_cache[f"{symbol}_{benchmark}_{period}"] = metrics
        return metrics
    
    def _ols_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculate beta using OLS regression
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            
        Returns:
            (beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper)
        """
        if len(returns) < 2:
            return 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0
        
        # Prepare data
        X = benchmark_returns.reshape(-1, 1)
        y = returns
        
        # Fit regression
        reg = LinearRegression()
        reg.fit(X, y)
        
        beta = reg.coef_[0]
        alpha = reg.intercept_
        
        # Calculate R-squared
        y_pred = reg.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Calculate standard error
        n = len(returns)
        residual = y - y_pred
        se = np.sqrt(np.sum(residual ** 2) / (n - 2)) / np.sqrt(np.sum((X - np.mean(X)) ** 2))
        std_err = se.item() if hasattr(se, 'item') else se
        
        # Calculate t-statistic and p-value
        t_stat = beta / std_err if std_err > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
        
        # Confidence intervals (95%)
        t_crit = stats.t.ppf(0.975, n - 2)
        ci_lower = beta - t_crit * std_err
        ci_upper = beta + t_crit * std_err
        
        return (
            float(beta),
            float(alpha),
            float(r_squared),
            float(p_value),
            float(std_err),
            float(ci_lower),
            float(ci_upper)
        )
    
    def _ridge_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        alpha: float = 1.0
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculate beta using Ridge regression
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            alpha: Regularization parameter
            
        Returns:
            (beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper)
        """
        if len(returns) < 2:
            return 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0
        
        X = benchmark_returns.reshape(-1, 1)
        y = returns
        
        reg = Ridge(alpha=alpha)
        reg.fit(X, y)
        
        beta = reg.coef_[0]
        alpha_val = reg.intercept_
        
        y_pred = reg.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Approximate standard error
        n = len(returns)
        residual = y - y_pred
        se = np.sqrt(np.sum(residual ** 2) / (n - 2)) / np.sqrt(np.sum((X - np.mean(X)) ** 2))
        std_err = se.item() if hasattr(se, 'item') else se
        
        t_stat = beta / std_err if std_err > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
        
        t_crit = stats.t.ppf(0.975, n - 2)
        ci_lower = beta - t_crit * std_err
        ci_upper = beta + t_crit * std_err
        
        return (
            float(beta),
            float(alpha_val),
            float(r_squared),
            float(p_value),
            float(std_err),
            float(ci_lower),
            float(ci_upper)
        )
    
    def _lasso_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        alpha: float = 0.01
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculate beta using Lasso regression
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            alpha: Regularization parameter
            
        Returns:
            (beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper)
        """
        if len(returns) < 2:
            return 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0
        
        X = benchmark_returns.reshape(-1, 1)
        y = returns
        
        reg = Lasso(alpha=alpha)
        reg.fit(X, y)
        
        beta = reg.coef_[0]
        alpha_val = reg.intercept_
        
        y_pred = reg.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        n = len(returns)
        residual = y - y_pred
        se = np.sqrt(np.sum(residual ** 2) / (n - 2)) / np.sqrt(np.sum((X - np.mean(X)) ** 2))
        std_err = se.item() if hasattr(se, 'item') else se
        
        t_stat = beta / std_err if std_err > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
        
        t_crit = stats.t.ppf(0.975, n - 2)
        ci_lower = beta - t_crit * std_err
        ci_upper = beta + t_crit * std_err
        
        return (
            float(beta),
            float(alpha_val),
            float(r_squared),
            float(p_value),
            float(std_err),
            float(ci_lower),
            float(ci_upper)
        )
    
    def _robust_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculate beta using robust regression
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            
        Returns:
            (beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper)
        """
        if len(returns) < 2:
            return 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0
        
        # Use Theil-Sen estimator
        from sklearn.linear_model import TheilSenRegressor
        
        X = benchmark_returns.reshape(-1, 1)
        y = returns
        
        reg = TheilSenRegressor()
        reg.fit(X, y)
        
        beta = reg.coef_[0]
        alpha_val = reg.intercept_
        
        y_pred = reg.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        n = len(returns)
        residual = y - y_pred
        se = np.sqrt(np.sum(residual ** 2) / (n - 2)) / np.sqrt(np.sum((X - np.mean(X)) ** 2))
        std_err = se.item() if hasattr(se, 'item') else se
        
        t_stat = beta / std_err if std_err > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
        
        t_crit = stats.t.ppf(0.975, n - 2)
        ci_lower = beta - t_crit * std_err
        ci_upper = beta + t_crit * std_err
        
        return (
            float(beta),
            float(alpha_val),
            float(r_squared),
            float(p_value),
            float(std_err),
            float(ci_lower),
            float(ci_upper)
        )
    
    def _ewma_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        lambda_val: float = 0.94
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Calculate beta using EWMA
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            lambda_val: Decay factor
            
        Returns:
            (beta, alpha, r_squared, p_value, std_err, ci_lower, ci_upper)
        """
        if len(returns) < 2:
            return 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0
        
        # Calculate EWMA weights
        n = len(returns)
        weights = np.array([(1 - lambda_val) * lambda_val ** (n - 1 - i) for i in range(n)])
        weights = weights / np.sum(weights)
        
        # Weighted regression
        X = benchmark_returns.reshape(-1, 1)
        y = returns
        
        # Weighted mean
        mean_x = np.average(X, weights=weights)
        mean_y = np.average(y, weights=weights)
        
        # Weighted covariance and variance
        cov = np.sum(weights * (X - mean_x) * (y - mean_y))
        var_x = np.sum(weights * (X - mean_x) ** 2)
        
        beta = cov / var_x if var_x > 0 else 0
        alpha_val = mean_y - beta * mean_x
        
        # Calculate R-squared
        y_pred = beta * X + alpha_val
        ss_res = np.sum(weights * (y - y_pred) ** 2)
        ss_tot = np.sum(weights * (y - mean_y) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Approximate standard error
        residual = y - y_pred
        se = np.sqrt(np.sum(weights * residual ** 2) / (n - 2)) / np.sqrt(np.sum(weights * (X - mean_x) ** 2))
        std_err = se.item() if hasattr(se, 'item') else se
        
        t_stat = beta / std_err if std_err > 0 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))
        
        t_crit = stats.t.ppf(0.975, n - 2)
        ci_lower = beta - t_crit * std_err
        ci_upper = beta + t_crit * std_err
        
        return (
            float(beta),
            float(alpha_val),
            float(r_squared),
            float(p_value),
            float(std_err),
            float(ci_lower),
            float(ci_upper)
        )
    
    # ============================================================
    # ROLLING BETA
    # ============================================================
    
    def calculate_rolling_beta(
        self,
        returns: Union[List[float], np.ndarray],
        benchmark_returns: Union[List[float], np.ndarray],
        window: int = 60,
        benchmark: str = "SPY",
        symbol: str = "unknown"
    ) -> List[BetaMetrics]:
        """
        Calculate rolling beta
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            window: Rolling window
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            List of BetaMetrics
        """
        if isinstance(returns, list):
            returns = np.array(returns)
        if isinstance(benchmark_returns, list):
            benchmark_returns = np.array(benchmark_returns)
        
        results = []
        
        for i in range(window, len(returns)):
            period_returns = returns[i-window:i]
            period_benchmark = benchmark_returns[i-window:i]
            
            try:
                beta_metrics = self.calculate_beta(
                    period_returns,
                    period_benchmark,
                    method=BetaMethod.OLS,
                    period=window,
                    benchmark=benchmark,
                    symbol=symbol
                )
                beta_metrics.details["date"] = datetime.now().isoformat()
                results.append(beta_metrics)
            except:
                continue
        
        return results
    
    # ============================================================
    # CONDITIONAL BETA
    # ============================================================
    
    def calculate_conditional_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        condition: np.ndarray,
        condition_value: float,
        condition_operator: str = ">",
        period: int = 252,
        benchmark: str = "SPY",
        symbol: str = "unknown"
    ) -> BetaMetrics:
        """
        Calculate conditional beta
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            condition: Condition array (e.g., market returns)
            condition_value: Condition threshold
            condition_operator: Comparison operator
            period: Lookback period
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            BetaMetrics
        """
        if len(returns) > period:
            returns = returns[-period:]
            benchmark_returns = benchmark_returns[-period:]
            condition = condition[-period:]
        
        # Apply condition
        if condition_operator == ">":
            mask = condition > condition_value
        elif condition_operator == "<":
            mask = condition < condition_value
        elif condition_operator == ">=":
            mask = condition >= condition_value
        elif condition_operator == "<=":
            mask = condition <= condition_value
        elif condition_operator == "==":
            mask = condition == condition_value
        else:
            mask = condition > condition_value
        
        filtered_returns = returns[mask]
        filtered_benchmark = benchmark_returns[mask]
        
        if len(filtered_returns) < 10:
            raise ValueError("Insufficient data for conditional beta")
        
        return self.calculate_beta(
            filtered_returns,
            filtered_benchmark,
            method=BetaMethod.OLS,
            period=len(filtered_returns),
            benchmark=benchmark,
            symbol=symbol
        )
    
    # ============================================================
    # DOWNSIDE/UPSIDE BETA
    # ============================================================
    
    def calculate_downside_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        threshold: float = 0.0,
        period: int = 252,
        benchmark: str = "SPY",
        symbol: str = "unknown"
    ) -> BetaMetrics:
        """
        Calculate downside beta (beta when benchmark returns are below threshold)
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            threshold: Return threshold
            period: Lookback period
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            BetaMetrics
        """
        return self.calculate_conditional_beta(
            returns,
            benchmark_returns,
            benchmark_returns,
            threshold,
            "<",
            period,
            benchmark,
            symbol
        )
    
    def calculate_upside_beta(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        threshold: float = 0.0,
        period: int = 252,
        benchmark: str = "SPY",
        symbol: str = "unknown"
    ) -> BetaMetrics:
        """
        Calculate upside beta (beta when benchmark returns are above threshold)
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            threshold: Return threshold
            period: Lookback period
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            BetaMetrics
        """
        return self.calculate_conditional_beta(
            returns,
            benchmark_returns,
            benchmark_returns,
            threshold,
            ">",
            period,
            benchmark,
            symbol
        )
    
    # ============================================================
    # BETA REGIME DETECTION
    # ============================================================
    
    def detect_beta_regimes(
        self,
        returns: np.ndarray,
        benchmark_returns: np.ndarray,
        window: int = 60,
        min_regime_length: int = 30,
        benchmark: str = "SPY",
        symbol: str = "unknown"
    ) -> List[BetaRegime]:
        """
        Detect beta regimes
        
        Args:
            returns: Asset returns
            benchmark_returns: Benchmark returns
            window: Rolling window
            min_regime_length: Minimum regime length
            benchmark: Benchmark name
            symbol: Asset symbol
            
        Returns:
            List of BetaRegime
        """
        if len(returns) < window:
            return []
        
        regimes = []
        current_regime = None
        start_date = datetime.now()
        
        for i in range(window, len(returns)):
            period_returns = returns[i-window:i]
            period_benchmark = benchmark_returns[i-window:i]
            
            beta = self.calculate_beta(
                period_returns,
                period_benchmark,
                period=window,
                benchmark=benchmark,
                symbol=symbol
            )
            
            # Determine regime based on beta value
            regime_name = "neutral"
            if beta.beta > 1.2:
                regime_name = "high_beta"
            elif beta.beta < 0.8:
                regime_name = "low_beta"
            elif beta.beta < 0.5:
                regime_name = "defensive"
            
            if current_regime is None:
                current_regime = regime_name
                start_date = datetime.now() - timedelta(days=window)
            elif regime_name != current_regime:
                # End current regime
                end_date = datetime.now()
                if (end_date - start_date).days >= min_regime_length:
                    regime = BetaRegime(
                        name=current_regime,
                        beta=beta.beta,
                        alpha=beta.alpha,
                        volatility=np.std(period_returns),
                        correlation=np.corrcoef(period_returns, period_benchmark)[0, 1],
                        start_date=start_date,
                        end_date=end_date,
                        condition=f"beta_{current_regime}",
                        data_points=window,
                    )
                    regimes.append(regime)
                
                # Start new regime
                current_regime = regime_name
                start_date = datetime.now()
        
        # Add final regime
        if current_regime:
            end_date = datetime.now()
            if (end_date - start_date).days >= min_regime_length:
                beta = self.calculate_beta(
                    returns[-window:],
                    benchmark_returns[-window:],
                    period=window,
                    benchmark=benchmark,
                    symbol=symbol
                )
                regime = BetaRegime(
                    name=current_regime,
                    beta=beta.beta,
                    alpha=beta.alpha,
                    volatility=np.std(returns[-window:]),
                    correlation=np.corrcoef(returns[-window:], benchmark_returns[-window:])[0, 1],
                    start_date=start_date,
                    end_date=end_date,
                    condition=f"beta_{current_regime}",
                    data_points=window,
                )
                regimes.append(regime)
        
        self.regime_cache[f"{symbol}_{benchmark}"] = regimes
        return regimes
    
    # ============================================================
    # VOLATILITY CALCULATION
    # ============================================================
    
    def calculate_volatility(
        self,
        returns: np.ndarray,
        period: int = 252,
        symbol: str = "unknown",
        annualize: bool = True
    ) -> VolatilityMetrics:
        """
        Calculate volatility metrics
        
        Args:
            returns: Asset returns
            period: Lookback period
            symbol: Asset symbol
            annualize: Annualize volatility
            
        Returns:
            VolatilityMetrics
        """
        if len(returns) > period:
            returns = returns[-period:]
        
        hist_vol = np.std(returns)
        if annualize:
            hist_vol = hist_vol * np.sqrt(252)
        
        # EWMA volatility
        lambda_val = 0.94
        ewma_vol = self._calculate_ewma_volatility(returns, lambda_val, annualize)
        
        # Rolling volatility
        rolling_vol = self._calculate_rolling_volatility(returns, 20, annualize)
        
        # Volatility of volatility
        vol_of_vol = self._calculate_volatility_of_volatility(returns, 20, annualize)
        
        # Skewness and kurtosis
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        
        return VolatilityMetrics(
            symbol=symbol,
            historical_vol=hist_vol,
            realized_vol=hist_vol,
            implied_vol=0.0,
            ewma_vol=ewma_vol,
            rolling_vol=rolling_vol,
            volatility_of_vol=vol_of_vol,
            skewness=skewness,
            kurtosis=kurtosis,
            period=period,
            details={
                "annualized": annualize,
                "n_observations": len(returns),
                "mean_return": float(np.mean(returns)),
            }
        )
    
    def _calculate_ewma_volatility(
        self,
        returns: np.ndarray,
        lambda_val: float,
        annualize: bool
    ) -> float:
        """Calculate EWMA volatility"""
        if len(returns) < 2:
            return 0.0
        
        variance = np.var(returns)
        for ret in returns:
            variance = lambda_val * variance + (1 - lambda_val) * ret ** 2
        
        vol = np.sqrt(variance)
        if annualize:
            vol = vol * np.sqrt(252)
        
        return float(vol)
    
    def _calculate_rolling_volatility(
        self,
        returns: np.ndarray,
        window: int,
        annualize: bool
    ) -> float:
        """Calculate rolling volatility"""
        if len(returns) < window:
            return 0.0
        
        rolling_vols = []
        for i in range(window, len(returns) + 1):
            vol = np.std(returns[i-window:i])
            if annualize:
                vol = vol * np.sqrt(252)
            rolling_vols.append(vol)
        
        return float(np.mean(rolling_vols)) if rolling_vols else 0.0
    
    def _calculate_volatility_of_volatility(
        self,
        returns: np.ndarray,
        window: int,
        annualize: bool
    ) -> float:
        """Calculate volatility of volatility"""
        if len(returns) < window:
            return 0.0
        
        rolling_vols = []
        for i in range(window, len(returns) + 1):
            vol = np.std(returns[i-window:i])
            rolling_vols.append(vol)
        
        if len(rolling_vols) < 2:
            return 0.0
        
        vol_of_vol = np.std(rolling_vols)
        if annualize:
            vol_of_vol = vol_of_vol * np.sqrt(252)
        
        return float(vol_of_vol)
    
    # ============================================================
    # CORRELATION CALCULATION
    # ============================================================
    
    def calculate_correlation(
        self,
        returns1: np.ndarray,
        returns2: np.ndarray,
        period: int = 252,
        asset1: str = "unknown",
        asset2: str = "unknown"
    ) -> CorrelationMetrics:
        """
        Calculate correlation between two assets
        
        Args:
            returns1: First asset returns
            returns2: Second asset returns
            period: Lookback period
            asset1: First asset name
            asset2: Second asset name
            
        Returns:
            CorrelationMetrics
        """
        if len(returns1) > period:
            returns1 = returns1[-period:]
            returns2 = returns2[-period:]
        
        correlation = np.corrcoef(returns1, returns2)[0, 1]
        p_value = stats.pearsonr(returns1, returns2)[1]
        covariance = np.cov(returns1, returns2)[0, 1]
        
        return CorrelationMetrics(
            asset1=asset1,
            asset2=asset2,
            correlation=correlation,
            p_value=p_value,
            covariance=covariance,
            period=period,
            details={
                "n_observations": len(returns1),
            }
        )
    
    # ============================================================
    # GETTER METHODS
    # ============================================================
    
    def get_beta(
        self,
        symbol: str,
        benchmark: str = "SPY",
        period: int = 252
    ) -> Optional[BetaMetrics]:
        """
        Get cached beta
        
        Args:
            symbol: Asset symbol
            benchmark: Benchmark name
            period: Lookback period
            
        Returns:
            BetaMetrics or None
        """
        key = f"{symbol}_{benchmark}_{period}"
        return self.beta_cache.get(key)
    
    def get_regimes(
        self,
        symbol: str,
        benchmark: str = "SPY"
    ) -> List[BetaRegime]:
        """
        Get cached beta regimes
        
        Args:
            symbol: Asset symbol
            benchmark: Benchmark name
            
        Returns:
            List of BetaRegime
        """
        key = f"{symbol}_{benchmark}"
        return self.regime_cache.get(key, [])
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get beta engine statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_beta_calculations": len(self.beta_cache),
            "total_volatility_calculations": len(self.volatility_cache),
            "total_correlation_calculations": len(self.correlation_cache),
            "total_regime_detections": len(self.regime_cache),
            "default_period": self.default_period,
            "default_benchmark": self.default_benchmark,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BetaMethod",
    "BetaType",
    
    # Dataclasses
    "BetaMetrics",
    "BetaRegime",
    "VolatilityMetrics",
    "CorrelationMetrics",
    
    # Classes
    "BetaEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
