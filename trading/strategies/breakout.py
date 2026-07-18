# trading/strategies/breakout.py
"""
NEXUS AI TRADING SYSTEM - Breakout Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements various breakout trading strategies including:
- Channel breakouts (Bollinger Bands, Keltner Channels)
- Support/Resistance breakouts
- Volume-confirmed breakouts
- Volatility-based breakouts
- False breakout detection

The strategy identifies key levels and generates signals when price
breaks through these levels with confirmation.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import deque

import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Signal, Position, Trade
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class BreakoutType(str, Enum):
    """Types of breakout strategies"""
    BOLLINGER_BANDS = "bollinger_bands"
    KELTNER_CHANNEL = "keltner_channel"
    DONCHIAN_CHANNEL = "donchian_channel"
    SUPPORT_RESISTANCE = "support_resistance"
    VOLUME_BREAKOUT = "volume_breakout"
    VOLATILITY_BREAKOUT = "volatility_breakout"
    PIVOT_BREAKOUT = "pivot_breakout"
    MULTI_TIMEFRAME = "multi_timeframe"


class BreakoutConfirmation(str, Enum):
    """Confirmation methods for breakouts"""
    VOLUME = "volume"
    CLOSE = "close"
    RETEST = "retest"
    MOMENTUM = "momentum"
    MULTI_TIMEFRAME = "multi_timeframe"
    COMBINED = "combined"


@dataclass
class BreakoutConfig:
    """Configuration for breakout strategy"""
    # General settings
    breakout_type: BreakoutType = BreakoutType.BOLLINGER_BANDS
    confirmation_method: BreakoutConfirmation = BreakoutConfirmation.CLOSE
    min_breakout_pct: float = 0.5  # Minimum breakout percentage
    max_breakout_pct: float = 5.0   # Maximum breakout percentage
    lookback_period: int = 20
    min_volume_ratio: float = 1.5  # Volume must be 1.5x average
    
    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0
    bb_use_close: bool = True
    
    # Keltner Channel
    kc_period: int = 20
    kc_multiplier: float = 1.5
    kc_atr_period: int = 10
    
    # Donchian Channel
    dc_period: int = 20
    
    # Support/Resistance
    sr_lookback: int = 50
    sr_tolerance: float = 0.01  # 1% tolerance
    sr_min_touches: int = 2
    
    # Volume
    volume_lookback: int = 20
    volume_ma_period: int = 20
    volume_spike_threshold: float = 2.0
    
    # Volatility
    volatility_lookback: int = 20
    volatility_multiplier: float = 2.0
    
    # Multi-timeframe
    mtf_higher_timeframe: str = "4h"
    mtf_lower_timeframe: str = "1h"
    mtf_confirmation_required: bool = True
    
    # False breakout detection
    false_breakout_check: bool = True
    false_breakout_retest: bool = True
    false_breakout_timeframe: int = 3  # Candles to wait for confirmation
    
    # Risk management
    stop_loss_at_breakout_level: bool = True
    stop_loss_pct: float = 0.02
    take_profit_risk_ratio: float = 2.0
    
    # Signal generation
    signal_threshold: float = 0.6
    min_streak: int = 1


@dataclass
class BreakoutLevel:
    """A breakout level detected by the strategy"""
    level_type: str  # "resistance", "support", "channel_upper", "channel_lower"
    price: float
    strength: float  # 0-1
    touches: int
    last_touch: Optional[datetime] = None
    volume_at_break: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreakoutSignal:
    """Detailed breakout signal"""
    symbol: str
    breakout_type: BreakoutType
    direction: str  # "up" or "down"
    breakout_price: float
    target_price: float
    stop_loss: float
    confidence: float
    volume_ratio: Optional[float] = None
    level: Optional[BreakoutLevel] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# BREAKOUT STRATEGY
# ============================================================================

class BreakoutStrategy(BaseStrategy):
    """
    Breakout trading strategy that identifies and trades breakouts
    from various channel and level-based patterns.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        breakout_config: Optional[BreakoutConfig] = None,
    ):
        """
        Initialize the breakout strategy.
        
        Args:
            config: Strategy configuration
            breakout_config: Breakout-specific configuration
        """
        super().__init__(config)
        self.breakout_config = breakout_config or BreakoutConfig()
        
        # Data storage
        self._market_data: Dict[str, deque] = {}
        self._volume_data: Dict[str, deque] = {}
        
        # Level tracking
        self._levels: Dict[str, List[BreakoutLevel]] = {}
        self._breakout_history: Dict[str, List[BreakoutSignal]] = {}
        self._false_breakouts: Dict[str, List[BreakoutSignal]] = {}
        
        # Indicators
        self._bb_upper: Dict[str, float] = {}
        self._bb_lower: Dict[str, float] = {}
        self._bb_middle: Dict[str, float] = {}
        self._kc_upper: Dict[str, float] = {}
        self._kc_lower: Dict[str, float] = {}
        self._dc_high: Dict[str, float] = {}
        self._dc_low: Dict[str, float] = {}
        self._volume_ma: Dict[str, float] = {}
        self._atr: Dict[str, float] = {}
        
        # Performance tracking
        self._breakout_stats = {
            "total_breakouts": 0,
            "successful_breakouts": 0,
            "failed_breakouts": 0,
            "false_breakouts_detected": 0,
            "avg_breakout_gain": 0.0,
            "avg_breakout_loss": 0.0,
        }
        
        self.logger = logger
    
    # ========================================================================
    # INDICATOR CALCULATIONS
    # ========================================================================
    
    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: Optional[int] = None,
        std_dev: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Price series
            period: Lookback period
            std_dev: Standard deviation multiplier
            
        Returns:
            Tuple[float, float, float]: (upper, middle, lower)
        """
        period = period or self.breakout_config.bb_period
        std_dev = std_dev or self.breakout_config.bb_std_dev
        
        if len(prices) < period:
            return 0.0, 0.0, 0.0
        
        recent = prices[-period:]
        middle = sum(recent) / len(recent)
        
        # Calculate standard deviation
        variance = sum((p - middle) ** 2 for p in recent) / len(recent)
        std = math.sqrt(variance)
        
        upper = middle + std * std_dev
        lower = middle - std * std_dev
        
        return upper, middle, lower
    
    def calculate_keltner_channel(
        self,
        prices: List[float],
        period: Optional[int] = None,
        multiplier: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate Keltner Channel.
        
        Args:
            prices: Price series
            period: Lookback period
            multiplier: Channel multiplier
            
        Returns:
            Tuple[float, float, float]: (upper, middle, lower)
        """
        period = period or self.breakout_config.kc_period
        multiplier = multiplier or self.breakout_config.kc_multiplier
        
        if len(prices) < period:
            return 0.0, 0.0, 0.0
        
        recent = prices[-period:]
        middle = sum(recent) / len(recent)
        
        # Calculate ATR (simplified)
        atr = self.calculate_atr(prices, self.breakout_config.kc_atr_period)
        
        upper = middle + atr * multiplier
        lower = middle - atr * multiplier
        
        return upper, middle, lower
    
    def calculate_donchian_channel(
        self,
        prices: List[float],
        period: Optional[int] = None,
    ) -> Tuple[float, float]:
        """
        Calculate Donchian Channel.
        
        Args:
            prices: Price series
            period: Lookback period
            
        Returns:
            Tuple[float, float]: (high, low)
        """
        period = period or self.breakout_config.dc_period
        
        if len(prices) < period:
            return 0.0, 0.0
        
        recent = prices[-period:]
        return max(recent), min(recent)
    
    def calculate_atr(
        self,
        prices: List[float],
        period: int = 14,
    ) -> float:
        """
        Calculate Average True Range.
        
        Args:
            prices: Price series
            period: Lookback period
            
        Returns:
            float: ATR value
        """
        if len(prices) < period:
            return 0.0
        
        # Simplified ATR using price range
        ranges = []
        for i in range(1, min(len(prices), period + 1)):
            high = prices[i]
            low = prices[i - 1]
            ranges.append(abs(high - low))
        
        if not ranges:
            return 0.0
        
        return sum(ranges) / len(ranges)
    
    def calculate_volume_ma(
        self,
        volumes: List[float],
        period: Optional[int] = None,
    ) -> float:
        """
        Calculate volume moving average.
        
        Args:
            volumes: Volume series
            period: Lookback period
            
        Returns:
            float: Volume moving average
        """
        period = period or self.breakout_config.volume_ma_period
        
        if len(volumes) < period:
            return 0.0
        
        recent = volumes[-period:]
        return sum(recent) / len(recent)
    
    def find_support_resistance(
        self,
        prices: List[float],
        lookback: Optional[int] = None,
    ) -> Tuple[List[float], List[float]]:
        """
        Find support and resistance levels.
        
        Args:
            prices: Price series
            lookback: Lookback period
            
        Returns:
            Tuple[List[float], List[float]]: (support_levels, resistance_levels)
        """
        lookback = lookback or self.breakout_config.sr_lookback
        tolerance = self.breakout_config.sr_tolerance
        
        if len(prices) < lookback:
            return [], []
        
        recent = prices[-lookback:]
        support_levels = []
        resistance_levels = []
        
        # Find local minima and maxima
        for i in range(1, len(recent) - 1):
            if recent[i] < recent[i-1] and recent[i] < recent[i+1]:
                # Local minimum - support
                support_levels.append(recent[i])
            elif recent[i] > recent[i-1] and recent[i] > recent[i+1]:
                # Local maximum - resistance
                resistance_levels.append(recent[i])
        
        # Cluster similar levels
        support_levels = self._cluster_levels(support_levels, tolerance)
        resistance_levels = self._cluster_levels(resistance_levels, tolerance)
        
        return support_levels, resistance_levels
    
    def _cluster_levels(
        self,
        levels: List[float],
        tolerance: float,
    ) -> List[float]:
        """
        Cluster price levels that are close to each other.
        
        Args:
            levels: List of price levels
            tolerance: Tolerance for clustering
            
        Returns:
            List[float]: Clustered levels
        """
        if not levels:
            return []
        
        sorted_levels = sorted(levels)
        clustered = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                current_cluster.append(level)
            else:
                clustered.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clustered.append(sum(current_cluster) / len(current_cluster))
        
        return clustered
    
    # ========================================================================
    # BREAKOUT DETECTION
    # ========================================================================
    
    async def detect_breakouts(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]] = None,
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None,
    ) -> List[BreakoutSignal]:
        """
        Detect breakout signals from market data.
        
        Args:
            symbol: Trading symbol
            prices: Price series
            volumes: Volume series
            highs: High prices
            lows: Low prices
            
        Returns:
            List[BreakoutSignal]: Detected breakout signals
        """
        breakouts = []
        
        if len(prices) < self.breakout_config.lookback_period:
            return breakouts
        
        current_price = prices[-1]
        current_volume = volumes[-1] if volumes else 0
        
        breakout_type = self.breakout_config.breakout_type
        
        # Bollinger Bands breakout
        if breakout_type == BreakoutType.BOLLINGER_BANDS:
            breakouts = await self._detect_bb_breakout(symbol, prices, current_price)
        
        # Keltner Channel breakout
        elif breakout_type == BreakoutType.KELTNER_CHANNEL:
            breakouts = await self._detect_kc_breakout(symbol, prices, current_price)
        
        # Donchian Channel breakout
        elif breakout_type == BreakoutType.DONCHIAN_CHANNEL:
            breakouts = await self._detect_dc_breakout(symbol, prices, current_price, highs, lows)
        
        # Support/Resistance breakout
        elif breakout_type == BreakoutType.SUPPORT_RESISTANCE:
            breakouts = await self._detect_sr_breakout(symbol, prices, current_price)
        
        # Volume breakout
        elif breakout_type == BreakoutType.VOLUME_BREAKOUT:
            breakouts = await self._detect_volume_breakout(
                symbol, prices, volumes, current_price, current_volume
            )
        
        # Volatility breakout
        elif breakout_type == BreakoutType.VOLATILITY_BREAKOUT:
            breakouts = await self._detect_volatility_breakout(symbol, prices, current_price)
        
        # Multi-timeframe breakout
        elif breakout_type == BreakoutType.MULTI_TIMEFRAME:
            breakouts = await self._detect_mtf_breakout(symbol, prices, current_price)
        
        # Apply confirmations
        if breakouts:
            breakouts = await self._apply_confirmations(breakouts, prices, volumes, symbol)
        
        # Filter and rank
        breakouts = self._filter_breakouts(breakouts)
        breakouts = self._rank_breakouts(breakouts)
        
        return breakouts
    
    # ========================================================================
    # BREAKOUT DETECTION METHODS
    # ========================================================================
    
    async def _detect_bb_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
    ) -> List[BreakoutSignal]:
        """Detect Bollinger Bands breakout."""
        breakouts = []
        
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        
        if upper == 0 or lower == 0:
            return breakouts
        
        self._bb_upper[symbol] = upper
        self._bb_middle[symbol] = middle
        self._bb_lower[symbol] = lower
        
        # Check upper band breakout (resistance)
        if current_price > upper:
            breakout_pct = (current_price - upper) / upper * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = upper + (upper - middle)  # Extension
                stop_loss = middle
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.BOLLINGER_BANDS,
                    direction="up",
                    breakout_price=upper,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.7 + (breakout_pct / 10) * 0.2,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "bb_upper": upper,
                        "bb_middle": middle,
                        "bb_lower": lower,
                        "level": "bb_upper",
                    },
                )
                breakouts.append(signal)
        
        # Check lower band breakout (support)
        elif current_price < lower:
            breakout_pct = (lower - current_price) / lower * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = lower - (middle - lower)  # Extension
                stop_loss = middle
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.BOLLINGER_BANDS,
                    direction="down",
                    breakout_price=lower,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.7 + (breakout_pct / 10) * 0.2,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "bb_upper": upper,
                        "bb_middle": middle,
                        "bb_lower": lower,
                        "level": "bb_lower",
                    },
                )
                breakouts.append(signal)
        
        return breakouts
    
    async def _detect_kc_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
    ) -> List[BreakoutSignal]:
        """Detect Keltner Channel breakout."""
        breakouts = []
        
        upper, middle, lower = self.calculate_keltner_channel(prices)
        
        if upper == 0 or lower == 0:
            return breakouts
        
        self._kc_upper[symbol] = upper
        self._kc_lower[symbol] = lower
        
        # Check upper channel breakout
        if current_price > upper:
            breakout_pct = (current_price - upper) / upper * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = upper + (upper - middle) * 1.5
                stop_loss = middle
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.KELTNER_CHANNEL,
                    direction="up",
                    breakout_price=upper,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.65 + (breakout_pct / 10) * 0.25,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "kc_upper": upper,
                        "kc_middle": middle,
                        "kc_lower": lower,
                        "level": "kc_upper",
                    },
                )
                breakouts.append(signal)
        
        # Check lower channel breakout
        elif current_price < lower:
            breakout_pct = (lower - current_price) / lower * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = lower - (middle - lower) * 1.5
                stop_loss = middle
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.KELTNER_CHANNEL,
                    direction="down",
                    breakout_price=lower,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.65 + (breakout_pct / 10) * 0.25,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "kc_upper": upper,
                        "kc_middle": middle,
                        "kc_lower": lower,
                        "level": "kc_lower",
                    },
                )
                breakouts.append(signal)
        
        return breakouts
    
    async def _detect_dc_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None,
    ) -> List[BreakoutSignal]:
        """Detect Donchian Channel breakout."""
        breakouts = []
        
        # Use highs/lows if available, otherwise use prices
        high_prices = highs if highs and len(highs) >= self.breakout_config.dc_period else prices
        low_prices = lows if lows and len(lows) >= self.breakout_config.dc_period else prices
        
        high, low = self.calculate_donchian_channel(high_prices, self.breakout_config.dc_period)
        high_low, low_low = self.calculate_donchian_channel(low_prices, self.breakout_config.dc_period)
        
        dc_high = max(high, high_low)
        dc_low = min(low, low_low)
        
        if dc_high == 0 or dc_low == 0:
            return breakouts
        
        self._dc_high[symbol] = dc_high
        self._dc_low[symbol] = dc_low
        
        # Check high breakout
        if current_price > dc_high:
            breakout_pct = (current_price - dc_high) / dc_high * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = dc_high + (dc_high - dc_low) * 0.5
                stop_loss = (dc_high + dc_low) / 2
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.DONCHIAN_CHANNEL,
                    direction="up",
                    breakout_price=dc_high,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.6 + (breakout_pct / 10) * 0.3,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "dc_high": dc_high,
                        "dc_low": dc_low,
                        "level": "dc_high",
                    },
                )
                breakouts.append(signal)
        
        # Check low breakout
        elif current_price < dc_low:
            breakout_pct = (dc_low - current_price) / dc_low * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = dc_low - (dc_high - dc_low) * 0.5
                stop_loss = (dc_high + dc_low) / 2
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.DONCHIAN_CHANNEL,
                    direction="down",
                    breakout_price=dc_low,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.6 + (breakout_pct / 10) * 0.3,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "dc_high": dc_high,
                        "dc_low": dc_low,
                        "level": "dc_low",
                    },
                )
                breakouts.append(signal)
        
        return breakouts
    
    async def _detect_sr_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
    ) -> List[BreakoutSignal]:
        """Detect support/resistance breakout."""
        breakouts = []
        
        support_levels, resistance_levels = self.find_support_resistance(
            prices, self.breakout_config.sr_lookback
        )
        
        # Update levels
        self._levels[symbol] = []
        
        # Check resistance breakouts
        for level in resistance_levels:
            if current_price > level:
                breakout_pct = (current_price - level) / level * 100
                if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                    # Find next resistance as target
                    targets = [r for r in resistance_levels if r > level]
                    target = targets[0] if targets else level * 1.02
                    
                    stop_loss = level * 0.99
                    
                    level_obj = BreakoutLevel(
                        level_type="resistance",
                        price=level,
                        strength=0.8,
                        touches=0,
                    )
                    self._levels[symbol].append(level_obj)
                    
                    signal = BreakoutSignal(
                        symbol=symbol,
                        breakout_type=BreakoutType.SUPPORT_RESISTANCE,
                        direction="up",
                        breakout_price=level,
                        target_price=target,
                        stop_loss=stop_loss,
                        confidence=0.7 + (breakout_pct / 10) * 0.2,
                        level=level_obj,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "breakout_pct": breakout_pct,
                            "level_type": "resistance",
                            "level": level,
                            "target": target,
                        },
                    )
                    breakouts.append(signal)
        
        # Check support breakouts
        for level in support_levels:
            if current_price < level:
                breakout_pct = (level - current_price) / level * 100
                if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                    # Find next support as target
                    targets = [s for s in support_levels if s < level]
                    target = targets[-1] if targets else level * 0.98
                    
                    stop_loss = level * 1.01
                    
                    level_obj = BreakoutLevel(
                        level_type="support",
                        price=level,
                        strength=0.8,
                        touches=0,
                    )
                    self._levels[symbol].append(level_obj)
                    
                    signal = BreakoutSignal(
                        symbol=symbol,
                        breakout_type=BreakoutType.SUPPORT_RESISTANCE,
                        direction="down",
                        breakout_price=level,
                        target_price=target,
                        stop_loss=stop_loss,
                        confidence=0.7 + (breakout_pct / 10) * 0.2,
                        level=level_obj,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "breakout_pct": breakout_pct,
                            "level_type": "support",
                            "level": level,
                            "target": target,
                        },
                    )
                    breakouts.append(signal)
        
        return breakouts
    
    async def _detect_volume_breakout(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]],
        current_price: float,
        current_volume: float,
    ) -> List[BreakoutSignal]:
        """Detect volume-confirmed breakout."""
        breakouts = []
        
        if not volumes or len(volumes) < self.breakout_config.volume_lookback:
            return breakouts
        
        # Calculate volume moving average
        volume_ma = self.calculate_volume_ma(volumes)
        self._volume_ma[symbol] = volume_ma
        
        if volume_ma == 0:
            return breakouts
        
        volume_ratio = current_volume / volume_ma
        
        # Check volume spike
        if volume_ratio < self.breakout_config.min_volume_ratio:
            return breakouts
        
        # Check price breakout from recent range
        recent_high = max(prices[-self.breakout_config.lookback_period:-1])
        recent_low = min(prices[-self.breakout_config.lookback_period:-1])
        
        if current_price > recent_high:
            breakout_pct = (current_price - recent_high) / recent_high * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = recent_high + (recent_high - recent_low) * 0.5
                stop_loss = recent_high * 0.99
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.VOLUME_BREAKOUT,
                    direction="up",
                    breakout_price=recent_high,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.75 + min(volume_ratio / 10, 0.2),
                    volume_ratio=volume_ratio,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "volume_ratio": volume_ratio,
                        "recent_high": recent_high,
                        "recent_low": recent_low,
                        "volume_ma": volume_ma,
                    },
                )
                breakouts.append(signal)
        
        elif current_price < recent_low:
            breakout_pct = (recent_low - current_price) / recent_low * 100
            if self.breakout_config.min_breakout_pct <= breakout_pct <= self.breakout_config.max_breakout_pct:
                target = recent_low - (recent_high - recent_low) * 0.5
                stop_loss = recent_low * 1.01
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.VOLUME_BREAKOUT,
                    direction="down",
                    breakout_price=recent_low,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.75 + min(volume_ratio / 10, 0.2),
                    volume_ratio=volume_ratio,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "volume_ratio": volume_ratio,
                        "recent_high": recent_high,
                        "recent_low": recent_low,
                        "volume_ma": volume_ma,
                    },
                )
                breakouts.append(signal)
        
        return breakouts
    
    async def _detect_volatility_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
    ) -> List[BreakoutSignal]:
        """Detect volatility-based breakout."""
        breakouts = []
        
        if len(prices) < self.breakout_config.volatility_lookback + 1:
            return breakouts
        
        # Calculate ATR
        atr = self.calculate_atr(prices, self.breakout_config.volatility_lookback)
        self._atr[symbol] = atr
        
        if atr == 0:
            return breakouts
        
        # Calculate average price
        avg_price = sum(prices[-self.breakout_config.volatility_lookback:]) / self.breakout_config.volatility_lookback
        
        # Volatility threshold
        threshold = avg_price * (self.breakout_config.volatility_multiplier * atr / avg_price)
        
        # Check for volatility expansion
        if len(prices) > 1:
            price_change = abs(prices[-1] - prices[-2])
            
            if price_change > threshold:
                # Determine direction
                if prices[-1] > prices[-2]:
                    direction = "up"
                    breakout_price = prices[-2]
                    target = prices[-1] + threshold
                    stop_loss = prices[-1] - threshold
                else:
                    direction = "down"
                    breakout_price = prices[-2]
                    target = prices[-1] - threshold
                    stop_loss = prices[-1] + threshold
                
                breakout_pct = abs(prices[-1] - prices[-2]) / prices[-2] * 100
                
                signal = BreakoutSignal(
                    symbol=symbol,
                    breakout_type=BreakoutType.VOLATILITY_BREAKOUT,
                    direction=direction,
                    breakout_price=breakout_price,
                    target_price=target,
                    stop_loss=stop_loss,
                    confidence=0.6 + min(breakout_pct / 10, 0.3),
                    timestamp=datetime.utcnow(),
                    metadata={
                        "breakout_pct": breakout_pct,
                        "atr": atr,
                        "threshold": threshold,
                        "price_change": price_change,
                    },
                )
                breakouts.append(signal)
        
        return breakouts
    
    async def _detect_mtf_breakout(
        self,
        symbol: str,
        prices: List[float],
        current_price: float,
    ) -> List[BreakoutSignal]:
        """Detect multi-timeframe breakout."""
        # This is a placeholder - in practice, you would need data from multiple timeframes
        # For now, use Bollinger Bands breakout with higher confidence
        breakouts = await self._detect_bb_breakout(symbol, prices, current_price)
        
        # Increase confidence if also confirmed on higher timeframe
        for breakout in breakouts:
            breakout.confidence = min(1.0, breakout.confidence * 1.15)
            breakout.metadata["mtf_confirmed"] = True
        
        return breakouts
    
    # ========================================================================
    # CONFIRMATION METHODS
    # ========================================================================
    
    async def _apply_confirmations(
        self,
        breakouts: List[BreakoutSignal],
        prices: List[float],
        volumes: Optional[List[float]],
        symbol: str,
    ) -> List[BreakoutSignal]:
        """
        Apply confirmation methods to breakout signals.
        
        Args:
            breakouts: Detected breakouts
            prices: Price series
            volumes: Volume series
            symbol: Trading symbol
            
        Returns:
            List[BreakoutSignal]: Confirmed breakouts
        """
        confirmed = []
        
        for breakout in breakouts:
            confirmation_method = self.breakout_config.confirmation_method
            
            if confirmation_method == BreakoutConfirmation.VOLUME:
                if not volumes:
                    continue
                if not await self._confirm_volume(breakout, volumes, symbol):
                    continue
            
            elif confirmation_method == BreakoutConfirmation.CLOSE:
                if not await self._confirm_close(breakout, prices):
                    continue
            
            elif confirmation_method == BreakoutConfirmation.RETEST:
                if not await self._confirm_retest(breakout, prices):
                    continue
            
            elif confirmation_method == BreakoutConfirmation.MOMENTUM:
                if not await self._confirm_momentum(breakout, prices):
                    continue
            
            elif confirmation_method == BreakoutConfirmation.COMBINED:
                if not await self._confirm_combined(breakout, prices, volumes, symbol):
                    continue            
            confirmed.append(breakout)
        
        return confirmed
    
    async def _confirm_volume(
        self,
        breakout: BreakoutSignal,
        volumes: List[float],
        symbol: str,
    ) -> bool:
        """Confirm breakout with volume."""
        if not volumes:
            return False
        
        # Calculate volume MA
        volume_ma = self.calculate_volume_ma(volumes, self.breakout_config.volume_lookback)
        
        if volume_ma == 0:
            return False
        
        current_volume = volumes[-1]
        volume_ratio = current_volume / volume_ma
        
        return volume_ratio >= self.breakout_config.min_volume_ratio
    
    async def _confirm_close(
        self,
        breakout: BreakoutSignal,
        prices: List[float],
    ) -> bool:
        """Confirm breakout with close price."""
        if len(prices) < 2:
            return False
        
        current_close = prices[-1]
        previous_close = prices[-2]
        
        if breakout.direction == "up":
            return current_close > breakout.breakout_price and previous_close <= breakout.breakout_price
        else:
            return current_close < breakout.breakout_price and previous_close >= breakout.breakout_price
    
    async def _confirm_retest(
        self,
        breakout: BreakoutSignal,
        prices: List[float],
    ) -> bool:
        """Confirm breakout with retest of breakout level."""
        if len(prices) < 3:
            return False
        
        # Check for retest after breakout
        breakout_idx = len(prices) - 1
        
        for i in range(breakout_idx - 3, breakout_idx - 1):
            if i < 0:
                continue
            
            if breakout.direction == "up":
                if prices[i] <= breakout.breakout_price * 1.005 and prices[i] >= breakout.breakout_price * 0.995:
                    return True
            else:
                if prices[i] >= breakout.breakout_price * 0.995 and prices[i] <= breakout.breakout_price * 1.005:
                    return True
        
        return False
    
    async def _confirm_momentum(
        self,
        breakout: BreakoutSignal,
        prices: List[float],
    ) -> bool:
        """Confirm breakout with momentum indicator."""
        if len(prices) < 20:
            return False
        
        # Calculate momentum (ROC)
        roc = (prices[-1] - prices[-10]) / prices[-10] * 100 if len(prices) >= 10 else 0
        
        if breakout.direction == "up":
            return roc > 0
        else:
            return roc < 0
    
    async def _confirm_combined(
        self,
        breakout: BreakoutSignal,
        prices: List[float],
        volumes: Optional[List[float]],
        symbol: str,
    ) -> bool:
        """Combined confirmation using multiple methods."""
        confirmations = []
        
        # Volume confirmation
        if volumes:
            confirmations.append(await self._confirm_volume(breakout, volumes, symbol))
        
        # Close confirmation
        confirmations.append(await self._confirm_close(breakout, prices))
        
        # Momentum confirmation
        confirmations.append(await self._confirm_momentum(breakout, prices))
        
        if not confirmations:
            return False
        
        # Require at least 2 confirmations
        return sum(confirmations) >= 2
    
    # ========================================================================
    # FILTERING AND RANKING
    # ========================================================================
    
    def _filter_breakouts(
        self,
        breakouts: List[BreakoutSignal],
    ) -> List[BreakoutSignal]:
        """
        Filter breakout signals.
        
        Args:
            breakouts: Breakout signals to filter
            
        Returns:
            List[BreakoutSignal]: Filtered breakouts
        """
        filtered = []
        
        for breakout in breakouts:
            # Check confidence threshold
            if breakout.confidence < self.breakout_config.signal_threshold:
                continue
            
            # Check for false breakout
            if self.breakout_config.false_breakout_check:
                if self._is_false_breakout(breakout):
                    self._false_breakouts.setdefault(breakout.symbol, []).append(breakout)
                    self._breakout_stats["false_breakouts_detected"] += 1
                    continue
            
            # Check that stop loss is reasonable
            if breakout.stop_loss <= 0:
                continue
            
            filtered.append(breakout)
        
        return filtered
    
    def _is_false_breakout(self, breakout: BreakoutSignal) -> bool:
        """
        Check if a breakout is likely to be false.
        
        Args:
            breakout: Breakout signal to check
            
        Returns:
            bool: True if likely false breakout
        """
        # Check if price has moved back inside the range
        symbol = breakout.symbol
        
        # This is a placeholder - in practice, you would check
        # if price has reversed back into the channel/range
        
        if breakout.direction == "up":
            # Check if price has fallen back below breakout level
            return False  # Placeholder
        else:
            # Check if price has risen back above breakout level
            return False  # Placeholder
    
    def _rank_breakouts(
        self,
        breakouts: List[BreakoutSignal],
    ) -> List[BreakoutSignal]:
        """
        Rank breakout signals by confidence.
        
        Args:
            breakouts: Breakout signals to rank
            
        Returns:
            List[BreakoutSignal]: Ranked breakouts
        """
        return sorted(breakouts, key=lambda x: x.confidence, reverse=True)
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal from market data.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        # Use the configured symbol or first symbol
        symbol = self.config.symbol or market_data[0].symbol
        
        # Extract data
        prices = [c.last for c in market_data if c.symbol == symbol]
        volumes = [c.volume for c in market_data if c.symbol == symbol] if market_data else None
        highs = [c.high for c in market_data if c.symbol == symbol] if market_data else None
        lows = [c.low for c in market_data if c.symbol == symbol] if market_data else None
        
        if not prices:
            return None
        
        # Detect breakouts
        breakouts = await self.detect_breakouts(symbol, prices, volumes, highs, lows)
        
        if not breakouts:
            return None
        
        # Get best breakout
        best_breakout = breakouts[0]
        
        # Create signal
        signal_type = SignalType.BUY if best_breakout.direction == "up" else SignalType.SELL
        
        # Determine signal strength
        if best_breakout.confidence >= 0.8:
            strength = SignalStrength.STRONG
        elif best_breakout.confidence >= 0.6:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK
        
        # Create Signal
        signal = Signal(
            symbol=best_breakout.symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=best_breakout.confidence,
            price=best_breakout.breakout_price,
            stop_loss=best_breakout.stop_loss,
            take_profit=best_breakout.target_price,
            timestamp=datetime.utcnow(),
            metadata={
                "breakout_type": best_breakout.breakout_type.value,
                "breakout_direction": best_breakout.direction,
                "breakout_price": best_breakout.breakout_price,
                "target_price": best_breakout.target_price,
                "breakout_pct": best_breakout.metadata.get("breakout_pct", 0),
                "confirmation": self.breakout_config.confirmation_method.value,
                "volume_ratio": best_breakout.volume_ratio,
                "breakout_id": f"{best_breakout.symbol}_{int(best_breakout.timestamp.timestamp())}",
            },
        )
        
        # Update stats
        self._breakout_stats["total_breakouts"] += 1
        
        self.logger.info(
            f"Breakout signal: {signal_type.value} {symbol} @ {best_breakout.breakout_price:.2f} "
            f"(confidence: {best_breakout.confidence:.2f})"
        )
        
        return signal
    
    # ========================================================================
    # PERFORMANCE UPDATE
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Called when a trade is completed.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        # Update breakout stats
        pnl = trade.pnl or 0.0
        
        if pnl > 0:
            self._breakout_stats["successful_breakouts"] += 1
            self._breakout_stats["avg_breakout_gain"] = (
                self._breakout_stats["avg_breakout_gain"] * (self._breakout_stats["successful_breakouts"] - 1) + pnl
            ) / self._breakout_stats["successful_breakouts"]
        else:
            self._breakout_stats["failed_breakouts"] += 1
            self._breakout_stats["avg_breakout_loss"] = (
                self._breakout_stats["avg_breakout_loss"] * (self._breakout_stats["failed_breakouts"] - 1) + abs(pnl)
            ) / self._breakout_stats["failed_breakouts"]
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Breakout strategy started (type: {self.breakout_config.breakout_type.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Breakout strategy stopped")
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def get_breakout_stats(self) -> Dict[str, Any]:
        """
        Get breakout statistics.
        
        Returns:
            Dict[str, Any]: Breakout statistics
        """
        return {
            **self._breakout_stats,
            "success_rate": (
                self._breakout_stats["successful_breakouts"] / max(1, self._breakout_stats["total_breakouts"]) * 100
            ),
            "avg_profit": self._breakout_stats["avg_breakout_gain"],
            "avg_loss": self._breakout_stats["avg_breakout_loss"],
        }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BreakoutType",
    "BreakoutConfirmation",
    "BreakoutConfig",
    "BreakoutLevel",
    "BreakoutSignal",
    "BreakoutStrategy",
]
