"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Ticker Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced ticker management system with:
- Real-time ticker data aggregation from multiple exchanges
- Ticker normalization and validation
- 24h price change tracking
- Volume analysis
- High/Low price tracking
- Ticker anomaly detection
- Multi-exchange ticker comparison
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
from .base import BaseTickerManager
from .exceptions import (
    TickerManagerError,
    TickerValidationError,
    TickerNotFoundError,
    TickerTimeoutError,
)
from .price_manager import PriceManager, PriceSource
from .config import TickerManagerConfig
from .constants import (
    TICKER_CACHE_TTL,
    MAX_TICKER_HISTORY,
    MIN_TICKER_SAMPLES,
    TICKER_ANOMALY_THRESHOLD,
    DEFAULT_VOLUME_THRESHOLD,
    DEFAULT_CHANGE_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class TickerQuality(str, Enum):
    """Quality of ticker data."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    STALE = "stale"
    INVALID = "invalid"


class TickerTrend(str, Enum):
    """Price trend direction."""
    STRONG_UP = "strong_up"
    UP = "up"
    SIDEWAYS = "sideways"
    DOWN = "down"
    STRONG_DOWN = "strong_down"
    VOLATILE = "volatile"


class VolumeLevel(str, Enum):
    """Volume level classification."""
    EXTREMELY_HIGH = "extremely_high"
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"
    EXTREMELY_LOW = "extremely_low"


# ============================================================
# DATA MODELS
# ============================================================

class TickerData(BaseModel):
    """Represents ticker data for a trading pair."""
    
    exchange: str
    symbol: str
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    quote_volume: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    open_24h: Optional[Decimal] = None
    close_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_pct_24h: Optional[float] = None
    volume_24h: Optional[Decimal] = None
    quote_volume_24h: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    exchange_timestamp: Optional[datetime] = None
    source_type: str = "spot"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality: TickerQuality = TickerQuality.GOOD
    trend: TickerTrend = TickerTrend.SIDEWAYS
    volume_level: VolumeLevel = VolumeLevel.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError(f"Price must be positive: {v}")
        return v

    @validator('volume', 'quote_volume', 'volume_24h', 'quote_volume_24h', each=True)
    def validate_volume(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"Volume must be non-negative: {v}")
        return v

    @root_validator
    def validate_bid_ask(cls, values):
        bid = values.get('bid')
        ask = values.get('ask')
        if bid is not None and ask is not None and bid >= ask:
            logger.warning(f"Invalid bid/ask: bid {bid} >= ask {ask}")
        return values

    @root_validator
    def validate_24h_prices(cls, values):
        high = values.get('high_24h')
        low = values.get('low_24h')
        price = values.get('price')
        
        if high is not None and low is not None and high < low:
            raise ValueError(f"High {high} must be >= low {low}")
        
        if high is not None and price is not None and high < price:
            logger.warning(f"24h high {high} < current price {price}")
        
        if low is not None and price is not None and low > price:
            logger.warning(f"24h low {low} > current price {price}")
        
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'price': str(self.price),
            'bid': str(self.bid) if self.bid else None,
            'ask': str(self.ask) if self.ask else None,
            'volume': str(self.volume) if self.volume else None,
            'quote_volume': str(self.quote_volume) if self.quote_volume else None,
            'high_24h': str(self.high_24h) if self.high_24h else None,
            'low_24h': str(self.low_24h) if self.low_24h else None,
            'open_24h': str(self.open_24h) if self.open_24h else None,
            'close_24h': str(self.close_24h) if self.close_24h else None,
            'change_24h': str(self.change_24h) if self.change_24h else None,
            'change_pct_24h': self.change_pct_24h,
            'volume_24h': str(self.volume_24h) if self.volume_24h else None,
            'quote_volume_24h': str(self.quote_volume_24h) if self.quote_volume_24h else None,
            'timestamp': self.timestamp.isoformat(),
            'exchange_timestamp': self.exchange_timestamp.isoformat() if self.exchange_timestamp else None,
            'source_type': self.source_type,
            'confidence': self.confidence,
            'quality': self.quality.value if isinstance(self.quality, TickerQuality) else self.quality,
            'trend': self.trend.value if isinstance(self.trend, TickerTrend) else self.trend,
            'volume_level': self.volume_level.value if isinstance(self.volume_level, VolumeLevel) else self.volume_level,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TickerData':
        """Create TickerData from dictionary."""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'exchange_timestamp' in data and isinstance(data['exchange_timestamp'], str):
            data['exchange_timestamp'] = datetime.fromisoformat(data['exchange_timestamp'])
        if 'quality' in data and isinstance(data['quality'], str):
            data['quality'] = TickerQuality(data['quality'])
        if 'trend' in data and isinstance(data['trend'], str):
            data['trend'] = TickerTrend(data['trend'])
        if 'volume_level' in data and isinstance(data['volume_level'], str):
            data['volume_level'] = VolumeLevel(data['volume_level'])
        return cls(**data)

    def get_mid_price(self) -> Optional[Decimal]:
        """Get mid price from bid/ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.price

    def get_spread(self) -> Optional[Decimal]:
        """Get spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    def get_spread_pct(self) -> Optional[float]:
        """Get spread percentage."""
        spread = self.get_spread()
        if spread is not None and self.bid is not None and self.bid > 0:
            return float(spread / self.bid * 100)
        return None

    def get_volume_usd(self) -> Optional[Decimal]:
        """Get volume in USD."""
        if self.volume and self.price:
            return self.volume * self.price
        return self.quote_volume

    def get_volume_24h_usd(self) -> Optional[Decimal]:
        """Get 24h volume in USD."""
        if self.volume_24h and self.price:
            return self.volume_24h * self.price
        return self.quote_volume_24h

    def is_active(self, max_age_seconds: int = 60) -> bool:
        """Check if ticker is active."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age <= max_age_seconds

    def has_complete_data(self) -> bool:
        """Check if ticker has complete data."""
        return all([
            self.price is not None,
            self.volume is not None,
            self.high_24h is not None,
            self.low_24h is not None,
            self.change_pct_24h is not None,
        ])


@dataclass
class TickerSnapshot:
    """Complete ticker snapshot across exchanges."""
    
    timestamp: datetime
    symbol: str
    tickers: Dict[str, TickerData]  # exchange -> TickerData
    consolidated_price: Optional[Decimal] = None
    consolidated_volume: Optional[Decimal] = None
    average_price: Optional[Decimal] = None
    median_price: Optional[Decimal] = None
    price_std: Optional[float] = None
    price_range: Optional[Decimal] = None
    average_change_pct: Optional[float] = None
    total_volume_24h: Optional[Decimal] = None
    exchange_count: int = 0
    active_exchange_count: int = 0
    anomaly_detected: bool = False
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    best_price: Optional[TickerData] = None
    worst_price: Optional[TickerData] = None
    highest_volume: Optional[TickerData] = None
    highest_change: Optional[TickerData] = None
    lowest_change: Optional[TickerData] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_ticker_for_exchange(self, exchange: str) -> Optional[TickerData]:
        """Get ticker for a specific exchange."""
        return self.tickers.get(exchange)

    def get_exchanges(self) -> Set[str]:
        """Get all exchanges in snapshot."""
        return set(self.tickers.keys())

    def get_active_exchanges(self, max_age_seconds: int = 60) -> List[str]:
        """Get exchanges with recent tickers."""
        active = []
        for exchange, ticker in self.tickers.items():
            if ticker.is_active(max_age_seconds):
                active.append(exchange)
        return active

    def get_price_ranking(self) -> List[Tuple[str, Decimal]]:
        """Get price ranking across exchanges."""
        ranking = []
        for exchange, ticker in self.tickers.items():
            ranking.append((exchange, ticker.price))
        return sorted(ranking, key=lambda x: x[1])

    def get_volume_ranking(self) -> List[Tuple[str, Decimal]]:
        """Get volume ranking across exchanges."""
        ranking = []
        for exchange, ticker in self.tickers.items():
            if ticker.volume:
                ranking.append((exchange, ticker.volume))
        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def get_change_ranking(self) -> List[Tuple[str, float]]:
        """Get change percentage ranking across exchanges."""
        ranking = []
        for exchange, ticker in self.tickers.items():
            if ticker.change_pct_24h is not None:
                ranking.append((exchange, ticker.change_pct_24h))
        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def get_best_price_exchange(self) -> Optional[str]:
        """Get exchange with the best (lowest) price."""
        if self.best_price:
            return self.best_price.exchange
        return None

    def get_worst_price_exchange(self) -> Optional[str]:
        """Get exchange with the worst (highest) price."""
        if self.worst_price:
            return self.worst_price.exchange
        return None

    def get_highest_volume_exchange(self) -> Optional[str]:
        """Get exchange with the highest volume."""
        if self.highest_volume:
            return self.highest_volume.exchange
        return None

    def get_price_disparity(self) -> Optional[float]:
        """Get price disparity as coefficient of variation."""
        if not self.tickers or self.price_std is None or self.average_price is None:
            return None
        if self.average_price == 0:
            return None
        return self.price_std / float(self.average_price)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'tickers': {
                k: v.to_dict()
                for k, v in self.tickers.items()
            },
            'consolidated_price': str(self.consolidated_price) if self.consolidated_price else None,
            'consolidated_volume': str(self.consolidated_volume) if self.consolidated_volume else None,
            'average_price': str(self.average_price) if self.average_price else None,
            'median_price': str(self.median_price) if self.median_price else None,
            'price_std': self.price_std,
            'price_range': str(self.price_range) if self.price_range else None,
            'average_change_pct': self.average_change_pct,
            'total_volume_24h': str(self.total_volume_24h) if self.total_volume_24h else None,
            'exchange_count': self.exchange_count,
            'active_exchange_count': self.active_exchange_count,
            'anomaly_detected': self.anomaly_detected,
            'anomalies': self.anomalies,
            'best_price': self.best_price.to_dict() if self.best_price else None,
            'worst_price': self.worst_price.to_dict() if self.worst_price else None,
            'highest_volume': self.highest_volume.to_dict() if self.highest_volume else None,
            'highest_change': self.highest_change.to_dict() if self.highest_change else None,
            'lowest_change': self.lowest_change.to_dict() if self.lowest_change else None,
            'metadata': self.metadata,
        }


@dataclass
class TickerStatistics:
    """Statistical analysis of ticker data."""
    
    symbol: str
    exchange: str
    price_mean: Decimal
    price_median: Decimal
    price_std: Decimal
    price_min: Decimal
    price_max: Decimal
    price_range: Decimal
    volume_mean: Decimal
    volume_median: Decimal
    volume_std: Decimal
    volume_total: Decimal
    change_mean: float
    change_median: float
    change_std: float
    change_min: float
    change_max: float
    volatility: float
    sample_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'price_mean': str(self.price_mean),
            'price_median': str(self.price_median),
            'price_std': str(self.price_std),
            'price_min': str(self.price_min),
            'price_max': str(self.price_max),
            'price_range': str(self.price_range),
            'volume_mean': str(self.volume_mean),
            'volume_median': str(self.volume_median),
            'volume_std': str(self.volume_std),
            'volume_total': str(self.volume_total),
            'change_mean': self.change_mean,
            'change_median': self.change_median,
            'change_std': self.change_std,
            'change_min': self.change_min,
            'change_max': self.change_max,
            'volatility': self.volatility,
            'sample_count': self.sample_count,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# TICKER MANAGER IMPLEMENTATION
# ============================================================

class TickerManager(BaseTickerManager):
    """
    Advanced ticker manager with:
    - Real-time ticker aggregation
    - Multi-exchange ticker comparison
    - 24h price change tracking
    - Volume analysis
    - Ticker anomaly detection
    - Historical ticker tracking
    """

    def __init__(
        self,
        price_manager: PriceManager,
        config: Optional[TickerManagerConfig] = None,
        redis_client: Optional[Any] = None,
        cache_ttl: int = 5,
    ):
        """
        Initialize ticker manager.

        Args:
            price_manager: PriceManager instance
            config: Configuration instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
        """
        self.price_manager = price_manager
        self.config = config or TickerManagerConfig()
        self.redis = redis_client
        self.cache_ttl = cache_ttl

        # Ticker storage
        self._tickers: Dict[str, Dict[str, TickerData]] = {}  # exchange -> symbol -> TickerData
        self._ticker_history: Dict[str, Dict[str, deque]] = {}  # exchange -> symbol -> deque of tickers
        self._ticker_updates: Dict[str, int] = {}
        self._last_update: Dict[str, float] = {}

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

        # Quality thresholds
        self._quality_thresholds = {
            'max_age_seconds': 60,
            'min_confidence': 0.5,
            'min_volume': Decimal('0.01'),
            'max_change_pct': 100,
            'min_change_pct': -100,
        }

        # Volume levels thresholds
        self._volume_thresholds = {
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
            'strong_up': 5.0,
            'up': 1.0,
            'down': -1.0,
            'strong_down': -5.0,
            'volatile': 3.0,
        }

        logger.info("TickerManager initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def update_ticker(
        self,
        exchange: str,
        symbol: str,
        price: Union[float, Decimal, str],
        bid: Optional[Union[float, Decimal, str]] = None,
        ask: Optional[Union[float, Decimal, str]] = None,
        volume: Optional[Union[float, Decimal, str]] = None,
        quote_volume: Optional[Union[float, Decimal, str]] = None,
        high_24h: Optional[Union[float, Decimal, str]] = None,
        low_24h: Optional[Union[float, Decimal, str]] = None,
        open_24h: Optional[Union[float, Decimal, str]] = None,
        close_24h: Optional[Union[float, Decimal, str]] = None,
        volume_24h: Optional[Union[float, Decimal, str]] = None,
        quote_volume_24h: Optional[Union[float, Decimal, str]] = None,
        exchange_timestamp: Optional[datetime] = None,
        source_type: str = "spot",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TickerData:
        """
        Update ticker data for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            price: Current price
            bid: Bid price (optional)
            ask: Ask price (optional)
            volume: Current volume (optional)
            quote_volume: Current quote volume (optional)
            high_24h: 24h high (optional)
            low_24h: 24h low (optional)
            open_24h: 24h open (optional)
            close_24h: 24h close (optional)
            volume_24h: 24h volume (optional)
            quote_volume_24h: 24h quote volume (optional)
            exchange_timestamp: Exchange timestamp
            source_type: Source type
            metadata: Additional metadata

        Returns:
            TickerData instance
        """
        start_time = time.perf_counter()

        try:
            # Convert values
            price_decimal = self._to_decimal(price)
            bid_decimal = self._to_decimal(bid) if bid is not None else None
            ask_decimal = self._to_decimal(ask) if ask is not None else None
            volume_decimal = self._to_decimal(volume) if volume is not None else None
            quote_volume_decimal = self._to_decimal(quote_volume) if quote_volume is not None else None
            high_24h_decimal = self._to_decimal(high_24h) if high_24h is not None else None
            low_24h_decimal = self._to_decimal(low_24h) if low_24h is not None else None
            open_24h_decimal = self._to_decimal(open_24h) if open_24h is not None else None
            close_24h_decimal = self._to_decimal(close_24h) if close_24h is not None else None
            volume_24h_decimal = self._to_decimal(volume_24h) if volume_24h is not None else None
            quote_volume_24h_decimal = self._to_decimal(quote_volume_24h) if quote_volume_24h is not None else None

            # Validate price
            if price_decimal is None or price_decimal <= 0:
                raise TickerValidationError(f"Invalid price: {price_decimal}")

            # Validate bid/ask
            if bid_decimal is not None and ask_decimal is not None and bid_decimal >= ask_decimal:
                logger.warning(f"Invalid bid/ask: bid {bid_decimal} >= ask {ask_decimal}")
                # Adjust
                mid = (bid_decimal + ask_decimal) / 2
                bid_decimal = mid * Decimal('0.9995')
                ask_decimal = mid * Decimal('1.0005')

            # Calculate 24h change
            change_24h = None
            change_pct_24h = None

            if open_24h_decimal is not None and open_24h_decimal > 0:
                change_24h = price_decimal - open_24h_decimal
                change_pct_24h = float(change_24h / open_24h_decimal * 100)

            # Validate 24h prices
            if high_24h_decimal is not None and low_24h_decimal is not None:
                if high_24h_decimal < low_24h_decimal:
                    raise TickerValidationError(f"High {high_24h_decimal} >= low {low_24h_decimal}")

            # Determine quality
            quality = self._determine_ticker_quality(
                exchange, symbol, price_decimal, volume_decimal
            )

            # Determine trend
            trend = self._determine_trend(exchange, symbol, change_pct_24h)

            # Determine volume level
            volume_level = self._determine_volume_level(volume_decimal)

            # Calculate confidence
            confidence = self._calculate_confidence(
                price_decimal, bid_decimal, ask_decimal, volume_decimal
            )

            # Create ticker data
            ticker_data = TickerData(
                exchange=exchange,
                symbol=symbol,
                price=price_decimal,
                bid=bid_decimal,
                ask=ask_decimal,
                volume=volume_decimal,
                quote_volume=quote_volume_decimal,
                high_24h=high_24h_decimal,
                low_24h=low_24h_decimal,
                open_24h=open_24h_decimal,
                close_24h=close_24h_decimal or price_decimal,
                change_24h=change_24h,
                change_pct_24h=change_pct_24h,
                volume_24h=volume_24h_decimal,
                quote_volume_24h=quote_volume_24h_decimal,
                timestamp=datetime.utcnow(),
                exchange_timestamp=exchange_timestamp or datetime.utcnow(),
                source_type=source_type,
                confidence=confidence,
                quality=quality,
                trend=trend,
                volume_level=volume_level,
                metadata=metadata or {},
            )

            # Validate ticker
            if not await self._validate_ticker(ticker_data):
                raise TickerValidationError(f"Ticker validation failed for {exchange}:{symbol}")

            # Store ticker
            async with self._lock:
                if exchange not in self._tickers:
                    self._tickers[exchange] = {}
                self._tickers[exchange][symbol] = ticker_data

                # Update history
                if exchange not in self._ticker_history:
                    self._ticker_history[exchange] = {}
                if symbol not in self._ticker_history[exchange]:
                    self._ticker_history[exchange][symbol] = deque(maxlen=MAX_TICKER_HISTORY)
                self._ticker_history[exchange][symbol].append(ticker_data)

                # Update metrics
                self._ticker_updates[exchange] = self._ticker_updates.get(exchange, 0) + 1
                self._last_update[exchange] = time.time()
                self._metrics['total_updates'] += 1
                self._metrics['successful_updates'] += 1

            # Cache ticker
            await self._cache_set(f"ticker:{exchange}:{symbol}", ticker_data.to_dict())

            # Detect anomalies
            await self._detect_ticker_anomalies(ticker_data)

            # Update latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._metrics['avg_update_latency_ms'] = (
                self._metrics['avg_update_latency_ms'] * 0.9 + latency_ms * 0.1
            )
            self._metrics['last_update_timestamp'] = datetime.utcnow().isoformat()

            logger.debug(
                "Ticker updated for %s:%s = %s (change: %.2f%%, volume: %s)",
                exchange, symbol, price_decimal, change_pct_24h or 0, volume_decimal
            )

            return ticker_data

        except Exception as e:
            self._metrics['failed_updates'] += 1
            logger.error(f"Failed to update ticker for {exchange}:{symbol}: {e}")
            raise TickerManagerError(f"Failed to update ticker: {e}")

    async def update_ticker_from_price(
        self,
        exchange: str,
        symbol: str,
        price_source: PriceSource,
        high_24h: Optional[Union[float, Decimal, str]] = None,
        low_24h: Optional[Union[float, Decimal, str]] = None,
        open_24h: Optional[Union[float, Decimal, str]] = None,
        volume_24h: Optional[Union[float, Decimal, str]] = None,
    ) -> TickerData:
        """
        Update ticker from a PriceSource.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            price_source: PriceSource instance
            high_24h: 24h high (optional)
            low_24h: 24h low (optional)
            open_24h: 24h open (optional)
            volume_24h: 24h volume (optional)

        Returns:
            TickerData instance
        """
        return await self.update_ticker(
            exchange=exchange,
            symbol=symbol,
            price=price_source.price,
            bid=price_source.bid,
            ask=price_source.ask,
            volume=price_source.volume,
            quote_volume=price_source.quote_volume,
            high_24h=high_24h,
            low_24h=low_24h,
            open_24h=open_24h,
            volume_24h=volume_24h,
            exchange_timestamp=price_source.exchange_timestamp,
            source_type=price_source.source_type.value if hasattr(price_source.source_type, 'value') else str(price_source.source_type),
        )

    async def get_ticker(
        self,
        exchange: str,
        symbol: str,
        use_cache: bool = True,
    ) -> Optional[TickerData]:
        """
        Get ticker for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            use_cache: Whether to use cache

        Returns:
            TickerData or None
        """
        # Check cache
        if use_cache:
            cached = await self._cache_get(f"ticker:{exchange}:{symbol}")
            if cached:
                try:
                    return TickerData.from_dict(cached)
                except Exception as e:
                    logger.warning(f"Failed to parse cached ticker: {e}")

        # Check memory
        async with self._lock:
            if exchange in self._tickers and symbol in self._tickers[exchange]:
                return self._tickers[exchange][symbol]

        return None

    async def get_tickers_for_symbol(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        max_age_seconds: int = 60,
    ) -> Dict[str, TickerData]:
        """
        Get tickers for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_confidence: Minimum confidence score
            max_age_seconds: Maximum age of ticker data

        Returns:
            Dict mapping exchange to TickerData
        """
        result = {}
        exchanges = exchanges or list(self._tickers.keys())

        for exchange in exchanges:
            ticker = await self.get_ticker(exchange, symbol)
            if ticker:
                if (ticker.confidence >= min_confidence and 
                    ticker.is_active(max_age_seconds)):
                    result[exchange] = ticker

        return result

    async def get_snapshot(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_confidence: float = 0.5,
        max_age_seconds: int = 60,
    ) -> TickerSnapshot:
        """
        Get a complete ticker snapshot.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_confidence: Minimum confidence score
            max_age_seconds: Maximum age of ticker data

        Returns:
            TickerSnapshot instance
        """
        tickers = await self.get_tickers_for_symbol(
            symbol, exchanges, min_confidence, max_age_seconds
        )

        if not tickers:
            raise TickerNotFoundError(f"No tickers found for {symbol}")

        # Calculate statistics
        prices = [t.price for t in tickers.values()]
        volumes = [t.volume for t in tickers.values() if t.volume is not None]
        changes = [t.change_pct_24h for t in tickers.values() if t.change_pct_24h is not None]

        # Price statistics
        average_price = sum(prices) / Decimal(len(prices))
        median_price = sorted(prices)[len(prices) // 2]
        price_std = Decimal(str(np.std([float(p) for p in prices]))) if len(prices) > 1 else Decimal('0')
        price_range = max(prices) - min(prices) if prices else Decimal('0')

        # Volume statistics
        total_volume = sum((v for v in volumes if v is not None), Decimal('0'))

        # Change statistics
        avg_change = statistics.mean(changes) if changes else 0

        # Find best and worst prices
        best_price = min(tickers.values(), key=lambda t: t.price)
        worst_price = max(tickers.values(), key=lambda t: t.price)

        # Find highest volume
        highest_volume = max(
            [t for t in tickers.values() if t.volume is not None],
            key=lambda t: t.volume or Decimal('0'),
            default=None,
        )

        # Find highest and lowest change
        highest_change = None
        lowest_change = None
        tickers_with_change = [t for t in tickers.values() if t.change_pct_24h is not None]
        if tickers_with_change:
            highest_change = max(tickers_with_change, key=lambda t: t.change_pct_24h or -float('inf'))
            lowest_change = min(tickers_with_change, key=lambda t: t.change_pct_24h or float('inf'))

        # Detect anomalies
        anomalies = []
        anomaly_detected = False

        for exchange, ticker in tickers.items():
            # Price anomaly
            price_float = float(ticker.price)
            avg_float = float(average_price)
            if avg_float > 0:
                deviation = abs(price_float - avg_float) / avg_float * 100
                if deviation > TICKER_ANOMALY_THRESHOLD:
                    anomalies.append({
                        'exchange': exchange,
                        'type': 'price',
                        'price': str(ticker.price),
                        'deviation_pct': deviation,
                    })
                    anomaly_detected = True

            # Volume anomaly
            if total_volume > 0 and ticker.volume:
                volume_float = float(ticker.volume)
                total_float = float(total_volume)
                volume_ratio = volume_float / total_float if total_float > 0 else 0
                if volume_ratio > 0.5:
                    anomalies.append({
                        'exchange': exchange,
                        'type': 'volume',
                        'volume': str(ticker.volume),
                        'volume_ratio': volume_ratio,
                    })
                    anomaly_detected = True

            # Change anomaly
            if changes and ticker.change_pct_24h is not None:
                change_std = statistics.stdev(changes) if len(changes) > 1 else 1
                if change_std > 0:
                    change_zscore = abs(ticker.change_pct_24h - avg_change) / change_std
                    if change_zscore > 3:
                        anomalies.append({
                            'exchange': exchange,
                            'type': 'change',
                            'change_pct': ticker.change_pct_24h,
                            'zscore': change_zscore,
                        })
                        anomaly_detected = True

        # Calculate active exchange count
        active_count = len([t for t in tickers.values() if t.is_active(max_age_seconds)])

        # Create snapshot
        snapshot = TickerSnapshot(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            tickers=tickers,
            consolidated_price=average_price,
            consolidated_volume=total_volume,
            average_price=average_price,
            median_price=median_price,
            price_std=float(price_std) if price_std else None,
            price_range=price_range,
            average_change_pct=avg_change,
            total_volume_24h=total_volume,
            exchange_count=len(tickers),
            active_exchange_count=active_count,
            anomaly_detected=anomaly_detected,
            anomalies=anomalies,
            best_price=best_price,
            worst_price=worst_price,
            highest_volume=highest_volume,
            highest_change=highest_change,
            lowest_change=lowest_change,
            metadata={
                'min_confidence': min_confidence,
                'max_age_seconds': max_age_seconds,
                'exchanges_queried': list(tickers.keys()),
            },
        )

        # Cache snapshot
        await self._cache_set(f"snapshot:ticker:{symbol}", snapshot.to_dict())

        logger.info(
            "Ticker snapshot for %s: %d exchanges, avg price: %s, total volume: %s",
            symbol, snapshot.exchange_count, average_price, total_volume
        )

        return snapshot

    async def get_ticker_statistics(
        self,
        exchange: str,
        symbol: str,
        window: int = 100,
    ) -> TickerStatistics:
        """
        Get statistical analysis of ticker data.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            window: Window size for statistics

        Returns:
            TickerStatistics instance
        """
        # Get ticker history
        async with self._lock:
            if exchange not in self._ticker_history:
                raise TickerNotFoundError(f"No ticker history for {exchange}:{symbol}")
            if symbol not in self._ticker_history[exchange]:
                raise TickerNotFoundError(f"No ticker history for {exchange}:{symbol}")

            history = list(self._ticker_history[exchange][symbol])
            if not history:
                raise TickerNotFoundError(f"No ticker history for {exchange}:{symbol}")

            recent = history[-window:]

        # Price statistics
        prices = [t.price for t in recent]
        price_mean = sum(prices) / Decimal(len(prices))
        price_median = sorted(prices)[len(prices) // 2]
        price_std = Decimal(str(np.std([float(p) for p in prices]))) if len(prices) > 1 else Decimal('0')
        price_min = min(prices)
        price_max = max(prices)
        price_range = price_max - price_min

        # Volume statistics
        volumes = [t.volume for t in recent if t.volume is not None]
        if volumes:
            volume_mean = sum(volumes) / Decimal(len(volumes))
            volume_median = sorted(volumes)[len(volumes) // 2]
            volume_std = Decimal(str(np.std([float(v) for v in volumes]))) if len(volumes) > 1 else Decimal('0')
            volume_total = sum(volumes)
        else:
            volume_mean = Decimal('0')
            volume_median = Decimal('0')
            volume_std = Decimal('0')
            volume_total = Decimal('0')

        # Change statistics
        changes = [t.change_pct_24h for t in recent if t.change_pct_24h is not None]
        if changes:
            change_mean = statistics.mean(changes)
            change_median = statistics.median(changes)
            change_std = statistics.stdev(changes) if len(changes) > 1 else 0
            change_min = min(changes)
            change_max = max(changes)
            volatility = change_std
        else:
            change_mean = 0
            change_median = 0
            change_std = 0
            change_min = 0
            change_max = 0
            volatility = 0

        return TickerStatistics(
            symbol=symbol,
            exchange=exchange,
            price_mean=price_mean,
            price_median=price_median,
            price_std=price_std,
            price_min=price_min,
            price_max=price_max,
            price_range=price_range,
            volume_mean=volume_mean,
            volume_median=volume_median,
            volume_std=volume_std,
            volume_total=volume_total,
            change_mean=change_mean,
            change_median=change_median,
            change_std=change_std,
            change_min=change_min,
            change_max=change_max,
            volatility=volatility,
            sample_count=len(recent),
        )

    async def get_ticker_history(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[TickerData]:
        """
        Get ticker history for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            limit: Maximum number of tickers to return

        Returns:
            List of TickerData
        """
        async with self._lock:
            if exchange not in self._ticker_history:
                return []
            if symbol not in self._ticker_history[exchange]:
                return []

            history = list(self._ticker_history[exchange][symbol])
            return history[-limit:]

    async def get_best_price_exchange(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], Optional[Decimal]]:
        """
        Get exchange with the best (lowest) price.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            Tuple of (exchange, price)
        """
        snapshot = await self.get_snapshot(symbol, exchanges)
        if snapshot.best_price:
            return snapshot.best_price.exchange, snapshot.best_price.price
        return None, None

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

    async def clear(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> None:
        """
        Clear stored ticker data.

        Args:
            exchange: Exchange to clear (all if None)
            symbol: Symbol to clear (all if None)
        """
        async with self._lock:
            if exchange:
                if symbol:
                    if exchange in self._tickers and symbol in self._tickers[exchange]:
                        del self._tickers[exchange][symbol]
                    if exchange in self._ticker_history and symbol in self._ticker_history[exchange]:
                        del self._ticker_history[exchange][symbol]
                else:
                    if exchange in self._tickers:
                        del self._tickers[exchange]
                    if exchange in self._ticker_history:
                        del self._ticker_history[exchange]
            else:
                self._tickers.clear()
                self._ticker_history.clear()
                self._ticker_updates.clear()
                self._last_update.clear()

        logger.info(f"Ticker data cleared for {exchange or 'all'}:{symbol or 'all'}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        now = time.time()
        recent_updates = [t for t in self._last_update.values() if now - t < 60]
        update_rate = len(recent_updates) / 60 if recent_updates else 0

        return {
            **self._metrics,
            'exchanges_tracked': len(self._tickers),
            'symbols_tracked': sum(len(tickers) for tickers in self._tickers.values()),
            'total_ticker_updates': sum(self._ticker_updates.values()),
            'ticker_updates_by_exchange': dict(self._ticker_updates),
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

    def _determine_ticker_quality(
        self,
        exchange: str,
        symbol: str,
        price: Decimal,
        volume: Optional[Decimal],
    ) -> TickerQuality:
        """Determine ticker quality."""
        # Check volume
        if volume is None or volume <= 0:
            return TickerQuality.POOR

        # Check age
        age = 0
        if exchange in self._last_update:
            age = time.time() - self._last_update[exchange]

        if age > 300:
            return TickerQuality.STALE
        elif age > 120:
            return TickerQuality.FAIR
        elif age > 60:
            return TickerQuality.GOOD

        # Check volume threshold
        if volume < Decimal('0.001'):
            return TickerQuality.POOR
        elif volume < Decimal('0.01'):
            return TickerQuality.FAIR
        elif volume < Decimal('1'):
            return TickerQuality.GOOD

        return TickerQuality.EXCELLENT

    def _determine_trend(
        self,
        exchange: str,
        symbol: str,
        change_pct: Optional[float],
    ) -> TickerTrend:
        """Determine price trend."""
        if change_pct is None:
            return TickerTrend.SIDEWAYS

        # Get historical change
        history = self._ticker_history.get(exchange, {}).get(symbol, deque())
        recent_changes = []
        if len(history) > 1:
            recent_changes = [
                t.change_pct_24h for t in list(history)[-10:]
                if t.change_pct_24h is not None
            ]

        # Calculate volatility
        volatility = 0
        if recent_changes and len(recent_changes) > 1:
            volatility = statistics.stdev(recent_changes)

        # Determine trend
        if change_pct > self._trend_thresholds['strong_up']:
            return TickerTrend.STRONG_UP
        elif change_pct > self._trend_thresholds['up']:
            return TickerTrend.UP
        elif change_pct < self._trend_thresholds['strong_down']:
            return TickerTrend.STRONG_DOWN
        elif change_pct < self._trend_thresholds['down']:
            return TickerTrend.DOWN

        # Check volatility
        if volatility > self._trend_thresholds['volatile']:
            return TickerTrend.VOLATILE

        return TickerTrend.SIDEWAYS

    def _determine_volume_level(self, volume: Optional[Decimal]) -> VolumeLevel:
        """Determine volume level."""
        if volume is None:
            return VolumeLevel.MEDIUM

        volume_float = float(volume)

        if volume_float >= self._volume_thresholds[VolumeLevel.EXTREMELY_HIGH]:
            return VolumeLevel.EXTREMELY_HIGH
        elif volume_float >= self._volume_thresholds[VolumeLevel.VERY_HIGH]:
            return VolumeLevel.VERY_HIGH
        elif volume_float >= self._volume_thresholds[VolumeLevel.HIGH]:
            return VolumeLevel.HIGH
        elif volume_float >= self._volume_thresholds[VolumeLevel.MEDIUM]:
            return VolumeLevel.MEDIUM
        elif volume_float >= self._volume_thresholds[VolumeLevel.LOW]:
            return VolumeLevel.LOW
        elif volume_float >= self._volume_thresholds[VolumeLevel.VERY_LOW]:
            return VolumeLevel.VERY_LOW
        else:
            return VolumeLevel.EXTREMELY_LOW

    def _calculate_confidence(
        self,
        price: Decimal,
        bid: Optional[Decimal],
        ask: Optional[Decimal],
        volume: Optional[Decimal],
    ) -> float:
        """Calculate confidence score."""
        confidence = 1.0

        # Check price
        if price <= 0:
            confidence *= 0.5

        # Check bid/ask
        if bid is not None and ask is not None:
            spread_pct = abs(float(ask - bid) / float(price) * 100)
            if spread_pct > 5:
                confidence *= 0.8
            elif spread_pct > 10:
                confidence *= 0.5

        # Check volume
        if volume is None or volume <= 0:
            confidence *= 0.7
        elif volume < Decimal('0.001'):
            confidence *= 0.8
        elif volume < Decimal('0.01'):
            confidence *= 0.9

        return max(0.1, min(1.0, confidence))

    async def _validate_ticker(self, ticker: TickerData) -> bool:
        """Validate ticker data."""
        # Check price
        if ticker.price <= 0:
            return False

        # Check volume
        if ticker.volume is not None and ticker.volume < 0:
            return False

        # Check 24h change
        if ticker.change_pct_24h is not None:
            if (ticker.change_pct_24h > self._quality_thresholds['max_change_pct'] or
                ticker.change_pct_24h < self._quality_thresholds['min_change_pct']):
                return False

        # Check 24h prices
        if ticker.high_24h is not None and ticker.low_24h is not None:
            if ticker.high_24h < ticker.low_24h:
                return False

            # Check if current price is within 24h range
            if (ticker.price > ticker.high_24h or 
                ticker.price < ticker.low_24h):
                # Allow slight deviation (1%)
                tolerance = ticker.price * Decimal('0.01')
                if (ticker.price - ticker.high_24h > tolerance or
                    ticker.low_24h - ticker.price > tolerance):
                    return False

        return True

    async def _detect_ticker_anomalies(self, ticker: TickerData) -> None:
        """Detect ticker anomalies."""
        # Get recent tickers
        history = await self.get_ticker_history(ticker.exchange, ticker.symbol)

        if len(history) < MIN_TICKER_SAMPLES:
            return

        # Check price anomaly
        prices = [t.price for t in history[-50:]]
        mean_price = sum(prices) / Decimal(len(prices))
        std_price = Decimal(str(np.std([float(p) for p in prices]))) if len(prices) > 1 else Decimal('0')

        if std_price > 0:
            zscore = abs(float(ticker.price - mean_price) / float(std_price))
            if zscore > 3:
                self._metrics['anomalies_detected'] += 1
                logger.warning(
                    "Ticker anomaly detected: %s:%s price=%s zscore=%.2f",
                    ticker.exchange, ticker.symbol, ticker.price, zscore
                )

        # Check volume anomaly
        if ticker.volume:
            volumes = [t.volume for t in history[-50:] if t.volume is not None]
            if volumes and len(volumes) > 1:
                mean_volume = sum(volumes) / Decimal(len(volumes))
                std_volume = Decimal(str(np.std([float(v) for v in volumes])))
                if std_volume > 0:
                    volume_zscore = abs(float(ticker.volume - mean_volume) / float(std_volume))
                    if volume_zscore > 3:
                        self._metrics['anomalies_detected'] += 1
                        logger.warning(
                            "Volume anomaly detected: %s:%s volume=%s zscore=%.2f",
                            ticker.exchange, ticker.symbol, ticker.volume, volume_zscore
                        )

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
        """Start the ticker manager."""
        self._running = True
        logger.info("TickerManager started")

    async def stop(self) -> None:
        """Stop the ticker manager."""
        self._running = False
        await self.clear()
        logger.info("TickerManager stopped")

    async def __aenter__(self) -> 'TickerManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_ticker_manager(
    price_manager: PriceManager,
    config: Optional[TickerManagerConfig] = None,
    redis_client: Optional[Any] = None,
    cache_ttl: int = 5,
) -> TickerManager:
    """
    Create a ticker manager instance.

    Args:
        price_manager: PriceManager instance
        config: Configuration instance
        redis_client: Redis client for caching
        cache_ttl: Cache TTL in seconds

    Returns:
        TickerManager instance
    """
    return TickerManager(
        price_manager=price_manager,
        config=config,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the ticker manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize price manager
        from .price_manager import create_price_manager
        price_manager = create_price_manager()

        # Initialize ticker manager
        ticker_manager = create_ticker_manager(price_manager)

        # Update ticker
        ticker = await ticker_manager.update_ticker(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
            high_24h=46000.0,
            low_24h=44000.0,
            open_24h=44500.0,
            volume_24h=1000000.0,
        )
        print(f"Ticker: {ticker.to_dict()}")

        # Get snapshot
        snapshot = await ticker_manager.get_snapshot("BTC-USDT")
        print(f"Snapshot: {json.dumps(snapshot.to_dict(), indent=2, default=str)}")

        # Get statistics
        stats = await ticker_manager.get_ticker_statistics("binance", "BTC-USDT")
        print(f"Statistics: {stats.to_dict()}")

        # Get best price exchange
        best_exchange, best_price = await ticker_manager.get_best_price_exchange("BTC-USDT")
        print(f"Best price: {best_exchange} - {best_price}")

        # Get metrics
        metrics = ticker_manager.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")

        await ticker_manager.stop()
        await price_manager.stop()

    asyncio.run(main())
