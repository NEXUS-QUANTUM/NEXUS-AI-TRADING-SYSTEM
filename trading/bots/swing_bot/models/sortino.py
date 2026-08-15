"""
Swing Bot Sortino Model
=========================

This module provides Sortino ratio analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class SortinoMetrics:
    """Sortino ratio metrics data structure."""
    timestamp: datetime
    sortino_ratio: float
    modified_sortino: float
    downside_risk: float
    target_return: float
    excess_return: float
    semideviation: float
    var_95: float
    expected_shortfall: float
    upside_potential: float


@dataclass
class SortinoSignal:
    """Sortino trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: SortinoMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class SortinoModel:
    """
    Sortino ratio analysis model for risk-adjusted returns.
    
    Implements Sortino ratio and related risk metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Sortino model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.target_return = self.config.get('target_return', 0.0)
        self.lookback_period = self.config.get('lookback_period', 252)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[SortinoMetrics] = []
        
    def calculate(self, returns: np.ndarray) -> SortinoMetrics:
        """
        Calculate Sortino ratio and related metrics.
        
        Args:
            returns: Returns array
            
        Returns:
            SortinoMetrics object
        """
        if len(returns) < 2:
            return self._get_default_metrics()
        
        # Calculate excess return
        mean_return = np.mean(returns)
        excess_return = mean_return - self.target_return
        
        # Calculate downside deviation (semideviation)
        downside_returns = returns[returns < self.target_return]
        
        if len(downside_returns) > 0:
            downside_risk = np.std(downside_returns)
            semideviation = np.sqrt(np.mean((downside_returns - self.target_return) ** 2))
        else:
            downside_risk = 0.0
            semideviation = 0.0
        
        # Calculate Sortino ratio
        if downside_risk > 0:
            sortino_ratio = excess_return / downside_risk * np.sqrt(252)
        else:
            sortino_ratio = float('inf') if excess_return > 0 else 0.0
        
        # Calculate modified Sortino (using semideviation)
        if semideviation > 0:
            modified_sortino = excess_return / semideviation * np.sqrt(252)
        else:
            modified_sortino = float('inf') if excess_return > 0 else 0.0
        
        # Calculate VaR
        var_95 = np.percentile(returns, 5)
        
        # Calculate Expected Shortfall
        tail_returns = returns[returns <= var_95]
        expected_shortfall = np.mean(tail_returns) if len(tail_returns) > 0 else var_95
        
        # Calculate Upside Potential
        upside_returns = returns[returns > 0]
        upside_potential = np.mean(upside_returns) if len(upside_returns) > 0 else 0
        
        metrics = SortinoMetrics(
            timestamp=datetime.now(),
            sortino_ratio=sortino_ratio,
            modified_sortino=modified_sortino,
            downside_risk=downside_risk,
            target_return=self.target_return,
            excess_return=excess_return,
            semideviation=semideviation,
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            upside_potential=upside_potential
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> SortinoMetrics:
        """
        Get default metrics.
        
        Returns:
            Default SortinoMetrics object
        """
        return SortinoMetrics(
            timestamp=datetime.now(),
            sortino_ratio=0.0,
            modified_sortino=0.0,
            downside_risk=0.0,
            target_return=self.target_return,
            excess_return=0.0,
            semideviation=0.0,
            var_95=0.0,
            expected_shortfall=0.0,
            upside_potential=0.0
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Sortino metrics for a trading system.
        
        Args:
            df: OHLCV data
            
        Returns:
            Analysis results
        """
        if len(df) < self.lookback_period:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate returns
        returns = df['close'].pct_change().dropna().values
        
        # Calculate metrics
        metrics = self.calculate(returns)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: SortinoMetrics) -> List[SortinoSignal]:
        """
        Generate trading signals from Sortino metrics.
        
        Args:
            df: OHLCV data
            metrics: SortinoMetrics object
            
        Returns:
            List of SortinoSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if Sortino ratio is significant
        if metrics.sortino_ratio > 1.0:
            # Good risk-adjusted returns
            confidence = min(metrics.sortino_ratio / 2, 1.0)
            
            if confidence > self.confidence_threshold:
                # Check trend
                if df['close'].iloc[-1] > df['close'].iloc[-5]:
                    signal_type = 'buy'
                    reason = "Strong Sortino ratio with positive trend"
                    target = current_price * (1 + confidence * 0.05)
                    stop_loss = current_price * (1 - confidence * 0.03)
                    
                    signals.append(SortinoSignal(
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
                            'sortino_ratio': metrics.sortino_ratio,
                            'downside_risk': metrics.downside_risk
                        }
                    ))
        
        # Check if Sortino ratio is negative
        elif metrics.sortino_ratio < -0.5:
            # Poor risk-adjusted returns
            confidence = min(abs(metrics.sortino_ratio) / 2, 1.0)
            
            if confidence > self.confidence_threshold:
                signal_type = 'sell'
                reason = "Weak Sortino ratio indicating poor risk-adjusted returns"
                target = current_price * (1 - confidence * 0.05)
                stop_loss = current_price * (1 + confidence * 0.03)
                
                signals.append(SortinoSignal(
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
                        'sortino_ratio': metrics.sortino_ratio,
                        'downside_risk': metrics.downside_risk
                    }
                ))
        
        return signals
    
    def _get_status(self, metrics: SortinoMetrics) -> str:
        """
        Get status from Sortino metrics.
        
        Args:
            metrics: SortinoMetrics object
            
        Returns:
            Status string
        """
        if metrics.sortino_ratio > 1.0:
            return 'excellent'
        elif metrics.sortino_ratio > 0.5:
            return 'good'
        elif metrics.sortino_ratio > 0.0:
            return 'moderate'
        elif metrics.sortino_ratio > -0.5:
            return 'poor'
        else:
            return 'very_poor'
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get Sortino metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_sortino': np.mean([m.sortino_ratio for m in self.metrics_history]),
            'best_sortino': max([m.sortino_ratio for m in self.metrics_history]),
            'worst_sortino': min([m.sortino_ratio for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_sortino_model(config: Optional[Dict[str, Any]] = None) -> SortinoModel:
    """
    Create a Sortino model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SortinoModel instance
    """
    return SortinoModel(config)


__all__ = [
    'SortinoMetrics',
    'SortinoSignal',
    'SortinoModel',
    'create_sortino_model'
]
