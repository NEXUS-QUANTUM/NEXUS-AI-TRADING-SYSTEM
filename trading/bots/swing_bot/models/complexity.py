"""
Swing Bot Complexity Model
============================

This module provides complexity analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ComplexityMetrics:
    """Complexity metrics data structure."""
    timestamp: datetime
    algorithmic_complexity: float
    structural_complexity: float
    informational_complexity: float
    computational_complexity: float
    lz_complexity: float
    kolmogorov_complexity: float
    entropy: float
    dimensionality: float


@dataclass
class ComplexitySignal:
    """Complexity trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ComplexityMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ComplexityModel:
    """
    Complexity analysis model for market dynamics.
    
    Implements various complexity metrics for market analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the complexity model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ComplexityMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze complexity metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Complexity analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> ComplexityMetrics:
        """
        Calculate complexity metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            ComplexityMetrics object
        """
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate algorithmic complexity
        algorithmic = self._calculate_algorithmic_complexity(close)
        
        # Calculate structural complexity
        structural = self._calculate_structural_complexity(close)
        
        # Calculate informational complexity
        informational = self._calculate_informational_complexity(close)
        
        # Calculate computational complexity
        computational = self._calculate_computational_complexity(close)
        
        # Calculate LZ complexity
        lz_complexity = self._calculate_lz_complexity(close)
        
        # Calculate Kolmogorov complexity (approximation)
        kolmogorov = self._calculate_kolmogorov_complexity(close)
        
        # Calculate entropy
        entropy = self._calculate_entropy(close)
        
        # Calculate dimensionality
        dimensionality = self._calculate_dimensionality(close)
        
        metrics = ComplexityMetrics(
            timestamp=datetime.now(),
            algorithmic_complexity=algorithmic,
            structural_complexity=structural,
            informational_complexity=informational,
            computational_complexity=computational,
            lz_complexity=lz_complexity,
            kolmogorov_complexity=kolmogorov,
            entropy=entropy,
            dimensionality=dimensionality
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_algorithmic_complexity(self, data: np.ndarray) -> float:
        """
        Calculate algorithmic complexity.
        
        Args:
            data: Time series data
            
        Returns:
            Algorithmic complexity (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        # Use derivative as measure of complexity
        derivatives = np.diff(data)
        complexity = np.std(derivatives) / (np.mean(np.abs(derivatives)) + 1e-10)
        
        return min(complexity, 1.0)
    
    def _calculate_structural_complexity(self, data: np.ndarray) -> float:
        """
        Calculate structural complexity.
        
        Args:
            data: Time series data
            
        Returns:
            Structural complexity (0-1)
        """
        if len(data) < 20:
            return 0.5
        
        # Calculate recurrence of patterns
        n = len(data)
        recurrence = 0
        total = 0
        
        for i in range(n - 10):
            for j in range(i + 1, n - 10):
                pattern_i = data[i:i+10]
                pattern_j = data[j:j+10]
                
                if np.allclose(pattern_i, pattern_j, rtol=0.1):
                    recurrence += 1
                total += 1
        
        if total == 0:
            return 0.5
        
        structural = 1 - recurrence / total
        
        return max(0, min(1, structural))
    
    def _calculate_informational_complexity(self, data: np.ndarray) -> float:
        """
        Calculate informational complexity.
        
        Args:
            data: Time series data
            
        Returns:
            Informational complexity (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        # Use Shannon entropy
        hist, _ = np.histogram(data, bins=10)
        hist = hist / len(data)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        max_entropy = np.log(10)
        
        return entropy / max_entropy
    
    def _calculate_computational_complexity(self, data: np.ndarray) -> float:
        """
        Calculate computational complexity.
        
        Args:
            data: Time series data
            
        Returns:
            Computational complexity (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        # Calculate complexity based on prediction difficulty
        returns = np.diff(np.log(data + 1e-10))
        
        # Calculate autocorrelation
        if len(returns) > 1:
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            complexity = 1 - abs(autocorr)
        else:
            complexity = 0.5
        
        return max(0, min(1, complexity))
    
    def _calculate_lz_complexity(self, data: np.ndarray) -> float:
        """
        Calculate LZ complexity.
        
        Args:
            data: Time series data
            
        Returns:
            LZ complexity (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        # Convert to binary string based on median
        median = np.median(data)
        binary = ''.join(['1' if x > median else '0' for x in data])
        
        # LZ complexity algorithm
        n = len(binary)
        if n == 0:
            return 0.5
        
        # Simple LZ complexity implementation
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
    
    def _calculate_kolmogorov_complexity(self, data: np.ndarray) -> float:
        """
        Calculate Kolmogorov complexity (approximation).
        
        Args:
            data: Time series data
            
        Returns:
            Kolmogorov complexity (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        # Use compression ratio as approximation
        # This is a simplified version
        import zlib
        
        # Convert to string
        data_str = data.tobytes()
        
        # Compress
        compressed = zlib.compress(data_str)
        
        # Complexity based on compression ratio
        original_size = len(data_str)
        compressed_size = len(compressed)
        
        if original_size == 0:
            return 0.5
        
        complexity = 1 - compressed_size / original_size
        
        return max(0, min(1, complexity))
    
    def _calculate_entropy(self, data: np.ndarray) -> float:
        """
        Calculate entropy of time series.
        
        Args:
            data: Time series data
            
        Returns:
            Entropy (0-1)
        """
        if len(data) < 10:
            return 0.5
        
        returns = np.diff(np.log(data + 1e-10))
        
        # Calculate entropy of returns
        hist, _ = np.histogram(returns, bins=10)
        hist = hist / len(returns)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        max_entropy = np.log(10)
        
        return entropy / max_entropy
    
    def _calculate_dimensionality(self, data: np.ndarray) -> float:
        """
        Calculate dimensionality of time series.
        
        Args:
            data: Time series data
            
        Returns:
            Dimensionality (0-1)
        """
        if len(data) < 20:
            return 0.5
        
        # Use correlation dimension as approximation
        # This is a simplified version
        n = len(data)
        m = 10  # embedding dimension
        
        # Create delay vectors
        vectors = []
        for i in range(n - m + 1):
            vectors.append(data[i:i+m])
        
        vectors = np.array(vectors)
        
        if len(vectors) < 2:
            return 0.5
        
        # Calculate pairwise distances
        distances = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                distances.append(np.linalg.norm(vectors[i] - vectors[j]))
        
        if not distances:
            return 0.5
        
        distances = np.array(distances)
        
        # Estimate dimension from distances
        # This is a rough approximation
        log_dist = np.log(distances + 1e-10)
        
        # Estimate slope of log-log plot
        # Simple approach: use ratio of variances
        if len(log_dist) > 1:
            var_ratio = np.var(log_dist[:-1]) / (np.var(log_dist[1:]) + 1e-10)
            dimension = 1 / (var_ratio + 1e-10)
        else:
            dimension = 0
        
        return max(0, min(1, dimension / 10))
    
    def _get_default_metrics(self) -> ComplexityMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ComplexityMetrics object
        """
        return ComplexityMetrics(
            timestamp=datetime.now(),
            algorithmic_complexity=0.5,
            structural_complexity=0.5,
            informational_complexity=0.5,
            computational_complexity=0.5,
            lz_complexity=0.5,
            kolmogorov_complexity=0.5,
            entropy=0.5,
            dimensionality=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: ComplexityMetrics) -> List[ComplexitySignal]:
        """
        Generate trading signals from complexity metrics.
        
        Args:
            df: OHLCV data
            metrics: ComplexityMetrics object
            
        Returns:
            List of ComplexitySignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if complexity is at extremes
        avg_complexity = (metrics.algorithmic_complexity +
                         metrics.structural_complexity +
                         metrics.informational_complexity) / 3
        
        if avg_complexity < self.confidence_threshold:
            return signals
        
        # Determine signal based on complexity
        if metrics.algorithmic_complexity > 0.7 and metrics.computational_complexity < 0.3:
            signal_type = 'buy'
            reason = "High algorithmic complexity with low computational complexity"
            confidence = avg_complexity
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.algorithmic_complexity < 0.3 and metrics.computational_complexity > 0.7:
            signal_type = 'sell'
            reason = "Low algorithmic complexity with high computational complexity"
            confidence = avg_complexity
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(ComplexitySignal(
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
                'algorithmic': metrics.algorithmic_complexity,
                'structural': metrics.structural_complexity,
                'informational': metrics.informational_complexity,
                'computational': metrics.computational_complexity,
                'entropy': metrics.entropy
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: ComplexityMetrics) -> str:
        """
        Get status from complexity metrics.
        
        Args:
            metrics: ComplexityMetrics object
            
        Returns:
            Status string
        """
        avg_complexity = (metrics.algorithmic_complexity +
                         metrics.structural_complexity +
                         metrics.informational_complexity +
                         metrics.computational_complexity) / 4
        
        if avg_complexity > 0.7:
            return 'high_complexity'
        elif avg_complexity > 0.4:
            return 'moderate_complexity'
        else:
            return 'low_complexity'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: ComplexityMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: ComplexityMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_complexity': 'High complexity market - difficult to predict',
            'moderate_complexity': 'Moderate complexity market - some patterns',
            'low_complexity': 'Low complexity market - more predictable'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get complexity metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_complexity': np.mean([
                m.algorithmic_complexity + m.structural_complexity +
                m.informational_complexity + m.computational_complexity
            ] for m in self.metrics_history) / 4,
            'max_complexity': max([
                m.algorithmic_complexity + m.structural_complexity +
                m.informational_complexity + m.computational_complexity
            ] for m in self.metrics_history) / 4,
            'min_complexity': min([
                m.algorithmic_complexity + m.structural_complexity +
                m.informational_complexity + m.computational_complexity
            ] for m in self.metrics_history) / 4,
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_complexity_model(config: Optional[Dict[str, Any]] = None) -> ComplexityModel:
    """
    Create a complexity model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ComplexityModel instance
    """
    return ComplexityModel(config)


__all__ = [
    'ComplexityMetrics',
    'ComplexitySignal',
    'ComplexityModel',
    'create_complexity_model'
]
