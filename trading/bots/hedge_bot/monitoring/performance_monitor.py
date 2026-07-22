# trading/bots/hedge_bot/monitoring/performance_monitor.py

"""
NEXUS HEDGE BOT - PERFORMANCE MONITOR
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced performance monitoring system with real-time metrics,
profiling, bottleneck detection, and optimization recommendations.

Version: 3.0.0
"""

import asyncio
import cProfile
import io
import json
import linecache
import pstats
import sys
import threading
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
import os
import gc

import aiohttp
import psutil
import structlog
import yaml
from pydantic import BaseModel, Field, validator
import numpy as np
import pandas as pd

# Try to import py-spy for profiling
try:
    import py_spy
    PY_SPY_AVAILABLE = True
except ImportError:
    PY_SPY_AVAILABLE = False

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class PerformanceMetricType(str, Enum):
    """Types of performance metrics."""
    CPU = "cpu"
    MEMORY = "memory"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    IO = "io"
    NETWORK = "network"
    GC = "gc"
    THREAD = "thread"
    PROCESS = "process"
    CUSTOM = "custom"


class PerformanceAlertLevel(str, Enum):
    """Performance alert levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


# === DATA MODELS ===

@dataclass
class PerformanceSample:
    """Performance sample data point."""
    sample_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cpu_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_percent: float = 0.0
    thread_count: int = 0
    file_descriptors: int = 0
    gc_count: int = 0
    gc_time_ms: float = 0.0
    latency_ms: float = 0.0
    throughput: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceSample":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class PerformanceAlert:
    """Performance alert."""
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: PerformanceAlertLevel = PerformanceAlertLevel.WARNING
    metric_type: PerformanceMetricType = PerformanceMetricType.CPU
    metric_name: str = ""
    current_value: float = 0.0
    threshold_value: float = 0.0
    message: str = ""
    recommendation: str = ""
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "level": self.level.value,
            "metric_type": self.metric_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceAlert":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        data["level"] = PerformanceAlertLevel(data["level"])
        data["metric_type"] = PerformanceMetricType(data["metric_type"])
        return cls(**data)


# === PERFORMANCE MONITOR ===

class PerformanceMonitor:
    """
    Advanced performance monitoring system with real-time metrics,
    profiling, bottleneck detection, and optimization recommendations.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
    ):
        """
        Initialize the PerformanceMonitor.

        Args:
            config: Configuration dictionary or path to config file
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config

        self._lock = threading.RLock()
        self._closed = False

        # Database for persistent storage
        self._db_path = Path(self.config.get("db_path", "performance.db"))
        self._initialize_db()

        # In-memory storage
        self._samples: deque = deque(maxlen=10000)
        self._alerts: List[PerformanceAlert] = []
        self._alert_history: deque = deque(maxlen=1000)

        # Profiling
        self._profiler = None
        self._profiling_enabled = self.config.get("profiling_enabled", False)
        self._profiling_active = False

        # Memory tracking
        self._memory_tracker_enabled = self.config.get("memory_tracking_enabled", True)
        if self._memory_tracker_enabled:
            tracemalloc.start()

        # Performance thresholds
        self._thresholds = self.config.get("thresholds", {
            "cpu_warning": 70.0,
            "cpu_critical": 85.0,
            "memory_warning": 80.0,
            "memory_critical": 90.0,
            "latency_warning": 100.0,
            "latency_critical": 500.0,
            "throughput_warning": 100.0,
            "throughput_critical": 50.0,
            "gc_time_warning": 100.0,
            "gc_time_critical": 500.0,
        })

        # Baseline statistics
        self._baselines: Dict[str, Dict[str, float]] = {}

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._collect_task: Optional[asyncio.Task] = None
        self._alert_task: Optional[asyncio.Task] = None
        self._baseline_task: Optional[asyncio.Task] = None

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "performance_monitor_initialized",
            db_path=str(self._db_path),
            profiling_enabled=self._profiling_enabled,
            memory_tracking_enabled=self._memory_tracker_enabled,
        )

    def _initialize_db(self) -> None:
        """Initialize the SQLite database."""
        self._db = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS performance_samples (
                sample_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_used_mb REAL NOT NULL,
                memory_percent REAL NOT NULL,
                thread_count INTEGER NOT NULL,
                file_descriptors INTEGER NOT NULL,
                gc_count INTEGER DEFAULT 0,
                gc_time_ms REAL DEFAULT 0,
                latency_ms REAL DEFAULT 0,
                throughput REAL DEFAULT 0,
                custom_metrics TEXT,
                labels TEXT,
                metadata TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS performance_alerts (
                alert_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                current_value REAL NOT NULL,
                threshold_value REAL NOT NULL,
                message TEXT NOT NULL,
                recommendation TEXT,
                resolved INTEGER DEFAULT 0,
                resolved_at TEXT,
                metadata TEXT
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_samples_timestamp ON performance_samples(timestamp)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON performance_alerts(timestamp)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON performance_alerts(resolved)
        """)

        logger.info("performance_db_initialized", db_path=str(self._db_path))

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Collection task
            self._collect_task = loop.create_task(self._collect_loop())

            # Alert task
            self._alert_task = loop.create_task(self._alert_loop())

            # Baseline task
            self._baseline_task = loop.create_task(self._baseline_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _collect_loop(self) -> None:
        """Background task for collecting performance samples."""
        while not self._closed:
            try:
                sample = await self._collect_sample()
                await self._process_sample(sample)
                await asyncio.sleep(self.config.get("collect_interval", 5.0))
            except Exception as e:
                logger.error("collect_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _alert_loop(self) -> None:
        """Background task for processing alerts."""
        while not self._closed:
            try:
                await self._check_alerts()
                await asyncio.sleep(self.config.get("alert_check_interval", 10.0))
            except Exception as e:
                logger.error("alert_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _baseline_loop(self) -> None:
        """Background task for updating baselines."""
        while not self._closed:
            try:
                await self._update_baselines()
                await asyncio.sleep(self.config.get("baseline_update_interval", 3600.0))
            except Exception as e:
                logger.error("baseline_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def _collect_sample(self) -> PerformanceSample:
        """Collect a performance sample."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)

        # Memory
        mem = psutil.virtual_memory()
        process = psutil.Process()
        memory_used = process.memory_info().rss / (1024 * 1024)  # MB

        # Threads
        thread_count = process.num_threads()

        # File descriptors
        try:
            file_descriptors = process.num_fds()
        except AttributeError:
            file_descriptors = 0

        # GC stats
        gc_count = gc.get_count()
        gc_time = gc.get_stats()

        # Latency (estimate from system)
        latency_ms = self._measure_latency()

        # Throughput (estimate)
        throughput = self._measure_throughput()

        # Custom metrics
        custom_metrics = await self._collect_custom_metrics()

        return PerformanceSample(
            cpu_percent=cpu_percent,
            memory_used_mb=memory_used,
            memory_percent=mem.percent,
            thread_count=thread_count,
            file_descriptors=file_descriptors,
            gc_count=sum(gc_count),
            gc_time_ms=sum(stat.get('time', 0) for stat in gc_time) * 1000,
            latency_ms=latency_ms,
            throughput=throughput,
            custom_metrics=custom_metrics,
            labels=self._get_labels(),
        )

    def _measure_latency(self) -> float:
        """Measure system latency."""
        # Simple latency measurement using localhost ping
        try:
            start = time.perf_counter()
            with socket.create_connection(('127.0.0.1', 80), timeout=1):
                pass
            return (time.perf_counter() - start) * 1000
        except Exception:
            return 0.0

    def _measure_throughput(self) -> float:
        """Measure system throughput."""
        # Estimate throughput based on network IO
        try:
            net_io = psutil.net_io_counters()
            # Use recent network activity
            return (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)  # MB/s
        except Exception:
            return 0.0

    async def _collect_custom_metrics(self) -> Dict[str, float]:
        """Collect custom performance metrics."""
        metrics = {}

        # Add system metrics
        try:
            # CPU frequency
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                metrics["cpu_frequency_mhz"] = cpu_freq.current

            # Swap usage
            swap = psutil.swap_memory()
            metrics["swap_usage_percent"] = swap.percent
            metrics["swap_used_mb"] = swap.used / (1024 * 1024)

            # System load
            load_avg = psutil.getloadavg()
            metrics["load_avg_1min"] = load_avg[0]
            metrics["load_avg_5min"] = load_avg[1]
            metrics["load_avg_15min"] = load_avg[2]

        except Exception as e:
            logger.debug("custom_metrics_error", error=str(e))

        return metrics

    def _get_labels(self) -> Dict[str, str]:
        """Get labels for the current sample."""
        return {
            "host": socket.gethostname(),
            "environment": self.config.get("environment", "production"),
            "version": "3.0.0",
        }

    async def _process_sample(self, sample: PerformanceSample) -> None:
        """Process a performance sample."""
        with self._lock:
            self._samples.append(sample)

            # Save to database
            self._db.execute("""
                INSERT INTO performance_samples (
                    sample_id, timestamp, cpu_percent, memory_used_mb,
                    memory_percent, thread_count, file_descriptors,
                    gc_count, gc_time_ms, latency_ms, throughput,
                    custom_metrics, labels, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sample.sample_id,
                sample.timestamp.isoformat(),
                sample.cpu_percent,
                sample.memory_used_mb,
                sample.memory_percent,
                sample.thread_count,
                sample.file_descriptors,
                sample.gc_count,
                sample.gc_time_ms,
                sample.latency_ms,
                sample.throughput,
                json.dumps(sample.custom_metrics),
                json.dumps(sample.labels),
                json.dumps(sample.metadata),
            ))

        logger.debug(
            "performance_sample_collected",
            cpu=sample.cpu_percent,
            memory=sample.memory_percent,
            latency=sample.latency_ms,
        )

    async def _check_alerts(self) -> None:
        """Check for performance alerts."""
        if not self._samples:
            return

        latest = self._samples[-1]

        # Check CPU
        self._check_metric(
            name="cpu_percent",
            value=latest.cpu_percent,
            threshold_warning=self._thresholds.get("cpu_warning", 70.0),
            threshold_critical=self._thresholds.get("cpu_critical", 85.0),
            metric_type=PerformanceMetricType.CPU,
            recommendation="Consider reducing load or scaling up resources",
        )

        # Check Memory
        self._check_metric(
            name="memory_percent",
            value=latest.memory_percent,
            threshold_warning=self._thresholds.get("memory_warning", 80.0),
            threshold_critical=self._thresholds.get("memory_critical", 90.0),
            metric_type=PerformanceMetricType.MEMORY,
            recommendation="Consider increasing memory or investigating memory leak",
        )

        # Check Latency
        self._check_metric(
            name="latency_ms",
            value=latest.latency_ms,
            threshold_warning=self._thresholds.get("latency_warning", 100.0),
            threshold_critical=self._thresholds.get("latency_critical", 500.0),
            metric_type=PerformanceMetricType.LATENCY,
            recommendation="Check network connectivity and system load",
        )

        # Check GC time
        self._check_metric(
            name="gc_time_ms",
            value=latest.gc_time_ms,
            threshold_warning=self._thresholds.get("gc_time_warning", 100.0),
            threshold_critical=self._thresholds.get("gc_time_critical", 500.0),
            metric_type=PerformanceMetricType.GC,
            recommendation="Consider reducing object allocations",
        )

    def _check_metric(
        self,
        name: str,
        value: float,
        threshold_warning: float,
        threshold_critical: float,
        metric_type: PerformanceMetricType,
        recommendation: str,
    ) -> None:
        """Check a metric against thresholds and create alerts if needed."""
        if value >= threshold_critical:
            level = PerformanceAlertLevel.CRITICAL
            message = f"{name} is at critical level: {value:.1f}%"
        elif value >= threshold_warning:
            level = PerformanceAlertLevel.WARNING
            message = f"{name} is at warning level: {value:.1f}%"
        else:
            # Resolve existing alerts for this metric
            self._resolve_alerts_for_metric(name)
            return

        # Check if alert already exists
        for alert in self._alerts:
            if alert.metric_name == name and not alert.resolved:
                # Update existing alert
                alert.current_value = value
                alert.timestamp = datetime.utcnow()
                alert.message = message
                self._save_alert(alert)
                return

        # Create new alert
        alert = PerformanceAlert(
            level=level,
            metric_type=metric_type,
            metric_name=name,
            current_value=value,
            threshold_value=threshold_critical if level == PerformanceAlertLevel.CRITICAL else threshold_warning,
            message=message,
            recommendation=recommendation,
        )

        self._alerts.append(alert)
        self._save_alert(alert)

        logger.warning(
            "performance_alert",
            metric=name,
            value=value,
            level=level.value,
            threshold=alert.threshold_value,
        )

    def _resolve_alerts_for_metric(self, metric_name: str) -> None:
        """Resolve all alerts for a specific metric."""
        for alert in self._alerts:
            if alert.metric_name == metric_name and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                self._save_alert(alert)
                logger.info(
                    "performance_alert_resolved",
                    metric=metric_name,
                    alert_id=alert.alert_id,
                )

    def _save_alert(self, alert: PerformanceAlert) -> None:
        """Save alert to database."""
        self._db.execute("""
            INSERT OR REPLACE INTO performance_alerts (
                alert_id, timestamp, level, metric_type, metric_name,
                current_value, threshold_value, message, recommendation,
                resolved, resolved_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            alert.alert_id,
            alert.timestamp.isoformat(),
            alert.level.value,
            alert.metric_type.value,
            alert.metric_name,
            alert.current_value,
            alert.threshold_value,
            alert.message,
            alert.recommendation,
            1 if alert.resolved else 0,
            alert.resolved_at.isoformat() if alert.resolved_at else None,
            json.dumps(alert.metadata),
        ))

    async def _update_baselines(self) -> None:
        """Update baseline statistics."""
        if len(self._samples) < 10:
            return

        # Get samples from the last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent = [s for s in self._samples if s.timestamp > cutoff]

        if not recent:
            return

        # Calculate baselines
        self._baselines = {
            "cpu_percent": {
                "mean": np.mean([s.cpu_percent for s in recent]),
                "std": np.std([s.cpu_percent for s in recent]),
                "p95": np.percentile([s.cpu_percent for s in recent], 95),
                "p99": np.percentile([s.cpu_percent for s in recent], 99),
            },
            "memory_percent": {
                "mean": np.mean([s.memory_percent for s in recent]),
                "std": np.std([s.memory_percent for s in recent]),
                "p95": np.percentile([s.memory_percent for s in recent], 95),
                "p99": np.percentile([s.memory_percent for s in recent], 99),
            },
            "latency_ms": {
                "mean": np.mean([s.latency_ms for s in recent]),
                "std": np.std([s.latency_ms for s in recent]),
                "p95": np.percentile([s.latency_ms for s in recent], 95),
                "p99": np.percentile([s.latency_ms for s in recent], 99),
            },
            "throughput": {
                "mean": np.mean([s.throughput for s in recent]),
                "std": np.std([s.throughput for s in recent]),
                "p95": np.percentile([s.throughput for s in recent], 95),
                "p99": np.percentile([s.throughput for s in recent], 99),
            },
        }

        logger.info(
            "baselines_updated",
            cpu_mean=self._baselines["cpu_percent"]["mean"],
            memory_mean=self._baselines["memory_percent"]["mean"],
            latency_mean=self._baselines["latency_ms"]["mean"],
        )

    def start_profiling(self, duration_seconds: int = 30) -> Dict[str, Any]:
        """
        Start CPU profiling.

        Args:
            duration_seconds: Duration of profiling in seconds

        Returns:
            Profiling results
        """
        if not self._profiling_enabled:
            return {"status": "disabled", "message": "Profiling is not enabled"}

        if self._profiling_active:
            return {"status": "error", "message": "Profiling is already active"}

        self._profiling_active = True

        try:
            # Start memory profiling
            if self._memory_tracker_enabled:
                tracemalloc.start()

            # Start CPU profiling
            profiler = cProfile.Profile()
            profiler.enable()

            # Wait for duration
            time.sleep(duration_seconds)

            # Stop profiling
            profiler.disable()

            # Get results
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats("cumtime")
            stats.print_stats(20)

            # Get memory snapshot
            if self._memory_tracker_enabled:
                snapshot = tracemalloc.take_snapshot()
                top_stats = snapshot.statistics("lineno")

                memory_stats = []
                for stat in top_stats[:20]:
                    memory_stats.append({
                        "file": stat.traceback[0].filename,
                        "line": stat.traceback[0].lineno,
                        "size_bytes": stat.size,
                        "size_mb": stat.size / (1024 * 1024),
                        "count": stat.count,
                    })

                tracemalloc.stop()
            else:
                memory_stats = []

            self._profiling_active = False

            results = {
                "status": "success",
                "duration_seconds": duration_seconds,
                "profile_output": stream.getvalue(),
                "memory_stats": memory_stats,
            }

            logger.info("profiling_completed", duration=duration_seconds)

            return results

        except Exception as e:
            self._profiling_active = False
            logger.error("profiling_error", error=str(e))
            return {"status": "error", "message": str(e)}

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a summary of performance metrics."""
        if not self._samples:
            return {"status": "no_data"}

        latest = self._samples[-1]
        baselines = self._baselines

        return {
            "latest": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "memory_used_mb": latest.memory_used_mb,
                "latency_ms": latest.latency_ms,
                "throughput": latest.throughput,
                "thread_count": latest.thread_count,
                "gc_time_ms": latest.gc_time_ms,
            },
            "baselines": baselines,
            "alerts_active": len([a for a in self._alerts if not a.resolved]),
            "alerts_total": len(self._alerts),
            "samples_collected": len(self._samples),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_performance_metrics(
        self,
        metric_type: Optional[Union[str, PerformanceMetricType]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PerformanceSample]:
        """
        Get performance metrics with filtering.

        Args:
            metric_type: Filter by metric type
            start_time: Start time
            end_time: End time
            limit: Maximum number of samples
            offset: Pagination offset

        Returns:
            List of PerformanceSample objects
        """
        sql = "SELECT * FROM performance_samples WHERE 1=1"
        params = []

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        samples = []

        for row in rows:
            data = dict(zip(columns, row))
            data["custom_metrics"] = json.loads(data["custom_metrics"]) if data.get("custom_metrics") else {}
            data["labels"] = json.loads(data["labels"]) if data.get("labels") else {}
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            samples.append(PerformanceSample.from_dict(data))

        return samples

    def get_alerts(
        self,
        resolved: Optional[bool] = None,
        level: Optional[Union[str, PerformanceAlertLevel]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PerformanceAlert]:
        """
        Get performance alerts.

        Args:
            resolved: Filter by resolved status
            level: Filter by alert level
            limit: Maximum number of alerts
            offset: Pagination offset

        Returns:
            List of PerformanceAlert objects
        """
        sql = "SELECT * FROM performance_alerts WHERE 1=1"
        params = []

        if resolved is not None:
            sql += " AND resolved = ?"
            params.append(1 if resolved else 0)

        if level:
            if isinstance(level, str):
                level = PerformanceAlertLevel(level)
            sql += " AND level = ?"
            params.append(level.value)

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        alerts = []

        for row in rows:
            data = dict(zip(columns, row))
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            alerts.append(PerformanceAlert.from_dict(data))

        return alerts

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve a performance alert.

        Args:
            alert_id: ID of the alert

        Returns:
            True if successful, False otherwise
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                self._save_alert(alert)
                return True
        return False

    def get_recommendations(self) -> List[Dict[str, Any]]:
        """
        Get performance optimization recommendations.

        Returns:
            List of recommendations
        """
        recommendations = []

        # Check CPU
        if self._samples:
            latest = self._samples[-1]
            if latest.cpu_percent > self._thresholds.get("cpu_warning", 70.0):
                recommendations.append({
                    "type": "cpu",
                    "severity": "high" if latest.cpu_percent > self._thresholds.get("cpu_critical", 85.0) else "medium",
                    "message": f"High CPU usage: {latest.cpu_percent:.1f}%",
                    "action": "Consider reducing processing load or scaling up CPU resources",
                })

            # Check memory
            if latest.memory_percent > self._thresholds.get("memory_warning", 80.0):
                recommendations.append({
                    "type": "memory",
                    "severity": "high" if latest.memory_percent > self._thresholds.get("memory_critical", 90.0) else "medium",
                    "message": f"High memory usage: {latest.memory_percent:.1f}%",
                    "action": "Investigate memory leak or increase memory allocation",
                })

            # Check latency
            if latest.latency_ms > self._thresholds.get("latency_warning", 100.0):
                recommendations.append({
                    "type": "latency",
                    "severity": "high" if latest.latency_ms > self._thresholds.get("latency_critical", 500.0) else "medium",
                    "message": f"High latency: {latest.latency_ms:.1f}ms",
                    "action": "Check network connectivity and system load",
                })

            # Check GC
            if latest.gc_time_ms > self._thresholds.get("gc_time_warning", 100.0):
                recommendations.append({
                    "type": "gc",
                    "severity": "high" if latest.gc_time_ms > self._thresholds.get("gc_time_critical", 500.0) else "medium",
                    "message": f"High GC time: {latest.gc_time_ms:.1f}ms",
                    "action": "Consider reducing object allocations or tuning GC parameters",
                })

        return recommendations

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance monitor metrics."""
        return {
            "samples_collected": len(self._samples),
            "alerts_active": len([a for a in self._alerts if not a.resolved]),
            "alerts_resolved": len([a for a in self._alerts if a.resolved]),
            "alerts_total": len(self._alerts),
            "profiling_active": self._profiling_active,
            "memory_tracking_active": self._memory_tracker_enabled,
            "baselines_available": bool(self._baselines),
            "last_sample": self._samples[-1].timestamp.isoformat() if self._samples else None,
        }

    def close(self) -> None:
        """Close the performance monitor."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        if self._memory_tracker_enabled:
            tracemalloc.stop()

        logger.info("performance_monitor_closed")

    def __enter__(self) -> "PerformanceMonitor":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "PerformanceMonitor",
    "PerformanceSample",
    "PerformanceAlert",
    "PerformanceMetricType",
    "PerformanceAlertLevel",
]

logger.info("performance_monitor_module_loaded", version="3.0.0")
