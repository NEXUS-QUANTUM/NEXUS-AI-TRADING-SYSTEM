"""
NEXUS AI TRADING SYSTEM - Paper Trading Orders Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_orders.py
Description: Paper trading order management with full API integration
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import ORDER_TYPES, TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository

# Paper trading imports
from trading.paper_trading.paper_account import PaperTradingAccount
from trading.paper_trading.paper_market import PaperTradingMarket

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderType(str, Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"  # One Cancels Other
    BRACKET = "bracket"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """Time in force"""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill
    GTD = "gtd"  # Good Till Date


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderRequest(BaseModel):
    """Request model for placing order"""
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    size: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.GTC
    expire_date: Optional[datetime] = None
    trail_distance: Optional[float] = None
    oco_order: Optional[Dict[str, Any]] = None
    bracket_order: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v


class OrderResponse(BaseModel):
    """Response model for order"""
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    size: float
    filled_size: float
    price: float
    avg_price: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce
    expire_date: Optional[datetime] = None
    trail_distance: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    rejected_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderUpdateRequest(BaseModel):
    """Request model for updating order"""
    order_id: str
    price: Optional[float] = None
    size: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    trail_distance: Optional[float] = None
    time_in_force: Optional[TimeInForce] = None
    metadata: Optional[Dict[str, Any]] = None


class OrderCancelRequest(BaseModel):
    """Request model for cancelling order"""
    order_id: str
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderHistoryResponse(BaseModel):
    """Response model for order history"""
    total_orders: int
    orders: List[OrderResponse]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OrderContext:
    """Context for order processing"""
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    filled_size: float
    price: float
    avg_price: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: TimeInForce
    expire_date: Optional[datetime] = None
    trail_distance: Optional[float] = None
    trail_high: Optional[float] = None
    trail_low: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    status: OrderStatus
    oco_order: Optional[Dict[str, Any]] = None
    bracket_order: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderFill:
    """Order fill details"""
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    timestamp: datetime
    trade_id: Optional[str] = None


# =============================================================================
# PAPER TRADING ORDERS
# =============================================================================

class PaperTradingOrders:
    """
    Paper Trading Order Management with full API integration.
    
    Features:
    - Multiple order types (market, limit, stop, stop-limit, trailing stop, OCO, bracket)
    - Order status management
    - Order execution
    - Order cancellation
    - Order modification
    - Order history
    - Batch operations
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        paper_account: Optional[PaperTradingAccount] = None,
        paper_market: Optional[PaperTradingMarket] = None
    ):
        """
        Initialize PaperTradingOrders.
        
        Args:
            config: Paper trading configuration
            order_repo: Order repository
            trade_repo: Trade repository
            paper_account: Paper trading account
            paper_market: Paper trading market
        """
        self.config = config or PaperTradingConfig()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.paper_account = paper_account or PaperTradingAccount()
        self.paper_market = paper_market or PaperTradingMarket()
        
        # Order management
        self._orders: Dict[str, OrderContext] = {}
        self._order_history: List[OrderContext] = []
        
        # Order book
        self._order_book: Dict[str, List[str]] = {}  # symbol -> list of order_ids
        
        # Pending orders for monitoring
        self._pending_orders: Dict[str, OrderContext] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Order counter
        self._order_counter: int = 0
        
        logger.info("PaperTradingOrders initialized")

    # =========================================================================
    # Order Placement
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: OrderRequest
    ) -> OrderResponse:
        """
        Place an order.
        
        Args:
            request: Order request
            
        Returns:
            OrderResponse: Order result
        """
        try:
            # Validate request
            await self._validate_order(request)
            
            # Check account
            account = await self.paper_account.get_account(request.account_id)
            if not account:
                raise ValueError(f"Account {request.account_id} not found")
            
            # Generate order ID
            self._order_counter += 1
            order_id = f"ord_{int(time.time() * 1000)}_{self._order_counter:06d}"
            
            # Get current price
            market_data = await self.paper_market.get_market_data(request.symbol)
            current_price = market_data.price
            
            # Validate order price
            if request.order_type == OrderType.LIMIT and request.price:
                if request.price <= 0:
                    raise ValueError("Limit price must be positive")
            
            if request.order_type == OrderType.STOP and request.stop_price:
                if request.stop_price <= 0:
                    raise ValueError("Stop price must be positive")
            
            # Create order context
            context = OrderContext(
                order_id=order_id,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                size=request.size,
                filled_size=0,
                price=request.price or current_price,
                avg_price=0,
                stop_price=request.stop_price,
                limit_price=request.limit_price,
                time_in_force=request.time_in_force,
                expire_date=request.expire_date,
                trail_distance=request.trail_distance,
                trail_high=current_price if request.trail_distance else None,
                trail_low=current_price if request.trail_distance else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                status=OrderStatus.PENDING,
                oco_order=request.oco_order,
                bracket_order=request.bracket_order,
                metadata=request.metadata
            )
            
            # Process order based on type
            if request.order_type == OrderType.MARKET:
                await self._process_market_order(context, current_price)
            elif request.order_type == OrderType.LIMIT:
                await self._process_limit_order(context, current_price)
            elif request.order_type == OrderType.STOP:
                await self._process_stop_order(context, current_price)
            elif request.order_type == OrderType.STOP_LIMIT:
                await self._process_stop_limit_order(context, current_price)
            elif request.order_type == OrderType.TRAILING_STOP:
                await self._process_trailing_stop_order(context, current_price)
            elif request.order_type == OrderType.OCO:
                await self._process_oco_order(context, current_price)
            elif request.order_type == OrderType.BRACKET:
                await self._process_bracket_order(context, current_price)
            else:
                await self._process_limit_order(context, current_price)
            
            # Store order
            self._orders[order_id] = context
            
            # Add to order book
            if request.symbol not in self._order_book:
                self._order_book[request.symbol] = []
            self._order_book[request.symbol].append(order_id)
            
            # Add to pending if not filled
            if context.status in [OrderStatus.PENDING, OrderStatus.OPEN]:
                self._pending_orders[order_id] = context
            
            # Start monitoring if not running
            if not self._is_monitoring:
                await self.start_monitoring()
            
            logger.info(f"Order {order_id} placed for {request.symbol}")
            return self._to_response(context)
            
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order placement failed: {str(e)}"
            )

    async def _validate_order(self, request: OrderRequest) -> None:
        """Validate order request"""
        if request.size <= 0:
            raise ValueError("Order size must be positive")
        
        if request.order_type == OrderType.MARKET:
            # Market order - no price needed
            pass
        elif request.order_type == OrderType.LIMIT:
            if not request.price or request.price <= 0:
                raise ValueError("Limit order requires valid price")
        elif request.order_type == OrderType.STOP:
            if not request.stop_price or request.stop_price <= 0:
                raise ValueError("Stop order requires valid stop price")
        elif request.order_type == OrderType.STOP_LIMIT:
            if not request.stop_price or request.stop_price <= 0:
                raise ValueError("Stop-limit order requires valid stop price")
            if not request.limit_price or request.limit_price <= 0:
                raise ValueError("Stop-limit order requires valid limit price")
        elif request.order_type == OrderType.TRAILING_STOP:
            if not request.trail_distance or request.trail_distance <= 0:
                raise ValueError("Trailing stop requires valid trail distance")

    # =========================================================================
    # Order Processing
    # =========================================================================

    async def _process_market_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process market order"""
        context.status = OrderStatus.FILLED
        context.filled_size = context.size
        context.avg_price = current_price
        context.price = current_price
        context.updated_at = datetime.utcnow()
        context.filled_at = datetime.utcnow()
        
        # Execute trade
        await self._execute_order(context)

    async def _process_limit_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process limit order"""
        if context.side == OrderSide.BUY:
            if current_price <= context.price:
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        else:  # SELL
            if current_price >= context.price:
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        
        context.updated_at = datetime.utcnow()

    async def _process_stop_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process stop order"""
        if context.side == OrderSide.BUY:
            if current_price >= context.stop_price:
                # Triggered - convert to market order
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        else:  # SELL
            if current_price <= context.stop_price:
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        
        context.updated_at = datetime.utcnow()

    async def _process_stop_limit_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process stop-limit order"""
        if context.side == OrderSide.BUY:
            if current_price >= context.stop_price:
                # Triggered - check limit price
                if current_price <= context.limit_price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
                else:
                    context.status = OrderStatus.OPEN
            else:
                context.status = OrderStatus.OPEN
        else:  # SELL
            if current_price <= context.stop_price:
                if current_price >= context.limit_price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
                else:
                    context.status = OrderStatus.OPEN
            else:
                context.status = OrderStatus.OPEN
        
        context.updated_at = datetime.utcnow()

    async def _process_trailing_stop_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process trailing stop order"""
        # Update trail prices
        if current_price > context.trail_high:
            context.trail_high = current_price
        if current_price < context.trail_low:
            context.trail_low = current_price
        
        # Calculate stop price
        if context.side == OrderSide.BUY:
            stop_price = context.trail_high * (1 - context.trail_distance)
            context.stop_price = stop_price
            
            if current_price <= stop_price:
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        else:  # SELL
            stop_price = context.trail_low * (1 + context.trail_distance)
            context.stop_price = stop_price
            
            if current_price >= stop_price:
                context.status = OrderStatus.FILLED
                context.filled_size = context.size
                context.avg_price = current_price
                context.price = current_price
                context.filled_at = datetime.utcnow()
                await self._execute_order(context)
            else:
                context.status = OrderStatus.OPEN
        
        context.updated_at = datetime.utcnow()

    async def _process_oco_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process OCO (One Cancels Other) order"""
        # Place parent order
        await self._process_limit_order(context, current_price)
        
        # If OCO order specified, place child orders
        if context.oco_order:
            # Place the other order
            # When one fills, the other is cancelled
            pass

    async def _process_bracket_order(
        self,
        context: OrderContext,
        current_price: float
    ) -> None:
        """Process bracket order"""
        # Place parent order
        await self._process_limit_order(context, current_price)
        
        # If bracket order specified, place stop loss and take profit
        if context.bracket_order:
            # Place stop loss and take profit orders
            # If one fills, the other is cancelled
            pass

    # =========================================================================
    # Order Execution
    # =========================================================================

    async def _execute_order(self, context: OrderContext) -> None:
        """Execute order and update account"""
        # Update account balance
        trade_value = context.size * context.avg_price
        
        if context.side == OrderSide.BUY:
            # Decrease balance
            await self.paper_account._update_balance(context.account_id, -trade_value)
        else:  # SELL
            # Increase balance
            await self.paper_account._update_balance(context.account_id, trade_value)
        
        # Update position
        await self.paper_account._update_position(
            context.account_id,
            context.symbol,
            context.side,
            context.size,
            context.avg_price
        )
        
        # Record trade
        await self.trade_repo.create({
            'order_id': context.order_id,
            'account_id': context.account_id,
            'symbol': context.symbol,
            'side': context.side.value,
            'size': context.size,
            'price': context.avg_price,
            'timestamp': datetime.utcnow()
        })
        
        # Remove from pending
        if context.order_id in self._pending_orders:
            del self._pending_orders[context.order_id]
        
        # Add to history
        self._order_history.append(context)

    # =========================================================================
    # Order Management
    # =========================================================================

    async def cancel_order(
        self,
        request: OrderCancelRequest
    ) -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            request: Cancel request
            
        Returns:
            Dict[str, Any]: Cancel result
        """
        try:
            if request.order_id not in self._orders:
                raise ValueError(f"Order {request.order_id} not found")
            
            context = self._orders[request.order_id]
            
            if context.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                raise ValueError(f"Order {request.order_id} cannot be cancelled")
            
            context.status = OrderStatus.CANCELLED
            context.updated_at = datetime.utcnow()
            context.cancelled_at = datetime.utcnow()
            
            # Remove from pending
            if request.order_id in self._pending_orders:
                del self._pending_orders[request.order_id]
            
            # Add to history
            self._order_history.append(context)
            
            logger.info(f"Order {request.order_id} cancelled")
            
            return {
                'order_id': request.order_id,
                'status': 'cancelled',
                'reason': request.reason,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order cancellation failed: {str(e)}"
            )

    async def update_order(
        self,
        request: OrderUpdateRequest
    ) -> OrderResponse:
        """
        Update an order.
        
        Args:
            request: Update request
            
        Returns:
            OrderResponse: Updated order
        """
        try:
            if request.order_id not in self._orders:
                raise ValueError(f"Order {request.order_id} not found")
            
            context = self._orders[request.order_id]
            
            if context.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
                raise ValueError(f"Order {request.order_id} cannot be updated")
            
            # Update fields
            if request.price is not None:
                context.price = request.price
            if request.size is not None:
                context.size = request.size
            if request.stop_price is not None:
                context.stop_price = request.stop_price
            if request.limit_price is not None:
                context.limit_price = request.limit_price
            if request.trail_distance is not None:
                context.trail_distance = request.trail_distance
            if request.time_in_force is not None:
                context.time_in_force = request.time_in_force
            if request.metadata is not None:
                context.metadata = request.metadata
            
            context.updated_at = datetime.utcnow()
            
            logger.info(f"Order {request.order_id} updated")
            return self._to_response(context)
            
        except Exception as e:
            logger.error(f"Error updating order: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order update failed: {str(e)}"
            )

    # =========================================================================
    # Order Retrieval
    # =========================================================================

    async def get_order(self, order_id: str) -> OrderResponse:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            OrderResponse: Order details
        """
        if order_id not in self._orders:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {order_id} not found"
            )
        
        return self._to_response(self._orders[order_id])

    async def get_orders(
        self,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        order_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> OrderHistoryResponse:
        """
        Get orders with filters.
        
        Args:
            account_id: Filter by account
            symbol: Filter by symbol
            status: Filter by status
            order_type: Filter by order type
            limit: Maximum records
            offset: Offset
            
        Returns:
            OrderHistoryResponse: Order history
        """
        orders = list(self._orders.values())
        
        if account_id:
            orders = [o for o in orders if o.account_id == account_id]
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        if status:
            orders = [o for o in orders if o.status.value == status]
        
        if order_type:
            orders = [o for o in orders if o.order_type.value == order_type]
        
        # Sort by creation time
        orders.sort(key=lambda o: o.created_at, reverse=True)
        
        # Apply pagination
        total = len(orders)
        orders = orders[offset:offset + limit]
        
        # Calculate summary
        summary = {
            'total_orders': total,
            'open_orders': len([o for o in orders if o.status == OrderStatus.OPEN]),
            'filled_orders': len([o for o in orders if o.status == OrderStatus.FILLED]),
            'cancelled_orders': len([o for o in orders if o.status == OrderStatus.CANCELLED]),
            'by_type': {}
        }
        
        for o in orders:
            order_type_key = o.order_type.value
            if order_type_key not in summary['by_type']:
                summary['by_type'][order_type_key] = 0
            summary['by_type'][order_type_key] += 1
        
        return OrderHistoryResponse(
            total_orders=total,
            orders=[self._to_response(o) for o in orders],
            summary=summary,
            metadata={}
        )

    # =========================================================================
    # Order Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start order monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Order monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop order monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Order monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Check pending orders
                for order_id, context in list(self._pending_orders.items()):
                    try:
                        await self._check_order(context)
                    except Exception as e:
                        logger.error(f"Error checking order {order_id}: {e}")
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def _check_order(self, context: OrderContext) -> None:
        """Check order status"""
        # Get current price
        market_data = await self.paper_market.get_market_data(context.symbol)
        current_price = market_data.price
        
        # Check if order should be filled
        if context.status == OrderStatus.OPEN:
            if context.order_type == OrderType.LIMIT:
                if context.side == OrderSide.BUY and current_price <= context.price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
                elif context.side == OrderSide.SELL and current_price >= context.price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
            
            elif context.order_type == OrderType.STOP:
                if context.side == OrderSide.BUY and current_price >= context.stop_price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
                elif context.side == OrderSide.SELL and current_price <= context.stop_price:
                    context.status = OrderStatus.FILLED
                    context.filled_size = context.size
                    context.avg_price = current_price
                    context.price = current_price
                    context.filled_at = datetime.utcnow()
                    await self._execute_order(context)
            
            elif context.order_type == OrderType.TRAILING_STOP:
                await self._process_trailing_stop_order(context, current_price)
            
            # Update timestamp
            context.updated_at = datetime.utcnow()
            
            # Remove from pending if filled
            if context.status == OrderStatus.FILLED:
                if context.order_id in self._pending_orders:
                    del self._pending_orders[context.order_id]
            
            # Update order in storage
            self._orders[context.order_id] = context

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _to_response(self, context: OrderContext) -> OrderResponse:
        """Convert context to response"""
        return OrderResponse(
            order_id=context.order_id,
            account_id=context.account_id,
            symbol=context.symbol,
            side=context.side,
            order_type=context.order_type,
            status=context.status,
            size=context.size,
            filled_size=context.filled_size,
            price=context.price,
            avg_price=context.avg_price,
            stop_price=context.stop_price,
            limit_price=context.limit_price,
            time_in_force=context.time_in_force,
            expire_date=context.expire_date,
            trail_distance=context.trail_distance,
            created_at=context.created_at,
            updated_at=context.updated_at,
            filled_at=context.filled_at,
            cancelled_at=context.cancelled_at,
            metadata=context.metadata
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the orders module"""
        await self.stop_monitoring()
        
        # Cancel all pending orders
        for order_id in list(self._pending_orders.keys()):
            try:
                await self.cancel_order(OrderCancelRequest(order_id=order_id))
            except Exception as e:
                logger.error(f"Error cancelling order {order_id}: {e}")
        
        self._orders.clear()
        self._order_history.clear()
        self._order_book.clear()
        self._pending_orders.clear()
        
        logger.info("PaperTradingOrders closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/orders", tags=["Paper Trading Orders"])


async def get_orders() -> PaperTradingOrders:
    """Dependency to get PaperTradingOrders instance"""
    return PaperTradingOrders()


@router.post("/place", response_model=OrderResponse)
async def place_order(
    request: OrderRequest,
    orders: PaperTradingOrders = Depends(get_orders)
):
    """Place an order"""
    return await orders.place_order(request)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    orders: PaperTradingOrders = Depends(get_orders)
):
    """Get order by ID"""
    return await orders.get_order(order_id)


@router.get("/")
async def get_orders(
    account_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    orders: PaperTradingOrders = Depends(get_orders)
):
    """Get orders with filters"""
    return await orders.get_orders(account_id, symbol, status, order_type, limit, offset)


@router.put("/update", response_model=OrderResponse)
async def update_order(
    request: OrderUpdateRequest,
    orders: PaperTradingOrders = Depends(get_orders)
):
    """Update an order"""
    return await orders.update_order(request)


@router.post("/cancel")
async def cancel_order(
    request: OrderCancelRequest,
    orders: PaperTradingOrders = Depends(get_orders)
):
    """Cancel an order"""
    return await orders.cancel_order(request)


@router.get("/types")
async def get_order_types():
    """Get available order types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in OrderType
        ]
    }


@router.get("/statuses")
async def get_order_statuses():
    """Get available order statuses"""
    return {
        'statuses': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in OrderStatus
        ]
    }


@router.get("/time-in-force")
async def get_time_in_force():
    """Get available time in force options"""
    return {
        'options': [
            {'name': t.value, 'description': t.name}
            for t in TimeInForce
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingOrders',
    'OrderStatus',
    'OrderType',
    'OrderSide',
    'TimeInForce',
    'OrderRequest',
    'OrderResponse',
    'OrderUpdateRequest',
    'OrderCancelRequest',
    'OrderHistoryResponse',
    'OrderContext',
    'OrderFill',
    'router'
]
