"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TAKE PROFIT MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des take profits pour le Hedge Bot.
Gestion des prises de profit, niveaux, scaling, et optimisation.

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

class TakeProfitType(Enum):
    """Types de take profit."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    VOLATILITY = "volatility"
    ATR = "atr"
    FIBONACCI = "fibonacci"
    RESISTANCE = "resistance"
    DYNAMIC = "dynamic"
    SCALING = "scaling"


class TakeProfitStatus(Enum):
    """Statuts de take profit."""
    PENDING = "pending"
    ACTIVE = "active"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class TakeProfitLevel:
    """Niveau de take profit."""
    level_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    entry_price: Decimal
    target_price: Decimal
    target_percent: float
    quantity: Decimal
    quantity_remaining: Decimal
    status: TakeProfitStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    triggered_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "level_id": str(self.level_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "entry_price": str(self.entry_price),
            "target_price": str(self.target_price),
            "target_percent": self.target_percent,
            "quantity": str(self.quantity),
            "quantity_remaining": str(self.quantity_remaining),
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None
        }


@dataclass
class TakeProfitSchedule:
    """Calendrier de take profit."""
    schedule_id: UUID
    position_id: UUID
    user_id: UUID
    symbol: str
    levels: List[TakeProfitLevel]
    total_quantity: Decimal
    remaining_quantity: Decimal
    total_target_percent: float
    status: TakeProfitStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "schedule_id": str(self.schedule_id),
            "position_id": str(self.position_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "levels": [l.to_dict() for l in self.levels],
            "total_quantity": str(self.total_quantity),
            "remaining_quantity": str(self.remaining_quantity),
            "total_target_percent": self.total_target_percent,
            "status": self.status.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class TakeProfitMetrics:
    """Métriques de take profit."""
    position_id: UUID
    total_profit: Decimal
    total_profit_usd: Decimal
    average_profit_percent: float
    max_profit_percent: float
    min_profit_percent: float
    profit_factor: float
    win_rate: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "position_id": str(self.position_id),
            "total_profit": str(self.total_profit),
            "total_profit_usd": str(self.total_profit_usd),
            "average_profit_percent": self.average_profit_percent,
            "max_profit_percent": self.max_profit_percent,
            "min_profit_percent": self.min_profit_percent,
            "profit_factor": self.profit_factor,
            "win_rate": self.win_rate,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE TAKE PROFIT MANAGER
# ============================================================================

class TakeProfitManager:
    """
    Gestionnaire de take profits avancé.
    """

    # Niveaux Fibonacci
    FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0]

    # Seuils de scaling
    SCALING_THRESHOLDS = {
        "low": 0.1,
        "medium": 0.25,
        "high": 0.5
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de take profits.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._levels: Dict[UUID, TakeProfitLevel] = {}
        self._schedules: Dict[UUID, TakeProfitSchedule] = {}
        self._metrics_cache: Dict[UUID, TakeProfitMetrics] = {}
        
        # Métriques
        self._metrics = {
            "total_levels": 0,
            "total_schedules": 0,
            "completed_levels": 0,
            "by_type": {},
            "by_status": {},
            "last_update": None
        }

        logger.info("TakeProfitManager initialisé avec succès")

    # ========================================================================
    # CRÉATION DE TAKE PROFIT
    # ========================================================================

    async def create_take_profit(
        self,
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        entry_price: Decimal,
        target_percent: float,
        quantity: Decimal,
        take_profit_type: TakeProfitType = TakeProfitType.PERCENTAGE,
        metadata: Optional[Dict] = None
    ) -> TakeProfitLevel:
        """
        Crée un niveau de take profit.

        Args:
            position_id: ID de la position
            user_id: ID de l'utilisateur
            symbol: Symbole
            entry_price: Prix d'entrée
            target_percent: Pourcentage cible
            quantity: Quantité
            take_profit_type: Type de take profit
            metadata: Métadonnées

        Returns:
            Niveau de take profit
        """
        try:
            level_id = uuid4()
            now = datetime.now()

            # Calcul du prix cible
            target_price = entry_price * Decimal(str(1 + target_percent))

            level = TakeProfitLevel(
                level_id=level_id,
                position_id=position_id,
                user_id=user_id,
                symbol=symbol,
                entry_price=entry_price,
                target_price=target_price,
                target_percent=target_percent,
                quantity=quantity,
                quantity_remaining=quantity,
                status=TakeProfitStatus.PENDING,
                metadata=metadata or {}
            )

            self._levels[level_id] = level
            self._metrics["total_levels"] += 1

            type_key = take_profit_type.value
            if type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][type_key] = 0
            self._metrics["by_type"][type_key] += 1

            logger.info(f"Take profit créé: {level_id}")
            return level

        except Exception as e:
            logger.error(f"Erreur de création du take profit: {e}")
            raise

    # ========================================================================
    # CRÉATION DE SCHÉMA DE TAKE PROFIT
    # ========================================================================

    async def create_schedule(
        self,
        position_id: UUID,
        user_id: UUID,
        symbol: str,
        entry_price: Decimal,
        total_quantity: Decimal,
        levels_config: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> TakeProfitSchedule:
        """
        Crée un calendrier de take profit.

        Args:
            position_id: ID de la position
            user_id: ID de l'utilisateur
            symbol: Symbole
            entry_price: Prix d'entrée
            total_quantity: Quantité totale
            levels_config: Configuration des niveaux
            metadata: Métadonnées

        Returns:
            Calendrier de take profit
        """
        try:
            schedule_id = uuid4()
            now = datetime.now()

            levels = []
            total_target_percent = 0

            for config in levels_config:
                target_percent = config.get("target_percent", 0.05)
                quantity = config.get("quantity", total_quantity / len(levels_config))
                
                level = await self.create_take_profit(
                    position_id=position_id,
                    user_id=user_id,
                    symbol=symbol,
                    entry_price=entry_price,
                    target_percent=target_percent,
                    quantity=quantity,
                    take_profit_type=TakeProfitType.SCALING,
                    metadata=config.get("metadata", {})
                )
                levels.append(level)
                total_target_percent += target_percent

            schedule = TakeProfitSchedule(
                schedule_id=schedule_id,
                position_id=position_id,
                user_id=user_id,
                symbol=symbol,
                levels=levels,
                total_quantity=total_quantity,
                remaining_quantity=total_quantity,
                total_target_percent=total_target_percent,
                status=TakeProfitStatus.PENDING,
                metadata=metadata or {}
            )

            self._schedules[schedule_id] = schedule
            self._metrics["total_schedules"] += 1

            return schedule

        except Exception as e:
            logger.error(f"Erreur de création du calendrier: {e}")
            raise

    # ========================================================================
    # MISE À JOUR DU TAKE PROFIT
    # ========================================================================

    async def update_level(
        self,
        level_id: UUID,
        current_price: Decimal
    ) -> Optional[TakeProfitLevel]:
        """
        Met à jour un niveau de take profit.

        Args:
            level_id: ID du niveau
            current_price: Prix actuel

        Returns:
            Niveau de take profit mis à jour
        """
        try:
            level = self._levels.get(level_id)
            if not level:
                return None

            if level.status in [TakeProfitStatus.COMPLETED, TakeProfitStatus.CANCELLED]:
                return level

            # Vérification du déclenchement
            if current_price >= level.target_price:
                level.status = TakeProfitStatus.COMPLETED
                level.quantity_remaining = Decimal("0")
                level.triggered_at = datetime.now()
                self._metrics["completed_levels"] += 1
                self._metrics["last_update"] = datetime.now().isoformat()

            status_key = level.status.value
            if status_key not in self._metrics["by_status"]:
                self._metrics["by_status"][status_key] = 0
            self._metrics["by_status"][status_key] += 1

            return level

        except Exception as e:
            logger.error(f"Erreur de mise à jour du take profit: {e}")
            return None

    # ========================================================================
    # CALCUL DES NIVEAUX
    # ========================================================================

    async def calculate_levels(
        self,
        entry_price: Decimal,
        take_profit_type: TakeProfitType,
        volatility: Optional[float] = None,
        atr: Optional[Decimal] = None,
        resistance_levels: Optional[List[Decimal]] = None,
        metadata: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Calcule les niveaux de take profit.

        Args:
            entry_price: Prix d'entrée
            take_profit_type: Type de take profit
            volatility: Volatilité
            atr: ATR
            resistance_levels: Niveaux de résistance
            metadata: Métadonnées

        Returns:
            Niveaux calculés
        """
        try:
            levels = []

            if take_profit_type == TakeProfitType.PERCENTAGE:
                for pct in [0.05, 0.10, 0.15, 0.20]:
                    target = entry_price * Decimal(str(1 + pct))
                    levels.append({
                        "target_percent": pct,
                        "target_price": target,
                        "weight": 1 / len([0.05, 0.10, 0.15, 0.20])
                    })

            elif take_profit_type == TakeProfitType.FIBONACCI:
                for fib in self.FIBONACCI_LEVELS:
                    if fib > 0:
                        target = entry_price * Decimal(str(1 + fib))
                        levels.append({
                            "target_percent": fib,
                            "target_price": target,
                            "weight": 1 / len([f for f in self.FIBONACCI_LEVELS if f > 0])
                        })

            elif take_profit_type == TakeProfitType.VOLATILITY and volatility:
                multipliers = [1.0, 1.5, 2.0, 3.0]
                for mult in multipliers:
                    target = entry_price * Decimal(str(1 + volatility * mult))
                    levels.append({
                        "target_percent": volatility * mult,
                        "target_price": target,
                        "weight": 1 / len(multipliers)
                    })

            elif take_profit_type == TakeProfitType.RESISTANCE and resistance_levels:
                for resistance in resistance_levels:
                    if resistance > entry_price:
                        target_percent = float((resistance - entry_price) / entry_price)
                        levels.append({
                            "target_percent": target_percent,
                            "target_price": resistance,
                            "weight": 1 / len(resistance_levels)
                        })

            return levels

        except Exception as e:
            logger.error(f"Erreur de calcul des niveaux: {e}")
            return []

    # ========================================================================
    # OPTIMISATION DU TAKE PROFIT
    # ========================================================================

    async def optimize(
        self,
        position_id: UUID,
        historical_prices: List[Decimal],
        target_percent_range: Tuple[float, float] = (0.01, 0.20),
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Optimise les paramètres de take profit.

        Args:
            position_id: ID de la position
            historical_prices: Prix historiques
            target_percent_range: Plage de pourcentages cibles
            metadata: Métadonnées

        Returns:
            Paramètres optimisés
        """
        try:
            results = []
            best_result = None
            best_score = -float('inf')

            entry_price = historical_prices[0] if historical_prices else Decimal("100")

            # Test de différents pourcentages
            step = 0.005
            current = target_percent_range[0]
            while current <= target_percent_range[1]:
                # Simulation du take profit
                result = await self._simulate_take_profit(
                    position_id,
                    historical_prices,
                    entry_price,
                    current
                )
                results.append(result)
                
                score = result.get("profit_factor", 0) * result.get("win_rate", 0)
                if score > best_score:
                    best_score = score
                    best_result = result
                
                current += step

            return {
                "best_parameters": {
                    "target_percent": best_result.get("target_percent", 0) if best_result else 0,
                    "target_price": str(best_result.get("target_price", Decimal("0"))) if best_result else "0",
                    "score": best_score
                } if best_result else {},
                "total_simulations": len(results),
                "results": results[:10],
                "recommendations": await self._generate_recommendations(best_result),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur d'optimisation du take profit: {e}")
            return {"error": str(e)}

    async def _simulate_take_profit(
        self,
        position_id: UUID,
        historical_prices: List[Decimal],
        entry_price: Decimal,
        target_percent: float
    ) -> Dict[str, Any]:
        """
        Simule un take profit.

        Args:
            position_id: ID de la position
            historical_prices: Prix historiques
            entry_price: Prix d'entrée
            target_percent: Pourcentage cible

        Returns:
            Résultats de simulation
        """
        try:
            target_price = entry_price * Decimal(str(1 + target_percent))
            triggered = False
            trigger_price = None
            max_price = entry_price

            for price in historical_prices:
                if price > max_price:
                    max_price = price
                if price >= target_price and not triggered:
                    triggered = True
                    trigger_price = price

            profit = (trigger_price - entry_price) if triggered else Decimal("0")
            profit_percent = (profit / entry_price) if entry_price > 0 else Decimal("0")

            return {
                "target_percent": target_percent,
                "target_price": float(target_price),
                "triggered": triggered,
                "trigger_price": float(trigger_price) if trigger_price else None,
                "profit": float(profit),
                "profit_percent": float(profit_percent),
                "max_price": float(max_price)
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
                f"Take profit optimal: {best_result['target_percent']*100:.1f}% "
                f"(profit: {best_result.get('profit_percent', 0)*100:.1f}%)"
            )
        else:
            recommendations.append("Ajuster le pourcentage cible à la baisse")

        return recommendations

    # ========================================================================
    # MÉTRIQUES
    # ========================================================================

    async def get_metrics(
        self,
        position_id: UUID
    ) -> Optional[TakeProfitMetrics]:
        """
        Calcule les métriques de take profit.

        Args:
            position_id: ID de la position

        Returns:
            Métriques de take profit
        """
        try:
            levels = [
                l for l in self._levels.values()
                if l.position_id == position_id
            ]

            if not levels:
                return None

            completed = [l for l in levels if l.status == TakeProfitStatus.COMPLETED]
            
            if not completed:
                return TakeProfitMetrics(
                    position_id=position_id,
                    total_profit=Decimal("0"),
                    total_profit_usd=Decimal("0"),
                    average_profit_percent=0.0,
                    max_profit_percent=0.0,
                    min_profit_percent=0.0,
                    profit_factor=0.0,
                    win_rate=0.0
                )

            profits = [
                (l.target_price - l.entry_price) / l.entry_price * 100
                for l in completed
            ]

            total_profit = sum(
                (l.target_price - l.entry_price) * l.quantity
                for l in completed
            )

            profit_percents = [float(p) for p in profits]

            return TakeProfitMetrics(
                position_id=position_id,
                total_profit=total_profit,
                total_profit_usd=total_profit,  # Conversion USD
                average_profit_percent=np.mean(profit_percents) if profit_percents else 0,
                max_profit_percent=max(profit_percents) if profit_percents else 0,
                min_profit_percent=min(profit_percents) if profit_percents else 0,
                profit_factor=1.0,  # À calculer avec les pertes
                win_rate=len(completed) / len(levels) if levels else 0
            )

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques: {e}")
            return None

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_level(
        self,
        level_id: UUID
    ) -> Optional[TakeProfitLevel]:
        """
        Récupère un niveau de take profit.

        Args:
            level_id: ID du niveau

        Returns:
            Niveau de take profit ou None
        """
        return self._levels.get(level_id)

    async def get_schedule(
        self,
        schedule_id: UUID
    ) -> Optional[TakeProfitSchedule]:
        """
        Récupère un calendrier de take profit.

        Args:
            schedule_id: ID du calendrier

        Returns:
            Calendrier de take profit ou None
        """
        return self._schedules.get(schedule_id)

    async def get_levels(
        self,
        position_id: UUID,
        status: Optional[TakeProfitStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TakeProfitLevel]:
        """
        Récupère les niveaux de take profit.

        Args:
            position_id: ID de la position
            status: Filtrer par statut
            limit: Nombre de niveaux
            offset: Décalage

        Returns:
            Liste des niveaux de take profit
        """
        levels = [l for l in self._levels.values() if l.position_id == position_id]

        if status:
            levels = [l for l in levels if l.status == status]

        levels.sort(key=lambda x: x.created_at, reverse=True)
        return levels[offset:offset + limit]

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
                "total_levels": self._metrics["total_levels"],
                "total_schedules": self._metrics["total_schedules"],
                "completed_levels": self._metrics["completed_levels"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_update": self._metrics["last_update"],
                "cached_levels": len(self._levels),
                "cached_schedules": len(self._schedules),
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
        logger.info("Fermeture de TakeProfitManager...")
        self._levels.clear()
        self._schedules.clear()
        self._metrics_cache.clear()
        logger.info("TakeProfitManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_take_profit_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> TakeProfitManager:
    """
    Crée une instance de TakeProfitManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de TakeProfitManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return TakeProfitManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TakeProfitType",
    "TakeProfitStatus",
    "TakeProfitLevel",
    "TakeProfitSchedule",
    "TakeProfitMetrics",
    "TakeProfitManager",
    "create_take_profit_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du TakeProfitManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TAKE PROFIT MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    manager = create_take_profit_manager()

    print(f"\n✅ TakeProfitManager initialisé")

    # Création d'un take profit
    position_id = UUID("12345678-1234-5678-1234-567812345678")
    user_id = UUID("87654321-4321-5678-8765-432187654321")
    
    print(f"\n📊 Création d'un take profit...")
    level = await manager.create_take_profit(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        entry_price=Decimal("50000"),
        target_percent=0.05,
        quantity=Decimal("0.1"),
        take_profit_type=TakeProfitType.PERCENTAGE,
        metadata={"strategy": "swing_trading"}
    )

    print(f"   ID: {level.level_id}")
    print(f"   Entrée: ${level.entry_price}")
    print(f"   Cible: ${level.target_price}")
    print(f"   Quantité: {level.quantity}")

    # Création d'un calendrier de take profit
    print(f"\n📅 Création d'un calendrier de take profit...")
    levels_config = [
        {"target_percent": 0.03, "quantity": Decimal("0.03")},
        {"target_percent": 0.05, "quantity": Decimal("0.03")},
        {"target_percent": 0.08, "quantity": Decimal("0.04")}
    ]

    schedule = await manager.create_schedule(
        position_id=position_id,
        user_id=user_id,
        symbol="BTC/USDT",
        entry_price=Decimal("50000"),
        total_quantity=Decimal("0.1"),
        levels_config=levels_config,
        metadata={"strategy": "scaling"}
    )

    print(f"   ID: {schedule.schedule_id}")
    print(f"   Niveaux: {len(schedule.levels)}")
    print(f"   Quantité totale: {schedule.total_quantity}")

    # Mise à jour des niveaux
    print(f"\n🔄 Mise à jour des niveaux...")
    prices = [50500, 50800, 51200, 51500, 51800, 52000]
    
    for price in prices:
        updated_level = await manager.update_level(
            level_id=level.level_id,
            current_price=Decimal(str(price))
        )
        if updated_level:
            print(f"   Prix: ${price} - Statut: {updated_level.status.value}")

    # Calcul des niveaux Fibonacci
    print(f"\n📈 Calcul des niveaux Fibonacci...")
    fib_levels = await manager.calculate_levels(
        entry_price=Decimal("50000"),
        take_profit_type=TakeProfitType.FIBONACCI
    )

    print(f"   Niveaux Fibonacci:")
    for lvl in fib_levels:
        print(f"      {lvl['target_percent']*100:.1f}% -> ${lvl['target_price']}")

    # Métriques
    print(f"\n📊 Métriques de take profit:")
    metrics = await manager.get_metrics(position_id)
    if metrics:
        print(f"   Profit total: ${metrics.total_profit}")
        print(f"   Profit moyen: {metrics.average_profit_percent:.2f}%")
        print(f"   Win rate: {metrics.win_rate*100:.1f}%")
        print(f"   Profit factor: {metrics.profit_factor:.2f}")

    # Santé du service
    health = await manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Niveaux: {health['total_levels']}")
    print(f"   Niveaux complétés: {health['completed_levels']}")
    print(f"   Calendriers: {health['total_schedules']}")

    # Fermeture
    await manager.close()

    print("\n" + "=" * 60)
    print("TakeProfitManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import numpy as np
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
