# blockchain/defi/liquidity_pool.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Liquidity Pool - Gestion des Pools de Liquidité DeFi

Ce module implémente un système complet de gestion des pools de liquidité
pour les protocoles DeFi (Uniswap, Curve, Balancer, etc.), permettant
le dépôt, le retrait, le farming et l'optimisation des rendements.

Fonctionnalités principales:
- Interface unifiée pour les pools de liquidité
- Support de multiples protocoles (Uniswap, Curve, Balancer, etc.)
- Dépôt et retrait de liquidités
- Gestion des positions LP
- Farming des récompenses
- Optimisation des rendements
- Monitoring des positions
- Analyse des risques
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel, YieldData

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class LiquidityPoolProtocol(Enum):
    """Protocoles de pool de liquidité supportés"""
    UNISWAP_V3 = "uniswap_v3"
    UNISWAP_V2 = "uniswap_v2"
    CURVE = "curve"
    BALANCER = "balancer"
    PANCAKESWAP = "pancakeswap"
    QUICKSWAP = "quickswap"
    SUSHI = "sushi"
    TRADERJOE = "traderjoe"


class PoolType(Enum):
    """Types de pool"""
    CONSTANT_PRODUCT = "constant_product"  # Uniswap V2
    CONCENTRATED = "concentrated"  # Uniswap V3
    STABLE = "stable"  # Curve
    WEIGHTED = "weighted"  # Balancer
    DYNAMIC = "dynamic"


@dataclass
class LiquidityPoolData:
    """Données d'un pool de liquidité"""
    pool_id: str
    protocol: LiquidityPoolProtocol
    chain: str
    name: str
    pool_type: PoolType
    address: str
    lp_token: str
    tokens: List[str]
    reserves: List[Decimal]
    total_supply: Decimal
    fees: Decimal
    tvl: Decimal
    volume_24h: Decimal
    apy: Decimal
    impermanent_loss: Decimal
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "pool_id": self.pool_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "name": self.name,
            "pool_type": self.pool_type.value,
            "address": self.address,
            "lp_token": self.lp_token,
            "tokens": self.tokens,
            "reserves": [str(r) for r in self.reserves],
            "total_supply": str(self.total_supply),
            "fees": str(self.fees),
            "tvl": str(self.tvl),
            "volume_24h": str(self.volume_24h),
            "apy": str(self.apy),
            "impermanent_loss": str(self.impermanent_loss),
            "is_active": self.is_active,
        }


@dataclass
class LiquidityPosition:
    """Position de liquidité"""
    position_id: str
    pool_id: str
    user: str
    chain: str
    lp_token: str
    lp_amount: Decimal
    token_amounts: List[Decimal]
    value_usd: Decimal
    apy: Decimal
    impermanent_loss: Decimal
    staked_amount: Decimal
    rewards: List[Dict[str, Any]]
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
            "token_amounts": [str(t) for t in self.token_amounts],
            "value_usd": str(self.value_usd),
            "apy": str(self.apy),
            "impermanent_loss": str(self.impermanent_loss),
            "staked_amount": str(self.staked_amount),
            "rewards": self.rewards,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class LiquidityQuote:
    """Devis de liquidité"""
    quote_id: str
    pool_id: str
    tokens: List[str]
    amounts: List[Decimal]
    lp_amount: Decimal
    slippage: Decimal
    fees: Decimal
    estimated_time: int
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "pool_id": self.pool_id,
            "tokens": self.tokens,
            "amounts": [str(a) for a in self.amounts],
            "lp_amount": str(self.lp_amount),
            "slippage": str(self.slippage),
            "fees": str(self.fees),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


# ============================================================
# CONFIGURATION DES POOLS
# ============================================================

POOL_ADDRESSES = {
    "uniswap_v3": {
        "ethereum": {
            "usdc_weth": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "usdt_weth": "0x11b815efB8f581194ae79006d24E0d814B7697F6",
            "dai_weth": "0x60594a405d53811d3BC4766596EFD80fd545A270",
        },
        "polygon": {
            "usdc_weth": "0x45dDa9cb7c25131DF268515131f647d726f50608",
        },
    },
    "curve": {
        "ethereum": {
            "3pool": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
        },
        "polygon": {
            "3pool": "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD6D24C",
        },
    },
    "balancer": {
        "ethereum": {
            "weth_usdc": "0x96646936b91d6B9D7D0c47C496AfBF3D6ec7B6f8",
        },
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class LiquidityPoolManager(BaseProtocol):
    """
    Gestionnaire de pools de liquidité DeFi
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
        Initialise le gestionnaire de pools de liquidité

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
        self._pools_cache: Dict[str, Dict[str, Tuple[float, LiquidityPoolData]]] = {}
        self._positions_cache: Dict[str, Tuple[float, LiquidityPosition]] = {}
        self._quotes_cache: Dict[str, Tuple[float, LiquidityQuote]] = {}
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
        self._total_liquidity_added = Decimal("0")
        self._total_liquidity_removed = Decimal("0")
        self._total_rewards = Decimal("0")

        # Initialisation des pools
        self._initialize_pools()

        logger.info("LiquidityPoolManager initialisé avec succès")

    def _initialize_pools(self) -> None:
        """Initialise les pools de liquidité"""
        # Les pools sont chargées dynamiquement
        pass

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_pool_data(
        self,
        pool_id: str,
        chain: str,
        protocol: Optional[LiquidityPoolProtocol] = None,
        force_refresh: bool = False,
    ) -> LiquidityPoolData:
        """
        Obtient les données d'un pool de liquidité

        Args:
            pool_id: ID du pool
            chain: Chaîne
            protocol: Protocole (optionnel)
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
            # Récupération des données du pool
            pool_data = await self._fetch_pool_data(pool_id, chain, protocol)

            # Mise en cache
            if chain not in self._pools_cache:
                self._pools_cache[chain] = {}
            self._pools_cache[chain][cache_key] = (time.time(), pool_data)

            # Métriques
            self.metrics.record_gauge(
                "liquidity_pool_tvl",
                float(pool_data.tvl),
                {"pool": pool_id, "chain": chain},
            )
            self.metrics.record_gauge(
                "liquidity_pool_apy",
                float(pool_data.apy),
                {"pool": pool_id, "chain": chain},
            )

            return pool_data

        except Exception as e:
            logger.error(f"Erreur de récupération des données du pool: {e}")
            raise DeFiError(f"Erreur de récupération des données du pool: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def add_liquidity(
        self,
        pool_id: str,
        token_amounts: Dict[str, Decimal],
        chain: str,
        wallet_address: str,
        min_lp_amount: Optional[Decimal] = None,
        protocol: Optional[LiquidityPoolProtocol] = None,
    ) -> str:
        """
        Ajoute de la liquidité à un pool

        Args:
            pool_id: ID du pool
            token_amounts: Dictionnaire {token: montant}
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_lp_amount: Montant minimum de LP tokens
            protocol: Protocole (optionnel)

        Returns:
            Hash de la transaction
        """
        logger.info(f"Ajout de liquidité au pool {pool_id} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données du pool
            pool_data = await self.get_pool_data(pool_id, chain, protocol, force_refresh=True)

            # Vérification des montants
            for token, amount in token_amounts.items():
                if token not in pool_data.tokens:
                    raise DeFiError(f"Token {token} non supporté par le pool")

                balance = await self._get_token_balance(token, chain, wallet_address)
                if balance < amount:
                    raise DeFiError(f"Solde insuffisant: {balance} < {amount}")

            # Approvals
            for token, amount in token_amounts.items():
                await self._approve_token(
                    token,
                    amount,
                    chain,
                    wallet,
                    pool_data.address,
                )

            # Construction de la transaction
            tx_data = await self._build_add_liquidity_transaction(
                pool_data, token_amounts, wallet_address, min_lp_amount
            )

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_liquidity_added += sum(token_amounts.values())
            self.metrics.record_increment(
                "liquidity_added",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Liquidité ajoutée: {tx_hash.hex()}")
            return tx_hash.hex()

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
        protocol: Optional[LiquidityPoolProtocol] = None,
    ) -> str:
        """
        Retire de la liquidité d'un pool

        Args:
            pool_id: ID du pool
            lp_amount: Montant de LP tokens à retirer
            chain: Chaîne
            wallet_address: Adresse du wallet
            min_amounts: Montants minimums par token
            protocol: Protocole (optionnel)

        Returns:
            Hash de la transaction
        """
        logger.info(f"Retrait de liquidité du pool {pool_id} sur {chain}")

        try:
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Récupération des données du pool
            pool_data = await self.get_pool_data(pool_id, chain, protocol, force_refresh=True)

            # Vérification du solde LP
            lp_balance = await self._get_lp_balance(pool_data.lp_token, chain, wallet_address)
            if lp_balance < lp_amount:
                raise DeFiError(
                    f"Solde LP insuffisant: {lp_balance} < {lp_amount}"
                )

            # Construction de la transaction
            tx_data = await self._build_remove_liquidity_transaction(
                pool_data, lp_amount, wallet_address, min_amounts
            )

            signed_tx = wallet.sign_transaction(tx_data)
            tx_hash = await self._send_transaction(chain, signed_tx)

            self._total_liquidity_removed += lp_amount
            self.metrics.record_increment(
                "liquidity_removed",
                1,
                {"pool": pool_id, "chain": chain},
            )

            logger.info(f"Liquidité retirée: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Erreur de retrait de liquidité: {e}")
            raise DeFiError(f"Erreur de retrait de liquidité: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_position(
        self,
        pool_id: str,
        user: str,
        chain: str,
        force_refresh: bool = False,
    ) -> Optional[LiquidityPosition]:
        """
        Obtient la position de liquidité d'un utilisateur

        Args:
            pool_id: ID du pool
            user: Adresse de l'utilisateur
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Position de liquidité ou None
        """
        cache_key = f"{chain}:{pool_id}:{user}"

        if not force_refresh and cache_key in self._positions_cache:
            cached_time, position = self._positions_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return position

        try:
            # Récupération des données du pool
            pool_data = await self.get_pool_data(pool_id, chain, force_refresh=force_refresh)

            # Récupération du solde LP
            lp_balance = await self._get_lp_balance(pool_data.lp_token, chain, user)

            if lp_balance == 0:
                return None

            # Récupération des montants de tokens
            token_amounts = await self._get_position_token_amounts(
                pool_data, lp_balance, user
            )

            # Calcul de la valeur
            value_usd = await self._calculate_position_value(
                pool_data, token_amounts
            )

            # Récupération de l'APY et de l'impermanent loss
            apy = pool_data.apy
            impermanent_loss = await self._calculate_impermanent_loss(
                pool_data, token_amounts
            )

            position = LiquidityPosition(
                position_id=f"lp_{uuid.uuid4().hex[:8]}",
                pool_id=pool_id,
                user=user,
                chain=chain,
                lp_token=pool_data.lp_token,
                lp_amount=lp_balance,
                token_amounts=token_amounts,
                value_usd=value_usd,
                apy=apy,
                impermanent_loss=impermanent_loss,
                staked_amount=Decimal("0"),
                rewards=[],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # Mise en cache
            self._positions_cache[cache_key] = (time.time(), position)

            return position

        except Exception as e:
            logger.error(f"Erreur de récupération de la position: {e}")
            raise DeFiError(f"Erreur de récupération de la position: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_quote(
        self,
        pool_id: str,
        token_amounts: Dict[str, Decimal],
        chain: str,
        protocol: Optional[LiquidityPoolProtocol] = None,
    ) -> LiquidityQuote:
        """
        Obtient un devis pour l'ajout de liquidité

        Args:
            pool_id: ID du pool
            token_amounts: Dictionnaire {token: montant}
            chain: Chaîne
            protocol: Protocole (optionnel)

        Returns:
            Devis de liquidité
        """
        cache_key = f"{chain}:{pool_id}:{hash(frozenset(token_amounts.items()))}"

        if cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            # Récupération des données du pool
            pool_data = await self.get_pool_data(pool_id, chain, protocol, force_refresh=True)

            # Calcul du montant de LP
            lp_amount = await self._calculate_lp_amount(
                pool_data, token_amounts
            )

            # Calcul du slippage
            slippage = await self._calculate_slippage(
                pool_data, token_amounts, lp_amount
            )

            # Calcul des frais
            fees = await self._calculate_liquidity_fees(
                pool_data, token_amounts
            )

            quote = LiquidityQuote(
                quote_id=f"lq_{uuid.uuid4().hex[:8]}",
                pool_id=pool_id,
                tokens=list(token_amounts.keys()),
                amounts=list(token_amounts.values()),
                lp_amount=lp_amount,
                slippage=slippage,
                fees=fees,
                estimated_time=60,
                confidence=0.98,
            )

            self._quotes_cache[cache_key] = (time.time(), quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        addresses: List[str],
        chain: str,
        interval: int = 300,
    ) -> None:
        """
        Surveille les positions de liquidité

        Args:
            addresses: Liste des adresses
            chain: Chaîne
            interval: Intervalle en secondes
        """
        logger.info(f"Démarrage du monitoring des positions de liquidité sur {chain}")

        while True:
            try:
                for address in addresses:
                    # Récupération des pools
                    for pool_id in self._get_pool_ids_for_chain(chain):
                        try:
                            position = await self.get_position(
                                pool_id, address, chain, force_refresh=True
                            )
                            if position:
                                # Alerte si impermanent loss trop élevé
                                if position.impermanent_loss > Decimal("0.1"):
                                    await self._send_alert({
                                        "type": "high_impermanent_loss",
                                        "address": address,
                                        "pool": pool_id,
                                        "chain": chain,
                                        "impermanent_loss": str(position.impermanent_loss),
                                        "severity": "warning",
                                    })
                        except Exception as e:
                            logger.debug(f"Erreur pour {pool_id}: {e}")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    async def _fetch_pool_data(
        self,
        pool_id: str,
        chain: str,
        protocol: Optional[LiquidityPoolProtocol],
    ) -> LiquidityPoolData:
        """Récupère les données d'un pool"""
        # Simulé - dans la réalité, on interrogerait les contrats
        return LiquidityPoolData(
            pool_id=pool_id,
            protocol=protocol or LiquidityPoolProtocol.UNISWAP_V3,
            chain=chain,
            name=f"Pool {pool_id}",
            pool_type=PoolType.CONCENTRATED,
            address="0x...",
            lp_token="0x...",
            tokens=["USDC", "WETH"],
            reserves=[Decimal("1000000"), Decimal("300")],
            total_supply=Decimal("100000"),
            fees=Decimal("0.003"),
            tvl=Decimal("1000000"),
            volume_24h=Decimal("500000"),
            apy=Decimal("0.15"),
            impermanent_loss=Decimal("0.02"),
            is_active=True,
        )

    async def _get_token_balance(
        self,
        token: str,
        chain: str,
        address: str,
    ) -> Decimal:
        """Obtient le solde d'un token"""
        # Simulé
        return Decimal("10000")

    async def _get_lp_balance(
        self,
        lp_token: str,
        chain: str,
        address: str,
    ) -> Decimal:
        """Obtient le solde d'un LP token"""
        # Simulé
        return Decimal("100")

    async def _get_position_token_amounts(
        self,
        pool_data: LiquidityPoolData,
        lp_balance: Decimal,
        user: str,
    ) -> List[Decimal]:
        """Obtient les montants de tokens d'une position"""
        # Simulé - basé sur la proportion du pool
        total_supply = pool_data.total_supply
        if total_supply == 0:
            return []

        ratio = lp_balance / total_supply
        return [r * ratio for r in pool_data.reserves]

    async def _calculate_position_value(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: List[Decimal],
    ) -> Decimal:
        """Calcule la valeur d'une position"""
        total_value = Decimal("0")
        for token, amount in zip(pool_data.tokens, token_amounts):
            price = await self._get_token_price(token, pool_data.chain)
            total_value += amount * price
        return total_value

    async def _calculate_lp_amount(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: Dict[str, Decimal],
    ) -> Decimal:
        """Calcule le montant de LP tokens à recevoir"""
        # Simulé - dépend du type de pool
        total_value = Decimal("0")
        for token, amount in token_amounts.items():
            price = await self._get_token_price(token, pool_data.chain)
            total_value += amount * price

        # Ratio approximatif
        if pool_data.tvl > 0:
            return (total_value / pool_data.tvl) * pool_data.total_supply
        return Decimal("0")

    async def _calculate_slippage(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: Dict[str, Decimal],
        lp_amount: Decimal,
    ) -> Decimal:
        """Calcule le slippage"""
        # Simulé
        return Decimal("0.005")

    async def _calculate_liquidity_fees(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: Dict[str, Decimal],
    ) -> Decimal:
        """Calcule les frais de liquidité"""
        total_value = Decimal("0")
        for token, amount in token_amounts.items():
            price = await self._get_token_price(token, pool_data.chain)
            total_value += amount * price
        return total_value * pool_data.fees

    async def _calculate_impermanent_loss(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: List[Decimal],
    ) -> Decimal:
        """Calcule l'impermanent loss"""
        # Simulé
        return Decimal("0.02")

    async def _get_token_price(self, token: str, chain: str) -> Decimal:
        """Obtient le prix d'un token"""
        # Simulé
        prices = {
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),
            "WETH": Decimal("3000"),
            "ETH": Decimal("3000"),
            "WBTC": Decimal("60000"),
        }
        return prices.get(token, Decimal("1"))

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_add_liquidity_transaction(
        self,
        pool_data: LiquidityPoolData,
        token_amounts: Dict[str, Decimal],
        wallet_address: str,
        min_lp_amount: Optional[Decimal],
    ) -> Dict[str, Any]:
        """Construit une transaction d'ajout de liquidité"""
        # Simulé - dépend du protocole
        return {
            "from": to_checksum_address(wallet_address),
            "to": to_checksum_address(pool_data.address),
            "value": 0,
            "gas": 300000,
            "gasPrice": 50000000000,
            "data": "0x",
        }

    async def _build_remove_liquidity_transaction(
        self,
        pool_data: LiquidityPoolData,
        lp_amount: Decimal,
        wallet_address: str,
        min_amounts: Optional[Dict[str, Decimal]],
    ) -> Dict[str, Any]:
        """Construit une transaction de retrait de liquidité"""
        return {
            "from": to_checksum_address(wallet_address),
            "to": to_checksum_address(pool_data.address),
            "value": 0,
            "gas": 300000,
            "gasPrice": 50000000000,
            "data": "0x",
        }

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _approve_token(
        self,
        token: str,
        amount: Decimal,
        chain: str,
        wallet: BaseWallet,
        spender: str,
    ) -> bool:
        """Approuve un token pour un contrat"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return False

            token_address = await self._get_token_address(token, chain)
            if not token_address:
                return False

            token_contract = provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=self.ERC20_ABI,
            )

            amount_wei = int(amount * Decimal(1e18))

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
        # Simulé
        return "0x..."

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

    def _get_pool_ids_for_chain(self, chain: str) -> List[str]:
        """Obtient les IDs des pools pour une chaîne"""
        # Simulé
        return ["usdc_weth", "usdt_weth", "dai_weth"]

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        if hasattr(self, "_alert_callbacks"):
            for callback in getattr(self, "_alert_callbacks", []):
                try:
                    await callback(alert)
                except Exception as e:
                    logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "total_liquidity_added": str(self._total_liquidity_added),
            "total_liquidity_removed": str(self._total_liquidity_removed),
            "total_rewards": str(self._total_rewards),
            "pools_cached": len(self._pools_cache),
            "positions_cached": len(self._positions_cache),
            "quotes_cached": len(self._quotes_cache),
            "chains_supported": list(self._pools_cache.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources LiquidityPoolManager...")

        self._pools_cache.clear()
        self._positions_cache.clear()
        self._quotes_cache.clear()
        self._price_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_liquidity_pool_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> LiquidityPoolManager:
    """
    Crée une instance de LiquidityPoolManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LiquidityPoolManager
    """
    return LiquidityPoolManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de LiquidityPoolManager"""
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

    # Création du gestionnaire
    manager = create_liquidity_pool_manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
    )

    # Récupération des données d'un pool
    pool_data = await manager.get_pool_data(
        pool_id="usdc_weth",
        chain="ethereum",
    )

    print(f"Pool USDC-WETH sur Ethereum:")
    print(f"  TVL: ${pool_data.tvl:,.2f}")
    print(f"  APY: {pool_data.apy:.2%}")
    print(f"  Volume 24h: ${pool_data.volume_24h:,.2f}")

    # Obtention d'un devis
    quote = await manager.get_quote(
        pool_id="usdc_weth",
        token_amounts={"USDC": Decimal("1000"), "WETH": Decimal("1")},
        chain="ethereum",
    )

    print(f"Devis:")
    print(f"  LP tokens: {quote.lp_amount}")
    print(f"  Slippage: {quote.slippage:.2%}")
    print(f"  Fees: ${quote.fees:.2f}")

    # Récupération d'une position
    position = await manager.get_position(
        pool_id="usdc_weth",
        user="0x...",
        chain="ethereum",
    )

    if position:
        print(f"Position:")
        print(f"  LP tokens: {position.lp_amount}")
        print(f"  Valeur: ${position.value_usd:,.2f}")
        print(f"  APY: {position.apy:.2%}")
        print(f"  Impermanent loss: {position.impermanent_loss:.2%}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
