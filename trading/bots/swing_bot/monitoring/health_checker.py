"""
Swing Bot Health Checker
==========================

This module provides health checking capabilities for the Swing Bot trading system.
"""

import time
import psutil
import threading
import asyncio
import socket
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
import requests
import redis
from pathlib import Path

from .notification_service import NotificationService


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    check_func: Callable[[], Tuple[bool, str]]
    interval: int = 60  # seconds
    timeout: int = 30   # seconds
    enabled: bool = True
    last_check: Optional[datetime] = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    last_message: str = ""
    consecutive_failures: int = 0
    success_count: int = 0
    failure_count: int = 0


@dataclass
class HealthReport:
    """Health check report."""
    status: HealthStatus
    timestamp: datetime
    checks: Dict[str, Dict[str, Any]]
    summary: Dict[str, Any]


class HealthChecker:
    """
    Monitor health of system components.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the health checker.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.checks: Dict[str, HealthCheck] = {}
        self.notification_service = NotificationService(self.config.get('notification', {}))
        self._lock = threading.RLock()
        self._running = False
        self._checker_thread: Optional[threading.Thread] = None
        self._alert_callbacks: List[Callable] = []
        
        # Register default health checks
        self._register_default_checks()
        
        if self.config.get('auto_start', True):
            self.start()
    
    def _register_default_checks(self) -> None:
        """Register default health checks."""
        self.register_check(
            name="system_cpu",
            check_func=self._check_cpu,
            interval=30
        )
        self.register_check(
            name="system_memory",
            check_func=self._check_memory,
            interval=30
        )
        self.register_check(
            name="system_disk",
            check_func=self._check_disk,
            interval=60
        )
        self.register_check(
            name="network",
            check_func=self._check_network,
            interval=60
        )
        self.register_check(
            name="database",
            check_func=self._check_database,
            interval=60
        )
        self.register_check(
            name="redis",
            check_func=self._check_redis,
            interval=60
        )
    
    def register_check(
        self,
        name: str,
        check_func: Callable[[], Tuple[bool, str]],
        interval: int = 60,
        timeout: int = 30,
        enabled: bool = True
    ) -> None:
        """
        Register a health check.
        
        Args:
            name: Check name
            check_func: Check function returning (is_healthy, message)
            interval: Check interval in seconds
            timeout: Check timeout in seconds
            enabled: Whether the check is enabled
        """
        with self._lock:
            self.checks[name] = HealthCheck(
                name=name,
                check_func=check_func,
                interval=interval,
                timeout=timeout,
                enabled=enabled
            )
    
    def start(self) -> None:
        """Start the health checker."""
        if self._running:
            return
        
        self._running = True
        self._checker_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._checker_thread.start()
        logging.info("Health checker started")
    
    def stop(self) -> None:
        """Stop the health checker."""
        self._running = False
        if self._checker_thread:
            self._checker_thread.join(timeout=5)
        logging.info("Health checker stopped")
    
    def _check_loop(self) -> None:
        """Main health check loop."""
        while self._running:
            try:
                self._run_checks()
                time.sleep(5)
            except Exception as e:
                logging.error(f"Health check loop error: {e}")
    
    def _run_checks(self) -> None:
        """Run all enabled health checks."""
        now = datetime.now()
        results = []
        
        with self._lock:
            for check in self.checks.values():
                if not check.enabled:
                    continue
                
                # Check if it's time to run
                if check.last_check and (now - check.last_check).total_seconds() < check.interval:
                    continue
                
                try:
                    is_healthy, message = self._run_check(check)
                    check.last_check = now
                    check.last_message = message
                    
                    if is_healthy:
                        check.last_status = HealthStatus.HEALTHY
                        check.success_count += 1
                        check.consecutive_failures = 0
                    else:
                        check.failure_count += 1
                        check.consecutive_failures += 1
                        
                        # Determine status based on consecutive failures
                        if check.consecutive_failures >= 3:
                            check.last_status = HealthStatus.UNHEALTHY
                        else:
                            check.last_status = HealthStatus.DEGRADED
                        
                        # Send alert on unhealthy
                        if check.consecutive_failures >= 3:
                            self._send_health_alert(check)
                    
                    results.append((check.name, check.last_status, check.last_message))
                    
                except Exception as e:
                    logging.error(f"Health check error for {check.name}: {e}")
                    check.last_check = now
                    check.last_message = f"Error: {str(e)}"
                    check.failure_count += 1
                    check.consecutive_failures += 1
                    check.last_status = HealthStatus.UNHEALTHY
                    
                    if check.consecutive_failures >= 3:
                        self._send_health_alert(check)
        
        # Notify subscribers
        if results and self._alert_callbacks:
            self._notify_subscribers(results)
    
    def _run_check(self, check: HealthCheck) -> Tuple[bool, str]:
        """
        Run a single health check with timeout.
        
        Args:
            check: Health check to run
        
        Returns:
            Tuple of (is_healthy, message)
        """
        result = [False, "Timeout"]
        
        def run_check():
            try:
                is_healthy, message = check.check_func()
                result[0] = is_healthy
                result[1] = message
            except Exception as e:
                result[0] = False
                result[1] = f"Error: {str(e)}"
        
        thread = threading.Thread(target=run_check, daemon=True)
        thread.start()
        thread.join(timeout=check.timeout)
        
        if thread.is_alive():
            return False, "Check timed out"
        
        return result[0], result[1]
    
    def _send_health_alert(self, check: HealthCheck) -> None:
        """Send an alert for an unhealthy check."""
        message = f"""
Health Check Alert: {check.name}

Status: {check.last_status.value}
Message: {check.last_message}
Consecutive Failures: {check.consecutive_failures}
Last Check: {check.last_check.strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        self.notification_service.send_alert(
            alert_type='health',
            message=message,
            severity='critical'
        )
    
    def _notify_subscribers(self, results: List[Tuple[str, HealthStatus, str]]) -> None:
        """Notify subscribers of health check results."""
        for callback in self._alert_callbacks:
            try:
                callback(results)
            except Exception as e:
                logging.error(f"Health callback error: {e}")
    
    def register_alert_callback(self, callback: Callable) -> None:
        """
        Register a callback for health alerts.
        
        Args:
            callback: Callback function
        """
        self._alert_callbacks.append(callback)
    
    def get_status(self) -> HealthStatus:
        """
        Get overall health status.
        
        Returns:
            Overall health status
        """
        with self._lock:
            if not self.checks:
                return HealthStatus.UNKNOWN
            
            unhealthy = []
            degraded = []
            
            for check in self.checks.values():
                if check.last_status == HealthStatus.UNHEALTHY:
                    unhealthy.append(check.name)
                elif check.last_status == HealthStatus.DEGRADED:
                    degraded.append(check.name)
            
            if unhealthy:
                return HealthStatus.UNHEALTHY
            elif degraded:
                return HealthStatus.DEGRADED
            else:
                return HealthStatus.HEALTHY
    
    def get_report(self) -> HealthReport:
        """
        Generate a health report.
        
        Returns:
            Health report
        """
        with self._lock:
            checks = {}
            summary = {
                'total': len(self.checks),
                'healthy': 0,
                'degraded': 0,
                'unhealthy': 0,
                'unknown': 0
            }
            
            for name, check in self.checks.items():
                checks[name] = {
                    'status': check.last_status.value,
                    'message': check.last_message,
                    'last_check': check.last_check.isoformat() if check.last_check else None,
                    'success_count': check.success_count,
                    'failure_count': check.failure_count,
                    'consecutive_failures': check.consecutive_failures
                }
                
                if check.last_status == HealthStatus.HEALTHY:
                    summary['healthy'] += 1
                elif check.last_status == HealthStatus.DEGRADED:
                    summary['degraded'] += 1
                elif check.last_status == HealthStatus.UNHEALTHY:
                    summary['unhealthy'] += 1
                else:
                    summary['unknown'] += 1
            
            return HealthReport(
                status=self.get_status(),
                timestamp=datetime.now(),
                checks=checks,
                summary=summary
            )
    
    def run_check_now(self, name: str) -> Tuple[bool, str]:
        """
        Run a specific health check immediately.
        
        Args:
            name: Check name
        
        Returns:
            Tuple of (is_healthy, message)
        """
        with self._lock:
            check = self.checks.get(name)
            if not check:
                return False, f"Check '{name}' not found"
            
            return self._run_check(check)
    
    # Default health checks
    
    def _check_cpu(self) -> Tuple[bool, str]:
        """Check CPU usage."""
        cpu_usage = psutil.cpu_percent(interval=0.1)
        threshold = self.config.get('cpu_threshold', 80)
        
        if cpu_usage > threshold:
            return False, f"CPU usage at {cpu_usage:.1f}% (threshold: {threshold}%)"
        return True, f"CPU usage at {cpu_usage:.1f}%"
    
    def _check_memory(self) -> Tuple[bool, str]:
        """Check memory usage."""
        memory = psutil.virtual_memory()
        threshold = self.config.get('memory_threshold', 85)
        
        if memory.percent > threshold:
            return False, f"Memory usage at {memory.percent:.1f}% (threshold: {threshold}%)"
        return True, f"Memory usage at {memory.percent:.1f}%"
    
    def _check_disk(self) -> Tuple[bool, str]:
        """Check disk usage."""
        disk = psutil.disk_usage('/')
        threshold = self.config.get('disk_threshold', 85)
        
        if disk.percent > threshold:
            return False, f"Disk usage at {disk.percent:.1f}% (threshold: {threshold}%)"
        return True, f"Disk usage at {disk.percent:.1f}%"
    
    def _check_network(self) -> Tuple[bool, str]:
        """Check network connectivity."""
        # Check DNS resolution
        try:
            socket.gethostbyname('8.8.8.8')
        except socket.gaierror:
            return False, "DNS resolution failed"
        
        # Check connectivity
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(('8.8.8.8', 53))
            sock.close()
            return True, "Network is reachable"
        except Exception as e:
            return False, f"Network check failed: {e}"
    
    def _check_database(self) -> Tuple[bool, str]:
        """Check database connectivity."""
        db_config = self.config.get('database', {})
        db_type = db_config.get('type', 'postgresql')
        
        if db_type == 'postgresql':
            return self._check_postgresql()
        elif db_type == 'mysql':
            return self._check_mysql()
        elif db_type == 'mongodb':
            return self._check_mongodb()
        else:
            return True, f"Database type {db_type} not configured"
    
    def _check_postgresql(self) -> Tuple[bool, str]:
        """Check PostgreSQL connectivity."""
        try:
            import psycopg2
            db_config = self.config.get('database', {})
            
            conn = psycopg2.connect(
                host=db_config.get('host', 'localhost'),
                port=db_config.get('port', 5432),
                database=db_config.get('name', 'postgres'),
                user=db_config.get('user', 'postgres'),
                password=db_config.get('password', ''),
                connect_timeout=5
            )
            conn.close()
            return True, "PostgreSQL connection successful"
        except ImportError:
            return True, "PostgreSQL not installed"
        except Exception as e:
            return False, f"PostgreSQL connection failed: {e}"
    
    def _check_mysql(self) -> Tuple[bool, str]:
        """Check MySQL connectivity."""
        try:
            import mysql.connector
            db_config = self.config.get('database', {})
            
            conn = mysql.connector.connect(
                host=db_config.get('host', 'localhost'),
                port=db_config.get('port', 3306),
                database=db_config.get('name', 'mysql'),
                user=db_config.get('user', 'root'),
                password=db_config.get('password', ''),
                connection_timeout=5
            )
            conn.close()
            return True, "MySQL connection successful"
        except ImportError:
            return True, "MySQL not installed"
        except Exception as e:
            return False, f"MySQL connection failed: {e}"
    
    def _check_mongodb(self) -> Tuple[bool, str]:
        """Check MongoDB connectivity."""
        try:
            import pymongo
            db_config = self.config.get('database', {})
            
            client = pymongo.MongoClient(
                host=db_config.get('host', 'localhost'),
                port=db_config.get('port', 27017),
                serverSelectionTimeoutMS=5000
            )
            client.admin.command('ping')
            client.close()
            return True, "MongoDB connection successful"
        except ImportError:
            return True, "MongoDB not installed"
        except Exception as e:
            return False, f"MongoDB connection failed: {e}"
    
    def _check_redis(self) -> Tuple[bool, str]:
        """Check Redis connectivity."""
        try:
            redis_config = self.config.get('redis', {})
            
            if not redis_config.get('enabled', True):
                return True, "Redis not configured"
            
            client = redis.Redis(
                host=redis_config.get('host', 'localhost'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password', None),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            client.ping()
            return True, "Redis connection successful"
        except ImportError:
            return True, "Redis not installed"
        except Exception as e:
            return False, f"Redis connection failed: {e}"


class AsyncHealthChecker(HealthChecker):
    """Asynchronous version of the health checker."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._checker_task: Optional[asyncio.Task] = None
    
    async def start_async(self) -> None:
        """Start the async health checker."""
        if self._running:
            return
        
        self._running = True
        self._checker_task = asyncio.create_task(self._async_check_loop())
        logging.info("Async health checker started")
    
    async def stop_async(self) -> None:
        """Stop the async health checker."""
        self._running = False
        if self._checker_task:
            self._checker_task.cancel()
            try:
                await self._checker_task
            except asyncio.CancelledError:
                pass
        logging.info("Async health checker stopped")
    
    async def _async_check_loop(self) -> None:
        """Async health check loop."""
        while self._running:
            try:
                await asyncio.to_thread(self._run_checks)
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Async health check loop error: {e}")


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def check_health() -> HealthReport:
    """
    Get a health report.
    
    Returns:
        Health report
    """
    return get_health_checker().get_report()


__all__ = [
    'HealthStatus',
    'HealthCheck',
    'HealthReport',
    'HealthChecker',
    'AsyncHealthChecker',
    'get_health_checker',
    'check_health'
]
