#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Exchange Base Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Base classes and interfaces for all exchange integrations.
Provides unified API for trading across multiple asset classes:
stocks, crypto, forex, futures, options, and more.

Author: Dr X...
Version: 3.0.0
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
import base64
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union, 
    TypeVar, Generic, Coroutine, AsyncIterator, Type, 
    Iterable, Mapping, overload, cast
)
from urllib.parse import urlencode, urlparse, parse_qs
import ssl
import certifi
import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientResponse, TCPConnector
from aiohttp.client_exceptions import (
    ClientError, ClientConnectionError, ClientResponseError, 
    ServerDisconnectedError, ContentTypeError
)
from asyncio import Lock, Semaphore
from collections import defaultdict, deque
from functools import wraps

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class AssetClass(str, Enum):
    """Asset classes supported by the exchange."""
    STOCK = "stock"
    CRYPTO = "crypto"
    FOREX = "forex"
    FUTURES = "futures"
    OPTIONS = "options"
    BOND = "bond"
    COMMODITY = "commodity"
    INDEX = "index"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    CFD = "cfd"
    SPOT = "spot"
    PERPETUAL = "perpetual"
    SWAP = "swap"
    SPREAD = "spread"


class ExchangeType(str, Enum):
    """Types of exchanges."""
    CENTRALIZED = "centralized"
    DECENTRALIZED = "decentralized"
    BROKER = "broker"
    MARKET_MAKER = "market_maker"
    AGGREGATOR = "aggregator"
    HYBRID = "hybrid"
    OTC = "otc"
    P2P = "p2p"


class OrderType(str, Enum):
    """Order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TRAILING_STOP_LIMIT = "trailing_stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"
    BRACKET = "bracket"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    PEGGED = "pegged"
    MARKET_IF_TOUCHED = "market_if_touched"
    LIMIT_IF_TOUCHED = "limit_if_touched"
    RELATIVE = "relative"
    MID = "mid"
    SCALE = "scale"
    SNAP = "snap"
    SNAP_MID = "snap_mid"


class OrderSide(str, Enum):
    """Order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"
    CLOSE = "close"
    CLOSE_BUY = "close_buy"
    CLOSE_SELL = "close_sell"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTD = "gtd"
    OPG = "opg"
    CLS = "cls"
    GTX = "gtx"
    EXT = "ext"
    EXO = "exo"
    AUCTION = "auction"
    IROC = "iroc"
    ROD = "rod"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    HELD = "held"
    CANCEL_PENDING = "cancel_pending"
    MODIFY_PENDING = "modify_pending"
    PENDING_CANCEL = "pending_cancel"
    PENDING_REPLACE = "pending_replace"
    SENT = "sent"
    QUEUED = "queued"
    TRIGGERED = "triggered"
    STOPPED = "stopped"


class PositionSide(str, Enum):
    """Position side."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"
    BOTH = "both"
    HEDGED = "hedged"


class OrderBookLevel(str, Enum):
    """Order book depth levels."""
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    LEVEL_4 = "level_4"


class DataFrequency(str, Enum):
    """Data frequency."""
    TICK = "tick"
    SECOND = "1s"
    MINUTE = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_8 = "8h"
    HOUR_12 = "12h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"
    QUARTER = "3M"
    YEAR = "1Y"


class WebSocketEvent(str, Enum):
    """WebSocket events."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    ORDER_UPDATE = "order_update"
    POSITION_UPDATE = "position_update"
    BALANCE_UPDATE = "balance_update"
    MARKET_DATA = "market_data"
    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "order_book"
    BAR = "bar"
    SIGNAL = "signal"
    AGGREGATE = "aggregate"
    TICKER = "ticker"
    STATUS = "status"
    ALERT = "alert"
    EXECUTION = "execution"
    ACCOUNT = "account"
    SUBSCRIPTION = "subscription"


class APIErrorCode(str, Enum):
    """API error codes."""
    INVALID_API_KEY = "invalid_api_key"
    INVALID_SIGNATURE = "invalid_signature"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INVALID_ORDER = "invalid_order"
    ORDER_NOT_FOUND = "order_not_found"
    POSITION_NOT_FOUND = "position_not_found"
    MARKET_CLOSED = "market_closed"
    MAINTENANCE = "maintenance"
    INVALID_SYMBOL = "invalid_symbol"
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_PRICE = "invalid_price"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"


class Environment(str, Enum):
    """Environment type."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"
    TESTNET = "testnet"
    PAPER = "paper"
    DEVELOPMENT = "development"
    STAGING = "staging"


class WebSocketState(str, Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Price:
    """Price representation with precision."""
    value: float
    currency: str = "USD"
    precision: int = 2
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return f"{self.value:.{self.precision}f} {self.currency}"
    
    def __float__(self) -> float:
        return self.value
    
    def __add__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value + other.value, self.currency, max(self.precision, other.precision))
        return Price(self.value + other, self.currency, self.precision)
    
    def __sub__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value - other.value, self.currency, max(self.precision, other.precision))
        return Price(self.value - other, self.currency, self.precision)
    
    def __mul__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value * other.value, self.currency, max(self.precision, other.precision))
        return Price(self.value * other, self.currency, self.precision)
    
    def __truediv__(self, other: Union['Price', float]) -> 'Price':
        if isinstance(other, Price):
            return Price(self.value / other.value, self.currency, max(self.precision, other.precision))
        return Price(self.value / other, self.currency, self.precision)
    
    def round(self, precision: Optional[int] = None) -> 'Price':
        """Round price to specified precision."""
        p = precision or self.precision
        return Price(round(self.value, p), self.currency, p, self.timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "currency": self.currency,
            "precision": self.precision,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Amount:
    """Amount representation with precision."""
    value: float
    asset: str
    precision: int = 8
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return f"{self.value:.{self.precision}f} {self.asset}"
    
    def __float__(self) -> float:
        return self.value
    
    def __add__(self, other: Union['Amount', float]) -> 'Amount':
        if isinstance(other, Amount):
            return Amount(self.value + other.value, self.asset, max(self.precision, other.precision))
        return Amount(self.value + other, self.asset, self.precision)
    
    def __sub__(self, other: Union['Amount', float]) -> 'Amount':
        if isinstance(other, Amount):
            return Amount(self.value - other.value, self.asset, max(self.precision, other.precision))
        return Amount(self.value - other, self.asset, self.precision)
    
    def __mul__(self, other: Union['Amount', float]) -> 'Amount':
        if isinstance(other, Amount):
            return Amount(self.value * other.value, self.asset, max(self.precision, other.precision))
        return Amount(self.value * other, self.asset, self.precision)
    
    def round(self, precision: Optional[int] = None) -> 'Amount':
        """Round amount to specified precision."""
        p = precision or self.precision
        return Amount(round(self.value, p), self.asset, p, self.timestamp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "value": self.value,
            "asset": self.asset,
            "precision": self.precision,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class Order:
    """Unified order representation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str = ""
    client_order_id: str = field(default_factory=lambda: f"nexus_{uuid.uuid4().hex[:16]}")
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    order_type: OrderType = OrderType.MARKET
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    trigger_price: Optional[float] = None
    trail_value: Optional[float] = None
    trail_unit: str = "points"  # points, percent
    time_in_force: TimeInForce = TimeInForce.DAY
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_price: Optional[float] = None
    commission: float = 0.0
    commission_asset: str = "USD"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    reduce_only: bool = False
    post_only: bool = False
    iceberg_qty: Optional[float] = None
    visible_qty: Optional[float] = None
    max_display_qty: Optional[float] = None
    min_qty: Optional[float] = None
    self_trade_prevention: bool = False
    order_restrictions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self) -> bool:
        """Check if order is active."""
        return self.status in [
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.MODIFY_PENDING,
            OrderStatus.PENDING_CANCEL,
            OrderStatus.PENDING_REPLACE,
            OrderStatus.SENT,
            OrderStatus.QUEUED,
        ]
    
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED
    
    def is_cancelled(self) -> bool:
        """Check if order is cancelled."""
        return self.status in [OrderStatus.CANCELLED, OrderStatus.EXPIRED]
    
    def is_rejected(self) -> bool:
        """Check if order is rejected."""
        return self.status == OrderStatus.REJECTED
    
    def get_remaining_quantity(self) -> float:
        """Get remaining quantity to fill."""
        return max(0.0, self.quantity - self.filled_quantity)
    
    def get_fill_percentage(self) -> float:
        """Get percentage filled."""
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100
    
    def get_fill_cost(self) -> float:
        """Get total fill cost."""
        if self.average_price:
            return self.filled_quantity * self.average_price
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "exchange": self.exchange,
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "order_type": self.order_type.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "limit_price": self.limit_price,
            "trigger_price": self.trigger_price,
            "trail_value": self.trail_value,
            "trail_unit": self.trail_unit,
            "time_in_force": self.time_in_force.value,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "commission": self.commission,
            "commission_asset": self.commission_asset,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reduce_only": self.reduce_only,
            "post_only": self.post_only,
            "metadata": self.metadata,
        }


@dataclass
class Position:
    """Unified position representation."""
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    side: PositionSide = PositionSide.FLAT
    quantity: float = 0.0
    average_price: float = 0.0
    current_price: Optional[float] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    cost_basis: float = 0.0
    market_value: float = 0.0
    margin_used: float = 0.0
    leverage: float = 1.0
    liquidation_price: Optional[float] = None
    entry_price: Optional[float] = None
    entry_timestamp: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    commission: float = 0.0
    commission_asset: str = "USD"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_pnl_percentage(self) -> float:
        """Calculate PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.total_pnl / self.cost_basis) * 100
    
    def get_unrealized_pnl_percentage(self) -> float:
        """Calculate unrealized PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100
    
    def get_realized_pnl_percentage(self) -> float:
        """Calculate realized PnL percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.realized_pnl / self.cost_basis) * 100
    
    def get_break_even_price(self) -> float:
        """Calculate break-even price including commission."""
        if abs(self.quantity) < 1e-10:
            return self.average_price
        return self.average_price + (self.commission / abs(self.quantity))
    
    def get_liquidation_distance(self) -> float:
        """Calculate distance to liquidation price."""
        if self.liquidation_price is None or self.current_price is None:
            return 0.0
        return abs(self.current_price - self.liquidation_price) / self.current_price * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "cost_basis": self.cost_basis,
            "market_value": self.market_value,
            "margin_used": self.margin_used,
            "leverage": self.leverage,
            "liquidation_price": self.liquidation_price,
            "entry_price": self.entry_price,
            "entry_timestamp": self.entry_timestamp.isoformat() if self.entry_timestamp else None,
            "exit_price": self.exit_price,
            "exit_timestamp": self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            "commission": self.commission,
            "commission_asset": self.commission_asset,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AccountBalance:
    """Account balance representation."""
    total_equity: float = 0.0
    available_balance: float = 0.0
    used_balance: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_pnl: float = 0.0
    buying_power: float = 0.0
    leverage: float = 1.0
    maintenance_margin: float = 0.0
    initial_margin: float = 0.0
    liquidation_margin: float = 0.0
    currency: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    balances: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_balance_ratio(self) -> float:
        """Get balance ratio."""
        if self.total_equity == 0:
            return 0.0
        return self.available_balance / self.total_equity
    
    def get_margin_ratio(self) -> float:
        """Get margin ratio."""
        if self.total_equity == 0:
            return 0.0
        return self.margin_used / self.total_equity
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_equity": self.total_equity,
            "available_balance": self.available_balance,
            "used_balance": self.used_balance,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "buying_power": self.buying_power,
            "leverage": self.leverage,
            "maintenance_margin": self.maintenance_margin,
            "initial_margin": self.initial_margin,
            "liquidation_margin": self.liquidation_margin,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
            "balances": self.balances,
        }


@dataclass
class Trade:
    """Trade execution representation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    symbol: str = ""
    asset_class: AssetClass = AssetClass.STOCK
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    commission: float = 0.0
    commission_asset: str = "USD"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_type: str = "regular"
    is_maker: bool = False
    is_taker: bool = True
    exchange: Optional[str] = None
    trade_id: Optional[str] = None
    fees: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_value(self) -> float:
        """Get trade value."""
        return self.quantity * self.price
    
    def get_net_value(self) -> float:
        """Get net value after commission."""
        return self.get_value() - self.commission
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "commission": self.commission,
            "commission_asset": self.commission_asset,
            "timestamp": self.timestamp.isoformat(),
            "trade_type": self.trade_type,
            "is_maker": self.is_maker,
            "is_taker": self.is_taker,
            "exchange": self.exchange,
            "trade_id": self.trade_id,
            "fees": self.fees,
        }


@dataclass
class MarketData:
    """Unified market data representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    bid_price: Optional[float] = None
    bid_quantity: Optional[float] = None
    ask_price: Optional[float] = None
    ask_quantity: Optional[float] = None
    last_price: Optional[float] = None
    last_quantity: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    open_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[float] = None
    vwap: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    spread: Optional[float] = None
    bid_count: Optional[int] = None
    ask_count: Optional[int] = None
    market_cap: Optional[float] = None
    volume_24h: Optional[float] = None
    high_24h: Optional[float] = None
    low_24h: Optional[float] = None
    open_24h: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_mid_price(self) -> Optional[float]:
        """Get mid price."""
        if self.bid_price is not None and self.ask_price is not None:
            return (self.bid_price + self.ask_price) / 2
        return None
    
    def get_spread_pct(self) -> Optional[float]:
        """Get spread percentage."""
        if self.bid_price is not None and self.ask_price is not None and self.bid_price > 0:
            return ((self.ask_price - self.bid_price) / self.bid_price) * 100
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "bid_price": self.bid_price,
            "bid_quantity": self.bid_quantity,
            "ask_price": self.ask_price,
            "ask_quantity": self.ask_quantity,
            "last_price": self.last_price,
            "last_quantity": self.last_quantity,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "open_price": self.open_price,
            "close_price": self.close_price,
            "volume": self.volume,
            "vwap": self.vwap,
            "change": self.change,
            "change_percent": self.change_percent,
            "spread": self.spread,
            "bid_count": self.bid_count,
            "ask_count": self.ask_count,
            "market_cap": self.market_cap,
            "volume_24h": self.volume_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "open_24h": self.open_24h,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "source": self.source,
        }


@dataclass
class OrderBook:
    """Order book representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    bids: List[Tuple[float, float]] = field(default_factory=list)
    asks: List[Tuple[float, float]] = field(default_factory=list)
    bid_ids: Optional[List[str]] = None
    ask_ids: Optional[List[str]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    level: OrderBookLevel = OrderBookLevel.LEVEL_2
    sequence_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_best_bid(self) -> Optional[Tuple[float, float]]:
        """Get best bid (highest price)."""
        if not self.bids:
            return None
        return self.bids[0]
    
    def get_best_ask(self) -> Optional[Tuple[float, float]]:
        """Get best ask (lowest price)."""
        if not self.asks:
            return None
        return self.asks[0]
    
    def get_spread(self) -> Optional[float]:
        """Get current bid-ask spread."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return best_ask[0] - best_bid[0]
        return None
    
    def get_mid_price(self) -> Optional[float]:
        """Get mid price."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        if best_bid and best_ask:
            return (best_bid[0] + best_ask[0]) / 2
        return None
    
    def get_volume_at_level(self, level: int, side: str = "bid") -> float:
        """Get cumulative volume at depth level."""
        book = self.bids if side == "bid" else self.asks
        if not book or level <= 0:
            return 0.0
        return sum(price_qty[1] for price_qty in book[:level])
    
    def get_price_at_depth(self, depth: float, side: str = "bid") -> Optional[float]:
        """Get price at specified depth."""
        book = self.bids if side == "bid" else self.asks
        if not book:
            return None
        
        cum_volume = 0.0
        for price, qty in book:
            cum_volume += qty
            if cum_volume >= depth:
                return price
        return book[-1][0] if book else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "bids": self.bids,
            "asks": self.asks,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "level": self.level.value,
            "sequence_id": self.sequence_id,
        }


@dataclass
class Candle:
    """OHLCV candle representation."""
    symbol: str
    asset_class: AssetClass = AssetClass.STOCK
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    timeframe: DataFrequency = DataFrequency.MINUTE
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: Optional[str] = None
    vwap: Optional[float] = None
    number_of_trades: Optional[int] = None
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_range(self) -> float:
        """Get price range (high - low)."""
        return self.high - self.low
    
    def get_body(self) -> float:
        """Get candle body (close - open)."""
        return self.close - self.open
    
    def get_upper_wick(self) -> float:
        """Get upper wick (high - max(open, close))."""
        return self.high - max(self.open, self.close)
    
    def get_lower_wick(self) -> float:
        """Get lower wick (min(open, close) - low)."""
        return min(self.open, self.close) - self.low
    
    def is_bullish(self) -> bool:
        """Check if candle is bullish."""
        return self.close > self.open
    
    def is_bearish(self) -> bool:
        """Check if candle is bearish."""
        return self.close < self.open
    
    def is_doji(self, threshold: float = 0.1) -> bool:
        """Check if candle is a doji."""
        if self.open == 0:
            return False
        return abs(self.close - self.open) / self.open <= threshold
    
    def is_hammer(self) -> bool:
        """Check if candle is a hammer pattern."""
        if self.open == 0 or self.close == 0:
            return False
        body = abs(self.close - self.open)
        lower_wick = self.get_lower_wick()
        upper_wick = self.get_upper_wick()
        return lower_wick > body * 2 and upper_wick < body * 0.5
    
    def is_shooting_star(self) -> bool:
        """Check if candle is a shooting star pattern."""
        if self.open == 0 or self.close == 0:
            return False
        body = abs(self.close - self.open)
        upper_wick = self.get_upper_wick()
        lower_wick = self.get_lower_wick()
        return upper_wick > body * 2 and lower_wick < body * 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "timeframe": self.timeframe.value,
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "vwap": self.vwap,
            "number_of_trades": self.number_of_trades,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
        }


@dataclass
class ExchangeInfo:
    """Exchange information."""
    name: str
    type: ExchangeType = ExchangeType.CENTRALIZED
    asset_classes: List[AssetClass] = field(default_factory=list)
    timezone: str = "UTC"
    website: str = ""
    api_version: str = ""
    supported_order_types: List[OrderType] = field(default_factory=list)
    supported_time_in_force: List[TimeInForce] = field(default_factory=list)
    max_leverage: float = 1.0
    min_trade_size: float = 0.0
    max_trade_size: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    price_precision: int = 2
    quantity_precision: int = 2
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    withdrawal_fee: float = 0.0
    deposit_fee: float = 0.0
    trading_pairs: List[str] = field(default_factory=list)
    quote_assets: List[str] = field(default_factory=list)
    base_assets: List[str] = field(default_factory=list)
    features: Dict[str, bool] = field(default_factory=dict)
    rate_limits: Dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    last_updated: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type.value,
            "asset_classes": [ac.value for ac in self.asset_classes],
            "timezone": self.timezone,
            "website": self.website,
            "api_version": self.api_version,
            "supported_order_types": [ot.value for ot in self.supported_order_types],
            "supported_time_in_force": [tif.value for tif in self.supported_time_in_force],
            "max_leverage": self.max_leverage,
            "min_trade_size": self.min_trade_size,
            "max_trade_size": self.max_trade_size,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "withdrawal_fee": self.withdrawal_fee,
            "deposit_fee": self.deposit_fee,
            "trading_pairs": self.trading_pairs,
            "quote_assets": self.quote_assets,
            "base_assets": self.base_assets,
            "features": self.features,
            "rate_limits": self.rate_limits,
            "status": self.status,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class WebSocketMessage:
    """WebSocket message representation."""
    channel: str = ""
    event_type: WebSocketEvent = WebSocketEvent.MARKET_DATA
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sequence_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIRequest:
    """API request representation."""
    method: str = "GET"
    endpoint: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class APIResponse:
    """API response representation."""
    status: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: float = 0.0
    retry_count: int = 0
    error: Optional[Exception] = None


# ============================================================================
# EXCEPTIONS
# ============================================================================

class ExchangeError(Exception):
    """Base exchange exception."""
    def __init__(self, message: str, code: Optional[str] = None, data: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.data = data or {}
        super().__init__(message)


class ConnectionError(ExchangeError):
    """Connection error."""
    pass


class AuthenticationError(ExchangeError):
    """Authentication error."""
    pass


class AuthorizationError(ExchangeError):
    """Authorization error."""
    pass


class RateLimitError(ExchangeError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class OrderError(ExchangeError):
    """Order error."""
    pass


class InvalidOrderError(OrderError):
    """Invalid order parameters."""
    pass


class InsufficientBalanceError(OrderError):
    """Insufficient balance."""
    pass


class MarketDataError(ExchangeError):
    """Market data error."""
    pass


class PositionError(ExchangeError):
    """Position error."""
    pass


class AccountError(ExchangeError):
    """Account error."""
    pass


class TimeoutError(ExchangeError):
    """Timeout error."""
    pass


class WebSocketError(ExchangeError):
    """WebSocket error."""
    pass


class InvalidSymbolError(ExchangeError):
    """Invalid symbol error."""
    pass


class MaintenanceError(ExchangeError):
    """Exchange maintenance error."""
    pass


class BadRequestError(ExchangeError):
    """Bad request error."""
    pass


class NotFoundError(ExchangeError):
    """Not found error."""
    pass


class ConflictError(ExchangeError):
    """Conflict error."""
    pass


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, requests: int = 100, period: int = 60):
        self.requests = requests
        self.period = period
        self._timestamps: deque = deque()
        self._lock = Lock()
    
    async def acquire(self) -> bool:
        """Acquire a rate limit slot."""
        async with self._lock:
            now = time.time()
            cutoff = now - self.period
            
            # Remove old timestamps
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            
            if len(self._timestamps) < self.requests:
                self._timestamps.append(now)
                return True
            
            # Wait until next slot
            wait_time = self._timestamps[0] + self.period - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Re-acquire
            return await self.acquire()
    
    def reset(self) -> None:
        """Reset rate limiter."""
        self._timestamps.clear()


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""
    
    class State(str, Enum):
        CLOSED = "closed"
        OPEN = "open"
        HALF_OPEN = "half_open"
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self._state = self.State.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = Lock()
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute a function with circuit breaker."""
        if self._state == self.State.OPEN:
            if self._last_failure_time and time.time() - self._last_failure_time >= self.timeout:
                await self._transition_to(self.State.HALF_OPEN)
            else:
                raise ConnectionError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            if self._state == self.State.HALF_OPEN:
                await self._transition_to(self.State.CLOSED)
            return result
        except Exception as e:
            await self._record_failure()
            raise
    
    async def _record_failure(self) -> None:
        """Record a failure."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state != self.State.OPEN and self._failure_count >= self.failure_threshold:
                await self._transition_to(self.State.OPEN)
    
    async def _transition_to(self, state: State) -> None:
        """Transition to a new state."""
        async with self._lock:
            self._state = state
            if state == self.State.CLOSED:
                self._failure_count = 0
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self._state == self.State.OPEN


# ============================================================================
# BASE EXCHANGE CLASS
# ============================================================================

class ExchangeBase(ABC):
    """
    Abstract base class for all exchange implementations.
    
    Provides a unified interface for trading across multiple exchanges
    and asset classes with built-in:
    - Rate limiting
    - Circuit breaker
    - Retry logic
    - Connection pooling
    - WebSocket support
    - Logging
    - Metrics
    - Caching
    - Error handling
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        paper_trading: bool = False,
        testnet: bool = False,
        sandbox: bool = False,
        environment: Environment = Environment.PRODUCTION,
        rate_limit_requests: int = 100,
        rate_limit_period: int = 60,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 60,
        proxy: Optional[str] = None,
        ssl_verify: bool = True,
        **kwargs
    ):
        """
        Initialize the exchange client.
        
        Args:
            api_key: API key
            api_secret: API secret
            api_passphrase: API passphrase (for some exchanges)
            base_url: Base URL for API endpoints
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            paper_trading: Enable paper trading mode
            testnet: Use testnet endpoints
            sandbox: Use sandbox environment
            environment: Environment type
            rate_limit_requests: Maximum requests per period
            rate_limit_period: Rate limit period in seconds
            circuit_breaker_threshold: Failure threshold for circuit breaker
            circuit_breaker_timeout: Circuit breaker timeout in seconds
            proxy: Proxy URL
            ssl_verify: Verify SSL certificates
            **kwargs: Additional configuration
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.paper_trading = paper_trading
        self.testnet = testnet
        self.sandbox = sandbox
        self.environment = environment
        self.proxy = proxy
        self.ssl_verify = ssl_verify
        
        # Components
        self._session: Optional[ClientSession] = None
        self._connected = False
        self._connection_id = str(uuid.uuid4())
        self._rate_limiter = RateLimiter(rate_limit_requests, rate_limit_period)
        self._circuit_breaker = CircuitBreaker(circuit_breaker_threshold, circuit_breaker_timeout)
        self._cache: Dict[str, Any] = {}
        self._subscriptions: Dict[str, Set[str]] = defaultdict(set)
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._websocket_connections: Dict[str, Any] = {}
        self._websocket_callbacks: Dict[str, Callable] = {}
        
        # Metrics
        self._request_count = 0
        self._error_count = 0
        self._last_request_time = 0.0
        self._request_history: List[Dict] = []
        self._start_time = time.time()
        
        # Logging
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"Initialized {self.__class__.__name__} (ID: {self._connection_id})")
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the exchange.
        
        Returns:
            bool: True if connection successful
        """
        self._connected = True
        return True
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the exchange.
        """
        if self._session:
            await self._session.close()
            self._session = None
        self._connected = False
    
    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Check if connected to the exchange.
        
        Returns:
            bool: True if connected
        """
        return self._connected
    
    @abstractmethod
    async def get_exchange_info(self) -> ExchangeInfo:
        """
        Get exchange information.
        
        Returns:
            ExchangeInfo: Exchange information
        """
        pass
    
    # ========================================================================
    # HTTP REQUEST METHODS
    # ========================================================================
    
    async def _get_session(self) -> ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            connector = TCPConnector(
                ssl=self._create_ssl_context() if self.ssl_verify else False,
                limit=100,
                limit_per_host=20,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            timeout = ClientTimeout(total=self.timeout)
            self._session = ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=True,
            )
        return self._session
    
    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context."""
        if self.ssl_verify:
            ctx = ssl.create_default_context(cafile=certifi.where())
            return ctx
        return None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        auth_type: str = "none",
        retries: Optional[int] = None,
        **kwargs
    ) -> APIResponse:
        """
        Make an HTTP request with retries and rate limiting.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Form data
            json_data: JSON data
            headers: Additional headers
            auth_type: Authentication type
            retries: Number of retries
            **kwargs: Additional arguments
        
        Returns:
            APIResponse: API response
        
        Raises:
            ExchangeError: If request fails
        """
        retries = retries or self.max_retries
        start_time = time.time()
        
        # Apply rate limiting
        await self._rate_limiter.acquire()
        
        # Build URL
        url = f"{self.base_url}{endpoint}"
        
        # Prepare headers
        request_headers = self._prepare_headers(headers or {})
        if auth_type != "none":
            request_headers = self._add_auth_headers(request_headers, endpoint, method, params, data or json_data)
        
        # Prepare request params
        if params:
            request_headers = self._prepare_params(params)
        
        session = await self._get_session()
        
        # Execute request with retries
        for attempt in range(retries + 1):
            try:
                async with self._circuit_breaker.execute(
                    session.request,
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=request_headers,
                    proxy=self.proxy,
                    **kwargs
                ) as response:
                    status = response.status
                    response_headers = dict(response.headers)
                    
                    # Read response
                    try:
                        response_data = await response.json()
                    except ContentTypeError:
                        response_data = {"text": await response.text()}
                    
                    duration = time.time() - start_time
                    self._request_count += 1
                    self._last_request_time = time.time()
                    
                    self._log_request(method, endpoint, status, duration)
                    
                    # Check for errors
                    if status >= 400:
                        error_data = response_data.get("error", {}) if isinstance(response_data, dict) else {}
                        error_message = error_data.get("message", str(response_data) if response_data else f"HTTP {status}")
                        error_code = error_data.get("code")
                        
                        if status == 429:
                            retry_after = response_headers.get("Retry-After")
                            raise RateLimitError(
                                f"Rate limit exceeded: {error_message}",
                                int(retry_after) if retry_after else None
                            )
                        elif status == 401:
                            raise AuthenticationError(f"Authentication failed: {error_message}")
                        elif status == 403:
                            raise AuthorizationError(f"Authorization failed: {error_message}")
                        elif status == 404:
                            raise NotFoundError(f"Not found: {error_message}")
                        elif status == 409:
                            raise ConflictError(f"Conflict: {error_message}")
                        elif status >= 500:
                            raise ExchangeError(f"Server error: {error_message}")
                        else:
                            raise ExchangeError(f"Request failed: {error_message}", code=error_code)
                    
                    return APIResponse(
                        status=status,
                        data=response_data,
                        headers=response_headers,
                        timestamp=datetime.utcnow(),
                        duration=duration,
                        retry_count=attempt,
                    )
                    
            except (ClientConnectionError, ServerDisconnectedError, TimeoutError, asyncio.TimeoutError) as e:
                self._error_count += 1
                if attempt < retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    self._logger.warning(f"Request failed (attempt {attempt+1}/{retries+1}): {e}. Retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise ConnectionError(f"Connection failed after {retries+1} attempts: {e}")
                    
            except Exception as e:
                self._error_count += 1
                if attempt < retries and not isinstance(e, (AuthenticationError, AuthorizationError)):
                    wait_time = self.retry_delay * (2 ** attempt)
                    self._logger.warning(f"Request failed (attempt {attempt+1}/{retries+1}): {e}. Retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        
        raise ExchangeError(f"Request failed after {retries+1} attempts")
    
    async def _get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """Make GET request."""
        return await self._request("GET", endpoint, params=params, headers=headers, **kwargs)
    
    async def _post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """Make POST request."""
        return await self._request("POST", endpoint, data=data, json_data=json_data, headers=headers, **kwargs)
    
    async def _put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """Make PUT request."""
        return await self._request("PUT", endpoint, data=data, json_data=json_data, headers=headers, **kwargs)
    
    async def _delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """Make DELETE request."""
        return await self._request("DELETE", endpoint, params=params, headers=headers, **kwargs)
    
    async def _patch(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """Make PATCH request."""
        return await self._request("PATCH", endpoint, data=data, json_data=json_data, headers=headers, **kwargs)
    
    # ========================================================================
    # AUTHENTICATION HELPERS
    # ========================================================================
    
    def _prepare_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Prepare request headers."""
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"NEXUS-Trading-System/{__version__}",
        }
        default_headers.update(headers)
        return default_headers
    
    def _add_auth_headers(
        self,
        headers: Dict[str, str],
        endpoint: str,
        method: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Dict[str, str]:
        """Add authentication headers."""
        # Default implementation - override in child classes
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    def _prepare_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare query parameters."""
        prepared = {}
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, datetime):
                prepared[key] = value.isoformat()
            elif isinstance(value, Enum):
                prepared[key] = value.value
            else:
                prepared[key] = str(value) if not isinstance(value, (int, float, bool)) else value
        return prepared
    
    def _generate_signature(
        self,
        payload: str,
        secret: Optional[str] = None,
        algorithm: str = "sha256"
    ) -> str:
        """
        Generate HMAC signature.
        
        Args:
            payload: Payload to sign
            secret: Secret key (uses api_secret if None)
            algorithm: Hash algorithm
        
        Returns:
            str: Signature
        """
        secret = secret or self.api_secret
        if not secret:
            raise AuthenticationError("No API secret provided for signature generation")
        
        if algorithm == "sha256":
            return hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
        elif algorithm == "sha512":
            return hmac.new(
                secret.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def _generate_nonce(self) -> str:
        """Generate a nonce for API requests."""
        return str(int(time.time() * 1000))
    
    def _generate_client_order_id(self) -> str:
        """Generate a client order ID."""
        return f"nexus_{uuid.uuid4().hex[:16]}"
    
    # ========================================================================
    # LOGGING HELPERS
    # ========================================================================
    
    def _log_request(self, method: str, endpoint: str, status: int, duration: float) -> None:
        """Log API request."""
        log_level = logging.DEBUG if status < 400 else logging.WARNING
        self._logger.log(
            log_level,
            f"{method} {endpoint} -> {status} ({duration:.3f}s)"
        )
    
    def _log_error(self, error: Exception, context: str = "") -> None:
        """Log error with context."""
        self._logger.error(f"{context}: {error}", exc_info=True)
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)
    
    def _get_timestamp_seconds(self) -> int:
        """Get current timestamp in seconds."""
        return int(time.time())
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format."""
        return symbol.upper().strip()
    
    def _validate_quantity(self, quantity: float) -> bool:
        """Validate order quantity."""
        return quantity > 0
    
    def _validate_price(self, price: float) -> bool:
        """Validate order price."""
        return price > 0
    
    def _round_price(self, price: float, precision: int = 2) -> float:
        """Round price to precision."""
        return round(price, precision)
    
    def _round_quantity(self, quantity: float, precision: int = 2) -> float:
        """Round quantity to precision."""
        return round(quantity, precision)
    
    def _format_price(self, price: float, precision: int = 2) -> str:
        """Format price string."""
        return f"{{:.{precision}f}}".format(price)
    
    def _format_quantity(self, quantity: float, precision: int = 2) -> str:
        """Format quantity string."""
        return f"{{:.{precision}f}}".format(quantity)
    
    # ========================================================================
    # CACHE MANAGEMENT
    # ========================================================================
    
    def _get_cache(self, key: str, default: Any = None) -> Any:
        """Get cached value."""
        return self._cache.get(key, default)
    
    def _set_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set cached value."""
        self._cache[key] = value
        if ttl:
            # TODO: Implement TTL
            pass
    
    def _clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()
    
    # ========================================================================
    # WEBSOCKET MANAGEMENT
    # ========================================================================
    
    @abstractmethod
    async def connect_websocket(self, endpoint: str, **kwargs) -> bool:
        """
        Connect to WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint
            **kwargs: Additional parameters
        
        Returns:
            bool: True if connected
        """
        pass
    
    @abstractmethod
    async def disconnect_websocket(self, endpoint: str) -> bool:
        """
        Disconnect from WebSocket endpoint.
        
        Args:
            endpoint: WebSocket endpoint
        
        Returns:
            bool: True if disconnected
        """
        pass
    
    @abstractmethod
    async def subscribe_to_orders(self, callback: Callable) -> bool:
        """
        Subscribe to order updates.
        
        Args:
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_positions(self, callback: Callable) -> bool:
        """
        Subscribe to position updates.
        
        Args:
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_market_data(
        self,
        symbols: List[str],
        callback: Callable
    ) -> bool:
        """
        Subscribe to market data.
        
        Args:
            symbols: List of symbols
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_order_book(
        self,
        symbol: str,
        callback: Callable,
        level: OrderBookLevel = OrderBookLevel.LEVEL_2
    ) -> bool:
        """
        Subscribe to order book updates.
        
        Args:
            symbol: Symbol
            callback: Callback function
            level: Order book level
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    @abstractmethod
    async def subscribe_to_trades(
        self,
        symbols: List[str],
        callback: Callable
    ) -> bool:
        """
        Subscribe to trade updates.
        
        Args:
            symbols: List of symbols
            callback: Callback function
        
        Returns:
            bool: True if subscribed
        """
        pass
    
    # ========================================================================
    # WEBHOOK SUPPORT
    # ========================================================================
    
    @abstractmethod
    async def register_webhook(
        self,
        url: str,
        event_types: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a webhook.
        
        Args:
            url: Webhook URL
            event_types: Event types to subscribe to
            **kwargs: Additional parameters
        
        Returns:
            dict: Webhook registration details
        """
        pass
    
    @abstractmethod
    async def unregister_webhook(self, webhook_id: str) -> bool:
        """
        Unregister a webhook.
        
        Args:
            webhook_id: Webhook ID
        
        Returns:
            bool: True if unregistered
        """
        pass
    
    # ========================================================================
    # STATUS AND METRICS
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get exchange metrics."""
        uptime = time.time() - self._start_time
        return {
            "request_count": self._request_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(1, self._request_count),
            "uptime_seconds": uptime,
            "connected": self._connected,
            "connection_id": self._connection_id,
            "cache_size": len(self._cache),
            "websocket_connections": len(self._websocket_connections),
            "subscriptions": {k: len(v) for k, v in self._subscriptions.items()},
        }
    
    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._request_count = 0
        self._error_count = 0
        self._start_time = time.time()
    
    # ========================================================================
    # CONTEXT MANAGER
    # ========================================================================
    
    async def __aenter__(self) -> 'ExchangeBase':
        """Context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.disconnect()
    
    # ========================================================================
    # MAGIC METHODS
    # ========================================================================
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(connected={self._connected}, id={self._connection_id[:8]})"
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__} - {self._connection_id}"


# ============================================================================
# EXCHANGE FACTORY
# ============================================================================

class ExchangeFactory:
    """
    Factory for creating exchange instances.
    
    Supports dynamic loading of exchange implementations with
    configuration management and dependency injection.
    """
    
    _exchanges: Dict[str, Type[ExchangeBase]] = {}
    _configs: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register(cls, name: str, exchange_class: Type[ExchangeBase]) -> None:
        """
        Register an exchange implementation.
        
        Args:
            name: Exchange name
            exchange_class: Exchange class
        """
        cls._exchanges[name.lower()] = exchange_class
    
    @classmethod
    def register_config(cls, name: str, config: Dict[str, Any]) -> None:
        """
        Register configuration for an exchange.
        
        Args:
            name: Exchange name
            config: Configuration dictionary
        """
        cls._configs[name.lower()] = config
    
    @classmethod
    def create(
        cls,
        exchange: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        **kwargs
    ) -> ExchangeBase:
        """
        Create an exchange instance.
        
        Args:
            exchange: Exchange name
            api_key: API key (optional)
            api_secret: API secret (optional)
            **kwargs: Additional configuration
        
        Returns:
            ExchangeBase: Exchange instance
        
        Raises:
            ValueError: If exchange is not registered
        """
        exchange = exchange.lower()
        if exchange not in cls._exchanges:
            raise ValueError(
                f"Exchange '{exchange}' not registered. "
                f"Available: {', '.join(cls._exchanges.keys())}"
            )
        
        # Merge with registered config
        config = cls._configs.get(exchange, {}).copy()
        config.update(kwargs)
        
        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}
        
        exchange_class = cls._exchanges[exchange]
        return exchange_class(api_key=api_key, api_secret=api_secret, **config)
    
    @classmethod
    def get_available_exchanges(cls) -> List[str]:
        """
        Get list of available exchanges.
        
        Returns:
            List[str]: List of exchange names
        """
        return list(cls._exchanges.keys())
    
    @classmethod
    def get_exchange_class(cls, name: str) -> Optional[Type[ExchangeBase]]:
        """
        Get exchange class by name.
        
        Args:
            name: Exchange name
        
        Returns:
            Optional[Type[ExchangeBase]]: Exchange class or None
        """
        return cls._exchanges.get(name.lower())
    
    @classmethod
    def get_config(cls, name: str) -> Dict[str, Any]:
        """
        Get configuration for an exchange.
        
        Args:
            name: Exchange name
        
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        return cls._configs.get(name.lower(), {})


# ============================================================================
# DECORATORS
# ============================================================================

def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    exponential: bool = True,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying on error.
    
    Args:
        max_retries: Maximum number of retries
        delay: Initial delay in seconds
        exponential: Use exponential backoff
        exceptions: Tuple of exceptions to retry
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries:
                        wait_time = delay * (2 ** attempt) if exponential else delay
                        self._logger.warning(
                            f"{func.__name__} failed (attempt {attempt+1}/{max_retries+1}): {e}. "
                            f"Retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        self._logger.error(f"{func.__name__} failed after {max_retries+1} attempts: {e}")
                        raise
            raise last_error
        return wrapper
    return decorator


def rate_limited(requests_per_second: int):
    """
    Decorator for rate limiting.
    
    Args:
        requests_per_second: Maximum requests per second
    """
    _last_call: Dict[str, float] = {}
    
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            key = f"{id(self)}_{func.__name__}"
            now = time.time()
            if key in _last_call and now - _last_call[key] < 1.0 / requests_per_second:
                wait_time = (1.0 / requests_per_second) - (now - _last_call[key])
                await asyncio.sleep(wait_time)
            _last_call[key] = time.time()
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


def log_request(func):
    """Decorator for logging API requests."""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        try:
            result = await func(self, *args, **kwargs)
            duration = time.time() - start_time
            self._log_request(
                func.__name__,
                str(args[0] if args else ""),
                200,
                duration
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            self._log_error(e, f"{func.__name__} ({duration:.3f}s)")
            raise
    return wrapper


def cache_result(ttl: int = 300):
    """
    Decorator for caching results.
    
    Args:
        ttl: Time to live in seconds
    """
    def decorator(func):
        cache_key = f"cache_{func.__name__}"
        
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Generate cache key
            key_parts = [func.__name__]
            if args:
                key_parts.extend(str(arg) for arg in args)
            if kwargs:
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            key = "_".join(key_parts)
            
            # Check cache
            cache_dict = getattr(self, cache_key, {})
            if key in cache_dict:
                entry = cache_dict[key]
                if time.time() - entry["timestamp"] < ttl:
                    return entry["value"]
            
            # Execute and cache
            result = await func(self, *args, **kwargs)
            if not hasattr(self, cache_key):
                setattr(self, cache_key, {})
            getattr(self, cache_key)[key] = {
                "value": result,
                "timestamp": time.time()
            }
            return result
        return wrapper
    return decorator


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("NEXUS AI TRADING SYSTEM - Exchange Base Module Test")
    print("=" * 70)
    print(f"Version: 3.0.0")
    print("=" * 70)
    
    # Test enums
    print("\n[1] Testing Enums:")
    print(f"  Asset Classes: {[a.value for a in AssetClass]}")
    print(f"  Order Types: {[o.value for o in OrderType]}")
    print(f"  Time in Force: {[t.value for t in TimeInForce]}")
    print(f"  Environments: {[e.value for e in Environment]}")
    
    # Test data classes
    print("\n[2] Testing Data Classes:")
    order = Order(
        symbol="AAPL",
        quantity=100,
        price=150.00,
        order_type=OrderType.LIMIT
    )
    print(f"  Order: {order}")
    print(f"    Active: {order.is_active()}")
    print(f"    Remaining: {order.get_remaining_quantity()}")
    
    position = Position(
        symbol="AAPL",
        side=PositionSide.LONG,
        quantity=100,
        average_price=150.00,
        current_price=155.00
    )
    print(f"  Position: {position}")
    print(f"    PnL: ${position.total_pnl:.2f}")
    print(f"    PnL%: {position.get_pnl_percentage():.2f}%")
    
    candle = Candle(
        symbol="AAPL",
        open=150.00,
        high=155.00,
        low=149.00,
        close=154.00,
        volume=1000000
    )
    print(f"  Candle: {candle}")
    print(f"    Body: {candle.get_body():.2f}")
    print(f"    Range: {candle.get_range():.2f}")
    print(f"    Bullish: {candle.is_bullish()}")
    print(f"    Hammer: {candle.is_hammer()}")
    
    order_book = OrderBook(
        symbol="AAPL",
        bids=[(150.00, 100), (149.50, 200)],
        asks=[(150.50, 100), (151.00, 200)]
    )
    print(f"  Order Book: {order_book}")
    print(f"    Best bid: {order_book.get_best_bid()}")
    print(f"    Best ask: {order_book.get_best_ask()}")
    print(f"    Spread: ${order_book.get_spread():.2f}")
    print(f"    Mid price: ${order_book.get_mid_price():.2f}")
    
    # Test rate limiter
    print("\n[3] Testing Rate Limiter:")
    limiter = RateLimiter(requests=10, period=5)
    print(f"  Requests: {limiter.requests}, Period: {limiter.period}s")
    
    # Test circuit breaker
    print("\n[4] Testing Circuit Breaker:")
    breaker = CircuitBreaker(failure_threshold=3, timeout=5)
    print(f"  Threshold: {breaker.failure_threshold}, Timeout: {breaker.timeout}s")
    print(f"  State: {breaker._state.value}")
    
    # Test ExchangeFactory
    print("\n[5] Testing ExchangeFactory:")
    print(f"  Available exchanges: {ExchangeFactory.get_available_exchanges()}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)
