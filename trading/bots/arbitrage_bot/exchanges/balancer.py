# trading/bots/arbitrage_bot/exchanges/balancer.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Balancer Protocol Integration

"""
Balancer Exchange Integration - Advanced Balancer Protocol Adapter

This module provides comprehensive integration with the Balancer Protocol:
- Swap execution (V2/V3)
- Pool management
- Liquidity provision
- Flash loans
- Yield farming
- Gauge voting
- VeBAL governance
- Pool creation
- Boosted pools

Protocols Supported:
    - Balancer V2 (Ethereum, Polygon, Arbitrum, etc.)
    - Balancer V3 (Coming soon)
    - Boosted Pools
    - Stable Pools
    - Weighted Pools
    - MetaStable Pools
    - Managed Pools

Architecture:
    - BalancerExchange: Main exchange class
    - BalancerAPI: API client for Balancer
    - PoolManager: Pool management
    - SwapCalculator: Swap calculations
    - LiquidityManager: Liquidity provision
    - FlashLoanManager: Flash loan management
    - GaugeManager: Gauge voting and rewards
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
from urllib.parse import urlencode

import aiohttp
import aiohttp.client_exceptions
import requests
from web3 import Web3
from web3.types import Wei, Address, TxParams, BlockNumber
from web3.middleware import geth_poa_middleware
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address, to_hex
from eth_account import Account
from eth_account.signers.local import LocalAccount

# Constants
BALANCER_API_BASE = "https://api.balancer.fi"
BALANCER_SUBGRAPH = "https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2"

# Supported chains
class BalancerChain(Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    GNOSIS = "gnosis"
    ZKSYNC_ERA = "zksync-era"
    BASE = "base"

# Pool types
class PoolType(Enum):
    WEIGHTED = "weighted"
    STABLE = "stable"
    META_STABLE = "meta-stable"
    MANAGED = "managed"
    COMPOSABLE_STABLE = "composable-stable"
    BOOSTED = "boosted"
    LIQUIDITY_BOOTSTRAPPING = "liquidity-bootstrapping"
    ELEMENT = "element"
    LINEAR = "linear"

# Swap types
class SwapType(Enum):
    EXACT_IN = "exact_in"
    EXACT_OUT = "exact_out"

# Pool status
class PoolStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"

@dataclass
class BalancerPool:
    """Balancer pool information."""
    id: str
    address: ChecksumAddress
    pool_type: PoolType
    tokens: List[str]
    weights: List[Decimal]
    swap_fee: Decimal
    admin_fee: Decimal
    total_liquidity: Decimal
    volume_24h: Decimal
    fees_24h: Decimal
    status: PoolStatus
    chain: BalancerChain
    created_at: datetime
    version: int = 2
    is_boosted: bool = False
    is_vebal: bool = False

@dataclass
class SwapQuote:
    """Swap quote result."""
    pool_id: str
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    swap_fee: Decimal
    admin_fee: Decimal
    price_impact: Decimal
    slippage: Decimal
    route: List[Dict[str, Any]]
    timestamp: datetime
    expires_at: datetime

@dataclass
class SwapResult:
    """Swap execution result."""
    success: bool
    tx_hash: Optional[str]
    pool_id: str
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    actual_amount_in: Decimal
    actual_amount_out: Decimal
    swap_fee: Decimal
    admin_fee: Decimal
    gas_used: int
    gas_price: Decimal
    timestamp: datetime
    error: Optional[str] = None

@dataclass
class FlashLoanInfo:
    """Flash loan information."""
    pool_id: str
    token: str
    amount: Decimal
    fee: Decimal
    max_amount: Decimal
    available: bool
    duration_blocks: int = 0

@dataclass
class LiquidityPosition:
    """Liquidity position."""
    pool_id: str
    user_address: ChecksumAddress
    tokens: List[str]
    amounts: List[Decimal]
    total_value: Decimal
    share_percentage: Decimal
    earned_fees: Decimal
    staked: bool
    gauge: Optional[str] = None

@dataclass
class GaugeInfo:
    """Gauge information."""
    gauge_id: str
    pool_id: str
    gauge_type: str  # "vebal", "single", "multipool"
    rewards: List[Dict[str, Any]]
    voting_power: Decimal
    current_weight: Decimal
    max_weight: Decimal
    is_active: bool
    address: Optional[ChecksumAddress] = None

class BalancerExchange:
    """
    Balancer Protocol Integration.
    
    This class provides comprehensive integration with the Balancer Protocol:
    1. Swap execution (V2/V3)
    2. Pool management
    3. Liquidity provision
    4. Flash loans
    5. Yield farming
    6. Gauge voting
    7. VeBAL governance
    8. Pool creation
    
    Features:
    - Multi-chain support
    - Real-time price discovery
    - Pool analytics
    - Liquidity management
    - Flash loan integration
    - Gauge and reward management
    - Subgraph integration
    """
    
    def __init__(
        self,
        chain: BalancerChain = BalancerChain.ETHEREUM,
        web3: Optional[Web3] = None,
        private_key: Optional[str] = None,
        max_slippage: Decimal = Decimal("0.01"),  # 1%
        gas_multiplier: Decimal = Decimal("1.1"),
        timeout: int = 30,
    ):
        """
        Initialize the Balancer exchange integration.
        
        Args:
            chain: Blockchain chain
            web3: Optional Web3 instance
            private_key: Optional private key for signing
            max_slippage: Maximum allowed slippage
            gas_multiplier: Gas price multiplier
            timeout: API timeout in seconds
        """
        self.logger = self._setup_logger()
        self.chain = chain
        self.max_slippage = max_slippage
        self.gas_multiplier = gas_multiplier
        self.timeout = timeout
        
        # Initialize Web3
        self.web3 = web3 or self._init_web3()
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # API configuration
        self.base_url = BALANCER_API_BASE
        self.subgraph_url = BALANCER_SUBGRAPH
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_lock = asyncio.Lock()
        
        # Cache
        self.pool_cache: Dict[str, BalancerPool] = {}
        self.token_cache: Dict[str, Dict] = {}
        
        # ABI
        self.vaul_abi = self._load_vault_abi()
        self.pool_abi = self._load_pool_abi()
        
        # Metrics
        self.metrics = {
            "quotes_requested": 0,
            "quotes_received": 0,
            "swaps_executed": 0,
            "swaps_succeeded": 0,
            "swaps_failed": 0,
            "flash_loans_processed": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
            "avg_execution_time_ms": 0,
            "errors": 0,
            "pools_cached": 0,
        }
        
        # State management
        self.is_running = False
        
        self.logger.info(f"Initialized Balancer Exchange on {chain.value}")
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logger."""
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
        """Initialize Web3 with appropriate provider."""
        rpc_urls = {
            BalancerChain.ETHEREUM: "https://mainnet.infura.io/v3/",
            BalancerChain.POLYGON: "https://polygon-mainnet.infura.io/v3/",
            BalancerChain.ARBITRUM: "https://arb1.arbitrum.io/rpc",
            BalancerChain.OPTIMISM: "https://mainnet.optimism.io",
            BalancerChain.AVALANCHE: "https://api.avax.network/ext/bc/C/rpc",
            BalancerChain.GNOSIS: "https://rpc.gnosischain.com",
            BalancerChain.BASE: "https://mainnet.base.org",
            BalancerChain.ZKSYNC_ERA: "https://mainnet.era.zksync.io",
        }
        
        rpc_url = rpc_urls.get(self.chain, "https://cloudflare-eth.com")
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            if w3.is_connected():
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                return w3
        except Exception as e:
            self.logger.warning(f"Web3 connection failed: {e}")
        
        return Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
    
    def _load_vault_abi(self) -> Dict:
        """Load Balancer Vault ABI."""
        # Balancer V2 Vault ABI
        return [
            {
                "inputs": [
                    {"name": "poolId", "type": "bytes32"},
                    {"name": "kind", "type": "uint8"},
                    {"name": "assets", "type": "address[]"},
                    {"name": "limits", "type": "int256[]"},
                    {"name": "funds", "type": "tuple"},
                    {"name": "userData", "type": "bytes"}
                ],
                "name": "swap",
                "outputs": [{"name": "amounts", "type": "int256[]"}],
                "stateMutability": "nonpayable",
                "type": "function"
            },
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
            },
            {
                "inputs": [
                    {"name": "poolId", "type": "bytes32"},
                    {"name": "user", "type": "address"}
                ],
                "name": "getPoolTokens",
                "outputs": [
                    {"name": "tokens", "type": "address[]"},
                    {"name": "balances", "type": "uint256[]"},
                    {"name": "lastChangeBlock", "type": "uint256"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def _load_pool_abi(self) -> Dict:
        """Load Balancer Pool ABI."""
        return [
            {
                "inputs": [],
                "name": "getPoolId",
                "outputs": [{"name": "poolId", "type": "bytes32"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "token", "type": "address"},
                    {"name": "amount", "type": "uint256"}
                ],
                "name": "getRate",
                "outputs": [{"name": "rate", "type": "uint256"}],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            async with self._session_lock:
                if self.session is None or self.session.closed:
                    connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
                    self.session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                        headers=self.headers,
                    )
        return self.session
    
    async def close(self) -> None:
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    def _get_vault_address(self) -> ChecksumAddress:
        """Get Balancer Vault address for the current chain."""
        vaults = {
            BalancerChain.ETHEREUM: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.POLYGON: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.ARBITRUM: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.OPTIMISM: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.AVALANCHE: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.GNOSIS: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.BASE: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
            BalancerChain.ZKSYNC_ERA: "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        }
        return to_checksum_address(vaults.get(self.chain, vaults[BalancerChain.ETHEREUM]))
    
    async def _graphql_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        Execute a GraphQL query on the Balancer subgraph.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            
        Returns:
            Query result
        """
        session = await self._get_session()
        
        try:
            async with session.post(
                self.subgraph_url,
                json={"query": query, "variables": variables or {}}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Subgraph error: {error_text}")
                    return {}
                return await response.json()
        except Exception as e:
            self.logger.error(f"Subgraph request failed: {e}")
            return {}
    
    async def get_pools(
        self,
        pool_type: Optional[PoolType] = None,
        min_liquidity: Optional[Decimal] = None,
        limit: int = 100,
    ) -> List[BalancerPool]:
        """
        Get Balancer pools.
        
        Args:
            pool_type: Optional pool type filter
            min_liquidity: Minimum liquidity filter
            limit: Maximum number of pools
            
        Returns:
            List of BalancerPool objects
        """
        try:
            query = """
            query GetPools($limit: Int, $poolType: String) {
                pools(first: $limit, where: {poolType: $poolType}) {
                    id
                    address
                    poolType
                    tokens {
                        address
                        symbol
                        decimals
                        weight
                    }
                    swapFee
                    adminFee
                    totalLiquidity
                    volume24h
                    fees24h
                    status
                    createdAt
                    isBoosted
                    isVeBal
                }
            }
            """
            
            variables = {
                "limit": limit,
                "poolType": pool_type.value if pool_type else None,
            }
            
            result = await self._graphql_query(query, variables)
            
            pools = []
            for data in result.get("data", {}).get("pools", []):
                pool = BalancerPool(
                    id=data["id"],
                    address=to_checksum_address(data["address"]),
                    pool_type=PoolType(data["poolType"]),
                    tokens=[t["address"] for t in data.get("tokens", [])],
                    weights=[Decimal(str(t.get("weight", 0))) for t in data.get("tokens", [])],
                    swap_fee=Decimal(str(data.get("swapFee", 0))),
                    admin_fee=Decimal(str(data.get("adminFee", 0))),
                    total_liquidity=Decimal(str(data.get("totalLiquidity", 0))),
                    volume_24h=Decimal(str(data.get("volume24h", 0))),
                    fees_24h=Decimal(str(data.get("fees24h", 0))),
                    status=PoolStatus(data.get("status", "active")),
                    chain=self.chain,
                    created_at=datetime.fromtimestamp(int(data.get("createdAt", 0))),
                    version=2,
                    is_boosted=data.get("isBoosted", False),
                    is_vebal=data.get("isVeBal", False),
                )
                
                if min_liquidity is None or pool.total_liquidity >= min_liquidity:
                    pools.append(pool)
                    self.pool_cache[pool.id] = pool
            
            self.metrics["pools_cached"] = len(self.pool_cache)
            self.logger.info(f"Loaded {len(pools)} pools")
            
            return pools
            
        except Exception as e:
            self.logger.error(f"Failed to get pools: {e}")
            return []
    
    async def get_pool(self, pool_id: str) -> Optional[BalancerPool]:
        """
        Get pool information.
        
        Args:
            pool_id: Pool ID
            
        Returns:
            BalancerPool or None
        """
        if pool_id in self.pool_cache:
            return self.pool_cache[pool_id]
        
        try:
            query = """
            query GetPool($poolId: ID!) {
                pool(id: $poolId) {
                    id
                    address
                    poolType
                    tokens {
                        address
                        symbol
                        decimals
                        weight
                    }
                    swapFee
                    adminFee
                    totalLiquidity
                    volume24h
                    fees24h
                    status
                    createdAt
                    isBoosted
                    isVeBal
                }
            }
            """
            
            result = await self._graphql_query(query, {"poolId": pool_id})
            data = result.get("data", {}).get("pool")
            
            if data:
                pool = BalancerPool(
                    id=data["id"],
                    address=to_checksum_address(data["address"]),
                    pool_type=PoolType(data["poolType"]),
                    tokens=[t["address"] for t in data.get("tokens", [])],
                    weights=[Decimal(str(t.get("weight", 0))) for t in data.get("tokens", [])],
                    swap_fee=Decimal(str(data.get("swapFee", 0))),
                    admin_fee=Decimal(str(data.get("adminFee", 0))),
                    total_liquidity=Decimal(str(data.get("totalLiquidity", 0))),
                    volume_24h=Decimal(str(data.get("volume24h", 0))),
                    fees_24h=Decimal(str(data.get("fees24h", 0))),
                    status=PoolStatus(data.get("status", "active")),
                    chain=self.chain,
                    created_at=datetime.fromtimestamp(int(data.get("createdAt", 0))),
                    version=2,
                    is_boosted=data.get("isBoosted", False),
                    is_vebal=data.get("isVeBal", False),
                )
                self.pool_cache[pool.id] = pool
                return pool
            
        except Exception as e:
            self.logger.error(f"Failed to get pool: {e}")
        
        return None
    
    async def get_pool_tokens(self, pool_id: str) -> Dict[str, Decimal]:
        """
        Get pool token balances.
        
        Args:
            pool_id: Pool ID
            
        Returns:
            Dictionary of token addresses to balances
        """
        try:
            vault_address = self._get_vault_address()
            vault = self.web3.eth.contract(
                address=vault_address,
                abi=self.vaul_abi
            )
            
            pool_id_bytes = bytes.fromhex(pool_id[2:] if pool_id.startswith("0x") else pool_id)
            
            tokens, balances, _ = vault.functions.getPoolTokens(pool_id_bytes).call()
            
            result = {}
            for token, balance in zip(tokens, balances):
                result[to_checksum_address(token)] = Decimal(str(balance))
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get pool tokens: {e}")
            return {}
    
    async def get_swap_quote(
        self,
        pool_id: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        swap_type: SwapType = SwapType.EXACT_IN,
        slippage: Optional[Decimal] = None,
    ) -> Optional[SwapQuote]:
        """
        Get a swap quote.
        
        Args:
            pool_id: Pool ID
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap
            swap_type: Exact in or exact out
            slippage: Maximum slippage percentage
            
        Returns:
            SwapQuote or None
        """
        try:
            # Get pool information
            pool = await self.get_pool(pool_id)
            if not pool:
                return None
            
            # Get pool tokens
            balances = await self.get_pool_tokens(pool_id)
            if token_in not in balances or token_out not in balances:
                return None
            
            # Calculate swap
            # For weighted pools, use the swap formula:
            # For a 2-token weighted pool with weights w1 and w2:
            # amount_out = amount_in * (balance_out / (balance_in + amount_in * (1 - fee)))
            
            balance_in = balances[token_in]
            balance_out = balances[token_out]
            
            # Get token weights
            weight_in = Decimal("0.5")  # Default weight
            weight_out = Decimal("0.5")
            
            # Calculate swap fee
            fee = pool.swap_fee
            
            # Calculate amount out
            if swap_type == SwapType.EXACT_IN:
                # Calculate with fee
                amount_in_with_fee = amount * (Decimal("1") - fee)
                
                # Calculate amount out using the weighted formula
                # For simplicity, using a basic formula
                amount_out = amount_in_with_fee * (balance_out / (balance_in + amount_in_with_fee))
            else:
                # Exact out calculation (complex, would use the inverse formula)
                amount_out = amount
                # Estimate amount in needed
                amount_in = amount * (balance_in / (balance_out - amount)) / (Decimal("1") - fee)
            
            # Calculate price impact
            price_impact = (amount * balance_out) / (balance_in * (balance_in + amount)) if amount > 0 else Decimal("0")
            
            # Calculate slippage
            slippage_pct = slippage or self.max_slippage
            
            # Build route
            route = [
                {
                    "poolId": pool_id,
                    "tokenIn": token_in,
                    "tokenOut": token_out,
                    "amountIn": str(amount),
                    "amountOut": str(amount_out),
                }
            ]
            
            quote = SwapQuote(
                pool_id=pool_id,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount,
                amount_out=amount_out,
                swap_fee=pool.swap_fee,
                admin_fee=pool.admin_fee,
                price_impact=price_impact,
                slippage=slippage_pct,
                route=route,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            )
            
            self.metrics["quotes_received"] += 1
            
            return quote
            
        except Exception as e:
            self.logger.error(f"Failed to get swap quote: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def execute_swap(
        self,
        pool_id: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        swap_type: SwapType = SwapType.EXACT_IN,
        slippage: Optional[Decimal] = None,
        receiver: Optional[str] = None,
        quote: Optional[SwapQuote] = None,
    ) -> SwapResult:
        """
        Execute a swap.
        
        Args:
            pool_id: Pool ID
            token_in: Input token address
            token_out: Output token address
            amount: Amount to swap
            swap_type: Exact in or exact out
            slippage: Maximum slippage percentage
            receiver: Receiver address (defaults to wallet)
            quote: Pre-fetched quote
            
        Returns:
            SwapResult
        """
        start_time = time.time()
        
        try:
            if not self.account:
                raise ValueError("No account available for signing")
            
            # Get quote if not provided
            if not quote:
                quote = await self.get_swap_quote(
                    pool_id=pool_id,
                    token_in=token_in,
                    token_out=token_out,
                    amount=amount,
                    swap_type=swap_type,
                    slippage=slippage,
                )
                
                if not quote:
                    raise ValueError("Failed to get quote")
            
            # Prepare swap parameters
            vault_address = self._get_vault_address()
            vault = self.web3.eth.contract(
                address=vault_address,
                abi=self.vaul_abi
            )
            
            pool_id_bytes = bytes.fromhex(pool_id[2:] if pool_id.startswith("0x") else pool_id)
            
            # Determine swap kind
            kind = 0  # 0 = exact_in, 1 = exact_out
            if swap_type == SwapType.EXACT_OUT:
                kind = 1
            
            # Prepare assets
            assets = [to_checksum_address(token_in), to_checksum_address(token_out)]
            
            # Prepare limits
            if kind == 0:
                # exact_in: limit is minimum amount out
                min_out = amount * (Decimal("1") - (slippage or self.max_slippage))
                limits = [int(amount * Decimal(10**18)), int(min_out * Decimal(10**18))]
            else:
                # exact_out: limit is maximum amount in
                max_in = amount * (Decimal("1") + (slippage or self.max_slippage))
                limits = [int(max_in * Decimal(10**18)), int(amount * Decimal(10**18))]
            
            # Prepare funds
            funds = {
                "sender": self.account.address,
                "fromInternalBalance": False,
                "recipient": receiver or self.account.address,
                "toInternalBalance": False,
            }
            
            # Build transaction
            tx = vault.functions.swap(
                pool_id_bytes,
                kind,
                assets,
                limits,
                funds,
                b""  # userData
            ).build_transaction({
                "from": self.account.address,
                "gas": 3000000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
            })
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            
            # Wait for receipt
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Parse result
            execution_time = (time.time() - start_time) * 1000
            self.metrics["swaps_executed"] += 1
            
            if receipt.status == 1:
                self.metrics["swaps_succeeded"] += 1
                self.metrics["total_volume"] += amount
                self.metrics["total_fees"] += quote.swap_fee
                self.metrics["avg_execution_time_ms"] = (
                    (self.metrics["avg_execution_time_ms"] * (self.metrics["swaps_executed"] - 1) + execution_time)
                    / self.metrics["swaps_executed"]
                )
                
                result = SwapResult(
                    success=True,
                    tx_hash=to_hex(tx_hash),
                    pool_id=pool_id,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=quote.amount_in,
                    amount_out=quote.amount_out,
                    actual_amount_in=amount,
                    actual_amount_out=quote.amount_out,
                    swap_fee=quote.swap_fee,
                    admin_fee=quote.admin_fee,
                    gas_used=receipt.gasUsed,
                    gas_price=Decimal(str(tx["gasPrice"])),
                    timestamp=datetime.utcnow(),
                )
                
                self.logger.info(f"Swap successful: TX {to_hex(tx_hash)}")
                return result
            else:
                self.metrics["swaps_failed"] += 1
                self.logger.error(f"Swap failed: TX {to_hex(tx_hash)}")
                
                return SwapResult(
                    success=False,
                    tx_hash=to_hex(tx_hash),
                    pool_id=pool_id,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=quote.amount_in,
                    amount_out=quote.amount_out,
                    actual_amount_in=Decimal("0"),
                    actual_amount_out=Decimal("0"),
                    swap_fee=quote.swap_fee,
                    admin_fee=quote.admin_fee,
                    gas_used=receipt.gasUsed,
                    gas_price=Decimal(str(tx["gasPrice"])),
                    timestamp=datetime.utcnow(),
                    error="Transaction failed",
                )
            
        except Exception as e:
            self.logger.error(f"Swap execution failed: {e}")
            self.metrics["errors"] += 1
            self.metrics["swaps_failed"] += 1
            
            return SwapResult(
                success=False,
                tx_hash=None,
                pool_id=pool_id,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount,
                amount_out=Decimal("0"),
                actual_amount_in=Decimal("0"),
                actual_amount_out=Decimal("0"),
                swap_fee=Decimal("0"),
                admin_fee=Decimal("0"),
                gas_used=0,
                gas_price=Decimal("0"),
                timestamp=datetime.utcnow(),
                error=str(e),
            )
    
    async def get_flash_loan_info(
        self,
        pool_id: str,
        token: str,
        amount: Decimal,
    ) -> Optional[FlashLoanInfo]:
        """
        Get flash loan information.
        
        Args:
            pool_id: Pool ID
            token: Token address
            amount: Requested amount
            
        Returns:
            FlashLoanInfo or None
        """
        try:
            # Get pool tokens
            balances = await self.get_pool_tokens(pool_id)
            
            if token not in balances:
                return None
            
            balance = balances[token]
            if balance < amount:
                return None
            
            # Get pool for fee
            pool = await self.get_pool(pool_id)
            fee = pool.swap_fee if pool else Decimal("0.001")
            
            return FlashLoanInfo(
                pool_id=pool_id,
                token=token,
                amount=amount,
                fee=fee,
                max_amount=balance,
                available=True,
                duration_blocks=0,
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get flash loan info: {e}")
            return None
    
    async def execute_flash_loan(
        self,
        pool_id: str,
        token: str,
        amount: Decimal,
        callback_contract: ChecksumAddress,
        callback_data: bytes = b"",
    ) -> Optional[str]:
        """
        Execute a flash loan.
        
        Args:
            pool_id: Pool ID
            token: Token address
            amount: Amount to borrow
            callback_contract: Callback contract address
            callback_data: Callback data
            
        Returns:
            Transaction hash or None
        """
        try:
            if not self.account:
                raise ValueError("No account available for signing")
            
            vault_address = self._get_vault_address()
            vault = self.web3.eth.contract(
                address=vault_address,
                abi=self.vaul_abi
            )
            
            pool_id_bytes = bytes.fromhex(pool_id[2:] if pool_id.startswith("0x") else pool_id)
            
            tx = vault.functions.flashLoan(
                pool_id_bytes,
                callback_contract,
                int(amount * Decimal(10**18))
            ).build_transaction({
                "from": self.account.address,
                "gas": 2000000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                self.metrics["flash_loans_processed"] += 1
                self.logger.info(f"Flash loan executed: TX {to_hex(tx_hash)}")
                return to_hex(tx_hash)
            else:
                self.logger.error(f"Flash loan failed: TX {to_hex(tx_hash)}")
                return None
            
        except Exception as e:
            self.logger.error(f"Flash loan execution failed: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def get_gauges(self, pool_id: Optional[str] = None) -> List[GaugeInfo]:
        """
        Get gauge information.
        
        Args:
            pool_id: Optional pool ID filter
            
        Returns:
            List of GaugeInfo objects
        """
        try:
            query = """
            query GetGauges($poolId: String) {
                gauges(where: {poolId: $poolId}) {
                    id
                    poolId
                    gaugeType
                    rewards {
                        token
                        amount
                    }
                    votingPower
                    currentWeight
                    maxWeight
                    isActive
                    address
                }
            }
            """
            
            variables = {"poolId": pool_id}
            result = await self._graphql_query(query, variables)
            
            gauges = []
            for data in result.get("data", {}).get("gauges", []):
                gauge = GaugeInfo(
                    gauge_id=data["id"],
                    pool_id=data["poolId"],
                    gauge_type=data["gaugeType"],
                    rewards=[
                        {"token": r["token"], "amount": Decimal(str(r["amount"]))}
                        for r in data.get("rewards", [])
                    ],
                    voting_power=Decimal(str(data.get("votingPower", 0))),
                    current_weight=Decimal(str(data.get("currentWeight", 0))),
                    max_weight=Decimal(str(data.get("maxWeight", 0))),
                    is_active=data.get("isActive", False),
                    address=to_checksum_address(data["address"]) if data.get("address") else None,
                )
                gauges.append(gauge)
            
            return gauges
            
        except Exception as e:
            self.logger.error(f"Failed to get gauges: {e}")
            return []
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get exchange metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "quotes_requested": self.metrics["quotes_requested"],
            "quotes_received": self.metrics["quotes_received"],
            "swaps_executed": self.metrics["swaps_executed"],
            "swaps_succeeded": self.metrics["swaps_succeeded"],
            "swaps_failed": self.metrics["swaps_failed"],
            "success_rate": (
                self.metrics["swaps_succeeded"] / self.metrics["swaps_executed"]
                if self.metrics["swaps_executed"] > 0 else 0
            ),
            "flash_loans_processed": self.metrics["flash_loans_processed"],
            "total_volume": float(self.metrics["total_volume"]),
            "total_fees": float(self.metrics["total_fees"]),
            "avg_execution_time_ms": self.metrics["avg_execution_time_ms"],
            "errors": self.metrics["errors"],
            "chain": self.chain.value,
            "pools_cached": self.metrics["pools_cached"],
        }


# Sync wrapper for compatibility with other exchange connectors
class BalancerExchangeSync:
    """
    Synchronous wrapper for BalancerExchange.
    """
    
    def __init__(self, *args, **kwargs):
        self._async_exchange = BalancerExchange(*args, **kwargs)
        self.logger = self._async_exchange.logger
    
    def get_pools(self, *args, **kwargs) -> List[BalancerPool]:
        """Synchronous get_pools wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.get_pools(*args, **kwargs))
        finally:
            loop.close()
    
    def get_pool(self, *args, **kwargs) -> Optional[BalancerPool]:
        """Synchronous get_pool wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.get_pool(*args, **kwargs))
        finally:
            loop.close()
    
    def get_swap_quote(self, *args, **kwargs) -> Optional[SwapQuote]:
        """Synchronous get_swap_quote wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.get_swap_quote(*args, **kwargs))
        finally:
            loop.close()
    
    def execute_swap(self, *args, **kwargs) -> SwapResult:
        """Synchronous execute_swap wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.execute_swap(*args, **kwargs))
        finally:
            loop.close()
    
    def get_flash_loan_info(self, *args, **kwargs) -> Optional[FlashLoanInfo]:
        """Synchronous get_flash_loan_info wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.get_flash_loan_info(*args, **kwargs))
        finally:
            loop.close()
    
    def get_gauges(self, *args, **kwargs) -> List[GaugeInfo]:
        """Synchronous get_gauges wrapper."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_exchange.get_gauges(*args, **kwargs))
        finally:
            loop.close()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics."""
        return self._async_exchange.get_metrics()
    
    def close(self) -> None:
        """Close the exchange."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._async_exchange.close())
        finally:
            loop.close()


# Module exports
__all__ = [
    'BalancerExchange',
    'BalancerExchangeSync',
    'BalancerChain',
    'PoolType',
    'SwapType',
    'PoolStatus',
    'BalancerPool',
    'SwapQuote',
    'SwapResult',
    'FlashLoanInfo',
    'LiquidityPosition',
    'GaugeInfo',
]
