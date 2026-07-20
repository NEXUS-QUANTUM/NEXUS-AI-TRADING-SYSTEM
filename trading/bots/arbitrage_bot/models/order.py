# trading/bots/arbitrage_bot/models/order.py
# NEXUS AI TRADING SYSTEM - ORDER MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for orders, order books, order management,
# and order execution across multiple exchanges for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Order Models

This module provides comprehensive data models for:
- Order creation and management
- Order status tracking and updates
- Order book management
- Order execution and settlement
- Multi-exchange order synchronization
- Order history and analytics
- Risk management and position sizing
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Types of orders."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    OCO = "oco"  # One-Cancels-Other
    OTO = "oto"  # One-Triggers-Other
    OTOCO = "otoco"  # One-Triggers-One-Cancels-Other
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    POST_ONLY = "post_only"
    REDUCE_ONLY = "reduce_only"
    CLOSE = "close"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    PENDING_CANCEL = "pending_cancel"
    PENDING_REPLACE = "pending_replace"
    REPLACED = "replaced"
    PARTIALLY_CANCELLED = "partially_cancelled"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTT = "GTT"  # Good Till Time
    DAY = "DAY"  # Day order
    MINUTE = "MINUTE"  # Minute order
    GTX = "GTX"  # Good Till Crossing


class OrderSource(str, Enum):
    """Source of order creation."""
    MANUAL = "manual"
    API = "api"
    BOT = "bot"
    STRATEGY = "strategy"
    ARBITRAGE = "arbitrage"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    LIQUIDATION = "liquidation"
    AUTO = "auto"


class OrderDestination(str, Enum):
    """Order destination."""
    EXCHANGE = "exchange"
    DEX = "dex"
    OTC = "otc"
    P2P = "p2p"
    BROKER = "broker"


class OrderCategory(str, Enum):
    """Order category for classification."""
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTIONS = "options"
    SWAP = "swap"
    ETF = "etf"


class OrderEvent(str, Enum):
    """Order events for status updates."""
    CREATED = "created"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    OPEN = "open"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REPLACED = "replaced"
    PENDING_CANCEL = "pending_cancel"


# ====================================================================================
# ORDER MODELS
# ====================================================================================

@dataclass
class Order:
    """
    Comprehensive order model.
    """
    # Core fields
    order_id: str = field(default_factory=lambda: str(uuid4()))
    client_order_id: str = ""
    exchange: str = ""
    exchange_order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    type: OrderType = OrderType.MARKET
    
    # Order details
    quantity: float = 0.0
    price: float = 0.0
    stop_price: float = 0.0
    limit_price: float = 0.0
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    executed_value: float = 0.0
    remaining_quantity: float = 0.0
    
    # Fees
    fee: float = 0.0
    fee_currency: str = ""
    fee_rate: float = 0.0
    
    # Status
    status: OrderStatus = OrderStatus.PENDING
    time_in_force: TimeInForce = TimeInForce.GTC
    expires_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    
    # Source and destination
    source: OrderSource = OrderSource.BOT
    destination: OrderDestination = OrderDestination.EXCHANGE
    category: OrderCategory = OrderCategory.SPOT
    
    # Risk management
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    trailing_stop_percent: float = 0.0
    max_slippage: float = 0.0
    
    # Position management
    position_id: str = ""
    reduce_only: bool = False
    post_only: bool = False
    leverage: int = 1
    
    # Parent-child relationships
    parent_order_id: str = ""
    child_order_ids: List[str] = field(default_factory=list)
    group_id: str = ""
    
    # Execution
    execution_time_ms: float = 0.0
    latency_ms: float = 0.0
    slippage: float = 0.0
    
    # Market conditions
    market_price: float = 0.0
    market_depth: float = 0.0
    volatility: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Audit
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.remaining_quantity = self.quantity - self.executed_quantity
        self.executed_value = self.executed_quantity * self.executed_price
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "exchange": self.exchange,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "side": self.side.value if self.side else None,
            "type": self.type.value if self.type else None,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "limit_price": self.limit_price,
            "executed_quantity": self.executed_quantity,
            "executed_price": self.executed_price,
            "executed_value": self.executed_value,
            "remaining_quantity": self.remaining_quantity,
            "fee": self.fee,
            "fee_currency": self.fee_currency,
            "fee_rate": self.fee_rate,
            "status": self.status.value if self.status else None,
            "time_in_force": self.time_in_force.value if self.time_in_force else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "expired_at": self.expired_at.isoformat() if self.expired_at else None,
            "source": self.source.value if self.source else None,
            "destination": self.destination.value if self.destination else None,
            "category": self.category.value if self.category else None,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "trailing_stop_percent": self.trailing_stop_percent,
            "max_slippage": self.max_slippage,
            "position_id": self.position_id,
            "reduce_only": self.reduce_only,
            "post_only": self.post_only,
            "leverage": self.leverage,
            "parent_order_id": self.parent_order_id,
            "child_order_ids": self.child_order_ids,
            "group_id": self.group_id,
            "execution_time_ms": self.execution_time_ms,
            "latency_ms": self.latency_ms,
            "slippage": self.slippage,
            "market_price": self.market_price,
            "market_depth": self.market_depth,
            "volatility": self.volatility,
            "metadata": self.metadata,
            "tags": self.tags,
            "audit_trail": self.audit_trail
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create from dictionary."""
        order = cls(
            order_id=data.get("order_id", str(uuid4())),
            client_order_id=data.get("client_order_id", ""),
            exchange=data.get("exchange", ""),
            exchange_order_id=data.get("exchange_order_id", ""),
            symbol=data.get("symbol", ""),
            side=OrderSide(data["side"]) if data.get("side") else OrderSide.BUY,
            type=OrderType(data["type"]) if data.get("type") else OrderType.MARKET,
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            stop_price=data.get("stop_price", 0.0),
            limit_price=data.get("limit_price", 0.0),
            executed_quantity=data.get("executed_quantity", 0.0),
            executed_price=data.get("executed_price", 0.0),
            executed_value=data.get("executed_value", 0.0),
            remaining_quantity=data.get("remaining_quantity", 0.0),
            fee=data.get("fee", 0.0),
            fee_currency=data.get("fee_currency", ""),
            fee_rate=data.get("fee_rate", 0.0),
            status=OrderStatus(data["status"]) if data.get("status") else OrderStatus.PENDING,
            time_in_force=TimeInForce(data["time_in_force"]) if data.get("time_in_force") else TimeInForce.GTC,
            source=OrderSource(data["source"]) if data.get("source") else OrderSource.BOT,
            destination=OrderDestination(data["destination"]) if data.get("destination") else OrderDestination.EXCHANGE,
            category=OrderCategory(data["category"]) if data.get("category") else OrderCategory.SPOT,
            stop_loss_price=data.get("stop_loss_price", 0.0),
            take_profit_price=data.get("take_profit_price", 0.0),
            trailing_stop_percent=data.get("trailing_stop_percent", 0.0),
            max_slippage=data.get("max_slippage", 0.0),
            position_id=data.get("position_id", ""),
            reduce_only=data.get("reduce_only", False),
            post_only=data.get("post_only", False),
            leverage=data.get("leverage", 1),
            parent_order_id=data.get("parent_order_id", ""),
            child_order_ids=data.get("child_order_ids", []),
            group_id=data.get("group_id", ""),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            latency_ms=data.get("latency_ms", 0.0),
            slippage=data.get("slippage", 0.0),
            market_price=data.get("market_price", 0.0),
            market_depth=data.get("market_depth", 0.0),
            volatility=data.get("volatility", 0.0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            audit_trail=data.get("audit_trail", [])
        )
        
        # Parse timestamps
        if data.get("expires_at"):
            order.expires_at = datetime.fromisoformat(data["expires_at"])
        if data.get("created_at"):
            order.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            order.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("submitted_at"):
            order.submitted_at = datetime.fromisoformat(data["submitted_at"])
        if data.get("accepted_at"):
            order.accepted_at = datetime.fromisoformat(data["accepted_at"])
        if data.get("filled_at"):
            order.filled_at = datetime.fromisoformat(data["filled_at"])
        if data.get("cancelled_at"):
            order.cancelled_at = datetime.fromisoformat(data["cancelled_at"])
        if data.get("expired_at"):
            order.expired_at = datetime.fromisoformat(data["expired_at"])
            
        order.__post_init__()
        return order
        
    def update_status(self, status: OrderStatus, event: Optional[OrderEvent] = None) -> None:
        """
        Update order status.
        
        Args:
            status: New status
            event: Order event
        """
        old_status = self.status
        self.status = status
        self.updated_at = datetime.utcnow()
        
        # Record audit trail
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "old_status": old_status.value if old_status else None,
            "new_status": status.value if status else None,
            "event": event.value if event else None
        }
        self.audit_trail.append(audit_entry)
        
        # Update timestamps based on status
        if status == OrderStatus.SUBMITTED:
            self.submitted_at = datetime.utcnow()
        elif status == OrderStatus.ACCEPTED:
            self.accepted_at = datetime.utcnow()
        elif status == OrderStatus.FILLED:
            self.filled_at = datetime.utcnow()
        elif status == OrderStatus.CANCELLED:
            self.cancelled_at = datetime.utcnow()
        elif status == OrderStatus.EXPIRED:
            self.expired_at = datetime.utcnow()
            
    def update_execution(self, executed_quantity: float, executed_price: float, fee: float = 0.0) -> None:
        """
        Update order execution details.
        
        Args:
            executed_quantity: Executed quantity
            executed_price: Executed price
            fee: Transaction fee
        """
        self.executed_quantity += executed_quantity
        self.executed_price = executed_price
        self.executed_value = self.executed_quantity * self.executed_price
        self.remaining_quantity = self.quantity - self.executed_quantity
        self.fee += fee
        self.updated_at = datetime.utcnow()
        
        # Update status based on fill
        if self.remaining_quantity <= 0:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.utcnow()
        else:
            self.status = OrderStatus.PARTIALLY_FILLED
            
        # Calculate execution metrics
        if self.executed_quantity > 0:
            self.slippage = (self.executed_price - self.price) / self.price * 100
            
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, 
                               OrderStatus.ACCEPTED, OrderStatus.OPEN, 
                               OrderStatus.PARTIALLY_FILLED]
        
    def is_completed(self) -> bool:
        """Check if order is completed."""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, 
                               OrderStatus.REJECTED, OrderStatus.EXPIRED, 
                               OrderStatus.FAILED]
        
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED
        
    def is_partially_filled(self) -> bool:
        """Check if order is partially filled."""
        return self.status == OrderStatus.PARTIALLY_FILLED
        
    def get_fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.quantity == 0:
            return 0.0
        return (self.executed_quantity / self.quantity) * 100
        
    def get_average_price(self) -> float:
        """Get average execution price."""
        if self.executed_quantity == 0:
            return 0.0
        return self.executed_value / self.executed_quantity


# ====================================================================================
# ORDER BOOK MODELS
# ====================================================================================

@dataclass
class OrderBookEntry:
    """
    Single entry in an order book.
    """
    price: float = 0.0
    quantity: float = 0.0
    order_count: int = 0
    orders: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "price": self.price,
            "quantity": self.quantity,
            "order_count": self.order_count,
            "orders": self.orders
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderBookEntry":
        """Create from dictionary."""
        return cls(
            price=data.get("price", 0.0),
            quantity=data.get("quantity", 0.0),
            order_count=data.get("order_count", 0),
            orders=data.get("orders", [])
        )


@dataclass
class OrderBook:
    """
    Complete order book model.
    """
    symbol: str = ""
    exchange: str = ""
    bids: List[OrderBookEntry] = field(default_factory=list)
    asks: List[OrderBookEntry] = field(default_factory=list)
    last_update_id: int = 0
    sequence_id: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Statistics
    bid_count: int = 0
    ask_count: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    mid_price: float = 0.0
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.bids:
            self.bid_count = len(self.bids)
            self.best_bid = self.bids[0].price if self.bids else 0.0
        if self.asks:
            self.ask_count = len(self.asks)
            self.best_ask = self.asks[0].price if self.asks else 0.0
        self.spread = self.best_ask - self.best_bid if self.best_bid and self.best_ask else 0.0
        self.mid_price = (self.best_ask + self.best_bid) / 2 if self.best_bid and self.best_ask else 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bids": [entry.to_dict() for entry in self.bids],
            "asks": [entry.to_dict() for entry in self.asks],
            "last_update_id": self.last_update_id,
            "sequence_id": self.sequence_id,
            "timestamp": self.timestamp.isoformat(),
            "bid_count": self.bid_count,
            "ask_count": self.ask_count,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread": self.spread,
            "mid_price": self.mid_price
        }


# ====================================================================================
# ORDER HISTORY MODELS
# ====================================================================================

@dataclass
class OrderHistory:
    """
    Order history tracking.
    """
    order_id: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "events": self.events,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
        
    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Add an event to history.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "data": data
        }
        self.events.append(event)
        self.updated_at = datetime.utcnow()


# ====================================================================================
# ORDER STATISTICS MODELS
# ====================================================================================

@dataclass
class OrderStatistics:
    """
    Order performance statistics.
    """
    # Core fields
    exchange: str = ""
    symbol: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Order counts
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    cancelled_orders: int = 0
    partial_orders: int = 0
    pending_orders: int = 0
    
    # Volume
    total_quantity: float = 0.0
    total_value: float = 0.0
    avg_order_size: float = 0.0
    max_order_size: float = 0.0
    min_order_size: float = 0.0
    
    # Execution
    avg_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    avg_slippage: float = 0.0
    max_slippage: float = 0.0
    
    # Fees
    total_fees: float = 0.0
    avg_fee: float = 0.0
    fee_rate: float = 0.0
    
    # Success rates
    success_rate: float = 0.0
    fill_rate: float = 0.0
    cancellation_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_orders": self.total_orders,
            "successful_orders": self.successful_orders,
            "failed_orders": self.failed_orders,
            "cancelled_orders": self.cancelled_orders,
            "partial_orders": self.partial_orders,
            "pending_orders": self.pending_orders,
            "total_quantity": self.total_quantity,
            "total_value": self.total_value,
            "avg_order_size": self.avg_order_size,
            "max_order_size": self.max_order_size,
            "min_order_size": self.min_order_size,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "max_execution_time_ms": self.max_execution_time_ms,
            "min_execution_time_ms": self.min_execution_time_ms,
            "avg_slippage": self.avg_slippage,
            "max_slippage": self.max_slippage,
            "total_fees": self.total_fees,
            "avg_fee": self.avg_fee,
            "fee_rate": self.fee_rate,
            "success_rate": self.success_rate,
            "fill_rate": self.fill_rate,
            "cancellation_rate": self.cancellation_rate
        }


# ====================================================================================
# ORDER FILTER MODELS
# ====================================================================================

@dataclass
class OrderFilter:
    """
    Filter for orders.
    """
    # Basic filters
    exchanges: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    sides: List[OrderSide] = field(default_factory=list)
    types: List[OrderType] = field(default_factory=list)
    statuses: List[OrderStatus] = field(default_factory=list)
    sources: List[OrderSource] = field(default_factory=list)
    categories: List[OrderCategory] = field(default_factory=list)
    
    # Time filters
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    
    # Financial filters
    min_quantity: float = 0.0
    max_quantity: float = float('inf')
    min_value: float = 0.0
    max_value: float = float('inf')
    min_fee: float = 0.0
    max_fee: float = float('inf')
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Sorting
    sort_by: str = "created_at"
    sort_order: str = "desc"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchanges": self.exchanges,
            "symbols": self.symbols,
            "sides": [s.value for s in self.sides],
            "types": [t.value for t in self.types],
            "statuses": [s.value for s in self.statuses],
            "sources": [s.value for s in self.sources],
            "categories": [c.value for c in self.categories],
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat() if self.until else None,
            "min_quantity": self.min_quantity,
            "max_quantity": self.max_quantity,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "min_fee": self.min_fee,
            "max_fee": self.max_fee,
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_market_order(
    exchange: str,
    symbol: str,
    side: OrderSide,
    quantity: float,
    **kwargs
) -> Order:
    """
    Create a market order.
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: Buy or sell
        quantity: Order quantity
        **kwargs: Additional order fields
        
    Returns:
        Order instance
    """
    return Order(
        exchange=exchange,
        symbol=symbol,
        side=side,
        type=OrderType.MARKET,
        quantity=quantity,
        **kwargs
    )


def create_limit_order(
    exchange: str,
    symbol: str,
    side: OrderSide,
    quantity: float,
    price: float,
    **kwargs
) -> Order:
    """
    Create a limit order.
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: Buy or sell
        quantity: Order quantity
        price: Limit price
        **kwargs: Additional order fields
        
    Returns:
        Order instance
    """
    return Order(
        exchange=exchange,
        symbol=symbol,
        side=side,
        type=OrderType.LIMIT,
        quantity=quantity,
        price=price,
        **kwargs
    )


def create_stop_order(
    exchange: str,
    symbol: str,
    side: OrderSide,
    quantity: float,
    stop_price: float,
    **kwargs
) -> Order:
    """
    Create a stop order.
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: Buy or sell
        quantity: Order quantity
        stop_price: Stop price
        **kwargs: Additional order fields
        
    Returns:
        Order instance
    """
    return Order(
        exchange=exchange,
        symbol=symbol,
        side=side,
        type=OrderType.STOP,
        quantity=quantity,
        stop_price=stop_price,
        **kwargs
    )


def calculate_order_value(
    quantity: float,
    price: float,
    fee_rate: float = 0.001
) -> Dict[str, float]:
    """
    Calculate order value including fees.
    
    Args:
        quantity: Order quantity
        price: Order price
        fee_rate: Fee rate (default 0.1%)
        
    Returns:
        Dict with value, fee, total
    """
    value = quantity * price
    fee = value * fee_rate
    total = value + fee
    
    return {
        "value": value,
        "fee": fee,
        "total": total
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'TimeInForce',
    'OrderSource',
    'OrderDestination',
    'OrderCategory',
    'OrderEvent',
    
    # Core Models
    'Order',
    'OrderBookEntry',
    'OrderBook',
    'OrderHistory',
    'OrderStatistics',
    'OrderFilter',
    
    # Helper Functions
    'create_market_order',
    'create_limit_order',
    'create_stop_order',
    'calculate_order_value',
]
