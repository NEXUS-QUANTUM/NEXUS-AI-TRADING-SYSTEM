"""
Swing Bot Adaptive Model
==========================

This module provides adaptive trading models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class AdaptiveState:
    """Adaptive state data structure."""
    timestamp: datetime
    market_conditions: Dict[str, float]
    strategy_weights: Dict[str, float]
    performance: Dict[str, float]
    confidence: float
    adaptation_count: int


@dataclass
class AdaptiveSignal:
    """Adaptive trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover', 'hold'
    strategy: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class AdaptiveModel:
    """
    Adaptive trading model that adjusts to changing market conditions.
    
    Implements multiple strategies with dynamic weighting based on performance.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the adaptive model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.strategies = self.config.get('strategies', [
            'trend_following',
            'mean_reversion',
            'momentum',
            'breakout',
            'counter_trend'
        ])
        self.learning_rate = self.config.get('learning_rate', 0.01)
        self.decay_rate = self.config.get('decay_rate', 0.99)
        self.adaptation_threshold = self.config.get('adaptation_threshold', 0.10)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Initialize strategy weights
        self.strategy_weights = {s: 1.0 / len(self.strategies) for s in self.strategies}
        self.strategy_performance = {s: deque(maxlen=100) for s in self.strategies}
        self.market_conditions = {}
        self.history: List[AdaptiveState] = []
        self.adaptation_count = 0
        
    def update(self, market_data: pd.DataFrame, performance: Dict[str, float]) -> AdaptiveState:
        """
        Update adaptive model with new data.
        
        Args:
            market_data: Market data
            performance: Performance metrics
            
        Returns:
            AdaptiveState object
        """
        # Update market conditions
        self.market_conditions = self._analyze_market_conditions(market_data)
        
        # Update strategy performance
        for strategy, perf in performance.items():
            if strategy in self.strategy_performance:
                self.strategy_performance[strategy].append(perf)
        
        # Update strategy weights
        self._update_strategy_weights()
        
        # Create state
        state = AdaptiveState(
            timestamp=datetime.now(),
            market_conditions=self.market_conditions.copy(),
            strategy_weights=self.strategy_weights.copy(),
            performance=performance,
            confidence=self._calculate_confidence(),
            adaptation_count=self.adaptation_count
        )
        self.history.append(state)
        
        return state
    
    def _analyze_market_conditions(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Analyze market conditions.
        
        Args:
            market_data: Market data
            
        Returns:
            Dictionary of market conditions
        """
        if len(market_data) < 20:
            return {'volatility': 0, 'trend_strength': 0, 'volume': 0, 'momentum': 0}
        
        close = market_data['close'].values
        volume = market_data['volume'].values
        
        # Calculate metrics
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        # Trend strength (ADX approximation)
        adx = self._calculate_adx(close)
        
        # Volume momentum
        volume_ma = np.mean(volume[-20:])
        volume_velocity = (volume[-1] - volume_ma) / volume_ma if volume_ma > 0 else 0
        
        # Price momentum
        momentum = (close[-1] - close[-20]) / close[-20] if close[-20] > 0 else 0
        
        return {
            'volatility': volatility,
            'trend_strength': adx,
            'volume': volume_velocity,
            'momentum': momentum,
            'regime': self._detect_regime(volatility, adx)
        }
    
    def _calculate_adx(self, close: np.ndarray) -> float:
        """
        Calculate ADX approximation.
        
        Args:
            close: Close prices
            
        Returns:
            ADX value
        """
        if len(close) < 14:
            return 0.0
        
        # Use linear regression R² as trend strength indicator
        indices = np.arange(len(close[-14:]))
        slope, intercept = MathUtils.linear_regression(indices, close[-14:])
        r2 = MathUtils.r_squared(indices, close[-14:])
        
        return r2 * 50  # Scale to ADX range (0-100)
    
    def _detect_regime(self, volatility: float, trend_strength: float) -> str:
        """
        Detect market regime.
        
        Args:
            volatility: Volatility value
            trend_strength: Trend strength value
            
        Returns:
            Regime string
        """
        if trend_strength > 30 and volatility > 0.20:
            return 'strong_trend'
        elif trend_strength > 25:
            return 'trending'
        elif volatility > 0.30:
            return 'volatile'
        elif volatility < 0.15:
            return 'quiet'
        else:
            return 'ranging'
    
    def _update_strategy_weights(self) -> None:
        """Update strategy weights based on performance."""
        # Calculate total performance
        total_performance = 0
        for strategy in self.strategies:
            perf = list(self.strategy_performance[strategy])
            if perf:
                # Use recent average performance
                recent_perf = np.mean(perf[-10:]) if len(perf) >= 10 else np.mean(perf)
                self.strategy_performance[strategy] = deque(list(perf), maxlen=100)
            else:
                recent_perf = 0.5  # Default neutral performance
            
            # Apply decay
            self.strategy_weights[strategy] *= self.decay_rate
            
            # Add performance-based adjustment
            adjustment = self.learning_rate * (recent_perf - 0.5)
            self.strategy_weights[strategy] += adjustment
            total_performance += recent_perf
        
        # Normalize weights
        total_weight = sum(self.strategy_weights.values())
        if total_weight > 0:
            for strategy in self.strategies:
                self.strategy_weights[strategy] /= total_weight
        
        # Clamp weights
        min_weight = 0.05
        for strategy in self.strategies:
            self.strategy_weights[strategy] = max(self.strategy_weights[strategy], min_weight)
        
        # Renormalize after clamping
        total_weight = sum(self.strategy_weights.values())
        if total_weight > 0:
            for strategy in self.strategies:
                self.strategy_weights[strategy] /= total_weight
    
    def _calculate_confidence(self) -> float:
        """Calculate adaptation confidence."""
        if not self.history:
            return 0.5
        
        # Check weight convergence
        weight_std = np.std(list(self.strategy_weights.values()))
        weight_confidence = 1 - min(weight_std * 2, 1.0)
        
        # Check performance stability
        recent_perf = []
        for perf_list in self.strategy_performance.values():
            if len(perf_list) > 10:
                recent_perf.extend(list(perf_list)[-10:])
        
        if recent_perf:
            perf_std = np.std(recent_perf)
            perf_confidence = 1 - min(perf_std * 2, 1.0)
        else:
            perf_confidence = 0.5
        
        # Combined confidence
        confidence = weight_confidence * 0.6 + perf_confidence * 0.4
        return min(max(confidence, 0.0), 1.0)
    
    def generate_signal(self, market_data: pd.DataFrame) -> Optional[AdaptiveSignal]:
        """
        Generate adaptive trading signal.
        
        Args:
            market_data: Market data
            
        Returns:
            AdaptiveSignal or None
        """
        if len(market_data) < 20:
            return None
        
        # Get best strategy
        best_strategy = max(self.strategy_weights, key=self.strategy_weights.get)
        best_weight = self.strategy_weights[best_strategy]
        
        if best_weight < self.confidence_threshold:
            return None
        
        # Generate signal from best strategy
        signal = self._generate_strategy_signal(market_data, best_strategy)
        
        if signal:
            signal.confidence *= best_weight
            signal.indicators['strategy_weights'] = self.strategy_weights.copy()
            signal.indicators['market_conditions'] = self.market_conditions.copy()
        
        return signal
    
    def _generate_strategy_signal(self, market_data: pd.DataFrame,
                                  strategy: str) -> Optional[AdaptiveSignal]:
        """
        Generate signal from specific strategy.
        
        Args:
            market_data: Market data
            strategy: Strategy name
            
        Returns:
            AdaptiveSignal or None
        """
        close = market_data['close'].values
        symbol = market_data.get('symbol', [''])[0] if 'symbol' in market_data.columns else ''
        
        if strategy == 'trend_following':
            return self._trend_following_signal(close, symbol)
        elif strategy == 'mean_reversion':
            return self._mean_reversion_signal(close, symbol)
        elif strategy == 'momentum':
            return self._momentum_signal(close, symbol)
        elif strategy == 'breakout':
            return self._breakout_signal(close, symbol)
        elif strategy == 'counter_trend':
            return self._counter_trend_signal(close, symbol)
        else:
            return None
    
    def _trend_following_signal(self, close: np.ndarray, symbol: str) -> Optional[AdaptiveSignal]:
        """Generate trend following signal."""
        if len(close) < 20:
            return None
        
        # Calculate moving averages
        ma20 = np.mean(close[-20:])
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else ma20
        
        # Calculate slope
        indices = np.arange(20)
        slope, intercept = MathUtils.linear_regression(indices, close[-20:])
        
        current_price = close[-1]
        
        if slope > 0 and current_price > ma20 > ma50:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='buy',
                strategy='trend_following',
                confidence=min(slope * 5, 1.0),
                price=current_price,
                target=current_price * (1 + 0.05),
                stop_loss=current_price * (1 - 0.025),
                reason=f"Uptrend detected (slope: {slope:.4f})"
            )
        elif slope < 0 and current_price < ma20 < ma50:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                strategy='trend_following',
                confidence=min(abs(slope) * 5, 1.0),
                price=current_price,
                target=current_price * (1 - 0.05),
                stop_loss=current_price * (1 + 0.025),
                reason=f"Downtrend detected (slope: {slope:.4f})"
            )
        
        return None
    
    def _mean_reversion_signal(self, close: np.ndarray, symbol: str) -> Optional[AdaptiveSignal]:
        """Generate mean reversion signal."""
        if len(close) < 20:
            return None
        
        # Calculate z-score
        mean = np.mean(close[-20:])
        std = np.std(close[-20:])
        current_price = close[-1]
        
        if std == 0:
            return None
        
        zscore = (current_price - mean) / std
        
        if zscore > 2.0:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                strategy='mean_reversion',
                confidence=min(zscore / 4, 1.0),
                price=current_price,
                target=mean,
                stop_loss=current_price * 1.02,
                reason=f"Overbought (z-score: {zscore:.2f})"
            )
        elif zscore < -2.0:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='buy',
                strategy='mean_reversion',
                confidence=min(abs(zscore) / 4, 1.0),
                price=current_price,
                target=mean,
                stop_loss=current_price * 0.98,
                reason=f"Oversold (z-score: {zscore:.2f})"
            )
        
        return None
    
    def _momentum_signal(self, close: np.ndarray, symbol: str) -> Optional[AdaptiveSignal]:
        """Generate momentum signal."""
        if len(close) < 20:
            return None
        
        current_price = close[-1]
        past_price = close[-10] if len(close) >= 10 else close[0]
        momentum = (current_price - past_price) / past_price if past_price > 0 else 0
        
        if momentum > 0.03:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='buy',
                strategy='momentum',
                confidence=min(momentum * 5, 1.0),
                price=current_price,
                target=current_price * (1 + momentum * 0.5),
                stop_loss=current_price * (1 - momentum * 0.25),
                reason=f"Strong momentum ({momentum:.2%})"
            )
        elif momentum < -0.03:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                strategy='momentum',
                confidence=min(abs(momentum) * 5, 1.0),
                price=current_price,
                target=current_price * (1 + momentum * 0.5),
                stop_loss=current_price * (1 - momentum * 0.25),
                reason=f"Strong negative momentum ({momentum:.2%})"
            )
        
        return None
    
    def _breakout_signal(self, close: np.ndarray, symbol: str) -> Optional[AdaptiveSignal]:
        """Generate breakout signal."""
        if len(close) < 20:
            return None
        
        high = np.max(close[-20:])
        low = np.min(close[-20:])
        current_price = close[-1]
        
        # Check for breakout
        if current_price > high * 1.01:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='buy',
                strategy='breakout',
                confidence=min((current_price - high) / high * 5, 1.0),
                price=current_price,
                target=current_price * 1.05,
                stop_loss=high * 0.99,
                reason=f"Breakout above resistance (High: {high:.2f})"
            )
        elif current_price < low * 0.99:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                strategy='breakout',
                confidence=min((low - current_price) / low * 5, 1.0),
                price=current_price,
                target=current_price * 0.95,
                stop_loss=low * 1.01,
                reason=f"Breakout below support (Low: {low:.2f})"
            )
        
        return None
    
    def _counter_trend_signal(self, close: np.ndarray, symbol: str) -> Optional[AdaptiveSignal]:
        """Generate counter-trend signal."""
        if len(close) < 20:
            return None
        
        # Calculate RSI approximation
        gains = 0
        losses = 0
        for i in range(1, 14):
            diff = close[-i] - close[-i-1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        
        if gains + losses == 0:
            return None
        
        rsi = 100 - (100 / (1 + gains / losses))
        current_price = close[-1]
        
        if rsi > 70:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                strategy='counter_trend',
                confidence=min((rsi - 70) / 30, 1.0),
                price=current_price,
                target=current_price * 0.98,
                stop_loss=current_price * 1.015,
                reason=f"Overbought (RSI: {rsi:.1f})"
            )
        elif rsi < 30:
            return AdaptiveSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type='buy',
                strategy='counter_trend',
                confidence=min((30 - rsi) / 30, 1.0),
                price=current_price,
                target=current_price * 1.02,
                stop_loss=current_price * 0.985,
                reason=f"Oversold (RSI: {rsi:.1f})"
            )
        
        return None
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of current adaptive state.
        
        Returns:
            State summary dictionary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'strategy_weights': self.strategy_weights,
            'market_conditions': self.market_conditions,
            'confidence': self._calculate_confidence(),
            'adaptation_count': self.adaptation_count,
            'history_length': len(self.history),
            'performance_summary': {
                strategy: {
                    'avg': np.mean(list(perf)) if perf else 0,
                    'std': np.std(list(perf)) if perf else 0,
                    'min': np.min(list(perf)) if perf else 0,
                    'max': np.max(list(perf)) if perf else 0
                }
                for strategy, perf in self.strategy_performance.items()
                if perf
            }
        }


def create_adaptive_model(config: Optional[Dict[str, Any]] = None) -> AdaptiveModel:
    """
    Create an adaptive model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        AdaptiveModel instance
    """
    return AdaptiveModel(config)


__all__ = [
    'AdaptiveState',
    'AdaptiveSignal',
    'AdaptiveModel',
    'create_adaptive_model'
]
