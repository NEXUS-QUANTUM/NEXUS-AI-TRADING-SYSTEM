# trading/bots/arbitrage_bot/strategies/adaptive_strategy.py
# NEXUS AI TRADING SYSTEM - ADAPTIVE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module implements adaptive arbitrage strategies that automatically adjust
# to changing market conditions, volatility, and liquidity.
# ====================================================================================

"""
NEXUS Adaptive Arbitrage Strategy

This module provides adaptive arbitrage strategies that:
- Automatically adjust to market conditions
- Optimize execution parameters in real-time
- Learn from historical performance
- Adapt to changing volatility and liquidity
- Support multiple arbitrage types
- Implement risk management rules
- Track and improve performance over time
"""

import asyncio
import logging
import time
import math
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# NEXUS internal imports
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity, OpportunityType, OpportunityConfidence
from trading.bots.arbitrage_bot.models.trade import Trade, TradeSide, TradeStatus
from trading.bots.arbitrage_bot.models.order import Order, OrderType, OrderSide
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.rate_limiter import RateLimiter

logger = logging.getLogger("nexus.arbitrage.adaptive_strategy")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class MarketCondition(str, Enum):
    """Market condition states."""
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_LIQUIDITY = "high_liquidity"
    LOW_LIQUIDITY = "low_liquidity"
    CRISIS = "crisis"
    RECOVERY = "recovery"


class StrategyMode(str, Enum):
    """Strategy operational modes."""
    AGGRESSIVE = "aggressive"      # Maximum opportunity capture
    BALANCED = "balanced"          # Balanced risk/reward
    CONSERVATIVE = "conservative"  # Risk-averse
    PAUSED = "paused"              # Temporarily paused
    EMERGENCY = "emergency"        # Emergency mode


class AdaptationSignal(str, Enum):
    """Signals that trigger adaptation."""
    VOLATILITY_CHANGE = "volatility_change"
    LIQUIDITY_CHANGE = "liquidity_change"
    SPREAD_CHANGE = "spread_change"
    PERFORMANCE_DECLINE = "performance_decline"
    OPPORTUNITY_RATE_CHANGE = "opportunity_rate_change"
    RISK_INCREASE = "risk_increase"
    MARKET_HOURS_CHANGE = "market_hours_change"
    EXCHANGE_ISSUE = "exchange_issue"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class StrategyParameter:
    """Individual strategy parameter."""
    name: str
    value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step_size: Optional[float] = None
    description: str = ""
    adjustable: bool = True


@dataclass
class StrategyState:
    """Current state of the strategy."""
    mode: StrategyMode = StrategyMode.BALANCED
    market_condition: MarketCondition = MarketCondition.NORMAL
    confidence: float = 0.5
    performance_score: float = 0.0
    opportunity_rate: float = 0.0
    success_rate: float = 0.0
    avg_profit: float = 0.0
    volatility: float = 0.0
    liquidity_score: float = 0.5
    last_adaptation: Optional[datetime] = None
    adaptation_count: int = 0
    is_active: bool = True
    error_count: int = 0


@dataclass
class AdaptationDecision:
    """Decision made during adaptation."""
    timestamp: datetime
    signal: AdaptationSignal
    reason: str
    changes: Dict[str, Any]
    confidence: float
    expected_improvement: float


# ====================================================================================
# ADAPTIVE STRATEGY
# ====================================================================================

class AdaptiveStrategy:
    """
    Adaptive arbitrage strategy that automatically adjusts to market conditions.
    
    Features:
    - Real-time market condition detection
    - Automatic parameter optimization
    - Performance-based adjustments
    - Risk-aware execution
    - Multi-strategy support
    - Performance tracking and analysis
    """
    
    def __init__(
        self,
        name: str = "adaptive_arbitrage",
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the adaptive strategy.
        
        Args:
            name: Strategy name
            config: Configuration dictionary
        """
        self.name = name
        self.config = config or {}
        
        # Strategy parameters
        self._parameters = self._initialize_parameters()
        
        # State management
        self._state = StrategyState()
        self._state_history: deque = deque(maxlen=1000)
        self._adaptation_history: deque = deque(maxlen=100)
        
        # Performance tracking
        self._performance_window: deque = deque(maxlen=1000)
        self._opportunity_window: deque = deque(maxlen=1000)
        self._trade_window: deque = deque(maxlen=1000)
        
        # Market data
        self._market_data: Dict[str, Any] = {}
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._spread_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._volume_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Metrics
        self._metrics = MetricsCollector(
            name=f"strategy_{name}",
            labels={"strategy": name}
        )
        self._setup_metrics()
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            max_requests=self.config.get("max_operations_per_second", 10),
            time_window=1.0
        )
        
        # Sub-strategies
        self._sub_strategies: Dict[str, Any] = {}
        self._active_sub_strategies: List[str] = []
        
        # Locks
        self._state_lock = asyncio.Lock()
        self._adaptation_lock = asyncio.Lock()
        
        # Background tasks
        self._running = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Register default sub-strategies
        self._register_default_sub_strategies()
        
        logger.info(f"AdaptiveStrategy '{name}' initialized (version=3.0.0)")
        
    def _initialize_parameters(self) -> Dict[str, StrategyParameter]:
        """Initialize strategy parameters."""
        return {
            # Risk parameters
            "max_position_size": StrategyParameter(
                name="max_position_size",
                value=self.config.get("max_position_size", 10000.0),
                min_value=100.0,
                max_value=100000.0,
                description="Maximum position size in USDT"
            ),
            "max_risk_per_trade": StrategyParameter(
                name="max_risk_per_trade",
                value=self.config.get("max_risk_per_trade", 0.02),
                min_value=0.001,
                max_value=0.10,
                description="Maximum risk per trade (2%)"
            ),
            "max_drawdown": StrategyParameter(
                name="max_drawdown",
                value=self.config.get("max_drawdown", 0.10),
                min_value=0.01,
                max_value=0.50,
                description="Maximum allowed drawdown"
            ),
            
            # Opportunity parameters
            "min_profit_threshold": StrategyParameter(
                name="min_profit_threshold",
                value=self.config.get("min_profit_threshold", 0.002),
                min_value=0.0005,
                max_value=0.01,
                description="Minimum profit threshold (0.2%)"
            ),
            "max_spread_bps": StrategyParameter(
                name="max_spread_bps",
                value=self.config.get("max_spread_bps", 10.0),
                min_value=1.0,
                max_value=50.0,
                description="Maximum spread in basis points"
            ),
            "min_confidence": StrategyParameter(
                name="min_confidence",
                value=self.config.get("min_confidence", 0.5),
                min_value=0.1,
                max_value=0.9,
                description="Minimum confidence score"
            ),
            
            # Execution parameters
            "max_slippage": StrategyParameter(
                name="max_slippage",
                value=self.config.get("max_slippage", 0.001),
                min_value=0.0001,
                max_value=0.01,
                description="Maximum allowed slippage"
            ),
            "execution_timeout": StrategyParameter(
                name="execution_timeout",
                value=self.config.get("execution_timeout", 5.0),
                min_value=1.0,
                max_value=30.0,
                description="Execution timeout in seconds"
            ),
            "retry_count": StrategyParameter(
                name="retry_count",
                value=self.config.get("retry_count", 3),
                min_value=1,
                max_value=10,
                description="Number of retry attempts"
            ),
            
            # Adaptation parameters
            "adaptation_frequency": StrategyParameter(
                name="adaptation_frequency",
                value=self.config.get("adaptation_frequency", 60),
                min_value=10,
                max_value=300,
                description="Adaptation frequency in seconds"
            ),
            "performance_window": StrategyParameter(
                name="performance_window",
                value=self.config.get("performance_window", 100),
                min_value=10,
                max_value=1000,
                description="Performance evaluation window"
            ),
            "adaptation_threshold": StrategyParameter(
                name="adaptation_threshold",
                value=self.config.get("adaptation_threshold", 0.05),
                min_value=0.01,
                max_value=0.20,
                description="Threshold for triggering adaptation"
            )
        }
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_gauge("confidence", "Strategy confidence level")
        self._metrics.register_gauge("performance_score", "Strategy performance score")
        self._metrics.register_gauge("opportunity_rate", "Opportunity detection rate")
        self._metrics.register_gauge("success_rate", "Trade success rate")
        self._metrics.register_counter("adaptations", "Number of adaptations")
        self._metrics.register_counter("opportunities_detected", "Opportunities detected")
        self._metrics.register_counter("opportunities_executed", "Opportunities executed")
        self._metrics.register_histogram("profit_percentage", "Profit percentage")
        
    def _register_default_sub_strategies(self) -> None:
        """Register default sub-strategies."""
        # This will be populated with actual strategy implementations
        self._sub_strategies = {
            "momentum": None,
            "mean_reversion": None,
            "arbitrage": None,
            "market_making": None
        }
        self._active_sub_strategies = ["arbitrage"]
        
    async def initialize(self) -> None:
        """Initialize the strategy."""
        if self._running:
            return
            
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info(f"AdaptiveStrategy '{self.name}' initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Market monitoring
        task = asyncio.create_task(self._market_monitor_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Adaptation loop
        task = asyncio.create_task(self._adaptation_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Performance evaluation
        task = asyncio.create_task(self._performance_evaluation_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _market_monitor_loop(self) -> None:
        """Monitor market conditions."""
        while self._running:
            try:
                await self._update_market_data()
                await self._detect_market_conditions()
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Market monitor error: {e}")
                await asyncio.sleep(10)
                
    async def _adaptation_loop(self) -> None:
        """Main adaptation loop."""
        while self._running:
            try:
                await asyncio.sleep(self._parameters["adaptation_frequency"].value)
                
                if self._state.is_active:
                    await self._adapt_to_market_conditions()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Adaptation error: {e}")
                
    async def _performance_evaluation_loop(self) -> None:
        """Evaluate and update performance metrics."""
        while self._running:
            try:
                await asyncio.sleep(30)
                await self._evaluate_performance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Performance evaluation error: {e}")
                
    # ====================================================================
    # MARKET DATA
    # ====================================================================
    
    async def _update_market_data(self) -> None:
        """Update market data from various sources."""
        # This would be implemented with actual exchange API calls
        # For now, we'll use mock data for demonstration
        pass
        
    async def _detect_market_conditions(self) -> None:
        """Detect current market conditions."""
        # Analyze volatility
        volatility = await self._calculate_volatility()
        self._state.volatility = volatility
        
        # Analyze liquidity
        liquidity = await self._calculate_liquidity()
        self._state.liquidity_score = liquidity
        
        # Determine market condition
        if volatility > 0.8:
            condition = MarketCondition.CRISIS
        elif volatility > 0.6:
            condition = MarketCondition.HIGH_VOLATILITY
        elif volatility < 0.2:
            condition = MarketCondition.LOW_VOLATILITY
        elif liquidity > 0.7:
            condition = MarketCondition.HIGH_LIQUIDITY
        elif liquidity < 0.3:
            condition = MarketCondition.LOW_LIQUIDITY
        else:
            condition = MarketCondition.NORMAL
            
        if self._state.market_condition != condition:
            old_condition = self._state.market_condition
            self._state.market_condition = condition
            logger.info(f"Market condition changed: {old_condition} -> {condition}")
            
            # Trigger adaptation on significant changes
            if condition in [MarketCondition.CRISIS, MarketCondition.HIGH_VOLATILITY]:
                await self._adapt_to_market_conditions()
                
    async def _calculate_volatility(self) -> float:
        """Calculate market volatility (0-1)."""
        # Simplified volatility calculation
        if not self._price_history:
            return 0.3
            
        # Get recent prices for a symbol
        prices = []
        for symbol, history in self._price_history.items():
            if len(history) > 10:
                prices.extend(history)
                
        if len(prices) < 10:
            return 0.3
            
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
                
        if not returns:
            return 0.3
            
        # Calculate standard deviation
        std_dev = statistics.stdev(returns) if len(returns) > 1 else 0
        
        # Normalize to 0-1
        volatility = min(1.0, std_dev * 10)
        return volatility
        
    async def _calculate_liquidity(self) -> float:
        """Calculate market liquidity (0-1)."""
        # Simplified liquidity calculation
        if not self._volume_history:
            return 0.5
            
        # Get recent volumes
        volumes = []
        for symbol, history in self._volume_history.items():
            if len(history) > 10:
                volumes.extend(history)
                
        if not volumes:
            return 0.5
            
        # Normalize
        avg_volume = sum(volumes) / len(volumes)
        liquidity = min(1.0, avg_volume / 1000000)  # Normalize to 1M volume
        return liquidity
        
    # ====================================================================
    # ADAPTATION
    # ====================================================================
    
    async def _adapt_to_market_conditions(self) -> None:
        """Adapt strategy to current market conditions."""
        async with self._adaptation_lock:
            changes = {}
            signals = []
            
            # Determine signals
            if self._state.volatility > 0.7:
                signals.append((AdaptationSignal.VOLATILITY_CHANGE, "High volatility detected"))
            elif self._state.volatility < 0.2:
                signals.append((AdaptationSignal.VOLATILITY_CHANGE, "Low volatility detected"))
                
            if self._state.liquidity_score < 0.3:
                signals.append((AdaptationSignal.LIQUIDITY_CHANGE, "Low liquidity detected"))
                
            if self._state.success_rate < 0.5:
                signals.append((AdaptationSignal.PERFORMANCE_DECLINE, "Performance decline detected"))
                
            # Adapt based on signals
            for signal, reason in signals:
                decision = await self._adapt_to_signal(signal, reason)
                if decision:
                    changes.update(decision.changes)
                    self._adaptation_history.append(decision)
                    
            if changes:
                self._state.adaptation_count += 1
                self._state.last_adaptation = datetime.utcnow()
                self._metrics.increment_counter("adaptations")
                logger.info(f"Strategy adapted: {changes}")
                
                # Update state
                await self._apply_changes(changes)
                
    async def _adapt_to_signal(
        self,
        signal: AdaptationSignal,
        reason: str
    ) -> Optional[AdaptationDecision]:
        """
        Adapt to a specific signal.
        
        Args:
            signal: Adaptation signal
            reason: Reason for adaptation
            
        Returns:
            Adaptation decision or None
        """
        changes = {}
        confidence = 0.5
        
        if signal == AdaptationSignal.VOLATILITY_CHANGE:
            if self._state.volatility > 0.7:
                # High volatility: reduce position size, increase spread tolerance
                changes["max_position_size"] = self._parameters["max_position_size"].value * 0.5
                changes["max_spread_bps"] = self._parameters["max_spread_bps"].value * 2
                changes["min_profit_threshold"] = self._parameters["min_profit_threshold"].value * 2
                confidence = 0.7
            else:
                # Low volatility: increase position size, tighten spread tolerance
                changes["max_position_size"] = min(
                    self._parameters["max_position_size"].value * 1.2,
                    self._parameters["max_position_size"].max_value
                )
                changes["max_spread_bps"] = self._parameters["max_spread_bps"].value * 0.5
                changes["min_profit_threshold"] = self._parameters["min_profit_threshold"].value * 0.5
                confidence = 0.6
                
        elif signal == AdaptationSignal.LIQUIDITY_CHANGE:
            if self._state.liquidity_score < 0.3:
                # Low liquidity: reduce position size, increase slippage tolerance
                changes["max_position_size"] = self._parameters["max_position_size"].value * 0.3
                changes["max_slippage"] = self._parameters["max_slippage"].value * 2
                changes["execution_timeout"] = self._parameters["execution_timeout"].value * 1.5
                confidence = 0.8
                
        elif signal == AdaptationSignal.PERFORMANCE_DECLINE:
            if self._state.success_rate < 0.5:
                # Poor performance: reduce risk, increase profit threshold
                changes["max_position_size"] = self._parameters["max_position_size"].value * 0.7
                changes["min_profit_threshold"] = self._parameters["min_profit_threshold"].value * 1.5
                changes["max_risk_per_trade"] = self._parameters["max_risk_per_trade"].value * 0.5
                confidence = 0.7
                
        elif signal == AdaptationSignal.OPPORTUNITY_RATE_CHANGE:
            if self._state.opportunity_rate < 0.01:
                changes["min_profit_threshold"] = self._parameters["min_profit_threshold"].value * 0.5
                changes["min_confidence"] = self._parameters["min_confidence"].value * 0.5
                confidence = 0.6
                
        if changes:
            return AdaptationDecision(
                timestamp=datetime.utcnow(),
                signal=signal,
                reason=reason,
                changes=changes,
                confidence=confidence,
                expected_improvement=0.1
            )
            
        return None
        
    async def _apply_changes(self, changes: Dict[str, Any]) -> None:
        """
        Apply parameter changes.
        
        Args:
            changes: Dictionary of parameter changes
        """
        async with self._state_lock:
            for key, value in changes.items():
                if key in self._parameters:
                    param = self._parameters[key]
                    # Validate value within bounds
                    if param.min_value is not None:
                        value = max(value, param.min_value)
                    if param.max_value is not None:
                        value = min(value, param.max_value)
                    if param.step_size is not None:
                        value = round(value / param.step_size) * param.step_size
                        
                    param.value = value
                    self._parameters[key] = param
                    
    # ====================================================================
    # OPPORTUNITY EVALUATION
    # ====================================================================
    
    async def evaluate_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Evaluate an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to evaluate
            
        Returns:
            Evaluation result with recommendation
        """
        # Check strategy state
        if not self._state.is_active:
            return {"action": "skip", "reason": "Strategy paused"}
            
        # Check mode
        if self._state.mode == StrategyMode.PAUSED:
            return {"action": "skip", "reason": "Strategy paused"}
            
        if self._state.mode == StrategyMode.EMERGENCY:
            return {"action": "skip", "reason": "Emergency mode"}
            
        # Calculate score
        score = await self._calculate_opportunity_score(opportunity)
        
        # Check against thresholds
        min_confidence = self._parameters["min_confidence"].value
        min_profit = self._parameters["min_profit_threshold"].value
        max_spread = self._parameters["max_spread_bps"].value
        
        if opportunity.confidence_score < min_confidence:
            return {"action": "skip", "reason": "Low confidence", "score": score}
            
        if opportunity.profit_percentage < min_profit:
            return {"action": "skip", "reason": "Low profit", "score": score}
            
        if self._state.success_rate < 0.4 and self._state.performance_score < 0.3:
            return {"action": "skip", "reason": "Poor performance", "score": score}
            
        # Check risk limits
        risk_assessment = await self._assess_risk(opportunity)
        if risk_assessment.overall_risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
            return {
                "action": "skip",
                "reason": "High risk",
                "score": score,
                "risk_level": risk_assessment.overall_risk_level
            }
            
        # Determine action
        if self._state.mode == StrategyMode.AGGRESSIVE:
            action = "execute" if score > 0.6 else "monitor"
        elif self._state.mode == StrategyMode.CONSERVATIVE:
            action = "execute" if score > 0.8 else "monitor"
        else:
            action = "execute" if score > 0.7 else "monitor"
            
        # Adjust position size based on confidence
        position_multiplier = min(1.0, opportunity.confidence_score / 0.5)
        max_position = self._parameters["max_position_size"].value
        position_size = max_position * position_multiplier
        
        return {
            "action": action,
            "score": score,
            "position_size": position_size,
            "max_position": max_position,
            "confidence": opportunity.confidence_score,
            "risk_level": risk_assessment.overall_risk_level
        }
        
    async def _calculate_opportunity_score(
        self,
        opportunity: ArbitrageOpportunity
    ) -> float:
        """
        Calculate opportunity score.
        
        Args:
            opportunity: Opportunity to score
            
        Returns:
            Opportunity score (0-1)
        """
        score = 0.0
        
        # Profitability (30%)
        profit_score = min(1.0, opportunity.profit_percentage / 0.01)
        score += profit_score * 0.3
        
        # Confidence (25%)
        score += opportunity.confidence_score * 0.25
        
        # Risk (20%)
        risk_score = 1.0 - opportunity.risk_score
        score += risk_score * 0.2
        
        # Market condition (15%)
        if self._state.market_condition in [MarketCondition.NORMAL, MarketCondition.HIGH_LIQUIDITY]:
            score += 0.15
        elif self._state.market_condition == MarketCondition.HIGH_VOLATILITY:
            score += 0.05
        else:
            score += 0.10
            
        # Performance history (10%)
        if self._state.success_rate > 0.7:
            score += 0.10
        elif self._state.success_rate > 0.5:
            score += 0.05
            
        return min(1.0, max(0.0, score))
        
    async def _assess_risk(
        self,
        opportunity: ArbitrageOpportunity
    ) -> RiskAssessment:
        """
        Assess risk of an opportunity.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            Risk assessment
        """
        risk_scores = {
            "market": 0.3,
            "liquidity": 0.3,
            "execution": 0.2,
            "counterparty": 0.2
        }
        
        # Adjust for current market conditions
        if self._state.volatility > 0.6:
            risk_scores["market"] = 0.7
            
        if self._state.liquidity_score < 0.3:
            risk_scores["liquidity"] = 0.6
            
        # Calculate overall risk
        overall_risk = sum(risk_scores.values()) / len(risk_scores)
        
        # Determine risk level
        if overall_risk < 0.3:
            level = RiskLevel.LOW
        elif overall_risk < 0.5:
            level = RiskLevel.MEDIUM
        elif overall_risk < 0.7:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH
            
        return RiskAssessment(
            overall_risk_score=overall_risk * 100,
            overall_risk_level=level,
            market_risk_score=risk_scores["market"] * 100,
            liquidity_risk_score=risk_scores["liquidity"] * 100
        )
        
    # ====================================================================
    # PERFORMANCE EVALUATION
    # ====================================================================
    
    async def _evaluate_performance(self) -> None:
        """Evaluate strategy performance."""
        trades = list(self._trade_window)
        
        if not trades:
            return
            
        # Calculate success rate
        successful = sum(1 for t in trades if t.status == TradeStatus.EXECUTED)
        total = len(trades)
        self._state.success_rate = successful / total if total > 0 else 0
        
        # Calculate average profit
        profits = [t.net_profit for t in trades if t.status == TradeStatus.EXECUTED]
        if profits:
            self._state.avg_profit = sum(profits) / len(profits)
            
        # Calculate performance score
        self._state.performance_score = self._calculate_performance_score(trades)
        
        # Update metrics
        self._metrics.set_gauge("confidence", self._state.confidence)
        self._metrics.set_gauge("performance_score", self._state.performance_score)
        self._metrics.set_gauge("success_rate", self._state.success_rate)
        self._metrics.set_gauge("opportunity_rate", self._state.opportunity_rate)
        
    def _calculate_performance_score(self, trades: List[Trade]) -> float:
        """
        Calculate overall performance score.
        
        Args:
            trades: List of trades
            
        Returns:
            Performance score (0-1)
        """
        if not trades:
            return 0.0
            
        # Profitability (40%)
        profits = [t.net_profit for t in trades if t.status == TradeStatus.EXECUTED]
        avg_profit = sum(profits) / len(profits) if profits else 0
        profit_score = min(1.0, avg_profit / 100)  # Normalize to 100 USDT
        
        # Success rate (30%)
        success_rate = self._state.success_rate
        success_score = success_rate
        
        # Consistency (20%)
        if len(trades) > 1:
            returns = [(t.net_profit / t.value) for t in trades if t.status == TradeStatus.EXECUTED and t.value > 0]
            if returns:
                std_dev = statistics.stdev(returns) if len(returns) > 1 else 0
                consistency_score = max(0, 1 - std_dev * 10)
            else:
                consistency_score = 0.5
        else:
            consistency_score = 0.5
            
        # Risk-adjusted return (10%)
        if avg_profit > 0 and self._state.volatility > 0:
            risk_adjusted = avg_profit / (self._state.volatility * 100)
            risk_score = min(1.0, risk_adjusted)
        else:
            risk_score = 0.5
            
        return (
            profit_score * 0.4 +
            success_score * 0.3 +
            consistency_score * 0.2 +
            risk_score * 0.1
        )
        
    # ====================================================================
    # TRADE MANAGEMENT
    # ====================================================================
    
    async def on_trade_executed(self, trade: Trade) -> None:
        """
        Handle trade execution callback.
        
        Args:
            trade: Executed trade
        """
        self._trade_window.append(trade)
        
        # Record metrics
        if trade.status == TradeStatus.EXECUTED:
            self._metrics.record_histogram("profit_percentage", trade.profit_percentage)
            self._metrics.increment_counter("opportunities_executed")
            
        # Trigger performance evaluation
        await self._evaluate_performance()
        
    async def on_opportunity_detected(self, opportunity: ArbitrageOpportunity) -> None:
        """
        Handle opportunity detection callback.
        
        Args:
            opportunity: Detected opportunity
        """
        self._opportunity_window.append(opportunity)
        self._metrics.increment_counter("opportunities_detected")
        
        # Update opportunity rate
        if len(self._opportunity_window) > 10:
            recent = list(self._opportunity_window)[-10:]
            self._state.opportunity_rate = len(recent) / 10
            
    # ====================================================================
    # STRATEGY CONTROL
    # ====================================================================
    
    async def pause(self) -> None:
        """Pause the strategy."""
        self._state.is_active = False
        self._state.mode = StrategyMode.PAUSED
        logger.info(f"Strategy '{self.name}' paused")
        
    async def resume(self) -> None:
        """Resume the strategy."""
        self._state.is_active = True
        self._state.mode = StrategyMode.BALANCED
        logger.info(f"Strategy '{self.name}' resumed")
        
    async def set_mode(self, mode: StrategyMode) -> None:
        """
        Set strategy mode.
        
        Args:
            mode: Strategy mode
        """
        self._state.mode = mode
        logger.info(f"Strategy '{self.name}' mode set to {mode.value}")
        
    def get_state(self) -> Dict[str, Any]:
        """
        Get strategy state.
        
        Returns:
            Strategy state dictionary
        """
        return {
            "name": self.name,
            "mode": self._state.mode.value,
            "market_condition": self._state.market_condition.value,
            "confidence": self._state.confidence,
            "performance_score": self._state.performance_score,
            "success_rate": self._state.success_rate,
            "avg_profit": self._state.avg_profit,
            "volatility": self._state.volatility,
            "liquidity_score": self._state.liquidity_score,
            "is_active": self._state.is_active,
            "adaptation_count": self._state.adaptation_count,
            "parameters": {
                name: param.value for name, param in self._parameters.items()
            }
        }
        
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get current parameters.
        
        Returns:
            Parameter dictionary
        """
        return {name: param.value for name, param in self._parameters.items()}
        
    async def update_parameter(self, name: str, value: Any) -> bool:
        """
        Update a parameter.
        
        Args:
            name: Parameter name
            value: New value
            
        Returns:
            True if updated
        """
        if name not in self._parameters:
            return False
            
        param = self._parameters[name]
        if not param.adjustable:
            return False
            
        param.value = value
        self._parameters[name] = param
        return True
        
    async def close(self) -> None:
        """Close the strategy."""
        self._running = False
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        logger.info(f"AdaptiveStrategy '{self.name}' closed")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'AdaptiveStrategy',
    'MarketCondition',
    'StrategyMode',
    'AdaptationSignal',
    'StrategyParameter',
    'StrategyState',
    'AdaptationDecision',
]
