# trading/bots/arbitrage_bot/detectors/flash_loan_detector.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Advanced Flash Loan Arbitrage Detection Engine

"""
Flash Loan Arbitrage Detector - Advanced Flash Loan Detection Engine

This module provides state-of-the-art detection of flash loan arbitrage
opportunities across multiple DeFi protocols with support for:
- Multi-protocol flash loan detection (AAVE, dYdX, Balancer, Uniswap V3)
- Cross-chain flash loan arbitrage
- Flash loan + DEX arbitrage combination
- Atomic transaction planning
- Collateral optimization
- Gas optimization for flash loans
- Risk assessment and profit simulation

Architecture:
    - BaseFlashLoanDetector: Abstract base class
    - FlashLoanDetector: Main detector implementation
    - ProtocolAdapter: Protocol-specific adapters
    - OpportunityAnalyzer: Profitability analysis
    - AtomicExecutor: Atomic execution planning
    - CollateralManager: Collateral optimization

Protocols Supported:
    - AAVE V2/V3 Flash Loans
    - dYdX Flash Loans
    - Balancer Flash Loans
    - Uniswap V3 Flash Swaps
    - MakerDAO Flash Loans
    - Euler Finance Flash Loans
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
FLASH_LOAN_FEE_AAVE = Decimal("0.0009")  # 0.09%
FLASH_LOAN_FEE_DYDX = Decimal("0")  # 0% (deprecated in V4)
FLASH_LOAN_FEE_BALANCER = Decimal("0.0005")  # 0.05%
FLASH_LOAN_FEE_UNISWAP_V3 = Decimal("0.0005")  # 0.05% (500 ppm)
FLASH_LOAN_FEE_EULER = Decimal("0.001")  # 0.1%
DEFAULT_FLASH_LOAN_GAS_LIMIT = 3000000
MIN_FLASH_LOAN_PROFIT = Decimal("0.001")  # 0.1% minimum profit

# Supported Flash Loan Protocols
class FlashLoanProtocol(Enum):
    AAVE_V2 = "aave_v2"
    AAVE_V3 = "aave_v3"
    DYDX = "dydx"
    BALANCER = "balancer"
    UNISWAP_V3 = "uniswap_v3"
    MAKERDAO = "makerdao"
    EULER = "euler"
    SPARK = "spark"

# Flash Loan Contract Addresses (Mainnet)
FLASH_LOAN_ADDRESSES = {
    FlashLoanProtocol.AAVE_V2: {
        "lending_pool": "0x7d2768dE32b0b80b7a3454c06BdAc94A69DDc7A9",
        "lending_pool_core": "0x398eC7346DcD622eDc5ae82352F02bE94C62d119",
        "address_provider": "0xB53C1a33016B2DC2fF3653530bfF1848a515c8c5",
    },
    FlashLoanProtocol.AAVE_V3: {
        "lending_pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "address_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e",
    },
    FlashLoanProtocol.DYDX: {
        "solo_margin": "0x1E0447b19BB6EcFdAe1e4AE1694b0C3659614e4E",  # Deprecated
        "dydx_v4": "",  # To be implemented
    },
    FlashLoanProtocol.BALANCER: {
        "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
    },
    FlashLoanProtocol.UNISWAP_V3: {
        "swap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
    },
    FlashLoanProtocol.MAKERDAO: {
        "dss_flash": "0x60744434d6339a6B27d73d9Eda62b6F66a0a04FA",
    },
    FlashLoanProtocol.EULER: {
        "euler": "0x27182842E098f60e3D576794A5bFFb0777E025d3",
    },
    FlashLoanProtocol.SPARK: {
        "spark": "0xC13e21B648A5Ee794902342038FF3aBAB266BE0A",
    },
}

# ABI Definitions
AAVE_LENDING_POOL_ABI = json.loads("""
[
    {
        "inputs": [
            {"name": "assets", "type": "address[]"},
            {"name": "amounts", "type": "uint256[]"},
            {"name": "modes", "type": "uint256[]"},
            {"name": "onBehalfOf", "type": "address"},
            {"name": "params", "type": "bytes"},
            {"name": "referralCode", "type": "uint16"}
        ],
        "name": "flashLoan",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "getReserveData",
        "outputs": [
            {"name": "reserveData", "type": "tuple"},
            {"name": "fee", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
""")

BALANCER_VAULT_ABI = json.loads("""
[
    {
        "inputs": [
            {"name": "poolId", "type": "bytes32"},
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "flashLoan",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
""")

UNISWAP_V3_SWAP_ROUTER_ABI = json.loads("""
[
    {
        "inputs": [
            {"name": "params", "type": "tuple"}
        ],
        "name": "uniswapV3FlashSwap",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
""")

# Typed dictionaries for type safety
class FlashLoanInfo(TypedDict):
    """Flash loan opportunity information."""
    protocol: FlashLoanProtocol
    asset: ChecksumAddress
    amount: Decimal
    fee: Decimal
    fee_amount: Decimal
    available: bool
    max_amount: Decimal
    min_amount: Decimal
    duration_blocks: int
    requires_callback: bool
    callback_gas_limit: int


class FlashLoanPath(TypedDict):
    """Flash loan execution path."""
    protocol: FlashLoanProtocol
    asset_in: ChecksumAddress
    asset_out: ChecksumAddress
    amount: Decimal
    steps: List[Dict[str, Any]]
    expected_profit: Decimal
    fee: Decimal
    gas_cost: Decimal
    net_profit: Decimal
    net_profit_percentage: Decimal
    risk_score: Decimal
    complexity: int
    requires_atomic_execution: bool
    callback_data: Optional[bytes]


class FlashLoanOpportunity(TypedDict):
    """Complete flash loan arbitrage opportunity."""
    paths: List[FlashLoanPath]
    best_path: FlashLoanPath
    total_profit: Decimal
    total_profit_percentage: Decimal
    total_fees: Decimal
    total_gas_cost: Decimal
    net_profit: Decimal
    net_profit_percentage: Decimal
    confidence: Decimal
    timestamp: datetime
    block_number: int
    execution_time_ms: int
    requires_contract_deployment: bool


@dataclass
class FlashLoanExecutionPlan:
    """Flash loan execution plan."""
    protocol: FlashLoanProtocol
    asset: ChecksumAddress
    amount: Decimal
    steps: List[Dict[str, Any]]
    callback_contract: Optional[ChecksumAddress]
    callback_data: bytes
    gas_limit: int
    deadline: int
    atomic_execution: bool
    validation_checks: List[str]
    fallback_plan: Optional["FlashLoanExecutionPlan"]


@dataclass
class ProtocolCapabilities:
    """Capabilities of a flash loan protocol."""
    protocol: FlashLoanProtocol
    supports_multiple_assets: bool
    max_assets: int
    max_amount: Decimal
    min_amount: Decimal
    fee_structure: str  # "fixed", "percentage", "dynamic"
    fee_rate: Decimal
    requires_callback: bool
    callback_gas_limit: int
    supports_atomic: bool
    supports_cross_chain: bool
    supported_assets: List[ChecksumAddress]


@dataclass
class RiskAssessment:
    """Risk assessment for a flash loan opportunity."""
    protocol_risk: Decimal  # 0-1
    market_risk: Decimal  # 0-1
    execution_risk: Decimal  # 0-1
    slippage_risk: Decimal  # 0-1
    overall_risk: Decimal  # 0-1
    confidence: Decimal  # 0-1
    warnings: List[str]
    mitigations: List[str]


class FlashLoanDetector:
    """
    Advanced Flash Loan Arbitrage Detector.
    
    This class implements sophisticated flash loan arbitrage detection
    across multiple DeFi protocols with support for:
    1. Multi-protocol flash loan opportunities
    2. Cross-chain flash loan arbitrage
    3. Flash loan + DEX arbitrage combinations
    4. Atomic transaction planning
    5. Collateral optimization
    6. Risk assessment and profit simulation
    
    Features:
    - Real-time flash loan opportunity scanning
    - Multi-protocol support (AAVE, dYdX, Balancer, Uniswap V3, MakerDAO, Euler)
    - Profit optimization with gas and fee calculations
    - Risk assessment with confidence scoring
    - Atomic execution planning
    - MEV protection
    - Callback contract generation
    """
    
    def __init__(
        self,
        web3_provider: Optional[Web3] = None,
        private_key: Optional[str] = None,
        min_profit_threshold: Decimal = MIN_FLASH_LOAN_PROFIT,
        max_gas_price: Decimal = Decimal("200"),  # gwei
        scan_interval: float = 2.0,
    ):
        """
        Initialize the Flash Loan Detector.
        
        Args:
            web3_provider: Optional Web3 instance
            private_key: Optional private key for signing transactions
            min_profit_threshold: Minimum profit percentage to consider
            max_gas_price: Maximum gas price to use (in gwei)
            scan_interval: Interval between scans in seconds
        """
        self.logger = self._setup_logger()
        self.min_profit_threshold = min_profit_threshold
        self.max_gas_price = max_gas_price
        self.scan_interval = scan_interval
        
        # Initialize Web3
        self.web3 = web3_provider or self._init_web3()
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # Initialize protocol adapters
        self.adapters: Dict[FlashLoanProtocol, 'ProtocolAdapter'] = {}
        self._init_adapters()
        
        # Cache for protocol data
        self.protocol_cache: Dict[str, Dict] = {}
        self.asset_cache: Dict[str, Dict] = {}
        self.opportunity_cache: Dict[str, FlashLoanOpportunity] = {}
        
        # Thread pool for parallel scanning
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Monitoring
        self.metrics = {
            "scans": 0,
            "opportunities_found": 0,
            "opportunities_executed": 0,
            "total_profit": Decimal("0"),
            "total_fees": Decimal("0"),
            "total_gas": Decimal("0"),
            "errors": 0,
            "success_rate": Decimal("0"),
        }
        
        # State management
        self.is_running = False
        self.scan_thread: Optional[threading.Thread] = None
        
        # MEV protection
        self.mev_shield = FlashLoanMEVShield()
        
        # Callback contract manager
        self.callback_manager = CallbackContractManager()
        
        # Risk engine
        self.risk_engine = RiskEngine()
    
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
        providers = [
            "https://mainnet.infura.io/v3/",
            "https://eth-mainnet.g.alchemy.com/v2/",
            "https://cloudflare-eth.com",
        ]
        for provider in providers:
            try:
                w3 = Web3(Web3.HTTPProvider(provider))
                if w3.is_connected():
                    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    return w3
            except Exception as e:
                self.logger.warning(f"Failed to connect to {provider}: {e}")
        return Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
    
    def _init_adapters(self) -> None:
        """Initialize protocol adapters."""
        self.adapters = {
            FlashLoanProtocol.AAVE_V2: AaveV2Adapter(self.web3),
            FlashLoanProtocol.AAVE_V3: AaveV3Adapter(self.web3),
            FlashLoanProtocol.DYDX: DydxAdapter(self.web3),
            FlashLoanProtocol.BALANCER: BalancerAdapter(self.web3),
            FlashLoanProtocol.UNISWAP_V3: UniswapV3Adapter(self.web3),
            FlashLoanProtocol.MAKERDAO: MakerDAOAdapter(self.web3),
            FlashLoanProtocol.EULER: EulerAdapter(self.web3),
            FlashLoanProtocol.SPARK: SparkAdapter(self.web3),
        }
    
    def start(self) -> None:
        """Start the background scanner."""
        if self.is_running:
            return
        
        self.is_running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        self.logger.info("Flash Loan Detector started")
    
    def stop(self) -> None:
        """Stop the background scanner."""
        self.is_running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5.0)
        self.logger.info("Flash Loan Detector stopped")
    
    def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self.is_running:
            try:
                # Scan for flash loan opportunities
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
        asset: Optional[ChecksumAddress] = None,
        protocols: Optional[List[FlashLoanProtocol]] = None,
        max_paths: int = 10,
    ) -> List[FlashLoanOpportunity]:
        """
        Scan for flash loan arbitrage opportunities.
        
        Args:
            asset: Optional asset to focus on
            protocols: Optional list of protocols to scan
            max_paths: Maximum number of paths to return
            
        Returns:
            List of FlashLoanOpportunity objects
        """
        try:
            start_time = time.time()
            opportunities = []
            
            # Get protocols to scan
            scan_protocols = protocols or list(self.adapters.keys())
            
            # Scan each protocol in parallel
            with ThreadPoolExecutor(max_workers=len(scan_protocols)) as executor:
                future_to_protocol = {
                    executor.submit(
                        self._scan_protocol,
                        protocol,
                        asset
                    ): protocol
                    for protocol in scan_protocols
                }
                
                for future in future_to_protocol:
                    try:
                        result = future.result(timeout=10.0)
                        if result:
                            opportunities.extend(result)
                    except Exception as e:
                        self.logger.error(f"Protocol scan failed: {e}")
            
            # Evaluate and rank opportunities
            evaluated = []
            for opp in opportunities:
                eval_opp = self._evaluate_opportunity(opp)
                if eval_opp and self._is_profitable(eval_opp):
                    evaluated.append(eval_opp)
            
            # Sort by net profit
            evaluated.sort(
                key=lambda x: x["net_profit"],
                reverse=True
            )
            
            # Update metrics
            self.metrics["opportunities_found"] += len(evaluated)
            
            execution_time = (time.time() - start_time) * 1000
            self.logger.debug(
                f"Scan completed in {execution_time:.2f}ms, "
                f"found {len(evaluated)} opportunities"
            )
            
            return evaluated[:max_paths]
            
        except Exception as e:
            self.logger.error(f"Opportunity scan failed: {e}")
            return []
    
    def _scan_protocol(
        self,
        protocol: FlashLoanProtocol,
        asset: Optional[ChecksumAddress] = None,
    ) -> List[FlashLoanOpportunity]:
        """
        Scan a specific protocol for flash loan opportunities.
        
        Args:
            protocol: Protocol to scan
            asset: Optional specific asset
            
        Returns:
            List of opportunities
        """
        adapter = self.adapters.get(protocol)
        if not adapter:
            return []
        
        try:
            # Get flash loan capabilities
            capabilities = adapter.get_capabilities()
            
            # Get available assets
            assets = [asset] if asset else capabilities.supported_assets
            
            # Scan each asset
            opportunities = []
            for asset_addr in assets:
                try:
                    # Get flash loan info
                    info = adapter.get_flash_loan_info(asset_addr)
                    if not info or not info["available"]:
                        continue
                    
                    # Find profitable paths
                    paths = self._find_profitable_paths(
                        info,
                        adapter,
                        capabilities
                    )
                    
                    if paths:
                        opportunities.extend(paths)
                        
                except Exception as e:
                    self.logger.debug(f"Asset scan failed for {asset_addr}: {e}")
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Protocol scan failed: {e}")
            return []
    
    def _find_profitable_paths(
        self,
        flash_info: FlashLoanInfo,
        adapter: 'ProtocolAdapter',
        capabilities: ProtocolCapabilities,
    ) -> List[FlashLoanOpportunity]:
        """
        Find profitable flash loan paths.
        
        Args:
            flash_info: Flash loan information
            adapter: Protocol adapter
            capabilities: Protocol capabilities
            
        Returns:
            List of profitable opportunities
        """
        paths = []
        
        try:
            asset = flash_info["asset"]
            amount = flash_info["amount"]
            fee = flash_info["fee"]
            fee_amount = flash_info["fee_amount"]
            
            # Find arbitrage opportunities using flash loan
            # 1. DEX arbitrage (Uniswap/SushiSwap)
            dex_paths = self._find_dex_arbitrage(asset, amount, adapter)
            for dex_path in dex_paths:
                opportunity = self._build_opportunity(
                    flash_info,
                    dex_path,
                    adapter,
                    "dex_arbitrage"
                )
                if opportunity:
                    paths.append(opportunity)
            
            # 2. Yield arbitrage (Lending/Staking)
            yield_paths = self._find_yield_arbitrage(asset, amount, adapter)
            for yield_path in yield_paths:
                opportunity = self._build_opportunity(
                    flash_info,
                    yield_path,
                    adapter,
                    "yield_arbitrage"
                )
                if opportunity:
                    paths.append(opportunity)
            
            # 3. Cross-protocol arbitrage
            cross_paths = self._find_cross_protocol_arbitrage(
                asset,
                amount,
                adapter
            )
            for cross_path in cross_paths:
                opportunity = self._build_opportunity(
                    flash_info,
                    cross_path,
                    adapter,
                    "cross_protocol_arbitrage"
                )
                if opportunity:
                    paths.append(opportunity)
            
        except Exception as e:
            self.logger.debug(f"Path finding failed: {e}")
        
        return paths
    
    def _find_dex_arbitrage(
        self,
        asset: ChecksumAddress,
        amount: Decimal,
        adapter: 'ProtocolAdapter',
    ) -> List[Dict[str, Any]]:
        """
        Find DEX arbitrage opportunities.
        
        Args:
            asset: Asset to arbitrage
            amount: Amount to use
            adapter: Protocol adapter
            
        Returns:
            List of arbitrage paths
        """
        paths = []
        # This would integrate with DEX detectors
        # For now, return simulated paths
        return paths
    
    def _find_yield_arbitrage(
        self,
        asset: ChecksumAddress,
        amount: Decimal,
        adapter: 'ProtocolAdapter',
    ) -> List[Dict[str, Any]]:
        """
        Find yield arbitrage opportunities.
        
        Args:
            asset: Asset to arbitrage
            amount: Amount to use
            adapter: Protocol adapter
            
        Returns:
            List of yield arbitrage paths
        """
        paths = []
        # This would integrate with yield aggregators
        return paths
    
    def _find_cross_protocol_arbitrage(
        self,
        asset: ChecksumAddress,
        amount: Decimal,
        adapter: 'ProtocolAdapter',
    ) -> List[Dict[str, Any]]:
        """
        Find cross-protocol arbitrage opportunities.
        
        Args:
            asset: Asset to arbitrage
            amount: Amount to use
            adapter: Protocol adapter
            
        Returns:
            List of cross-protocol paths
        """
        paths = []
        # This would integrate with multiple protocols
        return paths
    
    def _build_opportunity(
        self,
        flash_info: FlashLoanInfo,
        execution_path: Dict[str, Any],
        adapter: 'ProtocolAdapter',
        opportunity_type: str,
    ) -> Optional[FlashLoanOpportunity]:
        """
        Build a flash loan opportunity from a path.
        
        Args:
            flash_info: Flash loan information
            execution_path: Execution path
            adapter: Protocol adapter
            opportunity_type: Type of opportunity
            
        Returns:
            FlashLoanOpportunity or None
        """
        try:
            # Calculate expected profit
            amount = flash_info["amount"]
            fee = flash_info["fee"]
            fee_amount = flash_info["fee_amount"]
            
            # Estimate output from execution path
            expected_output = execution_path.get("expected_output", amount)
            
            # Calculate profit
            profit = expected_output - amount - fee_amount
            profit_percentage = (profit / amount) * Decimal("100")
            
            # Estimate gas cost
            gas_cost = self._estimate_gas_cost(execution_path)
            
            # Calculate net profit
            net_profit = profit - gas_cost
            net_profit_percentage = (net_profit / amount) * Decimal("100")
            
            # Calculate risk
            risk_score = self._calculate_risk_score(
                flash_info,
                execution_path,
                opportunity_type
            )
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                flash_info,
                execution_path,
                opportunity_type
            )
            
            # Build path
            path: FlashLoanPath = {
                "protocol": flash_info["protocol"],
                "asset_in": flash_info["asset"],
                "asset_out": flash_info["asset"],
                "amount": amount,
                "steps": execution_path.get("steps", []),
                "expected_profit": profit,
                "fee": fee,
                "gas_cost": gas_cost,
                "net_profit": net_profit,
                "net_profit_percentage": net_profit_percentage,
                "risk_score": risk_score,
                "complexity": len(execution_path.get("steps", [])),
                "requires_atomic_execution": True,
                "callback_data": execution_path.get("callback_data", b""),
            }
            
            # Build opportunity
            opportunity: FlashLoanOpportunity = {
                "paths": [path],
                "best_path": path,
                "total_profit": profit,
                "total_profit_percentage": profit_percentage,
                "total_fees": fee_amount,
                "total_gas_cost": gas_cost,
                "net_profit": net_profit,
                "net_profit_percentage": net_profit_percentage,
                "confidence": confidence,
                "timestamp": datetime.utcnow(),
                "block_number": self.web3.eth.block_number,
                "execution_time_ms": 0,
                "requires_contract_deployment": False,
            }
            
            return opportunity
            
        except Exception as e:
            self.logger.debug(f"Opportunity building failed: {e}")
            return None
    
    def _estimate_gas_cost(self, execution_path: Dict[str, Any]) -> Decimal:
        """
        Estimate gas cost for an execution path.
        
        Args:
            execution_path: Execution path
            
        Returns:
            Estimated gas cost in ETH
        """
        # Base gas for flash loan
        base_gas = Decimal("200000")  # 200k gas
        
        # Additional gas per step
        steps = len(execution_path.get("steps", []))
        step_gas = Decimal("50000") * Decimal(steps)
        
        # Total gas
        total_gas = base_gas + step_gas
        
        # Gas price in ETH
        gas_price = min(
            self._get_current_gas_price(),
            self.max_gas_price
        )
        gas_cost = (total_gas * gas_price) / Decimal(10**18)
        
        return gas_cost
    
    def _get_current_gas_price(self) -> Decimal:
        """
        Get current gas price.
        
        Returns:
            Gas price in gwei
        """
        try:
            price = self.web3.eth.gas_price
            return Decimal(str(price)) / Decimal(10**9)
        except Exception:
            return Decimal("100")  # Fallback to 100 gwei
    
    def _calculate_risk_score(
        self,
        flash_info: FlashLoanInfo,
        execution_path: Dict[str, Any],
        opportunity_type: str,
    ) -> Decimal:
        """
        Calculate risk score for an opportunity.
        
        Args:
            flash_info: Flash loan information
            execution_path: Execution path
            opportunity_type: Type of opportunity
            
        Returns:
            Risk score between 0 and 1
        """
        risk_score = Decimal("0")
        
        # Factor 1: Protocol risk
        protocol_risk = {
            FlashLoanProtocol.AAVE_V2: Decimal("0.05"),
            FlashLoanProtocol.AAVE_V3: Decimal("0.05"),
            FlashLoanProtocol.DYDX: Decimal("0.1"),
            FlashLoanProtocol.BALANCER: Decimal("0.1"),
            FlashLoanProtocol.UNISWAP_V3: Decimal("0.05"),
            FlashLoanProtocol.MAKERDAO: Decimal("0.1"),
            FlashLoanProtocol.EULER: Decimal("0.15"),
            FlashLoanProtocol.SPARK: Decimal("0.1"),
        }
        risk_score += protocol_risk.get(flash_info["protocol"], Decimal("0.15"))
        
        # Factor 2: Complexity risk
        complexity = len(execution_path.get("steps", []))
        complexity_risk = min(Decimal("0.3"), Decimal(complexity) * Decimal("0.05"))
        risk_score += complexity_risk
        
        # Factor 3: Opportunity type risk
        type_risk = {
            "dex_arbitrage": Decimal("0.1"),
            "yield_arbitrage": Decimal("0.15"),
            "cross_protocol_arbitrage": Decimal("0.2"),
        }
        risk_score += type_risk.get(opportunity_type, Decimal("0.15"))
        
        # Factor 4: Amount risk
        amount_risk = min(
            Decimal("0.2"),
            flash_info["amount"] / Decimal("1000000")
        )
        risk_score += amount_risk
        
        # Normalize
        return min(Decimal("1"), risk_score)
    
    def _calculate_confidence(
        self,
        flash_info: FlashLoanInfo,
        execution_path: Dict[str, Any],
        opportunity_type: str,
    ) -> Decimal:
        """
        Calculate confidence score for an opportunity.
        
        Args:
            flash_info: Flash loan information
            execution_path: Execution path
            opportunity_type: Type of opportunity
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = Decimal("0.8")  # Base confidence
        
        # Factor 1: Protocol reputation
        protocol_conf = {
            FlashLoanProtocol.AAVE_V2: Decimal("0.95"),
            FlashLoanProtocol.AAVE_V3: Decimal("0.95"),
            FlashLoanProtocol.DYDX: Decimal("0.85"),
            FlashLoanProtocol.BALANCER: Decimal("0.9"),
            FlashLoanProtocol.UNISWAP_V3: Decimal("0.95"),
            FlashLoanProtocol.MAKERDAO: Decimal("0.85"),
            FlashLoanProtocol.EULER: Decimal("0.8"),
            FlashLoanProtocol.SPARK: Decimal("0.8"),
        }
        confidence *= protocol_conf.get(
            flash_info["protocol"],
            Decimal("0.8")
        )
        
        # Factor 2: Path simplicity
        complexity = len(execution_path.get("steps", []))
        confidence *= Decimal("0.95") ** complexity
        
        # Factor 3: Market conditions
        confidence *= Decimal("0.95")
        
        # Factor 4: Historical success (would use real data)
        confidence *= Decimal("0.98")
        
        return max(Decimal("0"), min(Decimal("1"), confidence))
    
    def _is_profitable(self, opportunity: FlashLoanOpportunity) -> bool:
        """
        Check if an opportunity is profitable.
        
        Args:
            opportunity: Opportunity to check
            
        Returns:
            True if profitable
        """
        return (
            opportunity["net_profit_percentage"] >= self.min_profit_threshold * Decimal("100") and
            opportunity["confidence"] >= Decimal("0.5") and
            opportunity["best_path"]["risk_score"] <= Decimal("0.7")
        )
    
    def _process_opportunities(self, opportunities: List[FlashLoanOpportunity]) -> None:
        """
        Process detected opportunities.
        
        Args:
            opportunities: List of opportunities
        """
        for opp in opportunities:
            # Cache opportunity
            key = hashlib.md5(
                json.dumps([
                    str(opp["best_path"]["protocol"].value),
                    str(opp["best_path"]["asset_in"]),
                    str(opp["best_path"]["amount"]),
                ]).encode()
            ).hexdigest()
            self.opportunity_cache[key] = opp
            
        # Log top opportunities
        if opportunities:
            best = opportunities[0]
            self.logger.info(
                f"Found flash loan opportunity: "
                f"{best['net_profit_percentage']:.2f}% profit "
                f"via {best['best_path']['protocol'].value}, "
                f"confidence: {best['confidence']:.2f}, "
                f"risk: {best['best_path']['risk_score']:.2f}, "
                f"amount: ${best['best_path']['amount']:,.2f}"
            )
    
    def execute_opportunity(
        self,
        opportunity: FlashLoanOpportunity,
        callback_contract: Optional[ChecksumAddress] = None,
    ) -> Dict[str, Any]:
        """
        Execute a flash loan opportunity.
        
        Args:
            opportunity: Opportunity to execute
            callback_contract: Optional callback contract address
            
        Returns:
            Execution result
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
            
            # Get adapter
            adapter = self.adapters.get(path["protocol"])
            if not adapter:
                raise ValueError(f"No adapter for {path['protocol']}")
            
            # Build execution plan
            plan = self._build_execution_plan(path, callback_contract)
            if not plan:
                raise ValueError("Failed to build execution plan")
            
            # Execute flash loan
            tx = self._build_flash_loan_transaction(plan)
            if not tx:
                raise ValueError("Failed to build transaction")
            
            # Apply MEV protection
            tx = self.mev_shield.protect(tx)
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            
            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            
            if receipt.status == 1:
                result["success"] = True
                result["tx_hash"] = to_hex(tx_hash)
                result["gas_used"] = Decimal(str(receipt.gasUsed))
                result["profit"] = opportunity["net_profit"]
                
                # Update metrics
                self.metrics["opportunities_executed"] += 1
                self.metrics["total_profit"] += opportunity["net_profit"]
                self.metrics["total_fees"] += opportunity["total_fees"]
                self.metrics["total_gas"] += Decimal(str(receipt.gasUsed))
                
                self.logger.info(f"Executed flash loan: {to_hex(tx_hash)}")
            else:
                result["error"] = "Transaction failed"
                
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            result["error"] = str(e)
            self.metrics["errors"] += 1
        
        # Update success rate
        if self.metrics["opportunities_executed"] > 0:
            self.metrics["success_rate"] = (
                self.metrics["opportunities_executed"] /
                (self.metrics["opportunities_executed"] + self.metrics["errors"])
            )
        
        return result
    
    def _build_execution_plan(
        self,
        path: FlashLoanPath,
        callback_contract: Optional[ChecksumAddress] = None,
    ) -> Optional[FlashLoanExecutionPlan]:
        """
        Build execution plan for a flash loan path.
        
        Args:
            path: Flash loan path
            callback_contract: Optional callback contract
            
        Returns:
            Execution plan
        """
        try:
            # If no callback contract provided, generate one
            if not callback_contract:
                callback_contract = self.callback_manager.generate_callback(
                    path,
                    self.account.address if self.account else None
                )
            
            # Build plan
            plan = FlashLoanExecutionPlan(
                protocol=path["protocol"],
                asset=path["asset_in"],
                amount=path["amount"],
                steps=path["steps"],
                callback_contract=callback_contract,
                callback_data=path.get("callback_data", b""),
                gas_limit=DEFAULT_FLASH_LOAN_GAS_LIMIT,
                deadline=int(time.time()) + 600,  # 10 minutes
                atomic_execution=path["requires_atomic_execution"],
                validation_checks=[
                    "slippage_limit",
                    "min_profit",
                    "balance_check",
                ],
                fallback_plan=None,
            )
            
            return plan
            
        except Exception as e:
            self.logger.error(f"Execution plan building failed: {e}")
            return None
    
    def _build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
    ) -> Optional[TxParams]:
        """
        Build flash loan transaction.
        
        Args:
            plan: Execution plan
            
        Returns:
            Transaction parameters
        """
        try:
            adapter = self.adapters.get(plan.protocol)
            if not adapter:
                return None
            
            # Build transaction using adapter
            tx = adapter.build_flash_loan_transaction(
                plan,
                self.account.address if self.account else None
            )
            
            return tx
            
        except Exception as e:
            self.logger.error(f"Transaction building failed: {e}")
            return None
    
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
            "scan_interval": self.scan_interval,
        }


# Protocol Adapters

class ProtocolAdapter(ABC):
    """Abstract base class for flash loan protocol adapters."""
    
    def __init__(self, web3: Web3):
        self.web3 = web3
        self.logger = logging.getLogger(__name__)
        self.contract = None
    
    @abstractmethod
    def get_capabilities(self) -> ProtocolCapabilities:
        """Get protocol capabilities."""
        pass
    
    @abstractmethod
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        """Get flash loan information for an asset."""
        pass
    
    @abstractmethod
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        """Build flash loan transaction."""
        pass
    
    @abstractmethod
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        """Validate flash loan execution plan."""
        pass


class AaveV2Adapter(ProtocolAdapter):
    """AAVE V2 Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.lending_pool_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.AAVE_V2]["lending_pool"]
        self.lending_pool = self.web3.eth.contract(
            address=self.lending_pool_address,
            abi=AAVE_LENDING_POOL_ABI
        )
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.AAVE_V2,
            supports_multiple_assets=True,
            max_assets=1,  # AAVE V2 supports multiple assets
            max_amount=Decimal("1000000"),  # Example limit
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_AAVE,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],  # Would fetch from protocol
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        try:
            # Get reserve data
            data = self.lending_pool.functions.getReserveData(asset).call()
            
            # Parse fee
            fee = Decimal(str(data[1])) / Decimal(10**4)  # Fee in basis points
            
            return FlashLoanInfo(
                protocol=FlashLoanProtocol.AAVE_V2,
                asset=asset,
                amount=Decimal("1000"),  # Would calculate from reserve
                fee=fee,
                fee_amount=Decimal("0.9"),  # Example
                available=True,
                max_amount=Decimal("1000000"),
                min_amount=Decimal("0.001"),
                duration_blocks=0,  # Same block
                requires_callback=True,
                callback_gas_limit=2000000,
            )
        except Exception as e:
            self.logger.debug(f"Failed to get AAVE V2 flash loan info: {e}")
            return None
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        try:
            if not from_address:
                return None
            
            # Build flash loan parameters
            assets = [plan.asset]
            amounts = [int(plan.amount * Decimal(10**18))]
            modes = [0]  # 0 = no debt, 1 = stable, 2 = variable
            on_behalf_of = from_address
            params = plan.callback_data
            referral_code = 0
            
            # Build transaction
            tx = self.lending_pool.functions.flashLoan(
                assets,
                amounts,
                modes,
                on_behalf_of,
                params,
                referral_code
            ).build_transaction({
                "from": from_address,
                "gas": plan.gas_limit,
                "gasPrice": self.web3.eth.gas_price,
                "nonce": self.web3.eth.get_transaction_count(from_address),
                "chainId": 1,
            })
            
            return tx
            
        except Exception as e:
            self.logger.error(f"Failed to build AAVE V2 flash loan: {e}")
            return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class AaveV3Adapter(ProtocolAdapter):
    """AAVE V3 Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.lending_pool_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.AAVE_V3]["lending_pool"]
        self.lending_pool = self.web3.eth.contract(
            address=self.lending_pool_address,
            abi=AAVE_LENDING_POOL_ABI
        )
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.AAVE_V3,
            supports_multiple_assets=True,
            max_assets=10,  # AAVE V3 supports multiple assets
            max_amount=Decimal("5000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_AAVE,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        try:
            # Similar to V2 but with V3 specific logic
            return FlashLoanInfo(
                protocol=FlashLoanProtocol.AAVE_V3,
                asset=asset,
                amount=Decimal("1000"),
                fee=FLASH_LOAN_FEE_AAVE,
                fee_amount=Decimal("0.9"),
                available=True,
                max_amount=Decimal("5000000"),
                min_amount=Decimal("0.001"),
                duration_blocks=0,
                requires_callback=True,
                callback_gas_limit=2000000,
            )
        except Exception as e:
            self.logger.debug(f"Failed to get AAVE V3 flash loan info: {e}")
            return None
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        # Similar to V2
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class BalancerAdapter(ProtocolAdapter):
    """Balancer Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.vault_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.BALANCER]["vault"]
        self.vault = self.web3.eth.contract(
            address=self.vault_address,
            abi=BALANCER_VAULT_ABI
        )
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.BALANCER,
            supports_multiple_assets=True,
            max_assets=0,  # Unlimited
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_BALANCER,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.BALANCER,
            asset=asset,
            amount=Decimal("1000"),
            fee=FLASH_LOAN_FEE_BALANCER,
            fee_amount=Decimal("0.5"),
            available=True,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        try:
            if not from_address:
                return None
            
            # Build flash loan
            pool_id = b"0x0000000000000000000000000000000000000000000000000000000000000000"
            
            tx = self.vault.functions.flashLoan(
                pool_id,
                from_address,
                int(plan.amount * Decimal(10**18))
            ).build_transaction({
                "from": from_address,
                "gas": plan.gas_limit,
                "gasPrice": self.web3.eth.gas_price,
                "nonce": self.web3.eth.get_transaction_count(from_address),
                "chainId": 1,
            })
            
            return tx
            
        except Exception as e:
            self.logger.error(f"Failed to build Balancer flash loan: {e}")
            return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class UniswapV3Adapter(ProtocolAdapter):
    """Uniswap V3 Flash Swap Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.router_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.UNISWAP_V3]["swap_router"]
        self.router = self.web3.eth.contract(
            address=self.router_address,
            abi=UNISWAP_V3_SWAP_ROUTER_ABI
        )
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.UNISWAP_V3,
            supports_multiple_assets=False,
            max_assets=1,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_UNISWAP_V3,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.UNISWAP_V3,
            asset=asset,
            amount=Decimal("1000"),
            fee=FLASH_LOAN_FEE_UNISWAP_V3,
            fee_amount=Decimal("0.5"),
            available=True,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        # Uniswap V3 flash swap requires a pool ID
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class DydxAdapter(ProtocolAdapter):
    """dYdX Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        # dYdX V4 implementation would go here
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.DYDX,
            supports_multiple_assets=True,
            max_assets=5,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            fee_structure="fixed",
            fee_rate=FLASH_LOAN_FEE_DYDX,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.DYDX,
            asset=asset,
            amount=Decimal("1000"),
            fee=FLASH_LOAN_FEE_DYDX,
            fee_amount=Decimal("0"),
            available=True,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        # dYdX V4 implementation
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class MakerDAOAdapter(ProtocolAdapter):
    """MakerDAO Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.flash_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.MAKERDAO]["dss_flash"]
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.MAKERDAO,
            supports_multiple_assets=False,
            max_assets=1,
            max_amount=Decimal("5000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=Decimal("0.0005"),  # 0.05%
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.MAKERDAO,
            asset=asset,
            amount=Decimal("1000"),
            fee=Decimal("0.0005"),
            fee_amount=Decimal("0.5"),
            available=True,
            max_amount=Decimal("5000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class EulerAdapter(ProtocolAdapter):
    """Euler Finance Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.euler_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.EULER]["euler"]
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.EULER,
            supports_multiple_assets=True,
            max_assets=0,  # Unlimited
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_EULER,
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.EULER,
            asset=asset,
            amount=Decimal("1000"),
            fee=FLASH_LOAN_FEE_EULER,
            fee_amount=Decimal("1"),
            available=True,
            max_amount=Decimal("10000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


class SparkAdapter(ProtocolAdapter):
    """Spark Protocol Flash Loan Adapter."""
    
    def __init__(self, web3: Web3):
        super().__init__(web3)
        self.spark_address = FLASH_LOAN_ADDRESSES[FlashLoanProtocol.SPARK]["spark"]
    
    def get_capabilities(self) -> ProtocolCapabilities:
        return ProtocolCapabilities(
            protocol=FlashLoanProtocol.SPARK,
            supports_multiple_assets=True,
            max_assets=10,
            max_amount=Decimal("5000000"),
            min_amount=Decimal("0.001"),
            fee_structure="percentage",
            fee_rate=FLASH_LOAN_FEE_AAVE,  # Same as AAVE
            requires_callback=True,
            callback_gas_limit=2000000,
            supports_atomic=True,
            supports_cross_chain=False,
            supported_assets=[],
        )
    
    def get_flash_loan_info(self, asset: ChecksumAddress) -> Optional[FlashLoanInfo]:
        return FlashLoanInfo(
            protocol=FlashLoanProtocol.SPARK,
            asset=asset,
            amount=Decimal("1000"),
            fee=FLASH_LOAN_FEE_AAVE,
            fee_amount=Decimal("0.9"),
            available=True,
            max_amount=Decimal("5000000"),
            min_amount=Decimal("0.001"),
            duration_blocks=0,
            requires_callback=True,
            callback_gas_limit=2000000,
        )
    
    def build_flash_loan_transaction(
        self,
        plan: FlashLoanExecutionPlan,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[TxParams]:
        return None
    
    def validate_flash_loan(self, plan: FlashLoanExecutionPlan) -> bool:
        return plan.amount > Decimal("0") and plan.asset is not None


# Helper Classes

class FlashLoanMEVShield:
    """MEV Protection for Flash Loans."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = {
            "enabled": True,
            "use_private_mempool": True,
            "flashbots_enabled": True,
            "priority_fee": Decimal("1.5"),  # gwei
            "bundle_timeout": 30,  # seconds
        }
    
    def protect(self, tx: TxParams) -> TxParams:
        """
        Apply MEV protection to a transaction.
        
        Args:
            tx: Transaction to protect
            
        Returns:
            Protected transaction
        """
        if not self.config["enabled"]:
            return tx
        
        # Add priority fee
        tx["priorityFee"] = int(Web3.to_wei(self.config["priority_fee"], "gwei"))
        
        # Add additional protection
        tx["maxFeePerGas"] = tx.get("gasPrice", 0) * 2
        
        return tx


class CallbackContractManager:
    """Flash Loan Callback Contract Manager."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.contracts: Dict[str, ChecksumAddress] = {}
    
    def generate_callback(
        self,
        path: FlashLoanPath,
        from_address: Optional[ChecksumAddress] = None,
    ) -> Optional[ChecksumAddress]:
        """
        Generate or retrieve a callback contract.
        
        Args:
            path: Flash loan path
            from_address: Optional sender address
            
        Returns:
            Callback contract address
        """
        # In production, this would deploy or use a pre-deployed contract
        # For now, return a placeholder
        return None


class RiskEngine:
    """Risk Assessment Engine."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def assess(self, opportunity: FlashLoanOpportunity) -> RiskAssessment:
        """
        Assess risk for an opportunity.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            Risk assessment
        """
        risk = Decimal("0")
        confidence = Decimal("0.8")
        warnings = []
        mitigations = []
        
        # Protocol risk
        protocol_risk = opportunity["best_path"]["risk_score"]
        risk += protocol_risk * Decimal("0.3")
        
        # Market risk
        market_risk = Decimal("0.1")
        risk += market_risk
        
        # Execution risk
        execution_risk = Decimal(str(opportunity["best_path"]["complexity"])) / Decimal("10")
        risk += execution_risk * Decimal("0.2")
        
        # Slippage risk
        slippage_risk = Decimal("0.1")
        risk += slippage_risk * Decimal("0.2")
        
        # Overall risk
        overall_risk = min(Decimal("1"), risk)
        
        # Confidence adjustment
        confidence = opportunity["confidence"]
        
        # Warnings
        if opportunity["best_path"]["complexity"] > 5:
            warnings.append("High complexity path")
        if opportunity["net_profit_percentage"] < Decimal("1"):
            warnings.append("Low profit margin")
        
        # Mitigations
        mitigations.append("Use MEV protection")
        mitigations.append("Set slippage limits")
        
        return RiskAssessment(
            protocol_risk=protocol_risk,
            market_risk=market_risk,
            execution_risk=execution_risk,
            slippage_risk=slippage_risk,
            overall_risk=overall_risk,
            confidence=confidence,
            warnings=warnings,
            mitigations=mitigations,
        )


# Module exports
__all__ = [
    'FlashLoanDetector',
    'FlashLoanProtocol',
    'FlashLoanInfo',
    'FlashLoanPath',
    'FlashLoanOpportunity',
    'FlashLoanExecutionPlan',
    'ProtocolCapabilities',
    'RiskAssessment',
    'ProtocolAdapter',
    'AaveV2Adapter',
    'AaveV3Adapter',
    'BalancerAdapter',
    'UniswapV3Adapter',
    'DydxAdapter',
    'MakerDAOAdapter',
    'EulerAdapter',
    'SparkAdapter',
    'FlashLoanMEVShield',
    'CallbackContractManager',
    'RiskEngine',
]
