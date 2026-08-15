"""
Swing Bot Rotation Model
==========================

This module provides sector rotation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class RotationMetrics:
    """Rotation metrics data structure."""
    timestamp: datetime
    sector: str
    momentum_score: float
    relative_strength: float
    valuation_score: float
    flow_score: float
    combined_score: float
    weight: float


@dataclass
class RotationSignal:
    """Rotation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    from_sector: str
    to_sector: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class RotationModel:
    """
    Sector rotation model for systematic sector allocation.
    
    Implements momentum-based sector rotation strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the rotation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.sectors = self.config.get('sectors', ['technology', 'financials', 'healthcare',
                                                   'energy', 'consumer', 'industrials',
                                                   'utilities', 'materials', 'real_estate'])
        self.lookback_period = self.config.get('lookback_period', 30)
        self.rotation_frequency = self.config.get('rotation_frequency', 10)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.current_weights: Dict[str, float] = {}
        self.rotation_history: List[Dict[str, Any]] = []
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze rotation opportunities.
        
        Args:
            df_dict: Dictionary of sector dataframes
            
        Returns:
            Rotation analysis results
        """
        if not df_dict:
            return {'metrics': [], 'signals': []}
        
        # Calculate metrics for each sector
        metrics = []
        for sector, df in df_dict.items():
            if sector in self.sectors:
                metric = self._calculate_rotation_metrics(sector, df)
                metrics.append(metric)
        
        # Calculate weights
        weights = self._calculate_weights(metrics)
        
        # Detect rotation signals
        signals = self._generate_signals(df_dict, metrics, weights)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'weights': weights,
            'top_sectors': self._get_top_sectors(metrics, weights),
            'market_character': self._get_market_character(metrics)
        }
    
    def _calculate_rotation_metrics(self, sector: str, df: pd.DataFrame) -> RotationMetrics:
        """
        Calculate rotation metrics for a sector.
        
        Args:
            sector: Sector name
            df: Sector data
            
        Returns:
            RotationMetrics object
        """
        if len(df) < self.lookback_period:
            return RotationMetrics(
                timestamp=datetime.now(),
                sector=sector,
                momentum_score=0.0,
                relative_strength=0.0,
                valuation_score=0.0,
                flow_score=0.0,
                combined_score=0.0,
                weight=0.0
            )
        
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate momentum (short-term)
        momentum_short = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        momentum_med = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0
        momentum_score = momentum_short * 0.4 + momentum_med * 0.6
        
        # Calculate relative strength (compared to other sectors)
        # This would use actual benchmark data in production
        relative_strength = momentum_score * 0.5 + 0.5
        
        # Calculate valuation (placeholder)
        valuation_score = 0.5
        
        # Calculate flow (volume trend)
        if len(volume) >= 20:
            volume_trend = (volume[-1] - np.mean(volume[-20:])) / np.mean(volume[-20:])
            flow_score = min(max(volume_trend, -1), 1)
        else:
            flow_score = 0.0
        
        # Combined score
        combined_score = (momentum_score * 0.35 + 
                         relative_strength * 0.35 + 
                         valuation_score * 0.15 + 
                         flow_score * 0.15)
        
        return RotationMetrics(
            timestamp=datetime.now(),
            sector=sector,
            momentum_score=momentum_score,
            relative_strength=relative_strength,
            valuation_score=valuation_score,
            flow_score=flow_score,
            combined_score=combined_score,
            weight=0.0
        )
    
    def _calculate_weights(self, metrics: List[RotationMetrics]) -> Dict[str, float]:
        """
        Calculate sector weights.
        
        Args:
            metrics: List of rotation metrics
            
        Returns:
            Dictionary of sector weights
        """
        if not metrics:
            return {}
        
        # Normalize scores
        scores = [m.combined_score for m in metrics]
        min_score = min(scores)
        max_score = max(scores)
        
        weights = {}
        if max_score > min_score:
            for metric in metrics:
                # Convert scores to weights (positive only)
                normalized = (metric.combined_score - min_score) / (max_score - min_score)
                weights[metric.sector] = normalized + 0.01  # Add small minimum weight
        else:
            # Equal weights
            weight = 1.0 / len(metrics)
            for metric in metrics:
                weights[metric.sector] = weight
        
        # Normalize weights to sum to 1
        total = sum(weights.values())
        for sector in weights:
            weights[sector] /= total
        
        self.current_weights = weights
        
        # Update metrics with weights
        for metric in metrics:
            metric.weight = weights.get(metric.sector, 0)
        
        return weights
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         metrics: List[RotationMetrics],
                         weights: Dict[str, float]) -> List[RotationSignal]:
        """
        Generate rotation signals.
        
        Args:
            df_dict: Dictionary of sector dataframes
            metrics: List of rotation metrics
            weights: Sector weights
            
        Returns:
            List of RotationSignal objects
        """
        signals = []
        
        if not metrics or not weights:
            return signals
        
        # Sort sectors by weight
        sorted_sectors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        if len(sorted_sectors) < 2:
            return signals
        
        # Identify rotation from worst to best
        worst_sector = sorted_sectors[-1][0]
        best_sector = sorted_sectors[0][0]
        
        # Check if rotation is significant
        weight_diff = sorted_sectors[0][1] - sorted_sectors[-1][1]
        confidence = min(weight_diff * 5, 1.0)
        
        if confidence < self.confidence_threshold:
            return signals
        
        # Generate signal for best sector
        if best_sector in df_dict:
            df = df_dict[best_sector]
            if len(df) > 0:
                current_price = df['close'].iloc[-1]
                symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
                
                signal_type = 'buy'
                reason = f"Rotation into {best_sector} (weight: {weights[best_sector]:.2f})"
                target = current_price * (1 + confidence * 0.05)
                stop_loss = current_price * (1 - confidence * 0.03)
                
                signals.append(RotationSignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type=signal_type,
                    confidence=confidence,
                    price=current_price,
                    target=target,
                    stop_loss=stop_loss,
                    reason=reason,
                    from_sector=worst_sector,
                    to_sector=best_sector,
                    indicators={
                        'weight_diff': weight_diff,
                        'best_sector_score': weights[best_sector],
                        'worst_sector_score': weights[worst_sector]
                    }
                ))
        
        return signals
    
    def _get_top_sectors(self, metrics: List[RotationMetrics],
                        weights: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Get top sectors by weight.
        
        Args:
            metrics: List of rotation metrics
            weights: Sector weights
            
        Returns:
            List of top sectors
        """
        if not weights:
            return []
        
        sorted_sectors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {
                'sector': sector,
                'weight': weight,
                'momentum': next((m.momentum_score for m in metrics if m.sector == sector), 0),
                'relative_strength': next((m.relative_strength for m in metrics if m.sector == sector), 0)
            }
            for sector, weight in sorted_sectors[:3]
        ]
    
    def _get_market_character(self, metrics: List[RotationMetrics]) -> str:
        """
        Get market character description.
        
        Args:
            metrics: List of rotation metrics
            
        Returns:
            Market character description
        """
        if not metrics:
            return "No sector data available"
        
        # Calculate average momentum
        avg_momentum = np.mean([m.momentum_score for m in metrics])
        
        if avg_momentum > 0.03:
            return "Strong momentum - aggressive rotation"
        elif avg_momentum > 0.01:
            return "Positive momentum - moderate rotation"
        elif avg_momentum > -0.01:
            return "Neutral momentum - low rotation"
        elif avg_momentum > -0.03:
            return "Negative momentum - defensive rotation"
        else:
            return "Strong negative momentum - risk-off rotation"
    
    def get_rotation_summary(self) -> Dict[str, Any]:
        """
        Get rotation summary.
        
        Returns:
            Rotation summary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'current_weights': self.current_weights,
            'top_sector': max(self.current_weights.items(), key=lambda x: x[1])[0] if self.current_weights else None,
            'bottom_sector': min(self.current_weights.items(), key=lambda x: x[1])[0] if self.current_weights else None,
            'rotation_history_length': len(self.rotation_history),
            'sector_count': len(self.sectors)
        }


def create_rotation_model(config: Optional[Dict[str, Any]] = None) -> RotationModel:
    """
    Create a rotation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        RotationModel instance
    """
    return RotationModel(config)


__all__ = [
    'RotationMetrics',
    'RotationSignal',
    'RotationModel',
    'create_rotation_model'
]
