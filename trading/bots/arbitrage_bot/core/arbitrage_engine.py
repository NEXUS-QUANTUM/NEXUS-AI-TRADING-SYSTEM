#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Arbitrage Engine
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced arbitrage engine supporting multiple arbitrage strategies:
- Cross-exchange arbitrage (spot and futures)
- Triangular arbitrage
- Statistical arbitrage
- DeFi arbitrage (flash loans)
- Cross-chain arbitrage
- Futures-spot arbitrage (basis trading)
- Options arbitrage (put-call parity)
- ETF arbitrage
- Statistical arbitrage with cointegration

Author: Dr X...
Version: 3.0.0
"""

import asyncio
import json
import logging
import math
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, 
    Union, TypeVar, Generic, AsyncIterator, Coroutine,
    DefaultDict, Deque, Literal, overload
)
from dataclasses import dataclass, field
import numpy as np
from decimal import Decimal, getcontext

# Set decimal precision
getcontext().prec = 28

# ============================================================================
# ENUMS & TYPES
# ============================================================================

class ArbitrageType(str, Enum):
    """Types of arbitrage strategies."""
    CROSS_EXCHANGE = "cross_exchange"
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    DEFI_FLASH_LOAN = "defi_flash_loan"
    CROSS_CHAIN = "cross_chain"
    FUTURES_SPOT = "futures_spot"
    OPTIONS = "options"
    ETF = "etf"
    COINTEGRATION = "cointegration"
    MIXED = "mixed"


class ArbitrageStatus(str, Enum):
    """Status of arbitrage opportunity."""
    IDLE = "idle"
    DETECTED = "detected"
    ANALYZING = "analyzing"
    CONFIRMED = "confirmed"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PARTIALLY_COMPLETED = "partially_completed"


class ExecutionStrategy(str, Enum):
    """Execution strategies for arbitrage."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ATOMIC = "atomic"
    BATCH = "batch"
    ADAPTIVE = "adaptive"
    SMART = "smart"


class RiskLevel(str, Enum):
    """Risk levels for arbitrage."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity representation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ArbitrageType = ArbitrageType.CROSS_EXCHANGE
    pair: str = ""
    symbol: str = ""
    profit_percentage: float = 0.0
    profit_absolute: float = 0.0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0
    execution_cost: float = 0.0
    total_cost: float = 0.0
    expected_profit: float = 0.0
    confidence_score: float = 0.0
    risk_score: float = 0.0
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: ArbitrageStatus = ArbitrageStatus.DETECTED
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    execution_strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    steps: List[Dict[str, Any]] = field(default_factory=list)
    legs: List[Dict[str, Any]] = field(default_factory=list)
    route: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived fields."""
        self.net_profit = self.gross_profit - self.fees - self.slippage - self.execution_cost
        self.total_cost = self.fees + self.slippage + self.execution_cost
        if self.gross_profit > 0:
            self.profit_percentage = (self.net_profit / self.gross_profit) * 100
        
        # Calculate confidence based on various factors
        self.confidence_score = self._calculate_confidence()
        
        # Set expiration if not set
        if self.expires_at is None:
            self.expires_at = self.timestamp + timedelta(seconds=30)
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence score."""
        factors = []
        
        # Profitability factor
        if self.net_profit > 0:
            profit_factor = min(1.0, self.net_profit / (self.gross_profit * 0.1))
            factors.append(profit_factor * 0.3)
        
        # Risk factor
        risk_factor = 1.0 - (self.risk_score / 100)
        factors.append(risk_factor * 0.25)
        
        # Slippage factor
        slippage_factor = max(0, 1.0 - (self.slippage / self.gross_profit))
        factors.append(slippage_factor * 0.2)
        
        # Fee factor
        fee_factor = max(0, 1.0 - (self.fees / self.gross_profit))
        factors.append(fee_factor * 0.15)
        
        # Timing factor (if within 10 seconds of detection)
        time_diff = (datetime.utcnow() - self.timestamp).total_seconds()
        timing_factor = max(0, 1.0 - (time_diff / 30))
        factors.append(timing_factor * 0.1)
        
        return sum(factors)
    
    def is_expired(self) -> bool:
        """Check if opportunity has expired."""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "pair": self.pair,
            "symbol": self.symbol,
            "profit_percentage": self.profit_percentage,
            "profit_absolute": self.profit_absolute,
            "net_profit": self.net_profit,
            "gross_profit": self.gross_profit,
            "fees": self.fees,
            "slippage": self.slippage,
            "execution_cost": self.execution_cost,
            "total_cost": self.total_cost,
            "expected_profit": self.expected_profit,
            "confidence_score": self.confidence_score,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "execution_strategy": self.execution_strategy.value,
            "steps": self.steps,
            "legs": self.legs,
            "route": self.route,
            "metadata": self.metadata,
        }


@dataclass
class MarketData:
    """Market data for arbitrage."""
    exchange: str
    symbol: str
    bid: float
    ask: float
    bid_volume: float
    ask_volume: float
    last_price: float
    volume: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    depth: Optional[Dict[str, List[Tuple[float, float]]]] = None
    funding_rate: Optional[float] = None
    open_interest: Optional[float] = None
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_spread(self) -> float:
        """Get bid-ask spread."""
        return self.ask - self.bid
    
    def get_mid_price(self) -> float:
        """Get mid price."""
        return (self.bid + self.ask) / 2
    
    def get_spread_pct(self) -> float:
        """Get spread percentage."""
        if self.ask > 0:
            return ((self.ask - self.bid) / self.ask) * 100
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "bid": self.bid,
            "ask": self.ask,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "last_price": self.last_price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "spread": self.get_spread(),
            "mid_price": self.get_mid_price(),
            "funding_rate": self.funding_rate,
            "open_interest": self.open_interest,
            "mark_price": self.mark_price,
            "index_price": self.index_price,
        }


@dataclass
class ArbitrageExecution:
    """Arbitrage execution details."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    status: ArbitrageStatus = ArbitrageStatus.EXECUTING
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_profit: float = 0.0
    total_cost: float = 0.0
    gas_fees: float = 0.0
    exchange_fees: float = 0.0
    execution_orders: List[Dict[str, Any]] = field(default_factory=list)
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_profit": self.total_profit,
            "total_cost": self.total_cost,
            "gas_fees": self.gas_fees,
            "exchange_fees": self.exchange_fees,
            "execution_orders": self.execution_orders,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "retry_count": self.retry_count,
        }


# ============================================================================
# ARBITRAGE ENGINE
# ============================================================================

class ArbitrageEngine:
    """
    Advanced arbitrage engine for detecting and executing arbitrage opportunities.
    
    Features:
    - Cross-exchange arbitrage (spot, futures, options)
    - Triangular arbitrage (crypto, forex)
    - Statistical arbitrage (cointegration, pairs trading)
    - DeFi arbitrage (flash loans, DEX arbitrage)
    - Cross-chain arbitrage (bridges, cross-chain DEX)
    - Futures-spot arbitrage (basis trading, funding rate)
    - Options arbitrage (put-call parity, volatility)
    - ETF arbitrage (creation/redemption)
    - Real-time market data processing
    - Opportunity detection with confidence scoring
    - Risk management and position sizing
    - Atomic execution with fallback strategies
    - Performance metrics and analytics
    """
    
    def __init__(
        self,
        name: str = "ArbitrageEngine",
        exchanges: Optional[List] = None,
        config: Optional[Dict[str, Any]] = None,
        risk_manager: Optional[Any] = None,
        order_manager: Optional[Any] = None,
        data_provider: Optional[Any] = None,
        redis_client: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize the arbitrage engine.
        
        Args:
            name: Engine name
            exchanges: List of exchange connections
            config: Configuration dictionary
            risk_manager: Risk manager instance
            order_manager: Order manager instance
            data_provider: Data provider instance
            redis_client: Redis client for caching
            **kwargs: Additional arguments
        """
        self.name = name
        self.exchanges = exchanges or []
        self.config = config or self._default_config()
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.data_provider = data_provider
        self.redis_client = redis_client
        
        # Internal state
        self._running = False
        self._market_data: Dict[str, Dict[str, MarketData]] = defaultdict(dict)
        self._opportunities: Dict[str, ArbitrageOpportunity] = {}
        self._executions: Dict[str, ArbitrageExecution] = {}
        self._historical_data: deque = deque(maxlen=10000)
        
        # Worker tasks
        self._workers: List[asyncio.Task] = []
        self._detector_task: Optional[asyncio.Task] = None
        self._executor_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Queues
        self._opportunity_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._execution_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Statistics
        self._stats = {
            "opportunities_detected": 0,
            "opportunities_executed": 0,
            "opportunities_failed": 0,
            "total_profit": 0.0,
            "success_rate": 0.0,
            "avg_profit_pct": 0.0,
            "total_trades": 0,
            "execution_time_avg": 0.0,
        }
        
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger(f"{__name__}.{self.name}")
        
        self._setup_handlers()
        self._setup_strategies()
        self._setup_data_sources()
        
        self._logger.info(f"ArbitrageEngine initialized: {self.name}")
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "min_profit_percentage": 0.5,
            "min_absolute_profit": 10.0,
            "max_risk_per_trade": 1000.0,
            "max_position_size": 10000.0,
            "max_slippage_percentage": 1.0,
            "max_execution_time_seconds": 30,
            "max_retries": 3,
            "retry_delay_seconds": 1.0,
            "confidence_threshold": 0.7,
            "risk_threshold": 0.5,
            "opportunity_expiry_seconds": 30,
            "execution_strategy": "adaptive",
            "detection_interval": 0.1,  # seconds
            "data_update_interval": 0.05,
            "max_opportunities_per_second": 10,
            "enable_slippage_protection": True,
            "enable_gas_optimization": True,
            "enable_fallback": True,
            "enable_metrics": True,
            "allowed_exchanges": [],
            "banned_pairs": [],
            "preferred_pairs": [],
            "strategies": {
                "cross_exchange": {"enabled": True, "min_spread": 0.1},
                "triangular": {"enabled": True, "min_profit": 0.5},
                "statistical": {"enabled": True, "z_score_threshold": 2.0},
                "futures_spot": {"enabled": True, "min_basis": 0.1},
                "defi_flash_loan": {"enabled": False, "min_profit": 100.0},
                "cross_chain": {"enabled": False, "min_profit": 50.0},
            },
            "risk": {
                "max_position_size": 10000.0,
                "max_open_positions": 5,
                "max_daily_trades": 100,
                "max_daily_loss": 1000.0,
                "drawdown_limit": 0.1,
                "correlation_limit": 0.7,
            },
            "performance": {
                "max_opportunities_per_second": 10,
                "min_opportunity_interval": 0.1,
                "execution_timeout": 30,
                "batch_size": 10,
            },
        }
    
    # ========================================================================
    # SETUP METHODS
    # ========================================================================
    
    def _setup_handlers(self) -> None:
        """Setup event handlers."""
        self._handlers = {
            "opportunity_detected": [],
            "opportunity_confirmed": [],
            "opportunity_expired": [],
            "opportunity_executed": [],
            "opportunity_failed": [],
            "execution_completed": [],
            "execution_failed": [],
            "profit_realized": [],
            "loss_realized": [],
            "error": [],
        }
    
    def _setup_strategies(self) -> None:
        """Setup arbitrage strategies."""
        self._strategies = {
            "cross_exchange": self._detect_cross_exchange,
            "triangular": self._detect_triangular,
            "statistical": self._detect_statistical,
            "futures_spot": self._detect_futures_spot,
            "defi_flash_loan": self._detect_defi_flash_loan,
            "cross_chain": self._detect_cross_chain,
        }
    
    def _setup_data_sources(self) -> None:
        """Setup data sources."""
        self._data_sources = {}
        for exchange in self.exchanges:
            if hasattr(exchange, "get_market_data"):
                self._data_sources[exchange.name] = exchange
    
    # ========================================================================
    # EXCHANGE MANAGEMENT
    # ========================================================================
    
    def add_exchange(self, exchange: Any) -> None:
        """
        Add an exchange to the engine.
        
        Args:
            exchange: Exchange instance
        """
        self.exchanges.append(exchange)
        if hasattr(exchange, "name"):
            self._data_sources[exchange.name] = exchange
        self._logger.info(f"Added exchange: {getattr(exchange, 'name', 'unknown')}")
    
    def remove_exchange(self, exchange_name: str) -> None:
        """
        Remove an exchange from the engine.
        
        Args:
            exchange_name: Name of the exchange to remove
        """
        self.exchanges = [e for e in self.exchanges if getattr(e, "name", "") != exchange_name]
        if exchange_name in self._data_sources:
            del self._data_sources[exchange_name]
        self._logger.info(f"Removed exchange: {exchange_name}")
    
    # ========================================================================
    # MARKET DATA
    # ========================================================================
    
    async def _update_market_data(self) -> None:
        """Update market data from all exchanges."""
        tasks = []
        for exchange_name, exchange in self._data_sources.items():
            if hasattr(exchange, "get_market_data"):
                task = self._fetch_market_data(exchange_name, exchange)
                tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self._logger.error(f"Error fetching market data: {result}")
    
    async def _fetch_market_data(
        self,
        exchange_name: str,
        exchange: Any
    ) -> None:
        """
        Fetch market data from an exchange.
        
        Args:
            exchange_name: Exchange name
            exchange: Exchange instance
        """
        try:
            # Get symbols
            symbols = self._get_symbols_for_exchange(exchange_name)
            
            for symbol in symbols:
                try:
                    data = await exchange.get_market_data(symbol)
                    if data:
                        self._market_data[exchange_name][symbol] = data
                except Exception as e:
                    self._logger.warning(f"Error fetching data for {symbol}: {e}")
                    
        except Exception as e:
            self._logger.error(f"Error fetching market data from {exchange_name}: {e}")
    
    def _get_symbols_for_exchange(self, exchange_name: str) -> List[str]:
        """Get symbols to monitor for an exchange."""
        # Get from config or default
        preferred = self.config.get("preferred_pairs", [])
        if preferred:
            return preferred
        
        # Get from exchange
        for exchange in self.exchanges:
            if getattr(exchange, "name", "") == exchange_name:
                if hasattr(exchange, "symbols"):
                    return exchange.symbols
        
        return []
    
    def get_market_data(
        self,
        exchange: str,
        symbol: str
    ) -> Optional[MarketData]:
        """
        Get market data for a specific exchange and symbol.
        
        Args:
            exchange: Exchange name
            symbol: Trading symbol
            
        Returns:
            Optional[MarketData]: Market data
        """
        return self._market_data.get(exchange, {}).get(symbol)
    
    # ========================================================================
    # OPPORTUNITY DETECTION
    # ========================================================================
    
    async def _detect_opportunities(self) -> None:
        """Main loop for detecting arbitrage opportunities."""
        self._logger.info("Opportunity detection started")
        
        while self._running:
            try:
                # Update market data
                await self._update_market_data()
                
                # Run detection strategies
                tasks = []
                for strategy_name, strategy_func in self._strategies.items():
                    if self.config["strategies"].get(strategy_name, {}).get("enabled", False):
                        task = self._run_detection_strategy(strategy_name, strategy_func)
                        tasks.append(task)
                
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for result in results:
                        if isinstance(result, Exception):
                            self._logger.error(f"Strategy error: {result}")
                
                # Apply rate limiting
                await asyncio.sleep(self.config["detection_interval"])
                
            except Exception as e:
                self._logger.error(f"Error in detection loop: {e}")
                await asyncio.sleep(1)
        
        self._logger.info("Opportunity detection stopped")
    
    async def _run_detection_strategy(
        self,
        strategy_name: str,
        strategy_func: Callable
    ) -> None:
        """
        Run a specific detection strategy.
        
        Args:
            strategy_name: Name of the strategy
            strategy_func: Strategy function
        """
        try:
            opportunities = await strategy_func()
            
            if opportunities:
                for opp in opportunities:
                    # Validate opportunity
                    if self._validate_opportunity(opp):
                        # Add to queue
                        try:
                            await asyncio.wait_for(
                                self._opportunity_queue.put(opp),
                                timeout=1.0
                            )
                            self._stats["opportunities_detected"] += 1
                            self._logger.info(
                                f"Opportunity detected: {opp.type.value} - "
                                f"{opp.symbol} - {opp.profit_percentage:.2f}%"
                            )
                            await self._emit_event("opportunity_detected", opp)
                        except asyncio.TimeoutError:
                            self._logger.warning("Opportunity queue full")
        
        except Exception as e:
            self._logger.error(f"Error in strategy {strategy_name}: {e}")
    
    def _validate_opportunity(self, opp: ArbitrageOpportunity) -> bool:
        """
        Validate an arbitrage opportunity.
        
        Args:
            opp: Arbitrage opportunity
            
        Returns:
            bool: True if valid
        """
        # Check if expired
        if opp.is_expired():
            return False
        
        # Check minimum profit
        if opp.net_profit < self.config["min_absolute_profit"]:
            return False
        
        if opp.profit_percentage < self.config["min_profit_percentage"]:
            return False
        
        # Check confidence
        if opp.confidence_score < self.config["confidence_threshold"]:
            return False
        
        # Check risk
        if opp.risk_score > self.config["risk_threshold"]:
            return False
        
        # Check position size
        if opp.expected_profit > self.config["max_position_size"]:
            return False
        
        # Check if symbol is banned
        if opp.symbol in self.config["banned_pairs"]:
            return False
        
        # Check exchange limits
        if self.config["allowed_exchanges"]:
            for step in opp.steps:
                exchange = step.get("exchange")
                if exchange not in self.config["allowed_exchanges"]:
                    return False
        
        return True
    
    # ========================================================================
    # DETECTION STRATEGIES
    # ========================================================================
    
    async def _detect_cross_exchange(self) -> List[ArbitrageOpportunity]:
        """
        Detect cross-exchange arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        opportunities = []
        
        # Get symbols to compare
        symbols = self._get_common_symbols()
        
        for symbol in symbols:
            # Get prices from all exchanges
            prices = {}
            volumes = {}
            
            for exchange_name, data in self._market_data.items():
                if symbol in data:
                    market_data = data[symbol]
                    prices[exchange_name] = {
                        "bid": market_data.bid,
                        "ask": market_data.ask,
                        "mid": market_data.get_mid_price(),
                    }
                    volumes[exchange_name] = {
                        "bid": market_data.bid_volume,
                        "ask": market_data.ask_volume,
                    }
            
            if len(prices) < 2:
                continue
            
            # Find best bid and ask
            best_bid = max(
                [(ex, p["bid"]) for ex, p in prices.items()],
                key=lambda x: x[1] if x[1] > 0 else -float("inf")
            )
            best_ask = min(
                [(ex, p["ask"]) for ex, p in prices.items()],
                key=lambda x: x[1] if x[1] > 0 else float("inf")
            )
            
            if best_bid[1] <= 0 or best_ask[1] <= 0:
                continue
            
            # Calculate profit
            profit_pct = ((best_bid[1] - best_ask[1]) / best_ask[1]) * 100
            
            # Check if profitable
            if profit_pct < self.config["strategies"]["cross_exchange"]["min_spread"]:
                continue
            
            # Calculate fees
            fees = self._estimate_fees(best_bid[0], best_ask[0], profit_pct)
            
            # Create opportunity
            opp = ArbitrageOpportunity(
                type=ArbitrageType.CROSS_EXCHANGE,
                pair=symbol,
                symbol=symbol,
                gross_profit=best_bid[1] - best_ask[1],
                fees=fees,
                slippage=0.01,  # Estimate
                execution_cost=0.001,
                risk_level=self._calculate_risk_level(profit_pct, len(prices)),
                steps=[
                    {"exchange": best_ask[0], "action": "buy", "price": best_ask[1]},
                    {"exchange": best_bid[0], "action": "sell", "price": best_bid[1]},
                ],
                metadata={
                    "best_bid_exchange": best_bid[0],
                    "best_ask_exchange": best_ask[0],
                    "price_diff": best_bid[1] - best_ask[1],
                    "exchanges_compared": len(prices),
                }
            )
            
            opportunities.append(opp)
        
        return opportunities
    
    async def _detect_triangular(self) -> List[ArbitrageOpportunity]:
        """
        Detect triangular arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        opportunities = []
        
        # Get currency pairs
        pairs = self._get_currency_pairs()
        
        # Find triangular cycles
        cycles = self._find_triangular_cycles(pairs)
        
        for cycle in cycles:
            profit = self._calculate_triangular_profit(cycle)
            
            if profit > 0:
                opp = ArbitrageOpportunity(
                    type=ArbitrageType.TRIANGULAR,
                    pair=f"{cycle[0]}/{cycle[1]}/{cycle[2]}",
                    symbol=f"{cycle[0]}/{cycle[1]}/{cycle[2]}",
                    gross_profit=profit,
                    fees=self._estimate_fees(None, None, profit * 100),
                    slippage=0.005,
                    execution_cost=0.001,
                    risk_level=RiskLevel.MEDIUM,
                    steps=[
                        {"exchange": "exchange1", "action": "trade", "pair": cycle[0]},
                        {"exchange": "exchange1", "action": "trade", "pair": cycle[1]},
                        {"exchange": "exchange1", "action": "trade", "pair": cycle[2]},
                    ],
                    metadata={
                        "cycle": cycle,
                        "profit_calculated": profit,
                    }
                )
                opportunities.append(opp)
        
        return opportunities
    
    async def _detect_statistical(self) -> List[ArbitrageOpportunity]:
        """
        Detect statistical arbitrage opportunities using cointegration.
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        opportunities = []
        
        # Get historical data
        historical_data = self._get_historical_data()
        
        # Find cointegrated pairs
        pairs = self._find_cointegrated_pairs(historical_data)
        
        for pair in pairs:
            # Calculate z-score
            z_score = self._calculate_z_score(pair)
            
            # Check if trade signal
            if abs(z_score) > self.config["strategies"]["statistical"]["z_score_threshold"]:
                opp = ArbitrageOpportunity(
                    type=ArbitrageType.STATISTICAL,
                    pair=pair["symbol1"] + "/" + pair["symbol2"],
                    symbol=pair["symbol1"],
                    gross_profit=pair["expected_profit"],
                    fees=self._estimate_fees(None, None, 0.5),
                    slippage=0.01,
                    execution_cost=0.001,
                    risk_level=RiskLevel.MEDIUM,
                    metadata={
                        "z_score": z_score,
                        "cointegration": pair["cointegration"],
                        "hedge_ratio": pair["hedge_ratio"],
                    }
                )
                opportunities.append(opp)
        
        return opportunities
    
    async def _detect_futures_spot(self) -> List[ArbitrageOpportunity]:
        """
        Detect futures-spot arbitrage opportunities (basis trading).
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        opportunities = []
        
        # Get futures and spot prices
        for symbol in self._get_futures_symbols():
            spot_price = self._get_spot_price(symbol)
            futures_price = self._get_futures_price(symbol)
            
            if spot_price and futures_price:
                basis = (futures_price - spot_price) / spot_price * 100
                
                if basis > self.config["strategies"]["futures_spot"]["min_basis"]:
                    opp = ArbitrageOpportunity(
                        type=ArbitrageType.FUTURES_SPOT,
                        pair=symbol,
                        symbol=symbol,
                        gross_profit=futures_price - spot_price,
                        fees=self._estimate_fees(None, None, basis),
                        slippage=0.005,
                        execution_cost=0.001,
                        risk_level=RiskLevel.LOW,
                        steps=[
                            {"exchange": "spot", "action": "buy", "price": spot_price},
                            {"exchange": "futures", "action": "sell", "price": futures_price},
                        ],
                        metadata={
                            "basis": basis,
                            "spot_price": spot_price,
                            "futures_price": futures_price,
                            "funding_rate": self._get_funding_rate(symbol),
                        }
                    )
                    opportunities.append(opp)
        
        return opportunities
    
    async def _detect_defi_flash_loan(self) -> List[ArbitrageOpportunity]:
        """
        Detect DeFi flash loan arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        # This would interact with DeFi protocols
        # Placeholder for advanced implementation
        return []
    
    async def _detect_cross_chain(self) -> List[ArbitrageOpportunity]:
        """
        Detect cross-chain arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: List of opportunities
        """
        # This would interact with cross-chain bridges
        # Placeholder for advanced implementation
        return []
    
    # ========================================================================
    # HELPER METHODS FOR DETECTION
    # ========================================================================
    
    def _get_common_symbols(self) -> List[str]:
        """Get symbols available on all exchanges."""
        if not self._market_data:
            return []
        
        # Get symbols from first exchange
        first_exchange = next(iter(self._market_data.values()))
        symbols = set(first_exchange.keys())
        
        # Intersect with other exchanges
        for exchange_data in self._market_data.values():
            symbols &= set(exchange_data.keys())
        
        return list(symbols)
    
    def _get_currency_pairs(self) -> List[Tuple[str, str]]:
        """Get currency pairs for triangular arbitrage."""
        # This is a simplified version
        currencies = ["BTC", "ETH", "USDT", "BNB", "ADA", "XRP", "SOL", "DOT"]
        pairs = []
        for i, c1 in enumerate(currencies):
            for c2 in currencies[i+1:]:
                pairs.append((c1, c2))
        return pairs
    
    def _find_triangular_cycles(
        self,
        pairs: List[Tuple[str, str]]
    ) -> List[List[str]]:
        """Find triangular cycles in currency pairs."""
        # Simplified cycle detection
        cycles = []
        currencies = set()
        for c1, c2 in pairs:
            currencies.add(c1)
            currencies.add(c2)
        
        currencies = list(currencies)
        for i in range(len(currencies)):
            for j in range(i+1, len(currencies)):
                for k in range(j+1, len(currencies)):
                    cycles.append([currencies[i], currencies[j], currencies[k]])
        
        return cycles
    
    def _calculate_triangular_profit(self, cycle: List[str]) -> float:
        """
        Calculate profit from a triangular cycle.
        
        Args:
            cycle: List of currencies in the cycle
            
        Returns:
            float: Expected profit
        """
        # Simplified profit calculation
        return 0.01  # Placeholder
    
    def _get_historical_data(self) -> Dict[str, List[float]]:
        """Get historical price data for statistical arbitrage."""
        # This would fetch historical data from storage
        return {}  # Placeholder
    
    def _find_cointegrated_pairs(
        self,
        data: Dict[str, List[float]]
    ) -> List[Dict[str, Any]]:
        """Find cointegrated pairs for statistical arbitrage."""
        # This would use statistical tests for cointegration
        return []  # Placeholder
    
    def _calculate_z_score(self, pair: Dict[str, Any]) -> float:
        """
        Calculate z-score for a cointegrated pair.
        
        Args:
            pair: Pair information
            
        Returns:
            float: Z-score
        """
        return 0.0  # Placeholder
    
    def _get_futures_symbols(self) -> List[str]:
        """Get futures symbols for basis arbitrage."""
        return []
    
    def _get_spot_price(self, symbol: str) -> Optional[float]:
        """Get spot price for a symbol."""
        for exchange_data in self._market_data.values():
            if symbol in exchange_data:
                return exchange_data[symbol].bid
        return None
    
    def _get_futures_price(self, symbol: str) -> Optional[float]:
        """Get futures price for a symbol."""
        # This would get futures prices from futures exchanges
        return None
    
    def _get_funding_rate(self, symbol: str) -> Optional[float]:
        """Get funding rate for a futures symbol."""
        return None
    
    def _estimate_fees(
        self,
        exchange1: Optional[str],
        exchange2: Optional[str],
        profit_pct: float
    ) -> float:
        """
        Estimate fees for arbitrage.
        
        Args:
            exchange1: First exchange
            exchange2: Second exchange
            profit_pct: Profit percentage
            
        Returns:
            float: Estimated fees
        """
        # Base fee estimate
        base_fee = 0.001  # 0.1%
        
        # Add exchange-specific fees
        if exchange1 and exchange1 in self._data_sources:
            base_fee += 0.0005
        
        if exchange2 and exchange2 in self._data_sources:
            base_fee += 0.0005
        
        # Scale with profit
        fee_adjustment = min(0.005, profit_pct * 0.1)
        
        return base_fee + fee_adjustment
    
    def _calculate_risk_level(self, profit_pct: float, num_exchanges: int) -> RiskLevel:
        """
        Calculate risk level for an opportunity.
        
        Args:
            profit_pct: Profit percentage
            num_exchanges: Number of exchanges involved
            
        Returns:
            RiskLevel: Risk level
        """
        if profit_pct > 10:
            return RiskLevel.EXTREME
        elif profit_pct > 5:
            return RiskLevel.HIGH
        elif profit_pct > 2:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    # ========================================================================
    # EXECUTION ENGINE
    # ========================================================================
    
    async def _execute_opportunities(self) -> None:
        """Main loop for executing arbitrage opportunities."""
        self._logger.info("Execution engine started")
        
        while self._running:
            try:
                # Get opportunity from queue
                try:
                    opportunity = await asyncio.wait_for(
                        self._opportunity_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Execute opportunity
                execution = await self._execute_opportunity(opportunity)
                
                if execution and execution.status == ArbitrageStatus.COMPLETED:
                    self._stats["opportunities_executed"] += 1
                    self._stats["total_profit"] += execution.total_profit
                    self._stats["total_trades"] += len(execution.execution_orders)
                    await self._emit_event("opportunity_executed", execution)
                else:
                    self._stats["opportunities_failed"] += 1
                    await self._emit_event("opportunity_failed", execution)
                
                self._opportunity_queue.task_done()
                
            except Exception as e:
                self._logger.error(f"Error in execution loop: {e}")
                await asyncio.sleep(1)
        
        self._logger.info("Execution engine stopped")
    
    async def _execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Optional[ArbitrageExecution]:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Optional[ArbitrageExecution]: Execution details
        """
        execution = ArbitrageExecution(
            opportunity_id=opportunity.id,
            metadata={"opportunity": opportunity.to_dict()}
        )
        
        self._executions[execution.id] = execution
        
        try:
            # Check if still valid
            if opportunity.is_expired():
                execution.status = ArbitrageStatus.EXPIRED
                execution.error = "Opportunity expired"
                return execution
            
            # Update status
            opportunity.status = ArbitrageStatus.EXECUTING
            
            # Execute based on strategy
            if opportunity.execution_strategy == ExecutionStrategy.PARALLEL:
                result = await self._execute_parallel(opportunity)
            elif opportunity.execution_strategy == ExecutionStrategy.ATOMIC:
                result = await self._execute_atomic(opportunity)
            elif opportunity.execution_strategy == ExecutionStrategy.BATCH:
                result = await self._execute_batch(opportunity)
            else:
                result = await self._execute_sequential(opportunity)
            
            # Update execution
            if result["success"]:
                execution.status = ArbitrageStatus.COMPLETED
                execution.total_profit = result.get("profit", 0)
                execution.total_cost = result.get("cost", 0)
                execution.execution_orders = result.get("orders", [])
                opportunity.status = ArbitrageStatus.COMPLETED
                
                # Update statistics
                self._update_statistics(execution)
            else:
                execution.status = ArbitrageStatus.FAILED
                execution.error = result.get("error", "Unknown error")
                opportunity.status = ArbitrageStatus.FAILED
            
            execution.end_time = datetime.utcnow()
            execution.execution_time_ms = (
                (execution.end_time - execution.start_time).total_seconds() * 1000
            )
            
            # Emit event
            await self._emit_event("execution_completed", execution)
            
            return execution
            
        except Exception as e:
            self._logger.error(f"Error executing opportunity {opportunity.id}: {e}")
            execution.status = ArbitrageStatus.FAILED
            execution.error = str(e)
            execution.end_time = datetime.utcnow()
            opportunity.status = ArbitrageStatus.FAILED
            return execution
    
    async def _execute_sequential(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Execute arbitrage sequentially.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Dict[str, Any]: Execution result
        """
        orders = []
        total_profit = opportunity.net_profit
        
        for step in opportunity.steps:
            try:
                order = await self._execute_step(step, opportunity)
                orders.append(order)
                
                if order.get("status") != "completed":
                    return {
                        "success": False,
                        "error": f"Step failed: {order.get('error', 'Unknown error')}",
                        "orders": orders,
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "orders": orders,
                }
        
        return {
            "success": True,
            "profit": total_profit,
            "cost": opportunity.total_cost,
            "orders": orders,
        }
    
    async def _execute_parallel(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Execute arbitrage in parallel.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Dict[str, Any]: Execution result
        """
        tasks = []
        for step in opportunity.steps:
            task = self._execute_step(step, opportunity)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        orders = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                return {
                    "success": False,
                    "error": str(result),
                    "orders": orders,
                }
            orders.append(result)
            if result.get("status") != "completed":
                return {
                    "success": False,
                    "error": f"Step {i} failed: {result.get('error', 'Unknown error')}",
                    "orders": orders,
                }
        
        return {
            "success": True,
            "profit": opportunity.net_profit,
            "cost": opportunity.total_cost,
            "orders": orders,
        }
    
    async def _execute_atomic(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Execute arbitrage atomically (all or nothing).
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Dict[str, Any]: Execution result
        """
        # This would use atomic swaps or flash loans
        # For now, use sequential with rollback
        result = await self._execute_sequential(opportunity)
        
        if not result["success"]:
            # Rollback any partial executions
            await self._rollback_execution(result.get("orders", []))
        
        return result
    
    async def _execute_batch(
        self,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Execute arbitrage in batches.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            Dict[str, Any]: Execution result
        """
        # Split into smaller batches
        batch_size = self.config["performance"].get("batch_size", 10)
        total_profit = 0
        total_cost = 0
        all_orders = []
        
        for i in range(0, len(opportunity.steps), batch_size):
            batch = opportunity.steps[i:i+batch_size]
            
            # Execute batch
            for step in batch:
                order = await self._execute_step(step, opportunity)
                all_orders.append(order)
                
                if order.get("status") != "completed":
                    return {
                        "success": False,
                        "error": f"Batch step failed: {order.get('error', 'Unknown error')}",
                        "orders": all_orders,
                    }
            
            # Update progress
            total_profit += opportunity.net_profit * (len(batch) / len(opportunity.steps))
            total_cost += opportunity.total_cost * (len(batch) / len(opportunity.steps))
        
        return {
            "success": True,
            "profit": total_profit,
            "cost": total_cost,
            "orders": all_orders,
        }
    
    async def _execute_step(
        self,
        step: Dict[str, Any],
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, Any]:
        """
        Execute a single step of an arbitrage opportunity.
        
        Args:
            step: Step configuration
            opportunity: Arbitrage opportunity
            
        Returns:
            Dict[str, Any]: Step execution result
        """
        try:
            exchange = step.get("exchange")
            action = step.get("action")
            price = step.get("price")
            quantity = opportunity.expected_profit / price if price else 0
            
            # Find exchange instance
            exchange_instance = None
            for ex in self.exchanges:
                if getattr(ex, "name", "") == exchange:
                    exchange_instance = ex
                    break
            
            if not exchange_instance:
                return {"status": "failed", "error": f"Exchange {exchange} not found"}
            
            # Execute order
            if action == "buy":
                order = await exchange_instance.place_order(
                    symbol=opportunity.symbol,
                    side="buy",
                    order_type="limit",
                    quantity=quantity,
                    price=price
                )
            elif action == "sell":
                order = await exchange_instance.place_order(
                    symbol=opportunity.symbol,
                    side="sell",
                    order_type="limit",
                    quantity=quantity,
                    price=price
                )
            else:
                return {"status": "failed", "error": f"Unknown action: {action}"}
            
            return {
                "status": "completed",
                "order_id": order.get("id"),
                "order": order,
                "exchange": exchange,
                "action": action,
                "price": price,
                "quantity": quantity,
            }
            
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    async def _rollback_execution(self, orders: List[Dict[str, Any]]) -> None:
        """
        Rollback an execution.
        
        Args:
            orders: List of executed orders
        """
        for order in orders:
            try:
                exchange = order.get("exchange")
                order_id = order.get("order_id")
                
                if exchange and order_id:
                    exchange_instance = None
                    for ex in self.exchanges:
                        if getattr(ex, "name", "") == exchange:
                            exchange_instance = ex
                            break
                    
                    if exchange_instance:
                        await exchange_instance.cancel_order(order_id)
            except Exception as e:
                self._logger.error(f"Error rolling back order {order}: {e}")
    
    # ========================================================================
    # MONITORING & CLEANUP
    # ========================================================================
    
    async def _monitor_engine(self) -> None:
        """Monitor engine performance and health."""
        self._logger.info("Monitor started")
        
        while self._running:
            try:
                # Update statistics
                total_opp = self._stats["opportunities_detected"]
                executed = self._stats["opportunities_executed"]
                failed = self._stats["opportunities_failed"]
                
                if total_opp > 0:
                    self._stats["success_rate"] = (executed / total_opp) * 100
                
                # Log status
                self._logger.debug(
                    f"Status: Detected={total_opp}, "
                    f"Executed={executed}, Failed={failed}, "
                    f"Success Rate={self._stats['success_rate']:.1f}%, "
                    f"Total Profit=${self._stats['total_profit']:.2f}"
                )
                
                await asyncio.sleep(5)
                
            except Exception as e:
                self._logger.error(f"Monitor error: {e}")
                await asyncio.sleep(5)
        
        self._logger.info("Monitor stopped")
    
    async def _cleanup(self) -> None:
        """Clean up expired opportunities and resources."""
        self._logger.info("Cleanup started")
        
        while self._running:
            try:
                # Clean up expired opportunities
                expired = [k for k, v in self._opportunities.items() if v.is_expired()]
                for key in expired:
                    self._opportunities.pop(key, None)
                    self._logger.debug(f"Removed expired opportunity: {key}")
                
                # Clean up old executions
                old_executions = [
                    k for k, v in self._executions.items()
                    if v.end_time and (datetime.utcnow() - v.end_time).seconds > 3600
                ]
                for key in old_executions:
                    self._executions.pop(key, None)
                
                await asyncio.sleep(60)
                
            except Exception as e:
                self._logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(60)
        
        self._logger.info("Cleanup stopped")
    
    def _update_statistics(self, execution: ArbitrageExecution) -> None:
        """Update execution statistics."""
        self._stats["total_profit"] += execution.total_profit
        
        # Update average execution time
        if execution.execution_time_ms:
            current_avg = self._stats["execution_time_avg"]
            total_exec = self._stats["opportunities_executed"]
            self._stats["execution_time_avg"] = (
                (current_avg * (total_exec - 1) + execution.execution_time_ms) / total_exec
            )
    
    # ========================================================================
    # EVENT HANDLING
    # ========================================================================
    
    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.
        
        Args:
            event: Event name
            handler: Event handler function
        """
        if event in self._handlers:
            self._handlers[event].append(handler)
    
    async def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event to registered handlers.
        
        Args:
            event: Event name
            data: Event data
        """
        if event in self._handlers:
            for handler in self._handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    self._logger.error(f"Error in event handler {event}: {e}")
    
    # ========================================================================
    # LIFE CYCLE MANAGEMENT
    # ========================================================================
    
    async def start(self) -> None:
        """Start the arbitrage engine."""
        if self._running:
            self._logger.warning("Engine already running")
            return
        
        self._running = True
        
        try:
            # Start detection
            self._detector_task = asyncio.create_task(self._detect_opportunities())
            
            # Start execution
            self._executor_task = asyncio.create_task(self._execute_opportunities())
            
            # Start monitoring
            self._monitor_task = asyncio.create_task(self._monitor_engine())
            
            # Start cleanup
            self._cleanup_task = asyncio.create_task(self._cleanup())
            
            self._logger.info(f"ArbitrageEngine {self.name} started")
            
        except Exception as e:
            self._running = False
            self._logger.error(f"Error starting engine: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the arbitrage engine."""
        if not self._running:
            self._logger.warning("Engine already stopped")
            return
        
        self._running = False
        
        try:
            # Cancel tasks
            tasks = [
                self._detector_task,
                self._executor_task,
                self._monitor_task,
                self._cleanup_task,
            ]
            
            for task in tasks:
                if task:
                    task.cancel()
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            self._logger.info(f"ArbitrageEngine {self.name} stopped")
            
        except Exception as e:
            self._logger.error(f"Error stopping engine: {e}")
            raise
    
    async def __aenter__(self) -> 'ArbitrageEngine':
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.stop()
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            **self._stats,
            "running": self._running,
            "opportunities_queued": self._opportunity_queue.qsize(),
            "executions_queued": self._execution_queue.qsize(),
            "active_opportunities": len(self._opportunities),
            "active_executions": len(self._executions),
        }
    
    def get_opportunities(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get arbitrage opportunities.
        
        Args:
            status: Filter by status (optional)
            
        Returns:
            List[Dict[str, Any]]: Opportunities
        """
        opportunities = []
        for opp in self._opportunities.values():
            if status and opp.status.value != status:
                continue
            opportunities.append(opp.to_dict())
        return opportunities
    
    def get_executions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get arbitrage executions.
        
        Args:
            status: Filter by status (optional)
            
        Returns:
            List[Dict[str, Any]]: Executions
        """
        executions = []
        for exec_obj in self._executions.values():
            if status and exec_obj.status.value != status:
                continue
            executions.append(exec_obj.to_dict())
        return executions


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_arbitrage_engine(
    name: str = "ArbitrageEngine",
    exchanges: Optional[List] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> ArbitrageEngine:
    """
    Create an arbitrage engine instance.
    
    Args:
        name: Engine name
        exchanges: List of exchange connections
        config: Configuration dictionary
        **kwargs: Additional arguments
    
    Returns:
        ArbitrageEngine: Engine instance
    """
    return ArbitrageEngine(
        name=name,
        exchanges=exchanges or [],
        config=config,
        **kwargs
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    async def main():
        """Main entry point for testing."""
        import logging
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        # Create engine
        engine = create_arbitrage_engine(
            name="TestArbitrage",
            config={
                "min_profit_percentage": 0.5,
                "min_absolute_profit": 1.0,
                "strategies": {
                    "cross_exchange": {"enabled": True, "min_spread": 0.1},
                    "triangular": {"enabled": True, "min_profit": 0.5},
                }
            }
        )
        
        # Register event handlers
        def on_opportunity(opp):
            print(f"Opportunity detected: {opp.type.value} - {opp.profit_percentage:.2f}%")
        
        def on_execution(exec_obj):
            print(f"Execution completed: {exec_obj.total_profit:.2f}")
        
        engine.on("opportunity_detected", on_opportunity)
        engine.on("execution_completed", on_execution)
        
        # Start engine
        async with engine:
            print(f"ArbitrageEngine {engine.name} running...")
            
            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                print("Shutting down...")
    
    asyncio.run(main())
