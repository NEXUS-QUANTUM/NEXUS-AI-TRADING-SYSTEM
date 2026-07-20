# trading/bots/arbitrage_bot/models/opportunity.py
# NEXUS AI TRADING SYSTEM - OPPORTUNITY MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for arbitrage opportunities, including
# detection, analysis, execution, and tracking of arbitrage opportunities
# across multiple exchanges and markets.
# ====================================================================================

"""
NEXUS Arbitrage Bot Opportunity Models

This module provides comprehensive data models for:
- Arbitrage opportunity detection and classification
- Opportunity analysis and profitability calculation
- Execution tracking and performance monitoring
- Multi-exchange and multi-market arbitrage
- Triangular and cross-chain arbitrage
- Opportunity scoring and ranking
- Historical opportunity analysis
- Real-time opportunity monitoring
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

class OpportunityType(str, Enum):
    """Types of arbitrage opportunities."""
    SPOT = "spot"                      # Spot market arbitrage
    FUTURES = "futures"                # Futures market arbitrage
    PERPETUAL = "perpetual"            # Perpetual futures arbitrage
    CROSS_EXCHANGE = "cross_exchange"  # Cross-exchange arbitrage
    CROSS_MARKET = "cross_market"      # Cross-market arbitrage
    TRIANGULAR = "triangular"          # Triangular arbitrage
    CROSS_CHAIN = "cross_chain"        # Cross-chain arbitrage
    DEX_CEX = "dex_cex"               # DEX to CEX arbitrage
    DEX_DEX = "dex_dex"               # DEX to DEX arbitrage
    FUNDING_RATE = "funding_rate"      # Funding rate arbitrage
    BASIS = "basis"                    # Basis trading
    SPREAD = "spread"                  # Spread trading
    STATISTICAL = "statistical"        # Statistical arbitrage
    MEAN_REVERSION = "mean_reversion"  # Mean reversion
    MOMENTUM = "momentum"              # Momentum arbitrage
    EVENT_DRIVEN = "event_driven"      # Event-driven arbitrage


class OpportunityStatus(str, Enum):
    """Status of an arbitrage opportunity."""
    DETECTED = "detected"              # Opportunity detected
    ANALYZED = "analyzed"              # Opportunity analyzed
    PENDING = "pending"                # Pending execution
    EXECUTING = "executing"            # Being executed
    EXECUTED = "executed"              # Successfully executed
    PARTIALLY_EXECUTED = "partially_executed"  # Partially executed
    FAILED = "failed"                  # Execution failed
    CANCELLED = "cancelled"            # Cancelled
    EXPIRED = "expired"                # Expired
    SKIPPED = "skipped"                # Skipped (not profitable)
    OBSOLETE = "obsolete"              # No longer valid


class OpportunityConfidence(str, Enum):
    """Confidence levels for opportunities."""
    VERY_LOW = "very_low"              # < 20% confidence
    LOW = "low"                        # 20-40% confidence
    MEDIUM = "medium"                  # 40-60% confidence
    HIGH = "high"                      # 60-80% confidence
    VERY_HIGH = "very_high"            # > 80% confidence


class OpportunityPriority(str, Enum):
    """Priority levels for opportunity execution."""
    CRITICAL = "critical"              # Immediate execution required
    HIGH = "high"                      # Execute as soon as possible
    MEDIUM = "medium"                  # Execute when resources available
    LOW = "low"                        # Low priority execution
    BACKGROUND = "background"          # Background execution


class ArbitrageType(str, Enum):
    """Types of arbitrage strategies."""
    TWO_LEG = "two_leg"                # Two-leg arbitrage
    THREE_LEG = "three_leg"            # Three-leg arbitrage
    N_LEG = "n_leg"                    # Multi-leg arbitrage
    PAIR = "pair"                      # Pair trading
    BASKET = "basket"                  # Basket arbitrage
    INDEX = "index"                    # Index arbitrage


class ExecutionMethod(str, Enum):
    """Methods for executing opportunities."""
    ATOMIC = "atomic"                  # Atomic execution
    SEQUENTIAL = "sequential"          # Sequential execution
    PARALLEL = "parallel"              # Parallel execution
    BATCHED = "batched"                # Batched execution
    STAGGERED = "staggered"            # Staggered execution
    SMART = "smart"                    # Smart routing execution


# ====================================================================================
# OPPORTUNITY LEG MODELS
# ====================================================================================

@dataclass
class OpportunityLeg:
    """
    A single leg in an arbitrage opportunity.
    """
    # Core fields
    leg_id: str = field(default_factory=lambda: str(uuid4()))
    exchange: str = ""
    symbol: str = ""
    side: str = "buy"  # buy, sell
    quantity: float = 0.0
    price: float = 0.0
    value: float = 0.0
    fee: float = 0.0
    fee_rate: float = 0.0
    
    # Order details
    order_type: str = "market"  # market, limit
    time_in_force: str = "GTC"
    client_order_id: str = ""
    
    # Market data
    bid_price: float = 0.0
    ask_price: float = 0.0
    spread: float = 0.0
    depth: float = 0.0
    
    # Execution
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    executed_value: float = 0.0
    executed_at: Optional[datetime] = None
    order_id: str = ""
    status: str = "pending"  # pending, executing, executed, failed
    
    # Slippage
    expected_slippage: float = 0.0
    actual_slippage: float = 0.0
    slippage_ratio: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.value = self.quantity * self.price
        self.fee = self.value * self.fee_rate
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "leg_id": self.leg_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "value": self.value,
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "client_order_id": self.client_order_id,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "spread": self.spread,
            "depth": self.depth,
            "executed_quantity": self.executed_quantity,
            "executed_price": self.executed_price,
            "executed_value": self.executed_value,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "order_id": self.order_id,
            "status": self.status,
            "expected_slippage": self.expected_slippage,
            "actual_slippage": self.actual_slippage,
            "slippage_ratio": self.slippage_ratio,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpportunityLeg":
        """Create from dictionary."""
        leg = cls(
            leg_id=data.get("leg_id", str(uuid4())),
            exchange=data.get("exchange", ""),
            symbol=data.get("symbol", ""),
            side=data.get("side", "buy"),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            value=data.get("value", 0.0),
            fee=data.get("fee", 0.0),
            fee_rate=data.get("fee_rate", 0.0),
            order_type=data.get("order_type", "market"),
            time_in_force=data.get("time_in_force", "GTC"),
            client_order_id=data.get("client_order_id", ""),
            bid_price=data.get("bid_price", 0.0),
            ask_price=data.get("ask_price", 0.0),
            spread=data.get("spread", 0.0),
            depth=data.get("depth", 0.0),
            executed_quantity=data.get("executed_quantity", 0.0),
            executed_price=data.get("executed_price", 0.0),
            executed_value=data.get("executed_value", 0.0),
            order_id=data.get("order_id", ""),
            status=data.get("status", "pending"),
            expected_slippage=data.get("expected_slippage", 0.0),
            actual_slippage=data.get("actual_slippage", 0.0),
            slippage_ratio=data.get("slippage_ratio", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("executed_at"):
            leg.executed_at = datetime.fromisoformat(data["executed_at"])
            
        leg.__post_init__()
        return leg
        
    def is_executed(self) -> bool:
        """Check if leg is executed."""
        return self.status == "executed"
        
    def is_failed(self) -> bool:
        """Check if leg failed."""
        return self.status == "failed"
        
    def get_execution_ratio(self) -> float:
        """Get execution ratio (executed/expected)."""
        if self.quantity == 0:
            return 0.0
        return self.executed_quantity / self.quantity
        
    def get_slippage_cost(self) -> float:
        """Get slippage cost."""
        return self.actual_slippage * self.executed_quantity


# ====================================================================================
# OPPORTUNITY MODELS
# ====================================================================================

@dataclass
class ArbitrageOpportunity:
    """
    Complete arbitrage opportunity model.
    """
    # Core fields
    opportunity_id: str = field(default_factory=lambda: str(uuid4()))
    type: OpportunityType = OpportunityType.CROSS_EXCHANGE
    strategy: str = ""
    description: str = ""
    
    # Legs
    legs: List[OpportunityLeg] = field(default_factory=list)
    
    # Financial metrics
    gross_profit: float = 0.0
    net_profit: float = 0.0
    profit_percentage: float = 0.0
    annualized_return: float = 0.0
    total_value: float = 0.0
    total_fees: float = 0.0
    total_gas: float = 0.0
    total_cost: float = 0.0
    
    # Execution details
    execution_method: ExecutionMethod = ExecutionMethod.SEQUENTIAL
    estimated_execution_time_ms: float = 0.0
    actual_execution_time_ms: float = 0.0
    
    # Status and timing
    status: OpportunityStatus = OpportunityStatus.DETECTED
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    confidence: OpportunityConfidence = OpportunityConfidence.MEDIUM
    confidence_score: float = 0.5  # 0-1
    
    # Market conditions
    detected_at: datetime = field(default_factory=datetime.utcnow)
    analyzed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(seconds=30))
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Scoring
    score: float = 0.0
    risk_score: float = 0.0
    reward_score: float = 0.0
    efficiency_score: float = 0.0
    
    # Execution results
    execution_results: Dict[str, Any] = field(default_factory=dict)
    execution_errors: List[str] = field(default_factory=list)
    retry_count: int = 0
    
    # Market context
    symbols: List[str] = field(default_factory=list)
    exchanges: List[str] = field(default_factory=list)
    market_data: Dict[str, Any] = field(default_factory=dict)
    
    # Arbitrage type specific
    arbitrage_type: ArbitrageType = ArbitrageType.TWO_LEG
    leg_count: int = 2
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self._calculate_metrics()
        
    def _calculate_metrics(self) -> None:
        """Calculate all financial metrics."""
        if not self.legs:
            return
            
        # Calculate totals
        self.total_fees = sum(leg.fee for leg in self.legs)
        self.total_gas = sum(leg.metadata.get("gas_cost", 0.0) for leg in self.legs)
        self.total_cost = self.total_fees + self.total_gas
        
        # Calculate gross profit (buy vs sell)
        buy_value = sum(leg.value for leg in self.legs if leg.side == "buy")
        sell_value = sum(leg.value for leg in self.legs if leg.side == "sell")
        self.gross_profit = sell_value - buy_value
        self.net_profit = self.gross_profit - self.total_cost
        
        # Calculate percentages
        if buy_value > 0:
            self.profit_percentage = (self.net_profit / buy_value) * 100
            
        self.total_value = buy_value + sell_value
        self.leg_count = len(self.legs)
        
        # Calculate annualized return
        if self.profit_percentage > 0 and self.estimated_execution_time_ms > 0:
            execution_hours = self.estimated_execution_time_ms / (1000 * 3600)
            if execution_hours > 0:
                self.annualized_return = self.profit_percentage * (8760 / execution_hours)
                
        # Calculate confidence score if not set
        if self.confidence_score == 0.5 and self.legs:
            self.confidence_score = self._calculate_confidence_score()
            
        # Set confidence level based on score
        if self.confidence_score >= 0.8:
            self.confidence = OpportunityConfidence.VERY_HIGH
        elif self.confidence_score >= 0.6:
            self.confidence = OpportunityConfidence.HIGH
        elif self.confidence_score >= 0.4:
            self.confidence = OpportunityConfidence.MEDIUM
        elif self.confidence_score >= 0.2:
            self.confidence = OpportunityConfidence.LOW
        else:
            self.confidence = OpportunityConfidence.VERY_LOW
            
    def _calculate_confidence_score(self) -> float:
        """
        Calculate confidence score based on multiple factors.
        
        Returns:
            Confidence score (0-1)
        """
        score = 0.0
        factors = []
        
        # Profitability factor
        if self.net_profit > 0:
            profit_factor = min(1.0, self.net_profit / (self.total_value * 0.01))
            factors.append(profit_factor * 0.3)
            
        # Market stability factor
        avg_spread = sum(leg.spread for leg in self.legs) / len(self.legs) if self.legs else 0
        if avg_spread < 0.001:  # 0.1% spread
            stability_factor = 0.9
        elif avg_spread < 0.002:  # 0.2% spread
            stability_factor = 0.7
        elif avg_spread < 0.005:  # 0.5% spread
            stability_factor = 0.5
        else:
            stability_factor = 0.3
        factors.append(stability_factor * 0.25)
        
        # Liquidity factor
        avg_depth = sum(leg.depth for leg in self.legs) / len(self.legs) if self.legs else 0
        if avg_depth > 1000000:  # $1M depth
            liquidity_factor = 0.9
        elif avg_depth > 100000:  # $100K depth
            liquidity_factor = 0.7
        elif avg_depth > 10000:  # $10K depth
            liquidity_factor = 0.5
        else:
            liquidity_factor = 0.3
        factors.append(liquidity_factor * 0.2)
        
        # Execution time factor
        if self.estimated_execution_time_ms < 100:  # <100ms
            time_factor = 0.9
        elif self.estimated_execution_time_ms < 500:  # <500ms
            time_factor = 0.7
        elif self.estimated_execution_time_ms < 1000:  # <1s
            time_factor = 0.5
        else:
            time_factor = 0.3
        factors.append(time_factor * 0.15)
        
        # Historical success factor
        if hasattr(self, 'historical_success_rate'):
            success_factor = self.historical_success_rate
        else:
            success_factor = 0.7
        factors.append(success_factor * 0.1)
        
        score = sum(factors)
        return min(1.0, max(0.0, score))
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "opportunity_id": self.opportunity_id,
            "type": self.type.value if self.type else None,
            "strategy": self.strategy,
            "description": self.description,
            "legs": [leg.to_dict() for leg in self.legs],
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "profit_percentage": self.profit_percentage,
            "annualized_return": self.annualized_return,
            "total_value": self.total_value,
            "total_fees": self.total_fees,
            "total_gas": self.total_gas,
            "total_cost": self.total_cost,
            "execution_method": self.execution_method.value if self.execution_method else None,
            "estimated_execution_time_ms": self.estimated_execution_time_ms,
            "actual_execution_time_ms": self.actual_execution_time_ms,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "confidence": self.confidence.value if self.confidence else None,
            "confidence_score": self.confidence_score,
            "detected_at": self.detected_at.isoformat(),
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "expires_at": self.expires_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "score": self.score,
            "risk_score": self.risk_score,
            "reward_score": self.reward_score,
            "efficiency_score": self.efficiency_score,
            "execution_results": self.execution_results,
            "execution_errors": self.execution_errors,
            "retry_count": self.retry_count,
            "symbols": self.symbols,
            "exchanges": self.exchanges,
            "market_data": self.market_data,
            "arbitrage_type": self.arbitrage_type.value if self.arbitrage_type else None,
            "leg_count": self.leg_count,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArbitrageOpportunity":
        """Create from dictionary."""
        opportunity = cls(
            opportunity_id=data.get("opportunity_id", str(uuid4())),
            type=OpportunityType(data["type"]) if data.get("type") else OpportunityType.CROSS_EXCHANGE,
            strategy=data.get("strategy", ""),
            description=data.get("description", ""),
            legs=[OpportunityLeg.from_dict(l) for l in data.get("legs", [])],
            gross_profit=data.get("gross_profit", 0.0),
            net_profit=data.get("net_profit", 0.0),
            profit_percentage=data.get("profit_percentage", 0.0),
            annualized_return=data.get("annualized_return", 0.0),
            total_value=data.get("total_value", 0.0),
            total_fees=data.get("total_fees", 0.0),
            total_gas=data.get("total_gas", 0.0),
            total_cost=data.get("total_cost", 0.0),
            execution_method=ExecutionMethod(data["execution_method"]) if data.get("execution_method") else ExecutionMethod.SEQUENTIAL,
            estimated_execution_time_ms=data.get("estimated_execution_time_ms", 0.0),
            actual_execution_time_ms=data.get("actual_execution_time_ms", 0.0),
            status=OpportunityStatus(data["status"]) if data.get("status") else OpportunityStatus.DETECTED,
            priority=OpportunityPriority(data["priority"]) if data.get("priority") else OpportunityPriority.MEDIUM,
            confidence=OpportunityConfidence(data["confidence"]) if data.get("confidence") else OpportunityConfidence.MEDIUM,
            confidence_score=data.get("confidence_score", 0.5),
            score=data.get("score", 0.0),
            risk_score=data.get("risk_score", 0.0),
            reward_score=data.get("reward_score", 0.0),
            efficiency_score=data.get("efficiency_score", 0.0),
            execution_results=data.get("execution_results", {}),
            execution_errors=data.get("execution_errors", []),
            retry_count=data.get("retry_count", 0),
            symbols=data.get("symbols", []),
            exchanges=data.get("exchanges", []),
            market_data=data.get("market_data", {}),
            arbitrage_type=ArbitrageType(data["arbitrage_type"]) if data.get("arbitrage_type") else ArbitrageType.TWO_LEG,
            leg_count=data.get("leg_count", 2),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("detected_at"):
            opportunity.detected_at = datetime.fromisoformat(data["detected_at"])
        if data.get("analyzed_at"):
            opportunity.analyzed_at = datetime.fromisoformat(data["analyzed_at"])
        if data.get("executed_at"):
            opportunity.executed_at = datetime.fromisoformat(data["executed_at"])
        if data.get("expires_at"):
            opportunity.expires_at = datetime.fromisoformat(data["expires_at"])
        if data.get("updated_at"):
            opportunity.updated_at = datetime.fromisoformat(data["updated_at"])
            
        opportunity.__post_init__()
        return opportunity
        
    def is_expired(self) -> bool:
        """Check if opportunity has expired."""
        return datetime.utcnow() >= self.expires_at
        
    def is_profitable(self) -> bool:
        """Check if opportunity is profitable."""
        return self.net_profit > 0
        
    def get_time_remaining(self) -> float:
        """Get time remaining until expiration in seconds."""
        remaining = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(0, remaining)
        
    def add_leg(self, leg: OpportunityLeg) -> None:
        """
        Add a leg to the opportunity.
        
        Args:
            leg: Opportunity leg to add
        """
        self.legs.append(leg)
        self._calculate_metrics()
        self.updated_at = datetime.utcnow()
        
    def update_status(self, status: OpportunityStatus, message: str = "") -> None:
        """
        Update opportunity status.
        
        Args:
            status: New status
            message: Status update message
        """
        self.status = status
        self.updated_at = datetime.utcnow()
        if status == OpportunityStatus.EXECUTED:
            self.executed_at = datetime.utcnow()
        if message:
            self.execution_results["last_status_message"] = message
            
    def add_error(self, error: str) -> None:
        """
        Add an execution error.
        
        Args:
            error: Error message
        """
        self.execution_errors.append(error)
        self.updated_at = datetime.utcnow()
        
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = datetime.utcnow()
        
    def calculate_score(self) -> float:
        """
        Calculate overall opportunity score.
        
        Returns:
            Score value
        """
        # Profitability weight
        profit_score = min(100, self.net_profit * 10) if self.net_profit > 0 else 0
        
        # Confidence weight
        confidence_score = self.confidence_score * 100
        
        # Time sensitivity weight
        time_remaining = self.get_time_remaining()
        if time_remaining < 5:  # <5 seconds
            time_score = 100
        elif time_remaining < 30:  # <30 seconds
            time_score = 80
        elif time_remaining < 60:  # <1 minute
            time_score = 60
        elif time_remaining < 300:  # <5 minutes
            time_score = 40
        else:
            time_score = 20
            
        # Risk weight
        risk_score = (1 - self.risk_score) * 100
        
        # Weighted score
        self.score = (
            profit_score * 0.35 +
            confidence_score * 0.25 +
            time_score * 0.20 +
            risk_score * 0.20
        )
        
        return self.score


# ====================================================================================
# OPPORTUNITY SUMMARY MODELS
# ====================================================================================

@dataclass
class OpportunitySummary:
    """
    Summary of arbitrage opportunities.
    """
    # Core fields
    summary_id: str = field(default_factory=lambda: str(uuid4()))
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Opportunity counts
    total_detected: int = 0
    total_analyzed: int = 0
    total_executed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    total_expired: int = 0
    total_cancelled: int = 0
    
    # By type
    opportunities_by_type: Dict[str, int] = field(default_factory=dict)
    opportunities_by_strategy: Dict[str, int] = field(default_factory=dict)
    opportunities_by_exchange: Dict[str, int] = field(default_factory=dict)
    opportunities_by_symbol: Dict[str, int] = field(default_factory=dict)
    
    # Financial metrics
    total_gross_profit: float = 0.0
    total_net_profit: float = 0.0
    total_value: float = 0.0
    total_fees: float = 0.0
    total_gas: float = 0.0
    avg_profit: float = 0.0
    avg_profit_percentage: float = 0.0
    
    # Success metrics
    success_rate: float = 0.0
    win_rate: float = 0.0
    avg_confidence_score: float = 0.0
    
    # Top opportunities
    top_opportunities: List[ArbitrageOpportunity] = field(default_factory=list)
    best_opportunity: Optional[ArbitrageOpportunity] = None
    worst_opportunity: Optional[ArbitrageOpportunity] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": self.summary_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_detected": self.total_detected,
            "total_analyzed": self.total_analyzed,
            "total_executed": self.total_executed,
            "total_failed": self.total_failed,
            "total_skipped": self.total_skipped,
            "total_expired": self.total_expired,
            "total_cancelled": self.total_cancelled,
            "opportunities_by_type": self.opportunities_by_type,
            "opportunities_by_strategy": self.opportunities_by_strategy,
            "opportunities_by_exchange": self.opportunities_by_exchange,
            "opportunities_by_symbol": self.opportunities_by_symbol,
            "total_gross_profit": self.total_gross_profit,
            "total_net_profit": self.total_net_profit,
            "total_value": self.total_value,
            "total_fees": self.total_fees,
            "total_gas": self.total_gas,
            "avg_profit": self.avg_profit,
            "avg_profit_percentage": self.avg_profit_percentage,
            "success_rate": self.success_rate,
            "win_rate": self.win_rate,
            "avg_confidence_score": self.avg_confidence_score,
            "top_opportunities": [o.to_dict() for o in self.top_opportunities[:10]],
            "best_opportunity": self.best_opportunity.to_dict() if self.best_opportunity else None,
            "worst_opportunity": self.worst_opportunity.to_dict() if self.worst_opportunity else None,
            "metadata": self.metadata
        }


# ====================================================================================
# OPPORTUNITY FILTER MODELS
# ====================================================================================

@dataclass
class OpportunityFilter:
    """
    Filter for arbitrage opportunities.
    """
    # Basic filters
    types: List[OpportunityType] = field(default_factory=list)
    strategies: List[str] = field(default_factory=list)
    exchanges: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    
    # Status filters
    statuses: List[OpportunityStatus] = field(default_factory=list)
    priorities: List[OpportunityPriority] = field(default_factory=list)
    confidence_levels: List[OpportunityConfidence] = field(default_factory=list)
    
    # Financial filters
    min_profit: float = 0.0
    max_profit: float = float('inf')
    min_profit_percentage: float = 0.0
    max_profit_percentage: float = float('inf')
    min_confidence_score: float = 0.0
    max_confidence_score: float = 1.0
    
    # Time filters
    min_time_remaining: float = 0.0
    max_time_remaining: float = float('inf')
    since_detected: Optional[datetime] = None
    until_detected: Optional[datetime] = None
    
    # Risk filters
    max_risk_score: float = 1.0
    min_risk_score: float = 0.0
    
    # Sorting
    sort_by: str = "score"  # score, profit, confidence, time_remaining
    sort_order: str = "desc"  # asc, desc
    
    # Pagination
    limit: int = 100
    offset: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "types": [t.value for t in self.types],
            "strategies": self.strategies,
            "exchanges": self.exchanges,
            "symbols": self.symbols,
            "statuses": [s.value for s in self.statuses],
            "priorities": [p.value for p in self.priorities],
            "confidence_levels": [c.value for c in self.confidence_levels],
            "min_profit": self.min_profit,
            "max_profit": self.max_profit,
            "min_profit_percentage": self.min_profit_percentage,
            "max_profit_percentage": self.max_profit_percentage,
            "min_confidence_score": self.min_confidence_score,
            "max_confidence_score": self.max_confidence_score,
            "min_time_remaining": self.min_time_remaining,
            "max_time_remaining": self.max_time_remaining,
            "since_detected": self.since_detected.isoformat() if self.since_detected else None,
            "until_detected": self.until_detected.isoformat() if self.until_detected else None,
            "max_risk_score": self.max_risk_score,
            "min_risk_score": self.min_risk_score,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
            "limit": self.limit,
            "offset": self.offset
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_opportunity(
    type: OpportunityType = OpportunityType.CROSS_EXCHANGE,
    strategy: str = "",
    legs: List[OpportunityLeg] = None,
    **kwargs
) -> ArbitrageOpportunity:
    """
    Create a new arbitrage opportunity.
    
    Args:
        type: Opportunity type
        strategy: Strategy name
        legs: List of opportunity legs
        **kwargs: Additional opportunity fields
        
    Returns:
        ArbitrageOpportunity instance
    """
    opportunity = ArbitrageOpportunity(
        type=type,
        strategy=strategy,
        legs=legs or [],
        **kwargs
    )
    opportunity._calculate_metrics()
    return opportunity


def create_opportunity_leg(
    exchange: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    fee_rate: float = 0.001,
    **kwargs
) -> OpportunityLeg:
    """
    Create a new opportunity leg.
    
    Args:
        exchange: Exchange name
        symbol: Trading symbol
        side: buy or sell
        quantity: Order quantity
        price: Order price
        fee_rate: Fee rate (default 0.1%)
        **kwargs: Additional leg fields
        
    Returns:
        OpportunityLeg instance
    """
    return OpportunityLeg(
        exchange=exchange,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        fee_rate=fee_rate,
        **kwargs
    )


def calculate_opportunity_score(
    net_profit: float,
    confidence: float,
    time_remaining: float,
    risk: float
) -> float:
    """
    Calculate opportunity score.
    
    Args:
        net_profit: Net profit
        confidence: Confidence score (0-1)
        time_remaining: Time remaining in seconds
        risk: Risk score (0-1)
        
    Returns:
        Score (0-100)
    """
    profit_score = min(100, net_profit * 10) if net_profit > 0 else 0
    confidence_score = confidence * 100
    risk_score = (1 - risk) * 100
    
    # Time sensitivity
    if time_remaining < 5:
        time_score = 100
    elif time_remaining < 30:
        time_score = 80
    elif time_remaining < 60:
        time_score = 60
    elif time_remaining < 300:
        time_score = 40
    else:
        time_score = 20
        
    return (
        profit_score * 0.35 +
        confidence_score * 0.25 +
        time_score * 0.20 +
        risk_score * 0.20
    )


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'OpportunityType',
    'OpportunityStatus',
    'OpportunityConfidence',
    'OpportunityPriority',
    'ArbitrageType',
    'ExecutionMethod',
    
    # Core Models
    'OpportunityLeg',
    'ArbitrageOpportunity',
    'OpportunitySummary',
    'OpportunityFilter',
    
    # Helper Functions
    'create_opportunity',
    'create_opportunity_leg',
    'calculate_opportunity_score',
]
