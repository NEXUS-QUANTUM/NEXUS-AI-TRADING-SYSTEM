"""
Swing Bot Fractal Model
=========================

This module provides fractal analysis models for the Swing Bot trading system.
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
class FractalMetrics:
    """Fractal metrics data structure."""
    timestamp: datetime
    fractal_dimension: float
    correlation_dimension: float
    information_dimension: float
    box_counting_dimension: float
    lacunarity: float
    multifractal_spectrum: Dict[str, float]
    hurst_exponent: float
    complexity: float


@dataclass
class FractalSignal:
    """Fractal trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: FractalMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class FractalModel:
    """
    Fractal analysis model for market complexity.
    
    Implements various fractal metrics for market analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the fractal model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.embedding_dim = self.config.get('embedding_dim', 5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[FractalMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze fractal metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Fractal analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> FractalMetrics:
        """
        Calculate fractal metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            FractalMetrics object
        """
        close = df['close'].values
        
        # Calculate fractal dimension
        fractal_dim = self._calculate_fractal_dimension(close)
        
        # Calculate correlation dimension
        corr_dim = self._calculate_correlation_dimension(close)
        
        # Calculate information dimension
        info_dim = self._calculate_information_dimension(close)
        
        # Calculate box counting dimension
        box_dim = self._calculate_box_counting_dimension(close)
        
        # Calculate lacunarity
        lacunarity = self._calculate_lacunarity(close)
        
        # Calculate multifractal spectrum
        multifractal_spectrum = self._calculate_multifractal_spectrum(close)
        
        # Calculate Hurst exponent
        hurst = MathUtils.hurst_exponent(close)
        
        # Calculate complexity
        complexity = self._calculate_complexity(close)
        
        metrics = FractalMetrics(
            timestamp=datetime.now(),
            fractal_dimension=fractal_dim,
            correlation_dimension=corr_dim,
            information_dimension=info_dim,
            box_counting_dimension=box_dim,
            lacunarity=lacunarity,
            multifractal_spectrum=multifractal_spectrum,
            hurst_exponent=hurst,
            complexity=complexity
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_fractal_dimension(self, data: np.ndarray) -> float:
        """
        Calculate fractal dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Fractal dimension
        """
        if len(data) < 10:
            return 1.0
        
        # Use Higuchi's algorithm
        n = len(data)
        k_max = int(np.log10(n))
        
        log_k = []
        log_l = []
        
        for k in range(1, k_max + 1):
            l = 0
            for m in range(k):
                l_m = 0
                for i in range(m, n - k, k):
                    l_m += abs(data[i + k] - data[i])
                if l_m > 0:
                    l += l_m * (n - 1) / (k * ((n - m - 1) // k))
            if l > 0:
                log_k.append(np.log(k))
                log_l.append(np.log(l))
        
        if len(log_k) < 2:
            return 1.0
        
        slope, intercept = MathUtils.linear_regression(log_k, log_l)
        
        return slope
    
    def _calculate_correlation_dimension(self, data: np.ndarray) -> float:
        """
        Calculate correlation dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Correlation dimension
        """
        if len(data) < 20:
            return 0.0
        
        # Embed the time series
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
                embedded[i, j] = data[i + j * 1]  # Using time delay = 1
        
        return embedded
    
    def _calculate_information_dimension(self, data: np.ndarray) -> float:
        """
        Calculate information dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Information dimension
        """
        if len(data) < 20:
            return 0.0
        
        # Use box-counting with entropy
        n = len(data)
        data_min = np.min(data)
        data_max = np.max(data)
        range_size = data_max - data_min
        
        if range_size == 0:
            return 0.0
        
        # Try different box sizes
        box_sizes = np.logspace(-2, 0, 10)
        entropies = []
        
        for size in box_sizes:
            n_boxes = int(np.ceil(range_size / size))
            box_counts = np.zeros(n_boxes)
            
            for value in data:
                idx = int((value - data_min) / size)
                if idx < n_boxes:
                    box_counts[idx] += 1
            
            # Calculate Shannon entropy
            box_counts = box_counts[box_counts > 0]
            probs = box_counts / n
            entropy = -np.sum(probs * np.log(probs))
            entropies.append(entropy)
        
        if len(entropies) < 2:
            return 0.0
        
        # Fit line to log-log plot
        log_size = np.log(box_sizes)
        log_entropy = np.log(np.array(entropies) + 1e-10)
        
        valid_idx = np.isfinite(log_size) & np.isfinite(log_entropy)
        if np.sum(valid_idx) < 2:
            return 0.0
        
        slope, intercept = MathUtils.linear_regression(
            log_size[valid_idx],
            log_entropy[valid_idx]
        )
        
        return max(0, -slope)
    
    def _calculate_box_counting_dimension(self, data: np.ndarray) -> float:
        """
        Calculate box counting dimension.
        
        Args:
            data: Time series data
            
        Returns:
            Box counting dimension
        """
        if len(data) < 10:
            return 1.0
        
        n = len(data)
        data_min = np.min(data)
        data_max = np.max(data)
        range_size = data_max - data_min
        
        if range_size == 0:
            return 1.0
        
        # Try different box sizes
        box_sizes = np.logspace(-2, 0, 10)
        box_counts = []
        
        for size in box_sizes:
            n_boxes = int(np.ceil(range_size / size))
            boxes = np.zeros(n_boxes)
            
            for value in data:
                idx = int((value - data_min) / size)
                if idx < n_boxes:
                    boxes[idx] = 1
            
            box_counts.append(np.sum(boxes))
        
        # Fit line to log-log plot
        log_size = np.log(box_sizes)
        log_count = np.log(np.array(box_counts) + 1e-10)
        
        valid_idx = np.isfinite(log_size) & np.isfinite(log_count)
        if np.sum(valid_idx) < 2:
            return 1.0
        
        slope, intercept = MathUtils.linear_regression(
            log_size[valid_idx],
            log_count[valid_idx]
        )
        
        return -slope
    
    def _calculate_lacunarity(self, data: np.ndarray) -> float:
        """
        Calculate lacunarity.
        
        Args:
            data: Time series data
            
        Returns:
            Lacunarity
        """
        if len(data) < 10:
            return 0.0
        
        # Use sliding window method
        window_size = 5
        means = []
        variances = []
        
        for i in range(0, len(data) - window_size + 1, window_size):
            window = data[i:i + window_size]
            means.append(np.mean(window))
            variances.append(np.var(window))
        
        if not variances:
            return 0.0
        
        # Lacunarity = variance of means / mean of variances
        mean_of_means = np.mean(means)
        var_of_means = np.var(means)
        mean_of_variances = np.mean(variances)
        
        if mean_of_variances == 0:
            return 0.0
        
        lacunarity = var_of_means / mean_of_variances
        
        return min(lacunarity, 1.0)
    
    def _calculate_multifractal_spectrum(self, data: np.ndarray) -> Dict[str, float]:
        """
        Calculate multifractal spectrum.
        
        Args:
            data: Time series data
            
        Returns:
            Multifractal spectrum dictionary
        """
        if len(data) < 50:
            return {}
        
        # Simple multifractal analysis using q-moments
        q_values = np.linspace(-5, 5, 11)
        tau = []
        
        for q in q_values:
            if q == 0:
                continue
            moment = np.mean(data ** q)
            if moment > 0:
                tau.append(np.log(moment) / np.log(len(data)))
            else:
                tau.append(0)
        
        # Calculate multifractal spectrum
        spectrum = {}
        for i, q in enumerate(q_values):
            if q == 0:
                continue
            if i < len(tau):
                spectrum[f"q_{q:.1f}"] = tau[i]
        
        return spectrum
    
    def _calculate_complexity(self, data: np.ndarray) -> float:
        """
        Calculate complexity.
        
        Args:
            data: Time series data
            
        Returns:
            Complexity
        """
        if len(data) < 20:
            return 0.0
        
        # Use LZ complexity
        # Convert to binary string based on median
        median = np.median(data)
        binary = ''.join(['1' if x > median else '0' for x in data])
        
        # LZ complexity
        n = len(binary)
        if n == 0:
            return 0.0
        
        words = set()
        complexity = 0
        i = 0
        
        while i < n:
            found = False
            for j in range(i + 1, n + 1):
                substring = binary[i:j]
                if substring in words:
                    continue
                else:
                    words.add(substring)
                    complexity += 1
                    i = j
                    found = True
                    break
            
            if not found:
                break
        
        # Normalize
        max_complexity = n / np.log2(n) if n > 1 else 1
        
        return min(complexity / max_complexity, 1.0)
    
    def _get_default_metrics(self) -> FractalMetrics:
        """
        Get default metrics.
        
        Returns:
            Default FractalMetrics object
        """
        return FractalMetrics(
            timestamp=datetime.now(),
            fractal_dimension=1.0,
            correlation_dimension=0.0,
            information_dimension=0.0,
            box_counting_dimension=1.0,
            lacunarity=0.0,
            multifractal_spectrum={},
            hurst_exponent=0.5,
            complexity=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: FractalMetrics) -> List[FractalSignal]:
        """
        Generate trading signals from fractal metrics.
        
        Args:
            df: OHLCV data
            metrics: FractalMetrics object
            
        Returns:
            List of FractalSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check fractal dimension
        if metrics.fractal_dimension < 1.2:
            signal_type = 'buy'
            reason = f"Low fractal dimension ({metrics.fractal_dimension:.2f}) - predictable market"
            confidence = 1 - (metrics.fractal_dimension - 1) / 0.5
            confidence = min(max(confidence, 0), 1)
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.fractal_dimension > 1.8:
            signal_type = 'sell'
            reason = f"High fractal dimension ({metrics.fractal_dimension:.2f}) - chaotic market"
            confidence = (metrics.fractal_dimension - 1.5) / 0.5
            confidence = min(max(confidence, 0), 1)
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(FractalSignal(
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
                'fractal_dimension': metrics.fractal_dimension,
                'hurst_exponent': metrics.hurst_exponent,
                'correlation_dimension': metrics.correlation_dimension,
                'complexity': metrics.complexity
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: FractalMetrics) -> str:
        """
        Get status from fractal metrics.
        
        Args:
            metrics: FractalMetrics object
            
        Returns:
            Status string
        """
        if metrics.fractal_dimension < 1.2:
            return 'predictable'
        elif metrics.fractal_dimension < 1.5:
            return 'moderate'
        elif metrics.fractal_dimension < 1.8:
            return 'complex'
        else:
            return 'chaotic'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: FractalMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: FractalMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'predictable': "Predictable market - low complexity",
            'moderate': "Moderate market complexity",
            'complex': "Complex market - high fractal dimension",
            'chaotic': "Chaotic market - very high complexity"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get fractal metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_fractal_dimension': np.mean([m.fractal_dimension for m in self.metrics_history]),
            'average_hurst': np.mean([m.hurst_exponent for m in self.metrics_history]),
            'average_complexity': np.mean([m.complexity for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_fractal_model(config: Optional[Dict[str, Any]] = None) -> FractalModel:
    """
    Create a fractal model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FractalModel instance
    """
    return FractalModel(config)


__all__ = [
    'FractalMetrics',
    'FractalSignal',
    'FractalModel',
    'create_fractal_model'
]
