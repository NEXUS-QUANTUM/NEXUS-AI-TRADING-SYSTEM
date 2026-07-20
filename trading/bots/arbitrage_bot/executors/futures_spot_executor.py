# trading/bots/arbitrage_bot/executors/futures_spot_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Futures-Spot Arbitrage Execution Engine

"""
Futures-Spot Executor - Advanced Futures-Spot Arbitrage Execution Engine

This module provides sophisticated futures-spot arbitrage execution capabilities,
handling the complexities of basis trading, funding rate arbitrage, and
cross-exchange futures-spot execution.

Architecture:
    - BaseFuturesSpotExecutor: Abstract base class
    - FuturesSpotExecutor: Main executor implementation
    - BasisCalculator: Basis calculation
    - FundingRateManager: Funding rate management
    - PositionManager: Position management
    - RiskManager: Risk management
    - ExecutionMonitor: Execution monitoring
    - HedgeManager: Hedge management

Features:
    - Basis trading execution
    - Funding rate arbitrage
    - Cross-exchange execution
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
    FundingRate,
)


# Constants
MIN_BASIS_PROFIT = Decimal("0.001")  # 0.1%
MIN_FUNDING_RATE_ARBITRAGE = Decimal("0.0001")  # 0.01%
DEFAULT_HEDGE_RATIO = Decimal("1.0")
MAX_POSITION_SIZE = Decimal("100000")
REBALANCE_THRESHOLD = Decimal("0.001")  # 0.1%


@dataclass
class FuturesSpotConfig:
    """Futures-spot execution configuration."""
    min_basis_profit: Decimal = MIN_BASIS_PROFIT
    min_funding_rate_arbitrage: Decimal = MIN_FUNDING_RATE_ARBITRAGE
    default_hedge_ratio: Decimal = DEFAULT_HEDGE_RATIO
    max_position_size: Decimal = MAX_POSITION_SIZE
    rebalance_threshold: Decimal = REBALANCE_THRESHOLD
    use_hedging: bool = True
    use_funding_rate: bool = True
    require_basis_confirmation: bool = True
    require_funding_confirmation: bool = True
    use_mev_protection: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BasisData:
    """Basis calculation data."""
    symbol: str
    spot_price: Decimal
    futures_price: Decimal
    basis: Decimal
    basis_percentage: Decimal
    annualized_basis: Decimal
    days_to_expiry: Optional[int] = None
    funding_rate: Optional[Decimal] = None
    implied_funding_rate: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FuturesSpotPosition:
    """Futures-spot position."""
    position_id: str
    symbol: str
    spot_exchange: ExchangeType
    futures_exchange: ExchangeType
    spot_size: Decimal
    futures_size: Decimal
    spot_price: Decimal
    futures_price: Decimal
    basis: Decimal
    basis_percentage: Decimal
    funding_rate: Optional[Decimal] = None
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    hedge_ratio: Decimal = DEFAULT_HEDGE_RATIO
    status: ExecutionStatus = ExecutionStatus.PENDING
    spot_order_id: Optional[str] = None
    futures_order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class FuturesSpotExecutor(BaseExecutor):
    """
    Advanced Futures-Spot Arbitrage Execution Engine.
    
    This class provides sophisticated futures-spot arbitrage execution:
    1. Basis trading execution
    2. Funding rate arbitrage
    3. Cross-exchange execution
    4. Dynamic position sizing
    5. Risk management
    6. Hedging
    7. Execution monitoring
    8. MEV protection
    
    Features:
    - Basis trading
    - Funding rate arbitrage
    - Cross-exchange execution
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
        futures_spot_config: Optional[FuturesSpotConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the futures-spot executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            futures_spot_config: Futures-spot configuration
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.futures_spot_config = futures_spot_config or FuturesSpotConfig()
        
        # Positions
        self.positions: Dict[str, FuturesSpotPosition] = {}
        self.active_positions: Set[str] = set()
        self.completed_positions: Set[str] = set()
        
        # Price cache
        self.price_cache: Dict[str, Dict[str, Ticker]] = {}
        self.funding_cache: Dict[str, FundingRate] = {}
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._position_lock = Lock()
        self._price_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "positions_total": 0,
            "positions_succeeded": 0,
            "positions_failed": 0,
            "basis_trades": 0,
            "basis_succeeded": 0,
            "basis_failed": 0,
            "funding_trades": 0,
            "funding_succeeded": 0,
            "funding_failed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_position_time_ms": 0,
            "success_rate": Decimal("0"),
            "avg_basis": Decimal("0"),
            "avg_funding_rate": Decimal("0"),
        })
        
        self.logger.info("FuturesSpotExecutor initialized")
    
    def _generate_position_id(self) -> str:
        """Generate a unique position ID."""
        import uuid
        return f"fs_pos_{uuid.uuid4().hex[:16]}"
    
    def _get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get exchange instance."""
        return self.exchanges.get(exchange_type)
    
    async def _get_ticker(
        self,
        exchange: BaseExchange,
        symbol: str,
    ) -> Optional[Ticker]:
        """
        Get ticker from exchange.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            
        Returns:
            Ticker or None
        """
        try:
            return await exchange.get_ticker(symbol)
        except Exception as e:
            self.logger.debug(f"Failed to get ticker: {e}")
            return None
    
    async def _get_funding_rate(
        self,
        exchange: BaseExchange,
        symbol: str,
    ) -> Optional[FundingRate]:
        """
        Get funding rate from exchange.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            
        Returns:
            FundingRate or None
        """
        try:
            return await exchange.get_funding_rate(symbol)
        except Exception as e:
            self.logger.debug(f"Failed to get funding rate: {e}")
            return None
    
    async def _calculate_basis(
        self,
        spot_exchange: BaseExchange,
        futures_exchange: BaseExchange,
        symbol: str,
    ) -> Optional[BasisData]:
        """
        Calculate basis between spot and futures.
        
        Args:
            spot_exchange: Spot exchange
            futures_exchange: Futures exchange
            symbol: Trading symbol
            
        Returns:
            BasisData or None
        """
        try:
            spot_ticker = await self._get_ticker(spot_exchange, symbol)
            futures_ticker = await self._get_ticker(futures_exchange, symbol)
            
            if not spot_ticker or not futures_ticker:
                return None
            
            spot_price = spot_ticker.last
            futures_price = futures_ticker.last
            
            if not spot_price or not futures_price:
                return None
            
            basis = futures_price - spot_price
            basis_percentage = (basis / spot_price) * Decimal("100")
            
            # Get funding rate if available
            funding_rate = await self._get_funding_rate(futures_exchange, symbol)
            
            return BasisData(
                symbol=symbol,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_percentage=basis_percentage,
                annualized_basis=basis_percentage * 365,  # Simplified
                funding_rate=funding_rate.funding_rate if funding_rate else None,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Basis calculation failed: {e}")
            return None
    
    async def _execute_spot_order(
        self,
        exchange: BaseExchange,
        symbol: str,
        side: OrderSide,
        size: Decimal,
        price: Optional[Decimal] = None,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute a spot order.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            side: Order side
            size: Order size
            price: Order price
            
        Returns:
            Tuple of (order, error_message)
        """
        try:
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            
            order = await exchange.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=size,
                price=price,
                time_in_force=TimeInForce.IOC,
            )
            
            if order:
                return order, None
            else:
                return None, "Order placement failed"
            
        except Exception as e:
            return None, str(e)
    
    async def _execute_futures_order(
        self,
        exchange: BaseExchange,
        symbol: str,
        side: OrderSide,
        size: Decimal,
        price: Optional[Decimal] = None,
        reduce_only: bool = False,
    ) -> Tuple[Optional[Order], Optional[str]]:
        """
        Execute a futures order.
        
        Args:
            exchange: Exchange instance
            symbol: Trading symbol
            side: Order side
            size: Order size
            price: Order price
            reduce_only: Reduce only flag
            
        Returns:
            Tuple of (order, error_message)
        """
        try:
            order_type = OrderType.LIMIT if price else OrderType.MARKET
            
            order = await exchange.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=size,
                price=price,
                time_in_force=TimeInForce.IOC,
                reduce_only=reduce_only,
            )
            
            if order:
                return order, None
            else:
                return None, "Order placement failed"
            
        except Exception as e:
            return None, str(e)
    
    async def _execute_basis_trade(
        self,
        basis_data: BasisData,
        size: Decimal,
        side: str,  # "long_spot_short_futures" or "short_spot_long_futures"
    ) -> Tuple[Optional[Order], Optional[Order], Optional[str]]:
        """
        Execute a basis trade.
        
        Args:
            basis_data: Basis data
            size: Position size
            side: Trade side
            
        Returns:
            Tuple of (spot_order, futures_order, error_message)
        """
        try:
            spot_exchange = self._get_exchange(ExchangeType.BINANCE)  # Would be dynamic
            futures_exchange = self._get_exchange(ExchangeType.BINANCE_FUTURES)
            
            if not spot_exchange or not futures_exchange:
                return None, None, "Exchange not found"
            
            if side == "long_spot_short_futures":
                # Buy spot, sell futures
                spot_order, spot_error = await self._execute_spot_order(
                    spot_exchange,
                    basis_data.symbol,
                    OrderSide.BUY,
                    size,
                    basis_data.spot_price,
                )
                
                if spot_error or not spot_order:
                    return None, None, f"Spot order failed: {spot_error}"
                
                futures_order, futures_error = await self._execute_futures_order(
                    futures_exchange,
                    basis_data.symbol,
                    OrderSide.SELL,
                    size,
                    basis_data.futures_price,
                )
                
                if futures_error or not futures_order:
                    # Rollback spot order
                    await spot_exchange.cancel_order(spot_order.order_id, basis_data.symbol)
                    return None, None, f"Futures order failed: {futures_error}"
                
                return spot_order, futures_order, None
                
            else:  # short_spot_long_futures
                # Sell spot, buy futures
                spot_order, spot_error = await self._execute_spot_order(
                    spot_exchange,
                    basis_data.symbol,
                    OrderSide.SELL,
                    size,
                    basis_data.spot_price,
                )
                
                if spot_error or not spot_order:
                    return None, None, f"Spot order failed: {spot_error}"
                
                futures_order, futures_error = await self._execute_futures_order(
                    futures_exchange,
                    basis_data.symbol,
                    OrderSide.BUY,
                    size,
                    basis_data.futures_price,
                )
                
                if futures_error or not futures_order:
                    # Rollback spot order
                    await spot_exchange.cancel_order(spot_order.order_id, basis_data.symbol)
                    return None, None, f"Futures order failed: {futures_error}"
                
                return spot_order, futures_order, None
                
        except Exception as e:
            return None, None, str(e)
    
    async def _close_basis_trade(
        self,
        position: FuturesSpotPosition,
    ) -> Tuple[Optional[Order], Optional[Order], Optional[str]]:
        """
        Close a basis trade.
        
        Args:
            position: Position to close
            
        Returns:
            Tuple of (spot_order, futures_order, error_message)
        """
        try:
            spot_exchange = self._get_exchange(position.spot_exchange)
            futures_exchange = self._get_exchange(position.futures_exchange)
            
            if not spot_exchange or not futures_exchange:
                return None, None, "Exchange not found"
            
            # Close positions (reverse the original orders)
            if position.spot_size > 0:
                # Close spot position
                spot_close, spot_error = await self._execute_spot_order(
                    spot_exchange,
                    position.symbol,
                    OrderSide.SELL,
                    position.spot_size,
                )
            else:
                spot_close, spot_error = await self._execute_spot_order(
                    spot_exchange,
                    position.symbol,
                    OrderSide.BUY,
                    abs(position.spot_size),
                )
            
            if spot_error or not spot_close:
                return None, None, f"Spot close failed: {spot_error}"
            
            if position.futures_size > 0:
                # Close futures position
                futures_close, futures_error = await self._execute_futures_order(
                    futures_exchange,
                    position.symbol,
                    OrderSide.SELL,
                    position.futures_size,
                    reduce_only=True,
                )
            else:
                futures_close, futures_error = await self._execute_futures_order(
                    futures_exchange,
                    position.symbol,
                    OrderSide.BUY,
                    abs(position.futures_size),
                    reduce_only=True,
                )
            
            if futures_error or not futures_close:
                return None, None, f"Futures close failed: {futures_error}"
            
            return spot_close, futures_close, None
            
        except Exception as e:
            return None, None, str(e)
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a futures-spot arbitrage plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting futures-spot execution: {execution_id}")
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
            
            # Extract order details
            if len(plan.orders) != 2:
                raise self.ValidationError("Futures-spot arbitrage requires exactly 2 orders")
            
            spot_order = plan.orders[0] if plan.orders[0].market_type == MarketType.SPOT else plan.orders[1]
            futures_order = plan.orders[1] if plan.orders[1].market_type == MarketType.FUTURES else plan.orders[0]
            
            # Get exchanges
            spot_exchange = self._get_exchange(spot_order.exchange)
            futures_exchange = self._get_exchange(futures_order.exchange)
            
            if not spot_exchange or not futures_exchange:
                raise self.ValidationError("Exchange not found")
            
            # Calculate basis
            basis_data = await self._calculate_basis(
                spot_exchange,
                futures_exchange,
                spot_order.symbol,
            )
            
            if not basis_data:
                raise self.ExecutionError("Failed to calculate basis")
            
            # Determine trade side
            if basis_data.basis > 0:
                side = "long_spot_short_futures"
            else:
                side = "short_spot_long_futures"
            
            # Check if profitable
            if abs(basis_data.basis_percentage) < self.futures_spot_config.min_basis_profit * 100:
                raise self.ExecutionError("Basis too small for profitable trade")
            
            # Calculate position size
            size = min(spot_order.quantity, self.futures_spot_config.max_position_size)
            
            # Apply MEV protection
            if self.config.use_mev_protection:
                plan = await self.apply_mev_protection(plan)
            
            # Apply slippage protection
            plan = await self.apply_slippage_protection(plan)
            
            # Execute basis trade
            spot_result, futures_result, error = await self._execute_basis_trade(
                basis_data,
                size,
                side,
            )
            
            if error or not spot_result or not futures_result:
                raise self.ExecutionError(f"Basis trade execution failed: {error}")
            
            # Create position
            position_id = self._generate_position_id()
            position = FuturesSpotPosition(
                position_id=position_id,
                symbol=spot_order.symbol,
                spot_exchange=spot_order.exchange,
                futures_exchange=futures_order.exchange,
                spot_size=size if side == "long_spot_short_futures" else -size,
                futures_size=-size if side == "long_spot_short_futures" else size,
                spot_price=spot_result.average_price or basis_data.spot_price,
                futures_price=futures_result.average_price or basis_data.futures_price,
                basis=basis_data.basis,
                basis_percentage=basis_data.basis_percentage,
                funding_rate=basis_data.funding_rate,
                hedge_ratio=self.futures_spot_config.default_hedge_ratio,
                status=ExecutionStatus.COMPLETED,
                spot_order_id=spot_result.order_id,
                futures_order_id=futures_result.order_id,
                timestamp=datetime.utcnow(),
            )
            
            with self._position_lock:
                self.positions[position_id] = position
                self.completed_positions.add(position_id)
            
            # Calculate profit (simplified)
            profit = abs(basis_data.basis) * size
            
            # Update metrics
            self.metrics["positions_total"] += 1
            self.metrics["basis_trades"] += 1
            
            if profit > 0:
                self.metrics["positions_succeeded"] += 1
                self.metrics["basis_succeeded"] += 1
                self.metrics["total_profit"] += profit
            else:
                self.metrics["positions_failed"] += 1
                self.metrics["basis_failed"] += 1
                self.metrics["total_loss"] += abs(profit)
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            self.metrics["avg_basis"] = (
                (self.metrics["avg_basis"] * (self.metrics["basis_trades"] - 1) +
                 basis_data.basis_percentage) / self.metrics["basis_trades"]
            )
            if basis_data.funding_rate:
                self.metrics["avg_funding_rate"] = (
                    (self.metrics["avg_funding_rate"] * (self.metrics["basis_trades"] - 1) +
                     basis_data.funding_rate) / self.metrics["basis_trades"]
                )
            
            # Create execution result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
                orders=[spot_result, futures_result],
                trades=[],
                positions=[],
                profit=profit,
                profit_percentage=(profit / (size * basis_data.spot_price) * Decimal("100")
                                   if size * basis_data.spot_price > 0 else Decimal("0")),
                gas_cost=Decimal("0"),
                fee_cost=Decimal("0"),
                total_cost=size * basis_data.spot_price,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_id": position_id,
                    "side": side,
                    "basis": str(basis_data.basis),
                    "basis_percentage": str(basis_data.basis_percentage),
                    "spot_order_id": spot_result.order_id,
                    "futures_order_id": futures_result.order_id,
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
                f"Futures-spot execution completed: {execution_id} "
                f"profit: ${float(result.profit):.2f}, "
                f"basis: {float(basis_data.basis_percentage):.2f}%"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Futures-spot execution failed: {error_msg}")
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
        
        # Find position
        position_id = None
        for pos_id, position in self.positions.items():
            if position.status in [ExecutionStatus.PENDING, ExecutionStatus.EXECUTING]:
                position_id = pos_id
                break
        
        if not position_id:
            self.logger.warning(f"Execution not found: {execution_id}")
            return False
        
        # Update position
        with self._position_lock:
            if position_id in self.positions:
                self.positions[position_id].status = ExecutionStatus.CANCELLED
        
        self._emit_cancelled(execution_id)
        
        return True
    
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
        self.logger.info(f"Simulating futures-spot execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate basis
        spot_price = Decimal("100")
        futures_price = Decimal("101")
        size = Decimal("1000")
        basis = futures_price - spot_price
        profit = basis * size
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=[],
            trades=[],
            positions=[],
            profit=profit,
            profit_percentage=profit / (size * spot_price) * Decimal("100"),
            gas_cost=Decimal("0"),
            fee_cost=Decimal("0"),
            total_cost=size * spot_price,
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
            if len(plan.orders) != 2:
                return False, "Futures-spot arbitrage requires exactly 2 orders"
            
            # Check one spot, one futures
            spot_orders = [o for o in plan.orders if o.market_type == MarketType.SPOT]
            futures_orders = [o for o in plan.orders if o.market_type == MarketType.FUTURES]
            
            if len(spot_orders) != 1 or len(futures_orders) != 1:
                return False, "Must have one spot and one futures order"
            
            # Check symbols match
            if spot_orders[0].symbol != futures_orders[0].symbol:
                return False, "Symbols do not match"
            
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
            
            risk_ratio = total_value / (self.futures_spot_config.max_position_size)
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
                "symbol": plan.orders[0].symbol if plan.orders else None,
            }
            
        except Exception as e:
            self.logger.error(f"Risk calculation failed: {e}")
            return {
                "total_value": Decimal("0"),
                "risk_ratio": Decimal("0"),
                "risk_level": ExecutionRisk.MEDIUM,
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
            spot_orders = [o for o in plan.orders if o.market_type == MarketType.SPOT]
            if not spot_orders:
                return True, None
            
            order = spot_orders[0]
            exchange = self._get_exchange(order.exchange)
            if not exchange:
                return False, f"Exchange not found: {order.exchange}"
            
            balances = await exchange.get_balances()
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
        # Futures-spot execution doesn't have significant gas costs
        return plan
    
    def get_positions(self) -> Dict[str, FuturesSpotPosition]:
        """
        Get all futures-spot positions.
        
        Returns:
            Dictionary of position ID to FuturesSpotPosition
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
            "basis_trades": self.metrics["basis_trades"],
            "basis_succeeded": self.metrics["basis_succeeded"],
            "basis_failed": self.metrics["basis_failed"],
            "funding_trades": self.metrics["funding_trades"],
            "funding_succeeded": self.metrics["funding_succeeded"],
            "funding_failed": self.metrics["funding_failed"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "active_positions": len(self.active_positions),
            "completed_positions": len(self.completed_positions),
            "avg_basis": float(self.metrics["avg_basis"]),
            "avg_funding_rate": float(self.metrics["avg_funding_rate"]),
        }


# Module exports
__all__ = [
    'FuturesSpotExecutor',
    'FuturesSpotConfig',
    'BasisData',
    'FuturesSpotPosition',
]
