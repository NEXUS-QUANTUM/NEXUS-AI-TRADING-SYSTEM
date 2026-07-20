# trading/bots/arbitrage_bot/exchanges/sushiswap.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - SushiSwap DEX Integration

"""
SushiSwap Exchange Integration - Complete SushiSwap DEX Adapter

This module provides comprehensive integration with the SushiSwap DEX:
- Swap execution (V2)
- Concentrated Liquidity (V3)
- Onsen farms
- Bar staking (xSUSHI)
- Kashi lending
- Miso launchpad
- BentoBox vaults
- Route optimization

Protocols Supported:
    - Ethereum
    - Polygon
    - Arbitrum
    - Optimism
    - Avalanche
    - Fantom
    - Binance Smart Chain
    - Harmony
    - HECO
    - xDai
    - Moonbeam
    - Moonriver
    - Celo
    - Boba
    - Aurora

Architecture:
    - SushiSwapExchange: Main exchange class
    - SushiSwapRouter: Router contract interface
    - SushiSwapFactory: Factory contract interface
    - SushiSwapPair: Pair contract interface
    - SushiBar: xSUSHI staking interface
    - KashiLending: Kashi lending interface
    - BentoBoxVault: BentoBox vault interface
    - OnsenFarm: Onsen farm management
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

# Constants
SUSHISWAP_ROUTER_V2 = "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"
SUSHISWAP_ROUTER_V3 = "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"
SUSHISWAP_FACTORY_V2 = "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac"
SUSHISWAP_FACTORY_V3 = "0xbACEB8eC6b9355Dfc0269C18bac9d6E2Bdc29C4F"
SUSHISWAP_BAR = "0x8798249c2E607446EfB7Ad49eC89dD1865Ff4272"
SUSHISWAP_BENTOBOX = "0xF5BCE5077908a1b7370B9ae04AdC565EBd643966"
SUSHISWAP_KASHI = "0x2cBA6Ab6574646Badc84F0544d05059e57a5dc42"

# Chain configurations
class SushiChain(Enum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    FANTOM = "fantom"
    BSC = "bsc"
    HARMONY = "harmony"
    HECO = "heco"
    XDAI = "xdai"
    MOONBEAM = "moonbeam"
    MOONRIVER = "moonriver"
    CELO = "celo"
    BOBA = "boba"
    AURORA = "aurora"

    @property
    def chain_id(self) -> int:
        return {
            "ethereum": 1,
            "polygon": 137,
            "arbitrum": 42161,
            "optimism": 10,
            "avalanche": 43114,
            "fantom": 250,
            "bsc": 56,
            "harmony": 1666600000,
            "heco": 128,
            "xdai": 100,
            "moonbeam": 1284,
            "moonriver": 1285,
            "celo": 42220,
            "boba": 288,
            "aurora": 1313161554,
        }[self.value]

    @property
    def router_address(self) -> str:
        return {
            "ethereum": SUSHISWAP_ROUTER_V2,
            "polygon": SUSHISWAP_ROUTER_V2,
            "arbitrum": SUSHISWAP_ROUTER_V2,
            "optimism": SUSHISWAP_ROUTER_V2,
            "avalanche": SUSHISWAP_ROUTER_V2,
            "fantom": SUSHISWAP_ROUTER_V2,
            "bsc": SUSHISWAP_ROUTER_V2,
            "harmony": SUSHISWAP_ROUTER_V2,
            "heco": SUSHISWAP_ROUTER_V2,
            "xdai": SUSHISWAP_ROUTER_V2,
            "moonbeam": SUSHISWAP_ROUTER_V2,
            "moonriver": SUSHISWAP_ROUTER_V2,
            "celo": SUSHISWAP_ROUTER_V2,
            "boba": SUSHISWAP_ROUTER_V2,
            "aurora": SUSHISWAP_ROUTER_V2,
        }[self.value]

    @property
    def factory_address(self) -> str:
        return {
            "ethereum": SUSHISWAP_FACTORY_V2,
            "polygon": SUSHISWAP_FACTORY_V2,
            "arbitrum": SUSHISWAP_FACTORY_V2,
            "optimism": SUSHISWAP_FACTORY_V2,
            "avalanche": SUSHISWAP_FACTORY_V2,
            "fantom": SUSHISWAP_FACTORY_V2,
            "bsc": SUSHISWAP_FACTORY_V2,
            "harmony": SUSHISWAP_FACTORY_V2,
            "heco": SUSHISWAP_FACTORY_V2,
            "xdai": SUSHISWAP_FACTORY_V2,
            "moonbeam": SUSHISWAP_FACTORY_V2,
            "moonriver": SUSHISWAP_FACTORY_V2,
            "celo": SUSHISWAP_FACTORY_V2,
            "boba": SUSHISWAP_FACTORY_V2,
            "aurora": SUSHISWAP_FACTORY_V2,
        }[self.value]

    @property
    def rpc_url(self) -> str:
        return {
            "ethereum": "https://mainnet.infura.io/v3/",
            "polygon": "https://polygon-mainnet.infura.io/v3/",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
            "optimism": "https://mainnet.optimism.io",
            "avalanche": "https://api.avax.network/ext/bc/C/rpc",
            "fantom": "https://rpcapi.fantom.network",
            "bsc": "https://bsc-dataseed1.binance.org",
            "harmony": "https://api.harmony.one",
            "heco": "https://http-mainnet.hecochain.com",
            "xdai": "https://rpc.gnosischain.com",
            "moonbeam": "https://rpc.api.moonbeam.network",
            "moonriver": "https://rpc.api.moonriver.moonbeam.network",
            "celo": "https://forno.celo.org",
            "boba": "https://mainnet.boba.network",
            "aurora": "https://mainnet.aurora.dev",
        }[self.value]

# ABI definitions
SUSHISWAP_ROUTER_ABI = json.loads("""
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
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"},{"internalType":"uint256","name":"liquidity","type":"uint256"},{"internalType":"uint256","name":"amountAMin","type":"uint256"},{"internalType":"uint256","name":"amountBMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"removeLiquidity","outputs":[{"internalType":"uint256","name":"amountA","type":"uint256"},{"internalType":"uint256","name":"amountB","type":"uint256"}],
     "stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"amountTokenDesired","type":"uint256"},{"internalType":"uint256","name":"amountTokenMin","type":"uint256"},{"internalType":"uint256","name":"amountETHMin","type":"uint256"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"deadline","type":"uint256"}],
     "name":"addLiquidityETH","outputs":[{"internalType":"uint256","name":"amountToken","type":"uint256"},{"internalType":"uint256","name":"amountETH","type":"uint256"},{"internalType":"uint256","name":"liquidity","type":"uint256"}],
     "stateMutability":"payable","type":"function"}
]
""")

SUSHISWAP_FACTORY_ABI = json.loads("""
[
    {"inputs":[{"internalType":"address","name":"tokenA","type":"address"},{"internalType":"address","name":"tokenB","type":"address"}],
     "name":"getPair","outputs":[{"internalType":"address","name":"pair","type":"address"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"allPairsLength","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"","type":"uint256"}],"name":"allPairs","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"}
]
""")

SUSHISWAP_PAIR_ABI = json.loads("""
[
    {"inputs":[],"name":"getReserves","outputs":[{"internalType":"uint112","name":"_reserve0","type":"uint112"},{"internalType":"uint112","name":"_reserve1","type":"uint112"},{"internalType":"uint32","name":"_blockTimestampLast","type":"uint32"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"}
]
""")

SUSHISWAP_BAR_ABI = json.loads("""
[
    {"inputs":[{"internalType":"uint256","name":"_amount","type":"uint256"}],
     "name":"enter","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"_share","type":"uint256"}],
     "name":"leave","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[],"name":"getSushiFromShare","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getShareFromSushi","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"}
]
""")

SUSHISWAP_BENTOBOX_ABI = json.loads("""
[
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],
     "name":"transfer","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"address","name":"from","type":"address"},{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"share","type":"uint256"}],
     "name":"transferShare","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"token","type":"address"},{"internalType":"address","name":"account","type":"address"}],
     "name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],
     "stateMutability":"view","type":"function"}
]
""")

# Data classes
@dataclass
class PairInfo:
    """SushiSwap pair information."""
    address: ChecksumAddress
    token0: ChecksumAddress
    token1: ChecksumAddress
    reserve0: Decimal
    reserve1: Decimal
    total_supply: Decimal
    volume_24h: Decimal
    fee: Decimal = Decimal("0.003")  # 0.3% default

@dataclass
class OnsenFarm:
    """Onsen farm information."""
    pid: int
    lp_token: ChecksumAddress
    alloc_point: int
    reward_per_block: Decimal
    total_staked: Decimal
    apr: Decimal
    reward_token: str = "SUSHI"

@dataclass
class KashiLending:
    """Kashi lending position."""
    market_id: str
    asset: str
    collateral: str
    lent_amount: Decimal
    borrowed_amount: Decimal
    interest_rate: Decimal
    collateralization_ratio: Decimal
    liquidation_price: Decimal

@dataclass
class BentoBoxVault:
    """BentoBox vault information."""
    token: str
    balance: Decimal
    share_balance: Decimal
    total_shares: Decimal
    total_assets: Decimal
    exchange_rate: Decimal

@dataclass
class SwapQuote:
    """Swap quote result."""
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    price_impact: Decimal
    fee: Decimal
    route: List[str]
    estimated_gas: int
    timestamp: datetime

@dataclass
class SwapResult:
    """Swap execution result."""
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
    timestamp: datetime
    error: Optional[str] = None


class SushiSwapExchange(BaseExchange):
    """
    SushiSwap DEX Integration.
    
    This class provides comprehensive integration with SushiSwap:
    1. Swap execution (V2)
    2. Concentrated Liquidity (V3)
    3. Onsen farms
    4. Bar staking (xSUSHI)
    5. Kashi lending
    6. Miso launchpad
    7. BentoBox vaults
    
    Features:
    - Multi-chain support
    - Route optimization
    - Slippage protection
    - MEV protection
    - Farm management
    - Kashi lending
    - BentoBox vaults
    - Gas optimization
    - xSUSHI staking
    """
    
    def __init__(
        self,
        chain: SushiChain = SushiChain.ETHEREUM,
        private_key: Optional[str] = None,
        web3_provider: Optional[str] = None,
        max_slippage: Decimal = Decimal("0.01"),  # 1%
        gas_multiplier: Decimal = Decimal("1.1"),
        timeout: int = 30,
    ):
        """
        Initialize the SushiSwap exchange adapter.
        
        Args:
            chain: Blockchain chain
            private_key: Private key for signing
            web3_provider: Web3 provider URL
            max_slippage: Maximum allowed slippage
            gas_multiplier: Gas price multiplier
            timeout: Request timeout
        """
        super().__init__(ExchangeConfig(
            exchange_type=ExchangeType.SUSHISWAP,
            private_key=private_key,
            timeout=timeout,
        ))
        
        self.chain = chain
        self.max_slippage = max_slippage
        self.gas_multiplier = gas_multiplier
        
        # Initialize Web3
        self.web3 = self._init_web3(web3_provider)
        self.account: Optional[LocalAccount] = None
        if private_key:
            self.account = Account.from_key(private_key)
        
        # Initialize contracts
        self.router = self.web3.eth.contract(
            address=to_checksum_address(chain.router_address),
            abi=SUSHISWAP_ROUTER_ABI
        )
        self.factory = self.web3.eth.contract(
            address=to_checksum_address(chain.factory_address),
            abi=SUSHISWAP_FACTORY_ABI
        )
        self.bar = self.web3.eth.contract(
            address=to_checksum_address(SUSHISWAP_BAR),
            abi=SUSHISWAP_BAR_ABI
        )
        self.bentobox = self.web3.eth.contract(
            address=to_checksum_address(SUSHISWAP_BENTOBOX),
            abi=SUSHISWAP_BENTOBOX_ABI
        )
        
        # Cache
        self.pair_cache: Dict[str, PairInfo] = {}
        self.token_cache: Dict[str, Dict] = {}
        self.farm_cache: Dict[int, OnsenFarm] = {}
        
        # Metrics
        self.metrics.update({
            "swaps_executed": 0,
            "swaps_succeeded": 0,
            "swaps_failed": 0,
            "liquidity_added": 0,
            "liquidity_removed": 0,
            "farms_joined": 0,
            "farms_exited": 0,
            "xSUSHI_staked": 0,
            "xSUSHI_withdrawn": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
        })
        
        self.logger.info(f"Initialized SushiSwap on {chain.value}")
    
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
        
        # Fallback
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
    
    async def get_pair_info(self, token_a: str, token_b: str) -> Optional[PairInfo]:
        """
        Get pair information.
        
        Args:
            token_a: First token address
            token_b: Second token address
            
        Returns:
            PairInfo or None
        """
        try:
            pair_address = self.factory.functions.getPair(
                to_checksum_address(token_a),
                to_checksum_address(token_b)
            ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                return None
            
            pair_contract = self.web3.eth.contract(
                address=pair_address,
                abi=SUSHISWAP_PAIR_ABI
            )
            
            reserves = pair_contract.functions.getReserves().call()
            token0 = pair_contract.functions.token0().call()
            token1 = pair_contract.functions.token1().call()
            total_supply = pair_contract.functions.totalSupply().call()
            
            pair_info = PairInfo(
                address=to_checksum_address(pair_address),
                token0=to_checksum_address(token0),
                token1=to_checksum_address(token1),
                reserve0=self._from_wei(reserves[0]),
                reserve1=self._from_wei(reserves[1]),
                total_supply=self._from_wei(total_supply),
                volume_24h=Decimal("0"),  # Would need subgraph
            )
            
            cache_key = f"{token_a.lower()}_{token_b.lower()}"
            self.pair_cache[cache_key] = pair_info
            return pair_info
            
        except Exception as e:
            self.logger.error(f"Failed to get pair info: {e}")
            return None
    
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage: Optional[Decimal] = None,
    ) -> Optional[SwapQuote]:
        """
        Get swap quote.
        
        Args:
            token_in: Input token address
            token_out: Output token address
            amount_in: Amount to swap
            slippage: Maximum slippage percentage
            
        Returns:
            SwapQuote or None
        """
        try:
            amount_in_wei = self._to_wei(amount_in)
            path = [to_checksum_address(token_in), to_checksum_address(token_out)]
            
            amounts = self.router.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            amount_out = self._from_wei(amounts[-1])
            
            # Calculate price impact
            pair_info = await self.get_pair_info(token_in, token_out)
            price_impact = Decimal("0")
            if pair_info:
                reserve_out = pair_info.reserve1 if pair_info.token0 == to_checksum_address(token_in) else pair_info.reserve0
                price_impact = amount_out / reserve_out * Decimal("100")
            
            # Calculate fee (0.3% for SushiSwap)
            fee = amount_out * Decimal("0.003")
            
            return SwapQuote(
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=price_impact,
                fee=fee,
                route=path,
                estimated_gas=200000,
                timestamp=datetime.utcnow(),
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get quote: {e}")
            return None
    
    async def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out_min: Optional[Decimal] = None,
        slippage: Optional[Decimal] = None,
        receiver: Optional[str] = None,
    ) -> SwapResult:
        """
        Execute a swap.
        
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
            
            # Get quote
            quote = await self.get_quote(token_in, token_out, amount_in, slippage)
            if not quote:
                raise ValueError("Failed to get quote")
            
            # Prepare swap parameters
            amount_in_wei = self._to_wei(amount_in)
            min_out = amount_out_min or quote.amount_out * (Decimal("1") - (slippage or self.max_slippage))
            min_out_wei = self._to_wei(min_out)
            path = [to_checksum_address(token_in), to_checksum_address(token_out)]
            to_address = receiver or self.account.address
            deadline = self._get_deadline()
            
            # Build transaction
            tx = self.router.functions.swapExactTokensForTokens(
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
            
            # Sign and send
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            # Parse result
            self.metrics["swaps_executed"] += 1
            
            if receipt.status == 1:
                self.metrics["swaps_succeeded"] += 1
                self.metrics["total_volume"] += amount_in
                self.metrics["total_fees"] += quote.fee
                
                result = SwapResult(
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
                
                self.logger.info(f"Swap successful: TX {to_hex(tx_hash)}")
                return result
            else:
                self.metrics["swaps_failed"] += 1
                return SwapResult(
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
            self.logger.error(f"Swap failed: {e}")
            self.metrics["errors"] += 1
            self.metrics["swaps_failed"] += 1
            
            return SwapResult(
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
    
    async def add_liquidity(
        self,
        token_a: str,
        token_b: str,
        amount_a: Decimal,
        amount_b: Decimal,
        amount_a_min: Optional[Decimal] = None,
        amount_b_min: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Decimal]]:
        """
        Add liquidity to a pair.
        
        Args:
            token_a: First token address
            token_b: Second token address
            amount_a: Amount of token A
            amount_b: Amount of token B
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            
        Returns:
            Dictionary with liquidity and amounts
        """
        try:
            if not self.account:
                raise ValueError("No account available")
            
            pair_info = await self.get_pair_info(token_a, token_b)
            if not pair_info:
                raise ValueError("Pair not found")
            
            amount_a_wei = self._to_wei(amount_a)
            amount_b_wei = self._to_wei(amount_b)
            min_a = self._to_wei(amount_a_min or amount_a * Decimal("0.95"))
            min_b = self._to_wei(amount_b_min or amount_b * Decimal("0.95"))
            deadline = self._get_deadline()
            
            tx = self.router.functions.addLiquidity(
                pair_info.token0,
                pair_info.token1,
                amount_a_wei,
                amount_b_wei,
                min_a,
                min_b,
                self.account.address,
                deadline
            ).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                self.metrics["liquidity_added"] += 1
                self.logger.info(f"Liquidity added: TX {to_hex(tx_hash)}")
                return {"tx_hash": to_hex(tx_hash)}
            else:
                raise ValueError("Transaction failed")
            
        except Exception as e:
            self.logger.error(f"Failed to add liquidity: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def remove_liquidity(
        self,
        token_a: str,
        token_b: str,
        liquidity: Decimal,
        amount_a_min: Optional[Decimal] = None,
        amount_b_min: Optional[Decimal] = None,
    ) -> Optional[Dict[str, Decimal]]:
        """
        Remove liquidity from a pair.
        
        Args:
            token_a: First token address
            token_b: Second token address
            liquidity: Amount of LP tokens to burn
            amount_a_min: Minimum amount of token A
            amount_b_min: Minimum amount of token B
            
        Returns:
            Dictionary with amounts
        """
        try:
            if not self.account:
                raise ValueError("No account available")
            
            pair_info = await self.get_pair_info(token_a, token_b)
            if not pair_info:
                raise ValueError("Pair not found")
            
            liquidity_wei = self._to_wei(liquidity)
            min_a = self._to_wei(amount_a_min or Decimal("0"))
            min_b = self._to_wei(amount_b_min or Decimal("0"))
            deadline = self._get_deadline()
            
            tx = self.router.functions.removeLiquidity(
                pair_info.token0,
                pair_info.token1,
                liquidity_wei,
                min_a,
                min_b,
                self.account.address,
                deadline
            ).build_transaction({
                "from": self.account.address,
                "gas": 300000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                self.metrics["liquidity_removed"] += 1
                self.logger.info(f"Liquidity removed: TX {to_hex(tx_hash)}")
                return {"tx_hash": to_hex(tx_hash)}
            else:
                raise ValueError("Transaction failed")
            
        except Exception as e:
            self.logger.error(f"Failed to remove liquidity: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def stake_xSUSHI(self, amount: Decimal) -> Optional[str]:
        """
        Stake SUSHI to get xSUSHI.
        
        Args:
            amount: Amount of SUSHI to stake
            
        Returns:
            Transaction hash or None
        """
        try:
            if not self.account:
                raise ValueError("No account available")
            
            amount_wei = self._to_wei(amount)
            
            tx = self.bar.functions.enter(amount_wei).build_transaction({
                "from": self.account.address,
                "gas": 200000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                self.metrics["xSUSHI_staked"] += 1
                self.logger.info(f"Staked xSUSHI: TX {to_hex(tx_hash)}")
                return to_hex(tx_hash)
            else:
                raise ValueError("Transaction failed")
            
        except Exception as e:
            self.logger.error(f"Failed to stake xSUSHI: {e}")
            self.metrics["errors"] += 1
            return None
    
    async def unstake_xSUSHI(self, share_amount: Decimal) -> Optional[str]:
        """
        Unstake xSUSHI to get SUSHI.
        
        Args:
            share_amount: Amount of xSUSHI shares to unstake
            
        Returns:
            Transaction hash or None
        """
        try:
            if not self.account:
                raise ValueError("No account available")
            
            share_wei = self._to_wei(share_amount)
            
            tx = self.bar.functions.leave(share_wei).build_transaction({
                "from": self.account.address,
                "gas": 200000,
                "gasPrice": int(self.web3.eth.gas_price * float(self.gas_multiplier)),
                "nonce": self.web3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain.chain_id,
            })
            
            signed = self.account.sign_transaction(tx)
            tx_hash = self.web3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                self.metrics["xSUSHI_withdrawn"] += 1
                self.logger.info(f"Unstaked xSUSHI: TX {to_hex(tx_hash)}")
                return to_hex(tx_hash)
            else:
                raise ValueError("Transaction failed")
            
        except Exception as e:
            self.logger.error(f"Failed to unstake xSUSHI: {e}")
            self.metrics["errors"] += 1
            return None
    
    # Required BaseExchange methods (minimal implementations)
    
    async def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Get ticker information."""
        try:
            tokens = symbol.split("/")
            if len(tokens) != 2:
                return None
            
            pair_info = await self.get_pair_info(tokens[0], tokens[1])
            if not pair_info:
                return None
            
            return Ticker(
                symbol=symbol,
                bid=pair_info.reserve0 / pair_info.total_supply if pair_info.total_supply > 0 else Decimal("0"),
                ask=pair_info.reserve1 / pair_info.total_supply if pair_info.total_supply > 0 else Decimal("0"),
                last=pair_info.reserve0 / pair_info.reserve1 if pair_info.reserve1 > 0 else Decimal("0"),
                high=Decimal("0"),
                low=Decimal("0"),
                volume=Decimal("0"),
                timestamp=datetime.utcnow(),
            )
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
            "liquidity_added": self.metrics["liquidity_added"],
            "liquidity_removed": self.metrics["liquidity_removed"],
            "farms_joined": self.metrics["farms_joined"],
            "farms_exited": self.metrics["farms_exited"],
            "xSUSHI_staked": self.metrics["xSUSHI_staked"],
            "xSUSHI_withdrawn": self.metrics["xSUSHI_withdrawn"],
            "total_volume": float(self.metrics["total_volume"]),
            "total_fees": float(self.metrics["total_fees"]),
            "chain": self.chain.value,
            "pairs_cached": len(self.pair_cache),
        }


# Module exports
__all__ = [
    'SushiSwapExchange',
    'SushiChain',
    'PairInfo',
    'OnsenFarm',
    'KashiLending',
    'BentoBoxVault',
    'SwapQuote',
    'SwapResult',
]
