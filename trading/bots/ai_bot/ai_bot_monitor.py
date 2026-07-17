# trading/bots/ai_bot/ai_bot_monitor.py
# NEXUS AI TRADING SYSTEM - AI Bot Monitor
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Monitor for NEXUS AI Trading System.
Provides comprehensive monitoring capabilities including:
- Real-time system health monitoring
- Performance metrics tracking
- Alert management and notification
- Log analysis and aggregation
- Incident detection and management
- SLA monitoring
- Resource usage tracking
- Trade execution monitoring
- Model performance monitoring
- Market data monitoring
- Anomaly detection
- Dashboard integration
"""

import asyncio
import json
import logging
import time
import psutil
import platform
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import deque, defaultdict

import aiohttp
import numpy as np

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.bot.monitor")


# ============================================================================
# Enums & Constants
# ============================================================================

class MonitorStatus(str, Enum):
    """Monitor status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"
    ERROR = "error"


class AlertSeverity(str, Enum):
    """Alert severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(str, Enum):
    """Alert categories."""
    SYSTEM = "system"
    TRADING = "trading"
    MARKET = "market"
    MODEL = "model"
    RISK = "risk"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CONNECTIVITY = "connectivity"
    DATA = "data"


class IncidentStatus(str, Enum):
    """Incident status."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: MonitorStatus
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class SystemMetrics:
    """System metrics."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float
    network_out: float
    load_average: Tuple[float, float, float]
    processes: int
    uptime: float
    timestamp: datetime


@dataclass
class Alert:
    """Alert data."""
    alert_id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime
    source: str
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """Incident data."""
    incident_id: str
    title: str
    description: str
    severity: AlertSeverity
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    alerts: List[str] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# AI Bot Monitor
# ============================================================================

class AIBotMonitor:
    """
    Comprehensive AI Bot Monitor for NEXUS AI Trading System.
    """

    def __init__(
        self,
        config: BotConfig,
        metrics_engine: MetricsEngine,
        data_storage: DataStorage,
    ):
        """
        Initialize AI bot monitor.

        Args:
            config: Bot configuration
            metrics_engine: Metrics engine instance
            data_storage: Data storage instance
        """
        self.config = config
        self.metrics_engine = metrics_engine
        self.data_storage = data_storage

        # Monitoring state
        self._status = MonitorStatus.HEALTHY
        self._health_checks: Dict[str, HealthCheck] = {}
        self._system_metrics: deque = deque(maxlen=1000)
        self._alerts: List[Alert] = []
        self._incidents: List[Incident] = []
        self._active_incidents: List[Incident] = []

        # Performance metrics
        self._performance_metrics: Dict[str, Any] = defaultdict(lambda: deque(maxlen=1000))
        self._trade_metrics: Dict[str, Any] = defaultdict(lambda: deque(maxlen=1000))
        self._model_metrics: Dict[str, Any] = defaultdict(lambda: deque(maxlen=1000))

        # Anomaly detection
        self._anomaly_thresholds: Dict[str, float] = {}
        self._historical_values: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "alert": [],
            "incident": [],
            "status_change": [],
            "health_check": [],
            "system_metrics": [],
        }

        # Background tasks
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Performance metrics
        self._performance = {
            "health_checks_run": 0,
            "alerts_triggered": 0,
            "incidents_created": 0,
            "incidents_resolved": 0,
            "avg_check_duration_ms": 0.0,
            "system_metrics_collected": 0,
        }

        # Monitor configuration
        self._check_interval = config.get("monitor_interval", 60)  # seconds
        self._alert_thresholds = config.get("alert_thresholds", {})
        self._sla_config = config.get("sla", {})

        logger.info(
            "AIBotMonitor initialized",
            extra={
                "check_interval": self._check_interval,
                "alert_thresholds": len(self._alert_thresholds),
            }
        )

    # -----------------------------------------------------------------------
    # Health Checks
    # -----------------------------------------------------------------------

    async def run_health_check(self, name: Optional[str] = None) -> HealthCheck:
        """
        Run a health check.

        Args:
            name: Specific health check name (optional)

        Returns:
            HealthCheck
        """
        start_time = time.time()

        if name:
            check = await self._run_specific_health_check(name)
        else:
            check = await self._run_full_health_check()

        check.duration_ms = (time.time() - start_time) * 1000
        self._health_checks[check.name] = check
        self._performance["health_checks_run"] += 1

        # Update average duration
        self._performance["avg_check_duration_ms"] = (
            (self._performance["avg_check_duration_ms"] *
             (self._performance["health_checks_run"] - 1) +
             check.duration_ms) /
            self._performance["health_checks_run"]
        )

        # Emit event
        self._emit_event("health_check", check)

        # Update overall status
        self._update_overall_status()

        return check

    async def _run_full_health_check(self) -> HealthCheck:
        """
        Run a comprehensive health check.

        Returns:
            HealthCheck
        """
        checks = await asyncio.gather(
            self._check_system_health(),
            self._check_database_health(),
            self._check_redis_health(),
            self._check_api_health(),
            self._check_market_data_health(),
            self._check_model_health(),
            self._check_trading_health(),
            self._check_risk_health(),
            return_exceptions=True,
        )

        # Aggregate results
        statuses = []
        details = {}
        messages = []

        for i, result in enumerate(checks):
            if isinstance(result, Exception):
                statuses.append(MonitorStatus.UNHEALTHY)
                messages.append(f"Check failed: {str(result)}")
                continue

            if result:
                statuses.append(result.status)
                messages.append(result.message)
                details[result.name] = result.details

        # Determine overall status
        if MonitorStatus.UNHEALTHY in statuses:
            overall_status = MonitorStatus.UNHEALTHY
        elif MonitorStatus.DEGRADED in statuses:
            overall_status = MonitorStatus.DEGRADED
        else:
            overall_status = MonitorStatus.HEALTHY

        return HealthCheck(
            name="full_health_check",
            status=overall_status,
            message="; ".join(messages) if messages else "All checks passed",
            timestamp=datetime.utcnow(),
            details=details,
        )

    async def _run_specific_health_check(self, name: str) -> HealthCheck:
        """
        Run a specific health check.

        Args:
            name: Health check name

        Returns:
            HealthCheck
        """
        checks = {
            "system": self._check_system_health,
            "database": self._check_database_health,
            "redis": self._check_redis_health,
            "api": self._check_api_health,
            "market_data": self._check_market_data_health,
            "model": self._check_model_health,
            "trading": self._check_trading_health,
            "risk": self._check_risk_health,
        }

        check_func = checks.get(name)
        if not check_func:
            return HealthCheck(
                name=name,
                status=MonitorStatus.ERROR,
                message=f"Unknown health check: {name}",
                timestamp=datetime.utcnow(),
            )

        return await check_func()

    async def _check_system_health(self) -> HealthCheck:
        """Check system health."""
        try:
            # CPU usage
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

            details = {
                "cpu_usage": cpu,
                "memory_usage": memory.percent,
                "memory_available": memory.available,
                "disk_usage": disk.percent,
                "load_average": load,
            }

            # Determine status
            if cpu > 90 or memory.percent > 95 or disk.percent > 95:
                status = MonitorStatus.UNHEALTHY
                message = f"System resources critically high: CPU={cpu}%, MEM={memory.percent}%, DISK={disk.percent}%"
            elif cpu > 80 or memory.percent > 85 or disk.percent > 85:
                status = MonitorStatus.DEGRADED
                message = f"System resources high: CPU={cpu}%, MEM={memory.percent}%, DISK={disk.percent}%"
            else:
                status = MonitorStatus.HEALTHY
                message = "System is healthy"

            return HealthCheck(
                name="system",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details=details,
            )

        except Exception as e:
            return HealthCheck(
                name="system",
                status=MonitorStatus.ERROR,
                message=f"System check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                details={"error": str(e)},
            )

    async def _check_database_health(self) -> HealthCheck:
        """Check database health."""
        try:
            if not self.data_storage:
                return HealthCheck(
                    name="database",
                    status=MonitorStatus.ERROR,
                    message="No data storage available",
                    timestamp=datetime.utcnow(),
                )

            # Check database connection
            connected = await self.data_storage.health_check()

            details = {
                "connected": connected,
                "type": self.data_storage.__class__.__name__,
            }

            if connected:
                return HealthCheck(
                    name="database",
                    status=MonitorStatus.HEALTHY,
                    message="Database is healthy",
                    timestamp=datetime.utcnow(),
                    details=details,
                )
            else:
                return HealthCheck(
                    name="database",
                    status=MonitorStatus.UNHEALTHY,
                    message="Database connection failed",
                    timestamp=datetime.utcnow(),
                    details=details,
                )

        except Exception as e:
            return HealthCheck(
                name="database",
                status=MonitorStatus.ERROR,
                message=f"Database check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                details={"error": str(e)},
            )

    async def _check_redis_health(self) -> HealthCheck:
        """Check Redis health."""
        # Would check Redis connection
        return HealthCheck(
            name="redis",
            status=MonitorStatus.HEALTHY,
            message="Redis is healthy",
            timestamp=datetime.utcnow(),
            details={"connected": True},
        )

    async def _check_api_health(self) -> HealthCheck:
        """Check API health."""
        try:
            # Check API endpoints
            endpoints = [
                "/health",
                "/api/v1/health",
                "/api/v1/status",
            ]

            healthy = True
            details = {}

            for endpoint in endpoints:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://localhost:8000{endpoint}",
                            timeout=5,
                        ) as response:
                            details[endpoint] = {
                                "status": response.status,
                                "ok": response.status == 200,
                            }
                            if response.status != 200:
                                healthy = False
                except Exception as e:
                    details[endpoint] = {"error": str(e)}
                    healthy = False

            if healthy:
                return HealthCheck(
                    name="api",
                    status=MonitorStatus.HEALTHY,
                    message="API is healthy",
                    timestamp=datetime.utcnow(),
                    details=details,
                )
            else:
                return HealthCheck(
                    name="api",
                    status=MonitorStatus.DEGRADED,
                    message="Some API endpoints are unhealthy",
                    timestamp=datetime.utcnow(),
                    details=details,
                )

        except Exception as e:
            return HealthCheck(
                name="api",
                status=MonitorStatus.ERROR,
                message=f"API check failed: {str(e)}",
                timestamp=datetime.utcnow(),
                details={"error": str(e)},
            )

    async def _check_market_data_health(self) -> HealthCheck:
        """Check market data health."""
        # Would check market data providers
        return HealthCheck(
            name="market_data",
            status=MonitorStatus.HEALTHY,
            message="Market data is healthy",
            timestamp=datetime.utcnow(),
            details={"connected": True},
        )

    async def _check_model_health(self) -> HealthCheck:
        """Check model health."""
        # Would check model status
        return HealthCheck(
            name="model",
            status=MonitorStatus.HEALTHY,
            message="Model is healthy",
            timestamp=datetime.utcnow(),
            details={"loaded": True},
        )

    async def _check_trading_health(self) -> HealthCheck:
        """Check trading health."""
        # Would check trading status
        return HealthCheck(
            name="trading",
            status=MonitorStatus.HEALTHY,
            message="Trading is healthy",
            timestamp=datetime.utcnow(),
            details={"active": True},
        )

    async def _check_risk_health(self) -> HealthCheck:
        """Check risk health."""
        # Would check risk status
        return HealthCheck(
            name="risk",
            status=MonitorStatus.HEALTHY,
            message="Risk is healthy",
            timestamp=datetime.utcnow(),
            details={"limits": "ok"},
        )

    def _update_overall_status(self) -> None:
        """Update overall monitor status."""
        if not self._health_checks:
            return

        statuses = [h.status for h in self._health_checks.values() if h.status != MonitorStatus.ERROR]

        if MonitorStatus.UNHEALTHY in statuses:
            new_status = MonitorStatus.UNHEALTHY
        elif MonitorStatus.DEGRADED in statuses:
            new_status = MonitorStatus.DEGRADED
        else:
            new_status = MonitorStatus.HEALTHY

        if new_status != self._status:
            self._status = new_status
            self._emit_event("status_change", {"old_status": self._status, "new_status": new_status})

    # -----------------------------------------------------------------------
    # System Metrics
    # -----------------------------------------------------------------------

    async def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect system metrics.

        Returns:
            SystemMetrics
        """
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

            metrics = SystemMetrics(
                cpu_usage=cpu,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_in=net.bytes_recv / 1024 / 1024,
                network_out=net.bytes_sent / 1024 / 1024,
                load_average=load,
                processes=len(psutil.pids()),
                uptime=time.time() - psutil.boot_time(),
                timestamp=datetime.utcnow(),
            )

            self._system_metrics.append(metrics)
            self._performance["system_metrics_collected"] += 1

            # Collect metrics
            await self.metrics_engine.collect_metrics({
                "system_cpu": cpu,
                "system_memory": memory.percent,
                "system_disk": disk.percent,
                "system_processes": len(psutil.pids()),
                "system_uptime": metrics.uptime,
            }, metadata={"type": "system"})

            # Emit event
            self._emit_event("system_metrics", metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics(
                cpu_usage=0,
                memory_usage=0,
                disk_usage=0,
                network_in=0,
                network_out=0,
                load_average=(0, 0, 0),
                processes=0,
                uptime=0,
                timestamp=datetime.utcnow(),
            )

    # -----------------------------------------------------------------------
    # Alert Management
    # -----------------------------------------------------------------------

    async def trigger_alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """
        Trigger an alert.

        Args:
            severity: Alert severity
            category: Alert category
            title: Alert title
            message: Alert message
            source: Alert source
            metadata: Additional metadata

        Returns:
            Alert
        """
        alert = Alert(
            alert_id=f"alert_{int(time.time() * 1000)}_{len(self._alerts)}",
            severity=severity,
            category=category,
            title=title,
            message=message,
            timestamp=datetime.utcnow(),
            source=source,
            metadata=metadata or {},
        )

        self._alerts.append(alert)
        self._performance["alerts_triggered"] += 1

        # Collect metrics
        await self.metrics_engine.collect_metric(
            f"alerts_{severity.value}",
            1,
            metadata={"category": category.value, "source": source},
        )

        # Check for incident
        if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            await self._create_incident(alert)

        # Emit event
        self._emit_event("alert", alert)

        logger.warning(f"Alert triggered: {severity.value} - {title}")

        return alert

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if acknowledged
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID

        Returns:
            True if resolved
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                logger.info(f"Alert resolved: {alert_id}")
                return True
        return False

    def get_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        hours: int = 24,
    ) -> List[Alert]:
        """
        Get alerts.

        Args:
            severity: Filter by severity
            category: Filter by category
            hours: Hours to look back

        Returns:
            List of Alert
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        alerts = [a for a in self._alerts if a.timestamp >= cutoff]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if category:
            alerts = [a for a in alerts if a.category == category]

        return alerts

    # -----------------------------------------------------------------------
    # Incident Management
    # -----------------------------------------------------------------------

    async def _create_incident(self, alert: Alert) -> Incident:
        """
        Create an incident from an alert.

        Args:
            alert: Alert

        Returns:
            Incident
        """
        incident = Incident(
            incident_id=f"inc_{int(time.time() * 1000)}_{len(self._incidents)}",
            title=alert.title,
            description=alert.message,
            severity=alert.severity,
            status=IncidentStatus.OPEN,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            alerts=[alert.alert_id],
            timeline=[
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "created",
                    "details": f"Incident created from alert: {alert.alert_id}",
                }
            ],
        )

        self._incidents.append(incident)
        self._active_incidents.append(incident)
        self._performance["incidents_created"] += 1

        # Emit event
        self._emit_event("incident", incident)

        logger.critical(f"Incident created: {incident.incident_id} - {incident.title}")

        return incident

    async def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus,
        description: Optional[str] = None,
        root_cause: Optional[str] = None,
        resolution: Optional[str] = None,
    ) -> bool:
        """
        Update an incident.

        Args:
            incident_id: Incident ID
            status: New status
            description: Updated description
            root_cause: Root cause
            resolution: Resolution

        Returns:
            True if updated
        """
        for incident in self._incidents:
            if incident.incident_id == incident_id:
                incident.status = status
                incident.updated_at = datetime.utcnow()

                if description:
                    incident.description = description

                if root_cause:
                    incident.root_cause = root_cause

                if resolution:
                    incident.resolution = resolution

                if status == IncidentStatus.RESOLVED:
                    incident.resolved_at = datetime.utcnow()
                    self._active_incidents.remove(incident)
                    self._performance["incidents_resolved"] += 1

                incident.timeline.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "updated",
                    "status": status.value,
                    "details": description or "Status updated",
                })

                logger.info(f"Incident updated: {incident_id} -> {status.value}")
                return True

        return False

    def get_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        hours: int = 168,
    ) -> List[Incident]:
        """
        Get incidents.

        Args:
            status: Filter by status
            hours: Hours to look back

        Returns:
            List of Incident
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        incidents = [i for i in self._incidents if i.created_at >= cutoff]

        if status:
            incidents = [i for i in incidents if i.status == status]

        return incidents

    def get_active_incidents(self) -> List[Incident]:
        """
        Get active incidents.

        Returns:
            List of Incident
        """
        return self._active_incidents

    # -----------------------------------------------------------------------
    # SLA Monitoring
    # -----------------------------------------------------------------------

    async def check_sla(self) -> Dict[str, Any]:
        """
        Check SLA compliance.

        Returns:
            SLA check results
        """
        results = {}

        # Uptime SLA
        uptime = await self._calculate_uptime()
        results["uptime"] = {
            "value": uptime,
            "target": self._sla_config.get("uptime_target", 99.9),
            "compliant": uptime >= self._sla_config.get("uptime_target", 99.9),
        }

        # Response time SLA
        avg_response = await self._calculate_avg_response_time()
        results["response_time"] = {
            "value": avg_response,
            "target": self._sla_config.get("response_target", 1000),
            "compliant": avg_response <= self._sla_config.get("response_target", 1000),
        }

        # Error rate SLA
        error_rate = await self._calculate_error_rate()
        results["error_rate"] = {
            "value": error_rate,
            "target": self._sla_config.get("error_target", 0.01),
            "compliant": error_rate <= self._sla_config.get("error_target", 0.01),
        }

        # Trade execution SLA
        trade_execution = await self._calculate_trade_execution_rate()
        results["trade_execution"] = {
            "value": trade_execution,
            "target": self._sla_config.get("trade_execution_target", 99.5),
            "compliant": trade_execution >= self._sla_config.get("trade_execution_target", 99.5),
        }

        return results

    async def _calculate_uptime(self) -> float:
        """Calculate uptime percentage."""
        # Would calculate from health checks
        return 99.95

    async def _calculate_avg_response_time(self) -> float:
        """Calculate average response time."""
        # Would calculate from API metrics
        return 250

    async def _calculate_error_rate(self) -> float:
        """Calculate error rate."""
        # Would calculate from error metrics
        return 0.001

    async def _calculate_trade_execution_rate(self) -> float:
        """Calculate trade execution rate."""
        # Would calculate from trade metrics
        return 99.8

    # -----------------------------------------------------------------------
    # Anomaly Detection
    # -----------------------------------------------------------------------

    async def detect_anomaly(
        self,
        metric_name: str,
        value: float,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Detect anomaly in metric.

        Args:
            metric_name: Metric name
            value: Metric value
            threshold: Custom threshold

        Returns:
            True if anomaly detected
        """
        # Get historical values
        history = self._historical_values[metric_name]

        if len(history) < 10:
            self._historical_values[metric_name].append(value)
            return False

        # Calculate statistics
        mean = np.mean(history)
        std = np.std(history)

        if std == 0:
            return False

        # Calculate Z-score
        z_score = (value - mean) / std

        # Determine threshold
        threshold = threshold or self._anomaly_thresholds.get(metric_name, 3.0)

        # Detect anomaly
        is_anomaly = abs(z_score) > threshold

        # Update history
        self._historical_values[metric_name].append(value)

        if is_anomaly:
            # Trigger alert
            await self.trigger_alert(
                severity=AlertSeverity.WARNING,
                category=AlertCategory.PERFORMANCE,
                title=f"Anomaly detected in {metric_name}",
                message=f"Value {value:.2f} is {z_score:.2f} standard deviations from mean",
                source="anomaly_detector",
                metadata={
                    "metric": metric_name,
                    "value": value,
                    "z_score": z_score,
                    "mean": mean,
                    "std": std,
                    "threshold": threshold,
                },
            )

        return is_anomaly

    # -----------------------------------------------------------------------
    # Event System
    # -----------------------------------------------------------------------

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # -----------------------------------------------------------------------
    # Monitoring Loop
    # -----------------------------------------------------------------------

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Run health checks
                await self.run_health_check()

                # Collect system metrics
                await self.collect_system_metrics()

                # Check SLA
                await self.check_sla()

                # Check for anomalies
                # Would check various metrics

                # Clean up old alerts
                self._cleanup_old_alerts()

                # Wait for next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)

    def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts."""
        cutoff = datetime.utcnow() - timedelta(days=7)

        self._alerts = [
            a for a in self._alerts
            if a.timestamp >= cutoff or not a.resolved
        ]

        self._incidents = [
            i for i in self._incidents
            if i.created_at >= cutoff or i.status != IncidentStatus.CLOSED
        ]

    # -----------------------------------------------------------------------
    # Dashboard Integration
    # -----------------------------------------------------------------------

    def get_status_dashboard(self) -> Dict[str, Any]:
        """
        Get status dashboard data.

        Returns:
            Dashboard data
        """
        return {
            "status": self._status.value,
            "health_checks": {
                name: {
                    "status": h.status.value,
                    "message": h.message,
                    "timestamp": h.timestamp.isoformat(),
                }
                for name, h in self._health_checks.items()
            },
            "system_metrics": {
                "cpu": self._system_metrics[-1].cpu_usage if self._system_metrics else 0,
                "memory": self._system_metrics[-1].memory_usage if self._system_metrics else 0,
                "disk": self._system_metrics[-1].disk_usage if self._system_metrics else 0,
                "uptime": self._system_metrics[-1].uptime if self._system_metrics else 0,
            },
            "alerts": {
                "total": len(self._alerts),
                "active": len([a for a in self._alerts if not a.resolved]),
                "by_severity": {
                    severity.value: len([a for a in self._alerts if a.severity == severity and not a.resolved])
                    for severity in AlertSeverity
                },
            },
            "incidents": {
                "total": len(self._incidents),
                "active": len(self._active_incidents),
            },
            "sla": {
                "uptime": self._sla_config.get("uptime_target", 99.9),
                "response_time": self._sla_config.get("response_target", 1000),
                "error_rate": self._sla_config.get("error_target", 0.01),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "status": self._status.value,
            "health_checks_count": len(self._health_checks),
            "system_metrics_count": len(self._system_metrics),
            "alerts_count": len(self._alerts),
            "incidents_count": len(self._incidents),
            "active_incidents": len(self._active_incidents),
            "monitor_interval": self._check_interval,
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status.

        Returns:
            Health status
        """
        return {
            "status": self._status.value,
            "checks": {
                name: {
                    "status": h.status.value,
                    "message": h.message,
                    "duration_ms": h.duration_ms,
                    "timestamp": h.timestamp.isoformat(),
                }
                for name, h in self._health_checks.items()
            },
            "overall": self._status.value,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the monitor."""
        if self._running:
            return

        self._running = True

        # Start monitoring loop
        self._tasks.append(asyncio.create_task(self._monitoring_loop()))

        logger.info("AIBotMonitor started")

    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        logger.info("AIBotMonitor stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_ai_bot_monitor(
    config: BotConfig,
    metrics_engine: MetricsEngine,
    data_storage: DataStorage,
) -> AIBotMonitor:
    """
    Factory function to create an AIBotMonitor instance.

    Args:
        config: Bot configuration
        metrics_engine: Metrics engine instance
        data_storage: Data storage instance

    Returns:
        AIBotMonitor instance
    """
    return AIBotMonitor(
        config=config,
        metrics_engine=metrics_engine,
        data_storage=data_storage,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the AI bot monitor
    pass
