# trading/bots/hedge_bot/hedge_bot_data_prometheus.py

import asyncio
import json
import logging
import time
import os
import sys
import platform
import socket
import psutil
import aiohttp
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Callable, Tuple
from decimal import Decimal
from collections import defaultdict
from functools import wraps
from contextlib import asynccontextmanager
import inspect
import traceback

try:
    from prometheus_client import (
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        Info,
        Enum as PromEnum,
        generate_latest,
        CONTENT_TYPE_LATEST,
        process_collector,
        platform_collector,
        gc_collector,
    )
    from prometheus_client.exposition import MetricsHandler
    from prometheus_client.openmetrics import parser
except ImportError:
    print("Prometheus client not installed. Please install: pip install prometheus-client")
    sys.exit(1)

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"
    ENUM = "enum"


class AggregationMethod(str, Enum):
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    STDDEV = "stddev"
    QUANTILE = "quantile"
    MEDIAN = "median"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricStorage(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"
    FILE = "file"


@dataclass
class MetricDefinition:
    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    buckets: Optional[List[float]] = None
    quantiles: Optional[List[Tuple[float, float]]] = None
    namespace: str = "nexus"
    subsystem: str = "hedge_bot"
    unit: str = ""
    storage: MetricStorage = MetricStorage.MEMORY
    ttl: int = 86400
    aggregation: AggregationMethod = AggregationMethod.LAST


@dataclass
class MetricData:
    name: str
    value: Union[float, int, str, bool, Decimal]
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    type: Optional[MetricType] = None
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertRule:
    name: str
    metric_path: str
    condition: str
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str = ""
    duration: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    rule_name: str
    severity: AlertSeverity
    description: str
    current_value: float
    threshold: float
    condition: str
    labels: Dict[str, str]
    timestamp: datetime
    active: bool = True
    resolved_at: Optional[datetime] = None


class MetricsCache:
    def __init__(self, max_size: int = 10000, ttl: int = 60):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
        self._ttl = ttl
        self._lock = asyncio.Lock()
        self._hit_count = 0
        self._miss_count = 0

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None
            
            entry = self._cache[key]
            if time.time() - entry["timestamp"] > self._ttl:
                del self._cache[key]
                self._miss_count += 1
                return None
            
            self._hit_count += 1
            return entry["value"]

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            if len(self._cache) >= self._max_size:
                oldest = min(self._cache.keys(), key=lambda k: self._cache[k]["timestamp"])
                del self._cache[oldest]
            
            self._cache[key] = {
                "value": value,
                "timestamp": time.time()
            }

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0

    def get_stats(self) -> Dict[str, int]:
        return {
            "size": len(self._cache),
            "hits": self._hit_count,
            "misses": self._miss_count,
            "max_size": self._max_size
        }


class PrometheusMetricRegistry:
    
    def __init__(self, namespace: str = "nexus", subsystem: str = "hedge_bot"):
        self.namespace = namespace
        self.subsystem = subsystem
        self._registry = CollectorRegistry()
        self._metrics: Dict[str, Any] = {}
        self._definitions: Dict[str, MetricDefinition] = {}
        self._lock = asyncio.Lock()
        self._cache = MetricsCache()
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._created_at = time.time()
        
        process_collector.ProcessCollector(registry=self._registry)
        platform_collector.PlatformCollector(registry=self._registry)
        gc_collector.GCCollector(registry=self._registry)
        
        self._initialize_default_metrics()
        self._initialize_advanced_metrics()

    def _initialize_default_metrics(self) -> None:
        default_metrics = [
            MetricDefinition("total_pnl", MetricType.GAUGE, "Total profit and loss", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("daily_pnl", MetricType.GAUGE, "Daily profit and loss", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("weekly_pnl", MetricType.GAUGE, "Weekly profit and loss", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("monthly_pnl", MetricType.GAUGE, "Monthly profit and loss", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("win_rate", MetricType.GAUGE, "Win rate percentage", ["strategy", "timeframe"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("sharpe_ratio", MetricType.GAUGE, "Sharpe ratio", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("sortino_ratio", MetricType.GAUGE, "Sortino ratio", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("calmar_ratio", MetricType.GAUGE, "Calmar ratio", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("omega_ratio", MetricType.GAUGE, "Omega ratio", ["strategy", "threshold"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("max_drawdown", MetricType.GAUGE, "Maximum drawdown percentage", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("current_drawdown", MetricType.GAUGE, "Current drawdown percentage", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("total_trades", MetricType.COUNTER, "Total number of trades executed", ["strategy", "side", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("winning_trades", MetricType.COUNTER, "Number of winning trades", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("losing_trades", MetricType.COUNTER, "Number of losing trades", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("breakeven_trades", MetricType.COUNTER, "Number of breakeven trades", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("avg_win", MetricType.GAUGE, "Average win amount", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("avg_loss", MetricType.GAUGE, "Average loss amount", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("profit_factor", MetricType.GAUGE, "Profit factor", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("recovery_factor", MetricType.GAUGE, "Recovery factor", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("open_positions", MetricType.GAUGE, "Number of open positions", ["strategy", "asset", "direction"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_size", MetricType.GAUGE, "Current position size", ["strategy", "asset", "direction", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_value", MetricType.GAUGE, "Current position value", ["strategy", "asset", "direction", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_pnl", MetricType.GAUGE, "Unrealized PnL for open positions", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_entry_price", MetricType.GAUGE, "Entry price for positions", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_current_price", MetricType.GAUGE, "Current price for positions", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_liquidation_price", MetricType.GAUGE, "Liquidation price for positions", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_leverage", MetricType.GAUGE, "Leverage used for position", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("position_margin", MetricType.GAUGE, "Margin used for position", ["strategy", "asset", "position_id"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("current_risk", MetricType.GAUGE, "Current risk level percentage", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("value_at_risk", MetricType.GAUGE, "Value at Risk (VaR)", ["strategy", "confidence", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("expected_shortfall", MetricType.GAUGE, "Expected Shortfall (CVaR)", ["strategy", "confidence", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("conditional_var", MetricType.GAUGE, "Conditional Value at Risk", ["strategy", "confidence", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("leverage_used", MetricType.GAUGE, "Current leverage used", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("margin_used", MetricType.GAUGE, "Margin used in quote currency", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("margin_available", MetricType.GAUGE, "Available margin", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("margin_ratio", MetricType.GAUGE, "Margin ratio percentage", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("portfolio_volatility", MetricType.GAUGE, "Portfolio volatility", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("concentration_ratio", MetricType.GAUGE, "Concentration ratio", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("orders_placed", MetricType.COUNTER, "Total orders placed", ["strategy", "type", "status", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("order_execution_time", MetricType.HISTOGRAM, "Order execution time in seconds", ["strategy", "type", "asset"], buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("order_slippage", MetricType.HISTOGRAM, "Order slippage in basis points", ["strategy", "type", "asset"], buckets=[0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("order_queue_depth", MetricType.GAUGE, "Current order queue depth", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_price", MetricType.GAUGE, "Current market price", ["asset", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_volume", MetricType.GAUGE, "Current trading volume", ["asset", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_volatility", MetricType.GAUGE, "Market volatility", ["asset", "symbol", "timeframe"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_spread", MetricType.GAUGE, "Bid-ask spread in basis points", ["asset", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_liquidity", MetricType.GAUGE, "Market liquidity score", ["asset", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("market_depth", MetricType.GAUGE, "Market depth", ["asset", "symbol", "side"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("hedge_ratio", MetricType.GAUGE, "Current hedge ratio", ["strategy", "asset", "symbol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("hedge_effectiveness", MetricType.GAUGE, "Hedge effectiveness percentage", ["strategy", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("correlation_coefficient", MetricType.GAUGE, "Correlation coefficient", ["asset1", "asset2", "period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("beta_coefficient", MetricType.GAUGE, "Beta coefficient relative to market", ["asset", "symbol", "benchmark"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("bot_status", MetricType.GAUGE, "Bot status (1=active, 0=inactive, -1=error)", ["strategy", "instance"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("memory_usage", MetricType.GAUGE, "Memory usage in bytes", ["component", "type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("cpu_usage", MetricType.GAUGE, "CPU usage percentage", ["component", "core"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("api_requests_total", MetricType.COUNTER, "Total API requests made", ["endpoint", "method", "status", "exchange"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("api_latency", MetricType.HISTOGRAM, "API request latency in seconds", ["endpoint", "method", "exchange"], buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 30.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("api_errors_total", MetricType.COUNTER, "Total API errors", ["endpoint", "method", "error_type", "exchange"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("websocket_reconnections", MetricType.COUNTER, "WebSocket reconnection count", ["endpoint", "exchange"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("websocket_latency", MetricType.HISTOGRAM, "WebSocket message latency in seconds", ["endpoint", "exchange"], buckets=[0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("websocket_messages_total", MetricType.COUNTER, "Total WebSocket messages received", ["endpoint", "exchange", "type"], namespace="nexus", subsystem="hedge_bot"),
        ]
        
        for metric_def in default_metrics:
            self._definitions[metric_def.name] = metric_def
            self._create_metric(metric_def)

    def _initialize_advanced_metrics(self) -> None:
        advanced_metrics = [
            MetricDefinition("strategy_performance", MetricType.INFO, "Strategy performance info", ["strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("machine_learning_accuracy", MetricType.GAUGE, "ML model accuracy", ["model", "metric"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("prediction_confidence", MetricType.GAUGE, "Prediction confidence score", ["model", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("feature_importance", MetricType.GAUGE, "Feature importance score", ["model", "feature"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("backtest_performance", MetricType.INFO, "Backtest performance results", ["strategy", "version"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("risk_adjusted_return", MetricType.GAUGE, "Risk adjusted return", ["strategy", "metric"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("maximum_exposure", MetricType.GAUGE, "Maximum exposure percentage", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("portfolio_delta", MetricType.GAUGE, "Portfolio delta (Greeks)", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("portfolio_gamma", MetricType.GAUGE, "Portfolio gamma (Greeks)", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("portfolio_vega", MetricType.GAUGE, "Portfolio vega (Greeks)", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("portfolio_theta", MetricType.GAUGE, "Portfolio theta (Greeks)", ["strategy", "asset"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("stress_test_loss", MetricType.GAUGE, "Stress test maximum loss", ["scenario", "strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("monte_carlo_var", MetricType.GAUGE, "Monte Carlo VaR", ["confidence", "strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("monte_carlo_cvar", MetricType.GAUGE, "Monte Carlo CVaR", ["confidence", "strategy"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("network_latency", MetricType.HISTOGRAM, "Network latency in seconds", ["endpoint", "protocol"], buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("database_queries_total", MetricType.COUNTER, "Total database queries", ["table", "operation"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("database_query_latency", MetricType.HISTOGRAM, "Database query latency in seconds", ["table", "operation"], buckets=[0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("cache_hit_rate", MetricType.GAUGE, "Cache hit rate percentage", ["cache_type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("message_queue_size", MetricType.GAUGE, "Message queue size", ["queue_name"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("message_processing_time", MetricType.HISTOGRAM, "Message processing time in seconds", ["queue_name", "message_type"], buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("async_task_count", MetricType.GAUGE, "Number of async tasks", ["task_type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("thread_pool_size", MetricType.GAUGE, "Thread pool size", ["pool_name"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("thread_active_count", MetricType.GAUGE, "Active thread count", ["pool_name"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("concurrent_connections", MetricType.GAUGE, "Concurrent connections", ["protocol", "direction"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("data_throughput", MetricType.GAUGE, "Data throughput in bytes per second", ["channel", "direction"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("disk_io", MetricType.GAUGE, "Disk I/O in bytes", ["operation", "device"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("file_descriptors", MetricType.GAUGE, "Number of open file descriptors", ["component"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("process_start_time", MetricType.INFO, "Process start time info", ["process", "hostname", "pid"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("python_runtime", MetricType.INFO, "Python runtime info", ["version", "implementation", "platform"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("system_uptime", MetricType.GAUGE, "System uptime in seconds", ["hostname"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("network_connections", MetricType.GAUGE, "Network connections count", ["state", "protocol"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("swap_memory_usage", MetricType.GAUGE, "Swap memory usage in bytes", ["hostname"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("disk_usage", MetricType.GAUGE, "Disk usage in bytes", ["mount", "fs_type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("disk_usage_percent", MetricType.GAUGE, "Disk usage percentage", ["mount", "fs_type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("load_average", MetricType.GAUGE, "System load average", ["period"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("context_switches", MetricType.COUNTER, "Context switches", ["type"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("interrupts", MetricType.COUNTER, "Hardware interrupts", ["device"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("temperature", MetricType.GAUGE, "System temperature in Celsius", ["sensor"], namespace="nexus", subsystem="hedge_bot"),
            MetricDefinition("fan_speed", MetricType.GAUGE, "Fan speed in RPM", ["fan"], namespace="nexus", subsystem="hedge_bot"),
        ]
        
        for metric_def in advanced_metrics:
            self._definitions[metric_def.name] = metric_def
            self._create_metric(metric_def)

    def _create_metric(self, definition: MetricDefinition) -> None:
        metric_kwargs = {
            "name": definition.name,
            "documentation": definition.description,
            "labelnames": definition.labels,
            "namespace": definition.namespace,
            "subsystem": definition.subsystem,
        }
        
        try:
            if definition.type == MetricType.COUNTER:
                self._metrics[definition.name] = Counter(**metric_kwargs, registry=self._registry)
            elif definition.type == MetricType.GAUGE:
                self._metrics[definition.name] = Gauge(**metric_kwargs, registry=self._registry)
            elif definition.type == MetricType.HISTOGRAM:
                metric_kwargs["buckets"] = definition.buckets or [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
                self._metrics[definition.name] = Histogram(**metric_kwargs, registry=self._registry)
            elif definition.type == MetricType.SUMMARY:
                metric_kwargs["quantiles"] = definition.quantiles or [(0.5, 0.05), (0.9, 0.01), (0.95, 0.01), (0.99, 0.001), (0.999, 0.0001)]
                self._metrics[definition.name] = Summary(**metric_kwargs, registry=self._registry)
            elif definition.type == MetricType.INFO:
                self._metrics[definition.name] = Info(**metric_kwargs, registry=self._registry)
            elif definition.type == MetricType.ENUM:
                self._metrics[definition.name] = PromEnum(**metric_kwargs, registry=self._registry)
        except Exception as e:
            logger.error(f"Error creating metric {definition.name}: {e}")

    def _get_metric(self, name: str) -> Any:
        if name not in self._metrics and name in self._definitions:
            self._create_metric(self._definitions[name])
        return self._metrics.get(name)

    async def create_metric_async(self, definition: MetricDefinition) -> None:
        async with self._lock:
            if definition.name in self._definitions:
                logger.warning(f"Metric {definition.name} already exists, overwriting")
            self._definitions[definition.name] = definition
            self._create_metric(definition)

    def set_metric(self, name: str, value: Any, labels: Dict[str, str] = None) -> bool:
        metric = self._get_metric(name)
        if not metric:
            logger.warning(f"Metric {name} not found")
            return False
        
        labels = labels or {}
        
        try:
            if isinstance(metric, (Counter, Gauge)):
                metric.labels(**labels).set(float(value))
            elif isinstance(metric, Histogram):
                metric.labels(**labels).observe(float(value))
            elif isinstance(metric, Info):
                if isinstance(value, dict):
                    metric.labels(**labels).info(value)
                else:
                    metric.labels(**labels).info({"value": str(value)})
            elif isinstance(metric, PromEnum):
                metric.labels(**labels).state(str(value))
            else:
                return False
            return True
        except Exception as e:
            logger.error(f"Error setting metric {name}: {e}")
            return False

    def increment_metric(self, name: str, value: float = 1.0, labels: Dict[str, str] = None) -> bool:
        metric = self._get_metric(name)
        if not metric:
            logger.warning(f"Metric {name} not found")
            return False
        
        labels = labels or {}
        
        try:
            if isinstance(metric, Counter):
                metric.labels(**labels).inc(value)
                return True
            else:
                logger.warning(f"Metric {name} is not a counter")
                return False
        except Exception as e:
            logger.error(f"Error incrementing metric {name}: {e}")
            return False

    def observe_metric(self, name: str, value: float, labels: Dict[str, str] = None) -> bool:
        metric = self._get_metric(name)
        if not metric:
            logger.warning(f"Metric {name} not found")
            return False
        
        labels = labels or {}
        
        try:
            if isinstance(metric, (Histogram, Summary)):
                metric.labels(**labels).observe(value)
                return True
            else:
                logger.warning(f"Metric {name} is not a histogram or summary")
                return False
        except Exception as e:
            logger.error(f"Error observing metric {name}: {e}")
            return False

    def get_metric_value(self, name: str, labels: Dict[str, str] = None) -> Optional[float]:
        metric = self._get_metric(name)
        if not metric:
            return None
        
        labels = labels or {}
        
        try:
            if hasattr(metric, "labels"):
                labeled_metric = metric.labels(**labels)
                if hasattr(labeled_metric, "_value"):
                    return labeled_metric._value
                elif hasattr(labeled_metric, "_sum"):
                    return labeled_metric._sum
        except Exception as e:
            logger.error(f"Error getting metric {name}: {e}")
        
        return None

    def generate_metrics(self) -> bytes:
        return generate_latest(self._registry)

    def clear_metrics(self) -> None:
        for metric_name in list(self._metrics.keys()):
            metric = self._metrics[metric_name]
            if hasattr(metric, "clear"):
                try:
                    metric.clear()
                except Exception as e:
                    logger.error(f"Error clearing metric {metric_name}: {e}")

    def reset_metrics(self) -> None:
        self._registry = CollectorRegistry()
        self._metrics.clear()
        self._initialize_default_metrics()
        self._initialize_advanced_metrics()

    def get_metric_info(self, name: str) -> Optional[MetricDefinition]:
        return self._definitions.get(name)

    def list_metrics(self) -> List[str]:
        return list(self._definitions.keys())

    def get_metric_count(self) -> int:
        return len(self._metrics)

    def get_cache_stats(self) -> Dict[str, int]:
        return self._cache.get_stats()


class HedgeBotPrometheusCollector:
    
    def __init__(
        self,
        config: Dict[str, Any],
        registry: Optional[PrometheusMetricRegistry] = None,
        push_gateway_url: Optional[str] = None,
        push_interval: int = 30,
        enable_http_server: bool = True,
        http_port: int = 9090,
        enable_advanced_metrics: bool = True,
    ):
        self.config = config
        self.registry = registry or PrometheusMetricRegistry()
        self.push_gateway_url = push_gateway_url
        self.push_interval = push_interval
        self.enable_http_server = enable_http_server
        self.http_port = http_port
        self.enable_advanced_metrics = enable_advanced_metrics
        self._running = False
        self._push_task: Optional[asyncio.Task] = None
        self._http_server: Optional[asyncio.Server] = None
        self._collectors: Dict[str, Callable] = {}
        self._metrics_cache: Dict[str, Dict] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_collection_time = 0.0
        self._collection_count = 0
        self._error_count = 0
        self._success_count = 0
        self._start_time = time.time()
        self._hostname = socket.gethostname()
        self._pid = os.getpid()
        self._lock = asyncio.Lock()
        self._alert_manager = PrometheusAlertManager(config.get("alerts", {}))
        self._metric_processors: Dict[str, Callable] = {}
        self._aggregation_windows: Dict[str, List[float]] = defaultdict(lambda: [])
        self._last_metrics: Dict[str, Dict] = {}
        self._historical_data: Dict[str, pd.DataFrame] = {}
        
        self._register_default_collectors()
        self._register_advanced_collectors()

    def _register_default_collectors(self) -> None:
        self.register_collector("performance", self._collect_performance_metrics)
        self.register_collector("risk", self._collect_risk_metrics)
        self.register_collector("positions", self._collect_position_metrics)
        self.register_collector("orders", self._collect_order_metrics)
        self.register_collector("market", self._collect_market_metrics)
        self.register_collector("system", self._collect_system_metrics)
        self.register_collector("hedge", self._collect_hedge_metrics)
        self.register_collector("trading", self._collect_trading_metrics)
        self.register_collector("broker", self._collect_broker_metrics)

    def _register_advanced_collectors(self) -> None:
        if self.enable_advanced_metrics:
            self.register_collector("ml_models", self._collect_ml_metrics)
            self.register_collector("backtesting", self._collect_backtest_metrics)
            self.register_collector("network", self._collect_network_metrics)
            self.register_collector("database", self._collect_database_metrics)
            self.register_collector("async_operations", self._collect_async_metrics)

    def register_collector(self, name: str, collector_fn: Callable) -> None:
        self._collectors[name] = collector_fn
        logger.info(f"Registered collector: {name}")

    def register_metric_processor(self, name: str, processor_fn: Callable) -> None:
        self._metric_processors[name] = processor_fn
        logger.info(f"Registered metric processor: {name}")

    async def _ensure_session(self) -> None:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=20)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={"User-Agent": "Nexus-HedgeBot/3.0"}
            )

    async def _push_metrics(self) -> None:
        if not self.push_gateway_url:
            return
        
        try:
            await self._ensure_session()
            metrics_data = self.registry.generate_metrics()
            
            async with self._session.post(
                f"{self.push_gateway_url}/metrics/job/nexus_hedge_bot/instance/{self._hostname}",
                data=metrics_data,
                headers={"Content-Type": CONTENT_TYPE_LATEST},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to push metrics: {response.status}")
                    self._error_count += 1
                    self.registry.increment_metric("api_errors_total", 1, {"endpoint": "pushgateway", "method": "post", "error_type": str(response.status), "exchange": "prometheus"})
                else:
                    logger.debug("Metrics pushed to PushGateway")
                    self._success_count += 1
                    
        except asyncio.TimeoutError:
            logger.error("Timeout pushing metrics to PushGateway")
            self._error_count += 1
            self.registry.increment_metric("api_errors_total", 1, {"endpoint": "pushgateway", "method": "post", "error_type": "timeout", "exchange": "prometheus"})
        except Exception as e:
            logger.error(f"Error pushing metrics: {e}")
            self._error_count += 1
            self.registry.increment_metric("api_errors_total", 1, {"endpoint": "pushgateway", "method": "post", "error_type": type(e).__name__, "exchange": "prometheus"})

    async def _push_loop(self) -> None:
        consecutive_failures = 0
        while self._running:
            try:
                await asyncio.sleep(self.push_interval)
                await self._push_metrics()
                consecutive_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"Error in push loop: {e}")
                backoff = min(5 * (2 ** consecutive_failures), 60)
                await asyncio.sleep(backoff)

    async def _start_http_server(self) -> None:
        if not self.enable_http_server:
            return
        
        try:
            from prometheus_client import start_http_server
            start_http_server(self.http_port, addr='0.0.0.0')
            logger.info(f"Prometheus HTTP server started on port {self.http_port}")
            
            self.registry.set_metric("bot_status", 1, {"strategy": "hedge_bot", "instance": self._hostname})
        except Exception as e:
            logger.error(f"Error starting HTTP server: {e}")
            self.enable_http_server = False

    async def collect_all(self) -> Dict[str, Any]:
        results = {}
        self._collection_count += 1
        start_time = time.time()
        
        async with self._lock:
            for name, collector in self._collectors.items():
                try:
                    collector_start = time.time()
                    metrics = await collector()
                    results[name] = metrics
                    
                    collection_time = time.time() - collector_start
                    self.registry.observe_metric("metric_collection_time", collection_time, {"collector": name})
                    
                    if name in self._metric_processors:
                        results[name] = self._metric_processors[name](metrics)
                    
                    self._last_metrics[name] = metrics
                    
                except Exception as e:
                    logger.error(f"Error collecting {name} metrics: {e}")
                    self._error_count += 1
                    self.registry.increment_metric("api_errors_total", 1, {"endpoint": f"collector_{name}", "method": "collect", "error_type": type(e).__name__, "exchange": "internal"})
                    results[name] = {"error": str(e), "traceback": traceback.format_exc()}
        
        self._last_collection_time = time.time()
        total_time = time.time() - start_time
        
        self.registry.set_metric("collection_duration", total_time, {"collector": "all"})
        self.registry.set_metric("collection_count", self._collection_count)
        self.registry.set_metric("error_count", self._error_count)
        self.registry.set_metric("success_count", self._success_count)
        
        alerts = self._alert_manager.check_alert_conditions(results)
        if alerts:
            for alert in alerts:
                self.registry.increment_metric("alerts_triggered", 1, {
                    "alert": alert["name"],
                    "severity": alert["severity"],
                    "metric": alert["metric_path"]
                })
        
        return results

    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        metrics = {
            "total_pnl": 0.0,
            "daily_pnl": 0.0,
            "weekly_pnl": 0.0,
            "monthly_pnl": 0.0,
            "win_rate": 0.0,
            "win_rate_1d": 0.0,
            "win_rate_1w": 0.0,
            "win_rate_1m": 0.0,
            "sharpe_ratio": 0.0,
            "sharpe_ratio_1d": 0.0,
            "sharpe_ratio_1w": 0.0,
            "sharpe_ratio_1m": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "omega_ratio": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_1d": 0.0,
            "max_drawdown_1w": 0.0,
            "max_drawdown_1m": 0.0,
            "current_drawdown": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "recovery_factor": 0.0,
            "expected_payoff": 0.0,
            "risk_reward_ratio": 0.0,
        }
        
        for key, value in metrics.items():
            if key in ["total_trades", "winning_trades", "losing_trades", "breakeven_trades"]:
                self.registry.increment_metric(key, value)
            elif "sharpe" in key or "sortino" in key or "calmar" in key or "omega" in key:
                period = "1d" if "1d" in key else "1w" if "1w" in key else "1m" if "1m" in key else "all"
                metric_name = key.replace("_1d", "").replace("_1w", "").replace("_1m", "")
                self.registry.set_metric(metric_name, value, {"strategy": "hedge_bot", "period": period})
            elif "win_rate" in key:
                timeframe = "1d" if "1d" in key else "1w" if "1w" in key else "1m" if "1m" in key else "all"
                self.registry.set_metric("win_rate", value, {"strategy": "hedge_bot", "timeframe": timeframe})
            elif "drawdown" in key:
                period = "1d" if "1d" in key else "1w" if "1w" in key else "1m" if "1m" in key else "all"
                metric_name = "max_drawdown" if "max" in key else "current_drawdown"
                self.registry.set_metric(metric_name, value, {"strategy": "hedge_bot", "period": period})
            else:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
        
        return metrics

    async def _collect_risk_metrics(self) -> Dict[str, Any]:
        metrics = {
            "current_risk": 0.0,
            "value_at_risk_95": 0.0,
            "value_at_risk_99": 0.0,
            "expected_shortfall_95": 0.0,
            "expected_shortfall_99": 0.0,
            "conditional_var_95": 0.0,
            "conditional_var_99": 0.0,
            "leverage_used": 0.0,
            "margin_used": 0.0,
            "margin_available": 0.0,
            "margin_ratio": 0.0,
            "portfolio_volatility": 0.0,
            "beta_coefficient": 0.0,
            "concentration_ratio": 0.0,
            "maximum_exposure": 0.0,
            "risk_adjusted_return": 0.0,
        }
        
        for key, value in metrics.items():
            if key.startswith("value_at_risk") or key.startswith("expected_shortfall") or key.startswith("conditional_var"):
                confidence = "95" if "95" in key else "99"
                metric_name = "value_at_risk" if "value_at" in key else "expected_shortfall" if "expected" in key else "conditional_var"
                self.registry.set_metric(metric_name, value, {"strategy": "hedge_bot", "confidence": confidence, "period": "1d"})
            elif key == "leverage_used":
                self.registry.set_metric("leverage_used", value, {"strategy": "hedge_bot"})
            elif key in ["margin_used", "margin_available", "margin_ratio"]:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
            elif key == "beta_coefficient":
                self.registry.set_metric("beta_coefficient", value, {"asset": "portfolio", "benchmark": "market"})
            elif key == "current_risk":
                self.registry.set_metric("current_risk", value, {"strategy": "hedge_bot"})
            else:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
        
        return metrics

    async def _collect_position_metrics(self) -> Dict[str, Any]:
        metrics = {
            "positions": [],
            "total_positions": 0,
            "total_position_value": 0.0,
            "total_unrealized_pnl": 0.0,
            "total_long_value": 0.0,
            "total_short_value": 0.0,
            "long_positions": 0,
            "short_positions": 0,
            "avg_position_size": 0.0,
            "max_position_size": 0.0,
        }
        
        positions = []
        total_value = 0.0
        total_pnl = 0.0
        long_value = 0.0
        short_value = 0.0
        long_count = 0
        short_count = 0
        max_size = 0.0
        
        for position in positions:
            size = getattr(position, 'size', 0.0)
            value = getattr(position, 'value', 0.0)
            pnl = getattr(position, 'unrealized_pnl', 0.0)
            direction = getattr(position, 'direction', 'long')
            
            total_value += value
            total_pnl += pnl
            
            if direction == 'long':
                long_value += value
                long_count += 1
            else:
                short_value += value
                short_count += 1
            
            max_size = max(max_size, size)
            
            labels = {
                "strategy": getattr(position, 'strategy', 'hedge_bot'),
                "asset": getattr(position, 'asset', ''),
                "direction": direction,
                "symbol": getattr(position, 'symbol', ''),
                "position_id": getattr(position, 'id', '')
            }
            
            self.registry.set_metric("position_size", size, labels)
            self.registry.set_metric("position_value", value, labels)
            self.registry.set_metric("position_pnl", pnl, labels)
            self.registry.set_metric("position_entry_price", getattr(position, 'entry_price', 0.0), labels)
            self.registry.set_metric("position_current_price", getattr(position, 'current_price', 0.0), labels)
            self.registry.set_metric("position_leverage", getattr(position, 'leverage', 1.0), labels)
            self.registry.set_metric("position_margin", getattr(position, 'margin', 0.0), labels)
            
            if hasattr(position, 'liquidation_price'):
                self.registry.set_metric("position_liquidation_price", position.liquidation_price, labels)
        
        metrics["positions"] = positions
        metrics["total_positions"] = len(positions)
        metrics["total_position_value"] = total_value
        metrics["total_unrealized_pnl"] = total_pnl
        metrics["total_long_value"] = long_value
        metrics["total_short_value"] = short_value
        metrics["long_positions"] = long_count
        metrics["short_positions"] = short_count
        metrics["max_position_size"] = max_size
        metrics["avg_position_size"] = total_value / max(1, len(positions))
        
        self.registry.set_metric("open_positions", len(positions), {"strategy": "hedge_bot"})
        
        return metrics

    async def _collect_order_metrics(self) -> Dict[str, Any]:
        metrics = {
            "orders": [],
            "total_orders": 0,
            "pending_orders": 0,
            "executed_orders": 0,
            "failed_orders": 0,
            "cancelled_orders": 0,
            "avg_execution_time": 0.0,
            "total_order_value": 0.0,
            "fill_rate": 0.0,
            "slippage_avg": 0.0,
            "slippage_max": 0.0,
        }
        
        orders = []
        total_exec_time = 0.0
        executed_count = 0
        total_slippage = 0.0
        max_slippage = 0.0
        total_value = 0.0
        
        for order in orders:
            status = getattr(order, 'status', 'unknown')
            order_type = getattr(order, 'type', 'limit')
            exec_time = getattr(order, 'execution_time', 0.0)
            slippage = getattr(order, 'slippage', 0.0)
            value = getattr(order, 'value', 0.0)
            
            labels = {
                "strategy": getattr(order, 'strategy', 'hedge_bot'),
                "type": order_type,
                "status": status,
                "asset": getattr(order, 'asset', '')
            }
            
            self.registry.increment_metric("orders_placed", 1, labels)
            
            if exec_time > 0:
                self.registry.observe_metric("order_execution_time", exec_time, labels)
                total_exec_time += exec_time
                executed_count += 1
            
            if slippage != 0:
                self.registry.observe_metric("order_slippage", abs(slippage), labels)
                total_slippage += abs(slippage)
                max_slippage = max(max_slippage, abs(slippage))
            
            total_value += value
        
        metrics["orders"] = orders
        metrics["total_orders"] = len(orders)
        metrics["avg_execution_time"] = total_exec_time / max(1, executed_count)
        metrics["total_order_value"] = total_value
        metrics["slippage_avg"] = total_slippage / max(1, len(orders))
        metrics["slippage_max"] = max_slippage
        
        self.registry.set_metric("order_queue_depth", len([o for o in orders if getattr(o, 'status', '') == 'pending']))
        
        return metrics

    async def _collect_market_metrics(self) -> Dict[str, Any]:
        metrics = {}
        market_data = {}
        
        symbols = self.config.get("symbols", ["BTC-USDT", "ETH-USDT"])
        
        for symbol in symbols:
            data = {
                "price": 0.0,
                "volume": 0.0,
                "volatility": 0.0,
                "spread": 0.0,
                "liquidity": 0.0,
                "depth_bid": 0.0,
                "depth_ask": 0.0,
                "high_24h": 0.0,
                "low_24h": 0.0,
                "change_24h": 0.0,
            }
            
            labels = {"asset": symbol.split('-')[0], "symbol": symbol}
            
            self.registry.set_metric("market_price", data["price"], labels)
            self.registry.set_metric("market_volume", data["volume"], labels)
            self.registry.set_metric("market_spread", data["spread"], labels)
            self.registry.set_metric("market_liquidity", data["liquidity"], labels)
            self.registry.set_metric("market_depth", data["depth_bid"], {**labels, "side": "bid"})
            self.registry.set_metric("market_depth", data["depth_ask"], {**labels, "side": "ask"})
            
            for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
                self.registry.set_metric("market_volatility", data["volatility"], {**labels, "timeframe": tf})
            
            market_data[symbol] = data
        
        metrics["market_data"] = market_data
        return metrics

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        metrics = {}
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            disk = psutil.disk_usage('/')
            
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()
            connections = len(process.connections())
            threads = process.num_threads()
            
            for i, cpu in enumerate(cpu_percent):
                self.registry.set_metric("cpu_usage", cpu, {"component": "system", "core": str(i)})
            
            self.registry.set_metric("cpu_usage", process_cpu, {"component": "hedge_bot", "core": "process"})
            self.registry.set_metric("memory_usage", memory.used, {"component": "system", "type": "ram"})
            self.registry.set_metric("memory_usage", process_memory.rss, {"component": "hedge_bot", "type": "rss"})
            self.registry.set_metric("memory_usage", process_memory.vms, {"component": "hedge_bot", "type": "vms"})
            self.registry.set_metric("swap_memory_usage", swap.used, {"hostname": self._hostname})
            self.registry.set_metric("disk_usage", disk.used, {"mount": "/", "fs_type": "ext4"})
            self.registry.set_metric("disk_usage_percent", disk.percent, {"mount": "/", "fs_type": "ext4"})
            self.registry.set_metric("system_uptime", time.time() - psutil.boot_time(), {"hostname": self._hostname})
            self.registry.set_metric("network_connections", connections, {"state": "total", "protocol": "all"})
            self.registry.set_metric("file_descriptors", process.num_fds(), {"component": "hedge_bot"})
            self.registry.set_metric("thread_active_count", threads, {"pool_name": "process"})
            self.registry.set_metric("thread_pool_size", threads, {"pool_name": "process"})
            
            load_avg = psutil.getloadavg()
            for i, load in enumerate(load_avg):
                self.registry.set_metric("load_average", load, {"period": ["1m", "5m", "15m"][i]})
            
            metrics = {
                "cpu_percent": sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0,
                "memory_percent": memory.percent,
                "memory_used": memory.used,
                "swap_used": swap.used,
                "disk_used": disk.used,
                "disk_percent": disk.percent,
                "connections": connections,
                "process_cpu": process_cpu,
                "process_memory": process_memory.rss,
                "uptime": time.time() - psutil.boot_time(),
                "load_avg_1m": load_avg[0] if load_avg else 0,
                "load_avg_5m": load_avg[1] if load_avg else 0,
                "load_avg_15m": load_avg[2] if load_avg else 0,
            }
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            metrics = {"error": str(e)}
        
        self.registry.set_metric("bot_status", 1, {"strategy": "hedge_bot", "instance": self._hostname})
        
        return metrics

    async def _collect_hedge_metrics(self) -> Dict[str, Any]:
        metrics = {
            "hedge_ratio": 0.0,
            "hedge_effectiveness": 0.0,
            "correlations": {},
            "betas": {},
            "portfolio_delta": 0.0,
            "portfolio_gamma": 0.0,
            "portfolio_vega": 0.0,
            "portfolio_theta": 0.0,
        }
        
        self.registry.set_metric("hedge_ratio", metrics["hedge_ratio"], {"strategy": "hedge_bot"})
        self.registry.set_metric("hedge_effectiveness", metrics["hedge_effectiveness"], {"strategy": "hedge_bot", "period": "1d"})
        
        for asset_pair, correlation in metrics.get("correlations", {}).items():
            asset1, asset2 = asset_pair.split("_") if "_" in asset_pair else ("unknown", "unknown")
            self.registry.set_metric("correlation_coefficient", correlation, {"asset1": asset1, "asset2": asset2, "period": "1d"})
        
        for asset, beta in metrics.get("betas", {}).items():
            self.registry.set_metric("beta_coefficient", beta, {"asset": asset, "benchmark": "market"})
        
        self.registry.set_metric("portfolio_delta", metrics["portfolio_delta"], {"strategy": "hedge_bot"})
        self.registry.set_metric("portfolio_gamma", metrics["portfolio_gamma"], {"strategy": "hedge_bot"})
        self.registry.set_metric("portfolio_vega", metrics["portfolio_vega"], {"strategy": "hedge_bot"})
        self.registry.set_metric("portfolio_theta", metrics["portfolio_theta"], {"strategy": "hedge_bot"})
        
        return metrics

    async def _collect_trading_metrics(self) -> Dict[str, Any]:
        metrics = {
            "daily_volume": 0.0,
            "weekly_volume": 0.0,
            "monthly_volume": 0.0,
            "trading_frequency": 0.0,
            "avg_trade_duration": 0.0,
            "max_trade_duration": 0.0,
            "min_trade_duration": 0.0,
            "trade_interval": 0.0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "average_trade": 0.0,
            "median_trade": 0.0,
        }
        
        for key, value in metrics.items():
            if "volume" in key or "frequency" in key or "duration" in key:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
            elif "consecutive" in key:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
            else:
                self.registry.set_metric(key, value, {"strategy": "hedge_bot"})
        
        return metrics

    async def _collect_broker_metrics(self) -> Dict[str, Any]:
        metrics = {
            "broker_balance": 0.0,
            "broker_equity": 0.0,
            "broker_margin": 0.0,
            "broker_free_margin": 0.0,
            "broker_leverage": 0.0,
            "broker_connected": 1,
            "broker_latency": 0.0,
        }
        
        for key, value in metrics.items():
            if "broker_connected" in key:
                self.registry.set_metric("bot_status", value, {"strategy": "hedge_bot", "instance": "broker"})
            elif "broker_latency" in key:
                self.registry.observe_metric("api_latency", value, {"endpoint": "broker", "method": "status", "exchange": self.config.get("broker", "unknown")})
            else:
                self.registry.set_metric(key.replace("broker_", ""), value, {"exchange": self.config.get("broker", "unknown")})
        
        return metrics

    async def _collect_ml_metrics(self) -> Dict[str, Any]:
        metrics = {
            "models": [],
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "roc_auc": 0.0,
            "log_loss": 0.0,
            "mse": 0.0,
            "mae": 0.0,
            "r2_score": 0.0,
            "training_time": 0.0,
            "inference_time": 0.0,
        }
        
        models = self.config.get("ml_models", [])
        metrics["models"] = models
        
        for model in models:
            labels = {"model": model}
            self.registry.set_metric("machine_learning_accuracy", metrics["accuracy"], {**labels, "metric": "accuracy"})
            self.registry.set_metric("machine_learning_accuracy", metrics["precision"], {**labels, "metric": "precision"})
            self.registry.set_metric("machine_learning_accuracy", metrics["recall"], {**labels, "metric": "recall"})
            self.registry.set_metric("machine_learning_accuracy", metrics["f1_score"], {**labels, "metric": "f1_score"})
            self.registry.set_metric("machine_learning_accuracy", metrics["roc_auc"], {**labels, "metric": "roc_auc"})
            self.registry.set_metric("prediction_confidence", metrics["accuracy"], {"model": model})
        
        self.registry.observe_metric("api_latency", metrics["inference_time"], {"endpoint": "ml_inference", "method": "predict", "exchange": "internal"})
        
        return metrics

    async def _collect_backtest_metrics(self) -> Dict[str, Any]:
        metrics = {
            "backtest_results": [],
            "backtest_pnl": 0.0,
            "backtest_sharpe": 0.0,
            "backtest_drawdown": 0.0,
            "backtest_win_rate": 0.0,
            "backtest_trades": 0,
            "backtest_volatility": 0.0,
        }
        
        results = self.config.get("backtest_results", [])
        
        for result in results:
            version = result.get("version", "v1")
            info = {
                "strategy": result.get("strategy", "hedge_bot"),
                "version": version,
                "pnl": result.get("pnl", 0),
                "sharpe": result.get("sharpe", 0),
                "drawdown": result.get("drawdown", 0),
                "win_rate": result.get("win_rate", 0),
                "trades": result.get("trades", 0),
            }
            self.registry.set_metric("backtest_performance", info, {"strategy": "hedge_bot", "version": version})
        
        metrics["backtest_results"] = results
        
        return metrics

    async def _collect_network_metrics(self) -> Dict[str, Any]:
        metrics = {
            "network_interfaces": [],
            "bytes_sent": 0,
            "bytes_recv": 0,
            "packets_sent": 0,
            "packets_recv": 0,
            "errin": 0,
            "errout": 0,
            "dropin": 0,
            "dropout": 0,
            "active_connections": 0,
        }
        
        try:
            net_io = psutil.net_io_counters()
            metrics["bytes_sent"] = net_io.bytes_sent
            metrics["bytes_recv"] = net_io.bytes_recv
            metrics["packets_sent"] = net_io.packets_sent
            metrics["packets_recv"] = net_io.packets_recv
            metrics["errin"] = net_io.errin
            metrics["errout"] = net_io.errout
            metrics["dropin"] = net_io.dropin
            metrics["dropout"] = net_io.dropout
            
            self.registry.set_metric("data_throughput", net_io.bytes_sent / 1024, {"channel": "network", "direction": "out"})
            self.registry.set_metric("data_throughput", net_io.bytes_recv / 1024, {"channel": "network", "direction": "in"})
            
            self.registry.set_metric("network_connections", len(psutil.net_connections()), {"state": "active", "protocol": "all"})
            
            for iface, stats in psutil.net_if_stats().items():
                metrics["network_interfaces"].append({
                    "name": iface,
                    "is_up": stats.isup,
                    "speed": stats.speed,
                    "mtu": stats.mtu
                })
                
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
        
        return metrics

    async def _collect_database_metrics(self) -> Dict[str, Any]:
        metrics = {
            "query_count": 0,
            "query_latency": 0.0,
            "connection_pool_size": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "cache_hit_rate": 0.0,
            "cache_miss_rate": 0.0,
        }
        
        self.registry.set_metric("cache_hit_rate", metrics["cache_hit_rate"], {"cache_type": "database"})
        self.registry.set_metric("concurrent_connections", metrics["active_connections"], {"protocol": "database", "direction": "in"})
        self.registry.observe_metric("database_query_latency", metrics["query_latency"], {"table": "trades", "operation": "select"})
        self.registry.increment_metric("database_queries_total", metrics["query_count"], {"table": "trades", "operation": "select"})
        
        return metrics

    async def _collect_async_metrics(self) -> Dict[str, Any]:
        metrics = {
            "task_count": 0,
            "running_tasks": 0,
            "pending_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "avg_task_duration": 0.0,
            "max_task_duration": 0.0,
        }
        
        self.registry.set_metric("async_task_count", metrics["task_count"], {"task_type": "all"})
        self.registry.set_metric("async_task_count", metrics["running_tasks"], {"task_type": "running"})
        self.registry.set_metric("async_task_count", metrics["pending_tasks"], {"task_type": "pending"})
        
        return metrics

    async def collect_single(self, collector_name: str) -> Dict[str, Any]:
        if collector_name not in self._collectors:
            raise ValueError(f"Collector {collector_name} not found")
        
        try:
            result = await self._collectors[collector_name]()
            self._last_metrics[collector_name] = result
            return result
        except Exception as e:
            logger.error(f"Error collecting {collector_name}: {e}")
            return {"error": str(e)}

    async def start(self) -> None:
        if self._running:
            logger.warning("Prometheus collector already running")
            return
        
        self._running = True
        logger.info("Starting Prometheus collector")
        
        self.registry.set_metric("process_start_time", {"process": "hedge_bot", "hostname": self._hostname, "pid": str(self._pid)})
        self.registry.set_metric("python_runtime", {"version": sys.version, "implementation": sys.implementation.name, "platform": platform.platform()})
        
        if self.push_gateway_url:
            self._push_task = asyncio.create_task(self._push_loop())
        
        if self.enable_http_server:
            await self._start_http_server()
        
        await self.collect_all()
        logger.info("Prometheus collector started successfully")

    async def stop(self) -> None:
        self._running = False
        
        if self._push_task:
            self._push_task.cancel()
            try:
                await self._push_task
            except asyncio.CancelledError:
                pass
            self._push_task = None
        
        if self._session:
            await self._session.close()
            self._session = None
        
        self.registry.set_metric("bot_status", 0, {"strategy": "hedge_bot", "instance": self._hostname})
        
        logger.info("Prometheus collector stopped")

    async def collect_and_push(self) -> None:
        await self.collect_all()
        await self._push_metrics()

    def get_metrics_http_response(self) -> bytes:
        return self.registry.generate_metrics()

    def get_metrics_json(self) -> str:
        data = {
            "timestamp": datetime.now().isoformat(),
            "collection_count": self._collection_count,
            "error_count": self._error_count,
            "success_count": self._success_count,
            "uptime": time.time() - self._start_time,
            "hostname": self._hostname,
            "pid": self._pid,
            "metrics": {}
        }
        
        for metric_name, metric in self.registry._metrics.items():
            if hasattr(metric, "_samples"):
                samples = []
                for sample in metric._samples:
                    samples.append({
                        "name": sample.name,
                        "value": sample.value,
                        "labels": dict(sample.labels) if hasattr(sample, "labels") else {}
                    })
                data["metrics"][metric_name] = samples
        
        return json.dumps(data, indent=2, default=str)

    def get_metric_health_status(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._running else "stopped",
            "running": self._running,
            "collection_count": self._collection_count,
            "error_count": self._error_count,
            "success_count": self._success_count,
            "uptime": time.time() - self._start_time,
            "registered_collectors": list(self._collectors.keys()),
            "metric_count": len(self.registry._metrics),
            "last_collection": datetime.fromtimestamp(
                self._last_collection_time
            ).isoformat() if self._last_collection_time > 0 else None,
            "push_gateway_enabled": bool(self.push_gateway_url),
            "push_interval": self.push_interval,
            "http_server_enabled": self.enable_http_server,
            "http_port": self.http_port,
            "hostname": self._hostname,
            "pid": self._pid,
            "cache_stats": self.registry.get_cache_stats(),
            "alerts_active": len(self._alert_manager.get_active_alerts()),
        }

    def get_collector_info(self) -> Dict[str, Any]:
        return {
            "collectors": {name: inspect.signature(collector) for name, collector in self._collectors.items()},
            "processors": {name: inspect.signature(processor) for name, processor in self._metric_processors.items()},
        }


class PrometheusAlertManager:
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, Alert] = {}
        self._logger = logging.getLogger(__name__)
        self._historical_values: Dict[str, List[float]] = defaultdict(lambda: [])
        self._max_history = 1000
        
        self._load_rules()

    def _load_rules(self) -> None:
        for rule_name, rule_config in self.config.get("rules", {}).items():
            self.rules[rule_name] = AlertRule(
                name=rule_name,
                metric_path=rule_config.get("metric_path", ""),
                condition=rule_config.get("condition", ">"),
                threshold=rule_config.get("threshold", 0.0),
                severity=AlertSeverity(rule_config.get("severity", "warning")),
                description=rule_config.get("description", f"Alert for {rule_name}"),
                duration=rule_config.get("duration", 0),
                labels=rule_config.get("labels", {}),
                annotations=rule_config.get("annotations", {})
            )

    def add_rule(self, rule: AlertRule) -> None:
        self.rules[rule.name] = rule
        self._logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> None:
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.alerts.pop(rule_name, None)
            self._logger.info(f"Removed alert rule: {rule_name}")

    def check_alert_conditions(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        triggered = []
        current_time = datetime.now()
        
        for rule_name, rule in self.rules.items():
            try:
                metric_value = self._get_nested_value(metrics, rule.metric_path)
                if metric_value is None:
                    continue
                
                self._historical_values[rule_name].append(float(metric_value))
                if len(self._historical_values[rule_name]) > self._max_history:
                    self._historical_values[rule_name].pop(0)
                
                condition_met = self._check_condition(metric_value, rule.condition, rule.threshold)
                
                if condition_met:
                    if rule.duration > 0:
                        values = self._historical_values[rule_name][-rule.duration:]
                        if len(values) >= rule.duration:
                            sustained = all(
                                self._check_condition(v, rule.condition, rule.threshold)
                                for v in values
                            )
                            if not sustained:
                                continue
                    
                    alert = Alert(
                        rule_name=rule_name,
                        severity=rule.severity,
                        description=rule.description,
                        current_value=float(metric_value),
                        threshold=rule.threshold,
                        condition=rule.condition,
                        labels=rule.labels,
                        timestamp=current_time,
                        active=True
                    )
                    
                    if rule_name not in self.alerts or not self.alerts[rule_name].active:
                        self.alerts[rule_name] = alert
                        triggered.append({
                            "name": rule_name,
                            "severity": rule.severity.value,
                            "description": rule.description,
                            "metric_path": rule.metric_path,
                            "current_value": float(metric_value),
                            "threshold": rule.threshold,
                            "condition": rule.condition,
                            "labels": rule.labels,
                            "annotations": rule.annotations,
                            "timestamp": current_time.isoformat()
                        })
                else:
                    if rule_name in self.alerts and self.alerts[rule_name].active:
                        self.alerts[rule_name].active = False
                        self.alerts[rule_name].resolved_at = current_time
                        triggered.append({
                            "name": rule_name,
                            "severity": rule.severity.value,
                            "description": f"Alert {rule_name} resolved",
                            "metric_path": rule.metric_path,
                            "current_value": float(metric_value),
                            "threshold": rule.threshold,
                            "condition": rule.condition,
                            "labels": rule.labels,
                            "annotations": {"resolved": "true"},
                            "timestamp": current_time.isoformat(),
                            "resolved": True
                        })
                    
            except Exception as e:
                self._logger.error(f"Error checking alert rule {rule_name}: {e}")
        
        return triggered

    def _get_nested_value(self, obj: Any, path: str) -> Optional[float]:
        keys = path.split(".")
        value = obj
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                idx = int(key)
                if idx < len(value):
                    value = value[idx]
                else:
                    return None
            else:
                return None
            
            if value is None:
                return None
        
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _check_condition(self, value: Any, condition: str, threshold: float) -> bool:
        if not isinstance(value, (int, float)):
            return False
        
        conditions = {
            ">": lambda v, t: v > t,
            ">=": lambda v, t: v >= t,
            "<": lambda v, t: v < t,
            "<=": lambda v, t: v <= t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t,
            "between": lambda v, t: t[0] < v < t[1] if isinstance(t, (list, tuple)) else False,
            "outside": lambda v, t: v < t[0] or v > t[1] if isinstance(t, (list, tuple)) else False,
            "changes": lambda v, t: abs(v - self._historical_values.get("last", v)) > t,
        }
        
        return conditions.get(condition, lambda v, t: False)(value, threshold)

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": alert.rule_name,
                "severity": alert.severity.value,
                "description": alert.description,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
                "condition": alert.condition,
                "labels": alert.labels,
                "timestamp": alert.timestamp.isoformat(),
                "active": alert.active
            }
            for alert in self.alerts.values()
            if alert.active
        ]

    def get_all_alerts(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": alert.rule_name,
                "severity": alert.severity.value,
                "description": alert.description,
                "current_value": alert.current_value,
                "threshold": alert.threshold,
                "condition": alert.condition,
                "labels": alert.labels,
                "timestamp": alert.timestamp.isoformat(),
                "active": alert.active,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None
            }
            for alert in self.alerts.values()
        ]

    def clear_alerts(self) -> None:
        self.alerts.clear()
        self._logger.info("Cleared all alerts")

    def get_alert_stats(self) -> Dict[str, Any]:
        total = len(self.alerts)
        active = sum(1 for a in self.alerts.values() if a.active)
        resolved = total - active
        
        return {
            "total_alerts": total,
            "active_alerts": active,
            "resolved_alerts": resolved,
            "by_severity": {
                severity.value: sum(1 for a in self.alerts.values() if a.severity == severity and a.active)
                for severity in AlertSeverity
            }
        }

    def get_rule_info(self, rule_name: str) -> Optional[Dict[str, Any]]:
        if rule_name not in self.rules:
            return None
        
        rule = self.rules[rule_name]
        return {
            "name": rule.name,
            "metric_path": rule.metric_path,
            "condition": rule.condition,
            "threshold": rule.threshold,
            "severity": rule.severity.value,
            "description": rule.description,
            "duration": rule.duration,
            "labels": rule.labels,
            "annotations": rule.annotations,
            "active": rule_name in self.alerts and self.alerts[rule_name].active
        }


__all__ = [
    "MetricType",
    "AggregationMethod",
    "MetricDefinition",
    "MetricData",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    "MetricStorage",
    "PrometheusMetricRegistry",
    "HedgeBotPrometheusCollector",
    "PrometheusAlertManager",
    "MetricsCache",
]
