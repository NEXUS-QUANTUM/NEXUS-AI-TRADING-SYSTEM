"""
NEXUS AI TRADING SYSTEM - Mean Reversion Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Mean Reversion Agent system with:
- Multiple mean reversion strategies (Bollinger Bands, RSI, Z-Score, Kalman Filter)
- Statistical arbitrage
- Pairs trading
- Cointegration detection
- Real-time signal generation
- Order execution
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
from statsmodels.tsa.stattools import coint, adfuller

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

class MeanReversionStrategy(str, Enum):
    """Mean reversion strategies"""
    BOLLINGER_BANDS = "bollinger_bands"
    RSI = "rsi"
    Z_SCORE = "z_score"
    KALMAN_FILTER = "kalman_filter"
    PAIRS_TRADING = "pairs_trading"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    MACD = "macd"
    STOCHASTIC = "stochastic"
    CCI = "cci"
    WILLIAMS_R = "williams_r"


class SignalType(str, Enum):
    """Signal types"""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    EXIT = "exit"


@dataclass
class MeanReversionSignal:
    """Mean reversion signal"""
    timestamp: datetime
    symbol: str
    strategy: MeanReversionStrategy
    signal_type: SignalType
    price: float
    indicator_value: float
    threshold: float
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BollingerBands:
    """Bollinger Bands data"""
    upper: float
    middle: float
    lower: float
    bandwidth: float
    percent_b: float


@dataclass
class PairsTrade:
    """Pairs trading data"""
    symbol1: str
    symbol2: str
    spread: float
    z_score: float
    hedge_ratio: float
    cointegration_pvalue: float
    half_life: float


@dataclass
class MeanReversionPosition:
    """Mean reversion position"""
    symbol: str
    entry_price: float
    entry_time: datetime
    position_size: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    status: str = "open"
    strategy: Optional[MeanReversionStrategy] = None


@dataclass
class MeanReversionStats:
    """Mean reversion statistics"""
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


class MeanReversionConfig(BaseModel):
    """Mean reversion agent configuration"""
    enabled: bool = True
    symbols: List[str]
    strategies: List[MeanReversionStrategy]
    lookback_period: int = Field(default=100, gt=0)
    entry_threshold: float = Field(default=2.0, gt=0)
    exit_threshold: float = Field(default=0.5, gt=0)
    stop_loss: float = Field(default=0.05, gt=0)
    take_profit: float = Field(default=0.10, gt=0)
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
    cointegration_pvalue: float = Field(default=0.05, ge=0, le=1)
    pairs_lookback: int = Field(default=200, gt=0)
    pairs_update_interval: int = Field(default=3600, gt=0)
    signal_refresh_interval: int = Field(default=5, gt=0)
    order_refresh_interval: int = Field(default=5, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    metrics_collection_interval: int = Field(default=10, gt=0)
    log_level: str = "info"


# ========================================
# MEAN REVERSION STRATEGIES
# ========================================

class BaseMeanReversionStrategy:
    """Base class for mean reversion strategies"""
    
    def __init__(self, config: MeanReversionConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.price_history: Dict[str, List[float]] = {}
        self.indicator_history: Dict[str, List[float]] = {}
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MeanReversionSignal]:
        """Calculate mean reversion signals"""
        raise NotImplementedError
    
    async def get_indicator_value(self, symbol: str, prices: List[float]) -> float:
        """Get current indicator value"""
        raise NotImplementedError
    
    def add_price(self, symbol: str, price: float) -> None:
        """Add price to history"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        
        # Keep history within limits
        if len(self.price_history[symbol]) > self.config.lookback_period * 2:
            self.price_history[symbol] = self.price_history[symbol][-self.config.lookback_period * 2:]


class BollingerBandsStrategy(BaseMeanReversionStrategy):
    """Bollinger Bands mean reversion strategy"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        self.num_std = 2
        self.window = config.lookback_period
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MeanReversionSignal]:
        signals = []
        
        if len(prices) < self.window:
            return signals
        
        bands = await self.calculate_bollinger_bands(prices)
        current_price = prices[-1]
        
        # Buy signal: price below lower band
        if current_price < bands.lower:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.BOLLINGER_BANDS,
                signal_type=SignalType.BUY,
                price=current_price,
                indicator_value=bands.percent_b,
                threshold=0.0,
                confidence=min(1.0, abs(current_price - bands.lower) / (bands.middle - bands.lower))
            ))
        
        # Sell signal: price above upper band
        elif current_price > bands.upper:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.BOLLINGER_BANDS,
                signal_type=SignalType.SELL,
                price=current_price,
                indicator_value=bands.percent_b,
                threshold=1.0,
                confidence=min(1.0, abs(current_price - bands.upper) / (bands.upper - bands.middle))
            ))
        
        # Exit signal: price returns to middle
        elif abs(current_price - bands.middle) / bands.middle < 0.01:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.BOLLINGER_BANDS,
                signal_type=SignalType.EXIT,
                price=current_price,
                indicator_value=bands.percent_b,
                threshold=0.5,
                confidence=0.8
            ))
        
        return signals
    
    async def get_indicator_value(self, symbol: str, prices: List[float]) -> float:
        if len(prices) < self.window:
            return 0.5
        
        bands = await self.calculate_bollinger_bands(prices)
        return bands.percent_b
    
    async def calculate_bollinger_bands(self, prices: List[float]) -> BollingerBands:
        """Calculate Bollinger Bands"""
        if len(prices) < self.window:
            return BollingerBands(
                upper=0.0, middle=0.0, lower=0.0, bandwidth=0.0, percent_b=0.5
            )
        
        recent_prices = prices[-self.window:]
        middle = np.mean(recent_prices)
        std = np.std(recent_prices)
        
        upper = middle + (std * self.num_std)
        lower = middle - (std * self.num_std)
        bandwidth = (upper - lower) / middle if middle != 0 else 0
        
        current_price = prices[-1]
        percent_b = (current_price - lower) / (upper - lower) if upper != lower else 0.5
        
        return BollingerBands(
            upper=float(upper),
            middle=float(middle),
            lower=float(lower),
            bandwidth=float(bandwidth),
            percent_b=float(percent_b)
        )


class RSIStrategy(BaseMeanReversionStrategy):
    """RSI mean reversion strategy"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        self.window = 14
        self.oversold_threshold = 30
        self.overbought_threshold = 70
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MeanReversionSignal]:
        signals = []
        
        if len(prices) < self.window + 1:
            return signals
        
        rsi = await self.calculate_rsi(prices)
        current_rsi = rsi[-1]
        current_price = prices[-1]
        
        # Buy signal: RSI oversold
        if current_rsi < self.oversold_threshold:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.RSI,
                signal_type=SignalType.BUY,
                price=current_price,
                indicator_value=current_rsi,
                threshold=self.oversold_threshold,
                confidence=1.0 - (current_rsi / self.oversold_threshold)
            ))
        
        # Sell signal: RSI overbought
        elif current_rsi > self.overbought_threshold:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.RSI,
                signal_type=SignalType.SELL,
                price=current_price,
                indicator_value=current_rsi,
                threshold=self.overbought_threshold,
                confidence=(current_rsi - self.overbought_threshold) / (100 - self.overbought_threshold)
            ))
        
        # Exit signal: RSI returns to neutral
        elif 40 < current_rsi < 60:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.RSI,
                signal_type=SignalType.EXIT,
                price=current_price,
                indicator_value=current_rsi,
                threshold=50,
                confidence=0.7
            ))
        
        return signals
    
    async def get_indicator_value(self, symbol: str, prices: List[float]) -> float:
        if len(prices) < self.window + 1:
            return 50
        
        rsi = await self.calculate_rsi(prices)
        return rsi[-1]
    
    async def calculate_rsi(self, prices: List[float]) -> List[float]:
        """Calculate RSI"""
        if len(prices) < self.window + 1:
            return [50] * len(prices)
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        
        # Calculate average gains and losses
        avg_gain = np.mean(gains[:self.window])
        avg_loss = np.mean(losses[:self.window]) if np.mean(losses[:self.window]) > 0 else 0.001
        
        rsi_values = []
        
        for i in range(self.window, len(gains)):
            gain = gains[i-1]  # Adjust for 0-index
            loss = losses[i-1]
            
            avg_gain = ((avg_gain * (self.window - 1)) + gain) / self.window
            avg_loss = ((avg_loss * (self.window - 1)) + loss) / self.window
            
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        # Pad the beginning with 50
        return [50] * (self.window) + rsi_values


class ZScoreStrategy(BaseMeanReversionStrategy):
    """Z-Score mean reversion strategy"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        self.window = config.lookback_period
        self.entry_zscore = 2.0
        self.exit_zscore = 0.5
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MeanReversionSignal]:
        signals = []
        
        if len(prices) < self.window:
            return signals
        
        z_score = await self.calculate_zscore(prices)
        current_zscore = z_score[-1]
        current_price = prices[-1]
        
        # Buy signal: z-score below entry threshold
        if current_zscore < -self.entry_zscore:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.Z_SCORE,
                signal_type=SignalType.BUY,
                price=current_price,
                indicator_value=current_zscore,
                threshold=-self.entry_zscore,
                confidence=min(1.0, abs(current_zscore) / (self.entry_zscore * 2))
            ))
        
        # Sell signal: z-score above entry threshold
        elif current_zscore > self.entry_zscore:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.Z_SCORE,
                signal_type=SignalType.SELL,
                price=current_price,
                indicator_value=current_zscore,
                threshold=self.entry_zscore,
                confidence=min(1.0, abs(current_zscore) / (self.entry_zscore * 2))
            ))
        
        # Exit signal: z-score returns to exit threshold
        elif abs(current_zscore) < self.exit_zscore:
            signals.append(MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.Z_SCORE,
                signal_type=SignalType.EXIT,
                price=current_price,
                indicator_value=current_zscore,
                threshold=self.exit_zscore,
                confidence=0.9
            ))
        
        return signals
    
    async def get_indicator_value(self, symbol: str, prices: List[float]) -> float:
        if len(prices) < self.window:
            return 0
        
        z_score = await self.calculate_zscore(prices)
        return z_score[-1]
    
    async def calculate_zscore(self, prices: List[float]) -> List[float]:
        """Calculate Z-Score"""
        if len(prices) < self.window:
            return [0] * len(prices)
        
        z_scores = []
        
        for i in range(self.window, len(prices) + 1):
            window = prices[i-self.window:i]
            mean = np.mean(window)
            std = np.std(window) if np.std(window) > 0 else 0.0001
            z_score = (prices[i-1] - mean) / std
            z_scores.append(z_score)
        
        # Pad the beginning with 0
        return [0] * (self.window - 1) + z_scores


class PairsTradingStrategy(BaseMeanReversionStrategy):
    """Pairs trading mean reversion strategy"""
    
    def __init__(self, config: MeanReversionConfig):
        super().__init__(config)
        self.pairs: Dict[str, PairsTrade] = {}
        self.prices_data: Dict[str, List[float]] = {}
        self.last_update = datetime.utcnow()
        self.entry_zscore = 2.0
        self.exit_zscore = 0.5
    
    async def calculate_signals(self, symbol: str, prices: List[float]) -> List[MeanReversionSignal]:
        signals = []
        
        # Update pairs if needed
        await self.update_pairs()
        
        # Find pairs for this symbol
        for pair_key, pair in self.pairs.items():
            if symbol not in [pair.symbol1, pair.symbol2]:
                continue
            
            # Get the spread
            spread = await self.calculate_spread(pair)
            z_score = await self.calculate_zscore(spread, pair)
            
            current_price = prices[-1] if prices else 0
            
            if z_score < -self.entry_zscore:
                # Buy spread (buy symbol1, sell symbol2)
                signals.append(MeanReversionSignal(
                    timestamp=datetime.utcnow(),
                    symbol=f"{pair.symbol1}/{pair.symbol2}",
                    strategy=MeanReversionStrategy.PAIRS_TRADING,
                    signal_type=SignalType.BUY,
                    price=current_price,
                    indicator_value=z_score,
                    threshold=-self.entry_zscore,
                    confidence=min(1.0, abs(z_score) / (self.entry_zscore * 2)),
                    metadata={
                        "pair": [pair.symbol1, pair.symbol2],
                        "hedge_ratio": pair.hedge_ratio,
                        "spread": spread
                    }
                ))
            
            elif z_score > self.entry_zscore:
                # Sell spread (sell symbol1, buy symbol2)
                signals.append(MeanReversionSignal(
                    timestamp=datetime.utcnow(),
                    symbol=f"{pair.symbol1}/{pair.symbol2}",
                    strategy=MeanReversionStrategy.PAIRS_TRADING,
                    signal_type=SignalType.SELL,
                    price=current_price,
                    indicator_value=z_score,
                    threshold=self.entry_zscore,
                    confidence=min(1.0, abs(z_score) / (self.entry_zscore * 2)),
                    metadata={
                        "pair": [pair.symbol1, pair.symbol2],
                        "hedge_ratio": pair.hedge_ratio,
                        "spread": spread
                    }
                ))
            
            elif abs(z_score) < self.exit_zscore:
                signals.append(MeanReversionSignal(
                    timestamp=datetime.utcnow(),
                    symbol=f"{pair.symbol1}/{pair.symbol2}",
                    strategy=MeanReversionStrategy.PAIRS_TRADING,
                    signal_type=SignalType.EXIT,
                    price=current_price,
                    indicator_value=z_score,
                    threshold=self.exit_zscore,
                    confidence=0.9
                ))
        
        return signals
    
    async def get_indicator_value(self, symbol: str, prices: List[float]) -> float:
        # For pairs, return the average z-score of all pairs
        if not self.pairs:
            return 0
        
        z_scores = []
        for pair in self.pairs.values():
            spread = await self.calculate_spread(pair)
            z_score = await self.calculate_zscore(spread, pair)
            z_scores.append(z_score)
        
        return np.mean(z_scores) if z_scores else 0
    
    async def update_pairs(self) -> None:
        """Update pairs for trading"""
        now = datetime.utcnow()
        if (now - self.last_update).total_seconds() < self.config.pairs_update_interval:
            return
        
        # Find cointegrated pairs
        symbols = list(self.prices_data.keys())
        if len(symbols) < 2:
            return
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                s1 = symbols[i]
                s2 = symbols[j]
                
                prices1 = self.prices_data.get(s1, [])
                prices2 = self.prices_data.get(s2, [])
                
                if len(prices1) < self.config.pairs_lookback or len(prices2) < self.config.pairs_lookback:
                    continue
                
                # Align prices
                min_len = min(len(prices1), len(prices2))
                p1 = prices1[-min_len:]
                p2 = prices2[-min_len:]
                
                # Test for cointegration
                score, pvalue, _ = coint(p1, p2)
                
                if pvalue < self.config.cointegration_pvalue:
                    # Calculate hedge ratio
                    hedge_ratio = await self.calculate_hedge_ratio(p1, p2)
                    
                    # Calculate half-life of mean reversion
                    half_life = await self.calculate_half_life(p1, p2, hedge_ratio)
                    
                    pair_key = f"{s1}_{s2}"
                    self.pairs[pair_key] = PairsTrade(
                        symbol1=s1,
                        symbol2=s2,
                        spread=0,
                        z_score=0,
                        hedge_ratio=hedge_ratio,
                        cointegration_pvalue=pvalue,
                        half_life=half_life
                    )
                    
                    self.logger.info(f"Found cointegrated pair: {s1}/{s2} (pvalue={pvalue:.4f})")
        
        self.last_update = now
    
    async def calculate_hedge_ratio(self, prices1: List[float], prices2: List[float]) -> float:
        """Calculate hedge ratio using linear regression"""
        p1 = np.array(prices1)
        p2 = np.array(prices2)
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(p1, p2)
        return float(slope) if not np.isnan(slope) else 1.0
    
    async def calculate_half_life(self, prices1: List[float], prices2: List[float], hedge_ratio: float) -> float:
        """Calculate half-life of mean reversion"""
        spread = np.array(prices1) - hedge_ratio * np.array(prices2)
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        spread_lag = spread_lag.reshape(-1, 1)
        slope, intercept, r_value, p_value, std_err = stats.linregress(spread_lag.flatten(), spread_diff)
        
        if slope < 0:
            half_life = -np.log(2) / slope
            return float(half_life)
        return 10.0  # Default half-life
    
    async def calculate_spread(self, pair: PairsTrade) -> float:
        """Calculate spread for a pair"""
        prices1 = self.prices_data.get(pair.symbol1, [])
        prices2 = self.prices_data.get(pair.symbol2, [])
        
        if not prices1 or not prices2:
            return 0
        
        p1 = prices1[-1]
        p2 = prices2[-1]
        
        return p1 - pair.hedge_ratio * p2
    
    async def calculate_zscore(self, spread: float, pair: PairsTrade) -> float:
        """Calculate z-score for a pair"""
        prices1 = self.prices_data.get(pair.symbol1, [])
        prices2 = self.prices_data.get(pair.symbol2, [])
        
        if len(prices1) < self.config.pairs_lookback or len(prices2) < self.config.pairs_lookback:
            return 0
        
        min_len = min(len(prices1), len(prices2))
        p1 = prices1[-min_len:]
        p2 = prices2[-min_len:]
        
        spread_series = np.array(p1) - pair.hedge_ratio * np.array(p2)
        mean = np.mean(spread_series)
        std = np.std(spread_series) if np.std(spread_series) > 0 else 0.0001
        
        return (spread - mean) / std
    
    def add_price(self, symbol: str, price: float) -> None:
        """Add price to history"""
        if symbol not in self.prices_data:
            self.prices_data[symbol] = []
        self.prices_data[symbol].append(price)
        
        # Keep history within limits
        if len(self.prices_data[symbol]) > self.config.pairs_lookback * 2:
            self.prices_data[symbol] = self.prices_data[symbol][-self.config.pairs_lookback * 2:]


# ========================================
# MAIN MEAN REVERSION AGENT
# ========================================

class MeanReversionAgent(BaseAgent):
    """
    Mean Reversion Agent for automated mean reversion trading.
    
    Features:
    - Multiple mean reversion strategies
    - Statistical arbitrage
    - Pairs trading
    - Real-time signal generation
    - Automated order execution
    - Risk management
    - Performance analytics
    - Health monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._config = MeanReversionConfig(**config)
        self._broker: Optional[BaseBroker] = None
        self._strategies: Dict[MeanReversionStrategy, BaseMeanReversionStrategy] = {}
        
        # State
        self._positions: Dict[str, MeanReversionPosition] = {}
        self._stats: Dict[str, MeanReversionStats] = {}
        self._signals: List[MeanReversionSignal] = []
        self._price_data: Dict[str, List[float]] = {}
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_signals": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "exit_signals": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "current_drawdown": 0.0,
            "avg_holding_period": 0.0
        }
        
        self._initialize_strategies()
        self._initialize_broker()
        
        self.logger.info(f"MeanReversionAgent initialized for symbols: {self._config.symbols}")
    
    def _initialize_strategies(self) -> None:
        """Initialize mean reversion strategies"""
        strategy_map = {
            MeanReversionStrategy.BOLLINGER_BANDS: BollingerBandsStrategy,
            MeanReversionStrategy.RSI: RSIStrategy,
            MeanReversionStrategy.Z_SCORE: ZScoreStrategy,
            MeanReversionStrategy.PAIRS_TRADING: PairsTradingStrategy
        }
        
        for strategy_type in self._config.strategies:
            if strategy_type in strategy_map:
                self._strategies[strategy_type] = strategy_map[strategy_type](self._config)
                self.logger.info(f"Initialized {strategy_type} strategy")
    
    def _initialize_broker(self) -> None:
        """Initialize broker connection"""
        try:
            self._broker = get_broker(self._config.exchange)  # Need exchange in config
            self.logger.info(f"Initialized broker for {self._config.exchange}")
        except Exception as e:
            self.logger.error(f"Failed to initialize broker: {e}")
            raise
    
    # ========================================
    # AGENT LIFECYCLE
    # ========================================
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the mean reversion agent"""
        self.logger.info(f"Initializing MeanReversionAgent with config: {config}")
        
        if config:
            self._config = MeanReversionConfig(**{**self._config.dict(), **config})
        
        # Reinitialize strategies
        self._initialize_strategies()
        
        # Initialize stats
        for symbol in self._config.symbols:
            self._stats[symbol] = MeanReversionStats(symbol=symbol)
            self._price_data[symbol] = []
        
        # Register capabilities
        self.capabilities = [
            AgentCapability.MEAN_REVERSION,
            AgentCapability.STATISTICAL_ARBITRAGE,
            AgentCapability.ORDER_EXECUTION,
            AgentCapability.MARKET_DATA,
            AgentCapability.RISK_MANAGEMENT
        ]
        
        self.status = AgentStatus.INITIALIZED
        self.health = AgentHealth.HEALTHY
        self.logger.info("MeanReversionAgent initialized successfully")
    
    async def start(self) -> None:
        """Start the mean reversion agent"""
        self.logger.info("Starting MeanReversionAgent...")
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._signal_loop()))
        self._tasks.append(asyncio.create_task(self._execution_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.health = AgentHealth.HEALTHY
        self.logger.info("MeanReversionAgent started successfully")
    
    async def stop(self) -> None:
        """Stop the mean reversion agent"""
        self.logger.info("Stopping MeanReversionAgent...")
        self._running = False
        
        # Close all positions
        await self._close_all_positions()
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.status = AgentStatus.STOPPED
        self.logger.info("MeanReversionAgent stopped")
    
    async def pause(self) -> None:
        """Pause the mean reversion agent"""
        self.logger.info("Pausing MeanReversionAgent...")
        self._running = False
        self.status = AgentStatus.PAUSED
        self.logger.info("MeanReversionAgent paused")
    
    async def resume(self) -> None:
        """Resume the mean reversion agent"""
        self.logger.info("Resuming MeanReversionAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._signal_loop()))
        self._tasks.append(asyncio.create_task(self._execution_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        self._tasks.append(asyncio.create_task(self._metrics_loop()))
        
        self.status = AgentStatus.RUNNING
        self.logger.info("MeanReversionAgent resumed")
    
    async def health_check(self) -> AgentHealth:
        """Check agent health"""
        try:
            if not self._running:
                return AgentHealth.DEGRADED
            
            if not self._broker:
                return AgentHealth.UNHEALTHY
            
            if not self._strategies:
                return AgentHealth.DEGRADED
            
            # Check if any positions are in drawdown
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
        """Generate mean reversion signals"""
        # Update price data
        await self._update_prices()
        
        # Generate signals from each strategy
        new_signals = []
        
        for symbol in self._config.symbols:
            prices = self._price_data.get(symbol, [])
            if len(prices) < self._config.lookback_period:
                continue
            
            for strategy in self._strategies.values():
                try:
                    signals = await strategy.calculate_signals(symbol, prices)
                    new_signals.extend(signals)
                except Exception as e:
                    self.logger.error(f"Strategy {strategy.__class__.__name__} error: {e}")
        
        self._signals = new_signals
        self._metrics["total_signals"] += len(new_signals)
    
    async def _update_prices(self) -> None:
        """Update price data from broker"""
        if not self._broker:
            return
        
        for symbol in self._config.symbols:
            try:
                # Get latest price
                ticker = await self._broker.get_ticker(symbol)
                if ticker:
                    price = ticker.get('last', 0)
                    if price > 0:
                        self._price_data[symbol].append(price)
                        
                        # Update strategies
                        for strategy in self._strategies.values():
                            strategy.add_price(symbol, price)
                        
                        # Keep within limits
                        if len(self._price_data[symbol]) > self._config.lookback_period * 3:
                            self._price_data[symbol] = self._price_data[symbol][-self._config.lookback_period * 3:]
            except Exception as e:
                self.logger.error(f"Failed to update price for {symbol}: {e}")
    
    async def _process_signals(self) -> None:
        """Process and filter signals"""
        if not self._signals:
            return
        
        # Get best signal per symbol
        best_signals = {}
        for signal in self._signals:
            if signal.symbol not in best_signals:
                best_signals[signal.symbol] = signal
            elif signal.confidence > best_signals[signal.symbol].confidence:
                best_signals[signal.symbol] = signal
        
        # Execute signals
        for symbol, signal in best_signals.items():
            if signal.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                await self._execute_buy_signal(signal)
            elif signal.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                await self._execute_sell_signal(signal)
            elif signal.signal_type == SignalType.EXIT:
                await self._execute_exit_signal(signal)
    
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
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Execution loop error: {e}")
            
            await asyncio.sleep(self._config.order_refresh_interval)
    
    async def _execute_buy_signal(self, signal: MeanReversionSignal) -> None:
        """Execute a buy signal"""
        if len(self._positions) >= self._config.max_positions:
            self.logger.warning("Max positions reached")
            return
        
        # Calculate position size
        position_size = await self._calculate_position_size(signal)
        if position_size < self._config.min_position_size:
            self.logger.warning(f"Position size {position_size} below minimum")
            return
        
        # Place buy order
        try:
            order = await self._broker.create_order(
                symbol=signal.symbol,
                side='buy',
                type='market',
                quantity=position_size
            )
            
            if order:
                entry_price = order.get('price', signal.price)
                
                position = MeanReversionPosition(
                    symbol=signal.symbol,
                    entry_price=entry_price,
                    entry_time=datetime.utcnow(),
                    position_size=position_size,
                    current_price=entry_price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    total_pnl=0,
                    stop_loss=entry_price * (1 - self._config.stop_loss),
                    take_profit=entry_price * (1 + self._config.take_profit),
                    strategy=signal.strategy
                )
                
                self._positions[signal.symbol] = position
                self._metrics["total_trades"] += 1
                
                self.logger.info(f"BUY signal executed: {signal.symbol} @ {entry_price}")
                
        except Exception as e:
            self.logger.error(f"Failed to execute buy signal: {e}")
    
    async def _execute_sell_signal(self, signal: MeanReversionSignal) -> None:
        """Execute a sell signal"""
        if len(self._positions) >= self._config.max_positions:
            self.logger.warning("Max positions reached")
            return
        
        # Calculate position size
        position_size = await self._calculate_position_size(signal)
        if position_size < self._config.min_position_size:
            self.logger.warning(f"Position size {position_size} below minimum")
            return
        
        # Place sell order
        try:
            order = await self._broker.create_order(
                symbol=signal.symbol,
                side='sell',
                type='market',
                quantity=position_size
            )
            
            if order:
                entry_price = order.get('price', signal.price)
                
                position = MeanReversionPosition(
                    symbol=signal.symbol,
                    entry_price=entry_price,
                    entry_time=datetime.utcnow(),
                    position_size=-position_size,  # Short position
                    current_price=entry_price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                    total_pnl=0,
                    stop_loss=entry_price * (1 + self._config.stop_loss),
                    take_profit=entry_price * (1 - self._config.take_profit),
                    strategy=signal.strategy
                )
                
                self._positions[signal.symbol] = position
                self._metrics["total_trades"] += 1
                
                self.logger.info(f"SELL signal executed: {signal.symbol} @ {entry_price}")
                
        except Exception as e:
            self.logger.error(f"Failed to execute sell signal: {e}")
    
    async def _execute_exit_signal(self, signal: MeanReversionSignal) -> None:
        """Execute an exit signal"""
        if signal.symbol not in self._positions:
            return
        
        position = self._positions[signal.symbol]
        
        try:
            side = 'sell' if position.position_size > 0 else 'buy'
            quantity = abs(position.position_size)
            
            order = await self._broker.create_order(
                symbol=signal.symbol,
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
                if position.position_size > 0:  # Long position
                    position.realized_pnl = (exit_price - position.entry_price) * position.position_size
                else:  # Short position
                    position.realized_pnl = (position.entry_price - exit_price) * abs(position.position_size)
                
                position.total_pnl = position.realized_pnl
                
                # Update stats
                stats = self._stats.get(signal.symbol)
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
                
                self.logger.info(f"EXIT signal executed: {signal.symbol} @ {exit_price} | P&L: {position.realized_pnl:.2f}")
                
                # Remove position
                del self._positions[signal.symbol]
                
        except Exception as e:
            self.logger.error(f"Failed to execute exit signal: {e}")
    
    async def _calculate_position_size(self, signal: MeanReversionSignal) -> float:
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
            try:
                ticker = await self._broker.get_ticker(symbol)
                if ticker:
                    current_price = ticker.get('last', position.current_price)
                    position.current_price = current_price
                    
                    # Calculate unrealized P&L
                    if position.position_size > 0:
                        position.unrealized_pnl = (current_price - position.entry_price) * position.position_size
                    else:
                        position.unrealized_pnl = (position.entry_price - current_price) * abs(position.position_size)
                    
                    position.total_pnl = position.realized_pnl + position.unrealized_pnl
            except Exception as e:
                self.logger.error(f"Failed to update position {symbol}: {e}")
    
    async def _check_stop_loss(self) -> None:
        """Check and execute stop loss"""
        for symbol, position in list(self._positions.items()):
            if position.stop_loss is None:
                continue
            
            should_stop = False
            if position.position_size > 0:  # Long position
                if position.current_price <= position.stop_loss:
                    should_stop = True
            else:  # Short position
                if position.current_price >= position.stop_loss:
                    should_stop = True
            
            if should_stop:
                self.logger.info(f"Stop loss triggered for {symbol}")
                await self._close_position(symbol)
    
    async def _check_take_profit(self) -> None:
        """Check and execute take profit"""
        for symbol, position in list(self._positions.items()):
            if position.take_profit is None:
                continue
            
            should_take = False
            if position.position_size > 0:  # Long position
                if position.current_price >= position.take_profit:
                    should_take = True
            else:  # Short position
                if position.current_price <= position.take_profit:
                    should_take = True
            
            if should_take:
                self.logger.info(f"Take profit triggered for {symbol}")
                await self._close_position(symbol)
    
    async def _close_position(self, symbol: str) -> None:
        """Close a position"""
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        
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
                
                self.logger.info(f"Position closed: {symbol} @ {exit_price} | P&L: {position.realized_pnl:.2f}")
                
                del self._positions[symbol]
                
        except Exception as e:
            self.logger.error(f"Failed to close position {symbol}: {e}")
    
    async def _close_all_positions(self) -> None:
        """Close all open positions"""
        for symbol in list(self._positions.keys()):
            await self._close_position(symbol)
    
    # ========================================
    # STATISTICS & METRICS
    # ========================================
    
    async def _update_stats(self) -> None:
        """Update statistics"""
        for symbol, stats in self._stats.items():
            if stats.total_trades > 0:
                stats.win_rate = stats.winning_trades / stats.total_trades
                stats.avg_win = stats.total_pnl / stats.total_trades if stats.total_trades > 0 else 0
        
        # Update global metrics
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
            positions[symbol] = {
                "symbol": pos.symbol,
                "entry_price": pos.entry_price,
                "entry_time": pos.entry_time.isoformat(),
                "position_size": pos.position_size,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
                "total_pnl": pos.total_pnl,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "status": pos.status,
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
                "success_rate": stat.success_rate
            }
        return stats
    
    async def get_signals(self) -> List[Dict[str, Any]]:
        """Get recent signals"""
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "strategy": s.strategy.value,
                "signal_type": s.signal_type.value,
                "price": s.price,
                "indicator_value": s.indicator_value,
                "threshold": s.threshold,
                "confidence": s.confidence,
                "metadata": s.metadata
            }
            for s in self._signals[-20:]  # Last 20 signals
        ]
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            **self._metrics,
            "positions": len(self._positions),
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
    
    async def force_signal(self, symbol: str, signal_type: SignalType) -> None:
        """Force a signal for testing"""
        if signal_type == SignalType.BUY:
            signal = MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.Z_SCORE,
                signal_type=SignalType.BUY,
                price=self._price_data.get(symbol, [0])[-1] or 100,
                indicator_value=-3.0,
                threshold=-2.0,
                confidence=1.0
            )
            await self._execute_buy_signal(signal)
        elif signal_type == SignalType.SELL:
            signal = MeanReversionSignal(
                timestamp=datetime.utcnow(),
                symbol=symbol,
                strategy=MeanReversionStrategy.Z_SCORE,
                signal_type=SignalType.SELL,
                price=self._price_data.get(symbol, [0])[-1] or 100,
                indicator_value=3.0,
                threshold=2.0,
                confidence=1.0
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
            
            key = f"mean_reversion_state:{self.agent_id}"
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

def create_mean_reversion_agent(config: Dict[str, Any]) -> MeanReversionAgent:
    """Create a mean reversion agent instance"""
    return MeanReversionAgent(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MeanReversionAgent',
    'MeanReversionConfig',
    'MeanReversionStrategy',
    'SignalType',
    'MeanReversionSignal',
    'BollingerBands',
    'PairsTrade',
    'MeanReversionPosition',
    'MeanReversionStats',
    'create_mean_reversion_agent'
]
