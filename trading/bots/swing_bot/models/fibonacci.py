"""
Swing Bot Fibonacci Model
===========================

This module provides Fibonacci analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class FibonacciLevel:
    """Fibonacci level data structure."""
    level_type: str  # 'retracement', 'extension', 'projection'
    ratio: float
    price: float
    strength: float
    confidence: float
    timestamp: datetime


@dataclass
class FibonacciSignal:
    """Fibonacci trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    levels: List[FibonacciLevel]
    indicators: Dict[str, Any] = field(default_factory=dict)


class FibonacciModel:
    """
    Fibonacci analysis model for price levels.
    
    Implements Fibonacci retracement, extension, and projection analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Fibonacci model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.retracement_ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        self.extension_ratios = [0.618, 1.0, 1.272, 1.382, 1.618, 2.0, 2.618]
        self.projection_ratios = [0.618, 1.0, 1.272, 1.618]
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.levels_history: List[FibonacciLevel] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Fibonacci levels.
        
        Args:
            df: OHLCV data
            
        Returns:
            Fibonacci analysis results
        """
        if len(df) < self.lookback_period:
            return {'levels': [], 'signals': []}
        
        # Find swing points
        swing_highs = self._find_swing_points(df['high'].values, 'high')
        swing_lows = self._find_swing_points(df['low'].values, 'low')
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return {'levels': [], 'signals': []}
        
        # Calculate Fibonacci levels
        levels = self._calculate_fibonacci_levels(df, swing_highs, swing_lows)
        
        # Generate signals
        signals = self._generate_signals(df, levels)
        
        return {
            'levels': levels,
            'signals': signals,
            'current_level': levels[-1] if levels else None,
            'market_character': self._get_market_character(df, levels)
        }
    
    def _find_swing_points(self, prices: np.ndarray, point_type: str) -> List[Dict[str, Any]]:
        """
        Find swing high or low points.
        
        Args:
            prices: Price array
            point_type: 'high' or 'low'
            
        Returns:
            List of swing points
        """
        swings = []
        lookback = 5
        
        for i in range(lookback, len(prices) - lookback):
            if point_type == 'high':
                is_swing = True
                for j in range(lookback):
                    if prices[i] <= prices[i - j - 1] or prices[i] <= prices[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': prices[i]})
            else:
                is_swing = True
                for j in range(lookback):
                    if prices[i] >= prices[i - j - 1] or prices[i] >= prices[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': prices[i]})
        
        return swings
    
    def _calculate_fibonacci_levels(self, df: pd.DataFrame,
                                  swing_highs: List[Dict[str, Any]],
                                  swing_lows: List[Dict[str, Any]]) -> List[FibonacciLevel]:
        """
        Calculate Fibonacci levels.
        
        Args:
            df: OHLCV data
            swing_highs: Swing highs
            swing_lows: Swing lows
            
        Returns:
            List of FibonacciLevel objects
        """
        levels = []
        
        # Get latest swing high and low
        latest_high = swing_highs[-1] if swing_highs else None
        latest_low = swing_lows[-1] if swing_lows else None
        
        if not latest_high or not latest_low:
            return levels
        
        # Determine direction
        if latest_high['index'] > latest_low['index']:
            # Uptrend - calculate retracement levels
            start_price = latest_low['price']
            end_price = latest_high['price']
            level_type = 'retracement'
        else:
            # Downtrend - calculate retracement levels
            start_price = latest_high['price']
            end_price = latest_low['price']
            level_type = 'retracement'
        
        # Calculate retracement levels
        for ratio in self.retracement_ratios:
            if level_type == 'retracement':
                price = start_price + (end_price - start_price) * ratio
            else:
                price = start_price - (start_price - end_price) * ratio
            
            strength = 1 - abs(ratio - 0.5) * 2  # Strongest at 0.5
            confidence = self._calculate_level_confidence(df, price, ratio)
            
            level = FibonacciLevel(
                level_type='retracement',
                ratio=ratio,
                price=price,
                strength=strength,
                confidence=confidence,
                timestamp=datetime.now()
            )
            levels.append(level)
            
            # Store in history
            self.levels_history.append(level)
        
        # Calculate extension levels
        extension_ratios = self.extension_ratios if level_type == 'retracement' else self.extension_ratios
        
        for ratio in extension_ratios:
            if level_type == 'retracement':
                price = end_price + (end_price - start_price) * ratio
            else:
                price = start_price - (start_price - end_price) * ratio
            
            strength = 1 - abs(ratio - 1.0) * 0.5
            confidence = self._calculate_level_confidence(df, price, ratio)
            
            level = FibonacciLevel(
                level_type='extension',
                ratio=ratio,
                price=price,
                strength=strength,
                confidence=confidence,
                timestamp=datetime.now()
            )
            levels.append(level)
            
            # Store in history
            self.levels_history.append(level)
        
        return levels
    
    def _calculate_level_confidence(self, df: pd.DataFrame, price: float, ratio: float) -> float:
        """
        Calculate confidence for a Fibonacci level.
        
        Args:
            df: OHLCV data
            price: Level price
            ratio: Fibonacci ratio
            
        Returns:
            Confidence score (0-1)
        """
        close = df['close'].values
        
        # Check if price has touched this level before
        tolerance = 0.005
        touches = 0
        
        for p in close:
            if abs(p - price) / price < tolerance:
                touches += 1
        
        # Calculate confidence based on touches and ratio significance
        touch_score = min(touches / 3, 1.0)
        ratio_score = 1 - abs(ratio - 0.5) * 2  # Higher for 0.5, 0.618
        
        confidence = (touch_score * 0.4 + ratio_score * 0.6)
        
        return max(0, min(1, confidence))
    
    def _generate_signals(self, df: pd.DataFrame,
                         levels: List[FibonacciLevel]) -> List[FibonacciSignal]:
        """
        Generate trading signals from Fibonacci levels.
        
        Args:
            df: OHLCV data
            levels: List of Fibonacci levels
            
        Returns:
            List of FibonacciSignal objects
        """
        signals = []
        
        if not levels:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Find nearest levels
        retracement_levels = [l for l in levels if l.level_type == 'retracement']
        extension_levels = [l for l in levels if l.level_type == 'extension']
        
        if not retracement_levels:
            return signals
        
        # Check if price is near a Fibonacci level
        nearest_level = min(retracement_levels, key=lambda l: abs(l.price - current_price))
        distance = abs(nearest_level.price - current_price) / current_price
        
        if distance < 0.01 and nearest_level.confidence > self.confidence_threshold:
            # Price is near a Fibonacci level
            if nearest_level.ratio < 0.5:
                signal_type = 'buy'
                reason = f"Price at Fibonacci retracement {nearest_level.ratio:.1%}"
                confidence = nearest_level.confidence
                target = nearest_level.price * 1.02
                stop_loss = nearest_level.price * 0.98
            else:
                signal_type = 'sell'
                reason = f"Price at Fibonacci retracement {nearest_level.ratio:.1%}"
                confidence = nearest_level.confidence
                target = nearest_level.price * 0.98
                stop_loss = nearest_level.price * 1.02
            
            signals.append(FibonacciSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                levels=levels,
                indicators={
                    'nearest_level': nearest_level.ratio,
                    'level_price': nearest_level.price,
                    'confidence': nearest_level.confidence
                }
            ))
        
        # Check for extension targets
        if extension_levels and current_price > extension_levels[0].price:
            signal_type = 'buy'
            reason = f"Price above Fibonacci extension {extension_levels[0].ratio:.1%}"
            confidence = extension_levels[0].confidence
            target = extension_levels[1].price if len(extension_levels) > 1 else extension_levels[0].price * 1.02
            stop_loss = extension_levels[0].price * 0.98
            
            signals.append(FibonacciSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                levels=levels,
                indicators={
                    'extension_level': extension_levels[0].ratio,
                    'level_price': extension_levels[0].price
                }
            ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            levels: List[FibonacciLevel]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            levels: List of Fibonacci levels
            
        Returns:
            Market character description
        """
        if not levels:
            return "No Fibonacci levels detected"
        
        current_price = df['close'].iloc[-1]
        nearest_level = min(levels, key=lambda l: abs(l.price - current_price))
        
        return f"Near Fibonacci {nearest_level.level_type} level at {nearest_level.ratio:.1%}"
    
    def get_levels_summary(self) -> Dict[str, Any]:
        """
        Get Fibonacci levels summary.
        
        Returns:
            Levels summary
        """
        if not self.levels_history:
            return {'status': 'no_levels'}
        
        latest = self.levels_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_level': latest,
            'total_levels': len(self.levels_history),
            'retracement_levels': len([l for l in self.levels_history if l.level_type == 'retracement']),
            'extension_levels': len([l for l in self.levels_history if l.level_type == 'extension']),
            'average_confidence': np.mean([l.confidence for l in self.levels_history]),
            'current_price_relative': latest.price / self.levels_history[0].price if self.levels_history else 0
        }


def create_fibonacci_model(config: Optional[Dict[str, Any]] = None) -> FibonacciModel:
    """
    Create a Fibonacci model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FibonacciModel instance
    """
    return FibonacciModel(config)


__all__ = [
    'FibonacciLevel',
    'FibonacciSignal',
    'FibonacciModel',
    'create_fibonacci_model'
]
