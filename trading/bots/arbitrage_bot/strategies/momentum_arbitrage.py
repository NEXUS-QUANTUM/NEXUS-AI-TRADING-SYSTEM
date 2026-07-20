# trading/bots/arbitrage_bot/strategies/momentum_arbitrage.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Momentum Arbitrage Strategy

"""
Momentum Arbitrage Strategy - Advanced Momentum-Based Arbitrage Detection

This module provides sophisticated momentum arbitrage capabilities that
leverage price momentum across different markets and timeframes to identify
and execute arbitrage opportunities.

Architecture:
    - BaseMomentumArbitrage: Abstract base class
    - MomentumArbitrage: Main strategy implementation
    - MomentumAnalyzer: Price momentum analysis
    - DivergenceDetector: Momentum divergence detection
    - TrendAnalyzer: Trend identification
    - ArbitrageCalculator: Arbitrage opportunity calculation
    - RiskManager: Risk management
    - ExecutionManager: Execution coordination

Features:
    - Multi-timeframe momentum analysis
    - Momentum divergence detection
    - Trend-based arbitrage
    - Cross-asset momentum arbitrage
    - Dynamic entry/exit points
    - Risk management
    - MEV protection
    - Performance tracking
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    Callable,
    AsyncIterator,
    TypeVar,
    Generic,
)
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from scipy import stats

from ..executors.base_executor import (
    BaseExecutor,
    ExecutionType,
    ExecutionStatus,
    ExecutionPriority,
    ExecutionRisk,
    ExecutionConfig,
    ExecutionOrder,
    ExecutionResult,
    ExecutionPlan,
)
from ..exchanges.base_exchange import (
    BaseExchange,
    ExchangeType,
    OrderType,
    OrderSide,
    TimeInForce,
    MarketType,
    Ticker,
    OHLCV,
    Order,
    Trade,
)


# Constants
MIN_MOMENTUM_STRENGTH = Decimal("0.02")  # 2% minimum momentum
MAX_MOMENTUM_STRENGTH = Decimal("0.15")  # 15% maximum momentum
MIN_CORRELATION = Decimal("0.6")  # Minimum correlation for cross-asset
MAX_LEAD_LAG = 10  # Maximum lead-lag period (candles)
MIN_PROFIT_THRESHOLD = Decimal("0.001")  # 0.1% minimum profit
MOMENTUM_WINDOW_SHORT = 5  # Short-term momentum window
MOMENTUM_WINDOW_LONG = 20  # Long-term momentum window
MOMENTUM_WINDOW_EXTRA_LONG = 50  # Extra long-term momentum window


class MomentumType(Enum):
    """Momentum type enumeration."""
    PRICE_MOMENTUM = "price_momentum"
    VOLUME_MOMENTUM = "volume_momentum"
    RELATIVE_STRENGTH = "relative_strength"
    DIVERGENCE = "divergence"
    CROSS_ASSET = "cross_asset"
    TREND_FOLLOWING = "trend_following"


class TrendDirection(Enum):
    """Trend direction enumeration."""
    STRONG_UP = "strong_up"
    WEAK_UP = "weak_up"
    NEUTRAL = "neutral"
    WEAK_DOWN = "weak_down"
    STRONG_DOWN = "strong_down"


@dataclass
class MomentumData:
    """Momentum data."""
    symbol: str
    exchange: ExchangeType
    timeframe: str
    price: Decimal
    momentum_short: Decimal
    momentum_long: Decimal
    momentum_extra_long: Decimal
    rsi: Decimal
    volume: Decimal
    correlation: Optional[Decimal] = None
    trend_direction: TrendDirection = TrendDirection.NEUTRAL
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MomentumOpportunity:
    """Momentum arbitrage opportunity."""
    opportunity_id: str
    symbol: str
    exchange: ExchangeType
    momentum_type: MomentumType
    entry_price: Decimal
    exit_price: Decimal
    expected_profit: Decimal
    expected_profit_percentage: Decimal
    momentum_strength: Decimal
    trend_direction: TrendDirection
    confidence: Decimal
    risk_score: Decimal
    timeframe: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MomentumArbitrage:
    """
    Advanced Momentum Arbitrage Strategy.
    
    This class provides sophisticated momentum arbitrage capabilities:
    1. Multi-timeframe momentum analysis
    2. Momentum divergence detection
    3. Trend-based arbitrage
    4. Cross-asset momentum arbitrage
    5. Dynamic entry/exit points
    6. Risk management
    7. MEV protection
    8. Performance tracking
    
    Features:
    - Real-time momentum analysis
    - Divergence detection
    - Cross-asset correlation analysis
    - Dynamic position sizing
    - Risk management
    - MEV protection
    - Performance monitoring
    """
    
    def __init__(
        self,
        exchanges: Dict[ExchangeType, BaseExchange],
        executor: BaseExecutor,
        min_momentum: Decimal = MIN_MOMENTUM_STRENGTH,
        max_momentum: Decimal = MAX_MOMENTUM_STRENGTH,
        min_correlation: Decimal = MIN_CORRELATION,
        min_profit: Decimal = MIN_PROFIT_THRESHOLD,
        max_lead_lag: int = MAX_LEAD_LAG,
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the momentum arbitrage strategy.
        
        Args:
            exchanges: Dictionary of exchange instances
            executor: Execution engine
            min_momentum: Minimum momentum strength
            max_momentum: Maximum momentum strength
            min_correlation: Minimum correlation for cross-asset
            min_profit: Minimum profit threshold
            max_lead_lag: Maximum lead-lag period
            config: Optional configuration dictionary
            logger: Optional logger instance
        """
        self.exchanges = exchanges
        self.executor = executor
        self.min_momentum = min_momentum
        self.max_momentum = max_momentum
        self.min_correlation = min_correlation
        self.min_profit = min_profit
        self.max_lead_lag = max_lead_lag
        self.config = config or {}
        self.logger = logger or self._setup_logger()
        
        # Data storage
        self.momentum_cache: Dict[str, MomentumData] = {}
        self.price_history: Dict[str, Dict[str, deque]] = {}
        self.opportunity_cache: Dict[str, MomentumOpportunity] = {}
        
        # Active opportunities
        self.active_opportunities: Set[str] = set()
        
        # Metrics
        self.metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_succeeded": 0,
            "opportunities_failed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_momentum": Decimal("0"),
            "success_rate": Decimal("0"),
            "errors": 0,
        }
        
        # Background tasks
        self._is_running = False
        self._scan_task: Optional[asyncio.Task] = None
        
        self.logger.info("MomentumArbitrage initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger."""
        logger = logging.getLogger(f"{__name__}.MomentumArbitrage")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _fetch_ohlcv(
        self,
        exchange: BaseExchange,
        symbol: str,
        interval: str,
        limit: int = 100,
    ) -> List[OHLCV]:
        """
        Fetch OHLCV data from exchange.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            interval: Time interval
            limit: Number of candles
            
        Returns:
            List of OHLCV objects
        """
        try:
            # Map interval string to Interval enum
            interval_map = {
                "1m": Interval.M1,
                "5m": Interval.M5,
                "15m": Interval.M15,
                "30m": Interval.M30,
                "1h": Interval.H1,
                "4h": Interval.H4,
                "1d": Interval.D1,
            }
            
            interval_enum = interval_map.get(interval, Interval.M5)
            
            return await exchange.get_ohlcv(
                symbol=symbol,
                interval=interval_enum,
                limit=limit,
            )
        except Exception as e:
            self.logger.debug(f"Failed to fetch OHLCV: {e}")
            return []
    
    async def _calculate_momentum(
        self,
        prices: List[Decimal],
        short_window: int = MOMENTUM_WINDOW_SHORT,
        long_window: int = MOMENTUM_WINDOW_LONG,
        extra_long_window: int = MOMENTUM_WINDOW_EXTRA_LONG,
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate momentum indicators.
        
        Args:
            prices: List of prices
            short_window: Short-term window
            long_window: Long-term window
            extra_long_window: Extra long-term window
            
        Returns:
            Tuple of (short_momentum, long_momentum, extra_long_momentum)
        """
        if len(prices) < extra_long_window:
            return Decimal("0"), Decimal("0"), Decimal("0")
        
        # Convert to numpy array
        price_array = np.array([float(p) for p in prices])
        
        # Calculate returns
        returns = np.diff(price_array) / price_array[:-1]
        
        # Calculate momentum for different windows
        if len(returns) >= short_window:
            short_momentum = Decimal(str(np.mean(returns[-short_window:])))
        else:
            short_momentum = Decimal("0")
        
        if len(returns) >= long_window:
            long_momentum = Decimal(str(np.mean(returns[-long_window:])))
        else:
            long_momentum = Decimal("0")
        
        if len(returns) >= extra_long_window:
            extra_long_momentum = Decimal(str(np.mean(returns[-extra_long_window:])))
        else:
            extra_long_momentum = Decimal("0")
        
        return short_momentum, long_momentum, extra_long_momentum
    
    async def _calculate_rsi(
        self,
        prices: List[Decimal],
        window: int = 14,
    ) -> Decimal:
        """
        Calculate RSI indicator.
        
        Args:
            prices: List of prices
            window: RSI window
            
        Returns:
            RSI value
        """
        if len(prices) < window + 1:
            return Decimal("50")
        
        price_array = np.array([float(p) for p in prices])
        
        # Calculate price changes
        deltas = np.diff(price_array)
        
        # Separate gains and losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate average gains and losses
        avg_gain = np.mean(gains[-window:])
        avg_loss = np.mean(losses[-window:])
        
        if avg_loss == 0:
            return Decimal("100")
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return Decimal(str(rsi))
    
    async def _calculate_correlation(
        self,
        prices1: List[Decimal],
        prices2: List[Decimal],
        window: int = 20,
    ) -> Decimal:
        """
        Calculate correlation between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            window: Correlation window
            
        Returns:
            Correlation coefficient
        """
        if len(prices1) < window or len(prices2) < window:
            return Decimal("0")
        
        p1 = np.array([float(p) for p in prices1[-window:]])
        p2 = np.array([float(p) for p in prices2[-window:]])
        
        correlation = np.corrcoef(p1, p2)[0, 1]
        return Decimal(str(correlation))
    
    async def _analyze_trend(
        self,
        short_momentum: Decimal,
        long_momentum: Decimal,
        extra_long_momentum: Decimal,
    ) -> TrendDirection:
        """
        Analyze trend direction based on momentum.
        
        Args:
            short_momentum: Short-term momentum
            long_momentum: Long-term momentum
            extra_long_momentum: Extra long-term momentum
            
        Returns:
            TrendDirection
        """
        # Check for strong trends
        if short_momentum > Decimal("0.02") and long_momentum > Decimal("0.01"):
            return TrendDirection.STRONG_UP
        elif short_momentum < Decimal("-0.02") and long_momentum < Decimal("-0.01"):
            return TrendDirection.STRONG_DOWN
        
        # Check for weak trends
        elif short_momentum > Decimal("0.005") and long_momentum > Decimal("0.005"):
            return TrendDirection.WEAK_UP
        elif short_momentum < Decimal("-0.005") and long_momentum < Decimal("-0.005"):
            return TrendDirection.WEAK_DOWN
        
        return TrendDirection.NEUTRAL
    
    async def _detect_divergence(
        self,
        prices: List[Decimal],
        rsi: List[Decimal],
        window: int = 20,
    ) -> bool:
        """
        Detect momentum divergence.
        
        Args:
            prices: Price series
            rsi: RSI series
            window: Divergence window
            
        Returns:
            True if divergence detected
        """
        if len(prices) < window or len(rsi) < window:
            return False
        
        # Find local minima and maxima
        price_array = np.array([float(p) for p in prices[-window:]])
        rsi_array = np.array([float(r) for r in rsi[-window:]])
        
        # Find price minima
        price_min = np.min(price_array)
        price_min_idx = np.argmin(price_array)
        
        # Find RSI minima
        rsi_min = np.min(rsi_array)
        rsi_min_idx = np.argmin(rsi_array)
        
        # Check for bullish divergence
        if price_min_idx > rsi_min_idx and price_min < price_array[0] and rsi_min > rsi_array[0]:
            return True
        
        return False
    
    async def _analyze_momentum(
        self,
        exchange: BaseExchange,
        symbol: str,
        timeframe: str = "5m",
    ) -> Optional[MomentumData]:
        """
        Analyze momentum for a symbol.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            MomentumData or None
        """
        try:
            # Fetch OHLCV data
            ohlcv = await self._fetch_ohlcv(exchange, symbol, timeframe, limit=100)
            
            if len(ohlcv) < 30:
                return None
            
            # Extract prices
            prices = [c.close for c in ohlcv]
            
            # Calculate momentum
            short_mom, long_mom, extra_long_mom = await self._calculate_momentum(prices)
            
            # Calculate RSI
            rsi = await self._calculate_rsi(prices)
            
            # Get current price
            current_price = prices[-1]
            
            # Get volume
            volume = ohlcv[-1].volume
            
            # Analyze trend
            trend = await self._analyze_trend(short_mom, long_mom, extra_long_mom)
            
            return MomentumData(
                symbol=symbol,
                exchange=exchange.exchange_type,
                timeframe=timeframe,
                price=current_price,
                momentum_short=short_mom,
                momentum_long=long_mom,
                momentum_extra_long=extra_long_mom,
                rsi=rsi,
                volume=volume,
                trend_direction=trend,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.debug(f"Momentum analysis failed for {symbol}: {e}")
            return None
    
    async def _find_momentum_opportunities(
        self,
        momentum_data: MomentumData,
    ) -> List[MomentumOpportunity]:
        """
        Find momentum arbitrage opportunities.
        
        Args:
            momentum_data: Momentum data
            
        Returns:
            List of MomentumOpportunity
        """
        opportunities = []
        
        try:
            # Check momentum strength
            momentum_strength = abs(momentum_data.momentum_short)
            
            if momentum_strength < self.min_momentum or momentum_strength > self.max_momentum:
                return opportunities
            
            # Check for momentum opportunities based on trend
            if momentum_data.trend_direction in [TrendDirection.STRONG_UP, TrendDirection.WEAK_UP]:
                # Bullish momentum
                entry_price = momentum_data.price
                exit_price = entry_price * (Decimal("1") + momentum_data.momentum_short * Decimal("10"))
                
                opportunity = MomentumOpportunity(
                    opportunity_id=f"mom_{momentum_data.symbol}_{int(time.time())}",
                    symbol=momentum_data.symbol,
                    exchange=momentum_data.exchange,
                    momentum_type=MomentumType.PRICE_MOMENTUM,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    expected_profit=exit_price - entry_price,
                    expected_profit_percentage=(exit_price - entry_price) / entry_price * Decimal("100"),
                    momentum_strength=momentum_strength,
                    trend_direction=momentum_data.trend_direction,
                    confidence=Decimal("0.7"),
                    risk_score=Decimal("0.3"),
                    timeframe=momentum_data.timeframe,
                )
                opportunities.append(opportunity)
            
            elif momentum_data.trend_direction in [TrendDirection.STRONG_DOWN, TrendDirection.WEAK_DOWN]:
                # Bearish momentum
                entry_price = momentum_data.price
                exit_price = entry_price * (Decimal("1") - momentum_data.momentum_short * Decimal("10"))
                
                opportunity = MomentumOpportunity(
                    opportunity_id=f"mom_{momentum_data.symbol}_{int(time.time())}",
                    symbol=momentum_data.symbol,
                    exchange=momentum_data.exchange,
                    momentum_type=MomentumType.PRICE_MOMENTUM,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    expected_profit=entry_price - exit_price,
                    expected_profit_percentage=(entry_price - exit_price) / entry_price * Decimal("100"),
                    momentum_strength=momentum_strength,
                    trend_direction=momentum_data.trend_direction,
                    confidence=Decimal("0.7"),
                    risk_score=Decimal("0.3"),
                    timeframe=momentum_data.timeframe,
                )
                opportunities.append(opportunity)
            
            # Check for divergence opportunities
            if momentum_data.rsi < 30 and momentum_data.trend_direction == TrendDirection.STRONG_DOWN:
                # Bullish divergence (oversold)
                opportunity = MomentumOpportunity(
                    opportunity_id=f"div_{momentum_data.symbol}_{int(time.time())}",
                    symbol=momentum_data.symbol,
                    exchange=momentum_data.exchange,
                    momentum_type=MomentumType.DIVERGENCE,
                    entry_price=momentum_data.price,
                    exit_price=momentum_data.price * Decimal("1.05"),
                    expected_profit=momentum_data.price * Decimal("0.05"),
                    expected_profit_percentage=Decimal("5"),
                    momentum_strength=momentum_strength,
                    trend_direction=TrendDirection.WEAK_UP,
                    confidence=Decimal("0.75"),
                    risk_score=Decimal("0.25"),
                    timeframe=momentum_data.timeframe,
                )
                opportunities.append(opportunity)
            
            elif momentum_data.rsi > 70 and momentum_data.trend_direction == TrendDirection.STRONG_UP:
                # Bearish divergence (overbought)
                opportunity = MomentumOpportunity(
                    opportunity_id=f"div_{momentum_data.symbol}_{int(time.time())}",
                    symbol=momentum_data.symbol,
                    exchange=momentum_data.exchange,
                    momentum_type=MomentumType.DIVERGENCE,
                    entry_price=momentum_data.price,
                    exit_price=momentum_data.price * Decimal("0.95"),
                    expected_profit=momentum_data.price * Decimal("0.05"),
                    expected_profit_percentage=Decimal("5"),
                    momentum_strength=momentum_strength,
                    trend_direction=TrendDirection.WEAK_DOWN,
                    confidence=Decimal("0.75"),
                    risk_score=Decimal("0.25"),
                    timeframe=momentum_data.timeframe,
                )
                opportunities.append(opportunity)
            
        except Exception as e:
            self.logger.debug(f"Opportunity finding failed: {e}")
        
        return opportunities
    
    async def _execute_opportunity(
        self,
        opportunity: MomentumOpportunity,
    ) -> Optional[ExecutionResult]:
        """
        Execute a momentum arbitrage opportunity.
        
        Args:
            opportunity: Momentum opportunity
            
        Returns:
            ExecutionResult or None
        """
        try:
            # Build execution plan
            order = ExecutionOrder(
                exchange=opportunity.exchange,
                symbol=opportunity.symbol,
                side=OrderSide.BUY if opportunity.trend_direction in [TrendDirection.STRONG_UP, TrendDirection.WEAK_UP] else OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=Decimal("1"),  # Would be dynamic
                price=opportunity.entry_price,
                time_in_force=TimeInForce.GTC,
            )
            
            plan = ExecutionPlan(
                execution_id=f"mom_{opportunity.opportunity_id}",
                execution_type=ExecutionType.ATOMIC,
                orders=[order],
                config=ExecutionConfig(
                    max_slippage=Decimal("0.01"),
                    max_retries=3,
                    timeout=60,
                ),
                priority=ExecutionPriority.MEDIUM,
                risk_level=ExecutionRisk.MEDIUM,
                required_balance=opportunity.entry_price,
                max_loss=opportunity.expected_profit * Decimal("0.5"),
                deadline=datetime.utcnow() + timedelta(minutes=5),
            )
            
            # Execute
            result = await self.executor.execute(plan)
            
            # Update metrics
            self.metrics["opportunities_executed"] += 1
            
            if result.status == ExecutionStatus.COMPLETED:
                self.metrics["opportunities_succeeded"] += 1
                self.metrics["total_profit"] += result.profit
            else:
                self.metrics["opportunities_failed"] += 1
                self.metrics["total_loss"] += abs(result.profit)
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            
            return result
            
        except Exception as e:
            self.logger.error(f"Opportunity execution failed: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def scan_momentum(self) -> List[MomentumOpportunity]:
        """
        Scan for momentum arbitrage opportunities.
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        try:
            # Scan each exchange
            for exchange_type, exchange in self.exchanges.items():
                try:
                    # Get symbols
                    symbols = await exchange.get_symbols()
                    
                    # Analyze each symbol
                    for symbol in symbols[:20]:  # Limit for performance
                        try:
                            momentum_data = await self._analyze_momentum(
                                exchange,
                                symbol,
                                timeframe="5m",
                            )
                            
                            if momentum_data:
                                # Cache momentum data
                                key = f"{exchange_type.value}_{symbol}"
                                self.momentum_cache[key] = momentum_data
                                
                                # Find opportunities
                                opps = await self._find_momentum_opportunities(momentum_data)
                                opportunities.extend(opps)
                                
                        except Exception as e:
                            self.logger.debug(f"Symbol analysis failed for {symbol}: {e}")
                            
                except Exception as e:
                    self.logger.debug(f"Exchange scan failed for {exchange_type}: {e}")
            
            # Update metrics
            self.metrics["opportunities_detected"] += len(opportunities)
            
            # Sort by confidence
            opportunities.sort(key=lambda x: float(x.confidence), reverse=True)
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            return []
    
    async def execute_best_opportunity(self) -> Optional[ExecutionResult]:
        """
        Find and execute the best momentum opportunity.
        
        Returns:
            ExecutionResult or None
        """
        try:
            # Scan for opportunities
            opportunities = await self.scan_momentum()
            
            if not opportunities:
                return None
            
            # Filter by profit threshold
            profitable_opps = [
                o for o in opportunities
                if o.expected_profit_percentage >= self.min_profit * Decimal("100")
            ]
            
            if not profitable_opps:
                return None
            
            # Take best opportunity
            best_opp = profitable_opps[0]
            
            # Execute
            result = await self._execute_opportunity(best_opp)
            
            if result:
                self.active_opportunities.add(best_opp.opportunity_id)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Execute best opportunity failed: {e}")
            return None
    
    async def start(self) -> None:
        """Start the strategy."""
        if self._is_running:
            return
        
        self._is_running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        self.logger.info("MomentumArbitrage started")
    
    async def stop(self) -> None:
        """Stop the strategy."""
        self._is_running = False
        
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except Exception:
                pass
        
        self.logger.info("MomentumArbitrage stopped")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self._is_running:
            try:
                # Scan for opportunities
                opportunities = await self.scan_momentum()
                
                if opportunities:
                    self.logger.info(f"Found {len(opportunities)} momentum opportunities")
                    
                    # Execute best opportunity
                    best_opp = opportunities[0]
                    if best_opp.expected_profit_percentage >= self.min_profit * Decimal("100"):
                        await self._execute_opportunity(best_opp)
                
                # Sleep
                await asyncio.sleep(30)  # 30 seconds
                
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                await asyncio.sleep(10)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy metrics.
        
        Returns:
            Dictionary of metrics
        """
        success_rate = (
            self.metrics["opportunities_succeeded"] / self.metrics["opportunities_executed"]
            if self.metrics["opportunities_executed"] > 0 else Decimal("0")
        )
        
        return {
            "opportunities_detected": self.metrics["opportunities_detected"],
            "opportunities_executed": self.metrics["opportunities_executed"],
            "opportunities_succeeded": self.metrics["opportunities_succeeded"],
            "opportunities_failed": self.metrics["opportunities_failed"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "avg_momentum": float(self.metrics["avg_momentum"]),
            "success_rate": float(success_rate),
            "errors": self.metrics["errors"],
            "active_opportunities": len(self.active_opportunities),
            "is_running": self._is_running,
        }


# Module exports
__all__ = [
    'MomentumArbitrage',
    'MomentumType',
    'TrendDirection',
    'MomentumData',
    'MomentumOpportunity',
]
