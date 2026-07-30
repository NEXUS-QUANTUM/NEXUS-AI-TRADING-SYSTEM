# trading/bots/hedge_bot/hedge_bot_analyzer.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Analyzer Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Analyzer Module

This module provides comprehensive market analysis and pattern recognition
capabilities for the NEXUS Hedge Bot system. It includes technical analysis,
pattern detection, market profiling, and signal generation.

The module covers:
- Technical Indicators
- Pattern Recognition
- Market Profiling
- Volume Analysis
- Order Flow Analysis
- Sentiment Analysis
- Market Structure Analysis
- Support/Resistance Detection
- Trend Analysis
- Volatility Analysis
- Correlation Analysis
- Signal Generation
- Backtesting
- Optimization
"""

import os
import sys
import json
import math
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from scipy import stats
from scipy.signal import find_peaks, argrelextrema
from scipy.optimize import minimize

# Try to import optional dependencies
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

logger = logging.getLogger(__name__)


# ============================================================
# ANALYZER DATACLASSES
# ============================================================

@dataclass
class TechnicalIndicators:
    """Technical indicators data"""
    symbol: str
    timestamp: datetime
    sma_10: float = 0.0
    sma_20: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    ema_12: float = 0.0
    ema_26: float = 0.0
    rsi: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    bollinger_upper: float = 0.0
    bollinger_middle: float = 0.0
    bollinger_lower: float = 0.0
    atr: float = 0.0
    adx: float = 0.0
    cci: float = 0.0
    stoch_k: float = 0.0
    stoch_d: float = 0.0
    williams_r: float = 0.0
    obv: float = 0.0
    vwap: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "sma_10": self.sma_10,
            "sma_20": self.sma_20,
            "sma_50": self.sma_50,
            "sma_200": self.sma_200,
            "ema_12": self.ema_12,
            "ema_26": self.ema_26,
            "rsi": self.rsi,
            "macd": self.macd,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "bollinger_upper": self.bollinger_upper,
            "bollinger_middle": self.bollinger_middle,
            "bollinger_lower": self.bollinger_lower,
            "atr": self.atr,
            "adx": self.adx,
            "cci": self.cci,
            "stoch_k": self.stoch_k,
            "stoch_d": self.stoch_d,
            "williams_r": self.williams_r,
            "obv": self.obv,
            "vwap": self.vwap,
        }


@dataclass
class Pattern:
    """Market pattern data"""
    name: str
    symbol: str
    start_time: datetime
    end_time: datetime
    confidence: float
    type: str  # bullish, bearish, neutral
    strength: float
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "confidence": self.confidence,
            "type": self.type,
            "strength": self.strength,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class MarketProfile:
    """Market profile data"""
    symbol: str
    timestamp: datetime
    value_area_high: float
    value_area_low: float
    poc: float  # Point of Control
    profile_distribution: Dict[float, float]
    volume_profile: Dict[float, float]
    high_volume_node: float
    low_volume_node: float
    value_area_volume: float
    total_volume: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "value_area_high": self.value_area_high,
            "value_area_low": self.value_area_low,
            "poc": self.poc,
            "profile_distribution": self.profile_distribution,
            "volume_profile": self.volume_profile,
            "high_volume_node": self.high_volume_node,
            "low_volume_node": self.low_volume_node,
            "value_area_volume": self.value_area_volume,
            "total_volume": self.total_volume,
        }


@dataclass
class Signal:
    """Trading signal data"""
    symbol: str
    timestamp: datetime
    action: str  # buy, sell, hold
    confidence: float
    strength: float
    price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    indicators: Dict[str, Any] = field(default_factory=dict)
    patterns: List[Pattern] = field(default_factory=list)
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "confidence": self.confidence,
            "strength": self.strength,
            "price": self.price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "indicators": self.indicators,
            "patterns": [p.to_dict() for p in self.patterns],
            "reason": self.reason,
        }


# ============================================================
# ANALYZER ENGINE
# ============================================================

class AnalyzerEngine:
    """
    Comprehensive market analyzer for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the analyzer engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.indicators_cache: Dict[str, Dict[str, Any]] = {}
        self.patterns_cache: Dict[str, List[Pattern]] = {}
        self.profile_cache: Dict[str, Dict[str, Any]] = {}
        self.signals: List[Signal] = []
        
        logger.info("Analyzer engine initialized")
    
    # ============================================================
    # TECHNICAL INDICATORS
    # ============================================================
    
    def calculate_indicators(
        self,
        symbol: str,
        prices: List[float],
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None,
        volumes: Optional[List[float]] = None,
        timestamp: Optional[datetime] = None
    ) -> TechnicalIndicators:
        """
        Calculate technical indicators
        
        Args:
            symbol: Asset symbol
            prices: Price series
            highs: High price series
            lows: Low price series
            volumes: Volume series
            timestamp: Timestamp
            
        Returns:
            TechnicalIndicators
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        prices_array = np.array(prices)
        highs_array = np.array(highs) if highs else prices_array
        lows_array = np.array(lows) if lows else prices_array
        volumes_array = np.array(volumes) if volumes else np.ones(len(prices))
        
        # Use TA-Lib if available
        if HAS_TALIB:
            return self._calculate_indicators_talib(
                symbol, prices_array, highs_array, lows_array, volumes_array, timestamp
            )
        
        # Fallback to manual calculation
        return self._calculate_indicators_manual(
            symbol, prices_array, highs_array, lows_array, volumes_array, timestamp
        )
    
    def _calculate_indicators_talib(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        timestamp: datetime
    ) -> TechnicalIndicators:
        """Calculate indicators using TA-Lib"""
        try:
            # Simple Moving Averages
            sma_10 = talib.SMA(prices, timeperiod=10)[-1] if len(prices) >= 10 else 0
            sma_20 = talib.SMA(prices, timeperiod=20)[-1] if len(prices) >= 20 else 0
            sma_50 = talib.SMA(prices, timeperiod=50)[-1] if len(prices) >= 50 else 0
            sma_200 = talib.SMA(prices, timeperiod=200)[-1] if len(prices) >= 200 else 0
            
            # Exponential Moving Averages
            ema_12 = talib.EMA(prices, timeperiod=12)[-1] if len(prices) >= 12 else 0
            ema_26 = talib.EMA(prices, timeperiod=26)[-1] if len(prices) >= 26 else 0
            
            # RSI
            rsi = talib.RSI(prices, timeperiod=14)[-1] if len(prices) >= 14 else 50
            
            # MACD
            macd, macd_signal, macd_hist = talib.MACD(prices)
            macd_value = macd[-1] if len(macd) > 0 else 0
            macd_signal_value = macd_signal[-1] if len(macd_signal) > 0 else 0
            macd_hist_value = macd_hist[-1] if len(macd_hist) > 0 else 0
            
            # Bollinger Bands
            bb_upper, bb_middle, bb_lower = talib.BBANDS(prices, timeperiod=20, nbdevup=2, nbdevdn=2)
            bb_upper_val = bb_upper[-1] if len(bb_upper) > 0 else prices[-1]
            bb_middle_val = bb_middle[-1] if len(bb_middle) > 0 else prices[-1]
            bb_lower_val = bb_lower[-1] if len(bb_lower) > 0 else prices[-1]
            
            # ATR
            atr = talib.ATR(highs, lows, prices, timeperiod=14)[-1] if len(prices) >= 14 else 0
            
            # ADX
            adx = talib.ADX(highs, lows, prices, timeperiod=14)[-1] if len(prices) >= 14 else 0
            
            # CCI
            cci = talib.CCI(highs, lows, prices, timeperiod=14)[-1] if len(prices) >= 14 else 0
            
            # Stochastic
            stoch_k, stoch_d = talib.STOCH(highs, lows, prices)
            stoch_k_val = stoch_k[-1] if len(stoch_k) > 0 else 50
            stoch_d_val = stoch_d[-1] if len(stoch_d) > 0 else 50
            
            # Williams %R
            williams_r = talib.WILLR(highs, lows, prices, timeperiod=14)[-1] if len(prices) >= 14 else -50
            
            # OBV
            obv = talib.OBV(prices, volumes)[-1] if len(prices) > 0 else 0
            
            # VWAP (simplified)
            vwap = np.average(prices, weights=volumes) if len(volumes) > 0 else prices[-1]
            
            return TechnicalIndicators(
                symbol=symbol,
                timestamp=timestamp,
                sma_10=sma_10,
                sma_20=sma_20,
                sma_50=sma_50,
                sma_200=sma_200,
                ema_12=ema_12,
                ema_26=ema_26,
                rsi=rsi,
                macd=macd_value,
                macd_signal=macd_signal_value,
                macd_histogram=macd_hist_value,
                bollinger_upper=bb_upper_val,
                bollinger_middle=bb_middle_val,
                bollinger_lower=bb_lower_val,
                atr=atr,
                adx=adx,
                cci=cci,
                stoch_k=stoch_k_val,
                stoch_d=stoch_d_val,
                williams_r=williams_r,
                obv=obv,
                vwap=vwap,
            )
        except Exception as e:
            logger.warning(f"TA-Lib calculation failed: {e}")
            return self._calculate_indicators_manual(
                symbol, prices, highs, lows, volumes, timestamp
            )
    
    def _calculate_indicators_manual(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        timestamp: datetime
    ) -> TechnicalIndicators:
        """Calculate indicators manually"""
        # Simple Moving Averages
        sma_10 = np.mean(prices[-10:]) if len(prices) >= 10 else prices[-1]
        sma_20 = np.mean(prices[-20:]) if len(prices) >= 20 else prices[-1]
        sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else prices[-1]
        sma_200 = np.mean(prices[-200:]) if len(prices) >= 200 else prices[-1]
        
        # EMA
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        # RSI
        rsi = self._calculate_rsi(prices, 14)
        
        # MACD
        macd, macd_signal, macd_hist = self._calculate_macd(prices)
        
        # Bollinger Bands
        bb_middle = np.mean(prices[-20:]) if len(prices) >= 20 else prices[-1]
        bb_std = np.std(prices[-20:]) if len(prices) >= 20 else 0
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std
        
        # ATR
        atr = self._calculate_atr(highs, lows, prices, 14)
        
        # ADX
        adx = self._calculate_adx(highs, lows, prices, 14)
        
        # CCI
        cci = self._calculate_cci(highs, lows, prices, 14)
        
        # Stochastic
        stoch_k, stoch_d = self._calculate_stochastic(highs, lows, prices, 14)
        
        # Williams %R
        williams_r = self._calculate_williams_r(highs, lows, prices, 14)
        
        # OBV
        obv = self._calculate_obv(prices, volumes)
        
        # VWAP
        vwap = np.average(prices, weights=volumes) if len(volumes) > 0 else prices[-1]
        
        return TechnicalIndicators(
            symbol=symbol,
            timestamp=timestamp,
            sma_10=sma_10,
            sma_20=sma_20,
            sma_50=sma_50,
            sma_200=sma_200,
            ema_12=ema_12,
            ema_26=ema_26,
            rsi=rsi,
            macd=macd,
            macd_signal=macd_signal,
            macd_histogram=macd_hist,
            bollinger_upper=bb_upper,
            bollinger_middle=bb_middle,
            bollinger_lower=bb_lower,
            atr=atr,
            adx=adx,
            cci=cci,
            stoch_k=stoch_k,
            stoch_d=stoch_d,
            williams_r=williams_r,
            obv=obv,
            vwap=vwap,
        )
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA"""
        if len(prices) < period:
            return prices[-1]
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        return ema
    
    def _calculate_rsi(self, prices: np.ndarray, period: int) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        returns = np.diff(prices)
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD"""
        if len(prices) < 26:
            return 0.0, 0.0, 0.0
        
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        macd = ema_12 - ema_26
        
        # Signal line (9-day EMA of MACD)
        signal = self._calculate_ema(np.array([macd]), 9) if len(prices) >= 9 else macd
        
        # Histogram
        histogram = macd - signal
        
        return macd, signal, histogram
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate ATR"""
        if len(closes) < period:
            return 0.0
        
        tr = np.maximum(
            highs - lows,
            np.maximum(
                np.abs(highs - np.roll(closes, 1)),
                np.abs(lows - np.roll(closes, 1))
            )
        )[1:]
        
        return np.mean(tr[-period:])
    
    def _calculate_adx(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate ADX (simplified)"""
        if len(closes) < period:
            return 0.0
        
        # Simplified ADX using price range
        tr = self._calculate_atr(highs, lows, closes, period)
        if tr == 0:
            return 0.0
        
        # Directional movement
        up_move = highs[1:] - highs[:-1]
        down_move = lows[:-1] - lows[1:]
        
        plus_dm = np.maximum(up_move, 0)
        minus_dm = np.maximum(down_move, 0)
        
        plus_di = 100 * np.mean(plus_dm[-period:]) / tr if tr > 0 else 0
        minus_di = 100 * np.mean(minus_dm[-period:]) / tr if tr > 0 else 0
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        return dx
    
    def _calculate_cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate CCI"""
        if len(closes) < period:
            return 0.0
        
        tp = (highs + lows + closes) / 3
        mean_tp = np.mean(tp[-period:])
        mean_dev = np.mean(np.abs(tp[-period:] - mean_tp))
        
        if mean_dev == 0:
            return 0.0
        
        return (tp[-1] - mean_tp) / (0.015 * mean_dev)
    
    def _calculate_stochastic(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> Tuple[float, float]:
        """Calculate Stochastic"""
        if len(closes) < period:
            return 50.0, 50.0
        
        high = np.max(highs[-period:])
        low = np.min(lows[-period:])
        
        if high == low:
            return 50.0, 50.0
        
        k = 100 * (closes[-1] - low) / (high - low)
        d = k  # Simplified
        
        return k, d
    
    def _calculate_williams_r(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate Williams %R"""
        if len(closes) < period:
            return -50.0
        
        high = np.max(highs[-period:])
        low = np.min(lows[-period:])
        
        if high == low:
            return -50.0
        
        return -100 * (high - closes[-1]) / (high - low)
    
    def _calculate_obv(self, prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate OBV"""
        if len(prices) < 2:
            return 0.0
        
        obv = 0
        for i in range(1, len(prices)):
            if prices[i] > prices[i-1]:
                obv += volumes[i]
            elif prices[i] < prices[i-1]:
                obv -= volumes[i]
        
        return obv
    
    # ============================================================
    # PATTERN RECOGNITION
    # ============================================================
    
    def detect_patterns(
        self,
        symbol: str,
        prices: List[float],
        highs: Optional[List[float]] = None,
        lows: Optional[List[float]] = None,
        volumes: Optional[List[float]] = None
    ) -> List[Pattern]:
        """
        Detect market patterns
        
        Args:
            symbol: Asset symbol
            prices: Price series
            highs: High price series
            lows: Low price series
            volumes: Volume series
            
        Returns:
            List of patterns
        """
        patterns = []
        
        # Convert to numpy arrays
        prices_array = np.array(prices)
        highs_array = np.array(highs) if highs else prices_array
        lows_array = np.array(lows) if lows else prices_array
        
        # Detect various patterns
        patterns.extend(self._detect_trend_patterns(symbol, prices_array))
        patterns.extend(self._detect_chart_patterns(symbol, prices_array, highs_array, lows_array))
        patterns.extend(self._detect_candlestick_patterns(symbol, prices_array, highs_array, lows_array))
        
        # Cache patterns
        self.patterns_cache[symbol] = patterns
        
        return patterns
    
    def _detect_trend_patterns(self, symbol: str, prices: np.ndarray) -> List[Pattern]:
        """Detect trend patterns"""
        patterns = []
        
        if len(prices) < 20:
            return patterns
        
        # Calculate trend
        sma_20 = np.mean(prices[-20:])
        sma_50 = np.mean(prices[-50:]) if len(prices) >= 50 else sma_20
        
        # Uptrend
        if sma_20 > sma_50 and prices[-1] > sma_20:
            patterns.append(Pattern(
                name="uptrend",
                symbol=symbol,
                start_time=datetime.now() - timedelta(days=30),
                end_time=datetime.now(),
                confidence=0.7,
                type="bullish",
                strength=0.6,
                description="Price is in an uptrend",
                parameters={"sma_20": sma_20, "sma_50": sma_50},
            ))
        
        # Downtrend
        elif sma_20 < sma_50 and prices[-1] < sma_20:
            patterns.append(Pattern(
                name="downtrend",
                symbol=symbol,
                start_time=datetime.now() - timedelta(days=30),
                end_time=datetime.now(),
                confidence=0.7,
                type="bearish",
                strength=0.6,
                description="Price is in a downtrend",
                parameters={"sma_20": sma_20, "sma_50": sma_50},
            ))
        
        # Sideways
        else:
            patterns.append(Pattern(
                name="sideways",
                symbol=symbol,
                start_time=datetime.now() - timedelta(days=30),
                end_time=datetime.now(),
                confidence=0.6,
                type="neutral",
                strength=0.4,
                description="Price is moving sideways",
                parameters={"sma_20": sma_20, "sma_50": sma_50},
            ))
        
        return patterns
    
    def _detect_chart_patterns(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray
    ) -> List[Pattern]:
        """Detect chart patterns"""
        patterns = []
        
        if len(prices) < 50:
            return patterns
        
        # Find peaks and troughs
        peaks, _ = find_peaks(prices, distance=5, prominence=0.01)
        troughs, _ = find_peaks(-prices, distance=5, prominence=0.01)
        
        # Double Top
        if len(peaks) >= 2:
            if abs(prices[peaks[-1]] - prices[peaks[-2]]) / prices[peaks[-2]] < 0.02:
                patterns.append(Pattern(
                    name="double_top",
                    symbol=symbol,
                    start_time=datetime.now() - timedelta(days=10),
                    end_time=datetime.now(),
                    confidence=0.6,
                    type="bearish",
                    strength=0.5,
                    description="Double top pattern detected - potential reversal",
                    parameters={"peak1": prices[peaks[-2]], "peak2": prices[peaks[-1]]},
                ))
        
        # Double Bottom
        if len(troughs) >= 2:
            if abs(prices[troughs[-1]] - prices[troughs[-2]]) / prices[troughs[-2]] < 0.02:
                patterns.append(Pattern(
                    name="double_bottom",
                    symbol=symbol,
                    start_time=datetime.now() - timedelta(days=10),
                    end_time=datetime.now(),
                    confidence=0.6,
                    type="bullish",
                    strength=0.5,
                    description="Double bottom pattern detected - potential reversal",
                    parameters={"bottom1": prices[troughs[-2]], "bottom2": prices[troughs[-1]]},
                ))
        
        # Breakout
        if len(peaks) >= 3:
            resistance = np.mean([prices[p] for p in peaks[-3:]])
            if prices[-1] > resistance * 1.01:
                patterns.append(Pattern(
                    name="breakout",
                    symbol=symbol,
                    start_time=datetime.now() - timedelta(days=3),
                    end_time=datetime.now(),
                    confidence=0.7,
                    type="bullish",
                    strength=0.7,
                    description="Breakout above resistance",
                    parameters={"resistance": resistance},
                ))
        
        # Breakdown
        if len(troughs) >= 3:
            support = np.mean([prices[t] for t in troughs[-3:]])
            if prices[-1] < support * 0.99:
                patterns.append(Pattern(
                    name="breakdown",
                    symbol=symbol,
                    start_time=datetime.now() - timedelta(days=3),
                    end_time=datetime.now(),
                    confidence=0.7,
                    type="bearish",
                    strength=0.7,
                    description="Breakdown below support",
                    parameters={"support": support},
                ))
        
        return patterns
    
    def _detect_candlestick_patterns(
        self,
        symbol: str,
        prices: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray
    ) -> List[Pattern]:
        """Detect candlestick patterns"""
        patterns = []
        
        if len(prices) < 10:
            return patterns
        
        # Use TA-Lib for candlestick patterns if available
        if HAS_TALIB:
            try:
                # Doji
                doji = talib.CDLDOJI(prices, highs, lows, prices)[-1]
                if doji != 0:
                    patterns.append(Pattern(
                        name="doji",
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=1),
                        end_time=datetime.now(),
                        confidence=0.5,
                        type="neutral",
                        strength=0.3,
                        description="Doji candle pattern - indecision",
                        parameters={},
                    ))
                
                # Hammer
                hammer = talib.CDLHAMMER(prices, highs, lows, prices)[-1]
                if hammer != 0:
                    patterns.append(Pattern(
                        name="hammer",
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=1),
                        end_time=datetime.now(),
                        confidence=0.6,
                        type="bullish",
                        strength=0.6,
                        description="Hammer candle pattern - potential reversal",
                        parameters={},
                    ))
                
                # Shooting Star
                shooting_star = talib.CDLSHOOTINGSTAR(prices, highs, lows, prices)[-1]
                if shooting_star != 0:
                    patterns.append(Pattern(
                        name="shooting_star",
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=1),
                        end_time=datetime.now(),
                        confidence=0.6,
                        type="bearish",
                        strength=0.6,
                        description="Shooting star candle pattern - potential reversal",
                        parameters={},
                    ))
                
                # Engulfing
                engulfing = talib.CDLENGULFING(prices, highs, lows, prices)[-1]
                if engulfing != 0:
                    pattern_type = "bullish" if engulfing > 0 else "bearish"
                    patterns.append(Pattern(
                        name="engulfing",
                        symbol=symbol,
                        start_time=datetime.now() - timedelta(days=1),
                        end_time=datetime.now(),
                        confidence=0.7,
                        type=pattern_type,
                        strength=0.7,
                        description="Engulfing candle pattern",
                        parameters={},
                    ))
                
            except Exception as e:
                logger.warning(f"TA-Lib candlestick detection failed: {e}")
        
        return patterns
    
    # ============================================================
    # MARKET PROFILE
    # ============================================================
    
    def calculate_market_profile(
        self,
        symbol: str,
        prices: List[float],
        volumes: List[float],
        bins: int = 20
    ) -> MarketProfile:
        """
        Calculate market profile
        
        Args:
            symbol: Asset symbol
            prices: Price series
            volumes: Volume series
            bins: Number of price bins
            
        Returns:
            MarketProfile
        """
        prices_array = np.array(prices)
        volumes_array = np.array(volumes)
        
        # Create price bins
        price_min = np.min(prices_array)
        price_max = np.max(prices_array)
        bin_edges = np.linspace(price_min, price_max, bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Calculate volume profile
        volume_profile = {}
        for i in range(len(bin_centers)):
            mask = (prices_array >= bin_edges[i]) & (prices_array < bin_edges[i + 1])
            volume_profile[bin_centers[i]] = np.sum(volumes_array[mask])
        
        # Find Point of Control (POC)
        poc_price = max(volume_profile, key=volume_profile.get)
        
        # Calculate value area (70% of volume)
        sorted_volumes = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
        total_volume = sum(volume_profile.values())
        value_area_volume = 0
        value_area_high = 0
        value_area_low = 0
        
        for price, volume in sorted_volumes:
            value_area_volume += volume
            if value_area_volume >= 0.7 * total_volume:
                value_area_high = max(value_area_high, price)
                value_area_low = min(value_area_low, price)
                break
        
        # Find high and low volume nodes
        high_volume_node = max(volume_profile, key=volume_profile.get)
        low_volume_node = min(volume_profile, key=volume_profile.get)
        
        # Profile distribution
        profile_distribution = dict(zip(bin_centers, np.histogram(prices_array, bins=bin_edges)[0]))
        
        return MarketProfile(
            symbol=symbol,
            timestamp=datetime.now(),
            value_area_high=value_area_high,
            value_area_low=value_area_low,
            poc=poc_price,
            profile_distribution=profile_distribution,
            volume_profile=volume_profile,
            high_volume_node=high_volume_node,
            low_volume_node=low_volume_node,
            value_area_volume=value_area_volume,
            total_volume=total_volume,
        )
    
    # ============================================================
    # SIGNAL GENERATION
    # ============================================================
    
    def generate_signal(
        self,
        symbol: str,
        indicators: TechnicalIndicators,
        patterns: Optional[List[Pattern]] = None,
        current_price: Optional[float] = None
    ) -> Signal:
        """
        Generate trading signal
        
        Args:
            symbol: Asset symbol
            indicators: Technical indicators
            patterns: Detected patterns
            current_price: Current price
            
        Returns:
            Signal
        """
        if current_price is None:
            current_price = indicators.bollinger_middle
        
        action = "hold"
        confidence = 0.5
        strength = 0.3
        stop_loss = 0
        take_profit = 0
        risk_reward_ratio = 0
        reason = ""
        
        # Combine signals from indicators
        buy_signals = []
        sell_signals = []
        
        # RSI signals
        if indicators.rsi < 30:
            buy_signals.append("oversold")
            strength += 0.1
        elif indicators.rsi > 70:
            sell_signals.append("overbought")
            strength += 0.1
        
        # MACD signals
        if indicators.macd > indicators.macd_signal and indicators.macd_histogram > 0:
            buy_signals.append("macd_bullish")
            strength += 0.1
        elif indicators.macd < indicators.macd_signal and indicators.macd_histogram < 0:
            sell_signals.append("macd_bearish")
            strength += 0.1
        
        # Bollinger signals
        if current_price < indicators.bollinger_lower:
            buy_signals.append("bollinger_oversold")
            strength += 0.1
        elif current_price > indicators.bollinger_upper:
            sell_signals.append("bollinger_overbought")
            strength += 0.1
        
        # SMA signals
        if indicators.sma_10 > indicators.sma_50:
            buy_signals.append("sma_bullish")
            strength += 0.05
        elif indicators.sma_10 < indicators.sma_50:
            sell_signals.append("sma_bearish")
            strength += 0.05
        
        # Pattern signals
        if patterns:
            bullish_patterns = [p for p in patterns if p.type == "bullish"]
            bearish_patterns = [p for p in patterns if p.type == "bearish"]
            
            if bullish_patterns:
                buy_signals.append("patterns_bullish")
                strength += 0.1 * len(bullish_patterns)
            if bearish_patterns:
                sell_signals.append("patterns_bearish")
                strength += 0.1 * len(bearish_patterns)
        
        # Determine action
        if len(buy_signals) > len(sell_signals) and len(buy_signals) >= 2:
            action = "buy"
            confidence = 0.6 + 0.1 * len(buy_signals)
            reason = f"Buy signals: {', '.join(buy_signals)}"
            
            # Calculate stop loss and take profit
            atr = indicators.atr if indicators.atr > 0 else current_price * 0.01
            stop_loss = current_price - 2 * atr
            take_profit = current_price + 3 * atr
            risk_reward_ratio = (take_profit - current_price) / (current_price - stop_loss)
            
        elif len(sell_signals) > len(buy_signals) and len(sell_signals) >= 2:
            action = "sell"
            confidence = 0.6 + 0.1 * len(sell_signals)
            reason = f"Sell signals: {', '.join(sell_signals)}"
            
            # Calculate stop loss and take profit
            atr = indicators.atr if indicators.atr > 0 else current_price * 0.01
            stop_loss = current_price + 2 * atr
            take_profit = current_price - 3 * atr
            risk_reward_ratio = (current_price - take_profit) / (stop_loss - current_price)
        
        # Limit confidence
        confidence = min(confidence, 0.95)
        
        signal = Signal(
            symbol=symbol,
            timestamp=datetime.now(),
            action=action,
            confidence=confidence,
            strength=min(strength, 1.0),
            price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_ratio=risk_reward_ratio,
            indicators=indicators.to_dict(),
            patterns=patterns or [],
            reason=reason,
        )
        
        # Store signal
        self.signals.append(signal)
        
        return signal


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Dataclasses
    "TechnicalIndicators",
    "Pattern",
    "MarketProfile",
    "Signal",
    
    # Classes
    "AnalyzerEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
