# blockchain/bridges/bridge_fees.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Gestion des Frais de Bridge

Ce module implémente un système complet de calcul, d'optimisation et de gestion
des frais pour les opérations de bridge cross-chain, incluant l'estimation,
la comparaison, l'optimisation et le suivi des frais.

Fonctionnalités principales:
- Calcul des frais de bridge (protocole, gaz, slippage)
- Optimisation des frais multi-protocoles
- Estimation dynamique des coûts
- Suivi historique des frais
- Alertes sur les variations de frais
- Comparaison des coûts entre protocoles
- Gestion des frais de priorité
- Support des frais L1/L2
- Analytics des coûts
- Prédiction des frais
"""

import asyncio
import hashlib
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
from collections import defaultdict, deque
from functools import lru_cache, wraps
import statistics

import aiohttp

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, FeeError, ValidationError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, FeeError, ValidationError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class FeeType(Enum):
    """Types de frais"""
    BRIDGE = "bridge"  # Frais de protocole
    GAS = "gas"  # Frais de gaz
    SLIPPAGE = "slippage"  # Frais de slippage
    PRIORITY = "priority"  # Frais de priorité
    L1 = "l1"  # Frais L1 (Optimism, Arbitrum)
    L2 = "l2"  # Frais L2
    WITHDRAWAL = "withdrawal"  # Frais de retrait
    DEPOSIT = "deposit"  # Frais de dépôt
    EXECUTION = "execution"  # Frais d'exécution
    TOTAL = "total"  # Frais totaux


class FeeTier(Enum):
    """Niveaux de frais"""
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    PREMIUM = "premium"


class FeeOptimizationStrategy(Enum):
    """Stratégies d'optimisation"""
    CHEAPEST = "cheapest"  # Le moins cher
    FASTEST = "fastest"  # Le plus rapide
    BALANCED = "balanced"  # Équilibré
    SECURE = "secure"  # Le plus sécurisé
    CUSTOM = "custom"  # Personnalisé


@dataclass
class BridgeFee:
    """Frais de bridge"""
    fee_id: str
    fee_type: FeeType
    protocol: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    percentage: Decimal
    timestamp: datetime
    estimated: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "fee_id": self.fee_id,
            "fee_type": self.fee_type.value,
            "protocol": self.protocol,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "percentage": str(self.percentage),
            "timestamp": self.timestamp.isoformat(),
            "estimated": self.estimated,
        }

    def to_decimal(self) -> Decimal:
        """Convertit le montant en Decimal"""
        return self.amount


@dataclass
class FeeQuote:
    """Devis de frais"""
    quote_id: str
    protocol: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    amount: Decimal
    fees: List[BridgeFee]
    total_fee: Decimal
    total_percentage: Decimal
    estimated_time: int  # secondes
    confidence: float
    tier: FeeTier
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "quote_id": self.quote_id,
            "protocol": self.protocol,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "amount": str(self.amount),
            "fees": [f.to_dict() for f in self.fees],
            "total_fee": str(self.total_fee),
            "total_percentage": str(self.total_percentage),
            "estimated_time": self.estimated_time,
            "confidence": self.confidence,
            "tier": self.tier.value,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class FeeStats:
    """Statistiques de frais"""
    protocol: str
    chain_from: str
    chain_to: str
    token_from: str
    token_to: str
    timeframe: int  # secondes
    count: int
    avg_fee: Decimal
    min_fee: Decimal
    max_fee: Decimal
    median_fee: Decimal
    std_dev: Decimal
    avg_percentage: Decimal
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "chain_from": self.chain_from,
            "chain_to": self.chain_to,
            "token_from": self.token_from,
            "token_to": self.token_to,
            "timeframe": self.timeframe,
            "count": self.count,
            "avg_fee": str(self.avg_fee),
            "min_fee": str(self.min_fee),
            "max_fee": str(self.max_fee),
            "median_fee": str(self.median_fee),
            "std_dev": str(self.std_dev),
            "avg_percentage": str(self.avg_percentage),
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeFeeManager:
    """
    Gestionnaire de frais pour les bridges cross-chain
    """

    # Frais de base par protocole (en pourcentage)
    BASE_FEES = {
        "layerzero": Decimal("0.0005"),  # 0.05%
        "wormhole": Decimal("0.0003"),  # 0.03%
        "cctp": Decimal("0.0001"),  # 0.01%
        "optimism_native": Decimal("0.0002"),  # 0.02%
        "polygon_pos": Decimal("0.0002"),  # 0.02%
        "solana_wormhole": Decimal("0.0003"),  # 0.03%
        "debridge": Decimal("0.0004"),  # 0.04%
        "axelar": Decimal("0.0006"),  # 0.06%
        "across": Decimal("0.0003"),  # 0.03%
        "hop": Decimal("0.0005"),  # 0.05%
        "stargate": Decimal("0.0004"),  # 0.04%
        "connext": Decimal("0.0005"),  # 0.05%
        "synapse": Decimal("0.0004"),  # 0.04%
    }

    # Frais de gaz de base (en USD)
    GAS_FEES = {
        "ethereum": Decimal("5"),  # ~$5
        "polygon": Decimal("0.1"),  # ~$0.10
        "arbitrum": Decimal("0.5"),  # ~$0.50
        "optimism": Decimal("0.5"),  # ~$0.50
        "base": Decimal("0.3"),  # ~$0.30
        "solana": Decimal("0.01"),  # ~$0.01
        "avalanche": Decimal("0.2"),  # ~$0.20
        "bsc": Decimal("0.2"),  # ~$0.20
    }

    # Multiplicateurs de frais de priorité
    PRIORITY_MULTIPLIERS = {
        FeeTier.LOW: Decimal("0.8"),
        FeeTier.STANDARD: Decimal("1.0"),
        FeeTier.HIGH: Decimal("1.5"),
        FeeTier.PREMIUM: Decimal("2.0"),
    }

    def __init__(
        self,
        config: Dict[str, Any],
        bridge_manager: BridgeManager,
        web3_providers: Optional[Dict[str, Any]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 60,  # 1 minute
        price_feeds: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialise le gestionnaire de frais

        Args:
            config: Configuration
            bridge_manager: Gestionnaire de bridges
            web3_providers: Providers Web3 par chaîne
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
            price_feeds: Flux de prix personnalisés
        """
        self.config = config
        self.bridge_manager = bridge_manager
        self.web3_providers = web3_providers or {}
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl
        self.price_feeds = price_feeds or {}

        # États internes
        self._fee_cache: Dict[str, Tuple[float, FeeQuote]] = {}
        self._stats_cache: Dict[str, Tuple[float, FeeStats]] = {}
        self._historical_fees: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._fee_history: List[BridgeFee] = []
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des prix
        self._price_cache: Dict[str, Tuple[float, Decimal]] = {}
        self._price_update_interval = 60  # secondes

        # Configuration des seuils d'alerte
        self._alert_thresholds = self._load_alert_thresholds()

        # Statistiques
        self._fee_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        logger.info("BridgeFeeManager initialisé avec succès")

    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Charge les seuils d'alerte pour les frais"""
        return self.config.get("alert_thresholds", {
            "fee_increase": Decimal("0.3"),  # 30% d'augmentation
            "fee_decrease": Decimal("0.3"),  # 30% de diminution
            "gas_spike": Decimal("2.0"),  # 2x le prix normal
            "min_volume": Decimal("100"),  # Volume minimum pour les alertes
        })

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_fee_quote(
        self,
        protocol: str,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        tier: FeeTier = FeeTier.STANDARD,
        force_refresh: bool = False,
        **kwargs,
    ) -> FeeQuote:
        """
        Obtient un devis de frais pour un bridge

        Args:
            protocol: Protocole de bridge
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant
            tier: Niveau de frais
            force_refresh: Forcer le rafraîchissement
            **kwargs: Arguments additionnels

        Returns:
            Devis de frais
        """
        quote_key = f"{protocol}:{chain_from}:{chain_to}:{token_from}:{token_to}:{amount}:{tier.value}"

        if not force_refresh and quote_key in self._fee_cache:
            cached_time, quote = self._fee_cache[quote_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug("Devis de frais retourné du cache")
                return quote

        try:
            # Vérification du protocole
            bridge_config = await self.bridge_manager.get_bridge_config(protocol)
            if not bridge_config:
                raise FeeError(f"Protocole {protocol} non trouvé")

            # Vérification des tokens
            if token_from not in bridge_config.supported_tokens:
                raise FeeError(f"Token {token_from} non supporté par {protocol}")

            # Calcul des différents frais
            fees = []

            # 1. Frais de protocole
            protocol_fee = await self._calculate_protocol_fee(
                protocol, amount, tier
            )
            fees.append(protocol_fee)

            # 2. Frais de gaz
            gas_fee = await self._calculate_gas_fee(
                protocol, chain_from, chain_to, amount, tier
            )
            fees.append(gas_fee)

            # 3. Frais de slippage (si applicable)
            if token_from != token_to:
                slippage_fee = await self._calculate_slippage_fee(
                    protocol, token_from, token_to, amount, tier
                )
                fees.append(slippage_fee)

            # 4. Frais de priorité (si demandé)
            if tier != FeeTier.STANDARD:
                priority_fee = await self._calculate_priority_fee(
                    protocol, tier, amount
                )
                fees.append(priority_fee)

            # 5. Frais L1/L2 (pour Optimism, Arbitrum)
            if chain_from in ["optimism", "arbitrum"]:
                l1_fee = await self._calculate_l1_fee(
                    protocol, chain_from, amount, tier
                )
                fees.append(l1_fee)

            # Calcul du total
            total_fee = sum(f.amount for f in fees)
            total_percentage = total_fee / amount * Decimal("100")

            # Estimation du temps
            estimated_time = await self._estimate_time(
                protocol, chain_from, chain_to, tier
            )

            # Niveau de confiance
            confidence = await self._calculate_confidence(
                protocol, amount, fees
            )

            # Création du devis
            quote = FeeQuote(
                quote_id=f"fq_{uuid.uuid4().hex[:8]}",
                protocol=protocol,
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                fees=fees,
                total_fee=total_fee,
                total_percentage=total_percentage,
                estimated_time=estimated_time,
                confidence=confidence,
                tier=tier,
                timestamp=datetime.now(),
                metadata=kwargs,
            )

            # Mise en cache
            self._fee_cache[quote_key] = (time.time(), quote)

            # Stockage historique
            self._fee_history.extend(fees)

            # Métriques
            self.metrics.record_gauge(
                "bridge_fee_quote",
                float(total_fee),
                {
                    "protocol": protocol,
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "token_from": token_from,
                    "token_to": token_to,
                    "tier": tier.value,
                },
            )

            # Vérification des alertes
            await self._check_fee_alerts(quote)

            return quote

        except Exception as e:
            logger.error(f"Erreur d'obtention du devis de frais: {e}")
            raise FeeError(f"Erreur d'obtention du devis de frais: {e}")

    @async_retry(max_attempts=2, initial_delay=0.5)
    async def compare_fees(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        tier: FeeTier = FeeTier.STANDARD,
        protocols: Optional[List[str]] = None,
    ) -> Dict[str, FeeQuote]:
        """
        Compare les frais entre plusieurs protocoles

        Args:
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant
            tier: Niveau de frais
            protocols: Liste des protocoles à comparer

        Returns:
            Dictionnaire des devis par protocole
        """
        logger.info(
            f"Comparaison des frais: {amount} {token_from} ({chain_from}) "
            f"-> {token_to} ({chain_to})"
        )

        try:
            # Sélection des protocoles
            if protocols is None:
                bridge_configs = await self.bridge_manager.get_all_bridges()
                protocols = [
                    config.protocol.value
                    for config in bridge_configs
                    if config.enabled
                    and config.chain == chain_from
                    and token_from in config.supported_tokens
                ]

            # Obtention des devis
            quotes = {}
            tasks = []

            for protocol in protocols:
                task = self.get_fee_quote(
                    protocol=protocol,
                    chain_from=chain_from,
                    chain_to=chain_to,
                    token_from=token_from,
                    token_to=token_to,
                    amount=amount,
                    tier=tier,
                    force_refresh=True,
                )
                tasks.append((protocol, task))

            # Exécution en parallèle
            results = await asyncio.gather(
                *[task for _, task in tasks],
                return_exceptions=True,
            )

            for (protocol, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning(f"Erreur pour {protocol}: {result}")
                    continue
                quotes[protocol] = result

            # Métriques
            self.metrics.record_gauge(
                "bridge_fee_comparison",
                len(quotes),
                {
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "token_from": token_from,
                    "token_to": token_to,
                },
            )

            return quotes

        except Exception as e:
            logger.error(f"Erreur de comparaison des frais: {e}")
            raise FeeError(f"Erreur de comparaison des frais: {e}")

    async def optimize_fees(
        self,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        strategy: FeeOptimizationStrategy = FeeOptimizationStrategy.BALANCED,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> FeeQuote:
        """
        Optimise les frais selon une stratégie

        Args:
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant
            strategy: Stratégie d'optimisation
            constraints: Contraintes additionnelles

        Returns:
            Devis optimisé
        """
        logger.info(
            f"Optimisation des frais: {amount} {token_from} ({chain_from}) "
            f"-> {token_to} ({chain_to}) avec stratégie {strategy.value}"
        )

        try:
            # Obtention de tous les devis
            quotes = await self.compare_fees(
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                amount=amount,
                protocols=None,
            )

            if not quotes:
                raise FeeError("Aucun devis disponible")

            # Filtrage selon les contraintes
            if constraints:
                quotes = self._apply_constraints(quotes, constraints)

            # Sélection selon la stratégie
            if strategy == FeeOptimizationStrategy.CHEAPEST:
                best_quote = min(quotes.values(), key=lambda q: q.total_fee)
            elif strategy == FeeOptimizationStrategy.FASTEST:
                best_quote = min(quotes.values(), key=lambda q: q.estimated_time)
            elif strategy == FeeOptimizationStrategy.SECURE:
                best_quote = max(quotes.values(), key=lambda q: q.confidence)
            elif strategy == FeeOptimizationStrategy.BALANCED:
                def score(q: FeeQuote) -> float:
                    fee_score = 1.0 - float(q.total_fee / Decimal("100"))
                    time_score = 1.0 - (q.estimated_time / 3600.0)
                    confidence_score = q.confidence
                    return fee_score * 0.4 + time_score * 0.3 + confidence_score * 0.3
                best_quote = max(quotes.values(), key=score)
            else:
                best_quote = min(quotes.values(), key=lambda q: q.total_fee)

            logger.info(
                f"Optimisation terminée: {best_quote.protocol} "
                f"avec {best_quote.total_fee} de frais"
            )

            return best_quote

        except Exception as e:
            logger.error(f"Erreur d'optimisation des frais: {e}")
            raise FeeError(f"Erreur d'optimisation des frais: {e}")

    async def get_fee_stats(
        self,
        protocol: str,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        timeframe: int = 86400,  # 24 heures
    ) -> FeeStats:
        """
        Obtient les statistiques de frais

        Args:
            protocol: Protocole
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            timeframe: Période en secondes

        Returns:
            Statistiques de frais
        """
        stats_key = f"{protocol}:{chain_from}:{chain_to}:{token_from}:{token_to}:{timeframe}"

        if stats_key in self._stats_cache:
            cached_time, stats = self._stats_cache[stats_key]
            if time.time() - cached_time < self.cache_ttl:
                return stats

        try:
            # Récupération des données historiques
            cutoff = datetime.now() - timedelta(seconds=timeframe)

            relevant_fees = [
                fee for fee in self._fee_history
                if fee.protocol == protocol
                and fee.chain_from == chain_from
                and fee.chain_to == chain_to
                and fee.token_from == token_from
                and fee.token_to == token_to
                and fee.timestamp >= cutoff
            ]

            if not relevant_fees:
                # Si pas de données, retourner des statistiques par défaut
                return FeeStats(
                    protocol=protocol,
                    chain_from=chain_from,
                    chain_to=chain_to,
                    token_from=token_from,
                    token_to=token_to,
                    timeframe=timeframe,
                    count=0,
                    avg_fee=Decimal("0"),
                    min_fee=Decimal("0"),
                    max_fee=Decimal("0"),
                    median_fee=Decimal("0"),
                    std_dev=Decimal("0"),
                    avg_percentage=Decimal("0"),
                    timestamp=datetime.now(),
                )

            # Calcul des statistiques
            fees = [f.amount for f in relevant_fees]
            percentages = [f.percentage for f in relevant_fees]

            count = len(fees)
            avg_fee = sum(fees) / count
            min_fee = min(fees)
            max_fee = max(fees)
            median_fee = sorted(fees)[count // 2]

            # Écart-type
            mean = float(avg_fee)
            variance = sum((float(f) - mean) ** 2 for f in fees) / count
            std_dev = Decimal(str(statistics.sqrt(variance)))

            avg_percentage = sum(percentages) / count

            stats = FeeStats(
                protocol=protocol,
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                timeframe=timeframe,
                count=count,
                avg_fee=avg_fee,
                min_fee=min_fee,
                max_fee=max_fee,
                median_fee=median_fee,
                std_dev=std_dev,
                avg_percentage=avg_percentage,
                timestamp=datetime.now(),
            )

            self._stats_cache[stats_key] = (time.time(), stats)

            return stats

        except Exception as e:
            logger.error(f"Erreur d'obtention des statistiques: {e}")
            raise FeeError(f"Erreur d'obtention des statistiques: {e}")

    async def predict_fees(
        self,
        protocol: str,
        chain_from: str,
        chain_to: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        timeframe: int = 3600,  # 1 heure
    ) -> Dict[str, Any]:
        """
        Prédit l'évolution des frais

        Args:
            protocol: Protocole
            chain_from: Chaîne source
            chain_to: Chaîne destination
            token_from: Token source
            token_to: Token destination
            amount: Montant
            timeframe: Période de prédiction

        Returns:
            Prédictions de frais
        """
        logger.info(f"Prédiction des frais pour {protocol}")

        try:
            # Obtention des données historiques
            stats = await self.get_fee_stats(
                protocol=protocol,
                chain_from=chain_from,
                chain_to=chain_to,
                token_from=token_from,
                token_to=token_to,
                timeframe=timeframe * 24,  # 24h de données
            )

            if stats.count < 10:
                return {
                    "status": "insufficient_data",
                    "message": "Pas assez de données pour prédire",
                    "current_fee": Decimal("0"),
                    "predicted_fee": Decimal("0"),
                    "confidence": 0.0,
                }

            # Calcul des tendances
            # Tendance simple: moyenne mobile
            fee_values = [f.amount for f in self._fee_history[:stats.count]]
            recent_avg = sum(fee_values[-10:]) / min(10, len(fee_values))
            historical_avg = stats.avg_fee

            # Variation
            trend = (recent_avg - historical_avg) / historical_avg

            # Facteurs externes (simulés)
            gas_factor = await self._get_gas_factor(chain_from)
            volume_factor = await self._get_volume_factor(protocol, chain_from)

            # Prédiction
            predicted_fee = recent_avg * (1 + trend * 0.5 + gas_factor * 0.3 + volume_factor * 0.2)

            # Seuil de confiance
            confidence = min(0.9, stats.count / 100) * (1 - abs(float(trend)) * 0.1)

            return {
                "status": "success",
                "current_fee": recent_avg,
                "predicted_fee": predicted_fee,
                "trend": float(trend),
                "gas_factor": float(gas_factor),
                "volume_factor": float(volume_factor),
                "confidence": max(0.1, min(0.95, confidence)),
                "timeframe": timeframe,
            }

        except Exception as e:
            logger.error(f"Erreur de prédiction des frais: {e}")
            return {
                "status": "error",
                "message": str(e),
                "current_fee": Decimal("0"),
                "predicted_fee": Decimal("0"),
                "confidence": 0.0,
            }

    # ============================================================
    # MÉTHODES DE CALCUL DES FRAIS
    # ============================================================

    async def _calculate_protocol_fee(
        self,
        protocol: str,
        amount: Decimal,
        tier: FeeTier,
    ) -> BridgeFee:
        """Calcule les frais de protocole"""
        # Frais de base
        base_percentage = self.BASE_FEES.get(protocol, Decimal("0.0005"))

        # Ajustement selon le tier
        multiplier = self.PRIORITY_MULTIPLIERS.get(tier, Decimal("1.0"))

        percentage = base_percentage * multiplier
        fee_amount = amount * percentage

        # Arrondi à 8 décimales
        fee_amount = fee_amount.quantize(Decimal("0.00000001"))

        return BridgeFee(
            fee_id=f"pf_{uuid.uuid4().hex[:8]}",
            fee_type=FeeType.BRIDGE,
            protocol=protocol,
            chain_from="",
            chain_to="",
            token_from="",
            token_to="",
            amount=fee_amount,
            percentage=percentage,
            timestamp=datetime.now(),
            estimated=True,
            metadata={"base_percentage": str(base_percentage), "multiplier": str(multiplier)},
        )

    async def _calculate_gas_fee(
        self,
        protocol: str,
        chain_from: str,
        chain_to: str,
        amount: Decimal,
        tier: FeeTier,
    ) -> BridgeFee:
        """Calcule les frais de gaz"""
        # Frais de gaz de base
        base_gas = self.GAS_FEES.get(chain_from, Decimal("1"))

        # Ajustement selon le montant (les gros montants peuvent nécessiter plus de gaz)
        gas_multiplier = Decimal("1.0")
        if amount > Decimal("100000"):
            gas_multiplier = Decimal("1.5")
        elif amount > Decimal("50000"):
            gas_multiplier = Decimal("1.2")

        # Ajustement selon le tier
        tier_multiplier = self.PRIORITY_MULTIPLIERS.get(tier, Decimal("1.0"))

        gas_fee = base_gas * gas_multiplier * tier_multiplier
        gas_fee = gas_fee.quantize(Decimal("0.0001"))

        # Conversion en pourcentage du montant
        percentage = gas_fee / amount if amount > 0 else Decimal("0")

        return BridgeFee(
            fee_id=f"gf_{uuid.uuid4().hex[:8]}",
            fee_type=FeeType.GAS,
            protocol=protocol,
            chain_from=chain_from,
            chain_to=chain_to,
            token_from="",
            token_to="",
            amount=gas_fee,
            percentage=percentage,
            timestamp=datetime.now(),
            estimated=True,
            metadata={"base_gas": str(base_gas), "gas_multiplier": str(gas_multiplier)},
        )

    async def _calculate_slippage_fee(
        self,
        protocol: str,
        token_from: str,
        token_to: str,
        amount: Decimal,
        tier: FeeTier,
    ) -> BridgeFee:
        """Calcule les frais de slippage"""
        # Slippage estimé selon les paires de tokens
        slippage_base = Decimal("0.002")  # 0.2%

        # Ajustement selon le tier
        multiplier = self.PRIORITY_MULTIPLIERS.get(tier, Decimal("1.0"))

        # Certaines paires sont plus volatiles
        volatile_pairs = [
            ("ETH", "BTC"),
            ("ETH", "SOL"),
            ("USDC", "USDT"),
        ]

        for pair in volatile_pairs:
            if (token_from == pair[0] and token_to == pair[1]) or \
               (token_from == pair[1] and token_to == pair[0]):
                slippage_base = Decimal("0.005")  # 0.5%
                break

        # Ajustement selon le montant
        if amount > Decimal("100000"):
            slippage_base *= Decimal("1.5")
        elif amount > Decimal("50000"):
            slippage_base *= Decimal("1.2")

        percentage = slippage_base * multiplier
        fee_amount = amount * percentage
        fee_amount = fee_amount.quantize(Decimal("0.00000001"))

        return BridgeFee(
            fee_id=f"sf_{uuid.uuid4().hex[:8]}",
            fee_type=FeeType.SLIPPAGE,
            protocol=protocol,
            chain_from="",
            chain_to="",
            token_from=token_from,
            token_to=token_to,
            amount=fee_amount,
            percentage=percentage,
            timestamp=datetime.now(),
            estimated=True,
            metadata={"slippage_base": str(slippage_base), "multiplier": str(multiplier)},
        )

    async def _calculate_priority_fee(
        self,
        protocol: str,
        tier: FeeTier,
        amount: Decimal,
    ) -> BridgeFee:
        """Calcule les frais de priorité"""
        # Frais de priorité seulement pour les tiers High et Premium
        if tier not in [FeeTier.HIGH, FeeTier.PREMIUM]:
            return BridgeFee(
                fee_id=f"pf_{uuid.uuid4().hex[:8]}",
                fee_type=FeeType.PRIORITY,
                protocol=protocol,
                chain_from="",
                chain_to="",
                token_from="",
                token_to="",
                amount=Decimal("0"),
                percentage=Decimal("0"),
                timestamp=datetime.now(),
                estimated=True,
            )

        # Frais de priorité basés sur le montant
        base_fee = Decimal("0.0005") if tier == FeeTier.HIGH else Decimal("0.001")
        fee_amount = amount * base_fee
        fee_amount = fee_amount.quantize(Decimal("0.00000001"))

        return BridgeFee(
            fee_id=f"pf_{uuid.uuid4().hex[:8]}",
            fee_type=FeeType.PRIORITY,
            protocol=protocol,
            chain_from="",
            chain_to="",
            token_from="",
            token_to="",
            amount=fee_amount,
            percentage=base_fee,
            timestamp=datetime.now(),
            estimated=True,
            metadata={"tier": tier.value},
        )

    async def _calculate_l1_fee(
        self,
        protocol: str,
        chain: str,
        amount: Decimal,
        tier: FeeTier,
    ) -> BridgeFee:
        """Calcule les frais L1 (pour les L2)"""
        # Frais L1 spécifiques à Optimism/Arbitrum
        if chain not in ["optimism", "arbitrum"]:
            return BridgeFee(
                fee_id=f"l1_{uuid.uuid4().hex[:8]}",
                fee_type=FeeType.L1,
                protocol=protocol,
                chain_from=chain,
                chain_to="",
                token_from="",
                token_to="",
                amount=Decimal("0"),
                percentage=Decimal("0"),
                timestamp=datetime.now(),
                estimated=True,
            )

        # Frais L1 de base
        base_fee = Decimal("0.001") if chain == "optimism" else Decimal("0.0008")

        # Ajustement selon le montant
        if amount > Decimal("100000"):
            base_fee *= Decimal("1.5")

        fee_amount = amount * base_fee
        fee_amount = fee_amount.quantize(Decimal("0.00000001"))

        return BridgeFee(
            fee_id=f"l1_{uuid.uuid4().hex[:8]}",
            fee_type=FeeType.L1,
            protocol=protocol,
            chain_from=chain,
            chain_to="",
            token_from="",
            token_to="",
            amount=fee_amount,
            percentage=base_fee,
            timestamp=datetime.now(),
            estimated=True,
            metadata={"chain": chain},
        )

    # ============================================================
    # MÉTHODES DE CALCUL ADDITIONNELLES
    # ============================================================

    async def _estimate_time(
        self,
        protocol: str,
        chain_from: str,
        chain_to: str,
        tier: FeeTier,
    ) -> int:
        """Estime le temps de bridge"""
        # Temps de base par protocole
        base_time = {
            "layerzero": 120,
            "wormhole": 90,
            "cctp": 60,
            "optimism_native": 120,
            "polygon_pos": 120,
            "solana_wormhole": 30,
            "debridge": 150,
            "axelar": 180,
            "across": 130,
            "hop": 100,
            "stargate": 80,
            "connext": 110,
            "synapse": 95,
        }.get(protocol, 120)

        # Ajustement selon le tier
        tier_multipliers = {
            FeeTier.LOW: 1.5,
            FeeTier.STANDARD: 1.0,
            FeeTier.HIGH: 0.7,
            FeeTier.PREMIUM: 0.5,
        }

        multiplier = tier_multipliers.get(tier, 1.0)

        return int(base_time * multiplier)

    async def _calculate_confidence(
        self,
        protocol: str,
        amount: Decimal,
        fees: List[BridgeFee],
    ) -> float:
        """Calcule le niveau de confiance"""
        # Confiance de base
        base_confidence = 0.95

        # Ajustement selon les frais (si trop élevés, confiance réduite)
        total_fee = sum(f.amount for f in fees)
        if total_fee > amount * Decimal("0.05"):
            base_confidence -= 0.1
        elif total_fee > amount * Decimal("0.1"):
            base_confidence -= 0.2

        # Ajustement selon le montant
        if amount > Decimal("100000"):
            base_confidence -= 0.05

        # Ajustement selon le protocol
        protocol_confidence = {
            "wormhole": 0.98,
            "cctp": 0.98,
            "layerzero": 0.95,
            "optimism_native": 0.97,
            "polygon_pos": 0.97,
            "solana_wormhole": 0.96,
        }.get(protocol, 0.90)

        base_confidence = (base_confidence + protocol_confidence) / 2

        return max(0.5, min(0.99, base_confidence))

    async def _get_gas_factor(self, chain: str) -> Decimal:
        """Obtient le facteur de gaz actuel"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return Decimal("0")

            gas_price = await provider.eth.gas_price
            gas_price_decimal = Decimal(str(gas_price)) / Decimal(1e18)

            # Prix de gaz normal (en ETH/wei)
            normal_gas = Decimal("0.00005")  # 50 Gwei

            factor = gas_price_decimal / normal_gas
            return factor

        except Exception:
            return Decimal("0")

    async def _get_volume_factor(self, protocol: str, chain: str) -> Decimal:
        """Obtient le facteur de volume"""
        # Simulé - dans la réalité, on interrogerait un indexeur
        return Decimal("0")

    def _apply_constraints(
        self,
        quotes: Dict[str, FeeQuote],
        constraints: Dict[str, Any],
    ) -> Dict[str, FeeQuote]:
        """Applique les contraintes aux devis"""
        filtered = {}

        for protocol, quote in quotes.items():
            valid = True

            # Contrainte de temps maximum
            if "max_time" in constraints and quote.estimated_time > constraints["max_time"]:
                valid = False

            # Contrainte de frais maximum
            if "max_fee" in constraints and quote.total_fee > Decimal(str(constraints["max_fee"])):
                valid = False

            # Contrainte de confiance minimum
            if "min_confidence" in constraints and quote.confidence < constraints["min_confidence"]:
                valid = False

            if valid:
                filtered[protocol] = quote

        return filtered

    # ============================================================
    # MÉTHODES D'ALERTES
    # ============================================================

    async def _check_fee_alerts(self, quote: FeeQuote) -> None:
        """Vérifie les alertes de frais"""
        try:
            # Vérification de l'augmentation des frais
            stats = await self.get_fee_stats(
                protocol=quote.protocol,
                chain_from=quote.chain_from,
                chain_to=quote.chain_to,
                token_from=quote.token_from,
                token_to=quote.token_to,
                timeframe=3600,  # 1 heure
            )

            if stats.count > 0 and quote.total_fee > stats.avg_fee * Decimal("1.5"):
                logger.warning(
                    f"ALERTE: Frais en hausse pour {quote.protocol} - "
                    f"{quote.total_fee} vs moyenne {stats.avg_fee}"
                )

            # Vérification des frais de gaz
            gas_fees = [f for f in quote.fees if f.fee_type == FeeType.GAS]
            if gas_fees:
                gas_fee = gas_fees[0]
                gas_factor = await self._get_gas_factor(quote.chain_from)
                if gas_factor > Decimal("2"):
                    logger.warning(
                        f"ALERTE: Prix du gaz élevé sur {quote.chain_from} - "
                        f"facteur {gas_factor}"
                    )

        except Exception as e:
            logger.warning(f"Erreur de vérification des alertes: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "total_fee_quotes": len(self._fee_cache),
            "total_fee_history": len(self._fee_history),
            "total_stats": len(self._stats_cache),
            "active_estimates": len(self._fee_history[-100:]),
            "protocols": list(self.BASE_FEES.keys()),
            "cache_ttl": self.cache_ttl,
        }

    def get_fee_summary(self) -> Dict[str, Any]:
        """Obtient un résumé des frais"""
        summary = defaultdict(lambda: defaultdict(dict))

        for fee in self._fee_history[-1000:]:
            summary[fee.protocol][fee.fee_type.value] = {
                "count": summary[fee.protocol].get(fee.fee_type.value, {}).get("count", 0) + 1,
                "total": summary[fee.protocol].get(fee.fee_type.value, {}).get("total", Decimal("0")) + fee.amount,
            }

        # Conversion en dict standard
        result = {}
        for protocol, types in summary.items():
            result[protocol] = {}
            for fee_type, data in types.items():
                result[protocol][fee_type] = {
                    "count": data["count"],
                    "total": str(data["total"]),
                    "avg": str(data["total"] / data["count"]) if data["count"] > 0 else "0",
                }

        return result

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeFeeManager...")

        self._fee_cache.clear()
        self._stats_cache.clear()
        self._price_cache.clear()
        self._fee_history.clear()
        self._fee_stats.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_fee_manager(
    config: Dict[str, Any],
    bridge_manager: BridgeManager,
    **kwargs,
) -> BridgeFeeManager:
    """
    Crée une instance de BridgeFeeManager

    Args:
        config: Configuration
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeFeeManager
    """
    return BridgeFeeManager(
        config=config,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeFeeManager"""
    # Configuration
    config = {
        "alert_thresholds": {
            "fee_increase": "0.3",  # 30%
            "fee_decrease": "0.3",  # 30%
            "gas_spike": "2.0",  # 2x
            "min_volume": "100",
        },
    }

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        async def get_bridge_config(self, protocol):
            return {"supported_tokens": ["USDC", "ETH", "USDT"]}
        async def get_all_bridges(self):
            return []

    bridge_manager = SimpleBridgeManager()

    # Web3 providers (simplifiés)
    web3_providers = {}

    # Création du gestionnaire de frais
    fee_manager = create_bridge_fee_manager(
        config=config,
        bridge_manager=bridge_manager,
        web3_providers=web3_providers,
    )

    # Obtention d'un devis de frais
    quote = await fee_manager.get_fee_quote(
        protocol="wormhole",
        chain_from="ethereum",
        chain_to="polygon",
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
        tier=FeeTier.STANDARD,
    )

    print(f"Devis de frais: {quote.to_dict()}")
    print(f"Frais totaux: {quote.total_fee} ({quote.total_percentage}%)")

    # Comparaison des frais
    comparisons = await fee_manager.compare_fees(
        chain_from="ethereum",
        chain_to="polygon",
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
    )

    print("\nComparaison des frais:")
    for protocol, q in comparisons.items():
        print(f"  {protocol}: {q.total_fee} ({q.total_percentage:.2f}%)")

    # Optimisation des frais
    best_quote = await fee_manager.optimize_fees(
        chain_from="ethereum",
        chain_to="polygon",
        token_from="USDC",
        token_to="USDC",
        amount=Decimal("1000"),
        strategy=FeeOptimizationStrategy.BALANCED,
    )

    print(f"\nMeilleur devis: {best_quote.protocol} - {best_quote.total_fee}")

    # Statistiques
    stats = fee_manager.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Nettoyage
    await fee_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())
