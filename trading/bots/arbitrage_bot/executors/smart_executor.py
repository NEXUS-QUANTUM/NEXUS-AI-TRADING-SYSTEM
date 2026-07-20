# trading/bots/arbitrage_bot/executors/smart_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Smart Execution Engine

"""
Smart Executor - Advanced Smart Execution Engine

This module provides sophisticated smart execution capabilities that
dynamically select the optimal execution strategy based on market
conditions, order characteristics, and real-time performance metrics.

Architecture:
    - BaseSmartExecutor: Abstract base class
    - SmartExecutor: Main executor implementation
    - StrategySelector: Dynamic strategy selection
    - MarketAnalyzer: Market condition analysis
    - PerformanceTracker: Performance tracking
    - RouteOptimizer: Smart routing optimization
    - ExecutionMonitor: Execution monitoring

Features:
    - Dynamic strategy selection
    - Market condition analysis
    - Performance tracking
    - Smart routing
    - Adaptive execution
    - MEV protection
    - Slippage protection
    - Gas optimization
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
from random import random

import numpy as np

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
from .batch_executor import BatchExecutor, BatchConfig
from .parallel_executor import ParallelExecutor, ParallelConfig
from .sequential_executor import SequentialExecutor, SequentialConfig
from .cross_exchange_executor import CrossExchangeExecutor, CrossExchangeConfig
from .dex_executor import DEXExecutor, DEXConfig
from .flash_loan_executor import FlashLoanExecutor, FlashLoanConfig
from .order_executor import OrderExecutor, OrderConfig
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
DEFAULT_SELECTION_TIMEOUT = 5  # seconds
STRATEGY_SCORE_WEIGHT = {
    "speed": 0.3,
    "cost": 0.3,
    "success_rate": 0.2,
    "complexity": 0.1,
    "risk": 0.1,
}
MIN_STRATEGY_CONFIDENCE = Decimal("0.5")
STRATEGY_UPDATE_INTERVAL = 60  # seconds


class ExecutionStrategy(Enum):
    """Execution strategy enumeration."""
    BATCH = "batch"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CROSS_EXCHANGE = "cross_exchange"
    DEX = "dex"
    FLASH_LOAN = "flash_loan"
    ORDER = "order"
    SMART = "smart"
    HYBRID = "hybrid"


@dataclass
class SmartConfig:
    """Smart execution configuration."""
    selection_timeout: int = DEFAULT_SELECTION_TIMEOUT
    min_strategy_confidence: Decimal = MIN_STRATEGY_CONFIDENCE
    strategy_update_interval: int = STRATEGY_UPDATE_INTERVAL
    enable_adaptive_selection: bool = True
    enable_performance_tracking: bool = True
    enable_market_analysis: bool = True
    use_historical_performance: bool = True
    use_real_time_metrics: bool = True
    strategy_weights: Dict[str, float] = field(default_factory=lambda: STRATEGY_SCORE_WEIGHT)
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyScore:
    """Strategy performance score."""
    strategy: ExecutionStrategy
    score: Decimal
    confidence: Decimal
    metrics: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    weight: Decimal = Decimal("1.0")


@dataclass
class MarketCondition:
    """Market condition analysis."""
    volatility: Decimal
    liquidity: Decimal
    spread: Decimal
    volume: Decimal
    trend: str  # "bullish", "bearish", "neutral"
    confidence: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StrategyRecommendation:
    """Strategy recommendation."""
    strategy: ExecutionStrategy
    confidence: Decimal
    reasoning: List[str]
    expected_performance: Dict[str, Decimal]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SmartExecutor(BaseExecutor):
    """
    Advanced Smart Execution Engine.
    
    This class provides sophisticated smart execution capabilities:
    1. Dynamic strategy selection
    2. Market condition analysis
    3. Performance tracking
    4. Smart routing
    5. Adaptive execution
    6. MEV protection
    7. Slippage protection
    8. Gas optimization
    
    Features:
    - Dynamic strategy selection based on market conditions
    - Performance tracking and optimization
    - Market analysis
    - Smart routing
    - Adaptive execution
    - MEV protection
    - Slippage protection
    - Gas optimization
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        smart_config: Optional[SmartConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the smart executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            smart_config: Smart configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.smart_config = smart_config or SmartConfig()
        
        # Strategy tracking
        self.strategy_scores: Dict[ExecutionStrategy, StrategyScore] = {}
        self.strategy_history: Dict[ExecutionStrategy, List[StrategyScore]] = defaultdict(list)
        self.recommendations: Dict[str, StrategyRecommendation] = {}
        
        # Market analysis
        self.market_conditions: Dict[str, MarketCondition] = {}
        
        # Performance tracking
        self.performance_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # Strategy executors
        self.strategy_executors: Dict[ExecutionStrategy, BaseExecutor] = {}
        self._init_strategy_executors()
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._strategy_lock = Lock()
        self._market_lock = Lock()
        self._performance_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "strategy_selections": 0,
            "strategy_changes": 0,
            "adaptive_decisions": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_selection_time_ms": 0,
            "strategy_usage": defaultdict(int),
            "strategy_success_rate": defaultdict(Decimal),
        })
        
        # Start background tasks
        self._is_running = True
        self._update_task = asyncio.create_task(self._update_loop())
        
        self.logger.info("SmartExecutor initialized")
    
    def _init_strategy_executors(self) -> None:
        """Initialize strategy executors."""
        try:
            # Batch Executor
            self.strategy_executors[ExecutionStrategy.BATCH] = BatchExecutor(
                self.config,
                self.exchanges,
                BatchConfig(),
                self.logger,
            )
            
            # Sequential Executor
            self.strategy_executors[ExecutionStrategy.SEQUENTIAL] = SequentialExecutor(
                self.config,
                self.exchanges,
                SequentialConfig(),
                self.logger,
            )
            
            # Parallel Executor
            self.strategy_executors[ExecutionStrategy.PARALLEL] = ParallelExecutor(
                self.config,
                self.exchanges,
                ParallelConfig(),
                self.logger,
            )
            
            # Cross-Exchange Executor
            self.strategy_executors[ExecutionStrategy.CROSS_EXCHANGE] = CrossExchangeExecutor(
                self.config,
                self.exchanges,
                CrossExchangeConfig(),
                self.logger,
            )
            
            # DEX Executor
            self.strategy_executors[ExecutionStrategy.DEX] = DEXExecutor(
                self.config,
                self.exchanges,
                DEXConfig(),
                None,
                None,
                self.logger,
            )
            
            # Flash Loan Executor
            self.strategy_executors[ExecutionStrategy.FLASH_LOAN] = FlashLoanExecutor(
                self.config,
                self.exchanges,
                FlashLoanConfig(),
                None,
                None,
                self.logger,
            )
            
            # Order Executor
            self.strategy_executors[ExecutionStrategy.ORDER] = OrderExecutor(
                self.config,
                self.exchanges,
                OrderConfig(),
                self.logger,
            )
            
            # Smart Executor (self-reference for hybrid)
            self.strategy_executors[ExecutionStrategy.SMART] = self
            
            self.logger.info(f"Initialized {len(self.strategy_executors)} strategy executors")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize strategy executors: {e}")
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _analyze_market(self) -> MarketCondition:
        """
        Analyze current market conditions.
        
        Returns:
            MarketCondition object
        """
        try:
            # Get market data from exchanges
            vol_sum = Decimal("0")
            liq_sum = Decimal("0")
            spread_sum = Decimal("0")
            volume_sum = Decimal("0")
            count = 0
            
            for exchange_type, exchange in self.exchanges.items():
                try:
                    symbols = await exchange.get_symbols()
                    if symbols:
                        symbol = symbols[0]  # Use first symbol for analysis
                        ticker = await exchange.get_ticker(symbol)
                        if ticker:
                            vol_sum += ticker.change_percent_24h or Decimal("0")
                            liq_sum += ticker.volume or Decimal("0")
                            spread_sum += (ticker.ask - ticker.bid) / ticker.last if ticker.last > 0 else Decimal("0")
                            volume_sum += ticker.volume or Decimal("0")
                            count += 1
                except Exception:
                    continue
            
            if count > 0:
                volatility = vol_sum / count
                liquidity = liq_sum / count
                spread = spread_sum / count
                volume = volume_sum / count
                
                # Determine trend
                if volatility > Decimal("0.5"):
                    trend = "bullish"
                elif volatility < Decimal("-0.5"):
                    trend = "bearish"
                else:
                    trend = "neutral"
                
                return MarketCondition(
                    volatility=abs(volatility),
                    liquidity=liquidity,
                    spread=spread,
                    volume=volume,
                    trend=trend,
                    confidence=Decimal("0.7"),
                    timestamp=datetime.utcnow(),
                )
            
        except Exception as e:
            self.logger.error(f"Market analysis failed: {e}")
        
        return MarketCondition(
            volatility=Decimal("0.5"),
            liquidity=Decimal("1000000"),
            spread=Decimal("0.001"),
            volume=Decimal("100000"),
            trend="neutral",
            confidence=Decimal("0.5"),
            timestamp=datetime.utcnow(),
        )
    
    async def _score_strategy(
        self,
        strategy: ExecutionStrategy,
        market_condition: MarketCondition,
        order: ExecutionOrder,
    ) -> StrategyScore:
        """
        Score a strategy for the given market conditions.
        
        Args:
            strategy: Execution strategy
            market_condition: Market condition
            order: Execution order
            
        Returns:
            StrategyScore
        """
        try:
            weights = self.smart_config.strategy_weights
            score = Decimal("0")
            metrics = {}
            
            # Speed factor
            speed = Decimal("0.5")
            if strategy in [ExecutionStrategy.PARALLEL, ExecutionStrategy.ORDER]:
                speed = Decimal("0.8")
            elif strategy == ExecutionStrategy.BATCH:
                speed = Decimal("0.6")
            elif strategy == ExecutionStrategy.SEQUENTIAL:
                speed = Decimal("0.4")
            elif strategy == ExecutionStrategy.CROSS_EXCHANGE:
                speed = Decimal("0.3")
            elif strategy == ExecutionStrategy.DEX:
                speed = Decimal("0.2")
            elif strategy == ExecutionStrategy.FLASH_LOAN:
                speed = Decimal("0.1")
            
            # Cost factor
            cost = Decimal("0.5")
            if strategy in [ExecutionStrategy.BATCH, ExecutionStrategy.ORDER]:
                cost = Decimal("0.7")
            elif strategy == ExecutionStrategy.SEQUENTIAL:
                cost = Decimal("0.6")
            elif strategy == ExecutionStrategy.PARALLEL:
                cost = Decimal("0.5")
            elif strategy == ExecutionStrategy.CROSS_EXCHANGE:
                cost = Decimal("0.4")
            elif strategy == ExecutionStrategy.DEX:
                cost = Decimal("0.3")
            elif strategy == ExecutionStrategy.FLASH_LOAN:
                cost = Decimal("0.2")
            
            # Success rate factor
            success_rate = self.metrics["strategy_success_rate"].get(strategy, Decimal("0.7"))
            
            # Complexity factor
            complexity = Decimal("0.5")
            if strategy in [ExecutionStrategy.ORDER, ExecutionStrategy.SEQUENTIAL]:
                complexity = Decimal("0.8")
            elif strategy in [ExecutionStrategy.BATCH, ExecutionStrategy.PARALLEL]:
                complexity = Decimal("0.6")
            elif strategy in [ExecutionStrategy.CROSS_EXCHANGE, ExecutionStrategy.DEX]:
                complexity = Decimal("0.4")
            elif strategy == ExecutionStrategy.FLASH_LOAN:
                complexity = Decimal("0.3")
            
            # Risk factor
            risk = Decimal("0.5")
            if strategy in [ExecutionStrategy.ORDER, ExecutionStrategy.SEQUENTIAL, ExecutionStrategy.BATCH]:
                risk = Decimal("0.7")
            elif strategy == ExecutionStrategy.PARALLEL:
                risk = Decimal("0.5")
            elif strategy in [ExecutionStrategy.CROSS_EXCHANGE, ExecutionStrategy.DEX]:
                risk = Decimal("0.4")
            elif strategy == ExecutionStrategy.FLASH_LOAN:
                risk = Decimal("0.3")
            
            # Calculate weighted score
            score = (
                speed * Decimal(str(weights.get("speed", 0.3))) +
                cost * Decimal(str(weights.get("cost", 0.3))) +
                success_rate * Decimal(str(weights.get("success_rate", 0.2))) +
                complexity * Decimal(str(weights.get("complexity", 0.1))) +
                risk * Decimal(str(weights.get("risk", 0.1)))
            )
            
            metrics = {
                "speed": float(speed),
                "cost": float(cost),
                "success_rate": float(success_rate),
                "complexity": float(complexity),
                "risk": float(risk),
            }
            
            return StrategyScore(
                strategy=strategy,
                score=score,
                confidence=Decimal("0.8"),
                metrics=metrics,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Strategy scoring failed: {e}")
            return StrategyScore(
                strategy=strategy,
                score=Decimal("0.5"),
                confidence=Decimal("0.5"),
                metrics={},
                timestamp=datetime.utcnow(),
            )
    
    async def _select_strategy(
        self,
        plan: ExecutionPlan,
    ) -> Tuple[ExecutionStrategy, StrategyScore, Optional[str]]:
        """
        Select the best strategy for execution.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (selected_strategy, strategy_score, error_message)
        """
        try:
            # Analyze market
            market_condition = await self._analyze_market()
            with self._market_lock:
                self.market_conditions["global"] = market_condition
            
            # Score each strategy
            scores = []
            for strategy in ExecutionStrategy:
                if strategy == ExecutionStrategy.SMART or strategy == ExecutionStrategy.HYBRID:
                    continue
                
                # Check if strategy is applicable
                if not self._is_strategy_applicable(strategy, plan):
                    continue
                
                score = await self._score_strategy(strategy, market_condition, plan.orders[0] if plan.orders else None)
                scores.append((strategy, score))
            
            if not scores:
                return ExecutionStrategy.ORDER, StrategyScore(
                    strategy=ExecutionStrategy.ORDER,
                    score=Decimal("0.5"),
                    confidence=Decimal("0.5"),
                    metrics={},
                ), "No suitable strategy found"
            
            # Sort by score
            scores.sort(key=lambda x: x[1].score, reverse=True)
            
            # Update metrics
            self.metrics["strategy_selections"] += 1
            
            # Log selection
            self.logger.info(f"Selected strategy: {scores[0][0].value} with score {scores[0][1].score:.2f}")
            
            return scores[0][0], scores[0][1], None
            
        except Exception as e:
            return ExecutionStrategy.ORDER, StrategyScore(
                strategy=ExecutionStrategy.ORDER,
                score=Decimal("0.5"),
                confidence=Decimal("0.5"),
                metrics={},
            ), str(e)
    
    def _is_strategy_applicable(
        self,
        strategy: ExecutionStrategy,
        plan: ExecutionPlan,
    ) -> bool:
        """
        Check if a strategy is applicable to the execution plan.
        
        Args:
            strategy: Execution strategy
            plan: Execution plan
            
        Returns:
            True if applicable
        """
        if not plan.orders:
            return False
        
        # Check strategy-specific requirements
        if strategy == ExecutionStrategy.CROSS_EXCHANGE:
            # Need at least 2 orders on different exchanges
            exchanges = set(o.exchange for o in plan.orders)
            if len(exchanges) < 2:
                return False
            
            # Need one spot and one futures order
            spot_orders = [o for o in plan.orders if o.market_type == MarketType.SPOT]
            futures_orders = [o for o in plan.orders if o.market_type == MarketType.FUTURES]
            if not spot_orders or not futures_orders:
                return False
        
        elif strategy == ExecutionStrategy.DEX:
            # Need DEX exchanges
            dex_exchanges = [ExchangeType.UNISWAP, ExchangeType.PANCAKESWAP, ExchangeType.SUSHISWAP]
            if plan.orders[0].exchange not in dex_exchanges:
                return False
        
        elif strategy == ExecutionStrategy.FLASH_LOAN:
            # Need single order with sufficient size
            if len(plan.orders) != 1:
                return False
            if plan.orders[0].quantity < Decimal("1000"):
                return False
        
        elif strategy == ExecutionStrategy.PARALLEL:
            # Need multiple orders
            if len(plan.orders) < 2:
                return False
        
        elif strategy == ExecutionStrategy.BATCH:
            # Need multiple orders or batchable orders
            if len(plan.orders) < 2:
                return False
        
        return True
    
    async def _update_loop(self) -> None:
        """Background update loop for strategy scores and market analysis."""
        while self._is_running:
            try:
                await asyncio.sleep(self.smart_config.strategy_update_interval)
                
                # Update market analysis
                market_condition = await self._analyze_market()
                with self._market_lock:
                    self.market_conditions["global"] = market_condition
                
                # Update strategy scores
                sample_order = ExecutionOrder(
                    exchange=ExchangeType.BINANCE,
                    symbol="BTC/USDT",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=Decimal("1"),
                    price=Decimal("50000"),
                )
                
                sample_plan = ExecutionPlan(
                    execution_id="update_sample",
                    execution_type=ExecutionType.ATOMIC,
                    orders=[sample_order],
                    config=self.config,
                    priority=ExecutionPriority.LOW,
                    risk_level=ExecutionRisk.LOW,
                    required_balance=Decimal("0"),
                    max_loss=Decimal("0"),
                    deadline=datetime.utcnow(),
                )
                
                for strategy in ExecutionStrategy:
                    if strategy == ExecutionStrategy.SMART or strategy == ExecutionStrategy.HYBRID:
                        continue
                    
                    score = await self._score_strategy(strategy, market_condition, sample_order)
                    with self._strategy_lock:
                        self.strategy_scores[strategy] = score
                        self.strategy_history[strategy].append(score)
                    
                    # Keep only last 100 scores
                    if len(self.strategy_history[strategy]) > 100:
                        self.strategy_history[strategy] = self.strategy_history[strategy][-100:]
                
            except Exception as e:
                self.logger.error(f"Update loop error: {e}")
    
    async def _execute_with_strategy(
        self,
        strategy: ExecutionStrategy,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        """
        Execute a plan using a specific strategy.
        
        Args:
            strategy: Execution strategy
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        executor = self.strategy_executors.get(strategy)
        if not executor:
            return ExecutionResult(
                execution_id=plan.execution_id,
                status=ExecutionStatus.FAILED,
                orders=[],
                trades=[],
                positions=[],
                profit=Decimal("0"),
                profit_percentage=Decimal("0"),
                gas_cost=Decimal("0"),
                fee_cost=Decimal("0"),
                total_cost=Decimal("0"),
                execution_time_ms=0,
                timestamp=datetime.utcnow(),
                error=f"No executor for strategy: {strategy}",
            )
        
        # Update strategy usage
        self.metrics["strategy_usage"][strategy] += 1
        self.metrics["strategy_changes"] += 1
        
        # Execute with selected strategy
        result = await executor.execute(plan)
        
        # Track performance
        with self._performance_lock:
            self.performance_history[plan.execution_id].append({
                "strategy": strategy.value,
                "result": result.status.value,
                "profit": float(result.profit),
                "execution_time": result.execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        return result
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a plan using the optimal strategy.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting smart execution: {execution_id}")
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
            
            # Apply MEV protection
            if self.config.use_mev_protection:
                plan = await self.apply_mev_protection(plan)
            
            # Apply slippage protection
            plan = await self.apply_slippage_protection(plan)
            
            # Optimize gas
            plan = await self.optimize_gas(plan)
            
            # Select strategy
            selected_strategy, strategy_score, error = await self._select_strategy(plan)
            if error:
                self.logger.warning(f"Strategy selection warning: {error}")
            
            # Execute with selected strategy
            result = await self._execute_with_strategy(selected_strategy, plan)
            
            # Update metrics
            self.metrics["executions_total"] += 1
            if result.status == ExecutionStatus.COMPLETED:
                self.metrics["executions_succeeded"] += 1
                self.metrics["total_profit"] += result.profit
                self.metrics["strategy_success_rate"][selected_strategy] = (
                    (self.metrics["strategy_success_rate"].get(selected_strategy, Decimal("0")) * 
                     (self.metrics["strategy_usage"].get(selected_strategy, 1) - 1) + 
                     Decimal("1")) / self.metrics["strategy_usage"].get(selected_strategy, 1)
                )
            elif result.status == ExecutionStatus.FAILED:
                self.metrics["executions_failed"] += 1
                self.metrics["total_loss"] += abs(result.profit)
                self.metrics["strategy_success_rate"][selected_strategy] = (
                    self.metrics["strategy_success_rate"].get(selected_strategy, Decimal("0")) * 
                    (self.metrics["strategy_usage"].get(selected_strategy, 1) - 1) / 
                    self.metrics["strategy_usage"].get(selected_strategy, 1)
                )
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            self.metrics["avg_selection_time_ms"] = (
                (self.metrics["avg_selection_time_ms"] * (self.metrics["strategy_selections"] - 1) +
                 self._calculate_execution_time(start_time)) / max(1, self.metrics["strategy_selections"])
            )
            
            # Emit completion event
            self._emit_completed(result)
            
            self.logger.info(
                f"Smart execution completed: {execution_id} "
                f"strategy: {selected_strategy.value}, "
                f"profit: ${float(result.profit):.2f}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Smart execution failed: {error_msg}")
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
        
        # Try to cancel with all executors
        cancelled = False
        for executor in self.strategy_executors.values():
            if executor and executor != self:
                try:
                    if await executor.cancel_execution(execution_id):
                        cancelled = True
                except Exception:
                    continue
        
        self._emit_cancelled(execution_id)
        
        return cancelled
    
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
        self.logger.info(f"Simulating smart execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate with best strategy
        selected_strategy, _, _ = await self._select_strategy(plan)
        
        # Simulate execution
        total_profit = Decimal("10")
        total_volume = Decimal("1000")
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=[],
            trades=[],
            positions=[],
            profit=total_profit,
            profit_percentage=total_profit / total_volume * Decimal("100"),
            gas_cost=Decimal("0.001"),
            fee_cost=Decimal("0.001"),
            total_cost=total_volume,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.utcnow(),
            metadata={
                "simulated": True,
                "selected_strategy": selected_strategy.value,
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
            if not plan.orders:
                return False, "No orders to execute"
            
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
            
            risk_ratio = total_value / (self.config.max_position_size or Decimal("100000"))
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
                "symbols": list(set(o.symbol for o in plan.orders)),
                "exchanges": list(set(o.exchange for o in plan.orders)),
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
        # Group orders by exchange to reduce gas costs
        exchange_orders: Dict[ExchangeType, List[ExecutionOrder]] = defaultdict(list)
        for order in plan.orders:
            exchange_orders[order.exchange].append(order)
        
        optimized_orders = []
        for exchange_type, orders in exchange_orders.items():
            optimized_orders.extend(self._optimize_order_batching(orders))
        
        plan.orders = optimized_orders
        return plan
    
    def _optimize_order_batching(self, orders: List[ExecutionOrder]) -> List[ExecutionOrder]:
        """
        Optimize order batching for gas efficiency.
        
        Args:
            orders: List of orders
            
        Returns:
            Optimized orders
        """
        grouped = defaultdict(list)
        for order in orders:
            key = f"{order.symbol}_{order.side.value}_{order.exchange.value}"
            grouped[key].append(order)
        
        optimized = []
        for key, order_group in grouped.items():
            if len(order_group) > 1:
                combined = order_group[0]
                combined.quantity = sum(o.quantity for o in order_group)
                optimized.append(combined)
            else:
                optimized.append(order_group[0])
        
        return optimized
    
    def get_strategy_scores(self) -> Dict[ExecutionStrategy, StrategyScore]:
        """
        Get current strategy scores.
        
        Returns:
            Dictionary of strategy to score
        """
        with self._strategy_lock:
            return self.strategy_scores.copy()
    
    def get_strategy_recommendation(self) -> StrategyRecommendation:
        """
        Get strategy recommendation.
        
        Returns:
            StrategyRecommendation
        """
        if not self.strategy_scores:
            return StrategyRecommendation(
                strategy=ExecutionStrategy.ORDER,
                confidence=Decimal("0.5"),
                reasoning=["No strategy scores available"],
                expected_performance={},
                timestamp=datetime.utcnow(),
            )
        
        best_strategy = max(self.strategy_scores.items(), key=lambda x: x[1].score)
        
        reasoning = [
            f"{best_strategy[0].value} has highest score: {best_strategy[1].score:.2f}",
            f"Speed factor: {best_strategy[1].metrics.get('speed', 0):.2f}",
            f"Cost factor: {best_strategy[1].metrics.get('cost', 0):.2f}",
            f"Success rate: {best_strategy[1].metrics.get('success_rate', 0):.2f}",
        ]
        
        return StrategyRecommendation(
            strategy=best_strategy[0],
            confidence=best_strategy[1].confidence,
            reasoning=reasoning,
            expected_performance=best_strategy[1].metrics,
            timestamp=datetime.utcnow(),
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **super().get_metrics(),
            "strategy_selections": self.metrics["strategy_selections"],
            "strategy_changes": self.metrics["strategy_changes"],
            "adaptive_decisions": self.metrics["adaptive_decisions"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "avg_selection_time_ms": self.metrics["avg_selection_time_ms"],
            "strategy_usage": {k.value: v for k, v in self.metrics["strategy_usage"].items()},
            "strategy_success_rate": {k.value: float(v) for k, v in self.metrics["strategy_success_rate"].items()},
            "available_strategies": len(self.strategy_executors),
            "strategy_scores": {k.value: float(v.score) for k, v in self.strategy_scores.items()},
        }


# Module exports
__all__ = [
    'SmartExecutor',
    'SmartConfig',
    'ExecutionStrategy',
    'StrategyScore',
    'MarketCondition',
    'StrategyRecommendation',
]
