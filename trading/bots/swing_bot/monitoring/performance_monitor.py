"""
Swing Bot Performance Monitor
===============================

This module provides performance monitoring capabilities for the Swing Bot trading system.
"""

import time
import psutil
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from collections import deque
from dataclasses import dataclass, field
import logging
import json

from trading.bots.swing_bot.utils.validators import validate_data


@dataclass
class PerformanceMetric:
    """Performance metric data."""
    name: str
    value: float
    timestamp: datetime
    unit: str = "ms"
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceStats:
    """Performance statistics."""
    count: int = 0
    sum: float = 0.0
    mean: float = 0.0
    min: float = float('inf')
    max: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    std: float = 0.0


class PerformanceMonitor:
    """
    Monitor performance metrics for the trading system.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the performance monitor.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.metrics: Dict[str, List[PerformanceMetric]] = {}
        self.window_size = self.config.get('window_size', 1000)
        self.historical_window = self.config.get('historical_window', 3600)  # 1 hour
        self.enabled = self.config.get('enabled', True)
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._alert_callbacks: List[Callable] = []
        self._metrics_history: Dict[str, deque] = {}
        
        # Initialize system metrics collection
        if self.enabled:
            self._start_monitoring()
    
    def _start_monitoring(self) -> None:
        """Start the monitoring thread."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._collect_system_metrics()
                self._check_thresholds()
                time.sleep(self.config.get('monitoring_interval', 5))
            except Exception as e:
                logging.error(f"Performance monitor error: {e}")
    
    def _collect_system_metrics(self) -> None:
        """Collect system performance metrics."""
        # CPU usage
        cpu_usage = psutil.cpu_percent(interval=0.1)
        self.record_metric('cpu_usage', cpu_usage, unit='%')
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.record_metric('memory_usage', memory.percent, unit='%')
        self.record_metric('memory_used', memory.used / (1024 * 1024), unit='MB')
        
        # Disk usage
        disk = psutil.disk_usage('/')
        self.record_metric('disk_usage', disk.percent, unit='%')
        self.record_metric('disk_used', disk.used / (1024 * 1024 * 1024), unit='GB')
        
        # Network usage
        net = psutil.net_io_counters()
        self.record_metric('network_sent', net.bytes_sent / (1024 * 1024), unit='MB')
        self.record_metric('network_recv', net.bytes_recv / (1024 * 1024), unit='MB')
        
        # Process-specific metrics
        process = psutil.Process()
        self.record_metric('process_cpu', process.cpu_percent(interval=0.1), unit='%')
        self.record_metric('process_memory', process.memory_percent(), unit='%')
        self.record_metric('process_threads', process.num_threads(), unit='count')
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "ms",
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record a performance metric.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            tags: Additional tags
        """
        if not self.enabled:
            return
        
        with self._lock:
            metric = PerformanceMetric(
                name=name,
                value=value,
                timestamp=datetime.now(),
                unit=unit,
                tags=tags or {}
            )
            
            if name not in self.metrics:
                self.metrics[name] = []
            
            self.metrics[name].append(metric)
            
            # Trim metrics to window size
            if len(self.metrics[name]) > self.window_size:
                self.metrics[name] = self.metrics[name][-self.window_size:]
            
            # Update history
            if name not in self._metrics_history:
                self._metrics_history[name] = deque(maxlen=self.window_size)
            self._metrics_history[name].append(value)
    
    def record_time(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
        """
        Record a timing metric.
        
        Args:
            name: Metric name
            duration: Duration in seconds
            tags: Additional tags
        """
        self.record_metric(f"{name}_duration", duration * 1000, unit="ms", tags=tags)
    
    def get_metric(self, name: str) -> Optional[List[PerformanceMetric]]:
        """
        Get metrics for a specific name.
        
        Args:
            name: Metric name
        
        Returns:
            List of metrics or None
        """
        with self._lock:
            return self.metrics.get(name)
    
    def get_latest(self, name: str) -> Optional[float]:
        """
        Get the latest value for a metric.
        
        Args:
            name: Metric name
        
        Returns:
            Latest value or None
        """
        with self._lock:
            metrics = self.metrics.get(name)
            if metrics:
                return metrics[-1].value
            return None
    
    def get_stats(self, name: str, window: Optional[int] = None) -> Optional[PerformanceStats]:
        """
        Get statistics for a metric.
        
        Args:
            name: Metric name
            window: Number of recent values to consider
        
        Returns:
            Performance statistics or None
        """
        with self._lock:
            metrics = self.metrics.get(name)
            if not metrics:
                return None
            
            values = [m.value for m in metrics]
            if window:
                values = values[-window:]
            
            if not values:
                return None
            
            stats = PerformanceStats()
            stats.count = len(values)
            stats.sum = sum(values)
            stats.mean = stats.sum / stats.count
            stats.min = min(values)
            stats.max = max(values)
            
            # Calculate percentiles
            sorted_values = sorted(values)
            stats.p50 = sorted_values[int(stats.count * 0.5)]
            stats.p95 = sorted_values[int(stats.count * 0.95)]
            stats.p99 = sorted_values[int(stats.count * 0.99)]
            
            # Calculate standard deviation
            variance = sum((v - stats.mean) ** 2 for v in values) / stats.count
            stats.std = variance ** 0.5
            
            return stats
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all metrics with current values and statistics.
        
        Returns:
            Dictionary of metrics
        """
        result = {}
        with self._lock:
            for name in self.metrics:
                stats = self.get_stats(name)
                latest = self.get_latest(name)
                if stats:
                    result[name] = {
                        'latest': latest,
                        'mean': stats.mean,
                        'min': stats.min,
                        'max': stats.max,
                        'p50': stats.p50,
                        'p95': stats.p95,
                        'p99': stats.p99,
                        'count': stats.count
                    }
        return result
    
    def get_metric_history(self, name: str, limit: int = 100) -> List[float]:
        """
        Get historical values for a metric.
        
        Args:
            name: Metric name
            limit: Maximum number of values to return
        
        Returns:
            List of historical values
        """
        with self._lock:
            history = self._metrics_history.get(name)
            if history:
                return list(history)[-limit:]
            return []
    
    def set_threshold(
        self,
        metric: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        alert_callback: Optional[Callable] = None
    ) -> None:
        """
        Set a threshold for a metric.
        
        Args:
            metric: Metric name
            min_value: Minimum value
            max_value: Maximum value
            alert_callback: Callback function for alerts
        """
        if 'thresholds' not in self.config:
            self.config['thresholds'] = {}
        
        self.config['thresholds'][metric] = {
            'min': min_value,
            'max': max_value,
            'callback': alert_callback
        }
    
    def _check_thresholds(self) -> None:
        """Check all metrics against thresholds."""
        thresholds = self.config.get('thresholds', {})
        
        for metric_name, threshold in thresholds.items():
            latest = self.get_latest(metric_name)
            if latest is None:
                continue
            
            min_val = threshold.get('min')
            max_val = threshold.get('max')
            
            if min_val is not None and latest < min_val:
                self._trigger_alert(metric_name, latest, 'below_min', min_val)
            
            if max_val is not None and latest > max_val:
                self._trigger_alert(metric_name, latest, 'above_max', max_val)
    
    def _trigger_alert(
        self,
        metric: str,
        value: float,
        condition: str,
        threshold: float
    ) -> None:
        """
        Trigger an alert for a metric.
        
        Args:
            metric: Metric name
            value: Current value
            condition: Alert condition
            threshold: Threshold value
        """
        alert_data = {
            'metric': metric,
            'value': value,
            'condition': condition,
            'threshold': threshold,
            'timestamp': datetime.now().isoformat()
        }
        
        # Call registered callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logging.error(f"Alert callback error: {e}")
        
        # Call threshold-specific callback
        threshold_config = self.config.get('thresholds', {}).get(metric, {})
        callback = threshold_config.get('callback')
        if callback:
            try:
                callback(alert_data)
            except Exception as e:
                logging.error(f"Threshold callback error: {e}")
        
        logging.warning(f"Performance alert: {json.dumps(alert_data)}")
    
    def register_alert_callback(self, callback: Callable) -> None:
        """
        Register a callback for all alerts.
        
        Args:
            callback: Callback function
        """
        self._alert_callbacks.append(callback)
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get overall system health assessment.
        
        Returns:
            Health assessment
        """
        health = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }
        
        # Check CPU
        cpu_usage = self.get_latest('cpu_usage')
        if cpu_usage:
            health['metrics']['cpu_usage'] = cpu_usage
            if cpu_usage > 80:
                health['status'] = 'warning'
            if cpu_usage > 95:
                health['status'] = 'critical'
        
        # Check memory
        memory_usage = self.get_latest('memory_usage')
        if memory_usage:
            health['metrics']['memory_usage'] = memory_usage
            if memory_usage > 80:
                health['status'] = 'warning'
            if memory_usage > 95:
                health['status'] = 'critical'
        
        # Check disk
        disk_usage = self.get_latest('disk_usage')
        if disk_usage:
            health['metrics']['disk_usage'] = disk_usage
            if disk_usage > 80:
                health['status'] = 'warning'
            if disk_usage > 95:
                health['status'] = 'critical'
        
        return health
    
    def start_timer(self) -> Callable:
        """
        Create a timer for measuring operation duration.
        
        Returns:
            Timer function
        """
        start_time = time.perf_counter()
        
        def stop_timer(operation_name: str, tags: Optional[Dict[str, str]] = None) -> float:
            duration = time.perf_counter() - start_time
            self.record_time(operation_name, duration, tags)
            return duration
        
        return stop_timer
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self.metrics.clear()
            self._metrics_history.clear()
    
    def stop(self) -> None:
        """Stop the performance monitor."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)


class AsyncPerformanceMonitor(PerformanceMonitor):
    """
    Asynchronous version of the performance monitor.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the async monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._async_monitor_loop())
    
    async def _async_monitor_loop(self) -> None:
        """Async monitoring loop."""
        while self._running:
            try:
                await asyncio.to_thread(self._collect_system_metrics)
                await self._async_check_thresholds()
                await asyncio.sleep(self.config.get('monitoring_interval', 5))
            except Exception as e:
                logging.error(f"Async performance monitor error: {e}")
    
    async def _async_check_thresholds(self) -> None:
        """Async threshold checking."""
        await asyncio.to_thread(self._check_thresholds)
    
    async def stop(self) -> None:
        """Stop the async monitor."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def record_metric(name: str, value: float, unit: str = "ms", tags: Optional[Dict[str, str]] = None) -> None:
    """
    Record a performance metric using the global monitor.
    
    Args:
        name: Metric name
        value: Metric value
        unit: Unit of measurement
        tags: Additional tags
    """
    get_performance_monitor().record_metric(name, value, unit, tags)


def record_time(name: str, duration: float, tags: Optional[Dict[str, str]] = None) -> None:
    """
    Record a timing metric using the global monitor.
    
    Args:
        name: Metric name
        duration: Duration in seconds
        tags: Additional tags
    """
    get_performance_monitor().record_time(name, duration, tags)


def get_metric_stats(name: str) -> Optional[PerformanceStats]:
    """
    Get statistics for a metric using the global monitor.
    
    Args:
        name: Metric name
    
    Returns:
        Performance statistics or None
    """
    return get_performance_monitor().get_stats(name)


__all__ = [
    'PerformanceMetric',
    'PerformanceStats',
    'PerformanceMonitor',
    'AsyncPerformanceMonitor',
    'get_performance_monitor',
    'record_metric',
    'record_time',
    'get_metric_stats'
]
