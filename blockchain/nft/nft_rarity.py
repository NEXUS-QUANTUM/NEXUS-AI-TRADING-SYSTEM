# blockchain/nft/nft_rarity.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Rarity - Calcul de Rareté des NFTs

Ce module implémente un système complet de calcul de rareté pour les NFTs,
supportant multiples algorithmes (statistiques, trait-based, ML-based),
et l'analyse des collections.

Fonctionnalités principales:
- Calcul de rareté statistique (trait frequency)
- Calcul de rareté par attributs (trait-based rarity)
- Score de rareté composite
- Analyse de collection
- Classement des NFTs
- Support des multiples standards (ERC-721, ERC-1155)
- Cache des calculs de rareté
- Métriques de rareté avancées
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
from collections import defaultdict, Counter
from functools import lru_cache, wraps
import math
import statistics

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
    from .base_nft import BaseNFT, NFTMetadata, NFTData
    from .nft_metadata import NFTMetadataManager
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
    from .base_nft import BaseNFT, NFTMetadata, NFTData
    from .nft_metadata import NFTMetadataManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class RarityAlgorithm(Enum):
    """Algorithmes de calcul de rareté"""
    TRAIT_FREQUENCY = "trait_frequency"
    STATISTICAL = "statistical"
    SHANNON_ENTROPY = "shannon_entropy"
    COMPOSITE = "composite"
    ML_BASED = "ml_based"
    CUSTOM = "custom"


class RarityScoreType(Enum):
    """Types de scores de rareté"""
    GLOBAL = "global"  # Rareté globale dans la collection
    TRAIT = "trait"  # Rareté par trait
    COMPOSITE = "composite"  # Score composite
    NORMALIZED = "normalized"  # Score normalisé (0-1)
    PERCENTILE = "percentile"  # Percentile de rareté


@dataclass
class TraitRarity:
    """Rareté d'un trait"""
    trait_type: str
    value: str
    count: int
    frequency: float
    rarity_score: float
    percentile: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "trait_type": self.trait_type,
            "value": self.value,
            "count": self.count,
            "frequency": self.frequency,
            "rarity_score": self.rarity_score,
            "percentile": self.percentile,
            "metadata": self.metadata,
        }


@dataclass
class NFTRarityScore:
    """Score de rareté d'un NFT"""
    token_id: str
    contract_address: str
    collection: str
    raw_score: float
    normalized_score: float
    percentile: float
    rank: int
    total_supply: int
    trait_scores: Dict[str, TraitRarity]
    algorithm: RarityAlgorithm
    score_type: RarityScoreType
    calculated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "token_id": self.token_id,
            "contract_address": self.contract_address,
            "collection": self.collection,
            "raw_score": self.raw_score,
            "normalized_score": self.normalized_score,
            "percentile": self.percentile,
            "rank": self.rank,
            "total_supply": self.total_supply,
            "trait_scores": {k: v.to_dict() for k, v in self.trait_scores.items()},
            "algorithm": self.algorithm.value,
            "score_type": self.score_type.value,
            "calculated_at": self.calculated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class CollectionRarityStats:
    """Statistiques de rareté d'une collection"""
    collection: str
    total_supply: int
    avg_score: float
    median_score: float
    min_score: float
    max_score: float
    std_dev: float
    score_distribution: Dict[str, float]
    top_rarity_traits: List[TraitRarity]
    rarest_nfts: List[NFTRarityScore]
    calculated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "collection": self.collection,
            "total_supply": self.total_supply,
            "avg_score": self.avg_score,
            "median_score": self.median_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "std_dev": self.std_dev,
            "score_distribution": self.score_distribution,
            "top_rarity_traits": [t.to_dict() for t in self.top_rarity_traits],
            "rarest_nfts": [n.to_dict() for n in self.rarest_nfts[:10]],
            "calculated_at": self.calculated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTRarityManager(BaseNFT):
    """
    Gestionnaire avancé de rareté NFT
    """

    def __init__(
        self,
        config: Dict[str, Any],
        wallet_manager: Any,
        metadata_manager: Optional[NFTMetadataManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de rareté

        Args:
            config: Configuration
            wallet_manager: Gestionnaire de wallets
            metadata_manager: Gestionnaire de métadonnées
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
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._rarity_cache: Dict[str, Tuple[float, NFTRarityScore]] = {}
        self._collection_stats_cache: Dict[str, Tuple[float, CollectionRarityStats]] = {}
        self._trait_frequency_cache: Dict[str, Tuple[float, Dict[str, Dict[str, int]]]] = {}
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

        # Cache des métadonnées
        self._metadata_cache: Dict[str, NFTMetadata] = {}

        # Statistiques
        self._stats: Dict[str, Any] = defaultdict(dict)

        logger.info("NFTRarityManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES - CALCUL DE RARETÉ
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def calculate_rarity(
        self,
        contract_address: str,
        token_id: str,
        chain: str = "ethereum",
        algorithm: RarityAlgorithm = RarityAlgorithm.TRAIT_FREQUENCY,
        force_refresh: bool = False,
    ) -> NFTRarityScore:
        """
        Calcule le score de rareté d'un NFT

        Args:
            contract_address: Adresse du contrat
            token_id: ID du token
            chain: Chaîne
            algorithm: Algorithme de calcul
            force_refresh: Forcer le rafraîchissement

        Returns:
            Score de rareté du NFT
        """
        cache_key = f"{chain}:{contract_address}:{token_id}:{algorithm.value}"

        if not force_refresh and cache_key in self._rarity_cache:
            cached_time, score = self._rarity_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return score

        try:
            # Récupération des métadonnées
            nft_data = await self._get_nft_data(contract_address, token_id, chain)

            # Récupération de tous les NFTs de la collection
            collection_nfts = await self._get_collection_nfts(contract_address, chain)

            # Calcul selon l'algorithme
            if algorithm == RarityAlgorithm.TRAIT_FREQUENCY:
                score = await self._calculate_trait_frequency_rarity(
                    nft_data, collection_nfts, contract_address, token_id, chain
                )
            elif algorithm == RarityAlgorithm.STATISTICAL:
                score = await self._calculate_statistical_rarity(
                    nft_data, collection_nfts, contract_address, token_id, chain
                )
            elif algorithm == RarityAlgorithm.SHANNON_ENTROPY:
                score = await self._calculate_shannon_entropy_rarity(
                    nft_data, collection_nfts, contract_address, token_id, chain
                )
            elif algorithm == RarityAlgorithm.COMPOSITE:
                score = await self._calculate_composite_rarity(
                    nft_data, collection_nfts, contract_address, token_id, chain
                )
            else:
                raise RarityError(f"Algorithme {algorithm.value} non supporté")

            # Mise en cache
            self._rarity_cache[cache_key] = (time.time(), score)

            # Métriques
            self.metrics.record_gauge(
                "nft_rarity_score",
                score.normalized_score,
                {"collection": contract_address[:8], "algorithm": algorithm.value},
            )

            return score

        except Exception as e:
            logger.error(f"Erreur de calcul de rareté: {e}")
            raise RarityError(f"Erreur de calcul de rareté: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def calculate_collection_rarity_stats(
        self,
        contract_address: str,
        chain: str = "ethereum",
        algorithm: RarityAlgorithm = RarityAlgorithm.TRAIT_FREQUENCY,
        force_refresh: bool = False,
    ) -> CollectionRarityStats:
        """
        Calcule les statistiques de rareté d'une collection

        Args:
            contract_address: Adresse du contrat
            chain: Chaîne
            algorithm: Algorithme de calcul
            force_refresh: Forcer le rafraîchissement

        Returns:
            Statistiques de rareté de la collection
        """
        cache_key = f"{chain}:{contract_address}:{algorithm.value}"

        if not force_refresh and cache_key in self._collection_stats_cache:
            cached_time, stats = self._collection_stats_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return stats

        try:
            # Récupération de tous les NFTs de la collection
            collection_nfts = await self._get_collection_nfts(contract_address, chain)

            # Calcul des scores pour tous les NFTs
            scores = []
            for nft in collection_nfts:
                try:
                    score = await self.calculate_rarity(
                        contract_address=contract_address,
                        token_id=nft.token_id,
                        chain=chain,
                        algorithm=algorithm,
                        force_refresh=force_refresh,
                    )
                    scores.append(score)
                except Exception as e:
                    logger.warning(f"Erreur pour {nft.token_id}: {e}")

            if not scores:
                raise RarityError("Aucun score calculé")

            # Calcul des statistiques
            raw_scores = [s.raw_score for s in scores]
            normalized_scores = [s.normalized_score for s in scores]

            stats = CollectionRarityStats(
                collection=contract_address,
                total_supply=len(scores),
                avg_score=statistics.mean(raw_scores),
                median_score=statistics.median(raw_scores),
                min_score=min(raw_scores),
                max_score=max(raw_scores),
                std_dev=statistics.stdev(raw_scores) if len(raw_scores) > 1 else 0,
                score_distribution=self._calculate_score_distribution(normalized_scores),
                top_rarity_traits=await self._get_top_rarity_traits(contract_address, chain),
                rarest_nfts=sorted(scores, key=lambda x: x.raw_score, reverse=True)[:10],
                calculated_at=datetime.now(),
            )

            # Mise en cache
            self._collection_stats_cache[cache_key] = (time.time(), stats)

            # Métriques
            self.metrics.record_gauge(
                "nft_collection_avg_rarity",
                stats.avg_score,
                {"collection": contract_address[:8]},
            )

            return stats

        except Exception as e:
            logger.error(f"Erreur de calcul des statistiques: {e}")
            raise RarityError(f"Erreur de calcul des statistiques: {e}")

    # ============================================================
    # MÉTHODES DE COMPARAISON
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def compare_rarity(
        self,
        token_ids: List[str],
        contract_address: str,
        chain: str = "ethereum",
        algorithm: RarityAlgorithm = RarityAlgorithm.TRAIT_FREQUENCY,
    ) -> Dict[str, NFTRarityScore]:
        """
        Compare la rareté de plusieurs NFTs

        Args:
            token_ids: Liste des IDs de tokens
            contract_address: Adresse du contrat
            chain: Chaîne
            algorithm: Algorithme de calcul

        Returns:
            Dictionnaire des scores par token_id
        """
        scores = {}
        for token_id in token_ids:
            try:
                score = await self.calculate_rarity(
                    contract_address=contract_address,
                    token_id=token_id,
                    chain=chain,
                    algorithm=algorithm,
                )
                scores[token_id] = score
            except Exception as e:
                logger.warning(f"Erreur pour {token_id}: {e}")

        return scores

    # ============================================================
    # MÉTHODES D'ANALYSE DES TRAITS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_trait_frequency(
        self,
        contract_address: str,
        chain: str = "ethereum",
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, int]]:
        """
        Obtient la fréquence des traits dans une collection

        Args:
            contract_address: Adresse du contrat
            chain: Chaîne
            force_refresh: Forcer le rafraîchissement

        Returns:
            Dictionnaire des fréquences des traits
        """
        cache_key = f"{chain}:{contract_address}"

        if not force_refresh and cache_key in self._trait_frequency_cache:
            cached_time, frequency = self._trait_frequency_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return frequency

        try:
            # Récupération de tous les NFTs de la collection
            collection_nfts = await self._get_collection_nfts(contract_address, chain)

            # Comptage des traits
            trait_frequency = defaultdict(lambda: defaultdict(int))

            for nft in collection_nfts:
                if nft.metadata and nft.metadata.attributes:
                    for attr in nft.metadata.attributes:
                        trait_type = attr.get("trait_type", "unknown")
                        value = attr.get("value", "unknown")
                        trait_frequency[trait_type][value] += 1

            # Mise en cache
            self._trait_frequency_cache[cache_key] = (time.time(), dict(trait_frequency))

            return dict(trait_frequency)

        except Exception as e:
            logger.error(f"Erreur de récupération de la fréquence des traits: {e}")
            raise RarityError(f"Erreur de récupération de la fréquence des traits: {e}")

    # ============================================================
    # MÉTHODES INTERNES - ALGORITHMES
    # ============================================================

    async def _calculate_trait_frequency_rarity(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTRarityScore:
        """Calcule la rareté basée sur la fréquence des traits"""
        if not nft_data.metadata or not nft_data.metadata.attributes:
            return self._create_default_rarity_score(
                token_id, contract_address, chain, RarityAlgorithm.TRAIT_FREQUENCY
            )

        # Calcul des scores de traits
        trait_frequency = await self.get_trait_frequency(contract_address, chain, force_refresh=True)

        trait_scores = {}
        total_score = 0
        trait_count = 0

        for attr in nft_data.metadata.attributes:
            trait_type = attr.get("trait_type", "unknown")
            value = attr.get("value", "unknown")

            count = trait_frequency.get(trait_type, {}).get(value, 1)
            total_items = len(collection_nfts)
            frequency = count / total_items if total_items > 0 else 1

            # Score inverse de la fréquence
            rarity_score = 1 / frequency if frequency > 0 else 1

            trait_scores[f"{trait_type}:{value}"] = TraitRarity(
                trait_type=trait_type,
                value=value,
                count=count,
                frequency=frequency,
                rarity_score=rarity_score,
                percentile=1 - frequency,
            )

            total_score += rarity_score
            trait_count += 1

        # Score final
        raw_score = total_score / trait_count if trait_count > 0 else 0

        # Normalisation
        all_scores = []
        for nft in collection_nfts:
            if nft.metadata and nft.metadata.attributes:
                score = 0
                for attr in nft.metadata.attributes:
                    trait_type = attr.get("trait_type", "unknown")
                    value = attr.get("value", "unknown")
                    count = trait_frequency.get(trait_type, {}).get(value, 1)
                    frequency = count / len(collection_nfts) if len(collection_nfts) > 0 else 1
                    score += 1 / frequency if frequency > 0 else 1
                all_scores.append(score / len(nft.metadata.attributes) if nft.metadata.attributes else 0)

        normalized_score = self._normalize_score(raw_score, all_scores)

        return NFTRarityScore(
            token_id=token_id,
            contract_address=contract_address,
            collection=contract_address,
            raw_score=raw_score,
            normalized_score=normalized_score,
            percentile=self._calculate_percentile(raw_score, all_scores),
            rank=self._calculate_rank(raw_score, all_scores),
            total_supply=len(collection_nfts),
            trait_scores=trait_scores,
            algorithm=RarityAlgorithm.TRAIT_FREQUENCY,
            score_type=RarityScoreType.GLOBAL,
            calculated_at=datetime.now(),
        )

    async def _calculate_statistical_rarity(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTRarityScore:
        """Calcule la rareté statistique"""
        if not nft_data.metadata or not nft_data.metadata.attributes:
            return self._create_default_rarity_score(
                token_id, contract_address, chain, RarityAlgorithm.STATISTICAL
            )

        # Collecte des scores
        scores = []
        trait_scores = {}

        for attr in nft_data.metadata.attributes:
            trait_type = attr.get("trait_type", "unknown")
            value = attr.get("value", "unknown")

            # Calcul du score Z pour le trait
            trait_values = []
            for nft in collection_nfts:
                if nft.metadata and nft.metadata.attributes:
                    for a in nft.metadata.attributes:
                        if a.get("trait_type") == trait_type:
                            trait_values.append(1 if a.get("value") == value else 0)

            if trait_values:
                mean = statistics.mean(trait_values)
                std_dev = statistics.stdev(trait_values) if len(trait_values) > 1 else 1
                z_score = (1 - mean) / std_dev if std_dev > 0 else 0

                trait_scores[f"{trait_type}:{value}"] = TraitRarity(
                    trait_type=trait_type,
                    value=value,
                    count=sum(trait_values),
                    frequency=sum(trait_values) / len(trait_values),
                    rarity_score=z_score,
                    percentile=self._normalize_score(z_score, [z_score]),
                )

                scores.append(z_score)

        raw_score = statistics.mean(scores) if scores else 0

        # Collecte des scores de tous les NFTs
        all_scores = []
        for nft in collection_nfts:
            nft_scores = []
            if nft.metadata and nft.metadata.attributes:
                for attr in nft.metadata.attributes:
                    trait_type = attr.get("trait_type", "unknown")
                    value = attr.get("value", "unknown")
                    trait_values = []
                    for n in collection_nfts:
                        if n.metadata and n.metadata.attributes:
                            for a in n.metadata.attributes:
                                if a.get("trait_type") == trait_type:
                                    trait_values.append(1 if a.get("value") == value else 0)
                    if trait_values:
                        mean = statistics.mean(trait_values)
                        std_dev = statistics.stdev(trait_values) if len(trait_values) > 1 else 1
                        nft_scores.append((1 - mean) / std_dev if std_dev > 0 else 0)
            all_scores.append(statistics.mean(nft_scores) if nft_scores else 0)

        normalized_score = self._normalize_score(raw_score, all_scores)

        return NFTRarityScore(
            token_id=token_id,
            contract_address=contract_address,
            collection=contract_address,
            raw_score=raw_score,
            normalized_score=normalized_score,
            percentile=self._calculate_percentile(raw_score, all_scores),
            rank=self._calculate_rank(raw_score, all_scores),
            total_supply=len(collection_nfts),
            trait_scores=trait_scores,
            algorithm=RarityAlgorithm.STATISTICAL,
            score_type=RarityScoreType.GLOBAL,
            calculated_at=datetime.now(),
        )

    async def _calculate_shannon_entropy_rarity(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTRarityScore:
        """Calcule la rareté basée sur l'entropie de Shannon"""
        if not nft_data.metadata or not nft_data.metadata.attributes:
            return self._create_default_rarity_score(
                token_id, contract_address, chain, RarityAlgorithm.SHANNON_ENTROPY
            )

        trait_frequency = await self.get_trait_frequency(contract_address, chain, force_refresh=True)

        trait_scores = {}
        total_entropy = 0
        trait_count = 0

        for attr in nft_data.metadata.attributes:
            trait_type = attr.get("trait_type", "unknown")
            value = attr.get("value", "unknown")

            # Calcul de l'entropie pour ce trait
            freq = trait_frequency.get(trait_type, {})
            total = sum(freq.values()) if freq else 1

            if total > 0 and value in freq:
                p = freq[value] / total
                entropy = -p * math.log2(p) if p > 0 else 0

                trait_scores[f"{trait_type}:{value}"] = TraitRarity(
                    trait_type=trait_type,
                    value=value,
                    count=freq.get(value, 0),
                    frequency=p,
                    rarity_score=entropy,
                    percentile=1 - p,
                )

                total_entropy += entropy
                trait_count += 1

        raw_score = total_entropy / trait_count if trait_count > 0 else 0

        # Collecte des entropies de tous les NFTs
        all_entropies = []
        for nft in collection_nfts:
            nft_entropy = 0
            nft_traits = 0
            if nft.metadata and nft.metadata.attributes:
                for attr in nft.metadata.attributes:
                    trait_type = attr.get("trait_type", "unknown")
                    value = attr.get("value", "unknown")
                    freq = trait_frequency.get(trait_type, {})
                    total = sum(freq.values()) if freq else 1
                    if total > 0 and value in freq:
                        p = freq[value] / total
                        nft_entropy += -p * math.log2(p) if p > 0 else 0
                        nft_traits += 1
            all_entropies.append(nft_entropy / nft_traits if nft_traits > 0 else 0)

        normalized_score = self._normalize_score(raw_score, all_entropies)

        return NFTRarityScore(
            token_id=token_id,
            contract_address=contract_address,
            collection=contract_address,
            raw_score=raw_score,
            normalized_score=normalized_score,
            percentile=self._calculate_percentile(raw_score, all_entropies),
            rank=self._calculate_rank(raw_score, all_entropies),
            total_supply=len(collection_nfts),
            trait_scores=trait_scores,
            algorithm=RarityAlgorithm.SHANNON_ENTROPY,
            score_type=RarityScoreType.GLOBAL,
            calculated_at=datetime.now(),
        )

    async def _calculate_composite_rarity(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTRarityScore:
        """Calcule un score de rareté composite"""
        if not nft_data.metadata or not nft_data.metadata.attributes:
            return self._create_default_rarity_score(
                token_id, contract_address, chain, RarityAlgorithm.COMPOSITE
            )

        # Calcul des différents scores
        trait_freq_score = await self._calculate_trait_frequency_rarity(
            nft_data, collection_nfts, contract_address, token_id, chain
        )

        # Score composite: moyenne pondérée
        weights = {
            "trait_frequency": 0.4,
            "shannon": 0.3,
            "statistical": 0.3,
        }

        # Pour simplifier, on utilise une combinaison des métriques
        raw_score = (
            trait_freq_score.raw_score * weights["trait_frequency"] +
            await self._get_shannon_component(nft_data, collection_nfts, contract_address) * weights["shannon"] +
            await self._get_statistical_component(nft_data, collection_nfts, contract_address) * weights["statistical"]
        )

        # Collecte des scores composites de tous les NFTs
        all_scores = []
        for nft in collection_nfts:
            score = await self._get_composite_component(nft, collection_nfts, contract_address)
            all_scores.append(score)

        normalized_score = self._normalize_score(raw_score, all_scores)

        return NFTRarityScore(
            token_id=token_id,
            contract_address=contract_address,
            collection=contract_address,
            raw_score=raw_score,
            normalized_score=normalized_score,
            percentile=self._calculate_percentile(raw_score, all_scores),
            rank=self._calculate_rank(raw_score, all_scores),
            total_supply=len(collection_nfts),
            trait_scores={},
            algorithm=RarityAlgorithm.COMPOSITE,
            score_type=RarityScoreType.COMPOSITE,
            calculated_at=datetime.now(),
        )

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _get_nft_data(
        self,
        contract_address: str,
        token_id: str,
        chain: str,
    ) -> NFTData:
        """Récupère les données d'un NFT"""
        # Dans la réalité, on utiliserait le manager NFT
        # Simulé pour l'exemple
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
                attributes=[],
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    async def _get_collection_nfts(
        self,
        contract_address: str,
        chain: str,
    ) -> List[NFTData]:
        """Récupère tous les NFTs d'une collection"""
        # Simulé - dans la réalité, on interrogerait la blockchain
        return []

    def _create_default_rarity_score(
        self,
        token_id: str,
        contract_address: str,
        chain: str,
        algorithm: RarityAlgorithm,
    ) -> NFTRarityScore:
        """Crée un score de rareté par défaut"""
        return NFTRarityScore(
            token_id=token_id,
            contract_address=contract_address,
            collection=contract_address,
            raw_score=0,
            normalized_score=0,
            percentile=0,
            rank=0,
            total_supply=0,
            trait_scores={},
            algorithm=algorithm,
            score_type=RarityScoreType.GLOBAL,
            calculated_at=datetime.now(),
        )

    def _normalize_score(self, score: float, all_scores: List[float]) -> float:
        """Normalise un score entre 0 et 1"""
        if not all_scores:
            return 0

        min_score = min(all_scores)
        max_score = max(all_scores)

        if max_score == min_score:
            return 0

        return (score - min_score) / (max_score - min_score)

    def _calculate_percentile(self, score: float, all_scores: List[float]) -> float:
        """Calcule le percentile d'un score"""
        if not all_scores:
            return 0

        below = sum(1 for s in all_scores if s <= score)
        return below / len(all_scores)

    def _calculate_rank(self, score: float, all_scores: List[float]) -> int:
        """Calcule le rang d'un score"""
        if not all_scores:
            return 0

        above = sum(1 for s in all_scores if s > score)
        return above + 1

    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, float]:
        """Calcule la distribution des scores"""
        distribution = {
            "0-0.1": 0,
            "0.1-0.2": 0,
            "0.2-0.3": 0,
            "0.3-0.4": 0,
            "0.4-0.5": 0,
            "0.5-0.6": 0,
            "0.6-0.7": 0,
            "0.7-0.8": 0,
            "0.8-0.9": 0,
            "0.9-1.0": 0,
        }

        for score in scores:
            for key in distribution:
                low, high = map(float, key.split("-"))
                if low <= score < high:
                    distribution[key] += 1
                    break

        # Normalisation
        total = len(scores)
        for key in distribution:
            distribution[key] = distribution[key] / total if total > 0 else 0

        return distribution

    async def _get_top_rarity_traits(
        self,
        contract_address: str,
        chain: str,
    ) -> List[TraitRarity]:
        """Obtient les traits les plus rares"""
        trait_frequency = await self.get_trait_frequency(contract_address, chain, force_refresh=True)

        all_traits = []
        for trait_type, values in trait_frequency.items():
            total = sum(values.values()) if values else 1
            for value, count in values.items():
                frequency = count / total if total > 0 else 1
                rarity_score = 1 / frequency if frequency > 0 else 1

                all_traits.append(TraitRarity(
                    trait_type=trait_type,
                    value=value,
                    count=count,
                    frequency=frequency,
                    rarity_score=rarity_score,
                    percentile=1 - frequency,
                ))

        # Tri par score de rareté
        all_traits.sort(key=lambda x: x.rarity_score, reverse=True)

        return all_traits[:10]

    async def _get_shannon_component(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
    ) -> float:
        """Obtient la composante Shannon"""
        # Simulé
        return 0

    async def _get_statistical_component(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
    ) -> float:
        """Obtient la composante statistique"""
        # Simulé
        return 0

    async def _get_composite_component(
        self,
        nft_data: NFTData,
        collection_nfts: List[NFTData],
        contract_address: str,
    ) -> float:
        """Obtient la composante composite"""
        # Simulé
        return 0

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques d'utilisation"""
        return {
            "rarity_cached": len(self._rarity_cache),
            "collection_stats_cached": len(self._collection_stats_cache),
            "trait_frequency_cached": len(self._trait_frequency_cache),
            "cache_ttl": self.cache_ttl,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTRarityManager...")

        self._rarity_cache.clear()
        self._collection_stats_cache.clear()
        self._trait_frequency_cache.clear()
        self._metadata_cache.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# EXCEPTIONS
# ============================================================

class RarityError(NFTError):
    """Erreur de rareté"""
    pass


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_rarity_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTRarityManager:
    """
    Crée une instance de NFTRarityManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTRarityManager
    """
    return NFTRarityManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTRarityManager"""
    # Configuration
    config = {}

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Création du gestionnaire
    rarity_manager = create_nft_rarity_manager(
        config=config,
        wallet_manager=wallet_manager,
    )

    # Calcul de la rareté d'un NFT
    rarity = await rarity_manager.calculate_rarity(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        token_id="1",
        algorithm=RarityAlgorithm.TRAIT_FREQUENCY,
    )

    print(f"Score de rareté: {rarity.to_dict()}")

    # Calcul des statistiques de collection
    stats = await rarity_manager.calculate_collection_rarity_stats(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
    )

    print(f"Statistiques de la collection:")
    print(f"  Moyenne: {stats.avg_score:.2f}")
    print(f"  Médiane: {stats.median_score:.2f}")
    print(f"  Min: {stats.min_score:.2f}")
    print(f"  Max: {stats.max_score:.2f}")

    # Récupération de la fréquence des traits
    trait_frequency = await rarity_manager.get_trait_frequency(
        contract_address="0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
    )

    print(f"Fréquence des traits: {len(trait_frequency)} types")

    # Statistiques
    stats = rarity_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await rarity_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
