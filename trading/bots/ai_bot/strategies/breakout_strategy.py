# trading/bots/ai_bot/strategies/breakout_strategy.py
# NEXUS AI TRADING SYSTEM - Breakout Trading Strategy
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Breakout Trading Strategy for NEXUS AI Trading Bot.
Identifies and trades price breakouts using:
- Support and resistance levels
- Trendlines
- Moving averages
- Bollinger Bands
- Volume confirmation
- Volatility contraction patterns
- False breakout detection
- Retest confirmation

This strategy combines multiple breakout detection methods with
sophisticated confirmation mechanisms to identify high-probability
breakout opportunities.
"""

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
import talib

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, SignalType, SignalStrength
from trading.bots.ai_bot.strategies.risk_management import RiskManager
from trading.bots.ai_bot.execution.order_manager import OrderManager
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.breakout")


# ============================================================================
# Enums & Constants
# ============================================================================

class BreakoutType(str, Enum):
    """Types of breakouts."""
    RESISTANCE = "resistance"
    SUPPORT = "support"
    CHANNEL = "channel"
    TRIANGLE = "triangle"
    FLAG = "flag"
    PENNANT = "pennant"
    WEDGE = "wedge"
    MOVING_AVERAGE = "moving_average"
    BOLLINGER = "bollinger"
    VOLATILITY = "volatility"
    VOLUME = "volume"


class BreakoutDirection(str, Enum):
    """Breakout directions."""
    UP = "up"
    DOWN = "down"
    BOTH = "both"


class BreakoutConfidence(str, Enum):
    """Confidence levels for breakouts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class BreakoutLevel:
    """Breakout level data."""
    price: float
    direction: BreakoutDirection
    type: BreakoutType
    strength: float
    volume: float
    timestamp: datetime
    touches: int = 0
    age: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreakoutSignal:
    """Breakout signal data."""
    symbol: str
    direction: BreakoutDirection
    breakout_price: float
    target_price: float
    stop_loss: float
    volume: float
    confidence: BreakoutConfidence
    type: BreakoutType
    levels: List[BreakoutLevel]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BreakoutConfig(StrategyConfig):
    """Breakout strategy configuration."""
    lookback_periods: int = 200
    consolidation_periods: int = 20
    volume_threshold: float = 1.5
    breakout_threshold: float = 0.015
    retest_threshold: float = 0.005
    min_volume: float = 1000.0
    min_touches: int = 2
    max_age: int = 50
    use_trendlines: bool = True
    use_moving_averages: bool = True
    use_bollinger_bands: bool = True
    use_volume_analysis: bool = True
    use_false_breakout_detection: bool = True
    retest_confirmation: bool = True
    atr_multiplier_stop: float = 2.0
    target_multiplier: float = 1.5
    min_breakout_strength: float = 0.6
    max_breakout_strength: float = 0.95
    breakout_types: List[BreakoutType] = field(default_factory=lambda: list(BreakoutType))


# ============================================================================
# Breakout Strategy
# ============================================================================

class BreakoutStrategy(BaseStrategy):
    """
    Advanced Breakout Trading Strategy.
    Identifies and trades breakouts with high probability setups.
    """

    def __init__(
        self,
        config: BreakoutConfig,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        market_data_provider: Any,
    ):
        """
        Initialize breakout strategy.

        Args:
            config: Strategy configuration
            risk_manager: Risk management instance
            order_manager: Order management instance
            market_data_provider: Market data provider
        """
        super().__init__(config, risk_manager, order_manager)

        self.config = config
        self.market_data = market_data_provider

        # Data storage
        self._price_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        self._breakout_levels: Dict[str, List[BreakoutLevel]] = {}
        self._breakout_signals: Dict[str, List[BreakoutSignal]] = {}
        self._consolidation_patterns: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self._performance = {
            "breakouts_detected": 0,
            "breakouts_executed": 0,
            "breakouts_retested": 0,
            "false_breakouts": 0,
            "successful_breakouts": 0,
            "average_breakout_gain": 0.0,
            "average_breakout_loss": 0.0,
            "by_type": defaultdict(lambda: {
                "detected": 0,
                "executed": 0,
                "successful": 0,
            }),
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            "BreakoutStrategy initialized",
            extra={
                "symbols": self.config.symbols,
                "lookback": self.config.lookback_periods,
            }
        )

    # ========================================================================
    # Main Strategy Methods
    # ========================================================================

    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze market data and identify breakout opportunities.

        Returns:
            Analysis results with breakout signals
        """
        signals = []

        try:
            for symbol in self.config.symbols:
                # Get market data
                data = await self._get_market_data(symbol)

                if not data or len(data) < self.config.lookback_periods:
                    continue

                # Detect levels
                levels = await self._detect_levels(symbol, data)

                if not levels:
                    continue

                # Store levels
                self._breakout_levels[symbol] = levels

                # Detect breakouts
                breakouts = await self._detect_breakouts(symbol, data, levels)

                if breakouts:
                    # Validate and filter
                    validated = await self._validate_breakouts(symbol, breakouts, data)

                    if validated:
                        # Generate signals
                        signals.extend(await self._generate_signals(symbol, validated, data))

            # Rank and filter signals
            signals = self._rank_signals(signals)

            return {
                "signals": signals[:10],
                "total_signals": len(signals),
                "breakouts_detected": self._performance["breakouts_detected"],
                "breakout_levels": len(self._breakout_levels),
            }

        except Exception as e:
            logger.error(f"Error in breakout analysis: {e}")
            return {"signals": [], "error": str(e)}

    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """
        Execute a breakout trading signal.

        Args:
            signal: Trading signal

        Returns:
            Execution results
        """
        try:
            # Get breakout data from signal metadata
            breakout_data = signal.metadata.get("breakout", {})

            if not breakout_data:
                return {"success": False, "error": "No breakout data in signal"}

            # Check if breakout is still valid
            if not await self._validate_breakout_signal(signal.symbol, breakout_data):
                return {"success": False, "error": "Breakout no longer valid"}

            # Execute order
            order_result = await self.order_manager.place_order(
                symbol=signal.symbol,
                side="buy" if signal.type == SignalType.BUY else "sell",
                quantity=signal.quantity,
                order_type="limit",
                price=signal.price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )

            if order_result.get("success"):
                self._performance["breakouts_executed"] += 1
                self._performance["by_type"][breakout_data.get("type", "unknown")]["executed"] += 1

                return {
                    "success": True,
                    "order": order_result,
                    "breakout": breakout_data,
                }

            return order_result

        except Exception as e:
            logger.error(f"Error executing breakout signal: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Level Detection
    # ========================================================================

    async def _detect_levels(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> List[BreakoutLevel]:
        """
        Detect support and resistance levels.

        Args:
            symbol: Trading symbol
            data: Price data

        Returns:
            List of BreakoutLevel
        """
        levels = []

        try:
            # Get OHLC data
            high = data['high'].values
            low = data['low'].values
            close = data['close'].values
            volume = data['volume'].values

            # Detect resistance levels
            resistance = await self._find_resistance_levels(high, close, volume)

            for level in resistance:
                levels.append(BreakoutLevel(
                    price=level["price"],
                    direction=BreakoutDirection.UP,
                    type=BreakoutType.RESISTANCE,
                    strength=level["strength"],
                    volume=level["volume"],
                    timestamp=datetime.utcnow(),
                    touches=level["touches"],
                    age=level["age"],
                ))

            # Detect support levels
            support = await self._find_support_levels(low, close, volume)

            for level in support:
                levels.append(BreakoutLevel(
                    price=level["price"],
                    direction=BreakoutDirection.DOWN,
                    type=BreakoutType.SUPPORT,
                    strength=level["strength"],
                    volume=level["volume"],
                    timestamp=datetime.utcnow(),
                    touches=level["touches"],
                    age=level["age"],
                ))

            # Detect moving average levels
            if self.config.use_moving_averages:
                ma_levels = await self._detect_ma_levels(data)
                levels.extend(ma_levels)

            # Detect Bollinger Band levels
            if self.config.use_bollinger_bands:
                bb_levels = await self._detect_bollinger_levels(data)
                levels.extend(bb_levels)

            # Filter and sort
            levels = [l for l in levels if l.strength >= self.config.min_breakout_strength]
            levels.sort(key=lambda x: x.strength, reverse=True)

            # Limit number of levels
            return levels[:20]

        except Exception as e:
            logger.error(f"Error detecting levels for {symbol}: {e}")
            return []

    async def _find_resistance_levels(
        self,
        high: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Find resistance levels.

        Args:
            high: High prices
            close: Close prices
            volume: Volume data

        Returns:
            List of resistance levels
        """
        levels = []
        lookback = min(len(high), self.config.lookback_periods)

        # Use rolling peaks to find resistance
        for i in range(lookback, len(high)):
            window_high = high[i - lookback:i]
            current_high = high[i]

            # Check if current high is a peak
            if current_high == np.max(window_high) and i > 0:
                # Check if this level has been tested before
                touches = 1
                for j in range(i - lookback, i - 1):
                    if abs(high[j] - current_high) / current_high < 0.01:
                        touches += 1

                if touches >= self.config.min_touches:
                    # Calculate strength
                    strength = min(touches / 5, 1.0) * 0.5 + 0.5

                    # Calculate volume confirmation
                    vol_confirm = volume[i] / np.mean(volume[max(0, i - 20):i])
                    strength *= min(vol_confirm / self.config.volume_threshold, 1.0)

                    levels.append({
                        "price": current_high,
                        "strength": strength,
                        "volume": volume[i],
                        "touches": touches,
                        "age": i,
                    })

        # Consolidate nearby levels
        consolidated = self._consolidate_levels(levels, threshold=0.01)
        return consolidated

    async def _find_support_levels(
        self,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[Dict[str, Any]]:
        """
        Find support levels.

        Args:
            low: Low prices
            close: Close prices
            volume: Volume data

        Returns:
            List of support levels
        """
        # Similar to resistance but using lows
        levels = []
        lookback = min(len(low), self.config.lookback_periods)

        for i in range(lookback, len(low)):
            window_low = low[i - lookback:i]
            current_low = low[i]

            if current_low == np.min(window_low) and i > 0:
                touches = 1
                for j in range(i - lookback, i - 1):
                    if abs(low[j] - current_low) / current_low < 0.01:
                        touches += 1

                if touches >= self.config.min_touches:
                    strength = min(touches / 5, 1.0) * 0.5 + 0.5
                    vol_confirm = volume[i] / np.mean(volume[max(0, i - 20):i])
                    strength *= min(vol_confirm / self.config.volume_threshold, 1.0)

                    levels.append({
                        "price": current_low,
                        "strength": strength,
                        "volume": volume[i],
                        "touches": touches,
                        "age": i,
                    })

        consolidated = self._consolidate_levels(levels, threshold=0.01)
        return consolidated

    def _consolidate_levels(
        self,
        levels: List[Dict[str, Any]],
        threshold: float = 0.01,
    ) -> List[Dict[str, Any]]:
        """
        Consolidate nearby levels.

        Args:
            levels: List of levels
            threshold: Price threshold percentage

        Returns:
            Consolidated levels
        """
        if not levels:
            return []

        # Sort by price
        sorted_levels = sorted(levels, key=lambda x: x["price"])

        consolidated = []
        current_group = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            last_price = current_group[-1]["price"]

            if abs(level["price"] - last_price) / last_price < threshold:
                current_group.append(level)
            else:
                # Average the group
                avg_price = sum(l["price"] for l in current_group) / len(current_group)
                avg_strength = sum(l["strength"] for l in current_group) / len(current_group)
                max_touches = max(l["touches"] for l in current_group)

                consolidated.append({
                    "price": avg_price,
                    "strength": avg_strength,
                    "volume": current_group[-1]["volume"],
                    "touches": max_touches,
                    "age": current_group[-1]["age"],
                })

                current_group = [level]

        # Handle last group
        if current_group:
            avg_price = sum(l["price"] for l in current_group) / len(current_group)
            avg_strength = sum(l["strength"] for l in current_group) / len(current_group)
            max_touches = max(l["touches"] for l in current_group)

            consolidated.append({
                "price": avg_price,
                "strength": avg_strength,
                "volume": current_group[-1]["volume"],
                "touches": max_touches,
                "age": current_group[-1]["age"],
            })

        return consolidated

    async def _detect_ma_levels(self, data: pd.DataFrame) -> List[BreakoutLevel]:
        """
        Detect moving average levels.

        Args:
            data: Price data

        Returns:
            List of BreakoutLevel
        """
        levels = []
        close = data['close'].values
        volume = data['volume'].values

        # Common moving averages
        ma_periods = [20, 50, 100, 200]

        for period in ma_periods:
            if len(close) < period:
                continue

            ma = talib.SMA(close, timeperiod=period)

            for i in range(period, len(ma)):
                if ma[i] > 0:
                    # Check if price is near MA
                    price_ratio = close[i] / ma[i]

                    if 0.98 <= price_ratio <= 1.02:
                        # MA level
                        levels.append(BreakoutLevel(
                            price=ma[i],
                            direction=BreakoutDirection.BOTH,
                            type=BreakoutType.MOVING_AVERAGE,
                            strength=0.5 + (period / 400) * 0.5,
                            volume=volume[i],
                            timestamp=datetime.utcnow(),
                            touches=0,
                            age=i,
                            metadata={"period": period},
                        ))

        return levels

    async def _detect_bollinger_levels(self, data: pd.DataFrame) -> List[BreakoutLevel]:
        """
        Detect Bollinger Band levels.

        Args:
            data: Price data

        Returns:
            List of BreakoutLevel
        """
        levels = []
        close = data['close'].values
        volume = data['volume'].values

        # Calculate Bollinger Bands
        if len(close) < 20:
            return levels

        upper, middle, lower = talib.BBANDS(
            close,
            timeperiod=20,
            nbdevup=2,
            nbdevdn=2,
            matype=0,
        )

        for i in range(20, len(close)):
            if upper[i] > 0:
                # Upper band resistance
                if close[i] >= upper[i] * 0.98:
                    levels.append(BreakoutLevel(
                        price=upper[i],
                        direction=BreakoutDirection.UP,
                        type=BreakoutType.BOLLINGER,
                        strength=0.7,
                        volume=volume[i],
                        timestamp=datetime.utcnow(),
                        age=i,
                        metadata={"band": "upper"},
                    ))

                # Lower band support
                if close[i] <= lower[i] * 1.02:
                    levels.append(BreakoutLevel(
                        price=lower[i],
                        direction=BreakoutDirection.DOWN,
                        type=BreakoutType.BOLLINGER,
                        strength=0.7,
                        volume=volume[i],
                        timestamp=datetime.utcnow(),
                        age=i,
                        metadata={"band": "lower"},
                    ))

        return levels

    # ========================================================================
    # Breakout Detection
    # ========================================================================

    async def _detect_breakouts(
        self,
        symbol: str,
        data: pd.DataFrame,
        levels: List[BreakoutLevel],
    ) -> List[BreakoutSignal]:
        """
        Detect breakouts from levels.

        Args:
            symbol: Trading symbol
            data: Price data
            levels: List of levels

        Returns:
            List of BreakoutSignal
        """
        breakouts = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values
            volume = data['volume'].values

            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            for level in levels:
                # Check breakout conditions
                if level.direction == BreakoutDirection.UP:
                    if current_price > level.price * (1 + self.config.breakout_threshold):
                        breakout = await self._create_breakout_signal(
                            symbol,
                            BreakoutDirection.UP,
                            level,
                            current_price,
                            current_volume,
                            avg_volume,
                            data,
                        )
                        if breakout:
                            breakouts.append(breakout)

                elif level.direction == BreakoutDirection.DOWN:
                    if current_price < level.price * (1 - self.config.breakout_threshold):
                        breakout = await self._create_breakout_signal(
                            symbol,
                            BreakoutDirection.DOWN,
                            level,
                            current_price,
                            current_volume,
                            avg_volume,
                            data,
                        )
                        if breakout:
                            breakouts.append(breakout)

            return breakouts

        except Exception as e:
            logger.error(f"Error detecting breakouts for {symbol}: {e}")
            return []

    async def _create_breakout_signal(
        self,
        symbol: str,
        direction: BreakoutDirection,
        level: BreakoutLevel,
        current_price: float,
        current_volume: float,
        avg_volume: float,
        data: pd.DataFrame,
    ) -> Optional[BreakoutSignal]:
        """
        Create breakout signal.

        Args:
            symbol: Trading symbol
            direction: Breakout direction
            level: Breakout level
            current_price: Current price
            current_volume: Current volume
            avg_volume: Average volume
            data: Price data

        Returns:
            BreakoutSignal or None
        """
        try:
            # Calculate breakout strength
            price_strength = await self._calculate_breakout_strength(
                level.price,
                current_price,
                direction,
                data,
            )

            if price_strength < self.config.min_breakout_strength:
                return None

            # Volume confirmation
            volume_ratio = current_volume / avg_volume

            if self.config.use_volume_analysis and volume_ratio < self.config.volume_threshold:
                return None

            # Calculate targets
            atr = talib.ATR(
                data['high'].values,
                data['low'].values,
                data['close'].values,
                timeperiod=14,
            )[-1]

            if direction == BreakoutDirection.UP:
                stop_loss = level.price * (1 - self.config.atr_multiplier_stop * atr / level.price)
                target = current_price + (current_price - level.price) * self.config.target_multiplier
            else:
                stop_loss = level.price * (1 + self.config.atr_multiplier_stop * atr / level.price)
                target = current_price - (level.price - current_price) * self.config.target_multiplier

            # Calculate confidence
            confidence = await self._calculate_confidence(
                price_strength,
                volume_ratio,
                level.strength,
                data,
            )

            # Create signal
            signal = BreakoutSignal(
                symbol=symbol,
                direction=direction,
                breakout_price=current_price,
                target_price=target,
                stop_loss=stop_loss,
                volume=current_volume,
                confidence=confidence,
                type=level.type,
                levels=[level],
                metadata={
                    "price_strength": price_strength,
                    "volume_ratio": volume_ratio,
                    "atr": atr,
                    "level_price": level.price,
                    "level_strength": level.strength,
                },
            )

            self._performance["breakouts_detected"] += 1
            self._performance["by_type"][level.type.value]["detected"] += 1

            return signal

        except Exception as e:
            logger.error(f"Error creating breakout signal: {e}")
            return None

    async def _calculate_breakout_strength(
        self,
        level_price: float,
        current_price: float,
        direction: BreakoutDirection,
        data: pd.DataFrame,
    ) -> float:
        """
        Calculate breakout strength.

        Args:
            level_price: Level price
            current_price: Current price
            direction: Breakout direction
            data: Price data

        Returns:
            Breakout strength (0-1)
        """
        strength = 0.0

        # Momentum strength (40%)
        momentum = await self._calculate_momentum_strength(data)
        strength += momentum * 0.4

        # Price action strength (30%)
        price_action = await self._calculate_price_action_strength(
            level_price,
            current_price,
            direction,
            data,
        )
        strength += price_action * 0.3

        # Consolidation strength (20%)
        consolidation = await self._calculate_consolidation_strength(data)
        strength += consolidation * 0.2

        # Historical performance (10%)
        historical = await self._calculate_historical_strength(
            level_price,
            direction,
            data,
        )
        strength += historical * 0.1

        return min(strength, 1.0)

    async def _calculate_momentum_strength(self, data: pd.DataFrame) -> float:
        """
        Calculate momentum strength.

        Args:
            data: Price data

        Returns:
            Momentum strength (0-1)
        """
        close = data['close'].values

        # Calculate RSI
        rsi = talib.RSI(close, timeperiod=14)

        if len(rsi) > 0 and rsi[-1] is not None:
            # RSI strength
            if rsi[-1] > 70:
                return 0.8
            elif rsi[-1] > 60:
                return 0.6
            elif rsi[-1] > 50:
                return 0.4
            else:
                return 0.2

        # Calculate MACD
        macd, signal, hist = talib.MACD(close)

        if len(macd) > 0 and macd[-1] is not None:
            if macd[-1] > signal[-1] and hist[-1] > 0:
                return 0.7
            elif macd[-1] > signal[-1]:
                return 0.5

        return 0.3

    async def _calculate_price_action_strength(
        self,
        level_price: float,
        current_price: float,
        direction: BreakoutDirection,
        data: pd.DataFrame,
    ) -> float:
        """
        Calculate price action strength.

        Args:
            level_price: Level price
            current_price: Current price
            direction: Breakout direction
            data: Price data

        Returns:
            Price action strength (0-1)
        """
        close = data['close'].values
        high = data['high'].values
        low = data['low'].values

        # Look for candles confirming breakout
        candles = []

        for i in range(-10, 0):
            if direction == BreakoutDirection.UP:
                if close[i] > level_price and close[i] > high[i-1]:
                    candles.append(1)
            else:
                if close[i] < level_price and close[i] < low[i-1]:
                    candles.append(1)

        if not candles:
            return 0.2

        strength = min(len(candles) / 5, 1.0) * 0.8 + 0.2
        return strength

    async def _calculate_consolidation_strength(self, data: pd.DataFrame) -> float:
        """
        Calculate consolidation strength.

        Args:
            data: Price data

        Returns:
            Consolidation strength (0-1)
        """
        close = data['close'].values

        # Calculate Bollinger Band width
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)

        if len(upper) > 0 and upper[-1] is not None:
            bb_width = (upper[-1] - lower[-1]) / middle[-1]

            # Narrow bands = consolidation
            if bb_width < 0.05:
                return 0.8
            elif bb_width < 0.10:
                return 0.6
            elif bb_width < 0.15:
                return 0.4
            else:
                return 0.2

        return 0.3

    async def _calculate_historical_strength(
        self,
        level_price: float,
        direction: BreakoutDirection,
        data: pd.DataFrame,
    ) -> float:
        """
        Calculate historical breakout strength.

        Args:
            level_price: Level price
            direction: Breakout direction
            data: Price data

        Returns:
            Historical strength (0-1)
        """
        # Would analyze historical breakouts at this level
        return 0.5

    async def _calculate_confidence(
        self,
        price_strength: float,
        volume_ratio: float,
        level_strength: float,
        data: pd.DataFrame,
    ) -> BreakoutConfidence:
        """
        Calculate breakout confidence.

        Args:
            price_strength: Price strength
            volume_ratio: Volume ratio
            level_strength: Level strength
            data: Price data

        Returns:
            BreakoutConfidence
        """
        confidence_score = (
            price_strength * 0.4 +
            min(volume_ratio / 3, 1.0) * 0.3 +
            level_strength * 0.3
        )

        if confidence_score >= 0.8:
            return BreakoutConfidence.VERY_HIGH
        elif confidence_score >= 0.65:
            return BreakoutConfidence.HIGH
        elif confidence_score >= 0.5:
            return BreakoutConfidence.MEDIUM
        else:
            return BreakoutConfidence.LOW

    # ========================================================================
    # Signal Validation
    # ========================================================================

    async def _validate_breakouts(
        self,
        symbol: str,
        breakouts: List[BreakoutSignal],
        data: pd.DataFrame,
    ) -> List[BreakoutSignal]:
        """
        Validate breakout signals.

        Args:
            symbol: Trading symbol
            breakouts: List of BreakoutSignal
            data: Price data

        Returns:
            Validated breakout signals
        """
        validated = []

        for breakout in breakouts:
            # Check volume
            if breakout.volume < self.config.min_volume:
                continue

            # Check for false breakout
            if self.config.use_false_breakout_detection:
                if await self._is_false_breakout(breakout, data):
                    self._performance["false_breakouts"] += 1
                    continue

            # Check retest confirmation
            if self.config.retest_confirmation:
                if not await self._is_retested(breakout, data):
                    continue

            validated.append(breakout)

        return validated

    async def _is_false_breakout(
        self,
        breakout: BreakoutSignal,
        data: pd.DataFrame,
    ) -> bool:
        """
        Detect false breakout.

        Args:
            breakout: Breakout signal
            data: Price data

        Returns:
            True if false breakout
        """
        close = data['close'].values

        # Check if breakout is near key levels
        if len(close) < 2:
            return False

        # Check if price quickly returns
        if breakout.direction == BreakoutDirection.UP:
            # Check if price closed back below level
            if close[-1] < breakout.breakout_price * 0.99:
                return True
        else:
            if close[-1] > breakout.breakout_price * 1.01:
                return True

        return False

    async def _is_retested(
        self,
        breakout: BreakoutSignal,
        data: pd.DataFrame,
    ) -> bool:
        """
        Check if breakout has been retested.

        Args:
            breakout: Breakout signal
            data: Price data

        Returns:
            True if retested
        """
        close = data['close'].values

        if len(close) < 5:
            return False

        # Check for retest in last 5 candles
        for i in range(-5, 0):
            if breakout.direction == BreakoutDirection.UP:
                if close[i] <= breakout.breakout_price * (1 + self.config.retest_threshold):
                    self._performance["breakouts_retested"] += 1
                    return True
            else:
                if close[i] >= breakout.breakout_price * (1 - self.config.retest_threshold):
                    self._performance["breakouts_retested"] += 1
                    return True

        return False

    async def _validate_breakout_signal(
        self,
        symbol: str,
        breakout_data: Dict[str, Any],
    ) -> bool:
        """
        Validate breakout signal for execution.

        Args:
            symbol: Trading symbol
            breakout_data: Breakout data

        Returns:
            True if valid
        """
        try:
            # Get latest price
            ticker = await self.market_data.get_ticker(symbol)
            current_price = ticker.get('last', 0)

            if current_price <= 0:
                return False

            # Check if still above/below breakout level
            breakout_price = breakout_data.get('breakout_price', 0)

            if breakout_data.get('direction') == 'up':
                if current_price < breakout_price * 0.98:
                    return False
            else:
                if current_price > breakout_price * 1.02:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating breakout signal: {e}")
            return False

    # ========================================================================
    # Signal Generation
    # ========================================================================

    async def _generate_signals(
        self,
        symbol: str,
        breakouts: List[BreakoutSignal],
        data: pd.DataFrame,
    ) -> List[Signal]:
        """
        Generate trading signals from breakouts.

        Args:
            symbol: Trading symbol
            breakouts: Breakout signals
            data: Price data

        Returns:
            List of Signal
        """
        signals = []

        for breakout in breakouts:
            # Determine signal type
            if breakout.direction == BreakoutDirection.UP:
                signal_type = SignalType.BUY
                signal_strength = await self._get_signal_strength(breakout)
            else:
                signal_type = SignalType.SELL
                signal_strength = await self._get_signal_strength(breakout)

            # Calculate position size
            position_size = self._calculate_position_size(breakout.breakout_price)

            # Create signal
            signal = Signal(
                symbol=symbol,
                type=signal_type,
                strength=signal_strength,
                confidence=self._confidence_to_float(breakout.confidence),
                price=breakout.breakout_price,
                quantity=position_size,
                stop_loss=breakout.stop_loss,
                take_profit=breakout.target_price,
                reason=f"Breakout {breakout.direction.value} detected at {breakout.type.value} level",
                timestamp=datetime.utcnow(),
                expiry_time=datetime.utcnow() + timedelta(minutes=5),
                metadata={
                    "breakout": {
                        "direction": breakout.direction.value,
                        "type": breakout.type.value,
                        "breakout_price": breakout.breakout_price,
                        "target_price": breakout.target_price,
                        "stop_loss": breakout.stop_loss,
                        "confidence": breakout.confidence.value,
                        "volume": breakout.volume,
                        "level_strength": breakout.metadata.get("level_strength", 0),
                        "price_strength": breakout.metadata.get("price_strength", 0),
                        "volume_ratio": breakout.metadata.get("volume_ratio", 0),
                    }
                },
            )

            signals.append(signal)

        return signals

    async def _get_signal_strength(self, breakout: BreakoutSignal) -> SignalStrength:
        """
        Get signal strength from breakout confidence.

        Args:
            breakout: Breakout signal

        Returns:
            SignalStrength
        """
        mapping = {
            BreakoutConfidence.VERY_HIGH: SignalStrength.VERY_STRONG,
            BreakoutConfidence.HIGH: SignalStrength.STRONG,
            BreakoutConfidence.MEDIUM: SignalStrength.MODERATE,
            BreakoutConfidence.LOW: SignalStrength.WEAK,
        }
        return mapping.get(breakout.confidence, SignalStrength.WEAK)

    def _confidence_to_float(self, confidence: BreakoutConfidence) -> float:
        """
        Convert confidence to float.

        Args:
            confidence: BreakoutConfidence

        Returns:
            Confidence float (0-1)
        """
        mapping = {
            BreakoutConfidence.VERY_HIGH: 0.9,
            BreakoutConfidence.HIGH: 0.75,
            BreakoutConfidence.MEDIUM: 0.6,
            BreakoutConfidence.LOW: 0.4,
        }
        return mapping.get(confidence, 0.5)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _rank_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        Rank signals by confidence.

        Args:
            signals: List of signals

        Returns:
            Ranked signals
        """
        return sorted(signals, key=lambda x: x.confidence, reverse=True)

    def _calculate_position_size(self, price: float) -> float:
        """
        Calculate position size.

        Args:
            price: Entry price

        Returns:
            Position size
        """
        risk_amount = self.config.initial_capital * self.config.risk_per_trade
        stop_loss_amount = price * self.config.stop_loss_percent

        if stop_loss_amount > 0:
            return risk_amount / stop_loss_amount

        return self.config.max_position_size

    async def _get_market_data(self, symbol: str) -> pd.DataFrame:
        """
        Get market data for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            DataFrame with price data
        """
        # Would get from market data provider
        # This is a placeholder
        return pd.DataFrame()

    # ========================================================================
    # Performance Management
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "breakout_success_rate": (
                self._performance["successful_breakouts"] /
                max(self._performance["breakouts_executed"], 1)
            ),
            "false_breakout_rate": (
                self._performance["false_breakouts"] /
                max(self._performance["breakouts_detected"], 1)
            ),
            "by_type": dict(self._performance["by_type"]),
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy."""
        if self._running:
            return

        self._running = True
        logger.info("BreakoutStrategy started")

    async def stop(self) -> None:
        """Stop the strategy."""
        self._running = False

        # Clean up
        async with self._lock:
            self._breakout_levels.clear()
            self._breakout_signals.clear()

        logger.info("BreakoutStrategy stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_breakout_strategy(
    config: BreakoutConfig,
    risk_manager: RiskManager,
    order_manager: OrderManager,
    market_data_provider: Any,
) -> BreakoutStrategy:
    """
    Factory function to create a BreakoutStrategy instance.

    Args:
        config: Strategy configuration
        risk_manager: Risk management instance
        order_manager: Order management instance
        market_data_provider: Market data provider

    Returns:
        BreakoutStrategy instance
    """
    return BreakoutStrategy(
        config=config,
        risk_manager=risk_manager,
        order_manager=order_manager,
        market_data_provider=market_data_provider,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the breakout strategy
    pass
