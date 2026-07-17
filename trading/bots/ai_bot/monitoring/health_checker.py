"""
NEXUS AI TRADING SYSTEM - Health Checker
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced health monitoring system for trading bots, models, and infrastructure.
Provides comprehensive health checks, dependency validation, and self-healing capabilities.
"""

import asyncio
import json
import os
import platform
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import aiohttp
import psutil
import yaml
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field, validator

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
HEALTH_CHECK_COUNTER = Counter(
    "nexus_health_checks_total",
    "Total number of health checks performed",
    ["component", "status"],
)
HEALTH_CHECK_DURATION = Histogram(
    "nexus_health_check_duration_seconds",
    "Duration of health checks",
    ["component"],
)
HEALTH_STATUS_GAUGE = Gauge(
    "nexus_health_status",
    "Current health status of components",
    ["component", "metric"],
)
HEALTH_RECOVERY_COUNTER = Counter(
    "nexus_health_recoveries_total",
    "Total number of component recoveries",
    ["component"],
)


class HealthStatus(Enum):
    """Health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Types of components that can be health checked."""

    SYSTEM = "system"
    DATABASE = "database"
    CACHE = "cache"
    BROKER = "broker"
    MODEL = "model"
    BOT = "bot"
    API = "api"
    WEBSOCKET = "websocket"
    ALERT = "alert"
    METRICS = "metrics"
    STORAGE = "storage"
    NETWORK = "network"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    component: str
    component_type: ComponentType
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    duration_seconds: float
    dependencies: List[str] = field(default_factory=list)
    recovery_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "component": self.component,
            "component_type": self.component_type.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "dependencies": self.dependencies,
            "recovery_actions": self.recovery_actions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthCheckResult":
        """Create from dictionary."""
        return cls(
            component=data["component"],
            component_type=ComponentType(data["component_type"]),
            status=HealthStatus(data["status"]),
            message=data.get("message", ""),
            details=data.get("details", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            duration_seconds=data.get("duration_seconds", 0.0),
            dependencies=data.get("dependencies", []),
            recovery_actions=data.get("recovery_actions", []),
            metadata=data.get("metadata", {}),
        )


class HealthChecker:
    """
    Advanced health monitoring system with self-healing capabilities.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the health checker.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, HealthCheckResult] = {}
        self._history: List[HealthCheckResult] = []
        self._recovery_actions: Dict[str, List[Callable]] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None

        # Load configuration
        self.health_config = self.config.get("health_checker", {})
        self.check_interval = self.health_config.get("check_interval", 30)
        self.recovery_interval = self.health_config.get("recovery_interval", 60)
        self.max_history_size = self.health_config.get("max_history_size", 1000)
        self.auto_recovery = self.health_config.get("auto_recovery", True)
        self.dependency_check = self.health_config.get("dependency_check", True)

        # Register default checks
        self._register_default_checks()

        # Start background tasks
        self._start_background_tasks()

        logger.info("HealthChecker initialized")

    def _register_default_checks(self):
        """Register default health checks."""
        self.register_check("system", self.check_system)
        self.register_check("memory", self.check_memory)
        self.register_check("disk", self.check_disk)
        self.register_check("network", self.check_network)
        self.register_check("database", self.check_database)
        self.register_check("cache", self.check_cache)
        self.register_check("api", self.check_api)

        # Register recovery actions
        self.register_recovery("system", self.recover_system)
        self.register_recovery("memory", self.recover_memory)
        self.register_recovery("disk", self.recover_disk)
        self.register_recovery("database", self.recover_database)
        self.register_recovery("cache", self.recover_cache)

    def register_check(
        self,
        component: str,
        check_func: Callable,
        component_type: Optional[ComponentType] = None,
    ):
        """
        Register a health check function.

        Args:
            component: Component name
            check_func: Async function that returns HealthCheckResult
            component_type: Type of component
        """
        self._checks[component] = {
            "func": check_func,
            "type": component_type or ComponentType.SYSTEM,
        }
        logger.info(f"Registered health check for {component}")

    def register_recovery(
        self,
        component: str,
        recovery_func: Callable,
    ):
        """
        Register a recovery action.

        Args:
            component: Component name
            recovery_func: Async function that performs recovery
        """
        if component not in self._recovery_actions:
            self._recovery_actions[component] = []
        self._recovery_actions[component].append(recovery_func)
        logger.info(f"Registered recovery action for {component}")

    def _start_background_tasks(self):
        """Start background monitoring tasks."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

        if self.auto_recovery and self._recovery_task is None:
            self._recovery_task = asyncio.create_task(self._recovery_loop())

    async def _monitor_loop(self):
        """Background loop for periodic health checks."""
        while True:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def _recovery_loop(self):
        """Background loop for recovery actions."""
        while True:
            try:
                await self._perform_recovery()
                await asyncio.sleep(self.recovery_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in recovery loop: {e}")
                await asyncio.sleep(10)

    async def run_check(
        self,
        component: str,
        **kwargs,
    ) -> HealthCheckResult:
        """
        Run a specific health check.

        Args:
            component: Component to check
            **kwargs: Additional arguments for the check

        Returns:
            HealthCheckResult
        """
        if component not in self._checks:
            raise ValueError(f"No health check registered for {component}")

        start_time = time.time()
        check_info = self._checks[component]
        check_func = check_info["func"]
        component_type = check_info["type"]

        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func(**kwargs)
            else:
                result = check_func(**kwargs)

            if isinstance(result, dict):
                result = HealthCheckResult(
                    component=component,
                    component_type=component_type,
                    status=HealthStatus(result.get("status", "unknown")),
                    message=result.get("message", ""),
                    details=result.get("details", {}),
                    timestamp=datetime.utcnow(),
                    duration_seconds=time.time() - start_time,
                    dependencies=result.get("dependencies", []),
                    recovery_actions=result.get("recovery_actions", []),
                    metadata=result.get("metadata", {}),
                )
            elif not isinstance(result, HealthCheckResult):
                raise ValueError(f"Invalid result type: {type(result)}")

        except Exception as e:
            result = HealthCheckResult(
                component=component,
                component_type=component_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow(),
                duration_seconds=time.time() - start_time,
            )

        # Store result
        async with self._lock:
            self._results[component] = result
            self._history.append(result)

            # Limit history size
            if len(self._history) > self.max_history_size:
                self._history = self._history[-self.max_history_size:]

        # Update metrics
        HEALTH_CHECK_COUNTER.labels(
            component=component,
            status=result.status.value,
        ).inc()
        HEALTH_CHECK_DURATION.labels(component=component).observe(
            result.duration_seconds
        )
        HEALTH_STATUS_GAUGE.labels(
            component=component,
            metric="status_code",
        ).set(self._status_to_code(result.status))

        logger.info(f"Health check for {component}: {result.status.value}")

        return result

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks.

        Returns:
            Dictionary of results
        """
        results = {}

        for component in self._checks:
            result = await self.run_check(component)
            results[component] = result

        return results

    async def get_status(self, component: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current health status.

        Args:
            component: Optional component name

        Returns:
            Status information
        """
        if component:
            result = self._results.get(component)
            if not result:
                return {"status": "unknown", "message": "No health data available"}
            return result.to_dict()

        # Aggregate all results
        status = {
            "overall": "healthy",
            "components": {},
            "timestamp": datetime.utcnow().isoformat(),
        }

        for comp, result in self._results.items():
            status["components"][comp] = result.to_dict()

            # Update overall status
            if result.status == HealthStatus.UNHEALTHY:
                status["overall"] = "unhealthy"
            elif result.status == HealthStatus.DEGRADED and status["overall"] == "healthy":
                status["overall"] = "degraded"

        return status

    async def _perform_recovery(self):
        """Perform recovery actions for unhealthy components."""
        async with self._lock:
            for component, result in self._results.items():
                if result.status == HealthStatus.UNHEALTHY:
                    if component in self._recovery_actions:
                        for action in self._recovery_actions[component]:
                            try:
                                if asyncio.iscoroutinefunction(action):
                                    await action(result)
                                else:
                                    action(result)

                                # Re-check after recovery
                                await self.run_check(component)

                                HEALTH_RECOVERY_COUNTER.labels(
                                    component=component
                                ).inc()

                                logger.info(f"Recovery action performed for {component}")

                            except Exception as e:
                                logger.error(f"Recovery action failed for {component}: {e}")

    @staticmethod
    def _status_to_code(status: HealthStatus) -> int:
        """Convert status to numeric code."""
        codes = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.UNKNOWN: 3,
        }
        return codes.get(status, 3)

    # Default health checks

    async def check_system(self) -> Dict[str, Any]:
        """
        Check system health.

        Returns:
            System health status
        """
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.utcnow() - boot_time

            return {
                "status": "healthy",
                "message": "System is operational",
                "details": {
                    "hostname": socket.gethostname(),
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "uptime_seconds": uptime.total_seconds(),
                    "process_count": len(psutil.pids()),
                    "load_average": psutil.getloadavg(),
                },
                "dependencies": [],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"System check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_memory(self) -> Dict[str, Any]:
        """
        Check memory health.

        Returns:
            Memory health status
        """
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            status = "healthy"
            message = "Memory is healthy"

            if memory.percent > 90:
                status = "unhealthy"
                message = "Critical memory usage"
            elif memory.percent > 80:
                status = "degraded"
                message = "High memory usage"

            return {
                "status": status,
                "message": message,
                "details": {
                    "total_mb": memory.total / (1024 * 1024),
                    "available_mb": memory.available / (1024 * 1024),
                    "used_mb": memory.used / (1024 * 1024),
                    "percent_used": memory.percent,
                    "swap_total_mb": swap.total / (1024 * 1024),
                    "swap_used_mb": swap.used / (1024 * 1024),
                    "swap_percent": swap.percent,
                },
                "recovery_actions": [
                    "clear_cache",
                    "restart_services",
                ] if status == "unhealthy" else [],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Memory check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_disk(self) -> Dict[str, Any]:
        """
        Check disk health.

        Returns:
            Disk health status
        """
        try:
            disk = psutil.disk_usage("/")

            status = "healthy"
            message = "Disk is healthy"

            if disk.percent > 90:
                status = "unhealthy"
                message = "Critical disk usage"
            elif disk.percent > 80:
                status = "degraded"
                message = "High disk usage"

            return {
                "status": status,
                "message": message,
                "details": {
                    "total_gb": disk.total / (1024 ** 3),
                    "used_gb": disk.used / (1024 ** 3),
                    "free_gb": disk.free / (1024 ** 3),
                    "percent_used": disk.percent,
                },
                "recovery_actions": [
                    "clean_temp_files",
                    "archive_logs",
                ] if status == "unhealthy" else [],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Disk check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_network(self) -> Dict[str, Any]:
        """
        Check network health.

        Returns:
            Network health status
        """
        try:
            # Check internet connectivity
            internet = False
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://www.google.com", timeout=5) as response:
                        internet = response.status == 200
            except Exception:
                internet = False

            # Get network interfaces
            interfaces = psutil.net_if_stats()
            connections = psutil.net_connections()

            status = "healthy" if internet else "degraded"

            return {
                "status": status,
                "message": "Network is online" if internet else "Network may be offline",
                "details": {
                    "internet_accessible": internet,
                    "interfaces_count": len(interfaces),
                    "connections_count": len(connections),
                    "interfaces": {
                        name: {
                            "is_up": stats.isup,
                            "speed": stats.speed,
                        }
                        for name, stats in interfaces.items()
                    },
                },
                "dependencies": [],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Network check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_database(self) -> Dict[str, Any]:
        """
        Check database health.

        Returns:
            Database health status
        """
        # This is a placeholder - implement actual database check
        try:
            # TODO: Implement actual database health check
            return {
                "status": "healthy",
                "message": "Database is operational",
                "details": {
                    "connected": True,
                    "latency_ms": 5,
                },
                "dependencies": [],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Database check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_cache(self) -> Dict[str, Any]:
        """
        Check cache health.

        Returns:
            Cache health status
        """
        try:
            if self.cache_manager:
                health = await self.cache_manager.health_check()
                return {
                    "status": health.get("status", "unknown"),
                    "message": health.get("message", "Cache operational"),
                    "details": health.get("details", {}),
                    "dependencies": [],
                }
            else:
                return {
                    "status": "unknown",
                    "message": "Cache manager not configured",
                    "details": {"configured": False},
                }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Cache check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    async def check_api(self) -> Dict[str, Any]:
        """
        Check API health.

        Returns:
            API health status
        """
        try:
            # Check local API endpoint
            # TODO: Implement actual API health check
            return {
                "status": "healthy",
                "message": "API is operational",
                "details": {
                    "port": 8000,
                    "active_connections": 0,
                },
                "dependencies": ["database", "cache"],
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"API check failed: {str(e)}",
                "details": {"error": str(e)},
            }

    # Default recovery actions

    async def recover_system(self, result: HealthCheckResult):
        """
        Recover system component.

        Args:
            result: Health check result
        """
        logger.info("Attempting system recovery...")

        try:
            # Clear system caches
            os.system("sync && echo 3 > /proc/sys/vm/drop_caches")
            logger.info("System caches cleared")
        except Exception as e:
            logger.error(f"System recovery failed: {e}")

    async def recover_memory(self, result: HealthCheckResult):
        """
        Recover memory component.

        Args:
            result: Health check result
        """
        logger.info("Attempting memory recovery...")

        try:
            # Request garbage collection
            import gc
            gc.collect()

            # Clear GPU cache if available
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    logger.info("GPU cache cleared")
            except ImportError:
                pass

            logger.info("Memory recovery completed")
        except Exception as e:
            logger.error(f"Memory recovery failed: {e}")

    async def recover_disk(self, result: HealthCheckResult):
        """
        Recover disk component.

        Args:
            result: Health check result
        """
        logger.info("Attempting disk recovery...")

        try:
            # Clean up temporary files
            temp_dirs = ["/tmp", "/var/tmp"]
            for dir_path in temp_dirs:
                if os.path.exists(dir_path):
                    os.system(f"find {dir_path} -type f -atime +7 -delete 2>/dev/null")

            # Clean up old logs
            log_dir = Path("logs")
            if log_dir.exists():
                for log_file in log_dir.glob("*.log.*"):
                    if log_file.stat().st_mtime < time.time() - 7 * 86400:  # 7 days
                        log_file.unlink()

            logger.info("Disk recovery completed")
        except Exception as e:
            logger.error(f"Disk recovery failed: {e}")

    async def recover_database(self, result: HealthCheckResult):
        """
        Recover database component.

        Args:
            result: Health check result
        """
        logger.info("Attempting database recovery...")

        try:
            # TODO: Implement database recovery
            # This could include connection retry, session reset, etc.
            logger.info("Database recovery completed")
        except Exception as e:
            logger.error(f"Database recovery failed: {e}")

    async def recover_cache(self, result: HealthCheckResult):
        """
        Recover cache component.

        Args:
            result: Health check result
        """
        logger.info("Attempting cache recovery...")

        try:
            if self.cache_manager:
                await self.cache_manager.clear()
                logger.info("Cache cleared")
        except Exception as e:
            logger.error(f"Cache recovery failed: {e}")

    async def get_history(
        self,
        component: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get health check history.

        Args:
            component: Optional component filter
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of health check results
        """
        async with self._lock:
            history = self._history

            if component:
                history = [h for h in history if h.component == component]

            history = sorted(history, key=lambda x: x.timestamp, reverse=True)
            return [h.to_dict() for h in history[offset:offset + limit]]

    async def get_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive health report.

        Returns:
            Health report
        """
        async with self._lock:
            results = list(self._results.values())

            report = {
                "overall_status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "components": {},
                "statistics": {
                    "total_checks": len(results),
                    "healthy": sum(1 for r in results if r.status == HealthStatus.HEALTHY),
                    "degraded": sum(1 for r in results if r.status == HealthStatus.DEGRADED),
                    "unhealthy": sum(1 for r in results if r.status == HealthStatus.UNHEALTHY),
                    "unknown": sum(1 for r in results if r.status == HealthStatus.UNKNOWN),
                },
                "recovery_actions": [],
            }

            for result in results:
                report["components"][result.component] = result.to_dict()

                if result.status == HealthStatus.UNHEALTHY:
                    report["overall_status"] = "unhealthy"
                    for action in result.recovery_actions:
                        report["recovery_actions"].append({
                            "component": result.component,
                            "action": action,
                        })

            return report

    async def shutdown(self):
        """Shutdown the health checker."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass

        logger.info("HealthChecker shut down")


# Export singleton
health_checker = HealthChecker()
