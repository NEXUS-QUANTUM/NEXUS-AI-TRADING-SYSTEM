# trading/bots/arbitrage_bot/core/order_splitter.py
# Nexus AI Trading System - Arbitrage Bot Order Splitter Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Order Splitter Module

This module provides advanced order splitting and size optimization
for the arbitrage bot system, including:

- Smart order splitting strategies
- Dynamic position sizing
- Volume-based splitting
- Risk-adjusted splitting
- Time-based splitting
- Price-based splitting
- Optimal chunk calculation
- Slippage minimization
- Market impact reduction
- Fill rate optimization
- Adaptive splitting
- Batch processing
- Order size limits
- Minimum volume handling
- Partial fill management

The order splitter ensures optimal order sizes for arbitrage execution
to minimize market impact and maximize fill rates.
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
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.bots.arbitrage_bot.core.exchange_connector import ExchangeConnector
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketDepth
from trading.bots.arbitrage_bot.core.fee_calculator import FeeCalculator
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class SplitStrategy(str, Enum):
    """Order splitting strategies."""
    FIXED = "fixed"              # Fixed number of equal chunks
    VOLUME_BASED = "volume_based"  # Based on available volume
    TIME_BASED = "time_based"    # Spread over time
    PRICE_BASED = "price_based"  # Based on price levels
    RISK_ADJUSTED = "risk_adjusted"  # Based on risk
    ADAPTIVE = "adaptive"        # Adaptive to market conditions
    OPTIMAL = "optimal"          # Optimal chunk size
    MIN_IMPACT = "min_impact"    # Minimize market impact
    MAX_FILL = "max_fill"        # Maximize fill rate


class SplitStatus(str, Enum):
    """Split status."""
    PENDING = "pending"
    SPLITTING = "splitting"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SplitType(str, Enum):
    """Split types."""
    CHUNK = "chunk"      # Split into chunks
    LADDER = "ladder"    # Ladder orders at different prices
    ICON = "icon"        # Icon (iceberg) orders
    TWAP = "twap"        # Time-weighted average price
    VWAP = "vwap"        # Volume-weighted average price


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SplitConfig(BaseModel):
    """Split configuration."""
    max_chunk_size: Decimal = Decimal('1000')
    min_chunk_size: Decimal = Decimal('0.01')
    max_chunks: int = 20
    min_chunks: int = 1
    default_strategy: SplitStrategy = SplitStrategy.OPTIMAL
    volume_threshold: Decimal = Decimal('10000')
    price_threshold: Decimal = Decimal('0.005')  # 0.5%
    time_spread: int = 60  # seconds
    risk_adjustment: Decimal = Decimal('0.1')
    adaptive_interval: int = 10  # seconds
    max_slippage: Decimal = Decimal('0.01')  # 1%
    min_fill_rate: Decimal = Decimal('0.8')  # 80%
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('max_chunk_size', 'min_chunk_size')
    def validate_sizes(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v

    @validator('max_chunks', 'min_chunks')
    def validate_chunks(cls, v):
        if v < 1:
            raise ValueError("Chunks must be at least 1")
        return v


class SplitRequest(BaseModel):
    """Split request."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    total_volume: Decimal
    strategy: SplitStrategy = SplitStrategy.OPTIMAL
    split_type: SplitType = SplitType.CHUNK
    min_chunk_size: Optional[Decimal] = None
    max_chunk_size: Optional[Decimal] = None
    num_chunks: Optional[int] = None
    price_spread: Optional[Decimal] = None
    time_spread: Optional[int] = None
    max_slippage: Optional[Decimal] = None
    min_fill_rate: Optional[Decimal] = None
    reference_price: Optional[Decimal] = None
    side: Optional[str] = None  # 'buy' or 'sell'
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('total_volume')
    def validate_volume(cls, v):
        if v <= 0:
            raise ValueError("Volume must be positive")
        return v


class SplitChunk(BaseModel):
    """Split chunk."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    split_id: str
    chunk_index: int
    volume: Decimal
    price: Optional[Decimal] = None
    status: SplitStatus = SplitStatus.PENDING
    executed_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    order_id: Optional[str] = None
    exchange: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Check if chunk is completed."""
        return self.status == SplitStatus.COMPLETED

    @property
    def fill_rate(self) -> Decimal:
        """Calculate fill rate."""
        if self.volume == 0:
            return Decimal('0')
        return self.executed_volume / self.volume


class SplitResponse(BaseModel):
    """Split response."""
    id: str
    request_id: str
    symbol: str
    total_volume: Decimal
    executed_volume: Decimal
    remaining_volume: Decimal
    average_price: Decimal
    total_cost: Decimal
    total_fee: Decimal
    chunks: List[SplitChunk] = Field(default_factory=list)
    status: SplitStatus = SplitStatus.PENDING
    fill_rate: Decimal = Decimal('0')
    slippage: Decimal = Decimal('0')
    slippage_percent: Decimal = Decimal('0')
    strategy_used: SplitStrategy
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Check if split is completed."""
        return self.status in [SplitStatus.COMPLETED, SplitStatus.PARTIALLY_COMPLETED]

    @property
    def is_successful(self) -> bool:
        """Check if split was successful."""
        return self.status == SplitStatus.COMPLETED and self.fill_rate >= Decimal('0.9')


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Split requests
CREATE TABLE IF NOT EXISTS order_split_requests (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    total_volume DECIMAL(32, 16) NOT NULL,
    strategy VARCHAR(20) NOT NULL,
    split_type VARCHAR(20) NOT NULL,
    min_chunk_size DECIMAL(32, 16),
    max_chunk_size DECIMAL(32, 16),
    num_chunks INTEGER,
    price_spread DECIMAL(32, 16),
    time_spread INTEGER,
    max_slippage DECIMAL(32, 16),
    min_fill_rate DECIMAL(32, 16),
    reference_price DECIMAL(32, 16),
    side VARCHAR(10),
    status VARCHAR(20) NOT NULL,
    executed_volume DECIMAL(32, 16) DEFAULT 0,
    remaining_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    total_cost DECIMAL(32, 16) DEFAULT 0,
    total_fee DECIMAL(32, 16) DEFAULT 0,
    fill_rate DECIMAL(32, 16) DEFAULT 0,
    slippage DECIMAL(32, 16) DEFAULT 0,
    slippage_percent DECIMAL(32, 16) DEFAULT 0,
    execution_time_ms FLOAT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_order_split_requests_symbol (symbol),
    INDEX idx_order_split_requests_status (status),
    INDEX idx_order_split_requests_created_at (created_at)
);

-- Split chunks
CREATE TABLE IF NOT EXISTS order_split_chunks (
    id VARCHAR(64) PRIMARY KEY,
    split_id VARCHAR(64) NOT NULL,
    chunk_index INTEGER NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    price DECIMAL(32, 16),
    status VARCHAR(20) NOT NULL,
    executed_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16),
    fee DECIMAL(32, 16) DEFAULT 0,
    order_id VARCHAR(64),
    exchange VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_order_split_chunks_split_id (split_id),
    INDEX idx_order_split_chunks_status (status)
);
"""


# =============================================================================
# ORDER SPLITTER CLASS
# =============================================================================

class OrderSplitter:
    """
    Advanced order splitter for arbitrage bot.
    
    Features:
    - Smart order splitting strategies
    - Dynamic position sizing
    - Volume-based splitting
    - Risk-adjusted splitting
    - Time-based splitting
    - Price-based splitting
    - Optimal chunk calculation
    - Slippage minimization
    - Market impact reduction
    - Fill rate optimization
    - Adaptive splitting
    - Batch processing
    - Order size limits
    - Minimum volume handling
    - Partial fill management
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        fee_calculator: FeeCalculator,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[SplitConfig] = None
    ):
        self.market_data = market_data
        self.fee_calculator = fee_calculator
        self.redis = redis
        self.pool = pool
        self.config = config or SplitConfig()
        
        # Active splits
        self._splits: Dict[str, SplitResponse] = {}
        
        # Circuit breakers
        self._splitter_cb = CircuitBreaker(
            name="order_splitter",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("OrderSplitter initialized")
    
    async def initialize(self):
        """Initialize the order splitter."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        self._initialized = True
        logger.info("OrderSplitter initialized")
    
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
    # SPLIT OPERATIONS
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def split_order(
        self,
        request: SplitRequest
    ) -> SplitResponse:
        """
        Split an order into optimal chunks.
        
        Args:
            request: Split request
            
        Returns:
            SplitResponse
        """
        if self._splitter_cb.is_open():
            raise CircuitBreakerOpenError("Order splitter circuit breaker is open")
        
        try:
            # Determine optimal split parameters
            chunks = await self._calculate_chunks(request)
            
            if not chunks:
                raise ValueError("No chunks calculated")
            
            # Create response
            response = SplitResponse(
                id=str(uuid.uuid4()),
                request_id=request.id,
                symbol=request.symbol,
                total_volume=request.total_volume,
                executed_volume=Decimal('0'),
                remaining_volume=request.total_volume,
                average_price=Decimal('0'),
                total_cost=Decimal('0'),
                total_fee=Decimal('0'),
                chunks=chunks,
                status=SplitStatus.SPLITTING,
                strategy_used=request.strategy,
                created_at=datetime.utcnow()
            )
            
            self._splits[response.id] = response
            
            # Save to database
            if self.pool:
                await self._save_split_response(response)
            
            # Record success
            self._splitter_cb.record_success()
            
            logger.info(
                f"Split order {response.id}: {len(chunks)} chunks, "
                f"total {request.total_volume} {request.symbol}"
            )
            
            return response
            
        except Exception as e:
            self._splitter_cb.record_failure()
            logger.error(f"Order splitting error: {e}")
            
            # Create failed response
            return SplitResponse(
                id=str(uuid.uuid4()),
                request_id=request.id,
                symbol=request.symbol,
                total_volume=request.total_volume,
                executed_volume=Decimal('0'),
                remaining_volume=request.total_volume,
                average_price=Decimal('0'),
                total_cost=Decimal('0'),
                total_fee=Decimal('0'),
                status=SplitStatus.FAILED,
                strategy_used=request.strategy,
                error_message=str(e),
                created_at=datetime.utcnow()
            )
    
    async def _calculate_chunks(
        self,
        request: SplitRequest
    ) -> List[SplitChunk]:
        """
        Calculate optimal chunks for the request.
        
        Args:
            request: Split request
            
        Returns:
            List of SplitChunk
        """
        total_volume = request.total_volume
        
        # Get market depth for reference
        depth = None
        try:
            depth = await self.market_data.get_depth(
                request.symbol,
                depth=20
            )
        except Exception:
            pass
        
        # Determine chunk size based on strategy
        chunks = []
        
        if request.strategy == SplitStrategy.FIXED:
            # Fixed number of chunks
            num_chunks = request.num_chunks or self.config.min_chunks
            chunk_size = total_volume / num_chunks
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING
                    )
                )
        
        elif request.strategy == SplitStrategy.VOLUME_BASED:
            # Based on available volume
            if not depth:
                # Fallback to fixed
                return await self._calculate_chunks(
                    request.copy(update={'strategy': SplitStrategy.FIXED})
                )
            
            # Calculate optimal chunk size based on volume profile
            total_bid = depth.total_bid_volume
            total_ask = depth.total_ask_volume
            total_volume_depth = total_bid + total_ask
            
            if total_volume_depth == 0:
                chunk_size = total_volume / self.config.min_chunks
            else:
                # Chunk size proportional to liquidity
                chunk_ratio = min(Decimal('0.1'), total_volume / total_volume_depth)
                chunk_size = total_volume * chunk_ratio
            
            chunk_size = max(
                self.config.min_chunk_size,
                min(chunk_size, self.config.max_chunk_size)
            )
            
            num_chunks = math.ceil(float(total_volume / chunk_size))
            num_chunks = min(num_chunks, self.config.max_chunks)
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING
                    )
                )
        
        elif request.strategy == SplitStrategy.TIME_BASED:
            # Spread over time
            time_spread = request.time_spread or self.config.time_spread
            num_chunks = min(
                time_spread // 5,  # One chunk every 5 seconds
                self.config.max_chunks
            )
            num_chunks = max(num_chunks, self.config.min_chunks)
            
            chunk_size = total_volume / num_chunks
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'delay_seconds': i * 5}
                    )
                )
        
        elif request.strategy == SplitStrategy.PRICE_BASED:
            # Based on price levels
            if not depth:
                return await self._calculate_chunks(
                    request.copy(update={'strategy': SplitStrategy.FIXED})
                )
            
            price_spread = request.price_spread or self.config.price_threshold
            
            # Create ladder orders at different price levels
            num_levels = min(len(depth.bids) if depth.bids else 10, self.config.max_chunks)
            chunk_size = total_volume / num_levels
            
            for i in range(num_levels):
                price = None
                if request.side == 'buy' and depth.bids:
                    price = depth.bids[i][0] if i < len(depth.bids) else None
                elif request.side == 'sell' and depth.asks:
                    price = depth.asks[i][0] if i < len(depth.asks) else None
                
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        price=price,
                        status=SplitStatus.PENDING,
                        metadata={'price_level': i}
                    )
                )
        
        elif request.strategy == SplitStrategy.RISK_ADJUSTED:
            # Adjust based on risk
            risk_factor = Decimal('1') - self.config.risk_adjustment
            chunk_size = total_volume * risk_factor
            
            num_chunks = max(
                math.ceil(float(total_volume / chunk_size)),
                self.config.min_chunks
            )
            num_chunks = min(num_chunks, self.config.max_chunks)
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'risk_factor': float(risk_factor)}
                    )
                )
        
        elif request.strategy == SplitStrategy.ADAPTIVE:
            # Adaptive to market conditions
            # Monitor market and adjust chunk sizes dynamically
            
            # Start with fixed chunks
            num_chunks = self.config.min_chunks
            chunk_size = total_volume / num_chunks
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'adaptive': True}
                    )
                )
        
        elif request.strategy == SplitStrategy.OPTIMAL:
            # Calculate optimal chunk size
            if depth:
                # Use depth to find optimal chunk size
                avg_liquidity = (depth.total_bid_volume + depth.total_ask_volume) / 2
                chunk_size = avg_liquidity * Decimal('0.01')  # 1% of average liquidity
            else:
                chunk_size = self.config.max_chunk_size * Decimal('0.5')
            
            chunk_size = max(
                self.config.min_chunk_size,
                min(chunk_size, self.config.max_chunk_size)
            )
            
            num_chunks = math.ceil(float(total_volume / chunk_size))
            num_chunks = min(num_chunks, self.config.max_chunks)
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'optimal': True}
                    )
                )
        
        elif request.strategy == SplitStrategy.MIN_IMPACT:
            # Minimize market impact
            if depth:
                # Use 1% of total volume depth
                total_depth = depth.total_bid_volume + depth.total_ask_volume
                chunk_size = total_depth * Decimal('0.01')
            else:
                chunk_size = self.config.max_chunk_size * Decimal('0.1')
            
            chunk_size = max(
                self.config.min_chunk_size,
                min(chunk_size, self.config.max_chunk_size)
            )
            
            num_chunks = math.ceil(float(total_volume / chunk_size))
            num_chunks = min(num_chunks, self.config.max_chunks * 2)
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'min_impact': True}
                    )
                )
        
        elif request.strategy == SplitStrategy.MAX_FILL:
            # Maximize fill rate
            if depth:
                # Use larger chunks for better fill
                total_depth = depth.total_bid_volume + depth.total_ask_volume
                chunk_size = total_depth * Decimal('0.05')  # 5% of depth
            else:
                chunk_size = self.config.max_chunk_size
            
            chunk_size = min(chunk_size, self.config.max_chunk_size)
            chunk_size = max(chunk_size, self.config.min_chunk_size)
            
            num_chunks = math.ceil(float(total_volume / chunk_size))
            num_chunks = min(num_chunks, self.config.max_chunks)
            
            for i in range(num_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING,
                        metadata={'max_fill': True}
                    )
                )
        
        else:
            # Default to fixed
            chunk_size = total_volume / self.config.min_chunks
            for i in range(self.config.min_chunks):
                chunks.append(
                    SplitChunk(
                        split_id=request.id,
                        chunk_index=i,
                        volume=chunk_size,
                        status=SplitStatus.PENDING
                    )
                )
        
        # Adjust last chunk to match total volume
        if chunks:
            total_chunk_volume = sum(chunk.volume for chunk in chunks)
            if total_chunk_volume != total_volume:
                # Adjust last chunk
                chunks[-1].volume += (total_volume - total_chunk_volume)
        
        return chunks
    
    # =========================================================================
    # CHUNK EXECUTION
    # =========================================================================
    
    async def execute_chunk(
        self,
        split_id: str,
        chunk_index: int,
        exchange: str,
        order_id: str,
        executed_volume: Decimal,
        average_price: Decimal,
        fee: Decimal
    ):
        """
        Update chunk execution status.
        
        Args:
            split_id: Split ID
            chunk_index: Chunk index
            exchange: Exchange name
            order_id: Order ID
            executed_volume: Executed volume
            average_price: Average price
            fee: Fee
        """
        if split_id not in self._splits:
            return
        
        response = self._splits[split_id]
        
        if chunk_index >= len(response.chunks):
            return
        
        chunk = response.chunks[chunk_index]
        chunk.status = SplitStatus.COMPLETED
        chunk.executed_volume = executed_volume
        chunk.average_price = average_price
        chunk.fee = fee
        chunk.order_id = order_id
        chunk.exchange = exchange
        chunk.executed_at = datetime.utcnow()
        
        # Update response
        total_executed = Decimal('0')
        total_cost = Decimal('0')
        total_fee = Decimal('0')
        completed_chunks = 0
        
        for c in response.chunks:
            if c.status == SplitStatus.COMPLETED:
                completed_chunks += 1
                total_executed += c.executed_volume
                total_cost += c.executed_volume * (c.average_price or Decimal('0'))
                total_fee += c.fee
        
        response.executed_volume = total_executed
        response.remaining_volume = response.total_volume - total_executed
        response.total_cost = total_cost
        response.total_fee = total_fee
        
        if total_executed > 0:
            response.average_price = total_cost / total_executed
            response.fill_rate = total_executed / response.total_volume
        
        # Check status
        if response.remaining_volume <= Decimal('0.0001'):
            response.status = SplitStatus.COMPLETED
            response.completed_at = datetime.utcnow()
        elif completed_chunks > 0:
            response.status = SplitStatus.PARTIALLY_COMPLETED
        
        # Save to database
        if self.pool:
            await self._update_split_response(response)
            await self._update_split_chunk(chunk)
    
    # =========================================================================
    # SPLIT STATUS
    # =========================================================================
    
    async def get_split_status(self, split_id: str) -> Optional[SplitResponse]:
        """
        Get split status.
        
        Args:
            split_id: Split ID
            
        Returns:
            SplitResponse or None
        """
        return self._splits.get(split_id)
    
    async def cancel_split(self, split_id: str) -> bool:
        """
        Cancel a split.
        
        Args:
            split_id: Split ID
            
        Returns:
            True if cancelled successfully
        """
        if split_id not in self._splits:
            return False
        
        response = self._splits[split_id]
        
        if response.is_completed:
            return False
        
        response.status = SplitStatus.CANCELLED
        response.completed_at = datetime.utcnow()
        
        logger.info(f"Cancelled split {split_id}")
        return True
    
    # =========================================================================
    # OPTIMIZATION
    # =========================================================================
    
    async def optimize_split(
        self,
        symbol: str,
        volume: Decimal,
        side: str = 'buy'
    ) -> Dict[str, Any]:
        """
        Optimize split parameters.
        
        Args:
            symbol: Trading symbol
            volume: Volume to split
            side: 'buy' or 'sell'
            
        Returns:
            Optimization result
        """
        result = {
            "symbol": symbol,
            "volume": volume,
            "side": side,
            "recommended_strategy": SplitStrategy.OPTIMAL,
            "recommended_chunks": self.config.min_chunks,
            "estimated_impact": Decimal('0'),
            "recommendations": []
        }
        
        # Get market depth
        try:
            depth = await self.market_data.get_depth(symbol, depth=20)
            
            # Analyze liquidity
            total_depth = depth.total_bid_volume + depth.total_ask_volume
            
            if total_depth > 0:
                impact_ratio = volume / total_depth
                
                if impact_ratio < Decimal('0.01'):
                    result["recommended_strategy"] = SplitStrategy.MIN_IMPACT
                    result["recommendations"].append("Low market impact expected")
                elif impact_ratio < Decimal('0.05'):
                    result["recommended_strategy"] = SplitStrategy.OPTIMAL
                    result["recommendations"].append("Moderate market impact, use optimal splitting")
                elif impact_ratio < Decimal('0.1'):
                    result["recommended_strategy"] = SplitStrategy.VOLUME_BASED
                    result["recommendations"].append("High market impact, use volume-based splitting")
                else:
                    result["recommended_strategy"] = SplitStrategy.TIME_BASED
                    result["recommendations"].append("Very high market impact, use time-based splitting")
                
                # Calculate optimal chunks
                optimal_chunks = max(
                    self.config.min_chunks,
                    min(
                        self.config.max_chunks,
                        math.ceil(float(impact_ratio * Decimal('100')))
                    )
                )
                result["recommended_chunks"] = optimal_chunks
                result["estimated_impact"] = impact_ratio * Decimal('100')
            
        except Exception as e:
            logger.error(f"Error optimizing split: {e}")
            result["recommendations"].append("Unable to analyze market depth, using default strategy")
        
        return result
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_split_response(self, response: SplitResponse):
        """Save split response to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_split_requests (
                        id, symbol, total_volume, strategy, split_type,
                        min_chunk_size, max_chunk_size, num_chunks,
                        price_spread, time_spread, max_slippage,
                        min_fill_rate, reference_price, side,
                        status, executed_volume, remaining_volume,
                        avg_price, total_cost, total_fee, fill_rate,
                        slippage, slippage_percent, execution_time_ms,
                        error_message, completed_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22, $23,
                              $24, $25, $26, $27)
                    """,
                    response.id,
                    response.symbol,
                    response.total_volume,
                    response.strategy_used.value,
                    response.split_type.value,
                    response.min_chunk_size,
                    response.max_chunk_size,
                    response.num_chunks,
                    response.price_spread,
                    response.time_spread,
                    response.max_slippage,
                    response.min_fill_rate,
                    response.reference_price,
                    response.side,
                    response.status.value,
                    response.executed_volume,
                    response.remaining_volume,
                    response.average_price,
                    response.total_cost,
                    response.total_fee,
                    response.fill_rate,
                    response.slippage,
                    response.slippage_percent,
                    response.execution_time_ms,
                    response.error_message,
                    response.completed_at,
                    json.dumps(response.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving split response: {e}")
    
    async def _update_split_response(self, response: SplitResponse):
        """Update split response in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE order_split_requests SET
                        status = $1,
                        executed_volume = $2,
                        remaining_volume = $3,
                        avg_price = $4,
                        total_cost = $5,
                        total_fee = $6,
                        fill_rate = $7,
                        slippage = $8,
                        slippage_percent = $9,
                        execution_time_ms = $10,
                        error_message = $11,
                        completed_at = $12,
                        metadata = $13
                    WHERE id = $14
                    """,
                    response.status.value,
                    response.executed_volume,
                    response.remaining_volume,
                    response.average_price,
                    response.total_cost,
                    response.total_fee,
                    response.fill_rate,
                    response.slippage,
                    response.slippage_percent,
                    response.execution_time_ms,
                    response.error_message,
                    response.completed_at,
                    json.dumps(response.metadata, default=str),
                    response.id
                )
        except Exception as e:
            logger.error(f"Error updating split response: {e}")
    
    async def _update_split_chunk(self, chunk: SplitChunk):
        """Update split chunk in database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE order_split_chunks SET
                        status = $1,
                        executed_volume = $2,
                        avg_price = $3,
                        fee = $4,
                        order_id = $5,
                        exchange = $6,
                        executed_at = $7,
                        metadata = $8
                    WHERE id = $9
                    """,
                    chunk.status.value,
                    chunk.executed_volume,
                    chunk.average_price,
                    chunk.fee,
                    chunk.order_id,
                    chunk.exchange,
                    chunk.executed_at,
                    json.dumps(chunk.metadata, default=str),
                    chunk.id
                )
        except Exception as e:
            logger.error(f"Error updating split chunk: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the order splitter."""
        # Cancel active splits
        for split_id, response in self._splits.items():
            if not response.is_completed:
                await self.cancel_split(split_id)
        
        logger.info("OrderSplitter shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


class SplitError(Exception):
    """Split error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OrderSplitter',
    'SplitStrategy',
    'SplitStatus',
    'SplitType',
    'SplitConfig',
    'SplitRequest',
    'SplitChunk',
    'SplitResponse',
    'CircuitBreakerOpenError',
    'SplitError'
]
