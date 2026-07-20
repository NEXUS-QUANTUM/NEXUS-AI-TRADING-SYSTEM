# trading/bots/arbitrage_bot/strategies/statistical_strategy.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Statistical Arbitrage Strategy

"""
Statistical Arbitrage Strategy - Advanced Statistical Arbitrage Detection

This module provides sophisticated statistical arbitrage capabilities using
advanced statistical methods including cointegration, correlation analysis,
and machine learning techniques to identify and exploit mean-reverting
relationships between assets.

Architecture:
    - BaseStatisticalStrategy: Abstract base class
    - StatisticalStrategy: Main strategy implementation
    - CointegrationAnalyzer: Cointegration testing
    - CorrelationAnalyzer: Correlation analysis
    - MeanReversionDetector: Mean reversion detection
    - SpreadModeler: Spread modeling
    - KalmanFilter: Dynamic state estimation
    - RiskManager: Risk management
    - PositionManager: Position management

Features:
    - Cointegration-based pairs selection
    - Dynamic spread modeling
    - Kalman filter for hedge ratio estimation
    - Mean reversion detection
    - Multi-asset statistical arbitrage
    - Risk management
    - Position sizing
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
from scipy import stats
from scipy.optimize import minimize
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.regression.linear_model import OLS
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler

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
MIN_COINTEGRATION_PVALUE = Decimal("0.05")
MIN_CORRELATION = Decimal("0.7")
MAX_CORRELATION = Decimal("0.95")
ZSCORE_ENTRY_THRESHOLD = Decimal("2.0")
ZSCORE_EXIT_THRESHOLD = Decimal("0.5")
MIN_SPREAD_STD = Decimal("0.01")
MAX_SPREAD_STD = Decimal("0.5")
MAX_PAIRS = 50
MIN_PRICE_HISTORY = 30
REBALANCE_INTERVAL = 60  # seconds
KALMAN_UPDATE_INTERVAL = 5  # seconds


class StatisticalMethod(Enum):
    """Statistical method enumeration."""
    COINTEGRATION = "cointegration"
    CORRELATION = "correlation"
    PCA = "pca"
    KALMAN = "kalman"
    ML = "ml"
    ENSEMBLE = "ensemble"


@dataclass
class StatisticalPair:
    """Statistical arbitrage pair data."""
    symbol1: str
    symbol2: str
    exchange1: ExchangeType
    exchange2: ExchangeType
    correlation: Decimal
    cointegration_pvalue: Decimal
    hedge_ratio: Decimal
    intercept: Decimal
    spread_mean: Decimal
    spread_std: Decimal
    half_life: Decimal
    current_spread: Decimal
    current_zscore: Decimal
    status: str  # "normal", "entry_long", "entry_short", "exit"
    confidence: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StatisticalPosition:
    """Statistical arbitrage position."""
    position_id: str
    pair: StatisticalPair
    entry_zscore: Decimal
    current_zscore: Decimal
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    hedge_ratio: Decimal
    status: ExecutionStatus = ExecutionStatus.PENDING
    leg1_order_id: Optional[str] = None
    leg2_order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class StatisticalStrategy:
    """
    Advanced Statistical Arbitrage Strategy.
    
    This class provides sophisticated statistical arbitrage capabilities:
    1. Cointegration-based pairs selection
    2. Dynamic spread modeling
    3. Kalman filter for hedge ratio estimation
    4. Mean reversion detection
    5. Multi-asset statistical arbitrage
    6. Risk management
    7. Position sizing
    8. Performance tracking
    
    Features:
    - Real-time pair discovery
    - Dynamic hedge ratio estimation
    - Kalman filter optimization
    - Mean reversion detection
    - Risk management
    - Position sizing
    - Performance monitoring
    """
    
    def __init__(
        self,
        exchanges: Dict[ExchangeType, BaseExchange],
        executor: BaseExecutor,
        min_cointegration_pvalue: Decimal = MIN_COINTEGRATION_PVALUE,
        min_correlation: Decimal = MIN_CORRELATION,
        max_correlation: Decimal = MAX_CORRELATION,
        zscore_entry: Decimal = ZSCORE_ENTRY_THRESHOLD,
        zscore_exit: Decimal = ZSCORE_EXIT_THRESHOLD,
        max_pairs: int = MAX_PAIRS,
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the statistical arbitrage strategy.
        
        Args:
            exchanges: Dictionary of exchange instances
            executor: Execution engine
            min_cointegration_pvalue: Minimum p-value for cointegration
            min_correlation: Minimum correlation for pair selection
            max_correlation: Maximum correlation to avoid overfitting
            zscore_entry: Z-score threshold for entry
            zscore_exit: Z-score threshold for exit
            max_pairs: Maximum number of pairs to monitor
            config: Optional configuration dictionary
            logger: Optional logger instance
        """
        self.exchanges = exchanges
        self.executor = executor
        self.min_cointegration_pvalue = min_cointegration_pvalue
        self.min_correlation = min_correlation
        self.max_correlation = max_correlation
        self.zscore_entry = zscore_entry
        self.zscore_exit = zscore_exit
        self.max_pairs = max_pairs
        self.config = config or {}
        self.logger = logger or self._setup_logger()
        
        # Data storage
        self.price_history: Dict[str, deque] = {}
        self.pairs: Dict[str, StatisticalPair] = {}
        self.positions: Dict[str, StatisticalPosition] = {}
        
        # Kalman filter state
        self.kalman_state: Dict[str, Dict[str, Any]] = {}
        
        # Active pairs and positions
        self.active_pairs: Set[str] = set()
        self.active_positions: Set[str] = set()
        self.completed_positions: Set[str] = set()
        
        # Metrics
        self.metrics = {
            "pairs_analyzed": 0,
            "pairs_found": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_spread_std": Decimal("0"),
            "success_rate": Decimal("0"),
            "errors": 0,
        }
        
        # Background tasks
        self._is_running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._rebalance_task: Optional[asyncio.Task] = None
        self._kalman_task: Optional[asyncio.Task] = None
        
        self.logger.info("StatisticalStrategy initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger."""
        logger = logging.getLogger(f"{__name__}.StatisticalStrategy")
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
    
    async def _fetch_price_history(
        self,
        exchange: BaseExchange,
        symbol: str,
        limit: int = 100,
    ) -> List[Decimal]:
        """
        Fetch price history from exchange.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            limit: Number of candles
            
        Returns:
            List of prices
        """
        try:
            ohlcv = await exchange.get_ohlcv(
                symbol=symbol,
                interval=Interval.M1,
                limit=limit,
            )
            
            return [c.close for c in ohlcv]
        except Exception as e:
            self.logger.debug(f"Failed to fetch price history: {e}")
            return []
    
    async def _calculate_cointegration(
        self,
        prices1: List[Decimal],
        prices2: List[Decimal],
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate cointegration between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            
        Returns:
            Tuple of (pvalue, hedge_ratio, intercept)
        """
        if len(prices1) < MIN_PRICE_HISTORY or len(prices2) < MIN_PRICE_HISTORY:
            return Decimal("1.0"), Decimal("1.0"), Decimal("0")
        
        # Convert to numpy arrays
        p1 = np.array([float(p) for p in prices1])
        p2 = np.array([float(p) for p in prices2])
        
        try:
            # Calculate cointegration
            coint_result = coint(p1, p2)
            pvalue = Decimal(str(coint_result[1]))
            
            # Calculate hedge ratio using OLS
            model = OLS(p1, p2)
            results = model.fit()
            hedge_ratio = Decimal(str(results.params[0]))
            intercept = Decimal(str(results.params[1] if len(results.params) > 1 else 0))
            
            return pvalue, hedge_ratio, intercept
            
        except Exception as e:
            self.logger.debug(f"Cointegration calculation failed: {e}")
            return Decimal("1.0"), Decimal("1.0"), Decimal("0")
    
    async def _calculate_correlation(
        self,
        prices1: List[Decimal],
        prices2: List[Decimal],
    ) -> Decimal:
        """
        Calculate correlation between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            
        Returns:
            Correlation coefficient
        """
        if len(prices1) < MIN_PRICE_HISTORY or len(prices2) < MIN_PRICE_HISTORY:
            return Decimal("0")
        
        p1 = np.array([float(p) for p in prices1])
        p2 = np.array([float(p) for p in prices2])
        
        try:
            correlation = np.corrcoef(p1, p2)[0, 1]
            return Decimal(str(correlation))
        except Exception:
            return Decimal("0")
    
    async def _calculate_half_life(
        self,
        prices1: List[Decimal],
        prices2: List[Decimal],
        hedge_ratio: Decimal,
    ) -> Decimal:
        """
        Calculate half-life of mean reversion.
        
        Args:
            prices1: First price series
            prices2: Second price series
            hedge_ratio: Hedge ratio
            
        Returns:
            Half-life in seconds
        """
        try:
            p1 = np.array([float(p) for p in prices1])
            p2 = np.array([float(p) for p in prices2])
            hedge = float(hedge_ratio)
            
            # Calculate spread
            spread = p1 - hedge * p2
            
            # Calculate lagged spread and spread differences
            lagged_spread = np.roll(spread, 1)[1:]
            spread_diff = np.diff(spread)
            
            if len(spread_diff) < 2:
                return Decimal("1000")
            
            # OLS regression
            model = OLS(spread_diff, lagged_spread)
            results = model.fit()
            ar_coefficient = results.params[0]
            
            if ar_coefficient < 0:
                half_life = -np.log(2) / ar_coefficient
            else:
                half_life = 1000
            
            return Decimal(str(half_life))
            
        except Exception as e:
            self.logger.debug(f"Half-life calculation failed: {e}")
            return Decimal("1000")
    
    async def _analyze_pair(
        self,
        symbol1: str,
        symbol2: str,
        exchange1: ExchangeType,
        exchange2: ExchangeType,
    ) -> Optional[StatisticalPair]:
        """
        Analyze a pair for statistical arbitrage.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            exchange1: First exchange
            exchange2: Second exchange
            
        Returns:
            StatisticalPair or None
        """
        try:
            # Get exchanges
            ex1 = self._get_exchange(exchange1)
            ex2 = self._get_exchange(exchange2)
            
            if not ex1 or not ex2:
                return None
            
            # Fetch price history
            prices1 = await self._fetch_price_history(ex1, symbol1, limit=100)
            prices2 = await self._fetch_price_history(ex2, symbol2, limit=100)
            
            if len(prices1) < 30 or len(prices2) < 30:
                return None
            
            # Calculate correlation
            correlation = await self._calculate_correlation(prices1, prices2)
            
            if abs(correlation) < self.min_correlation or abs(correlation) > self.max_correlation:
                return None
            
            # Calculate cointegration
            pvalue, hedge_ratio, intercept = await self._calculate_cointegration(
                prices1, prices2
            )
            
            if pvalue > self.min_cointegration_pvalue:
                return None
            
            # Calculate spread statistics
            p1 = np.array([float(p) for p in prices1])
            p2 = np.array([float(p) for p in prices2])
            hedge = float(hedge_ratio)
            
            spread = p1 - hedge * p2
            spread_mean = Decimal(str(np.mean(spread)))
            spread_std = Decimal(str(np.std(spread)))
            
            if spread_std < MIN_SPREAD_STD or spread_std > MAX_SPREAD_STD:
                return None
            
            # Calculate half-life
            half_life = await self._calculate_half_life(prices1, prices2, hedge_ratio)
            
            # Calculate current spread and z-score
            current_spread = Decimal(str(p1[-1] - hedge * p2[-1]))
            current_zscore = (current_spread - spread_mean) / spread_std
            
            # Determine status
            if abs(current_zscore) > self.zscore_entry:
                if current_zscore > 0:
                    status = "entry_short"  # Spread is high, short spread
                else:
                    status = "entry_long"   # Spread is low, long spread
            elif abs(current_zscore) < self.zscore_exit:
                status = "exit"
            else:
                status = "normal"
            
            # Calculate confidence
            confidence = Decimal(str(min(1.0, 1.0 - float(pvalue) / 0.05)))
            
            return StatisticalPair(
                symbol1=symbol1,
                symbol2=symbol2,
                exchange1=exchange1,
                exchange2=exchange2,
                correlation=correlation,
                cointegration_pvalue=pvalue,
                hedge_ratio=hedge_ratio,
                intercept=intercept,
                spread_mean=spread_mean,
                spread_std=spread_std,
                half_life=half_life,
                current_spread=current_spread,
                current_zscore=current_zscore,
                status=status,
                confidence=confidence,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.debug(f"Pair analysis failed: {e}")
            return None
    
    async def _find_pairs(self) -> List[StatisticalPair]:
        """
        Find statistical arbitrage pairs.
        
        Returns:
            List of StatisticalPair objects
        """
        pairs = []
        
        try:
            # Get symbols from exchanges
            symbols_by_exchange = {}
            for exchange_type, exchange in self.exchanges.items():
                try:
                    symbols = await exchange.get_symbols()
                    symbols_by_exchange[exchange_type] = symbols[:50]  # Limit for performance
                except Exception as e:
                    self.logger.debug(f"Failed to get symbols from {exchange_type}: {e}")
            
            # Analyze pairs between same exchange
            for exchange_type, symbols in symbols_by_exchange.items():
                for i, sym1 in enumerate(symbols):
                    for sym2 in symbols[i+1:]:
                        try:
                            pair = await self._analyze_pair(
                                sym1, sym2,
                                exchange_type, exchange_type
                            )
                            if pair:
                                pairs.append(pair)
                        except Exception:
                            continue
            
            # Update metrics
            self.metrics["pairs_analyzed"] += len(pairs)
            
            # Sort by confidence and p-value
            pairs.sort(key=lambda x: (float(x.confidence), -float(x.cointegration_pvalue)), reverse=True)
            
            return pairs[:self.max_pairs]
            
        except Exception as e:
            self.logger.error(f"Pair finding failed: {e}")
            return []
    
    async def _update_kalman_filter(
        self,
        pair: StatisticalPair,
        price1: Decimal,
        price2: Decimal,
    ) -> None:
        """
        Update Kalman filter for dynamic hedge ratio.
        
        Args:
            pair: Statistical pair
            price1: First price
            price2: Second price
        """
        key = f"{pair.symbol1}_{pair.symbol2}"
        
        if key not in self.kalman_state:
            self.kalman_state[key] = {
                "hedge_ratio": float(pair.hedge_ratio),
                "intercept": float(pair.intercept),
                "variance": 0.01,
            }
        
        state = self.kalman_state[key]
        
        # Simple update: moving average of hedge ratio
        p1 = float(price1)
        p2 = float(price2)
        
        if p2 != 0:
            new_ratio = p1 / p2
        else:
            new_ratio = state["hedge_ratio"]
        
        # Exponential smoothing
        alpha = 0.1
        state["hedge_ratio"] = alpha * new_ratio + (1 - alpha) * state["hedge_ratio"]
        state["intercept"] = p1 - state["hedge_ratio"] * p2
        state["variance"] = 0.1 * (p1 - state["hedge_ratio"] * p2 - state["intercept"]) ** 2 + 0.9 * state["variance"]
    
    async def _execute_pair_trade(
        self,
        pair: StatisticalPair,
        position_type: str,  # "long" or "short"
    ) -> Optional[StatisticalPosition]:
        """
        Execute a pair trade.
        
        Args:
            pair: Statistical pair
            position_type: Type of position
            
        Returns:
            StatisticalPosition or None
        """
        try:
            # Calculate position sizes
            hedge_ratio = pair.hedge_ratio
            position_size = Decimal("10000") / pair.spread_std  # Dynamic sizing
            
            if position_type == "long":
                # Long leg1, short leg2
                leg1_size = position_size
                leg2_size = position_size * hedge_ratio
                leg1_side = OrderSide.BUY
                leg2_side = OrderSide.SELL
            else:
                # Short leg1, long leg2
                leg1_size = position_size
                leg2_size = position_size * hedge_ratio
                leg1_side = OrderSide.SELL
                leg2_side = OrderSide.BUY
            
            # Get exchanges
            ex1 = self._get_exchange(pair.exchange1)
            ex2 = self._get_exchange(pair.exchange2)
            
            if not ex1 or not ex2:
                return None
            
            # Get current prices
            ticker1 = await ex1.get_ticker(pair.symbol1)
            ticker2 = await ex2.get_ticker(pair.symbol2)
            
            if not ticker1 or not ticker2:
                return None
            
            # Build execution plan
            order1 = ExecutionOrder(
                exchange=pair.exchange1,
                symbol=pair.symbol1,
                side=leg1_side,
                order_type=OrderType.MARKET,
                quantity=leg1_size,
                price=ticker1.last,
                time_in_force=TimeInForce.IOC,
            )
            
            order2 = ExecutionOrder(
                exchange=pair.exchange2,
                symbol=pair.symbol2,
                side=leg2_side,
                order_type=OrderType.MARKET,
                quantity=leg2_size,
                price=ticker2.last,
                time_in_force=TimeInForce.IOC,
            )
            
            plan = ExecutionPlan(
                execution_id=f"stat_{pair.symbol1}_{pair.symbol2}_{int(time.time())}",
                execution_type=ExecutionType.ATOMIC,
                orders=[order1, order2],
                config=ExecutionConfig(
                    max_slippage=Decimal("0.01"),
                    max_retries=3,
                    timeout=30,
                ),
                priority=ExecutionPriority.HIGH,
                risk_level=ExecutionRisk.MEDIUM,
                required_balance=position_size,
                max_loss=position_size * Decimal("0.05"),
                deadline=datetime.utcnow() + timedelta(minutes=2),
            )
            
            # Execute
            result = await self.executor.execute(plan)
            
            if result.status != ExecutionStatus.COMPLETED:
                self.logger.warning(f"Pair trade execution failed: {result.error}")
                return None
            
            # Create position
            position = StatisticalPosition(
                position_id=f"stat_pos_{pair.symbol1}_{pair.symbol2}_{int(time.time())}",
                pair=pair,
                entry_zscore=pair.current_zscore,
                current_zscore=pair.current_zscore,
                size=position_size,
                entry_price=ticker1.last,  # Simplified
                current_price=ticker1.last,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                hedge_ratio=hedge_ratio,
                status=ExecutionStatus.COMPLETED,
                leg1_order_id=result.orders[0].order_id if result.orders else None,
                leg2_order_id=result.orders[1].order_id if result.orders else None,
                timestamp=datetime.utcnow(),
            )
            
            return position
            
        except Exception as e:
            self.logger.error(f"Pair trade execution failed: {e}")
            return None
    
    async def _check_and_close_positions(self) -> None:
        """Check and close positions that have reverted to mean."""
        for position_id, position in self.positions.items():
            if position.status != ExecutionStatus.COMPLETED:
                continue
            
            # Get current prices
            ex1 = self._get_exchange(position.pair.exchange1)
            ex2 = self._get_exchange(position.pair.exchange2)
            
            if not ex1 or not ex2:
                continue
            
            ticker1 = await ex1.get_ticker(position.pair.symbol1)
            ticker2 = await ex2.get_ticker(position.pair.symbol2)
            
            if not ticker1 or not ticker2:
                continue
            
            # Calculate current z-score
            p1 = float(ticker1.last)
            p2 = float(ticker2.last)
            hedge = float(position.hedge_ratio)
            
            spread = p1 - hedge * p2
            spread_mean = float(position.pair.spread_mean)
            spread_std = float(position.pair.spread_std)
            
            if spread_std == 0:
                continue
            
            zscore = (spread - spread_mean) / spread_std
            
            # Update position
            position.current_zscore = Decimal(str(zscore))
            position.current_price = ticker1.last
            
            # Check if should exit
            if abs(zscore) < float(self.zscore_exit):
                # Close position
                # Build closing orders (reverse of entry)
                leg1_side = OrderSide.BUY if position.entry_zscore < 0 else OrderSide.SELL
                leg2_side = OrderSide.SELL if position.entry_zscore < 0 else OrderSide.BUY
                
                order1 = ExecutionOrder(
                    exchange=position.pair.exchange1,
                    symbol=position.pair.symbol1,
                    side=leg1_side,
                    order_type=OrderType.MARKET,
                    quantity=position.size,
                    price=ticker1.last,
                    time_in_force=TimeInForce.IOC,
                )
                
                order2 = ExecutionOrder(
                    exchange=position.pair.exchange2,
                    symbol=position.pair.symbol2,
                    side=leg2_side,
                    order_type=OrderType.MARKET,
                    quantity=position.size * position.hedge_ratio,
                    price=ticker2.last,
                    time_in_force=TimeInForce.IOC,
                )
                
                plan = ExecutionPlan(
                    execution_id=f"close_stat_{position.position_id}",
                    execution_type=ExecutionType.ATOMIC,
                    orders=[order1, order2],
                    config=ExecutionConfig(
                        max_slippage=Decimal("0.01"),
                        max_retries=3,
                        timeout=30,
                    ),
                    priority=ExecutionPriority.HIGH,
                    risk_level=ExecutionRisk.MEDIUM,
                    required_balance=position.size,
                    max_loss=position.size * Decimal("0.05"),
                    deadline=datetime.utcnow() + timedelta(minutes=2),
                )
                
                result = await self.executor.execute(plan)
                
                if result.status == ExecutionStatus.COMPLETED:
                    # Calculate realized PnL
                    pnl = position.unrealized_pnl
                    position.realized_pnl = pnl
                    position.status = ExecutionStatus.COMPLETED
                    
                    self.metrics["positions_closed"] += 1
                    if pnl > 0:
                        self.metrics["total_profit"] += pnl
                    else:
                        self.metrics["total_loss"] += abs(pnl)
                    
                    self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
                    
                    self.completed_positions.add(position_id)
                    self.active_positions.discard(position_id)
                    
                    self.logger.info(f"Position closed: {position_id}, PnL: ${float(pnl):.2f}")
    
    async def _rebalance_loop(self) -> None:
        """Background rebalancing loop."""
        while self._is_running:
            try:
                await asyncio.sleep(REBALANCE_INTERVAL)
                await self._check_and_close_positions()
            except Exception as e:
                self.logger.error(f"Rebalance loop error: {e}")
    
    async def _kalman_update_loop(self) -> None:
        """Background Kalman filter update loop."""
        while self._is_running:
            try:
                await asyncio.sleep(KALMAN_UPDATE_INTERVAL)
                
                for pair_key, pair in self.pairs.items():
                    try:
                        # Get current prices
                        ex1 = self._get_exchange(pair.exchange1)
                        ex2 = self._get_exchange(pair.exchange2)
                        
                        if not ex1 or not ex2:
                            continue
                        
                        ticker1 = await ex1.get_ticker(pair.symbol1)
                        ticker2 = await ex2.get_ticker(pair.symbol2)
                        
                        if ticker1 and ticker2:
                            await self._update_kalman_filter(
                                pair,
                                ticker1.last,
                                ticker2.last,
                            )
                    except Exception as e:
                        self.logger.debug(f"Kalman update failed: {e}")
                        
            except Exception as e:
                self.logger.error(f"Kalman update loop error: {e}")
    
    async def start(self) -> None:
        """Start the strategy."""
        if self._is_running:
            return
        
        self._is_running = True
        self._scan_task = asyncio.create_task(self._scan_loop())
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        self._kalman_task = asyncio.create_task(self._kalman_update_loop())
        
        self.logger.info("StatisticalStrategy started")
    
    async def stop(self) -> None:
        """Stop the strategy."""
        self._is_running = False
        
        for task in [self._scan_task, self._rebalance_task, self._kalman_task]:
            if task:
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
        
        self.logger.info("StatisticalStrategy stopped")
    
    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self._is_running:
            try:
                # Find new pairs
                pairs = await self._find_pairs()
                
                if pairs:
                    self.metrics["pairs_found"] = len(pairs)
                    
                    # Store pairs
                    for pair in pairs:
                        key = f"{pair.symbol1}_{pair.symbol2}"
                        self.pairs[key] = pair
                        self.active_pairs.add(key)
                    
                    # Open positions for new pairs
                    for pair in pairs:
                        if pair.status in ["entry_long", "entry_short"] and pair.confidence > Decimal("0.7"):
                            position_type = "long" if pair.status == "entry_long" else "short"
                            position = await self._execute_pair_trade(pair, position_type)
                            
                            if position:
                                self.positions[position.position_id] = position
                                self.active_positions.add(position.position_id)
                                self.metrics["positions_opened"] += 1
                
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
            self.metrics["positions_closed"] / self.metrics["positions_opened"]
            if self.metrics["positions_opened"] > 0 else Decimal("0")
        )
        
        return {
            "pairs_analyzed": self.metrics["pairs_analyzed"],
            "pairs_found": self.metrics["pairs_found"],
            "active_pairs": len(self.active_pairs),
            "positions_opened": self.metrics["positions_opened"],
            "positions_closed": self.metrics["positions_closed"],
            "active_positions": len(self.active_positions),
            "completed_positions": len(self.completed_positions),
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "avg_spread_std": float(self.metrics["avg_spread_std"]),
            "success_rate": float(success_rate),
            "errors": self.metrics["errors"],
            "is_running": self._is_running,
        }


# Module exports
__all__ = [
    'StatisticalStrategy',
    'StatisticalMethod',
    'StatisticalPair',
    'StatisticalPosition',
]
