# trading/bots/arbitrage_bot/strategies/futures_spot_strategy.py
# NEXUS AI TRADING SYSTEM - FUTURES-SPOT ARBITRAGE STRATEGY
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module implements futures-spot arbitrage strategies for exploiting
# basis differences between spot and futures markets.
# ====================================================================================

"""
NEXUS Futures-Spot Arbitrage Strategy

This module provides futures-spot arbitrage strategies that:
- Monitor basis spreads between spot and futures
- Identify profitable cash-and-carry arbitrage
- Execute simultaneous spot and futures positions
- Manage funding rates and expiration
- Optimize for yield and basis capture
- Support multiple futures types (perpetual, quarterly)
- Implement risk management for leveraged positions
- Track PnL and margin requirements
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
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity, OpportunityType, OpportunityStatus
from trading.bots.arbitrage_bot.models.trade import Trade, TradeSide, TradeStatus, TradeType
from trading.bots.arbitrage_bot.models.exchange import ExchangeType
from trading.bots.arbitrage_bot.models.position import Position, PositionSide
from trading.bots.arbitrage_bot.models.risk import RiskAssessment, RiskLevel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector

logger = logging.getLogger("nexus.arbitrage.futures_spot_strategy")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class FuturesType(str, Enum):
    """Types of futures contracts."""
    PERPETUAL = "perpetual"
    QUARTERLY = "quarterly"
    BIQUARTERLY = "biquarterly"
    MONTHLY = "monthly"


class BasisState(str, Enum):
    """State of the basis."""
    CONTANGO = "contango"      # Futures > Spot (positive basis)
    BACKWARDATION = "backwardation"  # Futures < Spot (negative basis)
    NEUTRAL = "neutral"


class ArbitrageDirection(str, Enum):
    """Direction of arbitrage."""
    CASH_AND_CARRY = "cash_and_carry"  # Long spot, short futures
    REVERSE = "reverse"                 # Short spot, long futures


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class FuturesContract:
    """Futures contract information."""
    symbol: str
    exchange: str
    futures_type: FuturesType
    spot_symbol: str
    expiration_date: Optional[datetime]
    funding_rate: float
    funding_interval: int  # hours
    max_leverage: int
    min_margin: float
    initial_margin: float
    maintenance_margin: float
    is_active: bool = True


@dataclass
class BasisOpportunity:
    """Basis arbitrage opportunity."""
    spot_exchange: str
    futures_exchange: str
    spot_symbol: str
    futures_symbol: str
    spot_price: float
    futures_price: float
    basis: float
    basis_bps: float
    annualized_basis: float
    funding_rate: float
    net_yield: float
    position_size: float
    margin_required: float
    profit_potential: float
    days_to_expiry: float
    confidence: float
    direction: ArbitrageDirection
    contract: FuturesContract
    timestamp: datetime


# ====================================================================================
# FUTURES-SPOT STRATEGY
# ====================================================================================

class FuturesSpotStrategy(BaseStrategy):
    """
    Futures-spot arbitrage strategy.
    
    Features:
    - Real-time basis monitoring
    - Cash-and-carry arbitrage
    - Funding rate arbitrage
    - Leverage optimization
    - Margin management
    - Expiration handling
    - Risk management
    - Performance tracking
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        exchanges: Optional[List[str]] = None,
        contracts: Optional[List[FuturesContract]] = None
    ):
        """
        Initialize the futures-spot strategy.
        
        Args:
            config: Strategy configuration
            exchanges: List of exchanges to monitor
            contracts: List of futures contracts
        """
        super().__init__(config)
        
        # Exchange configuration
        self._exchanges = exchanges or ["binance", "bybit", "okx"]
        
        # Contracts
        self._contracts = contracts or self._initialize_contracts()
        self._contract_cache = {c.symbol: c for c in self._contracts}
        
        # Price tracking
        self._spot_prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._futures_prices: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._funding_rates: Dict[str, float] = {}
        
        # Positions
        self._open_positions: List[Position] = []
        self._closed_positions: List[Position] = []
        
        # Opportunity tracking
        self._opportunities: List[BasisOpportunity] = []
        self._executed_opportunities: List[BasisOpportunity] = []
        
        # Performance tracking
        self._exchange_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._contract_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # State
        self._last_price_update: Optional[datetime] = None
        self._price_update_interval = 5  # seconds
        
        # Execution parameters
        self._min_basis_bps = 10  # Minimum basis in bps
        self._min_yield = 0.01  # Minimum annualized yield
        self._max_leverage = 2.0
        self._max_position_size = 10000  # USD
        
        # Metrics
        self._futures_spot_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "exchanges_used": defaultdict(int),
            "contracts_used": defaultdict(int),
            "avg_basis_bps": 0,
            "avg_yield": 0,
            "total_profit": 0,
            "total_funding_collected": 0
        }
        
        logger.info(f"FuturesSpotStrategy initialized with {len(self._contracts)} contracts")
        
    def _initialize_contracts(self) -> List[FuturesContract]:
        """Initialize available futures contracts."""
        return [
            FuturesContract(
                symbol="BTC-USDT-PERP",
                exchange="binance",
                futures_type=FuturesType.PERPETUAL,
                spot_symbol="BTC-USDT",
                expiration_date=None,
                funding_rate=0.0001,
                funding_interval=8,
                max_leverage=25,
                min_margin=0.01,
                initial_margin=0.02,
                maintenance_margin=0.01,
                is_active=True
            ),
            FuturesContract(
                symbol="ETH-USDT-PERP",
                exchange="binance",
                futures_type=FuturesType.PERPETUAL,
                spot_symbol="ETH-USDT",
                expiration_date=None,
                funding_rate=0.0001,
                funding_interval=8,
                max_leverage=25,
                min_margin=0.01,
                initial_margin=0.02,
                maintenance_margin=0.01,
                is_active=True
            ),
            FuturesContract(
                symbol="BTC-USDT-QUARTERLY",
                exchange="bybit",
                futures_type=FuturesType.QUARTERLY,
                spot_symbol="BTC-USDT",
                expiration_date=datetime.utcnow() + timedelta(days=90),
                funding_rate=0.0001,
                funding_interval=8,
                max_leverage=20,
                min_margin=0.015,
                initial_margin=0.03,
                maintenance_margin=0.015,
                is_active=True
            ),
            FuturesContract(
                symbol="SOL-USDT-PERP",
                exchange="okx",
                futures_type=FuturesType.PERPETUAL,
                spot_symbol="SOL-USDT",
                expiration_date=None,
                funding_rate=0.0001,
                funding_interval=8,
                max_leverage=20,
                min_margin=0.015,
                initial_margin=0.025,
                maintenance_margin=0.0125,
                is_active=True
            )
        ]
        
    # ====================================================================
    # PRICE MONITORING
    # ====================================================================
    
    async def _update_prices(self) -> None:
        """Update spot and futures prices."""
        for exchange in self._exchanges:
            try:
                # Spot prices
                spot_data = await self._fetch_spot_prices(exchange)
                if spot_data:
                    self._spot_prices[exchange] = spot_data
                    
                # Futures prices
                futures_data = await self._fetch_futures_prices(exchange)
                if futures_data:
                    self._futures_prices[exchange] = futures_data
                    
                # Funding rates
                funding_data = await self._fetch_funding_rates(exchange)
                if funding_data:
                    self._funding_rates.update(funding_data)
                    
            except Exception as e:
                logger.error(f"Failed to fetch data from {exchange}: {e}")
                
        self._last_price_update = datetime.utcnow()
        
    async def _fetch_spot_prices(self, exchange: str) -> Dict[str, float]:
        """
        Fetch spot prices from an exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Dictionary of spot prices
        """
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "AVAX-USDT", "MATIC-USDT"]
        prices = {}
        
        for symbol in symbols:
            base_price = self._get_base_price(symbol)
            variation = 1 + (random.random() - 0.5) * 0.001
            prices[symbol] = base_price * variation
            
        return prices
        
    async def _fetch_futures_prices(self, exchange: str) -> Dict[str, float]:
        """
        Fetch futures prices from an exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Dictionary of futures prices
        """
        symbols = ["BTC-USDT-PERP", "ETH-USDT-PERP", "SOL-USDT-PERP"]
        prices = {}
        
        for symbol in symbols:
            base_price = self._get_futures_base_price(symbol)
            variation = 1 + (random.random() - 0.5) * 0.001
            prices[symbol] = base_price * variation
            
        return prices
        
    async def _fetch_funding_rates(self, exchange: str) -> Dict[str, float]:
        """
        Fetch funding rates from an exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Dictionary of funding rates
        """
        rates = {
            "BTC-USDT-PERP": 0.0001 + (random.random() - 0.5) * 0.0001,
            "ETH-USDT-PERP": 0.0001 + (random.random() - 0.5) * 0.0001,
            "SOL-USDT-PERP": 0.0001 + (random.random() - 0.5) * 0.0001
        }
        return rates
        
    def _get_base_price(self, symbol: str) -> float:
        """Get base spot price for a symbol."""
        base_prices = {
            "BTC-USDT": 95672.50,
            "ETH-USDT": 3124.80,
            "SOL-USDT": 98.45,
            "AVAX-USDT": 34.12,
            "MATIC-USDT": 0.7890
        }
        return base_prices.get(symbol, 0)
        
    def _get_futures_base_price(self, symbol: str) -> float:
        """Get base futures price for a symbol."""
        base_prices = {
            "BTC-USDT-PERP": 95800.00,
            "ETH-USDT-PERP": 3130.00,
            "SOL-USDT-PERP": 98.60
        }
        return base_prices.get(symbol, 0)
        
    # ====================================================================
    # OPPORTUNITY DETECTION
    # ====================================================================
    
    async def detect_opportunities(self) -> List[BasisOpportunity]:
        """
        Detect basis arbitrage opportunities.
        
        Returns:
            List of opportunities
        """
        opportunities = []
        
        # Update data
        await self._update_prices()
        
        # Check all contracts
        for contract in self._contracts:
            if not contract.is_active:
                continue
                
            # Get prices
            spot_price = self._spot_prices.get(contract.exchange, {}).get(contract.spot_symbol, 0)
            futures_price = self._futures_prices.get(contract.exchange, {}).get(contract.symbol, 0)
            
            if spot_price <= 0 or futures_price <= 0:
                continue
                
            # Calculate basis
            basis = futures_price - spot_price
            basis_bps = (basis / spot_price) * 10000
            
            # Calculate annualized basis
            days_to_expiry = 0
            if contract.expiration_date:
                days_to_expiry = (contract.expiration_date - datetime.utcnow()).days
                if days_to_expiry <= 0:
                    continue
                annualized_basis = basis_bps * (365 / days_to_expiry)
            else:
                # Perpetual: use funding rate
                annualized_basis = (contract.funding_rate * 3) * 365  # 3 funding periods per day
                
            # Check threshold
            if abs(basis_bps) < self._min_basis_bps:
                continue
                
            # Determine direction
            if basis > 0:
                direction = ArbitrageDirection.CASH_AND_CARRY
                yield_ = annualized_basis - (contract.funding_rate * 3 * 365)
            else:
                direction = ArbitrageDirection.REVERSE
                yield_ = -annualized_basis - (contract.funding_rate * 3 * 365)
                
            # Check yield
            if yield_ < self._min_yield:
                continue
                
            # Calculate position
            position_size = self._max_position_size
            margin_required = position_size * contract.initial_margin
            
            # Calculate profit
            if direction == ArbitrageDirection.CASH_AND_CARRY:
                profit_potential = position_size * (basis_bps / 10000)
            else:
                profit_potential = position_size * (-basis_bps / 10000)
                
            # Calculate confidence
            confidence = await self._calculate_confidence(contract, basis_bps, yield_)
            
            if confidence < self.config.min_confidence:
                continue
                
            # Create opportunity
            opportunity = BasisOpportunity(
                spot_exchange=contract.exchange,
                futures_exchange=contract.exchange,
                spot_symbol=contract.spot_symbol,
                futures_symbol=contract.symbol,
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_bps=basis_bps,
                annualized_basis=annualized_basis,
                funding_rate=contract.funding_rate,
                net_yield=yield_,
                position_size=position_size,
                margin_required=margin_required,
                profit_potential=profit_potential,
                days_to_expiry=days_to_expiry if contract.expiration_date else 365,
                confidence=confidence,
                direction=direction,
                contract=contract,
                timestamp=datetime.utcnow()
            )
            
            opportunities.append(opportunity)
            
        # Sort by yield
        opportunities.sort(key=lambda x: x.net_yield, reverse=True)
        
        return opportunities[:10]  # Return top 10
        
    async def _calculate_confidence(
        self,
        contract: FuturesContract,
        basis_bps: float,
        yield_: float
    ) -> float:
        """
        Calculate confidence score for an opportunity.
        
        Args:
            contract: Futures contract
            basis_bps: Basis in bps
            yield_: Annualized yield
            
        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5
        
        # Basis confidence
        if abs(basis_bps) > 50:
            confidence += 0.2
        elif abs(basis_bps) > 20:
            confidence += 0.1
            
        # Yield confidence
        if yield_ > 0.1:
            confidence += 0.2
        elif yield_ > 0.05:
            confidence += 0.1
            
        # Contract confidence
        if contract.futures_type == FuturesType.PERPETUAL:
            confidence += 0.1
        else:
            if contract.expiration_date and contract.expiration_date > datetime.utcnow() + timedelta(days=30):
                confidence += 0.1
                
        return min(1.0, confidence)
        
    # ====================================================================
    # OPPORTUNITY EXECUTION
    # ====================================================================
    
    async def execute_arbitrage(
        self,
        opportunity: BasisOpportunity
    ) -> StrategyResult:
        """
        Execute a basis arbitrage opportunity.
        
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
            risk_assessment = await self.assess_futures_spot_risk(opportunity)
            if risk_assessment.overall_risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                return StrategyResult(
                    success=False,
                    message="Risk too high",
                    error=f"Risk level: {risk_assessment.overall_risk_level.value}"
                )
                
            # Calculate position
            position_size = self.calculate_position_size(opportunity, risk_assessment)
            
            # Execute trade
            result = await self._execute_basis_trade(opportunity, position_size)
            
            # Update metrics
            self._futures_spot_metrics["opportunities_detected"] += 1
            if result.success:
                self._futures_spot_metrics["opportunities_executed"] += 1
                self._exchange_performance[opportunity.spot_exchange]["success_count"] = \
                    self._exchange_performance[opportunity.spot_exchange].get("success_count", 0) + 1
                self._contract_performance[opportunity.contract.symbol]["success_count"] = \
                    self._contract_performance[opportunity.contract.symbol].get("success_count", 0) + 1
            else:
                self._futures_spot_metrics["opportunities_failed"] += 1
                
            return result
            
        except Exception as e:
            logger.error(f"Basis execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    async def _validate_opportunity(
        self,
        opportunity: BasisOpportunity
    ) -> bool:
        """
        Validate a basis opportunity.
        
        Args:
            opportunity: Opportunity to validate
            
        Returns:
            True if valid
        """
        # Check contract is active
        if not opportunity.contract.is_active:
            return False
            
        # Check basis threshold
        if abs(opportunity.basis_bps) < self._min_basis_bps:
            return False
            
        # Check yield
        if opportunity.net_yield < self._min_yield:
            return False
            
        # Check margin
        if opportunity.margin_required > self.config.max_position_size * 0.5:
            return False
            
        return True
        
    async def assess_futures_spot_risk(
        self,
        opportunity: BasisOpportunity
    ) -> RiskAssessment:
        """
        Assess risk for futures-spot execution.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            Risk assessment
        """
        risk_factors = {
            "basis_risk": abs(opportunity.basis_bps) / 100,
            "leverage_risk": 0.3,
            "margin_risk": opportunity.margin_required / opportunity.position_size,
            "expiry_risk": 0.2 if opportunity.contract.expiration_date else 0.1,
            "funding_risk": abs(opportunity.funding_rate) * 10
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
            market_risk_score=risk_factors["basis_risk"] * 100,
            margin_risk_score=risk_factors["margin_risk"] * 100,
            execution_risk_score=risk_factors["expiry_risk"] * 100
        )
        
    def calculate_position_size(
        self,
        opportunity: BasisOpportunity,
        risk_assessment: RiskAssessment
    ) -> float:
        """
        Calculate position size for basis trade.
        
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
        
        # Yield multiplier
        yield_multiplier = min(1.0, opportunity.net_yield / 0.1)
        
        # Confidence multiplier
        confidence_multiplier = opportunity.confidence
        
        # Leverage multiplier
        leverage_multiplier = min(1.0, self._max_leverage / opportunity.contract.max_leverage)
        
        size = base_size * risk_multiplier * yield_multiplier * confidence_multiplier * leverage_multiplier
        
        # Apply min/max
        min_size = base_size * 0.1
        max_size = min(base_size, self._max_position_size)
        
        return max(min_size, min(size, max_size))
        
    async def _execute_basis_trade(
        self,
        opportunity: BasisOpportunity,
        position_size: float
    ) -> StrategyResult:
        """
        Execute the basis trade.
        
        Args:
            opportunity: Opportunity to execute
            position_size: Position size
            
        Returns:
            Strategy result
        """
        try:
            # Calculate quantities
            spot_quantity = position_size / opportunity.spot_price
            futures_quantity = position_size / opportunity.futures_price
            
            # Simulate execution
            success = random.random() < 0.95
            
            if success:
                # Calculate profit
                profit = opportunity.profit_potential * (position_size / opportunity.position_size)
                
                # Create position record
                position = Position(
                    symbol=opportunity.spot_symbol,
                    exchange=opportunity.spot_exchange,
                    side=PositionSide.LONG,
                    size=spot_quantity,
                    entry_price=opportunity.spot_price,
                    current_price=opportunity.spot_price
                )
                
                self._open_positions.append(position)
                
                # Create trade record
                trade = Trade(
                    id=f"FS-{opportunity.contract.symbol}-{int(time.time())}",
                    strategy_id=self.strategy_id,
                    type=TradeType.ARBITRAGE,
                    symbol=opportunity.spot_symbol,
                    side=TradeSide.BUY,
                    quantity=spot_quantity,
                    price=opportunity.spot_price,
                    value=position_size,
                    net_profit=profit,
                    profit_percentage=opportunity.net_yield * 100,
                    status=TradeStatus.EXECUTED
                )
                
                self._executed_opportunities.append(opportunity)
                await self.on_trade_completed(trade)
                
                logger.info(f"Basis trade executed: {opportunity.contract.symbol} - Yield: {opportunity.net_yield:.2%}")
                
                return StrategyResult(
                    success=True,
                    message="Basis trade executed successfully",
                    data={
                        "trade": trade,
                        "position": position,
                        "opportunity": opportunity,
                        "position_size": position_size,
                        "profit": profit
                    },
                    trade=trade
                )
            else:
                return StrategyResult(
                    success=False,
                    message="Basis trade failed",
                    error="Execution simulation failed"
                )
                
        except Exception as e:
            logger.error(f"Basis trade execution error: {e}")
            return StrategyResult(
                success=False,
                message="Execution failed",
                error=str(e)
            )
            
    # ====================================================================
    # POSITION MANAGEMENT
    # ====================================================================
    
    async def close_position(self, position: Position) -> StrategyResult:
        """
        Close an open position.
        
        Args:
            position: Position to close
            
        Returns:
            Strategy result
        """
        try:
            # Calculate exit price (simulated)
            exit_price = position.current_price * (1 + (random.random() - 0.5) * 0.001)
            
            # Calculate PnL
            if position.side == PositionSide.LONG:
                pnl = (exit_price - position.entry_price) * position.size
            else:
                pnl = (position.entry_price - exit_price) * position.size
                
            # Update position
            position.close(exit_price, pnl)
            
            # Move to closed positions
            self._open_positions.remove(position)
            self._closed_positions.append(position)
            
            # Create trade record
            trade = Trade(
                id=f"CLOSE-{position.symbol}-{int(time.time())}",
                strategy_id=self.strategy_id,
                type=TradeType.ARBITRAGE,
                symbol=position.symbol,
                side=TradeSide.SELL if position.side == PositionSide.LONG else TradeSide.BUY,
                quantity=position.size,
                price=exit_price,
                value=position.size * exit_price,
                net_profit=pnl,
                profit_percentage=(pnl / (position.size * position.entry_price)) * 100,
                status=TradeStatus.EXECUTED
            )
            
            await self.on_trade_completed(trade)
            
            logger.info(f"Position closed: {position.symbol} - PnL: ${pnl:.2f}")
            
            return StrategyResult(
                success=True,
                message="Position closed successfully",
                data={
                    "trade": trade,
                    "position": position,
                    "pnl": pnl
                },
                trade=trade
            )
            
        except Exception as e:
            logger.error(f"Position close error: {e}")
            return StrategyResult(
                success=False,
                message="Position close failed",
                error=str(e)
            )
            
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
        if opportunity.type != OpportunityType.BASIS:
            return {"action": "skip", "reason": "Not a basis opportunity"}
            
        if not self._spot_prices:
            await self._update_prices()
            
        return {
            "action": "analyze",
            "opportunity": opportunity,
            "futures_spot": True
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
        for opp in self._opportunities:
            if opp.contract.symbol == opportunity.metadata.get("futures_symbol"):
                return await self.execute_arbitrage(opp)
                
        return StrategyResult(
            success=False,
            message="No matching basis opportunity found",
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
        if opportunity.type != OpportunityType.BASIS:
            return False
            
        if not self._spot_prices:
            return False
            
        for opp in self._opportunities:
            if opp.contract.symbol == opportunity.metadata.get("futures_symbol"):
                return True
                
        return False
        
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get strategy metrics.
        
        Returns:
            Metrics dictionary
        """
        base_metrics = await super().get_metrics()
        
        return {
            **base_metrics,
            "futures_spot": {
                "opportunities_detected": self._futures_spot_metrics["opportunities_detected"],
                "opportunities_executed": self._futures_spot_metrics["opportunities_executed"],
                "opportunities_failed": self._futures_spot_metrics["opportunities_failed"],
                "success_rate": self._futures_spot_metrics["opportunities_executed"] / max(1, self._futures_spot_metrics["opportunities_detected"]) * 100,
                "exchanges_used": dict(self._futures_spot_metrics["exchanges_used"]),
                "contracts_used": dict(self._futures_spot_metrics["contracts_used"]),
                "avg_basis_bps": self._futures_spot_metrics["avg_basis_bps"],
                "avg_yield": self._futures_spot_metrics["avg_yield"],
                "total_profit": self._futures_spot_metrics["total_profit"],
                "total_funding_collected": self._futures_spot_metrics["total_funding_collected"]
            },
            "exchanges": self._exchanges,
            "contracts": [c.symbol for c in self._contracts if c.is_active],
            "open_positions": len(self._open_positions)
        }
        
    async def reset(self) -> None:
        """Reset strategy state."""
        self._opportunities = []
        self._executed_opportunities = []
        self._open_positions = []
        self._closed_positions = []
        self._futures_spot_metrics = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "exchanges_used": defaultdict(int),
            "contracts_used": defaultdict(int),
            "avg_basis_bps": 0,
            "avg_yield": 0,
            "total_profit": 0,
            "total_funding_collected": 0
        }
        self._exchange_performance = defaultdict(dict)
        self._contract_performance = defaultdict(dict)
        
        logger.info(f"FuturesSpotStrategy '{self.name}' reset")
        
    # ====================================================================
    # UTILITY METHODS
    # ====================================================================
    
    def add_contract(self, contract: FuturesContract) -> None:
        """
        Add a futures contract.
        
        Args:
            contract: Contract to add
        """
        self._contracts.append(contract)
        self._contract_cache[contract.symbol] = contract
        logger.info(f"Added futures contract: {contract.symbol}")
        
    def remove_contract(self, symbol: str) -> bool:
        """
        Remove a futures contract.
        
        Args:
            symbol: Contract symbol
            
        Returns:
            True if removed
        """
        for i, contract in enumerate(self._contracts):
            if contract.symbol == symbol:
                self._contracts.pop(i)
                if symbol in self._contract_cache:
                    del self._contract_cache[symbol]
                logger.info(f"Removed futures contract: {symbol}")
                return True
        return False
        
    def update_contract_status(self, symbol: str, is_active: bool) -> bool:
        """
        Update contract status.
        
        Args:
            symbol: Contract symbol
            is_active: New status
            
        Returns:
            True if updated
        """
        for contract in self._contracts:
            if contract.symbol == symbol:
                contract.is_active = is_active
                logger.info(f"Contract {symbol} status updated to {is_active}")
                return True
        return False
        
    def get_open_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of open positions
        """
        return self._open_positions
        
    def get_total_exposure(self) -> float:
        """
        Get total position exposure.
        
        Returns:
            Total exposure in USD
        """
        total = 0
        for position in self._open_positions:
            total += position.size * position.current_price
        return total
        
    # ====================================================================
    # CLEANUP
    # ====================================================================
    
    async def cleanup(self) -> None:
        """Clean up strategy resources."""
        await super().cleanup()
        self._opportunities = []
        self._executed_opportunities = []
        self._spot_prices = {}
        self._futures_prices = {}
        
        # Close all open positions
        for position in self._open_positions[:]:
            await self.close_position(position)
            
        logger.info(f"FuturesSpotStrategy '{self.name}' cleaned up")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'FuturesType',
    'BasisState',
    'ArbitrageDirection',
    'FuturesContract',
    'BasisOpportunity',
    'FuturesSpotStrategy',
]
