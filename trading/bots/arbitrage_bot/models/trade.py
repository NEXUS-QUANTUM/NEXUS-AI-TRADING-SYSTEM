# trading/bots/arbitrage_bot/models/trade.py
# NEXUS AI TRADING SYSTEM - TRADE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for trade execution, tracking,
# analysis, and reporting for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Trade Models

This module provides comprehensive data models for:
- Trade execution and tracking
- Trade analysis and performance
- Trade history and reporting
- Multi-leg trade management
- Trade reconciliation and audit
- Trade risk and compliance
- Trade settlement and clearing
- Trade optimization and improvement
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

class TradeSide(str, Enum):
    """Trade side."""
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    """Status of a trade."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    EXECUTED = "executed"
    PARTIALLY_EXECUTED = "partially_executed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    SETTLED = "settled"
    PENDING_SETTLEMENT = "pending_settlement"


class TradeType(str, Enum):
    """Types of trades."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"
    TRAILING_STOP = "trailing_stop"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"
    ARBITRAGE = "arbitrage"
    HEDGE = "hedge"
    REBALANCE = "rebalance"


class TradeExecutionMethod(str, Enum):
    """Methods of trade execution."""
    ATOMIC = "atomic"                    # Atomic execution
    SEQUENTIAL = "sequential"            # Sequential execution
    PARALLEL = "parallel"                # Parallel execution
    BATCHED = "batched"                  # Batched execution
    STAGGERED = "staggered"              # Staggered execution
    SMART = "smart"                      # Smart routing execution


class TradeCategory(str, Enum):
    """Categories for trade classification."""
    SPOT = "spot"
    MARGIN = "margin"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    OPTIONS = "options"
    SWAP = "swap"
    ETF = "etf"
    ARBITRAGE = "arbitrage"


class TradeRole(str, Enum):
    """Role in trade execution."""
    MAKER = "maker"
    TAKER = "taker"


class TradeSettlementStatus(str, Enum):
    """Settlement status of a trade."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    REVERSED = "reversed"


# ====================================================================================
# TRADE LEG MODELS
# ====================================================================================

@dataclass
class TradeLeg:
    """
    Single leg of a multi-leg trade.
    """
    # Core fields
    leg_id: str = field(default_factory=lambda: str(uuid4()))
    exchange: str = ""
    symbol: str = ""
    side: TradeSide = TradeSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    value: float = 0.0
    fee: float = 0.0
    fee_rate: float = 0.0
    
    # Order details
    order_id: str = ""
    order_type: str = "market"
    time_in_force: str = "GTC"
    
    # Execution details
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    executed_value: float = 0.0
    executed_at: Optional[datetime] = None
    status: TradeStatus = TradeStatus.PENDING
    
    # Slippage
    expected_slippage: float = 0.0
    actual_slippage: float = 0.0
    slippage_ratio: float = 0.0
    
    # Settlement
    settlement_status: TradeSettlementStatus = TradeSettlementStatus.PENDING
    settlement_time: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.value = self.quantity * self.price
        self.fee = self.value * self.fee_rate
        self.executed_value = self.executed_quantity * self.executed_price
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "leg_id": self.leg_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "side": self.side.value if self.side else None,
            "quantity": self.quantity,
            "price": self.price,
            "value": self.value,
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "order_id": self.order_id,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "executed_quantity": self.executed_quantity,
            "executed_price": self.executed_price,
            "executed_value": self.executed_value,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "status": self.status.value if self.status else None,
            "expected_slippage": self.expected_slippage,
            "actual_slippage": self.actual_slippage,
            "slippage_ratio": self.slippage_ratio,
            "settlement_status": self.settlement_status.value if self.settlement_status else None,
            "settlement_time": self.settlement_time.isoformat() if self.settlement_time else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeLeg":
        """Create from dictionary."""
        leg = cls(
            leg_id=data.get("leg_id", str(uuid4())),
            exchange=data.get("exchange", ""),
            symbol=data.get("symbol", ""),
            side=TradeSide(data["side"]) if data.get("side") else TradeSide.BUY,
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            value=data.get("value", 0.0),
            fee=data.get("fee", 0.0),
            fee_rate=data.get("fee_rate", 0.0),
            order_id=data.get("order_id", ""),
            order_type=data.get("order_type", "market"),
            time_in_force=data.get("time_in_force", "GTC"),
            executed_quantity=data.get("executed_quantity", 0.0),
            executed_price=data.get("executed_price", 0.0),
            executed_value=data.get("executed_value", 0.0),
            status=TradeStatus(data["status"]) if data.get("status") else TradeStatus.PENDING,
            expected_slippage=data.get("expected_slippage", 0.0),
            actual_slippage=data.get("actual_slippage", 0.0),
            slippage_ratio=data.get("slippage_ratio", 0.0),
            settlement_status=TradeSettlementStatus(data["settlement_status"]) if data.get("settlement_status") else TradeSettlementStatus.PENDING,
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("executed_at"):
            leg.executed_at = datetime.fromisoformat(data["executed_at"])
        if data.get("settlement_time"):
            leg.settlement_time = datetime.fromisoformat(data["settlement_time"])
            
        leg.__post_init__()
        return leg
        
    def is_executed(self) -> bool:
        """Check if leg is executed."""
        return self.status == TradeStatus.EXECUTED
        
    def is_partially_executed(self) -> bool:
        """Check if leg is partially executed."""
        return self.status == TradeStatus.PARTIALLY_EXECUTED
        
    def is_failed(self) -> bool:
        """Check if leg failed."""
        return self.status == TradeStatus.FAILED
        
    def get_execution_ratio(self) -> float:
        """Get execution ratio."""
        if self.quantity == 0:
            return 0.0
        return self.executed_quantity / self.quantity


# ====================================================================================
# TRADE MODELS
# ====================================================================================

@dataclass
class Trade:
    """
    Comprehensive trade model.
    """
    # Core fields
    trade_id: str = field(default_factory=lambda: str(uuid4()))
    strategy: str = ""
    strategy_id: str = ""
    symbol: str = ""
    exchange: str = ""
    
    # Trade details
    side: TradeSide = TradeSide.BUY
    type: TradeType = TradeType.MARKET
    category: TradeCategory = TradeCategory.SPOT
    quantity: float = 0.0
    price: float = 0.0
    value: float = 0.0
    
    # Execution
    execution_method: TradeExecutionMethod = TradeExecutionMethod.ATOMIC
    execution_time_ms: float = 0.0
    execution_latency_ms: float = 0.0
    
    # Status
    status: TradeStatus = TradeStatus.PENDING
    status_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    settled_at: Optional[datetime] = None
    
    # Legs (for multi-leg trades)
    legs: List[TradeLeg] = field(default_factory=list)
    leg_count: int = 0
    
    # Fees and costs
    total_fees: float = 0.0
    total_gas: float = 0.0
    total_slippage: float = 0.0
    total_costs: float = 0.0
    
    # PnL
    gross_profit: float = 0.0
    net_profit: float = 0.0
    profit_percentage: float = 0.0
    
    # Settlement
    settlement_status: TradeSettlementStatus = TradeSettlementStatus.PENDING
    settlement_time: Optional[datetime] = None
    
    # Risk
    risk_score: float = 0.0
    position_size: float = 0.0
    leverage: int = 1
    
    # Market context
    market_price: float = 0.0
    market_volatility: float = 0.0
    bid_ask_spread: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Audit
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.value = self.quantity * self.price
        self.leg_count = len(self.legs)
        self._calculate_fees_and_costs()
        self._calculate_pnl()
        
    def _calculate_fees_and_costs(self) -> None:
        """Calculate total fees and costs."""
        self.total_fees = sum(leg.fee for leg in self.legs)
        self.total_slippage = sum(leg.actual_slippage * leg.executed_quantity for leg in self.legs if leg.executed_quantity)
        self.total_gas = sum(leg.metadata.get("gas_cost", 0.0) for leg in self.legs)
        self.total_costs = self.total_fees + self.total_slippage + self.total_gas
        
    def _calculate_pnl(self) -> None:
        """Calculate PnL."""
        total_value = sum(leg.value for leg in self.legs)
        total_executed_value = sum(leg.executed_value for leg in self.legs)
        
        if self.side == TradeSide.BUY:
            self.gross_profit = total_executed_value - total_value
        else:
            self.gross_profit = total_value - total_executed_value
            
        self.net_profit = self.gross_profit - self.total_costs
        
        if total_value > 0:
            self.profit_percentage = (self.net_profit / total_value) * 100
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "strategy": self.strategy,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value if self.side else None,
            "type": self.type.value if self.type else None,
            "category": self.category.value if self.category else None,
            "quantity": self.quantity,
            "price": self.price,
            "value": self.value,
            "execution_method": self.execution_method.value if self.execution_method else None,
            "execution_time_ms": self.execution_time_ms,
            "execution_latency_ms": self.execution_latency_ms,
            "status": self.status.value if self.status else None,
            "status_history": self.status_history,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "settled_at": self.settled_at.isoformat() if self.settled_at else None,
            "legs": [leg.to_dict() for leg in self.legs],
            "leg_count": self.leg_count,
            "total_fees": self.total_fees,
            "total_gas": self.total_gas,
            "total_slippage": self.total_slippage,
            "total_costs": self.total_costs,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "profit_percentage": self.profit_percentage,
            "settlement_status": self.settlement_status.value if self.settlement_status else None,
            "settlement_time": self.settlement_time.isoformat() if self.settlement_time else None,
            "risk_score": self.risk_score,
            "position_size": self.position_size,
            "leverage": self.leverage,
            "market_price": self.market_price,
            "market_volatility": self.market_volatility,
            "bid_ask_spread": self.bid_ask_spread,
            "metadata": self.metadata,
            "tags": self.tags,
            "audit_trail": self.audit_trail
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trade":
        """Create from dictionary."""
        trade = cls(
            trade_id=data.get("trade_id", str(uuid4())),
            strategy=data.get("strategy", ""),
            strategy_id=data.get("strategy_id", ""),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            side=TradeSide(data["side"]) if data.get("side") else TradeSide.BUY,
            type=TradeType(data["type"]) if data.get("type") else TradeType.MARKET,
            category=TradeCategory(data["category"]) if data.get("category") else TradeCategory.SPOT,
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            value=data.get("value", 0.0),
            execution_method=TradeExecutionMethod(data["execution_method"]) if data.get("execution_method") else TradeExecutionMethod.ATOMIC,
            execution_time_ms=data.get("execution_time_ms", 0.0),
            execution_latency_ms=data.get("execution_latency_ms", 0.0),
            status=TradeStatus(data["status"]) if data.get("status") else TradeStatus.PENDING,
            status_history=data.get("status_history", []),
            legs=[TradeLeg.from_dict(l) for l in data.get("legs", [])],
            total_fees=data.get("total_fees", 0.0),
            total_gas=data.get("total_gas", 0.0),
            total_slippage=data.get("total_slippage", 0.0),
            total_costs=data.get("total_costs", 0.0),
            gross_profit=data.get("gross_profit", 0.0),
            net_profit=data.get("net_profit", 0.0),
            profit_percentage=data.get("profit_percentage", 0.0),
            settlement_status=TradeSettlementStatus(data["settlement_status"]) if data.get("settlement_status") else TradeSettlementStatus.PENDING,
            risk_score=data.get("risk_score", 0.0),
            position_size=data.get("position_size", 0.0),
            leverage=data.get("leverage", 1),
            market_price=data.get("market_price", 0.0),
            market_volatility=data.get("market_volatility", 0.0),
            bid_ask_spread=data.get("bid_ask_spread", 0.0),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
            audit_trail=data.get("audit_trail", [])
        )
        
        # Parse timestamps
        if data.get("created_at"):
            trade.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            trade.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("executed_at"):
            trade.executed_at = datetime.fromisoformat(data["executed_at"])
        if data.get("submitted_at"):
            trade.submitted_at = datetime.fromisoformat(data["submitted_at"])
        if data.get("settled_at"):
            trade.settled_at = datetime.fromisoformat(data["settled_at"])
        if data.get("settlement_time"):
            trade.settlement_time = datetime.fromisoformat(data["settlement_time"])
            
        trade.__post_init__()
        return trade
        
    def update_status(self, status: TradeStatus, event: str = "") -> None:
        """
        Update trade status.
        
        Args:
            status: New status
            event: Status change event
        """
        old_status = self.status
        self.status = status
        self.updated_at = datetime.utcnow()
        
        # Record status history
        self.status_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_status": old_status.value if old_status else None,
            "new_status": status.value if status else None,
            "event": event
        })
        
        # Update timestamps
        if status == TradeStatus.SUBMITTED:
            self.submitted_at = datetime.utcnow()
        elif status == TradeStatus.EXECUTED:
            self.executed_at = datetime.utcnow()
        elif status == TradeStatus.SETTLED:
            self.settled_at = datetime.utcnow()
            self.settlement_status = TradeSettlementStatus.COMPLETED
            self.settlement_time = datetime.utcnow()
            
    def add_leg(self, leg: TradeLeg) -> None:
        """
        Add a trade leg.
        
        Args:
            leg: Trade leg to add
        """
        self.legs.append(leg)
        self.leg_count = len(self.legs)
        self._calculate_fees_and_costs()
        self._calculate_pnl()
        self.updated_at = datetime.utcnow()
        
    def is_completed(self) -> bool:
        """Check if trade is completed."""
        return self.status in [TradeStatus.EXECUTED, TradeStatus.SETTLED]
        
    def is_pending(self) -> bool:
        """Check if trade is pending."""
        return self.status in [TradeStatus.PENDING, TradeStatus.SUBMITTED, TradeStatus.ACCEPTED]
        
    def is_failed(self) -> bool:
        """Check if trade failed."""
        return self.status == TradeStatus.FAILED
        
    def get_total_executed_quantity(self) -> float:
        """Get total executed quantity across all legs."""
        return sum(leg.executed_quantity for leg in self.legs)
        
    def get_avg_executed_price(self) -> float:
        """Get average executed price."""
        total_quantity = self.get_total_executed_quantity()
        if total_quantity == 0:
            return 0.0
        total_value = sum(leg.executed_value for leg in self.legs)
        return total_value / total_quantity
        
    def get_profit_after_costs(self) -> float:
        """Get profit after all costs."""
        return self.net_profit


# ====================================================================================
# TRADE SUMMARY MODELS
# ====================================================================================

@dataclass
class TradeSummary:
    """
    Summary of trades.
    """
    # Core fields
    summary_id: str = field(default_factory=lambda: str(uuid4()))
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Trade counts
    total_trades: int = 0
    executed_trades: int = 0
    failed_trades: int = 0
    pending_trades: int = 0
    cancelled_trades: int = 0
    
    # Volume
    total_volume: float = 0.0
    total_value: float = 0.0
    avg_trade_size: float = 0.0
    max_trade_size: float = 0.0
    min_trade_size: float = 0.0
    
    # PnL
    total_gross_profit: float = 0.0
    total_net_profit: float = 0.0
    total_fees: float = 0.0
    total_costs: float = 0.0
    avg_profit: float = 0.0
    profit_percentage: float = 0.0
    
    # Performance
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    
    # By strategy
    trades_by_strategy: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    profit_by_strategy: Dict[str, float] = field(default_factory=dict)
    
    # By exchange
    trades_by_exchange: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    profit_by_exchange: Dict[str, float] = field(default_factory=dict)
    
    # By symbol
    trades_by_symbol: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    profit_by_symbol: Dict[str, float] = field(default_factory=dict)
    
    # Time-based
    trades_by_day: Dict[str, int] = field(default_factory=dict)
    profit_by_day: Dict[str, float] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived metrics."""
        self._calculate_metrics()
        
    def _calculate_metrics(self) -> None:
        """Calculate derived metrics."""
        if self.total_trades > 0:
            self.win_rate = (self.executed_trades / self.total_trades) * 100
            self.avg_trade_size = self.total_volume / self.total_trades
            
        # Calculate profit factor
        gross_loss = abs(self.total_gross_profit - self.total_net_profit)
        if gross_loss > 0:
            self.profit_factor = self.total_gross_profit / gross_loss
        else:
            self.profit_factor = float('inf')
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": self.summary_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_trades": self.total_trades,
            "executed_trades": self.executed_trades,
            "failed_trades": self.failed_trades,
            "pending_trades": self.pending_trades,
            "cancelled_trades": self.cancelled_trades,
            "total_volume": self.total_volume,
            "total_value": self.total_value,
            "avg_trade_size": self.avg_trade_size,
            "max_trade_size": self.max_trade_size,
            "min_trade_size": self.min_trade_size,
            "total_gross_profit": self.total_gross_profit,
            "total_net_profit": self.total_net_profit,
            "total_fees": self.total_fees,
            "total_costs": self.total_costs,
            "avg_profit": self.avg_profit,
            "profit_percentage": self.profit_percentage,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "trades_by_strategy": self.trades_by_strategy,
            "profit_by_strategy": self.profit_by_strategy,
            "trades_by_exchange": self.trades_by_exchange,
            "profit_by_exchange": self.profit_by_exchange,
            "trades_by_symbol": self.trades_by_symbol,
            "profit_by_symbol": self.profit_by_symbol,
            "trades_by_day": self.trades_by_day,
            "profit_by_day": self.profit_by_day,
            "metadata": self.metadata
        }
        
    def add_trade(self, trade: Trade) -> None:
        """
        Add trade to summary.
        
        Args:
            trade: Trade to add
        """
        self.total_trades += 1
        
        if trade.is_completed():
            self.executed_trades += 1
        elif trade.is_failed():
            self.failed_trades += 1
        elif trade.is_pending():
            self.pending_trades += 1
        elif trade.status == TradeStatus.CANCELLED:
            self.cancelled_trades += 1
            
        self.total_volume += trade.quantity
        self.total_value += trade.value
        self.max_trade_size = max(self.max_trade_size, trade.quantity)
        self.min_trade_size = min(self.min_trade_size, trade.quantity)
        
        self.total_gross_profit += trade.gross_profit
        self.total_net_profit += trade.net_profit
        self.total_fees += trade.total_fees
        self.total_costs += trade.total_costs
        
        # Update strategy metrics
        if trade.strategy:
            if trade.strategy not in self.trades_by_strategy:
                self.trades_by_strategy[trade.strategy] = {"count": 0, "profit": 0.0}
            self.trades_by_strategy[trade.strategy]["count"] += 1
            self.trades_by_strategy[trade.strategy]["profit"] += trade.net_profit
            self.profit_by_strategy[trade.strategy] = self.profit_by_strategy.get(trade.strategy, 0) + trade.net_profit
            
        # Update exchange metrics
        if trade.exchange:
            if trade.exchange not in self.trades_by_exchange:
                self.trades_by_exchange[trade.exchange] = {"count": 0, "profit": 0.0}
            self.trades_by_exchange[trade.exchange]["count"] += 1
            self.trades_by_exchange[trade.exchange]["profit"] += trade.net_profit
            self.profit_by_exchange[trade.exchange] = self.profit_by_exchange.get(trade.exchange, 0) + trade.net_profit
            
        # Update symbol metrics
        if trade.symbol:
            if trade.symbol not in self.trades_by_symbol:
                self.trades_by_symbol[trade.symbol] = {"count": 0, "profit": 0.0}
            self.trades_by_symbol[trade.symbol]["count"] += 1
            self.trades_by_symbol[trade.symbol]["profit"] += trade.net_profit
            self.profit_by_symbol[trade.symbol] = self.profit_by_symbol.get(trade.symbol, 0) + trade.net_profit
            
        # Update day metrics
        day_key = trade.executed_at.strftime("%Y-%m-%d") if trade.executed_at else datetime.utcnow().strftime("%Y-%m-%d")
        self.trades_by_day[day_key] = self.trades_by_day.get(day_key, 0) + 1
        self.profit_by_day[day_key] = self.profit_by_day.get(day_key, 0) + trade.net_profit
        
        self._calculate_metrics()


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_trade(
    symbol: str,
    exchange: str,
    side: TradeSide,
    quantity: float,
    price: float,
    **kwargs
) -> Trade:
    """
    Create a new trade.
    
    Args:
        symbol: Trading symbol
        exchange: Exchange name
        side: Buy or sell
        quantity: Trade quantity
        price: Trade price
        **kwargs: Additional trade fields
        
    Returns:
        Trade instance
    """
    return Trade(
        symbol=symbol,
        exchange=exchange,
        side=side,
        quantity=quantity,
        price=price,
        **kwargs
    )


def create_trade_leg(
    exchange: str,
    symbol: str,
    side: TradeSide,
    quantity: float,
    price: float,
    fee_rate: float = 0.001,
    **kwargs
) -> TradeLeg:
    """
    Create a trade leg.
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: Buy or sell
        quantity: Trade quantity
        price: Trade price
        fee_rate: Fee rate
        **kwargs: Additional leg fields
        
    Returns:
        TradeLeg instance
    """
    return TradeLeg(
        exchange=exchange,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        fee_rate=fee_rate,
        **kwargs
    )


def calculate_trade_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    side: TradeSide,
    fees: float = 0.0
) -> Dict[str, float]:
    """
    Calculate trade PnL.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        quantity: Trade quantity
        side: Trade side
        fees: Total fees
        
    Returns:
        Dict with PnL metrics
    """
    entry_value = entry_price * quantity
    exit_value = exit_price * quantity
    
    if side == TradeSide.BUY:
        gross_profit = exit_value - entry_value
    else:
        gross_profit = entry_value - exit_value
        
    net_profit = gross_profit - fees
    
    return {
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "profit_percentage": (net_profit / entry_value * 100) if entry_value > 0 else 0,
        "entry_value": entry_value,
        "exit_value": exit_value
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'TradeSide',
    'TradeStatus',
    'TradeType',
    'TradeExecutionMethod',
    'TradeCategory',
    'TradeRole',
    'TradeSettlementStatus',
    
    # Core Models
    'TradeLeg',
    'Trade',
    'TradeSummary',
    
    # Helper Functions
    'create_trade',
    'create_trade_leg',
    'calculate_trade_pnl',
]
