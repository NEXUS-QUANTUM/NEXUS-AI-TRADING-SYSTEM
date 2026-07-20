# trading/bots/arbitrage_bot/models/risk.py
# NEXUS AI TRADING SYSTEM - RISK MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for risk management, risk assessment,
# risk monitoring, and risk mitigation for the arbitrage bot.
# ====================================================================================

"""
NEXUS Arbitrage Bot Risk Models

This module provides comprehensive data models for:
- Risk assessment and scoring
- Position risk management
- Portfolio risk analysis
- Market risk monitoring
- Counterparty risk assessment
- Liquidity risk management
- Operational risk control
- Compliance and regulatory risk
- Risk limits and thresholds
- Risk reporting and alerts
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

class RiskType(str, Enum):
    """Types of risk."""
    MARKET = "market"                    # Market risk
    CREDIT = "credit"                    # Credit risk
    LIQUIDITY = "liquidity"              # Liquidity risk
    OPERATIONAL = "operational"          # Operational risk
    COUNTERPARTY = "counterparty"        # Counterparty risk
    REGULATORY = "regulatory"            # Regulatory risk
    REPUTATIONAL = "reputational"        # Reputational risk
    SYSTEMIC = "systemic"                # Systemic risk
    CONCENTRATION = "concentration"      # Concentration risk
    MODEL = "model"                      # Model risk
    EXECUTION = "execution"              # Execution risk
    TECHNOLOGY = "technology"            # Technology risk
    LEGAL = "legal"                      # Legal risk
    COMPLIANCE = "compliance"            # Compliance risk
    FRAUD = "fraud"                      # Fraud risk
    CYBERSECURITY = "cybersecurity"      # Cybersecurity risk


class RiskLevel(str, Enum):
    """Risk severity levels."""
    VERY_LOW = "very_low"                # Minimal risk
    LOW = "low"                          # Low risk
    MEDIUM = "medium"                    # Moderate risk
    HIGH = "high"                        # High risk
    VERY_HIGH = "very_high"              # Critical risk
    EXTREME = "extreme"                  # Extreme risk


class RiskCategory(str, Enum):
    """Categories for risk classification."""
    TRADING = "trading"                  # Trading risk
    PORTFOLIO = "portfolio"              # Portfolio risk
    EXCHANGE = "exchange"                # Exchange risk
    MARKET = "market"                    # Market risk
    OPERATIONAL = "operational"          # Operational risk
    STRATEGY = "strategy"                # Strategy risk
    POSITION = "position"                # Position risk
    SYSTEM = "system"                    # System risk
    EXTERNAL = "external"                # External risk
    REGULATORY = "regulatory"            # Regulatory risk


class RiskMetric(str, Enum):
    """Risk metrics for measurement."""
    VAR = "var"                          # Value at Risk
    CVAR = "cvar"                        # Conditional VaR
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    PAIN_INDEX = "pain_index"
    ULCER_INDEX = "ulcer_index"
    MARGIN_UTILIZATION = "margin_utilization"
    LEVERAGE_RATIO = "leverage_ratio"
    CONCENTRATION_RATIO = "concentration_ratio"
    LIQUIDITY_RATIO = "liquidity_ratio"
    CURRENCY_EXPOSURE = "currency_exposure"


class RiskAction(str, Enum):
    """Actions to mitigate risk."""
    REDUCE_POSITION = "reduce_position"
    CLOSE_POSITION = "close_position"
    HEDGE = "hedge"
    REBALANCE = "rebalance"
    PAUSE_TRADING = "pause_trading"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    ADJUST_LEVERAGE = "adjust_leverage"
    DIVERSIFY = "diversify"
    LIQUIDATE = "liquidate"
    ALERT = "alert"
    REVIEW = "review"
    MANUAL_INTERVENTION = "manual_intervention"


# ====================================================================================
# RISK METRIC MODELS
# ====================================================================================

@dataclass
class RiskMetricValue:
    """
    Single risk metric value.
    """
    # Core fields
    metric_id: str = field(default_factory=lambda: str(uuid4()))
    metric: RiskMetric = RiskMetric.VAR
    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Context
    symbol: str = ""
    exchange: str = ""
    portfolio_id: str = ""
    strategy_id: str = ""
    
    # Confidence and thresholds
    confidence_level: float = 0.0         # 0-1
    threshold: float = 0.0                # Warning threshold
    critical_threshold: float = 0.0       # Critical threshold
    
    # Time horizon
    horizon: str = "1d"                   # 1h, 4h, 1d, 1w, 1M
    
    # Status
    is_breach: bool = False
    is_critical: bool = False
    status: str = "normal"                # normal, warning, critical
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "metric": self.metric.value if self.metric else None,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "exchange": self.exchange,
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "confidence_level": self.confidence_level,
            "threshold": self.threshold,
            "critical_threshold": self.critical_threshold,
            "horizon": self.horizon,
            "is_breach": self.is_breach,
            "is_critical": self.is_critical,
            "status": self.status,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskMetricValue":
        """Create from dictionary."""
        metric = cls(
            metric_id=data.get("metric_id", str(uuid4())),
            metric=RiskMetric(data["metric"]) if data.get("metric") else RiskMetric.VAR,
            value=data.get("value", 0.0),
            symbol=data.get("symbol", ""),
            exchange=data.get("exchange", ""),
            portfolio_id=data.get("portfolio_id", ""),
            strategy_id=data.get("strategy_id", ""),
            confidence_level=data.get("confidence_level", 0.0),
            threshold=data.get("threshold", 0.0),
            critical_threshold=data.get("critical_threshold", 0.0),
            horizon=data.get("horizon", "1d"),
            is_breach=data.get("is_breach", False),
            is_critical=data.get("is_critical", False),
            status=data.get("status", "normal"),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            metric.timestamp = datetime.fromisoformat(data["timestamp"])
            
        return metric
        
    def check_breach(self) -> None:
        """Check if metric breaches thresholds."""
        self.is_breach = self.value >= self.threshold if self.threshold > 0 else False
        self.is_critical = self.value >= self.critical_threshold if self.critical_threshold > 0 else False
        
        if self.is_critical:
            self.status = "critical"
        elif self.is_breach:
            self.status = "warning"
        else:
            self.status = "normal"


# ====================================================================================
# RISK ASSESSMENT MODELS
# ====================================================================================

@dataclass
class RiskAssessment:
    """
    Comprehensive risk assessment for a portfolio or position.
    """
    # Core fields
    assessment_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Overall risk
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    overall_risk_score: float = 0.0       # 0-100
    
    # Category scores
    market_risk_score: float = 0.0
    credit_risk_score: float = 0.0
    liquidity_risk_score: float = 0.0
    operational_risk_score: float = 0.0
    counterparty_risk_score: float = 0.0
    regulatory_risk_score: float = 0.0
    concentration_risk_score: float = 0.0
    
    # Metric values
    metrics: Dict[str, RiskMetricValue] = field(default_factory=dict)
    
    # Breaches
    breaches: List[RiskMetricValue] = field(default_factory=list)
    critical_breaches: List[RiskMetricValue] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    recommended_actions: List[RiskAction] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate risk scores."""
        self._calculate_scores()
        
    def _calculate_scores(self) -> None:
        """Calculate risk scores from metrics."""
        # Calculate overall risk score (0-100)
        scores = [
            self.market_risk_score,
            self.credit_risk_score,
            self.liquidity_risk_score,
            self.operational_risk_score,
            self.counterparty_risk_score,
            self.regulatory_risk_score,
            self.concentration_risk_score
        ]
        
        # Weighted average
        weights = [0.25, 0.10, 0.15, 0.10, 0.10, 0.15, 0.15]
        self.overall_risk_score = sum(s * w for s, w in zip(scores, weights))
        
        # Determine risk level
        if self.overall_risk_score < 20:
            self.overall_risk_level = RiskLevel.VERY_LOW
        elif self.overall_risk_score < 40:
            self.overall_risk_level = RiskLevel.LOW
        elif self.overall_risk_score < 60:
            self.overall_risk_level = RiskLevel.MEDIUM
        elif self.overall_risk_score < 80:
            self.overall_risk_level = RiskLevel.HIGH
        else:
            self.overall_risk_level = RiskLevel.VERY_HIGH
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_risk_level": self.overall_risk_level.value if self.overall_risk_level else None,
            "overall_risk_score": self.overall_risk_score,
            "market_risk_score": self.market_risk_score,
            "credit_risk_score": self.credit_risk_score,
            "liquidity_risk_score": self.liquidity_risk_score,
            "operational_risk_score": self.operational_risk_score,
            "counterparty_risk_score": self.counterparty_risk_score,
            "regulatory_risk_score": self.regulatory_risk_score,
            "concentration_risk_score": self.concentration_risk_score,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "breaches": [b.to_dict() for b in self.breaches],
            "critical_breaches": [b.to_dict() for b in self.critical_breaches],
            "recommendations": self.recommendations,
            "recommended_actions": [a.value for a in self.recommended_actions],
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        """Create from dictionary."""
        assessment = cls(
            assessment_id=data.get("assessment_id", str(uuid4())),
            overall_risk_level=RiskLevel(data["overall_risk_level"]) if data.get("overall_risk_level") else RiskLevel.MEDIUM,
            overall_risk_score=data.get("overall_risk_score", 0.0),
            market_risk_score=data.get("market_risk_score", 0.0),
            credit_risk_score=data.get("credit_risk_score", 0.0),
            liquidity_risk_score=data.get("liquidity_risk_score", 0.0),
            operational_risk_score=data.get("operational_risk_score", 0.0),
            counterparty_risk_score=data.get("counterparty_risk_score", 0.0),
            regulatory_risk_score=data.get("regulatory_risk_score", 0.0),
            concentration_risk_score=data.get("concentration_risk_score", 0.0),
            metrics={k: RiskMetricValue.from_dict(v) for k, v in data.get("metrics", {}).items()},
            breaches=[RiskMetricValue.from_dict(b) for b in data.get("breaches", [])],
            critical_breaches=[RiskMetricValue.from_dict(b) for b in data.get("critical_breaches", [])],
            recommendations=data.get("recommendations", []),
            recommended_actions=[RiskAction(a) for a in data.get("recommended_actions", [])],
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamp
        if data.get("timestamp"):
            assessment.timestamp = datetime.fromisoformat(data["timestamp"])
            
        assessment.__post_init__()
        return assessment
        
    def add_metric(self, metric: RiskMetricValue) -> None:
        """
        Add a risk metric.
        
        Args:
            metric: Risk metric to add
        """
        self.metrics[metric.metric.value] = metric
        if metric.is_breach:
            self.breaches.append(metric)
        if metric.is_critical:
            self.critical_breaches.append(metric)
            
    def generate_recommendations(self) -> None:
        """Generate risk mitigation recommendations."""
        self.recommendations = []
        self.recommended_actions = []
        
        # Based on risk scores
        if self.overall_risk_score > 70:
            self.recommendations.append({
                "priority": "high",
                "message": "Overall risk is very high. Consider reducing exposure.",
                "category": "overall"
            })
            self.recommended_actions.append(RiskAction.PAUSE_TRADING)
            
        if self.market_risk_score > 70:
            self.recommendations.append({
                "priority": "high",
                "message": "Market risk is elevated. Consider hedging positions.",
                "category": "market"
            })
            self.recommended_actions.append(RiskAction.HEDGE)
            
        if self.concentration_risk_score > 60:
            self.recommendations.append({
                "priority": "medium",
                "message": "Concentration risk is high. Consider diversifying positions.",
                "category": "concentration"
            })
            self.recommended_actions.append(RiskAction.DIVERSIFY)
            
        if self.liquidity_risk_score > 60:
            self.recommendations.append({
                "priority": "high",
                "message": "Liquidity risk is elevated. Consider reducing position sizes.",
                "category": "liquidity"
            })
            self.recommended_actions.append(RiskAction.REDUCE_POSITION)
            
        # Check metric breaches
        for metric in self.critical_breaches:
            self.recommendations.append({
                "priority": "critical",
                "message": f"Critical breach: {metric.metric.value} = {metric.value:.2f}",
                "category": "metric"
            })
            self.recommended_actions.append(RiskAction.ALERT)


# ====================================================================================
# POSITION RISK MODELS
# ====================================================================================

@dataclass
class PositionRisk:
    """
    Risk assessment for a single position.
    """
    # Core fields
    position_id: str = ""
    symbol: str = ""
    exchange: str = ""
    
    # Position details
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    side: str = "long"
    leverage: int = 1
    
    # Risk metrics
    value_at_risk: float = 0.0
    expected_shortfall: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    volatility: float = 0.0
    
    # Liquidation risk
    liquidation_price: float = 0.0
    liquidation_distance: float = 0.0
    liquidation_risk_score: float = 0.0
    
    # Margin risk
    margin_used: float = 0.0
    margin_utilization: float = 0.0
    maintenance_margin: float = 0.0
    
    # Risk score
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    
    # Risk limits
    position_limit: float = 0.0
    var_limit: float = 0.0
    drawdown_limit: float = 0.0
    
    # Breaches
    is_position_limit_breached: bool = False
    is_var_limit_breached: bool = False
    is_drawdown_limit_breached: bool = False
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate risk metrics."""
        self._calculate_risk_metrics()
        
    def _calculate_risk_metrics(self) -> None:
        """Calculate all risk metrics."""
        # Position value
        position_value = self.size * self.current_price
        
        # Value at Risk (95% confidence)
        if self.volatility > 0 and position_value > 0:
            self.value_at_risk = position_value * self.volatility * 1.645
            self.expected_shortfall = self.value_at_risk * 1.2
            
        # Max drawdown
        if self.entry_price > 0:
            if self.side == "long":
                self.max_drawdown = (self.entry_price - self.current_price) / self.entry_price * 100
                self.current_drawdown = self.max_drawdown
            else:
                self.max_drawdown = (self.current_price - self.entry_price) / self.entry_price * 100
                self.current_drawdown = self.max_drawdown
                
        # Liquidation risk
        if self.liquidation_price > 0:
            if self.side == "long":
                self.liquidation_distance = (self.current_price - self.liquidation_price) / self.current_price * 100
            else:
                self.liquidation_distance = (self.liquidation_price - self.current_price) / self.current_price * 100
                
            if self.liquidation_distance < 10:
                self.liquidation_risk_score = 100 - self.liquidation_distance * 10
            else:
                self.liquidation_risk_score = 0
                
        # Margin utilization
        if position_value > 0:
            self.margin_utilization = (self.margin_used / position_value) * 100
            
        # Overall risk score (0-100)
        self.risk_score = (
            self.value_at_risk * 0.3 +
            abs(self.current_drawdown) * 0.2 +
            self.liquidation_risk_score * 0.2 +
            self.margin_utilization * 0.3
        )
        
        # Risk level
        if self.risk_score < 20:
            self.risk_level = RiskLevel.VERY_LOW
        elif self.risk_score < 40:
            self.risk_level = RiskLevel.LOW
        elif self.risk_score < 60:
            self.risk_level = RiskLevel.MEDIUM
        elif self.risk_score < 80:
            self.risk_level = RiskLevel.HIGH
        else:
            self.risk_level = RiskLevel.VERY_HIGH
            
        # Check limits
        self.is_position_limit_breached = self.size > self.position_limit if self.position_limit > 0 else False
        self.is_var_limit_breached = self.value_at_risk > self.var_limit if self.var_limit > 0 else False
        self.is_drawdown_limit_breached = abs(self.current_drawdown) > self.drawdown_limit if self.drawdown_limit > 0 else False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "side": self.side,
            "leverage": self.leverage,
            "value_at_risk": self.value_at_risk,
            "expected_shortfall": self.expected_shortfall,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "volatility": self.volatility,
            "liquidation_price": self.liquidation_price,
            "liquidation_distance": self.liquidation_distance,
            "liquidation_risk_score": self.liquidation_risk_score,
            "margin_used": self.margin_used,
            "margin_utilization": self.margin_utilization,
            "maintenance_margin": self.maintenance_margin,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value if self.risk_level else None,
            "position_limit": self.position_limit,
            "var_limit": self.var_limit,
            "drawdown_limit": self.drawdown_limit,
            "is_position_limit_breached": self.is_position_limit_breached,
            "is_var_limit_breached": self.is_var_limit_breached,
            "is_drawdown_limit_breached": self.is_drawdown_limit_breached,
            "metadata": self.metadata
        }


# ====================================================================================
# RISK LIMIT MODELS
# ====================================================================================

@dataclass
class RiskLimit:
    """
    Risk limit definition and tracking.
    """
    # Core fields
    limit_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: RiskType = RiskType.MARKET
    category: RiskCategory = RiskCategory.TRADING
    
    # Limit values
    limit_value: float = 0.0
    warning_threshold: float = 0.0       # % of limit
    critical_threshold: float = 0.0      # % of limit
    current_value: float = 0.0
    current_utilization: float = 0.0
    
    # Scope
    scope: str = "portfolio"             # portfolio, strategy, position, exchange
    scope_id: str = ""
    
    # Timeframe
    timeframe: str = "1d"                # 1h, 4h, 1d, 1w, 1M
    
    # Status
    status: str = "normal"               # normal, warning, critical, breached
    is_breached: bool = False
    is_critical: bool = False
    
    # History
    breach_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Actions
    action_on_breach: RiskAction = RiskAction.ALERT
    auto_recovery: bool = False
    recovery_timeout: int = 3600          # seconds
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate utilization and status."""
        if self.limit_value > 0:
            self.current_utilization = (self.current_value / self.limit_value) * 100
        else:
            self.current_utilization = 0
            
        # Check thresholds
        if self.current_utilization >= self.critical_threshold:
            self.status = "critical"
            self.is_critical = True
            self.is_breached = True
        elif self.current_utilization >= self.warning_threshold:
            self.status = "warning"
            self.is_breached = True
        else:
            self.status = "normal"
            self.is_breached = False
            self.is_critical = False
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "limit_id": self.limit_id,
            "name": self.name,
            "type": self.type.value if self.type else None,
            "category": self.category.value if self.category else None,
            "limit_value": self.limit_value,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "current_value": self.current_value,
            "current_utilization": self.current_utilization,
            "scope": self.scope,
            "scope_id": self.scope_id,
            "timeframe": self.timeframe,
            "status": self.status,
            "is_breached": self.is_breached,
            "is_critical": self.is_critical,
            "breach_history": self.breach_history,
            "action_on_breach": self.action_on_breach.value if self.action_on_breach else None,
            "auto_recovery": self.auto_recovery,
            "recovery_timeout": self.recovery_timeout,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskLimit":
        """Create from dictionary."""
        limit = cls(
            limit_id=data.get("limit_id", str(uuid4())),
            name=data.get("name", ""),
            type=RiskType(data["type"]) if data.get("type") else RiskType.MARKET,
            category=RiskCategory(data["category"]) if data.get("category") else RiskCategory.TRADING,
            limit_value=data.get("limit_value", 0.0),
            warning_threshold=data.get("warning_threshold", 0.0),
            critical_threshold=data.get("critical_threshold", 0.0),
            current_value=data.get("current_value", 0.0),
            scope=data.get("scope", "portfolio"),
            scope_id=data.get("scope_id", ""),
            timeframe=data.get("timeframe", "1d"),
            status=data.get("status", "normal"),
            is_breached=data.get("is_breached", False),
            is_critical=data.get("is_critical", False),
            breach_history=data.get("breach_history", []),
            action_on_breach=RiskAction(data["action_on_breach"]) if data.get("action_on_breach") else RiskAction.ALERT,
            auto_recovery=data.get("auto_recovery", False),
            recovery_timeout=data.get("recovery_timeout", 3600),
            metadata=data.get("metadata", {})
        )
        limit.__post_init__()
        return limit
        
    def update_value(self, value: float) -> None:
        """
        Update current value.
        
        Args:
            value: New current value
        """
        self.current_value = value
        self.__post_init__()
        
        if self.is_breached:
            self.breach_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "value": self.current_value,
                "utilization": self.current_utilization,
                "status": self.status
            })


# ====================================================================================
# RISK REPORT MODELS
# ====================================================================================

@dataclass
class RiskReport:
    """
    Comprehensive risk report.
    """
    # Core fields
    report_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Summary
    overall_risk_level: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 0.0
    risk_change: float = 0.0              # Change from previous period
    
    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Breaches
    active_breaches: List[Dict[str, Any]] = field(default_factory=list)
    resolved_breaches: List[Dict[str, Any]] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Summary by category
    risk_by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    risk_by_exchange: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    risk_by_strategy: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp.isoformat(),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "overall_risk_level": self.overall_risk_level.value if self.overall_risk_level else None,
            "risk_score": self.risk_score,
            "risk_change": self.risk_change,
            "metrics": self.metrics,
            "active_breaches": self.active_breaches,
            "resolved_breaches": self.resolved_breaches,
            "recommendations": self.recommendations,
            "risk_by_category": self.risk_by_category,
            "risk_by_exchange": self.risk_by_exchange,
            "risk_by_strategy": self.risk_by_strategy,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_value_at_risk(
    returns: List[float],
    confidence_level: float = 0.95,
    horizon: int = 1
) -> float:
    """
    Calculate Value at Risk (VaR).
    
    Args:
        returns: List of returns
        confidence_level: Confidence level (0-1)
        horizon: Time horizon in days
        
    Returns:
        VaR value
    """
    if not returns:
        return 0.0
        
    # Sort returns
    sorted_returns = sorted(returns)
    
    # Calculate percentile
    index = int((1 - confidence_level) * len(sorted_returns))
    var = abs(sorted_returns[index]) * math.sqrt(horizon)
    
    return var


def calculate_conditional_var(
    returns: List[float],
    confidence_level: float = 0.95
) -> float:
    """
    Calculate Conditional VaR (Expected Shortfall).
    
    Args:
        returns: List of returns
        confidence_level: Confidence level (0-1)
        
    Returns:
        CVaR value
    """
    if not returns:
        return 0.0
        
    # Sort returns
    sorted_returns = sorted(returns)
    
    # Calculate VaR
    var_index = int((1 - confidence_level) * len(sorted_returns))
    var = abs(sorted_returns[var_index])
    
    # Calculate average of returns worse than VaR
    worse_returns = [r for r in sorted_returns[:var_index] if r < 0]
    if worse_returns:
        cvar = abs(sum(worse_returns) / len(worse_returns))
    else:
        cvar = var
        
    return cvar


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if not returns:
        return 0.0
        
    avg_return = sum(returns) / len(returns)
    if len(returns) > 1:
        std_dev = statistics.stdev(returns)
    else:
        std_dev = 0
        
    if std_dev == 0:
        return 0.0
        
    return (avg_return - risk_free_rate) / std_dev


def calculate_max_drawdown(
    values: List[float]
) -> Dict[str, float]:
    """
    Calculate maximum drawdown.
    
    Args:
        values: List of values
        
    Returns:
        Dict with max drawdown and duration
    """
    if not values:
        return {"max_drawdown": 0.0, "max_drawdown_duration": 0}
        
    peak = values[0]
    max_drawdown = 0.0
    max_drawdown_start = 0
    max_drawdown_end = 0
    current_start = 0
    
    for i, value in enumerate(values):
        if value > peak:
            peak = value
            current_start = i
        else:
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_start = current_start
                max_drawdown_end = i
                
    duration = max_drawdown_end - max_drawdown_start
    
    return {
        "max_drawdown": max_drawdown,
        "max_drawdown_duration": duration
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'RiskType',
    'RiskLevel',
    'RiskCategory',
    'RiskMetric',
    'RiskAction',
    
    # Core Models
    'RiskMetricValue',
    'RiskAssessment',
    'PositionRisk',
    'RiskLimit',
    'RiskReport',
    
    # Helper Functions
    'calculate_value_at_risk',
    'calculate_conditional_var',
    'calculate_sharpe_ratio',
    'calculate_max_drawdown',
]
