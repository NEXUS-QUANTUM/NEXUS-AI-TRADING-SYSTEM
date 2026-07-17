# blockchain/nft/nft_valuation.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Valuation - Évaluation des NFTs

Ce module implémente un système complet d'évaluation pour les NFTs,
supportant multiples méthodes d'évaluation (statistiques, ML, comparables),
et l'analyse des facteurs de valeur.

Fonctionnalités principales:
- Évaluation par comparaison (comparable sales)
- Évaluation statistique (floor price, averages)
- Évaluation basée sur les traits (trait-based valuation)
- Évaluation ML (machine learning models)
- Analyse des facteurs de valeur
- Prédiction de prix
- Support des collections
- Cache des évaluations
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
import statistics
import math

import aiohttp
import numpy as np
from scipy import stats as scipy_stats

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, AnalyticsError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTMetadata
    from .nft_metadata import NFTMetadataManager
    from .nft_rarity import NFTRarityManager, NFTRarityScore
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NFTError, ValidationError, AnalyticsError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
    from .base_nft import BaseNFT, NFTData, NFTCollection, NFTMetadata
    from .nft_metadata import NFTMetadataManager
    from .nft_rarity import NFTRarityManager, NFTRarityScore

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ValuationMethod(Enum):
    """Méthodes d'évaluation"""
    COMPARABLE_SALES = "comparable_sales"
    STATISTICAL = "statistical"
    TRAIT_BASED = "trait_based"
    ML_MODEL = "ml_model"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


class ValuationConfidence(Enum):
    """Niveaux de confiance de l'évaluation"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ComparableSale:
    """Vente comparable"""
    token_id: str
    price: Decimal
    currency: str
    timestamp: datetime
    similarity_score: float
    traits_match: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token_id": self.token_id,
            "price": str(self.price),
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
            "similarity_score": self.similarity_score,
            "traits_match": self.traits_match,
            "metadata": self.metadata,
        }


@dataclass
class NFTValuation:
    """Évaluation d'un NFT"""
    valuation_id: str
    token_id: str
    contract_address: str
    collection: str
    estimated_price: Decimal
    price_low: Decimal
    price_high: Decimal
    currency: str
    method: ValuationMethod
    confidence: ValuationConfidence
    confidence_score: float
    comparable_sales: List[ComparableSale]
    factors: Dict[str, Any]
    calculated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "valuation_id": self.valuation_id,
            "token_id": self.token_id,
            "contract_address": self.contract_address,
            "collection": self.collection,
            "estimated_price": str(self.estimated_price),
            "price_low": str(self.price_low),
            "price_high": str(self.price_high),
            "currency": self.currency,
            "method": self.method.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "comparable_sales": [s.to_dict() for s in self.comparable_sales],
            "factors": self.factors,
            "calculated_at": self.calculated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ValuationFactors:
    """Facteurs d'évaluation"""
    rarity_score: float
    trait_count: int
    unique_traits: int
    collection_floor: Decimal
    collection_volume_24h: Decimal
    market_trend: float
    liquidity_score: float
    whale_interest: float
    social_sentiment: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "rarity_score": self.rarity_score,
            "trait_count": self.trait_count,
            "unique_traits": self.unique_traits,
            "collection_floor": str(self.collection_floor),
            "collection_volume_24h": str(self.collection_volume_24h),
            "market_trend": self.market_trend,
            "liquidity_score": self.liquidity_score,
            "whale_interest": self.whale_interest,
            "social_sentiment": self.social_sentiment,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTValuationManager(BaseNFT):
    """
    Gestionnaire d'évaluation NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        metadata_manager: Optional[NFTMetadataManager] = None,
        rarity_manager: Optional[NFTRarityManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire d'évaluation

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            metadata_manager: Gestionnaire de métadonnées
            rarity_manager: Gestionnaire de rareté
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, wallet_manager, metrics_collector)

        self.config = config
        self.wallet_manager = wallet_manager
        self.metadata_manager = metadata_manager or NFTMetadataManager(
            config=config.get("metadata", {}),
            wallet_manager=wallet_manager,
            metrics_collector=metrics_collector,
        )
        self.rarity_manager = rarity_manager or NFTRarityManager(
            config=config.get("rarity", {}),
            wallet_manager=wallet_manager,
            metadata_manager=self.metadata_manager,
            metrics_collector=metrics_collector,
        )
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._valuations_cache: Dict[str, Tuple[float, NFTValuation]] = {}
        self._price_history_cache: Dict[str, List[Tuple[datetime, Decimal]]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
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

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)

        logger.info("NFTValuationManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_valuation(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
        method: ValuationMethod = ValuationMethod.ENSEMBLE,
        force_refresh: bool = False,
    ) -> NFTValuation:
        """
        Obtient l'évaluation d'un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne
            method: Méthode d'évaluation
            force_refresh: Forcer le rafraîchissement

        Returns:
            Évaluation du NFT
        """
        cache_key = f"{chain}:{contract_address}:{token_id}:{method.value}"

        if not force_refresh and cache_key in self._valuations_cache:
            cached_time, valuation = self._valuations_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return valuation

        try:
            # Récupération des données
            nft_data = await self._get_nft_data(contract_address, token_id, chain)

            # Récupération de la rareté
            rarity_score = await self.rarity_manager.calculate_rarity(
                contract_address=contract_address,
                token_id=token_id,
                chain=chain,
                force_refresh=force_refresh,
            )

            # Récupération des ventes comparables
            comparable_sales = await self._get_comparable_sales(
                contract_address, token_id, nft_data, chain
            )

            # Calcul des facteurs
            factors = await self._calculate_factors(
                nft_data, rarity_score, comparable_sales, chain
            )

            # Évaluation selon la méthode
            if method == ValuationMethod.COMPARABLE_SALES:
                valuation = await self._evaluate_by_comparable_sales(
                    nft_data, comparable_sales, factors, chain
                )
            elif method == ValuationMethod.STATISTICAL:
                valuation = await self._evaluate_statistically(
                    nft_data, factors, chain
                )
            elif method == ValuationMethod.TRAIT_BASED:
                valuation = await self._evaluate_by_traits(
                    nft_data, rarity_score, factors, chain
                )
            elif method == ValuationMethod.ML_MODEL:
                valuation = await self._evaluate_by_ml(
                    nft_data, rarity_score, factors, chain
                )
            else:  # ENSEMBLE
                valuation = await self._evaluate_ensemble(
                    nft_data, comparable_sales, rarity_score, factors, chain
                )

            # Mise en cache
            self._valuations_cache[cache_key] = (time.time(), valuation)

            # Métriques
            self.metrics.record_gauge(
                "nft_valuation_price",
                float(valuation.estimated_price),
                {"collection": contract_address[:8], "method": method.value},
            )

            return valuation

        except Exception as e:
            logger.error(f"Erreur d'évaluation: {e}")
            raise AnalyticsError(f"Erreur d'évaluation: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_price_prediction(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Prédit le prix futur d'un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne
            days: Nombre de jours

        Returns:
            Prédiction de prix
        """
        logger.info(f"Prédiction de prix pour {contract_address}/{token_id}")

        try:
            # Récupération de l'historique des prix
            price_history = await self._get_price_history(contract_address, token_id, chain)

            if len(price_history) < 2:
                return {
                    "status": "insufficient_data",
                    "message": "Pas assez de données historiques",
                    "current_price": Decimal("0"),
                    "predicted_price": Decimal("0"),
                }

            # Prédiction par régression
            prediction = await self._predict_price(price_history, days)

            return prediction

        except Exception as e:
            logger.error(f"Erreur de prédiction de prix: {e}")
            raise AnalyticsError(f"Erreur de prédiction de prix: {e}")

    # ============================================================
    # MÉTHODES D'ÉVALUATION
    # ============================================================

    async def _evaluate_by_comparable_sales(
        self,
        nft_data: NFTData,
        comparable_sales: List[ComparableSale],
        factors: ValuationFactors,
        chain: str,
    ) -> NFTValuation:
        """Évaluation par ventes comparables"""
        if not comparable_sales:
            return await self._evaluate_statistically(nft_data, factors, chain)

        # Calcul des prix
        prices = [s.price for s in comparable_sales]
        weights = [s.similarity_score for s in comparable_sales]

        # Prix pondéré
        weighted_price = sum(p * w for p, w in zip(prices, weights)) / sum(weights)

        # Intervalle de confiance
        std_dev = statistics.stdev(prices) if len(prices) > 1 else prices[0] * Decimal("0.1")
        price_low = weighted_price - std_dev * Decimal("1.96")
        price_high = weighted_price + std_dev * Decimal("1.96")

        # Ajustement par les facteurs
        adjustment = Decimal("1") + Decimal(factors.rarity_score * 0.1)
        estimated_price = weighted_price * adjustment

        return NFTValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:12]}",
            token_id=nft_data.token_id,
            contract_address=nft_data.contract_address,
            collection=nft_data.contract_address,
            estimated_price=estimated_price,
            price_low=price_low,
            price_high=price_high,
            currency="ETH",
            method=ValuationMethod.COMPARABLE_SALES,
            confidence=ValuationConfidence.HIGH if len(comparable_sales) >= 5 else ValuationConfidence.MEDIUM,
            confidence_score=min(1.0, len(comparable_sales) / 10),
            comparable_sales=comparable_sales[:20],
            factors=factors.to_dict(),
            calculated_at=datetime.now(),
        )

    async def _evaluate_statistically(
        self,
        nft_data: NFTData,
        factors: ValuationFactors,
        chain: str,
    ) -> NFTValuation:
        """Évaluation statistique"""
        # Base sur le floor price de la collection
        base_price = factors.collection_floor

        # Ajustement par la rareté
        rarity_multiplier = Decimal("1") + Decimal(factors.rarity_score * 0.5)

        # Ajustement par les traits uniques
        trait_multiplier = Decimal("1") + Decimal(factors.unique_traits * 0.05)

        # Ajustement par la liquidité
        liquidity_multiplier = Decimal("1") + Decimal(factors.liquidity_score * 0.2)

        estimated_price = base_price * rarity_multiplier * trait_multiplier * liquidity_multiplier

        # Intervalle
        price_low = estimated_price * Decimal("0.7")
        price_high = estimated_price * Decimal("1.3")

        return NFTValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:12]}",
            token_id=nft_data.token_id,
            contract_address=nft_data.contract_address,
            collection=nft_data.contract_address,
            estimated_price=estimated_price,
            price_low=price_low,
            price_high=price_high,
            currency="ETH",
            method=ValuationMethod.STATISTICAL,
            confidence=ValuationConfidence.MEDIUM,
            confidence_score=0.6,
            comparable_sales=[],
            factors=factors.to_dict(),
            calculated_at=datetime.now(),
        )

    async def _evaluate_by_traits(
        self,
        nft_data: NFTData,
        rarity_score: NFTRarityScore,
        factors: ValuationFactors,
        chain: str,
    ) -> NFTValuation:
        """Évaluation basée sur les traits"""
        if not nft_data.metadata or not nft_data.metadata.attributes:
            return await self._evaluate_statistically(nft_data, factors, chain)

        # Score de traits
        trait_score = 0
        for trait in nft_data.metadata.attributes:
            trait_type = trait.get("trait_type", "unknown")
            value = trait.get("value", "unknown")

            # Recherche du score de rareté du trait
            trait_key = f"{trait_type}:{value}"
            if trait_key in rarity_score.trait_scores:
                trait_score += rarity_score.trait_scores[trait_key].rarity_score

        trait_score = trait_score / len(nft_data.metadata.attributes) if nft_data.metadata.attributes else 0

        # Évaluation
        base_price = factors.collection_floor
        trait_multiplier = Decimal("1") + Decimal(trait_score * 0.3)
        estimated_price = base_price * trait_multiplier

        price_low = estimated_price * Decimal("0.8")
        price_high = estimated_price * Decimal("1.2")

        return NFTValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:12]}",
            token_id=nft_data.token_id,
            contract_address=nft_data.contract_address,
            collection=nft_data.contract_address,
            estimated_price=estimated_price,
            price_low=price_low,
            price_high=price_high,
            currency="ETH",
            method=ValuationMethod.TRAIT_BASED,
            confidence=ValuationConfidence.MEDIUM,
            confidence_score=0.65,
            comparable_sales=[],
            factors=factors.to_dict(),
            calculated_at=datetime.now(),
        )

    async def _evaluate_by_ml(
        self,
        nft_data: NFTData,
        rarity_score: NFTRarityScore,
        factors: ValuationFactors,
        chain: str,
    ) -> NFTValuation:
        """Évaluation par ML"""
        # Simulé - dans la réalité, on utiliserait un modèle ML entraîné
        estimated_price = factors.collection_floor * Decimal("1.2")

        return NFTValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:12]}",
            token_id=nft_data.token_id,
            contract_address=nft_data.contract_address,
            collection=nft_data.contract_address,
            estimated_price=estimated_price,
            price_low=estimated_price * Decimal("0.85"),
            price_high=estimated_price * Decimal("1.15"),
            currency="ETH",
            method=ValuationMethod.ML_MODEL,
            confidence=ValuationConfidence.HIGH,
            confidence_score=0.8,
            comparable_sales=[],
            factors=factors.to_dict(),
            calculated_at=datetime.now(),
        )

    async def _evaluate_ensemble(
        self,
        nft_data: NFTData,
        comparable_sales: List[ComparableSale],
        rarity_score: NFTRarityScore,
        factors: ValuationFactors,
        chain: str,
    ) -> NFTValuation:
        """Évaluation par ensemble de méthodes"""
        # Calcul des différentes évaluations
        eval_comparable = await self._evaluate_by_comparable_sales(
            nft_data, comparable_sales, factors, chain
        )
        eval_stat = await self._evaluate_statistically(
            nft_data, factors, chain
        )
        eval_trait = await self._evaluate_by_traits(
            nft_data, rarity_score, factors, chain
        )
        eval_ml = await self._evaluate_by_ml(
            nft_data, rarity_score, factors, chain
        )

        # Pondération des résultats
        prices = [
            eval_comparable.estimated_price,
            eval_stat.estimated_price,
            eval_trait.estimated_price,
            eval_ml.estimated_price,
        ]

        weights = [
            eval_comparable.confidence_score,
            eval_stat.confidence_score,
            eval_trait.confidence_score,
            eval_ml.confidence_score,
        ]

        total_weight = sum(weights)
        if total_weight > 0:
            weighted_price = sum(p * w for p, w in zip(prices, weights)) / total_weight
        else:
            weighted_price = statistics.mean(prices)

        # Intervalle
        price_low = min(prices) * Decimal("0.9")
        price_high = max(prices) * Decimal("1.1")

        return NFTValuation(
            valuation_id=f"val_{uuid.uuid4().hex[:12]}",
            token_id=nft_data.token_id,
            contract_address=nft_data.contract_address,
            collection=nft_data.contract_address,
            estimated_price=weighted_price,
            price_low=price_low,
            price_high=price_high,
            currency="ETH",
            method=ValuationMethod.ENSEMBLE,
            confidence=ValuationConfidence.HIGH,
            confidence_score=0.85,
            comparable_sales=comparable_sales[:10],
            factors=factors.to_dict(),
            calculated_at=datetime.now(),
        )

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    async def _get_comparable_sales(
        self,
        contract_address: str,
        token_id: str,
        nft_data: NFTData,
        chain: str,
    ) -> List[ComparableSale]:
        """Récupère les ventes comparables"""
        # Simulé - dans la réalité, on interrogerait les APIs de marketplace
        return [
            ComparableSale(
                token_id=str(i),
                price=Decimal(str(price)),
                currency="ETH",
                timestamp=datetime.now() - timedelta(days=i),
                similarity_score=0.8 - (i * 0.05),
                traits_match={"trait": "value"},
            )
            for i, price in enumerate([1.0, 1.2, 0.9, 1.1, 1.3])
        ]

    async def _get_price_history(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> List[Tuple[datetime, Decimal]]:
        """Récupère l'historique des prix"""
        cache_key = f"{chain}:{contract_address}:{token_id}"

        if cache_key in self._price_history_cache:
            return self._price_history_cache[cache_key]

        # Simulé
        history = []
        for i in range(30):
            price = Decimal(str(1.0 + i * 0.02))
            date = datetime.now() - timedelta(days=30 - i)
            history.append((date, price))

        self._price_history_cache[cache_key] = history
        return history

    async def _get_nft_data(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTData:
        """Récupère les données d'un NFT"""
        return NFTData(
            token_id=token_id,
            contract_address=contract_address,
            chain=chain,
            standard=NFTStandard.ERC721,
            owner="0x...",
            status=NFTStatus.AVAILABLE,
            metadata=NFTMetadata(
                name=f"NFT #{token_id}",
                description="",
                image="",
                attributes=[
                    {"trait_type": "Rarity", "value": "Legendary"},
                    {"trait_type": "Color", "value": "Gold"},
                ],
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    # ============================================================
    # MÉTHODES DE CALCUL
    # ============================================================

    async def _calculate_factors(
        self,
        nft_data: NFTData,
        rarity_score: NFTRarityScore,
        comparable_sales: List[ComparableSale],
        chain: str,
    ) -> ValuationFactors:
        """Calcule les facteurs d'évaluation"""
        # Nombre de traits
        trait_count = len(nft_data.metadata.attributes) if nft_data.metadata and nft_data.metadata.attributes else 0

        # Traits uniques
        unique_traits = 0
        if nft_data.metadata and nft_data.metadata.attributes:
            trait_values = set()
            for trait in nft_data.metadata.attributes:
                value = trait.get("value", "")
                trait_values.add(value)
            unique_traits = len(trait_values)

        # Collection floor (simulé)
        collection_floor = Decimal("1.0")

        # Collection volume (simulé)
        collection_volume_24h = Decimal("10.0")

        return ValuationFactors(
            rarity_score=rarity_score.normalized_score,
            trait_count=trait_count,
            unique_traits=unique_traits,
            collection_floor=collection_floor,
            collection_volume_24h=collection_volume_24h,
            market_trend=0.05,
            liquidity_score=0.7,
            whale_interest=0.3,
            social_sentiment=0.6,
        )

    async def _predict_price(
        self,
        price_history: List[Tuple[datetime, Decimal]],
        days: int,
    ) -> Dict[str, Any]:
        """Prédit le prix futur"""
        if len(price_history) < 2:
            return {
                "status": "insufficient_data",
                "message": "Pas assez de données historiques",
                "current_price": Decimal("0"),
                "predicted_price": Decimal("0"),
            }

        # Préparation des données
        prices = [float(p[1]) for p in price_history]
        dates = [(p[0] - price_history[0][0]).days for p in price_history]

        # Régression linéaire
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(dates, prices)

        # Prédiction
        last_date = dates[-1]
        predicted_price = slope * (last_date + days) + intercept

        # Intervalle de confiance
        confidence_interval = std_err * 1.96 * math.sqrt(1 + 1/len(dates) + (days ** 2) / sum((d - statistics.mean(dates)) ** 2 for d in dates))

        return {
            "status": "success",
            "current_price": Decimal(str(prices[-1])),
            "predicted_price": Decimal(str(predicted_price)),
            "price_low": Decimal(str(predicted_price - confidence_interval)),
            "price_high": Decimal(str(predicted_price + confidence_interval)),
            "confidence": 1 - p_value,
            "days": days,
            "trend": "up" if slope > 0 else "down",
            "r_squared": r_value ** 2,
        }

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "valuations_cached": len(self._valuations_cache),
            "price_history_cached": len(self._price_history_cache),
            "cache_ttl": self.cache_ttl,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTValuationManager...")

        self._valuations_cache.clear()
        self._price_history_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_valuation_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTValuationManager:
    """
    Crée une instance de NFTValuationManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTValuationManager
    """
    return NFTValuationManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTValuationManager"""
    # Configuration
    config = {}

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    valuation_manager = create_nft_valuation_manager(
        config=config,
        wallet_manager=wallet_manager,
    )

    # Obtention de l'évaluation d'un NFT
    valuation = await valuation_manager.get_valuation(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        method=ValuationMethod.ENSEMBLE,
    )

    print(f"Évaluation:")
    print(f"  Prix estimé: {valuation.estimated_price} ETH")
    print(f"  Fourchette: {valuation.price_low} - {valuation.price_high} ETH")
    print(f"  Méthode: {valuation.method.value}")
    print(f"  Confiance: {valuation.confidence.value}")
    print(f"  Ventes comparables: {len(valuation.comparable_sales)}")

    # Prédiction de prix
    prediction = await valuation_manager.get_price_prediction(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        days=30,
    )

    print(f"\nPrédiction de prix:")
    print(f"  Prix actuel: {prediction['current_price']} ETH")
    print(f"  Prix prédit: {prediction['predicted_price']} ETH")
    print(f"  Tendance: {prediction['trend']}")
    print(f"  Confiance: {prediction['confidence']:.2%}")

    # Statistiques
    stats = valuation_manager.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Nettoyage
    await valuation_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
