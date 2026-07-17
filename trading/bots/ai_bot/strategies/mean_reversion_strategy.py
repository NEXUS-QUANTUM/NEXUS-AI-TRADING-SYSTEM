# trading/bots/ai_bot/strategies/mean_reversion_strategy.py
# NEXUS AI TRADING SYSTEM - Mean Reversion Trading Strategy
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
Mean Reversion Trading Strategy for NEXUS AI Trading Bot.
Identifies and trades mean reversion opportunities using:
- Bollinger Bands
- RSI (Relative Strength Index)
- Z-score analysis
- Price-channel regression
- Kalman filter for trend estimation
- Pairs trading
- Volatility-based entry/exit
- Multi-timeframe confirmation
- Adaptive reversion parameters
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
from scipy import stats
from pykalman import KalmanFilter

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, SignalType, SignalStrength
from trading.bots.ai_bot.strategies.risk_management import RiskManager
from trading.bots.ai_bot.execution.order_manager import OrderManager
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.mean_reversion")


# ============================================================================
# Enums & Constants
# ============================================================================

class ReversionType(str, Enum):
    """Types of mean reversion."""
    BOLLINGER = "bollinger"
    RSI = "rsi"
    Z_SCORE = "z_score"
    REGRESSION = "regression"
    KALMAN = "kalman"
    PAIRS = "pairs"
    VOLATILITY = "volatility"
    MULTI_TIMEFRAME = "multi_timeframe"


class ReversionState(str, Enum):
    """Mean reversion states."""
    OVERSOLD = "oversold"
    OVERBOUGHT = "overbought"
    NEUTRAL = "neutral"
    EXTREME_OVERSOLD = "extreme_oversold"
    EXTREME_OVERBOUGHT = "extreme_overbought"


@dataclass
class ReversionSignal:
    """Mean reversion signal data."""
    symbol: str
    type: ReversionType
    state: ReversionState
    price: float
    mean: float
    std: float
    z_score: float
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    volatility: float
    timeframe: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MeanReversionConfig(StrategyConfig):
    """Mean reversion strategy configuration."""
    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0
    bb_entry_threshold: float = 1.5
    bb_exit_threshold: float = 0.5

    # RSI
    rsi_period: int = 14
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    rsi_entry_threshold: float = 5

    # Z-score
    z_score_entry: float = 2.0
    z_score_exit: float = 0.5
    z_score_lookback: int = 50

    # General
    min_confidence: float = 0.6
    max_position_duration: int = 60  # minutes
    reversion_strength_threshold: float = 0.7
    volatility_adjustment: bool = True
    use_multi_timeframe: bool = True
    use_kalman_filter: bool = True
    use_pairs_trading: bool = True
    pair_selection_threshold: float = 0.8
    lookback_periods: int = 100

    # Exit parameters
    take_profit_std: float = 1.0
    stop_loss_std: float = 2.5
    trailing_stop: bool = True
    trailing_stop_activation: float = 0.5


# ============================================================================
# Mean Reversion Strategy
# ============================================================================

class MeanReversionStrategy(BaseStrategy):
    """
    Advanced Mean Reversion Trading Strategy.
    Identifies and trades mean reversion opportunities.
    """

    def __init__(
        self,
        config: MeanReversionConfig,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        market_data_provider: Any,
    ):
        """
        Initialize mean reversion strategy.

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
        self._reversion_signals: Dict[str, List[ReversionSignal]] = {}
        self._kalman_filters: Dict[str, KalmanFilter] = {}
        self._pair_correlations: Dict[Tuple[str, str], float] = {}

        # Performance metrics
        self._performance = {
            "signals_detected": 0,
            "signals_executed": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "average_reversion_profit": 0.0,
            "average_reversion_loss": 0.0,
            "by_type": defaultdict(lambda: {
                "detected": 0,
                "executed": 0,
                "successful": 0,
            }),
            "by_state": defaultdict(lambda: {
                "detected": 0,
                "executed": 0,
            }),
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        logger.info(
            "MeanReversionStrategy initialized",
            extra={
                "symbols": self.config.symbols,
                "bb_period": self.config.bb_period,
                "rsi_period": self.config.rsi_period,
            }
        )

    # ========================================================================
    # Main Strategy Methods
    # ========================================================================

    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze market data and identify mean reversion opportunities.

        Returns:
            Analysis results with reversion signals
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

                # Detect reversion signals
                reversion_signals = await self._detect_reversion(symbol, data)

                if reversion_signals:
                    # Validate and filter signals
                    validated = await self._validate_signals(symbol, reversion_signals, data)

                    if validated:
                        # Generate trading signals
                        signals.extend(await self._generate_signals(symbol, validated, data))

            # Rank signals
            signals = self._rank_signals(signals)

            return {
                "signals": signals[:10],
                "total_signals": len(signals),
                "reversion_signals_detected": self._performance["signals_detected"],
            }

        except Exception as e:
            logger.error(f"Error in mean reversion analysis: {e}")
            return {"signals": [], "error": str(e)}

    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """
        Execute a mean reversion trading signal.

        Args:
            signal: Trading signal

        Returns:
            Execution results
        """
        try:
            # Get reversion data from signal metadata
            reversion_data = signal.metadata.get("reversion", {})

            if not reversion_data:
                return {"success": False, "error": "No reversion data in signal"}

            # Check if signal is still valid
            if not await self._validate_signal_execution(signal.symbol, reversion_data):
                return {"success": False, "error": "Signal no longer valid"}

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
                self._performance["signals_executed"] += 1
                self._performance["by_type"][reversion_data.get("type", "unknown")]["executed"] += 1
                self._performance["by_state"][reversion_data.get("state", "neutral")]["executed"] += 1

                return {
                    "success": True,
                    "order": order_result,
                    "reversion": reversion_data,
                }

            return order_result

        except Exception as e:
            logger.error(f"Error executing reversion signal: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Reversion Detection Methods
    # ========================================================================

    async def _detect_reversion(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> List[ReversionSignal]:
        """
        Detect mean reversion signals.

        Args:
            symbol: Trading symbol
            data: Price data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values
            volume = data['volume'].values

            # Bollinger Bands reversion
            bb_signals = await self._detect_bollinger_reversion(symbol, close, high, low, volume)

            if bb_signals:
                signals.extend(bb_signals)

            # RSI reversion
            rsi_signals = await self._detect_rsi_reversion(symbol, close, volume)

            if rsi_signals:
                signals.extend(rsi_signals)

            # Z-score reversion
            zscore_signals = await self._detect_zscore_reversion(symbol, close, volume)

            if zscore_signals:
                signals.extend(zscore_signals)

            # Kalman filter reversion
            if self.config.use_kalman_filter:
                kalman_signals = await self._detect_kalman_reversion(symbol, close, volume)

                if kalman_signals:
                    signals.extend(kalman_signals)

            # Pairs trading reversion
            if self.config.use_pairs_trading:
                pairs_signals = await self._detect_pairs_reversion(symbol, close, volume, data)

                if pairs_signals:
                    signals.extend(pairs_signals)

            # Multi-timeframe confirmation
            if self.config.use_multi_timeframe:
                signals = await self._apply_multi_timeframe_confirmation(symbol, signals)

            return signals

        except Exception as e:
            logger.error(f"Error detecting reversion for {symbol}: {e}")
            return []

    # ========================================================================
    # Bollinger Bands Reversion
    # ========================================================================

    async def _detect_bollinger_reversion(
        self,
        symbol: str,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> List[ReversionSignal]:
        """
        Detect Bollinger Bands mean reversion.

        Args:
            symbol: Trading symbol
            close: Close prices
            high: High prices
            low: Low prices
            volume: Volume data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            if len(close) < self.config.bb_period:
                return signals

            # Calculate Bollinger Bands
            upper, middle, lower = talib.BBANDS(
                close,
                timeperiod=self.config.bb_period,
                nbdevup=self.config.bb_std_dev,
                nbdevdn=self.config.bb_std_dev,
                matype=0,
            )

            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Check for oversold (price below lower band)
            if current_price < lower[-1]:
                # Calculate how far below
                deviation = (lower[-1] - current_price) / (upper[-1] - lower[-1])

                if deviation > self.config.bb_entry_threshold / 10:
                    # Check volume confirmation
                    volume_confirm = current_volume > avg_volume * 0.8

                    # Calculate confidence
                    confidence = min(deviation / 0.3, 1.0)

                    if confidence >= self.config.min_confidence:
                        signal = ReversionSignal(
                            symbol=symbol,
                            type=ReversionType.BOLLINGER,
                            state=ReversionState.OVERSOLD,
                            price=current_price,
                            mean=middle[-1],
                            std=(upper[-1] - lower[-1]) / 4,
                            z_score=(current_price - middle[-1]) / ((upper[-1] - lower[-1]) / 4),
                            confidence=confidence,
                            entry_price=current_price,
                            target_price=middle[-1] * 1.1,
                            stop_loss=current_price * 0.97,
                            volatility=(upper[-1] - lower[-1]) / middle[-1],
                            timeframe=self.config.timeframe,
                            timestamp=datetime.utcnow(),
                            metadata={
                                "bb_upper": upper[-1],
                                "bb_middle": middle[-1],
                                "bb_lower": lower[-1],
                                "volume_confirm": volume_confirm,
                                "deviation": deviation,
                            },
                        )

                        signals.append(signal)
                        self._performance["signals_detected"] += 1
                        self._performance["by_type"][ReversionType.BOLLINGER.value]["detected"] += 1
                        self._performance["by_state"][ReversionState.OVERSOLD.value]["detected"] += 1

            # Check for overbought (price above upper band)
            elif current_price > upper[-1]:
                deviation = (current_price - upper[-1]) / (upper[-1] - lower[-1])

                if deviation > self.config.bb_entry_threshold / 10:
                    volume_confirm = current_volume > avg_volume * 0.8
                    confidence = min(deviation / 0.3, 1.0)

                    if confidence >= self.config.min_confidence:
                        signal = ReversionSignal(
                            symbol=symbol,
                            type=ReversionType.BOLLINGER,
                            state=ReversionState.OVERBOUGHT,
                            price=current_price,
                            mean=middle[-1],
                            std=(upper[-1] - lower[-1]) / 4,
                            z_score=(current_price - middle[-1]) / ((upper[-1] - lower[-1]) / 4),
                            confidence=confidence,
                            entry_price=current_price,
                            target_price=middle[-1] * 0.9,
                            stop_loss=current_price * 1.03,
                            volatility=(upper[-1] - lower[-1]) / middle[-1],
                            timeframe=self.config.timeframe,
                            timestamp=datetime.utcnow(),
                            metadata={
                                "bb_upper": upper[-1],
                                "bb_middle": middle[-1],
                                "bb_lower": lower[-1],
                                "volume_confirm": volume_confirm,
                                "deviation": deviation,
                            },
                        )

                        signals.append(signal)
                        self._performance["signals_detected"] += 1
                        self._performance["by_type"][ReversionType.BOLLINGER.value]["detected"] += 1
                        self._performance["by_state"][ReversionState.OVERBOUGHT.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting Bollinger reversion: {e}")
            return []

    # ========================================================================
    # RSI Reversion
    # ========================================================================

    async def _detect_rsi_reversion(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[ReversionSignal]:
        """
        Detect RSI mean reversion.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            if len(close) < self.config.rsi_period:
                return signals

            # Calculate RSI
            rsi = talib.RSI(close, timeperiod=self.config.rsi_period)

            if rsi[-1] is None:
                return signals

            current_rsi = rsi[-1]
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Oversold condition
            if current_rsi < self.config.rsi_oversold:
                deviation = (self.config.rsi_oversold - current_rsi) / self.config.rsi_entry_threshold

                if deviation > 0.2:
                    volume_confirm = current_volume > avg_volume * 0.8
                    confidence = min(deviation * 2, 1.0)

                    if confidence >= self.config.min_confidence:
                        # Calculate target price
                        price_std = np.std(close[-20:])
                        target_price = current_price + price_std * 0.5

                        signal = ReversionSignal(
                            symbol=symbol,
                            type=ReversionType.RSI,
                            state=ReversionState.OVERSOLD,
                            price=current_price,
                            mean=self.config.rsi_oversold,
                            std=self.config.rsi_entry_threshold,
                            z_score=(current_rsi - self.config.rsi_oversold) / self.config.rsi_entry_threshold,
                            confidence=confidence,
                            entry_price=current_price,
                            target_price=target_price,
                            stop_loss=current_price * 0.97,
                            volatility=np.std(close[-20:]) / np.mean(close[-20:]),
                            timeframe=self.config.timeframe,
                            timestamp=datetime.utcnow(),
                            metadata={
                                "rsi": current_rsi,
                                "volume_confirm": volume_confirm,
                                "deviation": deviation,
                            },
                        )

                        signals.append(signal)
                        self._performance["signals_detected"] += 1
                        self._performance["by_type"][ReversionType.RSI.value]["detected"] += 1
                        self._performance["by_state"][ReversionState.OVERSOLD.value]["detected"] += 1

            # Overbought condition
            elif current_rsi > self.config.rsi_overbought:
                deviation = (current_rsi - self.config.rsi_overbought) / self.config.rsi_entry_threshold

                if deviation > 0.2:
                    volume_confirm = current_volume > avg_volume * 0.8
                    confidence = min(deviation * 2, 1.0)

                    if confidence >= self.config.min_confidence:
                        price_std = np.std(close[-20:])
                        target_price = current_price - price_std * 0.5

                        signal = ReversionSignal(
                            symbol=symbol,
                            type=ReversionType.RSI,
                            state=ReversionState.OVERBOUGHT,
                            price=current_price,
                            mean=self.config.rsi_overbought,
                            std=self.config.rsi_entry_threshold,
                            z_score=(current_rsi - self.config.rsi_overbought) / self.config.rsi_entry_threshold,
                            confidence=confidence,
                            entry_price=current_price,
                            target_price=target_price,
                            stop_loss=current_price * 1.03,
                            volatility=np.std(close[-20:]) / np.mean(close[-20:]),
                            timeframe=self.config.timeframe,
                            timestamp=datetime.utcnow(),
                            metadata={
                                "rsi": current_rsi,
                                "volume_confirm": volume_confirm,
                                "deviation": deviation,
                            },
                        )

                        signals.append(signal)
                        self._performance["signals_detected"] += 1
                        self._performance["by_type"][ReversionType.RSI.value]["detected"] += 1
                        self._performance["by_state"][ReversionState.OVERBOUGHT.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting RSI reversion: {e}")
            return []

    # ========================================================================
    # Z-Score Reversion
    # ========================================================================

    async def _detect_zscore_reversion(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[ReversionSignal]:
        """
        Detect Z-score mean reversion.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            lookback = min(self.config.z_score_lookback, len(close))

            if lookback < 20:
                return signals

            # Calculate rolling mean and std
            rolling_mean = np.mean(close[-lookback:])
            rolling_std = np.std(close[-lookback:])

            if rolling_std == 0:
                return signals

            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Calculate z-score
            z_score = (current_price - rolling_mean) / rolling_std

            # Check for extreme z-score
            if abs(z_score) > self.config.z_score_entry:
                # Determine direction
                if z_score > 0:
                    state = ReversionState.OVERBOUGHT
                    direction = "sell"
                    target_price = current_price - rolling_std * self.config.z_score_exit
                    stop_loss = current_price + rolling_std * 0.5
                else:
                    state = ReversionState.OVERSOLD
                    direction = "buy"
                    target_price = current_price + rolling_std * self.config.z_score_exit
                    stop_loss = current_price - rolling_std * 0.5

                # Calculate confidence
                confidence = min(abs(z_score) / (2 * self.config.z_score_entry), 1.0)

                # Volume confirmation
                volume_confirm = current_volume > avg_volume * 0.8

                if confidence >= self.config.min_confidence:
                    signal = ReversionSignal(
                        symbol=symbol,
                        type=ReversionType.Z_SCORE,
                        state=state,
                        price=current_price,
                        mean=rolling_mean,
                        std=rolling_std,
                        z_score=z_score,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        volatility=rolling_std / rolling_mean,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "rolling_mean": rolling_mean,
                            "rolling_std": rolling_std,
                            "volume_confirm": volume_confirm,
                            "z_score": z_score,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1
                    self._performance["by_type"][ReversionType.Z_SCORE.value]["detected"] += 1
                    self._performance["by_state"][state.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting Z-score reversion: {e}")
            return []

    # ========================================================================
    # Kalman Filter Reversion
    # ========================================================================

    async def _detect_kalman_reversion(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> List[ReversionSignal]:
        """
        Detect Kalman filter mean reversion.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            if len(close) < 20:
                return signals

            # Initialize or update Kalman filter
            if symbol not in self._kalman_filters:
                # 1D Kalman filter for price
                self._kalman_filters[symbol] = KalmanFilter(
                    transition_matrices=[1],
                    observation_matrices=[1],
                    initial_state_mean=close[-1],
                    initial_state_covariance=1,
                    transition_covariance=0.01,
                    observation_covariance=0.1,
                )

            kf = self._kalman_filters[symbol]

            # Update filter with current price
            current_price = close[-1]
            current_volume = volume[-1]
            avg_volume = np.mean(volume[-20:])

            # Predict and update
            state_means, state_covs = kf.filter(close[-20:])

            if len(state_means) < 2:
                return signals

            # Get filtered state
            filtered_price = state_means[-1][0]
            filtered_std = np.sqrt(state_covs[-1][0][0])

            # Calculate deviation
            deviation = current_price - filtered_price
            z_score = deviation / filtered_std

            # Check for significant deviation
            if abs(z_score) > self.config.z_score_entry * 0.8:
                if z_score > 0:
                    state = ReversionState.OVERBOUGHT
                    direction = "sell"
                    target_price = current_price - filtered_std * 0.5
                    stop_loss = current_price + filtered_std * 0.5
                else:
                    state = ReversionState.OVERSOLD
                    direction = "buy"
                    target_price = current_price + filtered_std * 0.5
                    stop_loss = current_price - filtered_std * 0.5

                confidence = min(abs(z_score) / (2 * self.config.z_score_entry), 1.0)
                volume_confirm = current_volume > avg_volume * 0.8

                if confidence >= self.config.min_confidence:
                    signal = ReversionSignal(
                        symbol=symbol,
                        type=ReversionType.KALMAN,
                        state=state,
                        price=current_price,
                        mean=filtered_price,
                        std=filtered_std,
                        z_score=z_score,
                        confidence=confidence,
                        entry_price=current_price,
                        target_price=target_price,
                        stop_loss=stop_loss,
                        volatility=filtered_std / filtered_price,
                        timeframe=self.config.timeframe,
                        timestamp=datetime.utcnow(),
                        metadata={
                            "filtered_price": filtered_price,
                            "filtered_std": filtered_std,
                            "volume_confirm": volume_confirm,
                        },
                    )

                    signals.append(signal)
                    self._performance["signals_detected"] += 1
                    self._performance["by_type"][ReversionType.KALMAN.value]["detected"] += 1
                    self._performance["by_state"][state.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting Kalman reversion: {e}")
            return []

    # ========================================================================
    # Pairs Trading Reversion
    # ========================================================================

    async def _detect_pairs_reversion(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
        data: pd.DataFrame,
    ) -> List[ReversionSignal]:
        """
        Detect pairs trading mean reversion.

        Args:
            symbol: Trading symbol
            close: Close prices
            volume: Volume data
            data: Full price data

        Returns:
            List of ReversionSignal
        """
        signals = []

        try:
            # Find correlated pairs
            pairs = await self._find_correlated_pairs(symbol, data)

            if not pairs:
                return signals

            for pair in pairs:
                # Get pair data
                pair_symbol = pair["symbol"]
                correlation = pair["correlation"]

                if correlation < self.config.pair_selection_threshold:
                    continue

                # Get pair price data
                pair_data = await self._get_market_data(pair_symbol)

                if pair_data is None:
                    continue

                # Calculate spread
                spread = close[-20:] / pair_data['close'].values[-20:]

                # Calculate spread statistics
                spread_mean = np.mean(spread)
                spread_std = np.std(spread)

                if spread_std == 0:
                    continue

                current_spread = close[-1] / pair_data['close'].values[-1]
                z_score = (current_spread - spread_mean) / spread_std

                # Check for spread divergence
                if abs(z_score) > self.config.z_score_entry:
                    if z_score > 0:
                        # Spread is too wide - sell symbol, buy pair
                        state = ReversionState.OVERBOUGHT
                        target_spread = spread_mean - spread_std * 0.3
                    else:
                        # Spread is too narrow - buy symbol, sell pair
                        state = ReversionState.OVERSOLD
                        target_spread = spread_mean + spread_std * 0.3

                    confidence = min(abs(z_score) / (2 * self.config.z_score_entry), 1.0)

                    if confidence >= self.config.min_confidence:
                        # Calculate target price
                        target_price = pair_data['close'].values[-1] * target_spread

                        signal = ReversionSignal(
                            symbol=symbol,
                            type=ReversionType.PAIRS,
                            state=state,
                            price=close[-1],
                            mean=spread_mean,
                            std=spread_std,
                            z_score=z_score,
                            confidence=confidence,
                            entry_price=close[-1],
                            target_price=target_price,
                            stop_loss=close[-1] * 0.97 if z_score > 0 else close[-1] * 1.03,
                            volatility=spread_std / spread_mean,
                            timeframe=self.config.timeframe,
                            timestamp=datetime.utcnow(),
                            metadata={
                                "pair_symbol": pair_symbol,
                                "correlation": correlation,
                                "spread_mean": spread_mean,
                                "spread_std": spread_std,
                                "current_spread": current_spread,
                                "target_spread": target_spread,
                            },
                        )

                        signals.append(signal)
                        self._performance["signals_detected"] += 1
                        self._performance["by_type"][ReversionType.PAIRS.value]["detected"] += 1
                        self._performance["by_state"][state.value]["detected"] += 1

            return signals

        except Exception as e:
            logger.error(f"Error detecting pairs reversion: {e}")
            return []

    async def _find_correlated_pairs(
        self,
        symbol: str,
        data: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """
        Find correlated pairs for pairs trading.

        Args:
            symbol: Base symbol
            data: Base symbol data

        Returns:
            List of correlated pairs
        """
        pairs = []

        try:
            close = data['close'].values

            # Get all available symbols
            all_symbols = self.config.symbols

            for other_symbol in all_symbols:
                if other_symbol == symbol:
                    continue

                # Get other symbol data
                other_data = await self._get_market_data(other_symbol)

                if other_data is None:
                    continue

                other_close = other_data['close'].values

                # Calculate correlation
                min_len = min(len(close), len(other_close))
                if min_len < 50:
                    continue

                correlation = np.corrcoef(close[-min_len:], other_close[-min_len:])[0, 1]

                if abs(correlation) > self.config.pair_selection_threshold:
                    pairs.append({
                        "symbol": other_symbol,
                        "correlation": correlation,
                    })

            # Sort by correlation strength
            pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

            return pairs[:5]

        except Exception as e:
            logger.error(f"Error finding correlated pairs: {e}")
            return []

    # ========================================================================
    # Multi-Timeframe Confirmation
    # ========================================================================

    async def _apply_multi_timeframe_confirmation(
        self,
        symbol: str,
        signals: List[ReversionSignal],
    ) -> List[ReversionSignal]:
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
                # Check if signal is confirmed on higher timeframes
                confirmation_count = 0

                for tf, tf_data in higher_tf.items():
                    if tf_data is None or len(tf_data) < 20:
                        continue

                    tf_close = tf_data['close'].values
                    tf_current = tf_close[-1]

                    # Check if higher timeframe is in agreement
                    if signal.state == ReversionState.OVERSOLD:
                        # Check if higher timeframe is also oversold or neutral
                        if tf_current < np.mean(tf_close[-20:]):
                            confirmation_count += 1
                    else:
                        if tf_current > np.mean(tf_close[-20:]):
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
    # Signal Validation
    # ========================================================================

    async def _validate_signals(
        self,
        symbol: str,
        signals: List[ReversionSignal],
        data: pd.DataFrame,
    ) -> List[ReversionSignal]:
        """
        Validate mean reversion signals.

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

            # Check if reversion strength is sufficient
            reversion_strength = await self._calculate_reversion_strength(signal, data)

            if reversion_strength < self.config.reversion_strength_threshold:
                continue

            # Check volatility adjustment
            if self.config.volatility_adjustment:
                if not await self._check_volatility_adjustment(signal, data):
                    continue

            validated.append(signal)

        return validated

    async def _calculate_reversion_strength(
        self,
        signal: ReversionSignal,
        data: pd.DataFrame,
    ) -> float:
        """
        Calculate reversion strength.

        Args:
            signal: Reversion signal
            data: Price data

        Returns:
            Reversion strength (0-1)
        """
        strength = 0.0

        # Price deviation strength (30%)
        deviation = abs(signal.z_score) / self.config.z_score_entry
        strength += min(deviation, 1.0) * 0.3

        # Volume strength (20%)
        volume_ratio = signal.metadata.get("volume_confirm", 0)
        strength += min(volume_ratio / 2, 1.0) * 0.2

        # Momentum divergence (25%)
        rsi = talib.RSI(data['close'].values, timeperiod=14)
        if len(rsi) > 0 and rsi[-1] is not None:
            if signal.state == ReversionState.OVERSOLD and rsi[-1] < 30:
                strength += 0.25
            elif signal.state == ReversionState.OVERBOUGHT and rsi[-1] > 70:
                strength += 0.25

        # Historical performance (25%)
        # Would check historical reversion success at this level
        strength += 0.2

        return min(strength, 1.0)

    async def _check_volatility_adjustment(
        self,
        signal: ReversionSignal,
        data: pd.DataFrame,
    ) -> bool:
        """
        Check volatility adjustment.

        Args:
            signal: Reversion signal
            data: Price data

        Returns:
            True if volatility is favorable
        """
        try:
            current_vol = signal.volatility
            avg_vol = data['close'].pct_change().std() * np.sqrt(252)

            if avg_vol == 0:
                return True

            vol_ratio = current_vol / avg_vol

            # Only trade when volatility is reasonable
            return 0.5 <= vol_ratio <= 2.0

        except Exception:
            return True

    async def _validate_signal_execution(
        self,
        symbol: str,
        reversion_data: Dict[str, Any],
    ) -> bool:
        """
        Validate signal for execution.

        Args:
            symbol: Trading symbol
            reversion_data: Reversion data

        Returns:
            True if valid
        """
        try:
            # Get latest price
            ticker = await self.market_data.get_ticker(symbol)
            current_price = ticker.get('last', 0)

            if current_price <= 0:
                return False

            # Check if reversion condition still exists
            entry_price = reversion_data.get('entry_price', 0)
            state = reversion_data.get('state', 'neutral')

            if state == 'oversold':
                if current_price > entry_price * 1.02:
                    return False
            else:
                if current_price < entry_price * 0.98:
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
        reversion_signals: List[ReversionSignal],
        data: pd.DataFrame,
    ) -> List[Signal]:
        """
        Generate trading signals from reversion signals.

        Args:
            symbol: Trading symbol
            reversion_signals: List of ReversionSignal
            data: Price data

        Returns:
            List of Signal
        """
        signals = []

        for reversion in reversion_signals:
            # Determine signal type
            if reversion.state in [ReversionState.OVERSOLD, ReversionState.EXTREME_OVERSOLD]:
                signal_type = SignalType.BUY
            else:
                signal_type = SignalType.SELL

            # Calculate position size
            position_size = self._calculate_position_size(reversion.entry_price)

            # Determine signal strength
            if reversion.confidence > 0.8:
                strength = SignalStrength.STRONG
            elif reversion.confidence > 0.65:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = Signal(
                symbol=symbol,
                type=signal_type,
                strength=strength,
                confidence=reversion.confidence,
                price=reversion.entry_price,
                quantity=position_size,
                stop_loss=reversion.stop_loss,
                take_profit=reversion.target_price,
                reason=f"Mean reversion: {reversion.type.value} {reversion.state.value}",
                timestamp=datetime.utcnow(),
                expiry_time=datetime.utcnow() + timedelta(minutes=30),
                metadata={
                    "reversion": {
                        "type": reversion.type.value,
                        "state": reversion.state.value,
                        "entry_price": reversion.entry_price,
                        "target_price": reversion.target_price,
                        "stop_loss": reversion.stop_loss,
                        "confidence": reversion.confidence,
                        "z_score": reversion.z_score,
                        "mean": reversion.mean,
                        "std": reversion.std,
                        "volatility": reversion.volatility,
                        "timeframe": reversion.timeframe,
                        "timestamp": reversion.timestamp.isoformat(),
                    }
                },
            )

            signals.append(signal)

        return signals

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
            "by_state": dict(self._performance["by_state"]),
            "active_pairs": len(self._pair_correlations),
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy."""
        if self._running:
            return

        self._running = True
        logger.info("MeanReversionStrategy started")

    async def stop(self) -> None:
        """Stop the strategy."""
        self._running = False

        # Clean up
        async with self._lock:
            self._reversion_signals.clear()
            self._price_history.clear()
            self._kalman_filters.clear()

        logger.info("MeanReversionStrategy stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_mean_reversion_strategy(
    config: MeanReversionConfig,
    risk_manager: RiskManager,
    order_manager: OrderManager,
    market_data_provider: Any,
) -> MeanReversionStrategy:
    """
    Factory function to create a MeanReversionStrategy instance.

    Args:
        config: Strategy configuration
        risk_manager: Risk management instance
        order_manager: Order management instance
        market_data_provider: Market data provider

    Returns:
        MeanReversionStrategy instance
    """
    return MeanReversionStrategy(
        config=config,
        risk_manager=risk_manager,
        order_manager=order_manager,
        market_data_provider=market_data_provider,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the mean reversion strategy
    pass
