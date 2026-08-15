"""
Swing Bot Calmar Model
========================

This module provides Calmar ratio analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class CalmarMetrics:
    """Calmar ratio metrics data structure."""
    timestamp: datetime
    calmar_ratio: float
    annualized_return: float
    max_drawdown: float
    recovery_time: float
    var_95: float
    expected_shortfall: float
    ulcer_index: float
    martin_ratio: float
    sterling_ratio: float


@dataclass
class CalmarSignal:
    """Calmar trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: CalmarMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class CalmarModel:
    """
    Calmar ratio analysis model for risk-adjusted returns.
    
    Implements Calmar ratio and related risk metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Calmar model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 252)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[CalmarMetrics] = []
        
    def calculate(self, returns: np.ndarray, prices: np.ndarray) -> CalmarMetrics:
        """
        Calculate Calmar ratio and related metrics.
        
        Args:
            returns: Returns array
            prices: Price array
            
        Returns:
            CalmarMetrics object
        """
        if len(returns) < 2 or len(prices) < 2:
            return self._get_default_metrics()
        
        # Calculate annualized return
        total_return = (prices[-1] - prices[0]) / prices[0]
        annualized_return = (1 + total_return) ** (252 / len(returns)) - 1
        
        # Calculate maximum drawdown
        max_drawdown, max_price, max_index = MathUtils.max_drawdown(prices)
        
        # Calculate Calmar ratio
        if abs(max_drawdown) > 0:
            calmar_ratio = annualized_return / abs(max_drawdown)
        else:
            calmar_ratio = float('inf') if annualized_return > 0 else 0.0
        
        # Calculate recovery time
        recovery_time = self._calculate_recovery_time(prices, max_index)
        
        # Calculate VaR
        var_95 = np.percentile(returns, 5)
        
        # Calculate Expected Shortfall
        tail_returns = returns[returns <= var_95]
        expected_shortfall = np.mean(tail_returns) if len(tail_returns) > 0 else var_95
        
        # Calculate Ulcer Index
        ulcer_index = self._calculate_ulcer_index(prices)
        
        # Calculate Martin Ratio
        if ulcer_index > 0:
            martin_ratio = annualized_return / (ulcer_index * 100)
        else:
            martin_ratio = 0.0
        
        # Calculate Sterling Ratio
        if abs(max_drawdown) > 0:
            sterling_ratio = annualized_return / (abs(max_drawdown) + 0.1)
        else:
            sterling_ratio = 0.0
        
        metrics = CalmarMetrics(
            timestamp=datetime.now(),
            calmar_ratio=calmar_ratio,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            recovery_time=recovery_time,
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            ulcer_index=ulcer_index,
            martin_ratio=martin_ratio,
            sterling_ratio=sterling_ratio
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_recovery_time(self, prices: np.ndarray, max_index: int) -> float:
        """
        Calculate recovery time from maximum drawdown.
        
        Args:
            prices: Price array
            max_index: Index of maximum drawdown
            
        Returns:
            Recovery time in days
        """
        if max_index >= len(prices) - 1:
            return 0.0
        
        max_price = prices[max_index]
        for i in range(max_index + 1, len(prices)):
            if prices[i] >= max_price:
                return i - max_index
        
        return len(prices) - max_index - 1
    
    def _calculate_ulcer_index(self, prices: np.ndarray) -> float:
        """
        Calculate Ulcer Index.
        
        Args:
            prices: Price array
            
        Returns:
            Ulcer Index
        """
        if len(prices) < 2:
            return 0.0
        
        # Calculate running maximum
        running_max = np.maximum.accumulate(prices)
        
        # Calculate percentage drawdowns
        drawdowns = (prices - running_max) / running_max
        
        # Calculate Ulcer Index
        ulcer = np.sqrt(np.mean(drawdowns ** 2))
        
        return ulcer
    
    def _get_default_metrics(self) -> CalmarMetrics:
        """
        Get default metrics.
        
        Returns:
            Default CalmarMetrics object
        """
        return CalmarMetrics(
            timestamp=datetime.now(),
            calmar_ratio=0.0,
            annualized_return=0.0,
            max_drawdown=0.0,
            recovery_time=0.0,
            var_95=0.0,
            expected_shortfall=0.0,
            ulcer_index=0.0,
            martin_ratio=0.0,
            sterling_ratio=0.0
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Calmar metrics for a trading system.
        
        Args:
            df: OHLCV data
            
        Returns:
            Analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate returns and prices
        returns = df['close'].pct_change().dropna().values
        prices = df['close'].values
        
        # Calculate metrics
        metrics = self.calculate(returns, prices)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: CalmarMetrics) -> List[CalmarSignal]:
        """
        Generate trading signals from Calmar metrics.
        
        Args:
            df: OHLCV data
            metrics: CalmarMetrics object
            
        Returns:
            List of CalmarSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if Calmar ratio is significant
        if metrics.calmar_ratio > 1.0:
            confidence = min(metrics.calmar_ratio / 2, 1.0)
            
            if confidence > self.confidence_threshold:
                signal_type = 'buy'
                reason = "Strong Calmar ratio indicating good risk-adjusted returns"
                target = current_price * (1 + confidence * 0.05)
                stop_loss = current_price * (1 - confidence * 0.03)
                
                signals.append(CalmarSignal(
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
                        'calmar_ratio': metrics.calmar_ratio,
                        'max_drawdown': metrics.max_drawdown
                    }
                ))
        
        # Check if Calmar ratio is negative
        elif metrics.calmar_ratio < -0.5:
            confidence = min(abs(metrics.calmar_ratio) / 2, 1.0)
            
            if confidence > self.confidence_threshold:
                signal_type = 'sell'
                reason = "Weak Calmar ratio indicating poor risk-adjusted returns"
                target = current_price * (1 - confidence * 0.05)
                stop_loss = current_price * (1 + confidence * 0.03)
                
                signals.append(CalmarSignal(
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
                        'calmar_ratio': metrics.calmar_ratio,
                        'max_drawdown': metrics.max_drawdown
                    }
                ))
        
        return signals
    
    def _get_status(self, metrics: CalmarMetrics) -> str:
        """
        Get status from Calmar metrics.
        
        Args:
            metrics: CalmarMetrics object
            
        Returns:
            Status string
        """
        if metrics.calmar_ratio > 1.0:
            return 'excellent'
        elif metrics.calmar_ratio > 0.5:
            return 'good'
        elif metrics.calmar_ratio > 0.0:
            return 'moderate'
        elif metrics.calmar_ratio > -0.5:
            return 'poor'
        else:
            return 'very_poor'
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get Calmar metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_calmar': np.mean([m.calmar_ratio for m in self.metrics_history]),
            'best_calmar': max([m.calmar_ratio for m in self.metrics_history]),
            'worst_calmar': min([m.calmar_ratio for m in self.metrics_history]),
            'average_max_drawdown': np.mean([m.max_drawdown for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_calmar_model(config: Optional[Dict[str, Any]] = None) -> CalmarModel:
    """
    Create a Calmar model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        CalmarModel instance
    """
    return CalmarModel(config)


__all__ = [
    'CalmarMetrics',
    'CalmarSignal',
    'CalmarModel',
    'create_calmar_model'
]
