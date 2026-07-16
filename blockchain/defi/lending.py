# blockchain/defi/lending.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Lending - Gestion des Prêts DeFi

Ce module implémente un système complet de gestion des prêts pour les
protocoles DeFi, avec support de multiples protocoles de lending, optimisation
des rendements, gestion des positions et monitoring des risques.

Fonctionnalités principales:
- Interface unifiée pour les prêts
- Support de multiples protocoles (Aave, Compound, etc.)
- Optimisation des rendements
- Gestion des collatéraux
- Monitoring des positions
- Alertes de liquidation
- Gestion des risques
- Support des tokens aTokens et cTokens
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
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, DeFiError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_protocol import BaseProtocol, Position, PositionType, RiskLevel
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class LendingProtocol(Enum):
    """Protocoles de lending supportés"""
    AAVE_V3 = "aave_v3"
    AAVE_V2 = "aave_v2"
    COMPOUND_V3 = "compound_v3"
    COMPOUND_V2 = "compound_v2"
    SPARK = "spark"
    MORPHO = "morpho"
    EULER = "euler"
    RADIANT = "radiant"


class LendingStatus(Enum):
    """Statuts d'un prêt"""
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    LIQUIDATED = "liquidated"
    PENDING = "pending"


class LendingType(Enum):
    """Types de prêt"""
    SUPPLY = "supply"  # Prêt de liquidités
    BORROW = "borrow"  # Emprunt de liquidités


@dataclass
class LendingPosition:
    """Position de prêt"""
    position_id: str
    protocol: LendingProtocol
    chain: str
    lender: str
    token: str
    amount: Decimal
    amount_usd: Decimal
    apy: Decimal
    collateral_token: Optional[str] = None
    collateral_amount: Optional[Decimal] = None
    health_factor: Optional[Decimal] = None
    status: LendingStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "lender": self.lender,
            "token": self.token,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "apy": str(self.apy),
            "collateral_token": self.collateral_token,
            "collateral_amount": str(self.collateral_amount) if self.collateral_amount else None,
            "health_factor": str(self.health_factor) if self.health_factor else None,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class LendingQuote:
    """Devis de prêt"""
    quote_id: str
    protocol: LendingProtocol
    chain: str
    token: str
    amount: Decimal
    apy: Decimal
    estimated_fees: Decimal
    min_amount: Decimal
    max_amount: Decimal
    duration_days: int
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
            "apy": str(self.apy),
            "estimated_fees": str(self.estimated_fees),
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "duration_days": self.duration_days,
            "confidence": self.confidence,
        }


@dataclass
class LendingRequest:
    """Requête de prêt"""
    request_id: str
    protocol: LendingProtocol
    chain: str
    token: str
    amount: Decimal
    lender: str
    lending_type: LendingType
    use_collateral: bool = False
    collateral_token: Optional[str] = None
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "token": self.token,
            "amount": str(self.amount),
            "lender": self.lender,
            "lending_type": self.lending_type.value,
            "use_collateral": self.use_collateral,
            "collateral_token": self.collateral_token,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
        }


@dataclass
class LendingResult:
    """Résultat de prêt"""
    result_id: str
    request_id: str
    position_id: str
    protocol: LendingProtocol
    chain: str
    tx_hash: str
    status: LendingStatus
    amount: Decimal
    apy: Decimal
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "position_id": self.position_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "tx_hash": self.tx_hash,
            "status": self.status.value,
            "amount": str(self.amount),
            "apy": str(self.apy),
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

PROTOCOL_CONFIGS = {
    LendingProtocol.AAVE_V3: {
        "name": "Aave V3",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "avalanche", "base"],
        "supported_tokens": ["USDC", "USDT", "DAI", "WETH", "WBTC", "MATIC", "AVAX"],
        "min_amount": Decimal("0.001"),
        "max_amount": Decimal("1000000"),
        "apy_range": (Decimal("0.01"), Decimal("0.10")),
        "risk_level": RiskLevel.LOW,
        "requires_approval": True,
        "supports_collateral": True,
    },
    LendingProtocol.COMPOUND_V3: {
        "name": "Compound V3",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "base"],
        "supported_tokens": ["USDC", "USDT", "WETH", "WBTC"],
        "min_amount": Decimal("0.01"),
        "max_amount": Decimal("500000"),
        "apy_range": (Decimal("0.01"), Decimal("0.08")),
        "risk_level": RiskLevel.LOW,
        "requires_approval": True,
        "supports_collateral": True,
    },
    LendingProtocol.SPARK: {
        "name": "Spark",
        "chains": ["ethereum"],
        "supported_tokens": ["DAI", "USDC", "USDT", "WETH", "WBTC"],
        "min_amount": Decimal("0.001"),
        "max_amount": Decimal("500000"),
        "apy_range": (Decimal("0.015"), Decimal("0.09")),
        "risk_level": RiskLevel.LOW,
        "requires_approval": True,
        "supports_collateral": True,
    },
    LendingProtocol.MORPHO: {
        "name": "Morpho",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism"],
        "supported_tokens": ["USDC", "USDT", "DAI", "WETH", "WBTC"],
        "min_amount": Decimal("0.001"),
        "max_amount": Decimal("500000"),
        "apy_range": (Decimal("0.02"), Decimal("0.12")),
        "risk_level": RiskLevel.MEDIUM,
        "requires_approval": True,
        "supports_collateral": True,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class LendingManager:
    """
    Gestionnaire de prêts DeFi
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
        Initialise le gestionnaire de prêts

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            protocol_instances: Instances des protocoles DeFi
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.wallet_manager = wallet_manager
        self.protocol_instances = protocol_instances
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._positions: Dict[str, LendingPosition] = {}
        self._quotes_cache: Dict[str, Tuple[float, LendingQuote]] = {}
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
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._total_supplied = Decimal("0")
        self._total_borrowed = Decimal("0")

        # Chargement des positions
        self._load_positions()

        logger.info("LendingManager initialisé avec succès")

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
        protocol: LendingProtocol,
        chain: str,
        token: str,
        amount: Decimal,
        lending_type: LendingType,
        force_refresh: bool = False,
        **kwargs,
    ) -> LendingQuote:
        """
        Obtient un devis de prêt

        Args:
            protocol: Protocole
            chain: Chaîne
            token: Token
            amount: Montant
            lending_type: Type de prêt
            force_refresh: Forcer le rafraîchissement
            **kwargs: Arguments additionnels

        Returns:
            Devis de prêt
        """
        cache_key = f"{protocol.value}:{chain}:{token}:{amount}:{lending_type.value}"

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
            if token not in protocol_config["supported_tokens"]:
                raise DeFiError(
                    f"Token {token} non supporté par {protocol.value}"
                )

            # Vérification du montant
            if amount < protocol_config["min_amount"]:
                raise DeFiError(
                    f"Montant minimum: {protocol_config['min_amount']}"
                )

            if amount > protocol_config["max_amount"]:
                raise DeFiError(
                    f"Montant maximum: {protocol_config['max_amount']}"
                )

            # Obtention de l'APY
            apy = await self._get_apy(
                protocol, chain, token, lending_type
            )

            # Calcul des frais estimés
            estimated_fees = await self._calculate_fees(
                protocol, chain, amount
            )

            # Création du devis
            quote = LendingQuote(
                quote_id=f"lq_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                chain=chain,
                token=token,
                amount=amount,
                apy=apy,
                estimated_fees=estimated_fees,
                min_amount=protocol_config["min_amount"],
                max_amount=protocol_config["max_amount"],
                duration_days=30,  # Par défaut
                confidence=await self._calculate_confidence(protocol),
                metadata=kwargs,
            )

            # Mise en cache
            self._quotes_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "lending_apy",
                float(apy),
                {"protocol": protocol.value, "chain": chain, "token": token},
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_lending(
        self,
        request: LendingRequest,
    ) -> LendingResult:
        """
        Exécute un prêt

        Args:
            request: Requête de prêt

        Returns:
            Résultat de prêt
        """
        logger.info(
            f"Exécution du prêt {request.lending_type.value}: "
            f"{request.amount} {request.token} sur {request.chain}"
        )

        try:
            # Validation
            await self._validate_lending_request(request)

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(request.lender)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {request.lender}")

            # Obtention du devis
            quote = await self.get_quote(
                protocol=request.protocol,
                chain=request.chain,
                token=request.token,
                amount=request.amount,
                lending_type=request.lending_type,
            )

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(
                request.protocol, request.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {request.protocol.value} non trouvée")

            # Exécution via le protocole
            if request.lending_type == LendingType.SUPPLY:
                tx_hash = await protocol_instance.supply(
                    asset=request.token,
                    amount=request.amount,
                    chain=request.chain,
                    wallet_address=request.lender,
                )
            else:
                tx_hash = await protocol_instance.borrow(
                    asset=request.token,
                    amount=request.amount,
                    chain=request.chain,
                    wallet_address=request.lender,
                    collateral_token=request.collateral_token,
                )

            # Création de la position
            position = LendingPosition(
                position_id=f"lp_{uuid.uuid4().hex[:12]}",
                protocol=request.protocol,
                chain=request.chain,
                lender=request.lender,
                token=request.token,
                amount=request.amount,
                amount_usd=await self._get_token_value(request.token, request.amount),
                apy=quote.apy,
                collateral_token=request.collateral_token,
                status=LendingStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._positions[position.position_id] = position

            # Mise à jour des statistiques
            if request.lending_type == LendingType.SUPPLY:
                self._total_supplied += request.amount
            else:
                self._total_borrowed += request.amount

            # Résultat
            result = LendingResult(
                result_id=f"lr_{uuid.uuid4().hex[:8]}",
                request_id=request.request_id,
                position_id=position.position_id,
                protocol=request.protocol,
                chain=request.chain,
                tx_hash=tx_hash,
                status=LendingStatus.ACTIVE,
                amount=request.amount,
                apy=quote.apy,
                timestamp=datetime.now(),
            )

            # Métriques
            self.metrics.record_increment(
                "lending_executed",
                1,
                {
                    "protocol": request.protocol.value,
                    "chain": request.chain,
                    "token": request.token,
                    "type": request.lending_type.value,
                },
            )

            logger.info(f"Prêt exécuté: {result.result_id}")
            return result

        except Exception as e:
            logger.error(f"Erreur d'exécution du prêt: {e}")
            self.metrics.record_increment(
                "lending_failed",
                1,
                {
                    "protocol": request.protocol.value,
                    "chain": request.chain,
                    "error": str(e)[:50],
                },
            )
            raise DeFiError(f"Erreur d'exécution du prêt: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def withdraw(
        self,
        position_id: str,
        amount: Optional[Decimal] = None,
    ) -> str:
        """
        Retire un prêt

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

            if position.status != LendingStatus.ACTIVE:
                raise DeFiError(f"Position {position_id} n'est pas active")

            withdraw_amount = amount or position.amount

            if withdraw_amount > position.amount:
                raise DeFiError(
                    f"Montant {withdraw_amount} dépasse le solde {position.amount}"
                )

            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            tx_hash = await protocol_instance.withdraw(
                asset=position.token,
                amount=withdraw_amount,
                chain=position.chain,
                wallet_address=position.lender,
            )

            # Mise à jour de la position
            position.amount -= withdraw_amount
            position.updated_at = datetime.now()

            if position.amount <= Decimal("0.001"):
                position.status = LendingStatus.WITHDRAWN

            # Métriques
            self.metrics.record_increment(
                "lending_withdrawn",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                    "token": position.token,
                },
            )

            logger.info(f"Retrait effectué: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de retrait: {e}")
            raise DeFiError(f"Erreur de retrait: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_positions(self, lender: str) -> List[LendingPosition]:
        """
        Obtient les positions de prêt d'un utilisateur

        Args:
            lender: Adresse du prêteur

        Returns:
            Liste des positions
        """
        return [
            pos for pos in self._positions.values()
            if pos.lender == lender
        ]

    async def get_position(self, position_id: str) -> Optional[LendingPosition]:
        """
        Obtient une position de prêt

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._positions.get(position_id)

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_positions(
        self,
        interval: int = 60,
    ) -> None:
        """
        Surveille les positions en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring des positions de prêt")

        while True:
            try:
                for position_id, position in list(self._positions.items()):
                    if position.status != LendingStatus.ACTIVE:
                        continue

                    # Mise à jour de l'APY
                    updated_apy = await self._get_apy(
                        position.protocol,
                        position.chain,
                        position.token,
                        LendingType.SUPPLY,
                    )
                    position.apy = updated_apy
                    position.updated_at = datetime.now()

                    # Vérification du health factor pour les emprunts
                    if position.health_factor and position.health_factor < Decimal("1.2"):
                        await self._send_health_alert(position)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _validate_lending_request(self, request: LendingRequest) -> None:
        """Valide une requête de prêt"""
        if request.amount <= Decimal("0"):
            raise ValidationError("Le montant doit être positif")

        # Vérification du protocole
        protocol_config = PROTOCOL_CONFIGS.get(request.protocol)
        if not protocol_config:
            raise ValidationError(f"Protocole {request.protocol.value} non supporté")

        # Vérification de la chaîne
        if request.chain not in protocol_config["chains"]:
            raise ValidationError(
                f"Chaîne {request.chain} non supportée par {request.protocol.value}"
            )

        # Vérification du token
        if request.token not in protocol_config["supported_tokens"]:
            raise ValidationError(
                f"Token {request.token} non supporté"
            )

        # Vérification des montants
        if request.amount < protocol_config["min_amount"]:
            raise ValidationError(
                f"Montant minimum: {protocol_config['min_amount']}"
            )

        if request.amount > protocol_config["max_amount"]:
            raise ValidationError(
                f"Montant maximum: {protocol_config['max_amount']}"
            )

        # Vérification du collatéral
        if request.use_collateral and not request.collateral_token:
            raise ValidationError("Token de collatéral requis")

    async def _get_apy(
        self,
        protocol: LendingProtocol,
        chain: str,
        token: str,
        lending_type: LendingType,
    ) -> Decimal:
        """Obtient l'APY pour un prêt"""
        # Simulé - dans la réalité, on interrogerait les contrats
        base_rates = {
            LendingProtocol.AAVE_V3: {
                "USDC": Decimal("0.03"),
                "USDT": Decimal("0.03"),
                "DAI": Decimal("0.025"),
                "WETH": Decimal("0.02"),
                "WBTC": Decimal("0.025"),
            },
            LendingProtocol.COMPOUND_V3: {
                "USDC": Decimal("0.025"),
                "USDT": Decimal("0.025"),
                "WETH": Decimal("0.015"),
                "WBTC": Decimal("0.02"),
            },
            LendingProtocol.SPARK: {
                "DAI": Decimal("0.035"),
                "USDC": Decimal("0.03"),
                "USDT": Decimal("0.03"),
            },
            LendingProtocol.MORPHO: {
                "USDC": Decimal("0.04"),
                "USDT": Decimal("0.04"),
                "DAI": Decimal("0.035"),
            },
        }

        protocol_rates = base_rates.get(protocol, {})
        rate = protocol_rates.get(token, Decimal("0.025"))

        # Ajustement pour les emprunts (taux plus élevé)
        if lending_type == LendingType.BORROW:
            rate *= Decimal("1.5")

        return rate

    async def _calculate_fees(
        self,
        protocol: LendingProtocol,
        chain: str,
        amount: Decimal,
    ) -> Decimal:
        """Calcule les frais estimés"""
        # Frais de gaz estimés
        gas_fee = Decimal("0.001")  # Simulé

        # Frais de protocole
        protocol_fee = amount * Decimal("0.0005")  # 0.05%

        return gas_fee + protocol_fee

    async def _get_token_value(self, token: str, amount: Decimal) -> Decimal:
        """Obtient la valeur USD d'un token"""
        # Simulé
        prices = {
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),
            "WETH": Decimal("3000"),
            "WBTC": Decimal("60000"),
            "MATIC": Decimal("0.7"),
            "AVAX": Decimal("40"),
        }
        price = prices.get(token, Decimal("1"))
        return amount * price

    async def _calculate_confidence(
        self,
        protocol: LendingProtocol,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            LendingProtocol.AAVE_V3: 0.98,
            LendingProtocol.COMPOUND_V3: 0.97,
            LendingProtocol.SPARK: 0.95,
            LendingProtocol.MORPHO: 0.94,
        }.get(protocol, 0.95)

        return base_confidence

    async def _get_protocol_instance(
        self,
        protocol: LendingProtocol,
        chain: str,
    ) -> Optional[Any]:
        """Obtient une instance du protocole"""
        key = f"{protocol.value}_{chain}"
        return self.protocol_instances.get(key)

    async def _send_health_alert(self, position: LendingPosition) -> None:
        """Envoie une alerte de santé"""
        alert = {
            "type": "lending_health_warning",
            "position_id": position.position_id,
            "protocol": position.protocol.value,
            "chain": position.chain,
            "lender": position.lender,
            "health_factor": str(position.health_factor),
            "amount": str(position.amount),
            "timestamp": datetime.now().isoformat(),
            "severity": "warning",
        }

        logger.warning(f"Alerte de prêt: {alert}")

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
        active_positions = sum(1 for p in self._positions.values() if p.status == LendingStatus.ACTIVE)
        withdrawn_positions = sum(1 for p in self._positions.values() if p.status == LendingStatus.WITHDRAWN)

        total_supplied = sum(p.amount for p in self._positions.values() if p.lending_type == LendingType.SUPPLY)

        return {
            "total_positions": total_positions,
            "active_positions": active_positions,
            "withdrawn_positions": withdrawn_positions,
            "total_supplied": str(self._total_supplied),
            "total_borrowed": str(self._total_borrowed),
            "average_apy": self._calculate_average_apy(),
            "cache_size": len(self._quotes_cache),
            "active_operations": len(self._active_operations),
        }

    def _calculate_average_apy(self) -> Decimal:
        """Calcule l'APY moyen"""
        active_positions = [
            p for p in self._positions.values()
            if p.status == LendingStatus.ACTIVE
        ]

        if not active_positions:
            return Decimal("0")

        total_apy = sum(p.apy for p in active_positions)
        return total_apy / len(active_positions)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources LendingManager...")

        self._quotes_cache.clear()
        self._positions.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_lending_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> LendingManager:
    """
    Crée une instance de LendingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de LendingManager
    """
    return LendingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de LendingManager"""
    # Configuration
    config = {
        "default_protocol": "aave_v3",
        "default_chain": "ethereum",
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Protocol instances (simplifié)
    class SimpleProtocol:
        async def supply(self, **kwargs):
            return f"0x{hash(str(kwargs)):064x}"

        async def borrow(self, **kwargs):
            return f"0x{hash(str(kwargs)):064x}"

        async def withdraw(self, **kwargs):
            return f"0x{hash(str(kwargs)):064x}"

    protocol_instances = {
        "aave_v3_ethereum": SimpleProtocol(),
    }

    # Création du gestionnaire
    manager = create_lending_manager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
    )

    # Obtention d'un devis
    quote = await manager.get_quote(
        protocol=LendingProtocol.AAVE_V3,
        chain="ethereum",
        token="USDC",
        amount=Decimal("10000"),
        lending_type=LendingType.SUPPLY,
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un prêt
    request = LendingRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=LendingProtocol.AAVE_V3,
        chain="ethereum",
        token="USDC",
        amount=Decimal("10000"),
        lender="0x1234567890123456789012345678901234567890",
        lending_type=LendingType.SUPPLY,
    )

    result = await manager.execute_lending(request)
    print(f"Résultat: {result.to_dict()}")

    # Retrait
    if result.position_id:
        tx_hash = await manager.withdraw(result.position_id)
        print(f"Retrait: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
