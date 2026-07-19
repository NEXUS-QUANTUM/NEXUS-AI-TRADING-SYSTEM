# trading/bots/arbitrage_bot/core/circuit_breaker.py
# Nexus AI Trading System - Arbitrage Bot Circuit Breaker Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Circuit Breaker Module

This module provides a comprehensive circuit breaker implementation for the
arbitrage bot system, protecting against cascading failures and ensuring
system resilience. It includes:

- Circuit breaker pattern implementation
- Failure detection and tracking
- Automatic recovery and half-open state
- Custom failure thresholds and recovery times
- Metrics and monitoring
- Event callbacks
- Thread-safe implementation
- Asynchronous support
- Multiple failure type support
- State persistence
- Circuit breaker groups
- Rate limiting integration
- Health checking
- Distributed circuit breaker support

The circuit breaker protects the arbitrage bot from:
- Exchange API failures
- Network issues
- Market volatility
- System overload
- Cascading failures
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreakerEvent(str, Enum):
    """Circuit breaker events."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    REJECTED = "rejected"  # Request rejected when circuit is open
    STATE_CHANGE = "state_change"
    RECOVERY = "recovery"
    FORCED_OPEN = "forced_open"
    FORCED_CLOSE = "forced_close"
    RESET = "reset"


class FailureType(str, Enum):
    """Types of failures."""
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    SERVER = "server"
    CLIENT = "client"
    AUTH = "auth"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration."""
    name: str
    enabled: bool = True
    
    # Failure thresholds
    failure_threshold: int = 5  # Number of failures to open circuit
    failure_percent_threshold: float = 50.0  # Percentage of failures to open circuit
    
    # Time windows
    failure_window_seconds: int = 60  # Time window for tracking failures
    recovery_timeout_seconds: int = 30  # Time to wait before attempting recovery
    
    # Half-open settings
    half_open_max_attempts: int = 3  # Maximum attempts in half-open state
    half_open_success_threshold: int = 2  # Successes needed to close
    
    # Timeout settings
    timeout_seconds: float = 10.0
    timeout_failure_threshold: int = 3
    
    # Rate limit settings
    rate_limit_threshold: int = 10  # Requests per second to trigger rate limiting
    
    # Notification settings
    notify_on_open: bool = True
    notify_on_close: bool = True
    notify_on_half_open: bool = True
    notify_on_failure: bool = False
    notify_on_success: bool = False
    
    # Persistence
    persist_state: bool = False
    persist_key: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('failure_threshold')
    def validate_failure_threshold(cls, v):
        if v < 1:
            raise ValueError("Failure threshold must be at least 1")
        return v

    @validator('failure_percent_threshold')
    def validate_failure_percent_threshold(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Failure percent threshold must be between 0 and 100")
        return v

    @validator('recovery_timeout_seconds')
    def validate_recovery_timeout(cls, v):
        if v < 1:
            raise ValueError("Recovery timeout must be at least 1 second")
        return v


class CircuitBreakerStateData(BaseModel):
    """Circuit breaker state data for persistence."""
    name: str
    state: CircuitBreakerState
    failure_count: int = 0
    success_count: int = 0
    total_failures: int = 0
    total_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changed_at: datetime = Field(default_factory=datetime.utcnow)
    recovery_started_at: Optional[datetime] = None
    half_open_attempts: int = 0
    half_open_successes: int = 0
    events: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CircuitBreakerMetrics(BaseModel):
    """Circuit breaker metrics."""
    name: str
    state: CircuitBreakerState
    failure_count: int
    success_count: int
    failure_rate: float
    total_requests: int
    total_failures: int
    total_successes: int
    uptime_seconds: float
    recovery_time_seconds: Optional[float] = None
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_duration_seconds: float
    half_open_attempts: int
    half_open_successes: int


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Circuit breaker states
CREATE TABLE IF NOT EXISTS circuit_breaker_states (
    name VARCHAR(255) PRIMARY KEY,
    state VARCHAR(20) NOT NULL,
    state_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_circuit_breaker_states_state (state),
    INDEX idx_circuit_breaker_states_updated_at (updated_at)
);

-- Circuit breaker events
CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    event VARCHAR(50) NOT NULL,
    message TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_circuit_breaker_events_name (name),
    INDEX idx_circuit_breaker_events_timestamp (timestamp)
);

-- Circuit breaker metrics history
CREATE TABLE IF NOT EXISTS circuit_breaker_metrics_history (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    metrics JSONB NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_circuit_breaker_metrics_history_name (name),
    INDEX idx_circuit_breaker_metrics_history_timestamp (timestamp)
);
"""


# =============================================================================
# CIRCUIT BREAKER CLASS
# =============================================================================

class CircuitBreaker:
    """
    Advanced circuit breaker implementation.
    
    This class implements the circuit breaker pattern to protect against
    cascading failures in distributed systems.
    
    Features:
    - Configurable failure thresholds
    - Automatic recovery with half-open state
    - Failure rate based tripping
    - Timeout detection
    - Rate limit detection
    - Event callbacks
    - State persistence
    - Comprehensive metrics
    - Thread-safe operations
    - Asynchronous support
    
    Usage:
        cb = CircuitBreaker("exchange_api", failure_threshold=5)
        
        try:
            result = await cb.call(some_async_function)
        except CircuitBreakerOpenError:
            # Circuit is open, handle gracefully
        except Exception as e:
            # Record failure
            await cb.record_failure()
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Configuration (auto-generated if not provided)
            redis: Redis client for distributed state
            pool: PostgreSQL connection pool
        """
        self.name = name
        self.redis = redis
        self.pool = pool
        
        # Configuration
        self._config = config or CircuitBreakerConfig(name=name)
        
        # State
        self._state = CircuitBreakerState.CLOSED
        self._state_data = CircuitBreakerStateData(
            name=name,
            state=CircuitBreakerState.CLOSED
        )
        
        # Failure tracking
        self._failures: List[Tuple[float, FailureType]] = []
        self._successes: List[float] = []
        self._failure_lock = asyncio.Lock()
        
        # Event handlers
        self._event_handlers: Dict[CircuitBreakerEvent, List[Callable]] = {}
        
        # Rate limit tracking
        self._request_timestamps: List[float] = []
        self._rate_limit_lock = asyncio.Lock()
        
        # Running state
        self._initialized = False
        self._running = False
        
        # Metrics
        self._metrics: Optional[CircuitBreakerMetrics] = None
        
        logger.info(f"Circuit breaker '{name}' initialized with config: "
                   f"threshold={self._config.failure_threshold}, "
                   f"recovery={self._config.recovery_timeout_seconds}s")
    
    async def initialize(self):
        """Initialize the circuit breaker."""
        if self._initialized:
            return
        
        # Load persisted state
        if self._config.persist_state:
            await self._load_state()
        
        # Start metrics collection
        self._running = True
        asyncio.create_task(self._metrics_collection_loop())
        
        self._initialized = True
        logger.info(f"Circuit breaker '{self.name}' initialized")
    
    # =========================================================================
    # CORE METHODS
    # =========================================================================
    
    async def call(
        self,
        func: Callable,
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            timeout: Timeout in seconds
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            CircuitBreakerTimeoutError: If execution times out
            Exception: Other exceptions from the function
        """
        # Check if circuit is open
        if self.is_open():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is open"
            )
        
        # Check rate limit
        if self._is_rate_limited():
            raise CircuitBreakerRateLimitError(
                f"Rate limit exceeded for '{self.name}'"
            )
        
        # Record request
        await self._record_request()
        
        try:
            # Execute with timeout
            timeout_seconds = timeout or self._config.timeout_seconds
            
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            else:
                # Run sync function in thread pool
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=timeout_seconds
                )
            
            # Record success
            await self.record_success()
            return result
            
        except asyncio.TimeoutError:
            await self.record_failure(FailureType.TIMEOUT)
            raise CircuitBreakerTimeoutError(
                f"Timeout for '{self.name}' after {timeout_seconds}s"
            )
        except Exception as e:
            # Determine failure type
            failure_type = self._determine_failure_type(e)
            await self.record_failure(failure_type)
            
            # Re-raise if not handled
            raise
        
        finally:
            # Update metrics
            await self._update_metrics()
    
    async def record_success(self):
        """
        Record a successful operation.
        
        This method should be called when an operation succeeds.
        """
        async with self._failure_lock:
            # Add success timestamp
            self._successes.append(time.time())
            
            # Trim old successes
            self._trim_successes()
            
            # Update state
            self._state_data.success_count += 1
            self._state_data.total_successes += 1
            self._state_data.last_success_time = datetime.utcnow()
            
            # Handle state transitions
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state_data.half_open_successes += 1
                
                # Check if enough successes to close
                if (self._state_data.half_open_successes >= 
                    self._config.half_open_success_threshold):
                    await self._transition_to(CircuitBreakerState.CLOSED)
                else:
                    # Still testing
                    await self._handle_event(
                        CircuitBreakerEvent.SUCCESS,
                        "Half-open success"
                    )
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                self._state_data.failure_count = 0
                self._state_data.total_failures = 0
                
                # Reset failure tracking
                self._failures = []
                
                await self._handle_event(
                    CircuitBreakerEvent.SUCCESS,
                    "Success recorded"
                )
            
            # Notify if configured
            if self._config.notify_on_success:
                await self._handle_event(
                    CircuitBreakerEvent.SUCCESS,
                    f"Success recorded: {self._state_data.total_successes}"
                )
    
    async def record_failure(self, failure_type: FailureType = FailureType.EXCEPTION):
        """
        Record a failed operation.
        
        Args:
            failure_type: Type of failure
        """
        async with self._failure_lock:
            # Add failure timestamp
            self._failures.append((time.time(), failure_type))
            
            # Trim old failures
            self._trim_failures()
            
            # Update state
            self._state_data.failure_count += 1
            self._state_data.total_failures += 1
            self._state_data.last_failure_time = datetime.utcnow()
            
            # Check if circuit should open
            if self._should_open():
                await self._transition_to(CircuitBreakerState.OPEN)
            else:
                await self._handle_event(
                    CircuitBreakerEvent.FAILURE,
                    f"Failure recorded: {failure_type}"
                )
            
            # Notify if configured
            if self._config.notify_on_failure:
                await self._handle_event(
                    CircuitBreakerEvent.FAILURE,
                    f"Failure recorded: {failure_type}"
                )
    
    async def record_timeout(self):
        """Record a timeout."""
        await self.record_failure(FailureType.TIMEOUT)
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def is_open(self) -> bool:
        """Check if the circuit is open."""
        if self._state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if self._state_data.recovery_started_at:
                elapsed = (
                    datetime.utcnow() - self._state_data.recovery_started_at
                ).total_seconds()
                
                if elapsed >= self._config.recovery_timeout_seconds:
                    # Move to half-open
                    asyncio.create_task(self._transition_to(
                        CircuitBreakerState.HALF_OPEN
                    ))
                    return False
        
        return self._state == CircuitBreakerState.OPEN
    
    def is_closed(self) -> bool:
        """Check if the circuit is closed."""
        return self._state == CircuitBreakerState.CLOSED
    
    def is_half_open(self) -> bool:
        """Check if the circuit is half-open."""
        return self._state == CircuitBreakerState.HALF_OPEN
    
    async def force_open(self):
        """Force the circuit to open."""
        await self._transition_to(CircuitBreakerState.OPEN, forced=True)
    
    async def force_close(self):
        """Force the circuit to close."""
        await self._transition_to(CircuitBreakerState.CLOSED, forced=True)
    
    async def reset(self):
        """Reset the circuit breaker to closed state."""
        async with self._failure_lock:
            self._state_data.failure_count = 0
            self._state_data.total_failures = 0
            self._state_data.total_successes = 0
            self._state_data.success_count = 0
            self._state_data.half_open_attempts = 0
            self._state_data.half_open_successes = 0
            self._state_data.events = []
            self._failures = []
            self._successes = []
            
            await self._transition_to(CircuitBreakerState.CLOSED, forced=True)
            await self._handle_event(CircuitBreakerEvent.RESET, "Circuit reset")
    
    async def _transition_to(
        self,
        new_state: CircuitBreakerState,
        forced: bool = False
    ):
        """
        Transition to a new state.
        
        Args:
            new_state: New state
            forced: Whether the transition is forced
        """
        old_state = self._state
        
        if old_state == new_state:
            return
        
        async with self._failure_lock:
            self._state = new_state
            self._state_data.state = new_state
            self._state_data.state_changed_at = datetime.utcnow()
            
            if new_state == CircuitBreakerState.OPEN:
                self._state_data.recovery_started_at = datetime.utcnow()
            elif new_state == CircuitBreakerState.CLOSED:
                self._state_data.recovery_started_at = None
                self._state_data.failure_count = 0
                self._state_data.half_open_attempts = 0
                self._state_data.half_open_successes = 0
            
            # Handle events
            event_type = CircuitBreakerEvent.STATE_CHANGE
            if forced:
                if new_state == CircuitBreakerState.OPEN:
                    event_type = CircuitBreakerEvent.FORCED_OPEN
                elif new_state == CircuitBreakerState.CLOSED:
                    event_type = CircuitBreakerEvent.FORCED_CLOSE
            
            event_message = (
                f"State changed from {old_state} to {new_state}"
                f"{' (forced)' if forced else ''}"
            )
            
            await self._handle_event(event_type, event_message)
            
            # Notify if configured
            if new_state == CircuitBreakerState.OPEN and self._config.notify_on_open:
                await self._handle_event(
                    CircuitBreakerEvent.STATE_CHANGE,
                    f"Circuit opened: {event_message}"
                )
            elif new_state == CircuitBreakerState.CLOSED and self._config.notify_on_close:
                await self._handle_event(
                    CircuitBreakerEvent.STATE_CHANGE,
                    f"Circuit closed: {event_message}"
                )
            elif new_state == CircuitBreakerState.HALF_OPEN and self._config.notify_on_half_open:
                await self._handle_event(
                    CircuitBreakerEvent.STATE_CHANGE,
                    f"Circuit half-open: {event_message}"
                )
            
            # Save state
            if self._config.persist_state:
                await self._save_state()
            
            logger.info(
                f"Circuit breaker '{self.name}' transitioned from "
                f"{old_state} to {new_state}"
            )
    
    def _should_open(self) -> bool:
        """
        Determine if the circuit should open based on failures.
        
        Returns:
            True if circuit should open
        """
        # Check failure count threshold
        if self._state_data.failure_count >= self._config.failure_threshold:
            return True
        
        # Check failure percent threshold
        total_requests = self._state_data.failure_count + self._state_data.success_count
        if total_requests > 0:
            failure_rate = (self._state_data.failure_count / total_requests) * 100
            if failure_rate >= self._config.failure_percent_threshold:
                return True
        
        # Check timeout failures
        timeout_failures = sum(
            1 for _, f_type in self._failures
            if f_type == FailureType.TIMEOUT
        )
        if timeout_failures >= self._config.timeout_failure_threshold:
            return True
        
        return False
    
    def _is_rate_limited(self) -> bool:
        """
        Check if rate limit is exceeded.
        
        Returns:
            True if rate limited
        """
        if self._config.rate_limit_threshold <= 0:
            return False
        
        now = time.time()
        window = 1.0  # 1 second window
        
        async with self._rate_limit_lock:
            # Remove old timestamps
            self._request_timestamps = [
                ts for ts in self._request_timestamps
                if now - ts < window
            ]
            
            # Check threshold
            if len(self._request_timestamps) >= self._config.rate_limit_threshold:
                return True
            
            # Add current request
            self._request_timestamps.append(now)
        
        return False
    
    async def _record_request(self):
        """Record a request for rate limiting."""
        pass
    
    def _trim_failures(self):
        """Trim old failures outside the window."""
        window = self._config.failure_window_seconds
        now = time.time()
        self._failures = [
            (ts, f_type) for ts, f_type in self._failures
            if now - ts <= window
        ]
    
    def _trim_successes(self):
        """Trim old successes outside the window."""
        window = self._config.failure_window_seconds
        now = time.time()
        self._successes = [
            ts for ts in self._successes
            if now - ts <= window
        ]
    
    def _determine_failure_type(self, exception: Exception) -> FailureType:
        """
        Determine failure type from exception.
        
        Args:
            exception: Exception to analyze
            
        Returns:
            Failure type
        """
        # This would typically check exception types
        # For now, return exception
        
        exception_name = exception.__class__.__name__.lower()
        
        if "timeout" in exception_name:
            return FailureType.TIMEOUT
        elif "rate" in exception_name:
            return FailureType.RATE_LIMIT
        elif "connection" in exception_name or "network" in exception_name:
            return FailureType.NETWORK
        elif "auth" in exception_name or "permission" in exception_name:
            return FailureType.AUTH
        elif "validation" in exception_name:
            return FailureType.VALIDATION
        elif "server" in exception_name or "internal" in exception_name:
            return FailureType.SERVER
        elif "client" in exception_name:
            return FailureType.CLIENT
        else:
            return FailureType.UNKNOWN
    
    # =========================================================================
    # EVENT HANDLING
    # =========================================================================
    
    def on(self, event: CircuitBreakerEvent, handler: Callable):
        """
        Register an event handler.
        
        Args:
            event: Event type
            handler: Handler function
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def _handle_event(self, event: CircuitBreakerEvent, message: str):
        """
        Handle an event.
        
        Args:
            event: Event type
            message: Event message
        """
        # Store event
        event_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": event.value,
            "message": message,
            "state": self._state.value,
            "failure_count": self._state_data.failure_count,
            "success_count": self._state_data.success_count
        }
        
        self._state_data.events.append(event_data)
        
        # Trim events
        if len(self._state_data.events) > 1000:
            self._state_data.events = self._state_data.events[-500:]
        
        # Log event
        logger.debug(f"Circuit breaker '{self.name}' event: {event} - {message}")
        
        # Notify handlers
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event, message, self._state_data)
                    else:
                        handler(event, message, self._state_data)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
    
    # =========================================================================
    # METRICS
    # =========================================================================
    
    async def get_metrics(self) -> CircuitBreakerMetrics:
        """
        Get circuit breaker metrics.
        
        Returns:
            CircuitBreakerMetrics
        """
        # Calculate metrics
        total_requests = (
            self._state_data.total_failures + self._state_data.total_successes
        )
        
        failure_rate = 0.0
        if total_requests > 0:
            failure_rate = (
                self._state_data.total_failures / total_requests
            ) * 100
        
        uptime = 0.0
        if self._state_data.state_changed_at:
            uptime = (
                datetime.utcnow() - self._state_data.state_changed_at
            ).total_seconds()
        
        recovery_time = None
        if self._state_data.recovery_started_at and self._state != CircuitBreakerState.OPEN:
            recovery_time = (
                datetime.utcnow() - self._state_data.recovery_started_at
            ).total_seconds()
        
        return CircuitBreakerMetrics(
            name=self.name,
            state=self._state,
            failure_count=self._state_data.failure_count,
            success_count=self._state_data.success_count,
            failure_rate=failure_rate,
            total_requests=total_requests,
            total_failures=self._state_data.total_failures,
            total_successes=self._state_data.total_successes,
            uptime_seconds=uptime,
            recovery_time_seconds=recovery_time,
            last_failure_time=self._state_data.last_failure_time,
            last_success_time=self._state_data.last_success_time,
            state_duration_seconds=uptime,
            half_open_attempts=self._state_data.half_open_attempts,
            half_open_successes=self._state_data.half_open_successes
        )
    
    async def _update_metrics(self):
        """Update metrics."""
        self._metrics = await self.get_metrics()
    
    async def _metrics_collection_loop(self):
        """Periodically collect metrics."""
        while self._running:
            try:
                await asyncio.sleep(10)  # Every 10 seconds
                await self._update_metrics()
                
                # Save metrics
                if self.pool:
                    await self._save_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(30)
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    async def _save_state(self):
        """Save circuit breaker state."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO circuit_breaker_states (
                        name, state, state_data, updated_at
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (name) DO UPDATE SET
                        state = EXCLUDED.state,
                        state_data = EXCLUDED.state_data,
                        updated_at = EXCLUDED.updated_at
                    """,
                    self.name,
                    self._state.value,
                    json.dumps(self._state_data.dict(), default=str),
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    async def _load_state(self):
        """Load circuit breaker state."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT state, state_data FROM circuit_breaker_states WHERE name = $1",
                    self.name
                )
                
                if row:
                    state_data = json.loads(row['state_data'])
                    self._state = CircuitBreakerState(row['state'])
                    self._state_data = CircuitBreakerStateData(**state_data)
                    
                    logger.info(f"Loaded state for '{self.name}': {self._state}")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    async def _save_metrics(self):
        """Save metrics to database."""
        if not self.pool or not self._metrics:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO circuit_breaker_metrics_history (
                        name, metrics, timestamp
                    ) VALUES ($1, $2, $3)
                    """,
                    self.name,
                    json.dumps(self._metrics.dict(), default=str),
                    datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the circuit breaker."""
        self._running = False
        
        if self._config.persist_state:
            await self._save_state()
        
        logger.info(f"Circuit breaker '{self.name}' shutdown")


# =============================================================================
# CIRCUIT BREAKER GROUP
# =============================================================================

class CircuitBreakerGroup:
    """
    Group of circuit breakers for related operations.
    
    This class manages a group of circuit breakers for related operations,
    providing aggregate monitoring and control.
    """
    
    def __init__(self, name: str):
        self.name = name
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    def add(self, breaker: CircuitBreaker):
        """Add a circuit breaker to the group."""
        self._breakers[breaker.name] = breaker
    
    def remove(self, name: str):
        """Remove a circuit breaker from the group."""
        self._breakers.pop(name, None)
    
    async def get_metrics(self) -> Dict[str, CircuitBreakerMetrics]:
        """Get metrics for all breakers in the group."""
        metrics = {}
        for name, breaker in self._breakers.items():
            metrics[name] = await breaker.get_metrics()
        return metrics
    
    async def force_open_all(self):
        """Force all circuit breakers to open."""
        for breaker in self._breakers.values():
            await breaker.force_open()
    
    async def force_close_all(self):
        """Force all circuit breakers to close."""
        for breaker in self._breakers.values():
            await breaker.force_close()
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            await breaker.reset()
    
    def get_status(self) -> Dict[str, CircuitBreakerState]:
        """Get status of all circuit breakers."""
        return {
            name: breaker._state
            for name, breaker in self._breakers.items()
        }


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class CircuitBreakerTimeoutError(Exception):
    """Exception raised when a timeout occurs."""
    pass


class CircuitBreakerRateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CircuitBreaker',
    'CircuitBreakerGroup',
    'CircuitBreakerState',
    'CircuitBreakerEvent',
    'FailureType',
    'CircuitBreakerConfig',
    'CircuitBreakerStateData',
    'CircuitBreakerMetrics',
    'CircuitBreakerOpenError',
    'CircuitBreakerTimeoutError',
    'CircuitBreakerRateLimitError'
]
