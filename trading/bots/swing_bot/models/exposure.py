"""
Swing Bot Exposure Model
==========================

This module provides exposure analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ExposureMetrics:
    """Exposure metrics data structure."""
    timestamp: datetime
    gross_exposure: float
    net_exposure: float
    beta_exposure: float
    sector_exposure: Dict[str, float]
    concentration: float
    leverage: float
    hedging_ratio: float
    risk_exposure: float


@dataclass
class ExposureSignal:
    """Exposure trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: ExposureMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class ExposureModel:
    """
    Exposure analysis model for portfolio risk assessment.
    
    Implements various exposure metrics for risk management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the exposure model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[ExposureMetrics] = []
        
    def analyze(self, positions: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Analyze exposure metrics.
        
        Args:
            positions: Dictionary of position data
            
        Returns:
            Exposure analysis results
        """
        if not positions:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(positions)
        
        # Generate signals
        signals = self._generate_signals(positions, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(positions, metrics)
        }
    
    def _calculate_metrics(self, positions: Dict[str, Dict[str, float]]) -> ExposureMetrics:
        """
        Calculate exposure metrics.
        
        Args:
            positions: Dictionary of position data
            
        Returns:
            ExposureMetrics object
        """
        # Calculate position values
        total_long = 0
        total_short = 0
        sector_exposures = {}
        
        for symbol, pos in positions.items():
            value = pos.get('quantity', 0) * pos.get('price', 0)
            side = pos.get('side', 'long')
            sector = pos.get('sector', 'unknown')
            
            if side == 'long':
                total_long += value
            else:
                total_short += value
            
            sector_exposures[sector] = sector_exposures.get(sector, 0) + value
        
        # Calculate gross and net exposure
        gross_exposure = total_long + total_short
        net_exposure = total_long - total_short
        
        # Calculate beta exposure (placeholder)
        beta_exposure = net_exposure
        
        # Calculate concentration
        if gross_exposure > 0:
            concentration = max(sector_exposures.values()) / gross_exposure if sector_exposures else 0
        else:
            concentration = 0
        
        # Calculate leverage
        if net_exposure != 0:
            leverage = gross_exposure / abs(net_exposure)
        else:
            leverage = 0
        
        # Calculate hedging ratio
        if total_long > 0:
            hedging_ratio = total_short / total_long
        else:
            hedging_ratio = 0
        
        # Calculate risk exposure
        risk_exposure = gross_exposure * (1 + abs(net_exposure) / gross_exposure) if gross_exposure > 0 else 0
        
        metrics = ExposureMetrics(
            timestamp=datetime.now(),
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            beta_exposure=beta_exposure,
            sector_exposure=sector_exposures,
            concentration=concentration,
            leverage=leverage,
            hedging_ratio=hedging_ratio,
            risk_exposure=risk_exposure
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> ExposureMetrics:
        """
        Get default metrics.
        
        Returns:
            Default ExposureMetrics object
        """
        return ExposureMetrics(
            timestamp=datetime.now(),
            gross_exposure=0.0,
            net_exposure=0.0,
            beta_exposure=0.0,
            sector_exposure={},
            concentration=0.0,
            leverage=0.0,
            hedging_ratio=0.0,
            risk_exposure=0.0
        )
    
    def _generate_signals(self, positions: Dict[str, Dict[str, float]],
                         metrics: ExposureMetrics) -> List[ExposureSignal]:
        """
        Generate trading signals from exposure metrics.
        
        Args:
            positions: Dictionary of position data
            metrics: ExposureMetrics object
            
        Returns:
            List of ExposureSignal objects
        """
        signals = []
        
        # Check exposure levels
        if metrics.hedging_ratio < self.confidence_threshold:
            return signals
        
        # Generate signal based on exposure
        if metrics.hedging_ratio > 0.8:
            # High hedging ratio - potential for reducing hedges
            signal_type = 'buy'
            reason = f"High hedging ratio ({metrics.hedging_ratio:.2f}) - potential for reducing hedges"
            confidence = metrics.hedging_ratio
            
            # Find a position to increase
            symbol = next(iter(positions.keys()))
            current_price = positions[symbol].get('price', 100)
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
            signals.append(ExposureSignal(
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
                    'hedging_ratio': metrics.hedging_ratio,
                    'net_exposure': metrics.net_exposure,
                    'gross_exposure': metrics.gross_exposure,
                    'concentration': metrics.concentration
                }
            ))
            
        elif metrics.hedging_ratio < 0.2:
            # Low hedging ratio - potential for increasing hedges
            signal_type = 'sell'
            reason = f"Low hedging ratio ({metrics.hedging_ratio:.2f}) - potential for increasing hedges"
            confidence = 1 - metrics.hedging_ratio
            
            # Find a position to reduce
            symbol = next(iter(positions.keys()))
            current_price = positions[symbol].get('price', 100)
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
            signals.append(ExposureSignal(
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
                    'hedging_ratio': metrics.hedging_ratio,
                    'net_exposure': metrics.net_exposure,
                    'gross_exposure': metrics.gross_exposure,
                    'concentration': metrics.concentration
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: ExposureMetrics) -> str:
        """
        Get status from exposure metrics.
        
        Args:
            metrics: ExposureMetrics object
            
        Returns:
            Status string
        """
        if metrics.hedging_ratio > 0.8:
            return 'over_hedged'
        elif metrics.hedging_ratio > 0.5:
            return 'hedged'
        elif metrics.hedging_ratio > 0.2:
            return 'under_hedged'
        else:
            return 'unhedged'
    
    def _get_market_character(self, positions: Dict[str, Dict[str, float]],
                            metrics: ExposureMetrics) -> str:
        """
        Get market character description.
        
        Args:
            positions: Dictionary of position data
            metrics: ExposureMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'over_hedged': f"Over-hedged ({metrics.hedging_ratio:.2f})",
            'hedged': f"Hedged ({metrics.hedging_ratio:.2f})",
            'under_hedged': f"Under-hedged ({metrics.hedging_ratio:.2f})",
            'unhedged': f"Unhedged ({metrics.hedging_ratio:.2f})"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get exposure metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_gross_exposure': np.mean([m.gross_exposure for m in self.metrics_history]),
            'average_net_exposure': np.mean([m.net_exposure for m in self.metrics_history]),
            'average_hedging_ratio': np.mean([m.hedging_ratio for m in self.metrics_history]),
            'average_concentration': np.mean([m.concentration for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_exposure_model(config: Optional[Dict[str, Any]] = None) -> ExposureModel:
    """
    Create an exposure model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ExposureModel instance
    """
    return ExposureModel(config)


__all__ = [
    'ExposureMetrics',
    'ExposureSignal',
    'ExposureModel',
    'create_exposure_model'
]
