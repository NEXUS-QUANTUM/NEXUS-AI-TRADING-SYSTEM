# blockchain/defi/staking.py.
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Staking - Gestion du Staking DeFi

Ce module implémente un système complet de gestion du staking pour les
protocoles DeFi, supportant le staking simple, le staking de LP tokens,
le staking de gouvernance, et l'optimisation des rendements.

Fonctionnalités principales:
- Staking de tokens natifs
- Staking de LP tokens
- Staking de gouvernance
- Farming des récompenses
- Optimisation des rendements
- Monitoring des positions
- Gestion des risques
- Support de multiples protocoles
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

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class StakingProtocol(Enum):
    """Protocoles de staking supportés"""
    LIDO = "lido"
    ROCKET_POOL = "rocket_pool"
    AAVE = "aave"
    COMPOUND = "compound"
    CURVE = "curve"
    UNISWAP = "uniswap"
    PANCAKESWAP = "pancakeswap"
    MAKER = "maker"
    SYNTHETIX = "synthetix"


class StakingType(Enum):
    """Types de staking"""
    NATIVE = "native"  # Staking de token natif
    LP = "lp"  # Staking de LP tokens
    GOVERNANCE = "governance"  # Staking de gouvernance
    LIQUID = "liquid"  # Staking liquide (ex: Lido)
    FARMING = "farming"  # Yield farming


@dataclass
class StakingPosition:
    """Position de staking"""
    position_id: str
    protocol: StakingProtocol
    chain: str
    user: str
    token: str
    staked_amount: Decimal
    staked_value_usd: Decimal
    rewards: List[Dict[str, Any]]
    apy: Decimal
    lock_period: int  # secondes
    lock_end: Optional[datetime] = None
    status: str = "active"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "user": self.user,
            "token": self.token,
            "staked_amount": str(self.staked_amount),
            "staked_value_usd": str(self.staked_value_usd),
            "rewards": self.rewards,
            "apy": str(self.apy),
            "lock_period": self.lock_period,
            "lock_end": self.lock_end.isoformat() if self.lock_end else None,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class StakingQuote:
    """Devis de staking"""
    quote_id: str
    protocol: StakingProtocol
    chain: str
    token: str
    amount: Decimal
    estimated_apy: Decimal
    estimated_rewards: Decimal
    lock_period: int
    fees: Decimal
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
            "lock_period": self.lock_period,
            "fees": str(self.fees),
            "confidence": self.confidence,
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

PROTOCOL_CONFIGS = {
    StakingProtocol.LIDO: {
        "name": "Lido",
        "chains": ["ethereum", "polygon"],
        "tokens": ["ETH", "stETH"],
        "min_stake": Decimal("0.001"),
        "apy_range": (Decimal("0.03"), Decimal("0.06")),
        "risk_level": RiskLevel.LOW,
    },
    StakingProtocol.ROCKET_POOL: {
        "name": "Rocket Pool",
        "chains": ["ethereum"],
        "tokens": ["ETH", "rETH"],
        "min_stake": Decimal("0.01"),
        "apy_range": (Decimal("0.035"), Decimal("0.065")),
        "risk_level": RiskLevel.LOW,
    },
    StakingProtocol.AAVE: {
        "name": "Aave",
        "chains": ["ethereum", "polygon", "arbitrum"],
        "tokens": ["AAVE", "aAAVE"],
        "min_stake": Decimal("0.1"),
        "apy_range": (Decimal("0.02"), Decimal("0.08")),
        "risk_level": RiskLevel.MEDIUM,
    },
    StakingProtocol.CURVE: {
        "name": "Curve",
        "chains": ["ethereum", "polygon", "arbitrum"],
        "tokens": ["CRV", "3pool"],
        "min_stake": Decimal("0.01"),
        "apy_range": (Decimal("0.04"), Decimal("0.12")),
        "risk_level": RiskLevel.MEDIUM,
    },
    StakingProtocol.PANCAKESWAP: {
        "name": "PancakeSwap",
        "chains": ["bsc"],
        "tokens": ["CAKE", "BNB"],
        "min_stake": Decimal("0.01"),
        "apy_range": (Decimal("0.05"), Decimal("0.20")),
        "risk_level": RiskLevel.MEDIUM,
    },
    StakingProtocol.SYNTHETIX: {
        "name": "Synthetix",
        "chains": ["ethereum"],
        "tokens": ["SNX", "sUSD"],
        "min_stake": Decimal("1"),
        "apy_range": (Decimal("0.05"), Decimal("0.15")),
        "risk_level": RiskLevel.HIGH,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class StakingManager(BaseProtocol):
    """
    Gestionnaire de staking DeFi
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        protocol_instances: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de staking

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            protocol_instances: Instances des protocoles
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.protocol_instances = protocol_instances
        self.cache_ttl = cache_ttl

        # États internes
        self._positions: Dict[str, StakingPosition] = {}
        self._quotes_cache: Dict[str, Tuple[float, StakingQuote]] = {}
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
        self._total_staked = Decimal("0")
        self._total_rewards_claimed = Decimal("0")
        self._total_unstaked = Decimal("0")

        # Chargement des positions
        self._load_positions()

        logger.info("StakingManager initialisé avec succès")

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
        protocol: StakingProtocol,
        chain: str,
        token: str,
        amount: Decimal,
        force_refresh: bool = False,
        **kwargs,
    ) -> StakingQuote:
        """
        Obtient un devis de staking

        Args:
            protocol: Protocole
            chain: Chaîne
            token: Token à staker
            amount: Montant
            force_refresh: Forcer le rafraîchissement
            **kwargs: Arguments additionnels

        Returns:
            Devis de staking
        """
        cache_key = f"{protocol.value}:{chain}:{token}:{amount}"

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
            if amount < protocol_config["min_stake"]:
                raise DeFiError(
                    f"Montant minimum: {protocol_config['min_stake']}"
                )

            # Obtention de l'APY
            apy = await self._get_apy(protocol, chain, token)

            # Calcul des récompenses estimées
            estimated_rewards = await self._calculate_estimated_rewards(
                amount, apy, 365  # 1 année
            )

            # Calcul des frais
            fees = await self._calculate_fees(protocol, chain, amount)

            # Période de lock
            lock_period = await self._get_lock_period(protocol, token)

            quote = StakingQuote(
                quote_id=f"sq_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                chain=chain,
                token=token,
                amount=amount,
                estimated_apy=apy,
                estimated_rewards=estimated_rewards,
                lock_period=lock_period,
                fees=fees,
                confidence=await self._calculate_confidence(protocol),
                metadata=kwargs,
            )

            # Mise en cache
            self._quotes_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "staking_apy",
                float(apy),
                {"protocol": protocol.value, "chain": chain, "token": token},
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def stake(
        self,
        protocol: StakingProtocol,
        token: str,
        amount: Decimal,
        chain: str,
        wallet_address: str,
        lock_period: Optional[int] = None,
    ) -> StakingPosition:
        """
        Exécute un staking

        Args:
            protocol: Protocole
            token: Token à staker
            amount: Montant
            chain: Chaîne
            wallet_address: Adresse du wallet
            lock_period: Période de lock en secondes

        Returns:
            Position de staking
        """
        logger.info(f"Stake {amount} {token} sur {chain} via {protocol.value}")

        try:
            # Validation
            await self._validate_staking_request(protocol, token, amount, chain)

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {wallet_address}")

            # Obtention du devis
            quote = await self.get_quote(protocol, chain, token, amount)

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(protocol, chain)
            if not protocol_instance:
                raise DeFiError(f"Instance de {protocol.value} non trouvée")

            # Exécution du staking
            tx_hash = await protocol_instance.execute_action(
                action="stake",
                token=token,
                amount=amount,
                address=wallet_address,
                lock_period=lock_period or quote.lock_period,
            )

            # Création de la position
            position = StakingPosition(
                position_id=f"sp_{uuid.uuid4().hex[:12]}",
                protocol=protocol,
                chain=chain,
                user=wallet_address,
                token=token,
                staked_amount=amount,
                staked_value_usd=await self._get_token_value(token, amount),
                rewards=[],
                apy=quote.estimated_apy,
                lock_period=lock_period or quote.lock_period,
                lock_end=datetime.now() + timedelta(seconds=lock_period or quote.lock_period),
                status="active",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={"tx_hash": tx_hash},
            )

            self._positions[position.position_id] = position
            self._total_staked += amount

            # Métriques
            self.metrics.record_increment(
                "staking_executed",
                1,
                {
                    "protocol": protocol.value,
                    "chain": chain,
                    "token": token,
                },
            )

            logger.info(f"Staking exécuté: {position.position_id}")
            return position

        except Exception as e:
            logger.error(f"Erreur de staking: {e}")
            raise DeFiError(f"Erreur de staking: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def unstake(
        self,
        position_id: str,
        amount: Optional[Decimal] = None,
    ) -> str:
        """
        Unstake des tokens

        Args:
            position_id: ID de la position
            amount: Montant à unstaker (optionnel)

        Returns:
            Hash de la transaction
        """
        logger.info(f"Unstake de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != "active":
                raise DeFiError(f"Position {position_id} n'est pas active")

            # Vérification du lock
            if position.lock_end and position.lock_end > datetime.now():
                raise DeFiError(
                    f"Tokens encore lockés jusqu'à {position.lock_end.isoformat()}"
                )

            unstake_amount = amount or position.staked_amount

            if unstake_amount > position.staked_amount:
                raise DeFiError(
                    f"Montant {unstake_amount} dépasse le solde {position.staked_amount}"
                )

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Exécution de l'unstaking
            tx_hash = await protocol_instance.execute_action(
                action="unstake",
                token=position.token,
                amount=unstake_amount,
                address=position.user,
            )

            # Mise à jour de la position
            position.staked_amount -= unstake_amount
            position.updated_at = datetime.now()

            if position.staked_amount <= Decimal("0.001"):
                position.status = "unstaked"

            self._total_unstaked += unstake_amount

            # Métriques
            self.metrics.record_increment(
                "staking_unstaked",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Unstake réussi: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de unstake: {e}")
            raise DeFiError(f"Erreur de unstake: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def claim_rewards(
        self,
        position_id: str,
    ) -> str:
        """
        Claim des récompenses

        Args:
            position_id: ID de la position

        Returns:
            Hash de la transaction
        """
        logger.info(f"Claim rewards de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != "active":
                raise DeFiError(f"Position {position_id} n'est pas active")

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Exécution du claim
            tx_hash = await protocol_instance.execute_action(
                action="claim_rewards",
                token=position.token,
                amount=Decimal("0"),
                address=position.user,
            )

            self._total_rewards_claimed += Decimal("0")  # À calculer
            position.updated_at = datetime.now()

            # Métriques
            self.metrics.record_increment(
                "staking_claimed_rewards",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Rewards claimés: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de claim rewards: {e}")
            raise DeFiError(f"Erreur de claim rewards: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_position(self, position_id: str) -> Optional[StakingPosition]:
        """
        Obtient une position de staking

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._positions.get(position_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_positions(self, user: str) -> List[StakingPosition]:
        """
        Obtient les positions de staking d'un utilisateur

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
    async def get_positions_by_protocol(
        self,
        protocol: StakingProtocol,
        user: str,
    ) -> List[StakingPosition]:
        """
        Obtient les positions de staking d'un utilisateur pour un protocole

        Args:
            protocol: Protocole
            user: Adresse de l'utilisateur

        Returns:
            Liste des positions
        """
        return [
            pos for pos in self._positions.values()
            if pos.user == user and pos.protocol == protocol
        ]

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        interval: int = 300,
    ) -> None:
        """
        Surveille les positions en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des positions de staking")

        while True:
            try:
                for position_id, position in list(self._positions.items()):
                    if position.status != "active":
                        continue

                    # Mise à jour de l'APY
                    updated_apy = await self._get_apy(
                        position.protocol,
                        position.chain,
                        position.token,
                    )
                    position.apy = updated_apy

                    # Mise à jour de la valeur
                    position.staked_value_usd = await self._get_token_value(
                        position.token,
                        position.staked_amount,
                    )

                    position.updated_at = datetime.now()

                    # Vérification des lock expirés
                    if position.lock_end and position.lock_end < datetime.now():
                        # Alerte pour lock expiré
                        await self._send_alert({
                            "type": "stake_lock_expired",
                            "position_id": position.position_id,
                            "token": position.token,
                            "severity": "info",
                        })

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _validate_staking_request(
        self,
        protocol: StakingProtocol,
        token: str,
        amount: Decimal,
        chain: str,
    ) -> None:
        """Valide une requête de staking"""
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
        if amount < protocol_config["min_stake"]:
            raise ValidationError(
                f"Montant minimum: {protocol_config['min_stake']}"
            )

    async def _get_apy(
        self,
        protocol: StakingProtocol,
        chain: str,
        token: str,
    ) -> Decimal:
        """Obtient l'APY pour un staking"""
        # Simulé - dans la réalité, on interrogerait les contrats
        base_rates = {
            StakingProtocol.LIDO: {
                "ETH": Decimal("0.035"),
                "stETH": Decimal("0.035"),
            },
            StakingProtocol.ROCKET_POOL: {
                "ETH": Decimal("0.04"),
                "rETH": Decimal("0.04"),
            },
            StakingProtocol.AAVE: {
                "AAVE": Decimal("0.05"),
                "aAAVE": Decimal("0.05"),
            },
            StakingProtocol.CURVE: {
                "CRV": Decimal("0.08"),
                "3pool": Decimal("0.06"),
            },
            StakingProtocol.PANCAKESWAP: {
                "CAKE": Decimal("0.15"),
                "BNB": Decimal("0.08"),
            },
            StakingProtocol.SYNTHETIX: {
                "SNX": Decimal("0.12"),
                "sUSD": Decimal("0.08"),
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
        # Calcul simple: amount * apy * (days/365)
        return amount * apy * Decimal(str(days / 365))

    async def _calculate_fees(
        self,
        protocol: StakingProtocol,
        chain: str,
        amount: Decimal,
    ) -> Decimal:
        """Calcule les frais de staking"""
        # Frais de gaz estimés
        gas_fee = Decimal("0.001")  # Simulé

        # Frais de protocole
        protocol_fee = amount * Decimal("0.0005")  # 0.05%

        return gas_fee + protocol_fee

    async def _get_lock_period(
        self,
        protocol: StakingProtocol,
        token: str,
    ) -> int:
        """Obtient la période de lock"""
        lock_periods = {
            StakingProtocol.LIDO: 0,  # Pas de lock
            StakingProtocol.ROCKET_POOL: 0,
            StakingProtocol.AAVE: 86400,  # 1 jour
            StakingProtocol.CURVE: 604800,  # 7 jours
            StakingProtocol.PANCAKESWAP: 0,
            StakingProtocol.SYNTHETIX: 604800,  # 7 jours
        }
        return lock_periods.get(protocol, 0)

    async def _get_token_value(self, token: str, amount: Decimal) -> Decimal:
        """Obtient la valeur USD d'un token"""
        # Simulé
        prices = {
            "ETH": Decimal("3000"),
            "stETH": Decimal("3000"),
            "rETH": Decimal("3000"),
            "AAVE": Decimal("100"),
            "aAAVE": Decimal("100"),
            "CRV": Decimal("0.5"),
            "3pool": Decimal("1"),
            "CAKE": Decimal("3"),
            "BNB": Decimal("600"),
            "SNX": Decimal("5"),
            "sUSD": Decimal("1"),
        }
        price = prices.get(token, Decimal("1"))
        return amount * price

    async def _calculate_confidence(
        self,
        protocol: StakingProtocol,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            StakingProtocol.LIDO: 0.98,
            StakingProtocol.ROCKET_POOL: 0.97,
            StakingProtocol.AAVE: 0.96,
            StakingProtocol.COMPOUND: 0.96,
            StakingProtocol.CURVE: 0.95,
            StakingProtocol.UNISWAP: 0.96,
            StakingProtocol.PANCAKESWAP: 0.94,
            StakingProtocol.MAKER: 0.97,
            StakingProtocol.SYNTHETIX: 0.93,
        }.get(protocol, 0.95)

        return base_confidence

    async def _get_protocol_instance(
        self,
        protocol: StakingProtocol,
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
        active_positions = sum(1 for p in self._positions.values() if p.status == "active")

        total_staked = sum(p.staked_value_usd for p in self._positions.values())
        total_rewards = sum(
            sum(Decimal(str(r.get("amount", "0"))) for r in p.rewards)
            for p in self._positions.values()
        )

        return {
            "total_positions": total_positions,
            "active_positions": active_positions,
            "total_staked_usd": str(total_staked),
            "total_rewards": str(total_rewards),
            "total_staked": str(self._total_staked),
            "total_unstaked": str(self._total_unstaked),
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
        logger.info("Nettoyage des ressources StakingManager...")

        self._quotes_cache.clear()
        self._positions.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_staking_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> StakingManager:
    """
    Crée une instance de StakingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de StakingManager
    """
    return StakingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de StakingManager"""
    # Configuration
    config = {
        "default_protocol": "lido",
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
        "lido_ethereum": SimpleProtocol(),
        "aave_ethereum": SimpleProtocol(),
        "curve_ethereum": SimpleProtocol(),
    }

    # Création du gestionnaire
    manager = create_staking_manager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
    )

    # Obtention d'un devis
    quote = await manager.get_quote(
        protocol=StakingProtocol.LIDO,
        chain="ethereum",
        token="ETH",
        amount=Decimal("1"),
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un staking
    position = await manager.stake(
        protocol=StakingProtocol.LIDO,
        token="ETH",
        amount=Decimal("1"),
        chain="ethereum",
        wallet_address="0x1234567890123456789012345678901234567890",
    )

    print(f"Position créée: {position.to_dict()}")

    # Claim des récompenses
    if position.position_id:
        tx_hash = await manager.claim_rewards(position.position_id)
        print(f"Claim rewards: {tx_hash}")

    # Unstake
    if position.position_id:
        tx_hash = await manager.unstake(position.position_id, Decimal("0.5"))
        print(f"Unstake: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
