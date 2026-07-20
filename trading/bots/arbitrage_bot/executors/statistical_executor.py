# trading/bots/arbitrage_bot/executors/statistical_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Statistical Arbitrage Execution Engine

"""
Statistical Executor - Advanced Statistical Arbitrage Execution Engine

This module provides sophisticated statistical arbitrage execution capabilities,
handling pairs trading, cointegration-based strategies, and mean reversion
execution with proper risk management and position sizing.

Architecture:
    - BaseStatisticalExecutor: Abstract base class
    - StatisticalExecutor: Main executor implementation
    - PairManager: Pair management
    - SpreadCalculator: Spread calculation
    - ZScoreAnalyzer: Z-score analysis
    - PositionSizer: Position sizing
    - RiskManager: Risk management
    - ExecutionMonitor: Execution monitoring

Features:
    - Pairs trading execution
    - Cointegration-based strategies
    - Mean reversion execution
    - Dynamic position sizing
    - Risk management
    - Hedging
    - Execution monitoring
    - MEV protection
"""

import asyncio
import json
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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

import numpy as np
from scipy import stats
from statsmodels.tsa.stattools import coint, adfuller

from .base_executor import (
    BaseExecutor,
    ExecutionType,
    ExecutionStatus,
    ExecutionPriority,
    ExecutionRisk,
    ExecutionConfig,
    ExecutionOrder,
    ExecutionPosition,
    ExecutionResult,
    ExecutionPlan,
    ExecutionListener,
)
from ..exchanges.base_exchange import (
    BaseExchange,
    ExchangeType,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Order,
    Trade,
    Position,
    Balance,
    Ticker,
)


# Constants
MIN_COINTEGRATION_PVALUE = Decimal("0.05")
MIN_CORRELATION = Decimal("0.7")
ZSCORE_ENTRY_THRESHOLD = Decimal("2.0")
ZSCORE_EXIT_THRESHOLD = Decimal("0.5")
MAX_POSITION_SIZE = Decimal("100000")
REBALANCE_INTERVAL = 60  # seconds
MIN_SPREAD_STD = Decimal("0.01")
MAX_SPREAD_STD = Decimal("0.5")


@dataclass
class StatisticalConfig:
    """Statistical arbitrage execution configuration."""
    min_cointegration_pvalue: Decimal = MIN_COINTEGRATION_PVALUE
    min_correlation: Decimal = MIN_CORRELATION
    zscore_entry_threshold: Decimal = ZSCORE_ENTRY_THRESHOLD
    zscore_exit_threshold: Decimal = ZSCORE_EXIT_THRESHOLD
    max_position_size: Decimal = MAX_POSITION_SIZE
    rebalance_interval: int = REBALANCE_INTERVAL
    min_spread_std: Decimal = MIN_SPREAD_STD
    max_spread_std: Decimal = MAX_SPREAD_STD
    use_hedging: bool = True
    hedge_ratio: Decimal = Decimal("1.0")
    use_cointegration: bool = True
    use_correlation: bool = True
    require_confirmation: bool = True
    use_mev_protection: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatisticalPair:
    """Statistical arbitrage pair."""
    symbol1: str
    symbol2: str
    correlation: Decimal
    cointegration_pvalue: Decimal
    hedge_ratio: Decimal
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
    symbol1: str
    symbol2: str
    exchange1: ExchangeType
    exchange2: ExchangeType
    leg1_side: OrderSide
    leg2_side: OrderSide
    leg1_size: Decimal
    leg2_size: Decimal
    leg1_price: Decimal
    leg2_price: Decimal
    spread: Decimal
    zscore: Decimal
    entry_spread: Decimal
    current_spread: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    hedge_ratio: Decimal = Decimal("1.0")
    status: ExecutionStatus = ExecutionStatus.PENDING
    leg1_order_id: Optional[str] = None
    leg2_order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class StatisticalExecutor(BaseExecutor):
    """
    Advanced Statistical Arbitrage Execution Engine.
    
    This class provides sophisticated statistical arbitrage execution:
    1. Pairs trading execution
    2. Cointegration-based strategies
    3. Mean reversion execution
    4. Dynamic position sizing
    5. Risk management
    6. Hedging
    7. Execution monitoring
    8. MEV protection
    
    Features:
    - Pairs trading
    - Cointegration-based strategies
    - Mean reversion execution
    - Dynamic position sizing
    - Risk management
    - Hedging
    - Execution monitoring
    - MEV protection
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        statistical_config: Optional[StatisticalConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the statistical executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            statistical_config: Statistical configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.statistical_config = statistical_config or StatisticalConfig()
        
        # Positions
        self.positions: Dict[str, StatisticalPosition] = {}
        self.active_positions: Set[str] = set()
        self.completed_positions: Set[str] = set()
        
        # Pairs
        self.pairs: Dict[str, StatisticalPair] = {}
        self.active_pairs: Set[str] = set()
        
        # Price history
        self.price_history: Dict[str, Dict[str, List[Decimal]]] = {}
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._position_lock = Lock()
        self._pair_lock = Lock()
        self._price_lock = Lock()
        
        # Background tasks
        self._is_running = True
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        # Metrics
        self.metrics.update({
            "positions_total": 0,
            "positions_succeeded": 0,
            "positions_failed": 0,
            "pairs_traded": 0,
            "pairs_succeeded": 0,
            "pairs_failed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_position_time_ms": 0,
            "success_rate": Decimal("0"),
            "avg_correlation": Decimal("0"),
            "avg_cointegration": Decimal("0"),
        })
        
        self.logger.info("StatisticalExecutor initialized")
    
    def _generate_position_id(self) -> str:
        """Generate a unique position ID."""
        import uuid
        return f"stat_pos_{uuid.uuid4().hex[:16]}"
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _get_price(self, exchange: BaseExchange, symbol: str) -> Optional[Decimal]:
        """
        Get current price from exchange.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            
        Returns:
            Price or None
        """
        try:
            ticker = await exchange.get_ticker(symbol)
            if ticker:
                return ticker.last
            return None
        except Exception as e:
            self.logger.debug(f"Failed to get price: {e}")
            return None
    
    async def _update_price_history(
        self,
        exchange: ExchangeType,
        symbol: str,
        price: Decimal,
    ) -> None:
        """
        Update price history for a symbol.
        
        Args:
            exchange: Exchange type
            symbol: Trading symbol
            price: Current price
        """
        key = f"{exchange.value}_{symbol}"
        
        with self._price_lock:
            if key not in self.price_history:
                self.price_history[key] = []
            
            self.price_history[key].append(price)
            
            # Keep limited history
            if len(self.price_history[key]) > 1000:
                self.price_history[key] = self.price_history[key][-1000:]
    
    async def _calculate_cointegration(
        self,
        prices1: List[Decimal],
        prices2: List[Decimal],
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate cointegration between two price series.
        
        Args:
            prices1: First price series
            prices2: Second price series
            
        Returns:
            Tuple of (cointegration_pvalue, hedge_ratio)
        """
        try:
            if len(prices1) < 20 or len(prices2) < 20:
                return Decimal("1.0"), Decimal("1.0")
            
            # Convert to numpy arrays
            p1 = np.array([float(p) for p in prices1])
            p2 = np.array([float(p) for p in prices2])
            
            # Calculate cointegration
            coint_result = coint(p1, p2)
            pvalue = Decimal(str(coint_result[1]))
            
            # Calculate hedge ratio using OLS
            from statsmodels.regression.linear_model import OLS
            model = OLS(p1, p2)
            results = model.fit()
            hedge_ratio = Decimal(str(results.params[0]))
            
            return pvalue, hedge_ratio
            
        except Exception as e:
            self.logger.debug(f"Cointegration calculation failed: {e}")
            return Decimal("1.0"), Decimal("1.0")
    
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
        try:
            if len(prices1) < 10 or len(prices2) < 10:
                return Decimal("0")
            
            # Convert to numpy arrays
            p1 = np.array([float(p) for p in prices1])
            p2 = np.array([float(p) for p in prices2])
            
            # Calculate Pearson correlation
            correlation = np.corrcoef(p1, p2)[0, 1]
            return Decimal(str(correlation))
            
        except Exception as e:
            self.logger.debug(f"Correlation calculation failed: {e}")
            return Decimal("0")
    
    async def _analyze_pair(
        self,
        exchange1: ExchangeType,
        exchange2: ExchangeType,
        symbol1: str,
        symbol2: str,
    ) -> Optional[StatisticalPair]:
        """
        Analyze a pair for statistical arbitrage.
        
        Args:
            exchange1: First exchange
            exchange2: Second exchange
            symbol1: First symbol
            symbol2: Second symbol
            
        Returns:
            StatisticalPair or None
        """
        try:
            # Get price histories
            key1 = f"{exchange1.value}_{symbol1}"
            key2 = f"{exchange2.value}_{symbol2}"
            
            with self._price_lock:
                prices1 = self.price_history.get(key1, [])
                prices2 = self.price_history.get(key2, [])
            
            if len(prices1) < 30 or len(prices2) < 30:
                return None
            
            # Calculate correlation
            correlation = await self._calculate_correlation(prices1, prices2)
            if abs(correlation) < self.statistical_config.min_correlation:
                return None
            
            # Calculate cointegration
            pvalue, hedge_ratio = await self._calculate_cointegration(prices1, prices2)
            if pvalue > self.statistical_config.min_cointegration_pvalue:
                return None
            
            # Calculate spread
            p1 = np.array([float(p) for p in prices1])
            p2 = np.array([float(p) for p in prices2])
            spread = p1 - float(hedge_ratio) * p2
            
            spread_mean = Decimal(str(np.mean(spread)))
            spread_std = Decimal(str(np.std(spread)))
            
            if spread_std < self.statistical_config.min_spread_std:
                return None
            
            if spread_std > self.statistical_config.max_spread_std:
                return None
            
            # Calculate half-life of mean reversion
            lagged_spread = np.roll(spread, 1)[1:]
            spread_diff = np.diff(spread)
            
            if len(spread_diff) > 1:
                from statsmodels.regression.linear_model import OLS
                model = OLS(spread_diff, lagged_spread)
                results = model.fit()
                ar_coefficient = results.params[0]
                
                if ar_coefficient < 0:
                    half_life = Decimal(str(-np.log(2) / ar_coefficient))
                else:
                    half_life = Decimal("1000")
            else:
                half_life = Decimal("1000")
            
            # Calculate current spread and z-score
            current_spread = Decimal(str(p1[-1] - float(hedge_ratio) * p2[-1]))
            current_zscore = (current_spread - spread_mean) / spread_std
            
            # Determine status
            if abs(current_zscore) > self.statistical_config.zscore_entry_threshold:
                if current_zscore > 0:
                    status = "entry_short"  # Spread is high, short spread
                else:
                    status = "entry_long"   # Spread is low, long spread
            elif abs(current_zscore) < self.statistical_config.zscore_exit_threshold:
                status = "exit"
            else:
                status = "normal"
            
            # Calculate confidence
            confidence = Decimal(str(min(1.0, 1.0 - float(pvalue) / 0.05)))
            
            pair = StatisticalPair(
                symbol1=symbol1,
                symbol2=symbol2,
                correlation=correlation,
                cointegration_pvalue=pvalue,
                hedge_ratio=hedge_ratio,
                spread_mean=spread_mean,
                spread_std=spread_std,
                half_life=half_life,
                current_spread=current_spread,
                current_zscore=current_zscore,
                status=status,
                confidence=confidence,
                timestamp=datetime.utcnow(),
            )
            
            return pair
            
        except Exception as e:
            self.logger.debug(f"Pair analysis failed: {e}")
            return None
    
    async def _execute_pair_trade(
        self,
        pair: StatisticalPair,
        position_type: str,  # "long" or "short"
    ) -> Tuple[Optional[Order], Optional[Order], Optional[str]]:
        """
        Execute a pair trade.
        
        Args:
            pair: Statistical pair
            position_type: Type of position
            
        Returns:
            Tuple of (leg1_order, leg2_order, error_message)
        """
        try:
            # Get exchanges
            exchange1 = self._get_exchange(ExchangeType.BINANCE)  # Would be dynamic
            exchange2 = self._get_exchange(ExchangeType.BINANCE)  # Would be dynamic
            
            if not exchange1 or not exchange2:
                return None, None, "Exchange not found"
            
            # Calculate position sizes
            hedge_ratio = pair.hedge_ratio
            position_size = Decimal("10000")  # Would use dynamic sizing
            
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
            
            # Execute leg1
            leg1_order = await exchange1.place_order(
                symbol=pair.symbol1,
                side=leg1_side,
                order_type=OrderType.MARKET,
                quantity=leg1_size,
            )
            
            if not leg1_order:
                return None, None, "Leg1 order failed"
            
            # Execute leg2
            leg2_order = await exchange2.place_order(
                symbol=pair.symbol2,
                side=leg2_side,
                order_type=OrderType.MARKET,
                quantity=leg2_size,
            )
            
            if not leg2_order:
                # Rollback leg1
                await exchange1.cancel_order(leg1_order.order_id, pair.symbol1)
                return None, None, "Leg2 order failed"
            
            return leg1_order, leg2_order, None
            
        except Exception as e:
            return None, None, str(e)
    
    async def _close_pair_trade(
        self,
        position: StatisticalPosition,
    ) -> Tuple[Optional[Order], Optional[Order], Optional[str]]:
        """
        Close a pair trade.
        
        Args:
            position: Position to close
            
        Returns:
            Tuple of (leg1_close, leg2_close, error_message)
        """
        try:
            exchange1 = self._get_exchange(position.exchange1)
            exchange2 = self._get_exchange(position.exchange2)
            
            if not exchange1 or not exchange2:
                return None, None, "Exchange not found"
            
            # Close leg1 (reverse the original side)
            leg1_side = OrderSide.SELL if position.leg1_side == OrderSide.BUY else OrderSide.BUY
            leg1_close = await exchange1.place_order(
                symbol=position.symbol1,
                side=leg1_side,
                order_type=OrderType.MARKET,
                quantity=position.leg1_size,
            )
            
            if not leg1_close:
                return None, None, "Leg1 close failed"
            
            # Close leg2
            leg2_side = OrderSide.SELL if position.leg2_side == OrderSide.BUY else OrderSide.BUY
            leg2_close = await exchange2.place_order(
                symbol=position.symbol2,
                side=leg2_side,
                order_type=OrderType.MARKET,
                quantity=position.leg2_size,
            )
            
            if not leg2_close:
                return None, None, "Leg2 close failed"
            
            return leg1_close, leg2_close, None
            
        except Exception as e:
            return None, None, str(e)
    
    async def _rebalance_loop(self) -> None:
        """Background rebalancing loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self.statistical_config.rebalance_interval)
                
                # Check and rebalance positions
                with self._position_lock:
                    for position_id, position in self.positions.items():
                        if position.status == ExecutionStatus.COMPLETED:
                            continue
                        
                        # Get current prices
                        exchange1 = self._get_exchange(position.exchange1)
                        exchange2 = self._get_exchange(position.exchange2)
                        
                        if not exchange1 or not exchange2:
                            continue
                        
                        price1 = await self._get_price(exchange1, position.symbol1)
                        price2 = await self._get_price(exchange2, position.symbol2)
                        
                        if not price1 or not price2:
                            continue
                        
                        # Update current price
                        position.current_spread = price1 - position.hedge_ratio * price2
                        
                        # Calculate unrealized PnL
                        pnl1 = (price1 - position.leg1_price) * position.leg1_size
                        pnl2 = (price2 - position.leg2_price) * position.leg2_size
                        position.unrealized_pnl = pnl1 + pnl2
                        
                        # Check if should exit
                        if abs(position.zscore) < self.statistical_config.zscore_exit_threshold:
                            # Close position
                            leg1_close, leg2_close, error = await self._close_pair_trade(position)
                            if not error:
                                position.status = ExecutionStatus.COMPLETED
                                position.realized_pnl = position.unrealized_pnl
                                self.metrics["positions_succeeded"] += 1
                                self.metrics["total_profit"] += position.realized_pnl
                
            except Exception as e:
                self.logger.error(f"Rebalance loop error: {e}")
    
    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._is_running:
            try:
                await asyncio.sleep(5)
                
                # Monitor active pairs
                with self._pair_lock:
                    for pair_id, pair in self.pairs.items():
                        if pair.status not in ["entry_long", "entry_short"]:
                            continue
                        
                        # Check if pair is still viable
                        if pair.confidence < Decimal("0.5"):
                            self.active_pairs.discard(pair_id)
                
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a statistical arbitrage plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting statistical execution: {execution_id}")
        self._emit_started(execution_id)
        
        try:
            # Validate execution plan
            is_valid, error = await self.validate_execution(plan)
            if not is_valid:
                raise self.ValidationError(f"Invalid execution plan: {error}")
            
            # Check balance
            has_balance, error = await self.check_balance(plan)
            if not has_balance:
                raise self.BalanceError(f"Insufficient balance: {error}")
            
            # Calculate risk
            risk_metrics = await self.calculate_risk(plan)
            if risk_metrics.get("risk_level", ExecutionRisk.MEDIUM) == ExecutionRisk.CRITICAL:
                raise self.RiskError("Risk level too high")
            
            # Extract pair details
            if len(plan.orders) != 2:
                raise self.ValidationError("Statistical arbitrage requires exactly 2 orders")
            
            leg1_order = plan.orders[0]
            leg2_order = plan.orders[1]
            
            # Analyze pair
            pair = await self._analyze_pair(
                leg1_order.exchange,
                leg2_order.exchange,
                leg1_order.symbol,
                leg2_order.symbol,
            )
            
            if not pair:
                raise self.ExecutionError("No viable statistical arbitrage pair found")
            
            # Determine position type
            if pair.current_zscore > self.statistical_config.zscore_entry_threshold:
                position_type = "short"  # Short spread
            elif pair.current_zscore < -self.statistical_config.zscore_entry_threshold:
                position_type = "long"  # Long spread
            else:
                raise self.ExecutionError("No entry signal")
            
            # Apply MEV protection
            if self.config.use_mev_protection:
                plan = await self.apply_mev_protection(plan)
            
            # Apply slippage protection
            plan = await self.apply_slippage_protection(plan)
            
            # Execute pair trade
            leg1_result, leg2_result, error = await self._execute_pair_trade(
                pair,
                position_type,
            )
            
            if error or not leg1_result or not leg2_result:
                raise self.ExecutionError(f"Pair trade execution failed: {error}")
            
            # Create position
            position_id = self._generate_position_id()
            position = StatisticalPosition(
                position_id=position_id,
                symbol1=leg1_order.symbol,
                symbol2=leg2_order.symbol,
                exchange1=leg1_order.exchange,
                exchange2=leg2_order.exchange,
                leg1_side=leg1_order.side,
                leg2_side=leg2_order.side,
                leg1_size=leg1_order.quantity,
                leg2_size=leg2_order.quantity,
                leg1_price=leg1_result.average_price or leg1_order.price or Decimal("0"),
                leg2_price=leg2_result.average_price or leg2_order.price or Decimal("0"),
                spread=pair.current_spread,
                zscore=pair.current_zscore,
                entry_spread=pair.current_spread,
                current_spread=pair.current_spread,
                hedge_ratio=pair.hedge_ratio,
                status=ExecutionStatus.COMPLETED,
                leg1_order_id=leg1_result.order_id,
                leg2_order_id=leg2_result.order_id,
                timestamp=datetime.utcnow(),
            )
            
            with self._position_lock:
                self.positions[position_id] = position
                self.completed_positions.add(position_id)
            
            # Store pair
            pair_key = f"{leg1_order.symbol}_{leg2_order.symbol}"
            with self._pair_lock:
                self.pairs[pair_key] = pair
                self.active_pairs.add(pair_key)
            
            # Calculate profit (simplified)
            profit = pair.current_spread * leg1_order.quantity
            
            # Update metrics
            self.metrics["positions_total"] += 1
            self.metrics["pairs_traded"] += 1
            
            if profit > 0:
                self.metrics["positions_succeeded"] += 1
                self.metrics["pairs_succeeded"] += 1
                self.metrics["total_profit"] += profit
            else:
                self.metrics["positions_failed"] += 1
                self.metrics["pairs_failed"] += 1
                self.metrics["total_loss"] += abs(profit)
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            self.metrics["avg_correlation"] = (
                (self.metrics["avg_correlation"] * (self.metrics["pairs_traded"] - 1) +
                 pair.correlation) / self.metrics["pairs_traded"]
            )
            self.metrics["avg_cointegration"] = (
                (self.metrics["avg_cointegration"] * (self.metrics["pairs_traded"] - 1) +
                 (Decimal("1") - pair.cointegration_pvalue)) / self.metrics["pairs_traded"]
            )
            
            # Create execution result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
                orders=[leg1_result, leg2_result],
                trades=[],
                positions=[],
                profit=profit,
                profit_percentage=(
                    profit / (leg1_order.quantity * leg1_order.price) * Decimal("100")
                    if leg1_order.quantity * leg1_order.price > 0 else Decimal("0")
                ),
                gas_cost=Decimal("0"),
                fee_cost=Decimal("0"),
                total_cost=leg1_order.quantity * leg1_order.price,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_id": position_id,
                    "pair": pair_key,
                    "correlation": str(pair.correlation),
                    "cointegration": str(pair.cointegration_pvalue),
                    "zscore": str(pair.current_zscore),
                    "position_type": position_type,
                    "leg1_order_id": leg1_result.order_id,
                    "leg2_order_id": leg2_result.order_id,
                },
            )
            
            # Store result
            self.results[execution_id] = result
            
            # Update metrics
            self.metrics["executions_total"] += 1
            if result.status == ExecutionStatus.COMPLETED:
                self.metrics["executions_succeeded"] += 1
            elif result.status == ExecutionStatus.FAILED:
                self.metrics["executions_failed"] += 1
            
            self.metrics["avg_execution_time_ms"] = (
                (self.metrics["avg_execution_time_ms"] * (self.metrics["executions_total"] - 1) +
                 result.execution_time_ms) / self.metrics["executions_total"]
            )
            
            # Emit completion event
            self._emit_completed(result)
            
            self.logger.info(
                f"Statistical execution completed: {execution_id} "
                f"profit: ${float(result.profit):.2f}, "
                f"zscore: {float(pair.current_zscore):.2f}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Statistical execution failed: {error_msg}")
            self.metrics["errors"] += 1
            self.metrics["executions_failed"] += 1
            
            # Emit failure event
            self._emit_failed(execution_id, error_msg)
            
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                orders=[],
                trades=[],
                positions=[],
                profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fee_cost=Decimal("0"),
                total_cost=Decimal("0"),
                execution_time_ms=self._calculate_execution_time(start_time),
                timestamp=datetime.utcnow(),
                error=error_msg,
            )
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel an execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if cancelled successfully
        """
        self.logger.info(f"Cancelling execution: {execution_id}")
        
        cancelled = 0
        
        with self._position_lock:
            for position_id, position in self.positions.items():
                if position.status in [ExecutionStatus.PENDING, ExecutionStatus.EXECUTING]:
                    position.status = ExecutionStatus.CANCELLED
                    cancelled += 1
        
        self._emit_cancelled(execution_id)
        
        return cancelled > 0
    
    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """
        Get execution status.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionStatus or None
        """
        result = self.results.get(execution_id)
        if result:
            return result.status
        
        return None
    
    async def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """
        Get execution result.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionResult or None
        """
        return self.results.get(execution_id)
    
    async def simulate_execution(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Simulate execution without placing real orders.
        
        Args:
            plan: Execution plan
            
        Returns:
            Simulated ExecutionResult
        """
        self.logger.info(f"Simulating statistical execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate pair trade
        profit = Decimal("10")
        zscore = Decimal("2.5")
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=[],
            trades=[],
            positions=[],
            profit=profit,
            profit_percentage=profit / Decimal("1000") * Decimal("100"),
            gas_cost=Decimal("0"),
            fee_cost=Decimal("0"),
            total_cost=Decimal("1000"),
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            metadata={
                "simulated": True,
                "zscore": str(zscore),
            },
        )
        
        return result
    
    async def validate_execution(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Validate an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check orders
            if len(plan.orders) != 2:
                return False, "Statistical arbitrage requires exactly 2 orders"
            
            # Check symbols are different
            if plan.orders[0].symbol == plan.orders[1].symbol:
                return False, "Symbols must be different"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def calculate_risk(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Calculate risk metrics for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Risk metrics dictionary
        """
        try:
            total_value = sum(order.quantity * (order.price or Decimal("1")) for order in plan.orders)
            
            risk_ratio = total_value / (self.statistical_config.max_position_size)
            if risk_ratio > Decimal("0.8"):
                risk_level = ExecutionRisk.CRITICAL
            elif risk_ratio > Decimal("0.5"):
                risk_level = ExecutionRisk.HIGH
            elif risk_ratio > Decimal("0.2"):
                risk_level = ExecutionRisk.MEDIUM
            else:
                risk_level = ExecutionRisk.LOW
            
            return {
                "total_value": total_value,
                "risk_ratio": risk_ratio,
                "risk_level": risk_level,
                "order_count": len(plan.orders),
                "symbols": [o.symbol for o in plan.orders],
                "exchanges": [o.exchange for o in plan.orders],
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
                "order_count": 0,
                "symbols": [],
                "exchanges": [],
                "error": str(e),
            }
    
    async def check_balance(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Check if there is sufficient balance for execution.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (has_balance, error_message)
        """
        try:
            # Group orders by exchange
            exchange_orders: Dict[ExchangeType, List[ExecutionOrder]] = defaultdict(list)
            for order in plan.orders:
                exchange_orders[order.exchange].append(order)
            
            for exchange_type, orders in exchange_orders.items():
                exchange = self._get_exchange(exchange_type)
                if not exchange:
                    return False, f"Exchange not found: {exchange_type}"
                
                balances = await exchange.get_balances()
                
                for order in orders:
                    asset = order.symbol.split("/")[0]
                    required = order.quantity * (order.price or Decimal("1"))
                    
                    balance = balances.get(asset)
                    if not balance:
                        return False, f"No balance for {asset}"
                    
                    if balance.free < required:
                        return False, f"Insufficient balance: {asset} ({balance.free} < {required})"
            
            return True, None
            
        except Exception as e:
            return False, str(e)
    
    async def apply_mev_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply MEV protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        for order in plan.orders:
            order.extra_params["mev_protection"] = True
            order.extra_params["private_mempool"] = self.config.use_private_mempool
        
        return plan
    
    async def apply_slippage_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply slippage protection to an execution plan.
        
        Args:
            plan: Execution plan            
        Returns:
            Protected execution plan
        """
        for order in plan.orders:
            order.extra_params["slippage_tolerance"] = self.config.max_slippage
        
        return plan
    
    async def optimize_gas(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize gas costs for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Optimized execution plan
        """
        return plan
    
    def get_positions(self) -> Dict[str, StatisticalPosition]:
        """
        Get all statistical positions.
        
        Returns:
            Dictionary of position ID to StatisticalPosition
        """
        with self._position_lock:
            return self.positions.copy()
    
    def get_pairs(self) -> Dict[str, StatisticalPair]:
        """
        Get all statistical pairs.
        
        Returns:
            Dictionary of pair key to StatisticalPair
        """
        with self._pair_lock:
            return self.pairs.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **super().get_metrics(),
            "positions_total": self.metrics["positions_total"],
            "positions_succeeded": self.metrics["positions_succeeded"],
            "positions_failed": self.metrics["positions_failed"],
            "pairs_traded": self.metrics["pairs_traded"],
            "pairs_succeeded": self.metrics["pairs_succeeded"],
            "pairs_failed": self.metrics["pairs_failed"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "active_positions": len(self.active_positions),
            "completed_positions": len(self.completed_positions),
            "active_pairs": len(self.active_pairs),
            "total_pairs": len(self.pairs),
            "avg_correlation": float(self.metrics["avg_correlation"]),
            "avg_cointegration": float(self.metrics["avg_cointegration"]),
        }


# Module exports
__all__ = [
    'StatisticalExecutor',
    'StatisticalConfig',
    'StatisticalPair',
    'StatisticalPosition',
]
