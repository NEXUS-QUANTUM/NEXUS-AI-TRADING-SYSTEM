"""
NEXUS AI TRADING SYSTEM - Performance Tracker
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced performance tracking system for real-time monitoring of trading bots,
models, and strategies with comprehensive data collection, aggregation,
and visualization capabilities.
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

import numpy as np
import pandas as pd
import psutil
import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
TRACKER_COUNTER = Counter(
    "nexus_performance_tracker_entries_total",
    "Total number of performance entries tracked",
    ["tracker_type", "component"],
)
TRACKER_DURATION = Histogram(
    "nexus_performance_tracker_duration_seconds",
    "Duration of performance tracking operations",
    ["operation"],
)
PERFORMANCE_POINTS_GAUGE = Gauge(
    "nexus_performance_tracker_points",
    "Number of performance tracking points",
    ["component"],
)


class TrackerType(Enum):
    """Types of performance trackers."""

    REAL_TIME = "realtime"
    AGGREGATED = "aggregated"
    HISTORICAL = "historical"
    WINDOWED = "windowed"
    EVENT_BASED = "event_based"


class AggregationWindow(Enum):
    """Aggregation windows for performance data."""

    MINUTE = "1min"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


@dataclass
class PerformanceEntry:
    """Single performance tracking entry."""

    timestamp: datetime
    component: str
    metric_name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tracker_type: TrackerType = TrackerType.REAL_TIME

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "metric_name": self.metric_name,
            "value": self.value,
            "labels": self.labels,
            "metadata": self.metadata,
            "tracker_type": self.tracker_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            component=data["component"],
            metric_name=data["metric_name"],
            value=data["value"],
            labels=data.get("labels", {}),
            metadata=data.get("metadata", {}),
            tracker_type=TrackerType(data.get("tracker_type", "realtime")),
        )


@dataclass
class AggregatedData:
    """Aggregated performance data."""

    window: AggregationWindow
    component: str
    metric_name: str
    count: int
    sum: float
    mean: float
    min: float
    max: float
    std: float
    p50: float
    p95: float
    p99: float
    start_time: datetime
    end_time: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window": self.window.value,
            "component": self.component,
            "metric_name": self.metric_name,
            "count": self.count,
            "sum": self.sum,
            "mean": self.mean,
            "min": self.min,
            "max": self.max,
            "std": self.std,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
        }


@dataclass
class TrackerConfig:
    """Configuration for a performance tracker."""

    name: str
    tracker_type: TrackerType
    component: str
    metrics: List[str]
    labels: List[str] = field(default_factory=list)
    aggregation_window: Optional[AggregationWindow] = None
    retention_days: int = 30
    max_points: int = 10000
    batch_size: int = 100
    flush_interval_seconds: int = 60
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "tracker_type": self.tracker_type.value,
            "component": self.component,
            "metrics": self.metrics,
            "labels": self.labels,
            "aggregation_window": self.aggregation_window.value if self.aggregation_window else None,
            "retention_days": self.retention_days,
            "max_points": self.max_points,
            "batch_size": self.batch_size,
            "flush_interval_seconds": self.flush_interval_seconds,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackerConfig":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            tracker_type=TrackerType(data["tracker_type"]),
            component=data["component"],
            metrics=data["metrics"],
            labels=data.get("labels", []),
            aggregation_window=AggregationWindow(data["aggregation_window"]) if data.get("aggregation_window") else None,
            retention_days=data.get("retention_days", 30),
            max_points=data.get("max_points", 10000),
            batch_size=data.get("batch_size", 100),
            flush_interval_seconds=data.get("flush_interval_seconds", 60),
            enabled=data.get("enabled", True),
        )


class PerformanceTracker:
    """
    Advanced performance tracking system for real-time monitoring.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the performance tracker.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._entries: List[PerformanceEntry] = []
        self._aggregated: Dict[str, List[AggregatedData]] = {}
        self._trackers: Dict[str, TrackerConfig] = {}
        self._buffer: deque = deque(maxlen=10000)
        self._flush_task: Optional[asyncio.Task] = None
        self._aggregation_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Load configuration
        self.tracker_config = self.config.get("performance_tracker", {})
        self.storage_path = Path(self.tracker_config.get("storage_path", "./data/performance"))
        self.configs_path = Path(self.tracker_config.get("configs_path", "./configs/performance/trackers.yaml"))
        self.default_retention_days = self.tracker_config.get("default_retention_days", 30)
        self.max_entries = self.tracker_config.get("max_entries", 100000)
        self.flush_interval = self.tracker_config.get("flush_interval", 60)
        self.aggregation_interval = self.tracker_config.get("aggregation_interval", 300)

        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load tracker configs
        self._load_tracker_configs()

        # Register default trackers
        self._register_default_trackers()

        # Start background tasks
        self._start_background_tasks()

        logger.info(f"PerformanceTracker initialized with {len(self._trackers)} trackers")

    def _load_tracker_configs(self):
        """Load tracker configurations."""
        try:
            if self.configs_path.exists():
                with open(self.configs_path, "r") as f:
                    data = yaml.safe_load(f)
                    for tracker_data in data.get("trackers", []):
                        config = TrackerConfig.from_dict(tracker_data)
                        self._trackers[config.name] = config
                logger.info(f"Loaded {len(self._trackers)} tracker configs")
        except Exception as e:
            logger.error(f"Error loading tracker configs: {e}")

    def _register_default_trackers(self):
        """Register default performance trackers."""
        default_trackers = [
            TrackerConfig(
                name="system_tracker",
                tracker_type=TrackerType.REAL_TIME,
                component="system",
                metrics=["cpu_usage", "memory_usage", "disk_usage", "network_io"],
                labels=["host"],
                retention_days=7,
                max_points=10000,
                flush_interval_seconds=30,
            ),
            TrackerConfig(
                name="trading_tracker",
                tracker_type=TrackerType.AGGREGATED,
                component="trading",
                metrics=["sharpe_ratio", "win_rate", "profit_factor", "max_drawdown",
                        "total_pnl", "trade_count", "volume"],
                labels=["symbol", "strategy"],
                aggregation_window=AggregationWindow.HOUR,
                retention_days=30,
                max_points=50000,
                flush_interval_seconds=60,
            ),
            TrackerConfig(
                name="model_tracker",
                tracker_type=TrackerType.WINDOWED,
                component="model",
                metrics=["accuracy", "precision", "recall", "f1_score",
                        "inference_time", "memory_usage"],
                labels=["model_id", "version"],
                aggregation_window=AggregationWindow.FIFTEEN_MINUTES,
                retention_days=14,
                max_points=20000,
                flush_interval_seconds=60,
            ),
            TrackerConfig(
                name="bot_tracker",
                tracker_type=TrackerType.EVENT_BASED,
                component="bot",
                metrics=["orders_placed", "orders_filled", "position_pnl",
                        "execution_time", "slippage"],
                labels=["bot_id", "strategy"],
                retention_days=30,
                max_points=50000,
                flush_interval_seconds=30,
            ),
        ]

        for tracker in default_trackers:
            if tracker.name not in self._trackers:
                self._trackers[tracker.name] = tracker

        logger.info(f"Registered {len(default_trackers)} default trackers")

    def _start_background_tasks(self):
        """Start background tasks."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._flush_loop())

        if self._aggregation_task is None:
            self._aggregation_task = asyncio.create_task(self._aggregation_loop())

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _flush_loop(self):
        """Background loop for flushing entries to storage."""
        while True:
            try:
                await self._flush_entries()
                await asyncio.sleep(self.flush_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")
                await asyncio.sleep(5)

    async def _aggregation_loop(self):
        """Background loop for aggregating performance data."""
        while True:
            try:
                await self._aggregate_entries()
                await asyncio.sleep(self.aggregation_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(10)

    async def _cleanup_loop(self):
        """Background loop for cleaning old entries."""
        while True:
            try:
                await self._cleanup_old_entries()
                await asyncio.sleep(3600)  # Run every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)

    async def track(
        self,
        component: str,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tracker_name: Optional[str] = None,
    ) -> None:
        """
        Track a performance metric.

        Args:
            component: Component name
            metric_name: Metric name
            value: Metric value
            labels: Metric labels
            metadata: Additional metadata
            tracker_name: Specific tracker to use
        """
        # Validate tracker
        if tracker_name:
            if tracker_name not in self._trackers:
                raise ValueError(f"Tracker not found: {tracker_name}")
            tracker = self._trackers[tracker_name]
            if not tracker.enabled:
                return
        else:
            # Find matching tracker
            tracker = None
            for t in self._trackers.values():
                if t.enabled and t.component == component and metric_name in t.metrics:
                    tracker = t
                    break

            if not tracker:
                # Use default tracker
                tracker = self._trackers.get("system_tracker")
                if not tracker or not tracker.enabled:
                    return

        # Validate labels
        if labels and tracker.labels:
            for key in labels:
                if key not in tracker.labels:
                    logger.warning(f"Label {key} not configured for tracker {tracker.name}")

        # Create entry
        entry = PerformanceEntry(
            timestamp=datetime.utcnow(),
            component=component,
            metric_name=metric_name,
            value=float(value),
            labels=labels or {},
            metadata=metadata or {},
            tracker_type=tracker.tracker_type,
        )

        # Add to buffer
        self._buffer.append(entry)

        # Update metrics
        TRACKER_COUNTER.labels(
            tracker_type=tracker.tracker_type.value,
            component=component,
        ).inc()
        PERFORMANCE_POINTS_GAUGE.labels(component=component).inc()

        # Real-time trackers update immediately
        if tracker.tracker_type == TrackerType.REAL_TIME:
            await self._process_realtime_entry(entry)

    async def _process_realtime_entry(self, entry: PerformanceEntry):
        """
        Process a real-time performance entry.

        Args:
            entry: Performance entry
        """
        # Store in cache for real-time access
        cache_key = f"perf:{entry.component}:{entry.metric_name}"
        await self.cache_manager.set(cache_key, entry.to_dict(), 3600)

        # Update in-memory storage
        async with self._lock:
            self._entries.append(entry)

            # Limit entries
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]

    async def _flush_entries(self):
        """Flush buffered entries to storage."""
        if not self._buffer:
            return

        async with self._lock:
            # Get current buffer
            batch = []
            while self._buffer:
                entry = self._buffer.popleft()
                batch.append(entry)

            if not batch:
                return

            # Group by date
            grouped = defaultdict(list)
            for entry in batch:
                date_key = entry.timestamp.strftime("%Y%m%d")
                grouped[date_key].append(entry)

            # Save to storage
            for date_key, entries in grouped.items():
                date_path = self.storage_path / date_key
                date_path.mkdir(parents=True, exist_ok=True)

                filename = f"{int(time.time())}_{len(entries)}.json"
                file_path = date_path / filename

                data = [e.to_dict() for e in entries]

                async with aiofiles.open(file_path, "w") as f:
                    await f.write(json.dumps(data, indent=2))

    async def _aggregate_entries(self):
        """Aggregate performance entries."""
        async with self._lock:
            # Get entries to aggregate
            entries = self._entries

            if not entries:
                return

            # Group by component and metric
            for tracker in self._trackers.values():
                if not tracker.enabled or tracker.aggregation_window is None:
                    continue

                # Filter entries for this tracker
                tracker_entries = [
                    e for e in entries
                    if e.component == tracker.component
                    and e.metric_name in tracker.metrics
                ]

                if not tracker_entries:
                    continue

                # Aggregate by window
                window_size = self._get_window_seconds(tracker.aggregation_window)
                window_start = tracker_entries[0].timestamp

                # Group by window
                window_groups = defaultdict(list)
                for entry in tracker_entries:
                    window_key = int(entry.timestamp.timestamp() / window_size) * window_size
                    window_groups[window_key].append(entry)

                # Calculate aggregates
                for window_key, group in window_groups.items():
                    values = [e.value for e in group]
                    start_time = datetime.fromtimestamp(window_key)
                    end_time = start_time + timedelta(seconds=window_size)

                    aggregated = AggregatedData(
                        window=tracker.aggregation_window,
                        component=tracker.component,
                        metric_name=tracker.metric_name,
                        count=len(values),
                        sum=float(np.sum(values)),
                        mean=float(np.mean(values)),
                        min=float(np.min(values)),
                        max=float(np.max(values)),
                        std=float(np.std(values)),
                        p50=float(np.percentile(values, 50)),
                        p95=float(np.percentile(values, 95)),
                        p99=float(np.percentile(values, 99)),
                        start_time=start_time,
                        end_time=end_time,
                    )

                    # Store aggregated data
                    if tracker.metric_name not in self._aggregated:
                        self._aggregated[tracker.metric_name] = []
                    self._aggregated[tracker.metric_name].append(aggregated)

                    # Limit aggregated data
                    if len(self._aggregated[tracker.metric_name]) > 1000:
                        self._aggregated[tracker.metric_name] = (
                            self._aggregated[tracker.metric_name][-1000:]
                        )

            # Clear processed entries
            self._entries.clear()

    def _get_window_seconds(self, window: AggregationWindow) -> int:
        """Get window size in seconds."""
        window_map = {
            AggregationWindow.MINUTE: 60,
            AggregationWindow.FIVE_MINUTES: 300,
            AggregationWindow.FIFTEEN_MINUTES: 900,
            AggregationWindow.HOUR: 3600,
            AggregationWindow.FOUR_HOURS: 14400,
            AggregationWindow.DAY: 86400,
            AggregationWindow.WEEK: 604800,
            AggregationWindow.MONTH: 2592000,
        }
        return window_map.get(window, 3600)

    async def _cleanup_old_entries(self):
        """Clean up old entries and files."""
        async with self._lock:
            # Clean in-memory entries
            cutoff_time = datetime.utcnow() - timedelta(days=self.default_retention_days)

            self._entries = [
                e for e in self._entries
                if e.timestamp > cutoff_time
            ]

            # Clean aggregated data
            for metric_name in list(self._aggregated.keys()):
                self._aggregated[metric_name] = [
                    a for a in self._aggregated[metric_name]
                    if a.end_time > cutoff_time
                ]

            # Clean storage files
            for date_dir in self.storage_path.glob("*"):
                if not date_dir.is_dir():
                    continue

                try:
                    date_obj = datetime.strptime(date_dir.name, "%Y%m%d")
                    if (datetime.utcnow() - date_obj).days > self.default_retention_days:
                        shutil.rmtree(date_dir)
                        logger.info(f"Removed old data directory: {date_dir}")
                except ValueError:
                    continue

    async def get_entries(
        self,
        component: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[PerformanceEntry]:
        """
        Get performance entries.

        Args:
            component: Filter by component
            metric_name: Filter by metric name
            start_time: Filter start time
            end_time: Filter end time
            limit: Maximum number of entries
            offset: Offset for pagination

        Returns:
            List of performance entries
        """
        async with self._lock:
            entries = self._entries.copy()

            if component:
                entries = [e for e in entries if e.component == component]

            if metric_name:
                entries = [e for e in entries if e.metric_name == metric_name]

            if start_time:
                entries = [e for e in entries if e.timestamp >= start_time]

            if end_time:
                entries = [e for e in entries if e.timestamp <= end_time]

            entries.sort(key=lambda x: x.timestamp, reverse=True)
            return entries[offset:offset + limit]

    async def get_aggregated(
        self,
        component: Optional[str] = None,
        metric_name: Optional[str] = None,
        window: Optional[AggregationWindow] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AggregatedData]:
        """
        Get aggregated performance data.

        Args:
            component: Filter by component
            metric_name: Filter by metric name
            window: Filter by aggregation window
            start_time: Filter start time
            end_time: Filter end time

        Returns:
            List of aggregated data
        """
        async with self._lock:
            aggregated = []

            for metric, data in self._aggregated.items():
                for agg in data:
                    if component and agg.component != component:
                        continue
                    if metric_name and agg.metric_name != metric_name:
                        continue
                    if window and agg.window != window:
                        continue
                    if start_time and agg.end_time < start_time:
                        continue
                    if end_time and agg.start_time > end_time:
                        continue
                    aggregated.append(agg)

            aggregated.sort(key=lambda x: x.start_time, reverse=True)
            return aggregated

    async def get_realtime_metrics(
        self,
        component: str,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get real-time metrics for a component.

        Args:
            component: Component name
            metrics: Specific metrics to retrieve

        Returns:
            Real-time metrics
        """
        result = {}

        for metric in metrics or []:
            cache_key = f"perf:{component}:{metric}"
            cached = await self.cache_manager.get(cache_key)

            if cached:
                result[metric] = cached["value"]

        return result

    async def get_component_metrics(
        self,
        component: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive metrics for a component.

        Args:
            component: Component name
            since: Time to fetch data from

        Returns:
            Component metrics
        """
        since = since or (datetime.utcnow() - timedelta(hours=24))

        entries = await self.get_entries(
            component=component,
            start_time=since,
            limit=10000,
        )

        if not entries:
            return {
                "component": component,
                "metrics": {},
                "count": 0,
                "last_updated": None,
            }

        # Group by metric
        metrics = {}
        for entry in entries:
            if entry.metric_name not in metrics:
                metrics[entry.metric_name] = []
            metrics[entry.metric_name].append(entry.value)

        # Calculate statistics
        result = {
            "component": component,
            "metrics": {},
            "count": len(entries),
            "last_updated": max(e.timestamp for e in entries).isoformat(),
        }

        for metric_name, values in metrics.items():
            if len(values) > 0:
                result["metrics"][metric_name] = {
                    "current": values[-1],
                    "mean": float(np.mean(values)),
                    "median": float(np.median(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "std": float(np.std(values)),
                    "count": len(values),
                }

        return result

    async def get_tracker_stats(self) -> Dict[str, Any]:
        """
        Get tracker statistics.

        Returns:
            Tracker statistics
        """
        async with self._lock:
            total_entries = len(self._entries)
            buffer_size = len(self._buffer)

            stats = {
                "total_entries": total_entries,
                "buffer_size": buffer_size,
                "trackers": {},
                "aggregated_metrics": len(self._aggregated),
                "storage_used_mb": await self._get_storage_usage(),
            }

            for name, tracker in self._trackers.items():
                stats["trackers"][name] = {
                    "enabled": tracker.enabled,
                    "type": tracker.tracker_type.value,
                    "component": tracker.component,
                    "metrics": tracker.metrics,
                    "retention_days": tracker.retention_days,
                }

            return stats

    async def _get_storage_usage(self) -> float:
        """Get storage usage in MB."""
        try:
            total_size = 0
            for file_path in self.storage_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size / (1024 * 1024)
        except Exception:
            return 0.0

    async def get_tracker_config(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific tracker configuration.

        Args:
            name: Tracker name

        Returns:
            Tracker config or None
        """
        config = self._trackers.get(name)
        return config.to_dict() if config else None

    async def get_tracker_configs(self) -> List[Dict[str, Any]]:
        """
        Get all tracker configurations.

        Returns:
            List of tracker configs
        """
        return [c.to_dict() for c in self._trackers.values()]

    async def add_tracker_config(self, config: TrackerConfig) -> bool:
        """
        Add a tracker configuration.

        Args:
            config: Tracker configuration

        Returns:
            True if added
        """
        async with self._lock:
            if config.name in self._trackers:
                return False

            self._trackers[config.name] = config
            await self._save_tracker_configs()
            logger.info(f"Added tracker config: {config.name}")
            return True

    async def update_tracker_config(self, name: str, updates: Dict[str, Any]) -> bool:
        """
        Update a tracker configuration.

        Args:
            name: Tracker name
            updates: Updates to apply

        Returns:
            True if updated
        """
        async with self._lock:
            if name not in self._trackers:
                return False

            config = self._trackers[name]

            for key, value in updates.items():
                if key == "tracker_type":
                    value = TrackerType(value)
                elif key == "aggregation_window":
                    value = AggregationWindow(value) if value else None
                setattr(config, key, value)

            await self._save_tracker_configs()
            logger.info(f"Updated tracker config: {name}")
            return True

    async def _save_tracker_configs(self):
        """Save tracker configurations."""
        try:
            data = {
                "trackers": [c.to_dict() for c in self._trackers.values()]
            }

            with open(self.configs_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving tracker configs: {e}")

    async def export_data(
        self,
        component: Optional[str] = None,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "csv",
        output_path: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Export performance data.

        Args:
            component: Filter by component
            metric_name: Filter by metric name
            start_time: Filter start time
            end_time: Filter end time
            format: Export format ("csv", "json", "parquet")
            output_path: Output path

        Returns:
            Output path or None
        """
        # Get data
        entries = await self.get_entries(
            component=component,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        if not entries:
            logger.warning("No data to export")
            return None

        # Convert to DataFrame
        data = []
        for entry in entries:
            row = {
                "timestamp": entry.timestamp,
                "component": entry.component,
                "metric_name": entry.metric_name,
                "value": entry.value,
                **entry.labels,
            }
            data.append(row)

        df = pd.DataFrame(data)

        # Set output path
        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            component_str = component or "all"
            output_path = self.storage_path / "exports" / f"{component_str}_{timestamp}.{format}"
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Export
        if format == "csv":
            df.to_csv(output_path, index=False)
        elif format == "json":
            df.to_json(output_path, orient="records", date_format="iso")
        elif format == "parquet":
            try:
                import pyarrow
                df.to_parquet(output_path, index=False)
            except ImportError:
                logger.warning("pyarrow not installed, falling back to CSV")
                output_path = output_path.with_suffix(".csv")
                df.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported {len(entries)} entries to {output_path}")
        return output_path

    async def get_metric_series(
        self,
        component: str,
        metric_name: str,
        since: Optional[datetime] = None,
        resolution: str = "5min",
    ) -> pd.Series:
        """
        Get metric time series.

        Args:
            component: Component name
            metric_name: Metric name
            since: Time to fetch from
            resolution: Resolution for resampling

        Returns:
            Time series as pandas Series
        """
        since = since or (datetime.utcnow() - timedelta(days=7))

        entries = await self.get_entries(
            component=component,
            metric_name=metric_name,
            start_time=since,
            limit=50000,
        )

        if not entries:
            return pd.Series()

        # Create Series
        data = {e.timestamp: e.value for e in entries}
        series = pd.Series(data)

        # Resample
        series = series.sort_index()
        series = series.resample(resolution).mean()

        return series

    async def get_metric_stats(
        self,
        component: str,
        metric_name: str,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get metric statistics.

        Args:
            component: Component name
            metric_name: Metric name
            since: Time to fetch from

        Returns:
            Metric statistics
        """
        since = since or (datetime.utcnow() - timedelta(days=30))

        entries = await self.get_entries(
            component=component,
            metric_name=metric_name,
            start_time=since,
            limit=50000,
        )

        if not entries:
            return {
                "metric": metric_name,
                "component": component,
                "count": 0,
            }

        values = [e.value for e in entries]
        timestamps = [e.timestamp for e in entries]

        return {
            "metric": metric_name,
            "component": component,
            "count": len(values),
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "std": float(np.std(values)),
            "q95": float(np.percentile(values, 95)),
            "q99": float(np.percentile(values, 99)),
            "start_time": min(timestamps).isoformat(),
            "end_time": max(timestamps).isoformat(),
        }

    async def shutdown(self):
        """Shutdown the performance tracker."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        if self._aggregation_task:
            self._aggregation_task.cancel()
            try:
                await self._aggregation_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Flush remaining entries
        if self._buffer:
            await self._flush_entries()

        logger.info("PerformanceTracker shut down")


# Export singleton
performance_tracker = PerformanceTracker()
