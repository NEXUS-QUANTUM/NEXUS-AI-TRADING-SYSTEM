# trading/bots/arbitrage_bot/models/balance.py
# NEXUS AI TRADING SYSTEM - BALANCE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for balance tracking, portfolio management,
# and asset allocation across multiple exchanges and wallets.
# ====================================================================================

"""
NEXUS Arbitrage Bot Balance Models

This module provides comprehensive data models for:
- Exchange balance tracking and synchronization
- Portfolio aggregation across multiple exchanges
- Asset allocation and position sizing
- PnL calculation and performance tracking
- Real-time balance monitoring and alerts
- Historical balance tracking and reporting
- Cross-exchange balance reconciliation
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

class BalanceType(str, Enum):
    """Types of balance entries."""
    AVAILABLE = "available"
    LOCKED = "locked"
    TOTAL = "total"
    FROZEN = "frozen"
    PENDING = "pending"
    MARGIN = "margin"
    COLLATERAL = "collateral"
    CROSS_MARGIN = "cross_margin"
    ISOLATED_MARGIN = "isolated_margin"
    UNREALIZED_PNL = "unrealized_pnl"
    REALIZED_PNL = "realized_pnl"


class AssetType(str, Enum):
    """Asset classification types."""
    CRYPTO = "crypto"
    STABLE = "stable"
    COMMODITY = "commodity"
    FIXED_INCOME = "fixed_income"
    EQUITY = "equity"
    DERIVATIVE = "derivative"
    CURRENCY = "currency"
    TOKEN = "token"
    NFT = "nft"


class AssetCategory(str, Enum):
    """Asset categories for classification."""
    # Crypto Assets
    BTC = "btc"
    ETH = "eth"
    ALTCOIN = "altcoin"
    DEFI = "defi"
    MEME = "meme"
    LAYER1 = "layer1"
    LAYER2 = "layer2"
    
    # Stablecoins
    FIAT_BACKED = "fiat_backed"
    CRYPTO_BACKED = "crypto_backed"
    ALGORITHMIC = "algorithmic"
    SYNTHETIC = "synthetic"
    
    # Trading Categories
    BASE = "base"
    QUOTE = "quote"
    SETTLEMENT = "settlement"
    
    # Risk Categories
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    EXTREME_RISK = "extreme_risk"


class BalanceChangeType(str, Enum):
    """Types of balance changes."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    FEE = "fee"
    REWARD = "reward"
    STAKING = "staking"
    UNSTAKING = "unstaking"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    AIRDROP = "airdrop"
    MANUAL = "manual"
    REBALANCE = "rebalance"
    CONVERSION = "conversion"
    BORROW = "borrow"
    REPAY = "repay"
    LIQUIDATION = "liquidation"
    FUNDING_PAYMENT = "funding_payment"
    FUNDING_RECEIPT = "funding_receipt"


class PositionSide(str, Enum):
    """Position direction."""
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class MarginType(str, Enum):
    """Margin types for leveraged trading."""
    CROSS = "cross"
    ISOLATED = "isolated"
    PORTFOLIO = "portfolio"


# ====================================================================================
# BALANCE DATA MODELS
# ====================================================================================

@dataclass
class Balance:
    """
    Core balance model representing an asset balance on a specific exchange.
    """
    # Core fields
    asset: str = ""
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    
    # Additional fields
    frozen: float = 0.0
    pending: float = 0.0
    margin: float = 0.0
    collateral: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    # Metadata
    exchange: str = ""
    account_id: str = ""
    wallet_id: str = ""
    asset_type: AssetType = AssetType.CRYPTO
    asset_category: AssetCategory = AssetCategory.ALTCOIN
    
    # Pricing
    usd_value: float = 0.0
    btc_value: float = 0.0
    eth_value: float = 0.0
    price: float = 0.0
    price_updated_at: Optional[datetime] = None
    
    # Timestamps
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metrics
    available_percentage: float = 100.0
    locked_percentage: float = 0.0
    frozen_percentage: float = 0.0
    
    # Risk
    risk_level: float = 0.0
    volatility: float = 0.0
    liquidity_score: float = 1.0
    
    # Custom data
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.total = self.free + self.locked
        self.available_percentage = (self.free / self.total * 100) if self.total > 0 else 100.0
        self.locked_percentage = (self.locked / self.total * 100) if self.total > 0 else 0.0
        self.frozen_percentage = (self.frozen / self.total * 100) if self.total > 0 else 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "asset": self.asset,
            "free": self.free,
            "locked": self.locked,
            "total": self.total,
            "frozen": self.frozen,
            "pending": self.pending,
            "margin": self.margin,
            "collateral": self.collateral,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "exchange": self.exchange,
            "account_id": self.account_id,
            "wallet_id": self.wallet_id,
            "asset_type": self.asset_type.value if self.asset_type else None,
            "asset_category": self.asset_category.value if self.asset_category else None,
            "usd_value": self.usd_value,
            "btc_value": self.btc_value,
            "eth_value": self.eth_value,
            "price": self.price,
            "price_updated_at": self.price_updated_at.isoformat() if self.price_updated_at else None,
            "updated_at": self.updated_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "available_percentage": self.available_percentage,
            "locked_percentage": self.locked_percentage,
            "frozen_percentage": self.frozen_percentage,
            "risk_level": self.risk_level,
            "volatility": self.volatility,
            "liquidity_score": self.liquidity_score,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Balance":
        """Create balance from dictionary."""
        balance = cls(
            asset=data.get("asset", ""),
            free=data.get("free", 0.0),
            locked=data.get("locked", 0.0),
            total=data.get("total", 0.0),
            frozen=data.get("frozen", 0.0),
            pending=data.get("pending", 0.0),
            margin=data.get("margin", 0.0),
            collateral=data.get("collateral", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            exchange=data.get("exchange", ""),
            account_id=data.get("account_id", ""),
            wallet_id=data.get("wallet_id", ""),
            asset_type=AssetType(data.get("asset_type", "crypto")),
            asset_category=AssetCategory(data.get("asset_category", "altcoin")),
            usd_value=data.get("usd_value", 0.0),
            btc_value=data.get("btc_value", 0.0),
            eth_value=data.get("eth_value", 0.0),
            price=data.get("price", 0.0),
            risk_level=data.get("risk_level", 0.0),
            volatility=data.get("volatility", 0.0),
            liquidity_score=data.get("liquidity_score", 1.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("price_updated_at"):
            balance.price_updated_at = datetime.fromisoformat(data["price_updated_at"])
        if data.get("updated_at"):
            balance.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("created_at"):
            balance.created_at = datetime.fromisoformat(data["created_at"])
            
        return balance
        
    def update(self, **kwargs) -> None:
        """Update balance fields."""
        for key, value in kwargs.items():
            if key == "free":
                self.free = value
            elif key == "locked":
                self.locked = value
            elif key == "frozen":
                self.frozen = value
            elif key == "pending":
                self.pending = value
            elif key == "unrealized_pnl":
                self.unrealized_pnl = value
            elif key == "realized_pnl":
                self.realized_pnl = value
            elif key == "price":
                self.price = value
                self.price_updated_at = datetime.utcnow()
            elif key == "usd_value":
                self.usd_value = value
            else:
                setattr(self, key, value)
        self.__post_init__()
        self.updated_at = datetime.utcnow()
        
    def add(self, amount: float, change_type: BalanceChangeType = BalanceChangeType.DEPOSIT) -> None:
        """Add to free balance."""
        self.free += amount
        self.total = self.free + self.locked
        self.__post_init__()
        self.updated_at = datetime.utcnow()
        
    def lock(self, amount: float) -> None:
        """Lock an amount (move from free to locked)."""
        if amount > self.free:
            raise ValueError(f"Insufficient free balance: {self.free} < {amount}")
        self.free -= amount
        self.locked += amount
        self.total = self.free + self.locked
        self.__post_init__()
        self.updated_at = datetime.utcnow()
        
    def unlock(self, amount: float) -> None:
        """Unlock an amount (move from locked to free)."""
        if amount > self.locked:
            raise ValueError(f"Insufficient locked balance: {self.locked} < {amount}")
        self.locked -= amount
        self.free += amount
        self.total = self.free + self.locked
        self.__post_init__()
        self.updated_at = datetime.utcnow()
        
    def apply_pnl(self, pnl: float) -> None:
        """Apply PnL to balance."""
        self.unrealized_pnl += pnl
        if pnl > 0:
            self.free += pnl
        else:
            self.free += pnl  # pnl is negative
        self.total = self.free + self.locked
        self.__post_init__()
        self.updated_at = datetime.utcnow()
        
    def is_positive(self) -> bool:
        """Check if balance is positive."""
        return self.total > 0
        
    def is_zero(self) -> bool:
        """Check if balance is zero."""
        return self.total == 0
        
    def get_available(self) -> float:
        """Get available (free) balance."""
        return self.free
        
    def get_locked(self) -> float:
        """Get locked balance."""
        return self.locked
        
    def get_total(self) -> float:
        """Get total balance."""
        return self.total
        
    def get_usd_value(self) -> float:
        """Get USD value."""
        return self.usd_value
        
    def get_btc_value(self) -> float:
        """Get BTC value."""
        return self.btc_value
        
    def get_eth_value(self) -> float:
        """Get ETH value."""
        return self.eth_value


@dataclass
class BalanceDelta:
    """Represents a change in balance."""
    asset: str = ""
    exchange: str = ""
    amount: float = 0.0
    change_type: BalanceChangeType = BalanceChangeType.DEPOSIT
    previous_balance: float = 0.0
    new_balance: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    transaction_id: str = ""
    order_id: str = ""
    trade_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "asset": self.asset,
            "exchange": self.exchange,
            "amount": self.amount,
            "change_type": self.change_type.value if self.change_type else None,
            "previous_balance": self.previous_balance,
            "new_balance": self.new_balance,
            "timestamp": self.timestamp.isoformat(),
            "transaction_id": self.transaction_id,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "metadata": self.metadata
        }
        
    def is_deposit(self) -> bool:
        """Check if this is a deposit."""
        return self.change_type == BalanceChangeType.DEPOSIT
        
    def is_withdrawal(self) -> bool:
        """Check if this is a withdrawal."""
        return self.change_type == BalanceChangeType.WITHDRAWAL
        
    def is_trade(self) -> bool:
        """Check if this is a trade."""
        return self.change_type in [BalanceChangeType.TRADE_BUY, BalanceChangeType.TRADE_SELL]
        
    def is_increase(self) -> bool:
        """Check if balance increased."""
        return self.amount > 0
        
    def is_decrease(self) -> bool:
        """Check if balance decreased."""
        return self.amount < 0


# ====================================================================================
# PORTFOLIO MODELS
# ====================================================================================

@dataclass
class Portfolio:
    """
    Aggregated portfolio across multiple exchanges and accounts.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    
    # Balances by exchange
    exchange_balances: Dict[str, Dict[str, Balance]] = field(default_factory=dict)
    
    # Aggregated balances by asset
    total_balances: Dict[str, Balance] = field(default_factory=dict)
    
    # Performance
    total_usd_value: float = 0.0
    total_btc_value: float = 0.0
    total_eth_value: float = 0.0
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    
    # Allocation
    asset_allocation: Dict[str, float] = field(default_factory=dict)
    exchange_allocation: Dict[str, float] = field(default_factory=dict)
    category_allocation: Dict[str, float] = field(default_factory=dict)
    risk_allocation: Dict[str, float] = field(default_factory=dict)
    
    # Metrics
    total_trades: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    snapshot_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "exchange_balances": {
                exchange: {asset: balance.to_dict() for asset, balance in balances.items()}
                for exchange, balances in self.exchange_balances.items()
            },
            "total_balances": {
                asset: balance.to_dict() for asset, balance in self.total_balances.items()
            },
            "total_usd_value": self.total_usd_value,
            "total_btc_value": self.total_btc_value,
            "total_eth_value": self.total_eth_value,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "monthly_pnl": self.monthly_pnl,
            "asset_allocation": self.asset_allocation,
            "exchange_allocation": self.exchange_allocation,
            "category_allocation": self.category_allocation,
            "risk_allocation": self.risk_allocation,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "snapshot_at": self.snapshot_at.isoformat() if self.snapshot_at else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        """Create portfolio from dictionary."""
        portfolio = cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", "")
        )
        
        # Parse exchange balances
        for exchange, balances in data.get("exchange_balances", {}).items():
            portfolio.exchange_balances[exchange] = {
                asset: Balance.from_dict(balance_data)
                for asset, balance_data in balances.items()
            }
            
        # Parse total balances
        for asset, balance_data in data.get("total_balances", {}).items():
            portfolio.total_balances[asset] = Balance.from_dict(balance_data)
            
        # Set fields
        portfolio.total_usd_value = data.get("total_usd_value", 0.0)
        portfolio.total_btc_value = data.get("total_btc_value", 0.0)
        portfolio.total_eth_value = data.get("total_eth_value", 0.0)
        portfolio.total_unrealized_pnl = data.get("total_unrealized_pnl", 0.0)
        portfolio.total_realized_pnl = data.get("total_realized_pnl", 0.0)
        portfolio.daily_pnl = data.get("daily_pnl", 0.0)
        portfolio.weekly_pnl = data.get("weekly_pnl", 0.0)
        portfolio.monthly_pnl = data.get("monthly_pnl", 0.0)
        portfolio.asset_allocation = data.get("asset_allocation", {})
        portfolio.exchange_allocation = data.get("exchange_allocation", {})
        portfolio.category_allocation = data.get("category_allocation", {})
        portfolio.risk_allocation = data.get("risk_allocation", {})
        portfolio.total_trades = data.get("total_trades", 0)
        portfolio.win_rate = data.get("win_rate", 0.0)
        portfolio.sharpe_ratio = data.get("sharpe_ratio", 0.0)
        portfolio.max_drawdown = data.get("max_drawdown", 0.0)
        portfolio.current_drawdown = data.get("current_drawdown", 0.0)
        portfolio.metadata = data.get("metadata", {})
        
        # Parse timestamps
        if data.get("created_at"):
            portfolio.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            portfolio.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("snapshot_at"):
            portfolio.snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            
        return portfolio
        
    def add_balance(self, balance: Balance) -> None:
        """
        Add or update a balance in the portfolio.
        
        Args:
            balance: Balance to add
        """
        exchange = balance.exchange
        asset = balance.asset
        
        # Update exchange balance
        if exchange not in self.exchange_balances:
            self.exchange_balances[exchange] = {}
        self.exchange_balances[exchange][asset] = balance
        
        # Update total balance
        if asset not in self.total_balances:
            self.total_balances[asset] = Balance(asset=asset)
        total_balance = self.total_balances[asset]
        total_balance.free += balance.free
        total_balance.locked += balance.locked
        total_balance.total = total_balance.free + total_balance.locked
        total_balance.usd_value += balance.usd_value
        total_balance.btc_value += balance.btc_value
        total_balance.eth_value += balance.eth_value
        
        # Update portfolio metrics
        self._update_metrics()
        
        self.updated_at = datetime.utcnow()
        
    def remove_exchange(self, exchange: str) -> None:
        """Remove all balances for an exchange."""
        if exchange in self.exchange_balances:
            # Remove from total balances
            for asset, balance in self.exchange_balances[exchange].items():
                if asset in self.total_balances:
                    total_balance = self.total_balances[asset]
                    total_balance.free -= balance.free
                    total_balance.locked -= balance.locked
                    total_balance.total = total_balance.free + total_balance.locked
                    total_balance.usd_value -= balance.usd_value
                    total_balance.btc_value -= balance.btc_value
                    total_balance.eth_value -= balance.eth_value
                    if total_balance.total == 0:
                        del self.total_balances[asset]
                        
            # Remove exchange
            del self.exchange_balances[exchange]
            
            self._update_metrics()
            self.updated_at = datetime.utcnow()
            
    def _update_metrics(self) -> None:
        """Update portfolio metrics."""
        # Calculate total values
        self.total_usd_value = sum(b.usd_value for b in self.total_balances.values())
        self.total_btc_value = sum(b.btc_value for b in self.total_balances.values())
        self.total_eth_value = sum(b.eth_value for b in self.total_balances.values())
        self.total_unrealized_pnl = sum(b.unrealized_pnl for b in self.total_balances.values())
        self.total_realized_pnl = sum(b.realized_pnl for b in self.total_balances.values())
        
        # Calculate allocations
        if self.total_usd_value > 0:
            self.asset_allocation = {
                asset: (balance.usd_value / self.total_usd_value * 100)
                for asset, balance in self.total_balances.items()
            }
            
            self.exchange_allocation = {
                exchange: sum(b.usd_value for b in balances.values()) / self.total_usd_value * 100
                for exchange, balances in self.exchange_balances.items()
            }
            
            self.category_allocation = {}
            for balance in self.total_balances.values():
                category = balance.asset_category.value if balance.asset_category else "other"
                self.category_allocation[category] = self.category_allocation.get(category, 0) + balance.usd_value
            for category in self.category_allocation:
                self.category_allocation[category] /= self.total_usd_value
                self.category_allocation[category] *= 100
                
            self.risk_allocation = {}
            for balance in self.total_balances.values():
                risk_level = f"risk_{int(balance.risk_level)}"
                self.risk_allocation[risk_level] = self.risk_allocation.get(risk_level, 0) + balance.usd_value
            for risk in self.risk_allocation:
                self.risk_allocation[risk] /= self.total_usd_value
                self.risk_allocation[risk] *= 100
                
    def get_asset_value(self, asset: str) -> float:
        """Get the USD value of an asset."""
        if asset in self.total_balances:
            return self.total_balances[asset].usd_value
        return 0.0
        
    def get_exchange_value(self, exchange: str) -> float:
        """Get the total USD value for an exchange."""
        if exchange in self.exchange_balances:
            return sum(b.usd_value for b in self.exchange_balances[exchange].values())
        return 0.0
        
    def get_allocation(self, asset: str) -> float:
        """Get the allocation percentage for an asset."""
        if self.total_usd_value > 0 and asset in self.total_balances:
            return self.total_balances[asset].usd_value / self.total_usd_value * 100
        return 0.0
        
    def get_concentration(self, threshold: float = 20.0) -> List[Tuple[str, float]]:
        """
        Get assets with concentration above threshold.
        
        Args:
            threshold: Percentage threshold
            
        Returns:
            List of (asset, percentage) tuples
        """
        concentrated = []
        for asset, percentage in self.asset_allocation.items():
            if percentage > threshold:
                concentrated.append((asset, percentage))
        return sorted(concentrated, key=lambda x: x[1], reverse=True)
        
    def get_portfolio_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the portfolio."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_usd_value": self.total_usd_value,
            "total_btc_value": self.total_btc_value,
            "total_eth_value": self.total_eth_value,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "asset_count": len(self.total_balances),
            "exchange_count": len(self.exchange_balances),
            "asset_allocation": self.asset_allocation,
            "exchange_allocation": self.exchange_allocation,
            "top_assets": sorted(
                [(asset, balance.usd_value) for asset, balance in self.total_balances.items()],
                key=lambda x: x[1], reverse=True
            )[:10]
        }


# ====================================================================================
# POSITION MODELS
# ====================================================================================

@dataclass
class Position:
    """
    Trading position model for tracking open positions.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    side: PositionSide = PositionSide.NEUTRAL
    entry_price: float = 0.0
    current_price: float = 0.0
    mark_price: float = 0.0
    liquidation_price: float = 0.0
    size: float = 0.0
    initial_size: float = 0.0
    leverage: float = 1.0
    margin: float = 0.0
    margin_type: MarginType = MarginType.CROSS
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    entry_time: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    is_open: bool = True
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value if self.side else None,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "mark_price": self.mark_price,
            "liquidation_price": self.liquidation_price,
            "size": self.size,
            "initial_size": self.initial_size,
            "leverage": self.leverage,
            "margin": self.margin,
            "margin_type": self.margin_type.value if self.margin_type else None,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "entry_time": self.entry_time.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "is_open": self.is_open,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create position from dictionary."""
        position = cls(
            id=data.get("id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            side=PositionSide(data.get("side", "neutral")),
            entry_price=data.get("entry_price", 0.0),
            current_price=data.get("current_price", 0.0),
            mark_price=data.get("mark_price", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            size=data.get("size", 0.0),
            initial_size=data.get("initial_size", 0.0),
            leverage=data.get("leverage", 1.0),
            margin=data.get("margin", 0.0),
            margin_type=MarginType(data.get("margin_type", "cross")),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            is_open=data.get("is_open", True),
            stop_loss=data.get("stop_loss", 0.0),
            take_profit=data.get("take_profit", 0.0),
            trailing_stop=data.get("trailing_stop", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("entry_time"):
            position.entry_time = datetime.fromisoformat(data["entry_time"])
        if data.get("updated_at"):
            position.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("closed_at"):
            position.closed_at = datetime.fromisoformat(data["closed_at"])
            
        return position
        
    def update_price(self, price: float) -> None:
        """Update current price and recalculate PnL."""
        self.current_price = price
        if self.size != 0 and self.entry_price != 0:
            if self.side == PositionSide.LONG:
                self.unrealized_pnl = (price - self.entry_price) * self.size
            elif self.side == PositionSide.SHORT:
                self.unrealized_pnl = (self.entry_price - price) * self.size
        self.updated_at = datetime.utcnow()
        
    def close(self, exit_price: float, pnl: float) -> None:
        """Close the position."""
        self.current_price = exit_price
        self.realized_pnl += pnl
        self.is_open = False
        self.closed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
    def get_pnl_percentage(self) -> float:
        """Get PnL as a percentage of entry value."""
        if self.entry_price == 0 or self.size == 0:
            return 0.0
        entry_value = self.entry_price * self.size
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100
            
    def get_roe(self) -> float:
        """Get Return on Equity (margin)."""
        if self.margin == 0:
            return 0.0
        return self.unrealized_pnl / self.margin * 100


# ====================================================================================
# BALANCE HISTORY MODELS
# ====================================================================================

@dataclass
class BalanceHistoryEntry:
    """Historical balance record."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    asset: str = ""
    exchange: str = ""
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    usd_value: float = 0.0
    price: float = 0.0
    snapshot_id: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "asset": self.asset,
            "exchange": self.exchange,
            "free": self.free,
            "locked": self.locked,
            "total": self.total,
            "usd_value": self.usd_value,
            "price": self.price,
            "snapshot_id": self.snapshot_id
        }


@dataclass
class BalanceSnapshot:
    """
    Snapshot of all balances at a point in time.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    balances: Dict[str, Balance] = field(default_factory=dict)
    portfolio: Optional[Portfolio] = None
    total_usd_value: float = 0.0
    total_btc_value: float = 0.0
    total_eth_value: float = 0.0
    asset_count: int = 0
    exchange_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "balances": {asset: balance.to_dict() for asset, balance in self.balances.items()},
            "total_usd_value": self.total_usd_value,
            "total_btc_value": self.total_btc_value,
            "total_eth_value": self.total_eth_value,
            "asset_count": self.asset_count,
            "exchange_count": self.exchange_count
        }


# ====================================================================================
# UTILITY FUNCTIONS
# ====================================================================================

def calculate_allocation(
    balances: Dict[str, Balance],
    total_value: float = None
) -> Dict[str, float]:
    """
    Calculate allocation percentages for a set of balances.
    
    Args:
        balances: Dictionary of asset -> Balance
        total_value: Total value (calculated if not provided)
        
    Returns:
        Dictionary of asset -> allocation percentage
    """
    if total_value is None:
        total_value = sum(b.usd_value for b in balances.values())
        
    if total_value == 0:
        return {asset: 0.0 for asset in balances}
        
    return {asset: (balance.usd_value / total_value * 100) for asset, balance in balances.items()}


def calculate_asset_concentration(
    balances: Dict[str, Balance],
    top_n: int = 5
) -> List[Tuple[str, float]]:
    """
    Calculate asset concentration (top N assets).
    
    Args:
        balances: Dictionary of asset -> Balance
        top_n: Number of top assets to return
        
    Returns:
        List of (asset, percentage) tuples
    """
    total_value = sum(b.usd_value for b in balances.values())
    if total_value == 0:
        return []
        
    sorted_assets = sorted(
        [(asset, balance.usd_value) for asset, balance in balances.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    return [(asset, value / total_value * 100) for asset, value in sorted_assets[:top_n]]


def calculate_diversification_score(balances: Dict[str, Balance]) -> float:
    """
    Calculate diversification score (0-1, higher is better).
    
    Args:
        balances: Dictionary of asset -> Balance
        
    Returns:
        Diversification score
    """
    if not balances:
        return 1.0
        
    total_value = sum(b.usd_value for b in balances.values())
    if total_value == 0:
        return 1.0
        
    # Calculate Herfindahl-Hirschman Index (HHI)
    hhi = sum((b.usd_value / total_value) ** 2 for b in balances.values())
    
    # Convert HHI to diversification score (1 - HHI)
    return 1 - hhi


def calculate_herfindahl_hirschman_index(balances: Dict[str, Balance]) -> float:
    """
    Calculate Herfindahl-Hirschman Index (HHI) for balance concentration.
    
    Args:
        balances: Dictionary of asset -> Balance
        
    Returns:
        HHI score (0-1)
    """
    total_value = sum(b.usd_value for b in balances.values())
    if total_value == 0:
        return 0.0
        
    return sum((b.usd_value / total_value) ** 2 for b in balances.values())


def get_risk_level(balance: Balance) -> str:
    """
    Get risk level label for a balance.
    
    Args:
        balance: Balance object
        
    Returns:
        Risk level label
    """
    if balance.risk_level < 0.2:
        return "very_low"
    elif balance.risk_level < 0.4:
        return "low"
    elif balance.risk_level < 0.6:
        return "medium"
    elif balance.risk_level < 0.8:
        return "high"
    else:
        return "very_high"


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'BalanceType',
    'AssetType',
    'AssetCategory',
    'BalanceChangeType',
    'PositionSide',
    'MarginType',
    
    # Core Models
    'Balance',
    'BalanceDelta',
    'Portfolio',
    'Position',
    'BalanceHistoryEntry',
    'BalanceSnapshot',
    
    # Utility Functions
    'calculate_allocation',
    'calculate_asset_concentration',
    'calculate_diversification_score',
    'calculate_herfindahl_hirschman_index',
    'get_risk_level',
]
