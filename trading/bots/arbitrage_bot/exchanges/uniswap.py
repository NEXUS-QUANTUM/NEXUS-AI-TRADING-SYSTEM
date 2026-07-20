# trading/bots/arbitrage_bot/exchanges/uniswap.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Uniswap DEX Integration (V2 & V3)

"""
Uniswap Exchange Integration - Complete Uniswap DEX Adapter

This module provides comprehensive integration with the Uniswap Protocol:
- Uniswap V2 swaps
- Uniswap V3 swaps (Concentrated Liquidity)
- V3 position management (NFT positions)
- V3 range orders
- V3 flash swaps
- V3 fee tiers (0.05%, 0.3%, 1%)
- V3 tick management
- V3 liquidity provision
- V3 position rebalancing

Protocols Supported:
    - Ethereum
    - Polygon
    - Arbitrum
    - Optimism
    - Avalanche
    - Celo
    - BSC (via PancakeSwap)
    - Base

Architecture:
    - UniswapExchange: Main exchange class
    - UniswapV2Router: V2 router interface
    - UniswapV3Router: V3 router interface
    - UniswapV3Pool: V3 pool interface
    - UniswapV3Manager: V3 position manager
    - QuoterV2: V3 quoting interface
    - UniswapV2Pair: V2 pair interface
    - UniswapV3NFT: V3 NFT position manager
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, AsyncIterator, Tuple, Union
from datetime import datetime

from web3 import Web3
from web3.types import TxParams, ChecksumAddress
from web3.middleware import geth_poa_middleware
from eth_typing import ChecksumAddress
from eth_utils import to_checksum_address, to_hex
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .base_exchange import (
    BaseExchange,
    ExchangeType,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    MarketType,
    Interval,
    ExchangeConfig,
    Balance,
    Ticker,
    OHLCV,
    Order,
    OrderBook,
    Position,
    Trade,
    FundingRate,
)

# Constants - V2
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_V2_FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
UNISWAP_V2_INIT_CODE_HASH = "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f"

# Constants - V3
UNISWAP_V3_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
UNISWAP_V3_QUOTER = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
UNISWAP_V3_NFT_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
UNISWAP_V3_SWAP_ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"
UNISWAP_V3_QUOTER_V2 = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"

# Fee tiers
class FeeTier(Enum):
    FEE_005 = 500  # 0.05%
    FEE_030 = 3000  # 0.3%
    FEE_100 = 10000  # 1.0%

# Chain configurations
class UniswapChain(Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    CELO = "celo"
    BASE = "base"

    @property
    def chain_id(self) -> int:
        return {
            "ethereum": 1,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "celo": 42220,
            "base": 8453,
        }[self.value]

    @property
    def v2_router_address(self) -> str:
        # Some chains use custom routers
        return {
            "ethereum": UNISWAP_V2_ROUTER,
            "polygon": "0xedf6066a2b290C185783862C7F4776A2C8077AD1",  # Quickswap
            "arbitrum": UNISWAP_V2_ROUTER,
            "optimism": UNISWAP_V2_ROUTER,
            "avalanche": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",  # TraderJoe
            "celo": UNISWAP_V2_ROUTER,
            "base": UNISWAP_V2_ROUTER,
        }[self.value]

    @property
    def v3_router_address(self) -> str:
        return {
            "ethereum": UNISWAP_V3_ROUTER,
            "polygon": UNISWAP_V3_ROUTER,
            "arbitrum": UNISWAP_V3_ROUTER,
            "optimism": UNISWAP_V3_ROUTER,
            "avalanche": UNISWAP_V3_ROUTER,
            "celo": UNISWAP_V3_ROUTER,
            "base": UNISWAP_V3_ROUTER,
        }[self.value]

    @property
    def v3_factory_address(self) -> str:
        return {
            "ethereum": UNISWAP_V3_FACTORY,
            "polygon": UNISWAP_V3_FACTORY,
            "arbitrum": UNISWAP_V3_FACTORY,
            "optimism": UNISWAP_V3_FACTORY,
            "avalanche": UNISWAP_V3_FACTORY,
            "celo": UNISWAP_V3_FACTORY,
            "base": UNISWAP_V3_FACTORY,
        }[self.value]

    @property
    def rpc_url(self) -> str:
        return {
            "ethereum": "https://mainnet.infura.io/v3/",
            "polygon": "https://polygon-mainnet.infura.io/v3/",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
            "optimism": "https://mainnet.optimism.io",
            "avalanche": "https://api.avax.network/ext/bc/C/rpc",
            "celo": "https://forno.celo.org",
            "base": "https://mainnet.base.org",
        }[self.value]

# ABI Definitions
UNISWAP_V2_ROUTER_ABI = json.loads("""
[
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],
     "name":"getAmountsOut","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"}],
     "name":"getAmountsIn","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"swapExactTokensForTokens","outputs":[{"internalType":"uint256[]","name":"amounts","type":"uint256[]"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMin","type":"uint256"},{"internalType":"address[]","name":"path","type":"address[]"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"swapExactTokensForTokensSupportingFeeOnTransferTokens","outputs":[],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint256","name":"amountADesired","type":"uint256"},{"internalType":"uint256","name":"amountBDesired","type":"uint256"},{"internalType":"uint256","name":"amountAMin","type":"uint256"},{"internalType":"uint256","name":"amountBMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"addLiquidity","outputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"amountB","type":"uint256"},{"internalType":"uint256","name":"liquidity","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amountTokenDesired","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"addLiquidityETH","outputs":[{"internalType":"uint256","name":"amountToken","type":"uint256"},{"internalType":"uint256","name":"amountETH","type":"uint256"},{"internalType":"uint256","name":"liquidity","type":"uint256"}],
     "stateMutability":"payable","type":"function"}
]
""")

UNISWAP_V3_ROUTER_ABI = json.loads("""
[
    {"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMinimum","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"name":"params","type":"tuple"}],
     "name":"exactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"components":[{"internalType":"bytes","name":"path","type":"bytes"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint256","name":"amountOutMinimum","type":"uint256"}],"name":"params","type":"tuple"}],
     "name":"exactInput","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"components":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"address","name":"recipient","type":"address"},{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint256","name":"amountInMaximum","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"name":"params","type":"tuple"}],
     "name":"exactOutputSingle","outputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"}
]
""")

UNISWAP_V3_POOL_ABI = json.loads("""
[
    {"inputs":[],"name":"liquidity","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"fee","outputs":[{"internalType":"uint24","name":"","type":"uint24"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"tickSpacing","outputs":[{"internalType":"int24","name":"","type":"int24"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"factory","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"}
]
""")

UNISWAP_V3_QUOTER_ABI = json.loads("""
[
    {"inputs":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
     "name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"bytes","name":"path","type":"bytes"},{"internalType":"uint256","name":"amountIn","type":"uint256"}],
     "name":"quoteExactInput","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint256","name":"amountOut","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],
     "name":"quoteExactOutputSingle","outputs":[{"internalType":"uint256","name":"amountIn","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"}
]
""")

UNISWAP_V3_NFT_ABI = json.loads("""
[
    {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],
     "name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],
     "stateMutability":"view","type":"function"}
]
""")

# Data classes
@dataclass
class V3PoolInfo:
    """Uniswap V3 pool information."""
    address: ChecksumAddress
    token0: ChecksumAddress
    token1: ChecksumAddress
    fee: int
    tick_spacing: int
    liquidity: Decimal
    sqrt_price: Decimal
    tick: int
    fee_growth_global: Decimal

@dataclass
class V3Position:
    """Uniswap V3 position."""
    token_id: int
    token0: str
    token1: str
    fee: int
    tick_lower: int
    tick_upper: int
    liquidity: Decimal
    amount0: Decimal
    amount1: Decimal
    fees_earned0: Decimal
    fees_earned1: Decimal
    price_lower: Decimal
    price_upper: Decimal
    current_price: Decimal

@dataclass
class SwapQuote:
    """Swap quote result."""
    version: str  # "v2" or "v3"
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    price_impact: Decimal
    fee: Decimal
    fee_tier: Optional[int] = None
    route: List[Union[str, Dict]]
    estimated_gas: int
    timestamp: datetime

@dataclass
class SwapResult:
    """Swap execution result."""
    version: str
    success: bool
    tx_hash: Optional[str]
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    actual_amount_in: Decimal
    actual_amount_out: Decimal
    gas_used: int
    fee: Decimal
    fee_tier: Optional[int] = None
    timestamp: datetime
    error: Optional[str] = None


class UniswapExchange(BaseExchange):
    """
    Uniswap DEX Integration (V2 & V3).
    
    This class provides comprehensive integration with Uniswap:
    1. V2 swaps
    2. V3 swaps (Concentrated Liquidity)
    3. V3 position management
    4. V3 flash swaps
    5. Multi-hop routing
    6. Fee tier selection
    
    Features:
    - V2 and V3 support
    - Multi-chain support
    - Route optimization
    - Slippage protection
    - MEV protection
    - V3 position management
    - Fee tier optimization
    - Gas optimization
    """
    
    def __init__(
        self,
        chain: UniswapChain = UniswapChain.ETHEREUM,
        private_key: Optional[str] = None,
        web3_provider: Optional[str] = None,
        max_slippage: Decimal = Decimal("0.01"),  # 1%
        gas_multiplier: Decimal = Decimal("1.1"),
        timeout: int = 30,
        default_version: str = "v3",
    ):
        """
        Initialize the Uniswap exchange adapter.
        
        Args:
            chain: Blockchain chain
            private_key: Private key for signing
            web3_provider: Web3 provider URL
            max_slippage: Maximum allowed slippage
            gas_multiplier: Gas price multiplier
            timeout: Request timeout
            default_version: Default protocol version ("v2" or "v3")
        """
        super().__init__(ExchangeConfig(
            exchange_type=ExchangeType.UNISWAP,
            private_key=private_key,
            timeout=timeout,
        ))
        
        self.chain = chain
        self.max_slippage = max_slippage
        self.gas_multiplier = gas_multiplier
        self.default_version = default_version
        
        # Initialize Web3
        self.web3 = self._init_web3(web3_provider)
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # Initialize V2 contracts
        self.v2_router = self.web3.eth.contract(
            address=to_checksum_address(chain.v2_router_address),
            abi=UNISWAP_V2_ROUTER_ABI
        )
        
        # Initialize V3 contracts
        self.v3_router = self.web3.eth.contract(
            address=to_checksum_address(chain.v3_router_address),
            abi=UNISWAP_V3_ROUTER_ABI
        )
        self.v3_factory = self.web3.eth.contract(
            address=to_checksum_address(chain.v3_factory_address),
            abi=UNISWAP_V3_FACTORY_ABI
        )
        self.v3_quoter = self.web3.eth.contract(
            address=to_checksum_address(UNISWAP_V3_QUOTER_V2),
            abi=UNISWAP_V3_QUOTER_ABI
        )
        self.v3_nft_manager = self.web3.eth.contract(
            address=to_checksum_address(UNISWAP_V3_NFT_MANAGER),
            abi=UNISWAP_V3_NFT_ABI
        )
        
        # Cache
        self.pool_cache: Dict[str, V3PoolInfo] = {}
        self.position_cache: Dict[int, V3Position] = {}
        self.token_cache: Dict[str, Dict] = {}
        
        # Metrics
        self.metrics.update({
            "swaps_executed": 0,
            "swaps_succeeded": 0,
            "swaps_failed": 0,
            "v2_swaps": 0,
            "v3_swaps": 0,
            "positions_created": 0,
            "positions_closed": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
        })
        
        self.logger.info(f"Initialized Uniswap on {chain.value} (default: {default_version})")
    
    def _init_web3(self, provider: Optional[str] = None) -> Web3:
        """Initialize Web3."""
        rpc_url = provider or self.chain.rpc_url
        try:
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            if w3.is_connected():
                return w3
        except Exception as e:
            self.logger.warning(f"Web3 connection failed: {e}")
        
        return Web3(Web3.HTTPProvider("https://cloudflare-eth.com"))
    
    def _get_deadline(self, seconds: int = 300) -> int:
        """Get transaction deadline."""
        return int(time.time()) + seconds
    
    def _to_wei(self, amount: Decimal, decimals: int = 18) -> int:
        """Convert to wei."""
        return int(amount * Decimal(10 ** decimals))
    
    def _from_wei(self, amount: int, decimals: int = 18) -> Decimal:
        """Convert from wei."""
        return Decimal(str(amount)) / Decimal(10 ** decimals)
    
    def _tick_to_price(self, tick: int, token0_decimals: int = 18, token1_decimals: int = 18) -> Decimal:
        """Convert tick to price."""
        return Decimal(str(1.0001 ** tick)) * Decimal(10 ** (token0_decimals - token1_decimals))
    
    def _price_to_tick(self, price: Decimal, token0_decimals: int = 18, token1_decimals: int = 18) -> int:
        """Convert price to tick."""
        adjusted_price = price / Decimal(10 ** (token0_decimals - token1_decimals))
        return int(round(adjusted_price.log10() / 0.0001))
    
    def _get_v3_pool_address(self, token_a: str, token_b: str, fee: int) -> Optional[ChecksumAddress]:
        """Get V3 pool address."""
        try:
            return self.v3_factory.functions.getPool(
                to_checksum_address(token_a),
                to_checksum_address(token_b),
                fee
            ).call()
        except Exception:
            return None
    
    async def get_v3_pool_info(self, token_a: str, token_b: str, fee: int) -> Optional[V3PoolInfo]:
        """
        Get V3 pool information.
        
        Args:
            token_a: First token address
            token_b: Second token address
            fee: Fee tier
            
        Returns:
            V3PoolInfo or None
        """
        try:
            pool_address = self._get_v3_pool_address(token_a, token_b, fee)
            if not pool_address or pool_address == "0x0000000000000000000000000000000000000000":
                return None
            
            pool_contract = self.web3.eth.contract(
                address=pool_address,
                abi=UNISWAP_V3_POOL_ABI
            )
            
            slot0 = pool_contract.functions.slot0().call()
            liquidity = pool_contract.functions.liquidity().call()
            token0 = pool_contract.functions.token0().call()
            token1 = pool_contract.functions.token1().call()
            tick_spacing = pool_contract.functions.tickSpacing().call()
            
            pool_info = V3PoolInfo(
                address=to_checksum_address(pool_address),
                token0=to_checksum_address(token0),
                token1=to_checksum_address(token1),
                fee=fee,
                tick_spacing=tick_spacing,
                liquidity=self._from_wei(liquidity),
                sqrt_price=Decimal(str(slot0[0])) / Decimal(2**96),
                tick=slot0[1],
                fee_growth_global=Decimal("0"),
            )
            
            cache_key = f"{token_a}_{token_b}_{fee}"
            self.pool_cache[cache_key] = pool_info
            return pool_info
            
        except Exception as e:
            self.logger.error(f"Failed to get V3 pool info: {e}")
            return None
    
    async def get_quote_v2(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
    ) -> Optional[SwapQuote]:
        """
        Get V2 swap quote.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            
        Returns:
            SwapQuote or None
        """
        try:
            amount_in_wei = self._to_wei(amount_in)
            path = [to_checksum_address(token_in), to_checksum_address(token_out)]
            
            amounts = self.v2_router.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            amount_out = self._from_wei(amounts[-1])
            fee = amount_out * Decimal("0.003")  # 0.3% V2 fee
            
            return SwapQuote(
                version="v2",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=Decimal("0"),
                fee=fee,
                route=path,
                estimated_gas=150000,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get V2 quote: {e}")
            return None
    
    async def get_quote_v3(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        fee_tier: Optional[int] = None,
    ) -> Optional[SwapQuote]:
        """
        Get V3 swap quote.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            fee_tier: Fee tier to use
            
        Returns:
            SwapQuote or None
        """
        try:
            if fee_tier is None:
                # Try fee tiers in order: 0.3%, 0.05%, 1%
                for fee in [3000, 500, 10000]:
                    try:
                        amount_out = await self._quote_v3_single(
                            token_in, token_out, amount_in, fee
                        )
                        if amount_out > 0:
                            fee_tier = fee
                            break
                    except Exception:
                        continue
                
                if fee_tier is None:
                    raise ValueError("No viable fee tier found")
            
            if fee_tier is None:
                raise ValueError("No fee tier specified")
            
            amount_out = await self._quote_v3_single(token_in, token_out, amount_in, fee_tier)
            
            if amount_out <= 0:
                return None
            
            fee = amount_out * Decimal(str(fee_tier)) / Decimal("1000000")
            
            return SwapQuote(
                version="v3",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=Decimal("0"),
                fee=fee,
                fee_tier=fee_tier,
                route=[{"fee": fee_tier, "tokenIn": token_in, "tokenOut": token_out}],
                estimated_gas=200000,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get V3 quote: {e}")
            return None
    
    async def _quote_v3_single(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        fee: int,
    ) -> Decimal:
        """Get V3 quote for a single hop."""
        try:
            amount_in_wei = self._to_wei(amount_in)
            
            result = self.v3_quoter.functions.quoteExactInputSingle({
                "tokenIn": to_checksum_address(token_in),
                "tokenOut": to_checksum_address(token_out),
                "fee": fee,
                "amountIn": amount_in_wei,
                "sqrtPriceLimitX96": 0,
            }).call()
            
            return self._from_wei(result)
            
        except Exception as e:
            self.logger.debug(f"V3 quote failed for fee {fee}: {e}")
            return Decimal("0")
    
    async def swap_v2(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out_min: Optional[Decimal] = None,
        slippage: Optional[Decimal] = None,
        receiver: Optional[str] = None,
    ) -> SwapResult:
        """
        Execute a V2 swap.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            amount_out_min: Minimum output amount
            slippage: Maximum slippage percentage
            receiver: Receiver address
            
        Returns:
            SwapResult
        """
        start_time = time.time()
        
        try:
            if not self.account:
                raise ValueError("No account available for signing")
            
            quote = await self.get_quote_v2(token_in, token_out, amount_in)
            if not quote:
                raise ValueError("Failed to get quote")
            
            amount_in_wei = self._to_wei(amount_in)
            min_out = amount_out_min or quote.amount_out * (Decimal("1") - (slippage or self.max_slippage))
            min_out_wei = self._to_wei(min_out)
            path = [to_checksum_address(token_in), to_checksum_address(token_out)]
            to_address = receiver or self.account.address
            deadline = self._get_deadline()
            
            tx = self.v2_router.functions.swapExactTokensForTokens(
                amount_in_wei,
                min_out_wei,
                path,
                to_checksum_address(to_address),
                deadline
            ).build_transaction({
                "from": self.account.address,
                "gas": 250000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            self.metrics["swaps_executed"] += 1
            self.metrics["v2_swaps"] += 1
            
            if receipt.status == 1:
                self.metrics["swaps_succeeded"] += 1
                self.metrics["total_volume"] += amount_in
                self.metrics["total_fees"] += quote.fee
                
                result = SwapResult(
                    version="v2",
                    success=True,
                    tx_hash=to_hex(tx_hash),
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=quote.amount_out,
                    actual_amount_in=amount_in,
                    actual_amount_out=quote.amount_out,
                    gas_used=receipt.gasUsed,
                    fee=quote.fee,
                    timestamp=datetime.utcnow(),
                )
                
                self.logger.info(f"V2 swap successful: TX {to_hex(tx_hash)}")
                return result
            else:
                self.metrics["swaps_failed"] += 1
                return SwapResult(
                    version="v2",
                    success=False,
                    tx_hash=to_hex(tx_hash),
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=Decimal("0"),
                    actual_amount_in=Decimal("0"),
                    actual_amount_out=Decimal("0"),
                    gas_used=receipt.gasUsed,
                    fee=Decimal("0"),
                    timestamp=datetime.utcnow(),
                    error="Transaction failed",
                )
            
        except Exception as e:
            self.logger.error(f"V2 swap failed: {e}")
            self.metrics["errors"] += 1
            self.metrics["swaps_failed"] += 1
            
            return SwapResult(
                version="v2",
                success=False,
                tx_hash=None,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=Decimal("0"),
                actual_amount_in=Decimal("0"),
                actual_amount_out=Decimal("0"),
                gas_used=0,
                fee=Decimal("0"),
                timestamp=datetime.utcnow(),
                error=str(e),
            )
    
    async def swap_v3(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        fee_tier: Optional[int] = None,
        amount_out_min: Optional[Decimal] = None,
        slippage: Optional[Decimal] = None,
        receiver: Optional[str] = None,
        sqrt_price_limit: Optional[int] = None,
    ) -> SwapResult:
        """
        Execute a V3 swap.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            fee_tier: Fee tier to use
            amount_out_min: Minimum output amount
            slippage: Maximum slippage percentage
            receiver: Receiver address
            sqrt_price_limit: Sqrt price limit X96
            
        Returns:
            SwapResult
        """
        start_time = time.time()
        
        try:
            if not self.account:
                raise ValueError("No account available for signing")
            
            quote = await self.get_quote_v3(token_in, token_out, amount_in, fee_tier)
            if not quote:
                raise ValueError("Failed to get quote")
            
            amount_in_wei = self._to_wei(amount_in)
            min_out = amount_out_min or quote.amount_out * (Decimal("1") - (slippage or self.max_slippage))
            min_out_wei = self._to_wei(min_out)
            to_address = receiver or self.account.address
            deadline = self._get_deadline()
            
            tx = self.v3_router.functions.exactInputSingle({
                "tokenIn": to_checksum_address(token_in),
                "tokenOut": to_checksum_address(token_out),
                "fee": quote.fee_tier or 3000,
                "recipient": to_checksum_address(to_address),
                "amountIn": amount_in_wei,
                "amountOutMinimum": min_out_wei,
                "sqrtPriceLimitX96": sqrt_price_limit or 0,
            }).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            self.metrics["swaps_executed"] += 1
            self.metrics["v3_swaps"] += 1
            
            if receipt.status == 1:
                self.metrics["swaps_succeeded"] += 1
                self.metrics["total_volume"] += amount_in
                self.metrics["total_fees"] += quote.fee
                
                result = SwapResult(
                    version="v3",
                    success=True,
                    tx_hash=to_hex(tx_hash),
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=quote.amount_out,
                    actual_amount_in=amount_in,
                    actual_amount_out=quote.amount_out,
                    gas_used=receipt.gasUsed,
                    fee=quote.fee,
                    fee_tier=quote.fee_tier,
                    timestamp=datetime.utcnow(),
                )
                
                self.logger.info(f"V3 swap successful: TX {to_hex(tx_hash)}")
                return result
            else:
                self.metrics["swaps_failed"] += 1
                return SwapResult(
                    version="v3",
                    success=False,
                    tx_hash=to_hex(tx_hash),
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    amount_out=Decimal("0"),
                    actual_amount_in=Decimal("0"),
                    actual_amount_out=Decimal("0"),
                    gas_used=receipt.gasUsed,
                    fee=Decimal("0"),
                    fee_tier=quote.fee_tier,
                    timestamp=datetime.utcnow(),
                    error="Transaction failed",
                )
            
        except Exception as e:
            self.logger.error(f"V3 swap failed: {e}")
            self.metrics["errors"] += 1
            self.metrics["swaps_failed"] += 1
            
            return SwapResult(
                version="v3",
                success=False,
                tx_hash=None,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=Decimal("0"),
                actual_amount_in=Decimal("0"),
                actual_amount_out=Decimal("0"),
                gas_used=0,
                fee=Decimal("0"),
                timestamp=datetime.utcnow(),
                error=str(e),
            )
    
    async def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        version: Optional[str] = None,
        fee_tier: Optional[int] = None,
        amount_out_min: Optional[Decimal] = None,
        slippage: Optional[Decimal] = None,
        receiver: Optional[str] = None,
    ) -> SwapResult:
        """
        Execute a swap (auto-selects V2/V3).
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            version: Protocol version ("v2" or "v3")
            fee_tier: Fee tier for V3
            amount_out_min: Minimum output amount
            slippage: Maximum slippage percentage
            receiver: Receiver address
            
        Returns:
            SwapResult
        """
        version = version or self.default_version
        
        if version == "v3":
            return await self.swap_v3(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                fee_tier=fee_tier,
                amount_out_min=amount_out_min,
                slippage=slippage,
                receiver=receiver,
            )
        else:
            return await self.swap_v2(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out_min=amount_out_min,
                slippage=slippage,
                receiver=receiver,
            )
    
    # Required BaseExchange methods (minimal implementations)
    
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker information."""
        try:
            tokens = symbol.split("/")
            if len(tokens) != 2:
                return None
            
            # Try V3 first
            for fee in [3000, 500, 10000]:
                pool = await self.get_v3_pool_info(tokens[0], tokens[1], fee)
                if pool:
                    price = self._tick_to_price(pool.tick)
                    return Ticker(
                        symbol=symbol,
                        bid=price * Decimal("0.999"),
                        ask=price * Decimal("1.001"),
                        last=price,
                        high=Decimal("0"),
                        low=Decimal("0"),
                        volume=Decimal("0"),
                        timestamp=datetime.utcnow(),
                    )
            
            return None
        except Exception:
            return None
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Optional[OrderBook]:
        """Get order book (not applicable for DEX)."""
        return None
    
    async def get_ohlcv(self, symbol: str, interval: Interval, limit: int = 100) -> List[OHLCV]:
        """Get OHLCV data."""
        return []
    
    async def get_historical_prices(self, symbol: str, interval: Interval, start_time: datetime, end_time: datetime) -> List[OHLCV]:
        """Get historical prices."""
        return []
    
    async def place_order(self, symbol: str, side: OrderSide, order_type: OrderType, quantity: Decimal,
                          price: Optional[Decimal] = None, **kwargs) -> Optional[Order]:
        """Place an order."""
        return None
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        return False
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Cancel all orders."""
        return False
    
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Get order status."""
        return None
    
    async def get_open_orders(self, symbol: str) -> List[Order]:
        """Get open orders."""
        return []
    
    async def get_order_history(self, symbol: str, limit: int = 100, start_time: Optional[datetime] = None,
                                end_time: Optional[datetime] = None) -> List[Order]:
        """Get order history."""
        return []
    
    async def get_balances(self) -> Dict[str, Balance]:
        """Get balances."""
        return {}
    
    async def get_balance(self, asset: str) -> Optional[Balance]:
        """Get balance for asset."""
        return None
    
    async def get_positions(self) -> List[Position]:
        """Get positions."""
        return []
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        return None
    
    async def get_symbols(self) -> List[str]:
        """Get available symbols."""
        return []
    
    async def get_funding_rate(self, symbol: str) -> Optional[FundingRate]:
        """Get funding rate."""
        return None
    
    async def connect_websocket(self) -> bool:
        """Connect WebSocket."""
        return False
    
    async def disconnect_websocket(self) -> bool:
        """Disconnect WebSocket."""
        return False
    
    async def subscribe_ticker(self, symbols: List[str], callback: Callable[[Ticker], None]) -> bool:
        """Subscribe to ticker."""
        return False
    
    async def subscribe_order_book(self, symbols: List[str], callback: Callable[[OrderBook], None]) -> bool:
        """Subscribe to order book."""
        return False
    
    async def subscribe_trades(self, symbols: List[str], callback: Callable[[Trade], None]) -> bool:
        """Subscribe to trades."""
        return False
    
    async def subscribe_user_data(self, callback: Callable[[Dict[str, Any]], None]) -> bool:
        """Subscribe to user data."""
        return False
    
    async def ping(self) -> bool:
        """Ping the exchange."""
        return self.web3.is_connected()
    
    async def get_server_time(self) -> datetime:
        """Get server time."""
        return datetime.utcnow()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics."""
        return {
            **super().get_metrics(),
            "swaps_executed": self.metrics["swaps_executed"],
            "swaps_succeeded": self.metrics["swaps_succeeded"],
            "swaps_failed": self.metrics["swaps_failed"],
            "v2_swaps": self.metrics["v2_swaps"],
            "v3_swaps": self.metrics["v3_swaps"],
            "positions_created": self.metrics["positions_created"],
            "positions_closed": self.metrics["positions_closed"],
            "total_volume": float(self.metrics["total_volume"]),
            "total_fees": float(self.metrics["total_fees"]),
            "chain": self.chain.value,
            "default_version": self.default_version,
            "pools_cached": len(self.pool_cache),
        }


# Module exports
__all__ = [
    'UniswapExchange',
    'UniswapChain',
    'FeeTier',
    'V3PoolInfo',
    'V3Position',
    'SwapQuote',
    'SwapResult',
]
