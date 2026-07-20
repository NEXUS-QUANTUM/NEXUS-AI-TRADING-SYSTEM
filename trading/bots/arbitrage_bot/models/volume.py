# trading/bots/arbitrage_bot/models/volume.py
# NEXUS AI TRADING SYSTEM - VOLUME MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for volume analysis, tracking,
# prediction, and optimization for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Volume Models

This module provides comprehensive data models for:
- Volume analysis and tracking
- Volume-based indicators and signals
- Liquidity assessment
- Volume prediction and forecasting
- Volume-weighted metrics (VWAP, etc.)
- Market depth analysis
- Volume anomaly detection
- Volume impact on arbitrage
- Volume trend analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class VolumeType(str, Enum):
    """Types of volume measurements."""
    TRADE = "trade"                      # Trade volume
    ORDER = "order"                      # Order volume
    QUOTE = "quote"                      # Quote volume
    BID = "bid"                          # Bid side volume
    ASK = "ask"                          # Ask side volume
    NET = "net"                          # Net volume (bid - ask)
    CUMULATIVE = "cumulative"            # Cumulative volume
    ROLLING = "rolling"                  # Rolling volume
    AVERAGE = "average"                  # Average volume


class VolumePeriod(str, Enum):
    """Time periods for volume analysis."""
    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


class VolumeDirection(str, Enum):
    """Direction of volume flow."""
    BUYING = "buying"                    # Net buying pressure
    SELLING = "selling"                  # Net selling pressure
    NEUTRAL = "neutral"                  # Balanced volume
    INCREASING = "increasing"            # Volume increasing
    DECREASING = "decreasing"            # Volume decreasing


class LiquidityLevel(str, Enum):
    """Liquidity levels."""
    VERY_HIGH = "very_high"              # Extremely liquid
    HIGH = "high"                        # Highly liquid
    MEDIUM = "medium"                    # Moderately liquid
    LOW = "low"                          # Low liquidity
    VERY_LOW = "very_low"                # Very low liquidity


class VolumeAnomalyType(str, Enum):
    """Types of volume anomalies."""
    SPIKE = "spike"                      # Volume spike
    DROP = "drop"                        # Volume drop
    SURGE = "surge"                      # Volume surge
    DROUGHT = "drought"                  # Volume drought
    PATTERN = "pattern"                  # Pattern anomaly


# ====================================================================================
# VOLUME DATA MODELS
# ====================================================================================

@dataclass
class Volume:
    """
    Comprehensive volume data model.
    """
    # Core fields
    volume_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Volume values
    trade_volume: float = 0.0
    quote_volume: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    net_volume: float = 0.0
    
    # Price references
    price: float = 0.0
    vwap: float = 0.0                     # Volume-Weighted Average Price
    twap: float = 0.0                     # Time-Weighted Average Price
    
    # Statistics
    count: int = 0                        # Number of trades
    avg_trade_size: float = 0.0
    max_trade_size: float = 0.0
    min_trade_size: float = 0.0
    
    # Direction
    direction: VolumeDirection = VolumeDirection.NEUTRAL
    buy_sell_ratio: float = 0.0
    
    # Liquidity
    liquidity_score: float = 0.0
    liquidity_level: LiquidityLevel = LiquidityLevel.MEDIUM
    order_book_depth: float = 0.0
    
    # Metadata
    period: VolumePeriod = VolumePeriod.MINUTE
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.net_volume = self.bid_volume - self.ask_volume
        
        # Calculate VWAP
        if self.trade_volume > 0:
            self.vwap = self.quote_volume / self.trade_volume
        else:
            self.vwap = self.price
            
        # Calculate average trade size
        if self.count > 0:
            self.avg_trade_size = self.trade_volume / self.count
            
        # Determine direction
        if self.net_volume > 0:
            self.direction = VolumeDirection.BUYING
        elif self.net_volume < 0:
            self.direction = VolumeDirection.SELLING
        else:
            self.direction = VolumeDirection.NEUTRAL
            
        # Calculate buy/sell ratio
        if self.ask_volume > 0:
            self.buy_sell_ratio = self.bid_volume / self.ask_volume
        else:
            self.buy_sell_ratio = 1.0
            
        # Calculate liquidity score
        self._calculate_liquidity_score()
        
    def _calculate_liquidity_score(self) -> None:
        """Calculate liquidity score."""
        score = 0.0
        
        # Volume component (50%)
        if self.trade_volume > 1000000:
            score += 50
        elif self.trade_volume > 100000:
            score += 40
        elif self.trade_volume > 10000:
            score += 30
        elif self.trade_volume > 1000:
            score += 20
        else:
            score += 10
            
        # Order book depth component (30%)
        if self.order_book_depth > 1000000:
            score += 30
        elif self.order_book_depth > 100000:
            score += 24
        elif self.order_book_depth > 10000:
            score += 18
        elif self.order_book_depth > 1000:
            score += 12
        else:
            score += 6
            
        # Trade count component (20%)
        if self.count > 1000:
            score += 20
        elif self.count > 100:
            score += 16
        elif self.count > 10:
            score += 12
        elif self.count > 1:
            score += 8
        else:
            score += 4
            
        self.liquidity_score = score
        
        # Determine liquidity level
        if self.liquidity_score >= 80:
            self.liquidity_level = LiquidityLevel.VERY_HIGH
        elif self.liquidity_score >= 60:
            self.liquidity_level = LiquidityLevel.HIGH
        elif self.liquidity_score >= 40:
            self.liquidity_level = LiquidityLevel.MEDIUM
        elif self.liquidity_score >= 20:
            self.liquidity_level = LiquidityLevel.LOW
        else:
            self.liquidity_level = LiquidityLevel.VERY_LOW
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "volume_id": self.volume_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "trade_volume": self.trade_volume,
            "quote_volume": self.quote_volume,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "net_volume": self.net_volume,
            "price": self.price,
            "vwap": self.vwap,
            "twap": self.twap,
            "count": self.count,
            "avg_trade_size": self.avg_trade_size,
            "max_trade_size": self.max_trade_size,
            "min_trade_size": self.min_trade_size,
            "direction": self.direction.value if self.direction else None,
            "buy_sell_ratio": self.buy_sell_ratio,
            "liquidity_score": self.liquidity_score,
            "liquidity_level": self.liquidity_level.value if self.liquidity_level else None,
            "order_book_depth": self.order_book_depth,
            "period": self.period.value if self.period else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Volume":
        """Create from dictionary."""
        volume = cls(
            volume_id=data.get("volume_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            trade_volume=data.get("trade_volume", 0.0),
            quote_volume=data.get("quote_volume", 0.0),
            bid_volume=data.get("bid_volume", 0.0),
            ask_volume=data.get("ask_volume", 0.0),
            net_volume=data.get("net_volume", 0.0),
            price=data.get("price", 0.0),
            vwap=data.get("vwap", 0.0),
            twap=data.get("twap", 0.0),
            count=data.get("count", 0),
            max_trade_size=data.get("max_trade_size", 0.0),
            min_trade_size=data.get("min_trade_size", 0.0),
            direction=VolumeDirection(data["direction"]) if data.get("direction") else VolumeDirection.NEUTRAL,
            buy_sell_ratio=data.get("buy_sell_ratio", 0.0),
            liquidity_score=data.get("liquidity_score", 0.0),
            liquidity_level=LiquidityLevel(data["liquidity_level"]) if data.get("liquidity_level") else LiquidityLevel.MEDIUM,
            order_book_depth=data.get("order_book_depth", 0.0),
            period=VolumePeriod(data["period"]) if data.get("period") else VolumePeriod.MINUTE,
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            volume.timestamp = datetime.fromisoformat(data["timestamp"])
            
        volume.__post_init__()
        return volume
        
    def is_high_volume(self, threshold: float = 1000000) -> bool:
        """Check if volume is high."""
        return self.trade_volume > threshold
        
    def is_low_volume(self, threshold: float = 100000) -> bool:
        """Check if volume is low."""
        return self.trade_volume < threshold
        
    def has_buying_pressure(self) -> bool:
        """Check if there is buying pressure."""
        return self.direction == VolumeDirection.BUYING and self.buy_sell_ratio > 1.0
        
    def has_selling_pressure(self) -> bool:
        """Check if there is selling pressure."""
        return self.direction == VolumeDirection.SELLING and self.buy_sell_ratio < 1.0


# ====================================================================================
# VOLUME HISTORY MODELS
# ====================================================================================

@dataclass
class VolumeHistory:
    """
    Historical volume data.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    period: VolumePeriod = VolumePeriod.HOUR
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    
    # Volume data
    volumes: List[Volume] = field(default_factory=list)
    
    # Statistics
    total_volume: float = 0.0
    avg_volume: float = 0.0
    max_volume: float = 0.0
    min_volume: float = 0.0
    median_volume: float = 0.0
    std_dev: float = 0.0
    
    # Percentiles
    p10_volume: float = 0.0
    p25_volume: float = 0.0
    p50_volume: float = 0.0
    p75_volume: float = 0.0
    p90_volume: float = 0.0
    p95_volume: float = 0.0
    p99_volume: float = 0.0
    
    # Trends
    trend_direction: str = "stable"
    trend_rate: float = 0.0
    trend_strength: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate statistics."""
        if self.volumes:
            self._calculate_statistics()
            
    def _calculate_statistics(self) -> None:
        """Calculate statistics from volume data."""
        if not self.volumes:
            return
            
        volume_values = [v.trade_volume for v in self.volumes]
        self.total_volume = sum(volume_values)
        self.avg_volume = self.total_volume / len(volume_values)
        self.max_volume = max(volume_values)
        self.min_volume = min(volume_values)
        self.median_volume = sorted(volume_values)[len(volume_values) // 2]
        
        if len(volume_values) > 1:
            self.std_dev = math.sqrt(sum((x - self.avg_volume) ** 2 for x in volume_values) / len(volume_values))
            
        # Calculate percentiles
        sorted_values = sorted(volume_values)
        self.p10_volume = sorted_values[int(len(sorted_values) * 0.1)] if sorted_values else 0
        self.p25_volume = sorted_values[int(len(sorted_values) * 0.25)] if sorted_values else 0
        self.p50_volume = sorted_values[int(len(sorted_values) * 0.5)] if sorted_values else 0
        self.p75_volume = sorted_values[int(len(sorted_values) * 0.75)] if sorted_values else 0
        self.p90_volume = sorted_values[int(len(sorted_values) * 0.9)] if sorted_values else 0
        self.p95_volume = sorted_values[int(len(sorted_values) * 0.95)] if sorted_values else 0
        self.p99_volume = sorted_values[int(len(sorted_values) * 0.99)] if sorted_values else 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period": self.period.value if self.period else None,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "volumes": [v.to_dict() for v in self.volumes[:1000]],
            "total_volume": self.total_volume,
            "avg_volume": self.avg_volume,
            "max_volume": self.max_volume,
            "min_volume": self.min_volume,
            "median_volume": self.median_volume,
            "std_dev": self.std_dev,
            "p10_volume": self.p10_volume,
            "p25_volume": self.p25_volume,
            "p50_volume": self.p50_volume,
            "p75_volume": self.p75_volume,
            "p90_volume": self.p90_volume,
            "p95_volume": self.p95_volume,
            "p99_volume": self.p99_volume,
            "trend_direction": self.trend_direction,
            "trend_rate": self.trend_rate,
            "trend_strength": self.trend_strength,
            "metadata": self.metadata
        }
        
    def add_volume(self, volume: Volume) -> None:
        """
        Add volume to history.
        
        Args:
            volume: Volume to add
        """
        self.volumes.append(volume)
        self._calculate_statistics()
        
    def get_volume_anomalies(self, threshold: float = 2.0) -> List[Volume]:
        """
        Get volume anomalies based on standard deviation.
        
        Args:
            threshold: Number of standard deviations
            
        Returns:
            List of anomalous volumes
        """
        if self.std_dev == 0:
            return []
            
        anomalies = []
        for volume in self.volumes:
            z_score = (volume.trade_volume - self.avg_volume) / self.std_dev
            if abs(z_score) > threshold:
                anomalies.append(volume)
        return anomalies


# ====================================================================================
# VOLUME-WEIGHTED METRICS MODELS
# ====================================================================================

@dataclass
class VWAP:
    """
    Volume-Weighted Average Price calculation.
    """
    # Core fields
    vwap_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    period: VolumePeriod = VolumePeriod.DAY
    
    # VWAP values
    current_vwap: float = 0.0
    typical_vwap: float = 0.0           # Typical VWAP range
    upper_band: float = 0.0
    lower_band: float = 0.0
    
    # Components
    cumulative_price_volume: float = 0.0
    cumulative_volume: float = 0.0
    
    # Statistics
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    update_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate VWAP."""
        if self.cumulative_volume > 0:
            self.current_vwap = self.cumulative_price_volume / self.cumulative_volume
            self.typical_vwap = self.current_vwap
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vwap_id": self.vwap_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period": self.period.value if self.period else None,
            "current_vwap": self.current_vwap,
            "typical_vwap": self.typical_vwap,
            "upper_band": self.upper_band,
            "lower_band": self.lower_band,
            "cumulative_price_volume": self.cumulative_price_volume,
            "cumulative_volume": self.cumulative_volume,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "update_count": self.update_count,
            "metadata": self.metadata
        }
        
    def update(self, price: float, volume: float) -> None:
        """
        Update VWAP with new price and volume.
        
        Args:
            price: Current price
            volume: Current volume
        """
        self.cumulative_price_volume += price * volume
        self.cumulative_volume += volume
        self.current_vwap = self.cumulative_price_volume / self.cumulative_volume if self.cumulative_volume > 0 else 0
        self.update_count += 1
        self.end_time = datetime.utcnow()
        
    def get_deviation(self, price: float) -> float:
        """
        Get deviation from VWAP.
        
        Args:
            price: Current price
            
        Returns:
            Deviation percentage
        """
        if self.current_vwap == 0:
            return 0.0
        return ((price - self.current_vwap) / self.current_vwap) * 100


# ====================================================================================
# VOLUME PREDICTION MODELS
# ====================================================================================

@dataclass
class VolumePrediction:
    """
    Volume prediction model.
    """
    # Core fields
    prediction_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Prediction values
    predicted_volume: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    confidence: float = 0.0
    
    # Timeframe
    horizon: str = "1h"                 # 1h, 4h, 24h
    period: VolumePeriod = VolumePeriod.HOUR
    
    # Model info
    model: str = "prophet"
    model_version: str = "1.0.0"
    features_used: List[str] = field(default_factory=list)
    
    # Historical comparison
    historical_avg: float = 0.0
    predicted_change: float = 0.0
    predicted_change_percentage: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_id": self.prediction_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "predicted_volume": self.predicted_volume,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "period": self.period.value if self.period else None,
            "model": self.model,
            "model_version": self.model_version,
            "features_used": self.features_used,
            "historical_avg": self.historical_avg,
            "predicted_change": self.predicted_change,
            "predicted_change_percentage": self.predicted_change_percentage,
            "metadata": self.metadata
        }


# ====================================================================================
# VOLUME ANOMALY MODELS
# ====================================================================================

@dataclass
class VolumeAnomaly:
    """
    Volume anomaly detection model.
    """
    # Core fields
    anomaly_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Anomaly details
    current_volume: float = 0.0
    expected_volume: float = 0.0
    deviation: float = 0.0
    deviation_percentage: float = 0.0
    z_score: float = 0.0
    
    # Context
    anomaly_type: VolumeAnomalyType = VolumeAnomalyType.SPIKE
    severity: str = "medium"            # low, medium, high, critical
    confidence: float = 0.0
    
    # Historical context
    avg_volume: float = 0.0
    std_dev: float = 0.0
    window_size: int = 100
    
    # Source data
    source_volumes: List[float] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.expected_volume > 0:
            self.deviation = self.current_volume - self.expected_volume
            self.deviation_percentage = (self.deviation / self.expected_volume) * 100
            
        if self.std_dev > 0:
            self.z_score = (self.current_volume - self.avg_volume) / self.std_dev
            
        # Determine severity
        abs_deviation = abs(self.deviation_percentage)
        if abs_deviation > 100:
            self.severity = "critical"
        elif abs_deviation > 50:
            self.severity = "high"
        elif abs_deviation > 20:
            self.severity = "medium"
        else:
            self.severity = "low"
            
        # Determine anomaly type
        if self.z_score > 2:
            self.anomaly_type = VolumeAnomalyType.SPIKE
            self.confidence = min(1.0, self.z_score / 5)
        elif self.z_score < -2:
            self.anomaly_type = VolumeAnomalyType.DROP
            self.confidence = min(1.0, abs(self.z_score) / 5)
        else:
            self.anomaly_type = VolumeAnomalyType.PATTERN
            self.confidence = 0.3
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_id": self.anomaly_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "current_volume": self.current_volume,
            "expected_volume": self.expected_volume,
            "deviation": self.deviation,
            "deviation_percentage": self.deviation_percentage,
            "z_score": self.z_score,
            "anomaly_type": self.anomaly_type.value if self.anomaly_type else None,
            "severity": self.severity,
            "confidence": self.confidence,
            "avg_volume": self.avg_volume,
            "std_dev": self.std_dev,
            "window_size": self.window_size,
            "source_volumes": self.source_volumes[:10],
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_vwap(
    prices: List[float],
    volumes: List[float]
) -> float:
    """
    Calculate Volume-Weighted Average Price.
    
    Args:
        prices: List of prices
        volumes: List of volumes
        
    Returns:
        VWAP
    """
    if not prices or not volumes or len(prices) != len(volumes):
        return 0.0
        
    total_price_volume = sum(p * v for p, v in zip(prices, volumes))
    total_volume = sum(volumes)
    
    if total_volume == 0:
        return 0.0
        
    return total_price_volume / total_volume


def calculate_volume_turnover(
    volume: float,
    total_supply: float
) -> float:
    """
    Calculate volume turnover ratio.
    
    Args:
        volume: Trade volume
        total_supply: Total supply of asset
        
    Returns:
        Turnover ratio
    """
    if total_supply == 0:
        return 0.0
    return volume / total_supply


def calculate_volume_price_correlation(
    prices: List[float],
    volumes: List[float]
) -> float:
    """
    Calculate correlation between price and volume.
    
    Args:
        prices: List of prices
        volumes: List of volumes
        
    Returns:
        Correlation coefficient
    """
    if len(prices) != len(volumes) or len(prices) < 2:
        return 0.0
        
    n = len(prices)
    mean_price = sum(prices) / n
    mean_volume = sum(volumes) / n
    
    numerator = sum((prices[i] - mean_price) * (volumes[i] - mean_volume) for i in range(n))
    denom_price = sum((prices[i] - mean_price) ** 2 for i in range(n))
    denom_volume = sum((volumes[i] - mean_volume) ** 2 for i in range(n))
    
    if denom_price == 0 or denom_volume == 0:
        return 0.0
        
    return numerator / (denom_price * denom_volume) ** 0.5


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'VolumeType',
    'VolumePeriod',
    'VolumeDirection',
    'LiquidityLevel',
    'VolumeAnomalyType',
    
    # Core Models
    'Volume',
    'VolumeHistory',
    'VWAP',
    'VolumePrediction',
    'VolumeAnomaly',
    
    # Helper Functions
    'calculate_vwap',
    'calculate_volume_turnover',
    'calculate_volume_price_correlation',
]
