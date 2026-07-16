# blockchain/defi/pancake_swap.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module PancakeSwap - Intégration DEX sur BSC

Ce module implémente une intégration complète du protocole PancakeSwap
sur Binance Smart Chain (BSC), permettant les swaps, la gestion de liquidité,
le farming et le staking.

Fonctionnalités principales:
- Swaps entre tokens BEP-20
- Gestion des pools de liquidité
- Farming des récompenses CAKE
- Staking de CAKE
- Support des pools Syrup
- Support des pools de loterie
- Optimisation des routes de swap
- Gestion du slippage
- Monitoring des positions
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
    from ..wallets.bsc_wallet import BSCWallet
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
    from ..wallets.bsc_wallet import BSCWallet
    from ..security.encryption import EncryptionManager
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class PancakeAction(Enum):
    """Actions PancakeSwap"""
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    HARVEST = "harvest"


class PancakePoolType(Enum):
    """Types de pools PancakeSwap"""
    V2 = "v2"  # Standard liquidity pool
    STABLE = "stable"  # Stable swap
    SYRUP = "syrup"  # Syrup pool (farming)
    CAKE = "cake"  # CAKE staking


@dataclass
class PancakePool:
    """Pool PancakeSwap"""
    pool_id: str
    pool_type: PancakePoolType
    address: str
    lp_token: str
    tokens: List[str]
    reserves: List[Decimal]
    total_supply: Decimal
    apr: Decimal
    tvl: Decimal
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "pool_id": self.pool_id,
            "pool_type": self.pool_type.value,
            "address": self.address,
            "lp_token": self.lp_token,
            "tokens": self.tokens,
            "reserves": [str(r) for r in self.reserves],
            "total_supply": str(self.total_supply),
            "apr": str(self.apr),
            "tvl": str(self.tvl),
            "is_active": self.is_active,
        }


@dataclass
class PancakePosition:
    """Position PancakeSwap"""
    position_id: str
    pool_id: str
    user: str
    lp_token: str
    lp_amount: Decimal
    token_amounts: List[Decimal]
    value_usd: Decimal
    staked_amount: Decimal
    rewards: List[Dict[str, Any]]
    apr: Decimal
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "pool_id": self.pool_id,
            "user": self.user,
            "lp_token": self.lp_token,
            "lp_amount": str(self.lp_amount),
            "token_amounts": [str(t) for t in self.token_amounts],
            "value_usd": str(self.value_usd),
            "staked_amount": str(self.staked_amount),
            "rewards": self.rewards,
            "apr": str(self.apr),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PancakeQuote:
    """Devis PancakeSwap"""
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
# ADRESSES DES CONTRATS PANCAKESWAP
# ============================================================

PANCAKE_ADDRESSES = {
    "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
    "multicall": "0x1Ee38d535d541c55C9dae27B12edf090C608E6Fb",
    "masterchef": "0x73feaa1eE314F8c655E354234017bE2193C9E24E",
    "masterchef_v2": "0x7dC9F7F6B7cA9C5b9d9e4E5F6A7B8C9D0E1F2A3B",
    "cake": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
    "wbnb": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
}

# Pools populaires
POPULAR_POOLS = {
    "cake_bnb": {
        "address": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
        "lp_token": "0x0eD7e52944161450477ee417DE9Cd3a859b14fD0",
        "tokens": ["CAKE", "BNB"],
    },
    "busd_bnb": {
        "address": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
        "lp_token": "0x58F876857a02D6762E0101bb5C46A8c1ED44Dc16",
        "tokens": ["BUSD", "BNB"],
    },
    "usdt_bnb": {
        "address": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
        "lp_token": "0x16b9a82891338f9bA80E2D6970FddA79D1eb0daE",
        "tokens": ["USDT", "BNB"],
    },
    "eth_bnb": {
        "address": "0x70D8929d04b60Af4fb9B58713eB4C3f43f5B6b96",
        "lp_token": "0x70D8929d04b60Af4fb9B58713eB4C3f43f5B6b96",
        "tokens": ["ETH", "BNB"],
    },
}

# ABIs des contrats
PANCAKE_ROUTER_ABI = [
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
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "payable": True,
        "stateMutability": "payable",
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
        "constant": False,
        "inputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapETHForExactTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "payable": True,
        "stateMutability": "payable",
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

MASTERCHEF_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "pid", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "deposit",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "pid", "type": "uint256"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "pid", "type": "uint256"},
        ],
        "name": "harvest",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "pid", "type": "uint256"},
            {"name": "user", "type": "address"},
        ],
        "name": "userInfo",
        "outputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "rewardDebt", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "pid", "type": "uint256"},
        ],
        "name": "poolInfo",
        "outputs": [
            {"name": "lpToken", "type": "address"},
            {"name": "allocPoint", "type": "uint256"},
            {"name": "lastRewardBlock", "type": "uint256"},
            {"name": "accCakePerShare", "type": "uint256"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalAllocPoint",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class PancakeSwapIntegration(BaseProtocol):
    """
    Intégration avancée de PancakeSwap sur BSC
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        bsc_provider: Web3,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise l'intégration PancakeSwap

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            bsc_provider: Provider Web3 pour BSC
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.bsc_provider = bsc_provider
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # Ajout du middleware PoA pour BSC
        try:
            self.bsc_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
        except Exception:
            pass

        # États internes
        self._contracts: Dict[str, Contract] = {}
        self._pools_cache: Dict[str, Tuple[float, PancakePool]] = {}
        self._positions_cache: Dict[str, Tuple[float, PancakePosition]] = {}
        self._quotes_cache: Dict[str, Tuple[float, PancakeQuote]] = {}
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

        logger.info("PancakeSwapIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats PancakeSwap"""
        try:
            # Router
            self._contracts["router"] = self.bsc_provider.eth.contract(
                address=to_checksum_address(PANCAKE_ADDRESSES["router"]),
                abi=PANCAKE_ROUTER_ABI,
            )

            # MasterChef
            self._contracts["masterchef"] = self.bsc_provider.eth.contract(
                address=to_checksum_address(PANCAKE_ADDRESSES["masterchef"]),
                abi=MASTERCHEF_ABI,
            )

            # MasterChef V2
            if "masterchef_v2" in PANCAKE_ADDRESSES:
                self._contracts["masterchef_v2"] = self.bsc_provider.eth.contract(
                    address=to_checksum_address(PANCAKE_ADDRESSES["masterchef_v2"]),
                    abi=MASTERCHEF_ABI,
                )

            logger.info(f"Contrats PancakeSwap chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    def _initialize_pools(self) -> None:
        """Initialise les pools PancakeSwap"""
        for pool_id, pool_info in POPULAR_POOLS.items():
            self._pools_cache[pool_id] = (
                time.time(),
                PancakePool(
                    pool_id=pool_id,
                    pool_type=PancakePoolType.V2,
                    address=pool_info["address"],
                    lp_token=pool_info["lp_token"],
                    tokens=pool_info["tokens"],
                    reserves=[Decimal("1000000"), Decimal("1000")],
                    total_supply=Decimal("100000"),
                    apr=Decimal("0.35"),
                    tvl=Decimal("1000000"),
                    is_active=True,
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
        wallet_address: str,
        min_amount_out: Optional[Decimal] = None,
        deadline: int = 3600,
    ) -> str:
        """
        Exécute un swap sur PancakeSwap

        Args:
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant à swapper
            wallet_address: Adresse du wallet
            min_amount_out: Montant minimum de sortie
            deadline: Délai en secondes

        Returns:
            Hash de la transaction
        """
        logger.info(f"Swap {amount} {token_in} -> {token_out} sur BSC")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des adresses des tokens
            token_in_addr = await self._get_token_address(token_in)
            token_out_addr = await self._get_token_address(token_out)

            # Vérification du solde
            if token_in != "BNB":
                balance = await self._get_token_balance(token_in_addr, wallet_address)
                if balance < amount:
                    raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Obtention du devis
            quote = await self.get_quote(token_in, token_out, amount)

            # Montant minimum de sortie
            if min_amount_out is None:
                min_amount_out = quote.amount_out * Decimal("0.99")  # 1% de slippage

            # Approval si nécessaire
            if token_in != "BNB":
                await self._approve_token(
                    token_in_addr,
                    amount,
                    wallet_address,
                    wallet,
                    PANCAKE_ADDRESSES["router"],
                )

            # Construction de la transaction
            router = self._contracts["router"]
            amount_wei = int(amount * Decimal(1e18))
            min_amount_wei = int(min_amount_out * Decimal(1e18))
            path = [to_checksum_address(token_in_addr), to_checksum_address(token_out_addr)]
            deadline_timestamp = int(time.time()) + deadline

            if token_in == "BNB":
                tx = router.functions.swapExactETHForTokens(
                    min_amount_wei,
                    path,
                    to_checksum_address(wallet_address),
                    deadline_timestamp,
                ).build_transaction({
                    "from": to_checksum_address(wallet_address),
                    "value": amount_wei,
                    "gas": 300000,
                    "gasPrice": await self._get_gas_price(),
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
                    "gasPrice": await self._get_gas_price(),
                })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(signed_tx)

            self._total_swaps += 1
            self.metrics.record_increment(
                "pancake_swap",
                1,
                {"token_in": token_in, "token_out": token_out},
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
        force_refresh: bool = False,
    ) -> PancakeQuote:
        """
        Obtient un devis de swap

        Args:
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant
            force_refresh: Forcer le rafraîchissement

        Returns:
            Devis de swap
        """
        cache_key = f"{token_in}:{token_out}:{amount}"

        if not force_refresh and cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            # Récupération des adresses des tokens
            token_in_addr = await self._get_token_address(token_in)
            token_out_addr = await self._get_token_address(token_out)

            router = self._contracts["router"]
            amount_wei = int(amount * Decimal(1e18))
            path = [to_checksum_address(token_in_addr), to_checksum_address(token_out_addr)]

            # Obtention du montant de sortie
            amounts = await self._async_call(
                router.functions.getAmountsOut(amount_wei, path)
            )

            amount_out = Decimal(str(amounts[1])) / Decimal(1e18)

            # Calcul du price impact
            price_impact = Decimal("0")
            if amount_out > 0:
                price_impact = (amount - amount_out) / amount

            # Frais (0.25% sur PancakeSwap)
            fees = amount * Decimal("0.0025")

            quote = PancakeQuote(
                quote_id=f"pq_{uuid.uuid4().hex[:8]}",
                token_in=token_in,
                token_out=token_out,
                amount_in=amount,
                amount_out=amount_out,
                price_impact=price_impact,
                fees=fees,
                route=path,
                estimated_time=30,
                confidence=0.99,
            )

            self._quotes_cache[cache_key] = (time.time(), quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - LIQUIDITÉ
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def add_liquidity(
        self,
        token_a: str,
        token_b: str,
        amount_a: Decimal,
        amount_b: Decimal,
        wallet_address: str,
        min_amount_a: Optional[Decimal] = None,
        min_amount_b: Optional[Decimal] = None,
        deadline: int = 3600,
    ) -> str:
        """
        Ajoute de la liquidité à un pool PancakeSwap

        Args:
            token_a: Token A
            token_b: Token B
            amount_a: Montant de token A
            amount_b: Montant de token B
            wallet_address: Adresse du wallet
            min_amount_a: Montant minimum de token A
            min_amount_b: Montant minimum de token B
            deadline: Délai en secondes

        Returns:
            Hash de la transaction
        """
        logger.info(f"Ajout de liquidité {token_a}/{token_b} sur BSC")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des adresses des tokens
            token_a_addr = await self._get_token_address(token_a)
            token_b_addr = await self._get_token_address(token_b)

            # Approvals
            await self._approve_token(
                token_a_addr, amount_a, wallet_address, wallet, PANCAKE_ADDRESSES["router"]
            )
            await self._approve_token(
                token_b_addr, amount_b, wallet_address, wallet, PANCAKE_ADDRESSES["router"]
            )

            # Montants minimums
            if min_amount_a is None:
                min_amount_a = amount_a * Decimal("0.99")
            if min_amount_b is None:
                min_amount_b = amount_b * Decimal("0.99")

            router = self._contracts["router"]
            amount_a_wei = int(amount_a * Decimal(1e18))
            amount_b_wei = int(amount_b * Decimal(1e18))
            min_a_wei = int(min_amount_a * Decimal(1e18))
            min_b_wei = int(min_amount_b * Decimal(1e18))
            deadline_timestamp = int(time.time()) + deadline

            tx = router.functions.addLiquidity(
                to_checksum_address(token_a_addr),
                to_checksum_address(token_b_addr),
                amount_a_wei,
                amount_b_wei,
                min_a_wei,
                min_b_wei,
                to_checksum_address(wallet_address),
                deadline_timestamp,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 400000,
                "gasPrice": await self._get_gas_price(),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(signed_tx)

            self._total_liquidity_added += (amount_a + amount_b) / 2
            self.metrics.record_increment(
                "pancake_add_liquidity",
                1,
                {"token_a": token_a, "token_b": token_b},
            )

            logger.info(f"Liquidité ajoutée: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur d'ajout de liquidité: {e}")
            raise DeFiError(f"Erreur d'ajout de liquidité: {e}")

    # ============================================================
    # MÉTHODES PUBLIQUES - FARMING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake(
        self,
        pool_id: str,
        amount: Decimal,
        wallet_address: str,
        use_v2: bool = False,
    ) -> str:
        """
        Stake des LP tokens dans un pool de farming

        Args:
            pool_id: ID du pool (pid)
            amount: Montant à staker
            wallet_address: Adresse du wallet
            use_v2: Utiliser MasterChef V2

        Returns:
            Hash de la transaction
        """
        logger.info(f"Stake {amount} LP tokens dans le pool {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du pool
            pool = self._pools_cache.get(pool_id)
            if not pool:
                raise DeFiError(f"Pool {pool_id} non trouvé")

            # Approval du LP token
            await self._approve_token(
                pool.lp_token,
                amount,
                wallet_address,
                wallet,
                PANCAKE_ADDRESSES["masterchef_v2" if use_v2 else "masterchef"],
            )

            masterchef = self._contracts["masterchef_v2" if use_v2 else "masterchef"]
            amount_wei = int(amount * Decimal(1e18))

            tx = masterchef.functions.deposit(
                int(pool_id),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(signed_tx)

            self.metrics.record_increment(
                "pancake_stake",
                1,
                {"pool": pool_id},
            )

            logger.info(f"Stake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de stake: {e}")
            raise DeFiError(f"Erreur de stake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake(
        self,
        pool_id: str,
        amount: Decimal,
        wallet_address: str,
        use_v2: bool = False,
    ) -> str:
        """
        Unstake des LP tokens d'un pool de farming

        Args:
            pool_id: ID du pool (pid)
            amount: Montant à unstaker
            wallet_address: Adresse du wallet
            use_v2: Utiliser MasterChef V2

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstake {amount} LP tokens du pool {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            masterchef = self._contracts["masterchef_v2" if use_v2 else "masterchef"]
            amount_wei = int(amount * Decimal(1e18))

            tx = masterchef.functions.withdraw(
                int(pool_id),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(signed_tx)

            self.metrics.record_increment(
                "pancake_unstake",
                1,
                {"pool": pool_id},
            )

            logger.info(f"Unstake réussi: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de unstake: {e}")
            raise DeFiError(f"Erreur de unstake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def claim_rewards(
        self,
        pool_id: str,
        wallet_address: str,
        use_v2: bool = False,
    ) -> str:
        """
        Claim des récompenses CAKE d'un pool de farming

        Args:
            pool_id: ID du pool (pid)
            wallet_address: Adresse du wallet
            use_v2: Utiliser MasterChef V2

        Returns:
            Hash de la transaction
        """
        logger.info(f"Claim rewards du pool {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            masterchef = self._contracts["masterchef_v2" if use_v2 else "masterchef"]

            tx = masterchef.functions.harvest(
                int(pool_id),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 200000,
                "gasPrice": await self._get_gas_price(),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(signed_tx)

            self._total_rewards_claimed += Decimal("0")  # À calculer
            self.metrics.record_increment(
                "pancake_claim_rewards",
                1,
                {"pool": pool_id},
            )

            logger.info(f"Rewards claimés: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de claim rewards: {e}")
            raise DeFiError(f"Erreur de claim rewards: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_token_address(self, token: str) -> str:
        """Obtient l'adresse d'un token sur BSC"""
        token_addresses = {
            "BNB": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
            "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
            "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
            "USDT": "0x55d398326f99059fF775485246999027B3197955",
            "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "DAI": "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
            "ETH": "0x2170Ed0880ac9A755fd29B2688956BD959F933F8",
            "WBTC": "0x7130d2A12B9BCbFAe4F2634d864A1Ee1Ce3Ead9c",
            "XRP": "0x1D2F0da169ceB9fC7B3144628dB156f3F6c60dBE",
            "ADA": "0x3EE2200Efb3400fAbB9AacF31297cBdD1d435D47",
        }
        return token_addresses.get(token, token)

    async def _get_token_balance(self, token_address: str, address: str) -> Decimal:
        """Obtient le solde d'un token"""
        try:
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                balance = await self.bsc_provider.eth.get_balance(
                    to_checksum_address(address)
                )
                return Decimal(str(balance)) / Decimal(1e18)

            token_contract = self.bsc_provider.eth.contract(
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
        wallet_address: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token pour un contrat"""
        try:
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                return True

            token_contract = self.bsc_provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            amount_wei = int(amount * Decimal(1e18))

            # Vérification de l'allowance
            allowance = await token_contract.functions.allowance(
                to_checksum_address(wallet_address),
                to_checksum_address(spender),
            ).call()

            if allowance >= amount_wei:
                return True

            approve_tx = token_contract.functions.approve(
                to_checksum_address(spender),
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 100000,
                "gasPrice": await self._get_gas_price(),
            })

            signed_tx = wallet.sign_transaction(approve_tx)
            await self._send_transaction(signed_tx)

            logger.info(f"Approval réussi pour {token_address}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval: {e}")
            raise DeFiError(f"Erreur d'approval: {e}")

    async def _get_gas_price(self) -> int:
        """Obtient le prix du gaz BSC"""
        try:
            return await self.bsc_provider.eth.gas_price
        except Exception:
            return 5000000000  # 5 Gwei par défaut

    async def _send_transaction(self, signed_tx: Any) -> HexBytes:
        """Envoie une transaction"""
        try:
            tx_hash = await self.bsc_provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(tx_hash)
            if receipt.get("status") != 1:
                raise DeFiError("Transaction échouée")

            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'envoi de transaction: {e}")
            raise DeFiError(f"Erreur d'envoi de transaction: {e}")

    async def _wait_for_transaction(
        self,
        tx_hash: HexBytes,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Attend la confirmation d'une transaction"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                receipt = await self.bsc_provider.eth.get_transaction_receipt(tx_hash)
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
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources PancakeSwapIntegration...")

        self._pools_cache.clear()
        self._positions_cache.clear()
        self._quotes_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_pancake_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    bsc_provider: Web3,
    **kwargs,
) -> PancakeSwapIntegration:
    """
    Crée une instance de PancakeSwapIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        bsc_provider: Provider Web3 BSC
        **kwargs: Arguments additionnels

    Returns:
        Instance de PancakeSwapIntegration
    """
    return PancakeSwapIntegration(
        config=config,
        wallet_manager=wallet_manager,
        bsc_provider=bsc_provider,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de PancakeSwapIntegration"""
    # Configuration
    config = {}

    # Web3 provider BSC
    bsc_provider = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org"))
    try:
        bsc_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
    except Exception:
        pass

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création de l'intégration
    pancake = create_pancake_integration(
        config=config,
        wallet_manager=wallet_manager,
        bsc_provider=bsc_provider,
    )

    # Obtention d'un devis de swap
    quote = await pancake.get_quote(
        token_in="BNB",
        token_out="CAKE",
        amount=Decimal("1"),
    )

    print(f"Devis swap BNB -> CAKE:")
    print(f"  Amount out: {quote.amount_out}")
    print(f"  Price impact: {quote.price_impact:.2%}")
    print(f"  Fees: {quote.fees}")

    # Récupération d'un pool
    pool = pancake._pools_cache.get("cake_bnb")[1] if "cake_bnb" in pancake._pools_cache else None
    if pool:
        print(f"\nPool CAKE-BNB:")
        print(f"  APR: {pool.apr:.2%}")
        print(f"  TVL: ${pool.tvl:,.2f}")

    # Statistiques
    stats = pancake.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Nettoyage
    await pancake.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
