# trading/bots/arbitrage_bot/models/portfolio.py
# NEXUS AI TRADING SYSTEM - PORTFOLIO MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for portfolio management, asset allocation,
# risk management, and performance tracking across multiple exchanges and strategies.
# ====================================================================================

"""
NEXUS Arbitrage Bot Portfolio Models

This module provides comprehensive data models for:
- Portfolio composition and asset allocation
- Risk management and position sizing
- Performance tracking and analytics
- Multi-exchange portfolio aggregation
- Rebalancing and optimization
- Portfolio metrics and KPIs
- Compliance and limits management
- Portfolio history and snapshots
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

class PortfolioStatus(str, Enum):
    """Status of a portfolio."""
    ACTIVE = "active"                    # Portfolio is active
    PAUSED = "paused"                    # Temporarily paused
    CLOSED = "closed"                    # Portfolio is closed
    ARCHIVED = "archived"                # Archived for historical reference
    UNDER_REVIEW = "under_review"        # Under review for compliance
    BREACHED = "breached"                # Risk limits breached


class AllocationType(str, Enum):
    """Types of asset allocation."""
    STRATEGIC = "strategic"              # Long-term strategic allocation
    TACTICAL = "tactical"                # Short-term tactical allocation
    DYNAMIC = "dynamic"                  # Dynamic adaptive allocation
    STATIC = "static"                    # Fixed allocation
    TARGET = "target"                    # Target allocation
    ACTUAL = "actual"                    # Actual current allocation


class RiskProfile(str, Enum):
    """Risk profiles for portfolio management."""
    CONSERVATIVE = "conservative"        # Low risk, low return
    MODERATE = "moderate"                # Moderate risk, moderate return
    AGGRESSIVE = "aggressive"            # High risk, high return
    VERY_AGGRESSIVE = "very_aggressive"  # Very high risk, very high return
    CUSTOM = "custom"                    # Custom risk profile


class PortfolioCategory(str, Enum):
    """Categories of portfolios."""
    ARBITRAGE = "arbitrage"              # Arbitrage portfolio
    HEDGE = "hedge"                      # Hedging portfolio
    SPECULATIVE = "speculative"          # Speculative trading
    BALANCED = "balanced"                # Balanced portfolio
    GROWTH = "growth"                    # Growth oriented
    INCOME = "income"                    # Income oriented
    ALPHA = "alpha"                      # Alpha generation
    BETA = "beta"                        # Beta exposure


class RebalanceTrigger(str, Enum):
    """Triggers for portfolio rebalancing."""
    TIME_BASED = "time_based"            # Scheduled rebalancing
    THRESHOLD = "threshold"              # Threshold-based rebalancing
    VOLATILITY = "volatility"            # Volatility-based rebalancing
    EVENT_DRIVEN = "event_driven"        # Event-driven rebalancing
    MANUAL = "manual"                    # Manual rebalancing
    OPPORTUNITY = "opportunity"          # Opportunity-based rebalancing


class LimitType(str, Enum):
    """Types of portfolio limits."""
    POSITION_SIZE = "position_size"      # Maximum position size
    CONCENTRATION = "concentration"      # Maximum concentration
    LEVERAGE = "leverage"                # Maximum leverage
    DRAWDOWN = "drawdown"                # Maximum drawdown
    VAR = "var"                          # Value at Risk limit
    VOLATILITY = "volatility"            # Volatility limit
    SECTOR = "sector"                    # Sector exposure limit
    ASSET = "asset"                      # Asset exposure limit
    EXCHANGE = "exchange"                # Exchange exposure limit


# ====================================================================================
# PORTFOLIO ALLOCATION MODELS
# ====================================================================================

@dataclass
class AssetAllocation:
    """
    Asset allocation for a portfolio.
    """
    # Core fields
    asset: str = ""
    target_weight: float = 0.0            # Target weight (percentage)
    current_weight: float = 0.0           # Current weight (percentage)
    min_weight: float = 0.0               # Minimum weight allowed
    max_weight: float = 1.0               # Maximum weight allowed
    allocation_type: AllocationType = AllocationType.TARGET
    
    # Value metrics
    target_value: float = 0.0             # Target value in base currency
    current_value: float = 0.0            # Current value in base currency
    min_value: float = 0.0                # Minimum value allowed
    max_value: float = 0.0                # Maximum value allowed
    
    # Performance
    return_ytd: float = 0.0               # Year-to-date return
    return_1m: float = 0.0                # 1-month return
    return_1w: float = 0.0                # 1-week return
    return_1d: float = 0.0                # 1-day return
    
    # Risk metrics
    volatility: float = 0.0               # Volatility
    sharpe_ratio: float = 0.0             # Sharpe ratio
    max_drawdown: float = 0.0             # Maximum drawdown
    
    # Status
    is_overweight: bool = False           # Whether asset is overweight
    is_underweight: bool = False          # Whether asset is underweight
    deviation: float = 0.0                # Deviation from target
    deviation_percentage: float = 0.0     # Deviation percentage
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.deviation = self.current_weight - self.target_weight
        self.deviation_percentage = (self.deviation / self.target_weight * 100) if self.target_weight > 0 else 0
        self.is_overweight = self.deviation > 0 and abs(self.deviation) > 0.01
        self.is_underweight = self.deviation < 0 and abs(self.deviation) > 0.01
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "asset": self.asset,
            "target_weight": self.target_weight,
            "current_weight": self.current_weight,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "allocation_type": self.allocation_type.value if self.allocation_type else None,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "return_ytd": self.return_ytd,
            "return_1m": self.return_1m,
            "return_1w": self.return_1w,
            "return_1d": self.return_1d,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "is_overweight": self.is_overweight,
            "is_underweight": self.is_underweight,
            "deviation": self.deviation,
            "deviation_percentage": self.deviation_percentage,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetAllocation":
        """Create from dictionary."""
        allocation = cls(
            asset=data.get("asset", ""),
            target_weight=data.get("target_weight", 0.0),
            current_weight=data.get("current_weight", 0.0),
            min_weight=data.get("min_weight", 0.0),
            max_weight=data.get("max_weight", 1.0),
            allocation_type=AllocationType(data["allocation_type"]) if data.get("allocation_type") else AllocationType.TARGET,
            target_value=data.get("target_value", 0.0),
            current_value=data.get("current_value", 0.0),
            min_value=data.get("min_value", 0.0),
            max_value=data.get("max_value", 0.0),
            return_ytd=data.get("return_ytd", 0.0),
            return_1m=data.get("return_1m", 0.0),
            return_1w=data.get("return_1w", 0.0),
            return_1d=data.get("return_1d", 0.0),
            volatility=data.get("volatility", 0.0),
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            metadata=data.get("metadata", {})
        )
        allocation.__post_init__()
        return allocation
        
    def update_current_weight(self, total_value: float) -> None:
        """Update current weight based on current value and total value."""
        if total_value > 0:
            self.current_weight = self.current_value / total_value
        else:
            self.current_weight = 0.0
        self.__post_init__()
        
    def is_within_limits(self) -> bool:
        """Check if allocation is within limits."""
        return self.min_weight <= self.current_weight <= self.max_weight


# ====================================================================================
# PORTFOLIO MODELS
# ====================================================================================

@dataclass
class Portfolio:
    """
    Comprehensive portfolio model.
    """
    # Core fields
    portfolio_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    status: PortfolioStatus = PortfolioStatus.ACTIVE
    category: PortfolioCategory = PortfolioCategory.ARBITRAGE
    risk_profile: RiskProfile = RiskProfile.MODERATE
    
    # Base currency
    base_currency: str = "USDT"
    
    # Allocation
    allocations: Dict[str, AssetAllocation] = field(default_factory=dict)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    total_profit_percentage: float = 0.0
    
    # Performance
    performance_ytd: float = 0.0
    performance_1m: float = 0.0
    performance_1w: float = 0.0
    performance_1d: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    # Risk limits
    risk_limits: Dict[str, float] = field(default_factory=dict)
    breaches: List[Dict[str, Any]] = field(default_factory=list)
    
    # Rebalancing
    rebalance_trigger: RebalanceTrigger = RebalanceTrigger.THRESHOLD
    rebalance_threshold: float = 0.05      # 5% deviation threshold
    rebalance_frequency: int = 24          # Hours between rebalances
    last_rebalance: Optional[datetime] = None
    
    # Trading
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    # Fees and costs
    total_fees: float = 0.0
    total_gas: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0
    
    # Exchange exposure
    exchange_exposure: Dict[str, float] = field(default_factory=dict)
    max_exchange_exposure: float = 0.3     # 30% max per exchange
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    snapshot_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "portfolio_id": self.portfolio_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value if self.status else None,
            "category": self.category.value if self.category else None,
            "risk_profile": self.risk_profile.value if self.risk_profile else None,
            "base_currency": self.base_currency,
            "allocations": {asset: alloc.to_dict() for asset, alloc in self.allocations.items()},
            "total_value": self.total_value,
            "total_cost": self.total_cost,
            "total_profit": self.total_profit,
            "total_profit_percentage": self.total_profit_percentage,
            "performance_ytd": self.performance_ytd,
            "performance_1m": self.performance_1m,
            "performance_1w": self.performance_1w,
            "performance_1d": self.performance_1d,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "volatility": self.volatility,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "beta": self.beta,
            "alpha": self.alpha,
            "risk_limits": self.risk_limits,
            "breaches": self.breaches,
            "rebalance_trigger": self.rebalance_trigger.value if self.rebalance_trigger else None,
            "rebalance_threshold": self.rebalance_threshold,
            "rebalance_frequency": self.rebalance_frequency,
            "last_rebalance": self.last_rebalance.isoformat() if self.last_rebalance else None,
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "total_fees": self.total_fees,
            "total_gas": self.total_gas,
            "total_slippage": self.total_slippage,
            "total_costs": self.total_costs,
            "exchange_exposure": self.exchange_exposure,
            "max_exchange_exposure": self.max_exchange_exposure,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "snapshot_at": self.snapshot_at.isoformat() if self.snapshot_at else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Portfolio":
        """Create from dictionary."""
        portfolio = cls(
            portfolio_id=data.get("portfolio_id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=PortfolioStatus(data["status"]) if data.get("status") else PortfolioStatus.ACTIVE,
            category=PortfolioCategory(data["category"]) if data.get("category") else PortfolioCategory.ARBITRAGE,
            risk_profile=RiskProfile(data["risk_profile"]) if data.get("risk_profile") else RiskProfile.MODERATE,
            base_currency=data.get("base_currency", "USDT"),
            total_value=data.get("total_value", 0.0),
            total_cost=data.get("total_cost", 0.0),
            total_profit=data.get("total_profit", 0.0),
            total_profit_percentage=data.get("total_profit_percentage", 0.0),
            performance_ytd=data.get("performance_ytd", 0.0),
            performance_1m=data.get("performance_1m", 0.0),
            performance_1w=data.get("performance_1w", 0.0),
            performance_1d=data.get("performance_1d", 0.0),
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            sortino_ratio=data.get("sortino_ratio", 0.0),
            calmar_ratio=data.get("calmar_ratio", 0.0),
            volatility=data.get("volatility", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            current_drawdown=data.get("current_drawdown", 0.0),
            var_95=data.get("var_95", 0.0),
            cvar_95=data.get("cvar_95", 0.0),
            beta=data.get("beta", 0.0),
            alpha=data.get("alpha", 0.0),
            risk_limits=data.get("risk_limits", {}),
            breaches=data.get("breaches", []),
            rebalance_trigger=RebalanceTrigger(data["rebalance_trigger"]) if data.get("rebalance_trigger") else RebalanceTrigger.THRESHOLD,
            rebalance_threshold=data.get("rebalance_threshold", 0.05),
            rebalance_frequency=data.get("rebalance_frequency", 24),
            total_trades=data.get("total_trades", 0),
            successful_trades=data.get("successful_trades", 0),
            failed_trades=data.get("failed_trades", 0),
            win_rate=data.get("win_rate", 0.0),
            avg_win=data.get("avg_win", 0.0),
            avg_loss=data.get("avg_loss", 0.0),
            total_fees=data.get("total_fees", 0.0),
            total_gas=data.get("total_gas", 0.0),
            total_slippage=data.get("total_slippage", 0.0),
            total_costs=data.get("total_costs", 0.0),
            exchange_exposure=data.get("exchange_exposure", {}),
            max_exchange_exposure=data.get("max_exchange_exposure", 0.3),
            metadata=data.get("metadata", {})
        )
        
        # Parse allocations
        for asset, alloc_data in data.get("allocations", {}).items():
            portfolio.allocations[asset] = AssetAllocation.from_dict(alloc_data)
            
        # Parse timestamps
        if data.get("created_at"):
            portfolio.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            portfolio.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("last_rebalance"):
            portfolio.last_rebalance = datetime.fromisoformat(data["last_rebalance"])
        if data.get("snapshot_at"):
            portfolio.snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            
        return portfolio
        
    def add_allocation(self, allocation: AssetAllocation) -> None:
        """
        Add or update asset allocation.
        
        Args:
            allocation: Asset allocation to add
        """
        self.allocations[allocation.asset] = allocation
        self._update_metrics()
        self.updated_at = datetime.utcnow()
        
    def remove_allocation(self, asset: str) -> None:
        """
        Remove asset allocation.
        
        Args:
            asset: Asset to remove
        """
        if asset in self.allocations:
            del self.allocations[asset]
            self._update_metrics()
            self.updated_at = datetime.utcnow()
            
    def _update_metrics(self) -> None:
        """Update portfolio metrics."""
        if not self.allocations:
            self.total_value = 0.0
            self.total_cost = 0.0
            self.total_profit = 0.0
            return
            
        # Calculate total values
        self.total_value = sum(alloc.current_value for alloc in self.allocations.values())
        self.total_cost = sum(alloc.target_value for alloc in self.allocations.values())
        self.total_profit = self.total_value - self.total_cost
        self.total_profit_percentage = (self.total_profit / self.total_cost * 100) if self.total_cost > 0 else 0
        
        # Update weights
        for alloc in self.allocations.values():
            alloc.update_current_weight(self.total_value)
            
        # Update exchange exposure
        self.exchange_exposure = {}
        for asset, alloc in self.allocations.items():
            # This would need exchange mapping from the asset metadata
            exchange = alloc.metadata.get("exchange", "unknown")
            self.exchange_exposure[exchange] = self.exchange_exposure.get(exchange, 0) + alloc.current_weight
            
    def update_asset_value(self, asset: str, current_value: float, current_price: float = 0.0) -> None:
        """
        Update value for a specific asset.
        
        Args:
            asset: Asset name
            current_value: Current value in base currency
            current_price: Current price (optional)
        """
        if asset in self.allocations:
            self.allocations[asset].current_value = current_value
            if current_price > 0:
                self.allocations[asset].metadata["current_price"] = current_price
            self._update_metrics()
            self.updated_at = datetime.utcnow()
            
    def calculate_risk_metrics(self) -> None:
        """Calculate risk metrics."""
        if not self.allocations:
            return
            
        # Calculate weighted volatility
        weighted_volatility = 0.0
        for alloc in self.allocations.values():
            weight = alloc.current_weight
            if weight > 0:
                weighted_volatility += weight * alloc.volatility
        self.volatility = weighted_volatility
        
        # Calculate Sharpe ratio (assuming risk-free rate of 2%)
        risk_free_rate = 0.02
        excess_return = self.performance_1m - (risk_free_rate / 12)
        if self.volatility > 0:
            self.sharpe_ratio = excess_return / self.volatility
            
        # Calculate Sortino ratio
        downside_volatility = self.volatility * 0.7  # Approximation
        if downside_volatility > 0:
            self.sortino_ratio = excess_return / downside_volatility
            
        # Calculate Calmar ratio
        if self.max_drawdown > 0:
            self.calmar_ratio = self.performance_ytd / self.max_drawdown
            
        # VaR and CVaR (parametric)
        z_score = 1.645  # 95% confidence
        self.var_95 = self.volatility * z_score * self.total_value
        self.cvar_95 = self.var_95 * 1.2  # Approximation
        
    def calculate_drawdown(self) -> float:
        """
        Calculate current drawdown from peak.
        
        Returns:
            Current drawdown percentage
        """
        if not self.allocations:
            return 0.0
            
        peak_value = max(alloc.current_value for alloc in self.allocations.values())
        current_value = self.total_value
        
        if peak_value > 0:
            self.current_drawdown = (peak_value - current_value) / peak_value * 100
            
        return self.current_drawdown
        
    def check_risk_limits(self) -> List[Dict[str, Any]]:
        """
        Check portfolio against risk limits.
        
        Returns:
            List of breaches
        """
        breaches = []
        
        # Check position size limits
        for asset, alloc in self.allocations.items():
            if alloc.current_weight > self.risk_limits.get("max_position_size", 1.0):
                breaches.append({
                    "type": "position_size",
                    "asset": asset,
                    "current": alloc.current_weight,
                    "limit": self.risk_limits.get("max_position_size"),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
        # Check concentration
        total_value = self.total_value
        for asset, alloc in self.allocations.items():
            if total_value > 0:
                concentration = alloc.current_value / total_value
                if concentration > self.risk_limits.get("max_concentration", 0.2):
                    breaches.append({
                        "type": "concentration",
                        "asset": asset,
                        "current": concentration * 100,
                        "limit": self.risk_limits.get("max_concentration") * 100,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
        # Check drawdown
        drawdown = self.calculate_drawdown()
        if drawdown > self.risk_limits.get("max_drawdown", 20.0):
            breaches.append({
                "type": "drawdown",
                "current": drawdown,
                "limit": self.risk_limits.get("max_drawdown"),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        # Check VaR
        if self.var_95 > self.risk_limits.get("max_var", 0.1):
            breaches.append({
                "type": "var",
                "current": self.var_95,
                "limit": self.risk_limits.get("max_var"),
                "timestamp": datetime.utcnow().isoformat()
            })
            
        self.breaches = breaches
        if breaches:
            self.status = PortfolioStatus.BREACHED
            
        return breaches
        
    def needs_rebalance(self) -> bool:
        """
        Check if portfolio needs rebalancing.
        
        Returns:
            True if rebalancing needed
        """
        if self.rebalance_trigger == RebalanceTrigger.TIME_BASED:
            if not self.last_rebalance:
                return True
            hours_since = (datetime.utcnow() - self.last_rebalance).total_seconds() / 3600
            return hours_since >= self.rebalance_frequency
            
        elif self.rebalance_trigger == RebalanceTrigger.THRESHOLD:
            for alloc in self.allocations.values():
                if abs(alloc.deviation) > self.rebalance_threshold:
                    return True
                    
        elif self.rebalance_trigger == RebalanceTrigger.VOLATILITY:
            if self.volatility > 0.5:  # 50% volatility threshold
                return True
                
        elif self.rebalance_trigger == RebalanceTrigger.OPPORTUNITY:
            # Check for arbitrage opportunities
            if any(alloc.deviation > 0.1 for alloc in self.allocations.values()):
                return True
                
        return False
        
    def get_allocation_summary(self) -> Dict[str, Any]:
        """
        Get summary of allocations.
        
        Returns:
            Allocation summary
        """
        return {
            "total_assets": len(self.allocations),
            "total_value": self.total_value,
            "total_profit": self.total_profit,
            "profit_percentage": self.total_profit_percentage,
            "largest_allocation": max(self.allocations.values(), key=lambda x: x.current_weight),
            "smallest_allocation": min(self.allocations.values(), key=lambda x: x.current_weight),
            "concentration": max(alloc.current_weight for alloc in self.allocations.values()),
            "diversification": 1 - sum(alloc.current_weight ** 2 for alloc in self.allocations.values()),
            "overweight_assets": [a for a in self.allocations.values() if a.is_overweight],
            "underweight_assets": [a for a in self.allocations.values() if a.is_underweight]
        }


# ====================================================================================
# PORTFOLIO SNAPSHOT MODELS
# ====================================================================================

@dataclass
class PortfolioSnapshot:
    """
    Snapshot of portfolio at a point in time.
    """
    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Portfolio state
    allocations: Dict[str, AssetAllocation] = field(default_factory=dict)
    total_value: float = 0.0
    total_cost: float = 0.0
    total_profit: float = 0.0
    total_profit_percentage: float = 0.0
    
    # Performance
    performance_ytd: float = 0.0
    performance_1m: float = 0.0
    performance_1w: float = 0.0
    performance_1d: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "portfolio_id": self.portfolio_id,
            "timestamp": self.timestamp.isoformat(),
            "allocations": {asset: alloc.to_dict() for asset, alloc in self.allocations.items()},
            "total_value": self.total_value,
            "total_cost": self.total_cost,
            "total_profit": self.total_profit,
            "total_profit_percentage": self.total_profit_percentage,
            "performance_ytd": self.performance_ytd,
            "performance_1m": self.performance_1m,
            "performance_1w": self.performance_1w,
            "performance_1d": self.performance_1d,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_portfolio(cls, portfolio: Portfolio) -> "PortfolioSnapshot":
        """Create snapshot from portfolio."""
        return cls(
            portfolio_id=portfolio.portfolio_id,
            allocations={asset: alloc for asset, alloc in portfolio.allocations.items()},
            total_value=portfolio.total_value,
            total_cost=portfolio.total_cost,
            total_profit=portfolio.total_profit,
            total_profit_percentage=portfolio.total_profit_percentage,
            performance_ytd=portfolio.performance_ytd,
            performance_1m=portfolio.performance_1m,
            performance_1w=portfolio.performance_1w,
            performance_1d=portfolio.performance_1d,
            volatility=portfolio.volatility,
            sharpe_ratio=portfolio.sharpe_ratio,
            sortino_ratio=portfolio.sortino_ratio,
            calmar_ratio=portfolio.calmar_ratio,
            max_drawdown=portfolio.max_drawdown,
            current_drawdown=portfolio.current_drawdown,
            var_95=portfolio.var_95,
            cvar_95=portfolio.cvar_95
        )


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_optimal_position_size(
    portfolio_value: float,
    risk_per_trade: float,
    stop_loss: float,
    entry_price: float,
    max_leverage: float = 1.0
) -> float:
    """
    Calculate optimal position size based on risk management.
    
    Args:
        portfolio_value: Total portfolio value
        risk_per_trade: Risk per trade (percentage)
        stop_loss: Stop loss price
        entry_price: Entry price
        max_leverage: Maximum leverage
        
    Returns:
        Optimal position size
    """
    risk_amount = portfolio_value * risk_per_trade
    risk_per_unit = abs(entry_price - stop_loss) if entry_price > 0 else 1
    
    if risk_per_unit == 0:
        return 0.0
        
    position_size = risk_amount / risk_per_unit
    position_size = position_size * max_leverage
    
    return position_size


def calculate_portfolio_value_at_risk(
    portfolio_value: float,
    volatility: float,
    confidence_level: float = 0.95
) -> float:
    """
    Calculate Value at Risk (VaR) for portfolio.
    
    Args:
        portfolio_value: Total portfolio value
        volatility: Portfolio volatility
        confidence_level: Confidence level (0-1)
        
    Returns:
        VaR amount
    """
    z_score = {
        0.90: 1.282,
        0.95: 1.645,
        0.99: 2.326
    }.get(confidence_level, 1.645)
    
    return portfolio_value * volatility * z_score


def calculate_sharpe_ratio(
    return_annualized: float,
    volatility_annualized: float,
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        return_annualized: Annualized return
        volatility_annualized: Annualized volatility
        risk_free_rate: Risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if volatility_annualized == 0:
        return 0.0
        
    return (return_annualized - risk_free_rate) / volatility_annualized


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'PortfolioStatus',
    'AllocationType',
    'RiskProfile',
    'PortfolioCategory',
    'RebalanceTrigger',
    'LimitType',
    
    # Core Models
    'AssetAllocation',
    'Portfolio',
    'PortfolioSnapshot',
    
    # Helper Functions
    'calculate_optimal_position_size',
    'calculate_portfolio_value_at_risk',
    'calculate_sharpe_ratio',
]
