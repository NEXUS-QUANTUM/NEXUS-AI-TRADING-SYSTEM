"""
Swing Bot Retracement Model
=============================

This module provides retracement analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class RetracementLevel:
    """Retracement level data structure."""
    level_type: str  # 'fibonacci', 'percentage', 'custom'
    level: float
    price: float
    strength: float
    confidence: float
    timestamp: datetime
    description: str = ""


@dataclass
class RetracementPattern:
    """Retracement pattern data structure."""
    pattern_type: str  # 'pullback', 'retracement', 'reversal'
    start_price: float
    end_price: float
    retracement_percent: float
    levels: List[RetracementLevel]
    confidence: float
    timestamp: datetime


@dataclass
class RetracementSignal:
    """Retracement trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: RetracementPattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class RetracementModel:
    """
    Retracement analysis model for price corrections.
    
    Analyzes Fibonacci and percentage retracements.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the retracement model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.fibonacci_levels = self.config.get('fibonacci_levels', 
                                               [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0])
        self.percentage_levels = self.config.get('percentage_levels',
                                               [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze retracement patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Retracement analysis results
        """
        if len(df) < self.lookback_period:
            return {'patterns': [], 'signals': []}
        
        # Detect swings
        swings = self._detect_swings(df)
        
        # Analyze retracements
        patterns = self._analyze_retracements(df, swings)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_swings(self, df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect swing highs and lows.
        
        Args:
            df: OHLCV data
            
        Returns:
            Dictionary of swing highs and lows
        """
        high = df['high'].values
        low = df['low'].values
        lookback = 5
        
        swings = {'highs': [], 'lows': []}
        
        for i in range(lookback, len(df) - lookback):
            # Check for swing high
            is_high = True
            for j in range(lookback):
                if high[i] <= high[i - j - 1] or high[i] <= high[i + j + 1]:
                    is_high = False
                    break
            if is_high:
                swings['highs'].append({
                    'index': i,
                    'price': high[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
            
            # Check for swing low
            is_low = True
            for j in range(lookback):
                if low[i] >= low[i - j - 1] or low[i] >= low[i + j + 1]:
                    is_low = False
                    break
            if is_low:
                swings['lows'].append({
                    'index': i,
                    'price': low[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
        
        return swings
    
    def _analyze_retracements(self, df: pd.DataFrame,
                            swings: Dict[str, List[Dict[str, Any]]]) -> List[RetracementPattern]:
        """
        Analyze retracement patterns.
        
        Args:
            df: OHLCV data
            swings: Swing points
            
        Returns:
            List of RetracementPattern objects
        """
        patterns = []
        
        # Analyze pullbacks (down to up)
        for i in range(len(swings['lows']) - 1):
            for j in range(i + 1, len(swings['lows'])):
                low1 = swings['lows'][i]
                low2 = swings['lows'][j]
                
                if low1['price'] < low2['price']:
                    continue
                
                # Find peak between lows
                peak = max(swings['highs'], 
                          key=lambda x: x['price'] if low1['index'] < x['index'] < low2['index'] else -float('inf'))
                
                if peak['price'] == -float('inf'):
                    continue
                
                # Calculate retracement
                retracement = (low2['price'] - low1['price']) / (peak['price'] - low1['price'])
                
                # Create pattern
                pattern = RetracementPattern(
                    pattern_type='pullback',
                    start_price=low1['price'],
                    end_price=low2['price'],
                    retracement_percent=retracement,
                    levels=self._calculate_fibonacci_levels(low1['price'], peak['price']),
                    confidence=self._calculate_confidence(df, low1, peak, low2),
                    timestamp=datetime.now()
                )
                patterns.append(pattern)
        
        # Analyze retracements (up to down)
        for i in range(len(swings['highs']) - 1):
            for j in range(i + 1, len(swings['highs'])):
                high1 = swings['highs'][i]
                high2 = swings['highs'][j]
                
                if high1['price'] > high2['price']:
                    continue
                
                # Find trough between peaks
                trough = min(swings['lows'],
                           key=lambda x: x['price'] if high1['index'] < x['index'] < high2['index'] else float('inf'))
                
                if trough['price'] == float('inf'):
                    continue
                
                # Calculate retracement
                retracement = (high2['price'] - high1['price']) / (high1['price'] - trough['price'])
                
                # Create pattern
                pattern = RetracementPattern(
                    pattern_type='retracement',
                    start_price=high1['price'],
                    end_price=high2['price'],
                    retracement_percent=retracement,
                    levels=self._calculate_fibonacci_levels(high1['price'], trough['price']),
                    confidence=self._calculate_confidence(df, high1, trough, high2),
                    timestamp=datetime.now()
                )
                patterns.append(pattern)
        
        return patterns
    
    def _calculate_fibonacci_levels(self, start_price: float, end_price: float) -> List[RetracementLevel]:
        """
        Calculate Fibonacci retracement levels.
        
        Args:
            start_price: Start price
            end_price: End price
            
        Returns:
            List of RetracementLevel objects
        """
        levels = []
        price_range = end_price - start_price
        
        for fib in self.fibonacci_levels:
            price = start_price + fib * price_range
            level = RetracementLevel(
                level_type='fibonacci',
                level=fib,
                price=price,
                strength=1 - abs(fib - 0.5) * 2,  # Strongest at 0.5
                confidence=0.7,
                timestamp=datetime.now(),
                description=f"Fibonacci {fib:.1%}"
            )
            levels.append(level)
        
        return levels
    
    def _calculate_confidence(self, df: pd.DataFrame, point1: Dict[str, Any],
                            point2: Dict[str, Any], point3: Dict[str, Any]) -> float:
        """
        Calculate confidence for retracement pattern.
        
        Args:
            df: OHLCV data
            point1: First point
            point2: Second point
            point3: Third point
            
        Returns:
            Confidence score (0-1)
        """
        # Price movement magnitude
        movement1 = abs(point2['price'] - point1['price']) / point1['price']
        movement2 = abs(point3['price'] - point2['price']) / point2['price']
        magnitude_score = min(movement1 + movement2, 1.0)
        
        # Time consistency
        time_ratio = (point3['index'] - point2['index']) / (point2['index'] - point1['index'])
        time_score = 1 - min(abs(time_ratio - 1), 0.5) * 2
        
        # Volume confirmation
        volume_section1 = df['volume'].iloc[point1['index']:point2['index']].mean()
        volume_section2 = df['volume'].iloc[point2['index']:point3['index']].mean()
        volume_score = min(volume_section2 / volume_section1 if volume_section1 > 0 else 1, 1.0)
        
        # Weighted combination
        confidence = (magnitude_score * 0.4 + time_score * 0.3 + volume_score * 0.3)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[RetracementPattern]) -> List[RetracementSignal]:
        """
        Generate trading signals from retracement patterns.
        
        Args:
            df: OHLCV data
            patterns: List of retracement patterns
            
        Returns:
            List of RetracementSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check for bullish retracement
        if latest_pattern.pattern_type == 'pullback':
            if latest_pattern.retracement_percent > 0.382:
                signal_type = 'buy'
                reason = f"Bullish retracement of {latest_pattern.retracement_percent:.1%}"
                target = latest_pattern.start_price * 1.02
                stop_loss = current_price * 0.98
            else:
                return None
        
        # Check for bearish retracement
        elif latest_pattern.pattern_type == 'retracement':
            if latest_pattern.retracement_percent > 0.382:
                signal_type = 'sell'
                reason = f"Bearish retracement of {latest_pattern.retracement_percent:.1%}"
                target = latest_pattern.start_price * 0.98
                stop_loss = current_price * 1.02
            else:
                return None
        else:
            return None
        
        signal = RetracementSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=latest_pattern.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            pattern=latest_pattern,
            indicators={
                'retracement_percent': latest_pattern.retracement_percent,
                'levels': latest_pattern.levels
            }
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[RetracementPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of retracement patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No retracement patterns detected"
        
        latest = patterns[-1]
        
        if latest.pattern_type == 'pullback':
            return f"Bullish pullback ({latest.retracement_percent:.1%} retracement)"
        else:
            return f"Bearish retracement ({latest.retracement_percent:.1%} retracement)"


def create_retracement_model(config: Optional[Dict[str, Any]] = None) -> RetracementModel:
    """
    Create a retracement model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        RetracementModel instance
    """
    return RetracementModel(config)


__all__ = [
    'RetracementLevel',
    'RetracementPattern',
    'RetracementSignal',
    'RetracementModel',
    'create_retracement_model'
]
