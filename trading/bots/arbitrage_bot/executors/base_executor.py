# trading/bots/arbitrage_bot/executors/base_executor.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Base Execution Engine

"""
Base Executor - Abstract Base Class for All Execution Engines

This module provides the abstract base class for all execution engines
in the NEXUS AI Trading System. It defines the standard interface for
executing arbitrage opportunities across different strategies.

Architecture:
    - BaseExecutor: Abstract base class
    - ExecutionType: Execution type enumeration
    - ExecutionStatus: Status enumeration
    - ExecutionConfig: Configuration dataclass
    - ExecutionResult: Result dataclass
    - ExecutionOrder: Order dataclass
    - ExecutionPosition: Position dataclass

Execution Types:
    - ATOMIC: Atomic execution (all-or-nothing)
    - SEQUENTIAL: Sequential execution (step by step)
    - PARALLEL: Parallel execution (simultaneous)
    - BATCH: Batch execution (grouped)
    - SMART: Smart execution (dynamic routing)

Features:
    - Abstract execution interface
    - Order management
    - Position management
    - Risk management
    - Slippage protection
    - Gas optimization
    - MEV protection
    - Execution monitoring
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Callable,
    AsyncIterator,
    TypeVar,
    Generic,
    Tuple,
    Set,
    Protocol,
    runtime_checkable,
)
from threading import Lock

from ..exchanges.base_exchange import (
    BaseExchange,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Order,
    Position,
    Trade,
    Balance,
    ExchangeType,
)


# Enums
class ExecutionType(Enum):
    """Execution type enumeration."""
    ATOMIC = "atomic"          # All-or-nothing execution
    SEQUENTIAL = "sequential"  # Step-by-step execution
    PARALLEL = "parallel"      # Parallel execution
    BATCH = "batch"            # Batch execution
    SMART = "smart"            # Smart/dynamic execution
    FLASH_LOAN = "flash_loan"  # Flash loan execution


class ExecutionStatus(Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    PREPARING = "preparing"
    EXECUTING = "executing"
    PARTIALLY_EXECUTED = "partially_executed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class ExecutionPriority(Enum):
    """Execution priority enumeration."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class ExecutionRisk(Enum):
    """Execution risk level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Dataclasses
@dataclass
class ExecutionConfig:
    """Execution configuration."""
    max_slippage: Decimal = Decimal("0.01")  # 1%
    max_gas_price: Decimal = Decimal("200")  # gwei
    gas_multiplier: Decimal = Decimal("1.1")
    max_position_size: Decimal = Decimal("100000")  # $100K
    max_risk_per_trade: Decimal = Decimal("0.01")  # 1%
    max_retries: int = 3
    retry_delay: int = 1  # seconds
    timeout: int = 60  # seconds
    require_confirmation: bool = True
    require_balance_check: bool = True
    require_risk_check: bool = True
    require_slippage_check: bool = True
    use_mev_protection: bool = True
    use_private_mempool: bool = True
    use_flash_loan: bool = False
    flash_loan_provider: Optional[str] = None
    priority: ExecutionPriority = ExecutionPriority.MEDIUM
    risk_level: ExecutionRisk = ExecutionRisk.MEDIUM
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionOrder:
    """Execution order."""
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    reduce_only: bool = False
    post_only: bool = False
    client_order_id: Optional[str] = None
    market_type: MarketType = MarketType.SPOT
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPosition:
    """Execution position."""
    symbol: str
    side: OrderSide
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expiry: Optional[datetime] = None


@dataclass
class ExecutionResult:
    """Execution result."""
    execution_id: str
    status: ExecutionStatus
    orders: List[Order]
    trades: List[Trade]
    positions: List[ExecutionPosition]
    profit: Decimal
    profit_percentage: Decimal
    gas_cost: Decimal
    fee_cost: Decimal
    total_cost: Decimal
    execution_time_ms: int
    timestamp: datetime
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Execution plan."""
    execution_id: str
    execution_type: ExecutionType
    orders: List[ExecutionOrder]
    steps: List[Dict[str, Any]]
    config: ExecutionConfig
    priority: ExecutionPriority
    risk_level: ExecutionRisk
    required_balance: Decimal
    max_loss: Decimal
    deadline: datetime
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: ExecutionStatus = ExecutionStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


# Protocols
@runtime_checkable
class ExecutionListener(Protocol):
    """Execution listener protocol."""
    
    def on_execution_started(self, execution_id: str) -> None:
        """Called when execution starts."""
        ...
    
    def on_execution_progress(self, execution_id: str, progress: float) -> None:
        """Called on execution progress."""
        ...
    
    def on_execution_completed(self, result: ExecutionResult) -> None:
        """Called when execution completes."""
        ...
    
    def on_execution_failed(self, execution_id: str, error: str) -> None:
        """Called when execution fails."""
        ...
    
    def on_execution_cancelled(self, execution_id: str) -> None:
        """Called when execution is cancelled."""
        ...


# Base Executor Class
class BaseExecutor(ABC):
    """
    Abstract base class for all execution engines.
    
    This class defines the standard interface that all execution
    engines must implement. It provides common functionality for
    executing arbitrage opportunities.
    
    Features:
    - Abstract execution interface
    - Order management
    - Position management
    - Risk management
    - Slippage protection
    - Gas optimization
    - MEV protection
    - Execution monitoring
    - Event handling
    """
    
    def __init__(
        self,
        config: ExecutionConfig,
        exchanges: Dict[ExchangeType, BaseExchange],
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the executor.
        
        Args:
            config: Execution configuration
            exchanges: Dictionary of exchanges
            logger: Optional logger instance
        """
        self.config = config
        self.exchanges = exchanges
        self.logger = logger or self._setup_logger()
        
        # Execution tracking
        self.executions: Dict[str, ExecutionPlan] = {}
        self.results: Dict[str, ExecutionResult] = {}
        self.active_executions: Set[str] = set()
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.order_map: Dict[str, List[str]] = {}  # execution_id -> order_ids
        
        # Position tracking
        self.positions: Dict[str, ExecutionPosition] = {}
        
        # Listeners
        self._listeners: List[ExecutionListener] = []
        
        # Locks
        self._execution_lock = Lock()
        self._order_lock = Lock()
        self._position_lock = Lock()
        
        # Metrics
        self.metrics = {
            "executions_total": 0,
            "executions_succeeded": 0,
            "executions_failed": 0,
            "executions_cancelled": 0,
            "total_profit": Decimal("0"),
            "total_loss": Decimal("0"),
            "net_profit": Decimal("0"),
            "total_gas_cost": Decimal("0"),
            "total_fee_cost": Decimal("0"),
            "avg_execution_time_ms": 0,
            "success_rate": Decimal("0"),
            "errors": 0,
        }
        
        # State
        self._is_running = False
        self._is_paused = False
        
        self.logger.info(f"Initialized {self.__class__.__name__}")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger."""
        logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # Abstract Methods
    
    @abstractmethod
    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Execute an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            ExecutionResult
        """
        pass
    
    @abstractmethod
    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel an execution.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_execution_status(self, execution_id: str) -> Optional[ExecutionStatus]:
        """
        Get execution status.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionStatus or None
        """
        pass
    
    @abstractmethod
    async def get_execution_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """
        Get execution result.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            ExecutionResult or None
        """
        pass
    
    @abstractmethod
    async def simulate_execution(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Simulate execution without placing real orders.
        
        Args:
            plan: Execution plan
            
        Returns:
            Simulated ExecutionResult
        """
        pass
    
    # Order Management
    
    @abstractmethod
    async def place_order(self, order: ExecutionOrder) -> Optional[Order]:
        """
        Place an order.
        
        Args:
            order: Execution order
            
        Returns:
            Order or None
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str, exchange: ExchangeType) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            exchange: Exchange type
            
        Returns:
            True if cancelled successfully
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str, symbol: str, exchange: ExchangeType) -> Optional[Order]:
        """
        Get order status.
        
        Args:
            order_id: Order ID
            symbol: Trading symbol
            exchange: Exchange type
            
        Returns:
            Order or None
        """
        pass
    
    @abstractmethod
    async def get_open_orders(self, symbol: str, exchange: ExchangeType) -> List[Order]:
        """
        Get open orders.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange type
            
        Returns:
            List of open orders
        """
        pass
    
    # Position Management
    
    @abstractmethod
    async def get_positions(self, exchange: ExchangeType) -> List[Position]:
        """
        Get all positions.
        
        Args:
            exchange: Exchange type
            
        Returns:
            List of positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str, exchange: ExchangeType) -> Optional[Position]:
        """
        Get position for a symbol.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange type
            
        Returns:
            Position or None
        """
        pass
    
    @abstractmethod
    async def close_position(self, position: ExecutionPosition) -> ExecutionResult:
        """
        Close a position.
        
        Args:
            position: Position to close
            
        Returns:
            ExecutionResult
        """
        pass
    
    # Risk Management
    
    @abstractmethod
    async def validate_execution(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Validate an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    async def calculate_risk(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Calculate risk metrics for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Risk metrics dictionary
        """
        pass
    
    @abstractmethod
    async def check_balance(self, plan: ExecutionPlan) -> Tuple[bool, Optional[str]]:
        """
        Check if there is sufficient balance for execution.
        
        Args:
            plan: Execution plan
            
        Returns:
            Tuple of (has_balance, error_message)
        """
        pass
    
    # MEV Protection
    
    @abstractmethod
    async def apply_mev_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply MEV protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        pass
    
    # Slippage Protection
    
    @abstractmethod
    async def apply_slippage_protection(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply slippage protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        pass
    
    # Gas Optimization
    
    @abstractmethod
    async def optimize_gas(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize gas costs for an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Optimized execution plan
        """
        pass
    
    # Utility Methods
    
    def get_exchange(self, exchange_type: ExchangeType) -> Optional[BaseExchange]:
        """
        Get an exchange instance by type.
        
        Args:
            exchange_type: Exchange type
            
        Returns:
            Exchange instance or None
        """
        return self.exchanges.get(exchange_type)
    
    def get_all_exchanges(self) -> Dict[ExchangeType, BaseExchange]:
        """
        Get all exchange instances.
        
        Returns:
            Dictionary of exchange type to instance
        """
        return self.exchanges.copy()
    
    def add_listener(self, listener: ExecutionListener) -> None:
        """
        Add an execution listener.
        
        Args:
            listener: Execution listener
        """
        self._listeners.append(listener)
    
    def remove_listener(self, listener: ExecutionListener) -> None:
        """
        Remove an execution listener.
        
        Args:
            listener: Execution listener
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def _emit_started(self, execution_id: str) -> None:
        """Emit execution started event."""
        for listener in self._listeners:
            try:
                listener.on_execution_started(execution_id)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    def _emit_progress(self, execution_id: str, progress: float) -> None:
        """Emit execution progress event."""
        for listener in self._listeners:
            try:
                listener.on_execution_progress(execution_id, progress)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    def _emit_completed(self, result: ExecutionResult) -> None:
        """Emit execution completed event."""
        for listener in self._listeners:
            try:
                listener.on_execution_completed(result)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    def _emit_failed(self, execution_id: str, error: str) -> None:
        """Emit execution failed event."""
        for listener in self._listeners:
            try:
                listener.on_execution_failed(execution_id, error)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    def _emit_cancelled(self, execution_id: str) -> None:
        """Emit execution cancelled event."""
        for listener in self._listeners:
            try:
                listener.on_execution_cancelled(execution_id)
            except Exception as e:
                self.logger.error(f"Listener error: {e}")
    
    def _generate_execution_id(self) -> str:
        """Generate a unique execution ID."""
        import uuid
        return f"exec_{uuid.uuid4().hex[:16]}"
    
    def _generate_client_order_id(self) -> str:
        """Generate a unique client order ID."""
        import uuid
        return f"nexus_{uuid.uuid4().hex[:12]}"
    
    def _calculate_execution_time(self, start_time: float) -> int:
        """Calculate execution time in milliseconds."""
        return int((time.time() - start_time) * 1000)
    
    def _format_decimal(self, value: Decimal, precision: int = 2) -> str:
        """Format decimal for display."""
        return f"{value:.{precision}f}"
    
    # Metrics
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get executor metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "active_executions": len(self.active_executions),
            "total_executions": len(self.executions),
            "total_results": len(self.results),
            "total_orders": len(self.orders),
            "total_positions": len(self.positions),
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "listener_count": len(self._listeners),
        }
    
    # Lifecycle Methods
    
    def start(self) -> None:
        """Start the executor."""
        if self._is_running:
            return
        
        self._is_running = True
        self._is_paused = False
        self.logger.info("Executor started")
    
    def stop(self) -> None:
        """Stop the executor."""
        self._is_running = False
        self.logger.info("Executor stopped")
    
    def pause(self) -> None:
        """Pause the executor."""
        self._is_paused = True
        self.logger.info("Executor paused")
    
    def resume(self) -> None:
        """Resume the executor."""
        self._is_paused = False
        self.logger.info("Executor resumed")
    
    # Error Handling
    
    class ExecutorError(Exception):
        """Base executor error."""
        pass
    
    class ExecutionError(ExecutorError):
        """Execution error."""
        pass
    
    class ValidationError(ExecutorError):
        """Validation error."""
        pass
    
    class BalanceError(ExecutorError):
        """Balance error."""
        pass
    
    class RiskError(ExecutorError):
        """Risk error."""
        pass
    
    class TimeoutError(ExecutorError):
        """Timeout error."""
        pass


# Module exports
__all__ = [
    'BaseExecutor',
    'ExecutionType',
    'ExecutionStatus',
    'ExecutionPriority',
    'ExecutionRisk',
    'ExecutionConfig',
    'ExecutionOrder',
    'ExecutionPosition',
    'ExecutionResult',
    'ExecutionPlan',
    'ExecutionListener',
]
