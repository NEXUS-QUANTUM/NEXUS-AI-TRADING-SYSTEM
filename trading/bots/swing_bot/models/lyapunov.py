"""
Swing Bot Lyapunov Model
==========================

This module provides Lyapunov exponent analysis models for the Swing Bot trading system.
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
class LyapunovMetrics:
    """Lyapunov metrics data structure."""
    timestamp: datetime
    lyapunov_exponent: float
    max_lyapunov: float
    average_lyapunov: float
    divergence_rate: float
    predictability: float
    stability_index: float
    dimension: float
    entropy: float


@dataclass
class LyapunovSignal:
    """Lyapunov trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: LyapunovMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class LyapunovModel:
    """
    Lyapunov exponent analysis model for chaos detection.
    
    Implements Lyapunov exponent analysis for market dynamics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Lyapunov model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.embedding_dim = self.config.get('embedding_dim', 5)
        self.time_delay = self.config.get('time_delay', 1)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[LyapunovMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Lyapunov metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Lyapunov analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(df)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, df: pd.DataFrame) -> LyapunovMetrics:
        """
        Calculate Lyapunov metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            LyapunovMetrics object
        """
        close = df['close'].values
        
        # Calculate Lyapunov exponent
        lyapunov = self._calculate_lyapunov(close)
        
        # Calculate maximum Lyapunov
        max_lyapunov = self._calculate_max_lyapunov(close)
        
        # Calculate average Lyapunov
        avg_lyapunov = self._calculate_average_lyapunov(close)
        
        # Calculate divergence rate
        divergence_rate = self._calculate_divergence_rate(close)
        
        # Calculate predictability
        predictability = 1 / (1 + abs(lyapunov))
        
        # Calculate stability index
        stability_index = 1 - min(abs(lyapunov), 1.0)
        
        # Calculate dimension
        dimension = self._calculate_dimension(close)
        
        # Calculate entropy
        entropy = self._calculate_entropy(close)
        
        metrics = LyapunovMetrics(
            timestamp=datetime.now(),
            lyapunov_exponent=lyapunov,
            max_lyapunov=max_lyapunov,
            average_lyapunov=avg_lyapunov,
            divergence_rate=divergence_rate,
            predictability=predictability,
            stability_index=stability_index,
            dimension=dimension,
            entropy=entropy
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_lyapunov(self, data: np.ndarray) -> float:
        """
        Calculate Lyapunov exponent.
        
        Args:
            data: Time series data
            
        Returns:
            Lyapunov exponent
        """
        if len(data) < self.lookback_period:
            return 0.0
        
        # Embed the time series
        embedded = self._embed_series(data)
        
        if len(embedded) < 2:
            return 0.0
        
        # Find nearest neighbors and track divergence
        n_points = len(embedded)
        divergences = []
        
        for i in range(n_points - 1):
            # Find nearest neighbor
            min_dist = float('inf')
            nearest_idx = -1
            
            for j in range(n_points):
                if i != j:
                    dist = np.linalg.norm(embedded[i] - embedded[j])
                    if dist < min_dist:
                        min_dist = dist
                        nearest_idx = j
            
            if nearest_idx != -1 and min_dist > 0:
                # Track divergence over time
                for t in range(1, min(n_points - i, n_points - nearest_idx)):
                    dist1 = np.linalg.norm(embedded[i + t] - embedded[nearest_idx + t])
                    if dist1 > 0:
                        divergence = np.log(dist1 / min_dist) / t
                        divergences.append(divergence)
        
        if not divergences:
            return 0.0
        
        return np.mean(divergences)
    
    def _embed_series(self, data: np.ndarray) -> np.ndarray:
        """
        Embed time series using Takens' embedding theorem.
        
        Args:
            data: Time series data
            
        Returns:
            Embedded series
        """
        n = len(data) - self.embedding_dim + 1
        if n <= 0:
            return np.array([])
        
        embedded = np.zeros((n, self.embedding_dim))
        
        for i in range(n):
            for j in range(self.embedding_dim):
                embedded[i, j] = data[i + j * self.time_delay]
        
        return embedded
    
    def _calculate_max_lyapunov(self, data: np.ndarray) -> float:
        """
        Calculate maximum Lyapunov exponent.
        
        Args:
            data: Time series data
            
        Returns:
            Maximum Lyapunov exponent
        """
        if len(data) < self.lookback_period:
            return 0.0
        
        # Use multiple embedding dimensions
        max_lyapunov = 0.0
        
        for dim in range(2, self.embedding_dim + 2):
            self.embedding_dim = dim
            lyapunov = self._calculate_lyapunov(data)
            max_lyapunov = max(max_lyapunov, abs(lyapunov))
        
        return max_lyapunov
    
    def _calculate_average_lyapunov(self, data: np.ndarray) -> float:
        """
        Calculate average Lyapunov exponent.
        
        Args:
            data: Time series data
            
        Returns:
            Average Lyapunov exponent
        """
        if len(data) < self.lookback_period:
            return 0.0
        
        lyapunovs = []
        
        for dim in range(2, self.embedding_dim + 1):
            self.embedding_dim = dim
            lyapunov = self._calculate_lyapunov(data)
            lyapunovs.append(lyapunov)
        
        if not lyapunovs:
            return 0.0
        
        return np.mean(lyapunovs)
    
    def _calculate_divergence_rate(self, data: np.ndarray) -> float:
        """
        Calculate divergence rate.
        
        Args:
            data: Time series data
            
        Returns:
            Divergence rate
        """
        if len(data) < 50:
            return 0.0
        
        returns = np.diff(np.log(data))
        
        # Calculate divergence using rolling windows
        window_size = 20
        divergences = []
        
        for i in range(window_size, len(returns) - window_size):
            before = returns[i - window_size:i]
            after = returns[i:i + window_size]
            
            if len(before) > 0 and len(after) > 0:
                divergence = np.mean(after) / np.mean(before) - 1 if np.mean(before) != 0 else 0
                divergences.append(abs(divergence))
        
        if not divergences:
            return 0.0
        
        return np.mean(divergences)
    
    def _calculate_dimension(self, data: np.ndarray) -> float:
        """
        Calculate dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Dimension
        """
        if len(data) < self.lookback_period:
            return 0.0
        
        # Use correlation dimension approximation
        embedded = self._embed_series(data)
        
        if len(embedded) < 10:
            return 0.0
        
        # Calculate correlation integral for different radii
        radii = np.logspace(-2, 0, 10)
        correlations = []
        
        for r in radii:
            count = 0
            n = len(embedded)
            for i in range(n):
                for j in range(i + 1, n):
                    dist = np.linalg.norm(embedded[i] - embedded[j])
                    if dist < r:
                        count += 1
            
            if n > 1:
                correlations.append(count / (n * (n - 1) / 2))
            else:
                correlations.append(0)
        
        # Fit line to log-log plot
        log_radii = np.log(radii)
        log_corr = np.log(np.array(correlations) + 1e-10)
        
        valid_idx = np.isfinite(log_radii) & np.isfinite(log_corr)
        if np.sum(valid_idx) < 2:
            return 0.0
        
        slope, intercept = MathUtils.linear_regression(
            log_radii[valid_idx],
            log_corr[valid_idx]
        )
        
        return max(0, slope)
    
    def _calculate_entropy(self, data: np.ndarray) -> float:
        """
        Calculate entropy.
        
        Args:
            data: Time series data
            
        Returns:
            Entropy
        """
        if len(data) < 20:
            return 0.0
        
        returns = np.diff(np.log(data))
        
        # Calculate entropy of returns
        hist, _ = np.histogram(returns, bins=10)
        hist = hist / len(returns)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        max_entropy = np.log(10)
        
        return entropy / max_entropy if max_entropy > 0 else 0
    
    def _get_default_metrics(self) -> LyapunovMetrics:
        """
        Get default metrics.
        
        Returns:
            Default LyapunovMetrics object
        """
        return LyapunovMetrics(
            timestamp=datetime.now(),
            lyapunov_exponent=0.0,
            max_lyapunov=0.0,
            average_lyapunov=0.0,
            divergence_rate=0.0,
            predictability=0.5,
            stability_index=0.5,
            dimension=0.0,
            entropy=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: LyapunovMetrics) -> List[LyapunovSignal]:
        """
        Generate trading signals from Lyapunov metrics.
        
        Args:
            df: OHLCV data
            metrics: LyapunovMetrics object
            
        Returns:
            List of LyapunovSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check predictability
        if metrics.predictability < self.confidence_threshold:
            return signals
        
        # Generate signal based on Lyapunov metrics
        if metrics.lyapunov_exponent < 0 and metrics.stability_index > 0.7:
            signal_type = 'buy'
            reason = f"Stable system (Lyapunov: {metrics.lyapunov_exponent:.3f})"
            confidence = metrics.stability_index
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.lyapunov_exponent > 0 and metrics.stability_index < 0.3:
            signal_type = 'sell'
            reason = f"Unstable system (Lyapunov: {metrics.lyapunov_exponent:.3f})"
            confidence = 1 - metrics.stability_index
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(LyapunovSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            metrics=metrics,
            indicators={
                'lyapunov': metrics.lyapunov_exponent,
                'predictability': metrics.predictability,
                'stability': metrics.stability_index,
                'entropy': metrics.entropy,
                'dimension': metrics.dimension
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: LyapunovMetrics) -> str:
        """
        Get status from Lyapunov metrics.
        
        Args:
            metrics: LyapunovMetrics object
            
        Returns:
            Status string
        """
        if metrics.lyapunov_exponent < -0.1:
            return 'stable'
        elif metrics.lyapunov_exponent < -0.01:
            return 'moderately_stable'
        elif metrics.lyapunov_exponent < 0.01:
            return 'neutral'
        elif metrics.lyapunov_exponent < 0.1:
            return 'moderately_unstable'
        else:
            return 'unstable'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: LyapunovMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: LyapunovMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'stable': "Stable market - predictable",
            'moderately_stable': "Moderately stable market",
            'neutral': "Neutral market dynamics",
            'moderately_unstable': "Moderately unstable market",
            'unstable': "Unstable market - chaotic"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get Lyapunov metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_lyapunov': np.mean([m.lyapunov_exponent for m in self.metrics_history]),
            'average_predictability': np.mean([m.predictability for m in self.metrics_history]),
            'average_stability': np.mean([m.stability_index for m in self.metrics_history]),
            'average_entropy': np.mean([m.entropy for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_lyapunov_model(config: Optional[Dict[str, Any]] = None) -> LyapunovModel:
    """
    Create a Lyapunov model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        LyapunovModel instance
    """
    return LyapunovModel(config)


__all__ = [
    'LyapunovMetrics',
    'LyapunovSignal',
    'LyapunovModel',
    'create_lyapunov_model'
]
