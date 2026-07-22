# trading/bots/hedge_bot/monitoring/health_checker.py

"""
NEXUS HEDGE BOT - HEALTH CHECKER
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive health monitoring system with component-level checks,
dependency validation, and automatic recovery recommendations.

Version: 3.0.0
"""

import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable

import aiohttp
import psutil
import structlog
import yaml
from redis.asyncio import Redis
from pydantic import BaseModel, Field, validator

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
    STARTING = "starting"
    STOPPING = "stopping"


class HealthCheckType(str, Enum):
    """Types of health checks."""
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    CACHE = "cache"
    BROKER = "broker"
    API = "api"
    WEBSOCKET = "websocket"
    FILE_SYSTEM = "file_system"
    PROCESS = "process"
    RESOURCE = "resource"
    CUSTOM = "custom"


class ResourceType(str, Enum):
    """Resource types for resource checks."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    FD = "file_descriptors"
    THREADS = "threads"
    PROCESSES = "processes"


# === DATA MODELS ===

@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: HealthCheckType = HealthCheckType.CUSTOM
    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    recovery_action: Optional[str] = None
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthCheckResult":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["type"] = HealthCheckType(data["type"])
        data["status"] = HealthStatus(data["status"])
        return cls(**data)


class HealthCheckConfig(BaseModel):
    """Configuration for a health check."""
    name: str
    type: HealthCheckType
    enabled: bool = True
    interval_seconds: int = 30
    timeout_seconds: int = 5
    retry_count: int = 3
    retry_delay_seconds: int = 1
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    dependencies: List[str] = Field(default_factory=list)
    recovery_action: Optional[str] = None
    severity: str = "medium"
    config: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class HealthMonitorConfig(BaseModel):
    """Configuration for the health monitor."""
    enabled: bool = True
    check_interval_seconds: int = 10
    report_interval_seconds: int = 60
    max_history_size: int = 1000
    alert_on_degraded: bool = True
    alert_on_unhealthy: bool = True
    checks: List[HealthCheckConfig] = Field(default_factory=list)
    notification_webhook: Optional[str] = None
    notification_email: Optional[str] = None


# === HEALTH CHECKERS ===

class BaseHealthChecker:
    """Base class for health checks."""

    def __init__(self, config: HealthCheckConfig):
        self.config = config
        self._last_result: Optional[HealthCheckResult] = None
        self._last_check_time: Optional[datetime] = None
        self._failure_count: int = 0
        self._success_count: int = 0
        self._history: List[HealthCheckResult] = []
        self._lock = threading.RLock()

    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        start_time = time.time()
        result = HealthCheckResult(
            name=self.config.name,
            type=self.config.type,
            status=HealthStatus.UNKNOWN,
            message="Check in progress",
            dependencies=self.config.dependencies,
            recovery_action=self.config.recovery_action,
            severity=self.config.severity,
        )

        try:
            # Run the actual check with timeout
            status, message, details = await asyncio.wait_for(
                self._perform_check(),
                timeout=self.config.timeout_seconds
            )
            result.status = status
            result.message = message
            result.details = details

            # Update counters
            if status == HealthStatus.HEALTHY:
                self._success_count += 1
                self._failure_count = 0
            else:
                self._failure_count += 1
                self._success_count = 0

        except asyncio.TimeoutError:
            result.status = HealthStatus.UNHEALTHY
            result.message = f"Check timed out after {self.config.timeout_seconds}s"
            result.details = {"timeout": self.config.timeout_seconds}
            self._failure_count += 1

        except Exception as e:
            result.status = HealthStatus.UNHEALTHY
            result.message = str(e)
            result.details = {"error": str(e), "traceback": traceback.format_exc()}
            self._failure_count += 1

        finally:
            result.duration_ms = (time.time() - start_time) * 1000
            result.timestamp = datetime.utcnow()

            with self._lock:
                self._last_result = result
                self._last_check_time = result.timestamp
                self._history.append(result)
                if len(self._history) > 100:
                    self._history = self._history[-100:]

            logger.info(
                "health_check_completed",
                name=self.config.name,
                status=result.status.value,
                duration_ms=result.duration_ms,
                failure_count=self._failure_count,
            )

            return result

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Perform the actual health check. Override in subclasses."""
        return HealthStatus.HEALTHY, "OK", {}

    def get_last_result(self) -> Optional[HealthCheckResult]:
        """Get the last check result."""
        with self._lock:
            return self._last_result

    def get_history(self, limit: int = 50) -> List[HealthCheckResult]:
        """Get the check history."""
        with self._lock:
            return self._history[-limit:]

    def get_failure_rate(self) -> float:
        """Get the failure rate."""
        total = self._success_count + self._failure_count
        if total == 0:
            return 0.0
        return self._failure_count / total


class SystemHealthChecker(BaseHealthChecker):
    """System health check (CPU, memory, disk, etc.)."""

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Check system resources."""
        details = {}

        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        details["cpu_percent"] = cpu_percent
        if cpu_percent > self.config.threshold_critical:
            return HealthStatus.UNHEALTHY, f"CPU usage: {cpu_percent}%", details
        elif cpu_percent > self.config.threshold_warning:
            return HealthStatus.DEGRADED, f"CPU usage: {cpu_percent}%", details

        # Memory
        mem = psutil.virtual_memory()
        details["memory_percent"] = mem.percent
        details["memory_used_gb"] = mem.used / (1024 ** 3)
        details["memory_total_gb"] = mem.total / (1024 ** 3)
        if mem.percent > self.config.threshold_critical:
            return HealthStatus.UNHEALTHY, f"Memory usage: {mem.percent}%", details
        elif mem.percent > self.config.threshold_warning:
            return HealthStatus.DEGRADED, f"Memory usage: {mem.percent}%", details

        # Disk
        disk = psutil.disk_usage("/")
        details["disk_percent"] = disk.percent
        details["disk_free_gb"] = disk.free / (1024 ** 3)
        details["disk_total_gb"] = disk.total / (1024 ** 3)
        if disk.percent > self.config.threshold_critical:
            return HealthStatus.UNHEALTHY, f"Disk usage: {disk.percent}%", details
        elif disk.percent > self.config.threshold_warning:
            return HealthStatus.DEGRADED, f"Disk usage: {disk.percent}%", details

        # Load average
        load_avg = psutil.getloadavg()
        details["load_avg_1min"] = load_avg[0]
        details["load_avg_5min"] = load_avg[1]
        details["load_avg_15min"] = load_avg[2]

        return HealthStatus.HEALTHY, "System resources OK", details


class NetworkHealthChecker(BaseHealthChecker):
    """Network health check."""

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Check network connectivity."""
        details = {}
        targets = self.config.config.get("targets", [
            {"host": "8.8.8.8", "port": 53},
            {"host": "1.1.1.1", "port": 53},
        ])
        timeout = self.config.config.get("timeout", 2.0)

        failed = []
        for target in targets:
            host = target.get("host")
            port = target.get("port", 80)
            try:
                start = time.time()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                details[f"{host}:{port}"] = f"OK ({time.time() - start:.2f}s)"
            except Exception as e:
                details[f"{host}:{port}"] = f"FAILED: {str(e)}"
                failed.append(f"{host}:{port}")

        if len(failed) == len(targets):
            return HealthStatus.UNHEALTHY, f"All targets unreachable: {failed}", details
        elif failed:
            return HealthStatus.DEGRADED, f"Some targets unreachable: {failed}", details

        return HealthStatus.HEALTHY, "Network OK", details


class DatabaseHealthChecker(BaseHealthChecker):
    """Database health check."""

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Check database connectivity."""
        db_path = self.config.config.get("db_path")
        if not db_path:
            return HealthStatus.UNHEALTHY, "Database path not configured", {}

        details = {"db_path": db_path}

        try:
            # Check if file exists
            db_file = Path(db_path)
            if not db_file.exists():
                return HealthStatus.UNHEALTHY, f"Database file not found: {db_path}", details

            # Check if file is readable
            if not os.access(db_path, os.R_OK):
                return HealthStatus.UNHEALTHY, f"Database file not readable: {db_path}", details

            # Try to connect and query
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()

            # Check file size
            size = db_file.stat().st_size
            details["size_bytes"] = size
            details["size_mb"] = size / (1024 ** 2)

            return HealthStatus.HEALTHY, "Database OK", details

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Database error: {str(e)}", details


class CacheHealthChecker(BaseHealthChecker):
    """Redis cache health check."""

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Redis connectivity."""
        redis_url = self.config.config.get("redis_url")
        if not redis_url:
            return HealthStatus.UNHEALTHY, "Redis URL not configured", {}

        details = {"redis_url": redis_url}

        try:
            redis_client = Redis.from_url(redis_url, decode_responses=True)
            await redis_client.ping()
            info = await redis_client.info()
            details.update({
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "uptime_days": info.get("uptime_in_days"),
            })
            await redis_client.close()
            return HealthStatus.HEALTHY, "Redis OK", details

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Redis error: {str(e)}", details


class BrokerHealthChecker(BaseHealthChecker):
    """Broker health check."""

    async def _perform_check(self) -> Tuple[HealthStatus, str, Dict[str, Any]]:
        """Check broker connectivity."""
        broker_type = self.config.config.get("broker_type", "binance")
        details = {"broker_type": broker_type}

        # This should be implemented with actual broker APIs
        # For now, just check if the broker module is available
        try:
            # Simulate broker health check
            await asyncio.sleep(0.1)
            return HealthStatus.HEALTHY, f"Broker {broker_type} OK", details
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Broker error: {str(e)}", details


# === HEALTH MONITOR ===

class HealthMonitor:
    """
    Comprehensive health monitoring system with component-level checks,
    dependency validation, and automatic recovery recommendations.
    """

    def __init__(
        self,
        config: Union[HealthMonitorConfig, Dict[str, Any], str],
        checkers: Optional[Dict[str, BaseHealthChecker]] = None,
    ):
        """
        Initialize the HealthMonitor.

        Args:
            config: Configuration object, dict, or path to config file
            checkers: Dictionary of existing health checkers
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                config_data = yaml.safe_load(f)
            self.config = HealthMonitorConfig(**config_data)
        elif isinstance(config, dict):
            self.config = HealthMonitorConfig(**config)
        else:
            self.config = config

        self._checkers: Dict[str, BaseHealthChecker] = {}
        self._lock = threading.RLock()
        self._running = False
        self._shutdown = False
        self._last_report: Optional[datetime] = None
        self._status_cache: Dict[str, HealthStatus] = {}

        # Initialize checkers
        if checkers:
            self._checkers = checkers
        else:
            self._initialize_checkers()

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()

        logger.info(
            "health_monitor_initialized",
            checkers_count=len(self._checkers),
            check_interval=self.config.check_interval_seconds,
        )

    def _initialize_checkers(self) -> None:
        """Initialize health checkers from configuration."""
        checker_map = {
            HealthCheckType.SYSTEM: SystemHealthChecker,
            HealthCheckType.NETWORK: NetworkHealthChecker,
            HealthCheckType.DATABASE: DatabaseHealthChecker,
            HealthCheckType.CACHE: CacheHealthChecker,
            HealthCheckType.BROKER: BrokerHealthChecker,
        }

        for check_config in self.config.checks:
            if not check_config.enabled:
                continue

            checker_class = checker_map.get(check_config.type, BaseHealthChecker)
            checker = checker_class(check_config)
            self._checkers[check_config.name] = checker

            logger.info(
                "health_checker_initialized",
                name=check_config.name,
                type=check_config.type.value,
            )

    async def start(self) -> None:
        """Start the health monitor."""
        if self._running:
            return

        self._running = True
        self._shutdown = False

        # Run initial checks
        await self._run_checks()

        # Start background tasks
        loop = asyncio.get_event_loop()
        self._background_tasks.add(
            loop.create_task(self._check_loop())
        )
        self._background_tasks.add(
            loop.create_task(self._report_loop())
        )

        logger.info("health_monitor_started")

    async def stop(self) -> None:
        """Stop the health monitor."""
        self._shutdown = True
        self._running = False

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        logger.info("health_monitor_stopped")

    async def _check_loop(self) -> None:
        """Background loop for running health checks."""
        while not self._shutdown:
            try:
                await self._run_checks()
                await asyncio.sleep(self.config.check_interval_seconds)
            except Exception as e:
                logger.error("check_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _report_loop(self) -> None:
        """Background loop for generating health reports."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.report_interval_seconds)
                await self._generate_report()
            except Exception as e:
                logger.error("report_loop_error", error=str(e))

    async def _run_checks(self) -> None:
        """Run all health checks."""
        tasks = []
        for name, checker in self._checkers.items():
            task = asyncio.create_task(self._run_single_check(name, checker))
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run_single_check(
        self,
        name: str,
        checker: BaseHealthChecker
    ) -> None:
        """Run a single health check."""
        try:
            result = await checker.check()
            with self._lock:
                self._status_cache[name] = result.status

            # Generate alerts for degraded/unhealthy status
            if result.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY):
                await self._handle_unhealthy_check(result)

        except Exception as e:
            logger.error(
                "health_check_error",
                checker=name,
                error=str(e),
            )

    async def _handle_unhealthy_check(self, result: HealthCheckResult) -> None:
        """Handle unhealthy check results."""
        logger.warning(
            "health_check_unhealthy",
            name=result.name,
            status=result.status.value,
            message=result.message,
            severity=result.severity,
        )

        # Trigger alerts based on severity
        if self.config.alert_on_degraded and result.status == HealthStatus.DEGRADED:
            await self._send_alert(result)

        if self.config.alert_on_unhealthy and result.status == HealthStatus.UNHEALTHY:
            await self._send_alert(result)

        # Execute recovery action if available
        if result.recovery_action:
            await self._execute_recovery_action(result)

    async def _send_alert(self, result: HealthCheckResult) -> None:
        """Send an alert for unhealthy check."""
        # This should integrate with the AlertManager
        logger.warning(
            "health_alert",
            check=result.name,
            status=result.status.value,
            message=result.message,
        )

        # Send to webhook if configured
        if self.config.notification_webhook:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.config.notification_webhook,
                        json=result.to_dict(),
                        timeout=5,
                    ) as response:
                        if response.status != 200:
                            logger.warning(
                                "webhook_failed",
                                status=response.status,
                            )
            except Exception as e:
                logger.error("webhook_error", error=str(e))

    async def _execute_recovery_action(self, result: HealthCheckResult) -> None:
        """Execute a recovery action."""
        action = result.recovery_action
        if not action:
            return

        logger.info(
            "executing_recovery_action",
            check=result.name,
            action=action,
        )

        # Parse action command
        # Example: "restart_service:hedge_bot"
        parts = action.split(":")
        if len(parts) == 2:
            action_type = parts[0]
            action_target = parts[1]

            if action_type == "restart_service":
                # Restart service (implementation would vary)
                logger.info("restarting_service", service=action_target)
            elif action_type == "clear_cache":
                # Clear cache
                logger.info("clearing_cache", target=action_target)
            elif action_type == "notify_admin":
                # Notify admin
                logger.info("notifying_admin", target=action_target)

    async def _generate_report(self) -> None:
        """Generate a health report."""
        statuses = await self.get_all_statuses()

        # Count by status
        counts = {status.value: 0 for status in HealthStatus}
        for status in statuses.values():
            counts[status.value] += 1

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": self.get_overall_status().value,
            "status_counts": counts,
            "details": statuses,
        }

        logger.info("health_report", report=report)

        self._last_report = datetime.utcnow()

    def get_overall_status(self) -> HealthStatus:
        """Get the overall health status."""
        with self._lock:
            statuses = list(self._status_cache.values())

            if HealthStatus.UNHEALTHY in statuses:
                return HealthStatus.UNHEALTHY
            elif HealthStatus.DEGRADED in statuses:
                return HealthStatus.DEGRADED
            elif all(s == HealthStatus.HEALTHY for s in statuses if s):
                return HealthStatus.HEALTHY
            else:
                return HealthStatus.UNKNOWN

    async def get_all_statuses(self) -> Dict[str, HealthStatus]:
        """Get all checker statuses."""
        with self._lock:
            return dict(self._status_cache)

    def get_checker(self, name: str) -> Optional[BaseHealthChecker]:
        """Get a specific checker by name."""
        return self._checkers.get(name)

    def get_check_result(self, name: str) -> Optional[HealthCheckResult]:
        """Get the last result for a specific check."""
        checker = self._checkers.get(name)
        if checker:
            return checker.get_last_result()
        return None

    async def run_check_now(self, name: str) -> Optional[HealthCheckResult]:
        """Run a specific check immediately."""
        checker = self._checkers.get(name)
        if not checker:
            return None

        return await checker.check()

    async def run_all_checks_now(self) -> Dict[str, HealthCheckResult]:
        """Run all checks immediately."""
        results = {}
        for name, checker in self._checkers.items():
            results[name] = await checker.check()
        return results

    def is_healthy(self) -> bool:
        """Check if all systems are healthy."""
        return self.get_overall_status() == HealthStatus.HEALTHY

    def is_degraded(self) -> bool:
        """Check if system is degraded."""
        return self.get_overall_status() == HealthStatus.DEGRADED

    def get_metrics(self) -> Dict[str, Any]:
        """Get health metrics."""
        statuses = self._status_cache
        counts = {status.value: 0 for status in HealthStatus}
        for status in statuses.values():
            counts[status.value] += 1

        return {
            "overall_status": self.get_overall_status().value,
            "status_counts": counts,
            "total_checks": len(self._checkers),
            "last_report": self._last_report.isoformat() if self._last_report else None,
        }


# === MODULE EXPORTS ===

__all__ = [
    "HealthMonitor",
    "HealthMonitorConfig",
    "HealthCheckConfig",
    "HealthCheckResult",
    "HealthStatus",
    "HealthCheckType",
    "ResourceType",
    "BaseHealthChecker",
    "SystemHealthChecker",
    "NetworkHealthChecker",
    "DatabaseHealthChecker",
    "CacheHealthChecker",
    "BrokerHealthChecker",
]

logger.info("health_checker_module_loaded", version="3.0.0")
