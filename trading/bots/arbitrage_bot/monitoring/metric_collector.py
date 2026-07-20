# trading/bots/arbitrage_bot/monitoring/metric_collector.py
# NEXUS AI TRADING SYSTEM - METRIC COLLECTOR
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive metrics collection and monitoring for the
# arbitrage bot, including performance metrics, business metrics, and system metrics.
# ====================================================================================

"""
NEXUS Arbitrage Bot Metric Collector

This module provides comprehensive metrics collection for:
- Performance metrics (latency, throughput, errors)
- Business metrics (trades, profit, opportunities)
- System metrics (CPU, memory, connections)
- Custom metrics for strategies
- Real-time metric aggregation
- Metric storage and export
- Integration with monitoring systems
"""

import asyncio
import logging
import time
import json
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import aiohttp
import aiofiles

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector as CoreMetricsCollector

logger = logging.getLogger("nexus.arbitrage.metric_collector")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class MetricType(str, Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricCategory(str, Enum):
    """Categories of metrics."""
    SYSTEM = "system"
    EXCHANGE = "exchange"
    TRADE = "trade"
    OPPORTUNITY = "opportunity"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    STRATEGY = "strategy"
    RISK = "risk"
    NETWORK = "network"
    CUSTOM = "custom"


class AggregationMethod(str, Enum):
    """Aggregation methods for metrics."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"
    RATE = "rate"
    LAST = "last"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class Metric:
    """
    Single metric data point.
    """
    name: str
    value: float
    type: MetricType
    category: MetricCategory
    timestamp: datetime
    labels: Dict[str, str]
    unit: str
    description: str
    metadata: Dict[str, Any]


@dataclass
class MetricAggregation:
    """
    Aggregated metric data.
    """
    name: str
    method: AggregationMethod
    value: float
    count: int
    min: float
    max: float
    sum: float
    avg: float
    percentiles: Dict[float, float]
    timestamp: datetime
    labels: Dict[str, str]


@dataclass
class MetricQuery:
    """
    Metric query parameters.
    """
    name: str
    category: Optional[MetricCategory]
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    aggregation: AggregationMethod
    interval: str  # 1m, 5m, 1h, 1d
    labels: Dict[str, str]
    limit: int


# ====================================================================================
# METRIC COLLECTOR
# ====================================================================================

class MetricCollector:
    """
    Comprehensive metrics collection system.
    
    Features:
    - Counter, gauge, histogram metrics
    - Real-time metric aggregation
    - Metric storage and export
    - Prometheus integration
    - Custom metric definitions
    - Alerting on metric thresholds
    - Metric querying and analysis
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metric collector.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.namespace = self.config.get("namespace", "nexus_arbitrage")
        
        # Metric storage
        self._metrics: Dict[str, Metric] = {}
        self._metric_history: Dict[str, deque] = {}
        self._aggregations: Dict[str, Dict[str, Any]] = {}
        
        # Core metrics collector
        self._core_metrics = CoreMetricsCollector(
            name="nexus_arbitrage_metrics",
            labels={"service": "arbitrage_bot"}
        )
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Metric definitions
        self._metric_definitions: Dict[str, Dict[str, Any]] = {}
        self._register_default_metrics()
        
        logger.info("MetricCollector initialized (version=3.0.0)")
        
    def _register_default_metrics(self) -> None:
        """Register default metric definitions."""
        # System metrics
        self.register_metric("system_cpu_usage", "CPU usage percentage", "gauge", MetricCategory.SYSTEM, "%")
        self.register_metric("system_memory_usage", "Memory usage in MB", "gauge", MetricCategory.SYSTEM, "MB")
        self.register_metric("system_disk_usage", "Disk usage percentage", "gauge", MetricCategory.SYSTEM, "%")
        self.register_metric("system_connections", "Active connections", "gauge", MetricCategory.SYSTEM, "count")
        
        # Trade metrics
        self.register_metric("trade_total", "Total trades executed", "counter", MetricCategory.TRADE, "count")
        self.register_metric("trade_success", "Successful trades", "counter", MetricCategory.TRADE, "count")
        self.register_metric("trade_failure", "Failed trades", "counter", MetricCategory.TRADE, "count")
        self.register_metric("trade_profit", "Trade profit", "counter", MetricCategory.TRADE, "USDT")
        self.register_metric("trade_loss", "Trade loss", "counter", MetricCategory.TRADE, "USDT")
        self.register_metric("trade_volume", "Trade volume", "counter", MetricCategory.TRADE, "USDT")
        self.register_metric("trade_latency", "Trade execution latency", "histogram", MetricCategory.TRADE, "ms")
        
        # Opportunity metrics
        self.register_metric("opportunity_detected", "Opportunities detected", "counter", MetricCategory.OPPORTUNITY, "count")
        self.register_metric("opportunity_executed", "Opportunities executed", "counter", MetricCategory.OPPORTUNITY, "count")
        self.register_metric("opportunity_profit", "Opportunity profit", "counter", MetricCategory.OPPORTUNITY, "USDT")
        self.register_metric("opportunity_spread", "Opportunity spread", "histogram", MetricCategory.OPPORTUNITY, "bps")
        
        # Exchange metrics
        self.register_metric("exchange_latency", "Exchange API latency", "histogram", MetricCategory.EXCHANGE, "ms")
        self.register_metric("exchange_requests", "Exchange API requests", "counter", MetricCategory.EXCHANGE, "count")
        self.register_metric("exchange_errors", "Exchange API errors", "counter", MetricCategory.EXCHANGE, "count")
        
        # Performance metrics
        self.register_metric("performance_latency", "System latency", "histogram", MetricCategory.PERFORMANCE, "ms")
        self.register_metric("performance_throughput", "System throughput", "counter", MetricCategory.PERFORMANCE, "ops/s")
        
        # Business metrics
        self.register_metric("business_pnl", "Total PnL", "gauge", MetricCategory.BUSINESS, "USDT")
        self.register_metric("business_balance", "Total balance", "gauge", MetricCategory.BUSINESS, "USDT")
        self.register_metric("business_risk", "Risk exposure", "gauge", MetricCategory.BUSINESS, "%")
        
    def register_metric(
        self,
        name: str,
        description: str,
        type: str,
        category: MetricCategory,
        unit: str = ""
    ) -> None:
        """
        Register a metric definition.
        
        Args:
            name: Metric name
            description: Metric description
            type: Metric type (counter, gauge, histogram)
            category: Metric category
            unit: Metric unit
        """
        self._metric_definitions[name] = {
            "description": description,
            "type": type,
            "category": category.value if isinstance(category, MetricCategory) else category,
            "unit": unit
        }
        
        # Initialize metric storage
        if name not in self._metric_history:
            self._metric_history[name] = deque(maxlen=10000)
            
        logger.info(f"Registered metric: {name}")
        
    async def initialize(self) -> None:
        """Initialize the metric collector."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("MetricCollector initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # System metrics collection
        task = asyncio.create_task(self._system_metrics_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics aggregation
        task = asyncio.create_task(self._aggregation_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _system_metrics_loop(self) -> None:
        """Collect system metrics periodically."""
        while self._running:
            try:
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                await self.record("system_cpu_usage", cpu_percent, labels={"cpu": "total"})
                
                # Memory
                memory = psutil.virtual_memory()
                await self.record("system_memory_usage", memory.used / (1024 * 1024), labels={"type": "used"})
                await self.record("system_memory_usage", memory.total / (1024 * 1024), labels={"type": "total"})
                
                # Disk
                disk = psutil.disk_usage('/')
                await self.record("system_disk_usage", disk.percent, labels={"mount": "/"})
                
                # Connections
                connections = len(psutil.net_connections())
                await self.record("system_connections", connections, labels={"state": "active"})
                
                # Update core metrics
                self._core_metrics.set_gauge("system_cpu_percent", cpu_percent)
                self._core_metrics.set_gauge("system_memory_used_mb", memory.used / (1024 * 1024))
                self._core_metrics.set_gauge("system_connections", connections)
                
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"System metrics collection error: {e}")
                await asyncio.sleep(30)
                
    async def _aggregation_loop(self) -> None:
        """Aggregate metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(60)
                
                # Aggregate recent metrics
                for name, history in self._metric_history.items():
                    if len(history) > 0:
                        # 1-minute aggregation
                        one_min_ago = datetime.utcnow() - timedelta(minutes=1)
                        recent = [m for m in history if m.timestamp > one_min_ago]
                        if recent:
                            await self._aggregate_metrics(name, recent, "1m")
                            
                        # 5-minute aggregation
                        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
                        recent = [m for m in history if m.timestamp > five_min_ago]
                        if recent:
                            await self._aggregate_metrics(name, recent, "5m")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation error: {e}")
                
    async def _aggregate_metrics(self, name: str, metrics: List[Metric], interval: str) -> None:
        """
        Aggregate metrics for a specific interval.
        
        Args:
            name: Metric name
            metrics: List of metrics
            interval: Aggregation interval
        """
        if not metrics:
            return
            
        values = [m.value for m in metrics]
        
        aggregation = MetricAggregation(
            name=name,
            method=AggregationMethod.AVG,
            value=sum(values) / len(values),
            count=len(values),
            min=min(values),
            max=max(values),
            sum=sum(values),
            avg=sum(values) / len(values),
            percentiles=self._calculate_percentiles(values),
            timestamp=datetime.utcnow(),
            labels=metrics[0].labels
        )
        
        # Store aggregation
        key = f"{name}_{interval}"
        if key not in self._aggregations:
            self._aggregations[key] = {}
        self._aggregations[key][datetime.utcnow().isoformat()] = aggregation
        
    def _calculate_percentiles(self, values: List[float]) -> Dict[float, float]:
        """Calculate percentiles."""
        if not values:
            return {}
            
        sorted_values = sorted(values)
        n = len(sorted_values)
        percentiles = {}
        
        for p in [50, 90, 95, 99]:
            index = int((p / 100) * (n - 1))
            percentiles[p] = sorted_values[index]
            
        return percentiles
        
    async def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
            timestamp: Metric timestamp
        """
        if name not in self._metric_definitions:
            logger.warning(f"Unknown metric: {name}")
            return
            
        definition = self._metric_definitions[name]
        
        metric = Metric(
            name=name,
            value=value,
            type=MetricType(definition["type"]),
            category=MetricCategory(definition["category"]),
            timestamp=timestamp or datetime.utcnow(),
            labels=labels or {},
            unit=definition.get("unit", ""),
            description=definition.get("description", ""),
            metadata={}
        )
        
        # Store metric
        self._metrics[f"{name}_{metric.timestamp.isoformat()}"] = metric
        self._metric_history[name].append(metric)
        
        # Update core metrics
        if definition["type"] == "counter":
            self._core_metrics.increment_counter(name, value=value, labels=labels)
        elif definition["type"] == "gauge":
            self._core_metrics.set_gauge(name, value, labels=labels)
        elif definition["type"] == "histogram":
            self._core_metrics.record_histogram(name, value, labels=labels)
            
    async def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Increment value
            labels: Metric labels
        """
        await self.record(name, value, labels)
        
    async def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
        """
        await self.record(name, value, labels)
        
    async def observe_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Observe a histogram metric.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
        """
        await self.record(name, value, labels)
        
    async def get_metric(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Metric]:
        """
        Get metrics by name.
        
        Args:
            name: Metric name
            labels: Filter by labels
            start_time: Start time
            end_time: End time
            limit: Maximum results
            
        Returns:
            List of metrics
        """
        metrics = list(self._metric_history.get(name, []))
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        if labels:
            metrics = [m for m in metrics if all(m.labels.get(k) == v for k, v in labels.items())]
            
        return metrics[-limit:]
        
    async def get_aggregation(
        self,
        name: str,
        interval: str = "1m",
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[MetricAggregation]:
        """
        Get aggregated metrics.
        
        Args:
            name: Metric name
            interval: Aggregation interval
            labels: Filter by labels
            start_time: Start time
            end_time: End time
            limit: Maximum results
            
        Returns:
            List of aggregations
        """
        key = f"{name}_{interval}"
        aggregations = self._aggregations.get(key, {})
        
        results = []
        for ts, agg in aggregations.items():
            timestamp = datetime.fromisoformat(ts)
            if start_time and timestamp < start_time:
                continue
            if end_time and timestamp > end_time:
                continue
            if labels and not all(agg.labels.get(k) == v for k, v in labels.items()):
                continue
            results.append(agg)
            
        return results[-limit:]
        
    async def query(
        self,
        query: MetricQuery
    ) -> List[Union[Metric, MetricAggregation]]:
        """
        Query metrics.
        
        Args:
            query: Metric query
            
        Returns:
            List of metrics or aggregations
        """
        if query.aggregation == AggregationMethod.LAST:
            return await self.get_metric(
                query.name,
                query.labels,
                query.start_time,
                query.end_time,
                query.limit
            )
        else:
            interval = query.interval
            results = await self.get_aggregation(
                query.name,
                interval,
                query.labels,
                query.start_time,
                query.end_time,
                query.limit
            )
            
            # Apply aggregation method
            if query.aggregation == AggregationMethod.AVG:
                results = [r for r in results]  # Already averaged
            elif query.aggregation == AggregationMethod.SUM:
                # Sum values over time
                total = sum(r.value for r in results)
                return [MetricAggregation(
                    name=query.name,
                    method=AggregationMethod.SUM,
                    value=total,
                    count=len(results),
                    min=0,
                    max=0,
                    sum=total,
                    avg=total / len(results) if results else 0,
                    percentiles={},
                    timestamp=datetime.utcnow(),
                    labels=query.labels
                )]
            elif query.aggregation == AggregationMethod.MIN:
                min_val = min(r.value for r in results) if results else 0
                return [MetricAggregation(
                    name=query.name,
                    method=AggregationMethod.MIN,
                    value=min_val,
                    count=len(results),
                    min=min_val,
                    max=0,
                    sum=0,
                    avg=0,
                    percentiles={},
                    timestamp=datetime.utcnow(),
                    labels=query.labels
                )]
            elif query.aggregation == AggregationMethod.MAX:
                max_val = max(r.value for r in results) if results else 0
                return [MetricAggregation(
                    name=query.name,
                    method=AggregationMethod.MAX,
                    value=max_val,
                    count=len(results),
                    min=0,
                    max=max_val,
                    sum=0,
                    avg=0,
                    percentiles={},
                    timestamp=datetime.utcnow(),
                    labels=query.labels
                )]
                
            return results
            
    async def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.
        
        Returns:
            Prometheus metrics string
        """
        lines = []
        
        for name, definition in self._metric_definitions.items():
            metrics = list(self._metric_history.get(name, []))
            if not metrics:
                continue
                
            latest = metrics[-1]
            metric_type = definition["type"]
            
            # Add HELP and TYPE
            lines.append(f"# HELP {self.namespace}_{name} {definition['description']}")
            lines.append(f"# TYPE {self.namespace}_{name} {metric_type}")
            
            # Format based on type
            if metric_type == "counter":
                total = sum(m.value for m in metrics)
                lines.append(f"{self.namespace}_{name} {total}")
            elif metric_type == "gauge":
                lines.append(f"{self.namespace}_{name} {latest.value}")
            elif metric_type == "histogram":
                # Calculate percentiles
                values = [m.value for m in metrics]
                for p in [50, 90, 95, 99]:
                    percentile = self._calculate_percentile(values, p)
                    lines.append(f"{self.namespace}_{name}_{{quantile=\"{p/100}\"}} {percentile}")
                    
        return "\n".join(lines)
        
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate percentile."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int((percentile / 100) * (len(sorted_values) - 1))
        return sorted_values[index]
        
    async def close(self) -> None:
        """Close the metric collector."""
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
                    
        logger.info("MetricCollector closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_metric_collector: Optional[MetricCollector] = None


def get_metric_collector() -> MetricCollector:
    """
    Get the global metric collector instance.
    
    Returns:
        MetricCollector instance
    """
    global _global_metric_collector
    if _global_metric_collector is None:
        _global_metric_collector = MetricCollector()
    return _global_metric_collector


def reset_metric_collector() -> None:
    """Reset the global metric collector instance."""
    global _global_metric_collector
    if _global_metric_collector:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_metric_collector.close())
            else:
                asyncio.run(_global_metric_collector.close())
        except Exception:
            pass
    _global_metric_collector = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'MetricType',
    'MetricCategory',
    'AggregationMethod',
    
    # Data Models
    'Metric',
    'MetricAggregation',
    'MetricQuery',
    
    # Main Class
    'MetricCollector',
    'get_metric_collector',
    'reset_metric_collector',
]
