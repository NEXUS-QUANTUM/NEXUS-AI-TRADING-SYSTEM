# trading/bots/arbitrage_bot/models/latency.py
# NEXUS AI TRADING SYSTEM - LATENCY MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for latency tracking, performance monitoring,
# and network optimization for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Latency Models

This module provides comprehensive data models for:
- Network latency measurement and tracking
- Exchange API latency monitoring
- Order execution latency analysis
- WebSocket latency optimization
- Geographic latency optimization
- Latency-based routing decisions
- Performance benchmarking
- SLA compliance monitoring
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from collections import deque

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class LatencyType(str, Enum):
    """Types of latency measurements."""
    NETWORK = "network"          # Network round-trip time
    API = "api"                  # API request latency
    ORDER = "order"              # Order execution latency
    WEBSOCKET = "websocket"      # WebSocket message latency
    DATABASE = "database"        # Database query latency
    CACHE = "cache"              # Cache operation latency
    CALCULATION = "calculation"  # Calculation/processing latency
    TOTAL = "total"              # Total end-to-end latency
    SETTLEMENT = "settlement"    # Settlement/confirmation latency
    GATEWAY = "gateway"          # Gateway/proxy latency
    DNS = "dns"                  # DNS resolution latency
    SSL = "ssl"                  # SSL handshake latency
    TCP = "tcp"                  # TCP connection latency


class LatencyPercentile(str, Enum):
    """Standard latency percentiles."""
    P50 = "p50"
    P90 = "p90"
    P95 = "p95"
    P99 = "p99"
    P999 = "p999"
    P100 = "p100"


class LatencyStatus(str, Enum):
    """Latency status indicators."""
    EXCELLENT = "excellent"      # < 10ms
    GOOD = "good"                # 10-50ms
    ACCEPTABLE = "acceptable"    # 50-100ms
    HIGH = "high"                # 100-500ms
    CRITICAL = "critical"        # > 500ms
    TIMEOUT = "timeout"          # Request timed out


class Region(str, Enum):
    """Geographic regions for latency optimization."""
    US_EAST = "us-east"
    US_WEST = "us-west"
    US_CENTRAL = "us-central"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    EU_EAST = "eu-east"
    ASIA_SOUTH = "asia-south"
    ASIA_EAST = "asia-east"
    ASIA_SOUTHEAST = "asia-southeast"
    OCEANIA = "oceania"
    SOUTH_AMERICA = "south-america"
    AFRICA = "africa"
    MIDDLE_EAST = "middle-east"


# ====================================================================================
# LATENCY MEASUREMENT MODELS
# ====================================================================================

@dataclass
class LatencyMeasurement:
    """
    Single latency measurement.
    """
    # Core fields
    measurement_id: str = field(default_factory=lambda: str(uuid4()))
    type: LatencyType = LatencyType.API
    value_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Source information
    source: str = ""           # Service/component name
    source_region: Region = Region.US_EAST
    target: str = ""           # Target service/exchange
    target_region: Optional[Region] = None
    
    # Request information
    endpoint: str = ""
    method: str = "GET"
    request_size_bytes: int = 0
    response_size_bytes: int = 0
    
    # Status
    success: bool = True
    status_code: int = 200
    error_message: str = ""
    
    # Network metrics
    dns_time_ms: float = 0.0
    connect_time_ms: float = 0.0
    ssl_time_ms: float = 0.0
    first_byte_time_ms: float = 0.0
    transfer_time_ms: float = 0.0
    
    # Additional metrics
    server_processing_time_ms: float = 0.0
    queuing_time_ms: float = 0.0
    retry_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "measurement_id": self.measurement_id,
            "type": self.type.value if self.type else None,
            "value_ms": self.value_ms,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "source_region": self.source_region.value if self.source_region else None,
            "target": self.target,
            "target_region": self.target_region.value if self.target_region else None,
            "endpoint": self.endpoint,
            "method": self.method,
            "request_size_bytes": self.request_size_bytes,
            "response_size_bytes": self.response_size_bytes,
            "success": self.success,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "dns_time_ms": self.dns_time_ms,
            "connect_time_ms": self.connect_time_ms,
            "ssl_time_ms": self.ssl_time_ms,
            "first_byte_time_ms": self.first_byte_time_ms,
            "transfer_time_ms": self.transfer_time_ms,
            "server_processing_time_ms": self.server_processing_time_ms,
            "queuing_time_ms": self.queuing_time_ms,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LatencyMeasurement":
        """Create from dictionary."""
        measurement = cls(
            measurement_id=data.get("measurement_id", str(uuid4())),
            type=LatencyType(data["type"]) if data.get("type") else LatencyType.API,
            value_ms=data.get("value_ms", 0.0),
            source=data.get("source", ""),
            source_region=Region(data["source_region"]) if data.get("source_region") else Region.US_EAST,
            target=data.get("target", ""),
            target_region=Region(data["target_region"]) if data.get("target_region") else None,
            endpoint=data.get("endpoint", ""),
            method=data.get("method", "GET"),
            request_size_bytes=data.get("request_size_bytes", 0),
            response_size_bytes=data.get("response_size_bytes", 0),
            success=data.get("success", True),
            status_code=data.get("status_code", 200),
            error_message=data.get("error_message", ""),
            dns_time_ms=data.get("dns_time_ms", 0.0),
            connect_time_ms=data.get("connect_time_ms", 0.0),
            ssl_time_ms=data.get("ssl_time_ms", 0.0),
            first_byte_time_ms=data.get("first_byte_time_ms", 0.0),
            transfer_time_ms=data.get("transfer_time_ms", 0.0),
            server_processing_time_ms=data.get("server_processing_time_ms", 0.0),
            queuing_time_ms=data.get("queuing_time_ms", 0.0),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            measurement.timestamp = datetime.fromisoformat(data["timestamp"])
            
        # Calculate total if not set
        if measurement.value_ms == 0:
            measurement.value_ms = sum([
                measurement.dns_time_ms,
                measurement.connect_time_ms,
                measurement.ssl_time_ms,
                measurement.first_byte_time_ms,
                measurement.transfer_time_ms,
                measurement.server_processing_time_ms,
                measurement.queuing_time_ms
            ])
            
        return measurement
        
    def get_status(self) -> LatencyStatus:
        """Get latency status based on value."""
        if self.value_ms < 10:
            return LatencyStatus.EXCELLENT
        elif self.value_ms < 50:
            return LatencyStatus.GOOD
        elif self.value_ms < 100:
            return LatencyStatus.ACCEPTABLE
        elif self.value_ms < 500:
            return LatencyStatus.HIGH
        else:
            return LatencyStatus.CRITICAL
            
    def get_breakdown(self) -> Dict[str, float]:
        """Get latency breakdown components."""
        return {
            "dns": self.dns_time_ms,
            "connect": self.connect_time_ms,
            "ssl": self.ssl_time_ms,
            "first_byte": self.first_byte_time_ms,
            "transfer": self.transfer_time_ms,
            "server_processing": self.server_processing_time_ms,
            "queuing": self.queuing_time_ms
        }


# ====================================================================================
# LATENCY STATISTICS MODELS
# ====================================================================================

@dataclass
class LatencyStatistics:
    """
    Statistical analysis of latency measurements.
    """
    # Core fields
    statistic_id: str = field(default_factory=lambda: str(uuid4()))
    type: LatencyType = LatencyType.API
    source: str = ""
    target: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Sample size
    total_samples: int = 0
    successful_samples: int = 0
    failed_samples: int = 0
    timeout_samples: int = 0
    
    # Basic statistics
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    std_dev_ms: float = 0.0
    variance_ms: float = 0.0
    
    # Percentiles
    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    p999_ms: float = 0.0
    
    # Distribution
    distribution: Dict[str, int] = field(default_factory=dict)  # buckets -> count
    
    # Trend
    trend: str = "stable"  # increasing, decreasing, stable
    trend_rate: float = 0.0  # ms per hour
    
    # Status
    current_status: LatencyStatus = LatencyStatus.GOOD
    status_changes: int = 0
    last_status_change: Optional[datetime] = None
    
    # SLA compliance
    sla_threshold_ms: float = 100.0
    sla_compliance: float = 100.0  # percentage
    sla_breaches: int = 0
    last_sla_breach: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "statistic_id": self.statistic_id,
            "type": self.type.value if self.type else None,
            "source": self.source,
            "target": self.target,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_samples": self.total_samples,
            "successful_samples": self.successful_samples,
            "failed_samples": self.failed_samples,
            "timeout_samples": self.timeout_samples,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "mean_ms": self.mean_ms,
            "median_ms": self.median_ms,
            "std_dev_ms": self.std_dev_ms,
            "variance_ms": self.variance_ms,
            "p50_ms": self.p50_ms,
            "p90_ms": self.p90_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "p999_ms": self.p999_ms,
            "distribution": self.distribution,
            "trend": self.trend,
            "trend_rate": self.trend_rate,
            "current_status": self.current_status.value if self.current_status else None,
            "status_changes": self.status_changes,
            "last_status_change": self.last_status_change.isoformat() if self.last_status_change else None,
            "sla_threshold_ms": self.sla_threshold_ms,
            "sla_compliance": self.sla_compliance,
            "sla_breaches": self.sla_breaches,
            "last_sla_breach": self.last_sla_breach.isoformat() if self.last_sla_breach else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LatencyStatistics":
        """Create from dictionary."""
        stats = cls(
            statistic_id=data.get("statistic_id", str(uuid4())),
            type=LatencyType(data["type"]) if data.get("type") else LatencyType.API,
            source=data.get("source", ""),
            target=data.get("target", ""),
            total_samples=data.get("total_samples", 0),
            successful_samples=data.get("successful_samples", 0),
            failed_samples=data.get("failed_samples", 0),
            timeout_samples=data.get("timeout_samples", 0),
            min_ms=data.get("min_ms", 0.0),
            max_ms=data.get("max_ms", 0.0),
            mean_ms=data.get("mean_ms", 0.0),
            median_ms=data.get("median_ms", 0.0),
            std_dev_ms=data.get("std_dev_ms", 0.0),
            variance_ms=data.get("variance_ms", 0.0),
            p50_ms=data.get("p50_ms", 0.0),
            p90_ms=data.get("p90_ms", 0.0),
            p95_ms=data.get("p95_ms", 0.0),
            p99_ms=data.get("p99_ms", 0.0),
            p999_ms=data.get("p999_ms", 0.0),
            distribution=data.get("distribution", {}),
            trend=data.get("trend", "stable"),
            trend_rate=data.get("trend_rate", 0.0),
            current_status=LatencyStatus(data["current_status"]) if data.get("current_status") else LatencyStatus.GOOD,
            status_changes=data.get("status_changes", 0),
            sla_threshold_ms=data.get("sla_threshold_ms", 100.0),
            sla_compliance=data.get("sla_compliance", 100.0),
            sla_breaches=data.get("sla_breaches", 0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("period_start"):
            stats.period_start = datetime.fromisoformat(data["period_start"])
        if data.get("period_end"):
            stats.period_end = datetime.fromisoformat(data["period_end"])
        if data.get("last_status_change"):
            stats.last_status_change = datetime.fromisoformat(data["last_status_change"])
        if data.get("last_sla_breach"):
            stats.last_sla_breach = datetime.fromisoformat(data["last_sla_breach"])
            
        return stats
        
    def add_measurement(self, measurement: LatencyMeasurement) -> None:
        """
        Add a measurement to the statistics.
        
        Args:
            measurement: Latency measurement
        """
        self.total_samples += 1
        if measurement.success:
            self.successful_samples += 1
        else:
            self.failed_samples += 1
            if measurement.status_code == 408:
                self.timeout_samples += 1
                
        # Update min/max
        if self.min_ms == 0 or measurement.value_ms < self.min_ms:
            self.min_ms = measurement.value_ms
        if measurement.value_ms > self.max_ms:
            self.max_ms = measurement.value_ms
            
        # Check SLA
        if measurement.value_ms > self.sla_threshold_ms:
            self.sla_breaches += 1
            self.last_sla_breach = datetime.utcnow()
            
        self.sla_compliance = ((self.total_samples - self.sla_breaches) / self.total_samples * 100) if self.total_samples > 0 else 100.0
        
    def calculate_percentiles(self, values: List[float]) -> None:
        """
        Calculate percentiles from values.
        
        Args:
            values: List of latency values
        """
        if not values:
            return
            
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        self.p50_ms = self._percentile(sorted_values, 50)
        self.p90_ms = self._percentile(sorted_values, 90)
        self.p95_ms = self._percentile(sorted_values, 95)
        self.p99_ms = self._percentile(sorted_values, 99)
        self.p999_ms = self._percentile(sorted_values, 99.9)
        
        # Calculate mean and median
        self.mean_ms = sum(values) / n
        self.median_ms = self.p50_ms
        
        # Calculate standard deviation
        variance = sum((x - self.mean_ms) ** 2 for x in values) / n
        self.std_dev_ms = math.sqrt(variance)
        self.variance_ms = variance
        
    def _percentile(self, sorted_values: List[float], percentile: float) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
            
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        if index == int(index):
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            fraction = index - int(index)
            return lower + (upper - lower) * fraction
            
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of latency status."""
        return {
            "current_status": self.current_status.value if self.current_status else None,
            "sla_compliance": self.sla_compliance,
            "sla_breaches": self.sla_breaches,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "trend": self.trend,
            "trend_rate": self.trend_rate
        }


# ====================================================================================
# LATENCY OPTIMIZATION MODELS
# ====================================================================================

@dataclass
class LatencyOptimization:
    """
    Latency optimization configuration and recommendations.
    """
    # Core fields
    optimization_id: str = field(default_factory=lambda: str(uuid4()))
    target: str = ""  # Exchange/service name
    type: LatencyType = LatencyType.API
    region: Region = Region.US_EAST
    
    # Current performance
    current_latency_ms: float = 0.0
    target_latency_ms: float = 0.0
    latency_gap_ms: float = 0.0
    
    # Optimization strategies
    strategies: List[Dict[str, Any]] = field(default_factory=list)
    active_strategies: List[str] = field(default_factory=list)
    recommended_strategies: List[str] = field(default_factory=list)
    
    # Cost-benefit analysis
    implementation_cost: float = 0.0
    expected_improvement_ms: float = 0.0
    expected_improvement_percentage: float = 0.0
    roi: float = 0.0
    
    # Geographic optimization
    nearest_region: Region = Region.US_EAST
    region_latencies: Dict[str, float] = field(default_factory=dict)
    region_recommendations: Dict[str, str] = field(default_factory=dict)
    
    # Network optimization
    use_http2: bool = False
    use_websocket: bool = False
    use_keepalive: bool = False
    use_compression: bool = False
    use_caching: bool = False
    
    # Provider optimization
    best_provider: str = ""
    provider_latencies: Dict[str, float] = field(default_factory=dict)
    provider_recommendations: Dict[str, str] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_optimization: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimization_id": self.optimization_id,
            "target": self.target,
            "type": self.type.value if self.type else None,
            "region": self.region.value if self.region else None,
            "current_latency_ms": self.current_latency_ms,
            "target_latency_ms": self.target_latency_ms,
            "latency_gap_ms": self.latency_gap_ms,
            "strategies": self.strategies,
            "active_strategies": self.active_strategies,
            "recommended_strategies": self.recommended_strategies,
            "implementation_cost": self.implementation_cost,
            "expected_improvement_ms": self.expected_improvement_ms,
            "expected_improvement_percentage": self.expected_improvement_percentage,
            "roi": self.roi,
            "nearest_region": self.nearest_region.value if self.nearest_region else None,
            "region_latencies": self.region_latencies,
            "region_recommendations": self.region_recommendations,
            "use_http2": self.use_http2,
            "use_websocket": self.use_websocket,
            "use_keepalive": self.use_keepalive,
            "use_compression": self.use_compression,
            "use_caching": self.use_caching,
            "best_provider": self.best_provider,
            "provider_latencies": self.provider_latencies,
            "provider_recommendations": self.provider_recommendations,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_optimization": self.last_optimization.isoformat() if self.last_optimization else None,
            "metadata": self.metadata
        }


# ====================================================================================
# LATENCY ALERT MODELS
# ====================================================================================

@dataclass
class LatencyAlert:
    """
    Alert for latency issues.
    """
    # Core fields
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    type: LatencyType = LatencyType.API
    target: str = ""
    region: Region = Region.US_EAST
    
    # Alert conditions
    threshold_ms: float = 0.0
    current_latency_ms: float = 0.0
    duration_seconds: int = 0
    
    # Severity
    severity: str = "warning"  # warning, critical
    status: str = "active"  # active, resolved, acknowledged
    
    # Metrics
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    breach_count: int = 0
    first_breach: Optional[datetime] = None
    last_breach: Optional[datetime] = None
    
    # Resolution
    resolved_at: Optional[datetime] = None
    resolution_message: str = ""
    auto_resolved: bool = False
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "type": self.type.value if self.type else None,
            "target": self.target,
            "region": self.region.value if self.region else None,
            "threshold_ms": self.threshold_ms,
            "current_latency_ms": self.current_latency_ms,
            "duration_seconds": self.duration_seconds,
            "severity": self.severity,
            "status": self.status,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "breach_count": self.breach_count,
            "first_breach": self.first_breach.isoformat() if self.first_breach else None,
            "last_breach": self.last_breach.isoformat() if self.last_breach else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_message": self.resolution_message,
            "auto_resolved": self.auto_resolved,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


# ====================================================================================
# LATENCY COMPARISON MODELS
# ====================================================================================

@dataclass
class LatencyComparison:
    """
    Comparison of latency across different endpoints or providers.
    """
    # Core fields
    comparison_id: str = field(default_factory=lambda: str(uuid4()))
    source: str = ""
    targets: List[str] = field(default_factory=list)
    type: LatencyType = LatencyType.API
    
    # Latency data
    target_latencies: Dict[str, float] = field(default_factory=dict)
    target_p95_latencies: Dict[str, float] = field(default_factory=dict)
    target_p99_latencies: Dict[str, float] = field(default_factory=dict)
    
    # Rankings
    best_target: str = ""
    best_latency_ms: float = 0.0
    worst_target: str = ""
    worst_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    median_latency_ms: float = 0.0
    
    # Improvement potential
    max_improvement_ms: float = 0.0
    max_improvement_percentage: float = 0.0
    
    # Regional data
    regional_latencies: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Timestamps
    compared_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "source": self.source,
            "targets": self.targets,
            "type": self.type.value if self.type else None,
            "target_latencies": self.target_latencies,
            "target_p95_latencies": self.target_p95_latencies,
            "target_p99_latencies": self.target_p99_latencies,
            "best_target": self.best_target,
            "best_latency_ms": self.best_latency_ms,
            "worst_target": self.worst_target,
            "worst_latency_ms": self.worst_latency_ms,
            "average_latency_ms": self.average_latency_ms,
            "median_latency_ms": self.median_latency_ms,
            "max_improvement_ms": self.max_improvement_ms,
            "max_improvement_percentage": self.max_improvement_percentage,
            "regional_latencies": self.regional_latencies,
            "compared_at": self.compared_at.isoformat(),
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_weighted_latency(
    latencies: List[float],
    weights: Optional[List[float]] = None
) -> float:
    """
    Calculate weighted average latency.
    
    Args:
        latencies: List of latency values
        weights: List of weights (defaults to equal weights)
        
    Returns:
        Weighted average latency
    """
    if not latencies:
        return 0.0
        
    if weights is None:
        return sum(latencies) / len(latencies)
        
    if len(latencies) != len(weights):
        raise ValueError("Latencies and weights must have same length")
        
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
        
    return sum(l * w for l, w in zip(latencies, weights)) / total_weight


def calculate_latency_percentiles(values: List[float]) -> Dict[str, float]:
    """
    Calculate standard latency percentiles.
    
    Args:
        values: List of latency values
        
    Returns:
        Dict of percentile -> value
    """
    if not values:
        return {p: 0.0 for p in ['p50', 'p90', 'p95', 'p99', 'p999']}
        
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    def percentile(p: float) -> float:
        index = (p / 100.0) * (n - 1)
        if index == int(index):
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            fraction = index - int(index)
            return lower + (upper - lower) * fraction
            
    return {
        'p50': percentile(50),
        'p90': percentile(90),
        'p95': percentile(95),
        'p99': percentile(99),
        'p999': percentile(99.9)
    }


def get_latency_status(value_ms: float) -> LatencyStatus:
    """
    Get latency status based on value.
    
    Args:
        value_ms: Latency value in milliseconds
        
    Returns:
        LatencyStatus
    """
    if value_ms < 10:
        return LatencyStatus.EXCELLENT
    elif value_ms < 50:
        return LatencyStatus.GOOD
    elif value_ms < 100:
        return LatencyStatus.ACCEPTABLE
    elif value_ms < 500:
        return LatencyStatus.HIGH
    else:
        return LatencyStatus.CRITICAL


def calculate_latency_budget(
    total_budget_ms: float,
    components: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate latency budget allocation across components.
    
    Args:
        total_budget_ms: Total latency budget
        components: Dict of component -> weight
        
    Returns:
        Dict of component -> allocated budget
    """
    total_weight = sum(components.values())
    if total_weight == 0:
        return {k: 0.0 for k in components}
        
    return {k: (v / total_weight) * total_budget_ms for k, v in components.items()}


def calculate_geographic_latency(
    source_region: Region,
    target_region: Region
) -> float:
    """
    Calculate estimated geographic latency between regions.
    
    Args:
        source_region: Source region
        target_region: Target region
        
    Returns:
        Estimated latency in milliseconds
    """
    # Approximate latency matrix (in ms)
    latency_matrix = {
        (Region.US_EAST, Region.US_WEST): 70,
        (Region.US_EAST, Region.EU_WEST): 85,
        (Region.US_EAST, Region.EU_CENTRAL): 90,
        (Region.US_EAST, Region.ASIA_EAST): 200,
        (Region.US_EAST, Region.ASIA_SOUTHEAST): 220,
        (Region.US_EAST, Region.OCEANIA): 230,
        (Region.US_WEST, Region.EU_WEST): 140,
        (Region.US_WEST, Region.EU_CENTRAL): 145,
        (Region.US_WEST, Region.ASIA_EAST): 150,
        (Region.US_WEST, Region.ASIA_SOUTHEAST): 170,
        (Region.US_WEST, Region.OCEANIA): 160,
        (Region.EU_WEST, Region.ASIA_EAST): 200,
        (Region.EU_WEST, Region.ASIA_SOUTHEAST): 220,
        (Region.EU_WEST, Region.OCEANIA): 250,
    }
    
    key = (source_region, target_region)
    reverse_key = (target_region, source_region)
    
    if key in latency_matrix:
        return latency_matrix[key]
    elif reverse_key in latency_matrix:
        return latency_matrix[reverse_key]
    else:
        # Default estimate
        return 200.0


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'LatencyType',
    'LatencyPercentile',
    'LatencyStatus',
    'Region',
    
    # Core Models
    'LatencyMeasurement',
    'LatencyStatistics',
    'LatencyOptimization',
    'LatencyAlert',
    'LatencyComparison',
    
    # Helper Functions
    'calculate_weighted_latency',
    'calculate_latency_percentiles',
    'get_latency_status',
    'calculate_latency_budget',
    'calculate_geographic_latency',
]
