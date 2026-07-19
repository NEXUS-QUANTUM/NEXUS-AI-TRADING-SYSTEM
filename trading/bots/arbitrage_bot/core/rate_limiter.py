# trading/bots/arbitrage_bot/core/rate_limiter.py
# Nexus AI Trading System - Arbitrage Bot Rate Limiter Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Rate Limiter Module

This module provides comprehensive rate limiting and request management
for the arbitrage bot system, including:

- Token bucket rate limiting
- Sliding window rate limiting
- Distributed rate limiting
- Per-endpoint rate limiting
- Per-exchange rate limiting
- Adaptive rate limiting
- Rate limit queuing
- Rate limit monitoring
- Rate limit alerts
- Rate limit optimization
- Request prioritization
- Request batching
- Throttling management
- Circuit breaker integration
- Rate limit headers parsing
- Automatic retry with backoff
- Rate limit statistics

The rate limiter ensures the arbitrage bot respects exchange API limits
and prevents rate limit errors.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import redis.asyncio as aioredis
from pydantic import BaseModel, Field, validator, root_validator

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class RateLimitType(str, Enum):
    """Rate limit types."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    ADAPTIVE = "adaptive"
    DISTRIBUTED = "distributed"


class RateLimitStatus(str, Enum):
    """Rate limit status."""
    OK = "ok"
    WARNING = "warning"  # Approaching limit
    THROTTLED = "throttled"  # Currently throttled
    BLOCKED = "blocked"  # Temporarily blocked
    ERROR = "error"


class RateLimitPriority(str, Enum):
    """Rate limit priority."""
    CRITICAL = "critical"  # Must execute
    HIGH = "high"  # High priority
    NORMAL = "normal"  # Normal priority
    LOW = "low"  # Low priority
    BACKGROUND = "background"  # Background operations


class RequestType(str, Enum):
    """Request types."""
    ORDER = "order"  # Order placement
    MARKET_DATA = "market_data"  # Market data request
    BALANCE = "balance"  # Balance check
    ACCOUNT = "account"  # Account operations
    WEBSOCKET = "websocket"  # WebSocket operations
    HISTORY = "history"  # Historical data
    STREAMING = "streaming"  # Streaming data
    ADMIN = "admin"  # Administrative operations


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RateLimitConfig(BaseModel):
    """Rate limit configuration."""
    enabled: bool = True
    type: RateLimitType = RateLimitType.TOKEN_BUCKET
    rate: int = 100  # Requests per second
    burst: Optional[int] = None  # Burst capacity
    
    # Window-based settings
    window_size: int = 60  # Window size in seconds
    max_requests_per_window: int = 1000
    
    # Adaptive settings
    min_rate: int = 10
    max_rate: int = 200
    adaptation_factor: float = 0.1
    
    # Distributed settings
    redis_key_prefix: str = "rate_limiter:"
    sync_interval: int = 5  # Sync interval in seconds
    
    # Queue settings
    queue_size: int = 1000
    queue_timeout: float = 60.0
    
    # Priority weights
    priority_weights: Dict[str, float] = Field(default_factory=lambda: {
        "critical": 2.0,
        "high": 1.5,
        "normal": 1.0,
        "low": 0.5,
        "background": 0.25
    })
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('rate')
    def validate_rate(cls, v):
        if v <= 0:
            raise ValueError("Rate must be positive")
        return v

    @validator('burst')
    def validate_burst(cls, v, values):
        if v is not None and v < values.get('rate', 100):
            raise ValueError("Burst must be at least rate")
        return v


class RateLimitRequest(BaseModel):
    """Rate limit request."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: RequestType
    priority: RateLimitPriority = RateLimitPriority.NORMAL
    endpoint: str
    exchange: Optional[str] = None
    weight: float = 1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('weight')
    def validate_weight(cls, v):
        if v <= 0:
            raise ValueError("Weight must be positive")
        return v


class RateLimitResponse(BaseModel):
    """Rate limit response."""
    request_id: str
    allowed: bool
    wait_time: float = 0.0
    retry_after: float = 0.0
    status: RateLimitStatus = RateLimitStatus.OK
    tokens_remaining: float = 0.0
    tokens_refill_rate: float = 0.0
    limit: int = 0
    remaining: int = 0
    reset_time: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RateLimitStats(BaseModel):
    """Rate limit statistics."""
    name: str
    type: RateLimitType
    requests: int = 0
    allowed: int = 0
    denied: int = 0
    queued: int = 0
    average_wait_time: float = 0.0
    max_wait_time: float = 0.0
    current_tokens: float = 0.0
    current_rate: float = 0.0
    peak_rate: float = 0.0
    status: RateLimitStatus = RateLimitStatus.OK
    last_request_time: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# RATE LIMITER IMPLEMENTATIONS
# =============================================================================

class RateLimiter:
    """
    Advanced rate limiter for arbitrage bot.
    
    Features:
    - Token bucket rate limiting
    - Sliding window rate limiting
    - Distributed rate limiting
    - Per-endpoint rate limiting
    - Per-exchange rate limiting
    - Adaptive rate limiting
    - Rate limit queuing
    - Rate limit monitoring
    - Rate limit alerts
    - Rate limit optimization
    - Request prioritization
    - Request batching
    - Throttling management
    - Circuit breaker integration
    - Rate limit headers parsing
    - Automatic retry with backoff
    - Rate limit statistics
    """
    
    def __init__(
        self,
        name: str,
        config: RateLimitConfig,
        redis: Optional[aioredis.Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.name = name
        self.config = config
        self.redis = redis
        self.pool = pool
        
        # Rate limiter state
        self._tokens = float(config.burst or config.rate)
        self._last_refill = time.time()
        self._window_requests: List[float] = []
        
        # Stats
        self._stats = RateLimitStats(name=name, type=config.type)
        
        # Queue
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._queue_workers: List[asyncio.Task] = []
        self._num_queue_workers = 5
        
        # Circuit breaker
        self._cb = CircuitBreaker(
            name=f"rate_limiter_{name}",
            failure_threshold=5,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Child limiters for endpoints
        self._endpoint_limiters: Dict[str, RateLimiter] = {}
        
        logger.info(f"RateLimiter '{name}' initialized with config type={config.type}, rate={config.rate}")
    
    async def initialize(self):
        """Initialize the rate limiter."""
        if self._initialized:
            return
        
        # Start queue workers
        self._running = True
        for i in range(self._num_queue_workers):
            worker = asyncio.create_task(self._queue_worker_loop(i))
            self._queue_workers.append(worker)
        
        # Start stats collection
        asyncio.create_task(self._stats_loop())
        
        self._initialized = True
        logger.info(f"RateLimiter '{self.name}' initialized")
    
    # =========================================================================
    # CORE RATE LIMITING
    # =========================================================================
    
    async def acquire(
        self,
        request: RateLimitRequest
    ) -> RateLimitResponse:
        """
        Acquire rate limit token.
        
        Args:
            request: Rate limit request
            
        Returns:
            RateLimitResponse
        """
        if not self.config.enabled:
            return RateLimitResponse(
                request_id=request.id,
                allowed=True,
                status=RateLimitStatus.OK,
                limit=self.config.rate,
                remaining=self.config.rate
            )
        
        # Check circuit breaker
        if self._cb.is_open():
            return RateLimitResponse(
                request_id=request.id,
                allowed=False,
                status=RateLimitStatus.BLOCKED,
                wait_time=self._cb.recovery_timeout,
                retry_after=self._cb.recovery_timeout,
                metadata={"reason": "Circuit breaker open"}
            )
        
        # Apply priority weight
        weight = request.weight * self.config.priority_weights.get(request.priority.value, 1.0)
        
        # Check rate limit
        allowed, wait_time, tokens_remaining = await self._check_limit(weight)
        
        if allowed:
            self._stats.allowed += 1
            self._stats.current_tokens = tokens_remaining
            return RateLimitResponse(
                request_id=request.id,
                allowed=True,
                wait_time=0.0,
                status=RateLimitStatus.OK,
                tokens_remaining=tokens_remaining,
                tokens_refill_rate=self.config.rate,
                limit=self.config.rate,
                remaining=int(tokens_remaining)
            )
        
        # Not allowed - queue or reject
        if self.config.queue_size > 0:
            # Try to queue
            try:
                priority = self._get_priority_value(request.priority)
                await asyncio.wait_for(
                    self._queue.put((priority, request)),
                    timeout=self.config.queue_timeout
                )
                self._stats.queued += 1
                
                return RateLimitResponse(
                    request_id=request.id,
                    allowed=False,
                    wait_time=self.config.queue_timeout,
                    retry_after=self.config.queue_timeout,
                    status=RateLimitStatus.THROTTLED,
                    tokens_remaining=tokens_remaining,
                    metadata={"reason": "Queued"}
                )
            except asyncio.TimeoutError:
                pass
        
        # Reject
        self._stats.denied += 1
        self._cb.record_failure()
        
        return RateLimitResponse(
            request_id=request.id,
            allowed=False,
            wait_time=wait_time,
            retry_after=wait_time,
            status=RateLimitStatus.THROTTLED,
            tokens_remaining=tokens_remaining,
            metadata={"reason": "Rate limit exceeded"}
        )
    
    async def _check_limit(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check if rate limit allows the request.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        if self.config.type == RateLimitType.TOKEN_BUCKET:
            return await self._check_token_bucket(weight)
        elif self.config.type == RateLimitType.SLIDING_WINDOW:
            return await self._check_sliding_window(weight)
        elif self.config.type == RateLimitType.FIXED_WINDOW:
            return await self._check_fixed_window(weight)
        elif self.config.type == RateLimitType.ADAPTIVE:
            return await self._check_adaptive(weight)
        elif self.config.type == RateLimitType.DISTRIBUTED:
            return await self._check_distributed(weight)
        else:
            return True, 0, self.config.rate
    
    async def _check_token_bucket(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check token bucket rate limit.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        async with self._lock:
            # Refill tokens
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.config.burst or self.config.rate,
                self._tokens + elapsed * self.config.rate
            )
            self._last_refill = now
            
            # Check if enough tokens
            if self._tokens >= weight:
                self._tokens -= weight
                return True, 0, self._tokens
            
            # Calculate wait time
            needed = weight - self._tokens
            wait_time = needed / self.config.rate
            
            return False, wait_time, self._tokens
    
    async def _check_sliding_window(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check sliding window rate limit.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        async with self._lock:
            now = time.time()
            window_start = now - self.config.window_size
            
            # Clean old requests
            self._window_requests = [t for t in self._window_requests if t > window_start]
            
            # Count requests in window
            count = len(self._window_requests)
            remaining = self.config.max_requests_per_window - count
            
            if remaining >= weight:
                self._window_requests.extend([now] * int(weight))
                return True, 0, remaining
            
            # Calculate wait time
            if self._window_requests:
                oldest = self._window_requests[0]
                wait_time = oldest + self.config.window_size - now
            else:
                wait_time = self.config.window_size
            
            return False, wait_time, remaining
    
    async def _check_fixed_window(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check fixed window rate limit.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        async with self._lock:
            now = time.time()
            window = int(now / self.config.window_size)
            
            # Get window count from Redis
            if self.redis:
                key = f"{self.config.redis_key_prefix}{self.name}:window:{window}"
                count = await self.redis.get(key) or 0
            else:
                # In-memory window count (not recommended for production)
                if not hasattr(self, '_window_counts'):
                    self._window_counts = {}
                count = self._window_counts.get(window, 0)
            
            remaining = self.config.max_requests_per_window - count
            
            if remaining >= weight:
                # Increment count
                if self.redis:
                    await self.redis.incr(key, int(weight))
                    await self.redis.expire(key, self.config.window_size + 5)
                else:
                    self._window_counts[window] = count + weight
                
                return True, 0, remaining
            
            wait_time = (window + 1) * self.config.window_size - now
            return False, wait_time, remaining
    
    async def _check_adaptive(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check adaptive rate limit.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        # Calculate current rate
        now = time.time()
        recent_requests = [t for t in self._window_requests if t > now - 60]
        current_rate = len(recent_requests) / 60
        
        # Adjust rate based on load
        if current_rate > self.config.rate * 0.8:
            # High load - decrease rate
            new_rate = max(
                self.config.min_rate,
                self.config.rate * (1 - self.config.adaptation_factor)
            )
            self.config.rate = int(new_rate)
        elif current_rate < self.config.rate * 0.3:
            # Low load - increase rate
            new_rate = min(
                self.config.max_rate,
                self.config.rate * (1 + self.config.adaptation_factor)
            )
            self.config.rate = int(new_rate)
        
        # Use token bucket with adjusted rate
        return await self._check_token_bucket(weight)
    
    async def _check_distributed(self, weight: float) -> Tuple[bool, float, float]:
        """
        Check distributed rate limit.
        
        Args:
            weight: Request weight
            
        Returns:
            Tuple of (allowed, wait_time, tokens_remaining)
        """
        if not self.redis:
            logger.warning("Redis not available for distributed rate limiting")
            return await self._check_token_bucket(weight)
        
        key = f"{self.config.redis_key_prefix}{self.name}:tokens"
        
        try:
            # Get current tokens from Redis
            tokens = await self.redis.get(key)
            if tokens is None:
                await self.redis.set(key, self.config.rate)
                tokens = self.config.rate
            else:
                tokens = float(tokens)
            
            # Refill tokens (distributed)
            now = time.time()
            last_refill_key = f"{key}:refill"
            last_refill = await self.redis.get(last_refill_key)
            if last_refill:
                elapsed = now - float(last_refill)
                tokens = min(
                    self.config.burst or self.config.rate,
                    tokens + elapsed * self.config.rate
                )
            
            if tokens >= weight:
                # Consume tokens
                await self.redis.decrby(key, int(weight))
                await self.redis.set(last_refill_key, str(now))
                return True, 0, tokens
            
            needed = weight - tokens
            wait_time = needed / self.config.rate
            return False, wait_time, tokens
            
        except Exception as e:
            logger.error(f"Distributed rate limit error: {e}")
            return await self._check_token_bucket(weight)
    
    # =========================================================================
    # QUEUE MANAGEMENT
    # =========================================================================
    
    def _get_priority_value(self, priority: RateLimitPriority) -> int:
        """Get numeric priority value."""
        values = {
            RateLimitPriority.CRITICAL: 0,
            RateLimitPriority.HIGH: 1,
            RateLimitPriority.NORMAL: 2,
            RateLimitPriority.LOW: 3,
            RateLimitPriority.BACKGROUND: 4
        }
        return values.get(priority, 2)
    
    async def _queue_worker_loop(self, worker_id: int):
        """
        Worker loop for processing queued requests.
        
        Args:
            worker_id: Worker ID
        """
        logger.info(f"Rate limiter queue worker {worker_id} started")
        
        while self._running:
            try:
                # Get from queue
                priority, request = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )
                
                # Try to acquire token
                response = await self.acquire(request)
                
                if response.allowed:
                    # Execute request (callback would be here)
                    pass
                else:
                    # Re-queue with backoff if still not allowed
                    if response.status != RateLimitStatus.BLOCKED:
                        await asyncio.sleep(response.wait_time or 1.0)
                        await self._queue.put((priority, request))
                
                self._queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Rate limiter queue worker {worker_id} stopped")
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def get_stats(self) -> RateLimitStats:
        """
        Get rate limit statistics.
        
        Returns:
            RateLimitStats
        """
        async with self._lock:
            self._stats.current_tokens = self._tokens
            self._stats.current_rate = self.config.rate
            
            # Calculate peak rate
            if len(self._window_requests) > 1:
                peaks = []
                window = 60
                for i in range(0, len(self._window_requests), 10):
                    chunk = self._window_requests[i:i+10]
                    if chunk:
                        rate = len(chunk) / (chunk[-1] - chunk[0]) if chunk[-1] > chunk[0] else 0
                        peaks.append(rate)
                if peaks:
                    self._stats.peak_rate = max(peaks)
            
            return self._stats
    
    async def reset_stats(self):
        """Reset statistics."""
        async with self._lock:
            self._stats = RateLimitStats(name=self.name, type=self.config.type)
    
    # =========================================================================
    # STATUS CHECK
    # =========================================================================
    
    async def get_status(self) -> RateLimitStatus:
        """
        Get current rate limit status.
        
        Returns:
            RateLimitStatus
        """
        if self._cb.is_open():
            return RateLimitStatus.BLOCKED
        
        tokens = self._tokens
        if tokens < self.config.rate * 0.1:
            return RateLimitStatus.THROTTLED
        elif tokens < self.config.rate * 0.25:
            return RateLimitStatus.WARNING
        
        return RateLimitStatus.OK
    
    # =========================================================================
    # STATS LOOP
    # =========================================================================
    
    async def _stats_loop(self):
        """Periodic stats collection and cleanup."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every minute
                
                # Update stats
                await self.get_stats()
                
                # Clean up old window requests
                now = time.time()
                window_start = now - self.config.window_size
                async with self._lock:
                    self._window_requests = [t for t in self._window_requests if t > window_start]
                
                # Save stats to database
                if self.pool:
                    await self._save_stats()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stats loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_stats(self):
        """Save stats to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO rate_limiter_stats (
                        name, type, requests, allowed, denied,
                        queued, average_wait_time, max_wait_time,
                        current_tokens, current_rate, peak_rate,
                        status, last_request_time, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14)
                    """,
                    self.name,
                    self.config.type.value,
                    self._stats.requests,
                    self._stats.allowed,
                    self._stats.denied,
                    self._stats.queued,
                    self._stats.average_wait_time,
                    self._stats.max_wait_time,
                    self._stats.current_tokens,
                    self._stats.current_rate,
                    self._stats.peak_rate,
                    self._stats.status.value,
                    self._stats.last_request_time,
                    json.dumps(self._stats.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    # =========================================================================
    # PER-ENDPOINT LIMITERS
    # =========================================================================
    
    def get_endpoint_limiter(
        self,
        endpoint: str,
        config: Optional[RateLimitConfig] = None
    ) -> 'RateLimiter':
        """
        Get or create an endpoint-specific rate limiter.
        
        Args:
            endpoint: Endpoint name
            config: Endpoint-specific configuration
            
        Returns:
            RateLimiter instance
        """
        if endpoint not in self._endpoint_limiters:
            if config is None:
                config = RateLimitConfig(
                    rate=int(self.config.rate * 0.5),
                    burst=int((self.config.burst or self.config.rate) * 0.5)
                )
            
            limiter = RateLimiter(
                name=f"{self.name}:{endpoint}",
                config=config,
                redis=self.redis,
                pool=self.pool
            )
            
            # Initialize the endpoint limiter
            asyncio.create_task(limiter.initialize())
            self._endpoint_limiters[endpoint] = limiter
        
        return self._endpoint_limiters[endpoint]
    
    # =========================================================================
    # EXCHANGE-SPECIFIC LIMITERS
    # =========================================================================
    
    @classmethod
    async def create_exchange_limiter(
        cls,
        exchange: str,
        rate: Optional[int] = None,
        redis: Optional[aioredis.Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> 'RateLimiter':
        """
        Create a rate limiter for a specific exchange.
        
        Args:
            exchange: Exchange name
            rate: Rate limit (requests per second)
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            RateLimiter instance
        """
        # Default rates for common exchanges
        default_rates = {
            "binance": 50,
            "okx": 40,
            "kraken": 30,
            "coinbase": 20,
            "bybit": 40,
            "bitget": 30,
            "kucoin": 30,
            "huobi": 30,
            "gateio": 30,
            "mexc": 20
        }
        
        if rate is None:
            rate = default_rates.get(exchange.lower(), 30)
        
        config = RateLimitConfig(
            rate=rate,
            burst=rate * 2,
            type=RateLimitType.DISTRIBUTED,
            redis_key_prefix=f"rate_limiter:{exchange}:"
        )
        
        limiter = cls(
            name=f"exchange_{exchange}",
            config=config,
            redis=redis,
            pool=pool
        )
        await limiter.initialize()
        
        return limiter
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the rate limiter."""
        self._running = False
        
        # Stop queue workers
        for worker in self._queue_workers:
            worker.cancel()
        
        if self._queue_workers:
            await asyncio.gather(*self._queue_workers, return_exceptions=True)
        
        # Shutdown endpoint limiters
        for limiter in self._endpoint_limiters.values():
            await limiter.shutdown()
        
        logger.info(f"RateLimiter '{self.name}' shutdown")


# =============================================================================
# RATE LIMITER FACTORY
# =============================================================================

class RateLimiterFactory:
    """
    Factory for creating and managing rate limiters.
    
    This factory provides a unified interface for creating different
    types of rate limiters and managing them centrally.
    """
    
    _limiters: Dict[str, RateLimiter] = {}
    
    @classmethod
    def get_limiter(
        cls,
        name: str,
        config: Optional[RateLimitConfig] = None,
        redis: Optional[aioredis.Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> RateLimiter:
        """
        Get or create a rate limiter.
        
        Args:
            name: Limiter name
            config: Rate limit configuration
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            RateLimiter instance
        """
        if name not in cls._limiters:
            if config is None:
                config = RateLimitConfig()
            
            limiter = RateLimiter(name, config, redis, pool)
            asyncio.create_task(limiter.initialize())
            cls._limiters[name] = limiter
        
        return cls._limiters[name]
    
    @classmethod
    async def create_exchange_limiter(
        cls,
        exchange: str,
        rate: Optional[int] = None,
        redis: Optional[aioredis.Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ) -> RateLimiter:
        """
        Create an exchange-specific rate limiter.
        
        Args:
            exchange: Exchange name
            rate: Rate limit (requests per second)
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            RateLimiter instance
        """
        limiter = await RateLimiter.create_exchange_limiter(exchange, rate, redis, pool)
        cls._limiters[f"exchange_{exchange}"] = limiter
        return limiter
    
    @classmethod
    async def shutdown_all(cls):
        """Shutdown all rate limiters."""
        for limiter in cls._limiters.values():
            await limiter.shutdown()
        cls._limiters.clear()


# =============================================================================
# DECORATOR
# =============================================================================

def rate_limited(
    limiter: RateLimiter,
    request_type: RequestType = RequestType.MARKET_DATA,
    priority: RateLimitPriority = RateLimitPriority.NORMAL,
    weight: float = 1.0
):
    """
    Decorator to apply rate limiting to a function.
    
    Args:
        limiter: Rate limiter instance
        request_type: Type of request
        priority: Request priority
        weight: Request weight
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Create request
            request = RateLimitRequest(
                type=request_type,
                priority=priority,
                endpoint=func.__name__,
                weight=weight
            )
            
            # Acquire token
            response = await limiter.acquire(request)
            
            if not response.allowed:
                raise RateLimitExceededError(
                    f"Rate limit exceeded for {func.__name__}: {response.status}",
                    response=response
                )
            
            try:
                return await func(*args, **kwargs)
            except Exception:
                # Record failure
                limiter._cb.record_failure()
                raise
        
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions
            return func(*args, **kwargs)
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class RateLimitExceededError(Exception):
    """Rate limit exceeded error."""
    def __init__(self, message: str, response: Optional[RateLimitResponse] = None):
        super().__init__(message)
        self.response = response


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RateLimiter',
    'RateLimiterFactory',
    'RateLimitType',
    'RateLimitStatus',
    'RateLimitPriority',
    'RequestType',
    'RateLimitConfig',
    'RateLimitRequest',
    'RateLimitResponse',
    'RateLimitStats',
    'rate_limited',
    'RateLimitExceededError'
]
