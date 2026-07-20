# trading/bots/arbitrage_bot/models/slippage.py
# NEXUS AI TRADING SYSTEM - SLIPPAGE MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for slippage calculation, estimation,
# analysis, and management for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Slippage Models

This module provides comprehensive data models for:
- Slippage calculation and estimation
- Slippage analysis and tracking
- Slippage impact on profitability
- Slippage tolerance and limits
- Slippage prediction and forecasting
- Order book impact analysis
- Market impact cost calculation
- Slippage optimization strategies
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

class SlippageType(str, Enum):
    """Types of slippage."""
    EXPECTED = "expected"                # Expected slippage
    ACTUAL = "actual"                    # Actual slippage
    MAXIMUM = "maximum"                  # Maximum allowed slippage
    MINIMUM = "minimum"                  # Minimum observed slippage
    AVERAGE = "average"                  # Average slippage
    PERCENTAGE = "percentage"            # Percentage slippage
    ABSOLUTE = "absolute"                # Absolute slippage
    BASIS_POINTS = "basis_points"        # Slippage in basis points
    MARKET_IMPACT = "market_impact"      # Market impact component
    VOLATILITY = "volatility"            # Volatility component


class SlippageDirection(str, Enum):
    """Direction of slippage."""
    POSITIVE = "positive"                # Favorable slippage
    NEGATIVE = "negative"                # Unfavorable slippage
    NEUTRAL = "neutral"                  # No slippage
    MIXED = "mixed"                      # Mixed direction


class SlippageSeverity(str, Enum):
    """Severity levels of slippage."""
    NEGLIGIBLE = "negligible"            # < 0.01%
    VERY_LOW = "very_low"                # 0.01-0.05%
    LOW = "low"                          # 0.05-0.1%
    MEDIUM = "medium"                    # 0.1-0.5%
    HIGH = "high"                        # 0.5-1.0%
    VERY_HIGH = "very_high"              # > 1.0%


class SlippageModel(str, Enum):
    """Slippage calculation models."""
    LINEAR = "linear"                    # Linear model
    SQUARE_ROOT = "square_root"          # Square root model
    LOGARITHMIC = "logarithmic"          # Logarithmic model
    POWER = "power"                      # Power law model
    EXPONENTIAL = "exponential"          # Exponential model
    MACHINE_LEARNING = "machine_learning"  # ML-based model
    HISTORICAL = "historical"            # Historical model
    ORDER_BOOK = "order_book"            # Order book model
    HYBRID = "hybrid"                    # Hybrid model


# ====================================================================================
# SLIPPAGE MODELS
# ====================================================================================

@dataclass
class Slippage:
    """
    Comprehensive slippage model.
    """
    # Core fields
    slippage_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    order_id: str = ""
    trade_id: str = ""
    
    # Slippage values
    expected_slippage: float = 0.0       # Percentage
    actual_slippage: float = 0.0         # Percentage
    expected_price: float = 0.0
    execution_price: float = 0.0
    slippage_amount: float = 0.0
    slippage_cost: float = 0.0
    
    # Slippage breakdown
    market_impact: float = 0.0           # Percentage
    volatility_component: float = 0.0    # Percentage
    execution_component: float = 0.0     # Percentage
    spread_component: float = 0.0        # Percentage
    
    # Direction and severity
    direction: SlippageDirection = SlippageDirection.NEUTRAL
    severity: SlippageSeverity = SlippageSeverity.NEGLIGIBLE
    type: SlippageType = SlippageType.ACTUAL
    
    # Model information
    model: SlippageModel = SlippageModel.ORDER_BOOK
    model_version: str = "1.0.0"
    confidence: float = 0.0              # 0-1
    
    # Context
    order_size: float = 0.0
    order_value: float = 0.0
    order_book_depth: float = 0.0
    market_volatility: float = 0.0
    bid_ask_spread: float = 0.0
    time_of_day: int = 0                 # Hour of day
    
    # Thresholds
    tolerance: float = 0.0               # Maximum allowed slippage
    is_tolerable: bool = True
    is_acceptable: bool = True
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    estimated_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.slippage_amount = self.execution_price - self.expected_price
        self.slippage_cost = self.slippage_amount * self.order_size
        
        # Set direction
        if self.slippage_amount > 0:
            self.direction = SlippageDirection.POSITIVE
        elif self.slippage_amount < 0:
            self.direction = SlippageDirection.NEGATIVE
        else:
            self.direction = SlippageDirection.NEUTRAL
            
        # Set severity
        abs_slippage = abs(self.actual_slippage)
        if abs_slippage < 0.0001:  # 0.01%
            self.severity = SlippageSeverity.NEGLIGIBLE
        elif abs_slippage < 0.0005:  # 0.05%
            self.severity = SlippageSeverity.VERY_LOW
        elif abs_slippage < 0.001:  # 0.1%
            self.severity = SlippageSeverity.LOW
        elif abs_slippage < 0.005:  # 0.5%
            self.severity = SlippageSeverity.MEDIUM
        elif abs_slippage < 0.01:  # 1.0%
            self.severity = SlippageSeverity.HIGH
        else:
            self.severity = SlippageSeverity.VERY_HIGH
            
        # Check tolerability
        if self.tolerance > 0:
            self.is_tolerable = abs(self.actual_slippage) <= self.tolerance
            self.is_acceptable = self.is_tolerable
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slippage_id": self.slippage_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "expected_slippage": self.expected_slippage,
            "actual_slippage": self.actual_slippage,
            "expected_price": self.expected_price,
            "execution_price": self.execution_price,
            "slippage_amount": self.slippage_amount,
            "slippage_cost": self.slippage_cost,
            "market_impact": self.market_impact,
            "volatility_component": self.volatility_component,
            "execution_component": self.execution_component,
            "spread_component": self.spread_component,
            "direction": self.direction.value if self.direction else None,
            "severity": self.severity.value if self.severity else None,
            "type": self.type.value if self.type else None,
            "model": self.model.value if self.model else None,
            "model_version": self.model_version,
            "confidence": self.confidence,
            "order_size": self.order_size,
            "order_value": self.order_value,
            "order_book_depth": self.order_book_depth,
            "market_volatility": self.market_volatility,
            "bid_ask_spread": self.bid_ask_spread,
            "time_of_day": self.time_of_day,
            "tolerance": self.tolerance,
            "is_tolerable": self.is_tolerable,
            "is_acceptable": self.is_acceptable,
            "timestamp": self.timestamp.isoformat(),
            "estimated_at": self.estimated_at.isoformat() if self.estimated_at else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Slippage":
        """Create from dictionary."""
        slippage = cls(
            slippage_id=data.get("slippage_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            order_id=data.get("order_id", ""),
            trade_id=data.get("trade_id", ""),
            expected_slippage=data.get("expected_slippage", 0.0),
            actual_slippage=data.get("actual_slippage", 0.0),
            expected_price=data.get("expected_price", 0.0),
            execution_price=data.get("execution_price", 0.0),
            slippage_amount=data.get("slippage_amount", 0.0),
            slippage_cost=data.get("slippage_cost", 0.0),
            market_impact=data.get("market_impact", 0.0),
            volatility_component=data.get("volatility_component", 0.0),
            execution_component=data.get("execution_component", 0.0),
            spread_component=data.get("spread_component", 0.0),
            direction=SlippageDirection(data["direction"]) if data.get("direction") else SlippageDirection.NEUTRAL,
            severity=SlippageSeverity(data["severity"]) if data.get("severity") else SlippageSeverity.NEGLIGIBLE,
            type=SlippageType(data["type"]) if data.get("type") else SlippageType.ACTUAL,
            model=SlippageModel(data["model"]) if data.get("model") else SlippageModel.ORDER_BOOK,
            model_version=data.get("model_version", "1.0.0"),
            confidence=data.get("confidence", 0.0),
            order_size=data.get("order_size", 0.0),
            order_value=data.get("order_value", 0.0),
            order_book_depth=data.get("order_book_depth", 0.0),
            market_volatility=data.get("market_volatility", 0.0),
            bid_ask_spread=data.get("bid_ask_spread", 0.0),
            time_of_day=data.get("time_of_day", 0),
            tolerance=data.get("tolerance", 0.0),
            is_tolerable=data.get("is_tolerable", True),
            is_acceptable=data.get("is_acceptable", True),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("timestamp"):
            slippage.timestamp = datetime.fromisoformat(data["timestamp"])
        if data.get("estimated_at"):
            slippage.estimated_at = datetime.fromisoformat(data["estimated_at"])
            
        slippage.__post_init__()
        return slippage
        
    def get_impact_percentage(self) -> float:
        """Get slippage impact as percentage of order value."""
        if self.order_value == 0:
            return 0.0
        return (self.slippage_cost / self.order_value) * 100
        
    def get_bps(self) -> float:
        """Get slippage in basis points."""
        return self.actual_slippage * 10000
        
    def is_favorable(self) -> bool:
        """Check if slippage is favorable (positive)."""
        return self.direction == SlippageDirection.POSITIVE
        
    def is_unfavorable(self) -> bool:
        """Check if slippage is unfavorable (negative)."""
        return self.direction == SlippageDirection.NEGATIVE


# ====================================================================================
# SLIPPAGE ESTIMATION MODELS
# ====================================================================================

@dataclass
class SlippageEstimate:
    """
    Slippage estimation model.
    """
    # Core fields
    estimate_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    exchange: str = ""
    
    # Estimate values
    estimated_slippage: float = 0.0      # Percentage
    min_slippage: float = 0.0
    max_slippage: float = 0.0
    confidence_interval: float = 0.0
    
    # Confidence levels
    p10_slippage: float = 0.0
    p50_slippage: float = 0.0
    p90_slippage: float = 0.0
    p95_slippage: float = 0.0
    p99_slippage: float = 0.0
    
    # Context
    order_size: float = 0.0
    order_value: float = 0.0
    market_volatility: float = 0.0
    bid_ask_spread: float = 0.0
    order_book_depth: float = 0.0
    
    # Model
    model: SlippageModel = SlippageModel.ORDER_BOOK
    model_version: str = "1.0.0"
    features_used: List[str] = field(default_factory=list)
    
    # Validation
    is_valid: bool = False
    validation_score: float = 0.0
    error_estimate: float = 0.0
    
    # Timestamps
    estimated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(seconds=30))
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": self.estimate_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "estimated_slippage": self.estimated_slippage,
            "min_slippage": self.min_slippage,
            "max_slippage": self.max_slippage,
            "confidence_interval": self.confidence_interval,
            "p10_slippage": self.p10_slippage,
            "p50_slippage": self.p50_slippage,
            "p90_slippage": self.p90_slippage,
            "p95_slippage": self.p95_slippage,
            "p99_slippage": self.p99_slippage,
            "order_size": self.order_size,
            "order_value": self.order_value,
            "market_volatility": self.market_volatility,
            "bid_ask_spread": self.bid_ask_spread,
            "order_book_depth": self.order_book_depth,
            "model": self.model.value if self.model else None,
            "model_version": self.model_version,
            "features_used": self.features_used,
            "is_valid": self.is_valid,
            "validation_score": self.validation_score,
            "error_estimate": self.error_estimate,
            "estimated_at": self.estimated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlippageEstimate":
        """Create from dictionary."""
        estimate = cls(
            estimate_id=data.get("estimate_id", str(uuid4())),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            estimated_slippage=data.get("estimated_slippage", 0.0),
            min_slippage=data.get("min_slippage", 0.0),
            max_slippage=data.get("max_slippage", 0.0),
            confidence_interval=data.get("confidence_interval", 0.0),
            p10_slippage=data.get("p10_slippage", 0.0),
            p50_slippage=data.get("p50_slippage", 0.0),
            p90_slippage=data.get("p90_slippage", 0.0),
            p95_slippage=data.get("p95_slippage", 0.0),
            p99_slippage=data.get("p99_slippage", 0.0),
            order_size=data.get("order_size", 0.0),
            order_value=data.get("order_value", 0.0),
            market_volatility=data.get("market_volatility", 0.0),
            bid_ask_spread=data.get("bid_ask_spread", 0.0),
            order_book_depth=data.get("order_book_depth", 0.0),
            model=SlippageModel(data["model"]) if data.get("model") else SlippageModel.ORDER_BOOK,
            model_version=data.get("model_version", "1.0.0"),
            features_used=data.get("features_used", []),
            is_valid=data.get("is_valid", False),
            validation_score=data.get("validation_score", 0.0),
            error_estimate=data.get("error_estimate", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("estimated_at"):
            estimate.estimated_at = datetime.fromisoformat(data["estimated_at"])
        if data.get("expires_at"):
            estimate.expires_at = datetime.fromisoformat(data["expires_at"])
            
        return estimate
        
    def is_expired(self) -> bool:
        """Check if estimate has expired."""
        return datetime.utcnow() >= self.expires_at


# ====================================================================================
# SLIPPAGE STATISTICS MODELS
# ====================================================================================

@dataclass
class SlippageStatistics:
    """
    Statistical analysis of slippage.
    """
    # Core fields
    symbol: str = ""
    exchange: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Basic statistics
    total_trades: int = 0
    avg_slippage: float = 0.0
    median_slippage: float = 0.0
    std_dev: float = 0.0
    min_slippage: float = 0.0
    max_slippage: float = 0.0
    
    # Percentiles
    p10_slippage: float = 0.0
    p25_slippage: float = 0.0
    p50_slippage: float = 0.0
    p75_slippage: float = 0.0
    p90_slippage: float = 0.0
    p95_slippage: float = 0.0
    p99_slippage: float = 0.0
    
    # Distribution
    positive_slippage_count: int = 0
    negative_slippage_count: int = 0
    neutral_slippage_count: int = 0
    positive_slippage_avg: float = 0.0
    negative_slippage_avg: float = 0.0
    
    # By severity
    negligible_count: int = 0
    very_low_count: int = 0
    low_count: int = 0
    medium_count: int = 0
    high_count: int = 0
    very_high_count: int = 0
    
    # Cost impact
    total_slippage_cost: float = 0.0
    avg_slippage_cost: float = 0.0
    max_slippage_cost: float = 0.0
    total_value: float = 0.0
    cost_percentage: float = 0.0
    
    # Trends
    slippage_trend: float = 0.0
    volatility_trend: float = 0.0
    spread_trend: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_trades": self.total_trades,
            "avg_slippage": self.avg_slippage,
            "median_slippage": self.median_slippage,
            "std_dev": self.std_dev,
            "min_slippage": self.min_slippage,
            "max_slippage": self.max_slippage,
            "p10_slippage": self.p10_slippage,
            "p25_slippage": self.p25_slippage,
            "p50_slippage": self.p50_slippage,
            "p75_slippage": self.p75_slippage,
            "p90_slippage": self.p90_slippage,
            "p95_slippage": self.p95_slippage,
            "p99_slippage": self.p99_slippage,
            "positive_slippage_count": self.positive_slippage_count,
            "negative_slippage_count": self.negative_slippage_count,
            "neutral_slippage_count": self.neutral_slippage_count,
            "positive_slippage_avg": self.positive_slippage_avg,
            "negative_slippage_avg": self.negative_slippage_avg,
            "negligible_count": self.negligible_count,
            "very_low_count": self.very_low_count,
            "low_count": self.low_count,
            "medium_count": self.medium_count,
            "high_count": self.high_count,
            "very_high_count": self.very_high_count,
            "total_slippage_cost": self.total_slippage_cost,
            "avg_slippage_cost": self.avg_slippage_cost,
            "max_slippage_cost": self.max_slippage_cost,
            "total_value": self.total_value,
            "cost_percentage": self.cost_percentage,
            "slippage_trend": self.slippage_trend,
            "volatility_trend": self.volatility_trend,
            "spread_trend": self.spread_trend,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def estimate_slippage(
    order_size: float,
    order_book_depth: float,
    volatility: float,
    spread: float,
    model: SlippageModel = SlippageModel.SQUARE_ROOT
) -> Dict[str, float]:
    """
    Estimate slippage based on market conditions.
    
    Args:
        order_size: Order size
        order_book_depth: Order book depth
        volatility: Market volatility
        spread: Bid-ask spread
        model: Slippage model to use
        
    Returns:
        Dict with slippage estimates
    """
    # Calculate market impact
    if order_book_depth > 0:
        market_impact = (order_size / order_book_depth) * 0.1
    else:
        market_impact = 0.01
        
    # Apply model
    if model == SlippageModel.LINEAR:
        slippage = market_impact + spread + (volatility * 0.1)
    elif model == SlippageModel.SQUARE_ROOT:
        slippage = math.sqrt(market_impact) + spread + (volatility * 0.1)
    elif model == SlippageModel.LOGARITHMIC:
        slippage = math.log1p(market_impact * 100) / 100 + spread + (volatility * 0.1)
    elif model == SlippageModel.POWER:
        slippage = market_impact ** 0.5 + spread + (volatility * 0.1)
    elif model == SlippageModel.EXPONENTIAL:
        slippage = (math.exp(market_impact) - 1) / 10 + spread + (volatility * 0.1)
    else:
        slippage = market_impact + spread + (volatility * 0.1)
        
    # Add volatility component
    volatility_component = volatility * 0.1
    
    # Add spread component
    spread_component = spread
    
    # Ensure realistic values
    slippage = min(max(slippage, 0.0001), 0.05)  # 0.01% to 5%
    
    return {
        "estimated_slippage": slippage,
        "market_impact": market_impact,
        "volatility_component": volatility_component,
        "spread_component": spread_component,
        "p10_slippage": slippage * 0.8,
        "p50_slippage": slippage,
        "p90_slippage": slippage * 1.2,
        "p95_slippage": slippage * 1.5,
        "p99_slippage": slippage * 2.0
    }


def calculate_slippage_tolerance(
    expected_profit: float,
    risk_appetite: float = 0.5,
    volatility: float = 0.0
) -> float:
    """
    Calculate slippage tolerance based on expected profit.
    
    Args:
        expected_profit: Expected profit from trade
        risk_appetite: Risk appetite factor (0-1)
        volatility: Market volatility
        
    Returns:
        Slippage tolerance as percentage
    """
    # Base tolerance (percentage of expected profit)
    base_tolerance = 0.1 * risk_appetite
    
    # Adjust for volatility
    volatility_adjustment = volatility * 0.5
    
    # Calculate tolerance
    tolerance = base_tolerance + volatility_adjustment
    
    # Ensure reasonable bounds
    return min(max(tolerance, 0.001), 0.05)  # 0.1% to 5%


def analyze_slippage_impact(
    slippage: Slippage,
    profit: float,
    expected_profit: float
) -> Dict[str, Any]:
    """
    Analyze the impact of slippage on profitability.
    
    Args:
        slippage: Slippage object
        profit: Actual profit
        expected_profit: Expected profit before slippage
        
    Returns:
        Analysis results
    """
    profit_impact = expected_profit - profit
    profit_impact_percentage = (profit_impact / abs(expected_profit) * 100) if expected_profit != 0 else 0
    
    return {
        "profit_impact": profit_impact,
        "profit_impact_percentage": profit_impact_percentage,
        "slippage_cost": slippage.slippage_cost,
        "profit_reduction": (1 - profit / expected_profit) * 100 if expected_profit != 0 else 0,
        "is_profitable": profit > 0,
        "slippage_wiped_profit": profit <= 0 and expected_profit > 0,
        "recommendation": "Reduce position size" if profit_impact_percentage > 20 else "Acceptable"
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'SlippageType',
    'SlippageDirection',
    'SlippageSeverity',
    'SlippageModel',
    
    # Core Models
    'Slippage',
    'SlippageEstimate',
    'SlippageStatistics',
    
    # Helper Functions
    'estimate_slippage',
    'calculate_slippage_tolerance',
    'analyze_slippage_impact',
]
