# trading/bots/arbitrage_bot/data/depth_manager.py
# Nexus AI Trading System - Arbitrage Bot Depth Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Depth Manager Module

This module provides comprehensive order book depth management for the
arbitrage bot system, including:

- Multi-exchange order book aggregation
- Real-time depth updates via WebSocket
- Depth snapshot management
- Depth delta processing
- Liquidity analysis
- Depth-based price impact calculation
- Depth visualization
- Depth health monitoring
- Depth data persistence
- Multi-level depth management
- Depth validation and cleaning

The depth manager handles all order book data for the arbitrage bot,
enabling accurate liquidity analysis and execution decisions.
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
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.market_data import MarketDepth, MarketPrice
from trading.bots.arbitrage_bot.data.data_cache import DataCache
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class DepthLevel(str, Enum):
    """Depth levels."""
    LEVEL_1 = "level_1"     # Best bid/ask
    LEVEL_2 = "level_2"     # Top 10 levels
    LEVEL_3 = "level_3"     # Top 50 levels
    LEVEL_4 = "level_4"     # Full depth


class DepthStatus(str, Enum):
    """Depth status."""
    FRESH = "fresh"         # Recently updated
    STALE = "stale"         # Needs update
    EXPIRED = "expired"     # Expired
    INVALID = "invalid"     # Invalid data
    ERROR = "error"         # Error state


class DepthAction(str, Enum):
    """Depth actions."""
    SNAPSHOT = "snapshot"   # Full depth snapshot
    UPDATE = "update"       # Depth update
    DELETE = "delete"       # Delete entries
    INSERT = "insert"       # Insert entries


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DepthLevelEntry(BaseModel):
    """Depth level entry."""
    price: Decimal
    volume: Decimal
    order_count: Optional[int] = None
    is_bid: bool  # True for bid, False for ask
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('price', 'volume')
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Price/volume cannot be negative")
        return v


class DepthSnapshot(BaseModel):
    """Depth snapshot."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    bids: List[DepthLevelEntry] = Field(default_factory=list)
    asks: List[DepthLevelEntry] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: DepthStatus = DepthStatus.FRESH
    source: str = "rest"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def best_bid(self) -> Optional[DepthLevelEntry]:
        """Get best bid."""
        if self.bids:
            return self.bids[0]
        return None

    @property
    def best_ask(self) -> Optional[DepthLevelEntry]:
        """Get best ask."""
        if self.asks:
            return self.asks[0]
        return None

    @property
    def spread(self) -> Optional[Decimal]:
        """Get bid-ask spread."""
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return None

    @property
    def mid_price(self) -> Optional[Decimal]:
        """Get mid price."""
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2
        return None

    @property
    def total_bid_volume(self) -> Decimal:
        """Get total bid volume."""
        return sum(entry.volume for entry in self.bids)

    @property
    def total_ask_volume(self) -> Decimal:
        """Get total ask volume."""
        return sum(entry.volume for entry in self.asks)

    @property
    def total_volume(self) -> Decimal:
        """Get total volume."""
        return self.total_bid_volume + self.total_ask_volume


class DepthDelta(BaseModel):
    """Depth delta (change)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: DepthAction
    bids: List[DepthLevelEntry] = Field(default_factory=list)
    asks: List[DepthLevelEntry] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DepthMetrics(BaseModel):
    """Depth metrics."""
    exchange: str
    symbol: str
    depth_level: DepthLevel
    bid_count: int = 0
    ask_count: int = 0
    total_bid_volume: Decimal = Decimal('0')
    total_ask_volume: Decimal = Decimal('0')
    best_bid: Decimal = Decimal('0')
    best_ask: Decimal = Decimal('0')
    spread: Decimal = Decimal('0')
    spread_percent: Decimal = Decimal('0')
    mid_price: Decimal = Decimal('0')
    liquidity_score: Decimal = Decimal('0')
    depth_imbalance: Decimal = Decimal('0')  # (-1 to 1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DepthStatistics(BaseModel):
    """Depth statistics."""
    exchange: str
    symbol: str
    interval: str  # 1m, 5m, 15m, 1h, etc.
    count: int = 0
    avg_bid_count: float = 0.0
    avg_ask_count: float = 0.0
    avg_total_volume: Decimal = Decimal('0')
    avg_spread: Decimal = Decimal('0')
    max_spread: Decimal = Decimal('0')
    min_spread: Decimal = Decimal('0')
    avg_liquidity: Decimal = Decimal('0')
    std_liquidity: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Depth snapshots
CREATE TABLE IF NOT EXISTS depth_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    source VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_depth_snapshots_exchange (exchange),
    INDEX idx_depth_snapshots_symbol (symbol),
    INDEX idx_depth_snapshots_timestamp (timestamp)
);

-- Depth deltas
CREATE TABLE IF NOT EXISTS depth_deltas (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    action VARCHAR(20) NOT NULL,
    bids JSONB DEFAULT '[]',
    asks JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    INDEX idx_depth_deltas_exchange (exchange),
    INDEX idx_depth_deltas_symbol (symbol),
    INDEX idx_depth_deltas_timestamp (timestamp)
);

-- Depth metrics
CREATE TABLE IF NOT EXISTS depth_metrics (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    depth_level VARCHAR(20) NOT NULL,
    bid_count INTEGER NOT NULL,
    ask_count INTEGER NOT NULL,
    total_bid_volume DECIMAL(32, 16) NOT NULL,
    total_ask_volume DECIMAL(32, 16) NOT NULL,
    best_bid DECIMAL(32, 16) NOT NULL,
    best_ask DECIMAL(32, 16) NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    spread_percent DECIMAL(32, 16) NOT NULL,
    mid_price DECIMAL(32, 16) NOT NULL,
    liquidity_score DECIMAL(32, 16) NOT NULL,
    depth_imbalance DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    UNIQUE(exchange, symbol, depth_level, timestamp)
);

-- Depth statistics
CREATE TABLE IF NOT EXISTS depth_statistics (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    count INTEGER NOT NULL,
    avg_bid_count FLOAT NOT NULL,
    avg_ask_count FLOAT NOT NULL,
    avg_total_volume DECIMAL(32, 16) NOT NULL,
    avg_spread DECIMAL(32, 16) NOT NULL,
    max_spread DECIMAL(32, 16) NOT NULL,
    min_spread DECIMAL(32, 16) NOT NULL,
    avg_liquidity DECIMAL(32, 16) NOT NULL,
    std_liquidity DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    UNIQUE(exchange, symbol, interval, timestamp)
);
"""


# =============================================================================
# DEPTH MANAGER CLASS
# =============================================================================

class DepthManager:
    """
    Advanced depth manager for arbitrage bot.
    
    Features:
    - Multi-exchange order book aggregation
    - Real-time depth updates via WebSocket
    - Depth snapshot management
    - Depth delta processing
    - Liquidity analysis
    - Depth-based price impact calculation
    - Depth visualization
    - Depth health monitoring
    - Depth data persistence
    - Multi-level depth management
    - Depth validation and cleaning
    """
    
    def __init__(
        self,
        data_cache: Optional[DataCache] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_cache = data_cache
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Depth cache
        self._snapshots: Dict[str, DepthSnapshot] = {}  # exchange:symbol -> snapshot
        self._deltas: Dict[str, List[DepthDelta]] = {}  # exchange:symbol -> deltas
        
        # Metrics
        self._metrics: Dict[str, DepthMetrics] = {}
        
        # Statistics
        self._statistics: Dict[str, DepthStatistics] = {}
        
        # Circuit breakers
        self._depth_cb = CircuitBreaker(
            name="depth_manager",
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
        
        logger.info("DepthManager initialized")
    
    async def initialize(self):
        """Initialize the depth manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load snapshots
        if self.pool:
            await self._load_snapshots()
        
        self._running = True
        self._initialized = True
        
        # Start cleanup loop
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("DepthManager initialized")
    
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
    # DEPTH OPERATIONS
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def update_depth(
        self,
        exchange: str,
        symbol: str,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]],
        source: str = "websocket",
        status: DepthStatus = DepthStatus.FRESH
    ) -> DepthSnapshot:
        """
        Update order book depth.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            bids: List of (price, volume) for bids
            asks: List of (price, volume) for asks
            source: Data source
            status: Depth status
            
        Returns:
            DepthSnapshot
        """
        if self._depth_cb.is_open():
            raise CircuitBreakerOpenError("Depth manager circuit breaker is open")
        
        try:
            # Validate and sort
            valid_bids = self._validate_depth_entries(bids, is_bid=True)
            valid_asks = self._validate_depth_entries(asks, is_bid=False)
            
            # Sort bids descending (highest price first)
            valid_bids.sort(key=lambda x: x.price, reverse=True)
            # Sort asks ascending (lowest price first)
            valid_asks.sort(key=lambda x: x.price)
            
            # Create snapshot
            snapshot = DepthSnapshot(
                exchange=exchange,
                symbol=symbol,
                bids=valid_bids,
                asks=valid_asks,
                timestamp=datetime.utcnow(),
                status=status,
                source=source
            )
            
            # Update cache
            key = f"{exchange}:{symbol}"
            async with self._lock:
                self._snapshots[key] = snapshot
            
            # Cache in Redis
            if self.redis:
                await self._cache_snapshot(snapshot)
            
            # Save to database
            if self.pool:
                await self._save_snapshot(snapshot)
            
            # Calculate and save metrics
            metrics = await self._calculate_metrics(snapshot)
            if self.pool:
                await self._save_metrics(metrics)
            
            # Record success
            self._depth_cb.record_success()
            
            # Trigger handlers
            await self._trigger_handlers("depth_update", snapshot)
            
            return snapshot
            
        except Exception as e:
            self._depth_cb.record_failure()
            logger.error(f"Depth update error: {e}")
            
            # Return existing snapshot if available
            key = f"{exchange}:{symbol}"
            if key in self._snapshots:
                return self._snapshots[key]
            
            raise
    
    async def apply_delta(
        self,
        exchange: str,
        symbol: str,
        action: DepthAction,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]]
    ) -> DepthSnapshot:
        """
        Apply a depth delta.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            action: Delta action
            bids: Bid entries
            asks: Ask entries
            
        Returns:
            Updated DepthSnapshot
        """
        key = f"{exchange}:{symbol}"
        
        if key not in self._snapshots:
            # No existing snapshot, create one
            return await self.update_depth(exchange, symbol, bids, asks, source="delta")
        
        snapshot = self._snapshots[key]
        updated_bids = list(snapshot.bids)
        updated_asks = list(snapshot.asks)
        
        if action == DepthAction.SNAPSHOT:
            # Full replacement
            return await self.update_depth(exchange, symbol, bids, asks, source="delta")
            
        elif action == DepthAction.INSERT:
            # Insert new levels
            for bid in bids:
                updated_bids.append(bid)
            for ask in asks:
                updated_asks.append(ask)
                
        elif action == DepthAction.UPDATE:
            # Update existing levels
            for bid in bids:
                updated_bids = [b if b.price != bid.price else bid for b in updated_bids]
            for ask in asks:
                updated_asks = [a if a.price != ask.price else ask for a in updated_asks]
                
        elif action == DepthAction.DELETE:
            # Delete levels
            for bid in bids:
                updated_bids = [b for b in updated_bids if b.price != bid.price]
            for ask in asks:
                updated_asks = [a for a in updated_asks if a.price != ask.price]
        
        # Create delta record
        delta = DepthDelta(
            exchange=exchange,
            symbol=symbol,
            timestamp=datetime.utcnow(),
            action=action,
            bids=[DepthLevelEntry(price=p, volume=v, is_bid=True) for p, v in bids],
            asks=[DepthLevelEntry(price=p, volume=v, is_bid=False) for p, v in asks]
        )
        
        # Store delta
        if key not in self._deltas:
            self._deltas[key] = []
        self._deltas[key].append(delta)
        
        # Trim deltas
        if len(self._deltas[key]) > 1000:
            self._deltas[key] = self._deltas[key][-500:]
        
        # Save delta
        if self.pool:
            await self._save_delta(delta)
        
        # Update snapshot
        return await self.update_depth(
            exchange, symbol,
            [(b.price, b.volume) for b in updated_bids],
            [(a.price, a.volume) for a in updated_asks],
            source="delta"
        )
    
    # =========================================================================
    # DEPTH QUERYING
    # =========================================================================
    
    async def get_depth(
        self,
        exchange: str,
        symbol: str,
        level: DepthLevel = DepthLevel.LEVEL_2,
        refresh: bool = False
    ) -> Optional[DepthSnapshot]:
        """
        Get order book depth.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            level: Depth level
            refresh: Force refresh
            
        Returns:
            DepthSnapshot or None
        """
        key = f"{exchange}:{symbol}"
        
        if not refresh and key in self._snapshots:
            snapshot = self._snapshots[key]
            
            # Check if still fresh
            age = (datetime.utcnow() - snapshot.timestamp).total_seconds()
            if age < 5:  # 5 seconds freshness
                return self._get_depth_level(snapshot, level)
        
        # Try from cache
        if self.data_cache and not refresh:
            cached = await self.data_cache.get(f"depth:{key}")
            if cached:
                return cached
        
        return None
    
    def _get_depth_level(
        self,
        snapshot: DepthSnapshot,
        level: DepthLevel
    ) -> DepthSnapshot:
        """
        Get depth at specific level.
        
        Args:
            snapshot: Full depth snapshot
            level: Depth level
            
        Returns:
            DepthSnapshot at requested level
        """
        if level == DepthLevel.LEVEL_1:
            return DepthSnapshot(
                exchange=snapshot.exchange,
                symbol=snapshot.symbol,
                bids=snapshot.bids[:1] if snapshot.bids else [],
                asks=snapshot.asks[:1] if snapshot.asks else [],
                timestamp=snapshot.timestamp,
                status=snapshot.status,
                source=snapshot.source
            )
        elif level == DepthLevel.LEVEL_2:
            return DepthSnapshot(
                exchange=snapshot.exchange,
                symbol=snapshot.symbol,
                bids=snapshot.bids[:10] if snapshot.bids else [],
                asks=snapshot.asks[:10] if snapshot.asks else [],
                timestamp=snapshot.timestamp,
                status=snapshot.status,
                source=snapshot.source
            )
        elif level == DepthLevel.LEVEL_3:
            return DepthSnapshot(
                exchange=snapshot.exchange,
                symbol=snapshot.symbol,
                bids=snapshot.bids[:50] if snapshot.bids else [],
                asks=snapshot.asks[:50] if snapshot.asks else [],
                timestamp=snapshot.timestamp,
                status=snapshot.status,
                source=snapshot.source
            )
        else:
            return snapshot
    
    async def get_depth_metrics(
        self,
        exchange: str,
        symbol: str
    ) -> Optional[DepthMetrics]:
        """
        Get depth metrics.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            
        Returns:
            DepthMetrics or None
        """
        key = f"{exchange}:{symbol}"
        
        if key in self._metrics:
            return self._metrics[key]
        
        # Calculate from snapshot
        if key in self._snapshots:
            snapshot = self._snapshots[key]
            metrics = await self._calculate_metrics(snapshot)
            self._metrics[key] = metrics
            return metrics
        
        return None
    
    # =========================================================================
    # LIQUIDITY ANALYSIS
    # =========================================================================
    
    async def calculate_liquidity_score(
        self,
        exchange: str,
        symbol: str,
        depth_level: int = 10
    ) -> Decimal:
        """
        Calculate liquidity score.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            depth_level: Depth level
            
        Returns:
            Liquidity score (0-100)
        """
        snapshot = await self.get_depth(exchange, symbol)
        
        if not snapshot:
            return Decimal('0')
        
        # Calculate total volume at depth
        bid_volume = sum(entry.volume for entry in snapshot.bids[:depth_level])
        ask_volume = sum(entry.volume for entry in snapshot.asks[:depth_level])
        total_volume = bid_volume + ask_volume
        
        if total_volume == 0:
            return Decimal('0')
        
        # Calculate spread
        spread = snapshot.spread or Decimal('0')
        
        # Calculate liquidity score
        # Higher volume and lower spread = higher liquidity
        volume_score = min(total_volume / Decimal('1000'), Decimal('1')) * 50
        spread_score = max(Decimal('0'), Decimal('1') - spread * 100) * 50
        
        return volume_score + spread_score
    
    async def calculate_market_impact(
        self,
        exchange: str,
        symbol: str,
        order_size: Decimal,
        side: str = "buy"
    ) -> Decimal:
        """
        Calculate market impact of an order.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            order_size: Order size
            side: 'buy' or 'sell'
            
        Returns:
            Market impact percentage
        """
        snapshot = await self.get_depth(exchange, symbol)
        
        if not snapshot:
            return Decimal('1')  # Default 1% impact
        
        # Calculate impact using depth
        cumulative_volume = Decimal('0')
        weighted_price = Decimal('0')
        
        if side == "buy":
            levels = snapshot.asks
        else:
            levels = snapshot.bids
        
        for entry in levels:
            if cumulative_volume >= order_size:
                break
            
            remaining = min(order_size - cumulative_volume, entry.volume)
            weighted_price += entry.price * remaining
            cumulative_volume += remaining
        
        if cumulative_volume == 0:
            return Decimal('1')
        
        avg_price = weighted_price / cumulative_volume
        
        # Compare to mid price
        mid_price = snapshot.mid_price or avg_price
        
        if mid_price == 0:
            return Decimal('1')
        
        impact = abs(avg_price - mid_price) / mid_price * 100
        
        return impact.quantize(Decimal('0.01'))
    
    # =========================================================================
    # DEPTH VALIDATION
    # =========================================================================
    
    def _validate_depth_entries(
        self,
        entries: List[Tuple[Decimal, Decimal]],
        is_bid: bool
    ) -> List[DepthLevelEntry]:
        """
        Validate and clean depth entries.
        
        Args:
            entries: List of (price, volume) tuples
            is_bid: True for bid, False for ask
            
        Returns:
            List of DepthLevelEntry
        """
        validated = []
        
        for price, volume in entries:
            if price <= 0 or volume <= 0:
                continue
            
            # Round to reasonable precision
            price_rounded = price.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
            volume_rounded = volume.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            
            entry = DepthLevelEntry(
                price=price_rounded,
                volume=volume_rounded,
                is_bid=is_bid
            )
            validated.append(entry)
        
        return validated
    
    # =========================================================================
    # METRICS CALCULATION
    # =========================================================================
    
    async def _calculate_metrics(
        self,
        snapshot: DepthSnapshot
    ) -> DepthMetrics:
        """
        Calculate depth metrics.
        
        Args:
            snapshot: Depth snapshot
            
        Returns:
            DepthMetrics
        """
        bid_count = len(snapshot.bids)
        ask_count = len(snapshot.asks)
        total_bid_volume = snapshot.total_bid_volume
        total_ask_volume = snapshot.total_ask_volume
        
        best_bid = snapshot.best_bid.price if snapshot.best_bid else Decimal('0')
        best_ask = snapshot.best_ask.price if snapshot.best_ask else Decimal('0')
        spread = snapshot.spread or Decimal('0')
        mid_price = snapshot.mid_price or Decimal('0')
        
        # Calculate spread percentage
        spread_percent = (spread / mid_price * 100) if mid_price > 0 else Decimal('0')
        
        # Calculate depth imbalance
        total_volume = total_bid_volume + total_ask_volume
        depth_imbalance = (
            (total_bid_volume - total_ask_volume) / total_volume
            if total_volume > 0 else Decimal('0')
        )
        
        # Calculate liquidity score
        liquidity_score = await self.calculate_liquidity_score(
            snapshot.exchange,
            snapshot.symbol
        )
        
        return DepthMetrics(
            exchange=snapshot.exchange,
            symbol=snapshot.symbol,
            depth_level=DepthLevel.LEVEL_4,
            bid_count=bid_count,
            ask_count=ask_count,
            total_bid_volume=total_bid_volume.quantize(Decimal('0.0001')),
            total_ask_volume=total_ask_volume.quantize(Decimal('0.0001')),
            best_bid=best_bid.quantize(Decimal('0.00000001')),
            best_ask=best_ask.quantize(Decimal('0.00000001')),
            spread=spread.quantize(Decimal('0.00000001')),
            spread_percent=spread_percent.quantize(Decimal('0.0001')),
            mid_price=mid_price.quantize(Decimal('0.00000001')),
            liquidity_score=liquidity_score.quantize(Decimal('0.01')),
            depth_imbalance=depth_imbalance.quantize(Decimal('0.0001')),
            timestamp=snapshot.timestamp
        )
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_depth_update(self, handler: Callable):
        """Register a depth update handler."""
        key = "depth_update"
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
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_snapshot(self, snapshot: DepthSnapshot):
        """Cache depth snapshot in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"depth:{snapshot.exchange}:{snapshot.symbol}"
            await self.redis.setex(
                key,
                30,  # 30 second TTL
                json.dumps(snapshot.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Cache snapshot error: {e}")
    
    # =========================================================================
    # CLEANUP LOOP
    # =========================================================================
    
    async def _cleanup_loop(self):
        """Periodic cleanup of old depth data."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Every hour
                
                # Clean old snapshots
                # Keep last 24 hours of data
                cutoff = datetime.utcnow() - timedelta(hours=24)
                
                if self.pool:
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            "DELETE FROM depth_snapshots WHERE timestamp < $1",
                            cutoff
                        )
                        await conn.execute(
                            "DELETE FROM depth_deltas WHERE timestamp < $1",
                            cutoff
                        )
                
                logger.info("Depth cleanup completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(3600)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_snapshots(self):
        """Load snapshots from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM depth_snapshots 
                    WHERE timestamp > NOW() - INTERVAL '1 hour'
                    ORDER BY timestamp DESC
                    LIMIT 1000
                    """
                )
                
                for row in rows:
                    snapshot = DepthSnapshot(
                        id=row['id'],
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        bids=[DepthLevelEntry(**b) for b in row['bids']],
                        asks=[DepthLevelEntry(**a) for a in row['asks']],
                        timestamp=row['timestamp'],
                        status=DepthStatus(row['status']),
                        source=row['source'],
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{snapshot.exchange}:{snapshot.symbol}"
                    self._snapshots[key] = snapshot
                
                logger.info(f"Loaded {len(self._snapshots)} depth snapshots")
                
        except Exception as e:
            logger.error(f"Error loading snapshots: {e}")
    
    async def _save_snapshot(self, snapshot: DepthSnapshot):
        """Save depth snapshot to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO depth_snapshots (
                        id, exchange, symbol, bids, asks,
                        timestamp, status, source, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    snapshot.id,
                    snapshot.exchange,
                    snapshot.symbol,
                    json.dumps([e.dict() for e in snapshot.bids], default=str),
                    json.dumps([e.dict() for e in snapshot.asks], default=str),
                    snapshot.timestamp,
                    snapshot.status.value,
                    snapshot.source,
                    json.dumps(snapshot.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
    
    async def _save_delta(self, delta: DepthDelta):
        """Save depth delta to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO depth_deltas (
                        id, exchange, symbol, timestamp,
                        action, bids, asks, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    delta.id,
                    delta.exchange,
                    delta.symbol,
                    delta.timestamp,
                    delta.action.value,
                    json.dumps([e.dict() for e in delta.bids], default=str),
                    json.dumps([e.dict() for e in delta.asks], default=str),
                    json.dumps(delta.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving delta: {e}")
    
    async def _save_metrics(self, metrics: DepthMetrics):
        """Save depth metrics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO depth_metrics (
                        exchange, symbol, depth_level,
                        bid_count, ask_count,
                        total_bid_volume, total_ask_volume,
                        best_bid, best_ask, spread,
                        spread_percent, mid_price,
                        liquidity_score, depth_imbalance,
                        timestamp
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7,
                              $8, $9, $10, $11, $12, $13, $14, $15)
                    ON CONFLICT (exchange, symbol, depth_level, timestamp) DO UPDATE SET
                        bid_count = EXCLUDED.bid_count,
                        ask_count = EXCLUDED.ask_count,
                        total_bid_volume = EXCLUDED.total_bid_volume,
                        total_ask_volume = EXCLUDED.total_ask_volume,
                        best_bid = EXCLUDED.best_bid,
                        best_ask = EXCLUDED.best_ask,
                        spread = EXCLUDED.spread,
                        spread_percent = EXCLUDED.spread_percent,
                        mid_price = EXCLUDED.mid_price,
                        liquidity_score = EXCLUDED.liquidity_score,
                        depth_imbalance = EXCLUDED.depth_imbalance
                    """,
                    metrics.exchange,
                    metrics.symbol,
                    metrics.depth_level.value,
                    metrics.bid_count,
                    metrics.ask_count,
                    metrics.total_bid_volume,
                    metrics.total_ask_volume,
                    metrics.best_bid,
                    metrics.best_ask,
                    metrics.spread,
                    metrics.spread_percent,
                    metrics.mid_price,
                    metrics.liquidity_score,
                    metrics.depth_imbalance,
                    metrics.timestamp
                )
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the depth manager."""
        self._running = False
        logger.info("DepthManager shutdown")


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
    'DepthManager',
    'DepthLevel',
    'DepthStatus',
    'DepthAction',
    'DepthLevelEntry',
    'DepthSnapshot',
    'DepthDelta',
    'DepthMetrics',
    'DepthStatistics',
    'CircuitBreakerOpenError'
]
