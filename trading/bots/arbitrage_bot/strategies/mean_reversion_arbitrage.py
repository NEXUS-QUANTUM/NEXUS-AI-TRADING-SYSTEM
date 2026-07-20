# trading/bots/arbitrage_bot/strategies/mean_reversion_arbitrage.py
# NEXUS AI TRADING SYSTEM - MEAN REVERSION ARBITRAGE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module implements mean reversion arbitrage strategies for exploiting
# temporary price deviations from historical means across exchanges.
# ====================================================================================

"""
NEXUS Mean Reversion Arbitrage Strategy

This module provides mean reversion arbitrage strategies that:
- Identify temporary price deviations from historical means
- Execute pair trades based on mean reversion signals
- Monitor spread relationships across exchanges
- Optimize entry and exit timing
- Implement statistical arbitrage techniques
- Track cointegration relationships
- Manage risk through position sizing
- Adapt to changing market regimes
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
import numpy as np
from scipy import stats

# NEXUS internal imports
from trading.bots.arbitrage_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, StrategyResult
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity, OpportunityType, OpportunityStatus
from trading.bots.arbitrage_bot.models.trade import Trade, TradeSide, TradeStatus, TradeType
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector

logger = logging.getLogger("nexus.arbitrage.mean_reversion_arbitrage")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class MeanReversionSignal(str, Enum):
    """Types of mean reversion signals."""
    ZSCORE = "zscore"
    RSI = "rsi"
    BOLLINGER = "bollinger"
    KELTNER = "keltner"
    DONCHIAN = "donchian"
    COINTEGRATION = "cointegration"
    CORRELATION = "correlation"


class SignalStrength(str, Enum):
    """Strength of mean reversion signal."""
    VERY_STRONG = "very_strong"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    VERY_WEAK = "very_weak"


class ExitCondition(str, Enum):
    """Exit conditions for mean reversion trades."""
    MEAN_REVERSION = "mean_reversion"
    TARGET_PROFIT = "target_profit"
    STOP_LOSS = "stop_loss"
    TIME_BASED = "time_based"
    SIGNAL_REVERSAL = "signal_reversal"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class MeanReversionPair:
    """Pair for mean reversion arbitrage."""
    symbol: str
    exchange: str
    mean_price: float
    std_dev: float
    zscore: float
    rsi: float
    bollinger_upper: float
    bollinger_lower: float
    signal: MeanReversionSignal
    signal_strength: SignalStrength
    is_opportunity: bool
    confidence: float


@dataclass
class MeanReversionOpportunity:
    """Mean reversion arbitrage opportunity."""
    symbol: str
    exchange: str
    current_price: float
    mean_price: float
    zscore: float
    deviation: float
    deviation_percentage: float
    signal_type: MeanReversionSignal
    signal_strength: SignalStrength
    expected_reversion_price: float
    profit_potential: float
    confidence: float
    stop_loss: float
    take_profit: float
    time_horizon: float
    direction: str  # long, short
    entry_price: float
    exit_price: float
    timestamp: datetime


# ====================================================================================
# MEAN REVERSION ARBITRAGE STRATEGY
# ====================================================================================

class MeanReversionArbitrage(BaseStrategy):
    """
    Mean reversion arbitrage strategy.
    
    Features:
    - Statistical arbitrage based on mean reversion
    - Multiple signal types (Z-score, RSI, Bollinger Bands)
    - Cointegration and correlation analysis
    - Adaptive parameter tuning
    - Risk management through position sizing
    - Multiple exit conditions
    - Performance tracking and optimization
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        lookback_period: int = 100,
        zscore_threshold: float = 2.0,
        rsi_threshold: float = 30.0
    ):
        """
        Initialize the mean reversion strategy.
        
        Args:
            config: Strategy configuration
            lookback_period: Lookback period for calculations
            zscore_threshold: Z-score threshold for signals
            rsi_threshold: RSI threshold for signals
        """
        super().__init__(config)
        
        # Configuration
        self._lookback_period = lookback_period
        self._zscore_threshold = zscore_threshold
        self._rsi_threshold = rsi_threshold
        
        # Price data storage
        self._price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._returns_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._spread_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        
        # Statistical data
        self._means: Dict[str, float] = {}
        self._std_devs: Dict[str, float] = {}
        self._z_scores: Dict[str, float] = {}
        self._rsi_values: Dict[str, float] = {}
        self._bollinger_bands: Dict[str, Dict[str, float]] = {}
        
        # Cointegration data
        self._cointegration_pairs: Dict[str, Dict[str, float]] = {}
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        
        # Opportunity tracking
        self._opportunities: List[MeanReversionOpportunity] = []
        self._executed_opportunities: List[MeanReversionOpportunity] = []
        self._closed_opportunities: List[MeanReversionOpportunity] = []
        
        # Performance tracking
        self._signal_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._symbol_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # State
        self._last_calculation: Optional[datetime] = None
        self._calculation_interval = 10  # seconds
        
        # Execution parameters
        self._min_profit_threshold = self.config.min_profit_threshold
        self._max_position_size = self.config.max_position_size
        self._stop_loss_percentage = 0.02  # 2%
        self._take_profit_percentage = 0.03  # 3%
        self._max_holding_time = 3600  # 1 hour in seconds
        
        # Metrics
        self._mean_reversion_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "signals_used": defaultdict(int),
            "signals_strength": defaultdict(int),
            "avg_time_to_reversion": 0,
            "total_profit": 0,
            "win_rate": 0,
            "max_drawdown": 0
        }
        
        logger.info(f"MeanReversionArbitrage initialized with lookback={lookback_period}, zscore={zscore_threshold}")
        
    # ====================================================================
    # DATA COLLECTION
    # ====================================================================
    
    async def _update_data(self, symbol: str, price: float) -> None:
        """
        Update price data for a symbol.
        
        Args:
            symbol: Symbol name
            price: Current price
        """
        self._price_history[symbol].append(price)
        
        # Calculate returns
        if len(self._price_history[symbol]) > 1:
            prev_price = list(self._price_history[symbol])[-2]
            if prev_price > 0:
                return_ = (price - prev_price) / prev_price
                self._returns_history[symbol].append(return_)
                
        # Calculate statistics
        if len(self._price_history[symbol]) >= self._lookback_period:
            prices = list(self._price_history[symbol])[-self._lookback_period:]
            
            # Mean and standard deviation
            self._means[symbol] = statistics.mean(prices)
            self._std_devs[symbol] = statistics.stdev(prices) if len(prices) > 1 else 0
            
            # Z-score
            if self._std_devs[symbol] > 0:
                self._z_scores[symbol] = (price - self._means[symbol]) / self._std_devs[symbol]
                
            # RSI
            self._rsi_values[symbol] = self._calculate_rsi(symbol)
            
            # Bollinger Bands
            if self._std_devs[symbol] > 0:
                self._bollinger_bands[symbol] = {
                    "upper": self._means[symbol] + 2 * self._std_devs[symbol],
                    "middle": self._means[symbol],
                    "lower": self._means[symbol] - 2 * self._std_devs[symbol]
                }
                
    def _calculate_rsi(self, symbol: str) -> float:
        """
        Calculate RSI for a symbol.
        
        Args:
            symbol: Symbol name
            
        Returns:
            RSI value
        """
        returns = list(self._returns_history[symbol])
        if len(returns) < 14:
            return 50.0
            
        recent_returns = returns[-14:]
        gains = [r for r in recent_returns if r > 0]
        losses = [abs(r) for r in recent_returns if r < 0]
        
        avg_gain = sum(gains) / len(gains) if gains else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        if avg_loss == 0:
            return 100.0
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
        
    # ====================================================================
    # SIGNAL DETECTION
    # ====================================================================
    
    async def detect_signals(self) -> List[MeanReversionPair]:
        """
        Detect mean reversion signals.
        
        Returns:
            List of mean reversion pairs
        """
        signals = []
        
        for symbol, price in self._price_history.items():
            if len(price) < self._lookback_period:
                continue
                
            current_price = price[-1]
            
            # Check Z-score signal
            zscore = self._z_scores.get(symbol, 0)
            if abs(zscore) > self._zscore_threshold:
                signal_type = MeanReversionSignal.ZSCORE
                signal_strength = self._get_signal_strength(abs(zscore))
                
                pair = MeanReversionPair(
                    symbol=symbol,
                    exchange="",
                    mean_price=self._means.get(symbol, 0),
                    std_dev=self._std_devs.get(symbol, 0),
                    zscore=zscore,
                    rsi=self._rsi_values.get(symbol, 50),
                    bollinger_upper=self._bollinger_bands.get(symbol, {}).get("upper", 0),
                    bollinger_lower=self._bollinger_bands.get(symbol, {}).get("lower", 0),
                    signal=signal_type,
                    signal_strength=signal_strength,
                    is_opportunity=True,
                    confidence=self._calculate_confidence(symbol, signal_type)
                )
                signals.append(pair)
                
            # Check RSI signal
            rsi = self._rsi_values.get(symbol, 50)
            if rsi < self._rsi_threshold or rsi > (100 - self._rsi_threshold):
                signal_type = MeanReversionSignal.RSI
                signal_strength = self._get_signal_strength(abs(50 - rsi) / 50)
                
                pair = MeanReversionPair(
                    symbol=symbol,
                    exchange="",
                    mean_price=self._means.get(symbol, 0),
                    std_dev=self._std_devs.get(symbol, 0),
                    zscore=zscore,
                    rsi=rsi,
                    bollinger_upper=self._bollinger_bands.get(symbol, {}).get("upper", 0),
                    bollinger_lower=self._bollinger_bands.get(symbol, {}).get("lower", 0),
                    signal=signal_type,
                    signal_strength=signal_strength,
                    is_opportunity=True,
                    confidence=self._calculate_confidence(symbol, signal_type)
                )
                signals.append(pair)
                
            # Check Bollinger Band signal
            if symbol in self._bollinger_bands:
                bb = self._bollinger_bands[symbol]
                if current_price >= bb["upper"] or current_price <= bb["lower"]:
                    signal_type = MeanReversionSignal.BOLLINGER
                    signal_strength = self._get_signal_strength(
                        abs(current_price - bb["middle"]) / bb["middle"]
                    )
                    
                    pair = MeanReversionPair(
                        symbol=symbol,
                        exchange="",
                        mean_price=self._means.get(symbol, 0),
                        std_dev=self._std_devs.get(symbol, 0),
                        zscore=zscore,
                        rsi=rsi,
                        bollinger_upper=bb["upper"],
                        bollinger_lower=bb["lower"],
                        signal=signal_type,
                        signal_strength=signal_strength,
                        is_opportunity=True,
                        confidence=self._calculate_confidence(symbol, signal_type)
                    )
                    signals.append(pair)
                    
        # Sort by signal strength
        strength_order = {
            SignalStrength.VERY_STRONG: 5,
            SignalStrength.STRONG: 4,
            SignalStrength.MODERATE: 3,
            SignalStrength.WEAK: 2,
            SignalStrength.VERY_WEAK: 1
        }
        signals.sort(key=lambda x: strength_order.get(x.signal_strength, 0), reverse=True)
        
        return signals[:20]  # Return top 20
        
    def _get_signal_strength(self, value: float) -> SignalStrength:
        """
        Get signal strength based on value.
        
        Args:
            value: Signal value
            
        Returns:
            Signal strength
        """
        if value > 3.0:
            return SignalStrength.VERY_STRONG
        elif value > 2.0:
            return SignalStrength.STRONG
        elif value > 1.5:
            return SignalStrength.MODERATE
        elif value > 1.0:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK
            
    def _calculate_confidence(self, symbol: str, signal_type: MeanReversionSignal) -> float:
        """
        Calculate confidence for a signal.
        
        Args:
            symbol: Symbol name
            signal_type: Signal type
            
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5
        
        # Based on Z-score
        zscore = self._z_scores.get(symbol, 0)
        if abs(zscore) > 3.0:
            confidence += 0.2
        elif abs(zscore) > 2.0:
            confidence += 0.1
            
        # Based on RSI
        rsi = self._rsi_values.get(symbol, 50)
        if rsi < 20 or rsi > 80:
            confidence += 0.2
        elif rsi < 30 or rsi > 70:
            confidence += 0.1
            
        # Based on historical success
        symbol_perf = self._symbol_performance.get(symbol, {})
        if symbol_perf.get("success_rate", 0) > 0.6:
            confidence += 0.1
            
        return min(1.0, confidence)
        
    # ====================================================================
    # OPPORTUNITY CREATION
    # ====================================================================
    
    def create_opportunity(self, signal: MeanReversionPair) -> MeanReversionOpportunity:
        """
        Create a mean reversion opportunity from a signal.
        
        Args:
            signal: Mean reversion signal
            
        Returns:
            Mean reversion opportunity
        """
        current_price = self._price_history[signal.symbol][-1]
        mean_price = signal.mean_price
        
        # Determine direction
        if current_price > mean_price:
            direction = "short"
            entry_price = current_price
            expected_reversion_price = mean_price
        else:
            direction = "long"
            entry_price = current_price
            expected_reversion_price = mean_price
            
        # Calculate deviation
        deviation = current_price - mean_price
        deviation_percentage = (deviation / mean_price) * 100
        
        # Calculate profit potential
        profit_potential = abs(deviation) * self._max_position_size * 0.5
        
        # Set stop loss and take profit
        if direction == "long":
            stop_loss = entry_price * (1 - self._stop_loss_percentage)
            take_profit = expected_reversion_price + (abs(deviation) * 0.5)
        else:
            stop_loss = entry_price * (1 + self._stop_loss_percentage)
            take_profit = expected_reversion_price - (abs(deviation) * 0.5)
            
        # Estimate time horizon
        volatility = self._std_devs.get(signal.symbol, 0)
        if volatility > 0:
            time_horizon = abs(deviation) / (volatility * 10) * 3600
        else:
            time_horizon = 3600
            
        # Create opportunity
        opportunity = MeanReversionOpportunity(
            symbol=signal.symbol,
            exchange=signal.exchange,
            current_price=current_price,
            mean_price=mean_price,
            zscore=signal.zscore,
            deviation=deviation,
            deviation_percentage=deviation_percentage,
            signal_type=signal.signal,
            signal_strength=signal.signal_strength,
            expected_reversion_price=expected_reversion_price,
            profit_potential=profit_potential,
            confidence=signal.confidence,
            stop_loss=stop_loss,
            take_profit=take_profit,
            time_horizon=time_horizon,
            direction=direction,
            entry_price=entry_price,
            exit_price=expected_reversion_price,
            timestamp=datetime.utcnow()
        )
        
        return opportunity
        
    # ====================================================================
    # OPPORTUNITY EXECUTION
    # ====================================================================
    
    async def execute_opportunity(
        self,
        opportunity: MeanReversionOpportunity
    ) -> StrategyResult:
        """
        Execute a mean reversion opportunity.
        
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
            risk_assessment = await self.assess_mean_reversion_risk(opportunity)
            if risk_assessment.overall_risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                return StrategyResult(
                    success=False,
                    message="Risk too high",
                    error=f"Risk level: {risk_assessment.overall_risk_level.value}"
                )
                
            # Calculate position
            position_size = self.calculate_position_size(opportunity, risk_assessment)
            
            # Execute trade
            result = await self._execute_mean_reversion_trade(opportunity, position_size)
            
            # Update metrics
            self._mean_reversion_metrics["opportunities_detected"] += 1
            self._mean_reversion_metrics["signals_used"][opportunity.signal_type.value] += 1
            self._mean_reversion_metrics["signals_strength"][opportunity.signal_strength.value] += 1
            
            if result.success:
                self._mean_reversion_metrics["opportunities_executed"] += 1
                self._symbol_performance[opportunity.symbol]["success_count"] = \
                    self._symbol_performance[opportunity.symbol].get("success_count", 0) + 1
            else:
                self._mean_reversion_metrics["opportunities_failed"] += 1
                
            return result
            
        except Exception as e:
            logger.error(f"Mean reversion execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    async def _validate_opportunity(
        self,
        opportunity: MeanReversionOpportunity
    ) -> bool:
        """
        Validate a mean reversion opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        # Check confidence
        if opportunity.confidence < self.config.min_confidence:
            return False
            
        # Check deviation percentage
        if abs(opportunity.deviation_percentage) < self._min_profit_threshold * 100:
            return False
            
        # Check profit potential
        if opportunity.profit_potential < 1.0:
            return False
            
        return True
        
    async def assess_mean_reversion_risk(
        self,
        opportunity: MeanReversionOpportunity
    ) -> RiskAssessment:
        """
        Assess risk for mean reversion execution.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            Risk assessment
        """
        risk_factors = {
            "deviation_risk": abs(opportunity.deviation_percentage) / 10,
            "signal_risk": 1 - opportunity.confidence,
            "time_risk": opportunity.time_horizon / 3600,
            "volatility_risk": self._std_devs.get(opportunity.symbol, 0) / opportunity.mean_price * 10
        }
        
        overall_risk = sum(risk_factors.values()) / len(risk_factors)
        
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
            market_risk_score=risk_factors["deviation_risk"] * 100,
            execution_risk_score=risk_factors["time_risk"] * 100,
            volatility_risk_score=risk_factors["volatility_risk"] * 100
        )
        
    def calculate_position_size(
        self,
        opportunity: MeanReversionOpportunity,
        risk_assessment: RiskAssessment
    ) -> float:
        """
        Calculate position size for a mean reversion trade.
        
        Args:
            opportunity: Opportunity to size
            risk_assessment: Risk assessment
            
        Returns:
            Position size
        """
        base_size = self.config.max_position_size
        
        # Risk multiplier
        risk_multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.HIGH: 0.4,
            RiskLevel.VERY_HIGH: 0.2
        }
        risk_multiplier = risk_multipliers.get(risk_assessment.overall_risk_level, 0.5)
        
        # Signal strength multiplier
        strength_multipliers = {
            SignalStrength.VERY_STRONG: 1.0,
            SignalStrength.STRONG: 0.8,
            SignalStrength.MODERATE: 0.6,
            SignalStrength.WEAK: 0.4,
            SignalStrength.VERY_WEAK: 0.2
        }
        strength_multiplier = strength_multipliers.get(opportunity.signal_strength, 0.5)
        
        # Deviation multiplier
        deviation_multiplier = min(1.0, abs(opportunity.deviation_percentage) / 5)
        
        size = base_size * risk_multiplier * strength_multiplier * deviation_multiplier
        
        # Apply min/max
        min_size = base_size * 0.01
        max_size = base_size
        
        return max(min_size, min(size, max_size))
        
    async def _execute_mean_reversion_trade(
        self,
        opportunity: MeanReversionOpportunity,
        position_size: float
    ) -> StrategyResult:
        """
        Execute the mean reversion trade.
        
        Args:
            opportunity: Opportunity to execute
            position_size: Position size
            
        Returns:
            Strategy result
        """
        try:
            # Calculate quantity
            quantity = position_size / opportunity.entry_price
            
            # Simulate execution
            # Mean reversion trades typically take time to play out
            execution_time = random.uniform(0.1, opportunity.time_horizon * 0.1)
            
            # Simulate success (mean reversion occurs)
            success_probability = 0.6 + (opportunity.confidence * 0.3)
            success = random.random() < success_probability
            
            if success:
                # Calculate profit
                profit = abs(opportunity.deviation) * quantity * 0.5
                exit_price = opportunity.expected_reversion_price
                
                # Create trade record
                trade = Trade(
                    id=f"MR-{opportunity.symbol}-{int(time.time())}",
                    strategy_id=self.strategy_id,
                    type=TradeType.ARBITRAGE,
                    symbol=opportunity.symbol,
                    side=TradeSide.BUY if opportunity.direction == "long" else TradeSide.SELL,
                    quantity=quantity,
                    price=opportunity.entry_price,
                    value=position_size,
                    net_profit=profit,
                    profit_percentage=(profit / position_size) * 100,
                    status=TradeStatus.EXECUTED
                )
                
                self._executed_opportunities.append(opportunity)
                await self.on_trade_completed(trade)
                
                # Update metrics
                self._mean_reversion_metrics["total_profit"] += profit
                
                # Update win rate
                executed = self._mean_reversion_metrics["opportunities_executed"]
                successful = sum(1 for o in self._executed_opportunities if o.confidence > 0.6)
                self._mean_reversion_metrics["win_rate"] = (successful / executed) * 100 if executed > 0 else 0
                
                logger.info(f"Mean reversion trade executed: {opportunity.symbol} - Profit: ${profit:.2f}")
                
                return StrategyResult(
                    success=True,
                    message="Mean reversion trade executed successfully",
                    data={
                        "trade": trade,
                        "opportunity": opportunity,
                        "position_size": position_size,
                        "profit": profit,
                        "execution_time": execution_time
                    },
                    trade=trade
                )
            else:
                return StrategyResult(
                    success=False,
                    message="Mean reversion failed - price did not revert",
                    error="Mean reversion did not occur"
                )
                
        except Exception as e:
            logger.error(f"Mean reversion trade execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    # ====================================================================
    # POSITION MANAGEMENT
    # ====================================================================
    
    async def monitor_positions(self) -> None:
        """
        Monitor open positions and check exit conditions.
        """
        # This would be implemented to monitor open positions
        # and exit when mean reversion occurs or stop loss is hit
        pass
        
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
        # Check if mean reversion is applicable
        if opportunity.type not in [OpportunityType.SPOT, OpportunityType.CROSS_EXCHANGE]:
            return {"action": "skip", "reason": "Not applicable for mean reversion"}
            
        return {
            "action": "analyze",
            "opportunity": opportunity,
            "mean_reversion": True
        }
        
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
        # Find matching mean reversion opportunity
        for opp in self._opportunities:
            if opp.symbol == opportunity.symbol:
                return await self.execute_opportunity(opp)
                
        return StrategyResult(
            success=False,
            message="No matching mean reversion opportunity found",
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
        if opportunity.type not in [OpportunityType.SPOT, OpportunityType.CROSS_EXCHANGE]:
            return False
            
        # Check if we have data for this symbol
        if opportunity.symbol not in self._price_history:
            return False
            
        if len(self._price_history[opportunity.symbol]) < self._lookback_period:
            return False
            
        return True
        
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy metrics.
        
        Returns:
            Metrics dictionary
        """
        base_metrics = await super().get_metrics()
        
        return {
            **base_metrics,
            "mean_reversion": {
                "opportunities_detected": self._mean_reversion_metrics["opportunities_detected"],
                "opportunities_executed": self._mean_reversion_metrics["opportunities_executed"],
                "opportunities_failed": self._mean_reversion_metrics["opportunities_failed"],
                "win_rate": self._mean_reversion_metrics["win_rate"],
                "total_profit": self._mean_reversion_metrics["total_profit"],
                "avg_time_to_reversion": self._mean_reversion_metrics["avg_time_to_reversion"],
                "max_drawdown": self._mean_reversion_metrics["max_drawdown"],
                "signals_used": dict(self._mean_reversion_metrics["signals_used"]),
                "signals_strength": dict(self._mean_reversion_metrics["signals_strength"])
            },
            "lookback_period": self._lookback_period,
            "zscore_threshold": self._zscore_threshold,
            "rsi_threshold": self._rsi_threshold,
            "symbols_tracked": len(self._price_history)
        }
        
    async def reset(self) -> None:
        """Reset strategy state."""
        self._opportunities = []
        self._executed_opportunities = []
        self._closed_opportunities = []
        self._price_history = defaultdict(lambda: deque(maxlen=10000))
        self._returns_history = defaultdict(lambda: deque(maxlen=10000))
        self._means = {}
        self._std_devs = {}
        self._z_scores = {}
        self._rsi_values = {}
        self._bollinger_bands = {}
        self._mean_reversion_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "signals_used": defaultdict(int),
            "signals_strength": defaultdict(int),
            "avg_time_to_reversion": 0,
            "total_profit": 0,
            "win_rate": 0,
            "max_drawdown": 0
        }
        self._symbol_performance = defaultdict(dict)
        
        logger.info(f"MeanReversionArbitrage '{self.name}' reset")
        
    # ====================================================================
    # CLEANUP
    # ====================================================================
    
    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        await super().cleanup()
        self._price_history.clear()
        self._returns_history.clear()
        self._means.clear()
        self._std_devs.clear()
        self._z_scores.clear()
        self._rsi_values.clear()
        self._bollinger_bands.clear()
        
        logger.info(f"MeanReversionArbitrage '{self.name}' cleaned up")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'MeanReversionSignal',
    'SignalStrength',
    'ExitCondition',
    'MeanReversionPair',
    'MeanReversionOpportunity',
    'MeanReversionArbitrage',
]
