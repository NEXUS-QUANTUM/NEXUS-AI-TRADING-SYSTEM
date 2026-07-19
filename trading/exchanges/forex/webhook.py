# trading/exchanges/forex/webhook.py
# Nexus AI Trading System - Forex Webhook Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union, Coroutine

import aiohttp
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, HttpUrl, validator
from redis.asyncio import Redis
import asyncpg
import orjson
import backoff
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Local imports - Nexus framework
from shared.configs.app_config import AppConfig
from shared.helpers.logging import get_logger
from shared.helpers.crypto_helpers import encrypt_data, decrypt_data
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# CONSTANTS & ENUMS
# =============================================================================

class WebhookEventType(str, Enum):
    """Types of webhook events."""
    PRICE = "price"
    SIGNAL = "signal"
    ORDER = "order"
    POSITION = "position"
    ACCOUNT = "account"
    RISK = "risk"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"
    ALERT = "alert"
    REPORT = "report"
    BACKTEST = "backtest"
    TRAINING = "training"
    INFERENCE = "inference"
    MODEL = "model"
    CONFIG = "config"
    ERROR = "error"
    STATUS = "status"
    PERFORMANCE = "performance"
    LIQUIDITY = "liquidity"
    SPREAD = "spread"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    SENTIMENT = "sentiment"
    NEWS = "news"
    ECONOMIC = "economic"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    CUSTOM = "custom"


class WebhookProvider(str, Enum):
    """Supported webhook providers."""
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOKSITE = "webhooksite"
    PUSHOVER = "pushover"
    GOTIFY = "gotify"
    APPWRITE = "appwrite"
    NTFY = "ntfy"
    MATRIX = "matrix"
    MATTERMOST = "mattermost"
    ROCKETCHAT = "rocketchat"
    CUSTOM = "custom"


class WebhookStatus(str, Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    FILTERED = "filtered"


class WebhookPriority(str, Enum):
    """Webhook priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class WebhookPayload(BaseModel):
    """Base webhook payload."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: WebhookEventType
    provider: WebhookProvider
    source: str = Field(..., description="Source identifier (e.g., system, bot, user)")
    correlation_id: Optional[str] = None
    priority: WebhookPriority = WebhookPriority.NORMAL
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    signature: Optional[str] = None
    expires_at: Optional[datetime] = None

    @validator('signature', always=True)
    def validate_signature(cls, v, values):
        """Validate or generate signature."""
        if v is not None:
            return v
        # Generate signature from data
        data_str = json.dumps(values.get('data', {}), sort_keys=True)
        secret = AppConfig.WEBHOOK_SECRET
        return hmac.new(
            secret.encode('utf-8'),
            data_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookConfig(BaseModel):
    """Webhook configuration."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    provider: WebhookProvider
    url: HttpUrl
    webhook_secret: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    events: List[WebhookEventType] = Field(default_factory=list)
    enabled: bool = True
    priority: WebhookPriority = WebhookPriority.NORMAL
    retry_config: Dict[str, Any] = Field(default_factory=lambda: {
        "max_attempts": 3,
        "base_delay": 1.0,
        "max_delay": 60.0,
        "exponential": True
    })
    timeout: float = 30.0
    rate_limit: Optional[int] = None  # requests per second
    batch_size: Optional[int] = None
    compression: bool = True
    verify_ssl: bool = True
    auth_type: Optional[str] = None
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('webhook_secret')
    def validate_webhook_secret(cls, v):
        """Ensure webhook secret meets requirements."""
        if v is not None and len(v) < 32:
            raise ValueError("Webhook secret must be at least 32 characters")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str
    payload_id: str
    event_type: WebhookEventType
    url: HttpUrl
    status: WebhookStatus = WebhookStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[float] = None
    scheduled_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    retry_after: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookFilter(BaseModel):
    """Webhook filter conditions."""
    event_types: Optional[List[WebhookEventType]] = None
    sources: Optional[List[str]] = None
    priorities: Optional[List[WebhookPriority]] = None
    min_priority: Optional[WebhookPriority] = None
    correlation_ids: Optional[List[str]] = None
    data_conditions: Optional[Dict[str, Any]] = None

    def matches(self, payload: WebhookPayload) -> bool:
        """Check if payload matches filter conditions."""
        if self.event_types and payload.event_type not in self.event_types:
            return False
        if self.sources and payload.source not in self.sources:
            return False
        if self.priorities and payload.priority not in self.priorities:
            return False
        if self.min_priority:
            priority_order = [WebhookPriority.CRITICAL, WebhookPriority.HIGH,
                            WebhookPriority.NORMAL, WebhookPriority.LOW,
                            WebhookPriority.BACKGROUND]
            if priority_order.index(payload.priority) > priority_order.index(self.min_priority):
                return False
        if self.correlation_ids and payload.correlation_id not in self.correlation_ids:
            return False
        if self.data_conditions:
            for key, value in self.data_conditions.items():
                if not self._check_condition(payload.data, key, value):
                    return False
        return True

    @staticmethod
    def _check_condition(data: Dict, key: str, value: Any) -> bool:
        """Check a single condition against nested data."""
        keys = key.split('.')
        current = data
        for k in keys:
            if not isinstance(current, dict) or k not in current:
                return False
            current = current[k]
        return current == value


# =============================================================================
# DATABASE MODELS (SQL)
# =============================================================================

CREATE_TABLE_SQL = """
-- Webhook configurations
CREATE TABLE IF NOT EXISTS webhook_configs (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    webhook_secret TEXT,
    headers JSONB DEFAULT '{}',
    events JSONB DEFAULT '[]',
    enabled BOOLEAN DEFAULT TRUE,
    priority VARCHAR(20) DEFAULT 'normal',
    retry_config JSONB DEFAULT '{"max_attempts": 3, "base_delay": 1.0, "max_delay": 60.0, "exponential": true}',
    timeout FLOAT DEFAULT 30.0,
    rate_limit INTEGER,
    batch_size INTEGER,
    compression BOOLEAN DEFAULT TRUE,
    verify_ssl BOOLEAN DEFAULT TRUE,
    auth_type VARCHAR(50),
    auth_config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Webhook deliveries
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id VARCHAR(64) PRIMARY KEY,
    webhook_id VARCHAR(64) NOT NULL REFERENCES webhook_configs(id),
    payload_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    response_code INTEGER,
    response_body TEXT,
    error_message TEXT,
    duration_ms FLOAT,
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP,
    retry_after TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Webhook payloads
CREATE TABLE IF NOT EXISTS webhook_payloads (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    source VARCHAR(255) NOT NULL,
    correlation_id VARCHAR(64),
    priority VARCHAR(20) DEFAULT 'normal',
    data JSONB NOT NULL,
    metadata JSONB DEFAULT '{}',
    signature TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

-- Webhook subscriptions
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id VARCHAR(64) PRIMARY KEY,
    webhook_id VARCHAR(64) NOT NULL REFERENCES webhook_configs(id),
    user_id VARCHAR(64),
    filter JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_payload_id ON webhook_deliveries(payload_id);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_scheduled_at ON webhook_deliveries(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_webhook_payloads_event_type ON webhook_payloads(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_payloads_created_at ON webhook_payloads(created_at);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_webhook_id ON webhook_subscriptions(webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_subscriptions_user_id ON webhook_subscriptions(user_id);
"""


# =============================================================================
# CORE IMPLEMENTATION
# =============================================================================

class WebhookManager:
    """
    Advanced webhook manager for Forex trading signals.
    
    Features:
    - Multiple provider support (Telegram, Slack, Discord, etc.)
    - Batch processing and aggregation
    - Automatic retry with exponential backoff
    - Circuit breaker pattern
    - Rate limiting per webhook
    - Payload filtering and transformation
    - Signature verification
    - Queue persistence with Redis/PostgreSQL
    - Real-time metrics and monitoring
    - Webhook health checking
    - Load balancing across multiple webhooks
    - Dead letter queue for failed deliveries
    - Webhook event transformation pipeline
    - Webhook aggregation and deduplication
    """
    
    def __init__(
        self,
        config: AppConfig,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.redis = redis
        self.pool = pool
        self._session: Optional[aiohttp.ClientSession] = None
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._rate_limiters: Dict[str, Dict[str, any]] = {}
        self._webhook_cache: Dict[str, WebhookConfig] = {}
        self._processing_queue: asyncio.Queue = asyncio.Queue()
        self._dead_letter_queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._batch_worker: Optional[asyncio.Task] = None
        self._health_check_worker: Optional[asyncio.Task] = None
        self._cleanup_worker: Optional[asyncio.Task] = None
        self._running = False
        self._metrics: Dict[str, Dict[str, float]] = {
            "delivered": {"count": 0, "rate": 0.0},
            "failed": {"count": 0, "rate": 0.0},
            "retried": {"count": 0, "rate": 0.0},
            "filtered": {"count": 0, "rate": 0.0},
            "avg_latency": {"value": 0.0}
        }
        self._metrics_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize webhook manager."""
        if not self._session:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ttl_dns_cache=300,
                ssl=self.config.WEBHOOK_VERIFY_SSL
            )
            timeout = aiohttp.ClientTimeout(
                total=self.config.WEBHOOK_TIMEOUT,
                connect=10,
                sock_read=30
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "NexusAI/3.0",
                    "Accept": "application/json"
                }
            )
        
        # Initialize database
        if self.pool:
            await self._init_database()
        
        # Load webhooks from database
        await self._load_webhooks()
        
        # Initialize circuit breakers
        for webhook_id, webhook in self._webhook_cache.items():
            self._circuit_breakers[webhook_id] = CircuitBreaker(
                name=f"webhook_{webhook_id}",
                failure_threshold=5,
                recovery_timeout=60,
                half_open_max_calls=3
            )
            if webhook.rate_limit:
                self._rate_limiters[webhook_id] = {
                    "tokens": webhook.rate_limit,
                    "last_refill": time.time(),
                    "rate": webhook.rate_limit
                }
        
        # Start workers
        self._running = True
        num_workers = min(self.config.WEBHOOK_WORKERS, 10)
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        self._batch_worker = asyncio.create_task(self._batch_worker_loop())
        self._health_check_worker = asyncio.create_task(self._health_check_loop())
        self._cleanup_worker = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"WebhookManager initialized with {num_workers} workers")
    
    async def _init_database(self):
        """Initialize database tables."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for statement in CREATE_TABLE_SQL.split(';'):
                    if statement.strip():
                        await conn.execute(statement)
        logger.info("Database tables initialized")
    
    async def _load_webhooks(self):
        """Load webhook configurations from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM webhook_configs WHERE enabled = TRUE"
                )
                for row in rows:
                    try:
                        config = WebhookConfig(
                            id=row['id'],
                            name=row['name'],
                            provider=WebhookProvider(row['provider']),
                            url=HttpUrl(row['url']),
                            webhook_secret=row.get('webhook_secret'),
                            headers=row.get('headers', {}),
                            events=[WebhookEventType(e) for e in row.get('events', [])],
                            enabled=row.get('enabled', True),
                            priority=WebhookPriority(row.get('priority', 'normal')),
                            retry_config=row.get('retry_config', {}),
                            timeout=row.get('timeout', 30.0),
                            rate_limit=row.get('rate_limit'),
                            batch_size=row.get('batch_size'),
                            compression=row.get('compression', True),
                            verify_ssl=row.get('verify_ssl', True),
                            auth_type=row.get('auth_type'),
                            auth_config=row.get('auth_config', {}),
                            metadata=row.get('metadata', {})
                        )
                        self._webhook_cache[config.id] = config
                    except Exception as e:
                        logger.error(f"Error loading webhook {row['id']}: {e}")
            
            logger.info(f"Loaded {len(self._webhook_cache)} webhooks")
        except Exception as e:
            logger.error(f"Error loading webhooks: {e}")
    
    async def _worker_loop(self, worker_id: int):
        """Worker loop for processing webhook queue."""
        logger.info(f"Webhook worker {worker_id} started")
        
        while self._running:
            try:
                # Get payload from queue
                payload = await asyncio.wait_for(
                    self._processing_queue.get(),
                    timeout=1.0
                )
                
                # Process payload
                await self._process_payload(payload)
                
                # Mark task done
                self._processing_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(0.1)
        
        logger.info(f"Webhook worker {worker_id} stopped")
    
    async def _batch_worker_loop(self):
        """Batch processing worker."""
        logger.info("Batch worker started")
        
        batch: List[WebhookPayload] = []
        batch_size = self.config.WEBHOOK_BATCH_SIZE or 10
        batch_timeout = self.config.WEBHOOK_BATCH_TIMEOUT or 1.0
        
        while self._running:
            try:
                # Collect batch
                start_time = time.time()
                while len(batch) < batch_size:
                    try:
                        payload = await asyncio.wait_for(
                            self._processing_queue.get(),
                            timeout=max(0.1, batch_timeout - (time.time() - start_time))
                        )
                        batch.append(payload)
                        self._processing_queue.task_done()
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    # Process batch
                    await self._process_batch(batch)
                    batch = []
                
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch worker error: {e}")
                await asyncio.sleep(0.1)
        
        # Process remaining batch on shutdown
        if batch:
            await self._process_batch(batch)
        
        logger.info("Batch worker stopped")
    
    async def _health_check_loop(self):
        """Health check worker."""
        logger.info("Health check worker started")
        
        while self._running:
            try:
                for webhook_id, webhook in self._webhook_cache.items():
                    if webhook.enabled:
                        try:
                            health = await self._check_webhook_health(webhook)
                            if not health:
                                logger.warning(f"Webhook {webhook_id} health check failed")
                                if webhook_id in self._circuit_breakers:
                                    self._circuit_breakers[webhook_id].record_failure()
                        except Exception as e:
                            logger.error(f"Health check error for {webhook_id}: {e}")
                
                await asyncio.sleep(self.config.WEBHOOK_HEALTH_INTERVAL or 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check worker error: {e}")
                await asyncio.sleep(1)
        
        logger.info("Health check worker stopped")
    
    async def _cleanup_loop(self):
        """Cleanup worker for old deliveries and payloads."""
        logger.info("Cleanup worker started")
        
        while self._running:
            try:
                retention_days = self.config.WEBHOOK_RETENTION_DAYS or 7
                cutoff = datetime.utcnow() - timedelta(days=retention_days)
                
                if self.pool:
                    async with self.pool.acquire() as conn:
                        # Clean up old deliveries
                        await conn.execute(
                            "DELETE FROM webhook_deliveries WHERE scheduled_at < $1",
                            cutoff
                        )
                        # Clean up old payloads
                        await conn.execute(
                            "DELETE FROM webhook_payloads WHERE created_at < $1",
                            cutoff
                        )
                
                await asyncio.sleep(86400)  # Daily cleanup
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                await asyncio.sleep(3600)
        
        logger.info("Cleanup worker stopped")
    
    # =========================================================================
    # WEBHOOK PROCESSING
    # =========================================================================
    
    async def send(
        self,
        data: Dict[str, Any],
        event_type: WebhookEventType = WebhookEventType.CUSTOM,
        source: str = "system",
        provider: Optional[WebhookProvider] = None,
        correlation_id: Optional[str] = None,
        priority: WebhookPriority = WebhookPriority.NORMAL,
        metadata: Optional[Dict[str, Any]] = None,
        wait_for_delivery: bool = False,
        timeout: Optional[float] = None
    ) -> Union[str, WebhookDelivery]:
        """
        Send a webhook payload to all matching webhooks.
        
        Args:
            data: Payload data
            event_type: Type of event
            source: Source identifier
            provider: Specific provider to target (None = all)
            correlation_id: Correlation ID for tracking
            priority: Priority level
            metadata: Additional metadata
            wait_for_delivery: Wait for delivery confirmation
            timeout: Timeout for waiting
            
        Returns:
            Payload ID or Delivery record
        """
        # Create payload
        payload = WebhookPayload(
            event_type=event_type,
            provider=provider or WebhookProvider.CUSTOM,
            source=source,
            correlation_id=correlation_id,
            priority=priority,
            data=data,
            metadata=metadata or {},
            signature=None  # Will be auto-generated
        )
        
        # Save payload
        await self._save_payload(payload)
        
        # Find matching webhooks
        targets = []
        for webhook_id, webhook in self._webhook_cache.items():
            if not webhook.enabled:
                continue
            if provider and webhook.provider != provider:
                continue
            if webhook.events and event_type not in webhook.events:
                continue
            targets.append(webhook)
        
        if not targets:
            logger.debug(f"No webhooks match event {event_type}")
            return payload.id
        
        # Check if should batch
        if len(targets) > 1 and self.config.WEBHOOK_BATCHING:
            # Add to queue for batch processing
            await self._processing_queue.put(payload)
            return payload.id
        
        # Process sequentially
        if wait_for_delivery:
            deliveries = await self._process_payload_sync(payload, targets, timeout)
            return deliveries
        
        # Async processing
        await self._process_payload(payload)
        return payload.id
    
    async def _process_payload(self, payload: WebhookPayload):
        """Process a single payload through all matching webhooks."""
        targets = []
        for webhook_id, webhook in self._webhook_cache.items():
            if not webhook.enabled:
                continue
            if webhook.events and payload.event_type not in webhook.events:
                continue
            targets.append(webhook)
        
        if not targets:
            return
        
        await self._process_payload_sync(payload, targets)
    
    async def _process_payload_sync(
        self,
        payload: WebhookPayload,
        targets: List[WebhookConfig],
        timeout: Optional[float] = None
    ) -> List[WebhookDelivery]:
        """Process payload synchronously."""
        deliveries = []
        
        # Filter and deduplicate
        targets = await self._filter_and_deduplicate(payload, targets)
        
        # Process each target
        for webhook in targets:
            delivery = await self._deliver_payload(payload, webhook, timeout)
            deliveries.append(delivery)
            
            # Update metrics
            if delivery.status == WebhookStatus.DELIVERED:
                await self._update_metrics("delivered", 1)
                async with self._metrics_lock:
                    self._metrics["avg_latency"]["value"] = (
                        (self._metrics["avg_latency"]["value"] + delivery.duration_ms) / 2
                    )
            elif delivery.status == WebhookStatus.FAILED:
                await self._update_metrics("failed", 1)
        
        return deliveries
    
    async def _process_batch(self, batch: List[WebhookPayload]):
        """Process a batch of payloads."""
        # Group by webhook
        grouped = {}
        for payload in batch:
            for webhook_id, webhook in self._webhook_cache.items():
                if not webhook.enabled:
                    continue
                if webhook.events and payload.event_type not in webhook.events:
                    continue
                if webhook_id not in grouped:
                    grouped[webhook_id] = {"webhook": webhook, "payloads": []}
                grouped[webhook_id]["payloads"].append(payload)
        
        # Process each group
        for webhook_id, group in grouped.items():
            webhook = group["webhook"]
            payloads = group["payloads"]
            
            if webhook.batch_size and len(payloads) >= webhook.batch_size:
                # Batch delivery
                await self._deliver_batch(payloads, webhook)
            else:
                # Individual delivery
                for payload in payloads:
                    await self._deliver_payload(payload, webhook)
    
    # =========================================================================
    # DELIVERY ENGINE
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=60.0)
    async def _deliver_payload(
        self,
        payload: WebhookPayload,
        webhook: WebhookConfig,
        timeout: Optional[float] = None
    ) -> WebhookDelivery:
        """Deliver a payload to a webhook with retry logic."""
        delivery_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Check circuit breaker
        circuit_breaker = self._circuit_breakers.get(webhook.id)
        if circuit_breaker and circuit_breaker.is_open():
            raise Exception(f"Circuit breaker open for webhook {webhook.id}")
        
        # Check rate limit
        if not await self._check_rate_limit(webhook.id, webhook.rate_limit):
            delivery = WebhookDelivery(
                id=delivery_id,
                webhook_id=webhook.id,
                payload_id=payload.id,
                event_type=payload.event_type,
                url=webhook.url,
                status=WebhookStatus.FAILED,
                error_message="Rate limit exceeded",
                duration_ms=(time.time() - start_time) * 1000,
                scheduled_at=datetime.utcnow(),
                retry_after=datetime.utcnow() + timedelta(seconds=1)
            )
            await self._save_delivery(delivery)
            return delivery
        
        try:
            # Prepare request
            headers = self._prepare_headers(webhook, payload)
            data = self._prepare_data(webhook, payload)
            
            # Send request
            timeout_seconds = timeout or webhook.timeout
            async with self._session.post(
                str(webhook.url),
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
                ssl=webhook.verify_ssl
            ) as response:
                duration_ms = (time.time() - start_time) * 1000
                response_body = await response.text()
                
                delivery = WebhookDelivery(
                    id=delivery_id,
                    webhook_id=webhook.id,
                    payload_id=payload.id,
                    event_type=payload.event_type,
                    url=webhook.url,
                    status=WebhookStatus.DELIVERED if response.status < 400 else WebhookStatus.FAILED,
                    attempts=1,
                    response_code=response.status,
                    response_body=response_body if len(response_body) < 1000 else response_body[:1000] + "...",
                    duration_ms=duration_ms,
                    scheduled_at=datetime.utcnow(),
                    delivered_at=datetime.utcnow(),
                    metadata={
                        "headers": dict(response.headers),
                        "payload_size": len(json.dumps(data))
                    }
                )
                
                # Record success/failure
                if delivery.status == WebhookStatus.DELIVERED:
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    await self._update_metrics("delivered", 1)
                else:
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    await self._update_metrics("failed", 1)
                    
                    # Retry logic
                    if await self._should_retry(delivery, webhook):
                        delivery.status = WebhookStatus.RETRY
                        delivery.retry_after = datetime.utcnow() + timedelta(
                            seconds=webhook.retry_config.get("base_delay", 1.0) *
                            (2 ** delivery.attempts)
                        )
                        await self._update_metrics("retried", 1)
                
                # Save delivery
                await self._save_delivery(delivery)
                
                return delivery
                
        except asyncio.TimeoutError as e:
            await self._update_metrics("failed", 1)
            if circuit_breaker:
                circuit_breaker.record_failure()
            
            delivery = WebhookDelivery(
                id=delivery_id,
                webhook_id=webhook.id,
                payload_id=payload.id,
                event_type=payload.event_type,
                url=webhook.url,
                status=WebhookStatus.FAILED,
                attempts=1,
                error_message=f"Timeout: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
                scheduled_at=datetime.utcnow()
            )
            await self._save_delivery(delivery)
            return delivery
            
        except Exception as e:
            await self._update_metrics("failed", 1)
            if circuit_breaker:
                circuit_breaker.record_failure()
            
            delivery = WebhookDelivery(
                id=delivery_id,
                webhook_id=webhook.id,
                payload_id=payload.id,
                event_type=payload.event_type,
                url=webhook.url,
                status=WebhookStatus.FAILED,
                attempts=1,
                error_message=str(e),
                duration_ms=(time.time() - start_time) * 1000,
                scheduled_at=datetime.utcnow()
            )
            await self._save_delivery(delivery)
            return delivery
    
    async def _deliver_batch(
        self,
        payloads: List[WebhookPayload],
        webhook: WebhookConfig
    ) -> WebhookDelivery:
        """Deliver a batch of payloads."""
        # Aggregate data
        batch_data = {
            "batch_id": str(uuid.uuid4()),
            "count": len(payloads),
            "timestamp": datetime.utcnow().isoformat(),
            "payloads": [
                {
                    "id": p.id,
                    "event_type": p.event_type.value,
                    "source": p.source,
                    "data": p.data,
                    "metadata": p.metadata
                }
                for p in payloads
            ]
        }
        
        # Create a single payload for the batch
        batch_payload = WebhookPayload(
            event_type=WebhookEventType.CUSTOM,
            provider=webhook.provider,
            source="batch_processor",
            correlation_id=payloads[0].correlation_id if payloads else None,
            priority=WebhookPriority.NORMAL,
            data=batch_data,
            metadata={
                "batch": True,
                "webhook_id": webhook.id,
                "webhook_name": webhook.name
            }
        )
        
        # Deliver as a single payload
        return await self._deliver_payload(batch_payload, webhook)
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _prepare_headers(self, webhook: WebhookConfig, payload: WebhookPayload) -> Dict[str, str]:
        """Prepare request headers."""
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-ID": webhook.id,
            "X-Webhook-Name": webhook.name,
            "X-Event-Type": payload.event_type.value,
            "X-Payload-ID": payload.id,
            "X-Source": payload.source,
            "X-Priority": payload.priority.value,
            "X-Timestamp": datetime.utcnow().isoformat()
        }
        
        # Correlation ID
        if payload.correlation_id:
            headers["X-Correlation-ID"] = payload.correlation_id
        
        # Signature
        if payload.signature:
            headers["X-Webhook-Signature"] = payload.signature
        
        # Custom headers
        for key, value in webhook.headers.items():
            headers[key] = value
        
        # Auth headers
        if webhook.auth_type == "bearer" and webhook.auth_config.get("token"):
            headers["Authorization"] = f"Bearer {webhook.auth_config['token']}"
        elif webhook.auth_type == "basic" and webhook.auth_config.get("username"):
            import base64
            auth = f"{webhook.auth_config['username']}:{webhook.auth_config.get('password', '')}"
            encoded = base64.b64encode(auth.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif webhook.auth_type == "api_key" and webhook.auth_config.get("key"):
            key_header = webhook.auth_config.get("header", "X-API-Key")
            headers[key_header] = webhook.auth_config["key"]
        
        return headers
    
    def _prepare_data(self, webhook: WebhookConfig, payload: WebhookPayload) -> Dict[str, Any]:
        """Prepare request data."""
        data = payload.data.copy()
        
        # Add metadata
        data["_webhook"] = {
            "id": webhook.id,
            "name": webhook.name,
            "provider": webhook.provider.value,
            "priority": payload.priority.value,
            "event_type": payload.event_type.value,
            "correlation_id": payload.correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Transform for specific providers
        if webhook.provider == WebhookProvider.TELEGRAM:
            data = self._transform_telegram(data)
        elif webhook.provider == WebhookProvider.SLACK:
            data = self._transform_slack(data)
        elif webhook.provider == WebhookProvider.DISCORD:
            data = self._transform_discord(data)
        elif webhook.provider == WebhookProvider.NTFY:
            data = self._transform_ntfy(data)
        
        return data
    
    def _transform_telegram(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for Telegram."""
        # Telegram expects a specific format
        if "message" in data:
            return {"text": data["message"]}
        elif "text" in data:
            return {"text": data["text"]}
        else:
            # Convert to readable text
            text = json.dumps(data, indent=2)
            return {"text": f"```json\n{text}\n```"}
    
    def _transform_slack(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for Slack."""
        if "blocks" in data:
            return {"blocks": data["blocks"]}
        elif "attachments" in data:
            return {"attachments": data["attachments"]}
        else:
            # Create a simple message
            text = data.get("message", data.get("text", json.dumps(data, indent=2)))
            return {"text": text}
    
    def _transform_discord(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for Discord."""
        if "embeds" in data:
            return {"embeds": data["embeds"]}
        elif "content" in data:
            return {"content": data["content"]}
        else:
            content = data.get("message", data.get("text", json.dumps(data, indent=2)))
            return {"content": content}
    
    def _transform_ntfy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data for NTFY."""
        # NTFY expects a specific format
        result = {}
        if "message" in data:
            result["message"] = data["message"]
        elif "text" in data:
            result["message"] = data["text"]
        if "title" in data:
            result["title"] = data["title"]
        if "priority" in data:
            result["priority"] = data["priority"]
        if "tags" in data:
            result["tags"] = data["tags"]
        if "click" in data:
            result["click"] = data["click"]
        return result
    
    async def _filter_and_deduplicate(
        self,
        payload: WebhookPayload,
        targets: List[WebhookConfig]
    ) -> List[WebhookConfig]:
        """Filter and deduplicate targets."""
        # Remove duplicate webhooks (same URL, same provider)
        seen = set()
        filtered = []
        for webhook in targets:
            key = (webhook.provider.value, str(webhook.url))
            if key in seen:
                continue
            seen.add(key)
            
            # Check if webhook is healthy
            circuit_breaker = self._circuit_breakers.get(webhook.id)
            if circuit_breaker and circuit_breaker.is_open():
                logger.warning(f"Webhook {webhook.id} is in open state, skipping")
                continue
            
            filtered.append(webhook)
        
        # Sort by priority
        priority_order = {
            WebhookPriority.CRITICAL: 0,
            WebhookPriority.HIGH: 1,
            WebhookPriority.NORMAL: 2,
            WebhookPriority.LOW: 3,
            WebhookPriority.BACKGROUND: 4
        }
        filtered.sort(key=lambda w: priority_order.get(w.priority, 5))
        
        return filtered
    
    async def _check_rate_limit(self, webhook_id: str, rate_limit: Optional[int]) -> bool:
        """Check if rate limit allows a request."""
        if not rate_limit:
            return True
        
        if webhook_id not in self._rate_limiters:
            self._rate_limiters[webhook_id] = {
                "tokens": rate_limit,
                "last_refill": time.time(),
                "rate": rate_limit
            }
        
        limiter = self._rate_limiters[webhook_id]
        now = time.time()
        
        # Refill tokens
        elapsed = now - limiter["last_refill"]
        new_tokens = elapsed * limiter["rate"]
        limiter["tokens"] = min(limiter["rate"], limiter["tokens"] + new_tokens)
        limiter["last_refill"] = now
        
        # Check if tokens available
        if limiter["tokens"] >= 1:
            limiter["tokens"] -= 1
            return True
        
        return False
    
    async def _should_retry(self, delivery: WebhookDelivery, webhook: WebhookConfig) -> bool:
        """Check if delivery should be retried."""
        max_attempts = webhook.retry_config.get("max_attempts", 3)
        if delivery.attempts >= max_attempts:
            return False
        
        # Only retry certain statuses
        if delivery.response_code in [400, 401, 403, 404, 405, 410, 413, 414, 415, 416, 417, 418, 422, 423, 429, 431, 451]:
            # Client errors that won't be resolved by retry
            return False
        
        if delivery.response_code in [500, 502, 503, 504]:
            # Server errors - retry
            return True
        
        if delivery.response_code is None:
            # Network errors - retry
            return True
        
        return False
    
    async def _check_webhook_health(self, webhook: WebhookConfig) -> bool:
        """Check webhook health."""
        try:
            headers = self._prepare_headers(webhook, WebhookPayload(
                event_type=WebhookEventType.HEARTBEAT,
                provider=webhook.provider,
                source="health_check",
                data={"ping": "pong"}
            ))
            
            async with self._session.head(
                str(webhook.url),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
                ssl=webhook.verify_ssl
            ) as response:
                return response.status < 500
                
        except Exception:
            return False
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_payload(self, payload: WebhookPayload):
        """Save payload to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_payloads (
                        id, event_type, provider, source, correlation_id,
                        priority, data, metadata, signature, expires_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    payload.id,
                    payload.event_type.value,
                    payload.provider.value,
                    payload.source,
                    payload.correlation_id,
                    payload.priority.value,
                    json.dumps(payload.data),
                    json.dumps(payload.metadata),
                    payload.signature,
                    payload.expires_at
                )
        except Exception as e:
            logger.error(f"Error saving payload: {e}")
    
    async def _save_delivery(self, delivery: WebhookDelivery):
        """Save delivery record to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_deliveries (
                        id, webhook_id, payload_id, event_type, url,
                        status, attempts, response_code, response_body,
                        error_message, duration_ms, scheduled_at,
                        delivered_at, retry_after, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                              $11, $12, $13, $14, $15)
                    """,
                    delivery.id,
                    delivery.webhook_id,
                    delivery.payload_id,
                    delivery.event_type.value,
                    str(delivery.url),
                    delivery.status.value,
                    delivery.attempts,
                    delivery.response_code,
                    delivery.response_body,
                    delivery.error_message,
                    delivery.duration_ms,
                    delivery.scheduled_at,
                    delivery.delivered_at,
                    delivery.retry_after,
                    json.dumps(delivery.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving delivery: {e}")
    
    async def get_deliveries(
        self,
        webhook_id: Optional[str] = None,
        status: Optional[WebhookStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[WebhookDelivery]:
        """Get delivery records."""
        if not self.pool:
            return []
        
        try:
            query = "SELECT * FROM webhook_deliveries WHERE 1=1"
            params = []
            param_count = 1
            
            if webhook_id:
                query += f" AND webhook_id = ${param_count}"
                params.append(webhook_id)
                param_count += 1
            
            if status:
                query += f" AND status = ${param_count}"
                params.append(status.value)
                param_count += 1
            
            query += f" ORDER BY scheduled_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
            params.append(limit)
            params.append(offset)
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                return [self._row_to_delivery(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting deliveries: {e}")
            return []
    
    def _row_to_delivery(self, row) -> WebhookDelivery:
        """Convert database row to delivery model."""
        return WebhookDelivery(
            id=row['id'],
            webhook_id=row['webhook_id'],
            payload_id=row['payload_id'],
            event_type=WebhookEventType(row['event_type']),
            url=HttpUrl(row['url']),
            status=WebhookStatus(row['status']),
            attempts=row.get('attempts', 0),
            response_code=row.get('response_code'),
            response_body=row.get('response_body'),
            error_message=row.get('error_message'),
            duration_ms=row.get('duration_ms'),
            scheduled_at=row.get('scheduled_at', datetime.utcnow()),
            delivered_at=row.get('delivered_at'),
            retry_after=row.get('retry_after'),
            metadata=row.get('metadata', {})
        )
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def _update_metrics(self, metric: str, value: float):
        """Update metrics."""
        async with self._metrics_lock:
            if metric in self._metrics and isinstance(self._metrics[metric], dict):
                if "count" in self._metrics[metric]:
                    self._metrics[metric]["count"] += value
                elif "value" in self._metrics[metric]:
                    self._metrics[metric]["value"] = value
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        async with self._metrics_lock:
            return {
                **self._metrics,
                "active_workers": len(self._workers),
                "queue_size": self._processing_queue.qsize(),
                "dead_letter_size": self._dead_letter_queue.qsize(),
                "cache_size": len(self._webhook_cache),
                "circuit_breakers": {
                    key: cb.get_state() for key, cb in self._circuit_breakers.items()
                }
            }
    
    # =========================================================================
    # WEBHOOK MANAGEMENT
    # =========================================================================
    
    async def register_webhook(self, config: WebhookConfig) -> WebhookConfig:
        """Register a new webhook configuration."""
        if config.id in self._webhook_cache:
            raise ValueError(f"Webhook {config.id} already exists")
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_configs (
                        id, name, provider, url, webhook_secret,
                        headers, events, enabled, priority,
                        retry_config, timeout, rate_limit,
                        batch_size, compression, verify_ssl,
                        auth_type, auth_config, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    """,
                    config.id,
                    config.name,
                    config.provider.value,
                    str(config.url),
                    config.webhook_secret,
                    json.dumps(config.headers),
                    json.dumps([e.value for e in config.events]),
                    config.enabled,
                    config.priority.value,
                    json.dumps(config.retry_config),
                    config.timeout,
                    config.rate_limit,
                    config.batch_size,
                    config.compression,
                    config.verify_ssl,
                    config.auth_type,
                    json.dumps(config.auth_config),
                    json.dumps(config.metadata)
                )
        
        self._webhook_cache[config.id] = config
        self._circuit_breakers[config.id] = CircuitBreaker(
            name=f"webhook_{config.id}",
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=3
        )
        if config.rate_limit:
            self._rate_limiters[config.id] = {
                "tokens": config.rate_limit,
                "last_refill": time.time(),
                "rate": config.rate_limit
            }
        
        logger.info(f"Webhook {config.id} registered")
        return config
    
    async def update_webhook(self, config: WebhookConfig) -> WebhookConfig:
        """Update an existing webhook configuration."""
        if config.id not in self._webhook_cache:
            raise ValueError(f"Webhook {config.id} not found")
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE webhook_configs SET
                        name = $2, provider = $3, url = $4,
                        webhook_secret = $5, headers = $6, events = $7,
                        enabled = $8, priority = $9, retry_config = $10,
                        timeout = $11, rate_limit = $12,
                        batch_size = $13, compression = $14,
                        verify_ssl = $15, auth_type = $16,
                        auth_config = $17, metadata = $18,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $1
                    """,
                    config.id,
                    config.name,
                    config.provider.value,
                    str(config.url),
                    config.webhook_secret,
                    json.dumps(config.headers),
                    json.dumps([e.value for e in config.events]),
                    config.enabled,
                    config.priority.value,
                    json.dumps(config.retry_config),
                    config.timeout,
                    config.rate_limit,
                    config.batch_size,
                    config.compression,
                    config.verify_ssl,
                    config.auth_type,
                    json.dumps(config.auth_config),
                    json.dumps(config.metadata)
                )
        
        self._webhook_cache[config.id] = config
        logger.info(f"Webhook {config.id} updated")
        return config
    
    async def delete_webhook(self, webhook_id: str):
        """Delete a webhook configuration."""
        if webhook_id not in self._webhook_cache:
            return
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM webhook_configs WHERE id = $1",
                    webhook_id
                )
                await conn.execute(
                    "DELETE FROM webhook_subscriptions WHERE webhook_id = $1",
                    webhook_id
                )
        
        del self._webhook_cache[webhook_id]
        if webhook_id in self._circuit_breakers:
            del self._circuit_breakers[webhook_id]
        if webhook_id in self._rate_limiters:
            del self._rate_limiters[webhook_id]
        
        logger.info(f"Webhook {webhook_id} deleted")
    
    async def list_webhooks(self) -> List[WebhookConfig]:
        """List all webhook configurations."""
        return list(self._webhook_cache.values())
    
    async def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get a webhook configuration."""
        return self._webhook_cache.get(webhook_id)
    
    # =========================================================================
    # SUBSCRIPTIONS
    # =========================================================================
    
    async def create_subscription(
        self,
        webhook_id: str,
        user_id: str,
        filter_config: Optional[WebhookFilter] = None
    ) -> str:
        """Create a webhook subscription."""
        webhook = await self.get_webhook(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook {webhook_id} not found")
        
        subscription_id = str(uuid.uuid4())
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO webhook_subscriptions (
                        id, webhook_id, user_id, filter, active
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    subscription_id,
                    webhook_id,
                    user_id,
                    json.dumps(filter_config.dict() if filter_config else {}),
                    True
                )
        
        logger.info(f"Subscription {subscription_id} created for webhook {webhook_id}")
        return subscription_id
    
    async def delete_subscription(self, subscription_id: str):
        """Delete a webhook subscription."""
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM webhook_subscriptions WHERE id = $1",
                    subscription_id
                )
        
        logger.info(f"Subscription {subscription_id} deleted")
    
    # =========================================================================
    # WEBHOOK RECEIVER
    # =========================================================================
    
    class WebhookReceiver:
        """Webhook receiver for incoming webhook requests."""
        
        def __init__(self, manager: 'WebhookManager'):
            self.manager = manager
            self.app = FastAPI(title="Nexus Webhook Receiver")
            self._setup_routes()
        
        def _setup_routes(self):
            """Setup FastAPI routes."""
            
            @self.app.get("/")
            async def root():
                return {
                    "service": "Nexus Webhook Receiver",
                    "status": "active",
                    "version": "3.0.0",
                    "capabilities": [
                        "Price alerts",
                        "Trading signals",
                        "Order notifications",
                        "Position updates",
                        "Account events",
                        "Risk alerts",
                        "Heartbeat",
                        "System events",
                        "Performance reports"
                    ]
                }
            
            @self.app.get("/health")
            async def health():
                return {
                    "status": "healthy",
                    "metrics": await self.manager.get_metrics()
                }
            
            @self.app.post("/webhook/{provider}")
            async def receive_webhook(
                provider: str,
                request: Request,
                background_tasks: BackgroundTasks,
                x_signature: Optional[str] = Header(None),
                x_timestamp: Optional[str] = Header(None)
            ):
                """Receive a webhook request."""
                try:
                    # Parse body
                    body = await request.body()
                    data = orjson.loads(body)
                    
                    # Validate provider
                    try:
                        provider_enum = WebhookProvider(provider.lower())
                    except ValueError:
                        raise HTTPException(400, f"Unsupported provider: {provider}")
                    
                    # Create payload
                    payload = WebhookPayload(
                        event_type=WebhookEventType.CUSTOM,
                        provider=provider_enum,
                        source="webhook_receiver",
                        data=data,
                        metadata={
                            "headers": dict(request.headers),
                            "client_ip": request.client.host if request.client else None
                        }
                    )
                    
                    # Verify signature if provided
                    if x_signature and x_timestamp:
                        # Verify webhook signature
                        secret = self.manager.config.WEBHOOK_SECRET
                        expected = hmac.new(
                            secret.encode(),
                            f"{x_timestamp}.{body.decode()}".encode(),
                            hashlib.sha256
                        ).hexdigest()
                        if not hmac.compare_digest(x_signature, expected):
                            raise HTTPException(401, "Invalid signature")
                    
                    # Process in background
                    background_tasks.add_task(
                        self.manager.send,
                        data=payload.data,
                        event_type=WebhookEventType.CUSTOM,
                        source=f"webhook_{provider}",
                        provider=provider_enum,
                        correlation_id=payload.id,
                        metadata=payload.metadata
                    )
                    
                    return {
                        "status": "received",
                        "id": payload.id,
                        "provider": provider,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                except orjson.JSONDecodeError:
                    raise HTTPException(400, "Invalid JSON body")
                except Exception as e:
                    logger.error(f"Error receiving webhook: {e}")
                    raise HTTPException(500, f"Internal error: {str(e)}")
            
            @self.app.post("/webhook/test")
            async def test_webhook(request: Request):
                """Test webhook endpoint."""
                try:
                    body = await request.body()
                    data = orjson.loads(body)
                    
                    return {
                        "status": "success",
                        "received": data,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "message": str(e)}
                    )
        
        def run(self, host: str = "0.0.0.0", port: int = 8081):
            """Run the webhook receiver server."""
            uvicorn.run(
                self.app,
                host=host,
                port=port,
                log_level="info"
            )
    
    def create_receiver(self) -> 'WebhookReceiver':
        """Create a webhook receiver instance."""
        return self.WebhookReceiver(self)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the webhook manager."""
        self._running = False
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        if self._batch_worker:
            self._batch_worker.cancel()
        if self._health_check_worker:
            self._health_check_worker.cancel()
        if self._cleanup_worker:
            self._cleanup_worker.cancel()
        
        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        if self._batch_worker:
            await asyncio.gather(self._batch_worker, return_exceptions=True)
        if self._health_check_worker:
            await asyncio.gather(self._health_check_worker, return_exceptions=True)
        if self._cleanup_worker:
            await asyncio.gather(self._cleanup_worker, return_exceptions=True)
        
        # Close session
        if self._session:
            await self._session.close()
            self._session = None
        
        logger.info("WebhookManager shutdown complete")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def create_webhook_manager(
    config: AppConfig,
    redis: Optional[Redis] = None,
    pool: Optional[asyncpg.Pool] = None
) -> WebhookManager:
    """Create and initialize a webhook manager."""
    manager = WebhookManager(config, redis, pool)
    await manager.initialize()
    return manager


# =============================================================================
# WEBHOOK PRESETS
# =============================================================================

def get_forex_price_alert_webhook(
    webhook_url: str,
    secret: Optional[str] = None
) -> WebhookConfig:
    """Create a webhook for forex price alerts."""
    return WebhookConfig(
        name="Forex Price Alert",
        provider=WebhookProvider.WEBHOOKSITE,
        url=HttpUrl(webhook_url),
        webhook_secret=secret,
        events=[
            WebhookEventType.PRICE,
            WebhookEventType.ALERT,
            WebhookEventType.SIGNAL
        ],
        priority=WebhookPriority.HIGH,
        retry_config={
            "max_attempts": 5,
            "base_delay": 2.0,
            "max_delay": 120.0,
            "exponential": True
        },
        timeout=10.0,
        rate_limit=10,
        headers={
            "X-Source": "NexusForexAI"
        }
    )


def get_telegram_bot_webhook(
    bot_token: str,
    chat_id: str
) -> WebhookConfig:
    """Create a webhook for a Telegram bot."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    return WebhookConfig(
        name="Telegram Bot",
        provider=WebhookProvider.TELEGRAM,
        url=HttpUrl(url),
        auth_type="bearer",
        auth_config={"token": bot_token},
        events=[
            WebhookEventType.SIGNAL,
            WebhookEventType.ORDER,
            WebhookEventType.POSITION,
            WebhookEventType.ALERT,
            WebhookEventType.REPORT
        ],
        priority=WebhookPriority.NORMAL,
        retry_config={
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "exponential": True
        },
        timeout=15.0,
        rate_limit=30,
        metadata={
            "chat_id": chat_id,
            "parse_mode": "Markdown",
            "disable_notification": False
        }
    )


def get_slack_webhook(
    webhook_url: str,
    channel: Optional[str] = None
) -> WebhookConfig:
    """Create a webhook for Slack."""
    return WebhookConfig(
        name="Slack Alerts",
        provider=WebhookProvider.SLACK,
        url=HttpUrl(webhook_url),
        events=[
            WebhookEventType.SIGNAL,
            WebhookEventType.ORDER,
            WebhookEventType.POSITION,
            WebhookEventType.ALERT,
            WebhookEventType.PERFORMANCE,
            WebhookEventType.RISK
        ],
        priority=WebhookPriority.NORMAL,
        retry_config={
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "exponential": True
        },
        timeout=10.0,
        rate_limit=10,
        metadata={
            "channel": channel,
            "icon_emoji": ":chart_with_upwards_trend:",
            "username": "Nexus Forex AI"
        }
    )


def get_discord_webhook(
    webhook_url: str,
    thread_id: Optional[str] = None
) -> WebhookConfig:
    """Create a webhook for Discord."""
    return WebhookConfig(
        name="Discord Alerts",
        provider=WebhookProvider.DISCORD,
        url=HttpUrl(webhook_url),
        events=[
            WebhookEventType.SIGNAL,
            WebhookEventType.ORDER,
            WebhookEventType.POSITION,
            WebhookEventType.ALERT,
            WebhookEventType.PERFORMANCE,
            WebhookEventType.SENTIMENT
        ],
        priority=WebhookPriority.NORMAL,
        retry_config={
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 30.0,
            "exponential": True
        },
        timeout=10.0,
        rate_limit=10,
        metadata={
            "thread_id": thread_id,
            "username": "Nexus Forex AI",
            "avatar_url": "https://nexusquantum.com/logo.png"
        }
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'WebhookManager',
    'WebhookConfig',
    'WebhookPayload',
    'WebhookDelivery',
    'WebhookFilter',
    'WebhookEventType',
    'WebhookProvider',
    'WebhookStatus',
    'WebhookPriority',
    'create_webhook_manager',
    'get_forex_price_alert_webhook',
    'get_telegram_bot_webhook',
    'get_slack_webhook',
    'get_discord_webhook'
]
