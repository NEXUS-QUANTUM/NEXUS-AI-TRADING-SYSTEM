"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Volume Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced volume management system for arbitrage with:
- Real-time volume aggregation from multiple exchanges
- Volume normalization and validation
- Volume profile analysis
- Volume anomaly detection
- Volume-weighted price calculation
- Volume trend analysis
- Multi-exchange volume comparison
- Volume-based arbitrage opportunity filtering
"""

import asyncio
import json
import logging
import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field, validator, root_validator

# Local imports
from .base import BaseVolumeManager
from .exceptions import (
    VolumeManagerError,
    VolumeValidationError,
    VolumeNotFoundError,
    VolumeTimeoutError,
)
from .price_manager import PriceManager, PriceSource
from .ticker_manager import TickerManager, TickerData
from .config import VolumeManagerConfig
from .constants import (
    VOLUME_CACHE_TTL,
    MAX_VOLUME_HISTORY,
    MIN_VOLUME_SAMPLES,
    VOLUME_ANOMALY_THRESHOLD,
    DEFAULT_VOLUME_THRESHOLD,
    VOLUME_WEIGHTING_FACTOR,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class VolumeLevel(str, Enum):
    """Volume level classification."""
    EXTREMELY_HIGH = "extremely_high"
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"
    EXTREMELY_LOW = "extremely_low"
    NO_VOLUME = "no_volume"


class VolumeTrend(str, Enum):
    """Volume trend direction."""
    STRONG_INCREASING = "strong_increasing"
    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    STRONG_DECREASING = "strong_decreasing"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


class VolumeQuality(str, Enum):
    """Volume data quality."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    SUSPICIOUS = "suspicious"
    INVALID = "invalid"


# ============================================================
# DATA MODELS
# ============================================================

class VolumeData(BaseModel):
    """Represents volume data for a trading pair."""
    
    exchange: str
    symbol: str
    volume: Decimal
    quote_volume: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    quote_volume_24h: Optional[Decimal] = None
    volume_weighted_price: Optional[Decimal] = None
    volume_weighted_price_24h: Optional[Decimal] = None
    volume_ratio: Optional[float] = None
    volume_change_pct: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    exchange_timestamp: Optional[datetime] = None
    source_type: str = "spot"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality: VolumeQuality = VolumeQuality.GOOD
    level: VolumeLevel = VolumeLevel.MEDIUM
    trend: VolumeTrend = VolumeTrend.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    @validator('volume')
    def validate_volume(cls, v):
        if v < 0:
            raise ValueError(f"Volume must be non-negative: {v}")
        return v

    @validator('quote_volume', 'volume_24h', 'quote_volume_24h', each=True)
    def validate_optional_volume(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"Volume must be non-negative: {v}")
        return v

    @validator('volume_ratio')
    def validate_volume_ratio(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"Volume ratio must be non-negative: {v}")
        return v

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'volume': str(self.volume),
            'quote_volume': str(self.quote_volume) if self.quote_volume else None,
            'volume_24h': str(self.volume_24h) if self.volume_24h else None,
            'quote_volume_24h': str(self.quote_volume_24h) if self.quote_volume_24h else None,
            'volume_weighted_price': str(self.volume_weighted_price) if self.volume_weighted_price else None,
            'volume_weighted_price_24h': str(self.volume_weighted_price_24h) if self.volume_weighted_price_24h else None,
            'volume_ratio': self.volume_ratio,
            'volume_change_pct': self.volume_change_pct,
            'timestamp': self.timestamp.isoformat(),
            'exchange_timestamp': self.exchange_timestamp.isoformat() if self.exchange_timestamp else None,
            'source_type': self.source_type,
            'confidence': self.confidence,
            'quality': self.quality.value if isinstance(self.quality, VolumeQuality) else self.quality,
            'level': self.level.value if isinstance(self.level, VolumeLevel) else self.level,
            'trend': self.trend.value if isinstance(self.trend, VolumeTrend) else self.trend,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VolumeData':
        """Create VolumeData from dictionary."""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'exchange_timestamp' in data and isinstance(data['exchange_timestamp'], str):
            data['exchange_timestamp'] = datetime.fromisoformat(data['exchange_timestamp'])
        if 'quality' in data and isinstance(data['quality'], str):
            data['quality'] = VolumeQuality(data['quality'])
        if 'level' in data and isinstance(data['level'], str):
            data['level'] = VolumeLevel(data['level'])
        if 'trend' in data and isinstance(data['trend'], str):
            data['trend'] = VolumeTrend(data['trend'])
        return cls(**data)

    def get_volume_usd(self, price: Optional[Decimal] = None) -> Optional[Decimal]:
        """Get volume in USD."""
        if self.quote_volume is not None:
            return self.quote_volume
        if price is not None and self.volume is not None:
            return self.volume * price
        return None

    def get_volume_24h_usd(self, price: Optional[Decimal] = None) -> Optional[Decimal]:
        """Get 24h volume in USD."""
        if self.quote_volume_24h is not None:
            return self.quote_volume_24h
        if price is not None and self.volume_24h is not None:
            return self.volume_24h * price
        return None

    def is_active(self, max_age_seconds: int = 60) -> bool:
        """Check if volume data is active."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age <= max_age_seconds

    def has_complete_data(self) -> bool:
        """Check if volume data is complete."""
        return all([
            self.volume is not None,
            self.volume_24h is not None,
        ])


@dataclass
class VolumeSnapshot:
    """Complete volume snapshot across exchanges."""
    
    timestamp: datetime
    symbol: str
    volumes: Dict[str, VolumeData]  # exchange -> VolumeData
    total_volume: Optional[Decimal] = None
    total_quote_volume: Optional[Decimal] = None
    total_volume_24h: Optional[Decimal] = None
    total_quote_volume_24h: Optional[Decimal] = None
    average_volume: Optional[Decimal] = None
    median_volume: Optional[Decimal] = None
    volume_std: Optional[float] = None
    exchange_count: int = 0
    active_exchange_count: int = 0
    anomaly_detected: bool = False
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    highest_volume: Optional[VolumeData] = None
    lowest_volume: Optional[VolumeData] = None
    volume_distribution: Dict[str, float] = field(default_factory=dict)
    market_volume: Optional[Decimal] = None
    volume_weighted_price: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_volume_for_exchange(self, exchange: str) -> Optional[VolumeData]:
        """Get volume for a specific exchange."""
        return self.volumes.get(exchange)

    def get_exchanges(self) -> Set[str]:
        """Get all exchanges in snapshot."""
        return set(self.volumes.keys())

    def get_active_exchanges(self, max_age_seconds: int = 60) -> List[str]:
        """Get exchanges with recent volume data."""
        active = []
        for exchange, volume in self.volumes.items():
            if volume.is_active(max_age_seconds):
                active.append(exchange)
        return active

    def get_volume_ranking(self) -> List[Tuple[str, Decimal]]:
        """Get volume ranking across exchanges."""
        ranking = []
        for exchange, volume in self.volumes.items():
            ranking.append((exchange, volume.volume))
        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def get_quote_volume_ranking(self) -> List[Tuple[str, Decimal]]:
        """Get quote volume ranking across exchanges."""
        ranking = []
        for exchange, volume in self.volumes.items():
            if volume.quote_volume is not None:
                ranking.append((exchange, volume.quote_volume))
        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def get_highest_volume_exchange(self) -> Optional[str]:
        """Get exchange with the highest volume."""
        if self.highest_volume:
            return self.highest_volume.exchange
        return None

    def get_lowest_volume_exchange(self) -> Optional[str]:
        """Get exchange with the lowest volume."""
        if self.lowest_volume:
            return self.lowest_volume.exchange
        return None

    def get_volume_share(self, exchange: str) -> Optional[float]:
        """Get volume share for an exchange."""
        if self.total_volume and exchange in self.volumes:
            volume = self.volumes[exchange].volume
            if self.total_volume > 0:
                return float(volume / self.total_volume * 100)
        return None

    def get_volume_concentration(self) -> Optional[float]:
        """Get volume concentration (HHI)."""
        if not self.volumes or not self.total_volume:
            return None
        
        total = float(self.total_volume)
        if total == 0:
            return None
        
        hhi = 0
        for volume_data in self.volumes.values():
            share = float(volume_data.volume) / total
            hhi += share * share
        
        return hhi

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'volumes': {
                k: v.to_dict()
                for k, v in self.volumes.items()
            },
            'total_volume': str(self.total_volume) if self.total_volume else None,
            'total_quote_volume': str(self.total_quote_volume) if self.total_quote_volume else None,
            'total_volume_24h': str(self.total_volume_24h) if self.total_volume_24h else None,
            'total_quote_volume_24h': str(self.total_quote_volume_24h) if self.total_quote_volume_24h else None,
            'average_volume': str(self.average_volume) if self.average_volume else None,
            'median_volume': str(self.median_volume) if self.median_volume else None,
            'volume_std': self.volume_std,
            'exchange_count': self.exchange_count,
            'active_exchange_count': self.active_exchange_count,
            'anomaly_detected': self.anomaly_detected,
            'anomalies': self.anomalies,
            'highest_volume': self.highest_volume.to_dict() if self.highest_volume else None,
            'lowest_volume': self.lowest_volume.to_dict() if self.lowest_volume else None,
            'volume_distribution': self.volume_distribution,
            'market_volume': str(self.market_volume) if self.market_volume else None,
            'volume_weighted_price': str(self.volume_weighted_price) if self.volume_weighted_price else None,
            'metadata': self.metadata,
        }


@dataclass
class VolumeStatistics:
    """Statistical analysis of volume data."""
    
    symbol: str
    exchange: str
    volume_mean: Decimal
    volume_median: Decimal
    volume_std: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_range: Decimal
    quote_volume_mean: Optional[Decimal] = None
    quote_volume_median: Optional[Decimal] = None
    quote_volume_std: Optional[Decimal] = None
    volume_volatility: float = 0.0
    volume_trend: VolumeTrend = VolumeTrend.UNKNOWN
    trend_strength: float = 0.0
    sample_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'volume_mean': str(self.volume_mean),
            'volume_median': str(self.volume_median),
            'volume_std': str(self.volume_std),
            'volume_min': str(self.volume_min),
            'volume_max': str(self.volume_max),
            'volume_range': str(self.volume_range),
            'quote_volume_mean': str(self.quote_volume_mean) if self.quote_volume_mean else None,
            'quote_volume_median': str(self.quote_volume_median) if self.quote_volume_median else None,
            'quote_volume_std': str(self.quote_volume_std) if self.quote_volume_std else None,
            'volume_volatility': self.volume_volatility,
            'volume_trend': self.volume_trend.value if isinstance(self.volume_trend, VolumeTrend) else self.volume_trend,
            'trend_strength': self.trend_strength,
            'sample_count': self.sample_count,
            'timestamp': self.timestamp.isoformat(),
        }


@dataclass
class VolumeAnomaly:
    """Volume anomaly detection result."""
    
    exchange: str
    symbol: str
    type: str  # spike, drop, abnormal, suspicious
    volume: Decimal
    expected_volume: Decimal
    deviation_pct: float
    zscore: float
    severity: str  # low, medium, high, critical
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'type': self.type,
            'volume': str(self.volume),
            'expected_volume': str(self.expected_volume),
            'deviation_pct': self.deviation_pct,
            'zscore': self.zscore,
            'severity': self.severity,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }


# ============================================================
# VOLUME MANAGER IMPLEMENTATION
# ============================================================

class VolumeManager(BaseVolumeManager):
    """
    Advanced volume manager with:
    - Real-time volume aggregation
    - Multi-exchange volume comparison
    - Volume anomaly detection
    - Volume trend analysis
    - Volume-weighted price calculation
    - Volume-based arbitrage filtering
    """

    def __init__(
        self,
        price_manager: PriceManager,
        ticker_manager: Optional[TickerManager] = None,
        config: Optional[VolumeManagerConfig] = None,
        redis_client: Optional[Any] = None,
        cache_ttl: int = 5,
    ):
        """
        Initialize volume manager.

        Args:
            price_manager: PriceManager instance
            ticker_manager: TickerManager instance (optional)
            config: Configuration instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
        """
        self.price_manager = price_manager
        self.ticker_manager = ticker_manager
        self.config = config or VolumeManagerConfig()
        self.redis = redis_client
        self.cache_ttl = cache_ttl

        # Volume storage
        self._volumes: Dict[str, Dict[str, VolumeData]] = {}  # exchange -> symbol -> VolumeData
        self._volume_history: Dict[str, Dict[str, deque]] = {}  # exchange -> symbol -> deque of volumes
        self._volume_updates: Dict[str, int] = {}
        self._last_update: Dict[str, float] = {}

        # Volume averages
        self._volume_averages: Dict[str, Dict[str, Dict[str, Decimal]]] = {}  # exchange -> symbol -> {mean, median, std}

        # Metrics
        self._metrics = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'anomalies_detected': 0,
            'avg_update_latency_ms': 0,
            'last_update_timestamp': None,
            'update_rate_per_sec': 0,
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

        # Volume thresholds
        self._volume_levels = {
            VolumeLevel.EXTREMELY_HIGH: 1000000,
            VolumeLevel.VERY_HIGH: 100000,
            VolumeLevel.HIGH: 10000,
            VolumeLevel.MEDIUM: 1000,
            VolumeLevel.LOW: 100,
            VolumeLevel.VERY_LOW: 10,
            VolumeLevel.EXTREMELY_LOW: 0,
        }

        # Trend thresholds
        self._trend_thresholds = {
            'strong_increasing': 20.0,
            'increasing': 5.0,
            'decreasing': -5.0,
            'strong_decreasing': -20.0,
            'volatile': 30.0,
        }

        logger.info("VolumeManager initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def update_volume(
        self,
        exchange: str,
        symbol: str,
        volume: Union[float, Decimal, str],
        quote_volume: Optional[Union[float, Decimal, str]] = None,
        volume_24h: Optional[Union[float, Decimal, str]] = None,
        quote_volume_24h: Optional[Union[float, Decimal, str]] = None,
        volume_weighted_price: Optional[Union[float, Decimal, str]] = None,
        exchange_timestamp: Optional[datetime] = None,
        source_type: str = "spot",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VolumeData:
        """
        Update volume data for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            volume: Current volume
            quote_volume: Current quote volume (optional)
            volume_24h: 24h volume (optional)
            quote_volume_24h: 24h quote volume (optional)
            volume_weighted_price: Volume weighted price (optional)
            exchange_timestamp: Exchange timestamp
            source_type: Source type
            metadata: Additional metadata

        Returns:
            VolumeData instance
        """
        start_time = time.perf_counter()

        try:
            # Convert values
            volume_decimal = self._to_decimal(volume)
            quote_volume_decimal = self._to_decimal(quote_volume) if quote_volume is not None else None
            volume_24h_decimal = self._to_decimal(volume_24h) if volume_24h is not None else None
            quote_volume_24h_decimal = self._to_decimal(quote_volume_24h) if quote_volume_24h is not None else None
            vwp_decimal = self._to_decimal(volume_weighted_price) if volume_weighted_price is not None else None

            # Validate volume
            if volume_decimal is None or volume_decimal < 0:
                raise VolumeValidationError(f"Invalid volume: {volume_decimal}")

            # Get price for VWP if not provided
            if vwp_decimal is None:
                price_source = await self.price_manager.get_price(exchange, symbol)
                if price_source:
                    vwp_decimal = price_source.price

            # Calculate volume ratio
            volume_ratio = None
            if volume_24h_decimal and volume_24h_decimal > 0:
                volume_ratio = float(volume_decimal / volume_24h_decimal)

            # Calculate volume change percentage
            volume_change_pct = None
            history = await self.get_volume_history(exchange, symbol, limit=10)
            if len(history) >= 2:
                prev_volume = history[-2].volume
                if prev_volume > 0:
                    volume_change_pct = float((volume_decimal - prev_volume) / prev_volume * 100)

            # Determine quality
            quality = self._determine_volume_quality(
                exchange, symbol, volume_decimal, quote_volume_decimal
            )

            # Determine level
            level = self._determine_volume_level(volume_decimal)

            # Determine trend
            trend = self._determine_volume_trend(exchange, symbol, volume_decimal)

            # Calculate confidence
            confidence = self._calculate_confidence(
                volume_decimal, quote_volume_decimal, volume_24h_decimal
            )

            # Create volume data
            volume_data = VolumeData(
                exchange=exchange,
                symbol=symbol,
                volume=volume_decimal,
                quote_volume=quote_volume_decimal,
                volume_24h=volume_24h_decimal,
                quote_volume_24h=quote_volume_24h_decimal,
                volume_weighted_price=vwp_decimal,
                volume_weighted_price_24h=None,  # Could calculate from 24h data
                volume_ratio=volume_ratio,
                volume_change_pct=volume_change_pct,
                timestamp=datetime.utcnow(),
                exchange_timestamp=exchange_timestamp or datetime.utcnow(),
                source_type=source_type,
                confidence=confidence,
                quality=quality,
                level=level,
                trend=trend,
                metadata=metadata or {},
            )

            # Validate volume data
            if not await self._validate_volume_data(volume_data):
                raise VolumeValidationError(f"Volume validation failed for {exchange}:{symbol}")

            # Store volume
            async with self._lock:
                if exchange not in self._volumes:
                    self._volumes[exchange] = {}
                self._volumes[exchange][symbol] = volume_data

                # Update history
                if exchange not in self._volume_history:
                    self._volume_history[exchange] = {}
                if symbol not in self._volume_history[exchange]:
                    self._volume_history[exchange][symbol] = deque(maxlen=MAX_VOLUME_HISTORY)
                self._volume_history[exchange][symbol].append(volume_data)

                # Update metrics
                self._volume_updates[exchange] = self._volume_updates.get(exchange, 0) + 1
                self._last_update[exchange] = time.time()
                self._metrics['total_updates'] += 1
                self._metrics['successful_updates'] += 1

            # Cache volume
            await self._cache_set(f"volume:{exchange}:{symbol}", volume_data.to_dict())

            # Detect anomalies
            await self._detect_volume_anomalies(volume_data)

            # Update volume averages
            await self._update_volume_averages(exchange, symbol)

            # Update latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics['avg_update_latency_ms'] = (
                self._metrics['avg_update_latency_ms'] * 0.9 + latency_ms * 0.1
            )
            self._metrics['last_update_timestamp'] = datetime.utcnow().isoformat()

            logger.debug(
                "Volume updated for %s:%s = %s (24h: %s, ratio: %.2f%%)",
                exchange, symbol, volume_decimal, volume_24h_decimal, volume_ratio or 0
            )

            return volume_data

        except Exception as e:
            self._metrics['failed_updates'] += 1
            logger.error(f"Failed to update volume for {exchange}:{symbol}: {e}")
            raise VolumeManagerError(f"Failed to update volume: {e}")

    async def update_volume_from_ticker(
        self,
        exchange: str,
        symbol: str,
        ticker_data: TickerData,
    ) -> VolumeData:
        """
        Update volume from TickerData.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            ticker_data: TickerData instance

        Returns:
            VolumeData instance
        """
        return await self.update_volume(
            exchange=exchange,
            symbol=symbol,
            volume=ticker_data.volume or Decimal('0'),
            quote_volume=ticker_data.quote_volume,
            volume_24h=ticker_data.volume_24h,
            quote_volume_24h=ticker_data.quote_volume_24h,
            exchange_timestamp=ticker_data.exchange_timestamp,
            source_type=ticker_data.source_type,
            metadata=ticker_data.metadata,
        )

    async def get_volume(
        self,
        exchange: str,
        symbol: str,
        use_cache: bool = True,
    ) -> Optional[VolumeData]:
        """
        Get volume for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            use_cache: Whether to use cache

        Returns:
            VolumeData or None
        """
        # Check cache
        if use_cache:
            cached = await self._cache_get(f"volume:{exchange}:{symbol}")
            if cached:
                try:
                    return VolumeData.from_dict(cached)
                except Exception as e:
                    logger.warning(f"Failed to parse cached volume: {e}")

        # Check memory
        async with self._lock:
            if exchange in self._volumes and symbol in self._volumes[exchange]:
                return self._volumes[exchange][symbol]

        return None

    async def get_volumes_for_symbol(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        max_age_seconds: int = 60,
    ) -> Dict[str, VolumeData]:
        """
        Get volumes for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_confidence: Minimum confidence score
            max_age_seconds: Maximum age of volume data

        Returns:
            Dict mapping exchange to VolumeData
        """
        result = {}
        exchanges = exchanges or list(self._volumes.keys())

        for exchange in exchanges:
            volume = await self.get_volume(exchange, symbol)
            if volume:
                if (volume.confidence >= min_confidence and 
                    volume.is_active(max_age_seconds)):
                    result[exchange] = volume

        return result

    async def get_snapshot(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        max_age_seconds: int = 60,
    ) -> VolumeSnapshot:
        """
        Get a complete volume snapshot.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_confidence: Minimum confidence score
            max_age_seconds: Maximum age of volume data

        Returns:
            VolumeSnapshot instance
        """
        volumes = await self.get_volumes_for_symbol(
            symbol, exchanges, min_confidence, max_age_seconds
        )

        if not volumes:
            raise VolumeNotFoundError(f"No volumes found for {symbol}")

        # Calculate statistics
        volume_values = [v.volume for v in volumes.values()]
        quote_volume_values = [v.quote_volume for v in volumes.values() if v.quote_volume is not None]
        volume_24h_values = [v.volume_24h for v in volumes.values() if v.volume_24h is not None]

        # Total volumes
        total_volume = sum(volume_values, Decimal('0'))
        total_quote_volume = sum(quote_volume_values, Decimal('0')) if quote_volume_values else None
        total_volume_24h = sum(volume_24h_values, Decimal('0')) if volume_24h_values else None

        # Average and median
        average_volume = total_volume / Decimal(len(volume_values)) if volume_values else Decimal('0')
        median_volume = sorted(volume_values)[len(volume_values) // 2] if volume_values else Decimal('0')

        # Standard deviation
        volume_std = Decimal(str(np.std([float(v) for v in volume_values]))) if len(volume_values) > 1 else Decimal('0')

        # Volume distribution
        volume_distribution = {}
        if total_volume > 0:
            for exchange, volume_data in volumes.items():
                share = float(volume_data.volume / total_volume * 100)
                volume_distribution[exchange] = share

        # Find highest and lowest
        highest_volume = max(volumes.values(), key=lambda v: v.volume)
        lowest_volume = min(volumes.values(), key=lambda v: v.volume)

        # Calculate volume-weighted price
        vwp = None
        if total_volume > 0 and quote_volume_values:
            total_value = sum(
                v.quote_volume for v in volumes.values() 
                if v.quote_volume is not None
            )
            if total_value > 0:
                # VWP = total_value / total_volume
                vwp = total_value / total_volume

        # Detect anomalies
        anomalies = []
        anomaly_detected = False

        for exchange, volume_data in volumes.items():
            # Volume anomaly
            if average_volume > 0 and volume_std > 0:
                zscore = abs(float(volume_data.volume - average_volume) / float(volume_std))
                if zscore > VOLUME_ANOMALY_THRESHOLD:
                    anomalies.append({
                        'exchange': exchange,
                        'type': 'volume',
                        'volume': str(volume_data.volume),
                        'zscore': zscore,
                        'threshold': VOLUME_ANOMALY_THRESHOLD,
                    })
                    anomaly_detected = True

            # Volume ratio anomaly
            if volume_data.volume_ratio is not None and volume_data.volume_ratio > 0.5:
                anomalies.append({
                    'exchange': exchange,
                    'type': 'volume_ratio',
                    'volume_ratio': volume_data.volume_ratio,
                    'threshold': 0.5,
                })
                anomaly_detected = True

        # Calculate active exchange count
        active_count = len([v for v in volumes.values() if v.is_active(max_age_seconds)])

        # Calculate market volume (use highest volume exchange as market)
        market_volume = highest_volume.volume if highest_volume else None

        # Create snapshot
        snapshot = VolumeSnapshot(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            volumes=volumes,
            total_volume=total_volume,
            total_quote_volume=total_quote_volume,
            total_volume_24h=total_volume_24h,
            total_quote_volume_24h=None,  # Could calculate from 24h data
            average_volume=average_volume,
            median_volume=median_volume,
            volume_std=float(volume_std) if volume_std else None,
            exchange_count=len(volumes),
            active_exchange_count=active_count,
            anomaly_detected=anomaly_detected,
            anomalies=anomalies,
            highest_volume=highest_volume,
            lowest_volume=lowest_volume,
            volume_distribution=volume_distribution,
            market_volume=market_volume,
            volume_weighted_price=vwp,
            metadata={
                'min_confidence': min_confidence,
                'max_age_seconds': max_age_seconds,
                'exchanges_queried': list(volumes.keys()),
            },
        )

        # Cache snapshot
        await self._cache_set(f"snapshot:volume:{symbol}", snapshot.to_dict())

        logger.info(
            "Volume snapshot for %s: %d exchanges, total volume: %s",
            symbol, snapshot.exchange_count, total_volume
        )

        return snapshot

    async def get_volume_statistics(
        self,
        exchange: str,
        symbol: str,
        window: int = 100,
    ) -> VolumeStatistics:
        """
        Get statistical analysis of volume data.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            window: Window size for statistics

        Returns:
            VolumeStatistics instance
        """
        # Get volume history
        async with self._lock:
            if exchange not in self._volume_history:
                raise VolumeNotFoundError(f"No volume history for {exchange}:{symbol}")
            if symbol not in self._volume_history[exchange]:
                raise VolumeNotFoundError(f"No volume history for {exchange}:{symbol}")

            history = list(self._volume_history[exchange][symbol])
            if not history:
                raise VolumeNotFoundError(f"No volume history for {exchange}:{symbol}")

            recent = history[-window:]

        # Volume statistics
        volumes = [v.volume for v in recent]
        volume_mean = sum(volumes) / Decimal(len(volumes))
        volume_median = sorted(volumes)[len(volumes) // 2]
        volume_std = Decimal(str(np.std([float(v) for v in volumes]))) if len(volumes) > 1 else Decimal('0')
        volume_min = min(volumes)
        volume_max = max(volumes)
        volume_range = volume_max - volume_min

        # Quote volume statistics
        quote_volumes = [v.quote_volume for v in recent if v.quote_volume is not None]
        quote_volume_mean = None
        quote_volume_median = None
        quote_volume_std = None
        if quote_volumes:
            quote_volume_mean = sum(quote_volumes) / Decimal(len(quote_volumes))
            quote_volume_median = sorted(quote_volumes)[len(quote_volumes) // 2]
            quote_volume_std = Decimal(str(np.std([float(v) for v in quote_volumes]))) if len(quote_volumes) > 1 else Decimal('0')

        # Calculate volatility
        volume_volatility = float(volume_std / volume_mean * 100) if volume_mean > 0 else 0

        # Determine trend
        trend, trend_strength = self._calculate_volume_trend(volumes)

        return VolumeStatistics(
            symbol=symbol,
            exchange=exchange,
            volume_mean=volume_mean,
            volume_median=volume_median,
            volume_std=volume_std,
            volume_min=volume_min,
            volume_max=volume_max,
            volume_range=volume_range,
            quote_volume_mean=quote_volume_mean,
            quote_volume_median=quote_volume_median,
            quote_volume_std=quote_volume_std,
            volume_volatility=volume_volatility,
            volume_trend=trend,
            trend_strength=trend_strength,
            sample_count=len(recent),
        )

    async def get_volume_history(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[VolumeData]:
        """
        Get volume history for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            limit: Maximum number of volumes to return

        Returns:
            List of VolumeData
        """
        async with self._lock:
            if exchange not in self._volume_history:
                return []
            if symbol not in self._volume_history[exchange]:
                return []

            history = list(self._volume_history[exchange][symbol])
            return history[-limit:]

    async def get_volume_weighted_price(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Optional[Decimal]:
        """
        Calculate volume-weighted price across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            Volume-weighted price or None
        """
        volumes = await self.get_volumes_for_symbol(symbol, exchanges)

        if not volumes:
            return None

        total_volume = Decimal('0')
        total_value = Decimal('0')

        for volume_data in volumes.values():
            # Get price for this exchange
            price = await self.price_manager.get_price(volume_data.exchange, symbol)
            if price and volume_data.volume:
                total_volume += volume_data.volume
                total_value += volume_data.volume * price.price

        if total_volume > 0:
            return total_value / total_volume

        return None

    async def get_volume_anomalies(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_zscore: float = 3.0,
    ) -> List[VolumeAnomaly]:
        """
        Detect volume anomalies.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_zscore: Minimum z-score for anomaly detection

        Returns:
            List of VolumeAnomaly
        """
        anomalies = []
        volumes = await self.get_volumes_for_symbol(symbol, exchanges)

        for exchange, volume_data in volumes.items():
            # Get volume history
            history = await self.get_volume_history(exchange, symbol, limit=50)

            if len(history) < MIN_VOLUME_SAMPLES:
                continue

            volumes_list = [v.volume for v in history[-50:]]
            mean_volume = sum(volumes_list) / Decimal(len(volumes_list))
            std_volume = Decimal(str(np.std([float(v) for v in volumes_list]))) if len(volumes_list) > 1 else Decimal('0')

            if std_volume == 0:
                continue

            # Calculate z-score
            zscore = abs(float(volume_data.volume - mean_volume) / float(std_volume))

            if zscore >= min_zscore:
                deviation_pct = float((volume_data.volume - mean_volume) / mean_volume * 100) if mean_volume > 0 else 0

                # Determine type and severity
                anomaly_type = "spike" if volume_data.volume > mean_volume else "drop"
                severity = "low"
                if zscore >= 5:
                    severity = "critical"
                elif zscore >= 4:
                    severity = "high"
                elif zscore >= 3:
                    severity = "medium"

                anomalies.append(VolumeAnomaly(
                    exchange=exchange,
                    symbol=symbol,
                    type=anomaly_type,
                    volume=volume_data.volume,
                    expected_volume=mean_volume,
                    deviation_pct=deviation_pct,
                    zscore=zscore,
                    severity=severity,
                    metadata={
                        'mean_volume': str(mean_volume),
                        'std_volume': str(std_volume),
                        'sample_count': len(volumes_list),
                    },
                ))

                self._metrics['anomalies_detected'] += 1

        return anomalies

    async def get_highest_volume_exchange(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], Optional[Decimal]]:
        """
        Get exchange with the highest volume.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            Tuple of (exchange, volume)
        """
        snapshot = await self.get_snapshot(symbol, exchanges)
        if snapshot.highest_volume:
            return snapshot.highest_volume.exchange, snapshot.highest_volume.volume
        return None, None

    async def get_volume_share(
        self,
        symbol: str,
        exchange: str,
        exchanges: Optional[List[str]] = None,
    ) -> Optional[float]:
        """
        Get volume share for an exchange.

        Args:
            symbol: Trading pair symbol
            exchange: Exchange name
            exchanges: List of exchanges to query

        Returns:
            Volume share percentage
        """
        snapshot = await self.get_snapshot(symbol, exchanges)
        return snapshot.get_volume_share(exchange)

    async def is_liquid_enough(
        self,
        symbol: str,
        quantity: Union[float, Decimal, str],
        exchanges: Optional[List[str]] = None,
        min_volume_ratio: float = 0.01,
    ) -> bool:
        """
        Check if a trade of given quantity is liquid enough.

        Args:
            symbol: Trading pair symbol
            quantity: Trade quantity
            exchanges: List of exchanges to query
            min_volume_ratio: Minimum volume ratio required

        Returns:
            True if liquid enough, False otherwise
        """
        quantity_decimal = self._to_decimal(quantity)
        if quantity_decimal is None or quantity_decimal <= 0:
            return False

        snapshot = await self.get_snapshot(symbol, exchanges)

        if not snapshot.total_volume:
            return False

        # Check if quantity is less than min_volume_ratio of total volume
        ratio = quantity_decimal / snapshot.total_volume
        return ratio <= min_volume_ratio

    async def clear(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> None:
        """
        Clear stored volume data.

        Args:
            exchange: Exchange to clear (all if None)
            symbol: Symbol to clear (all if None)
        """
        async with self._lock:
            if exchange:
                if symbol:
                    if exchange in self._volumes and symbol in self._volumes[exchange]:
                        del self._volumes[exchange][symbol]
                    if exchange in self._volume_history and symbol in self._volume_history[exchange]:
                        del self._volume_history[exchange][symbol]
                else:
                    if exchange in self._volumes:
                        del self._volumes[exchange]
                    if exchange in self._volume_history:
                        del self._volume_history[exchange]
            else:
                self._volumes.clear()
                self._volume_history.clear()
                self._volume_updates.clear()
                self._last_update.clear()
                self._volume_averages.clear()

        logger.info(f"Volume data cleared for {exchange or 'all'}:{symbol or 'all'}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        now = time.time()
        recent_updates = [t for t in self._last_update.values() if now - t < 60]
        update_rate = len(recent_updates) / 60 if recent_updates else 0

        return {
            **self._metrics,
            'exchanges_tracked': len(self._volumes),
            'symbols_tracked': sum(len(volumes) for volumes in self._volumes.values()),
            'total_volume_updates': sum(self._volume_updates.values()),
            'volume_updates_by_exchange': dict(self._volume_updates),
            'last_update_by_exchange': {
                k: datetime.fromtimestamp(v).isoformat()
                for k, v in self._last_update.items()
            },
            'update_rate_per_sec': update_rate,
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _to_decimal(self, value: Union[float, Decimal, str, None]) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except:
                return None
        return Decimal(str(value))

    def _determine_volume_quality(
        self,
        exchange: str,
        symbol: str,
        volume: Decimal,
        quote_volume: Optional[Decimal],
    ) -> VolumeQuality:
        """Determine volume quality."""
        # Check if volume is zero
        if volume == 0:
            return VolumeQuality.POOR

        # Check if volume is too low
        if volume < Decimal('0.001'):
            return VolumeQuality.POOR
        elif volume < Decimal('0.01'):
            return VolumeQuality.FAIR
        elif volume < Decimal('1'):
            return VolumeQuality.GOOD

        # Check quote volume if available
        if quote_volume is not None and quote_volume == 0:
            return VolumeQuality.SUSPICIOUS

        # Check age
        age = 0
        if exchange in self._last_update:
            age = time.time() - self._last_update[exchange]

        if age > 300:
            return VolumeQuality.FAIR
        elif age > 120:
            return VolumeQuality.GOOD

        return VolumeQuality.EXCELLENT

    def _determine_volume_level(self, volume: Decimal) -> VolumeLevel:
        """Determine volume level."""
        volume_float = float(volume)

        if volume_float >= self._volume_levels[VolumeLevel.EXTREMELY_HIGH]:
            return VolumeLevel.EXTREMELY_HIGH
        elif volume_float >= self._volume_levels[VolumeLevel.VERY_HIGH]:
            return VolumeLevel.VERY_HIGH
        elif volume_float >= self._volume_levels[VolumeLevel.HIGH]:
            return VolumeLevel.HIGH
        elif volume_float >= self._volume_levels[VolumeLevel.MEDIUM]:
            return VolumeLevel.MEDIUM
        elif volume_float >= self._volume_levels[VolumeLevel.LOW]:
            return VolumeLevel.LOW
        elif volume_float >= self._volume_levels[VolumeLevel.VERY_LOW]:
            return VolumeLevel.VERY_LOW
        elif volume_float > 0:
            return VolumeLevel.EXTREMELY_LOW
        else:
            return VolumeLevel.NO_VOLUME

    def _determine_volume_trend(
        self,
        exchange: str,
        symbol: str,
        current_volume: Decimal,
    ) -> VolumeTrend:
        """Determine volume trend."""
        # Get historical volumes
        history = self._volume_history.get(exchange, {}).get(symbol, deque())

        if len(history) < 5:
            return VolumeTrend.UNKNOWN

        # Get recent volumes
        recent_volumes = [v.volume for v in list(history)[-10:]]
        if len(recent_volumes) < 5:
            return VolumeTrend.UNKNOWN

        # Calculate trend
        first_half = recent_volumes[:len(recent_volumes)//2]
        second_half = recent_volumes[len(recent_volumes)//2:]

        if not first_half or not second_half:
            return VolumeTrend.UNKNOWN

        first_avg = sum(first_half) / Decimal(len(first_half))
        second_avg = sum(second_half) / Decimal(len(second_half))

        if first_avg == 0:
            return VolumeTrend.UNKNOWN

        change_pct = float((second_avg - first_avg) / first_avg * 100)

        # Calculate volatility
        volumes_float = [float(v) for v in recent_volumes]
        volatility = statistics.stdev(volumes_float) / statistics.mean(volumes_float) if statistics.mean(volumes_float) > 0 else 0

        if volatility > 0.5:
            return VolumeTrend.VOLATILE
        elif change_pct > self._trend_thresholds['strong_increasing']:
            return VolumeTrend.STRONG_INCREASING
        elif change_pct > self._trend_thresholds['increasing']:
            return VolumeTrend.INCREASING
        elif change_pct < self._trend_thresholds['strong_decreasing']:
            return VolumeTrend.STRONG_DECREASING
        elif change_pct < self._trend_thresholds['decreasing']:
            return VolumeTrend.DECREASING
        else:
            return VolumeTrend.STABLE

    def _calculate_confidence(
        self,
        volume: Decimal,
        quote_volume: Optional[Decimal],
        volume_24h: Optional[Decimal],
    ) -> float:
        """Calculate confidence score."""
        confidence = 1.0

        # Check volume
        if volume <= 0:
            confidence *= 0.5
        elif volume < Decimal('0.001'):
            confidence *= 0.7
        elif volume < Decimal('0.01'):
            confidence *= 0.8

        # Check quote volume
        if quote_volume is not None:
            if quote_volume <= 0:
                confidence *= 0.8
            elif quote_volume < Decimal('0.001'):
                confidence *= 0.9

        # Check 24h volume ratio
        if volume_24h is not None and volume_24h > 0:
            ratio = float(volume / volume_24h)
            if ratio > 1:
                confidence *= 0.9
            elif ratio < 0.001:
                confidence *= 0.8

        return max(0.1, min(1.0, confidence))

    async def _validate_volume_data(self, volume_data: VolumeData) -> bool:
        """Validate volume data."""
        # Check volume
        if volume_data.volume < 0:
            return False

        # Check quote volume
        if volume_data.quote_volume is not None and volume_data.quote_volume < 0:
            return False

        # Check 24h volume
        if volume_data.volume_24h is not None and volume_data.volume_24h < 0:
            return False

        # Check if volume is too high (suspicious)
        if volume_data.volume_24h is not None and volume_data.volume_24h > 0:
            if volume_data.volume > volume_data.volume_24h * Decimal('100'):
                return False

        return True

    async def _detect_volume_anomalies(self, volume_data: VolumeData) -> None:
        """Detect volume anomalies."""
        # Get recent volumes
        history = await self.get_volume_history(volume_data.exchange, volume_data.symbol)

        if len(history) < MIN_VOLUME_SAMPLES:
            return

        volumes = [v.volume for v in history[-50:]]
        mean_volume = sum(volumes) / Decimal(len(volumes))
        std_volume = Decimal(str(np.std([float(v) for v in volumes]))) if len(volumes) > 1 else Decimal('0')

        if std_volume == 0:
            return

        # Calculate z-score
        zscore = abs(float(volume_data.volume - mean_volume) / float(std_volume))

        if zscore > VOLUME_ANOMALY_THRESHOLD:
            self._metrics['anomalies_detected'] += 1
            logger.warning(
                "Volume anomaly detected: %s:%s volume=%s zscore=%.2f",
                volume_data.exchange, volume_data.symbol, volume_data.volume, zscore
            )

    async def _update_volume_averages(self, exchange: str, symbol: str) -> None:
        """Update volume averages."""
        history = await self.get_volume_history(exchange, symbol, limit=50)

        if len(history) < MIN_VOLUME_SAMPLES:
            return

        volumes = [v.volume for v in history]
        mean_volume = sum(volumes) / Decimal(len(volumes))
        median_volume = sorted(volumes)[len(volumes) // 2]
        std_volume = Decimal(str(np.std([float(v) for v in volumes]))) if len(volumes) > 1 else Decimal('0')

        if exchange not in self._volume_averages:
            self._volume_averages[exchange] = {}
        
        self._volume_averages[exchange][symbol] = {
            'mean': mean_volume,
            'median': median_volume,
            'std': std_volume,
            'count': len(volumes),
            'updated_at': datetime.utcnow().isoformat(),
        }

    def _calculate_volume_trend(
        self,
        volumes: List[Decimal],
    ) -> Tuple[VolumeTrend, float]:
        """Calculate volume trend and strength."""
        if len(volumes) < 5:
            return VolumeTrend.UNKNOWN, 0.0

        # Use linear regression on log volumes
        x = np.arange(len(volumes))
        y = np.log([float(v) + 1e-10 for v in volumes])  # Avoid log(0)

        try:
            slope, intercept = np.polyfit(x, y, 1)
            
            # Determine trend based on slope
            if slope > 0.02:
                if slope > 0.05:
                    return VolumeTrend.STRONG_INCREASING, abs(slope)
                return VolumeTrend.INCREASING, abs(slope)
            elif slope < -0.02:
                if slope < -0.05:
                    return VolumeTrend.STRONG_DECREASING, abs(slope)
                return VolumeTrend.DECREASING, abs(slope)
            else:
                # Check for volatility
                recent_volatility = statistics.stdev([float(v) for v in volumes[-10:]]) if len(volumes) >= 10 else 0
                mean_volume = statistics.mean([float(v) for v in volumes])
                
                if mean_volume > 0 and recent_volatility / mean_volume > 0.5:
                    return VolumeTrend.VOLATILE, 0.0
                
                return VolumeTrend.STABLE, 0.0
        except:
            return VolumeTrend.UNKNOWN, 0.0

    async def _cache_set(self, key: str, value: Any) -> None:
        """Set cache value."""
        if self.redis:
            try:
                await self.redis.setex(
                    key,
                    self.cache_ttl,
                    json.dumps(value, default=str),
                )
            except Exception as e:
                logger.warning(f"Failed to set cache: {e}")
        else:
            self._cache[key] = value
            self._cache_timestamps[key] = time.time()

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Get cache value."""
        if self.redis:
            try:
                data = await self.redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Failed to get cache: {e}")
        else:
            if key in self._cache:
                if time.time() - self._cache_timestamps[key] < self.cache_ttl:
                    return self._cache[key]
                else:
                    del self._cache[key]
                    del self._cache_timestamps[key]

        return None

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the volume manager."""
        self._running = True
        logger.info("VolumeManager started")

    async def stop(self) -> None:
        """Stop the volume manager."""
        self._running = False
        await self.clear()
        logger.info("VolumeManager stopped")

    async def __aenter__(self) -> 'VolumeManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_volume_manager(
    price_manager: PriceManager,
    ticker_manager: Optional[TickerManager] = None,
    config: Optional[VolumeManagerConfig] = None,
    redis_client: Optional[Any] = None,
    cache_ttl: int = 5,
) -> VolumeManager:
    """
    Create a volume manager instance.

    Args:
        price_manager: PriceManager instance
        ticker_manager: TickerManager instance (optional)
        config: Configuration instance
        redis_client: Redis client for caching
        cache_ttl: Cache TTL in seconds

    Returns:
        VolumeManager instance
    """
    return VolumeManager(
        price_manager=price_manager,
        ticker_manager=ticker_manager,
        config=config,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the volume manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize price manager
        from .price_manager import create_price_manager
        price_manager = create_price_manager()

        # Initialize volume manager
        volume_manager = create_volume_manager(price_manager)

        # Update some prices
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            volume=123.45,
        )

        await price_manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            volume=67.89,
        )

        # Update volumes
        await volume_manager.update_volume(
            exchange="binance",
            symbol="BTC-USDT",
            volume=123.45,
            quote_volume=5555250.0,
            volume_24h=1000000.0,
        )

        await volume_manager.update_volume(
            exchange="bybit",
            symbol="BTC-USDT",
            volume=67.89,
            quote_volume=3055000.0,
            volume_24h=500000.0,
        )

        # Get snapshot
        snapshot = await volume_manager.get_snapshot("BTC-USDT")
        print(f"Snapshot: {json.dumps(snapshot.to_dict(), indent=2, default=str)}")

        # Get volume statistics
        stats = await volume_manager.get_volume_statistics("binance", "BTC-USDT")
        print(f"Statistics: {stats.to_dict()}")

        # Get volume anomalies
        anomalies = await volume_manager.get_volume_anomalies("BTC-USDT")
        for anomaly in anomalies:
            print(f"Anomaly: {anomaly.to_dict()}")

        # Get highest volume exchange
        exchange, volume = await volume_manager.get_highest_volume_exchange("BTC-USDT")
        print(f"Highest volume: {exchange} - {volume}")

        # Get volume share
        share = await volume_manager.get_volume_share("BTC-USDT", "binance")
        print(f"Binance volume share: {share:.2f}%")

        # Check liquidity
        liquid = await volume_manager.is_liquid_enough("BTC-USDT", 0.01)
        print(f"Is liquid enough: {liquid}")

        # Get metrics
        metrics = volume_manager.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")

        await volume_manager.stop()
        await price_manager.stop()

    asyncio.run(main())
