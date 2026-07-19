# trading/bots/arbitrage_bot/core/execution_timer.py
# Nexus AI Trading System - Arbitrage Bot Execution Timer Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Execution Timer Module

This module provides comprehensive execution timing and latency monitoring
for the arbitrage bot system, including:

- Precision timing and latency measurement
- Execution time tracking and analytics
- Performance monitoring and alerting
- Latency distribution analysis
- SLA monitoring
- Timing statistics and reporting
- Concurrent execution management
- Timeout handling
- Performance profiling
- Latency benchmarking

The execution timer ensures that the arbitrage bot operates within
acceptable latency bounds and provides detailed timing analytics
for performance optimization.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator
from redis.asyncio import Redis
import numpy as np

# Nexus imports
from shared.helpers.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class TimerStatus(str, Enum):
    """Timer status."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ERROR = "error"


class TimerMetricType(str, Enum):
    """Timer metric types."""
    EXECUTION = "execution"
    ORDER_PLACEMENT = "order_placement"
    ORDER_CANCELLATION = "order_cancellation"
    ORDER_STATUS = "order_status"
    BALANCE_UPDATE = "balance_update"
    MARKET_DATA = "market_data"
    WEBHOOK = "webhook"
    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    TOTAL = "total"


class TimerSeverity(str, Enum):
    """Timer severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class ExecutionTimerConfig(BaseModel):
    """Execution timer configuration."""
    enabled: bool = True
    track_all: bool = True
    track_critical: bool = True
    default_timeout: float = 30.0
    warning_threshold: float = 5.0  # seconds
    error_threshold: float = 10.0  # seconds
    critical_threshold: float = 20.0  # seconds
    max_metrics_history: int = 10000
    persist_metrics: bool = True
    alert_on_slow: bool = True
    alert_on_timeout: bool = True
    alert_on_error: bool = True
    metric_ttl: int = 3600  # seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('default_timeout', 'warning_threshold', 'error_threshold', 'critical_threshold')
    def validate_thresholds(cls, v):
        if v < 0:
            raise ValueError("Threshold must be non-negative")
        return v

    @validator('max_metrics_history')
    def validate_max_history(cls, v):
        if v < 100:
            raise ValueError("Max metrics history must be at least 100")
        return v


class TimerMetric(BaseModel):
    """Timer metric."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: TimerMetricType
    severity: TimerSeverity = TimerSeverity.INFO
    status: TimerStatus = TimerStatus.COMPLETED
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    timeout_seconds: Optional[float] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_slow(self) -> bool:
        """Check if the metric is slow."""
        if self.duration_ms is None:
            return False
        return self.duration_ms > 5000  # 5 seconds

    @property
    def is_timeout(self) -> bool:
        """Check if the metric is a timeout."""
        return self.status == TimerStatus.TIMEOUT

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.duration_ms is None:
            return None
        return self.duration_ms / 1000

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class TimerStatistics(BaseModel):
    """Timer statistics."""
    name: str
    type: TimerMetricType
    count: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_dev_ms: float = 0.0
    total_ms: float = 0.0
    slow_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    success_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    window_seconds: int = 60


class ExecutionTimerSnapshot(BaseModel):
    """Timer snapshot."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_metrics: int
    active_timers: int
    completed_timers: int
    slow_timers: int
    timeout_timers: int
    error_timers: int
    average_duration_ms: float
    stats_by_type: Dict[str, TimerStatistics]
    stats_by_name: Dict[str, TimerStatistics]
    slowest_metrics: List[TimerMetric]
    latest_metrics: List[TimerMetric]


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Timer metrics
CREATE TABLE IF NOT EXISTS execution_timer_metrics (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms FLOAT,
    timeout_seconds FLOAT,
    thread_id VARCHAR(64),
    task_id VARCHAR(64),
    correlation_id VARCHAR(64),
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    error TEXT,
    stack_trace TEXT,
    context JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_execution_timer_metrics_name (name),
    INDEX idx_execution_timer_metrics_type (type),
    INDEX idx_execution_timer_metrics_status (status),
    INDEX idx_execution_timer_metrics_start_time (start_time)
);

-- Timer statistics
CREATE TABLE IF NOT EXISTS execution_timer_stats (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    count INTEGER DEFAULT 0,
    min_ms FLOAT DEFAULT 0,
    max_ms FLOAT DEFAULT 0,
    mean_ms FLOAT DEFAULT 0,
    median_ms FLOAT DEFAULT 0,
    p50_ms FLOAT DEFAULT 0,
    p90_ms FLOAT DEFAULT 0,
    p95_ms FLOAT DEFAULT 0,
    p99_ms FLOAT DEFAULT 0,
    std_dev_ms FLOAT DEFAULT 0,
    total_ms FLOAT DEFAULT 0,
    slow_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_seconds INTEGER DEFAULT 60,
    UNIQUE(name, type, timestamp)
);

-- Timer alerts
CREATE TABLE IF NOT EXISTS execution_timer_alerts (
    id SERIAL PRIMARY KEY,
    metric_id VARCHAR(64) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_execution_timer_alerts_metric_id (metric_id),
    INDEX idx_execution_timer_alerts_created_at (created_at)
);
"""


# =============================================================================
# EXECUTION TIMER CLASS
# =============================================================================

class ExecutionTimer:
    """
    High-precision execution timer for arbitrage bot.
    
    This class provides comprehensive timing and performance monitoring
    for arbitrage operations with support for:
    
    - Sub-millisecond precision timing
    - Concurrent timer support
    - Automatic timeout detection
    - Performance statistics
    - Custom metrics and tags
    - Alert on slow/timeout operations
    - Persistence to database
    - Real-time monitoring
    - Correlation ID tracking
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[ExecutionTimerConfig] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        """
        Initialize the execution timer.
        
        Args:
            name: Timer name
            config: Timer configuration
            redis: Redis client for caching
            pool: PostgreSQL connection pool
        """
        self.name = name
        self.config = config or ExecutionTimerConfig()
        self.redis = redis
        self.pool = pool
        
        # Timer state
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._status = TimerStatus.IDLE
        self._metrics: Dict[str, TimerMetric] = {}
        self._active_metrics: Dict[str, TimerMetric] = {}
        self._completed_metrics: List[TimerMetric] = []
        
        # Statistics
        self._statistics: Dict[str, TimerStatistics] = {}
        self._stats_by_type: Dict[str, TimerStatistics] = {}
        self._stats_by_name: Dict[str, TimerStatistics] = {}
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Running state
        self._initialized = False
        self._running = False
        
        # Database
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info(f"ExecutionTimer '{name}' initialized")
    
    async def initialize(self):
        """Initialize the execution timer."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load statistics
        if self.pool:
            await self._load_statistics()
        
        # Start metrics collection
        if self.config.track_all:
            self._running = True
            asyncio.create_task(self._metrics_collection_loop())
        
        self._initialized = True
        logger.info(f"ExecutionTimer '{self.name}' initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # TIMER OPERATIONS
    # =========================================================================
    
    async def start(
        self,
        metric_type: TimerMetricType = TimerMetricType.EXECUTION,
        timeout: Optional[float] = None,
        correlation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a timer.
        
        Args:
            metric_type: Type of metric
            timeout: Timeout in seconds
            correlation_id: Correlation ID for tracking
            tags: List of tags
            metadata: Additional metadata
            context: Context data
            
        Returns:
            Metric ID
        """
        if not self.config.enabled:
            return ""
        
        metric_id = str(uuid.uuid4())
        
        metric = TimerMetric(
            id=metric_id,
            name=self.name,
            type=metric_type,
            severity=TimerSeverity.INFO,
            status=TimerStatus.RUNNING,
            start_time=datetime.utcnow(),
            timeout_seconds=timeout or self.config.default_timeout,
            correlation_id=correlation_id,
            tags=tags or [],
            metadata=metadata or {},
            context=context or {}
        )
        
        async with self._lock:
            self._metrics[metric_id] = metric
            self._active_metrics[metric_id] = metric
        
        # Start timeout monitor
        asyncio.create_task(self._monitor_timeout(metric_id))
        
        logger.debug(f"Timer started: {self.name} [{metric_type.value}] id={metric_id}")
        
        return metric_id
    
    async def stop(
        self,
        metric_id: str,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TimerMetric]:
        """
        Stop a timer.
        
        Args:
            metric_id: Metric ID
            error: Error message if any
            metadata: Additional metadata
            
        Returns:
            Timer metric or None
        """
        if not metric_id or metric_id not in self._active_metrics:
            return None
        
        async with self._lock:
            metric = self._active_metrics.pop(metric_id)
            
            if metric_id in self._metrics:
                self._metrics[metric_id] = metric
            
            metric.end_time = datetime.utcnow()
            metric.duration_ms = (metric.end_time - metric.start_time).total_seconds() * 1000
            metric.status = TimerStatus.COMPLETED if not error else TimerStatus.ERROR
            
            if error:
                metric.error = error
                metric.severity = TimerSeverity.ERROR
            
            if metadata:
                metric.metadata.update(metadata)
            
            # Check thresholds
            if metric.duration_ms > self.config.critical_threshold * 1000:
                metric.severity = TimerSeverity.CRITICAL
            elif metric.duration_ms > self.config.error_threshold * 1000:
                metric.severity = TimerSeverity.ERROR
            elif metric.duration_ms > self.config.warning_threshold * 1000:
                metric.severity = TimerSeverity.WARNING
            
            # Add to completed
            self._completed_metrics.append(metric)
            
            # Trim completed metrics
            if len(self._completed_metrics) > self.config.max_metrics_history:
                self._completed_metrics = self._completed_metrics[-self.config.max_metrics_history:]
            
            # Update statistics
            await self._update_statistics(metric)
            
            # Save metric
            if self.config.persist_metrics and self.pool:
                await self._save_metric(metric)
            
            # Check for alerts
            if metric.severity in [TimerSeverity.WARNING, TimerSeverity.ERROR, TimerSeverity.CRITICAL]:
                await self._trigger_alert(metric)
        
        logger.debug(f"Timer stopped: {self.name} [{metric.type.value}] duration={metric.duration_ms:.2f}ms")
        
        return metric
    
    async def _monitor_timeout(self, metric_id: str):
        """
        Monitor a timer for timeout.
        
        Args:
            metric_id: Metric ID
        """
        if metric_id not in self._active_metrics:
            return
        
        metric = self._active_metrics[metric_id]
        timeout = metric.timeout_seconds or self.config.default_timeout
        
        await asyncio.sleep(timeout)
        
        async with self._lock:
            if metric_id in self._active_metrics:
                metric = self._active_metrics[metric_id]
                
                if metric.status == TimerStatus.RUNNING:
                    metric.status = TimerStatus.TIMEOUT
                    metric.severity = TimerSeverity.CRITICAL
                    metric.error = f"Timeout after {timeout}s"
                    
                    # Move to completed
                    self._active_metrics.pop(metric_id)
                    self._completed_metrics.append(metric)
                    
                    if self.config.persist_metrics and self.pool:
                        await self._save_metric(metric)
                    
                    if self.config.alert_on_timeout:
                        await self._trigger_alert(metric)
                    
                    logger.warning(
                        f"Timer timeout: {self.name} [{metric.type.value}] "
                        f"timeout={timeout}s"
                    )
    
    # =========================================================================
    # CONTEXT MANAGER SUPPORT
    # =========================================================================
    
    async def __aenter__(self):
        """Enter async context."""
        self._start_time = time.time()
        self._status = TimerStatus.RUNNING
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        self._end_time = time.time()
        self._status = TimerStatus.COMPLETED
        
        duration_ms = (self._end_time - self._start_time) * 1000 if self._start_time else 0
        
        if exc_val:
            self._status = TimerStatus.ERROR
            logger.error(f"Timer {self.name} error: {exc_val}")
        
        logger.debug(f"Timer {self.name} completed: {duration_ms:.2f}ms")
    
    def __enter__(self):
        """Enter context."""
        self._start_time = time.time()
        self._status = TimerStatus.RUNNING
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        self._end_time = time.time()
        self._status = TimerStatus.COMPLETED
        
        duration_ms = (self._end_time - self._start_time) * 1000 if self._start_time else 0
        
        if exc_val:
            self._status = TimerStatus.ERROR
            logger.error(f"Timer {self.name} error: {exc_val}")
        
        logger.debug(f"Timer {self.name} completed: {duration_ms:.2f}ms")
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def _update_statistics(self, metric: TimerMetric):
        """
        Update statistics with a metric.
        
        Args:
            metric: Timer metric
        """
        key = f"{metric.type.value}:{metric.name}"
        
        if key not in self._statistics:
            self._statistics[key] = TimerStatistics(
                name=metric.name,
                type=metric.type
            )
        
        stats = self._statistics[key]
        stats.count += 1
        stats.total_ms += metric.duration_ms or 0
        
        if stats.min_ms == 0 or (metric.duration_ms and metric.duration_ms < stats.min_ms):
            stats.min_ms = metric.duration_ms or 0
        if metric.duration_ms and metric.duration_ms > stats.max_ms:
            stats.max_ms = metric.duration_ms
        
        # Track status counts
        if metric.status == TimerStatus.COMPLETED:
            stats.success_count += 1
        elif metric.status == TimerStatus.TIMEOUT:
            stats.timeout_count += 1
        elif metric.status == TimerStatus.ERROR:
            stats.error_count += 1
        
        if metric.is_slow:
            stats.slow_count += 1
        
        # Recalculate mean
        stats.mean_ms = stats.total_ms / stats.count if stats.count > 0 else 0
        
        # Update by type
        if metric.type.value not in self._stats_by_type:
            self._stats_by_type[metric.type.value] = TimerStatistics(
                name=metric.type.value,
                type=metric.type
            )
        
        type_stats = self._stats_by_type[metric.type.value]
        type_stats.count += 1
        type_stats.total_ms += metric.duration_ms or 0
        type_stats.mean_ms = type_stats.total_ms / type_stats.count if type_stats.count > 0 else 0
        
        # Update by name
        if metric.name not in self._stats_by_name:
            self._stats_by_name[metric.name] = TimerStatistics(
                name=metric.name,
                type=metric.type
            )
        
        name_stats = self._stats_by_name[metric.name]
        name_stats.count += 1
        name_stats.total_ms += metric.duration_ms or 0
        name_stats.mean_ms = name_stats.total_ms / name_stats.count if name_stats.count > 0 else 0
    
    async def get_statistics(
        self,
        metric_type: Optional[TimerMetricType] = None,
        name: Optional[str] = None
    ) -> Dict[str, TimerStatistics]:
        """
        Get timer statistics.
        
        Args:
            metric_type: Filter by type
            name: Filter by name
            
        Returns:
            Dict of statistics
        """
        async with self._lock:
            result = {}
            
            if metric_type and name:
                key = f"{metric_type.value}:{name}"
                if key in self._statistics:
                    result[key] = self._statistics[key]
            elif metric_type:
                for key, stats in self._statistics.items():
                    if stats.type == metric_type:
                        result[key] = stats
            elif name:
                for key, stats in self._statistics.items():
                    if stats.name == name:
                        result[key] = stats
            else:
                result = self._statistics.copy()
            
            return result
    
    async def get_metrics(
        self,
        status: Optional[TimerStatus] = None,
        severity: Optional[TimerSeverity] = None,
        limit: int = 100
    ) -> List[TimerMetric]:
        """
        Get timer metrics.
        
        Args:
            status: Filter by status
            severity: Filter by severity
            limit: Number of metrics to return
            
        Returns:
            List of timer metrics
        """
        async with self._lock:
            metrics = self._completed_metrics[-limit:]
            
            if status:
                metrics = [m for m in metrics if m.status == status]
            
            if severity:
                metrics = [m for m in metrics if m.severity == severity]
            
            return metrics
    
    async def get_snapshot(self) -> ExecutionTimerSnapshot:
        """
        Get a snapshot of the current timer state.
        
        Returns:
            ExecutionTimerSnapshot
        """
        async with self._lock:
            metrics = self._completed_metrics[-100:]
            active = len(self._active_metrics)
            
            # Calculate averages
            total_duration = sum(m.duration_ms or 0 for m in metrics)
            avg_duration = total_duration / len(metrics) if metrics else 0
            
            # Get slowest metrics
            slowest = sorted(
                metrics,
                key=lambda m: m.duration_ms or 0,
                reverse=True
            )[:10]
            
            return ExecutionTimerSnapshot(
                total_metrics=len(self._metrics),
                active_timers=active,
                completed_timers=len(self._completed_metrics),
                slow_timers=sum(1 for m in metrics if m.is_slow),
                timeout_timers=sum(1 for m in metrics if m.status == TimerStatus.TIMEOUT),
                error_timers=sum(1 for m in metrics if m.status == TimerStatus.ERROR),
                average_duration_ms=avg_duration,
                stats_by_type=self._stats_by_type.copy(),
                stats_by_name=self._stats_by_name.copy(),
                slowest_metrics=slowest,
                latest_metrics=metrics[-20:]
            )
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def on_alert(self, callback: Callable):
        """
        Register an alert callback.
        
        Args:
            callback: Alert callback function
        """
        self._alert_callbacks.append(callback)
    
    async def _trigger_alert(self, metric: TimerMetric):
        """
        Trigger an alert.
        
        Args:
            metric: Timer metric
        """
        if not self.config.alert_on_slow and metric.severity == TimerSeverity.WARNING:
            return
        
        if not self.config.alert_on_timeout and metric.status == TimerStatus.TIMEOUT:
            return
        
        if not self.config.alert_on_error and metric.status == TimerStatus.ERROR:
            return
        
        message = (
            f"Timer alert: {metric.name} [{metric.type.value}] "
            f"duration={metric.duration_ms:.2f}ms "
            f"severity={metric.severity.value}"
        )
        
        if metric.error:
            message += f" error={metric.error}"
        
        if metric.correlation_id:
            message += f" correlation={metric.correlation_id}"
        
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(metric, message)
                else:
                    callback(metric, message)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.warning(message)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_metric(self, metric: TimerMetric):
        """
        Save metric to database.
        
        Args:
            metric: Timer metric
        """
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO execution_timer_metrics (
                        id, name, type, severity, status,
                        start_time, end_time, duration_ms,
                        timeout_seconds, thread_id, task_id,
                        correlation_id, tags, metadata,
                        error, stack_trace, context
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16, $17)
                    """,
                    metric.id,
                    metric.name,
                    metric.type.value,
                    metric.severity.value,
                    metric.status.value,
                    metric.start_time,
                    metric.end_time,
                    metric.duration_ms,
                    metric.timeout_seconds,
                    metric.thread_id,
                    metric.task_id,
                    metric.correlation_id,
                    json.dumps(metric.tags),
                    json.dumps(metric.metadata, default=str),
                    metric.error,
                    metric.stack_trace,
                    json.dumps(metric.context, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving metric: {e}")
    
    async def _load_statistics(self):
        """Load statistics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM execution_timer_stats
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """
                )
                
                async with self._lock:
                    for row in rows:
                        stats = TimerStatistics(
                            name=row['name'],
                            type=TimerMetricType(row['type']),
                            count=row['count'],
                            min_ms=row['min_ms'],
                            max_ms=row['max_ms'],
                            mean_ms=row['mean_ms'],
                            median_ms=row['median_ms'],
                            p50_ms=row['p50_ms'],
                            p90_ms=row['p90_ms'],
                            p95_ms=row['p95_ms'],
                            p99_ms=row['p99_ms'],
                            std_dev_ms=row['std_dev_ms'],
                            total_ms=row['total_ms'],
                            slow_count=row['slow_count'],
                            timeout_count=row['timeout_count'],
                            error_count=row['error_count'],
                            success_count=row['success_count'],
                            timestamp=row['timestamp'],
                            window_seconds=row['window_seconds']
                        )
                        
                        key = f"{stats.type.value}:{stats.name}"
                        self._statistics[key] = stats
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
    
    async def _save_statistics(self):
        """Save statistics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for stats in self._statistics.values():
                        await conn.execute(
                            """
                            INSERT INTO execution_timer_stats (
                                name, type, count, min_ms, max_ms,
                                mean_ms, median_ms, p50_ms, p90_ms,
                                p95_ms, p99_ms, std_dev_ms, total_ms,
                                slow_count, timeout_count, error_count,
                                success_count, timestamp, window_seconds
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                                      $9, $10, $11, $12, $13, $14, $15,
                                      $16, $17, $18, $19)
                            ON CONFLICT (name, type, timestamp) DO UPDATE SET
                                count = EXCLUDED.count,
                                min_ms = EXCLUDED.min_ms,
                                max_ms = EXCLUDED.max_ms,
                                mean_ms = EXCLUDED.mean_ms,
                                median_ms = EXCLUDED.median_ms,
                                p50_ms = EXCLUDED.p50_ms,
                                p90_ms = EXCLUDED.p90_ms,
                                p95_ms = EXCLUDED.p95_ms,
                                p99_ms = EXCLUDED.p99_ms,
                                std_dev_ms = EXCLUDED.std_dev_ms,
                                total_ms = EXCLUDED.total_ms,
                                slow_count = EXCLUDED.slow_count,
                                timeout_count = EXCLUDED.timeout_count,
                                error_count = EXCLUDED.error_count,
                                success_count = EXCLUDED.success_count
                            """,
                            stats.name,
                            stats.type.value,
                            stats.count,
                            stats.min_ms,
                            stats.max_ms,
                            stats.mean_ms,
                            stats.median_ms,
                            stats.p50_ms,
                            stats.p90_ms,
                            stats.p95_ms,
                            stats.p99_ms,
                            stats.std_dev_ms,
                            stats.total_ms,
                            stats.slow_count,
                            stats.timeout_count,
                            stats.error_count,
                            stats.success_count,
                            stats.timestamp,
                            stats.window_seconds
                        )
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
    
    # =========================================================================
    # METRICS COLLECTION
    # =========================================================================
    
    async def _metrics_collection_loop(self):
        """Periodically collect and save metrics."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every 60 seconds
                
                if self.config.persist_metrics:
                    await self._save_statistics()
                
                # Clean up old metrics
                if self.redis:
                    for metric_id in list(self._metrics.keys()):
                        metric = self._metrics[metric_id]
                        if metric.status in [TimerStatus.COMPLETED, TimerStatus.TIMEOUT, TimerStatus.ERROR]:
                            age = (datetime.utcnow() - metric.end_time).total_seconds()
                            if age > self.config.metric_ttl:
                                self._metrics.pop(metric_id, None)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def reset(self):
        """Reset all timers and statistics."""
        async with self._lock:
            self._metrics.clear()
            self._active_metrics.clear()
            self._completed_metrics.clear()
            self._statistics.clear()
            self._stats_by_type.clear()
            self._stats_by_name.clear()
            
            logger.info(f"ExecutionTimer '{self.name}' reset")
    
    async def get_active_count(self) -> int:
        """Get number of active timers."""
        async with self._lock:
            return len(self._active_metrics)
    
    async def get_completed_count(self) -> int:
        """Get number of completed timers."""
        async with self._lock:
            return len(self._completed_metrics)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the execution timer."""
        self._running = False
        
        # Save final statistics
        if self.config.persist_metrics:
            await self._save_statistics()
        
        logger.info(f"ExecutionTimer '{self.name}' shutdown")


# =============================================================================
# DECORATOR
# =============================================================================

def timed(
    name: Optional[str] = None,
    metric_type: TimerMetricType = TimerMetricType.EXECUTION,
    timeout: Optional[float] = None,
    **kwargs
):
    """
    Decorator to time function execution.
    
    Args:
        name: Timer name
        metric_type: Metric type
        timeout: Timeout in seconds
        **kwargs: Additional arguments for timer
    
    Returns:
        Decorated function
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            timer_name = name or func.__name__
            timer = await get_timer()
            
            if timer and timer.config.enabled:
                metric_id = await timer.start(
                    metric_type=metric_type,
                    timeout=timeout,
                    tags=[timer_name],
                    metadata={"function": func.__name__}
                )
                
                try:
                    result = await func(*args, **kwargs)
                    await timer.stop(metric_id)
                    return result
                except Exception as e:
                    await timer.stop(metric_id, error=str(e))
                    raise
            else:
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# GLOBAL TIMER INSTANCE
# =============================================================================

_global_timer: Optional[ExecutionTimer] = None


async def get_timer(
    name: str = "global",
    config: Optional[ExecutionTimerConfig] = None,
    redis: Optional[Redis] = None,
    pool: Optional[asyncpg.Pool] = None
) -> ExecutionTimer:
    """
    Get or create global timer instance.
    
    Args:
        name: Timer name
        config: Timer configuration
        redis: Redis client
        pool: PostgreSQL connection pool
        
    Returns:
        ExecutionTimer instance
    """
    global _global_timer
    
    if _global_timer is None:
        _global_timer = ExecutionTimer(name, config, redis, pool)
        await _global_timer.initialize()
    
    return _global_timer


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ExecutionTimer',
    'TimerStatus',
    'TimerMetricType',
    'TimerSeverity',
    'ExecutionTimerConfig',
    'TimerMetric',
    'TimerStatistics',
    'ExecutionTimerSnapshot',
    'timed',
    'get_timer'
]
