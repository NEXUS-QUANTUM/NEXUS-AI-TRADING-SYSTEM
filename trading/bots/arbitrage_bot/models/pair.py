# trading/bots/arbitrage_bot/models/pair.py
# NEXUS AI TRADING SYSTEM - PAIR MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for trading pairs, pair configurations,
# pair analysis, and pair management across multiple exchanges for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Pair Models

This module provides comprehensive data models for:
- Trading pair definition and configuration
- Pair mapping across exchanges
- Pair analysis and correlation
- Pair performance tracking
- Pair risk assessment
- Pair optimization and selection
- Cross-exchange pair matching
- Pair metadata and statistics
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

class PairCategory(str, Enum):
    """Categories of trading pairs."""
    MAJOR = "major"                      # Major pairs (BTC, ETH, etc.)
    CROSS = "cross"                      # Cross pairs (ETH/BTC, etc.)
    EXOTIC = "exotic"                    # Exotic pairs
    STABLE = "stable"                    # Stablecoin pairs (USDT/USDC, etc.)
    DEFI = "defi"                        # DeFi tokens
    MEME = "meme"                        # Meme coins
    LAYER1 = "layer1"                    # Layer 1 tokens
    LAYER2 = "layer2"                    # Layer 2 tokens
    AI = "ai"                            # AI tokens
    GAMING = "gaming"                    # Gaming tokens
    METAVERSE = "metaverse"              # Metaverse tokens
    NFT = "nft"                          # NFT-related tokens
    RWA = "rwa"                          # Real World Assets
    PRIVACY = "privacy"                  # Privacy tokens
    INFRASTRUCTURE = "infrastructure"    # Infrastructure tokens


class PairStatus(str, Enum):
    """Status of a trading pair."""
    ACTIVE = "active"                    # Actively traded
    PAUSED = "paused"                    # Temporarily paused
    DISABLED = "disabled"                # Permanently disabled
    MAINTENANCE = "maintenance"          # Under maintenance
    DELISTED = "delisted"                # Delisted from exchange
    MONITORING = "monitoring"            # Under monitoring


class PairType(str, Enum):
    """Types of trading pairs."""
    SPOT = "spot"                        # Spot pair
    PERPETUAL = "perpetual"              # Perpetual futures
    FUTURES = "futures"                  # Dated futures
    OPTIONS = "options"                  # Options pair
    MARGIN = "margin"                    # Margin trading pair
    LEVERAGED = "leveraged"              # Leveraged token pair


class CorrelationStrength(str, Enum):
    """Strength of correlation between pairs."""
    VERY_STRONG = "very_strong"          # 0.8 - 1.0
    STRONG = "strong"                    # 0.6 - 0.8
    MODERATE = "moderate"                # 0.4 - 0.6
    WEAK = "weak"                        # 0.2 - 0.4
    VERY_WEAK = "very_weak"              # 0.0 - 0.2
    NEGATIVE = "negative"                # -1.0 - 0.0


class LiquidityLevel(str, Enum):
    """Liquidity level of a trading pair."""
    VERY_HIGH = "very_high"              # > $100M daily volume
    HIGH = "high"                        # $50M - $100M
    MEDIUM = "medium"                    # $10M - $50M
    LOW = "low"                          # $1M - $10M
    VERY_LOW = "very_low"                # < $1M


class VolatilityLevel(str, Enum):
    """Volatility level of a trading pair."""
    VERY_LOW = "very_low"                # < 10% annualized
    LOW = "low"                          # 10-30% annualized
    MEDIUM = "medium"                    # 30-60% annualized
    HIGH = "high"                        # 60-100% annualized
    VERY_HIGH = "very_high"              # > 100% annualized


# ====================================================================================
# PAIR MODELS
# ====================================================================================

@dataclass
class Pair:
    """
    Trading pair model.
    """
    # Core fields
    pair_id: str = field(default_factory=lambda: str(uuid4()))
    base_asset: str = ""
    quote_asset: str = ""
    symbol: str = ""
    exchange: str = ""
    
    # Pair type and category
    pair_type: PairType = PairType.SPOT
    category: PairCategory = PairCategory.MAJOR
    status: PairStatus = PairStatus.ACTIVE
    
    # Exchange-specific fields
    exchange_symbol: str = ""
    exchange_pair_id: str = ""
    contract_address: str = ""
    
    # Trading parameters
    min_quantity: float = 0.0
    max_quantity: float = 0.0
    step_size: float = 0.0
    min_price: float = 0.0
    max_price: float = 0.0
    tick_size: float = 0.0
    min_notional: float = 0.0
    
    # Leverage and margin
    max_leverage: int = 1
    min_leverage: int = 1
    margin_asset: str = ""
    
    # Fees
    maker_fee: float = 0.001
    taker_fee: float = 0.001
    funding_rate: float = 0.0
    funding_interval: int = 8  # hours
    
    # Market data
    current_price: float = 0.0
    bid_price: float = 0.0
    ask_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    
    # Volume and liquidity
    volume_24h: float = 0.0
    volume_24h_quote: float = 0.0
    volume_30d: float = 0.0
    liquidity_score: float = 0.0
    liquidity_level: LiquidityLevel = LiquidityLevel.MEDIUM
    
    # Volatility
    volatility_24h: float = 0.0
    volatility_7d: float = 0.0
    volatility_30d: float = 0.0
    volatility_level: VolatilityLevel = VolatilityLevel.MEDIUM
    
    # Correlation
    correlations: Dict[str, float] = field(default_factory=dict)
    correlation_strength: CorrelationStrength = CorrelationStrength.MODERATE
    
    # Performance
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    price_change_30d: float = 0.0
    ath_price: float = 0.0
    atl_price: float = 0.0
    
    # Metrics
    profitability_score: float = 0.0
    risk_score: float = 0.0
    opportunity_score: float = 0.0
    pair_quality_score: float = 0.0
    
    # Arbitrage metrics
    arbitrage_volume_24h: float = 0.0
    arbitrage_profit_24h: float = 0.0
    arbitrage_count_24h: int = 0
    avg_spread_bps: float = 0.0
    max_spread_bps: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_traded: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize derived fields."""
        self.symbol = f"{self.base_asset}{self.quote_asset}"
        if self.bid_price and self.ask_price:
            self.spread = self.ask_price - self.bid_price
            self.spread_bps = (self.spread / self.mid_price) * 10000 if self.mid_price > 0 else 0
            
    @property
    def mid_price(self) -> float:
        """Get mid price."""
        if self.bid_price and self.ask_price:
            return (self.bid_price + self.ask_price) / 2
        return self.current_price
        
    @property
    def name(self) -> str:
        """Get pair name."""
        return f"{self.base_asset}/{self.quote_asset}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "pair_type": self.pair_type.value if self.pair_type else None,
            "category": self.category.value if self.category else None,
            "status": self.status.value if self.status else None,
            "exchange_symbol": self.exchange_symbol,
            "exchange_pair_id": self.exchange_pair_id,
            "contract_address": self.contract_address,
            "min_quantity": self.min_quantity,
            "max_quantity": self.max_quantity,
            "step_size": self.step_size,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "tick_size": self.tick_size,
            "min_notional": self.min_notional,
            "max_leverage": self.max_leverage,
            "min_leverage": self.min_leverage,
            "margin_asset": self.margin_asset,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "funding_rate": self.funding_rate,
            "funding_interval": self.funding_interval,
            "current_price": self.current_price,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "spread": self.spread,
            "spread_bps": self.spread_bps,
            "volume_24h": self.volume_24h,
            "volume_24h_quote": self.volume_24h_quote,
            "volume_30d": self.volume_30d,
            "liquidity_score": self.liquidity_score,
            "liquidity_level": self.liquidity_level.value if self.liquidity_level else None,
            "volatility_24h": self.volatility_24h,
            "volatility_7d": self.volatility_7d,
            "volatility_30d": self.volatility_30d,
            "volatility_level": self.volatility_level.value if self.volatility_level else None,
            "correlations": self.correlations,
            "correlation_strength": self.correlation_strength.value if self.correlation_strength else None,
            "price_change_24h": self.price_change_24h,
            "price_change_7d": self.price_change_7d,
            "price_change_30d": self.price_change_30d,
            "ath_price": self.ath_price,
            "atl_price": self.atl_price,
            "profitability_score": self.profitability_score,
            "risk_score": self.risk_score,
            "opportunity_score": self.opportunity_score,
            "pair_quality_score": self.pair_quality_score,
            "arbitrage_volume_24h": self.arbitrage_volume_24h,
            "arbitrage_profit_24h": self.arbitrage_profit_24h,
            "arbitrage_count_24h": self.arbitrage_count_24h,
            "avg_spread_bps": self.avg_spread_bps,
            "max_spread_bps": self.max_spread_bps,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_traded": self.last_traded.isoformat() if self.last_traded else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pair":
        """Create from dictionary."""
        pair = cls(
            pair_id=data.get("pair_id", str(uuid4())),
            base_asset=data.get("base_asset", ""),
            quote_asset=data.get("quote_asset", ""),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            pair_type=PairType(data["pair_type"]) if data.get("pair_type") else PairType.SPOT,
            category=PairCategory(data["category"]) if data.get("category") else PairCategory.MAJOR,
            status=PairStatus(data["status"]) if data.get("status") else PairStatus.ACTIVE,
            exchange_symbol=data.get("exchange_symbol", ""),
            exchange_pair_id=data.get("exchange_pair_id", ""),
            contract_address=data.get("contract_address", ""),
            min_quantity=data.get("min_quantity", 0.0),
            max_quantity=data.get("max_quantity", 0.0),
            step_size=data.get("step_size", 0.0),
            min_price=data.get("min_price", 0.0),
            max_price=data.get("max_price", 0.0),
            tick_size=data.get("tick_size", 0.0),
            min_notional=data.get("min_notional", 0.0),
            max_leverage=data.get("max_leverage", 1),
            min_leverage=data.get("min_leverage", 1),
            margin_asset=data.get("margin_asset", ""),
            maker_fee=data.get("maker_fee", 0.001),
            taker_fee=data.get("taker_fee", 0.001),
            funding_rate=data.get("funding_rate", 0.0),
            funding_interval=data.get("funding_interval", 8),
            current_price=data.get("current_price", 0.0),
            bid_price=data.get("bid_price", 0.0),
            ask_price=data.get("ask_price", 0.0),
            volume_24h=data.get("volume_24h", 0.0),
            volume_24h_quote=data.get("volume_24h_quote", 0.0),
            volume_30d=data.get("volume_30d", 0.0),
            liquidity_score=data.get("liquidity_score", 0.0),
            liquidity_level=LiquidityLevel(data["liquidity_level"]) if data.get("liquidity_level") else LiquidityLevel.MEDIUM,
            volatility_24h=data.get("volatility_24h", 0.0),
            volatility_7d=data.get("volatility_7d", 0.0),
            volatility_30d=data.get("volatility_30d", 0.0),
            volatility_level=VolatilityLevel(data["volatility_level"]) if data.get("volatility_level") else VolatilityLevel.MEDIUM,
            correlations=data.get("correlations", {}),
            correlation_strength=CorrelationStrength(data["correlation_strength"]) if data.get("correlation_strength") else CorrelationStrength.MODERATE,
            price_change_24h=data.get("price_change_24h", 0.0),
            price_change_7d=data.get("price_change_7d", 0.0),
            price_change_30d=data.get("price_change_30d", 0.0),
            ath_price=data.get("ath_price", 0.0),
            atl_price=data.get("atl_price", 0.0),
            profitability_score=data.get("profitability_score", 0.0),
            risk_score=data.get("risk_score", 0.0),
            opportunity_score=data.get("opportunity_score", 0.0),
            pair_quality_score=data.get("pair_quality_score", 0.0),
            arbitrage_volume_24h=data.get("arbitrage_volume_24h", 0.0),
            arbitrage_profit_24h=data.get("arbitrage_profit_24h", 0.0),
            arbitrage_count_24h=data.get("arbitrage_count_24h", 0),
            avg_spread_bps=data.get("avg_spread_bps", 0.0),
            max_spread_bps=data.get("max_spread_bps", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("created_at"):
            pair.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            pair.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("last_traded"):
            pair.last_traded = datetime.fromisoformat(data["last_traded"])
            
        pair.__post_init__()
        return pair
        
    def update_price(self, price: float, bid: float = 0.0, ask: float = 0.0) -> None:
        """
        Update price data.
        
        Args:
            price: Current price
            bid: Best bid price
            ask: Best ask price
        """
        self.current_price = price
        self.bid_price = bid or price
        self.ask_price = ask or price
        self.spread = self.ask_price - self.bid_price
        self.spread_bps = (self.spread / self.mid_price) * 10000 if self.mid_price > 0 else 0
        self.updated_at = datetime.utcnow()
        
    def update_volume(self, volume: float, quote_volume: float = 0.0) -> None:
        """
        Update volume data.
        
        Args:
            volume: Trading volume
            quote_volume: Quote volume
        """
        self.volume_24h = volume
        self.volume_24h_quote = quote_volume or volume * self.current_price
        self.updated_at = datetime.utcnow()
        
    def calculate_liquidity_level(self) -> LiquidityLevel:
        """Calculate liquidity level based on volume."""
        if self.volume_24h > 100000000:  # > $100M
            return LiquidityLevel.VERY_HIGH
        elif self.volume_24h > 50000000:  # > $50M
            return LiquidityLevel.HIGH
        elif self.volume_24h > 10000000:  # > $10M
            return LiquidityLevel.MEDIUM
        elif self.volume_24h > 1000000:   # > $1M
            return LiquidityLevel.LOW
        else:
            return LiquidityLevel.VERY_LOW
            
    def calculate_volatility_level(self) -> VolatilityLevel:
        """Calculate volatility level based on 30d volatility."""
        if self.volatility_30d > 1.0:  # > 100%
            return VolatilityLevel.VERY_HIGH
        elif self.volatility_30d > 0.6:  # 60-100%
            return VolatilityLevel.HIGH
        elif self.volatility_30d > 0.3:  # 30-60%
            return VolatilityLevel.MEDIUM
        elif self.volatility_30d > 0.1:  # 10-30%
            return VolatilityLevel.LOW
        else:
            return VolatilityLevel.VERY_LOW
            
    def calculate_pair_quality_score(self) -> float:
        """
        Calculate overall pair quality score.
        
        Returns:
            Quality score (0-100)
        """
        score = 0.0
        
        # Liquidity score (30%)
        liquidity_scores = {
            LiquidityLevel.VERY_HIGH: 100,
            LiquidityLevel.HIGH: 80,
            LiquidityLevel.MEDIUM: 60,
            LiquidityLevel.LOW: 40,
            LiquidityLevel.VERY_LOW: 20
        }
        score += liquidity_scores.get(self.liquidity_level, 50) * 0.3
        
        # Spread score (25%)
        if self.spread_bps < 1:  # < 1 basis point
            spread_score = 100
        elif self.spread_bps < 5:  # < 5 basis points
            spread_score = 80
        elif self.spread_bps < 10:  # < 10 basis points
            spread_score = 60
        elif self.spread_bps < 20:  # < 20 basis points
            spread_score = 40
        else:
            spread_score = 20
        score += spread_score * 0.25
        
        # Volatility score (20%)
        volatility_scores = {
            VolatilityLevel.VERY_LOW: 60,
            VolatilityLevel.LOW: 70,
            VolatilityLevel.MEDIUM: 80,
            VolatilityLevel.HIGH: 90,
            VolatilityLevel.VERY_HIGH: 70
        }
        score += volatility_scores.get(self.volatility_level, 70) * 0.2
        
        # Fee score (15%)
        avg_fee = (self.maker_fee + self.taker_fee) / 2
        if avg_fee < 0.0005:  # < 0.05%
            fee_score = 100
        elif avg_fee < 0.001:  # < 0.1%
            fee_score = 80
        elif avg_fee < 0.002:  # < 0.2%
            fee_score = 60
        elif avg_fee < 0.005:  # < 0.5%
            fee_score = 40
        else:
            fee_score = 20
        score += fee_score * 0.15
        
        # Arbitrage potential score (10%)
        if self.arbitrage_count_24h > 100:
            arb_score = 100
        elif self.arbitrage_count_24h > 50:
            arb_score = 80
        elif self.arbitrage_count_24h > 20:
            arb_score = 60
        elif self.arbitrage_count_24h > 10:
            arb_score = 40
        else:
            arb_score = 20
        score += arb_score * 0.1
        
        self.pair_quality_score = score
        return score
        
    def is_tradable(self) -> bool:
        """Check if pair is tradable."""
        return self.status == PairStatus.ACTIVE and self.current_price > 0
        
    def get_minimum_trade_value(self) -> float:
        """Get minimum trade value."""
        return self.min_quantity * self.current_price
        
    def get_maximum_trade_value(self) -> float:
        """Get maximum trade value."""
        return self.max_quantity * self.current_price
        
    def validate_quantity(self, quantity: float) -> bool:
        """
        Validate quantity against constraints.
        
        Args:
            quantity: Quantity to validate
            
        Returns:
            True if valid
        """
        if quantity < self.min_quantity or quantity > self.max_quantity:
            return False
        if self.step_size > 0:
            remainder = (quantity / self.step_size) % 1
            if remainder > 1e-10:
                return False
        return True
        
    def validate_price(self, price: float) -> bool:
        """
        Validate price against constraints.
        
        Args:
            price: Price to validate
            
        Returns:
            True if valid
        """
        if price < self.min_price or price > self.max_price:
            return False
        if self.tick_size > 0:
            remainder = (price / self.tick_size) % 1
            if remainder > 1e-10:
                return False
        return True


# ====================================================================================
# PAIR MAPPING MODELS
# ====================================================================================

@dataclass
class PairMapping:
    """
    Mapping of a pair across multiple exchanges.
    """
    # Core fields
    mapping_id: str = field(default_factory=lambda: str(uuid4()))
    base_asset: str = ""
    quote_asset: str = ""
    symbol: str = ""
    
    # Exchange-specific mappings
    exchange_mappings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Unified metrics
    avg_volume_24h: float = 0.0
    avg_liquidity_score: float = 0.0
    avg_spread_bps: float = 0.0
    avg_price: float = 0.0
    
    # Active exchanges
    active_exchanges: List[str] = field(default_factory=list)
    total_exchanges: int = 0
    
    # Arbitrage potential
    max_spread_bps: float = 0.0
    min_spread_bps: float = 0.0
    avg_spread_volatility: float = 0.0
    arbitrage_opportunities_24h: int = 0
    arbitrage_profit_potential: float = 0.0
    
    # Metadata
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mapping_id": self.mapping_id,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "symbol": self.symbol,
            "exchange_mappings": self.exchange_mappings,
            "avg_volume_24h": self.avg_volume_24h,
            "avg_liquidity_score": self.avg_liquidity_score,
            "avg_spread_bps": self.avg_spread_bps,
            "avg_price": self.avg_price,
            "active_exchanges": self.active_exchanges,
            "total_exchanges": self.total_exchanges,
            "max_spread_bps": self.max_spread_bps,
            "min_spread_bps": self.min_spread_bps,
            "avg_spread_volatility": self.avg_spread_volatility,
            "arbitrage_opportunities_24h": self.arbitrage_opportunities_24h,
            "arbitrage_profit_potential": self.arbitrage_profit_potential,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
        
    def add_exchange_mapping(self, exchange: str, pair_data: Dict[str, Any]) -> None:
        """
        Add or update exchange mapping.
        
        Args:
            exchange: Exchange name
            pair_data: Pair data from exchange
        """
        self.exchange_mappings[exchange] = pair_data
        self.total_exchanges = len(self.exchange_mappings)
        
        # Update active exchanges
        if pair_data.get("status") == "active":
            if exchange not in self.active_exchanges:
                self.active_exchanges.append(exchange)
        else:
            if exchange in self.active_exchanges:
                self.active_exchanges.remove(exchange)
                
        self._update_metrics()
        self.updated_at = datetime.utcnow()
        
    def _update_metrics(self) -> None:
        """Update aggregated metrics."""
        volumes = []
        spreads = []
        prices = []
        
        for exchange, data in self.exchange_mappings.items():
            if data.get("status") == "active":
                volumes.append(data.get("volume_24h", 0))
                spreads.append(data.get("spread_bps", 0))
                prices.append(data.get("price", 0))
                
        if volumes:
            self.avg_volume_24h = sum(volumes) / len(volumes)
            self.avg_liquidity_score = min(100, self.avg_volume_24h / 1000000 * 100)
        if spreads:
            self.avg_spread_bps = sum(spreads) / len(spreads)
            self.max_spread_bps = max(spreads)
            self.min_spread_bps = min(spreads)
            self.avg_spread_volatility = (self.max_spread_bps - self.min_spread_bps) / 2
        if prices:
            self.avg_price = sum(prices) / len(prices)
            
        # Calculate arbitrage potential
        if spreads and len(spreads) > 1:
            self.arbitrage_profit_potential = (self.max_spread_bps - self.min_spread_bps) / 2


# ====================================================================================
# PAIR PERFORMANCE MODELS
# ====================================================================================

@dataclass
class PairPerformance:
    """
    Performance metrics for a trading pair.
    """
    pair_id: str = ""
    symbol: str = ""
    exchange: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Return metrics
    total_return: float = 0.0
    daily_return: float = 0.0
    weekly_return: float = 0.0
    monthly_return: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    
    # Trading metrics
    total_volume: float = 0.0
    avg_volume: float = 0.0
    max_volume: float = 0.0
    min_volume: float = 0.0
    
    # Arbitrage metrics
    arbitrage_profit: float = 0.0
    arbitrage_count: int = 0
    success_rate: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pair_id": self.pair_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_return": self.total_return,
            "daily_return": self.daily_return,
            "weekly_return": self.weekly_return,
            "monthly_return": self.monthly_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "total_volume": self.total_volume,
            "avg_volume": self.avg_volume,
            "max_volume": self.max_volume,
            "min_volume": self.min_volume,
            "arbitrage_profit": self.arbitrage_profit,
            "arbitrage_count": self.arbitrage_count,
            "success_rate": self.success_rate,
            "metadata": self.metadata
        }


# ====================================================================================
# PAIR FILTER MODELS
# ====================================================================================

@dataclass
class PairFilter:
    """
    Filter for trading pairs.
    """
    # Basic filters
    exchanges: List[str] = field(default_factory=list)
    base_assets: List[str] = field(default_factory=list)
    quote_assets: List[str] = field(default_factory=list)
    categories: List[PairCategory] = field(default_factory=list)
    pair_types: List[PairType] = field(default_factory=list)
    statuses: List[PairStatus] = field(default_factory=list)
    
    # Financial filters
    min_volume: float = 0.0
    max_volume: float = float('inf')
    min_liquidity_score: float = 0.0
    max_liquidity_score: float = 100.0
    max_spread_bps: float = float('inf')
    min_spread_bps: float = 0.0
    
    # Volatility filters
    min_volatility: float = 0.0
    max_volatility: float = float('inf')
    volatility_levels: List[VolatilityLevel] = field(default_factory=list)
    
    # Arbitrage filters
    min_arbitrage_opportunities: int = 0
    min_arbitrage_profit: float = 0.0
    min_arbitrage_count: int = 0
    
    # Performance filters
    min_profitability_score: float = 0.0
    min_pair_quality_score: float = 0.0
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Sorting
    sort_by: str = "pair_quality_score"
    sort_order: str = "desc"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchanges": self.exchanges,
            "base_assets": self.base_assets,
            "quote_assets": self.quote_assets,
            "categories": [c.value for c in self.categories],
            "pair_types": [p.value for p in self.pair_types],
            "statuses": [s.value for s in self.statuses],
            "min_volume": self.min_volume,
            "max_volume": self.max_volume,
            "min_liquidity_score": self.min_liquidity_score,
            "max_liquidity_score": self.max_liquidity_score,
            "max_spread_bps": self.max_spread_bps,
            "min_spread_bps": self.min_spread_bps,
            "min_volatility": self.min_volatility,
            "max_volatility": self.max_volatility,
            "volatility_levels": [v.value for v in self.volatility_levels],
            "min_arbitrage_opportunities": self.min_arbitrage_opportunities,
            "min_arbitrage_profit": self.min_arbitrage_profit,
            "min_arbitrage_count": self.min_arbitrage_count,
            "min_profitability_score": self.min_profitability_score,
            "min_pair_quality_score": self.min_pair_quality_score,
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_pair(
    base_asset: str,
    quote_asset: str,
    exchange: str,
    **kwargs
) -> Pair:
    """
    Create a trading pair.
    
    Args:
        base_asset: Base asset
        quote_asset: Quote asset
        exchange: Exchange name
        **kwargs: Additional pair fields
        
    Returns:
        Pair instance
    """
    return Pair(
        base_asset=base_asset,
        quote_asset=quote_asset,
        exchange=exchange,
        **kwargs
    )


def calculate_pair_correlation(
    prices_a: List[float],
    prices_b: List[float]
) -> float:
    """
    Calculate correlation between two price series.
    
    Args:
        prices_a: First price series
        prices_b: Second price series
        
    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(prices_a) != len(prices_b) or len(prices_a) < 2:
        return 0.0
        
    n = len(prices_a)
    mean_a = sum(prices_a) / n
    mean_b = sum(prices_b) / n
    
    numerator = sum((prices_a[i] - mean_a) * (prices_b[i] - mean_b) for i in range(n))
    denominator_a = sum((prices_a[i] - mean_a) ** 2 for i in range(n))
    denominator_b = sum((prices_b[i] - mean_b) ** 2 for i in range(n))
    
    if denominator_a == 0 or denominator_b == 0:
        return 0.0
        
    return numerator / (denominator_a ** 0.5 * denominator_b ** 0.5)


def calculate_pair_spread(
    price_a: float,
    price_b: float,
    base_price: float
) -> float:
    """
    Calculate spread between two prices in basis points.
    
    Args:
        price_a: First price
        price_b: Second price
        base_price: Base price for normalization
        
    Returns:
        Spread in basis points
    """
    if base_price == 0:
        return 0.0
    return abs(price_a - price_b) / base_price * 10000


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'PairCategory',
    'PairStatus',
    'PairType',
    'CorrelationStrength',
    'LiquidityLevel',
    'VolatilityLevel',
    
    # Core Models
    'Pair',
    'PairMapping',
    'PairPerformance',
    'PairFilter',
    
    # Helper Functions
    'create_pair',
    'calculate_pair_correlation',
    'calculate_pair_spread',
]
