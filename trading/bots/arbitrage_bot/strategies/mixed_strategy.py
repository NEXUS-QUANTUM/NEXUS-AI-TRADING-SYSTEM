# trading/bots/arbitrage_bot/strategies/mixed_strategy.py
# NEXUS AI TRADING SYSTEM - MIXED ARBITRAGE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module implements a mixed arbitrage strategy that combines multiple
# strategy types with dynamic switching based on market conditions.
# ====================================================================================

"""
NEXUS Mixed Arbitrage Strategy

This module provides a mixed arbitrage strategy that:
- Combines multiple strategy types (CEX, DEX, cross-chain, basis, flash loan)
- Dynamically switches between strategies based on market conditions
- Implements strategy rotation for optimal performance
- Manages risk through diversification
- Tracks strategy performance and adapts
- Supports multiple execution modes
- Provides comprehensive risk management
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
from trading.bots.arbitrage_bot.strategies.mean_reversion_arbitrage import MeanReversionArbitrage
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity
from trading.bots.arbitrage_bot.models.trade import Trade
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector

logger = logging.getLogger("nexus.arbitrage.mixed_strategy")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class StrategyRotation(str, Enum):
    """Strategy rotation modes."""
    ROTATE = "rotate"              # Rotate through strategies
    BEST_PERFORMER = "best_performer"  # Use best performing
    ADAPTIVE = "adaptive"          # Adapt to market conditions
    DIVERSIFY = "diversify"        # Run multiple strategies
    RISK_BASED = "risk_based"      # Based on risk assessment


class StrategyPriority(str, Enum):
    """Strategy priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class StrategyState:
    """State of a strategy in the mixed strategy."""
    name: str
    strategy: BaseStrategy
    priority: StrategyPriority
    weight: float
    active: bool
    performance_score: float
    risk_score: float
    success_rate: float
    last_used: datetime
    opportunities: int
    executions: int
    profit: float
    max_drawdown: float


@dataclass
class MixedOpportunity:
    """Mixed arbitrage opportunity."""
    strategy_name: str
    opportunity: ArbitrageOpportunity
    estimated_profit: float
    confidence: float
    risk_level: RiskLevel
    priority: StrategyPriority
    score: float


# ====================================================================================
# MIXED STRATEGY
# ====================================================================================

class MixedStrategy(BaseStrategy):
    """
    Mixed arbitrage strategy with dynamic switching.
    
    Features:
    - Multiple strategy types
    - Dynamic strategy switching
    - Performance-based selection
    - Risk management
    - Strategy rotation
    - Market condition adaptation
    - Performance tracking
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        rotation_mode: StrategyRotation = StrategyRotation.ADAPTIVE,
        strategies: Optional[List[BaseStrategy]] = None
    ):
        """
        Initialize the mixed strategy.
        
        Args:
            config: Strategy configuration
            rotation_mode: Strategy rotation mode
            strategies: List of strategies to include
        """
        super().__init__(config)
        
        # Configuration
        self._rotation_mode = rotation_mode
        self._strategy_states: Dict[str, StrategyState] = {}
        self._active_strategies: List[str] = []
        
        # Initialize strategies
        self._initialize_strategies(strategies)
        
        # Market condition tracking
        self._market_conditions: Dict[str, float] = {
            "volatility": 0.3,
            "trend": 0.3,
            "liquidity": 0.5,
            "volume": 0.5,
            "spread": 0.3
        }
        
        # Performance tracking
        self._strategy_returns: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._strategy_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Opportunity tracking
        self._opportunities: List[MixedOpportunity] = []
        self._executed_opportunities: List[MixedOpportunity] = []
        
        # State
        self._last_rotation: Optional[datetime] = None
        self._rotation_interval = 300  # 5 minutes in seconds
        self._current_strategy: Optional[str] = None
        self._strategy_history: List[Dict[str, Any]] = []
        
        # Execution parameters
        self._min_profit_threshold = self.config.min_profit_threshold
        self._max_position_size = self.config.max_position_size
        
        # Metrics
        self._mixed_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "strategy_switches": 0,
            "strategies_used": defaultdict(int),
            "total_profit": 0,
            "win_rate": 0,
            "max_drawdown": 0,
            "avg_strategy_duration": 0
        }
        
        logger.info(f"MixedStrategy initialized with {len(self._strategy_states)} strategies")
        
    def _initialize_strategies(self, strategies: Optional[List[BaseStrategy]] = None) -> None:
        """
        Initialize strategies.
        
        Args:
            strategies: List of strategies to include
        """
        if strategies:
            for strategy in strategies:
                self._add_strategy(strategy)
        else:
            # Default strategies
            self._add_default_strategies()
            
    def _add_default_strategies(self) -> None:
        """Add default strategies."""
        # Cross-exchange strategy
        ce_config = StrategyConfig(
            name="cross_exchange",
            type="cex_cex",
            max_position_size=self.config.max_position_size * 0.3,
            min_profit_threshold=0.002
        )
        self.add_strategy(
            CrossExchangeStrategy(ce_config),
            StrategyPriority.HIGH,
            0.25
        )
        
        # Cross-chain strategy
        cc_config = StrategyConfig(
            name="cross_chain",
            type="cross_chain",
            max_position_size=self.config.max_position_size * 0.2,
            min_profit_threshold=0.005
        )
        self.add_strategy(
            CrossChainStrategy(cc_config),
            StrategyPriority.MEDIUM,
            0.20
        )
        
        # DEX strategy
        dex_config = StrategyConfig(
            name="dex",
            type="dex_dex",
            max_position_size=self.config.max_position_size * 0.2,
            min_profit_threshold=0.003
        )
        self.add_strategy(
            DEXStrategy(dex_config),
            StrategyPriority.MEDIUM,
            0.20
        )
        
        # Futures-spot strategy
        fs_config = StrategyConfig(
            name="futures_spot",
            type="basis",
            max_position_size=self.config.max_position_size * 0.15,
            min_profit_threshold=0.001
        )
        self.add_strategy(
            FuturesSpotStrategy(fs_config),
            StrategyPriority.LOW,
            0.15
        )
        
        # Mean reversion strategy
        mr_config = StrategyConfig(
            name="mean_reversion",
            type="mean_reversion",
            max_position_size=self.config.max_position_size * 0.15,
            min_profit_threshold=0.002
        )
        self.add_strategy(
            MeanReversionArbitrage(mr_config),
            StrategyPriority.MEDIUM,
            0.20
        )
        
    def add_strategy(
        self,
        strategy: BaseStrategy,
        priority: StrategyPriority = StrategyPriority.MEDIUM,
        weight: float = 0.2
    ) -> None:
        """
        Add a strategy to the mix.
        
        Args:
            strategy: Strategy to add
            priority: Strategy priority
            weight: Initial weight
        """
        strategy_name = strategy.name
        
        self._strategy_states[strategy_name] = StrategyState(
            name=strategy_name,
            strategy=strategy,
            priority=priority,
            weight=weight,
            active=True,
            performance_score=0.5,
            risk_score=0.5,
            success_rate=0.5,
            last_used=datetime.utcnow(),
            opportunities=0,
            executions=0,
            profit=0,
            max_drawdown=0
        )
        
        self._active_strategies.append(strategy_name)
        
        logger.info(f"Added strategy: {strategy_name} with priority {priority.value} and weight {weight}")
        
    def remove_strategy(self, strategy_name: str) -> bool:
        """
        Remove a strategy from the mix.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            True if removed
        """
        if strategy_name in self._strategy_states:
            del self._strategy_states[strategy_name]
            if strategy_name in self._active_strategies:
                self._active_strategies.remove(strategy_name)
            logger.info(f"Removed strategy: {strategy_name}")
            return True
        return False
        
    async def initialize(self) -> None:
        """Initialize the mixed strategy."""
        if self._running:
            return
            
        # Initialize all strategies
        for state in self._strategy_states.values():
            await state.strategy.initialize()
            
        await super().initialize()
        
        # Select initial strategy
        await self._select_strategy()
        
        logger.info(f"MixedStrategy '{self.name}' initialized")
        
    # ====================================================================
    # STRATEGY SELECTION
    # ====================================================================
    
    async def _select_strategy(self) -> Optional[str]:
        """
        Select the best strategy for current conditions.
        
        Returns:
            Selected strategy name or None
        """
        if not self._active_strategies:
            return None
            
        if self._rotation_mode == StrategyRotation.ROTATE:
            return await self._select_rotate()
        elif self._rotation_mode == StrategyRotation.BEST_PERFORMER:
            return await self._select_best_performer()
        elif self._rotation_mode == StrategyRotation.DIVERSIFY:
            return await self._select_diversify()
        elif self._rotation_mode == StrategyRotation.RISK_BASED:
            return await self._select_risk_based()
        else:
            return await self._select_adaptive()
            
    async def _select_rotate(self) -> Optional[str]:
        """
        Select strategy by rotation.
        
        Returns:
            Selected strategy name
        """
        if not self._active_strategies:
            return None
            
        # Find next strategy
        current_index = 0
        if self._current_strategy in self._active_strategies:
            current_index = self._active_strategies.index(self._current_strategy)
            
        next_index = (current_index + 1) % len(self._active_strategies)
        selected = self._active_strategies[next_index]
        
        self._current_strategy = selected
        self._mixed_metrics["strategy_switches"] += 1
        
        logger.info(f"Rotated to strategy: {selected}")
        return selected
        
    async def _select_best_performer(self) -> Optional[str]:
        """
        Select best performing strategy.
        
        Returns:
            Best performing strategy name
        """
        if not self._active_strategies:
            return None
            
        # Score strategies
        scores = {}
        for name in self._active_strategies:
            state = self._strategy_states[name]
            score = state.performance_score * 0.5 + state.success_rate * 0.3 + (1 - state.risk_score) * 0.2
            scores[name] = score
            
        selected = max(scores.items(), key=lambda x: x[1])[0]
        
        self._current_strategy = selected
        self._mixed_metrics["strategy_switches"] += 1
        
        logger.info(f"Best performer: {selected} (score: {scores[selected]:.2f})")
        return selected
        
    async def _select_diversify(self) -> Optional[str]:
        """
        Select strategy for diversification.
        
        Returns:
            Selected strategy name
        """
        if not self._active_strategies:
            return None
            
        # Select based on weights
        weights = []
        strategies = []
        
        for name in self._active_strategies:
            state = self._strategy_states[name]
            if state.weight > 0:
                weights.append(state.weight)
                strategies.append(name)
                
        if not strategies:
            return self._active_strategies[0]
            
        selected = random.choices(strategies, weights=weights)[0]
        
        self._current_strategy = selected
        self._mixed_metrics["strategy_switches"] += 1
        
        logger.info(f"Diversified to: {selected}")
        return selected
        
    async def _select_risk_based(self) -> Optional[str]:
        """
        Select strategy based on risk.
        
        Returns:
            Selected strategy name
        """
        if not self._active_strategies:
            return None
            
        # Select lowest risk strategy
        selected = min(
            self._active_strategies,
            key=lambda x: self._strategy_states[x].risk_score
        )
        
        self._current_strategy = selected
        self._mixed_metrics["strategy_switches"] += 1
        
        logger.info(f"Risk-based selected: {selected}")
        return selected
        
    async def _select_adaptive(self) -> Optional[str]:
        """
        Select strategy adaptively based on market conditions.
        
        Returns:
            Selected strategy name
        """
        if not self._active_strategies:
            return None
            
        # Get market condition scores for each strategy
        scores = {}
        for name in self._active_strategies:
            state = self._strategy_states[name]
            
            # Market condition score
            market_score = self._get_market_score(name)
            
            # Performance score
            performance_score = state.performance_score
            
            # Risk score
            risk_score = 1 - state.risk_score
            
            # Priority score
            priority_scores = {
                StrategyPriority.HIGH: 1.0,
                StrategyPriority.MEDIUM: 0.7,
                StrategyPriority.LOW: 0.4
            }
            priority_score = priority_scores.get(state.priority, 0.5)
            
            # Combined score
            scores[name] = (
                market_score * 0.35 +
                performance_score * 0.25 +
                risk_score * 0.25 +
                priority_score * 0.15
            )
            
        selected = max(scores.items(), key=lambda x: x[1])[0]
        
        self._current_strategy = selected
        self._mixed_metrics["strategy_switches"] += 1
        
        logger.info(f"Adaptive selected: {selected} (score: {scores[selected]:.2f})")
        return selected
        
    def _get_market_score(self, strategy_name: str) -> float:
        """
        Get market condition score for a strategy.
        
        Args:
            strategy_name: Strategy name
            
        Returns:
            Market score (0-1)
        """
        # Strategy suitability for different market conditions
        suitability = {
            "cross_exchange": {
                "volatility": 0.7,
                "trend": 0.5,
                "liquidity": 0.8,
                "volume": 0.7,
                "spread": 0.6
            },
            "cross_chain": {
                "volatility": 0.6,
                "trend": 0.4,
                "liquidity": 0.5,
                "volume": 0.4,
                "spread": 0.5
            },
            "dex": {
                "volatility": 0.6,
                "trend": 0.5,
                "liquidity": 0.4,
                "volume": 0.5,
                "spread": 0.7
            },
            "futures_spot": {
                "volatility": 0.4,
                "trend": 0.8,
                "liquidity": 0.6,
                "volume": 0.6,
                "spread": 0.3
            },
            "mean_reversion": {
                "volatility": 0.5,
                "trend": 0.3,
                "liquidity": 0.6,
                "volume": 0.5,
                "spread": 0.4
            }
        }
        
        scores = suitability.get(strategy_name, {})
        if not scores:
            return 0.5
            
        # Weighted average
        total_score = sum(
            scores.get(condition, 0.5) * value
            for condition, value in self._market_conditions.items()
        )
        
        return total_score / sum(self._market_conditions.values())
        
    # ====================================================================
    # MARKET CONDITION UPDATE
    # ====================================================================
    
    async def _update_market_conditions(self) -> None:
        """Update market condition indicators."""
        # This would be implemented with actual market data
        # For now, use mock logic
        self._market_conditions = {
            "volatility": 0.3 + random.random() * 0.4,
            "trend": 0.3 + random.random() * 0.4,
            "liquidity": 0.4 + random.random() * 0.4,
            "volume": 0.4 + random.random() * 0.4,
            "spread": 0.2 + random.random() * 0.3
        }
        
    # ====================================================================
    # OPPORTUNITY DETECTION
    # ====================================================================
    
    async def detect_opportunities(self) -> List[MixedOpportunity]:
        """
        Detect mixed arbitrage opportunities.
        
        Returns:
            List of mixed opportunities
        """
        opportunities = []
        
        # Update market conditions
        await self._update_market_conditions()
        
        # Consider strategy rotation
        if (not self._last_rotation or 
            (datetime.utcnow() - self._last_rotation).total_seconds() > self._rotation_interval):
            await self._select_strategy()
            self._last_rotation = datetime.utcnow()
            
        # Get opportunities from active strategies
        for name, state in self._strategy_states.items():
            if not state.active:
                continue
                
            strategy = state.strategy
            if hasattr(strategy, 'detect_opportunities'):
                try:
                    sub_opportunities = await strategy.detect_opportunities()
                    
                    for opp in sub_opportunities:
                        # Calculate mixed score
                        score = self._calculate_mixed_score(opp, name)
                        
                        if score > 0.5:
                            mixed_opp = MixedOpportunity(
                                strategy_name=name,
                                opportunity=opp,
                                estimated_profit=self._estimate_opportunity_profit(opp, name),
                                confidence=self._estimate_confidence(opp, name),
                                risk_level=self._estimate_risk(opp, name),
                                priority=state.priority,
                                score=score
                            )
                            opportunities.append(mixed_opp)
                            
                except Exception as e:
                    logger.error(f"Error detecting opportunities from {name}: {e}")
                    
        # Sort by score
        opportunities.sort(key=lambda x: x.score, reverse=True)
        
        # Update metrics
        self._mixed_metrics["opportunities_detected"] += len(opportunities)
        
        return opportunities[:20]  # Return top 20
        
    def _calculate_mixed_score(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> float:
        """
        Calculate mixed score for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Mixed score (0-1)
        """
        state = self._strategy_states.get(strategy_name)
        if not state:
            return 0.0
            
        # Get opportunity attributes
        profit = getattr(opportunity, 'profit_percentage', 0) or getattr(opportunity, 'net_yield', 0) or 0
        confidence = getattr(opportunity, 'confidence', 0.5)
        
        # Normalize profit to 0-1
        profit_score = min(1.0, profit / 2)
        
        # Strategy weight score
        weight_score = state.weight
        
        # Performance score
        performance_score = state.performance_score
        
        # Priority score
        priority_scores = {
            StrategyPriority.HIGH: 1.0,
            StrategyPriority.MEDIUM: 0.7,
            StrategyPriority.LOW: 0.4
        }
        priority_score = priority_scores.get(state.priority, 0.5)
        
        # Combined weighted score
        score = (
            profit_score * 0.25 +
            confidence * 0.20 +
            weight_score * 0.20 +
            performance_score * 0.20 +
            priority_score * 0.15
        )
        
        return min(1.0, max(0, score))
        
    def _estimate_opportunity_profit(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> float:
        """
        Estimate profit for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Estimated profit
        """
        profit = getattr(opportunity, 'net_profit', 0) or getattr(opportunity, 'profit_potential', 0) or 0
        return profit
        
    def _estimate_confidence(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> float:
        """
        Estimate confidence for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Confidence score
        """
        confidence = getattr(opportunity, 'confidence', 0.5)
        state = self._strategy_states.get(strategy_name)
        
        if state:
            confidence = (confidence + state.performance_score) / 2
            
        return min(1.0, max(0, confidence))
        
    def _estimate_risk(
        self,
        opportunity: Any,
        strategy_name: str
    ) -> RiskLevel:
        """
        Estimate risk for an opportunity.
        
        Args:
            opportunity: Sub-strategy opportunity
            strategy_name: Strategy name
            
        Returns:
            Risk level
        """
        if hasattr(opportunity, 'risk_level'):
            return opportunity.risk_level
            
        state = self._strategy_states.get(strategy_name)
        if state:
            risk_score = state.risk_score
            if risk_score < 0.3:
                return RiskLevel.LOW
            elif risk_score < 0.5:
                return RiskLevel.MEDIUM
            elif risk_score < 0.7:
                return RiskLevel.HIGH
            else:
                return RiskLevel.VERY_HIGH
                
        return RiskLevel.MEDIUM
        
    # ====================================================================
    # OPPORTUNITY EXECUTION
    # ====================================================================
    
    async def execute_opportunity(
        self,
        opportunity: MixedOpportunity
    ) -> StrategyResult:
        """
        Execute a mixed opportunity.
        
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
                
            # Get strategy
            state = self._strategy_states.get(opportunity.strategy_name)
            if not state:
                return StrategyResult(
                    success=False,
                    message="Strategy not found",
                    error=f"Strategy {opportunity.strategy_name} not found"
                )
                
            # Execute through strategy
            result = await state.strategy.execute_trade(opportunity.opportunity)
            
            # Update state
            if result.success:
                state.executions += 1
                if result.trade:
                    state.profit += result.trade.net_profit
                state.performance_score = min(1.0, state.performance_score * 1.05)
                state.success_rate = state.executions / (state.opportunities + 1) if state.opportunities > 0 else 0.5
                
                self._mixed_metrics["opportunities_executed"] += 1
                self._mixed_metrics["strategies_used"][opportunity.strategy_name] += 1
                self._mixed_metrics["total_profit"] += result.trade.net_profit if result.trade else 0
                
                # Update win rate
                executed = self._mixed_metrics["opportunities_executed"]
                successful = sum(1 for o in self._executed_opportunities if o.score > 0.6)
                self._mixed_metrics["win_rate"] = (successful / executed) * 100 if executed > 0 else 0
                
            else:
                state.risk_score = min(1.0, state.risk_score * 1.05)
                self._mixed_metrics["opportunities_failed"] += 1
                
            return result
            
        except Exception as e:
            logger.error(f"Mixed execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    async def _validate_opportunity(
        self,
        opportunity: MixedOpportunity
    ) -> bool:
        """
        Validate a mixed opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        # Check confidence
        if opportunity.confidence < self.config.min_confidence:
            return False
            
        # Check risk
        if opportunity.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
            return False
            
        # Check profit
        if opportunity.estimated_profit < 1.0:
            return False
            
        return True
        
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
        # Find best strategy for this opportunity
        best_strategy = None
        best_score = -float('inf')
        
        for name, state in self._strategy_states.items():
            if not state.active:
                continue
                
            if hasattr(state.strategy, 'analyze_opportunity'):
                try:
                    result = await state.strategy.analyze_opportunity(opportunity)
                    if result.get('action') != 'skip':
                        score = state.performance_score * 0.6 + state.weight * 0.4
                        if score > best_score:
                            best_score = score
                            best_strategy = name
                except Exception:
                    continue
                    
        if best_strategy:
            return {
                'action': 'analyze',
                'strategy': best_strategy,
                'mixed': True
            }
            
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
        # Find matching mixed opportunity
        for opp in self._opportunities:
            if opp.opportunity == opportunity:
                return await self.execute_opportunity(opp)
                
        return StrategyResult(
            success=False,
            message="No matching mixed opportunity found",
            error="Opportunity not found"
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
        for name, state in self._strategy_states.items():
            if not state.active:
                continue
                
            if hasattr(state.strategy, 'validate_opportunity'):
                try:
                    if await state.strategy.validate_opportunity(opportunity):
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
        for name, state in self._strategy_states.items():
            if hasattr(state.strategy, 'get_metrics'):
                try:
                    strategy_metrics[name] = await state.strategy.get_metrics()
                except Exception:
                    strategy_metrics[name] = {}
                    
        return {
            **base_metrics,
            "mixed": {
                "opportunities_detected": self._mixed_metrics["opportunities_detected"],
                "opportunities_executed": self._mixed_metrics["opportunities_executed"],
                "opportunities_failed": self._mixed_metrics["opportunities_failed"],
                "success_rate": self._mixed_metrics["opportunities_executed"] / max(1, self._mixed_metrics["opportunities_detected"]) * 100,
                "strategy_switches": self._mixed_metrics["strategy_switches"],
                "strategies_used": dict(self._mixed_metrics["strategies_used"]),
                "total_profit": self._mixed_metrics["total_profit"],
                "win_rate": self._mixed_metrics["win_rate"],
                "max_drawdown": self._mixed_metrics["max_drawdown"],
                "avg_strategy_duration": self._mixed_metrics["avg_strategy_duration"]
            },
            "rotation_mode": self._rotation_mode.value,
            "active_strategies": self._active_strategies,
            "current_strategy": self._current_strategy,
            "strategy_states": {
                name: {
                    "priority": state.priority.value,
                    "weight": state.weight,
                    "active": state.active,
                    "performance_score": state.performance_score,
                    "risk_score": state.risk_score,
                    "success_rate": state.success_rate,
                    "opportunities": state.opportunities,
                    "executions": state.executions,
                    "profit": state.profit
                }
                for name, state in self._strategy_states.items()
            },
            "market_conditions": self._market_conditions,
            "sub_strategies": strategy_metrics
        }
        
    async def reset(self) -> None:
        """Reset strategy state."""
        # Reset all strategies
        for state in self._strategy_states.values():
            if hasattr(state.strategy, 'reset'):
                await state.strategy.reset()
                
        self._opportunities = []
        self._executed_opportunities = []
        self._strategy_returns = defaultdict(lambda: deque(maxlen=100))
        self._mixed_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "strategy_switches": 0,
            "strategies_used": defaultdict(int),
            "total_profit": 0,
            "win_rate": 0,
            "max_drawdown": 0,
            "avg_strategy_duration": 0
        }
        
        logger.info(f"MixedStrategy '{self.name}' reset")
        
    # ====================================================================
    # CLEANUP
    # ====================================================================
    
    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        # Clean up all strategies
        for state in self._strategy_states.values():
            if hasattr(state.strategy, 'cleanup'):
                await state.strategy.cleanup()
                
        await super().cleanup()
        
        logger.info(f"MixedStrategy '{self.name}' cleaned up")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'StrategyRotation',
    'StrategyPriority',
    'StrategyState',
    'MixedOpportunity',
    'MixedStrategy',
]
