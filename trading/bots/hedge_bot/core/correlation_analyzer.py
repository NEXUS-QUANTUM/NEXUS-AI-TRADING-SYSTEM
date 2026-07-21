"""
NEXUS AI TRADING SYSTEM - HEDGE BOT CORRELATION ANALYZER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'analyse de corrélation pour le Hedge Bot.
Analyse des corrélations, matrices de corrélation, et métriques de dépendance.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from scipy import stats
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_correlation,
    calculate_beta
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class CorrelationMethod(Enum):
    """Méthodes de corrélation."""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"
    DISTANCE = "distance"
    MUTUAL_INFO = "mutual_info"
    COPULA = "copula"


class CorrelationStrength(Enum):
    """Force de corrélation."""
    VERY_WEAK = "very_weak"      # 0.0 - 0.2
    WEAK = "weak"                # 0.2 - 0.4
    MODERATE = "moderate"        # 0.4 - 0.6
    STRONG = "strong"            # 0.6 - 0.8
    VERY_STRONG = "very_strong"  # 0.8 - 1.0


@dataclass
class CorrelationResult:
    """Résultat de corrélation."""
    asset1: str
    asset2: str
    correlation: float
    p_value: float
    method: CorrelationMethod
    strength: CorrelationStrength
    n_observations: int
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "asset1": self.asset1,
            "asset2": self.asset2,
            "correlation": self.correlation,
            "p_value": self.p_value,
            "method": self.method.value,
            "strength": self.strength.value,
            "n_observations": self.n_observations,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CorrelationMatrix:
    """Matrice de corrélation."""
    assets: List[str]
    matrix: List[List[float]]
    p_values: List[List[float]]
    method: CorrelationMethod
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "assets": self.assets,
            "matrix": self.matrix,
            "p_values": self.p_values,
            "method": self.method.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CorrelationCluster:
    """Cluster de corrélation."""
    cluster_id: UUID
    assets: List[str]
    avg_correlation: float
    min_correlation: float
    max_correlation: float
    size: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "cluster_id": str(self.cluster_id),
            "assets": self.assets,
            "avg_correlation": self.avg_correlation,
            "min_correlation": self.min_correlation,
            "max_correlation": self.max_correlation,
            "size": self.size,
            "metadata": self.metadata
        }


@dataclass
class CorrelationMetrics:
    """Métriques de corrélation."""
    user_id: UUID
    avg_correlation: float
    max_correlation: float
    min_correlation: float
    std_correlation: float
    positive_pairs: int
    negative_pairs: int
    zero_pairs: int
    total_pairs: int
    correlation_density: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "avg_correlation": self.avg_correlation,
            "max_correlation": self.max_correlation,
            "min_correlation": self.min_correlation,
            "std_correlation": self.std_correlation,
            "positive_pairs": self.positive_pairs,
            "negative_pairs": self.negative_pairs,
            "zero_pairs": self.zero_pairs,
            "total_pairs": self.total_pairs,
            "correlation_density": self.correlation_density,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE CORRELATION ANALYZER
# ============================================================================

class CorrelationAnalyzer:
    """
    Analyseur de corrélation avancé.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise l'analyseur de corrélation.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._correlation_cache: Dict[str, CorrelationResult] = {}
        self._matrix_cache: Dict[str, CorrelationMatrix] = {}
        self._cluster_cache: Dict[str, List[CorrelationCluster]] = {}
        self._metrics_cache: Dict[UUID, CorrelationMetrics] = {}
        self._price_cache: Dict[str, List[float]] = {}
        
        # Métriques
        self._metrics = {
            "total_analyses": 0,
            "by_method": {},
            "by_strength": {},
            "last_analysis": None
        }

        logger.info("CorrelationAnalyzer initialisé avec succès")

    # ========================================================================
    # ANALYSE DE CORRÉLATION
    # ========================================================================

    async def analyze(
        self,
        asset1: str,
        asset2: str,
        returns_data: Dict[str, List[float]],
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        metadata: Optional[Dict] = None
    ) -> CorrelationResult:
        """
        Analyse la corrélation entre deux actifs.

        Args:
            asset1: Premier actif
            asset2: Deuxième actif
            returns_data: Données de rendements
            method: Méthode de corrélation
            metadata: Métadonnées

        Returns:
            Résultat de corrélation
        """
        try:
            self._metrics["total_analyses"] += 1
            self._metrics["last_analysis"] = datetime.now().isoformat()

            method_key = method.value
            if method_key not in self._metrics["by_method"]:
                self._metrics["by_method"][method_key] = 0
            self._metrics["by_method"][method_key] += 1

            # Récupération des rendements
            returns1 = returns_data.get(asset1, [])
            returns2 = returns_data.get(asset2, [])

            if len(returns1) != len(returns2) or len(returns1) < 2:
                raise ValueError("Données de rendements invalides")

            # Calcul de la corrélation
            if method == CorrelationMethod.PEARSON:
                corr, p_value = stats.pearsonr(returns1, returns2)
            elif method == CorrelationMethod.SPEARMAN:
                corr, p_value = stats.spearmanr(returns1, returns2)
            elif method == CorrelationMethod.KENDALL:
                corr, p_value = stats.kendalltau(returns1, returns2)
            else:
                corr, p_value = stats.pearsonr(returns1, returns2)

            # Force de corrélation
            strength = self._get_correlation_strength(corr)

            strength_key = strength.value
            if strength_key not in self._metrics["by_strength"]:
                self._metrics["by_strength"][strength_key] = 0
            self._metrics["by_strength"][strength_key] += 1

            result = CorrelationResult(
                asset1=asset1,
                asset2=asset2,
                correlation=corr,
                p_value=p_value,
                method=method,
                strength=strength,
                n_observations=len(returns1),
                timestamp=datetime.now(),
                metadata=metadata or {}
            )

            # Mise en cache
            cache_key = f"{asset1}_{asset2}_{method.value}"
            self._correlation_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Erreur d'analyse de corrélation: {e}")
            raise

    def _get_correlation_strength(self, correlation: float) -> CorrelationStrength:
        """
        Détermine la force de corrélation.

        Args:
            correlation: Coefficient de corrélation

        Returns:
            Force de corrélation
        """
        abs_corr = abs(correlation)
        if abs_corr < 0.2:
            return CorrelationStrength.VERY_WEAK
        elif abs_corr < 0.4:
            return CorrelationStrength.WEAK
        elif abs_corr < 0.6:
            return CorrelationStrength.MODERATE
        elif abs_corr < 0.8:
            return CorrelationStrength.STRONG
        else:
            return CorrelationStrength.VERY_STRONG

    # ========================================================================
    # MATRICE DE CORRÉLATION
    # ========================================================================

    async def matrix(
        self,
        returns_data: Dict[str, List[float]],
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        metadata: Optional[Dict] = None
    ) -> CorrelationMatrix:
        """
        Calcule la matrice de corrélation.

        Args:
            returns_data: Données de rendements
            method: Méthode de corrélation
            metadata: Métadonnées

        Returns:
            Matrice de corrélation
        """
        try:
            assets = list(returns_data.keys())
            n = len(assets)
            
            matrix = np.zeros((n, n))
            p_values = np.zeros((n, n))

            for i, asset1 in enumerate(assets):
                for j, asset2 in enumerate(assets):
                    if i == j:
                        matrix[i][j] = 1.0
                        p_values[i][j] = 0.0
                    else:
                        if method == CorrelationMethod.PEARSON:
                            corr, p_val = stats.pearsonr(
                                returns_data[asset1],
                                returns_data[asset2]
                            )
                        elif method == CorrelationMethod.SPEARMAN:
                            corr, p_val = stats.spearmanr(
                                returns_data[asset1],
                                returns_data[asset2]
                            )
                        elif method == CorrelationMethod.KENDALL:
                            corr, p_val = stats.kendalltau(
                                returns_data[asset1],
                                returns_data[asset2]
                            )
                        else:
                            corr, p_val = stats.pearsonr(
                                returns_data[asset1],
                                returns_data[asset2]
                            )
                        
                        matrix[i][j] = corr
                        p_values[i][j] = p_val

            corr_matrix = CorrelationMatrix(
                assets=assets,
                matrix=matrix.tolist(),
                p_values=p_values.tolist(),
                method=method,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )

            cache_key = "_".join(sorted(assets))
            self._matrix_cache[cache_key] = corr_matrix

            return corr_matrix

        except Exception as e:
            logger.error(f"Erreur de calcul de la matrice de corrélation: {e}")
            raise

    # ========================================================================
    # CLUSTERING
    # ========================================================================

    async def cluster(
        self,
        returns_data: Dict[str, List[float]],
        method: CorrelationMethod = CorrelationMethod.PEARSON,
        threshold: float = 0.5,
        metadata: Optional[Dict] = None
    ) -> List[CorrelationCluster]:
        """
        Clusterise les actifs par corrélation.

        Args:
            returns_data: Données de rendements
            method: Méthode de corrélation
            threshold: Seuil de corrélation
            metadata: Métadonnées

        Returns:
            Liste des clusters
        """
        try:
            # Calcul de la matrice
            corr_matrix = await self.matrix(returns_data, method, metadata)
            
            # Conversion en distance
            distance_matrix = 1 - np.abs(np.array(corr_matrix.matrix))
            
            # Clustering hiérarchique
            linkage = hierarchy.linkage(
                squareform(distance_matrix),
                method='average'
            )
            
            # Formation des clusters
            clusters = hierarchy.fcluster(linkage, 1 - threshold, criterion='distance')
            
            # Organisation des clusters
            cluster_dict: Dict[int, List[str]] = {}
            for i, cluster_id in enumerate(clusters):
                if cluster_id not in cluster_dict:
                    cluster_dict[cluster_id] = []
                cluster_dict[cluster_id].append(corr_matrix.assets[i])

            # Création des objets Cluster
            result = []
            for cluster_id, assets in cluster_dict.items():
                if len(assets) > 1:
                    # Calcul des corrélations moyennes
                    correlations = []
                    for i, asset1 in enumerate(assets):
                        for asset2 in assets[i+1:]:
                            idx1 = corr_matrix.assets.index(asset1)
                            idx2 = corr_matrix.assets.index(asset2)
                            correlations.append(corr_matrix.matrix[idx1][idx2])
                    
                    result.append(CorrelationCluster(
                        cluster_id=uuid4(),
                        assets=assets,
                        avg_correlation=sum(correlations) / len(correlations) if correlations else 0,
                        min_correlation=min(correlations) if correlations else 0,
                        max_correlation=max(correlations) if correlations else 0,
                        size=len(assets)
                    ))

            cache_key = f"cluster_{'_'.join(sorted(returns_data.keys()))}"
            self._cluster_cache[cache_key] = result

            return result

        except Exception as e:
            logger.error(f"Erreur de clustering: {e}")
            return []

    # ========================================================================
    # MÉTRIQUES DE CORRÉLATION
    # ========================================================================

    async def get_metrics(
        self,
        user_id: UUID,
        returns_data: Dict[str, List[float]],
        method: CorrelationMethod = CorrelationMethod.PEARSON
    ) -> CorrelationMetrics:
        """
        Calcule les métriques de corrélation.

        Args:
            user_id: ID de l'utilisateur
            returns_data: Données de rendements
            method: Méthode de corrélation

        Returns:
            Métriques de corrélation
        """
        try:
            corr_matrix = await self.matrix(returns_data, method)
            
            matrix = np.array(corr_matrix.matrix)
            n = len(matrix)
            
            # Extraction des corrélations uniques
            correlations = []
            for i in range(n):
                for j in range(i+1, n):
                    correlations.append(matrix[i][j])
            
            if not correlations:
                return CorrelationMetrics(
                    user_id=user_id,
                    avg_correlation=0.0,
                    max_correlation=0.0,
                    min_correlation=0.0,
                    std_correlation=0.0,
                    positive_pairs=0,
                    negative_pairs=0,
                    zero_pairs=0,
                    total_pairs=0,
                    correlation_density=0.0
                )

            # Statistiques
            avg_corr = np.mean(correlations)
            max_corr = np.max(correlations)
            min_corr = np.min(correlations)
            std_corr = np.std(correlations)

            # Comptage
            positive = sum(1 for c in correlations if c > 0.05)
            negative = sum(1 for c in correlations if c < -0.05)
            zero = sum(1 for c in correlations if abs(c) <= 0.05)
            total = len(correlations)

            # Densité de corrélation
            density = positive / total if total > 0 else 0

            metrics = CorrelationMetrics(
                user_id=user_id,
                avg_correlation=avg_corr,
                max_correlation=max_corr,
                min_correlation=min_corr,
                std_correlation=std_corr,
                positive_pairs=positive,
                negative_pairs=negative,
                zero_pairs=zero,
                total_pairs=total,
                correlation_density=density
            )

            self._metrics_cache[user_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques: {e}")
            return CorrelationMetrics(user_id=user_id)

    # ========================================================================
    # RECOMMANDATIONS
    # ========================================================================

    async def get_recommendations(
        self,
        returns_data: Dict[str, List[float]],
        threshold: float = 0.7,
        method: CorrelationMethod = CorrelationMethod.PEARSON
    ) -> Dict[str, Any]:
        """
        Génère des recommandations basées sur les corrélations.

        Args:
            returns_data: Données de rendements
            threshold: Seuil de corrélation
            method: Méthode de corrélation

        Returns:
            Recommandations
        """
        try:
            corr_matrix = await self.matrix(returns_data, method)
            
            recommendations = {
                "high_correlation_pairs": [],
                "negative_correlation_pairs": [],
                "diversification_opportunities": [],
                "hedge_pairs": []
            }

            assets = corr_matrix.assets
            matrix = np.array(corr_matrix.matrix)

            # Paires hautement corrélées
            for i in range(len(assets)):
                for j in range(i+1, len(assets)):
                    corr = matrix[i][j]
                    if abs(corr) > threshold:
                        recommendations["high_correlation_pairs"].append({
                            "asset1": assets[i],
                            "asset2": assets[j],
                            "correlation": float(corr)
                        })
                    
                    if corr < -0.3:
                        recommendations["negative_correlation_pairs"].append({
                            "asset1": assets[i],
                            "asset2": assets[j],
                            "correlation": float(corr)
                        })

            # Opportunités de diversification
            for asset in assets:
                idx = assets.index(asset)
                avg_corr = np.mean([matrix[idx][j] for j in range(len(assets)) if j != idx])
                if avg_corr < 0.3:
                    recommendations["diversification_opportunities"].append({
                        "asset": asset,
                        "avg_correlation": float(avg_corr)
                    })

            # Paires de hedge
            for i in range(len(assets)):
                for j in range(i+1, len(assets)):
                    corr = matrix[i][j]
                    if corr < -0.2:
                        recommendations["hedge_pairs"].append({
                            "asset1": assets[i],
                            "asset2": assets[j],
                            "correlation": float(corr),
                            "hedge_ratio": 1 - abs(corr)
                        })

            return recommendations

        except Exception as e:
            logger.error(f"Erreur de génération des recommandations: {e}")
            return {}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_correlation(
        self,
        asset1: str,
        asset2: str,
        method: CorrelationMethod = CorrelationMethod.PEARSON
    ) -> Optional[CorrelationResult]:
        """
        Récupère un résultat de corrélation du cache.

        Args:
            asset1: Premier actif
            asset2: Deuxième actif
            method: Méthode de corrélation

        Returns:
            Résultat de corrélation ou None
        """
        cache_key = f"{asset1}_{asset2}_{method.value}"
        return self._correlation_cache.get(cache_key)

    async def get_matrix(
        self,
        assets: List[str]
    ) -> Optional[CorrelationMatrix]:
        """
        Récupère une matrice de corrélation du cache.

        Args:
            assets: Liste des actifs

        Returns:
            Matrice de corrélation ou None
        """
        cache_key = "_".join(sorted(assets))
        return self._matrix_cache.get(cache_key)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_analyses": self._metrics["total_analyses"],
                "by_method": self._metrics["by_method"],
                "by_strength": self._metrics["by_strength"],
                "last_analysis": self._metrics["last_analysis"],
                "cached_correlations": len(self._correlation_cache),
                "cached_matrices": len(self._matrix_cache),
                "cached_clusters": len(self._cluster_cache),
                "cached_metrics": len(self._metrics_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de CorrelationAnalyzer...")
        self._correlation_cache.clear()
        self._matrix_cache.clear()
        self._cluster_cache.clear()
        self._metrics_cache.clear()
        self._price_cache.clear()
        logger.info("CorrelationAnalyzer fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_correlation_analyzer(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> CorrelationAnalyzer:
    """
    Crée une instance de CorrelationAnalyzer.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de CorrelationAnalyzer
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return CorrelationAnalyzer(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "CorrelationMethod",
    "CorrelationStrength",
    "CorrelationResult",
    "CorrelationMatrix",
    "CorrelationCluster",
    "CorrelationMetrics",
    "CorrelationAnalyzer",
    "create_correlation_analyzer"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du CorrelationAnalyzer."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT CORRELATION ANALYZER")
    print("=" * 60)

    # Création de l'analyseur
    analyzer = create_correlation_analyzer()

    print(f"\n✅ CorrelationAnalyzer initialisé")

    # Génération de données de test
    np.random.seed(42)
    n = 100
    
    returns_data = {
        "BTC": np.random.normal(0.001, 0.03, n).tolist(),
        "ETH": np.random.normal(0.001, 0.035, n).tolist(),
        "SOL": np.random.normal(0.001, 0.04, n).tolist(),
        "USDC": np.random.normal(0, 0.001, n).tolist(),
        "MATIC": np.random.normal(0.001, 0.045, n).tolist()
    }

    print(f"\n📊 Actifs analysés: {list(returns_data.keys())}")

    # Analyse de corrélation
    print(f"\n🔍 Analyse de corrélation...")
    result = await analyzer.analyze(
        asset1="BTC",
        asset2="ETH",
        returns_data=returns_data,
        method=CorrelationMethod.PEARSON
    )

    print(f"   BTC-ETH: {result.correlation:.4f} ({result.strength.value})")
    print(f"   p-value: {result.p_value:.4f}")

    # Matrice de corrélation
    print(f"\n📊 Matrice de corrélation...")
    matrix = await analyzer.matrix(returns_data)
    print(f"   Assets: {matrix.assets}")
    print(f"   Matrice: {matrix.matrix[0][:5]}...")

    # Clustering
    print(f"\n📦 Clustering...")
    clusters = await analyzer.cluster(
        returns_data=returns_data,
        threshold=0.5
    )

    for i, cluster in enumerate(clusters):
        print(f"   Cluster {i+1}: {cluster.assets} (avg corr: {cluster.avg_correlation:.3f})")

    # Métriques
    print(f"\n📈 Métriques de corrélation:")
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    metrics = await analyzer.get_metrics(user_id, returns_data)
    print(f"   Corrélation moyenne: {metrics.avg_correlation:.3f}")
    print(f"   Corrélation max: {metrics.max_correlation:.3f}")
    print(f"   Corrélation min: {metrics.min_correlation:.3f}")
    print(f"   Paires positives: {metrics.positive_pairs}")
    print(f"   Paires négatives: {metrics.negative_pairs}")

    # Recommandations
    print(f"\n💡 Recommandations:")
    recommendations = await analyzer.get_recommendations(returns_data)
    print(f"   Paires hautement corrélées: {len(recommendations['high_correlation_pairs'])}")
    print(f"   Paires à corrélation négative: {len(recommendations['negative_correlation_pairs'])}")
    print(f"   Opportunités de diversification: {len(recommendations['diversification_opportunities'])}")

    # Santé du service
    health = await analyzer.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Analyses: {health['total_analyses']}")
    print(f"   Matrices en cache: {health['cached_matrices']}")

    # Fermeture
    await analyzer.close()

    print("\n" + "=" * 60)
    print("CorrelationAnalyzer NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
