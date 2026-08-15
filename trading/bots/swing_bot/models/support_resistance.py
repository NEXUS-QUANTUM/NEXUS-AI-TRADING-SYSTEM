"""
Swing Bot Support & Resistance Model
======================================

This module provides support and resistance analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from trading.bots.swing_bot.utils.validators import Validator


@dataclass
class SupportResistanceLevel:
    """Support/resistance level data structure."""
    level_type: str  # 'support', 'resistance'
    price: float
    strength: float
    touch_count: int
    volume: float
    start_date: datetime
    end_date: datetime
    confidence: float
    zones: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class SupportResistanceSignal:
    """Support/resistance trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'bounce_buy', 'breakout_buy', 'rejection_sell', 'breakdown_sell'
    level_type: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class SupportResistanceModel:
    """
    Support and resistance analysis model.
    
    Identifies and analyzes support and resistance levels.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the support/resistance model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.min_touches = self.config.get('min_touches', 2)
        self.level_tolerance = self.config.get('level_tolerance', 0.005)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze support and resistance levels.
        
        Args:
            df: OHLCV data
            
        Returns:
            Support/resistance analysis results
        """
        if len(df) < self.lookback_period:
            return {'levels': [], 'signals': []}
        
        # Detect levels
        levels = self._detect_levels(df)
        
        # Generate signals
        signals = self._generate_signals(df, levels)
        
        return {
            'levels': levels,
            'signals': signals,
            'current_support': self._get_nearest_level(levels, 'support', df['close'].iloc[-1]),
            'current_resistance': self._get_nearest_level(levels, 'resistance', df['close'].iloc[-1]),
            'market_character': self._get_market_character(df, levels)
        }
    
    def _detect_levels(self, df: pd.DataFrame) -> List[SupportResistanceLevel]:
        """
        Detect support and resistance levels.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of SupportResistanceLevel objects
        """
        levels = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Find pivot points
        pivots = self._find_pivots(df)
        
        # Group pivot points into levels
        support_levels = self._group_pivots(pivots['lows'], 'support', df)
        resistance_levels = self._group_pivots(pivots['highs'], 'resistance', df)
        
        levels.extend(support_levels)
        levels.extend(resistance_levels)
        
        return levels
    
    def _find_pivots(self, df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find pivot highs and lows.
        
        Args:
            df: OHLCV data
            
        Returns:
            Dictionary of pivot highs and lows
        """
        high = df['high'].values
        low = df['low'].values
        lookback = self.config.get('pivot_lookback', 5)
        
        pivots = {'highs': [], 'lows': []}
        
        for i in range(lookback, len(df) - lookback):
            # Check for pivot high
            is_high = True
            for j in range(lookback):
                if high[i] <= high[i - j - 1] or high[i] <= high[i + j + 1]:
                    is_high = False
                    break
            if is_high:
                pivots['highs'].append({
                    'index': i,
                    'price': high[i],
                    'volume': df['volume'].iloc[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
            
            # Check for pivot low
            is_low = True
            for j in range(lookback):
                if low[i] >= low[i - j - 1] or low[i] >= low[i + j + 1]:
                    is_low = False
                    break
            if is_low:
                pivots['lows'].append({
                    'index': i,
                    'price': low[i],
                    'volume': df['volume'].iloc[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
        
        return pivots
    
    def _group_pivots(self, pivots: List[Dict[str, Any]], level_type: str,
                     df: pd.DataFrame) -> List[SupportResistanceLevel]:
        """
        Group pivot points into levels.
        
        Args:
            pivots: List of pivot points
            level_type: 'support' or 'resistance'
            df: OHLCV data
            
        Returns:
            List of SupportResistanceLevel objects
        """
        if not pivots:
            return []
        
        # Sort by price
        sorted_pivots = sorted(pivots, key=lambda x: x['price'])
        
        levels = []
        current_group = [sorted_pivots[0]]
        
        for i in range(1, len(sorted_pivots)):
            pivot = sorted_pivots[i]
            last = current_group[-1]
            
            # Check if within tolerance
            if abs(pivot['price'] - last['price']) / last['price'] <= self.level_tolerance:
                current_group.append(pivot)
            else:
                # Create level from current group
                level = self._create_level(current_group, level_type, df)
                if level:
                    levels.append(level)
                current_group = [pivot]
        
        # Create level from last group
        if current_group:
            level = self._create_level(current_group, level_type, df)
            if level:
                levels.append(level)
        
        # Sort by strength
        levels.sort(key=lambda x: x.strength, reverse=True)
        
        return levels
    
    def _create_level(self, group: List[Dict[str, Any]], level_type: str,
                     df: pd.DataFrame) -> Optional[SupportResistanceLevel]:
        """
        Create a support/resistance level from a group of pivots.
        
        Args:
            group: List of pivot points
            level_type: 'support' or 'resistance'
            df: OHLCV data
            
        Returns:
            SupportResistanceLevel or None
        """
        if len(group) < self.min_touches:
            return None
        
        # Calculate level price (weighted average)
        total_volume = sum(p['volume'] for p in group)
        if total_volume == 0:
            price = np.mean([p['price'] for p in group])
        else:
            price = sum(p['price'] * p['volume'] for p in group) / total_volume
        
        # Calculate strength
        strength = self._calculate_strength(group, df, price, level_type)
        
        # Calculate confidence
        confidence = self._calculate_confidence(group, df, price, level_type)
        
        # Calculate zones
        zones = self._calculate_zones(price, df, level_type)
        
        return SupportResistanceLevel(
            level_type=level_type,
            price=price,
            strength=strength,
            touch_count=len(group),
            volume=total_volume,
            start_date=group[0]['timestamp'],
            end_date=group[-1]['timestamp'],
            confidence=confidence,
            zones=zones
        )
    
    def _calculate_strength(self, group: List[Dict[str, Any]], df: pd.DataFrame,
                           price: float, level_type: str) -> float:
        """
        Calculate level strength.
        
        Args:
            group: Group of pivot points
            df: OHLCV data
            price: Level price
            level_type: 'support' or 'resistance'
            
        Returns:
            Strength score (0-1)
        """
        # Touch count
        touch_score = min(len(group) / 5, 1.0)
        
        # Volume at level
        total_volume = sum(p['volume'] for p in group)
        avg_volume = np.mean(df['volume'].values)
        volume_score = min(total_volume / (avg_volume * len(group) * 2), 1.0) if avg_volume > 0 else 0
        
        # Time duration
        duration = len(df)
        if group:
            start_idx = group[0]['index']
            duration_score = min((duration - start_idx) / 50, 1.0)
        else:
            duration_score = 0
        
        # Price rejection (for resistance) or support (for support)
        close = df['close'].values
        rejection_count = 0
        for i in range(len(close)):
            if level_type == 'resistance' and close[i] < price * (1 + self.level_tolerance):
                rejection_count += 1
            elif level_type == 'support' and close[i] > price * (1 - self.level_tolerance):
                rejection_count += 1
        
        rejection_score = min(rejection_count / 20, 1.0)
        
        # Weighted average
        strength = (touch_score * 0.3 + volume_score * 0.3 +
                   duration_score * 0.2 + rejection_score * 0.2)
        
        return min(max(strength, 0.0), 1.0)
    
    def _calculate_confidence(self, group: List[Dict[str, Any]], df: pd.DataFrame,
                             price: float, level_type: str) -> float:
        """
        Calculate level confidence.
        
        Args:
            group: Group of pivot points
            df: OHLCV data
            price: Level price
            level_type: 'support' or 'resistance'
            
        Returns:
            Confidence score (0-1)
        """
        # Number of touches
        touch_confidence = min(len(group) / 3, 1.0)
        
        # Price consistency
        prices = [p['price'] for p in group]
        price_std = np.std(prices)
        price_mean = np.mean(prices)
        consistency = 1 - min(price_std / price_mean * 10, 1.0) if price_mean > 0 else 0
        
        # Volume confirmation
        total_volume = sum(p['volume'] for p in group)
        avg_volume = np.mean(df['volume'].values)
        volume_confidence = min(total_volume / (avg_volume * len(group)), 1.0) if avg_volume > 0 else 0
        
        # Combined confidence
        confidence = (touch_confidence * 0.4 + consistency * 0.3 + volume_confidence * 0.3)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _calculate_zones(self, price: float, df: pd.DataFrame,
                        level_type: str) -> List[Dict[str, float]]:
        """
        Calculate support/resistance zones.
        
        Args:
            price: Level price
            df: OHLCV data
            level_type: 'support' or 'resistance'
            
        Returns:
            List of zone dictionaries
        """
        zones = []
        
        # Calculate ATR for zone width
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        if len(close) < 14:
            return zones
        
        # Calculate ATR
        atr = self._calculate_atr(high, low, close, 14)
        zone_width = atr * 0.5
        
        # Create zones
        if level_type == 'support':
            zones.append({
                'low': price - zone_width * 0.5,
                'high': price + zone_width * 0.5,
                'type': 'inner'
            })
            zones.append({
                'low': price - zone_width,
                'high': price + zone_width,
                'type': 'outer'
            })
        else:  # resistance
            zones.append({
                'low': price - zone_width * 0.5,
                'high': price + zone_width * 0.5,
                'type': 'inner'
            })
            zones.append({
                'low': price - zone_width,
                'high': price + zone_width,
                'type': 'outer'
            })
        
        return zones
    
    def _calculate_atr(self, high: np.ndarray, low: np.ndarray,
                      close: np.ndarray, period: int) -> float:
        """
        Calculate Average True Range.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: Period
            
        Returns:
            ATR value
        """
        if len(close) < period + 1:
            return 0.0
        
        true_range = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            true_range.append(tr)
        
        return np.mean(true_range[-period:])
    
    def _get_nearest_level(self, levels: List[SupportResistanceLevel],
                          level_type: str, current_price: float) -> Optional[SupportResistanceLevel]:
        """
        Get the nearest level of a specific type.
        
        Args:
            levels: List of levels
            level_type: 'support' or 'resistance'
            current_price: Current price
            
        Returns:
            Nearest level or None
        """
        filtered_levels = [l for l in levels if l.level_type == level_type]
        if not filtered_levels:
            return None
        
        nearest = min(filtered_levels, key=lambda l: abs(l.price - current_price))
        return nearest
    
    def _generate_signals(self, df: pd.DataFrame,
                         levels: List[SupportResistanceLevel]) -> List[SupportResistanceSignal]:
        """
        Generate trading signals from support/resistance levels.
        
        Args:
            df: OHLCV data
            levels: List of levels
            
        Returns:
            List of SupportResistanceSignal objects
        """
        signals = []
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Get support and resistance levels
        support = self._get_nearest_level(levels, 'support', current_price)
        resistance = self._get_nearest_level(levels, 'resistance', current_price)
        
        # Check for support bounce
        if support and current_price <= support.price * (1 + self.level_tolerance):
            signal = self._generate_bounce_signal(df, support, 'support')
            if signal:
                signals.append(signal)
        
        # Check for resistance rejection
        if resistance and current_price >= resistance.price * (1 - self.level_tolerance):
            signal = self._generate_rejection_signal(df, resistance, 'resistance')
            if signal:
                signals.append(signal)
        
        # Check for support breakdown
        if support and current_price < support.price * (1 - self.level_tolerance):
            signal = self._generate_breakdown_signal(df, support)
            if signal:
                signals.append(signal)
        
        # Check for resistance breakout
        if resistance and current_price > resistance.price * (1 + self.level_tolerance):
            signal = self._generate_breakout_signal(df, resistance)
            if signal:
                signals.append(signal)
        
        return signals
    
    def _generate_bounce_signal(self, df: pd.DataFrame,
                               level: SupportResistanceLevel,
                               level_type: str) -> Optional[SupportResistanceSignal]:
        """
        Generate bounce signal from support.
        
        Args:
            df: OHLCV data
            level: Support level
            level_type: 'support'
            
        Returns:
            SupportResistanceSignal or None
        """
        if level.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        
        return SupportResistanceSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type='bounce_buy',
            level_type=level_type,
            confidence=level.confidence,
            price=current_price,
            target=level.price * 1.02,
            stop_loss=level.price * 0.98,
            reason=f"Bounce from support at {level.price:.2f}",
            indicators={
                'strength': level.strength,
                'touch_count': level.touch_count,
                'zones': level.zones
            }
        )
    
    def _generate_rejection_signal(self, df: pd.DataFrame,
                                  level: SupportResistanceLevel,
                                  level_type: str) -> Optional[SupportResistanceSignal]:
        """
        Generate rejection signal from resistance.
        
        Args:
            df: OHLCV data
            level: Resistance level
            level_type: 'resistance'
            
        Returns:
            SupportResistanceSignal or None
        """
        if level.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        
        return SupportResistanceSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type='rejection_sell',
            level_type=level_type,
            confidence=level.confidence,
            price=current_price,
            target=level.price * 0.98,
            stop_loss=level.price * 1.02,
            reason=f"Rejection from resistance at {level.price:.2f}",
            indicators={
                'strength': level.strength,
                'touch_count': level.touch_count,
                'zones': level.zones
            }
        )
    
    def _generate_breakdown_signal(self, df: pd.DataFrame,
                                  level: SupportResistanceLevel) -> Optional[SupportResistanceSignal]:
        """
        Generate breakdown signal below support.
        
        Args:
            df: OHLCV data
            level: Support level
            
        Returns:
            SupportResistanceSignal or None
        """
        if level.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        
        return SupportResistanceSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type='breakdown_sell',
            level_type='support',
            confidence=level.confidence,
            price=current_price,
            target=level.price * 0.98,
            stop_loss=level.price * 1.02,
            reason=f"Breakdown below support at {level.price:.2f}",
            indicators={
                'strength': level.strength,
                'touch_count': level.touch_count,
                'zones': level.zones
            }
        )
    
    def _generate_breakout_signal(self, df: pd.DataFrame,
                                 level: SupportResistanceLevel) -> Optional[SupportResistanceSignal]:
        """
        Generate breakout signal above resistance.
        
        Args:
            df: OHLCV data
            level: Resistance level
            
        Returns:
            SupportResistanceSignal or None
        """
        if level.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        
        return SupportResistanceSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type='breakout_buy',
            level_type='resistance',
            confidence=level.confidence,
            price=current_price,
            target=level.price * 1.02,
            stop_loss=level.price * 0.98,
            reason=f"Breakout above resistance at {level.price:.2f}",
            indicators={
                'strength': level.strength,
                'touch_count': level.touch_count,
                'zones': level.zones
            }
        )
    
    def _get_market_character(self, df: pd.DataFrame,
                             levels: List[SupportResistanceLevel]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            levels: List of levels
            
        Returns:
            Market character description
        """
        if not levels:
            return "No significant support/resistance levels"
        
        current_price = df['close'].iloc[-1]
        support = self._get_nearest_level(levels, 'support', current_price)
        resistance = self._get_nearest_level(levels, 'resistance', current_price)
        
        if support and resistance:
            range_width = (resistance.price - support.price) / support.price
            if range_width < 0.05:
                return "Tight range (consolidation)"
            elif range_width < 0.10:
                return "Moderate range"
            else:
                return "Wide range"
        elif support:
            return "Support level identified"
        elif resistance:
            return "Resistance level identified"
        else:
            return "No significant levels"
    
    def get_level_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get support/resistance statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Level statistics
        """
        analysis = self.analyze(df)
        levels = analysis['levels']
        
        if not levels:
            return {'total_levels': 0}
        
        stats = {
            'total_levels': len(levels),
            'support_levels': len([l for l in levels if l.level_type == 'support']),
            'resistance_levels': len([l for l in levels if l.level_type == 'resistance']),
            'avg_strength': np.mean([l.strength for l in levels]),
            'avg_confidence': np.mean([l.confidence for l in levels]),
            'avg_touches': np.mean([l.touch_count for l in levels]),
            'strongest_level': max(levels, key=lambda l: l.strength),
            'nearest_support': self._get_nearest_level(levels, 'support', df['close'].iloc[-1]),
            'nearest_resistance': self._get_nearest_level(levels, 'resistance', df['close'].iloc[-1])
        }
        
        return stats


def create_support_resistance_model(config: Optional[Dict[str, Any]] = None) -> SupportResistanceModel:
    """
    Create a support/resistance model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SupportResistanceModel instance
    """
    return SupportResistanceModel(config)


__all__ = [
    'SupportResistanceLevel',
    'SupportResistanceSignal',
    'SupportResistanceModel',
    'create_support_resistance_model'
]
