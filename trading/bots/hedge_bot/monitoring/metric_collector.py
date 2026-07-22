# trading/bots/hedge_bot/monitoring/metric_collector.py

"""
NEXUS HEDGE BOT - METRIC COLLECTOR
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive metric collection system with real-time monitoring,
histogram support, and Prometheus integration.

Version: 3.0.0
"""

import asyncio
import json
import sqlite3
import threading
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from uuid import uuid4

import aiohttp
import psutil
import structlog
import yaml
from pydantic import BaseModel, Field, validator
import numpy as np
import pandas as pd

# Try to import Prometheus client
try:
    from prometheus_client import Counter, Gauge, Histogram, Summary, CollectorRegistry, push_to_gateway
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class MetricCategory(str, Enum):
    """Categories of metrics."""
    SYSTEM = "system"
    PERFORMANCE = "performance"
    TRADING = "trading"
    RISK = "risk"
    BROKER = "broker"
    MARKET = "market"
    POSITION = "position"
    OPERATIONAL = "operational"
    BUSINESS = "business"
    CUSTOM = "custom"


# === DATA MODELS ===

@dataclass
class Metric:
    """Metric data point."""
    metric_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: MetricType = MetricType.GAUGE
    category: MetricCategory = MetricCategory.SYSTEM
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    unit: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "type": self.type.value,
            "category": self.category.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metric":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["type"] = MetricType(data["type"])
        data["category"] = MetricCategory(data["category"])
        return cls(**data)


@dataclass
class MetricHistogram:
    """Histogram data for metrics."""
    name: str = ""
    buckets: List[float] = field(default_factory=list)
    counts: List[int] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }


# === METRIC COLLECTOR ===

class MetricCollector:
    """
    Comprehensive metric collection system with real-time monitoring,
    histogram support, and Prometheus integration.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
    ):
        """
        Initialize the MetricCollector.

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
        self._db_path = Path(self.config.get("db_path", "metrics.db"))
        self._initialize_db()

        # In-memory storage
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._histograms: Dict[str, MetricHistogram] = {}
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = defaultdict(float)

        # Prometheus metrics
        self._prometheus_metrics: Dict[str, Any] = {}
        self._prometheus_registry = None
        self._prometheus_push_gateway = self.config.get("prometheus_push_gateway")

        if PROMETHEUS_AVAILABLE and self.config.get("prometheus_enabled", False):
            self._init_prometheus()

        # Aggregation windows
        self._aggregation_windows = self.config.get("aggregation_windows", [60, 300, 900, 3600])

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._collect_task: Optional[asyncio.Task] = None
        self._aggregate_task: Optional[asyncio.Task] = None
        self._push_task: Optional[asyncio.Task] = None

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "metric_collector_initialized",
            db_path=str(self._db_path),
            prometheus_enabled=self.config.get("prometheus_enabled", False),
            aggregation_windows=self._aggregation_windows,
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
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                value REAL NOT NULL,
                labels TEXT,
                timestamp TEXT NOT NULL,
                unit TEXT,
                description TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS histograms (
                name TEXT NOT NULL,
                buckets TEXT NOT NULL,
                counts TEXT NOT NULL,
                sum REAL NOT NULL,
                count INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                labels TEXT,
                PRIMARY KEY (name, timestamp)
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(name)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category)
        """)

        logger.info("metric_db_initialized", db_path=str(self._db_path))

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client_not_available")
            return

        self._prometheus_registry = CollectorRegistry()

        # Create default metrics
        self._prometheus_metrics = {
            "cpu_usage": Gauge("nexus_cpu_usage", "CPU usage percentage", registry=self._prometheus_registry),
            "memory_usage": Gauge("nexus_memory_usage", "Memory usage percentage", registry=self._prometheus_registry),
            "memory_used_gb": Gauge("nexus_memory_used_gb", "Memory used in GB", registry=self._prometheus_registry),
            "disk_usage": Gauge("nexus_disk_usage", "Disk usage percentage", registry=self._prometheus_registry),
            "connections_active": Gauge("nexus_connections_active", "Active connections", registry=self._prometheus_registry),
            "trades_total": Counter("nexus_trades_total", "Total trades executed", registry=self._prometheus_registry),
            "trades_successful": Counter("nexus_trades_successful", "Successful trades", registry=self._prometheus_registry),
            "trades_failed": Counter("nexus_trades_failed", "Failed trades", registry=self._prometheus_registry),
            "pnl_total": Gauge("nexus_pnl_total", "Total PnL", registry=self._prometheus_registry),
            "var_95": Gauge("nexus_var_95", "Value at Risk 95%", registry=self._prometheus_registry),
            "sharpe_ratio": Gauge("nexus_sharpe_ratio", "Sharpe ratio", registry=self._prometheus_registry),
            "request_duration": Histogram(
                "nexus_request_duration_seconds",
                "Request duration in seconds",
                buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                registry=self._prometheus_registry,
            ),
            "api_requests_total": Counter(
                "nexus_api_requests_total",
                "Total API requests",
                ["method", "endpoint", "status"],
                registry=self._prometheus_registry,
            ),
        }

        logger.info("prometheus_metrics_initialized")

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Collection task
            self._collect_task = loop.create_task(self._collect_loop())

            # Aggregation task
            self._aggregate_task = loop.create_task(self._aggregate_loop())

            # Push task (if Prometheus is enabled)
            if self._prometheus_push_gateway and self.config.get("prometheus_enabled", False):
                self._push_task = loop.create_task(self._push_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _collect_loop(self) -> None:
        """Background task for collecting metrics."""
        while not self._closed:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.config.get("collect_interval", 10))
            except Exception as e:
                logger.error("collect_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _aggregate_loop(self) -> None:
        """Background task for aggregating metrics."""
        while not self._closed:
            try:
                await self._aggregate_metrics()
                await asyncio.sleep(self.config.get("aggregate_interval", 60))
            except Exception as e:
                logger.error("aggregate_loop_error", error=str(e))
                await asyncio.sleep(30)

    async def _push_loop(self) -> None:
        """Background task for pushing metrics to Prometheus."""
        while not self._closed:
            try:
                await self._push_to_prometheus()
                await asyncio.sleep(self.config.get("push_interval", 15))
            except Exception as e:
                logger.error("push_loop_error", error=str(e))
                await asyncio.sleep(60)

    async def _collect_system_metrics(self) -> None:
        """Collect system metrics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.record_metric(
            name="system.cpu_usage",
            value=cpu_percent,
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            unit="%",
            description="CPU usage percentage",
        )

        # Memory
        mem = psutil.virtual_memory()
        self.record_metric(
            name="system.memory_usage",
            value=mem.percent,
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            unit="%",
            description="Memory usage percentage",
        )
        self.record_metric(
            name="system.memory_used_gb",
            value=mem.used / (1024 ** 3),
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            unit="GB",
            description="Memory used in GB",
        )

        # Disk
        disk = psutil.disk_usage("/")
        self.record_metric(
            name="system.disk_usage",
            value=disk.percent,
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            unit="%",
            description="Disk usage percentage",
        )
        self.record_metric(
            name="system.disk_free_gb",
            value=disk.free / (1024 ** 3),
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            unit="GB",
            description="Disk free space in GB",
        )

        # Load average
        load_avg = psutil.getloadavg()
        self.record_metric(
            name="system.load_avg_1min",
            value=load_avg[0],
            type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            description="Load average 1 minute",
        )

        # Network
        net_io = psutil.net_io_counters()
        self.record_metric(
            name="system.network_bytes_sent",
            value=net_io.bytes_sent,
            type=MetricType.COUNTER,
            category=MetricCategory.SYSTEM,
            unit="bytes",
            description="Network bytes sent",
        )
        self.record_metric(
            name="system.network_bytes_recv",
            value=net_io.bytes_recv,
            type=MetricType.COUNTER,
            category=MetricCategory.SYSTEM,
            unit="bytes",
            description="Network bytes received",
        )

        # Update Prometheus metrics
        if PROMETHEUS_AVAILABLE and self._prometheus_metrics:
            self._prometheus_metrics["cpu_usage"].set(cpu_percent)
            self._prometheus_metrics["memory_usage"].set(mem.percent)
            self._prometheus_metrics["memory_used_gb"].set(mem.used / (1024 ** 3))
            self._prometheus_metrics["disk_usage"].set(disk.percent)

        logger.debug("system_metrics_collected", cpu=cpu_percent, memory=mem.percent, disk=disk.percent)

    async def _aggregate_metrics(self) -> None:
        """Aggregate metrics for monitoring."""
        try:
            # Get recent metrics
            recent = await self.get_metrics(since=datetime.utcnow() - timedelta(minutes=5), limit=1000)

            if not recent:
                return

            # Group by name
            grouped = defaultdict(list)
            for metric in recent:
                grouped[metric.name].append(metric)

            # Calculate aggregates
            for name, metrics in grouped.items():
                values = [m.value for m in metrics]
                if not values:
                    continue

                self.record_metric(
                    name=f"{name}.avg",
                    value=np.mean(values),
                    type=MetricType.GAUGE,
                    category=MetricCategory.PERFORMANCE,
                    labels={"aggregation": "avg"},
                    description=f"Average of {name}",
                )
                self.record_metric(
                    name=f"{name}.max",
                    value=np.max(values),
                    type=MetricType.GAUGE,
                    category=MetricCategory.PERFORMANCE,
                    labels={"aggregation": "max"},
                    description=f"Maximum of {name}",
                )
                self.record_metric(
                    name=f"{name}.min",
                    value=np.min(values),
                    type=MetricType.GAUGE,
                    category=MetricCategory.PERFORMANCE,
                    labels={"aggregation": "min"},
                    description=f"Minimum of {name}",
                )
                self.record_metric(
                    name=f"{name}.p95",
                    value=np.percentile(values, 95),
                    type=MetricType.GAUGE,
                    category=MetricCategory.PERFORMANCE,
                    labels={"aggregation": "p95"},
                    description=f"95th percentile of {name}",
                )
                self.record_metric(
                    name=f"{name}.p99",
                    value=np.percentile(values, 99),
                    type=MetricType.GAUGE,
                    category=MetricCategory.PERFORMANCE,
                    labels={"aggregation": "p99"},
                    description=f"99th percentile of {name}",
                )

            logger.debug("metrics_aggregated", groups=len(grouped))

        except Exception as e:
            logger.error("aggregation_error", error=str(e))

    async def _push_to_prometheus(self) -> None:
        """Push metrics to Prometheus Push Gateway."""
        if not PROMETHEUS_AVAILABLE or not self._prometheus_push_gateway:
            return

        try:
            push_to_gateway(
                self._prometheus_push_gateway,
                job="nexus_hedge_bot",
                registry=self._prometheus_registry,
            )
            logger.debug("prometheus_push_successful", gateway=self._prometheus_push_gateway)
        except Exception as e:
            logger.error("prometheus_push_error", error=str(e))

    def record_metric(
        self,
        name: str,
        value: float,
        type: Union[str, MetricType] = MetricType.GAUGE,
        category: Union[str, MetricCategory] = MetricCategory.SYSTEM,
        labels: Optional[Dict[str, str]] = None,
        unit: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Metric:
        """
        Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            type: Metric type
            category: Metric category
            labels: Metric labels
            unit: Metric unit
            description: Metric description
            tags: Metric tags
            metadata: Additional metadata

        Returns:
            Created Metric object
        """
        if isinstance(type, str):
            type = MetricType(type)
        if isinstance(category, str):
            category = MetricCategory(category)

        metric = Metric(
            name=name,
            value=value,
            type=type,
            category=category,
            labels=labels or {},
            unit=unit,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )

        with self._lock:
            # Store in memory
            self._metrics[name].append(metric)

            # Update counters/gauges
            if type == MetricType.COUNTER:
                self._counters[name] += value
            elif type == MetricType.GAUGE:
                self._gauges[name] = value

            # Save to database
            self._db.execute("""
                INSERT INTO metrics (
                    metric_id, name, type, category, value, labels,
                    timestamp, unit, description, tags, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.metric_id,
                name,
                type.value,
                category.value,
                value,
                json.dumps(labels),
                metric.timestamp.isoformat(),
                unit,
                description,
                json.dumps(tags),
                json.dumps(metadata),
            ))

            # Update Prometheus if available
            self._update_prometheus(metric)

        return metric

    def _update_prometheus(self, metric: Metric) -> None:
        """Update Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE or not self._prometheus_metrics:
            return

        try:
            # Map to Prometheus metrics
            prom_name = metric.name.replace(".", "_").replace("-", "_")

            if prom_name in self._prometheus_metrics:
                prom_metric = self._prometheus_metrics[prom_name]
                if isinstance(prom_metric, (Gauge, Counter)):
                    prom_metric.set(metric.value)
                elif isinstance(prom_metric, Histogram):
                    prom_metric.observe(metric.value)

            # Handle specific metrics
            if metric.name == "trades_total":
                self._prometheus_metrics["trades_total"].inc()
            elif metric.name == "trades_successful":
                self._prometheus_metrics["trades_successful"].inc()
            elif metric.name == "trades_failed":
                self._prometheus_metrics["trades_failed"].inc()

        except Exception as e:
            logger.error("prometheus_update_error", error=str(e))

    def record_histogram(
        self,
        name: str,
        value: float,
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a histogram value.

        Args:
            name: Histogram name
            value: Value to record
            buckets: Bucket boundaries
            labels: Labels
        """
        if buckets is None:
            buckets = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]

        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"

        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = MetricHistogram(
                    name=name,
                    buckets=buckets,
                    counts=[0] * len(buckets),
                    labels=labels or {},
                )

            hist = self._histograms[key]
            hist.count += 1
            hist.sum += value

            # Find bucket
            for i, bucket in enumerate(buckets):
                if value <= bucket:
                    hist.counts[i] += 1
                    break
            else:
                # Value exceeds all buckets
                if hist.counts:
                    hist.counts[-1] += 1

            # Save to database
            self._db.execute("""
                INSERT INTO histograms (name, buckets, counts, sum, count, timestamp, labels)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                json.dumps(buckets),
                json.dumps(hist.counts),
                hist.sum,
                hist.count,
                hist.timestamp.isoformat(),
                json.dumps(labels or {}),
            ))

    def get_metrics(
        self,
        name: Optional[str] = None,
        category: Optional[Union[str, MetricCategory]] = None,
        since: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Metric]:
        """
        Get metrics with filtering.

        Args:
            name: Filter by metric name
            category: Filter by category
            since: Get metrics after this time
            limit: Maximum number of metrics
            offset: Pagination offset

        Returns:
            List of Metric objects
        """
        sql = "SELECT * FROM metrics WHERE 1=1"
        params = []

        if name:
            sql += " AND name = ?"
            params.append(name)

        if category:
            if isinstance(category, str):
                category = MetricCategory(category)
            sql += " AND category = ?"
            params.append(category.value)

        if since:
            sql += " AND timestamp >= ?"
            params.append(since.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        metrics = []

        for row in rows:
            data = dict(zip(columns, row))
            data["labels"] = json.loads(data["labels"]) if data.get("labels") else {}
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            metrics.append(Metric.from_dict(data))

        return metrics

    def get_metric_value(self, name: str) -> Optional[float]:
        """Get the latest value of a metric."""
        cursor = self._db.execute(
            "SELECT value FROM metrics WHERE name = ? ORDER BY timestamp DESC LIMIT 1",
            (name,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def get_counter(self, name: str) -> float:
        """Get a counter value."""
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        """Get a gauge value."""
        return self._gauges.get(name, 0.0)

    def get_histogram(self, name: str) -> Optional[MetricHistogram]:
        """Get a histogram."""
        for hist in self._histograms.values():
            if hist.name == name:
                return hist
        return None

    def get_metric_stats(
        self,
        name: str,
        window_seconds: int = 300,
    ) -> Dict[str, float]:
        """
        Get statistics for a metric.

        Args:
            name: Metric name
            window_seconds: Time window in seconds

        Returns:
            Dictionary of statistics
        """
        since = datetime.utcnow() - timedelta(seconds=window_seconds)

        cursor = self._db.execute("""
            SELECT value FROM metrics
            WHERE name = ? AND timestamp >= ?
            ORDER BY timestamp ASC
        """, (name, since.isoformat()))

        values = [row[0] for row in cursor.fetchall()]

        if not values:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "mean": 0,
                "std": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
                "sum": 0,
            }

        return {
            "count": len(values),
            "min": np.min(values),
            "max": np.max(values),
            "mean": np.mean(values),
            "std": np.std(values),
            "p50": np.percentile(values, 50),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
            "sum": np.sum(values),
        }

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all metrics.

        Returns:
            Dictionary of metric summary
        """
        total = self._get_total_metrics()
        by_category = self._get_counts_by_category()
        by_type = self._get_counts_by_type()

        return {
            "total_metrics": total,
            "metrics_by_category": by_category,
            "metrics_by_type": by_type,
            "active_gauges": len(self._gauges),
            "active_counters": len(self._counters),
            "histograms": len(self._histograms),
            "last_collection": self._get_last_collection_time(),
        }

    def _get_total_metrics(self) -> int:
        """Get total number of metrics in database."""
        cursor = self._db.execute("SELECT COUNT(*) FROM metrics")
        return cursor.fetchone()[0]

    def _get_counts_by_category(self) -> Dict[str, int]:
        """Get metric counts by category."""
        cursor = self._db.execute(
            "SELECT category, COUNT(*) FROM metrics GROUP BY category"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_counts_by_type(self) -> Dict[str, int]:
        """Get metric counts by type."""
        cursor = self._db.execute(
            "SELECT type, COUNT(*) FROM metrics GROUP BY type"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_last_collection_time(self) -> Optional[str]:
        """Get the last collection time."""
        cursor = self._db.execute(
            "SELECT timestamp FROM metrics ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def close(self) -> None:
        """Close the metric collector."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        logger.info("metric_collector_closed")

    def __enter__(self) -> "MetricCollector":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "MetricCollector",
    "Metric",
    "MetricHistogram",
    "MetricType",
    "MetricCategory",
]

logger.info("metric_collector_module_loaded", version="3.0.0")
