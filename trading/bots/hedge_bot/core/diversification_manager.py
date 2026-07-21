"""
NEXUS AI TRADING SYSTEM - HEDGE BOT DIVERSIFICATION MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion de la diversification pour le Hedge Bot.
Optimisation de la diversification, allocation d'actifs, et rééquilibrage.

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
from scipy.optimize import minimize, differential_evolution

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_correlation
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class DiversificationStrategy(Enum):
    """Stratégies de diversification."""
    EQUAL_WEIGHT = "equal_weight"
    VOLATILITY_WEIGHTED = "volatility_weighted"
    RISK_PARITY = "risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    CUSTOM = "custom"


class DiversificationMetric(Enum):
    """Métriques de diversification."""
    HERFINDAHL = "herfindahl"
    EFFECTIVE_NUMBER = "effective_number"
    CONCENTRATION_RATIO = "concentration_ratio"
    DIVERSIFICATION_RATIO = "diversification_ratio"
    RISK_CONTRIBUTION = "risk_contribution"
    CORRELATION = "correlation"


@dataclass
class DiversificationAnalysis:
    """Analyse de diversification."""
    analysis_id: UUID
    user_id: UUID
    strategy: DiversificationStrategy
    assets: List[str]
    weights: List[float]
    metrics: Dict[str, Any]
    recommendations: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "strategy": self.strategy.value,
            "assets": self.assets,
            "weights": self.weights,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DiversificationMetrics:
    """Métriques de diversification."""
    user_id: UUID
    num_assets: int
    effective_num_assets: float
    herfindahl_index: float
    concentration_ratio: float
    diversification_ratio: float
    risk_contributions: Dict[str, float]
    correlation_avg: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "num_assets": self.num_assets,
            "effective_num_assets": self.effective_num_assets,
            "herfindahl_index": self.herfindahl_index,
            "concentration_ratio": self.concentration_ratio,
            "diversification_ratio": self.diversification_ratio,
            "risk_contributions": self.risk_contributions,
            "correlation_avg": self.correlation_avg,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE DIVERSIFICATION MANAGER
# ============================================================================

class DiversificationManager:
    """
    Gestionnaire de diversification avancé.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de diversification.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._analysis_cache: Dict[UUID, DiversificationAnalysis] = {}
        self._metrics_cache: Dict[UUID, DiversificationMetrics] = {}
        self._portfolio_cache: Dict[UUID, Dict[str, float]] = {}
        
        # Métriques
        self._metrics = {
            "total_analyses": 0,
            "by_strategy": {},
            "last_analysis": None
        }

        logger.info("DiversificationManager initialisé avec succès")

    # ========================================================================
    # ANALYSE DE DIVERSIFICATION
    # ========================================================================

    async def analyze(
        self,
        user_id: UUID,
        assets_data: Dict[str, Dict[str, Any]],
        strategy: DiversificationStrategy = DiversificationStrategy.RISK_PARITY,
        constraints: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> DiversificationAnalysis:
        """
        Analyse la diversification d'un portefeuille.

        Args:
            user_id: ID de l'utilisateur
            assets_data: Données des actifs (prix, rendements, etc.)
            strategy: Stratégie de diversification
            constraints: Contraintes
            metadata: Métadonnées

        Returns:
            Analyse de diversification
        """
        try:
            analysis_id = uuid4()
            now = datetime.now()

            # Extraction des données
            assets = list(assets_data.keys())
            returns = [assets_data[a].get("returns", []) for a in assets]
            
            # Calcul des poids optimaux
            weights = await self._calculate_weights(
                assets_data,
                strategy,
                constraints
            )

            # Calcul des métriques
            metrics = await self._calculate_metrics(assets, weights, returns)

            # Recommandations
            recommendations = await self._generate_recommendations(
                assets,
                weights,
                metrics,
                strategy
            )

            analysis = DiversificationAnalysis(
                analysis_id=analysis_id,
                user_id=user_id,
                strategy=strategy,
                assets=assets,
                weights=weights,
                metrics=metrics,
                recommendations=recommendations,
                metadata=metadata or {}
            )

            self._analysis_cache[analysis_id] = analysis
            self._metrics["total_analyses"] += 1
            self._metrics["last_analysis"] = now.isoformat()

            strategy_key = strategy.value
            if strategy_key not in self._metrics["by_strategy"]:
                self._metrics["by_strategy"][strategy_key] = 0
            self._metrics["by_strategy"][strategy_key] += 1

            return analysis

        except Exception as e:
            logger.error(f"Erreur d'analyse de diversification: {e}")
            raise

    async def _calculate_weights(
        self,
        assets_data: Dict[str, Dict[str, Any]],
        strategy: DiversificationStrategy,
        constraints: Optional[Dict]
    ) -> List[float]:
        """
        Calcule les poids optimaux.

        Args:
            assets_data: Données des actifs
            strategy: Stratégie
            constraints: Contraintes

        Returns:
            Poids optimaux
        """
        n = len(assets_data)
        assets = list(assets_data.keys())

        if strategy == DiversificationStrategy.EQUAL_WEIGHT:
            return [1.0 / n] * n

        elif strategy == DiversificationStrategy.VOLATILITY_WEIGHTED:
            volatilities = [
                np.std(assets_data[a].get("returns", [0])) + 0.001
                for a in assets
            ]
            inv_vol = [1.0 / v for v in volatilities]
            total = sum(inv_vol)
            return [v / total for v in inv_vol]

        elif strategy == DiversificationStrategy.RISK_PARITY:
            return await self._risk_parity_weights(assets_data)

        elif strategy == DiversificationStrategy.MAX_DIVERSIFICATION:
            return await self._max_diversification_weights(assets_data)

        elif strategy == DiversificationStrategy.MIN_VARIANCE:
            return await self._min_variance_weights(assets_data)

        elif strategy == DiversificationStrategy.MAX_SHARPE:
            return await self._max_sharpe_weights(assets_data)

        else:
            return [1.0 / n] * n

    async def _risk_parity_weights(
        self,
        assets_data: Dict[str, Dict[str, Any]]
    ) -> List[float]:
        """
        Calcule les poids Risk Parity.

        Args:
            assets_data: Données des actifs

        Returns:
            Poids Risk Parity
        """
        try:
            n = len(assets_data)
            returns = [assets_data[a].get("returns", []) for a in assets_data.keys()]
            
            if not returns or len(returns[0]) < 2:
                return [1.0 / n] * n

            # Matrice de covariance
            returns_df = pd.DataFrame(returns).T
            cov_matrix = returns_df.cov().values

            # Fonction objectif
            def objective(weights):
                portfolio_var = np.dot(weights.T, np.dot(cov_matrix, weights))
                risk_contrib = []
                for i in range(n):
                    contrib = weights[i] * np.dot(cov_matrix[i], weights) / portfolio_var
                    risk_contrib.append(contrib)
                return np.std(risk_contrib)

            # Contraintes
            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}
            ]
            bounds = [(0.05, 0.95) for _ in range(n)]

            # Optimisation
            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return result.x.tolist()
            return [1.0 / n] * n

        except Exception as e:
            logger.error(f"Erreur Risk Parity: {e}")
            return [1.0 / len(assets_data)] * len(assets_data)

    async def _max_diversification_weights(
        self,
        assets_data: Dict[str, Dict[str, Any]]
    ) -> List[float]:
        """
        Calcule les poids de diversification maximale.

        Args:
            assets_data: Données des actifs

        Returns:
            Poids de diversification maximale
        """
        try:
            n = len(assets_data)
            returns = [assets_data[a].get("returns", []) for a in assets_data.keys()]
            
            if not returns or len(returns[0]) < 2:
                return [1.0 / n] * n

            returns_df = pd.DataFrame(returns).T
            cov_matrix = returns_df.cov().values
            volatilities = np.sqrt(np.diag(cov_matrix))

            # Fonction objectif
            def objective(weights):
                portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                weighted_avg_vol = np.dot(weights, volatilities)
                return -weighted_avg_vol / portfolio_vol

            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}
            ]
            bounds = [(0, 1) for _ in range(n)]

            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return result.x.tolist()
            return [1.0 / n] * n

        except Exception as e:
            logger.error(f"Erreur Max Diversification: {e}")
            return [1.0 / len(assets_data)] * len(assets_data)

    async def _min_variance_weights(
        self,
        assets_data: Dict[str, Dict[str, Any]]
    ) -> List[float]:
        """
        Calcule les poids de variance minimale.

        Args:
            assets_data: Données des actifs

        Returns:
            Poids de variance minimale
        """
        try:
            n = len(assets_data)
            returns = [assets_data[a].get("returns", []) for a in assets_data.keys()]
            
            if not returns or len(returns[0]) < 2:
                return [1.0 / n] * n

            returns_df = pd.DataFrame(returns).T
            cov_matrix = returns_df.cov().values

            def objective(weights):
                return np.dot(weights.T, np.dot(cov_matrix, weights))

            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}
            ]
            bounds = [(0, 1) for _ in range(n)]

            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return result.x.tolist()
            return [1.0 / n] * n

        except Exception as e:
            logger.error(f"Erreur Min Variance: {e}")
            return [1.0 / len(assets_data)] * len(assets_data)

    async def _max_sharpe_weights(
        self,
        assets_data: Dict[str, Dict[str, Any]]
    ) -> List[float]:
        """
        Calcule les poids de Sharpe maximal.

        Args:
            assets_data: Données des actifs

        Returns:
            Poids de Sharpe maximal
        """
        try:
            n = len(assets_data)
            returns = [assets_data[a].get("returns", []) for a in assets_data.keys()]
            
            if not returns or len(returns[0]) < 2:
                return [1.0 / n] * n

            returns_df = pd.DataFrame(returns).T
            mean_returns = returns_df.mean().values
            cov_matrix = returns_df.cov().values
            risk_free_rate = 0.02 / 252

            def objective(weights):
                portfolio_return = np.dot(weights, mean_returns)
                portfolio_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                return -(portfolio_return - risk_free_rate) / portfolio_vol

            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}
            ]
            bounds = [(0, 1) for _ in range(n)]

            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return result.x.tolist()
            return [1.0 / n] * n

        except Exception as e:
            logger.error(f"Erreur Max Sharpe: {e}")
            return [1.0 / len(assets_data)] * len(assets_data)

    # ========================================================================
    # MÉTRIQUES DE DIVERSIFICATION
    # ========================================================================

    async def _calculate_metrics(
        self,
        assets: List[str],
        weights: List[float],
        returns: List[List[float]]
    ) -> Dict[str, Any]:
        """
        Calcule les métriques de diversification.

        Args:
            assets: Liste des actifs
            weights: Poids
            returns: Rendements

        Returns:
            Métriques
        """
        try:
            n = len(assets)
            total_weight = sum(weights)
            normalized_weights = [w / total_weight for w in weights]

            # Herfindahl Index
            herfindahl = sum(w ** 2 for w in normalized_weights)

            # Nombre effectif
            effective_num = 1 / herfindahl if herfindahl > 0 else 1

            # Ratio de concentration (top 4)
            top4 = sorted(normalized_weights, reverse=True)[:4]
            concentration_ratio = sum(top4)

            # Ratio de diversification
            diversification_ratio = 1 - herfindahl

            # Risque contributions
            risk_contributions = {}
            if returns and len(returns) > 0 and len(returns[0]) > 1:
                returns_df = pd.DataFrame(returns).T
                cov_matrix = returns_df.cov().values
                portfolio_var = np.dot(weights, np.dot(cov_matrix, weights))
                
                for i, asset in enumerate(assets):
                    if portfolio_var > 0:
                        contrib = weights[i] * np.dot(cov_matrix[i], weights) / portfolio_var
                        risk_contributions[asset] = float(contrib)

            # Corrélation moyenne
            correlation_avg = 0
            if returns and len(returns) > 1:
                correlations = []
                for i in range(len(assets)):
                    for j in range(i+1, len(assets)):
                        corr = np.corrcoef(returns[i], returns[j])[0][1]
                        if not np.isnan(corr):
                            correlations.append(corr)
                if correlations:
                    correlation_avg = np.mean(correlations)

            # Volatilité
            volatility = 0
            if returns and len(returns) > 0 and len(returns[0]) > 1:
                portfolio_returns = np.dot(normalized_weights, np.array(returns))
                volatility = np.std(portfolio_returns) * np.sqrt(252)

            # Sharpe Ratio
            sharpe_ratio = 0
            if returns and len(returns) > 0 and len(returns[0]) > 1:
                portfolio_returns = np.dot(normalized_weights, np.array(returns))
                sharpe_ratio = calculate_sharpe_ratio(portfolio_returns.tolist())

            # Max Drawdown
            max_drawdown = 0
            if returns and len(returns) > 0 and len(returns[0]) > 1:
                portfolio_returns = np.dot(normalized_weights, np.array(returns))
                max_drawdown = calculate_max_drawdown(portfolio_returns.tolist())

            return {
                "herfindahl_index": herfindahl,
                "effective_number": effective_num,
                "concentration_ratio": concentration_ratio,
                "diversification_ratio": diversification_ratio,
                "risk_contributions": risk_contributions,
                "correlation_avg": correlation_avg,
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio,
                "max_drawdown": max_drawdown
            }

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques: {e}")
            return {}

    async def _generate_recommendations(
        self,
        assets: List[str],
        weights: List[float],
        metrics: Dict[str, Any],
        strategy: DiversificationStrategy
    ) -> List[str]:
        """
        Génère des recommandations.

        Args:
            assets: Liste des actifs
            weights: Poids
            metrics: Métriques
            strategy: Stratégie

        Returns:
            Liste des recommandations
        """
        recommendations = []

        # Concentration
        if metrics.get("herfindahl_index", 0) > 0.5:
            recommendations.append("Réduire la concentration en ajoutant plus d'actifs")

        # Diversification
        if metrics.get("diversification_ratio", 0) < 0.3:
            recommendations.append("Améliorer la diversification du portefeuille")

        # Corrélation
        if metrics.get("correlation_avg", 1) > 0.7:
            recommendations.append("Ajouter des actifs faiblement corrélés")

        # Volatilité
        if metrics.get("volatility", 0) > 0.3:
            recommendations.append("Réduire la volatilité en ajoutant des actifs stables")

        # Sharpe Ratio
        if metrics.get("sharpe_ratio", 0) < 0.5:
            recommendations.append("Améliorer le ratio de Sharpe")

        return recommendations

    # ========================================================================
    # RÉÉQUILIBRAGE
    # ========================================================================

    async def rebalance(
        self,
        user_id: UUID,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        tolerance: float = 0.01
    ) -> Dict[str, Any]:
        """
        Génère des instructions de rééquilibrage.

        Args:
            user_id: ID de l'utilisateur
            current_weights: Poids actuels
            target_weights: Poids cibles
            tolerance: Tolérance

        Returns:
            Instructions de rééquilibrage
        """
        try:
            instructions = []
            total_trades = 0
            total_value = 0

            for asset, target in target_weights.items():
                current = current_weights.get(asset, 0)
                diff = target - current

                if abs(diff) > tolerance:
                    side = "buy" if diff > 0 else "sell"
                    amount = abs(diff)
                    
                    instructions.append({
                        "asset": asset,
                        "side": side,
                        "amount": amount,
                        "current_weight": current,
                        "target_weight": target
                    })
                    
                    total_trades += 1
                    total_value += amount

            return {
                "instructions": instructions,
                "total_trades": total_trades,
                "total_value": total_value,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur de rééquilibrage: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_analysis(
        self,
        analysis_id: UUID
    ) -> Optional[DiversificationAnalysis]:
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
                "by_strategy": self._metrics["by_strategy"],
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
        logger.info("Fermeture de DiversificationManager...")
        self._analysis_cache.clear()
        self._metrics_cache.clear()
        self._portfolio_cache.clear()
        logger.info("DiversificationManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_diversification_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> DiversificationManager:
    """
    Crée une instance de DiversificationManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de DiversificationManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return DiversificationManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "DiversificationStrategy",
    "DiversificationMetric",
    "DiversificationAnalysis",
    "DiversificationMetrics",
    "DiversificationManager",
    "create_diversification_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du DiversificationManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT DIVERSIFICATION MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    manager = create_diversification_manager()

    print(f"\n✅ DiversificationManager initialisé")

    # Données des actifs
    np.random.seed(42)
    n = 252
    
    assets_data = {
        "BTC": {
            "returns": np.random.normal(0.001, 0.03, n).tolist(),
            "price": 50000
        },
        "ETH": {
            "returns": np.random.normal(0.001, 0.035, n).tolist(),
            "price": 3000
        },
        "SOL": {
            "returns": np.random.normal(0.001, 0.04, n).tolist(),
            "price": 150
        },
        "USDC": {
            "returns": np.random.normal(0, 0.001, n).tolist(),
            "price": 1
        }
    }

    print(f"\n📊 Actifs analysés: {list(assets_data.keys())}")

    # Analyse de diversification
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n🔍 Analyse de diversification...")
    
    analysis = await manager.analyze(
        user_id=user_id,
        assets_data=assets_data,
        strategy=DiversificationStrategy.RISK_PARITY
    )

    print(f"   Stratégie: {analysis.strategy.value}")
    print(f"   Poids optimaux:")
    for asset, weight in zip(analysis.assets, analysis.weights):
        print(f"      {asset}: {weight*100:.1f}%")

    # Métriques
    print(f"\n📈 Métriques de diversification:")
    metrics = analysis.metrics
    print(f"   Herfindahl Index: {metrics.get('herfindahl_index', 0):.3f}")
    print(f"   Nombre effectif: {metrics.get('effective_number', 0):.2f}")
    print(f"   Ratio de diversification: {metrics.get('diversification_ratio', 0):.3f}")
    print(f"   Corrélation moyenne: {metrics.get('correlation_avg', 0):.3f}")
    print(f"   Volatilité: {metrics.get('volatility', 0):.2%}")
    print(f"   Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")

    # Recommandations
    print(f"\n💡 Recommandations:")
    for rec in analysis.recommendations:
        print(f"   {rec}")

    # Rééquilibrage
    print(f"\n🔄 Rééquilibrage...")
    current_weights = {
        "BTC": 0.40,
        "ETH": 0.30,
        "SOL": 0.20,
        "USDC": 0.10
    }
    
    target_weights = dict(zip(analysis.assets, analysis.weights))
    
    rebalance = await manager.rebalance(
        user_id=user_id,
        current_weights=current_weights,
        target_weights=target_weights,
        tolerance=0.02
    )

    print(f"   Instructions de rééquilibrage:")
    for instruction in rebalance.get('instructions', []):
        print(f"      {instruction['side']} {instruction['asset']}: {instruction['amount']*100:.1f}%")

    # Santé du service
    health = await manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Analyses: {health['total_analyses']}")
    print(f"   Par stratégie: {health['by_strategy']}")

    # Fermeture
    await manager.close()

    print("\n" + "=" * 60)
    print("DiversificationManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    from ..utils.helpers import calculate_max_drawdown
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
