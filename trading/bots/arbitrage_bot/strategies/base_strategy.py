# trading/bots/arbitrage_bot/strategies/base_strategy.py
# NEXUS AI TRADING SYSTEM - BASE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the base strategy class and common interfaces for all
# arbitrage strategies in the NEXUS trading system.
# ====================================================================================

"""
NEXUS Arbitrage Base Strategy

This module provides the foundation for all arbitrage strategies with:
- Abstract base class defining the strategy interface
- Common utility methods for all strategies
- Risk management integration
- Performance tracking
- Configuration management
- Event handling
"""

import asyncio
import logging
import time
import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# NEXUS internal imports
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity, OpportunityType, OpportunityStatus
from trading.bots.arbitrage_bot.models.trade import Trade, TradeSide, TradeStatus, TradeType
from trading.bots.arbitrage_bot.models.order import Order, OrderType, OrderSide, OrderStatus
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.models.portfolio import Portfolio
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.rate_limiter import RateLimiter

logger = logging.getLogger("nexus.arbitrage.base_strategy")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class StrategyType(str, Enum):
    """Types of arbitrage strategies."""
    CEX_CEX = "cex_cex"
    DEX_DEX = "dex_dex"
    CEX_DEX = "cex_dex"
    TRIANGULAR = "triangular"
    CROSS_CHAIN = "cross_chain"
    FUNDING_RATE = "funding_rate"
    STATISTICAL = "statistical"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    HYBRID = "hybrid"


class StrategyStatus(str, Enum):
    """Status of a strategy."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    BACKTESTING = "backtesting"


class StrategyRiskLevel(str, Enum):
    """Risk levels for strategies."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class StrategyConfig:
    """Configuration for a strategy."""
    name: str
    type: StrategyType
    enabled: bool = True
    risk_level: StrategyRiskLevel = StrategyRiskLevel.MEDIUM
    max_position_size: float = 10000.0
    max_risk_per_trade: float = 0.02  # 2%
    min_profit_threshold: float = 0.002  # 0.2%
    max_slippage: float = 0.001  # 0.1%
    execution_timeout: float = 5.0
    retry_count: int = 3
    min_confidence: float = 0.5
    max_drawdown: float = 0.10  # 10%
    stop_loss: float = 0.02  # 2%
    take_profit: float = 0.05  # 5%
    trailing_stop: float = 0.01  # 1%


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy."""
    total_opportunities: int = 0
    executed_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_profit: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    total_trades: int = 0
    avg_execution_time: float = 0.0
    success_rate: float = 0.0
    last_update: Optional[datetime] = None


@dataclass
class StrategyResult:
    """Result of a strategy operation."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    trade: Optional[Trade] = None
    error: Optional[str] = None


# ====================================================================================
# BASE STRATEGY CLASS
# ====================================================================================

class BaseStrategy(ABC):
    """
    Abstract base class for all arbitrage strategies.
    
    All strategies must implement:
    - analyze_opportunity: Evaluate an opportunity
    - execute_trade: Execute a trade
    - validate_opportunity: Validate an opportunity
    - get_metrics: Get strategy metrics
    - reset: Reset strategy state
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        portfolio: Optional[Portfolio] = None
    ):
        """
        Initialize the base strategy.
        
        Args:
            config: Strategy configuration
            portfolio: Portfolio instance (optional)
        """
        self.config = config
        self.portfolio = portfolio
        
        # Strategy identification
        self.name = config.name
        self.type = config.type
        self.strategy_id = f"{config.type.value}_{config.name}_{int(time.time())}"
        
        # State
        self.status = StrategyStatus.INITIALIZING
        self._start_time: Optional[datetime] = None
        self._last_run: Optional[datetime] = None
        self._running = False
        
        # Metrics
        self.metrics = StrategyMetrics()
        self._metrics_collector = MetricsCollector(
            name=f"strategy_{self.name}",
            labels={"strategy": self.name, "type": self.type.value}
        )
        self._setup_metrics()
        
        # Storage
        self._opportunities: List[ArbitrageOpportunity] = []
        self._trades: List[Trade] = []
        self._orders: List[Order] = []
        self._history: deque = deque(maxlen=10000)
        
        # Performance windows
        self._profit_window: deque = deque(maxlen=100)
        self._trade_window: deque = deque(maxlen=100)
        self._opportunity_window: deque = deque(maxlen=100)
        
        # Locks
        self._state_lock = asyncio.Lock()
        self._execution_lock = asyncio.Lock()
        
        # Rate limiting
        self._rate_limiter = RateLimiter(
            max_requests=self.config.max_position_size / 1000,
            time_window=1.0
        )
        
        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Risk management
        self._risk_assessment: Optional[RiskAssessment] = None
        
        logger.info(f"BaseStrategy '{self.name}' initialized (type={self.type.value})")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics_collector.register_gauge("status", "Strategy status")
        self._metrics_collector.register_gauge("win_rate", "Win rate")
        self._metrics_collector.register_gauge("profit", "Total profit")
        self._metrics_collector.register_gauge("drawdown", "Current drawdown")
        self._metrics_collector.register_counter("opportunities", "Opportunities detected")
        self._metrics_collector.register_counter("trades", "Trades executed")
        self._metrics_collector.register_histogram("execution_time", "Execution time in ms")
        self._metrics_collector.register_histogram("profit_percentage", "Profit percentage")
        
    # ====================================================================
    # ABSTRACT METHODS
    # ====================================================================
    
    @abstractmethod
    async def analyze_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Analyze an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to analyze
            
        Returns:
            Analysis result with score and recommendation
        """
        pass
    
    @abstractmethod
    async def execute_trade(
        self,
        opportunity: ArbitrageOpportunity,
        **kwargs
    ) -> StrategyResult:
        """
        Execute a trade based on an opportunity.
        
        Args:
            opportunity: Opportunity to execute
            **kwargs: Additional execution parameters
            
        Returns:
            Strategy result with trade details
        """
        pass
    
    @abstractmethod
    async def validate_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> bool:
        """
        Validate an opportunity before execution.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        pass
    
    @abstractmethod
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy metrics.
        
        Returns:
            Metrics dictionary
        """
        pass
    
    @abstractmethod
    async def reset(self) -> None:
        """Reset strategy state."""
        pass
    
    # ====================================================================
    # COMMON METHODS
    # ====================================================================
    
    async def initialize(self) -> bool:
        """
        Initialize the strategy.
        
        Returns:
            True if initialization successful
        """
        try:
            self.status = StrategyStatus.INITIALIZING
            self._start_time = datetime.utcnow()
            
            # Initialize portfolio if needed
            if self.portfolio:
                await self._initialize_portfolio()
                
            # Load historical data
            await self._load_historical_data()
            
            self.status = StrategyStatus.RUNNING
            self._running = True
            
            logger.info(f"Strategy '{self.name}' initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Strategy '{self.name}' initialization failed: {e}")
            self.status = StrategyStatus.ERROR
            return False
            
    async def _initialize_portfolio(self) -> None:
        """Initialize portfolio."""
        if self.portfolio:
            # Ensure portfolio is loaded
            pass
            
    async def _load_historical_data(self) -> None:
        """Load historical data for the strategy."""
        # Override in subclasses if needed
        pass
        
    async def start(self) -> None:
        """Start the strategy."""
        if self.status == StrategyStatus.RUNNING:
            logger.warning(f"Strategy '{self.name}' already running")
            return
            
        if self.status == StrategyStatus.ERROR:
            await self.initialize()
            
        self.status = StrategyStatus.RUNNING
        self._running = True
        self._start_time = datetime.utcnow()
        
        self._emit_event("strategy_started", {"strategy": self.name})
        logger.info(f"Strategy '{self.name}' started")
        
    async def stop(self) -> None:
        """Stop the strategy."""
        self.status = StrategyStatus.STOPPED
        self._running = False
        
        self._emit_event("strategy_stopped", {"strategy": self.name})
        logger.info(f"Strategy '{self.name}' stopped")
        
    async def pause(self) -> None:
        """Pause the strategy."""
        self.status = StrategyStatus.PAUSED
        self._running = False
        
        self._emit_event("strategy_paused", {"strategy": self.name})
        logger.info(f"Strategy '{self.name}' paused")
        
    async def resume(self) -> None:
        """Resume the strategy."""
        self.status = StrategyStatus.RUNNING
        self._running = True
        
        self._emit_event("strategy_resumed", {"strategy": self.name})
        logger.info(f"Strategy '{self.name}' resumed")
        
    # ====================================================================
    # OPPORTUNITY HANDLING
    # ====================================================================
    
    async def process_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> StrategyResult:
        """
        Process an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to process
            
        Returns:
            Strategy result
        """
        if not self._running:
            return StrategyResult(
                success=False,
                message="Strategy not running",
                error="Strategy stopped"
            )
            
        try:
            # Track opportunity
            self._opportunities.append(opportunity)
            self._opportunity_window.append(opportunity)
            self._metrics_collector.increment_counter("opportunities")
            
            # Validate
            if not await self.validate_opportunity(opportunity):
                return StrategyResult(
                    success=False,
                    message="Opportunity validation failed",
                    error="Validation failed"
                )
                
            # Analyze
            analysis = await self.analyze_opportunity(opportunity)
            
            if analysis.get("action") == "skip":
                return StrategyResult(
                    success=False,
                    message=f"Skipped: {analysis.get('reason', 'No reason provided')}",
                    data=analysis
                )
                
            # Execute if recommended
            if analysis.get("action") in ["execute", "trade"]:
                result = await self.execute_trade(opportunity, **analysis)
                return result
                
            return StrategyResult(
                success=True,
                message="Opportunity processed",
                data=analysis
            )
            
        except Exception as e:
            logger.error(f"Opportunity processing error: {e}")
            return StrategyResult(
                success=False,
                message="Processing failed",
                error=str(e)
            )
            
    # ====================================================================
    # TRADE MANAGEMENT
    # ====================================================================
    
    async def on_trade_completed(self, trade: Trade) -> None:
        """
        Handle trade completion.
        
        Args:
            trade: Completed trade
        """
        self._trades.append(trade)
        self._trade_window.append(trade)
        self._metrics_collector.increment_counter("trades")
        
        # Update metrics
        self._update_trade_metrics(trade)
        
        # Emit event
        self._emit_event("trade_completed", {"trade": trade})
        
    def _update_trade_metrics(self, trade: Trade) -> None:
        """
        Update metrics based on trade result.
        
        Args:
            trade: Completed trade
        """
        self.metrics.total_trades += 1
        
        if trade.status == TradeStatus.EXECUTED:
            self.metrics.executed_trades += 1
            if trade.net_profit > 0:
                self.metrics.successful_trades += 1
                self.metrics.total_profit += trade.net_profit
            else:
                self.metrics.total_loss += abs(trade.net_profit)
            self.metrics.net_profit = self.metrics.total_profit - self.metrics.total_loss
            
        elif trade.status == TradeStatus.FAILED:
            self.metrics.failed_trades += 1
            
        # Calculate derived metrics
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = (
                self.metrics.successful_trades / self.metrics.total_trades * 100
            )
            
        if self.metrics.successful_trades > 0:
            self.metrics.avg_profit = self.metrics.total_profit / self.metrics.successful_trades
            
        if self.metrics.failed_trades > 0:
            self.metrics.avg_loss = self.metrics.total_loss / self.metrics.failed_trades
            
        if self.metrics.total_loss > 0:
            self.metrics.profit_factor = self.metrics.total_profit / self.metrics.total_loss
            
        # Update drawdown
        self._update_drawdown()
        
        # Update metrics collector
        self._metrics_collector.set_gauge("win_rate", self.metrics.win_rate)
        self._metrics_collector.set_gauge("profit", self.metrics.net_profit)
        self._metrics_collector.set_gauge("drawdown", self.metrics.current_drawdown)
        
        if trade.net_profit != 0:
            self._metrics_collector.record_histogram(
                "profit_percentage",
                trade.profit_percentage
            )
            
    def _update_drawdown(self) -> None:
        """Update drawdown metrics."""
        profits = [t.net_profit for t in self._trades if t.status == TradeStatus.EXECUTED]
        
        if not profits:
            return
            
        # Calculate running total
        running_total = 0
        peak = 0
        max_drawdown = 0
        current_drawdown = 0
        
        for profit in profits:
            running_total += profit
            if running_total > peak:
                peak = running_total
            drawdown = peak - running_total
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            current_drawdown = drawdown
            
        self.metrics.max_drawdown = max_drawdown
        self.metrics.current_drawdown = current_drawdown
        
    # ====================================================================
    # RISK MANAGEMENT
    # ====================================================================
    
    async def assess_risk(
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
        # Base risk assessment
        risk_factors = {
            "market_risk": 0.3,
            "liquidity_risk": 0.3,
            "execution_risk": 0.2,
            "counterparty_risk": 0.2
        }
        
        # Adjust based on opportunity type
        if opportunity.type in [OpportunityType.CROSS_CHAIN, OpportunityType.DEX_CEX]:
            risk_factors["execution_risk"] = 0.4
            risk_factors["counterparty_risk"] = 0.3
            
        if opportunity.type == OpportunityType.TRIANGULAR:
            risk_factors["execution_risk"] = 0.4
            risk_factors["market_risk"] = 0.4
            
        # Adjust based on confidence
        confidence_factor = 1 - opportunity.confidence_score
        risk_factors["market_risk"] += confidence_factor * 0.3
        
        # Calculate overall risk
        overall_risk = sum(risk_factors.values()) / len(risk_factors)
        
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
            market_risk_score=risk_factors["market_risk"] * 100,
            liquidity_risk_score=risk_factors["liquidity_risk"] * 100,
            counterparty_risk_score=risk_factors["counterparty_risk"] * 100
        )
        
    def calculate_position_size(
        self,
        opportunity: ArbitrageOpportunity,
        risk_assessment: RiskAssessment
    ) -> float:
        """
        Calculate position size based on risk.
        
        Args:
            opportunity: Opportunity to size
            risk_assessment: Risk assessment
            
        Returns:
            Position size
        """
        # Base size
        base_size = self.config.max_position_size
        
        # Adjust for risk level
        risk_multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.HIGH: 0.4,
            RiskLevel.VERY_HIGH: 0.2
        }
        risk_multiplier = risk_multipliers.get(
            risk_assessment.overall_risk_level,
            0.5
        )
        
        # Adjust for confidence
        confidence_multiplier = opportunity.confidence_score
        
        # Adjust for profit potential
        profit_multiplier = min(1.0, opportunity.profit_percentage / 0.01)
        
        # Calculate size
        size = base_size * risk_multiplier * confidence_multiplier * profit_multiplier
        
        # Apply min/max
        min_size = self.config.max_position_size * 0.01
        max_size = self.config.max_position_size
        
        return max(min_size, min(size, max_size))
        
    # ====================================================================
    # EVENT HANDLING
    # ====================================================================
    
    def on_event(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event: Event name
            handler: Event handler function
        """
        self._event_handlers[event].append(handler)
        
    def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """
        Emit an event to registered handlers.
        
        Args:
            event: Event name
            data: Event data
        """
        for handler in self._event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Event handler error for {event}: {e}")
                
    # ====================================================================
    # UTILITY METHODS
    # ====================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get strategy status.
        
        Returns:
            Status dictionary
        """
        return {
            "name": self.name,
            "type": self.type.value,
            "status": self.status.value,
            "running": self._running,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "metrics": {
                "total_opportunities": self.metrics.total_opportunities,
                "total_trades": self.metrics.total_trades,
                "win_rate": self.metrics.win_rate,
                "net_profit": self.metrics.net_profit,
                "current_drawdown": self.metrics.current_drawdown,
                "max_drawdown": self.metrics.max_drawdown
            }
        }
        
    def get_metrics(self) -> StrategyMetrics:
        """
        Get strategy metrics.
        
        Returns:
            Strategy metrics
        """
        self.metrics.last_update = datetime.utcnow()
        return self.metrics
        
    def get_performance(self) -> Dict[str, Any]:
        """
        Get performance summary.
        
        Returns:
            Performance summary
        """
        return {
            "total_profit": self.metrics.total_profit,
            "total_loss": self.metrics.total_loss,
            "net_profit": self.metrics.net_profit,
            "win_rate": self.metrics.win_rate,
            "profit_factor": self.metrics.profit_factor,
            "sharpe_ratio": self.metrics.sharpe_ratio,
            "max_drawdown": self.metrics.max_drawdown,
            "current_drawdown": self.metrics.current_drawdown,
            "avg_profit": self.metrics.avg_profit,
            "avg_loss": self.metrics.avg_loss,
            "total_trades": self.metrics.total_trades,
            "successful_trades": self.metrics.successful_trades,
            "failed_trades": self.metrics.failed_trades
        }
        
    async def save_state(self) -> None:
        """Save strategy state."""
        # Override in subclasses if needed
        pass
        
    async def load_state(self) -> None:
        """Load strategy state."""
        # Override in subclasses if needed
        pass
        
    def __repr__(self) -> str:
        return f"BaseStrategy(name={self.name}, type={self.type.value}, status={self.status.value})"
        
    # ====================================================================
    # CLEANUP
    # ====================================================================
    
    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        await self.stop()
        
        # Close metrics collector
        try:
            await self._metrics_collector.close()
        except Exception:
            pass
            
        logger.info(f"Strategy '{self.name}' cleaned up")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'StrategyType',
    'StrategyStatus',
    'StrategyRiskLevel',
    'StrategyConfig',
    'StrategyMetrics',
    'StrategyResult',
    'BaseStrategy',
]
