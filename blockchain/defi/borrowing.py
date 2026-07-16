# blockchain/defi/borrowing.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Borrowing - Gestion des Emprunts DeFi

Ce module implémente un système complet de gestion des emprunts pour les
protocoles DeFi, avec support de multiples protocoles de lending, optimisation
des taux, gestion des positions et monitoring des risques.

Fonctionnalités principales:
- Interface unifiée pour les emprunts
- Support de multiples protocoles (Aave, Compound, etc.)
- Optimisation des taux d'intérêt
- Gestion des collatéraux
- Monitoring des positions
- Alertes de liquidation
- Gestion des risques
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

class BorrowProtocol(Enum):
    """Protocoles de borrowing supportés"""
    AAVE_V3 = "aave_v3"
    AAVE_V2 = "aave_v2"
    COMPOUND_V3 = "compound_v3"
    COMPOUND_V2 = "compound_v2"
    SPARK = "spark"
    MORPHO = "morpho"
    EULER = "euler"
    RADIANT = "radiant"


class InterestRateMode(Enum):
    """Modes de taux d'intérêt"""
    STABLE = "stable"
    VARIABLE = "variable"


class BorrowStatus(Enum):
    """Statuts d'un emprunt"""
    ACTIVE = "active"
    LIQUIDATED = "liquidated"
    REPAID = "repaid"
    DEFAULTED = "defaulted"
    PENDING = "pending"


class CollateralType(Enum):
    """Types de collatéral"""
    TOKEN = "token"
    LP = "lp"
    NFT = "nft"
    STAKED = "staked"


@dataclass
class BorrowPosition:
    """Position d'emprunt"""
    position_id: str
    protocol: BorrowProtocol
    chain: str
    borrower: str
    collateral_token: str
    collateral_amount: Decimal
    collateral_value_usd: Decimal
    debt_token: str
    debt_amount: Decimal
    debt_value_usd: Decimal
    interest_rate_mode: InterestRateMode
    current_interest_rate: Decimal
    liquidation_threshold: Decimal
    health_factor: Decimal
    status: BorrowStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "position_id": self.position_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "borrower": self.borrower,
            "collateral_token": self.collateral_token,
            "collateral_amount": str(self.collateral_amount),
            "collateral_value_usd": str(self.collateral_value_usd),
            "debt_token": self.debt_token,
            "debt_amount": str(self.debt_amount),
            "debt_value_usd": str(self.debt_value_usd),
            "interest_rate_mode": self.interest_rate_mode.value,
            "current_interest_rate": str(self.current_interest_rate),
            "liquidation_threshold": str(self.liquidation_threshold),
            "health_factor": str(self.health_factor),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class BorrowQuote:
    """Devis d'emprunt"""
    quote_id: str
    protocol: BorrowProtocol
    chain: str
    collateral_token: str
    collateral_amount: Decimal
    debt_token: str
    debt_amount: Decimal
    max_borrowable: Decimal
    interest_rate: Decimal
    interest_rate_mode: InterestRateMode
    liquidation_threshold: Decimal
    estimated_health_factor: Decimal
    fees: Decimal
    estimated_time: int  # secondes
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "collateral_token": self.collateral_token,
            "collateral_amount": str(self.collateral_amount),
            "debt_token": self.debt_token,
            "debt_amount": str(self.debt_amount),
            "max_borrowable": str(self.max_borrowable),
            "interest_rate": str(self.interest_rate),
            "interest_rate_mode": self.interest_rate_mode.value,
            "liquidation_threshold": str(self.liquidation_threshold),
            "estimated_health_factor": str(self.estimated_health_factor),
            "fees": str(self.fees),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
        }


@dataclass
class BorrowRequest:
    """Requête d'emprunt"""
    request_id: str
    protocol: BorrowProtocol
    chain: str
    collateral_token: str
    collateral_amount: Decimal
    debt_token: str
    debt_amount: Decimal
    borrower: str
    interest_rate_mode: InterestRateMode = InterestRateMode.VARIABLE
    use_collateral_as_repay: bool = False
    slippage_tolerance: Decimal = Decimal("0.005")
    deadline: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "protocol": self.protocol.value,
            "chain": self.chain,
            "collateral_token": self.collateral_token,
            "collateral_amount": str(self.collateral_amount),
            "debt_token": self.debt_token,
            "debt_amount": str(self.debt_amount),
            "borrower": self.borrower,
            "interest_rate_mode": self.interest_rate_mode.value,
            "use_collateral_as_repay": self.use_collateral_as_repay,
            "slippage_tolerance": str(self.slippage_tolerance),
            "deadline": self.deadline,
        }


@dataclass
class BorrowResult:
    """Résultat d'emprunt"""
    result_id: str
    request_id: str
    position_id: str
    protocol: BorrowProtocol
    chain: str
    tx_hash: str
    status: BorrowStatus
    collateral_amount: Decimal
    debt_amount: Decimal
    interest_rate: Decimal
    health_factor: Decimal
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
            "collateral_amount": str(self.collateral_amount),
            "debt_amount": str(self.debt_amount),
            "interest_rate": str(self.interest_rate),
            "health_factor": str(self.health_factor),
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CONFIGURATION DES PROTOCOLES
# ============================================================

PROTOCOL_CONFIGS = {
    BorrowProtocol.AAVE_V3: {
        "name": "Aave V3",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism", "avalanche", "base"],
        "supported_collateral": ["ETH", "WETH", "USDC", "USDT", "DAI", "WBTC", "MATIC", "AVAX"],
        "supported_debt": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
        "min_collateral": Decimal("0.001"),
        "min_debt": Decimal("0.001"),
        "liquidation_threshold": Decimal("0.8"),
        "ltv": Decimal("0.7"),
        "health_factor_alert": Decimal("1.2"),
        "health_factor_critical": Decimal("1.05"),
    },
    BorrowProtocol.COMPOUND_V3: {
        "name": "Compound V3",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism"],
        "supported_collateral": ["ETH", "USDC", "WBTC"],
        "supported_debt": ["USDC"],
        "min_collateral": Decimal("0.01"),
        "min_debt": Decimal("1"),
        "liquidation_threshold": Decimal("0.85"),
        "ltv": Decimal("0.75"),
        "health_factor_alert": Decimal("1.3"),
        "health_factor_critical": Decimal("1.1"),
    },
    BorrowProtocol.SPARK: {
        "name": "Spark",
        "chains": ["ethereum"],
        "supported_collateral": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
        "supported_debt": ["DAI"],
        "min_collateral": Decimal("0.001"),
        "min_debt": Decimal("1"),
        "liquidation_threshold": Decimal("0.78"),
        "ltv": Decimal("0.68"),
        "health_factor_alert": Decimal("1.25"),
        "health_factor_critical": Decimal("1.08"),
    },
    BorrowProtocol.MORPHO: {
        "name": "Morpho",
        "chains": ["ethereum", "polygon", "arbitrum", "optimism"],
        "supported_collateral": ["ETH", "USDC", "USDT", "DAI", "WBTC"],
        "supported_debt": ["ETH", "USDC", "USDT", "DAI"],
        "min_collateral": Decimal("0.001"),
        "min_debt": Decimal("0.001"),
        "liquidation_threshold": Decimal("0.82"),
        "ltv": Decimal("0.72"),
        "health_factor_alert": Decimal("1.15"),
        "health_factor_critical": Decimal("1.02"),
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BorrowingManager:
    """
    Gestionnaire d'emprunts DeFi
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
        Initialise le gestionnaire d'emprunts

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
        self._positions: Dict[str, BorrowPosition] = {}
        self._quotes_cache: Dict[str, Tuple[float, BorrowQuote]] = {}
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

        # Chargement des positions
        self._load_positions()

        logger.info("BorrowingManager initialisé avec succès")

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
        protocol: BorrowProtocol,
        chain: str,
        collateral_token: str,
        collateral_amount: Decimal,
        debt_token: str,
        debt_amount: Decimal,
        interest_rate_mode: InterestRateMode = InterestRateMode.VARIABLE,
        force_refresh: bool = False,
        **kwargs,
    ) -> BorrowQuote:
        """
        Obtient un devis d'emprunt

        Args:
            protocol: Protocole
            chain: Chaîne
            collateral_token: Token de collatéral
            collateral_amount: Montant de collatéral
            debt_token: Token de dette
            debt_amount: Montant de dette
            interest_rate_mode: Mode de taux
            force_refresh: Forcer le rafraîchissement
            **kwargs: Arguments additionnels

        Returns:
            Devis d'emprunt
        """
        cache_key = f"{protocol.value}:{chain}:{collateral_token}:{debt_token}:{collateral_amount}:{debt_amount}"

        if not force_refresh and cache_key in self._quotes_cache:
            cached_time, quote = self._quotes_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return quote

        try:
            # Vérification du protocole
            protocol_config = PROTOCOL_CONFIGS.get(protocol)
            if not protocol_config:
                raise DeFiError(f"Protocole {protocol.value} non supporté")

            # Vérification du collatéral
            if collateral_token not in protocol_config["supported_collateral"]:
                raise DeFiError(
                    f"Collatéral {collateral_token} non supporté par {protocol.value}"
                )

            # Vérification de la dette
            if debt_token not in protocol_config["supported_debt"]:
                raise DeFiError(
                    f"Dette {debt_token} non supportée par {protocol.value}"
                )

            # Vérification des montants
            if collateral_amount < protocol_config["min_collateral"]:
                raise DeFiError(
                    f"Collatéral minimum: {protocol_config['min_collateral']}"
                )

            if debt_amount < protocol_config["min_debt"]:
                raise DeFiError(
                    f"Dette minimum: {protocol_config['min_debt']}"
                )

            # Calcul du montant maximum empruntable
            max_borrowable = await self._calculate_max_borrowable(
                protocol, chain, collateral_token, collateral_amount, debt_token
            )

            if debt_amount > max_borrowable:
                raise DeFiError(
                    f"Montant de dette {debt_amount} dépasse le maximum {max_borrowable}"
                )

            # Obtention du taux d'intérêt
            interest_rate = await self._get_interest_rate(
                protocol, chain, debt_token, interest_rate_mode
            )

            # Estimation du health factor
            health_factor = await self._estimate_health_factor(
                protocol, collateral_amount, debt_amount, collateral_token, debt_token
            )

            # Calcul des frais
            fees = await self._calculate_fees(protocol, chain, debt_amount)

            # Création du devis
            quote = BorrowQuote(
                quote_id=f"bq_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                chain=chain,
                collateral_token=collateral_token,
                collateral_amount=collateral_amount,
                debt_token=debt_token,
                debt_amount=debt_amount,
                max_borrowable=max_borrowable,
                interest_rate=interest_rate,
                interest_rate_mode=interest_rate_mode,
                liquidation_threshold=protocol_config["liquidation_threshold"],
                estimated_health_factor=health_factor,
                fees=fees,
                estimated_time=await self._estimate_time(protocol, chain),
                confidence=await self._calculate_confidence(protocol),
                metadata=kwargs,
            )

            # Mise en cache
            self._quotes_cache[cache_key] = (time.time(), quote)

            # Métriques
            self.metrics.record_gauge(
                "borrowing_quote_health_factor",
                float(health_factor),
                {"protocol": protocol.value, "chain": chain},
            )

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis: {e}")
            raise DeFiError(f"Erreur d'obtention du devis: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_borrow(
        self,
        request: BorrowRequest,
    ) -> BorrowResult:
        """
        Exécute un emprunt

        Args:
            request: Requête d'emprunt

        Returns:
            Résultat d'emprunt
        """
        logger.info(
            f"Exécution d'emprunt: {request.debt_amount} {request.debt_token} "
            f"avec collatéral {request.collateral_amount} {request.collateral_token}"
        )

        try:
            # Validation
            await self._validate_borrow_request(request)

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(request.borrower)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {request.borrower}")

            # Obtention du devis
            quote = await self.get_quote(
                protocol=request.protocol,
                chain=request.chain,
                collateral_token=request.collateral_token,
                collateral_amount=request.collateral_amount,
                debt_token=request.debt_token,
                debt_amount=request.debt_amount,
                interest_rate_mode=request.interest_rate_mode,
            )

            # Récupération de l'instance du protocole
            protocol_instance = await self._get_protocol_instance(request.protocol, request.chain)
            if not protocol_instance:
                raise DeFiError(f"Instance de {request.protocol.value} non trouvée")

            # Exécution via le protocole
            tx_hash = await protocol_instance.execute_action(
                action="borrow",
                token=request.debt_token,
                amount=request.debt_amount,
                address=request.borrower,
                collateral_token=request.collateral_token,
                collateral_amount=request.collateral_amount,
                interest_rate_mode=request.interest_rate_mode,
            )

            # Création de la position
            position = BorrowPosition(
                position_id=f"bp_{uuid.uuid4().hex[:12]}",
                protocol=request.protocol,
                chain=request.chain,
                borrower=request.borrower,
                collateral_token=request.collateral_token,
                collateral_amount=request.collateral_amount,
                collateral_value_usd=await self._get_token_value(
                    request.collateral_token, request.collateral_amount
                ),
                debt_token=request.debt_token,
                debt_amount=request.debt_amount,
                debt_value_usd=await self._get_token_value(
                    request.debt_token, request.debt_amount
                ),
                interest_rate_mode=request.interest_rate_mode,
                current_interest_rate=quote.interest_rate,
                liquidation_threshold=quote.liquidation_threshold,
                health_factor=quote.estimated_health_factor,
                status=BorrowStatus.ACTIVE,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            self._positions[position.position_id] = position

            # Résultat
            result = BorrowResult(
                result_id=f"br_{uuid.uuid4().hex[:12]}",
                request_id=request.request_id,
                position_id=position.position_id,
                protocol=request.protocol,
                chain=request.chain,
                tx_hash=tx_hash,
                status=BorrowStatus.ACTIVE,
                collateral_amount=request.collateral_amount,
                debt_amount=request.debt_amount,
                interest_rate=quote.interest_rate,
                health_factor=quote.estimated_health_factor,
                timestamp=datetime.now(),
            )

            # Métriques
            self.metrics.record_increment(
                "borrowing_executed",
                1,
                {
                    "protocol": request.protocol.value,
                    "chain": request.chain,
                    "debt_token": request.debt_token,
                },
            )

            logger.info(f"Emprunt exécuté: {result.result_id}")
            return result

        except Exception as e:
            logger.error(f"Erreur d'exécution d'emprunt: {e}")
            self.metrics.record_increment(
                "borrowing_failed",
                1,
                {
                    "protocol": request.protocol.value,
                    "chain": request.chain,
                    "error": str(e)[:50],
                },
            )
            raise DeFiError(f"Erreur d'exécution d'emprunt: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def repay(
        self,
        position_id: str,
        amount: Optional[Decimal] = None,
        use_collateral: bool = False,
    ) -> str:
        """
        Rembourse un emprunt

        Args:
            position_id: ID de la position
            amount: Montant à rembourser
            use_collateral: Utiliser le collatéral pour rembourser

        Returns:
            Hash de la transaction
        """
        logger.info(f"Remboursement de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.status != BorrowStatus.ACTIVE:
                raise DeFiError(f"Position {position_id} n'est pas active")

            # Montant à rembourser
            repay_amount = amount or position.debt_amount

            if repay_amount > position.debt_amount:
                raise DeFiError(
                    f"Montant {repay_amount} dépasse la dette {position.debt_amount}"
                )

            # Récupération du protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(position.borrower)
            if not wallet:
                raise DeFiError(f"Wallet non trouvé: {position.borrower}")

            # Exécution du remboursement
            if use_collateral:
                tx_hash = await protocol_instance.execute_action(
                    action="repay_with_collateral",
                    token=position.debt_token,
                    amount=repay_amount,
                    address=position.borrower,
                    collateral_token=position.collateral_token,
                )
            else:
                tx_hash = await protocol_instance.execute_action(
                    action="repay",
                    token=position.debt_token,
                    amount=repay_amount,
                    address=position.borrower,
                )

            # Mise à jour de la position
            position.debt_amount -= repay_amount
            position.updated_at = datetime.now()

            if position.debt_amount <= Decimal("0.001"):
                position.status = BorrowStatus.REPAID

            # Métriques
            self.metrics.record_increment(
                "borrowing_repaid",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                },
            )

            logger.info(f"Remboursement effectué: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de remboursement: {e}")
            raise DeFiError(f"Erreur de remboursement: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_positions(self, address: str) -> List[BorrowPosition]:
        """
        Obtient les positions d'emprunt d'un utilisateur

        Args:
            address: Adresse de l'utilisateur

        Returns:
            Liste des positions
        """
        return [
            pos for pos in self._positions.values()
            if pos.borrower == address
        ]

    async def get_position(self, position_id: str) -> Optional[BorrowPosition]:
        """
        Obtient une position d'emprunt

        Args:
            position_id: ID de la position

        Returns:
            Position ou None
        """
        return self._positions.get(position_id)

    async def liquidate_position(
        self,
        position_id: str,
        liquidator: str,
        amount: Optional[Decimal] = None,
    ) -> str:
        """
        Liquide une position

        Args:
            position_id: ID de la position
            liquidator: Adresse du liquidateur
            amount: Montant à liquider

        Returns:
            Hash de la transaction
        """
        logger.info(f"Liquidation de la position {position_id}")

        try:
            position = self._positions.get(position_id)
            if not position:
                raise DeFiError(f"Position {position_id} non trouvée")

            if position.health_factor > Decimal("1.0"):
                raise DeFiError(
                    f"Position non liquidable (HF: {position.health_factor})"
                )

            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if not protocol_instance:
                raise DeFiError(f"Instance de {position.protocol.value} non trouvée")

            # Exécution de la liquidation
            tx_hash = await protocol_instance.execute_action(
                action="liquidate",
                token=position.debt_token,
                amount=amount or position.debt_amount,
                address=liquidator,
                collateral_token=position.collateral_token,
                borrower=position.borrower,
            )

            # Mise à jour de la position
            position.status = BorrowStatus.LIQUIDATED
            position.updated_at = datetime.now()

            # Métriques
            self.metrics.record_increment(
                "borrowing_liquidated",
                1,
                {
                    "protocol": position.protocol.value,
                    "chain": position.chain,
                },
            )

            logger.info(f"Liquidation effectuée: {tx_hash}")
            return tx_hash

        except Exception as e:
            logger.error(f"Erreur de liquidation: {e}")
            raise DeFiError(f"Erreur de liquidation: {e}")

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
        logger.info("Démarrage du monitoring des positions d'emprunt")

        while True:
            try:
                for position_id, position in list(self._positions.items()):
                    if position.status != BorrowStatus.ACTIVE:
                        continue

                    # Mise à jour du health factor
                    updated_position = await self._update_position_health(position_id)
                    if updated_position:
                        position = updated_position

                    # Vérification des alertes
                    if position.health_factor < Decimal("1.2"):
                        await self._send_health_alert(position)

                    if position.health_factor < Decimal("1.05"):
                        logger.warning(
                            f"Position {position_id} en danger de liquidation "
                            f"(HF: {position.health_factor})"
                        )

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _validate_borrow_request(self, request: BorrowRequest) -> None:
        """Valide une requête d'emprunt"""
        if request.collateral_amount <= Decimal("0"):
            raise ValidationError("Le collatéral doit être positif")

        if request.debt_amount <= Decimal("0"):
            raise ValidationError("La dette doit être positive")

        # Vérification du protocole
        protocol_config = PROTOCOL_CONFIGS.get(request.protocol)
        if not protocol_config:
            raise ValidationError(f"Protocole {request.protocol.value} non supporté")

        # Vérification de la chaîne
        if request.chain not in protocol_config["chains"]:
            raise ValidationError(
                f"Chaîne {request.chain} non supportée par {request.protocol.value}"
            )

        # Vérification des tokens
        if request.collateral_token not in protocol_config["supported_collateral"]:
            raise ValidationError(
                f"Collatéral {request.collateral_token} non supporté"
            )

        if request.debt_token not in protocol_config["supported_debt"]:
            raise ValidationError(
                f"Dette {request.debt_token} non supportée"
            )

        # Vérification des montants minimaux
        if request.collateral_amount < protocol_config["min_collateral"]:
            raise ValidationError(
                f"Collatéral minimum: {protocol_config['min_collateral']}"
            )

        if request.debt_amount < protocol_config["min_debt"]:
            raise ValidationError(
                f"Dette minimum: {protocol_config['min_debt']}"
            )

    async def _calculate_max_borrowable(
        self,
        protocol: BorrowProtocol,
        chain: str,
        collateral_token: str,
        collateral_amount: Decimal,
        debt_token: str,
    ) -> Decimal:
        """Calcule le montant maximum empruntable"""
        protocol_config = PROTOCOL_CONFIGS.get(protocol)

        # Valeur du collatéral en USD
        collateral_value = await self._get_token_value(
            collateral_token, collateral_amount
        )

        # LTV
        ltv = protocol_config["ltv"]

        # Montant maximum empruntable
        max_borrowable = collateral_value * ltv

        # Conversion en token de dette
        debt_value = await self._get_token_value(debt_token, Decimal("1"))
        if debt_value > 0:
            max_borrowable = max_borrowable / debt_value

        return max_borrowable

    async def _get_token_value(self, token: str, amount: Decimal) -> Decimal:
        """Obtient la valeur USD d'un token"""
        # Dans la réalité, on utiliserait des oracles de prix
        # Simulé pour l'exemple
        prices = {
            "ETH": Decimal("3000"),
            "WETH": Decimal("3000"),
            "USDC": Decimal("1"),
            "USDT": Decimal("1"),
            "DAI": Decimal("1"),
            "WBTC": Decimal("60000"),
            "MATIC": Decimal("0.7"),
            "AVAX": Decimal("40"),
        }
        price = prices.get(token, Decimal("1"))
        return amount * price

    async def _get_interest_rate(
        self,
        protocol: BorrowProtocol,
        chain: str,
        debt_token: str,
        mode: InterestRateMode,
    ) -> Decimal:
        """Obtient le taux d'intérêt"""
        # Simulé - dans la réalité, on interrogerait les contrats
        base_rates = {
            BorrowProtocol.AAVE_V3: {
                "ETH": {"variable": Decimal("0.02"), "stable": Decimal("0.03")},
                "USDC": {"variable": Decimal("0.04"), "stable": Decimal("0.05")},
                "USDT": {"variable": Decimal("0.04"), "stable": Decimal("0.05")},
                "DAI": {"variable": Decimal("0.03"), "stable": Decimal("0.04")},
                "WBTC": {"variable": Decimal("0.025"), "stable": Decimal("0.035")},
            },
            BorrowProtocol.COMPOUND_V3: {
                "USDC": {"variable": Decimal("0.05")},
            },
            BorrowProtocol.SPARK: {
                "DAI": {"variable": Decimal("0.03"), "stable": Decimal("0.04")},
            },
        }

        protocol_rates = base_rates.get(protocol, {})
        token_rates = protocol_rates.get(debt_token, {})
        rate_key = "variable" if mode == InterestRateMode.VARIABLE else "stable"
        return token_rates.get(rate_key, Decimal("0.05"))

    async def _estimate_health_factor(
        self,
        protocol: BorrowProtocol,
        collateral_amount: Decimal,
        debt_amount: Decimal,
        collateral_token: str,
        debt_token: str,
    ) -> Decimal:
        """Estime le health factor"""
        # Valeur du collatéral
        collateral_value = await self._get_token_value(
            collateral_token, collateral_amount
        )

        # Valeur de la dette
        debt_value = await self._get_token_value(debt_token, debt_amount)

        # Seuil de liquidation
        protocol_config = PROTOCOL_CONFIGS.get(protocol)
        liquidation_threshold = protocol_config["liquidation_threshold"]

        if debt_value > 0:
            health_factor = (collateral_value * liquidation_threshold) / debt_value
        else:
            health_factor = Decimal("999")

        return health_factor

    async def _calculate_fees(
        self,
        protocol: BorrowProtocol,
        chain: str,
        amount: Decimal,
    ) -> Decimal:
        """Calcule les frais"""
        # Frais de gaz estimés
        gas_fee = Decimal("0.001")  # Simulé

        # Frais de protocole
        protocol_fee = amount * Decimal("0.0005")  # 0.05%

        return gas_fee + protocol_fee

    async def _estimate_time(
        self,
        protocol: BorrowProtocol,
        chain: str,
    ) -> int:
        """Estime le temps de transaction"""
        base_time = 60  # secondes

        # Ajustement selon la chaîne
        chain_times = {
            "ethereum": 60,
            "polygon": 30,
            "arbitrum": 20,
            "optimism": 20,
            "avalanche": 20,
            "base": 20,
        }

        return chain_times.get(chain, base_time)

    async def _calculate_confidence(
        self,
        protocol: BorrowProtocol,
    ) -> float:
        """Calcule le niveau de confiance"""
        base_confidence = {
            BorrowProtocol.AAVE_V3: 0.98,
            BorrowProtocol.COMPOUND_V3: 0.97,
            BorrowProtocol.SPARK: 0.95,
            BorrowProtocol.MORPHO: 0.94,
        }.get(protocol, 0.95)

        return base_confidence

    async def _get_protocol_instance(
        self,
        protocol: BorrowProtocol,
        chain: str,
    ) -> Optional[Any]:
        """Obtient une instance du protocole"""
        key = f"{protocol.value}_{chain}"
        return self.protocol_instances.get(key)

    async def _update_position_health(
        self,
        position_id: str,
    ) -> Optional[BorrowPosition]:
        """Met à jour le health factor d'une position"""
        position = self._positions.get(position_id)
        if not position:
            return None

        try:
            # Mise à jour via le protocole
            protocol_instance = await self._get_protocol_instance(
                position.protocol, position.chain
            )
            if protocol_instance:
                # Récupération de la position à jour
                updated_positions = await protocol_instance.get_positions(
                    position.borrower
                )

                for pos in updated_positions:
                    if pos.position_type == PositionType.DEBT:
                        # Mise à jour du health factor
                        health_factor = await self._estimate_health_factor(
                            position.protocol,
                            position.collateral_amount,
                            position.debt_amount,
                            position.collateral_token,
                            position.debt_token,
                        )
                        position.health_factor = health_factor
                        position.updated_at = datetime.now()

            return position

        except Exception as e:
            logger.warning(f"Erreur de mise à jour de la position {position_id}: {e}")
            return position

    async def _send_health_alert(self, position: BorrowPosition) -> None:
        """Envoie une alerte de santé"""
        alert = {
            "type": "borrowing_health_warning",
            "position_id": position.position_id,
            "protocol": position.protocol.value,
            "chain": position.chain,
            "borrower": position.borrower,
            "health_factor": str(position.health_factor),
            "debt_amount": str(position.debt_amount),
            "collateral_amount": str(position.collateral_amount),
            "timestamp": datetime.now().isoformat(),
            "severity": "critical" if position.health_factor < Decimal("1.1") else "warning",
        }

        logger.warning(f"Alerte d'emprunt: {alert}")

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        total_positions = len(self._positions)
        active_positions = sum(1 for p in self._positions.values() if p.status == BorrowStatus.ACTIVE)
        liquidated_positions = sum(1 for p in self._positions.values() if p.status == BorrowStatus.LIQUIDATED)

        total_debt = sum(p.debt_value_usd for p in self._positions.values())
        total_collateral = sum(p.collateral_value_usd for p in self._positions.values())

        return {
            "total_positions": total_positions,
            "active_positions": active_positions,
            "liquidated_positions": liquidated_positions,
            "total_debt_usd": str(total_debt),
            "total_collateral_usd": str(total_collateral),
            "average_health_factor": self._calculate_avg_health_factor(),
            "cache_size": len(self._quotes_cache),
            "active_operations": len(self._active_operations),
        }

    def _calculate_avg_health_factor(self) -> float:
        """Calcule le health factor moyen"""
        active_positions = [
            p for p in self._positions.values()
            if p.status == BorrowStatus.ACTIVE
        ]

        if not active_positions:
            return 0.0

        total = sum(float(p.health_factor) for p in active_positions)
        return total / len(active_positions)

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
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BorrowingManager...")

        self._quotes_cache.clear()
        self._positions.clear()
        self._active_operations.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_borrowing_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> BorrowingManager:
    """
    Crée une instance de BorrowingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de BorrowingManager
    """
    return BorrowingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de BorrowingManager"""
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
        async def get_positions(self, address):
            return []

        async def execute_action(self, action, **kwargs):
            return f"0x{hash(str(kwargs)):064x}"

    protocol_instances = {
        "aave_v3_ethereum": SimpleProtocol(),
    }

    # Création du gestionnaire
    manager = create_borrowing_manager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
    )

    # Obtention d'un devis
    quote = await manager.get_quote(
        protocol=BorrowProtocol.AAVE_V3,
        chain="ethereum",
        collateral_token="ETH",
        collateral_amount=Decimal("1"),
        debt_token="USDC",
        debt_amount=Decimal("1000"),
    )

    print(f"Devis: {quote.to_dict()}")

    # Exécution d'un emprunt
    request = BorrowRequest(
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        protocol=BorrowProtocol.AAVE_V3,
        chain="ethereum",
        collateral_token="ETH",
        collateral_amount=Decimal("1"),
        debt_token="USDC",
        debt_amount=Decimal("1000"),
        borrower="0x1234567890123456789012345678901234567890",
    )

    result = await manager.execute_borrow(request)
    print(f"Résultat: {result.to_dict()}")

    # Remboursement
    if result.position_id:
        tx_hash = await manager.repay(result.position_id)
        print(f"Remboursement: {tx_hash}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
