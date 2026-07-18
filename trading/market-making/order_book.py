"""
NEXUS AI TRADING SYSTEM - Market Making Order Book Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/order_book.py
Description: Advanced order book management with full API integration
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status, WebSocket, WebSocketDisconnect

# NEXUS Internal Imports
from shared.configs.market_making_config import MarketMakingConfig
from shared.constants.trading_constants import ORDER_TYPES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.websocket_manager import WebSocketManager

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class OrderBookLevel(str, Enum):
    """Order book depth levels"""
    LEVEL_1 = "level_1"  # Best bid/ask only
    LEVEL_2 = "level_2"  # Top 10 levels
    LEVEL_3 = "level_3"  # Full order book


class OrderBookUpdateType(str, Enum):
    """Types of order book updates"""
    SNAPSHOT = "snapshot"
    UPDATE = "update"
    DELETE = "delete"
    TRADE = "trade"


class OrderSide(str, Enum):
    """Order side"""
    BID = "bid"
    ASK = "ask"


class OrderBookStatus(str, Enum):
    """Order book status"""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OrderBookLevelData(BaseModel):
    """Order book level data"""
    price: float
    size: float
    order_count: int = 0
    cumulative_size: float = 0.0


class OrderBookSnapshot(BaseModel):
    """Order book snapshot"""
    symbol: str
    timestamp: datetime
    bid_levels: List[OrderBookLevelData]
    ask_levels: List[OrderBookLevelData]
    mid_price: float
    spread: float
    depth: float
    imbalance: float
    last_update: datetime


class OrderBookUpdate(BaseModel):
    """Order book update"""
    symbol: str
    update_type: OrderBookUpdateType
    side: Optional[OrderSide] = None
    price: Optional[float] = None
    size: Optional[float] = None
    old_size: Optional[float] = None
    timestamp: datetime


class OrderBookConfig(BaseModel):
    """Order book configuration"""
    symbol: str
    max_depth: int = 10
    update_frequency: int = 100  # milliseconds
    max_history: int = 10000
    enable_websocket: bool = True
    enable_analytics: bool = True
    price_precision: int = 2
    size_precision: int = 4
    minimum_order_size: float = 0.01


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OrderBookLevel:
    """Order book level"""
    price: float
    size: float
    order_count: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'price': self.price,
            'size': self.size,
            'order_count': self.order_count,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class OrderBookState:
    """Order book state"""
    symbol: str
    bid_levels: Dict[float, OrderBookLevel]
    ask_levels: Dict[float, OrderBookLevel]
    timestamp: datetime
    sequence_number: int
    status: OrderBookStatus


@dataclass
class OrderBookStats:
    """Order book statistics"""
    symbol: str
    timestamp: datetime
    mid_price: float
    spread: float
    bid_depth: float
    ask_depth: float
    total_depth: float
    imbalance: float
    weighted_bid: float
    weighted_ask: float
    bid_volume: float
    ask_volume: float
    spread_pct: float


# =============================================================================
# ORDER BOOK MANAGER
# =============================================================================

class OrderBookManager:
    """
    Advanced Order Book Manager with full API integration.
    
    Features:
    - Real-time order book tracking
    - Multiple depth levels (L1, L2, L3)
    - Order book analytics
    - WebSocket streaming
    - Snapshot management
    - Order book reconstruction
    - Depth visualization
    - Market impact analysis
    """

    def __init__(
        self,
        config: Optional[MarketMakingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None
    ):
        """
        Initialize OrderBookManager.
        
        Args:
            config: Market making configuration
            broker_factory: Factory for broker instances
        """
        self.config = config or MarketMakingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        
        # Order book states
        self._books: Dict[str, OrderBookState] = {}
        self._configs: Dict[str, OrderBookConfig] = {}
        
        # Snapshots and history
        self._snapshots: Dict[str, List[OrderBookSnapshot]] = defaultdict(list)
        self._updates: Dict[str, List[OrderBookUpdate]] = defaultdict(list)
        self._stats: Dict[str, List[OrderBookStats]] = defaultdict(list)
        
        # Subscription management
        self._subscribers: Dict[str, List[WebSocket]] = defaultdict(list)
        self._subscriber_patterns: Dict[str, List[WebSocket]] = defaultdict(list)
        
        # Monitoring
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Websocket manager
        self._ws_manager = WebSocketManager()
        
        logger.info("OrderBookManager initialized")

    # =========================================================================
    # Order Book Management
    # =========================================================================

    async def create_order_book(
        self,
        config: OrderBookConfig
    ) -> OrderBookSnapshot:
        """
        Create and initialize an order book.
        
        Args:
            config: Order book configuration
            
        Returns:
            OrderBookSnapshot: Initial snapshot
        """
        try:
            self._configs[config.symbol] = config
            
            # Get initial snapshot
            snapshot = await self._fetch_snapshot(config.symbol)
            
            # Initialize state
            self._books[config.symbol] = OrderBookState(
                symbol=config.symbol,
                bid_levels={},
                ask_levels={},
                timestamp=datetime.utcnow(),
                sequence_number=0,
                status=OrderBookStatus.ACTIVE
            )
            
            # Process snapshot
            await self._process_snapshot(config.symbol, snapshot)
            
            # Store snapshot
            self._snapshots[config.symbol].append(snapshot)
            
            logger.info(f"Order book created for {config.symbol}")
            return snapshot
            
        except Exception as e:
            logger.error(f"Error creating order book: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order book creation failed: {str(e)}"
            )

    async def _fetch_snapshot(self, symbol: str) -> OrderBookSnapshot:
        """Fetch order book snapshot from broker"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    snapshot = await broker.get_order_book(symbol)
                    if snapshot:
                        return self._parse_snapshot(symbol, snapshot)
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error fetching snapshot: {e}")
        
        # Return mock snapshot
        return self._generate_mock_snapshot(symbol)

    def _parse_snapshot(self, symbol: str, data: Dict[str, Any]) -> OrderBookSnapshot:
        """Parse broker snapshot data"""
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        bid_levels = []
        for level in bids[:10]:
            bid_levels.append(OrderBookLevelData(
                price=float(level[0]),
                size=float(level[1])
            ))
        
        ask_levels = []
        for level in asks[:10]:
            ask_levels.append(OrderBookLevelData(
                price=float(level[0]),
                size=float(level[1])
            ))
        
        # Calculate mid price and spread
        best_bid = bid_levels[0].price if bid_levels else 0
        best_ask = ask_levels[0].price if ask_levels else 0
        mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
        spread = best_ask - best_bid if best_ask > best_bid else 0
        
        # Calculate depth
        total_bid_depth = sum(l.size for l in bid_levels)
        total_ask_depth = sum(l.size for l in ask_levels)
        total_depth = total_bid_depth + total_ask_depth
        
        # Calculate imbalance
        imbalance = (total_bid_depth - total_ask_depth) / total_depth if total_depth > 0 else 0
        
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            mid_price=mid_price,
            spread=spread,
            depth=total_depth,
            imbalance=imbalance,
            last_update=datetime.utcnow()
        )

    def _generate_mock_snapshot(self, symbol: str) -> OrderBookSnapshot:
        """Generate mock order book snapshot"""
        base_price = 100.0
        
        bid_levels = []
        ask_levels = []
        
        for i in range(10):
            # Bid levels
            bid_price = base_price - (i + 1) * 0.01
            bid_size = np.random.uniform(1, 10)
            bid_levels.append(OrderBookLevelData(
                price=bid_price,
                size=bid_size
            ))
            
            # Ask levels
            ask_price = base_price + (i + 1) * 0.01
            ask_size = np.random.uniform(1, 10)
            ask_levels.append(OrderBookLevelData(
                price=ask_price,
                size=ask_size
            ))
        
        best_bid = bid_levels[0].price
        best_ask = ask_levels[0].price
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        
        total_bid_depth = sum(l.size for l in bid_levels)
        total_ask_depth = sum(l.size for l in ask_levels)
        total_depth = total_bid_depth + total_ask_depth
        imbalance = (total_bid_depth - total_ask_depth) / total_depth if total_depth > 0 else 0
        
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            mid_price=mid_price,
            spread=spread,
            depth=total_depth,
            imbalance=imbalance,
            last_update=datetime.utcnow()
        )

    async def _process_snapshot(
        self,
        symbol: str,
        snapshot: OrderBookSnapshot
    ) -> None:
        """Process order book snapshot"""
        if symbol not in self._books:
            return
        
        state = self._books[symbol]
        
        # Clear existing levels
        state.bid_levels.clear()
        state.ask_levels.clear()
        
        # Add new levels
        for level in snapshot.bid_levels:
            state.bid_levels[level.price] = OrderBookLevel(
                price=level.price,
                size=level.size,
                order_count=level.order_count or 1,
                timestamp=snapshot.timestamp
            )
        
        for level in snapshot.ask_levels:
            state.ask_levels[level.price] = OrderBookLevel(
                price=level.price,
                size=level.size,
                order_count=level.order_count or 1,
                timestamp=snapshot.timestamp
            )
        
        state.timestamp = snapshot.timestamp
        state.sequence_number += 1

    # =========================================================================
    # Order Book Updates
    # =========================================================================

    async def process_update(
        self,
        update: OrderBookUpdate
    ) -> Optional[OrderBookSnapshot]:
        """
        Process an order book update.
        
        Args:
            update: Order book update
            
        Returns:
            Optional[OrderBookSnapshot]: Updated snapshot if changed
        """
        if update.symbol not in self._books:
            return None
        
        state = self._books[update.symbol]
        
        if update.update_type == OrderBookUpdateType.SNAPSHOT:
            # Full snapshot
            snapshot = await self._fetch_snapshot(update.symbol)
            await self._process_snapshot(update.symbol, snapshot)
            return snapshot
            
        elif update.update_type == OrderBookUpdateType.UPDATE:
            # Single level update
            if update.side == OrderSide.BID:
                levels = state.bid_levels
            else:
                levels = state.ask_levels
            
            if update.price is not None:
                if update.size == 0:
                    # Remove level
                    if update.price in levels:
                        del levels[update.price]
                else:
                    # Add or update level
                    levels[update.price] = OrderBookLevel(
                        price=update.price,
                        size=update.size,
                        order_count=1,
                        timestamp=update.timestamp
                    )
            
            # Update sequence
            state.sequence_number += 1
            
            # Store update
            self._updates[update.symbol].append(update)
            
            # Create snapshot if significant change
            if len(self._updates[update.symbol]) % 10 == 0:
                snapshot = self._create_snapshot(update.symbol)
                self._snapshots[update.symbol].append(snapshot)
                return snapshot
            
        elif update.update_type == OrderBookUpdateType.DELETE:
            # Delete level
            if update.side == OrderSide.BID:
                levels = state.bid_levels
            else:
                levels = state.ask_levels
            
            if update.price in levels:
                del levels[update.price]
            
            state.sequence_number += 1
        
        elif update.update_type == OrderBookUpdateType.TRADE:
            # Trade occurred - update stats
            await self._update_stats(update.symbol)
        
        return None

    def _create_snapshot(self, symbol: str) -> OrderBookSnapshot:
        """Create snapshot from current state"""
        if symbol not in self._books:
            return None
        
        state = self._books[symbol]
        
        # Sort levels by price
        bid_levels = []
        for price, level in sorted(state.bid_levels.items(), reverse=True)[:10]:
            bid_levels.append(OrderBookLevelData(
                price=price,
                size=level.size,
                order_count=level.order_count,
                cumulative_size=sum(l.size for l in bid_levels) + level.size
            ))
        
        ask_levels = []
        for price, level in sorted(state.ask_levels.items())[:10]:
            ask_levels.append(OrderBookLevelData(
                price=price,
                size=level.size,
                order_count=level.order_count,
                cumulative_size=sum(l.size for l in ask_levels) + level.size
            ))
        
        best_bid = bid_levels[0].price if bid_levels else 0
        best_ask = ask_levels[0].price if ask_levels else 0
        mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
        spread = best_ask - best_bid if best_ask > best_bid else 0
        
        total_bid_depth = sum(l.size for l in bid_levels)
        total_ask_depth = sum(l.size for l in ask_levels)
        total_depth = total_bid_depth + total_ask_depth
        imbalance = (total_bid_depth - total_ask_depth) / total_depth if total_depth > 0 else 0
        
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            mid_price=mid_price,
            spread=spread,
            depth=total_depth,
            imbalance=imbalance,
            last_update=datetime.utcnow()
        )

    # =========================================================================
    # Stats and Analytics
    # =========================================================================

    async def _update_stats(self, symbol: str) -> None:
        """Update order book statistics"""
        if symbol not in self._books:
            return
        
        snapshot = self._create_snapshot(symbol)
        if not snapshot:
            return
        
        # Calculate stats
        stats = OrderBookStats(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            mid_price=snapshot.mid_price,
            spread=snapshot.spread,
            bid_depth=sum(l.size for l in snapshot.bid_levels),
            ask_depth=sum(l.size for l in snapshot.ask_levels),
            total_depth=snapshot.depth,
            imbalance=snapshot.imbalance,
            weighted_bid=self._calculate_weighted_price(snapshot.bid_levels),
            weighted_ask=self._calculate_weighted_price(snapshot.ask_levels),
            bid_volume=sum(l.size * l.price for l in snapshot.bid_levels),
            ask_volume=sum(l.size * l.price for l in snapshot.ask_levels),
            spread_pct=snapshot.spread / snapshot.mid_price if snapshot.mid_price > 0 else 0
        )
        
        self._stats[symbol].append(stats)
        
        # Keep history limited
        if len(self._stats[symbol]) > 1000:
            self._stats[symbol] = self._stats[symbol][-1000:]

    def _calculate_weighted_price(
        self,
        levels: List[OrderBookLevelData]
    ) -> float:
        """Calculate weighted average price"""
        if not levels:
            return 0
        
        total_size = sum(l.size for l in levels)
        if total_size == 0:
            return 0
        
        weighted_sum = sum(l.size * l.price for l in levels)
        return weighted_sum / total_size

    def get_stats(self, symbol: str, limit: int = 100) -> List[OrderBookStats]:
        """
        Get order book statistics.
        
        Args:
            symbol: Symbol
            limit: Number of stats to return
            
        Returns:
            List[OrderBookStats]: Statistics
        """
        stats = self._stats.get(symbol, [])
        return stats[-limit:] if stats else []

    # =========================================================================
    # Depth and Liquidity
    # =========================================================================

    def get_depth(
        self,
        symbol: str,
        side: Optional[OrderSide] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get order book depth.
        
        Args:
            symbol: Symbol
            side: Bid or ask (None for both)
            limit: Number of levels
            
        Returns:
            Dict[str, Any]: Depth data
        """
        if symbol not in self._books:
            return {}
        
        state = self._books[symbol]
        result = {}
        
        if side is None or side == OrderSide.BID:
            bids = sorted(state.bid_levels.items(), reverse=True)[:limit]
            result['bids'] = [
                {'price': price, 'size': level.size}
                for price, level in bids
            ]
        
        if side is None or side == OrderSide.ASK:
            asks = sorted(state.ask_levels.items())[:limit]
            result['asks'] = [
                {'price': price, 'size': level.size}
                for price, level in asks
            ]
        
        return result

    def get_liquidity(self, symbol: str, depth: float = 0.01) -> Dict[str, float]:
        """
        Get liquidity at a given depth.
        
        Args:
            symbol: Symbol
            depth: Depth percentage (0.01 = 1%)
            
        Returns:
            Dict[str, float]: Liquidity data
        """
        if symbol not in self._books:
            return {}
        
        state = self._books[symbol]
        
        # Get mid price
        best_bid = max(state.bid_levels.keys()) if state.bid_levels else 0
        best_ask = min(state.ask_levels.keys()) if state.ask_levels else 0
        mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
        
        if mid_price == 0:
            return {}
        
        threshold = mid_price * depth
        
        bid_liquidity = 0
        ask_liquidity = 0
        
        for price, level in state.bid_levels.items():
            if mid_price - price <= threshold:
                bid_liquidity += level.size
        
        for price, level in state.ask_levels.items():
            if price - mid_price <= threshold:
                ask_liquidity += level.size
        
        return {
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity,
            'total_liquidity': bid_liquidity + ask_liquidity,
            'mid_price': mid_price,
            'depth_threshold': threshold
        }

    def get_imbalance(self, symbol: str) -> float:
        """
        Get order book imbalance.
        
        Args:
            symbol: Symbol
            
        Returns:
            float: Imbalance (-1 to 1)
        """
        if symbol not in self._books:
            return 0
        
        state = self._books[symbol]
        
        bid_depth = sum(level.size for level in state.bid_levels.values())
        ask_depth = sum(level.size for level in state.ask_levels.values())
        total_depth = bid_depth + ask_depth
        
        if total_depth == 0:
            return 0
        
        return (bid_depth - ask_depth) / total_depth

    # =========================================================================
    # Order Book Reconstruction
    # =========================================================================

    def reconstruct_book(
        self,
        symbol: str,
        timestamp: datetime
    ) -> Optional[OrderBookSnapshot]:
        """
        Reconstruct order book at a given timestamp.
        
        Args:
            symbol: Symbol
            timestamp: Desired timestamp
            
        Returns:
            Optional[OrderBookSnapshot]: Reconstructed snapshot
        """
        if symbol not in self._snapshots:
            return None
        
        # Find closest snapshot
        snapshots = self._snapshots[symbol]
        closest = min(snapshots, key=lambda s: abs((s.timestamp - timestamp).total_seconds()))
        
        # Apply updates after snapshot
        updates = [
            u for u in self._updates.get(symbol, [])
            if closest.timestamp < u.timestamp <= timestamp
        ]
        
        # Start from snapshot
        bid_levels = {l.price: l.size for l in closest.bid_levels}
        ask_levels = {l.price: l.size for l in closest.ask_levels}
        
        for update in updates:
            if update.side == OrderSide.BID:
                if update.update_type == OrderBookUpdateType.UPDATE:
                    if update.size == 0:
                        bid_levels.pop(update.price, None)
                    else:
                        bid_levels[update.price] = update.size
            else:
                if update.update_type == OrderBookUpdateType.UPDATE:
                    if update.size == 0:
                        ask_levels.pop(update.price, None)
                    else:
                        ask_levels[update.price] = update.size
        
        # Create snapshot
        bid_level_data = [
            OrderBookLevelData(price=p, size=s)
            for p, s in sorted(bid_levels.items(), reverse=True)[:10]
        ]
        ask_level_data = [
            OrderBookLevelData(price=p, size=s)
            for p, s in sorted(ask_levels.items())[:10]
        ]
        
        best_bid = bid_level_data[0].price if bid_level_data else 0
        best_ask = ask_level_data[0].price if ask_level_data else 0
        
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp=timestamp,
            bid_levels=bid_level_data,
            ask_levels=ask_level_data,
            mid_price=(best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0,
            spread=best_ask - best_bid if best_ask > best_bid else 0,
            depth=sum(l.size for l in bid_level_data) + sum(l.size for l in ask_level_data),
            imbalance=0,
            last_update=timestamp
        )

    # =========================================================================
    # WebSocket Support
    # =========================================================================

    async def subscribe(
        self,
        websocket: WebSocket,
        symbol: str,
        levels: int = 10
    ) -> None:
        """
        Subscribe to order book updates.
        
        Args:
            websocket: WebSocket connection
            symbol: Symbol
            levels: Number of levels
        """
        await self._ws_manager.connect(websocket)
        
        # Send initial snapshot
        if symbol in self._books:
            snapshot = self._create_snapshot(symbol)
            if snapshot:
                await self._ws_manager.send_json({
                    'type': 'snapshot',
                    'symbol': symbol,
                    'data': snapshot.dict()
                })
        
        # Add to subscribers
        self._subscribers[symbol].append(websocket)
        
        try:
            while True:
                # Keep connection alive
                try:
                    data = await websocket.receive_text()
                    if data == 'ping':
                        await websocket.send_text('pong')
                except WebSocketDisconnect:
                    break
        finally:
            # Remove subscriber
            if symbol in self._subscribers:
                self._subscribers[symbol].remove(websocket)
            await self._ws_manager.disconnect(websocket)

    async def broadcast_update(self, update: OrderBookUpdate) -> None:
        """
        Broadcast order book update to subscribers.
        
        Args:
            update: Order book update
        """
        if update.symbol not in self._subscribers:
            return
        
        message = {
            'type': 'update',
            'symbol': update.symbol,
            'data': update.dict()
        }
        
        for subscriber in self._subscribers[update.symbol]:
            try:
                await self._ws_manager.send_json(message, subscriber)
            except Exception as e:
                logger.warning(f"Error broadcasting to subscriber: {e}")

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start order book monitoring"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Order book monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop order book monitoring"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        # Close WebSocket connections
        await self._ws_manager.close_all()
        logger.info("Order book monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_running:
            try:
                for symbol in list(self._books.keys()):
                    # Refresh order book
                    snapshot = await self._fetch_snapshot(symbol)
                    await self._process_snapshot(symbol, snapshot)
                    
                    # Update stats
                    await self._update_stats(symbol)
                    
                    # Broadcast update
                    update = OrderBookUpdate(
                        symbol=symbol,
                        update_type=OrderBookUpdateType.SNAPSHOT,
                        timestamp=datetime.utcnow()
                    )
                    await self.broadcast_update(update)
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the order book manager"""
        await self.stop_monitoring()
        
        self._books.clear()
        self._configs.clear()
        self._snapshots.clear()
        self._updates.clear()
        self._stats.clear()
        self._subscribers.clear()
        
        logger.info("OrderBookManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/order-book", tags=["Order Book"])


async def get_manager() -> OrderBookManager:
    """Dependency to get OrderBookManager instance"""
    return OrderBookManager()


@router.post("/create")
async def create_order_book(
    config: OrderBookConfig,
    manager: OrderBookManager = Depends(get_manager)
):
    """Create an order book"""
    return await manager.create_order_book(config)


@router.get("/{symbol}")
async def get_order_book(
    symbol: str,
    levels: int = Query(10, le=50),
    manager: OrderBookManager = Depends(get_manager)
):
    """Get order book data"""
    depth = manager.get_depth(symbol, limit=levels)
    if not depth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order book for {symbol} not found"
        )
    return depth


@router.get("/{symbol}/stats")
async def get_order_book_stats(
    symbol: str,
    limit: int = Query(100, le=1000),
    manager: OrderBookManager = Depends(get_manager)
):
    """Get order book statistics"""
    return manager.get_stats(symbol, limit)


@router.get("/{symbol}/liquidity")
async def get_liquidity(
    symbol: str,
    depth: float = Query(0.01, ge=0, le=0.1),
    manager: OrderBookManager = Depends(get_manager)
):
    """Get liquidity at depth"""
    return manager.get_liquidity(symbol, depth)


@router.get("/{symbol}/imbalance")
async def get_imbalance(
    symbol: str,
    manager: OrderBookManager = Depends(get_manager)
):
    """Get order book imbalance"""
    return {'imbalance': manager.get_imbalance(symbol)}


@router.websocket("/ws/{symbol}")
async def order_book_websocket(
    websocket: WebSocket,
    symbol: str,
    levels: int = Query(10, le=50),
    manager: OrderBookManager = Depends(get_manager)
):
    """WebSocket endpoint for order book data"""
    await manager.subscribe(websocket, symbol, levels)


@router.post("/{symbol}/update")
async def process_update(
    symbol: str,
    update: OrderBookUpdate,
    manager: OrderBookManager = Depends(get_manager)
):
    """Process an order book update"""
    snapshot = await manager.process_update(update)
    return {'success': True, 'snapshot': snapshot}


@router.post("/monitor/start")
async def start_monitoring(
    manager: OrderBookManager = Depends(get_manager)
):
    """Start order book monitoring"""
    await manager.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_monitoring(
    manager: OrderBookManager = Depends(get_manager)
):
    """Stop order book monitoring"""
    await manager.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OrderBookManager',
    'OrderBookLevel',
    'OrderBookState',
    'OrderBookStats',
    'OrderBookLevelData',
    'OrderBookSnapshot',
    'OrderBookUpdate',
    'OrderBookConfig',
    'OrderBookLevel',
    'OrderSide',
    'OrderBookStatus',
    'OrderBookUpdateType',
    'router'
]
