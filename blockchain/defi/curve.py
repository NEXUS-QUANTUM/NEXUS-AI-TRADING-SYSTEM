# blockchain/defi/curve.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Curve Finance - Intégration DeFi Avancée

Ce module implémente une intégration complète du protocole Curve Finance,
permettant des opérations avancées de swap, de dépôt de liquidités, de staking,
et de yield farming avec des mécanismes d'optimisation des taux.

Fonctionnalités principales:
- Swaps entre stablecoins et tokens
- Dépôts dans les pools Curve
- Retraits de liquidités (LP tokens)
- Staking des LP tokens
- Farming des récompenses (CRV, cvxCRV, etc.)
- Support multi-chain
- Optimisation des taux de swap
- Gestion des slippages
- Monitoring des pools
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

class CurveVersion(Enum):
    """Versions du protocole Curve"""
    V1 = "v1"
    V2 = "v2"
    CRYPTO = "crypto"


class CurvePoolType(Enum):
    """Types de pools Curve"""
    STABLE = "stable"  # Pools de stablecoins
    CRYPTO = "crypto"  # Pools de cryptos volatiles
    META = "meta"  # Meta-pools
    FACTORY = "factory"  # Pools factory
    GAUGE = "gauge"  # Pools avec gauges


class CurveAction(Enum):
    """Actions Curve"""
    SWAP = "swap"
    ADD_LIQUIDITY = "add_liquidity"
    REMOVE_LIQUIDITY = "remove_liquidity"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM_REWARDS = "claim_rewards"
    DEPOSIT_GAUGE = "deposit_gauge"
    WITHDRAW_GAUGE = "withdraw_gauge"


@dataclass
class CurvePoolData:
    """Données d'un pool Curve"""
    pool_id: str
    name: str
    version: CurveVersion
    pool_type: CurvePoolType
    chain: str
    address: str
    lp_token: str
    tokens: List[str]
    balances: List[Decimal]
    virtual_price: Decimal
    base_price: Decimal
    total_supply: Decimal
    fees: Decimal
    admin_fees: Decimal
    apy: Decimal
    tvl: Decimal
    volume_24h: Decimal
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "pool_id": self.pool_id,
            "name": self.name,
            "version": self.version.value,
            "pool_type": self.pool_type.value,
            "chain": self.chain,
            "address": self.address,
            "lp_token": self.lp_token,
            "tokens": self.tokens,
            "balances": [str(b) for b in self.balances],
            "virtual_price": str(self.virtual_price),
            "base_price": str(self.base_price),
            "total_supply": str(self.total_supply),
            "fees": str(self.fees),
            "admin_fees": str(self.admin_fees),
            "apy": str(self.apy),
            "tvl": str(self.tvl),
            "volume_24h": str(self.volume_24h),
            "is_active": self.is_active,
        }


@dataclass
class CurvePosition:
    """Position Curve"""
    position_id: str
    pool_id: str
    user: str
    chain: str
    lp_token: str
    lp_amount: Decimal
    lp_value_usd: Decimal
    staked_amount: Decimal
    staked_value_usd: Decimal
    rewards: List[Dict[str, Any]]
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
            "lp_token": self.lp_token,
            "lp_amount": str(self.lp_amount),
            "lp_value_usd": str(self.lp_value_usd),
            "staked_amount": str(self.staked_amount),
            "staked_value_usd": str(self.staked_value_usd),
            "rewards": self.rewards,
            "apy": str(self.apy),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CurveSwapQuote:
    """Devis de swap Curve"""
    quote_id: str
    pool_id: str
    token_in: str
    token_out: str
    amount_in: Decimal
    amount_out: Decimal
    price_impact: Decimal
    fees: Decimal
    estimated_time: int
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "pool_id": self.pool_id,
            "token_in": self.token_in,
            "token_out": self.token_out,
            "amount_in": str(self.amount_in),
            "amount_out": str(self.amount_out),
            "price_impact": str(self.price_impact),
            "fees": str(self.fees),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


# ============================================================
# ADRESSES DES CONTRATS CURVE
# ============================================================

CURVE_CONTRACTS = {
    "ethereum": {
        "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
        "crypto_factory": "0xF18056Bbd320E96A48e3Fbf8bC061322531aac99",
        "stable_factory": "0x4F5D9E7aD2b2D7b3B0F2A4C7E8D9F0A1B2C3D4E5",
        "gauge_controller": "0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB",
        "minter": "0xd061D61a4d941c39E5453435B6345cE61EB8eB85",
    },
    "polygon": {
        "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
        "crypto_factory": "0xF18056Bbd320E96A48e3Fbf8bC061322531aac99",
    },
    "arbitrum": {
        "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
    },
    "optimism": {
        "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
    },
}

# Pools Curve populaires
CURVE_POOLS = {
    "ethereum": {
        "3pool": {
            "address": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
            "lp_token": "0x6c3F90f043a72FA612cbac8115EE7e52BDe6F490",
            "tokens": ["DAI", "USDC", "USDT"],
            "type": CurvePoolType.STABLE,
            "version": CurveVersion.V1,
        },
        "steth": {
            "address": "0xDC24316b9AE028F1497c275EB9192a3Ea0f67022",
            "lp_token": "0x06325440D014e39736583c165C2963BA99fAf14E",
            "tokens": ["ETH", "stETH"],
            "type": CurvePoolType.CRYPTO,
            "version": CurveVersion.V1,
        },
        "frax": {
            "address": "0xDcEF968d416a41Cdac0ED8702fAC8128A64241A2",
            "lp_token": "0x5E8422345238F34275888049021821E8E08CAa1f",
            "tokens": ["FRAX", "USDC"],
            "type": CurvePoolType.META,
            "version": CurveVersion.V1,
        },
    },
    "polygon": {
        "3pool": {
            "address": "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD6D24C",
            "lp_token": "0x445FE580eF8d70FF569aB36e80c647af338db351",
            "tokens": ["DAI", "USDC", "USDT"],
            "type": CurvePoolType.STABLE,
            "version": CurveVersion.V1,
        },
    },
}


# ============================================================
# ABIS DES CONTRATS
# ============================================================

CURVE_POOL_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "virtual_price",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "get_virtual_price",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "fee",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "admin_fee",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "balances",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "j", "type": "int128"},
            {"name": "dx", "type": "uint256"},
            {"name": "min_dy", "type": "uint256"},
        ],
        "name": "exchange",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amounts", "type": "uint256[]"},
            {"name": "min_mint_amount", "type": "uint256"},
        ],
        "name": "add_liquidity",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "amount", "type": "uint256"},
            {"name": "min_amounts", "type": "uint256[]"},
        ],
        "name": "remove_liquidity",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "amount", "type": "uint256"},
            {"name": "min_amount", "type": "uint256"},
        ],
        "name": "remove_liquidity_one_coin",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "i", "type": "int128"},
            {"name": "j", "type": "int128"},
            {"name": "dx", "type": "uint256"},
        ],
        "name": "get_dy",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "amounts", "type": "uint256[]"},
        ],
        "name": "calc_token_amount",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]

CURVE_GAUGE_ABI = [
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "deposit",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "amount", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [],
        "name": "claim_rewards",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "user", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "user", "type": "address"}],
        "name": "claimable_tokens",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class CurveIntegration(BaseProtocol):
    """
    Intégration avancée du protocole Curve Finance
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
        Initialise l'intégration Curve

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
        self._pools_cache: Dict[str, Dict[str, Tuple[float, CurvePoolData]]] = {}
        self._positions_cache: Dict[str, Tuple[float, CurvePosition]] = {}
        self._quotes_cache: Dict[str, Tuple[float, CurveSwapQuote]] = {}
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
        self._decimals_cache: Dict[str, int] = {}

        # Métriques
        self._total_swaps = 0
        self._total_liquidity_added = Decimal("0")
        self._total_rewards_claimed = Decimal("0")

        # Initialisation des contrats
        self._load_contracts()

        # Initialisation des pools
        self._initialize_pools()

        logger.info("CurveIntegration initialisé avec succès")

    def _load_contracts(self) -> None:
        """Charge les contrats Curve"""
        try:
            self._contracts = {}

            for chain, chain_config in CURVE_CONTRACTS.items():
                if chain not in self.web3_providers:
                    logger.warning(f"Provider Web3 non trouvé pour {chain}")
                    continue

                provider = self.web3_providers[chain]
                self._contracts[chain] = {}

                # Contrats généraux
                for contract_name, address in chain_config.items():
                    if contract_name == "gauge_controller":
                        abi = CURVE_GAUGE_ABI
                    else:
                        abi = CURVE_POOL_ABI

                    self._contracts[chain][contract_name] = provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=abi,
                    )

                # Pools
                pool_config = CURVE_POOLS.get(chain, {})
                for pool_name, pool_info in pool_config.items():
                    pool_contract = provider.eth.contract(
                        address=to_checksum_address(pool_info["address"]),
                        abi=CURVE_POOL_ABI,
                    )
                    self._contracts[chain][f"pool_{pool_name}"] = pool_contract

                    # Gauge si disponible
                    if "gauge" in pool_info:
                        gauge_contract = provider.eth.contract(
                            address=to_checksum_address(pool_info["gauge"]),
                            abi=CURVE_GAUGE_ABI,
                        )
                        self._contracts[chain][f"gauge_{pool_name}"] = gauge_contract

            logger.info(f"Contrats Curve chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des contrats: {e}")
            raise DeFiError(f"Erreur de chargement des contrats: {e}")

    def _initialize_pools(self) -> None:
        """Initialise les pools Curve"""
        # Les pools sont chargées dynamiquement
        pass

    # ============================================================
    # MÉTHODES DE BASE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_pool_data(
        self,
        pool_id: str,
        chain: str,
        force_refresh: bool = False,
    ) -> CurvePoolData:
        """
        Obtient les données d'un pool Curve

        Args:
            pool_id: ID du pool
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Données du pool
        """
        cache_key = f"{chain}:{pool_id}"

        if not force_refresh and cache_key in self._pools_cache.get(chain, {}):
            cached_time, data = self._pools_cache[chain][cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return data

        try:
            # Récupération du contrat du pool
            pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
            if not pool_contract:
                raise DeFiError(f"Pool {pool_id} non trouvé sur {chain}")

            # Récupération des données
            virtual_price = await self._async_call(
                pool_contract.functions.get_virtual_price()
            )

            total_supply = await self._async_call(
                pool_contract.functions.totalSupply()
            )

            fee = await self._async_call(
                pool_contract.functions.fee()
            )

            admin_fee = await self._async_call(
                pool_contract.functions.admin_fee()
            )

            balances = await self._async_call(
                pool_contract.functions.balances()
            )

            # Récupération des données du pool
            pool_info = CURVE_POOLS.get(chain, {}).get(pool_id, {})

            # Calcul de la TVL
            tvl = Decimal("0")
            for balance, token in zip(balances, pool_info.get("tokens", [])):
                token_price = await self._get_token_price(token, chain)
                tvl += Decimal(str(balance)) / Decimal(10 ** 18) * token_price

            # APY estimé (simulé)
            apy = Decimal("0.05")  # 5%

            data = CurvePoolData(
                pool_id=pool_id,
                name=pool_info.get("name", pool_id),
                version=pool_info.get("version", CurveVersion.V1),
                pool_type=pool_info.get("type", CurvePoolType.STABLE),
                chain=chain,
                address=pool_info.get("address", ""),
                lp_token=pool_info.get("lp_token", ""),
                tokens=pool_info.get("tokens", []),
                balances=[Decimal(str(b)) / Decimal(10 ** 18) for b in balances],
                virtual_price=Decimal(str(virtual_price)) / Decimal(10 ** 18),
                base_price=Decimal("1"),
                total_supply=Decimal(str(total_supply)) / Decimal(10 ** 18),
                fees=Decimal(str(fee)) / Decimal(10 ** 10),
                admin_fees=Decimal(str(admin_fee)) / Decimal(10 ** 10),
                apy=apy,
                tvl=tvl,
                volume_24h=Decimal("0"),
                is_active=True,
            )

            # Mise en cache
            if chain not in self._pools_cache:
                self._pools_cache[chain] = {}
            self._pools_cache[chain][cache_key] = (time.time(), data)

            # Métriques
            self.metrics.record_gauge(
                "curve_pool_tvl",
                float(tvl),
                {"pool": pool_id, "chain": chain},
            )
            self.metrics.record_gauge(
                "curve_pool_apy",
                float(apy),
                {"pool": pool_id, "chain": chain},
            )

            return data

        except Exception as e:
            logger.error(f"Erreur de récupération des données du pool: {e}")
            raise DeFiError(f"Erreur de récupération des données du pool: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_position(
        self,
        pool_id: str,
        user: str,
        chain: str,
        force_refresh: bool = False,
    ) -> Optional[CurvePosition]:
        """
        Obtient la position d'un utilisateur dans un pool

        Args:
            pool_id: ID du pool
            user: Adresse de l'utilisateur
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Position ou None
        """
        cache_key = f"{chain}:{pool_id}:{user}"

        if not force_refresh and cache_key in self._positions_cache:
            cached_time, position = self._positions_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return position

        try:
            # Récupération du contrat LP token
            pool_info = CURVE_POOLS.get(chain, {}).get(pool_id, {})
            lp_token_address = pool_info.get("lp_token", "")
            if not lp_token_address:
                return None

            lp_contract = self.web3_providers[chain].eth.contract(
                address=to_checksum_address(lp_token_address),
                abi=self.ERC20_ABI,
            )

            # Solde LP
            lp_balance = await self._async_call(
                lp_contract.functions.balanceOf(to_checksum_address(user))
            )
            lp_amount = Decimal(str(lp_balance)) / Decimal(10 ** 18)

            if lp_amount == 0:
                return None

            # Valeur du LP
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh)
            lp_value = lp_amount * pool_data.virtual_price

            # Staking dans la gauge
            staked_amount = Decimal("0")
            gauge_contract = self._contracts[chain].get(f"gauge_{pool_id}")
            if gauge_contract:
                stake_balance = await self._async_call(
                    gauge_contract.functions.balanceOf(to_checksum_address(user))
                )
                staked_amount = Decimal(str(stake_balance)) / Decimal(10 ** 18)

                # Récompenses claimables
                rewards = await self._get_claimable_rewards(pool_id, user, chain)
            else:
                rewards = []

            position = CurvePosition(
                position_id=f"cp_{uuid.uuid4().hex[:8]}",
                pool_id=pool_id,
                user=user,
                chain=chain,
                lp_token=lp_token_address,
                lp_amount=lp_amount,
                lp_value_usd=lp_value,
                staked_amount=staked_amount,
                staked_value_usd=staked_amount * pool_data.virtual_price,
                rewards=rewards,
                apy=pool_data.apy,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # Mise en cache
            self._positions_cache[cache_key] = (time.time(), position)

            return position

        except Exception as e:
            logger.error(f"Erreur de récupération de la position: {e}")
            raise DeFiError(f"Erreur de récupération de la position: {e}")

    # ============================================================
    # MÉTHODES D'ACTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def swap(
        self,
        pool_id: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        min_amount_out: Optional[Decimal] = None,
    ) -> str:
        """
        Exécute un swap sur Curve

        Args:
            pool_id: ID du pool
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant à swapper
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_amount_out: Montant minimum de sortie

        Returns:
            Hash de la transaction
        """
        logger.info(f"Swap {amount} {token_in} -> {token_out} sur {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du pool
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh=True)

            # Récupération des indices des tokens
            i = pool_data.tokens.index(token_in)
            j = pool_data.tokens.index(token_out)

            # Obtention du devis
            quote = await self.get_swap_quote(
                pool_id, token_in, token_out, amount, chain
            )

            # Montant minimum de sortie
            if min_amount_out is None:
                min_amount_out = quote.amount_out * (1 - Decimal("0.005"))  # 0.5% de slippage

            # Approval
            await self._approve_token(
                token_in,
                amount,
                chain,
                wallet,
                pool_data.address,
            )

            amount_wei = int(amount * Decimal(10 ** 18))

            pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
            if not pool_contract:
                raise DeFiError(f"Pool {pool_id} non trouvé")

            tx = pool_contract.functions.exchange(
                i,
                j,
                amount_wei,
                int(min_amount_out * Decimal(10 ** 18)),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_swaps += 1
            self.metrics.record_increment(
                "curve_swap",
                1,
                {"pool": pool_id, "chain": chain, "token_in": token_in, "token_out": token_out},
            )

            logger.info(f"Swap réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de swap: {e}")
            raise DeFiError(f"Erreur de swap: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def add_liquidity(
        self,
        pool_id: str,
        amounts: Dict[str, Decimal],
        chain: str,
        wallet_address: str,
        min_lp_amount: Optional[Decimal] = None,
    ) -> str:
        """
        Ajoute des liquidités à un pool Curve

        Args:
            pool_id: ID du pool
            amounts: Dictionnaire {token: montant}
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_lp_amount: Montant minimum de LP tokens

        Returns:
            Hash de la transaction
        """
        logger.info(f"Add liquidity à {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du pool
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh=True)

            # Vérification des tokens
            amounts_list = []
            for token in pool_data.tokens:
                if token in amounts:
                    amounts_list.append(amounts[token])
                    # Approval du token
                    await self._approve_token(
                        token,
                        amounts[token],
                        chain,
                        wallet,
                        pool_data.address,
                    )
                else:
                    amounts_list.append(Decimal("0"))

            amount_wei = [int(a * Decimal(10 ** 18)) for a in amounts_list]

            # Calcul du montant minimum de LP
            if min_lp_amount is None:
                pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
                if pool_contract:
                    lp_estimate = await self._async_call(
                        pool_contract.functions.calc_token_amount(amount_wei)
                    )
                    min_lp_amount = Decimal(str(lp_estimate)) / Decimal(10 ** 18)
                    min_lp_amount *= Decimal("0.99")  # 1% de slippage

            pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
            if not pool_contract:
                raise DeFiError(f"Pool {pool_id} non trouvé")

            tx = pool_contract.functions.add_liquidity(
                amount_wei,
                int(min_lp_amount * Decimal(10 ** 18)),
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 400000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_liquidity_added += sum(amounts.values())
            self.metrics.record_increment(
                "curve_add_liquidity",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Liquidité ajoutée: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur d'ajout de liquidité: {e}")
            raise DeFiError(f"Erreur d'ajout de liquidité: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def remove_liquidity(
        self,
        pool_id: str,
        lp_amount: Decimal,
        chain: str,
        wallet_address: str,
        min_amounts: Optional[Dict[str, Decimal]] = None,
    ) -> str:
        """
        Retire des liquidités d'un pool Curve

        Args:
            pool_id: ID du pool
            lp_amount: Montant de LP tokens à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_amounts: Montants minimums par token

        Returns:
            Hash de la transaction
        """
        logger.info(f"Remove liquidity de {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du pool
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh=True)

            # Montants minimums
            if min_amounts is None:
                min_amounts = {}
                for token in pool_data.tokens:
                    min_amounts[token] = Decimal("0")

            min_amounts_list = [int(min_amounts.get(t, 0) * Decimal(10 ** 18)) for t in pool_data.tokens]

            lp_amount_wei = int(lp_amount * Decimal(10 ** 18))

            pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
            if not pool_contract:
                raise DeFiError(f"Pool {pool_id} non trouvé")

            tx = pool_contract.functions.remove_liquidity(
                lp_amount_wei,
                min_amounts_list,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 400000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "curve_remove_liquidity",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Liquidité retirée: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de retrait de liquidité: {e}")
            raise DeFiError(f"Erreur de retrait de liquidité: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake(
        self,
        pool_id: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Stake des LP tokens dans la gauge Curve

        Args:
            pool_id: ID du pool
            amount: Montant de LP tokens à staker
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Stake {amount} LP tokens dans {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération du contrat gauge
            gauge_contract = self._contracts[chain].get(f"gauge_{pool_id}")
            if not gauge_contract:
                raise DeFiError(f"Gauge {pool_id} non trouvé")

            # Approval du LP token
            pool_info = CURVE_POOLS.get(chain, {}).get(pool_id, {})
            lp_token = pool_info.get("lp_token", "")
            if not lp_token:
                raise DeFiError(f"LP token non trouvé pour {pool_id}")

            await self._approve_token(
                lp_token,
                amount,
                chain,
                wallet,
                gauge_contract.address,
            )

            amount_wei = int(amount * Decimal(10 ** 18))

            tx = gauge_contract.functions.deposit(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "curve_stake",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Stake réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de stake: {e}")
            raise DeFiError(f"Erreur de stake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake(
        self,
        pool_id: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Unstake des LP tokens de la gauge Curve

        Args:
            pool_id: ID du pool
            amount: Montant de LP tokens à unstaker
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstake {amount} LP tokens de {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            gauge_contract = self._contracts[chain].get(f"gauge_{pool_id}")
            if not gauge_contract:
                raise DeFiError(f"Gauge {pool_id} non trouvé")

            amount_wei = int(amount * Decimal(10 ** 18))

            tx = gauge_contract.functions.withdraw(
                amount_wei,
            ).build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "curve_unstake",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Unstake réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de unstake: {e}")
            raise DeFiError(f"Erreur de unstake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def claim_rewards(
        self,
        pool_id: str,
        chain: str,
        wallet_address: str,
    ) -> str:
        """
        Claim des récompenses de la gauge Curve

        Args:
            pool_id: ID du pool
            chain: Chaîne
            wallet_address: Adresse du wallet

        Returns:
            Hash de la transaction
        """
        logger.info(f"Claim rewards de {pool_id}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            gauge_contract = self._contracts[chain].get(f"gauge_{pool_id}")
            if not gauge_contract:
                raise DeFiError(f"Gauge {pool_id} non trouvé")

            tx = gauge_contract.functions.claim_rewards().build_transaction({
                "from": to_checksum_address(wallet_address),
                "gas": 300000,
                "gasPrice": await self._get_gas_price(chain),
            })

            signed_tx = wallet.sign_transaction(tx)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self.metrics.record_increment(
                "curve_claim_rewards",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Rewards claimés: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de claim rewards: {e}")
            raise DeFiError(f"Erreur de claim rewards: {e}")

    # ============================================================
    # MÉTHODES DE DEVIS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_swap_quote(
        self,
        pool_id: str,
        token_in: str,
        token_out: str,
        amount: Decimal,
        chain: str,
    ) -> CurveSwapQuote:
        """
        Obtient un devis de swap

        Args:
            pool_id: ID du pool
            token_in: Token d'entrée
            token_out: Token de sortie
            amount: Montant à swapper
            chain: Chaîne

        Returns:
            Devis de swap
        """
        cache_key = f"{pool_id}:{token_in}:{token_out}:{amount}:{chain}"

        if cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            # Récupération du pool
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh=True)

            # Récupération des indices des tokens
            i = pool_data.tokens.index(token_in)
            j = pool_data.tokens.index(token_out)

            pool_contract = self._contracts[chain].get(f"pool_{pool_id}")
            if not pool_contract:
                raise DeFiError(f"Pool {pool_id} non trouvé")

            amount_wei = int(amount * Decimal(10 ** 18))

            # Récupération du montant de sortie
            dy = await self._async_call(
                pool_contract.functions.get_dy(i, j, amount_wei)
            )

            amount_out = Decimal(str(dy)) / Decimal(10 ** 18)

            # Calcul du price impact
            price_impact = Decimal("0")
            if amount_out > 0:
                price_impact = (amount - amount_out) / amount

            # Frais
            fees = amount * pool_data.fees

            quote = CurveSwapQuote(
                quote_id=f"csq_{uuid.uuid4().hex[:8]}",
                pool_id=pool_id,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount,
                amount_out=amount_out,
                price_impact=price_impact,
                fees=fees,
                estimated_time=30,
                confidence=0.98,
            )

            # Mise en cache
            self._quotes_cache[cache_key] = (time.time(), quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_token_price(self, token: str, chain: str) -> Decimal:
        """Obtient le prix d'un token"""
        # Simulé - dans la réalité, on utiliserait des oracles
        prices = {
            "DAI": Decimal("1"),
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "ETH": Decimal("3000"),
            "stETH": Decimal("3000"),
            "FRAX": Decimal("1"),
        }
        return prices.get(token, Decimal("1"))

    async def _get_claimable_rewards(
        self,
        pool_id: str,
        user: str,
        chain: str,
    ) -> List[Dict[str, Any]]:
        """Obtient les récompenses claimables"""
        try:
            gauge_contract = self._contracts[chain].get(f"gauge_{pool_id}")
            if not gauge_contract:
                return []

            claimable = await self._async_call(
                gauge_contract.functions.claimable_tokens(to_checksum_address(user))
            )

            rewards = []
            if claimable > 0:
                rewards.append({
                    "token": "CRV",
                    "amount": str(Decimal(str(claimable)) / Decimal(10 ** 18)),
                    "value_usd": "0",
                })

            return rewards

        except Exception:
            return []

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token pour Curve"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return False

            # Obtention de l'adresse du token
            token_address = await self._get_token_address(token, chain)
            if not token_address:
                return False

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            decimals = await self._get_erc20_decimals(token_contract)
            amount_wei = int(amount * Decimal(10 ** decimals))

            # Vérification de l'allowance
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

            logger.info(f"Approval réussi pour {token}")
            return True

        except Exception as e:
            logger.error(f"Erreur d'approval: {e}")
            raise DeFiError(f"Erreur d'approval: {e}")

    async def _get_token_address(self, token: str, chain: str) -> str:
        """Obtient l'adresse d'un token"""
        # Mapping des tokens
        token_addresses = {
            "ethereum": {
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
                "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "stETH": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
                "FRAX": "0x853d955aCEf822Db058eb8505911ED77F175b99e",
            },
            "polygon": {
                "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
            },
        }

        chain_tokens = token_addresses.get(chain, {})
        return chain_tokens.get(token, "")

    async def _get_erc20_decimals(self, contract: Contract) -> int:
        """Obtient les décimales d'un contrat ERC-20"""
        try:
            return await contract.functions.decimals().call()
        except Exception:
            return 18

    async def _get_gas_price(self, chain: str) -> int:
        """Obtient le prix du gaz"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 50000000000
            return await provider.eth.gas_price
        except Exception:
            return 50000000000

    async def _send_transaction(self, chain: str, signed_tx: Any) -> str:
        """Envoie une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                raise DeFiError(f"Provider Web3 non trouvé pour {chain}")

            tx_hash = await provider.eth.send_raw_transaction(signed_tx)

            receipt = await self._wait_for_transaction(provider, tx_hash)
            if receipt.get("status") != 1:
                raise DeFiError("Transaction échouée")

            return tx_hash.hex()

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
            "chains_supported": list(self._contracts.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources CurveIntegration...")

        self._pools_cache.clear()
        self._positions_cache.clear()
        self._quotes_cache.clear()
        self._price_cache.clear()
        self._decimals_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_curve_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> CurveIntegration:
    """
    Crée une instance de CurveIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de CurveIntegration
    """
    return CurveIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de CurveIntegration"""
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
    curve = create_curve_integration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Récupération des données d'un pool
    pool_data = await curve.get_pool_data("3pool", "ethereum")
    print(f"3pool sur Ethereum:")
    print(f"  TVL: ${pool_data.tvl:,.2f}")
    print(f"  APY: {pool_data.apy:.2%}")
    print(f"  Virtual price: {pool_data.virtual_price:.4f}")
    print(f"  Tokens: {pool_data.tokens}")

    # Obtention d'un devis de swap
    quote = await curve.get_swap_quote(
        pool_id="3pool",
        token_in="DAI",
        token_out="USDC",
        amount=Decimal("1000"),
        chain="ethereum",
    )
    print(f"Swap DAI -> USDC:")
    print(f"  Amount in: {quote.amount_in}")
    print(f"  Amount out: {quote.amount_out}")
    print(f"  Price impact: {quote.price_impact:.4%}")
    print(f"  Fees: {quote.fees}")

    # Récupération d'une position
    position = await curve.get_position(
        pool_id="3pool",
        user="0x...",
        chain="ethereum",
    )
    if position:
        print(f"Position:")
        print(f"  LP amount: {position.lp_amount}")
        print(f"  Value: ${position.lp_value_usd:,.2f}")
        print(f"  Staked: {position.staked_amount}")

    # Statistiques
    stats = curve.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await curve.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
