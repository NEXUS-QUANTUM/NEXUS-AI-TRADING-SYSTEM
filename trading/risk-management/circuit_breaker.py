# trading/risk-management/circuit_breaker.py
"""
NEXUS AI TRADING SYSTEM - Circuit Breaker
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements circuit breaker patterns for risk management
to prevent catastrophic losses and protect the trading system from
market anomalies, system failures, and excessive drawdowns.

Key Features:
- Market volatility circuit breakers
- Loss-based circuit breakers
- Drawdown circuit breakers
- Daily loss limits
- Consecutive loss limits
- Recovery and reset mechanisms
- Alerting and logging
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import deque, defaultdict

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import Trade, Position, MarketData

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class CircuitBreakerState(str, Enum):
    """States of a circuit breaker"""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Tripped - no trading
    HALF_OPEN = "half_open"    # Testing recovery
    RECOVERING = "recovering"  # Gradual recovery
    PERMANENTLY_OPEN = "permanently_open"  # Requires manual reset


class CircuitBreakerType(str, Enum):
    """Types of circuit breakers"""
    VOLATILITY = "volatility"
    LOSS = "loss"
    DRAWDOWN = "drawdown"
    DAILY_LOSS = "daily_loss"
    CONSECUTIVE_LOSS = "consecutive_loss"
    MAX_POSITION = "max_position"
    MAX_EXPOSURE = "max_exposure"
    RATE_LIMIT = "rate_limit"
    SYSTEM_ERROR = "system_error"
    TIME_BASED = "time_based"


class CircuitBreakerSeverity(str, Enum):
    """Severity levels for circuit breakers"""
    WARNING = "warning"        # Alert only
    MODERATE = "moderate"      # Partial restriction
    SEVERE = "severe"          # Full restriction
    CRITICAL = "critical"      # Emergency shutdown


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker"""
    breaker_type: CircuitBreakerType
    severity: CircuitBreakerSeverity = CircuitBreakerSeverity.MODERATE
    threshold: float = 0.0
    time_window: int = 60  # seconds
    min_samples: int = 5
    cooldown_period: int = 300  # seconds
    reset_period: int = 3600  # seconds
    max_trips: int = 3
    auto_reset: bool = True
    enabled: bool = True
    name: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerStateData:
    """State data for a circuit breaker"""
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    trips: int = 0
    last_trip_time: Optional[datetime] = None
    last_reset_time: Optional[datetime] = None
    value_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    error_history: deque = field(default_factory=lambda: deque(maxlen=100))
    current_value: float = 0.0
    is_triggered: bool = False
    cooldown_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerEvent:
    """Circuit breaker event"""
    breaker_name: str
    breaker_type: CircuitBreakerType
    state: CircuitBreakerState
    severity: CircuitBreakerSeverity
    timestamp: datetime = field(default_factory=datetime.utcnow)
    value: float = 0.0
    threshold: float = 0.0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreaker:
    """
    Circuit breaker for risk management.
    
    Monitors various risk metrics and trips when thresholds are exceeded.
    Supports multiple breaker types and severity levels.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        """
        Initialize the circuit breaker.
        
        Args:
            config: Circuit breaker configuration
        """
        self.config = config
        self.state_data = CircuitBreakerStateData()
        self._events: List[CircuitBreakerEvent] = []
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_trip_callbacks: List[Callable[[CircuitBreakerEvent], Awaitable[None]]] = []
        self._on_reset_callbacks: List[Callable[[CircuitBreakerEvent], Awaitable[None]]] = []
        self._on_state_change_callbacks: List[Callable[[CircuitBreakerState, CircuitBreakerState], Awaitable[None]]] = []
        
        self.logger = logger
    
    @property
    def name(self) -> str:
        """Get breaker name."""
        return self.config.name or f"{self.config.breaker_type.value}_breaker"
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        return self.state_data.state
    
    @property
    def is_tripped(self) -> bool:
        """Check if breaker is tripped."""
        return self.state in [CircuitBreakerState.OPEN, CircuitBreakerState.PERMANENTLY_OPEN]
    
    @property
    def is_allowed(self) -> bool:
        """Check if trading is allowed."""
        return self.state == CircuitBreakerState.CLOSED
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_trip(self, callback: Callable[[CircuitBreakerEvent], Awaitable[None]]) -> None:
        """Register callback for trip events."""
        self._on_trip_callbacks.append(callback)
    
    def on_reset(self, callback: Callable[[CircuitBreakerEvent], Awaitable[None]]) -> None:
        """Register callback for reset events."""
        self._on_reset_callbacks.append(callback)
    
    def on_state_change(
        self,
        callback: Callable[[CircuitBreakerState, CircuitBreakerState], Awaitable[None]],
    ) -> None:
        """Register callback for state changes."""
        self._on_state_change_callbacks.append(callback)
    
    async def _trigger_trip_callbacks(self, event: CircuitBreakerEvent) -> None:
        """Trigger trip callbacks."""
        for callback in self._on_trip_callbacks:
            try:
                await callback(event)
            except Exception as e:
                self.logger.error(f"Error in trip callback: {e}")
    
    async def _trigger_reset_callbacks(self, event: CircuitBreakerEvent) -> None:
        """Trigger reset callbacks."""
        for callback in self._on_reset_callbacks:
            try:
                await callback(event)
            except Exception as e:
                self.logger.error(f"Error in reset callback: {e}")
    
    async def _trigger_state_change_callbacks(
        self,
        old_state: CircuitBreakerState,
        new_state: CircuitBreakerState,
    ) -> None:
        """Trigger state change callbacks."""
        for callback in self._on_state_change_callbacks:
            try:
                await callback(old_state, new_state)
            except Exception as e:
                self.logger.error(f"Error in state change callback: {e}")
    
    # ========================================================================
    # CORE OPERATIONS
    # ========================================================================
    
    async def update(self, value: float) -> bool:
        """
        Update the circuit breaker with a new value.
        
        Args:
            value: Current value to evaluate
            
        Returns:
            bool: True if breaker remains closed
        """
        if not self.config.enabled:
            return True
        
        async with self._lock:
            self.state_data.current_value = value
            self.state_data.value_history.append(value)
            
            # Check if we're in cooldown
            if self.state_data.cooldown_until and datetime.utcnow() < self.state_data.cooldown_until:
                return False
            
            # Evaluate based on type
            should_trip = await self._evaluate(value)
            
            if should_trip:
                await self._trip(value)
                return False
            
            # Check if we should reset
            if self.state == CircuitBreakerState.OPEN:
                await self._attempt_reset()
            
            return self.state == CircuitBreakerState.CLOSED
    
    async def _evaluate(self, value: float) -> bool:
        """
        Evaluate if the breaker should trip.
        
        Args:
            value: Current value
            
        Returns:
            bool: True if breaker should trip
        """
        if self.state == CircuitBreakerState.PERMANENTLY_OPEN:
            return True
        
        # Check if we have enough samples
        if len(self.state_data.value_history) < self.config.min_samples:
            return False
        
        # Evaluate based on type
        breaker_type = self.config.breaker_type
        threshold = self.config.threshold
        
        if breaker_type == CircuitBreakerType.VOLATILITY:
            # Check volatility spike
            recent = list(self.state_data.value_history)[-self.config.min_samples:]
            mean = sum(recent) / len(recent)
            std = (sum((v - mean) ** 2 for v in recent) / len(recent)) ** 0.5
            return value > mean + std * threshold
        
        elif breaker_type == CircuitBreakerType.LOSS:
            # Check loss threshold
            return abs(value) > threshold
        
        elif breaker_type == CircuitBreakerType.DRAWDOWN:
            # Check drawdown threshold
            peak = max(self.state_data.value_history)
            current_dd = (peak - value) / peak if peak > 0 else 0
            return current_dd > threshold
        
        elif breaker_type == CircuitBreakerType.DAILY_LOSS:
            # Check daily loss
            return abs(value) > threshold
        
        elif breaker_type == CircuitBreakerType.CONSECUTIVE_LOSS:
            # Check consecutive losses
            return value >= threshold
        
        elif breaker_type == CircuitBreakerType.MAX_POSITION:
            # Check max position size
            return value > threshold
        
        elif breaker_type == CircuitBreakerType.MAX_EXPOSURE:
            # Check max exposure
            return value > threshold
        
        elif breaker_type == CircuitBreakerType.RATE_LIMIT:
            # Check rate limit
            return value > threshold
        
        elif breaker_type == CircuitBreakerType.SYSTEM_ERROR:
            # Check system errors
            return value >= threshold
        
        elif breaker_type == CircuitBreakerType.TIME_BASED:
            # Time-based tripping
            elapsed = (datetime.utcnow() - self.state_data.last_trip_time).total_seconds() if self.state_data.last_trip_time else 0
            return elapsed > threshold
        
        return False
    
    async def _trip(self, value: float) -> None:
        """
        Trip the circuit breaker.
        
        Args:
            value: Value that triggered the trip
        """
        old_state = self.state_data.state
        
        # Update state
        self.state_data.state = CircuitBreakerState.OPEN
        self.state_data.trips += 1
        self.state_data.last_trip_time = datetime.utcnow()
        self.state_data.is_triggered = True
        self.state_data.cooldown_until = datetime.utcnow() + timedelta(seconds=self.config.cooldown_period)
        
        # Check if max trips exceeded
        if self.state_data.trips >= self.config.max_trips:
            self.state_data.state = CircuitBreakerState.PERMANENTLY_OPEN
            self.logger.critical(f"Circuit breaker {self.name} permanently open after {self.state_data.trips} trips")
        
        # Create event
        event = CircuitBreakerEvent(
            breaker_name=self.name,
            breaker_type=self.config.breaker_type,
            state=self.state_data.state,
            severity=self.config.severity,
            value=value,
            threshold=self.config.threshold,
            message=f"Circuit breaker {self.name} tripped (value: {value:.2f}, threshold: {self.config.threshold:.2f})",
            metadata={"trips": self.state_data.trips},
        )
        self._events.append(event)
        
        # Trigger callbacks
        await self._trigger_trip_callbacks(event)
        if old_state != self.state_data.state:
            await self._trigger_state_change_callbacks(old_state, self.state_data.state)
        
        self.logger.warning(
            f"Circuit breaker {self.name} tripped: "
            f"value={value:.2f}, threshold={self.config.threshold:.2f}, "
            f"type={self.config.breaker_type.value}"
        )
    
    async def _attempt_reset(self) -> None:
        """
        Attempt to reset the circuit breaker.
        """
        if not self.config.auto_reset:
            return
        
        if self.state == CircuitBreakerState.PERMANENTLY_OPEN:
            return
        
        # Check if cooldown period has passed
        if self.state_data.cooldown_until and datetime.utcnow() < self.state_data.cooldown_until:
            return
        
        # Check reset period
        if self.state_data.last_reset_time:
            elapsed = (datetime.utcnow() - self.state_data.last_reset_time).total_seconds()
            if elapsed < self.config.reset_period:
                return
        
        # Reset to half-open
        old_state = self.state_data.state
        self.state_data.state = CircuitBreakerState.HALF_OPEN
        self.state_data.last_reset_time = datetime.utcnow()
        self.state_data.is_triggered = False
        
        # If half-open is successful, transition to closed
        # This requires successful checks
        if await self._check_half_open():
            self.state_data.state = CircuitBreakerState.CLOSED
            self.logger.info(f"Circuit breaker {self.name} reset to closed")
        else:
            self.state_data.state = CircuitBreakerState.OPEN
            self.logger.warning(f"Circuit breaker {self.name} half-open test failed")
        
        # Create event
        event = CircuitBreakerEvent(
            breaker_name=self.name,
            breaker_type=self.config.breaker_type,
            state=self.state_data.state,
            severity=self.config.severity,
            message=f"Circuit breaker {self.name} reset attempt",
        )
        self._events.append(event)
        
        # Trigger callbacks
        await self._trigger_reset_callbacks(event)
        if old_state != self.state_data.state:
            await self._trigger_state_change_callbacks(old_state, self.state_data.state)
    
    async def _check_half_open(self) -> bool:
        """
        Check if half-open state should transition to closed.
        
        Returns:
            bool: True if recovery is successful
        """
        # Check if value is below threshold
        current_value = self.state_data.current_value
        
        if self.config.breaker_type in [
            CircuitBreakerType.LOSS,
            CircuitBreakerType.DRAWDOWN,
            CircuitBreakerType.DAILY_LOSS,
        ]:
            return abs(current_value) < self.config.threshold * 0.5
        
        elif self.config.breaker_type == CircuitBreakerType.VOLATILITY:
            recent = list(self.state_data.value_history)[-self.config.min_samples:]
            mean = sum(recent) / len(recent)
            std = (sum((v - mean) ** 2 for v in recent) / len(recent)) ** 0.5
            return current_value < mean + std * self.config.threshold * 0.5
        
        # Default: check if value is below threshold
        return current_value < self.config.threshold
    
    # ========================================================================
    # MANUAL OPERATIONS
    # ========================================================================
    
    async def reset(self) -> bool:
        """
        Manually reset the circuit breaker.
        
        Returns:
            bool: True if reset was successful
        """
        async with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            
            if self.state == CircuitBreakerState.PERMANENTLY_OPEN:
                self.logger.warning(f"Cannot reset permanently open circuit breaker {self.name}")
                return False
            
            old_state = self.state_data.state
            self.state_data.state = CircuitBreakerState.CLOSED
            self.state_data.is_triggered = False
            self.state_data.cooldown_until = None
            self.state_data.trips = 0
            
            event = CircuitBreakerEvent(
                breaker_name=self.name,
                breaker_type=self.config.breaker_type,
                state=self.state_data.state,
                severity=self.config.severity,
                message=f"Circuit breaker {self.name} manually reset",
            )
            self._events.append(event)
            
            await self._trigger_reset_callbacks(event)
            if old_state != self.state_data.state:
                await self._trigger_state_change_callbacks(old_state, self.state_data.state)
            
            self.logger.info(f"Circuit breaker {self.name} manually reset")
            return True
    
    async def force_trip(self, reason: str = "Manual trip") -> None:
        """
        Manually trip the circuit breaker.
        
        Args:
            reason: Reason for manual trip
        """
        async with self._lock:
            old_state = self.state_data.state
            self.state_data.state = CircuitBreakerState.OPEN
            self.state_data.is_triggered = True
            self.state_data.last_trip_time = datetime.utcnow()
            
            event = CircuitBreakerEvent(
                breaker_name=self.name,
                breaker_type=self.config.breaker_type,
                state=self.state_data.state,
                severity=CircuitBreakerSeverity.CRITICAL,
                message=f"Circuit breaker {self.name} manually tripped: {reason}",
                metadata={"reason": reason},
            )
            self._events.append(event)
            
            await self._trigger_trip_callbacks(event)
            if old_state != self.state_data.state:
                await self._trigger_state_change_callbacks(old_state, self.state_data.state)
            
            self.logger.warning(f"Circuit breaker {self.name} manually tripped: {reason}")
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    def get_events(self, limit: int = 50) -> List[CircuitBreakerEvent]:
        """
        Get circuit breaker events.
        
        Args:
            limit: Maximum number of events
            
        Returns:
            List[CircuitBreakerEvent]: Events
        """
        return self._events[-limit:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get circuit breaker metrics.
        
        Returns:
            Dict[str, Any]: Metrics
        """
        return {
            "name": self.name,
            "type": self.config.breaker_type.value,
            "severity": self.config.severity.value,
            "state": self.state.value,
            "is_tripped": self.is_tripped,
            "is_allowed": self.is_allowed,
            "trips": self.state_data.trips,
            "current_value": self.state_data.current_value,
            "threshold": self.config.threshold,
            "cooldown_remaining": max(0, (self.state_data.cooldown_until - datetime.utcnow()).total_seconds()) if self.state_data.cooldown_until else 0,
            "event_count": len(self._events),
            "enabled": self.config.enabled,
            "samples": len(self.state_data.value_history),
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get circuit breaker summary.
        
        Returns:
            Dict[str, Any]: Summary
        """
        return {
            "breaker": self.name,
            "state": self.state.value,
            "type": self.config.breaker_type.value,
            "severity": self.config.severity.value,
            "trips": self.state_data.trips,
            "threshold": self.config.threshold,
            "current_value": self.state_data.current_value,
            "last_trip": self.state_data.last_trip_time.isoformat() if self.state_data.last_trip_time else None,
        }


# ============================================================================
# CIRCUIT BREAKER MANAGER
# ============================================================================

class CircuitBreakerManager:
    """
    Manages multiple circuit breakers.
    
    Coordinates multiple circuit breakers for comprehensive risk management.
    """
    
    def __init__(self):
        """Initialize the circuit breaker manager."""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        
        # Global state
        self._global_state = CircuitBreakerState.CLOSED
        self._global_cooldown_until: Optional[datetime] = None
        
        # Events
        self._global_events: List[CircuitBreakerEvent] = []
        
        self.logger = logger
    
    # ========================================================================
    # BREAKER MANAGEMENT
    # ========================================================================
    
    def add_breaker(self, config: CircuitBreakerConfig) -> CircuitBreaker:
        """
        Add a circuit breaker.
        
        Args:
            config: Circuit breaker configuration
            
        Returns:
            CircuitBreaker: Created circuit breaker
        """
        breaker = CircuitBreaker(config)
        name = breaker.name
        
        # Ensure unique name
        if name in self._breakers:
            # Append index
            index = 1
            while f"{name}_{index}" in self._breakers:
                index += 1
            name = f"{name}_{index}"
            breaker.config.name = name
        
        self._breakers[name] = breaker
        
        # Set up callback for global state updates
        async def on_state_change(old_state: CircuitBreakerState, new_state: CircuitBreakerState) -> None:
            if new_state in [CircuitBreakerState.OPEN, CircuitBreakerState.PERMANENTLY_OPEN]:
                await self._update_global_state()
        
        breaker.on_state_change(on_state_change)
        
        self.logger.info(f"Added circuit breaker: {name}")
        return breaker
    
    def get_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """
        Get a circuit breaker by name.
        
        Args:
            name: Breaker name
            
        Returns:
            Optional[CircuitBreaker]: Circuit breaker or None
        """
        return self._breakers.get(name)
    
    def get_breakers_by_type(self, breaker_type: CircuitBreakerType) -> List[CircuitBreaker]:
        """
        Get circuit breakers by type.
        
        Args:
            breaker_type: Breaker type
            
        Returns:
            List[CircuitBreaker]: Matching breakers
        """
        return [b for b in self._breakers.values() if b.config.breaker_type == breaker_type]
    
    def get_all_breakers(self) -> List[CircuitBreaker]:
        """
        Get all circuit breakers.
        
        Returns:
            List[CircuitBreaker]: All breakers
        """
        return list(self._breakers.values())
    
    def remove_breaker(self, name: str) -> bool:
        """
        Remove a circuit breaker.
        
        Args:
            name: Breaker name
            
        Returns:
            bool: True if removed
        """
        if name in self._breakers:
            del self._breakers[name]
            self.logger.info(f"Removed circuit breaker: {name}")
            return True
        return False
    
    # ========================================================================
    # GLOBAL STATE
    # ========================================================================
    
    async def _update_global_state(self) -> None:
        """
        Update global circuit breaker state.
        """
        async with self._lock:
            # Check if any critical breaker is open
            critical_open = any(
                b.is_tripped and b.config.severity == CircuitBreakerSeverity.CRITICAL
                for b in self._breakers.values()
            )
            
            if critical_open:
                self._global_state = CircuitBreakerState.OPEN
                self._global_cooldown_until = datetime.utcnow() + timedelta(minutes=5)
                self.logger.warning("Global circuit breaker opened due to critical trip")
                return
            
            # Check if any severe breaker is open
            severe_open = any(
                b.is_tripped and b.config.severity == CircuitBreakerSeverity.SEVERE
                for b in self._breakers.values()
            )
            
            if severe_open:
                self._global_state = CircuitBreakerState.HALF_OPEN
                self.logger.warning("Global circuit breaker in half-open state")
                return
            
            # All clear
            self._global_state = CircuitBreakerState.CLOSED
            self._global_cooldown_until = None
    
    def is_global_allowed(self) -> bool:
        """
        Check if trading is allowed globally.
        
        Returns:
            bool: True if allowed
        """
        if self._global_state == CircuitBreakerState.OPEN:
            # Check if cooldown has passed
            if self._global_cooldown_until and datetime.utcnow() < self._global_cooldown_until:
                return False
            return True
        
        return self._global_state == CircuitBreakerState.CLOSED
    
    async def check_all(self, value: Optional[float] = None) -> bool:
        """
        Check all circuit breakers.
        
        Args:
            value: Value to check (optional)
            
        Returns:
            bool: True if all breakers allow trading
        """
        if not self.is_global_allowed():
            return False
        
        all_allowed = True
        
        for breaker in self._breakers.values():
            if value is not None and breaker.config.breaker_type in [
                CircuitBreakerType.VOLATILITY,
                CircuitBreakerType.LOSS,
                CircuitBreakerType.DRAWDOWN,
                CircuitBreakerType.DAILY_LOSS,
            ]:
                if not await breaker.update(value):
                    all_allowed = False
            else:
                if not breaker.is_allowed:
                    all_allowed = False
        
        # Update global state
        await self._update_global_state()
        
        return all_allowed and self.is_global_allowed()
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    def get_global_state(self) -> Dict[str, Any]:
        """
        Get global circuit breaker state.
        
        Returns:
            Dict[str, Any]: Global state
        """
        return {
            "state": self._global_state.value,
            "is_allowed": self.is_global_allowed(),
            "cooldown_remaining": max(0, (self._global_cooldown_until - datetime.utcnow()).total_seconds()) if self._global_cooldown_until else 0,
            "breaker_count": len(self._breakers),
            "open_breakers": [b.name for b in self._breakers.values() if b.is_tripped],
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get circuit breaker summary.
        
        Returns:
            Dict[str, Any]: Summary
        """
        return {
            "global": self.get_global_state(),
            "breakers": {
                name: breaker.get_summary()
                for name, breaker in self._breakers.items()
            },
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get circuit breaker metrics.
        
        Returns:
            Dict[str, Any]: Metrics
        """
        return {
            "total_breakers": len(self._breakers),
            "open_breakers": sum(1 for b in self._breakers.values() if b.is_tripped),
            "closed_breakers": sum(1 for b in self._breakers.values() if b.is_allowed),
            "global_state": self._global_state.value,
            "breakers": {
                name: breaker.get_metrics()
                for name, breaker in self._breakers.items()
            },
        }
    
    async def reset_all(self) -> int:
        """
        Reset all circuit breakers.
        
        Returns:
            int: Number of breakers reset
        """
        reset_count = 0
        
        for breaker in self._breakers.values():
            if await breaker.reset():
                reset_count += 1
        
        # Update global state
        await self._update_global_state()
        
        self.logger.info(f"Reset {reset_count} circuit breakers")
        return reset_count
    
    def get_events(self, limit: int = 100) -> List[CircuitBreakerEvent]:
        """
        Get all circuit breaker events.
        
        Args:
            limit: Maximum number of events
            
        Returns:
            List[CircuitBreakerEvent]: Events
        """
        all_events = []
        for breaker in self._breakers.values():
            all_events.extend(breaker.get_events())
        
        all_events.sort(key=lambda x: x.timestamp, reverse=True)
        return all_events[:limit]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "CircuitBreakerState",
    "CircuitBreakerType",
    "CircuitBreakerSeverity",
    
    # Models
    "CircuitBreakerConfig",
    "CircuitBreakerStateData",
    "CircuitBreakerEvent",
    
    # Classes
    "CircuitBreaker",
    "CircuitBreakerManager",
]
