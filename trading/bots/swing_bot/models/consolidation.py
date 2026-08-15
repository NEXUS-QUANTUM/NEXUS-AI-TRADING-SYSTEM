"""
Swing Bot Consolidation Model
===============================

This module provides consolidation pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ConsolidationPattern:
    """Consolidation pattern data structure."""
    pattern_type: str  # 'range', 'triangle', 'flag', 'pennant'
    start_price: float
    end_price: float
    high_price: float
    low_price: float
    width: float
    duration: int
    strength: float
    confidence: float
    timestamp: datetime
    breakout_direction: Optional[str] = None


@dataclass
class ConsolidationSignal:
    """Consolidation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: ConsolidationPattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class ConsolidationModel:
    """
    Consolidation pattern analysis model.
    
    Identifies and analyzes consolidation patterns:
    - Range consolidation
    - Triangle consolidation
    - Flag consolidation
    - Pennant consolidation
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the consolidation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_duration = self.config.get('min_duration', 5)
        self.max_duration = self.config.get('max_duration', 30)
        self.width_threshold = self.config.get('width_threshold', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze consolidation patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Consolidation analysis results
        """
        if len(df) < self.min_duration:
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
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[ConsolidationPattern]:
        """
        Detect consolidation patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ConsolidationPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Find consolidation ranges
        for i in range(self.min_duration, len(df)):
            # Check each possible duration
            for duration in range(self.min_duration, min(self.max_duration + 1, i + 1)):
                segment = df.iloc[i - duration:i + 1]
                
                if len(segment) < self.min_duration:
                    continue
                
                # Check if it's a consolidation
                pattern = self._check_consolidation(segment)
                
                if pattern:
                    patterns.append(pattern)
        
        return patterns
    
    def _check_consolidation(self, segment: pd.DataFrame) -> Optional[ConsolidationPattern]:
        """
        Check if a segment is a consolidation pattern.
        
        Args:
            segment: Price segment
            
        Returns:
            ConsolidationPattern or None
        """
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        
        # Calculate range
        high_price = np.max(high)
        low_price = np.min(low)
        width = (high_price - low_price) / low_price
        
        # Check if range is within threshold
        if width > self.width_threshold * 2:
            return None
        
        # Check price movement
        price_change = (close[-1] - close[0]) / close[0]
        
        # Determine pattern type
        if width < 0.01:
            pattern_type = 'range'
        else:
            # Check for narrowing or expanding
            if len(segment) > 2:
                first_width = (high[0] - low[0]) / low[0]
                last_width = (high[-1] - low[-1]) / low[-1]
                
                if last_width < first_width * 0.8:
                    pattern_type = 'triangle'
                elif last_width > first_width * 1.2:
                    pattern_type = 'pennant'
                else:
                    pattern_type = 'flag'
            else:
                pattern_type = 'range'
        
        # Calculate strength
        strength = self._calculate_strength(segment, width)
        
        # Calculate confidence
        confidence = self._calculate_confidence(segment, pattern_type)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Determine breakout direction
        breakout_direction = None
        if abs(price_change) > 0.01:
            breakout_direction = 'up' if price_change > 0 else 'down'
        
        return ConsolidationPattern(
            pattern_type=pattern_type,
            start_price=close[0],
            end_price=close[-1],
            high_price=high_price,
            low_price=low_price,
            width=width,
            duration=len(segment),
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            breakout_direction=breakout_direction
        )
    
    def _calculate_strength(self, segment: pd.DataFrame, width: float) -> float:
        """
        Calculate consolidation strength.
        
        Args:
            segment: Price segment
            width: Width of consolidation
            
        Returns:
            Strength score (0-1)
        """
        high = segment['high'].values
        low = segment['low'].values
        volume = segment['volume'].values
        
        # Volume consistency
        volume_std = np.std(volume)
        volume_mean = np.mean(volume)
        volume_consistency = 1 - min(volume_std / (volume_mean + 1e-10), 1.0)
        
        # Range consistency
        range_std = np.std(high - low)
        range_mean = np.mean(high - low)
        range_consistency = 1 - min(range_std / (range_mean + 1e-10), 1.0)
        
        # Duration factor
        duration_score = min(len(segment) / 20, 1.0)
        
        # Combine
        strength = (volume_consistency * 0.3 +
                   range_consistency * 0.3 +
                   duration_score * 0.4)
        
        return max(0, min(1, strength))
    
    def _calculate_confidence(self, segment: pd.DataFrame, pattern_type: str) -> float:
        """
        Calculate consolidation confidence.
        
        Args:
            segment: Price segment
            pattern_type: Pattern type
            
        Returns:
            Confidence score (0-1)
        """
        close = segment['close'].values
        high = segment['high'].values
        low = segment['low'].values
        
        # Price stability
        price_std = np.std(close)
        price_mean = np.mean(close)
        stability = 1 - min(price_std / (price_mean + 1e-10), 1.0)
        
        # Pattern recognition
        if pattern_type == 'range':
            pattern_score = 0.8
        elif pattern_type == 'triangle':
            pattern_score = 0.7
        elif pattern_type == 'flag':
            pattern_score = 0.6
        else:  # pennant
            pattern_score = 0.5
        
        # Duration factor
        duration_score = min(len(segment) / 15, 1.0)
        
        # Combine
        confidence = (stability * 0.3 +
                     pattern_score * 0.3 +
                     duration_score * 0.4)
        
        return max(0, min(1, confidence))
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[ConsolidationPattern]) -> List[ConsolidationSignal]:
        """
        Generate trading signals from consolidation patterns.
        
        Args:
            df: OHLCV data
            patterns: List of consolidation patterns
            
        Returns:
            List of ConsolidationSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on pattern
        if latest_pattern.breakout_direction == 'up':
            signal_type = 'buy'
            reason = f"Breakout from {latest_pattern.pattern_type} consolidation"
            confidence = latest_pattern.confidence
            target = latest_pattern.high_price * 1.02
            stop_loss = latest_pattern.low_price * 0.98
            
        elif latest_pattern.breakout_direction == 'down':
            signal_type = 'sell'
            reason = f"Breakdown from {latest_pattern.pattern_type} consolidation"
            confidence = latest_pattern.confidence
            target = latest_pattern.low_price * 0.98
            stop_loss = latest_pattern.high_price * 1.02
            
        else:
            # No breakout yet
            if latest_pattern.width < 0.01:
                # Tight range - look for breakout
                if current_price > latest_pattern.high_price * 0.99:
                    signal_type = 'buy'
                    reason = "Potential breakout from tight range"
                    confidence = latest_pattern.confidence * 0.8
                    target = current_price * 1.02
                    stop_loss = current_price * 0.98
                elif current_price < latest_pattern.low_price * 1.01:
                    signal_type = 'sell'
                    reason = "Potential breakdown from tight range"
                    confidence = latest_pattern.confidence * 0.8
                    target = current_price * 0.98
                    stop_loss = current_price * 1.02
                else:
                    return signals
            else:
                return signals
        
        signals.append(ConsolidationSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            pattern=latest_pattern,
            indicators={
                'width': latest_pattern.width,
                'duration': latest_pattern.duration,
                'strength': latest_pattern.strength
            }
        ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[ConsolidationPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of consolidation patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No consolidation patterns detected"
        
        latest = patterns[-1]
        
        pattern_names = {
            'range': 'Range consolidation',
            'triangle': 'Triangle consolidation',
            'flag': 'Flag consolidation',
            'pennant': 'Pennant consolidation'
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
        
        return f"{strength_names[strength_level]} {pattern_names.get(latest.pattern_type, latest.pattern_type)}"


def create_consolidation_model(config: Optional[Dict[str, Any]] = None) -> ConsolidationModel:
    """
    Create a consolidation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ConsolidationModel instance
    """
    return ConsolidationModel(config)


__all__ = [
    'ConsolidationPattern',
    'ConsolidationSignal',
    'ConsolidationModel',
    'create_consolidation_model'
]
