"""
Swing Bot Flag Model
======================

This module provides flag pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class FlagPattern:
    """Flag pattern data structure."""
    pattern_type: str  # 'bullish', 'bearish'
    pole_length: int
    flag_length: int
    pole_start: datetime
    pole_end: datetime
    flag_start: datetime
    flag_end: datetime
    breakout_price: float
    target_price: float
    stop_loss: float
    confidence: float
    strength: float
    volume_confirmation: bool


@dataclass
class FlagSignal:
    """Flag trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: FlagPattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class FlagModel:
    """
    Flag pattern analysis model.
    
    Identifies and analyzes flag patterns:
    - Bullish flags
    - Bearish flags
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the flag model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_pole_length = self.config.get('min_pole_length', 5)
        self.max_pole_length = self.config.get('max_pole_length', 30)
        self.min_flag_length = self.config.get('min_flag_length', 3)
        self.max_flag_length = self.config.get('max_flag_length', 20)
        self.breakout_threshold = self.config.get('breakout_threshold', 0.02)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze flag patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Flag analysis results
        """
        if len(df) < self.min_pole_length + self.min_flag_length:
            return {'patterns': [], 'signals': []}
        
        # Detect patterns
        patterns = self._detect_patterns(df)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[FlagPattern]:
        """
        Detect flag patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of FlagPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Detect flags
        for i in range(len(swing_highs) - 1):
            for j in range(i + 1, len(swing_highs)):
                # Check pole length
                pole_length = swing_highs[j]['index'] - swing_highs[i]['index']
                if not (self.min_pole_length <= pole_length <= self.max_pole_length):
                    continue
                
                # Check if this is a valid pole
                pole_segment = df.iloc[swing_highs[i]['index']:swing_highs[j]['index'] + 1]
                if len(pole_segment) < 2:
                    continue
                
                # Check for flag formation
                flag_start = swing_highs[j]['index']
                flag_end = min(flag_start + self.max_flag_length, len(df) - 1)
                flag_segment = df.iloc[flag_start:flag_end + 1]
                
                if len(flag_segment) < self.min_flag_length:
                    continue
                
                # Check if flag is within pattern
                flag_high = flag_segment['high'].max()
                flag_low = flag_segment['low'].min()
                flag_range = (flag_high - flag_low) / flag_low
                
                # Check for breakout
                current_price = close[-1]
                breakout_price = flag_high if flag_segment['high'].iloc[-1] > flag_segment['high'].iloc[0] else flag_low
                
                # Determine pattern type
                if flag_segment['high'].iloc[-1] > flag_segment['high'].iloc[0]:
                    pattern_type = 'bullish'
                    breakout_price = flag_high
                    target_price = breakout_price + (breakout_price - flag_low)
                    stop_loss = flag_low * 0.98
                else:
                    pattern_type = 'bearish'
                    breakout_price = flag_low
                    target_price = breakout_price - (flag_high - breakout_price)
                    stop_loss = flag_high * 1.02
                
                # Check volume confirmation
                avg_volume = np.mean(volume[-self.min_flag_length:])
                volume_confirm = volume[-1] > avg_volume * self.volume_threshold
                
                # Calculate confidence
                confidence = self._calculate_confidence(pole_segment, flag_segment)
                
                if confidence < self.confidence_threshold:
                    continue
                
                # Calculate strength
                strength = self._calculate_strength(pole_segment, flag_segment)
                
                patterns.append(FlagPattern(
                    pattern_type=pattern_type,
                    pole_length=pole_length,
                    flag_length=len(flag_segment),
                    pole_start=df.index[swing_highs[i]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    pole_end=df.index[swing_highs[j]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    flag_start=df.index[flag_start] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    flag_end=df.index[flag_end] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    breakout_price=breakout_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    confidence=confidence,
                    strength=strength,
                    volume_confirmation=volume_confirm
                ))
        
        return patterns
    
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
    
    def _calculate_confidence(self, pole_segment: pd.DataFrame,
                            flag_segment: pd.DataFrame) -> float:
        """
        Calculate flag pattern confidence.
        
        Args:
            pole_segment: Pole segment data
            flag_segment: Flag segment data
            
        Returns:
            Confidence score (0-1)
        """
        # Pole strength
        pole_range = (pole_segment['high'].max() - pole_segment['low'].min()) / pole_segment['close'].iloc[0]
        pole_strength = min(pole_range * 5, 1.0)
        
        # Flag consolidation
        flag_high = flag_segment['high'].max()
        flag_low = flag_segment['low'].min()
        flag_range = (flag_high - flag_low) / flag_low
        flag_consolidation = 1 - min(flag_range * 5, 0.8)
        
        # Volume pattern
        pole_volume = pole_segment['volume'].mean()
        flag_volume = flag_segment['volume'].mean()
        volume_pattern = min(flag_volume / pole_volume, 1.0) if pole_volume > 0 else 0.5
        
        # Flag symmetry
        flag_mid = (flag_high + flag_low) / 2
        flag_symmetry = 1 - abs(flag_segment['close'].iloc[-1] - flag_mid) / (flag_high - flag_low) if (flag_high - flag_low) > 0 else 0.5
        
        # Weighted combination
        confidence = (pole_strength * 0.3 + flag_consolidation * 0.3 +
                     volume_pattern * 0.2 + flag_symmetry * 0.2)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _calculate_strength(self, pole_segment: pd.DataFrame,
                          flag_segment: pd.DataFrame) -> float:
        """
        Calculate flag pattern strength.
        
        Args:
            pole_segment: Pole segment data
            flag_segment: Flag segment data
            
        Returns:
            Strength score (0-1)
        """
        # Pole slope
        pole_slope, pole_intercept = MathUtils.linear_regression(
            np.arange(len(pole_segment)),
            pole_segment['close'].values
        )
        pole_strength = min(abs(pole_slope) * 10, 1.0)
        
        # Flag duration
        flag_duration = len(flag_segment)
        flag_duration_score = min(flag_duration / self.max_flag_length, 1.0)
        
        # Price movement
        price_change = (pole_segment['close'].iloc[-1] - pole_segment['close'].iloc[0]) / pole_segment['close'].iloc[0]
        price_strength = min(abs(price_change) * 5, 1.0)
        
        # Combined strength
        strength = (pole_strength * 0.4 + flag_duration_score * 0.3 + price_strength * 0.3)
        
        return min(max(strength, 0.0), 1.0)
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[FlagPattern]) -> List[FlagSignal]:
        """
        Generate trading signals from flag patterns.
        
        Args:
            df: OHLCV data
            patterns: List of flag patterns
            
        Returns:
            List of FlagSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if breakout has occurred
        if latest_pattern.pattern_type == 'bullish':
            if current_price > latest_pattern.breakout_price * (1 + self.breakout_threshold):
                signal_type = 'buy'
                reason = "Bullish flag breakout detected"
            else:
                return None
        else:
            if current_price < latest_pattern.breakout_price * (1 - self.breakout_threshold):
                signal_type = 'sell'
                reason = "Bearish flag breakdown detected"
            else:
                return None
        
        signal = FlagSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=latest_pattern.confidence,
            price=current_price,
            target=latest_pattern.target_price,
            stop_loss=latest_pattern.stop_loss,
            reason=reason,
            pattern=latest_pattern,
            indicators={
                'pole_length': latest_pattern.pole_length,
                'flag_length': latest_pattern.flag_length,
                'volume_confirmation': latest_pattern.volume_confirmation,
                'strength': latest_pattern.strength
            }
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[FlagPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of flag patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No flag patterns detected"
        
        latest = patterns[-1]
        
        direction_names = {
            'bullish': 'Bullish flag',
            'bearish': 'Bearish flag'
        }
        
        strength = latest.strength
        strength_names = {
            'weak': 'Weak',
            'moderate': 'Moderate',
            'strong': 'Strong',
            'very_strong': 'Very Strong'
        }
        
        strength_level = 'moderate'
        if strength > 0.75:
            strength_level = 'very_strong'
        elif strength > 0.50:
            strength_level = 'strong'
        elif strength > 0.25:
            strength_level = 'moderate'
        else:
            strength_level = 'weak'
        
        return f"{strength_names[strength_level]} {direction_names[latest.pattern_type]}"


def create_flag_model(config: Optional[Dict[str, Any]] = None) -> FlagModel:
    """
    Create a flag model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FlagModel instance
    """
    return FlagModel(config)


__all__ = [
    'FlagPattern',
    'FlagSignal',
    'FlagModel',
    'create_flag_model'
]
