# trading/bots/ai_bot/strategies/momentum_strategy.py
# NEXUS AI TRADING SYSTEM - Momentum Trading Strategy
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Momentum Trading Strategy for NEXUS AI Trading Bot.
Identifies and trades momentum opportunities using:
- Price momentum indicators (ROC, RSI, MACD)
- Volume momentum (OBV, Money Flow Index)
- Breakout momentum
- Trend strength (ADX)
- Multi-timeframe momentum
- Divergence detection
- Momentum oscillator combinations
- Adaptive momentum parameters
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

logger = get_logger("nexus.trading.strategy.momentum")


# ============================================================================
# Enums & Constants
# ============================================================================

class MomentumType(str, Enum):
    """Types of momentum."""
    PRICE = "price"
    VOLUME = "volume"
    BREAKOUT = "breakout"
    OSCILLATOR = "oscillator"
    DIVERGENCE = "divergence"
    MULTI_TIMEFRAME = "multi_timeframe"
    ADAPTIVE = "adaptive"
    RELATIVE = "relative"


class MomentumDirection(str, Enum):
    """Momentum directions."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    STRONG_BULLISH = "strong_bullish"
    STRONG_BEARISH = "strong_bearish"


class DivergenceType(str, Enum):
    """Divergence types."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    HIDDEN_BULLISH = "hidden_bullish"
    HIDDEN_BEARISH = "hidden_bearish"


@dataclass
class MomentumSignal:
    """Momentum signal data."""
    symbol: str
    type: MomentumType
    direction: MomentumDirection
    strength: float
    price: float
    momentum_value: float
    volume: float
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    timeframe: str
    timestamp: datetime
    divergence: Optional[DivergenceType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MomentumConfig(StrategyConfig):
    """Momentum strategy configuration."""
    # Momentum indicators
    roc_period: int = 14
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    adx_period: int = 14
    obv_period: int = 20
    mfi_period: int = 14

    # Momentum thresholds
    momentum_threshold: float = 0.5
    strong_momentum_threshold: float = 1.0
    divergence_threshold: float = 0.3
    adx_threshold: float = 25

    # Volume momentum
    volume_momentum_threshold: float = 1.2
    volume_breakout_threshold: float = 1.5

    # Configuration
    use_volume_momentum: bool = True
    use_divergence_detection: bool = True
    use_multi_timeframe: bool = True
    use_adaptive_momentum: bool = True
    lookback_periods: int = 100
    min_confidence: float = 0.6
    position_size_multiplier: float = 1.0
    momentum_reversal_threshold: float = 0.2

    # Exit parameters
    trailing_stop: bool = True
    trailing_stop_activation: float = 0.3
    take_profit_multiplier: float = 2.0
    stop_loss_multiplier: float = 1.5


# ============================================================================
# Momentum Strategy
# ============================================================================

class MomentumStrategy(BaseStrategy):
    """
    Advanced Momentum Trading Strategy.
    Identifies and trades momentum opportunities across multiple indicators.
    """

    def __init__(
        self,
        config: MomentumConfig,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        market_data_provider: Any,
    ):
        """
        Initialize momentum strategy.

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
        self._momentum_signals: Dict[str, List[MomentumSignal]] = {}
        self._divergence_history: Dict[str, List[Dict[str, Any]]] = {}
        self._adaptive_parameters: Dict[str, Dict[str, float]] = {}

        # Performance metrics
        self._performance = {
            "signals_detected": 0,
            "signals_executed": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "average_momentum_gain": 0.0,
            "average_momentum_loss": 0.0,
            "by_type": defaultdict(lambda: {
                "detected": 0,
                "executed": 0,
                "successful": 0,
            }),
            "by_direction": defaultdict(lambda: {
                "detected": 0,
                "executed": 0,
                "successful": 0,
            }),
            "divergence_signals": 0,
            "divergence_success": 0,
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            "MomentumStrategy initialized",
            extra={
                "symbols": self.config.symbols,
                "roc_period": self.config.roc_period,
                "rsi_period": self.config.rsi_period,
            }
        )

    # ========================================================================
    # Main Strategy Methods
    # ========================================================================

    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze market data and identify momentum opportunities.

        Returns:
            Analysis results with momentum signals
        """
        signals = []

        try:
            for symbol in self.config.symbols:
                # Get market data
                data = await self._get_market_data(symbol)

                if data is None or len(data) < self.config.lookback_periods:
                    continue

                # Update price history
                self._update_price_history(symbol, data)

                # Update adaptive parameters
                if self.config.use_adaptive_momentum:
                    await self._update_adaptive_parameters(symbol, data)

                # Detect momentum signals
                momentum_signals = await self._detect_momentum(symbol, data)

                if momentum_signals:
                    # Validate signals
                    validated = await self._validate_signals(symbol, momentum_signals, data)

                    if validated:
                        # Generate trading signals
                        signals.extend(await self._generate_signals(symbol, validated, data))

            # Rank signals
            signals = self._rank_signals(signals)

            return {
                "signals": signals[:10],
                "total_signals": len(signals),
                "momentum_signals_detected": self._performance["signals_detected"],
                "divergence_detected": self._performance["divergence_signals"],
            }

        except Exception as e:
            logger.error(f"Error in momentum analysis: {e}")
            return {"signals": [], "error": str(e)}

    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """
        Execute a momentum trading signal.

        Args:
            signal: Trading signal

        Returns:
            Execution results
        """
        try:
            # Get momentum data from signal metadata
            momentum_data = signal.metadata.get("momentum", {})

            if not momentum_data:
                return {"success": False, "error": "No momentum data in signal"}

            # Check if signal is still valid
            if not await self._validate_signal_execution(signal.symbol, momentum_data):
                return {"success": False, "error": "Signal no longer valid"}

            # Calculate position size with momentum adjustment
            position_size = await self._calculate_momentum_position_size(
                signal.symbol,
                signal.price,
                momentum_data,
            )

            # Execute order
            order_result = await self.order_manager.place_order(
                symbol=signal.symbol,
                side="buy" if signal.type == SignalType.BUY else "sell",
                quantity=position_size,
                order_type="limit",
                price=signal.price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )

            if order_result.get("success"):
                self._performance["signals_executed"] += 1
                self._performance["by_type"][momentum_data.get("type", "unknown")]["executed"] += 1
                self._performance["by_direction"][momentum_data.get("direction", "neutral")]["executed"] += 1

                return {
                    "success": True,
                    "order": order_result,
                    "momentum": momentum_data,
                }

            return order_result

        except Exception as e:
            logger.error(f"Error executing momentum signal: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Momentum Detection Methods
    # ========================================================================

    async def _detect_momentum(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> List[MomentumSignal]:
        """
        Detect momentum signals.

        Args:
            symbol: Trading symbol
            data: Price data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values
            volume = data['volume'].values

            # Get adaptive parameters
            params = self._adaptive_parameters.get(symbol, {})
            roc_period = params.get("roc_period", self.config.roc_period)
            rsi_period = params.get("rsi_period", self.config.rsi_period)

            # Price momentum (ROC)
            roc_signals = await self._detect_roc_momentum(symbol, close, roc_period, volume)

            if roc_signals:
                signals.extend(roc_signals)

            # RSI momentum
            rsi_signals = await self._detect_rsi_momentum(symbol, close, rsi_period, volume)

            if rsi_signals:
                signals.extend(rsi_signals)

            # MACD momentum
            macd_signals = await self._detect_macd_momentum(symbol, close, volume)

            if macd_signals:
                signals.extend(macd_signals)

            # ADX trend strength
            adx_signals = await self._detect_adx_momentum(symbol, high, low, close, volume)

            if adx_signals:
                signals.extend(adx_signals)

            # Volume momentum
            if self.config.use_volume_momentum:
                volume_signals = await self._detect_volume_momentum(symbol, close, volume)

                if volume_signals:
                    signals.extend(volume_signals)

            # Divergence detection
            if self.config.use_divergence_detection:
                divergence_signals = await self._detect_divergence(symbol, close, volume)

                if divergence_signals:
                    signals.extend(divergence_signals)

            # Multi-timeframe confirmation
            if self.config.use_multi_timeframe:
                signals = await self._apply_multi_timeframe_confirmation(symbol, signals)

            return signals

        except Exception as e:
            logger.error(f"Error detecting momentum for {symbol}: {e}")
            return []

    # ========================================================================
    # ROC Momentum
    # ========================================================================

    async def _detect_roc_momentum(
        self,
        symbol: str,
        close: np.ndarray,
        period: int,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect ROC momentum signals.

        Args:
            symbol: Trading symbol
            close: Close prices
            period: ROC period
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(close) < period:
                return signals

            # Calculate ROC
            roc = talib.ROC(close, timeperiod=period)

            if roc[-1] is None:
                return signals

            current_roc = roc[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Check momentum direction and strength
            momentum_strength = abs(current_roc) / 100

            if momentum_strength > self.config.momentum_threshold:
                # Determine direction
                if current_roc > 0:
                    direction = MomentumDirection.BULLISH
                    if momentum_strength > self.config.strong_momentum_threshold:
                        direction = MomentumDirection.STRONG_BULLISH
                else:
                    direction = MomentumDirection.BEARISH
                    if momentum_strength > self.config.strong_momentum_threshold:
                        direction = MomentumDirection.STRONG_BEARISH

                # Calculate confidence
                confidence = min(momentum_strength / self.config.strong_momentum_threshold, 1.0)

                # Volume confirmation
                volume_confirm = current_volume > avg_volume * 1.1

                # Calculate target and stop loss
                price_change = current_price * abs(current_roc) / 100
                if direction in [MomentumDirection.BULLISH, MomentumDirection.STRONG_BULLISH]:
                    target_price = current_price + price_change * self.config.take_profit_multiplier
                    stop_loss = current_price - price_change * self.config.stop_loss_multiplier
                else:
                    target_price = current_price - price_change * self.config.take_profit_multiplier
                    stop_loss = current_price + price_change * self.config.stop_loss_multiplier

                signal = MomentumSignal(
                    symbol=symbol,
                    type=MomentumType.PRICE,
                    direction=direction,
                    strength=momentum_strength,
                    price=current_price,
                    momentum_value=current_roc,
                    volume=current_volume,
                    confidence=confidence,
                    entry_price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    timeframe=self.config.timeframe,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "roc": current_roc,
                        "volume_confirm": volume_confirm,
                        "momentum_strength": momentum_strength,
                    },
                )

                signals.append(signal)
                self._performance["signals_detected"] += 1
                self._performance["by_type"][MomentumType.PRICE.value]["detected"] += 1
                self._performance["by_direction"][direction.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting ROC momentum: {e}")
            return []

    # ========================================================================
    # RSI Momentum
    # ========================================================================

    async def _detect_rsi_momentum(
        self,
        symbol: str,
        close: np.ndarray,
        period: int,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect RSI momentum signals.

        Args:
            symbol: Trading symbol
            close: Close prices
            period: RSI period
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(close) < period:
                return signals

            # Calculate RSI
            rsi = talib.RSI(close, timeperiod=period)

            if rsi[-1] is None:
                return signals

            current_rsi = rsi[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # RSI momentum zones
            if current_rsi > 70:
                # Overbought - potential bearish momentum reversal
                rsi_strength = (current_rsi - 70) / 30
                direction = MomentumDirection.BEARISH
                confidence = min(rsi_strength, 1.0)

            elif current_rsi < 30:
                # Oversold - potential bullish momentum reversal
                rsi_strength = (30 - current_rsi) / 30
                direction = MomentumDirection.BULLISH
                confidence = min(rsi_strength, 1.0)

            else:
                # Neutral zone - check for momentum
                rsi_diff = current_rsi - 50
                if abs(rsi_diff) > 10:
                    direction = MomentumDirection.BULLISH if rsi_diff > 0 else MomentumDirection.BEARISH
                    confidence = abs(rsi_diff) / 20
                else:
                    return signals

            if confidence >= self.config.min_confidence:
                # Volume confirmation
                volume_confirm = current_volume > avg_volume * 0.9

                # Calculate targets
                price_std = np.std(close[-20:])
                if direction in [MomentumDirection.BULLISH, MomentumDirection.STRONG_BULLISH]:
                    target_price = current_price + price_std * 1.5
                    stop_loss = current_price - price_std * 1.0
                else:
                    target_price = current_price - price_std * 1.5
                    stop_loss = current_price + price_std * 1.0

                signal = MomentumSignal(
                    symbol=symbol,
                    type=MomentumType.OSCILLATOR,
                    direction=direction,
                    strength=confidence,
                    price=current_price,
                    momentum_value=current_rsi,
                    volume=current_volume,
                    confidence=confidence,
                    entry_price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    timeframe=self.config.timeframe,
                    timestamp=datetime.utcnow(),
                    metadata={
                        "rsi": current_rsi,
                        "volume_confirm": volume_confirm,
                        "price_std": price_std,
                    },
                )

                signals.append(signal)
                self._performance["signals_detected"] += 1
                self._performance["by_type"][MomentumType.OSCILLATOR.value]["detected"] += 1
                self._performance["by_direction"][direction.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting RSI momentum: {e}")
            return []

    # ========================================================================
    # MACD Momentum
    # ========================================================================

    async def _detect_macd_momentum(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect MACD momentum signals.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(close) < self.config.macd_slow:
                return signals

            # Calculate MACD
            macd, signal, hist = talib.MACD(
                close,
                fastperiod=self.config.macd_fast,
                slowperiod=self.config.macd_slow,
                signalperiod=self.config.macd_signal,
            )

            if macd[-1] is None or signal[-1] is None or hist[-1] is None:
                return signals

            current_macd = macd[-1]
            current_signal = signal[-1]
            current_hist = hist[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Check for momentum signals
            if current_macd > current_signal and current_hist > 0:
                # Bullish momentum
                momentum_strength = abs(current_hist) / (abs(current_macd) + 0.001)
                confidence = min(momentum_strength * 2, 1.0)

                if confidence >= self.config.min_confidence:
                    direction = MomentumDirection.BULLISH
                    if current_hist > current_hist[-2] if len(hist) > 1 else 0:
                        direction = MomentumDirection.STRONG_BULLISH

                    price_std = np.std(close[-20:])
                    target_price = current_price + price_std * 1.5
                    stop_loss = current_price - price_std * 0.8

                    signal = MomentumSignal(
                        symbol=symbol,
                        type=MomentumType.OSCILLATOR,
                        direction=direction,
                        strength=confidence,
                        price=current_price,
                        momentum_value=current_hist,
                        volume=current_volume,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "macd": current_macd,
                            "signal": current_signal,
                            "histogram": current_hist,
                            "volume_confirm": current_volume > avg_volume * 0.9,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1

            elif current_macd < current_signal and current_hist < 0:
                # Bearish momentum
                momentum_strength = abs(current_hist) / (abs(current_macd) + 0.001)
                confidence = min(momentum_strength * 2, 1.0)

                if confidence >= self.config.min_confidence:
                    direction = MomentumDirection.BEARISH
                    if current_hist < hist[-2] if len(hist) > 1 else 0:
                        direction = MomentumDirection.STRONG_BEARISH

                    price_std = np.std(close[-20:])
                    target_price = current_price - price_std * 1.5
                    stop_loss = current_price + price_std * 0.8

                    signal = MomentumSignal(
                        symbol=symbol,
                        type=MomentumType.OSCILLATOR,
                        direction=direction,
                        strength=confidence,
                        price=current_price,
                        momentum_value=current_hist,
                        volume=current_volume,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "macd": current_macd,
                            "signal": current_signal,
                            "histogram": current_hist,
                            "volume_confirm": current_volume > avg_volume * 0.9,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting MACD momentum: {e}")
            return []

    # ========================================================================
    # ADX Momentum
    # ========================================================================

    async def _detect_adx_momentum(
        self,
        symbol: str,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect ADX trend strength momentum signals.

        Args:
            symbol: Trading symbol
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(close) < self.config.adx_period:
                return signals

            # Calculate ADX
            adx = talib.ADX(high, low, close, timeperiod=self.config.adx_period)

            if adx[-1] is None:
                return signals

            current_adx = adx[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Check if trend is strong
            if current_adx > self.config.adx_threshold:
                # Determine direction using DI+/DI-
                plus_di = talib.PLUS_DI(high, low, close, timeperiod=self.config.adx_period)
                minus_di = talib.MINUS_DI(high, low, close, timeperiod=self.config.adx_period)

                if plus_di[-1] is None or minus_di[-1] is None:
                    return signals

                # Check if DI cross confirms momentum
                if plus_di[-1] > minus_di[-1] and plus_di[-1] > plus_di[-2] if len(plus_di) > 1 else True:
                    direction = MomentumDirection.BULLISH
                    confidence = min(current_adx / 50, 1.0)
                elif minus_di[-1] > plus_di[-1] and minus_di[-1] > minus_di[-2] if len(minus_di) > 1 else True:
                    direction = MomentumDirection.BEARISH
                    confidence = min(current_adx / 50, 1.0)
                else:
                    return signals

                if confidence >= self.config.min_confidence:
                    price_std = np.std(close[-20:])
                    if direction == MomentumDirection.BULLISH:
                        target_price = current_price + price_std * 1.2
                        stop_loss = current_price - price_std * 0.7
                    else:
                        target_price = current_price - price_std * 1.2
                        stop_loss = current_price + price_std * 0.7

                    signal = MomentumSignal(
                        symbol=symbol,
                        type=MomentumType.OSCILLATOR,
                        direction=direction,
                        strength=confidence,
                        price=current_price,
                        momentum_value=current_adx,
                        volume=current_volume,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "adx": current_adx,
                            "plus_di": plus_di[-1],
                            "minus_di": minus_di[-1],
                            "volume_confirm": current_volume > avg_volume * 0.9,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting ADX momentum: {e}")
            return []

    # ========================================================================
    # Volume Momentum
    # ========================================================================

    async def _detect_volume_momentum(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect volume momentum signals.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(volume) < self.config.obv_period:
                return signals

            # Calculate On-Balance Volume
            obv = talib.OBV(close, volume)

            if obv[-1] is None:
                return signals

            # Calculate OBV momentum
            obv_roc = talib.ROC(obv, timeperiod=self.config.obv_period)

            if obv_roc[-1] is None:
                return signals

            current_obv = obv[-1]
            current_obv_roc = obv_roc[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Check for volume momentum
            if abs(current_obv_roc) > self.config.volume_momentum_threshold:
                if current_obv_roc > 0:
                    direction = MomentumDirection.BULLISH
                else:
                    direction = MomentumDirection.BEARISH

                confidence = min(abs(current_obv_roc) / self.config.volume_breakout_threshold, 1.0)

                if confidence >= self.config.min_confidence:
                    # Check for price-volume divergence
                    price_roc = talib.ROC(close, timeperiod=self.config.roc_period)

                    if price_roc[-1] is not None:
                        price_divergence = abs(current_obv_roc) > abs(price_roc[-1])

                    price_std = np.std(close[-20:])
                    if direction == MomentumDirection.BULLISH:
                        target_price = current_price + price_std * 1.0
                        stop_loss = current_price - price_std * 0.6
                    else:
                        target_price = current_price - price_std * 1.0
                        stop_loss = current_price + price_std * 0.6

                    signal = MomentumSignal(
                        symbol=symbol,
                        type=MomentumType.VOLUME,
                        direction=direction,
                        strength=confidence,
                        price=current_price,
                        momentum_value=current_obv_roc,
                        volume=current_volume,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "obv": current_obv,
                            "obv_roc": current_obv_roc,
                            "price_divergence": price_divergence if price_roc[-1] is not None else False,
                            "volume_confirm": current_volume > avg_volume * 1.2,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1
                    self._performance["by_type"][MomentumType.VOLUME.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting volume momentum: {e}")
            return []

    # ========================================================================
    # Divergence Detection
    # ========================================================================

    async def _detect_divergence(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[MomentumSignal]:
        """
        Detect momentum divergence signals.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of MomentumSignal
        """
        signals = []

        try:
            if len(close) < 50:
                return signals

            # Calculate RSI for divergence
            rsi = talib.RSI(close, timeperiod=14)

            if rsi[-1] is None:
                return signals

            # Find swing highs and lows
            swing_highs = self._find_swing_highs(close, 10)
            swing_lows = self._find_swing_lows(close, 10)

            current_price = close[-1]
            current_rsi = rsi[-1]
            current_volume = volume[-1]

            # Regular bullish divergence
            if self._check_bullish_divergence(close, rsi, swing_lows):
                confidence = 0.7
                direction = MomentumDirection.BULLISH
                divergence_type = DivergenceType.BULLISH

                price_std = np.std(close[-20:])
                target_price = current_price + price_std * 1.0
                stop_loss = current_price - price_std * 0.6

                signal = self._create_divergence_signal(
                    symbol, direction, divergence_type, confidence,
                    current_price, target_price, stop_loss, current_volume,
                    "bullish_divergence", rsi[-1]
                )
                signals.append(signal)

            # Regular bearish divergence
            if self._check_bearish_divergence(close, rsi, swing_highs):
                confidence = 0.7
                direction = MomentumDirection.BEARISH
                divergence_type = DivergenceType.BEARISH

                price_std = np.std(close[-20:])
                target_price = current_price - price_std * 1.0
                stop_loss = current_price + price_std * 0.6

                signal = self._create_divergence_signal(
                    symbol, direction, divergence_type, confidence,
                    current_price, target_price, stop_loss, current_volume,
                    "bearish_divergence", rsi[-1]
                )
                signals.append(signal)

            # Hidden bullish divergence
            if self._check_hidden_bullish_divergence(close, rsi, swing_lows):
                confidence = 0.65
                direction = MomentumDirection.BULLISH
                divergence_type = DivergenceType.HIDDEN_BULLISH

                price_std = np.std(close[-20:])
                target_price = current_price + price_std * 1.2
                stop_loss = current_price - price_std * 0.5

                signal = self._create_divergence_signal(
                    symbol, direction, divergence_type, confidence,
                    current_price, target_price, stop_loss, current_volume,
                    "hidden_bullish_divergence", rsi[-1]
                )
                signals.append(signal)

            # Hidden bearish divergence
            if self._check_hidden_bearish_divergence(close, rsi, swing_highs):
                confidence = 0.65
                direction = MomentumDirection.BEARISH
                divergence_type = DivergenceType.HIDDEN_BEARISH

                price_std = np.std(close[-20:])
                target_price = current_price - price_std * 1.2
                stop_loss = current_price + price_std * 0.5

                signal = self._create_divergence_signal(
                    symbol, direction, divergence_type, confidence,
                    current_price, target_price, stop_loss, current_volume,
                    "hidden_bearish_divergence", rsi[-1]
                )
                signals.append(signal)

            if signals:
                self._performance["divergence_signals"] += len(signals)

            return signals

        except Exception as e:
            logger.error(f"Error detecting divergence: {e}")
            return []

    def _find_swing_highs(self, prices: np.ndarray, lookback: int) -> List[int]:
        """Find swing high indices."""
        highs = []
        for i in range(lookback, len(prices) - lookback):
            if prices[i] == max(prices[i - lookback:i + lookback + 1]):
                highs.append(i)
        return highs

    def _find_swing_lows(self, prices: np.ndarray, lookback: int) -> List[int]:
        """Find swing low indices."""
        lows = []
        for i in range(lookback, len(prices) - lookback):
            if prices[i] == min(prices[i - lookback:i + lookback + 1]):
                lows.append(i)
        return lows

    def _check_bullish_divergence(
        self,
        prices: np.ndarray,
        rsi: np.ndarray,
        swing_lows: List[int],
    ) -> bool:
        """Check for bullish divergence."""
        if len(swing_lows) < 2:
            return False

        low1 = swing_lows[-2]
        low2 = swing_lows[-1]

        # Price made lower low
        if prices[low2] < prices[low1]:
            # RSI made higher low
            if rsi[low2] > rsi[low1]:
                return True

        return False

    def _check_bearish_divergence(
        self,
        prices: np.ndarray,
        rsi: np.ndarray,
        swing_highs: List[int],
    ) -> bool:
        """Check for bearish divergence."""
        if len(swing_highs) < 2:
            return False

        high1 = swing_highs[-2]
        high2 = swing_highs[-1]

        # Price made higher high
        if prices[high2] > prices[high1]:
            # RSI made lower high
            if rsi[high2] < rsi[high1]:
                return True

        return False

    def _check_hidden_bullish_divergence(
        self,
        prices: np.ndarray,
        rsi: np.ndarray,
        swing_lows: List[int],
    ) -> bool:
        """Check for hidden bullish divergence."""
        if len(swing_lows) < 2:
            return False

        low1 = swing_lows[-2]
        low2 = swing_lows[-1]

        # Price made higher low
        if prices[low2] > prices[low1]:
            # RSI made lower low
            if rsi[low2] < rsi[low1]:
                return True

        return False

    def _check_hidden_bearish_divergence(
        self,
        prices: np.ndarray,
        rsi: np.ndarray,
        swing_highs: List[int],
    ) -> bool:
        """Check for hidden bearish divergence."""
        if len(swing_highs) < 2:
            return False

        high1 = swing_highs[-2]
        high2 = swing_highs[-1]

        # Price made lower high
        if prices[high2] < prices[high1]:
            # RSI made higher high
            if rsi[high2] > rsi[high1]:
                return True

        return False

    def _create_divergence_signal(
        self,
        symbol: str,
        direction: MomentumDirection,
        divergence_type: DivergenceType,
        confidence: float,
        price: float,
        target_price: float,
        stop_loss: float,
        volume: float,
        reason: str,
        rsi_value: float,
    ) -> MomentumSignal:
        """Create a divergence signal."""
        return MomentumSignal(
            symbol=symbol,
            type=MomentumType.DIVERGENCE,
            direction=direction,
            strength=confidence,
            price=price,
            momentum_value=rsi_value,
            volume=volume,
            confidence=confidence,
            entry_price=price,
            target_price=target_price,
            stop_loss=stop_loss,
            timeframe=self.config.timeframe,
            timestamp=datetime.utcnow(),
            divergence=divergence_type,
            metadata={
                "divergence_type": divergence_type.value,
                "reason": reason,
                "rsi_value": rsi_value,
            },
        )

    # ========================================================================
    # Multi-Timeframe Confirmation
    # ========================================================================

    async def _apply_multi_timeframe_confirmation(
        self,
        symbol: str,
        signals: List[MomentumSignal],
    ) -> List[MomentumSignal]:
        """
        Apply multi-timeframe confirmation to signals.

        Args:
            symbol: Trading symbol
            signals: List of signals

        Returns:
            Confirmed signals
        """
        confirmed = []

        try:
            # Get higher timeframe data
            higher_tf = {
                "15m": await self._get_market_data(symbol, "15m"),
                "1h": await self._get_market_data(symbol, "1h"),
                "4h": await self._get_market_data(symbol, "4h"),
            }

            for signal in signals:
                confirmation_count = 0

                for tf, tf_data in higher_tf.items():
                    if tf_data is None or len(tf_data) < 20:
                        continue

                    tf_close = tf_data['close'].values
                    tf_rsi = talib.RSI(tf_close, timeperiod=14)

                    if tf_rsi[-1] is None:
                        continue

                    # Check if higher timeframe confirms direction
                    if signal.direction in [MomentumDirection.BULLISH, MomentumDirection.STRONG_BULLISH]:
                        if tf_rsi[-1] > 50:
                            confirmation_count += 1
                    else:
                        if tf_rsi[-1] < 50:
                            confirmation_count += 1

                # Require at least one higher timeframe confirmation
                if confirmation_count >= 1:
                    signal.confidence = min(1.0, signal.confidence + confirmation_count * 0.05)
                    signal.metadata["multi_tf_confirmation"] = True
                    confirmed.append(signal)

            return confirmed

        except Exception as e:
            logger.error(f"Error applying multi-timeframe confirmation: {e}")
            return signals

    # ========================================================================
    # Adaptive Momentum
    # ========================================================================

    async def _update_adaptive_parameters(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> None:
        """
        Update adaptive momentum parameters.

        Args:
            symbol: Trading symbol
            data: Price data
        """
        try:
            close = data['close'].values

            if len(close) < 50:
                return

            # Calculate market volatility
            returns = np.diff(np.log(close))
            volatility = np.std(returns) * np.sqrt(252)

            # Adjust ROC period based on volatility
            if volatility > 0.3:
                roc_period = max(5, self.config.roc_period - 5)
            elif volatility < 0.15:
                roc_period = min(30, self.config.roc_period + 5)
            else:
                roc_period = self.config.roc_period

            # Adjust RSI period based on market condition
            if volatility > 0.3:
                rsi_period = max(7, self.config.rsi_period - 5)
            elif volatility < 0.15:
                rsi_period = min(21, self.config.rsi_period + 5)
            else:
                rsi_period = self.config.rsi_period

            self._adaptive_parameters[symbol] = {
                "roc_period": roc_period,
                "rsi_period": rsi_period,
                "volatility": volatility,
                "last_update": datetime.utcnow(),
            }

        except Exception as e:
            logger.error(f"Error updating adaptive parameters: {e}")

    # ========================================================================
    # Signal Validation
    # ========================================================================

    async def _validate_signals(
        self,
        symbol: str,
        signals: List[MomentumSignal],
        data: pd.DataFrame,
    ) -> List[MomentumSignal]:
        """
        Validate momentum signals.

        Args:
            symbol: Trading symbol
            signals: List of signals
            data: Price data

        Returns:
            Validated signals
        """
        validated = []

        for signal in signals:
            # Check confidence
            if signal.confidence < self.config.min_confidence:
                continue

            # Check momentum strength
            if signal.strength < self.config.momentum_threshold:
                continue

            # Check for momentum reversal
            if await self._check_momentum_reversal(signal, data):
                continue

            validated.append(signal)

        return validated

    async def _check_momentum_reversal(
        self,
        signal: MomentumSignal,
        data: pd.DataFrame,
    ) -> bool:
        """
        Check for potential momentum reversal.

        Args:
            signal: Momentum signal
            data: Price data

        Returns:
            True if reversal detected
        """
        close = data['close'].values

        if len(close) < 10:
            return False

        # Check recent price action
        recent_change = (close[-1] - close[-5]) / close[-5]

        if signal.direction in [MomentumDirection.BULLISH, MomentumDirection.STRONG_BULLISH]:
            if recent_change < -self.config.momentum_reversal_threshold:
                return True
        else:
            if recent_change > self.config.momentum_reversal_threshold:
                return True

        return False

    async def _validate_signal_execution(
        self,
        symbol: str,
        momentum_data: Dict[str, Any],
    ) -> bool:
        """
        Validate signal for execution.

        Args:
            symbol: Trading symbol
            momentum_data: Momentum data

        Returns:
            True if valid
        """
        try:
            # Get latest price
            ticker = await self.market_data.get_ticker(symbol)
            current_price = ticker.get('last', 0)

            if current_price <= 0:
                return False

            # Check momentum direction is still valid
            direction = momentum_data.get('direction', 'neutral')

            if direction in ['bullish', 'strong_bullish']:
                if current_price < momentum_data.get('entry_price', 0) * 0.98:
                    return False
            else:
                if current_price > momentum_data.get('entry_price', 0) * 1.02:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating signal execution: {e}")
            return False

    # ========================================================================
    # Signal Generation
    # ========================================================================

    async def _generate_signals(
        self,
        symbol: str,
        momentum_signals: List[MomentumSignal],
        data: pd.DataFrame,
    ) -> List[Signal]:
        """
        Generate trading signals from momentum signals.

        Args:
            symbol: Trading symbol
            momentum_signals: List of MomentumSignal
            data: Price data

        Returns:
            List of Signal
        """
        signals = []

        for momentum in momentum_signals:
            # Determine signal type
            if momentum.direction in [MomentumDirection.BULLISH, MomentumDirection.STRONG_BULLISH]:
                signal_type = SignalType.BUY
                if momentum.direction == MomentumDirection.STRONG_BULLISH:
                    signal_type = SignalType.STRONG_BUY
            else:
                signal_type = SignalType.SELL
                if momentum.direction == MomentumDirection.STRONG_BEARISH:
                    signal_type = SignalType.STRONG_SELL

            # Calculate position size
            position_size = await self._calculate_momentum_position_size(
                symbol,
                momentum.entry_price,
                momentum.__dict__,
            )

            # Determine signal strength
            if momentum.confidence > 0.8:
                strength = SignalStrength.STRONG
            elif momentum.confidence > 0.65:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = Signal(
                symbol=symbol,
                type=signal_type,
                strength=strength,
                confidence=momentum.confidence,
                price=momentum.entry_price,
                quantity=position_size,
                stop_loss=momentum.stop_loss,
                take_profit=momentum.target_price,
                reason=f"Momentum: {momentum.type.value} {momentum.direction.value}",
                timestamp=datetime.utcnow(),
                expiry_time=datetime.utcnow() + timedelta(minutes=15),
                metadata={
                    "momentum": {
                        "type": momentum.type.value,
                        "direction": momentum.direction.value,
                        "strength": momentum.strength,
                        "entry_price": momentum.entry_price,
                        "target_price": momentum.target_price,
                        "stop_loss": momentum.stop_loss,
                        "confidence": momentum.confidence,
                        "momentum_value": momentum.momentum_value,
                        "volume": momentum.volume,
                        "timeframe": momentum.timeframe,
                        "divergence": momentum.divergence.value if momentum.divergence else None,
                        "timestamp": momentum.timestamp.isoformat(),
                    }
                },
            )

            signals.append(signal)

        return signals

    # ========================================================================
    # Position Sizing
    # ========================================================================

    async def _calculate_momentum_position_size(
        self,
        symbol: str,
        price: float,
        momentum_data: Dict[str, Any],
    ) -> float:
        """
        Calculate position size with momentum adjustment.

        Args:
            symbol: Trading symbol
            price: Entry price
            momentum_data: Momentum data

        Returns:
            Position size
        """
        # Base position size
        base_size = self._calculate_position_size(price)

        # Momentum strength adjustment
        strength = momentum_data.get('strength', 0.5)
        momentum_multiplier = 0.5 + strength * 0.5

        # Direction adjustment
        direction = momentum_data.get('direction', 'neutral')
        if direction in ['strong_bullish', 'strong_bearish']:
            direction_multiplier = 1.2
        else:
            direction_multiplier = 1.0

        # Volatility adjustment
        volatility = momentum_data.get('metadata', {}).get('price_std', 0)
        if volatility > 0:
            vol_multiplier = 1.0 / (1 + volatility)
        else:
            vol_multiplier = 1.0

        # Calculate final size
        final_size = base_size * momentum_multiplier * direction_multiplier * vol_multiplier

        # Apply limits
        min_size = self.config.min_position_size if hasattr(self.config, 'min_position_size') else 0.01
        max_size = self.config.max_position_size * self.config.position_size_multiplier

        return max(min_size, min(final_size, max_size))

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _rank_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        Rank signals by confidence and strength.

        Args:
            signals: List of signals

        Returns:
            Ranked signals
        """
        return sorted(
            signals,
            key=lambda x: (x.confidence, x.strength.value),
            reverse=True
        )

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

    async def _get_market_data(self, symbol: str, timeframe: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Get market data for symbol.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (optional)

        Returns:
            DataFrame with price data
        """
        try:
            tf = timeframe or self.config.timeframe
            return await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe=tf,
                limit=self.config.lookback_periods,
            )
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    def _update_price_history(self, symbol: str, data: pd.DataFrame) -> None:
        """
        Update price history.

        Args:
            symbol: Trading symbol
            data: Price data
        """
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=self.config.lookback_periods)

        close = data['close'].values

        for price in close:
            self._price_history[symbol].append(price)

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
            "by_type": dict(self._performance["by_type"]),
            "by_direction": dict(self._performance["by_direction"]),
            "divergence_success_rate": (
                self._performance["divergence_success"] /
                max(self._performance["divergence_signals"], 1)
            ),
            "adaptive_parameters": self._adaptive_parameters,
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy."""
        if self._running:
            return

        self._running = True
        logger.info("MomentumStrategy started")

    async def stop(self) -> None:
        """Stop the strategy."""
        self._running = False

        # Clean up
        async with self._lock:
            self._momentum_signals.clear()
            self._price_history.clear()
            self._divergence_history.clear()
            self._adaptive_parameters.clear()

        logger.info("MomentumStrategy stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_momentum_strategy(
    config: MomentumConfig,
    risk_manager: RiskManager,
    order_manager: OrderManager,
    market_data_provider: Any,
) -> MomentumStrategy:
    """
    Factory function to create a MomentumStrategy instance.

    Args:
        config: Strategy configuration
        risk_manager: Risk management instance
        order_manager: Order management instance
        market_data_provider: Market data provider

    Returns:
        MomentumStrategy instance
    """
    return MomentumStrategy(
        config=config,
        risk_manager=risk_manager,
        order_manager=order_manager,
        market_data_provider=market_data_provider,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the momentum strategy
    pass
