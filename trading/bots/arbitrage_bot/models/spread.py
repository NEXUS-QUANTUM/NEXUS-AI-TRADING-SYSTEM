# trading/bots/arbitrage_bot/models/spread.py
# NEXUS AI TRADING SYSTEM - SPREAD MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for spread analysis, calculation,
# monitoring, and optimization for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Spread Models

This module provides comprehensive data models for:
- Spread calculation and analysis
- Bid-ask spread monitoring
- Cross-exchange spread analysis
- Spread volatility and trends
- Spread-based arbitrage opportunities
- Spread optimization strategies
- Spread impact on profitability
- Historical spread analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class SpreadType(str, Enum):
    """Types of spreads."""
    BID_ASK = "bid_ask"                  # Exchange bid-ask spread
    CROSS_EXCHANGE = "cross_exchange"    # Cross-exchange spread
    CROSS_MARKET = "cross_market"        # Cross-market spread
    CROSS_CHAIN = "cross_chain"          # Cross-chain spread
    BASIS = "basis"                      # Basis spread (futures - spot)
    FUNDING = "funding"                  # Funding rate spread
    INTEREST = "interest"                # Interest rate spread
    ARBITRAGE = "arbitrage"              # Arbitrage spread


class SpreadDirection(str, Enum):
    """Direction of spread."""
    NORMAL = "normal"                    # Bid < Ask (normal market)
    INVERTED = "inverted"                # Bid > Ask (inverted market)
    FLAT = "flat"                        # Bid = Ask (flat market)
    WIDE = "wide"                        # Wide spread
    NARROW = "narrow"                    # Narrow spread
    VOLATILE = "volatile"                # Volatile spread


class SpreadSeverity(str, Enum):
    """Severity levels of spreads."""
    VERY_NARROW = "very_narrow"          # < 0.01%
    NARROW = "narrow"                    # 0.01-0.05%
    NORMAL = "normal"                    # 0.05-0.1%
    WIDE = "wide"                        # 0.1-0.5%
    VERY_WIDE = "very_wide"              # > 0.5%


class SpreadCalculationMethod(str, Enum):
    """Methods for calculating spreads."""
    ABSOLUTE = "absolute"                # Absolute difference
    PERCENTAGE = "percentage"            # Percentage
    BPS = "bps"                          # Basis points
    RELATIVE = "relative"                # Relative to mid
    LOG = "log"                          # Logarithmic


# ====================================================================================
# SPREAD MODELS
# ====================================================================================

@dataclass
class Spread:
    """
    Comprehensive spread model.
    """
    # Core fields
    spread_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    type: SpreadType = SpreadType.BID_ASK
    
    # Spread values
    bid_price: float = 0.0
    ask_price: float = 0.0
    mid_price: float = 0.0
    absolute_spread: float = 0.0
    percentage_spread: float = 0.0
    spread_bps: float = 0.0
    
    # Direction and severity
    direction: SpreadDirection = SpreadDirection.NORMAL
    severity: SpreadSeverity = SpreadSeverity.NORMAL
    
    # Calculation
    calculation_method: SpreadCalculationMethod = SpreadCalculationMethod.PERCENTAGE
    calculation_version: str = "1.0.0"
    
    # Context
    timestamp: datetime = field(default_factory=datetime.utcnow)
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    total_volume: float = 0.0
    
    # Statistics
    avg_spread: float = 0.0
    min_spread: float = 0.0
    max_spread: float = 0.0
    std_dev: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.mid_price = (self.bid_price + self.ask_price) / 2 if self.bid_price and self.ask_price else 0
        self.absolute_spread = self.ask_price - self.bid_price if self.bid_price and self.ask_price else 0
        
        # Calculate percentage spread
        if self.mid_price > 0:
            self.percentage_spread = (self.absolute_spread / self.mid_price) * 100
            self.spread_bps = self.percentage_spread * 100
            
        # Determine direction
        if self.absolute_spread > 0:
            self.direction = SpreadDirection.NORMAL
        elif self.absolute_spread < 0:
            self.direction = SpreadDirection.INVERTED
        else:
            self.direction = SpreadDirection.FLAT
            
        # Determine severity
        abs_spread_bps = abs(self.spread_bps)
        if abs_spread_bps < 1:  # < 0.01%
            self.severity = SpreadSeverity.VERY_NARROW
        elif abs_spread_bps < 5:  # 0.01-0.05%
            self.severity = SpreadSeverity.NARROW
        elif abs_spread_bps < 10:  # 0.05-0.1%
            self.severity = SpreadSeverity.NORMAL
        elif abs_spread_bps < 50:  # 0.1-0.5%
            self.severity = SpreadSeverity.WIDE
        else:  # > 0.5%
            self.severity = SpreadSeverity.VERY_WIDE
            
        # Update total volume
        self.total_volume = self.bid_volume + self.ask_volume
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spread_id": self.spread_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "type": self.type.value if self.type else None,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "mid_price": self.mid_price,
            "absolute_spread": self.absolute_spread,
            "percentage_spread": self.percentage_spread,
            "spread_bps": self.spread_bps,
            "direction": self.direction.value if self.direction else None,
            "severity": self.severity.value if self.severity else None,
            "calculation_method": self.calculation_method.value if self.calculation_method else None,
            "calculation_version": self.calculation_version,
            "timestamp": self.timestamp.isoformat(),
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "total_volume": self.total_volume,
            "avg_spread": self.avg_spread,
            "min_spread": self.min_spread,
            "max_spread": self.max_spread,
            "std_dev": self.std_dev,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Spread":
        """Create from dictionary."""
        spread = cls(
            spread_id=data.get("spread_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            type=SpreadType(data["type"]) if data.get("type") else SpreadType.BID_ASK,
            bid_price=data.get("bid_price", 0.0),
            ask_price=data.get("ask_price", 0.0),
            mid_price=data.get("mid_price", 0.0),
            absolute_spread=data.get("absolute_spread", 0.0),
            percentage_spread=data.get("percentage_spread", 0.0),
            spread_bps=data.get("spread_bps", 0.0),
            direction=SpreadDirection(data["direction"]) if data.get("direction") else SpreadDirection.NORMAL,
            severity=SpreadSeverity(data["severity"]) if data.get("severity") else SpreadSeverity.NORMAL,
            calculation_method=SpreadCalculationMethod(data["calculation_method"]) if data.get("calculation_method") else SpreadCalculationMethod.PERCENTAGE,
            calculation_version=data.get("calculation_version", "1.0.0"),
            bid_volume=data.get("bid_volume", 0.0),
            ask_volume=data.get("ask_volume", 0.0),
            total_volume=data.get("total_volume", 0.0),
            avg_spread=data.get("avg_spread", 0.0),
            min_spread=data.get("min_spread", 0.0),
            max_spread=data.get("max_spread", 0.0),
            std_dev=data.get("std_dev", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            spread.timestamp = datetime.fromisoformat(data["timestamp"])
            
        spread.__post_init__()
        return spread
        
    def is_normal(self) -> bool:
        """Check if spread is normal (bid < ask)."""
        return self.direction == SpreadDirection.NORMAL
        
    def is_inverted(self) -> bool:
        """Check if spread is inverted (bid > ask)."""
        return self.direction == SpreadDirection.INVERTED
        
    def is_profitable_for_arbitrage(self, min_spread_bps: float = 5.0) -> bool:
        """
        Check if spread is profitable for arbitrage.
        
        Args:
            min_spread_bps: Minimum spread in basis points
            
        Returns:
            True if spread is profitable
        """
        return self.spread_bps >= min_spread_bps
        
    def get_arbitrage_profit_potential(self, fees_bps: float = 0.0) -> float:
        """
        Calculate arbitrage profit potential.
        
        Args:
            fees_bps: Trading fees in basis points
            
        Returns:
            Profit potential in basis points
        """
        return self.spread_bps - fees_bps


# ====================================================================================
# CROSS-EXCHANGE SPREAD MODELS
# ====================================================================================

@dataclass
class CrossExchangeSpread:
    """
    Spread between two exchanges.
    """
    # Core fields
    spread_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange_a: str = ""
    exchange_b: str = ""
    
    # Prices
    price_a: float = 0.0
    price_b: float = 0.0
    mid_price: float = 0.0
    absolute_spread: float = 0.0
    percentage_spread: float = 0.0
    spread_bps: float = 0.0
    
    # Direction
    direction: str = "a_to_b"           # a_to_b, b_to_a, flat
    source_exchange: str = ""
    target_exchange: str = ""
    
    # Fees
    fee_a: float = 0.0
    fee_b: float = 0.0
    total_fees_bps: float = 0.0
    
    # Profitability
    net_profit_bps: float = 0.0
    is_profitable: bool = False
    profit_ratio: float = 0.0
    
    # Timing
    timestamp: datetime = field(default_factory=datetime.utcnow)
    latency_ms: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.mid_price = (self.price_a + self.price_b) / 2 if self.price_a and self.price_b else 0
        self.absolute_spread = abs(self.price_a - self.price_b)
        
        if self.mid_price > 0:
            self.percentage_spread = (self.absolute_spread / self.mid_price) * 100
            self.spread_bps = self.percentage_spread * 100
            
        # Determine direction
        if self.price_a > self.price_b:
            self.direction = "a_to_b"
            self.source_exchange = self.exchange_a
            self.target_exchange = self.exchange_b
        elif self.price_b > self.price_a:
            self.direction = "b_to_a"
            self.source_exchange = self.exchange_b
            self.target_exchange = self.exchange_a
        else:
            self.direction = "flat"
            self.source_exchange = ""
            self.target_exchange = ""
            
        # Calculate net profit
        self.total_fees_bps = self.fee_a + self.fee_b
        self.net_profit_bps = self.spread_bps - self.total_fees_bps
        self.is_profitable = self.net_profit_bps > 0
        self.profit_ratio = self.net_profit_bps / self.total_fees_bps if self.total_fees_bps > 0 else 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spread_id": self.spread_id,
            "symbol": self.symbol,
            "exchange_a": self.exchange_a,
            "exchange_b": self.exchange_b,
            "price_a": self.price_a,
            "price_b": self.price_b,
            "mid_price": self.mid_price,
            "absolute_spread": self.absolute_spread,
            "percentage_spread": self.percentage_spread,
            "spread_bps": self.spread_bps,
            "direction": self.direction,
            "source_exchange": self.source_exchange,
            "target_exchange": self.target_exchange,
            "fee_a": self.fee_a,
            "fee_b": self.fee_b,
            "total_fees_bps": self.total_fees_bps,
            "net_profit_bps": self.net_profit_bps,
            "is_profitable": self.is_profitable,
            "profit_ratio": self.profit_ratio,
            "timestamp": self.timestamp.isoformat(),
            "latency_ms": self.latency_ms,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossExchangeSpread":
        """Create from dictionary."""
        spread = cls(
            spread_id=data.get("spread_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange_a=data.get("exchange_a", ""),
            exchange_b=data.get("exchange_b", ""),
            price_a=data.get("price_a", 0.0),
            price_b=data.get("price_b", 0.0),
            mid_price=data.get("mid_price", 0.0),
            absolute_spread=data.get("absolute_spread", 0.0),
            percentage_spread=data.get("percentage_spread", 0.0),
            spread_bps=data.get("spread_bps", 0.0),
            direction=data.get("direction", "flat"),
            source_exchange=data.get("source_exchange", ""),
            target_exchange=data.get("target_exchange", ""),
            fee_a=data.get("fee_a", 0.0),
            fee_b=data.get("fee_b", 0.0),
            total_fees_bps=data.get("total_fees_bps", 0.0),
            net_profit_bps=data.get("net_profit_bps", 0.0),
            is_profitable=data.get("is_profitable", False),
            profit_ratio=data.get("profit_ratio", 0.0),
            latency_ms=data.get("latency_ms", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            spread.timestamp = datetime.fromisoformat(data["timestamp"])
            
        spread.__post_init__()
        return spread


# ====================================================================================
# SPREAD HISTORY MODELS
# ====================================================================================

@dataclass
class SpreadHistory:
    """
    Historical spread data.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    type: SpreadType = SpreadType.BID_ASK
    interval: str = "1m"                # 1m, 5m, 15m, 1h, 4h, 1d
    
    # Historical data
    spreads: List[Spread] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    values: List[float] = field(default_factory=list)  # Spread values in bps
    
    # Statistics
    count: int = 0
    min_spread_bps: float = 0.0
    max_spread_bps: float = 0.0
    avg_spread_bps: float = 0.0
    median_spread_bps: float = 0.0
    std_dev: float = 0.0
    
    # Percentiles
    p10_spread_bps: float = 0.0
    p25_spread_bps: float = 0.0
    p50_spread_bps: float = 0.0
    p75_spread_bps: float = 0.0
    p90_spread_bps: float = 0.0
    p95_spread_bps: float = 0.0
    p99_spread_bps: float = 0.0
    
    # Trends
    trend_direction: str = "stable"      # increasing, decreasing, stable
    trend_rate: float = 0.0             # bps per hour
    trend_strength: float = 0.0         # 0-1
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate statistics."""
        if self.spreads:
            self._calculate_statistics()
            
    def _calculate_statistics(self) -> None:
        """Calculate statistics from spread data."""
        if not self.spreads:
            return
            
        spread_values = [s.spread_bps for s in self.spreads]
        self.count = len(spread_values)
        self.min_spread_bps = min(spread_values)
        self.max_spread_bps = max(spread_values)
        self.avg_spread_bps = sum(spread_values) / len(spread_values)
        self.median_spread_bps = sorted(spread_values)[len(spread_values) // 2]
        
        if len(spread_values) > 1:
            self.std_dev = math.sqrt(sum((x - self.avg_spread_bps) ** 2 for x in spread_values) / len(spread_values))
            
        # Calculate percentiles
        sorted_values = sorted(spread_values)
        self.p10_spread_bps = sorted_values[int(len(sorted_values) * 0.1)] if sorted_values else 0
        self.p25_spread_bps = sorted_values[int(len(sorted_values) * 0.25)] if sorted_values else 0
        self.p50_spread_bps = sorted_values[int(len(sorted_values) * 0.5)] if sorted_values else 0
        self.p75_spread_bps = sorted_values[int(len(sorted_values) * 0.75)] if sorted_values else 0
        self.p90_spread_bps = sorted_values[int(len(sorted_values) * 0.9)] if sorted_values else 0
        self.p95_spread_bps = sorted_values[int(len(sorted_values) * 0.95)] if sorted_values else 0
        self.p99_spread_bps = sorted_values[int(len(sorted_values) * 0.99)] if sorted_values else 0
        
        # Calculate trend
        if len(spread_values) > 1:
            # Simple linear regression
            x = list(range(len(spread_values)))
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(spread_values)
            sum_xy = sum(x[i] * spread_values[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            
            if n * sum_x2 - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                self.trend_rate = slope * 60  # Convert to per hour
                
                if slope > 0.001:
                    self.trend_direction = "increasing"
                elif slope < -0.001:
                    self.trend_direction = "decreasing"
                else:
                    self.trend_direction = "stable"
                    
                # Calculate trend strength (R-squared)
                y_pred = [sum_y / n + slope * (xi - sum_x / n) for xi in x]
                ss_reg = sum((yp - sum_y / n) ** 2 for yp in y_pred)
                ss_tot = sum((y - sum_y / n) ** 2 for y in spread_values)
                if ss_tot > 0:
                    self.trend_strength = ss_reg / ss_tot
                    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "type": self.type.value if self.type else None,
            "interval": self.interval,
            "spreads": [s.to_dict() for s in self.spreads[:1000]],  # Limit size
            "timestamps": [t.isoformat() for t in self.timestamps[:1000]],
            "values": self.values[:1000],
            "count": self.count,
            "min_spread_bps": self.min_spread_bps,
            "max_spread_bps": self.max_spread_bps,
            "avg_spread_bps": self.avg_spread_bps,
            "median_spread_bps": self.median_spread_bps,
            "std_dev": self.std_dev,
            "p10_spread_bps": self.p10_spread_bps,
            "p25_spread_bps": self.p25_spread_bps,
            "p50_spread_bps": self.p50_spread_bps,
            "p75_spread_bps": self.p75_spread_bps,
            "p90_spread_bps": self.p90_spread_bps,
            "p95_spread_bps": self.p95_spread_bps,
            "p99_spread_bps": self.p99_spread_bps,
            "trend_direction": self.trend_direction,
            "trend_rate": self.trend_rate,
            "trend_strength": self.trend_strength,
            "metadata": self.metadata
        }


# ====================================================================================
# SPREAD OPTIMIZATION MODELS
# ====================================================================================

@dataclass
class SpreadOptimization:
    """
    Spread optimization strategy.
    """
    # Core fields
    optimization_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    
    # Current spread
    current_spread_bps: float = 0.0
    target_spread_bps: float = 0.0
    spread_gap_bps: float = 0.0
    
    # Optimization strategies
    strategies: List[Dict[str, Any]] = field(default_factory=list)
    active_strategies: List[str] = field(default_factory=list)
    recommended_strategies: List[str] = field(default_factory=list)
    
    # Expected improvement
    expected_improvement_bps: float = 0.0
    expected_improvement_percentage: float = 0.0
    
    # Cost-benefit
    implementation_cost: float = 0.0
    expected_benefit: float = 0.0
    roi: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimization_id": self.optimization_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "current_spread_bps": self.current_spread_bps,
            "target_spread_bps": self.target_spread_bps,
            "spread_gap_bps": self.spread_gap_bps,
            "strategies": self.strategies,
            "active_strategies": self.active_strategies,
            "recommended_strategies": self.recommended_strategies,
            "expected_improvement_bps": self.expected_improvement_bps,
            "expected_improvement_percentage": self.expected_improvement_percentage,
            "implementation_cost": self.implementation_cost,
            "expected_benefit": self.expected_benefit,
            "roi": self.roi,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_spread(
    bid: float,
    ask: float,
    method: SpreadCalculationMethod = SpreadCalculationMethod.PERCENTAGE
) -> float:
    """
    Calculate spread between bid and ask.
    
    Args:
        bid: Bid price
        ask: Ask price
        method: Calculation method
        
    Returns:
        Spread value
    """
    if bid == 0 or ask == 0:
        return 0.0
        
    absolute_spread = ask - bid
    
    if method == SpreadCalculationMethod.ABSOLUTE:
        return absolute_spread
    elif method == SpreadCalculationMethod.PERCENTAGE:
        return (absolute_spread / bid) * 100
    elif method == SpreadCalculationMethod.BPS:
        return (absolute_spread / bid) * 10000
    elif method == SpreadCalculationMethod.RELATIVE:
        mid = (bid + ask) / 2
        return absolute_spread / mid if mid > 0 else 0
    elif method == SpreadCalculationMethod.LOG:
        return math.log(ask / bid) if bid > 0 else 0
    else:
        return absolute_spread


def calculate_cross_exchange_spread(
    price_a: float,
    price_b: float,
    fee_a_bps: float = 0,
    fee_b_bps: float = 0
) -> Dict[str, float]:
    """
    Calculate cross-exchange spread.
    
    Args:
        price_a: Price on exchange A
        price_b: Price on exchange B
        fee_a_bps: Fee on exchange A in bps
        fee_b_bps: Fee on exchange B in bps
        
    Returns:
        Dict with spread metrics
    """
    if price_a == 0 or price_b == 0:
        return {
            "spread_bps": 0,
            "net_spread_bps": 0,
            "is_profitable": False,
            "profit_ratio": 0
        }
        
    absolute_spread = abs(price_a - price_b)
    mid_price = (price_a + price_b) / 2
    spread_bps = (absolute_spread / mid_price) * 10000 if mid_price > 0 else 0
    
    total_fees_bps = fee_a_bps + fee_b_bps
    net_spread_bps = spread_bps - total_fees_bps
    
    return {
        "spread_bps": spread_bps,
        "net_spread_bps": net_spread_bps,
        "is_profitable": net_spread_bps > 0,
        "profit_ratio": net_spread_bps / total_fees_bps if total_fees_bps > 0 else 0
    }


def calculate_arbitrage_spread(
    buy_exchange_price: float,
    sell_exchange_price: float,
    buy_fee_bps: float,
    sell_fee_bps: float,
    min_profit_bps: float = 5.0
) -> Dict[str, Any]:
    """
    Calculate arbitrage spread between two exchanges.
    
    Args:
        buy_exchange_price: Price on buy exchange
        sell_exchange_price: Price on sell exchange
        buy_fee_bps: Fee on buy exchange in bps
        sell_fee_bps: Fee on sell exchange in bps
        min_profit_bps: Minimum profit in bps
        
    Returns:
        Dict with arbitrage analysis
    """
    if buy_exchange_price == 0 or sell_exchange_price == 0:
        return {
            "is_arbitrage": False,
            "spread_bps": 0,
            "net_profit_bps": 0,
            "reason": "Invalid prices"
        }
        
    absolute_spread = sell_exchange_price - buy_exchange_price
    mid_price = (buy_exchange_price + sell_exchange_price) / 2
    spread_bps = (absolute_spread / mid_price) * 10000 if mid_price > 0 else 0
    
    total_fees_bps = buy_fee_bps + sell_fee_bps
    net_profit_bps = spread_bps - total_fees_bps
    
    return {
        "is_arbitrage": net_profit_bps > min_profit_bps,
        "spread_bps": spread_bps,
        "net_profit_bps": net_profit_bps,
        "total_fees_bps": total_fees_bps,
        "profit_percentage": net_profit_bps / 100,
        "reason": "Profit opportunity" if net_profit_bps > min_profit_bps else "Profit too small"
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'SpreadType',
    'SpreadDirection',
    'SpreadSeverity',
    'SpreadCalculationMethod',
    
    # Core Models
    'Spread',
    'CrossExchangeSpread',
    'SpreadHistory',
    'SpreadOptimization',
    
    # Helper Functions
    'calculate_spread',
    'calculate_cross_exchange_spread',
    'calculate_arbitrage_spread',
]
