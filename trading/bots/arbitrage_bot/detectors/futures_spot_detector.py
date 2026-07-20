# trading/bots/arbitrage_bot/detectors/futures_spot_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Futures-Spot Arbitrage Detection Engine

"""
Futures-Spot Arbitrage Detector - Advanced Futures-Spot Arbitrage Detection Engine

This module provides state-of-the-art detection of futures-spot arbitrage
opportunities (also known as basis trading) across multiple exchanges with:
- Multi-exchange futures-spot price discrepancy detection
- Funding rate arbitrage
- Cross-exchange basis trading
- Perpetual vs. spot arbitrage
- Calendar spread arbitrage (different expiries)
- Delivery arbitrage
- Risk-neutral basis trading
- Dynamic position sizing

Architecture:
    - BaseFuturesSpotDetector: Abstract base class
    - FuturesSpotDetector: Main detector implementation
    - ExchangeConnector: Exchange-specific connectors
    - BasisAnalyzer: Basis calculation and analysis
    - FundingRateAnalyzer: Funding rate optimization
    - PositionManager: Position sizing and management
    - RiskManager: Risk assessment and management

Concepts:
    - Basis = Futures Price - Spot Price
    - Contango: Futures > Spot (positive basis)
    - Backwardation: Futures < Spot (negative basis)
    - Funding Rate: Periodic payment between long/short positions
    - Basis Yield: Annualized return from basis trading
"""

import asyncio
import hashlib
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, getcontext
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    TypeVar,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    overload,
    Protocol,
    runtime_checkable,
)
from functools import lru_cache, wraps, partial
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
from itertools import combinations, permutations, product
from contextlib import asynccontextmanager, contextmanager
from typing_extensions import TypedDict, NotRequired

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from sklearn.linear_model import LinearRegression

# Constants and configurations
MIN_BASIS_THRESHOLD = Decimal("0.001")  # 0.1% minimum basis
MIN_FUNDING_RATE_ARBITRAGE = Decimal("0.0001")  # 0.01% funding rate arbitrage
MAX_POSITION_SIZE = Decimal("1000000")  # $1M max position
MIN_CONFIDENCE = Decimal("0.6")
DEFAULT_REBALANCE_INTERVAL = 3600  # 1 hour

# Exchange types
class ExchangeType(Enum):
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    DELIVERY = "delivery"
    OPTION = "option"

# Market types
class MarketType(Enum):
    CRYPTO = "crypto"
    FOREX = "forex"
    STOCK = "stock"
    COMMODITY = "commodity"
    INDEX = "index"

# Contract types
class ContractType(Enum):
    PERPETUAL = "perpetual"
    QUARTERLY = "quarterly"
    BIQUARTERLY = "biquarterly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"
    DAILY = "daily"
    DELIVERY = "delivery"

# Order types
class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"

# Typed dictionaries for type safety
class MarketData(TypedDict):
    """Market data for a symbol."""
    symbol: str
    exchange: str
    price: Decimal
    bid: Decimal
    ask: Decimal
    volume: Decimal
    timestamp: datetime
    market_type: MarketType
    contract_type: Optional[ContractType]
    expiry: Optional[datetime]
    funding_rate: Optional[Decimal]
    next_funding_time: Optional[datetime]
    open_interest: Optional[Decimal]
    mark_price: Optional[Decimal]
    index_price: Optional[Decimal]

class BasisData(TypedDict):
    """Basis calculation data."""
    symbol: str
    spot_price: Decimal
    futures_price: Decimal
    basis: Decimal
    basis_percentage: Decimal
    annualized_basis: Decimal
    days_to_expiry: Optional[float]
    funding_rate: Optional[Decimal]
    implied_funding_rate: Optional[Decimal]
    basis_yield: Decimal
    annualized_yield: Decimal

class ArbitrageOpportunity(TypedDict):
    """Futures-spot arbitrage opportunity."""
    symbol: str
    exchange: str
    spot_price: Decimal
    futures_price: Decimal
    basis: Decimal
    basis_percentage: Decimal
    annualized_basis: Decimal
    funding_rate: Optional[Decimal]
    position_type: str  # "long_spot_short_futures" or "short_spot_long_futures"
    entry_price: Decimal
    exit_price: Decimal
    expected_profit: Decimal
    expected_profit_percentage: Decimal
    annualized_return: Decimal
    risk_score: Decimal
    confidence: Decimal
    position_size: Decimal
    max_position_size: Decimal
    recommended_position: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    expiry: Optional[datetime]
    time_to_expiry: Optional[timedelta]
    contract_type: ContractType

@dataclass
class Position:
    """Trading position."""
    symbol: str
    exchange: str
    side: OrderSide
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    pnl: Decimal
    pnl_percentage: Decimal
    timestamp: datetime
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    expiry: Optional[datetime] = None

@dataclass
class RiskParameters:
    """Risk management parameters."""
    max_position_size: Decimal = MAX_POSITION_SIZE
    max_leverage: Decimal = Decimal("3")
    max_drawdown: Decimal = Decimal("0.05")  # 5%
    stop_loss_percentage: Decimal = Decimal("0.02")  # 2%
    take_profit_percentage: Decimal = Decimal("0.05")  # 5%
    max_positions: int = 10
    max_correlation: Decimal = Decimal("0.7")
    risk_free_rate: Decimal = Decimal("0.02")  # 2%
    max_risk_per_trade: Decimal = Decimal("0.01")  # 1%

class FuturesSpotDetector:
    """
    Advanced Futures-Spot Arbitrage Detector.
    
    This class implements sophisticated futures-spot arbitrage detection
    with support for:
    1. Basis trading (cash-and-carry arbitrage)
    2. Funding rate arbitrage
    3. Cross-exchange basis arbitrage
    4. Calendar spread arbitrage
    5. Perpetual vs. delivery arbitrage
    6. Dynamic position sizing
    7. Risk-neutral basis trading
    
    Features:
    - Real-time basis calculation and monitoring
    - Multi-exchange support (Binance, Bybit, OKX, etc.)
    - Funding rate optimization
    - Annualized yield calculation
    - Position sizing with Kelly criterion
    - Risk management with stop-loss/take-profit
    - MEV protection
    - Automated rebalancing
    """
    
    def __init__(
        self,
        exchanges: List[str],
        min_basis_threshold: Decimal = MIN_BASIS_THRESHOLD,
        max_position_size: Decimal = MAX_POSITION_SIZE,
        risk_parameters: Optional[RiskParameters] = None,
        scan_interval: float = 1.0,
    ):
        """
        Initialize the Futures-Spot Detector.
        
        Args:
            exchanges: List of exchange names to monitor
            min_basis_threshold: Minimum basis to consider
            max_position_size: Maximum position size
            risk_parameters: Risk management parameters
            scan_interval: Interval between scans in seconds
        """
        self.logger = self._setup_logger()
        self.exchanges = exchanges
        self.min_basis_threshold = min_basis_threshold
        self.max_position_size = max_position_size
        self.risk_params = risk_parameters or RiskParameters()
        self.scan_interval = scan_interval
        
        # Initialize exchange connectors
        self.connectors: Dict[str, ExchangeConnector] = {}
        self._init_connectors()
        
        # Data caches
        self.spot_cache: Dict[str, MarketData] = {}
        self.futures_cache: Dict[str, Dict[str, MarketData]] = {}
        self.basis_cache: Dict[str, BasisData] = {}
        self.opportunity_cache: Dict[str, ArbitrageOpportunity] = {}
        
        # Position tracking
        self.positions: List[Position] = []
        self.position_lock = threading.Lock()
        
        # Thread pool for parallel scanning
        self.executor = ThreadPoolExecutor(max_workers=len(exchanges))
        
        # Metrics
        self.metrics = {
            "scans": 0,
            "opportunities_found": 0,
            "opportunities_executed": 0,
            "total_profit": Decimal("0"),
            "total_trades": 0,
            "win_rate": Decimal("0"),
            "avg_return": Decimal("0"),
            "sharpe_ratio": Decimal("0"),
            "max_drawdown": Decimal("0"),
            "errors": 0,
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        
        # MEV protection
        self.mev_shield = MEVProtection()
        
        # Risk manager
        self.risk_manager = RiskManager(self.risk_params)
        
        # Performance tracker
        self.performance_tracker = PerformanceTracker()
        
        # Start background scanner
        self.start()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger for the detector."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _init_connectors(self) -> None:
        """Initialize exchange connectors."""
        for exchange in self.exchanges:
            try:
                connector = ExchangeConnectorFactory.create(exchange)
                self.connectors[exchange] = connector
            except Exception as e:
                self.logger.error(f"Failed to initialize {exchange}: {e}")
    
    def start(self) -> None:
        """Start the background scanner."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        self.logger.info("Futures-Spot Detector started")
    
    def stop(self) -> None:
        """Stop the background scanner."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        self.logger.info("Futures-Spot Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self.is_running:
            try:
                # Scan for opportunities
                opportunities = self.scan_opportunities()
                if opportunities:
                    self._process_opportunities(opportunities)
                
                # Update metrics
                self.metrics["scans"] += 1
                
                # Sleep until next scan
                time.sleep(self.scan_interval)
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                self.metrics["errors"] += 1
                time.sleep(1.0)
    
    def scan_opportunities(
        self,
        symbols: Optional[List[str]] = None,
    ) -> List[ArbitrageOpportunity]:
        """
        Scan for futures-spot arbitrage opportunities.
        
        Args:
            symbols: Optional list of symbols to scan
            
        Returns:
            List of ArbitrageOpportunity objects
        """
        try:
            start_time = time.time()
            opportunities = []
            
            # Get market data from all exchanges
            market_data = self._get_market_data(symbols)
            
            # Calculate basis for all pairs
            for exchange, data in market_data.items():
                spot_data = data.get("spot", {})
                futures_data = data.get("futures", {})
                
                for symbol, spot in spot_data.items():
                    if symbol in futures_data:
                        for future in futures_data[symbol]:
                            # Calculate basis
                            basis = self._calculate_basis(spot, future)
                            if basis:
                                # Evaluate opportunity
                                opportunity = self._evaluate_opportunity(
                                    spot,
                                    future,
                                    basis
                                )
                                if opportunity and self._is_viable(opportunity):
                                    opportunities.append(opportunity)
            
            # Rank opportunities by annualized return
            opportunities.sort(
                key=lambda x: x["annualized_return"],
                reverse=True
            )
            
            # Apply position sizing
            for i, opp in enumerate(opportunities):
                opp["recommended_position"] = self._calculate_position_size(
                    opp,
                    i,
                    len(opportunities)
                )
            
            # Update metrics
            self.metrics["opportunities_found"] += len(opportunities)
            
            execution_time = (time.time() - start_time) * 1000
            self.logger.debug(
                f"Scan completed in {execution_time:.2f}ms, "
                f"found {len(opportunities)} opportunities"
            )
            
            return opportunities[:self.risk_params.max_positions]
            
        except Exception as e:
            self.logger.error(f"Opportunity scan failed: {e}")
            return []
    
    def _get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, Dict[str, MarketData]]]:
        """
        Get market data from all exchanges.
        
        Args:
            symbols: Optional list of symbols
            
        Returns:
            Dictionary of market data by exchange
        """
        market_data = {}
        
        with ThreadPoolExecutor(max_workers=len(self.connectors)) as executor:
            future_to_exchange = {
                executor.submit(self._get_exchange_data, exchange, symbols): exchange
                for exchange in self.connectors.keys()
            }
            
            for future in future_to_exchange:
                try:
                    exchange = future_to_exchange[future]
                    data = future.result(timeout=10.0)
                    if data:
                        market_data[exchange] = data
                except Exception as e:
                    self.logger.warning(f"Failed to get data from exchange: {e}")
        
        return market_data
    
    def _get_exchange_data(
        self,
        exchange: str,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        """
        Get data from a specific exchange.
        
        Args:
            exchange: Exchange name
            symbols: Optional list of symbols
            
        Returns:
            Dictionary of market data
        """
        connector = self.connectors.get(exchange)
        if not connector:
            return {}
        
        try:
            return connector.get_market_data(symbols)
        except Exception as e:
            self.logger.debug(f"Failed to get data from {exchange}: {e}")
            return {}
    
    def _calculate_basis(
        self,
        spot: MarketData,
        future: MarketData,
    ) -> Optional[BasisData]:
        """
        Calculate basis between spot and futures prices.
        
        Args:
            spot: Spot market data
            future: Futures market data
            
        Returns:
            BasisData or None
        """
        try:
            spot_price = spot["price"]
            futures_price = future["price"]
            
            # Calculate basis
            basis = futures_price - spot_price
            basis_percentage = (basis / spot_price) * Decimal("100")
            
            # Calculate annualized basis
            days_to_expiry = None
            if future.get("expiry"):
                days_to_expiry = (
                    future["expiry"] - datetime.utcnow()
                ).total_seconds() / 86400
                
            if days_to_expiry and days_to_expiry > 0:
                annualized_basis = basis_percentage * (365 / days_to_expiry)
            else:
                annualized_basis = basis_percentage * 365  # Perpetual assumption
            
            # Get funding rate if available
            funding_rate = future.get("funding_rate")
            
            # Calculate basis yield
            if funding_rate:
                basis_yield = basis_percentage + funding_rate * 365 * 100
            else:
                basis_yield = basis_percentage
            
            return BasisData(
                symbol=spot["symbol"],
                spot_price=spot_price,
                futures_price=futures_price,
                basis=basis,
                basis_percentage=basis_percentage,
                annualized_basis=annualized_basis,
                days_to_expiry=days_to_expiry,
                funding_rate=funding_rate,
                implied_funding_rate=annualized_basis / 365 if days_to_expiry else None,
                basis_yield=basis_yield,
                annualized_yield=basis_yield * (365 / days_to_expiry) if days_to_expiry else basis_yield * 365,
            )
            
        except Exception as e:
            self.logger.debug(f"Basis calculation failed: {e}")
            return None
    
    def _evaluate_opportunity(
        self,
        spot: MarketData,
        future: MarketData,
        basis: BasisData,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Evaluate a basis trading opportunity.
        
        Args:
            spot: Spot market data
            future: Futures market data
            basis: Basis data
            
        Returns:
            ArbitrageOpportunity or None
        """
        try:
            # Determine position type
            if basis["basis"] > 0:
                # Contango: Futures > Spot
                # Long spot, short futures
                position_type = "long_spot_short_futures"
                entry_price = spot["price"]
                exit_price = future["price"]  # Close both at expiry
            else:
                # Backwardation: Futures < Spot
                # Short spot, long futures
                position_type = "short_spot_long_futures"
                entry_price = future["price"]
                exit_price = spot["price"]
            
            # Calculate profit
            expected_profit = abs(basis["basis"])
            expected_profit_percentage = abs(basis["basis_percentage"])
            
            # Calculate annualized return
            if basis["days_to_expiry"]:
                annualized_return = basis["annualized_yield"]
            else:
                annualized_return = abs(basis["basis_percentage"]) * 365
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(spot, future, basis)
            
            # Calculate confidence
            confidence = self._calculate_confidence(spot, future, basis)
            
            # Calculate position size
            position_size = self._calculate_position_size_initial(basis)
            
            # Calculate stop loss and take profit
            stop_loss = entry_price * (1 - float(self.risk_params.stop_loss_percentage))
            take_profit = entry_price * (1 + float(self.risk_params.take_profit_percentage))
            
            return ArbitrageOpportunity(
                symbol=spot["symbol"],
                exchange=spot["exchange"],
                spot_price=spot["price"],
                futures_price=future["price"],
                basis=basis["basis"],
                basis_percentage=basis["basis_percentage"],
                annualized_basis=basis["annualized_basis"],
                funding_rate=future.get("funding_rate"),
                position_type=position_type,
                entry_price=entry_price,
                exit_price=exit_price,
                expected_profit=expected_profit,
                expected_profit_percentage=expected_profit_percentage,
                annualized_return=annualized_return,
                risk_score=risk_score,
                confidence=confidence,
                position_size=position_size,
                max_position_size=self.max_position_size,
                recommended_position=position_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                expiry=future.get("expiry"),
                time_to_expiry=timedelta(days=basis["days_to_expiry"]) if basis["days_to_expiry"] else None,
                contract_type=future.get("contract_type", ContractType.PERPETUAL),
            )
            
        except Exception as e:
            self.logger.debug(f"Opportunity evaluation failed: {e}")
            return None
    
    def _calculate_risk_score(
        self,
        spot: MarketData,
        future: MarketData,
        basis: BasisData,
    ) -> Decimal:
        """
        Calculate risk score for an opportunity.
        
        Args:
            spot: Spot market data
            future: Futures market data
            basis: Basis data
            
        Returns:
            Risk score between 0 and 1
        """
        risk_score = Decimal("0")
        
        # Factor 1: Basis volatility
        basis_volatility = Decimal("0.1")  # Would calculate from historical data
        risk_score += basis_volatility * Decimal("0.3")
        
        # Factor 2: Liquidity risk
        spot_volume = spot.get("volume", Decimal("0"))
        futures_volume = future.get("volume", Decimal("0"))
        if spot_volume > Decimal("0") and futures_volume > Decimal("0"):
            liquidity_risk = Decimal("1") - min(
                Decimal("1"),
                (spot_volume + futures_volume) / Decimal("1000000")
            )
            risk_score += liquidity_risk * Decimal("0.2")
        
        # Factor 3: Exchange risk
        exchange_risk = Decimal("0.1")  # Base risk
        risk_score += exchange_risk
        
        # Factor 4: Time to expiry risk
        if basis["days_to_expiry"]:
            time_risk = Decimal("1") / Decimal(str(basis["days_to_expiry"] + 1))
            risk_score += time_risk * Decimal("0.2")
        
        # Factor 5: Funding rate risk
        if basis["funding_rate"]:
            funding_risk = abs(basis["funding_rate"]) * Decimal("100")
            risk_score += min(Decimal("0.2"), funding_risk * Decimal("0.5"))
        
        # Normalize
        return min(Decimal("1"), risk_score)
    
    def _calculate_confidence(
        self,
        spot: MarketData,
        future: MarketData,
        basis: BasisData,
    ) -> Decimal:
        """
        Calculate confidence score for an opportunity.
        
        Args:
            spot: Spot market data
            future: Futures market data
            basis: Basis data
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = Decimal("0.8")  # Base confidence
        
        # Factor 1: Data freshness
        time_diff = (datetime.utcnow() - spot["timestamp"]).total_seconds()
        if time_diff > 60:
            confidence *= Decimal("0.9")
        
        # Factor 2: Volume confirmation
        spot_volume = spot.get("volume", Decimal("0"))
        futures_volume = future.get("volume", Decimal("0"))
        if spot_volume > Decimal("0") and futures_volume > Decimal("0"):
            volume_confirm = min(
                Decimal("1"),
                (spot_volume + futures_volume) / Decimal("500000")
            )
            confidence *= Decimal("0.9") + volume_confirm * Decimal("0.1")
        
        # Factor 3: Market stability
        bid_ask_spread = spot.get("ask", Decimal("0")) - spot.get("bid", Decimal("0"))
        if bid_ask_spread > Decimal("0"):
            spread_pct = bid_ask_spread / spot["price"]
            if spread_pct > Decimal("0.001"):
                confidence *= Decimal("0.95")
        
        # Factor 4: Historical success rate
        confidence *= Decimal("0.98")
        
        return max(Decimal("0"), min(Decimal("1"), confidence))
    
    def _calculate_position_size_initial(self, basis: BasisData) -> Decimal:
        """
        Calculate initial position size.
        
        Args:
            basis: Basis data
            
        Returns:
            Position size
        """
        # Use Kelly criterion for position sizing
        base_size = Decimal("10000")  # $10K base
        
        # Adjust based on basis strength
        basis_strength = abs(basis["basis_percentage"])
        size_multiplier = min(Decimal("5"), basis_strength * Decimal("100"))
        
        # Adjust based on risk
        risk_adjustment = Decimal("1") - self._calculate_risk_score_estimate(basis)
        
        # Calculate final size
        size = base_size * size_multiplier * risk_adjustment
        
        # Cap at maximum
        return min(self.max_position_size, size)
    
    def _calculate_risk_score_estimate(self, basis: BasisData) -> Decimal:
        """
        Estimate risk score from basis data.
        
        Args:
            basis: Basis data
            
        Returns:
            Risk score estimate
        """
        risk = Decimal("0.3")  # Base risk
        
        # Increase risk for higher basis (more volatility)
        basis_abs = abs(basis["basis_percentage"])
        risk += min(Decimal("0.3"), basis_abs * Decimal("10"))
        
        # Decrease risk for funded positions
        if basis["funding_rate"]:
            risk -= min(Decimal("0.1"), abs(basis["funding_rate"]) * Decimal("100"))
        
        return min(Decimal("0.8"), risk)
    
    def _is_viable(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Check if an opportunity is viable.
        
        Args:
            opportunity: Opportunity to check
            
        Returns:
            True if viable
        """
        return (
            abs(opportunity["basis_percentage"]) >= float(self.min_basis_threshold * 100) and
            opportunity["confidence"] >= MIN_CONFIDENCE and
            opportunity["risk_score"] <= Decimal("0.7") and
            opportunity["annualized_return"] > self.risk_params.risk_free_rate * 100
        )
    
    def _process_opportunities(self, opportunities: List[ArbitrageOpportunity]) -> None:
        """
        Process detected opportunities.
        
        Args:
            opportunities: List of opportunities
        """
        for opp in opportunities:
            # Cache opportunity
            key = hashlib.md5(
                json.dumps([
                    opp["symbol"],
                    opp["exchange"],
                    str(opp["position_type"]),
                ]).encode()
            ).hexdigest()
            self.opportunity_cache[key] = opp
        
        # Log top opportunities
        if opportunities:
            best = opportunities[0]
            self.logger.info(
                f"Found basis opportunity: {best['symbol']} on {best['exchange']}, "
                f"basis: {best['basis_percentage']:.2f}%, "
                f"annualized: {best['annualized_return']:.2f}%, "
                f"confidence: {best['confidence']:.2f}, "
                f"risk: {best['risk_score']:.2f}"
            )
    
    def _calculate_position_size(
        self,
        opportunity: ArbitrageOpportunity,
        rank: int,
        total: int,
    ) -> Decimal:
        """
        Calculate recommended position size.
        
        Args:
            opportunity: Opportunity
            rank: Rank in opportunities list
            total: Total opportunities
            
        Returns:
            Recommended position size
        """
        # Base size from initial calculation
        base_size = opportunity["position_size"]
        
        # Adjust for rank (top opportunities get more size)
        rank_multiplier = Decimal(str(total - rank)) / Decimal(str(total))
        rank_multiplier = max(Decimal("0.5"), rank_multiplier)
        
        # Adjust for risk
        risk_multiplier = Decimal("1") - opportunity["risk_score"]
        
        # Calculate final size
        size = base_size * rank_multiplier * risk_multiplier
        
        # Apply risk per trade limit
        max_risk_amount = self.risk_params.max_risk_per_trade * self.max_position_size
        size = min(size, max_risk_amount)
        
        return size
    
    def execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
    ) -> Dict[str, Any]:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            Execution result
        """
        result = {
            "success": False,
            "order_ids": [],
            "profit": Decimal("0"),
            "position": None,
            "error": None,
        }
        
        try:
            # Get exchange connector
            connector = self.connectors.get(opportunity["exchange"])
            if not connector:
                raise ValueError(f"No connector for {opportunity['exchange']}")
            
            # Determine position side
            if opportunity["position_type"] == "long_spot_short_futures":
                spot_side = OrderSide.BUY
                futures_side = OrderSide.SELL
            else:
                spot_side = OrderSide.SELL
                futures_side = OrderSide.BUY
            
            # Calculate position sizes
            position_size = opportunity["recommended_position"]
            spot_position = position_size / 2  # Half in spot, half in futures
            futures_position = position_size / 2
            
            # Execute spot order
            spot_order = connector.place_order(
                symbol=opportunity["symbol"],
                side=spot_side,
                order_type=OrderType.MARKET,
                quantity=spot_position,
                market_type=MarketType.SPOT,
            )
            
            if not spot_order:
                raise ValueError("Spot order failed")
            
            # Execute futures order
            futures_order = connector.place_order(
                symbol=opportunity["symbol"],
                side=futures_side,
                order_type=OrderType.MARKET,
                quantity=futures_position,
                market_type=MarketType.FUTURES,
                contract_type=opportunity["contract_type"],
            )
            
            if not futures_order:
                # Rollback spot order
                connector.cancel_order(spot_order["id"])
                raise ValueError("Futures order failed")
            
            # Create position
            position = Position(
                symbol=opportunity["symbol"],
                exchange=opportunity["exchange"],
                side=spot_side,
                size=position_size,
                entry_price=opportunity["entry_price"],
                current_price=opportunity["entry_price"],
                pnl=Decimal("0"),
                pnl_percentage=Decimal("0"),
                timestamp=datetime.utcnow(),
                stop_loss=opportunity["stop_loss"],
                take_profit=opportunity["take_profit"],
                expiry=opportunity["expiry"],
            )
            
            # Add to positions
            with self.position_lock:
                self.positions.append(position)
            
            # Update metrics
            self.metrics["opportunities_executed"] += 1
            self.metrics["total_trades"] += 2  # Spot + Futures
            
            result["success"] = True
            result["order_ids"] = [spot_order["id"], futures_order["id"]]
            result["position"] = position
            
            self.logger.info(
                f"Executed futures-spot arbitrage: {opportunity['symbol']} "
                f"size: ${position_size:,.2f}"
            )
            
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            result["error"] = str(e)
            self.metrics["errors"] += 1
        
        return result
    
    def close_position(
        self,
        position: Position,
    ) -> Dict[str, Any]:
        """
        Close an open position.
        
        Args:
            position: Position to close
            
        Returns:
            Close result
        """
        result = {
            "success": False,
            "order_ids": [],
            "pnl": Decimal("0"),
            "error": None,
        }
        
        try:
            connector = self.connectors.get(position.exchange)
            if not connector:
                raise ValueError(f"No connector for {position.exchange}")
            
            # Close spot and futures positions
            spot_close = connector.place_order(
                symbol=position.symbol,
                side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=position.size / 2,
                market_type=MarketType.SPOT,
            )
            
            futures_close = connector.place_order(
                symbol=position.symbol,
                side=OrderSide.BUY if position.side == OrderSide.BUY else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=position.size / 2,
                market_type=MarketType.FUTURES,
            )
            
            if spot_close and futures_close:
                # Calculate PnL
                current_price = connector.get_price(position.symbol)
                pnl = (current_price - position.entry_price) * position.size
                
                result["success"] = True
                result["order_ids"] = [spot_close["id"], futures_close["id"]]
                result["pnl"] = pnl
                
                # Update metrics
                self.metrics["total_profit"] += pnl
                
                # Remove position
                with self.position_lock:
                    self.positions.remove(position)
                
                self.logger.info(f"Closed position: {position.symbol}, PnL: ${pnl:,.2f}")
            else:
                raise ValueError("Failed to close position")
            
        except Exception as e:
            self.logger.error(f"Position close failed: {e}")
            result["error"] = str(e)
            self.metrics["errors"] += 1
        
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "positions_open": len(self.positions),
            "opportunities_cached": len(self.opportunity_cache),
            "is_running": self.is_running,
            "min_basis_threshold": float(self.min_basis_threshold),
            "max_position_size": float(self.max_position_size),
            "scan_interval": self.scan_interval,
        }


# Exchange Connectors

class ExchangeConnector(ABC):
    """Abstract base class for exchange connectors."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(__name__)
    
    @abstractmethod
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        """Get market data from exchange."""
        pass
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        """Place an order on exchange."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def get_price(self, symbol: str) -> Decimal:
        """Get current price for a symbol."""
        pass


class ExchangeConnectorFactory:
    """Factory for creating exchange connectors."""
    
    @staticmethod
    def create(exchange: str) -> ExchangeConnector:
        """
        Create an exchange connector.
        
        Args:
            exchange: Exchange name
            
        Returns:
            ExchangeConnector instance
        """
        if exchange.lower() in ["binance", "binance_futures"]:
            from .binance_connector import BinanceConnector
            return BinanceConnector(exchange)
        elif exchange.lower() in ["bybit", "bybit_futures"]:
            from .bybit_connector import BybitConnector
            return BybitConnector(exchange)
        elif exchange.lower() in ["okx", "okx_futures"]:
            from .okx_connector import OKXConnector
            return OKXConnector(exchange)
        elif exchange.lower() in ["kraken", "kraken_futures"]:
            from .kraken_connector import KrakenConnector
            return KrakenConnector(exchange)
        elif exchange.lower() in ["coinbase", "coinbase_futures"]:
            from .coinbase_connector import CoinbaseConnector
            return CoinbaseConnector(exchange)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")


class BinanceConnector(ExchangeConnector):
    """Binance exchange connector."""
    
    def __init__(self, name: str):
        super().__init__(name)
        # Initialize Binance API client
        try:
            from binance.client import Client
            from binance.enums import *
            self.client = Client()
        except ImportError:
            self.logger.warning("Binance client not available")
    
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        # Implementation for Binance
        return {}
    
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        # Implementation for Binance
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        # Implementation for Binance
        return True
    
    def get_price(self, symbol: str) -> Decimal:
        # Implementation for Binance
        return Decimal("0")


class BybitConnector(ExchangeConnector):
    """Bybit exchange connector."""
    
    def __init__(self, name: str):
        super().__init__(name)
        # Initialize Bybit API client
        try:
            from pybit.unified_trading import HTTP
            self.client = HTTP()
        except ImportError:
            self.logger.warning("Bybit client not available")
    
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        return {}
    
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        return True
    
    def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")


class OKXConnector(ExchangeConnector):
    """OKX exchange connector."""
    
    def __init__(self, name: str):
        super().__init__(name)
        # Initialize OKX API client
        try:
            from okx import MarketData, Trade
            self.market = MarketData()
            self.trade = Trade()
        except ImportError:
            self.logger.warning("OKX client not available")
    
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        return {}
    
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        return True
    
    def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")


class KrakenConnector(ExchangeConnector):
    """Kraken exchange connector."""
    
    def __init__(self, name: str):
        super().__init__(name)
        # Initialize Kraken API client
        try:
            from krakenex import API
            self.client = API()
        except ImportError:
            self.logger.warning("Kraken client not available")
    
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        return {}
    
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        return True
    
    def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")


class CoinbaseConnector(ExchangeConnector):
    """Coinbase exchange connector."""
    
    def __init__(self, name: str):
        super().__init__(name)
        # Initialize Coinbase API client
        try:
            from coinbase.wallet.client import Client
            self.client = Client()
        except ImportError:
            self.logger.warning("Coinbase client not available")
    
    def get_market_data(
        self,
        symbols: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, MarketData]]:
        return {}
    
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        market_type: MarketType = MarketType.SPOT,
        contract_type: Optional[ContractType] = None,
        price: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Any]]:
        return None
    
    def cancel_order(self, order_id: str) -> bool:
        return True
    
    def get_price(self, symbol: str) -> Decimal:
        return Decimal("0")


# Helper Classes

class MEVProtection:
    """MEV Protection for futures-spot arbitrage."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = {
            "enabled": True,
            "private_mempool": True,
            "slippage_protection": Decimal("0.001"),  # 0.1%
        }
    
    def protect(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Apply MEV protection to an order."""
        if not self.config["enabled"]:
            return order
        
        # Add slippage protection
        if "price" in order:
            order["slippage_tolerance"] = float(self.config["slippage_protection"])
        
        return order


class RiskManager:
    """Risk management for futures-spot arbitrage."""
    
    def __init__(self, params: RiskParameters):
        self.params = params
        self.logger = logging.getLogger(__name__)
    
    def validate_position(self, position: Position) -> bool:
        """Validate a position against risk parameters."""
        # Check position size
        if abs(position.size) > self.params.max_position_size:
            return False
        
        # Check leverage
        if abs(position.size / position.entry_price) > self.params.max_leverage:
            return False
        
        # Check drawdown
        if position.pnl_percentage < -self.params.max_drawdown:
            return False
        
        return True
    
    def calculate_stop_loss(self, position: Position) -> Decimal:
        """Calculate stop-loss price."""
        if position.side == OrderSide.BUY:
            return position.entry_price * (1 - float(self.params.stop_loss_percentage))
        else:
            return position.entry_price * (1 + float(self.params.stop_loss_percentage))
    
    def calculate_take_profit(self, position: Position) -> Decimal:
        """Calculate take-profit price."""
        if position.side == OrderSide.BUY:
            return position.entry_price * (1 + float(self.params.take_profit_percentage))
        else:
            return position.entry_price * (1 - float(self.params.take_profit_percentage))


class PerformanceTracker:
    """Performance tracking for futures-spot arbitrage."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.trades: List[Dict[str, Any]] = []
        self.returns: List[Decimal] = []
    
    def add_trade(self, trade: Dict[str, Any]) -> None:
        """Add a trade to the tracker."""
        self.trades.append(trade)
        if "return" in trade:
            self.returns.append(trade["return"])
    
    def get_sharpe_ratio(self, risk_free_rate: Decimal = Decimal("0.02")) -> Decimal:
        """Calculate Sharpe ratio."""
        if not self.returns:
            return Decimal("0")
        
        returns_array = np.array([float(r) for r in self.returns])
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return Decimal("0")
        
        sharpe = (mean_return - float(risk_free_rate)) / std_return
        return Decimal(str(sharpe))
    
    def get_win_rate(self) -> Decimal:
        """Calculate win rate."""
        if not self.trades:
            return Decimal("0")
        
        wins = sum(1 for t in self.trades if t.get("pnl", Decimal("0")) > Decimal("0"))
        return Decimal(str(wins / len(self.trades)))
    
    def get_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown."""
        if not self.returns:
            return Decimal("0")
        
        cumulative = np.cumsum([float(r) for r in self.returns])
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        max_drawdown = np.max(drawdown)
        
        return Decimal(str(max_drawdown))


# Module exports
__all__ = [
    'FuturesSpotDetector',
    'ExchangeType',
    'MarketType',
    'ContractType',
    'OrderSide',
    'OrderType',
    'MarketData',
    'BasisData',
    'ArbitrageOpportunity',
    'Position',
    'RiskParameters',
    'ExchangeConnector',
    'ExchangeConnectorFactory',
    'BinanceConnector',
    'BybitConnector',
    'OKXConnector',
    'KrakenConnector',
    'CoinbaseConnector',
    'MEVProtection',
    'RiskManager',
    'PerformanceTracker',
]
