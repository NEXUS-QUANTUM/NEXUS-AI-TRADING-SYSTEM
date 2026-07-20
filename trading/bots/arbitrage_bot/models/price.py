# trading/bots/arbitrage_bot/models/price.py
# NEXUS AI TRADING SYSTEM - PRICE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for price data, price feeds, price analysis,
# and price-related calculations for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Price Models

This module provides comprehensive data models for:
- Price data structures and feeds
- Price analysis and statistics
- Price comparisons and spreads
- Price history and trends
- Price prediction and forecasting
- Price volatility and stability
- Price impact and slippage
- Price anomalies and outliers
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import statistics

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class PriceSource(str, Enum):
    """Sources of price data."""
    EXCHANGE = "exchange"                # Direct from exchange
    AGGREGATOR = "aggregator"            # Aggregated from multiple sources
    ORACLE = "oracle"                    # Price oracle (Chainlink, etc.)
    INDEX = "index"                      # Index price
    TWAP = "twap"                        # Time-weighted average price
    VWAP = "vwap"                        # Volume-weighted average price
    MID = "mid"                          # Mid price from order book
    LAST = "last"                        # Last traded price
    MARK = "mark"                        # Mark price (futures)
    FAIR = "fair"                        # Fair value price
    SPOT = "spot"                        # Spot price
    FUTURES = "futures"                  # Futures price
    PERPETUAL = "perpetual"              # Perpetual price


class PriceType(str, Enum):
    """Types of price data."""
    BID = "bid"                          # Bid price
    ASK = "ask"                          # Ask price
    LAST = "last"                        # Last traded price
    HIGH = "high"                        # Highest price
    LOW = "low"                          # Lowest price
    OPEN = "open"                        # Opening price
    CLOSE = "close"                      # Closing price
    VWAP = "vwap"                        # Volume-weighted average price
    TWAP = "twap"                        # Time-weighted average price
    MID = "mid"                          # Mid price
    MARK = "mark"                        # Mark price
    INDEX = "index"                      # Index price
    FAIR = "fair"                        # Fair price


class PriceStatus(str, Enum):
    """Status of price data."""
    LIVE = "live"                        # Live price data
    DELAYED = "delayed"                  # Delayed price data
    SNAPSHOT = "snapshot"                # Snapshot price
    HISTORICAL = "historical"            # Historical price
    ESTIMATED = "estimated"              # Estimated price
    FORECAST = "forecast"                # Forecasted price


class TrendDirection(str, Enum):
    """Price trend direction."""
    UP = "up"                            # Upward trend
    DOWN = "down"                        # Downward trend
    SIDEWAYS = "sideways"                # Sideways/consolidation
    REVERSAL = "reversal"                # Trend reversal
    BREAKOUT = "breakout"                # Breakout
    BREAKDOWN = "breakdown"              # Breakdown


class VolatilityLevel(str, Enum):
    """Volatility levels."""
    VERY_LOW = "very_low"                # < 5% annualized
    LOW = "low"                          # 5-15% annualized
    MEDIUM = "medium"                    # 15-30% annualized
    HIGH = "high"                        # 30-60% annualized
    VERY_HIGH = "very_high"              # > 60% annualized


# ====================================================================================
# PRICE DATA MODELS
# ====================================================================================

@dataclass
class Price:
    """
    Single price point with metadata.
    """
    # Core fields
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: PriceSource = PriceSource.EXCHANGE
    type: PriceType = PriceType.LAST
    
    # Context
    symbol: str = ""
    exchange: str = ""
    currency: str = "USDT"
    
    # Additional data
    volume: float = 0.0                    # Volume at this price
    bid: float = 0.0                       # Bid price (if available)
    ask: float = 0.0                       # Ask price (if available)
    spread: float = 0.0                    # Spread (ask - bid)
    
    # Confidence
    confidence: float = 1.0                # Confidence level (0-1)
    status: PriceStatus = PriceStatus.LIVE
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.bid and self.ask:
            self.spread = self.ask - self.bid
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value if self.source else None,
            "type": self.type.value if self.type else None,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "currency": self.currency,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "spread": self.spread,
            "confidence": self.confidence,
            "status": self.status.value if self.status else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Price":
        """Create from dictionary."""
        price = cls(
            price=data.get("price", 0.0),
            source=PriceSource(data["source"]) if data.get("source") else PriceSource.EXCHANGE,
            type=PriceType(data["type"]) if data.get("type") else PriceType.LAST,
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            currency=data.get("currency", "USDT"),
            volume=data.get("volume", 0.0),
            bid=data.get("bid", 0.0),
            ask=data.get("ask", 0.0),
            confidence=data.get("confidence", 1.0),
            status=PriceStatus(data["status"]) if data.get("status") else PriceStatus.LIVE,
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            price.timestamp = datetime.fromisoformat(data["timestamp"])
            
        price.__post_init__()
        return price
        
    def get_mid_price(self) -> float:
        """Get mid price if bid/ask available."""
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.price
        
    def get_spread_bps(self) -> float:
        """Get spread in basis points."""
        if self.bid and self.ask and self.bid > 0:
            return (self.ask - self.bid) / self.bid * 10000
        return 0.0
        
    def is_positive(self) -> bool:
        """Check if price is positive."""
        return self.price > 0
        
    def is_valid(self) -> bool:
        """Check if price is valid."""
        return self.price > 0 and math.isfinite(self.price)


@dataclass
class PriceFeed:
    """
    Continuous price feed data.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    source: PriceSource = PriceSource.EXCHANGE
    
    # Current price
    current_price: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    mid_price: float = 0.0
    
    # 24-hour data
    high_24h: float = 0.0
    low_24h: float = 0.0
    open_24h: float = 0.0
    close_24h: float = 0.0
    volume_24h: float = 0.0
    quote_volume_24h: float = 0.0
    change_24h: float = 0.0
    change_percent_24h: float = 0.0
    
    # 7-day data
    high_7d: float = 0.0
    low_7d: float = 0.0
    change_percent_7d: float = 0.0
    
    # 30-day data
    high_30d: float = 0.0
    low_30d: float = 0.0
    change_percent_30d: float = 0.0
    
    # Statistics
    avg_price: float = 0.0
    median_price: float = 0.0
    std_dev: float = 0.0
    volatility: float = 0.0
    
    # Status
    status: PriceStatus = PriceStatus.LIVE
    confidence: float = 1.0
    
    # Timestamps
    updated_at: datetime = field(default_factory=datetime.utcnow)
    data_start: Optional[datetime] = None
    data_end: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.mid_price = (self.bid_price + self.ask_price) / 2 if self.bid_price and self.ask_price else self.current_price
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "source": self.source.value if self.source else None,
            "current_price": self.current_price,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "mid_price": self.mid_price,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "open_24h": self.open_24h,
            "close_24h": self.close_24h,
            "volume_24h": self.volume_24h,
            "quote_volume_24h": self.quote_volume_24h,
            "change_24h": self.change_24h,
            "change_percent_24h": self.change_percent_24h,
            "high_7d": self.high_7d,
            "low_7d": self.low_7d,
            "change_percent_7d": self.change_percent_7d,
            "high_30d": self.high_30d,
            "low_30d": self.low_30d,
            "change_percent_30d": self.change_percent_30d,
            "avg_price": self.avg_price,
            "median_price": self.median_price,
            "std_dev": self.std_dev,
            "volatility": self.volatility,
            "status": self.status.value if self.status else None,
            "confidence": self.confidence,
            "updated_at": self.updated_at.isoformat(),
            "data_start": self.data_start.isoformat() if self.data_start else None,
            "data_end": self.data_end.isoformat() if self.data_end else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceFeed":
        """Create from dictionary."""
        feed = cls(
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            source=PriceSource(data["source"]) if data.get("source") else PriceSource.EXCHANGE,
            current_price=data.get("current_price", 0.0),
            bid_price=data.get("bid_price", 0.0),
            ask_price=data.get("ask_price", 0.0),
            high_24h=data.get("high_24h", 0.0),
            low_24h=data.get("low_24h", 0.0),
            open_24h=data.get("open_24h", 0.0),
            close_24h=data.get("close_24h", 0.0),
            volume_24h=data.get("volume_24h", 0.0),
            quote_volume_24h=data.get("quote_volume_24h", 0.0),
            change_24h=data.get("change_24h", 0.0),
            change_percent_24h=data.get("change_percent_24h", 0.0),
            high_7d=data.get("high_7d", 0.0),
            low_7d=data.get("low_7d", 0.0),
            change_percent_7d=data.get("change_percent_7d", 0.0),
            high_30d=data.get("high_30d", 0.0),
            low_30d=data.get("low_30d", 0.0),
            change_percent_30d=data.get("change_percent_30d", 0.0),
            avg_price=data.get("avg_price", 0.0),
            median_price=data.get("median_price", 0.0),
            std_dev=data.get("std_dev", 0.0),
            volatility=data.get("volatility", 0.0),
            status=PriceStatus(data["status"]) if data.get("status") else PriceStatus.LIVE,
            confidence=data.get("confidence", 1.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("updated_at"):
            feed.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("data_start"):
            feed.data_start = datetime.fromisoformat(data["data_start"])
        if data.get("data_end"):
            feed.data_end = datetime.fromisoformat(data["data_end"])
            
        feed.__post_init__()
        return feed
        
    def update(self, price: float, bid: float = 0.0, ask: float = 0.0) -> None:
        """
        Update price feed.
        
        Args:
            price: Current price
            bid: Bid price
            ask: Ask price
        """
        self.current_price = price
        if bid:
            self.bid_price = bid
        if ask:
            self.ask_price = ask
        self.mid_price = (self.bid_price + self.ask_price) / 2 if self.bid_price and self.ask_price else self.current_price
        self.updated_at = datetime.utcnow()
        
    def get_volatility_level(self) -> VolatilityLevel:
        """Get volatility level."""
        if self.volatility < 0.05:
            return VolatilityLevel.VERY_LOW
        elif self.volatility < 0.15:
            return VolatilityLevel.LOW
        elif self.volatility < 0.30:
            return VolatilityLevel.MEDIUM
        elif self.volatility < 0.60:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.VERY_HIGH


# ====================================================================================
# PRICE HISTORY MODELS
# ====================================================================================

@dataclass
class PriceHistory:
    """
    Historical price data.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    interval: str = "1m"                   # 1m, 5m, 15m, 1h, 4h, 1d, 1w, 1M
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    
    # Price data
    prices: List[Price] = field(default_factory=list)
    
    # OHLCV data
    opens: List[float] = field(default_factory=list)
    highs: List[float] = field(default_factory=list)
    lows: List[float] = field(default_factory=list)
    closes: List[float] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    
    # Statistics
    count: int = 0
    min_price: float = 0.0
    max_price: float = 0.0
    avg_price: float = 0.0
    median_price: float = 0.0
    std_dev: float = 0.0
    total_volume: float = 0.0
    avg_volume: float = 0.0
    
    # Volatility
    volatility: float = 0.0
    volatility_annualized: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate statistics."""
        if self.prices:
            self._calculate_statistics()
            
    def _calculate_statistics(self) -> None:
        """Calculate statistics from price data."""
        if not self.prices:
            return
            
        price_values = [p.price for p in self.prices]
        volume_values = [p.volume for p in self.prices if p.volume > 0]
        
        self.count = len(price_values)
        self.min_price = min(price_values)
        self.max_price = max(price_values)
        self.avg_price = sum(price_values) / len(price_values)
        self.median_price = statistics.median(price_values)
        self.std_dev = statistics.stdev(price_values) if len(price_values) > 1 else 0.0
        self.total_volume = sum(volume_values) if volume_values else 0.0
        self.avg_volume = self.total_volume / len(volume_values) if volume_values else 0.0
        self.volatility = self.std_dev / self.avg_price if self.avg_price > 0 else 0.0
        self.volatility_annualized = self.volatility * math.sqrt(365 * 24 * 60 / self._get_interval_minutes())
        
    def _get_interval_minutes(self) -> float:
        """Get interval in minutes."""
        interval_map = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "6h": 360,
            "12h": 720, "1d": 1440, "1w": 10080, "1M": 43200
        }
        return interval_map.get(self.interval, 1)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "interval": self.interval,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "prices": [p.to_dict() for p in self.prices[:1000]],  # Limit to avoid excessive size
            "opens": self.opens,
            "highs": self.highs,
            "lows": self.lows,
            "closes": self.closes,
            "volumes": self.volumes,
            "count": self.count,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "avg_price": self.avg_price,
            "median_price": self.median_price,
            "std_dev": self.std_dev,
            "total_volume": self.total_volume,
            "avg_volume": self.avg_volume,
            "volatility": self.volatility,
            "volatility_annualized": self.volatility_annualized,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceHistory":
        """Create from dictionary."""
        history = cls(
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            interval=data.get("interval", "1m"),
            start_time=datetime.fromisoformat(data["start_time"]) if data.get("start_time") else datetime.utcnow(),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else datetime.utcnow(),
            prices=[Price.from_dict(p) for p in data.get("prices", [])],
            opens=data.get("opens", []),
            highs=data.get("highs", []),
            lows=data.get("lows", []),
            closes=data.get("closes", []),
            volumes=data.get("volumes", []),
            metadata=data.get("metadata", {})
        )
        history.__post_init__()
        return history
        
    def add_price(self, price: Price) -> None:
        """
        Add price to history.
        
        Args:
            price: Price to add
        """
        self.prices.append(price)
        self._calculate_statistics()
        
    def get_returns(self) -> List[float]:
        """
        Calculate returns from price data.
        
        Returns:
            List of returns
        """
        if len(self.prices) < 2:
            return []
            
        returns = []
        for i in range(1, len(self.prices)):
            if self.prices[i-1].price > 0:
                ret = (self.prices[i].price - self.prices[i-1].price) / self.prices[i-1].price
                returns.append(ret)
        return returns
        
    def get_cumulative_return(self) -> float:
        """
        Calculate cumulative return.
        
        Returns:
            Cumulative return
        """
        if not self.prices:
            return 0.0
        return (self.prices[-1].price - self.prices[0].price) / self.prices[0].price if self.prices[0].price > 0 else 0.0


# ====================================================================================
# PRICE COMPARISON MODELS
# ====================================================================================

@dataclass
class PriceComparison:
    """
    Comparison of prices across multiple sources.
    """
    # Core fields
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Price data
    prices: Dict[str, Dict[str, float]] = field(default_factory=dict)  # source -> {type: price}
    
    # Best prices
    best_bid: float = 0.0
    best_bid_source: str = ""
    best_ask: float = 0.0
    best_ask_source: str = ""
    best_mid: float = 0.0
    best_mid_source: str = ""
    
    # Worst prices
    worst_bid: float = 0.0
    worst_bid_source: str = ""
    worst_ask: float = 0.0
    worst_ask_source: str = ""
    
    # Spreads
    spread: float = 0.0
    max_spread: float = 0.0
    min_spread: float = 0.0
    avg_spread: float = 0.0
    
    # Arbitrage opportunities
    arbitrage_opportunities: List[Dict[str, Any]] = field(default_factory=list)
    max_arbitrage_profit: float = 0.0
    max_arbitrage_percentage: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate comparison metrics."""
        self._calculate_metrics()
        
    def _calculate_metrics(self) -> None:
        """Calculate comparison metrics."""
        # Extract bids and asks
        bids = {}
        asks = {}
        
        for source, price_data in self.prices.items():
            if isinstance(price_data, dict):
                if 'bid' in price_data:
                    bids[source] = price_data['bid']
                if 'ask' in price_data:
                    asks[source] = price_data['ask']
                    
        # Best prices
        if bids:
            self.best_bid = max(bids.values())
            self.best_bid_source = max(bids, key=bids.get)
            self.worst_bid = min(bids.values())
            self.worst_bid_source = min(bids, key=bids.get)
            
        if asks:
            self.best_ask = min(asks.values())
            self.best_ask_source = min(asks, key=asks.get)
            self.worst_ask = max(asks.values())
            self.worst_ask_source = max(asks, key=asks.get)
            
        # Mid prices
        if self.best_bid and self.best_ask:
            self.best_mid = (self.best_bid + self.best_ask) / 2
            self.best_mid_source = f"{self.best_bid_source}/{self.best_ask_source}"
            
        # Spreads
        spreads = []
        for source in set(bids.keys()) & set(asks.keys()):
            if bids[source] > 0:
                spread = (asks[source] - bids[source]) / bids[source] * 10000
                spreads.append(spread)
                
        if spreads:
            self.spread = statistics.mean(spreads)
            self.max_spread = max(spreads)
            self.min_spread = min(spreads)
            self.avg_spread = statistics.mean(spreads)
            
        # Arbitrage opportunities
        self._find_arbitrage_opportunities(bids, asks)
        
    def _find_arbitrage_opportunities(self, bids: Dict[str, float], asks: Dict[str, float]) -> None:
        """
        Find arbitrage opportunities between sources.
        
        Args:
            bids: Dict of bid prices by source
            asks: Dict of ask prices by source
        """
        self.arbitrage_opportunities = []
        self.max_arbitrage_profit = 0.0
        self.max_arbitrage_percentage = 0.0
        
        for buy_source, ask_price in asks.items():
            for sell_source, bid_price in bids.items():
                if buy_source != sell_source and ask_price > 0:
                    spread = (bid_price - ask_price) / ask_price * 100
                    if spread > 0:
                        opportunity = {
                            "buy_exchange": buy_source,
                            "sell_exchange": sell_source,
                            "buy_price": ask_price,
                            "sell_price": bid_price,
                            "spread_percentage": spread,
                            "profit_percentage": spread * 0.95  # Estimate after fees
                        }
                        self.arbitrage_opportunities.append(opportunity)
                        
                        if spread > self.max_arbitrage_percentage:
                            self.max_arbitrage_percentage = spread
                            self.max_arbitrage_profit = spread * 0.95


# ====================================================================================
# PRICE ANOMALY MODELS
# ====================================================================================

@dataclass
class PriceAnomaly:
    """
    Price anomaly detection result.
    """
    anomaly_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Anomaly details
    detected_price: float = 0.0
    expected_price: float = 0.0
    deviation: float = 0.0
    deviation_percentage: float = 0.0
    z_score: float = 0.0
    
    # Context
    window_size: int = 100
    avg_price: float = 0.0
    std_dev: float = 0.0
    median_price: float = 0.0
    
    # Classification
    anomaly_type: str = "spike"           # spike, dip, breakout, breakdown, flash_crash
    severity: str = "medium"              # low, medium, high, critical
    confidence: float = 0.0
    
    # Source data
    source_prices: List[float] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "anomaly_id": self.anomaly_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "detected_price": self.detected_price,
            "expected_price": self.expected_price,
            "deviation": self.deviation,
            "deviation_percentage": self.deviation_percentage,
            "z_score": self.z_score,
            "window_size": self.window_size,
            "avg_price": self.avg_price,
            "std_dev": self.std_dev,
            "median_price": self.median_price,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "source_prices": self.source_prices[:10],  # Limit for display
            "metadata": self.metadata
        }


# ====================================================================================
# PRICE FORECAST MODELS
# ====================================================================================

@dataclass
class PriceForecast:
    """
    Price forecast/prediction result.
    """
    forecast_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    forecast_time: datetime = field(default_factory=datetime.utcnow)
    
    # Forecast details
    current_price: float = 0.0
    forecast_price: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    confidence: float = 0.0
    
    # Timeframes
    timeframe: str = "1h"                 # 1h, 4h, 24h, 7d, 30d
    horizon_hours: int = 1
    
    # Expected movement
    expected_change: float = 0.0
    expected_change_percentage: float = 0.0
    expected_volatility: float = 0.0
    
    # Model
    model: str = "prophet"                # prophet, arima, lstm, transformer
    model_version: str = "1.0.0"
    features_used: List[str] = field(default_factory=list)
    
    # Scenario analysis
    scenarios: Dict[str, Dict[str, float]] = field(default_factory=dict)  # bullish, bearish, base
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "forecast_id": self.forecast_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp.isoformat(),
            "forecast_time": self.forecast_time.isoformat(),
            "current_price": self.current_price,
            "forecast_price": self.forecast_price,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence": self.confidence,
            "timeframe": self.timeframe,
            "horizon_hours": self.horizon_hours,
            "expected_change": self.expected_change,
            "expected_change_percentage": self.expected_change_percentage,
            "expected_volatility": self.expected_volatility,
            "model": self.model,
            "model_version": self.model_version,
            "features_used": self.features_used,
            "scenarios": self.scenarios,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_price_change(
    old_price: float,
    new_price: float,
    as_percentage: bool = True
) -> float:
    """
    Calculate price change.
    
    Args:
        old_price: Old price
        new_price: New price
        as_percentage: Return as percentage
        
    Returns:
        Price change
    """
    if old_price == 0:
        return 0.0
        
    change = (new_price - old_price) / old_price
    if as_percentage:
        change = change * 100
        
    return change


def calculate_volatility(
    prices: List[float],
    annualize: bool = True,
    periods_per_year: float = 365
) -> float:
    """
    Calculate volatility from price series.
    
    Args:
        prices: List of prices
        annualize: Annualize volatility
        periods_per_year: Number of periods per year
        
    Returns:
        Volatility
    """
    if len(prices) < 2:
        return 0.0
        
    # Calculate returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
            
    if not returns:
        return 0.0
        
    # Calculate standard deviation
    std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.0
    
    if annualize:
        return std_dev * math.sqrt(periods_per_year)
        
    return std_dev


def calculate_moving_average(
    prices: List[float],
    window: int
) -> List[float]:
    """
    Calculate moving average of price series.
    
    Args:
        prices: List of prices
        window: Window size
        
    Returns:
        Moving averages
    """
    if len(prices) < window:
        return []
        
    moving_averages = []
    for i in range(window - 1, len(prices)):
        window_prices = prices[i - window + 1:i + 1]
        moving_averages.append(sum(window_prices) / window)
        
    return moving_averages


def calculate_bollinger_bands(
    prices: List[float],
    window: int = 20,
    num_std: float = 2.0
) -> Dict[str, List[float]]:
    """
    Calculate Bollinger Bands.
    
    Args:
        prices: List of prices
        window: SMA window
        num_std: Number of standard deviations
        
    Returns:
        Dict with upper, middle, lower bands
    """
    if len(prices) < window:
        return {'upper': [], 'middle': [], 'lower': []}
        
    upper = []
    middle = []
    lower = []
    
    for i in range(window - 1, len(prices)):
        window_prices = prices[i - window + 1:i + 1]
        sma = sum(window_prices) / window
        std_dev = statistics.stdev(window_prices) if len(window_prices) > 1 else 0
        
        middle.append(sma)
        upper.append(sma + (std_dev * num_std))
        lower.append(sma - (std_dev * num_std))
        
    return {'upper': upper, 'middle': middle, 'lower': lower}


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'PriceSource',
    'PriceType',
    'PriceStatus',
    'TrendDirection',
    'VolatilityLevel',
    
    # Core Models
    'Price',
    'PriceFeed',
    'PriceHistory',
    'PriceComparison',
    'PriceAnomaly',
    'PriceForecast',
    
    # Helper Functions
    'calculate_price_change',
    'calculate_volatility',
    'calculate_moving_average',
    'calculate_bollinger_bands',
]
