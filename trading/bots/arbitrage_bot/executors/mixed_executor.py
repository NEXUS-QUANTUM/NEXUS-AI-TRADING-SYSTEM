# trading/bots/arbitrage_bot/executors/mixed_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Mixed Strategy Execution Engine

"""
Mixed Executor - Advanced Mixed Strategy Arbitrage Execution Engine

This module provides sophisticated mixed strategy execution capabilities,
combining multiple arbitrage strategies simultaneously for optimal results.

Architecture:
    - BaseMixedExecutor: Abstract base class
    - MixedExecutor: Main executor implementation
    - StrategyCombinator: Strategy combination logic
    - ExecutionCoordinator: Multi-strategy coordination
    - RiskAggregator: Aggregated risk management
    - PerformanceOptimizer: Performance optimization
    - ExecutionMonitor: Execution monitoring

Features:
    - Multi-strategy execution
    - Strategy combination
    - Coordinated execution
    - Aggregated risk management
    - Performance optimization
    - Execution monitoring
    - MEV protection
    - Slippage protection
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
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
)


# Constants
MIN_MIXED_PROFIT = Decimal("0.001")  # 0.1%
MAX_COMBINED_RISK = Decimal("0.5")  # 50%
MAX_CONCURRENT_STRATEGIES = 5
STRATEGY_TIMEOUT = 60  # seconds


@dataclass
class MixedConfig:
    """Mixed execution configuration."""
    min_profit: Decimal = MIN_MIXED_PROFIT
    max_combined_risk: Decimal = MAX_COMBINED_RISK
    max_concurrent_strategies: int = MAX_CONCURRENT_STRATEGIES
    strategy_timeout: int = STRATEGY_TIMEOUT
    require_all_strategies: bool = True
    parallel_execution: bool = True
    use_hedging: bool = True
    hedge_ratio: Decimal = Decimal("0.5")
    rebalance_threshold: Decimal = Decimal("0.001")
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyExecution:
    """Single strategy execution details."""
    strategy_id: str
    strategy_type: str
    execution_id: str
    orders: List[ExecutionOrder]
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[ExecutionResult] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MixedPosition:
    """Mixed strategy position."""
    position_id: str
    symbol: str
    strategies: List[str]
    total_size: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    combined_risk: Decimal = Decimal("0")
    hedge_ratio: Decimal = Decimal("0.5")
    status: ExecutionStatus = ExecutionStatus.PENDING
    sub_positions: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MixedExecutor(BaseExecutor):
    """
    Advanced Mixed Strategy Execution Engine.
    
    This class provides sophisticated mixed strategy execution:
    1. Multi-strategy execution
    2. Strategy combination
    3. Coordinated execution
    4. Aggregated risk management
    5. Performance optimization
    6. Execution monitoring
    7. MEV protection
    8. Slippage protection
    
    Features:
    - Multi-strategy execution
    - Strategy combination
    - Coordinated execution
    - Aggregated risk management
    - Performance optimization
    - Execution monitoring
    - MEV protection
    - Slippage protection
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        mixed_config: Optional[MixedConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the mixed executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            mixed_config: Mixed configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.mixed_config = mixed_config or MixedConfig()
        
        # Strategy tracking
        self.strategies: Dict[str, StrategyExecution] = {}
        self.active_strategies: Set[str] = set()
        self.completed_strategies: Set[str] = set()
        
        # Positions
        self.positions: Dict[str, MixedPosition] = {}
        self.active_positions: Set[str] = set()
        self.completed_positions: Set[str] = set()
        
        # Strategy executors
        self.strategy_executors: Dict[str, BaseExecutor] = {}
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._position_lock = Lock()
        self._strategy_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "positions_total": 0,
            "positions_succeeded": 0,
            "positions_failed": 0,
            "strategies_executed": 0,
            "strategies_succeeded": 0,
            "strategies_failed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_position_time_ms": 0,
            "success_rate": Decimal("0"),
            "combined_risk": Decimal("0"),
            "strategy_usage": defaultdict(int),
        })
        
        self.logger.info("MixedExecutor initialized")
    
    def _generate_position_id(self) -> str:
        """Generate a unique position ID."""
        import uuid
        return f"mixed_pos_{uuid.uuid4().hex[:16]}"
    
    def _generate_strategy_id(self) -> str:
        """Generate a unique strategy ID."""
        import uuid
        return f"strategy_{uuid.uuid4().hex[:12]}"
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _execute_single_strategy(
        self,
        strategy_id: str,
        strategy_type: str,
        orders: List[ExecutionOrder],
    ) -> Tuple[Optional[ExecutionResult], Optional[str]]:
        """
        Execute a single strategy.
        
        Args:
            strategy_id: Strategy ID
            strategy_type: Strategy type
            orders: Execution orders
            
        Returns:
            Tuple of (result, error_message)
        """
        try:
            # Create execution plan for strategy
            plan = ExecutionPlan(
                execution_id=strategy_id,
                execution_type=ExecutionType.ATOMIC,
                orders=orders,
                config=self.config,
                priority=ExecutionPriority.HIGH,
                risk_level=ExecutionRisk.MEDIUM,
                required_balance=Decimal("0"),
                max_loss=Decimal("0"),
                deadline=datetime.utcnow() + timedelta(seconds=60),
            )
            
            # Find appropriate executor
            from .executor_factory import ExecutorFactory, ExecutorCreationParams
            
            params = ExecutorCreationParams(
                executor_type=strategy_type,
                execution_config=self.config.__dict__,
                exchanges=self.exchanges,
                private_key=None,
                web3_provider=None,
                extra_params={},
            )
            
            executor = ExecutorFactory.create_executor(params)
            if not executor:
                return None, f"No executor found for strategy: {strategy_type}"
            
            # Execute strategy
            result = await executor.execute(plan)
            
            if result.status == ExecutionStatus.COMPLETED:
                return result, None
            else:
                return None, result.error or "Strategy execution failed"
            
        except Exception as e:
            return None, str(e)
    
    async def _combine_strategies(
        self,
        strategy_results: Dict[str, ExecutionResult],
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Combine multiple strategy results.
        
        Args:
            strategy_results: Dictionary of strategy results
            
        Returns:
            Tuple of (combined_result, error_message)
        """
        try:
            total_profit = Decimal("0")
            total_volume = Decimal("0")
            total_gas = Decimal("0")
            total_fees = Decimal("0")
            combined_orders = []
            
            for strategy_id, result in strategy_results.items():
                total_profit += result.profit
                total_volume += result.total_cost
                total_gas += result.gas_cost
                total_fees += result.fee_cost
                combined_orders.extend(result.orders)
            
            combined_risk = self._calculate_combined_risk(strategy_results)
            
            return {
                "total_profit": total_profit,
                "total_volume": total_volume,
                "total_gas": total_gas,
                "total_fees": total_fees,
                "combined_orders": combined_orders,
                "combined_risk": combined_risk,
            }, None
            
        except Exception as e:
            return {}, str(e)
    
    def _calculate_combined_risk(
        self,
        strategy_results: Dict[str, ExecutionResult],
    ) -> Decimal:
        """
        Calculate combined risk from multiple strategies.
        
        Args:
            strategy_results: Dictionary of strategy results
            
        Returns:
            Combined risk score
        """
        if not strategy_results:
            return Decimal("0")
        
        total_risk = Decimal("0")
        for result in strategy_results.values():
            risk = result.metadata.get("risk_level", 0.3)
            total_risk += Decimal(str(risk))
        
        avg_risk = total_risk / len(strategy_results)
        return min(avg_risk, self.mixed_config.max_combined_risk)
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a mixed strategy arbitrage plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting mixed execution: {execution_id}")
        self._emit_started(execution_id)
        
        try:
            # Validate execution plan
            is_valid, error = await self.validate_execution(plan)
            if not is_valid:
                raise self.ValidationError(f"Invalid execution plan: {error}")
            
            # Calculate risk
            risk_metrics = await self.calculate_risk(plan)
            if risk_metrics.get("risk_level", ExecutionRisk.MEDIUM) == ExecutionRisk.CRITICAL:
                raise self.RiskError("Risk level too high")
            
            # Group orders by strategy
            strategy_groups = self._group_orders_by_strategy(plan.orders)
            
            if len(strategy_groups) > self.mixed_config.max_concurrent_strategies:
                raise self.ExecutionError("Too many concurrent strategies")
            
            # Execute strategies
            strategy_results = {}
            strategy_errors = {}
            
            if self.mixed_config.parallel_execution:
                # Execute strategies in parallel
                tasks = []
                for strategy_id, (strategy_type, orders) in enumerate(strategy_groups.items()):
                    task = self._execute_single_strategy(
                        f"{execution_id}_{strategy_id}",
                        strategy_type,
                        orders,
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for i, result in enumerate(results):
                    strategy_id = f"{execution_id}_{i}"
                    if isinstance(result, Exception):
                        strategy_errors[strategy_id] = str(result)
                    elif isinstance(result, tuple):
                        exec_result, error = result
                        if exec_result:
                            strategy_results[strategy_id] = exec_result
                        elif error:
                            strategy_errors[strategy_id] = error
            else:
                # Execute strategies sequentially
                for strategy_id, (strategy_type, orders) in enumerate(strategy_groups.items()):
                    result, error = await self._execute_single_strategy(
                        f"{execution_id}_{strategy_id}",
                        strategy_type,
                        orders,
                    )
                    if result:
                        strategy_results[f"{execution_id}_{strategy_id}"] = result
                    elif error:
                        strategy_errors[f"{execution_id}_{strategy_id}"] = error
            
            # Check if all strategies succeeded
            if self.mixed_config.require_all_strategies and strategy_errors:
                raise self.ExecutionError(f"Some strategies failed: {strategy_errors}")
            
            # Combine results
            combined, error = await self._combine_strategies(strategy_results)
            if error:
                raise self.ExecutionError(f"Strategy combination failed: {error}")
            
            # Create position
            position_id = self._generate_position_id()
            position = MixedPosition(
                position_id=position_id,
                symbol=plan.orders[0].symbol if plan.orders else "MIXED",
                strategies=list(strategy_results.keys()),
                total_size=combined["total_volume"],
                avg_entry_price=Decimal("1"),  # Simplified
                current_price=Decimal("1"),  # Simplified
                realized_pnl=combined["total_profit"],
                combined_risk=combined["combined_risk"],
                hedge_ratio=self.mixed_config.hedge_ratio,
                status=ExecutionStatus.COMPLETED,
                sub_positions=[
                    {
                        "strategy_id": sid,
                        "profit": result.profit,
                        "orders": len(result.orders),
                    }
                    for sid, result in strategy_results.items()
                ],
                timestamp=datetime.utcnow(),
            )
            
            with self._position_lock:
                self.positions[position_id] = position
                self.completed_positions.add(position_id)
            
            # Update metrics
            self.metrics["positions_total"] += 1
            self.metrics["strategies_executed"] += len(strategy_results)
            self.metrics["combined_risk"] = (
                (self.metrics["combined_risk"] * (self.metrics["positions_total"] - 1) +
                 combined["combined_risk"]) / self.metrics["positions_total"]
            )
            
            for strategy_id in strategy_results:
                self.metrics["strategy_usage"][strategy_id.split("_")[-1]] += 1
            
            if combined["total_profit"] > 0:
                self.metrics["positions_succeeded"] += 1
                self.metrics["strategies_succeeded"] += len(strategy_results)
                self.metrics["total_profit"] += combined["total_profit"]
            else:
                self.metrics["positions_failed"] += 1
                self.metrics["strategies_failed"] += len(strategy_results)
                self.metrics["total_loss"] += abs(combined["total_profit"])
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            
            # Create execution result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
                orders=combined["combined_orders"],
                trades=[],
                positions=[],
                profit=combined["total_profit"],
                profit_percentage=(
                    combined["total_profit"] / combined["total_volume"] * Decimal("100")
                    if combined["total_volume"] > 0 else Decimal("0")
                ),
                gas_cost=combined["total_gas"],
                fee_cost=combined["total_fees"],
                total_cost=combined["total_volume"],
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_id": position_id,
                    "strategies_executed": len(strategy_results),
                    "strategies_succeeded": len([r for r in strategy_results.values() if r.status == ExecutionStatus.COMPLETED]),
                    "combined_risk": str(combined["combined_risk"]),
                    "strategy_results": {
                        sid: {
                            "profit": str(r.profit),
                            "orders": len(r.orders),
                            "status": r.status.value,
                        }
                        for sid, r in strategy_results.items()
                    },
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
                f"Mixed execution completed: {execution_id} "
                f"profit: ${float(result.profit):.2f}, "
                f"strategies: {len(strategy_results)}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Mixed execution failed: {error_msg}")
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
    
    def _group_orders_by_strategy(
        self,
        orders: List[ExecutionOrder],
    ) -> Dict[str, Tuple[str, List[ExecutionOrder]]]:
        """
        Group orders by strategy type.
        
        Args:
            orders: List of execution orders
            
        Returns:
            Dictionary mapping strategy IDs to (strategy_type, orders)
        """
        groups = defaultdict(list)
        
        for order in orders:
            strategy_type = order.extra_params.get("strategy_type", "default")
            groups[strategy_type].append(order)
        
        return {
            f"{i}_{self._generate_strategy_id()}": (strategy_type, order_list)
            for i, (strategy_type, order_list) in enumerate(groups.items())
        }
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel an execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if cancelled successfully
        """
        self.logger.info(f"Cancelling execution: {execution_id}")
        
        # Find active strategies for this execution
        cancelled = 0
        with self._strategy_lock:
            for strategy_id, strategy in self.strategies.items():
                if strategy.execution_id == execution_id and strategy.status in [
                    ExecutionStatus.PENDING,
                    ExecutionStatus.EXECUTING,
                ]:
                    strategy.status = ExecutionStatus.CANCELLED
                    cancelled += 1
        
        # Update position
        with self._position_lock:
            for pos_id, position in self.positions.items():
                if position.status in [ExecutionStatus.PENDING, ExecutionStatus.EXECUTING]:
                    position.status = ExecutionStatus.CANCELLED
                    break
        
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
        self.logger.info(f"Simulating mixed execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate mixed execution
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
            metadata={"simulated": True},
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
            
            # Check strategies
            strategy_types = set(
                o.extra_params.get("strategy_type", "default")
                for o in plan.orders
            )
            
            if len(strategy_types) > self.mixed_config.max_concurrent_strategies:
                return False, f"Too many strategy types: {len(strategy_types)}"
            
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
            strategy_types = set(o.extra_params.get("strategy_type", "default") for o in plan.orders)
            
            risk_ratio = total_value / (self.config.max_position_size or Decimal("100000"))
            if risk_ratio > Decimal("0.8") or len(strategy_types) > 3:
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
                "strategy_count": len(strategy_types),
                "strategy_types": list(strategy_types),
                "order_count": len(plan.orders),
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
                "strategy_count": 0,
                "strategy_types": [],
                "order_count": 0,
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
            # Optimize orders for each exchange
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
        # Group by symbol and side
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
    
    def get_positions(self) -> Dict[str, MixedPosition]:
        """
        Get all mixed positions.
        
        Returns:
            Dictionary of position ID to MixedPosition
        """
        with self._position_lock:
            return self.positions.copy()
    
    def get_active_positions(self) -> List[str]:
        """
        Get active position IDs.
        
        Returns:
            List of active position IDs
        """
        with self._position_lock:
            return list(self.active_positions)
    
    def get_completed_positions(self) -> List[str]:
        """
        Get completed position IDs.
        
        Returns:
            List of completed position IDs
        """
        with self._position_lock:
            return list(self.completed_positions)
    
    def get_strategy_usage(self) -> Dict[str, int]:
        """
        Get strategy usage statistics.
        
        Returns:
            Dictionary of strategy type to usage count
        """
        return dict(self.metrics["strategy_usage"])
    
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
            "strategies_executed": self.metrics["strategies_executed"],
            "strategies_succeeded": self.metrics["strategies_succeeded"],
            "strategies_failed": self.metrics["strategies_failed"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "active_positions": len(self.active_positions),
            "completed_positions": len(self.completed_positions),
            "combined_risk": float(self.metrics["combined_risk"]),
            "strategy_usage": dict(self.metrics["strategy_usage"]),
        }


# Module exports
__all__ = [
    'MixedExecutor',
    'MixedConfig',
    'StrategyExecution',
    'MixedPosition',
]
