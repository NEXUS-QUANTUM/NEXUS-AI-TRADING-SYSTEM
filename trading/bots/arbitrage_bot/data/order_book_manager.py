# trading/bots/arbitrage_bot/data/order_book_manager.py
# Nexus AI Trading System - Arbitrage Bot Order Book Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Order Book Manager Module

This module provides comprehensive order book management for the arbitrage
bot system, including:

- Multi-exchange order book synchronization
- Real-time order book updates
- Order book reconstruction from deltas
- Order book validation and verification
- Order book analytics
- Order book snapshot management
- Order book persistence
- Order book depth aggregation
- Order book imbalance detection
- Order book liquidity analysis
- Order book visualization
- Order book health monitoring

The order book manager handles all order book data for the arbitrage bot,
enabling accurate market analysis and execution decisions.
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
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager
from trading.bots.arbitrage_bot.data.depth_manager import DepthManager, DepthSnapshot, DepthLevel, DepthLevelEntry
from trading.bots.arbitrage_bot.data.liquidity_manager import LiquidityManager
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OrderBookStatus(str, Enum):
    """Order book status."""
    SYNCED = "synced"           # Fully synced
    PARTIAL = "partial"         # Partially synced
    STALE = "stale"             # Needs update
    UNSYNCED = "unsynced"       # Not synced
    ERROR = "error"             # Error state


class OrderBookAction(str, Enum):
    """Order book actions."""
    SNAPSHOT = "snapshot"       # Full snapshot
    UPDATE = "update"           # Update entry
    DELETE = "delete"           # Delete entry
    INSERT = "insert"           # Insert entry
    CLEAR = "clear"             # Clear book


class OrderBookValidation(str, Enum):
    """Order book validation."""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"
    CHECKSUM_ERROR = "checksum_error"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderBookEntry(BaseModel):
    """Order book entry."""
    price: Decimal
    volume: Decimal
    order_count: Optional[int] = None
    is_bid: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('price', 'volume')
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Price/volume cannot be negative")
        return v


class OrderBook(BaseModel):
    """Order book."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    bids: List[OrderBookEntry] = Field(default_factory=list)
    asks: List[OrderBookEntry] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: OrderBookStatus = OrderBookStatus.SYNCED
    sequence_id: Optional[int] = None
    checksum: Optional[str] = None
    depth_level: DepthLevel = DepthLevel.LEVEL_4
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def best_bid(self) -> Optional[OrderBookEntry]:
        """Get best bid."""
        if self.bids:
            return self.bids[0]
        return None

    @property
    def best_ask(self) -> Optional[OrderBookEntry]:
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


class OrderBookDelta(BaseModel):
    """Order book delta."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    sequence_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: OrderBookAction
    bids: List[OrderBookEntry] = Field(default_factory=list)
    asks: List[OrderBookEntry] = Field(default_factory=list)
    previous_sequence_id: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderBookSnapshot(BaseModel):
    """Order book snapshot."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bids: List[OrderBookEntry] = Field(default_factory=list)
    asks: List[OrderBookEntry] = Field(default_factory=list)
    sequence_id: int
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderBookStatistics(BaseModel):
    """Order book statistics."""
    exchange: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_bid_volume: Decimal
    total_ask_volume: Decimal
    total_volume: Decimal
    bid_count: int
    ask_count: int
    best_bid: Decimal
    best_ask: Decimal
    spread: Decimal
    spread_percent: Decimal
    mid_price: Decimal
    bid_ask_imbalance: Decimal  # (-1 to 1)
    depth_imbalance_1pct: Decimal  # Imbalance within 1% of mid price
    depth_imbalance_5pct: Decimal  # Imbalance within 5% of mid price
    avg_bid_depth: Decimal
    avg_ask_depth: Decimal
    order_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Order books
CREATE TABLE IF NOT EXISTS order_books (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL,
    sequence_id BIGINT,
    checksum VARCHAR(64),
    depth_level VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(exchange, symbol, depth_level)
);

-- Order book deltas
CREATE TABLE IF NOT EXISTS order_book_deltas (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    sequence_id BIGINT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    action VARCHAR(20) NOT NULL,
    bids JSONB DEFAULT '[]',
    asks JSONB DEFAULT '[]',
    previous_sequence_id BIGINT,
    metadata JSONB DEFAULT '{}',
    INDEX idx_order_book_deltas_exchange (exchange),
    INDEX idx_order_book_deltas_symbol (symbol),
    INDEX idx_order_book_deltas_timestamp (timestamp)
);

-- Order book snapshots
CREATE TABLE IF NOT EXISTS order_book_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    bids JSONB NOT NULL,
    asks JSONB NOT NULL,
    sequence_id BIGINT NOT NULL,
    checksum VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    INDEX idx_order_book_snapshots_exchange (exchange),
    INDEX idx_order_book_snapshots_symbol (symbol),
    INDEX idx_order_book_snapshots_timestamp (timestamp)
);

-- Order book statistics
CREATE TABLE IF NOT EXISTS order_book_statistics (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    total_bid_volume DECIMAL(32, 16) NOT NULL,
    total_ask_volume DECIMAL(32, 16) NOT NULL,
    total_volume DECIMAL(32, 16) NOT NULL,
    bid_count INTEGER NOT NULL,
    ask_count INTEGER NOT NULL,
    best_bid DECIMAL(32, 16) NOT NULL,
    best_ask DECIMAL(32, 16) NOT NULL,
    spread DECIMAL(32, 16) NOT NULL,
    spread_percent DECIMAL(32, 16) NOT NULL,
    mid_price DECIMAL(32, 16) NOT NULL,
    bid_ask_imbalance DECIMAL(32, 16) NOT NULL,
    depth_imbalance_1pct DECIMAL(32, 16) NOT NULL,
    depth_imbalance_5pct DECIMAL(32, 16) NOT NULL,
    avg_bid_depth DECIMAL(32, 16) NOT NULL,
    avg_ask_depth DECIMAL(32, 16) NOT NULL,
    order_count INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    UNIQUE(exchange, symbol, timestamp)
);
"""


# =============================================================================
# ORDER BOOK MANAGER CLASS
# =============================================================================

class OrderBookManager:
    """
    Advanced order book manager for arbitrage bot.
    
    Features:
    - Multi-exchange order book synchronization
    - Real-time order book updates
    - Order book reconstruction from deltas
    - Order book validation and verification
    - Order book analytics
    - Order book snapshot management
    - Order book persistence
    - Order book depth aggregation
    - Order book imbalance detection
    - Order book liquidity analysis
    - Order book visualization
    - Order book health monitoring
    """
    
    def __init__(
        self,
        depth_manager: DepthManager,
        liquidity_manager: LiquidityManager,
        market_data: MarketDataManager,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.depth_manager = depth_manager
        self.liquidity_manager = liquidity_manager
        self.market_data = market_data
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Order book cache
        self._books: Dict[str, OrderBook] = {}  # exchange:symbol -> book
        
        # Delta cache
        self._deltas: Dict[str, List[OrderBookDelta]] = {}  # exchange:symbol -> deltas
        
        # Snapshots
        self._snapshots: Dict[str, OrderBookSnapshot] = {}
        
        # Statistics
        self._statistics: Dict[str, OrderBookStatistics] = {}
        
        # Circuit breakers
        self._book_cb = CircuitBreaker(
            name="order_book_manager",
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
        
        logger.info("OrderBookManager initialized")
    
    async def initialize(self):
        """Initialize the order book manager."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load books
        if self.pool:
            await self._load_books()
        
        # Load snapshots
        if self.pool:
            await self._load_snapshots()
        
        # Load statistics
        if self.pool:
            await self._load_statistics()
        
        # Start update loop
        self._running = True
        self._update_task = asyncio.create_task(self._update_loop())
        
        self._initialized = True
        logger.info("OrderBookManager initialized")
    
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
    # ORDER BOOK OPERATIONS
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def update_book(
        self,
        exchange: str,
        symbol: str,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]],
        sequence_id: Optional[int] = None,
        source: str = "websocket"
    ) -> OrderBook:
        """
        Update order book with new data.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            bids: List of (price, volume) for bids
            asks: List of (price, volume) for asks
            sequence_id: Sequence ID for ordering
            source: Data source
            
        Returns:
            Updated OrderBook
        """
        if self._book_cb.is_open():
            raise CircuitBreakerOpenError("Order book circuit breaker is open")
        
        key = f"{exchange}:{symbol}"
        
        try:
            # Validate and sort entries
            valid_bids = self._validate_entries(bids, is_bid=True)
            valid_asks = self._validate_entries(asks, is_bid=False)
            
            # Sort bids descending, asks ascending
            valid_bids.sort(key=lambda x: x.price, reverse=True)
            valid_asks.sort(key=lambda x: x.price)
            
            # Get existing book
            existing = self._books.get(key)
            
            if existing:
                # Apply updates
                updated_bids = self._apply_updates(existing.bids, valid_bids, is_bid=True)
                updated_asks = self._apply_updates(existing.asks, valid_asks, is_bid=False)
            else:
                updated_bids = valid_bids
                updated_asks = valid_asks
            
            # Create book
            book = OrderBook(
                exchange=exchange,
                symbol=symbol,
                bids=updated_bids,
                asks=updated_asks,
                timestamp=datetime.utcnow(),
                status=OrderBookStatus.SYNCED,
                sequence_id=sequence_id,
                depth_level=DepthLevel.LEVEL_4,
                source=source
            )
            
            # Validate book
            if not await self.validate_book(book):
                book.status = OrderBookStatus.PARTIAL
            
            # Update cache
            async with self._lock:
                self._books[key] = book
            
            # Save to database
            if self.pool:
                await self._save_book(book)
            
            # Calculate statistics
            stats = await self._calculate_statistics(book)
            if self.pool:
                await self._save_statistics(stats)
            
            # Record success
            self._book_cb.record_success()
            
            # Trigger handlers
            await self._trigger_handlers("book_update", book)
            
            return book
            
        except Exception as e:
            self._book_cb.record_failure()
            logger.error(f"Order book update error: {e}")
            
            # Return existing book if available
            if key in self._books:
                return self._books[key]
            
            raise
    
    def _validate_entries(
        self,
        entries: List[Tuple[Decimal, Decimal]],
        is_bid: bool
    ) -> List[OrderBookEntry]:
        """Validate and convert entries."""
        validated = []
        
        for price, volume in entries:
            if price <= 0 or volume <= 0:
                continue
            
            entry = OrderBookEntry(
                price=price.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
                volume=volume.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
                is_bid=is_bid
            )
            validated.append(entry)
        
        return validated
    
    def _apply_updates(
        self,
        existing: List[OrderBookEntry],
        updates: List[OrderBookEntry],
        is_bid: bool
    ) -> List[OrderBookEntry]:
        """Apply updates to existing entries."""
        if not updates:
            return existing
        
        # Create price map of existing entries
        price_map = {e.price: e for e in existing}
        
        # Apply updates
        for update in updates:
            if update.volume <= 0:
                # Delete entry
                price_map.pop(update.price, None)
            else:
                # Update or insert
                price_map[update.price] = update
        
        # Convert back to list and sort
        result = list(price_map.values())
        
        if is_bid:
            result.sort(key=lambda x: x.price, reverse=True)
        else:
            result.sort(key=lambda x: x.price)
        
        return result
    
    @async_retry(max_attempts=3, base_delay=0.5, max_delay=5.0)
    async def get_book(
        self,
        exchange: str,
        symbol: str,
        depth: DepthLevel = DepthLevel.LEVEL_4,
        refresh: bool = False
    ) -> Optional[OrderBook]:
        """
        Get order book.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            depth: Depth level
            refresh: Force refresh
            
        Returns:
            OrderBook or None
        """
        key = f"{exchange}:{symbol}"
        
        if not refresh and key in self._books:
            book = self._books[key]
            age = (datetime.utcnow() - book.timestamp).total_seconds()
            if age < 5:  # 5 seconds freshness
                return self._filter_depth(book, depth)
        
        # Try from depth manager
        depth_snapshot = await self.depth_manager.get_depth(exchange, symbol, depth, refresh)
        
        if depth_snapshot:
            book = OrderBook(
                exchange=exchange,
                symbol=symbol,
                bids=[OrderBookEntry(
                    price=e.price,
                    volume=e.volume,
                    is_bid=True,
                    timestamp=e.timestamp
                ) for e in depth_snapshot.bids],
                asks=[OrderBookEntry(
                    price=e.price,
                    volume=e.volume,
                    is_bid=False,
                    timestamp=e.timestamp
                ) for e in depth_snapshot.asks],
                timestamp=depth_snapshot.timestamp,
                status=OrderBookStatus.SYNCED if depth_snapshot.status == DepthStatus.FRESH else OrderBookStatus.STALE,
                depth_level=depth
            )
            
            async with self._lock:
                self._books[key] = book
            
            return book
        
        return None
    
    def _filter_depth(self, book: OrderBook, depth: DepthLevel) -> OrderBook:
        """Filter book to specified depth."""
        if depth == DepthLevel.LEVEL_1:
            return OrderBook(
                exchange=book.exchange,
                symbol=book.symbol,
                bids=book.bids[:1] if book.bids else [],
                asks=book.asks[:1] if book.asks else [],
                timestamp=book.timestamp,
                status=book.status,
                depth_level=depth
            )
        elif depth == DepthLevel.LEVEL_2:
            return OrderBook(
                exchange=book.exchange,
                symbol=book.symbol,
                bids=book.bids[:10] if book.bids else [],
                asks=book.asks[:10] if book.asks else [],
                timestamp=book.timestamp,
                status=book.status,
                depth_level=depth
            )
        elif depth == DepthLevel.LEVEL_3:
            return OrderBook(
                exchange=book.exchange,
                symbol=book.symbol,
                bids=book.bids[:50] if book.bids else [],
                asks=book.asks[:50] if book.asks else [],
                timestamp=book.timestamp,
                status=book.status,
                depth_level=depth
            )
        else:
            return book
    
    # =========================================================================
    # DELTA PROCESSING
    # =========================================================================
    
    async def apply_delta(
        self,
        exchange: str,
        symbol: str,
        action: OrderBookAction,
        bids: List[Tuple[Decimal, Decimal]],
        asks: List[Tuple[Decimal, Decimal]],
        sequence_id: int,
        previous_sequence_id: Optional[int] = None
    ) -> OrderBook:
        """
        Apply a delta to the order book.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            action: Delta action
            bids: Bid entries
            asks: Ask entries
            sequence_id: Sequence ID
            previous_sequence_id: Previous sequence ID
            
        Returns:
            Updated OrderBook
        """
        key = f"{exchange}:{symbol}"
        
        # Create delta
        delta = OrderBookDelta(
            exchange=exchange,
            symbol=symbol,
            sequence_id=sequence_id,
            action=action,
            bids=self._validate_entries(bids, is_bid=True),
            asks=self._validate_entries(asks, is_bid=False),
            previous_sequence_id=previous_sequence_id,
            timestamp=datetime.utcnow()
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
        
        # Apply to book
        if action == OrderBookAction.SNAPSHOT:
            return await self.update_book(
                exchange, symbol,
                [(b.price, b.volume) for b in delta.bids],
                [(a.price, a.volume) for a in delta.asks],
                sequence_id,
                source="delta"
            )
        else:
            # Get current book
            book = await self.get_book(exchange, symbol)
            
            if not book:
                # No book, create from delta
                return await self.update_book(
                    exchange, symbol,
                    [(b.price, b.volume) for b in delta.bids],
                    [(a.price, a.volume) for a in delta.asks],
                    sequence_id,
                    source="delta"
                )
            
            # Apply delta to book
            if action == OrderBookAction.UPDATE:
                updated_bids = self._apply_updates(book.bids, delta.bids, True)
                updated_asks = self._apply_updates(book.asks, delta.asks, False)
            elif action == OrderBookAction.INSERT:
                updated_bids = book.bids + delta.bids
                updated_asks = book.asks + delta.asks
                updated_bids.sort(key=lambda x: x.price, reverse=True)
                updated_asks.sort(key=lambda x: x.price)
            elif action == OrderBookAction.DELETE:
                bid_prices = {b.price for b in delta.bids}
                ask_prices = {a.price for a in delta.asks}
                updated_bids = [b for b in book.bids if b.price not in bid_prices]
                updated_asks = [a for a in book.asks if a.price not in ask_prices]
            elif action == OrderBookAction.CLEAR:
                updated_bids = []
                updated_asks = []
            else:
                updated_bids = book.bids
                updated_asks = book.asks
            
            # Create updated book
            updated_book = OrderBook(
                exchange=exchange,
                symbol=symbol,
                bids=updated_bids,
                asks=updated_asks,
                timestamp=datetime.utcnow(),
                status=OrderBookStatus.SYNCED,
                sequence_id=sequence_id,
                depth_level=DepthLevel.LEVEL_4
            )
            
            # Update cache
            async with self._lock:
                self._books[key] = updated_book
            
            # Save to database
            if self.pool:
                await self._save_book(updated_book)
            
            # Trigger handlers
            await self._trigger_handlers("book_update", updated_book)
            
            return updated_book
    
    # =========================================================================
    # VALIDATION
    # =========================================================================
    
    async def validate_book(self, book: OrderBook) -> bool:
        """
        Validate order book.
        
        Args:
            book: Order book to validate
            
        Returns:
            True if valid
        """
        # Check if bids are sorted correctly
        if len(book.bids) > 1:
            for i in range(len(book.bids) - 1):
                if book.bids[i].price < book.bids[i + 1].price:
                    return False
        
        # Check if asks are sorted correctly
        if len(book.asks) > 1:
            for i in range(len(book.asks) - 1):
                if book.asks[i].price > book.asks[i + 1].price:
                    return False
        
        # Check for negative prices/volumes
        for entry in book.bids + book.asks:
            if entry.price <= 0 or entry.volume < 0:
                return False
        
        # Check for crossing
        if book.best_bid and book.best_ask:
            if book.best_bid.price >= book.best_ask.price:
                return False
        
        return True
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def _calculate_statistics(
        self,
        book: OrderBook
    ) -> OrderBookStatistics:
        """
        Calculate order book statistics.
        
        Args:
            book: Order book
            
        Returns:
            OrderBookStatistics
        """
        total_bid_volume = book.total_bid_volume
        total_ask_volume = book.total_ask_volume
        total_volume = total_bid_volume + total_ask_volume
        
        best_bid = book.best_bid.price if book.best_bid else Decimal('0')
        best_ask = book.best_ask.price if book.best_ask else Decimal('0')
        spread = book.spread or Decimal('0')
        mid_price = book.mid_price or Decimal('0')
        
        spread_percent = (spread / mid_price * 100) if mid_price > 0 else Decimal('0')
        
        bid_ask_imbalance = (
            (total_bid_volume - total_ask_volume) / total_volume
            if total_volume > 0 else Decimal('0')
        )
        
        # Calculate depth imbalance within 1% and 5% of mid price
        depth_imbalance_1pct = self._calculate_depth_imbalance(book, 0.01)
        depth_imbalance_5pct = self._calculate_depth_imbalance(book, 0.05)
        
        # Calculate average depths
        avg_bid_depth = sum(e.volume for e in book.bids) / len(book.bids) if book.bids else Decimal('0')
        avg_ask_depth = sum(e.volume for e in book.asks) / len(book.asks) if book.asks else Decimal('0')
        
        return OrderBookStatistics(
            exchange=book.exchange,
            symbol=book.symbol,
            total_bid_volume=total_bid_volume.quantize(Decimal('0.0001')),
            total_ask_volume=total_ask_volume.quantize(Decimal('0.0001')),
            total_volume=total_volume.quantize(Decimal('0.0001')),
            bid_count=len(book.bids),
            ask_count=len(book.asks),
            best_bid=best_bid.quantize(Decimal('0.00000001')),
            best_ask=best_ask.quantize(Decimal('0.00000001')),
            spread=spread.quantize(Decimal('0.00000001')),
            spread_percent=spread_percent.quantize(Decimal('0.0001')),
            mid_price=mid_price.quantize(Decimal('0.00000001')),
            bid_ask_imbalance=bid_ask_imbalance.quantize(Decimal('0.0001')),
            depth_imbalance_1pct=depth_imbalance_1pct.quantize(Decimal('0.0001')),
            depth_imbalance_5pct=depth_imbalance_5pct.quantize(Decimal('0.0001')),
            avg_bid_depth=avg_bid_depth.quantize(Decimal('0.0001')),
            avg_ask_depth=avg_ask_depth.quantize(Decimal('0.0001')),
            order_count=len(book.bids) + len(book.asks)
        )
    
    def _calculate_depth_imbalance(
        self,
        book: OrderBook,
        percent: float
    ) -> Decimal:
        """
        Calculate depth imbalance within a percentage of mid price.
        
        Args:
            book: Order book
            percent: Percentage from mid price
            
        Returns:
            Depth imbalance (-1 to 1)
        """
        mid = book.mid_price
        if mid is None or mid == 0:
            return Decimal('0')
        
        threshold = mid * Decimal(str(percent))
        
        bid_volume = Decimal('0')
        ask_volume = Decimal('0')
        
        for entry in book.bids:
            if mid - entry.price <= threshold:
                bid_volume += entry.volume
        
        for entry in book.asks:
            if entry.price - mid <= threshold:
                ask_volume += entry.volume
        
        total = bid_volume + ask_volume
        if total == 0:
            return Decimal('0')
        
        return (bid_volume - ask_volume) / total
    
    # =========================================================================
    # HANDLERS
    # =========================================================================
    
    async def on_book_update(self, handler: Callable):
        """Register a book update handler."""
        key = "book_update"
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
                await asyncio.sleep(10)  # Every 10 seconds
                
                # Update statistics for tracked books
                for key, book in list(self._books.items()):
                    try:
                        stats = await self._calculate_statistics(book)
                        self._statistics[key] = stats
                        if self.pool:
                            await self._save_statistics(stats)
                    except Exception as e:
                        logger.error(f"Error updating statistics for {key}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update loop error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_books(self):
        """Load order books from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM order_books")
                
                for row in rows:
                    book = OrderBook(
                        id=row['id'],
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        bids=[OrderBookEntry(**b) for b in row['bids']],
                        asks=[OrderBookEntry(**a) for a in row['asks']],
                        timestamp=row['timestamp'],
                        status=OrderBookStatus(row['status']),
                        sequence_id=row['sequence_id'],
                        checksum=row['checksum'],
                        depth_level=DepthLevel(row['depth_level']),
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{book.exchange}:{book.symbol}"
                    self._books[key] = book
                
                logger.info(f"Loaded {len(self._books)} order books")
                
        except Exception as e:
            logger.error(f"Error loading books: {e}")
    
    async def _load_snapshots(self):
        """Load snapshots from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM order_book_snapshots
                    ORDER BY timestamp DESC LIMIT 1000
                    """
                )
                
                for row in rows:
                    snapshot = OrderBookSnapshot(
                        id=row['id'],
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        timestamp=row['timestamp'],
                        bids=[OrderBookEntry(**b) for b in row['bids']],
                        asks=[OrderBookEntry(**a) for a in row['asks']],
                        sequence_id=row['sequence_id'],
                        checksum=row['checksum'],
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{snapshot.exchange}:{snapshot.symbol}"
                    self._snapshots[key] = snapshot
                
                logger.info(f"Loaded {len(self._snapshots)} snapshots")
                
        except Exception as e:
            logger.error(f"Error loading snapshots: {e}")
    
    async def _load_statistics(self):
        """Load statistics from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM order_book_statistics")
                
                for row in rows:
                    stats = OrderBookStatistics(
                        exchange=row['exchange'],
                        symbol=row['symbol'],
                        timestamp=row['timestamp'],
                        total_bid_volume=row['total_bid_volume'],
                        total_ask_volume=row['total_ask_volume'],
                        total_volume=row['total_volume'],
                        bid_count=row['bid_count'],
                        ask_count=row['ask_count'],
                        best_bid=row['best_bid'],
                        best_ask=row['best_ask'],
                        spread=row['spread'],
                        spread_percent=row['spread_percent'],
                        mid_price=row['mid_price'],
                        bid_ask_imbalance=row['bid_ask_imbalance'],
                        depth_imbalance_1pct=row['depth_imbalance_1pct'],
                        depth_imbalance_5pct=row['depth_imbalance_5pct'],
                        avg_bid_depth=row['avg_bid_depth'],
                        avg_ask_depth=row['avg_ask_depth'],
                        order_count=row['order_count'],
                        metadata=row['metadata'] or {}
                    )
                    
                    key = f"{stats.exchange}:{stats.symbol}"
                    self._statistics[key] = stats
                
                logger.info(f"Loaded {len(self._statistics)} statistics")
                
        except Exception as e:
            logger.error(f"Error loading statistics: {e}")
    
    async def _save_book(self, book: OrderBook):
        """Save order book to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_books (
                        id, exchange, symbol, bids, asks,
                        timestamp, status, sequence_id,
                        checksum, depth_level, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (exchange, symbol, depth_level) DO UPDATE SET
                        bids = EXCLUDED.bids,
                        asks = EXCLUDED.asks,
                        timestamp = EXCLUDED.timestamp,
                        status = EXCLUDED.status,
                        sequence_id = EXCLUDED.sequence_id,
                        checksum = EXCLUDED.checksum,
                        metadata = EXCLUDED.metadata
                    """,
                    book.id,
                    book.exchange,
                    book.symbol,
                    json.dumps([e.dict() for e in book.bids], default=str),
                    json.dumps([e.dict() for e in book.asks], default=str),
                    book.timestamp,
                    book.status.value,
                    book.sequence_id,
                    book.checksum,
                    book.depth_level.value,
                    json.dumps(book.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving book: {e}")
    
    async def _save_delta(self, delta: OrderBookDelta):
        """Save delta to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_book_deltas (
                        id, exchange, symbol, sequence_id,
                        timestamp, action, bids, asks,
                        previous_sequence_id, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    delta.id,
                    delta.exchange,
                    delta.symbol,
                    delta.sequence_id,
                    delta.timestamp,
                    delta.action.value,
                    json.dumps([e.dict() for e in delta.bids], default=str),
                    json.dumps([e.dict() for e in delta.asks], default=str),
                    delta.previous_sequence_id,
                    json.dumps(delta.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving delta: {e}")
    
    async def _save_snapshot(self, snapshot: OrderBookSnapshot):
        """Save snapshot to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_book_snapshots (
                        id, exchange, symbol, timestamp,
                        bids, asks, sequence_id, checksum,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    snapshot.id,
                    snapshot.exchange,
                    snapshot.symbol,
                    snapshot.timestamp,
                    json.dumps([e.dict() for e in snapshot.bids], default=str),
                    json.dumps([e.dict() for e in snapshot.asks], default=str),
                    snapshot.sequence_id,
                    snapshot.checksum,
                    json.dumps(snapshot.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving snapshot: {e}")
    
    async def _save_statistics(self, stats: OrderBookStatistics):
        """Save statistics to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_book_statistics (
                        exchange, symbol, timestamp,
                        total_bid_volume, total_ask_volume,
                        total_volume, bid_count, ask_count,
                        best_bid, best_ask, spread,
                        spread_percent, mid_price,
                        bid_ask_imbalance,
                        depth_imbalance_1pct, depth_imbalance_5pct,
                        avg_bid_depth, avg_ask_depth,
                        order_count, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8,
                              $9, $10, $11, $12, $13,
                              $14, $15, $16,
                              $17, $18, $19, $20)
                    ON CONFLICT (exchange, symbol, timestamp) DO UPDATE SET
                        total_bid_volume = EXCLUDED.total_bid_volume,
                        total_ask_volume = EXCLUDED.total_ask_volume,
                        total_volume = EXCLUDED.total_volume,
                        bid_count = EXCLUDED.bid_count,
                        ask_count = EXCLUDED.ask_count,
                        best_bid = EXCLUDED.best_bid,
                        best_ask = EXCLUDED.best_ask,
                        spread = EXCLUDED.spread,
                        spread_percent = EXCLUDED.spread_percent,
                        mid_price = EXCLUDED.mid_price,
                        bid_ask_imbalance = EXCLUDED.bid_ask_imbalance,
                        depth_imbalance_1pct = EXCLUDED.depth_imbalance_1pct,
                        depth_imbalance_5pct = EXCLUDED.depth_imbalance_5pct,
                        avg_bid_depth = EXCLUDED.avg_bid_depth,
                        avg_ask_depth = EXCLUDED.avg_ask_depth,
                        order_count = EXCLUDED.order_count,
                        metadata = EXCLUDED.metadata
                    """,
                    stats.exchange,
                    stats.symbol,
                    stats.timestamp,
                    stats.total_bid_volume,
                    stats.total_ask_volume,
                    stats.total_volume,
                    stats.bid_count,
                    stats.ask_count,
                    stats.best_bid,
                    stats.best_ask,
                    stats.spread,
                    stats.spread_percent,
                    stats.mid_price,
                    stats.bid_ask_imbalance,
                    stats.depth_imbalance_1pct,
                    stats.depth_imbalance_5pct,
                    stats.avg_bid_depth,
                    stats.avg_ask_depth,
                    stats.order_count,
                    json.dumps(stats.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving statistics: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the order book manager."""
        self._running = False
        
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        
        logger.info("OrderBookManager shutdown")


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
    'OrderBookManager',
    'OrderBookStatus',
    'OrderBookAction',
    'OrderBookValidation',
    'OrderBookEntry',
    'OrderBook',
    'OrderBookDelta',
    'OrderBookSnapshot',
    'OrderBookStatistics',
    'CircuitBreakerOpenError'
]
