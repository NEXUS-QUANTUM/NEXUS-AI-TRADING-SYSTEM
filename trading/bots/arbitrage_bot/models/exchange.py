# trading/bots/arbitrage_bot/models/exchange.py
# NEXUS AI TRADING SYSTEM - EXCHANGE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for exchange configuration, connection,
# market data, and exchange-related entities for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Exchange Models

This module provides comprehensive data models for:
- Exchange configuration and credentials
- Market data structures (order books, tickers, trades)
- Exchange status and health monitoring
- Rate limiting and connection management
- Symbol and pair information
- Exchange capabilities and features
- API endpoint configuration
- Exchange metadata and statistics
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class ExchangeType(str, Enum):
    """Types of exchanges."""
    CEX = "cex"          # Centralized Exchange
    DEX = "dex"          # Decentralized Exchange
    HYBRID = "hybrid"    # Hybrid Exchange
    P2P = "p2p"          # Peer-to-Peer Exchange
    OTC = "otc"          # Over-the-Counter


class ExchangeMarket(str, Enum):
    """Market types supported by exchanges."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTIONS = "options"
    MARGIN = "margin"
    LEVERAGED = "leveraged"
    SWAP = "swap"
    ETF = "etf"
    STAKING = "staking"
    LENDING = "lending"
    BORROWING = "borrowing"


class ExchangeStatus(str, Enum):
    """Status of exchange connection."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    SUSPENDED = "suspended"
    UNAVAILABLE = "unavailable"
    CONNECTING = "connecting"
    DISCONNECTING = "disconnecting"


class SymbolStatus(str, Enum):
    """Status of a trading symbol."""
    TRADING = "trading"
    HALTED = "halted"
    SUSPENDED = "suspended"
    DELISTED = "delisted"
    PRE_TRADING = "pre_trading"
    POST_TRADING = "post_trading"
    MAINTENANCE = "maintenance"


class OrderSide(str, Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order types."""
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"
    TRAILING_STOP = "trailing_stop"
    ICEBERG = "iceberg"
    TWAP = "twap"
    POST_ONLY = "post_only"


class TimeInForce(str, Enum):
    """Time in force for orders."""
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    GTT = "GTT"  # Good Till Time
    DAY = "DAY"  # Day order
    MINUTE = "MINUTE"  # Minute order


class RateLimitType(str, Enum):
    """Rate limit types."""
    REQUESTS = "requests"
    ORDERS = "orders"
    WEBSOCKET = "websocket"
    WITHDRAWALS = "withdrawals"
    DEPOSITS = "deposits"
    TRANSFERS = "transfers"


# ====================================================================================
# EXCHANGE CONFIGURATION MODELS
# ====================================================================================

@dataclass
class ExchangeCredentials:
    """
    Exchange API credentials.
    """
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    private_key: str = ""
    public_key: str = ""
    
    # Additional auth fields
    client_id: str = ""
    account_id: str = ""
    sub_account_id: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    # Permissions
    permissions: List[str] = field(default_factory=list)
    read_only: bool = False
    trading_enabled: bool = True
    withdrawal_enabled: bool = False
    
    # Usage tracking
    last_used: Optional[datetime] = None
    usage_count: int = 0
    failed_attempts: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (redacted)."""
        return {
            "api_key": self.api_key[:4] + "..." if self.api_key else "",
            "has_secret": bool(self.api_secret),
            "has_passphrase": bool(self.passphrase),
            "has_private_key": bool(self.private_key),
            "client_id": self.client_id,
            "account_id": self.account_id,
            "sub_account_id": self.sub_account_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "permissions": self.permissions,
            "read_only": self.read_only,
            "trading_enabled": self.trading_enabled,
            "withdrawal_enabled": self.withdrawal_enabled,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "usage_count": self.usage_count,
            "failed_attempts": self.failed_attempts,
            "metadata": self.metadata
        }
        
    def is_valid(self) -> bool:
        """Check if credentials are valid."""
        if self.expires_at:
            return datetime.utcnow() < self.expires_at
        return True
        
    def is_expired(self) -> bool:
        """Check if credentials have expired."""
        if self.expires_at:
            return datetime.utcnow() >= self.expires_at
        return False
        
    def increment_usage(self) -> None:
        """Increment usage counter."""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
        
    def increment_failure(self) -> None:
        """Increment failure counter."""
        self.failed_attempts += 1


@dataclass
class ExchangeConfig:
    """
    Complete exchange configuration.
    """
    # Basic info
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    exchange_type: ExchangeType = ExchangeType.CEX
    market_type: ExchangeMarket = ExchangeMarket.SPOT
    
    # Endpoints
    base_url: str = ""
    ws_url: str = ""
    api_version: str = "v1"
    endpoints: Dict[str, str] = field(default_factory=dict)
    
    # Authentication
    credentials: ExchangeCredentials = field(default_factory=ExchangeCredentials)
    auth_method: str = "api_key"  # api_key, oauth, jwt
    
    # Connection settings
    timeout: float = 10.0
    retry_count: int = 3
    retry_delay: float = 1.0
    keep_alive: bool = True
    max_connections: int = 10
    
    # Rate limits
    rate_limits: Dict[str, float] = field(default_factory=lambda: {
        "requests_per_second": 10.0,
        "requests_per_minute": 600.0,
        "orders_per_second": 5.0,
        "orders_per_minute": 300.0,
        "websocket_connections": 5
    })
    
    # Features
    supports_market_data: bool = True
    supports_order_management: bool = True
    supports_websocket: bool = True
    supports_funding_rate: bool = False
    supports_margin: bool = False
    supports_futures: bool = False
    supports_options: bool = False
    
    # Symbols
    symbols: List[str] = field(default_factory=list)
    symbol_info: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Status
    status: ExchangeStatus = ExchangeStatus.OFFLINE
    health: Dict[str, Any] = field(default_factory=dict)
    last_health_check: Optional[datetime] = None
    
    # Performance
    avg_latency_ms: float = 0.0
    success_rate: float = 100.0
    total_requests: int = 0
    failed_requests: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "exchange_type": self.exchange_type.value if self.exchange_type else None,
            "market_type": self.market_type.value if self.market_type else None,
            "base_url": self.base_url,
            "ws_url": self.ws_url,
            "api_version": self.api_version,
            "endpoints": self.endpoints,
            "credentials": self.credentials.to_dict(),
            "auth_method": self.auth_method,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "retry_delay": self.retry_delay,
            "keep_alive": self.keep_alive,
            "max_connections": self.max_connections,
            "rate_limits": self.rate_limits,
            "supports_market_data": self.supports_market_data,
            "supports_order_management": self.supports_order_management,
            "supports_websocket": self.supports_websocket,
            "supports_funding_rate": self.supports_funding_rate,
            "supports_margin": self.supports_margin,
            "supports_futures": self.supports_futures,
            "supports_options": self.supports_options,
            "symbols": self.symbols,
            "symbol_info": self.symbol_info,
            "status": self.status.value if self.status else None,
            "health": self.health,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
            "avg_latency_ms": self.avg_latency_ms,
            "success_rate": self.success_rate,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExchangeConfig":
        """Create from dictionary."""
        config = cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            exchange_type=ExchangeType(data["exchange_type"]) if data.get("exchange_type") else ExchangeType.CEX,
            market_type=ExchangeMarket(data["market_type"]) if data.get("market_type") else ExchangeMarket.SPOT,
            base_url=data.get("base_url", ""),
            ws_url=data.get("ws_url", ""),
            api_version=data.get("api_version", "v1"),
            endpoints=data.get("endpoints", {}),
            auth_method=data.get("auth_method", "api_key"),
            timeout=data.get("timeout", 10.0),
            retry_count=data.get("retry_count", 3),
            retry_delay=data.get("retry_delay", 1.0),
            keep_alive=data.get("keep_alive", True),
            max_connections=data.get("max_connections", 10),
            rate_limits=data.get("rate_limits", {}),
            supports_market_data=data.get("supports_market_data", True),
            supports_order_management=data.get("supports_order_management", True),
            supports_websocket=data.get("supports_websocket", True),
            supports_funding_rate=data.get("supports_funding_rate", False),
            supports_margin=data.get("supports_margin", False),
            supports_futures=data.get("supports_futures", False),
            supports_options=data.get("supports_options", False),
            symbols=data.get("symbols", []),
            symbol_info=data.get("symbol_info", {}),
            status=ExchangeStatus(data["status"]) if data.get("status") else ExchangeStatus.OFFLINE,
            health=data.get("health", {}),
            avg_latency_ms=data.get("avg_latency_ms", 0.0),
            success_rate=data.get("success_rate", 100.0),
            total_requests=data.get("total_requests", 0),
            failed_requests=data.get("failed_requests", 0),
            metadata=data.get("metadata", {})
        )
        
        # Parse credentials
        if data.get("credentials"):
            creds = data["credentials"]
            config.credentials = ExchangeCredentials(
                api_key=creds.get("api_key", ""),
                api_secret=creds.get("api_secret", ""),
                passphrase=creds.get("passphrase", ""),
                private_key=creds.get("private_key", ""),
                public_key=creds.get("public_key", ""),
                client_id=creds.get("client_id", ""),
                account_id=creds.get("account_id", ""),
                sub_account_id=creds.get("sub_account_id", ""),
                permissions=creds.get("permissions", []),
                read_only=creds.get("read_only", False),
                trading_enabled=creds.get("trading_enabled", True),
                withdrawal_enabled=creds.get("withdrawal_enabled", False),
                usage_count=creds.get("usage_count", 0),
                failed_attempts=creds.get("failed_attempts", 0),
                metadata=creds.get("metadata", {})
            )
            
        # Parse timestamps
        if data.get("created_at"):
            config.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            config.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("last_health_check"):
            config.last_health_check = datetime.fromisoformat(data["last_health_check"])
            
        return config
        
    def update_health(self, is_healthy: bool, latency: float = 0.0) -> None:
        """Update exchange health status."""
        self.status = ExchangeStatus.ONLINE if is_healthy else ExchangeStatus.DEGRADED
        self.avg_latency_ms = (self.avg_latency_ms * 0.9 + latency * 0.1) if self.avg_latency_ms > 0 else latency
        self.last_health_check = datetime.utcnow()
        self.health = {
            "healthy": is_healthy,
            "latency_ms": latency,
            "last_check": self.last_health_check.isoformat()
        }


# ====================================================================================
# MARKET DATA MODELS
# ====================================================================================

@dataclass
class SymbolInfo:
    """
    Information about a trading symbol/pair.
    """
    symbol: str = ""
    base_asset: str = ""
    quote_asset: str = ""
    base_precision: int = 8
    quote_precision: int = 8
    
    # Trading limits
    min_qty: float = 0.0
    max_qty: float = 0.0
    step_size: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    tick_size: float = 0.0
    
    # Market status
    status: SymbolStatus = SymbolStatus.TRADING
    is_margin: bool = False
    is_futures: bool = False
    is_options: bool = False
    
    # Leverage
    max_leverage: int = 1
    min_leverage: int = 1
    
    # Fees
    maker_fee: float = 0.001
    taker_fee: float = 0.001
    
    # Metadata
    contract_size: float = 1.0
    settlement_asset: str = ""
    margin_asset: str = ""
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "base_precision": self.base_precision,
            "quote_precision": self.quote_precision,
            "min_qty": self.min_qty,
            "max_qty": self.max_qty,
            "step_size": self.step_size,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "tick_size": self.tick_size,
            "status": self.status.value if self.status else None,
            "is_margin": self.is_margin,
            "is_futures": self.is_futures,
            "is_options": self.is_options,
            "max_leverage": self.max_leverage,
            "min_leverage": self.min_leverage,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "contract_size": self.contract_size,
            "settlement_asset": self.settlement_asset,
            "margin_asset": self.margin_asset,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SymbolInfo":
        """Create from dictionary."""
        info = cls(
            symbol=data.get("symbol", ""),
            base_asset=data.get("base_asset", ""),
            quote_asset=data.get("quote_asset", ""),
            base_precision=data.get("base_precision", 8),
            quote_precision=data.get("quote_precision", 8),
            min_qty=data.get("min_qty", 0.0),
            max_qty=data.get("max_qty", 0.0),
            step_size=data.get("step_size", 0.0),
            min_price=data.get("min_price", 0.0),
            max_price=data.get("max_price", 0.0),
            tick_size=data.get("tick_size", 0.0),
            status=SymbolStatus(data["status"]) if data.get("status") else SymbolStatus.TRADING,
            is_margin=data.get("is_margin", False),
            is_futures=data.get("is_futures", False),
            is_options=data.get("is_options", False),
            max_leverage=data.get("max_leverage", 1),
            min_leverage=data.get("min_leverage", 1),
            maker_fee=data.get("maker_fee", 0.001),
            taker_fee=data.get("taker_fee", 0.001),
            contract_size=data.get("contract_size", 1.0),
            settlement_asset=data.get("settlement_asset", ""),
            margin_asset=data.get("margin_asset", ""),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("created_at"):
            info.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            info.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return info
        
    def validate_price(self, price: float) -> bool:
        """Validate price against min/max and tick size."""
        if price < self.min_price or price > self.max_price:
            return False
        if self.tick_size > 0:
            remainder = (price / self.tick_size) % 1
            if remainder > 1e-10:
                return False
        return True
        
    def validate_quantity(self, quantity: float) -> bool:
        """Validate quantity against min/max and step size."""
        if quantity < self.min_qty or quantity > self.max_qty:
            return False
        if self.step_size > 0:
            remainder = (quantity / self.step_size) % 1
            if remainder > 1e-10:
                return False
        return True


@dataclass
class ExchangeInfo:
    """
    Comprehensive exchange information.
    """
    exchange: str = ""
    timezone: str = "UTC"
    server_time: int = 0
    
    # Symbols
    symbols: List[SymbolInfo] = field(default_factory=list)
    
    # Rate limits
    rate_limits: List[Dict[str, Any]] = field(default_factory=list)
    
    # Filters
    exchange_filters: List[Dict[str, Any]] = field(default_factory=list)
    
    # Fees
    fees: Dict[str, float] = field(default_factory=dict)
    
    # Features
    features: Dict[str, bool] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "timezone": self.timezone,
            "server_time": self.server_time,
            "symbols": [s.to_dict() for s in self.symbols],
            "rate_limits": self.rate_limits,
            "exchange_filters": self.exchange_filters,
            "fees": self.fees,
            "features": self.features,
            "metadata": self.metadata,
            "updated_at": self.updated_at.isoformat()
        }
        
    def get_symbol(self, symbol: str) -> Optional[SymbolInfo]:
        """Get symbol info by symbol name."""
        for s in self.symbols:
            if s.symbol == symbol:
                return s
        return None


@dataclass
class Ticker:
    """
    24-hour ticker data.
    """
    symbol: str = ""
    exchange: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    quote_volume: float = 0.0
    change_24h: float = 0.0
    change_percent_24h: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Additional fields
    avg_price: float = 0.0
    weighted_avg_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "high": self.high,
            "low": self.low,
            "open": self.open,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "change_24h": self.change_24h,
            "change_percent_24h": self.change_percent_24h,
            "timestamp": self.timestamp.isoformat(),
            "avg_price": self.avg_price,
            "weighted_avg_price": self.weighted_avg_price,
            "spread": self.spread,
            "spread_bps": self.spread_bps
        }


@dataclass
class OrderBook:
    """
    Order book data.
    """
    symbol: str = ""
    exchange: str = ""
    bids: List[Tuple[float, float]] = field(default_factory=list)
    asks: List[Tuple[float, float]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    last_update_id: int = 0
    sequence_id: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bids": [[price, qty] for price, qty in self.bids],
            "asks": [[price, qty] for price, qty in self.asks],
            "timestamp": self.timestamp.isoformat(),
            "last_update_id": self.last_update_id,
            "sequence_id": self.sequence_id
        }


@dataclass
class Trade:
    """
    Trade data.
    """
    symbol: str = ""
    exchange: str = ""
    price: float = 0.0
    quantity: float = 0.0
    side: OrderSide = OrderSide.BUY
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trade_id: str = ""
    order_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side.value if self.side else None,
            "timestamp": self.timestamp.isoformat(),
            "trade_id": self.trade_id,
            "order_id": self.order_id
        }


@dataclass
class Kline:
    """
    Candlestick/Kline data.
    """
    symbol: str = ""
    exchange: str = ""
    interval: str = "1m"
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    quote_volume: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    close_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "interval": self.interval,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "timestamp": self.timestamp.isoformat(),
            "close_time": self.close_time.isoformat() if self.close_time else None
        }


@dataclass
class FundingRate:
    """
    Funding rate data for perpetual contracts.
    """
    symbol: str = ""
    exchange: str = ""
    rate: float = 0.0
    next_rate: float = 0.0
    next_time: Optional[datetime] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "rate": self.rate,
            "next_rate": self.next_rate,
            "next_time": self.next_time.isoformat() if self.next_time else None,
            "timestamp": self.timestamp.isoformat()
        }


# ====================================================================================
# EXCHANGE HEALTH MODELS
# ====================================================================================

@dataclass
class ExchangeHealth:
    """
    Exchange health and status information.
    """
    exchange: str = ""
    status: ExchangeStatus = ExchangeStatus.ONLINE
    latency_ms: float = 0.0
    success_rate: float = 100.0
    uptime_percentage: float = 100.0
    last_check: datetime = field(default_factory=datetime.utcnow)
    
    # Error counts
    error_counts: Dict[str, int] = field(default_factory=dict)
    total_errors: int = 0
    
    # Request statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Websocket status
    ws_connected: bool = False
    ws_latency_ms: float = 0.0
    ws_message_rate: float = 0.0
    
    # Rate limit status
    rate_limit_remaining: float = 0.0
    rate_limit_reset: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "status": self.status.value if self.status else None,
            "latency_ms": self.latency_ms,
            "success_rate": self.success_rate,
            "uptime_percentage": self.uptime_percentage,
            "last_check": self.last_check.isoformat(),
            "error_counts": self.error_counts,
            "total_errors": self.total_errors,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "ws_connected": self.ws_connected,
            "ws_latency_ms": self.ws_latency_ms,
            "ws_message_rate": self.ws_message_rate,
            "rate_limit_remaining": self.rate_limit_remaining,
            "rate_limit_reset": self.rate_limit_reset.isoformat() if self.rate_limit_reset else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExchangeHealth":
        """Create from dictionary."""
        health = cls(
            exchange=data.get("exchange", ""),
            status=ExchangeStatus(data["status"]) if data.get("status") else ExchangeStatus.ONLINE,
            latency_ms=data.get("latency_ms", 0.0),
            success_rate=data.get("success_rate", 100.0),
            uptime_percentage=data.get("uptime_percentage", 100.0),
            error_counts=data.get("error_counts", {}),
            total_errors=data.get("total_errors", 0),
            total_requests=data.get("total_requests", 0),
            successful_requests=data.get("successful_requests", 0),
            failed_requests=data.get("failed_requests", 0),
            ws_connected=data.get("ws_connected", False),
            ws_latency_ms=data.get("ws_latency_ms", 0.0),
            ws_message_rate=data.get("ws_message_rate", 0.0),
            rate_limit_remaining=data.get("rate_limit_remaining", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("last_check"):
            health.last_check = datetime.fromisoformat(data["last_check"])
        if data.get("rate_limit_reset"):
            health.rate_limit_reset = datetime.fromisoformat(data["rate_limit_reset"])
            
        return health
        
    def is_healthy(self) -> bool:
        """Check if exchange is healthy."""
        return self.status == ExchangeStatus.ONLINE and self.success_rate >= 95.0
        
    def is_degraded(self) -> bool:
        """Check if exchange is degraded."""
        return self.status == ExchangeStatus.DEGRADED or self.success_rate < 95.0
        
    def record_request(self, success: bool, latency_ms: float) -> None:
        """Record a request."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        self.success_rate = (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 100.0
        self.latency_ms = (self.latency_ms * 0.9 + latency_ms * 0.1) if self.latency_ms > 0 else latency_ms
        self.last_check = datetime.utcnow()


# ====================================================================================
# RATE LIMIT MODELS
# ====================================================================================

@dataclass
class RateLimit:
    """
    Rate limit information.
    """
    type: RateLimitType = RateLimitType.REQUESTS
    limit: int = 0
    remaining: int = 0
    reset_at: datetime = field(default_factory=datetime.utcnow)
    window: int = 60  # seconds
    
    # Usage tracking
    used: int = 0
    first_request: Optional[datetime] = None
    last_request: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value if self.type else None,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at.isoformat(),
            "window": self.window,
            "used": self.used,
            "first_request": self.first_request.isoformat() if self.first_request else None,
            "last_request": self.last_request.isoformat() if self.last_request else None
        }
        
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.remaining <= 0 and datetime.utcnow() < self.reset_at
        
    def get_reset_time(self) -> float:
        """Get time until reset in seconds."""
        return max(0, (self.reset_at - datetime.utcnow()).total_seconds())
        
    def increment(self) -> None:
        """Increment usage."""
        self.used += 1
        self.remaining = max(0, self.limit - self.used)
        self.last_request = datetime.utcnow()
        if not self.first_request:
            self.first_request = datetime.utcnow()


# ====================================================================================
# EXCHANGE STATISTICS MODELS
# ====================================================================================

@dataclass
class ExchangeStats:
    """
    Exchange performance statistics.
    """
    exchange: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Request statistics
    total_requests: int = 0
    avg_requests_per_second: float = 0.0
    max_requests_per_second: float = 0.0
    
    # Latency statistics
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Success statistics
    success_rate: float = 100.0
    error_rate: float = 0.0
    
    # Order statistics
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    avg_order_time_ms: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_requests": self.total_requests,
            "avg_requests_per_second": self.avg_requests_per_second,
            "max_requests_per_second": self.max_requests_per_second,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "total_orders": self.total_orders,
            "successful_orders": self.successful_orders,
            "failed_orders": self.failed_orders,
            "avg_order_time_ms": self.avg_order_time_ms,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_exchange_config(
    name: str,
    exchange_type: ExchangeType = ExchangeType.CEX,
    **kwargs
) -> ExchangeConfig:
    """
    Create an exchange configuration with default values.
    
    Args:
        name: Exchange name
        exchange_type: Type of exchange
        **kwargs: Additional configuration fields
        
    Returns:
        ExchangeConfig instance
    """
    return ExchangeConfig(
        name=name,
        exchange_type=exchange_type,
        **kwargs
    )


def create_symbol_info(
    symbol: str,
    base: str,
    quote: str,
    **kwargs
) -> SymbolInfo:
    """
    Create symbol information.
    
    Args:
        symbol: Symbol name
        base: Base asset
        quote: Quote asset
        **kwargs: Additional symbol fields
        
    Returns:
        SymbolInfo instance
    """
    return SymbolInfo(
        symbol=symbol,
        base_asset=base,
        quote_asset=quote,
        **kwargs
    )


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'ExchangeType',
    'ExchangeMarket',
    'ExchangeStatus',
    'SymbolStatus',
    'OrderSide',
    'OrderType',
    'TimeInForce',
    'RateLimitType',
    
    # Configuration Models
    'ExchangeCredentials',
    'ExchangeConfig',
    
    # Market Data Models
    'SymbolInfo',
    'ExchangeInfo',
    'Ticker',
    'OrderBook',
    'Trade',
    'Kline',
    'FundingRate',
    
    # Health Models
    'ExchangeHealth',
    
    # Rate Limit Models
    'RateLimit',
    
    # Statistics Models
    'ExchangeStats',
    
    # Helper Functions
    'create_exchange_config',
    'create_symbol_info',
]
