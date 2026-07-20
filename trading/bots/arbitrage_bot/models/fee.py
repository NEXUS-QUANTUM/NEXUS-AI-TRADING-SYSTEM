# trading/bots/arbitrage_bot/models/fee.py
# NEXUS AI TRADING SYSTEM - FEE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for trading fees, fee structures,
# fee calculations, and fee optimization for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Fee Models

This module provides comprehensive data models for:
- Trading fee structures (maker/taker)
- Fee tier management
- Volume-based fee discounts
- Fee calculation and optimization
- Fee comparison across exchanges
- Rebate and discount programs
- Fee history and analytics
- Fee impact on profitability
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

class FeeTierType(str, Enum):
    """Types of fee tiers."""
    MAKER = "maker"
    TAKER = "taker"
    BOTH = "both"
    VOLUME = "volume"
    VIP = "vip"
    INSTITUTIONAL = "institutional"
    RETAIL = "retail"


class FeeDiscountType(str, Enum):
    """Types of fee discounts."""
    VOLUME = "volume"
    TOKEN = "token"
    STAKING = "staking"
    VIP = "vip"
    REFERRAL = "referral"
    PROMOTIONAL = "promotional"
    BULK = "bulk"
    INSTITUTIONAL = "institutional"


class FeeCurrency(str, Enum):
    """Fee payment currencies."""
    NATIVE = "native"  # Native asset of the exchange
    USDT = "usdt"
    USDC = "usdc"
    BUSD = "busd"
    DAI = "dai"
    BTC = "btc"
    ETH = "eth"
    BNB = "bnb"
    FTT = "ftt"
    HT = "ht"
    OKB = "okb"
    KCS = "kcs"
    GT = "gt"


class FeeCalculationMethod(str, Enum):
    """Methods for calculating fees."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    TIERED = "tiered"
    HYBRID = "hybrid"
    DYNAMIC = "dynamic"
    NEGOTIATED = "negotiated"


# ====================================================================================
# FEE STRUCTURE MODELS
# ====================================================================================

@dataclass
class FeeTier:
    """
    Fee tier for volume-based pricing.
    """
    # Core fields
    tier_id: str = field(default_factory=lambda: str(uuid4()))
    tier_name: str = ""
    tier_level: int = 0
    tier_type: FeeTierType = FeeTierType.BOTH
    
    # Volume requirements
    min_volume_30d: float = 0.0
    max_volume_30d: float = float('inf')
    volume_currency: str = "USDT"
    min_balance: float = 0.0
    balance_currency: str = "USDT"
    
    # Fee rates
    maker_fee: float = 0.001  # 0.1%
    taker_fee: float = 0.001  # 0.1%
    maker_fee_bps: float = 10.0
    taker_fee_bps: float = 10.0
    
    # Discounts
    discount_rate: float = 0.0
    discount_type: FeeDiscountType = FeeDiscountType.VOLUME
    discount_currency: str = "USDT"
    discount_amount: float = 0.0
    
    # Requirements
    requirements: Dict[str, Any] = field(default_factory=dict)
    qualification_period: int = 30  # days
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.maker_fee_bps = self.maker_fee * 10000
        self.taker_fee_bps = self.taker_fee * 10000
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tier_id": self.tier_id,
            "tier_name": self.tier_name,
            "tier_level": self.tier_level,
            "tier_type": self.tier_type.value if self.tier_type else None,
            "min_volume_30d": self.min_volume_30d,
            "max_volume_30d": self.max_volume_30d,
            "volume_currency": self.volume_currency,
            "min_balance": self.min_balance,
            "balance_currency": self.balance_currency,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "maker_fee_bps": self.maker_fee_bps,
            "taker_fee_bps": self.taker_fee_bps,
            "discount_rate": self.discount_rate,
            "discount_type": self.discount_type.value if self.discount_type else None,
            "discount_currency": self.discount_currency,
            "discount_amount": self.discount_amount,
            "requirements": self.requirements,
            "qualification_period": self.qualification_period,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeeTier":
        """Create from dictionary."""
        tier = cls(
            tier_id=data.get("tier_id", str(uuid4())),
            tier_name=data.get("tier_name", ""),
            tier_level=data.get("tier_level", 0),
            tier_type=FeeTierType(data["tier_type"]) if data.get("tier_type") else FeeTierType.BOTH,
            min_volume_30d=data.get("min_volume_30d", 0.0),
            max_volume_30d=data.get("max_volume_30d", float('inf')),
            volume_currency=data.get("volume_currency", "USDT"),
            min_balance=data.get("min_balance", 0.0),
            balance_currency=data.get("balance_currency", "USDT"),
            maker_fee=data.get("maker_fee", 0.001),
            taker_fee=data.get("taker_fee", 0.001),
            discount_rate=data.get("discount_rate", 0.0),
            discount_type=FeeDiscountType(data["discount_type"]) if data.get("discount_type") else FeeDiscountType.VOLUME,
            discount_currency=data.get("discount_currency", "USDT"),
            discount_amount=data.get("discount_amount", 0.0),
            requirements=data.get("requirements", {}),
            qualification_period=data.get("qualification_period", 30),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("created_at"):
            tier.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            tier.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return tier
        
    def qualifies(self, volume_30d: float, balance: float = 0.0) -> bool:
        """
        Check if this tier qualifies based on volume and balance.
        
        Args:
            volume_30d: 30-day trading volume
            balance: Current balance
            
        Returns:
            True if qualifies
        """
        if volume_30d < self.min_volume_30d or volume_30d > self.max_volume_30d:
            return False
        if balance < self.min_balance:
            return False
        return True
        
    def get_effective_maker_fee(self) -> float:
        """Get effective maker fee after discount."""
        return self.maker_fee * (1 - self.discount_rate)
        
    def get_effective_taker_fee(self) -> float:
        """Get effective taker fee after discount."""
        return self.taker_fee * (1 - self.discount_rate)
        
    def get_savings(self, volume: float, is_maker: bool = True) -> float:
        """
        Calculate fee savings compared to base rate.
        
        Args:
            volume: Trading volume
            is_maker: Whether this is a maker order
            
        Returns:
            Savings amount
        """
        base_fee = self.maker_fee if is_maker else self.taker_fee
        effective_fee = self.get_effective_maker_fee() if is_maker else self.get_effective_taker_fee()
        return (base_fee - effective_fee) * volume


@dataclass
class FeeSchedule:
    """
    Complete fee schedule for an exchange.
    """
    # Core fields
    exchange: str = ""
    schedule_id: str = field(default_factory=lambda: str(uuid4()))
    schedule_name: str = ""
    
    # Fee tiers
    tiers: List[FeeTier] = field(default_factory=list)
    default_tier: FeeTier = field(default_factory=FeeTier)
    
    # Fee structure
    fee_structure: FeeCalculationMethod = FeeCalculationMethod.TIERED
    base_maker_fee: float = 0.001
    base_taker_fee: float = 0.001
    
    # Fee currencies
    fee_currency: FeeCurrency = FeeCurrency.USDT
    settlement_currency: str = "USDT"
    
    # Discount programs
    discount_programs: List[Dict[str, Any]] = field(default_factory=list)
    active_discounts: List[FeeDiscountType] = field(default_factory=list)
    
    # Fee history
    fee_history: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "schedule_id": self.schedule_id,
            "schedule_name": self.schedule_name,
            "tiers": [t.to_dict() for t in self.tiers],
            "default_tier": self.default_tier.to_dict(),
            "fee_structure": self.fee_structure.value if self.fee_structure else None,
            "base_maker_fee": self.base_maker_fee,
            "base_taker_fee": self.base_taker_fee,
            "fee_currency": self.fee_currency.value if self.fee_currency else None,
            "settlement_currency": self.settlement_currency,
            "discount_programs": self.discount_programs,
            "active_discounts": [d.value for d in self.active_discounts],
            "fee_history": self.fee_history,
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeeSchedule":
        """Create from dictionary."""
        schedule = cls(
            exchange=data.get("exchange", ""),
            schedule_id=data.get("schedule_id", str(uuid4())),
            schedule_name=data.get("schedule_name", ""),
            tiers=[FeeTier.from_dict(t) for t in data.get("tiers", [])],
            default_tier=FeeTier.from_dict(data.get("default_tier", {})),
            fee_structure=FeeCalculationMethod(data["fee_structure"]) if data.get("fee_structure") else FeeCalculationMethod.TIERED,
            base_maker_fee=data.get("base_maker_fee", 0.001),
            base_taker_fee=data.get("base_taker_fee", 0.001),
            fee_currency=FeeCurrency(data["fee_currency"]) if data.get("fee_currency") else FeeCurrency.USDT,
            settlement_currency=data.get("settlement_currency", "USDT"),
            discount_programs=data.get("discount_programs", []),
            active_discounts=[FeeDiscountType(d) for d in data.get("active_discounts", [])],
            fee_history=data.get("fee_history", []),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("last_updated"):
            schedule.last_updated = datetime.fromisoformat(data["last_updated"])
            
        return schedule
        
    def get_fee_tier(self, volume_30d: float, balance: float = 0.0) -> Optional[FeeTier]:
        """
        Get the applicable fee tier.
        
        Args:
            volume_30d: 30-day trading volume
            balance: Current balance
            
        Returns:
            Matching FeeTier or None
        """
        # Sort tiers by level descending
        sorted_tiers = sorted(self.tiers, key=lambda t: t.tier_level, reverse=True)
        
        for tier in sorted_tiers:
            if tier.qualifies(volume_30d, balance):
                return tier
        return self.default_tier
        
    def calculate_fee(
        self,
        amount: float,
        price: float = 1.0,
        is_maker: bool = True,
        volume_30d: float = 0.0,
        balance: float = 0.0,
        include_discounts: bool = True
    ) -> float:
        """
        Calculate fee for a trade.
        
        Args:
            amount: Trade amount in base currency
            price: Price in quote currency
            is_maker: Whether this is a maker order
            volume_30d: 30-day trading volume
            balance: Current balance
            include_discounts: Whether to apply discounts
            
        Returns:
            Fee amount in quote currency
        """
        # Get applicable tier
        tier = self.get_fee_tier(volume_30d, balance)
        
        # Get base fee rate
        if tier:
            fee_rate = tier.get_effective_maker_fee() if is_maker else tier.get_effective_taker_fee()
        else:
            fee_rate = self.base_maker_fee if is_maker else self.base_taker_fee
            
        # Apply additional discounts
        if include_discounts and self.active_discounts:
            for discount_type in self.active_discounts:
                discount = self._get_discount_rate(discount_type)
                fee_rate = fee_rate * (1 - discount)
                
        # Calculate fee
        trade_value = amount * price
        return trade_value * fee_rate
        
    def _get_discount_rate(self, discount_type: FeeDiscountType) -> float:
        """Get discount rate for a specific discount type."""
        discount_map = {
            FeeDiscountType.VOLUME: 0.1,  # 10% volume discount
            FeeDiscountType.TOKEN: 0.15,   # 15% token discount
            FeeDiscountType.STAKING: 0.05, # 5% staking discount
            FeeDiscountType.VIP: 0.20,     # 20% VIP discount
            FeeDiscountType.REFERRAL: 0.10,# 10% referral discount
            FeeDiscountType.PROMOTIONAL: 0.30, # 30% promotional discount
            FeeDiscountType.BULK: 0.15,    # 15% bulk discount
            FeeDiscountType.INSTITUTIONAL: 0.25 # 25% institutional discount
        }
        return discount_map.get(discount_type, 0.0)
        
    def compare_tiers(self, volume_30d: float, balance: float = 0.0) -> Dict[str, Any]:
        """
        Compare all tiers for a given volume and balance.
        
        Args:
            volume_30d: 30-day trading volume
            balance: Current balance
            
        Returns:
            Comparison results
        """
        results = {}
        for tier in self.tiers:
            tier_results = {
                "qualified": tier.qualifies(volume_30d, balance),
                "maker_fee": tier.maker_fee,
                "taker_fee": tier.taker_fee,
                "maker_fee_bps": tier.maker_fee_bps,
                "taker_fee_bps": tier.taker_fee_bps,
                "effective_maker": tier.get_effective_maker_fee(),
                "effective_taker": tier.get_effective_taker_fee(),
                "discount_rate": tier.discount_rate
            }
            results[tier.tier_name or f"Tier {tier.tier_level}"] = tier_results
        return results
        
    def get_savings_analysis(
        self,
        monthly_volume: float,
        current_tier: Optional[FeeTier] = None
    ) -> Dict[str, Any]:
        """
        Analyze fee savings for different tiers.
        
        Args:
            monthly_volume: Monthly trading volume
            current_tier: Current tier (for comparison)
            
        Returns:
            Savings analysis
        """
        analysis = {
            "monthly_volume": monthly_volume,
            "current_tier": current_tier.tier_name if current_tier else "Unknown",
            "savings": [],
            "best_tier": None,
            "best_savings": 0.0
        }
        
        # Calculate savings for each tier
        for tier in self.tiers:
            if tier.qualifies(monthly_volume):
                maker_savings = tier.get_savings(monthly_volume * 0.5, True)  # Assume 50% maker
                taker_savings = tier.get_savings(monthly_volume * 0.5, False)  # Assume 50% taker
                total_savings = maker_savings + taker_savings
                
                savings_info = {
                    "tier": tier.tier_name or f"Tier {tier.tier_level}",
                    "maker_savings": maker_savings,
                    "taker_savings": taker_savings,
                    "total_savings": total_savings
                }
                analysis["savings"].append(savings_info)
                
                if total_savings > analysis["best_savings"]:
                    analysis["best_savings"] = total_savings
                    analysis["best_tier"] = tier.tier_name or f"Tier {tier.tier_level}"
                    
        return analysis


# ====================================================================================
# FEE CALCULATION MODELS
# ====================================================================================

@dataclass
class FeeCalculation:
    """
    Fee calculation for a specific trade or set of trades.
    """
    # Core fields
    calculation_id: str = field(default_factory=lambda: str(uuid4()))
    trade_id: str = ""
    exchange: str = ""
    symbol: str = ""
    
    # Trade details
    side: str = "buy"  # buy, sell
    amount: float = 0.0
    price: float = 0.0
    trade_value: float = 0.0
    is_maker: bool = True
    
    # Fee details
    fee_rate: float = 0.0
    fee_rate_bps: float = 0.0
    fee_amount: float = 0.0
    fee_currency: str = "USDT"
    
    # Discounts applied
    discounts_applied: List[FeeDiscountType] = field(default_factory=list)
    discount_total: float = 0.0
    original_fee: float = 0.0
    saved_amount: float = 0.0
    
    # Tier information
    tier_level: int = 0
    tier_name: str = ""
    
    # Fee breakdown
    base_fee: float = 0.0
    volume_discount: float = 0.0
    token_discount: float = 0.0
    promo_discount: float = 0.0
    other_discounts: float = 0.0
    
    # Timestamps
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.trade_value = self.amount * self.price
        self.fee_amount = self.trade_value * self.fee_rate
        self.fee_rate_bps = self.fee_rate * 10000
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "calculation_id": self.calculation_id,
            "trade_id": self.trade_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "side": self.side,
            "amount": self.amount,
            "price": self.price,
            "trade_value": self.trade_value,
            "is_maker": self.is_maker,
            "fee_rate": self.fee_rate,
            "fee_rate_bps": self.fee_rate_bps,
            "fee_amount": self.fee_amount,
            "fee_currency": self.fee_currency,
            "discounts_applied": [d.value for d in self.discounts_applied],
            "discount_total": self.discount_total,
            "original_fee": self.original_fee,
            "saved_amount": self.saved_amount,
            "tier_level": self.tier_level,
            "tier_name": self.tier_name,
            "base_fee": self.base_fee,
            "volume_discount": self.volume_discount,
            "token_discount": self.token_discount,
            "promo_discount": self.promo_discount,
            "other_discounts": self.other_discounts,
            "calculated_at": self.calculated_at.isoformat(),
            "metadata": self.metadata
        }
        
    def get_effective_rate(self) -> float:
        """Get effective fee rate after all discounts."""
        return self.fee_rate / (1 + self.discount_total) if self.discount_total > 0 else self.fee_rate
        
    def get_savings_percentage(self) -> float:
        """Get savings percentage."""
        if self.original_fee == 0:
            return 0.0
        return (self.saved_amount / self.original_fee) * 100


# ====================================================================================
# FEE HISTORY AND ANALYTICS MODELS
# ====================================================================================

@dataclass
class FeeHistoryEntry:
    """
    Historical fee record.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    exchange: str = ""
    symbol: str = ""
    fee_type: str = ""  # maker, taker
    fee_rate: float = 0.0
    fee_amount: float = 0.0
    volume: float = 0.0
    trade_value: float = 0.0
    currency: str = "USDT"
    
    # Discounts
    discount_type: Optional[FeeDiscountType] = None
    discount_rate: float = 0.0
    discount_amount: float = 0.0
    
    # Tier
    tier_level: int = 0
    tier_name: str = ""
    
    # Timestamps
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    recorded_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "fee_type": self.fee_type,
            "fee_rate": self.fee_rate,
            "fee_amount": self.fee_amount,
            "volume": self.volume,
            "trade_value": self.trade_value,
            "currency": self.currency,
            "discount_type": self.discount_type.value if self.discount_type else None,
            "discount_rate": self.discount_rate,
            "discount_amount": self.discount_amount,
            "tier_level": self.tier_level,
            "tier_name": self.tier_name,
            "occurred_at": self.occurred_at.isoformat(),
            "recorded_at": self.recorded_at.isoformat()
        }


@dataclass
class FeeAnalytics:
    """
    Fee analytics and statistics.
    """
    exchange: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Fee statistics
    total_fees: float = 0.0
    avg_maker_fee: float = 0.0
    avg_taker_fee: float = 0.0
    max_maker_fee: float = 0.0
    min_maker_fee: float = 0.0
    max_taker_fee: float = 0.0
    min_taker_fee: float = 0.0
    
    # Volume statistics
    total_volume: float = 0.0
    avg_trade_size: float = 0.0
    total_trades: int = 0
    
    # Discount statistics
    total_discounts: float = 0.0
    avg_discount_rate: float = 0.0
    max_discount_rate: float = 0.0
    min_discount_rate: float = 0.0
    
    # Fee by tier
    fees_by_tier: Dict[str, float] = field(default_factory=dict)
    fees_by_symbol: Dict[str, float] = field(default_factory=dict)
    fees_by_fee_type: Dict[str, float] = field(default_factory=dict)
    
    # Fee efficiency
    fee_to_volume_ratio: float = 0.0
    fee_to_profit_ratio: float = 0.0
    savings_rate: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_fees": self.total_fees,
            "avg_maker_fee": self.avg_maker_fee,
            "avg_taker_fee": self.avg_taker_fee,
            "max_maker_fee": self.max_maker_fee,
            "min_maker_fee": self.min_maker_fee,
            "max_taker_fee": self.max_taker_fee,
            "min_taker_fee": self.min_taker_fee,
            "total_volume": self.total_volume,
            "avg_trade_size": self.avg_trade_size,
            "total_trades": self.total_trades,
            "total_discounts": self.total_discounts,
            "avg_discount_rate": self.avg_discount_rate,
            "max_discount_rate": self.max_discount_rate,
            "min_discount_rate": self.min_discount_rate,
            "fees_by_tier": self.fees_by_tier,
            "fees_by_symbol": self.fees_by_symbol,
            "fees_by_fee_type": self.fees_by_fee_type,
            "fee_to_volume_ratio": self.fee_to_volume_ratio,
            "fee_to_profit_ratio": self.fee_to_profit_ratio,
            "savings_rate": self.savings_rate,
            "metadata": self.metadata
        }


# ====================================================================================
# FEE COMPARISON MODELS
# ====================================================================================

@dataclass
class FeeComparison:
    """
    Fee comparison across multiple exchanges.
    """
    # Core fields
    comparison_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    base_asset: str = ""
    quote_asset: str = ""
    
    # Trade parameters
    trade_amount: float = 0.0
    trade_price: float = 1.0
    trade_value: float = 0.0
    is_maker: bool = True
    
    # Exchange fees
    exchange_fees: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Best and worst
    best_exchange: str = ""
    best_fee: float = 0.0
    worst_exchange: str = ""
    worst_fee: float = 0.0
    average_fee: float = 0.0
    
    # Savings potential
    max_savings: float = 0.0
    max_savings_percentage: float = 0.0
    
    # Timestamps
    compared_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.exchange_fees:
            self._calculate_metrics()
            
    def _calculate_metrics(self) -> None:
        """Calculate comparison metrics."""
        fees = []
        for exchange, data in self.exchange_fees.items():
            fee = data.get("fee_amount", 0.0)
            fees.append(fee)
            if not self.best_exchange or fee < self.best_fee:
                self.best_exchange = exchange
                self.best_fee = fee
            if not self.worst_exchange or fee > self.worst_fee:
                self.worst_exchange = exchange
                self.worst_fee = fee
                
        if fees:
            self.average_fee = sum(fees) / len(fees)
            self.max_savings = self.worst_fee - self.best_fee
            self.max_savings_percentage = (self.max_savings / self.worst_fee * 100) if self.worst_fee > 0 else 0
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "trade_amount": self.trade_amount,
            "trade_price": self.trade_price,
            "trade_value": self.trade_value,
            "is_maker": self.is_maker,
            "exchange_fees": self.exchange_fees,
            "best_exchange": self.best_exchange,
            "best_fee": self.best_fee,
            "worst_exchange": self.worst_exchange,
            "worst_fee": self.worst_fee,
            "average_fee": self.average_fee,
            "max_savings": self.max_savings,
            "max_savings_percentage": self.max_savings_percentage,
            "compared_at": self.compared_at.isoformat(),
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_fee_impact(
    fee_rate: float,
    trade_value: float,
    price_impact: float = 0.0,
    is_arbitrage: bool = False
) -> Dict[str, float]:
    """
    Calculate the impact of fees on a trade.
    
    Args:
        fee_rate: Fee rate (e.g., 0.001 for 0.1%)
        trade_value: Trade value in quote currency
        price_impact: Expected price impact (as decimal)
        is_arbitrage: Whether this is an arbitrage trade
        
    Returns:
        Impact metrics
    """
    fee_amount = trade_value * fee_rate
    
    # For arbitrage, fees are paid on both sides
    if is_arbitrage:
        fee_amount *= 2
        
    total_impact = fee_amount + (trade_value * price_impact)
    
    return {
        "fee_amount": fee_amount,
        "price_impact": price_impact,
        "price_impact_amount": trade_value * price_impact,
        "total_impact": total_impact,
        "impact_percentage": (total_impact / trade_value) * 100
    }


def calculate_break_even_spread(
    fee_rate: float,
    is_arbitrage: bool = True,
    other_costs: float = 0.0
) -> float:
    """
    Calculate break-even spread for arbitrage.
    
    Args:
        fee_rate: Fee rate (e.g., 0.001 for 0.1%)
        is_arbitrage: Whether this is an arbitrage trade
        other_costs: Other costs (gas, withdrawal, etc.)
        
    Returns:
        Minimum spread required to break even (as percentage)
    """
    total_fee = fee_rate * (2 if is_arbitrage else 1)
    return (total_fee + other_costs) * 100


def calculate_optimal_tier(
    monthly_volume: float,
    fee_schedule: FeeSchedule,
    balance: float = 0.0
) -> FeeTier:
    """
    Calculate the optimal fee tier for a given volume.
    
    Args:
        monthly_volume: Monthly trading volume
        fee_schedule: Fee schedule
        balance: Current balance
        
    Returns:
        Optimal FeeTier
    """
    best_tier = fee_schedule.default_tier
    best_savings = 0.0
    
    for tier in fee_schedule.tiers:
        if tier.qualifies(monthly_volume, balance):
            # Calculate savings for this tier
            maker_savings = tier.get_savings(monthly_volume * 0.5, True)
            taker_savings = tier.get_savings(monthly_volume * 0.5, False)
            total_savings = maker_savings + taker_savings
            
            if total_savings > best_savings:
                best_savings = total_savings
                best_tier = tier
                
    return best_tier


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'FeeTierType',
    'FeeDiscountType',
    'FeeCurrency',
    'FeeCalculationMethod',
    
    # Core Models
    'FeeTier',
    'FeeSchedule',
    'FeeCalculation',
    'FeeHistoryEntry',
    'FeeAnalytics',
    'FeeComparison',
    
    # Helper Functions
    'calculate_fee_impact',
    'calculate_break_even_spread',
    'calculate_optimal_tier',
]
