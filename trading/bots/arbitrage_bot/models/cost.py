# trading/bots/arbitrage_bot/models/cost.py
# NEXUS AI TRADING SYSTEM - COST MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for cost tracking, fee calculation,
# slippage estimation, and overall trading cost management for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Cost Models

This module provides comprehensive data models for:
- Trading fees (maker/taker, exchange-specific)
- Gas fees (Ethereum, BSC, Polygon, etc.)
- Slippage calculation and estimation
- Cost of carry and funding rates
- Total cost of execution analysis
- Profitability calculations
- Fee optimization and routing
- Historical cost tracking and reporting
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

class FeeType(str, Enum):
    """Types of trading fees."""
    MAKER = "maker"
    TAKER = "taker"
    POST_ONLY = "post_only"
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    OCO = "oco"
    TWAP = "twap"
    ICEBERG = "iceberg"
    TRAILING_STOP = "trailing_stop"
    TP_SL = "tp_sl"
    REDUCE_ONLY = "reduce_only"


class GasType(str, Enum):
    """Types of gas costs."""
    ETH = "eth"           # Ethereum
    BNB = "bnb"           # BSC
    MATIC = "matic"       # Polygon
    AVAX = "avax"         # Avalanche
    FTM = "ftm"           # Fantom
    ARB = "arb"           # Arbitrum
    OP = "op"             # Optimism
    SOL = "sol"           # Solana
    NEAR = "near"         # NEAR
    DOT = "dot"           # Polkadot
    ATOM = "atom"         # Cosmos
    XRP = "xrp"           # XRP Ledger
    ADA = "ada"           # Cardano
    ALGO = "algo"         # Algorand
    VET = "vet"           # VeChain
    CRO = "cro"           # Cronos
    HBAR = "hbar"         # Hedera
    ONE = "one"           # Harmony
    ELROND = "egld"       # Elrond
    THETA = "theta"       # Theta
    STX = "stx"           # Stacks
    ATOM = "atom"         # Cosmos


class SlippageType(str, Enum):
    """Types of slippage calculations."""
    EXPECTED = "expected"
    ACTUAL = "actual"
    MAXIMUM = "maximum"
    MINIMUM = "minimum"
    AVERAGE = "average"
    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"
    BASIS_POINTS = "basis_points"


class CostCategory(str, Enum):
    """Categories for cost classification."""
    TRADING_FEE = "trading_fee"
    GAS_FEE = "gas_fee"
    BRIDGE_FEE = "bridge_fee"
    WITHDRAWAL_FEE = "withdrawal_fee"
    DEPOSIT_FEE = "deposit_fee"
    FUNDING_COST = "funding_cost"
    BORROW_COST = "borrow_cost"
    SLIPPAGE_COST = "slippage_cost"
    SPREAD_COST = "spread_cost"
    CARRY_COST = "carry_cost"
    EXCHANGE_FEE = "exchange_fee"
    NETWORK_FEE = "network_fee"
    ACCOUNT_MAINTENANCE = "account_maintenance"
    INACTIVITY_FEE = "inactivity_fee"
    SETTLEMENT_FEE = "settlement_fee"
    TAX_COST = "tax_cost"
    REGULATORY_COST = "regulatory_cost"
    OPPORTUNITY_COST = "opportunity_cost"
    LIQUIDATION_COST = "liquidation_cost"
    MARGIN_COST = "margin_cost"
    INTEREST_COST = "interest_cost"


class FeeStructure(str, Enum):
    """Fee structure types."""
    TIERED = "tiered"
    FLAT = "flat"
    PERCENTAGE = "percentage"
    HYBRID = "hybrid"
    DYNAMIC = "dynamic"
    VOLUME_BASED = "volume_based"
    VIP = "vip"
    BESPOKE = "bespoke"


# ====================================================================================
# COST DATA MODELS
# ====================================================================================

@dataclass
class Fee:
    """
    Represents a trading fee for a specific exchange and fee type.
    """
    # Core fields
    exchange: str = ""
    fee_type: FeeType = FeeType.MAKER
    fee_rate: float = 0.0
    fee_amount: float = 0.0
    fee_currency: str = "USDT"
    base_amount: float = 0.0
    
    # Tier information
    tier_level: int = 0
    tier_name: str = ""
    volume_30d: float = 0.0
    volume_30d_currency: str = "USDT"
    
    # Fee structure
    fee_structure: FeeStructure = FeeStructure.TIERED
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    is_maker: bool = True
    is_taker: bool = False
    
    # Discounts
    has_discount: bool = False
    discount_rate: float = 0.0
    discount_type: str = ""  # BNB, FTT, etc.
    discount_amount: float = 0.0
    
    # Payment
    payment_method: str = ""  # credit, debit, crypto, etc.
    payment_currency: str = "USDT"
    payment_amount: float = 0.0
    exchange_rate: float = 1.0
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        if self.fee_amount == 0 and self.fee_rate > 0 and self.base_amount > 0:
            self.fee_amount = self.base_amount * self.fee_rate
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "fee_type": self.fee_type.value if self.fee_type else None,
            "fee_rate": self.fee_rate,
            "fee_amount": self.fee_amount,
            "fee_currency": self.fee_currency,
            "base_amount": self.base_amount,
            "tier_level": self.tier_level,
            "tier_name": self.tier_name,
            "volume_30d": self.volume_30d,
            "volume_30d_currency": self.volume_30d_currency,
            "fee_structure": self.fee_structure.value if self.fee_structure else None,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "is_maker": self.is_maker,
            "is_taker": self.is_taker,
            "has_discount": self.has_discount,
            "discount_rate": self.discount_rate,
            "discount_type": self.discount_type,
            "discount_amount": self.discount_amount,
            "payment_method": self.payment_method,
            "payment_currency": self.payment_currency,
            "payment_amount": self.payment_amount,
            "exchange_rate": self.exchange_rate,
            "timestamp": self.timestamp.isoformat(),
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fee":
        """Create fee from dictionary."""
        fee = cls(
            exchange=data.get("exchange", ""),
            fee_type=FeeType(data.get("fee_type", "maker")),
            fee_rate=data.get("fee_rate", 0.0),
            fee_amount=data.get("fee_amount", 0.0),
            fee_currency=data.get("fee_currency", "USDT"),
            base_amount=data.get("base_amount", 0.0),
            tier_level=data.get("tier_level", 0),
            tier_name=data.get("tier_name", ""),
            volume_30d=data.get("volume_30d", 0.0),
            volume_30d_currency=data.get("volume_30d_currency", "USDT"),
            fee_structure=FeeStructure(data.get("fee_structure", "tiered")),
            maker_fee=data.get("maker_fee", 0.0),
            taker_fee=data.get("taker_fee", 0.0),
            is_maker=data.get("is_maker", True),
            is_taker=data.get("is_taker", False),
            has_discount=data.get("has_discount", False),
            discount_rate=data.get("discount_rate", 0.0),
            discount_type=data.get("discount_type", ""),
            discount_amount=data.get("discount_amount", 0.0),
            payment_method=data.get("payment_method", ""),
            payment_currency=data.get("payment_currency", "USDT"),
            payment_amount=data.get("payment_amount", 0.0),
            exchange_rate=data.get("exchange_rate", 1.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("timestamp"):
            fee.timestamp = datetime.fromisoformat(data["timestamp"])
        if data.get("start_date"):
            fee.start_date = datetime.fromisoformat(data["start_date"])
        if data.get("end_date"):
            fee.end_date = datetime.fromisoformat(data["end_date"])
            
        return fee
        
    def calculate_fee(self, amount: float, price: float = 1.0) -> float:
        """
        Calculate fee for a given trade amount.
        
        Args:
            amount: Trade amount in base currency
            price: Price of asset in fee currency
            
        Returns:
            Fee amount in fee currency
        """
        value = amount * price
        return value * self.fee_rate
        
    def apply_discount(self) -> float:
        """Apply discount to fee amount."""
        if not self.has_discount:
            return self.fee_amount
        return self.fee_amount * (1 - self.discount_rate)
        
    def get_effective_rate(self) -> float:
        """Get effective fee rate after discounts."""
        if not self.has_discount:
            return self.fee_rate
        return self.fee_rate * (1 - self.discount_rate)


@dataclass
class GasCost:
    """
    Represents gas costs for blockchain transactions.
    """
    # Core fields
    chain: GasType = GasType.ETH
    gas_price: float = 0.0
    gas_limit: int = 0
    gas_used: int = 0
    total_gas: float = 0.0
    total_cost: float = 0.0
    cost_currency: str = "USD"
    
    # Units
    gas_unit: str = "gwei"
    cost_unit: str = "USD"
    
    # Transaction details
    transaction_hash: str = ""
    from_address: str = ""
    to_address: str = ""
    transaction_type: str = ""  # transfer, swap, bridge, etc.
    status: str = "pending"  # pending, success, failed
    
    # Priority
    priority: str = "standard"  # low, standard, high, urgent
    priority_multiplier: float = 1.0
    
    # Market conditions
    base_gas_price: float = 0.0
    max_priority_fee: float = 0.0
    max_fee_per_gas: float = 0.0
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    mined_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.total_gas = self.gas_used * self.gas_price
        self.total_cost = self.total_gas * self.gas_price / 1e9  # Convert gwei to native
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chain": self.chain.value if self.chain else None,
            "gas_price": self.gas_price,
            "gas_limit": self.gas_limit,
            "gas_used": self.gas_used,
            "total_gas": self.total_gas,
            "total_cost": self.total_cost,
            "cost_currency": self.cost_currency,
            "gas_unit": self.gas_unit,
            "cost_unit": self.cost_unit,
            "transaction_hash": self.transaction_hash,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "transaction_type": self.transaction_type,
            "status": self.status,
            "priority": self.priority,
            "priority_multiplier": self.priority_multiplier,
            "base_gas_price": self.base_gas_price,
            "max_priority_fee": self.max_priority_fee,
            "max_fee_per_gas": self.max_fee_per_gas,
            "timestamp": self.timestamp.isoformat(),
            "mined_at": self.mined_at.isoformat() if self.mined_at else None,
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GasCost":
        """Create gas cost from dictionary."""
        cost = cls(
            chain=GasType(data.get("chain", "eth")),
            gas_price=data.get("gas_price", 0.0),
            gas_limit=data.get("gas_limit", 0),
            gas_used=data.get("gas_used", 0),
            total_gas=data.get("total_gas", 0.0),
            total_cost=data.get("total_cost", 0.0),
            cost_currency=data.get("cost_currency", "USD"),
            gas_unit=data.get("gas_unit", "gwei"),
            cost_unit=data.get("cost_unit", "USD"),
            transaction_hash=data.get("transaction_hash", ""),
            from_address=data.get("from_address", ""),
            to_address=data.get("to_address", ""),
            transaction_type=data.get("transaction_type", ""),
            status=data.get("status", "pending"),
            priority=data.get("priority", "standard"),
            priority_multiplier=data.get("priority_multiplier", 1.0),
            base_gas_price=data.get("base_gas_price", 0.0),
            max_priority_fee=data.get("max_priority_fee", 0.0),
            max_fee_per_gas=data.get("max_fee_per_gas", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("timestamp"):
            cost.timestamp = datetime.fromisoformat(data["timestamp"])
        if data.get("mined_at"):
            cost.mined_at = datetime.fromisoformat(data["mined_at"])
        if data.get("confirmed_at"):
            cost.confirmed_at = datetime.fromisoformat(data["confirmed_at"])
            
        return cost
        
    def estimate_cost(self, gas_price: Optional[float] = None) -> float:
        """Estimate transaction cost."""
        if gas_price is None:
            gas_price = self.gas_price
        return gas_price * self.gas_limit / 1e9
        
    def is_successful(self) -> bool:
        """Check if transaction was successful."""
        return self.status == "success"
        
    def get_cost_in_usd(self, price: float = 1.0) -> float:
        """Get cost in USD."""
        return self.total_cost * price
        
    def get_cost_in_native(self) -> float:
        """Get cost in native currency."""
        return self.total_cost


@dataclass
class Slippage:
    """
    Represents slippage for a trade execution.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    expected_price: float = 0.0
    execution_price: float = 0.0
    slippage_amount: float = 0.0
    slippage_percentage: float = 0.0
    slippage_type: SlippageType = SlippageType.ACTUAL
    side: str = "buy"  # buy, sell
    
    # Trade details
    order_size: float = 0.0
    order_value: float = 0.0
    expected_value: float = 0.0
    actual_value: float = 0.0
    order_type: str = "market"
    
    # Market conditions
    market_volatility: float = 0.0
    bid_ask_spread: float = 0.0
    order_book_depth: float = 0.0
    liquidity_score: float = 0.0
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.slippage_amount = self.execution_price - self.expected_price
        if self.expected_price != 0:
            self.slippage_percentage = self.slippage_amount / self.expected_price * 100
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "expected_price": self.expected_price,
            "execution_price": self.execution_price,
            "slippage_amount": self.slippage_amount,
            "slippage_percentage": self.slippage_percentage,
            "slippage_type": self.slippage_type.value if self.slippage_type else None,
            "side": self.side,
            "order_size": self.order_size,
            "order_value": self.order_value,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "order_type": self.order_type,
            "market_volatility": self.market_volatility,
            "bid_ask_spread": self.bid_ask_spread,
            "order_book_depth": self.order_book_depth,
            "liquidity_score": self.liquidity_score,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Slippage":
        """Create slippage from dictionary."""
        slippage = cls(
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            expected_price=data.get("expected_price", 0.0),
            execution_price=data.get("execution_price", 0.0),
            slippage_amount=data.get("slippage_amount", 0.0),
            slippage_percentage=data.get("slippage_percentage", 0.0),
            slippage_type=SlippageType(data.get("slippage_type", "actual")),
            side=data.get("side", "buy"),
            order_size=data.get("order_size", 0.0),
            order_value=data.get("order_value", 0.0),
            expected_value=data.get("expected_value", 0.0),
            actual_value=data.get("actual_value", 0.0),
            order_type=data.get("order_type", "market"),
            market_volatility=data.get("market_volatility", 0.0),
            bid_ask_spread=data.get("bid_ask_spread", 0.0),
            order_book_depth=data.get("order_book_depth", 0.0),
            liquidity_score=data.get("liquidity_score", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            slippage.timestamp = datetime.fromisoformat(data["timestamp"])
            
        return slippage
        
    def is_positive_slippage(self) -> bool:
        """Check if slippage is positive (favorable)."""
        return self.slippage_amount > 0
        
    def is_negative_slippage(self) -> bool:
        """Check if slippage is negative (unfavorable)."""
        return self.slippage_amount < 0
        
    def get_impact(self) -> float:
        """Get the impact of slippage on order value."""
        return self.actual_value - self.expected_value
        
    def is_acceptable(self, max_slippage: float) -> bool:
        """Check if slippage is within acceptable range."""
        return abs(self.slippage_percentage) <= max_slippage


@dataclass
class TotalCost:
    """
    Aggregated total cost for a trade or set of trades.
    """
    # Core fields
    trade_id: str = ""
    strategy: str = ""
    symbol: str = ""
    
    # Cost components
    trading_fees: List[Fee] = field(default_factory=list)
    gas_costs: List[GasCost] = field(default_factory=list)
    slippage_costs: List[Slippage] = field(default_factory=list)
    bridge_fees: List[Fee] = field(default_factory=list)
    withdrawal_fees: List[Fee] = field(default_factory=list)
    deposit_fees: List[Fee] = field(default_factory=list)
    funding_costs: List[Fee] = field(default_factory=list)
    other_costs: List[Fee] = field(default_factory=list)
    
    # Totals
    total_trading_fees: float = 0.0
    total_gas_costs: float = 0.0
    total_slippage_costs: float = 0.0
    total_bridge_fees: float = 0.0
    total_withdrawal_fees: float = 0.0
    total_deposit_fees: float = 0.0
    total_funding_costs: float = 0.0
    total_other_costs: float = 0.0
    total_net_cost: float = 0.0
    
    # Currency
    currency: str = "USDT"
    
    # Profitability
    gross_profit: float = 0.0
    net_profit: float = 0.0
    profit_after_costs: float = 0.0
    cost_percentage: float = 0.0
    profit_percentage: float = 0.0
    
    # Timestamps
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate totals and derived fields."""
        self._calculate_totals()
        
    def _calculate_totals(self) -> None:
        """Calculate all totals from cost components."""
        self.total_trading_fees = sum(f.fee_amount for f in self.trading_fees)
        self.total_gas_costs = sum(g.total_cost for g in self.gas_costs)
        self.total_slippage_costs = abs(sum(s.slippage_amount for s in self.slippage_costs))
        self.total_bridge_fees = sum(f.fee_amount for f in self.bridge_fees)
        self.total_withdrawal_fees = sum(f.fee_amount for f in self.withdrawal_fees)
        self.total_deposit_fees = sum(f.fee_amount for f in self.deposit_fees)
        self.total_funding_costs = sum(f.fee_amount for f in self.funding_costs)
        self.total_other_costs = sum(f.fee_amount for f in self.other_costs)
        
        self.total_net_cost = (
            self.total_trading_fees +
            self.total_gas_costs +
            self.total_slippage_costs +
            self.total_bridge_fees +
            self.total_withdrawal_fees +
            self.total_deposit_fees +
            self.total_funding_costs +
            self.total_other_costs
        )
        
        # Profitability
        self.net_profit = self.gross_profit - self.total_net_cost
        self.profit_after_costs = self.net_profit
        if self.gross_profit > 0:
            self.cost_percentage = self.total_net_cost / self.gross_profit * 100
            self.profit_percentage = self.net_profit / self.gross_profit * 100
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "trading_fees": [f.to_dict() for f in self.trading_fees],
            "gas_costs": [g.to_dict() for g in self.gas_costs],
            "slippage_costs": [s.to_dict() for s in self.slippage_costs],
            "bridge_fees": [f.to_dict() for f in self.bridge_fees],
            "withdrawal_fees": [f.to_dict() for f in self.withdrawal_fees],
            "deposit_fees": [f.to_dict() for f in self.deposit_fees],
            "funding_costs": [f.to_dict() for f in self.funding_costs],
            "other_costs": [f.to_dict() for f in self.other_costs],
            "total_trading_fees": self.total_trading_fees,
            "total_gas_costs": self.total_gas_costs,
            "total_slippage_costs": self.total_slippage_costs,
            "total_bridge_fees": self.total_bridge_fees,
            "total_withdrawal_fees": self.total_withdrawal_fees,
            "total_deposit_fees": self.total_deposit_fees,
            "total_funding_costs": self.total_funding_costs,
            "total_other_costs": self.total_other_costs,
            "total_net_cost": self.total_net_cost,
            "currency": self.currency,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "profit_after_costs": self.profit_after_costs,
            "cost_percentage": self.cost_percentage,
            "profit_percentage": self.profit_percentage,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TotalCost":
        """Create total cost from dictionary."""
        cost = cls(
            trade_id=data.get("trade_id", ""),
            strategy=data.get("strategy", ""),
            symbol=data.get("symbol", ""),
            trading_fees=[Fee.from_dict(f) for f in data.get("trading_fees", [])],
            gas_costs=[GasCost.from_dict(g) for g in data.get("gas_costs", [])],
            slippage_costs=[Slippage.from_dict(s) for s in data.get("slippage_costs", [])],
            bridge_fees=[Fee.from_dict(f) for f in data.get("bridge_fees", [])],
            withdrawal_fees=[Fee.from_dict(f) for f in data.get("withdrawal_fees", [])],
            deposit_fees=[Fee.from_dict(f) for f in data.get("deposit_fees", [])],
            funding_costs=[Fee.from_dict(f) for f in data.get("funding_costs", [])],
            other_costs=[Fee.from_dict(f) for f in data.get("other_costs", [])],
            gross_profit=data.get("gross_profit", 0.0),
            currency=data.get("currency", "USDT"),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("start_time"):
            cost.start_time = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            cost.end_time = datetime.fromisoformat(data["end_time"])
            
        cost._calculate_totals()
        return cost
        
    def add_trading_fee(self, fee: Fee) -> None:
        """Add a trading fee to the total."""
        self.trading_fees.append(fee)
        self._calculate_totals()
        
    def add_gas_cost(self, gas: GasCost) -> None:
        """Add a gas cost to the total."""
        self.gas_costs.append(gas)
        self._calculate_totals()
        
    def add_slippage(self, slippage: Slippage) -> None:
        """Add slippage to the total."""
        self.slippage_costs.append(slippage)
        self._calculate_totals()
        
    def get_breakdown(self) -> Dict[str, float]:
        """Get detailed cost breakdown."""
        return {
            "trading_fees": self.total_trading_fees,
            "gas_costs": self.total_gas_costs,
            "slippage_costs": self.total_slippage_costs,
            "bridge_fees": self.total_bridge_fees,
            "withdrawal_fees": self.total_withdrawal_fees,
            "deposit_fees": self.total_deposit_fees,
            "funding_costs": self.total_funding_costs,
            "other_costs": self.total_other_costs,
            "total": self.total_net_cost
        }
        
    def get_cost_by_category(self, category: CostCategory) -> float:
        """Get total cost for a specific category."""
        category_map = {
            CostCategory.TRADING_FEE: self.total_trading_fees,
            CostCategory.GAS_FEE: self.total_gas_costs,
            CostCategory.SLIPPAGE_COST: self.total_slippage_costs,
            CostCategory.BRIDGE_FEE: self.total_bridge_fees,
            CostCategory.WITHDRAWAL_FEE: self.total_withdrawal_fees,
            CostCategory.DEPOSIT_FEE: self.total_deposit_fees,
            CostCategory.FUNDING_COST: self.total_funding_costs,
        }
        return category_map.get(category, 0.0)
        
    def is_profitable(self) -> bool:
        """Check if the trade is profitable after all costs."""
        return self.net_profit > 0
        
    def get_profit_margin(self) -> float:
        """Get profit margin percentage."""
        if self.gross_profit == 0:
            return 0.0
        return self.net_profit / self.gross_profit * 100


# ====================================================================================
# FEE STRUCTURE MODELS
# ====================================================================================

@dataclass
class FeeTier:
    """Fee tier for volume-based pricing."""
    tier_level: int = 0
    tier_name: str = ""
    min_volume: float = 0.0
    max_volume: float = float('inf')
    volume_currency: str = "USDT"
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    discount_rate: float = 0.0
    qualification_period: int = 30  # days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tier_level": self.tier_level,
            "tier_name": self.tier_name,
            "min_volume": self.min_volume,
            "max_volume": self.max_volume,
            "volume_currency": self.volume_currency,
            "maker_fee": self.maker_fee,
            "taker_fee": self.taker_fee,
            "discount_rate": self.discount_rate,
            "qualification_period": self.qualification_period
        }


@dataclass
class FeeSchedule:
    """Complete fee schedule for an exchange."""
    exchange: str = ""
    fee_structure: FeeStructure = FeeStructure.TIERED
    tiers: List[FeeTier] = field(default_factory=list)
    default_maker_fee: float = 0.001
    default_taker_fee: float = 0.001
    current_tier: int = 0
    current_maker_fee: float = 0.001
    current_taker_fee: float = 0.001
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_fee(self, volume: float, is_maker: bool = True) -> float:
        """Get fee rate for a given volume."""
        for tier in self.tiers:
            if tier.min_volume <= volume <= tier.max_volume:
                return tier.maker_fee if is_maker else tier.taker_fee
        return self.default_maker_fee if is_maker else self.default_taker_fee
        
    def get_tier(self, volume: float) -> Optional[FeeTier]:
        """Get the fee tier for a given volume."""
        for tier in self.tiers:
            if tier.min_volume <= volume <= tier.max_volume:
                return tier
        return None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "fee_structure": self.fee_structure.value if self.fee_structure else None,
            "tiers": [t.to_dict() for t in self.tiers],
            "default_maker_fee": self.default_maker_fee,
            "default_taker_fee": self.default_taker_fee,
            "current_tier": self.current_tier,
            "current_maker_fee": self.current_maker_fee,
            "current_taker_fee": self.current_taker_fee,
            "updated_at": self.updated_at.isoformat()
        }


# ====================================================================================
# COST ANALYSIS MODELS
# ====================================================================================

@dataclass
class CostAnalysis:
    """
    Comprehensive cost analysis for trading activities.
    """
    # Period
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Costs by category
    costs_by_category: Dict[CostCategory, float] = field(default_factory=dict)
    costs_by_exchange: Dict[str, float] = field(default_factory=dict)
    costs_by_symbol: Dict[str, float] = field(default_factory=dict)
    costs_by_strategy: Dict[str, float] = field(default_factory=dict)
    
    # Totals
    total_cost: float = 0.0
    total_trades: int = 0
    total_volume: float = 0.0
    total_fees: float = 0.0
    total_gas: float = 0.0
    total_slippage: float = 0.0
    
    # Efficiency metrics
    cost_per_trade: float = 0.0
    cost_per_unit_volume: float = 0.0
    fee_percentage: float = 0.0
    slippage_percentage: float = 0.0
    gas_percentage: float = 0.0
    
    # Profitability
    total_profit: float = 0.0
    net_profit: float = 0.0
    profit_margin: float = 0.0    cost_to_profit_ratio: float = 0.0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "costs_by_category": {k.value: v for k, v in self.costs_by_category.items()},
            "costs_by_exchange": self.costs_by_exchange,
            "costs_by_symbol": self.costs_by_symbol,
            "costs_by_strategy": self.costs_by_strategy,
            "total_cost": self.total_cost,
            "total_trades": self.total_trades,
            "total_volume": self.total_volume,
            "total_fees": self.total_fees,
            "total_gas": self.total_gas,
            "total_slippage": self.total_slippage,
            "cost_per_trade": self.cost_per_trade,
            "cost_per_unit_volume": self.cost_per_unit_volume,
            "fee_percentage": self.fee_percentage,
            "slippage_percentage": self.slippage_percentage,
            "gas_percentage": self.gas_percentage,
            "total_profit": self.total_profit,
            "net_profit": self.net_profit,
            "profit_margin": self.profit_margin,
            "cost_to_profit_ratio": self.cost_to_profit_ratio,
            "recommendations": self.recommendations
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_cost_effectiveness(
    profit: float,
    cost: float,
    volume: float
) -> Dict[str, float]:
    """
    Calculate cost effectiveness metrics.
    
    Args:
        profit: Total profit
        cost: Total cost
        volume: Total volume
        
    Returns:
        Dict of metrics
    """
    return {
        "cost_per_unit_profit": cost / profit if profit > 0 else float('inf'),
        "profit_per_unit_cost": profit / cost if cost > 0 else float('inf'),
        "cost_per_unit_volume": cost / volume if volume > 0 else 0,
        "profit_per_unit_volume": profit / volume if volume > 0 else 0,
        "profit_margin": (profit - cost) / profit * 100 if profit > 0 else 0
    }


def calculate_break_even_price(
    entry_price: float,
    fee_rate: float,
    target_profit: float = 0.0
) -> float:
    """
    Calculate break-even price for a trade.
    
    Args:
        entry_price: Entry price
        fee_rate: Fee rate (both sides)
        target_profit: Target profit percentage
        
    Returns:
        Break-even price
    """
    return entry_price * (1 + fee_rate + target_profit / 100)


def calculate_effective_cost(
    fees: List[Fee],
    gas_costs: List[GasCost],
    slippage: List[Slippage]
) -> float:
    """
    Calculate total effective cost.
    
    Args:
        fees: List of fees
        gas_costs: List of gas costs
        slippage: List of slippage
        
    Returns:
        Total effective cost
    """
    total = 0.0
    total += sum(f.fee_amount for f in fees)
    total += sum(g.total_cost for g in gas_costs)
    total += abs(sum(s.slippage_amount for s in slippage))
    return total


def calculate_profit_after_costs(
    gross_profit: float,
    fees: List[Fee],
    gas_costs: List[GasCost],
    slippage: List[Slippage]
) -> float:
    """
    Calculate profit after all costs.
    
    Args:
        gross_profit: Gross profit
        fees: List of fees
        gas_costs: List of gas costs
        slippage: List of slippage
        
    Returns:
        Net profit after costs
    """
    total_cost = calculate_effective_cost(fees, gas_costs, slippage)
    return gross_profit - total_cost


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'FeeType',
    'GasType',
    'SlippageType',
    'CostCategory',
    'FeeStructure',
    
    # Core Models
    'Fee',
    'GasCost',
    'Slippage',
    'TotalCost',
    'FeeTier',
    'FeeSchedule',
    'CostAnalysis',
    
    # Helper Functions
    'calculate_cost_effectiveness',
    'calculate_break_even_price',
    'calculate_effective_cost',
    'calculate_profit_after_costs',
]
