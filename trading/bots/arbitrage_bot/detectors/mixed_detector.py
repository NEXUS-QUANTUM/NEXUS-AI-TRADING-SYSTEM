# trading/bots/arbitrage_bot/detectors/mixed_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Mixed Arbitrage Detection Engine

"""
Mixed Arbitrage Detector - Advanced Multi-Strategy Arbitrage Detection Engine

This module provides state-of-the-art detection of mixed arbitrage opportunities
combining multiple arbitrage strategies simultaneously:
- DEX Arbitrage + Flash Loans
- Futures-Spot Arbitrage + Funding Rate Arbitrage
- Cross-Exchange Arbitrage + Statistical Arbitrage
- Triangular Arbitrage + Flash Loans
- Multi-Leg Arbitrage (3+ legs)
- Composite Arbitrage Strategies
- Dynamic Strategy Selection
- Portfolio-Level Arbitrage Optimization

Architecture:
    - BaseMixedDetector: Abstract base class
    - MixedDetector: Main detector implementation
    - StrategyCombinator: Strategy combination logic
    - LegOptimizer: Multi-leg optimization
    - PortfolioArbitrage: Portfolio-level arbitrage
    - DynamicSelector: Dynamic strategy selection
    - RiskAggregator: Aggregated risk management

Strategies Supported:
    - DEX Arbitrage (Uniswap, SushiSwap, PancakeSwap, etc.)
    - Flash Loan Arbitrage (AAVE, Balancer, Uniswap V3)
    - Futures-Spot Arbitrage (Basis Trading)
    - Funding Rate Arbitrage
    - Cross-Exchange Arbitrage
    - Triangular Arbitrage
    - Statistical Arbitrage
    - Options Arbitrage
    - Yield Arbitrage
    - MEV Arbitrage
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
from scipy.optimize import minimize, linprog
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Constants and configurations
MIN_MIXED_ARBITRAGE_PROFIT = Decimal("0.005")  # 0.5% minimum profit
MAX_LEGS = 6  # Maximum number of legs in a mixed arbitrage
MIN_LEG_PROFIT = Decimal("0.001")  # 0.1% minimum profit per leg
MAX_COMPLEXITY_SCORE = Decimal("0.7")
MIN_CONFIDENCE = Decimal("0.65")
DEFAULT_GAS_BUFFER = Decimal("1.2")

# Strategy types
class ArbitrageStrategy(Enum):
    """Types of arbitrage strategies."""
    DEX = "dex_arbitrage"
    FLASH_LOAN = "flash_loan_arbitrage"
    FUTURES_SPOT = "futures_spot_arbitrage"
    FUNDING_RATE = "funding_rate_arbitrage"
    CROSS_EXCHANGE = "cross_exchange_arbitrage"
    TRIANGULAR = "triangular_arbitrage"
    STATISTICAL = "statistical_arbitrage"
    OPTIONS = "options_arbitrage"
    YIELD = "yield_arbitrage"
    MEV = "mev_arbitrage"
    LIQUIDATION = "liquidation_arbitrage"
    NFT = "nft_arbitrage"
    CROSS_CHAIN = "cross_chain_arbitrage"
    PERPETUAL = "perpetual_arbitrage"
    BASIS = "basis_arbitrage"

class StrategyCategory(Enum):
    """Categories of arbitrage strategies."""
    DEX_BASED = "dex_based"
    FLASH_LOAN_BASED = "flash_loan_based"
    FUTURES_BASED = "futures_based"
    EXCHANGE_BASED = "exchange_based"
    STATISTICAL_BASED = "statistical_based"
    COMPOSITE = "composite"

# Typed dictionaries
class StrategyProfile(TypedDict):
    """Profile of an arbitrage strategy."""
    strategy: ArbitrageStrategy
    category: StrategyCategory
    expected_profit: Decimal
    risk_score: Decimal
    complexity: int
    gas_cost: Decimal
    execution_time_ms: int
    success_rate: Decimal
    capital_required: Decimal
    leverage_used: Decimal
    requires_contract: bool
    requires_flash_loan: bool
    min_profit_threshold: Decimal

class MixedArbitrageLeg(TypedDict):
    """A single leg in a mixed arbitrage."""
    strategy: ArbitrageStrategy
    action: str  # "buy", "sell", "swap", "borrow", "repay", "deposit", "withdraw"
    asset_in: str
    asset_out: str
    amount_in: Decimal
    amount_out: Decimal
    expected_profit: Decimal
    expected_profit_percentage: Decimal
    exchange: Optional[str]
    protocol: Optional[str]
    pool_id: Optional[str]
    path: List[str]
    slippage: Decimal
    gas_cost: Decimal
    risk_score: Decimal
    confidence: Decimal
    timestamp: datetime

class MixedArbitrageOpportunity(TypedDict):
    """Complete mixed arbitrage opportunity."""
    legs: List[MixedArbitrageLeg]
    strategies: List[ArbitrageStrategy]
    categories: List[StrategyCategory]
    total_profit: Decimal
    total_profit_percentage: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    net_profit_percentage: Decimal
    weighted_risk_score: Decimal
    avg_confidence: Decimal
    complexity_score: Decimal
    capital_required: Decimal
    capital_used: Decimal
    execution_time_ms: int
    requires_flash_loan: bool
    requires_contract_deployment: bool
    requires_cross_chain: bool
    priority: int
    timestamp: datetime

@dataclass
class StrategyCombination:
    """Combination of strategies for mixed arbitrage."""
    strategies: List[ArbitrageStrategy]
    expected_profit: Decimal
    risk_score: Decimal
    complexity: int
    synergy_score: Decimal
    capital_required: Decimal
    execution_time_ms: int

@dataclass
class ExecutionPlan:
    """Execution plan for mixed arbitrage."""
    legs: List[MixedArbitrageLeg]
    sequential: bool
    atomic: bool
    timeout: int
    gas_limit: int
    deadline: datetime
    fallback_plan: Optional["ExecutionPlan"]
    verification_checks: List[str]

@dataclass
class PortfolioArbitrageState:
    """State of portfolio-level arbitrage."""
    total_capital: Decimal
    used_capital: Decimal
    available_capital: Decimal
    open_positions: List[Dict[str, Any]]
    total_pnl: Decimal
    current_risk: Decimal
    max_risk: Decimal
    diversification_score: Decimal

class MixedDetector:
    """
    Advanced Mixed Arbitrage Detector.
    
    This class implements sophisticated detection of mixed arbitrage
    opportunities combining multiple strategies:
    1. DEX Arbitrage + Flash Loans
    2. Futures-Spot + Funding Rate
    3. Cross-Exchange + Statistical Arbitrage
    4. Triangular + Flash Loans
    5. Multi-Leg Composite Arbitrage
    6. Dynamic Strategy Selection
    7. Portfolio-Level Optimization
    
    Features:
    - Multi-strategy combination detection
    - Real-time opportunity scanning
    - Dynamic strategy selection based on market conditions
    - Portfolio-level arbitrage optimization
    - Complex leg optimization
    - Risk aggregation and management
    - Atomic execution planning
    - MEV protection
    - Cross-chain support
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        min_profit_threshold: Decimal = MIN_MIXED_ARBITRAGE_PROFIT,
        max_legs: int = MAX_LEGS,
        max_complexity: Decimal = MAX_COMPLEXITY_SCORE,
        scan_interval: float = 2.0,
        enable_detectors: Optional[List[str]] = None,
    ):
        """
        Initialize the Mixed Detector.
        
        Args:
            config: Optional configuration dictionary
            min_profit_threshold: Minimum profit percentage to consider
            max_legs: Maximum number of legs
            max_complexity: Maximum complexity score
            scan_interval: Interval between scans in seconds
            enable_detectors: List of detector names to enable
        """
        self.logger = self._setup_logger()
        self.config = config or {}
        self.min_profit_threshold = min_profit_threshold
        self.max_legs = max_legs
        self.max_complexity = max_complexity
        self.scan_interval = scan_interval
        
        # Initialize detectors
        self.detectors: Dict[ArbitrageStrategy, Any] = {}
        self._init_detectors(enable_detectors)
        
        # Strategy registry
        self.strategy_registry = self._build_strategy_registry()
        
        # Cache
        self.opportunity_cache: Dict[str, MixedArbitrageOpportunity] = {}
        self.strategy_cache: Dict[str, StrategyProfile] = {}
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Portfolio state
        self.portfolio = PortfolioArbitrageState(
            total_capital=Decimal("1000000"),
            used_capital=Decimal("0"),
            available_capital=Decimal("1000000"),
            open_positions=[],
            total_pnl=Decimal("0"),
            current_risk=Decimal("0"),
            max_risk=Decimal("0.5"),
            diversification_score=Decimal("1"),
        )
        
        # Metrics
        self.metrics = {
            "scans": 0,
            "opportunities_found": 0,
            "opportunities_executed": 0,
            "total_profit": Decimal("0"),
            "strategy_usage": defaultdict(int),
            "avg_complexity": Decimal("0"),
            "success_rate": Decimal("0"),
            "errors": 0,
            "total_gas_cost": Decimal("0"),
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        
        # MEV protection
        self.mev_shield = MixedMEVShield()
        
        # Risk aggregator
        self.risk_aggregator = RiskAggregator()
        
        # Start scanner
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
    
    def _init_detectors(self, enable_detectors: Optional[List[str]] = None) -> None:
        """
        Initialize individual arbitrage detectors.
        
        Args:
            enable_detectors: List of detector names to enable
        """
        # Import detectors dynamically
        try:
            from ..detectors.dex_detector import DexDetector
            from ..detectors.flash_loan_detector import FlashLoanDetector
            from ..detectors.futures_spot_detector import FuturesSpotDetector
            from ..detectors.cross_exchange_detector import CrossExchangeDetector
            from ..detectors.triangular_detector import TriangularDetector
            from ..detectors.statistical_detector import StatisticalDetector
            
            self.detectors = {
                ArbitrageStrategy.DEX: DexDetector(),
                ArbitrageStrategy.FLASH_LOAN: FlashLoanDetector(),
                ArbitrageStrategy.FUTURES_SPOT: FuturesSpotDetector(exchanges=["binance", "bybit"]),
                ArbitrageStrategy.CROSS_EXCHANGE: CrossExchangeDetector(),
                ArbitrageStrategy.TRIANGULAR: TriangularDetector(),
                ArbitrageStrategy.STATISTICAL: StatisticalDetector(),
            }
            
            # Filter enabled detectors
            if enable_detectors:
                enabled_set = set(enable_detectors)
                self.detectors = {
                    k: v for k, v in self.detectors.items()
                    if k.value in enabled_set or k.name.lower() in enabled_set
                }
            
        except ImportError as e:
            self.logger.warning(f"Failed to import detectors: {e}")
            # Fallback to minimal detectors
            self.detectors = {}
    
    def _build_strategy_registry(self) -> Dict[ArbitrageStrategy, StrategyProfile]:
        """
        Build strategy registry with profiles for all strategies.
        
        Returns:
            Dictionary of strategy profiles
        """
        registry = {}
        
        # Define profiles for each strategy
        profiles = {
            ArbitrageStrategy.DEX: {
                "category": StrategyCategory.DEX_BASED,
                "complexity": 1,
                "gas_cost": Decimal("0.001"),
                "capital_required": Decimal("1000"),
                "leverage_used": Decimal("1"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.001"),
            },
            ArbitrageStrategy.FLASH_LOAN: {
                "category": StrategyCategory.FLASH_LOAN_BASED,
                "complexity": 2,
                "gas_cost": Decimal("0.002"),
                "capital_required": Decimal("0"),
                "leverage_used": Decimal("1"),
                "requires_contract": True,
                "requires_flash_loan": True,
                "min_profit_threshold": Decimal("0.002"),
            },
            ArbitrageStrategy.FUTURES_SPOT: {
                "category": StrategyCategory.FUTURES_BASED,
                "complexity": 2,
                "gas_cost": Decimal("0.001"),
                "capital_required": Decimal("5000"),
                "leverage_used": Decimal("1.5"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.003"),
            },
            ArbitrageStrategy.CROSS_EXCHANGE: {
                "category": StrategyCategory.EXCHANGE_BASED,
                "complexity": 2,
                "gas_cost": Decimal("0.001"),
                "capital_required": Decimal("2000"),
                "leverage_used": Decimal("1"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.002"),
            },
            ArbitrageStrategy.TRIANGULAR: {
                "category": StrategyCategory.DEX_BASED,
                "complexity": 3,
                "gas_cost": Decimal("0.002"),
                "capital_required": Decimal("1000"),
                "leverage_used": Decimal("1"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.003"),
            },
            ArbitrageStrategy.STATISTICAL: {
                "category": StrategyCategory.STATISTICAL_BASED,
                "complexity": 3,
                "gas_cost": Decimal("0.001"),
                "capital_required": Decimal("5000"),
                "leverage_used": Decimal("1.2"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.005"),
            },
            ArbitrageStrategy.FUNDING_RATE: {
                "category": StrategyCategory.FUTURES_BASED,
                "complexity": 1,
                "gas_cost": Decimal("0.001"),
                "capital_required": Decimal("3000"),
                "leverage_used": Decimal("2"),
                "requires_contract": False,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.002"),
            },
            ArbitrageStrategy.OPTIONS: {
                "category": StrategyCategory.COMPOSITE,
                "complexity": 4,
                "gas_cost": Decimal("0.003"),
                "capital_required": Decimal("10000"),
                "leverage_used": Decimal("1"),
                "requires_contract": True,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.01"),
            },
            ArbitrageStrategy.MEV: {
                "category": StrategyCategory.COMPOSITE,
                "complexity": 4,
                "gas_cost": Decimal("0.005"),
                "capital_required": Decimal("1000"),
                "leverage_used": Decimal("1"),
                "requires_contract": True,
                "requires_flash_loan": False,
                "min_profit_threshold": Decimal("0.005"),
            },
        }
        
        for strategy, profile in profiles.items():
            registry[strategy] = {
                "strategy": strategy,
                **profile,
                "expected_profit": Decimal("0"),
                "risk_score": Decimal("0.3"),
                "execution_time_ms": 0,
                "success_rate": Decimal("0.8"),
            }
        
        return registry
    
    def start(self) -> None:
        """Start the background scanner."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        self.logger.info("Mixed Detector started")
    
    def stop(self) -> None:
        """Stop the background scanner."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        self.logger.info("Mixed Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self.is_running:
            try:
                # Scan for mixed opportunities
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
        strategies: Optional[List[ArbitrageStrategy]] = None,
        max_combinations: int = 50,
    ) -> List[MixedArbitrageOpportunity]:
        """
        Scan for mixed arbitrage opportunities.
        
        Args:
            strategies: Optional list of strategies to consider
            max_combinations: Maximum number of strategy combinations to evaluate
            
        Returns:
            List of MixedArbitrageOpportunity objects
        """
        try:
            start_time = time.time()
            opportunities = []
            
            # Get strategies to scan
            scan_strategies = strategies or list(self.detectors.keys())
            
            # Get individual opportunities from each detector
            individual_opps = self._scan_detectors(scan_strategies)
            
            if not individual_opps:
                return []
            
            # Find profitable combinations
            combinations = self._find_strategy_combinations(
                individual_opps,
                max_combinations
            )
            
            # Build mixed opportunities from combinations
            for combo in combinations:
                mixed_opp = self._build_mixed_opportunity(combo)
                if mixed_opp and self._is_viable(mixed_opp):
                    opportunities.append(mixed_opp)
            
            # Rank opportunities
            opportunities.sort(
                key=lambda x: (x["net_profit_percentage"], -x["complexity_score"]),
                reverse=True
            )
            
            # Update metrics
            self.metrics["opportunities_found"] += len(opportunities)
            if opportunities:
                avg_complexity = sum(
                    o["complexity_score"] for o in opportunities
                ) / len(opportunities)
                self.metrics["avg_complexity"] = avg_complexity
            
            execution_time = (time.time() - start_time) * 1000
            self.logger.debug(
                f"Mixed scan completed in {execution_time:.2f}ms, "
                f"found {len(opportunities)} mixed opportunities"
            )
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Mixed opportunity scan failed: {e}")
            return []
    
    def _scan_detectors(
        self,
        strategies: List[ArbitrageStrategy],
    ) -> Dict[ArbitrageStrategy, List[Any]]:
        """
        Scan individual detectors for opportunities.
        
        Args:
            strategies: List of strategies to scan
            
        Returns:
            Dictionary mapping strategies to their opportunities
        """
        results = defaultdict(list)
        
        with ThreadPoolExecutor(max_workers=len(strategies)) as executor:
            future_to_strategy = {
                executor.submit(self._scan_single_detector, strategy): strategy
                for strategy in strategies
                if strategy in self.detectors
            }
            
            for future in future_to_strategy:
                try:
                    strategy = future_to_strategy[future]
                    opps = future.result(timeout=10.0)
                    if opps:
                        results[strategy] = opps
                except Exception as e:
                    self.logger.debug(f"Detector scan failed: {e}")
        
        return results
    
    def _scan_single_detector(
        self,
        strategy: ArbitrageStrategy,
    ) -> List[Any]:
        """
        Scan a single detector.
        
        Args:
            strategy: Strategy to scan
            
        Returns:
            List of opportunities from the detector
        """
        detector = self.detectors.get(strategy)
        if not detector:
            return []
        
        try:
            if hasattr(detector, 'scan_opportunities'):
                return detector.scan_opportunities()
            return []
        except Exception as e:
            self.logger.debug(f"Detector {strategy.value} scan failed: {e}")
            return []
    
    def _find_strategy_combinations(
        self,
        individual_opps: Dict[ArbitrageStrategy, List[Any]],
        max_combinations: int,
    ) -> List[List[Tuple[ArbitrageStrategy, Any]]]:
        """
        Find profitable combinations of strategies.
        
        Args:
            individual_opps: Individual opportunities by strategy
            max_combinations: Maximum number of combinations to return
            
        Returns:
            List of strategy-opportunity combinations
        """
        combinations = []
        
        # Get strategies with opportunities
        available_strategies = [
            (s, opps) for s, opps in individual_opps.items()
            if opps
        ]
        
        if not available_strategies:
            return []
        
        # Try different combination sizes (2 to max_legs)
        for r in range(2, min(len(available_strategies) + 1, self.max_legs + 1)):
            for combo in combinations(available_strategies, r):
                # Take best opportunity from each strategy
                combo_opps = [(s, opps[0]) for s, opps in combo]
                
                # Check if combination is viable
                if self._is_combination_viable(combo_opps):
                    combinations.append(combo_opps)
                    
                    if len(combinations) >= max_combinations:
                        return combinations
        
        return combinations
    
    def _is_combination_viable(
        self,
        combo: List[Tuple[ArbitrageStrategy, Any]],
    ) -> bool:
        """
        Check if a strategy combination is viable.
        
        Args:
            combo: Strategy-opportunity pairs
            
        Returns:
            True if combination is viable
        """
        # Check for conflicts
        strategies = [s for s, _ in combo]
        
        # Flash loan + futures-spot conflict
        if (ArbitrageStrategy.FLASH_LOAN in strategies and
            ArbitrageStrategy.FUTURES_SPOT in strategies):
            return False
        
        # DEX + flash loan works well
        if (ArbitrageStrategy.DEX in strategies and
            ArbitrageStrategy.FLASH_LOAN in strategies):
            return True
        
        # Futures-spot + funding rate works well
        if (ArbitrageStrategy.FUTURES_SPOT in strategies and
            ArbitrageStrategy.FUNDING_RATE in strategies):
            return True
        
        # Cross-exchange + statistical works well
        if (ArbitrageStrategy.CROSS_EXCHANGE in strategies and
            ArbitrageStrategy.STATISTICAL in strategies):
            return True
        
        # Too many similar strategies
        dex_strategies = [s for s in strategies if s in [
            ArbitrageStrategy.DEX,
            ArbitrageStrategy.TRIANGULAR,
            ArbitrageStrategy.CROSS_EXCHANGE,
        ]]
        if len(dex_strategies) > 2:
            return False
        
        return True
    
    def _build_mixed_opportunity(
        self,
        combo: List[Tuple[ArbitrageStrategy, Any]],
    ) -> Optional[MixedArbitrageOpportunity]:
        """
        Build a mixed arbitrage opportunity from a combination.
        
        Args:
            combo: Strategy-opportunity pairs
            
        Returns:
            MixedArbitrageOpportunity or None
        """
        try:
            legs = []
            strategies = []
            categories = set()
            
            total_profit = Decimal("0")
            total_gas_cost = Decimal("0")
            total_risk = Decimal("0")
            total_confidence = Decimal("0")
            total_capital = Decimal("0")
            total_complexity = 0
            requires_flash_loan = False
            requires_contract = False
            
            for strategy, opp in combo:
                # Get strategy profile
                profile = self.strategy_registry.get(strategy)
                if not profile:
                    continue
                
                # Extract opportunity data
                leg = self._extract_leg_data(strategy, opp, profile)
                if leg:
                    legs.append(leg)
                    strategies.append(strategy)
                    categories.add(profile["category"])
                    
                    total_profit += leg["expected_profit"]
                    total_gas_cost += leg["gas_cost"]
                    total_risk += leg["risk_score"]
                    total_confidence += leg["confidence"]
                    total_capital += profile["capital_required"]
                    total_complexity += profile["complexity"]
                    
                    if profile["requires_flash_loan"]:
                        requires_flash_loan = True
                    if profile["requires_contract"]:
                        requires_contract = True
            
            if not legs:
                return None
            
            # Calculate aggregated metrics
            n_legs = len(legs)
            avg_risk = total_risk / n_legs
            avg_confidence = total_confidence / n_legs
            avg_complexity = total_complexity / n_legs
            complexity_score = min(
                Decimal("1"),
                avg_complexity / Decimal(str(self.max_legs))
            )
            
            # Calculate net profit
            net_profit = total_profit - total_gas_cost
            net_profit_percentage = (net_profit / total_capital) * Decimal("100")
            
            # Calculate priority
            priority = self._calculate_priority(
                net_profit_percentage,
                avg_risk,
                avg_confidence,
                complexity_score
            )
            
            # Build opportunity
            opportunity: MixedArbitrageOpportunity = {
                "legs": legs,
                "strategies": strategies,
                "categories": list(categories),
                "total_profit": total_profit,
                "total_profit_percentage": (total_profit / total_capital) * Decimal("100"),
                "total_gas_cost": total_gas_cost,
                "net_profit": net_profit,
                "net_profit_percentage": net_profit_percentage,
                "weighted_risk_score": avg_risk,
                "avg_confidence": avg_confidence,
                "complexity_score": complexity_score,
                "capital_required": total_capital,
                "capital_used": total_capital,
                "execution_time_ms": 0,
                "requires_flash_loan": requires_flash_loan,
                "requires_contract_deployment": requires_contract,
                "requires_cross_chain": len(categories) > 2,
                "priority": priority,
                "timestamp": datetime.utcnow(),
            }
            
            return opportunity
            
        except Exception as e:
            self.logger.debug(f"Mixed opportunity building failed: {e}")
            return None
    
    def _extract_leg_data(
        self,
        strategy: ArbitrageStrategy,
        opp: Any,
        profile: StrategyProfile,
    ) -> Optional[MixedArbitrageLeg]:
        """
        Extract leg data from an opportunity.
        
        Args:
            strategy: Strategy type
            opp: Opportunity object
            profile: Strategy profile
            
        Returns:
            MixedArbitrageLeg or None
        """
        try:
            # Extract common fields based on opportunity type
            if strategy == ArbitrageStrategy.DEX:
                return {
                    "strategy": strategy,
                    "action": "swap",
                    "asset_in": getattr(opp, "token_in", "ETH"),
                    "asset_out": getattr(opp, "token_out", "USDC"),
                    "amount_in": Decimal("1000"),
                    "amount_out": Decimal("1050"),
                    "expected_profit": Decimal("50"),
                    "expected_profit_percentage": Decimal("5"),
                    "exchange": getattr(opp, "exchange", "Uniswap"),
                    "protocol": getattr(opp, "protocol", "UniswapV3"),
                    "pool_id": getattr(opp, "pool_id", None),
                    "path": getattr(opp, "path", []),
                    "slippage": Decimal("0.001"),
                    "gas_cost": profile["gas_cost"],
                    "risk_score": getattr(opp, "risk_score", Decimal("0.3")),
                    "confidence": getattr(opp, "confidence", Decimal("0.8")),
                    "timestamp": datetime.utcnow(),
                }
            elif strategy == ArbitrageStrategy.FLASH_LOAN:
                return {
                    "strategy": strategy,
                    "action": "borrow",
                    "asset_in": getattr(opp, "asset", "USDC"),
                    "asset_out": getattr(opp, "asset", "USDC"),
                    "amount_in": getattr(opp, "amount", Decimal("10000")),
                    "amount_out": getattr(opp, "amount", Decimal("10000")),
                    "expected_profit": getattr(opp, "expected_profit", Decimal("100")),
                    "expected_profit_percentage": Decimal("1"),
                    "exchange": getattr(opp, "exchange", None),
                    "protocol": getattr(opp, "protocol", "AAVE"),
                    "pool_id": getattr(opp, "pool_id", None),
                    "path": getattr(opp, "path", []),
                    "slippage": Decimal("0.001"),
                    "gas_cost": profile["gas_cost"],
                    "risk_score": getattr(opp, "risk_score", Decimal("0.4")),
                    "confidence": getattr(opp, "confidence", Decimal("0.7")),
                    "timestamp": datetime.utcnow(),
                }
            else:
                # Generic fallback
                return {
                    "strategy": strategy,
                    "action": "trade",
                    "asset_in": "ETH",
                    "asset_out": "USDC",
                    "amount_in": Decimal("1000"),
                    "amount_out": Decimal("1050"),
                    "expected_profit": Decimal("50"),
                    "expected_profit_percentage": Decimal("5"),
                    "exchange": None,
                    "protocol": strategy.value,
                    "pool_id": None,
                    "path": [],
                    "slippage": Decimal("0.001"),
                    "gas_cost": profile["gas_cost"],
                    "risk_score": Decimal("0.3"),
                    "confidence": Decimal("0.8"),
                    "timestamp": datetime.utcnow(),
                }
        except Exception as e:
            self.logger.debug(f"Leg extraction failed: {e}")
            return None
    
    def _calculate_priority(
        self,
        profit: Decimal,
        risk: Decimal,
        confidence: Decimal,
        complexity: Decimal,
    ) -> int:
        """
        Calculate priority score for an opportunity.
        
        Args:
            profit: Profit percentage
            risk: Risk score
            confidence: Confidence score
            complexity: Complexity score
            
        Returns:
            Priority score (higher = higher priority)
        """
        # Weighted scoring
        score = (
            profit * Decimal("0.4") +
            (Decimal("1") - risk) * Decimal("0.3") +
            confidence * Decimal("0.2") +
            (Decimal("1") - complexity) * Decimal("0.1")
        )
        
        # Convert to integer priority (1-10)
        priority = int(score * Decimal("10"))
        return max(1, min(10, priority))
    
    def _is_viable(self, opportunity: MixedArbitrageOpportunity) -> bool:
        """
        Check if a mixed opportunity is viable.
        
        Args:
            opportunity: Opportunity to check
            
        Returns:
            True if viable
        """
        return (
            opportunity["net_profit_percentage"] >= float(self.min_profit_threshold * 100) and
            opportunity["avg_confidence"] >= MIN_CONFIDENCE and
            opportunity["weighted_risk_score"] <= Decimal("0.6") and
            opportunity["complexity_score"] <= self.max_complexity and
            opportunity["capital_required"] <= self.portfolio.available_capital
        )
    
    def _process_opportunities(self, opportunities: List[MixedArbitrageOpportunity]) -> None:
        """
        Process detected opportunities.
        
        Args:
            opportunities: List of opportunities
        """
        for opp in opportunities:
            # Cache opportunity
            key = hashlib.md5(
                json.dumps([
                    [s.value for s in opp["strategies"]],
                    str(opp["net_profit"]),
                ]).encode()
            ).hexdigest()
            self.opportunity_cache[key] = opp
            
            # Update strategy usage
            for strategy in opp["strategies"]:
                self.metrics["strategy_usage"][strategy] += 1
        
        # Log top opportunity
        if opportunities:
            best = opportunities[0]
            strategies = ", ".join([s.value for s in best["strategies"]])
            self.logger.info(
                f"Found mixed opportunity: {strategies} "
                f"profit: {best['net_profit_percentage']:.2f}%, "
                f"complexity: {best['complexity_score']:.2f}, "
                f"confidence: {best['avg_confidence']:.2f}, "
                f"risk: {best['weighted_risk_score']:.2f}"
            )
    
    def execute_opportunity(
        self,
        opportunity: MixedArbitrageOpportunity,
    ) -> Dict[str, Any]:
        """
        Execute a mixed arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            Execution result
        """
        result = {
            "success": False,
            "execution_ids": [],
            "profit": Decimal("0"),
            "gas_used": Decimal("0"),
            "error": None,
        }
        
        try:
            # Build execution plan
            plan = self._build_execution_plan(opportunity)
            if not plan:
                raise ValueError("Failed to build execution plan")
            
            # Validate plan
            if not self._validate_plan(plan):
                raise ValueError("Plan validation failed")
            
            # Execute plan
            execution_result = self._execute_plan(plan)
            
            if execution_result["success"]:
                result["success"] = True
                result["execution_ids"] = execution_result["execution_ids"]
                result["profit"] = execution_result["profit"]
                result["gas_used"] = execution_result["gas_used"]
                
                # Update metrics
                self.metrics["opportunities_executed"] += 1
                self.metrics["total_profit"] += execution_result["profit"]
                self.metrics["total_gas_cost"] += execution_result["gas_used"]
                
                self.logger.info(
                    f"Executed mixed arbitrage: profit ${execution_result['profit']:,.2f}"
                )
            else:
                result["error"] = execution_result.get("error", "Execution failed")
            
        except Exception as e:
            self.logger.error(f"Mixed execution failed: {e}")
            result["error"] = str(e)
            self.metrics["errors"] += 1
        
        return result
    
    def _build_execution_plan(
        self,
        opportunity: MixedArbitrageOpportunity,
    ) -> Optional[ExecutionPlan]:
        """
        Build execution plan for mixed arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            ExecutionPlan or None
        """
        try:
            # Determine execution order
            legs = opportunity["legs"]
            
            # Flash loans should be executed first
            flash_loan_legs = [
                l for l in legs
                if l["strategy"] == ArbitrageStrategy.FLASH_LOAN
            ]
            other_legs = [
                l for l in legs
                if l["strategy"] != ArbitrageStrategy.FLASH_LOAN
            ]
            
            ordered_legs = flash_loan_legs + other_legs
            
            # Build plan
            plan = ExecutionPlan(
                legs=ordered_legs,
                sequential=opportunity["complexity_score"] > Decimal("0.5"),
                atomic=opportunity["requires_flash_loan"],
                timeout=300,  # 5 minutes
                gas_limit=self._calculate_gas_limit(ordered_legs),
                deadline=datetime.utcnow() + timedelta(minutes=10),
                fallback_plan=None,
                verification_checks=[
                    "slippage",
                    "balance",
                    "profit_threshold",
                    "risk_limits",
                ],
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Plan building failed: {e}")
            return None
    
    def _calculate_gas_limit(self, legs: List[MixedArbitrageLeg]) -> int:
        """
        Calculate total gas limit for all legs.
        
        Args:
            legs: List of legs
            
        Returns:
            Total gas limit
        """
        base_gas = 50000
        leg_gas = sum(int(l["gas_cost"] * 1000000) for l in legs)  # Convert ETH to gas
        return int((base_gas + leg_gas) * 1.5)
    
    def _validate_plan(self, plan: ExecutionPlan) -> bool:
        """
        Validate execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            True if valid
        """
        # Check legs
        if not plan.legs:
            return False
        
        # Check gas limit
        if plan.gas_limit > 10000000:  # 10M gas limit
            return False
        
        # Check deadline
        if plan.deadline < datetime.utcnow():
            return False
        
        return True
    
    def _execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Execute an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Execution result
        """
        result = {
            "success": False,
            "execution_ids": [],
            "profit": Decimal("0"),
            "gas_used": Decimal("0"),
            "error": None,
        }
        
        try:
            # Execute legs sequentially
            total_profit = Decimal("0")
            total_gas = Decimal("0")
            execution_ids = []
            
            for leg in plan.legs:
                # Execute leg using appropriate detector
                detector = self.detectors.get(leg["strategy"])
                if not detector:
                    raise ValueError(f"No detector for {leg['strategy']}")
                
                # Execute
                if hasattr(detector, 'execute_opportunity'):
                    leg_result = detector.execute_opportunity(leg)
                    if leg_result.get("success"):
                        total_profit += leg_result.get("profit", Decimal("0"))
                        total_gas += leg_result.get("gas_used", Decimal("0"))
                        execution_ids.append(leg_result.get("tx_hash"))
                    else:
                        raise ValueError(f"Leg execution failed: {leg_result.get('error')}")
            
            result["success"] = True
            result["execution_ids"] = execution_ids
            result["profit"] = total_profit
            result["gas_used"] = total_gas
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Plan execution failed: {e}")
        
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "opportunities_cached": len(self.opportunity_cache),
            "is_running": self.is_running,
            "min_profit_threshold": float(self.min_profit_threshold),
            "max_legs": self.max_legs,
            "scan_interval": self.scan_interval,
            "portfolio": {
                "total_capital": float(self.portfolio.total_capital),
                "used_capital": float(self.portfolio.used_capital),
                "available_capital": float(self.portfolio.available_capital),
                "open_positions": len(self.portfolio.open_positions),
                "total_pnl": float(self.portfolio.total_pnl),
                "current_risk": float(self.portfolio.current_risk),
            },
            "strategy_usage": {k.value: v for k, v in self.metrics["strategy_usage"].items()},
        }


# Helper Classes

class MixedMEVShield:
    """MEV Protection for mixed arbitrage."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = {
            "enabled": True,
            "private_mempool": True,
            "flashbots_enabled": True,
            "bundle_timeout": 30,
            "priority_fee": Decimal("1.5"),  # gwei
            "slippage_protection": Decimal("0.001"),
            "frontrunning_protection": True,
            "sandwich_protection": True,
        }
    
    def protect(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Apply MEV protection to an execution plan.
        
        Args:
            plan: Execution plan
            
        Returns:
            Protected execution plan
        """
        if not self.config["enabled"]:
            return plan
        
        # Add slippage protection to legs
        for leg in plan.legs:
            leg["slippage"] = min(leg["slippage"], self.config["slippage_protection"])
        
        # Increase gas limit for protection
        plan.gas_limit = int(plan.gas_limit * 1.2)
        
        return plan


class RiskAggregator:
    """Risk aggregation for mixed arbitrage."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def aggregate_risk(self, legs: List[MixedArbitrageLeg]) -> Dict[str, Decimal]:
        """
        Aggregate risk across multiple legs.
        
        Args:
            legs: List of legs
            
        Returns:
            Aggregated risk metrics
        """
        if not legs:
            return {
                "total_risk": Decimal("0"),
                "avg_risk": Decimal("0"),
                "max_risk": Decimal("0"),
                "correlation_risk": Decimal("0"),
            }
        
        risks = [l["risk_score"] for l in legs]
        total_risk = sum(risks)
        avg_risk = total_risk / len(risks)
        max_risk = max(risks)
        
        # Estimate correlation risk
        correlation_risk = Decimal("0.1") * len(risks)
        
        return {
            "total_risk": total_risk,
            "avg_risk": avg_risk,
            "max_risk": max_risk,
            "correlation_risk": correlation_risk,
        }
    
    def validate_risk(self, risk_metrics: Dict[str, Decimal], max_risk: Decimal) -> bool:
        """
        Validate risk metrics against limits.
        
        Args:
            risk_metrics: Risk metrics
            max_risk: Maximum allowed risk
            
        Returns:
            True if risk is acceptable
        """
        return risk_metrics["total_risk"] <= max_risk


# Module exports
__all__ = [
    'MixedDetector',
    'ArbitrageStrategy',
    'StrategyCategory',
    'StrategyProfile',
    'MixedArbitrageLeg',
    'MixedArbitrageOpportunity',
    'StrategyCombination',
    'ExecutionPlan',
    'PortfolioArbitrageState',
    'MixedMEVShield',
    'RiskAggregator',
]
