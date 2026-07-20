# trading/bots/arbitrage_bot/models/depth.py
# NEXUS AI TRADING SYSTEM - ORDER BOOK DEPTH MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for order book depth, liquidity analysis,
# market impact estimation, and order book dynamics for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Order Book Depth Models

This module provides comprehensive data models for:
- Order book depth analysis and visualization
- Liquidity measurement and scoring
- Market impact estimation
- Order book dynamics and update tracking
- Depth of market (DOM) analysis
- Cumulative volume analysis
- Imbalance detection and analysis
- Support and resistance level identification
- Order flow analysis
- Spoofing and manipulation detection
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
import bisect
from collections import deque

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class OrderBookSide(str, Enum):
    """Order book sides."""
    BID = "bid"
    ASK = "ask"


class OrderType(str, Enum):
    """Types of orders in the order book."""
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"


class OrderStatus(str, Enum):
    """Order statuses."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class DepthUpdateType(str, Enum):
    """Types of depth updates."""
    SNAPSHOT = "snapshot"
    DELTA = "delta"
    FULL = "full"


class LiquidityType(str, Enum):
    """Types of liquidity."""
    ACTIVE = "active"
    PASSIVE = "passive"
    DEEP = "deep"
    SHALLOW = "shallow"
    THIN = "thin"
    THICK = "thick"
    IMBALANCED = "imbalanced"


class MarketImpactType(str, Enum):
    """Types of market impact."""
    PRICE_IMPACT = "price_impact"
    SLIPPAGE_IMPACT = "slippage_impact"
    VOLUME_IMPACT = "volume_impact"
    SPREAD_IMPACT = "spread_impact"
    DEPTH_IMPACT = "depth_impact"


# ====================================================================================
# ORDER BOOK DEPTH MODELS
# ====================================================================================

@dataclass
class OrderBookLevel:
    """
    Single level in the order book (price + quantity).
    """
    price: float = 0.0
    quantity: float = 0.0
    side: Optional[OrderBookSide] = None
    order_count: int = 0
    orders: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate and format."""
        self.price = round(self.price, 8)
        self.quantity = round(self.quantity, 8)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side.value if self.side else None,
            "order_count": self.order_count,
            "orders": self.orders
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderBookLevel":
        """Create from dictionary."""
        return cls(
            price=data.get("price", 0.0),
            quantity=data.get("quantity", 0.0),
            side=OrderBookSide(data["side"]) if data.get("side") else None,
            order_count=data.get("order_count", 0),
            orders=data.get("orders", [])
        )
        
    def is_empty(self) -> bool:
        """Check if level is empty."""
        return self.quantity == 0
        
    def get_value(self) -> float:
        """Get the value at this level (price * quantity)."""
        return self.price * self.quantity


@dataclass
class OrderBookDepth:
    """
    Complete order book depth data.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    
    # Metadata
    sequence_id: int = 0
    last_update_id: int = 0
    received_at: datetime = field(default_factory=datetime.utcnow)
    snapshot_time: datetime = field(default_factory=datetime.utcnow)
    update_type: DepthUpdateType = DepthUpdateType.SNAPSHOT
    
    # Derived metrics
    bid_count: int = 0
    ask_count: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0
    spread: float = 0.0
    mid_price: float = 0.0
    
    # Cumulative metrics
    cumulative_bid_volume: float = 0.0
    cumulative_ask_volume: float = 0.0
    total_volume: float = 0.0
    
    # Imbalance metrics
    volume_imbalance: float = 0.0
    order_imbalance: float = 0.0
    spread_imbalance: float = 0.0
    
    # Liquidity metrics
    liquidity_score: float = 0.0
    depth_score: float = 0.0
    market_depth: Dict[str, float] = field(default_factory=dict)
    
    # Price levels
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    
    # Market impact
    estimated_impact: Dict[str, float] = field(default_factory=dict)
    
    # Raw data (for debugging)
    raw_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Calculate derived metrics after initialization."""
        self._calculate_derived_metrics()
        
    def _calculate_derived_metrics(self) -> None:
        """Calculate all derived metrics."""
        # Count levels
        self.bid_count = len(self.bids)
        self.ask_count = len(self.asks)
        
        # Best bid/ask
        if self.bids:
            self.best_bid = self.bids[0].price if self.bids else 0.0
        if self.asks:
            self.best_ask = self.asks[0].price if self.asks else 0.0
            
        # Spread and mid price
        self.spread = self.best_ask - self.best_bid if self.best_ask and self.best_bid else 0.0
        self.mid_price = (self.best_ask + self.best_bid) / 2 if self.best_ask and self.best_bid else 0.0
        
        # Cumulative volumes
        self.cumulative_bid_volume = sum(level.quantity for level in self.bids)
        self.cumulative_ask_volume = sum(level.quantity for level in self.asks)
        self.total_volume = self.cumulative_bid_volume + self.cumulative_ask_volume
        
        # Volume imbalance
        if self.total_volume > 0:
            self.volume_imbalance = (self.cumulative_bid_volume - self.cumulative_ask_volume) / self.total_volume
        else:
            self.volume_imbalance = 0.0
            
        # Order imbalance
        total_orders = self.bid_count + self.ask_count
        if total_orders > 0:
            self.order_imbalance = (self.bid_count - self.ask_count) / total_orders
        else:
            self.order_imbalance = 0.0
            
        # Spread imbalance
        if self.best_bid and self.best_ask:
            self.spread_imbalance = (self.best_ask - self.best_bid) / self.mid_price
        else:
            self.spread_imbalance = 0.0
            
        # Liquidity score
        self._calculate_liquidity_score()
        
        # Depth metrics
        self._calculate_depth_metrics()
        
        # Support and resistance levels
        self._identify_support_resistance()
        
        # Market impact
        self._calculate_market_impact()
        
    def _calculate_liquidity_score(self) -> None:
        """Calculate liquidity score based on depth and spread."""
        if self.best_bid == 0 or self.best_ask == 0:
            self.liquidity_score = 0.0
            return
            
        # Normalized spread (invert so lower spread = higher score)
        normalized_spread = 1.0 / (1.0 + self.spread / self.mid_price)
        
        # Normalized depth
        total_value = 0.0
        levels_to_consider = min(10, max(self.bid_count, self.ask_count))
        
        for i in range(levels_to_consider):
            if i < self.bid_count:
                total_value += self.bids[i].get_value()
            if i < self.ask_count:
                total_value += self.asks[i].get_value()
                
        # Normalize depth by mid price
        normalized_depth = total_value / (self.mid_price * (1 + self.spread / self.mid_price))
        normalized_depth = min(1.0, normalized_depth / 1000000)  # Cap at 1M USD equivalent
        
        # Combine scores
        self.liquidity_score = (normalized_spread * 0.4 + normalized_depth * 0.6)
        
    def _calculate_depth_metrics(self) -> None:
        """Calculate depth metrics at various price levels."""
        if not self.bids or not self.asks:
            return
            
        # Depth at 1%, 2%, 5%, 10% from mid price
        percentages = [0.01, 0.02, 0.05, 0.10]
        self.market_depth = {}
        
        for pct in percentages:
            # Bid depth
            bid_price_limit = self.mid_price * (1 - pct)
            bid_volume = 0.0
            for level in self.bids:
                if level.price >= bid_price_limit:
                    bid_volume += level.quantity
                else:
                    break
                    
            # Ask depth
            ask_price_limit = self.mid_price * (1 + pct)
            ask_volume = 0.0
            for level in self.asks:
                if level.price <= ask_price_limit:
                    ask_volume += level.quantity
                else:
                    break
                    
            self.market_depth[f"bid_{pct*100:.0f}pct"] = bid_volume
            self.market_depth[f"ask_{pct*100:.0f}pct"] = ask_volume
            self.market_depth[f"total_{pct*100:.0f}pct"] = bid_volume + ask_volume
            
        # Depth score (weighted average of 1% and 5% depth)
        total_1pct = self.market_depth.get("total_1pct", 0.0)
        total_5pct = self.market_depth.get("total_5pct", 0.0)
        self.depth_score = (total_1pct * 0.7 + total_5pct * 0.3) / (self.mid_price or 1.0)
        
    def _identify_support_resistance(self) -> None:
        """Identify support and resistance levels from order book."""
        self.support_levels = []
        self.resistance_levels = []
        
        if not self.bids or not self.asks:
            return
            
        # Support levels from bid side
        bid_cumulative = 0.0
        for level in self.bids:
            bid_cumulative += level.quantity
            if bid_cumulative > sum(l.quantity for l in self.bids) * 0.1:
                self.support_levels.append(level.price)
                break
                
        # More support levels at price clusters
        bid_prices = [l.price for l in self.bids[:5]]
        if len(bid_prices) > 1:
            avg_gap = sum(abs(bid_prices[i] - bid_prices[i+1]) for i in range(len(bid_prices)-1)) / (len(bid_prices)-1)
            if avg_gap < self.mid_price * 0.001:
                self.support_levels.append(bid_prices[-1])
                
        # Resistance levels from ask side
        ask_cumulative = 0.0
        for level in self.asks:
            ask_cumulative += level.quantity
            if ask_cumulative > sum(l.quantity for l in self.asks) * 0.1:
                self.resistance_levels.append(level.price)
                break
                
        # More resistance levels at price clusters
        ask_prices = [l.price for l in self.asks[:5]]
        if len(ask_prices) > 1:
            avg_gap = sum(abs(ask_prices[i] - ask_prices[i+1]) for i in range(len(ask_prices)-1)) / (len(ask_prices)-1)
            if avg_gap < self.mid_price * 0.001:
                self.resistance_levels.append(ask_prices[-1])
                
    def _calculate_market_impact(self) -> None:
        """Calculate estimated market impact for various order sizes."""
        self.estimated_impact = {}
        
        # Impact for 1%, 5%, 10%, 25%, 50% of total volume
        percentages = [0.01, 0.05, 0.10, 0.25, 0.50]
        
        for pct in percentages:
            # Bid impact (buy)
            bid_impact = self._calculate_buy_impact(pct)
            # Ask impact (sell)
            ask_impact = self._calculate_sell_impact(pct)
            
            self.estimated_impact[f"buy_{pct*100:.0f}pct"] = bid_impact
            self.estimated_impact[f"sell_{pct*100:.0f}pct"] = ask_impact
            self.estimated_impact[f"avg_{pct*100:.0f}pct"] = (bid_impact + ask_impact) / 2
            
    def _calculate_buy_impact(self, percentage: float) -> float:
        """
        Calculate price impact for a buy order of given percentage of depth.
        
        Args:
            percentage: Percentage of total depth to buy
            
        Returns:
            Estimated price impact
        """
        if not self.asks:
            return 0.0
            
        target_volume = self.cumulative_ask_volume * percentage
        cumulative_volume = 0.0
        weighted_price = 0.0
        
        for level in self.asks:
            if cumulative_volume + level.quantity >= target_volume:
                remaining = target_volume - cumulative_volume
                weighted_price += level.price * remaining
                cumulative_volume = target_volume
                break
            else:
                weighted_price += level.price * level.quantity
                cumulative_volume += level.quantity
                
        if cumulative_volume > 0:
            avg_price = weighted_price / cumulative_volume
            return (avg_price - self.mid_price) / self.mid_price
        return 0.0
        
    def _calculate_sell_impact(self, percentage: float) -> float:
        """
        Calculate price impact for a sell order of given percentage of depth.
        
        Args:
            percentage: Percentage of total depth to sell
            
        Returns:
            Estimated price impact
        """
        if not self.bids:
            return 0.0
            
        target_volume = self.cumulative_bid_volume * percentage
        cumulative_volume = 0.0
        weighted_price = 0.0
        
        for level in self.bids:
            if cumulative_volume + level.quantity >= target_volume:
                remaining = target_volume - cumulative_volume
                weighted_price += level.price * remaining
                cumulative_volume = target_volume
                break
            else:
                weighted_price += level.price * level.quantity
                cumulative_volume += level.quantity
                
        if cumulative_volume > 0:
            avg_price = weighted_price / cumulative_volume
            return (self.mid_price - avg_price) / self.mid_price
        return 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "sequence_id": self.sequence_id,
            "last_update_id": self.last_update_id,
            "received_at": self.received_at.isoformat(),
            "snapshot_time": self.snapshot_time.isoformat(),
            "update_type": self.update_type.value if self.update_type else None,
            "bid_count": self.bid_count,
            "ask_count": self.ask_count,
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "spread": self.spread,
            "mid_price": self.mid_price,
            "cumulative_bid_volume": self.cumulative_bid_volume,
            "cumulative_ask_volume": self.cumulative_ask_volume,
            "total_volume": self.total_volume,
            "volume_imbalance": self.volume_imbalance,
            "order_imbalance": self.order_imbalance,
            "spread_imbalance": self.spread_imbalance,
            "liquidity_score": self.liquidity_score,
            "depth_score": self.depth_score,
            "market_depth": self.market_depth,
            "support_levels": self.support_levels,
            "resistance_levels": self.resistance_levels,
            "estimated_impact": self.estimated_impact
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderBookDepth":
        """Create from dictionary."""
        depth = cls(
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            bids=[OrderBookLevel.from_dict(l) for l in data.get("bids", [])],
            asks=[OrderBookLevel.from_dict(l) for l in data.get("asks", [])],
            sequence_id=data.get("sequence_id", 0),
            last_update_id=data.get("last_update_id", 0),
            update_type=DepthUpdateType(data["update_type"]) if data.get("update_type") else DepthUpdateType.SNAPSHOT,
            raw_data=data.get("raw_data")
        )
        
        # Parse timestamps
        if data.get("received_at"):
            depth.received_at = datetime.fromisoformat(data["received_at"])
        if data.get("snapshot_time"):
            depth.snapshot_time = datetime.fromisoformat(data["snapshot_time"])
            
        depth._calculate_derived_metrics()
        return depth
        
    def apply_delta(self, bids_delta: List[Tuple[float, float]], asks_delta: List[Tuple[float, float]]) -> "OrderBookDepth":
        """
        Apply delta updates to the order book.
        
        Args:
            bids_delta: List of (price, quantity) for bid updates
            asks_delta: List of (price, quantity) for ask updates
            
        Returns:
            Updated OrderBookDepth instance
        """
        # Create copy of current depth
        new_depth = OrderBookDepth(
            symbol=self.symbol,
            exchange=self.exchange,
            bids=[OrderBookLevel(price=l.price, quantity=l.quantity, order_count=l.order_count) for l in self.bids],
            asks=[OrderBookLevel(price=l.price, quantity=l.quantity, order_count=l.order_count) for l in self.asks],
            sequence_id=self.sequence_id + 1,
            last_update_id=self.last_update_id,
            received_at=datetime.utcnow(),
            snapshot_time=self.snapshot_time,
            update_type=DepthUpdateType.DELTA
        )
        
        # Apply bid deltas
        for price, quantity in bids_delta:
            self._apply_level_delta(new_depth.bids, price, quantity, side=OrderBookSide.BID)
            
        # Apply ask deltas
        for price, quantity in asks_delta:
            self._apply_level_delta(new_depth.asks, price, quantity, side=OrderBookSide.ASK)
            
        # Recalculate derived metrics
        new_depth._calculate_derived_metrics()
        
        return new_depth
        
    def _apply_level_delta(self, levels: List[OrderBookLevel], price: float, quantity: float, side: OrderBookSide) -> None:
        """Apply a delta update to a list of levels."""
        price = round(price, 8)
        quantity = round(quantity, 8)
        
        # Find existing level
        for i, level in enumerate(levels):
            if level.price == price:
                if quantity == 0:
                    # Remove level
                    levels.pop(i)
                else:
                    # Update level
                    level.quantity = quantity
                return
                
        # New level
        if quantity > 0:
            new_level = OrderBookLevel(price=price, quantity=quantity, side=side)
            # Insert maintaining sorted order
            if side == OrderBookSide.BID:
                # Bids: descending order
                bisect.insort(levels, new_level, key=lambda x: -x.price)
            else:
                # Asks: ascending order
                bisect.insort(levels, new_level, key=lambda x: x.price)
                
    def get_level_by_price(self, price: float, side: OrderBookSide) -> Optional[OrderBookLevel]:
        """Get level at specific price."""
        levels = self.bids if side == OrderBookSide.BID else self.asks
        price = round(price, 8)
        
        for level in levels:
            if level.price == price:
                return level
        return None
        
    def get_volume_at_price(self, price: float, side: OrderBookSide) -> float:
        """Get volume at specific price."""
        level = self.get_level_by_price(price, side)
        return level.quantity if level else 0.0
        
    def get_volume_up_to_price(self, price: float, side: OrderBookSide) -> float:
        """Get cumulative volume up to a specific price."""
        levels = self.bids if side == OrderBookSide.BID else self.asks
        total = 0.0
        
        for level in levels:
            if side == OrderBookSide.BID:
                if level.price >= price:
                    total += level.quantity
                else:
                    break
            else:
                if level.price <= price:
                    total += level.quantity
                else:
                    break
                    
        return total
        
    def get_avg_price_for_volume(self, volume: float, side: OrderBookSide) -> float:
        """Get average price for a given volume."""
        levels = self.bids if side == OrderBookSide.BID else self.asks
        cumulative_volume = 0.0
        weighted_price = 0.0
        
        for level in levels:
            if cumulative_volume + level.quantity >= volume:
                remaining = volume - cumulative_volume
                weighted_price += level.price * remaining
                cumulative_volume = volume
                break
            else:
                weighted_price += level.price * level.quantity
                cumulative_volume += level.quantity
                
        if cumulative_volume > 0:
            return weighted_price / cumulative_volume
        return 0.0


# ====================================================================================
# LIQUIDITY ANALYSIS MODELS
# ====================================================================================

@dataclass
class LiquidityAnalysis:
    """
    Comprehensive liquidity analysis for a symbol.
    """
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Liquidity metrics
    bid_liquidity: float = 0.0
    ask_liquidity: float = 0.0
    total_liquidity: float = 0.0
    liquidity_ratio: float = 0.0
    
    # Depth metrics
    depth_1pct: float = 0.0
    depth_2pct: float = 0.0
    depth_5pct: float = 0.0
    depth_10pct: float = 0.0
    
    # Spread metrics
    spread: float = 0.0
    spread_bps: float = 0.0
    spread_percentage: float = 0.0
    
    # Imbalance metrics
    volume_imbalance: float = 0.0
    order_imbalance: float = 0.0
    pressure: str = "neutral"  # buy, sell, neutral
    
    # Quality metrics
    liquidity_score: float = 0.0
    depth_score: float = 0.0
    quality_score: float = 0.0
    
    # Rankings
    global_rank: Optional[int] = None
    exchange_rank: Optional[int] = None
    peer_rank: Optional[int] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "bid_liquidity": self.bid_liquidity,
            "ask_liquidity": self.ask_liquidity,
            "total_liquidity": self.total_liquidity,
            "liquidity_ratio": self.liquidity_ratio,
            "depth_1pct": self.depth_1pct,
            "depth_2pct": self.depth_2pct,
            "depth_5pct": self.depth_5pct,
            "depth_10pct": self.depth_10pct,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "spread_percentage": self.spread_percentage,
            "volume_imbalance": self.volume_imbalance,
            "order_imbalance": self.order_imbalance,
            "pressure": self.pressure,
            "liquidity_score": self.liquidity_score,
            "depth_score": self.depth_score,
            "quality_score": self.quality_score,
            "global_rank": self.global_rank,
            "exchange_rank": self.exchange_rank,
            "peer_rank": self.peer_rank,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_order_book(cls, depth: OrderBookDepth) -> "LiquidityAnalysis":
        """Create liquidity analysis from order book depth."""
        analysis = cls(
            symbol=depth.symbol,
            exchange=depth.exchange,
            timestamp=depth.received_at
        )
        
        # Liquidity metrics
        analysis.bid_liquidity = depth.cumulative_bid_volume
        analysis.ask_liquidity = depth.cumulative_ask_volume
        analysis.total_liquidity = depth.total_volume
        analysis.liquidity_ratio = analysis.bid_liquidity / analysis.ask_liquidity if analysis.ask_liquidity > 0 else 1.0
        
        # Depth metrics
        analysis.depth_1pct = depth.market_depth.get("total_1pct", 0.0)
        analysis.depth_2pct = depth.market_depth.get("total_2pct", 0.0)
        analysis.depth_5pct = depth.market_depth.get("total_5pct", 0.0)
        analysis.depth_10pct = depth.market_depth.get("total_10pct", 0.0)
        
        # Spread metrics
        analysis.spread = depth.spread
        if depth.mid_price > 0:
            analysis.spread_bps = (depth.spread / depth.mid_price) * 10000
            analysis.spread_percentage = (depth.spread / depth.mid_price) * 100
            
        # Imbalance metrics
        analysis.volume_imbalance = depth.volume_imbalance
        analysis.order_imbalance = depth.order_imbalance
        
        if analysis.volume_imbalance > 0.1:
            analysis.pressure = "buy"
        elif analysis.volume_imbalance < -0.1:
            analysis.pressure = "sell"
        else:
            analysis.pressure = "neutral"
            
        # Quality metrics
        analysis.liquidity_score = depth.liquidity_score
        analysis.depth_score = depth.depth_score
        analysis.quality_score = (analysis.liquidity_score * 0.4 + analysis.depth_score * 0.3 + 
                                 (1 - abs(analysis.volume_imbalance)) * 0.3)
                                 
        return analysis


# ====================================================================================
# ORDER FLOW MODELS
# ====================================================================================

@dataclass
class OrderFlow:
    """
    Order flow analysis model.
    """
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Bid flow
    bid_volume: float = 0.0
    bid_count: int = 0
    bid_value: float = 0.0
    bid_weighted_price: float = 0.0
    
    # Ask flow
    ask_volume: float = 0.0
    ask_count: int = 0
    ask_value: float = 0.0
    ask_weighted_price: float = 0.0
    
    # Net flow
    net_volume: float = 0.0
    net_value: float = 0.0
    net_flow: float = 0.0
    flow_imbalance: float = 0.0
    
    # Order types
    market_buy_count: int = 0
    market_sell_count: int = 0
    limit_buy_count: int = 0
    limit_sell_count: int = 0
    
    # Aggression
    buy_aggression: float = 0.0
    sell_aggression: float = 0.0
    net_aggression: float = 0.0
    
    # Pressure
    pressure: str = "neutral"  # buy, sell, neutral
    pressure_strength: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "bid_volume": self.bid_volume,
            "bid_count": self.bid_count,
            "bid_value": self.bid_value,
            "bid_weighted_price": self.bid_weighted_price,
            "ask_volume": self.ask_volume,
            "ask_count": self.ask_count,
            "ask_value": self.ask_value,
            "ask_weighted_price": self.ask_weighted_price,
            "net_volume": self.net_volume,
            "net_value": self.net_value,
            "net_flow": self.net_flow,
            "flow_imbalance": self.flow_imbalance,
            "market_buy_count": self.market_buy_count,
            "market_sell_count": self.market_sell_count,
            "limit_buy_count": self.limit_buy_count,
            "limit_sell_count": self.limit_sell_count,
            "buy_aggression": self.buy_aggression,
            "sell_aggression": self.sell_aggression,
            "net_aggression": self.net_aggression,
            "pressure": self.pressure,
            "pressure_strength": self.pressure_strength,
            "metadata": self.metadata
        }


# ====================================================================================
# DEPTH SNAPSHOT MODELS
# ====================================================================================

@dataclass
class DepthSnapshot:
    """
    Historical snapshot of order book depth.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    depth: OrderBookDepth = field(default_factory=OrderBookDepth)
    analysis: Optional[LiquidityAnalysis] = None
    
    # Metadata
    snapshot_type: str = "full"  # full, delta, compressed
    compression_ratio: float = 1.0
    raw_size: int = 0
    compressed_size: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "depth": self.depth.to_dict() if self.depth else None,
            "analysis": self.analysis.to_dict() if self.analysis else None,
            "snapshot_type": self.snapshot_type,
            "compression_ratio": self.compression_ratio,
            "raw_size": self.raw_size,
            "compressed_size": self.compressed_size
        }


# ====================================================================================
# DEPTH STATISTICS MODELS
# ====================================================================================

@dataclass
class DepthStatistics:
    """
    Statistical analysis of order book depth over time.
    """
    symbol: str = ""
    exchange: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Basic statistics
    avg_depth: float = 0.0
    max_depth: float = 0.0
    min_depth: float = 0.0
    median_depth: float = 0.0
    std_dev_depth: float = 0.0
    
    # Spread statistics
    avg_spread: float = 0.0
    max_spread: float = 0.0
    min_spread: float = 0.0
    median_spread: float = 0.0
    std_dev_spread: float = 0.0
    
    # Imbalance statistics
    avg_imbalance: float = 0.0
    max_imbalance: float = 0.0
    min_imbalance: float = 0.0
    std_dev_imbalance: float = 0.0
    
    # Liquidity statistics
    avg_liquidity_score: float = 0.0
    max_liquidity_score: float = 0.0
    min_liquidity_score: float = 0.0
    std_dev_liquidity_score: float = 0.0
    
    # Distribution
    depth_distribution: Dict[str, float] = field(default_factory=dict)
    spread_distribution: Dict[str, float] = field(default_factory=dict)
    
    # Percentiles
    depth_percentiles: Dict[int, float] = field(default_factory=dict)
    spread_percentiles: Dict[int, float] = field(default_factory=dict)
    imbalance_percentiles: Dict[int, float] = field(default_factory=dict)
    
    # Metadata
    snapshots_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "avg_depth": self.avg_depth,
            "max_depth": self.max_depth,
            "min_depth": self.min_depth,
            "median_depth": self.median_depth,
            "std_dev_depth": self.std_dev_depth,
            "avg_spread": self.avg_spread,
            "max_spread": self.max_spread,
            "min_spread": self.min_spread,
            "median_spread": self.median_spread,
            "std_dev_spread": self.std_dev_spread,
            "avg_imbalance": self.avg_imbalance,
            "max_imbalance": self.max_imbalance,
            "min_imbalance": self.min_imbalance,
            "std_dev_imbalance": self.std_dev_imbalance,
            "avg_liquidity_score": self.avg_liquidity_score,
            "max_liquidity_score": self.max_liquidity_score,
            "min_liquidity_score": self.min_liquidity_score,
            "std_dev_liquidity_score": self.std_dev_liquidity_score,
            "depth_distribution": self.depth_distribution,
            "spread_distribution": self.spread_distribution,
            "depth_percentiles": self.depth_percentiles,
            "spread_percentiles": self.spread_percentiles,
            "imbalance_percentiles": self.imbalance_percentiles,
            "snapshots_count": self.snapshots_count,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_depth_percentile(
    depths: List[float],
    percentile: float
) -> float:
    """
    Calculate percentile of depth values.
    
    Args:
        depths: List of depth values
        percentile: Percentile (0-100)
        
    Returns:
        Depth value at percentile
    """
    if not depths:
        return 0.0
        
    sorted_depths = sorted(depths)
    index = (percentile / 100) * (len(sorted_depths) - 1)
    
    if index == int(index):
        return sorted_depths[int(index)]
    else:
        lower = sorted_depths[int(index)]
        upper = sorted_depths[int(index) + 1]
        fraction = index - int(index)
        return lower + (upper - lower) * fraction


def calculate_weighted_average_price(
    levels: List[OrderBookLevel],
    volume: float
) -> float:
    """
    Calculate weighted average price for a given volume.
    
    Args:
        levels: List of order book levels
        volume: Volume to fill
        
    Returns:
        Weighted average price
    """
    cumulative_volume = 0.0
    weighted_price = 0.0
    
    for level in levels:
        if cumulative_volume + level.quantity >= volume:
            remaining = volume - cumulative_volume
            weighted_price += level.price * remaining
            cumulative_volume = volume
            break
        else:
            weighted_price += level.price * level.quantity
            cumulative_volume += level.quantity
            
    if cumulative_volume > 0:
        return weighted_price / cumulative_volume
    return 0.0


def detect_spoofing(
    depth: OrderBookDepth,
    threshold: float = 0.3,
    window: int = 5
) -> bool:
    """
    Detect potential spoofing in order book.
    
    Args:
        depth: Order book depth
        threshold: Imbalance threshold
        window: Number of levels to check
        
    Returns:
        True if spoofing detected
    """
    # Check for large imbalance in first few levels
    bid_volume = sum(level.quantity for level in depth.bids[:window])
    ask_volume = sum(level.quantity for level in depth.asks[:window])
    total = bid_volume + ask_volume
    
    if total > 0:
        imbalance = abs(bid_volume - ask_volume) / total
        return imbalance > threshold
        
    return False


def calculate_depth_tier(
    depth: OrderBookDepth,
    percentage: float,
    side: OrderBookSide
) -> Tuple[float, float]:
    """
    Calculate depth tier for a given percentage.
    
    Args:
        depth: Order book depth
        percentage: Percentage from mid price
        side: BID or ASK
        
    Returns:
        Tuple of (volume, average_price)
    """
    if side == OrderBookSide.BID:
        price_limit = depth.mid_price * (1 - percentage)
        levels = depth.bids
    else:
        price_limit = depth.mid_price * (1 + percentage)
        levels = depth.asks
        
    volume = 0.0
    weighted_price = 0.0
    
    for level in levels:
        if side == OrderBookSide.BID:
            if level.price >= price_limit:
                volume += level.quantity
                weighted_price += level.price * level.quantity
            else:
                break
        else:
            if level.price <= price_limit:
                volume += level.quantity
                weighted_price += level.price * level.quantity
            else:
                break
                
    avg_price = weighted_price / volume if volume > 0 else 0.0
    return volume, avg_price


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'OrderBookSide',
    'OrderType',
    'OrderStatus',
    'DepthUpdateType',
    'LiquidityType',
    'MarketImpactType',
    
    # Core Models
    'OrderBookLevel',
    'OrderBookDepth',
    'LiquidityAnalysis',
    'OrderFlow',
    'DepthSnapshot',
    'DepthStatistics',
    
    # Helper Functions
    'calculate_depth_percentile',
    'calculate_weighted_average_price',
    'detect_spoofing',
    'calculate_depth_tier',
]
