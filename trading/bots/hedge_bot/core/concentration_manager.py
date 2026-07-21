"""
NEXUS AI TRADING SYSTEM - HEDGE BOT CONCENTRATION MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion de la concentration pour le Hedge Bot.
Analyse de la concentration, diversification, et gestion des risques de concentration.

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

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class ConcentrationMetric(Enum):
    """Métriques de concentration."""
    HERFINDAHL = "herfindahl"
    GINI = "gini"
    CR = "cr"  # Concentration Ratio
    HHI = "hhi"  # Herfindahl-Hirschman Index
    HFD = "hfd"  # Hirschman-Herfindahl Index
    ROSENBLUTH = "rosenbluth"
    HALL_TIDEMAN = "hall_tideman"
    THEIL = "theil"
    ENTROPY = "entropy"


class ConcentrationRisk(Enum):
    """Niveaux de risque de concentration."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    CRITICAL = "critical"


@dataclass
class ConcentrationAnalysis:
    """Analyse de concentration."""
    analysis_id: UUID
    user_id: UUID
    metric: ConcentrationMetric
    value: float
    risk_level: ConcentrationRisk
    assets: List[str]
    weights: List[float]
    threshold: float
    recommendation: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "metric": self.metric.value,
            "value": self.value,
            "risk_level": self.risk_level.value,
            "assets": self.assets,
            "weights": self.weights,
            "threshold": self.threshold,
            "recommendation": self.recommendation,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DiversificationMetrics:
    """Métriques de diversification."""
    user_id: UUID
    num_assets: int
    effective_num_assets: float
    concentration_ratio: float
    herfindahl_index: float
    gini_coefficient: float
    diversification_ratio: float
    entropy: float
    max_single_asset_weight: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "num_assets": self.num_assets,
            "effective_num_assets": self.effective_num_assets,
            "concentration_ratio": self.concentration_ratio,
            "herfindahl_index": self.herfindahl_index,
            "gini_coefficient": self.gini_coefficient,
            "diversification_ratio": self.diversification_ratio,
            "entropy": self.entropy,
            "max_single_asset_weight": self.max_single_asset_weight,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE CONCENTRATION MANAGER
# ============================================================================

class ConcentrationManager:
    """
    Gestionnaire de concentration avancé.
    """

    # Seuils de concentration
    CONCENTRATION_THRESHOLDS = {
        "hhi": {
            "very_low": 0.0,
            "low": 0.15,
            "moderate": 0.25,
            "high": 0.45,
            "very_high": 0.65,
            "critical": 0.80
        },
        "cr": {
            "very_low": 0.0,
            "low": 0.20,
            "moderate": 0.35,
            "high": 0.50,
            "very_high": 0.70,
            "critical": 0.85
        },
        "gini": {
            "very_low": 0.0,
            "low": 0.25,
            "moderate": 0.45,
            "high": 0.60,
            "very_high": 0.75,
            "critical": 0.90
        }
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de concentration.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._analysis_cache: Dict[UUID, ConcentrationAnalysis] = {}
        self._metrics_cache: Dict[UUID, DiversificationMetrics] = {}
        self._portfolio_cache: Dict[UUID, Dict[str, float]] = {}
        
        # Métriques
        self._metrics = {
            "total_analyses": 0,
            "by_risk_level": {},
            "by_metric": {},
            "last_analysis": None
        }

        logger.info("ConcentrationManager initialisé avec succès")

    # ========================================================================
    # ANALYSE DE CONCENTRATION
    # ========================================================================

    async def analyze(
        self,
        user_id: UUID,
        assets_weights: Dict[str, float],
        metric: ConcentrationMetric = ConcentrationMetric.HHI,
        threshold: Optional[float] = None,
        metadata: Optional[Dict] = None
    ) -> ConcentrationAnalysis:
        """
        Analyse la concentration d'un portefeuille.

        Args:
            user_id: ID de l'utilisateur
            assets_weights: Poids des actifs
            metric: Métrique de concentration
            threshold: Seuil
            metadata: Métadonnées

        Returns:
            Analyse de concentration
        """
        try:
            analysis_id = uuid4()
            assets = list(assets_weights.keys())
            weights = list(assets_weights.values())

            # Calcul de la métrique
            value = 0.0
            if metric == ConcentrationMetric.HERFINDAHL or metric == ConcentrationMetric.HHI:
                value = sum(w ** 2 for w in weights)
            elif metric == ConcentrationMetric.GINI:
                value = self._calculate_gini(weights)
            elif metric == ConcentrationMetric.CR:
                value = sum(sorted(weights, reverse=True)[:4])
            elif metric == ConcentrationMetric.ENTROPY:
                value = -sum(w * np.log(w) for w in weights if w > 0)
            elif metric == ConcentrationMetric.ROSENBLUTH:
                value = 1 / (2 * sum(w ** 2 for w in weights) - 1)
            elif metric == ConcentrationMetric.HALL_TIDEMAN:
                sorted_weights = sorted(weights, reverse=True)
                value = 1 / (2 * sum(sorted_weights[i] * (i + 1) for i in range(len(sorted_weights))) - 1)

            # Détermination du risque
            risk_level = self._get_risk_level(metric, value, threshold)

            # Recommandation
            recommendation = self._get_recommendation(risk_level, metric, value)

            analysis = ConcentrationAnalysis(
                analysis_id=analysis_id,
                user_id=user_id,
                metric=metric,
                value=value,
                risk_level=risk_level,
                assets=assets,
                weights=weights,
                threshold=threshold or self._get_default_threshold(metric),
                recommendation=recommendation,
                metadata=metadata or {}
            )

            self._analysis_cache[analysis_id] = analysis
            self._metrics["total_analyses"] += 1
            self._metrics["last_analysis"] = datetime.now().isoformat()

            risk_key = risk_level.value
            if risk_key not in self._metrics["by_risk_level"]:
                self._metrics["by_risk_level"][risk_key] = 0
            self._metrics["by_risk_level"][risk_key] += 1

            metric_key = metric.value
            if metric_key not in self._metrics["by_metric"]:
                self._metrics["by_metric"][metric_key] = 0
            self._metrics["by_metric"][metric_key] += 1

            return analysis

        except Exception as e:
            logger.error(f"Erreur d'analyse de concentration: {e}")
            raise

    def _calculate_gini(self, weights: List[float]) -> float:
        """
        Calcule le coefficient de Gini.

        Args:
            weights: Poids

        Returns:
            Coefficient de Gini
        """
        sorted_weights = sorted(weights)
        n = len(sorted_weights)
        total = sum(sorted_weights)
        
        if total == 0:
            return 0.0

        cumulative = 0
        gini = 0
        
        for i, w in enumerate(sorted_weights):
            cumulative += w
            gini += (2 * i + 1) * w
        
        gini = 1 - (gini / (n * total))
        return gini

    def _get_risk_level(
        self,
        metric: ConcentrationMetric,
        value: float,
        threshold: Optional[float] = None
    ) -> ConcentrationRisk:
        """
        Détermine le niveau de risque.

        Args:
            metric: Métrique
            value: Valeur
            threshold: Seuil

        Returns:
            Niveau de risque
        """
        if threshold is not None:
            if value <= threshold * 0.25:
                return ConcentrationRisk.VERY_LOW
            elif value <= threshold * 0.5:
                return ConcentrationRisk.LOW
            elif value <= threshold * 0.75:
                return ConcentrationRisk.MODERATE
            elif value <= threshold * 0.9:
                return ConcentrationRisk.HIGH
            elif value <= threshold:
                return ConcentrationRisk.VERY_HIGH
            else:
                return ConcentrationRisk.CRITICAL

        thresholds = self.CONCENTRATION_THRESHOLDS.get(metric.value, {})
        if not thresholds:
            return ConcentrationRisk.MODERATE

        if value < thresholds["low"]:
            return ConcentrationRisk.VERY_LOW
        elif value < thresholds["moderate"]:
            return ConcentrationRisk.LOW
        elif value < thresholds["high"]:
            return ConcentrationRisk.MODERATE
        elif value < thresholds["very_high"]:
            return ConcentrationRisk.HIGH
        elif value < thresholds["critical"]:
            return ConcentrationRisk.VERY_HIGH
        else:
            return ConcentrationRisk.CRITICAL

    def _get_default_threshold(self, metric: ConcentrationMetric) -> float:
        """
        Récupère le seuil par défaut.

        Args:
            metric: Métrique

        Returns:
            Seuil
        """
        thresholds = self.CONCENTRATION_THRESHOLDS.get(metric.value, {})
        return thresholds.get("critical", 1.0)

    def _get_recommendation(
        self,
        risk_level: ConcentrationRisk,
        metric: ConcentrationMetric,
        value: float
    ) -> str:
        """
        Génère une recommandation.

        Args:
            risk_level: Niveau de risque
            metric: Métrique
            value: Valeur

        Returns:
            Recommandation
        """
        if risk_level == ConcentrationRisk.VERY_LOW:
            return "Portefeuille très bien diversifié. Maintenir la stratégie actuelle."
        elif risk_level == ConcentrationRisk.LOW:
            return "Bonne diversification. Surveiller l'évolution des poids."
        elif risk_level == ConcentrationRisk.MODERATE:
            return "Concentration modérée. Envisager une légère diversification."
        elif risk_level == ConvergenceRisk.HIGH:
            return "Concentration élevée. Réduire l'exposition aux actifs dominants."
        elif risk_level == ConcentrationRisk.VERY_HIGH:
            return "Concentration très élevée. Diversifier d'urgence le portefeuille."
        else:
            return "Concentration critique. Prendre des mesures immédiates de diversification."

    # ========================================================================
    # MÉTRIQUES DE DIVERSIFICATION
    # ========================================================================

    async def get_diversification_metrics(
        self,
        user_id: UUID,
        assets_weights: Dict[str, float]
    ) -> DiversificationMetrics:
        """
        Calcule les métriques de diversification.

        Args:
            user_id: ID de l'utilisateur
            assets_weights: Poids des actifs

        Returns:
            Métriques de diversification
        """
        try:
            weights = list(assets_weights.values())
            n = len(weights)
            total = sum(weights)

            if total == 0:
                return DiversificationMetrics(
                    user_id=user_id,
                    num_assets=0,
                    effective_num_assets=0.0,
                    concentration_ratio=0.0,
                    herfindahl_index=0.0,
                    gini_coefficient=0.0,
                    diversification_ratio=0.0,
                    entropy=0.0,
                    max_single_asset_weight=0.0
                )

            # Normalisation des poids
            normalized_weights = [w / total for w in weights]

            # Herfindahl-Hirschman Index
            hhi = sum(w ** 2 for w in normalized_weights)

            # Nombre effectif d'actifs
            effective_num_assets = 1 / hhi if hhi > 0 else 0

            # Ratio de concentration (top 4)
            top4 = sorted(normalized_weights, reverse=True)[:4]
            concentration_ratio = sum(top4)

            # Coefficient de Gini
            gini = self._calculate_gini(normalized_weights)

            # Ratio de diversification
            diversification_ratio = 1 - hhi

            # Entropie
            entropy = -sum(w * np.log(w) for w in normalized_weights if w > 0)

            # Poids maximum
            max_weight = max(normalized_weights) if normalized_weights else 0

            metrics = DiversificationMetrics(
                user_id=user_id,
                num_assets=n,
                effective_num_assets=effective_num_assets,
                concentration_ratio=concentration_ratio,
                herfindahl_index=hhi,
                gini_coefficient=gini,
                diversification_ratio=diversification_ratio,
                entropy=entropy,
                max_single_asset_weight=max_weight
            )

            self._metrics_cache[user_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques de diversification: {e}")
            return DiversificationMetrics(user_id=user_id)

    # ========================================================================
    # RECOMMANDATIONS DE DIVERSIFICATION
    # ========================================================================

    async def get_diversification_recommendations(
        self,
        user_id: UUID,
        assets_weights: Dict[str, float],
        target_hhi: float = 0.15
    ) -> List[Dict[str, Any]]:
        """
        Génère des recommandations de diversification.

        Args:
            user_id: ID de l'utilisateur
            assets_weights: Poids des actifs
            target_hhi: HHI cible

        Returns:
            Liste des recommandations
        """
        try:
            recommendations = []
            metrics = await self.get_diversification_metrics(user_id, assets_weights)

            if metrics.herfindahl_index > target_hhi:
                # Identifier les actifs surpondérés
                weights = list(assets_weights.values())
                total = sum(weights)
                normalized = [w / total for w in weights]
                assets = list(assets_weights.keys())

                over_weighted = []
                for i, (asset, weight) in enumerate(zip(assets, normalized)):
                    if weight > 1 / (len(assets) * 2):
                        over_weighted.append({
                            "asset": asset,
                            "weight": weight,
                            "suggested_reduction": weight - 1 / len(assets)
                        })

                recommendations.append({
                    "type": "reduce_concentration",
                    "message": f"Réduire la concentration des actifs dominants",
                    "assets_to_reduce": over_weighted[:3],
                    "target_hhi": target_hhi,
                    "current_hhi": metrics.herfindahl_index
                })

                if metrics.effective_num_assets < len(assets) * 0.5:
                    recommendations.append({
                        "type": "add_assets",
                        "message": "Ajouter de nouveaux actifs pour améliorer la diversification",
                        "current_effective": metrics.effective_num_assets,
                        "target_effective": len(assets) * 0.7
                    })

            return recommendations

        except Exception as e:
            logger.error(f"Erreur de génération des recommandations: {e}")
            return []

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_analysis(
        self,
        analysis_id: UUID
    ) -> Optional[ConcentrationAnalysis]:
        """
        Récupère une analyse.

        Args:
            analysis_id: ID de l'analyse

        Returns:
            Analyse ou None
        """
        return self._analysis_cache.get(analysis_id)

    async def get_metrics(
        self,
        user_id: UUID
    ) -> Optional[DiversificationMetrics]:
        """
        Récupère les métriques de diversification.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Métriques ou None
        """
        return self._metrics_cache.get(user_id)

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
                "by_risk_level": self._metrics["by_risk_level"],
                "by_metric": self._metrics["by_metric"],
                "last_analysis": self._metrics["last_analysis"],
                "cached_analyses": len(self._analysis_cache),
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
        logger.info("Fermeture de ConcentrationManager...")
        self._analysis_cache.clear()
        self._metrics_cache.clear()
        self._portfolio_cache.clear()
        logger.info("ConcentrationManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_concentration_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> ConcentrationManager:
    """
    Crée une instance de ConcentrationManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de ConcentrationManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ConcentrationManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ConcentrationMetric",
    "ConcentrationRisk",
    "ConcentrationAnalysis",
    "DiversificationMetrics",
    "ConcentrationManager",
    "create_concentration_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du ConcentrationManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT CONCENTRATION MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    concentration_mgr = create_concentration_manager()

    print(f"\n✅ ConcentrationManager initialisé")

    # Portefeuille de test
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    portfolio = {
        "BTC": 0.40,
        "ETH": 0.25,
        "SOL": 0.15,
        "USDC": 0.10,
        "MATIC": 0.10
    }

    print(f"\n📊 Portefeuille:")
    for asset, weight in portfolio.items():
        print(f"   {asset}: {weight*100:.1f}%")

    # Analyse de concentration
    print(f"\n🔍 Analyse de concentration...")
    analysis = await concentration_mgr.analyze(
        user_id=user_id,
        assets_weights=portfolio,
        metric=ConcentrationMetric.HHI
    )

    print(f"   HHI: {analysis.value:.4f}")
    print(f"   Risque: {analysis.risk_level.value}")
    print(f"   Recommandation: {analysis.recommendation}")

    # Métriques de diversification
    print(f"\n📈 Métriques de diversification:")
    metrics = await concentration_mgr.get_diversification_metrics(
        user_id=user_id,
        assets_weights=portfolio
    )

    print(f"   Nombre d'actifs: {metrics.num_assets}")
    print(f"   Nombre effectif: {metrics.effective_num_assets:.2f}")
    print(f"   HHI: {metrics.herfindahl_index:.4f}")
    print(f"   Coefficient de Gini: {metrics.gini_coefficient:.4f}")
    print(f"   Ratio de diversification: {metrics.diversification_ratio:.4f}")
    print(f"   Poids max: {metrics.max_single_asset_weight*100:.1f}%")

    # Recommandations
    print(f"\n💡 Recommandations de diversification:")
    recommendations = await concentration_mgr.get_diversification_recommendations(
        user_id=user_id,
        assets_weights=portfolio,
        target_hhi=0.15
    )

    for rec in recommendations:
        print(f"   {rec['type']}: {rec['message']}")

    # Santé du service
    health = await concentration_mgr.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Analyses: {health['total_analyses']}")
    print(f"   Par niveau de risque: {health['by_risk_level']}")

    # Fermeture
    await concentration_mgr.close()

    print("\n" + "=" * 60)
    print("ConcentrationManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
