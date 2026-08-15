"""
Swing Bot Chaos Model
=======================

This module provides chaos theory analysis models for the Swing Bot trading system.
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
class ChaosMetrics:
    """Chaos theory metrics data structure."""
    timestamp: datetime
    lyapunov_exponent: float
    correlation_dimension: float
    kolmogorov_entropy: float
    hurst_exponent: float
    fractal_dimension: float
    predictability_score: float
    stability_index: float
    entropy_rate: float


@dataclass
class ChaosSignal:
    """Chaos trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ChaosMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ChaosModel:
    """
    Chaos theory analysis model for market dynamics.
    
    Implements chaos theory metrics for market analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the chaos model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.embedding_dim = self.config.get('embedding_dim', 5)
        self.time_delay = self.config.get('time_delay', 1)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ChaosMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze chaos metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Chaos analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> ChaosMetrics:
        """
        Calculate chaos metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            ChaosMetrics object
        """
        close = df['close'].values
        
        # Calculate Hurst exponent
        hurst = MathUtils.hurst_exponent(close)
        
        # Calculate Lyapunov exponent
        lyapunov = self._calculate_lyapunov(close)
        
        # Calculate correlation dimension
        correlation_dim = self._calculate_correlation_dimension(close)
        
        # Calculate Kolmogorov entropy
        kolmogorov = self._calculate_kolmogorov_entropy(close)
        
        # Calculate fractal dimension
        fractal_dim = self._calculate_fractal_dimension(close)
        
        # Calculate predictability score
        predictability = 1 - min(abs(lyapunov) / 2, 1.0)
        
        # Calculate stability index
        stability = 1 - min(abs(hurst - 0.5) * 2, 1.0)
        
        # Calculate entropy rate
        entropy = self._calculate_entropy_rate(close)
        
        metrics = ChaosMetrics(
            timestamp=datetime.now(),
            lyapunov_exponent=lyapunov,
            correlation_dimension=correlation_dim,
            kolmogorov_entropy=kolmogorov,
            hurst_exponent=hurst,
            fractal_dimension=fractal_dim,
            predictability_score=predictability,
            stability_index=stability,
            entropy_rate=entropy
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
        
        # Simple approximation using Rosenstein algorithm
        # This is a simplified version
        
        # Embed the time series
        embedded = self._embed_series(data)
        
        if len(embedded) < 2:
            return 0.0
        
        # Find nearest neighbors
        n_points = len(embedded)
        distances = []
        
        for i in range(n_points):
            min_dist = float('inf')
            for j in range(n_points):
                if i != j:
                    dist = np.linalg.norm(embedded[i] - embedded[j])
                    if dist < min_dist:
                        min_dist = dist
            distances.append(min_dist)
        
        # Calculate divergence
        divergences = []
        for i in range(len(distances) - 1):
            if distances[i] > 0:
                divergences.append(np.log(distances[i + 1] / distances[i]))
        
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
    
    def _calculate_correlation_dimension(self, data: np.ndarray) -> float:
        """
        Calculate correlation dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Correlation dimension
        """
        if len(data) < 100:
            return 0.0
        
        # Simple approximation using Grassberger-Procaccia algorithm
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
        log_corr = np.log(correlations + 1e-10)
        
        # Remove invalid points
        valid_idx = np.isfinite(log_radii) & np.isfinite(log_corr)
        if np.sum(valid_idx) < 2:
            return 0.0
        
        slope, intercept = MathUtils.linear_regression(
            log_radii[valid_idx],
            log_corr[valid_idx]
        )
        
        return max(0, slope)
    
    def _calculate_kolmogorov_entropy(self, data: np.ndarray) -> float:
        """
        Calculate Kolmogorov entropy.
        
        Args:
            data: Time series data
            
        Returns:
            Kolmogorov entropy
        """
        if len(data) < 100:
            return 0.0
        
        # Simple approximation using entropy rate
        embedded = self._embed_series(data)
        
        if len(embedded) < 10:
            return 0.0
        
        # Calculate entropy rate using block entropy
        block_size = 10
        n_blocks = len(embedded) // block_size
        
        if n_blocks < 2:
            return 0.0
        
        # Calculate entropy for different block sizes
        entropies = []
        
        for m in range(1, min(block_size, n_blocks)):
            # Create blocks
            blocks = []
            for i in range(n_blocks - m + 1):
                block = embedded[i:i + m]
                blocks.append(block.tobytes())  # Simple hash
            
            # Calculate entropy
            unique_blocks = len(set(blocks))
            if n_blocks - m + 1 > 0:
                entropy = np.log(unique_blocks) / (n_blocks - m + 1)
                entropies.append(entropy)
        
        if not entropies:
            return 0.0
        
        return np.mean(entropies)
    
    def _calculate_fractal_dimension(self, data: np.ndarray) -> float:
        """
        Calculate fractal dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Fractal dimension
        """
        if len(data) < 10:
            return 0.0
        
        # Simple approximation using box-counting method
        # This is a simplified version
        epsilon = 0.01
        n_points = len(data)
        distances = []
        
        for i in range(n_points):
            for j in range(i + 1, n_points):
                distances.append(abs(data[i] - data[j]))
        
        if not distances:
            return 0.0
        
        distances = np.array(distances)
        counts = []
        epsilons = np.logspace(-2, 0, 10)
        
        for eps in epsilons:
            count = np.sum(distances < eps)
            counts.append(count)
        
        # Fit line to log-log plot
        log_eps = np.log(epsilons)
        log_counts = np.log(np.array(counts) + 1e-10)
        
        valid_idx = np.isfinite(log_eps) & np.isfinite(log_counts)
        if np.sum(valid_idx) < 2:
            return 0.0
        
        slope, intercept = MathUtils.linear_regression(
            log_eps[valid_idx],
            log_counts[valid_idx]
        )
        
        return max(0, slope)
    
    def _calculate_entropy_rate(self, data: np.ndarray) -> float:
        """
        Calculate entropy rate.
        
        Args:
            data: Time series data
            
        Returns:
            Entropy rate
        """
        if len(data) < 20:
            return 0.0
        
        # Simple approximation using approximate entropy
        m = 2
        r = 0.2 * np.std(data)
        
        if r == 0:
            return 0.0
        
        # Calculate approximate entropy
        def _approx_entropy(seq, m, r):
            n = len(seq)
            if n - m + 1 <= 1:
                return 0.0
            
            # Build vectors
            vectors = []
            for i in range(n - m + 1):
                vectors.append(seq[i:i + m])
            
            # Count matches
            matches = []
            for i, v1 in enumerate(vectors):
                count = 0
                for j, v2 in enumerate(vectors):
                    if i != j:
                        if np.max(np.abs(v1 - v2)) < r:
                            count += 1
                if len(vectors) > 1:
                    matches.append(count / (len(vectors) - 1))
                else:
                    matches.append(0)
            
            if len(matches) == 0:
                return 0.0
            
            return np.mean([np.log(m + 1e-10) for m in matches])
        
        # Calculate approximate entropy for m and m+1
        ae_m = _approx_entropy(data, m, r)
        ae_m1 = _approx_entropy(data, m + 1, r)
        
        if ae_m == 0:
            return 0.0
        
        return ae_m - ae_m1
    
    def _get_default_metrics(self) -> ChaosMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ChaosMetrics object
        """
        return ChaosMetrics(
            timestamp=datetime.now(),
            lyapunov_exponent=0.0,
            correlation_dimension=0.0,
            kolmogorov_entropy=0.0,
            hurst_exponent=0.5,
            fractal_dimension=0.0,
            predictability_score=0.5,
            stability_index=0.5,
            entropy_rate=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: ChaosMetrics) -> List[ChaosSignal]:
        """
        Generate trading signals from chaos metrics.
        
        Args:
            df: OHLCV data
            metrics: ChaosMetrics object
            
        Returns:
            List of ChaosSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check predictability
        predictability = metrics.predictability_score
        
        if predictability < self.confidence_threshold:
            return signals
        
        # Determine signal based on chaos metrics
        hurst = metrics.hurst_exponent
        lyapunov = metrics.lyapunov_exponent
        
        if hurst > 0.6 and lyapunov < 0.1:
            signal_type = 'buy'
            reason = "High predictability and stability detected"
            confidence = predictability
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif hurst < 0.4 and lyapunov > 0.2:
            signal_type = 'sell'
            reason = "Low predictability and instability detected"
            confidence = predictability
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(ChaosSignal(
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
                'hurst': hurst,
                'lyapunov': lyapunov,
                'stability': metrics.stability_index,
                'entropy': metrics.entropy_rate
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: ChaosMetrics) -> str:
        """
        Get status from chaos metrics.
        
        Args:
            metrics: ChaosMetrics object
            
        Returns:
            Status string
        """
        if metrics.hurst_exponent > 0.6 and metrics.lyapunov_exponent < 0.1:
            return 'predictable'
        elif metrics.hurst_exponent < 0.4 and metrics.lyapunov_exponent > 0.2:
            return 'chaotic'
        else:
            return 'transitional'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: ChaosMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: ChaosMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'predictable': 'Predictable market with strong trend',
            'chaotic': 'Chaotic market with high uncertainty',
            'transitional': 'Transitional market with moderate uncertainty'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get chaos metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_hurst': np.mean([m.hurst_exponent for m in self.metrics_history]),
            'average_lyapunov': np.mean([m.lyapunov_exponent for m in self.metrics_history]),
            'average_predictability': np.mean([m.predictability_score for m in self.metrics_history]),
            'average_stability': np.mean([m.stability_index for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_chaos_model(config: Optional[Dict[str, Any]] = None) -> ChaosModel:
    """
    Create a chaos model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ChaosModel instance
    """
    return ChaosModel(config)


__all__ = [
    'ChaosMetrics',
    'ChaosSignal',
    'ChaosModel',
    'create_chaos_model'
]
