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
from asyncio import Queue
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple, Union, TypeVar, Generic, cast
)
from urllib.parse import parse_qs, urlparse

import aiohttp
import redis.asyncio as redis
from aiohttp import ClientSession, ClientTimeout, web
from pydantic import BaseModel, Field, ValidationError, validator, root_validator
from pydantic.types import PositiveInt, NonNegativeFloat, constr

from ..base import ExchangeBase
from ..converter import DataConverter
from ..exceptions import WebhookError, ValidationError as ExchangeValidationError
from ...core.config import get_config
from ...core.logging import get_logger
from ...core.metrics import MetricsCollector
from ...core.retry import retry_with_backoff
from ...core.circuit_breaker import CircuitBreaker
from ...core.rate_limiter import RateLimiter
from ...core.cache import CacheManager

logger = get_logger(__name__)

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

DEFAULT_WEBHOOK_PORT = 8080
DEFAULT_WEBHOOK_PATH = "/webhook"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BATCH_SIZE = 100
DEFAULT_QUEUE_SIZE = 10000
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60
DEFAULT_RATE_LIMIT_REQUESTS = 100
DEFAULT_RATE_LIMIT_PERIOD = 60

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


class WebhookStatus(str, Enum):
    """Status of webhook processing."""
    RECEIVED = "received"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DISCARDED = "discarded"


class SignatureAlgorithm(str, Enum):
    """Supported signature algorithms."""
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA512 = "hmac_sha512"
    RSA_SHA256 = "rsa_sha256"
    NONE = "none"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WebhookConfig(BaseModel):
    """Configuration for webhook handler."""
    
    provider: WebhookProvider = WebhookProvider.CUSTOM
    path: str = DEFAULT_WEBHOOK_PATH
    port: PositiveInt = DEFAULT_WEBHOOK_PORT
    host: str = "0.0.0.0"
    ssl_cert: Optional[str] = None
    ssl_key: Optional[str] = None
    
    # Security
    secret_key: Optional[str] = None
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.HMAC_SHA256
    verify_signature: bool = True
    allowed_ips: List[str] = Field(default_factory=list)
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])
    
    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: PositiveInt = DEFAULT_RATE_LIMIT_REQUESTS
    rate_limit_period: PositiveInt = DEFAULT_RATE_LIMIT_PERIOD
    
    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: PositiveInt = DEFAULT_CIRCUIT_BREAKER_THRESHOLD
    circuit_breaker_timeout: PositiveInt = DEFAULT_CIRCUIT_BREAKER_TIMEOUT
    
    # Processing
    timeout_seconds: PositiveInt = DEFAULT_TIMEOUT_SECONDS
    max_retries: PositiveInt = DEFAULT_MAX_RETRIES
    retry_delay: NonNegativeFloat = DEFAULT_RETRY_DELAY
    batch_size: PositiveInt = DEFAULT_BATCH_SIZE
    queue_size: PositiveInt = DEFAULT_QUEUE_SIZE
    async_processing: bool = True
    parallel_workers: PositiveInt = 4
    
    # Storage
    store_raw: bool = True
    store_processed: bool = True
    retention_days: PositiveInt = 30
    
    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True
    
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


class WebhookPayload(BaseModel):
    """Base model for webhook payload."""
    
    event_type: WebhookEventType
    provider: WebhookProvider
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    data: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Optional[str] = None
    signature: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    ip: Optional[str] = None
    
    @validator("timestamp", pre=True)
    def parse_timestamp(cls, v: Any) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            return datetime.utcfromtimestamp(v / 1000 if v > 1e12 else v)
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f%z",
            ]:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Unsupported timestamp format: {v}")
        raise ValueError(f"Unsupported timestamp type: {type(v)}")
    
    @root_validator
    def validate_signature(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate signature if required."""
        # Signature validation is done at processing time
        return values


class WebhookResponse(BaseModel):
    """Response model for webhook handler."""
    
    status: WebhookStatus
    message: str
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[float] = None
    data: Optional[Dict[str, Any]] = None


class StockTradeData(BaseModel):
    """Stock trade data model."""
    
    symbol: str
    price: float
    size: float
    timestamp: datetime
    exchange: Optional[str] = None
    trade_id: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    tape: Optional[str] = None
    
    @validator("price", "size")
    def validate_positive(cls, v: float) -> float:
        """Validate price and size are positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class StockQuoteData(BaseModel):
    """Stock quote data model."""
    
    symbol: str
    bid_price: float
    bid_size: float
    ask_price: float
    ask_size: float
    timestamp: datetime
    exchange: Optional[str] = None
    bid_exchange: Optional[str] = None
    ask_exchange: Optional[str] = None
    
    @validator("bid_price", "ask_price", "bid_size", "ask_size")
    def validate_positive(cls, v: float) -> float:
        """Validate values are positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v


class StockAggregateData(BaseModel):
    """Stock aggregate data model."""
    
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    exchange: Optional[str] = None
    vwap: Optional[float] = None
    number_of_trades: Optional[int] = None
    
    @validator("open", "high", "low", "close", "volume")
    def validate_non_negative(cls, v: float) -> float:
        """Validate values are non-negative."""
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


# ============================================================================
# WEBHOOK HANDLER CLASS
# ============================================================================

class WebhookHandler:
    """
    Advanced webhook handler for stock market data.
    
    Features:
    - Multi-provider webhook support
    - Signature verification (HMAC, RSA)
    - IP whitelisting / origin validation
    - Rate limiting (per IP, per provider)
    - Circuit breaker pattern
    - Async processing with queue
    - Retry mechanisms
    - Data validation and transformation
    - Metrics and monitoring
    - Storage (raw and processed data)
    - Event filtering and routing
    - Plugin system for custom handlers
    - Health checks and status endpoints
    """
    
    def __init__(
        self,
        config: Optional[WebhookConfig] = None,
        exchange: Optional[ExchangeBase] = None,
        redis_client: Optional[redis.Redis] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """
        Initialize webhook handler.
        
        Args:
            config: Webhook configuration
            exchange: Exchange instance for processing
            redis_client: Redis client for distributed state
            metrics_collector: Metrics collector for monitoring
            cache_manager: Cache manager for performance
        """
        self.config = config or WebhookConfig()
        self.exchange = exchange
        self.redis_client = redis_client
        self.metrics = metrics_collector or MetricsCollector()
        self.cache = cache_manager or CacheManager()
        
        # State management
        self._running = False
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        
        # Queues
        self._input_queue: Queue = Queue(maxsize=self.config.queue_size)
        self._output_queue: Queue = Queue(maxsize=self.config.queue_size)
        
        # Workers
        self._workers: List[asyncio.Task] = []
        self._processor_task: Optional[asyncio.Task] = None
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            requests=self.config.rate_limit_requests,
            period=self.config.rate_limit_period,
            redis_client=redis_client,
        )
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_threshold,
            timeout_seconds=self.config.circuit_breaker_timeout,
            redis_client=redis_client,
            name="webhook_circuit_breaker",
        )
        
        # Handlers registry
        self._handlers: Dict[WebhookProvider, Dict[WebhookEventType, List[Callable]]] = {}
        self._middlewares: List[Callable] = []
        
        # Cache for processed data
        self._data_cache: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self._stats = {
            "total_received": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_discarded": 0,
            "total_retried": 0,
            "processing_times": [],
        }
        
        # Health status
        self._last_health_check = datetime.utcnow()
        self._health_status = "healthy"
        
        self._setup_handlers()
        self._setup_routes()
        self._setup_signature_verifiers()
        
        logger.info(
            f"WebhookHandler initialized: provider={self.config.provider.value}, "
            f"path={self.config.path}, port={self.config.port}"
        )
    
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
    
    def _setup_routes(self) -> None:
        """Setup web routes."""
        self._app = web.Application(
            middlewares=[
                self._log_middleware,
                self._error_middleware,
                self._rate_limit_middleware,
            ]
        )
        
        # Primary webhook endpoint
        self._app.router.add_post(
            self.config.path,
            self._handle_webhook_post,
        )
        
        # Alternative GET method for verification
        self._app.router.add_get(
            self.config.path,
            self._handle_webhook_get,
        )
        
        # Health check endpoint
        self._app.router.add_get(
            "/health",
            self._handle_health_check,
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
        
        # Admin endpoints (if enabled)
        if self.config.enable_metrics:
            self._app.router.add_post(
                "/admin/clear_cache",
                self._handle_clear_cache,
            )
            self._app.router.add_post(
                "/admin/reset_stats",
                self._handle_reset_stats,
            )
        
        logger.debug(f"Webhook routes configured: {len(self._app.router.routes())} routes")
    
    def _setup_signature_verifiers(self) -> None:
        """Setup signature verifiers."""
        self._signature_verifiers = {
            SignatureAlgorithm.HMAC_SHA256: self._verify_hmac_sha256,
            SignatureAlgorithm.HMAC_SHA512: self._verify_hmac_sha512,
            SignatureAlgorithm.RSA_SHA256: self._verify_rsa_sha256,
            SignatureAlgorithm.NONE: self._verify_none,
        }
    
    def register_handler(
        self,
        provider: WebhookProvider,
        event_type: WebhookEventType,
        handler: Callable,
    ) -> None:
        """
        Register a custom handler for a specific provider and event type.
        
        Args:
            provider: Webhook provider
            event_type: Event type
            handler: Handler function
        """
        if provider not in self._handlers:
            self._handlers[provider] = {}
        if event_type not in self._handlers[provider]:
            self._handlers[provider][event_type] = []
        self._handlers[provider][event_type].append(handler)
        logger.debug(f"Registered handler: provider={provider.value}, event={event_type.value}")
    
    def register_middleware(self, middleware: Callable) -> None:
        """
        Register a middleware function.
        
        Args:
            middleware: Middleware function
        """
        self._middlewares.append(middleware)
        logger.debug(f"Registered middleware: {middleware.__name__}")
    
    # ========================================================================
    # MAIN WEBHOOK HANDLERS
    # ========================================================================
    
    async def _handle_webhook_post(self, request: web.Request) -> web.Response:
        """
        Handle POST webhook requests.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        start_time = time.time()
        
        try:
            # Extract request information
            ip = request.remote or request.headers.get("X-Forwarded-For", "unknown")
            headers = dict(request.headers)
            
            # Validate IP
            if not self._is_ip_allowed(ip):
                logger.warning(f"Blocked request from unauthorized IP: {ip}")
                self.metrics.increment("webhook.blocked_ip")
                return web.json_response(
                    {"error": "IP not allowed"},
                    status=403,
                )
            
            # Validate origin
            if not self._is_origin_allowed(headers.get("Origin", "")):
                logger.warning(f"Blocked request from unauthorized origin: {headers.get('Origin', '')}")
                self.metrics.increment("webhook.blocked_origin")
                return web.json_response(
                    {"error": "Origin not allowed"},
                    status=403,
                )
            
            # Get raw data
            raw_data = await request.text()
            
            # Parse JSON
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON payload: {e}")
                self.metrics.increment("webhook.invalid_json")
                return web.json_response(
                    {"error": "Invalid JSON payload"},
                    status=400,
                )
            
            # Extract provider from headers or data
            provider = self._detect_provider(headers, data)
            
            # Determine event type
            event_type = self._detect_event_type(data, provider)
            
            # Create payload
            payload = WebhookPayload(
                event_type=event_type,
                provider=provider,
                timestamp=datetime.utcnow(),
                source=ip,
                data=data,
                raw_data=raw_data,
                signature=headers.get("X-Signature"),
                headers=headers,
                ip=ip,
            )
            
            # Validate signature
            if self.config.verify_signature and payload.signature:
                if not await self._verify_signature(payload):
                    logger.warning(f"Invalid signature from IP: {ip}")
                    self.metrics.increment("webhook.invalid_signature")
                    return web.json_response(
                        {"error": "Invalid signature"},
                        status=401,
                    )
            
            # Store raw payload
            if self.config.store_raw:
                await self._store_raw_payload(payload)
            
            # Queue for processing
            if self.config.async_processing:
                try:
                    await self._input_queue.put(payload)
                    status = WebhookStatus.PROCESSING
                    message = "Payload queued for processing"
                except asyncio.QueueFull:
                    logger.warning(f"Queue full, discarding payload from {ip}")
                    self.metrics.increment("webhook.queue_full")
                    status = WebhookStatus.DISCARDED
                    message = "Queue full, payload discarded"
            else:
                # Process synchronously
                result = await self._process_payload(payload)
                status = result.status
                message = result.message
            
            # Update statistics
            self._stats["total_received"] += 1
            self.metrics.increment("webhook.received")
            
            # Generate response
            processing_time = (time.time() - start_time) * 1000
            response = WebhookResponse(
                status=status,
                message=message,
                id=payload.data.get("id", str(int(time.time()))),
                processing_time_ms=processing_time,
            )
            
            return web.json_response(
                response.dict(exclude_none=True),
                status=200 if status != WebhookStatus.FAILED else 500,
            )
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}", exc_info=True)
            self.metrics.increment("webhook.error")
            return web.json_response(
                {"error": "Internal server error"},
                status=500,
            )
    
    async def _handle_webhook_get(self, request: web.Request) -> web.Response:
        """
        Handle GET webhook requests (for webhook verification).
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        # Common verification response
        return web.json_response(
            {
                "status": "ok",
                "message": "Webhook endpoint is active",
                "version": "3.0.0",
                "provider": self.config.provider.value,
            },
            status=200,
        )
    
    # ========================================================================
    # HEALTH & STATUS ENDPOINTS
    # ========================================================================
    
    async def _handle_health_check(self, request: web.Request) -> web.Response:
        """
        Handle health check requests.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        health_status = {
            "status": self._health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": (datetime.utcnow() - self._last_health_check).total_seconds(),
            "queue_size": self._input_queue.qsize(),
            "workers": len(self._workers),
            "stats": {
                "total_received": self._stats["total_received"],
                "total_processed": self._stats["total_processed"],
                "total_failed": self._stats["total_failed"],
                "queue_depth": self._input_queue.qsize(),
            },
        }
        
        status_code = 200 if self._health_status == "healthy" else 503
        return web.json_response(health_status, status=status_code)
    
    async def _handle_status(self, request: web.Request) -> web.Response:
        """
        Handle status requests.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        status_data = {
            "status": "running" if self._running else "stopped",
            "provider": self.config.provider.value,
            "path": self.config.path,
            "port": self.config.port,
            "queue_size": self._input_queue.qsize(),
            "queue_max": self.config.queue_size,
            "workers": len(self._workers),
            "stats": self._stats,
            "circuit_breaker": {
                "enabled": self.config.circuit_breaker_enabled,
                "is_open": self._circuit_breaker.is_open(),
            },
            "rate_limiter": {
                "enabled": self.config.rate_limit_enabled,
                "requests": self.config.rate_limit_requests,
                "period": self.config.rate_limit_period,
            },
            "last_health_check": self._last_health_check.isoformat(),
        }
        
        return web.json_response(status_data, status=200)
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """
        Handle metrics requests.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        # Get metrics from collector
        metrics_data = await self.metrics.get_metrics(
            prefix="webhook",
            include=[
                "received_total",
                "processed_total",
                "failed_total",
                "discarded_total",
                "retried_total",
                "processing_time_seconds",
                "queue_depth",
                "worker_active",
            ],
        )
        
        return web.json_response(metrics_data, status=200)
    
    async def _handle_clear_cache(self, request: web.Request) -> web.Response:
        """
        Clear the data cache.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        self._data_cache.clear()
        logger.info("Cache cleared")
        return web.json_response({"status": "ok", "message": "Cache cleared"}, status=200)
    
    async def _handle_reset_stats(self, request: web.Request) -> web.Response:
        """
        Reset statistics.
        
        Args:
            request: HTTP request
            
        Returns:
            Web response
        """
        self._stats = {
            "total_received": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_discarded": 0,
            "total_retried": 0,
            "processing_times": [],
        }
        logger.info("Stats reset")
        return web.json_response({"status": "ok", "message": "Stats reset"}, status=200)
    
    # ========================================================================
    # EVENT HANDLERS
    # ========================================================================
    
    async def _handle_trade(self, payload: WebhookPayload) -> WebhookResponse:
        """
        Handle trade events.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Webhook response
        """
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
            
            self._stats["total_processed"] += 1
            self.metrics.increment("webhook.trade.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Trade processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing trade: {e}", exc_info=True)
            self._stats["total_failed"] += 1
            self.metrics.increment("webhook.trade.error")
            raise
    
    async def _handle_quote(self, payload: WebhookPayload) -> WebhookResponse:
        """
        Handle quote events.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Webhook response
        """
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
            
            self._stats["total_processed"] += 1
            self.metrics.increment("webhook.quote.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Quote processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing quote: {e}", exc_info=True)
            self._stats["total_failed"] += 1
            self.metrics.increment("webhook.quote.error")
            raise
    
    async def _handle_aggregate(self, payload: WebhookPayload) -> WebhookResponse:
        """
        Handle aggregate events.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Webhook response
        """
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
            
            self._stats["total_processed"] += 1
            self.metrics.increment("webhook.aggregate.processed")
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Aggregate processed successfully",
                data=result,
            )
            
        except Exception as e:
            logger.error(f"Error processing aggregate: {e}", exc_info=True)
            self._stats["total_failed"] += 1
            self.metrics.increment("webhook.aggregate.error")
            raise
    
    async def _handle_heartbeat(self, payload: WebhookPayload) -> WebhookResponse:
        """
        Handle heartbeat events.
        
        Args:
            payload: Webhook payload
            
        Returns:
            Webhook response
        """
        self._last_health_check = datetime.utcnow()
        self._health_status = "healthy"
        
        return WebhookResponse(
            status=WebhookStatus.COMPLETED,
            message="Heartbeat received",
            data={"timestamp": datetime.utcnow().isoformat()},
        )
    
    # ========================================================================
    # DATA PARSING
    # ========================================================================
    
    def _parse_trade_data(self, data: Dict[str, Any]) -> StockTradeData:
        """Parse trade data from various formats."""
        # Convert provider-specific formats
        if self.config.provider == WebhookProvider.ALPACA:
            # Alpaca format
            return StockTradeData(
                symbol=data.get("S", data.get("symbol", "")),
                price=float(data.get("p", data.get("price", 0))),
                size=float(data.get("s", data.get("size", 0))),
                timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
                exchange=data.get("x", data.get("exchange")),
                trade_id=data.get("i", data.get("trade_id")),
                conditions=data.get("c", data.get("conditions", [])),
                tape=data.get("z", data.get("tape")),
            )
        elif self.config.provider == WebhookProvider.POLYGON:
            # Polygon format
            return StockTradeData(
                symbol=data.get("sym", data.get("symbol", "")),
                price=float(data.get("p", data.get("price", 0))),
                size=float(data.get("s", data.get("size", 0))),
                timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
                exchange=data.get("x", data.get("exchange")),
                trade_id=str(data.get("id", data.get("trade_id", ""))),
                conditions=data.get("c", data.get("conditions", [])),
            )
        else:
            # Generic format
            return StockTradeData(**data)
    
    def _parse_quote_data(self, data: Dict[str, Any]) -> StockQuoteData:
        """Parse quote data from various formats."""
        if self.config.provider == WebhookProvider.ALPACA:
            return StockQuoteData(
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
        else:
            return StockQuoteData(**data)
    
    def _parse_aggregate_data(self, data: Dict[str, Any]) -> StockAggregateData:
        """Parse aggregate data from various formats."""
        if self.config.provider == WebhookProvider.POLYGON:
            return StockAggregateData(
                symbol=data.get("sym", data.get("symbol", "")),
                open=float(data.get("o", data.get("open", 0))),
                high=float(data.get("h", data.get("high", 0))),
                low=float(data.get("l", data.get("low", 0))),
                close=float(data.get("c", data.get("close", 0))),
                volume=float(data.get("v", data.get("volume", 0))),
                timestamp=self._parse_timestamp(data.get("t", data.get("timestamp"))),
                vwap=float(data.get("vw", data.get("vwap", 0))),
                number_of_trades=data.get("n", data.get("number_of_trades")),
            )
        else:
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
            # Try common formats
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
            # Try parsing as ISO format
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        # Default to current time
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
            for middleware in self._middlewares:
                payload = await middleware(payload)
                if payload is None:
                    return WebhookResponse(
                        status=WebhookStatus.DISCARDED,
                        message="Payload discarded by middleware",
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
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler(payload)
                    else:
                        result = handler(payload)
                    responses.append(result)
                except Exception as e:
                    logger.error(f"Handler {handler.__name__} failed: {e}", exc_info=True)
                    self.metrics.increment("webhook.handler_error")
                    responses.append({"error": str(e)})
            
            # Determine overall status
            all_success = all(isinstance(r, WebhookResponse) and r.status == WebhookStatus.COMPLETED 
                            if hasattr(r, "status") else False for r in responses)
            
            processing_time = (time.time() - start_time) * 1000
            self._stats["processing_times"].append(processing_time)
            
            return WebhookResponse(
                status=WebhookStatus.COMPLETED if all_success else WebhookStatus.FAILED,
                message="Payload processed" if all_success else "Some handlers failed",
                data={"responses": [r.dict() if hasattr(r, "dict") else r for r in responses]},
                processing_time_ms=processing_time,
            )
            
        except Exception as e:
            logger.error(f"Error processing payload: {e}", exc_info=True)
            self._stats["total_failed"] += 1
            self.metrics.increment("webhook.processing_error")
            
            # Check circuit breaker
            if self.config.circuit_breaker_enabled:
                self._circuit_breaker.record_failure()
                if self._circuit_breaker.is_open():
                    logger.warning("Circuit breaker is open, rejecting requests")
                    raise WebhookError("Circuit breaker is open")
            
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
        
        secret = self.config.secret_key.encode("utf-8")
        expected = hmac.new(secret, payload.raw_data.encode("utf-8"), hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(payload.signature.lower(), expected.lower())
    
    async def _verify_hmac_sha512(self, payload: WebhookPayload) -> bool:
        """Verify HMAC-SHA512 signature."""
        if not payload.signature or not payload.raw_data:
            return False
        
        secret = self.config.secret_key.encode("utf-8")
        expected = hmac.new(secret, payload.raw_data.encode("utf-8"), hashlib.sha512).hexdigest()
        
        return hmac.compare_digest(payload.signature.lower(), expected.lower())
    
    async def _verify_rsa_sha256(self, payload: WebhookPayload) -> bool:
        """Verify RSA-SHA256 signature."""
        # RSA verification would require public key
        # This is a placeholder for future implementation
        logger.warning("RSA signature verification not implemented")
        return True
    
    async def _verify_none(self, payload: WebhookPayload) -> bool:
        """No signature verification."""
        return True
    
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
        
        if "alpaca" in user_agent:
            return WebhookProvider.ALPACA
        elif "polygon" in user_agent:
            return WebhookProvider.POLYGON
        elif "finnhub" in user_agent:
            return WebhookProvider.FINNHUB
        elif "tradier" in user_agent:
            return WebhookProvider.TRADIER
        elif "binance" in user_agent:
            return WebhookProvider.BINANCE
        elif "coinbase" in user_agent:
            return WebhookProvider.COINBASE
        
        # Check data
        if "alpaca" in str(data).lower():
            return WebhookProvider.ALPACA
        elif "polygon" in str(data).lower():
            return WebhookProvider.POLYGON
        
        return self.config.provider
    
    def _detect_event_type(self, data: Dict[str, Any], provider: WebhookProvider) -> WebhookEventType:
        """Detect event type from data."""
        # Check for common event fields
        if "event_type" in data:
            try:
                return WebhookEventType(data["event_type"])
            except ValueError:
                pass
        
        if "type" in data:
            try:
                return WebhookEventType(data["type"])
            except ValueError:
                pass
        
        if "event" in data:
            try:
                return WebhookEventType(data["event"])
            except ValueError:
                pass
        
        # Provider-specific detection
        if provider == WebhookProvider.ALPACA:
            if "p" in data and "s" in data:
                return WebhookEventType.TRADE
            if "bp" in data and "ap" in data:
                return WebhookEventType.QUOTE
        
        if provider == WebhookProvider.POLYGON:
            if "p" in data and "s" in data:
                return WebhookEventType.TRADE
            if "bp" in data and "ap" in data:
                return WebhookEventType.QUOTE
            if "o" in data and "c" in data:
                return WebhookEventType.AGGREGATE
        
        # Check data structure
        if "price" in data and "size" in data:
            return WebhookEventType.TRADE
        elif "bid_price" in data and "ask_price" in data:
            return WebhookEventType.QUOTE
        elif "open" in data and "close" in data:
            return WebhookEventType.AGGREGATE
        
        return WebhookEventType.SYSTEM
    
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
                self._data_cache[key] = payload.raw_data
        except Exception as e:
            logger.warning(f"Error storing raw payload: {e}")
    
    async def _store_processed_data(self, payload: WebhookPayload, data: Any) -> None:
        """Store processed data."""
        try:
            key = f"webhook:processed:{payload.provider.value}:{datetime.utcnow().strftime('%Y%m%d%H')}"
            if self.redis_client:
                await self.redis_client.lpush(key, json.dumps(data))
                await self.redis_client.expire(key, self.config.retention_days * 86400)
        except Exception as e:
            logger.warning(f"Error storing processed data: {e}")
    
    # ========================================================================
    # MIDDLEWARES
    # ========================================================================
    
    @web.middleware
    async def _log_middleware(self, request: web.Request, handler: Callable) -> web.Response:
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
    async def _error_middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Error handling middleware."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unhandled error in request: {e}", exc_info=True)
            return web.json_response(
                {"error": "Internal server error", "message": str(e)},
                status=500,
            )
    
    @web.middleware
    async def _rate_limit_middleware(self, request: web.Request, handler: Callable) -> web.Response:
        """Rate limiting middleware."""
        if not self.config.rate_limit_enabled:
            return await handler(request)
        
        client_key = f"rate_limit:{request.remote or 'unknown'}:webhook"
        allowed = await self._rate_limiter.is_allowed(client_key)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {request.remote}")
            return web.json_response(
                {"error": "Rate limit exceeded"},
                status=429,
            )
        
        return await handler(request)
    
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
                    if self.config.max_retries > 0:
                        await self._retry_payload(payload)
                
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
        retries = payload.data.get("_retry_count", 0) + 1
        
        if retries <= self.config.max_retries:
            payload.data["_retry_count"] = retries
            payload.data["_last_retry"] = datetime.utcnow().isoformat()
            
            logger.info(f"Retrying payload (attempt {retries}/{self.config.max_retries})")
            self._stats["total_retried"] += 1
            self.metrics.increment("webhook.retry")
            
            # Exponential backoff
            delay = self.config.retry_delay * (2 ** (retries - 1))
            await asyncio.sleep(delay)
            
            try:
                await self._input_queue.put(payload)
            except asyncio.QueueFull:
                logger.error("Queue full, cannot retry payload")
        else:
            logger.error(f"Max retries exceeded for payload: {payload}")
            self._stats["total_failed"] += 1
            self.metrics.increment("webhook.max_retries_exceeded")
    
    async def _processor_task_loop(self) -> None:
        """Main processor task loop."""
        logger.info("Processor task started")
        
        while self._running:
            try:
                # Process output queue
                if not self._output_queue.empty():
                    response = await self._output_queue.get()
                    
                    # Store completed responses
                    if response.status == WebhookStatus.COMPLETED:
                        await self._store_processed_data(
                            WebhookPayload(
                                event_type=WebhookEventType.SYSTEM,
                                provider=self.config.provider,
                                data={"response": response.dict()},
                            ),
                            response.dict(),
                        )
                    
                    self._output_queue.task_done()
                else:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Processor task error: {e}", exc_info=True)
                await asyncio.sleep(1)
        
        logger.info("Processor task stopped")
    
    # ========================================================================
    # LIFE CYCLE MANAGEMENT
    # ========================================================================
    
    async def start(self) -> None:
        """Start the webhook handler."""
        if self._running:
            logger.warning("Webhook handler is already running")
            return
        
        self._running = True
        self._last_health_check = datetime.utcnow()
        
        try:
            # Start HTTP server
            self._runner = web.AppRunner(self._app)
            await self._runner.setup()
            
            self._site = web.TCPSite(
                self._runner,
                host=self.config.host,
                port=self.config.port,
                ssl_context=self._create_ssl_context(),
            )
            await self._site.start()
            
            logger.info(f"Webhook server started on {self.config.host}:{self.config.port}")
            
            # Start workers
            if self.config.async_processing:
                for i in range(self.config.parallel_workers):
                    worker = asyncio.create_task(self._worker_loop(i))
                    self._workers.append(worker)
                
                self._processor_task = asyncio.create_task(self._processor_task_loop())
            
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
            
            self._workers.clear()
            
            # Stop HTTP server
            if self._site:
                await self._site.stop()
                self._site = None
            
            if self._runner:
                await self._runner.cleanup()
                self._runner = None
            
            logger.info("Webhook handler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping webhook handler: {e}", exc_info=True)
            raise
    
    def _create_ssl_context(self) -> Optional[Any]:
        """Create SSL context for HTTPS."""
        if self.config.ssl_cert and self.config.ssl_key:
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                self.config.ssl_cert,
                self.config.ssl_key,
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
        return self._stats.copy()


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_webhook_handler(
    provider: Union[str, WebhookProvider] = WebhookProvider.CUSTOM,
    path: str = DEFAULT_WEBHOOK_PATH,
    port: int = DEFAULT_WEBHOOK_PORT,
    secret_key: Optional[str] = None,
    **kwargs: Any,
) -> WebhookHandler:
    """
    Create a webhook handler instance.
    
    Args:
        provider: Webhook provider
        path: Webhook path
        port: Webhook port
        secret_key: Secret key for signature verification
        **kwargs: Additional configuration options
        
    Returns:
        WebhookHandler instance
    """
    if isinstance(provider, str):
        provider = WebhookProvider(provider.lower())
    
    config = WebhookConfig(
        provider=provider,
        path=path,
        port=port,
        secret_key=secret_key,
        **kwargs,
    )
    
    return WebhookHandler(config)


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
            port=8080,
            secret_key="test-secret-key-123",
            allowed_ips=["127.0.0.1", "::1"],
            rate_limit_requests=10,
            rate_limit_period=60,
            max_retries=3,
        )
        
        # Register custom handler
        def custom_trade_handler(payload: WebhookPayload) -> WebhookResponse:
            print(f"Custom trade handler: {payload.data}")
            return WebhookResponse(
                status=WebhookStatus.COMPLETED,
                message="Custom trade processed",
            )
        
        handler.register_handler(
            WebhookProvider.CUSTOM,
            WebhookEventType.TRADE,
            custom_trade_handler,
        )
        
        # Start handler
        async with handler:
            print(f"Webhook handler running on port {handler.config.port}")
            print(f"Endpoints:")
            print(f"  POST {handler.config.path} - Main webhook endpoint")
            print(f"  GET /health - Health check")
            print(f"  GET /status - Status information")
            print(f"  GET /metrics - Metrics")
            
            # Keep running
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                print("Shutting down...")
    
    asyncio.run(main())
