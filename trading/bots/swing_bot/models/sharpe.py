"""
Swing Bot Sharpe Model
========================

This module provides Sharpe ratio analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class SharpeMetrics:
    """Sharpe ratio metrics data structure."""
    timestamp: datetime
    sharpe_ratio: float
    modified_sharpe: float
    probabilistic_sharpe: float
    annualized_return: float
    volatility: float
    risk_free_rate: float
    downside_deviation: float
    var_95: float
    expected_shortfall: float


@dataclass
class SharpeSignal:
    """Sharpe trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: SharpeMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class SharpeModel:
    """
    Sharpe ratio analysis model for risk-adjusted returns.
    
    Implements Sharpe ratio and related risk metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Sharpe model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.risk_free_rate = self.config.get('risk_free_rate', 0.02)
        self.lookback_period = self.config.get('lookback_period', 252)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[SharpeMetrics] = []
        
    def calculate(self, returns: np.ndarray) -> SharpeMetrics:
        """
        Calculate Sharpe ratio and related metrics.
        
        Args:
            returns: Returns array
            
        Returns:
            SharpeMetrics object
        """
        if len(returns) < 2:
            return self._get_default_metrics()
        
        # Calculate annualized return
        mean_return = np.mean(returns)
        annualized_return = (1 + mean_return) ** 252 - 1
        
        # Calculate volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Calculate Sharpe ratio
        if volatility > 0:
            sharpe_ratio = (annualized_return - self.risk_free_rate) / volatility
        else:
            sharpe_ratio = 0.0
        
        # Calculate modified Sharpe (using downside deviation)
        downside_returns = returns[returns < self.risk_free_rate / 252]
        if len(downside_returns) > 0:
            downside_deviation = np.std(downside_returns) * np.sqrt(252)
        else:
            downside_deviation = 0.0
        
        if downside_deviation > 0:
            modified_sharpe = (annualized_return - self.risk_free_rate) / downside_deviation
        else:
            modified_sharpe = float('inf') if annualized_return > self.risk_free_rate else 0.0
        
        # Calculate probabilistic Sharpe
        probabilistic_sharpe = self._calculate_probabilistic_sharpe(returns)
        
        # Calculate VaR
        var_95 = np.percentile(returns, 5) * np.sqrt(252)
        
        # Calculate Expected Shortfall
        tail_returns = returns[returns <= np.percentile(returns, 5)]
        expected_shortfall = np.mean(tail_returns) * np.sqrt(252) if len(tail_returns) > 0 else var_95
        
        metrics = SharpeMetrics(
            timestamp=datetime.now(),
            sharpe_ratio=sharpe_ratio,
            modified_sharpe=modified_sharpe,
            probabilistic_sharpe=probabilistic_sharpe,
            annualized_return=annualized_return,
            volatility=volatility,
            risk_free_rate=self.risk_free_rate,
            downside_deviation=downside_deviation,
            var_95=var_95,
            expected_shortfall=expected_shortfall
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_probabilistic_sharpe(self, returns: np.ndarray) -> float:
        """
        Calculate probabilistic Sharpe ratio.
        
        Args:
            returns: Returns array
            
        Returns:
            Probabilistic Sharpe ratio
        """
        if len(returns) < 30:
            return 0.0
        
        # Bootstrap to get distribution of Sharpe ratios
        n_iterations = 1000
        sharpe_values = []
        
        for _ in range(n_iterations):
            sample = np.random.choice(returns, size=len(returns), replace=True)
            mean = np.mean(sample)
            std = np.std(sample)
            
            if std > 0:
                annualized = (1 + mean) ** 252 - 1
                annualized_std = std * np.sqrt(252)
                sharpe = (annualized - self.risk_free_rate) / annualized_std if annualized_std > 0 else 0
                sharpe_values.append(sharpe)
        
        # Return median of bootstrap distribution
        if sharpe_values:
            return np.median(sharpe_values)
        return 0.0
    
    def _get_default_metrics(self) -> SharpeMetrics:
        """
        Get default metrics.
        
        Returns:
            Default SharpeMetrics object
        """
        return SharpeMetrics(
            timestamp=datetime.now(),
            sharpe_ratio=0.0,
            modified_sharpe=0.0,
            probabilistic_sharpe=0.0,
            annualized_return=0.0,
            volatility=0.0,
            risk_free_rate=self.risk_free_rate,
            downside_deviation=0.0,
            var_95=0.0,
            expected_shortfall=0.0
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Sharpe metrics for a trading system.
        
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
                         metrics: SharpeMetrics) -> List[SharpeSignal]:
        """
        Generate trading signals from Sharpe metrics.
        
        Args:
            df: OHLCV data
            metrics: SharpeMetrics object
            
        Returns:
            List of SharpeSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if Sharpe ratio is significant
        if metrics.sharpe_ratio > 0.5:
            confidence = min(metrics.sharpe_ratio, 1.0)
            
            if confidence > self.confidence_threshold:
                signal_type = 'buy'
                reason = "Strong Sharpe ratio indicating good risk-adjusted returns"
                target = current_price * (1 + confidence * 0.05)
                stop_loss = current_price * (1 - confidence * 0.03)
                
                signals.append(SharpeSignal(
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
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'volatility': metrics.volatility
                    }
                ))
        
        # Check if Sharpe ratio is negative
        elif metrics.sharpe_ratio < -0.3:
            confidence = min(abs(metrics.sharpe_ratio), 1.0)
            
            if confidence > self.confidence_threshold:
                signal_type = 'sell'
                reason = "Negative Sharpe ratio indicating poor risk-adjusted returns"
                target = current_price * (1 - confidence * 0.05)
                stop_loss = current_price * (1 + confidence * 0.03)
                
                signals.append(SharpeSignal(
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
                        'sharpe_ratio': metrics.sharpe_ratio,
                        'volatility': metrics.volatility
                    }
                ))
        
        return signals
    
    def _get_status(self, metrics: SharpeMetrics) -> str:
        """
        Get status from Sharpe metrics.
        
        Args:
            metrics: SharpeMetrics object
            
        Returns:
            Status string
        """
        if metrics.sharpe_ratio > 1.0:
            return 'excellent'
        elif metrics.sharpe_ratio > 0.5:
            return 'good'
        elif metrics.sharpe_ratio > 0.0:
            return 'moderate'
        elif metrics.sharpe_ratio > -0.5:
            return 'poor'
        else:
            return 'very_poor'
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get Sharpe metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_sharpe': np.mean([m.sharpe_ratio for m in self.metrics_history]),
            'best_sharpe': max([m.sharpe_ratio for m in self.metrics_history]),
            'worst_sharpe': min([m.sharpe_ratio for m in self.metrics_history]),
            'average_volatility': np.mean([m.volatility for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_sharpe_model(config: Optional[Dict[str, Any]] = None) -> SharpeModel:
    """
    Create a Sharpe model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SharpeModel instance
    """
    return SharpeModel(config)


__all__ = [
    'SharpeMetrics',
    'SharpeSignal',
    'SharpeModel',
    'create_sharpe_model'
]
