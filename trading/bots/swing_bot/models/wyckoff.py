"""
Swing Bot Wyckoff Model
========================

This module provides Wyckoff analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import talib
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class WyckoffPhase:
    """Wyckoff phase data structure."""
    phase: str  # 'accumulation', 'markup', 'distribution', 'markdown'
    sub_phase: str  # 'a', 'b', 'c', 'd', 'e'
    strength: float
    timestamp: datetime
    price_range: Tuple[float, float]
    volume_profile: Dict[str, float]


@dataclass
class WyckoffSignal:
    """Wyckoff trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    phase: str
    confidence: float
    price: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class WyckoffModel:
    """
    Wyckoff Method analysis model.
    
    Implements the Wyckoff Method for market analysis, including:
    - Accumulation phases (A, B, C, D, E)
    - Distribution phases (A, B, C, D, E)
    - Markup and Markdown phases
    - Wyckoff's laws of supply and demand
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Wyckoff model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.min_price_range = self.config.get('min_price_range', 0.02)
        self.phase_confirmation = self.config.get('phase_confirmation', 5)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        
        # Wyckoff's laws
        self.law_supply_demand = self.config.get('law_supply_demand', True)
        self.law_cause_effect = self.config.get('law_cause_effect', True)
        self.law_effort_result = self.config.get('law_effort_result', True)
    
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze Wyckoff phases and patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Wyckoff analysis results
        """
        if len(df) < self.lookback_period:
            return {'phase': 'insufficient_data', 'signals': []}
        
        # Identify phases
        phases = self._identify_phases(df)
        
        # Generate signals
        signals = self._generate_signals(df, phases)
        
        # Calculate phase strength
        strength = self._calculate_phase_strength(df, phases)
        
        return {
            'phase': phases[-1].phase if phases else 'unknown',
            'sub_phase': phases[-1].sub_phase if phases else 'unknown',
            'strength': strength,
            'phases': phases,
            'signals': signals,
            'market_character': self._get_market_character(df, phases)
        }
    
    def _identify_phases(self, df: pd.DataFrame) -> List[WyckoffPhase]:
        """
        Identify Wyckoff phases.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of Wyckoff phases
        """
        phases = []
        
        # Identify swing points
        swings = self._identify_swings(df)
        
        # Analyze price and volume patterns
        for i in range(len(swings) - 1):
            phase = self._classify_phase(df, swings, i)
            if phase:
                phases.append(phase)
        
        return phases
    
    def _identify_swings(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Identify swing highs and lows."""
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        swings = []
        left_bars = self.config.get('swing_left_bars', 5)
        right_bars = self.config.get('swing_right_bars', 5)
        
        for i in range(left_bars, len(df) - right_bars):
            # Check for swing high
            is_high = True
            for j in range(left_bars):
                if high[i] <= high[i - j - 1]:
                    is_high = False
                    break
            if is_high:
                for j in range(right_bars):
                    if high[i] <= high[i + j + 1]:
                        is_high = False
                        break
            
            # Check for swing low
            is_low = True
            if not is_high:
                for j in range(left_bars):
                    if low[i] >= low[i - j - 1]:
                        is_low = False
                        break
                if is_low:
                    for j in range(right_bars):
                        if low[i] >= low[i + j + 1]:
                            is_low = False
                            break
            
            if is_high:
                swings.append({
                    'type': 'high',
                    'price': high[i],
                    'index': i,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else i
                })
            elif is_low:
                swings.append({
                    'type': 'low',
                    'price': low[i],
                    'index': i,
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else i
                })
        
        return swings
    
    def _classify_phase(self, df: pd.DataFrame, swings: List[Dict[str, Any]], idx: int) -> Optional[WyckoffPhase]:
        """Classify a Wyckoff phase."""
        if idx + 1 >= len(swings):
            return None
        
        current = swings[idx]
        next_swing = swings[idx + 1]
        
        # Analyze price and volume characteristics
        start_idx = current['index']
        end_idx = next_swing['index']
        
        segment = df.iloc[start_idx:end_idx + 1]
        
        if len(segment) < 5:
            return None
        
        price_range = next_swing['price'] - current['price']
        avg_volume = segment['volume'].mean()
        volume_velocity = self._calc_volume_velocity(segment)
        
        # Determine phase type
        if current['type'] == 'low' and next_swing['type'] == 'high':
            # Upward movement
            if price_range / current['price'] < self.min_price_range:
                phase = 'consolidation'
                sub_phase = 'a'
            elif volume_velocity > self.volume_threshold:
                phase = 'markup'
                sub_phase = 'c'
            else:
                phase = 'markup'
                sub_phase = 'b'
        elif current['type'] == 'high' and next_swing['type'] == 'low':
            # Downward movement
            if abs(price_range) / current['price'] < self.min_price_range:
                phase = 'consolidation'
                sub_phase = 'a'
            elif volume_velocity > self.volume_threshold:
                phase = 'markdown'
                sub_phase = 'c'
            else:
                phase = 'markdown'
                sub_phase = 'b'
        else:
            return None
        
        return WyckoffPhase(
            phase=phase,
            sub_phase=sub_phase,
            strength=self._calc_phase_strength(segment),
            timestamp=current['timestamp'] if isinstance(current['timestamp'], datetime) else datetime.now(),
            price_range=(min(segment['low']), max(segment['high'])),
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _calc_phase_strength(self, segment: pd.DataFrame) -> float:
        """Calculate phase strength."""
        if len(segment) < 5:
            return 0.0
        
        # Price movement strength
        price_change = (segment['close'].iloc[-1] - segment['close'].iloc[0]) / segment['close'].iloc[0]
        price_strength = abs(price_change)
        
        # Volume strength
        avg_volume = segment['volume'].mean()
        volume_strength = min(avg_volume / 1000000, 1.0)
        
        # Volatility strength
        volatility = segment['close'].pct_change().std()
        volatility_strength = min(volatility * 10, 1.0)
        
        return (price_strength * 0.4 + volume_strength * 0.4 + volatility_strength * 0.2)
    
    def _calc_volume_velocity(self, segment: pd.DataFrame) -> float:
        """Calculate volume velocity."""
        if len(segment) < 10:
            return 0.0
        
        recent_avg = segment['volume'].tail(5).mean()
        past_avg = segment['volume'].head(5).mean()
        
        if past_avg == 0:
            return 0.0
        
        return recent_avg / past_avg
    
    def _calc_volume_profile(self, segment: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume profile."""
        price_range = segment['high'].max() - segment['low'].min()
        if price_range == 0:
            return {}
        
        bins = 10
        volume_profile = {}
        
        for i in range(bins):
            low = segment['low'].min() + (i / bins) * price_range
            high = segment['low'].min() + ((i + 1) / bins) * price_range
            
            mask = (segment['high'] >= low) & (segment['low'] <= high)
            volume = segment.loc[mask, 'volume'].sum()
            
            volume_profile[f"{low:.2f}-{high:.2f}"] = volume
        
        return volume_profile
    
    def _generate_signals(self, df: pd.DataFrame, phases: List[WyckoffPhase]) -> List[WyckoffSignal]:
        """Generate trading signals based on Wyckoff phases."""
        signals = []
        
        if not phases:
            return signals
        
        latest_phase = phases[-1]
        
        # Buy signals
        if latest_phase.phase == 'accumulation' and latest_phase.sub_phase in ['c', 'd', 'e']:
            signal = WyckoffSignal(
                symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
                timestamp=datetime.now(),
                signal_type='buy',
                phase=latest_phase.phase,
                confidence=min(latest_phase.strength * 1.5, 1.0),
                price=df['close'].iloc[-1],
                reason=f"Accumulation phase {latest_phase.sub_phase} detected"
            )
            signals.append(signal)
        
        # Sell signals
        if latest_phase.phase == 'distribution' and latest_phase.sub_phase in ['c', 'd', 'e']:
            signal = WyckoffSignal(
                symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
                timestamp=datetime.now(),
                signal_type='sell',
                phase=latest_phase.phase,
                confidence=min(latest_phase.strength * 1.5, 1.0),
                price=df['close'].iloc[-1],
                reason=f"Distribution phase {latest_phase.sub_phase} detected"
            )
            signals.append(signal)
        
        # Short signals
        if latest_phase.phase == 'markdown' and latest_phase.sub_phase in ['b', 'c']:
            signal = WyckoffSignal(
                symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
                timestamp=datetime.now(),
                signal_type='short',
                phase=latest_phase.phase,
                confidence=min(latest_phase.strength * 1.5, 1.0),
                price=df['close'].iloc[-1],
                reason=f"Markdown phase {latest_phase.sub_phase} detected"
            )
            signals.append(signal)
        
        # Cover signals (exit shorts)
        if latest_phase.phase == 'accumulation' and latest_phase.sub_phase in ['a', 'b']:
            signal = WyckoffSignal(
                symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
                timestamp=datetime.now(),
                signal_type='cover',
                phase=latest_phase.phase,
                confidence=min(latest_phase.strength * 1.5, 1.0),
                price=df['close'].iloc[-1],
                reason=f"Accumulation phase {latest_phase.sub_phase} detected, covering shorts"
            )
            signals.append(signal)
        
        return signals
    
    def _calculate_phase_strength(self, df: pd.DataFrame, phases: List[WyckoffPhase]) -> float:
        """Calculate overall phase strength."""
        if not phases:
            return 0.0
        
        # Weighted average of recent phases
        weights = np.linspace(0.5, 1.0, len(phases))
        strengths = [p.strength for p in phases]
        
        return np.average(strengths, weights=weights)
    
    def _get_market_character(self, df: pd.DataFrame, phases: List[WyckoffPhase]) -> str:
        """Get market character description."""
        if not phases:
            return "Neutral"
        
        latest = phases[-1]
        
        market_chars = {
            'accumulation': "Accumulation - Smart money buying",
            'markup': "Markup - Bullish trend",
            'distribution': "Distribution - Smart money selling",
            'markdown': "Markdown - Bearish trend",
            'consolidation': "Consolidation - Range bound"
        }
        
        return market_chars.get(latest.phase, "Unknown")
    
    def get_wyckoff_laws(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Check Wyckoff's three laws.
        
        Args:
            df: OHLCV data
            
        Returns:
            Dictionary of law statuses
        """
        laws = {}
        
        # Law of Supply and Demand
        if self.law_supply_demand:
            supply_demand = self._check_supply_demand(df)
            laws['supply_demand'] = supply_demand
        
        # Law of Cause and Effect
        if self.law_cause_effect:
            cause_effect = self._check_cause_effect(df)
            laws['cause_effect'] = cause_effect
        
        # Law of Effort and Result
        if self.law_effort_result:
            effort_result = self._check_effort_result(df)
            laws['effort_result'] = effort_result
        
        return laws
    
    def _check_supply_demand(self, df: pd.DataFrame) -> bool:
        """Check Wyckoff's Law of Supply and Demand."""
        # Check if price increases on high volume (demand)
        # and decreases on low volume (supply)
        price_change = df['close'].pct_change()
        volume_change = df['volume'].pct_change()
        
        demand = (price_change > 0) & (volume_change > 0)
        supply = (price_change < 0) & (volume_change > 0)
        
        if demand.any() and supply.any():
            return True
        return False
    
    def _check_cause_effect(self, df: pd.DataFrame) -> bool:
        """Check Wyckoff's Law of Cause and Effect."""
        # Check if the magnitude of price movement is proportional
        # to the duration of consolidation
        return True  # Placeholder
    
    def _check_effort_result(self, df: pd.DataFrame) -> bool:
        """Check Wyckoff's Law of Effort and Result."""
        # Check if volume (effort) confirms price movement (result)
        price_change = df['close'].pct_change().abs()
        volume_ma = df['volume'].rolling(20).mean()
        
        effort = df['volume'] > volume_ma
        result = price_change > self.min_price_range
        
        return (effort & result).any()


def create_wyckoff_model(config: Optional[Dict[str, Any]] = None) -> WyckoffModel:
    """
    Create a Wyckoff model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        WyckoffModel instance
    """
    return WyckoffModel(config)


__all__ = [
    'WyckoffPhase',
    'WyckoffSignal',
    'WyckoffModel',
    'create_wyckoff_model'
]
