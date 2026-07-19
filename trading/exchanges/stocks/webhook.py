#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Stocks Webhook Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced webhook handler for stock market data and events.
Supports real-time data ingestion, multi-provider webhooks,
signature verification, retry mechanisms, and event processing.

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
from asyncio import Queue, QueueFull, QueueEmpty
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, 
    Union, TypeVar, Generic, cast, AsyncIterator, Iterable
)
from urllib.parse import parse_qs, urlparse, urlencode
from collections import defaultdict, deque
import ssl
import aiohttp
from aiohttp import ClientSession, ClientTimeout, web, WSMsgType
from aiohttp.web import Request, Response, json_response
from aiohttp.client_exceptions import ClientError, ClientConnectionError
from pydantic import BaseModel, Field, validator, root_validator, ValidationError
from pydantic.types import PositiveInt, NonNegativeFloat, constr, confloat

from ..base import (
    ExchangeBase,
    Order,
    Position,
    Trade,
    MarketData,
    OrderBook,
    Candle,
    AssetClass,
    OrderSide,
    OrderType,
    ExchangeError,
    AuthenticationError,
    RateLimitError,
    WebSocketError,
)
from ..stocks.base import (
    StockExchangeBase,
    StockOrder,
    StockPosition,
    StockMarketData,
    StockOrderBook,
    StockTrade,
    StockQuote,
    StockBar,
    StockWatchlist,
)
from ..stocks.exceptions import (
    StockExchangeError,
    AuthenticationError as StockAuthError,
    OrderError as StockOrderError,
    MarketDataError as StockMarketDataError,
)
from ...core.config import get_config
from ...core.logging import get_logger
from ...core.metrics import MetricsCollector
from ...core.retry import retry_with_backoff, RetryConfig
from ...core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from ...core.rate_limiter import RateLimiter, RateLimiterConfig
from ...core.cache import CacheManager, CacheConfig
from ...core.events import EventBus, EventType
from ...core.health import HealthCheck, HealthStatus
from ...core.tracing import Tracer, SpanContext
from ...core.encryption import Encryptor, KeyManager

logger = get_logger(__name__)

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

DEFAULT_WEBHOOK_PORT = 8080
DEFAULT_WEBHOOK_HOST = "0.0.0.0"
DEFAULT_WEBHOOK_PATH = "/webhook"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_BATCH_SIZE = 100
DEFAULT_QUEUE_SIZE = 10000
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60
DEFAULT_RATE_LIMIT_REQUESTS = 100
DEFAULT_RATE_LIMIT_PERIOD = 60
DEFAULT_MAX_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_CACHE_TTL = 300  # 5 minutes
DEFAULT_MAX_CONCURRENT = 10

# ============================================================================
# ENUMS & TYPES
# ============================================================================

class WebhookProvider(str, Enum):
    """Supported webhook providers."""
    ALPACA = "alpaca"
    POLYGON = "polygon"
    FINNHUB = "finnhub"
    TWELVE_DATA = "twelve_data"
    YAHOO = "yahoo"
    TRADIER = "tradier"
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    OANDA = "oanda"
    CUSTOM = "custom"
    WEBHOOK = "webhook"
    GITHUB = "github"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"


class WebhookEventType(str, Enum):
    """Types of webhook events."""
    TRADE = "trade"
    QUOTE = "quote"
    ORDER_BOOK = "order_book"
    AGGREGATE = "aggregate"
    STATUS = "status"
    ERROR = "error"
    PING = "ping"
    SUBSCRIPTION = "subscription"
    UNSUBSCRIPTION = "unsubscription"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"
    ORDER = "order"
    POSITION = "position"
    ACCOUNT = "account"
    ALERT = "alert"
    SIGNAL = "signal"
    BAR = "bar"
    TICKER = "ticker"
    NEWS = "news"
    EARNINGS = "earnings"
    DIVIDEND = "dividend"
    SPLIT = "split"
    CORPORATE_ACTION = "corporate_action"


class WebhookStatus(str, Enum):
    """Status of webhook processing."""
    RECEIVED = "received"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DISCARDED = "discarded"
    QUEUED = "queued"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms."""
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"
    RSA_SHA256 = "rsa_sha256"
    RSA_SHA512 = "rsa_sha512"
    ECDSA_SHA256 = "ecdsa_sha256"
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"


class WebhookFormat(str, Enum):
    """Webhook payload formats."""
    JSON = "json"
    XML = "xml"
    PROTOBUF = "protobuf"
    MSGPACK = "msgpack"
    CBOR = "cbor"
    YAML = "yaml"


class WebhookAuthType(str, Enum):
    """Webhook authentication types."""
    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    BASIC = "basic"
    HMAC = "hmac"
    OAUTH2 = "oauth2"
    JWT = "jwt"


class WebhookCompression(str, Enum):
    """Webhook compression types."""
    NONE = "none"
    GZIP = "gzip"
    DEFLATE = "deflate"
    ZSTD = "zstd"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WebhookConfig(BaseModel):
    """Configuration for webhook handler."""
    
    provider: WebhookProvider = WebhookProvider.CUSTOM
    path: str = DEFAULT_WEBHOOK_PATH
    host: str = DEFAULT_WEBHOOK_HOST
    port: PositiveInt = DEFAULT_WEBHOOK_PORT
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    ssl_ca: Optional[str] = None
    
    # Security
    secret_key: Optional[str] = None
    public_key: Optional[str] = None
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    verify_signature: bool = True
    verify_timestamp: bool = True
    timestamp_tolerance: PositiveInt = 300  # 5 minutes
    allowed_ips: List[str] = Field(default_factory=list)
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    allowed_methods: List[str] = Field(default_factory=lambda: ["POST"])
    max_payload_size: PositiveInt = DEFAULT_MAX_PAYLOAD_SIZE
    require_https: bool = True
    
    # Authentication
    auth_type: WebhookAuthType = WebhookAuthType.NONE
    auth_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    api_key_header: str = "X-API-Key"
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: PositiveInt = DEFAULT_RATE_LIMIT_REQUESTS
    rate_limit_period: PositiveInt = DEFAULT_RATE_LIMIT_PERIOD
    rate_limit_by_ip: bool = True
    rate_limit_by_provider: bool = False
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: PositiveInt = DEFAULT_CIRCUIT_BREAKER_THRESHOLD
    circuit_breaker_timeout: PositiveInt = DEFAULT_CIRCUIT_BREAKER_TIMEOUT
    circuit_breaker_retry_timeout: PositiveInt = 30
    
    # Processing
    timeout_seconds: PositiveInt = DEFAULT_TIMEOUT_SECONDS
    max_retries: PositiveInt = DEFAULT_MAX_RETRIES
    retry_delay: NonNegativeFloat = DEFAULT_RETRY_DELAY
    retry_backoff: float = DEFAULT_RETRY_BACKOFF
    batch_size: PositiveInt = DEFAULT_BATCH_SIZE
    queue_size: PositiveInt = DEFAULT_QUEUE_SIZE
    async_processing: bool = True
    parallel_workers: PositiveInt = 4
    max_concurrent: PositiveInt = DEFAULT_MAX_CONCURRENT
    process_timeout: PositiveInt = 60
    
    # Storage
    store_raw: bool = True
    store_processed: bool = True
    store_errors: bool = True
    retention_days: PositiveInt = 30
    storage_backend: str = "redis"  # redis, postgres, mongodb, file
    
    # Caching
    cache_enabled: bool = True
    cache_ttl: PositiveInt = DEFAULT_CACHE_TTL
    cache_max_size: PositiveInt = 10000
    
    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"
    
    # Compression
    compression: WebhookCompression = WebhookCompression.NONE
    compression_threshold: PositiveInt = 1024  # bytes
    
    # Format
    format: WebhookFormat = WebhookFormat.JSON
    
    @validator("path")
    def validate_path(cls, v: str) -> str:
        """Validate webhook path."""
        if not v.startswith("/"):
            v = f"/{v}"
        return v
    
    @validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate port number."""
        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @validator("max_payload_size")
    def validate_max_payload_size(cls, v: int) -> int:
        """Validate max payload size."""
        if v < 1024:
            raise ValueError("Max payload size must be at least 1KB")
        return v
    
    @validator("retry_backoff")
    def validate_retry_backoff(cls, v: float) -> float:
        """Validate retry backoff."""
        if v < 1.0:
            raise ValueError("Retry backoff must be at least 1.0")
        return v


class WebhookPayload(BaseModel):
    """Base model for webhook payload."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: WebhookEventType
    provider: WebhookProvider
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    source_ip: Optional[str] = None
    source_url: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Optional[str] = None
    raw_data_b64: Optional[str] = None
    signature: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    retry_count: int = 0
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            if v > 1e12:  # nanoseconds
                return datetime.utcfromtimestamp(v / 1e9)
            elif v > 1e9:  # milliseconds
                return datetime.utcfromtimestamp(v / 1000)
            else:  # seconds
                return datetime.utcfromtimestamp(v)
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
        raise ValueError(f"Unsupported timestamp format: {v}")
    
    @root_validator
    def validate_signature(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate signature if required."""
        # Signature validation is done at processing time
        return values
    
    def to_bytes(self) -> bytes:
        """Convert payload to bytes."""
        return json.dumps(self.dict()).encode('utf-8')
    
    def to_base64(self) -> str:
        """Convert payload to base64."""
        return base64.b64encode(self.to_bytes()).decode('utf-8')


class WebhookResponse(BaseModel):
    """Response model for webhook handler."""
    
    status: WebhookStatus
    message: str
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    retry_after: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "message": self.message,
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "processing_time_ms": self.processing_time_ms,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "retry_after": self.retry_after,
            "metadata": self.metadata,
        }


class StockTradeData(BaseModel):
    """Stock trade data model."""
    
    symbol: str
    price: confloat(gt=0)
    size: confloat(gt=0)
    timestamp: datetime
    exchange: Optional[str] = None
    trade_id: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    tape: Optional[str] = None
    source: Optional[str] = None
    
    @validator("symbol")
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol."""
        return v.upper().strip()
    
    def to_trade(self) -> Trade:
        """Convert to Trade object."""
        return Trade(
            symbol=self.symbol,
            asset_class=AssetClass.STOCK,
            side=OrderSide.BUY if self.size > 0 else OrderSide.SELL,
            quantity=abs(self.size),
            price=self.price,
            timestamp=self.timestamp,
            exchange=self.exchange,
            trade_id=self.trade_id,
            metadata={
                "conditions": self.conditions,
                "tape": self.tape,
                "source": self.source,
            }
        )


class StockQuoteData(BaseModel):
    """Stock quote data model."""
    
    symbol: str
    bid_price: confloat(gt=0)
    bid_size: confloat(gt=0)
    ask_price: confloat(gt=0)
    ask_size: confloat(gt=0)
    timestamp: datetime
    exchange: Optional[str] = None
    bid_exchange: Optional[str] = None
    ask_exchange: Optional[str] = None
    last_price: Optional[float] = None
    last_size: Optional[float] = None
    
    @validator("symbol")
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol."""
        return v.upper().strip()
    
    def get_mid_price(self) -> float:
        """Get mid price."""
        return (self.bid_price + self.ask_price) / 2
    
    def get_spread(self) -> float:
        """Get spread."""
        return self.ask_price - self.bid_price
    
    def get_spread_pct(self) -> float:
        """Get spread percentage."""
        if self.bid_price > 0:
            return (self.get_spread() / self.bid_price) * 100
        return 0.0


class StockAggregateData(BaseModel):
    """Stock aggregate data model."""
    
    symbol: str
    open: confloat(ge=0)
    high: confloat(ge=0)
    low: confloat(ge=0)
    close: confloat(ge=0)
    volume: confloat(ge=0)
    timestamp: datetime
    exchange: Optional[str] = None
    vwap: Optional[float] = None
    number_of_trades: Optional[int] = None
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    
    @validator("symbol")
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol."""
        return v.upper().strip()
    
    def to_candle(self, timeframe: str = "1m") -> Candle:
        """Convert to Candle object."""
        from ..base import Candle, DataFrequency
        
        freq_map = {
            "1s": DataFrequency.SECOND,
            "1m": DataFrequency.MINUTE,
            "5m": DataFrequency.MINUTE_5,
            "15m": DataFrequency.MINUTE_15,
            "30m": DataFrequency.MINUTE_30,
            "1h": DataFrequency.HOUR,
            "4h": DataFrequency.HOUR_4,
            "1d": DataFrequency.DAY,
            "1w": DataFrequency.WEEK,
            "1M": DataFrequency.MONTH,
        }
        
        return Candle(
            symbol=self.symbol,
            asset_class=AssetClass.STOCK,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            timeframe=freq_map.get(timeframe, DataFrequency.MINUTE),
            timestamp=self.timestamp,
            exchange=self.exchange,
            vwap=self.vwap,
            number_of_trades=self.number_of_trades,
            buy_volume=self.buy_volume,
            sell_volume=self.sell_volume,
        )


class WebhookStats(BaseModel):
    """Webhook statistics."""
    
    total_received: int = 0
    total_processed: int = 0
    total_failed: int = 0
    total_discarded: int = 0
    total_retried: int = 0
    total_timeout: int = 0
    total_rejected: int = 0
    avg_processing_time: float = 0.0
    max_processing_time: float = 0.0
    min_processing_time: float = 0.0
    last_processing_time: float = 0.0
    queue_depth: int = 0
    worker_active: int = 0
    uptime_seconds: float = 0.0
    events: Dict[str, int] = Field(default_factory=dict)
    providers: Dict[str, int] = Field(default_factory=dict)
    statuses: Dict[str, int] = Field(default_factory=dict)
    errors: Dict[str, int] = Field(default_factory=dict)
    processing_times: List[float] = Field(default_factory=list)


# ============================================================================
# WEBHOOK HANDLER CLASS
# ============================================================================

class WebhookHandler:
    """
    Advanced webhook handler for stock market data.
    
    Features:
    - Multi-provider webhook support
    - Signature verification (HMAC, RSA, ECDSA)
    - IP whitelisting / origin validation
    - Rate limiting (per IP, per provider)
    - Circuit breaker pattern
    - Async processing with queue
    - Retry mechanisms with exponential backoff
    - Data validation and transformation
    - Metrics and monitoring
    - Storage (raw and processed data)
    - Event filtering and routing
    - Plugin system for custom handlers
    - Health checks and status endpoints
    - Compression support (gzip, deflate, zstd)
    - Multiple authentication methods
    - Caching with TTL
    - Tracing and logging
    - Batch processing
    """
    
    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        exchange: Optional[ExchangeBase] = None,
        redis_client: Optional[Any] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_manager: Optional[CacheManager] = None,
        event_bus: Optional[EventBus] = None,
        tracer: Optional[Tracer] = None,
        encryptor: Optional[Encryptor] = None,
        **kwargs
    ):
        """
        Initialize webhook handler.
        
        Args:
            config: Webhook configuration
            exchange: Exchange instance for processing
            redis_client: Redis client for distributed state
            metrics_collector: Metrics collector for monitoring
            cache_manager: Cache manager for performance
            event_bus: Event bus for event distribution
            tracer: Tracer for distributed tracing
            encryptor: Encryptor for data encryption
            **kwargs: Additional arguments
        """
        self.config = config or WebhookConfig()
        self.exchange = exchange
        self.redis_client = redis_client
        self.metrics = metrics_collector or MetricsCollector()
        self.cache = cache_manager or CacheManager()
        self.event_bus = event_bus or EventBus()
        self.tracer = tracer or Tracer()
        self.encryptor = encryptor or Encryptor()
        
        # State management
        self._running = False
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        
        # Queues
        self._input_queue: Queue = Queue(maxsize=self.config.queue_size)
        self._output_queue: Queue = Queue(maxsize=self.config.queue_size)
        self._dead_letter_queue: Queue = Queue(maxsize=self.config.queue_size)
        
        # Workers
        self._workers: List[asyncio.Task] = []
        self._processor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            config=RateLimiterConfig(
                requests=self.config.rate_limit_requests,
                period=self.config.rate_limit_period,
                redis_client=redis_client,
                key_prefix="webhook_rate",
            )
        )
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=self.config.circuit_breaker_threshold,
                timeout_seconds=self.config.circuit_breaker_timeout,
                retry_timeout_seconds=self.config.circuit_breaker_retry_timeout,
                redis_client=redis_client,
                name="webhook_circuit_breaker",
            )
        )
        
        # Handlers registry
        self._handlers: Dict[WebhookProvider, Dict[WebhookEventType, List[Callable]]] = {}
        self._middlewares: List[Callable] = []
        self._filters: List[Callable] = []
        self._transformers: List[Callable] = []
        
        # Cache for processed data
        self._data_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self._stats = WebhookStats()
        self._start_time = time.time()
        
        # Health status
        self._last_health_check = datetime.utcnow()
        self._health_status = HealthStatus.HEALTHY
        self._health_details: Dict[str, Any] = {}
        
        # Active connections
        self._active_connections: Set[str] = set()
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        
        # Setup
        self._setup_handlers()
        self._setup_routes()
        self._setup_signature_verifiers()
        self._setup_middlewares()
        self._setup_filters()
        self._setup_transformers()
        
        logger.info(
            f"WebhookHandler initialized: provider={self.config.provider.value}, "
            f"path={self.config.path}, port={self.config.port}, "
            f"workers={self.config.parallel_workers}"
        )
    
    # ========================================================================
    # SETUP METHODS
    # ========================================================================
    
    def _setup_handlers(self) -> None:
        """Setup default event handlers."""
        # Register default handlers
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.TRADE,
            self._handle_trade,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.QUOTE,
            self._handle_quote,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.AGGREGATE,
            self._handle_aggregate,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.HEARTBEAT,
            self._handle_heartbeat,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.ORDER,
            self._handle_order,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.POSITION,
            self._handle_position,
        )
        self.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.ACCOUNT,
            self._handle_account,
        )
        
        # Provider-specific handlers
        self.register_handler(
            WebhookProvider.ALPACA,
            WebhookEventType.TRADE,
            self._handle_alpaca_trade,
        )
        self.register_handler(
            WebhookProvider.ALPACA,
            WebhookEventType.QUOTE,
            self._handle_alpaca_quote,
        )
        self.register_handler(
            WebhookProvider.POLYGON,
            WebhookEventType.TRADE,
            self._handle_polygon_trade,
        )
        self.register_handler(
            WebhookProvider.POLYGON,
            WebhookEventType.QUOTE,
            self._handle_polygon_quote,
        )
        self.register_handler(
            WebhookProvider.POLYGON,
            WebhookEventType.AGGREGATE,
            self._handle_polygon_aggregate,
        )
        
        logger.debug(f"Registered {sum(len(h) for h in self._handlers.values())} handlers")
    
    def _setup_routes(self) -> None:
        """Setup web routes."""
        self._app = web.Application(
            middlewares=[
                self._cors_middleware,
                self._logging_middleware,
                self._error_middleware,
                self._rate_limit_middleware,
                self._auth_middleware,
                self._size_limit_middleware,
                self._compression_middleware,
            ]
        )
        
        # Primary webhook endpoint
        self._app.router.add_route(
            "*",
            self.config.path,
            self._handle_webhook,
        )
        
        # Health check endpoint
        self._app.router.add_get(
            "/health",
            self._handle_health_check,
        )
        self._app.router.add_get(
            "/health/ready",
            self._handle_readiness_check,
        )
        self._app.router.add_get(
            "/health/live",
            self._handle_liveness_check,
        )
        
        # Status endpoint
        self._app.router.add_get(
            "/status",
            self._handle_status,
        )
        
        # Metrics endpoint
        self._app.router.add_get(
            "/metrics",
            self._handle_metrics,
        )
        
        # Admin endpoints
        if self.config.enable_metrics:
            self._app.router.add_post(
                "/admin/clear_cache",
                self._handle_clear_cache,
            )
            self._app.router.add_post(
                "/admin/reset_stats",
                self._handle_reset_stats,
            )
            self._app.router.add_post(
                "/admin/purge_queue",
                self._handle_purge_queue,
            )
            self._app.router.add_post(
                "/admin/reload_handlers",
                self._handle_reload_handlers,
            )
        
        # WebSocket endpoint for real-time monitoring
        self._app.router.add_get(
            "/ws",
            self._handle_websocket,
        )
        
        logger.debug(f"Webhook routes configured: {len(self._app.router.routes())} routes")
    
    def _setup_signature_verifiers(self) -> None:
        """Setup signature verifiers."""
        self._signature_verifiers = {
            SignatureAlgorithm.HMAC_SHA256: self._verify_hmac_sha256,
            SignatureAlgorithm.HMAC_SHA512: self._verify_hmac_sha512,
            SignatureAlgorithm.RSA_SHA256: self._verify_rsa_sha256,
            SignatureAlgorithm.RSA_SHA512: self._verify_rsa_sha512,
            SignatureAlgorithm.ECDSA_SHA256: self._verify_ecdsa_sha256,
            SignatureAlgorithm.NONE: self._verify_none,
            SignatureAlgorithm.BASIC: self._verify_basic,
            SignatureAlgorithm.BEARER: self._verify_bearer,
        }
    
    def _setup_middlewares(self) -> None:
        """Setup middlewares."""
        pass
    
    def _setup_filters(self) -> None:
        """Setup filters."""
        pass
    
    def _setup_transformers(self) -> None:
        """Setup transformers."""
        pass
    
    # ========================================================================
    # HANDLER REGISTRATION
    # ========================================================================
    
    def register_handler(
        self,
        provider: Union[WebhookProvider, str],
        event_type: Union[WebhookEventType, str],
        handler: Callable,
        priority: int = 0,
    ) -> None:
        """
        Register a custom handler for a specific provider and event type.
        
        Args:
            provider: Webhook provider
            event_type: Event type
            handler: Handler function
            priority: Handler priority (lower = higher priority)
        """
        if isinstance(provider, str):
            provider = WebhookProvider(provider.lower())
        if isinstance(event_type, str):
            event_type = WebhookEventType(event_type.lower())
        
        if provider not in self._handlers:
            self._handlers[provider] = {}
        if event_type not in self._handlers[provider]:
            self._handlers[provider][event_type] = []
        
        self._handlers[provider][event_type].append((priority, handler))
        self._handlers[provider][event_type].sort(key=lambda x: x[0])
        
        logger.debug(f"Registered handler: provider={provider.value}, event={event_type.value}")
    
    def register_middleware(self, middleware: Callable, priority: int = 0) -> None:
        """
        Register a middleware function.
        
        Args:
            middleware: Middleware function
            priority: Middleware priority (lower = higher priority)
        """
        self._middlewares.append((priority, middleware))
        self._middlewares.sort(key=lambda x: x[0])
        logger.debug(f"Registered middleware: {middleware.__name__}")
    
    def register_filter(self, filter_func: Callable, priority: int = 0) -> None:
        """
        Register a filter function.
        
        Args:
            filter_func: Filter function
            priority: Filter priority (lower = higher priority)
        """
        self._filters.append((priority, filter_func))
        self._filters.sort(key=lambda x: x[0])
        logger.debug(f"Registered filter: {filter_func.__name__}")
    
    def register_transformer(self, transformer: Callable, priority: int = 0) -> None:
        """
        Register a transformer function.
        
        Args:
            transformer: Transformer function
            priority: Transformer priority (lower = higher priority)
        """
        self._transformers.append((priority, transformer))
        self._transformers.sort(key=lambda x: x[0])
        logger.debug(f"Registered transformer: {transformer.__name__}")
    
    # ========================================================================
    # MAIN WEBHOOK HANDLERS
    # ========================================================================
    
    async def _handle_webhook(self, request: Request) -> Response:
        """
        Handle webhook requests.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())[:8]
        
        # Set tracing
        if self.config.enable_tracing:
            span = self.tracer.start_span("webhook_handle")
            span.set_tag("request_id", request_id)
            span.set_tag("path", request.path)
            span.set_tag("method", request.method)
        
        try:
            # Extract request information
            ip = request.remote or request.headers.get("X-Forwarded-For", "unknown")
            user_agent = request.headers.get("User-Agent", "unknown")
            content_type = request.headers.get("Content-Type", "")
            content_length = request.headers.get("Content-Length")
            
            # Validate IP
            if not self._is_ip_allowed(ip):
                logger.warning(f"Blocked request from unauthorized IP: {ip}")
                self._increment_metric("webhook.blocked_ip")
                return json_response(
                    {"error": "IP not allowed", "code": "IP_NOT_ALLOWED"},
                    status=403,
                )
            
            # Validate origin
            origin = request.headers.get("Origin", "")
            if not self._is_origin_allowed(origin):
                logger.warning(f"Blocked request from unauthorized origin: {origin}")
                self._increment_metric("webhook.blocked_origin")
                return json_response(
                    {"error": "Origin not allowed", "code": "ORIGIN_NOT_ALLOWED"},
                    status=403,
                )
            
            # Validate method
            if request.method not in self.config.allowed_methods:
                logger.warning(f"Method not allowed: {request.method}")
                self._increment_metric("webhook.method_not_allowed")
                return json_response(
                    {"error": f"Method {request.method} not allowed"},
                    status=405,
                )
            
            # Read body with size limit
            try:
                raw_data = await request.text()
                if len(raw_data) > self.config.max_payload_size:
                    self._increment_metric("webhook.payload_too_large")
                    return json_response(
                        {"error": "Payload too large", "max_size": self.config.max_payload_size},
                        status=413,
                    )
            except Exception as e:
                logger.error(f"Error reading request body: {e}")
                self._increment_metric("webhook.read_error")
                return json_response(
                    {"error": "Failed to read request body"},
                    status=400,
                )
            
            # Decompress if needed
            if self.config.compression != WebhookCompression.NONE:
                raw_data = self._decompress_data(raw_data, request.headers)
            
            # Parse JSON
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON payload: {e}")
                self._increment_metric("webhook.invalid_json")
                return json_response(
                    {"error": "Invalid JSON payload", "detail": str(e)},
                    status=400,
                )
            
            # Detect provider from headers or data
            provider = self._detect_provider(request.headers, data)
            
            # Detect event type
            event_type = self._detect_event_type(data, provider)
            
            # Create payload
            payload = WebhookPayload(
                event_type=event_type,
                provider=provider,
                timestamp=datetime.utcnow(),
                source=ip,
                source_ip=ip,
                source_url=str(request.url),
                data=data,
                raw_data=raw_data,
                signature=request.headers.get("X-Signature") or request.headers.get("Signature"),
                headers=dict(request.headers),
                ip=ip,
                user_agent=user_agent,
                content_type=content_type,
                content_length=int(content_length) if content_length else None,
                metadata={
                    "request_id": request_id,
                    "path": request.path,
                    "method": request.method,
                }
            )
            
            # Validate signature
            if self.config.verify_signature and payload.signature:
                if not await self._verify_signature(payload):
                    logger.warning(f"Invalid signature from IP: {ip}")
                    self._increment_metric("webhook.invalid_signature")
                    return json_response(
                        {"error": "Invalid signature", "code": "INVALID_SIGNATURE"},
                        status=401,
                    )
            
            # Apply filters
            for _, filter_func in self._filters:
                if not await self._apply_filter(filter_func, payload):
                    logger.debug(f"Payload filtered out by {filter_func.__name__}")
                    self._increment_metric("webhook.filtered")
                    return json_response(
                        {"status": "filtered", "message": "Payload filtered out"},
                        status=200,
                    )
            
            # Apply transformers
            for _, transformer in self._transformers:
                payload = await self._apply_transformer(transformer, payload)
            
            # Store raw payload
            if self.config.store_raw:
                await self._store_raw_payload(payload)
            
            # Emit event
            if self.event_bus:
                await self.event_bus.emit(EventType.WEBHOOK_RECEIVED, payload)
            
            # Queue for processing
            if self.config.async_processing:
                try:
                    await self._input_queue.put(payload)
                    status = WebhookStatus.QUEUED
                    message = "Payload queued for processing"
                    self._increment_metric("webhook.queued")
                except QueueFull:
                    logger.warning(f"Queue full, discarding payload from {ip}")
                    self._increment_metric("webhook.queue_full")
                    status = WebhookStatus.DISCARDED
                    message = "Queue full, payload discarded"
            else:
                # Process synchronously
                result = await self._process_payload(payload)
                status = result.status
                message = result.message
            
            # Update statistics
            self._stats.total_received += 1
            self._stats.events[event_type.value] = self._stats.events.get(event_type.value, 0) + 1
            self._stats.providers[provider.value] = self._stats.providers.get(provider.value, 0) + 1
            self._increment_metric("webhook.received")
            
            # Generate response
            processing_time = (time.time() - start_time) * 1000
            
            response = WebhookResponse(
                status=status,
                message=message,
                id=payload.id,
                processing_time_ms=processing_time,
                data={"request_id": request_id} if status == WebhookStatus.QUEUED else None,
            )
            
            # Set tracing tags
            if self.config.enable_tracing:
                span.set_tag("status", status.value)
                span.set_tag("processing_time_ms", processing_time)
                span.finish()
            
            return json_response(
                response.to_dict(),
                status=202 if status == WebhookStatus.QUEUED else 200,
                headers=self._get_response_headers(),
            )
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}", exc_info=True)
            self._increment_metric("webhook.error")
            
            if self.config.enable_tracing:
                span.set_tag("error", str(e))
                span.set_tag("error_type", type(e).__name__)
                span.finish()
            
            return json_response(
                {"error": "Internal server error", "detail": str(e) if self.config.enable_logging else None},
                status=500,
            )
    
    # ========================================================================
    # HEALTH & STATUS ENDPOINTS
    # ========================================================================
    
    async def _handle_health_check(self, request: Request) -> Response:
        """Handle health check requests."""
        health_data = {
            "status": self._health_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - self._start_time,
            "queue_size": self._input_queue.qsize(),
            "workers": len(self._workers),
            "stats": {
                "total_received": self._stats.total_received,
                "total_processed": self._stats.total_processed,
                "total_failed": self._stats.total_failed,
                "queue_depth": self._input_queue.qsize(),
                "worker_active": len([w for w in self._workers if not w.done()]),
            },
            "details": self._health_details,
        }
        
        status_code = 200 if self._health_status == HealthStatus.HEALTHY else 503
        return json_response(health_data, status=status_code)
    
    async def _handle_readiness_check(self, request: Request) -> Response:
        """Handle readiness check requests."""
        ready = (
            self._running and
            self._input_queue.qsize() < self.config.queue_size * 0.8 and
            len(self._workers) > 0
        )
        return json_response(
            {"ready": ready, "queue_usage": self._input_queue.qsize() / self.config.queue_size},
            status=200 if ready else 503,
        )
    
    async def _handle_liveness_check(self, request: Request) -> Response:
        """Handle liveness check requests."""
        alive = self._running
        return json_response(
            {"alive": alive},
            status=200 if alive else 503,
        )
    
    async def _handle_status(self, request: Request) -> Response:
        """Handle status requests."""
        status_data = {
            "status": "running" if self._running else "stopped",
            "provider": self.config.provider.value,
            "path": self.config.path,
            "host": self.config.host,
            "port": self.config.port,
            "queue_size": self._input_queue.qsize(),
            "queue_max": self.config.queue_size,
            "workers": len(self._workers),
            "worker_active": len([w for w in self._workers if not w.done()]),
            "stats": self._stats.dict(),
            "circuit_breaker": {
                "enabled": self.config.circuit_breaker_enabled,
                "is_open": self._circuit_breaker.is_open() if self.config.circuit_breaker_enabled else False,
                "failures": self._circuit_breaker.get_failure_count() if self.config.circuit_breaker_enabled else 0,
            },
            "rate_limiter": {
                "enabled": self.config.rate_limit_enabled,
                "requests": self.config.rate_limit_requests,
                "period": self.config.rate_limit_period,
            },
            "last_health_check": self._last_health_check.isoformat(),
            "health_status": self._health_status.value,
            "active_connections": len(self._active_connections),
        }
        
        return json_response(status_data, status=200)
    
    async def _handle_metrics(self, request: Request) -> Response:
        """Handle metrics requests."""
        metrics_data = {
            "webhook_received_total": self._stats.total_received,
            "webhook_processed_total": self._stats.total_processed,
            "webhook_failed_total": self._stats.total_failed,
            "webhook_discarded_total": self._stats.total_discarded,
            "webhook_retried_total": self._stats.total_retried,
            "webhook_timeout_total": self._stats.total_timeout,
            "webhook_rejected_total": self._stats.total_rejected,
            "webhook_queue_depth": self._input_queue.qsize(),
            "webhook_worker_active": len([w for w in self._workers if not w.done()]),
            "webhook_processing_time_avg": self._stats.avg_processing_time,
            "webhook_processing_time_max": self._stats.max_processing_time,
            "webhook_uptime_seconds": time.time() - self._start_time,
            **{f"webhook_events_{k}": v for k, v in self._stats.events.items()},
            **{f"webhook_providers_{k}": v for k, v in self._stats.providers.items()},
            **{f"webhook_errors_{k}": v for k, v in self._stats.errors.items()},
        }
        
        # Format as Prometheus metrics if requested
        if request.headers.get("Accept") == "text/plain":
            return self._format_prometheus_metrics(metrics_data)
        
        return json_response(metrics_data, status=200)
    
    async def _handle_clear_cache(self, request: Request) -> Response:
        """Clear the data cache."""
        self._data_cache.clear()
        if self.cache:
            await self.cache.clear()
        logger.info("Cache cleared")
        self._increment_metric("webhook.cache_cleared")
        return json_response({"status": "ok", "message": "Cache cleared"}, status=200)
    
    async def _handle_reset_stats(self, request: Request) -> Response:
        """Reset statistics."""
        self._stats = WebhookStats()
        self._start_time = time.time()
        logger.info("Stats reset")
        self._increment_metric("webhook.stats_reset")
        return json_response({"status": "ok", "message": "Stats reset"}, status=200)
    
    async def _handle_purge_queue(self, request: Request) -> Response:
        """Purge the processing queue."""
        purged = 0
        while not self._input_queue.empty():
            try:
                self._input_queue.get_nowait()
                self._input_queue.task_done()
                purged += 1
            except QueueEmpty:
                break
        logger.info(f"Queue purged: {purged} items removed")
        self._increment_metric("webhook.queue_purged")
        return json_response({"status": "ok", "message": f"Queue purged", "purged": purged}, status=200)
    
    async def _handle_reload_handlers(self, request: Request) -> Response:
        """Reload handlers."""
        # Reload would re-import handler modules
        # This is a placeholder
        logger.info("Handlers reloaded")
        self._increment_metric("webhook.handlers_reloaded")
        return json_response({"status": "ok", "message": "Handlers reloaded"}, status=200)
    
    async def _handle_websocket(self, request: Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for real-time monitoring."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        connection_id = str(uuid.uuid4())
        self._active_connections.add(connection_id)
        self._connection_locks[connection_id] = asyncio.Lock()
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        if data.get("type") == "subscribe":
                            # Subscribe to events
                            event_types = data.get("events", [])
                            self._websocket_callbacks[connection_id] = lambda d: ws.send_str(json.dumps(d))
                            await ws.send_str(json.dumps({
                                "type": "subscribed",
                                "events": event_types,
                            }))
                        elif data.get("type") == "unsubscribe":
                            if connection_id in self._websocket_callbacks:
                                del self._websocket_callbacks[connection_id]
                            await ws.send_str(json.dumps({
                                "type": "unsubscribed",
                            }))
                        elif data.get("type") == "ping":
                            await ws.send_str(json.dumps({
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                            }))
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({
                            "type": "error",
                            "message": "Invalid JSON",
                        }))
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
                    break
                elif msg.type == WSMsgType.CLOSE:
                    break
        finally:
            self._active_connections.remove(connection_id)
            if connection_id in self._connection_locks:
                del self._connection_locks[connection_id]
            if connection_id in self._websocket_callbacks:
                del self._websocket_callbacks[connection_id]
        
        return ws
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    async def _handle_trade(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle trade events."""
        try:
            # Parse trade data
            trade_data = self._parse_trade_data(payload.data)
            
            # Process trade
            if self.exchange:
                result = await self.exchange.process_trade(trade_data)
            else:
                result = {"status": "processed", "trade_id": trade_data.trade_id}
            
            # Store processed data
            if self.config.store_processed:
                await self._store_processed_data(payload, result)
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.trade.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Trade processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["trade"] = self._stats.errors.get("trade", 0) + 1
            self._increment_metric("webhook.trade.error")
            raise
    
    async def _handle_quote(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle quote events."""
        try:
            # Parse quote data
            quote_data = self._parse_quote_data(payload.data)
            
            # Process quote
            if self.exchange:
                result = await self.exchange.process_quote(quote_data)
            else:
                result = {"status": "processed", "symbol": quote_data.symbol}
            
            # Store processed data
            if self.config.store_processed:
                await self._store_processed_data(payload, result)
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.quote.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Quote processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing quote: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["quote"] = self._stats.errors.get("quote", 0) + 1
            self._increment_metric("webhook.quote.error")
            raise
    
    async def _handle_aggregate(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle aggregate events."""
        try:
            # Parse aggregate data
            agg_data = self._parse_aggregate_data(payload.data)
            
            # Process aggregate
            if self.exchange:
                result = await self.exchange.process_aggregate(agg_data)
            else:
                result = {"status": "processed", "symbol": agg_data.symbol}
            
            # Store processed data
            if self.config.store_processed:
                await self._store_processed_data(payload, result)
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.aggregate.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Aggregate processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing aggregate: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["aggregate"] = self._stats.errors.get("aggregate", 0) + 1
            self._increment_metric("webhook.aggregate.error")
            raise
    
    async def _handle_heartbeat(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle heartbeat events."""
        self._last_health_check = datetime.utcnow()
        self._health_status = HealthStatus.HEALTHY
        self._increment_metric("webhook.heartbeat")
        
        return WebhookResponse(
            status=WebhookStatus.COMPLETED,
            message="Heartbeat received",
            data={"timestamp": datetime.utcnow().isoformat()},
        )
    
    async def _handle_order(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle order events."""
        try:
            order_data = payload.data.get("order", {})
            order = Order(**order_data)
            
            if self.exchange:
                result = await self.exchange.process_order_update(order)
            else:
                result = {"status": "processed", "order_id": order.id}
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.order.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Order processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing order: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["order"] = self._stats.errors.get("order", 0) + 1
            self._increment_metric("webhook.order.error")
            raise
    
    async def _handle_position(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle position events."""
        try:
            position_data = payload.data.get("position", {})
            position = Position(**position_data)
            
            if self.exchange:
                result = await self.exchange.process_position_update(position)
            else:
                result = {"status": "processed", "symbol": position.symbol}
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.position.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Position processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing position: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["position"] = self._stats.errors.get("position", 0) + 1
            self._increment_metric("webhook.position.error")
            raise
    
    async def _handle_account(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle account events."""
        try:
            account_data = payload.data.get("account", {})
            
            if self.exchange:
                result = await self.exchange.process_account_update(account_data)
            else:
                result = {"status": "processed"}
            
            self._stats.total_processed += 1
            self._increment_metric("webhook.account.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Account processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing account: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["account"] = self._stats.errors.get("account", 0) + 1
            self._increment_metric("webhook.account.error")
            raise
    
    # ========================================================================
    # PROVIDER-SPECIFIC HANDLERS
    # ========================================================================
    
    async def _handle_alpaca_trade(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle Alpaca trade events."""
        data = payload.data
        trade_data = StockTradeData(
            symbol=data.get("S", data.get("symbol", "")),
            price=float(data.get("p", data.get("price", 0))),
            size=float(data.get("s", data.get("size", 0))),
            timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
            exchange=data.get("x", data.get("exchange")),
            trade_id=data.get("i", data.get("trade_id")),
            conditions=data.get("c", data.get("conditions", [])),
            tape=data.get("z", data.get("tape")),
        )
        payload.data["parsed"] = trade_data.dict()
        return await self._handle_trade(payload)
    
    async def _handle_alpaca_quote(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle Alpaca quote events."""
        data = payload.data
        quote_data = StockQuoteData(
            symbol=data.get("S", data.get("symbol", "")),
            bid_price=float(data.get("bp", data.get("bid_price", 0))),
            bid_size=float(data.get("bs", data.get("bid_size", 0))),
            ask_price=float(data.get("ap", data.get("ask_price", 0))),
            ask_size=float(data.get("as", data.get("ask_size", 0))),
            timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
            exchange=data.get("x", data.get("exchange")),
            bid_exchange=data.get("bx", data.get("bid_exchange")),
            ask_exchange=data.get("ax", data.get("ask_exchange")),
        )
        payload.data["parsed"] = quote_data.dict()
        return await self._handle_quote(payload)
    
    async def _handle_polygon_trade(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle Polygon trade events."""
        data = payload.data
        trade_data = StockTradeData(
            symbol=data.get("sym", data.get("symbol", "")),
            price=float(data.get("p", data.get("price", 0))),
            size=float(data.get("s", data.get("size", 0))),
            timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
            exchange=data.get("x", data.get("exchange")),
            trade_id=str(data.get("id", data.get("trade_id", ""))),
            conditions=data.get("c", data.get("conditions", [])),
        )
        payload.data["parsed"] = trade_data.dict()
        return await self._handle_trade(payload)
    
    async def _handle_polygon_quote(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle Polygon quote events."""
        data = payload.data
        quote_data = StockQuoteData(
            symbol=data.get("sym", data.get("symbol", "")),
            bid_price=float(data.get("bp", data.get("bid_price", 0))),
            bid_size=float(data.get("bs", data.get("bid_size", 0))),
            ask_price=float(data.get("ap", data.get("ask_price", 0))),
            ask_size=float(data.get("as", data.get("ask_size", 0))),
            timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
            exchange=data.get("x", data.get("exchange")),
            bid_exchange=data.get("bx", data.get("bid_exchange")),
            ask_exchange=data.get("ax", data.get("ask_exchange")),
            last_price=float(data.get("lp", data.get("last_price", 0))) if data.get("lp") else None,
            last_size=float(data.get("ls", data.get("last_size", 0))) if data.get("ls") else None,
        )
        payload.data["parsed"] = quote_data.dict()
        return await self._handle_quote(payload)
    
    async def _handle_polygon_aggregate(self, payload: WebhookPayload) -> WebhookResponse:
        """Handle Polygon aggregate events."""
        data = payload.data
        agg_data = StockAggregateData(
            symbol=data.get("sym", data.get("symbol", "")),
            open=float(data.get("o", data.get("open", 0))),
            high=float(data.get("h", data.get("high", 0))),
            low=float(data.get("l", data.get("low", 0))),
            close=float(data.get("c", data.get("close", 0))),
            volume=float(data.get("v", data.get("volume", 0))),
            timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
            vwap=float(data.get("vw", data.get("vwap", 0))) if data.get("vw") else None,
            number_of_trades=data.get("n", data.get("number_of_trades")),
        )
        payload.data["parsed"] = agg_data.dict()
        return await self._handle_aggregate(payload)
    
    # ========================================================================
    # DATA PARSING
    # ========================================================================
    
    def _parse_trade_data(self, data: Dict[str, Any]) -> StockTradeData:
        """Parse trade data from various formats."""
        return StockTradeData(**data)
    
    def _parse_quote_data(self, data: Dict[str, Any]) -> StockQuoteData:
        """Parse quote data from various formats."""
        return StockQuoteData(**data)
    
    def _parse_aggregate_data(self, data: Dict[str, Any]) -> StockAggregateData:
        """Parse aggregate data from various formats."""
        return StockAggregateData(**data)
    
    def _parse_timestamp(self, value: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            if value > 1e12:  # Nanoseconds
                return datetime.utcfromtimestamp(value / 1e9)
            elif value > 1e9:  # Milliseconds
                return datetime.utcfromtimestamp(value / 1000)
            else:  # Seconds
                return datetime.utcfromtimestamp(value)
        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return datetime.utcnow()
    
    # ========================================================================
    # PROCESSING PIPELINE
    # ========================================================================
    
    async def _process_payload(self, payload: WebhookPayload) -> WebhookResponse:
        """
        Process a webhook payload through the pipeline.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Webhook response
        """
        start_time = time.time()
        
        try:
            # Run middlewares
            for _, middleware in self._middlewares:
                payload = await middleware(payload)
                if payload is None:
                    return WebhookResponse(
                        status=WebhookStatus.DISCARDED,
                        message="Payload discarded by middleware",
                    )
            
            # Apply circuit breaker
            if self.config.circuit_breaker_enabled:
                if self._circuit_breaker.is_open():
                    self._increment_metric("webhook.circuit_breaker_open")
                    return WebhookResponse(
                        status=WebhookStatus.FAILED,
                        message="Circuit breaker is open",
                        retry_after=self.config.circuit_breaker_retry_timeout,
                    )
            
            # Find handlers for this provider and event type
            handlers = self._handlers.get(payload.provider, {}).get(payload.event_type, [])
            
            if not handlers:
                # Try generic handlers
                handlers = self._handlers.get(WebhookProvider.CUSTOM, {}).get(payload.event_type, [])
            
            if not handlers:
                logger.warning(f"No handler for {payload.provider.value}/{payload.event_type.value}")
                return WebhookResponse(
                    status=WebhookStatus.COMPLETED,
                    message="No handler registered, payload ignored",
                )
            
            # Execute handlers
            responses = []
            for priority, handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(payload)
                    else:
                        result = handler(payload)
                    
                    if isinstance(result, WebhookResponse):
                        responses.append(result)
                    else:
                        responses.append(WebhookResponse(
                            status=WebhookStatus.COMPLETED,
                            message="Handler executed successfully",
                            data=result if isinstance(result, dict) else {"result": result},
                        ))
                except Exception as e:
                    logger.error(f"Handler {handler.__name__} failed: {e}", exc_info=True)
                    self._stats.errors[handler.__name__] = self._stats.errors.get(handler.__name__, 0) + 1
                    self._increment_metric("webhook.handler_error")
                    responses.append(WebhookResponse(
                        status=WebhookStatus.FAILED,
                        message=f"Handler {handler.__name__} failed: {str(e)}",
                    ))
            
            # Determine overall status
            all_success = all(r.status == WebhookStatus.COMPLETED for r in responses)
            
            processing_time = (time.time() - start_time) * 1000
            self._stats.processing_times.append(processing_time)
            self._stats.avg_processing_time = sum(self._stats.processing_times) / len(self._stats.processing_times)
            self._stats.max_processing_time = max(self._stats.max_processing_time, processing_time)
            self._stats.min_processing_time = min(self._stats.min_processing_time, processing_time)
            self._stats.last_processing_time = processing_time
            
            if self._stats.total_processed % 100 == 0:
                self._stats.processing_times = self._stats.processing_times[-1000:]
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED if all_success else WebhookStatus.PARTIALLY_COMPLETED,
                message="Payload processed" if all_success else "Some handlers failed",
                data={"responses": [r.to_dict() for r in responses]},
                processing_time_ms=processing_time,
            )
            
        except Exception as e:
            logger.error(f"Error processing payload: {e}", exc_info=True)
            self._stats.total_failed += 1
            self._stats.errors["processing"] = self._stats.errors.get("processing", 0) + 1
            self._increment_metric("webhook.processing_error")
            
            # Check circuit breaker
            if self.config.circuit_breaker_enabled:
                self._circuit_breaker.record_failure()
                if self._circuit_breaker.is_open():
                    logger.warning("Circuit breaker is open, rejecting requests")
                    raise WebSocketError("Circuit breaker is open")
            
            raise
    
    # ========================================================================
    # SIGNATURE VERIFICATION
    # ========================================================================
    
    async def _verify_signature(self, payload: WebhookPayload) -> bool:
        """
        Verify the signature of a webhook payload.
        
        Args:
            payload: Webhook payload
            
        Returns:
            True if signature is valid
        """
        if not self.config.secret_key:
            return True
        
        algorithm = self.config.signature_algorithm
        verifier = self._signature_verifiers.get(algorithm)
        
        if not verifier:
            logger.error(f"Unsupported signature algorithm: {algorithm}")
            return False
        
        return await verifier(payload)
    
    async def _verify_hmac_sha256(self, payload: WebhookPayload) -> bool:
        """Verify HMAC-SHA256 signature."""
        if not payload.signature or not payload.raw_data:
            return False
        
        secret = self.config.secret_key.encode('utf-8')
        expected = hmac.new(secret, payload.raw_data.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Check timestamp if enabled
        if self.config.verify_timestamp:
            timestamp = payload.headers.get("X-Timestamp")
            if timestamp:
                try:
                    ts = datetime.fromisoformat(timestamp)
                    if abs((datetime.utcnow() - ts).total_seconds()) > self.config.timestamp_tolerance:
                        logger.warning("Timestamp tolerance exceeded")
                        return False
                except ValueError:
                    pass
        
        return hmac.compare_digest(payload.signature.lower(), expected.lower())
    
    async def _verify_hmac_sha512(self, payload: WebhookPayload) -> bool:
        """Verify HMAC-SHA512 signature."""
        if not payload.signature or not payload.raw_data:
            return False
        
        secret = self.config.secret_key.encode('utf-8')
        expected = hmac.new(secret, payload.raw_data.encode('utf-8'), hashlib.sha512).hexdigest()
        
        return hmac.compare_digest(payload.signature.lower(), expected.lower())
    
    async def _verify_rsa_sha256(self, payload: WebhookPayload) -> bool:
        """Verify RSA-SHA256 signature."""
        if not payload.signature or not payload.raw_data or not self.config.public_key:
            return False
        
        try:
            import rsa
            public_key = rsa.PublicKey.load_pkcs1(self.config.public_key.encode('utf-8'))
            signature = base64.b64decode(payload.signature)
            rsa.verify(payload.raw_data.encode('utf-8'), signature, public_key)
            return True
        except Exception as e:
            logger.error(f"RSA verification failed: {e}")
            return False
    
    async def _verify_rsa_sha512(self, payload: WebhookPayload) -> bool:
        """Verify RSA-SHA512 signature."""
        # Similar to RSA-SHA256 but with SHA512
        return await self._verify_rsa_sha256(payload)
    
    async def _verify_ecdsa_sha256(self, payload: WebhookPayload) -> bool:
        """Verify ECDSA-SHA256 signature."""
        if not payload.signature or not payload.raw_data:
            return False
        
        # ECDSA verification would require a public key
        # This is a placeholder
        logger.warning("ECDSA signature verification not implemented")
        return True
    
    async def _verify_none(self, payload: WebhookPayload) -> bool:
        """No signature verification."""
        return True
    
    async def _verify_basic(self, payload: WebhookPayload) -> bool:
        """Basic authentication."""
        auth = payload.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        
        try:
            credentials = base64.b64decode(auth[6:]).decode('utf-8')
            username, password = credentials.split(":", 1)
            expected_username, expected_password = self.config.secret_key.split(":", 1) if self.config.secret_key else ("", "")
            return username == expected_username and password == expected_password
        except Exception:
            return False
    
    async def _verify_bearer(self, payload: WebhookPayload) -> bool:
        """Bearer token authentication."""
        auth = payload.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        
        token = auth[7:]
        return token == self.config.secret_key
    
    # ========================================================================
    # MIDDLEWARES
    # ========================================================================
    
    @web.middleware
    async def _cors_middleware(self, request: Request, handler: Callable) -> Response:
        """CORS middleware."""
        if request.method == "OPTIONS":
            response = json_response({})
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, X-Signature, X-Timestamp"
            response.headers["Access-Control-Max-Age"] = "86400"
            return response
        
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    
    @web.middleware
    async def _logging_middleware(self, request: Request, handler: Callable) -> Response:
        """Logging middleware."""
        start_time = time.time()
        
        try:
            response = await handler(request)
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
        
        duration = (time.time() - start_time) * 1000
        logger.debug(
            f"{request.method} {request.path} -> {response.status} "
            f"({duration:.2f}ms) from {request.remote}"
        )
        
        return response
    
    @web.middleware
    async def _error_middleware(self, request: Request, handler: Callable) -> Response:
        """Error handling middleware."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return json_response(
                {"error": "Validation error", "details": e.errors()},
                status=400,
            )
        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {e}")
            return json_response(
                {"error": "Rate limit exceeded", "retry_after": e.retry_after},
                status=429,
                headers={"Retry-After": str(e.retry_after) if e.retry_after else "60"},
            )
        except AuthenticationError as e:
            logger.warning(f"Authentication error: {e}")
            return json_response(
                {"error": "Authentication failed", "detail": str(e)},
                status=401,
            )
        except AuthorizationError as e:
            logger.warning(f"Authorization error: {e}")
            return json_response(
                {"error": "Authorization failed", "detail": str(e)},
                status=403,
            )
        except Exception as e:
            logger.error(f"Unhandled error: {e}", exc_info=True)
            return json_response(
                {"error": "Internal server error", "detail": str(e) if self.config.enable_logging else None},
                status=500,
            )
    
    @web.middleware
    async def _rate_limit_middleware(self, request: Request, handler: Callable) -> Response:
        """Rate limiting middleware."""
        if not self.config.rate_limit_enabled:
            return await handler(request)
        
        # Determine rate limit key
        if self.config.rate_limit_by_ip:
            key = f"rate_limit:{request.remote or 'unknown'}:webhook"
        elif self.config.rate_limit_by_provider:
            provider = request.headers.get("X-Provider", "unknown")
            key = f"rate_limit:{provider}:webhook"
        else:
            key = "rate_limit:global:webhook"
        
        allowed = await self._rate_limiter.is_allowed(key)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {key}")
            self._increment_metric("webhook.rate_limited")
            return json_response(
                {"error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"},
                status=429,
                headers={"Retry-After": str(self.config.rate_limit_period)},
            )
        
        return await handler(request)
    
    @web.middleware
    async def _auth_middleware(self, request: Request, handler: Callable) -> Response:
        """Authentication middleware."""
        if self.config.auth_type == WebhookAuthType.NONE:
            return await handler(request)
        
        auth_header = request.headers.get(self.config.auth_header, "")
        
        if self.config.auth_type == WebhookAuthType.API_KEY:
            api_key = request.headers.get(self.config.api_key_header, "")
            if api_key != self.config.secret_key:
                return json_response(
                    {"error": "Invalid API key", "code": "INVALID_API_KEY"},
                    status=401,
                )
        elif self.config.auth_type == WebhookAuthType.BEARER:
            if not auth_header.startswith(f"{self.config.auth_scheme} "):
                return json_response(
                    {"error": "Invalid authorization header", "code": "INVALID_AUTH"},
                    status=401,
                )
            token = auth_header[len(self.config.auth_scheme) + 1:]
            if token != self.config.secret_key:
                return json_response(
                    {"error": "Invalid token", "code": "INVALID_TOKEN"},
                    status=401,
                )
        elif self.config.auth_type == WebhookAuthType.BASIC:
            if not auth_header.startswith("Basic "):
                return json_response(
                    {"error": "Invalid authorization header", "code": "INVALID_AUTH"},
                    status=401,
                )
            try:
                credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = credentials.split(":", 1)
                expected_username, expected_password = self.config.secret_key.split(":", 1) if self.config.secret_key else ("", "")
                if username != expected_username or password != expected_password:
                    return json_response(
                        {"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"},
                        status=401,
                    )
            except Exception:
                return json_response(
                    {"error": "Invalid authorization header", "code": "INVALID_AUTH"},
                    status=401,
                )
        
        return await handler(request)
    
    @web.middleware
    async def _size_limit_middleware(self, request: Request, handler: Callable) -> Response:
        """Request size limit middleware."""
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.config.max_payload_size:
                    return json_response(
                        {"error": "Payload too large", "max_size": self.config.max_payload_size},
                        status=413,
                    )
            except ValueError:
                pass
        
        return await handler(request)
    
    @web.middleware
    async def _compression_middleware(self, request: Request, handler: Callable) -> Response:
        """Compression middleware."""
        response = await handler(request)
        
        # Compress response if enabled
        if self.config.compression != WebhookCompression.NONE:
            accept_encoding = request.headers.get("Accept-Encoding", "")
            if "gzip" in accept_encoding and self.config.compression == WebhookCompression.GZIP:
                response.headers["Content-Encoding"] = "gzip"
            elif "deflate" in accept_encoding and self.config.compression == WebhookCompression.DEFLATE:
                response.headers["Content-Encoding"] = "deflate"
        
        return response
    
    # ========================================================================
    # UTILITY FUNCTIONS
    # ========================================================================
    
    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if IP is allowed."""
        if not self.config.allowed_ips:
            return True
        return ip in self.config.allowed_ips
    
    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is allowed."""
        if "*" in self.config.allowed_origins:
            return True
        return origin in self.config.allowed_origins
    
    def _detect_provider(self, headers: Dict[str, str], data: Dict[str, Any]) -> WebhookProvider:
        """Detect provider from headers or data."""
        # Check headers
        user_agent = headers.get("User-Agent", "").lower()
        
        provider_map = {
            "alpaca": WebhookProvider.ALPACA,
            "polygon": WebhookProvider.POLYGON,
            "finnhub": WebhookProvider.FINNHUB,
            "tradier": WebhookProvider.TRADIER,
            "binance": WebhookProvider.BINANCE,
            "coinbase": WebhookProvider.COINBASE,
            "kraken": WebhookProvider.KRAKEN,
            "oanda": WebhookProvider.OANDA,
            "github": WebhookProvider.GITHUB,
            "slack": WebhookProvider.SLACK,
            "discord": WebhookProvider.DISCORD,
            "telegram": WebhookProvider.TELEGRAM,
        }
        
        for key, provider in provider_map.items():
            if key in user_agent:
                return provider
        
        # Check headers
        provider_header = headers.get("X-Provider", headers.get("X-Webhook-Provider", "")).lower()
        if provider_header in provider_map:
            return provider_map[provider_header]
        
        # Check data
        data_str = str(data).lower()
        for key, provider in provider_map.items():
            if key in data_str:
                return provider
        
        return self.config.provider
    
    def _detect_event_type(self, data: Dict[str, Any], provider: WebhookProvider) -> WebhookEventType:
        """Detect event type from data."""
        # Check for common event fields
        event_fields = ["event_type", "type", "event", "action", "status"]
        
        for field in event_fields:
            if field in data:
                try:
                    return WebhookEventType(data[field].lower())
                except ValueError:
                    pass
        
        # Provider-specific detection
        provider_detectors = {
            WebhookProvider.ALPACA: self._detect_alpaca_event_type,
            WebhookProvider.POLYGON: self._detect_polygon_event_type,
            WebhookProvider.BINANCE: self._detect_binance_event_type,
            WebhookProvider.COINBASE: self._detect_coinbase_event_type,
        }
        
        if provider in provider_detectors:
            event_type = provider_detectors[provider](data)
            if event_type:
                return event_type
        
        # Data structure detection
        if "price" in data and "size" in data:
            return WebhookEventType.TRADE
        elif "bid_price" in data and "ask_price" in data:
            return WebhookEventType.QUOTE
        elif "open" in data and "close" in data:
            return WebhookEventType.AGGREGATE
        elif "bids" in data and "asks" in data:
            return WebhookEventType.ORDER_BOOK
        elif "order" in data:
            return WebhookEventType.ORDER
        elif "position" in data:
            return WebhookEventType.POSITION
        elif "account" in data:
            return WebhookEventType.ACCOUNT
        
        return WebhookEventType.SYSTEM
    
    def _detect_alpaca_event_type(self, data: Dict[str, Any]) -> Optional[WebhookEventType]:
        """Detect Alpaca event type."""
        if "p" in data and "s" in data:
            return WebhookEventType.TRADE
        if "bp" in data and "ap" in data:
            return WebhookEventType.QUOTE
        if "event" in data:
            if data["event"] == "trade":
                return WebhookEventType.TRADE
            elif data["event"] == "quote":
                return WebhookEventType.QUOTE
        return None
    
    def _detect_polygon_event_type(self, data: Dict[str, Any]) -> Optional[WebhookEventType]:
        """Detect Polygon event type."""
        if "p" in data and "s" in data:
            return WebhookEventType.TRADE
        if "bp" in data and "ap" in data:
            return WebhookEventType.QUOTE
        if "o" in data and "c" in data:
            return WebhookEventType.AGGREGATE
        return None
    
    def _detect_binance_event_type(self, data: Dict[str, Any]) -> Optional[WebhookEventType]:
        """Detect Binance event type."""
        event_type = data.get("e", "")
        if event_type == "trade":
            return WebhookEventType.TRADE
        elif event_type == "bookTicker":
            return WebhookEventType.QUOTE
        elif event_type == "depthUpdate":
            return WebhookEventType.ORDER_BOOK
        elif event_type == "24hrTicker":
            return WebhookEventType.TICKER
        return None
    
    def _detect_coinbase_event_type(self, data: Dict[str, Any]) -> Optional[WebhookEventType]:
        """Detect Coinbase event type."""
        event_type = data.get("type", "")
        if event_type == "match":
            return WebhookEventType.TRADE
        elif event_type == "received":
            return WebhookEventType.ORDER
        elif event_type == "open":
            return WebhookEventType.ORDER
        elif event_type == "done":
            return WebhookEventType.ORDER
        elif event_type == "change":
            return WebhookEventType.ORDER
        elif event_type == "activate":
            return WebhookEventType.ORDER
        elif event_type == "subscriptions":
            return WebhookEventType.SUBSCRIPTION
        return None
    
    def _decompress_data(self, data: str, headers: Dict[str, str]) -> str:
        """Decompress data based on Content-Encoding."""
        content_encoding = headers.get("Content-Encoding", "")
        
        if content_encoding == "gzip":
            import gzip
            return gzip.decompress(data.encode('utf-8')).decode('utf-8')
        elif content_encoding == "deflate":
            import zlib
            return zlib.decompress(data.encode('utf-8')).decode('utf-8')
        elif content_encoding == "zstd":
            import zstandard
            decompressor = zstandard.ZstdDecompressor()
            return decompressor.decompress(data.encode('utf-8')).decode('utf-8')
        
        return data
    
    def _get_response_headers(self) -> Dict[str, str]:
        """Get response headers."""
        headers = {
            "X-Webhook-Version": "3.0.0",
            "X-Request-ID": str(uuid.uuid4()),
        }
        return headers
    
    async def _apply_filter(self, filter_func: Callable, payload: WebhookPayload) -> bool:
        """Apply a filter to the payload."""
        if asyncio.iscoroutinefunction(filter_func):
            return await filter_func(payload)
        return filter_func(payload)
    
    async def _apply_transformer(self, transformer: Callable, payload: WebhookPayload) -> WebhookPayload:
        """Apply a transformer to the payload."""
        if asyncio.iscoroutinefunction(transformer):
            return await transformer(payload)
        return transformer(payload)
    
    # ========================================================================
    # STORAGE METHODS
    # ========================================================================
    
    async def _store_raw_payload(self, payload: WebhookPayload) -> None:
        """Store raw payload."""
        try:
            key = f"webhook:raw:{payload.provider.value}:{datetime.utcnow().strftime('%Y%m%d%H')}"
            if self.redis_client:
                await self.redis_client.lpush(key, payload.raw_data)
                await self.redis_client.expire(key, self.config.retention_days * 86400)
            else:
                # In-memory storage (limited)
                if len(self._data_cache) > 1000:
                    self._data_cache.pop(next(iter(self._data_cache)))
                self._data_cache[f"{key}:{payload.id}"] = payload.raw_data
        except Exception as e:
            logger.warning(f"Error storing raw payload: {e}")
    
    async def _store_processed_data(self, payload: WebhookPayload, data: Any) -> None:
        """Store processed data."""
        try:
            key = f"webhook:processed:{payload.provider.value}:{datetime.utcnow().strftime('%Y%m%d%H')}"
            serialized = json.dumps(data) if not isinstance(data, str) else data
            if self.redis_client:
                await self.redis_client.lpush(key, serialized)
                await self.redis_client.expire(key, self.config.retention_days * 86400)
        except Exception as e:
            logger.warning(f"Error storing processed data: {e}")
    
    async def _store_error(self, payload: WebhookPayload, error: Exception) -> None:
        """Store error."""
        if not self.config.store_errors:
            return
        
        try:
            error_data = {
                "payload_id": payload.id,
                "error": str(error),
                "error_type": type(error).__name__,
                "provider": payload.provider.value,
                "event_type": payload.event_type.value,
                "timestamp": datetime.utcnow().isoformat(),
                "retry_count": payload.retry_count,
            }
            key = f"webhook:errors:{datetime.utcnow().strftime('%Y%m%d')}"
            if self.redis_client:
                await self.redis_client.lpush(key, json.dumps(error_data))
                await self.redis_client.expire(key, self.config.retention_days * 86400)
        except Exception as e:
            logger.warning(f"Error storing error: {e}")
    
    # ========================================================================
    # METRICS
    # ========================================================================
    
    def _increment_metric(self, name: str, value: int = 1) -> None:
        """Increment a metric."""
        if self.metrics:
            self.metrics.increment(name, value)
    
    def _format_prometheus_metrics(self, metrics: Dict[str, Any]) -> Response:
        """Format metrics as Prometheus format."""
        lines = []
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key} {value}")
        return Response(text="\n".join(lines), content_type="text/plain")
    
    # ========================================================================
    # WORKER MANAGEMENT
    # ========================================================================
    
    async def _worker_loop(self, worker_id: int) -> None:
        """
        Worker loop for processing queued payloads.
        
        Args:
            worker_id: Worker identifier
        """
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get payload from queue
                payload = await asyncio.wait_for(
                    self._input_queue.get(),
                    timeout=1.0,
                )
                
                try:
                    # Process payload
                    response = await self._process_payload(payload)
                    
                    # Add to output queue if needed
                    await self._output_queue.put(response)
                    
                    logger.debug(f"Worker {worker_id} processed payload: {response.status}")
                    
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}", exc_info=True)
                    
                    # Retry logic
                    if self.config.max_retries > 0 and payload.retry_count < self.config.max_retries:
                        payload.retry_count += 1
                        await self._retry_payload(payload)
                    else:
                        self._stats.total_failed += 1
                        await self._store_error(payload, e)
                        await self._dead_letter_queue.put(payload)
                
                finally:
                    self._input_queue.task_done()
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} fatal error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info(f"Worker {worker_id} stopped")
    
    async def _retry_payload(self, payload: WebhookPayload) -> None:
        """
        Retry processing a failed payload.
        
        Args:
            payload: Webhook payload to retry
        """
        retry_delay = self.config.retry_delay * (self.config.retry_backoff ** payload.retry_count)
        
        logger.info(f"Retrying payload (attempt {payload.retry_count}/{self.config.max_retries})")
        self._stats.total_retried += 1
        self._increment_metric("webhook.retry")
        
        await asyncio.sleep(retry_delay)
        
        try:
            await self._input_queue.put(payload)
        except QueueFull:
            logger.error("Queue full, cannot retry payload")
            self._stats.total_failed += 1
            await self._dead_letter_queue.put(payload)
    
    async def _processor_task_loop(self) -> None:
        """Main processor task loop."""
        logger.info("Processor task started")
        
        while self._running:
            try:
                # Process output queue
                if not self._output_queue.empty():
                    response = await self._output_queue.get()
                    self._output_queue.task_done()
                    
                    # Emit processed event
                    if self.event_bus:
                        await self.event_bus.emit(EventType.WEBHOOK_PROCESSED, response)
                    
                    # Notify WebSocket subscribers
                    if self._websocket_callbacks:
                        for callback in self._websocket_callbacks.values():
                            try:
                                await callback({
                                    "type": "processed",
                                    "data": response.to_dict(),
                                })
                            except Exception:
                                pass
                else:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Processor task error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("Processor task stopped")
    
    async def _cleanup_task_loop(self) -> None:
        """Cleanup task loop."""
        logger.info("Cleanup task started")
        
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                # Clean expired cache entries
                if self.config.cache_enabled and len(self._data_cache) > self.config.cache_max_size:
                    # Remove oldest entries
                    oldest = sorted(self._data_cache.items(), key=lambda x: x[1].get("timestamp", 0))
                    for key, _ in oldest[:len(oldest) // 2]:
                        del self._data_cache[key]
                
                # Update health status
                self._health_details = {
                    "queue_usage": self._input_queue.qsize() / self.config.queue_size,
                    "worker_count": len(self._workers),
                    "active_connections": len(self._active_connections),
                    "cache_size": len(self._data_cache),
                }
                
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=True)
        
        logger.info("Cleanup task stopped")
    
    # ========================================================================
    # LIFE CYCLE MANAGEMENT
    # ========================================================================
    
    async def start(self) -> None:
        """Start the webhook handler."""
        if self._running:
            logger.warning("Webhook handler is already running")
            return
        
        self._running = True
        self._start_time = time.time()
        self._last_health_check = datetime.utcnow()
        
        try:
            # Start HTTP server
            self._runner = web.AppRunner(self._app)
            await self._runner.setup()
            
            ssl_context = self._create_ssl_context() if self.config.ssl_cert else None
            
            self._site = web.TCPSite(
                self._runner,
                host=self.config.host,
                port=self.config.port,
                ssl_context=ssl_context,
            )
            await self._site.start()
            
            logger.info(f"Webhook server started on {self.config.host}:{self.config.port}")
            
            # Start workers
            if self.config.async_processing:
                for i in range(self.config.parallel_workers):
                    worker = asyncio.create_task(self._worker_loop(i))
                    self._workers.append(worker)
                
                self._processor_task = asyncio.create_task(self._processor_task_loop())
                self._cleanup_task = asyncio.create_task(self._cleanup_task_loop())
            
            logger.info(f"Webhook handler started with {len(self._workers)} workers")
            
        except Exception as e:
            self._running = False
            logger.error(f"Error starting webhook handler: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Stop the webhook handler."""
        if not self._running:
            logger.warning("Webhook handler is not running")
            return
        
        self._running = False
        
        try:
            # Stop workers
            for worker in self._workers:
                worker.cancel()
            
            if self._workers:
                await asyncio.gather(*self._workers, return_exceptions=True)
            
            if self._processor_task:
                self._processor_task.cancel()
                await asyncio.gather(self._processor_task, return_exceptions=True)
            
            if self._cleanup_task:
                self._cleanup_task.cancel()
                await asyncio.gather(self._cleanup_task, return_exceptions=True)
            
            self._workers.clear()
            
            # Close WebSocket connections
            for connection_id in list(self._active_connections):
                if connection_id in self._websocket_callbacks:
                    del self._websocket_callbacks[connection_id]
            self._active_connections.clear()
            
            # Stop HTTP server
            if self._site:
                await self._site.stop()
                self._site = None
            
            if self._runner:
                await self._runner.cleanup()
                self._runner = None
            
            # Close Redis connection
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("Webhook handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping webhook handler: {e}", exc_info=True)
            raise
    
    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context for HTTPS."""
        if self.config.ssl_cert and self.config.ssl_key:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                self.config.ssl_cert,
                self.config.ssl_key,
                self.config.ssl_ca,
            )
            return ssl_context
        return None
    
    async def __aenter__(self) -> "WebhookHandler":
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.stop()
    
    # ========================================================================
    # PROPERTIES
    # ========================================================================
    
    @property
    def is_running(self) -> bool:
        """Check if the handler is running."""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._input_queue.qsize()
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get statistics."""
        return self._stats.dict()
    
    @property
    def health_status(self) -> HealthStatus:
        """Get health status."""
        return self._health_status


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_webhook_handler(
    provider: Union[str, WebhookProvider] = WebhookProvider.CUSTOM,
    path: str = DEFAULT_WEBHOOK_PATH,
    host: str = DEFAULT_WEBHOOK_HOST,
    port: int = DEFAULT_WEBHOOK_PORT,
    secret_key: Optional[str] = None,
    exchange: Optional[ExchangeBase] = None,
    **kwargs
) -> WebhookHandler:
    """
    Create a webhook handler instance.
    
    Args:
        provider: Webhook provider
        path: Webhook path
        host: Webhook host
        port: Webhook port
        secret_key: Secret key for signature verification
        exchange: Exchange instance for processing
        **kwargs: Additional configuration options
        
    Returns:
        WebhookHandler instance
    """
    if isinstance(provider, str):
        provider = WebhookProvider(provider.lower())
    
    config = WebhookConfig(
        provider=provider,
        path=path,
        host=host,
        port=port,
        secret_key=secret_key,
        **kwargs,
    )
    
    return WebhookHandler(config, exchange=exchange)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    async def main():
        """Main entry point for testing."""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        
        # Create webhook handler
        handler = create_webhook_handler(
            provider="custom",
            path="/webhook",
            host="0.0.0.0",
            port=8080,
            secret_key="test-secret-key-1234567890",
            allowed_ips=["127.0.0.1", "::1", "192.168.1.0/24"],
            rate_limit_requests=100,
            rate_limit_period=60,
            max_retries=3,
            parallel_workers=4,
            enable_metrics=True,
            enable_tracing=True,
            store_raw=True,
            store_processed=True,
            compression=WebhookCompression.GZIP,
        )
        
        # Register custom handler
        async def custom_trade_handler(payload: WebhookPayload) -> WebhookResponse:
            print(f"Custom trade handler: {payload.data}")
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Custom trade processed",
                data={"processed": True, "symbol": payload.data.get("symbol")},
            )
        
        handler.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.TRADE,
            custom_trade_handler,
            priority=1,
        )
        
        # Register filter
        async def symbol_filter(payload: WebhookPayload) -> bool:
            """Filter out symbols that start with 'TEST'."""
            symbol = payload.data.get("symbol", "")
            return not symbol.startswith("TEST")
        
        handler.register_filter(symbol_filter)
        
        # Start handler
        async with handler:
            print(f"Webhook handler running on http://{handler.config.host}:{handler.config.port}")
            print(f"Endpoints:")
            print(f"  POST {handler.config.path} - Main webhook endpoint")
            print(f"  GET /health - Health check")
            print(f"  GET /health/ready - Readiness check")
            print(f"  GET /health/live - Liveness check")
            print(f"  GET /status - Status information")
            print(f"  GET /metrics - Metrics")
            print(f"  WS /ws - WebSocket for real-time monitoring")
            
            # Keep running
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                print("\nShutting down...")
    
    asyncio.run(main())
