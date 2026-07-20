"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Spread Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced spread management system for arbitrage detection with:
- Real-time spread calculation and monitoring
- Spread analysis and prediction
- Fee-aware spread calculation
- Spread anomaly detection
- Historical spread tracking
- Multi-exchange spread comparison
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

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LinearRegression = None
    StandardScaler = None

# Local imports
from .base import BaseSpreadManager
from .exceptions import (
    SpreadManagerError,
    SpreadCalculationError,
    SpreadValidationError,
    SpreadNotFoundError,
)
from .price_manager import PriceManager, PriceSource, NormalizedPrice, PriceSnapshot
from .config import SpreadManagerConfig
from .constants import (
    DEFAULT_FEE_RATES,
    EXCHANGE_FEE_RATES,
    SPREAD_CACHE_TTL,
    MAX_SPREAD_HISTORY,
    MIN_SPREAD_SAMPLES,
    SPREAD_ANOMALY_THRESHOLD,
    SPREAD_WARNING_THRESHOLD,
    SPREAD_CRITICAL_THRESHOLD,
)

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class SpreadType(str, Enum):
    """Type of spread."""
    BID_ASK = "bid_ask"
    EXCHANGE = "exchange"
    CROSS_EXCHANGE = "cross_exchange"
    INTERNAL = "internal"
    EXTERNAL = "external"
    NET = "net"
    GROSS = "gross"
    EFFECTIVE = "effective"
    NORMALIZED = "normalized"


class SpreadDirection(str, Enum):
    """Direction of spread."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    ZERO = "zero"
    WIDENING = "widening"
    NARROWING = "narrowing"
    VOLATILE = "volatile"


class SpreadQuality(str, Enum):
    """Quality of spread."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# ============================================================
# DATA MODELS
# ============================================================

class SpreadData(BaseModel):
    """Represents spread data for a trading pair."""
    
    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    spread: Decimal
    spread_pct: float
    mid_price: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_type: str = "spot"
    fee_rate: Decimal = Decimal('0.001')
    effective_spread: Optional[Decimal] = None
    effective_spread_pct: Optional[float] = None
    normalized_spread: Optional[Decimal] = None
    normalized_spread_pct: Optional[float] = None
    quality: SpreadQuality = SpreadQuality.GOOD
    direction: SpreadDirection = SpreadDirection.POSITIVE
    volume: Optional[Decimal] = None
    quote_volume: Optional[Decimal] = None
    depth_bid: Optional[Decimal] = None
    depth_ask: Optional[Decimal] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @validator('spread')
    def validate_spread(cls, v):
        if v < 0:
            raise ValueError(f"Spread must be non-negative: {v}")
        return v

    @validator('bid', 'ask')
    def validate_bid_ask(cls, v):
        if v <= 0:
            raise ValueError(f"Bid/Ask must be positive: {v}")
        return v

    @root_validator
    def validate_bid_ask_relationship(cls, values):
        bid = values.get('bid')
        ask = values.get('ask')
        if bid is not None and ask is not None and bid >= ask:
            raise ValueError(f"Bid {bid} must be less than ask {ask}")
        return values

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange': self.exchange,
            'symbol': self.symbol,
            'bid': str(self.bid),
            'ask': str(self.ask),
            'spread': str(self.spread),
            'spread_pct': self.spread_pct,
            'mid_price': str(self.mid_price),
            'timestamp': self.timestamp.isoformat(),
            'source_type': self.source_type,
            'fee_rate': str(self.fee_rate),
            'effective_spread': str(self.effective_spread) if self.effective_spread else None,
            'effective_spread_pct': self.effective_spread_pct,
            'normalized_spread': str(self.normalized_spread) if self.normalized_spread else None,
            'normalized_spread_pct': self.normalized_spread_pct,
            'quality': self.quality.value if isinstance(self.quality, SpreadQuality) else self.quality,
            'direction': self.direction.value if isinstance(self.direction, SpreadDirection) else self.direction,
            'volume': str(self.volume) if self.volume else None,
            'quote_volume': str(self.quote_volume) if self.quote_volume else None,
            'depth_bid': str(self.depth_bid) if self.depth_bid else None,
            'depth_ask': str(self.depth_ask) if self.depth_ask else None,
            'confidence': self.confidence,
            'metadata': self.metadata,
        }


@dataclass
class CrossExchangeSpread:
    """Represents spread between two exchanges."""
    
    symbol: str
    exchange_1: str
    exchange_2: str
    price_1: Decimal
    price_2: Decimal
    spread: Decimal
    spread_pct: float
    timestamp: datetime
    direction: SpreadDirection
    fee_rate_1: Decimal = Decimal('0.001')
    fee_rate_2: Decimal = Decimal('0.001')
    effective_spread: Optional[Decimal] = None
    effective_spread_pct: Optional[float] = None
    normalized_spread: Optional[Decimal] = None
    normalized_spread_pct: Optional[float] = None
    volume_1: Optional[Decimal] = None
    volume_2: Optional[Decimal] = None
    confidence: float = 1.0
    is_arbitrage_opportunity: bool = False
    arbitrage_profit: Optional[Decimal] = None
    arbitrage_profit_pct: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange_1': self.exchange_1,
            'exchange_2': self.exchange_2,
            'price_1': str(self.price_1),
            'price_2': str(self.price_2),
            'spread': str(self.spread),
            'spread_pct': self.spread_pct,
            'timestamp': self.timestamp.isoformat(),
            'direction': self.direction.value if isinstance(self.direction, SpreadDirection) else self.direction,
            'fee_rate_1': str(self.fee_rate_1),
            'fee_rate_2': str(self.fee_rate_2),
            'effective_spread': str(self.effective_spread) if self.effective_spread else None,
            'effective_spread_pct': self.effective_spread_pct,
            'normalized_spread': str(self.normalized_spread) if self.normalized_spread else None,
            'normalized_spread_pct': self.normalized_spread_pct,
            'volume_1': str(self.volume_1) if self.volume_1 else None,
            'volume_2': str(self.volume_2) if self.volume_2 else None,
            'confidence': self.confidence,
            'is_arbitrage_opportunity': self.is_arbitrage_opportunity,
            'arbitrage_profit': str(self.arbitrage_profit) if self.arbitrage_profit else None,
            'arbitrage_profit_pct': self.arbitrage_profit_pct,
            'metadata': self.metadata,
        }


@dataclass
class SpreadSnapshot:
    """Complete spread snapshot."""
    
    timestamp: datetime
    symbol: str
    spreads: Dict[str, SpreadData]  # exchange -> SpreadData
    cross_spreads: List[CrossExchangeSpread]
    best_spread: Optional[SpreadData] = None
    worst_spread: Optional[SpreadData] = None
    average_spread_pct: Optional[float] = None
    median_spread_pct: Optional[float] = None
    spread_std: Optional[float] = None
    spread_volatility: Optional[float] = None
    exchange_count: int = 0
    anomaly_detected: bool = False
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    market_spread: Optional[Decimal] = None
    market_spread_pct: Optional[float] = None
    best_bid_exchange: Optional[str] = None
    best_ask_exchange: Optional[str] = None
    best_cross_spread: Optional[CrossExchangeSpread] = None
    total_volume: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_spread_for_exchange(self, exchange: str) -> Optional[SpreadData]:
        """Get spread for a specific exchange."""
        return self.spreads.get(exchange)

    def get_exchanges(self) -> Set[str]:
        """Get all exchanges in snapshot."""
        return set(self.spreads.keys())

    def get_best_spread_exchange(self) -> Optional[str]:
        """Get exchange with the best (tightest) spread."""
        if self.best_spread:
            return self.best_spread.exchange
        return None

    def get_worst_spread_exchange(self) -> Optional[str]:
        """Get exchange with the worst (widest) spread."""
        if self.worst_spread:
            return self.worst_spread.exchange
        return None

    def get_spread_ranking(self) -> List[Tuple[str, float]]:
        """Get spread ranking across exchanges."""
        ranking = []
        for exchange, spread in self.spreads.items():
            ranking.append((exchange, spread.spread_pct))
        return sorted(ranking, key=lambda x: x[1])

    def get_arbitrage_opportunities(self) -> List[CrossExchangeSpread]:
        """Get all arbitrage opportunities."""
        return [s for s in self.cross_spreads if s.is_arbitrage_opportunity]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'spreads': {
                k: v.to_dict()
                for k, v in self.spreads.items()
            },
            'cross_spreads': [s.to_dict() for s in self.cross_spreads],
            'best_spread': self.best_spread.to_dict() if self.best_spread else None,
            'worst_spread': self.worst_spread.to_dict() if self.worst_spread else None,
            'average_spread_pct': self.average_spread_pct,
            'median_spread_pct': self.median_spread_pct,
            'spread_std': self.spread_std,
            'spread_volatility': self.spread_volatility,
            'exchange_count': self.exchange_count,
            'anomaly_detected': self.anomaly_detected,
            'anomalies': self.anomalies,
            'market_spread': str(self.market_spread) if self.market_spread else None,
            'market_spread_pct': self.market_spread_pct,
            'best_bid_exchange': self.best_bid_exchange,
            'best_ask_exchange': self.best_ask_exchange,
            'best_cross_spread': self.best_cross_spread.to_dict() if self.best_cross_spread else None,
            'total_volume': str(self.total_volume) if self.total_volume else None,
            'metadata': self.metadata,
        }


@dataclass
class SpreadStatistics:
    """Statistical analysis of spreads."""
    
    symbol: str
    exchange: str
    mean_spread_pct: float
    median_spread_pct: float
    std_spread_pct: float
    min_spread_pct: float
    max_spread_pct: float
    spread_range: float
    volatility: float
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    percentiles: Dict[int, float] = field(default_factory=dict)
    trend_direction: SpreadDirection = SpreadDirection.ZERO
    trend_strength: float = 0.0
    sample_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'mean_spread_pct': self.mean_spread_pct,
            'median_spread_pct': self.median_spread_pct,
            'std_spread_pct': self.std_spread_pct,
            'min_spread_pct': self.min_spread_pct,
            'max_spread_pct': self.max_spread_pct,
            'spread_range': self.spread_range,
            'volatility': self.volatility,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
            'percentiles': self.percentiles,
            'trend_direction': self.trend_direction.value if isinstance(self.trend_direction, SpreadDirection) else self.trend_direction,
            'trend_strength': self.trend_strength,
            'sample_count': self.sample_count,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# SPREAD MANAGER IMPLEMENTATION
# ============================================================

class SpreadManager(BaseSpreadManager):
    """
    Advanced spread manager with:
    - Real-time spread calculation
    - Multi-exchange spread analysis
    - Fee-aware spread calculation
    - Spread anomaly detection
    - Historical spread tracking
    - Spread prediction
    - Arbitrage opportunity detection
    """

    def __init__(
        self,
        price_manager: PriceManager,
        config: Optional[SpreadManagerConfig] = None,
        redis_client: Optional[Any] = None,
        cache_ttl: int = 5,
    ):
        """
        Initialize spread manager.

        Args:
            price_manager: PriceManager instance
            config: Configuration instance
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
        """
        self.price_manager = price_manager
        self.config = config or SpreadManagerConfig()
        self.redis = redis_client
        self.cache_ttl = cache_ttl

        # Spread storage
        self._spreads: Dict[str, Dict[str, SpreadData]] = {}  # exchange -> symbol -> SpreadData
        self._spread_history: Dict[str, Dict[str, deque]] = {}  # exchange -> symbol -> deque of spreads
        self._cross_spreads: Dict[str, List[CrossExchangeSpread]] = {}  # symbol -> list of cross spreads

        # Metrics
        self._metrics = {
            'total_calculations': 0,
            'successful_calculations': 0,
            'failed_calculations': 0,
            'anomalies_detected': 0,
            'arbitrage_opportunities_found': 0,
            'avg_spread_pct': 0,
            'min_spread_pct': float('inf'),
            'max_spread_pct': 0,
            'last_calculation_timestamp': None,
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Fee rates
        self._fee_rates = DEFAULT_FEE_RATES

        # Spread thresholds
        self._thresholds = {
            'excellent': 0.05,
            'good': 0.15,
            'fair': 0.30,
            'poor': 0.50,
            'critical': 1.00,
        }

        # Anomaly detection config
        self._anomaly_config = {
            'zscore_threshold': 3.0,
            'iqr_multiplier': 1.5,
            'min_samples': 10,
            'window_size': 50,
        }

        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}

        logger.info("SpreadManager initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def calculate_spread(
        self,
        exchange: str,
        symbol: str,
        bid: Optional[Decimal] = None,
        ask: Optional[Decimal] = None,
        price_source: Optional[PriceSource] = None,
        include_fees: bool = True,
        normalize: bool = True,
    ) -> SpreadData:
        """
        Calculate spread for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            bid: Bid price (optional, will get from price manager if not provided)
            ask: Ask price (optional, will get from price manager if not provided)
            price_source: PriceSource instance (optional)
            include_fees: Whether to include fees in spread calculation
            normalize: Whether to normalize the spread

        Returns:
            SpreadData instance
        """
        start_time = time.perf_counter()

        try:
            # Get prices if not provided
            if price_source is None:
                price_source = await self.price_manager.get_price(exchange, symbol)
                if price_source is None:
                    raise SpreadNotFoundError(f"No price found for {exchange}:{symbol}")

            # Use provided bid/ask or from price source
            bid = bid or price_source.bid
            ask = ask or price_source.ask

            if bid is None or ask is None:
                # Use price as mid price
                price = price_source.price
                bid = price * Decimal('0.9995')
                ask = price * Decimal('1.0005')

            # Validate
            if bid >= ask:
                raise SpreadValidationError(f"Bid {bid} must be less than ask {ask}")

            # Calculate spread
            spread = ask - bid
            mid_price = (bid + ask) / 2
            spread_pct = float(spread / mid_price * 100) if mid_price > 0 else 0

            # Get fee rate
            fee_rate = self._get_fee_rate(exchange)

            # Calculate effective spread with fees
            effective_spread = None
            effective_spread_pct = None
            if include_fees:
                effective_spread = spread + (ask * fee_rate) + (bid * fee_rate)
                effective_spread_pct = float(effective_spread / mid_price * 100) if mid_price > 0 else 0

            # Normalize spread
            normalized_spread = None
            normalized_spread_pct = None
            if normalize:
                normalized_spread = self._normalize_spread(spread, mid_price, fee_rate)
                normalized_spread_pct = float(normalized_spread / mid_price * 100) if mid_price > 0 else 0

            # Determine quality and direction
            quality = self._determine_spread_quality(spread_pct)
            direction = self._determine_spread_direction(exchange, symbol, spread_pct)

            # Create spread data
            spread_data = SpreadData(
                exchange=exchange,
                symbol=symbol,
                bid=bid,
                ask=ask,
                spread=spread,
                spread_pct=spread_pct,
                mid_price=mid_price,
                timestamp=datetime.utcnow(),
                source_type=price_source.source_type.value if hasattr(price_source.source_type, 'value') else str(price_source.source_type),
                fee_rate=fee_rate,
                effective_spread=effective_spread,
                effective_spread_pct=effective_spread_pct,
                normalized_spread=normalized_spread,
                normalized_spread_pct=normalized_spread_pct,
                quality=quality,
                direction=direction,
                volume=price_source.volume,
                quote_volume=price_source.quote_volume,
                confidence=price_source.confidence,
            )

            # Store spread
            async with self._lock:
                if exchange not in self._spreads:
                    self._spreads[exchange] = {}
                self._spreads[exchange][symbol] = spread_data

                # Update history
                if exchange not in self._spread_history:
                    self._spread_history[exchange] = {}
                if symbol not in self._spread_history[exchange]:
                    self._spread_history[exchange][symbol] = deque(maxlen=MAX_SPREAD_HISTORY)
                self._spread_history[exchange][symbol].append(spread_data)

            # Cache spread
            await self._cache_set(f"spread:{exchange}:{symbol}", spread_data.to_dict())

            # Update metrics
            self._update_metrics(spread_data)

            # Detect anomalies
            await self._detect_spread_anomalies(spread_data)

            logger.debug(
                "Spread calculated for %s:%s = %.4f%% (effective: %.4f%%)",
                exchange, symbol, spread_pct, effective_spread_pct or 0
            )

            return spread_data

        except Exception as e:
            self._metrics['failed_calculations'] += 1
            logger.error(f"Failed to calculate spread for {exchange}:{symbol}: {e}")
            raise SpreadCalculationError(f"Failed to calculate spread: {e}")

    async def get_spread(
        self,
        exchange: str,
        symbol: str,
        use_cache: bool = True,
    ) -> Optional[SpreadData]:
        """
        Get spread for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            use_cache: Whether to use cache

        Returns:
            SpreadData or None
        """
        # Check cache
        if use_cache:
            cached = await self._cache_get(f"spread:{exchange}:{symbol}")
            if cached:
                try:
                    return SpreadData(**cached)
                except Exception as e:
                    logger.warning(f"Failed to parse cached spread: {e}")

        # Check memory
        async with self._lock:
            if exchange in self._spreads and symbol in self._spreads[exchange]:
                return self._spreads[exchange][symbol]

        return None

    async def get_spreads_for_symbol(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_confidence: float = 0.5,
    ) -> Dict[str, SpreadData]:
        """
        Get spreads for a symbol across exchanges.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_confidence: Minimum confidence score

        Returns:
            Dict mapping exchange to SpreadData
        """
        result = {}
        exchanges = exchanges or list(self._spreads.keys())

        for exchange in exchanges:
            spread = await self.get_spread(exchange, symbol)
            if spread and spread.confidence >= min_confidence:
                result[exchange] = spread

        return result

    async def calculate_cross_exchange_spread(
        self,
        exchange_1: str,
        exchange_2: str,
        symbol: str,
        include_fees: bool = True,
    ) -> CrossExchangeSpread:
        """
        Calculate spread between two exchanges.

        Args:
            exchange_1: First exchange name
            exchange_2: Second exchange name
            symbol: Trading pair symbol
            include_fees: Whether to include fees

        Returns:
            CrossExchangeSpread instance
        """
        # Get prices from both exchanges
        price_1 = await self.price_manager.get_price(exchange_1, symbol)
        price_2 = await self.price_manager.get_price(exchange_2, symbol)

        if price_1 is None:
            raise SpreadNotFoundError(f"No price found for {exchange_1}:{symbol}")
        if price_2 is None:
            raise SpreadNotFoundError(f"No price found for {exchange_2}:{symbol}")

        # Calculate spread
        price_1_decimal = price_1.price
        price_2_decimal = price_2.price

        spread = price_2_decimal - price_1_decimal
        spread_pct = float(spread / price_1_decimal * 100) if price_1_decimal > 0 else 0

        # Get fee rates
        fee_1 = self._get_fee_rate(exchange_1)
        fee_2 = self._get_fee_rate(exchange_2)

        # Calculate effective spread with fees
        effective_spread = None
        effective_spread_pct = None
        if include_fees:
            effective_spread = spread - (price_1_decimal * fee_1) - (price_2_decimal * fee_2)
            effective_spread_pct = float(effective_spread / price_1_decimal * 100) if price_1_decimal > 0 else 0

        # Determine direction
        if spread > 0:
            direction = SpreadDirection.POSITIVE
        elif spread < 0:
            direction = SpreadDirection.NEGATIVE
        else:
            direction = SpreadDirection.ZERO

        # Check if arbitrage opportunity
        is_arbitrage = False
        arbitrage_profit = None
        arbitrage_profit_pct = None

        if effective_spread is not None and effective_spread > 0:
            is_arbitrage = True
            arbitrage_profit = effective_spread
            arbitrage_profit_pct = effective_spread_pct

        # Create cross exchange spread
        cross_spread = CrossExchangeSpread(
            symbol=symbol,
            exchange_1=exchange_1,
            exchange_2=exchange_2,
            price_1=price_1_decimal,
            price_2=price_2_decimal,
            spread=spread,
            spread_pct=spread_pct,
            timestamp=datetime.utcnow(),
            direction=direction,
            fee_rate_1=fee_1,
            fee_rate_2=fee_2,
            effective_spread=effective_spread,
            effective_spread_pct=effective_spread_pct,
            volume_1=price_1.volume,
            volume_2=price_2.volume,
            confidence=min(price_1.confidence, price_2.confidence),
            is_arbitrage_opportunity=is_arbitrage,
            arbitrage_profit=arbitrage_profit,
            arbitrage_profit_pct=arbitrage_profit_pct,
        )

        # Store cross spread
        if symbol not in self._cross_spreads:
            self._cross_spreads[symbol] = []
        self._cross_spreads[symbol].append(cross_spread)

        # Keep only recent cross spreads
        if len(self._cross_spreads[symbol]) > 1000:
            self._cross_spreads[symbol] = self._cross_spreads[symbol][-1000:]

        # Update metrics
        if is_arbitrage:
            self._metrics['arbitrage_opportunities_found'] += 1

        logger.info(
            "Cross exchange spread %s-%s for %s: %.4f%% (arbitrage: %s)",
            exchange_1, exchange_2, symbol, spread_pct, is_arbitrage
        )

        return cross_spread

    async def get_snapshot(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> SpreadSnapshot:
        """
        Get a complete spread snapshot.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            SpreadSnapshot instance
        """
        # Get spreads
        spreads = await self.get_spreads_for_symbol(symbol, exchanges)

        if not spreads:
            raise SpreadNotFoundError(f"No spreads found for {symbol}")

        # Calculate cross spreads
        cross_spreads = []
        exchange_list = list(spreads.keys())

        for i in range(len(exchange_list)):
            for j in range(i + 1, len(exchange_list)):
                try:
                    cross = await self.calculate_cross_exchange_spread(
                        exchange_list[i],
                        exchange_list[j],
                        symbol,
                    )
                    cross_spreads.append(cross)
                except Exception as e:
                    logger.warning(f"Failed to calculate cross spread {exchange_list[i]}-{exchange_list[j]}: {e}")

        # Calculate statistics
        spread_values = [s.spread_pct for s in spreads.values()]
        avg_spread = statistics.mean(spread_values) if spread_values else 0
        median_spread = statistics.median(spread_values) if spread_values else 0
        std_spread = statistics.stdev(spread_values) if len(spread_values) > 1 else 0

        # Find best and worst spreads
        best_spread = min(spreads.values(), key=lambda s: s.spread_pct)
        worst_spread = max(spreads.values(), key=lambda s: s.spread_pct)

        # Determine best bid and ask exchanges
        best_bid_exchange = None
        best_ask_exchange = None
        best_bid = None
        best_ask = None

        for exchange, spread in spreads.items():
            if best_bid is None or spread.bid > best_bid:
                best_bid = spread.bid
                best_bid_exchange = exchange
            if best_ask is None or spread.ask < best_ask:
                best_ask = spread.ask
                best_ask_exchange = exchange

        # Find best cross spread
        best_cross_spread = None
        if cross_spreads:
            best_cross_spread = min(cross_spreads, key=lambda s: abs(s.spread_pct))

        # Detect anomalies
        anomalies = []
        anomaly_detected = False

        for exchange, spread in spreads.items():
            zscore = abs(spread.spread_pct - avg_spread) / std_spread if std_spread > 0 else 0
            if zscore > self._anomaly_config['zscore_threshold']:
                anomalies.append({
                    'exchange': exchange,
                    'spread_pct': spread.spread_pct,
                    'zscore': zscore,
                })
                anomaly_detected = True

        # Calculate volatility
        volatility = None
        if len(spread_values) > 1:
            volatility = std_spread / avg_spread if avg_spread > 0 else 0

        # Calculate total volume
        total_volume = None
        for spread in spreads.values():
            if spread.volume:
                total_volume = (total_volume or Decimal('0')) + spread.volume

        # Create snapshot
        snapshot = SpreadSnapshot(
            timestamp=datetime.utcnow(),
            symbol=symbol,
            spreads=spreads,
            cross_spreads=cross_spreads,
            best_spread=best_spread,
            worst_spread=worst_spread,
            average_spread_pct=avg_spread,
            median_spread_pct=median_spread,
            spread_std=std_spread,
            spread_volatility=volatility,
            exchange_count=len(spreads),
            anomaly_detected=anomaly_detected,
            anomalies=anomalies,
            market_spread=best_spread.spread,
            market_spread_pct=best_spread.spread_pct,
            best_bid_exchange=best_bid_exchange,
            best_ask_exchange=best_ask_exchange,
            best_cross_spread=best_cross_spread,
            total_volume=total_volume,
            metadata={
                'exchanges_queried': list(spreads.keys()),
            },
        )

        # Cache snapshot
        await self._cache_set(f"snapshot:spread:{symbol}", snapshot.to_dict())

        logger.info(
            "Spread snapshot for %s: %d exchanges, avg spread: %.4f%%, best: %.4f%%",
            symbol, snapshot.exchange_count, avg_spread, best_spread.spread_pct
        )

        return snapshot

    async def get_spread_statistics(
        self,
        exchange: str,
        symbol: str,
        window: int = 100,
    ) -> SpreadStatistics:
        """
        Get statistical analysis of spreads.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            window: Window size for statistics

        Returns:
            SpreadStatistics instance
        """
        # Get spread history
        async with self._lock:
            if exchange not in self._spread_history:
                raise SpreadNotFoundError(f"No spread history for {exchange}:{symbol}")
            if symbol not in self._spread_history[exchange]:
                raise SpreadNotFoundError(f"No spread history for {exchange}:{symbol}")

            history = list(self._spread_history[exchange][symbol])
            if not history:
                raise SpreadNotFoundError(f"No spread history for {exchange}:{symbol}")

            # Get recent window
            recent = history[-window:]

        spread_values = [s.spread_pct for s in recent]

        # Calculate statistics
        mean_spread = statistics.mean(spread_values) if spread_values else 0
        median_spread = statistics.median(spread_values) if spread_values else 0
        std_spread = statistics.stdev(spread_values) if len(spread_values) > 1 else 0
        min_spread = min(spread_values) if spread_values else 0
        max_spread = max(spread_values) if spread_values else 0
        spread_range = max_spread - min_spread

        # Calculate volatility
        volatility = std_spread / mean_spread if mean_spread > 0 else 0

        # Calculate skewness and kurtosis
        skewness = None
        kurtosis = None
        if SCIPY_AVAILABLE and len(spread_values) > 3:
            skewness = stats.skew(spread_values)
            kurtosis = stats.kurtosis(spread_values)

        # Calculate percentiles
        percentiles = {}
        for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            if len(spread_values) > 1:
                percentiles[p] = np.percentile(spread_values, p)
            else:
                percentiles[p] = spread_values[0] if spread_values else 0

        # Determine trend
        trend_direction = SpreadDirection.ZERO
        trend_strength = 0

        if len(spread_values) > 5:
            # Simple linear regression for trend
            if SKLEARN_AVAILABLE and LinearRegression:
                X = np.array(range(len(spread_values))).reshape(-1, 1)
                y = np.array(spread_values).reshape(-1, 1)
                model = LinearRegression()
                model.fit(X, y)
                slope = model.coef_[0][0]
                if slope > 0.001:
                    trend_direction = SpreadDirection.WIDENING
                    trend_strength = abs(slope)
                elif slope < -0.001:
                    trend_direction = SpreadDirection.NARROWING
                    trend_strength = abs(slope)
            else:
                # Simple comparison of first half vs second half
                mid = len(spread_values) // 2
                first_half = spread_values[:mid]
                second_half = spread_values[mid:]
                if first_half and second_half:
                    first_avg = statistics.mean(first_half)
                    second_avg = statistics.mean(second_half)
                    diff_pct = (second_avg - first_avg) / first_avg * 100 if first_avg > 0 else 0
                    if diff_pct > 5:
                        trend_direction = SpreadDirection.WIDENING
                        trend_strength = diff_pct / 100
                    elif diff_pct < -5:
                        trend_direction = SpreadDirection.NARROWING
                        trend_strength = abs(diff_pct) / 100

        return SpreadStatistics(
            symbol=symbol,
            exchange=exchange,
            mean_spread_pct=mean_spread,
            median_spread_pct=median_spread,
            std_spread_pct=std_spread,
            min_spread_pct=min_spread,
            max_spread_pct=max_spread,
            spread_range=spread_range,
            volatility=volatility,
            skewness=skewness,
            kurtosis=kurtosis,
            percentiles=percentiles,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            sample_count=len(spread_values),
        )

    async def predict_spread(
        self,
        exchange: str,
        symbol: str,
        horizon: int = 10,
    ) -> List[float]:
        """
        Predict future spreads.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            horizon: Number of steps to predict

        Returns:
            List of predicted spread percentages
        """
        # Get spread history
        history = await self.get_spread_history(exchange, symbol, limit=100)

        if len(history) < 10:
            return []

        # Simple moving average prediction
        spread_values = [s.spread_pct for s in history]
        window = min(20, len(spread_values))

        # Use exponential smoothing
        alpha = 0.3
        smoothed = spread_values[0]
        predictions = []

        for _ in range(horizon):
            if len(spread_values) >= window:
                recent_avg = statistics.mean(spread_values[-window:])
                smoothed = alpha * recent_avg + (1 - alpha) * smoothed
            else:
                smoothed = alpha * spread_values[-1] + (1 - alpha) * smoothed

            predictions.append(smoothed)

            # Add some noise for realism
            if len(spread_values) > 1:
                std = statistics.stdev(spread_values[-min(window, len(spread_values)):])
                noise = np.random.normal(0, std * 0.1)
                predictions[-1] = max(0, predictions[-1] + noise)

        return predictions

    async def get_spread_history(
        self,
        exchange: str,
        symbol: str,
        limit: int = 100,
    ) -> List[SpreadData]:
        """
        Get spread history for an exchange-symbol pair.

        Args:
            exchange: Exchange name
            symbol: Trading pair symbol
            limit: Maximum number of spreads to return

        Returns:
            List of SpreadData
        """
        async with self._lock:
            if exchange not in self._spread_history:
                return []
            if symbol not in self._spread_history[exchange]:
                return []

            history = list(self._spread_history[exchange][symbol])
            return history[-limit:]

    async def get_arbitrage_opportunities(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
        min_profit_pct: float = 0.1,
        max_opportunities: int = 10,
    ) -> List[CrossExchangeSpread]:
        """
        Get arbitrage opportunities for a symbol.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query
            min_profit_pct: Minimum profit percentage
            max_opportunities: Maximum number of opportunities

        Returns:
            List of CrossExchangeSpread
        """
        snapshot = await self.get_snapshot(symbol, exchanges)

        opportunities = snapshot.get_arbitrage_opportunities()

        # Filter by profit percentage
        opportunities = [
            o for o in opportunities
            if o.arbitrage_profit_pct is not None and o.arbitrage_profit_pct >= min_profit_pct
        ]

        # Sort by profit percentage
        opportunities.sort(
            key=lambda o: o.arbitrage_profit_pct or 0,
            reverse=True,
        )

        return opportunities[:max_opportunities]

    async def get_best_spread_exchange(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], Optional[SpreadData]]:
        """
        Get exchange with the best (tightest) spread.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            Tuple of (exchange, SpreadData)
        """
        snapshot = await self.get_snapshot(symbol, exchanges)
        return snapshot.best_spread.exchange if snapshot.best_spread else None, snapshot.best_spread

    async def get_worst_spread_exchange(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], Optional[SpreadData]]:
        """
        Get exchange with the worst (widest) spread.

        Args:
            symbol: Trading pair symbol
            exchanges: List of exchanges to query

        Returns:
            Tuple of (exchange, SpreadData)
        """
        snapshot = await self.get_snapshot(symbol, exchanges)
        return snapshot.worst_spread.exchange if snapshot.worst_spread else None, snapshot.worst_spread

    async def clear(self, exchange: Optional[str] = None, symbol: Optional[str] = None) -> None:
        """
        Clear stored spread data.

        Args:
            exchange: Exchange to clear (all if None)
            symbol: Symbol to clear (all if None)
        """
        async with self._lock:
            if exchange:
                if symbol:
                    if exchange in self._spreads and symbol in self._spreads[exchange]:
                        del self._spreads[exchange][symbol]
                    if exchange in self._spread_history and symbol in self._spread_history[exchange]:
                        del self._spread_history[exchange][symbol]
                else:
                    if exchange in self._spreads:
                        del self._spreads[exchange]
                    if exchange in self._spread_history:
                        del self._spread_history[exchange]
            else:
                self._spreads.clear()
                self._spread_history.clear()
                self._cross_spreads.clear()

        logger.info(f"Spread data cleared for {exchange or 'all'}:{symbol or 'all'}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            **self._metrics,
            'exchanges_tracked': len(self._spreads),
            'symbols_tracked': sum(len(spreads) for spreads in self._spreads.values()),
            'spread_quality_distribution': self._get_spread_quality_distribution(),
        }

    # ============================================================
    # PRIVATE METHODS
    # ============================================================

    def _get_fee_rate(self, exchange: str) -> Decimal:
        """Get fee rate for an exchange."""
        exchange_lower = exchange.lower()
        if exchange_lower in self._fee_rates:
            return self._fee_rates[exchange_lower].get('taker', Decimal('0.001'))
        return Decimal('0.001')

    def _normalize_spread(self, spread: Decimal, mid_price: Decimal, fee_rate: Decimal) -> Decimal:
        """Normalize spread using fee rate."""
        # Adjust spread for fee
        return spread + (mid_price * fee_rate * 2)

    def _determine_spread_quality(self, spread_pct: float) -> SpreadQuality:
        """Determine spread quality based on percentage."""
        if spread_pct <= self._thresholds['excellent']:
            return SpreadQuality.EXCELLENT
        elif spread_pct <= self._thresholds['good']:
            return SpreadQuality.GOOD
        elif spread_pct <= self._thresholds['fair']:
            return SpreadQuality.FAIR
        elif spread_pct <= self._thresholds['poor']:
            return SpreadQuality.POOR
        else:
            return SpreadQuality.CRITICAL

    def _determine_spread_direction(
        self,
        exchange: str,
        symbol: str,
        current_spread_pct: float,
    ) -> SpreadDirection:
        """Determine spread direction based on history."""
        # Get spread history
        history = self._spread_history.get(exchange, {}).get(symbol, deque())

        if len(history) < 5:
            return SpreadDirection.ZERO

        # Calculate average of recent spreads
        recent = [h.spread_pct for h in list(history)[-10:]]
        avg_recent = statistics.mean(recent) if recent else current_spread_pct

        # Determine direction
        if current_spread_pct > avg_recent * 1.2:
            return SpreadDirection.WIDENING
        elif current_spread_pct < avg_recent * 0.8:
            return SpreadDirection.NARROWING

        # Check volatility
        if len(recent) > 5:
            std = statistics.stdev(recent)
            if std > avg_recent * 0.5:
                return SpreadDirection.VOLATILE

        return SpreadDirection.ZERO

    async def _detect_spread_anomalies(self, spread_data: SpreadData) -> None:
        """Detect spread anomalies."""
        # Get recent spreads
        history = await self.get_spread_history(spread_data.exchange, spread_data.symbol)

        if len(history) < self._anomaly_config['min_samples']:
            return

        # Calculate z-score
        spread_values = [s.spread_pct for s in history[-self._anomaly_config['window_size']:]]
        mean = statistics.mean(spread_values)
        std = statistics.stdev(spread_values) if len(spread_values) > 1 else 0

        if std == 0:
            return

        zscore = abs(spread_data.spread_pct - mean) / std

        if zscore > self._anomaly_config['zscore_threshold']:
            self._metrics['anomalies_detected'] += 1
            logger.warning(
                "Spread anomaly detected: %s:%s spread=%.4f%% zscore=%.2f",
                spread_data.exchange, spread_data.symbol, spread_data.spread_pct, zscore
            )

    def _update_metrics(self, spread_data: SpreadData) -> None:
        """Update metrics."""
        self._metrics['total_calculations'] += 1
        self._metrics['successful_calculations'] += 1

        # Update spread statistics
        self._metrics['avg_spread_pct'] = (
            self._metrics['avg_spread_pct'] * 0.9 + spread_data.spread_pct * 0.1
        )
        self._metrics['min_spread_pct'] = min(
            self._metrics['min_spread_pct'], spread_data.spread_pct
        )
        self._metrics['max_spread_pct'] = max(
            self._metrics['max_spread_pct'], spread_data.spread_pct
        )
        self._metrics['last_calculation_timestamp'] = datetime.utcnow().isoformat()

    def _get_spread_quality_distribution(self) -> Dict[str, int]:
        """Get distribution of spread quality."""
        distribution = {
            SpreadQuality.EXCELLENT.value: 0,
            SpreadQuality.GOOD.value: 0,
            SpreadQuality.FAIR.value: 0,
            SpreadQuality.POOR.value: 0,
            SpreadQuality.CRITICAL.value: 0,
        }

        for spreads in self._spreads.values():
            for spread in spreads.values():
                quality = spread.quality.value if isinstance(spread.quality, SpreadQuality) else spread.quality
                if quality in distribution:
                    distribution[quality] += 1

        return distribution

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
        """Start the spread manager."""
        self._running = True
        logger.info("SpreadManager started")

    async def stop(self) -> None:
        """Stop the spread manager."""
        self._running = False
        await self.clear()
        logger.info("SpreadManager stopped")

    async def __aenter__(self) -> 'SpreadManager':
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_spread_manager(
    price_manager: PriceManager,
    config: Optional[SpreadManagerConfig] = None,
    redis_client: Optional[Any] = None,
    cache_ttl: int = 5,
) -> SpreadManager:
    """
    Create a spread manager instance.

    Args:
        price_manager: PriceManager instance
        config: Configuration instance
        redis_client: Redis client for caching
        cache_ttl: Cache TTL in seconds

    Returns:
        SpreadManager instance
    """
    return SpreadManager(
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
    Example usage of the spread manager.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        # Initialize price manager
        from .price_manager import create_price_manager
        price_manager = create_price_manager()

        # Update some prices
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
        )

        await price_manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            bid=45010.0,
            ask=45030.0,
            volume=67.89,
        )

        # Initialize spread manager
        spread_manager = create_spread_manager(price_manager)

        # Calculate spread
        spread = await spread_manager.calculate_spread("binance", "BTC-USDT")
        print(f"Spread: {spread.spread_pct:.4f}%")

        # Get snapshot
        snapshot = await spread_manager.get_snapshot("BTC-USDT")
        print(f"Snapshot: {json.dumps(snapshot.to_dict(), indent=2, default=str)}")

        # Get arbitrage opportunities
        opportunities = await spread_manager.get_arbitrage_opportunities(
            "BTC-USDT",
            min_profit_pct=0.1,
        )
        for opp in opportunities:
            print(f"Arbitrage opportunity: {opp.exchange_1} -> {opp.exchange_2}: {opp.arbitrage_profit_pct:.4f}%")

        # Get spread statistics
        stats = await spread_manager.get_spread_statistics("binance", "BTC-USDT")
        print(f"Spread statistics: {stats.to_dict()}")

        # Get metrics
        metrics = spread_manager.get_metrics()
        print(f"Metrics: {json.dumps(metrics, indent=2, default=str)}")

        await spread_manager.stop()
        await price_manager.stop()

    asyncio.run(main())
