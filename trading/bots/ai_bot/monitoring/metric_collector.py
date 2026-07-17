"""
NEXUS AI TRADING SYSTEM - Metric Collector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced metric collection system for monitoring trading bots, models,
and system performance with real-time aggregation, historical storage,
and Prometheus integration.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiofiles
import numpy as np
import pandas as pd
import psutil
import yaml
from prometheus_client import Counter, Gauge, Histogram, Summary

from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
METRIC_COLLECTED_COUNTER = Counter(
    "nexus_metrics_collected_total",
    "Total number of metrics collected",
    ["metric_type", "source"],
)
METRIC_AGGREGATION_DURATION = Histogram(
    "nexus_metric_aggregation_duration_seconds",
    "Duration of metric aggregation",
    ["aggregation_type"],
)
METRIC_STORAGE_SIZE = Gauge(
    "nexus_metric_storage_size_bytes",
    "Size of metric storage",
)


class MetricType(Enum):
    """Types of metrics."""

    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class AggregationType(Enum):
    """Types of aggregation."""

    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    FIRST = "first"
    STD = "std"
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"


@dataclass
class MetricDefinition:
    """Metric definition."""

    name: str
    type: MetricType
    description: str
    unit: str = ""
    labels: List[str] = field(default_factory=list)
    default_value: Any = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    aggregation: AggregationType = AggregationType.AVG
    retention_days: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "unit": self.unit,
            "labels": self.labels,
            "default_value": self.default_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "aggregation": self.aggregation.value,
            "retention_days": self.retention_days,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricDefinition":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=MetricType(data["type"]),
            description=data["description"],
            unit=data.get("unit", ""),
            labels=data.get("labels", []),
            default_value=data.get("default_value", 0.0),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            aggregation=AggregationType(data.get("aggregation", "avg")),
            retention_days=data.get("retention_days", 30),
        )


@dataclass
class MetricPoint:
    """Single metric data point."""

    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "labels": self.labels,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricPoint":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            value=data["value"],
            labels=data.get("labels", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MetricSeries:
    """Time series of metric data."""

    name: str
    definition: MetricDefinition
    points: List[MetricPoint] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "definition": self.definition.to_dict(),
            "points": [p.to_dict() for p in self.points],
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricSeries":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            definition=MetricDefinition.from_dict(data["definition"]),
            points=[MetricPoint.from_dict(p) for p in data.get("points", [])],
            last_updated=datetime.fromisoformat(data["last_updated"]),
        )


class MetricCollector:
    """
    Advanced metric collection system with real-time aggregation and storage.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """
        Initialize the metric collector.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self._lock = asyncio.Lock()
        self._metrics: Dict[str, MetricSeries] = {}
        self._definitions: Dict[str, MetricDefinition] = {}
        self._collectors: Dict[str, Callable] = {}
        self._collector_task: Optional[asyncio.Task] = None
        self._agg_task: Optional[asyncio.Task] = None
        self._buffer: deque = deque(maxlen=10000)

        # Load configuration
        self.metric_config = self.config.get("metric_collector", {})
        self.storage_path = Path(self.metric_config.get("storage_path", "./data/metrics"))
        self.definitions_file = Path(self.metric_config.get("definitions_file", "./configs/metrics/definitions.yaml"))
        self.collect_interval = self.metric_config.get("collect_interval", 10)
        self.agg_interval = self.metric_config.get("agg_interval", 60)
        self.buffer_size = self.metric_config.get("buffer_size", 10000)
        self.max_points_per_series = self.metric_config.get("max_points_per_series", 10000)

        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load metric definitions
        self._load_definitions()

        # Register default collectors
        self._register_default_collectors()

        # Start background tasks
        self._start_background_tasks()

        logger.info(f"MetricCollector initialized with {len(self._definitions)} metrics")

    def _load_definitions(self):
        """Load metric definitions from configuration."""
        try:
            if self.definitions_file.exists():
                with open(self.definitions_file, "r") as f:
                    data = yaml.safe_load(f)
                    for metric_data in data.get("metrics", []):
                        definition = MetricDefinition.from_dict(metric_data)
                        self._definitions[definition.name] = definition
                        self._metrics[definition.name] = MetricSeries(
                            name=definition.name,
                            definition=definition,
                        )
                logger.info(f"Loaded {len(self._definitions)} metric definitions")
            else:
                self._load_default_definitions()
        except Exception as e:
            logger.error(f"Error loading metric definitions: {e}")
            self._load_default_definitions()

    def _load_default_definitions(self):
        """Load default metric definitions."""
        default_definitions = [
            MetricDefinition(
                name="system_cpu_usage",
                type=MetricType.GAUGE,
                description="CPU usage percentage",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                aggregation=AggregationType.AVG,
                retention_days=7,
            ),
            MetricDefinition(
                name="system_memory_usage",
                type=MetricType.GAUGE,
                description="Memory usage percentage",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                aggregation=AggregationType.AVG,
                retention_days=7,
            ),
            MetricDefinition(
                name="system_disk_usage",
                type=MetricType.GAUGE,
                description="Disk usage percentage",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                aggregation=AggregationType.AVG,
                retention_days=7,
            ),
            MetricDefinition(
                name="trading_orders_total",
                type=MetricType.COUNTER,
                description="Total number of orders",
                unit="orders",
                aggregation=AggregationType.SUM,
                retention_days=30,
                labels=["symbol", "side", "status"],
            ),
            MetricDefinition(
                name="trading_volume_total",
                type=MetricType.COUNTER,
                description="Total trading volume",
                unit="USD",
                aggregation=AggregationType.SUM,
                retention_days=30,
                labels=["symbol"],
            ),
            MetricDefinition(
                name="trading_pnl",
                type=MetricType.GAUGE,
                description="Total profit and loss",
                unit="USD",
                aggregation=AggregationType.LAST,
                retention_days=30,
                labels=["symbol"],
            ),
            MetricDefinition(
                name="model_inference_latency",
                type=MetricType.HISTOGRAM,
                description="Model inference latency",
                unit="ms",
                aggregation=AggregationType.P95,
                retention_days=7,
                labels=["model_id"],
            ),
            MetricDefinition(
                name="model_accuracy",
                type=MetricType.GAUGE,
                description="Model prediction accuracy",
                unit="%",
                min_value=0.0,
                max_value=100.0,
                aggregation=AggregationType.AVG,
                retention_days=30,
                labels=["model_id"],
            ),
            MetricDefinition(
                name="bot_status",
                type=MetricType.GAUGE,
                description="Bot status (1=running, 0=stopped)",
                unit="status",
                min_value=0.0,
                max_value=1.0,
                aggregation=AggregationType.LAST,
                retention_days=7,
                labels=["bot_id"],
            ),
            MetricDefinition(
                name="api_latency",
                type=MetricType.HISTOGRAM,
                description="API request latency",
                unit="ms",
                aggregation=AggregationType.P95,
                retention_days=7,
                labels=["endpoint", "method"],
            ),
        ]

        for definition in default_definitions:
            self._definitions[definition.name] = definition
            self._metrics[definition.name] = MetricSeries(
                name=definition.name,
                definition=definition,
            )

        logger.info(f"Loaded {len(self._definitions)} default metric definitions")

    def _register_default_collectors(self):
        """Register default metric collectors."""
        self.register_collector("system", self._collect_system_metrics)
        self.register_collector("memory", self._collect_memory_metrics)
        self.register_collector("disk", self._collect_disk_metrics)
        self.register_collector("network", self._collect_network_metrics)

    def register_collector(
        self,
        name: str,
        collector_func: Callable,
    ):
        """
        Register a metric collector.

        Args:
            name: Collector name
            collector_func: Async function that returns metrics
        """
        self._collectors[name] = collector_func
        logger.info(f"Registered metric collector: {name}")

    def _start_background_tasks(self):
        """Start background tasks."""
        if self._collector_task is None:
            self._collector_task = asyncio.create_task(self._collector_loop())

        if self._agg_task is None:
            self._agg_task = asyncio.create_task(self._aggregator_loop())

    async def _collector_loop(self):
        """Background loop for metric collection."""
        while True:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in collector loop: {e}")
                await asyncio.sleep(5)

    async def _aggregator_loop(self):
        """Background loop for metric aggregation."""
        while True:
            try:
                await self._aggregate_metrics()
                await asyncio.sleep(self.agg_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregator loop: {e}")
                await asyncio.sleep(10)

    async def _collect_metrics(self):
        """Collect metrics from all collectors."""
        for name, collector in self._collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    metrics = await collector()
                else:
                    metrics = collector()

                if metrics:
                    await self._process_metrics(metrics, source=name)

            except Exception as e:
                logger.error(f"Error in collector {name}: {e}")

    async def _process_metrics(
        self,
        metrics: Dict[str, Any],
        source: str = "system",
    ):
        """
        Process collected metrics.

        Args:
            metrics: Dictionary of metric values
            source: Source of metrics
        """
        timestamp = datetime.utcnow()

        for name, value in metrics.items():
            if name not in self._definitions:
                continue

            definition = self._definitions[name]

            # Validate value
            if definition.min_value is not None and value < definition.min_value:
                value = definition.min_value
            if definition.max_value is not None and value > definition.max_value:
                value = definition.max_value

            # Create metric point
            point = MetricPoint(
                timestamp=timestamp,
                value=value,
                labels={"source": source},
            )

            # Add to buffer
            self._buffer.append((name, point))

            # Update metrics
            METRIC_COLLECTED_COUNTER.labels(
                metric_type=definition.type.value,
                source=source,
            ).inc()

    async def _aggregate_metrics(self):
        """Aggregate buffered metrics."""
        start_time = time.time()

        async with self._lock:
            # Get all buffered points
            points_by_metric = defaultdict(list)
            while self._buffer:
                name, point = self._buffer.popleft()
                points_by_metric[name].append(point)

            # Aggregate points
            for name, points in points_by_metric.items():
                if name not in self._metrics:
                    continue

                series = self._metrics[name]

                # Aggregate based on definition
                agg_type = series.definition.aggregation
                values = [p.value for p in points]

                if agg_type == AggregationType.SUM:
                    agg_value = sum(values)
                elif agg_type == AggregationType.AVG:
                    agg_value = sum(values) / len(values)
                elif agg_type == AggregationType.MIN:
                    agg_value = min(values)
                elif agg_type == AggregationType.MAX:
                    agg_value = max(values)
                elif agg_type == AggregationType.COUNT:
                    agg_value = len(values)
                elif agg_type == AggregationType.LAST:
                    agg_value = values[-1]
                elif agg_type == AggregationType.FIRST:
                    agg_value = values[0]
                elif agg_type == AggregationType.STD:
                    agg_value = np.std(values)
                elif agg_type == AggregationType.P50:
                    agg_value = np.percentile(values, 50)
                elif agg_type == AggregationType.P95:
                    agg_value = np.percentile(values, 95)
                elif agg_type == AggregationType.P99:
                    agg_value = np.percentile(values, 99)
                else:
                    agg_value = values[-1]

                # Create aggregated point
                agg_point = MetricPoint(
                    timestamp=datetime.utcnow(),
                    value=agg_value,
                    labels={"aggregated": "true"},
                )

                # Add to series
                series.points.append(agg_point)
                series.last_updated = datetime.utcnow()

                # Limit points
                if len(series.points) > self.max_points_per_series:
                    series.points = series.points[-self.max_points_per_series:]

                # Save to storage
                await self._save_metric_series(name)

        METRIC_AGGREGATION_DURATION.labels(
            aggregation_type="all"
        ).observe(time.time() - start_time)

    async def record_metric(
        self,
        name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None,
    ):
        """
        Record a single metric value.

        Args:
            name: Metric name
            value: Metric value
            timestamp: Metric timestamp (default: now)
            labels: Metric labels
        """
        if name not in self._definitions:
            raise ValueError(f"Unknown metric: {name}")

        definition = self._definitions[name]

        # Validate value
        if definition.min_value is not None and value < definition.min_value:
            value = definition.min_value
        if definition.max_value is not None and value > definition.max_value:
            value = definition.max_value

        point = MetricPoint(
            timestamp=timestamp or datetime.utcnow(),
            value=value,
            labels=labels or {},
        )

        # Add to buffer
        self._buffer.append((name, point))

        METRIC_COLLECTED_COUNTER.labels(
            metric_type=definition.type.value,
            source="manual",
        ).inc()

    async def get_metric(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: Optional[Union[AggregationType, str]] = None,
    ) -> List[MetricPoint]:
        """
        Get metric data.

        Args:
            name: Metric name
            start_time: Start time
            end_time: End time
            aggregation: Aggregation type

        Returns:
            List of metric points
        """
        async with self._lock:
            if name not in self._metrics:
                return []

            series = self._metrics[name]
            points = series.points

            # Filter by time
            if start_time:
                points = [p for p in points if p.timestamp >= start_time]
            if end_time:
                points = [p for p in points if p.timestamp <= end_time]

            # Apply aggregation
            if aggregation:
                if isinstance(aggregation, str):
                    aggregation = AggregationType(aggregation)

                if not points:
                    return []

                values = [p.value for p in points]

                if aggregation == AggregationType.SUM:
                    agg_value = sum(values)
                elif aggregation == AggregationType.AVG:
                    agg_value = sum(values) / len(values)
                elif aggregation == AggregationType.MIN:
                    agg_value = min(values)
                elif aggregation == AggregationType.MAX:
                    agg_value = max(values)
                elif aggregation == AggregationType.COUNT:
                    agg_value = len(values)
                elif aggregation == AggregationType.LAST:
                    agg_value = values[-1]
                elif aggregation == AggregationType.FIRST:
                    agg_value = values[0]
                elif aggregation == AggregationType.STD:
                    agg_value = np.std(values)
                elif aggregation == AggregationType.P50:
                    agg_value = np.percentile(values, 50)
                elif aggregation == AggregationType.P95:
                    agg_value = np.percentile(values, 95)
                elif aggregation == AggregationType.P99:
                    agg_value = np.percentile(values, 99)
                else:
                    agg_value = values[-1]

                return [MetricPoint(
                    timestamp=datetime.utcnow(),
                    value=agg_value,
                    labels={"aggregated": aggregation.value},
                )]

            return points

    async def get_metrics(
        self,
        names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, List[MetricPoint]]:
        """
        Get multiple metrics.

        Args:
            names: List of metric names
            start_time: Start time
            end_time: End time

        Returns:
            Dictionary of metric data
        """
        result = {}

        metrics = names or list(self._metrics.keys())

        for name in metrics:
            points = await self.get_metric(name, start_time, end_time)
            if points:
                result[name] = points

        return result

    async def get_metric_series(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        interval_seconds: int = 60,
    ) -> pd.DataFrame:
        """
        Get metric series as DataFrame.

        Args:
            name: Metric name
            start_time: Start time
            end_time: End time
            interval_seconds: Interval for resampling

        Returns:
            DataFrame with metric series
        """
        points = await self.get_metric(name, start_time, end_time)

        if not points:
            return pd.DataFrame()

        # Create DataFrame
        df = pd.DataFrame([
            {"timestamp": p.timestamp, "value": p.value}
            for p in points
        ])

        df.set_index("timestamp", inplace=True)

        # Resample
        if interval_seconds:
            df = df.resample(f"{interval_seconds}s").mean()

        return df

    async def get_metric_stats(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get metric statistics.

        Args:
            name: Metric name
            start_time: Start time
            end_time: End time

        Returns:
            Metric statistics
        """
        points = await self.get_metric(name, start_time, end_time)

        if not points:
            return {
                "count": 0,
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        values = [p.value for p in points]

        return {
            "count": len(values),
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "p50": np.percentile(values, 50),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
        }

    async def _collect_system_metrics(self) -> Dict[str, float]:
        """Collect system metrics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            return {
                "system_cpu_usage": cpu_percent,
                "system_memory_usage": memory.percent,
                "system_disk_usage": disk.percent,
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}

    async def _collect_memory_metrics(self) -> Dict[str, float]:
        """Collect memory metrics."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            return {
                "memory_total_mb": memory.total / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024),
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_swap_used_mb": swap.used / (1024 * 1024) if swap else 0,
            }
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
            return {}

    async def _collect_disk_metrics(self) -> Dict[str, float]:
        """Collect disk metrics."""
        try:
            disk = psutil.disk_usage("/")
            io_counters = psutil.disk_io_counters()

            return {
                "disk_total_gb": disk.total / (1024 ** 3),
                "disk_used_gb": disk.used / (1024 ** 3),
                "disk_free_gb": disk.free / (1024 ** 3),
                "disk_read_bytes": io_counters.read_bytes if io_counters else 0,
                "disk_write_bytes": io_counters.write_bytes if io_counters else 0,
            }
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
            return {}

    async def _collect_network_metrics(self) -> Dict[str, float]:
        """Collect network metrics."""
        try:
            io_counters = psutil.net_io_counters()
            connections = psutil.net_connections()

            return {
                "network_bytes_sent": io_counters.bytes_sent,
                "network_bytes_recv": io_counters.bytes_recv,
                "network_packets_sent": io_counters.packets_sent,
                "network_packets_recv": io_counters.packets_recv,
                "network_connections": len(connections),
            }
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            return {}

    async def _save_metric_series(self, name: str):
        """Save metric series to storage."""
        try:
            series = self._metrics[name]

            # Only save if there are points
            if not series.points:
                return

            # Create subdirectory by metric name
            metric_path = self.storage_path / name
            metric_path.mkdir(parents=True, exist_ok=True)

            # Save to file with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_path = metric_path / f"{timestamp}.json"

            data = series.to_dict()
            async with aiofiles.open(file_path, "w") as f:
                await f.write(json.dumps(data, indent=2))

            # Clean old files
            await self._clean_old_metrics(name)

        except Exception as e:
            logger.error(f"Error saving metric series {name}: {e}")

    async def _clean_old_metrics(self, name: str):
        """
        Clean old metric files.

        Args:
            name: Metric name
        """
        try:
            metric_path = self.storage_path / name
            if not metric_path.exists():
                return

            definition = self._definitions.get(name)
            if not definition:
                return

            retention_days = definition.retention_days
            cutoff = datetime.utcnow() - timedelta(days=retention_days)

            for file_path in metric_path.glob("*.json"):
                try:
                    # Extract timestamp from filename
                    timestamp_str = file_path.stem.split("_")[0]
                    file_time = datetime.strptime(timestamp_str, "%Y%m%d")

                    if file_time < cutoff:
                        file_path.unlink()
                        logger.debug(f"Removed old metric file: {file_path}")
                except Exception as e:
                    logger.debug(f"Error cleaning metric file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error cleaning old metrics {name}: {e}")

    async def load_historical_metrics(
        self,
        name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[MetricPoint]:
        """
        Load historical metrics from storage.

        Args:
            name: Metric name
            start_time: Start time
            end_time: End time

        Returns:
            List of metric points
        """
        points = []

        try:
            metric_path = self.storage_path / name
            if not metric_path.exists():
                return []

            for file_path in sorted(metric_path.glob("*.json")):
                try:
                    async with aiofiles.open(file_path, "r") as f:
                        content = await f.read()
                        data = json.loads(content)

                        series = MetricSeries.from_dict(data)

                        for point in series.points:
                            if start_time and point.timestamp < start_time:
                                continue
                            if end_time and point.timestamp > end_time:
                                continue
                            points.append(point)

                except Exception as e:
                    logger.debug(f"Error loading metric file {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error loading historical metrics {name}: {e}")

        return points

    async def export_metrics(
        self,
        names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json",
    ) -> Union[str, pd.DataFrame]:
        """
        Export metrics in various formats.

        Args:
            names: List of metric names
            start_time: Start time
            end_time: End time
            format: Export format ("json", "csv", "parquet")

        Returns:
            Exported data
        """
        metrics = await self.get_metrics(names, start_time, end_time)

        if format == "json":
            return json.dumps({
                name: [p.to_dict() for p in points]
                for name, points in metrics.items()
            }, indent=2)

        elif format == "csv":
            # Convert to DataFrame
            data = []
            for name, points in metrics.items():
                for point in points:
                    data.append({
                        "metric": name,
                        "timestamp": point.timestamp,
                        "value": point.value,
                        **point.labels,
                    })
            return pd.DataFrame(data).to_csv(index=False)

        elif format == "parquet":
            # Convert to DataFrame
            data = []
            for name, points in metrics.items():
                for point in points:
                    data.append({
                        "metric": name,
                        "timestamp": point.timestamp,
                        "value": point.value,
                        **point.labels,
                    })
            return pd.DataFrame(data)

        else:
            raise ValueError(f"Unsupported format: {format}")

    async def add_definition(self, definition: MetricDefinition):
        """
        Add a new metric definition.

        Args:
            definition: Metric definition
        """
        async with self._lock:
            if definition.name in self._definitions:
                raise ValueError(f"Metric already exists: {definition.name}")

            self._definitions[definition.name] = definition
            self._metrics[definition.name] = MetricSeries(
                name=definition.name,
                definition=definition,
            )

            await self._save_definitions()
            logger.info(f"Added metric definition: {definition.name}")

    async def update_definition(self, name: str, updates: Dict[str, Any]):
        """
        Update a metric definition.

        Args:
            name: Metric name
            updates: Updates to apply
        """
        async with self._lock:
            if name not in self._definitions:
                raise ValueError(f"Metric not found: {name}")

            definition = self._definitions[name]

            for key, value in updates.items():
                if key == "type":
                    value = MetricType(value)
                elif key == "aggregation":
                    value = AggregationType(value)
                setattr(definition, key, value)

            # Update series
            self._metrics[name].definition = definition

            await self._save_definitions()
            logger.info(f"Updated metric definition: {name}")

    async def _save_definitions(self):
        """Save metric definitions to file."""
        try:
            data = {
                "metrics": [
                    definition.to_dict()
                    for definition in self._definitions.values()
                ]
            }

            self.definitions_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.definitions_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving metric definitions: {e}")

    async def shutdown(self):
        """Shutdown the metric collector."""
        if self._collector_task:
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass

        if self._agg_task:
            self._agg_task.cancel()
            try:
                await self._agg_task
            except asyncio.CancelledError:
                pass

        # Flush buffer
        if self._buffer:
            await self._aggregate_metrics()

        logger.info("MetricCollector shut down")


# Export singleton
metric_collector = MetricCollector()
