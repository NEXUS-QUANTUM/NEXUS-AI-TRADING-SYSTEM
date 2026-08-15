"""
Swing Bot Elliott Wave Model
==============================

This module provides Elliott Wave analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ElliottWave:
    """Elliott Wave data structure."""
    wave_number: int
    wave_type: str  # 'impulse', 'corrective'
    direction: str  # 'up', 'down'
    start_price: float
    end_price: float
    fibonacci_levels: Dict[str, float]
    confidence: float
    timestamp: datetime


@dataclass
class WaveSignal:
    """Elliott Wave trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    wave: ElliottWave
    indicators: Dict[str, Any] = field(default_factory=dict)


class ElliottWaveModel:
    """
    Elliott Wave analysis model for market cycles.
    
    Implements Elliott Wave principle for pattern recognition.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Elliott Wave model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 200)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.wave_history: List[ElliottWave] = []
        self.fibonacci_levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Elliott Wave patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Elliott Wave analysis results
        """
        if len(df) < self.lookback_period:
            return {'waves': [], 'signals': []}
        
        # Detect waves
        waves = self._detect_waves(df)
        
        # Generate signals
        signals = self._generate_signals(df, waves)
        
        return {
            'waves': waves,
            'signals': signals,
            'current_wave': waves[-1] if waves else None,
            'market_character': self._get_market_character(df, waves)
        }
    
    def _detect_waves(self, df: pd.DataFrame) -> List[ElliottWave]:
        """
        Detect Elliott Waves.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ElliottWave objects
        """
        waves = []
        close = df['close'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(close, 'high')
        swing_lows = self._find_swing_points(close, 'low')
        
        # Identify impulse waves (5-wave pattern)
        if len(swing_highs) >= 3 and len(swing_lows) >= 3:
            impulse_waves = self._identify_impulse_waves(swing_highs, swing_lows, close)
            waves.extend(impulse_waves)
        
        # Identify corrective waves (3-wave pattern)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            corrective_waves = self._identify_corrective_waves(swing_highs, swing_lows, close)
            waves.extend(corrective_waves)
        
        self.wave_history.extend(waves)
        
        return waves
    
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
        lookback = 10
        
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
    
    def _identify_impulse_waves(self, swing_highs: List[Dict[str, Any]],
                              swing_lows: List[Dict[str, Any]],
                              close: np.ndarray) -> List[ElliottWave]:
        """
        Identify impulse waves.
        
        Args:
            swing_highs: Swing highs
            swing_lows: Swing lows
            close: Close prices
            
        Returns:
            List of ElliottWave objects
        """
        waves = []
        
        # Check for 5-wave impulse pattern
        if len(swing_highs) >= 3 and len(swing_lows) >= 3:
            # Wave 1: Up
            if swing_highs[0]['price'] > swing_lows[0]['price']:
                wave1 = ElliottWave(
                    wave_number=1,
                    wave_type='impulse',
                    direction='up',
                    start_price=swing_lows[0]['price'],
                    end_price=swing_highs[0]['price'],
                    fibonacci_levels=self._calculate_fibonacci_levels(swing_lows[0]['price'], swing_highs[0]['price']),
                    confidence=0.7,
                    timestamp=datetime.now()
                )
                waves.append(wave1)
                
                # Wave 2: Down
                if swing_lows[1]['price'] < swing_highs[0]['price']:
                    wave2 = ElliottWave(
                        wave_number=2,
                        wave_type='corrective',
                        direction='down',
                        start_price=swing_highs[0]['price'],
                        end_price=swing_lows[1]['price'],
                        fibonacci_levels=self._calculate_fibonacci_levels(swing_highs[0]['price'], swing_lows[1]['price']),
                        confidence=0.6,
                        timestamp=datetime.now()
                    )
                    waves.append(wave2)
                    
                    # Wave 3: Up (should be strongest)
                    if swing_highs[1]['price'] > swing_highs[0]['price']:
                        wave3 = ElliottWave(
                            wave_number=3,
                            wave_type='impulse',
                            direction='up',
                            start_price=swing_lows[1]['price'],
                            end_price=swing_highs[1]['price'],
                            fibonacci_levels=self._calculate_fibonacci_levels(swing_lows[1]['price'], swing_highs[1]['price']),
                            confidence=0.8,
                            timestamp=datetime.now()
                        )
                        waves.append(wave3)
                        
                        # Wave 4: Down
                        if swing_lows[2]['price'] > swing_lows[1]['price']:
                            wave4 = ElliottWave(
                                wave_number=4,
                                wave_type='corrective',
                                direction='down',
                                start_price=swing_highs[1]['price'],
                                end_price=swing_lows[2]['price'],
                                fibonacci_levels=self._calculate_fibonacci_levels(swing_highs[1]['price'], swing_lows[2]['price']),
                                confidence=0.6,
                                timestamp=datetime.now()
                            )
                            waves.append(wave4)
                            
                            # Wave 5: Up
                            if swing_highs[2]['price'] > swing_highs[1]['price']:
                                wave5 = ElliottWave(
                                    wave_number=5,
                                    wave_type='impulse',
                                    direction='up',
                                    start_price=swing_lows[2]['price'],
                                    end_price=swing_highs[2]['price'],
                                    fibonacci_levels=self._calculate_fibonacci_levels(swing_lows[2]['price'], swing_highs[2]['price']),
                                    confidence=0.7,
                                    timestamp=datetime.now()
                                )
                                waves.append(wave5)
        
        return waves
    
    def _identify_corrective_waves(self, swing_highs: List[Dict[str, Any]],
                                 swing_lows: List[Dict[str, Any]],
                                 close: np.ndarray) -> List[ElliottWave]:
        """
        Identify corrective waves.
        
        Args:
            swing_highs: Swing highs
            swing_lows: Swing lows
            close: Close prices
            
        Returns:
            List of ElliottWave objects
        """
        waves = []
        
        # Check for 3-wave corrective pattern (A-B-C)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            # Wave A: Down
            if swing_lows[0]['price'] < swing_highs[0]['price']:
                wave_a = ElliottWave(
                    wave_number=0,  # Use 0 for corrective waves
                    wave_type='corrective',
                    direction='down',
                    start_price=swing_highs[0]['price'],
                    end_price=swing_lows[0]['price'],
                    fibonacci_levels=self._calculate_fibonacci_levels(swing_highs[0]['price'], swing_lows[0]['price']),
                    confidence=0.6,
                    timestamp=datetime.now()
                )
                waves.append(wave_a)
                
                # Wave B: Up
                if swing_highs[1]['price'] > swing_lows[0]['price']:
                    wave_b = ElliottWave(
                        wave_number=0,
                        wave_type='corrective',
                        direction='up',
                        start_price=swing_lows[0]['price'],
                        end_price=swing_highs[1]['price'],
                        fibonacci_levels=self._calculate_fibonacci_levels(swing_lows[0]['price'], swing_highs[1]['price']),
                        confidence=0.6,
                        timestamp=datetime.now()
                    )
                    waves.append(wave_b)
                    
                    # Wave C: Down (should reach at least wave A level)
                    if swing_lows[1]['price'] < swing_lows[0]['price']:
                        wave_c = ElliottWave(
                            wave_number=0,
                            wave_type='corrective',
                            direction='down',
                            start_price=swing_highs[1]['price'],
                            end_price=swing_lows[1]['price'],
                            fibonacci_levels=self._calculate_fibonacci_levels(swing_highs[1]['price'], swing_lows[1]['price']),
                            confidence=0.7,
                            timestamp=datetime.now()
                        )
                        waves.append(wave_c)
        
        return waves
    
    def _calculate_fibonacci_levels(self, start_price: float, end_price: float) -> Dict[str, float]:
        """
        Calculate Fibonacci levels.
        
        Args:
            start_price: Start price
            end_price: End price
            
        Returns:
            Dictionary of Fibonacci levels
        """
        price_range = end_price - start_price
        levels = {}
        
        for fib in self.fibonacci_levels:
            levels[f"{fib:.1%}"] = start_price + fib * price_range
        
        return levels
    
    def _generate_signals(self, df: pd.DataFrame,
                         waves: List[ElliottWave]) -> List[WaveSignal]:
        """
        Generate trading signals from Elliott Waves.
        
        Args:
            df: OHLCV data
            waves: List of ElliottWave objects
            
        Returns:
            List of WaveSignal objects
        """
        signals = []
        
        if not waves:
            return signals
        
        # Get current wave position
        current_wave = waves[-1]
        
        if current_wave.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on wave position
        if current_wave.wave_type == 'impulse' and current_wave.wave_number == 3:
            # Wave 3 is typically the strongest
            signal_type = 'buy'
            reason = f"Wave 3 impulse - strong upward movement"
            confidence = current_wave.confidence
            target = current_price * 1.05
            stop_loss = current_price * 0.97
            
        elif current_wave.wave_type == 'impulse' and current_wave.wave_number == 5:
            # Wave 5 - potential exhaustion
            signal_type = 'sell'
            reason = f"Wave 5 impulse - potential reversal"
            confidence = current_wave.confidence * 0.8
            target = current_price * 0.95
            stop_loss = current_price * 1.03
            
        elif current_wave.wave_type == 'corrective' and current_wave.wave_number == 0:
            # Corrective wave - look for reversal
            if current_wave.direction == 'down':
                signal_type = 'buy'
                reason = "Corrective wave - potential reversal"
                confidence = current_wave.confidence * 0.7
                target = current_price * 1.03
                stop_loss = current_price * 0.97
            else:
                signal_type = 'sell'
                reason = "Corrective wave - potential continuation"
                confidence = current_wave.confidence * 0.7
                target = current_price * 0.97
                stop_loss = current_price * 1.03
        else:
            return signals
        
        signals.append(WaveSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            wave=current_wave,
            indicators={
                'wave_number': current_wave.wave_number,
                'wave_type': current_wave.wave_type,
                'fibonacci_levels': current_wave.fibonacci_levels
            }
        ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            waves: List[ElliottWave]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            waves: List of ElliottWave objects
            
        Returns:
            Market character description
        """
        if not waves:
            return "No Elliott Wave pattern detected"
        
        current_wave = waves[-1]
        
        if current_wave.wave_type == 'impulse':
            return f"Impulse wave {current_wave.wave_number} - {current_wave.direction}"
        else:
            return f"Corrective wave - {current_wave.direction}"
    
    def get_wave_summary(self) -> Dict[str, Any]:
        """
        Get Elliott Wave summary.
        
        Returns:
            Wave summary
        """
        if not self.wave_history:
            return {'status': 'no_waves'}
        
        latest = self.wave_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_wave': latest,
            'total_waves': len(self.wave_history),
            'impulse_waves': len([w for w in self.wave_history if w.wave_type == 'impulse']),
            'corrective_waves': len([w for w in self.wave_history if w.wave_type == 'corrective']),
            'average_confidence': np.mean([w.confidence for w in self.wave_history]),
            'current_pattern': self._get_market_character(pd.DataFrame(), self.wave_history)
        }


def create_elliott_wave_model(config: Optional[Dict[str, Any]] = None) -> ElliottWaveModel:
    """
    Create an Elliott Wave model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ElliottWaveModel instance
    """
    return ElliottWaveModel(config)


__all__ = [
    'ElliottWave',
    'WaveSignal',
    'ElliottWaveModel',
    'create_elliott_wave_model'
]
