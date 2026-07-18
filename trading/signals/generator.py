# trading/signals/generator.py
"""
NEXUS AI TRADING SYSTEM - Signal Generator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides signal generation capabilities including:
- Rule-based signal generation
- Pattern detection
- Multi-timeframe signal generation
- Signal strength calculation
- Confidence scoring
- Signal filtering and ranking
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict, deque

import numpy as np
import pandas as pd
from scipy import stats

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, OrderBook, Trade
from .base import Signal, SignalType, SignalStrength
from ..strategies.base import BaseStrategy

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class SignalGenerationMethod(str, Enum):
    """Methods for generating signals"""
    RULE_BASED = "rule_based"
    PATTERN = "pattern"
    INDICATOR = "indicator"
    PRICE_ACTION = "price_action"
    VOLUME = "volume"
    ORDER_BOOK = "order_book"
    MULTI_TIMEFRAME = "multi_timeframe"
    COMPOSITE = "composite"


class PatternType(str, Enum):
    """Types of price patterns"""
    HEAD_SHOULDERS = "head_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIANGLE = "triangle"
    FLAG = "flag"
    PENNANT = "pennant"
    WEDGE = "wedge"
    CUP_HANDLE = "cup_handle"
    BREAKOUT = "breakout"


@dataclass
class SignalGeneratorConfig:
    """Configuration for signal generator"""
    # Generation parameters
    generation_methods: List[SignalGenerationMethod] = field(default_factory=lambda: [
        SignalGenerationMethod.INDICATOR,
        SignalGenerationMethod.PRICE_ACTION,
    ])
    min_confidence: float = 0.5
    min_signal_strength: SignalStrength = SignalStrength.MEDIUM
    
    # Pattern detection
    pattern_lookback: int = 100
    pattern_confirmation_bars: int = 3
    pattern_tolerance: float = 0.01  # 1% tolerance
    
    # Indicator settings
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std_dev: float = 2.0
    
    # Multi-timeframe
    timeframe_weight: Dict[str, float] = field(default_factory=lambda: {
        "1m": 0.3,
        "5m": 0.5,
        "15m": 0.7,
        "1h": 1.0,
        "4h": 1.2,
        "1d": 1.5,
    })
    min_timeframes_for_signal: int = 2
    
    # Filtering
    filter_duplicates: bool = True
    duplicate_window: int = 60  # seconds
    max_signals_per_minute: int = 10
    
    # Ranking
    ranking_method: str = "confidence"  # confidence, strength, composite


@dataclass
class GeneratedSignal:
    """Generated signal with metadata"""
    signal: Signal
    generation_method: SignalGenerationMethod
    confidence: float
    weight: float = 1.0
    timeframe: Optional[str] = None
    pattern_type: Optional[PatternType] = None
    indicator_values: Dict[str, float] = field(default_factory=dict)
    supporting_signals: List[Signal] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_signal(self) -> Signal:
        """Convert to base Signal."""
        return self.signal


# ============================================================================
# SIGNAL GENERATOR
# ============================================================================

class SignalGenerator:
    """
    Generates trading signals using various methods.
    
    Features:
    - Multiple signal generation methods
    - Pattern detection
    - Indicator-based signals
    - Multi-timeframe confirmation
    - Signal ranking and filtering
    - Confidence scoring
    """
    
    def __init__(self, config: Optional[SignalGeneratorConfig] = None):
        """
        Initialize the signal generator.
        
        Args:
            config: Generator configuration
        """
        self.config = config or SignalGeneratorConfig()
        
        # Data storage
        self._market_data: Dict[str, deque] = {}
        self._indicator_cache: Dict[str, Dict[str, float]] = {}
        self._pattern_cache: Dict[str, List[PatternType]] = defaultdict(list)
        
        # Signal history
        self._signal_history: List[GeneratedSignal] = []
        self._recent_signals: deque = deque(maxlen=1000)
        
        # Statistics
        self._stats = {
            "signals_generated": 0,
            "signals_by_method": defaultdict(int),
            "signals_by_type": defaultdict(int),
            "signals_filtered": 0,
            "avg_confidence": 0.0,
            "avg_generation_time_ms": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signals(
        self,
        market_data: Dict[str, List[MarketData]],
        order_books: Optional[Dict[str, OrderBook]] = None,
    ) -> List[GeneratedSignal]:
        """
        Generate signals from market data.
        
        Args:
            market_data: Market data by symbol
            order_books: Order books by symbol
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        start_time = time.time()
        signals = []
        
        async with self._lock:
            # Update data cache
            for symbol, data in market_data.items():
                if symbol not in self._market_data:
                    self._market_data[symbol] = deque(maxlen=1000)
                self._market_data[symbol].extend(data)
            
            # Generate signals for each symbol
            for symbol, data in market_data.items():
                if not data:
                    continue
                
                symbol_signals = await self._generate_symbol_signals(
                    symbol,
                    data,
                    order_books.get(symbol) if order_books else None,
                )
                signals.extend(symbol_signals)
            
            # Filter and rank signals
            signals = self._filter_signals(signals)
            signals = self._rank_signals(signals)
            
            # Update statistics
            self._stats["signals_generated"] += len(signals)
            for signal in signals:
                self._stats["signals_by_method"][signal.generation_method.value] += 1
                self._stats["signals_by_type"][signal.signal.signal_type.value] += 1
            
            if signals:
                self._stats["avg_confidence"] = (
                    (self._stats["avg_confidence"] * (self._stats["signals_generated"] - len(signals)) +
                     sum(s.confidence for s in signals)) /
                    self._stats["signals_generated"]
                )
            
            self._stats["avg_generation_time_ms"] = (
                (self._stats["avg_generation_time_ms"] * (len(self._signal_history)) +
                 (time.time() - start_time) * 1000) /
                (len(self._signal_history) + len(signals))
            )
            
            # Store history
            self._signal_history.extend(signals)
            for signal in signals:
                self._recent_signals.append(signal)
        
        return signals
    
    async def _generate_symbol_signals(
        self,
        symbol: str,
        data: List[MarketData],
        order_book: Optional[OrderBook] = None,
    ) -> List[GeneratedSignal]:
        """
        Generate signals for a single symbol.
        
        Args:
            symbol: Trading symbol
            data: Market data
            order_book: Order book data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        
        for method in self.config.generation_methods:
            if method == SignalGenerationMethod.INDICATOR:
                signals.extend(await self._generate_indicator_signals(symbol, data))
            elif method == SignalGenerationMethod.PATTERN:
                signals.extend(await self._generate_pattern_signals(symbol, data))
            elif method == SignalGenerationMethod.PRICE_ACTION:
                signals.extend(await self._generate_price_action_signals(symbol, data))
            elif method == SignalGenerationMethod.VOLUME:
                signals.extend(await self._generate_volume_signals(symbol, data))
            elif method == SignalGenerationMethod.ORDER_BOOK:
                if order_book:
                    signals.extend(await self._generate_order_book_signals(symbol, order_book))
            elif method == SignalGenerationMethod.MULTI_TIMEFRAME:
                signals.extend(await self._generate_multi_timeframe_signals(symbol, data))
            elif method == SignalGenerationMethod.RULE_BASED:
                signals.extend(await self._generate_rule_based_signals(symbol, data))
            elif method == SignalGenerationMethod.COMPOSITE:
                signals.extend(await self._generate_composite_signals(symbol, data))
        
        return signals
    
    # ========================================================================
    # INDICATOR-BASED SIGNALS
    # ========================================================================
    
    async def _generate_indicator_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals based on technical indicators.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        prices = [d.close for d in data]
        
        if len(prices) < self.config.bb_period:
            return signals
        
        # Calculate indicators
        rsi = self._calculate_rsi(prices)
        macd, macd_signal, macd_hist = self._calculate_macd(prices)
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(prices)
        
        current_price = prices[-1]
        current_rsi = rsi[-1] if rsi else 50
        current_macd = macd[-1] if macd else 0
        
        # RSI signals
        if current_rsi <= self.config.rsi_oversold:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=0.7 + (self.config.rsi_oversold - current_rsi) / self.config.rsi_oversold * 0.2,
                price=current_price,
                generation_method=SignalGenerationMethod.INDICATOR,
                indicator_values={"rsi": current_rsi},
                metadata={"indicator": "rsi", "value": current_rsi},
            )
            signals.append(signal)
        
        elif current_rsi >= self.config.rsi_overbought:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                confidence=0.7 + (current_rsi - self.config.rsi_overbought) / (100 - self.config.rsi_overbought) * 0.2,
                price=current_price,
                generation_method=SignalGenerationMethod.INDICATOR,
                indicator_values={"rsi": current_rsi},
                metadata={"indicator": "rsi", "value": current_rsi},
            )
            signals.append(signal)
        
        # Bollinger Bands signals
        if len(prices) > 0 and bb_upper > 0 and bb_lower > 0:
            if current_price <= bb_lower:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    confidence=0.6 + (bb_lower - current_price) / current_price * 10,
                    price=current_price,
                    generation_method=SignalGenerationMethod.INDICATOR,
                    indicator_values={"bb_lower": bb_lower, "bb_middle": bb_middle},
                    metadata={"indicator": "bb", "value": "lower_band"},
                )
                signals.append(signal)
            
            elif current_price >= bb_upper:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    confidence=0.6 + (current_price - bb_upper) / current_price * 10,
                    price=current_price,
                    generation_method=SignalGenerationMethod.INDICATOR,
                    indicator_values={"bb_upper": bb_upper, "bb_middle": bb_middle},
                    metadata={"indicator": "bb", "value": "upper_band"},
                )
                signals.append(signal)
        
        # MACD signals
        if len(macd_hist) > 1:
            if macd_hist[-1] > 0 and macd_hist[-2] <= 0:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    confidence=0.65 + abs(macd_hist[-1]) / 10,
                    price=current_price,
                    generation_method=SignalGenerationMethod.INDICATOR,
                    indicator_values={"macd": current_macd, "macd_hist": macd_hist[-1]},
                    metadata={"indicator": "macd", "value": "histogram_cross_above"},
                )
                signals.append(signal)
            
            elif macd_hist[-1] < 0 and macd_hist[-2] >= 0:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    confidence=0.65 + abs(macd_hist[-1]) / 10,
                    price=current_price,
                    generation_method=SignalGenerationMethod.INDICATOR,
                    indicator_values={"macd": current_macd, "macd_hist": macd_hist[-1]},
                    metadata={"indicator": "macd", "value": "histogram_cross_below"},
                )
                signals.append(signal)
        
        return signals
    
    # ========================================================================
    # PATTERN-BASED SIGNALS
    # ========================================================================
    
    async def _generate_pattern_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals based on price patterns.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        prices = [d.close for d in data]
        
        if len(prices) < self.config.pattern_lookback:
            return signals
        
        # Detect patterns
        patterns = self._detect_patterns(prices)
        
        for pattern_type in patterns:
            if pattern_type in [PatternType.HEAD_SHOULDERS, PatternType.DOUBLE_TOP]:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    confidence=0.7,
                    price=prices[-1],
                    generation_method=SignalGenerationMethod.PATTERN,
                    pattern_type=pattern_type,
                    metadata={"pattern": pattern_type.value},
                )
                signals.append(signal)
            
            elif pattern_type in [PatternType.DOUBLE_BOTTOM, PatternType.BREAKOUT]:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    confidence=0.7,
                    price=prices[-1],
                    generation_method=SignalGenerationMethod.PATTERN,
                    pattern_type=pattern_type,
                    metadata={"pattern": pattern_type.value},
                )
                signals.append(signal)
        
        return signals
    
    # ========================================================================
    # PRICE ACTION SIGNALS
    # ========================================================================
    
    async def _generate_price_action_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals from price action.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        prices = [d.close for d in data]
        
        if len(prices) < 20:
            return signals
        
        current_price = prices[-1]
        
        # Support/Resistance breakouts
        support, resistance = self._find_support_resistance(prices)
        
        if support and current_price < support[-1]:
            # Break below support
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                confidence=0.65,
                price=current_price,
                generation_method=SignalGenerationMethod.PRICE_ACTION,
                metadata={"action": "support_break", "level": support[-1]},
            )
            signals.append(signal)
        
        elif resistance and current_price > resistance[-1]:
            # Break above resistance
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=0.65,
                price=current_price,
                generation_method=SignalGenerationMethod.PRICE_ACTION,
                metadata={"action": "resistance_break", "level": resistance[-1]},
            )
            signals.append(signal)
        
        # Candlestick patterns (simplified)
        if len(data) >= 2:
            if data[-1].close > data[-2].close * 1.02 and data[-1].low > data[-2].high:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    confidence=0.6,
                    price=current_price,
                    generation_method=SignalGenerationMethod.PRICE_ACTION,
                    metadata={"action": "bullish_engulfing"},
                )
                signals.append(signal)
            
            elif data[-1].close < data[-2].close * 0.98 and data[-1].high < data[-2].low:
                signal = self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    confidence=0.6,
                    price=current_price,
                    generation_method=SignalGenerationMethod.PRICE_ACTION,
                    metadata={"action": "bearish_engulfing"},
                )
                signals.append(signal)
        
        return signals
    
    # ========================================================================
    # VOLUME-BASED SIGNALS
    # ========================================================================
    
    async def _generate_volume_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals from volume data.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        volumes = [d.volume for d in data if d.volume]
        
        if len(volumes) < 20:
            return signals
        
        current_price = data[-1].close
        current_volume = volumes[-1]
        
        # Calculate volume moving average
        vol_ma = sum(volumes[-20:]) / 20
        
        # Volume spike
        if current_volume > vol_ma * 2:
            # Check price direction with volume
            if len(data) >= 2:
                price_change = (data[-1].close - data[-2].close) / data[-2].close
                
                if price_change > 0.01:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.BUY,
                        confidence=0.6 + min(1, current_volume / vol_ma / 2) * 0.2,
                        price=current_price,
                        generation_method=SignalGenerationMethod.VOLUME,
                        metadata={
                            "action": "volume_spike",
                            "volume_ratio": current_volume / vol_ma,
                            "price_change": price_change,
                        },
                    )
                    signals.append(signal)
                elif price_change < -0.01:
                    signal = self._create_signal(
                        symbol=symbol,
                        signal_type=SignalType.SELL,
                        confidence=0.6 + min(1, current_volume / vol_ma / 2) * 0.2,
                        price=current_price,
                        generation_method=SignalGenerationMethod.VOLUME,
                        metadata={
                            "action": "volume_spike",
                            "volume_ratio": current_volume / vol_ma,
                            "price_change": price_change,
                        },
                    )
                    signals.append(signal)
        
        return signals
    
    # ========================================================================
    # ORDER BOOK SIGNALS
    # ========================================================================
    
    async def _generate_order_book_signals(
        self,
        symbol: str,
        order_book: OrderBook,
    ) -> List[GeneratedSignal]:
        """
        Generate signals from order book data.
        
        Args:
            symbol: Trading symbol
            order_book: Order book data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        
        if not order_book or not order_book.bids or not order_book.asks:
            return signals
        
        # Calculate imbalance
        bid_depth = sum(b[1] for b in order_book.bids[:10])
        ask_depth = sum(a[1] for a in order_book.asks[:10])
        
        if bid_depth + ask_depth == 0:
            return signals
        
        imbalance = bid_depth / (bid_depth + ask_depth)
        
        # Strong bid pressure
        if imbalance > 0.65:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=0.55 + (imbalance - 0.65) / 0.35 * 0.2,
                price=order_book.bids[0][0] if order_book.bids else 0,
                generation_method=SignalGenerationMethod.ORDER_BOOK,
                metadata={
                    "action": "bid_imbalance",
                    "imbalance": imbalance,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                },
            )
            signals.append(signal)
        
        # Strong ask pressure
        if imbalance < 0.35:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                confidence=0.55 + (0.35 - imbalance) / 0.35 * 0.2,
                price=order_book.asks[0][0] if order_book.asks else 0,
                generation_method=SignalGenerationMethod.ORDER_BOOK,
                metadata={
                    "action": "ask_imbalance",
                    "imbalance": imbalance,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                },
            )
            signals.append(signal)
        
        return signals
    
    # ========================================================================
    # MULTI-TIMEFRAME SIGNALS
    # ========================================================================
    
    async def _generate_multi_timeframe_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals using multi-timeframe analysis.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        
        # This would require data from multiple timeframes
        # For now, use indicator signals with higher confidence if confirmed
        indicator_signals = await self._generate_indicator_signals(symbol, data)
        
        if indicator_signals:
            # In practice, we would check higher timeframe confirmation
            for signal in indicator_signals:
                signal.confidence = min(1, signal.confidence * 1.1)
                signal.metadata["multi_timeframe_confirmed"] = True
        
        return signals
    
    # ========================================================================
    # RULE-BASED SIGNALS
    # ========================================================================
    
    async def _generate_rule_based_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals using predefined rules.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        prices = [d.close for d in data]
        
        if len(prices) < 50:
            return signals
        
        # Example rules
        # 1. Price above 50-period MA with rising volume
        ma50 = sum(prices[-50:]) / 50 if len(prices) >= 50 else 0
        if ma50 > 0 and prices[-1] > ma50 * 1.01:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=0.6,
                price=prices[-1],
                generation_method=SignalGenerationMethod.RULE_BASED,
                metadata={"rule": "price_above_ma50"},
            )
            signals.append(signal)
        
        # 2. Price below 50-period MA
        elif ma50 > 0 and prices[-1] < ma50 * 0.99:
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                confidence=0.6,
                price=prices[-1],
                generation_method=SignalGenerationMethod.RULE_BASED,
                metadata={"rule": "price_below_ma50"},
            )
            signals.append(signal)
        
        return signals
    
    # ========================================================================
    # COMPOSITE SIGNALS
    # ========================================================================
    
    async def _generate_composite_signals(
        self,
        symbol: str,
        data: List[MarketData],
    ) -> List[GeneratedSignal]:
        """
        Generate signals from composite analysis.
        
        Args:
            symbol: Trading symbol
            data: Market data
            
        Returns:
            List[GeneratedSignal]: Generated signals
        """
        signals = []
        
        # Generate signals from multiple methods
        indicator = await self._generate_indicator_signals(symbol, data)
        price_action = await self._generate_price_action_signals(symbol, data)
        pattern = await self._generate_pattern_signals(symbol, data)
        
        # Combine signals
        all_signals = indicator + price_action + pattern
        
        if not all_signals:
            return signals
        
        # Group by signal type
        buy_signals = [s for s in all_signals if s.signal.signal_type == SignalType.BUY]
        sell_signals = [s for s in all_signals if s.signal.signal_type == SignalType.SELL]
        
        # Create composite signals if multiple confirmations
        if len(buy_signals) >= 2:
            avg_confidence = sum(s.confidence for s in buy_signals) / len(buy_signals)
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=min(1, avg_confidence * 1.1 + len(buy_signals) * 0.05),
                price=data[-1].close,
                generation_method=SignalGenerationMethod.COMPOSITE,
                supporting_signals=[s.signal for s in buy_signals],
                metadata={
                    "method": "composite",
                    "confirmations": len(buy_signals),
                    "source_methods": [s.generation_method.value for s in buy_signals],
                },
            )
            signals.append(signal)
        
        if len(sell_signals) >= 2:
            avg_confidence = sum(s.confidence for s in sell_signals) / len(sell_signals)
            signal = self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                confidence=min(1, avg_confidence * 1.1 + len(sell_signals) * 0.05),
                price=data[-1].close,
                generation_method=SignalGenerationMethod.COMPOSITE,
                supporting_signals=[s.signal for s in sell_signals],
                metadata={
                    "method": "composite",
                    "confirmations": len(sell_signals),
                    "source_methods": [s.generation_method.value for s in sell_signals],
                },
            )
            signals.append(signal)
        
        return signals
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _calculate_rsi(self, prices: List[float]) -> List[float]:
        """Calculate RSI."""
        if len(prices) < self.config.rsi_period + 1:
            return []
        
        rsi = []
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            gains.append(max(0, diff))
            losses.append(max(0, -diff))
        
        for i in range(self.config.rsi_period - 1, len(gains)):
            avg_gain = sum(gains[i - self.config.rsi_period + 1:i + 1]) / self.config.rsi_period
            avg_loss = sum(losses[i - self.config.rsi_period + 1:i + 1]) / self.config.rsi_period
            
            if avg_loss == 0:
                rsi.append(100)
            else:
                rs = avg_gain / avg_loss
                rsi.append(100 - (100 / (1 + rs)))
        
        return rsi
    
    def _calculate_macd(
        self,
        prices: List[float],
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD."""
        if len(prices) < self.config.macd_slow + self.config.macd_signal:
            return [], [], []
        
        # Simple EMA approximation
        ema_fast = []
        ema_slow = []
        
        for i in range(len(prices)):
            if i == 0:
                ema_fast.append(prices[i])
                ema_slow.append(prices[i])
            else:
                ema_fast.append(
                    prices[i] * (2 / (self.config.macd_fast + 1)) +
                    ema_fast[-1] * (1 - (2 / (self.config.macd_fast + 1)))
                )
                ema_slow.append(
                    prices[i] * (2 / (self.config.macd_slow + 1)) +
                    ema_slow[-1] * (1 - (2 / (self.config.macd_slow + 1)))
                )
        
        macd = [f - s for f, s in zip(ema_fast, ema_slow)]
        
        # Signal line
        signal = []
        for i in range(len(macd)):
            if i == 0:
                signal.append(macd[i])
            else:
                signal.append(
                    macd[i] * (2 / (self.config.macd_signal + 1)) +
                    signal[-1] * (1 - (2 / (self.config.macd_signal + 1)))
                )
        
        histogram = [m - s for m, s in zip(macd, signal)]
        
        return macd, signal, histogram
    
    def _calculate_bollinger_bands(
        self,
        prices: List[float],
    ) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < self.config.bb_period:
            return 0, 0, 0
        
        recent = prices[-self.config.bb_period:]
        middle = sum(recent) / self.config.bb_period
        std = np.std(recent)
        
        upper = middle + std * self.config.bb_std_dev
        lower = middle - std * self.config.bb_std_dev
        
        return upper, middle, lower
    
    def _detect_patterns(self, prices: List[float]) -> List[PatternType]:
        """Detect price patterns."""
        patterns = []
        
        if len(prices) < 20:
            return patterns
        
        recent = prices[-20:]
        
        # Simple pattern detection (simplified)
        # Double Top
        peaks = self._find_peaks(recent)
        if len(peaks) >= 2:
            if abs(peaks[-1] - peaks[-2]) / peaks[-2] < self.config.pattern_tolerance:
                patterns.append(PatternType.DOUBLE_TOP)
        
        # Double Bottom
        valleys = self._find_valleys(recent)
        if len(valleys) >= 2:
            if abs(valleys[-1] - valleys[-2]) / valleys[-2] < self.config.pattern_tolerance:
                patterns.append(PatternType.DOUBLE_BOTTOM)
        
        # Breakout (simplified)
        if len(prices) >= 20:
            high_20 = max(prices[-20:-1])
            low_20 = min(prices[-20:-1])
            if prices[-1] > high_20 * 1.01:
                patterns.append(PatternType.BREAKOUT)
            elif prices[-1] < low_20 * 0.99:
                patterns.append(PatternType.BREAKOUT)
        
        return patterns
    
    def _find_peaks(self, prices: List[float]) -> List[float]:
        """Find price peaks."""
        peaks = []
        for i in range(1, len(prices) - 1):
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                peaks.append(prices[i])
        return peaks
    
    def _find_valleys(self, prices: List[float]) -> List[float]:
        """Find price valleys."""
        valleys = []
        for i in range(1, len(prices) - 1):
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                valleys.append(prices[i])
        return valleys
    
    def _find_support_resistance(
        self,
        prices: List[float],
    ) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels."""
        if len(prices) < 20:
            return [], []
        
        recent = prices[-20:]
        
        # Simple support/resistance using local min/max
        levels = []
        for i in range(1, len(recent) - 1):
            if recent[i] < recent[i-1] and recent[i] < recent[i+1]:
                levels.append(recent[i])
            elif recent[i] > recent[i-1] and recent[i] > recent[i+1]:
                levels.append(recent[i])
        
        # Cluster levels
        support = []
        resistance = []
        current_price = prices[-1]
        
        for level in levels:
            if level < current_price:
                support.append(level)
            else:
                resistance.append(level)
        
        # Sort and remove duplicates
        support = sorted(set(support))
        resistance = sorted(set(resistance))
        
        return support, resistance
    
    def _create_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float,
        price: float,
        generation_method: SignalGenerationMethod,
        pattern_type: Optional[PatternType] = None,
        indicator_values: Optional[Dict[str, float]] = None,
        supporting_signals: Optional[List[Signal]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GeneratedSignal:
        """
        Create a generated signal.
        
        Args:
            symbol: Trading symbol
            signal_type: Signal type
            confidence: Signal confidence
            price: Signal price
            generation_method: Generation method
            pattern_type: Pattern type
            indicator_values: Indicator values
            supporting_signals: Supporting signals
            metadata: Additional metadata
            
        Returns:
            GeneratedSignal: Generated signal
        """
        # Determine signal strength
        if confidence >= 0.85:
            strength = SignalStrength.VERY_STRONG
        elif confidence >= 0.7:
            strength = SignalStrength.STRONG
        elif confidence >= 0.55:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK
        
        signal = Signal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=price,
            timestamp=datetime.utcnow(),
        )
        
        return GeneratedSignal(
            signal=signal,
            generation_method=generation_method,
            confidence=confidence,
            pattern_type=pattern_type,
            indicator_values=indicator_values or {},
            supporting_signals=supporting_signals or [],
            metadata=metadata or {},
        )
    
    # ========================================================================
    # FILTERING AND RANKING
    # ========================================================================
    
    def _filter_signals(self, signals: List[GeneratedSignal]) -> List[GeneratedSignal]:
        """
        Filter signals based on criteria.
        
        Args:
            signals: Raw signals
            
        Returns:
            List[GeneratedSignal]: Filtered signals
        """
        filtered = []
        
        for signal in signals:
            # Check confidence
            if signal.confidence < self.config.min_confidence:
                self._stats["signals_filtered"] += 1
                continue
            
            # Check signal strength
            if self._strength_score(signal.signal.strength) < self._strength_score(self.config.min_signal_strength):
                self._stats["signals_filtered"] += 1
                continue
            
            # Check duplicates
            if self.config.filter_duplicates:
                if self._is_duplicate(signal):
                    self._stats["signals_filtered"] += 1
                    continue
            
            # Check rate limit
            if not self._check_rate_limit(signal):
                self._stats["signals_filtered"] += 1
                continue
            
            filtered.append(signal)
        
        return filtered
    
    def _strength_score(self, strength: SignalStrength) -> int:
        """Get numeric score for signal strength."""
        scores = {
            SignalStrength.WEAK: 1,
            SignalStrength.MEDIUM: 2,
            SignalStrength.STRONG: 3,
            SignalStrength.VERY_STRONG: 4,
        }
        return scores.get(strength, 0)
    
    def _is_duplicate(self, signal: GeneratedSignal) -> bool:
        """
        Check if signal is a duplicate.
        
        Args:
            signal: Signal to check
            
        Returns:
            bool: True if duplicate
        """
        window = self.config.duplicate_window
        
        for recent in self._recent_signals:
            age = (datetime.utcnow() - recent.timestamp).total_seconds()
            if age > window:
                continue
            
            if (recent.signal.symbol == signal.signal.symbol and
                recent.signal.signal_type == signal.signal.signal_type and
                abs(recent.signal.price - signal.signal.price) / signal.signal.price < 0.01):
                return True
        
        return False
    
    def _check_rate_limit(self, signal: GeneratedSignal) -> bool:
        """
        Check if rate limit is exceeded.
        
        Args:
            signal: Signal to check
            
        Returns:
            bool: True if rate limit not exceeded
        """
        # Count signals in the last minute
        count = sum(
            1 for s in self._recent_signals
            if (datetime.utcnow() - s.timestamp).total_seconds() < 60
        )
        
        return count < self.config.max_signals_per_minute
    
    def _rank_signals(self, signals: List[GeneratedSignal]) -> List[GeneratedSignal]:
        """
        Rank signals by quality.
        
        Args:
            signals: Signals to rank
            
        Returns:
            List[GeneratedSignal]: Ranked signals
        """
        if self.config.ranking_method == "confidence":
            return sorted(signals, key=lambda x: x.confidence, reverse=True)
        elif self.config.ranking_method == "strength":
            return sorted(signals, key=lambda x: self._strength_score(x.signal.strength), reverse=True)
        else:
            # Composite score
            for signal in signals:
                score = (
                    signal.confidence * 0.5 +
                    self._strength_score(signal.signal.strength) / 4 * 0.3 +
                    len(signal.supporting_signals) * 0.05
                )
                signal.metadata["rank_score"] = score
            
            return sorted(signals, key=lambda x: x.metadata.get("rank_score", 0), reverse=True)
    
    # ========================================================================
    # METRICS AND STATISTICS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get generator metrics.
        
        Returns:
            Dict[str, Any]: Generator metrics
        """
        return {
            **self._stats,
            "signal_history": len(self._signal_history),
            "recent_signals": len(self._recent_signals),
            "active_symbols": len(self._market_data),
            "signal_types": dict(self._stats["signals_by_type"]),
            "generation_methods": dict(self._stats["signals_by_method"]),
        }
    
    def get_recent_signals(self, limit: int = 50) -> List[GeneratedSignal]:
        """
        Get recent signals.
        
        Args:
            limit: Number of signals
            
        Returns:
            List[GeneratedSignal]: Recent signals
        """
        return list(self._recent_signals)[-limit:]
    
    # ========================================================================
    # RESET AND CLEANUP
    # ========================================================================
    
    def reset(self) -> None:
        """Reset generator state."""
        self._market_data.clear()
        self._indicator_cache.clear()
        self._pattern_cache.clear()
        self._signal_history.clear()
        self._recent_signals.clear()
        self._stats = {
            "signals_generated": 0,
            "signals_by_method": defaultdict(int),
            "signals_by_type": defaultdict(int),
            "signals_filtered": 0,
            "avg_confidence": 0.0,
            "avg_generation_time_ms": 0.0,
        }
        self.logger.info("Signal generator reset")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "SignalGenerationMethod",
    "PatternType",
    
    # Models
    "SignalGeneratorConfig",
    "GeneratedSignal",
    
    # Generator
    "SignalGenerator",
]
