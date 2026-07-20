# trading/bots/arbitrage_bot/data/liquidity_manager.py
# Nexus AI Trading System - Arbitrage Bot Liquidity Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Liquidity Manager Module

This module provides comprehensive liquidity management for the arbitrage
bot system, including:

- Multi-exchange liquidity aggregation
- Real-time liquidity monitoring
- Liquidity scoring and ranking
- Liquidity depth analysis
- Liquidity fragmentation analysis
- Cross-exchange liquidity comparison
- Liquidity-based order routing
- Liquidity alerts and notifications
- Liquidity forecasting
- Liquidity provider management
- Slippage estimation based on liquidity
- Market impact analysis
- Liquidity visualization
- Liquidity health monitoring

The liquidity manager ensures optimal execution by routing orders
to exchanges with the best liquidity conditions.
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
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketDepth, MarketPrice
from trading.bots.arbitrage_bot.data.depth_manager import DepthManager, DepthSnapshot, DepthLevel
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class LiquidityLevel(str, Enum):
    """Liquidity levels."""
    EXCELLENT = "excellent"   # Deep liquidity
    GOOD = "good"             # Good liquidity
    ADEQUATE = "adequate"     # Adequate liquidity
    POOR = "poor"             # Poor liquidity
    VERY_POOR = "very_poor"   # Very poor liquidity


class LiquidityStatus(str, Enum):
    """Liquidity status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNAVAILABLE = "unavailable"


class LiquiditySource(str, Enum):
    """Liquidity sources."""
    EXCHANGE = "exchange"
    MARKET_MAKER = "market_maker"
    AGGREGATOR = "aggregator"
    DEX = "dex"
    CEX = "cex"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class LiquidityConfig(BaseModel):
    """Liquidity configuration."""
    enabled: bool = True
    min_liquidity_score: int = 30
    max_spread_percent: Decimal = Decimal('0.005')  # 0.5%
    min_depth_volume: Decimal = Decimal('1000')
    liquidity_refresh_interval: int = 5  # seconds
    alert_threshold_low: int = 20
    alert_threshold_critical: int = 10
    max_slippage_percent: Decimal = Decimal('0.01')  # 1%
    use_weighted_liquidity: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('min_liquidity_score')
    def validate_score(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Liquidity score must be between 0 and 100")
        return v

    @validator('min_depth_volume')
    def validate_volume(cls, v):
        if v <= 0:
            raise ValueError("Minimum depth volume must be positive")
        return v


class LiquidityMetrics(BaseModel):
    """Liquidity metrics."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Core metrics
    liquidity_score: Decimal  # 0-100
    liquidity_level: LiquidityLevel
    liquidity_status: LiquidityStatus
    
    # Depth metrics
    depth_bid_volume: Decimal
    depth_ask_volume: Decimal
    depth_total_volume: Decimal
    depth_bid_count: int
    depth_ask_count: int
    
    # Spread metrics
    spread: Decimal
    spread_percent: Decimal
    average_spread_1h: Optional[Decimal] = None
    spread_volatility: Optional[Decimal] = None
    
    # Volume metrics
    volume_24h: Optional[Decimal] = None
    volume_avg_1h: Optional[Decimal] = None
    volume_volatility: Optional[Decimal] = None
    
    # Order book metrics
    bid_ask_imbalance: Decimal  # (-1 to 1)
    market_depth_score: Decimal  # 0-100
    
    # Slippage estimates
    estimated_slippage_1k: Decimal  # Slippage for $1000 order
    estimated_slippage_10k: Decimal  # Slippage for $10,000 order
    estimated_slippage_100k: Decimal  # Slippage for $100,000 order
    
    # Market impact
    market_impact_1k: Decimal
    market_impact_10k: Decimal
    market_impact_100k: Decimal
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LiquidityRanking(BaseModel):
    """Liquidity ranking."""
    exchange: str
    symbol: str
    liquidity_score: Decimal
    liquidity_level: LiquidityLevel
    depth_volume: Decimal
    spread: Decimal
    rank: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LiquidityAlert(BaseModel):
    """Liquidity alert."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    severity: str  # info, warning, critical
    message: str
    liquidity_score: Decimal
    threshold: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LiquidityForecast(BaseModel):
    """Liquidity forecast."""
    exchange: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    forecast_hours: int = 1
    predicted_liquidity_score: Decimal
    confidence_interval_low: Decimal
    confidence_interval_high: Decimal
    trend: str  # increasing, decreasing, stable
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Liquidity metrics
CREATE TABLE IF NOT EXISTS liquidity_metrics (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    liquidity_score DECIMAL(32, 16) NOT NULL,
    liquidity_level VARCHAR(20) NOT NULL,
    liquidity_status VARCHAR(20) NOT NULL,
    depth_bid_volume DECIMAL(32, 16) NOT NULL,
    depth_ask_volume DECIMAL(32, 16) NOT NULL,
    depth_total_volume DECIMAL(32, 16) NOT NULL,
    depth_bid_count INTEGER NOT NULL,
    depth_ask_count INTEGER NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    spread_percent DECIMAL(32, 16) NOT NULL,
    average_spread_1h DECIMAL(32, 16),
    spread_volatility DECIMAL(32, 16),
    volume_24h DECIMAL(32, 16),
    volume_avg_1h DECIMAL(32, 16),
    volume_volatility DECIMAL(32, 16),
    bid_ask_imbalance DECIMAL(32, 16) NOT NULL,
    market_depth_score DECIMAL(32, 16) NOT NULL,
    estimated_slippage_1k DECIMAL(32, 16) NOT NULL,
    estimated_slippage_10k DECIMAL(32, 16) NOT NULL,
    estimated_slippage_100k DECIMAL(32, 16) NOT NULL,
    market_impact_1k DECIMAL(32, 16) NOT NULL,
    market_impact_10k DECIMAL(32, 16) NOT NULL,
    market_impact_100k DECIMAL(32, 16) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_liquidity_metrics_exchange (exchange),
    INDEX idx_liquidity_metrics_symbol (symbol),
    INDEX idx_liquidity_metrics_timestamp (timestamp)
);

-- Liquidity rankings
CREATE TABLE IF NOT EXISTS liquidity_rankings (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    liquidity_score DECIMAL(32, 16) NOT NULL,
    liquidity_level VARCHAR(20) NOT NULL,
    depth_volume DECIMAL(32, 16) NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    rank INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    UNIQUE(exchange, symbol, timestamp)
);

-- Liquidity alerts
CREATE TABLE IF NOT EXISTS liquidity_alerts (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    liquidity_score DECIMAL(32, 16) NOT NULL,
    threshold DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    INDEX idx_liquidity_alerts_exchange (exchange),
    INDEX idx_liquidity_alerts_symbol (symbol),
    INDEX idx_liquidity_alerts_timestamp (timestamp)
);

-- Liquidity forecasts
CREATE TABLE IF NOT EXISTS liquidity_forecasts (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    forecast_hours INTEGER NOT NULL,
    predicted_liquidity_score DECIMAL(32, 16) NOT NULL,
    confidence_interval_low DECIMAL(32, 16) NOT NULL,
    confidence_interval_high DECIMAL(32, 16) NOT NULL,
    trend VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(exchange, symbol, forecast_hours, timestamp)
);
"""


# =============================================================================
# LIQUIDITY MANAGER CLASS
# =============================================================================

class LiquidityManager:
    """
    Advanced liquidity manager for arbitrage bot.
    
    Features:
    - Multi-exchange liquidity aggregation
    - Real-time liquidity monitoring
    - Liquidity scoring and ranking
    - Liquidity depth analysis
    - Liquidity fragmentation analysis
    - Cross-exchange liquidity comparison
    - Liquidity-based order routing
    - Liquidity alerts and notifications
    - Liquidity forecasting
    - Liquidity provider management
    - Slippage estimation based on liquidity
    - Market impact analysis
    - Liquidity visualization
    - Liquidity health monitoring
    """
    
    def __init__(
        self,
        depth_manager: DepthManager,
        market_data: MarketDataManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[LiquidityConfig] = None
    ):
        self.depth_manager = depth_manager
        self.market_data = market_data
        self.redis = redis
        self.pool = pool
        self.config = config or LiquidityConfig()
        
        # Liquidity metrics cache
        self._metrics: Dict[str, LiquidityMetrics] = {}  # exchange:symbol -> metrics
        self._rankings: Dict[str, LiquidityRanking] = {}  # symbol -> ranking
        
        # Alerts
        self._alerts: List[LiquidityAlert] = []
        
        # Forecasts
        self._forecasts: Dict[str, LiquidityForecast] = {}
        
        # Circuit breakers
        self._liquidity_cb = CircuitBreaker(
            name="liquidity_manager",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Update task
        self._update_task: Optional[asyncio.Task] = None
        
        logger.info("LiquidityManager initialized")
    
    async def initialize(self):
        """Initialize the liquidity manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load metrics
        if self.pool:
            await self._load_metrics()
        
        # Load rankings
        if self.pool:
            await self._load_rankings()
        
        # Start update loop
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("LiquidityManager initialized")
    
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
    # LIQUIDITY ANALYSIS
    # =========================================================================
    
    async def analyze_liquidity(
        self,
        exchange: str,
        symbol: str,
        refresh: bool = False
    ) -> LiquidityMetrics:
        """
        Analyze liquidity for a symbol on an exchange.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            refresh: Force refresh
            
        Returns:
            LiquidityMetrics
        """
        if self._liquidity_cb.is_open():
            raise CircuitBreakerOpenError("Liquidity manager circuit breaker is open")
        
        key = f"{exchange}:{symbol}"
        
        if not refresh and key in self._metrics:
            # Check if metrics are still fresh
            metrics = self._metrics[key]
            age = (datetime.utcnow() - metrics.timestamp).total_seconds()
            if age < self.config.liquidity_refresh_interval:
                return metrics
        
        try:
            # Get depth snapshot
            depth = await self.depth_manager.get_depth(exchange, symbol, DepthLevel.LEVEL_3)
            
            if not depth:
                raise ValueError(f"No depth data for {symbol} on {exchange}")
            
            # Calculate liquidity metrics
            metrics = await self._calculate_liquidity_metrics(exchange, symbol, depth)
            
            # Update cache
            async with self._lock:
                self._metrics[key] = metrics
            
            # Save to database
            if self.pool:
                await self._save_metrics(metrics)
            
            # Check for alerts
            await self._check_alerts(metrics)
            
            # Record success
            self._liquidity_cb.record_success()
            
            return metrics
            
        except Exception as e:
            self._liquidity_cb.record_failure()
            logger.error(f"Liquidity analysis error: {e}")
            
            # Return cached metrics if available
            if key in self._metrics:
                return self._metrics[key]
            
            raise
    
    async def _calculate_liquidity_metrics(
        self,
        exchange: str,
        symbol: str,
        depth: DepthSnapshot
    ) -> LiquidityMetrics:
        """
        Calculate liquidity metrics from depth data.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            depth: Depth snapshot
            
        Returns:
            LiquidityMetrics
        """
        # Core metrics
        total_bid_volume = depth.total_bid_volume
        total_ask_volume = depth.total_ask_volume
        total_volume = total_bid_volume + total_ask_volume
        
        # Spread metrics
        spread = depth.spread or Decimal('0')
        mid_price = depth.mid_price or Decimal('1')
        spread_percent = (spread / mid_price * 100) if mid_price > 0 else Decimal('0')
        
        # Calculate liquidity score (0-100)
        liquidity_score = await self._calculate_liquidity_score(depth)
        
        # Determine level
        liquidity_level = self._get_liquidity_level(liquidity_score)
        liquidity_status = self._get_liquidity_status(liquidity_score)
        
        # Calculate bid-ask imbalance
        bid_ask_imbalance = (
            (total_bid_volume - total_ask_volume) / total_volume
            if total_volume > 0 else Decimal('0')
        )
        
        # Calculate market depth score
        depth_score = await self._calculate_depth_score(depth)
        
        # Estimate slippage for different order sizes
        slippage_1k = await self._estimate_slippage(depth, Decimal('1000'))
        slippage_10k = await self._estimate_slippage(depth, Decimal('10000'))
        slippage_100k = await self._estimate_slippage(depth, Decimal('100000'))
        
        # Calculate market impact
        impact_1k = await self._estimate_market_impact(depth, Decimal('1000'))
        impact_10k = await self._estimate_market_impact(depth, Decimal('10000'))
        impact_100k = await self._estimate_market_impact(depth, Decimal('100000'))
        
        return LiquidityMetrics(
            exchange=exchange,
            symbol=symbol,
            liquidity_score=liquidity_score.quantize(Decimal('0.01')),
            liquidity_level=liquidity_level,
            liquidity_status=liquidity_status,
            depth_bid_volume=total_bid_volume.quantize(Decimal('0.0001')),
            depth_ask_volume=total_ask_volume.quantize(Decimal('0.0001')),
            depth_total_volume=total_volume.quantize(Decimal('0.0001')),
            depth_bid_count=len(depth.bids),
            depth_ask_count=len(depth.asks),
            spread=spread.quantize(Decimal('0.00000001')),
            spread_percent=spread_percent.quantize(Decimal('0.0001')),
            bid_ask_imbalance=bid_ask_imbalance.quantize(Decimal('0.0001')),
            market_depth_score=depth_score.quantize(Decimal('0.01')),
            estimated_slippage_1k=slippage_1k.quantize(Decimal('0.0001')),
            estimated_slippage_10k=slippage_10k.quantize(Decimal('0.0001')),
            estimated_slippage_100k=slippage_100k.quantize(Decimal('0.0001')),
            market_impact_1k=impact_1k.quantize(Decimal('0.0001')),
            market_impact_10k=impact_10k.quantize(Decimal('0.0001')),
            market_impact_100k=impact_100k.quantize(Decimal('0.0001'))
        )
    
    async def _calculate_liquidity_score(self, depth: DepthSnapshot) -> Decimal:
        """
        Calculate liquidity score.
        
        Args:
            depth: Depth snapshot
            
        Returns:
            Liquidity score (0-100)
        """
        total_volume = depth.total_volume
        spread = depth.spread or Decimal('0')
        mid_price = depth.mid_price or Decimal('1')
        
        # Volume component (0-50)
        volume_score = min(total_volume / Decimal('10000'), Decimal('1')) * 50
        
        # Spread component (0-50)
        spread_percent = (spread / mid_price * 100) if mid_price > 0 else Decimal('0')
        spread_score = max(Decimal('0'), (Decimal('0.01') - spread_percent) / Decimal('0.01') * 50)
        spread_score = min(spread_score, Decimal('50'))
        
        # Weighted score
        if self.config.use_weighted_liquidity:
            # Use weighted average with depth volume weight
            total_score = volume_score * Decimal('0.6') + spread_score * Decimal('0.4')
        else:
            total_score = (volume_score + spread_score) / 2
        
        # Apply min/max
        return max(Decimal('0'), min(total_score, Decimal('100')))
    
    def _get_liquidity_level(self, score: Decimal) -> LiquidityLevel:
        """Get liquidity level from score."""
        if score >= 80:
            return LiquidityLevel.EXCELLENT
        elif score >= 60:
            return LiquidityLevel.GOOD
        elif score >= 40:
            return LiquidityLevel.ADEQUATE
        elif score >= 20:
            return LiquidityLevel.POOR
        else:
            return LiquidityLevel.VERY_POOR
    
    def _get_liquidity_status(self, score: Decimal) -> LiquidityStatus:
        """Get liquidity status from score."""
        if score >= 30:
            return LiquidityStatus.HEALTHY
        elif score >= 15:
            return LiquidityStatus.DEGRADED
        else:
            return LiquidityStatus.CRITICAL
    
    async def _calculate_depth_score(self, depth: DepthSnapshot) -> Decimal:
        """
        Calculate market depth score.
        
        Args:
            depth: Depth snapshot
            
        Returns:
            Depth score (0-100)
        """
        # Count levels
        bid_count = len(depth.bids)
        ask_count = len(depth.asks)
        total_count = bid_count + ask_count
        
        # Score based on number of levels
        if total_count >= 50:
            score = Decimal('100')
        elif total_count >= 30:
            score = Decimal('80')
        elif total_count >= 15:
            score = Decimal('60')
        elif total_count >= 5:
            score = Decimal('40')
        else:
            score = Decimal('20')
        
        # Adjust for volume distribution
        total_volume = depth.total_volume
        if total_volume > Decimal('100000'):
            score = min(score + Decimal('20'), Decimal('100'))
        elif total_volume > Decimal('10000'):
            score = min(score + Decimal('10'), Decimal('100'))
        
        return score
    
    # =========================================================================
    # SLIPPAGE AND MARKET IMPACT
    # =========================================================================
    
    async def _estimate_slippage(
        self,
        depth: DepthSnapshot,
        order_size: Decimal
    ) -> Decimal:
        """
        Estimate slippage for an order.
        
        Args:
            depth: Depth snapshot
            order_size: Order size in USD
            
        Returns:
            Estimated slippage percentage
        """
        if order_size <= 0:
            return Decimal('0')
        
        total_volume = depth.total_volume
        
        if total_volume == 0:
            return Decimal('1')  # 1% default
        
        # Calculate ratio of order to total volume
        ratio = order_size / total_volume
        
        # Slippage increases with order size relative to liquidity
        slippage = ratio * Decimal('5')  # 5x multiplier
        
        # Cap at 5%
        return min(slippage, Decimal('5'))
    
    async def _estimate_market_impact(
        self,
        depth: DepthSnapshot,
        order_size: Decimal
    ) -> Decimal:
        """
        Estimate market impact of an order.
        
        Args:
            depth: Depth snapshot
            order_size: Order size in USD
            
        Returns:
            Estimated market impact percentage
        """
        if order_size <= 0:
            return Decimal('0')
        
        total_volume = depth.total_volume
        
        if total_volume == 0:
            return Decimal('1')
        
        # Calculate impact
        ratio = order_size / total_volume
        
        # Square root impact model
        impact = (ratio ** Decimal('0.5')) * Decimal('2')
        
        # Cap at 10%
        return min(impact, Decimal('10'))
    
    # =========================================================================
    # LIQUIDITY RANKING
    # =========================================================================
    
    async def rank_liquidity(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None
    ) -> List[LiquidityRanking]:
        """
        Rank liquidity across exchanges.
        
        Args:
            symbol: Trading symbol
            exchanges: List of exchanges (None = all)
            
        Returns:
            List of LiquidityRanking sorted by score
        """
        if exchanges is None:
            exchanges = list(self.depth_manager._snapshots.keys())
            exchanges = [e.split(':')[0] for e in exchanges if e.endswith(f":{symbol}")]
            exchanges = list(set(exchanges))
        
        rankings = []
        
        for exchange in exchanges:
            try:
                metrics = await self.analyze_liquidity(exchange, symbol, refresh=True)
                
                ranking = LiquidityRanking(
                    exchange=exchange,
                    symbol=symbol,
                    liquidity_score=metrics.liquidity_score,
                    liquidity_level=metrics.liquidity_level,
                    depth_volume=metrics.depth_total_volume,
                    spread=metrics.spread,
                    rank=0,
                    timestamp=datetime.utcnow()
                )
                rankings.append(ranking)
                
            except Exception as e:
                logger.error(f"Error ranking liquidity for {exchange}: {e}")
        
        # Sort by liquidity score descending
        rankings.sort(key=lambda x: x.liquidity_score, reverse=True)
        
        # Assign ranks
        for i, ranking in enumerate(rankings):
            ranking.rank = i + 1
        
        # Cache rankings
        for ranking in rankings:
            key = f"{ranking.symbol}:{ranking.exchange}"
            self._rankings[key] = ranking
        
        # Save to database
        if self.pool:
            await self._save_rankings(rankings)
        
        return rankings
    
    async def get_best_liquidity(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None
    ) -> Optional[LiquidityRanking]:
        """
        Get the exchange with the best liquidity.
        
        Args:
            symbol: Trading symbol
            exchanges: List of exchanges
            
        Returns:
            Best LiquidityRanking or None
        """
        rankings = await self.rank_liquidity(symbol, exchanges)
        return rankings[0] if rankings else None
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def _check_alerts(self, metrics: LiquidityMetrics):
        """
        Check for liquidity alerts.
        
        Args:
            metrics: Liquidity metrics
        """
        score = metrics.liquidity_score
        
        if score < self.config.alert_threshold_critical:
            severity = "critical"
            threshold = self.config.alert_threshold_critical
        elif score < self.config.alert_threshold_low:
            severity = "warning"
            threshold = self.config.alert_threshold_low
        else:
            return
        
        alert = LiquidityAlert(
            exchange=metrics.exchange,
            symbol=metrics.symbol,
            severity=severity,
            message=f"Low liquidity detected: {score:.1f} (threshold: {threshold})",
            liquidity_score=score,
            threshold=Decimal(str(threshold)),
            timestamp=datetime.utcnow()
        )
        
        self._alerts.append(alert)
        
        # Save alert
        if self.pool:
            await self._save_alert(alert)
        
        # Trigger handlers
        await self._trigger_handlers("liquidity_alert", alert)
        
        logger.warning(
            f"Liquidity alert: {metrics.exchange}:{metrics.symbol} "
            f"score={score:.1f} severity={severity}"
        )
    
    # =========================================================================
    # LIQUIDITY FORECASTING
    # =========================================================================
    
    async def forecast_liquidity(
        self,
        exchange: str,
        symbol: str,
        hours: int = 1
    ) -> LiquidityForecast:
        """
        Forecast liquidity for a symbol.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            hours: Forecast horizon in hours
            
        Returns:
            LiquidityForecast
        """
        # Get historical metrics
        if not self.pool:
            # Simple forecast based on current metrics
            current = await self.analyze_liquidity(exchange, symbol)
            
            return LiquidityForecast(
                exchange=exchange,
                symbol=symbol,
                forecast_hours=hours,
                predicted_liquidity_score=current.liquidity_score,
                confidence_interval_low=current.liquidity_score * Decimal('0.8'),
                confidence_interval_high=current.liquidity_score * Decimal('1.2'),
                trend="stable",
                metadata={"current_score": float(current.liquidity_score)}
            )
        
        try:
            # Get historical data
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM liquidity_metrics
                    WHERE exchange = $1 AND symbol = $2
                    ORDER BY timestamp DESC
                    LIMIT 100
                    """,
                    exchange,
                    symbol
                )
                
                if len(rows) < 10:
                    # Not enough data
                    current = await self.analyze_liquidity(exchange, symbol)
                    return LiquidityForecast(
                        exchange=exchange,
                        symbol=symbol,
                        forecast_hours=hours,
                        predicted_liquidity_score=current.liquidity_score,
                        confidence_interval_low=current.liquidity_score * Decimal('0.5'),
                        confidence_interval_high=current.liquidity_score * Decimal('1.5'),
                        trend="stable",
                        metadata={"current_score": float(current.liquidity_score)}
                    )
                
                # Extract scores
                scores = [row['liquidity_score'] for row in rows]
                timestamps = [row['timestamp'] for row in rows]
                
                # Simple linear regression
                x = np.array([(t - timestamps[-1]).total_seconds() / 3600 for t in timestamps])
                y = np.array([float(s) for s in scores])
                
                if len(x) > 1:
                    slope, intercept = np.polyfit(x, y, 1)
                    predicted = intercept + slope * hours
                else:
                    predicted = y[0] if y else 50
                
                # Calculate confidence intervals
                std = np.std(y) if len(y) > 1 else 5
                ci_low = predicted - 1.96 * std
                ci_high = predicted + 1.96 * std
                
                # Determine trend
                if slope > 0.1:
                    trend = "increasing"
                elif slope < -0.1:
                    trend = "decreasing"
                else:
                    trend = "stable"
                
                forecast = LiquidityForecast(
                    exchange=exchange,
                    symbol=symbol,
                    forecast_hours=hours,
                    predicted_liquidity_score=Decimal(str(max(0, predicted))).quantize(Decimal('0.01')),
                    confidence_interval_low=Decimal(str(max(0, ci_low))).quantize(Decimal('0.01')),
                    confidence_interval_high=Decimal(str(max(0, ci_high))).quantize(Decimal('0.01')),
                    trend=trend,
                    metadata={"slope": float(slope), "intercept": float(intercept)}
                )
                
                # Cache forecast
                key = f"{exchange}:{symbol}:{hours}"
                self._forecasts[key] = forecast
                
                # Save forecast
                if self.pool:
                    await self._save_forecast(forecast)
                
                return forecast
                
        except Exception as e:
            logger.error(f"Liquidity forecast error: {e}")
            
            # Fallback to current metrics
            current = await self.analyze_liquidity(exchange, symbol)
            return LiquidityForecast(
                exchange=exchange,
                symbol=symbol,
                forecast_hours=hours,
                predicted_liquidity_score=current.liquidity_score,
                confidence_interval_low=current.liquidity_score * Decimal('0.6'),
                confidence_interval_high=current.liquidity_score * Decimal('1.4'),
                trend="stable",
                metadata={"error": str(e)}
            )
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_liquidity_update(self, handler: Callable):
        """Register a liquidity update handler."""
        key = "liquidity_update"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
    
    async def on_liquidity_alert(self, handler: Callable):
        """Register a liquidity alert handler."""
        key = "liquidity_alert"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
    
    async def _trigger_handlers(self, event: str, data: Any):
        """Trigger handlers for an event."""
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Handler error: {e}")
    
    # =========================================================================
    # UPDATE LOOP
    # =========================================================================
    
    async def _update_loop(self):
        """Periodic update loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.liquidity_refresh_interval)
                
                # Refresh liquidity for all tracked symbols
                for key in list(self._metrics.keys()):
                    try:
                        exchange, symbol = key.split(':')
                        await self.analyze_liquidity(exchange, symbol, refresh=True)
                    except Exception as e:
                        logger.error(f"Error refreshing liquidity for {key}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(10)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_metrics(self):
        """Load liquidity metrics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM liquidity_metrics
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """
                )
                
                for row in rows:
                    metrics = LiquidityMetrics(
                        id=row['id'],
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        timestamp=row['timestamp'],
                        liquidity_score=row['liquidity_score'],
                        liquidity_level=LiquidityLevel(row['liquidity_level']),
                        liquidity_status=LiquidityStatus(row['liquidity_status']),
                        depth_bid_volume=row['depth_bid_volume'],
                        depth_ask_volume=row['depth_ask_volume'],
                        depth_total_volume=row['depth_total_volume'],
                        depth_bid_count=row['depth_bid_count'],
                        depth_ask_count=row['depth_ask_count'],
                        spread=row['spread'],
                        spread_percent=row['spread_percent'],
                        average_spread_1h=row['average_spread_1h'],
                        spread_volatility=row['spread_volatility'],
                        volume_24h=row['volume_24h'],
                        volume_avg_1h=row['volume_avg_1h'],
                        volume_volatility=row['volume_volatility'],
                        bid_ask_imbalance=row['bid_ask_imbalance'],
                        market_depth_score=row['market_depth_score'],
                        estimated_slippage_1k=row['estimated_slippage_1k'],
                        estimated_slippage_10k=row['estimated_slippage_10k'],
                        estimated_slippage_100k=row['estimated_slippage_100k'],
                        market_impact_1k=row['market_impact_1k'],
                        market_impact_10k=row['market_impact_10k'],
                        market_impact_100k=row['market_impact_100k'],
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{metrics.exchange}:{metrics.symbol}"
                    self._metrics[key] = metrics
                
                logger.info(f"Loaded {len(self._metrics)} liquidity metrics")
                
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
    
    async def _load_rankings(self):
        """Load liquidity rankings from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (symbol, exchange) * 
                    FROM liquidity_rankings
                    ORDER BY symbol, exchange, timestamp DESC
                    """
                )
                
                for row in rows:
                    ranking = LiquidityRanking(
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        liquidity_score=row['liquidity_score'],
                        liquidity_level=LiquidityLevel(row['liquidity_level']),
                        depth_volume=row['depth_volume'],
                        spread=row['spread'],
                        rank=row['rank'],
                        timestamp=row['timestamp']
                    )
                    
                    key = f"{ranking.symbol}:{ranking.exchange}"
                    self._rankings[key] = ranking
                
                logger.info(f"Loaded {len(self._rankings)} liquidity rankings")
                
        except Exception as e:
            logger.error(f"Error loading rankings: {e}")
    
    async def _save_metrics(self, metrics: LiquidityMetrics):
        """Save liquidity metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO liquidity_metrics (
                        id, exchange, symbol, timestamp,
                        liquidity_score, liquidity_level, liquidity_status,
                        depth_bid_volume, depth_ask_volume, depth_total_volume,
                        depth_bid_count, depth_ask_count,
                        spread, spread_percent,
                        average_spread_1h, spread_volatility,
                        volume_24h, volume_avg_1h, volume_volatility,
                        bid_ask_imbalance, market_depth_score,
                        estimated_slippage_1k, estimated_slippage_10k,
                        estimated_slippage_100k,
                        market_impact_1k, market_impact_10k, market_impact_100k,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7,
                              $8, $9, $10, $11, $12,
                              $13, $14, $15, $16,
                              $17, $18, $19,
                              $20, $21,
                              $22, $23, $24, $25, $26, $27,
                              $28)
                    """,
                    metrics.id,
                    metrics.exchange,
                    metrics.symbol,
                    metrics.timestamp,
                    metrics.liquidity_score,
                    metrics.liquidity_level.value,
                    metrics.liquidity_status.value,
                    metrics.depth_bid_volume,
                    metrics.depth_ask_volume,
                    metrics.depth_total_volume,
                    metrics.depth_bid_count,
                    metrics.depth_ask_count,
                    metrics.spread,
                    metrics.spread_percent,
                    metrics.average_spread_1h,
                    metrics.spread_volatility,
                    metrics.volume_24h,
                    metrics.volume_avg_1h,
                    metrics.volume_volatility,
                    metrics.bid_ask_imbalance,
                    metrics.market_depth_score,
                    metrics.estimated_slippage_1k,
                    metrics.estimated_slippage_10k,
                    metrics.estimated_slippage_100k,
                    metrics.market_impact_1k,
                    metrics.market_impact_10k,
                    metrics.market_impact_100k,
                    json.dumps(metrics.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    async def _save_rankings(self, rankings: List[LiquidityRanking]):
        """Save liquidity rankings to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                for ranking in rankings:
                    await conn.execute(
                        """
                        INSERT INTO liquidity_rankings (
                            exchange, symbol, liquidity_score,
                            liquidity_level, depth_volume, spread,
                            rank, timestamp
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        ranking.exchange,
                        ranking.symbol,
                        ranking.liquidity_score,
                        ranking.liquidity_level.value,
                        ranking.depth_volume,
                        ranking.spread,
                        ranking.rank,
                        ranking.timestamp
                    )
        except Exception as e:
            logger.error(f"Error saving rankings: {e}")
    
    async def _save_alert(self, alert: LiquidityAlert):
        """Save liquidity alert to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO liquidity_alerts (
                        id, exchange, symbol, severity,
                        message, liquidity_score, threshold,
                        timestamp, acknowledged, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    alert.id,
                    alert.exchange,
                    alert.symbol,
                    alert.severity,
                    alert.message,
                    alert.liquidity_score,
                    alert.threshold,
                    alert.timestamp,
                    alert.acknowledged,
                    json.dumps(alert.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving alert: {e}")
    
    async def _save_forecast(self, forecast: LiquidityForecast):
        """Save liquidity forecast to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO liquidity_forecasts (
                        exchange, symbol, timestamp,
                        forecast_hours, predicted_liquidity_score,
                        confidence_interval_low, confidence_interval_high,
                        trend, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (exchange, symbol, forecast_hours, timestamp) DO UPDATE SET
                        predicted_liquidity_score = EXCLUDED.predicted_liquidity_score,
                        confidence_interval_low = EXCLUDED.confidence_interval_low,
                        confidence_interval_high = EXCLUDED.confidence_interval_high,
                        trend = EXCLUDED.trend,
                        metadata = EXCLUDED.metadata
                    """,
                    forecast.exchange,
                    forecast.symbol,
                    forecast.timestamp,
                    forecast.forecast_hours,
                    forecast.predicted_liquidity_score,
                    forecast.confidence_interval_low,
                    forecast.confidence_interval_high,
                    forecast.trend,
                    json.dumps(forecast.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving forecast: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the liquidity manager."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("LiquidityManager shutdown")


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
    'LiquidityManager',
    'LiquidityLevel',
    'LiquidityStatus',
    'LiquiditySource',
    'LiquidityConfig',
    'LiquidityMetrics',
    'LiquidityRanking',
    'LiquidityAlert',
    'LiquidityForecast',
    'CircuitBreakerOpenError'
]
