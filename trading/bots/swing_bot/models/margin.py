"""
Swing Bot Margin Model
========================

This module provides margin analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class MarginMetrics:
    """Margin metrics data structure."""
    timestamp: datetime
    margin_used: float
    margin_available: float
    margin_ratio: float
    leverage: float
    liquidation_price: float
    margin_call_level: float
    collateral_value: float
    maintenance_margin: float
    initial_margin: float


@dataclass
class MarginSignal:
    """Margin trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: MarginMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class MarginModel:
    """
    Margin analysis model for leverage trading.
    
    Implements margin calculation and risk assessment.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the margin model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.initial_margin = self.config.get('initial_margin', 0.10)
        self.maintenance_margin = self.config.get('maintenance_margin', 0.05)
        self.max_leverage = self.config.get('max_leverage', 10.0)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[MarginMetrics] = []
        
    def calculate(self, position: Dict[str, Any], price: float) -> MarginMetrics:
        """
        Calculate margin metrics for a position.
        
        Args:
            position: Position data
            price: Current price
            
        Returns:
            MarginMetrics object
        """
        # Position data
        quantity = position.get('quantity', 0)
        entry_price = position.get('entry_price', price)
        position_value = quantity * price
        initial_value = quantity * entry_price
        
        # Calculate margin
        margin_used = position_value * self.initial_margin
        collateral = position_value * (1 + position.get('unrealized_pnl', 0))
        margin_available = collateral - margin_used
        
        # Calculate margin ratio
        if position_value > 0:
            margin_ratio = margin_used / position_value
        else:
            margin_ratio = 0.0
        
        # Calculate leverage
        if margin_used > 0:
            leverage = position_value / margin_used
        else:
            leverage = 0.0
        
        # Calculate liquidation price
        if position.get('side') == 'long':
            liquidation_price = entry_price * (1 - self.maintenance_margin / self.initial_margin)
        else:  # short
            liquidation_price = entry_price * (1 + self.maintenance_margin / self.initial_margin)
        
        # Calculate margin call level
        margin_call_level = margin_ratio / self.maintenance_margin
        
        metrics = MarginMetrics(
            timestamp=datetime.now(),
            margin_used=margin_used,
            margin_available=margin_available,
            margin_ratio=margin_ratio,
            leverage=leverage,
            liquidation_price=liquidation_price,
            margin_call_level=margin_call_level,
            collateral_value=collateral,
            maintenance_margin=self.maintenance_margin,
            initial_margin=self.initial_margin
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze margin metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Margin analysis results
        """
        if len(df) < 10:
            return {'metrics': None, 'signals': []}
        
        # Sample position for analysis
        position = {
            'quantity': 100,
            'entry_price': df['close'].iloc[0],
            'side': 'long',
            'unrealized_pnl': 0
        }
        
        current_price = df['close'].iloc[-1]
        
        # Calculate metrics
        metrics = self.calculate(position, current_price)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: MarginMetrics) -> List[MarginSignal]:
        """
        Generate trading signals from margin metrics.
        
        Args:
            df: OHLCV data
            metrics: MarginMetrics object
            
        Returns:
            List of MarginSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check margin levels
        if metrics.margin_call_level < 0.5:
            # Low margin - potential for adding position
            signal_type = 'buy'
            reason = f"Low margin usage ({metrics.margin_ratio:.2%}) - capacity to add"
            confidence = 1 - metrics.margin_call_level
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
            signals.append(MarginSignal(
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
                    'margin_ratio': metrics.margin_ratio,
                    'leverage': metrics.leverage,
                    'margin_call_level': metrics.margin_call_level,
                    'liquidation_price': metrics.liquidation_price
                }
            ))
            
        elif metrics.margin_call_level > 0.8:
            # High margin - need to reduce position
            signal_type = 'sell'
            reason = f"High margin usage ({metrics.margin_ratio:.2%}) - need to reduce"
            confidence = metrics.margin_call_level
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
            signals.append(MarginSignal(
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
                    'margin_ratio': metrics.margin_ratio,
                    'leverage': metrics.leverage,
                    'margin_call_level': metrics.margin_call_level,
                    'liquidation_price': metrics.liquidation_price
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: MarginMetrics) -> str:
        """
        Get status from margin metrics.
        
        Args:
            metrics: MarginMetrics object
            
        Returns:
            Status string
        """
        if metrics.margin_call_level > 0.8:
            return 'high_margin'
        elif metrics.margin_call_level > 0.6:
            return 'moderate_margin'
        elif metrics.margin_call_level > 0.3:
            return 'low_margin'
        else:
            return 'very_low_margin'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: MarginMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: MarginMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_margin': f"High margin usage ({metrics.margin_ratio:.2%}) - risky",
            'moderate_margin': f"Moderate margin usage ({metrics.margin_ratio:.2%})",
            'low_margin': f"Low margin usage ({metrics.margin_ratio:.2%})",
            'very_low_margin': f"Very low margin usage ({metrics.margin_ratio:.2%})"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get margin metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_margin_ratio': np.mean([m.margin_ratio for m in self.metrics_history]),
            'average_leverage': np.mean([m.leverage for m in self.metrics_history]),
            'average_margin_call_level': np.mean([m.margin_call_level for m in self.metrics_history]),
            'max_margin_ratio': max([m.margin_ratio for m in self.metrics_history]),
            'min_margin_ratio': min([m.margin_ratio for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_margin_model(config: Optional[Dict[str, Any]] = None) -> MarginModel:
    """
    Create a margin model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MarginModel instance
    """
    return MarginModel(config)


__all__ = [
    'MarginMetrics',
    'MarginSignal',
    'MarginModel',
    'create_margin_model'
]
