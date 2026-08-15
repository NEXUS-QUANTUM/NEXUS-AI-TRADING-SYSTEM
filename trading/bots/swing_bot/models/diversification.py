"""
Swing Bot Diversification Model
=================================

This module provides diversification analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class DiversificationMetrics:
    """Diversification metrics data structure."""
    timestamp: datetime
    diversification_ratio: float
    effective_diversification: float
    herfindahl_index: float
    concentration_ratio: float
    number_of_assets: int
    average_correlation: float
    max_correlation: float
    min_correlation: float
    risk_contribution: Dict[str, float]


@dataclass
class DiversificationSignal:
    """Diversification trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: DiversificationMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class DiversificationModel:
    """
    Diversification analysis model for portfolio risk assessment.
    
    Implements various diversification metrics for risk management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the diversification model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[DiversificationMetrics] = []
        
    def analyze(self, returns_dict: Dict[str, np.ndarray],
               weights: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyze diversification metrics.
        
        Args:
            returns_dict: Dictionary of asset returns
            weights: Dictionary of asset weights
            
        Returns:
            Diversification analysis results
        """
        if len(returns_dict) < 2:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(returns_dict, weights)
        
        # Generate signals
        signals = self._generate_signals(returns_dict, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(metrics)
        }
    
    def _calculate_metrics(self, returns_dict: Dict[str, np.ndarray],
                         weights: Dict[str, float]) -> DiversificationMetrics:
        """
        Calculate diversification metrics.
        
        Args:
            returns_dict: Dictionary of asset returns
            weights: Dictionary of asset weights
            
        Returns:
            DiversificationMetrics object
        """
        assets = list(returns_dict.keys())
        n_assets = len(assets)
        
        # Calculate correlation matrix
        corr_matrix = np.zeros((n_assets, n_assets))
        for i, asset1 in enumerate(assets):
            for j, asset2 in enumerate(assets):
                if i == j:
                    corr_matrix[i, j] = 1.0
                else:
                    if len(returns_dict[asset1]) > 0 and len(returns_dict[asset2]) > 0:
                        corr = MathUtils.correlation(returns_dict[asset1], returns_dict[asset2])
                        corr_matrix[i, j] = corr
                    else:
                        corr_matrix[i, j] = 0.0
        
        # Calculate weight array
        weight_array = np.array([weights.get(asset, 1.0/n_assets) for asset in assets])
        weight_array = weight_array / np.sum(weight_array)
        
        # Calculate Herfindahl index
        hhi = np.sum(weight_array ** 2)
        
        # Calculate concentration ratio (CR4)
        sorted_weights = np.sort(weight_array)[::-1]
        cr4 = np.sum(sorted_weights[:4]) if n_assets >= 4 else np.sum(sorted_weights)
        
        # Calculate average correlation
        upper_tri_indices = np.triu_indices(n_assets, k=1)
        correlations = corr_matrix[upper_tri_indices]
        avg_corr = np.mean(correlations) if len(correlations) > 0 else 0
        
        # Calculate diversification ratio
        portfolio_vol = np.sqrt(np.dot(weight_array.T, np.dot(corr_matrix, weight_array)))
        weighted_vol = np.dot(weight_array, np.sqrt(np.diag(corr_matrix)))
        diversification_ratio = weighted_vol / portfolio_vol if portfolio_vol > 0 else 1.0
        
        # Calculate effective diversification
        effective_div = 1 / (1 + np.std(correlations))
        
        # Calculate risk contributions
        risk_contrib = {}
        for i, asset in enumerate(assets):
            marginal_risk = np.dot(corr_matrix[i, :], weight_array)
            risk_contrib[asset] = weight_array[i] * marginal_risk / portfolio_vol if portfolio_vol > 0 else 0
        
        metrics = DiversificationMetrics(
            timestamp=datetime.now(),
            diversification_ratio=diversification_ratio,
            effective_diversification=effective_div,
            herfindahl_index=hhi,
            concentration_ratio=cr4,
            number_of_assets=n_assets,
            average_correlation=avg_corr,
            max_correlation=np.max(correlations) if len(correlations) > 0 else 0,
            min_correlation=np.min(correlations) if len(correlations) > 0 else 0,
            risk_contribution=risk_contrib
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> DiversificationMetrics:
        """
        Get default metrics.
        
        Returns:
            Default DiversificationMetrics object
        """
        return DiversificationMetrics(
            timestamp=datetime.now(),
            diversification_ratio=1.0,
            effective_diversification=0.0,
            herfindahl_index=1.0,
            concentration_ratio=1.0,
            number_of_assets=0,
            average_correlation=0.0,
            max_correlation=0.0,
            min_correlation=0.0,
            risk_contribution={}
        )
    
    def _generate_signals(self, returns_dict: Dict[str, np.ndarray],
                         metrics: DiversificationMetrics) -> List[DiversificationSignal]:
        """
        Generate trading signals from diversification metrics.
        
        Args:
            returns_dict: Dictionary of asset returns
            metrics: DiversificationMetrics object
            
        Returns:
            List of DiversificationSignal objects
        """
        signals = []
        
        if metrics.diversification_ratio < self.confidence_threshold:
            return signals
        
        # Determine signal based on diversification
        if metrics.effective_diversification > 0.6:
            # High diversification - can take more risk
            signal_type = 'buy'
            reason = f"High diversification (score: {metrics.effective_diversification:.2f})"
            confidence = metrics.effective_diversification
            
            # Find an asset with potential
            assets = list(returns_dict.keys())
            if assets:
                symbol = assets[0]
                current_price = 100.0  # Placeholder
                target = current_price * 1.02
                stop_loss = current_price * 0.98
            else:
                return signals
            
            signals.append(DiversificationSignal(
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
                    'diversification_ratio': metrics.diversification_ratio,
                    'effective_diversification': metrics.effective_diversification,
                    'herfindahl_index': metrics.herfindahl_index,
                    'average_correlation': metrics.average_correlation
                }
            ))
            
        elif metrics.effective_diversification < 0.3:
            # Low diversification - need to reduce risk
            signal_type = 'sell'
            reason = f"Low diversification (score: {metrics.effective_diversification:.2f})"
            confidence = 1 - metrics.effective_diversification
            
            # Find the most concentrated asset
            assets = list(metrics.risk_contribution.keys())
            if assets:
                max_risk_asset = max(metrics.risk_contribution, key=metrics.risk_contribution.get)
                symbol = max_risk_asset
                current_price = 100.0  # Placeholder
                target = current_price * 0.98
                stop_loss = current_price * 1.02
            else:
                return signals
            
            signals.append(DiversificationSignal(
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
                    'diversification_ratio': metrics.diversification_ratio,
                    'effective_diversification': metrics.effective_diversification,
                    'herfindahl_index': metrics.herfindahl_index,
                    'concentration_ratio': metrics.concentration_ratio
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: DiversificationMetrics) -> str:
        """
        Get status from diversification metrics.
        
        Args:
            metrics: DiversificationMetrics object
            
        Returns:
            Status string
        """
        if metrics.effective_diversification > 0.6:
            return 'diversified'
        elif metrics.effective_diversification > 0.4:
            return 'moderately_diversified'
        else:
            return 'concentrated'
    
    def _get_market_character(self, metrics: DiversificationMetrics) -> str:
        """
        Get market character description.
        
        Args:
            metrics: DiversificationMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'diversified': f"Diversified (ratio: {metrics.diversification_ratio:.2f})",
            'moderately_diversified': f"Moderately diversified (ratio: {metrics.diversification_ratio:.2f})",
            'concentrated': f"Concentrated (ratio: {metrics.diversification_ratio:.2f})"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get diversification metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_diversification_ratio': np.mean([m.diversification_ratio for m in self.metrics_history]),
            'average_effective_diversification': np.mean([m.effective_diversification for m in self.metrics_history]),
            'average_herfindahl': np.mean([m.herfindahl_index for m in self.metrics_history]),
            'average_correlation': np.mean([m.average_correlation for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_diversification_model(config: Optional[Dict[str, Any]] = None) -> DiversificationModel:
    """
    Create a diversification model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DiversificationModel instance
    """
    return DiversificationModel(config)


__all__ = [
    'DiversificationMetrics',
    'DiversificationSignal',
    'DiversificationModel',
    'create_diversification_model'
]
