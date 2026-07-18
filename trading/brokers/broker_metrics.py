# trading/brokers/broker_metrics.py
"""
NEXUS AI TRADING SYSTEM - Broker Metrics Collection
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides comprehensive metrics collection and monitoring
for broker operations. It tracks performance metrics, error rates,
latency, throughput, and other key indicators for broker health
and performance analysis.
"""

import asyncio
import time
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Awaitable
from collections import deque, defaultdict
from threading import Lock

from shared.utilities.logger import get_logger
from .base import BaseBroker, BrokerException

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class MetricType(str, Enum):
    """Types of metrics collected"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"
    PERCENTILE = "percentile"


class MetricAggregation(str, Enum):
    """Aggregation methods for metrics"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    PERCENTILE_50 = "p50"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"
    PERCENTILE_999 = "p999"


@dataclass
class MetricValue:
    """A single metric value"""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


@dataclass
class MetricAggregationResult:
    """Result of metric aggregation"""
    name: str
    value: float
    aggregation: MetricAggregation
    timestamp: float = field(default_factory=time.time)
    sample_count: int = 0
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class BrokerMetricsSnapshot:
    """Snapshot of broker metrics at a point in time"""
    broker_id: str
    broker_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Connection metrics
    is_connected: bool = False
    connection_uptime: float = 0.0
    reconnect_count: int = 0
    
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    error_rate: float = 0.0
    
    # Latency metrics
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Throughput metrics
    requests_per_second: float = 0.0
    requests_per_minute: float = 0.0
    requests_per_hour: float = 0.0
    
    # Order metrics
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    order_error_rate: float = 0.0
    
    # Account metrics
    balance: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    open_positions: int = 0
    open_orders: int = 0
    
    # Health metrics
    health_status: str = "unknown"
    last_health_check: Optional[datetime] = None
    
    # Custom metrics
    custom: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "broker_id": self.broker_id,
            "broker_name": self.broker_name,
            "timestamp": self.timestamp.isoformat(),
            "connection": {
                "is_connected": self.is_connected,
                "uptime": self.connection_uptime,
                "reconnect_count": self.reconnect_count,
            },
            "requests": {
                "total": self.total_requests,
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "error_rate": self.error_rate,
            },
            "latency": {
                "avg_ms": self.avg_latency_ms,
                "max_ms": self.max_latency_ms,
                "min_ms": self.min_latency_ms,
                "p95_ms": self.p95_latency_ms,
                "p99_ms": self.p99_latency_ms,
            },
            "throughput": {
                "per_second": self.requests_per_second,
                "per_minute": self.requests_per_minute,
                "per_hour": self.requests_per_hour,
            },
            "orders": {
                "total": self.total_orders,
                "successful": self.successful_orders,
                "failed": self.failed_orders,
                "error_rate": self.order_error_rate,
            },
            "account": {
                "balance": self.balance,
                "equity": self.equity,
                "buying_power": self.buying_power,
                "open_positions": self.open_positions,
                "open_orders": self.open_orders,
            },
            "health": {
                "status": self.health_status,
                "last_check": self.last_health_check.isoformat() if self.last_health_check else None,
            },
            "custom": self.custom,
        }


# ============================================================================
# METRIC COLLECTOR
# ============================================================================

class BrokerMetricsCollector:
    """
    Collects and manages metrics for broker operations.
    
    Features:
    - Real-time metric collection
    - Support for counters, gauges, histograms, and timers
    - Metric aggregation and reporting
    - Configurable retention and sampling
    - Thread-safe operations
    """
    
    def __init__(
        self,
        broker_id: str,
        broker_name: str = "unknown",
        max_samples: int = 10000,
        retention_days: int = 7,
    ):
        """
        Initialize the metrics collector.
        
        Args:
            broker_id: Broker identifier
            broker_name: Broker name
            max_samples: Maximum number of samples to keep
            retention_days: Number of days to retain metrics
        """
        self.broker_id = broker_id
        self.broker_name = broker_name
        self.max_samples = max_samples
        self.retention_days = retention_days
        
        # Metric storage
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self._timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self._rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        
        # Time series data
        self._time_series: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        
        # Request tracking
        self._request_timestamps: deque = deque(maxlen=max_samples)
        self._error_timestamps: deque = deque(maxlen=max_samples)
        self._order_timestamps: deque = deque(maxlen=max_samples)
        self._order_error_timestamps: deque = deque(maxlen=max_samples)
        
        # Latency tracking
        self._latency_samples: deque = deque(maxlen=max_samples)
        
        # Account snapshots
        self._account_snapshots: List[Tuple[float, float, float]] = []  # timestamp, balance, equity
        
        # Lock for thread safety
        self._lock = Lock()
        
        # Start time
        self._start_time = time.time()
        self._last_cleanup = time.time()
        
        self.logger = logger
    
    # ========================================================================
    # METRIC RECORDING
    # ========================================================================
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Value to increment by
            tags: Optional tags
        """
        with self._lock:
            key = self._build_key(name, tags)
            self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
            tags: Optional tags
        """
        with self._lock:
            key = self._build_key(name, tags)
            self._gauges[key] = value
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram value.
        
        Args:
            name: Metric name
            value: Value to record
            tags: Optional tags
        """
        with self._lock:
            key = self._build_key(name, tags)
            self._histograms[key].append(value)
    
    def record_timer(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a timer duration.
        
        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            tags: Optional tags
        """
        with self._lock:
            key = self._build_key(name, tags)
            self._timers[key].append(duration_ms)
    
    def record_rate(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a rate value.
        
        Args:
            name: Metric name
            value: Rate value
            tags: Optional tags
        """
        with self._lock:
            key = self._build_key(name, tags)
            self._rates[key].append(value)
    
    def record_request(self, success: bool, latency_ms: float) -> None:
        """
        Record a request.
        
        Args:
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
        """
        with self._lock:
            self._request_timestamps.append(time.time())
            self._latency_samples.append(latency_ms)
            
            if not success:
                self._error_timestamps.append(time.time())
    
    def record_order(self, success: bool) -> None:
        """
        Record an order.
        
        Args:
            success: Whether the order was successful
        """
        with self._lock:
            self._order_timestamps.append(time.time())
            if not success:
                self._order_error_timestamps.append(time.time())
    
    def record_account_snapshot(self, balance: float, equity: float, buying_power: float) -> None:
        """
        Record an account snapshot.
        
        Args:
            balance: Account balance
            equity: Account equity
            buying_power: Buying power
        """
        with self._lock:
            self._account_snapshots.append((time.time(), balance, equity, buying_power))
            
            # Trim snapshots if too many
            if len(self._account_snapshots) > self.max_samples:
                self._account_snapshots = self._account_snapshots[-self.max_samples:]
    
    def _build_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """
        Build a key for metric storage.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            str: Storage key
        """
        if not tags:
            return name
        
        # Sort tags for consistent key
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}:{tag_str}"
    
    # ========================================================================
    # METRIC AGGREGATION
    # ========================================================================
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """
        Get counter value.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            float: Counter value
        """
        with self._lock:
            key = self._build_key(name, tags)
            return self._counters.get(key, 0.0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """
        Get gauge value.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            float: Gauge value
        """
        with self._lock:
            key = self._build_key(name, tags)
            return self._gauges.get(key, 0.0)
    
    def get_histogram_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """
        Get histogram statistics.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Dict: Statistics including count, sum, avg, min, max, percentiles
        """
        with self._lock:
            key = self._build_key(name, tags)
            values = list(self._histograms.get(key, []))
            
            if not values:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }
            
            sorted_values = sorted(values)
            total = sum(values)
            
            return {
                "count": len(values),
                "sum": total,
                "avg": total / len(values),
                "min": min(values),
                "max": max(values),
                "p50": self._percentile(sorted_values, 50),
                "p95": self._percentile(sorted_values, 95),
                "p99": self._percentile(sorted_values, 99),
            }
    
    def get_timer_stats(
        self,
        name: str,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """
        Get timer statistics.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            Dict: Statistics including count, sum, avg, min, max, percentiles
        """
        with self._lock:
            key = self._build_key(name, tags)
            values = list(self._timers.get(key, []))
            
            if not values:
                return {
                    "count": 0,
                    "sum": 0.0,
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }
            
            sorted_values = sorted(values)
            total = sum(values)
            
            return {
                "count": len(values),
                "sum": total,
                "avg": total / len(values),
                "min": min(values),
                "max": max(values),
                "p50": self._percentile(sorted_values, 50),
                "p95": self._percentile(sorted_values, 95),
                "p99": self._percentile(sorted_values, 99),
            }
    
    def get_rate(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """
        Get rate value.
        
        Args:
            name: Metric name
            tags: Optional tags
            
        Returns:
            float: Rate value
        """
        with self._lock:
            key = self._build_key(name, tags)
            values = list(self._rates.get(key, []))
            if not values:
                return 0.0
            return sum(values) / len(values)
    
    def _percentile(self, sorted_values: List[float], percentile: int) -> float:
        """
        Calculate percentile from sorted values.
        
        Args:
            sorted_values: Sorted list of values
            percentile: Percentile (0-100)
            
        Returns:
            float: Percentile value
        """
        if not sorted_values:
            return 0.0
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        lower = int(math.floor(index))
        upper = int(math.ceil(index))
        
        if lower == upper:
            return sorted_values[lower]
        
        return sorted_values[lower] * (upper - index) + sorted_values[upper] * (index - lower)
    
    # ========================================================================
    # SNAPSHOT GENERATION
    # ========================================================================
    
    def get_snapshot(
        self,
        health_status: str = "unknown",
        last_health_check: Optional[datetime] = None,
    ) -> BrokerMetricsSnapshot:
        """
        Get a snapshot of current metrics.
        
        Args:
            health_status: Current health status
            last_health_check: Last health check timestamp
            
        Returns:
            BrokerMetricsSnapshot: Metrics snapshot
        """
        with self._lock:
            now = time.time()
            
            # Calculate request metrics
            total_requests = len(self._request_timestamps)
            total_errors = len(self._error_timestamps)
            successful_requests = total_requests - total_errors
            error_rate = (total_errors / max(total_requests, 1)) * 100
            
            # Calculate latency metrics
            latency_list = list(self._latency_samples)
            if latency_list:
                sorted_latency = sorted(latency_list)
                avg_latency = sum(latency_list) / len(latency_list)
                max_latency = max(latency_list)
                min_latency = min(latency_list)
                p95_latency = self._percentile(sorted_latency, 95)
                p99_latency = self._percentile(sorted_latency, 99)
            else:
                avg_latency = max_latency = min_latency = p95_latency = p99_latency = 0.0
            
            # Calculate throughput
            minute_ago = now - 60
            hour_ago = now - 3600
            requests_minute = sum(1 for t in self._request_timestamps if t > minute_ago)
            requests_hour = sum(1 for t in self._request_timestamps if t > hour_ago)
            
            requests_per_second = requests_minute / 60
            requests_per_minute = requests_minute
            requests_per_hour = requests_hour
            
            # Calculate order metrics
            total_orders = len(self._order_timestamps)
            order_errors = len(self._order_error_timestamps)
            successful_orders = total_orders - order_errors
            order_error_rate = (order_errors / max(total_orders, 1)) * 100
            
            # Calculate account metrics
            balance = 0.0
            equity = 0.0
            buying_power = 0.0
            if self._account_snapshots:
                _, balance, equity, buying_power = self._account_snapshots[-1]
            
            # Calculate connection uptime
            uptime = now - self._start_time
            
            return BrokerMetricsSnapshot(
                broker_id=self.broker_id,
                broker_name=self.broker_name,
                is_connected=True,  # Should be set by caller
                connection_uptime=uptime,
                reconnect_count=self.get_counter("connection.reconnect"),
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=total_errors,
                error_rate=error_rate,
                avg_latency_ms=avg_latency,
                max_latency_ms=max_latency,
                min_latency_ms=min_latency,
                p95_latency_ms=p95_latency,
                p99_latency_ms=p99_latency,
                requests_per_second=requests_per_second,
                requests_per_minute=requests_per_minute,
                requests_per_hour=requests_per_hour,
                total_orders=total_orders,
                successful_orders=successful_orders,
                failed_orders=order_errors,
                order_error_rate=order_error_rate,
                balance=balance,
                equity=equity,
                buying_power=buying_power,
                open_positions=int(self.get_gauge("account.open_positions")),
                open_orders=int(self.get_gauge("account.open_orders")),
                health_status=health_status,
                last_health_check=last_health_check,
                custom=self._get_custom_metrics(),
            )
    
    def _get_custom_metrics(self) -> Dict[str, Any]:
        """Get custom metrics from gauges and counters."""
        custom = {}
        
        for key, value in self._gauges.items():
            if not key.startswith("account.") and not key.startswith("connection."):
                custom[key] = value
        
        for key, value in self._counters.items():
            if not key.startswith("account.") and not key.startswith("connection."):
                custom[key] = value
        
        return custom
    
    # ========================================================================
    # TIME SERIES
    # ========================================================================
    
    def get_time_series(
        self,
        metric_name: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        interval: int = 60,
        aggregation: MetricAggregation = MetricAggregation.AVG,
    ) -> List[Tuple[float, float]]:
        """
        Get time series data for a metric.
        
        Args:
            metric_name: Metric name
            start_time: Start timestamp
            end_time: End timestamp
            interval: Interval in seconds
            aggregation: Aggregation method
            
        Returns:
            List[Tuple[float, float]]: Time series data
        """
        with self._lock:
            if metric_name not in self._time_series:
                return []
            
            data = self._time_series[metric_name]
            
            # Filter by time range
            if start_time:
                data = [(t, v) for t, v in data if t >= start_time]
            if end_time:
                data = [(t, v) for t, v in data if t <= end_time]
            
            if not data:
                return []
            
            # Aggregate by interval
            if interval > 0:
                aggregated = []
                current_time = data[0][0]
                current_values = []
                
                for timestamp, value in data:
                    if timestamp - current_time >= interval:
                        if current_values:
                            agg_value = self._aggregate_values(current_values, aggregation)
                            aggregated.append((current_time, agg_value))
                        current_time = timestamp
                        current_values = []
                    current_values.append(value)
                
                if current_values:
                    agg_value = self._aggregate_values(current_values, aggregation)
                    aggregated.append((current_time, agg_value))
                
                return aggregated
            
            return data
    
    def record_time_series(self, metric_name: str, value: float, timestamp: Optional[float] = None) -> None:
        """
        Record a time series data point.
        
        Args:
            metric_name: Metric name
            value: Value to record
            timestamp: Optional timestamp (defaults to now)
        """
        with self._lock:
            ts = timestamp or time.time()
            self._time_series[metric_name].append((ts, value))
            
            # Trim if too many
            if len(self._time_series[metric_name]) > self.max_samples:
                self._time_series[metric_name] = self._time_series[metric_name][-self.max_samples:]
    
    def _aggregate_values(self, values: List[float], aggregation: MetricAggregation) -> float:
        """
        Aggregate values using the specified method.
        
        Args:
            values: List of values
            aggregation: Aggregation method
            
        Returns:
            float: Aggregated value
        """
        if not values:
            return 0.0
        
        if aggregation == MetricAggregation.SUM:
            return sum(values)
        elif aggregation == MetricAggregation.AVG:
            return sum(values) / len(values)
        elif aggregation == MetricAggregation.MIN:
            return min(values)
        elif aggregation == MetricAggregation.MAX:
            return max(values)
        elif aggregation == MetricAggregation.COUNT:
            return len(values)
        elif aggregation == MetricAggregation.LAST:
            return values[-1]
        elif aggregation == MetricAggregation.PERCENTILE_50:
            return self._percentile(sorted(values), 50)
        elif aggregation == MetricAggregation.PERCENTILE_95:
            return self._percentile(sorted(values), 95)
        elif aggregation == MetricAggregation.PERCENTILE_99:
            return self._percentile(sorted(values), 99)
        elif aggregation == MetricAggregation.PERCENTILE_999:
            return self._percentile(sorted(values), 99.9)
        else:
            return sum(values) / len(values)
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def cleanup(self) -> None:
        """Clean up old metrics."""
        with self._lock:
            now = time.time()
            retention_seconds = self.retention_days * 24 * 3600
            
            # Clean up time series
            for metric_name in list(self._time_series.keys()):
                data = self._time_series[metric_name]
                data = [(t, v) for t, v in data if now - t <= retention_seconds]
                if data:
                    self._time_series[metric_name] = data
                else:
                    del self._time_series[metric_name]
            
            # Clean up account snapshots
            self._account_snapshots = [
                snap for snap in self._account_snapshots
                if now - snap[0] <= retention_seconds
            ]
            
            self._last_cleanup = now
    
    # ========================================================================
    # EXPORT
    # ========================================================================
    
    def export_metrics(self, format: str = "json") -> Dict[str, Any]:
        """
        Export all metrics.
        
        Args:
            format: Export format (json, prometheus)
            
        Returns:
            Dict: Exported metrics
        """
        with self._lock:
            if format == "prometheus":
                return self._export_prometheus()
            else:
                return self._export_json()
    
    def _export_json(self) -> Dict[str, Any]:
        """Export metrics as JSON."""
        return {
            "broker_id": self.broker_id,
            "broker_name": self.broker_name,
            "counters": self._counters,
            "gauges": self._gauges,
            "histograms": {
                name: {
                    "count": len(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "avg": sum(values) / len(values) if values else 0,
                }
                for name, values in self._histograms.items()
            },
            "timers": {
                name: {
                    "count": len(values),
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                    "avg": sum(values) / len(values) if values else 0,
                }
                for name, values in self._timers.items()
            },
            "request_stats": {
                "total": len(self._request_timestamps),
                "errors": len(self._error_timestamps),
                "error_rate": (len(self._error_timestamps) / max(len(self._request_timestamps), 1)) * 100,
            },
            "latency_stats": {
                "avg": sum(self._latency_samples) / len(self._latency_samples) if self._latency_samples else 0,
                "min": min(self._latency_samples) if self._latency_samples else 0,
                "max": max(self._latency_samples) if self._latency_samples else 0,
            },
            "order_stats": {
                "total": len(self._order_timestamps),
                "errors": len(self._order_error_timestamps),
                "error_rate": (len(self._order_error_timestamps) / max(len(self._order_timestamps), 1)) * 100,
            },
        }
    
    def _export_prometheus(self) -> Dict[str, Any]:
        """Export metrics in Prometheus format."""
        metrics = {}
        
        # Counters
        for name, value in self._counters.items():
            metrics[f"broker_{name}_total"] = value
        
        # Gauges
        for name, value in self._gauges.items():
            metrics[f"broker_{name}"] = value
        
        # Request stats
        metrics["broker_requests_total"] = len(self._request_timestamps)
        metrics["broker_requests_errors_total"] = len(self._error_timestamps)
        metrics["broker_requests_error_rate"] = (
            len(self._error_timestamps) / max(len(self._request_timestamps), 1) * 100
        )
        
        # Latency stats
        if self._latency_samples:
            metrics["broker_latency_avg_ms"] = sum(self._latency_samples) / len(self._latency_samples)
            metrics["broker_latency_min_ms"] = min(self._latency_samples)
            metrics["broker_latency_max_ms"] = max(self._latency_samples)
        
        # Order stats
        metrics["broker_orders_total"] = len(self._order_timestamps)
        metrics["broker_orders_errors_total"] = len(self._order_error_timestamps)
        
        return metrics
    
    # ========================================================================
    # RESET
    # ========================================================================
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            self._rates.clear()
            self._time_series.clear()
            self._request_timestamps.clear()
            self._error_timestamps.clear()
            self._order_timestamps.clear()
            self._order_error_timestamps.clear()
            self._latency_samples.clear()
            self._account_snapshots.clear()
            self._start_time = time.time()
            self.logger.info(f"Reset metrics for broker {self.broker_id}")


# ============================================================================
# METRICS MANAGER
# ============================================================================

class BrokerMetricsManager:
    """
    Manages metrics collection for multiple brokers.
    
    Features:
    - Centralized metrics management
    - Aggregated reporting across brokers
    - Global metric queries
    """
    
    def __init__(self):
        """Initialize the metrics manager."""
        self._collectors: Dict[str, BrokerMetricsCollector] = {}
        self._lock = Lock()
        self.logger = logger
    
    def get_collector(
        self,
        broker_id: str,
        broker_name: str = "unknown",
    ) -> BrokerMetricsCollector:
        """
        Get or create a metrics collector for a broker.
        
        Args:
            broker_id: Broker identifier
            broker_name: Broker name
            
        Returns:
            BrokerMetricsCollector: Metrics collector
        """
        with self._lock:
            if broker_id not in self._collectors:
                self._collectors[broker_id] = BrokerMetricsCollector(
                    broker_id=broker_id,
                    broker_name=broker_name,
                )
            return self._collectors[broker_id]
    
    def remove_collector(self, broker_id: str) -> bool:
        """
        Remove a metrics collector.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            bool: True if collector was removed
        """
        with self._lock:
            if broker_id in self._collectors:
                del self._collectors[broker_id]
                return True
            return False
    
    def get_all_snapshots(self) -> Dict[str, BrokerMetricsSnapshot]:
        """
        Get snapshots for all brokers.
        
        Returns:
            Dict[str, BrokerMetricsSnapshot]: Snapshots by broker ID
        """
        with self._lock:
            return {
                broker_id: collector.get_snapshot()
                for broker_id, collector in self._collectors.items()
            }
    
    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated metrics across all brokers.
        
        Returns:
            Dict: Aggregated metrics
        """
        with self._lock:
            if not self._collectors:
                return {}
            
            total_requests = 0
            total_errors = 0
            total_latency = 0
            latency_count = 0
            total_orders = 0
            order_errors = 0
            
            for collector in self._collectors.values():
                total_requests += len(collector._request_timestamps)
                total_errors += len(collector._error_timestamps)
                total_orders += len(collector._order_timestamps)
                order_errors += len(collector._order_error_timestamps)
                
                latency_samples = list(collector._latency_samples)
                if latency_samples:
                    total_latency += sum(latency_samples)
                    latency_count += len(latency_samples)
            
            return {
                "total_brokers": len(self._collectors),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate": (total_errors / max(total_requests, 1)) * 100,
                "avg_latency_ms": total_latency / max(latency_count, 1),
                "total_orders": total_orders,
                "order_error_rate": (order_errors / max(total_orders, 1)) * 100,
                "active_brokers": sum(1 for c in self._collectors.values() if c.get_gauge("connection.connected")),
            }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "MetricType",
    "MetricAggregation",
    
    # Models
    "MetricValue",
    "MetricAggregationResult",
    "BrokerMetricsSnapshot",
    
    # Classes
    "BrokerMetricsCollector",
    "BrokerMetricsManager",
]
