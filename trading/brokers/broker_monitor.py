# trading/brokers/broker_monitor.py
"""
NEXUS AI TRADING SYSTEM - Broker Monitor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides real-time monitoring capabilities for broker connections.
It tracks broker health, performance, and operational status with alerting
and visualization capabilities.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable, Awaitable
from collections import deque, defaultdict

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from .base import BaseBroker, BrokerException
from .broker_health import HealthStatus, BrokerHealthChecker
from .broker_metrics import BrokerMetricsCollector, BrokerMetricsSnapshot
from .broker_connection import ConnectionState

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(str, Enum):
    """Alert categories"""
    CONNECTION = "connection"
    HEALTH = "health"
    PERFORMANCE = "performance"
    RATE_LIMIT = "rate_limit"
    ORDER = "order"
    ACCOUNT = "account"
    SYSTEM = "system"


@dataclass
class Alert:
    """Alert definition"""
    id: str
    broker_id: str
    severity: AlertSeverity
    category: AlertCategory
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "broker_id": self.broker_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass
class BrokerStatus:
    """Current status of a broker"""
    broker_id: str
    broker_name: str
    is_connected: bool
    connection_state: ConnectionState
    health_status: HealthStatus
    last_health_check: Optional[datetime]
    uptime_seconds: float
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    open_positions: int
    open_orders: int
    balance: float
    equity: float
    last_activity: Optional[datetime]
    alerts: List[Alert] = field(default_factory=list)


# ============================================================================
# BROKER MONITOR
# ============================================================================

class BrokerMonitor:
    """
    Real-time monitor for broker connections.
    
    Features:
    - Real-time status monitoring
    - Alert generation and management
    - Performance tracking
    - Event streaming
    - Historical data retention
    """
    
    def __init__(
        self,
        max_alerts: int = 1000,
        alert_cooldown: int = 60,
        history_retention: int = 3600,
    ):
        """
        Initialize the broker monitor.
        
        Args:
            max_alerts: Maximum number of alerts to store
            alert_cooldown: Cooldown period for duplicate alerts in seconds
            history_retention: Retention period for history in seconds
        """
        self.max_alerts = max_alerts
        self.alert_cooldown = alert_cooldown
        self.history_retention = history_retention
        
        self._brokers: Dict[str, Dict[str, Any]] = {}
        self._alerts: List[Alert] = []
        self._alert_cache: Dict[str, float] = {}  # alert_key -> last_trigger_time
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._status_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        self._lock = asyncio.Lock()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self._on_alert: List[Callable[[Alert], Awaitable[None]]] = []
        self._on_status_change: List[Callable[[str, Dict[str, Any]], Awaitable[None]]] = []
        
        self.logger = logger
    
    # ========================================================================
    # CALLBACK MANAGEMENT
    # ========================================================================
    
    def on_alert(self, callback: Callable[[Alert], Awaitable[None]]) -> None:
        """Register callback for alerts"""
        self._on_alert.append(callback)
    
    def on_status_change(self, callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Register callback for status changes"""
        self._on_status_change.append(callback)
    
    async def _trigger_alert(self, alert: Alert) -> None:
        """Trigger alert callbacks"""
        for callback in self._on_alert:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {e}")
    
    async def _trigger_status_change(self, broker_id: str, status: Dict[str, Any]) -> None:
        """Trigger status change callbacks"""
        for callback in self._on_status_change:
            try:
                await callback(broker_id, status)
            except Exception as e:
                self.logger.error(f"Error in status change callback: {e}")
    
    # ========================================================================
    # BROKER REGISTRATION
    # ========================================================================
    
    async def register_broker(
        self,
        broker_id: str,
        broker_name: str,
        health_checker: BrokerHealthChecker,
        metrics_collector: BrokerMetricsCollector,
        is_connected: bool = False,
    ) -> None:
        """
        Register a broker for monitoring.
        
        Args:
            broker_id: Broker identifier
            broker_name: Broker name
            health_checker: Health checker instance
            metrics_collector: Metrics collector instance
            is_connected: Whether the broker is currently connected
        """
        async with self._lock:
            self._brokers[broker_id] = {
                "broker_id": broker_id,
                "broker_name": broker_name,
                "health_checker": health_checker,
                "metrics_collector": metrics_collector,
                "is_connected": is_connected,
                "registered_at": datetime.utcnow(),
                "last_status": None,
                "status_history": [],
            }
            
            # Start monitoring if not already running
            if not self._running:
                await self.start()
            
            self.logger.info(f"Registered broker {broker_id} for monitoring")
    
    async def unregister_broker(self, broker_id: str) -> bool:
        """
        Unregister a broker from monitoring.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            bool: True if broker was unregistered
        """
        async with self._lock:
            if broker_id in self._brokers:
                del self._brokers[broker_id]
                self.logger.info(f"Unregistered broker {broker_id}")
                return True
            return False
    
    # ========================================================================
    # ALERT MANAGEMENT
    # ========================================================================
    
    async def alert(
        self,
        broker_id: str,
        severity: AlertSeverity,
        category: AlertCategory,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """
        Generate an alert.
        
        Args:
            broker_id: Broker identifier
            severity: Alert severity
            category: Alert category
            message: Alert message
            details: Additional details
            
        Returns:
            Optional[Alert]: Generated alert or None if suppressed
        """
        async with self._lock:
            # Check cooldown for duplicate alerts
            alert_key = f"{broker_id}:{category}:{message[:50]}"
            now = time.time()
            
            if alert_key in self._alert_cache:
                if now - self._alert_cache[alert_key] < self.alert_cooldown:
                    return None
            
            self._alert_cache[alert_key] = now
            
            # Create alert
            alert = Alert(
                id=f"alert_{int(now)}_{len(self._alerts)}",
                broker_id=broker_id,
                severity=severity,
                category=category,
                message=message,
                details=details or {},
            )
            
            self._alerts.append(alert)
            
            # Trim alerts if too many
            if len(self._alerts) > self.max_alerts:
                self._alerts = self._alerts[-self.max_alerts:]
            
            # Trigger callbacks
            await self._trigger_alert(alert)
            
            self.logger.warning(
                f"Alert [{severity.value}] {broker_id}: {message}"
            )
            
            return alert
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as resolved.
        
        Args:
            alert_id: Alert identifier
            
        Returns:
            bool: True if alert was resolved
        """
        async with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.utcnow()
                    return True
            return False
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert identifier
            
        Returns:
            bool: True if alert was acknowledged
        """
        async with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id and not alert.acknowledged:
                    alert.acknowledged = True
                    return True
            return False
    
    def get_alerts(
        self,
        broker_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Alert]:
        """
        Get alerts matching filters.
        
        Args:
            broker_id: Optional broker ID filter
            severity: Optional severity filter
            category: Optional category filter
            resolved: Optional resolved status filter
            limit: Maximum number of alerts to return
            
        Returns:
            List[Alert]: Matching alerts
        """
        alerts = self._alerts[-limit:] if limit > 0 else self._alerts
        
        if broker_id:
            alerts = [a for a in alerts if a.broker_id == broker_id]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        return alerts[-limit:] if limit > 0 else alerts
    
    # ========================================================================
    # STATUS COLLECTION
    # ========================================================================
    
    async def get_status(self, broker_id: Optional[str] = None) -> Dict[str, BrokerStatus]:
        """
        Get current status for brokers.
        
        Args:
            broker_id: Optional specific broker ID
            
        Returns:
            Dict[str, BrokerStatus]: Status by broker ID
        """
        async with self._lock:
            result = {}
            
            if broker_id:
                brokers = {broker_id: self._brokers.get(broker_id)}
                if not brokers[broker_id]:
                    return {}
            else:
                brokers = self._brokers
            
            for bid, data in brokers.items():
                if not data:
                    continue
                
                health_checker = data.get("health_checker")
                metrics_collector = data.get("metrics_collector")
                
                if not health_checker or not metrics_collector:
                    continue
                
                # Get metrics snapshot
                snapshot = metrics_collector.get_snapshot(
                    health_status=health_checker.current_status.value,
                    last_health_check=health_checker._last_check,
                )
                
                # Get uptime
                uptime = time.time() - health_checker._start_time if hasattr(health_checker, "_start_time") else 0
                
                # Get alerts for this broker
                broker_alerts = self.get_alerts(broker_id=bid, resolved=False, limit=10)
                
                status = BrokerStatus(
                    broker_id=bid,
                    broker_name=data.get("broker_name", "unknown"),
                    is_connected=data.get("is_connected", False),
                    connection_state=data.get("connection_state", ConnectionState.DISCONNECTED),
                    health_status=health_checker.current_status,
                    last_health_check=health_checker._last_check,
                    uptime_seconds=uptime,
                    total_requests=snapshot.total_requests,
                    error_rate=snapshot.error_rate,
                    avg_latency_ms=snapshot.avg_latency_ms,
                    open_positions=snapshot.open_positions,
                    open_orders=snapshot.open_orders,
                    balance=snapshot.balance,
                    equity=snapshot.equity,
                    last_activity=datetime.utcnow(),  # Should track last activity
                    alerts=broker_alerts,
                )
                
                result[bid] = status
            
            return result
    
    async def get_broker_status(self, broker_id: str) -> Optional[BrokerStatus]:
        """
        Get status for a specific broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Optional[BrokerStatus]: Broker status or None
        """
        statuses = await self.get_status(broker_id)
        return statuses.get(broker_id)
    
    # ========================================================================
    # MONITORING LOOP
    # ========================================================================
    
    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Started broker monitor")
    
    async def stop(self) -> None:
        """Stop the monitoring loop."""
        if not self._running:
            return
        
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        self.logger.info("Stopped broker monitor")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_brokers()
                await self._cleanup_history()
                await asyncio.sleep(10)  # Check every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(10)
    
    async def _check_brokers(self) -> None:
        """Check all registered brokers."""
        async with self._lock:
            for broker_id, data in self._brokers.items():
                try:
                    await self._check_broker(broker_id, data)
                except Exception as e:
                    self.logger.error(f"Error checking broker {broker_id}: {e}")
                    await self.alert(
                        broker_id=broker_id,
                        severity=AlertSeverity.ERROR,
                        category=AlertCategory.SYSTEM,
                        message=f"Error checking broker: {e}",
                        details={"error": str(e)},
                    )
    
    async def _check_broker(self, broker_id: str, data: Dict[str, Any]) -> None:
        """
        Check a specific broker.
        
        Args:
            broker_id: Broker identifier
            data: Broker data
        """
        health_checker = data.get("health_checker")
        metrics_collector = data.get("metrics_collector")
        
        if not health_checker or not metrics_collector:
            return
        
        # Get current status
        health_status = health_checker.current_status
        snapshot = metrics_collector.get_snapshot(
            health_status=health_status.value,
            last_health_check=health_checker._last_check,
        )
        
        # Track previous status
        previous_status = data.get("last_status")
        data["last_status"] = snapshot.to_dict()
        
        # Store history
        data["status_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "status": snapshot.to_dict(),
        })
        
        # Trim history
        if len(data["status_history"]) > 1000:
            data["status_history"] = data["status_history"][-1000:]
        
        # Check for issues and generate alerts
        await self._check_health_alerts(broker_id, health_status, snapshot)
        await self._check_performance_alerts(broker_id, snapshot)
        await self._check_account_alerts(broker_id, snapshot)
        await self._check_rate_limit_alerts(broker_id, snapshot)
        
        # Trigger status change if significant
        if previous_status:
            if self._status_changed(previous_status, snapshot.to_dict()):
                await self._trigger_status_change(broker_id, snapshot.to_dict())
    
    async def _check_health_alerts(
        self,
        broker_id: str,
        health_status: HealthStatus,
        snapshot: BrokerMetricsSnapshot,
    ) -> None:
        """Check health status and generate alerts."""
        if health_status == HealthStatus.OFFLINE:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.CONNECTION,
                message="Broker is offline",
                details={"status": health_status.value},
            )
        elif health_status == HealthStatus.UNHEALTHY:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.ERROR,
                category=AlertCategory.HEALTH,
                message="Broker is unhealthy",
                details={"status": health_status.value},
            )
        elif health_status == HealthStatus.DEGRADED:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.HEALTH,
                message="Broker is degraded",
                details={"status": health_status.value},
            )
    
    async def _check_performance_alerts(
        self,
        broker_id: str,
        snapshot: BrokerMetricsSnapshot,
    ) -> None:
        """Check performance metrics and generate alerts."""
        # Error rate alert
        if snapshot.error_rate > 20:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.ERROR,
                category=AlertCategory.PERFORMANCE,
                message=f"High error rate: {snapshot.error_rate:.1f}%",
                details={"error_rate": snapshot.error_rate},
            )
        elif snapshot.error_rate > 10:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.PERFORMANCE,
                message=f"Elevated error rate: {snapshot.error_rate:.1f}%",
                details={"error_rate": snapshot.error_rate},
            )
        
        # Latency alert
        if snapshot.p95_latency_ms > 1000:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.PERFORMANCE,
                message=f"High latency: p95={snapshot.p95_latency_ms:.0f}ms",
                details={"p95_latency": snapshot.p95_latency_ms},
            )
        
        # Order error rate alert
        if snapshot.order_error_rate > 10:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.ORDER,
                message=f"High order error rate: {snapshot.order_error_rate:.1f}%",
                details={"order_error_rate": snapshot.order_error_rate},
            )
    
    async def _check_account_alerts(
        self,
        broker_id: str,
        snapshot: BrokerMetricsSnapshot,
    ) -> None:
        """Check account metrics and generate alerts."""
        # Low balance alert
        if snapshot.balance > 0 and snapshot.balance < 100:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.ACCOUNT,
                message=f"Low account balance: ${snapshot.balance:.2f}",
                details={"balance": snapshot.balance},
            )
        
        # High margin usage alert
        if snapshot.equity > 0:
            margin_ratio = (snapshot.equity - snapshot.balance) / snapshot.equity
            if margin_ratio > 0.8:
                await self.alert(
                    broker_id=broker_id,
                    severity=AlertSeverity.WARNING,
                    category=AlertCategory.ACCOUNT,
                    message=f"High margin usage: {margin_ratio:.1%}",
                    details={"margin_ratio": margin_ratio},
                )
    
    async def _check_rate_limit_alerts(
        self,
        broker_id: str,
        snapshot: BrokerMetricsSnapshot,
    ) -> None:
        """Check rate limit metrics and generate alerts."""
        # Check for rate limit errors from metrics
        rate_limit_errors = snapshot.custom.get("rate_limit_errors", 0)
        if rate_limit_errors > 0:
            await self.alert(
                broker_id=broker_id,
                severity=AlertSeverity.WARNING,
                category=AlertCategory.RATE_LIMIT,
                message=f"Rate limit errors detected: {rate_limit_errors}",
                details={"rate_limit_errors": rate_limit_errors},
            )
    
    def _status_changed(self, previous: Dict[str, Any], current: Dict[str, Any]) -> bool:
        """
        Check if status has changed significantly.
        
        Args:
            previous: Previous status
            current: Current status
            
        Returns:
            bool: True if status changed
        """
        # Check key indicators
        key_fields = [
            "is_connected",
            "health_status",
            "error_rate",
            "open_positions",
            "open_orders",
        ]
        
        for field in key_fields:
            if previous.get(field) != current.get(field):
                return True
        
        # Check if error rate changed significantly
        prev_error = previous.get("requests", {}).get("error_rate", 0)
        curr_error = current.get("requests", {}).get("error_rate", 0)
        if abs(curr_error - prev_error) > 5:
            return True
        
        return False
    
    async def _cleanup_history(self) -> None:
        """Clean up old history data."""
        now = time.time()
        cutoff = now - self.history_retention
        
        async with self._lock:
            for broker_id in list(self._status_history.keys()):
                self._status_history[broker_id] = [
                    entry for entry in self._status_history[broker_id]
                    if entry.get("timestamp", 0) > cutoff
                ]
                if not self._status_history[broker_id]:
                    del self._status_history[broker_id]
    
    # ========================================================================
    # QUERY METHODS
    # ========================================================================
    
    def get_status_history(
        self,
        broker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get status history for a broker.
        
        Args:
            broker_id: Broker identifier
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum number of entries
            
        Returns:
            List[Dict]: Status history
        """
        data = self._brokers.get(broker_id, {})
        history = data.get("status_history", [])
        
        # Filter by time
        if start_time:
            start_ts = start_time.timestamp()
            history = [h for h in history if h.get("timestamp", 0) > start_ts]
        
        if end_time:
            end_ts = end_time.timestamp()
            history = [h for h in history if h.get("timestamp", 0) < end_ts]
        
        return history[-limit:] if limit > 0 else history
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all monitored brokers.
        
        Returns:
            Dict: Summary statistics
        """
        async def _get_summary():
            statuses = await self.get_status()
            
            total = len(statuses)
            connected = sum(1 for s in statuses.values() if s.is_connected)
            healthy = sum(1 for s in statuses.values() if s.health_status == HealthStatus.HEALTHY)
            
            total_requests = sum(s.total_requests for s in statuses.values())
            avg_error_rate = sum(s.error_rate for s in statuses.values()) / max(total, 1)
            avg_latency = sum(s.avg_latency_ms for s in statuses.values()) / max(total, 1)
            
            alerts = self.get_alerts(resolved=False)
            
            return {
                "total_brokers": total,
                "connected_brokers": connected,
                "healthy_brokers": healthy,
                "total_requests": total_requests,
                "avg_error_rate": avg_error_rate,
                "avg_latency_ms": avg_latency,
                "active_alerts": len(alerts),
                "alerts_by_severity": {
                    severity.value: len([a for a in alerts if a.severity == severity])
                    for severity in AlertSeverity
                },
                "brokers": {
                    bid: {
                        "status": s.health_status.value,
                        "connected": s.is_connected,
                        "uptime": s.uptime_seconds,
                    }
                    for bid, s in statuses.items()
                },
            }
        
        # Run async in sync context
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a new task if loop is running
                return asyncio.create_task(_get_summary())
            else:
                return loop.run_until_complete(_get_summary())
        except RuntimeError:
            # No running loop
            return asyncio.run(_get_summary())
    
    # ========================================================================
    # HEALTH CHECK FORWARDING
    # ========================================================================
    
    async def check_broker_health(self, broker_id: str) -> Optional[Dict[str, Any]]:
        """
        Force a health check on a broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Optional[Dict]: Health check result
        """
        data = self._brokers.get(broker_id)
        if not data:
            return None
        
        health_checker = data.get("health_checker")
        if not health_checker:
            return None
        
        result = await health_checker.perform_check()
        return result.to_dict()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "AlertSeverity",
    "AlertCategory",
    
    # Models
    "Alert",
    "BrokerStatus",
    
    # Class
    "BrokerMonitor",
]
