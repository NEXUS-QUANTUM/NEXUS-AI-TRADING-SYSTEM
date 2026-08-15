"""
Swing Bot Distribution Model
==============================

This module provides distribution analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy import stats


@dataclass
class DistributionMetrics:
    """Distribution metrics data structure."""
    timestamp: datetime
    mean: float
    median: float
    mode: float
    std: float
    skewness: float
    kurtosis: float
    variance: float
    range: Tuple[float, float]
    iqr: float
    distribution_type: str  # 'normal', 'skewed', 'bimodal', 'uniform'


@dataclass
class DistributionSignal:
    """Distribution trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: DistributionMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class DistributionModel:
    """
    Distribution analysis model for market behavior.
    
    Implements distribution analysis of price and returns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the distribution model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[DistributionMetrics] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze distribution metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Distribution analysis results
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
    
    def _calculate_metrics(self, df: pd.DataFrame) -> DistributionMetrics:
        """
        Calculate distribution metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            DistributionMetrics object
        """
        close = df['close'].values
        returns = np.diff(np.log(close))
        
        # Calculate statistics
        mean = np.mean(returns)
        median = np.median(returns)
        
        # Calculate mode (using histogram)
        hist, bin_edges = np.histogram(returns, bins=10)
        mode_index = np.argmax(hist)
        mode = (bin_edges[mode_index] + bin_edges[mode_index + 1]) / 2
        
        std = np.std(returns)
        variance = np.var(returns)
        
        # Calculate skewness and kurtosis
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        
        # Calculate range and IQR
        range_min = np.min(returns)
        range_max = np.max(returns)
        q1 = np.percentile(returns, 25)
        q3 = np.percentile(returns, 75)
        iqr = q3 - q1
        
        # Determine distribution type
        distribution_type = self._determine_distribution_type(returns, skewness, kurtosis)
        
        metrics = DistributionMetrics(
            timestamp=datetime.now(),
            mean=mean,
            median=median,
            mode=mode,
            std=std,
            skewness=skewness,
            kurtosis=kurtosis,
            variance=variance,
            range=(range_min, range_max),
            iqr=iqr,
            distribution_type=distribution_type
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _determine_distribution_type(self, returns: np.ndarray, skewness: float,
                                   kurtosis: float) -> str:
        """
        Determine the type of distribution.
        
        Args:
            returns: Returns array
            skewness: Skewness value
            kurtosis: Kurtosis value
            
        Returns:
            Distribution type string
        """
        if len(returns) < 10:
            return 'unknown'
        
        # Check for normality
        _, p_value = stats.normaltest(returns)
        
        if p_value > 0.05:
            return 'normal'
        
        # Check for skewness
        if abs(skewness) > 0.5:
            return 'skewed'
        
        # Check for bimodality (using Hartigan's Dip Test)
        try:
            from diptest import diptest
            dip, p_value = diptest(returns)
            if p_value < 0.05:
                return 'bimodal'
        except:
            pass
        
        # Check for uniformity
        if np.std(returns) < 0.01:
            return 'uniform'
        
        return 'unknown'
    
    def _get_default_metrics(self) -> DistributionMetrics:
        """
        Get default metrics.
        
        Returns:
            Default DistributionMetrics object
        """
        return DistributionMetrics(
            timestamp=datetime.now(),
            mean=0.0,
            median=0.0,
            mode=0.0,
            std=0.0,
            skewness=0.0,
            kurtosis=0.0,
            variance=0.0,
            range=(0.0, 0.0),
            iqr=0.0,
            distribution_type='unknown'
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: DistributionMetrics) -> List[DistributionSignal]:
        """
        Generate trading signals from distribution metrics.
        
        Args:
            df: OHLCV data
            metrics: DistributionMetrics object
            
        Returns:
            List of DistributionSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check for extreme skewness
        confidence = 1 - min(abs(metrics.skewness) / 2, 1.0)
        
        if confidence < self.confidence_threshold:
            return signals
        
        # Generate signal based on distribution
        if metrics.skewness > 0.5:
            # Positive skew - potential for upward movement
            signal_type = 'buy'
            reason = f"Positive skewness ({metrics.skewness:.3f}) indicating upside potential"
            confidence = 1 - min(metrics.skewness / 2, 1.0)
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.skewness < -0.5:
            # Negative skew - potential for downward movement
            signal_type = 'sell'
            reason = f"Negative skewness ({metrics.skewness:.3f}) indicating downside risk"
            confidence = 1 - min(abs(metrics.skewness) / 2, 1.0)
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(DistributionSignal(
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
                'skewness': metrics.skewness,
                'kurtosis': metrics.kurtosis,
                'distribution_type': metrics.distribution_type,
                'iqr': metrics.iqr
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: DistributionMetrics) -> str:
        """
        Get status from distribution metrics.
        
        Args:
            metrics: DistributionMetrics object
            
        Returns:
            Status string
        """
        if metrics.distribution_type == 'normal':
            return 'normal'
        elif metrics.distribution_type == 'skewed':
            if metrics.skewness > 0:
                return 'positive_skew'
            else:
                return 'negative_skew'
        elif metrics.distribution_type == 'bimodal':
            return 'bimodal'
        elif metrics.distribution_type == 'uniform':
            return 'uniform'
        else:
            return 'unknown'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: DistributionMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: DistributionMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'normal': f"Normal distribution (skew: {metrics.skewness:.3f})",
            'positive_skew': f"Positive skew ({metrics.skewness:.3f}) - upside bias",
            'negative_skew': f"Negative skew ({metrics.skewness:.3f}) - downside bias",
            'bimodal': f"Bimodal distribution - market indecision",
            'uniform': f"Uniform distribution - low volatility",
            'unknown': f"Unknown distribution type"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get distribution metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_skewness': np.mean([m.skewness for m in self.metrics_history]),
            'average_kurtosis': np.mean([m.kurtosis for m in self.metrics_history]),
            'average_std': np.mean([m.std for m in self.metrics_history]),
            'distribution_types': {
                'normal': len([m for m in self.metrics_history if m.distribution_type == 'normal']),
                'skewed': len([m for m in self.metrics_history if m.distribution_type == 'skewed']),
                'bimodal': len([m for m in self.metrics_history if m.distribution_type == 'bimodal']),
                'uniform': len([m for m in self.metrics_history if m.distribution_type == 'uniform'])
            },
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_distribution_model(config: Optional[Dict[str, Any]] = None) -> DistributionModel:
    """
    Create a distribution model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DistributionModel instance
    """
    return DistributionModel(config)


__all__ = [
    'DistributionMetrics',
    'DistributionSignal',
    'DistributionModel',
    'create_distribution_model'
]
