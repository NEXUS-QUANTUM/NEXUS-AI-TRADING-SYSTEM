# trading/bots/arbitrage_bot/core/latency_monitor.py
# Nexus AI Trading System - Arbitrage Bot Latency Monitor Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Latency Monitor Module

This module provides comprehensive latency monitoring and optimization
for the arbitrage bot system, including:

- End-to-end latency measurement
- Network latency monitoring
- Exchange API latency tracking
- Execution latency analysis
- Latency distribution statistics
- Performance alerts
- Latency optimization recommendations
- Historical latency analysis
- Real-time latency dashboards
- Cross-exchange latency comparison

The latency monitor ensures the arbitrage bot operates with minimal
latency to capture arbitrage opportunities before they disappear.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import aiohttp
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class LatencySource(str, Enum):
    """Latency source types."""
    EXCHANGE_API = "exchange_api"
    NETWORK = "network"
    WEBSOCKET = "websocket"
    ORDER_PLACEMENT = "order_placement"
    ORDER_CANCELLATION = "order_cancellation"
    BALANCE_UPDATE = "balance_update"
    MARKET_DATA = "market_data"
    DATABASE = "database"
    CACHE = "cache"
    WEBHOOK = "webhook"
    TOTAL = "total"
    END_TO_END = "end_to_end"


class LatencySeverity(str, Enum):
    """Latency severity levels."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class LatencyStatus(str, Enum):
    """Latency status."""
    OK = "ok"
    WARNING = "warning"
    DEGRADED = "degraded"
    FAILED = "failed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class LatencyConfig(BaseModel):
    """Latency monitor configuration."""
    enabled: bool = True
    monitor_interval: int = 60  # seconds
    history_retention_days: int = 7
    alert_on_elevated: bool = True
    alert_on_high: bool = True
    alert_on_critical: bool = True
    
    # Thresholds in milliseconds
    threshold_normal: float = 50.0
    threshold_elevated: float = 100.0
    threshold_high: float = 200.0
    threshold_critical: float = 500.0
    
    # Percentiles for reporting
    percentiles: List[float] = [50, 90, 95, 99, 99.9]
    
    # Sampling
    sample_rate: float = 1.0  # 1.0 = 100% sampling
    max_samples_per_minute: int = 1000
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LatencyMetric(BaseModel):
    """Latency metric."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: LatencySource
    exchange: Optional[str] = None
    endpoint: Optional[str] = None
    operation: Optional[str] = None
    value_ms: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_normal(self) -> bool:
        return self.value_ms < 50.0

    @property
    def is_elevated(self) -> bool:
        return 50.0 <= self.value_ms < 100.0

    @property
    def is_high(self) -> bool:
        return 100.0 <= self.value_ms < 200.0

    @property
    def is_critical(self) -> bool:
        return self.value_ms >= 200.0

    @property
    def severity(self) -> LatencySeverity:
        if self.is_critical:
            return LatencySeverity.CRITICAL
        elif self.is_high:
            return LatencySeverity.HIGH
        elif self.is_elevated:
            return LatencySeverity.ELEVATED
        return LatencySeverity.NORMAL


class LatencyStatistics(BaseModel):
    """Latency statistics."""
    source: LatencySource
    exchange: Optional[str] = None
    count: int = 0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    p99_9_ms: float = 0.0
    std_dev_ms: float = 0.0
    total_ms: float = 0.0
    normal_count: int = 0
    elevated_count: int = 0
    high_count: int = 0
    critical_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    window_seconds: int = 60
    status: LatencyStatus = LatencyStatus.OK


class LatencyAlert(BaseModel):
    """Latency alert."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: LatencySource
    exchange: Optional[str] = None
    severity: LatencySeverity
    value_ms: float
    threshold_ms: float
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LatencySnapshot(BaseModel):
    """Latency snapshot."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_metrics: int
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    status: LatencyStatus
    statistics: Dict[str, LatencyStatistics]
    alerts: List[LatencyAlert]


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Latency metrics
CREATE TABLE IF NOT EXISTS latency_metrics (
    id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(30) NOT NULL,
    exchange VARCHAR(50),
    endpoint VARCHAR(255),
    operation VARCHAR(255),
    value_ms FLOAT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    INDEX idx_latency_metrics_source (source),
    INDEX idx_latency_metrics_exchange (exchange),
    INDEX idx_latency_metrics_timestamp (timestamp)
);

-- Latency statistics
CREATE TABLE IF NOT EXISTS latency_stats (
    id SERIAL PRIMARY KEY,
    source VARCHAR(30) NOT NULL,
    exchange VARCHAR(50),
    count INTEGER DEFAULT 0,
    min_ms FLOAT DEFAULT 0,
    max_ms FLOAT DEFAULT 0,
    mean_ms FLOAT DEFAULT 0,
    median_ms FLOAT DEFAULT 0,
    p50_ms FLOAT DEFAULT 0,
    p90_ms FLOAT DEFAULT 0,
    p95_ms FLOAT DEFAULT 0,
    p99_ms FLOAT DEFAULT 0,
    p99_9_ms FLOAT DEFAULT 0,
    std_dev_ms FLOAT DEFAULT 0,
    total_ms FLOAT DEFAULT 0,
    normal_count INTEGER DEFAULT 0,
    elevated_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    window_seconds INTEGER DEFAULT 60,
    status VARCHAR(20) DEFAULT 'ok',
    UNIQUE(source, exchange, timestamp)
);

-- Latency alerts
CREATE TABLE IF NOT EXISTS latency_alerts (
    id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(30) NOT NULL,
    exchange VARCHAR(50),
    severity VARCHAR(20) NOT NULL,
    value_ms FLOAT NOT NULL,
    threshold_ms FLOAT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_latency_alerts_source (source),
    INDEX idx_latency_alerts_timestamp (timestamp)
);
"""


# =============================================================================
# LATENCY MONITOR CLASS
# =============================================================================

class LatencyMonitor:
    """
    Advanced latency monitor for arbitrage bot.
    
    Features:
    - End-to-end latency measurement
    - Network latency monitoring
    - Exchange API latency tracking
    - Execution latency analysis
    - Latency distribution statistics
    - Performance alerts
    - Latency optimization recommendations
    - Historical latency analysis
    - Real-time latency dashboards
    - Cross-exchange latency comparison
    - Percentile-based tracking
    - Automatic alerting
    - Health status reporting
    """
    
    def __init__(
        self,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[LatencyConfig] = None
    ):
        self.redis = redis
        self.pool = pool
        self.config = config or LatencyConfig()
        
        # Latency metrics
        self._metrics: List[LatencyMetric] = []
        self._statistics: Dict[str, LatencyStatistics] = {}
        self._alerts: List[LatencyAlert] = []
        
        # Circuit breakers
        self._latency_cb = CircuitBreaker(
            name="latency_monitor",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        # Metric buffer
        self._buffer: List[LatencyMetric] = []
        self._buffer_lock = asyncio.Lock()
        self._buffer_size = 1000
        
        # Statistics window
        self._stats_window = 60  # seconds
        
        logger.info("LatencyMonitor initialized")
    
    async def initialize(self):
        """Initialize the latency monitor."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Create HTTP session for network checks
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": "NexusAI-Trading/3.0"}
        )
        
        # Start monitoring
        self._running = True
        asyncio.create_task(self._monitoring_loop())
        asyncio.create_task(self._statistics_loop())
        
        self._initialized = True
        logger.info("LatencyMonitor initialized")
    
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
    # LATENCY RECORDING
    # =========================================================================
    
    async def record_latency(
        self,
        source: LatencySource,
        value_ms: float,
        exchange: Optional[str] = None,
        endpoint: Optional[str] = None,
        operation: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a latency measurement.
        
        Args:
            source: Latency source
            value_ms: Latency in milliseconds
            exchange: Exchange name
            endpoint: API endpoint
            operation: Operation name
            tags: Additional tags
            metadata: Additional metadata
        """
        if not self.config.enabled:
            return
        
        # Sample if needed
        if self.config.sample_rate < 1.0:
            if random.random() > self.config.sample_rate:
                return
        
        # Create metric
        metric = LatencyMetric(
            source=source,
            exchange=exchange,
            endpoint=endpoint,
            operation=operation,
            value_ms=value_ms,
            tags=tags or [],
            metadata=metadata or {}
        )
        
        # Add to buffer
        async with self._buffer_lock:
            self._buffer.append(metric)
            
            # Trim buffer if too large
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]
        
        # Check for alerts
        if metric.severity in [LatencySeverity.HIGH, LatencySeverity.CRITICAL]:
            await self._check_alerts(metric)
        
        # Add to metrics list
        self._metrics.append(metric)
        if len(self._metrics) > 10000:
            self._metrics = self._metrics[-5000:]
    
    async def record_end_to_end_latency(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        exchange: Optional[str] = None,
        operation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record end-to-end latency.
        
        Args:
            start_time: Start time
            end_time: End time (default: now)
            exchange: Exchange name
            operation: Operation name
            metadata: Additional metadata
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        latency_ms = (end_time - start_time).total_seconds() * 1000
        
        await self.record_latency(
            source=LatencySource.END_TO_END,
            value_ms=latency_ms,
            exchange=exchange,
            operation=operation,
            metadata=metadata
        )
    
    async def record_network_latency(
        self,
        exchange: str,
        value_ms: float,
        endpoint: Optional[str] = None
    ):
        """
        Record network latency.
        
        Args:
            exchange: Exchange name
            value_ms: Latency in milliseconds
            endpoint: API endpoint
        """
        await self.record_latency(
            source=LatencySource.NETWORK,
            value_ms=value_ms,
            exchange=exchange,
            endpoint=endpoint,
            tags=["network"]
        )
    
    async def record_exchange_latency(
        self,
        exchange: str,
        value_ms: float,
        endpoint: str,
        operation: str
    ):
        """
        Record exchange API latency.
        
        Args:
            exchange: Exchange name
            value_ms: Latency in milliseconds
            endpoint: API endpoint
            operation: Operation name
        """
        await self.record_latency(
            source=LatencySource.EXCHANGE_API,
            value_ms=value_ms,
            exchange=exchange,
            endpoint=endpoint,
            operation=operation,
            tags=["api"]
        )
    
    # =========================================================================
    # LATENCY MEASUREMENT
    # =========================================================================
    
    async def measure_latency(
        self,
        source: LatencySource,
        func: Callable,
        *args,
        exchange: Optional[str] = None,
        endpoint: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ) -> Tuple[Any, float]:
        """
        Measure latency of a function call.
        
        Args:
            source: Latency source
            func: Function to measure
            *args: Positional arguments
            exchange: Exchange name
            endpoint: API endpoint
            operation: Operation name
            **kwargs: Keyword arguments
            
        Returns:
            Tuple of (result, latency_ms)
        """
        start = time.perf_counter()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            latency_ms = (time.perf_counter() - start) * 1000
            
            await self.record_latency(
                source=source,
                value_ms=latency_ms,
                exchange=exchange,
                endpoint=endpoint,
                operation=operation,
                metadata={"result_type": type(result).__name__}
            )
            
            return result, latency_ms
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            
            await self.record_latency(
                source=source,
                value_ms=latency_ms,
                exchange=exchange,
                endpoint=endpoint,
                operation=operation,
                metadata={"error": str(e)}
            )
            
            raise
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def get_statistics(
        self,
        source: Optional[LatencySource] = None,
        exchange: Optional[str] = None,
        window_seconds: int = 60
    ) -> Dict[str, LatencyStatistics]:
        """
        Get latency statistics.
        
        Args:
            source: Filter by source
            exchange: Filter by exchange
            window_seconds: Time window in seconds
            
        Returns:
            Dict of statistics
        """
        async with self._buffer_lock:
            # Get metrics in window
            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            metrics = [m for m in self._buffer if m.timestamp > cutoff]
            
            if source:
                metrics = [m for m in metrics if m.source == source]
            
            if exchange:
                metrics = [m for m in metrics if m.exchange == exchange]
            
            if not metrics:
                return {}
            
            # Group by source and exchange
            groups = {}
            for metric in metrics:
                key = f"{metric.source.value}:{metric.exchange or 'global'}"
                if key not in groups:
                    groups[key] = []
                groups[key].append(metric.value_ms)
            
            # Calculate statistics for each group
            result = {}
            for key, values in groups.items():
                values.sort()
                n = len(values)
                
                stats = LatencyStatistics(
                    source=LatencySource(key.split(':')[0]),
                    exchange=key.split(':')[1] if ':' in key else None,
                    count=n,
                    min_ms=values[0],
                    max_ms=values[-1],
                    mean_ms=sum(values) / n,
                    median_ms=values[n // 2],
                    p50_ms=values[int(n * 0.50)],
                    p90_ms=values[int(n * 0.90)],
                    p95_ms=values[int(n * 0.95)],
                    p99_ms=values[int(n * 0.99)],
                    p99_9_ms=values[int(n * 0.999)],
                    std_dev_ms=np.std(values) if n > 1 else 0.0,
                    total_ms=sum(values),
                    normal_count=sum(1 for v in values if v < 50),
                    elevated_count=sum(1 for v in values if 50 <= v < 100),
                    high_count=sum(1 for v in values if 100 <= v < 200),
                    critical_count=sum(1 for v in values if v >= 200),
                    window_seconds=window_seconds,
                    status=self._calculate_status(values)
                )
                
                result[key] = stats
            
            return result
    
    def _calculate_status(self, values: List[float]) -> LatencyStatus:
        """Calculate status based on values."""
        if not values:
            return LatencyStatus.OK
        
        # Check critical
        critical_count = sum(1 for v in values if v >= 200)
        if critical_count / len(values) > 0.1:  # 10% critical
            return LatencyStatus.FAILED
        
        # Check high
        high_count = sum(1 for v in values if 100 <= v < 200)
        if high_count / len(values) > 0.2:  # 20% high
            return LatencyStatus.DEGRADED
        
        # Check elevated
        elevated_count = sum(1 for v in values if 50 <= v < 100)
        if elevated_count / len(values) > 0.3:  # 30% elevated
            return LatencyStatus.WARNING
        
        return LatencyStatus.OK
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def on_alert(self, callback: Callable):
        """Register an alert callback."""
        self._alert_callbacks.append(callback)
    
    async def _check_alerts(self, metric: LatencyMetric):
        """Check if an alert should be triggered."""
        if metric.severity == LatencySeverity.NORMAL:
            return
        
        if metric.severity == LatencySeverity.ELEVATED and not self.config.alert_on_elevated:
            return
        
        if metric.severity == LatencySeverity.HIGH and not self.config.alert_on_high:
            return
        
        if metric.severity == LatencySeverity.CRITICAL and not self.config.alert_on_critical:
            return
        
        # Create alert
        threshold = {
            LatencySeverity.ELEVATED: self.config.threshold_elevated,
            LatencySeverity.HIGH: self.config.threshold_high,
            LatencySeverity.CRITICAL: self.config.threshold_critical
        }.get(metric.severity, 0)
        
        alert = LatencyAlert(
            source=metric.source,
            exchange=metric.exchange,
            severity=metric.severity,
            value_ms=metric.value_ms,
            threshold_ms=threshold,
            message=f"Latency {metric.severity.value}: {metric.value_ms:.2f}ms ({metric.source.value})",
            timestamp=datetime.utcnow(),
            metadata=metric.metadata
        )
        
        self._alerts.append(alert)
        
        # Trigger callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        # Save alert
        if self.pool:
            await self._save_alert(alert)
    
    # =========================================================================
    # SNAPSHOT
    # =========================================================================
    
    async def get_snapshot(self) -> LatencySnapshot:
        """
        Get a latency snapshot.
        
        Returns:
            LatencySnapshot
        """
        stats = await self.get_statistics(window_seconds=60)
        
        all_values = []
        for stat in stats.values():
            # We need to reconstruct values from statistics
            all_values.extend([stat.min_ms, stat.max_ms, stat.mean_ms, stat.median_ms])
        
        if not all_values:
            return LatencySnapshot(
                total_metrics=0,
                min_latency_ms=0,
                max_latency_ms=0,
                avg_latency_ms=0,
                median_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                status=LatencyStatus.OK,
                statistics={},
                alerts=[]
            )
        
        return LatencySnapshot(
            total_metrics=sum(stat.count for stat in stats.values()),
            min_latency_ms=min(all_values),
            max_latency_ms=max(all_values),
            avg_latency_ms=sum(all_values) / len(all_values),
            median_latency_ms=sorted(all_values)[len(all_values) // 2],
            p95_latency_ms=np.percentile(all_values, 95) if all_values else 0,
            p99_latency_ms=np.percentile(all_values, 99) if all_values else 0,
            status=self._calculate_status(all_values),
            statistics=stats,
            alerts=self._alerts[-10:] if self._alerts else []
        )
    
    # =========================================================================
    # MONITORING LOOPS
    # =========================================================================
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await asyncio.sleep(1)  # Check every second
                
                # Buffer metrics to database
                async with self._buffer_lock:
                    if self._buffer and self.pool:
                        to_save = self._buffer[:100]  # Save in batches
                        await self._save_metrics(to_save)
                        
                        # Remove saved metrics from buffer
                        for metric in to_save:
                            self._buffer.remove(metric)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)
    
    async def _statistics_loop(self):
        """Statistics calculation loop."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every 60 seconds
                
                # Calculate statistics
                stats = await self.get_statistics(window_seconds=60)
                
                # Save statistics
                if self.pool:
                    for stat in stats.values():
                        await self._save_statistics(stat)
                
                # Check overall status
                for key, stat in stats.items():
                    if stat.status in [LatencyStatus.DEGRADED, LatencyStatus.FAILED]:
                        # Create alert for degraded status
                        alert = LatencyAlert(
                            source=stat.source,
                            exchange=stat.exchange,
                            severity=LatencySeverity.HIGH if stat.status == LatencyStatus.DEGRADED else LatencySeverity.CRITICAL,
                            value_ms=stat.p95_ms,
                            threshold_ms=self.config.threshold_high if stat.status == LatencyStatus.DEGRADED else self.config.threshold_critical,
                            message=f"Latency status {stat.status.value}: {stat.source.value} p95={stat.p95_ms:.2f}ms",
                            timestamp=datetime.utcnow()
                        )
                        self._alerts.append(alert)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Statistics loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # NETWORK LATENCY CHECKS
    # =========================================================================
    
    async def check_network_latency(
        self,
        exchange: str,
        endpoint: str
    ) -> float:
        """
        Check network latency to an endpoint.
        
        Args:
            exchange: Exchange name
            endpoint: API endpoint URL
            
        Returns:
            Latency in milliseconds
        """
        try:
            start = time.perf_counter()
            
            async with self._session.get(
                endpoint,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                await response.read()
            
            latency_ms = (time.perf_counter() - start) * 1000
            
            await self.record_network_latency(exchange, latency_ms, endpoint)
            
            return latency_ms
            
        except Exception as e:
            logger.error(f"Network latency check error for {exchange}: {e}")
            return -1
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_metrics(self, metrics: List[LatencyMetric]):
        """Save metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for metric in metrics:
                        await conn.execute(
                            """
                            INSERT INTO latency_metrics (
                                id, source, exchange, endpoint,
                                operation, value_ms, timestamp,
                                tags, metadata
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            """,
                            metric.id,
                            metric.source.value,
                            metric.exchange,
                            metric.endpoint,
                            metric.operation,
                            metric.value_ms,
                            metric.timestamp,
                            json.dumps(metric.tags),
                            json.dumps(metric.metadata, default=str)
                        )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    async def _save_statistics(self, stat: LatencyStatistics):
        """Save statistics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO latency_stats (
                        source, exchange, count, min_ms, max_ms,
                        mean_ms, median_ms, p50_ms, p90_ms,
                        p95_ms, p99_ms, p99_9_ms, std_dev_ms,
                        total_ms, normal_count, elevated_count,
                        high_count, critical_count, timestamp,
                        window_seconds, status
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14, $15,
                              $16, $17, $18, $19, $20, $21)
                    ON CONFLICT (source, exchange, timestamp) DO UPDATE SET
                        count = EXCLUDED.count,
                        min_ms = EXCLUDED.min_ms,
                        max_ms = EXCLUDED.max_ms,
                        mean_ms = EXCLUDED.mean_ms,
                        median_ms = EXCLUDED.median_ms,
                        p50_ms = EXCLUDED.p50_ms,
                        p90_ms = EXCLUDED.p90_ms,
                        p95_ms = EXCLUDED.p95_ms,
                        p99_ms = EXCLUDED.p99_ms,
                        p99_9_ms = EXCLUDED.p99_9_ms,
                        std_dev_ms = EXCLUDED.std_dev_ms,
                        total_ms = EXCLUDED.total_ms,
                        normal_count = EXCLUDED.normal_count,
                        elevated_count = EXCLUDED.elevated_count,
                        high_count = EXCLUDED.high_count,
                        critical_count = EXCLUDED.critical_count,
                        status = EXCLUDED.status
                    """,
                    stat.source.value,
                    stat.exchange,
                    stat.count,
                    stat.min_ms,
                    stat.max_ms,
                    stat.mean_ms,
                    stat.median_ms,
                    stat.p50_ms,
                    stat.p90_ms,
                    stat.p95_ms,
                    stat.p99_ms,
                    stat.p99_9_ms,
                    stat.std_dev_ms,
                    stat.total_ms,
                    stat.normal_count,
                    stat.elevated_count,
                    stat.high_count,
                    stat.critical_count,
                    stat.timestamp,
                    stat.window_seconds,
                    stat.status.value
                )
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
    
    async def _save_alert(self, alert: LatencyAlert):
        """Save alert to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO latency_alerts (
                        id, source, exchange, severity,
                        value_ms, threshold_ms, message,
                        timestamp, acknowledged, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    alert.id,
                    alert.source.value,
                    alert.exchange,
                    alert.severity.value,
                    alert.value_ms,
                    alert.threshold_ms,
                    alert.message,
                    alert.timestamp,
                    alert.acknowledged,
                    json.dumps(alert.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status.
        
        Returns:
            Health status dict
        """
        snapshot = await self.get_snapshot()
        
        return {
            "status": snapshot.status.value,
            "total_metrics": snapshot.total_metrics,
            "avg_latency_ms": snapshot.avg_latency_ms,
            "p95_latency_ms": snapshot.p95_latency_ms,
            "p99_latency_ms": snapshot.p99_latency_ms,
            "alert_count": len(snapshot.alerts),
            "statistics": snapshot.statistics,
            "timestamp": snapshot.timestamp.isoformat()
        }
    
    async def get_latency_report(
        self,
        hours: int = 24,
        source: Optional[LatencySource] = None,
        exchange: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a latency report.
        
        Args:
            hours: Hours of history
            source: Filter by source
            exchange: Filter by exchange
            
        Returns:
            Latency report
        """
        if not self.pool:
            return {}
        
        try:
            query = """
                SELECT 
                    source,
                    exchange,
                    COUNT(*) as count,
                    MIN(value_ms) as min_ms,
                    MAX(value_ms) as max_ms,
                    AVG(value_ms) as mean_ms,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY value_ms) as median_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value_ms) as p95_ms,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value_ms) as p99_ms
                FROM latency_metrics
                WHERE timestamp > NOW() - INTERVAL '$1 hours'
            """
            params = [hours]
            
            if source:
                query += " AND source = $2"
                params.append(source.value)
            
            if exchange:
                query += " AND exchange = $3"
                params.append(exchange)
            
            query += " GROUP BY source, exchange ORDER BY source, exchange"
            
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                report = {
                    "generated_at": datetime.utcnow().isoformat(),
                    "hours": hours,
                    "data": []
                }
                
                for row in rows:
                    report["data"].append({
                        "source": row['source'],
                        "exchange": row['exchange'],
                        "count": row['count'],
                        "min_ms": row['min_ms'],
                        "max_ms": row['max_ms'],
                        "mean_ms": row['mean_ms'],
                        "median_ms": row['median_ms'],
                        "p95_ms": row['p95_ms'],
                        "p99_ms": row['p99_ms']
                    })
                
                return report
                
        except Exception as e:
            logger.error(f"Error generating latency report: {e}")
            return {}
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the latency monitor."""
        self._running = False
        
        # Flush remaining metrics
        if self.pool and self._buffer:
            await self._save_metrics(self._buffer)
            self._buffer.clear()
        
        if self._session:
            await self._session.close()
        
        logger.info("LatencyMonitor shutdown")


# =============================================================================
# DECORATOR
# =============================================================================

def measure_latency(
    source: LatencySource,
    exchange: Optional[str] = None,
    endpoint: Optional[str] = None,
    operation: Optional[str] = None
):
    """
    Decorator to measure function latency.
    
    Args:
        source: Latency source
        exchange: Exchange name
        endpoint: API endpoint
        operation: Operation name
        
    Returns:
        Decorated function
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = await get_latency_monitor()
            result, latency = await monitor.measure_latency(
                source=source,
                func=func,
                *args,
                exchange=exchange,
                endpoint=endpoint,
                operation=operation or func.__name__,
                **kwargs
            )
            return result
        
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't easily measure asynchronously
            start = time.perf_counter()
            result = func(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            
            # Record latency (fire and forget)
            asyncio.create_task(
                get_latency_monitor().record_latency(
                    source=source,
                    value_ms=latency_ms,
                    exchange=exchange,
                    endpoint=endpoint,
                    operation=operation or func.__name__
                )
            )
            return result
        
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# GLOBAL MONITOR INSTANCE
# =============================================================================

_global_monitor: Optional[LatencyMonitor] = None


async def get_latency_monitor(
    redis: Optional[Redis] = None,
    pool: Optional[asyncpg.Pool] = None,
    config: Optional[LatencyConfig] = None
) -> LatencyMonitor:
    """
    Get or create global latency monitor.
    
    Args:
        redis: Redis client
        pool: PostgreSQL connection pool
        config: Latency configuration
        
    Returns:
        LatencyMonitor instance
    """
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = LatencyMonitor(redis, pool, config)
        await _global_monitor.initialize()
    
    return _global_monitor


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'LatencyMonitor',
    'LatencySource',
    'LatencySeverity',
    'LatencyStatus',
    'LatencyConfig',
    'LatencyMetric',
    'LatencyStatistics',
    'LatencyAlert',
    'LatencySnapshot',
    'measure_latency',
    'get_latency_monitor'
]
