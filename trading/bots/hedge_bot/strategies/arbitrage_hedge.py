# trading/bots/hedge_bot/strategies/arbitrage_hedge.py

"""
NEXUS HEDGE BOT - ARBITRAGE HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced arbitrage hedging strategy that identifies and exploits price
discrepancies across different markets, exchanges, and instruments
while maintaining hedged positions.

Version: 3.0.0
"""

import asyncio
import math
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import numpy as np
import pandas as pd
import structlog
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class ArbitrageType(str, Enum):
    """Types of arbitrage opportunities."""
    CROSS_EXCHANGE = "cross_exchange"          # Same asset, different exchanges
    CROSS_INSTRUMENT = "cross_instrument"      # Different instruments (e.g., spot vs futures)
    TRIANGULAR = "triangular"                   # Triangular arbitrage (currency triangle)
    STATISTICAL = "statistical"                # Statistical arbitrage (cointegration)
    BASIS = "basis"                            # Basis arbitrage (spot vs futures)
    FUNDING = "funding"                        # Funding rate arbitrage
    DEBT = "debt"                              # Debt arbitrage (lending/borrowing)
    DEX = "dex"                                # Decentralized exchange arbitrage
    CROSS_CHAIN = "cross_chain"                # Cross-chain arbitrage


class ArbitrageStatus(str, Enum):
    """Status of an arbitrage opportunity."""
    DETECTED = "detected"
    ANALYZING = "analyzing"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    HEDGED = "hedged"


class ExecutionStyle(str, Enum):
    """Execution styles for arbitrage."""
    ATOMIC = "atomic"           # Execute all legs simultaneously
    SEQUENTIAL = "sequential"   # Execute legs sequentially with hedging
    BATCH = "batch"             # Batch execution with hedging
    SMART = "smart"             # Smart execution with dynamic hedging


# === DATA MODELS ===

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity data model."""
    opportunity_id: str = field(default_factory=lambda: str(uuid4()))
    type: ArbitrageType = ArbitrageType.CROSS_EXCHANGE
    status: ArbitrageStatus = ArbitrageStatus.DETECTED
    detected_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    
    # Legs
    legs: List[Dict[str, Any]] = field(default_factory=list)  # Each leg: {instrument, exchange, side, size, price}
    hedge_legs: List[Dict[str, Any]] = field(default_factory=list)
    
    # Prices
    theoretical_price: float = 0.0
    current_price: float = 0.0
    spread: float = 0.0
    spread_pct: float = 0.0
    expected_profit: float = 0.0
    expected_profit_pct: float = 0.0
    realized_profit: float = 0.0
    slippage: float = 0.0
    
    # Risk
    risk_score: float = 0.0
    execution_risk: float = 0.0
    timing_risk: float = 0.0
    slippage_risk: float = 0.0
    max_loss: float = 0.0
    stop_loss: float = 0.0
    
    # Metadata
    confidence: float = 0.0
    priority: int = 1
    fees: Dict[str, float] = field(default_factory=dict)
    timing_constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "detected_at": self.detected_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "type": self.type.value,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArbitrageOpportunity":
        data = data.copy()
        data["detected_at"] = datetime.fromisoformat(data["detected_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        if data.get("executed_at"):
            data["executed_at"] = datetime.fromisoformat(data["executed_at"])
        data["type"] = ArbitrageType(data["type"])
        data["status"] = ArbitrageStatus(data["status"])
        return cls(**data)


@dataclass
class ArbitrageExecution:
    """Arbitrage execution record."""
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    opportunity_id: str = ""
    type: ArbitrageType = ArbitrageType.CROSS_EXCHANGE
    style: ExecutionStyle = ExecutionStyle.SMART
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: ArbitrageStatus = ArbitrageStatus.EXECUTING
    
    # Orders
    orders: List[Dict[str, Any]] = field(default_factory=list)
    hedge_orders: List[Dict[str, Any]] = field(default_factory=list)
    
    # Results
    gross_profit: float = 0.0
    net_profit: float = 0.0
    fees_paid: float = 0.0
    slippage_total: float = 0.0
    execution_time_ms: float = 0.0
    
    # Hedging
    hedge_ratio: float = 0.0
    hedge_effectiveness: float = 0.0
    hedge_pnl: float = 0.0
    
    # Error handling
    errors: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    success: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "type": self.type.value,
            "style": self.style.value,
            "status": self.status.value,
        }


# === ARBITRAGE HEDGE STRATEGY ===

class ArbitrageHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced arbitrage hedging strategy that identifies and exploits price
    discrepancies while maintaining fully hedged positions.
    """
    
    def __init__(
        self,
        name: str = "arbitrage_hedge",
        exchange_connectors: Optional[Dict[str, Any]] = None,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the arbitrage hedge strategy.
        
        Args:
            name: Strategy name
            exchange_connectors: Dictionary of exchange connectors
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)
        
        self.exchange_connectors = exchange_connectors or {}
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data
        
        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False
        
        # Opportunities
        self._opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._active_opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._executed_opportunities: List[ArbitrageOpportunity] = []
        self._failed_opportunities: List[ArbitrageOpportunity] = []
        
        # Executions
        self._executions: Dict[str, ArbitrageExecution] = {}
        self._execution_history: List[ArbitrageExecution] = []
        
        # Configurations
        self._config = {
            "min_spread_pct": 0.001,           # Minimum spread percentage (0.1%)
            "max_spread_pct": 0.05,            # Maximum spread percentage (5%)
            "min_profit_pct": 0.002,           # Minimum profit percentage (0.2%)
            "max_position_size": 1000000.0,    # Maximum position size in base currency
            "max_execution_time_seconds": 30,  # Maximum execution time
            "hedge_ratio": 0.95,               # Hedge ratio for execution
            "slippage_tolerance": 0.001,       # Slippage tolerance (0.1%)
            "max_risk_score": 0.3,             # Maximum risk score for execution
            "opportunity_ttl_seconds": 10,     # Opportunity time-to-live
            "max_retries": 3,                  # Maximum retry count
            "parallel_execution": True,        # Execute legs in parallel
        }
        
        # Statistics
        self._stats = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "total_profit": 0.0,
            "total_fees": 0.0,
            "total_slippage": 0.0,
            "avg_execution_time_ms": 0.0,
            "success_rate": 0.0,
        }
        
        # Price cache
        self._price_cache: Dict[str, Dict[str, float]] = {}
        self._order_book_cache: Dict[str, Dict[str, Any]] = {}
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._scanner_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(
            "arbitrage_hedge_strategy_initialized",
            name=name,
            exchanges=list(self.exchange_connectors.keys()),
        )
    
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and identify arbitrage opportunities.
        
        Args:
            market_data: Current market data
            
        Returns:
            Analysis results with opportunities
        """
        try:
            # Update price cache
            await self._update_price_cache(market_data)
            
            # Scan for opportunities
            opportunities = await self._scan_opportunities(market_data)
            
            # Analyze and filter opportunities
            filtered = await self._filter_opportunities(opportunities)
            
            # Add to active opportunities
            for opp in filtered:
                self._active_opportunities[opp.opportunity_id] = opp
                self._opportunities[opp.opportunity_id] = opp
                self._stats["opportunities_detected"] += 1
            
            # Clean up expired opportunities
            await self._cleanup_expired_opportunities()
            
            # Execute high-priority opportunities
            for opp in self._active_opportunities.values():
                if opp.priority >= 5 and opp.confidence > 0.7:
                    await self._execute_opportunity(opp)
            
            return {
                "opportunities_detected": len(filtered),
                "active_opportunities": len(self._active_opportunities),
                "opportunities": [opp.to_dict() for opp in filtered],
                "stats": self._stats,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "arbitrage_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def _update_price_cache(self, market_data: Dict[str, Any]) -> None:
        """Update price cache with current market data."""
        with self._lock:
            symbols = market_data.get("symbols", [])
            for symbol in symbols:
                if symbol not in self._price_cache:
                    self._price_cache[symbol] = {}
                
                # Update prices from different sources
                for exchange, data in market_data.get("exchanges", {}).items():
                    if symbol in data:
                        self._price_cache[symbol][exchange] = data[symbol].get("price", 0)
    
    async def _scan_opportunities(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """
        Scan for arbitrage opportunities.
        
        Args:
            market_data: Current market data
            
        Returns:
            List of detected opportunities
        """
        opportunities = []
        
        try:
            # Cross-exchange arbitrage
            cross_exchange_opps = await self._scan_cross_exchange(market_data)
            opportunities.extend(cross_exchange_opps)
            
            # Cross-instrument arbitrage
            cross_instrument_opps = await self._scan_cross_instrument(market_data)
            opportunities.extend(cross_instrument_opps)
            
            # Triangular arbitrage
            triangular_opps = await self._scan_triangular(market_data)
            opportunities.extend(triangular_opps)
            
            # Statistical arbitrage
            statistical_opps = await self._scan_statistical(market_data)
            opportunities.extend(statistical_opps)
            
            # Basis arbitrage
            basis_opps = await self._scan_basis(market_data)
            opportunities.extend(basis_opps)
            
            # Funding rate arbitrage
            funding_opps = await self._scan_funding(market_data)
            opportunities.extend(funding_opps)
            
        except Exception as e:
            logger.error("opportunity_scan_error", error=str(e))
        
        return opportunities
    
    async def _scan_cross_exchange(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """Scan for cross-exchange arbitrage opportunities."""
        opportunities = []
        
        try:
            symbols = market_data.get("symbols", [])
            exchanges = market_data.get("exchanges", {})
            
            for symbol in symbols:
                prices = {}
                for exchange, data in exchanges.items():
                    if symbol in data:
                        prices[exchange] = data[symbol].get("price", 0)
                
                if len(prices) < 2:
                    continue
                
                # Find min and max prices
                min_price = min(prices.values())
                max_price = max(prices.values())
                
                if min_price <= 0:
                    continue
                
                spread = max_price - min_price
                spread_pct = spread / min_price
                
                # Check if spread is profitable
                if spread_pct >= self._config["min_spread_pct"]:
                    min_exchange = [k for k, v in prices.items() if v == min_price][0]
                    max_exchange = [k for k, v in prices.items() if v == max_price][0]
                    
                    opportunity = ArbitrageOpportunity(
                        type=ArbitrageType.CROSS_EXCHANGE,
                        legs=[
                            {
                                "instrument": symbol,
                                "exchange": min_exchange,
                                "side": "BUY",
                                "price": min_price,
                            },
                            {
                                "instrument": symbol,
                                "exchange": max_exchange,
                                "side": "SELL",
                                "price": max_price,
                            },
                        ],
                        spread=spread,
                        spread_pct=spread_pct * 100,
                        expected_profit=spread * self._config.get("position_size", 1000),
                        expected_profit_pct=spread_pct * 100,
                        confidence=0.8,
                        priority=3,
                    )
                    opportunities.append(opportunity)
            
        except Exception as e:
            logger.error("cross_exchange_scan_error", error=str(e))
        
        return opportunities
    
    async def _scan_cross_instrument(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """Scan for cross-instrument arbitrage opportunities (spot vs futures)."""
        opportunities = []
        
        try:
            # Get spot and futures prices
            spot_prices = market_data.get("spot_prices", {})
            futures_prices = market_data.get("futures_prices", {})
            
            for symbol, spot_price in spot_prices.items():
                if symbol not in futures_prices:
                    continue
                
                future_price = futures_prices[symbol]
                basis = future_price - spot_price
                basis_pct = basis / spot_price if spot_price > 0 else 0
                
                # Check for basis arbitrage
                if abs(basis_pct) > self._config["min_spread_pct"]:
                    opportunity = ArbitrageOpportunity(
                        type=ArbitrageType.BASIS,
                        legs=[
                            {
                                "instrument": symbol,
                                "type": "spot",
                                "side": "BUY" if basis_pct > 0 else "SELL",
                                "price": spot_price,
                            },
                            {
                                "instrument": symbol,
                                "type": "future",
                                "side": "SELL" if basis_pct > 0 else "BUY",
                                "price": future_price,
                            },
                        ],
                        spread=abs(basis),
                        spread_pct=abs(basis_pct) * 100,
                        expected_profit=abs(basis) * self._config.get("position_size", 1000),
                        expected_profit_pct=abs(basis_pct) * 100,
                        confidence=0.7,
                        priority=2,
                    )
                    opportunities.append(opportunity)
            
        except Exception as e:
            logger.error("cross_instrument_scan_error", error=str(e))
        
        return opportunities
    
    async def _scan_triangular(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """Scan for triangular arbitrage opportunities."""
        opportunities = []
        
        try:
            # Get currency pairs
            pairs = market_data.get("currency_pairs", [])
            
            for pair in pairs:
                if len(pair) != 3:
                    continue
                
                # Triangular arbitrage: A/B, B/C, C/A
                rate_ab = market_data.get(f"{pair[0]}/{pair[1]}", {}).get("price", 0)
                rate_bc = market_data.get(f"{pair[1]}/{pair[2]}", {}).get("price", 0)
                rate_ca = market_data.get(f"{pair[2]}/{pair[0]}", {}).get("price", 0)
                
                if rate_ab <= 0 or rate_bc <= 0 or rate_ca <= 0:
                    continue
                
                # Calculate theoretical cross rate
                theoretical = rate_ab * rate_bc * rate_ca
                arbitrage_pct = abs(theoretical - 1.0)
                
                if arbitrage_pct > self._config["min_spread_pct"]:
                    direction = 1 if theoretical > 1 else -1
                    
                    opportunity = ArbitrageOpportunity(
                        type=ArbitrageType.TRIANGULAR,
                        legs=[
                            {
                                "pair": f"{pair[0]}/{pair[1]}",
                                "side": "BUY" if direction > 0 else "SELL",
                                "price": rate_ab,
                            },
                            {
                                "pair": f"{pair[1]}/{pair[2]}",
                                "side": "BUY" if direction > 0 else "SELL",
                                "price": rate_bc,
                            },
                            {
                                "pair": f"{pair[2]}/{pair[0]}",
                                "side": "BUY" if direction > 0 else "SELL",
                                "price": rate_ca,
                            },
                        ],
                        spread=arbitrage_pct,
                        spread_pct=arbitrage_pct * 100,
                        expected_profit=arbitrage_pct * 1000,
                        expected_profit_pct=arbitrage_pct * 100,
                        confidence=0.6,
                        priority=1,
                    )
                    opportunities.append(opportunity)
            
        except Exception as e:
            logger.error("triangular_scan_error", error=str(e))
        
        return opportunities
    
    async def _scan_statistical(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """Scan for statistical arbitrage opportunities."""
        opportunities = []
        
        try:
            # Use cointegration analysis
            price_data = market_data.get("historical_prices", {})
            
            if len(price_data) < 2:
                return opportunities
            
            # Find cointegrated pairs
            symbols = list(price_data.keys())
            for i in range(len(symbols)):
                for j in range(i + 1, len(symbols)):
                    symbol1 = symbols[i]
                    symbol2 = symbols[j]
                    
                    prices1 = price_data.get(symbol1, [])
                    prices2 = price_data.get(symbol2, [])
                    
                    if len(prices1) < 30 or len(prices2) < 30:
                        continue
                    
                    # Simple correlation check (simplified)
                    corr = np.corrcoef(prices1[-30:], prices2[-30:])[0, 1]
                    
                    if abs(corr) > 0.7:
                        # Calculate spread
                        spread = prices1[-1] - prices2[-1] * (prices1[-1] / prices2[-1])
                        
                        if abs(spread) > 0.01 * prices1[-1]:
                            opportunity = ArbitrageOpportunity(
                                type=ArbitrageType.STATISTICAL,
                                legs=[
                                    {
                                        "instrument": symbol1,
                                        "side": "BUY" if spread < 0 else "SELL",
                                        "price": prices1[-1],
                                    },
                                    {
                                        "instrument": symbol2,
                                        "side": "SELL" if spread < 0 else "BUY",
                                        "price": prices2[-1],
                                    },
                                ],
                                spread=abs(spread),
                                spread_pct=abs(spread / prices1[-1]) * 100,
                                expected_profit=abs(spread) * 100,
                                confidence=0.5,
                                priority=1,
                                metadata={"correlation": corr},
                            )
                            opportunities.append(opportunity)
            
        except Exception as e:
            logger.error("statistical_scan_error", error=str(e))
        
        return opportunities
    
    async def _scan_funding(
        self,
        market_data: Dict[str, Any]
    ) -> List[ArbitrageOpportunity]:
        """Scan for funding rate arbitrage opportunities."""
        opportunities = []
        
        try:
            funding_rates = market_data.get("funding_rates", {})
            
            for symbol, rate in funding_rates.items():
                # Check if funding rate is abnormally high
                if abs(rate) > 0.001:  # 0.1% funding rate
                    opportunity = ArbitrageOpportunity(
                        type=ArbitrageType.FUNDING,
                        legs=[
                            {
                                "instrument": symbol,
                                "type": "perpetual",
                                "side": "BUY" if rate < 0 else "SELL",
                                "funding_rate": rate,
                            },
                            {
                                "instrument": symbol,
                                "type": "spot",
                                "side": "SELL" if rate < 0 else "BUY",
                            },
                        ],
                        spread=abs(rate),
                        spread_pct=abs(rate) * 100,
                        expected_profit=abs(rate) * self._config.get("position_size", 1000),
                        expected_profit_pct=abs(rate) * 100,
                        confidence=0.65,
                        priority=2,
                    )
                    opportunities.append(opportunity)
            
        except Exception as e:
            logger.error("funding_scan_error", error=str(e))
        
        return opportunities
    
    async def _filter_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity]
    ) -> List[ArbitrageOpportunity]:
        """
        Filter and validate opportunities.
        
        Args:
            opportunities: Raw opportunities
            
        Returns:
            Filtered opportunities
        """
        filtered = []
        
        for opp in opportunities:
            # Check minimum profit
            if opp.expected_profit_pct < self._config["min_spread_pct"] * 100:
                continue
            
            # Check maximum spread
            if opp.spread_pct > self._config["max_spread_pct"] * 100:
                continue
            
            # Check risk score
            opp.risk_score = await self._calculate_risk_score(opp)
            if opp.risk_score > self._config["max_risk_score"]:
                continue
            
            # Check if already exists
            if any(o.type == opp.type and o.spread == opp.spread for o in filtered):
                continue
            
            # Check expiration
            if opp.expires_at is None:
                opp.expires_at = datetime.utcnow() + timedelta(
                    seconds=self._config["opportunity_ttl_seconds"]
                )
            
            filtered.append(opp)
        
        # Sort by priority and confidence
        filtered.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        
        return filtered
    
    async def _calculate_risk_score(self, opportunity: ArbitrageOpportunity) -> float:
        """Calculate risk score for an opportunity."""
        risk_score = 0.0
        
        # Execution risk
        if opportunity.type in [
            ArbitrageType.CROSS_EXCHANGE,
            ArbitrageType.CROSS_INSTRUMENT,
        ]:
            risk_score += 0.1
        
        # Timing risk
        if opportunity.type == ArbitrageType.TRIANGULAR:
            risk_score += 0.3
        
        # Slippage risk
        if opportunity.spread_pct < 0.5:
            risk_score += 0.2
        
        # Confidence risk
        if opportunity.confidence < 0.6:
            risk_score += 0.2
        
        # Market conditions risk
        if self.market_state:
            if self.market_state.volatility_regime == VolatilityRegime.HIGH:
                risk_score += 0.2
        
        return min(1.0, risk_score)
    
    async def _execute_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
        """
        if opportunity.status != ArbitrageStatus.DETECTED:
            return
        
        with self._lock:
            opportunity.status = ArbitrageStatus.EXECUTING
        
        execution = ArbitrageExecution(
            opportunity_id=opportunity.opportunity_id,
            type=opportunity.type,
            style=ExecutionStyle.SMART,
        )
        self._executions[execution.execution_id] = execution
        
        try:
            # Calculate optimal execution
            if self._config["parallel_execution"]:
                # Execute all legs in parallel
                await self._execute_legs_parallel(opportunity, execution)
            else:
                # Execute legs sequentially with hedging
                await self._execute_legs_sequential(opportunity, execution)
            
            # Execute hedge legs
            await self._execute_hedge_legs(opportunity, execution)
            
            # Update execution status
            execution.completed_at = datetime.utcnow()
            execution.status = ArbitrageStatus.COMPLETED
            execution.success = True
            
            # Calculate results
            execution.gross_profit = opportunity.expected_profit
            execution.net_profit = opportunity.expected_profit - execution.fees_paid
            
            # Update opportunity
            opportunity.status = ArbitrageStatus.COMPLETED
            opportunity.executed_at = datetime.utcnow()
            opportunity.realized_profit = execution.net_profit
            
            # Update stats
            self._stats["opportunities_executed"] += 1
            self._stats["total_profit"] += execution.net_profit
            
            logger.info(
                "arbitrage_execution_completed",
                opportunity_id=opportunity.opportunity_id,
                profit=execution.net_profit,
                execution_time_ms=execution.execution_time_ms,
            )
            
        except Exception as e:
            execution.status = ArbitrageStatus.FAILED
            execution.errors.append({"error": str(e), "timestamp": datetime.utcnow().isoformat()})
            
            opportunity.status = ArbitrageStatus.FAILED
            
            self._stats["opportunities_failed"] += 1
            
            logger.error(
                "arbitrage_execution_failed",
                opportunity_id=opportunity.opportunity_id,
                error=str(e),
                traceback=traceback.format_exc(),
            )
        
        self._execution_history.append(execution)
        
        # Remove from active
        if opportunity.opportunity_id in self._active_opportunities:
            del self._active_opportunities[opportunity.opportunity_id]
    
    async def _execute_legs_parallel(
        self,
        opportunity: ArbitrageOpportunity,
        execution: ArbitrageExecution,
    ) -> None:
        """Execute all legs in parallel."""
        tasks = []
        for leg in opportunity.legs:
            task = asyncio.create_task(self._execute_leg(leg, opportunity))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                raise result
    
    async def _execute_legs_sequential(
        self,
        opportunity: ArbitrageOpportunity,
        execution: ArbitrageExecution,
    ) -> None:
        """Execute legs sequentially with hedging."""
        for leg in opportunity.legs:
            await self._execute_leg(leg, opportunity)
    
    async def _execute_leg(self, leg: Dict[str, Any], opportunity: ArbitrageOpportunity) -> None:
        """Execute a single arbitrage leg."""
        try:
            exchange = leg.get("exchange")
            instrument = leg.get("instrument")
            side = leg.get("side")
            size = leg.get("size", self._config.get("position_size", 1000))
            
            if not exchange or not instrument:
                raise ValueError("Missing exchange or instrument")
            
            # Get connector
            connector = self.exchange_connectors.get(exchange)
            if not connector:
                raise ValueError(f"Exchange connector not found: {exchange}")
            
            # Place order
            order = await connector.place_order(
                symbol=instrument,
                side=side,
                size=size,
                order_type="MARKET",
            )
            
            leg["order"] = order
            
            logger.info(
                "arbitrage_leg_executed",
                opportunity_id=opportunity.opportunity_id,
                exchange=exchange,
                instrument=instrument,
                side=side,
                size=size,
                order_id=order.get("order_id"),
            )
            
        except Exception as e:
            logger.error(
                "arbitrage_leg_failed",
                opportunity_id=opportunity.opportunity_id,
                leg=leg,
                error=str(e),
            )
            raise
    
    async def _execute_hedge_legs(
        self,
        opportunity: ArbitrageOpportunity,
        execution: ArbitrageExecution,
    ) -> None:
        """Execute hedge legs to maintain hedged position."""
        hedge_ratio = self._config["hedge_ratio"]
        
        for leg in opportunity.legs:
            hedge_leg = {
                "instrument": leg.get("instrument"),
                "exchange": leg.get("exchange"),
                "side": "SELL" if leg.get("side") == "BUY" else "BUY",
                "size": leg.get("size", 0) * hedge_ratio,
                "hedge": True,
            }
            
            try:
                connector = self.exchange_connectors.get(hedge_leg["exchange"])
                if connector:
                    order = await connector.place_order(
                        symbol=hedge_leg["instrument"],
                        side=hedge_leg["side"],
                        size=hedge_leg["size"],
                        order_type="LIMIT",
                        price=leg.get("price", 0) * (1 - 0.001),  # Slight advantage
                    )
                    hedge_leg["order"] = order
                    execution.hedge_orders.append(order)
            except Exception as e:
                logger.warning(
                    "hedge_leg_failed",
                    opportunity_id=opportunity.opportunity_id,
                    hedge_leg=hedge_leg,
                    error=str(e),
                )
    
    async def _cleanup_expired_opportunities(self) -> None:
        """Clean up expired opportunities."""
        now = datetime.utcnow()
        expired = []
        
        for opp_id, opp in self._active_opportunities.items():
            if opp.expires_at and opp.expires_at < now:
                opp.status = ArbitrageStatus.EXPIRED
                expired.append(opp_id)
        
        for opp_id in expired:
            del self._active_opportunities[opp_id]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        return {
            "opportunities_detected": self._stats["opportunities_detected"],
            "opportunities_executed": self._stats["opportunities_executed"],
            "opportunities_failed": self._stats["opportunities_failed"],
            "success_rate": self._stats["success_rate"],
            "total_profit": self._stats["total_profit"],
            "total_fees": self._stats["total_fees"],
            "active_opportunities": len(self._active_opportunities),
            "execution_history": len(self._execution_history),
            "config": self._config,
        }
    
    def get_opportunities(self) -> List[Dict[str, Any]]:
        """Get all active opportunities."""
        return [opp.to_dict() for opp in self._active_opportunities.values()]
    
    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("arbitrage_hedge_strategy_started")
    
    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("arbitrage_hedge_strategy_stopped")
    
    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("arbitrage_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "ArbitrageHedgeStrategy",
    "ArbitrageOpportunity",
    "ArbitrageExecution",
    "ArbitrageType",
    "ArbitrageStatus",
    "ExecutionStyle",
]

logger.info("arbitrage_hedge_module_loaded", version="3.0.0")
