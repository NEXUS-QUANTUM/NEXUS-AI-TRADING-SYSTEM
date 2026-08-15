"""
Swing Bot Leverage Model
==========================

This module provides leverage analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class LeverageMetrics:
    """Leverage metrics data structure."""
    timestamp: datetime
    current_leverage: float
    max_leverage: float
    avg_leverage: float
    leverage_ratio: float
    margin_usage: float
    risk_score: float
    optimal_leverage: float
    leverage_efficiency: float


@dataclass
class LeverageSignal:
    """Leverage trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: LeverageMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class LeverageModel:
    """
    Leverage analysis model for risk management.
    
    Implements leverage calculation and optimization.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the leverage model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.max_leverage = self.config.get('max_leverage', 3.0)
        self.min_leverage = self.config.get('min_leverage', 0.5)
        self.risk_tolerance = self.config.get('risk_tolerance', 0.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[LeverageMetrics] = []
        
    def calculate(self, position_value: float, equity: float) -> LeverageMetrics:
        """
        Calculate leverage metrics.
        
        Args:
            position_value: Total position value
            equity: Account equity
            
        Returns:
            LeverageMetrics object
        """
        # Calculate leverage
        if equity > 0:
            current_leverage = position_value / equity
        else:
            current_leverage = 0.0
        
        # Calculate margin usage
        margin_usage = min(current_leverage / self.max_leverage, 1.0)
        
        # Calculate risk score
        risk_score = margin_usage * self.risk_tolerance
        
        # Calculate optimal leverage (using Kelly criterion approximation)
        optimal_leverage = min(self.max_leverage, self.risk_tolerance * 2)
        
        # Calculate leverage efficiency
        if current_leverage > 0:
            leverage_efficiency = 1 - abs(current_leverage - optimal_leverage) / optimal_leverage
        else:
            leverage_efficiency = 0.0
        
        metrics = LeverageMetrics(
            timestamp=datetime.now(),
            current_leverage=current_leverage,
            max_leverage=self.max_leverage,
            avg_leverage=current_leverage,  # Will be updated from history
            leverage_ratio=current_leverage / self.max_leverage if self.max_leverage > 0 else 0,
            margin_usage=margin_usage,
            risk_score=risk_score,
            optimal_leverage=optimal_leverage,
            leverage_efficiency=leverage_efficiency
        )
        
        # Update average leverage from history
        if self.metrics_history:
            avg_leverage = np.mean([m.current_leverage for m in self.metrics_history[-10:]])
            metrics.avg_leverage = avg_leverage
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def analyze(self, df: pd.DataFrame, equity: float) -> Dict[str, Any]:
        """
        Analyze leverage metrics.
        
        Args:
            df: OHLCV data
            equity: Account equity
            
        Returns:
            Leverage analysis results
        """
        if len(df) < 20:
            return {'metrics': None, 'signals': []}
        
        # Calculate position value (simplified)
        position_value = df['close'].iloc[-1] * 100  # 100 shares
        
        # Calculate metrics
        metrics = self.calculate(position_value, equity)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: LeverageMetrics) -> List[LeverageSignal]:
        """
        Generate trading signals from leverage metrics.
        
        Args:
            df: OHLCV data
            metrics: LeverageMetrics object
            
        Returns:
            List of LeverageSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check leverage efficiency
        if metrics.leverage_efficiency < self.confidence_threshold:
            return signals
        
        # Generate signal based on leverage
        if metrics.current_leverage < metrics.optimal_leverage * 0.8:
            # Under-leveraged
            signal_type = 'buy'
            reason = f"Under-leveraged ({metrics.current_leverage:.2f}x) - potential to increase"
            confidence = metrics.leverage_efficiency
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif metrics.current_leverage > metrics.optimal_leverage * 1.2:
            # Over-leveraged
            signal_type = 'sell'
            reason = f"Over-leveraged ({metrics.current_leverage:.2f}x) - need to reduce"
            confidence = metrics.leverage_efficiency
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(LeverageSignal(
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
                'current_leverage': metrics.current_leverage,
                'optimal_leverage': metrics.optimal_leverage,
                'margin_usage': metrics.margin_usage,
                'risk_score': metrics.risk_score
            }
        ))
        
        return signals
    
    def _get_status(self, metrics: LeverageMetrics) -> str:
        """
        Get status from leverage metrics.
        
        Args:
            metrics: LeverageMetrics object
            
        Returns:
            Status string
        """
        ratio = metrics.current_leverage / metrics.optimal_leverage if metrics.optimal_leverage > 0 else 1
        
        if ratio > 1.2:
            return 'over_leveraged'
        elif ratio > 0.8:
            return 'optimal'
        else:
            return 'under_leveraged'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: LeverageMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: LeverageMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'over_leveraged': f"Over-leveraged ({metrics.current_leverage:.2f}x)",
            'optimal': f"Optimal leverage ({metrics.current_leverage:.2f}x)",
            'under_leveraged': f"Under-leveraged ({metrics.current_leverage:.2f}x)"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get leverage metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_leverage': np.mean([m.current_leverage for m in self.metrics_history]),
            'max_leverage_used': max([m.current_leverage for m in self.metrics_history]),
            'min_leverage_used': min([m.current_leverage for m in self.metrics_history]),
            'average_margin_usage': np.mean([m.margin_usage for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_leverage_model(config: Optional[Dict[str, Any]] = None) -> LeverageModel:
    """
    Create a leverage model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        LeverageModel instance
    """
    return LeverageModel(config)


__all__ = [
    'LeverageMetrics',
    'LeverageSignal',
    'LeverageModel',
    'create_leverage_model'
]
