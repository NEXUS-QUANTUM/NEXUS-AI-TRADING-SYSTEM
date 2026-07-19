"""
NEXUS AI TRADING SYSTEM - Paper Trading Account Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_account.py
Description: Paper trading account management with full API integration
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
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Order, Trade
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class AccountStatus(str, Enum):
    """Account status"""
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class AccountType(str, Enum):
    """Account type"""
    PAPER = "paper"
    DEMO = "demo"
    SIMULATION = "simulation"


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


class OrderSide(str, Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    """Time in force"""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AccountCreateRequest(BaseModel):
    """Request model for account creation"""
    name: str
    initial_balance: float = 100000.0
    account_type: AccountType = AccountType.PAPER
    currency: str = "USD"
    leverage: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('initial_balance')
    def validate_balance(cls, v):
        if v <= 0:
            raise ValueError("Initial balance must be positive")
        return v


class AccountResponse(BaseModel):
    """Response model for account"""
    account_id: str
    name: str
    account_type: AccountType
    status: AccountStatus
    balance: float
    equity: float
    available_balance: float
    margin_used: float
    margin_available: float
    leverage: float
    total_pnl: float
    total_pnl_pct: float
    positions_count: int
    orders_count: int
    trades_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionResponse(BaseModel):
    """Response model for position"""
    position_id: str
    account_id: str
    symbol: str
    side: OrderSide
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    value: float
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AccountState:
    """Account state"""
    account_id: str
    balance: float
    equity: float
    available_balance: float
    margin_used: float
    margin_available: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    timestamp: datetime


@dataclass
class TradeResult:
    """Trade execution result"""
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    pnl: float
    timestamp: datetime
    status: str


# =============================================================================
# PAPER TRADING ACCOUNT
# =============================================================================

class PaperTradingAccount:
    """
    Paper Trading Account with full API integration.
    
    Features:
    - Account creation and management
    - Order placement (market, limit, stop, stop-limit, trailing stop)
    - Position management
    - Balance tracking
    - PnL calculation
    - Order book simulation
    - Market data integration
    - Real-time updates
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize PaperTradingAccount.
        
        Args:
            config: Paper trading configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or PaperTradingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Account cache
        self._accounts: Dict[str, AccountState] = {}
        self._account_info: Dict[str, Dict[str, Any]] = {}
        
        # Order management
        self._pending_orders: Dict[str, OrderRequest] = {}
        self._order_history: List[OrderResponse] = []
        
        # Price cache
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("PaperTradingAccount initialized")

    # =========================================================================
    # Account Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_account(
        self,
        request: AccountCreateRequest
    ) -> AccountResponse:
        """
        Create a new paper trading account.
        
        Args:
            request: Account creation request
            
        Returns:
            AccountResponse: Created account
        """
        try:
            # Generate account ID
            account_id = f"paper_{int(time.time() * 1000)}_{request.name[:10]}"
            
            # Create account
            account_data = {
                'account_id': account_id,
                'name': request.name,
                'account_type': request.account_type.value,
                'status': AccountStatus.ACTIVE.value,
                'balance': request.initial_balance,
                'equity': request.initial_balance,
                'available_balance': request.initial_balance,
                'margin_used': 0,
                'margin_available': request.initial_balance,
                'leverage': request.leverage,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'positions_count': 0,
                'orders_count': 0,
                'trades_count': 0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'metadata': request.metadata
            }
            
            # Initialize account state
            state = AccountState(
                account_id=account_id,
                balance=request.initial_balance,
                equity=request.initial_balance,
                available_balance=request.initial_balance,
                margin_used=0,
                margin_available=request.initial_balance,
                positions=[],
                orders=[],
                trades=[],
                timestamp=datetime.utcnow()
            )
            
            self._accounts[account_id] = state
            self._account_info[account_id] = account_data
            
            logger.info(f"Paper trading account created: {account_id}")
            return self._to_account_response(account_data, state)
            
        except Exception as e:
            logger.error(f"Error creating account: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Account creation failed: {str(e)}"
            )

    def _to_account_response(
        self,
        account_data: Dict[str, Any],
        state: AccountState
    ) -> AccountResponse:
        """Convert account data to response"""
        return AccountResponse(
            account_id=state.account_id,
            name=account_data['name'],
            account_type=AccountType(account_data['account_type']),
            status=AccountStatus(account_data['status']),
            balance=state.balance,
            equity=state.equity,
            available_balance=state.available_balance,
            margin_used=state.margin_used,
            margin_available=state.margin_available,
            leverage=account_data['leverage'],
            total_pnl=account_data['total_pnl'],
            total_pnl_pct=account_data['total_pnl_pct'],
            positions_count=len(state.positions),
            orders_count=len(state.orders),
            trades_count=len(state.trades),
            created_at=account_data['created_at'],
            updated_at=account_data['updated_at'],
            metadata=account_data['metadata']
        )

    async def get_account(self, account_id: str) -> AccountResponse:
        """
        Get account details.
        
        Args:
            account_id: Account ID
            
        Returns:
            AccountResponse: Account details
        """
        if account_id not in self._accounts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account {account_id} not found"
            )
        
        state = self._accounts[account_id]
        account_data = self._account_info[account_id]
        
        # Update account state
        await self._update_account_state(account_id)
        
        return self._to_account_response(account_data, state)

    async def get_all_accounts(self) -> List[AccountResponse]:
        """Get all accounts"""
        responses = []
        for account_id in self._accounts:
            try:
                response = await self.get_account(account_id)
                responses.append(response)
            except Exception as e:
                logger.error(f"Error getting account {account_id}: {e}")
        return responses

    async def update_account_status(
        self,
        account_id: str,
        status: AccountStatus
    ) -> AccountResponse:
        """
        Update account status.
        
        Args:
            account_id: Account ID
            status: New status
            
        Returns:
            AccountResponse: Updated account
        """
        if account_id not in self._accounts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account {account_id} not found"
            )
        
        self._account_info[account_id]['status'] = status.value
        
        if status == AccountStatus.PAUSED:
            # Cancel pending orders
            await self._cancel_all_orders(account_id)
        
        logger.info(f"Account {account_id} status updated to {status.value}")
        return await self.get_account(account_id)

    # =========================================================================
    # Order Management
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
            
            # Check account status
            if request.account_id not in self._accounts:
                raise ValueError(f"Account {request.account_id} not found")
            
            account_data = self._account_info[request.account_id]
            if account_data['status'] != AccountStatus.ACTIVE.value:
                raise ValueError(f"Account {request.account_id} is not active")
            
            # Get current price
            current_price = await self._get_current_price(request.symbol)
            if not current_price:
                raise ValueError(f"Unable to get price for {request.symbol}")
            
            # Validate order price
            if request.order_type == OrderType.LIMIT and request.price:
                if request.price <= 0:
                    raise ValueError("Limit price must be positive")
            
            # Generate order ID
            order_id = f"order_{int(time.time() * 1000)}_{request.symbol}"
            
            # Create order
            order = {
                'order_id': order_id,
                'account_id': request.account_id,
                'symbol': request.symbol,
                'side': request.side.value,
                'order_type': request.order_type.value,
                'status': OrderStatus.PENDING.value,
                'size': request.size,
                'filled_size': 0,
                'price': request.price or current_price,
                'avg_price': 0,
                'stop_price': request.stop_price,
                'limit_price': request.limit_price,
                'time_in_force': request.time_in_force.value,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'metadata': request.metadata
            }
            
            # Store pending order
            self._pending_orders[order_id] = request
            
            # Process order based on type
            if request.order_type == OrderType.MARKET:
                order = await self._process_market_order(order, current_price)
            elif request.order_type == OrderType.LIMIT:
                order = await self._process_limit_order(order, current_price)
            elif request.order_type == OrderType.STOP:
                order = await self._process_stop_order(order, current_price)
            elif request.order_type == OrderType.STOP_LIMIT:
                order = await self._process_stop_limit_order(order, current_price)
            elif request.order_type == OrderType.TRAILING_STOP:
                order = await self._process_trailing_stop_order(order, current_price)
            
            # Convert to response
            response = OrderResponse(
                order_id=order['order_id'],
                account_id=order['account_id'],
                symbol=order['symbol'],
                side=OrderSide(order['side']),
                order_type=OrderType(order['order_type']),
                status=OrderStatus(order['status']),
                size=order['size'],
                filled_size=order['filled_size'],
                price=order['price'],
                avg_price=order['avg_price'],
                stop_price=order.get('stop_price'),
                limit_price=order.get('limit_price'),
                time_in_force=TimeInForce(order['time_in_force']),
                created_at=order['created_at'],
                updated_at=order['updated_at'],
                filled_at=order.get('filled_at'),
                cancelled_at=order.get('cancelled_at'),
                metadata=order.get('metadata', {})
            )
            
            # Update account state
            await self._update_account_state(request.account_id)
            
            # Store in history
            self._order_history.append(response)
            
            logger.info(f"Order {order_id} placed for {request.symbol}")
            return response
            
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

    async def _process_market_order(
        self,
        order: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Process market order"""
        order['status'] = OrderStatus.FILLED.value
        order['filled_size'] = order['size']
        order['avg_price'] = current_price
        order['filled_at'] = datetime.utcnow()
        order['price'] = current_price
        
        # Update account
        await self._execute_trade(order)
        
        return order

    async def _process_limit_order(
        self,
        order: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Process limit order"""
        # Check if price condition met
        if order['side'] == OrderSide.BUY.value:
            if current_price <= order['price']:
                # Order fills
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
            else:
                order['status'] = OrderStatus.OPEN.value
        else:  # SELL
            if current_price >= order['price']:
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
            else:
                order['status'] = OrderStatus.OPEN.value
        
        return order

    async def _process_stop_order(
        self,
        order: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Process stop order"""
        # Stop order becomes market order when triggered
        if order['side'] == OrderSide.BUY.value:
            if current_price >= order['stop_price']:
                # Triggered - convert to market order
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
            else:
                order['status'] = OrderStatus.OPEN.value
        else:  # SELL
            if current_price <= order['stop_price']:
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
            else:
                order['status'] = OrderStatus.OPEN.value
        
        return order

    async def _process_stop_limit_order(
        self,
        order: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Process stop-limit order"""
        # Stop-limit becomes limit order when triggered
        if order['side'] == OrderSide.BUY.value:
            if current_price >= order['stop_price']:
                # Triggered - now check limit price
                if current_price <= order['limit_price']:
                    order['status'] = OrderStatus.FILLED.value
                    order['filled_size'] = order['size']
                    order['avg_price'] = current_price
                    order['price'] = current_price
                    order['filled_at'] = datetime.utcnow()
                    await self._execute_trade(order)
                else:
                    order['status'] = OrderStatus.OPEN.value
            else:
                order['status'] = OrderStatus.OPEN.value
        else:  # SELL
            if current_price <= order['stop_price']:
                if current_price >= order['limit_price']:
                    order['status'] = OrderStatus.FILLED.value
                    order['filled_size'] = order['size']
                    order['avg_price'] = current_price
                    order['price'] = current_price
                    order['filled_at'] = datetime.utcnow()
                    await self._execute_trade(order)
                else:
                    order['status'] = OrderStatus.OPEN.value
            else:
                order['status'] = OrderStatus.OPEN.value
        
        return order

    async def _process_trailing_stop_order(
        self,
        order: Dict[str, Any],
        current_price: float
    ) -> Dict[str, Any]:
        """Process trailing stop order"""
        # Store initial price for trailing
        if 'trail_initial_price' not in order:
            order['trail_initial_price'] = current_price
            order['trail_high'] = current_price
            order['trail_low'] = current_price
        
        # Update trail prices
        if current_price > order['trail_high']:
            order['trail_high'] = current_price
        if current_price < order['trail_low']:
            order['trail_low'] = current_price
        
        # Calculate trail stop price
        if order['side'] == OrderSide.BUY.value:
            # Buy trailing stop - stop price moves up with price
            trail_distance = order.get('trail_distance', 0.02)
            stop_price = order['trail_high'] * (1 - trail_distance)
            order['stop_price'] = stop_price
            
            if current_price >= stop_price:
                # Not triggered yet
                order['status'] = OrderStatus.OPEN.value
            else:
                # Triggered
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
        else:  # SELL
            # Sell trailing stop - stop price moves down with price
            trail_distance = order.get('trail_distance', 0.02)
            stop_price = order['trail_low'] * (1 + trail_distance)
            order['stop_price'] = stop_price
            
            if current_price <= stop_price:
                order['status'] = OrderStatus.OPEN.value
            else:
                order['status'] = OrderStatus.FILLED.value
                order['filled_size'] = order['size']
                order['avg_price'] = current_price
                order['price'] = current_price
                order['filled_at'] = datetime.utcnow()
                await self._execute_trade(order)
        
        return order

    async def _execute_trade(self, order: Dict[str, Any]) -> None:
        """Execute trade and update account"""
        account_id = order['account_id']
        state = self._accounts[account_id]
        
        # Calculate trade value
        trade_value = order['size'] * order['avg_price']
        
        # Update balance
        if order['side'] == OrderSide.BUY.value:
            state.balance -= trade_value
        else:  # SELL
            state.balance += trade_value
        
        # Update position
        await self._update_position(account_id, order)
        
        # Record trade
        trade = {
            'order_id': order['order_id'],
            'symbol': order['symbol'],
            'side': order['side'],
            'size': order['size'],
            'price': order['avg_price'],
            'timestamp': order['filled_at'],
            'pnl': 0  # Will be calculated on position close
        }
        
        state.trades.append(trade)
        state.equity = state.balance + await self._calculate_position_value(account_id)
        
        # Update account info
        self._account_info[account_id]['trades_count'] += 1
        self._account_info[account_id]['updated_at'] = datetime.utcnow()

    async def _update_position(
        self,
        account_id: str,
        order: Dict[str, Any]
    ) -> None:
        """Update position for account"""
        state = self._accounts[account_id]
        
        # Find existing position
        existing_pos = None
        for pos in state.positions:
            if pos['symbol'] == order['symbol'] and pos['side'] == order['side']:
                existing_pos = pos
                break
        
        if existing_pos:
            # Update existing position
            total_size = existing_pos['size'] + order['size']
            total_cost = existing_pos['size'] * existing_pos['entry_price'] + order['size'] * order['avg_price']
            existing_pos['size'] = total_size
            existing_pos['entry_price'] = total_cost / total_size if total_size > 0 else 0
            existing_pos['updated_at'] = datetime.utcnow()
        else:
            # Create new position
            state.positions.append({
                'position_id': f"pos_{int(time.time() * 1000)}_{order['symbol']}",
                'symbol': order['symbol'],
                'side': order['side'],
                'size': order['size'],
                'entry_price': order['avg_price'],
                'current_price': order['avg_price'],
                'pnl': 0,
                'pnl_pct': 0,
                'value': order['size'] * order['avg_price'],
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })

    async def _calculate_position_value(self, account_id: str) -> float:
        """Calculate total position value"""
        state = self._accounts[account_id]
        total_value = 0
        
        for pos in state.positions:
            current_price = await self._get_current_price(pos['symbol'])
            if current_price:
                pos['current_price'] = current_price
                pos['value'] = pos['size'] * current_price
                total_value += pos['value']
        
        return total_value

    # =========================================================================
    # Account State Update
    # =========================================================================

    async def _update_account_state(self, account_id: str) -> None:
        """Update account state"""
        state = self._accounts[account_id]
        
        # Update positions
        position_value = await self._calculate_position_value(account_id)
        
        # Calculate equity
        state.equity = state.balance + position_value
        
        # Calculate PnL
        total_pnl = state.equity - self._account_info[account_id]['initial_balance']
        self._account_info[account_id]['total_pnl'] = total_pnl
        self._account_info[account_id]['total_pnl_pct'] = (total_pnl / self._account_info[account_id]['initial_balance']) * 100
        
        # Update margin
        state.margin_used = position_value * 0.5  # 50% margin requirement
        state.margin_available = state.equity - state.margin_used
        
        state.timestamp = datetime.utcnow()

    # =========================================================================
    # Order Cancellation
    # =========================================================================

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: Success indicator
        """
        if order_id not in self._pending_orders:
            return False
        
        del self._pending_orders[order_id]
        
        # Update order in history
        for order in self._order_history:
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.utcnow()
                order.cancelled_at = datetime.utcnow()
                break
        
        logger.info(f"Order {order_id} cancelled")
        return True

    async def _cancel_all_orders(self, account_id: str) -> int:
        """Cancel all orders for account"""
        cancelled = 0
        for order_id, request in list(self._pending_orders.items()):
            if request.account_id == account_id:
                if await self.cancel_order(order_id):
                    cancelled += 1
        return cancelled

    # =========================================================================
    # Market Data
    # =========================================================================

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        # Check cache
        if symbol in self._price_cache:
            cache_time = self._price_cache[symbol].get('timestamp')
            if cache_time and (datetime.utcnow() - cache_time).seconds < 5:
                return self._price_cache[symbol]['price']
        
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        self._price_cache[symbol] = {
                            'price': price,
                            'timestamp': datetime.utcnow()
                        }
                        return price
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting price for {symbol}: {e}")
        
        # Generate mock price
        mock_price = 100.0 + np.random.normal(0, 0.5)
        self._price_cache[symbol] = {
            'price': mock_price,
            'timestamp': datetime.utcnow()
        }
        return mock_price

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the paper trading account"""
        self._accounts.clear()
        self._account_info.clear()
        self._pending_orders.clear()
        self._order_history.clear()
        self._price_cache.clear()
        logger.info("PaperTradingAccount closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading", tags=["Paper Trading"])


async def get_account() -> PaperTradingAccount:
    """Dependency to get PaperTradingAccount instance"""
    return PaperTradingAccount()


@router.post("/account", response_model=AccountResponse)
async def create_account(
    request: AccountCreateRequest,
    account: PaperTradingAccount = Depends(get_account)
):
    """Create a paper trading account"""
    return await account.create_account(request)


@router.get("/account/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: str,
    account: PaperTradingAccount = Depends(get_account)
):
    """Get account details"""
    return await account.get_account(account_id)


@router.get("/accounts")
async def get_all_accounts(
    account: PaperTradingAccount = Depends(get_account)
):
    """Get all accounts"""
    return await account.get_all_accounts()


@router.put("/account/{account_id}/status")
async def update_account_status(
    account_id: str,
    status: AccountStatus = Body(..., embed=True),
    account: PaperTradingAccount = Depends(get_account)
):
    """Update account status"""
    return await account.update_account_status(account_id, status)


@router.post("/order", response_model=OrderResponse)
async def place_order(
    request: OrderRequest,
    account: PaperTradingAccount = Depends(get_account)
):
    """Place an order"""
    return await account.place_order(request)


@router.delete("/order/{order_id}")
async def cancel_order(
    order_id: str,
    account: PaperTradingAccount = Depends(get_account)
):
    """Cancel an order"""
    success = await account.cancel_order(order_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    return {"success": True}


@router.get("/order-types")
async def get_order_types():
    """Get available order types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in OrderType
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
    'PaperTradingAccount',
    'AccountStatus',
    'AccountType',
    'OrderStatus',
    'OrderType',
    'OrderSide',
    'TimeInForce',
    'AccountCreateRequest',
    'AccountResponse',
    'OrderRequest',
    'OrderResponse',
    'PositionResponse',
    'AccountState',
    'TradeResult',
    'router'
]
