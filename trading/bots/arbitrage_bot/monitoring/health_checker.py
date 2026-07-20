# trading/bots/arbitrage_bot/monitoring/health_checker.py
# NEXUS AI TRADING SYSTEM - HEALTH CHECKER
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive health checking for all system components
# including exchanges, services, connections, and performance metrics.
# ====================================================================================

"""
NEXUS Arbitrage Bot Health Checker

This module provides comprehensive health checking for:
- Exchange connectivity and API status
- Service health and availability
- WebSocket connection status
- Database and cache connectivity
- Performance metrics and thresholds
- System resource utilization
- Network latency and connectivity
- Component dependency health
"""

import asyncio
import logging
import time
import psutil
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler, RetryConfig
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger("nexus.arbitrage.health_checker")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class ComponentType(str, Enum):
    """Types of components to check."""
    EXCHANGE = "exchange"
    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    WEBSOCKET = "websocket"
    NETWORK = "network"
    SYSTEM = "system"
    API = "api"
    QUEUE = "queue"
    WORKER = "worker"


class CheckSeverity(str, Enum):
    """Severity of health check failures."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class HealthCheckConfig:
    """Configuration for a health check."""
    name: str
    component_type: ComponentType
    check_interval: int = 60  # seconds
    timeout: int = 10  # seconds
    retry_count: int = 3
    failure_threshold: int = 3
    severity: CheckSeverity = CheckSeverity.MEDIUM
    enabled: bool = True
    dependencies: List[str] = field(default_factory=list)


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    type: ComponentType
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    duration_ms: float
    error: Optional[str] = None


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component: str
    type: ComponentType
    status: HealthStatus
    last_check: datetime
    last_success: Optional[datetime]
    last_failure: Optional[datetime]
    consecutive_failures: int
    success_rate: float
    latency_p50: float
    latency_p95: float
    details: Dict[str, Any]
    history: List[HealthCheckResult]


@dataclass
class SystemHealth:
    """Overall system health."""
    status: HealthStatus
    components: Dict[str, ComponentHealth]
    timestamp: datetime
    uptime_seconds: float
    summary: Dict[str, Any]


# ====================================================================================
# HEALTH CHECKER
# ====================================================================================

class HealthChecker:
    """
    Comprehensive health checking system.
    
    Features:
    - Component health monitoring
    - Dependency-based checking
    - Automatic retry and recovery
    - Performance metrics collection
    - Health history tracking
    - Alert generation on failures
    - Integration with monitoring systems
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the health checker.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Health checks
        self._checks: Dict[str, HealthCheckConfig] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self._component_health: Dict[str, ComponentHealth] = {}
        
        # Check functions
        self._check_functions: Dict[str, Callable] = {}
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_health_checker",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        self._start_time = datetime.utcnow()
        
        # System metrics
        self._system_metrics: Dict[str, Any] = {}
        
        logger.info("HealthChecker initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_gauge("health_status", "Health status (0=unhealthy, 1=healthy)")
        self._metrics.register_gauge("health_checks_total", "Total health checks")
        self._metrics.register_gauge("health_checks_failed", "Failed health checks")
        self._metrics.register_counter("health_check_success", "Successful health checks")
        self._metrics.register_counter("health_check_failure", "Failed health checks")
        self._metrics.register_histogram("health_check_duration_ms", "Health check duration in milliseconds")
        
    def register_check(
        self,
        config: HealthCheckConfig,
        check_func: Callable
    ) -> None:
        """
        Register a health check.
        
        Args:
            config: Health check configuration
            check_func: Async function to perform the check
        """
        self._checks[config.name] = config
        self._check_functions[config.name] = check_func
        
        # Initialize component health
        self._component_health[config.name] = ComponentHealth(
            component=config.name,
            type=config.component_type,
            status=HealthStatus.UNKNOWN,
            last_check=datetime.utcnow(),
            last_success=None,
            last_failure=None,
            consecutive_failures=0,
            success_rate=100.0,
            latency_p50=0.0,
            latency_p95=0.0,
            details={},
            history=[]
        )
        
        # Initialize circuit breaker
        self._circuit_breakers[config.name] = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            recovery_timeout=60.0,
            half_open_attempts=2
        )
        
        logger.info(f"Registered health check: {config.name}")
        
    async def initialize(self) -> None:
        """Initialize the health checker."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("HealthChecker initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # Health check loop
        task = asyncio.create_task(self._health_check_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics update loop
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _health_check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            try:
                # Get minimum check interval
                min_interval = min(
                    (c.check_interval for c in self._checks.values() if c.enabled),
                    default=60
                )
                
                # Wait for next check
                await asyncio.sleep(min_interval)
                
                # Run all checks
                await self.run_all_checks()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                
    async def _metrics_update_loop(self) -> None:
        """Update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(30)
                
                # Update system metrics
                await self._update_system_metrics()
                
                # Update component metrics
                for name, health in self._component_health.items():
                    status_value = 1 if health.status == HealthStatus.HEALTHY else 0
                    self._metrics.set_gauge(
                        f"component_{name}_status",
                        status_value,
                        labels={"component": name}
                    )
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
                
    async def _update_system_metrics(self) -> None:
        """Update system resource metrics."""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self._system_metrics["cpu_percent"] = cpu_percent
            
            # Memory
            memory = psutil.virtual_memory()
            self._system_metrics["memory_percent"] = memory.percent
            self._system_metrics["memory_used_gb"] = memory.used / (1024 ** 3)
            self._system_metrics["memory_total_gb"] = memory.total / (1024 ** 3)
            
            # Disk
            disk = psutil.disk_usage('/')
            self._system_metrics["disk_percent"] = disk.percent
            self._system_metrics["disk_used_gb"] = disk.used / (1024 ** 3)
            self._system_metrics["disk_total_gb"] = disk.total / (1024 ** 3)
            
            # Network
            net_io = psutil.net_io_counters()
            self._system_metrics["net_bytes_sent_mb"] = net_io.bytes_sent / (1024 ** 2)
            self._system_metrics["net_bytes_recv_mb"] = net_io.bytes_recv / (1024 ** 2)
            
            # Uptime
            self._system_metrics["uptime_seconds"] = (datetime.utcnow() - self._start_time).total_seconds()
            
            # Update metrics
            self._metrics.set_gauge("system_cpu_percent", cpu_percent)
            self._metrics.set_gauge("system_memory_percent", memory.percent)
            self._metrics.set_gauge("system_disk_percent", disk.percent)
            self._metrics.set_gauge("system_uptime_seconds", self._system_metrics["uptime_seconds"])
            
        except Exception as e:
            logger.error(f"System metrics update error: {e}")
            
    async def run_check(self, name: str) -> HealthCheckResult:
        """
        Run a specific health check.
        
        Args:
            name: Name of the health check
            
        Returns:
            Health check result
        """
        if name not in self._checks:
            raise ValueError(f"Health check not found: {name}")
            
        config = self._checks[name]
        check_func = self._check_functions[name]
        
        if not config.enabled:
            return HealthCheckResult(
                component=name,
                type=config.component_type,
                status=HealthStatus.UNKNOWN,
                message="Check disabled",
                details={},
                timestamp=datetime.utcnow(),
                duration_ms=0
            )
            
        # Check circuit breaker
        cb = self._circuit_breakers[name]
        if cb.is_open():
            return HealthCheckResult(
                component=name,
                type=config.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Circuit breaker open - retry after {cb.get_retry_after():.0f}s",
                details={"retry_after": cb.get_retry_after()},
                timestamp=datetime.utcnow(),
                duration_ms=0
            )
            
        # Run check with timeout
        start_time = time.time()
        result = None
        
        try:
            # Run check with retry
            retry_handler = RetryHandler(
                RetryConfig(
                    max_retries=config.retry_count,
                    backoff=1.0
                )
            )
            
            async def _run_check():
                return await check_func()
                
            check_result = await retry_handler.execute(
                _run_check,
                timeout=config.timeout
            )
            
            # Process result
            if check_result.get("status") == "healthy":
                status = HealthStatus.HEALTHY
                message = check_result.get("message", "Healthy")
                cb.record_success()
                self._metrics.increment_counter("health_check_success")
            else:
                status = HealthStatus.UNHEALTHY
                message = check_result.get("message", "Unhealthy")
                cb.record_failure()
                self._metrics.increment_counter("health_check_failure")
                
            result = HealthCheckResult(
                component=name,
                type=config.component_type,
                status=status,
                message=message,
                details=check_result.get("details", {}),
                timestamp=datetime.utcnow(),
                duration_ms=(time.time() - start_time) * 1000
            )
            
        except asyncio.TimeoutError:
            cb.record_failure()
            result = HealthCheckResult(
                component=name,
                type=config.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {config.timeout}s",
                details={"timeout": config.timeout},
                timestamp=datetime.utcnow(),
                duration_ms=(time.time() - start_time) * 1000,
                error="Timeout"
            )
            self._metrics.increment_counter("health_check_failure")
            
        except Exception as e:
            cb.record_failure()
            result = HealthCheckResult(
                component=name,
                type=config.component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                details={},
                timestamp=datetime.utcnow(),
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
            self._metrics.increment_counter("health_check_failure")
            
        # Update component health
        self._update_component_health(name, result)
        
        # Store result
        self._results[name] = result
        
        # Update metrics
        self._metrics.record_histogram("health_check_duration_ms", result.duration_ms)
        
        return result
        
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks.
        
        Returns:
            Dict of results
        """
        results = {}
        
        # Run checks in parallel
        tasks = []
        for name in self._checks:
            if self._checks[name].enabled:
                tasks.append(self.run_check(name))
                
        # Wait for all checks
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for name, result in zip(self._checks, check_results):
            if isinstance(result, Exception):
                logger.error(f"Health check {name} failed: {result}")
                continue
            results[name] = result
            
        return results
        
    def _update_component_health(self, name: str, result: HealthCheckResult) -> None:
        """
        Update component health.
        
        Args:
            name: Component name
            result: Health check result
        """
        health = self._component_health[name]
        
        health.last_check = result.timestamp
        health.details = result.details
        
        # Update status
        if result.status == HealthStatus.HEALTHY:
            health.last_success = result.timestamp
            health.consecutive_failures = 0
        else:
            health.last_failure = result.timestamp
            health.consecutive_failures += 1
            
        # Update success rate
        history_size = len(health.history)
        if history_size > 0:
            successes = sum(1 for h in health.history if h.status == HealthStatus.HEALTHY)
            health.success_rate = (successes / history_size) * 100
            
        # Update latency metrics
        latencies = [h.duration_ms for h in health.history[-100:]]
        if latencies:
            health.latency_p50 = self._percentile(latencies, 50)
            health.latency_p95 = self._percentile(latencies, 95)
            
        # Determine overall status
        if health.consecutive_failures >= self._checks[name].failure_threshold:
            health.status = HealthStatus.UNHEALTHY
        elif health.consecutive_failures > 0:
            health.status = HealthStatus.DEGRADED
        else:
            health.status = HealthStatus.HEALTHY
            
        # Add to history
        health.history.append(result)
        if len(health.history) > 1000:
            health.history = health.history[-1000:]
            
    def _percentile(self, values: List[float], percentile: float) -> float:
        """
        Calculate percentile.
        
        Args:
            values: List of values
            percentile: Percentile (0-100)
            
        Returns:
            Percentile value
        """
        if not values:
            return 0.0
            
        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        
        if index == int(index):
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            fraction = index - int(index)
            return lower + (upper - lower) * fraction
            
    def get_component_health(self, name: str) -> Optional[ComponentHealth]:
        """
        Get health of a specific component.
        
        Args:
            name: Component name
            
        Returns:
            Component health
        """
        return self._component_health.get(name)
        
    def get_system_health(self) -> SystemHealth:
        """
        Get overall system health.
        
        Returns:
            System health
        """
        # Determine overall status
        statuses = [h.status for h in self._component_health.values()]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif HealthStatus.UNKNOWN in statuses:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY
            
        return SystemHealth(
            status=overall,
            components=self._component_health.copy(),
            timestamp=datetime.utcnow(),
            uptime_seconds=(datetime.utcnow() - self._start_time).total_seconds(),
            summary=self._get_system_summary()
        )
        
    def _get_system_summary(self) -> Dict[str, Any]:
        """
        Get system summary.
        
        Returns:
            System summary
        """
        summary = {
            "total_checks": len(self._checks),
            "enabled_checks": sum(1 for c in self._checks.values() if c.enabled),
            "healthy_components": sum(1 for h in self._component_health.values() if h.status == HealthStatus.HEALTHY),
            "degraded_components": sum(1 for h in self._component_health.values() if h.status == HealthStatus.DEGRADED),
            "unhealthy_components": sum(1 for h in self._component_health.values() if h.status == HealthStatus.UNHEALTHY),
            "unknown_components": sum(1 for h in self._component_health.values() if h.status == HealthStatus.UNKNOWN),
            "system_metrics": self._system_metrics
        }
        
        # By component type
        by_type = defaultdict(lambda: {"healthy": 0, "degraded": 0, "unhealthy": 0, "unknown": 0})
        for health in self._component_health.values():
            by_type[health.type.value][health.status.value] += 1
        summary["by_type"] = dict(by_type)
        
        return summary
        
    async def is_component_healthy(self, name: str) -> bool:
        """
        Check if a component is healthy.
        
        Args:
            name: Component name
            
        Returns:
            True if healthy
        """
        health = self._component_health.get(name)
        if not health:
            return False
            
        if health.status == HealthStatus.HEALTHY:
            return True
            
        # Check if check is due
        config = self._checks.get(name)
        if config and config.enabled:
            time_since_check = (datetime.utcnow() - health.last_check).total_seconds()
            if time_since_check > config.check_interval * 2:
                # Run check
                await self.run_check(name)
                health = self._component_health.get(name)
                
        return health.status == HealthStatus.HEALTHY
        
    async def wait_for_healthy(
        self,
        name: str,
        timeout: float = 30.0,
        interval: float = 1.0
    ) -> bool:
        """
        Wait for a component to become healthy.
        
        Args:
            name: Component name
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds
            
        Returns:
            True if healthy within timeout
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.is_component_healthy(name):
                return True
            await asyncio.sleep(interval)
        return False
        
    async def close(self) -> None:
        """Close the health checker."""
        self._running = False
        self._initialized = False
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        logger.info("HealthChecker closed")


# ====================================================================================
# FACTORY FUNCTIONS
# ====================================================================================

def create_exchange_health_check(
    exchange_name: str,
    check_func: Callable,
    interval: int = 60
) -> HealthCheckConfig:
    """
    Create an exchange health check configuration.
    
    Args:
        exchange_name: Name of the exchange
        check_func: Health check function
        interval: Check interval in seconds
        
    Returns:
        Health check configuration
    """
    return HealthCheckConfig(
        name=f"exchange_{exchange_name}",
        component_type=ComponentType.EXCHANGE,
        check_interval=interval,
        timeout=15,
        retry_count=3,
        failure_threshold=3,
        severity=CheckSeverity.HIGH
    )


def create_service_health_check(
    service_name: str,
    check_func: Callable,
    interval: int = 30
) -> HealthCheckConfig:
    """
    Create a service health check configuration.
    
    Args:
        service_name: Name of the service
        check_func: Health check function
        interval: Check interval in seconds
        
    Returns:
        Health check configuration
    """
    return HealthCheckConfig(
        name=f"service_{service_name}",
        component_type=ComponentType.SERVICE,
        check_interval=interval,
        timeout=10,
        retry_count=3,
        failure_threshold=3,
        severity=CheckSeverity.CRITICAL
    )


def create_database_health_check(
    db_name: str,
    check_func: Callable,
    interval: int = 30
) -> HealthCheckConfig:
    """
    Create a database health check configuration.
    
    Args:
        db_name: Name of the database
        check_func: Health check function
        interval: Check interval in seconds
        
    Returns:
        Health check configuration
    """
    return HealthCheckConfig(
        name=f"database_{db_name}",
        component_type=ComponentType.DATABASE,
        check_interval=interval,
        timeout=5,
        retry_count=2,
        failure_threshold=2,
        severity=CheckSeverity.CRITICAL
    )


def create_websocket_health_check(
    ws_name: str,
    check_func: Callable,
    interval: int = 30
) -> HealthCheckConfig:
    """
    Create a WebSocket health check configuration.
    
    Args:
        ws_name: Name of the WebSocket
        check_func: Health check function
        interval: Check interval in seconds
        
    Returns:
        Health check configuration
    """
    return HealthCheckConfig(
        name=f"websocket_{ws_name}",
        component_type=ComponentType.WEBSOCKET,
        check_interval=interval,
        timeout=5,
        retry_count=2,
        failure_threshold=2,
        severity=CheckSeverity.HIGH
    )


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """
    Get the global health checker instance.
    
    Returns:
        HealthChecker instance
    """
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


def reset_health_checker() -> None:
    """Reset the global health checker instance."""
    global _global_health_checker
    if _global_health_checker:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_health_checker.close())
            else:
                asyncio.run(_global_health_checker.close())
        except Exception:
            pass
    _global_health_checker = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'HealthStatus',
    'ComponentType',
    'CheckSeverity',
    
    # Data Models
    'HealthCheckConfig',
    'HealthCheckResult',
    'ComponentHealth',
    'SystemHealth',
    
    # Main Class
    'HealthChecker',
    'get_health_checker',
    'reset_health_checker',
    
    # Factory Functions
    'create_exchange_health_check',
    'create_service_health_check',
    'create_database_health_check',
    'create_websocket_health_check',
]
