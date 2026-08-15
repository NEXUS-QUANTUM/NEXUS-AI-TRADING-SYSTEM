"""
Swing Bot Math Utilities Module
================================

This module provides mathematical utilities for the Swing Bot trading system.
Includes statistical calculations, number formatting, and mathematical helpers.
"""

import math
import statistics
import random
from typing import List, Optional, Union, Tuple, Dict, Any
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
import numpy as np
from scipy import stats


class MathUtils:
    """
    Utility class for mathematical operations.
    """
    
    @staticmethod
    def round_to(
        value: float,
        precision: int = 2,
        method: str = 'half_up'
    ) -> float:
        """
        Round a number to a specific precision.
        
        Args:
            value: Number to round
            precision: Number of decimal places
            method: Rounding method ('half_up', 'down', 'up')
        
        Returns:
            Rounded number
        """
        decimal = Decimal(str(value))
        rounding_modes = {
            'half_up': ROUND_HALF_UP,
            'down': ROUND_DOWN,
            'up': ROUND_UP
        }
        mode = rounding_modes.get(method, ROUND_HALF_UP)
        return float(decimal.quantize(Decimal('0.' + '0' * precision), rounding=mode))
    
    @staticmethod
    def clamp(value: float, min_value: float, max_value: float) -> float:
        """
        Clamp a value between minimum and maximum.
        
        Args:
            value: Value to clamp
            min_value: Minimum allowed value
            max_value: Maximum allowed value
        
        Returns:
            Clamped value
        """
        return max(min(value, max_value), min_value)
    
    @staticmethod
    def lerp(start: float, end: float, t: float) -> float:
        """
        Linear interpolation between two values.
        
        Args:
            start: Start value
            end: End value
            t: Interpolation factor (0.0 to 1.0)
        
        Returns:
            Interpolated value
        """
        t = MathUtils.clamp(t, 0.0, 1.0)
        return start + (end - start) * t
    
    @staticmethod
    def normalize(value: float, min_value: float, max_value: float) -> float:
        """
        Normalize a value to the range [0, 1].
        
        Args:
            value: Value to normalize
            min_value: Minimum value
            max_value: Maximum value
        
        Returns:
            Normalized value
        """
        if max_value == min_value:
            return 0.0
        return (value - min_value) / (max_value - min_value)
    
    @staticmethod
    def zscore(value: float, mean: float, std: float) -> float:
        """
        Calculate the z-score of a value.
        
        Args:
            value: Value
            mean: Mean of distribution
            std: Standard deviation of distribution
        
        Returns:
            Z-score
        """
        if std == 0:
            return 0.0
        return (value - mean) / std
    
    @staticmethod
    def percentile(data: List[float], p: float) -> float:
        """
        Calculate the p-th percentile of data.
        
        Args:
            data: List of numbers
            p: Percentile (0 to 100)
        
        Returns:
            Percentile value
        """
        if not data:
            return 0.0
        p = MathUtils.clamp(p, 0.0, 100.0)
        sorted_data = sorted(data)
        n = len(sorted_data)
        index = (p / 100.0) * (n - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            i = int(index)
            return sorted_data[i] + (sorted_data[i + 1] - sorted_data[i]) * (index - i)
    
    @staticmethod
    def moving_average(data: List[float], window: int) -> List[float]:
        """
        Calculate moving average of data.
        
        Args:
            data: List of numbers
            window: Window size
        
        Returns:
            List of moving averages
        """
        if not data or window <= 0:
            return []
        if window >= len(data):
            return [statistics.mean(data)]
        
        result = []
        for i in range(len(data) - window + 1):
            result.append(statistics.mean(data[i:i + window]))
        return result
    
    @staticmethod
    def exponential_moving_average(data: List[float], alpha: float) -> List[float]:
        """
        Calculate exponential moving average of data.
        
        Args:
            data: List of numbers
            alpha: Smoothing factor (0 to 1)
        
        Returns:
            List of EMA values
        """
        if not data:
            return []
        
        alpha = MathUtils.clamp(alpha, 0.0, 1.0)
        result = [data[0]]
        
        for i in range(1, len(data)):
            result.append(alpha * data[i] + (1 - alpha) * result[-1])
        
        return result
    
    @staticmethod
    def standard_deviation(data: List[float], sample: bool = True) -> float:
        """
        Calculate standard deviation of data.
        
        Args:
            data: List of numbers
            sample: True for sample, False for population
        
        Returns:
            Standard deviation
        """
        if len(data) < 2:
            return 0.0
        return statistics.stdev(data) if sample else statistics.pstdev(data)
    
    @staticmethod
    def variance(data: List[float], sample: bool = True) -> float:
        """
        Calculate variance of data.
        
        Args:
            data: List of numbers
            sample: True for sample, False for population
        
        Returns:
            Variance
        """
        if len(data) < 2:
            return 0.0
        return statistics.variance(data) if sample else statistics.pvariance(data)
    
    @staticmethod
    def correlation(x: List[float], y: List[float]) -> float:
        """
        Calculate Pearson correlation coefficient.
        
        Args:
            x: First list of numbers
            y: Second list of numbers
        
        Returns:
            Correlation coefficient
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        try:
            return statistics.correlation(x, y)
        except Exception:
            return 0.0
    
    @staticmethod
    def covariance(x: List[float], y: List[float], sample: bool = True) -> float:
        """
        Calculate covariance between two lists.
        
        Args:
            x: First list of numbers
            y: Second list of numbers
            sample: True for sample, False for population
        
        Returns:
            Covariance
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        try:
            if sample:
                return statistics.covariance(x, y)
            else:
                return statistics.covariance(x, y) * (len(x) - 1) / len(x)
        except Exception:
            return 0.0
    
    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> Tuple[float, float]:
        """
        Perform linear regression on data.
        
        Args:
            x: Independent variable
            y: Dependent variable
        
        Returns:
            Tuple of (slope, intercept)
        """
        if len(x) != len(y) or len(x) < 2:
            return (0.0, 0.0)
        
        try:
            slope, intercept = stats.linregress(x, y)[:2]
            return (slope, intercept)
        except Exception:
            return (0.0, 0.0)
    
    @staticmethod
    def r_squared(x: List[float], y: List[float]) -> float:
        """
        Calculate R-squared for linear regression.
        
        Args:
            x: Independent variable
            y: Dependent variable
        
        Returns:
            R-squared value
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        try:
            r_value = stats.linregress(x, y)[2]
            return r_value ** 2
        except Exception:
            return 0.0
    
    @staticmethod
    def p_value(x: List[float], y: List[float]) -> float:
        """
        Calculate p-value for linear regression.
        
        Args:
            x: Independent variable
            y: Dependent variable
        
        Returns:
            P-value
        """
        if len(x) != len(y) or len(x) < 2:
            return 1.0
        
        try:
            return stats.linregress(x, y)[3]
        except Exception:
            return 1.0
    
    @staticmethod
    def log_return(prices: List[float]) -> List[float]:
        """
        Calculate logarithmic returns.
        
        Args:
            prices: List of prices
        
        Returns:
            List of log returns
        """
        if len(prices) < 2:
            return []
        
        result = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                result.append(math.log(prices[i] / prices[i - 1]))
            else:
                result.append(0.0)
        return result
    
    @staticmethod
    def simple_return(prices: List[float]) -> List[float]:
        """
        Calculate simple returns.
        
        Args:
            prices: List of prices
        
        Returns:
            List of simple returns
        """
        if len(prices) < 2:
            return []
        
        result = []
        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                result.append((prices[i] - prices[i - 1]) / prices[i - 1])
            else:
                result.append(0.0)
        return result
    
    @staticmethod
    def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sharpe ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate
        
        Returns:
            Sharpe ratio
        """
        if not returns:
            return 0.0
        
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        if std_return == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / std_return
    
    @staticmethod
    def sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sortino ratio.
        
        Args:
            returns: List of returns
            risk_free_rate: Risk-free rate
        
        Returns:
            Sortino ratio
        """
        if not returns:
            return 0.0
        
        mean_return = statistics.mean(returns)
        negative_returns = [r for r in returns if r < risk_free_rate]
        
        if not negative_returns:
            return float('inf')
        
        downside_deviation = statistics.stdev(negative_returns) if len(negative_returns) > 1 else 0.0
        
        if downside_deviation == 0:
            return 0.0
        
        return (mean_return - risk_free_rate) / downside_deviation
    
    @staticmethod
    def max_drawdown(prices: List[float]) -> Tuple[float, float, int]:
        """
        Calculate maximum drawdown.
        
        Args:
            prices: List of prices
        
        Returns:
            Tuple of (drawdown, max_price, index)
        """
        if len(prices) < 2:
            return (0.0, prices[0] if prices else 0.0, 0)
        
        max_price = prices[0]
        max_drawdown = 0.0
        max_index = 0
        
        for i, price in enumerate(prices):
            if price > max_price:
                max_price = price
            else:
                drawdown = (max_price - price) / max_price
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_index = i
        
        return (max_drawdown, max_price, max_index)
    
    @staticmethod
    def volatility(returns: List[float], annualize: bool = True, periods_per_year: int = 252) -> float:
        """
        Calculate volatility of returns.
        
        Args:
            returns: List of returns
            annualize: Whether to annualize
            periods_per_year: Number of periods per year
        
        Returns:
            Volatility
        """
        if len(returns) < 2:
            return 0.0
        
        vol = statistics.stdev(returns)
        
        if annualize:
            vol = vol * math.sqrt(periods_per_year)
        
        return vol
    
    @staticmethod
    def beta(asset_returns: List[float], market_returns: List[float]) -> float:
        """
        Calculate beta coefficient.
        
        Args:
            asset_returns: Asset returns
            market_returns: Market returns
        
        Returns:
            Beta
        """
        if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
            return 1.0
        
        cov = MathUtils.covariance(asset_returns, market_returns)
        var = MathUtils.variance(market_returns)
        
        if var == 0:
            return 1.0
        
        return cov / var
    
    @staticmethod
    def alpha(asset_returns: List[float], market_returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calculate Jensen's Alpha.
        
        Args:
            asset_returns: Asset returns
            market_returns: Market returns
            risk_free_rate: Risk-free rate
        
        Returns:
            Alpha
        """
        if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
            return 0.0
        
        beta = MathUtils.beta(asset_returns, market_returns)
        asset_mean = statistics.mean(asset_returns)
        market_mean = statistics.mean(market_returns)
        
        return (asset_mean - risk_free_rate) - beta * (market_mean - risk_free_rate)
    
    @staticmethod
    def kelly_criterion(win_rate: float, win_loss_ratio: float) -> float:
        """
        Calculate Kelly Criterion percentage.
        
        Args:
            win_rate: Probability of winning (0 to 1)
            win_loss_ratio: Average win / Average loss
        
        Returns:
            Kelly percentage
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        kelly = win_rate - ((1 - win_rate) / win_loss_ratio)
        return MathUtils.clamp(kelly, 0.0, 0.25)  # Cap at 25% for safety
    
    @staticmethod
    def half_life(data: List[float]) -> float:
        """
        Calculate half-life of mean reversion.
        
        Args:
            data: Time series data
        
        Returns:
            Half-life
        """
        if len(data) < 3:
            return 0.0
        
        # Use linear regression on lagged values
        lagged = data[:-1]
        current = data[1:]
        
        slope, intercept = MathUtils.linear_regression(lagged, current)
        
        if slope >= 0:
            return float('inf')
        
        return -math.log(2) / math.log(slope)
    
    @staticmethod
    def hurst_exponent(data: List[float], max_lag: int = 100) -> float:
        """
        Calculate Hurst exponent.
        
        Args:
            data: Time series data
            max_lag: Maximum lag
        
        Returns:
            Hurst exponent
        """
        if len(data) < 10:
            return 0.5
        
        max_lag = min(max_lag, len(data) // 2)
        if max_lag < 10:
            max_lag = len(data) // 4
        
        lags = range(10, max_lag + 1, max(1, max_lag // 20))
        
        # Calculate RS values
        rs_values = []
        for lag in lags:
            # Calculate standard deviation of differences
            diffs = [data[i + lag] - data[i] for i in range(len(data) - lag)]
            if not diffs:
                continue
            
            mean_diff = statistics.mean(diffs)
            std_diff = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
            
            if std_diff == 0:
                continue
            
            # Calculate RS value
            min_diff = min(diffs)
            max_diff = max(diffs)
            rs = (max_diff - min_diff) / std_diff
            rs_values.append((math.log(lag), math.log(rs)))
        
        if len(rs_values) < 3:
            return 0.5
        
        # Linear regression on log-log plot
        x = [v[0] for v in rs_values]
        y = [v[1] for v in rs_values]
        slope, intercept = MathUtils.linear_regression(x, y)
        
        return slope
    
    @staticmethod
    def correlation_matrix(data: List[List[float]]) -> List[List[float]]:
        """
        Calculate correlation matrix for multiple time series.
        
        Args:
            data: List of time series
        
        Returns:
            Correlation matrix
        """
        n = len(data)
        if n == 0:
            return []
        
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 1.0
                elif i < j:
                    corr = MathUtils.correlation(data[i], data[j])
                    matrix[i][j] = corr
                    matrix[j][i] = corr
        
        return matrix
    
    @staticmethod
    def covariance_matrix(data: List[List[float]], sample: bool = True) -> List[List[float]]:
        """
        Calculate covariance matrix for multiple time series.
        
        Args:
            data: List of time series
            sample: True for sample, False for population
        
        Returns:
            Covariance matrix
        """
        n = len(data)
        if n == 0:
            return []
        
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = MathUtils.variance(data[i], sample)
                elif i < j:
                    cov = MathUtils.covariance(data[i], data[j], sample)
                    matrix[i][j] = cov
                    matrix[j][i] = cov
        
        return matrix
    
    @staticmethod
    def risk_parity_weights(cov_matrix: List[List[float]], tolerance: float = 1e-6) -> List[float]:
        """
        Calculate risk parity weights.
        
        Args:
            cov_matrix: Covariance matrix
            tolerance: Convergence tolerance
        
        Returns:
            Risk parity weights
        """
        n = len(cov_matrix)
        if n == 0:
            return []
        
        # Initialize equal weights
        weights = [1.0 / n] * n
        
        # Iterative optimization
        for _ in range(100):
            # Calculate portfolio variance
            portfolio_var = 0.0
            for i in range(n):
                for j in range(n):
                    portfolio_var += weights[i] * weights[j] * cov_matrix[i][j]
            
            # Calculate marginal risk contributions
            marginal_risk = [0.0] * n
            for i in range(n):
                for j in range(n):
                    marginal_risk[i] += weights[j] * cov_matrix[i][j]
                marginal_risk[i] = marginal_risk[i] / portfolio_var if portfolio_var > 0 else 1.0 / n
            
            # Calculate target weights
            target_weights = [0.0] * n
            for i in range(n):
                target_weights[i] = (1.0 / marginal_risk[i]) / sum(1.0 / mr for mr in marginal_risk if mr > 0)
            
            # Check convergence
            diff = sum(abs(weights[i] - target_weights[i]) for i in range(n))
            weights = target_weights
            
            if diff < tolerance:
                break
        
        return weights


# Function aliases for easier import
round_to = MathUtils.round_to
clamp = MathUtils.clamp
lerp = MathUtils.lerp
normalize = MathUtils.normalize
zscore = MathUtils.zscore
percentile = MathUtils.percentile
moving_average = MathUtils.moving_average
exponential_moving_average = MathUtils.exponential_moving_average
standard_deviation = MathUtils.standard_deviation
variance = MathUtils.variance
correlation = MathUtils.correlation
covariance = MathUtils.covariance
linear_regression = MathUtils.linear_regression
r_squared = MathUtils.r_squared
p_value = MathUtils.p_value
log_return = MathUtils.log_return
simple_return = MathUtils.simple_return
sharpe_ratio = MathUtils.sharpe_ratio
sortino_ratio = MathUtils.sortino_ratio
max_drawdown = MathUtils.max_drawdown
volatility = MathUtils.volatility
beta = MathUtils.beta
alpha = MathUtils.alpha
kelly_criterion = MathUtils.kelly_criterion
half_life = MathUtils.half_life
hurst_exponent = MathUtils.hurst_exponent
correlation_matrix = MathUtils.correlation_matrix
covariance_matrix = MathUtils.covariance_matrix
risk_parity_weights = MathUtils.risk_parity_weights


__all__ = [
    # Class
    'MathUtils',
    
    # Function aliases
    'round_to',
    'clamp',
    'lerp',
    'normalize',
    'zscore',
    'percentile',
    'moving_average',
    'exponential_moving_average',
    'standard_deviation',
    'variance',
    'correlation',
    'covariance',
    'linear_regression',
    'r_squared',
    'p_value',
    'log_return',
    'simple_return',
    'sharpe_ratio',
    'sortino_ratio',
    'max_drawdown',
    'volatility',
    'beta',
    'alpha',
    'kelly_criterion',
    'half_life',
    'hurst_exponent',
    'correlation_matrix',
    'covariance_matrix',
    'risk_parity_weights',
]
