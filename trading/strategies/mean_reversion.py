# trading/strategies/mean_reversion.py
"""
NEXUS AI TRADING SYSTEM - Mean Reversion Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements mean reversion trading strategies including:
- Bollinger Bands reversion
- RSI-based reversion
- Z-score reversion
- Volatility-based reversion
- Channel reversion
- Pairs trading reversion

Mean reversion strategies profit from the assumption that asset prices
will revert to their historical mean or average over time.
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
from scipy import stats

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Signal, Position, Trade
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ReversionType(str, Enum):
    """Types of mean reversion strategies"""
    BOLLINGER_BANDS = "bollinger_bands"
    RSI = "rsi"
    Z_SCORE = "z_score"
    VOLATILITY = "volatility"
    CHANNEL = "channel"
    PAIRS = "pairs"
    COMBINED = "combined"


class EntryTrigger(str, Enum):
    """Entry trigger conditions"""
    BAND_TOUCH = "band_touch"          # Touch Bollinger Band
    RSI_OVERSOLD = "rsi_oversold"      # RSI below oversold threshold
    RSI_OVERBOUGHT = "rsi_overbought"  # RSI above overbought threshold
    Z_SCORE_EXCEED = "z_score_exceed"  # Z-score exceeds threshold
    CHANNEL_EXTREME = "channel_extreme" # Price at channel extreme
    COMBINED = "combined"              # Multiple conditions


@dataclass
class MeanReversionConfig:
    """Configuration for mean reversion strategy"""
    # Strategy type
    reversion_type: ReversionType = ReversionType.BOLLINGER_BANDS
    entry_trigger: EntryTrigger = EntryTrigger.BAND_TOUCH
    
    # Bollinger Bands
    bb_period: int = 20
    bb_std_dev: float = 2.0
    bb_use_close: bool = True
    
    # RSI
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    
    # Z-Score
    zscore_lookback: int = 30
    zscore_threshold: float = 2.0
    zscore_mean_reversion: float = 0.0  # Target z-score (0 = mean)
    
    # Volatility
    volatility_lookback: int = 20
    volatility_percentile: float = 90.0  # Percentile for high volatility
    
    # Channel
    channel_lookback: int = 20
    channel_width: float = 0.02  # 2% channel
    
    # Pairs trading
    pairs_lookback: int = 50
    pairs_correlation_threshold: float = 0.7
    pairs_half_life: int = 30
    
    # Risk management
    position_size: float = 1000.0
    max_position_size: float = 10000.0
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    max_positions: int = 3
    
    # Entry/Exit
    min_confidence: float = 0.6
    exit_at_mean: bool = True
    exit_at_band_middle: bool = True
    max_holding_period: int = 20  # bars
    
    # Filtering
    require_trend_filter: bool = False
    trend_ma_period: int = 50
    min_volume_ratio: float = 0.5


@dataclass
class MeanReversionState:
    """Current state of mean reversion strategy"""
    symbol: str
    current_price: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    z_score: float = 0.0
    rsi: float = 50.0
    volatility: float = 0.0
    
    # Bollinger Bands
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    
    # Channel
    channel_upper: float = 0.0
    channel_lower: float = 0.0
    
    # Position tracking
    position_count: int = 0
    entry_price: float = 0.0
    holding_period: int = 0
    is_long: bool = False
    
    # Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# MEAN REVERSION STRATEGY
# ============================================================================

class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion trading strategy that identifies and trades
    when price deviates significantly from its mean.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        reversion_config: Optional[MeanReversionConfig] = None,
    ):
        """
        Initialize the mean reversion strategy.
        
        Args:
            config: Strategy configuration
            reversion_config: Mean reversion configuration
        """
        super().__init__(config)
        self.reversion_config = reversion_config or MeanReversionConfig()
        
        # State management
        self._states: Dict[str, MeanReversionState] = {}
        
        # Data storage
        self._price_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        self._returns_history: Dict[str, deque] = {}
        
        # Indicator values
        self._indicators: Dict[str, Dict[str, float]] = {}
        
        # Performance tracking
        self._reversion_stats = {
            "total_signals": 0,
            "valid_signals": 0,
            "reversion_trades": 0,
            "successful_reversions": 0,
            "failed_reversions": 0,
            "avg_reversion_time": 0.0,
            "reversion_win_rate": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
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
        period = period or self.reversion_config.bb_period
        std_dev = std_dev or self.reversion_config.bb_std_dev
        
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
    
    def calculate_rsi(
        self,
        prices: List[float],
        period: Optional[int] = None,
    ) -> float:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            prices: Price series
            period: RSI period
            
        Returns:
            float: RSI value (0-100)
        """
        period = period or self.reversion_config.rsi_period
        
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
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return rsi
    
    def calculate_z_score(
        self,
        prices: List[float],
        lookback: Optional[int] = None,
    ) -> float:
        """
        Calculate Z-score of the current price.
        
        Args:
            prices: Price series
            lookback: Lookback period
            
        Returns:
            float: Z-score
        """
        lookback = lookback or self.reversion_config.zscore_lookback
        
        if len(prices) < lookback:
            return 0.0
        
        recent = prices[-lookback:]
        mean = sum(recent) / len(recent)
        std = math.sqrt(sum((p - mean) ** 2 for p in recent) / len(recent))
        
        if std == 0:
            return 0.0
        
        current = prices[-1]
        return (current - mean) / std
    
    def calculate_volatility(
        self,
        prices: List[float],
        lookback: Optional[int] = None,
    ) -> float:
        """
        Calculate volatility (standard deviation of returns).
        
        Args:
            prices: Price series
            lookback: Lookback period
            
        Returns:
            float: Volatility
        """
        lookback = lookback or self.reversion_config.volatility_lookback
        
        if len(prices) < lookback + 1:
            return 0.0
        
        returns = []
        for i in range(1, min(lookback + 1, len(prices))):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if not returns:
            return 0.0
        
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        
        return math.sqrt(variance)
    
    def calculate_channel(
        self,
        prices: List[float],
        lookback: Optional[int] = None,
        width: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Calculate price channel.
        
        Args:
            prices: Price series
            lookback: Lookback period
            width: Channel width percentage
            
        Returns:
            Tuple[float, float]: (upper, lower)
        """
        lookback = lookback or self.reversion_config.channel_lookback
        width = width or self.reversion_config.channel_width
        
        if len(prices) < lookback:
            return 0.0, 0.0
        
        recent = prices[-lookback:]
        mid = sum(recent) / len(recent)
        
        upper = mid * (1 + width)
        lower = mid * (1 - width)
        
        return upper, lower
    
    # ========================================================================
    # SIGNAL DETECTION
    # ========================================================================
    
    async def _detect_reversion_signal(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]] = None,
    ) -> Optional[Signal]:
        """
        Detect mean reversion signal.
        
        Args:
            symbol: Trading symbol
            prices: Price series
            volumes: Volume series
            
        Returns:
            Optional[Signal]: Reversion signal or None
        """
        if len(prices) < self.reversion_config.bb_period:
            return None
        
        current_price = prices[-1]
        
        # Initialize state
        if symbol not in self._states:
            self._states[symbol] = MeanReversionState(symbol=symbol)
        
        state = self._states[symbol]
        state.current_price = current_price
        
        # Store price history
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=100)
        self._price_history[symbol].append(current_price)
        
        # Calculate indicators
        reversion_type = self.reversion_config.reversion_type
        
        if reversion_type == ReversionType.BOLLINGER_BANDS:
            return await self._detect_bb_signal(symbol, prices, state)
        
        elif reversion_type == ReversionType.RSI:
            return await self._detect_rsi_signal(symbol, prices, state)
        
        elif reversion_type == ReversionType.Z_SCORE:
            return await self._detect_zscore_signal(symbol, prices, state)
        
        elif reversion_type == ReversionType.VOLATILITY:
            return await self._detect_volatility_signal(symbol, prices, state)
        
        elif reversion_type == ReversionType.CHANNEL:
            return await self._detect_channel_signal(symbol, prices, state)
        
        elif reversion_type == ReversionType.COMBINED:
            return await self._detect_combined_signal(symbol, prices, volumes, state)
        
        return None
    
    async def _detect_bb_signal(
        self,
        symbol: str,
        prices: List[float],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """Detect Bollinger Bands reversion signal."""
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        
        state.bb_upper = upper
        state.bb_middle = middle
        state.bb_lower = lower
        state.mean = middle
        
        current = prices[-1]
        
        # Buy signal: price at lower band (oversold)
        if current <= lower and self.reversion_config.entry_trigger in [
            EntryTrigger.BAND_TOUCH, EntryTrigger.COMBINED
        ]:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=current,
                state=state,
                reason=f"BB lower band touch at {lower:.2f}",
                metadata={"bb_lower": lower, "bb_middle": middle, "bb_upper": upper},
            )
        
        # Sell signal: price at upper band (overbought)
        elif current >= upper and self.reversion_config.entry_trigger in [
            EntryTrigger.BAND_TOUCH, EntryTrigger.COMBINED
        ]:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=current,
                state=state,
                reason=f"BB upper band touch at {upper:.2f}",
                metadata={"bb_lower": lower, "bb_middle": middle, "bb_upper": upper},
            )
        
        return None
    
    async def _detect_rsi_signal(
        self,
        symbol: str,
        prices: List[float],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """Detect RSI reversion signal."""
        rsi = self.calculate_rsi(prices)
        state.rsi = rsi
        
        # Buy signal: RSI oversold
        if rsi <= self.reversion_config.rsi_oversold:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=prices[-1],
                state=state,
                reason=f"RSI oversold: {rsi:.1f}",
                metadata={"rsi": rsi},
            )
        
        # Sell signal: RSI overbought
        elif rsi >= self.reversion_config.rsi_overbought:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=prices[-1],
                state=state,
                reason=f"RSI overbought: {rsi:.1f}",
                metadata={"rsi": rsi},
            )
        
        return None
    
    async def _detect_zscore_signal(
        self,
        symbol: str,
        prices: List[float],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """Detect Z-score reversion signal."""
        zscore = self.calculate_z_score(prices)
        state.z_score = zscore
        state.mean = sum(prices[-self.reversion_config.zscore_lookback:]) / min(len(prices), self.reversion_config.zscore_lookback)
        
        threshold = self.reversion_config.zscore_threshold
        
        # Buy signal: negative z-score (price below mean)
        if zscore <= -threshold:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=prices[-1],
                state=state,
                reason=f"Z-score below threshold: {zscore:.2f}",
                metadata={"zscore": zscore, "mean": state.mean},
            )
        
        # Sell signal: positive z-score (price above mean)
        elif zscore >= threshold:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=prices[-1],
                state=state,
                reason=f"Z-score above threshold: {zscore:.2f}",
                metadata={"zscore": zscore, "mean": state.mean},
            )
        
        return None
    
    async def _detect_volatility_signal(
        self,
        symbol: str,
        prices: List[float],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """Detect volatility reversion signal."""
        volatility = self.calculate_volatility(prices)
        state.volatility = volatility
        
        # Calculate historical volatility distribution
        if len(self._returns_history.get(symbol, deque())) < 50:
            return None
        
        hist_volatility = list(self._returns_history[symbol])
        percentile = np.percentile(hist_volatility, self.reversion_config.volatility_percentile)
        
        # High volatility suggests reversion opportunity
        if volatility > percentile:
            # Determine direction based on price position
            zscore = self.calculate_z_score(prices, 20)
            
            if zscore < -1:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.BUY,
                    price=prices[-1],
                    state=state,
                    reason=f"High volatility with low price: {volatility:.4f}",
                    metadata={"volatility": volatility, "zscore": zscore},
                )
            elif zscore > 1:
                return await self._create_signal(
                    symbol=symbol,
                    signal_type=SignalType.SELL,
                    price=prices[-1],
                    state=state,
                    reason=f"High volatility with high price: {volatility:.4f}",
                    metadata={"volatility": volatility, "zscore": zscore},
                )
        
        return None
    
    async def _detect_channel_signal(
        self,
        symbol: str,
        prices: List[float],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """Detect channel reversion signal."""
        upper, lower = self.calculate_channel(prices)
        
        state.channel_upper = upper
        state.channel_lower = lower
        
        current = prices[-1]
        
        # Buy signal: price at lower channel
        if current <= lower:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=current,
                state=state,
                reason=f"Channel lower touch: {lower:.2f}",
                metadata={"channel_upper": upper, "channel_lower": lower},
            )
        
        # Sell signal: price at upper channel
        elif current >= upper:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=current,
                state=state,
                reason=f"Channel upper touch: {upper:.2f}",
                metadata={"channel_upper": upper, "channel_lower": lower},
            )
        
        return None
    
    async def _detect_combined_signal(
        self,
        symbol: str,
        prices: List[float],
        volumes: Optional[List[float]],
        state: MeanReversionState,
    ) -> Optional[Signal]:
        """
        Detect combined mean reversion signal using multiple indicators.
        """
        # Calculate all indicators
        upper, middle, lower = self.calculate_bollinger_bands(prices)
        rsi = self.calculate_rsi(prices)
        zscore = self.calculate_z_score(prices)
        volatility = self.calculate_volatility(prices)
        
        state.bb_upper = upper
        state.bb_middle = middle
        state.bb_lower = lower
        state.rsi = rsi
        state.z_score = zscore
        state.volatility = volatility
        
        current = prices[-1]
        
        # Buy signal conditions
        buy_conditions = 0
        buy_conditions += 1 if current <= lower else 0  # BB lower touch
        buy_conditions += 1 if rsi <= 30 else 0  # RSI oversold
        buy_conditions += 1 if zscore <= -1.5 else 0  # Z-score below mean
        
        # Sell signal conditions
        sell_conditions = 0
        sell_conditions += 1 if current >= upper else 0  # BB upper touch
        sell_conditions += 1 if rsi >= 70 else 0  # RSI overbought
        sell_conditions += 1 if zscore >= 1.5 else 0  # Z-score above mean
        
        # Require at least 2 conditions
        if buy_conditions >= 2:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=current,
                state=state,
                reason=f"Combined buy signal: {buy_conditions} conditions met",
                metadata={
                    "bb_upper": upper,
                    "bb_middle": middle,
                    "bb_lower": lower,
                    "rsi": rsi,
                    "zscore": zscore,
                    "conditions_met": buy_conditions,
                },
            )
        
        elif sell_conditions >= 2:
            return await self._create_signal(
                symbol=symbol,
                signal_type=SignalType.SELL,
                price=current,
                state=state,
                reason=f"Combined sell signal: {sell_conditions} conditions met",
                metadata={
                    "bb_upper": upper,
                    "bb_middle": middle,
                    "bb_lower": lower,
                    "rsi": rsi,
                    "zscore": zscore,
                    "conditions_met": sell_conditions,
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
        state: MeanReversionState,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """
        Create a trading signal from reversion detection.
        
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
        # Check if we already have a position
        if len(self.positions) >= self.reversion_config.max_positions:
            return None
        
        # Check if symbol is already in position
        if symbol in self.positions:
            return None
        
        # Calculate confidence
        confidence = self._calculate_reversion_confidence(state, signal_type)
        
        if confidence < self.reversion_config.min_confidence:
            return None
        
        # Calculate position size
        position_size = self.reversion_config.position_size
        
        # Adjust size based on confidence
        if confidence > 0.8:
            position_size *= 1.5
        elif confidence < 0.7:
            position_size *= 0.75
        
        position_size = max(0, min(position_size, self.reversion_config.max_position_size))
        
        # Calculate stop loss and take profit
        stop_loss, take_profit = self._calculate_reversion_targets(
            price=price,
            signal_type=signal_type,
            state=state,
        )
        
        # Determine signal strength
        strength = self._determine_signal_strength(confidence)
        
        # Update state
        state.position_count += 1
        state.entry_price = price
        state.is_long = signal_type == SignalType.BUY
        state.holding_period = 0
        self._reversion_stats["total_signals"] += 1
        self._reversion_stats["valid_signals"] += 1
        
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
                "reversion_type": self.reversion_config.reversion_type.value,
                "entry_trigger": self.reversion_config.entry_trigger.value,
                "state": {
                    "bb_upper": state.bb_upper,
                    "bb_middle": state.bb_middle,
                    "bb_lower": state.bb_lower,
                    "rsi": state.rsi,
                    "z_score": state.z_score,
                    "volatility": state.volatility,
                },
            },
        )
        
        self.logger.info(
            f"Mean reversion signal: {signal_type.value} {symbol} @ {price:.2f} "
            f"(confidence: {confidence:.2f}) - {reason}"
        )
        
        return signal
    
    def _calculate_reversion_confidence(
        self,
        state: MeanReversionState,
        signal_type: SignalType,
    ) -> float:
        """
        Calculate confidence level for reversion signal.
        
        Args:
            state: Current state
            signal_type: Signal type
            
        Returns:
            float: Confidence level (0-1)
        """
        confidence = 0.6  # Base confidence
        
        if self.reversion_config.reversion_type == ReversionType.BOLLINGER_BANDS:
            # Higher confidence when price is further from mean
            if state.bb_middle > 0:
                deviation = abs(state.current_price - state.bb_middle) / state.bb_middle
                confidence += min(deviation * 5, 0.3)
        
        elif self.reversion_config.reversion_type == ReversionType.RSI:
            # Higher confidence when RSI is more extreme
            if signal_type == SignalType.BUY:
                rsi_deviation = (self.reversion_config.rsi_oversold - state.rsi) / self.reversion_config.rsi_oversold
            else:
                rsi_deviation = (state.rsi - self.reversion_config.rsi_overbought) / (100 - self.reversion_config.rsi_overbought)
            confidence += min(max(0, rsi_deviation * 0.3), 0.3)
        
        elif self.reversion_config.reversion_type == ReversionType.Z_SCORE:
            # Higher confidence when z-score is more extreme
            zscore_abs = abs(state.z_score)
            confidence += min((zscore_abs - 1) * 0.15, 0.3)
        
        elif self.reversion_config.reversion_type == ReversionType.COMBINED:
            # Multiple indicators boost confidence
            indicators = 0
            if state.current_price <= state.bb_lower or state.current_price >= state.bb_upper:
                indicators += 1
            if state.rsi <= 30 or state.rsi >= 70:
                indicators += 1
            if abs(state.z_score) >= 1.5:
                indicators += 1
            
            confidence += indicators * 0.1
        
        return min(0.95, confidence)
    
    def _determine_signal_strength(self, confidence: float) -> SignalStrength:
        """Determine signal strength based on confidence."""
        if confidence >= 0.85:
            return SignalStrength.STRONG
        elif confidence >= 0.7:
            return SignalStrength.MEDIUM
        else:
            return SignalStrength.WEAK
    
    def _calculate_reversion_targets(
        self,
        price: float,
        signal_type: SignalType,
        state: MeanReversionState,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate stop loss and take profit targets.
        
        Args:
            price: Entry price
            signal_type: Signal type
            state: Current state
            
        Returns:
            Tuple[Optional[float], Optional[float]]: (stop_loss, take_profit)
        """
        stop_loss_pct = self.reversion_config.stop_loss_pct
        take_profit_pct = self.reversion_config.take_profit_pct
        
        # If we have a mean, use it for take profit
        if self.reversion_config.exit_at_mean and state.mean > 0:
            if signal_type == SignalType.BUY and price < state.mean:
                # Mean is above price, use as initial target
                take_profit = state.mean
            elif signal_type == SignalType.SELL and price > state.mean:
                # Mean is below price, use as initial target
                take_profit = state.mean
            else:
                # Use percentage-based target
                if signal_type == SignalType.BUY:
                    take_profit = price * (1 + take_profit_pct)
                else:
                    take_profit = price * (1 - take_profit_pct)
        else:
            # Percentage-based targets
            if signal_type == SignalType.BUY:
                take_profit = price * (1 + take_profit_pct)
            else:
                take_profit = price * (1 - take_profit_pct)
        
        # Stop loss
        if signal_type == SignalType.BUY:
            stop_loss = price * (1 - stop_loss_pct)
        else:
            stop_loss = price * (1 + stop_loss_pct)
        
        return stop_loss, take_profit
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on mean reversion logic.
        
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
        
        # Update returns history
        if len(prices) > 1:
            returns = (prices[-1] - prices[-2]) / prices[-2]
            if symbol not in self._returns_history:
                self._returns_history[symbol] = deque(maxlen=100)
            self._returns_history[symbol].append(returns)
        
        # Detect reversion signal
        signal = await self._detect_reversion_signal(symbol, prices, volumes)
        
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
        
        # Update reversion stats
        self._reversion_stats["reversion_trades"] += 1
        
        if pnl > 0:
            self._reversion_stats["successful_reversions"] += 1
        else:
            self._reversion_stats["failed_reversions"] += 1
        
        # Calculate success rate
        total = self._reversion_stats["reversion_trades"]
        if total > 0:
            self._reversion_stats["reversion_win_rate"] = (
                self._reversion_stats["successful_reversions"] / total * 100
            )
        
        # Update state
        for state in self._states.values():
            if state.symbol == trade.symbol:
                state.total_trades += 1
                if pnl > 0:
                    state.winning_trades += 1
                else:
                    state.losing_trades += 1
                state.total_pnl += pnl
                break
    
    async def on_position_update(self, position: Position) -> None:
        """
        Handle position update.
        
        Args:
            position: Updated position
        """
        await super().on_position_update(position)
        
        # Update holding period
        for state in self._states.values():
            if state.symbol == position.symbol:
                state.holding_period += 1
                
                # Exit if holding period exceeded
                if self.reversion_config.max_holding_period > 0:
                    if state.holding_period >= self.reversion_config.max_holding_period:
                        self.logger.info(
                            f"Max holding period reached for {position.symbol}, closing position"
                        )
                        # Signal to close
                        signal = Signal(
                            symbol=position.symbol,
                            signal_type=SignalType.CLOSE,
                            strength=SignalStrength.MEDIUM,
                            confidence=0.8,
                            price=position.entry_price,
                            timestamp=datetime.utcnow(),
                            metadata={"reason": "max_holding_period"},
                        )
                        await self.process_signal(signal)
                break
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_reversion_stats(self) -> Dict[str, Any]:
        """
        Get mean reversion statistics.
        
        Returns:
            Dict[str, Any]: Reversion statistics
        """
        return {
            **self._reversion_stats,
            "current_states": {
                symbol: {
                    "price": state.current_price,
                    "mean": state.mean,
                    "z_score": state.z_score,
                    "rsi": state.rsi,
                    "bb_upper": state.bb_upper,
                    "bb_middle": state.bb_middle,
                    "bb_lower": state.bb_lower,
                    "holding_period": state.holding_period,
                    "total_trades": state.total_trades,
                    "total_pnl": state.total_pnl,
                }
                for symbol, state in self._states.items()
            },
            "config": {
                "reversion_type": self.reversion_config.reversion_type.value,
                "entry_trigger": self.reversion_config.entry_trigger.value,
                "bb_period": self.reversion_config.bb_period,
                "rsi_period": self.reversion_config.rsi_period,
                "zscore_threshold": self.reversion_config.zscore_threshold,
            },
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Mean reversion strategy started (type: {self.reversion_config.reversion_type.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        await super().on_stop()
        self.logger.info("Mean reversion strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ReversionType",
    "EntryTrigger",
    "MeanReversionConfig",
    "MeanReversionState",
    "MeanReversionStrategy",
]
