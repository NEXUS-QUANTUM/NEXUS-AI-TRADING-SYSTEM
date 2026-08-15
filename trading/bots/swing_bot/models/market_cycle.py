"""
Swing Bot Market Cycle Model
==============================

This module provides market cycle analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class MarketCycle:
    """Market cycle data structure."""
    phase: str  # 'accumulation', 'markup', 'distribution', 'markdown'
    sub_phase: str  # 'early', 'mid', 'late'
    start_date: datetime
    end_date: datetime
    start_price: float
    end_price: float
    strength: float
    duration: int
    confidence: float


@dataclass
class CycleSignal:
    """Market cycle trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    cycle: MarketCycle
    indicators: Dict[str, Any] = field(default_factory=dict)


class MarketCycleModel:
    """
    Market cycle analysis model for trend identification.
    
    Implements market cycle detection and analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the market cycle model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 200)
        self.min_cycle_duration = self.config.get('min_cycle_duration', 20)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.cycle_history: List[MarketCycle] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze market cycles.
        
        Args:
            df: OHLCV data
            
        Returns:
            Market cycle analysis results
        """
        if len(df) < self.lookback_period:
            return {'cycle': None, 'signals': []}
        
        # Detect cycles
        cycle = self._detect_cycle(df)
        
        # Generate signals
        signals = self._generate_signals(df, cycle)
        
        return {
            'cycle': cycle,
            'signals': signals,
            'status': self._get_status(cycle),
            'market_character': self._get_market_character(df, cycle)
        }
    
    def _detect_cycle(self, df: pd.DataFrame) -> Optional[MarketCycle]:
        """
        Detect market cycle.
        
        Args:
            df: OHLCV data
            
        Returns:
            MarketCycle or None
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None
        
        # Identify cycle phases
        phases = self._identify_phases(swing_highs, swing_lows, df)
        
        if not phases:
            return None
        
        # Get current phase
        current_phase = phases[-1]
        start_date = df.index[current_phase['start_idx']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        end_date = df.index[current_phase['end_idx']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        
        # Calculate metrics
        strength = self._calculate_cycle_strength(df, current_phase)
        duration = current_phase['end_idx'] - current_phase['start_idx']
        confidence = self._calculate_cycle_confidence(df, current_phase)
        
        if confidence < self.confidence_threshold:
            return None
        
        return MarketCycle(
            phase=current_phase['phase'],
            sub_phase=current_phase['sub_phase'],
            start_date=start_date,
            end_date=end_date,
            start_price=close[current_phase['start_idx']],
            end_price=close[current_phase['end_idx']],
            strength=strength,
            duration=duration,
            confidence=confidence
        )
    
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
    
    def _identify_phases(self, swing_highs: List[Dict[str, Any]],
                        swing_lows: List[Dict[str, Any]],
                        df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Identify cycle phases.
        
        Args:
            swing_highs: Swing highs
            swing_lows: Swing lows
            df: OHLCV data
            
        Returns:
            List of phase dictionaries
        """
        phases = []
        close = df['close'].values
        
        # Combine swings in order
        all_swings = []
        i, j = 0, 0
        while i < len(swing_highs) and j < len(swing_lows):
            if swing_highs[i]['index'] < swing_lows[j]['index']:
                all_swings.append({'type': 'high', 'index': swing_highs[i]['index'], 
                                 'price': swing_highs[i]['price']})
                i += 1
            else:
                all_swings.append({'type': 'low', 'index': swing_lows[j]['index'],
                                 'price': swing_lows[j]['price']})
                j += 1
        
        # Identify phases
        for k in range(len(all_swings) - 3):
            swing1 = all_swings[k]
            swing2 = all_swings[k + 1]
            swing3 = all_swings[k + 2]
            
            # Check for phase patterns
            if swing1['type'] == 'low' and swing2['type'] == 'high' and swing3['type'] == 'low':
                # Accumulation or distribution
                if swing2['price'] > swing1['price'] and swing3['price'] > swing1['price']:
                    phase = 'accumulation'
                    sub_phase = 'early'
                elif swing2['price'] > swing1['price'] and swing3['price'] < swing2['price']:
                    phase = 'distribution'
                    sub_phase = 'mid'
                else:
                    phase = 'markdown'
                    sub_phase = 'late'
                
                phases.append({
                    'phase': phase,
                    'sub_phase': sub_phase,
                    'start_idx': swing1['index'],
                    'end_idx': swing3['index']
                })
            
            elif swing1['type'] == 'high' and swing2['type'] == 'low' and swing3['type'] == 'high':
                # Markup or markdown
                if swing2['price'] < swing1['price'] and swing3['price'] < swing1['price']:
                    phase = 'markdown'
                    sub_phase = 'early'
                elif swing2['price'] < swing1['price'] and swing3['price'] > swing2['price']:
                    phase = 'markup'
                    sub_phase = 'mid'
                else:
                    phase = 'accumulation'
                    sub_phase = 'late'
                
                phases.append({
                    'phase': phase,
                    'sub_phase': sub_phase,
                    'start_idx': swing1['index'],
                    'end_idx': swing3['index']
                })
        
        return phases
    
    def _calculate_cycle_strength(self, df: pd.DataFrame, phase: Dict[str, Any]) -> float:
        """
        Calculate cycle strength.
        
        Args:
            df: OHLCV data
            phase: Phase dictionary
            
        Returns:
            Strength score (0-1)
        """
        close = df['close'].values
        volume = df['volume'].values
        
        start = phase['start_idx']
        end = phase['end_idx']
        segment = close[start:end + 1]
        volume_segment = volume[start:end + 1]
        
        # Price movement
        price_change = (close[end] - close[start]) / close[start]
        price_strength = min(abs(price_change) * 5, 1.0)
        
        # Volume trend
        volume_ma = np.mean(volume_segment)
        volume_trend = (volume_segment[-1] - volume_segment[0]) / (volume_segment[0] + 1e-10)
        volume_strength = min(abs(volume_trend) * 2, 1.0)
        
        # Duration factor
        duration = end - start
        duration_score = min(duration / 50, 1.0)
        
        # Combine
        strength = (price_strength * 0.4 + volume_strength * 0.3 + duration_score * 0.3)
        
        return max(0, min(1, strength))
    
    def _calculate_cycle_confidence(self, df: pd.DataFrame, phase: Dict[str, Any]) -> float:
        """
        Calculate cycle confidence.
        
        Args:
            df: OHLCV data
            phase: Phase dictionary
            
        Returns:
            Confidence score (0-1)
        """
        close = df['close'].values
        start = phase['start_idx']
        end = phase['end_idx']
        segment = close[start:end + 1]
        
        # Trend consistency
        slope, intercept = MathUtils.linear_regression(np.arange(len(segment)), segment)
        r2 = MathUtils.r_squared(np.arange(len(segment)), segment)
        consistency = r2
        
        # Phase recognition
        phase_scores = {
            'accumulation': 0.8,
            'markup': 0.9,
            'distribution': 0.8,
            'markdown': 0.9
        }
        phase_score = phase_scores.get(phase['phase'], 0.5)
        
        # Sub-phase adjustment
        sub_phase_scores = {
            'early': 0.7,
            'mid': 0.8,
            'late': 0.9
        }
        sub_phase_score = sub_phase_scores.get(phase['sub_phase'], 0.7)
        
        # Duration factor
        duration = end - start
        duration_score = min(duration / 30, 1.0)
        
        # Combine
        confidence = (consistency * 0.3 + phase_score * 0.3 + sub_phase_score * 0.2 + duration_score * 0.2)
        
        return max(0, min(1, confidence))
    
    def _generate_signals(self, df: pd.DataFrame,
                         cycle: Optional[MarketCycle]) -> List[CycleSignal]:
        """
        Generate trading signals from market cycle.
        
        Args:
            df: OHLCV data
            cycle: MarketCycle object
            
        Returns:
            List of CycleSignal objects
        """
        signals = []
        
        if not cycle:
            return signals
        
        if cycle.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on cycle phase
        if cycle.phase == 'accumulation' and cycle.sub_phase == 'late':
            signal_type = 'buy'
            reason = f"Late accumulation phase - potential markup"
            confidence = cycle.confidence
            target = current_price * 1.05
            stop_loss = current_price * 0.95
            
        elif cycle.phase == 'markup' and cycle.sub_phase == 'early':
            signal_type = 'buy'
            reason = f"Early markup phase - trend beginning"
            confidence = cycle.confidence
            target = current_price * 1.03
            stop_loss = current_price * 0.97
            
        elif cycle.phase == 'distribution' and cycle.sub_phase == 'late':
            signal_type = 'sell'
            reason = f"Late distribution phase - potential markdown"
            confidence = cycle.confidence
            target = current_price * 0.95
            stop_loss = current_price * 1.05
            
        elif cycle.phase == 'markdown' and cycle.sub_phase == 'early':
            signal_type = 'sell'
            reason = f"Early markdown phase - trend beginning"
            confidence = cycle.confidence
            target = current_price * 0.97
            stop_loss = current_price * 1.03
            
        else:
            return signals
        
        signals.append(CycleSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            cycle=cycle,
            indicators={
                'phase': cycle.phase,
                'sub_phase': cycle.sub_phase,
                'strength': cycle.strength,
                'duration': cycle.duration
            }
        ))
        
        return signals
    
    def _get_status(self, cycle: Optional[MarketCycle]) -> str:
        """
        Get status from market cycle.
        
        Args:
            cycle: MarketCycle object
            
        Returns:
            Status string
        """
        if not cycle:
            return 'unknown'
        
        phase_map = {
            'accumulation': 'Accumulation phase',
            'markup': 'Markup phase',
            'distribution': 'Distribution phase',
            'markdown': 'Markdown phase'
        }
        
        sub_phase_map = {
            'early': 'Early',
            'mid': 'Mid',
            'late': 'Late'
        }
        
        phase_name = phase_map.get(cycle.phase, cycle.phase)
        sub_phase_name = sub_phase_map.get(cycle.sub_phase, cycle.sub_phase)
        
        return f"{sub_phase_name} {phase_name}"
    
    def _get_market_character(self, df: pd.DataFrame,
                            cycle: Optional[MarketCycle]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            cycle: MarketCycle object
            
        Returns:
            Market character description
        """
        status = self._get_status(cycle)
        strength = cycle.strength if cycle else 0
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
        
        return f"{strength_names[strength_level]} {status}" if status != 'unknown' else "No cycle detected"
    
    def get_cycle_summary(self) -> Dict[str, Any]:
        """
        Get market cycle summary.
        
        Returns:
            Cycle summary
        """
        if not self.cycle_history:
            return {'status': 'no_cycles'}
        
        latest = self.cycle_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_cycle': latest,
            'phase_distribution': {
                'accumulation': len([c for c in self.cycle_history if c.phase == 'accumulation']),
                'markup': len([c for c in self.cycle_history if c.phase == 'markup']),
                'distribution': len([c for c in self.cycle_history if c.phase == 'distribution']),
                'markdown': len([c for c in self.cycle_history if c.phase == 'markdown'])
            },
            'average_duration': np.mean([c.duration for c in self.cycle_history]),
            'average_strength': np.mean([c.strength for c in self.cycle_history]),
            'current_phase': self._get_status(latest)
        }


def create_market_cycle_model(config: Optional[Dict[str, Any]] = None) -> MarketCycleModel:
    """
    Create a market cycle model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        MarketCycleModel instance
    """
    return MarketCycleModel(config)


__all__ = [
    'MarketCycle',
    'CycleSignal',
    'MarketCycleModel',
    'create_market_cycle_model'
]
