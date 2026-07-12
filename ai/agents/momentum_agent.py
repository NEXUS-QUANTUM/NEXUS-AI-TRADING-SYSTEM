"""
NEXUS AI TRADING SYSTEM - Momentum Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Momentum Agent system with:
- Multiple momentum strategies (Trend Following, MACD, Moving Average Crossover)
- Multi-timeframe analysis
- Trend detection and confirmation
- Breakout detection
- Dynamic position sizing
- Risk management
- Performance analytics
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator
from scipy import stats
from scipy.signal import find_peaks

from ai.agents.base_agent import BaseAgent, AgentHealth, AgentStatus
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_config import AgentConfig
from ai.agents.agent_registry import get_agent_registry
from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import get_broker
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import BrokerError, OrderError, MarketDataError
from backend.models.trading import Order, OrderSide, OrderType, OrderStatus

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class MomentumStrategy(str, Enum):
    """Momentum strategies"""
    TREND_FOLLOWING = "trend_following"
    MACD = "macd"
    MOVING_AVERAGE_CROSSOVER = "moving_average_crossover"
    BREAKOUT = "breakout"
    MOMENTUM_OSCILLATOR = "momentum_oscillator"
    AVERAGE_DIRECTIONAL_INDEX = "average_directional_index"
    PARABOLIC_SAR = "parabolic_sar"
    MOMENTUM_DIVERGENCE = "momentum_divergence"
    VOLUME_MOMENTUM = "volume_momentum"
    RELATIVE_STRENGTH = "relative_strength"


class TrendType(str, Enum):
    """Trend types"""
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    SIDEWAYS = "sideways"
    WEAK_DOWNTREND = "weak_downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class BreakoutType(str, Enum):
    """Breakout types"""
    RESISTANCE = "resistance"
    SUPPORT = "support"
    CONSOLIDATION = "consolidation"
    CHANNEL = "channel"
    PATTERN = "pattern"


@dataclass
class MomentumSignal:
    """Momentum signal"""
    timestamp: datetime
    symbol: str
    strategy: MomentumStrategy
    signal_type: str  # 'buy', 'sell', 'neutral', 'strong_buy', 'strong_sell'
    price: float
    momentum_value: float
    trend: TrendType
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MovingAverageData:
    """Moving average data"""
    sma: Dict[int, float]  # period -> value
    ema: Dict[int, float]  # period -> value
    wma: Dict[int, float]  # period -> value


@dataclass
class MACDData:
    """MACD data"""
    macd_line: float
    signal_line: float
    histogram: float
    crossover: Optional[str] = None  # 'bullish', 'bearish', None


@dataclass
class TrendData:
    """Trend data"""
    trend_type: TrendType
    strength: float  # 0-1
    duration: int  # number of periods
    slope: float
    momentum: float


@dataclass
class MomentumPosition:
    """Momentum position"""
    symbol: str
    entry_price: float
    entry_time: datetime
    position_size: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    entry_signal: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trailing_stop: Optional[float] = None
    highest_price: Optional[float] = None
    lowest_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = "open"
    strategy: Optional[MomentumStrategy] = None


@dataclass
class MomentumStats:
    """Momentum statistics"""
    symbol: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_holding_period: float = 0.0
    success_rate: float = 0.0
    max_consecutive_losses: int = 0
    max_consecutive_wins: int = 0


class MomentumConfig(BaseModel):
    """Momentum agent configuration"""
    enabled: bool = True
    symbols: List[str]
    strategies: List[MomentumStrategy]
    lookback_period: int = Field(default=200, gt=0)
    fast_ma_period: int = Field(default=10, gt=0)
    slow_ma_period: int = Field(default=30, gt=0)
    macd_fast: int = Field(default=12, gt=0)
    macd_slow: int = Field(default=26, gt=0)
    macd_signal: int = Field(default=9, gt=0)
    momentum_period: int = Field(default=14, gt=0)
    breakout_period: int = Field(default=20, gt=0)
    adx_period: int = Field(default=14, gt=0)
    rsi_period: int = Field(default=14, gt=0)
    entry_threshold: float = Field(default=0.0, ge=0)
    exit_threshold: float = Field(default=0.0, ge=0)
    stop_loss: float = Field(default=0.05, gt=0)
    take_profit: float = Field(default=0.15, gt=0)
    trailing_stop: Optional[float] = Field(default=0.02)
    max_position_size: float = Field(default=1000.0, gt=0)
    min_position_size: float = Field(default=10.0, gt=0)
    max_positions: int = Field(default=5, gt=0)
    max_drawdown: float = Field(default=0.10, ge=0, le=1)
    risk_per_trade: float = Field(default=0.01, ge=0, le=1)
    commission_rate: float = Field(default=0.001, ge=0)
    slippage: float = Field(default=0.001, ge=0)
    use_margin: bool = False
    leverage: float = Field(default=1.0, ge=0)
    max_leverage: float = Field(default=10.0, ge=0)
    trend_confirmation: bool = True
    multi_timeframe: bool = False
    timeframes: List[int] = Field(default=[1, 5, 15, 60])
    signal_refresh_interval: int = Field(default=5, gt=0)
    order_refresh_interval: int = Field(default=5, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    metrics_collection_interval: int = Field(default=10, gt=0)
    log_level: str = "info"


# ========================================
# MOMENTUM STRATEGIES
# ========================================

class BaseMomentumStrategy:
    """Base class for momentum strategies"""
    
    def __init__(self, config: MomentumConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.price_history: Dict[str, List[float]] = {}
        self.indicator_history: Dict[str, List[float]] = {}
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        """Calculate momentum signals"""
        raise NotImplementedError
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get current trend data"""
        raise NotImplementedError
    
    def add_price(self, symbol: str, price: float) -> None:
        """Add price to history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        
        if len(self.price_history[symbol]) > self.config.lookback_period * 3:
            self.price_history[symbol] = self.price_history[symbol][-self.config.lookback_period * 3:]


class TrendFollowingStrategy(BaseMomentumStrategy):
    """Trend following momentum strategy"""
    
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.trend_periods = [10, 20, 50, 200]
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        signals = []
        
        if len(prices) < max(self.trend_periods) + 1:
            return signals
        
        trend_data = await self.get_trend(symbol, prices)
        current_price = prices[-1]
        
        # Get moving averages
        ma_data = await self.calculate_moving_averages(prices)
        
        # Check for trend signals
        if trend_data.trend_type in [TrendType.STRONG_UPTREND, TrendType.WEAK_UPTREND]:
            # Check if price is above all moving averages
            above_all_ma = all(current_price > ma_data.sma.get(p, 0) for p in self.trend_periods)
            
            if above_all_ma and current_price > ma_data.sma.get(200, 0):
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.TREND_FOLLOWING,
                    signal_type="strong_buy" if trend_data.strength > 0.7 else "buy",
                    price=current_price,
                    momentum_value=trend_data.momentum,
                    trend=trend_data.trend_type,
                    confidence=trend_data.strength,
                    metadata={
                        "ma_values": {p: ma_data.sma.get(p) for p in self.trend_periods},
                        "trend_strength": trend_data.strength,
                        "trend_duration": trend_data.duration
                    }
                ))
        
        elif trend_data.trend_type in [TrendType.STRONG_DOWNTREND, TrendType.WEAK_DOWNTREND]:
            # Check if price is below all moving averages
            below_all_ma = all(current_price < ma_data.sma.get(p, 0) for p in self.trend_periods)
            
            if below_all_ma and current_price < ma_data.sma.get(200, 0):
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.TREND_FOLLOWING,
                    signal_type="strong_sell" if trend_data.strength > 0.7 else "sell",
                    price=current_price,
                    momentum_value=trend_data.momentum,
                    trend=trend_data.trend_type,
                    confidence=trend_data.strength,
                    metadata={
                        "ma_values": {p: ma_data.sma.get(p) for p in self.trend_periods},
                        "trend_strength": trend_data.strength,
                        "trend_duration": trend_data.duration
                    }
                ))
        
        # Exit signal: trend reversal
        if trend_data.trend_type == TrendType.SIDEWAYS:
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.TREND_FOLLOWING,
                signal_type="neutral",
                price=current_price,
                momentum_value=trend_data.momentum,
                trend=trend_data.trend_type,
                confidence=0.5,
                metadata={"message": "Trend is sideways, waiting for breakout"}
            ))
        
        return signals
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get trend data for trend following"""
        if len(prices) < 50:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        # Calculate slope using linear regression
        x = np.arange(len(prices[-50:]))
        y = np.array(prices[-50:])
        slope, intercept = np.polyfit(x, y, 1)
        
        # Calculate momentum using rate of change
        momentum = (prices[-1] / prices[-10] - 1) * 100 if len(prices) > 10 else 0
        
        # Calculate trend strength using ADX-like calculation
        strength = min(1.0, abs(slope) / (np.std(prices[-50:]) * 0.5))
        
        # Determine trend type
        if slope > 0:
            if strength > 0.7:
                trend_type = TrendType.STRONG_UPTREND
            else:
                trend_type = TrendType.WEAK_UPTREND
        elif slope < 0:
            if strength > 0.7:
                trend_type = TrendType.STRONG_DOWNTREND
            else:
                trend_type = TrendType.WEAK_DOWNTREND
        else:
            trend_type = TrendType.SIDEWAYS
        
        # Estimate duration of current trend
        duration = 0
        if len(prices) > 20:
            # Count consecutive bars in trend direction
            for i in range(1, min(20, len(prices))):
                if trend_type in [TrendType.STRONG_UPTREND, TrendType.WEAK_UPTREND]:
                    if prices[-i] > prices[-i-1]:
                        duration += 1
                    else:
                        break
                elif trend_type in [TrendType.STRONG_DOWNTREND, TrendType.WEAK_DOWNTREND]:
                    if prices[-i] < prices[-i-1]:
                        duration += 1
                    else:
                        break
        
        return TrendData(
            trend_type=trend_type,
            strength=strength,
            duration=duration,
            slope=slope,
            momentum=momentum
        )
    
    async def calculate_moving_averages(self, prices: List[float]) -> MovingAverageData:
        """Calculate moving averages"""
        sma_data = {}
        ema_data = {}
        wma_data = {}
        
        for period in self.trend_periods:
            if len(prices) >= period:
                # SMA
                sma = np.mean(prices[-period:])
                sma_data[period] = float(sma)
                
                # EMA
                if len(prices) >= period * 2:
                    ema = pd.Series(prices).ewm(span=period, adjust=False).mean().iloc[-1]
                    ema_data[period] = float(ema)
                
                # WMA
                if len(prices) >= period:
                    weights = np.arange(1, period + 1)
                    wma = np.sum(prices[-period:] * weights) / np.sum(weights)
                    wma_data[period] = float(wma)
        
        return MovingAverageData(sma=sma_data, ema=ema_data, wma=wma_data)


class MACDStrategy(BaseMomentumStrategy):
    """MACD momentum strategy"""
    
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.fast = config.macd_fast
        self.slow = config.macd_slow
        self.signal = config.macd_signal
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        signals = []
        
        if len(prices) < self.slow + self.signal:
            return signals
        
        macd_data = await self.calculate_macd(prices)
        current_price = prices[-1]
        
        # Bullish crossover: MACD crosses above signal line
        if (len(macd_data.histogram) > 1 and 
            macd_data.histogram[-2] <= 0 and 
            macd_data.histogram[-1] > 0):
            
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MACD,
                signal_type="buy",
                price=current_price,
                momentum_value=macd_data.histogram[-1],
                trend=TrendType.WEAK_UPTREND,
                confidence=0.8,
                metadata={
                    "macd_line": macd_data.macd_line,
                    "signal_line": macd_data.signal_line,
                    "crossover": "bullish"
                }
            ))
        
        # Bearish crossover: MACD crosses below signal line
        elif (len(macd_data.histogram) > 1 and 
              macd_data.histogram[-2] >= 0 and 
              macd_data.histogram[-1] < 0):
            
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MACD,
                signal_type="sell",
                price=current_price,
                momentum_value=macd_data.histogram[-1],
                trend=TrendType.WEAK_DOWNTREND,
                confidence=0.8,
                metadata={
                    "macd_line": macd_data.macd_line,
                    "signal_line": macd_data.signal_line,
                    "crossover": "bearish"
                }
            ))
        
        # Strong momentum: MACD and histogram both increasing
        elif (len(macd_data.histogram) > 2 and
              macd_data.histogram[-1] > macd_data.histogram[-2] > macd_data.histogram[-3]):
            
            if macd_data.macd_line > 0:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MACD,
                    signal_type="strong_buy",
                    price=current_price,
                    momentum_value=macd_data.histogram[-1],
                    trend=TrendType.STRONG_UPTREND,
                    confidence=0.9,
                    metadata={
                        "macd_line": macd_data.macd_line,
                        "signal_line": macd_data.signal_line,
                        "trend": "increasing"
                    }
                ))
            elif macd_data.macd_line < 0:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MACD,
                    signal_type="strong_sell",
                    price=current_price,
                    momentum_value=macd_data.histogram[-1],
                    trend=TrendType.STRONG_DOWNTREND,
                    confidence=0.9,
                    metadata={
                        "macd_line": macd_data.macd_line,
                        "signal_line": macd_data.signal_line,
                        "trend": "decreasing"
                    }
                ))
        
        return signals
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get trend data from MACD"""
        if len(prices) < self.slow + self.signal:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        macd_data = await self.calculate_macd(prices)
        
        # Determine trend from MACD
        if macd_data.macd_line > 0 and macd_data.histogram > 0:
            trend_type = TrendType.STRONG_UPTREND
            strength = min(1.0, abs(macd_data.macd_line) / 100)
        elif macd_data.macd_line > 0:
            trend_type = TrendType.WEAK_UPTREND
            strength = 0.5
        elif macd_data.macd_line < 0 and macd_data.histogram < 0:
            trend_type = TrendType.STRONG_DOWNTREND
            strength = min(1.0, abs(macd_data.macd_line) / 100)
        elif macd_data.macd_line < 0:
            trend_type = TrendType.WEAK_DOWNTREND
            strength = 0.5
        else:
            trend_type = TrendType.SIDEWAYS
            strength = 0.0
        
        return TrendData(
            trend_type=trend_type,
            strength=strength,
            duration=0,
            slope=0.0,
            momentum=macd_data.histogram
        )
    
    async def calculate_macd(self, prices: List[float]) -> MACDData:
        """Calculate MACD"""
        if len(prices) < self.slow:
            return MACDData(macd_line=0.0, signal_line=0.0, histogram=0.0)
        
        # Calculate EMAs
        ema_fast = pd.Series(prices).ewm(span=self.fast, adjust=False).mean()
        ema_slow = pd.Series(prices).ewm(span=self.slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return MACDData(
            macd_line=float(macd_line.iloc[-1]),
            signal_line=float(signal_line.iloc[-1]),
            histogram=float(histogram.iloc[-1])
        )


class MovingAverageCrossoverStrategy(BaseMomentumStrategy):
    """Moving average crossover momentum strategy"""
    
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.fast_period = config.fast_ma_period
        self.slow_period = config.slow_ma_period
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        signals = []
        
        if len(prices) < self.slow_period + 1:
            return signals
        
        # Calculate moving averages
        fast_ma = np.mean(prices[-self.fast_period:]) if len(prices) >= self.fast_period else 0
        slow_ma = np.mean(prices[-self.slow_period:]) if len(prices) >= self.slow_period else 0
        
        current_price = prices[-1]
        
        # Golden cross: fast MA crosses above slow MA
        if len(prices) > self.slow_period + 1:
            prev_fast_ma = np.mean(prices[-self.fast_period-1:-1]) if len(prices) >= self.fast_period + 1 else 0
            prev_slow_ma = np.mean(prices[-self.slow_period-1:-1]) if len(prices) >= self.slow_period + 1 else 0
            
            if prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MOVING_AVERAGE_CROSSOVER,
                    signal_type="strong_buy",
                    price=current_price,
                    momentum_value=fast_ma - slow_ma,
                    trend=TrendType.STRONG_UPTREND,
                    confidence=0.9,
                    metadata={
                        "fast_ma": fast_ma,
                        "slow_ma": slow_ma,
                        "crossover": "bullish"
                    }
                ))
            
            # Death cross: fast MA crosses below slow MA
            elif prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MOVING_AVERAGE_CROSSOVER,
                    signal_type="strong_sell",
                    price=current_price,
                    momentum_value=fast_ma - slow_ma,
                    trend=TrendType.STRONG_DOWNTREND,
                    confidence=0.9,
                    metadata={
                        "fast_ma": fast_ma,
                        "slow_ma": slow_ma,
                        "crossover": "bearish"
                    }
                ))
        
        # Trend confirmation: price above fast MA
        if current_price > fast_ma > slow_ma:
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MOVING_AVERAGE_CROSSOVER,
                signal_type="buy",
                price=current_price,
                momentum_value=fast_ma - slow_ma,
                trend=TrendType.WEAK_UPTREND,
                confidence=0.7,
                metadata={
                    "fast_ma": fast_ma,
                    "slow_ma": slow_ma,
                    "price_above": "both"
                }
            ))
        
        elif current_price < fast_ma < slow_ma:
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MOVING_AVERAGE_CROSSOVER,
                signal_type="sell",
                price=current_price,
                momentum_value=fast_ma - slow_ma,
                trend=TrendType.WEAK_DOWNTREND,
                confidence=0.7,
                metadata={
                    "fast_ma": fast_ma,
                    "slow_ma": slow_ma,
                    "price_below": "both"
                }
            ))
        
        return signals
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get trend data from moving averages"""
        if len(prices) < self.slow_period:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        fast_ma = np.mean(prices[-self.fast_period:])
        slow_ma = np.mean(prices[-self.slow_period:])
        
        if fast_ma > slow_ma:
            trend_type = TrendType.WEAK_UPTREND
            strength = min(1.0, (fast_ma - slow_ma) / slow_ma * 10)
        elif fast_ma < slow_ma:
            trend_type = TrendType.WEAK_DOWNTREND
            strength = min(1.0, (slow_ma - fast_ma) / slow_ma * 10)
        else:
            trend_type = TrendType.SIDEWAYS
            strength = 0.0
        
        return TrendData(
            trend_type=trend_type,
            strength=strength,
            duration=0,
            slope=0.0,
            momentum=fast_ma - slow_ma
        )


class BreakoutStrategy(BaseMomentumStrategy):
    """Breakout momentum strategy"""
    
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.period = config.breakout_period
        self.volume_threshold = 1.5
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        signals = []
        
        if len(prices) < self.period + 1:
            return signals
        
        # Calculate resistance and support levels
        recent_prices = prices[-self.period:]
        resistance = max(recent_prices)
        support = min(recent_prices)
        
        current_price = prices[-1]
        price_range = resistance - support
        
        # Breakout above resistance
        if current_price > resistance:
            # Check if it's a genuine breakout (price above resistance by > 0.5%)
            if current_price > resistance * 1.005:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.BREAKOUT,
                    signal_type="strong_buy" if current_price > resistance * 1.01 else "buy",
                    price=current_price,
                    momentum_value=current_price / resistance,
                    trend=TrendType.STRONG_UPTREND,
                    confidence=0.9,
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "breakout_type": "resistance"
                    }
                ))
        
        # Breakdown below support
        elif current_price < support:
            if current_price < support * 0.995:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.BREAKOUT,
                    signal_type="strong_sell" if current_price < support * 0.99 else "sell",
                    price=current_price,
                    momentum_value=current_price / support,
                    trend=TrendType.STRONG_DOWNTREND,
                    confidence=0.9,
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "breakout_type": "support"
                    }
                ))
        
        # Channel breakout
        if price_range > 0:
            # Check if price is at the top of the range
            if current_price > support + price_range * 0.9:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.BREAKOUT,
                    signal_type="buy",
                    price=current_price,
                    momentum_value=current_price / support,
                    trend=TrendType.WEAK_UPTREND,
                    confidence=0.6,
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "position": "near_resistance"
                    }
                ))
            elif current_price < support + price_range * 0.1:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.BREAKOUT,
                    signal_type="sell",
                    price=current_price,
                    momentum_value=current_price / support,
                    trend=TrendType.WEAK_DOWNTREND,
                    confidence=0.6,
                    metadata={
                        "resistance": resistance,
                        "support": support,
                        "position": "near_support"
                    }
                ))
        
        return signals
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get trend data from breakout"""
        if len(prices) < self.period:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        recent_prices = prices[-self.period:]
        resistance = max(recent_prices)
        support = min(recent_prices)
        current_price = prices[-1]
        
        price_range = resistance - support
        if price_range == 0:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        # Calculate position in range
        position = (current_price - support) / price_range
        
        if position > 0.8:
            trend_type = TrendType.WEAK_UPTREND
            strength = position
        elif position < 0.2:
            trend_type = TrendType.WEAK_DOWNTREND
            strength = 1 - position
        else:
            trend_type = TrendType.SIDEWAYS
            strength = 0.5
        
        return TrendData(
            trend_type=trend_type,
            strength=strength,
            duration=0,
            slope=0.0,
            momentum=position
        )


class MomentumOscillatorStrategy(BaseMomentumStrategy):
    """Momentum oscillator strategy (RSI-based)"""
    
    def __init__(self, config: MomentumConfig):
        super().__init__(config)
        self.period = config.momentum_period
        self.overbought = 70
        self.oversold = 30
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MomentumSignal]:
        signals = []
        
        if len(prices) < self.period + 1:
            return signals
        
        rsi = await self.calculate_rsi(prices)
        current_rsi = rsi[-1]
        current_price = prices[-1]
        
        # Buy signal: RSI oversold
        if current_rsi < self.oversold:
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MOMENTUM_OSCILLATOR,
                signal_type="buy",
                price=current_price,
                momentum_value=current_rsi,
                trend=TrendType.WEAK_UPTREND,
                confidence=1.0 - (current_rsi / self.oversold),
                metadata={
                    "rsi": current_rsi,
                    "oversold": self.oversold
                }
            ))
        
        # Sell signal: RSI overbought
        elif current_rsi > self.overbought:
            signals.append(MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.MOMENTUM_OSCILLATOR,
                signal_type="sell",
                price=current_price,
                momentum_value=current_rsi,
                trend=TrendType.WEAK_DOWNTREND,
                confidence=(current_rsi - self.overbought) / (100 - self.overbought),
                metadata={
                    "rsi": current_rsi,
                    "overbought": self.overbought
                }
            ))
        
        # Strong momentum: RSI moving up from oversold
        if len(rsi) > 2:
            if rsi[-2] < 30 and rsi[-1] > 30 and rsi[-1] > rsi[-2]:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MOMENTUM_OSCILLATOR,
                    signal_type="strong_buy",
                    price=current_price,
                    momentum_value=current_rsi,
                    trend=TrendType.STRONG_UPTREND,
                    confidence=0.9,
                    metadata={
                        "rsi": current_rsi,
                        "signal": "bullish_divergence"
                    }
                ))
            elif rsi[-2] > 70 and rsi[-1] < 70 and rsi[-1] < rsi[-2]:
                signals.append(MomentumSignal(
                    timestamp=datetime.utcnow(),
                    symbol=symbol,
                    strategy=MomentumStrategy.MOMENTUM_OSCILLATOR,
                    signal_type="strong_sell",
                    price=current_price,
                    momentum_value=current_rsi,
                    trend=TrendType.STRONG_DOWNTREND,
                    confidence=0.9,
                    metadata={
                        "rsi": current_rsi,
                        "signal": "bearish_divergence"
                    }
                ))
        
        return signals
    
    async def get_trend(self, symbol: str, prices: List[float]) -> TrendData:
        """Get trend data from RSI"""
        if len(prices) < self.period + 1:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        rsi = await self.calculate_rsi(prices)
        current_rsi = rsi[-1]
        
        if current_rsi > 60:
            trend_type = TrendType.WEAK_UPTREND
            strength = (current_rsi - 50) / 50
        elif current_rsi < 40:
            trend_type = TrendType.WEAK_DOWNTREND
            strength = (50 - current_rsi) / 50
        else:
            trend_type = TrendType.SIDEWAYS
            strength = 0.5
        
        return TrendData(
            trend_type=trend_type,
            strength=strength,
            duration=0,
            slope=0.0,
            momentum=current_rsi
        )
    
    async def calculate_rsi(self, prices: List[float]) -> List[float]:
        """Calculate RSI"""
        if len(prices) < self.period + 1:
            return [50] * len(prices)
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        
        avg_gain = np.mean(gains[:self.period])
        avg_loss = np.mean(losses[:self.period]) if np.mean(losses[:self.period]) > 0 else 0.001
        
        rsi_values = []
        
        for i in range(self.period, len(gains)):
            gain = gains[i-1]
            loss = losses[i-1]
            
            avg_gain = ((avg_gain * (self.period - 1)) + gain) / self.period
            avg_loss = ((avg_loss * (self.period - 1)) + loss) / self.period
            
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        return [50] * (self.period) + rsi_values


# ========================================
# MAIN MOMENTUM AGENT
# ========================================

class MomentumAgent(BaseAgent):
    """
    Momentum Agent for automated momentum trading.
    
    Features:
    - Multiple momentum strategies
    - Trend following
    - Breakout detection
    - Dynamic position sizing
    - Risk management
    - Performance analytics
    - Health monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._config = MomentumConfig(**config)
        self._broker: Optional[BaseBroker] = None
        self._strategies: Dict[MomentumStrategy, BaseMomentumStrategy] = {}
        
        # State
        self._positions: Dict[str, MomentumPosition] = {}
        self._stats: Dict[str, MomentumStats] = {}
        self._signals: List[MomentumSignal] = []
        self._price_data: Dict[str, List[float]] = {}
        self._trend_data: Dict[str, TrendData] = {}
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "neutral_signals": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "current_drawdown": 0.0,
            "avg_holding_period": 0.0,
            "avg_position_size": 0.0,
            "max_consecutive_losses": 0,
            "max_consecutive_wins": 0
        }
        
        self._initialize_strategies()
        self._initialize_broker()
        
        self.logger.info(f"MomentumAgent initialized for symbols: {self._config.symbols}")
    
    def _initialize_strategies(self) -> None:
        """Initialize momentum strategies"""
        strategy_map = {
            MomentumStrategy.TREND_FOLLOWING: TrendFollowingStrategy,
            MomentumStrategy.MACD: MACDStrategy,
            MomentumStrategy.MOVING_AVERAGE_CROSSOVER: MovingAverageCrossoverStrategy,
            MomentumStrategy.BREAKOUT: BreakoutStrategy,
            MomentumStrategy.MOMENTUM_OSCILLATOR: MomentumOscillatorStrategy
        }
        
        for strategy_type in self._config.strategies:
            if strategy_type in strategy_map:
                self._strategies[strategy_type] = strategy_map[strategy_type](self._config)
                self.logger.info(f"Initialized {strategy_type} strategy")
    
    def _initialize_broker(self) -> None:
        """Initialize broker connection"""
        try:
            self._broker = get_broker(self._config.exchange)
            self.logger.info(f"Initialized broker for {self._config.exchange}")
        except Exception as e:
            self.logger.error(f"Failed to initialize broker: {e}")
            raise
    
    # ========================================
    # AGENT LIFECYCLE
    # ========================================
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the momentum agent"""
        self.logger.info(f"Initializing MomentumAgent with config: {config}")
        
        if config:
            self._config = MomentumConfig(**{**self._config.dict(), **config})
        
        self._initialize_strategies()
        
        for symbol in self._config.symbols:
            self._stats[symbol] = MomentumStats(symbol=symbol)
            self._price_data[symbol] = []
        
        self.capabilities = [
            AgentCapability.MOMENTUM_TRADING,
            AgentCapability.TREND_FOLLOWING,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
        
        self.status = AgentStatus.INITIALIZED
        self.health = AgentHealth.HEALTHY
        self.logger.info("MomentumAgent initialized successfully")
    
    async def start(self) -> None:
        """Start the momentum agent"""
        self.logger.info("Starting MomentumAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._signal_loop()))
        self._tasks.append(asyncio.create_task(self._execution_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.health = AgentHealth.HEALTHY
        self.logger.info("MomentumAgent started successfully")
    
    async def stop(self) -> None:
        """Stop the momentum agent"""
        self.logger.info("Stopping MomentumAgent...")
        self._running = False
        
        await self._close_all_positions()
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.status = AgentStatus.STOPPED
        self.logger.info("MomentumAgent stopped")
    
    async def pause(self) -> None:
        """Pause the momentum agent"""
        self.logger.info("Pausing MomentumAgent...")
        self._running = False
        self.status = AgentStatus.PAUSED
        self.logger.info("MomentumAgent paused")
    
    async def resume(self) -> None:
        """Resume the momentum agent"""
        self.logger.info("Resuming MomentumAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._signal_loop()))
        self._tasks.append(asyncio.create_task(self._execution_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.logger.info("MomentumAgent resumed")
    
    async def health_check(self) -> AgentHealth:
        """Check agent health"""
        try:
            if not self._running:
                return AgentHealth.DEGRADED
            
            if not self._broker:
                return AgentHealth.UNHEALTHY
            
            if not self._strategies:
                return AgentHealth.DEGRADED
            
            for pos in self._positions.values():
                if pos.unrealized_pnl < -self._config.max_drawdown * abs(pos.position_size) * pos.entry_price:
                    return AgentHealth.DEGRADED
            
            return AgentHealth.HEALTHY
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return AgentHealth.UNHEALTHY
    
    # ========================================
    # SIGNAL GENERATION
    # ========================================
    
    async def _signal_loop(self) -> None:
        """Main signal generation loop"""
        while self._running:
            try:
                await self._generate_signals()
                await self._process_signals()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Signal loop error: {e}")
                self.health = AgentHealth.DEGRADED
            
            await asyncio.sleep(self._config.signal_refresh_interval)
    
    async def _generate_signals(self) -> None:
        """Generate momentum signals"""
        await self._update_prices()
        
        new_signals = []
        
        for symbol in self._config.symbols:
            prices = self._price_data.get(symbol, [])
            if len(prices) < self._config.lookback_period:
                continue
            
            # Get trend data
            trend_data = await self._get_trend_data(symbol, prices)
            self._trend_data[symbol] = trend_data
            
            for strategy in self._strategies.values():
                try:
                    signals = await strategy.calculate_signals(symbol, prices)
                    new_signals.extend(signals)
                except Exception as e:
                    self.logger.error(f"Strategy {strategy.__class__.__name__} error: {e}")
        
        self._signals = new_signals
        self._metrics["total_signals"] += len(new_signals)
    
    async def _get_trend_data(self, symbol: str, prices: List[float]) -> TrendData:
        """Get aggregated trend data from all strategies"""
        trend_data = []
        
        for strategy in self._strategies.values():
            try:
                data = await strategy.get_trend(symbol, prices)
                trend_data.append(data)
            except Exception as e:
                self.logger.error(f"Error getting trend from {strategy.__class__.__name__}: {e}")
        
        if not trend_data:
            return TrendData(
                trend_type=TrendType.SIDEWAYS,
                strength=0.0,
                duration=0,
                slope=0.0,
                momentum=0.0
            )
        
        # Aggregate trend data
        avg_strength = sum(t.strength for t in trend_data) / len(trend_data)
        avg_momentum = sum(t.momentum for t in trend_data) / len(trend_data)
        avg_duration = sum(t.duration for t in trend_data) / len(trend_data)
        
        # Determine trend type based on momentum
        if avg_momentum > 0.5 and avg_strength > 0.6:
            trend_type = TrendType.STRONG_UPTREND
        elif avg_momentum > 0.2:
            trend_type = TrendType.WEAK_UPTREND
        elif avg_momentum < -0.5 and avg_strength > 0.6:
            trend_type = TrendType.STRONG_DOWNTREND
        elif avg_momentum < -0.2:
            trend_type = TrendType.WEAK_DOWNTREND
        else:
            trend_type = TrendType.SIDEWAYS
        
        return TrendData(
            trend_type=trend_type,
            strength=avg_strength,
            duration=int(avg_duration),
            slope=0.0,
            momentum=avg_momentum
        )
    
    async def _update_prices(self) -> None:
        """Update price data from broker"""
        if not self._broker:
            return
        
        for symbol in self._config.symbols:
            try:
                ticker = await self._broker.get_ticker(symbol)
                if ticker:
                    price = ticker.get('last', 0)
                    if price > 0:
                        self._price_data[symbol].append(price)
                        
                        for strategy in self._strategies.values():
                            strategy.add_price(symbol, price)
                        
                        if len(self._price_data[symbol]) > self._config.lookback_period * 3:
                            self._price_data[symbol] = self._price_data[symbol][-self._config.lookback_period * 3:]
            except Exception as e:
                self.logger.error(f"Failed to update price for {symbol}: {e}")
    
    async def _process_signals(self) -> None:
        """Process and filter signals"""
        if not self._signals:
            return
        
        # Filter signals by confidence
        filtered_signals = [s for s in self._signals if s.confidence >= 0.6]
        
        # Group by symbol
        signals_by_symbol = {}
        for signal in filtered_signals:
            if signal.symbol not in signals_by_symbol:
                signals_by_symbol[signal.symbol] = []
            signals_by_symbol[signal.symbol].append(signal)
        
        # Process each symbol
        for symbol, signals in signals_by_symbol.items():
            # Get highest confidence signal
            best_signal = max(signals, key=lambda s: s.confidence)
            
            # Apply trend confirmation
            if self._config.trend_confirmation:
                trend = self._trend_data.get(symbol)
                if trend:
                    # Only trade in the direction of the trend
                    if best_signal.signal_type in ['buy', 'strong_buy']:
                        if trend.trend_type in [TrendType.STRONG_DOWNTREND, TrendType.WEAK_DOWNTREND]:
                            continue
                    elif best_signal.signal_type in ['sell', 'strong_sell']:
                        if trend.trend_type in [TrendType.STRONG_UPTREND, TrendType.WEAK_UPTREND]:
                            continue
            
            # Execute signal
            if best_signal.signal_type in ['buy', 'strong_buy']:
                await self._execute_buy_signal(best_signal)
            elif best_signal.signal_type in ['sell', 'strong_sell']:
                await self._execute_sell_signal(best_signal)
            elif best_signal.signal_type == 'neutral':
                await self._execute_exit_signal(best_signal)
    
    # ========================================
    # ORDER EXECUTION
    # ========================================
    
    async def _execution_loop(self) -> None:
        """Order execution monitoring loop"""
        while self._running:
            try:
                await self._update_positions()
                await self._check_stop_loss()
                await self._check_take_profit()
                await self._check_trailing_stop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Execution loop error: {e}")
            
            await asyncio.sleep(self._config.order_refresh_interval)
    
    async def _execute_buy_signal(self, signal: MomentumSignal) -> None:
        """Execute a buy signal"""
        if len(self._positions) >= self._config.max_positions:
            self.logger.warning("Max positions reached")
            return
        
        # Check if already in position
        if signal.symbol in self._positions:
            pos = self._positions[signal.symbol]
            if pos.status == "open":
                self.logger.warning(f"Already in position for {signal.symbol}")
                return
        
        # Calculate position size
        position_size = await self._calculate_position_size(signal)
        if position_size < self._config.min_position_size:
            self.logger.warning(f"Position size {position_size} below minimum")
            return
        
        try:
            order = await self._broker.create_order(
                symbol=signal.symbol,
                side='buy',
                type='market',
                quantity=position_size
            )
            
            if order:
                entry_price = order.get('price', signal.price)
                
                position = MomentumPosition(
                    symbol=signal.symbol,
                    entry_price=entry_price,
                    entry_time=datetime.utcnow(),
                    position_size=position_size,
                    current_price=entry_price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    total_pnl=0,
                    entry_signal=signal.signal_type,
                    stop_loss=entry_price * (1 - self._config.stop_loss),
                    take_profit=entry_price * (1 + self._config.take_profit),
                    trailing_stop=self._config.trailing_stop * entry_price if self._config.trailing_stop else None,
                    highest_price=entry_price,
                    lowest_price=entry_price,
                    strategy=signal.strategy
                )
                
                self._positions[signal.symbol] = position
                self._metrics["total_trades"] += 1
                
                self.logger.info(f"BUY signal executed: {signal.symbol} @ {entry_price:.4f} | Size: {position_size:.2f}")
                
        except Exception as e:
            self.logger.error(f"Failed to execute buy signal: {e}")
    
    async def _execute_sell_signal(self, signal: MomentumSignal) -> None:
        """Execute a sell signal"""
        if len(self._positions) >= self._config.max_positions:
            self.logger.warning("Max positions reached")
            return
        
        if signal.symbol in self._positions:
            pos = self._positions[signal.symbol]
            if pos.status == "open":
                self.logger.warning(f"Already in position for {signal.symbol}")
                return
        
        position_size = await self._calculate_position_size(signal)
        if position_size < self._config.min_position_size:
            self.logger.warning(f"Position size {position_size} below minimum")
            return
        
        try:
            order = await self._broker.create_order(
                symbol=signal.symbol,
                side='sell',
                type='market',
                quantity=position_size
            )
            
            if order:
                entry_price = order.get('price', signal.price)
                
                position = MomentumPosition(
                    symbol=signal.symbol,
                    entry_price=entry_price,
                    entry_time=datetime.utcnow(),
                    position_size=-position_size,
                    current_price=entry_price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    total_pnl=0,
                    entry_signal=signal.signal_type,
                    stop_loss=entry_price * (1 + self._config.stop_loss),
                    take_profit=entry_price * (1 - self._config.take_profit),
                    trailing_stop=self._config.trailing_stop * entry_price if self._config.trailing_stop else None,
                    highest_price=entry_price,
                    lowest_price=entry_price,
                    strategy=signal.strategy
                )
                
                self._positions[signal.symbol] = position
                self._metrics["total_trades"] += 1
                
                self.logger.info(f"SELL signal executed: {signal.symbol} @ {entry_price:.4f} | Size: {position_size:.2f}")
                
        except Exception as e:
            self.logger.error(f"Failed to execute sell signal: {e}")
    
    async def _execute_exit_signal(self, signal: MomentumSignal) -> None:
        """Execute an exit signal"""
        if signal.symbol not in self._positions:
            return
        
        position = self._positions[signal.symbol]
        if position.status != "open":
            return
        
        # Check if we should exit based on trend
        if self._config.trend_confirmation:
            trend = self._trend_data.get(signal.symbol)
            if trend:
                # Don't exit if trend is still strong
                if position.position_size > 0 and trend.trend_type in [TrendType.STRONG_UPTREND, TrendType.WEAK_UPTREND]:
                    return
                if position.position_size < 0 and trend.trend_type in [TrendType.STRONG_DOWNTREND, TrendType.WEAK_DOWNTREND]:
                    return
        
        await self._close_position(signal.symbol, "exit_signal")
    
    async def _calculate_position_size(self, signal: MomentumSignal) -> float:
        """Calculate position size based on risk"""
        risk_amount = self._config.risk_per_trade * self._config.max_position_size
        stop_loss_pct = self._config.stop_loss
        
        if stop_loss_pct > 0:
            position_size = risk_amount / (signal.price * stop_loss_pct)
        else:
            position_size = self._config.min_position_size
        
        # Apply max position limit
        position_size = min(position_size, self._config.max_position_size)
        position_size = max(position_size, self._config.min_position_size)
        
        return position_size
    
    async def _update_positions(self) -> None:
        """Update positions with current prices"""
        if not self._broker:
            return
        
        for symbol, position in list(self._positions.items()):
            if position.status != "open":
                continue
                
            try:
                ticker = await self._broker.get_ticker(symbol)
                if ticker:
                    current_price = ticker.get('last', position.current_price)
                    position.current_price = current_price
                    
                    # Update highest/lowest
                    if current_price > position.highest_price or position.highest_price is None:
                        position.highest_price = current_price
                    if current_price < position.lowest_price or position.lowest_price is None:
                        position.lowest_price = current_price
                    
                    # Calculate P&L
                    if position.position_size > 0:
                        position.unrealized_pnl = (current_price - position.entry_price) * position.position_size
                    else:
                        position.unrealized_pnl = (position.entry_price - current_price) * abs(position.position_size)
                    
                    position.total_pnl = position.realized_pnl + position.unrealized_pnl
                    
                    # Update trailing stop
                    if position.trailing_stop:
                        if position.position_size > 0:
                            # Long position: trail stop up
                            new_stop = current_price * (1 - self._config.trailing_stop)
                            if new_stop > position.stop_loss:
                                position.stop_loss = new_stop
                        else:
                            # Short position: trail stop down
                            new_stop = current_price * (1 + self._config.trailing_stop)
                            if new_stop < position.stop_loss:
                                position.stop_loss = new_stop
            except Exception as e:
                self.logger.error(f"Failed to update position {symbol}: {e}")
    
    async def _check_stop_loss(self) -> None:
        """Check and execute stop loss"""
        for symbol, position in list(self._positions.items()):
            if position.status != "open" or position.stop_loss is None:
                continue
            
            should_stop = False
            if position.position_size > 0:
                if position.current_price <= position.stop_loss:
                    should_stop = True
            else:
                if position.current_price >= position.stop_loss:
                    should_stop = True
            
            if should_stop:
                self.logger.info(f"Stop loss triggered for {symbol} at {position.current_price:.4f}")
                await self._close_position(symbol, "stop_loss")
    
    async def _check_take_profit(self) -> None:
        """Check and execute take profit"""
        for symbol, position in list(self._positions.items()):
            if position.status != "open" or position.take_profit is None:
                continue
            
            should_take = False
            if position.position_size > 0:
                if position.current_price >= position.take_profit:
                    should_take = True
            else:
                if position.current_price <= position.take_profit:
                    should_take = True
            
            if should_take:
                self.logger.info(f"Take profit triggered for {symbol} at {position.current_price:.4f}")
                await self._close_position(symbol, "take_profit")
    
    async def _check_trailing_stop(self) -> None:
        """Check and execute trailing stop"""
        # Trailing stop is updated in _update_positions
        pass
    
    async def _close_position(self, symbol: str, reason: str) -> None:
        """Close a position"""
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        if position.status != "open":
            return
        
        try:
            side = 'sell' if position.position_size > 0 else 'buy'
            quantity = abs(position.position_size)
            
            order = await self._broker.create_order(
                symbol=symbol,
                side=side,
                type='market',
                quantity=quantity
            )
            
            if order:
                exit_price = order.get('price', position.current_price)
                position.exit_price = exit_price
                position.exit_time = datetime.utcnow()
                position.status = "closed"
                
                # Calculate P&L
                if position.position_size > 0:
                    position.realized_pnl = (exit_price - position.entry_price) * position.position_size
                else:
                    position.realized_pnl = (position.entry_price - exit_price) * abs(position.position_size)
                
                position.total_pnl = position.realized_pnl
                
                # Update stats
                stats = self._stats.get(symbol)
                if stats:
                    stats.total_trades += 1
                    stats.total_pnl += position.realized_pnl
                    if position.realized_pnl > 0:
                        stats.winning_trades += 1
                    else:
                        stats.losing_trades += 1
                
                self._metrics["total_pnl"] += position.realized_pnl
                if position.realized_pnl > 0:
                    self._metrics["winning_trades"] += 1
                else:
                    self._metrics["losing_trades"] += 1
                
                self.logger.info(
                    f"Position closed: {symbol} @ {exit_price:.4f} | "
                    f"Reason: {reason} | P&L: {position.realized_pnl:.2f}"
                )
                
                del self._positions[symbol]
                
        except Exception as e:
            self.logger.error(f"Failed to close position {symbol}: {e}")
    
    async def _close_all_positions(self) -> None:
        """Close all open positions"""
        for symbol in list(self._positions.keys()):
            await self._close_position(symbol, "manual_close")
    
    # ========================================
    # STATISTICS & METRICS
    # ========================================
    
    async def _update_stats(self) -> None:
        """Update statistics"""
        for symbol, stats in self._stats.items():
            if stats.total_trades > 0:
                stats.win_rate = stats.winning_trades / stats.total_trades
                stats.avg_win = stats.total_pnl / stats.total_trades if stats.total_trades > 0 else 0
        
        total_trades = self._metrics["total_trades"]
        if total_trades > 0:
            self._metrics["win_rate"] = self._metrics["winning_trades"] / total_trades
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                self.health = await self.health_check()
                self.logger.debug(f"Health: {self.health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self._config.health_check_interval)
    
    async def _metrics_loop(self) -> None:
        """Metrics collection loop"""
        while self._running:
            try:
                await self._update_stats()
                await self.save_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics loop error: {e}")
            
            await asyncio.sleep(self._config.metrics_collection_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions"""
        positions = {}
        for symbol, pos in self._positions.items():
            if pos.status != "open":
                continue
            positions[symbol] = {
                "symbol": pos.symbol,
                "entry_price": pos.entry_price,
                "entry_time": pos.entry_time.isoformat(),
                "position_size": pos.position_size,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "total_pnl": pos.total_pnl,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "trailing_stop": pos.trailing_stop,
                "highest_price": pos.highest_price,
                "lowest_price": pos.lowest_price,
                "entry_signal": pos.entry_signal,
                "strategy": pos.strategy.value if pos.strategy else None
            }
        return positions
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        stats = {}
        for symbol, stat in self._stats.items():
            stats[symbol] = {
                "symbol": stat.symbol,
                "total_trades": stat.total_trades,
                "winning_trades": stat.winning_trades,
                "losing_trades": stat.losing_trades,
                "total_pnl": stat.total_pnl,
                "win_rate": stat.win_rate,
                "avg_win": stat.avg_win,
                "avg_loss": stat.avg_loss,
                "profit_factor": stat.profit_factor,
                "sharpe_ratio": stat.sharpe_ratio,
                "max_drawdown": stat.max_drawdown,
                "avg_holding_period": stat.avg_holding_period,
                "success_rate": stat.success_rate,
                "max_consecutive_losses": stat.max_consecutive_losses,
                "max_consecutive_wins": stat.max_consecutive_wins
            }
        return stats
    
    async def get_signals(self) -> List[Dict[str, Any]]:
        """Get recent signals"""
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "strategy": s.strategy.value,
                "signal_type": s.signal_type,
                "price": s.price,
                "momentum_value": s.momentum_value,
                "trend": s.trend.value,
                "confidence": s.confidence,
                "metadata": s.metadata
            }
            for s in self._signals[-20:]
        ]
    
    async def get_trends(self) -> Dict[str, Dict[str, Any]]:
        """Get current trends"""
        trends = {}
        for symbol, trend in self._trend_data.items():
            trends[symbol] = {
                "trend_type": trend.trend_type.value,
                "strength": trend.strength,
                "duration": trend.duration,
                "momentum": trend.momentum
            }
        return trends
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            **self._metrics,
            "positions": len([p for p in self._positions.values() if p.status == "open"]),
            "signals_count": len(self._signals),
            "active_strategies": list(self._strategies.keys()),
            "running": self._running,
            "status": self.status,
            "health": self.health
        }
    
    async def force_update(self) -> None:
        """Force an immediate update"""
        await self._update_prices()
        await self._generate_signals()
        await self._process_signals()
        await self._update_positions()
    
    async def force_signal(self, symbol: str, signal_type: str) -> None:
        """Force a signal for testing"""
        price = self._price_data.get(symbol, [100])[-1] if self._price_data.get(symbol) else 100
        
        if signal_type in ['buy', 'strong_buy']:
            signal = MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.TREND_FOLLOWING,
                signal_type=signal_type,
                price=price,
                momentum_value=1.0,
                trend=TrendType.STRONG_UPTREND,
                confidence=0.9
            )
            await self._execute_buy_signal(signal)
        elif signal_type in ['sell', 'strong_sell']:
            signal = MomentumSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MomentumStrategy.TREND_FOLLOWING,
                signal_type=signal_type,
                price=price,
                momentum_value=-1.0,
                trend=TrendType.STRONG_DOWNTREND,
                confidence=0.9
            )
            await self._execute_sell_signal(signal)
    
    # ========================================
    # STATE PERSISTENCE
    # ========================================
    
    async def save_state(self) -> None:
        """Save agent state"""
        try:
            state = {
                "positions": await self.get_positions(),
                "stats": await self.get_stats(),
                "metrics": self._metrics,
                "price_data": {
                    symbol: prices[-100:] for symbol, prices in self._price_data.items()
                }
            }
            
            key = f"momentum_state:{self.agent_id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(state, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")


# ========================================
# DEPENDENCY INJECTION
# ========================================

def create_momentum_agent(config: Dict[str, Any]) -> MomentumAgent:
    """Create a momentum agent instance"""
    return MomentumAgent(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MomentumAgent',
    'MomentumConfig',
    'MomentumStrategy',
    'TrendType',
    'BreakoutType',
    'MomentumSignal',
    'MovingAverageData',
    'MACDData',
    'TrendData',
    'MomentumPosition',
    'MomentumStats',
    'create_momentum_agent'
]
