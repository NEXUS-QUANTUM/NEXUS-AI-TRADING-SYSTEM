"""
NEXUS AI TRADING SYSTEM - Market Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced market analysis with technical indicators, pattern recognition,
market regime detection, and sentiment analysis capabilities.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import find_peaks, argrelextrema
from scipy.stats import norm, skew, kurtosis
import warnings
from pathlib import Path
import logging
from concurrent.futures import ThreadPoolExecutor
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nexus.shared.types.market import (
    MarketData, OHLCV, OrderBook, MarketDepth,
    MarketRegime, MarketCondition, TrendDirection
)
from nexus.shared.helpers.trading_helpers import (
    calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_atr, calculate_ichimoku, calculate_fibonacci_retracement,
    calculate_pivot_points, calculate_support_resistance
)
from nexus.shared.utilities.logger import Logger

logger = Logger(__name__)


class PatternType(Enum):
    """Types of chart patterns"""
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    TRIPLE_TOP = "triple_top"
    TRIPLE_BOTTOM = "triple_bottom"
    BULLISH_FLAG = "bullish_flag"
    BEARISH_FLAG = "bearish_flag"
    BULLISH_PENNANT = "bullish_pennant"
    BEARISH_PENNANT = "bearish_pennant"
    WEDGE = "wedge"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    CUP_AND_HANDLE = "cup_and_handle"
    INVERSE_CUP_AND_HANDLE = "inverse_cup_and_handle"
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    DOJI = "doji"
    HAMMER = "hammer"
    SHOOTING_STAR = "shooting_star"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    PIERCING_LINE = "piercing_line"
    DARK_CLOUD_COVER = "dark_cloud_cover"


class MarketRegimeType(Enum):
    """Types of market regimes"""
    BULL_TRENDING = "bull_trending"
    BEAR_TRENDING = "bear_trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"
    CONSOLIDATION = "consolidation"
    REVERSAL = "reversal"
    STABLE = "stable"
    UNKNOWN = "unknown"


@dataclass_json
@dataclass
class MarketAnalyzerConfig:
    """Configuration for market analyzer"""
    # Analysis parameters
    lookback_periods: int = 200
    short_window: int = 20
    medium_window: int = 50
    long_window: int = 200
    
    # Technical indicator parameters
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_std: float = 2.0
    atr_period: int = 14
    ichimoku_conversion: int = 9
    ichimoku_base: int = 26
    ichimoku_span: int = 52
    
    # Pattern detection parameters
    pattern_lookback: int = 100
    pattern_sensitivity: float = 0.02
    minimum_pattern_size: float = 0.01
    
    # Volume analysis
    volume_sma_period: int = 20
    volume_spike_threshold: float = 1.5
    
    # Regime detection
    regime_lookback: int = 50
    volatility_threshold: float = 0.02
    trend_threshold: float = 0.01
    
    # Market structure
    support_resistance_lookback: int = 100
    support_resistance_threshold: float = 0.005
    
    # Output options
    generate_charts: bool = True
    save_results: bool = True
    output_dir: str = "data/exports/market_analysis"
    
    # Parallel processing
    use_parallel: bool = True
    max_workers: int = 4


@dataclass_json
@dataclass
class TechnicalIndicators:
    """Technical indicator values"""
    # Trend indicators
    sma_short: Optional[List[float]] = None
    sma_medium: Optional[List[float]] = None
    sma_long: Optional[List[float]] = None
    ema_short: Optional[List[float]] = None
    ema_medium: Optional[List[float]] = None
    ema_long: Optional[List[float]] = None
    wma_short: Optional[List[float]] = None
    wma_medium: Optional[List[float]] = None
    wma_long: Optional[List[float]] = None
    hull_ma: Optional[List[float]] = None
    kama: Optional[List[float]] = None
    
    # Momentum indicators
    rsi: Optional[List[float]] = None
    macd: Optional[List[float]] = None
    macd_signal: Optional[List[float]] = None
    macd_histogram: Optional[List[float]] = None
    stochastic_k: Optional[List[float]] = None
    stochastic_d: Optional[List[float]] = None
    williams_r: Optional[List[float]] = None
    cci: Optional[List[float]] = None
    mfi: Optional[List[float]] = None
    roc: Optional[List[float]] = None
    momentum: Optional[List[float]] = None
    
    # Volatility indicators
    bollinger_upper: Optional[List[float]] = None
    bollinger_middle: Optional[List[float]] = None
    bollinger_lower: Optional[List[float]] = None
    atr: Optional[List[float]] = None
    keltner_upper: Optional[List[float]] = None
    keltner_middle: Optional[List[float]] = None
    keltner_lower: Optional[List[float]] = None
    donchian_upper: Optional[List[float]] = None
    donchian_lower: Optional[List[float]] = None
    
    # Volume indicators
    obv: Optional[List[float]] = None
    volume_sma: Optional[List[float]] = None
    volume_momentum: Optional[List[float]] = None
    mfi: Optional[List[float]] = None
    vwap: Optional[List[float]] = None
    
    # Market strength
    adx: Optional[List[float]] = None
    plus_di: Optional[List[float]] = None
    minus_di: Optional[List[float]] = None
    aroon_up: Optional[List[float]] = None
    aroon_down: Optional[List[float]] = None
    
    # Ichimoku
    ichimoku_conversion_line: Optional[List[float]] = None
    ichimoku_base_line: Optional[List[float]] = None
    ichimoku_span_a: Optional[List[float]] = None
    ichimoku_span_b: Optional[List[float]] = None
    ichimoku_chikou_span: Optional[List[float]] = None
    
    # Current values
    current: Dict[str, float] = field(default_factory=dict)


@dataclass_json
@dataclass
class PatternDetection:
    """Detected chart patterns"""
    pattern_type: Optional[PatternType] = None
    confidence: float = 0.0
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    pattern_size: float = 0.0
    formation_bars: int = 0
    detection_time: datetime = field(default_factory=datetime.now)
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pattern_type": self.pattern_type.value if self.pattern_type else None,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "support_level": self.support_level,
            "resistance_level": self.resistance_level,
            "pattern_size": self.pattern_size,
            "formation_bars": self.formation_bars,
            "detection_time": self.detection_time.isoformat(),
            "additional_data": self.additional_data
        }


@dataclass_json
@dataclass
class MarketRegimeAnalysis:
    """Market regime analysis results"""
    current_regime: MarketRegimeType = MarketRegimeType.UNKNOWN
    regime_confidence: float = 0.0
    trend_direction: TrendDirection = TrendDirection.NEUTRAL
    trend_strength: float = 0.0
    volatility_level: float = 0.0
    volatility_status: str = "neutral"
    momentum_status: str = "neutral"
    market_structure: Dict[str, Any] = field(default_factory=dict)
    key_levels: Dict[str, float] = field(default_factory=dict)
    regime_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Probabilities
    bull_probability: float = 0.0
    bear_probability: float = 0.0
    range_probability: float = 0.0
    breakout_probability: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "current_regime": self.current_regime.value,
            "regime_confidence": self.regime_confidence,
            "trend_direction": self.trend_direction.value,
            "trend_strength": self.trend_strength,
            "volatility_level": self.volatility_level,
            "volatility_status": self.volatility_status,
            "momentum_status": self.momentum_status,
            "market_structure": self.market_structure,
            "key_levels": self.key_levels,
            "bull_probability": self.bull_probability,
            "bear_probability": self.bear_probability,
            "range_probability": self.range_probability,
            "breakout_probability": self.breakout_probability
        }


@dataclass_json
@dataclass
class MarketAnalysisResult:
    """Complete market analysis result"""
    # Basic information
    symbol: str = ""
    timeframe: str = ""
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    analysis_duration: float = 0.0
    
    # Core analytics
    technical_indicators: TechnicalIndicators = field(default_factory=TechnicalIndicators)
    patterns: List[PatternDetection] = field(default_factory=list)
    regime_analysis: MarketRegimeAnalysis = field(default_factory=MarketRegimeAnalysis)
    support_resistance: Dict[str, List[float]] = field(default_factory=dict)
    fibonacci_levels: Dict[str, float] = field(default_factory=dict)
    pivot_points: Dict[str, float] = field(default_factory=dict)
    
    # Market summary
    summary: Dict[str, Any] = field(default_factory=dict)
    signals: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Raw data
    ohlcv_data: Optional[pd.DataFrame] = None
    market_data: Optional[MarketData] = None
    
    # Visualization
    chart_paths: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "analysis_duration": self.analysis_duration,
            "technical_indicators": self.technical_indicators.__dict__,
            "patterns": [p.to_dict() for p in self.patterns],
            "regime_analysis": self.regime_analysis.to_dict(),
            "support_resistance": self.support_resistance,
            "fibonacci_levels": self.fibonacci_levels,
            "pivot_points": self.pivot_points,
            "summary": self.summary,
            "signals": self.signals,
            "recommendations": self.recommendations,
            "warnings": self.warnings
        }


class MarketAnalyzer:
    """
    Advanced market analyzer with comprehensive technical analysis,
    pattern recognition, and market regime detection capabilities.
    """
    
    def __init__(
        self,
        config: Optional[MarketAnalyzerConfig] = None,
        executor: Optional[ThreadPoolExecutor] = None
    ):
        """
        Initialize the market analyzer.
        
        Args:
            config: Configuration for analysis
            executor: Thread pool executor for parallel processing
        """
        self.config = config or MarketAnalyzerConfig()
        self.executor = executor or ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._logger = Logger(__name__)
        
    async def analyze_market(
        self,
        ohlcv_data: Union[pd.DataFrame, MarketData],
        symbol: str = "Unknown",
        timeframe: str = "1h"
    ) -> MarketAnalysisResult:
        """
        Perform comprehensive market analysis.
        
        Args:
            ohlcv_data: OHLCV data or MarketData object
            symbol: Trading symbol
            timeframe: Timeframe of the data
            
        Returns:
            Complete market analysis result
        """
        start_time = datetime.now()
        
        self._logger.info(f"Starting market analysis for {symbol}")
        
        try:
            # Convert data if needed
            if isinstance(ohlcv_data, MarketData):
                ohlcv_data = self._market_data_to_dataframe(ohlcv_data)
            
            if ohlcv_data.empty:
                raise ValueError("Empty OHLCV data provided")
            
            # Run analysis in parallel
            tasks = [
                self._calculate_technical_indicators_async(ohlcv_data),
                self._detect_patterns_async(ohlcv_data),
                self._analyze_regime_async(ohlcv_data),
                self._find_support_resistance_async(ohlcv_data),
                self._calculate_fibonacci_async(ohlcv_data),
                self._calculate_pivot_points_async(ohlcv_data)
            ]
            
            results = await asyncio.gather(*tasks)
            
            technical_indicators = results[0]
            patterns = results[1]
            regime_analysis = results[2]
            support_resistance = results[3]
            fibonacci_levels = results[4]
            pivot_points = results[5]
            
            # Generate summary and signals
            summary = self._generate_summary(
                technical_indicators, regime_analysis, patterns
            )
            signals = self._generate_signals(
                technical_indicators, regime_analysis, patterns, support_resistance
            )
            recommendations = self._generate_recommendations(summary, signals)
            warnings = self._generate_warnings(summary, signals)
            
            # Create result
            result = MarketAnalysisResult(
                symbol=symbol,
                timeframe=timeframe,
                analysis_timestamp=datetime.now(),
                analysis_duration=(datetime.now() - start_time).total_seconds(),
                technical_indicators=technical_indicators,
                patterns=patterns,
                regime_analysis=regime_analysis,
                support_resistance=support_resistance,
                fibonacci_levels=fibonacci_levels,
                pivot_points=pivot_points,
                summary=summary,
                signals=signals,
                recommendations=recommendations,
                warnings=warnings,
                ohlcv_data=ohlcv_data
            )
            
            # Generate charts if requested
            if self.config.generate_charts:
                result.chart_paths = await self._generate_charts(result)
            
            # Save results if requested
            if self.config.save_results:
                await self._save_results(result)
            
            self._logger.info(f"Market analysis completed in {result.analysis_duration:.2f}s")
            
            return result
            
        except Exception as e:
            self._logger.error(f"Error in market analysis: {str(e)}")
            raise
    
    def _market_data_to_dataframe(self, market_data: MarketData) -> pd.DataFrame:
        """Convert MarketData object to DataFrame."""
        if hasattr(market_data, 'ohlcv'):
            ohlcv = market_data.ohlcv
            return pd.DataFrame({
                'open': [o.open for o in ohlcv],
                'high': [o.high for o in ohlcv],
                'low': [o.low for o in ohlcv],
                'close': [o.close for o in ohlcv],
                'volume': [o.volume for o in ohlcv],
                'timestamp': [o.timestamp for o in ohlcv]
            })
        elif hasattr(market_data, 'data'):
            return market_data.data
        else:
            raise ValueError("Unsupported market data format")
    
    async def _calculate_technical_indicators_async(
        self,
        ohlcv_data: pd.DataFrame
    ) -> TechnicalIndicators:
        """Calculate technical indicators asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._calculate_technical_indicators_sync,
            ohlcv_data
        )
    
    def _calculate_technical_indicators_sync(
        self,
        ohlcv_data: pd.DataFrame
    ) -> TechnicalIndicators:
        """Synchronous technical indicator calculation."""
        indicators = TechnicalIndicators()
        
        close = ohlcv_data['close'].values
        high = ohlcv_data['high'].values
        low = ohlcv_data['low'].values
        volume = ohlcv_data['volume'].values if 'volume' in ohlcv_data.columns else None
        
        if len(close) < self.config.long_window:
            self._logger.warning(f"Insufficient data for full indicator calculation. Need {self.config.long_window} bars")
            return indicators
        
        # Trend indicators
        indicators.sma_short = self._calculate_sma(close, self.config.short_window)
        indicators.sma_medium = self._calculate_sma(close, self.config.medium_window)
        indicators.sma_long = self._calculate_sma(close, self.config.long_window)
        indicators.ema_short = self._calculate_ema(close, self.config.short_window)
        indicators.ema_medium = self._calculate_ema(close, self.config.medium_window)
        indicators.ema_long = self._calculate_ema(close, self.config.long_window)
        
        # Momentum indicators
        indicators.rsi = self._calculate_rsi(close, self.config.rsi_period)
        indicators.macd, indicators.macd_signal, indicators.macd_histogram = self._calculate_macd(
            close, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal
        )
        
        # Stochastic Oscillator
        indicators.stochastic_k, indicators.stochastic_d = self._calculate_stochastic(
            high, low, close, 14, 3
        )
        
        # Williams %R
        indicators.williams_r = self._calculate_williams_r(high, low, close, 14)
        
        # CCI
        indicators.cci = self._calculate_cci(high, low, close, 20)
        
        # MFI
        if volume is not None:
            indicators.mfi = self._calculate_mfi(high, low, close, volume, 14)
        
        # Volatility indicators
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
            close, self.config.bollinger_std, self.config.medium_window
        )
        indicators.bollinger_upper = bb_upper
        indicators.bollinger_middle = bb_middle
        indicators.bollinger_lower = bb_lower
        
        indicators.atr = self._calculate_atr(high, low, close, self.config.atr_period)
        
        # Volume indicators
        if volume is not None:
            indicators.obv = self._calculate_obv(close, volume)
            indicators.volume_sma = self._calculate_sma(volume, self.config.volume_sma_period)
        
        # Market strength
        indicators.adx, indicators.plus_di, indicators.minus_di = self._calculate_adx(
            high, low, close, 14
        )
        
        indicators.aroon_up, indicators.aroon_down = self._calculate_aroon(
            high, low, 25
        )
        
        # Ichimoku Cloud
        (indicators.ichimoku_conversion_line,
         indicators.ichimoku_base_line,
         indicators.ichimoku_span_a,
         indicators.ichimoku_span_b,
         indicators.ichimoku_chikou_span) = self._calculate_ichimoku(
            high, low, close,
            self.config.ichimoku_conversion,
            self.config.ichimoku_base,
            self.config.ichimoku_span
        )
        
        # Current values
        indicators.current = {
            "close": close[-1] if len(close) > 0 else 0,
            "high": high[-1] if len(high) > 0 else 0,
            "low": low[-1] if len(low) > 0 else 0,
            "volume": volume[-1] if volume is not None and len(volume) > 0 else 0,
            "sma_short": indicators.sma_short[-1] if indicators.sma_short else 0,
            "sma_medium": indicators.sma_medium[-1] if indicators.sma_medium else 0,
            "sma_long": indicators.sma_long[-1] if indicators.sma_long else 0,
            "rsi": indicators.rsi[-1] if indicators.rsi else 0,
            "macd": indicators.macd[-1] if indicators.macd else 0,
            "macd_signal": indicators.macd_signal[-1] if indicators.macd_signal else 0,
            "bb_upper": indicators.bollinger_upper[-1] if indicators.bollinger_upper else 0,
            "bb_middle": indicators.bollinger_middle[-1] if indicators.bollinger_middle else 0,
            "bb_lower": indicators.bollinger_lower[-1] if indicators.bollinger_lower else 0,
            "atr": indicators.atr[-1] if indicators.atr else 0,
            "adx": indicators.adx[-1] if indicators.adx else 0
        }
        
        return indicators
    
    def _calculate_sma(self, data: np.ndarray, period: int) -> List[float]:
        """Calculate Simple Moving Average."""
        if len(data) < period:
            return []
        return list(pd.Series(data).rolling(window=period).mean().dropna())
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> List[float]:
        """Calculate Exponential Moving Average."""
        if len(data) < period:
            return []
        return list(pd.Series(data).ewm(span=period, adjust=False).mean().dropna())
    
    def _calculate_rsi(self, data: np.ndarray, period: int) -> List[float]:
        """Calculate Relative Strength Index."""
        if len(data) < period + 1:
            return []
            
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)
        
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = avg_gain / avg_loss
        rs[np.isinf(rs)] = 0
        rsi = 100 - (100 / (1 + rs))
        
        return list(rsi[period:])
    
    def _calculate_macd(
        self,
        data: np.ndarray,
        fast: int,
        slow: int,
        signal: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate MACD."""
        if len(data) < slow:
            return [], [], []
            
        ema_fast = pd.Series(data).ewm(span=fast, adjust=False).mean()
        ema_slow = pd.Series(data).ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_histogram = macd - macd_signal
        
        return list(macd.dropna()), list(macd_signal.dropna()), list(macd_histogram.dropna())
    
    def _calculate_stochastic(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        k_period: int,
        d_period: int
    ) -> Tuple[List[float], List[float]]:
        """Calculate Stochastic Oscillator."""
        if len(close) < k_period:
            return [], []
            
        k_values = []
        for i in range(k_period - 1, len(close)):
            highest_high = np.max(high[i-k_period+1:i+1])
            lowest_low = np.min(low[i-k_period+1:i+1])
            if highest_high != lowest_low:
                k = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
            else:
                k = 50
            k_values.append(k)
        
        # Calculate D (SMA of K)
        d_values = []
        for i in range(d_period - 1, len(k_values)):
            d = np.mean(k_values[i-d_period+1:i+1])
            d_values.append(d)
        
        k_values = k_values[d_period - 1:]  # Align lengths
        
        return k_values, d_values
    
    def _calculate_williams_r(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> List[float]:
        """Calculate Williams %R."""
        if len(close) < period:
            return []
            
        williams_r = []
        for i in range(period - 1, len(close)):
            highest_high = np.max(high[i-period+1:i+1])
            lowest_low = np.min(low[i-period+1:i+1])
            if highest_high != lowest_low:
                wr = -100 * (highest_high - close[i]) / (highest_high - lowest_low)
            else:
                wr = 0
            williams_r.append(wr)
        
        return williams_r
    
    def _calculate_cci(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> List[float]:
        """Calculate Commodity Channel Index."""
        if len(close) < period:
            return []
            
        typical_price = (high + low + close) / 3
        cci = []
        
        for i in range(period - 1, len(typical_price)):
            tp_slice = typical_price[i-period+1:i+1]
            mean_tp = np.mean(tp_slice)
            mean_dev = np.mean(np.abs(tp_slice - mean_tp))
            if mean_dev != 0:
                cci_value = (typical_price[i] - mean_tp) / (0.015 * mean_dev)
            else:
                cci_value = 0
            cci.append(cci_value)
        
        return cci
    
    def _calculate_mfi(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        period: int
    ) -> List[float]:
        """Calculate Money Flow Index."""
        if len(close) < period + 1:
            return []
            
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        mfi = []
        for i in range(period, len(close)):
            positive_flow = 0
            negative_flow = 0
            
            for j in range(i - period + 1, i + 1):
                if typical_price[j] > typical_price[j-1]:
                    positive_flow += money_flow[j]
                elif typical_price[j] < typical_price[j-1]:
                    negative_flow += money_flow[j]
            
            if negative_flow == 0:
                mfi_value = 100
            else:
                money_ratio = positive_flow / negative_flow
                mfi_value = 100 - (100 / (1 + money_ratio))
            mfi.append(mfi_value)
        
        return mfi
    
    def _calculate_bollinger_bands(
        self,
        data: np.ndarray,
        std_dev: float,
        period: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate Bollinger Bands."""
        if len(data) < period:
            return [], [], []
            
        sma = pd.Series(data).rolling(window=period).mean()
        std = pd.Series(data).rolling(window=period).std()
        
        upper = sma + std_dev * std
        middle = sma
        lower = sma - std_dev * std
        
        return list(upper.dropna()), list(middle.dropna()), list(lower.dropna())
    
    def _calculate_atr(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> List[float]:
        """Calculate Average True Range."""
        if len(close) < period + 1:
            return []
            
        true_range = []
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            true_range.append(tr)
        
        atr = []
        for i in range(period - 1, len(true_range)):
            atr_value = np.mean(true_range[i-period+1:i+1])
            atr.append(atr_value)
        
        return atr
    
    def _calculate_obv(self, close: np.ndarray, volume: np.ndarray) -> List[float]:
        """Calculate On-Balance Volume."""
        if len(close) < 2:
            return []
            
        obv = np.zeros_like(close)
        obv[0] = volume[0]
        
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        return list(obv)
    
    def _calculate_adx(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """Calculate ADX, +DI, -DI."""
        if len(close) < period + 1:
            return [], [], []
            
        true_range = []
        plus_dm = []
        minus_dm = []
        
        for i in range(1, len(close)):
            tr = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
            true_range.append(tr)
            
            up_move = high[i] - high[i-1]
            down_move = low[i-1] - low[i]
            
            plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
            minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
        
        # Smooth
        atr = []
        plus_di = []
        minus_di = []
        
        for i in range(period - 1, len(true_range)):
            tr_slice = true_range[i-period+1:i+1]
            atr_value = np.mean(tr_slice)
            atr.append(atr_value)
            
            plus_slice = plus_dm[i-period+1:i+1]
            minus_slice = minus_dm[i-period+1:i+1]
            
            plus_di_value = 100 * (np.mean(plus_slice) / atr_value) if atr_value != 0 else 0
            minus_di_value = 100 * (np.mean(minus_slice) / atr_value) if atr_value != 0 else 0
            
            plus_di.append(plus_di_value)
            minus_di.append(minus_di_value)
        
        # Calculate DX
        dx = []
        for i in range(len(plus_di)):
            dx_value = 100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]) if (plus_di[i] + minus_di[i]) != 0 else 0
            dx.append(dx_value)
        
        # Calculate ADX
        adx = []
        for i in range(period - 1, len(dx)):
            adx_value = np.mean(dx[i-period+1:i+1])
            adx.append(adx_value)
        
        return adx, plus_di, minus_di
    
    def _calculate_aroon(
        self,
        high: np.ndarray,
        low: np.ndarray,
        period: int
    ) -> Tuple[List[float], List[float]]:
        """Calculate Aroon Up and Down."""
        if len(high) < period:
            return [], []
            
        aroon_up = []
        aroon_down = []
        
        for i in range(period - 1, len(high)):
            high_slice = high[i-period+1:i+1]
            low_slice = low[i-period+1:i+1]
            
            high_idx = np.argmax(high_slice)
            low_idx = np.argmin(low_slice)
            
            aroon_up_value = 100 * (period - high_idx) / period
            aroon_down_value = 100 * (period - low_idx) / period
            
            aroon_up.append(aroon_up_value)
            aroon_down.append(aroon_down_value)
        
        return aroon_up, aroon_down
    
    def _calculate_ichimoku(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        conversion_period: int,
        base_period: int,
        span_period: int
    ) -> Tuple[List[float], List[float], List[float], List[float], List[float]]:
        """Calculate Ichimoku Cloud components."""
        if len(close) < span_period:
            return [], [], [], [], []
            
        # Conversion Line (Tenkan-sen)
        conversion_line = []
        for i in range(conversion_period - 1, len(close)):
            high_slice = high[i-conversion_period+1:i+1]
            low_slice = low[i-conversion_period+1:i+1]
            conversion_line.append((np.max(high_slice) + np.min(low_slice)) / 2)
        
        # Base Line (Kijun-sen)
        base_line = []
        for i in range(base_period - 1, len(close)):
            high_slice = high[i-base_period+1:i+1]
            low_slice = low[i-base_period+1:i+1]
            base_line.append((np.max(high_slice) + np.min(low_slice)) / 2)
        
        # Senkou Span A (Leading Span A)
        span_a = []
        min_len = min(len(conversion_line), len(base_line))
        for i in range(min_len):
            span_a.append((conversion_line[i] + base_line[i]) / 2)
        
        # Senkou Span B (Leading Span B)
        span_b = []
        for i in range(span_period - 1, len(close)):
            high_slice = high[i-span_period+1:i+1]
            low_slice = low[i-span_period+1:i+1]
            span_b.append((np.max(high_slice) + np.min(low_slice)) / 2)
        
        # Chikou Span (Lagging Span)
        chikou_span = close[:-span_period]
        
        return conversion_line, base_line, span_a, span_b, list(chikou_span)
    
    async def _detect_patterns_async(self, ohlcv_data: pd.DataFrame) -> List[PatternDetection]:
        """Detect chart patterns asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._detect_patterns_sync,
            ohlcv_data
        )
    
    def _detect_patterns_sync(self, ohlcv_data: pd.DataFrame) -> List[PatternDetection]:
        """Synchronous pattern detection."""
        patterns = []
        close = ohlcv_data['close'].values
        high = ohlcv_data['high'].values
        low = ohlcv_data['low'].values
        open_price = ohlcv_data['open'].values
        
        if len(close) < self.config.pattern_lookback:
            return patterns
        
        # Detect Head and Shoulders
        hs_pattern = self._detect_head_and_shoulders(close)
        if hs_pattern:
            patterns.append(hs_pattern)
        
        # Detect Double Top/Bottom
        dt_pattern = self._detect_double_top_bottom(close)
        if dt_pattern:
            patterns.append(dt_pattern)
        
        # Detect Triangles
        triangle_pattern = self._detect_triangle(high, low)
        if triangle_pattern:
            patterns.append(triangle_pattern)
        
        # Detect Candlestick patterns
        candle_patterns = self._detect_candlestick_patterns(open_price, high, low, close)
        patterns.extend(candle_patterns)
        
        # Detect Flags and Pennants
        flag_pattern = self._detect_flag_pattern(close)
        if flag_pattern:
            patterns.append(flag_pattern)
        
        # Detect Wedges
        wedge_pattern = self._detect_wedge(high, low)
        if wedge_pattern:
            patterns.append(wedge_pattern)
        
        return patterns
    
    def _detect_head_and_shoulders(self, close: np.ndarray) -> Optional[PatternDetection]:
        """Detect Head and Shoulders pattern."""
        if len(close) < 50:
            return None
            
        # Find local maxima
        peaks, _ = find_peaks(close, distance=5, prominence=np.std(close) * 0.2)
        
        if len(peaks) < 3:
            return None
            
        # Look for Head and Shoulders pattern (3 peaks)
        for i in range(len(peaks) - 2):
            left_peak = peaks[i]
            head = peaks[i+1]
            right_peak = peaks[i+2]
            
            # Check pattern structure
            if (close[left_peak] < close[head] and 
                close[right_peak] < close[head] and
                close[left_peak] > close[right_peak] * 0.95 and
                close[right_peak] > close[left_peak] * 0.95):
                
                # Check symmetry
                left_width = head - left_peak
                right_width = right_peak - head
                if 0.5 < left_width / right_width < 2:
                    
                    # Calculate pattern size
                    pattern_size = (close[head] - min(close[left_peak], close[right_peak])) / close[head]
                    
                    if pattern_size > self.config.minimum_pattern_size:
                        return PatternDetection(
                            pattern_type=PatternType.HEAD_AND_SHOULDERS,
                            confidence=0.8,
                            entry_price=close[right_peak],
                            target_price=close[right_peak] - pattern_size * 0.5,
                            stop_loss=close[head] * 1.02,
                            pattern_size=pattern_size,
                            formation_bars=right_peak - left_peak,
                            additional_data={
                                "left_shoulder": float(close[left_peak]),
                                "head": float(close[head]),
                                "right_shoulder": float(close[right_peak])
                            }
                        )
        
        return None
    
    def _detect_double_top_bottom(self, close: np.ndarray) -> Optional[PatternDetection]:
        """Detect Double Top/Bottom pattern."""
        if len(close) < 30:
            return None
            
        # Find local extrema
        peaks, _ = find_peaks(close, distance=10, prominence=np.std(close) * 0.15)
        valleys, _ = find_peaks(-close, distance=10, prominence=np.std(close) * 0.15)
        
        # Double Top (two peaks)
        if len(peaks) >= 2:
            for i in range(len(peaks) - 1):
                peak1 = peaks[i]
                peak2 = peaks[i+1]
                
                if (abs(close[peak1] - close[peak2]) / close[peak1] < 0.03 and  # Similar heights
                    peak2 - peak1 > 10 and  # Minimum distance
                    peak2 - peak1 < 50):  # Maximum distance
                    
                    # Check for valley between peaks
                    valley = np.argmin(close[peak1:peak2]) + peak1
                    if close[valley] < close[peak1] * 0.95:
                        pattern_size = (close[peak1] - close[valley]) / close[peak1]
                        
                        if pattern_size > self.config.minimum_pattern_size:
                            return PatternDetection(
                                pattern_type=PatternType.DOUBLE_TOP,
                                confidence=0.75,
                                entry_price=close[peak2],
                                target_price=close[valley] - pattern_size * 0.5,
                                stop_loss=close[peak2] * 1.02,
                                pattern_size=pattern_size,
                                formation_bars=peak2 - peak1,
                                additional_data={
                                    "peak1": float(close[peak1]),
                                    "peak2": float(close[peak2]),
                                    "valley": float(close[valley])
                                }
                            )
        
        # Double Bottom (two valleys)
        if len(valleys) >= 2:
            for i in range(len(valleys) - 1):
                valley1 = valleys[i]
                valley2 = valleys[i+1]
                
                if (abs(close[valley1] - close[valley2]) / close[valley1] < 0.03 and
                    valley2 - valley1 > 10 and
                    valley2 - valley1 < 50):
                    
                    peak = np.argmax(close[valley1:valley2]) + valley1
                    if close[peak] > close[valley1] * 1.05:
                        pattern_size = (close[peak] - close[valley1]) / close[valley1]
                        
                        if pattern_size > self.config.minimum_pattern_size:
                            return PatternDetection(
                                pattern_type=PatternType.DOUBLE_BOTTOM,
                                confidence=0.75,
                                entry_price=close[valley2],
                                target_price=close[peak] + pattern_size * 0.5,
                                stop_loss=close[valley2] * 0.98,
                                pattern_size=pattern_size,
                                formation_bars=valley2 - valley1,
                                additional_data={
                                    "valley1": float(close[valley1]),
                                    "valley2": float(close[valley2]),
                                    "peak": float(close[peak])
                                }
                            )
        
        return None
    
    def _detect_triangle(
        self,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[PatternDetection]:
        """Detect Triangle patterns."""
        if len(high) < 30:
            return None
            
        # Get recent data (last 50 bars)
        recent_high = high[-50:]
        recent_low = low[-50:]
        
        # Fit lines to highs and lows
        x = np.arange(len(recent_high))
        
        # High line (resistance)
        high_peaks, _ = find_peaks(recent_high, distance=5)
        if len(high_peaks) < 3:
            return None
            
        high_peaks_x = high_peaks[-3:]
        high_peaks_y = recent_high[high_peaks[-3:]]
        
        # Low line (support)
        low_valleys, _ = find_peaks(-recent_low, distance=5)
        if len(low_valleys) < 3:
            return None
            
        low_valleys_x = low_valleys[-3:]
        low_valleys_y = recent_low[low_valleys[-3:]]
        
        # Calculate slopes
        if len(high_peaks_x) >= 2 and len(low_valleys_x) >= 2:
            high_slope = (high_peaks_y[-1] - high_peaks_y[0]) / (high_peaks_x[-1] - high_peaks_x[0])
            low_slope = (low_valleys_y[-1] - low_valleys_y[0]) / (low_valleys_x[-1] - low_valleys_x[0])
            
            # Symmetrical Triangle (converging)
            if high_slope < 0 and low_slope > 0:
                return PatternDetection(
                    pattern_type=PatternType.SYMMETRICAL_TRIANGLE,
                    confidence=0.7,
                    entry_price=recent_high[-1],
                    target_price=recent_high[-1] * 1.05,
                    stop_loss=recent_low[-1] * 0.98,
                    pattern_size=(recent_high[-1] - recent_low[-1]) / recent_high[-1],
                    formation_bars=50,
                    additional_data={
                        "high_slope": high_slope,
                        "low_slope": low_slope,
                        "apex_price": (high_peaks_y[-1] + low_valleys_y[-1]) / 2
                    }
                )
            # Ascending Triangle (bullish)
            elif high_slope < 0.001 and low_slope > 0:
                return PatternDetection(
                    pattern_type=PatternType.ASCENDING_TRIANGLE,
                    confidence=0.75,
                    entry_price=recent_high[-1],
                    target_price=recent_high[-1] * 1.08,
                    stop_loss=recent_low[-1] * 0.98,
                    pattern_size=(recent_high[-1] - recent_low[-1]) / recent_high[-1],
                    formation_bars=50,
                    additional_data={
                        "resistance": float(recent_high[-1]),
                        "support_trend": low_slope
                    }
                )
            # Descending Triangle (bearish)
            elif high_slope < 0 and low_slope > -0.001:
                return PatternDetection(
                    pattern_type=PatternType.DESCENDING_TRIANGLE,
                    confidence=0.75,
                    entry_price=recent_high[-1],
                    target_price=recent_high[-1] * 0.92,
                    stop_loss=recent_high[-1] * 1.02,
                    pattern_size=(recent_high[-1] - recent_low[-1]) / recent_high[-1],
                    formation_bars=50,
                    additional_data={
                        "support": float(recent_low[-1]),
                        "resistance_trend": high_slope
                    }
                )
        
        return None
    
    def _detect_candlestick_patterns(
        self,
        open_price: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> List[PatternDetection]:
        """Detect candlestick patterns."""
        patterns = []
        
        if len(close) < 3:
            return patterns
            
        # Get last 3 candles for pattern detection
        o1, o2, o3 = open_price[-3:], open_price[-2:-1], open_price[-1:]
        h1, h2, h3 = high[-3:], high[-2:-1], high[-1:]
        l1, l2, l3 = low[-3:], low[-2:-1], low[-1:]
        c1, c2, c3 = close[-3:], close[-2:-1], close[-1:]
        
        # Bullish Engulfing
        if (c2[0] > o2[0] and  # Previous candle is bullish
            o3[0] < c2[0] and  # Current opens below previous close
            c3[0] > o2[0] and  # Current closes above previous open
            o3[0] < o2[0] and c3[0] > c2[0]):  # Engulfs previous candle
            patterns.append(PatternDetection(
                pattern_type=PatternType.BULLISH_ENGULFING,
                confidence=0.8,
                entry_price=c3[0],
                target_price=c3[0] * 1.02,
                stop_loss=o3[0] * 0.98,
                pattern_size=(c3[0] - o3[0]) / c3[0],
                formation_bars=2,
                additional_data={
                    "previous_close": float(c2[0]),
                    "current_open": float(o3[0]),
                    "current_close": float(c3[0])
                }
            ))
        
        # Bearish Engulfing
        if (c2[0] < o2[0] and  # Previous candle is bearish
            o3[0] > c2[0] and  # Current opens above previous close
            c3[0] < o2[0] and  # Current closes below previous open
            o3[0] > o2[0] and c3[0] < c2[0]):  # Engulfs previous candle
            patterns.append(PatternDetection(
                pattern_type=PatternType.BEARISH_ENGULFING,
                confidence=0.8,
                entry_price=c3[0],
                target_price=c3[0] * 0.98,
                stop_loss=o3[0] * 1.02,
                pattern_size=(o3[0] - c3[0]) / o3[0],
                formation_bars=2,
                additional_data={
                    "previous_close": float(c2[0]),
                    "current_open": float(o3[0]),
                    "current_close": float(c3[0])
                }
            ))
        
        # Doji
        body_size = abs(c3[0] - o3[0])
        total_range = h3[0] - l3[0]
        if total_range > 0 and body_size / total_range < 0.1:
            patterns.append(PatternDetection(
                pattern_type=PatternType.DOJI,
                confidence=0.6,
                entry_price=c3[0],
                target_price=c3[0] * (1 + body_size * 2),
                stop_loss=c3[0] * (1 - body_size * 2),
                pattern_size=body_size / c3[0],
                formation_bars=1,
                additional_data={
                    "body_size": float(body_size),
                    "total_range": float(total_range)
                }
            ))
        
        # Hammer (bullish reversal)
        if (c3[0] > o3[0] and  # Bullish candle
            (l3[0] - o3[0]) > 2 * (c3[0] - o3[0]) and  # Long lower shadow
            (h3[0] - c3[0]) < (c3[0] - o3[0]) * 0.1):  # Short upper shadow
            patterns.append(PatternDetection(
                pattern_type=PatternType.HAMMER,
                confidence=0.75,
                entry_price=c3[0],
                target_price=c3[0] * 1.02,
                stop_loss=l3[0] * 0.98,
                pattern_size=(c3[0] - o3[0]) / c3[0],
                formation_bars=1,
                additional_data={
                    "lower_shadow": float(l3[0] - o3[0]),
                    "upper_shadow": float(h3[0] - c3[0])
                }
            ))
        
        # Shooting Star (bearish reversal)
        if (c3[0] < o3[0] and  # Bearish candle
            (h3[0] - o3[0]) > 2 * (o3[0] - c3[0]) and  # Long upper shadow
            (c3[0] - l3[0]) < (o3[0] - c3[0]) * 0.1):  # Short lower shadow
            patterns.append(PatternDetection(
                pattern_type=PatternType.SHOOTING_STAR,
                confidence=0.75,
                entry_price=c3[0],
                target_price=c3[0] * 0.98,
                stop_loss=h3[0] * 1.02,
                pattern_size=(o3[0] - c3[0]) / o3[0],
                formation_bars=1,
                additional_data={
                    "upper_shadow": float(h3[0] - o3[0]),
                    "lower_shadow": float(c3[0] - l3[0])
                }
            ))
        
        # Morning Star (bullish reversal)
        if len(close) >= 3:
            if (c1[0] < o1[0] and  # First candle bearish
                abs(c2[0] - o2[0]) < abs(c1[0] - o1[0]) * 0.2 and  # Second candle small body
                c3[0] > o3[0] and  # Third candle bullish
                c3[0] > (o1[0] + c1[0]) / 2):  # Closes above midpoint of first candle
                patterns.append(PatternDetection(
                    pattern_type=PatternType.MORNING_STAR,
                    confidence=0.8,
                    entry_price=c3[0],
                    target_price=c3[0] * 1.03,
                    stop_loss=l3[0] * 0.98,
                    pattern_size=(c3[0] - o3[0]) / c3[0],
                    formation_bars=3,
                    additional_data={
                        "first_close": float(c1[0]),
                        "second_close": float(c2[0]),
                        "third_close": float(c3[0])
                    }
                ))
        
        # Evening Star (bearish reversal)
        if len(close) >= 3:
            if (c1[0] > o1[0] and  # First candle bullish
                abs(c2[0] - o2[0]) < abs(c1[0] - o1[0]) * 0.2 and  # Second candle small body
                c3[0] < o3[0] and  # Third candle bearish
                c3[0] < (o1[0] + c1[0]) / 2):  # Closes below midpoint of first candle
                patterns.append(PatternDetection(
                    pattern_type=PatternType.EVENING_STAR,
                    confidence=0.8,
                    entry_price=c3[0],
                    target_price=c3[0] * 0.97,
                    stop_loss=h3[0] * 1.02,
                    pattern_size=(o3[0] - c3[0]) / o3[0],
                    formation_bars=3,
                    additional_data={
                        "first_close": float(c1[0]),
                        "second_close": float(c2[0]),
                        "third_close": float(c3[0])
                    }
                ))
        
        return patterns
    
    def _detect_flag_pattern(self, close: np.ndarray) -> Optional[PatternDetection]:
        """Detect Flag pattern."""
        if len(close) < 30:
            return None
            
        # Look for sharp move (flagpole)
        recent_close = close[-20:]
        price_change = (recent_close[-1] - recent_close[0]) / recent_close[0]
        
        if abs(price_change) < 0.05:  # Need at least 5% move
            return None
            
        # Check for consolidation (flag)
        flag_high = np.max(recent_close[-10:])
        flag_low = np.min(recent_close[-10:])
        flag_size = (flag_high - flag_low) / flag_high
        
        if flag_size > 0.03:  # Tight consolidation
            return None
            
        if price_change > 0:  # Bullish flag
            return PatternDetection(
                pattern_type=PatternType.BULLISH_FLAG,
                confidence=0.7,
                entry_price=recent_close[-1],
                target_price=recent_close[0] * (1 + price_change * 1.5),
                stop_loss=flag_low * 0.98,
                pattern_size=flag_size,
                formation_bars=20,
                additional_data={
                    "flagpole_change": price_change,
                    "flag_high": float(flag_high),
                    "flag_low": float(flag_low)
                }
            )
        else:  # Bearish flag
            return PatternDetection(
                pattern_type=PatternType.BEARISH_FLAG,
                confidence=0.7,
                entry_price=recent_close[-1],
                target_price=recent_close[0] * (1 + price_change * 1.5),
                stop_loss=flag_high * 1.02,
                pattern_size=flag_size,
                formation_bars=20,
                additional_data={
                    "flagpole_change": price_change,
                    "flag_high": float(flag_high),
                    "flag_low": float(flag_low)
                }
            )
    
    def _detect_wedge(self, high: np.ndarray, low: np.ndarray) -> Optional[PatternDetection]:
        """Detect Wedge pattern."""
        if len(high) < 30:
            return None
            
        # Get recent data
        recent_high = high[-30:]
        recent_low = low[-30:]
        x = np.arange(len(recent_high))
        
        # Fit lines
        high_slope = (recent_high[-1] - recent_high[0]) / len(recent_high)
        low_slope = (recent_low[-1] - recent_low[0]) / len(recent_low)
        
        # Falling wedge (bullish)
        if high_slope < 0 and low_slope < 0 and high_slope < low_slope:
            return PatternDetection(
                pattern_type=PatternType.WEDGE,
                confidence=0.7,
                entry_price=recent_high[-1],
                target_price=recent_high[0] * 1.05,
                stop_loss=recent_low[-1] * 0.98,
                pattern_size=(recent_high[-1] - recent_low[-1]) / recent_high[-1],
                formation_bars=30,
                additional_data={
                    "high_slope": high_slope,
                    "low_slope": low_slope,
                    "wedge_type": "falling"
                }
            )
        # Rising wedge (bearish)
        elif high_slope > 0 and low_slope > 0 and high_slope > low_slope:
            return PatternDetection(
                pattern_type=PatternType.WEDGE,
                confidence=0.7,
                entry_price=recent_high[-1],
                target_price=recent_high[0] * 0.95,
                stop_loss=recent_high[-1] * 1.02,
                pattern_size=(recent_high[-1] - recent_low[-1]) / recent_high[-1],
                formation_bars=30,
                additional_data={
                    "high_slope": high_slope,
                    "low_slope": low_slope,
                    "wedge_type": "rising"
                }
            )
        
        return None
    
    async def _analyze_regime_async(self, ohlcv_data: pd.DataFrame) -> MarketRegimeAnalysis:
        """Analyze market regime asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._analyze_regime_sync,
            ohlcv_data
        )
    
    def _analyze_regime_sync(self, ohlcv_data: pd.DataFrame) -> MarketRegimeAnalysis:
        """Synchronous regime analysis."""
        analysis = MarketRegimeAnalysis()
        
        if len(ohlcv_data) < self.config.regime_lookback:
            return analysis
            
        close = ohlcv_data['close'].values
        high = ohlcv_data['high'].values
        low = ohlcv_data['low'].values
        
        # Calculate returns and volatility
        returns = np.diff(close) / close[:-1]
        volatility = np.std(returns[-self.config.regime_lookback:])
        
        # Determine volatility status
        analysis.volatility_level = volatility
        if volatility > self.config.volatility_threshold * 2:
            analysis.volatility_status = "high"
        elif volatility < self.config.volatility_threshold * 0.5:
            analysis.volatility_status = "low"
        else:
            analysis.volatility_status = "normal"
        
        # Calculate trend
        sma_short = np.mean(close[-self.config.short_window:])
        sma_long = np.mean(close[-self.config.long_window:])
        trend_strength = abs(sma_short - sma_long) / sma_long
        
        analysis.trend_strength = trend_strength
        
        if sma_short > sma_long and trend_strength > self.config.trend_threshold:
            analysis.trend_direction = TrendDirection.UP
        elif sma_short < sma_long and trend_strength > self.config.trend_threshold:
            analysis.trend_direction = TrendDirection.DOWN
        else:
            analysis.trend_direction = TrendDirection.NEUTRAL
        
        # Calculate momentum
        rsi_values = self._calculate_rsi(close, self.config.rsi_period)
        if rsi_values:
            current_rsi = rsi_values[-1]
            if current_rsi > 60:
                analysis.momentum_status = "bullish"
            elif current_rsi < 40:
                analysis.momentum_status = "bearish"
            else:
                analysis.momentum_status = "neutral"
        
        # Determine regime
        regimes = []
        
        # Trending regimes
        if analysis.trend_direction == TrendDirection.UP and trend_strength > 0.02:
            analysis.current_regime = MarketRegimeType.BULL_TRENDING
            regimes.append(("bull_trending", 0.8))
        elif analysis.trend_direction == TrendDirection.DOWN and trend_strength > 0.02:
            analysis.current_regime = MarketRegimeType.BEAR_TRENDING
            regimes.append(("bear_trending", 0.8))
        
        # Ranging regime
        if trend_strength < 0.01:
            analysis.current_regime = MarketRegimeType.RANGING
            regimes.append(("ranging", 0.7))
        
        # Volatility regimes
        if volatility > self.config.volatility_threshold * 1.5:
            if analysis.current_regime != MarketRegimeType.UNKNOWN:
                regimes.append(("high_volatility", 0.6))
        elif volatility < self.config.volatility_threshold * 0.5:
            regimes.append(("low_volatility", 0.6))
        
        # Check for breakout/breakdown
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
            close, self.config.bollinger_std, self.config.medium_window
        )
        if bb_upper and bb_lower:
            if close[-1] > bb_upper[-1] * 1.01:
                analysis.current_regime = MarketRegimeType.BREAKOUT
                regimes.append(("breakout", 0.8))
            elif close[-1] < bb_lower[-1] * 0.99:
                analysis.current_regime = MarketRegimeType.BREAKDOWN
                regimes.append(("breakdown", 0.8))
        
        # Calculate probabilities
        analysis.bull_probability = 0.5
        analysis.bear_probability = 0.5
        analysis.range_probability = 0.0
        analysis.breakout_probability = 0.0
        
        if analysis.current_regime == MarketRegimeType.BULL_TRENDING:
            analysis.bull_probability = 0.7
            analysis.bear_probability = 0.2
            analysis.range_probability = 0.1
            analysis.regime_confidence = 0.8
        elif analysis.current_regime == MarketRegimeType.BEAR_TRENDING:
            analysis.bull_probability = 0.2
            analysis.bear_probability = 0.7
            analysis.range_probability = 0.1
            analysis.regime_confidence = 0.8
        elif analysis.current_regime == MarketRegimeType.RANGING:
            analysis.bull_probability = 0.3
            analysis.bear_probability = 0.3
            analysis.range_probability = 0.4
            analysis.regime_confidence = 0.7
        elif analysis.current_regime == MarketRegimeType.BREAKOUT:
            analysis.bull_probability = 0.7
            analysis.bear_probability = 0.1
            analysis.breakout_probability = 0.2
            analysis.regime_confidence = 0.7
        elif analysis.current_regime == MarketRegimeType.BREAKDOWN:
            analysis.bull_probability = 0.1
            analysis.bear_probability = 0.7
            analysis.breakout_probability = 0.2
            analysis.regime_confidence = 0.7
        
        # Key levels
        analysis.key_levels = {
            "support": np.min(close[-self.config.support_resistance_lookback:]),
            "resistance": np.max(close[-self.config.support_resistance_lookback:]),
            "sma_short": sma_short,
            "sma_medium": np.mean(close[-self.config.medium_window:]),
            "sma_long": sma_long
        }
        
        # Market structure
        analysis.market_structure = {
            "trend_direction": analysis.trend_direction.value,
            "trend_strength": trend_strength,
            "volatility": volatility,
            "volatility_status": analysis.volatility_status,
            "momentum_status": analysis.momentum_status
        }
        
        return analysis
    
    async def _find_support_resistance_async(
        self,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, List[float]]:
        """Find support and resistance levels asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._find_support_resistance_sync,
            ohlcv_data
        )
    
    def _find_support_resistance_sync(
        self,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, List[float]]:
        """Synchronous support/resistance detection."""
        high = ohlcv_data['high'].values
        low = ohlcv_data['low'].values
        close = ohlcv_data['close'].values
        
        if len(close) < self.config.support_resistance_lookback:
            return {"support": [], "resistance": []}
        
        # Find pivot points
        pivots_high = argrelextrema(high, np.greater, order=5)[0]
        pivots_low = argrelextrema(low, np.less, order=5)[0]
        
        # Get pivot values
        resistance_levels = []
        for idx in pivots_high:
            if idx >= len(high):
                continue
            level = high[idx]
            if level > 0:
                resistance_levels.append(level)
        
        support_levels = []
        for idx in pivots_low:
            if idx >= len(low):
                continue
            level = low[idx]
            if level > 0:
                support_levels.append(level)
        
        # Cluster nearby levels
        support_levels = self._cluster_levels(support_levels, self.config.support_resistance_threshold)
        resistance_levels = self._cluster_levels(resistance_levels, self.config.support_resistance_threshold)
        
        # Sort and keep most recent levels
        support_levels = sorted(support_levels)[-5:]
        resistance_levels = sorted(resistance_levels)[-5:]
        
        return {
            "support": support_levels,
            "resistance": resistance_levels
        }
    
    def _cluster_levels(self, levels: List[float], threshold: float) -> List[float]:
        """Cluster nearby price levels."""
        if not levels:
            return []
            
        levels = sorted(levels)
        clustered = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] < threshold:
                current_cluster.append(level)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    async def _calculate_fibonacci_async(
        self,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._calculate_fibonacci_sync,
            ohlcv_data
        )
    
    def _calculate_fibonacci_sync(self, ohlcv_data: pd.DataFrame) -> Dict[str, float]:
        """Synchronous Fibonacci calculation."""
        if len(ohlcv_data) < 50:
            return {}
            
        high = ohlcv_data['high'].values
        low = ohlcv_data['low'].values
        close = ohlcv_data['close'].values
        
        # Find recent swing high and low
        recent_high = np.max(high[-50:])
        recent_low = np.min(low[-50:])
        
        # Calculate Fibonacci levels
        diff = recent_high - recent_low
        
        return {
            "level_0": recent_low,
            "level_0.236": recent_low + 0.236 * diff,
            "level_0.382": recent_low + 0.382 * diff,
            "level_0.5": recent_low + 0.5 * diff,
            "level_0.618": recent_low + 0.618 * diff,
            "level_0.786": recent_low + 0.786 * diff,
            "level_1": recent_high,
            "extension_1.272": recent_high + 0.272 * diff,
            "extension_1.618": recent_high + 0.618 * diff,
            "extension_2.0": recent_high + diff
        }
    
    async def _calculate_pivot_points_async(
        self,
        ohlcv_data: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate pivot points asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._calculate_pivot_points_sync,
            ohlcv_data
        )
    
    def _calculate_pivot_points_sync(self, ohlcv_data: pd.DataFrame) -> Dict[str, float]:
        """Synchronous pivot point calculation."""
        if len(ohlcv_data) < 2:
            return {}
            
        high = ohlcv_data['high'].values[-1]
        low = ohlcv_data['low'].values[-1]
        close = ohlcv_data['close'].values[-1]
        
        pivot = (high + low + close) / 3
        
        return {
            "pivot": pivot,
            "resistance_1": 2 * pivot - low,
            "resistance_2": pivot + (high - low),
            "resistance_3": high + 2 * (pivot - low),
            "support_1": 2 * pivot - high,
            "support_2": pivot - (high - low),
            "support_3": low - 2 * (high - pivot)
        }
    
    def _generate_summary(
        self,
        indicators: TechnicalIndicators,
        regime: MarketRegimeAnalysis,
        patterns: List[PatternDetection]
    ) -> Dict[str, Any]:
        """Generate market summary."""
        summary = {
            "price": indicators.current.get("close", 0),
            "volume": indicators.current.get("volume", 0),
            "regime": regime.current_regime.value,
            "trend": regime.trend_direction.value,
            "trend_strength": regime.trend_strength,
            "volatility": regime.volatility_level,
            "volatility_status": regime.volatility_status,
            "momentum": regime.momentum_status,
            "rsi": indicators.current.get("rsi", 0),
            "macd": indicators.current.get("macd", 0),
            "patterns_found": len(patterns),
            "support_levels": regime.key_levels.get("support", 0),
            "resistance_levels": regime.key_levels.get("resistance", 0),
            "bull_probability": regime.bull_probability,
            "bear_probability": regime.bear_probability
        }
        
        return summary
    
    def _generate_signals(
        self,
        indicators: TechnicalIndicators,
        regime: MarketRegimeAnalysis,
        patterns: List[PatternDetection],
        support_resistance: Dict[str, List[float]]
    ) -> Dict[str, Any]:
        """Generate trading signals."""
        signals = {
            "buy": False,
            "sell": False,
            "neutral": True,
            "strength": 0.0,
            "reasons": []
        }
        
        close = indicators.current.get("close", 0)
        if close == 0:
            return signals
        
        buy_score = 0
        sell_score = 0
        
        # RSI signals
        rsi = indicators.current.get("rsi", 50)
        if rsi < self.config.rsi_oversold:
            buy_score += 0.3
            signals["reasons"].append("RSI oversold")
        elif rsi > self.config.rsi_overbought:
            sell_score += 0.3
            signals["reasons"].append("RSI overbought")
        
        # Moving average signals
        sma_short = indicators.current.get("sma_short", 0)
        sma_medium = indicators.current.get("sma_medium", 0)
        sma_long = indicators.current.get("sma_long", 0)
        
        if sma_short > 0 and sma_medium > 0 and sma_long > 0:
            if close > sma_short > sma_medium > sma_long:
                buy_score += 0.3
                signals["reasons"].append("Price above all MAs (bullish)")
            elif close < sma_short < sma_medium < sma_long:
                sell_score += 0.3
                signals["reasons"].append("Price below all MAs (bearish)")
            
            if sma_short > sma_medium and sma_medium > sma_long:
                buy_score += 0.2
                signals["reasons"].append("Golden cross")
            elif sma_short < sma_medium and sma_medium < sma_long:
                sell_score += 0.2
                signals["reasons"].append("Death cross")
        
        # MACD signals
        macd = indicators.current.get("macd", 0)
        macd_signal = indicators.current.get("macd_signal", 0)
        if macd > 0 and macd > macd_signal:
            buy_score += 0.2
            signals["reasons"].append("MACD bullish crossover")
        elif macd < 0 and macd < macd_signal:
            sell_score += 0.2
            signals["reasons"].append("MACD bearish crossover")
        
        # Bollinger Bands signals
        bb_upper = indicators.current.get("bb_upper", 0)
        bb_lower = indicators.current.get("bb_lower", 0)
        if bb_upper > 0 and bb_lower > 0:
            if close < bb_lower:
                buy_score += 0.2
                signals["reasons"].append("Price below lower Bollinger band")
            elif close > bb_upper:
                sell_score += 0.2
                signals["reasons"].append("Price above upper Bollinger band")
        
        # Support/Resistance signals
        if support_resistance:
            for level in support_resistance.get("support", []):
                if abs(close - level) / level < 0.01:
                    buy_score += 0.2
                    signals["reasons"].append(f"Price near support level {level:.2f}")
                    break
            
            for level in support_resistance.get("resistance", []):
                if abs(close - level) / level < 0.01:
                    sell_score += 0.2
                    signals["reasons"].append(f"Price near resistance level {level:.2f}")
                    break
        
        # Pattern signals
        for pattern in patterns:
            if pattern.pattern_type in [
                PatternType.BULLISH_ENGULFING,
                PatternType.HAMMER,
                PatternType.MORNING_STAR,
                PatternType.DOUBLE_BOTTOM,
                PatternType.HEAD_AND_SHOULDERS
            ]:
                buy_score += 0.2
                signals["reasons"].append(f"{pattern.pattern_type.value} pattern detected")
            elif pattern.pattern_type in [
                PatternType.BEARISH_ENGULFING,
                PatternType.SHOOTING_STAR,
                PatternType.EVENING_STAR,
                PatternType.DOUBLE_TOP
            ]:
                sell_score += 0.2
                signals["reasons"].append(f"{pattern.pattern_type.value} pattern detected")
        
        # Regime signals
        if regime.current_regime == MarketRegimeType.BULL_TRENDING:
            buy_score += 0.2
            signals["reasons"].append("Bullish market regime")
        elif regime.current_regime == MarketRegimeType.BEAR_TRENDING:
            sell_score += 0.2
            signals["reasons"].append("Bearish market regime")
        elif regime.current_regime == MarketRegimeType.BREAKOUT:
            buy_score += 0.3
            signals["reasons"].append("Breakout detected")
        elif regime.current_regime == MarketRegimeType.BREAKDOWN:
            sell_score += 0.3
            signals["reasons"].append("Breakdown detected")
        
        # Determine final signal
        buy_score = min(buy_score, 1.0)
        sell_score = min(sell_score, 1.0)
        
        if buy_score > 0.5 and buy_score > sell_score:
            signals["buy"] = True
            signals["neutral"] = False
            signals["strength"] = buy_score
        elif sell_score > 0.5 and sell_score > buy_score:
            signals["sell"] = True
            signals["neutral"] = False
            signals["strength"] = sell_score
        else:
            signals["neutral"] = True
            signals["strength"] = max(buy_score, sell_score)
        
        return signals
    
    def _generate_recommendations(
        self,
        summary: Dict[str, Any],
        signals: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if summary["regime"] == MarketRegimeType.BULL_TRENDING.value:
            recommendations.append("✅ Bullish trend detected - Consider long positions")
            if signals["buy"]:
                recommendations.append("🟢 Strong buy signal - Consider entering long position")
        elif summary["regime"] == MarketRegimeType.BEAR_TRENDING.value:
            recommendations.append("❌ Bearish trend detected - Consider short positions")
            if signals["sell"]:
                recommendations.append("🔴 Strong sell signal - Consider entering short position")
        elif summary["regime"] == MarketRegimeType.RANGING.value:
            recommendations.append("📊 Ranging market - Consider mean reversion strategies")
        
        if summary["volatility_status"] == "high":
            recommendations.append("⚠️ High volatility - Use tighter stops and smaller positions")
        elif summary["volatility_status"] == "low":
            recommendations.append("📉 Low volatility - Consider breakout strategies")
        
        if summary.get("patterns_found", 0) > 0:
            recommendations.append(f"📊 {summary['patterns_found']} chart patterns detected - Monitor for confirmations")
        
        if summary["rsi"] < 30:
            recommendations.append("🟢 RSI oversold - Potential buying opportunity")
        elif summary["rsi"] > 70:
            recommendations.append("🔴 RSI overbought - Potential selling opportunity")
        
        if signals["buy"] and not signals["sell"]:
            recommendations.append("✅ Overall buy signal - Look for entry points")
        elif signals["sell"] and not signals["buy"]:
            recommendations.append("✅ Overall sell signal - Look for entry points")
        else:
            recommendations.append("⚡ Neutral signal - Wait for clearer direction")
        
        return recommendations
    
    def _generate_warnings(
        self,
        summary: Dict[str, Any],
        signals: Dict[str, Any]
    ) -> List[str]:
        """Generate warnings based on analysis."""
        warnings = []
        
        if summary["volatility_status"] == "high":
            warnings.append("⚠️ High volatility - Risk of sharp price movements")
        
        if summary.get("rsi", 50) > 80:
            warnings.append("🔴 RSI extremely overbought - Possible reversal")
        elif summary.get("rsi", 50) < 20:
            warnings.append("🟢 RSI extremely oversold - Possible reversal")
        
        if summary.get("trend_strength", 0) < 0.005:
            warnings.append("📊 Weak trend - Avoid directional strategies")
        
        if summary["regime"] == MarketRegimeType.UNKNOWN.value:
            warnings.append("❓ Market regime unknown - Use caution")
        
        if signals["buy"] and signals["sell"]:
            warnings.append("⚠️ Conflicting signals - Wait for clarity")
        
        return warnings
    
    async def _generate_charts(self, result: MarketAnalysisResult) -> Dict[str, str]:
        """Generate market analysis charts."""
        chart_paths = {}
        
        try:
            df = result.ohlcv_data
            if df is None or df.empty:
                return chart_paths
            
            # Create comprehensive chart
            fig = make_subplots(
                rows=5, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=(
                    f"{result.symbol} - {result.timeframe}",
                    "Volume & Volume Indicators",
                    "RSI & Momentum",
                    "MACD",
                    "Bollinger Bands & Price"
                ),
                row_heights=[0.3, 0.15, 0.15, 0.2, 0.2]
            )
            
            # Price chart
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name="Price"
                ),
                row=1, col=1
            )
            
            # Add moving averages
            if result.technical_indicators.sma_short:
                sma_short = result.technical_indicators.sma_short
                if len(sma_short) >= len(df):
                    fig.add_trace(
                        go.Scatter(
                            x=df.index[-len(sma_short):],
                            y=sma_short,
                            name=f"SMA {self.config.short_window}",
                            line=dict(color="blue", width=1)
                        ),
                        row=1, col=1
                    )
            
            # Add Bollinger Bands
            if result.technical_indicators.bollinger_upper:
                bb_upper = result.technical_indicators.bollinger_upper
                bb_middle = result.technical_indicators.bollinger_middle
                bb_lower = result.technical_indicators.bollinger_lower
                if len(bb_upper) >= len(df):
                    idx = df.index[-len(bb_upper):]
                    fig.add_trace(
                        go.Scatter(
                            x=idx,
                            y=bb_upper,
                            name="BB Upper",
                            line=dict(color="gray", width=1, dash="dash")
                        ),
                        row=1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=idx,
                            y=bb_middle,
                            name="BB Middle",
                            line=dict(color="gray", width=1)
                        ),
                        row=1, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=idx,
                            y=bb_lower,
                            name="BB Lower",
                            line=dict(color="gray", width=1, dash="dash"),
                            fill='tonexty',
                            fillcolor='rgba(128, 128, 128, 0.1)'
                        ),
                        row=1, col=1
                    )
            
            # Add support/resistance levels
            for level in result.support_resistance.get("support", []):
                fig.add_hline(y=level, line_color="green", line_dash="dash", row=1, col=1)
            for level in result.support_resistance.get("resistance", []):
                fig.add_hline(y=level, line_color="red", line_dash="dash", row=1, col=1)
            
            # Volume chart
            colors = ['green' if df['close'].iloc[i] > df['open'].iloc[i] else 'red' 
                     for i in range(len(df))]
            fig.add_trace(
                go.Bar(
                    x=df.index,
                    y=df['volume'],
                    name="Volume",
                    marker_color=colors,
                    opacity=0.7
                ),
                row=2, col=1
            )
            
            # Add volume MA
            if result.technical_indicators.volume_sma:
                vol_sma = result.technical_indicators.volume_sma
                if len(vol_sma) >= len(df):
                    fig.add_trace(
                        go.Scatter(
                            x=df.index[-len(vol_sma):],
                            y=vol_sma,
                            name=f"Volume SMA {self.config.volume_sma_period}",
                            line=dict(color="orange", width=1)
                        ),
                        row=2, col=1
                    )
            
            # RSI chart
            if result.technical_indicators.rsi:
                rsi = result.technical_indicators.rsi
                if len(rsi) >= len(df):
                    fig.add_trace(
                        go.Scatter(
                            x=df.index[-len(rsi):],
                            y=rsi,
                            name="RSI",
                            line=dict(color="purple", width=2)
                        ),
                        row=3, col=1
                    )
                    fig.add_hline(y=70, line_color="red", line_dash="dash", row=3, col=1)
                    fig.add_hline(y=30, line_color="green", line_dash="dash", row=3, col=1)
                    fig.add_hline(y=50, line_color="gray", line_dash="dot", row=3, col=1)
            
            # MACD chart
            if result.technical_indicators.macd:
                macd = result.technical_indicators.macd
                macd_signal = result.technical_indicators.macd_signal
                macd_hist = result.technical_indicators.macd_histogram
                if len(macd) >= len(df):
                    idx = df.index[-len(macd):]
                    fig.add_trace(
                        go.Scatter(
                            x=idx,
                            y=macd,
                            name="MACD",
                            line=dict(color="blue", width=2)
                        ),
                        row=4, col=1
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=idx,
                            y=macd_signal,
                            name="Signal",
                            line=dict(color="orange", width=2)
                        ),
                        row=4, col=1
                    )
                    # MACD histogram
                    colors_hist = ['green' if val > 0 else 'red' for val in macd_hist]
                    fig.add_trace(
                        go.Bar(
                            x=idx,
                            y=macd_hist,
                            name="Histogram",
                            marker_color=colors_hist,
                            opacity=0.5
                        ),
                        row=4, col=1
                    )
                    fig.add_hline(y=0, line_color="gray", line_dash="solid", row=4, col=1)
            
            # Update layout
            fig.update_layout(
                height=1200,
                title_text=f"Market Analysis - {result.symbol} ({result.timeframe})",
                template="plotly_dark",
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                xaxis_rangeslider_visible=False
            )
            
            # Update axes
            fig.update_xaxes(title_text="Date", row=5, col=1)
            fig.update_yaxes(title_text="Price", row=1, col=1)
            fig.update_yaxes(title_text="Volume", row=2, col=1)
            fig.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])
            fig.update_yaxes(title_text="MACD", row=4, col=1)
            fig.update_yaxes(title_text="Price", row=5, col=1)
            
            # Save chart
            chart_path = Path(self.config.output_dir) / f"{result.symbol}_market_analysis.html"
            chart_path.parent.mkdir(parents=True, exist_ok=True)
            fig.write_html(str(chart_path))
            chart_paths["analysis"] = str(chart_path)
            
        except Exception as e:
            self._logger.error(f"Error generating charts: {str(e)}")
        
        return chart_paths
    
    async def _save_results(self, result: MarketAnalysisResult) -> None:
        """Save analysis results to files."""
        try:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save JSON results
            json_path = output_dir / f"{result.symbol}_market_analysis.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, default=str)
                
            self._logger.info(f"Results saved to {output_dir}")
            
        except Exception as e:
            self._logger.error(f"Error saving results: {str(e)}")


# Factory function for easy initialization
def create_market_analyzer(
    lookback_periods: int = 200,
    generate_charts: bool = True,
    save_results: bool = True
) -> MarketAnalyzer:
    """
    Create a market analyzer with default configuration.
    
    Args:
        lookback_periods: Number of periods to look back
        generate_charts: Whether to generate charts
        save_results: Whether to save results
        
    Returns:
        Configured MarketAnalyzer instance
    """
    config = MarketAnalyzerConfig(
        lookback_periods=lookback_periods,
        generate_charts=generate_charts,
        save_results=save_results
    )
    return MarketAnalyzer(config)
