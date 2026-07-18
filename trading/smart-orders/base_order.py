"""
NEXUS AI TRADING SYSTEM - Base Smart Order Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module: trading/smart-orders/base_order.py
Version: 1.0.0
Description: Base class for all smart order implementations
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict

from shared.types.trading import OrderSide, OrderType, OrderStatus, TimeInForce
from shared.interfaces.broker import BrokerInterface
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class SmartOrderState(str, Enum):
    """Base states for smart orders"""
    INACTIVE = "inactive"
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXECUTED = "executed"
    PARTIALLY_EXECUTED = "partially_executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ERROR = "error"


class SmartOrderConfig(BaseModel):
    """Base configuration for all smart orders"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Core settings
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side (BUY/SELL)")
    
    # Order settings
    order_type: OrderType = Field(default=OrderType.LIMIT)
    time_in_force: TimeInForce = Field(default=TimeInForce.GTC)
    quantity: Optional[float] = Field(None, description="Order quantity")
    
    # Risk settings
    max_slippage: float = Field(0.01, description="Maximum allowed slippage")
    max_risk_percent: float = Field(0.02, description="Maximum risk percentage")
    
    # Time settings
    expire_after: Optional[int] = Field(None, description="Expire after seconds")
    start_time: Optional[datetime] = Field(None, description="Start time")
    end_time: Optional[datetime] = Field(None, description="End time")
    
    # Tags and metadata
    tags: List[str] = Field(default_factory=list, description="Order tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    client_order_id: Optional[str] = Field(None, description="Client order ID")
    
    # Execution settings
    retry_count: int = Field(3, description="Number of retries")
    retry_delay: float = Field(1.0, description="Retry delay in seconds")
    timeout: float = Field(30.0, description="Order timeout in seconds")


class OrderFill(BaseModel):
    """Order fill information"""
    order_id: str
    price: float
    quantity: float
    timestamp: datetime
    fee: float = 0.0
    fee_currency: str = "USD"
    liquidity: str = "maker"  # maker/taker


class SmartOrder(ABC):
    """
    Base class for all smart order implementations.
    
    This abstract class defines the interface and common functionality
    for all smart order types including:
    - Lifecycle management
    - State management
    - Event handling
    - Error handling
    - Metrics collection
    """

    def __init__(
        self,
        config: SmartOrderConfig,
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional['OrderManager'] = None  # Forward reference
    ):
        """
        Initialize a smart order.

        Args:
            config: Order configuration
            broker: Broker interface for execution
            order_manager: Order manager for coordination
        """
        self.id = str(uuid.uuid4())
        self.config = config
        self._broker = broker
        self._order_manager = order_manager
        self._state = SmartOrderState.INACTIVE
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()
        self._executed_at: Optional[datetime] = None
        self._cancelled_at: Optional[datetime] = None
        
        # Fill tracking
        self._fills: List[OrderFill] = []
        self._total_filled_quantity: float = 0.0
        self._average_fill_price: float = 0.0
        
        # Error tracking
        self._errors: List[Dict[str, Any]] = []
        self._last_error: Optional[str] = None
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            'on_state_change': [],
            'on_fill': [],
            'on_error': [],
            'on_cancel': [],
            'on_expire': []
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"Created smart order {self.id} for {config.symbol}")

    @abstractmethod
    async def activate(self, *args, **kwargs) -> bool:
        """
        Activate the smart order.

        This method should be implemented by subclasses to define
        how the order is activated.

        Returns:
            bool: True if activated successfully
        """
        pass

    @abstractmethod
    async def update_price(self, price: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Update the current price.

        This method should be implemented by subclasses to handle
        price updates.

        Args:
            price: Current market price
            timestamp: Optional timestamp

        Returns:
            bool: True if updated successfully
        """
        pass

    @abstractmethod
    async def check_conditions(self, *args, **kwargs) -> bool:
        """
        Check if order conditions are met.

        This method should be implemented by subclasses to define
        when the order should trigger.

        Returns:
            bool: True if conditions are met
        """
        pass

    @abstractmethod
    async def cancel(self) -> bool:
        """
        Cancel the order.

        Returns:
            bool: True if cancelled successfully
        """
        pass

    @abstractmethod
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get order metrics.

        Returns:
            Dict[str, Any]: Order metrics
        """
        pass

    # ==================== Common Methods ====================

    async def execute(self) -> bool:
        """
        Execute the order.

        Returns:
            bool: True if executed successfully
        """
        if self._state in [SmartOrderState.EXECUTED, SmartOrderState.CANCELLED]:
            logger.warning(f"Order {self.id} already executed or cancelled")
            return False

        if not self._broker:
            logger.error(f"Order {self.id}: No broker available")
            return False

        try:
            # Prepare order parameters
            params = self._prepare_order_params()

            # Place the order
            result = await self._broker.place_order(**params)

            # Process result
            if result and result.get('status') in ['FILLED', 'PARTIALLY_FILLED']:
                await self._handle_execution(result)
                return True
            else:
                await self._handle_error(f"Order execution failed: {result}")
                return False

        except Exception as e:
            await self._handle_error(str(e))
            return False

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current order status.

        Returns:
            Dict[str, Any]: Status information
        """
        async with self._lock:
            status = {
                'order_id': self.id,
                'state': self._state.value,
                'symbol': self.config.symbol,
                'side': self.config.side.value,
                'created_at': self._created_at.isoformat(),
                'updated_at': self._updated_at.isoformat(),
                'total_filled': self._total_filled_quantity,
                'average_price': self._average_fill_price,
                'fills': [fill.model_dump() for fill in self._fills],
                'errors': self._errors[-5:] if self._errors else [],  # Last 5 errors
                'config': self.config.model_dump()
            }

            if self._executed_at:
                status['executed_at'] = self._executed_at.isoformat()
            if self._cancelled_at:
                status['cancelled_at'] = self._cancelled_at.isoformat()

            return status

    def get_state(self) -> SmartOrderState:
        """Get current state"""
        return self._state

    def get_id(self) -> str:
        """Get order ID"""
        return self.id

    def get_symbol(self) -> str:
        """Get trading symbol"""
        return self.config.symbol

    def get_side(self) -> OrderSide:
        """Get order side"""
        return self.config.side

    def get_quantity(self) -> Optional[float]:
        """Get order quantity"""
        return self.config.quantity

    def get_filled_quantity(self) -> float:
        """Get filled quantity"""
        return self._total_filled_quantity

    def get_average_price(self) -> float:
        """Get average fill price"""
        return self._average_fill_price

    def get_fills(self) -> List[OrderFill]:
        """Get all fills"""
        return self._fills.copy()

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get errors"""
        return self._errors.copy()

    def get_last_error(self) -> Optional[str]:
        """Get last error"""
        return self._last_error

    def is_active(self) -> bool:
        """Check if order is active"""
        return self._state in [SmartOrderState.ACTIVE, SmartOrderState.PENDING]

    def is_completed(self) -> bool:
        """Check if order is completed"""
        return self._state in [SmartOrderState.EXECUTED, SmartOrderState.CANCELLED, SmartOrderState.EXPIRED]

    # ==================== Event System ====================

    def on(self, event: str, handler: Callable):
        """
        Register an event handler.

        Args:
            event: Event name ('state_change', 'fill', 'error', 'cancel', 'expire')
            handler: Handler function
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)
        else:
            self._event_handlers[event] = [handler]

    def off(self, event: str, handler: Callable):
        """
        Unregister an event handler.

        Args:
            event: Event name
            handler: Handler function to remove
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    async def _emit_event(self, event: str, data: Dict[str, Any]):
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(self, data)
                else:
                    handler(self, data)
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}")

    # ==================== State Management ====================

    async def _set_state(self, new_state: SmartOrderState):
        """
        Set order state.

        Args:
            new_state: New state
        """
        async with self._lock:
            old_state = self._state
            self._state = new_state
            self._updated_at = datetime.utcnow()

            await self._emit_event('state_change', {
                'old_state': old_state.value,
                'new_state': new_state.value,
                'timestamp': self._updated_at
            })

            logger.debug(f"Order {self.id} state changed: {old_state.value} -> {new_state.value}")

    # ==================== Execution Handling ====================

    def _prepare_order_params(self) -> Dict[str, Any]:
        """
        Prepare order parameters for broker.

        Returns:
            Dict[str, Any]: Order parameters
        """
        params = {
            'symbol': self.config.symbol,
            'side': self.config.side,
            'order_type': self.config.order_type,
            'quantity': self.config.quantity,
            'time_in_force': self.config.time_in_force,
            'client_order_id': self.config.client_order_id or self.id
        }

        # Add price for limit/stop orders
        if self.config.order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if hasattr(self, '_get_limit_price'):
                params['price'] = self._get_limit_price()

        # Add stop price for stop orders
        if self.config.order_type in [OrderType.STOP, OrderType.STOP_LIMIT]:
            if hasattr(self, '_get_stop_price'):
                params['stop_price'] = self._get_stop_price()

        # Add metadata
        if self.config.metadata:
            params['metadata'] = self.config.metadata

        return params

    async def _handle_execution(self, result: Dict[str, Any]):
        """
        Handle successful execution.

        Args:
            result: Execution result
        """
        async with self._lock:
            # Create fill
            fill = OrderFill(
                order_id=result.get('order_id', self.id),
                price=result.get('price', 0),
                quantity=result.get('filled_quantity', 0),
                timestamp=datetime.utcnow(),
                fee=result.get('fee', 0),
                fee_currency=result.get('fee_currency', 'USD'),
                liquidity=result.get('liquidity', 'maker')
            )

            self._fills.append(fill)
            self._total_filled_quantity += fill.quantity

            # Update average price
            self._average_fill_price = (
                (self._average_fill_price * (self._total_filled_quantity - fill.quantity) +
                 fill.price * fill.quantity) / self._total_filled_quantity
            ) if self._total_filled_quantity > 0 else fill.price

            # Update state
            if self._total_filled_quantity >= (self.config.quantity or 0) * 0.99:
                await self._set_state(SmartOrderState.EXECUTED)
                self._executed_at = datetime.utcnow()
            else:
                await self._set_state(SmartOrderState.PARTIALLY_EXECUTED)

            # Emit fill event
            await self._emit_event('fill', {
                'fill': fill.model_dump(),
                'total_filled': self._total_filled_quantity,
                'average_price': self._average_fill_price
            })

    async def _handle_error(self, error: str):
        """
        Handle error.

        Args:
            error: Error message
        """
        async with self._lock:
            self._last_error = error
            self._errors.append({
                'timestamp': datetime.utcnow(),
                'error': error
            })

            if len(self._errors) > 100:
                self._errors.pop(0)

            await self._set_state(SmartOrderState.ERROR)
            await self._emit_event('error', {'error': error})

            logger.error(f"Order {self.id} error: {error}")

    # ==================== Utility Methods ====================

    def _round_price(self, price: float) -> float:
        """
        Round price to tick size.

        Args:
            price: Price to round

        Returns:
            float: Rounded price
        """
        tick_size = getattr(self.config, 'tick_size', 0.0001)
        return round(price / tick_size) * tick_size

    def _round_quantity(self, quantity: float) -> float:
        """
        Round quantity to lot size.

        Args:
            quantity: Quantity to round

        Returns:
            float: Rounded quantity
        """
        lot_size = getattr(self.config, 'lot_size', 0.000001)
        return round(quantity / lot_size) * lot_size

    def _is_valid_price(self, price: float) -> bool:
        """
        Check if price is valid.

        Args:
            price: Price to check

        Returns:
            bool: True if valid
        """
        return price > 0 and price < float('inf')

    def _is_valid_quantity(self, quantity: float) -> bool:
        """
        Check if quantity is valid.

        Args:
            quantity: Quantity to check

        Returns:
            bool: True if valid
        """
        min_quantity = getattr(self.config, 'min_quantity', 0.000001)
        return quantity >= min_quantity and quantity < float('inf')

    # ==================== Serialization ====================

    async def to_dict(self) -> Dict[str, Any]:
        """
        Convert order to dictionary.

        Returns:
            Dict[str, Any]: Order data
        """
        return {
            'id': self.id,
            'type': self.__class__.__name__,
            'config': self.config.model_dump(),
            'state': self._state.value,
            'created_at': self._created_at.isoformat(),
            'updated_at': self._updated_at.isoformat(),
            'executed_at': self._executed_at.isoformat() if self._executed_at else None,
            'cancelled_at': self._cancelled_at.isoformat() if self._cancelled_at else None,
            'total_filled': self._total_filled_quantity,
            'average_price': self._average_fill_price,
            'fills': [fill.model_dump() for fill in self._fills],
            'last_error': self._last_error
        }

    @classmethod
    async def from_dict(
        cls,
        data: Dict[str, Any],
        broker: Optional[BrokerInterface] = None,
        order_manager: Optional['OrderManager'] = None
    ) -> 'SmartOrder':
        """
        Create order from dictionary.

        Args:
            data: Order data
            broker: Broker interface
            order_manager: Order manager

        Returns:
            SmartOrder: Reconstructed order
        """
        # This should be overridden by subclasses
        raise NotImplementedError("Subclasses must implement from_dict")

    # ==================== Magic Methods ====================

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.is_active():
            await self.cancel()

    def __repr__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__} id={self.id} symbol={self.config.symbol} state={self._state.value}>"
