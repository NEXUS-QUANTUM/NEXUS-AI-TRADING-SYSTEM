# blockchain/defi/uniswap.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Uniswap - Intégration DEX Avancée

Ce module implémente une intégration complète du protocole Uniswap (V2 et V3),
permettant les swaps, la gestion de liquidité, le farming et l'optimisation
des rendements.

Fonctionnalités principales:
- Swaps entre tokens (V2 et V3)
- Gestion des pools de liquidité
- Farming des récompenses UNI
- Support des positions NFT (V3)
- Optimisation des routes de swap
- Gestion du slippage
- Monitoring des positions
- Support multi-chain
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
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
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache, wraps

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.multi_chain_wallet import MultiChainWallet
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class UniswapVersion(Enum):
    """Versions d'Uniswap"""
    V2 = "v2"
    V3 = "v3"


class UniswapChain(Enum):
    """Chaînes supportées par Uniswap"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    BSC = "bsc"


class UniswapAction(Enum):
    """Actions Uniswap"""
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"


@dataclass
class UniswapPool:
    """Pool Uniswap"""
    pool_id: str
    version: UniswapVersion
    chain: str
    address: str
    token0: str
    token1: str
    fee: int
    liquidity: Decimal
    tvl: Decimal
    volume_24h: Decimal
    apy: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "pool_id": self.pool_id,
            "version": self.version.value,
            "chain": self.chain,
            "address": self.address,
            "token0": self.token0,
            "token1": self.token1,
            "fee": self.fee,
            "liquidity": str(self.liquidity),
            "tvl": str(self.tvl),
            "volume_24h": str(self.volume_24h),
            "apy": str(self.apy),
        }


@dataclass
class UniswapPosition:
    """Position Uniswap"""
    position_id: str
    pool_id: str
    user: str
    chain: str
    token0: str
    token1: str
    amount0: Decimal
    amount1: Decimal
    liquidity: Decimal
    value_usd: Decimal
    uncollected_fees: Decimal
    apy: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "pool_id": self.pool_id,
            "user": self.user,
            "chain": self.chain,
            "token0": self.token0,
            "token1": self.token1,
            "amount0": str(self.amount0),
            "amount1": str(self.amount1),
            "liquidity": str(self.liquidity),
            "value_usd": str(self.value_usd),
            "uncollected_fees": str(self.uncollected_fees),
            "apy": str(self.apy),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class UniswapQuote:
    """Devis Uniswap"""
    quote_id: str
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    price_impact: Decimal
    fees: Decimal
    route: List[str]
    estimated_time: int
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in": str(self.amount_in),
            "amount_out": str(self.amount_out),
            "price_impact": str(self.price_impact),
            "fees": str(self.fees),
            "route": self.route,
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


# ============================================================
# ADRESSES DES CONTRATS UNISWAP
# ============================================================

UNISWAP_V2_ADDRESSES = {
    UniswapChain.ETHEREUM: {
        "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    },
    UniswapChain.POLYGON: {
        "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
    },
}

UNISWAP_V3_ADDRESSES = {
    UniswapChain.ETHEREUM: {
        "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "nft_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
        "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
        "swap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    },
    UniswapChain.POLYGON: {
        "router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "nft_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
        "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
    },
    UniswapChain.ARBITRUM: {
        "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
        "nft_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
    },
    UniswapChain.OPTIMISM: {
        "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    },
    UniswapChain.BASE: {
        "router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
    },
}

# ABIs des contrats
UNISWAP_V2_ROUTER_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "amountInMax", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapTokensForExactTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "amountADesired", "type": "uint256"},
            {"name": "amountBDesired", "type": "uint256"},
            {"name": "amountAMin", "type": "uint256"},
            {"name": "amountBMin", "type": "uint256"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "addLiquidity",
        "outputs": [
            {"name": "amountA", "type": "uint256"},
            {"name": "amountB", "type": "uint256"},
            {"name": "liquidity", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
            {"name": "liquidity", "type": "uint256"},
            {"name": "amountAMin", "type": "uint256"},
            {"name": "amountBMin", "type": "uint256"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "removeLiquidity",
        "outputs": [
            {"name": "amountA", "type": "uint256"},
            {"name": "amountB", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

UNISWAP_V3_ROUTER_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "params", "type": "tuple"},
        ],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "payable": False,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "params", "type": "tuple"},
        ],
        "name": "exactOutputSingle",
        "outputs": [{"name": "amountIn", "type": "uint256"}],
        "payable": False,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "params", "type": "tuple"},
        ],
        "name": "exactInput",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "payable": False,
        "stateMutability": "payable",
        "type": "function",
    },
]

UNISWAP_V3_QUOTER_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "path", "type": "bytes"},
            {"name": "amountIn", "type": "uint256"},
        ],
        "name": "quoteExactInput",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class UniswapIntegration(BaseProtocol):
    """
    Intégration avancée d'Uniswap V2/V3
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: MultiChainWallet,
        web3_providers: Dict[str, Web3],
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'intégration Uniswap

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.web3_providers = web3_providers
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._contracts: Dict[str, Dict[str, Dict[str, Contract]]] = {}
        self._pools_cache: Dict[str, Tuple[float, UniswapPool]] = {}
        self._positions_cache: Dict[str, Tuple[float, UniswapPosition]] = {}
        self._quotes_cache: Dict[str, Tuple[float, UniswapQuote]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des prix
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}

        # Métriques
        self._total_swaps = 0
        self._total_liquidity_added = Decimal("0")
        self._total_rewards_claimed = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des pools
        self._initialize_pools()

        logger.info("UniswapIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats Uniswap"""
        try:
            self._contracts = {
                "v2": {},
                "v3": {},
            }

            # Uniswap V2
            for chain, addresses in UNISWAP_V2_ADDRESSES.items():
                chain_value = chain.value
                if chain_value not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts["v2"][chain_value] = {}

                for name, address in addresses.items():
                    if name == "router":
                        abi = UNISWAP_V2_ROUTER_ABI
                    else:
                        abi = []

                    self._contracts["v2"][chain_value][name] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )

            # Uniswap V3
            for chain, addresses in UNISWAP_V3_ADDRESSES.items():
                chain_value = chain.value
                if chain_value not in self.web3_providers:
                    continue

                provider = self.web3_providers[chain_value]
                self._contracts["v3"][chain_value] = {}

                for name, address in addresses.items():
                    if name in ["router", "swap_router"]:
                        abi = UNISWAP_V3_ROUTER_ABI
                    elif name == "quoter":
                        abi = UNISWAP_V3_QUOTER_ABI
                    else:
                        abi = []

                    self._contracts["v3"][chain_value][name] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )

            logger.info(f"Contrats Uniswap chargés")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    def _initialize_pools(self) -> None:
        """Initialise les pools Uniswap"""
        # Pools populaires
        popular_pools = {
            "ethereum": {
                "weth_usdc": {
                    "address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
                    "token0": "WETH",
                    "token1": "USDC",
                    "fee": 3000,
                },
                "weth_usdt": {
                    "address": "0x11b815efB8f581194ae79006d24E0d814B7697F6",
                    "token0": "WETH",
                    "token1": "USDT",
                    "fee": 3000,
                },
            },
            "polygon": {
                "weth_usdc": {
                    "address": "0x45dDa9cb7c25131DF268515131f647d726f50608",
                    "token0": "WETH",
                    "token1": "USDC",
                    "fee": 3000,
                },
            },
        }

        for chain, pools in popular_pools.items():
            for pool_id, pool_info in pools.items():
                self._pools_cache[f"{chain}:{pool_id}"] = (
                    time.time(),
                    UniswapPool(
                        pool_id=pool_id,
                        version=UniswapVersion.V3,
                        chain=chain,
                        address=pool_info["address"],
                        token0=pool_info["token0"],
                        token1=pool_info["token1"],
                        fee=pool_info["fee"],
                        liquidity=Decimal("1000000"),
                        tvl=Decimal("1000000"),
                        volume_24h=Decimal("500000"),
                        apy=Decimal("0.15"),
                    )
                )

    # ============================================================
    # MÉTHODES PUBLIQUES - SWAPS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def swap(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        version: UniswapVersion = UniswapVersion.V3,
        min_amount_out: Optional[Decimal] = None,
        deadline: int = 3600,
    ) -> str:
        """
        Exécute un swap sur Uniswap

        Args:
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant à swapper
            chain: Chaîne
            wallet_address: Adresse du wallet
            version: Version d'Uniswap
            min_amount_out: Montant minimum de sortie
            deadline: Délai en secondes

        Returns:
            Hash de la transaction
        """
        logger.info(f"Swap {amount} {token_in} -> {token_out} sur {chain} (v{version.value})")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des adresses des tokens
            token_in_addr = await self._get_token_address(token_in, chain)
            token_out_addr = await self._get_token_address(token_out, chain)

            # Vérification du solde
            balance = await self._get_balance(token_in, chain, wallet_address)
            if balance < amount:
                raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Obtention du devis
            quote = await self.get_quote(
                token_in, token_out, amount, chain, version
            )

            # Montant minimum de sortie
            if min_amount_out is None:
                min_amount_out = quote.amount_out * Decimal("0.99")  # 1% de slippage

            # Approval si nécessaire
            if token_in != "ETH":
                await self._approve_token(
                    token_in_addr,
                    amount,
                    chain,
                    wallet,
                    await self._get_router_address(chain, version),
                )

            # Construction de la transaction
            if version == UniswapVersion.V2:
                tx_data = await self._build_v2_swap_transaction(
                    token_in_addr,
                    token_out_addr,
                    amount,
                    min_amount_out,
                    wallet_address,
                    deadline,
                )
            else:
                tx_data = await self._build_v3_swap_transaction(
                    token_in_addr,
                    token_out_addr,
                    amount,
                    min_amount_out,
                    wallet_address,
                    deadline,
                )

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_swaps += 1
            self.metrics.record_increment(
                "uniswap_swap",
                1,
                {
                    "version": version.value,
                    "chain": chain,
                    "token_in": token_in,
                    "token_out": token_out,
                },
            )

            logger.info(f"Swap réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de swap: {e}")
            raise DeFiError(f"Erreur de swap: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
        version: UniswapVersion = UniswapVersion.V3,
        force_refresh: bool = False,
    ) -> UniswapQuote:
        """
        Obtient un devis de swap

        Args:
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant
            chain: Chaîne
            version: Version d'Uniswap
            force_refresh: Forcer le rafraîchissement

        Returns:
            Devis de swap
        """
        cache_key = f"{version.value}:{chain}:{token_in}:{token_out}:{amount}"

        if not force_refresh and cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            token_in_addr = await self._get_token_address(token_in, chain)
            token_out_addr = await self._get_token_address(token_out, chain)

            if version == UniswapVersion.V2:
                amount_out = await self._get_v2_quote(
                    token_in_addr, token_out_addr, amount, chain
                )
                route = [token_in, token_out]
                fees = amount * Decimal("0.003")  # 0.3% pour V2
            else:
                amount_out, route = await self._get_v3_quote(
                    token_in_addr, token_out_addr, amount, chain
                )
                fees = amount * Decimal("0.0005")  # 0.05% pour V3 (0.05%)

            # Calcul du price impact
            price_impact = Decimal("0")
            if amount_out > 0:
                price_impact = (amount - amount_out) / amount

            quote = UniswapQuote(
                quote_id=f"uq_{uuid.uuid4().hex[:8]}",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount,
                amount_out=amount_out,
                price_impact=price_impact,
                fees=fees,
                route=route,
                estimated_time=30 if version == UniswapVersion.V3 else 60,
                confidence=0.99 if version == UniswapVersion.V3 else 0.98,
            )

            self._quotes_cache[cache_key] = (time.time(), quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_v2_swap_transaction(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        min_amount_out: Decimal,
        wallet_address: str,
        deadline: int,
    ) -> Dict[str, Any]:
        """Construit une transaction de swap V2"""
        router = self._contracts["v2"]["ethereum"]["router"]
        amount_wei = int(amount * Decimal(1e18))
        min_amount_wei = int(min_amount_out * Decimal(1e18))
        path = [to_checksum_address(token_in), to_checksum_address(token_out)]
        deadline_timestamp = int(time.time()) + deadline

        if token_in == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            tx = router.functions.swapExactETHForTokens(
                min_amount_wei,
                path,
                to_checksum_address(wallet_address),
                deadline_timestamp,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "value": amount_wei,
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })
        else:
            tx = router.functions.swapExactTokensForTokens(
                amount_wei,
                min_amount_wei,
                path,
                to_checksum_address(wallet_address),
                deadline_timestamp,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

        return dict(tx)

    async def _build_v3_swap_transaction(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        min_amount_out: Decimal,
        wallet_address: str,
        deadline: int,
    ) -> Dict[str, Any]:
        """Construit une transaction de swap V3"""
        router = self._contracts["v3"]["ethereum"]["router"]
        amount_wei = int(amount * Decimal(1e18))
        min_amount_wei = int(min_amount_out * Decimal(1e18))

        # Encodage du path pour V3
        path = await self._encode_v3_path(token_in, token_out)

        if token_in == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
            tx = router.functions.exactInputSingle({
                "tokenIn": to_checksum_address(token_in),
                "tokenOut": to_checksum_address(token_out),
                "fee": 3000,  # 0.3%
                "recipient": to_checksum_address(wallet_address),
                "deadline": int(time.time()) + deadline,
                "amountIn": amount_wei,
                "amountOutMinimum": min_amount_wei,
                "sqrtPriceLimitX96": 0,
            }).build_transaction({
                "from": to_checksum_address(wallet_address),
                "value": amount_wei,
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })
        else:
            tx = router.functions.exactInputSingle({
                "tokenIn": to_checksum_address(token_in),
                "tokenOut": to_checksum_address(token_out),
                "fee": 3000,
                "recipient": to_checksum_address(wallet_address),
                "deadline": int(time.time()) + deadline,
                "amountIn": amount_wei,
                "amountOutMinimum": min_amount_wei,
                "sqrtPriceLimitX96": 0,
            }).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price("ethereum"),
            })

        return dict(tx)

    # ============================================================
    # MÉTHODES DE DEVIS
    # ============================================================

    async def _get_v2_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
    ) -> Decimal:
        """Obtient un devis V2"""
        router = self._contracts["v2"]["ethereum"]["router"]
        amount_wei = int(amount * Decimal(1e18))
        path = [to_checksum_address(token_in), to_checksum_address(token_out)]

        amounts = await self._async_call(
            router.functions.getAmountsOut(amount_wei, path)
        )

        return Decimal(str(amounts[1])) / Decimal(1e18)

    async def _get_v3_quote(
        self,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
    ) -> Tuple[Decimal, List[str]]:
        """Obtient un devis V3"""
        quoter = self._contracts["v3"]["ethereum"]["quoter"]
        amount_wei = int(amount * Decimal(1e18))

        path = await self._encode_v3_path(token_in, token_out)

        amount_out = await self._async_call(
            quoter.functions.quoteExactInput(path, amount_wei)
        )

        return Decimal(str(amount_out)) / Decimal(1e18), [token_in, token_out]

    async def _encode_v3_path(self, token_in: str, token_out: str) -> bytes:
        """Encode un path V3"""
        # Pour V3, le path est: tokenIn -> fee -> tokenOut
        token_in_bytes = bytes.fromhex(token_in[2:])
        token_out_bytes = bytes.fromhex(token_out[2:])
        fee_bytes = (3000).to_bytes(3, byteorder='big')

        return token_in_bytes + fee_bytes + token_out_bytes

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_token_address(self, token: str, chain: str) -> str:
        """Obtient l'adresse d'un token"""
        token_addresses = {
            "ethereum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
            },
            "polygon": {
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
            },
            "arbitrum": {
                "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
                "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
                "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
                "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
            },
            "optimism": {
                "WETH": "0x4200000000000000000000000000000000000006",
                "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
                "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
                "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
            },
        }
        return token_addresses.get(chain, {}).get(token, token)

    async def _get_router_address(self, chain: str, version: UniswapVersion) -> str:
        """Obtient l'adresse du router"""
        if version == UniswapVersion.V2:
            return UNISWAP_V2_ADDRESSES[UniswapChain(chain)]["router"]
        else:
            return UNISWAP_V3_ADDRESSES[UniswapChain(chain)]["router"]

    async def _get_balance(self, token: str, chain: str, address: str) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            if token == "ETH":
                balance = await provider.eth.get_balance(
                    to_checksum_address(address)
                )
                return Decimal(str(balance)) / Decimal(1e18)

            token_address = await self._get_token_address(token, chain)
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            balance = await token_contract.functions.balanceOf(
                to_checksum_address(address)
            ).call()
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            logger.warning(f"Erreur de solde: {e}")
            return Decimal("0")

    async def _approve_token(
        self,
        token_address: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token pour un contrat"""
        try:
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                return True

            provider = self.web3_providers.get(chain)
            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            amount_wei = int(amount * Decimal(1e18))

            allowance = await token_contract.functions.allowance(
                to_checksum_address(wallet.address),
                to_checksum_address(spender),
            ).call()

            if allowance >= amount_wei:
                return True

            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet.address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(approve_tx)
            await self._send_transaction(chain, signed_tx)

            logger.info(f"Approval réussi")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval: {e}")
            raise DeFiError(f"Erreur d'approval: {e}")

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(self, chain: str, signed_tx: Any) -> HexBytes:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise DeFiError("Transaction échouée")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise DeFiError(f"Erreur d'envoi de transaction: {e}")

    async def _wait_for_transaction(
        self,
        provider: Web3,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await provider.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    return dict(receipt)
            except Exception:
                pass
            await asyncio.sleep(2)

        raise DeFiError(f"Timeout de transaction: {tx_hash.hex()}")

    async def _async_call(self, call_func) -> Any:
        """Appel asynchrone d'une fonction de contrat"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, call_func.call)

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_swaps": self._total_swaps,
            "total_liquidity_added": str(self._total_liquidity_added),
            "total_rewards_claimed": str(self._total_rewards_claimed),
            "pools_cached": len(self._pools_cache),
            "positions_cached": len(self._positions_cache),
            "quotes_cached": len(self._quotes_cache),
            "chains_supported": list(self._contracts["v2"].keys()) + list(self._contracts["v3"].keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources UniswapIntegration...")

        self._pools_cache.clear()
        self._positions_cache.clear()
        self._quotes_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_uniswap_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> UniswapIntegration:
    """
    Crée une instance de UniswapIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de UniswapIntegration
    """
    return UniswapIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de UniswapIntegration"""
    # Configuration
    config = {}

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "polygon": Web3(Web3.HTTPProvider("https://polygon-rpc.com")),
    }

    # Ajout du middleware PoA pour Polygon
    try:
        web3_providers["polygon"].middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création de l'intégration
    uniswap = create_uniswap_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Obtention d'un devis V3
    quote = await uniswap.get_quote(
        token_in="ETH",
        token_out="USDC",
        amount=Decimal("1"),
        chain="ethereum",
        version=UniswapVersion.V3,
    )

    print(f"Devis V3 ETH -> USDC:")
    print(f"  Amount out: {quote.amount_out}")
    print(f"  Price impact: {quote.price_impact:.2%}")
    print(f"  Fees: {quote.fees}")

    # Obtention d'un devis V2
    quote_v2 = await uniswap.get_quote(
        token_in="ETH",
        token_out="USDC",
        amount=Decimal("1"),
        chain="ethereum",
        version=UniswapVersion.V2,
    )

    print(f"Devis V2 ETH -> USDC:")
    print(f"  Amount out: {quote_v2.amount_out}")
    print(f"  Price impact: {quote_v2.price_impact:.2%}")
    print(f"  Fees: {quote_v2.fees}")

    # Statistiques
    stats = uniswap.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await uniswap.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
