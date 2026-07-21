"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TRAILING STOP MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des trailing stops pour le Hedge Bot.
Gestion des stops suiveurs, activation, mise à jour, et monitoring.

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
    calculate_volatility,
    calculate_sharpe_ratio
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class TrailingStopType(Enum):
    """Types de trailing stop."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    VOLATILITY = "volatility"
    ATR = "atr"
    DYNAMIC = "dynamic"
    SMART = "smart"


class TrailingStopStatus(Enum):
    """Statuts de trailing stop."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class TrailingStop:
    """Trailing stop."""
    stop_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    stop_type: TrailingStopType
    initial_price: Decimal
    current_price: Decimal
    highest_price: Decimal
    lowest_price: Decimal
    stop_price: Decimal
    activation_price: Decimal
    trail_percent: float
    trail_amount: Decimal
    status: TrailingStopStatus
    created_at: datetime
    updated_at: datetime
    triggered_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "stop_id": str(self.stop_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "stop_type": self.stop_type.value,
            "initial_price": str(self.initial_price),
            "current_price": str(self.current_price),
            "highest_price": str(self.highest_price),
            "lowest_price": str(self.lowest_price),
            "stop_price": str(self.stop_price),
            "activation_price": str(self.activation_price),
            "trail_percent": self.trail_percent,
            "trail_amount": str(self.trail_amount),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "metadata": self.metadata
        }


@dataclass
class TrailingStopMetrics:
    """Métriques de trailing stop."""
    stop_id: UUID
    total_distance: Decimal
    current_distance: Decimal
    max_distance: Decimal
    avg_distance: Decimal
    stop_efficiency: float
    profit_protected: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "stop_id": str(self.stop_id),
            "total_distance": str(self.total_distance),
            "current_distance": str(self.current_distance),
            "max_distance": str(self.max_distance),
            "avg_distance": str(self.avg_distance),
            "stop_efficiency": self.stop_efficiency,
            "profit_protected": str(self.profit_protected),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE TRAILING STOP MANAGER
# ============================================================================

class TrailingStopManager:
    """
    Gestionnaire de trailing stops avancé.
    """

    # Facteurs de volatilité par défaut
    VOLATILITY_FACTORS = {
        "low": 1.0,
        "medium": 1.5,
        "high": 2.0
    }

    # Seuils d'efficacité
    EFFICIENCY_THRESHOLDS = {
        "poor": 0.3,
        "average": 0.5,
        "good": 0.7,
        "excellent": 0.9
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de trailing stops.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._stops: Dict[UUID, TrailingStop] = {}
        self._metrics_cache: Dict[UUID, TrailingStopMetrics] = {}
        self._price_cache: Dict[str, List[Decimal]] = {}
        
        # Métriques
        self._metrics = {
            "total_stops": 0,
            "active_stops": 0,
            "triggered_stops": 0,
            "by_type": {},
            "by_status": {},
            "last_update": None
        }

        logger.info("TrailingStopManager initialisé avec succès")

    # ========================================================================
    # CRÉATION DE TRAILING STOP
    # ========================================================================

    async def create_trailing_stop(
        self,
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        initial_price: Decimal,
        stop_type: TrailingStopType = TrailingStopType.PERCENTAGE,
        trail_percent: float = 0.02,
        trail_amount: Optional[Decimal] = None,
        activation_price: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> TrailingStop:
        """
        Crée un trailing stop.

        Args:
            position_id: ID de la position
            user_id: ID de l'utilisateur
            symbol: Symbole
            initial_price: Prix initial
            stop_type: Type de trailing stop
            trail_percent: Pourcentage de suivi
            trail_amount: Montant de suivi
            activation_price: Prix d'activation
            metadata: Métadonnées

        Returns:
            Trailing stop créé
        """
        try:
            stop_id = uuid4()
            now = datetime.now()

            # Calcul du prix d'activation
            if activation_price is None:
                activation_price = initial_price

            # Calcul du stop price initial
            stop_price = self._calculate_stop_price(
                initial_price,
                stop_type,
                trail_percent,
                trail_amount
            )

            stop = TrailingStop(
                stop_id=stop_id,
                position_id=position_id,
                user_id=user_id,
                symbol=symbol,
                stop_type=stop_type,
                initial_price=initial_price,
                current_price=initial_price,
                highest_price=initial_price,
                lowest_price=initial_price,
                stop_price=stop_price,
                activation_price=activation_price,
                trail_percent=trail_percent,
                trail_amount=trail_amount or Decimal("0"),
                status=TrailingStopStatus.INACTIVE,
                created_at=now,
                updated_at=now,
                metadata=metadata or {}
            )

            self._stops[stop_id] = stop
            self._metrics["total_stops"] += 1

            stop_type_key = stop_type.value
            if stop_type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][stop_type_key] = 0
            self._metrics["by_type"][stop_type_key] += 1

            logger.info(f"Trailing stop créé: {stop_id}")
            return stop

        except Exception as e:
            logger.error(f"Erreur de création du trailing stop: {e}")
            raise

    def _calculate_stop_price(
        self,
        price: Decimal,
        stop_type: TrailingStopType,
        trail_percent: float,
        trail_amount: Optional[Decimal]
    ) -> Decimal:
        """
        Calcule le prix du stop.

        Args:
            price: Prix actuel
            stop_type: Type de stop
            trail_percent: Pourcentage de suivi
            trail_amount: Montant de suivi

        Returns:
            Prix du stop
        """
        if stop_type == TrailingStopType.PERCENTAGE:
            return price * Decimal(str(1 - trail_percent))
        elif stop_type == TrailingStopType.FIXED and trail_amount:
            return price - trail_amount
        else:
            return price * Decimal(str(1 - trail_percent))

    # ========================================================================
    # MISE À JOUR DU TRAILING STOP
    # ========================================================================

    async def update_stop(
        self,
        stop_id: UUID,
        current_price: Decimal
    ) -> Optional[TrailingStop]:
        """
        Met à jour un trailing stop.

        Args:
            stop_id: ID du stop
            current_price: Prix actuel

        Returns:
            Trailing stop mis à jour
        """
        try:
            stop = self._stops.get(stop_id)
            if not stop:
                return None

            if stop.status != TrailingStopStatus.ACTIVE:
                return stop

            # Mise à jour des prix extrêmes
            if current_price > stop.highest_price:
                stop.highest_price = current_price
            if current_price < stop.lowest_price:
                stop.lowest_price = current_price

            # Calcul du nouveau stop price
            new_stop_price = self._calculate_stop_price(
                current_price,
                stop.stop_type,
                stop.trail_percent,
                stop.trail_amount
            )

            # Mise à jour du stop (seulement s'il est plus haut)
            if new_stop_price > stop.stop_price:
                stop.stop_price = new_stop_price

            stop.current_price = current_price
            stop.updated_at = datetime.now()

            # Vérification du déclenchement
            if current_price <= stop.stop_price:
                stop.status = TrailingStopStatus.TRIGGERED
                stop.triggered_at = datetime.now()
                self._metrics["triggered_stops"] += 1
                logger.info(f"Trailing stop déclenché: {stop_id}")

            self._metrics["last_update"] = datetime.now().isoformat()

            return stop

        except Exception as e:
            logger.error(f"Erreur de mise à jour du trailing stop: {e}")
            return None

    # ========================================================================
    # ACTIVATION DU TRAILING STOP
    # ========================================================================

    async def activate_stop(
        self,
        stop_id: UUID,
        current_price: Decimal
    ) -> bool:
        """
        Active un trailing stop.

        Args:
            stop_id: ID du stop
            current_price: Prix actuel

        Returns:
            True si activé
        """
        try:
            stop = self._stops.get(stop_id)
            if not stop:
                return False

            if stop.status != TrailingStopStatus.INACTIVE:
                return False

            # Vérification du prix d'activation
            if current_price >= stop.activation_price:
                stop.status = TrailingStopStatus.ACTIVE
                stop.current_price = current_price
                stop.highest_price = current_price
                stop.lowest_price = current_price
                stop.updated_at = datetime.now()
                self._metrics["active_stops"] += 1

                logger.info(f"Trailing stop activé: {stop_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Erreur d'activation du trailing stop: {e}")
            return False

    # ========================================================================
    # MÉTRIQUES DU TRAILING STOP
    # ========================================================================

    async def get_metrics(
        self,
        stop_id: UUID
    ) -> Optional[TrailingStopMetrics]:
        """
        Calcule les métriques d'un trailing stop.

        Args:
            stop_id: ID du stop

        Returns:
            Métriques du trailing stop
        """
        try:
            stop = self._stops.get(stop_id)
            if not stop:
                return None

            # Distances
            total_distance = stop.highest_price - stop.initial_price
            current_distance = stop.current_price - stop.initial_price
            max_distance = stop.highest_price - stop.initial_price

            # Distance moyenne
            avg_distance = (total_distance + current_distance) / 2

            # Efficacité du stop
            if total_distance > 0:
                stop_efficiency = float(current_distance / total_distance)
            else:
                stop_efficiency = 1.0

            # Profit protégé
            profit_protected = stop.highest_price - stop.stop_price

            metrics = TrailingStopMetrics(
                stop_id=stop_id,
                total_distance=total_distance,
                current_distance=current_distance,
                max_distance=max_distance,
                avg_distance=avg_distance,
                stop_efficiency=stop_efficiency,
                profit_protected=profit_protected
            )

            self._metrics_cache[stop_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques: {e}")
            return None

    # ========================================================================
    # ANALYSE DU TRAILING STOP
    # ========================================================================

    async def analyze_stop(
        self,
        stop_id: UUID,
        historical_prices: List[Decimal]
    ) -> Dict[str, Any]:
        """
        Analyse un trailing stop.

        Args:
            stop_id: ID du stop
            historical_prices: Prix historiques

        Returns:
            Analyse du trailing stop
        """
        try:
            stop = self._stops.get(stop_id)
            if not stop:
                return {"error": "Stop non trouvé"}

            # Simulation du stop sur l'historique
            triggers = []
            highest = stop.initial_price
            stop_price = self._calculate_stop_price(
                stop.initial_price,
                stop.stop_type,
                stop.trail_percent,
                stop.trail_amount
            )

            for price in historical_prices:
                if price > highest:
                    highest = price
                    new_stop = self._calculate_stop_price(
                        price,
                        stop.stop_type,
                        stop.trail_percent,
                        stop.trail_amount
                    )
                    if new_stop > stop_price:
                        stop_price = new_stop

                if price <= stop_price:
                    triggers.append({
                        "price": price,
                        "stop_price": stop_price,
                        "peak": highest
                    })

            return {
                "stop_id": str(stop_id),
                "total_triggers": len(triggers),
                "first_trigger": triggers[0] if triggers else None,
                "best_trigger": max(triggers, key=lambda x: x["price"]) if triggers else None,
                "worst_trigger": min(triggers, key=lambda x: x["price"]) if triggers else None,
                "trigger_frequency": len(triggers) / len(historical_prices) if historical_prices else 0,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'analyse du trailing stop: {e}")
            return {"error": str(e)}

    # ========================================================================
    # OPTIMISATION DU TRAILING STOP
    # ========================================================================

    async def optimize_stop(
        self,
        position_id: UUID,
        historical_prices: List[Decimal],
        stop_types: Optional[List[TrailingStopType]] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Optimise les paramètres du trailing stop.

        Args:
            position_id: ID de la position
            historical_prices: Prix historiques
            stop_types: Types de stop à tester
            metadata: Métadonnées

        Returns:
            Paramètres optimisés
        """
        try:
            if stop_types is None:
                stop_types = [TrailingStopType.PERCENTAGE]

            results = []
            best_result = None
            best_score = -float('inf')

            # Test de différentes configurations
            for stop_type in stop_types:
                if stop_type == TrailingStopType.PERCENTAGE:
                    for pct in [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]:
                        result = await self._simulate_stop(
                            position_id,
                            historical_prices,
                            stop_type,
                            trail_percent=pct
                        )
                        results.append(result)
                        
                        score = result.get("profit_protected", 0) - result.get("trigger_frequency", 0) * 100
                        if score > best_score:
                            best_score = score
                            best_result = result

            return {
                "best_parameters": best_result.get("params", {}) if best_result else {},
                "best_score": best_score,
                "total_simulations": len(results),
                "results": results[:10],  # Top 10 résultats
                "recommendations": await self._generate_recommendations(best_result),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'optimisation du trailing stop: {e}")
            return {"error": str(e)}

    async def _simulate_stop(
        self,
        position_id: UUID,
        historical_prices: List[Decimal],
        stop_type: TrailingStopType,
        trail_percent: float = 0.02,
        trail_amount: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Simule un trailing stop.

        Args:
            position_id: ID de la position
            historical_prices: Prix historiques
            stop_type: Type de stop
            trail_percent: Pourcentage de suivi
            trail_amount: Montant de suivi

        Returns:
            Résultats de simulation
        """
        try:
            initial_price = historical_prices[0] if historical_prices else Decimal("100")
            highest = initial_price
            stop_price = self._calculate_stop_price(
                initial_price,
                stop_type,
                trail_percent,
                trail_amount
            )

            triggered = False
            trigger_price = None
            peak_price = None

            for price in historical_prices:
                if price > highest:
                    highest = price
                    new_stop = self._calculate_stop_price(
                        price,
                        stop_type,
                        trail_percent,
                        trail_amount
                    )
                    if new_stop > stop_price:
                        stop_price = new_stop

                if price <= stop_price and not triggered:
                    triggered = True
                    trigger_price = price
                    peak_price = highest

            profit_protected = (peak_price - stop_price) if peak_price and stop_price else Decimal("0")

            return {
                "params": {
                    "stop_type": stop_type.value,
                    "trail_percent": trail_percent,
                    "trail_amount": float(trail_amount) if trail_amount else 0
                },
                "triggered": triggered,
                "trigger_price": float(trigger_price) if trigger_price else None,
                "peak_price": float(peak_price) if peak_price else None,
                "profit_protected": float(profit_protected),
                "trigger_frequency": 1 if triggered else 0
            }

        except Exception as e:
            logger.error(f"Erreur de simulation: {e}")
            return {"error": str(e)}

    async def _generate_recommendations(
        self,
        best_result: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Génère des recommandations.

        Args:
            best_result: Meilleur résultat

        Returns:
            Liste des recommandations
        """
        recommendations = []

        if not best_result:
            return ["Aucune recommandation disponible"]

        if best_result.get("triggered", False):
            recommendations.append(
                f"Utiliser un trailing stop {best_result['params']['stop_type']} "
                f"avec {best_result['params']['trail_percent']*100:.1f}% de suivi"
            )

            if best_result.get("profit_protected", 0) > 0:
                recommendations.append(
                    f"Profit protégé: {best_result['profit_protected']:.2f}"
                )
        else:
            recommendations.append("Ajuster les paramètres du trailing stop")

        return recommendations

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_stop(
        self,
        stop_id: UUID
    ) -> Optional[TrailingStop]:
        """
        Récupère un trailing stop.

        Args:
            stop_id: ID du stop

        Returns:
            Trailing stop ou None
        """
        return self._stops.get(stop_id)

    async def get_stops(
        self,
        position_id: UUID,
        status: Optional[TrailingStopStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TrailingStop]:
        """
        Récupère les trailing stops d'une position.

        Args:
            position_id: ID de la position
            status: Filtrer par statut
            limit: Nombre de stops
            offset: Décalage

        Returns:
            Liste des trailing stops
        """
        stops = [s for s in self._stops.values() if s.position_id == position_id]

        if status:
            stops = [s for s in stops if s.status == status]

        stops.sort(key=lambda x: x.created_at, reverse=True)
        return stops[offset:offset + limit]

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
                "total_stops": self._metrics["total_stops"],
                "active_stops": self._metrics["active_stops"],
                "triggered_stops": self._metrics["triggered_stops"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_update": self._metrics["last_update"],
                "cached_stops": len(self._stops),
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
        logger.info("Fermeture de TrailingStopManager...")
        self._stops.clear()
        self._metrics_cache.clear()
        self._price_cache.clear()
        logger.info("TrailingStopManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_trailing_stop_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> TrailingStopManager:
    """
    Crée une instance de TrailingStopManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de TrailingStopManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return TrailingStopManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TrailingStopType",
    "TrailingStopStatus",
    "TrailingStop",
    "TrailingStopMetrics",
    "TrailingStopManager",
    "create_trailing_stop_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du TrailingStopManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TRAILING STOP MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    manager = create_trailing_stop_manager()

    print(f"\n✅ TrailingStopManager initialisé")

    # Création d'un trailing stop
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un trailing stop...")
    stop = await manager.create_trailing_stop(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        initial_price=Decimal("50000"),
        stop_type=TrailingStopType.PERCENTAGE,
        trail_percent=0.02,
        activation_price=Decimal("51000"),
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {stop.stop_id}")
    print(f"   Symbole: {stop.symbol}")
    print(f"   Prix initial: ${stop.initial_price}")
    print(f"   Prix d'activation: ${stop.activation_price}")
    print(f"   Stop price: ${stop.stop_price}")
    print(f"   Statut: {stop.status.value}")

    # Activation du stop
    print(f"\n🔒 Activation du stop...")
    await manager.activate_stop(
        stop_id=stop.stop_id,
        current_price=Decimal("51050")
    )
    print(f"   Statut: {stop.status.value}")

    # Mise à jour du stop
    print(f"\n🔄 Mise à jour du stop...")
    prices = [51100, 51500, 51800, 52000, 51850, 51600, 51400]
    
    for price in prices:
        updated_stop = await manager.update_stop(
            stop_id=stop.stop_id,
            current_price=Decimal(str(price))
        )
        if updated_stop:
            print(f"   Prix: ${price} - Stop: ${updated_stop.stop_price}")

    # Métriques
    print(f"\n📈 Métriques du stop:")
    metrics = await manager.get_metrics(stop.stop_id)
    if metrics:
        print(f"   Distance totale: ${metrics.total_distance}")
        print(f"   Distance actuelle: ${metrics.current_distance}")
        print(f"   Efficacité: {metrics.stop_efficiency:.2%}")
        print(f"   Profit protégé: ${metrics.profit_protected}")

    # Analyse du stop
    print(f"\n🔍 Analyse du stop:")
    historical_prices = [Decimal(str(p)) for p in [50000, 50200, 50500, 50800, 51000, 51200, 51500, 51300]]
    analysis = await manager.analyze_stop(
        stop_id=stop.stop_id,
        historical_prices=historical_prices
    )
    print(f"   Déclenchements: {analysis.get('total_triggers', 0)}")
    print(f"   Fréquence: {analysis.get('trigger_frequency', 0):.2%}")

    # Optimisation
    print(f"\n🎯 Optimisation du stop:")
    optimization = await manager.optimize_stop(
        position_id=position_id,
        historical_prices=historical_prices
    )
    print(f"   Meilleurs paramètres: {optimization.get('best_parameters', {})}")
    print(f"   Score: {optimization.get('best_score', 0):.2f}")
    
    recommendations = optimization.get('recommendations', [])
    for rec in recommendations:
        print(f"   💡 {rec}")

    # Santé du service
    health = await manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Stops totaux: {health['total_stops']}")
    print(f"   Stops actifs: {health['active_stops']}")
    print(f"   Stops déclenchés: {health['triggered_stops']}")

    # Fermeture
    await manager.close()

    print("\n" + "=" * 60)
    print("TrailingStopManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
