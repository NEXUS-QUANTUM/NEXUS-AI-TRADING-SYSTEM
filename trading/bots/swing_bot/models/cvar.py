"""
Swing Bot CVaR Model
======================

This module provides Conditional Value at Risk (CVaR) models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy import stats


@dataclass
class CVaRMetrics:
    """CVaR metrics data structure."""
    timestamp: datetime
    cvar_95: float
    cvar_99: float
    var_95: float
    var_99: float
    expected_shortfall: float
    tail_risk: float
    volatility: float
    skewness: float
    kurtosis: float


@dataclass
class CVaRSignal:
    """CVaR trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: CVaRMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class CVaRModel:
    """
    Conditional Value at Risk (CVaR) model for risk assessment.
    
    Implements CVaR and related risk metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CVaR model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 252)
        self.confidence_levels = self.config.get('confidence_levels', [0.95, 0.99])
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[CVaRMetrics] = []
        
    def calculate(self, returns: np.ndarray) -> CVaRMetrics:
        """
        Calculate CVaR and related metrics.
        
        Args:
            returns: Returns array
            
        Returns:
            CVaRMetrics object
        """
        if len(returns) < 2:
            return self._get_default_metrics()
        
        # Calculate VaR and CVaR for different confidence levels
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        
        # Calculate CVaR (Expected Shortfall)
        tail_returns_95 = returns[returns <= var_95]
        cvar_95 = np.mean(tail_returns_95) if len(tail_returns_95) > 0 else var_95
        
        tail_returns_99 = returns[returns <= var_99]
        cvar_99 = np.mean(tail_returns_99) if len(tail_returns_99) > 0 else var_99
        
        # Calculate Expected Shortfall (average of worst losses)
        expected_shortfall = (cvar_95 + cvar_99) / 2
        
        # Calculate Tail Risk
        tail_risk = (cvar_95 - var_95) / (var_95 + 1e-10)
        
        # Calculate volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Calculate skewness
        skewness = stats.skew(returns)
        
        # Calculate kurtosis
        kurtosis = stats.kurtosis(returns)
        
        metrics = CVaRMetrics(
            timestamp=datetime.now(),
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall=expected_shortfall,
            tail_risk=tail_risk,
            volatility=volatility,
            skewness=skewness,
            kurtosis=kurtosis
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> CVaRMetrics:
        """
        Get default metrics.
        
        Returns:
            Default CVaRMetrics object
        """
        return CVaRMetrics(
            timestamp=datetime.now(),
            cvar_95=0.0,
            cvar_99=0.0,
            var_95=0.0,
            var_99=0.0,
            expected_shortfall=0.0,
            tail_risk=0.0,
            volatility=0.0,
            skewness=0.0,
            kurtosis=0.0
        )
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze CVaR metrics for a trading system.
        
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
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: CVaRMetrics) -> List[CVaRSignal]:
        """
        Generate trading signals from CVaR metrics.
        
        Args:
            df: OHLCV data
            metrics: CVaRMetrics object
            
        Returns:
            List of CVaRSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check CVaR levels
        confidence = 1 - abs(metrics.cvar_95) * 10
        confidence = min(max(confidence, 0.0), 1.0)
        
        if confidence < self.confidence_threshold:
            return signals
        
        # Generate signal based on CVaR
        if metrics.cvar_95 > 0:
            # Positive CVaR indicates potential for losses
            signal_type = 'sell'
            reason = f"High CVaR ({metrics.cvar_95:.4f}) indicating downside risk"
            target = current_price * (1 - confidence * 0.02)
            stop_loss = current_price * (1 + confidence * 0.02)
            
            signals.append(CVaRSignal(
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
                    'cvar_95': metrics.cvar_95,
                    'var_95': metrics.var_95,
                    'tail_risk': metrics.tail_risk,
                    'volatility': metrics.volatility
                }
            ))
            
        elif metrics.cvar_95 < -0.01:
            # Negative CVaR indicates potential for gains
            signal_type = 'buy'
            reason = f"Low CVaR ({metrics.cvar_95:.4f}) indicating upside potential"
            target = current_price * (1 + confidence * 0.02)
            stop_loss = current_price * (1 - confidence * 0.02)
            
            signals.append(CVaRSignal(
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
                    'cvar_95': metrics.cvar_95,
                    'var_95': metrics.var_95,
                    'tail_risk': metrics.tail_risk,
                    'volatility': metrics.volatility
                }
            ))
        
        return signals
    
    def _get_status(self, metrics: CVaRMetrics) -> str:
        """
        Get status from CVaR metrics.
        
        Args:
            metrics: CVaRMetrics object
            
        Returns:
            Status string
        """
        if metrics.cvar_95 > 0.02:
            return 'high_risk'
        elif metrics.cvar_95 > 0.005:
            return 'moderate_risk'
        elif metrics.cvar_95 > -0.005:
            return 'neutral_risk'
        elif metrics.cvar_95 > -0.02:
            return 'low_risk'
        else:
            return 'very_low_risk'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: CVaRMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: CVaRMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'high_risk': f'High CVaR ({metrics.cvar_95:.4f}) - high downside risk',
            'moderate_risk': f'Moderate CVaR ({metrics.cvar_95:.4f})',
            'neutral_risk': f'Neutral CVaR ({metrics.cvar_95:.4f})',
            'low_risk': f'Low CVaR ({metrics.cvar_95:.4f}) - favorable risk',
            'very_low_risk': f'Very low CVaR ({metrics.cvar_95:.4f}) - attractive'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get CVaR metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_cvar_95': np.mean([m.cvar_95 for m in self.metrics_history]),
            'average_cvar_99': np.mean([m.cvar_99 for m in self.metrics_history]),
            'average_var_95': np.mean([m.var_95 for m in self.metrics_history]),
            'average_tail_risk': np.mean([m.tail_risk for m in self.metrics_history]),
            'average_volatility': np.mean([m.volatility for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_cvar_model(config: Optional[Dict[str, Any]] = None) -> CVaRModel:
    """
    Create a CVaR model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        CVaRModel instance
    """
    return CVaRModel(config)


__all__ = [
    'CVaRMetrics',
    'CVaRSignal',
    'CVaRModel',
    'create_cvar_model'
]
