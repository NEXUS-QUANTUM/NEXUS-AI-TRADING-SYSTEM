"""
Swing Bot Concentration Model
===============================

This module provides concentration analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ConcentrationMetrics:
    """Concentration metrics data structure."""
    timestamp: datetime
    herfindahl_index: float
    gini_coefficient: float
    concentration_ratio: float
    diversification_score: float
    effective_number: float
    max_weight: float
    min_weight: float
    entropy: float


@dataclass
class ConcentrationSignal:
    """Concentration trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ConcentrationMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ConcentrationModel:
    """
    Concentration analysis model for portfolio risk assessment.
    
    Implements various concentration metrics for risk analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the concentration model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ConcentrationMetrics] = []
        
    def analyze(self, weights: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyze concentration metrics.
        
        Args:
            weights: Dictionary of asset weights
            
        Returns:
            Concentration analysis results
        """
        if not weights:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(weights)
        
        # Generate signals
        signals = self._generate_signals(weights, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(weights, metrics)
        }
    
    def _calculate_metrics(self, weights: Dict[str, float]) -> ConcentrationMetrics:
        """
        Calculate concentration metrics.
        
        Args:
            weights: Dictionary of asset weights
            
        Returns:
            ConcentrationMetrics object
        """
        # Convert to array
        weight_values = np.array(list(weights.values()))
        n_assets = len(weight_values)
        
        # Herfindahl-Hirschman Index (HHI)
        hhi = np.sum(weight_values ** 2)
        
        # Gini coefficient
        sorted_weights = np.sort(weight_values)
        n = len(sorted_weights)
        if n > 0:
            gini = (2 * np.sum(np.arange(1, n + 1) * sorted_weights) / (n * np.sum(sorted_weights)) -
                   (n + 1) / n)
        else:
            gini = 0.0
        
        # Concentration ratio (CR4)
        top_4 = np.sort(weight_values)[-4:] if len(weight_values) >= 4 else weight_values
        cr4 = np.sum(top_4)
        
        # Diversification score
        diversification = 1 - hhi
        
        # Effective number of bets
        if hhi > 0:
            effective_number = 1 / hhi
        else:
            effective_number = n_assets
        
        # Max and min weights
        max_weight = np.max(weight_values) if len(weight_values) > 0 else 0
        min_weight = np.min(weight_values) if len(weight_values) > 0 else 0
        
        # Entropy
        # Normalize weights to avoid log of zero
        entropy = -np.sum(weight_values * np.log(weight_values + 1e-10))
        max_entropy = np.log(n_assets) if n_assets > 0 else 1
        
        metrics = ConcentrationMetrics(
            timestamp=datetime.now(),
            herfindahl_index=hhi,
            gini_coefficient=gini,
            concentration_ratio=cr4,
            diversification_score=diversification,
            effective_number=effective_number,
            max_weight=max_weight,
            min_weight=min_weight,
            entropy=entropy / max_entropy if max_entropy > 0 else 0
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> ConcentrationMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ConcentrationMetrics object
        """
        return ConcentrationMetrics(
            timestamp=datetime.now(),
            herfindahl_index=0.0,
            gini_coefficient=0.0,
            concentration_ratio=0.0,
            diversification_score=0.0,
            effective_number=0.0,
            max_weight=0.0,
            min_weight=0.0,
            entropy=0.0
        )
    
    def _generate_signals(self, weights: Dict[str, float],
                         metrics: ConcentrationMetrics) -> List[ConcentrationSignal]:
        """
        Generate trading signals from concentration metrics.
        
        Args:
            weights: Dictionary of asset weights
            metrics: ConcentrationMetrics object
            
        Returns:
            List of ConcentrationSignal objects
        """
        signals = []
        
        if metrics.diversification_score < self.confidence_threshold:
            return signals
        
        # Determine signal based on concentration
        if metrics.herfindahl_index > 0.25:
            # High concentration
            signal_type = 'sell'
            reason = "High concentration - recommend diversification"
            confidence = metrics.diversification_score
            
            # Find the most concentrated asset
            max_asset = max(weights, key=weights.get)
            current_price = 100.0  # Placeholder
            symbol = max_asset
            
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
            signals.append(ConcentrationSignal(
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
                    'hhi': metrics.herfindahl_index,
                    'concentration_ratio': metrics.concentration_ratio,
                    'effective_number': metrics.effective_number
                }
            ))
            
        elif metrics.herfindahl_index < 0.10:
            # Low concentration
            signal_type = 'buy'
            reason = "Low concentration - potential for targeted investment"
            confidence = metrics.diversification_score
            
            # Find an asset with potential
            potential_assets = [a for a, w in weights.items() if w > 0.05]
            if potential_assets:
                symbol = potential_assets[0]
                current_price = 100.0  # Placeholder
                target = current_price * 1.02
                stop_loss = current_price * 0.98
            else:
                return signals
            
            signals.append(ConcentrationSignal(
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
                    'hhi': metrics.herfindahl_index,
                    'concentration_ratio': metrics.concentration_ratio,
                    'effective_number': metrics.effective_number
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: ConcentrationMetrics) -> str:
        """
        Get status from concentration metrics.
        
        Args:
            metrics: ConcentrationMetrics object
            
        Returns:
            Status string
        """
        if metrics.herfindahl_index > 0.25:
            return 'high_concentration'
        elif metrics.herfindahl_index > 0.15:
            return 'moderate_concentration'
        else:
            return 'low_concentration'
    
    def _get_market_character(self, weights: Dict[str, float],
                            metrics: ConcentrationMetrics) -> str:
        """
        Get market character description.
        
        Args:
            weights: Dictionary of asset weights
            metrics: ConcentrationMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_concentration': f'High concentration (HHI: {metrics.herfindahl_index:.3f})',
            'moderate_concentration': f'Moderate concentration (HHI: {metrics.herfindahl_index:.3f})',
            'low_concentration': f'Low concentration (HHI: {metrics.herfindahl_index:.3f})'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get concentration metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_hhi': np.mean([m.herfindahl_index for m in self.metrics_history]),
            'average_diversification': np.mean([m.diversification_score for m in self.metrics_history]),
            'average_effective_number': np.mean([m.effective_number for m in self.metrics_history]),
            'average_gini': np.mean([m.gini_coefficient for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_concentration_model(config: Optional[Dict[str, Any]] = None) -> ConcentrationModel:
    """
    Create a concentration model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ConcentrationModel instance
    """
    return ConcentrationModel(config)


__all__ = [
    'ConcentrationMetrics',
    'ConcentrationSignal',
    'ConcentrationModel',
    'create_concentration_model'
]
