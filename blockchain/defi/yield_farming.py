# blockchain/defi/yield_farming.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Yield Farming - Gestion du Yield Farming DeFi

Ce module implémente un système complet de gestion du yield farming pour
les protocoles DeFi, supportant le farming simple, le compounding, l'optimisation
des rendements, et la gestion des risques.

Fonctionnalités principales:
- Farming de tokens
- Compounding automatique
- Optimisation des rendements
- Gestion des risques
- Support de multiples protocoles
- Monitoring des positions
- Alertes de performance
- Statistiques avancées
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

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .staking import StakingManager
    from .liquidity_pool import LiquidityPoolManager
    from .defi_aggregator import DeFiAggregator
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from .staking import StakingManager
    from .liquidity_pool import LiquidityPoolManager
    from .defi_aggregator import DeFiAggregator

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class FarmingProtocol(Enum):
    """Protocoles de farming supportés"""
    CURVE = "curve"
    UNISWAP = "uniswap"
    PANCAKESWAP = "pancakeswap"
    AAVE = "aave"
    COMPOUND = "compound"
    CONVEX = "convex"
    YEARN = "yearn"
    BEETHOVEN = "beethoven"


class FarmingStrategy(Enum):
    """Stratégies de farming"""
    MAX_APY = "max_apy"  # Maximiser l'APY
    MAX_SAFETY = "max_safety"  # Maximiser la sécurité
    BALANCED = "balanced"  # Équilibré
    COMPOUND = "compound"  # Compounding automatique
    HARVEST = "harvest"  # Harvest manuel


class FarmingStatus(Enum):
    """Statuts de farming"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FarmingPosition:
    """Position de farming"""
    position_id: str
    protocol: FarmingProtocol
    chain: str
    user: str
    token: str
    deposited_amount: Decimal
    deposited_value_usd: Decimal
    rewards: List[Dict[str, Any]]
    total_rewards_value_usd: Decimal
    apy: Decimal
    strategy: FarmingStrategy
    status: FarmingStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "user": self.user,
            "token": self.token,
            "deposited_amount": str(self.deposited_amount),
            "deposited_value_usd": str(self.deposited_value_usd),
            "rewards": self.rewards,
            "total_rewards_value_usd": str(self.total_rewards_value_usd),
            "apy": str(self.apy),
            "strategy": self.strategy.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class FarmingQuote:
    """Devis de farming"""
    quote_id: str
    protocol: FarmingProtocol
    chain: str
    token: str
    amount: Decimal
    estimated_apy: Decimal
    estimated_rewards: Decimal
    estimated_rewards_value_usd: Decimal
    fees: Decimal
    lock_period: int
    risk_level: RiskLevel
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "token": self.token,
            "amount": str(self.amount),
            "estimated_apy": str(self.estimated_apy),
            "estimated_rewards": str(self.estimated_rewards),
            "estimated_rewards_value_usd": str(self.estimated_rewards_value_usd),
            "fees": str(self.fees),
            "lock_period": self.lock_period,
            "risk_level": self.risk_level.value,
            "confidence": self.confidence,
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

PROTOCOL_CONFIGS = {
    FarmingProtocol.CURVE: {
        "name": "Curve",
        "chains": ["ethereum", "polygon", "arbitrum"],
        "tokens": ["3CRV", "stETH", "CRV"],
        "min_deposit": Decimal("10"),
        "apy_range": (Decimal("0.05"), Decimal("0.25")),
        "risk_level": RiskLevel.MEDIUM,
        "lock_period": 0,
        "harvest_interval": 86400,  # 1 jour
    },
    FarmingProtocol.UNISWAP: {
        "name": "Uniswap",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism"],
        "tokens": ["UNI", "ETH-USDC", "ETH-USDT"],
        "min_deposit": Decimal("100"),
        "apy_range": (Decimal("0.03"), Decimal("0.20")),
        "risk_level": RiskLevel.MEDIUM,
        "lock_period": 0,
        "harvest_interval": 86400,
    },
    FarmingProtocol.PANCAKESWAP: {
        "name": "PancakeSwap",
        "chains": ["bsc"],
        "tokens": ["CAKE", "BNB", "CAKE-BNB"],
        "min_deposit": Decimal("10"),
        "apy_range": (Decimal("0.05"), Decimal("0.40")),
        "risk_level": RiskLevel.MEDIUM,
        "lock_period": 0,
        "harvest_interval": 43200,  # 12 heures
    },
    FarmingProtocol.AAVE: {
        "name": "Aave",
        "chains": ["ethereum", "polygon", "arbitrum"],
        "tokens": ["AAVE", "aUSDC", "aETH"],
        "min_deposit": Decimal("1"),
        "apy_range": (Decimal("0.02"), Decimal("0.08")),
        "risk_level": RiskLevel.LOW,
        "lock_period": 0,
        "harvest_interval": 86400,
    },
    FarmingProtocol.CONVEX: {
        "name": "Convex",
        "chains": ["ethereum"],
        "tokens": ["CVX", "cvxCRV"],
        "min_deposit": Decimal("10"),
        "apy_range": (Decimal("0.08"), Decimal("0.35")),
        "risk_level": RiskLevel.HIGH,
        "lock_period": 604800,  # 7 jours
        "harvest_interval": 43200,
    },
    FarmingProtocol.YEARN: {
        "name": "Yearn",
        "chains": ["ethereum", "polygon"],
        "tokens": ["YFI", "yUSDC", "yETH"],
        "min_deposit": Decimal("1"),
        "apy_range": (Decimal("0.04"), Decimal("0.15")),
        "risk_level": RiskLevel.MEDIUM,
        "lock_period": 0,
        "harvest_interval": 86400,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class YieldFarmingManager(BaseProtocol):
    """
    Gestionnaire de yield farming DeFi
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        protocol_instances: Dict[str, Any],
        staking_manager: Optional[StakingManager] = None,
        liquidity_pool_manager: Optional[LiquidityPoolManager] = None,
        aggregator: Optional[DeFiAggregator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de yield farming

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            protocol_instances: Instances des protocoles
            staking_manager: Gestionnaire de staking
            liquidity_pool_manager: Gestionnaire de pools de liquidité
            aggregator: Agrégateur DeFi
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.protocol_instances = protocol_instances
        self.staking_manager = staking_manager
        self.liquidity_pool_manager = liquidity_pool_manager
        self.aggregator = aggregator
        self.cache_ttl = cache_ttl

        # États internes
        self._positions: Dict[str, FarmingPosition] = {}
        self._quotes_cache: Dict[str, Tuple[float, FarmingQuote]] = {}
        self._active_operations: Dict[str, Dict[str, Any]] = {}
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

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Statistiques
        self._total_deposited = Decimal("0")
        self._total_rewards_claimed = Decimal("0")
        self._total_withdrawn = Decimal("0")

        # Chargement des positions
        self._load_positions()

        logger.info("YieldFarmingManager initialisé avec succès")

    def _load_positions(self) -> None:
        """Charge les positions existantes"""
        # Dans une implémentation réelle, on chargerait depuis une base de données
        pass

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_quote(
        self,
        protocol: FarmingProtocol,
        chain: str,
        token: str,
        amount: Decimal,
        strategy: FarmingStrategy = FarmingStrategy.BALANCED,
        force_refresh: bool = False,
        **kwargs,
    ) -> FarmingQuote:
        """
        Obtient un devis de farming

        Args:
            protocol: Protocole
            chain: Chaîne
            token: Token
            amount: Montant
            strategy: Stratégie de farming
            force_refresh: Forcer le rafraîchissement
            **kwargs: Arguments additionnels

        Returns:
            Devis de farming
        """
        cache_key = f"{protocol.value}:{chain}:{token}:{amount}:{strategy.value}"

        if not force_refresh and cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            # Vérification du protocole
            protocol_config = PROTOCOL_CONFIGS.get(protocol)
            if not protocol_config:
                raise DeFiError(f"Protocole {protocol.value} non supporté")

            # Vérification du token
            if token not in protocol_config["tokens"]:
                raise DeFiError(
                    f"Token {token} non supporté par {protocol.value}"
                )

            # Vérification du montant
            if amount < protocol_config["min_deposit"]:
                raise DeFiError(
                    f"Montant minimum: {protocol_config['min_deposit']}"
                )

            # Obtention de l'APY
            apy = await self._get_apy(protocol, chain, token, strategy)

            # Calcul des récompenses estimées
            estimated_rewards = await self._calculate_estimated_rewards(
                amount, apy, 365  # 1 année
            )

            # Valeur des récompenses
            estimated_rewards_value_usd = await self._get_token_value(
                token, estimated_rewards
            )

            # Calcul des frais
            fees = await self._calculate_fees(protocol, chain, amount)

            # Période de lock
            lock_period = protocol_config["lock_period"]

            # Niveau de risque
            risk_level = protocol_config["risk_level"]

            quote = FarmingQuote(
                quote_id=f"fq_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                chain=chain,
                token=token,
                amount=amount,
                estimated_apy=apy,
                estimated_rewards=estimated_rewards,
                estimated_rewards_value_usd=estimated_rewards_value_usd,
                fees=fees,
                lock_period=lock_period,
                risk_level=risk_level,
                confidence=await self._calculate_confidence(protocol),
                metadata=kwargs,
            )

            # Mise en cache
            self._quotes_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "yield_farming_apy",
                float(apy),
                {"protocol": protocol.value, "chain": chain, "token": token},
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def start_farming(
        self,
        protocol: FarmingProtocol,
        token: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        strategy: FarmingStrategy = FarmingStrategy.BALANCED,
        auto_compound: bool = True,
    ) -> FarmingPosition:
        """
        Démarre le farming

        Args:
            protocol: Protocole
            token: Token
            amount: Montant
            chain: Chaîne
            wallet_address: Adresse du wallet
            strategy: Stratégie de farming
            auto_compound: Compounding automatique

        Returns:
            Position de farming
        """
        logger.info(f"Démarrage du farming {amount} {token} sur {chain} via {protocol.value}")

        try:
            # Validation
            await self._validate_farming_request(protocol, token, amount, chain)

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Obtention du devis
            quote = await self.get_quote(protocol, chain, token, amount, strategy)

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(protocol, chain)
            if not protocol_instance:
                raise DeFiError(f"Instance de {protocol.value} non trouvée")

            # Exécution du farming
            tx_hash = await protocol_instance.execute_action(
                action="deposit",
                token=token,
                amount=amount,
                address=wallet_address,
            )

            # Création de la position
            position = FarmingPosition(
                position_id=f"fp_{uuid.uuid4().hex[:12]}",
                protocol=protocol,
                chain=chain,
                user=wallet_address,
                token=token,
                deposited_amount=amount,
                deposited_value_usd=await self._get_token_value(token, amount),
                rewards=[],
                total_rewards_value_usd=Decimal("0"),
                apy=quote.estimated_apy,
                strategy=strategy,
                status=FarmingStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={
                    "tx_hash": tx_hash,
                    "auto_compound": auto_compound,
                },
            )

            self._positions[position.position_id] = position
            self._total_deposited += amount

            # Métriques
            self.metrics.record_increment(
                "yield_farming_started",
                1,
                {
                    "protocol": protocol.value,
                    "chain": chain,
                    "token": token,
                    "strategy": strategy.value,
                },
            )

            logger.info(f"Farming démarré: {position.position_id}")
            return position

        except Exception as e:
            logger.error(f"Erreur de démarrage du farming: {e}")
            raise DeFiError(f"Erreur de démarrage du farming: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def harvest(
        self,
        position_id: str,
    ) -> str:
        """
        Harvest des récompenses

        Args:
            position_id: ID de la position

        Returns:
            Hash de la transaction
        """
        logger.info(f"Harvest de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != FarmingStatus.ACTIVE:
                raise DeFiError(f"Position {position_id} n'est pas active")

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Exécution du harvest
            tx_hash = await protocol_instance.execute_action(
                action="harvest",
                token=position.token,
                amount=Decimal("0"),
                address=position.user,
            )

            # Mise à jour de la position
            # Dans la réalité, on récupérerait les récompenses
            position.rewards.append({
                "token": position.token,
                "amount": "0",  # À calculer
                "value_usd": "0",
                "timestamp": datetime.now().isoformat(),
            })
            position.updated_at = datetime.now()

            self._total_rewards_claimed += Decimal("0")
            self.metrics.record_increment(
                "yield_farming_harvested",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Harvest réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de harvest: {e}")
            raise DeFiError(f"Erreur de harvest: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def compound(
        self,
        position_id: str,
    ) -> str:
        """
        Compose les récompenses

        Args:
            position_id: ID de la position

        Returns:
            Hash de la transaction
        """
        logger.info(f"Compounding de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != FarmingStatus.ACTIVE:
                raise DeFiError(f"Position {position_id} n'est pas active")

            # Harvest puis redépose
            await self.harvest(position_id)

            # Redéposer les récompenses
            # Dans la réalité, on récupérerait le montant exact
            reward_amount = Decimal("0")  # À calculer

            if reward_amount > 0:
                protocol_instance = await self._get_protocol_instance(
                    position.protocol, position.chain
                )
                if protocol_instance:
                    await protocol_instance.execute_action(
                        action="deposit",
                        token=position.token,
                        amount=reward_amount,
                        address=position.user,
                    )

            position.updated_at = datetime.now()

            self.metrics.record_increment(
                "yield_farming_compounded",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Compounding réussi")
            return "0x..."  # Hash de la transaction

        except Exception as e:
            logger.error(f"Erreur de compounding: {e}")
            raise DeFiError(f"Erreur de compounding: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def withdraw(
        self,
        position_id: str,
        amount: Optional[Decimal] = None,
    ) -> str:
        """
        Retire des fonds du farming

        Args:
            position_id: ID de la position
            amount: Montant à retirer (optionnel)

        Returns:
            Hash de la transaction
        """
        logger.info(f"Retrait de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != FarmingStatus.ACTIVE:
                raise DeFiError(f"Position {position_id} n'est pas active")

            withdraw_amount = amount or position.deposited_amount

            if withdraw_amount > position.deposited_amount:
                raise DeFiError(
                    f"Montant {withdraw_amount} dépasse le solde {position.deposited_amount}"
                )

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Exécution du retrait
            tx_hash = await protocol_instance.execute_action(
                action="withdraw",
                token=position.token,
                amount=withdraw_amount,
                address=position.user,
            )

            # Mise à jour de la position
            position.deposited_amount -= withdraw_amount
            position.deposited_value_usd = await self._get_token_value(
                position.token, position.deposited_amount
            )
            position.updated_at = datetime.now()

            if position.deposited_amount <= Decimal("0.001"):
                position.status = FarmingStatus.COMPLETED

            self._total_withdrawn += withdraw_amount
            self.metrics.record_increment(
                "yield_farming_withdrawn",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Retrait réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de retrait: {e}")
            raise DeFiError(f"Erreur de retrait: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_position(self, position_id: str) -> Optional[FarmingPosition]:
        """
        Obtient une position de farming

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._positions.get(position_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_positions(self, user: str) -> List[FarmingPosition]:
        """
        Obtient les positions de farming d'un utilisateur

        Args:
            user: Adresse de l'utilisateur

        Returns:
            Liste des positions
        """
        return [
            pos for pos in self._positions.values()
            if pos.user == user
        ]

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_best_farming_opportunities(
        self,
        token: str,
        chain: str,
        amount: Decimal,
        risk_tolerance: RiskLevel = RiskLevel.MEDIUM,
    ) -> List[Dict[str, Any]]:
        """
        Obtient les meilleures opportunités de farming

        Args:
            token: Token
            chain: Chaîne
            amount: Montant
            risk_tolerance: Tolérance au risque

        Returns:
            Liste des opportunités
        """
        opportunities = []

        for protocol in FarmingProtocol:
            try:
                if chain not in PROTOCOL_CONFIGS[protocol]["chains"]:
                    continue

                if token not in PROTOCOL_CONFIGS[protocol]["tokens"]:
                    continue

                quote = await self.get_quote(
                    protocol=protocol,
                    chain=chain,
                    token=token,
                    amount=amount,
                    force_refresh=True,
                )

                if quote.risk_level.value <= risk_tolerance.value:
                    opportunities.append({
                        "protocol": protocol.value,
                        "apy": str(quote.estimated_apy),
                        "rewards": str(quote.estimated_rewards),
                        "rewards_value_usd": str(quote.estimated_rewards_value_usd),
                        "fees": str(quote.fees),
                        "lock_period": quote.lock_period,
                        "risk_level": quote.risk_level.value,
                        "confidence": quote.confidence,
                    })

            except Exception as e:
                logger.debug(f"Erreur pour {protocol.value}: {e}")

        # Tri par APY décroissant
        opportunities.sort(key=lambda x: Decimal(x["apy"]), reverse=True)

        return opportunities

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        interval: int = 600,  # 10 minutes
    ) -> None:
        """
        Surveille les positions en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des positions de farming")

        while True:
            try:
                for position_id, position in list(self._positions.items()):
                    if position.status != FarmingStatus.ACTIVE:
                        continue

                    # Mise à jour de l'APY
                    updated_apy = await self._get_apy(
                        position.protocol,
                        position.chain,
                        position.token,
                        position.strategy,
                    )
                    position.apy = updated_apy

                    # Mise à jour de la valeur
                    position.deposited_value_usd = await self._get_token_value(
                        position.token,
                        position.deposited_amount,
                    )

                    position.updated_at = datetime.now()

                    # Vérification des alertes
                    if position.apy < Decimal("0.01"):
                        await self._send_alert({
                            "type": "low_apy",
                            "position_id": position.position_id,
                            "protocol": position.protocol.value,
                            "chain": position.chain,
                            "token": position.token,
                            "apy": str(position.apy),
                            "severity": "warning",
                        })

                    # Compounding automatique
                    if position.metadata.get("auto_compound", False):
                        protocol_config = PROTOCOL_CONFIGS.get(position.protocol)
                        if protocol_config:
                            harvest_interval = protocol_config.get("harvest_interval", 86400)
                            last_harvest = position.updated_at
                            if (datetime.now() - last_harvest).total_seconds() > harvest_interval:
                                await self.compound(position_id)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _validate_farming_request(
        self,
        protocol: FarmingProtocol,
        token: str,
        amount: Decimal,
        chain: str,
    ) -> None:
        """Valide une requête de farming"""
        if amount <= Decimal("0"):
            raise ValidationError("Le montant doit être positif")

        # Vérification du protocole
        protocol_config = PROTOCOL_CONFIGS.get(protocol)
        if not protocol_config:
            raise ValidationError(f"Protocole {protocol.value} non supporté")

        # Vérification de la chaîne
        if chain not in protocol_config["chains"]:
            raise ValidationError(
                f"Chaîne {chain} non supportée par {protocol.value}"
            )

        # Vérification du token
        if token not in protocol_config["tokens"]:
            raise ValidationError(
                f"Token {token} non supporté"
            )

        # Vérification du montant minimum
        if amount < protocol_config["min_deposit"]:
            raise ValidationError(
                f"Montant minimum: {protocol_config['min_deposit']}"
            )

    async def _get_apy(
        self,
        protocol: FarmingProtocol,
        chain: str,
        token: str,
        strategy: FarmingStrategy,
    ) -> Decimal:
        """Obtient l'APY pour un farming"""
        # Simulé - dans la réalité, on interrogerait les contrats
        base_rates = {
            FarmingProtocol.CURVE: {
                "3CRV": Decimal("0.08"),
                "stETH": Decimal("0.06"),
                "CRV": Decimal("0.12"),
            },
            FarmingProtocol.UNISWAP: {
                "UNI": Decimal("0.05"),
                "ETH-USDC": Decimal("0.15"),
                "ETH-USDT": Decimal("0.15"),
            },
            FarmingProtocol.PANCAKESWAP: {
                "CAKE": Decimal("0.20"),
                "BNB": Decimal("0.10"),
                "CAKE-BNB": Decimal("0.30"),
            },
            FarmingProtocol.AAVE: {
                "AAVE": Decimal("0.06"),
                "aUSDC": Decimal("0.04"),
                "aETH": Decimal("0.03"),
            },
            FarmingProtocol.CONVEX: {
                "CVX": Decimal("0.15"),
                "cvxCRV": Decimal("0.25"),
            },
            FarmingProtocol.YEARN: {
                "YFI": Decimal("0.08"),
                "yUSDC": Decimal("0.06"),
                "yETH": Decimal("0.05"),
            },
        }

        protocol_rates = base_rates.get(protocol, {})
        return protocol_rates.get(token, Decimal("0.05"))

    async def _calculate_estimated_rewards(
        self,
        amount: Decimal,
        apy: Decimal,
        days: int,
    ) -> Decimal:
        """Calcule les récompenses estimées"""
        return amount * apy * Decimal(str(days / 365))

    async def _calculate_fees(
        self,
        protocol: FarmingProtocol,
        chain: str,
        amount: Decimal,
    ) -> Decimal:
        """Calcule les frais de farming"""
        # Frais de gaz estimés
        gas_fee = Decimal("0.001")  # Simulé

        # Frais de protocole
        protocol_fee = amount * Decimal("0.001")  # 0.1%

        return gas_fee + protocol_fee

    async def _get_token_value(self, token: str, amount: Decimal) -> Decimal:
        """Obtient la valeur USD d'un token"""
        # Simulé
        prices = {
            "3CRV": Decimal("1"),
            "stETH": Decimal("3000"),
            "CRV": Decimal("0.5"),
            "UNI": Decimal("5"),
            "ETH-USDC": Decimal("1"),
            "ETH-USDT": Decimal("1"),
            "CAKE": Decimal("3"),
            "BNB": Decimal("600"),
            "CAKE-BNB": Decimal("1"),
            "AAVE": Decimal("100"),
            "aUSDC": Decimal("1"),
            "aETH": Decimal("3000"),
            "CVX": Decimal("4"),
            "cvxCRV": Decimal("0.6"),
            "YFI": Decimal("8000"),
            "yUSDC": Decimal("1"),
            "yETH": Decimal("3000"),
        }
        price = prices.get(token, Decimal("1"))
        return amount * price

    async def _calculate_confidence(
        self,
        protocol: FarmingProtocol,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            FarmingProtocol.CURVE: 0.95,
            FarmingProtocol.UNISWAP: 0.96,
            FarmingProtocol.PANCAKESWAP: 0.94,
            FarmingProtocol.AAVE: 0.97,
            FarmingProtocol.COMPOUND: 0.97,
            FarmingProtocol.CONVEX: 0.90,
            FarmingProtocol.YEARN: 0.93,
            FarmingProtocol.BEETHOVEN: 0.92,
        }.get(protocol, 0.95)

        return base_confidence

    async def _get_protocol_instance(
        self,
        protocol: FarmingProtocol,
        chain: str,
    ) -> Optional[Any]:
        """Obtient une instance du protocole"""
        key = f"{protocol.value}_{chain}"
        return self.protocol_instances.get(key)

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes

        Args:
            callback: Fonction callback
        """
        self._alert_callbacks.append(callback)

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        total_positions = len(self._positions)
        active_positions = sum(1 for p in self._positions.values() if p.status == FarmingStatus.ACTIVE)

        total_deposited = sum(p.deposited_value_usd for p in self._positions.values())
        total_rewards = sum(p.total_rewards_value_usd for p in self._positions.values())

        return {
            "total_positions": total_positions,
            "active_positions": active_positions,
            "total_deposited_usd": str(total_deposited),
            "total_rewards_usd": str(total_rewards),
            "total_deposited": str(self._total_deposited),
            "total_withdrawn": str(self._total_withdrawn),
            "total_rewards_claimed": str(self._total_rewards_claimed),
            "cache_size": len(self._quotes_cache),
            "active_operations": len(self._active_operations),
            "protocols": {p.value for p in self._positions.keys()},
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources YieldFarmingManager...")

        self._quotes_cache.clear()
        self._positions.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_yield_farming_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> YieldFarmingManager:
    """
    Crée une instance de YieldFarmingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de YieldFarmingManager
    """
    return YieldFarmingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de YieldFarmingManager"""
    # Configuration
    config = {
        "default_protocol": "curve",
        "default_chain": "ethereum",
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Protocol instances (simplifié)
    class SimpleProtocol:
        async def execute_action(self, action, **kwargs):
            return f"0x{hash(str(kwargs)):064x}"

    protocol_instances = {
        "curve_ethereum": SimpleProtocol(),
        "uniswap_ethereum": SimpleProtocol(),
        "pancakeswap_bsc": SimpleProtocol(),
    }

    # Création du gestionnaire
    manager = create_yield_farming_manager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
    )

    # Obtention d'un devis
    quote = await manager.get_quote(
        protocol=FarmingProtocol.CURVE,
        chain="ethereum",
        token="3CRV",
        amount=Decimal("1000"),
    )

    print(f"Devis: {quote.to_dict()}")

    # Démarrage du farming
    position = await manager.start_farming(
        protocol=FarmingProtocol.CURVE,
        token="3CRV",
        amount=Decimal("1000"),
        chain="ethereum",
        wallet_address="0x1234567890123456789012345678901234567890",
        strategy=FarmingStrategy.COMPOUND,
        auto_compound=True,
    )

    print(f"Position créée: {position.to_dict()}")

    # Harvest
    if position.position_id:
        tx_hash = await manager.harvest(position.position_id)
        print(f"Harvest: {tx_hash}")

    # Compound
    if position.position_id:
        tx_hash = await manager.compound(position.position_id)
        print(f"Compound: {tx_hash}")

    # Retrait
    if position.position_id:
        tx_hash = await manager.withdraw(position.position_id, Decimal("500"))
        print(f"Retrait: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
