"""
Swing Bot Metric Collector
============================

This module provides metric collection capabilities for the Swing Bot trading system.
"""

import time
import psutil
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import logging

from trading.bots.swing_bot.core import Trade, Position, Portfolio


@dataclass
class Metric:
    """Metric data structure."""
    name: str
    value: Union[int, float, str]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


@dataclass
class MetricSummary:
    """Metric summary statistics."""
    count: int = 0
    sum: float = 0.0
    mean: float = 0.0
    min: float = float('inf')
    max: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    std: float = 0.0


class MetricCollector:
    """
    Collect and manage trading metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the metric collector.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.historical: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.latest: Dict[str, Metric] = {}
        self._lock = threading.RLock()
        self._running = False
        self._collector_thread: Optional[threading.Thread] = None
        self._collectors: List[Callable] = []
        self._subscriptions: List[Callable] = []
        
        # Initialize default collectors
        self._register_default_collectors()
        
        if self.config.get('enabled', True):
            self.start()
    
    def _register_default_collectors(self) -> None:
        """Register default metric collectors."""
        self.register_collector(self._collect_system_metrics)
        self.register_collector(self._collect_trading_metrics)
    
    def start(self) -> None:
        """Start the metric collection."""
        if self._running:
            return
        
        self._running = True
        self._collector_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collector_thread.start()
        logging.info("Metric collector started")
    
    def stop(self) -> None:
        """Stop the metric collection."""
        self._running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=5)
        logging.info("Metric collector stopped")
    
    def register_collector(self, collector: Callable) -> None:
        """
        Register a metric collector function.
        
        Args:
            collector: Collector function
        """
        self._collectors.append(collector)
    
    def subscribe(self, callback: Callable) -> None:
        """
        Subscribe to metric updates.
        
        Args:
            callback: Callback function
        """
        self._subscriptions.append(callback)
    
    def _collect_loop(self) -> None:
        """Main collection loop."""
        interval = self.config.get('collection_interval', 5)
        
        while self._running:
            try:
                for collector in self._collectors:
                    try:
                        collector()
                    except Exception as e:
                        logging.error(f"Collector error: {e}")
                
                # Notify subscribers
                if self._subscriptions:
                    self._notify_subscribers()
                
                time.sleep(interval)
            except Exception as e:
                logging.error(f"Collection loop error: {e}")
    
    def _notify_subscribers(self) -> None:
        """Notify subscribers of new metrics."""
        for callback in self._subscriptions:
            try:
                callback(self.get_latest_metrics())
            except Exception as e:
                logging.error(f"Subscription callback error: {e}")
    
    def _collect_system_metrics(self) -> None:
        """Collect system metrics."""
        # CPU
        self.record('cpu_usage', psutil.cpu_percent(interval=0.1), unit='%')
        
        # Memory
        mem = psutil.virtual_memory()
        self.record('memory_usage', mem.percent, unit='%')
        self.record('memory_used', mem.used / (1024 * 1024), unit='MB')
        
        # Disk
        disk = psutil.disk_usage('/')
        self.record('disk_usage', disk.percent, unit='%')
        self.record('disk_used', disk.used / (1024 * 1024 * 1024), unit='GB')
        
        # Network
        net = psutil.net_io_counters()
        self.record('network_sent', net.bytes_sent / (1024 * 1024), unit='MB')
        self.record('network_recv', net.bytes_recv / (1024 * 1024), unit='MB')
        
        # Process
        process = psutil.Process()
        self.record('process_cpu', process.cpu_percent(interval=0.1), unit='%')
        self.record('process_memory', process.memory_percent(), unit='%')
        self.record('process_threads', process.num_threads(), unit='count')
        self.record('process_files', process.num_fds() if hasattr(process, 'num_fds') else 0, unit='count')
    
    def _collect_trading_metrics(self) -> None:
        """Collect trading metrics."""
        # This should be extended by the trading system
        pass
    
    def record(
        self,
        name: str,
        value: Union[int, float, str],
        tags: Optional[Dict[str, str]] = None,
        unit: str = ""
    ) -> None:
        """
        Record a metric.
        
        Args:
            name: Metric name
            value: Metric value
            tags: Additional tags
            unit: Unit of measurement
        """
        with self._lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {},
                unit=unit
            )
            
            self.metrics[name].append(metric)
            self.historical[name].append(value)
            self.latest[name] = metric
            
            # Trim metrics to prevent memory issues
            max_size = self.config.get('max_metrics_per_name', 10000)
            if len(self.metrics[name]) > max_size:
                self.metrics[name] = self.metrics[name][-max_size:]
    
    def get_metric(self, name: str, limit: int = 100) -> List[Metric]:
        """
        Get metrics for a specific name.
        
        Args:
            name: Metric name
            limit: Maximum number of metrics to return
        
        Returns:
            List of metrics
        """
        with self._lock:
            metrics = self.metrics.get(name, [])
            return metrics[-limit:] if limit > 0 else metrics
    
    def get_latest_metrics(self) -> Dict[str, Any]:
        """
        Get the latest values for all metrics.
        
        Returns:
            Dictionary of latest metric values
        """
        with self._lock:
            return {
                name: {
                    'value': metric.value,
                    'timestamp': metric.timestamp.isoformat(),
                    'unit': metric.unit,
                    'tags': metric.tags
                }
                for name, metric in self.latest.items()
            }
    
    def get_summary(self, name: str, window: Optional[int] = None) -> Optional[MetricSummary]:
        """
        Get summary statistics for a metric.
        
        Args:
            name: Metric name
            window: Number of recent values to consider
        
        Returns:
            Metric summary or None
        """
        with self._lock:
            metrics = self.metrics.get(name, [])
            if not metrics:
                return None
            
            values = [m.value for m in metrics if isinstance(m.value, (int, float))]
            if window:
                values = values[-window:]
            
            if not values:
                return None
            
            summary = MetricSummary()
            summary.count = len(values)
            summary.sum = sum(values)
            summary.mean = summary.sum / summary.count
            summary.min = min(values)
            summary.max = max(values)
            
            # Calculate percentiles
            sorted_values = sorted(values)
            summary.p50 = sorted_values[int(summary.count * 0.5)]
            summary.p95 = sorted_values[int(summary.count * 0.95)]
            summary.p99 = sorted_values[int(summary.count * 0.99)]
            
            # Calculate standard deviation
            variance = sum((v - summary.mean) ** 2 for v in values) / summary.count
            summary.std = variance ** 0.5
            
            return summary
    
    def get_history(self, name: str, limit: int = 100) -> List[Any]:
        """
        Get historical values for a metric.
        
        Args:
            name: Metric name
            limit: Maximum number of values to return
        
        Returns:
            List of historical values
        """
        with self._lock:
            history = self.historical.get(name, deque())
            return list(history)[-limit:]
    
    def get_all_summaries(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summaries for all metrics.
        
        Returns:
            Dictionary of metric summaries
        """
        result = {}
        with self._lock:
            for name in self.metrics:
                summary = self.get_summary(name)
                if summary:
                    result[name] = {
                        'count': summary.count,
                        'mean': summary.mean,
                        'min': summary.min,
                        'max': summary.max,
                        'p50': summary.p50,
                        'p95': summary.p95,
                        'p99': summary.p99,
                        'std': summary.std
                    }
        return result
    
    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self.metrics.clear()
            self.historical.clear()
            self.latest.clear()
    
    def export(self) -> Dict[str, Any]:
        """
        Export all metrics as a dictionary.
        
        Returns:
            Dictionary of all metrics
        """
        with self._lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'metrics': {
                    name: [
                        {
                            'value': m.value,
                            'timestamp': m.timestamp.isoformat(),
                            'tags': m.tags,
                            'unit': m.unit
                        }
                        for m in metrics
                    ]
                    for name, metrics in self.metrics.items()
                },
                'summaries': self.get_all_summaries()
            }


class AsyncMetricCollector(MetricCollector):
    """Asynchronous version of the metric collector."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._collector_task: Optional[asyncio.Task] = None
    
    async def start_async(self) -> None:
        """Start the async metric collection."""
        if self._running:
            return
        
        self._running = True
        self._collector_task = asyncio.create_task(self._async_collect_loop())
        logging.info("Async metric collector started")
    
    async def stop_async(self) -> None:
        """Stop the async metric collection."""
        self._running = False
        if self._collector_task:
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass
        logging.info("Async metric collector stopped")
    
    async def _async_collect_loop(self) -> None:
        """Async collection loop."""
        interval = self.config.get('collection_interval', 5)
        
        while self._running:
            try:
                for collector in self._collectors:
                    try:
                        if asyncio.iscoroutinefunction(collector):
                            await collector()
                        else:
                            collector()
                    except Exception as e:
                        logging.error(f"Async collector error: {e}")
                
                # Notify subscribers
                if self._subscriptions:
                    await self._async_notify_subscribers()
                
                await asyncio.sleep(interval)
            except Exception as e:
                logging.error(f"Async collection loop error: {e}")
    
    async def _async_notify_subscribers(self) -> None:
        """Notify subscribers asynchronously."""
        latest = self.get_latest_metrics()
        for callback in self._subscriptions:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(latest)
                else:
                    callback(latest)
            except Exception as e:
                logging.error(f"Async subscription callback error: {e}")
    
    async def record_async(
        self,
        name: str,
        value: Union[int, float, str],
        tags: Optional[Dict[str, str]] = None,
        unit: str = ""
    ) -> None:
        """Record a metric asynchronously."""
        await asyncio.to_thread(self.record, name, value, tags, unit)


# Global metric collector instance
_metric_collector: Optional[MetricCollector] = None


def get_metric_collector() -> MetricCollector:
    """Get the global metric collector instance."""
    global _metric_collector
    if _metric_collector is None:
        _metric_collector = MetricCollector()
    return _metric_collector


def record_metric(
    name: str,
    value: Union[int, float, str],
    tags: Optional[Dict[str, str]] = None,
    unit: str = ""
) -> None:
    """
    Record a metric using the global collector.
    
    Args:
        name: Metric name
        value: Metric value
        tags: Additional tags
        unit: Unit of measurement
    """
    get_metric_collector().record(name, value, tags, unit)


__all__ = [
    'Metric',
    'MetricSummary',
    'MetricCollector',
    'AsyncMetricCollector',
    'get_metric_collector',
    'record_metric'
]
