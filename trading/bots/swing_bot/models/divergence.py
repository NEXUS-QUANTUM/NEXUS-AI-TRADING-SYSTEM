"""
Swing Bot Divergence Model
============================

This module provides divergence analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class DivergencePattern:
    """Divergence pattern data structure."""
    pattern_type: str  # 'bullish', 'bearish', 'hidden_bullish', 'hidden_bearish'
    indicator: str  # 'rsi', 'macd', 'stochastic', 'price'
    start_price: float
    end_price: float
    start_indicator: float
    end_indicator: float
    strength: float
    confidence: float
    timestamp: datetime


@dataclass
class DivergenceSignal:
    """Divergence trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: DivergencePattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class DivergenceModel:
    """
    Divergence analysis model for market reversals.
    
    Identifies and analyzes divergence patterns:
    - Bullish divergence
    - Bearish divergence
    - Hidden divergences
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the divergence model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.min_swing_size = self.config.get('min_swing_size', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.patterns_history: List[DivergencePattern] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze divergence patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Divergence analysis results
        """
        if len(df) < self.lookback_period:
            return {'patterns': [], 'signals': []}
        
        # Calculate indicators
        rsi = self._calculate_rsi(df)
        macd = self._calculate_macd(df)
        stochastic = self._calculate_stochastic(df)
        
        # Detect patterns
        patterns = self._detect_patterns(df, rsi, macd, stochastic)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _calculate_rsi(self, df: pd.DataFrame) -> np.ndarray:
        """
        Calculate RSI.
        
        Args:
            df: OHLCV data
            
        Returns:
            RSI values
        """
        close = df['close'].values
        
        if len(close) < 15:
            return np.zeros(len(close))
        
        returns = np.diff(close)
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        rsi = np.zeros(len(close))
        avg_gain = np.mean(gains[:14])
        avg_loss = np.mean(losses[:14])
        
        for i in range(14, len(close)):
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))
            
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        
        return rsi
    
    def _calculate_macd(self, df: pd.DataFrame) -> np.ndarray:
        """
        Calculate MACD.
        
        Args:
            df: OHLCV data
            
        Returns:
            MACD values
        """
        close = df['close'].values
        
        if len(close) < 26:
            return np.zeros(len(close))
        
        # Calculate EMAs
        ema12 = self._calculate_ema(close, 12)
        ema26 = self._calculate_ema(close, 26)
        
        if len(ema12) == 0 or len(ema26) == 0:
            return np.zeros(len(close))
        
        macd = ema12 - ema26
        
        return macd
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate EMA.
        
        Args:
            data: Input data
            period: EMA period
            
        Returns:
            EMA values
        """
        if len(data) < period:
            return np.array([])
        
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_stochastic(self, df: pd.DataFrame) -> np.ndarray:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            df: OHLCV data
            
        Returns:
            Stochastic values
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        if len(close) < 14:
            return np.zeros(len(close))
        
        stochastic = np.zeros(len(close))
        
        for i in range(14, len(close)):
            highest_high = np.max(high[i-14:i+1])
            lowest_low = np.min(low[i-14:i+1])
            
            if highest_high == lowest_low:
                stochastic[i] = 50.0
            else:
                stochastic[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
        
        return stochastic
    
    def _detect_patterns(self, df: pd.DataFrame, rsi: np.ndarray,
                        macd: np.ndarray, stochastic: np.ndarray) -> List[DivergencePattern]:
        """
        Detect divergence patterns.
        
        Args:
            df: OHLCV data
            rsi: RSI values
            macd: MACD values
            stochastic: Stochastic values
            
        Returns:
            List of DivergencePattern objects
        """
        patterns = []
        close = df['close'].values
        
        # Find swing points
        price_highs = self._find_swing_points(close, 'high')
        price_lows = self._find_swing_points(close, 'low')
        rsi_highs = self._find_swing_points(rsi, 'high')
        rsi_lows = self._find_swing_points(rsi, 'low')
        
        # Check for price-indicator divergences
        # Bearish divergence (price makes higher high, indicator makes lower high)
        if len(price_highs) >= 2 and len(rsi_highs) >= 2:
            price_high1 = price_highs[-2]
            price_high2 = price_highs[-1]
            rsi_high1 = rsi_highs[-2]
            rsi_high2 = rsi_highs[-1]
            
            if (price_high2['price'] > price_high1['price'] and 
                rsi_high2['price'] < rsi_high1['price']):
                patterns.append(DivergencePattern(
                    pattern_type='bearish',
                    indicator='rsi',
                    start_price=price_high1['price'],
                    end_price=price_high2['price'],
                    start_indicator=rsi_high1['price'],
                    end_indicator=rsi_high2['price'],
                    strength=self._calculate_strength(price_high1, price_high2, rsi_high1, rsi_high2),
                    confidence=0.7,
                    timestamp=datetime.now()
                ))
        
        # Bullish divergence (price makes lower low, indicator makes higher low)
        if len(price_lows) >= 2 and len(rsi_lows) >= 2:
            price_low1 = price_lows[-2]
            price_low2 = price_lows[-1]
            rsi_low1 = rsi_lows[-2]
            rsi_low2 = rsi_lows[-1]
            
            if (price_low2['price'] < price_low1['price'] and 
                rsi_low2['price'] > rsi_low1['price']):
                patterns.append(DivergencePattern(
                    pattern_type='bullish',
                    indicator='rsi',
                    start_price=price_low1['price'],
                    end_price=price_low2['price'],
                    start_indicator=rsi_low1['price'],
                    end_indicator=rsi_low2['price'],
                    strength=self._calculate_strength(price_low1, price_low2, rsi_low1, rsi_low2),
                    confidence=0.7,
                    timestamp=datetime.now()
                ))
        
        # Check MACD divergence
        macd_highs = self._find_swing_points(macd, 'high')
        macd_lows = self._find_swing_points(macd, 'low')
        
        # Bearish MACD divergence
        if len(price_highs) >= 2 and len(macd_highs) >= 2:
            price_high1 = price_highs[-2]
            price_high2 = price_highs[-1]
            macd_high1 = macd_highs[-2]
            macd_high2 = macd_highs[-1]
            
            if (price_high2['price'] > price_high1['price'] and 
                macd_high2['price'] < macd_high1['price']):
                patterns.append(DivergencePattern(
                    pattern_type='bearish',
                    indicator='macd',
                    start_price=price_high1['price'],
                    end_price=price_high2['price'],
                    start_indicator=macd_high1['price'],
                    end_indicator=macd_high2['price'],
                    strength=self._calculate_strength(price_high1, price_high2, macd_high1, macd_high2),
                    confidence=0.7,
                    timestamp=datetime.now()
                ))
        
        # Bullish MACD divergence
        if len(price_lows) >= 2 and len(macd_lows) >= 2:
            price_low1 = price_lows[-2]
            price_low2 = price_lows[-1]
            macd_low1 = macd_lows[-2]
            macd_low2 = macd_lows[-1]
            
            if (price_low2['price'] < price_low1['price'] and 
                macd_low2['price'] > macd_low1['price']):
                patterns.append(DivergencePattern(
                    pattern_type='bullish',
                    indicator='macd',
                    start_price=price_low1['price'],
                    end_price=price_low2['price'],
                    start_indicator=macd_low1['price'],
                    end_indicator=macd_low2['price'],
                    strength=self._calculate_strength(price_low1, price_low2, macd_low1, macd_low2),
                    confidence=0.7,
                    timestamp=datetime.now()
                ))
        
        self.patterns_history.extend(patterns)
        
        return patterns
    
    def _find_swing_points(self, data: np.ndarray, point_type: str) -> List[Dict[str, Any]]:
        """
        Find swing high or low points.
        
        Args:
            data: Data array
            point_type: 'high' or 'low'
            
        Returns:
            List of swing points
        """
        swings = []
        lookback = 5
        
        for i in range(lookback, len(data) - lookback):
            if point_type == 'high':
                is_swing = True
                for j in range(lookback):
                    if data[i] <= data[i - j - 1] or data[i] <= data[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': data[i]})
            else:
                is_swing = True
                for j in range(lookback):
                    if data[i] >= data[i - j - 1] or data[i] >= data[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': data[i]})
        
        return swings
    
    def _calculate_strength(self, point1: Dict[str, Any], point2: Dict[str, Any],
                          ind1: Dict[str, Any], ind2: Dict[str, Any]) -> float:
        """
        Calculate divergence strength.
        
        Args:
            point1: First price point
            point2: Second price point
            ind1: First indicator point
            ind2: Second indicator point
            
        Returns:
            Strength score (0-1)
        """
        price_diff = abs(point2['price'] - point1['price']) / point1['price']
        ind_diff = abs(ind2['price'] - ind1['price']) / (abs(ind1['price']) + 1e-10)
        
        strength = min((price_diff + ind_diff) * 5, 1.0)
        
        return strength
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[DivergencePattern]) -> List[DivergenceSignal]:
        """
        Generate trading signals from divergence patterns.
        
        Args:
            df: OHLCV data
            patterns: List of divergence patterns
            
        Returns:
            List of DivergenceSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal
        if latest_pattern.pattern_type == 'bullish':
            signal_type = 'buy'
            reason = f"Bullish {latest_pattern.indicator} divergence detected"
            confidence = latest_pattern.confidence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif latest_pattern.pattern_type == 'bearish':
            signal_type = 'sell'
            reason = f"Bearish {latest_pattern.indicator} divergence detected"
            confidence = latest_pattern.confidence
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(DivergenceSignal(
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
                'indicator': latest_pattern.indicator,
                'start_indicator': latest_pattern.start_indicator,
                'end_indicator': latest_pattern.end_indicator,
                'strength': latest_pattern.strength
            }
        ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[DivergencePattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of divergence patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No divergence patterns detected"
        
        latest = patterns[-1]
        
        if latest.pattern_type == 'bullish':
            return f"Bullish divergence detected on {latest.indicator}"
        else:
            return f"Bearish divergence detected on {latest.indicator}"
    
    def get_patterns_summary(self) -> Dict[str, Any]:
        """
        Get divergence patterns summary.
        
        Returns:
            Patterns summary
        """
        if not self.patterns_history:
            return {'status': 'no_patterns'}
        
        latest = self.patterns_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_pattern': latest,
            'total_patterns': len(self.patterns_history),
            'bullish_patterns': len([p for p in self.patterns_history if p.pattern_type == 'bullish']),
            'bearish_patterns': len([p for p in self.patterns_history if p.pattern_type == 'bearish']),
            'rsi_patterns': len([p for p in self.patterns_history if p.indicator == 'rsi']),
            'macd_patterns': len([p for p in self.patterns_history if p.indicator == 'macd']),
            'average_confidence': np.mean([p.confidence for p in self.patterns_history]),
            'average_strength': np.mean([p.strength for p in self.patterns_history])
        }


def create_divergence_model(config: Optional[Dict[str, Any]] = None) -> DivergenceModel:
    """
    Create a divergence model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DivergenceModel instance
    """
    return DivergenceModel(config)


__all__ = [
    'DivergencePattern',
    'DivergenceSignal',
    'DivergenceModel',
    'create_divergence_model'
]
