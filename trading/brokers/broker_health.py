# trading/brokers/broker_health.py
"""
NEXUS AI TRADING SYSTEM - Broker Health Monitoring
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides health monitoring capabilities for broker connections.
It includes health checks, anomaly detection, performance monitoring,
and alerting for broker-related issues.
"""

import asyncio
import time
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Awaitable
from collections import deque

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from .base import BaseBroker, BrokerException, BrokerConnectionError

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class HealthStatus(str, Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    OFFLINE = "offline"


class HealthCheckType(str, Enum):
    """Types of health checks"""
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    MARKET_DATA = "market_data"
    ORDER_PLACEMENT = "order_placement"
    ACCOUNT_INFO = "account_info"
    LATENCY = "latency"
    RATE_LIMIT = "rate_limit"
    WEBSOCKET = "websocket"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    check_type: HealthCheckType
    status: HealthStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "check_type": self.check_type.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "error": self.error,
            "details": self.details,
        }


@dataclass
class BrokerHealthReport:
    """Comprehensive health report for a broker"""
    broker_name: str
    broker_id: str
    overall_status: HealthStatus
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checks: List[HealthCheckResult] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "broker_name": self.broker_name,
            "broker_id": self.broker_id,
            "overall_status": self.overall_status.value,
            "timestamp": self.timestamp.isoformat(),
            "checks": [c.to_dict() for c in self.checks],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for a broker"""
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    request_count: int = 0
    error_count: int = 0
    error_rate: float = 0.0
    throughput_per_second: float = 0.0
    uptime_percentage: float = 100.0
    last_check: Optional[datetime] = None


# ============================================================================
# HEALTH CHECKER
# ============================================================================

class BrokerHealthChecker:
    """
    Performs health checks on broker connections.
    
    Features:
    - Multiple health check types
    - Configurable check intervals
    - Asynchronous health checks
    - Detailed health reports
    - History tracking
    """
    
    def __init__(
        self,
        broker: BaseBroker,
        broker_id: str = "",
        check_interval: int = 30,
        history_size: int = 100,
    ):
        """
        Initialize the health checker.
        
        Args:
            broker: Broker instance to monitor
            broker_id: Broker identifier
            check_interval: Interval between checks in seconds
            history_size: Number of checks to keep in history
        """
        self.broker = broker
        self.broker_id = broker_id or getattr(broker, "connection_id", "unknown")
        self.broker_name = broker.name.value if broker.name else "unknown"
        self.check_interval = check_interval
        self.history_size = history_size
        
        self._history: deque = deque(maxlen=history_size)
        self._current_status = HealthStatus.UNKNOWN
        self._last_check: Optional[datetime] = None
        self._is_running = False
        self._check_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # Performance tracking
        self._latency_samples: deque = deque(maxlen=1000)
        self._request_timestamps: deque = deque(maxlen=1000)
        self._error_timestamps: deque = deque(maxlen=1000)
        self._start_time = time.time()
        
        # Callbacks
        self._on_status_change: List[Callable[[HealthStatus, HealthStatus], Awaitable[None]]] = []
        self._on_check_complete: List[Callable[[HealthCheckResult], Awaitable[None]]] = []
        
        self.logger = logger
    
    @property
    def current_status(self) -> HealthStatus:
        """Get current health status"""
        return self._current_status
    
    @property
    def is_running(self) -> bool:
        """Check if health checks are running"""
        return self._is_running
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_status_change(
        self,
        callback: Callable[[HealthStatus, HealthStatus], Awaitable[None]],
    ) -> None:
        """
        Register callback for status changes.
        
        Args:
            callback: Async callback receiving (old_status, new_status)
        """
        self._on_status_change.append(callback)
    
    def on_check_complete(
        self,
        callback: Callable[[HealthCheckResult], Awaitable[None]],
    ) -> None:
        """
        Register callback for check completion.
        
        Args:
            callback: Async callback receiving the check result
        """
        self._on_check_complete.append(callback)
    
    async def _trigger_status_change(
        self,
        old_status: HealthStatus,
        new_status: HealthStatus,
    ) -> None:
        """Trigger status change callbacks"""
        for callback in self._on_status_change:
            try:
                await callback(old_status, new_status)
            except Exception as e:
                self.logger.error(f"Error in status change callback: {e}")
    
    async def _trigger_check_complete(self, result: HealthCheckResult) -> None:
        """Trigger check complete callbacks"""
        for callback in self._on_check_complete:
            try:
                await callback(result)
            except Exception as e:
                self.logger.error(f"Error in check complete callback: {e}")
    
    # ========================================================================
    # HEALTH CHECKS
    # ========================================================================
    
    async def perform_check(self) -> HealthCheckResult:
        """
        Perform a comprehensive health check.
        
        Returns:
            HealthCheckResult: Combined health check result
        """
        start_time = time.time()
        checks = []
        statuses = []
        
        # Perform individual checks
        check_methods = [
            self._check_connection,
            self._check_authentication,
            self._check_account_info,
            self._check_market_data,
            self._check_latency,
        ]
        
        for method in check_methods:
            try:
                result = await method()
                checks.append(result)
                statuses.append(result.status)
            except Exception as e:
                self.logger.error(f"Error in health check {method.__name__}: {e}")
                checks.append(HealthCheckResult(
                    check_type=HealthCheckType.CONNECTION,
                    status=HealthStatus.UNHEALTHY,
                    error=str(e),
                ))
                statuses.append(HealthStatus.UNHEALTHY)
        
        # Determine overall status
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        elif HealthStatus.OFFLINE in statuses:
            overall = HealthStatus.OFFLINE
        else:
            overall = HealthStatus.HEALTHY
        
        # Calculate metrics
        latency_ms = (time.time() - start_time) * 1000
        self._latency_samples.append(latency_ms)
        
        # Update current status
        old_status = self._current_status
        self._current_status = overall
        self._last_check = datetime.utcnow()
        
        # Create result
        result = HealthCheckResult(
            check_type=HealthCheckType.CONNECTION,
            status=overall,
            latency_ms=latency_ms,
            details={
                "checks": [c.to_dict() for c in checks],
                "broker_connected": self.broker.is_connected,
                "broker_sandbox": self.broker.is_sandbox,
            },
        )
        
        # Store in history
        self._history.append(result)
        
        # Trigger callbacks
        if old_status != overall:
            await self._trigger_status_change(old_status, overall)
        await self._trigger_check_complete(result)
        
        return result
    
    async def _check_connection(self) -> HealthCheckResult:
        """Check broker connection"""
        start = time.time()
        try:
            connected = self.broker.is_connected
            latency = (time.time() - start) * 1000
            
            if connected:
                return HealthCheckResult(
                    check_type=HealthCheckType.CONNECTION,
                    status=HealthStatus.HEALTHY,
                    latency_ms=latency,
                    details={"connected": True},
                )
            else:
                # Try to reconnect
                try:
                    connected = await self.broker.connect()
                    if connected:
                        return HealthCheckResult(
                            check_type=HealthCheckType.CONNECTION,
                            status=HealthStatus.DEGRADED,
                            latency_ms=(time.time() - start) * 1000,
                            details={"connected": True, "reconnected": True},
                        )
                    else:
                        return HealthCheckResult(
                            check_type=HealthCheckType.CONNECTION,
                            status=HealthStatus.OFFLINE,
                            latency_ms=(time.time() - start) * 1000,
                            error="Failed to reconnect",
                        )
                except Exception as e:
                    return HealthCheckResult(
                        check_type=HealthCheckType.CONNECTION,
                        status=HealthStatus.OFFLINE,
                        latency_ms=(time.time() - start) * 1000,
                        error=str(e),
                    )
                    
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.CONNECTION,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    
    async def _check_authentication(self) -> HealthCheckResult:
        """Check authentication"""
        start = time.time()
        try:
            # Try to get account info as authentication test
            if self.broker.is_connected:
                # Use existing connection
                try:
                    account_info = await self.broker.get_account_info()
                    if account_info:
                        return HealthCheckResult(
                            check_type=HealthCheckType.AUTHENTICATION,
                            status=HealthStatus.HEALTHY,
                            latency_ms=(time.time() - start) * 1000,
                            details={"authenticated": True},
                        )
                except BrokerException as e:
                    if "authentication" in str(e).lower() or "auth" in str(e).lower():
                        return HealthCheckResult(
                            check_type=HealthCheckType.AUTHENTICATION,
                            status=HealthStatus.UNHEALTHY,
                            latency_ms=(time.time() - start) * 1000,
                            error=f"Authentication failed: {e}",
                        )
                    raise
            
            return HealthCheckResult(
                check_type=HealthCheckType.AUTHENTICATION,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                details={"authenticated": False, "not_connected": True},
            )
            
        except Exception as e:
            if "auth" in str(e).lower() or "key" in str(e).lower():
                return HealthCheckResult(
                    check_type=HealthCheckType.AUTHENTICATION,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=(time.time() - start) * 1000,
                    error=f"Authentication error: {e}",
                )
            return HealthCheckResult(
                check_type=HealthCheckType.AUTHENTICATION,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    
    async def _check_account_info(self) -> HealthCheckResult:
        """Check account info"""
        start = time.time()
        try:
            if not self.broker.is_connected:
                return HealthCheckResult(
                    check_type=HealthCheckType.ACCOUNT_INFO,
                    status=HealthStatus.DEGRADED,
                    latency_ms=(time.time() - start) * 1000,
                    error="Not connected",
                )
            
            account_info = await self.broker.get_account_info()
            
            # Check account health indicators
            warnings = []
            if account_info.equity < 100:
                warnings.append("Low account balance")
            if account_info.margin_used / (account_info.equity + 0.01) > 0.8:
                warnings.append("High margin usage")
            
            status = HealthStatus.HEALTHY
            if warnings:
                status = HealthStatus.DEGRADED
            
            return HealthCheckResult(
                check_type=HealthCheckType.ACCOUNT_INFO,
                status=status,
                latency_ms=(time.time() - start) * 1000,
                details={
                    "account_id": account_info.account_id,
                    "equity": float(account_info.equity),
                    "buying_power": float(account_info.buying_power),
                    "margin_used": float(account_info.margin_used),
                    "open_positions": account_info.open_positions_count,
                    "open_orders": account_info.open_orders_count,
                    "warnings": warnings,
                },
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.ACCOUNT_INFO,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    
    async def _check_market_data(self) -> HealthCheckResult:
        """Check market data availability"""
        start = time.time()
        try:
            if not self.broker.is_connected:
                return HealthCheckResult(
                    check_type=HealthCheckType.MARKET_DATA,
                    status=HealthStatus.DEGRADED,
                    latency_ms=(time.time() - start) * 1000,
                    error="Not connected",
                )
            
            # Try to get market data for a common symbol
            test_symbols = ["BTC/USD", "ETH/USD", "AAPL", "EUR/USD"]
            for symbol in test_symbols:
                try:
                    data = await self.broker.get_market_data(symbol)
                    if data:
                        return HealthCheckResult(
                            check_type=HealthCheckType.MARKET_DATA,
                            status=HealthStatus.HEALTHY,
                            latency_ms=(time.time() - start) * 1000,
                            details={
                                "symbol": symbol,
                                "bid": float(data.bid),
                                "ask": float(data.ask),
                                "last": float(data.last),
                            },
                        )
                except Exception:
                    continue
            
            return HealthCheckResult(
                check_type=HealthCheckType.MARKET_DATA,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                error="No market data available for test symbols",
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.MARKET_DATA,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    
    async def _check_latency(self) -> HealthCheckResult:
        """Check request latency"""
        start = time.time()
        try:
            if not self.broker.is_connected:
                return HealthCheckResult(
                    check_type=HealthCheckType.LATENCY,
                    status=HealthStatus.DEGRADED,
                    latency_ms=(time.time() - start) * 1000,
                    error="Not connected",
                )
            
            # Calculate latency metrics
            if self._latency_samples:
                avg_latency = sum(self._latency_samples) / len(self._latency_samples)
                p95 = self._calculate_percentile(list(self._latency_samples), 95)
                p99 = self._calculate_percentile(list(self._latency_samples), 99)
                
                # Determine status based on latency
                if avg_latency < 100:
                    status = HealthStatus.HEALTHY
                elif avg_latency < 500:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.UNHEALTHY
                
                return HealthCheckResult(
                    check_type=HealthCheckType.LATENCY,
                    status=status,
                    latency_ms=(time.time() - start) * 1000,
                    details={
                        "avg_latency_ms": avg_latency,
                        "p95_latency_ms": p95,
                        "p99_latency_ms": p99,
                        "samples": len(self._latency_samples),
                    },
                )
            
            return HealthCheckResult(
                check_type=HealthCheckType.LATENCY,
                status=HealthStatus.HEALTHY,
                latency_ms=0,
                details={"no_samples": True},
            )
            
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.LATENCY,
                status=HealthStatus.DEGRADED,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
            )
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of a list of values"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(math.ceil((percentile / 100.0) * len(sorted_values))) - 1
        return sorted_values[max(0, min(index, len(sorted_values) - 1))]
    
    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """
        Get performance metrics.
        
        Returns:
            PerformanceMetrics: Performance metrics
        """
        if not self._latency_samples:
            return PerformanceMetrics()
        
        latency_list = list(self._latency_samples)
        now = time.time()
        
        # Count requests in the last minute
        minute_ago = now - 60
        recent_requests = sum(1 for t in self._request_timestamps if t > minute_ago)
        recent_errors = sum(1 for t in self._error_timestamps if t > minute_ago)
        
        error_rate = recent_errors / (recent_requests + 1) * 100
        
        return PerformanceMetrics(
            avg_latency_ms=sum(latency_list) / len(latency_list),
            max_latency_ms=max(latency_list),
            min_latency_ms=min(latency_list),
            p95_latency_ms=self._calculate_percentile(latency_list, 95),
            p99_latency_ms=self._calculate_percentile(latency_list, 99),
            request_count=len(self._request_timestamps),
            error_count=len(self._error_timestamps),
            error_rate=error_rate,
            throughput_per_second=recent_requests / 60 if recent_requests > 0 else 0,
            uptime_percentage=(
                (time.time() - self._start_time - self._get_downtime()) /
                (time.time() - self._start_time) * 100
            ) if time.time() - self._start_time > 0 else 100,
            last_check=self._last_check,
        )
    
    def _get_downtime(self) -> float:
        """Calculate total downtime"""
        # Simplified: count offline periods from history
        downtime = 0.0
        offline_start = None
        
        for check in reversed(list(self._history)):
            if check.status in (HealthStatus.OFFLINE, HealthStatus.UNHEALTHY):
                if offline_start is None:
                    offline_start = check.timestamp
            else:
                if offline_start is not None:
                    downtime += (check.timestamp - offline_start).total_seconds()
                    offline_start = None
        
        if offline_start is not None:
            downtime += (datetime.utcnow() - offline_start).total_seconds()
        
        return downtime
    
    # ========================================================================
    # RUNNING CHECKS
    # ========================================================================
    
    async def start(self) -> None:
        """Start periodic health checks."""
        if self._is_running:
            return
        
        self._is_running = True
        self._check_task = asyncio.create_task(self._check_loop())
        self.logger.info(f"Started health checks for {self.broker_name} (interval={self.check_interval}s)")
    
    async def stop(self) -> None:
        """Stop periodic health checks."""
        if not self._is_running:
            return
        
        self._is_running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
            self._check_task = None
        
        self.logger.info(f"Stopped health checks for {self.broker_name}")
    
    async def _check_loop(self) -> None:
        """Health check loop."""
        while self._is_running:
            try:
                await self.perform_check()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    # ========================================================================
    # REPORTING
    # ========================================================================
    
    async def get_report(self) -> BrokerHealthReport:
        """
        Get a comprehensive health report.
        
        Returns:
            BrokerHealthReport: Health report
        """
        # Perform a fresh check
        await self.perform_check()
        
        # Get performance metrics
        perf_metrics = self.get_performance_metrics()
        
        # Generate recommendations
        recommendations = []
        warnings = []
        
        if perf_metrics.error_rate > 10:
            warnings.append(f"High error rate: {perf_metrics.error_rate:.1f}%")
            recommendations.append("Check broker API credentials and network connectivity")
        
        if perf_metrics.avg_latency_ms > 500:
            warnings.append(f"High average latency: {perf_metrics.avg_latency_ms:.0f}ms")
            recommendations.append("Consider using a closer region or upgrading connection")
        
        if self._current_status == HealthStatus.OFFLINE:
            warnings.append("Broker is offline")
            recommendations.append("Check broker connectivity and credentials")
        
        if self._current_status == HealthStatus.DEGRADED:
            warnings.append("Broker is degraded")
            recommendations.append("Review recent error logs and connection status")
        
        return BrokerHealthReport(
            broker_name=self.broker_name,
            broker_id=self.broker_id,
            overall_status=self._current_status,
            checks=list(self._history) if self._history else [],
            metrics={
                "latency": {
                    "avg_ms": perf_metrics.avg_latency_ms,
                    "max_ms": perf_metrics.max_latency_ms,
                    "p95_ms": perf_metrics.p95_latency_ms,
                    "p99_ms": perf_metrics.p99_latency_ms,
                },
                "requests": {
                    "total": perf_metrics.request_count,
                    "errors": perf_metrics.error_count,
                    "error_rate": perf_metrics.error_rate,
                    "throughput_per_second": perf_metrics.throughput_per_second,
                },
                "uptime": {
                    "percentage": perf_metrics.uptime_percentage,
                    "start_time": self._start_time,
                },
                "current_status": self._current_status.value,
                "last_check": self._last_check.isoformat() if self._last_check else None,
            },
            recommendations=recommendations,
            warnings=warnings,
        )
    
    def get_history(self, count: Optional[int] = None) -> List[HealthCheckResult]:
        """
        Get health check history.
        
        Args:
            count: Number of checks to return (all if None)
            
        Returns:
            List[HealthCheckResult]: Health check history
        """
        history = list(self._history)
        if count is not None:
            history = history[-count:]
        return history


# ============================================================================
# HEALTH MONITOR
# ============================================================================

class BrokerHealthMonitor:
    """
    Centralized health monitor for multiple brokers.
    
    Manages health checkers for multiple broker instances and provides
    aggregated health reporting and monitoring.
    """
    
    def __init__(self):
        """Initialize the health monitor."""
        self._checkers: Dict[str, BrokerHealthChecker] = {}
        self._lock = asyncio.Lock()
        self._alert_callback: Optional[Callable[[str, HealthStatus, HealthStatus], Awaitable[None]]] = None
        self.logger = logger
    
    def register_broker(
        self,
        broker: BaseBroker,
        broker_id: Optional[str] = None,
        check_interval: int = 30,
    ) -> BrokerHealthChecker:
        """
        Register a broker for health monitoring.
        
        Args:
            broker: Broker instance
            broker_id: Optional broker identifier
            check_interval: Health check interval in seconds
            
        Returns:
            BrokerHealthChecker: Health checker for the broker
        """
        broker_id = broker_id or getattr(broker, "connection_id", f"broker_{len(self._checkers)}")
        
        checker = BrokerHealthChecker(
            broker=broker,
            broker_id=broker_id,
            check_interval=check_interval,
        )
        
        # Set up status change callback for alerts
        async def on_status_change(old_status: HealthStatus, new_status: HealthStatus) -> None:
            if self._alert_callback:
                try:
                    await self._alert_callback(broker_id, old_status, new_status)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
        
        checker.on_status_change(on_status_change)
        
        self._checkers[broker_id] = checker
        self.logger.info(f"Registered broker {broker_id} for health monitoring")
        return checker
    
    def unregister_broker(self, broker_id: str) -> bool:
        """
        Unregister a broker from health monitoring.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            bool: True if broker was unregistered
        """
        if broker_id in self._checkers:
            checker = self._checkers[broker_id]
            asyncio.create_task(checker.stop())
            del self._checkers[broker_id]
            self.logger.info(f"Unregistered broker {broker_id}")
            return True
        return False
    
    def get_checker(self, broker_id: str) -> Optional[BrokerHealthChecker]:
        """
        Get the health checker for a broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Optional[BrokerHealthChecker]: Health checker or None
        """
        return self._checkers.get(broker_id)
    
    async def start_all(self) -> None:
        """Start health checks for all registered brokers."""
        for checker in self._checkers.values():
            await checker.start()
        self.logger.info(f"Started health checks for {len(self._checkers)} brokers")
    
    async def stop_all(self) -> None:
        """Stop health checks for all registered brokers."""
        for checker in self._checkers.values():
            await checker.stop()
        self.logger.info(f"Stopped health checks for {len(self._checkers)} brokers")
    
    def set_alert_callback(
        self,
        callback: Callable[[str, HealthStatus, HealthStatus], Awaitable[None]],
    ) -> None:
        """
        Set callback for broker status changes.
        
        Args:
            callback: Async callback receiving (broker_id, old_status, new_status)
        """
        self._alert_callback = callback
    
    async def get_all_reports(self) -> Dict[str, BrokerHealthReport]:
        """
        Get health reports for all registered brokers.
        
        Returns:
            Dict[str, BrokerHealthReport]: Reports by broker ID
        """
        reports = {}
        for broker_id, checker in self._checkers.items():
            try:
                reports[broker_id] = await checker.get_report()
            except Exception as e:
                self.logger.error(f"Error getting report for {broker_id}: {e}")
        return reports
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all broker health statuses.
        
        Returns:
            Dict: Health summary
        """
        summary = {
            "total_brokers": len(self._checkers),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "offline": 0,
            "unknown": 0,
            "brokers": {},
        }
        
        for broker_id, checker in self._checkers.items():
            status = checker.current_status
            summary["brokers"][broker_id] = {
                "status": status.value,
                "last_check": checker._last_check.isoformat() if checker._last_check else None,
            }
            
            if status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif status == HealthStatus.DEGRADED:
                summary["degraded"] += 1
            elif status == HealthStatus.UNHEALTHY:
                summary["unhealthy"] += 1
            elif status == HealthStatus.OFFLINE:
                summary["offline"] += 1
            else:
                summary["unknown"] += 1
        
        return summary


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "HealthStatus",
    "HealthCheckType",
    
    # Models
    "HealthCheckResult",
    "BrokerHealthReport",
    "PerformanceMetrics",
    
    # Classes
    "BrokerHealthChecker",
    "BrokerHealthMonitor",
]
