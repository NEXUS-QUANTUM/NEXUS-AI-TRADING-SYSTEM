"""
NEXUS AI TRADING SYSTEM - HEDGE BOT ASSET ALLOCATOR MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'allocation d'actifs pour le Hedge Bot.
Gestion de l'allocation, diversification, rééquilibrage, et optimisation de portefeuille.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from scipy.optimize import minimize, differential_evolution
from scipy.stats import norm

from ..utils.helpers import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_volatility,
    calculate_beta,
    calculate_alpha
)
from ..utils.math_utils import MathUtils, create_math_utils

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class AllocationStrategy(Enum):
    """Stratégies d'allocation."""
    EQUAL_WEIGHT = "equal_weight"
    MARKET_CAP = "market_cap"
    VOLATILITY_WEIGHTED = "volatility_weighted"
    MIN_VARIANCE = "min_variance"
    MAX_SHARPE = "max_sharpe"
    MAX_DIVERSIFICATION = "max_diversification"
    RISK_PARITY = "risk_parity"
    TARGET_RISK = "target_risk"
    BLACK_LITTERMAN = "black_litterman"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    CUSTOM = "custom"


class AllocationStatus(Enum):
    """Statuts d'allocation."""
    PENDING = "pending"
    ACTIVE = "active"
    REBALANCING = "rebalancing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class Asset:
    """Actif."""
    asset_id: UUID
    symbol: str
    name: str
    asset_type: str  # crypto, stock, forex, commodity, etc.
    price: Decimal
    price_usd: Decimal
    quantity: Decimal
    value: Decimal
    value_usd: Decimal
    weight: float  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "asset_id": str(self.asset_id),
            "symbol": self.symbol,
            "name": self.name,
            "asset_type": self.asset_type,
            "price": str(self.price),
            "price_usd": str(self.price_usd),
            "quantity": str(self.quantity),
            "value": str(self.value),
            "value_usd": str(self.value_usd),
            "weight": self.weight,
            "metadata": self.metadata,
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Allocation:
    """Allocation."""
    allocation_id: UUID
    user_id: UUID
    strategy: AllocationStrategy
    assets: List[Asset]
    total_value: Decimal
    total_value_usd: Decimal
    status: AllocationStatus
    created_at: datetime
    updated_at: datetime
    target_weights: Dict[str, float] = field(default_factory=dict)
    current_weights: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "allocation_id": str(self.allocation_id),
            "user_id": str(self.user_id),
            "strategy": self.strategy.value,
            "assets": [a.to_dict() for a in self.assets],
            "total_value": str(self.total_value),
            "total_value_usd": str(self.total_value_usd),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "target_weights": self.target_weights,
            "current_weights": self.current_weights,
            "metrics": self.metrics,
            "metadata": self.metadata
        }


@dataclass
class RebalanceResult:
    """Résultat de rééquilibrage."""
    rebalance_id: UUID
    allocation_id: UUID
    user_id: UUID
    trades: List[Dict[str, Any]]
    total_cost: Decimal
    total_cost_usd: Decimal
    total_value: Decimal
    total_value_usd: Decimal
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "rebalance_id": str(self.rebalance_id),
            "allocation_id": str(self.allocation_id),
            "user_id": str(self.user_id),
            "trades": self.trades,
            "total_cost": str(self.total_cost),
            "total_cost_usd": str(self.total_cost_usd),
            "total_value": str(self.total_value),
            "total_value_usd": str(self.total_value_usd),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE ASSET ALLOCATOR
# ============================================================================

class AssetAllocator:
    """
    Gestionnaire d'allocation d'actifs.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise l'allocateur d'actifs.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Utilitaires
        self.math_utils = create_math_utils()
        
        # Cache
        self._allocations: Dict[UUID, Allocation] = {}
        self._assets: Dict[UUID, Asset] = {}
        self._rebalances: Dict[UUID, RebalanceResult] = {}
        
        # Métriques
        self._metrics = {
            "total_allocations": 0,
            "total_rebalances": 0,
            "total_value_usd": Decimal("0"),
            "by_strategy": {},
            "by_status": {},
            "last_allocation": None
        }

        logger.info("AssetAllocator initialisé avec succès")

    # ========================================================================
    # CRÉATION D'ALLOCATION
    # ========================================================================

    async def create_allocation(
        self,
        user_id: UUID,
        strategy: AllocationStrategy,
        assets_data: List[Dict[str, Any]],
        target_weights: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict] = None
    ) -> Allocation:
        """
        Crée une allocation.

        Args:
            user_id: ID de l'utilisateur
            strategy: Stratégie d'allocation
            assets_data: Données des actifs
            target_weights: Poids cibles
            metadata: Métadonnées

        Returns:
            Allocation créée
        """
        try:
            allocation_id = uuid4()
            now = datetime.now()

            # Création des actifs
            assets = []
            for asset_data in assets_data:
                asset = Asset(
                    asset_id=uuid4(),
                    symbol=asset_data["symbol"],
                    name=asset_data.get("name", asset_data["symbol"]),
                    asset_type=asset_data.get("asset_type", "crypto"),
                    price=Decimal(str(asset_data.get("price", 0))),
                    price_usd=Decimal(str(asset_data.get("price_usd", 0))),
                    quantity=Decimal(str(asset_data.get("quantity", 0))),
                    value=Decimal(str(asset_data.get("value", 0))),
                    value_usd=Decimal(str(asset_data.get("value_usd", 0))),
                    weight=asset_data.get("weight", 0.0),
                    metadata=asset_data.get("metadata", {})
                )
                assets.append(asset)
                self._assets[asset.asset_id] = asset

            # Calcul des poids
            if not target_weights:
                target_weights = await self._calculate_weights(strategy, assets)

            total_value = sum(a.value for a in assets)
            total_value_usd = sum(a.value_usd for a in assets)

            # Calcul des poids actuels
            current_weights = {}
            for asset in assets:
                if total_value_usd > 0:
                    current_weights[asset.symbol] = float(asset.value_usd / total_value_usd)

            # Métriques d'allocation
            metrics = await self._calculate_metrics(assets, target_weights)

            allocation = Allocation(
                allocation_id=allocation_id,
                user_id=user_id,
                strategy=strategy,
                assets=assets,
                total_value=total_value,
                total_value_usd=total_value_usd,
                status=AllocationStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                target_weights=target_weights,
                current_weights=current_weights,
                metrics=metrics,
                metadata=metadata or {}
            )

            # Stockage
            self._allocations[allocation_id] = allocation
            self._metrics["total_allocations"] += 1
            self._metrics["total_value_usd"] += total_value_usd

            strategy_key = strategy.value
            if strategy_key not in self._metrics["by_strategy"]:
                self._metrics["by_strategy"][strategy_key] = 0
            self._metrics["by_strategy"][strategy_key] += 1

            self._metrics["last_allocation"] = now.isoformat()

            # Sauvegarde Redis
            if self.redis:
                await self._save_allocation(allocation)

            logger.info(f"Allocation créée: {allocation_id} - {strategy.value}")
            return allocation

        except Exception as e:
            logger.error(f"Erreur lors de la création de l'allocation: {e}")
            raise

    async def _calculate_weights(
        self,
        strategy: AllocationStrategy,
        assets: List[Asset]
    ) -> Dict[str, float]:
        """
        Calcule les poids selon la stratégie.

        Args:
            strategy: Stratégie d'allocation
            assets: Liste des actifs

        Returns:
            Poids par actif
        """
        weights = {}
        n = len(assets)

        if strategy == AllocationStrategy.EQUAL_WEIGHT:
            for asset in assets:
                weights[asset.symbol] = 1.0 / n

        elif strategy == AllocationStrategy.MARKET_CAP:
            total_cap = sum(a.value_usd for a in assets)
            if total_cap > 0:
                for asset in assets:
                    weights[asset.symbol] = float(asset.value_usd / total_cap)

        elif strategy == AllocationStrategy.VOLATILITY_WEIGHTED:
            volatilities = []
            for asset in assets:
                vol = await self._get_volatility(asset.symbol)
                volatilities.append(vol)
            
            inv_vol = [1.0 / v if v > 0 else 0 for v in volatilities]
            total_inv = sum(inv_vol)
            
            if total_inv > 0:
                for i, asset in enumerate(assets):
                    weights[asset.symbol] = inv_vol[i] / total_inv

        elif strategy == AllocationStrategy.MIN_VARIANCE:
            weights = await self._min_variance_allocation(assets)

        elif strategy == AllocationStrategy.MAX_SHARPE:
            weights = await self._max_sharpe_allocation(assets)

        elif strategy == AllocationStrategy.RISK_PARITY:
            weights = await self._risk_parity_allocation(assets)

        elif strategy == AllocationStrategy.TARGET_RISK:
            weights = await self._target_risk_allocation(assets)

        else:
            # Poids égaux par défaut
            for asset in assets:
                weights[asset.symbol] = 1.0 / n

        # Normalisation
        total = sum(weights.values())
        if total > 0:
            for key in weights:
                weights[key] /= total

        return weights

    async def _min_variance_allocation(
        self,
        assets: List[Asset]
    ) -> Dict[str, float]:
        """
        Calcule l'allocation à variance minimale.

        Args:
            assets: Liste des actifs

        Returns:
            Poids optimaux
        """
        try:
            n = len(assets)
            
            # Récupération des données historiques
            returns = []
            for asset in assets:
                hist_returns = await self._get_historical_returns(asset.symbol)
                returns.append(hist_returns)

            if not returns or len(returns[0]) < 2:
                return {}

            # Matrice de covariance
            returns_df = pd.DataFrame(returns).T
            cov_matrix = returns_df.cov().values

            # Fonction objectif
            def objective(weights):
                return np.dot(weights.T, np.dot(cov_matrix, weights))

            # Contraintes
            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}  # Somme = 1
            ]
            bounds = [(0, 1) for _ in range(n)]

            # Optimisation
            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return {assets[i].symbol: result.x[i] for i in range(n)}
            return {}

        except Exception as e:
            logger.error(f"Erreur d'allocation min variance: {e}")
            return {}

    async def _max_sharpe_allocation(
        self,
        assets: List[Asset]
    ) -> Dict[str, float]:
        """
        Calcule l'allocation à Sharpe maximal.

        Args:
            assets: Liste des actifs

        Returns:
            Poids optimaux
        """
        try:
            n = len(assets)
            risk_free_rate = 0.02

            # Récupération des données
            returns = []
            for asset in assets:
                hist_returns = await self._get_historical_returns(asset.symbol)
                returns.append(hist_returns)

            if not returns or len(returns[0]) < 2:
                return {}

            # Moyennes et covariance
            returns_df = pd.DataFrame(returns).T
            mean_returns = returns_df.mean().values
            cov_matrix = returns_df.cov().values

            # Fonction objectif (Sharpe négatif)
            def objective(weights):
                portfolio_return = np.dot(weights, mean_returns)
                portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
                sharpe = (portfolio_return - risk_free_rate / 365) / portfolio_std
                return -sharpe

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
                return {assets[i].symbol: result.x[i] for i in range(n)}
            return {}

        except Exception as e:
            logger.error(f"Erreur d'allocation max Sharpe: {e}")
            return {}

    async def _risk_parity_allocation(
        self,
        assets: List[Asset]
    ) -> Dict[str, float]:
        """
        Calcule l'allocation Risk Parity.

        Args:
            assets: Liste des actifs

        Returns:
            Poids optimaux
        """
        try:
            n = len(assets)
            
            # Récupération des volatilités
            volatilities = []
            for asset in assets:
                vol = await self._get_volatility(asset.symbol)
                volatilities.append(vol)

            # Fonction objectif
            def objective(weights):
                risk_contributions = [
                    weights[i] * volatilities[i] for i in range(n)
                ]
                target_risk = sum(risk_contributions) / n
                return sum((rc - target_risk) ** 2 for rc in risk_contributions)

            constraints = [
                {'type': 'eq', 'fun': lambda x: sum(x) - 1}
            ]
            bounds = [(0.05, 0.95) for _ in range(n)]

            result = minimize(
                objective,
                [1.0 / n] * n,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )

            if result.success:
                return {assets[i].symbol: result.x[i] for i in range(n)}
            return {}

        except Exception as e:
            logger.error(f"Erreur d'allocation risk parity: {e}")
            return {}

    async def _target_risk_allocation(
        self,
        assets: List[Asset]
    ) -> Dict[str, float]:
        """
        Calcule l'allocation à risque cible.

        Args:
            assets: Liste des actifs

        Returns:
            Poids optimaux
        """
        try:
            n = len(assets)
            target_vol = self.config.get("target_volatility", 0.15)
            
            # Récupération des volatilités
            volatilities = []
            for asset in assets:
                vol = await self._get_volatility(asset.symbol)
                volatilities.append(vol)

            # Calcul des poids basés sur la volatilité
            inv_vol = [1.0 / v if v > 0 else 0 for v in volatilities]
            total_inv = sum(inv_vol)
            
            if total_inv == 0:
                return {}

            weights = [iv / total_inv for iv in inv_vol]
            
            # Ajustement pour le risque cible
            current_vol = sum(w * v for w, v in zip(weights, volatilities))
            if current_vol > 0:
                scale = target_vol / current_vol
                weights = [w * scale for w in weights]

            # Normalisation
            total = sum(weights)
            if total > 0:
                weights = [w / total for w in weights]

            return {assets[i].symbol: weights[i] for i in range(n)}

        except Exception as e:
            logger.error(f"Erreur d'allocation target risk: {e}")
            return {}

    # ========================================================================
    # RÉÉQUILIBRAGE
    # ========================================================================

    async def rebalance(
        self,
        allocation_id: UUID,
        execute_trades: bool = True,
        metadata: Optional[Dict] = None
    ) -> RebalanceResult:
        """
        Rééquilibre une allocation.

        Args:
            allocation_id: ID de l'allocation
            execute_trades: Exécuter les trades
            metadata: Métadonnées

        Returns:
            Résultat du rééquilibrage
        """
        try:
            allocation = self._allocations.get(allocation_id)
            if not allocation:
                raise ValueError(f"Allocation {allocation_id} non trouvée")

            rebalance_id = uuid4()
            now = datetime.now()

            allocation.status = AllocationStatus.REBALANCING

            # Calcul des trades nécessaires
            trades = []
            total_cost = Decimal("0")
            total_cost_usd = Decimal("0")

            for asset in allocation.assets:
                current_weight = allocation.current_weights.get(asset.symbol, 0)
                target_weight = allocation.target_weights.get(asset.symbol, 0)
                
                weight_diff = target_weight - current_weight
                
                if abs(weight_diff) > self.config.get("rebalance_threshold", 0.01):
                    trade_value = allocation.total_value_usd * Decimal(str(abs(weight_diff)))
                    
                    trade = {
                        "symbol": asset.symbol,
                        "side": "buy" if weight_diff > 0 else "sell",
                        "amount": str(trade_value),
                        "quantity": str(trade_value / asset.price_usd) if asset.price_usd > 0 else "0",
                        "price": str(asset.price_usd),
                        "weight_diff": weight_diff
                    }
                    trades.append(trade)
                    
                    if weight_diff > 0:
                        total_cost += trade_value
                    total_cost_usd += trade_value

            # Exécution des trades
            if execute_trades and trades:
                # Simulation d'exécution
                for trade in trades:
                    logger.info(f"Trade exécuté: {trade['side']} {trade['quantity']} {trade['symbol']}")

            # Mise à jour de l'allocation
            allocation.status = AllocationStatus.COMPLETED
            allocation.updated_at = now

            # Création du résultat
            result = RebalanceResult(
                rebalance_id=rebalance_id,
                allocation_id=allocation_id,
                user_id=allocation.user_id,
                trades=trades,
                total_cost=total_cost,
                total_cost_usd=total_cost_usd,
                total_value=allocation.total_value,
                total_value_usd=allocation.total_value_usd,
                status="completed",
                created_at=now,
                completed_at=datetime.now(),
                metadata=metadata or {}
            )

            self._rebalances[rebalance_id] = result
            self._metrics["total_rebalances"] += 1

            return result

        except Exception as e:
            logger.error(f"Erreur lors du rééquilibrage: {e}")
            allocation.status = AllocationStatus.ERROR
            raise

    # ========================================================================
    # MÉTRIQUES D'ALLOCATION
    # ========================================================================

    async def _calculate_metrics(
        self,
        assets: List[Asset],
        target_weights: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Calcule les métriques d'allocation.

        Args:
            assets: Liste des actifs
            target_weights: Poids cibles

        Returns:
            Métriques
        """
        try:
            metrics = {
                "diversification": 0.0,
                "concentration": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "number_of_assets": len(assets),
                "effective_number": 0.0
            }

            # Diversification (indice de Herfindahl)
            herfindahl = sum(w ** 2 for w in target_weights.values())
            metrics["diversification"] = 1 - herfindahl
            metrics["effective_number"] = 1 / herfindahl if herfindahl > 0 else 1

            # Concentration
            max_weight = max(target_weights.values()) if target_weights else 0
            metrics["concentration"] = max_weight

            # Calcul des métriques de performance (simplifié)
            returns = []
            for asset in assets:
                hist_returns = await self._get_historical_returns(asset.symbol)
                if hist_returns:
                    returns.append(hist_returns)

            if returns:
                # Portfolio returns
                weights_array = np.array([target_weights.get(asset.symbol, 0) for asset in assets])
                returns_array = np.array(returns)
                
                if len(returns_array) > 0 and len(returns_array[0]) > 1:
                    portfolio_returns = np.dot(weights_array, returns_array)
                    
                    metrics["sharpe_ratio"] = calculate_sharpe_ratio(portfolio_returns.tolist())
                    metrics["sortino_ratio"] = calculate_sortino_ratio(portfolio_returns.tolist())
                    metrics["volatility"] = calculate_volatility(portfolio_returns.tolist())
                    metrics["max_drawdown"] = calculate_max_drawdown(portfolio_returns.tolist())

            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques: {e}")
            return {}

    # ========================================================================
    # RÉCUPÉRATION DE DONNÉES
    # ========================================================================

    async def _get_volatility(self, symbol: str) -> float:
        """
        Récupère la volatilité d'un actif.

        Args:
            symbol: Symbole de l'actif

        Returns:
            Volatilité annualisée
        """
        try:
            # Simulation de volatilité
            return 0.3 + 0.2 * np.random.random()
        except Exception:
            return 0.3

    async def _get_historical_returns(self, symbol: str) -> List[float]:
        """
        Récupère les rendements historiques d'un actif.

        Args:
            symbol: Symbole de l'actif

        Returns:
            Liste des rendements
        """
        try:
            # Simulation de rendements
            return list(np.random.normal(0.001, 0.02, 30))
        except Exception:
            return []

    # ========================================================================
    # STOCKAGE
    # ========================================================================

    async def _save_allocation(self, allocation: Allocation) -> None:
        """
        Sauvegarde une allocation dans Redis.

        Args:
            allocation: Allocation à sauvegarder
        """
        try:
            key = f"allocation:{allocation.allocation_id}"
            await self.redis.setex(
                key,
                86400 * 30,  # 30 jours
                json.dumps(allocation.to_dict())
            )
        except Exception as e:
            logger.error(f"Erreur de sauvegarde de l'allocation: {e}")

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_allocation(
        self,
        allocation_id: UUID
    ) -> Optional[Allocation]:
        """
        Récupère une allocation.

        Args:
            allocation_id: ID de l'allocation

        Returns:
            Allocation ou None
        """
        return self._allocations.get(allocation_id)

    async def get_all_allocations(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[Allocation]:
        """
        Récupère les allocations d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            limit: Nombre d'allocations
            offset: Décalage

        Returns:
            Liste des allocations
        """
        allocations = [
            a for a in self._allocations.values()
            if a.user_id == user_id
        ]
        allocations.sort(key=lambda x: x.created_at, reverse=True)
        return allocations[offset:offset + limit]

    async def get_rebalance(
        self,
        rebalance_id: UUID
    ) -> Optional[RebalanceResult]:
        """
        Récupère un résultat de rééquilibrage.

        Args:
            rebalance_id: ID du rééquilibrage

        Returns:
            Résultat de rééquilibrage
        """
        return self._rebalances.get(rebalance_id)

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
                "total_allocations": self._metrics["total_allocations"],
                "total_rebalances": self._metrics["total_rebalances"],
                "total_value_usd": str(self._metrics["total_value_usd"]),
                "by_strategy": self._metrics["by_strategy"],
                "by_status": self._metrics["by_status"],
                "last_allocation": self._metrics["last_allocation"],
                "cached_allocations": len(self._allocations),
                "cached_rebalances": len(self._rebalances),
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
        logger.info("Fermeture de AssetAllocator...")
        self._allocations.clear()
        self._assets.clear()
        self._rebalances.clear()
        logger.info("AssetAllocator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_asset_allocator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> AssetAllocator:
    """
    Crée une instance de AssetAllocator.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de AssetAllocator
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return AssetAllocator(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AllocationStrategy",
    "AllocationStatus",
    "Asset",
    "Allocation",
    "RebalanceResult",
    "AssetAllocator",
    "create_asset_allocator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de l'allocateur d'actifs."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT ASSET ALLOCATOR")
    print("=" * 60)

    # Création de l'allocateur
    allocator = create_asset_allocator()

    print(f"\n✅ AssetAllocator initialisé")

    # Données des actifs
    assets_data = [
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "asset_type": "crypto",
            "price": 50000,
            "price_usd": 50000,
            "quantity": 0.1,
            "value": 5000,
            "value_usd": 5000
        },
        {
            "symbol": "ETH",
            "name": "Ethereum",
            "asset_type": "crypto",
            "price": 3000,
            "price_usd": 3000,
            "quantity": 1.0,
            "value": 3000,
            "value_usd": 3000
        },
        {
            "symbol": "SOL",
            "name": "Solana",
            "asset_type": "crypto",
            "price": 150,
            "price_usd": 150,
            "quantity": 10,
            "value": 1500,
            "value_usd": 1500
        }
    ]

    # Création d'une allocation
    print(f"\n📊 Création d'une allocation...")
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    allocation = await allocator.create_allocation(
        user_id=user_id,
        strategy=AllocationStrategy.RISK_PARITY,
        assets_data=assets_data,
        metadata={"purpose": "example"}
    )

    print(f"   ID: {allocation.allocation_id}")
    print(f"   Stratégie: {allocation.strategy.value}")
    print(f"   Actifs: {len(allocation.assets)}")
    print(f"   Valeur totale: ${allocation.total_value_usd}")

    # Affichage des poids
    print(f"\n📈 Poids cibles:")
    for symbol, weight in allocation.target_weights.items():
        print(f"   {symbol}: {weight*100:.1f}%")

    # Métriques d'allocation
    print(f"\n📊 Métriques:")
    for key, value in allocation.metrics.items():
        print(f"   {key}: {value}")

    # Rééquilibrage
    print(f"\n🔄 Rééquilibrage...")
    rebalance = await allocator.rebalance(
        allocation_id=allocation.allocation_id,
        execute_trades=True
    )

    print(f"   ID: {rebalance.rebalance_id}")
    print(f"   Trades: {len(rebalance.trades)}")
    print(f"   Coût total: ${rebalance.total_cost_usd}")

    # Santé du service
    health = await allocator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Allocations: {health['total_allocations']}")
    print(f"   Rééquilibrages: {health['total_rebalances']}")
    print(f"   Valeur totale: ${health['total_value_usd']}")

    # Fermeture
    await allocator.close()

    print("\n" + "=" * 60)
    print("AssetAllocator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
