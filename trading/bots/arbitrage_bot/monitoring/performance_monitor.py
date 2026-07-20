# trading/bots/arbitrage_bot/monitoring/performance_monitor.py
# NEXUS AI TRADING SYSTEM - PERFORMANCE MONITOR
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive performance monitoring for the arbitrage bot,
# including latency tracking, throughput analysis, resource utilization, and
# performance optimization recommendations.
# ====================================================================================

"""
NEXUS Arbitrage Bot Performance Monitor

This module provides comprehensive performance monitoring for:
- System performance (CPU, memory, disk, network)
- Application performance (latency, throughput, errors)
- Exchange performance (API latency, success rates)
- Trade performance (execution time, slippage)
- Strategy performance (profitability, win rate)
- Performance trend analysis
- Optimization recommendations
- Performance alerting
"""

import asyncio
import logging
import time
import psutil
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import aiohttp

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.models.latency import LatencyMeasurement, LatencyStatistics
from trading.bots.arbitrage_bot.models.performance import PerformanceMetrics

logger = logging.getLogger("nexus.arbitrage.performance_monitor")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class PerformanceMetric(str, Enum):
    """Performance metric types."""
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    EXECUTION_TIME = "execution_time"
    SLIPPAGE = "slippage"


class PerformanceSeverity(str, Enum):
    """Performance issue severity."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class PerformanceStatus(str, Enum):
    """Performance status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class PerformanceDataPoint:
    """
    Single performance data point.
    """
    metric: str
    value: float
    unit: str
    timestamp: datetime
    labels: Dict[str, str]
    metadata: Dict[str, Any]


@dataclass
class PerformanceThreshold:
    """
    Performance threshold definition.
    """
    metric: str
    warning_threshold: float
    critical_threshold: float
    severity: PerformanceSeverity
    unit: str


@dataclass
class PerformanceIssue:
    """
    Performance issue detected.
    """
    issue_id: str
    metric: str
    description: str
    current_value: float
    threshold_value: float
    severity: PerformanceSeverity
    timestamp: datetime
    recommendations: List[str]


@dataclass
class PerformanceReport:
    """
    Performance report.
    """
    period_start: datetime
    period_end: datetime
    status: PerformanceStatus
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    issues: List[PerformanceIssue]
    recommendations: List[str]


# ====================================================================================
# PERFORMANCE MONITOR
# ====================================================================================

class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    Features:
    - Real-time performance monitoring
    - Latency tracking and analysis
    - Throughput monitoring
    - Resource utilization tracking
    - Performance trend analysis
    - Threshold-based alerting
    - Optimization recommendations
    - Performance reporting
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the performance monitor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Performance data
        self._data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._latency_data: deque = deque(maxlen=1000)
        self._execution_times: deque = deque(maxlen=1000)
        self._slippage_data: deque = deque(maxlen=1000)
        
        # Thresholds
        self._thresholds: Dict[str, PerformanceThreshold] = {}
        self._register_default_thresholds()
        
        # Issues
        self._issues: List[PerformanceIssue] = []
        self._issue_history: deque = deque(maxlen=1000)
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_performance_monitor",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # Status
        self._status = PerformanceStatus.EXCELLENT
        self._last_check = datetime.utcnow()
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Start time
        self._start_time = datetime.utcnow()
        
        # System metrics
        self._system_metrics: Dict[str, float] = {}
        
        logger.info("PerformanceMonitor initialized (version=3.0.0)")
        
    def _register_default_thresholds(self) -> None:
        """Register default performance thresholds."""
        self.set_threshold("latency_p95", 100, 200, PerformanceSeverity.HIGH, "ms")
        self.set_threshold("latency_p99", 200, 500, PerformanceSeverity.CRITICAL, "ms")
        self.set_threshold("error_rate", 0.05, 0.10, PerformanceSeverity.HIGH, "%")
        self.set_threshold("success_rate", 99.5, 99.0, PerformanceSeverity.HIGH, "%")
        self.set_threshold("cpu_usage", 70, 90, PerformanceSeverity.MEDIUM, "%")
        self.set_threshold("memory_usage", 80, 95, PerformanceSeverity.HIGH, "%")
        self.set_threshold("execution_time_p95", 1000, 2000, PerformanceSeverity.MEDIUM, "ms")
        self.set_threshold("slippage_p95", 0.1, 0.5, PerformanceSeverity.MEDIUM, "%")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_gauge("performance_cpu_percent", "CPU usage percentage")
        self._metrics.register_gauge("performance_memory_percent", "Memory usage percentage")
        self._metrics.register_gauge("performance_latency_p95", "95th percentile latency in ms")
        self._metrics.register_gauge("performance_latency_p99", "99th percentile latency in ms")
        self._metrics.register_gauge("performance_error_rate", "Error rate")
        self._metrics.register_gauge("performance_success_rate", "Success rate")
        self._metrics.register_counter("performance_issues", "Performance issues detected")
        
    def set_threshold(
        self,
        metric: str,
        warning_threshold: float,
        critical_threshold: float,
        severity: PerformanceSeverity,
        unit: str
    ) -> None:
        """
        Set performance threshold.
        
        Args:
            metric: Metric name
            warning_threshold: Warning threshold value
            critical_threshold: Critical threshold value
            severity: Severity level
            unit: Unit of measurement
        """
        self._thresholds[metric] = PerformanceThreshold(
            metric=metric,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            severity=severity,
            unit=unit
        )
        logger.info(f"Threshold set for {metric}: warning={warning_threshold}, critical={critical_threshold}")
        
    async def initialize(self) -> None:
        """Initialize the performance monitor."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("PerformanceMonitor initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # System metrics collection
        task = asyncio.create_task(self._system_metrics_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Performance check loop
        task = asyncio.create_task(self._performance_check_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics update loop
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _system_metrics_loop(self) -> None:
        """Collect system metrics periodically."""
        while self._running:
            try:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                self._system_metrics["cpu_usage"] = cpu_percent
                self.record("cpu_usage", cpu_percent, "%")
                
                # Memory
                memory = psutil.virtual_memory()
                self._system_metrics["memory_usage"] = memory.percent
                self._system_metrics["memory_used_mb"] = memory.used / (1024 * 1024)
                self._system_metrics["memory_total_mb"] = memory.total / (1024 * 1024)
                self.record("memory_usage", memory.percent, "%")
                
                # Disk
                disk = psutil.disk_usage('/')
                self._system_metrics["disk_usage"] = disk.percent
                self.record("disk_usage", disk.percent, "%")
                
                # Network
                net_io = psutil.net_io_counters()
                self._system_metrics["net_sent_mb"] = net_io.bytes_sent / (1024 * 1024)
                self._system_metrics["net_recv_mb"] = net_io.bytes_recv / (1024 * 1024)
                
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System metrics collection error: {e}")
                await asyncio.sleep(30)
                
    async def _performance_check_loop(self) -> None:
        """Check performance against thresholds."""
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._check_performance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance check error: {e}")
                
    async def _metrics_update_loop(self) -> None:
        """Update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(60)
                
                # Update core metrics
                self._metrics.set_gauge("performance_cpu_percent", self._system_metrics.get("cpu_usage", 0))
                self._metrics.set_gauge("performance_memory_percent", self._system_metrics.get("memory_usage", 0))
                
                # Calculate latency percentiles
                if self._latency_data:
                    latencies = [d.value for d in self._latency_data if d.metric == "latency"]
                    if latencies:
                        self._metrics.set_gauge("performance_latency_p95", statistics.percentile(latencies, 95))
                        self._metrics.set_gauge("performance_latency_p99", statistics.percentile(latencies, 99))
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
                
    def record(
        self,
        metric: str,
        value: float,
        unit: str = "",
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a performance data point.
        
        Args:
            metric: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Metric labels
            metadata: Additional metadata
        """
        data_point = PerformanceDataPoint(
            metric=metric,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            labels=labels or {},
            metadata=metadata or {}
        )
        
        self._data[metric].append(data_point)
        
        # Store in specific collections for analysis
        if metric == "latency":
            self._latency_data.append(data_point)
        elif metric == "execution_time":
            self._execution_times.append(data_point)
        elif metric == "slippage":
            self._slippage_data.append(data_point)
            
    async def _check_performance(self) -> None:
        """Check performance against thresholds."""
        self._last_check = datetime.utcnow()
        issues = []
        
        for metric, threshold in self._thresholds.items():
            data = self._data.get(metric, deque())
            if not data:
                continue
                
            # Calculate current value (use latest or percentile)
            current_value = data[-1].value
            
            # Check against thresholds
            if current_value >= threshold.critical_threshold:
                severity = PerformanceSeverity.CRITICAL
                issue_desc = f"{metric} is critically high: {current_value:.2f} {threshold.unit} (threshold: {threshold.critical_threshold})"
            elif current_value >= threshold.warning_threshold:
                severity = PerformanceSeverity.HIGH
                issue_desc = f"{metric} is high: {current_value:.2f} {threshold.unit} (threshold: {threshold.warning_threshold})"
            else:
                continue
                
            # Create issue
            issue = PerformanceIssue(
                issue_id=f"PERF-{datetime.utcnow().strftime('%Y%m%d')}-{len(self._issues)+1:04d}",
                metric=metric,
                description=issue_desc,
                current_value=current_value,
                threshold_value=threshold.warning_threshold if severity == PerformanceSeverity.HIGH else threshold.critical_threshold,
                severity=severity,
                timestamp=datetime.utcnow(),
                recommendations=self._get_recommendations(metric, current_value)
            )
            
            issues.append(issue)
            self._issues.append(issue)
            self._issue_history.append(issue)
            self._metrics.increment_counter("performance_issues")
            
        # Update status
        if issues:
            if any(i.severity == PerformanceSeverity.CRITICAL for i in issues):
                self._status = PerformanceStatus.CRITICAL
            elif any(i.severity == PerformanceSeverity.HIGH for i in issues):
                self._status = PerformanceStatus.POOR
            else:
                self._status = PerformanceStatus.FAIR
        else:
            self._status = PerformanceStatus.EXCELLENT
            
        if issues:
            logger.warning(f"Performance issues detected: {len(issues)}")
            for issue in issues:
                logger.warning(f"  {issue.description}")
                
    def _get_recommendations(self, metric: str, current_value: float) -> List[str]:
        """
        Get performance optimization recommendations.
        
        Args:
            metric: Metric name
            current_value: Current value
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if metric == "cpu_usage":
            if current_value > 80:
                recommendations.append("Consider scaling up resources or optimizing code")
            if current_value > 90:
                recommendations.append("Immediate action required: reduce load or scale up")
                
        elif metric == "memory_usage":
            if current_value > 80:
                recommendations.append("Check for memory leaks and optimize memory usage")
            if current_value > 90:
                recommendations.append("Immediate action: increase memory or restart service")
                
        elif metric in ["latency_p95", "latency_p99"]:
            if current_value > 100:
                recommendations.append("Optimize network connections and reduce latency")
            if current_value > 200:
                recommendations.append("Consider moving to closer region or optimizing code")
                
        elif metric == "error_rate":
            if current_value > 0.05:
                recommendations.append("Investigate error logs and fix root causes")
            if current_value > 0.10:
                recommendations.append("Critical: Immediate action required to reduce errors")
                
        elif metric == "execution_time_p95":
            if current_value > 1000:
                recommendations.append("Optimize order execution path")
            if current_value > 2000:
                recommendations.append("Critical: Reduce execution complexity")
                
        return recommendations or ["Monitor performance and investigate root cause"]
        
    def get_latency_stats(self) -> Dict[str, float]:
        """
        Get latency statistics.
        
        Returns:
            Latency statistics
        """
        latencies = [d.value for d in self._latency_data if d.metric == "latency"]
        if not latencies:
            return {}
            
        return {
            "min": min(latencies),
            "max": max(latencies),
            "avg": sum(latencies) / len(latencies),
            "p50": statistics.percentile(latencies, 50),
            "p90": statistics.percentile(latencies, 90),
            "p95": statistics.percentile(latencies, 95),
            "p99": statistics.percentile(latencies, 99)
        }
        
    def get_throughput_stats(self) -> Dict[str, float]:
        """
        Get throughput statistics.
        
        Returns:
            Throughput statistics
        """
        # Calculate throughput from execution times
        times = [d.value for d in self._execution_times]
        if not times:
            return {}
            
        return {
            "avg": sum(times) / len(times),
            "p50": statistics.percentile(times, 50),
            "p90": statistics.percentile(times, 90),
            "p95": statistics.percentile(times, 95)
        }
        
    def get_system_metrics(self) -> Dict[str, float]:
        """
        Get system metrics.
        
        Returns:
            System metrics
        """
        return self._system_metrics.copy()
        
    def get_performance_report(self) -> PerformanceReport:
        """
        Get comprehensive performance report.
        
        Returns:
            Performance report
        """
        return PerformanceReport(
            period_start=self._start_time,
            period_end=datetime.utcnow(),
            status=self._status,
            summary=self._get_summary(),
            metrics={
                "latency": self.get_latency_stats(),
                "throughput": self.get_throughput_stats(),
                "system": self.get_system_metrics()
            },
            issues=self._issues[-10:],
            recommendations=self._get_global_recommendations()
        )
        
    def _get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        latency_stats = self.get_latency_stats()
        system_metrics = self.get_system_metrics()
        
        return {
            "status": self._status.value,
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "last_check": self._last_check.isoformat(),
            "total_issues": len(self._issues),
            "open_issues": len([i for i in self._issues if i.severity in [PerformanceSeverity.HIGH, PerformanceSeverity.CRITICAL]]),
            "latency_p95": latency_stats.get("p95", 0),
            "latency_p99": latency_stats.get("p99", 0),
            "cpu_usage": system_metrics.get("cpu_usage", 0),
            "memory_usage": system_metrics.get("memory_usage", 0)
        }
        
    def _get_global_recommendations(self) -> List[str]:
        """Get global performance recommendations."""
        recommendations = []
        
        if self._status in [PerformanceStatus.POOR, PerformanceStatus.CRITICAL]:
            recommendations.append("Immediate performance intervention required")
            
        latency_stats = self.get_latency_stats()
        if latency_stats.get("p95", 0) > 100:
            recommendations.append("Optimize latency: reduce network and processing delays")
            
        system_metrics = self.get_system_metrics()
        if system_metrics.get("cpu_usage", 0) > 70:
            recommendations.append("High CPU usage: consider optimizing code or scaling up")
            
        if system_metrics.get("memory_usage", 0) > 80:
            recommendations.append("High memory usage: check for memory leaks and optimize")
            
        open_issues = len([i for i in self._issues if i.severity in [PerformanceSeverity.HIGH, PerformanceSeverity.CRITICAL]])
        if open_issues > 0:
            recommendations.append(f"Address {open_issues} open performance issues")
            
        return recommendations or ["Performance is within acceptable ranges"]
        
    def get_issue_history(
        self,
        limit: int = 100,
        severity: Optional[PerformanceSeverity] = None
    ) -> List[PerformanceIssue]:
        """
        Get performance issue history.
        
        Args:
            limit: Maximum results
            severity: Filter by severity
            
        Returns:
            List of issues
        """
        issues = list(self._issue_history)
        if severity:
            issues = [i for i in issues if i.severity == severity]
        return issues[-limit:]
        
    def clear_issues(self) -> None:
        """Clear resolved issues."""
        self._issues = []
        logger.info("Performance issues cleared")
        
    async def close(self) -> None:
        """Close the performance monitor."""
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
                    
        logger.info("PerformanceMonitor closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get the global performance monitor instance.
    
    Returns:
        PerformanceMonitor instance
    """
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = PerformanceMonitor()
    return _global_performance_monitor


def reset_performance_monitor() -> None:
    """Reset the global performance monitor instance."""
    global _global_performance_monitor
    if _global_performance_monitor:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_performance_monitor.close())
            else:
                asyncio.run(_global_performance_monitor.close())
        except Exception:
            pass
    _global_performance_monitor = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'PerformanceMetric',
    'PerformanceSeverity',
    'PerformanceStatus',
    
    # Data Models
    'PerformanceDataPoint',
    'PerformanceThreshold',
    'PerformanceIssue',
    'PerformanceReport',
    
    # Main Class
    'PerformanceMonitor',
    'get_performance_monitor',
    'reset_performance_monitor',
]
