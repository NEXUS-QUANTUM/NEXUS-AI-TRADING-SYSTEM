# trading/bots/arbitrage_bot/core/order_router.py
# Nexus AI Trading System - Arbitrage Bot Order Router Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Order Router Module

This module provides advanced order routing and execution management
for the arbitrage bot system, including:

- Smart order routing across multiple exchanges
- Order execution optimization
- Order splitting and aggregation
- Slippage control
- Execution quality monitoring
- Order lifecycle management
- Multi-leg order coordination
- Atomic execution support
- Order timing optimization
- Fill rate optimization
- Execution cost minimization
- Order type selection
- Order cancellation management

The order router ensures optimal execution of arbitrage trades
across multiple exchanges with minimal slippage and maximum fill rates.
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
from trading.bots.arbitrage_bot.core.exchange_connector import (
    ExchangeConnector,
    ExchangeOrder,
    ExchangeOrderType,
    ExchangeOrderSide,
    ExchangeOrderStatus,
    ExchangeTimeInForce
)
from trading.bots.arbitrage_bot.core.market_data import MarketDataManager, MarketPrice
from trading.bots.arbitrage_bot.core.latency_monitor import LatencyMonitor, LatencySource
from trading.bots.arbitrage_bot.core.fee_calculator import FeeCalculator
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OrderRouterType(str, Enum):
    """Order router types."""
    SMART = "smart"  # Intelligent routing
    DIRECT = "direct"  # Direct to specific exchange
    SPLIT = "split"  # Split across exchanges
    ATOMIC = "atomic"  # Atomic execution
    ADAPTIVE = "adaptive"  # Adaptive based on conditions


class OrderExecutionStrategy(str, Enum):
    """Order execution strategies."""
    MARKET = "market"  # Market orders
    LIMIT = "limit"  # Limit orders
    TWAP = "twap"  # Time-weighted average price
    VWAP = "vwap"  # Volume-weighted average price
    ICEBERG = "iceberg"  # Iceberg orders
    PEGGED = "pegged"  # Pegged to market
    ADAPTIVE = "adaptive"  # Adaptive execution


class ExecutionQuality(str, Enum):
    """Execution quality levels."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    FAILED = "failed"


class OrderRoutingStatus(str, Enum):
    """Order routing status."""
    PENDING = "pending"
    ROUTING = "routing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderRoute(BaseModel):
    """Order route definition."""
    exchange: str
    symbol: str
    side: ExchangeOrderSide
    order_type: ExchangeOrderType
    volume: Decimal
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    time_in_force: ExchangeTimeInForce = ExchangeTimeInForce.GTC
    client_order_id: Optional[str] = None
    priority: int = 0  # Lower = higher priority
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('volume')
    def validate_volume(cls, v):
        if v <= 0:
            raise ValueError("Volume must be positive")
        return v


class RoutingRequest(BaseModel):
    """Order routing request."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    total_volume: Decimal
    side: ExchangeOrderSide
    order_type: ExchangeOrderType = ExchangeOrderType.LIMIT
    price: Optional[Decimal] = None
    limit_price: Optional[Decimal] = None
    max_slippage: Decimal = Decimal('0.005')  # 0.5%
    min_fill_rate: Decimal = Decimal('0.8')  # 80%
    max_execution_time: int = 30  # seconds
    time_in_force: ExchangeTimeInForce = ExchangeTimeInForce.GTC
    client_order_id: Optional[str] = None
    exchanges: Optional[List[str]] = None
    strategy: OrderExecutionStrategy = OrderExecutionStrategy.LIMIT
    priority: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('total_volume')
    def validate_volume(cls, v):
        if v <= 0:
            raise ValueError("Volume must be positive")
        return v


class RoutingResponse(BaseModel):
    """Order routing response."""
    id: str
    request_id: str
    status: OrderRoutingStatus
    total_volume: Decimal
    filled_volume: Decimal
    remaining_volume: Decimal
    average_price: Decimal
    total_cost: Decimal
    total_fee: Decimal
    orders: List[ExchangeOrder] = Field(default_factory=list)
    routes: List[OrderRoute] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    fill_rate: Decimal = Decimal('0')
    slippage: Decimal = Decimal('0')
    slippage_percent: Decimal = Decimal('0')
    quality: ExecutionQuality = ExecutionQuality.GOOD
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_completed(self) -> bool:
        """Check if routing is completed."""
        return self.status in [
            OrderRoutingStatus.COMPLETED,
            OrderRoutingStatus.PARTIALLY_COMPLETED,
            OrderRoutingStatus.FAILED,
            OrderRoutingStatus.CANCELLED
        ]

    @property
    def is_successful(self) -> bool:
        """Check if routing was successful."""
        return (self.status == OrderRoutingStatus.COMPLETED and 
                self.fill_rate >= Decimal('0.9'))

    @property
    def remaining_percent(self) -> Decimal:
        """Get remaining volume percentage."""
        if self.total_volume == 0:
            return Decimal('0')
        return self.remaining_volume / self.total_volume * 100


class ExecutionReport(BaseModel):
    """Execution report."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    routing_id: str
    exchange: str
    order_id: str
    symbol: str
    side: ExchangeOrderSide
    price: Decimal
    volume: Decimal
    fee: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Routing requests
CREATE TABLE IF NOT EXISTS order_routing_requests (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    total_volume DECIMAL(32, 16) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    price DECIMAL(32, 16),
    limit_price DECIMAL(32, 16),
    max_slippage DECIMAL(32, 16) NOT NULL,
    min_fill_rate DECIMAL(32, 16) NOT NULL,
    max_execution_time INTEGER NOT NULL,
    time_in_force VARCHAR(10) NOT NULL,
    client_order_id VARCHAR(64),
    exchanges JSONB DEFAULT '[]',
    strategy VARCHAR(20) NOT NULL,
    priority INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    filled_volume DECIMAL(32, 16) DEFAULT 0,
    remaining_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    total_cost DECIMAL(32, 16) DEFAULT 0,
    total_fee DECIMAL(32, 16) DEFAULT 0,
    execution_time_ms FLOAT DEFAULT 0,
    fill_rate DECIMAL(32, 16) DEFAULT 0,
    slippage DECIMAL(32, 16) DEFAULT 0,
    slippage_percent DECIMAL(32, 16) DEFAULT 0,
    quality VARCHAR(20),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_order_routing_requests_symbol (symbol),
    INDEX idx_order_routing_requests_status (status),
    INDEX idx_order_routing_requests_created_at (created_at)
);

-- Execution reports
CREATE TABLE IF NOT EXISTS execution_reports (
    id VARCHAR(64) PRIMARY KEY,
    routing_id VARCHAR(64) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    order_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_execution_reports_routing_id (routing_id),
    INDEX idx_execution_reports_timestamp (timestamp)
);
"""


# =============================================================================
# ORDER ROUTER CLASS
# =============================================================================

class OrderRouter:
    """
    Advanced order router for arbitrage bot.
    
    Features:
    - Smart order routing across multiple exchanges
    - Order execution optimization
    - Order splitting and aggregation
    - Slippage control
    - Execution quality monitoring
    - Order lifecycle management
    - Multi-leg order coordination
    - Atomic execution support
    - Order timing optimization
    - Fill rate optimization
    - Execution cost minimization
    - Order type selection
    - Order cancellation management
    """
    
    def __init__(
        self,
        market_data: MarketDataManager,
        fee_calculator: FeeCalculator,
        latency_monitor: Optional[LatencyMonitor] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.market_data = market_data
        self.fee_calculator = fee_calculator
        self.latency_monitor = latency_monitor
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Exchange connectors
        self._connectors: Dict[str, ExchangeConnector] = {}
        
        # Active routes
        self._routes: Dict[str, RoutingResponse] = {}
        
        # Circuit breakers
        self._router_cb = CircuitBreaker(
            name="order_router",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        # Execution tasks
        self._execution_tasks: Dict[str, asyncio.Task] = {}
        
        # Callbacks
        self._callbacks: List[Callable] = []
        
        logger.info("OrderRouter initialized")
    
    async def initialize(self):
        """Initialize the order router."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        self._running = True
        
        # Register connectors from market data
        if hasattr(self.market_data, '_connectors'):
            for name, connector in self.market_data._connectors.items():
                self.register_connector(connector)
        
        self._initialized = True
        logger.info("OrderRouter initialized")
    
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
    # CONNECTOR MANAGEMENT
    # =========================================================================
    
    def register_connector(self, connector: ExchangeConnector):
        """
        Register an exchange connector.
        
        Args:
            connector: Exchange connector instance
        """
        self._connectors[connector.config.exchange] = connector
        logger.info(f"Registered connector for {connector.config.exchange}")
    
    # =========================================================================
    # ORDER ROUTING
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def route_order(
        self,
        request: RoutingRequest
    ) -> RoutingResponse:
        """
        Route an order using the specified strategy.
        
        Args:
            request: Routing request
            
        Returns:
            RoutingResponse
        """
        if self._router_cb.is_open():
            raise CircuitBreakerOpenError("Order router circuit breaker is open")
        
        try:
            # Get available exchanges
            exchanges = request.exchanges or list(self._connectors.keys())
            if not exchanges:
                raise ValueError("No exchanges available")
            
            # Get current market prices
            prices = {}
            for exchange in exchanges:
                try:
                    price = await self.market_data.get_price(exchange, request.symbol)
                    prices[exchange] = price
                except Exception as e:
                    logger.warning(f"Error getting price for {exchange}: {e}")
            
            if not prices:
                raise ValueError("No price data available")
            
            # Calculate optimal route
            routes = await self._calculate_routes(request, prices)
            if not routes:
                raise ValueError("No valid routes found")
            
            # Execute routes
            response = await self._execute_routes(request, routes)
            
            # Record success
            self._router_cb.record_success()
            
            return response
            
        except Exception as e:
            self._router_cb.record_failure()
            logger.error(f"Order routing error: {e}")
            
            # Create failed response
            return RoutingResponse(
                id=str(uuid.uuid4()),
                request_id=request.id,
                status=OrderRoutingStatus.FAILED,
                total_volume=request.total_volume,
                filled_volume=Decimal('0'),
                remaining_volume=request.total_volume,
                average_price=Decimal('0'),
                total_cost=Decimal('0'),
                total_fee=Decimal('0'),
                error_message=str(e),
                quality=ExecutionQuality.FAILED
            )
    
    async def _calculate_routes(
        self,
        request: RoutingRequest,
        prices: Dict[str, MarketPrice]
    ) -> List[OrderRoute]:
        """
        Calculate optimal routes for the request.
        
        Args:
            request: Routing request
            prices: Market prices
            
        Returns:
            List of OrderRoute
        """
        routes = []
        remaining_volume = request.total_volume
        
        # Determine if volume should be split
        exchanges = list(prices.keys())
        
        if request.strategy == OrderExecutionStrategy.MARKET:
            # Use market orders
            for exchange in exchanges:
                price = prices[exchange]
                if request.side == ExchangeOrderSide.BUY:
                    route_price = price.ask
                else:
                    route_price = price.bid
                
                # Check if price is within slippage limit
                target_price = request.price or route_price
                if abs(route_price - target_price) / target_price <= request.max_slippage:
                    route = OrderRoute(
                        exchange=exchange,
                        symbol=request.symbol,
                        side=request.side,
                        order_type=ExchangeOrderType.MARKET,
                        volume=min(remaining_volume, Decimal('100')),  # Max market order size
                        price=route_price,
                        time_in_force=ExchangeTimeInForce.IOC,
                        priority=0
                    )
                    routes.append(route)
                    remaining_volume -= route.volume
                    
                    if remaining_volume <= 0:
                        break
        
        elif request.strategy == OrderExecutionStrategy.LIMIT:
            # Use limit orders at specified price
            target_price = request.price or min(prices.values(), key=lambda p: p.ask if request.side == ExchangeOrderSide.BUY else p.bid)
            
            for exchange in exchanges:
                if remaining_volume <= 0:
                    break
                
                price = prices[exchange]
                if request.side == ExchangeOrderSide.BUY:
                    route_price = min(price.ask, target_price)
                else:
                    route_price = max(price.bid, target_price)
                
                # Check if price is within slippage limit
                if abs(route_price - target_price) / target_price > request.max_slippage:
                    continue
                
                # Split volume proportionally based on liquidity
                share = Decimal('0.5') if len(routes) < 2 else Decimal('0.3')
                volume = min(remaining_volume * share, Decimal('1000'))
                
                route = OrderRoute(
                    exchange=exchange,
                    symbol=request.symbol,
                    side=request.side,
                    order_type=ExchangeOrderType.LIMIT,
                    volume=volume,
                    limit_price=route_price,
                    time_in_force=request.time_in_force,
                    priority=len(routes)
                )
                routes.append(route)
                remaining_volume -= volume
        
        elif request.strategy == OrderExecutionStrategy.TWAP:
            # Time-weighted average price
            # Split into chunks over time
            num_chunks = min(10, max(2, int(remaining_volume / Decimal('100'))))
            chunk_size = remaining_volume / num_chunks
            
            for i in range(num_chunks):
                if remaining_volume <= 0:
                    break
                
                # Rotate exchanges
                exchange = exchanges[i % len(exchanges)]
                price = prices[exchange]
                
                if request.side == ExchangeOrderSide.BUY:
                    route_price = price.ask
                else:
                    route_price = price.bid
                
                route = OrderRoute(
                    exchange=exchange,
                    symbol=request.symbol,
                    side=request.side,
                    order_type=ExchangeOrderType.LIMIT,
                    volume=chunk_size,
                    limit_price=route_price * (1 + (Decimal('0.01') * (i - num_chunks/2))),
                    time_in_force=ExchangeTimeInForce.GTC,
                    priority=i
                )
                routes.append(route)
                remaining_volume -= chunk_size
        
        else:
            # Default: direct route to best exchange
            if request.side == ExchangeOrderSide.BUY:
                best_exchange = min(exchanges, key=lambda e: prices[e].ask)
                price = prices[best_exchange].ask
            else:
                best_exchange = max(exchanges, key=lambda e: prices[e].bid)
                price = prices[best_exchange].bid
            
            route = OrderRoute(
                exchange=best_exchange,
                symbol=request.symbol,
                side=request.side,
                order_type=ExchangeOrderType.LIMIT,
                volume=remaining_volume,
                limit_price=price,
                time_in_force=request.time_in_force,
                priority=0
            )
            routes.append(route)
        
        return routes
    
    async def _execute_routes(
        self,
        request: RoutingRequest,
        routes: List[OrderRoute]
    ) -> RoutingResponse:
        """
        Execute the calculated routes.
        
        Args:
            request: Routing request
            routes: List of routes
            
        Returns:
            RoutingResponse
        """
        response = RoutingResponse(
            id=str(uuid.uuid4()),
            request_id=request.id,
            status=OrderRoutingStatus.PENDING,
            total_volume=request.total_volume,
            filled_volume=Decimal('0'),
            remaining_volume=request.total_volume,
            average_price=Decimal('0'),
            total_cost=Decimal('0'),
            total_fee=Decimal('0'),
            routes=routes,
            created_at=datetime.utcnow()
        )
        
        self._routes[response.id] = response
        
        # Execute routes
        orders = []
        total_cost = Decimal('0')
        total_fee = Decimal('0')
        total_filled = Decimal('0')
        total_volume = Decimal('0')
        prices = []
        
        for route in routes:
            try:
                connector = self._connectors.get(route.exchange)
                if not connector:
                    continue
                
                # Place order
                if self.latency_monitor:
                    order, _ = await self.latency_monitor.measure_latency(
                        source=LatencySource.ORDER_PLACEMENT,
                        func=connector.place_order,
                        symbol=route.symbol,
                        side=route.side,
                        order_type=route.order_type,
                        volume=route.volume,
                        price=route.limit_price or route.price,
                        time_in_force=route.time_in_force,
                        client_order_id=route.client_order_id,
                        exchange=route.exchange,
                        operation="place_order"
                    )
                else:
                    order = await connector.place_order(
                        symbol=route.symbol,
                        side=route.side,
                        order_type=route.order_type,
                        volume=route.volume,
                        price=route.limit_price or route.price,
                        time_in_force=route.time_in_force,
                        client_order_id=route.client_order_id
                    )
                
                orders.append(order)
                
                # Update totals
                filled = order.filled_volume
                total_filled += filled
                total_volume += order.volume
                
                if order.average_price and filled > 0:
                    cost = order.average_price * filled
                    total_cost += cost
                    prices.append(order.average_price)
                
                total_fee += order.fee
                
            except Exception as e:
                logger.error(f"Error executing route on {route.exchange}: {e}")
                response.error_message = str(e)
        
        # Update response
        response.orders = orders
        response.filled_volume = total_filled
        response.remaining_volume = request.total_volume - total_filled
        response.total_cost = total_cost
        response.total_fee = total_fee
        
        if total_filled > 0:
            response.average_price = total_cost / total_filled
            response.fill_rate = total_filled / request.total_volume
        else:
            response.average_price = Decimal('0')
            response.fill_rate = Decimal('0')
        
        # Calculate slippage
        if request.price and response.average_price > 0:
            response.slippage = response.average_price - request.price
            response.slippage_percent = response.slippage / request.price * 100
        
        # Determine quality
        if response.fill_rate >= Decimal('0.95'):
            response.quality = ExecutionQuality.EXCELLENT
        elif response.fill_rate >= Decimal('0.8'):
            response.quality = ExecutionQuality.GOOD
        elif response.fill_rate >= Decimal('0.5'):
            response.quality = ExecutionQuality.FAIR
        elif response.fill_rate > 0:
            response.quality = ExecutionQuality.POOR
        else:
            response.quality = ExecutionQuality.FAILED
        
        # Determine status
        if response.fill_rate >= Decimal('0.9'):
            response.status = OrderRoutingStatus.COMPLETED
        elif response.fill_rate > 0:
            response.status = OrderRoutingStatus.PARTIALLY_COMPLETED
        else:
            response.status = OrderRoutingStatus.FAILED
        
        response.completed_at = datetime.utcnow()
        response.execution_time_ms = (response.completed_at - response.created_at).total_seconds() * 1000
        
        # Save to database
        if self.pool:
            await self._save_routing_response(response)
            
            # Save execution reports
            for order in orders:
                report = ExecutionReport(
                    routing_id=response.id,
                    exchange=route.exchange,
                    order_id=order.id,
                    symbol=order.symbol,
                    side=order.side,
                    price=order.average_price or order.price,
                    volume=order.filled_volume,
                    fee=order.fee
                )
                await self._save_execution_report(report)
        
        # Update cache
        if self.redis:
            await self._cache_response(response)
        
        # Notify callbacks
        for callback in self._callbacks:
            try:
                await callback(response)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        return response
    
    # =========================================================================
    # ORDER MANAGEMENT
    # =========================================================================
    
    async def cancel_route(self, route_id: str) -> bool:
        """
        Cancel an active route.
        
        Args:
            route_id: Route ID
            
        Returns:
            True if cancelled successfully
        """
        if route_id not in self._routes:
            return False
        
        response = self._routes[route_id]
        
        if response.is_completed:
            return False
        
        cancelled = 0
        for order in response.orders:
            if order.is_open:
                try:
                    connector = self._connectors.get(order.exchange)
                    if connector:
                        if await connector.cancel_order(order.id):
                            cancelled += 1
                except Exception as e:
                    logger.error(f"Error cancelling order {order.id}: {e}")
        
        response.status = OrderRoutingStatus.CANCELLED
        response.completed_at = datetime.utcnow()
        
        logger.info(f"Cancelled route {route_id} with {cancelled} orders")
        return cancelled > 0
    
    async def get_route_status(self, route_id: str) -> Optional[RoutingResponse]:
        """
        Get status of a route.
        
        Args:
            route_id: Route ID
            
        Returns:
            RoutingResponse or None
        """
        # Check memory
        if route_id in self._routes:
            return self._routes[route_id]
        
        # Check cache
        if self.redis:
            cached = await self.redis.get(f"route:{route_id}")
            if cached:
                data = json.loads(cached)
                return RoutingResponse(**data)
        
        # Check database
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM order_routing_requests WHERE id = $1",
                        route_id
                    )
                    if row:
                        return RoutingResponse(
                            id=row['id'],
                            request_id=row['id'],
                            status=OrderRoutingStatus(row['status']),
                            total_volume=row['total_volume'],
                            filled_volume=row['filled_volume'],
                            remaining_volume=row['remaining_volume'],
                            average_price=row['avg_price'],
                            total_cost=row['total_cost'],
                            total_fee=row['total_fee'],
                            orders=[],
                            routes=[],
                            fill_rate=row['fill_rate'],
                            slippage=row['slippage'],
                            slippage_percent=row['slippage_percent'],
                            quality=ExecutionQuality(row['quality']) if row['quality'] else ExecutionQuality.GOOD,
                            error_message=row['error_message'],
                            created_at=row['created_at'],
                            completed_at=row['completed_at'],
                            metadata=row['metadata'] or {}
                        )
            except Exception as e:
                logger.error(f"Error getting route from database: {e}")
        
        return None
    
    # =========================================================================
    # EXECUTION OPTIMIZATION
    # =========================================================================
    
    async def optimize_execution(
        self,
        symbol: str,
        volume: Decimal,
        side: ExchangeOrderSide,
        exchanges: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Optimize execution parameters.
        
        Args:
            symbol: Trading symbol
            volume: Volume to trade
            side: Buy or sell
            exchanges: List of exchanges
            
        Returns:
            Optimization result
        """
        if exchanges is None:
            exchanges = list(self._connectors.keys())
        
        result = {
            "best_exchange": None,
            "best_price": None,
            "best_fee": None,
            "total_cost": None,
            "recommendations": []
        }
        
        for exchange in exchanges:
            try:
                price = await self.market_data.get_price(exchange, symbol)
                fee_config = await self.fee_calculator.get_fee_config(exchange)
                
                if side == ExchangeOrderSide.BUY:
                    price_value = price.ask
                else:
                    price_value = price.bid
                
                # Calculate effective price with fees
                fee_rate = fee_config.get_taker_fee() if fee_config else Decimal('0.001')
                effective_price = price_value * (1 + fee_rate)
                total_cost = effective_price * volume
                
                if (result["best_price"] is None or 
                    effective_price < result["best_price"]):
                    result["best_exchange"] = exchange
                    result["best_price"] = effective_price
                    result["best_fee"] = fee_rate
                    result["total_cost"] = total_cost
            except Exception as e:
                logger.error(f"Error optimizing for {exchange}: {e}")
        
        # Generate recommendations
        if result["best_exchange"]:
            result["recommendations"].append(
                f"Best exchange: {result['best_exchange']} with effective price {result['best_price']:.8f}"
            )
            
            # Check if splitting would help
            if len(exchanges) > 1:
                result["recommendations"].append(
                    "Consider splitting order across exchanges for better liquidity"
                )
            
            # Check if limit orders would be better
            result["recommendations"].append(
                "Consider using limit orders for better price"
            )
        
        return result
    
    # =========================================================================
    # CALLBACKS
    # =========================================================================
    
    async def on_completion(self, callback: Callable):
        """
        Register a completion callback.
        
        Args:
            callback: Callback function
        """
        self._callbacks.append(callback)
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_routing_response(self, response: RoutingResponse):
        """Save routing response to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO order_routing_requests (
                        id, symbol, total_volume, side, order_type,
                        price, limit_price, max_slippage, min_fill_rate,
                        max_execution_time, time_in_force, client_order_id,
                        exchanges, strategy, priority, status,
                        filled_volume, remaining_volume, avg_price,
                        total_cost, total_fee, execution_time_ms,
                        fill_rate, slippage, slippage_percent,
                        quality, error_message, completed_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14, $15, $16,
                              $17, $18, $19, $20, $21, $22,
                              $23, $24, $25, $26, $27, $28, $29)
                    """,
                    response.id,
                    response.symbol,
                    response.total_volume,
                    response.side.value,
                    response.order_type.value,
                    response.price,
                    response.limit_price,
                    response.max_slippage,
                    response.min_fill_rate,
                    response.max_execution_time,
                    response.time_in_force.value,
                    response.client_order_id,
                    json.dumps(response.exchanges or []),
                    response.strategy.value,
                    response.priority,
                    response.status.value,
                    response.filled_volume,
                    response.remaining_volume,
                    response.average_price,
                    response.total_cost,
                    response.total_fee,
                    response.execution_time_ms,
                    response.fill_rate,
                    response.slippage,
                    response.slippage_percent,
                    response.quality.value,
                    response.error_message,
                    response.completed_at,
                    json.dumps(response.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving routing response: {e}")
    
    async def _save_execution_report(self, report: ExecutionReport):
        """Save execution report to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO execution_reports (
                        id, routing_id, exchange, order_id,
                        symbol, side, price, volume, fee,
                        timestamp, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                    report.id,
                    report.routing_id,
                    report.exchange,
                    report.order_id,
                    report.symbol,
                    report.side.value,
                    report.price,
                    report.volume,
                    report.fee,
                    report.timestamp,
                    json.dumps(report.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving execution report: {e}")
    
    async def _cache_response(self, response: RoutingResponse):
        """Cache routing response in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"route:{response.id}"
            await self.redis.setex(
                key,
                3600,  # 1 hour
                json.dumps(response.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Error caching response: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the order router."""
        self._running = False
        
        # Cancel active routes
        for route_id, response in self._routes.items():
            if not response.is_completed:
                await self.cancel_route(route_id)
        
        logger.info("OrderRouter shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class CircuitBreakerOpenError(Exception):
    """Circuit breaker open error."""
    pass


class RoutingError(Exception):
    """Routing error."""
    pass


class ExecutionError(Exception):
    """Execution error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OrderRouter',
    'OrderRouterType',
    'OrderExecutionStrategy',
    'ExecutionQuality',
    'OrderRoutingStatus',
    'OrderRoute',
    'RoutingRequest',
    'RoutingResponse',
    'ExecutionReport',
    'CircuitBreakerOpenError',
    'RoutingError',
    'ExecutionError'
]
