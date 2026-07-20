# trading/bots/arbitrage_bot/detectors/signal_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Trading Signal Detection Engine

"""
Signal Detector - Advanced Trading Signal Detection Engine

This module provides sophisticated trading signal detection capabilities:
- Multi-timeframe signal detection
- Technical indicator-based signals
- Machine learning-based signal detection
- Pattern recognition
- Divergence detection
- Signal strength scoring
- Signal confirmation
- Signal filtering and prioritization

Architecture:
    - BaseSignalDetector: Abstract base class
    - SignalDetector: Main detector implementation
    - IndicatorEngine: Technical indicator calculation
    - PatternRecognizer: Pattern recognition engine
    - DivergenceDetector: Divergence detection
    - SignalScorer: Signal scoring and ranking
    - SignalFilter: Signal filtering and validation
    - MLSignalDetector: ML-based signal detection

Signal Types:
    - Entry signals (Long/Short)
    - Exit signals
    - Trend signals
    - Reversal signals
    - Breakout signals
    - Momentum signals
    - Divergence signals
    - Pattern signals
    - Volume signals
    - Volatility signals
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    TypeVar,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    overload,
    Protocol,
    runtime_checkable,
)
from functools import lru_cache, wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from itertools import combinations, permutations, product
from contextlib import asynccontextmanager, contextmanager
from typing_extensions import TypedDict, NotRequired

import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks, argrelextrema
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPClassifier
import ta  # Technical Analysis library
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolume, VolumeWeightedAveragePrice

# Constants
MIN_SIGNAL_CONFIDENCE = Decimal("0.6")
MAX_SIGNALS_PER_SCAN = 50
HISTORICAL_WINDOW = 200
SIGNAL_CACHE_SIZE = 1000
MIN_PRICE_SAMPLES = 20

# Signal types
class SignalType(Enum):
    ENTRY_LONG = "entry_long"
    ENTRY_SHORT = "entry_short"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"
    TREND_BULLISH = "trend_bullish"
    TREND_BEARISH = "trend_bearish"
    REVERSAL_BULLISH = "reversal_bullish"
    REVERSAL_BEARISH = "reversal_bearish"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    MOMENTUM_UP = "momentum_up"
    MOMENTUM_DOWN = "momentum_down"
    DIVERGENCE_BULLISH = "divergence_bullish"
    DIVERGENCE_BEARISH = "divergence_bearish"
    PATTERN = "pattern"
    VOLUME_SURGE = "volume_surge"
    VOLATILITY_EXPANSION = "volatility_expansion"
    VOLATILITY_CONTRACTION = "volatility_contraction"
    OVERSOLD = "oversold"
    OVERBOUGHT = "overbought"

# Signal priority
class SignalPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4

# Timeframes
class Timeframe(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    MN1 = "1M"

@dataclass
class Signal:
    """Trading signal data."""
    signal_type: SignalType
    symbol: str
    price: Decimal
    timestamp: datetime
    confidence: Decimal
    strength: Decimal
    timeframe: Timeframe
    indicators: Dict[str, Any]
    supporting_signals: List["Signal"]
    priority: SignalPriority
    entry_price: Optional[Decimal] = None
    exit_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    targets: List[Decimal] = field(default_factory=list)
    reason: str = ""
    source: str = "technical"
    expires_at: Optional[datetime] = None
    signature: Optional[str] = None

@dataclass
class IndicatorData:
    """Technical indicator data."""
    name: str
    value: Decimal
    previous_value: Optional[Decimal] = None
    history: List[Decimal] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class PatternData:
    """Chart pattern data."""
    pattern_name: str
    symbol: str
    start_price: Decimal
    end_price: Decimal
    start_time: datetime
    end_time: datetime
    confidence: Decimal
    breakout_price: Optional[Decimal] = None
    target_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DivergenceData:
    """Divergence detection data."""
    symbol: str
    type: str  # "bullish" or "bearish"
    price: Decimal
    indicator: str
    price_peaks: List[Decimal]
    indicator_peaks: List[Decimal]
    strength: Decimal
    confidence: Decimal
    timestamp: datetime

class SignalDetector:
    """
    Advanced Trading Signal Detection Engine.
    
    This class provides comprehensive signal detection capabilities:
    1. Multi-timeframe signal detection
    2. Technical indicator-based signals
    3. ML-based signal detection
    4. Pattern recognition
    5. Divergence detection
    6. Signal scoring and ranking
    7. Signal confirmation
    8. Signal filtering
    
    Features:
    - Real-time signal detection
    - Multiple timeframe analysis
    - ML model integration
    - Pattern recognition
    - Divergence detection
    - Signal validation
    - Priority-based filtering
    - WebSocket support
    """
    
    def __init__(
        self,
        min_confidence: Decimal = MIN_SIGNAL_CONFIDENCE,
        timeframes: Optional[List[Timeframe]] = None,
        scan_interval: float = 1.0,
    ):
        """
        Initialize the Signal Detector.
        
        Args:
            min_confidence: Minimum confidence for signal acceptance
            timeframes: Timeframes to analyze
            scan_interval: Scan interval in seconds
        """
        self.logger = self._setup_logger()
        self.min_confidence = min_confidence
        self.timeframes = timeframes or [
            Timeframe.M1, Timeframe.M5, Timeframe.M15,
            Timeframe.H1, Timeframe.H4, Timeframe.D1
        ]
        self.scan_interval = scan_interval
        
        # Signal storage
        self.signals: Dict[str, List[Signal]] = {}
        self.active_signals: Dict[str, Signal] = {}
        self.signal_cache: Dict[str, Signal] = {}
        
        # Indicator data
        self.indicator_cache: Dict[str, Dict[str, IndicatorData]] = {}
        self.price_history: Dict[str, Dict[Timeframe, List[Decimal]]] = {}
        
        # Pattern data
        self.patterns: Dict[str, List[PatternData]] = {}
        
        # Divergence data
        self.divergences: Dict[str, List[DivergenceData]] = {}
        
        # ML models
        self.ml_models: Dict[str, Any] = {}
        self._init_ml_models()
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Metrics
        self.metrics = {
            "signals_generated": 0,
            "signals_executed": 0,
            "signals_expired": 0,
            "avg_confidence": Decimal("0"),
            "signal_types": defaultdict(int),
            "timeframe_signals": defaultdict(int),
            "errors": 0,
            "accuracy": Decimal("0.7"),
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        
        # Start scanner
        self.start()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the detector."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _init_ml_models(self) -> None:
        """Initialize ML models for signal detection."""
        # Random Forest for classification
        self.ml_models["rf"] = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        
        # Gradient Boosting
        self.ml_models["gb"] = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            random_state=42
        )
        
        # Neural Network
        self.ml_models["nn"] = MLPClassifier(
            hidden_layer_sizes=(100, 50),
            max_iter=1000,
            random_state=42
        )
    
    def start(self) -> None:
        """Start the signal detector."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        
        self.logger.info("Signal Detector started")
    
    def stop(self) -> None:
        """Stop the signal detector."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        self.logger.info("Signal Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main signal scanning loop."""
        while self.is_running:
            try:
                # Analyze each symbol
                symbols = list(self.price_history.keys())
                for symbol in symbols:
                    signals = self._analyze_symbol(symbol)
                    if signals:
                        self._process_signals(symbol, signals)
                
                # Clean expired signals
                self._clean_expired_signals()
                
                # Sleep until next scan
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                self.metrics["errors"] += 1
                time.sleep(1.0)
    
    def _analyze_symbol(self, symbol: str) -> List[Signal]:
        """
        Analyze a symbol for trading signals.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of detected signals
        """
        signals = []
        
        # Get price data
        price_data = self.price_history.get(symbol, {})
        if not price_data:
            return signals
        
        # Analyze each timeframe
        for timeframe in self.timeframes:
            prices = price_data.get(timeframe, [])
            if len(prices) < MIN_PRICE_SAMPLES:
                continue
            
            # Convert to numpy array
            price_array = np.array([float(p) for p in prices])
            
            # Calculate indicators
            indicators = self._calculate_indicators(price_array)
            
            # Detect signals
            timeframe_signals = self._detect_signals(
                symbol,
                timeframe,
                price_array,
                indicators
            )
            
            if timeframe_signals:
                signals.extend(timeframe_signals)
        
        # Limit signals
        if len(signals) > MAX_SIGNALS_PER_SCAN:
            signals = signals[:MAX_SIGNALS_PER_SCAN]
        
        return signals
    
    def _calculate_indicators(self, prices: np.ndarray) -> Dict[str, Any]:
        """
        Calculate technical indicators.
        
        Args:
            prices: Price array
            
        Returns:
            Dictionary of indicators
        """
        indicators = {}
        
        # Ensure we have enough data
        if len(prices) < 20:
            return indicators
        
        # Create pandas Series
        s = pd.Series(prices)
        
        # Trend indicators
        if len(prices) >= 26:
            # MACD
            macd = MACD(s)
            indicators["macd"] = macd.macd().iloc[-1]
            indicators["macd_signal"] = macd.macd_signal().iloc[-1]
            indicators["macd_diff"] = macd.macd_diff().iloc[-1]
        
        # Moving averages
        if len(prices) >= 20:
            indicators["sma_20"] = SMAIndicator(s, 20).sma_indicator().iloc[-1]
            indicators["ema_12"] = EMAIndicator(s, 12).ema_indicator().iloc[-1]
            indicators["ema_26"] = EMAIndicator(s, 26).ema_indicator().iloc[-1]
        
        # Momentum indicators
        if len(prices) >= 14:
            # RSI
            rsi = RSIIndicator(s, 14)
            indicators["rsi"] = rsi.rsi().iloc[-1]
            
            # Stochastic
            stoch = StochasticOscillator(s, s, s, 14, 3, 3)
            indicators["stoch_k"] = stoch.stoch().iloc[-1]
            indicators["stoch_d"] = stoch.stoch_signal().iloc[-1]
            
            # Williams %R
            williams = WilliamsRIndicator(s, s, s, 14)
            indicators["williams_r"] = williams.williams_r().iloc[-1]
        
        # Volatility indicators
        if len(prices) >= 20:
            # Bollinger Bands
            bb = BollingerBands(s, 20, 2)
            indicators["bb_high"] = bb.bollinger_hband().iloc[-1]
            indicators["bb_mid"] = bb.bollinger_mavg().iloc[-1]
            indicators["bb_low"] = bb.bollinger_lband().iloc[-1]
            indicators["bb_width"] = bb.bollinger_wband().iloc[-1]
            indicators["bb_percent"] = bb.bollinger_pband().iloc[-1]
            
            # ATR
            atr = AverageTrueRange(s, s, s, 14)
            indicators["atr"] = atr.average_true_range().iloc[-1]
            indicators["atr_percent"] = atr.average_true_range().iloc[-1] / prices[-1]
        
        # Volume indicators (if available)
        # OBV and VWAP would require volume data
        
        return indicators
    
    def _detect_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        prices: np.ndarray,
        indicators: Dict[str, Any],
    ) -> List[Signal]:
        """
        Detect trading signals from indicators.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            prices: Price array
            indicators: Indicator dictionary
            
        Returns:
            List of detected signals
        """
        signals = []
        current_price = Decimal(str(prices[-1]))
        
        # Trend signals
        trend_signal = self._detect_trend_signals(symbol, timeframe, prices, indicators)
        if trend_signal:
            signals.append(trend_signal)
        
        # Momentum signals
        momentum_signal = self._detect_momentum_signals(symbol, timeframe, indicators)
        if momentum_signal:
            signals.append(momentum_signal)
        
        # Volatility signals
        volatility_signal = self._detect_volatility_signals(symbol, timeframe, indicators)
        if volatility_signal:
            signals.append(volatility_signal)
        
        # Overbought/Oversold signals
        obos_signal = self._detect_obos_signals(symbol, timeframe, indicators)
        if obos_signal:
            signals.append(obos_signal)
        
        # Pattern signals
        pattern_signal = self._detect_pattern_signals(symbol, timeframe, prices)
        if pattern_signal:
            signals.append(pattern_signal)
        
        # Divergence signals
        divergence_signal = self._detect_divergence(symbol, timeframe, prices, indicators)
        if divergence_signal:
            signals.append(divergence_signal)
        
        # ML-based signals
        ml_signals = self._detect_ml_signals(symbol, timeframe, prices, indicators)
        if ml_signals:
            signals.extend(ml_signals)
        
        return signals
    
    def _detect_trend_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        prices: np.ndarray,
        indicators: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Detect trend-based signals.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            prices: Price array
            indicators: Indicator dictionary
            
        Returns:
            Signal or None
        """
        if len(prices) < 50:
            return None
        
        current_price = Decimal(str(prices[-1]))
        
        # Check moving average alignment
        if "sma_20" in indicators and "ema_12" in indicators and "ema_26" in indicators:
            sma_20 = Decimal(str(indicators["sma_20"]))
            ema_12 = Decimal(str(indicators["ema_12"]))
            ema_26 = Decimal(str(indicators["ema_26"]))
            
            # Bullish trend: Price > SMA20 > EMA12 > EMA26
            if (current_price > sma_20 and sma_20 > ema_12 and ema_12 > ema_26):
                confidence = Decimal("0.7")
                return Signal(
                    signal_type=SignalType.TREND_BULLISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.8"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    reason="Strong bullish trend confirmed by MA alignment",
                    source="trend",
                )
            
            # Bearish trend: Price < SMA20 < EMA12 < EMA26
            elif (current_price < sma_20 and sma_20 < ema_12 and ema_12 < ema_26):
                confidence = Decimal("0.7")
                return Signal(
                    signal_type=SignalType.TREND_BEARISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.8"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    reason="Strong bearish trend confirmed by MA alignment",
                    source="trend",
                )
        
        # MACD signals
        if "macd" in indicators and "macd_signal" in indicators:
            macd = Decimal(str(indicators["macd"]))
            signal = Decimal(str(indicators["macd_signal"]))
            
            # MACD crossover
            if macd > signal:
                confidence = Decimal("0.65")
                return Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.7"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.HIGH,
                    entry_price=current_price,
                    reason="MACD bullish crossover",
                    source="trend",
                )
            elif macd < signal:
                confidence = Decimal("0.65")
                return Signal(
                    signal_type=SignalType.ENTRY_SHORT,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.7"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.HIGH,
                    entry_price=current_price,
                    reason="MACD bearish crossover",
                    source="trend",
                )
        
        return None
    
    def _detect_momentum_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Detect momentum-based signals.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicators: Indicator dictionary
            
        Returns:
            Signal or None
        """
        current_price = Decimal(str(indicators.get("price", 0)))
        
        # RSI signals
        if "rsi" in indicators:
            rsi = Decimal(str(indicators["rsi"]))
            
            # RSI oversold - potential reversal up
            if rsi < 30:
                confidence = Decimal("0.7")
                return Signal(
                    signal_type=SignalType.REVERSAL_BULLISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.75"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.HIGH,
                    entry_price=current_price,
                    reason=f"RSI oversold at {rsi:.1f}",
                    source="momentum",
                )
            
            # RSI overbought - potential reversal down
            elif rsi > 70:
                confidence = Decimal("0.7")
                return Signal(
                    signal_type=SignalType.REVERSAL_BEARISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.75"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.HIGH,
                    entry_price=current_price,
                    reason=f"RSI overbought at {rsi:.1f}",
                    source="momentum",
                )
        
        # Stochastic signals
        if "stoch_k" in indicators and "stoch_d" in indicators:
            stoch_k = Decimal(str(indicators["stoch_k"]))
            stoch_d = Decimal(str(indicators["stoch_d"]))
            
            # Stochastic crossover
            if stoch_k > stoch_d and stoch_k < 30:
                confidence = Decimal("0.6")
                return Signal(
                    signal_type=SignalType.ENTRY_LONG,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.65"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    entry_price=current_price,
                    reason="Stochastic bullish crossover in oversold zone",
                    source="momentum",
                )
            elif stoch_k < stoch_d and stoch_k > 70:
                confidence = Decimal("0.6")
                return Signal(
                    signal_type=SignalType.ENTRY_SHORT,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.65"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    entry_price=current_price,
                    reason="Stochastic bearish crossover in overbought zone",
                    source="momentum",
                )
        
        return None
    
    def _detect_volatility_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Detect volatility-based signals.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicators: Indicator dictionary
            
        Returns:
            Signal or None
        """
        current_price = Decimal(str(indicators.get("price", 0)))
        
        # Bollinger Bands signals
        if "bb_high" in indicators and "bb_low" in indicators:
            bb_high = Decimal(str(indicators["bb_high"]))
            bb_low = Decimal(str(indicators["bb_low"]))
            bb_percent = Decimal(str(indicators.get("bb_percent", 0.5)))
            
            # Price touching lower band - potential bounce
            if current_price <= bb_low and bb_percent < 0.1:
                confidence = Decimal("0.65")
                return Signal(
                    signal_type=SignalType.REVERSAL_BULLISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.7"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    entry_price=current_price,
                    reason="Price at lower Bollinger Band - potential bounce",
                    source="volatility",
                )
            
            # Price touching upper band - potential pullback
            elif current_price >= bb_high and bb_percent > 0.9:
                confidence = Decimal("0.65")
                return Signal(
                    signal_type=SignalType.REVERSAL_BEARISH,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.7"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.MEDIUM,
                    entry_price=current_price,
                    reason="Price at upper Bollinger Band - potential pullback",
                    source="volatility",
                )
        
        # ATR signals - volatility expansion/contraction
        if "atr_percent" in indicators:
            atr_pct = Decimal(str(indicators["atr_percent"]))
            
            # Volatility expansion
            if atr_pct > Decimal("0.05"):
                confidence = Decimal("0.55")
                return Signal(
                    signal_type=SignalType.VOLATILITY_EXPANSION,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.6"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.LOW,
                    reason=f"High volatility detected (ATR {atr_pct:.2%})",
                    source="volatility",
                )
            
            # Volatility contraction
            elif atr_pct < Decimal("0.01"):
                confidence = Decimal("0.55")
                return Signal(
                    signal_type=SignalType.VOLATILITY_CONTRACTION,
                    symbol=symbol,
                    price=current_price,
                    timestamp=datetime.utcnow(),
                    confidence=confidence,
                    strength=Decimal("0.6"),
                    timeframe=timeframe,
                    indicators=indicators,
                    supporting_signals=[],
                    priority=SignalPriority.LOW,
                    reason=f"Low volatility detected (ATR {atr_pct:.2%})",
                    source="volatility",
                )
        
        return None
    
    def _detect_obos_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        indicators: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Detect overbought/oversold signals.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            indicators: Indicator dictionary
            
        Returns:
            Signal or None
        """
        current_price = Decimal(str(indicators.get("price", 0)))
        
        # Multiple indicators confirmation
        oversold_count = 0
        overbought_count = 0
        
        if "rsi" in indicators:
            rsi = Decimal(str(indicators["rsi"]))
            if rsi < 30:
                oversold_count += 1
            elif rsi > 70:
                overbought_count += 1
        
        if "stoch_k" in indicators:
            stoch_k = Decimal(str(indicators["stoch_k"]))
            if stoch_k < 20:
                oversold_count += 1
            elif stoch_k > 80:
                overbought_count += 1
        
        if "williams_r" in indicators:
            williams = Decimal(str(indicators["williams_r"]))
            if williams < -80:
                oversold_count += 1
            elif williams > -20:
                overbought_count += 1
        
        # Oversold signal
        if oversold_count >= 2:
            confidence = Decimal(str(0.6 + 0.1 * oversold_count))
            return Signal(
                signal_type=SignalType.OVERSOLD,
                symbol=symbol,
                price=current_price,
                timestamp=datetime.utcnow(),
                confidence=min(confidence, Decimal("0.9")),
                strength=Decimal("0.7"),
                timeframe=timeframe,
                indicators=indicators,
                supporting_signals=[],
                priority=SignalPriority.HIGH,
                reason=f"Multiple indicators confirm oversold ({oversold_count} indicators)",
                source="obos",
            )
        
        # Overbought signal
        elif overbought_count >= 2:
            confidence = Decimal(str(0.6 + 0.1 * overbought_count))
            return Signal(
                signal_type=SignalType.OVERBOUGHT,
                symbol=symbol,
                price=current_price,
                timestamp=datetime.utcnow(),
                confidence=min(confidence, Decimal("0.9")),
                strength=Decimal("0.7"),
                timeframe=timeframe,
                indicators=indicators,
                supporting_signals=[],
                priority=SignalPriority.HIGH,
                reason=f"Multiple indicators confirm overbought ({overbought_count} indicators)",
                source="obos",
            )
        
        return None
    
    def _detect_pattern_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        prices: np.ndarray,
    ) -> Optional[Signal]:
        """
        Detect chart pattern signals.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            prices: Price array
            
        Returns:
            Signal or None
        """
        if len(prices) < 30:
            return None
        
        current_price = Decimal(str(prices[-1]))
        
        # Find local minima and maxima
        maxima = argrelextrema(prices, np.greater)[0]
        minima = argrelextrema(prices, np.less)[0]
        
        # Double Bottom pattern
        if len(minima) >= 2:
            last_min = minima[-1]
            prev_min = minima[-2]
            
            # Check if they are at similar levels
            if last_min > 0 and prev_min > 0:
                last_price = prices[last_min]
                prev_price = prices[prev_min]
                
                if abs(last_price - prev_price) / prev_price < 0.05:
                    # Check if price is breaking above the middle peak
                    middle_peak = max(prices[minima[-1]:last_min]) if last_min > minima[-1] else current_price
                    if current_price > Decimal(str(middle_peak * 1.01)):
                        confidence = Decimal("0.7")
                        pattern = PatternData(
                            pattern_name="double_bottom",
                            symbol=symbol,
                            start_price=Decimal(str(prev_price)),
                            end_price=Decimal(str(last_price)),
                            start_time=datetime.utcnow() - timedelta(hours=1),
                            end_time=datetime.utcnow(),
                            confidence=confidence,
                            breakout_price=current_price,
                            target_price=current_price * Decimal("1.05"),
                            stop_loss=Decimal(str(prev_price * 0.98)),
                            parameters={"height": abs(last_price - prev_price)},
                        )
                        
                        return Signal(
                            signal_type=SignalType.PATTERN,
                            symbol=symbol,
                            price=current_price,
                            timestamp=datetime.utcnow(),
                            confidence=confidence,
                            strength=Decimal("0.75"),
                            timeframe=timeframe,
                            indicators={},
                            supporting_signals=[],
                            priority=SignalPriority.HIGH,
                            entry_price=current_price,
                            reason="Double Bottom pattern detected",
                            source="pattern",
                        )
        
        # Double Top pattern
        if len(maxima) >= 2:
            last_max = maxima[-1]
            prev_max = maxima[-2]
            
            if last_max > 0 and prev_max > 0:
                last_price = prices[last_max]
                prev_price = prices[prev_max]
                
                if abs(last_price - prev_price) / prev_price < 0.05:
                    # Check if price is breaking below the middle trough
                    middle_trough = min(prices[maxima[-1]:last_max]) if last_max > maxima[-1] else current_price
                    if current_price < Decimal(str(middle_trough * 0.99)):
                        confidence = Decimal("0.7")
                        return Signal(
                            signal_type=SignalType.PATTERN,
                            symbol=symbol,
                            price=current_price,
                            timestamp=datetime.utcnow(),
                            confidence=confidence,
                            strength=Decimal("0.75"),
                            timeframe=timeframe,
                            indicators={},
                            supporting_signals=[],
                            priority=SignalPriority.HIGH,
                            entry_price=current_price,
                            reason="Double Top pattern detected",
                            source="pattern",
                        )
        
        return None
    
    def _detect_divergence(
        self,
        symbol: str,
        timeframe: Timeframe,
        prices: np.ndarray,
        indicators: Dict[str, Any],
    ) -> Optional[Signal]:
        """
        Detect divergence between price and indicators.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            prices: Price array
            indicators: Indicator dictionary
            
        Returns:
            Signal or None
        """
        if len(prices) < 30:
            return None
        
        current_price = Decimal(str(prices[-1]))
        
        # Check RSI divergence
        if "rsi" in indicators and len(prices) >= 20:
            rsi_values = indicators.get("rsi_history", [])
            if len(rsi_values) >= 20:
                # Find recent peaks/troughs
                price_minima = argrelextrema(prices, np.less)[0]
                rsi_minima = argrelextrema(np.array(rsi_values), np.less)[0]
                
                # Bullish divergence: price makes lower low, RSI makes higher low
                if len(price_minima) >= 2 and len(rsi_minima) >= 2:
                    price_low1 = prices[price_minima[-2]]
                    price_low2 = prices[price_minima[-1]]
                    rsi_low1 = rsi_values[rsi_minima[-2]]
                    rsi_low2 = rsi_values[rsi_minima[-1]]
                    
                    if price_low2 < price_low1 and rsi_low2 > rsi_low1:
                        confidence = Decimal("0.75")
                        divergence = DivergenceData(
                            symbol=symbol,
                            type="bullish",
                            price=current_price,
                            indicator="RSI",
                            price_peaks=[Decimal(str(price_low1)), Decimal(str(price_low2))],
                            indicator_peaks=[Decimal(str(rsi_low1)), Decimal(str(rsi_low2))],
                            strength=Decimal("0.8"),
                            confidence=confidence,
                            timestamp=datetime.utcnow(),
                        )
                        
                        return Signal(
                            signal_type=SignalType.DIVERGENCE_BULLISH,
                            symbol=symbol,
                            price=current_price,
                            timestamp=datetime.utcnow(),
                            confidence=confidence,
                            strength=Decimal("0.8"),
                            timeframe=timeframe,
                            indicators=indicators,
                            supporting_signals=[],
                            priority=SignalPriority.HIGH,
                            entry_price=current_price,
                            reason="Bullish RSI divergence detected",
                            source="divergence",
                        )
        
        return None
    
    def _detect_ml_signals(
        self,
        symbol: str,
        timeframe: Timeframe,
        prices: np.ndarray,
        indicators: Dict[str, Any],
    ) -> List[Signal]:
        """
        Detect signals using ML models.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            prices: Price array
            indicators: Indicator dictionary
            
        Returns:
            List of ML signals
        """
        signals = []
        
        # Prepare features
        features = []
        feature_names = []
        
        # Add price features
        if len(prices) >= 20:
            returns = np.diff(prices) / prices[:-1]
            features.extend([
                np.mean(returns[-5:]),
                np.std(returns[-5:]),
                np.mean(returns[-10:]),
                np.std(returns[-10:]),
            ])
            feature_names.extend([
                "return_5_mean", "return_5_std",
                "return_10_mean", "return_10_std",
            ])
        
        # Add indicator features
        for key, value in indicators.items():
            if isinstance(value, (int, float)):
                features.append(value)
                feature_names.append(key)
        
        # Add technical features
        if len(prices) >= 50:
            # Volatility
            volatility = np.std(prices[-20:]) / np.mean(prices[-20:])
            features.append(volatility)
            feature_names.append("volatility")
            
            # Trend strength
            sma_20 = np.mean(prices[-20:])
            sma_50 = np.mean(prices[-50:])
            trend_strength = (sma_20 - sma_50) / sma_50
            features.append(trend_strength)
            feature_names.append("trend_strength")
        
        if len(features) < 10:
            return signals
        
        # Normalize features
        scaler = StandardScaler()
        X = scaler.fit_transform([features])
        
        # Make predictions using ensemble
        predictions = []
        for model_name, model in self.ml_models.items():
            try:
                pred = model.predict(X)
                proba = model.predict_proba(X) if hasattr(model, "predict_proba") else None
                predictions.append((pred[0], proba[0] if proba is not None else None))
            except Exception:
                continue
        
        if not predictions:
            return signals
        
        # Aggregate predictions
        long_votes = sum(1 for p, _ in predictions if p == 1)
        short_votes = sum(1 for p, _ in predictions if p == 0)
        
        total_votes = len(predictions)
        current_price = Decimal(str(prices[-1]))
        
        # Long signal
        if long_votes / total_votes > 0.6:
            confidence = Decimal(str(long_votes / total_votes))
            signals.append(Signal(
                signal_type=SignalType.ENTRY_LONG,
                symbol=symbol,
                price=current_price,
                timestamp=datetime.utcnow(),
                confidence=confidence,
                strength=confidence * Decimal("0.8"),
                timeframe=timeframe,
                indicators=indicators,
                supporting_signals=[],
                priority=SignalPriority.MEDIUM,
                entry_price=current_price,
                reason=f"ML model consensus for long ({long_votes}/{total_votes})",
                source="ml_ensemble",
            ))
        
        # Short signal
        if short_votes / total_votes > 0.6:
            confidence = Decimal(str(short_votes / total_votes))
            signals.append(Signal(
                signal_type=SignalType.ENTRY_SHORT,
                symbol=symbol,
                price=current_price,
                timestamp=datetime.utcnow(),
                confidence=confidence,
                strength=confidence * Decimal("0.8"),
                timeframe=timeframe,
                indicators=indicators,
                supporting_signals=[],
                priority=SignalPriority.MEDIUM,
                entry_price=current_price,
                reason=f"ML model consensus for short ({short_votes}/{total_votes})",
                source="ml_ensemble",
            ))
        
        return signals
    
    def _process_signals(self, symbol: str, signals: List[Signal]) -> None:
        """
        Process detected signals.
        
        Args:
            symbol: Trading symbol
            signals: List of signals
        """
        # Filter by confidence
        filtered = [s for s in signals if s.confidence >= self.min_confidence]
        
        if not filtered:
            return
        
        # Sort by priority and strength
        filtered.sort(key=lambda s: (s.priority.value, float(s.strength)))
        
        # Store signals
        if symbol not in self.signals:
            self.signals[symbol] = []
        
        for signal in filtered:
            # Generate signature
            signal.signature = self._generate_signal_signature(signal)
            
            # Cache signal
            self.signals[symbol].append(signal)
            self.signal_cache[signal.signature] = signal
            
            # Update active signals
            if signal.signal_type in [SignalType.ENTRY_LONG, SignalType.ENTRY_SHORT]:
                self.active_signals[symbol] = signal
            
            # Update metrics
            self.metrics["signals_generated"] += 1
            self.metrics["signal_types"][signal.signal_type.value] += 1
            self.metrics["timeframe_signals"][signal.timeframe.value] += 1
            
            # Log signal
            self.logger.info(
                f"Signal generated: {signal.signal_type.value} for {symbol} "
                f"at ${float(signal.price):.2f} with confidence {float(signal.confidence):.2f}"
            )
        
        # Trim signals if needed
        if len(self.signals[symbol]) > SIGNAL_CACHE_SIZE:
            self.signals[symbol] = self.signals[symbol][-SIGNAL_CACHE_SIZE:]
    
    def _generate_signal_signature(self, signal: Signal) -> str:
        """
        Generate unique signature for a signal.
        
        Args:
            signal: Signal object
            
        Returns:
            Unique signature string
        """
        data = [
            signal.symbol,
            signal.signal_type.value,
            signal.timeframe.value,
            str(float(signal.price)),
            signal.timestamp.strftime("%Y%m%d%H%M%S"),
        ]
        return hashlib.md5(":".join(data).encode()).hexdigest()
    
    def _clean_expired_signals(self) -> None:
        """Clean expired signals from cache."""
        now = datetime.utcnow()
        expired_count = 0
        
        # Clean expired signals
        for symbol in list(self.signals.keys()):
            self.signals[symbol] = [
                s for s in self.signals[symbol]
                if s.expires_at is None or s.expires_at > now
            ]
            expired_count += len([s for s in self.signals[symbol] if s.expires_at and s.expires_at <= now])
        
        self.metrics["signals_expired"] += expired_count
    
    def update_price_data(
        self,
        symbol: str,
        price: Decimal,
        timeframe: Timeframe = Timeframe.M1,
    ) -> None:
        """
        Update price data for a symbol.
        
        Args:
            symbol: Trading symbol
            price: Current price
            timeframe: Timeframe
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = {}
        
        if timeframe not in self.price_history[symbol]:
            self.price_history[symbol][timeframe] = []
        
        self.price_history[symbol][timeframe].append(price)
        
        # Trim history
        if len(self.price_history[symbol][timeframe]) > HISTORICAL_WINDOW:
            self.price_history[symbol][timeframe] = self.price_history[symbol][timeframe][-HISTORICAL_WINDOW:]
    
    def get_signals(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[SignalType] = None,
        min_confidence: Optional[Decimal] = None,
        limit: int = 50,
    ) -> List[Signal]:
        """
        Get detected signals.
        
        Args:
            symbol: Optional symbol filter
            signal_type: Optional signal type filter
            min_confidence: Optional minimum confidence
            limit: Maximum number of signals to return
            
        Returns:
            List of signals
        """
        all_signals = []
        
        symbols = [symbol] if symbol else list(self.signals.keys())
        for sym in symbols:
            if sym in self.signals:
                all_signals.extend(self.signals[sym])
        
        # Apply filters
        if signal_type:
            all_signals = [s for s in all_signals if s.signal_type == signal_type]
        
        if min_confidence:
            all_signals = [s for s in all_signals if s.confidence >= min_confidence]
        
        # Sort by priority and confidence
        all_signals.sort(
            key=lambda s: (s.priority.value, float(s.confidence)),
            reverse=True
        )
        
        return all_signals[:limit]
    
    def get_active_signals(self) -> Dict[str, Signal]:
        """
        Get active (unexecuted) entry signals.
        
        Returns:
            Dictionary of active signals by symbol
        """
        return self.active_signals.copy()
    
    def get_signal_by_id(self, signal_id: str) -> Optional[Signal]:
        """
        Get a signal by its signature.
        
        Args:
            signal_id: Signal signature
            
        Returns:
            Signal or None
        """
        return self.signal_cache.get(signal_id)
    
    def confirm_signal(self, signal: Signal, confirmation_count: int = 2) -> bool:
        """
        Confirm a signal by checking supporting signals.
        
        Args:
            signal: Signal to confirm
            confirmation_count: Number of confirmations required
            
        Returns:
            True if confirmed
        """
        # Get supporting signals
        supporting = [
            s for s in self.signals.get(signal.symbol, [])
            if s.signature != signal.signature and
            s.confidence >= Decimal("0.5") and
            s.timestamp > signal.timestamp - timedelta(minutes=5)
        ]
        
        # Check for signals in the same direction
        bullish_signal_types = [
            SignalType.ENTRY_LONG,
            SignalType.TREND_BULLISH,
            SignalType.REVERSAL_BULLISH,
            SignalType.DIVERGENCE_BULLISH,
            SignalType.MOMENTUM_UP,
        ]
        
        bearish_signal_types = [
            SignalType.ENTRY_SHORT,
            SignalType.TREND_BEARISH,
            SignalType.REVERSAL_BEARISH,
            SignalType.DIVERGENCE_BEARISH,
            SignalType.MOMENTUM_DOWN,
        ]
        
        if signal.signal_type in bullish_signal_types:
            confirmations = [
                s for s in supporting
                if s.signal_type in bullish_signal_types
            ]
        else:
            confirmations = [
                s for s in supporting
                if s.signal_type in bearish_signal_types
            ]
        
        return len(confirmations) >= confirmation_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "signals_generated": self.metrics["signals_generated"],
            "signals_executed": self.metrics["signals_executed"],
            "signals_expired": self.metrics["signals_expired"],
            "avg_confidence": float(self.metrics["avg_confidence"]),
            "active_signals": len(self.active_signals),
            "symbols_tracked": len(self.signals),
            "signal_types": dict(self.metrics["signal_types"]),
            "timeframe_signals": dict(self.metrics["timeframe_signals"]),
            "errors": self.metrics["errors"],
            "accuracy": float(self.metrics["accuracy"]),
            "is_running": self.is_running,
            "scan_interval": self.scan_interval,
        }


# Module exports
__all__ = [
    'SignalDetector',
    'Signal',
    'SignalType',
    'SignalPriority',
    'Timeframe',
    'IndicatorData',
    'PatternData',
    'DivergenceData',
]
