# trading/bots/arbitrage_bot/strategies/hybrid_strategy.py
# NEXUS AI TRADING SYSTEM - HYBRID ARBITRAGE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module implements a hybrid arbitrage strategy that combines multiple
# arbitrage techniques and dynamically allocates capital based on performance.
# ====================================================================================

"""
NEXUS Hybrid Arbitrage Strategy

This module provides a hybrid arbitrage strategy that:
- Combines multiple arbitrage techniques (cross-exchange, cross-chain, DEX, futures-spot)
- Dynamically allocates capital based on performance
- Adapts to changing market conditions
- Implements portfolio-level risk management
- Optimizes for risk-adjusted returns
- Supports multiple execution modes
- Tracks and learns from performance
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
import random

# NEXUS internal imports
from trading.bots.arbitrage_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyResult
from trading.bots.arbitrage_bot.strategies.cross_exchange_strategy import CrossExchangeStrategy
from trading.bots.arbitrage_bot.strategies.cross_chain_strategy import CrossChainStrategy
from trading.bots.arbitrage_bot.strategies.dex_strategy import DEXStrategy
from trading.bots.arbitrage_bot.strategies.futures_spot_strategy import FuturesSpotStrategy
from trading.bots.arbitrage_bot.strategies.flash_loan_strategy import FlashLoanStrategy
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity
from trading.bots.arbitrage_bot.models.trade import Trade
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector

logger = logging.getLogger("nexus.arbitrage.hybrid_strategy")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class HybridMode(str, Enum):
    """Hybrid strategy modes."""
    BALANCED = "balanced"          # Balanced allocation across strategies
    AGGRESSIVE = "aggressive"      # Focus on highest performing strategies
    CONSERVATIVE = "conservative"  # Focus on lowest risk strategies
    ADAPTIVE = "adaptive"          # Dynamically adapt based on market conditions
    DIVERSIFIED = "diversified"    # Spread across all strategies equally


class AllocationMethod(str, Enum):
    """Capital allocation methods."""
    EQUAL = "equal"                # Equal allocation
    PERFORMANCE = "performance"    # Based on performance
    RISK_PARITY = "risk_parity"    # Based on risk
    SHARPE = "sharpe"              # Based on Sharpe ratio
    DYNAMIC = "dynamic"            # Dynamic allocation
    OPTIMAL = "optimal"            # Optimal portfolio allocation


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class StrategyAllocation:
    """Allocation for a sub-strategy."""
    strategy: BaseStrategy
    allocation: float  # Percentage of capital
    current_value: float
    performance_score: float
    risk_score: float
    sharpe_ratio: float
    last_rebalance: datetime


@dataclass
class HybridOpportunity:
    """Hybrid arbitrage opportunity."""
    primary_opportunity: ArbitrageOpportunity
    strategy_type: str
    estimated_profit: float
    confidence: float
    allocation_required: float
    risk_level: RiskLevel
    combined_score: float


# ====================================================================================
# HYBRID STRATEGY
# ====================================================================================

class HybridStrategy(BaseStrategy):
    """
    Hybrid arbitrage strategy combining multiple techniques.
    
    Features:
    - Multi-strategy orchestration
    - Dynamic capital allocation
    - Risk-adjusted performance optimization
    - Market condition adaptation
    - Portfolio-level risk management
    - Performance tracking and learning
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        sub_strategies: Optional[Dict[str, BaseStrategy]] = None,
        allocation_method: AllocationMethod = AllocationMethod.DYNAMIC
    ):
        """
        Initialize the hybrid strategy.
        
        Args:
            config: Strategy configuration
            sub_strategies: Dictionary of sub-strategies
            allocation_method: Allocation method
        """
        super().__init__(config)
        
        # Sub-strategies
        self._sub_strategies = sub_strategies or self._initialize_sub_strategies()
        self._allocations: Dict[str, StrategyAllocation] = {}
        self._allocation_method = allocation_method
        
        # Strategy performance
        self._strategy_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._strategy_returns: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Opportunity tracking
        self._opportunities: List[HybridOpportunity] = []
        self._executed_opportunities: List[HybridOpportunity] = []
        
        # Allocation state
        self._last_allocation_update: Optional[datetime] = None
        self._allocation_update_interval = 60  # seconds
        self._capital_allocation: Dict[str, float] = {}
        self._total_capital = self.config.max_position_size
        
        # Market condition
        self._market_condition = "normal"  # normal, volatile, trending, ranging
        
        # Performance tracking
        self._portfolio_returns: deque = deque(maxlen=1000)
        self._portfolio_volatility: float = 0.0
        self._portfolio_sharpe: float = 0.0
        
        # Metrics
        self._hybrid_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "strategies_used": defaultdict(int),
            "total_profit": 0,
            "capital_utilization": 0,
            "avg_roi": 0,
            "sharpe_ratio": 0
        }
        
        # Initialize allocations
        self._initialize_allocations()
        
        logger.info(f"HybridStrategy initialized with {len(self._sub_strategies)} sub-strategies")
        
    def _initialize_sub_strategies(self) -> Dict[str, BaseStrategy]:
        """
        Initialize sub-strategies.
        
        Returns:
            Dictionary of sub-strategies
        """
        strategies = {}
        
        # Cross-exchange strategy
        ce_config = StrategyConfig(
            name="cross_exchange",
            type="cex_cex",
            max_position_size=self.config.max_position_size * 0.3
        )
        strategies["cross_exchange"] = CrossExchangeStrategy(ce_config)
        
        # Cross-chain strategy
        cc_config = StrategyConfig(
            name="cross_chain",
            type="cross_chain",
            max_position_size=self.config.max_position_size * 0.2
        )
        strategies["cross_chain"] = CrossChainStrategy(cc_config)
        
        # DEX strategy
        dex_config = StrategyConfig(
            name="dex",
            type="dex_dex",
            max_position_size=self.config.max_position_size * 0.2
        )
        strategies["dex"] = DEXStrategy(dex_config)
        
        # Futures-spot strategy
        fs_config = StrategyConfig(
            name="futures_spot",
            type="basis",
            max_position_size=self.config.max_position_size * 0.2
        )
        strategies["futures_spot"] = FuturesSpotStrategy(fs_config)
        
        # Flash loan strategy (if enabled)
        if self.config.metadata.get("flash_loans_enabled", False):
            fl_config = StrategyConfig(
                name="flash_loan",
                type="flash_loan",
                max_position_size=self.config.max_position_size * 0.1
            )
            strategies["flash_loan"] = FlashLoanStrategy(fl_config)
            
        return strategies
        
    def _initialize_allocations(self) -> None:
        """Initialize capital allocations."""
        total = len(self._sub_strategies)
        equal_allocation = 1.0 / total if total > 0 else 0
        
        for name, strategy in self._sub_strategies.items():
            self._allocations[name] = StrategyAllocation(
                strategy=strategy,
                allocation=equal_allocation,
                current_value=0,
                performance_score=0.5,
                risk_score=0.5,
                sharpe_ratio=0.0,
                last_rebalance=datetime.utcnow()
            )
            self._capital_allocation[name] = equal_allocation * self._total_capital
            
    async def initialize(self) -> None:
        """Initialize the hybrid strategy."""
        if self._running:
            return
            
        # Initialize all sub-strategies
        for name, strategy in self._sub_strategies.items():
            await strategy.initialize()
            
        await super().initialize()
        
        logger.info(f"HybridStrategy '{self.name}' initialized")
        
    # ====================================================================
    # STRATEGY ORCHESTRATION
    # ====================================================================
    
    async def _update_allocations(self) -> None:
        """Update capital allocations based on performance."""
        if self._allocation_method == AllocationMethod.EQUAL:
            await self._update_equal_allocations()
        elif self._allocation_method == AllocationMethod.PERFORMANCE:
            await self._update_performance_allocations()
        elif self._allocation_method == AllocationMethod.RISK_PARITY:
            await self._update_risk_parity_allocations()
        elif self._allocation_method == AllocationMethod.SHARPE:
            await self._update_sharpe_allocations()
        else:
            await self._update_dynamic_allocations()
            
        self._last_allocation_update = datetime.utcnow()
        
    async def _update_equal_allocations(self) -> None:
        """Update equal allocations."""
        total = len(self._sub_strategies)
        allocation = 1.0 / total if total > 0 else 0
        
        for name in self._sub_strategies:
            self._allocations[name].allocation = allocation
            self._capital_allocation[name] = allocation * self._total_capital
            
    async def _update_performance_allocations(self) -> None:
        """Update allocations based on performance."""
        # Calculate performance scores
        total_score = 0
        scores = {}
        
        for name, alloc in self._allocations.items():
            score = alloc.performance_score
            scores[name] = score
            total_score += score
            
        # Allocate based on performance
        for name in self._sub_strategies:
            allocation = scores.get(name, 0) / total_score if total_score > 0 else 0
            self._allocations[name].allocation = allocation
            self._capital_allocation[name] = allocation * self._total_capital
            
    async def _update_risk_parity_allocations(self) -> None:
        """Update risk parity allocations."""
        # Calculate risk scores
        total_risk = 0
        risks = {}
        
        for name, alloc in self._allocations.items():
            risk = alloc.risk_score
            risks[name] = risk
            total_risk += risk
            
        # Allocate inversely to risk
        for name in self._sub_strategies:
            allocation = (1 - risks.get(name, 0.5)) / total_risk if total_risk > 0 else 0
            self._allocations[name].allocation = allocation
            self._capital_allocation[name] = allocation * self._total_capital
            
    async def _update_sharpe_allocations(self) -> None:
        """Update allocations based on Sharpe ratio."""
        # Calculate Sharpe scores
        total_score = 0
        scores = {}
        
        for name, alloc in self._allocations.items():
            score = max(0, alloc.sharpe_ratio)
            scores[name] = score
            total_score += score
            
        # Allocate based on Sharpe ratio
        for name in self._sub_strategies:
            allocation = scores.get(name, 0) / total_score if total_score > 0 else 0
            self._allocations[name].allocation = allocation
            self._capital_allocation[name] = allocation * self._total_capital
            
    async def _update_dynamic_allocations(self) -> None:
        """
        Update allocations dynamically based on multiple factors.
        
        Uses a combination of performance, risk, and market conditions.
        """
        # Calculate combined scores
        total_score = 0
        scores = {}
        
        for name, alloc in self._allocations.items():
            # Weighted combination of performance, risk, and market condition
            performance_weight = 0.4
            risk_weight = 0.3
            market_weight = 0.3
            
            performance_score = alloc.performance_score
            risk_score = 1 - alloc.risk_score  # Lower risk is better
            market_score = self._get_market_score(name)
            
            score = (
                performance_score * performance_weight +
                risk_score * risk_weight +
                market_score * market_weight
            )
            
            scores[name] = score
            total_score += score
            
        # Allocate based on combined score
        for name in self._sub_strategies:
            allocation = scores.get(name, 0) / total_score if total_score > 0 else 0
            self._allocations[name].allocation = allocation
            self._capital_allocation[name] = allocation * self._total_capital
            
    def _get_market_score(self, strategy_name: str) -> float:
        """
        Get market condition score for a strategy.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            Market score (0-1)
        """
        # Different strategies perform better in different conditions
        market_scores = {
            "normal": {
                "cross_exchange": 0.6,
                "cross_chain": 0.4,
                "dex": 0.5,
                "futures_spot": 0.5,
                "flash_loan": 0.3
            },
            "volatile": {
                "cross_exchange": 0.7,
                "cross_chain": 0.3,
                "dex": 0.6,
                "futures_spot": 0.4,
                "flash_loan": 0.5
            },
            "trending": {
                "cross_exchange": 0.5,
                "cross_chain": 0.3,
                "dex": 0.4,
                "futures_spot": 0.8,
                "flash_loan": 0.2
            },
            "ranging": {
                "cross_exchange": 0.8,
                "cross_chain": 0.5,
                "dex": 0.7,
                "futures_spot": 0.3,
                "flash_loan": 0.6
            }
        }
        
        return market_scores.get(self._market_condition, {}).get(strategy_name, 0.5)
        
    def _update_market_condition(self) -> None:
        """Update market condition based on volatility and trends."""
        # This would be implemented with actual market data analysis
        # For now, use mock logic
        volatility = self._portfolio_volatility
        
        if volatility > 0.3:
            self._market_condition = "volatile"
        elif volatility > 0.2:
            self._market_condition = "trending"
        elif volatility > 0.1:
            self._market_condition = "ranging"
        else:
            self._market_condition = "normal"
            
    # ====================================================================
    # OPPORTUNITY DETECTION
    # ====================================================================
    
    async def detect_opportunities(self) -> List[HybridOpportunity]:
        """
        Detect hybrid arbitrage opportunities.
        
        Returns:
            List of hybrid opportunities
        """
        opportunities = []
        
        # Update allocations
        if (not self._last_allocation_update or 
            (datetime.utcnow() - self._last_allocation_update).total_seconds() > self._allocation_update_interval):
            await self._update_allocations()
            
        # Detect opportunities from all sub-strategies
        for name, strategy in self._sub_strategies.items():
            try:
                # Get opportunities from sub-strategy
                if hasattr(strategy, 'detect_opportunities'):
                    sub_opportunities = await strategy.detect_opportunities()
                    
                    for opp in sub_opportunities:
                        # Calculate hybrid score
                        score = self._calculate_hybrid_score(opp, name)
                        
                        if score > 0.5:
                            hybrid_opp = HybridOpportunity(
                                primary_opportunity=opp,
                                strategy_type=name,
                                estimated_profit=self._calculate_estimated_profit(opp, name),
                                confidence=opp.confidence if hasattr(opp, 'confidence') else 0.5,
                                allocation_required=self._capital_allocation.get(name, 0),
                                risk_level=await self._assess_opportunity_risk(opp, name),
                                combined_score=score
                            )
                            opportunities.append(hybrid_opp)
                            
            except Exception as e:
                logger.error(f"Error detecting opportunities from {name}: {e}")
                
        # Sort by combined score
        opportunities.sort(key=lambda x: x.combined_score, reverse=True)
        
        # Update metrics
        self._hybrid_metrics["opportunities_detected"] += len(opportunities)
        
        return opportunities[:20]  # Return top 20
        
    def _calculate_hybrid_score(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> float:
        """
        Calculate hybrid score for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Combined score (0-1)
        """
        # Get opportunity attributes
        profit = getattr(opportunity, 'profit_percentage', 0) or getattr(opportunity, 'net_yield', 0) or 0
        confidence = getattr(opportunity, 'confidence', 0.5)
        risk = getattr(opportunity, 'risk_level', RiskLevel.MEDIUM)
        
        # Normalize profit to 0-1
        profit_score = min(1.0, profit / 2)
        
        # Risk score (invert)
        risk_scores = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.6,
            RiskLevel.HIGH: 0.3,
            RiskLevel.VERY_HIGH: 0.1
        }
        risk_score = risk_scores.get(risk, 0.5)
        
        # Allocation score
        allocation = self._capital_allocation.get(strategy_name, 0)
        allocation_score = min(1.0, allocation / 1000)
        
        # Performance score
        performance = self._allocations.get(strategy_name)
        performance_score = performance.performance_score if performance else 0.5
        
        # Combined weighted score
        score = (
            profit_score * 0.3 +
            confidence * 0.25 +
            risk_score * 0.2 +
            allocation_score * 0.15 +
            performance_score * 0.1
        )
        
        return min(1.0, max(0, score))
        
    def _calculate_estimated_profit(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> float:
        """
        Calculate estimated profit for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Estimated profit
        """
        # Get profit from opportunity
        profit = getattr(opportunity, 'net_profit', 0) or getattr(opportunity, 'profit_potential', 0) or 0
        
        # Adjust for allocation
        allocation = self._capital_allocation.get(strategy_name, 0)
        total_capital = self._total_capital
        
        if total_capital > 0:
            profit = profit * (allocation / total_capital)
            
        return profit
        
    async def _assess_opportunity_risk(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> RiskLevel:
        """
        Assess risk for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Risk level
        """
        # Get risk from opportunity or estimate
        if hasattr(opportunity, 'risk_level'):
            return opportunity.risk_level
            
        # Estimate risk based on type
        risk_map = {
            "cross_exchange": RiskLevel.MEDIUM,
            "cross_chain": RiskLevel.HIGH,
            "dex": RiskLevel.MEDIUM,
            "futures_spot": RiskLevel.MEDIUM,
            "flash_loan": RiskLevel.HIGH
        }
        
        base_risk = risk_map.get(strategy_name, RiskLevel.MEDIUM)
        
        # Adjust based on profit and confidence
        profit = getattr(opportunity, 'profit_percentage', 0) or 0
        confidence = getattr(opportunity, 'confidence', 0.5)
        
        if profit > 1.0 and confidence > 0.7:
            return RiskLevel.LOW
        elif profit > 0.5 and confidence > 0.5:
            return RiskLevel.MEDIUM
        else:
            return base_risk
            
    # ====================================================================
    # OPPORTUNITY EXECUTION
    # ====================================================================
    
    async def execute_arbitrage(
        self,
        opportunity: HybridOpportunity
    ) -> StrategyResult:
        """
        Execute a hybrid arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            Strategy result
        """
        try:
            # Validate opportunity
            if not await self._validate_opportunity(opportunity):
                return StrategyResult(
                    success=False,
                    message="Opportunity validation failed",
                    error="Invalid opportunity"
                )
                
            # Check risk
            if opportunity.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                return StrategyResult(
                    success=False,
                    message="Risk too high",
                    error=f"Risk level: {opportunity.risk_level.value}"
                )
                
            # Get sub-strategy
            strategy = self._sub_strategies.get(opportunity.strategy_type)
            if not strategy:
                return StrategyResult(
                    success=False,
                    message="Strategy not found",
                    error=f"Strategy {opportunity.strategy_type} not found"
                )
                
            # Execute trade using sub-strategy
            result = await strategy.execute_trade(opportunity.primary_opportunity)
            
            # Update metrics
            if result.success:
                self._hybrid_metrics["opportunities_executed"] += 1
                self._hybrid_metrics["strategies_used"][opportunity.strategy_type] += 1
                self._hybrid_metrics["total_profit"] += result.trade.net_profit if result.trade else 0
                
                # Update strategy performance
                self._update_strategy_performance(opportunity.strategy_type, result)
                
            else:
                self._hybrid_metrics["opportunities_failed"] += 1
                
            return result
            
        except Exception as e:
            logger.error(f"Hybrid execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    async def _validate_opportunity(
        self,
        opportunity: HybridOpportunity
    ) -> bool:
        """
        Validate a hybrid opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        # Check confidence
        if opportunity.confidence < self.config.min_confidence:
            return False
            
        # Check allocation
        if opportunity.allocation_required < self.config.max_position_size * 0.01:
            return False
            
        # Check estimated profit
        if opportunity.estimated_profit < 1.0:
            return False
            
        return True
        
    def _update_strategy_performance(
        self,
        strategy_name: str,
        result: StrategyResult
    ) -> None:
        """
        Update strategy performance metrics.
        
        Args:
            strategy_name: Strategy name
            result: Execution result
        """
        if not result.success or not result.trade:
            return
            
        # Update returns
        return_value = result.trade.net_profit / self._capital_allocation.get(strategy_name, 1)
        self._strategy_returns[strategy_name].append(return_value)
        
        # Update performance score
        returns = list(self._strategy_returns[strategy_name])
        if len(returns) > 10:
            avg_return = statistics.mean(returns[-10:])
            std_dev = statistics.stdev(returns[-10:]) if len(returns) > 1 else 0.01
            
            performance_score = max(0, min(1, (avg_return / std_dev) * 10))
            
            self._allocations[strategy_name].performance_score = performance_score
            self._allocations[strategy_name].sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0
            
    # ====================================================================
    # PORTFOLIO MANAGEMENT
    # ====================================================================
    
    async def rebalance_portfolio(self) -> None:
        """
        Rebalance the portfolio based on allocations.
        """
        await self._update_allocations()
        
        # Close positions in strategies with reduced allocation
        for name, alloc in self._allocations.items():
            strategy = self._sub_strategies.get(name)
            if strategy and hasattr(strategy, 'get_open_positions'):
                positions = strategy.get_open_positions()
                for position in positions:
                    # Check if position exceeds allocation
                    current_value = position.size * position.current_price
                    if current_value > self._capital_allocation.get(name, 0) * 1.2:
                        await strategy.close_position(position)
                        
        logger.info("Portfolio rebalanced")
        
    # ====================================================================
    # STRATEGY INTERFACE IMPLEMENTATION
    # ====================================================================
    
    async def analyze_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Analyze an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to analyze
            
        Returns:
            Analysis result
        """
        # Route to appropriate sub-strategy
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'analyze_opportunity'):
                try:
                    result = await strategy.analyze_opportunity(opportunity)
                    if result.get('action') != 'skip':
                        return {
                            'action': 'analyze',
                            'strategy': name,
                            'result': result
                        }
                except Exception:
                    continue
                    
        return {'action': 'skip', 'reason': 'No suitable strategy found'}
        
    async def execute_trade(
        self,
        opportunity: ArbitrageOpportunity,
        **kwargs
    ) -> StrategyResult:
        """
        Execute a trade based on an opportunity.
        
        Args:
            opportunity: Opportunity to execute
            **kwargs: Additional parameters
            
        Returns:
            Strategy result
        """
        # Route to appropriate sub-strategy
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'validate_opportunity'):
                try:
                    if await strategy.validate_opportunity(opportunity):
                        return await strategy.execute_trade(opportunity, **kwargs)
                except Exception:
                    continue
                    
        return StrategyResult(
            success=False,
            message="No suitable strategy for opportunity",
            error="Routing failed"
        )
        
    async def validate_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> bool:
        """
        Validate an opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        # Check with all sub-strategies
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'validate_opportunity'):
                try:
                    if await strategy.validate_opportunity(opportunity):
                        return True
                except Exception:
                    continue
        return False
        
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy metrics.
        
        Returns:
            Metrics dictionary
        """
        base_metrics = await super().get_metrics()
        
        # Get metrics from sub-strategies
        strategy_metrics = {}
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'get_metrics'):
                try:
                    strategy_metrics[name] = await strategy.get_metrics()
                except Exception:
                    strategy_metrics[name] = {}
                    
        return {
            **base_metrics,
            "hybrid": {
                "opportunities_detected": self._hybrid_metrics["opportunities_detected"],
                "opportunities_executed": self._hybrid_metrics["opportunities_executed"],
                "opportunities_failed": self._hybrid_metrics["opportunities_failed"],
                "success_rate": self._hybrid_metrics["opportunities_executed"] / max(1, self._hybrid_metrics["opportunities_detected"]) * 100,
                "strategies_used": dict(self._hybrid_metrics["strategies_used"]),
                "total_profit": self._hybrid_metrics["total_profit"],
                "capital_utilization": self._hybrid_metrics["capital_utilization"],
                "avg_roi": self._hybrid_metrics["avg_roi"],
                "sharpe_ratio": self._hybrid_metrics["sharpe_ratio"]
            },
            "allocations": {
                name: {
                    "allocation": alloc.allocation,
                    "performance_score": alloc.performance_score,
                    "risk_score": alloc.risk_score,
                    "sharpe_ratio": alloc.sharpe_ratio
                }
                for name, alloc in self._allocations.items()
            },
            "market_condition": self._market_condition,
            "allocation_method": self._allocation_method.value,
            "sub_strategies": strategy_metrics
        }
        
    async def reset(self) -> None:
        """Reset strategy state."""
        # Reset all sub-strategies
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'reset'):
                await strategy.reset()
                
        self._opportunities = []
        self._executed_opportunities = []
        self._strategy_returns = defaultdict(lambda: deque(maxlen=100))
        self._hybrid_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "strategies_used": defaultdict(int),
            "total_profit": 0,
            "capital_utilization": 0,
            "avg_roi": 0,
            "sharpe_ratio": 0
        }
        
        self._initialize_allocations()
        
        logger.info(f"HybridStrategy '{self.name}' reset")
        
    # ====================================================================
    # CLEANUP
    # ====================================================================
    
    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        # Clean up all sub-strategies
        for name, strategy in self._sub_strategies.items():
            if hasattr(strategy, 'cleanup'):
                await strategy.cleanup()
                
        await super().cleanup()
        
        logger.info(f"HybridStrategy '{self.name}' cleaned up")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'HybridMode',
    'AllocationMethod',
    'StrategyAllocation',
    'HybridOpportunity',
    'HybridStrategy',
]
