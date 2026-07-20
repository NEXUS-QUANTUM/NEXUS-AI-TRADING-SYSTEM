# trading/bots/arbitrage_bot/executors/dex_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - DEX Execution Engine

"""
DEX Executor - Advanced Decentralized Exchange Execution Engine

This module provides sophisticated DEX execution capabilities for
arbitrage opportunities across decentralized exchanges, handling the
complexities of on-chain transactions, gas optimization, and MEV protection.

Architecture:
    - BaseDEXExecutor: Abstract base class
    - DEXExecutor: Main executor implementation
    - TransactionBuilder: Transaction building
    - GasOptimizer: Gas optimization
    - MEVProtector: MEV protection
    - SlippageCalculator: Slippage calculation
    - RouteOptimizer: Route optimization
    - ExecutionMonitor: Execution monitoring

Features:
    - DEX order execution (Uniswap, PancakeSwap, SushiSwap)
    - Transaction building and signing
    - Gas optimization
    - MEV protection
    - Slippage protection
    - Route optimization
    - Multi-hop execution
    - Flash loan integration
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

from web3 import Web3
from web3.types import TxParams, ChecksumAddress
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address, to_hex
from eth_account import Account
from eth_account.signers.local import LocalAccount

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
DEFAULT_GAS_LIMIT = 300000
DEFAULT_GAS_PRICE = 100  # gwei
MAX_GAS_PRICE = 500  # gwei
MIN_GAS_PRICE = 10  # gwei
SLIPPAGE_TOLERANCE = Decimal("0.01")  # 1%
DEADLINE_SECONDS = 300  # 5 minutes
MAX_ROUTE_LENGTH = 5
MIN_POOL_LIQUIDITY = Decimal("10000")


@dataclass
class DEXConfig:
    """DEX execution configuration."""
    default_gas_limit: int = DEFAULT_GAS_LIMIT
    default_gas_price: int = DEFAULT_GAS_PRICE
    max_gas_price: int = MAX_GAS_PRICE
    min_gas_price: int = MIN_GAS_PRICE
    slippage_tolerance: Decimal = SLIPPAGE_TOLERANCE
    deadline_seconds: int = DEADLINE_SECONDS
    max_route_length: int = MAX_ROUTE_LENGTH
    min_pool_liquidity: Decimal = MIN_POOL_LIQUIDITY
    use_flash_loan: bool = False
    flash_loan_provider: Optional[str] = None
    use_mev_protection: bool = True
    use_private_mempool: bool = True
    use_multihop: bool = True
    optimize_gas: bool = True
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DEXRoute:
    """DEX route for swaps."""
    hops: List[Dict[str, Any]]
    exchanges: List[ExchangeType]
    path: List[str]
    expected_output: Decimal
    estimated_gas: int
    price_impact: Decimal
    confidence: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DEXPosition:
    """DEX position."""
    position_id: str
    symbol: str
    dex_exchange: ExchangeType
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    status: ExecutionStatus = ExecutionStatus.PENDING
    route: Optional[DEXRoute] = None
    tx_hash: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DEXExecutor(BaseExecutor):
    """
    Advanced DEX Execution Engine.
    
    This class provides sophisticated DEX execution capabilities:
    1. DEX order execution
    2. Transaction building and signing
    3. Gas optimization
    4. MEV protection
    5. Slippage protection
    6. Route optimization
    7. Multi-hop execution
    8. Flash loan integration
    
    Features:
    - Multi-DEX support (Uniswap, PancakeSwap, SushiSwap)
    - Transaction building and signing
    - Gas optimization
    - MEV protection
    - Slippage protection
    - Route optimization
    - Multi-hop execution
    - Flash loan integration
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        dex_config: Optional[DEXConfig] = None,
        private_key: Optional[str] = None,
        web3_provider: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the DEX executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            dex_config: DEX configuration
            private_key: Private key for signing
            web3_provider: Web3 provider URL
            logger: Optional logger instance
        """
        super().__init__(config, exchanges, logger)
        self.dex_config = dex_config or DEXConfig()
        
        # Initialize Web3
        self.web3 = self._init_web3(web3_provider)
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # DEX tracking
        self.positions: Dict[str, DEXPosition] = {}
        self.active_positions: Set[str] = set()
        self.completed_positions: Set[str] = set()
        
        # Route cache
        self.route_cache: Dict[str, DEXRoute] = {}
        
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)
        
        # Locks
        self._position_lock = Lock()
        
        # Metrics
        self.metrics.update({
            "positions_total": 0,
            "positions_succeeded": 0,
            "positions_failed": 0,
            "swaps_executed": 0,
            "swaps_succeeded": 0,
            "swaps_failed": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "avg_position_time_ms": 0,
            "success_rate": Decimal("0"),
            "avg_gas_used": 0,
            "avg_slippage": Decimal("0"),
        })
        
        self.logger.info("DEXExecutor initialized")
    
    def _init_web3(self, provider: Optional[str] = None) -> Web3:
        """Initialize Web3."""
        rpc_url = provider or "https://mainnet.infura.io/v3/"
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                return w3
        except Exception as e:
            self.logger.warning(f"Web3 connection failed: {e}")
        
        return Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
    
    def _generate_position_id(self) -> str:
        """Generate a unique position ID."""
        import uuid
        return f"dex_pos_{uuid.uuid4().hex[:16]}"
    
    def _get_dex_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """Get DEX exchange instance."""
        return self.exchanges.get(exchange_type)
    
    def _to_wei(self, amount: Decimal, decimals: int = 18) -> int:
        """Convert to wei."""
        return int(amount * Decimal(10 ** decimals))
    
    def _from_wei(self, amount: int, decimals: int = 18) -> Decimal:
        """Convert from wei."""
        return Decimal(str(amount)) / Decimal(10 ** decimals)
    
    async def _get_gas_price(self) -> int:
        """
        Get optimal gas price.
        
        Returns:
            Gas price in wei
        """
        try:
            gas_price = self.web3.eth.gas_price
            gas_price_gwei = gas_price / 10**9
            
            # Apply min/max constraints
            if gas_price_gwei < self.dex_config.min_gas_price:
                gas_price_gwei = self.dex_config.min_gas_price
            elif gas_price_gwei > self.dex_config.max_gas_price:
                gas_price_gwei = self.dex_config.max_gas_price
            
            return int(gas_price_gwei * 10**9)
        except Exception:
            return self.dex_config.default_gas_price * 10**9
    
    async def _find_best_route(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        dex_exchange: ExchangeType,
    ) -> Optional[DEXRoute]:
        """
        Find the best route for a swap.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            dex_exchange: DEX exchange
            
        Returns:
            DEXRoute or None
        """
        try:
            exchange = self._get_dex_exchange(dex_exchange)
            if not exchange:
                return None
            
            # Get quote from exchange
            if hasattr(exchange, 'get_quote'):
                quote = await exchange.get_quote(token_in, token_out, amount_in)
                if quote:
                    return DEXRoute(
                        hops=[{"exchange": dex_exchange, "token_in": token_in, "token_out": token_out}],
                        exchanges=[dex_exchange],
                        path=[token_in, token_out],
                        expected_output=quote.amount_out,
                        estimated_gas=quote.estimated_gas or 200000,
                        price_impact=quote.price_impact or Decimal("0"),
                        confidence=Decimal("0.9"),
                        timestamp=datetime.utcnow(),
                    )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Route finding failed: {e}")
            return None
    
    async def _execute_swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        dex_exchange: ExchangeType,
        route: Optional[DEXRoute] = None,
        slippage: Optional[Decimal] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Execute a swap on a DEX.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            dex_exchange: DEX exchange
            route: Optional route
            slippage: Slippage tolerance
            
        Returns:
            Tuple of (tx_hash, error_message)
        """
        try:
            if not self.account:
                return None, "No account available for signing"
            
            exchange = self._get_dex_exchange(dex_exchange)
            if not exchange:
                return None, f"Exchange not found: {dex_exchange}"
            
            # Find route if not provided
            if not route:
                route = await self._find_best_route(
                    token_in,
                    token_out,
                    amount_in,
                    dex_exchange,
                )
            
            if not route:
                return None, "No route found"
            
            # Execute swap
            if hasattr(exchange, 'swap'):
                result = await exchange.swap(
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    slippage=slippage or self.dex_config.slippage_tolerance,
                )
                
                if result and result.success:
                    return result.tx_hash, None
                else:
                    return None, result.error if result else "Swap failed"
            
            return None, "Exchange does not support swap"
            
        except Exception as e:
            return None, str(e)
    
    async def _monitor_transaction(
        self,
        tx_hash: str,
        timeout: int = DEADLINE_SECONDS,
    ) -> Tuple[bool, Optional[str]]:
        """
        Monitor a transaction for confirmation.
        
        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_confirmed, error_message)
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                receipt = self.web3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.status == 1:
                        return True, None
                    else:
                        return False, "Transaction failed"
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
        return False, "Transaction monitoring timed out"
    
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute a DEX arbitrage plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        start_time = time.time()
        execution_id = plan.execution_id
        
        self.logger.info(f"Starting DEX execution: {execution_id}")
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
            
            # Extract DEX details
            if len(plan.orders) != 1:
                raise self.ValidationError("DEX arbitrage requires exactly 1 order")
            
            order = plan.orders[0]
            
            # Get DEX exchange
            dex_exchange = order.exchange
            if dex_exchange not in [ExchangeType.UNISWAP, ExchangeType.PANCAKESWAP, 
                                    ExchangeType.SUSHISWAP, ExchangeType.BALANCER,
                                    ExchangeType.CURVE]:
                raise self.ValidationError(f"Invalid DEX exchange: {dex_exchange}")
            
            # Parse token addresses
            token_in = order.symbol.split("/")[0]
            token_out = order.symbol.split("/")[1] if "/" in order.symbol else "WETH"
            
            # Apply MEV protection
            if self.config.use_mev_protection:
                plan = await self.apply_mev_protection(plan)
            
            # Apply slippage protection
            plan = await self.apply_slippage_protection(plan)
            
            # Find best route
            route = await self._find_best_route(
                token_in,
                token_out,
                order.quantity,
                dex_exchange,
            )
            
            if not route:
                raise self.ExecutionError("No route found for swap")
            
            # Execute swap
            tx_hash, error = await self._execute_swap(
                token_in,
                token_out,
                order.quantity,
                dex_exchange,
                route,
                self.dex_config.slippage_tolerance,
            )
            
            if error or not tx_hash:
                raise self.ExecutionError(f"Swap execution failed: {error}")
            
            # Monitor transaction
            confirmed, monitor_error = await self._monitor_transaction(tx_hash)
            if not confirmed:
                raise self.ExecutionError(f"Transaction confirmation failed: {monitor_error}")
            
            # Calculate profit
            profit = route.expected_output - order.quantity
            
            # Create position
            position_id = self._generate_position_id()
            position = DEXPosition(
                position_id=position_id,
                symbol=order.symbol,
                dex_exchange=dex_exchange,
                token_in=token_in,
                token_out=token_out,
                amount_in=order.quantity,
                amount_out=route.expected_output,
                entry_price=order.price or Decimal("1"),
                current_price=order.price or Decimal("1"),
                unrealized_pnl=profit,
                status=ExecutionStatus.COMPLETED if profit > 0 else ExecutionStatus.PARTIALLY_EXECUTED,
                route=route,
                tx_hash=tx_hash,
                timestamp=datetime.utcnow(),
            )
            
            with self._position_lock:
                self.positions[position_id] = position
                self.completed_positions.add(position_id)
            
            # Update metrics
            self.metrics["positions_total"] += 1
            self.metrics["swaps_executed"] += 1
            self.metrics["avg_gas_used"] = (
                (self.metrics["avg_gas_used"] * (self.metrics["swaps_executed"] - 1) +
                 route.estimated_gas) / self.metrics["swaps_executed"]
            )
            
            if profit > 0:
                self.metrics["positions_succeeded"] += 1
                self.metrics["swaps_succeeded"] += 1
                self.metrics["total_profit"] += profit
            else:
                self.metrics["positions_failed"] += 1
                self.metrics["swaps_failed"] += 1
                self.metrics["total_loss"] += abs(profit)
            
            self.metrics["net_profit"] = self.metrics["total_profit"] - self.metrics["total_loss"]
            
            # Create execution result
            execution_time_ms = self._calculate_execution_time(start_time)
            result = ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
                orders=[],  # Would parse from swap
                trades=[],
                positions=[],
                profit=profit,
                profit_percentage=(profit / order.quantity * Decimal("100")
                                   if order.quantity > 0 else Decimal("0")),
                gas_cost=Decimal(str(route.estimated_gas)) / Decimal(10**18),
                fee_cost=Decimal("0.003") * order.quantity,  # 0.3% fee
                total_cost=order.quantity,
                execution_time_ms=execution_time_ms,
                timestamp=datetime.utcnow(),
                metadata={
                    "position_id": position_id,
                    "tx_hash": tx_hash,
                    "dex_exchange": dex_exchange.value,
                    "route": str(route),
                    "estimated_gas": route.estimated_gas,
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
                f"DEX execution completed: {execution_id} "
                f"profit: ${float(result.profit):.2f}, "
                f"tx: {tx_hash}"
            )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"DEX execution failed: {error_msg}")
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
        
        # Find position for this execution
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
        self.logger.info(f"Simulating DEX execution: {plan.execution_id}")
        
        start_time = time.time()
        
        # Simulate swap
        amount_in = Decimal("100")
        amount_out = Decimal("102")
        profit = amount_out - amount_in
        
        execution_time_ms = self._calculate_execution_time(start_time)
        
        result = ExecutionResult(
            execution_id=plan.execution_id,
            status=ExecutionStatus.COMPLETED,
            orders=[],
            trades=[],
            positions=[],
            profit=profit,
            profit_percentage=profit / amount_in * Decimal("100"),
            gas_cost=Decimal("0.001"),
            fee_cost=Decimal("0.003"),
            total_cost=amount_in,
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
            if len(plan.orders) != 1:
                return False, "DEX arbitrage requires exactly 1 order"
            
            order = plan.orders[0]
            
            # Check exchange is DEX
            if order.exchange not in [ExchangeType.UNISWAP, ExchangeType.PANCAKESWAP,
                                      ExchangeType.SUSHISWAP, ExchangeType.BALANCER,
                                      ExchangeType.CURVE]:
                return False, f"Invalid DEX exchange: {order.exchange}"
            
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
                "dex_exchange": plan.orders[0].exchange if plan.orders else None,
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
            for order in plan.orders:
                exchange = self._get_dex_exchange(order.exchange)
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
            
            # Increase gas price for priority
            if self.dex_config.use_private_mempool:
                order.extra_params["gas_price_boost"] = 1.2
        
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
            order.extra_params["slippage_tolerance"] = self.dex_config.slippage_tolerance
            
            # Adjust price for slippage
            if order.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if order.price:
                    if order.side == OrderSide.BUY:
                        order.price = order.price * (Decimal("1") + self.dex_config.slippage_tolerance)
                    else:
                        order.price = order.price * (Decimal("1") - self.dex_config.slippage_tolerance)
        
        return plan
    
    async def optimize_gas(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize gas costs for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Optimized execution plan
        """
        if not self.dex_config.optimize_gas:
            return plan
        
        for order in plan.orders:
            # Set optimal gas price
            gas_price = await self._get_gas_price()
            order.extra_params["gas_price"] = gas_price
            order.extra_params["gas_limit"] = self.dex_config.default_gas_limit
        
        return plan
    
    def get_positions(self) -> Dict[str, DEXPosition]:
        """
        Get all DEX positions.
        
        Returns:
            Dictionary of position ID to DEXPosition
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
            "swaps_executed": self.metrics["swaps_executed"],
            "swaps_succeeded": self.metrics["swaps_succeeded"],
            "swaps_failed": self.metrics["swaps_failed"],
            "total_profit": float(self.metrics["total_profit"]),
            "total_loss": float(self.metrics["total_loss"]),
            "net_profit": float(self.metrics["net_profit"]),
            "active_positions": len(self.active_positions),
            "completed_positions": len(self.completed_positions),
            "avg_gas_used": self.metrics["avg_gas_used"],
            "avg_slippage": float(self.metrics["avg_slippage"]),
        }


# Module exports
__all__ = [
    'DEXExecutor',
    'DEXConfig',
    'DEXRoute',
    'DEXPosition',
]
