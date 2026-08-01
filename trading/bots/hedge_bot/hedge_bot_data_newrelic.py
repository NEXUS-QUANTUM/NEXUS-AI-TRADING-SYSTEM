"""
NEXUS AI TRADING SYSTEM
Hedge Bot Data NewRelic Integration

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: trading/bots/hedge_bot/hedge_bot_data_newrelic.py
Description: NewRelic integration for hedge bot monitoring, observability,
             performance tracking, and real-time analytics with full
             production capabilities.
"""

import asyncio
import json
import logging
import time
import socket
import platform
import os
import psutil
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Set, Callable, Awaitable
from collections import defaultdict, deque
import threading
import queue

import aiohttp
import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async, RetryConfig

logger = get_logger(__name__)


class MetricType(str, Enum):
    """Types of metrics sent to NewRelic."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"
    DISTRIBUTION = "distribution"
    RATE = "rate"
    PERCENTILE = "percentile"
    COUNT = "count"
    VALUE = "value"
    EVENT = "event"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class ServiceStatus(str, Enum):
    """Service status."""
    RUNNING = "running"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


@dataclass
class NewRelicConfig:
    """Configuration for NewRelic integration."""
    api_key: str
    account_id: str
    region: str = "us"
    app_name: str = "NexusTradingIA"
    environment: str = "production"
    api_url: str = "https://api.newrelic.com/graphql"
    metrics_url: str = "https://metric-api.newrelic.com/v1"
    events_url: str = "https://insights-collector.newrelic.com/v1/accounts"
    batch_size: int = 100
    flush_interval: int = 60
    max_queue_size: int = 10000
    enable_distributed_tracing: bool = True
    enable_apm: bool = True
    enable_infrastructure: bool = True
    enable_browser_monitoring: bool = True
    enable_logging: bool = True
    custom_attributes: Dict[str, str] = field(default_factory=dict)
    sampling_rate: float = 1.0
    compression_enabled: bool = True
    retry_attempts: int = 3
    timeout: int = 30


@dataclass
class MetricData:
    """Metric data structure."""
    name: str
    value: float
    type: MetricType
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)
    unit: str = ""
    description: str = ""


@dataclass
class SpanData:
    """Distributed trace span data."""
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: Optional[Dict[str, Any]] = None


@dataclass
class EventData:
    """Event data structure."""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)
    severity: AlertSeverity = AlertSeverity.INFO


@dataclass
class LogData:
    """Log data structure."""
    message: str
    level: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)
    source: str = "hedge_bot"


@dataclass
class ServiceMetric:
    """Service health metric."""
    service_name: str
    status: ServiceStatus
    uptime_seconds: float
    memory_usage_mb: float
    cpu_usage_percent: float
    active_connections: int
    request_rate: float
    error_rate: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceMetric:
    """Performance metric."""
    name: str
    value: float
    percentile: Optional[float] = None
    count: Optional[int] = None
    sum: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


class NewRelicIntegration:
    """
    Full NewRelic integration for hedge bot monitoring.
    
    Features:
    - Custom metrics ingestion
    - Distributed tracing
    - Event tracking
    - Log integration
    - APM monitoring
    - Infrastructure monitoring
    - Service health monitoring
    - Performance analysis
    - Alert management
    - Real-time dashboards
    - Custom queries
    - NRQL support
    - Batch processing
    - Asynchronous operations
    - Error tracking
    - Transaction tracing
    - External service monitoring
    - Database monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize NewRelic integration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._newrelic_config = NewRelicConfig(**config.get("newrelic", {}))
        
        # HTTP session
        self._http_session: Optional[aiohttp.ClientSession] = None
        
        # Metrics queue
        self._metric_queue: asyncio.Queue = asyncio.Queue(maxsize=self._newrelic_config.max_queue_size)
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=self._newrelic_config.max_queue_size)
        self._span_queue: asyncio.Queue = asyncio.Queue(maxsize=self._newrelic_config.max_queue_size)
        self._log_queue: asyncio.Queue = asyncio.Queue(maxsize=self._newrelic_config.max_queue_size)
        
        # Batch buffers
        self._metric_batch: List[MetricData] = []
        self._event_batch: List[EventData] = []
        self._span_batch: List[SpanData] = []
        self._log_batch: List[LogData] = []
        
        # Flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # Service metrics
        self._service_metrics: Dict[str, ServiceMetric] = {}
        self._performance_metrics: Dict[str, List[PerformanceMetric]] = defaultdict(list)
        
        # Tracing
        self._trace_cache: Dict[str, SpanData] = {}
        self._active_spans: Dict[str, SpanData] = {}
        
        # Statistics
        self._stats = {
            "metrics_sent": 0,
            "events_sent": 0,
            "spans_sent": 0,
            "logs_sent": 0,
            "errors": 0,
            "batches_sent": 0,
            "last_flush": None,
        }
        
        # System info
        self._hostname = socket.gethostname()
        self._pid = os.getpid()
        self._start_time = time.time()
        
        # Thread safety
        self._lock = asyncio.Lock()
        
        # NRQL query cache
        self._query_cache: Dict[str, Any] = {}
        
        logger.info(f"NewRelicIntegration initialized for {self._newrelic_config.app_name}")
    
    # ========================================================================
    # INITIALIZATION AND STARTUP
    # ========================================================================
    
    async def start(self) -> None:
        """Start the NewRelic integration."""
        if self._is_running:
            logger.warning("NewRelic integration already running")
            return
        
        self._is_running = True
        
        # Create HTTP session
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._newrelic_config.timeout),
            headers=self._get_headers(),
        )
        
        # Start flush task
        self._flush_task = asyncio.create_task(self._flush_loop())
        
        # Start system metrics collection
        asyncio.create_task(self._collect_system_metrics())
        
        logger.info("NewRelic integration started")
    
    async def stop(self) -> None:
        """Stop the NewRelic integration."""
        logger.info("Stopping NewRelic integration...")
        
        self._is_running = False
        
        # Cancel flush task
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining data
        await self._flush_all()
        
        # Close HTTP session
        if self._http_session:
            await self._http_session.close()
        
        logger.info("NewRelic integration stopped")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for NewRelic API."""
        headers = {
            "Api-Key": self._newrelic_config.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self._newrelic_config.compression_enabled:
            headers["Accept-Encoding"] = "gzip, deflate"
            headers["Content-Encoding"] = "gzip"
        
        return headers
    
    # ========================================================================
    # METRIC COLLECTION
    # ========================================================================
    
    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        attributes: Optional[Dict[str, Any]] = None,
        unit: str = "",
        description: str = "",
    ) -> None:
        """
        Record a custom metric.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            attributes: Additional attributes
            unit: Unit of measurement
            description: Metric description
        """
        if not self._is_running:
            logger.warning("NewRelic integration not running")
            return
        
        metric = MetricData(
            name=name,
            value=value,
            type=metric_type,
            timestamp=datetime.now(),
            attributes=attributes or {},
            unit=unit,
            description=description,
        )
        
        # Apply sampling
        if self._newrelic_config.sampling_rate < 1.0:
            if np.random.random() > self._newrelic_config.sampling_rate:
                return
        
        try:
            await self._metric_queue.put(metric)
        except asyncio.QueueFull:
            logger.warning(f"Metric queue full, dropping metric: {name}")
    
    async def record_counter(
        self,
        name: str,
        value: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a counter metric."""
        await self.record_metric(name, value, MetricType.COUNTER, attributes)
    
    async def record_gauge(
        self,
        name: str,
        value: float,
        attributes: Optional[Dict[str, Any]] = None,
        unit: str = "",
    ) -> None:
        """Record a gauge metric."""
        await self.record_metric(name, value, MetricType.GAUGE, attributes, unit)
    
    async def record_histogram(
        self,
        name: str,
        value: float,
        attributes: Optional[Dict[str, Any]] = None,
        unit: str = "",
    ) -> None:
        """Record a histogram metric."""
        await self.record_metric(name, value, MetricType.HISTOGRAM, attributes, unit)
    
    async def record_timer(
        self,
        name: str,
        duration_ms: float,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a timer metric."""
        await self.record_metric(name, duration_ms, MetricType.TIMER, attributes, "ms")
    
    # ========================================================================
    # DISTRIBUTED TRACING
    # ========================================================================
    
    def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a distributed trace span.
        
        Args:
            name: Span name
            parent_id: Parent span ID
            attributes: Span attributes
            
        Returns:
            Span ID
        """
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        
        span = SpanData(
            trace_id=trace_id,
            span_id=span_id,
            parent_id=parent_id,
            name=name,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=0.0,
            attributes=attributes or {},
        )
        
        self._active_spans[span_id] = span
        self._trace_cache[trace_id] = span
        
        return span_id
    
    def end_span(self, span_id: str, status: str = "ok", error: Optional[Dict[str, Any]] = None) -> None:
        """
        End a distributed trace span.
        
        Args:
            span_id: Span ID
            status: Status of the span
            error: Error information
        """
        if span_id not in self._active_spans:
            logger.warning(f"Span {span_id} not found")
            return
        
        span = self._active_spans[span_id]
        span.end_time = datetime.now()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        
        if error:
            span.error = error
            span.status = "error"
        
        # Add to queue for processing
        if self._is_running:
            asyncio.create_task(self._enqueue_span(span))
        
        # Remove from active spans
        del self._active_spans[span_id]
    
    async def _enqueue_span(self, span: SpanData) -> None:
        """Enqueue a span for processing."""
        try:
            await self._span_queue.put(span)
        except asyncio.QueueFull:
            logger.warning(f"Span queue full, dropping span: {span.name}")
    
    @contextmanager
    def trace(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Context manager for distributed tracing.
        
        Args:
            name: Span name
            attributes: Span attributes
            
        Yields:
            Span ID
        """
        span_id = self.start_span(name, None, attributes)
        try:
            yield span_id
        except Exception as e:
            self.end_span(span_id, "error", {"type": type(e).__name__, "message": str(e)})
            raise
        else:
            self.end_span(span_id)
    
    # ========================================================================
    # EVENT TRACKING
    # ========================================================================
    
    async def record_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        severity: AlertSeverity = AlertSeverity.INFO,
    ) -> None:
        """
        Record a custom event.
        
        Args:
            name: Event name
            attributes: Event attributes
            severity: Event severity
        """
        if not self._is_running:
            logger.warning("NewRelic integration not running")
            return
        
        event = EventData(
            name=name,
            timestamp=datetime.now(),
            attributes=attributes or {},
            severity=severity,
        )
        
        try:
            await self._event_queue.put(event)
        except asyncio.QueueFull:
            logger.warning(f"Event queue full, dropping event: {name}")
    
    async def record_alert(
        self,
        name: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.WARNING,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an alert event."""
        attrs = attributes or {}
        attrs["message"] = message
        await self.record_event(f"alert_{name}", attrs, severity)
    
    # ========================================================================
    # LOG INTEGRATION
    # ========================================================================
    
    async def record_log(
        self,
        message: str,
        level: str = "info",
        attributes: Optional[Dict[str, Any]] = None,
        source: str = "hedge_bot",
    ) -> None:
        """
        Record a log entry.
        
        Args:
            message: Log message
            level: Log level
            attributes: Log attributes
            source: Log source
        """
        if not self._is_running:
            logger.warning("NewRelic integration not running")
            return
        
        log = LogData(
            message=message,
            level=level,
            timestamp=datetime.now(),
            attributes=attributes or {},
            source=source,
        )
        
        try:
            await self._log_queue.put(log)
        except asyncio.QueueFull:
            logger.warning(f"Log queue full, dropping log: {message[:50]}...")
    
    # ========================================================================
    # SERVICE HEALTH MONITORING
    # ========================================================================
    
    async def update_service_health(
        self,
        service_name: str,
        status: ServiceStatus,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update service health metrics.
        
        Args:
            service_name: Service name
            status: Service status
            metrics: Additional metrics
        """
        uptime = time.time() - self._start_time
        
        # Get system metrics
        try:
            memory = psutil.Process(self._pid).memory_info()
            memory_mb = memory.rss / 1024 / 1024
            cpu_percent = psutil.Process(self._pid).cpu_percent()
        except:
            memory_mb = 0
            cpu_percent = 0
        
        service_metric = ServiceMetric(
            service_name=service_name,
            status=status,
            uptime_seconds=uptime,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
            active_connections=metrics.get("connections", 0) if metrics else 0,
            request_rate=metrics.get("request_rate", 0) if metrics else 0,
            error_rate=metrics.get("error_rate", 0) if metrics else 0,
            latency_p50=metrics.get("latency_p50", 0) if metrics else 0,
            latency_p95=metrics.get("latency_p95", 0) if metrics else 0,
            latency_p99=metrics.get("latency_p99", 0) if metrics else 0,
        )
        
        self._service_metrics[service_name] = service_metric
        
        # Record as metrics
        await self.record_gauge(
            f"service.{service_name}.memory_usage",
            service_metric.memory_usage_mb,
            {"service": service_name},
            "MB"
        )
        
        await self.record_gauge(
            f"service.{service_name}.cpu_usage",
            service_metric.cpu_usage_percent,
            {"service": service_name},
            "%"
        )
        
        await self.record_gauge(
            f"service.{service_name}.active_connections",
            service_metric.active_connections,
            {"service": service_name},
            "connections"
        )
        
        await self.record_gauge(
            f"service.{service_name}.request_rate",
            service_metric.request_rate,
            {"service": service_name},
            "req/s"
        )
        
        await self.record_gauge(
            f"service.{service_name}.error_rate",
            service_metric.error_rate,
            {"service": service_name},
            "errors/s"
        )
        
        await self.record_gauge(
            f"service.{service_name}.latency_p95",
            service_metric.latency_p95,
            {"service": service_name},
            "ms"
        )
    
    async def _collect_system_metrics(self) -> None:
        """Collect system metrics periodically."""
        while self._is_running:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                await self.record_gauge("system.cpu.usage", cpu_percent, {}, "%")
                
                # Memory usage
                memory = psutil.virtual_memory()
                await self.record_gauge("system.memory.usage", memory.percent, {}, "%")
                await self.record_gauge("system.memory.used", memory.used / 1024 / 1024 / 1024, {}, "GB")
                await self.record_gauge("system.memory.available", memory.available / 1024 / 1024 / 1024, {}, "GB")
                
                # Disk usage
                disk = psutil.disk_usage('/')
                await self.record_gauge("system.disk.usage", disk.percent, {}, "%")
                await self.record_gauge("system.disk.used", disk.used / 1024 / 1024 / 1024, {}, "GB")
                await self.record_gauge("system.disk.free", disk.free / 1024 / 1024 / 1024, {}, "GB")
                
                # Network
                net_io = psutil.net_io_counters()
                await self.record_gauge("system.network.bytes_sent", net_io.bytes_sent / 1024 / 1024, {}, "MB")
                await self.record_gauge("system.network.bytes_recv", net_io.bytes_recv / 1024 / 1024, {}, "MB")
                
                # Process metrics
                process = psutil.Process(self._pid)
                await self.record_gauge("system.process.cpu", process.cpu_percent(), {}, "%")
                await self.record_gauge("system.process.memory", process.memory_percent(), {}, "%")
                await self.record_gauge("system.process.threads", process.num_threads(), {}, "threads")
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
            
            await asyncio.sleep(60)  # Collect every minute
    
    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================
    
    async def record_performance(
        self,
        name: str,
        value: float,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            name=name,
            value=value,
            attributes=attributes or {},
        )
        
        self._performance_metrics[name].append(metric)
        
        # Keep last 1000 metrics
        if len(self._performance_metrics[name]) > 1000:
            self._performance_metrics[name] = self._performance_metrics[name][-1000:]
        
        # Record as metric
        await self.record_gauge(f"performance.{name}", value, attributes)
    
    def get_performance_summary(self, name: str) -> Dict[str, float]:
        """Get performance summary for a metric."""
        if name not in self._performance_metrics:
            return {}
        
        values = [m.value for m in self._performance_metrics[name]]
        if not values:
            return {}
        
        return {
            "min": min(values),
            "max": max(values),
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "p50": np.percentile(values, 50),
            "p90": np.percentile(values, 90),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
            "count": len(values),
        }
    
    # ========================================================================
    # NRQL QUERIES
    # ========================================================================
    
    async def query_nrql(self, query: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a NRQL query.
        
        Args:
            query: NRQL query string
            timeout: Query timeout
            
        Returns:
            Query results
        """
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        
        url = f"{self._newrelic_config.api_url}/v1/accounts/{self._newrelic_config.account_id}/query"
        
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        
        data = {
            "nrql": query,
            "timeout": timeout,
        }
        
        try:
            async with self._http_session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    self._query_cache[hash(query)] = {
                        "result": result,
                        "timestamp": datetime.now(),
                    }
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"NRQL query failed: {response.status} - {error_text}")
                    return {}
        except Exception as e:
            logger.error(f"Error executing NRQL query: {e}")
            return {}
    
    async def get_metric_data(
        self,
        metric_name: str,
        timeframe: str = "1 hour",
        aggregation: str = "average",
    ) -> List[Dict[str, Any]]:
        """
        Get metric data via NRQL.
        
        Args:
            metric_name: Name of the metric
            timeframe: Time range
            aggregation: Aggregation method
            
        Returns:
            Metric data points
        """
        query = f"""
            SELECT {aggregation}({metric_name}) 
            FROM Metric 
            TIMESERIES 
            SINCE {timeframe} 
            LIMIT MAX
        """
        
        result = await self.query_nrql(query)
        
        if "data" in result and result["data"]:
            return result["data"]
        
        return []
    
    async def get_event_data(
        self,
        event_type: str,
        timeframe: str = "1 hour",
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get event data via NRQL.
        
        Args:
            event_type: Event type
            timeframe: Time range
            filters: Event filters
            
        Returns:
            Event data
        """
        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join([f"{k} = '{v}'" for k, v in filters.items()])
        
        query = f"""
            SELECT * 
            FROM {event_type} 
            {where_clause}
            SINCE {timeframe} 
            LIMIT MAX
        """
        
        result = await self.query_nrql(query)
        
        if "data" in result and result["data"]:
            return result["data"]
        
        return []
    
    # ========================================================================
    # BATCH PROCESSING AND FLUSHING
    # ========================================================================
    
    async def _flush_loop(self) -> None:
        """Background loop to flush data."""
        while self._is_running:
            try:
                await self._flush_batch()
                await asyncio.sleep(self._newrelic_config.flush_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")
                await asyncio.sleep(5)
    
    async def _flush_batch(self) -> None:
        """Flush a batch of data."""
        async with self._lock:
            # Flush metrics
            metrics = await self._drain_queue(self._metric_queue, self._newrelic_config.batch_size)
            if metrics:
                await self._send_metrics(metrics)
            
            # Flush events
            events = await self._drain_queue(self._event_queue, self._newrelic_config.batch_size)
            if events:
                await self._send_events(events)
            
            # Flush spans
            spans = await self._drain_queue(self._span_queue, self._newrelic_config.batch_size)
            if spans:
                await self._send_spans(spans)
            
            # Flush logs
            logs = await self._drain_queue(self._log_queue, self._newrelic_config.batch_size)
            if logs:
                await self._send_logs(logs)
    
    async def _flush_all(self) -> None:
        """Flush all remaining data."""
        async with self._lock:
            # Flush all metrics
            metrics = []
            while not self._metric_queue.empty():
                try:
                    metric = self._metric_queue.get_nowait()
                    metrics.append(metric)
                except asyncio.QueueEmpty:
                    break
            if metrics:
                await self._send_metrics(metrics)
            
            # Flush all events
            events = []
            while not self._event_queue.empty():
                try:
                    event = self._event_queue.get_nowait()
                    events.append(event)
                except asyncio.QueueEmpty:
                    break
            if events:
                await self._send_events(events)
            
            # Flush all spans
            spans = []
            while not self._span_queue.empty():
                try:
                    span = self._span_queue.get_nowait()
                    spans.append(span)
                except asyncio.QueueEmpty:
                    break
            if spans:
                await self._send_spans(spans)
            
            # Flush all logs
            logs = []
            while not self._log_queue.empty():
                try:
                    log = self._log_queue.get_nowait()
                    logs.append(log)
                except asyncio.QueueEmpty:
                    break
            if logs:
                await self._send_logs(logs)
    
    async def _drain_queue(self, queue: asyncio.Queue, max_items: int) -> List[Any]:
        """Drain items from a queue."""
        items = []
        for _ in range(max_items):
            try:
                item = queue.get_nowait()
                items.append(item)
            except asyncio.QueueEmpty:
                break
        return items
    
    # ========================================================================
    # DATA SENDING
    # ========================================================================
    
    async def _send_metrics(self, metrics: List[MetricData]) -> None:
        """Send metrics to NewRelic."""
        if not metrics:
            return
        
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        
        url = f"{self._newrelic_config.metrics_url}/accounts/{self._newrelic_config.account_id}/metrics"
        
        # Format metrics for NewRelic
        formatted_metrics = []
        for metric in metrics:
            formatted = {
                "name": metric.name,
                "value": metric.value,
                "type": metric.type.value,
                "timestamp": int(metric.timestamp.timestamp() * 1000),
                "attributes": {
                    "app": self._newrelic_config.app_name,
                    "environment": self._newrelic_config.environment,
                    "host": self._hostname,
                    **self._newrelic_config.custom_attributes,
                    **metric.attributes,
                },
            }
            if metric.unit:
                formatted["unit"] = metric.unit
            if metric.description:
                formatted["description"] = metric.description
            formatted_metrics.append(formatted)
        
        # Send in batches
        for i in range(0, len(formatted_metrics), 100):
            batch = formatted_metrics[i:i+100]
            data = json.dumps({"metrics": batch})
            
            try:
                async with self._http_session.post(url, data=data) as response:
                    if response.status in [200, 202]:
                        self._stats["metrics_sent"] += len(batch)
                        self._stats["batches_sent"] += 1
                        self._stats["last_flush"] = datetime.now()
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to send metrics: {response.status} - {error_text}")
                        self._stats["errors"] += 1
            except Exception as e:
                logger.error(f"Error sending metrics: {e}")
                self._stats["errors"] += 1
    
    async def _send_events(self, events: List[EventData]) -> None:
        """Send events to NewRelic."""
        if not events:
            return
        
        if not self._http_session:
            self._http_session = aiohttp.ClientSession()
        
        url = f"{self._newrelic_config.events_url}/{self._newrelic_config.account_id}/events"
        
        # Format events
        formatted_events = []
        for event in events:
            formatted = {
                "eventType": event.name,
                "timestamp": int(event.timestamp.timestamp() * 1000),
                "severity": event.severity.value,
                "app": self._newrelic_config.app_name,
                "environment": self._newrelic_config.environment,
                "host": self._hostname,
                **self._newrelic_config.custom_attributes,
                **event.attributes,
            }
            formatted_events.append(formatted)
        
        data = json.dumps(formatted_events)
        
        try:
            async with self._http_session.post(url, data=data) as response:
                if response.status in [200, 202]:
                    self._stats["events_sent"] += len(formatted_events)
                    self._stats["batches_sent"] += 1
                    self._stats["last_flush"] = datetime.now()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send events: {response.status} - {error_text}")
                    self._stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error sending events: {e}")
            self._stats["errors"] += 1
    
    async def _send_spans(self, spans: List[SpanData]) -> None:
        """Send spans for distributed tracing."""
        if not spans:
            return
        
        # Format spans for NewRelic
        formatted_spans = []
        for span in spans:
            formatted = {
                "traceId": span.trace_id,
                "spanId": span.span_id,
                "parentId": span.parent_id,
                "name": span.name,
                "startTime": int(span.start_time.timestamp() * 1000),
                "endTime": int(span.end_time.timestamp() * 1000),
                "duration": span.duration_ms,
                "status": span.status,
                "attributes": {
                    "app": self._newrelic_config.app_name,
                    "environment": self._newrelic_config.environment,
                    "host": self._hostname,
                    **self._newrelic_config.custom_attributes,
                    **span.attributes,
                },
            }
            if span.error:
                formatted["error"] = span.error
            formatted_spans.append(formatted)
        
        # Send to NewRelic via API
        # Note: NewRelic uses a different endpoint for spans
        url = f"{self._newrelic_config.metrics_url}/accounts/{self._newrelic_config.account_id}/trace"
        
        data = json.dumps({"spans": formatted_spans})
        
        try:
            async with self._http_session.post(url, data=data) as response:
                if response.status in [200, 202]:
                    self._stats["spans_sent"] += len(formatted_spans)
                    self._stats["batches_sent"] += 1
                    self._stats["last_flush"] = datetime.now()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send spans: {response.status} - {error_text}")
                    self._stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error sending spans: {e}")
            self._stats["errors"] += 1
    
    async def _send_logs(self, logs: List[LogData]) -> None:
        """Send logs to NewRelic."""
        if not logs:
            return
        
        # Format logs
        formatted_logs = []
        for log in logs:
            formatted = {
                "message": log.message,
                "level": log.level,
                "timestamp": int(log.timestamp.timestamp() * 1000),
                "source": log.source,
                "app": self._newrelic_config.app_name,
                "environment": self._newrelic_config.environment,
                "host": self._hostname,
                **self._newrelic_config.custom_attributes,
                **log.attributes,
            }
            formatted_logs.append(formatted)
        
        # Send to NewRelic
        url = f"{self._newrelic_config.metrics_url}/accounts/{self._newrelic_config.account_id}/logs"
        
        data = json.dumps({"logs": formatted_logs})
        
        try:
            async with self._http_session.post(url, data=data) as response:
                if response.status in [200, 202]:
                    self._stats["logs_sent"] += len(formatted_logs)
                    self._stats["batches_sent"] += 1
                    self._stats["last_flush"] = datetime.now()
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send logs: {response.status} - {error_text}")
                    self._stats["errors"] += 1
        except Exception as e:
            logger.error(f"Error sending logs: {e}")
            self._stats["errors"] += 1
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        return {
            **self._stats,
            "is_running": self._is_running,
            "queue_sizes": {
                "metrics": self._metric_queue.qsize(),
                "events": self._event_queue.qsize(),
                "spans": self._span_queue.qsize(),
                "logs": self._log_queue.qsize(),
            },
            "active_spans": len(self._active_spans),
            "service_metrics": len(self._service_metrics),
            "performance_metrics": {k: len(v) for k, v in self._performance_metrics.items()},
            "uptime_seconds": time.time() - self._start_time,
        }
    
    def get_service_health(self, service_name: str) -> Optional[ServiceMetric]:
        """Get health metrics for a service."""
        return self._service_metrics.get(service_name)
    
    def get_all_service_health(self) -> Dict[str, ServiceMetric]:
        """Get health metrics for all services."""
        return self._service_metrics
    
    async def record_transaction(
        self,
        name: str,
        func: Callable,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Record a transaction with timing.
        
        Args:
            name: Transaction name
            func: Async function to execute
            attributes: Transaction attributes
            
        Returns:
            Function result
        """
        start_time = time.time()
        span_id = self.start_span(name, None, attributes)
        
        try:
            result = await func()
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timer(f"transaction.{name}", duration_ms, attributes)
            self.end_span(span_id)
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await self.record_timer(f"transaction.{name}", duration_ms, attributes)
            self.end_span(span_id, "error", {"type": type(e).__name__, "message": str(e)})
            raise
    
    async def record_request(
        self,
        method: str,
        url: str,
        status_code: int,
        duration_ms: float,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record an external request.
        
        Args:
            method: HTTP method
            url: Request URL
            status_code: Response status code
            duration_ms: Request duration
            attributes: Additional attributes
        """
        attrs = attributes or {}
        attrs["method"] = method
        attrs["url"] = url
        attrs["status_code"] = status_code
        
        # Record request metric
        await self.record_timer(f"request.{method}.{status_code}", duration_ms, attrs)
        
        # Record request counter
        await self.record_counter(f"request.{method}.total", 1, attrs)
        
        if status_code >= 400:
            await self.record_counter("request.errors", 1, attrs)
        
        if status_code >= 500:
            await self.record_alert(
                "request_error",
                f"Request failed: {method} {url} - {status_code}",
                AlertSeverity.HIGH,
                attrs,
            )
    
    async def record_database_query(
        self,
        query_name: str,
        duration_ms: float,
        rows_affected: int = 0,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a database query.
        
        Args:
            query_name: Query name
            duration_ms: Query duration
            rows_affected: Number of rows affected
            attributes: Additional attributes
        """
        attrs = attributes or {}
        attrs["rows_affected"] = rows_affected
        
        await self.record_timer(f"database.{query_name}", duration_ms, attrs)
        await self.record_gauge(f"database.{query_name}.rows", rows_affected, attrs)
    
    # ========================================================================
    # CLEANUP
    # ========================================================================
    
    def clear_cache(self) -> None:
        """Clear query cache."""
        self._query_cache.clear()
        logger.info("Query cache cleared")
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = {
            "metrics_sent": 0,
            "events_sent": 0,
            "spans_sent": 0,
            "logs_sent": 0,
            "errors": 0,
            "batches_sent": 0,
            "last_flush": None,
        }
        logger.info("Statistics reset")


# ========================================================================
# CONTEXT MANAGER
# ========================================================================

from contextlib import contextmanager


@contextmanager
def newrelic_trace(
    integration: NewRelicIntegration,
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Context manager for NewRelic tracing.
    
    Args:
        integration: NewRelicIntegration instance
        name: Trace name
        attributes: Trace attributes
        
    Yields:
        Span ID
    """
    if not integration._is_running:
        yield None
        return
    
    span_id = integration.start_span(name, None, attributes)
    try:
        yield span_id
    except Exception as e:
        integration.end_span(span_id, "error", {"type": type(e).__name__, "message": str(e)})
        raise
    else:
        integration.end_span(span_id)


async def newrelic_transaction(
    integration: NewRelicIntegration,
    name: str,
    func: Callable,
    attributes: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Decorator-like function for NewRelic transaction.
    
    Args:
        integration: NewRelicIntegration instance
        name: Transaction name
        func: Async function to execute
        attributes: Transaction attributes
        
    Returns:
        Function result
    """
    return await integration.record_transaction(name, func, attributes)


# ========================================================================
# FACTORY FUNCTION
# ========================================================================

def create_newrelic_integration(
    config: Dict[str, Any],
) -> NewRelicIntegration:
    """Factory function to create a NewRelicIntegration instance."""
    return NewRelicIntegration(config)
