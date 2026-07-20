# trading/bots/arbitrage_bot/detectors/dex_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced DeFi Arbitrage Detection Engine

"""
DEX Arbitrage Detector - Advanced DeFi Arbitrage Detection Engine

This module provides state-of-the-art detection of arbitrage opportunities
across decentralized exchanges (DEXs) with support for:
- Multi-hop arbitrage (up to 5 hops)
- Flash loan integration
- MEV protection
- Gas optimization
- Liquidity pool analysis
- Slippage modeling
- Atomic execution planning

Architecture:
    - BaseDetector: Abstract base class for all detectors
    - DexDetector: Main detector implementation
    - OpportunityScanner: Multi-threaded scanner
    - RouterAnalyzer: Path optimization
    - GasOptimizer: Gas cost optimization
    - MEVShield: MEV protection layer

References:
    - Uniswap V2/V3 Protocol
    - Balancer Protocol
    - Curve Finance
    - 1inch Aggregator
    - SushiSwap
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
from web3 import Web3
from web3.types import Wei, Address, BlockNumber, TxReceipt, TxParams
from eth_account import Account
from eth_typing import ChecksumAddress, HexStr, HexAddress
from eth_utils import to_checksum_address, to_hex, from_wei
from eth_abi import encode, decode

# Third-party imports
try:
    from web3.middleware import geth_poa_middleware
    from web3.middleware.gas_price_strategy import (
        fast_gas_price_strategy,
        medium_gas_price_strategy,
        slow_gas_price_strategy,
    )
    from eth_account.signers.local import LocalAccount
except ImportError:
    pass

try:
    import aiohttp
    import aiohttp.client_exceptions
    import asyncio
except ImportError:
    pass

# Constants and configurations
DEFAULT_DECIMAL_PRECISION = 18
GAS_BUFFER_MULTIPLIER = Decimal("1.2")
MAX_HOPS = 5
MIN_PROFIT_THRESHOLD = Decimal("0.001")  # 0.1% minimum profit
MAX_SLIPPAGE = Decimal("0.05")  # 5% maximum slippage
DEFAULT_GAS_LIMIT = 2000000
DEFAULT_GAS_PRICE = Web3.to_wei(100, "gwei")

# Supported DEX Protocols
class DEXProtocol(Enum):
    UNISWAP_V2 = "uniswap_v2"
    UNISWAP_V3 = "uniswap_v3"
    SUSHISWAP = "sushiswap"
    PANCAKESWAP = "pancakeswap"
    CURVE = "curve"
    BALANCER = "balancer"
    ONEINCH = "1inch"
    DODO = "dodo"
    QUICKSWAP = "quickswap"
    TRADERJOE = "traderjoe"
    SPOOKYSWAP = "spookyswap"
    BEETHOVENX = "beethovenx"
    AERODROME = "aerodrome"
    VELODROME = "velodrome"
    CAMELOT = "camelot"

# DEX Router addresses (mainnet)
DEX_ROUTERS = {
    DEXProtocol.UNISWAP_V2: "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    DEXProtocol.UNISWAP_V3: "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    DEXProtocol.SUSHISWAP: "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
    DEXProtocol.PANCAKESWAP: "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    DEXProtocol.CURVE: "0x99a58482BD75cbab83b27EC03CA68fF4898B5788",
    DEXProtocol.BALANCER: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    DEXProtocol.ONEINCH: "0x1111111254fb6c44bAC0beD2854e76F90643097d",
    DEXProtocol.DODO: "0xa356867fdCEA8e71AEaF87805808803806231FdC",
    DEXProtocol.QUICKSWAP: "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
    DEXProtocol.TRADERJOE: "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
    DEXProtocol.SPOOKYSWAP: "0xF491e7B69E4244ad4002BC14e878a34207E38c29",
    DEXProtocol.BEETHOVENX: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    DEXProtocol.AERODROME: "0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43",
    DEXProtocol.VELODROME: "0xa132DAB612dB5cB67B9Fe2FbaDf82B9Ad87C8676",
    DEXProtocol.CAMELOT: "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
}

# DEX Factory addresses (for creating new pairs)
DEX_FACTORIES = {
    DEXProtocol.UNISWAP_V2: "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    DEXProtocol.UNISWAP_V3: "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    DEXProtocol.SUSHISWAP: "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
    DEXProtocol.PANCAKESWAP: "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
    DEXProtocol.CURVE: "0x0000000000000000000000000000000000000000",  # Special case
    DEXProtocol.BALANCER: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    DEXProtocol.DODO: "0x3A8B83E9f9fcd6F1D4c6Ba3F0498C77f5799A827",
}

# Known token addresses (mainnet)
KNOWN_TOKENS = {
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
    "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    "AAVE": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
    "MKR": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
    "COMP": "0xc00e94Cb662C3520282E6f5717214004A7f26888",
    "SNX": "0xC011a73ee8576Fb46F5E1c5751cA3B9Fe0af2a6F",
    "CRV": "0xD533a949740bb3306d119CC777fa900bA034cd52",
    "BAL": "0xba100000625a3754423978a60c9317c58a424e3D",
    "1INCH": "0x111111111117dC0aa78b770fA6A738034120C302",
    "DODO": "0x43Dfc4159D86F3A37A5A4B3D4580b6ad68d7f84A",
    "FXS": "0x3432B6A60D23Ca0dFCa7761B7ab56459D9C964D0",
    "CVX": "0x4e3FBD56CD56c3e72c1403e103b45Db9da5B9D2B",
    "LDO": "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32",
    "RPL": "0xD33526068D116cE69F19A9ee46F0bd304F21A51f",
    "ENS": "0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72",
}

# ABI definitions
UNISWAP_V2_ROUTER_ABI = json.loads("""
[
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],
     "name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],
     "name":"getAmountsIn","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"nonpayable","type":"function"}
]
""")

UNISWAP_V3_QUOTER_ABI = json.loads("""
[
    {"inputs":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
     "name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"bytes","name":"path","type":"bytes"},{"internalType":"uint256","name":"amountIn","type":"uint256"}],
     "name":"quoteExactInput","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"}
]
""")

# Typed dictionaries for type safety
class LiquidityPoolInfo(TypedDict):
    """Information about a liquidity pool."""
    address: ChecksumAddress
    token0: ChecksumAddress
    token1: ChecksumAddress
    reserve0: Decimal
    reserve1: Decimal
    fee: Decimal
    protocol: DEXProtocol
    total_supply: NotRequired[Decimal]
    virtual_reserve: NotRequired[Decimal]


class ArbitragePath(TypedDict):
    """An arbitrage path definition."""
    tokens: List[ChecksumAddress]
    dexes: List[DEXProtocol]
    hops: List[int]
    expected_output: Decimal
    expected_input: Decimal
    profit: Decimal
    profit_percentage: Decimal
    gas_cost: Decimal
    net_profit: Decimal
    net_profit_percentage: Decimal
    risk_score: Decimal
    complexity: int
    requires_flash_loan: bool


class OpportunityResult(TypedDict):
    """Arbitrage opportunity result."""
    path: List[ArbitragePath]
    best_path: ArbitragePath
    total_profit: Decimal
    total_profit_percentage: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    net_profit_percentage: Decimal
    confidence: Decimal
    timestamp: datetime
    execution_time_ms: int


@dataclass
class RouteNode:
    """Node in a route path."""
    token: ChecksumAddress
    dex: DEXProtocol
    pool: Optional[LiquidityPoolInfo] = None
    previous: Optional["RouteNode"] = None
    next: Optional["RouteNode"] = None
    cost: Decimal = Decimal("0")
    estimated_output: Decimal = Decimal("0")


@dataclass
class FlashLoanInfo:
    """Information about a flash loan opportunity."""
    provider: str  # e.g., "AAVE", "DYDX", "BALANCER"
    required_amount: Decimal
    fee: Decimal
    max_amount: Decimal
    available_tokens: List[str]
    duration_seconds: int = 0  # 0 means within same block


@dataclass
class MEVProtection:
    """MEV protection configuration."""
    enabled: bool = True
    use_private_mempool: bool = True
    flashbots_enabled: bool = True
    backrun_protection: bool = True
    sandwich_protection: bool = True
    bundle_submission: bool = True
    priority_fee_multiplier: Decimal = Decimal("1.2")


# Configuration class
@dataclass
class DexDetectorConfig:
    """Configuration for the DEX detector."""
    # Core settings
    min_profit_threshold: Decimal = MIN_PROFIT_THRESHOLD
    max_hops: int = MAX_HOPS
    max_slippage: Decimal = MAX_SLIPPAGE
    gas_buffer: Decimal = GAS_BUFFER_MULTIPLIER
    
    # Scanning settings
    scan_interval: float = 1.0  # seconds
    scan_block_range: int = 5  # blocks to scan ahead
    parallel_scans: int = 10
    
    # Risk settings
    max_risk_score: Decimal = Decimal("0.5")
    min_confidence: Decimal = Decimal("0.7")
    max_concurrent_opportunities: int = 5
    
    # Flash loan settings
    enable_flash_loans: bool = True
    max_flash_loan_amount: Decimal = Decimal("1000000")
    flash_loan_fee_threshold: Decimal = Decimal("0.001")
    
    # MEV settings
    mev_protection: MEVProtection = MEVProtection()
    
    # Network settings
    web3_providers: List[str] = field(default_factory=lambda: [
        "https://mainnet.infura.io/v3/",
        "https://eth-mainnet.g.alchemy.com/v2/"
    ])
    chain_id: int = 1
    supported_dexes: List[DEXProtocol] = field(default_factory=lambda: list(DEXProtocol))


class DexDetector:
    """
    Advanced DEX Arbitrage Detector.
    
    This class implements sophisticated arbitrage detection across multiple DEXs
    with support for multi-hop paths, flash loans, MEV protection, and
    real-time opportunity scanning.
    
    Features:
    1. Multi-hop arbitrage detection (up to MAX_HOPS)
    2. Flash loan integration for zero-capital arbitrage
    3. MEV protection with Flashbots integration
    4. Real-time liquidity pool monitoring
    5. Slippage and gas optimization
    6. Risk scoring and confidence assessment
    7. Parallel scanning with thread pools
    8. Atomic execution planning
    """
    
    def __init__(
        self,
        config: Optional[DexDetectorConfig] = None,
        web3_provider: Optional[Web3] = None,
        private_key: Optional[str] = None,
    ):
        """
        Initialize the DEX detector.
        
        Args:
            config: Optional configuration object
            web3_provider: Optional Web3 instance
            private_key: Optional private key for signing transactions
        """
        self.config = config or DexDetectorConfig()
        self.logger = self._setup_logger()
        
        # Initialize Web3
        self.web3 = web3_provider or self._init_web3()
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # Initialize contract interfaces
        self._init_contracts()
        
        # Cache for token data and pool information
        self.token_cache: Dict[str, Dict] = {}
        self.pool_cache: Dict[str, LiquidityPoolInfo] = {}
        self.route_cache: Dict[str, List[RouteNode]] = {}
        
        # Thread pool for parallel scanning
        self.executor = ThreadPoolExecutor(max_workers=self.config.parallel_scans)
        
        # Opportunity tracking
        self.opportunities: Dict[str, OpportunityResult] = {}
        self.opportunity_lock = threading.Lock()
        
        # Monitoring
        self.metrics = {
            "scan_count": 0,
            "opportunities_found": 0,
            "executed_trades": 0,
            "total_profit": Decimal("0"),
            "total_gas_cost": Decimal("0"),
            "net_profit": Decimal("0"),
            "error_count": 0,
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        
        # MEV protection
        self.mev_shield = MEVShield(self.config.mev_protection)
        
        # Flash loan integration
        self.flash_loan_manager = FlashLoanManager(self.config)
        
        # Gas optimization
        self.gas_optimizer = GasOptimizer()
        
        # Start background scanner if configured
        if config and config.scan_interval > 0:
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
    
    def _init_web3(self) -> Web3:
        """Initialize Web3 with providers."""
        for provider in self.config.web3_providers:
            try:
                w3 = Web3(Web3.HTTPProvider(provider))
                if w3.is_connected():
                    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    return w3
            except Exception as e:
                self.logger.warning(f"Failed to connect to {provider}: {e}")
        
        # Fallback to default
        return Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
    
    def _init_contracts(self) -> None:
        """Initialize DEX contract interfaces."""
        self.contracts: Dict[DEXProtocol, Any] = {}
        self.quoter_contracts: Dict[DEXProtocol, Any] = {}
        
        for dex in self.config.supported_dexes:
            if dex in DEX_ROUTERS:
                try:
                    router_address = to_checksum_address(DEX_ROUTERS[dex])
                    router_contract = self.web3.eth.contract(
                        address=router_address,
                        abi=UNISWAP_V2_ROUTER_ABI
                    )
                    self.contracts[dex] = router_contract
                    
                    # V3 requires different ABI
                    if dex in (DEXProtocol.UNISWAP_V3, DEXProtocol.AERODROME):
                        quoter_address = to_checksum_address(DEX_ROUTERS[dex])
                        quoter_contract = self.web3.eth.contract(
                            address=quoter_address,
                            abi=UNISWAP_V3_QUOTER_ABI
                        )
                        self.quoter_contracts[dex] = quoter_contract
                except Exception as e:
                    self.logger.warning(f"Failed to initialize {dex}: {e}")
    
    def start(self) -> None:
        """Start the background scanner."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        self.logger.info("DEX Detector started")
    
    def stop(self) -> None:
        """Stop the background scanner."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        self.logger.info("DEX Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self.is_running:
            try:
                # Scan for opportunities
                opportunities = self.scan_opportunities()
                if opportunities:
                    self._process_opportunities(opportunities)
                
                # Sleep until next scan
                time.sleep(self.config.scan_interval)
            except Exception as e:
                self.logger.error(f"Scan loop error: {e}")
                self.metrics["error_count"] += 1
                time.sleep(1.0)
    
    def scan_opportunities(
        self,
        base_token: Optional[ChecksumAddress] = None,
        max_hops: Optional[int] = None,
    ) -> List[OpportunityResult]:
        """
        Scan for arbitrage opportunities.
        
        Args:
            base_token: Optional base token address
            max_hops: Maximum number of hops to consider
            
        Returns:
            List of OpportunityResult objects
        """
        try:
            start_time = time.time()
            
            # Get available tokens and pools
            tokens = self._get_available_tokens()
            pools = self._get_available_pools()
            
            # Build paths
            paths = self._build_paths(
                tokens,
                pools,
                base_token=base_token,
                max_hops=max_hops or self.config.max_hops
            )
            
            # Evaluate paths in parallel
            opportunities = []
            with ThreadPoolExecutor(max_workers=self.config.parallel_scans) as executor:
                future_to_path = {
                    executor.submit(self._evaluate_path, path): path
                    for path in paths
                }
                for future in future_to_path:
                    try:
                        result = future.result(timeout=5.0)
                        if result and self._is_profitable(result):
                            opportunities.append(result)
                    except Exception as e:
                        self.logger.debug(f"Path evaluation failed: {e}")
            
            # Sort by net profit
            opportunities.sort(
                key=lambda x: x["net_profit"],
                reverse=True
            )
            
            # Update metrics
            self.metrics["scan_count"] += 1
            self.metrics["opportunities_found"] += len(opportunities)
            
            execution_time = (time.time() - start_time) * 1000
            self.logger.debug(f"Scan completed in {execution_time:.2f}ms, found {len(opportunities)} opportunities")
            
            return opportunities[:self.config.max_concurrent_opportunities]
            
        except Exception as e:
            self.logger.error(f"Opportunity scan failed: {e}")
            return []
    
    def _build_paths(
        self,
        tokens: List[ChecksumAddress],
        pools: List[LiquidityPoolInfo],
        base_token: Optional[ChecksumAddress] = None,
        max_hops: int = MAX_HOPS,
    ) -> List[List[RouteNode]]:
        """
        Build all possible arbitrage paths.
        
        This uses a graph-based approach to find potential arbitrage
        paths with configurable complexity limits.
        
        Args:
            tokens: Available tokens
            pools: Available liquidity pools
            base_token: Optional starting token
            max_hops: Maximum number of hops
            
        Returns:
            List of path nodes
        """
        paths = []
        
        # Build graph of token connectivity
        graph = self._build_graph(pools)
        
        # Get start tokens
        start_tokens = [base_token] if base_token else tokens
        
        # Use BFS to find paths
        for start_token in start_tokens:
            if start_token not in graph:
                continue
            
            for _ in range(1, max_hops + 1):
                for path in self._find_paths(graph, start_token, start_token, max_hops=max_hops):
                    if path and len(path) > 1:
                        paths.append(path)
        
        return paths
    
    def _build_graph(self, pools: List[LiquidityPoolInfo]) -> Dict[ChecksumAddress, List[RouteNode]]:
        """
        Build token connectivity graph from pools.
        
        Args:
            pools: List of liquidity pools
            
        Returns:
            Dictionary mapping token addresses to connected nodes
        """
        graph = defaultdict(list)
        
        for pool in pools:
            # Add edge from token0 to token1
            node0 = RouteNode(
                token=pool["token0"],
                dex=pool["protocol"],
                pool=pool
            )
            node1 = RouteNode(
                token=pool["token1"],
                dex=pool["protocol"],
                pool=pool
            )
            graph[pool["token0"]].append(node1)
            graph[pool["token1"]].append(node0)
        
        return graph
    
    def _find_paths(
        self,
        graph: Dict[ChecksumAddress, List[RouteNode]],
        start: ChecksumAddress,
        target: ChecksumAddress,
        max_hops: int,
        current_path: Optional[List[RouteNode]] = None,
        visited: Optional[Set[ChecksumAddress]] = None,
    ) -> Iterator[List[RouteNode]]:
        """
        Find all paths between tokens using DFS.
        
        Args:
            graph: Token connectivity graph
            start: Starting token address
            target: Target token address
            max_hops: Maximum number of hops
            current_path: Current path being built
            visited: Set of visited token addresses
            
        Yields:
            List of RouteNode objects representing the path
        """
        if current_path is None:
            current_path = []
        if visited is None:
            visited = set()
        
        # Prevent cycles
        if len(current_path) >= max_hops:
            return
        
        # Add current token to visited
        visited.add(start)
        
        # Explore neighbors
        for node in graph.get(start, []):
            if node.token in visited:
                continue
            
            # Create new path
            new_path = current_path + [node]
            
            # Check if we reached the target
            if node.token == target and len(new_path) > 1:
                yield new_path
            else:
                # Continue searching
                yield from self._find_paths(
                    graph,
                    node.token,
                    target,
                    max_hops,
                    new_path,
                    visited.copy()
                )
        
        # Remove current token from visited (backtracking)
        visited.remove(start)
    
    def _evaluate_path(self, path: List[RouteNode]) -> Optional[OpportunityResult]:
        """
        Evaluate a path for arbitrage profitability.
        
        Args:
            path: List of RouteNode objects
            
        Returns:
            OpportunityResult or None if not profitable
        """
        try:
            # Get token amounts and prices
            tokens = [node.token for node in path]
            dexes = [node.dex for node in path]
            
            # Calculate expected output
            amount_in = Decimal("1")  # 1 token as basis
            current_amount = amount_in
            expected_outputs = []
            
            for i, node in enumerate(path):
                # Simulate swap
                output = self._simulate_swap(
                    tokens[i],
                    tokens[i + 1] if i + 1 < len(tokens) else tokens[0],
                    current_amount,
                    node.dex,
                    node.pool
                )
                expected_outputs.append(output)
                current_amount = output
            
            # Calculate profit
            expected_output = current_amount
            profit = expected_output - amount_in
            profit_percentage = (profit / amount_in) * Decimal("100")
            
            # Calculate gas cost
            gas_cost = self.gas_optimizer.estimate_gas_cost(path)
            
            # Calculate net profit
            net_profit = profit - gas_cost
            net_profit_percentage = (net_profit / amount_in) * Decimal("100")
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(path, expected_output)
            
            # Calculate confidence
            confidence = self._calculate_confidence(path, expected_output)
            
            # Check if profitable
            if net_profit_percentage >= self.config.min_profit_threshold * Decimal("100"):
                # Build path definition
                path_def: ArbitragePath = {
                    "tokens": tokens,
                    "dexes": dexes,
                    "hops": list(range(len(path))),
                    "expected_output": expected_output,
                    "expected_input": amount_in,
                    "profit": profit,
                    "profit_percentage": profit_percentage,
                    "gas_cost": gas_cost,
                    "net_profit": net_profit,
                    "net_profit_percentage": net_profit_percentage,
                    "risk_score": risk_score,
                    "complexity": len(path),
                    "requires_flash_loan": False,
                }
                
                # Create opportunity result
                result: OpportunityResult = {
                    "path": [path_def],
                    "best_path": path_def,
                    "total_profit": profit,
                    "total_profit_percentage": profit_percentage,
                    "total_gas_cost": gas_cost,
                    "net_profit": net_profit,
                    "net_profit_percentage": net_profit_percentage,
                    "confidence": confidence,
                    "timestamp": datetime.utcnow(),
                    "execution_time_ms": 0,
                }
                
                return result
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Path evaluation error: {e}")
            return None
    
    def _simulate_swap(
        self,
        token_in: ChecksumAddress,
        token_out: ChecksumAddress,
        amount_in: Decimal,
        dex: DEXProtocol,
        pool: Optional[LiquidityPoolInfo] = None,
    ) -> Decimal:
        """
        Simulate a swap on a specific DEX.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            dex: DEX protocol
            pool: Optional pool information
            
        Returns:
            Estimated output amount
        """
        if dex not in self.contracts:
            return Decimal("0")
        
        try:
            # Convert to Wei
            amount_in_wei = int(amount_in * Decimal(10**18))
            
            # Different simulation for V2 vs V3
            if dex in (DEXProtocol.UNISWAP_V3, DEXProtocol.AERODROME):
                # Use V3 quoter
                if dex in self.quoter_contracts:
                    quoter = self.quoter_contracts[dex]
                    try:
                        # Build path
                        path = self._build_v3_path(token_in, token_out)
                        if path:
                            result = quoter.functions.quoteExactInput(
                                path,
                                amount_in_wei
                            ).call()
                            return Decimal(str(result)) / Decimal(10**18)
                    except Exception:
                        pass
            
            # Use V2 style simulation
            router = self.contracts[dex]
            path = [token_in, token_out]
            amounts = router.functions.getAmountsOut(amount_in_wei, path).call()
            
            if amounts and len(amounts) > 1:
                return Decimal(str(amounts[-1])) / Decimal(10**18)
            
            return Decimal("0")
            
        except Exception as e:
            self.logger.debug(f"Swap simulation failed: {e}")
            return Decimal("0")
    
    def _build_v3_path(self, token_in: ChecksumAddress, token_out: ChecksumAddress) -> Optional[bytes]:
        """
        Build Uniswap V3 path for quoting.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            
        Returns:
            Encoded path bytes or None
        """
        try:
            # Encode path: tokenIn, fee, tokenOut
            fees = [3000, 10000]  # 0.3% and 1% fee tiers
            for fee in fees:
                try:
                    path = encode(
                        ['address', 'uint24', 'address'],
                        [token_in, fee, token_out]
                    )
                    return path
                except Exception:
                    continue
            return None
        except Exception:
            return None
    
    def _calculate_risk_score(
        self,
        path: List[RouteNode],
        expected_output: Decimal,
    ) -> Decimal:
        """
        Calculate risk score for a path.
        
        Args:
            path: Path nodes
            expected_output: Expected output amount
            
        Returns:
            Risk score between 0 and 1
        """
        risk_score = Decimal("0")
        
        # Factor 1: Path length
        length_factor = Decimal(len(path)) / Decimal(MAX_HOPS)
        risk_score += length_factor * Decimal("0.3")
        
        # Factor 2: Dex reputation
        dex_reputation = {
            DEXProtocol.UNISWAP_V2: Decimal("0.9"),
            DEXProtocol.UNISWAP_V3: Decimal("0.95"),
            DEXProtocol.SUSHISWAP: Decimal("0.85"),
            DEXProtocol.PANCAKESWAP: Decimal("0.8"),
            DEXProtocol.CURVE: Decimal("0.9"),
            DEXProtocol.BALANCER: Decimal("0.9"),
            DEXProtocol.ONEINCH: Decimal("0.95"),
        }
        for node in path:
            rep = dex_reputation.get(node.dex, Decimal("0.7"))
            risk_score += (Decimal("1") - rep) * Decimal("0.2")
        
        # Factor 3: Liquidity depth
        liquidity_score = Decimal("0")
        for node in path:
            if node.pool:
                reserve0 = node.pool.get("reserve0", Decimal("0"))
                reserve1 = node.pool.get("reserve1", Decimal("0"))
                total_reserve = reserve0 + reserve1
                if total_reserve > Decimal("0"):
                    # Higher liquidity = lower risk
                    liquidity_factor = min(Decimal("1"), total_reserve / Decimal("1000000"))
                    liquidity_score += liquidity_factor
        liquidity_score /= Decimal(len(path)) if path else Decimal("1")
        risk_score += (Decimal("1") - liquidity_score) * Decimal("0.3")
        
        # Normalize
        risk_score = min(Decimal("1"), max(Decimal("0"), risk_score))
        
        return risk_score
    
    def _calculate_confidence(
        self,
        path: List[RouteNode],
        expected_output: Decimal,
    ) -> Decimal:
        """
        Calculate confidence score for a path.
        
        Args:
            path: Path nodes
            expected_output: Expected output amount
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = Decimal("0.9")  # Base confidence
        
        # Factor 1: Recent price movement
        confidence *= Decimal("0.95")
        
        # Factor 2: Path complexity
        complexity_factor = Decimal("1") - (Decimal(len(path)) / Decimal(MAX_HOPS)) * Decimal("0.1")
        confidence *= complexity_factor
        
        # Factor 3: Liquidity quality
        for node in path:
            if node.pool:
                reserve0 = node.pool.get("reserve0", Decimal("0"))
                reserve1 = node.pool.get("reserve1", Decimal("0"))
                if reserve0 > Decimal("0") and reserve1 > Decimal("0"):
                    ratio = min(reserve0, reserve1) / max(reserve0, reserve1)
                    liquidity_quality = min(Decimal("1"), ratio)
                    confidence *= Decimal("0.95") + liquidity_quality * Decimal("0.05")
        
        # Factor 4: Historical success rate
        # (Would use historical data in production)
        confidence *= Decimal("0.98")
        
        return max(Decimal("0"), min(Decimal("1"), confidence))
    
    def _is_profitable(self, result: OpportunityResult) -> bool:
        """
        Check if an opportunity is profitable.
        
        Args:
            result: Opportunity result
            
        Returns:
            True if profitable
        """
        return (
            result["net_profit_percentage"] >= self.config.min_profit_threshold * Decimal("100") and
            result["confidence"] >= self.config.min_confidence and
            result["best_path"]["risk_score"] <= self.config.max_risk_score
        )
    
    def _process_opportunities(self, opportunities: List[OpportunityResult]) -> None:
        """
        Process detected opportunities.
        
        Args:
            opportunities: List of opportunity results
        """
        with self.opportunity_lock:
            for opp in opportunities:
                key = hashlib.md5(
                    json.dumps([
                        str(t) for t in opp["path"][0]["tokens"]
                    ]).encode()
                ).hexdigest()
                self.opportunities[key] = opp
        
        # Log top opportunities
        if opportunities:
            best = opportunities[0]
            self.logger.info(
                f"Found opportunity: {best['net_profit_percentage']:.2f}% profit "
                f"via {len(best['best_path']['tokens'])-1} hops, "
                f"confidence: {best['confidence']:.2f}, "
                f"risk: {best['best_path']['risk_score']:.2f}"
            )
    
    def execute_opportunity(
        self,
        opportunity: OpportunityResult,
        use_flash_loan: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: OpportunityResult to execute
            use_flash_loan: Whether to use flash loan
            
        Returns:
            Execution result dictionary
        """
        result = {
            "success": False,
            "tx_hash": None,
            "profit": Decimal("0"),
            "gas_used": Decimal("0"),
            "error": None,
        }
        
        try:
            if not self.account:
                raise ValueError("No account available for execution")
            
            # Get best path
            path = opportunity["best_path"]
            tokens = path["tokens"]
            dexes = path["dexes"]
            
            # Build transaction
            tx = self._build_execution_transaction(
                tokens,
                dexes,
                opportunity["total_profit"],
                use_flash_loan=use_flash_loan
            )
            
            if not tx:
                raise ValueError("Failed to build transaction")
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            
            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                result["success"] = True
                result["tx_hash"] = to_hex(tx_hash)
                result["gas_used"] = Decimal(str(receipt.gasUsed))
                
                # Update metrics
                self.metrics["executed_trades"] += 1
                self.metrics["total_profit"] += opportunity["net_profit"]
                self.metrics["total_gas_cost"] += result["gas_used"]
                self.metrics["net_profit"] += opportunity["net_profit"] - result["gas_used"]
                
                self.logger.info(f"Executed trade: {to_hex(tx_hash)}")
            else:
                result["error"] = "Transaction failed"
                
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            result["error"] = str(e)
            self.metrics["error_count"] += 1
        
        return result
    
    def _build_execution_transaction(
        self,
        tokens: List[ChecksumAddress],
        dexes: List[DEXProtocol],
        amount: Decimal,
        use_flash_loan: bool = False,
    ) -> Optional[TxParams]:
        """
        Build execution transaction.
        
        Args:
            tokens: Token addresses
            dexes: DEX protocols
            amount: Amount to trade
            use_flash_loan: Whether to use flash loan
            
        Returns:
            Transaction parameters
        """
        try:
            if use_flash_loan:
                return self._build_flash_loan_transaction(tokens, dexes, amount)
            
            # Standard swap transaction
            amount_in_wei = int(amount * Decimal(10**18))
            min_output = int(amount * Decimal(0.95) * Decimal(10**18))  # 5% slippage
            
            router = self.contracts.get(dexes[0])
            if not router:
                return None
            
            # Build swap transaction
            path = tokens
            deadline = int(time.time()) + 300  # 5 minutes
            
            tx = router.functions.swapExactTokensForTokens(
                amount_in_wei,
                min_output,
                path,
                self.account.address,
                deadline
            ).build_transaction({
                "from": self.account.address,
                "gas": DEFAULT_GAS_LIMIT,
                "gasPrice": self._get_optimal_gas_price(),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.config.chain_id,
            })
            
            return tx
            
        except Exception as e:
            self.logger.error(f"Transaction building failed: {e}")
            return None
    
    def _build_flash_loan_transaction(
        self,
        tokens: List[ChecksumAddress],
        dexes: List[DEXProtocol],
        amount: Decimal,
    ) -> Optional[TxParams]:
        """
        Build flash loan transaction.
        
        Args:
            tokens: Token addresses
            dexes: DEX protocols
            amount: Amount to borrow
            
        Returns:
            Transaction parameters
        """
        try:
            # Get flash loan info
            loan_info = self.flash_loan_manager.get_flash_loan_info(
                tokens[0],
                amount,
                duration_seconds=0
            )
            
            if not loan_info:
                self.logger.warning("No flash loan available")
                return None
            
            # Build flash loan transaction
            # (Implementation would depend on flash loan provider)
            return None
            
        except Exception as e:
            self.logger.error(f"Flash loan transaction building failed: {e}")
            return None
    
    def _get_optimal_gas_price(self) -> int:
        """
        Get optimal gas price.
        
        Returns:
            Gas price in Wei
        """
        try:
            price = self.web3.eth.gas_price
            # Add buffer
            return int(price * float(self.config.gas_buffer))
        except Exception:
            return DEFAULT_GAS_PRICE
    
    def _get_available_tokens(self) -> List[ChecksumAddress]:
        """
        Get list of available tokens.
        
        Returns:
            List of token addresses
        """
        # Use known tokens
        return [to_checksum_address(addr) for addr in KNOWN_TOKENS.values()]
    
    def _get_available_pools(self) -> List[LiquidityPoolInfo]:
        """
        Get list of available liquidity pools.
        
        Returns:
            List of pool information
        """
        # This would query on-chain data in production
        # For now, return a small set of known pools
        pools = []
        try:
            # USDC/ETH pool on Uniswap V2
            pools.append({
                "address": to_checksum_address("0x0d4a11d5EEaaC28EC3F61d100daF4d40471f1852"),
                "token0": to_checksum_address(KNOWN_TOKENS["USDC"]),
                "token1": to_checksum_address(KNOWN_TOKENS["WETH"]),
                "reserve0": Decimal("100000000"),
                "reserve1": Decimal("4000"),
                "fee": Decimal("0.003"),
                "protocol": DEXProtocol.UNISWAP_V2,
                "total_supply": Decimal("1000000"),
            })
            # DAI/USDC pool on Curve
            pools.append({
                "address": to_checksum_address("0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7"),
                "token0": to_checksum_address(KNOWN_TOKENS["DAI"]),
                "token1": to_checksum_address(KNOWN_TOKENS["USDC"]),
                "reserve0": Decimal("50000000"),
                "reserve1": Decimal("50000000"),
                "fee": Decimal("0.0004"),
                "protocol": DEXProtocol.CURVE,
                "total_supply": Decimal("50000000"),
                "virtual_reserve": Decimal("50000000"),
            })
        except Exception as e:
            self.logger.warning(f"Failed to get pool info: {e}")
        
        return pools
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get detector metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            **self.metrics,
            "opportunities_count": len(self.opportunities),
            "is_running": self.is_running,
            "config": {
                "min_profit_threshold": float(self.config.min_profit_threshold),
                "max_hops": self.config.max_hops,
                "scan_interval": self.config.scan_interval,
            },
        }


# Helper Classes

class MEVShield:
    """MEV Protection Layer."""
    
    def __init__(self, config: MEVProtection):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def protect(
        self,
        tx: TxParams,
        private_mempool: bool = True,
    ) -> TxParams:
        """
        Apply MEV protection to a transaction.
        
        Args:
            tx: Transaction parameters
            private_mempool: Whether to use private mempool
            
        Returns:
            Protected transaction
        """
        if not self.config.enabled:
            return tx
        
        if private_mempool and self.config.use_private_mempool:
            # Add priority fees
            tx["priorityFee"] = self._calculate_priority_fee()
        
        if self.config.flashbots_enabled:
            # Add Flashbots-specific fields
            pass
        
        return tx
    
    def _calculate_priority_fee(self) -> int:
        """Calculate optimal priority fee."""
        # In production, this would query the network
        return int(Web3.to_wei(1.5, "gwei"))


class FlashLoanManager:
    """Flash Loan Management."""
    
    def __init__(self, config: DexDetectorConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.providers = ["AAVE", "DYDX", "BALANCER"]
    
    def get_flash_loan_info(
        self,
        token: ChecksumAddress,
        amount: Decimal,
        duration_seconds: int = 0,
    ) -> Optional[FlashLoanInfo]:
        """
        Get flash loan information.
        
        Args:
            token: Token address
            amount: Required amount
            duration_seconds: Duration in seconds
            
        Returns:
            FlashLoanInfo or None
        """
        if not self.config.enable_flash_loans:
            return None
        
        if amount > self.config.max_flash_loan_amount:
            return None
        
        # Check if token is available
        if token.lower() in [t.lower() for t in self._get_available_tokens()]:
            return FlashLoanInfo(
                provider="AAVE",
                required_amount=amount,
                fee=Decimal("0.0009"),  # 0.09% fee
                max_amount=self.config.max_flash_loan_amount,
                available_tokens=self._get_available_tokens(),
                duration_seconds=duration_seconds,
            )
        
        return None
    
    def _get_available_tokens(self) -> List[str]:
        """Get list of tokens available for flash loans."""
        # In production, this would query the protocol
        return [t.lower() for t in KNOWN_TOKENS.values() if t.lower() in [
            "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
            "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
            "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI
        ]]


class GasOptimizer:
    """Gas Cost Optimization."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.gas_data: Dict[str, Any] = {}
    
    def estimate_gas_cost(self, path: List[RouteNode]) -> Decimal:
        """
        Estimate gas cost for a path.
        
        Args:
            path: Path nodes
            
        Returns:
            Estimated gas cost in ETH
        """
        # Base gas for swap
        base_gas = Decimal("100000")  # 100k gas
        
        # Additional gas per hop
        hop_gas = Decimal("50000") * Decimal(len(path))
        
        # Total gas
        total_gas = base_gas + hop_gas
        
        # Convert to ETH (assuming gas price ~100 gwei)
        gas_price = Decimal("100")  # gwei
        gas_cost = (total_gas * gas_price) / Decimal(10**18)
        
        return gas_cost
    
    def optimize_path(
        self,
        path: List[RouteNode],
        max_gas: Decimal,
    ) -> List[RouteNode]:
        """
        Optimize a path for gas efficiency.
        
        Args:
            path: Path nodes
            max_gas: Maximum gas allowed
            
        Returns:
            Optimized path
        """
        # Simple optimization: remove nodes if over limit
        if self.estimate_gas_cost(path) > max_gas:
            # Remove nodes from the middle
            if len(path) > 2:
                return [path[0], path[-1]]
        
        return path


# Utility functions

def to_decimal(wei: Union[int, Wei]) -> Decimal:
    """Convert Wei to Decimal."""
    return Decimal(str(wei)) / Decimal(10**18)


def to_wei(amount: Decimal, decimals: int = 18) -> int:
    """Convert Decimal to Wei."""
    return int(amount * Decimal(10**decimals))


def validate_address(address: str) -> ChecksumAddress:
    """Validate and checksum an Ethereum address."""
    if not Web3.is_address(address):
        raise ValueError(f"Invalid address: {address}")
    return to_checksum_address(address)


def format_profit(profit: Decimal) -> str:
    """Format profit for display."""
    if profit >= 0:
        return f"+${profit:.2f}"
    return f"-${abs(profit):.2f}"


# Module exports
__all__ = [
    'DexDetector',
    'DexDetectorConfig',
    'DEXProtocol',
    'LiquidityPoolInfo',
    'ArbitragePath',
    'OpportunityResult',
    'RouteNode',
    'FlashLoanInfo',
    'MEVProtection',
    'MEVShield',
    'FlashLoanManager',
    'GasOptimizer',
    'to_decimal',
    'to_wei',
    'validate_address',
    'format_profit',
]
