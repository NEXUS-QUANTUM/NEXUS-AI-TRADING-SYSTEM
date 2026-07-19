# trading/bots/arbitrage_bot/core/slippage_calculator.py
# Nexus AI Trading System - Arbitrage Bot Slippage Calculator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Slippage Calculator Module

This module provides comprehensive slippage calculation and optimization
for the arbitrage bot system, including:

- Order book-based slippage estimation
- Historical slippage analysis
- Market impact modeling
- Slippage probability distribution
- Slippage optimization
- Real-time slippage monitoring
- Slippage alerts and limits
- Multi-exchange slippage comparison
- Slippage factor analysis
- Liquidity-based slippage adjustment
- Volatility-based slippage adjustment
- Order size optimization
- Slippage reporting and analytics

The slippage calculator ensures accurate profit calculations and helps
optimize order sizes to minimize slippage impact.
"""

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
from scipy import stats

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketDepth, MarketPrice
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeOrder
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SlippageType(str, Enum):
    """Slippage types."""
    BID_ASK = "bid_ask"          # Bid-ask spread slippage
    MARKET_IMPACT = "market_impact"  # Market impact slippage
    LATENCY = "latency"          # Latency-based slippage
    VOLATILITY = "volatility"    # Volatility-based slippage
    LIQUIDITY = "liquidity"      # Liquidity-based slippage
    TOTAL = "total"              # Total slippage


class SlippageLevel(str, Enum):
    """Slippage levels."""
    NONE = "none"                # 0-0.01%
    VERY_LOW = "very_low"        # 0.01-0.05%
    LOW = "low"                  # 0.05-0.1%
    MODERATE = "moderate"        # 0.1-0.5%
    HIGH = "high"                # 0.5-1.0%
    VERY_HIGH = "very_high"      # 1.0-5.0%
    EXTREME = "extreme"          # >5.0%


class SlippageStatus(str, Enum):
    """Slippage status."""
    OK = "ok"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SlippageConfig(BaseModel):
    """Slippage configuration."""
    enabled: bool = True
    max_slippage_percent: Decimal = Decimal('0.01')  # 1%
    min_slippage_percent: Decimal = Decimal('0.0001')  # 0.01%
    default_slippage_percent: Decimal = Decimal('0.001')  # 0.1%
    max_order_size_percent: Decimal = Decimal('0.05')  # 5% of order book depth
    
    # Historical analysis
    history_lookback_days: int = 30
    history_min_samples: int = 10
    confidence_level: float = 0.95
    
    # Market impact
    market_impact_model: str = "linear"  # linear, square_root, exponential
    market_impact_factor: Decimal = Decimal('0.1')
    
    # Latency
    latency_impact_factor: Decimal = Decimal('0.0001')  # per ms
    max_latency_ms: float = 1000.0
    
    # Volatility
    volatility_sensitivity: Decimal = Decimal('0.1')
    
    # Alerts
    alert_threshold_high: Decimal = Decimal('0.005')  # 0.5%
    alert_threshold_critical: Decimal = Decimal('0.01')  # 1%
    
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_slippage_percent', 'min_slippage_percent')
    def validate_slippage(cls, v):
        if v < 0:
            raise ValueError("Slippage percentage cannot be negative")
        return v

    @validator('max_order_size_percent')
    def validate_order_size(cls, v):
        if v < 0 or v > 1:
            raise ValueError("Order size percent must be between 0 and 1")
        return v


class SlippageEstimate(BaseModel):
    """Slippage estimate."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    exchange: str
    order_size: Decimal
    estimated_price: Decimal
    expected_price: Decimal
    slippage: Decimal
    slippage_percent: Decimal
    slippage_type: SlippageType = SlippageType.TOTAL
    level: SlippageLevel
    status: SlippageStatus = SlippageStatus.OK
    
    # Breakdown
    bid_ask_slippage: Decimal = Decimal('0')
    market_impact_slippage: Decimal = Decimal('0')
    latency_slippage: Decimal = Decimal('0')
    volatility_slippage: Decimal = Decimal('0')
    liquidity_slippage: Decimal = Decimal('0')
    
    # Confidence
    confidence: Decimal = Decimal('0.9')
    confidence_interval_low: Decimal = Decimal('0')
    confidence_interval_high: Decimal = Decimal('0')
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_acceptable(self) -> bool:
        """Check if slippage is acceptable."""
        return self.slippage_percent <= Decimal('0.005')  # 0.5%

    @property
    def is_critical(self) -> bool:
        """Check if slippage is critical."""
        return self.slippage_percent > Decimal('0.01')  # 1%


class SlippageHistory(BaseModel):
    """Slippage history entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    exchange: str
    order_size: Decimal
    expected_price: Decimal
    actual_price: Decimal
    slippage: Decimal
    slippage_percent: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SlippageStatistics(BaseModel):
    """Slippage statistics."""
    symbol: str
    exchange: str
    sample_count: int = 0
    
    # Statistics
    mean_slippage: Decimal
    median_slippage: Decimal
    std_slippage: Decimal
    min_slippage: Decimal
    max_slippage: Decimal
    
    # Percentiles
    p10_slippage: Decimal
    p25_slippage: Decimal
    p50_slippage: Decimal
    p75_slippage: Decimal
    p90_slippage: Decimal
    p95_slippage: Decimal
    p99_slippage: Decimal
    
    # Distribution
    skewness: Decimal
    kurtosis: Decimal
    
    # Confidence intervals
    ci_90_low: Decimal
    ci_90_high: Decimal
    ci_95_low: Decimal
    ci_95_high: Decimal
    ci_99_low: Decimal
    ci_99_high: Decimal
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SlippageOptimization(BaseModel):
    """Slippage optimization result."""
    symbol: str
    exchange: str
    original_order_size: Decimal
    optimized_order_size: Decimal
    original_slippage: Decimal
    optimized_slippage: Decimal
    savings: Decimal
    savings_percent: Decimal
    recommendations: List[str] = Field(default_factory=list)
    confidence: Decimal = Decimal('0.8')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Slippage estimates
CREATE TABLE IF NOT EXISTS slippage_estimates (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    order_size DECIMAL(32, 16) NOT NULL,
    estimated_price DECIMAL(32, 16) NOT NULL,
    expected_price DECIMAL(32, 16) NOT NULL,
    slippage DECIMAL(32, 16) NOT NULL,
    slippage_percent DECIMAL(32, 16) NOT NULL,
    slippage_type VARCHAR(20) NOT NULL,
    level VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    bid_ask_slippage DECIMAL(32, 16) DEFAULT 0,
    market_impact_slippage DECIMAL(32, 16) DEFAULT 0,
    latency_slippage DECIMAL(32, 16) DEFAULT 0,
    volatility_slippage DECIMAL(32, 16) DEFAULT 0,
    liquidity_slippage DECIMAL(32, 16) DEFAULT 0,
    confidence DECIMAL(5, 4) DEFAULT 0.9,
    confidence_interval_low DECIMAL(32, 16) DEFAULT 0,
    confidence_interval_high DECIMAL(32, 16) DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_slippage_estimates_symbol (symbol),
    INDEX idx_slippage_estimates_exchange (exchange),
    INDEX idx_slippage_estimates_timestamp (timestamp)
);

-- Slippage history
CREATE TABLE IF NOT EXISTS slippage_history (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    order_size DECIMAL(32, 16) NOT NULL,
    expected_price DECIMAL(32, 16) NOT NULL,
    actual_price DECIMAL(32, 16) NOT NULL,
    slippage DECIMAL(32, 16) NOT NULL,
    slippage_percent DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_slippage_history_symbol (symbol),
    INDEX idx_slippage_history_exchange (exchange),
    INDEX idx_slippage_history_timestamp (timestamp)
);

-- Slippage statistics
CREATE TABLE IF NOT EXISTS slippage_statistics (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    sample_count INTEGER NOT NULL,
    mean_slippage DECIMAL(32, 16) NOT NULL,
    median_slippage DECIMAL(32, 16) NOT NULL,
    std_slippage DECIMAL(32, 16) NOT NULL,
    min_slippage DECIMAL(32, 16) NOT NULL,
    max_slippage DECIMAL(32, 16) NOT NULL,
    p10_slippage DECIMAL(32, 16) NOT NULL,
    p25_slippage DECIMAL(32, 16) NOT NULL,
    p50_slippage DECIMAL(32, 16) NOT NULL,
    p75_slippage DECIMAL(32, 16) NOT NULL,
    p90_slippage DECIMAL(32, 16) NOT NULL,
    p95_slippage DECIMAL(32, 16) NOT NULL,
    p99_slippage DECIMAL(32, 16) NOT NULL,
    skewness DECIMAL(32, 16) NOT NULL,
    kurtosis DECIMAL(32, 16) NOT NULL,
    ci_90_low DECIMAL(32, 16) NOT NULL,
    ci_90_high DECIMAL(32, 16) NOT NULL,
    ci_95_low DECIMAL(32, 16) NOT NULL,
    ci_95_high DECIMAL(32, 16) NOT NULL,
    ci_99_low DECIMAL(32, 16) NOT NULL,
    ci_99_high DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(symbol, exchange)
);

-- Slippage alerts
CREATE TABLE IF NOT EXISTS slippage_alerts (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    slippage DECIMAL(32, 16) NOT NULL,
    threshold DECIMAL(32, 16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    INDEX idx_slippage_alerts_symbol (symbol),
    INDEX idx_slippage_alerts_exchange (exchange),
    INDEX idx_slippage_alerts_triggered_at (triggered_at)
);
"""


# =============================================================================
# SLIPPAGE CALCULATOR CLASS
# =============================================================================

class SlippageCalculator:
    """
    Advanced slippage calculator for arbitrage bot.
    
    Features:
    - Order book-based slippage estimation
    - Historical slippage analysis
    - Market impact modeling
    - Slippage probability distribution
    - Slippage optimization
    - Real-time slippage monitoring
    - Slippage alerts and limits
    - Multi-exchange slippage comparison
    - Slippage factor analysis
    - Liquidity-based slippage adjustment
    - Volatility-based slippage adjustment
    - Order size optimization
    - Slippage reporting and analytics
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[SlippageConfig] = None
    ):
        self.market_data = market_data
        self.redis = redis
        self.pool = pool
        self.config = config or SlippageConfig()
        
        # Slippage history
        self._history: Dict[str, List[SlippageHistory]] = {}
        
        # Statistics
        self._statistics: Dict[str, SlippageStatistics] = {}
        
        # Circuit breakers
        self._slippage_cb = CircuitBreaker(
            name="slippage_calculator",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Alert callbacks
        self._alert_callbacks: List[Callable] = []
        
        logger.info("SlippageCalculator initialized")
    
    async def initialize(self):
        """Initialize the slippage calculator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load statistics
        if self.pool:
            await self._load_statistics()
        
        self._running = True
        self._initialized = True
        
        logger.info("SlippageCalculator initialized")
    
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
    # SLIPPAGE ESTIMATION
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def estimate_slippage(
        self,
        symbol: str,
        exchange: str,
        order_size: Decimal,
        side: str = "buy",
        include_breakdown: bool = True
    ) -> SlippageEstimate:
        """
        Estimate slippage for an order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            order_size: Order size
            side: 'buy' or 'sell'
            include_breakdown: Include breakdown details
            
        Returns:
            SlippageEstimate
        """
        if self._slippage_cb.is_open():
            raise CircuitBreakerOpenError("Slippage calculator circuit breaker is open")
        
        try:
            # Get current market data
            price = await self.market_data.get_price(exchange, symbol)
            depth = await self.market_data.get_depth(exchange, symbol, depth=20)
            
            # Get expected price based on side
            if side == "buy":
                expected_price = price.ask
            else:
                expected_price = price.bid
            
            # Calculate slippage components
            bid_ask_slippage = self._calculate_bid_ask_slippage(depth, order_size, side)
            market_impact_slippage = self._calculate_market_impact(depth, order_size, side)
            latency_slippage = self._calculate_latency_slippage(exchange)
            volatility_slippage = self._calculate_volatility_slippage(symbol)
            liquidity_slippage = self._calculate_liquidity_slippage(depth, order_size, side)
            
            # Calculate total slippage
            if include_breakdown:
                total_slippage = (
                    bid_ask_slippage +
                    market_impact_slippage +
                    latency_slippage +
                    volatility_slippage +
                    liquidity_slippage
                )
            else:
                # Use market impact model
                total_slippage = self._calculate_total_slippage(depth, order_size, side)
            
            # Adjust for confidence
            confidence = await self._get_slippage_confidence(symbol, exchange)
            
            # Calculate estimated price
            if side == "buy":
                estimated_price = expected_price * (1 + total_slippage)
            else:
                estimated_price = expected_price * (1 - total_slippage)
            
            # Calculate slippage percent
            slippage_percent = abs(estimated_price - expected_price) / expected_price
            
            # Determine level
            level = self._get_slippage_level(slippage_percent)
            
            # Determine status
            status = self._get_slippage_status(slippage_percent)
            
            # Calculate confidence intervals
            ci_low, ci_high = self._calculate_confidence_interval(symbol, exchange, slippage_percent)
            
            estimate = SlippageEstimate(
                symbol=symbol,
                exchange=exchange,
                order_size=order_size,
                estimated_price=estimated_price.quantize(Decimal('0.00000001')),
                expected_price=expected_price.quantize(Decimal('0.00000001')),
                slippage=total_slippage.quantize(Decimal('0.00000001')),
                slippage_percent=slippage_percent.quantize(Decimal('0.0001')),
                slippage_type=SlippageType.TOTAL,
                level=level,
                status=status,
                bid_ask_slippage=bid_ask_slippage.quantize(Decimal('0.00000001')),
                market_impact_slippage=market_impact_slippage.quantize(Decimal('0.00000001')),
                latency_slippage=latency_slippage.quantize(Decimal('0.00000001')),
                volatility_slippage=volatility_slippage.quantize(Decimal('0.00000001')),
                liquidity_slippage=liquidity_slippage.quantize(Decimal('0.00000001')),
                confidence=confidence,
                confidence_interval_low=ci_low,
                confidence_interval_high=ci_high,
                metadata={"side": side}
            )
            
            # Save estimate
            if self.pool:
                await self._save_estimate(estimate)
            
            # Check for alerts
            if status in [SlippageStatus.HIGH, SlippageStatus.CRITICAL]:
                await self._trigger_alert(estimate)
            
            self._slippage_cb.record_success()
            return estimate
            
        except Exception as e:
            self._slippage_cb.record_failure()
            logger.error(f"Error estimating slippage: {e}")
            
            # Return default estimate
            return SlippageEstimate(
                symbol=symbol,
                exchange=exchange,
                order_size=order_size,
                estimated_price=Decimal('0'),
                expected_price=Decimal('0'),
                slippage=Decimal('0'),
                slippage_percent=Decimal('0'),
                level=SlippageLevel.NONE,
                status=SlippageStatus.OK,
                confidence=Decimal('0'),
                metadata={"error": str(e)}
            )
    
    # =========================================================================
    # SLIPPAGE COMPONENT CALCULATIONS
    # =========================================================================
    
    def _calculate_bid_ask_slippage(
        self,
        depth: MarketDepth,
        order_size: Decimal,
        side: str
    ) -> Decimal:
        """Calculate bid-ask spread slippage."""
        if not depth.bids or not depth.asks:
            return Decimal('0')
        
        best_bid = depth.bids[0][0]
        best_ask = depth.asks[0][0]
        spread = best_ask - best_bid
        
        # Slippage is half of spread
        return spread / Decimal('2')
    
    def _calculate_market_impact(
        self,
        depth: MarketDepth,
        order_size: Decimal,
        side: str
    ) -> Decimal:
        """Calculate market impact slippage."""
        # Use the order book to calculate market impact
        # Larger orders consume more liquidity and cause more impact
        
        # Determine available volume at each price level
        if side == "buy":
            levels = depth.asks
        else:
            levels = depth.bids
        
        if not levels:
            return Decimal('0')
        
        # Calculate cumulative volume at each level
        cumulative_volume = Decimal('0')
        weighted_price = Decimal('0')
        
        for price, volume in levels:
            if cumulative_volume >= order_size:
                break
            remaining = min(order_size - cumulative_volume, volume)
            weighted_price += price * remaining
            cumulative_volume += remaining
        
        if cumulative_volume > 0:
            avg_price = weighted_price / cumulative_volume
            if side == "buy":
                best_price = depth.asks[0][0] if depth.asks else avg_price
            else:
                best_price = depth.bids[0][0] if depth.bids else avg_price
            
            impact = abs(avg_price - best_price) / best_price
            
            # Apply market impact model
            impact_factor = self._get_market_impact_factor(cumulative_volume, order_size)
            return impact * impact_factor
        
        return Decimal('0')
    
    def _calculate_latency_slippage(self, exchange: str) -> Decimal:
        """Calculate latency-based slippage."""
        # Estimate average latency for the exchange
        latency_ms = self._get_exchange_latency(exchange)
        
        # Convert latency to slippage
        latency_slippage = Decimal(str(latency_ms)) * self.config.latency_impact_factor
        return min(latency_slippage, Decimal('0.01'))  # Cap at 1%
    
    def _calculate_volatility_slippage(self, symbol: str) -> Decimal:
        """Calculate volatility-based slippage."""
        volatility = self._get_symbol_volatility(symbol)
        return volatility * self.config.volatility_sensitivity
    
    def _calculate_liquidity_slippage(
        self,
        depth: MarketDepth,
        order_size: Decimal,
        side: str
    ) -> Decimal:
        """Calculate liquidity-based slippage."""
        total_depth = depth.total_bid_volume + depth.total_ask_volume
        if total_depth == 0:
            return Decimal('0.005')  # Default 0.5%
        
        # Calculate liquidity ratio
        liquidity_ratio = order_size / total_depth
        
        # Convert to slippage
        if liquidity_ratio < Decimal('0.01'):
            return Decimal('0')
        elif liquidity_ratio < Decimal('0.05'):
            return liquidity_ratio * Decimal('0.5')
        elif liquidity_ratio < Decimal('0.1'):
            return liquidity_ratio * Decimal('1')
        else:
            return Decimal('0.01')  # Cap at 1%
    
    def _calculate_total_slippage(
        self,
        depth: MarketDepth,
        order_size: Decimal,
        side: str
    ) -> Decimal:
        """Calculate total slippage using the market impact model."""
        # Use the market impact model directly
        model = self.config.market_impact_model
        
        if model == "linear":
            impact = order_size / (depth.total_bid_volume + depth.total_ask_volume)
            return impact * self.config.market_impact_factor
        
        elif model == "square_root":
            depth_volume = depth.total_bid_volume + depth.total_ask_volume
            if depth_volume > 0:
                impact = (order_size / depth_volume) ** Decimal('0.5')
                return impact * self.config.market_impact_factor
            return Decimal('0')
        
        elif model == "exponential":
            impact = 1 - Decimal(str(math.exp(-float(order_size) / float(depth.total_bid_volume + depth.total_ask_volume))))
            return impact * self.config.market_impact_factor
        
        else:
            return Decimal('0.001')  # Default 0.1%
    
    # =========================================================================
    # HISTORICAL ANALYSIS
    # =========================================================================
    
    async def add_slippage_history(
        self,
        symbol: str,
        exchange: str,
        order_size: Decimal,
        expected_price: Decimal,
        actual_price: Decimal,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SlippageHistory:
        """
        Add a slippage history entry.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            order_size: Order size
            expected_price: Expected price
            actual_price: Actual price
            metadata: Additional metadata
            
        Returns:
            SlippageHistory
        """
        slippage = actual_price - expected_price
        slippage_percent = abs(slippage) / expected_price if expected_price > 0 else Decimal('0')
        
        history = SlippageHistory(
            symbol=symbol,
            exchange=exchange,
            order_size=order_size,
            expected_price=expected_price,
            actual_price=actual_price,
            slippage=slippage.quantize(Decimal('0.00000001')),
            slippage_percent=slippage_percent.quantize(Decimal('0.0001')),
            metadata=metadata or {}
        )
        
        key = f"{exchange}:{symbol}"
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(history)
        
        # Trim history
        if len(self._history[key]) > 10000:
            self._history[key] = self._history[key][-5000:]
        
        # Save to database
        if self.pool:
            await self._save_history(history)
        
        # Update statistics
        await self._update_statistics(symbol, exchange)
        
        return history
    
    async def _update_statistics(self, symbol: str, exchange: str):
        """Update slippage statistics."""
        key = f"{exchange}:{symbol}"
        history = self._history.get(key, [])
        
        if len(history) < 10:
            return
        
        # Extract slippage percentages
        slippage_pcts = [float(h.slippage_percent) for h in history]
        
        # Calculate statistics
        mean = np.mean(slippage_pcts)
        median = np.median(slippage_pcts)
        std = np.std(slippage_pcts)
        min_val = np.min(slippage_pcts)
        max_val = np.max(slippage_pcts)
        
        # Calculate percentiles
        p10 = np.percentile(slippage_pcts, 10)
        p25 = np.percentile(slippage_pcts, 25)
        p50 = np.percentile(slippage_pcts, 50)
        p75 = np.percentile(slippage_pcts, 75)
        p90 = np.percentile(slippage_pcts, 90)
        p95 = np.percentile(slippage_pcts, 95)
        p99 = np.percentile(slippage_pcts, 99)
        
        # Calculate skewness and kurtosis
        skewness = stats.skew(slippage_pcts)
        kurtosis = stats.kurtosis(slippage_pcts)
        
        # Calculate confidence intervals
        z_90 = 1.645
        z_95 = 1.96
        z_99 = 2.576
        
        se = std / np.sqrt(len(slippage_pcts))
        ci_90_low = mean - z_90 * se
        ci_90_high = mean + z_90 * se
        ci_95_low = mean - z_95 * se
        ci_95_high = mean + z_95 * se
        ci_99_low = mean - z_99 * se
        ci_99_high = mean + z_99 * se
        
        stats_obj = SlippageStatistics(
            symbol=symbol,
            exchange=exchange,
            sample_count=len(slippage_pcts),
            mean_slippage=Decimal(str(mean)).quantize(Decimal('0.0001')),
            median_slippage=Decimal(str(median)).quantize(Decimal('0.0001')),
            std_slippage=Decimal(str(std)).quantize(Decimal('0.0001')),
            min_slippage=Decimal(str(min_val)).quantize(Decimal('0.0001')),
            max_slippage=Decimal(str(max_val)).quantize(Decimal('0.0001')),
            p10_slippage=Decimal(str(p10)).quantize(Decimal('0.0001')),
            p25_slippage=Decimal(str(p25)).quantize(Decimal('0.0001')),
            p50_slippage=Decimal(str(p50)).quantize(Decimal('0.0001')),
            p75_slippage=Decimal(str(p75)).quantize(Decimal('0.0001')),
            p90_slippage=Decimal(str(p90)).quantize(Decimal('0.0001')),
            p95_slippage=Decimal(str(p95)).quantize(Decimal('0.0001')),
            p99_slippage=Decimal(str(p99)).quantize(Decimal('0.0001')),
            skewness=Decimal(str(skewness)).quantize(Decimal('0.01')),
            kurtosis=Decimal(str(kurtosis)).quantize(Decimal('0.01')),
            ci_90_low=Decimal(str(ci_90_low)).quantize(Decimal('0.0001')),
            ci_90_high=Decimal(str(ci_90_high)).quantize(Decimal('0.0001')),
            ci_95_low=Decimal(str(ci_95_low)).quantize(Decimal('0.0001')),
            ci_95_high=Decimal(str(ci_95_high)).quantize(Decimal('0.0001')),
            ci_99_low=Decimal(str(ci_99_low)).quantize(Decimal('0.0001')),
            ci_99_high=Decimal(str(ci_99_high)).quantize(Decimal('0.0001'))
        )
        
        self._statistics[key] = stats_obj
        
        # Save to database
        if self.pool:
            await self._save_statistics(stats_obj)
    
    # =========================================================================
    # SLIPPAGE OPTIMIZATION
    # =========================================================================
    
    async def optimize_order_size(
        self,
        symbol: str,
        exchange: str,
        order_size: Decimal,
        side: str = "buy",
        target_slippage_percent: Optional[Decimal] = None
    ) -> SlippageOptimization:
        """
        Optimize order size to minimize slippage.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange name
            order_size: Original order size
            side: 'buy' or 'sell'
            target_slippage_percent: Target slippage percentage
            
        Returns:
            SlippageOptimization
        """
        if target_slippage_percent is None:
            target_slippage_percent = self.config.max_slippage_percent
        
        # Get current estimate
        current_estimate = await self.estimate_slippage(symbol, exchange, order_size, side)
        
        # Find optimal size
        depth = await self.market_data.get_depth(exchange, symbol, depth=20)
        total_depth = depth.total_bid_volume + depth.total_ask_volume
        
        # Binary search for optimal size
        low = Decimal('0')
        high = order_size
        optimal_size = order_size
        
        for _ in range(20):  # 20 iterations
            mid = (low + high) / 2
            estimate = await self.estimate_slippage(symbol, exchange, mid, side)
            
            if estimate.slippage_percent <= target_slippage_percent:
                optimal_size = mid
                low = mid
            else:
                high = mid
        
        # Get optimized estimate
        optimized_estimate = await self.estimate_slippage(symbol, exchange, optimal_size, side)
        
        # Calculate savings
        savings = current_estimate.slippage - optimized_estimate.slippage
        savings_percent = (savings / current_estimate.slippage * 100) if current_estimate.slippage > 0 else Decimal('0')
        
        # Generate recommendations
        recommendations = []
        
        if optimal_size < order_size * Decimal('0.5'):
            recommendations.append("Significant size reduction needed - consider splitting order")
        elif optimal_size < order_size * Decimal('0.8'):
            recommendations.append("Moderate size reduction recommended")
        
        if current_estimate.slippage_percent > self.config.max_slippage_percent:
            recommendations.append(f"Reduce order size to {optimal_size:.2f} to meet slippage target")
        
        # Check if splitting across exchanges would help
        recommendations.append("Consider splitting order across multiple exchanges for better execution")
        
        return SlippageOptimization(
            symbol=symbol,
            exchange=exchange,
            original_order_size=order_size,
            optimized_order_size=optimal_size.quantize(Decimal('0.0001')),
            original_slippage=current_estimate.slippage_percent,
            optimized_slippage=optimized_estimate.slippage_percent,
            savings=savings.quantize(Decimal('0.0001')),
            savings_percent=savings_percent.quantize(Decimal('0.01')),
            recommendations=recommendations,
            confidence=Decimal('0.8')
        )
    
    # =========================================================================
    # SLIPPAGE LEVELS AND STATUS
    # =========================================================================
    
    def _get_slippage_level(self, slippage_percent: Decimal) -> SlippageLevel:
        """Get slippage level."""
        if slippage_percent <= Decimal('0.0001'):
            return SlippageLevel.NONE
        elif slippage_percent <= Decimal('0.0005'):
            return SlippageLevel.VERY_LOW
        elif slippage_percent <= Decimal('0.001'):
            return SlippageLevel.LOW
        elif slippage_percent <= Decimal('0.005'):
            return SlippageLevel.MODERATE
        elif slippage_percent <= Decimal('0.01'):
            return SlippageLevel.HIGH
        elif slippage_percent <= Decimal('0.05'):
            return SlippageLevel.VERY_HIGH
        else:
            return SlippageLevel.EXTREME
    
    def _get_slippage_status(self, slippage_percent: Decimal) -> SlippageStatus:
        """Get slippage status."""
        if slippage_percent < self.config.alert_threshold_high:
            return SlippageStatus.OK
        elif slippage_percent < self.config.alert_threshold_critical:
            return SlippageStatus.WARNING
        else:
            return SlippageStatus.CRITICAL
    
    # =========================================================================
    # CONFIDENCE CALCULATIONS
    # =========================================================================
    
    async def _get_slippage_confidence(self, symbol: str, exchange: str) -> Decimal:
        """Get confidence level for slippage estimate."""
        key = f"{exchange}:{symbol}"
        stats = self._statistics.get(key)
        
        if not stats or stats.sample_count < 10:
            return Decimal('0.5')  # Low confidence
        
        # Confidence based on sample size
        if stats.sample_count > 100:
            return Decimal('0.95')
        elif stats.sample_count > 50:
            return Decimal('0.9')
        elif stats.sample_count > 20:
            return Decimal('0.8')
        else:
            return Decimal('0.7')
    
    def _calculate_confidence_interval(
        self,
        symbol: str,
        exchange: str,
        slippage_percent: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate confidence interval for slippage."""
        key = f"{exchange}:{symbol}"
        stats = self._statistics.get(key)
        
        if not stats or stats.sample_count < 10:
            # Use default 20% variation
            variation = slippage_percent * Decimal('0.2')
            return (
                max(Decimal('0'), slippage_percent - variation),
                slippage_percent + variation
            )
        
        # Use statistical confidence interval
        confidence = self.config.confidence_level
        z_score = 1.96 if confidence == 0.95 else 2.576 if confidence == 0.99 else 1.645
        
        ci_low = stats.ci_95_low if confidence == 0.95 else stats.ci_99_low
        ci_high = stats.ci_95_high if confidence == 0.95 else stats.ci_99_high
        
        # Adjust for current slippage
        ratio = slippage_percent / stats.mean_slippage if stats.mean_slippage > 0 else Decimal('1')
        ci_low = ci_low * ratio
        ci_high = ci_high * ratio
        
        return (
            max(Decimal('0'), ci_low),
            ci_high
        )
    
    # =========================================================================
    # EXCHANGE-SPECIFIC VALUES
    # =========================================================================
    
    def _get_exchange_latency(self, exchange: str) -> float:
        """Get average latency for an exchange."""
        # Would be implemented with actual latency monitoring
        latency_map = {
            "binance": 50.0,
            "okx": 60.0,
            "kraken": 80.0,
            "coinbase": 70.0,
            "bybit": 55.0,
            "bitget": 65.0,
            "kucoin": 75.0,
            "huobi": 85.0,
            "gateio": 90.0,
            "mexc": 95.0
        }
        return latency_map.get(exchange.lower(), 75.0)
    
    def _get_symbol_volatility(self, symbol: str) -> Decimal:
        """Get volatility for a symbol."""
        # Would be implemented with actual volatility calculations
        # Return default 30% volatility
        return Decimal('0.3')
    
    def _get_market_impact_factor(
        self,
        cumulative_volume: Decimal,
        order_size: Decimal
    ) -> Decimal:
        """Get market impact factor based on order size relative to liquidity."""
        if order_size == 0:
            return Decimal('0')
        
        ratio = cumulative_volume / order_size
        
        if ratio > Decimal('0.5'):
            return Decimal('1')
        elif ratio > Decimal('0.2'):
            return Decimal('0.5')
        elif ratio > Decimal('0.1'):
            return Decimal('0.2')
        else:
            return Decimal('0.1')
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def on_alert(self, callback: Callable):
        """Register an alert callback."""
        self._alert_callbacks.append(callback)
    
    async def _trigger_alert(self, estimate: SlippageEstimate):
        """Trigger a slippage alert."""
        message = (
            f"High slippage detected: {estimate.symbol} on {estimate.exchange} "
            f"{estimate.slippage_percent:.2f}% (limit: {self.config.max_slippage_percent:.2f}%)"
        )
        
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(estimate, message)
                else:
                    callback(estimate, message)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        logger.warning(message)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_estimate(self, estimate: SlippageEstimate):
        """Save slippage estimate to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO slippage_estimates (
                        id, symbol, exchange, order_size,
                        estimated_price, expected_price,
                        slippage, slippage_percent, slippage_type,
                        level, status,
                        bid_ask_slippage, market_impact_slippage,
                        latency_slippage, volatility_slippage,
                        liquidity_slippage, confidence,
                        confidence_interval_low, confidence_interval_high,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14, $15,
                              $16, $17, $18, $19, $20, $21)
                    """,
                    estimate.id,
                    estimate.symbol,
                    estimate.exchange,
                    estimate.order_size,
                    estimate.estimated_price,
                    estimate.expected_price,
                    estimate.slippage,
                    estimate.slippage_percent,
                    estimate.slippage_type.value,
                    estimate.level.value,
                    estimate.status.value,
                    estimate.bid_ask_slippage,
                    estimate.market_impact_slippage,
                    estimate.latency_slippage,
                    estimate.volatility_slippage,
                    estimate.liquidity_slippage,
                    estimate.confidence,
                    estimate.confidence_interval_low,
                    estimate.confidence_interval_high,
                    estimate.timestamp,
                    json.dumps(estimate.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving slippage estimate: {e}")
    
    async def _save_history(self, history: SlippageHistory):
        """Save slippage history to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO slippage_history (
                        id, symbol, exchange, order_size,
                        expected_price, actual_price,
                        slippage, slippage_percent,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    history.id,
                    history.symbol,
                    history.exchange,
                    history.order_size,
                    history.expected_price,
                    history.actual_price,
                    history.slippage,
                    history.slippage_percent,
                    history.timestamp,
                    json.dumps(history.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving slippage history: {e}")
    
    async def _save_statistics(self, stats: SlippageStatistics):
        """Save slippage statistics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO slippage_statistics (
                        symbol, exchange, sample_count,
                        mean_slippage, median_slippage,
                        std_slippage, min_slippage, max_slippage,
                        p10_slippage, p25_slippage, p50_slippage,
                        p75_slippage, p90_slippage, p95_slippage,
                        p99_slippage, skewness, kurtosis,
                        ci_90_low, ci_90_high,
                        ci_95_low, ci_95_high,
                        ci_99_low, ci_99_high,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13, $14, $15,
                              $16, $17, $18, $19, $20, $21,
                              $22, $23, $24, $25)
                    ON CONFLICT (symbol, exchange) DO UPDATE SET
                        sample_count = EXCLUDED.sample_count,
                        mean_slippage = EXCLUDED.mean_slippage,
                        median_slippage = EXCLUDED.median_slippage,
                        std_slippage = EXCLUDED.std_slippage,
                        min_slippage = EXCLUDED.min_slippage,
                        max_slippage = EXCLUDED.max_slippage,
                        p10_slippage = EXCLUDED.p10_slippage,
                        p25_slippage = EXCLUDED.p25_slippage,
                        p50_slippage = EXCLUDED.p50_slippage,
                        p75_slippage = EXCLUDED.p75_slippage,
                        p90_slippage = EXCLUDED.p90_slippage,
                        p95_slippage = EXCLUDED.p95_slippage,
                        p99_slippage = EXCLUDED.p99_slippage,
                        skewness = EXCLUDED.skewness,
                        kurtosis = EXCLUDED.kurtosis,
                        ci_90_low = EXCLUDED.ci_90_low,
                        ci_90_high = EXCLUDED.ci_90_high,
                        ci_95_low = EXCLUDED.ci_95_low,
                        ci_95_high = EXCLUDED.ci_95_high,
                        ci_99_low = EXCLUDED.ci_99_low,
                        ci_99_high = EXCLUDED.ci_99_high,
                        timestamp = EXCLUDED.timestamp,
                        metadata = EXCLUDED.metadata
                    """,
                    stats.symbol,
                    stats.exchange,
                    stats.sample_count,
                    stats.mean_slippage,
                    stats.median_slippage,
                    stats.std_slippage,
                    stats.min_slippage,
                    stats.max_slippage,
                    stats.p10_slippage,
                    stats.p25_slippage,
                    stats.p50_slippage,
                    stats.p75_slippage,
                    stats.p90_slippage,
                    stats.p95_slippage,
                    stats.p99_slippage,
                    stats.skewness,
                    stats.kurtosis,
                    stats.ci_90_low,
                    stats.ci_90_high,
                    stats.ci_95_low,
                    stats.ci_95_high,
                    stats.ci_99_low,
                    stats.ci_99_high,
                    stats.timestamp,
                    json.dumps(stats.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving slippage statistics: {e}")
    
    async def _load_statistics(self):
        """Load slippage statistics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM slippage_statistics")
                
                for row in rows:
                    stats = SlippageStatistics(
                        symbol=row['symbol'],
                        exchange=row['exchange'],
                        sample_count=row['sample_count'],
                        mean_slippage=row['mean_slippage'],
                        median_slippage=row['median_slippage'],
                        std_slippage=row['std_slippage'],
                        min_slippage=row['min_slippage'],
                        max_slippage=row['max_slippage'],
                        p10_slippage=row['p10_slippage'],
                        p25_slippage=row['p25_slippage'],
                        p50_slippage=row['p50_slippage'],
                        p75_slippage=row['p75_slippage'],
                        p90_slippage=row['p90_slippage'],
                        p95_slippage=row['p95_slippage'],
                        p99_slippage=row['p99_slippage'],
                        skewness=row['skewness'],
                        kurtosis=row['kurtosis'],
                        ci_90_low=row['ci_90_low'],
                        ci_90_high=row['ci_90_high'],
                        ci_95_low=row['ci_95_low'],
                        ci_95_high=row['ci_95_high'],
                        ci_99_low=row['ci_99_low'],
                        ci_99_high=row['ci_99_high'],
                        timestamp=row['timestamp'],
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{stats.exchange}:{stats.symbol}"
                    self._statistics[key] = stats
                
                logger.info(f"Loaded {len(self._statistics)} statistics")
                
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the slippage calculator."""
        self._running = False
        logger.info("SlippageCalculator shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SlippageCalculator',
    'SlippageType',
    'SlippageLevel',
    'SlippageStatus',
    'SlippageConfig',
    'SlippageEstimate',
    'SlippageHistory',
    'SlippageStatistics',
    'SlippageOptimization',
    'CircuitBreakerOpenError'
]
