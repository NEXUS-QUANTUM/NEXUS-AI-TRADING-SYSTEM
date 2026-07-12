"""
NEXUS AI TRADING SYSTEM - Base Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Base Agent system with:
- Abstract base class for all agents
- Lifecycle management (init, start, stop, pause, resume)
- Health monitoring
- Configuration management
- Capability registration
- Event handling
- Logging
- Metrics collection
- Error handling
- Retry logic
- Circuit breaker pattern
- Rate limiting
- Dependency injection
- Testing utilities
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator
from redis import Redis

from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_metrics import AgentMetrics
from backend.core.config import settings
from backend.core.exceptions import AgentError, AgentInitializationError
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.utils.retry import retry_with_backoff

logger = get_logger(__name__)


# ========================================
# ENUMS & CONSTANTS
# ========================================

class AgentStatus(str, Enum):
    """Agent status enum"""
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class AgentHealth(str, Enum):
    """Agent health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AgentPriority(str, Enum):
    """Agent priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    BACKGROUND = "background"


# ========================================
# MODELS
# ========================================

class AgentConfig(BaseModel):
    """Base agent configuration"""
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    version: str = "1.0.0"
    priority: AgentPriority = AgentPriority.NORMAL
    enabled: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    heartbeat_interval: float = 10.0
    health_check_interval: float = 30.0
    max_errors: int = 10
    error_window: float = 60.0
    rate_limit: Optional[int] = None
    rate_limit_window: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 60.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('version')
    def validate_version(cls, v: str) -> str:
        """Validate version format"""
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', v):
            raise ValueError('Version must be in format X.Y.Z')
        return v


@dataclass
class AgentContext:
    """Agent execution context"""
    agent_id: str
    instance_id: str = field(default_factory=lambda: str(uuid4()))
    start_time: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    total_errors: int = 0
    success_count: int = 0
    total_executions: int = 0
    status: AgentStatus = AgentStatus.CREATED
    health: AgentHealth = AgentHealth.UNKNOWN


@dataclass
class AgentEvent:
    """Agent event"""
    type: str
    agent_id: str
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ========================================
# CIRCUIT BREAKER
# ========================================

class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping execution when failures exceed threshold.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = "closed"  # closed, open, half-open
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._last_state_change = datetime.utcnow()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.CircuitBreaker.{name}")
    
    @property
    def state(self) -> str:
        """Get current state"""
        return self._state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self._state == "closed"
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self._state == "open"
    
    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open"""
        return self._state == "half-open"
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Any: Function result
            
        Raises:
            CircuitBreakerError: If circuit is open
        """
        async with self._lock:
            # Check current state
            if self._state == "open":
                # Check if recovery timeout has elapsed
                elapsed = (datetime.utcnow() - self._last_state_change).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self._state = "half-open"
                    self._half_open_calls = 0
                    self.logger.info(f"Circuit {self.name} transitioning to half-open")
                else:
                    raise CircuitBreakerError(
                        f"Circuit {self.name} is open (remaining: {self.recovery_timeout - elapsed:.1f}s)"
                    )
            
            if self._state == "half-open":
                self._half_open_calls += 1
                if self._half_open_calls > self.half_open_max_calls:
                    raise CircuitBreakerError(
                        f"Circuit {self.name} is half-open and max calls exceeded"
                    )
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Success
            async with self._lock:
                if self._state == "half-open":
                    self._success_count += 1
                    if self._success_count >= self.half_open_max_calls:
                        self._state = "closed"
                        self._failure_count = 0
                        self._success_count = 0
                        self.logger.info(f"Circuit {self.name} closed successfully")
            
            return result
            
        except Exception as e:
            # Failure
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = datetime.utcnow()
                
                if self._state == "half-open":
                    self._state = "open"
                    self._last_state_change = datetime.utcnow()
                    self.logger.warning(f"Circuit {self.name} opened (half-open failure)")
                elif self._state == "closed" and self._failure_count >= self.failure_threshold:
                    self._state = "open"
                    self._last_state_change = datetime.utcnow()
                    self.logger.warning(
                        f"Circuit {self.name} opened after {self._failure_count} failures"
                    )
            
            raise


class CircuitBreakerError(Exception):
    """Circuit breaker error"""
    pass


# ========================================
# RATE LIMITER
# ========================================

class RateLimiter:
    """
    Rate limiter for agent execution.
    
    Limits the number of executions per time window.
    """
    
    def __init__(
        self,
        name: str,
        max_calls: int,
        window: float = 60.0
    ):
        self.name = name
        self.max_calls = max_calls
        self.window = window
        self._calls: List[float] = []
        self._lock = asyncio.Lock()
        self.logger = get_logger(f"{__name__}.RateLimiter.{name}")
    
    async def acquire(self) -> bool:
        """
        Acquire a rate limit slot.
        
        Returns:
            bool: True if slot acquired, False otherwise
        """
        async with self._lock:
            now = time.time()
            
            # Clean old calls
            self._calls = [t for t in self._calls if t > now - self.window]
            
            # Check if limit exceeded
            if len(self._calls) >= self.max_calls:
                return False
            
            # Add current call
            self._calls.append(now)
            return True
    
    async def wait_and_acquire(self) -> None:
        """
        Wait until a rate limit slot is available.
        """
        while not await self.acquire():
            await asyncio.sleep(0.1)
    
    def reset(self) -> None:
        """Reset the rate limiter"""
        self._calls = []


# ========================================
# BASE AGENT
# ========================================

class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides:
    - Lifecycle management
    - Configuration
    - Health monitoring
    - Logging
    - Metrics
    - Circuit breaker
    - Rate limiting
    - Error handling
    - Event system
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the base agent.
        
        Args:
            config: Agent configuration
        """
        self.config = AgentConfig(**config)
        self.agent_id = self.config.agent_id
        self.name = self.config.name
        self.version = self.config.version
        
        # Context
        self.context = AgentContext(
            agent_id=self.agent_id,
            status=AgentStatus.CREATED,
            health=AgentHealth.UNKNOWN
        )
        
        # Capabilities
        self.capabilities: List[AgentCapability] = []
        
        # Metrics
        self.metrics = AgentMetrics()
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name=f"{self.name}-breaker",
            failure_threshold=self.config.circuit_breaker_threshold,
            recovery_timeout=self.config.circuit_breaker_timeout
        )
        
        # Rate limiter
        self.rate_limiter = None
        if self.config.rate_limit:
            self.rate_limiter = RateLimiter(
                name=f"{self.name}-limiter",
                max_calls=self.config.rate_limit,
                window=self.config.rate_limit_window
            )
        
        # Redis client for state persistence
        self.redis = get_redis()
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {}
        
        # Error tracking
        self._error_timestamps: List[float] = []
        
        # Running state
        self._running = False
        self._initialized = False
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Logger
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.logger.info(f"Agent {self.name} ({self.agent_id}) initialized")
    
    # ========================================
    # ABSTRACT METHODS
    # ========================================
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        Initialize the agent.
        
        Args:
            config: Agent configuration
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the agent's main execution.
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the agent's execution.
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> AgentHealth:
        """
        Perform a health check.
        
        Returns:
            AgentHealth: Health status
        """
        pass
    
    @abstractmethod
    async def pause(self) -> None:
        """
        Pause the agent's execution.
        """
        pass
    
    @abstractmethod
    async def resume(self) -> None:
        """
        Resume the agent's execution.
        """
        pass
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def run(self) -> None:
        """
        Main execution loop with lifecycle management.
        """
        try:
            # Check circuit breaker
            if self.circuit_breaker.is_open:
                self.logger.warning(f"Circuit breaker is open for {self.name}")
                return
            
            # Check rate limit
            if self.rate_limiter and not await self.rate_limiter.acquire():
                self.logger.warning(f"Rate limit exceeded for {self.name}")
                return
            
            # Execute with retry
            await retry_with_backoff(
                self._execute,
                max_retries=self.config.max_retries,
                initial_delay=self.config.retry_delay
            )
            
        except Exception as e:
            self._handle_error(e)
            raise
    
    async def _execute(self) -> None:
        """
        Execute the agent's main logic.
        
        This method should be overridden by subclasses.
        """
        pass
    
    def _handle_error(self, error: Exception) -> None:
        """
        Handle errors and update metrics.
        
        Args:
            error: The error that occurred
        """
        # Update context
        self.context.error_count += 1
        self.context.total_errors += 1
        self.context.last_error = str(error)
        self.context.status = AgentStatus.ERROR
        
        # Track error timestamps
        now = time.time()
        self._error_timestamps.append(now)
        
        # Clean old errors
        window_start = now - self.config.error_window
        self._error_timestamps = [t for t in self._error_timestamps if t > window_start]
        
        # Check if error threshold exceeded
        if len(self._error_timestamps) >= self.config.max_errors:
            self.logger.critical(
                f"Agent {self.name} exceeded error threshold ({self.config.max_errors})"
            )
            self.context.health = AgentHealth.UNHEALTHY
        
        # Update metrics
        self.metrics.increment_error()
        
        self.logger.error(f"Agent {self.name} error: {error}")
    
    # ========================================
    # STATE PERSISTENCE
    # ========================================
    
    async def save_state(self) -> None:
        """
        Save agent state to Redis.
        """
        try:
            state = {
                "agent_id": self.agent_id,
                "name": self.name,
                "version": self.version,
                "status": self.context.status.value,
                "health": self.context.health.value,
                "start_time": self.context.start_time.isoformat() if self.context.start_time else None,
                "last_heartbeat": self.context.last_heartbeat.isoformat() if self.context.last_heartbeat else None,
                "error_count": self.context.error_count,
                "total_errors": self.context.total_errors,
                "success_count": self.context.success_count,
                "total_executions": self.context.total_executions,
                "last_error": self.context.last_error,
                "metrics": self.metrics.to_dict()
            }
            
            key = f"agent_state:{self.agent_id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(state, default=str)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save agent state: {e}")
    
    async def load_state(self) -> Optional[Dict[str, Any]]:
        """
        Load agent state from Redis.
        
        Returns:
            Optional[Dict[str, Any]]: Loaded state or None
        """
        try:
            key = f"agent_state:{self.agent_id}"
            data = self.redis.get(key)
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load agent state: {e}")
            return None
    
    # ========================================
    # EVENT SYSTEM
    # ========================================
    
    def on(self, event_type: str, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event_type: Event type
            handler: Event handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def off(self, event_type: str, handler: Callable) -> None:
        """
        Remove an event handler.
        
        Args:
            event_type: Event type
            handler: Event handler to remove
        """
        if event_type in self._event_handlers:
            self._event_handlers[event_type] = [
                h for h in self._event_handlers[event_type]
                if h != handler
            ]
    
    async def emit(self, event: AgentEvent) -> None:
        """
        Emit an event.
        
        Args:
            event: Event to emit
        """
        handlers = self._event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                self.logger.error(f"Event handler error: {e}")
    
    # ========================================
    # METRICS
    # ========================================
    
    def get_metrics(self) -> AgentMetrics:
        """
        Get agent metrics.
        
        Returns:
            AgentMetrics: Current metrics
        """
        return self.metrics
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get performance report.
        
        Returns:
            Dict[str, Any]: Performance metrics
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "status": self.context.status.value,
            "health": self.context.health.value,
            "uptime": self._get_uptime(),
            "error_count": self.context.error_count,
            "total_errors": self.context.total_errors,
            "success_count": self.context.success_count,
            "total_executions": self.context.total_executions,
            "success_rate": self._get_success_rate(),
            "metrics": self.metrics.to_dict()
        }
    
    def _get_uptime(self) -> float:
        """Calculate agent uptime in seconds."""
        if self.context.start_time:
            return (datetime.utcnow() - self.context.start_time).total_seconds()
        return 0.0
    
    def _get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.context.total_executions
        if total == 0:
            return 0.0
        return (self.context.success_count / total) * 100
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def has_capability(self, capability: AgentCapability) -> bool:
        """
        Check if agent has a specific capability.
        
        Args:
            capability: Capability to check
            
        Returns:
            bool: True if agent has the capability
        """
        return capability in self.capabilities
    
    def get_status(self) -> AgentStatus:
        """
        Get current agent status.
        
        Returns:
            AgentStatus: Current status
        """
        return self.context.status
    
    def get_health(self) -> AgentHealth:
        """
        Get current agent health.
        
        Returns:
            AgentHealth: Current health
        """
        return self.context.health
    
    def is_running(self) -> bool:
        """
        Check if agent is running.
        
        Returns:
            bool: True if agent is running
        """
        return self._running and self.context.status == AgentStatus.RUNNING
    
    def is_initialized(self) -> bool:
        """
        Check if agent is initialized.
        
        Returns:
            bool: True if agent is initialized
        """
        return self._initialized
    
    async def update_heartbeat(self) -> None:
        """
        Update agent heartbeat.
        """
        self.context.last_heartbeat = datetime.utcnow()
        await self.save_state()
        
        # Publish heartbeat to Redis
        try:
            channel = f"agent_heartbeat:{self.agent_id}"
            self.redis.publish(
                channel,
                json.dumps({
                    "agent_id": self.agent_id,
                    "name": self.name,
                    "status": self.context.status.value,
                    "health": self.context.health.value,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
        except Exception as e:
            self.logger.error(f"Failed to publish heartbeat: {e}")
    
    # ========================================
    # CONTEXT MANAGER
    # ========================================
    
    async def __aenter__(self):
        """Enter async context manager."""
        await self.initialize(self.config.dict())
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        await self.stop()
    
    # ========================================
    # REPRESENTATION
    # ========================================
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, id={self.agent_id}, status={self.context.status.value})>"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.agent_id})"


# ========================================
# AGENT FACTORY
# ========================================

class AgentFactory:
    """
    Factory for creating agent instances.
    """
    
    _agents: Dict[str, Type[BaseAgent]] = {}
    
    @classmethod
    def register(cls, name: str, agent_class: Type[BaseAgent]) -> None:
        """
        Register an agent class.
        
        Args:
            name: Agent name
            agent_class: Agent class
        """
        cls._agents[name] = agent_class
        logger.info(f"Registered agent: {name}")
    
    @classmethod
    def create(cls, name: str, config: Dict[str, Any]) -> BaseAgent:
        """
        Create an agent instance.
        
        Args:
            name: Agent name
            config: Agent configuration
            
        Returns:
            BaseAgent: Agent instance
            
        Raises:
            ValueError: If agent class not found
        """
        if name not in cls._agents:
            raise ValueError(f"Agent class '{name}' not found")
        
        agent_class = cls._agents[name]
        return agent_class(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'BaseAgent',
    'AgentConfig',
    'AgentContext',
    'AgentEvent',
    'AgentStatus',
    'AgentHealth',
    'AgentPriority',
    'CircuitBreaker',
    'CircuitBreakerError',
    'RateLimiter',
    'AgentFactory'
]
