# trading/bots/arbitrage_bot/models/position.py
# NEXUS AI TRADING SYSTEM - POSITION MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for position management, tracking,
# and analysis across multiple exchanges and markets for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Position Models

This module provides comprehensive data models for:
- Position creation and management
- Position tracking and monitoring
- PnL calculation and analysis
- Position risk management
- Position closure and settlement
- Multi-exchange position aggregation
- Position performance analytics
- Position history and audit trails
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

class PositionSide(str, Enum):
    """Position direction."""
    LONG = "long"                        # Long position
    SHORT = "short"                      # Short position
    NEUTRAL = "neutral"                  # Neutral position
    FLAT = "flat"                        # Flat (no position)


class PositionStatus(str, Enum):
    """Status of a position."""
    OPEN = "open"                        # Position is open
    CLOSED = "closed"                    # Position is closed
    PARTIALLY_CLOSED = "partially_closed"  # Position is partially closed
    LIQUIDATED = "liquidated"            # Position was liquidated
    PENDING = "pending"                  # Position is pending
    REJECTED = "rejected"                # Position was rejected
    EXPIRED = "expired"                  # Position expired


class PositionType(str, Enum):
    """Types of positions."""
    SPOT = "spot"                        # Spot position
    FUTURES = "futures"                  # Futures position
    PERPETUAL = "perpetual"              # Perpetual futures position
    OPTIONS = "options"                  # Options position
    MARGIN = "margin"                    # Margin position
    LEVERAGED = "leveraged"              # Leveraged position
    SYNTHETIC = "synthetic"              # Synthetic position


class MarginType(str, Enum):
    """Margin types for leveraged positions."""
    CROSS = "cross"                      # Cross margin
    ISOLATED = "isolated"                # Isolated margin
    PORTFOLIO = "portfolio"              # Portfolio margin


class PositionEvent(str, Enum):
    """Position lifecycle events."""
    CREATED = "created"                  # Position created
    OPENED = "opened"                    # Position opened
    INCREASED = "increased"              # Position increased
    DECREASED = "decreased"              # Position decreased
    PARTIALLY_CLOSED = "partially_closed"  # Position partially closed
    CLOSED = "closed"                    # Position closed
    LIQUIDATED = "liquidated"            # Position liquidated
    UPDATED = "updated"                  # Position updated
    MARGIN_CALL = "margin_call"          # Margin call triggered


# ====================================================================================
# POSITION MODELS
# ====================================================================================

@dataclass
class Position:
    """
    Comprehensive position model.
    """
    # Core fields
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    side: PositionSide = PositionSide.NEUTRAL
    position_type: PositionType = PositionType.SPOT
    
    # Size and value
    size: float = 0.0                     # Current position size
    initial_size: float = 0.0             # Initial position size
    average_entry_price: float = 0.0      # Average entry price
    current_price: float = 0.0            # Current market price
    mark_price: float = 0.0               # Mark price (for futures)
    
    # Value calculations
    entry_value: float = 0.0              # Entry value (size * entry_price)
    current_value: float = 0.0            # Current value (size * current_price)
    notional_value: float = 0.0           # Notional value
    
    # PnL
    unrealized_pnl: float = 0.0           # Unrealized PnL
    realized_pnl: float = 0.0             # Realized PnL
    total_pnl: float = 0.0                # Total PnL (realized + unrealized)
    pnl_percentage: float = 0.0           # PnL percentage
    pnl_percentage_annualized: float = 0.0  # Annualized PnL percentage
    
    # Margin and leverage
    margin: float = 0.0                   # Used margin
    margin_type: MarginType = MarginType.CROSS
    leverage: int = 1                     # Leverage multiplier
    maintenance_margin: float = 0.0       # Maintenance margin
    initial_margin: float = 0.0           # Initial margin
    margin_ratio: float = 0.0             # Margin ratio
    
    # Liquidation
    liquidation_price: float = 0.0        # Liquidation price
    liquidation_buffer: float = 0.0       # Distance to liquidation
    
    # Fees
    entry_fee: float = 0.0                # Entry fee
    exit_fee: float = 0.0                 # Exit fee
    funding_paid: float = 0.0             # Funding fees paid
    total_fees: float = 0.0               # Total fees
    
    # Risk metrics
    risk_score: float = 0.0               # Risk score (0-1)
    var_95: float = 0.0                   # 95% VaR
    expected_shortfall: float = 0.0       # Expected shortfall
    beta: float = 0.0                     # Beta to benchmark
    
    # Timestamps
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    
    # Stop-loss and take-profit
    stop_loss_price: float = 0.0          # Stop-loss price
    take_profit_price: float = 0.0        # Take-profit price
    trailing_stop_price: float = 0.0      # Trailing stop price
    trailing_stop_percent: float = 0.0    # Trailing stop percentage
    
    # Orders
    entry_order_id: str = ""              # Entry order ID
    close_order_id: str = ""              # Close order ID
    stop_loss_order_id: str = ""          # Stop-loss order ID
    take_profit_order_id: str = ""        # Take-profit order ID
    
    # Related positions
    parent_position_id: str = ""          # Parent position ID
    child_position_ids: List[str] = field(default_factory=list)
    group_id: str = ""                    # Position group ID
    
    # Strategy
    strategy_id: str = ""                 # Strategy that opened this position
    strategy_name: str = ""               # Strategy name
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Audit
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self._calculate_metrics()
        
    def _calculate_metrics(self) -> None:
        """Calculate all position metrics."""
        # Entry value
        self.entry_value = self.size * self.average_entry_price
        
        # Current value
        self.current_value = self.size * self.current_price
        
        # Notional value
        self.notional_value = abs(self.size * self.current_price)
        
        # Unrealized PnL
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (self.current_price - self.average_entry_price) * self.size
        elif self.side == PositionSide.SHORT:
            self.unrealized_pnl = (self.average_entry_price - self.current_price) * self.size
        else:
            self.unrealized_pnl = 0.0
            
        # Total PnL
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        
        # PnL percentage
        if self.entry_value != 0:
            self.pnl_percentage = (self.total_pnl / abs(self.entry_value)) * 100
            
        # Annualized PnL
        if self.opened_at:
            days_open = (datetime.utcnow() - self.opened_at).total_seconds() / (24 * 3600)
            if days_open > 0:
                self.pnl_percentage_annualized = self.pnl_percentage * (365 / days_open)
                
        # Margin ratio
        if self.margin > 0:
            self.margin_ratio = self.margin / self.notional_value
            
        # Liquidation buffer
        if self.liquidation_price > 0:
            if self.side == PositionSide.LONG:
                self.liquidation_buffer = (self.current_price - self.liquidation_price) / self.current_price
            elif self.side == PositionSide.SHORT:
                self.liquidation_buffer = (self.liquidation_price - self.current_price) / self.current_price
            else:
                self.liquidation_buffer = 0.0
                
        # Total fees
        self.total_fees = self.entry_fee + self.exit_fee + self.funding_paid
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value if self.side else None,
            "position_type": self.position_type.value if self.position_type else None,
            "size": self.size,
            "initial_size": self.initial_size,
            "average_entry_price": self.average_entry_price,
            "current_price": self.current_price,
            "mark_price": self.mark_price,
            "entry_value": self.entry_value,
            "current_value": self.current_value,
            "notional_value": self.notional_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "pnl_percentage": self.pnl_percentage,
            "pnl_percentage_annualized": self.pnl_percentage_annualized,
            "margin": self.margin,
            "margin_type": self.margin_type.value if self.margin_type else None,
            "leverage": self.leverage,
            "maintenance_margin": self.maintenance_margin,
            "initial_margin": self.initial_margin,
            "margin_ratio": self.margin_ratio,
            "liquidation_price": self.liquidation_price,
            "liquidation_buffer": self.liquidation_buffer,
            "entry_fee": self.entry_fee,
            "exit_fee": self.exit_fee,
            "funding_paid": self.funding_paid,
            "total_fees": self.total_fees,
            "risk_score": self.risk_score,
            "var_95": self.var_95,
            "expected_shortfall": self.expected_shortfall,
            "beta": self.beta,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "status": self.status.value if self.status else None,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "trailing_stop_price": self.trailing_stop_price,
            "trailing_stop_percent": self.trailing_stop_percent,
            "entry_order_id": self.entry_order_id,
            "close_order_id": self.close_order_id,
            "stop_loss_order_id": self.stop_loss_order_id,
            "take_profit_order_id": self.take_profit_order_id,
            "parent_position_id": self.parent_position_id,
            "child_position_ids": self.child_position_ids,
            "group_id": self.group_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "metadata": self.metadata,
            "tags": self.tags,
            "audit_trail": self.audit_trail
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        """Create from dictionary."""
        position = cls(
            position_id=data.get("position_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            side=PositionSide(data["side"]) if data.get("side") else PositionSide.NEUTRAL,
            position_type=PositionType(data["position_type"]) if data.get("position_type") else PositionType.SPOT,
            size=data.get("size", 0.0),
            initial_size=data.get("initial_size", 0.0),
            average_entry_price=data.get("average_entry_price", 0.0),
            current_price=data.get("current_price", 0.0),
            mark_price=data.get("mark_price", 0.0),
            entry_value=data.get("entry_value", 0.0),
            current_value=data.get("current_value", 0.0),
            notional_value=data.get("notional_value", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            total_pnl=data.get("total_pnl", 0.0),
            pnl_percentage=data.get("pnl_percentage", 0.0),
            pnl_percentage_annualized=data.get("pnl_percentage_annualized", 0.0),
            margin=data.get("margin", 0.0),
            margin_type=MarginType(data["margin_type"]) if data.get("margin_type") else MarginType.CROSS,
            leverage=data.get("leverage", 1),
            maintenance_margin=data.get("maintenance_margin", 0.0),
            initial_margin=data.get("initial_margin", 0.0),
            margin_ratio=data.get("margin_ratio", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            liquidation_buffer=data.get("liquidation_buffer", 0.0),
            entry_fee=data.get("entry_fee", 0.0),
            exit_fee=data.get("exit_fee", 0.0),
            funding_paid=data.get("funding_paid", 0.0),
            total_fees=data.get("total_fees", 0.0),
            risk_score=data.get("risk_score", 0.0),
            var_95=data.get("var_95", 0.0),
            expected_shortfall=data.get("expected_shortfall", 0.0),
            beta=data.get("beta", 0.0),
            status=PositionStatus(data["status"]) if data.get("status") else PositionStatus.OPEN,
            stop_loss_price=data.get("stop_loss_price", 0.0),
            take_profit_price=data.get("take_profit_price", 0.0),
            trailing_stop_price=data.get("trailing_stop_price", 0.0),
            trailing_stop_percent=data.get("trailing_stop_percent", 0.0),
            entry_order_id=data.get("entry_order_id", ""),
            close_order_id=data.get("close_order_id", ""),
            stop_loss_order_id=data.get("stop_loss_order_id", ""),
            take_profit_order_id=data.get("take_profit_order_id", ""),
            parent_position_id=data.get("parent_position_id", ""),
            child_position_ids=data.get("child_position_ids", []),
            group_id=data.get("group_id", ""),
            strategy_id=data.get("strategy_id", ""),
            strategy_name=data.get("strategy_name", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            audit_trail=data.get("audit_trail", [])
        )
        
        # Parse timestamps
        if data.get("opened_at"):
            position.opened_at = datetime.fromisoformat(data["opened_at"])
        if data.get("updated_at"):
            position.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("closed_at"):
            position.closed_at = datetime.fromisoformat(data["closed_at"])
            
        position.__post_init__()
        return position
        
    def update_price(self, current_price: float, mark_price: float = 0.0) -> None:
        """
        Update position price and recalculate metrics.
        
        Args:
            current_price: Current market price
            mark_price: Mark price (for futures)
        """
        self.current_price = current_price
        if mark_price > 0:
            self.mark_price = mark_price
        self.updated_at = datetime.utcnow()
        self._calculate_metrics()
        
    def increase_position(self, additional_size: float, entry_price: float) -> None:
        """
        Increase position size.
        
        Args:
            additional_size: Additional size to add
            entry_price: Entry price for additional size
        """
        # Calculate new average entry price
        total_value = (self.size * self.average_entry_price) + (additional_size * entry_price)
        self.size += additional_size
        self.average_entry_price = total_value / self.size if self.size > 0 else 0
        
        self.updated_at = datetime.utcnow()
        self._calculate_metrics()
        
        # Add audit trail
        self.audit_trail.append({
            "event": PositionEvent.INCREASED.value,
            "timestamp": datetime.utcnow().isoformat(),
            "additional_size": additional_size,
            "entry_price": entry_price,
            "new_size": self.size,
            "new_avg_price": self.average_entry_price
        })
        
    def decrease_position(self, decrease_size: float, exit_price: float) -> float:
        """
        Decrease position size and realize PnL.
        
        Args:
            decrease_size: Size to decrease
            exit_price: Exit price
            
        Returns:
            Realized PnL from the decrease
        """
        if decrease_size > self.size:
            decrease_size = self.size
            
        # Calculate realized PnL
        if self.side == PositionSide.LONG:
            realized = (exit_price - self.average_entry_price) * decrease_size
        elif self.side == PositionSide.SHORT:
            realized = (self.average_entry_price - exit_price) * decrease_size
        else:
            realized = 0.0
            
        # Update position
        self.size -= decrease_size
        self.realized_pnl += realized
        self.updated_at = datetime.utcnow()
        
        if self.size <= 0:
            self.status = PositionStatus.CLOSED
            self.closed_at = datetime.utcnow()
            
        self._calculate_metrics()
        
        # Add audit trail
        self.audit_trail.append({
            "event": PositionEvent.DECREASED.value,
            "timestamp": datetime.utcnow().isoformat(),
            "decrease_size": decrease_size,
            "exit_price": exit_price,
            "realized_pnl": realized,
            "new_size": self.size,
            "status": self.status.value
        })
        
        return realized
        
    def close_position(self, exit_price: float) -> float:
        """
        Close entire position.
        
        Args:
            exit_price: Exit price
            
        Returns:
            Total realized PnL
        """
        if self.size == 0:
            return 0.0
            
        realized = self.decrease_position(self.size, exit_price)
        self.status = PositionStatus.CLOSED
        self.closed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        # Add audit trail
        self.audit_trail.append({
            "event": PositionEvent.CLOSED.value,
            "timestamp": datetime.utcnow().isoformat(),
            "exit_price": exit_price,
            "realized_pnl": realized
        })
        
        return realized
        
    def liquidate(self, liquidation_price: float) -> float:
        """
        Liquidate position.
        
        Args:
            liquidation_price: Liquidation price
            
        Returns:
            Realized PnL from liquidation
        """
        if self.size == 0:
            return 0.0
            
        realized = self.close_position(liquidation_price)
        self.status = PositionStatus.LIQUIDATED
        self.updated_at = datetime.utcnow()
        
        # Add audit trail
        self.audit_trail.append({
            "event": PositionEvent.LIQUIDATED.value,
            "timestamp": datetime.utcnow().isoformat(),
            "liquidation_price": liquidation_price,
            "realized_pnl": realized
        })
        
        return realized
        
    def set_stop_loss(self, stop_loss_price: float) -> None:
        """
        Set stop-loss price.
        
        Args:
            stop_loss_price: Stop-loss price
        """
        self.stop_loss_price = stop_loss_price
        self.updated_at = datetime.utcnow()
        
        # Add audit trail
        self.audit_trail.append({
            "event": "stop_loss_set",
            "timestamp": datetime.utcnow().isoformat(),
            "stop_loss_price": stop_loss_price
        })
        
    def set_take_profit(self, take_profit_price: float) -> None:
        """
        Set take-profit price.
        
        Args:
            take_profit_price: Take-profit price
        """
        self.take_profit_price = take_profit_price
        self.updated_at = datetime.utcnow()
        
        # Add audit trail
        self.audit_trail.append({
            "event": "take_profit_set",
            "timestamp": datetime.utcnow().isoformat(),
            "take_profit_price": take_profit_price
        })
        
    def is_open(self) -> bool:
        """Check if position is open."""
        return self.status == PositionStatus.OPEN
        
    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.status in [PositionStatus.CLOSED, PositionStatus.LIQUIDATED]
        
    def is_profitable(self) -> bool:
        """Check if position is profitable."""
        return self.total_pnl > 0
        
    def get_risk_reward_ratio(self) -> float:
        """
        Calculate risk-reward ratio.
        
        Returns:
            Risk-reward ratio (0 if not applicable)
        """
        if self.stop_loss_price == 0 or self.take_profit_price == 0:
            return 0.0
            
        if self.side == PositionSide.LONG:
            risk = self.average_entry_price - self.stop_loss_price
            reward = self.take_profit_price - self.average_entry_price
        elif self.side == PositionSide.SHORT:
            risk = self.stop_loss_price - self.average_entry_price
            reward = self.average_entry_price - self.take_profit_price
        else:
            return 0.0
            
        if risk == 0:
            return 0.0
            
        return reward / risk
        
    def get_margin_ratio(self) -> float:
        """
        Get current margin ratio.
        
        Returns:
            Margin ratio as percentage
        """
        if self.notional_value == 0:
            return 0.0
        return (self.margin / self.notional_value) * 100
        
    def get_leverage_used(self) -> float:
        """
        Get current leverage used.
        
        Returns:
            Leverage multiplier
        """
        if self.margin == 0:
            return 0.0
        return self.notional_value / self.margin


# ====================================================================================
# POSITION SUMMARY MODELS
# ====================================================================================

@dataclass
class PositionSummary:
    """
    Summary of positions across a portfolio.
    """
    # Core fields
    summary_id: str = field(default_factory=lambda: str(uuid4()))
    portfolio_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Position counts
    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    liquidated_positions: int = 0
    
    # By side
    long_positions: int = 0
    short_positions: int = 0
    long_value: float = 0.0
    short_value: float = 0.0
    net_exposure: float = 0.0
    
    # By exchange
    positions_by_exchange: Dict[str, int] = field(default_factory=dict)
    value_by_exchange: Dict[str, float] = field(default_factory=dict)
    
    # By symbol
    positions_by_symbol: Dict[str, int] = field(default_factory=dict)
    value_by_symbol: Dict[str, float] = field(default_factory=dict)
    
    # By strategy
    positions_by_strategy: Dict[str, int] = field(default_factory=dict)
    pnl_by_strategy: Dict[str, float] = field(default_factory=dict)
    
    # PnL summary
    total_unrealized_pnl: float = 0.0
    total_realized_pnl: float = 0.0
    total_pnl: float = 0.0
    profitable_positions: int = 0
    unprofitable_positions: int = 0
    win_rate: float = 0.0
    
    # Risk metrics
    total_margin: float = 0.0
    total_notional: float = 0.0
    avg_leverage: float = 0.0
    total_liquidation_risk: float = 0.0
    
    # Best and worst
    best_position: Optional[Position] = None
    worst_position: Optional[Position] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": self.summary_id,
            "portfolio_id": self.portfolio_id,
            "timestamp": self.timestamp.isoformat(),
            "total_positions": self.total_positions,
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "liquidated_positions": self.liquidated_positions,
            "long_positions": self.long_positions,
            "short_positions": self.short_positions,
            "long_value": self.long_value,
            "short_value": self.short_value,
            "net_exposure": self.net_exposure,
            "positions_by_exchange": self.positions_by_exchange,
            "value_by_exchange": self.value_by_exchange,
            "positions_by_symbol": self.positions_by_symbol,
            "value_by_symbol": self.value_by_symbol,
            "positions_by_strategy": self.positions_by_strategy,
            "pnl_by_strategy": self.pnl_by_strategy,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "total_realized_pnl": self.total_realized_pnl,
            "total_pnl": self.total_pnl,
            "profitable_positions": self.profitable_positions,
            "unprofitable_positions": self.unprofitable_positions,
            "win_rate": self.win_rate,
            "total_margin": self.total_margin,
            "total_notional": self.total_notional,
            "avg_leverage": self.avg_leverage,
            "total_liquidation_risk": self.total_liquidation_risk,
            "best_position": self.best_position.to_dict() if self.best_position else None,
            "worst_position": self.worst_position.to_dict() if self.worst_position else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_positions(cls, positions: List[Position], portfolio_id: str = "") -> "PositionSummary":
        """
        Create summary from list of positions.
        
        Args:
            positions: List of positions
            portfolio_id: Portfolio ID
            
        Returns:
            PositionSummary instance
        """
        summary = cls(portfolio_id=portfolio_id)
        
        # Count positions
        summary.total_positions = len(positions)
        summary.open_positions = sum(1 for p in positions if p.is_open())
        summary.closed_positions = sum(1 for p in positions if p.status == PositionStatus.CLOSED)
        summary.liquidated_positions = sum(1 for p in positions if p.status == PositionStatus.LIQUIDATED)
        
        # By side
        long_positions = [p for p in positions if p.side == PositionSide.LONG]
        short_positions = [p for p in positions if p.side == PositionSide.SHORT]
        summary.long_positions = len(long_positions)
        summary.short_positions = len(short_positions)
        summary.long_value = sum(p.notional_value for p in long_positions)
        summary.short_value = sum(p.notional_value for p in short_positions)
        summary.net_exposure = summary.long_value - summary.short_value
        
        # By exchange
        for p in positions:
            summary.positions_by_exchange[p.exchange] = summary.positions_by_exchange.get(p.exchange, 0) + 1
            summary.value_by_exchange[p.exchange] = summary.value_by_exchange.get(p.exchange, 0) + p.notional_value
            
        # By symbol
        for p in positions:
            summary.positions_by_symbol[p.symbol] = summary.positions_by_symbol.get(p.symbol, 0) + 1
            summary.value_by_symbol[p.symbol] = summary.value_by_symbol.get(p.symbol, 0) + p.notional_value
            
        # By strategy
        for p in positions:
            if p.strategy_name:
                summary.positions_by_strategy[p.strategy_name] = summary.positions_by_strategy.get(p.strategy_name, 0) + 1
                summary.pnl_by_strategy[p.strategy_name] = summary.pnl_by_strategy.get(p.strategy_name, 0) + p.total_pnl
                
        # PnL summary
        summary.total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        summary.total_realized_pnl = sum(p.realized_pnl for p in positions)
        summary.total_pnl = summary.total_unrealized_pnl + summary.total_realized_pnl
        summary.profitable_positions = sum(1 for p in positions if p.is_profitable())
        summary.unprofitable_positions = summary.total_positions - summary.profitable_positions
        summary.win_rate = (summary.profitable_positions / summary.total_positions * 100) if summary.total_positions > 0 else 0
        
        # Risk metrics
        summary.total_margin = sum(p.margin for p in positions)
        summary.total_notional = sum(p.notional_value for p in positions)
        summary.avg_leverage = summary.total_notional / summary.total_margin if summary.total_margin > 0 else 0
        summary.total_liquidation_risk = sum(1 for p in positions if p.liquidation_buffer < 0.1)
        
        # Best and worst
        if positions:
            summary.best_position = max(positions, key=lambda p: p.total_pnl)
            summary.worst_position = min(positions, key=lambda p: p.total_pnl)
            
        return summary


# ====================================================================================
# POSITION FILTER MODELS
# ====================================================================================

@dataclass
class PositionFilter:
    """
    Filter for positions.
    """
    # Basic filters
    exchanges: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    sides: List[PositionSide] = field(default_factory=list)
    statuses: List[PositionStatus] = field(default_factory=list)
    position_types: List[PositionType] = field(default_factory=list)
    strategies: List[str] = field(default_factory=list)
    
    # Time filters
    opened_since: Optional[datetime] = None
    opened_until: Optional[datetime] = None
    closed_since: Optional[datetime] = None
    closed_until: Optional[datetime] = None
    
    # Financial filters
    min_size: float = 0.0
    max_size: float = float('inf')
    min_value: float = 0.0
    max_value: float = float('inf')
    min_pnl: float = 0.0
    max_pnl: float = float('inf')
    min_leverage: int = 0
    max_leverage: int = float('inf')
    
    # Risk filters
    min_risk_score: float = 0.0
    max_risk_score: float = 1.0
    min_liquidation_buffer: float = 0.0
    max_liquidation_buffer: float = 1.0
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    # Sorting
    sort_by: str = "opened_at"
    sort_order: str = "desc"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchanges": self.exchanges,
            "symbols": self.symbols,
            "sides": [s.value for s in self.sides],
            "statuses": [s.value for s in self.statuses],
            "position_types": [p.value for p in self.position_types],
            "strategies": self.strategies,
            "opened_since": self.opened_since.isoformat() if self.opened_since else None,
            "opened_until": self.opened_until.isoformat() if self.opened_until else None,
            "closed_since": self.closed_since.isoformat() if self.closed_since else None,
            "closed_until": self.closed_until.isoformat() if self.closed_until else None,
            "min_size": self.min_size,
            "max_size": self.max_size,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "min_pnl": self.min_pnl,
            "max_pnl": self.max_pnl,
            "min_leverage": self.min_leverage,
            "max_leverage": self.max_leverage,
            "min_risk_score": self.min_risk_score,
            "max_risk_score": self.max_risk_score,
            "min_liquidation_buffer": self.min_liquidation_buffer,
            "max_liquidation_buffer": self.max_liquidation_buffer,
            "limit": self.limit,
            "offset": self.offset,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_position(
    symbol: str,
    exchange: str,
    side: PositionSide,
    size: float,
    entry_price: float,
    **kwargs
) -> Position:
    """
    Create a new position.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange name
        side: Position side
        size: Position size
        entry_price: Entry price
        **kwargs: Additional position fields
        
    Returns:
        Position instance
    """
    return Position(
        symbol=symbol,
        exchange=exchange,
        side=side,
        size=size,
        initial_size=size,
        average_entry_price=entry_price,
        current_price=entry_price,
        **kwargs
    )


def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss_price: float,
    risk_per_trade: float,
    leverage: int = 1
) -> float:
    """
    Calculate position size based on risk.
    
    Args:
        capital: Available capital
        entry_price: Entry price
        stop_loss_price: Stop loss price
        risk_per_trade: Risk per trade (percentage)
        leverage: Leverage multiplier
        
    Returns:
        Position size
    """
    if entry_price == 0 or stop_loss_price == 0:
        return 0.0
        
    risk_amount = capital * risk_per_trade
    risk_per_unit = abs(entry_price - stop_loss_price)
    
    if risk_per_unit == 0:
        return 0.0
        
    return (risk_amount / risk_per_unit) * leverage


def calculate_liquidation_price(
    entry_price: float,
    side: PositionSide,
    leverage: int,
    maintenance_margin: float
) -> float:
    """
    Calculate liquidation price.
    
    Args:
        entry_price: Entry price
        side: Position side
        leverage: Leverage multiplier
        maintenance_margin: Maintenance margin rate
        
    Returns:
        Liquidation price
    """
    if leverage == 0:
        return 0.0
        
    margin_factor = 1 / leverage
    
    if side == PositionSide.LONG:
        return entry_price * (1 - margin_factor / (1 - maintenance_margin))
    else:
        return entry_price * (1 + margin_factor / (1 - maintenance_margin))


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'PositionSide',
    'PositionStatus',
    'PositionType',
    'MarginType',
    'PositionEvent',
    
    # Core Models
    'Position',
    'PositionSummary',
    'PositionFilter',
    
    # Helper Functions
    'create_position',
    'calculate_position_size',
    'calculate_liquidation_price',
]
