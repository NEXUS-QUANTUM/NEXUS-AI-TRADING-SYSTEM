"""
Swing Bot Correlation Model
=============================

This module provides correlation analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class CorrelationMetrics:
    """Correlation metrics data structure."""
    timestamp: datetime
    correlation_matrix: np.ndarray
    average_correlation: float
    max_correlation: float
    min_correlation: float
    positive_correlation_ratio: float
    negative_correlation_ratio: float
    correlation_volatility: float
    diversification_score: float
    assets: List[str]


@dataclass
class CorrelationSignal:
    """Correlation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: CorrelationMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class CorrelationModel:
    """
    Correlation analysis model for market relationships.
    
    Implements correlation analysis for multiple assets.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the correlation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[CorrelationMetrics] = []
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze correlations between assets.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            Correlation analysis results
        """
        if len(df_dict) < 2:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(df_dict)
        
        # Generate signals
        signals = self._generate_signals(df_dict, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(metrics)
        }
    
    def _calculate_metrics(self, df_dict: Dict[str, pd.DataFrame]) -> CorrelationMetrics:
        """
        Calculate correlation metrics.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            CorrelationMetrics object
        """
        # Get returns for each asset
        returns = {}
        for symbol, df in df_dict.items():
            if len(df) > 1:
                returns[symbol] = df['close'].pct_change().dropna().values[-self.lookback_period:]
            else:
                returns[symbol] = np.zeros(10)
        
        # Calculate correlation matrix
        symbols = list(returns.keys())
        n_assets = len(symbols)
        corr_matrix = np.zeros((n_assets, n_assets))
        
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    corr_matrix[i, j] = 1.0
                else:
                    if len(returns[symbol1]) > 0 and len(returns[symbol2]) > 0:
                        corr = MathUtils.correlation(returns[symbol1], returns[symbol2])
                        corr_matrix[i, j] = corr
                    else:
                        corr_matrix[i, j] = 0.0
        
        # Calculate statistics
        upper_tri_indices = np.triu_indices(n_assets, k=1)
        correlations = corr_matrix[upper_tri_indices]
        
        if len(correlations) > 0:
            avg_correlation = np.mean(correlations)
            max_correlation = np.max(correlations)
            min_correlation = np.min(correlations)
            positive_ratio = np.sum(correlations > 0) / len(correlations)
            negative_ratio = np.sum(correlations < 0) / len(correlations)
            correlation_volatility = np.std(correlations)
        else:
            avg_correlation = 0.0
            max_correlation = 0.0
            min_correlation = 0.0
            positive_ratio = 0.0
            negative_ratio = 0.0
            correlation_volatility = 0.0
        
        # Calculate diversification score
        diversification_score = 1 - np.mean(np.abs(correlations))
        
        metrics = CorrelationMetrics(
            timestamp=datetime.now(),
            correlation_matrix=corr_matrix,
            average_correlation=avg_correlation,
            max_correlation=max_correlation,
            min_correlation=min_correlation,
            positive_correlation_ratio=positive_ratio,
            negative_correlation_ratio=negative_ratio,
            correlation_volatility=correlation_volatility,
            diversification_score=diversification_score,
            assets=symbols
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> CorrelationMetrics:
        """
        Get default metrics.
        
        Returns:
            Default CorrelationMetrics object
        """
        return CorrelationMetrics(
            timestamp=datetime.now(),
            correlation_matrix=np.array([[1.0]]),
            average_correlation=0.0,
            max_correlation=0.0,
            min_correlation=0.0,
            positive_correlation_ratio=0.0,
            negative_correlation_ratio=0.0,
            correlation_volatility=0.0,
            diversification_score=0.0,
            assets=[]
        )
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         metrics: CorrelationMetrics) -> List[CorrelationSignal]:
        """
        Generate trading signals from correlation metrics.
        
        Args:
            df_dict: Dictionary of asset dataframes
            metrics: CorrelationMetrics object
            
        Returns:
            List of CorrelationSignal objects
        """
        signals = []
        
        if metrics.diversification_score < self.confidence_threshold:
            return signals
        
        # Find assets with low correlation
        n_assets = len(metrics.assets)
        if n_assets < 2:
            return signals
        
        # Find pair with lowest correlation
        min_corr = 1.0
        best_pair = None
        
        for i in range(n_assets):
            for j in range(i + 1, n_assets):
                corr = metrics.correlation_matrix[i, j]
                if corr < min_corr:
                    min_corr = corr
                    best_pair = (metrics.assets[i], metrics.assets[j])
        
        if best_pair is None or min_corr > 0.3:
            return signals
        
        # Generate signal for the asset with low correlation
        symbol = best_pair[0]
        if symbol not in df_dict:
            return signals
        
        df = df_dict[symbol]
        if len(df) < 20:
            return signals
        
        current_price = df['close'].iloc[-1]
        
        signal_type = 'buy'
        reason = f"Low correlation with {best_pair[1]} ({min_corr:.3f})"
        confidence = 1 - min_corr
        
        target = current_price * 1.02
        stop_loss = current_price * 0.98
        
        signals.append(CorrelationSignal(
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
                'correlation': min_corr,
                'correlated_asset': best_pair[1],
                'diversification_score': metrics.diversification_score
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: CorrelationMetrics) -> str:
        """
        Get status from correlation metrics.
        
        Args:
            metrics: CorrelationMetrics object
            
        Returns:
            Status string
        """
        if metrics.diversification_score > 0.6:
            return 'diversified'
        elif metrics.diversification_score > 0.3:
            return 'moderate_diversification'
        else:
            return 'concentrated'
    
    def _get_market_character(self, metrics: CorrelationMetrics) -> str:
        """
        Get market character description.
        
        Args:
            metrics: CorrelationMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'diversified': f'Diversified (avg corr: {metrics.average_correlation:.3f})',
            'moderate_diversification': f'Moderate diversification (avg corr: {metrics.average_correlation:.3f})',
            'concentrated': f'Concentrated (avg corr: {metrics.average_correlation:.3f})'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get correlation metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_correlation': np.mean([m.average_correlation for m in self.metrics_history]),
            'average_diversification': np.mean([m.diversification_score for m in self.metrics_history]),
            'min_correlation': min([m.min_correlation for m in self.metrics_history]),
            'max_correlation': max([m.max_correlation for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_correlation_model(config: Optional[Dict[str, Any]] = None) -> CorrelationModel:
    """
    Create a correlation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        CorrelationModel instance
    """
    return CorrelationModel(config)


__all__ = [
    'CorrelationMetrics',
    'CorrelationSignal',
    'CorrelationModel',
    'create_correlation_model'
]
