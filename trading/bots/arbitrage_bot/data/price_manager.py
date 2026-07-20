"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Price Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced price management system for arbitrage detection with:
- Real-time price aggregation from multiple exchanges
- Price normalization and validation
- Spread calculation with fee consideration
- Price anomaly detection
- Caching and rate limiting
"""

import asyncio
import hashlib
import json
import logging
import math
import os
import pickle
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from enum import Enum
from functools import lru_cache, wraps
from threading import Lock
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

import aiohttp
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
    after_log,
)

# Redis imports with fallback
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

# Optional imports for advanced features
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    IsolationForest = None

# Local imports
from .base import BasePriceManager
from .exceptions import (
    PriceManagerError,
    PriceValidationError,
    PriceTimeoutError,
    PriceNotFoundError,
    RateLimitExceededError,
    ExchangeConnectionError,
    DataNormalizationError,
)
from .data_normalizer import DataNormalizer
from .data_cache import DataCache
from .config import PriceManagerConfig
from .constants import (
    DEFAULT_FEE_RATES,
    EXCHANGE_FEE_RATES,
    PRICE_CACHE_TTL,
    MAX_PRICE_HISTORY,
    ANOMALY_THRESHOLD,
    MIN_PRICE_AGE_SECONDS,
    MAX_PRICE_AGE_SECONDS,
    PRICE_UPDATE_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_WAIT_SECONDS,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class PriceSourceType(str, Enum):
    """Type of price source."""
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    MARGIN = "margin"
    OPTION = "option"
    INDEX = "index"
    DERIVED = "derived"


class PriceConsensusMethod(str, Enum):
    """Method for price consensus calculation."""
    MEAN = "mean"
    MEDIAN = "median"
    WEIGHTED = "weighted"
    CONSENSUS = "consensus"
    ROBUST = "robust"
    TRIM_MEAN = "trim_mean"
    VWAP = "vwap"
    TWAP = "twap"


class AnomalyDetectionMethod(str, Enum):
    """Method for anomaly detection."""
    ZSCORE = "zscore"
    IQR = "iqr"
    ISOLATION_FOREST = "isolation_forest"
    MAD = "mad"  # Median Absolute Deviation
    GRUBBS = "grubbs"
    EWMA = "ewma"
    HODRICK_PRESCOTT = "hodrick_prescott"
    WAVELET = "wavelet"


# ============================================================
# DATA MODELS
# ============================================================

class PriceSource(BaseModel):
    """Represents a price source with metadata."""
    
    exchange: str
    symbol: str
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    quote_volume: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: Optional[float] = None
    source_type: PriceSourceType = PriceSourceType.SPOT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    raw_data: Optional[Dict[str, Any]] = None
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange_timestamp: Optional[datetime] = None
    processing_time_ms: Optional[float] = None
    is_synthetic: bool = False
    synthetic_source: Optional[str] = None

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError(f"Price must be positive: {v}")
        return v

    @validator('bid', 'ask', each=True)
    def validate_bid_ask(cls, v, values):
        if v is not None and v <= 0:
            raise ValueError(f"Bid/Ask must be positive: {v}")
        if v is not None and 'price' in values:
            price = values['price']
            if abs(float(v) - float(price)) / float(price) > 0.5:
                logger.warning(f"Bid/Ask {v} far from price {price}")
        return v

    @root_validator
    def validate_bid_ask_relationship(cls, values):
        bid = values.get('bid')
        ask = values.get('ask')
        if bid is not None and ask is not None and bid >= ask:
            logger.warning(f"Invalid bid/ask spread: bid {bid} >= ask {ask}")
            # Adjust to ensure bid < ask
            price = values.get('price', (bid + ask) / 2)
            values['bid'] = price * Decimal('0.9995')
            values['ask'] = price * Decimal('1.0005')
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.dict(exclude={'timestamp', 'raw_data', 'exchange_timestamp'}),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'exchange_timestamp': self.exchange_timestamp.isoformat() if self.exchange_timestamp else None,
            'price': str(self.price),
            'bid': str(self.bid) if self.bid else None,
            'ask': str(self.ask) if self.ask else None,
            'volume': str(self.volume) if self.volume else None,
            'quote_volume': str(self.quote_volume) if self.quote_volume else None,
            'source_type': self.source_type.value if isinstance(self.source_type, PriceSourceType) else self.source_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceSource':
        """Create PriceSource from dictionary."""
        data = data.copy()
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'exchange_timestamp' in data and isinstance(data['exchange_timestamp'], str):
            data['exchange_timestamp'] = datetime.fromisoformat(data['exchange_timestamp'])
        if 'source_type' in data and isinstance(data['source_type'], str):
            data['source_type'] = PriceSourceType(data['source_type'])
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


@dataclass
class NormalizedPrice:
    """Normalized price with derived metrics."""
    
    exchange: str
    symbol: str
    price: Decimal
    bid: Optional[Decimal]
    ask: Optional[Decimal]
    spread: Optional[Decimal]
    spread_pct: Optional[float]
    mid_price: Optional[Decimal]
    timestamp: datetime
    source_type: PriceSourceType
    confidence: float
    fee_rate: Optional[Decimal] = None
    effective_price_buy: Optional[Decimal] = None
    effective_price_sell: Optional[Decimal] = None
    normalized_score: float = 1.0
    volume: Optional[Decimal] = None
    quote_volume: Optional[Decimal] = None
    quality_score: float = 1.0
    normalized_price: Optional[Decimal] = None
    normalized_spread: Optional[Decimal] = None
    spread_to_market_pct: Optional[float] = None
    
    def __post_init__(self):
        if self.bid is not None and self.ask is not None:
            self.spread = self.ask - self.bid
            if self.bid > 0:
                self.spread_pct = float((self.ask - self.bid) / self.bid * 100)
            self.mid_price = (self.bid + self.ask) / 2
        else:
            self.spread = None
            self.spread_pct = None
            self.mid_price = self.price
        
        if self.fee_rate is not None:
            if self.mid_price is not None:
                self.normalized_price = self.mid_price * (Decimal('1') + self.fee_rate)
            else:
                self.normalized_price = self.price * (Decimal('1') + self.fee_rate)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'price': str(self.price),
            'bid': str(self.bid) if self.bid else None,
            'ask': str(self.ask) if self.ask else None,
            'spread': str(self.spread) if self.spread else None,
            'spread_pct': self.spread_pct,
            'mid_price': str(self.mid_price) if self.mid_price else None,
            'timestamp': self.timestamp.isoformat(),
            'source_type': self.source_type.value if isinstance(self.source_type, PriceSourceType) else self.source_type,
            'confidence': self.confidence,
            'fee_rate': str(self.fee_rate) if self.fee_rate else None,
            'effective_price_buy': str(self.effective_price_buy) if self.effective_price_buy else None,
            'effective_price_sell': str(self.effective_price_sell) if self.effective_price_sell else None,
            'normalized_score': self.normalized_score,
            'volume': str(self.volume) if self.volume else None,
            'quote_volume': str(self.quote_volume) if self.quote_volume else None,
            'quality_score': self.quality_score,
            'normalized_price': str(self.normalized_price) if self.normalized_price else None,
            'normalized_spread': str(self.normalized_spread) if self.normalized_spread else None,
            'spread_to_market_pct': self.spread_to_market_pct,
        }


@dataclass
class PriceSnapshot:
    """Complete price snapshot across exchanges."""
    
    timestamp: datetime
    symbol: str
    prices: Dict[str, NormalizedPrice]
    consolidated_price: Optional[Decimal] = None
    weighted_price: Optional[Decimal] = None
    median_price: Optional[Decimal] = None
    trim_mean_price: Optional[Decimal] = None
    robust_price: Optional[Decimal] = None
    price_std: Optional[float] = None
    price_mad: Optional[float] = None
    price_iqr: Optional[float] = None
    exchange_count: int = 0
    anomaly_detected: bool = False
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    market_price: Optional[Decimal] = None
    market_spread: Optional[Decimal] = None
    market_spread_pct: Optional[float] = None
    volume_weighted_price: Optional[Decimal] = None
    total_volume: Optional[Decimal] = None
    best_bid: Optional[Tuple[str, Decimal]] = None
    best_ask: Optional[Tuple[str, Decimal]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    consensus_method: str = "weighted"
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def get_price_for_exchange(self, exchange: str) -> Optional[Decimal]:
        """Get price for a specific exchange."""
        if exchange in self.prices:
            return self.prices[exchange].price
        return None

    def get_normalized_price_for_exchange(self, exchange: str) -> Optional[Decimal]:
        """Get normalized price for a specific exchange."""
        if exchange in self.prices:
            return self.prices[exchange].normalized_price or self.prices[exchange].price
        return None

    def get_exchanges(self) -> Set[str]:
        """Get all exchanges in snapshot."""
        return set(self.prices.keys())

    def get_active_exchanges(self) -> List[str]:
        """Get exchanges with recent prices."""
        now = datetime.utcnow()
        active = []
        for exchange, price in self.prices.items():
            age = (now - price.timestamp).total_seconds()
            if age < 60:
                active.append(exchange)
        return active

    def get_best_bid(self) -> Tuple[Optional[str], Optional[Decimal]]:
        """Get highest bid across all exchanges."""
        best = None
        best_exchange = None
        for exchange, price in self.prices.items():
            if price.bid is not None:
                if best is None or price.bid > best:
                    best = price.bid
                    best_exchange = exchange
        return best_exchange, best

    def get_best_ask(self) -> Tuple[Optional[str], Optional[Decimal]]:
        """Get lowest ask across all exchanges."""
        best = None
        best_exchange = None
        for exchange, price in self.prices.items():
            if price.ask is not None:
                if best is None or price.ask < best:
                    best = price.ask
                    best_exchange = exchange
        return best_exchange, best

    def get_widest_spread(self) -> Tuple[Optional[str], Optional[Decimal], Optional[float]]:
        """Get exchange with widest spread."""
        widest = None
        widest_exchange = None
        for exchange, price in self.prices.items():
            if price.spread is not None:
                if widest is None or price.spread > widest:
                    widest = price.spread
                    widest_exchange = exchange
        if widest_exchange:
            return widest_exchange, widest, self.prices[widest_exchange].spread_pct
        return None, None, None

    def get_price_disparity(self) -> Optional[float]:
        """Get price disparity as coefficient of variation."""
        if not self.prices or self.price_std is None or self.consolidated_price is None:
            return None
        if self.consolidated_price == 0:
            return None
        return self.price_std / float(self.consolidated_price)

    def get_exchange_rankings(self, metric: str = "price") -> List[Tuple[str, Decimal]]:
        """Get exchange rankings by price."""
        if metric == "price":
            items = [(e, p.price) for e, p in self.prices.items()]
        elif metric == "normalized_price":
            items = [(e, p.normalized_price or p.price) for e, p in self.prices.items()]
        elif metric == "spread":
            items = [(e, p.spread or Decimal('0')) for e, p in self.prices.items()]
        elif metric == "confidence":
            items = [(e, Decimal(str(p.confidence))) for e, p in self.prices.items()]
        else:
            items = [(e, p.price) for e, p in self.prices.items()]
        
        return sorted(items, key=lambda x: x[1])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'prices': {
                k: v.to_dict()
                for k, v in self.prices.items()
            },
            'consolidated_price': str(self.consolidated_price) if self.consolidated_price else None,
            'weighted_price': str(self.weighted_price) if self.weighted_price else None,
            'median_price': str(self.median_price) if self.median_price else None,
            'trim_mean_price': str(self.trim_mean_price) if self.trim_mean_price else None,
            'robust_price': str(self.robust_price) if self.robust_price else None,
            'price_std': self.price_std,
            'price_mad': self.price_mad,
            'price_iqr': self.price_iqr,
            'exchange_count': self.exchange_count,
            'anomaly_detected': self.anomaly_detected,
            'anomalies': self.anomalies,
            'market_price': str(self.market_price) if self.market_price else None,
            'market_spread': str(self.market_spread) if self.market_spread else None,
            'market_spread_pct': self.market_spread_pct,
            'volume_weighted_price': str(self.volume_weighted_price) if self.volume_weighted_price else None,
            'total_volume': str(self.total_volume) if self.total_volume else None,
            'best_bid': (self.best_bid[0], str(self.best_bid[1])) if self.best_bid else None,
            'best_ask': (self.best_ask[0], str(self.best_ask[1])) if self.best_ask else None,
            'metadata': self.metadata,
            'consensus_method': self.consensus_method,
            'validation_passed': self.validation_passed,
            'validation_errors': self.validation_errors,
        }


@dataclass
class PriceUpdateResult:
    """Result of a price update operation."""
    
    success: bool
    exchange: str
    symbol: str
    price: Optional[Decimal] = None
    normalized_price: Optional[NormalizedPrice] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cache_hit: bool = False
    source_type: PriceSourceType = PriceSourceType.SPOT
    quality_score: float = 1.0


@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity details."""
    
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    gross_profit: Decimal
    gross_profit_pct: float
    net_profit: Decimal
    net_profit_pct: float
    fees: Dict[str, Any]
    volume: Optional[Decimal] = None
    max_volume: Optional[Decimal] = None
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    spread: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_profitable(self, min_profit_pct: float = 0.1) -> bool:
        """Check if opportunity is profitable."""
        return self.net_profit_pct >= min_profit_pct

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'buy_exchange': self.buy_exchange,
            'sell_exchange': self.sell_exchange,
            'buy_price': str(self.buy_price),
            'sell_price': str(self.sell_price),
            'gross_profit': str(self.gross_profit),
            'gross_profit_pct': self.gross_profit_pct,
            'net_profit': str(self.net_profit),
            'net_profit_pct': self.net_profit_pct,
            'fees': self.fees,
            'volume': str(self.volume) if self.volume else None,
            'max_volume': str(self.max_volume) if self.max_volume else None,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'spread': self.spread,
            'metadata': self.metadata,
        }


# ============================================================
# PRICE MANAGER IMPLEMENTATION
# ============================================================

class PriceManager(BasePriceManager):
    """
    Advanced price manager for arbitrage detection with:
    - Multi-exchange price aggregation
    - Real-time price normalization
    - Spread and fee calculations
    - Price anomaly detection using statistical methods
    - Smart caching with TTL
    - Configurable rate limiting
    - Comprehensive metrics
    """

    def __init__(
        self,
        config: Optional[PriceManagerConfig] = None,
        redis_client: Optional[redis.Redis] = None,
        cache_ttl: int = 5,
        enable_advanced_metrics: bool = True,
    ):
        """
        Initialize price manager.

        Args:
            config: Configuration instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
            enable_advanced_metrics: Enable advanced metrics collection
        """
        self.config = config or PriceManagerConfig()
        self.redis = redis_client
        self.cache = DataCache(redis_client, default_ttl=cache_ttl)
        self.enable_advanced_metrics = enable_advanced_metrics

        # Price storage
        self._prices: Dict[str, Dict[str, PriceSource]] = {}
        self._price_history: Dict[str, Dict[str, deque]] = {}
        self._price_updates: Dict[str, int] = {}
        self._last_update: Dict[str, float] = {}
        self._quality_scores: Dict[str, Dict[str, float]] = {}
        self._price_aggregates: Dict[str, Dict[str, Any]] = {}

        # Exchange availability tracking
        self._exchange_status: Dict[str, Dict[str, Any]] = {}
        self._exchange_latency: Dict[str, List[float]] = defaultdict(list)

        # Metrics
        self._metrics = {
            'total_updates': 0,
            'successful_updates': 0,
            'failed_updates': 0,
            'anomalies_detected': 0,
            'avg_latency_ms': 0,
            'min_latency_ms': float('inf'),
            'max_latency_ms': 0,
            'last_update_timestamp': None,
            'update_rate_per_sec': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'price_validation_errors': 0,
            'exchange_errors': 0,
        }
        self._update_timestamps: deque = deque(maxlen=100)

        # Lock for thread safety
        self._lock = asyncio.Lock()
        self._thread_lock = Lock()

        # Fee rates per exchange
        self._fee_rates: Dict[str, Dict[str, Decimal]] = {
            'binance': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'bybit': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'coinbase': {'taker': Decimal('0.005'), 'maker': Decimal('0.004')},
            'kraken': {'taker': Decimal('0.0026'), 'maker': Decimal('0.0016')},
            'okx': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'gateio': {'taker': Decimal('0.002'), 'maker': Decimal('0.001')},
            'kucoin': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'mexc': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'bitget': {'taker': Decimal('0.001'), 'maker': Decimal('0.0008')},
            'huobi': {'taker': Decimal('0.002'), 'maker': Decimal('0.001')},
            'ftx': {'taker': Decimal('0.0007'), 'maker': Decimal('0.0005')},
            'deribit': {'taker': Decimal('0.0005'), 'maker': Decimal('0.0005')},
            'bitmex': {'taker': Decimal('0.00075'), 'maker': Decimal('0.00025')},
        }

        # Normalizer
        self._normalizer = DataNormalizer()

        # Rate limiting
        self._rate_limiters: Dict[str, asyncio.Semaphore] = {}
        self._last_rate_limit_reset: Dict[str, float] = {}
        self._rate_limit_counts: Dict[str, int] = {}

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._running = False

        # Price quality thresholds
        self._quality_thresholds = {
            'min_confidence': 0.5,
            'min_volume': Decimal('0.01'),
            'max_age_seconds': 30,
            'min_exchanges': 2,
        }

        # Anomaly detection configuration
        self._anomaly_config = {
            'zscore_threshold': 3.0,
            'iqr_multiplier': 1.5,
            'mad_threshold': 3.0,
            'min_samples': 10,
            'window_size': 50,
        }

        # Initialize isolation forest if available
        self._isolation_forest = None
        if SKLEARN_AVAILABLE and IsolationForest:
            self._isolation_forest = IsolationForest(
                contamination=0.05,
                random_state=42,
                n_estimators=100,
            )
            self._anomaly_features: List[Dict[str, float]] = []

        logger.info("PriceManager initialized with config: %s", config)

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((PriceTimeoutError, ConnectionError, aiohttp.ClientError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def update_price(
        self,
        exchange: str,
        symbol: str,
        price: Union[float, Decimal, str],
        bid: Optional[Union[float, Decimal, str]] = None,
        ask: Optional[Union[float, Decimal, str]] = None,
        volume: Optional[Union[float, Decimal, str]] = None,
        quote_volume: Optional[Union[float, Decimal, str]] = None,
        raw_data: Optional[Dict[str, Any]] = None,
        source_type: Union[str, PriceSourceType] = PriceSourceType.SPOT,
        exchange_timestamp: Optional[datetime] = None,
        quality_score: float = 1.0,
    ) -> NormalizedPrice:
        """
        Update price for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol (e.g., BTC-USDT)
            price: Current price
            bid: Bid price (optional)
            ask: Ask price (optional)
            volume: Trading volume (optional)
            quote_volume: Quote currency volume (optional)
            raw_data: Raw exchange data
            source_type: Source type (spot, futures, perpetual, margin)
            exchange_timestamp: Exchange timestamp
            quality_score: Quality score for this price

        Returns:
            NormalizedPrice instance
        """
        start_time = time.perf_counter()

        try:
            # Validate inputs
            price_decimal = self._to_decimal(price)
            bid_decimal = self._to_decimal(bid) if bid is not None else None
            ask_decimal = self._to_decimal(ask) if ask is not None else None
            volume_decimal = self._to_decimal(volume) if volume is not None else None
            quote_volume_decimal = self._to_decimal(quote_volume) if quote_volume is not None else None

            # Validate price
            if price_decimal is None or price_decimal <= 0:
                raise PriceValidationError(f"Invalid price: {price_decimal}")

            # Validate bid/ask
            if bid_decimal is not None and bid_decimal <= 0:
                raise PriceValidationError(f"Invalid bid: {bid_decimal}")
            if ask_decimal is not None and ask_decimal <= 0:
                raise PriceValidationError(f"Invalid ask: {ask_decimal}")

            # Validate bid < ask if both provided
            if bid_decimal is not None and ask_decimal is not None and bid_decimal >= ask_decimal:
                logger.warning(f"Invalid bid/ask spread: bid {bid_decimal} >= ask {ask_decimal}")
                # Adjust to ensure valid spread
                mid = (bid_decimal + ask_decimal) / 2
                bid_decimal = mid * Decimal('0.9995')
                ask_decimal = mid * Decimal('1.0005')

            # Check rate limit
            await self._check_rate_limit(exchange)

            # Convert source type
            if isinstance(source_type, str):
                source_type = PriceSourceType(source_type)

            # Create price source
            price_source = PriceSource(
                exchange=exchange,
                symbol=symbol,
                price=price_decimal,
                bid=bid_decimal,
                ask=ask_decimal,
                volume=volume_decimal,
                quote_volume=quote_volume_decimal,
                timestamp=datetime.utcnow(),
                latency_ms=None,
                source_type=source_type,
                confidence=self._calculate_confidence(price_decimal, bid_decimal, ask_decimal),
                quality_score=quality_score,
                raw_data=raw_data,
                exchange_timestamp=exchange_timestamp or datetime.utcnow(),
                source_id=str(uuid.uuid4()),
            )

            # Validate price
            if not await self._validate_price(price_source):
                self._metrics['price_validation_errors'] += 1
                raise PriceValidationError(f"Price validation failed for {exchange}:{symbol}")

            # Store price
            async with self._lock:
                if exchange not in self._prices:
                    self._prices[exchange] = {}
                self._prices[exchange][symbol] = price_source

                # Update history
                if exchange not in self._price_history:
                    self._price_history[exchange] = {}
                if symbol not in self._price_history[exchange]:
                    self._price_history[exchange][symbol] = deque(maxlen=MAX_PRICE_HISTORY)
                self._price_history[exchange][symbol].append(price_decimal)

                # Update quality scores
                if exchange not in self._quality_scores:
                    self._quality_scores[exchange] = {}
                self._quality_scores[exchange][symbol] = quality_score

                # Update metrics
                self._price_updates[exchange] = self._price_updates.get(exchange, 0) + 1
                self._last_update[exchange] = time.time()
                self._metrics['total_updates'] += 1
                self._metrics['successful_updates'] += 1
                self._update_timestamps.append(time.time())

            # Cache price
            await self.cache.set(
                f"price:{exchange}:{symbol}",
                price_source.to_dict(),
                ttl=self.config.cache_ttl,
            )

            # Normalize price
            normalized = await self._normalize_price(price_source)

            # Detect anomalies
            await self._detect_anomalies(normalized)

            # Update exchange status
            self._update_exchange_status(exchange, True)

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._update_latency_metrics(exchange, latency_ms)
            self._metrics['avg_latency_ms'] = (
                self._metrics['avg_latency_ms'] * 0.9 + latency_ms * 0.1
            )
            self._metrics['min_latency_ms'] = min(
                self._metrics['min_latency_ms'], latency_ms
            )
            self._metrics['max_latency_ms'] = max(
                self._metrics['max_latency_ms'], latency_ms
            )
            self._metrics['last_update_timestamp'] = datetime.utcnow().isoformat()

            logger.debug(
                "Price updated for %s:%s = %s (latency: %.2fms, quality: %.2f)",
                exchange, symbol, price_decimal, latency_ms, quality_score
            )

            return normalized

        except Exception as e:
            self._metrics['failed_updates'] += 1
            self._update_exchange_status(exchange, False)
            logger.error(f"Failed to update price for {exchange}:{symbol}: {e}")
            raise PriceManagerError(f"Failed to update price: {e}")

    async def update_prices_batch(
        self,
        prices: List[Dict[str, Any]],
        max_concurrent: int = 10,
    ) -> List[PriceUpdateResult]:
        """
        Update multiple prices in batch.

        Args:
            prices: List of price dictionaries
            max_concurrent: Maximum concurrent updates

        Returns:
            List of PriceUpdateResult
        """
        results = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def update_single(price_data: Dict[str, Any]) -> PriceUpdateResult:
            async with semaphore:
                try:
                    normalized = await self.update_price(
                        exchange=price_data['exchange'],
                        symbol=price_data['symbol'],
                        price=price_data['price'],
                        bid=price_data.get('bid'),
                        ask=price_data.get('ask'),
                        volume=price_data.get('volume'),
                        quote_volume=price_data.get('quote_volume'),
                        raw_data=price_data.get('raw_data'),
                        source_type=price_data.get('source_type', 'spot'),
                        exchange_timestamp=price_data.get('exchange_timestamp'),
                        quality_score=price_data.get('quality_score', 1.0),
                    )
                    return PriceUpdateResult(
                        success=True,
                        exchange=price_data['exchange'],
                        symbol=price_data['symbol'],
                        price=normalized.price,
                        normalized_price=normalized,
                        latency_ms=0,
                    )
                except Exception as e:
                    return PriceUpdateResult(
                        success=False,
                        exchange=price_data['exchange'],
                        symbol=price_data['symbol'],
                        error=str(e),
                    )

        tasks = [update_single(price) for price in prices]
        results = await asyncio.gather(*tasks)

        return results

    async def get_price(
        self,
        exchange: str,
        symbol: str,
        use_cache: bool = True,
        max_age_seconds: float = 60.0,
    ) -> Optional[PriceSource]:
        """
        Get price for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            use_cache: Whether to use cache
            max_age_seconds: Maximum age of price data

        Returns:
            PriceSource or None
        """
        # Check cache first
        if use_cache:
            cached = await self.cache.get(f"price:{exchange}:{symbol}")
            if cached:
                try:
                    self._metrics['cache_hits'] += 1
                    price_source = PriceSource.from_dict(cached)
                    # Check age
                    age = (datetime.utcnow() - price_source.timestamp).total_seconds()
                    if age <= max_age_seconds:
                        return price_source
                except Exception as e:
                    logger.warning(f"Failed to parse cached price: {e}")
                    self._metrics['cache_misses'] += 1

        # Check memory
        async with self._lock:
            if exchange in self._prices and symbol in self._prices[exchange]:
                price = self._prices[exchange][symbol]
                age = (datetime.utcnow() - price.timestamp).total_seconds()
                if age <= max_age_seconds:
                    return price

        self._metrics['cache_misses'] += 1
        return None

    async def get_prices_for_symbol(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_age_seconds: float = 60.0,
        min_confidence: float = 0.5,
    ) -> Dict[str, PriceSource]:
        """
        Get prices for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query (all if None)
            min_age_seconds: Maximum age of price data
            min_confidence: Minimum confidence score

        Returns:
            Dict mapping exchange to PriceSource
        """
        result = {}
        now = datetime.utcnow()

        exchanges = exchanges or list(self._prices.keys())

        for exchange in exchanges:
            price = await self.get_price(exchange, symbol)
            if price:
                # Check age
                age = (now - price.timestamp).total_seconds()
                if age <= min_age_seconds and price.confidence >= min_confidence:
                    result[exchange] = price

        return result

    async def get_snapshot(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_age_seconds: float = 60.0,
        min_confidence: float = 0.5,
        consensus_method: str = "weighted",
        trim_ratio: float = 0.1,
    ) -> PriceSnapshot:
        """
        Get a complete price snapshot across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_age_seconds: Maximum age of price data
            min_confidence: Minimum confidence score
            consensus_method: Method for price consensus
            trim_ratio: Trim ratio for trim_mean method

        Returns:
            PriceSnapshot instance
        """
        prices = await self.get_prices_for_symbol(
            symbol, exchanges, min_age_seconds, min_confidence
        )

        if not prices:
            raise PriceNotFoundError(f"No prices found for {symbol}")

        # Normalize prices
        normalized_prices = {}
        for exchange, price_source in prices.items():
            try:
                normalized = await self._normalize_price(price_source)
                normalized_prices[exchange] = normalized
            except Exception as e:
                logger.warning(f"Failed to normalize price from {exchange}: {e}")

        if not normalized_prices:
            raise PriceNotFoundError(f"No valid normalized prices for {symbol}")

        # Get price values
        price_values = [p.price for p in normalized_prices.values()]
        price_values_decimal = [Decimal(str(p)) for p in price_values]

        # Calculate consolidated metrics
        consolidated = await self._consolidate_prices(
            normalized_prices, method=consensus_method
        )

        # Weighted price by volume
        weighted_price = await self._calculate_weighted_price(normalized_prices)

        # Median
        sorted_prices = sorted(price_values_decimal)
        median = sorted_prices[len(sorted_prices) // 2] if sorted_prices else None

        # Trim mean
        trim_mean = None
        if len(sorted_prices) > 2:
            trim_count = int(len(sorted_prices) * trim_ratio)
            trimmed = sorted_prices[trim_count:-trim_count] if trim_count > 0 else sorted_prices
            if trimmed:
                trim_mean = sum(trimmed) / Decimal(len(trimmed))

        # Standard deviation
        price_floats = [float(p) for p in price_values_decimal]
        price_std = float(np.std(price_floats)) if len(price_floats) > 1 else None

        # Median Absolute Deviation
        if len(price_floats) > 1:
            median_val = statistics.median(price_floats)
            price_mad = statistics.median([abs(x - median_val) for x in price_floats])
        else:
            price_mad = None

        # IQR
        if len(price_floats) > 1:
            q1 = np.percentile(price_floats, 25)
            q3 = np.percentile(price_floats, 75)
            price_iqr = q3 - q1
        else:
            price_iqr = None

        # Detect anomalies
        anomalies = []
        anomaly_detected = False

        for exchange, normalized in normalized_prices.items():
            is_anomaly, anomaly_data = await self._check_anomaly(
                normalized, normalized_prices, consolidated, price_std
            )
            if is_anomaly:
                anomalies.append({
                    'exchange': exchange,
                    'price': str(normalized.price),
                    'deviation': anomaly_data.get('deviation'),
                    'zscore': anomaly_data.get('zscore'),
                    'threshold': self._anomaly_config['zscore_threshold'],
                    'confidence': normalized.confidence,
                })
                anomaly_detected = True

        # Get best bid and ask
        best_bid_exchange, best_bid = self._get_best_bid(normalized_prices)
        best_ask_exchange, best_ask = self._get_best_ask(normalized_prices)

        # Calculate market metrics
        market_price = weighted_price or consolidated
        market_spread = None
        market_spread_pct = None
        if best_bid and best_ask:
            market_spread = best_ask - best_bid
            if best_bid > 0:
                market_spread_pct = float(market_spread / best_bid * 100)

        # Total volume
        total_volume = None
        for p in normalized_prices.values():
            if p.volume:
                total_volume = (total_volume or Decimal('0')) + p.volume

        # Create snapshot
        snapshot = PriceSnapshot(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            prices=normalized_prices,
            consolidated_price=consolidated,
            weighted_price=weighted_price,
            median_price=median,
            trim_mean_price=trim_mean,
            robust_price=trim_mean or consolidated,
            price_std=price_std,
            price_mad=price_mad,
            price_iqr=price_iqr,
            exchange_count=len(normalized_prices),
            anomaly_detected=anomaly_detected,
            anomalies=anomalies,
            market_price=market_price,
            market_spread=market_spread,
            market_spread_pct=market_spread_pct,
            volume_weighted_price=weighted_price,
            total_volume=total_volume,
            best_bid=(best_bid_exchange, best_bid) if best_bid else None,
            best_ask=(best_ask_exchange, best_ask) if best_ask else None,
            metadata={
                'min_age_seconds': min_age_seconds,
                'min_confidence': min_confidence,
                'exchanges_queried': list(prices.keys()),
                'consensus_method': consensus_method,
            },
            consensus_method=consensus_method,
        )

        # Cache snapshot
        if self.redis:
            await self.cache.set(
                f"snapshot:{symbol}",
                snapshot.to_dict(),
                ttl=self.config.cache_ttl,
            )

        logger.info(
            "Snapshot created for %s: %d exchanges, anomaly: %s, price: %s",
            symbol, snapshot.exchange_count, anomaly_detected, consolidated
        )

        return snapshot

    async def get_best_price(
        self,
        symbol: str,
        side: str = "buy",
        exchanges: Optional[List[str]] = None,
        min_age_seconds: float = 60.0,
        include_fees: bool = True,
    ) -> Tuple[Optional[str], Optional[Decimal], Optional[PriceSource]]:
        """
        Get the best price for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            side: "buy" or "sell"
            exchanges: List of exchanges to query
            min_age_seconds: Maximum age of price data
            include_fees: Whether to include fees in calculation

        Returns:
            Tuple of (exchange, price, price_source)
        """
        prices = await self.get_prices_for_symbol(symbol, exchanges, min_age_seconds)

        if not prices:
            return None, None, None

        best_exchange = None
        best_price = None
        best_source = None

        for exchange, price_source in prices.items():
            fee_rate = self._get_fee_rate(exchange, "taker")

            if side.lower() == "buy":
                # For buying, use ask price (lower is better)
                price = price_source.ask or price_source.price
                if include_fees:
                    price = price * (Decimal('1') + fee_rate)
                if best_price is None or price < best_price:
                    best_price = price
                    best_exchange = exchange
                    best_source = price_source
            else:
                # For selling, use bid price (higher is better)
                price = price_source.bid or price_source.price
                if include_fees:
                    price = price * (Decimal('1') - fee_rate)
                if best_price is None or price > best_price:
                    best_price = price
                    best_exchange = exchange
                    best_source = price_source

        return best_exchange, best_price, best_source

    async def get_spread(
        self,
        exchange: str,
        symbol: str,
        include_fees: bool = True,
    ) -> Tuple[Optional[Decimal], Optional[float]]:
        """
        Calculate spread for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            include_fees: Whether to include trading fees in calculation

        Returns:
            Tuple of (spread, spread_pct)
        """
        price = await self.get_price(exchange, symbol)

        if not price or price.bid is None or price.ask is None:
            return None, None

        spread = price.ask - price.bid
        spread_pct = float(spread / price.bid * 100) if price.bid > 0 else 0

        if include_fees:
            fee_rate = self._get_fee_rate(exchange, "taker")
            effective_spread = spread + (price.ask * fee_rate) + (price.bid * fee_rate)
            spread_pct = float(effective_spread / price.bid * 100) if price.bid > 0 else 0
            return effective_spread, spread_pct

        return spread, spread_pct

    async def get_arbitrage_opportunity(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_profit_pct: float = 0.5,
        min_volume: Optional[Decimal] = None,
        max_spread_pct: Optional[float] = None,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Find arbitrage opportunity for a symbol.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_profit_pct: Minimum profit percentage
            min_volume: Minimum volume requirement
            max_spread_pct: Maximum spread percentage

        Returns:
            ArbitrageOpportunity or None
        """
        snapshot = await self.get_snapshot(symbol, exchanges)

        if snapshot.exchange_count < 2:
            return None

        # Get best bid and ask
        best_bid_exchange, best_bid = snapshot.get_best_bid()
        best_ask_exchange, best_ask = snapshot.get_best_ask()

        if not best_bid or not best_ask or best_ask_exchange == best_bid_exchange:
            return None

        # Check if exchanges are different
        if best_ask_exchange == best_bid_exchange:
            return None

        # Check spread limit
        if max_spread_pct is not None:
            spread_pct = await self.get_spread(best_ask_exchange, symbol)
            if spread_pct[1] and spread_pct[1] > max_spread_pct:
                return None

        # Calculate fees
        fee_rate_bid = self._get_fee_rate(best_bid_exchange or "", "taker")
        fee_rate_ask = self._get_fee_rate(best_ask_exchange or "", "taker")

        # Effective profit after fees
        profit = best_bid - best_ask
        profit_pct = float(profit / best_ask * 100) if best_ask > 0 else 0

        # Subtract fees
        fee_cost = (best_ask * fee_rate_ask) + (best_bid * fee_rate_bid)
        net_profit = profit - fee_cost
        net_profit_pct = float(net_profit / best_ask * 100) if best_ask > 0 else 0

        if net_profit_pct < min_profit_pct:
            return None

        # Check volume
        volume = min(
            snapshot.prices[best_ask_exchange].volume or Decimal('inf'),
            snapshot.prices[best_bid_exchange].volume or Decimal('inf'),
        )
        if min_volume and (volume is None or volume < min_volume):
            return None

        # Get spread data
        spread_data = []
        for exchange, price in snapshot.prices.items():
            if price.spread_pct is not None:
                spread_data.append({
                    'exchange': exchange,
                    'spread_pct': price.spread_pct,
                })

        return ArbitrageOpportunity(
            symbol=symbol,
            buy_exchange=best_ask_exchange,
            sell_exchange=best_bid_exchange,
            buy_price=best_ask,
            sell_price=best_bid,
            gross_profit=profit,
            gross_profit_pct=profit_pct,
            net_profit=net_profit,
            net_profit_pct=net_profit_pct,
            fees={
                'buy_fee_rate': float(fee_rate_ask),
                'sell_fee_rate': float(fee_rate_bid),
                'total_fee_cost': str(fee_cost),
                'fee_amount': str(fee_cost),
            },
            volume=volume if volume != Decimal('inf') else None,
            confidence=min(
                snapshot.prices[best_ask_exchange].confidence,
                snapshot.prices[best_bid_exchange].confidence,
            ),
            spread=spread_data,
            metadata={
                'snapshot_timestamp': snapshot.timestamp.isoformat(),
                'exchange_count': snapshot.exchange_count,
                'anomaly_detected': snapshot.anomaly_detected,
            },
        )

    async def get_arbitrage_opportunities(
        self,
        symbols: List[str],
        exchanges: Optional[List[str]] = None,
        min_profit_pct: float = 0.5,
        max_opportunities: int = 10,
    ) -> List[ArbitrageOpportunity]:
        """
        Find arbitrage opportunities for multiple symbols.

        Args:
            symbols: List of trading pair symbols
            exchanges: List of exchanges to query
            min_profit_pct: Minimum profit percentage
            max_opportunities: Maximum number of opportunities to return

        Returns:
            List of ArbitrageOpportunity
        """
        opportunities = []
        tasks = []

        async def get_opportunity(symbol: str) -> Optional[ArbitrageOpportunity]:
            try:
                return await self.get_arbitrage_opportunity(
                    symbol, exchanges, min_profit_pct
                )
            except Exception as e:
                logger.warning(f"Failed to get opportunity for {symbol}: {e}")
                return None

        for symbol in symbols:
            tasks.append(get_opportunity(symbol))

        results = await asyncio.gather(*tasks)

        for result in results:
            if result:
                opportunities.append(result)

        # Sort by net profit percentage
        opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)

        return opportunities[:max_opportunities]

    async def get_price_history(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[Decimal]:
        """
        Get price history for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            limit: Maximum number of prices to return

        Returns:
            List of prices
        """
        async with self._lock:
            if exchange not in self._price_history:
                return []
            if symbol not in self._price_history[exchange]:
                return []

            history = list(self._price_history[exchange][symbol])
            return history[-limit:]

    async def get_price_statistics(
        self,
        exchange: str,
        symbol: str,
        window: int = 100,
    ) -> Dict[str, Any]:
        """
        Get price statistics for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            window: Window size for statistics

        Returns:
            Dictionary with statistics
        """
        history = await self.get_price_history(exchange, symbol, window)

        if not history:
            return {}

        prices = [float(p) for p in history]

        return {
            'count': len(prices),
            'mean': statistics.mean(prices) if len(prices) > 1 else prices[0],
            'median': statistics.median(prices) if len(prices) > 1 else prices[0],
            'std': statistics.stdev(prices) if len(prices) > 1 else 0,
            'min': min(prices),
            'max': max(prices),
            'range': max(prices) - min(prices),
            'p25': np.percentile(prices, 25) if len(prices) > 1 else prices[0],
            'p75': np.percentile(prices, 75) if len(prices) > 1 else prices[0],
            'cv': (statistics.stdev(prices) / statistics.mean(prices)) if len(prices) > 1 and statistics.mean(prices) > 0 else 0,
            'latest': prices[-1] if prices else None,
            'first': prices[0] if prices else None,
            'change': ((prices[-1] - prices[0]) / prices[0] * 100) if len(prices) > 1 and prices[0] > 0 else 0,
        }

    async def clear(
        self,
        exchange: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> None:
        """
        Clear stored price data.

        Args:
            exchange: Exchange to clear (all if None)
            symbol: Symbol to clear (all if None)
        """
        async with self._lock:
            if exchange:
                if symbol:
                    # Clear specific symbol
                    if exchange in self._prices and symbol in self._prices[exchange]:
                        del self._prices[exchange][symbol]
                    if exchange in self._price_history and symbol in self._price_history[exchange]:
                        del self._price_history[exchange][symbol]
                else:
                    # Clear entire exchange
                    if exchange in self._prices:
                        del self._prices[exchange]
                    if exchange in self._price_history:
                        del self._price_history[exchange]
            else:
                # Clear everything
                self._prices.clear()
                self._price_history.clear()
                self._price_updates.clear()
                self._last_update.clear()
                self._quality_scores.clear()

            # Clear cache
            if self.redis:
                await self.cache.clear()

        logger.info(f"Price data cleared for {exchange or 'all'}:{symbol or 'all'}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        now = time.time()
        recent_updates = [t for t in self._update_timestamps if now - t < 60]
        update_rate = len(recent_updates) / 60 if recent_updates else 0

        metrics = {
            **self._metrics,
            'exchanges_tracked': len(self._prices),
            'symbols_tracked': sum(len(prices) for prices in self._prices.values()),
            'total_price_updates': sum(self._price_updates.values()),
            'price_updates_by_exchange': dict(self._price_updates),
            'last_update_by_exchange': {
                k: datetime.fromtimestamp(v).isoformat()
                for k, v in self._last_update.items()
            },
            'update_rate_per_sec': update_rate,
            'exchange_status': self._exchange_status,
            'cache_stats': {
                'hits': self._metrics.get('cache_hits', 0),
                'misses': self._metrics.get('cache_misses', 0),
                'hit_rate': self._metrics.get('cache_hits', 0) / (
                    self._metrics.get('cache_hits', 0) + self._metrics.get('cache_misses', 0)
                ) if self._metrics.get('cache_hits', 0) + self._metrics.get('cache_misses', 0) > 0 else 0,
            },
        }

        if self.enable_advanced_metrics:
            metrics['quality_scores'] = dict(self._quality_scores)

        return metrics

    def get_exchange_status(self, exchange: str) -> Dict[str, Any]:
        """Get status for a specific exchange."""
        return self._exchange_status.get(exchange, {
            'available': False,
            'last_update': None,
            'success_rate': 0,
            'avg_latency_ms': 0,
        })

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

    async def _normalize_price(self, price_source: PriceSource) -> NormalizedPrice:
        """Normalize a price source."""
        fee_rate = self._get_fee_rate(price_source.exchange, "taker")

        effective_price_buy = price_source.ask or price_source.price
        effective_price_sell = price_source.bid or price_source.price

        if effective_price_buy:
            effective_price_buy = effective_price_buy * (Decimal('1') + fee_rate)
        if effective_price_sell:
            effective_price_sell = effective_price_sell * (Decimal('1') - fee_rate)

        return NormalizedPrice(
            exchange=price_source.exchange,
            symbol=price_source.symbol,
            price=price_source.price,
            bid=price_source.bid,
            ask=price_source.ask,
            spread=None,
            spread_pct=None,
            mid_price=None,
            timestamp=price_source.timestamp,
            source_type=price_source.source_type,
            confidence=price_source.confidence,
            fee_rate=fee_rate,
            effective_price_buy=effective_price_buy,
            effective_price_sell=effective_price_sell,
            normalized_score=self._calculate_normalized_score(price_source),
            volume=price_source.volume,
            quote_volume=price_source.quote_volume,
            quality_score=price_source.quality_score,
        )

    def _get_fee_rate(self, exchange: str, fee_type: str = "taker") -> Decimal:
        """Get fee rate for an exchange."""
        exchange_lower = exchange.lower()
        if exchange_lower in self._fee_rates:
            return self._fee_rates[exchange_lower].get(fee_type, Decimal('0.001'))
        return Decimal('0.001')

    def _calculate_confidence(
        self,
        price: Decimal,
        bid: Optional[Decimal],
        ask: Optional[Decimal],
    ) -> float:
        """Calculate confidence score for a price."""
        confidence = 1.0

        # Check if price is reasonable
        if price <= 0:
            confidence *= 0.5

        # Check spread
        if bid is not None and ask is not None:
            spread_pct = float(abs(ask - bid) / price * 100)
            if spread_pct > 5:
                confidence *= 0.8
            elif spread_pct > 10:
                confidence *= 0.5
            elif spread_pct > 20:
                confidence *= 0.3

        # Check price vs bid/ask
        if bid is not None and price < bid:
            confidence *= 0.9
        if ask is not None and price > ask:
            confidence *= 0.9

        return max(0.1, min(1.0, confidence))

    def _calculate_normalized_score(self, price_source: PriceSource) -> float:
        """Calculate normalized score for a price."""
        score = 1.0

        # Volume score
        if price_source.volume is not None:
            if price_source.volume < Decimal('0.01'):
                score *= 0.9
            elif price_source.volume < Decimal('0.001'):
                score *= 0.7

        # Age score
        age = (datetime.utcnow() - price_source.timestamp).total_seconds()
        if age > 10:
            score *= max(0, 1 - (age - 10) / 60)
        elif age > 60:
            score *= 0.5

        # Confidence score
        score *= price_source.confidence

        return max(0.1, min(1.0, score))

    async def _validate_price(self, price_source: PriceSource) -> bool:
        """Validate a price source."""
        # Basic validation
        if price_source.price <= 0:
            return False

        # Check against recent history
        history = await self.get_price_history(
            price_source.exchange,
            price_source.symbol,
            limit=10,
        )

        if len(history) >= 3:
            mean_price = sum(history[-3:], Decimal('0')) / Decimal(len(history[-3:]))
            if mean_price > 0:
                deviation = abs(price_source.price - mean_price) / mean_price * 100
                if deviation > 50:
                    logger.warning(
                        f"Price deviation too high for {price_source.exchange}:{price_source.symbol}: "
                        f"{deviation:.2f}%"
                    )
                    return False

        return True

    async def _detect_anomalies(self, normalized: NormalizedPrice) -> None:
        """Detect price anomalies."""
        # Get recent prices for this exchange-symbol
        history = await self.get_price_history(
            normalized.exchange,
            normalized.symbol,
            limit=self._anomaly_config['window_size'],
        )

        if len(history) < self._anomaly_config['min_samples']:
            return

        # Calculate z-score
        prices = [float(p) for p in history]
        mean = np.mean(prices)
        std = np.std(prices)

        if std == 0:
            return

        zscore = abs(float(normalized.price) - mean) / std

        if zscore > self._anomaly_config['zscore_threshold']:
            self._metrics['anomalies_detected'] += 1
            logger.warning(
                "Anomaly detected: %s:%s price=%s zscore=%.2f",
                normalized.exchange, normalized.symbol, normalized.price, zscore
            )

            # Update anomaly features for isolation forest
            if SKLEARN_AVAILABLE and self._isolation_forest:
                self._anomaly_features.append({
                    'price': float(normalized.price),
                    'mean': mean,
                    'std': std,
                    'zscore': zscore,
                    'timestamp': time.time(),
                })
                # Keep only recent features
                if len(self._anomaly_features) > 1000:
                    self._anomaly_features = self._anomaly_features[-500:]

    async def _check_anomaly(
        self,
        normalized: NormalizedPrice,
        all_prices: Dict[str, NormalizedPrice],
        consolidated: Decimal,
        price_std: Optional[float],
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if a price is anomalous."""
        if not price_std or price_std == 0:
            return False, {}

        zscore = abs(float(normalized.price) - float(consolidated)) / price_std

        is_anomaly = zscore > self._anomaly_config['zscore_threshold']

        return is_anomaly, {
            'deviation': float(normalized.price) - float(consolidated),
            'zscore': zscore,
        }

    async def _consolidate_prices(
        self,
        prices: Dict[str, NormalizedPrice],
        method: str = "weighted",
    ) -> Decimal:
        """Consolidate prices using different methods."""
        if not prices:
            return Decimal('0')

        price_values = [p.price for p in prices.values()]

        if method == "mean":
            return sum(price_values) / Decimal(len(price_values))

        if method == "median":
            sorted_prices = sorted(price_values)
            return sorted_prices[len(sorted_prices) // 2]

        if method == "weighted":
            total_weight = Decimal('0')
            weighted_sum = Decimal('0')
            for p in prices.values():
                weight = p.volume or Decimal('1')
                total_weight += weight
                weighted_sum += p.price * weight
            return weighted_sum / total_weight if total_weight > 0 else Decimal('0')

        if method == "vwap":
            total_volume = Decimal('0')
            total_value = Decimal('0')
            for p in prices.values():
                if p.volume is not None and p.volume > 0:
                    total_volume += p.volume
                    total_value += p.price * p.volume
            return total_value / total_volume if total_volume > 0 else Decimal('0')

        if method == "consensus":
            tolerance = Decimal('0.005')  # 0.5%
            groups = []
            for price in price_values:
                found = False
                for group in groups:
                    if abs(price - group[0]) / group[0] <= tolerance:
                        group.append(price)
                        found = True
                        break
                if not found:
                    groups.append([price])
            largest_group = max(groups, key=len)
            return sum(largest_group) / Decimal(len(largest_group))

        if method == "robust":
            # Use trimmed mean
            sorted_prices = sorted(price_values)
            trim = int(len(sorted_prices) * 0.1)
            trimmed = sorted_prices[trim:-trim] if trim > 0 else sorted_prices
            return sum(trimmed) / Decimal(len(trimmed)) if trimmed else sorted_prices[0]

        # Default: mean
        return sum(price_values) / Decimal(len(price_values))

    async def _calculate_weighted_price(
        self,
        prices: Dict[str, NormalizedPrice],
    ) -> Optional[Decimal]:
        """Calculate volume-weighted price."""
        total_volume = Decimal('0')
        total_value = Decimal('0')

        for p in prices.values():
            if p.volume is not None and p.volume > 0:
                total_volume += p.volume
                total_value += p.price * p.volume

        if total_volume > 0:
            return total_value / total_volume

        return None

    def _get_best_bid(
        self,
        prices: Dict[str, NormalizedPrice],
    ) -> Tuple[Optional[str], Optional[Decimal]]:
        """Get highest bid across all exchanges."""
        best = None
        best_exchange = None
        for exchange, price in prices.items():
            if price.bid is not None:
                if best is None or price.bid > best:
                    best = price.bid
                    best_exchange = exchange
        return best_exchange, best

    def _get_best_ask(
        self,
        prices: Dict[str, NormalizedPrice],
    ) -> Tuple[Optional[str], Optional[Decimal]]:
        """Get lowest ask across all exchanges."""
        best = None
        best_exchange = None
        for exchange, price in prices.items():
            if price.ask is not None:
                if best is None or price.ask < best:
                    best = price.ask
                    best_exchange = exchange
        return best_exchange, best

    async def _check_rate_limit(self, exchange: str) -> None:
        """Check and enforce rate limiting for an exchange."""
        now = time.time()

        # Initialize rate limiter if needed
        if exchange not in self._rate_limiters:
            self._rate_limiters[exchange] = asyncio.Semaphore(10)
            self._last_rate_limit_reset[exchange] = now
            self._rate_limit_counts[exchange] = 0

        # Reset rate limit counter if needed
        if now - self._last_rate_limit_reset[exchange] > 60:
            self._last_rate_limit_reset[exchange] = now
            self._rate_limit_counts[exchange] = 0

        # Check rate limit
        if self._rate_limit_counts[exchange] >= 60:
            raise RateLimitExceededError(
                f"Rate limit exceeded for {exchange}: {self._rate_limit_counts[exchange]} updates in last minute"
            )

        # Acquire semaphore
        async with self._rate_limiters[exchange]:
            self._rate_limit_counts[exchange] += 1

    def _update_exchange_status(self, exchange: str, success: bool) -> None:
        """Update exchange status."""
        if exchange not in self._exchange_status:
            self._exchange_status[exchange] = {
                'available': success,
                'last_update': time.time(),
                'success_rate': 1.0,
                'total_attempts': 0,
                'successful_attempts': 0,
            }

        status = self._exchange_status[exchange]
        status['total_attempts'] += 1
        if success:
            status['successful_attempts'] += 1
        status['available'] = success
        status['last_update'] = time.time()

        # Calculate success rate
        if status['total_attempts'] > 0:
            status['success_rate'] = (
                status['successful_attempts'] / status['total_attempts']
            )

    def _update_latency_metrics(self, exchange: str, latency_ms: float) -> None:
        """Update latency metrics for an exchange."""
        self._exchange_latency[exchange].append(latency_ms)
        if len(self._exchange_latency[exchange]) > 100:
            self._exchange_latency[exchange] = self._exchange_latency[exchange][-100:]

        # Update exchange status with latency
        if exchange in self._exchange_status:
            self._exchange_status[exchange]['avg_latency_ms'] = (
                sum(self._exchange_latency[exchange]) / len(self._exchange_latency[exchange])
            )

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the price manager."""
        self._running = True
        logger.info("PriceManager started")

    async def stop(self) -> None:
        """Stop the price manager."""
        self._running = False

        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()

        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

        # Clear data
        await self.clear()

        logger.info("PriceManager stopped")

    async def __aenter__(self) -> 'PriceManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_price_manager(
    config: Optional[PriceManagerConfig] = None,
    redis_url: Optional[str] = None,
    cache_ttl: int = 5,
    enable_advanced_metrics: bool = True,
) -> PriceManager:
    """
    Create a price manager instance.

    Args:
        config: Configuration instance
        redis_url: Redis URL for caching
        cache_ttl: Cache TTL in seconds
        enable_advanced_metrics: Enable advanced metrics collection

    Returns:
        PriceManager instance
    """
    redis_client = None
    if redis_url and REDIS_AVAILABLE:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)

    return PriceManager(
        config=config,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
        enable_advanced_metrics=enable_advanced_metrics,
    )


async def create_price_manager_async(
    config: Optional[PriceManagerConfig] = None,
    redis_url: Optional[str] = None,
    cache_ttl: int = 5,
) -> PriceManager:
    """Create and start a price manager asynchronously."""
    manager = create_price_manager(config, redis_url, cache_ttl)
    await manager.start()
    return manager


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the price manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize price manager
        manager = create_price_manager()

        # Update prices
        await manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
            quote_volume=5555250.0,
        )

        await manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            bid=45010.0,
            ask=45030.0,
            volume=67.89,
            quote_volume=3055000.0,
        )

        await manager.update_price(
            exchange="coinbase",
            symbol="BTC-USDT",
            price=44980.0,
            bid=44970.0,
            ask=44990.0,
            volume=45.67,
            quote_volume=2054000.0,
        )

        # Get snapshot
        snapshot = await manager.get_snapshot("BTC-USDT")
        print(f"Snapshot: {json.dumps(snapshot.to_dict(), indent=2, default=str)}")

        # Get arbitrage opportunity
        opportunity = await manager.get_arbitrage_opportunity(
            "BTC-USDT",
            min_profit_pct=0.1,
        )
        if opportunity:
            print(f"Arbitrage opportunity: {json.dumps(opportunity.to_dict(), indent=2, default=str)}")
        else:
            print("No arbitrage opportunity found")

        # Get metrics
        metrics = manager.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")

        await manager.stop()

    asyncio.run(main())
