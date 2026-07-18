# trading/strategies/momentum.py
"""
NEXUS AI TRADING SYSTEM - Momentum Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements momentum-based trading strategies including:
- Price momentum
- Volume momentum
- Relative strength
- Rate of change
- Moving average crossovers
- MACD momentum
- Dual momentum
- Time series momentum

Momentum strategies profit from the continuation of existing trends
and price movements.
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

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Signal, Position, Trade
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class MomentumType(str, Enum):
    """Types of momentum strategies"""
    PRICE = "price"                    # Price momentum
    VOLUME = "volume"                  # Volume momentum
    RSI = "rsi"                        # RSI momentum
    MACD = "macd"                      # MACD momentum
    MA_CROSSOVER = "ma_crossover"      # Moving average crossover
    ROC = "roc"                        # Rate of change
    DUAL = "dual"                      # Dual momentum
    TIME_SERIES = "time_series"        # Time series momentum
    COMBINED = "combined"              # Combined momentum signals


class MomentumDirection(str, Enum):
    """Direction for momentum trading"""
    LONG_ONLY = "long_only"
    SHORT_ONLY = "short_only"
    BOTH = "both"


@dataclass
class MomentumConfig:
    """Configuration for momentum strategy"""
    # Strategy type
    momentum_type: MomentumType = MomentumType.PRICE
    direction: MomentumDirection = MomentumDirection.BOTH
    
    # Momentum periods
    short_period: int = 10
    medium_period: int = 30
    long_period: int = 50
    
    # Price momentum
    price_momentum_lookback: int = 20
    price_momentum_threshold: float = 2.0  # Percentage
    
    # Volume momentum
    volume_lookback: int = 20
    volume_threshold: float = 1.5
    
    # RSI
    rsi_period: int = 14
    rsi_upper: float = 70.0
    rsi_lower: float = 30.0
    
    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # ROC
    roc_period: int = 10
    roc_threshold: float = 5.0  # Percentage
    
    # Moving average crossover
    ma_fast: int = 10
    ma_slow: int = 30
    
    # Dual momentum
    absolute_momentum_period: int = 12  # months
    relative_momentum_period: int = 6   # months
    
    # Risk management
    position_size: float = 1000.0
    max_position_size: float = 10000.0
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    max_positions: int = 5
    max_drawdown: float = 0.10
    
    # Entry/Exit
    min_confidence: float = 0.6
    exit_on_trend_reversal: bool = True
    exit_on_signal_reversal: bool = True
    trailing_stop_pct: float = 0.02
    
    # Filtering
    require_volume_confirmation: bool = False
    require_trend_confirmation: bool = False
    trend_ma_period: int = 50


@dataclass
class MomentumState:
    """Current state of momentum strategy"""
    symbol: str
    current_price: float = 0.0
    momentum_score: float = 0.0
    trend_direction: int = 0  # 1: up, -1: down, 0: neutral
    momentum_value: float = 0.0
    
    # Moving averages
    ma_short: float = 0.0
    ma_medium: float = 0.0
    ma_long: float = 0.0
    
    # RSI
    rsi: float = 50.0
    
    # MACD
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    
    # ROC
    roc: float = 0.0
    
    # Position tracking
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    highest_price: float = 0.0
    lowest_price: float = 0.0
    holding_period: int = 0
    is_long: bool = False
    
    # Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# MOMENTUM STRATEGY
# ============================================================================

class MomentumStrategy(BaseStrategy):
    """
    Momentum trading strategy that follows trends and momentum signals.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        momentum_config: Optional[MomentumConfig] = None,
    ):
        """
        Initialize the momentum strategy.
        
        Args:
            config: Strategy configuration
            momentum_config: Momentum configuration
        """
        super().__init__(config)
        self.momentum_config = momentum_config or MomentumConfig()
        
        # State management
        self._states: Dict[str, MomentumState] = {}
        
        # Data storage
        self._price_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        self._returns_history: Dict[str, deque] = {}
        
        # Indicator values
        self._indicators: Dict[str, Dict[str, float]] = {}
        
        # Performance tracking
        self._momentum_stats = {
            "total_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "momentum_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_hold_period": 0.0,
            "momentum_win_rate": 0.0,
            "avg_momentum_score": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # INDICATOR CALCULATIONS
    # ========================================================================
    
    def calculate_ma(self, prices: List[float], period: int) -> float:
        """
        Calculate moving average.
        
        Args:
            prices: Price series
            period: MA period
            
        Returns:
            float: Moving average
        """
        if len(prices) < period:
            return 0.0
        
        recent = prices[-period:]
        return sum(recent) / len(recent)
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """
        Calculate RSI.
        
        Args:
            prices: Price series
            period: RSI period
            
        Returns:
            float: RSI value
        """
        if len(prices) < period + 1:
            return 50.0
        
        deltas = []
        for i in range(1, len(prices)):
            deltas.append(prices[i] - prices[i-1])
        
        gains = [d for d in deltas[-period:] if d > 0]
        losses = [abs(d) for d in deltas[-period:] if d < 0]
        
        avg_gain = sum(gains) / period if gains else 0
        avg_loss = sum(losses) / period if losses else 0
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
    
    def calculate_macd(
        self,
        prices: List[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Tuple[float, float, float]:
        """
        Calculate MACD.
        
        Args:
            prices: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line period
            
        Returns:
            Tuple[float, float, float]: (MACD, signal_line, histogram)
        """
        if len(prices) < slow + signal:
            return 0.0, 0.0, 0.0
        
        # Simple approximation using SMA for speed
        fast_ma = self.calculate_ma(prices, fast)
        slow_ma = self.calculate_ma(prices, slow)
        macd = fast_ma - slow_ma
        
        # Signal line (SMA of MACD)
        # Use price history as approximation
        signal_line = self.calculate_ma([macd] * min(len(prices), signal), signal)
        histogram = macd - signal_line
        
        return macd, signal_line, histogram
    
    def calculate_roc(self, prices: List[float], period: int) -> float:
        """
        Calculate Rate of Change.
        
        Args:
            prices: Price series
            period: ROC period
            
        Returns:
            float: ROC percentage
        """
        if len(prices) < period + 1:
            return 0.0
        
        current = prices[-1]
        previous = prices[-period - 1]
        
        if previous == 0:
            return 0.0
        
        return ((current - previous) / previous) * 100
    
    def calculate_momentum_score(
        self,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> float:
        """
        Calculate momentum score.
        
        Args:
            prices: Price series
            volumes: Volume series
            
        Returns:
            float: Momentum score
        """
        if len(prices) < 2:
            return 0.0
        
        # Price momentum
        price_roc = self.calculate_roc(prices, self.momentum_config.price_momentum_lookback)
        
        # Normalize price momentum
        price_score = max(-1, min(1, price_roc / self.momentum_config.price_momentum_threshold))
        
        # Volume momentum (if available)
        volume_score = 0.0
        if volumes and len(volumes) >= self.momentum_config.volume_lookback:
            volume_ma = self.calculate_ma(volumes, self.momentum_config.volume_lookback)
            if volume_ma > 0:
                volume_ratio = volumes[-1] / volume_ma
                volume_score = max(-1, min(1, (volume_ratio - 1) * 2))
        
        # Combined momentum score (price dominates)
        momentum_score = price_score * 0.7 + volume_score * 0.3
        
        return momentum_score
    
    # ========================================================================
    # SIGNAL DETECTION
    # ========================================================================
    
    async def _detect_momentum_signal(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> Optional[Signal]:
        """
        Detect momentum signal.
        
        Args:
            symbol: Trading symbol
            prices: Price series
            volumes: Volume series
            
        Returns:
            Optional[Signal]: Momentum signal or None
        """
        if len(prices) < self.momentum_config.long_period:
            return None
        
        current_price = prices[-1]
        
        # Initialize state
        if symbol not in self._states:
            self._states[symbol] = MomentumState(symbol=symbol)
        
        state = self._states[symbol]
        state.current_price = current_price
        
        # Store price history
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=200)
        self._price_history[symbol].append(current_price)
        
        # Calculate indicators
        momentum_type = self.momentum_config.momentum_type
        
        if momentum_type == MomentumType.PRICE:
            return await self._detect_price_momentum(symbol, prices, volumes, state)
        
        elif momentum_type == MomentumType.VOLUME:
            return await self._detect_volume_momentum(symbol, prices, volumes, state)
        
        elif momentum_type == MomentumType.RSI:
            return await self._detect_rsi_momentum(symbol, prices, state)
        
        elif momentum_type == MomentumType.MACD:
            return await self._detect_macd_momentum(symbol, prices, state)
        
        elif momentum_type == MomentumType.MA_CROSSOVER:
            return await self._detect_ma_crossover(symbol, prices, state)
        
        elif momentum_type == MomentumType.ROC:
            return await self._detect_roc_momentum(symbol, prices, state)
        
        elif momentum_type == MomentumType.COMBINED:
            return await self._detect_combined_momentum(symbol, prices, volumes, state)
        
        return None
    
    async def _detect_price_momentum(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect price momentum signal."""
        momentum_score = self.calculate_momentum_score(prices, volumes)
        state.momentum_score = momentum_score
        
        # Calculate moving averages for trend confirmation
        ma_short = self.calculate_ma(prices, self.momentum_config.short_period)
        ma_long = self.calculate_ma(prices, self.momentum_config.long_period)
        state.ma_short = ma_short
        state.ma_long = ma_long
        
        current = prices[-1]
        
        # Determine trend direction
        trend_up = ma_short > ma_long and current > ma_short
        trend_down = ma_short < ma_long and current < ma_short
        
        # Buy signal: strong positive momentum with uptrend
        if momentum_score > 0.5 and trend_up:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=current,
                    state=state,
                    reason=f"Strong positive momentum: {momentum_score:.2f}",
                    metadata={"momentum_score": momentum_score},
                )
        
        # Sell signal: strong negative momentum with downtrend
        elif momentum_score < -0.5 and trend_down:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=current,
                    state=state,
                    reason=f"Strong negative momentum: {momentum_score:.2f}",
                    metadata={"momentum_score": momentum_score},
                )
        
        return None
    
    async def _detect_volume_momentum(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect volume momentum signal."""
        if not volumes or len(volumes) < self.momentum_config.volume_lookback:
            return None
        
        current_volume = volumes[-1]
        volume_ma = self.calculate_ma(volumes, self.momentum_config.volume_lookback)
        
        if volume_ma == 0:
            return None
        
        volume_ratio = current_volume / volume_ma
        
        # Price momentum
        price_momentum = self.calculate_momentum_score(prices, volumes)
        
        # Buy signal: volume surge with price momentum
        if volume_ratio > self.momentum_config.volume_threshold and price_momentum > 0.3:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=prices[-1],
                    state=state,
                    reason=f"Volume surge with price momentum: {volume_ratio:.2f}x",
                    metadata={"volume_ratio": volume_ratio, "price_momentum": price_momentum},
                )
        
        # Sell signal: volume surge with negative momentum
        elif volume_ratio > self.momentum_config.volume_threshold and price_momentum < -0.3:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=prices[-1],
                    state=state,
                    reason=f"Volume surge with negative momentum: {volume_ratio:.2f}x",
                    metadata={"volume_ratio": volume_ratio, "price_momentum": price_momentum},
                )
        
        return None
    
    async def _detect_rsi_momentum(
        self,
        symbol: str,
        prices: List[float],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect RSI momentum signal."""
        rsi = self.calculate_rsi(prices, self.momentum_config.rsi_period)
        state.rsi = rsi
        
        # Check trend for confirmation
        ma_short = self.calculate_ma(prices, self.momentum_config.short_period)
        ma_long = self.calculate_ma(prices, self.momentum_config.long_period)
        trend_up = ma_short > ma_long
        
        # Buy signal: RSI oversold with bullish trend
        if rsi <= self.momentum_config.rsi_lower and trend_up:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=prices[-1],
                    state=state,
                    reason=f"RSI oversold with bullish trend: {rsi:.1f}",
                    metadata={"rsi": rsi},
                )
        
        # Sell signal: RSI overbought with bearish trend
        elif rsi >= self.momentum_config.rsi_upper and not trend_up:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=prices[-1],
                    state=state,
                    reason=f"RSI overbought with bearish trend: {rsi:.1f}",
                    metadata={"rsi": rsi},
                )
        
        return None
    
    async def _detect_macd_momentum(
        self,
        symbol: str,
        prices: List[float],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect MACD momentum signal."""
        macd, signal, histogram = self.calculate_macd(
            prices,
            self.momentum_config.macd_fast,
            self.momentum_config.macd_slow,
            self.momentum_config.macd_signal,
        )
        
        state.macd = macd
        state.macd_signal = signal
        state.macd_histogram = histogram
        
        # Check previous histogram for crossover detection
        prev_histogram = 0.0
        if len(prices) > self.momentum_config.macd_slow + 1:
            prev_macd, prev_signal, prev_histogram = self.calculate_macd(
                prices[:-1],
                self.momentum_config.macd_fast,
                self.momentum_config.macd_slow,
                self.momentum_config.macd_signal,
            )
        
        # Buy signal: MACD histogram turns positive (crossover)
        if prev_histogram <= 0 and histogram > 0:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=prices[-1],
                    state=state,
                    reason=f"MACD bullish crossover: {histogram:.4f}",
                    metadata={"macd": macd, "signal": signal, "histogram": histogram},
                )
        
        # Sell signal: MACD histogram turns negative (crossover)
        elif prev_histogram >= 0 and histogram < 0:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=prices[-1],
                    state=state,
                    reason=f"MACD bearish crossover: {histogram:.4f}",
                    metadata={"macd": macd, "signal": signal, "histogram": histogram},
                )
        
        return None
    
    async def _detect_ma_crossover(
        self,
        symbol: str,
        prices: List[float],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect moving average crossover signal."""
        ma_fast = self.calculate_ma(prices, self.momentum_config.ma_fast)
        ma_slow = self.calculate_ma(prices, self.momentum_config.ma_slow)
        
        state.ma_short = ma_fast
        state.ma_long = ma_slow
        
        # Calculate previous values for crossover detection
        prev_ma_fast = 0.0
        prev_ma_slow = 0.0
        if len(prices) > self.momentum_config.ma_slow + 1:
            prev_ma_fast = self.calculate_ma(prices[:-1], self.momentum_config.ma_fast)
            prev_ma_slow = self.calculate_ma(prices[:-1], self.momentum_config.ma_slow)
        
        # Buy signal: fast MA crosses above slow MA
        if prev_ma_fast <= prev_ma_slow and ma_fast > ma_slow:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=prices[-1],
                    state=state,
                    reason=f"Golden cross: {ma_fast:.2f} > {ma_slow:.2f}",
                    metadata={"ma_fast": ma_fast, "ma_slow": ma_slow},
                )
        
        # Sell signal: fast MA crosses below slow MA
        elif prev_ma_fast >= prev_ma_slow and ma_fast < ma_slow:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=prices[-1],
                    state=state,
                    reason=f"Death cross: {ma_fast:.2f} < {ma_slow:.2f}",
                    metadata={"ma_fast": ma_fast, "ma_slow": ma_slow},
                )
        
        return None
    
    async def _detect_roc_momentum(
        self,
        symbol: str,
        prices: List[float],
        state: MomentumState,
    ) -> Optional[Signal]:
        """Detect Rate of Change momentum signal."""
        roc = self.calculate_roc(prices, self.momentum_config.roc_period)
        state.roc = roc
        
        threshold = self.momentum_config.roc_threshold
        
        # Buy signal: strong positive ROC with trend
        if roc > threshold:
            ma_short = self.calculate_ma(prices, self.momentum_config.short_period)
            ma_long = self.calculate_ma(prices, self.momentum_config.long_period)
            
            if ma_short > ma_long:  # Uptrend confirmation
                if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                    return await self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        price=prices[-1],
                        state=state,
                        reason=f"Strong ROC with uptrend: {roc:.2f}%",
                        metadata={"roc": roc},
                    )
        
        # Sell signal: strong negative ROC with trend
        elif roc < -threshold:
            ma_short = self.calculate_ma(prices, self.momentum_config.short_period)
            ma_long = self.calculate_ma(prices, self.momentum_config.long_period)
            
            if ma_short < ma_long:  # Downtrend confirmation
                if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                    return await self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        price=prices[-1],
                        state=state,
                        reason=f"Strong negative ROC with downtrend: {roc:.2f}%",
                        metadata={"roc": roc},
                    )
        
        return None
    
    async def _detect_combined_momentum(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]],
        state: MomentumState,
    ) -> Optional[Signal]:
        """
        Detect combined momentum signal using multiple indicators.
        """
        # Calculate all indicators
        momentum_score = self.calculate_momentum_score(prices, volumes)
        rsi = self.calculate_rsi(prices, self.momentum_config.rsi_period)
        macd, signal, histogram = self.calculate_macd(
            prices,
            self.momentum_config.macd_fast,
            self.momentum_config.macd_slow,
            self.momentum_config.macd_signal,
        )
        ma_short = self.calculate_ma(prices, self.momentum_config.short_period)
        ma_long = self.calculate_ma(prices, self.momentum_config.long_period)
        
        state.momentum_score = momentum_score
        state.rsi = rsi
        state.macd = macd
        state.macd_signal = signal
        state.macd_histogram = histogram
        state.ma_short = ma_short
        state.ma_long = ma_long
        
        current = prices[-1]
        
        # Buy signal conditions
        buy_conditions = 0
        buy_conditions += 1 if momentum_score > 0.3 else 0
        buy_conditions += 1 if rsi > 50 else 0
        buy_conditions += 1 if ma_short > ma_long else 0
        buy_conditions += 1 if histogram > 0 else 0
        
        # Sell signal conditions
        sell_conditions = 0
        sell_conditions += 1 if momentum_score < -0.3 else 0
        sell_conditions += 1 if rsi < 50 else 0
        sell_conditions += 1 if ma_short < ma_long else 0
        sell_conditions += 1 if histogram < 0 else 0
        
        # Require at least 3 conditions
        if buy_conditions >= 3:
            if self.momentum_config.direction in [MomentumDirection.LONG_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=current,
                    state=state,
                    reason=f"Combined buy signal: {buy_conditions} conditions",
                    metadata={
                        "momentum_score": momentum_score,
                        "rsi": rsi,
                        "macd": macd,
                        "histogram": histogram,
                        "conditions": buy_conditions,
                    },
                )
        
        elif sell_conditions >= 3:
            if self.momentum_config.direction in [MomentumDirection.SHORT_ONLY, MomentumDirection.BOTH]:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=current,
                    state=state,
                    reason=f"Combined sell signal: {sell_conditions} conditions",
                    metadata={
                        "momentum_score": momentum_score,
                        "rsi": rsi,
                        "macd": macd,
                        "histogram": histogram,
                        "conditions": sell_conditions,
                    },
                )
        
        return None
    
    # ========================================================================
    # SIGNAL CREATION
    # ========================================================================
    
    async def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        price: float,
        state: MomentumState,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """
        Create a trading signal from momentum detection.
        
        Args:
            symbol: Trading symbol
            signal_type: Signal type
            price: Current price
            state: Current state
            reason: Signal reason
            metadata: Additional metadata
            
        Returns:
            Optional[Signal]: Trading signal
        """
        # Check position limits
        if len(self.positions) >= self.momentum_config.max_positions:
            return None
        
        if symbol in self.positions:
            return None
        
        # Calculate confidence
        confidence = self._calculate_momentum_confidence(state, signal_type)
        
        if confidence < self.momentum_config.min_confidence:
            return None
        
        # Calculate position size
        position_size = self.momentum_config.position_size
        
        # Adjust size based on confidence
        if confidence > 0.85:
            position_size *= 1.5
        elif confidence < 0.7:
            position_size *= 0.75
        
        position_size = max(0, min(position_size, self.momentum_config.max_position_size))
        
        # Calculate stop loss and take profit
        if signal_type == SignalType.BUY:
            stop_loss = price * (1 - self.momentum_config.stop_loss_pct)
            take_profit = price * (1 + self.momentum_config.take_profit_pct)
        else:
            stop_loss = price * (1 + self.momentum_config.stop_loss_pct)
            take_profit = price * (1 - self.momentum_config.take_profit_pct)
        
        # Determine signal strength
        strength = self._determine_signal_strength(confidence)
        
        # Update state
        state.entry_price = price
        state.entry_time = datetime.utcnow()
        state.highest_price = price
        state.lowest_price = price
        state.is_long = signal_type == SignalType.BUY
        state.holding_period = 0
        
        self._momentum_stats["total_signals"] += 1
        if signal_type == SignalType.BUY:
            self._momentum_stats["buy_signals"] += 1
        else:
            self._momentum_stats["sell_signals"] += 1
        
        # Create signal
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=datetime.utcnow(),
            metadata={
                **metadata,
                "reason": reason,
                "momentum_type": self.momentum_config.momentum_type.value,
                "state": {
                    "momentum_score": state.momentum_score,
                    "rsi": state.rsi,
                    "macd": state.macd,
                    "macd_histogram": state.macd_histogram,
                    "ma_short": state.ma_short,
                    "ma_long": state.ma_long,
                },
            },
        )
        
        self.logger.info(
            f"Momentum signal: {signal_type.value} {symbol} @ {price:.2f} "
            f"(confidence: {confidence:.2f}) - {reason}"
        )
        
        return signal
    
    def _calculate_momentum_confidence(
        self,
        state: MomentumState,
        signal_type: SignalType,
    ) -> float:
        """
        Calculate confidence level for momentum signal.
        
        Args:
            state: Current state
            signal_type: Signal type
            
        Returns:
            float: Confidence level (0-1)
        """
        confidence = 0.6  # Base confidence
        
        # Momentum score contribution
        abs_momentum = abs(state.momentum_score)
        confidence += min(abs_momentum * 0.3, 0.25)
        
        # RSI contribution (if available)
        if state.rsi > 0:
            if signal_type == SignalType.BUY and state.rsi > 50:
                confidence += 0.05
            elif signal_type == SignalType.SELL and state.rsi < 50:
                confidence += 0.05
        
        # Trend confirmation
        if state.ma_short > 0 and state.ma_long > 0:
            if signal_type == SignalType.BUY and state.ma_short > state.ma_long:
                confidence += 0.1
            elif signal_type == SignalType.SELL and state.ma_short < state.ma_long:
                confidence += 0.1
        
        # MACD confirmation
        if state.macd_histogram != 0:
            if signal_type == SignalType.BUY and state.macd_histogram > 0:
                confidence += 0.05
            elif signal_type == SignalType.SELL and state.macd_histogram < 0:
                confidence += 0.05
        
        return min(0.95, confidence)
    
    def _determine_signal_strength(self, confidence: float) -> SignalStrength:
        """Determine signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.7:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on momentum logic.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        symbol = self.config.symbol or market_data[0].symbol
        prices = [c.close for c in market_data if c.symbol == symbol]
        volumes = [c.volume for c in market_data if c.symbol == symbol] if market_data else None
        
        if not prices:
            return None
        
        # Detect momentum signal
        signal = await self._detect_momentum_signal(symbol, prices, volumes)
        
        return signal
    
    # ========================================================================
    # TRADE HANDLING
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Handle completed trade.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        pnl = trade.pnl or 0.0
        
        # Update momentum stats
        self._momentum_stats["momentum_trades"] += 1
        
        if pnl > 0:
            self._momentum_stats["winning_trades"] += 1
        else:
            self._momentum_stats["losing_trades"] += 1
        
        # Calculate win rate
        total = self._momentum_stats["momentum_trades"]
        if total > 0:
            self._momentum_stats["momentum_win_rate"] = (
                self._momentum_stats["winning_trades"] / total * 100            )
        
        # Update state
        for state in self._states.values():
            if state.symbol == trade.symbol:
                state.total_trades += 1
                if pnl > 0:
                    state.winning_trades += 1
                else:
                    state.losing_trades += 1
                state.total_pnl += pnl
                
                # Calculate average momentum score for this trade
                score = state.momentum_score
                total_trades = state.total_trades
                self._momentum_stats["avg_momentum_score"] = (
                    (self._momentum_stats["avg_momentum_score"] * (total_trades - 1) + abs(score)) / total_trades
                )
                break
    
    async def on_position_update(self, position: Position) -> None:
        """
        Handle position update.
        
        Args:
            position: Updated position
        """
        await super().on_position_update(position)
        
        # Update state
        for state in self._states.values():
            if state.symbol == position.symbol:
                state.holding_period += 1
                state.highest_price = max(state.highest_price, position.entry_price)
                state.lowest_price = min(state.lowest_price, position.entry_price)
                
                # Check trailing stop
                if self.momentum_config.trailing_stop_pct > 0:
                    if state.is_long:
                        trail_stop = state.highest_price * (1 - self.momentum_config.trailing_stop_pct)
                        if position.entry_price <= trail_stop:
                            self.logger.info(f"Trailing stop hit for {position.symbol}")
                            signal = Signal(
                                symbol=position.symbol,
                                signal_type=SignalType.CLOSE,
                                strength=SignalStrength.MEDIUM,
                                confidence=0.9,
                                price=position.entry_price,
                                timestamp=datetime.utcnow(),
                                metadata={"reason": "trailing_stop"},
                            )
                            await self.process_signal(signal)
                    else:
                        trail_stop = state.lowest_price * (1 + self.momentum_config.trailing_stop_pct)
                        if position.entry_price >= trail_stop:
                            self.logger.info(f"Trailing stop hit for {position.symbol}")
                            signal = Signal(
                                symbol=position.symbol,
                                signal_type=SignalType.CLOSE,
                                strength=SignalStrength.MEDIUM,
                                confidence=0.9,
                                price=position.entry_price,
                                timestamp=datetime.utcnow(),
                                metadata={"reason": "trailing_stop"},
                            )
                            await self.process_signal(signal)
                break
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_momentum_stats(self) -> Dict[str, Any]:
        """
        Get momentum statistics.
        
        Returns:
            Dict[str, Any]: Momentum statistics
        """
        return {
            **self._momentum_stats,
            "current_states": {
                symbol: {
                    "price": state.current_price,
                    "momentum_score": state.momentum_score,
                    "rsi": state.rsi,
                    "macd": state.macd,
                    "macd_histogram": state.macd_histogram,
                    "ma_short": state.ma_short,
                    "ma_long": state.ma_long,
                    "holding_period": state.holding_period,
                    "total_trades": state.total_trades,
                    "total_pnl": state.total_pnl,
                }
                for symbol, state in self._states.items()
            },
            "config": {
                "momentum_type": self.momentum_config.momentum_type.value,
                "direction": self.momentum_config.direction.value,
                "short_period": self.momentum_config.short_period,
                "long_period": self.momentum_config.long_period,
            },
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Momentum strategy started (type: {self.momentum_config.momentum_type.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Momentum strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "MomentumType",
    "MomentumDirection",
    "MomentumConfig",
    "MomentumState",
    "MomentumStrategy",
]
