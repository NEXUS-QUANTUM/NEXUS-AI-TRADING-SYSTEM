"""
NEXUS AI TRADING SYSTEM - HEDGE BOT BREAKEVEN MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion du point mort pour le Hedge Bot.
Calcul du breakeven, des coûts, des frais, et des métriques de rentabilité.

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

import pandas as pd
import numpy as np

from ..utils.helpers import (
    safe_decimal,
    safe_float,
    calculate_sharpe_ratio,
    calculate_sortino_ratio
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class CostType(Enum):
    """Types de coûts."""
    FIXED = "fixed"
    VARIABLE = "variable"
    SEMI_VARIABLE = "semi_variable"
    DIRECT = "direct"
    INDIRECT = "indirect"
    OPPORTUNITY = "opportunity"
    TRANSACTION = "transaction"
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"


class BreakevenStatus(Enum):
    """Statuts de point mort."""
    NOT_ACHIEVED = "not_achieved"
    ACHIEVED = "achieved"
    EXCEEDED = "exceeded"
    MAINTAINED = "maintained"


@dataclass
class CostItem:
    """Élément de coût."""
    cost_id: UUID
    name: str
    cost_type: CostType
    amount: Decimal
    currency: str
    frequency: str  # daily, weekly, monthly, yearly, one_time
    start_date: datetime
    end_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "cost_id": str(self.cost_id),
            "name": self.name,
            "cost_type": self.cost_type.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metadata": self.metadata
        }


@dataclass
class RevenueItem:
    """Élément de revenu."""
    revenue_id: UUID
    name: str
    amount: Decimal
    currency: str
    frequency: str  # daily, weekly, monthly, yearly, one_time
    start_date: datetime
    end_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "revenue_id": str(self.revenue_id),
            "name": self.name,
            "amount": str(self.amount),
            "currency": self.currency,
            "frequency": self.frequency,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "metadata": self.metadata
        }


@dataclass
class BreakevenAnalysis:
    """Analyse de point mort."""
    analysis_id: UUID
    user_id: UUID
    total_fixed_costs: Decimal
    total_variable_costs: Decimal
    total_operational_costs: Decimal
    total_revenue: Decimal
    total_cost: Decimal
    net_profit: Decimal
    breakeven_point: Decimal
    margin_of_safety: float
    contribution_margin: Decimal
    contribution_margin_ratio: float
    operating_leverage: float
    roi_percentage: float
    payback_period_days: int
    status: BreakevenStatus
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "analysis_id": str(self.analysis_id),
            "user_id": str(self.user_id),
            "total_fixed_costs": str(self.total_fixed_costs),
            "total_variable_costs": str(self.total_variable_costs),
            "total_operational_costs": str(self.total_operational_costs),
            "total_revenue": str(self.total_revenue),
            "total_cost": str(self.total_cost),
            "net_profit": str(self.net_profit),
            "breakeven_point": str(self.breakeven_point),
            "margin_of_safety": self.margin_of_safety,
            "contribution_margin": str(self.contribution_margin),
            "contribution_margin_ratio": self.contribution_margin_ratio,
            "operating_leverage": self.operating_leverage,
            "roi_percentage": self.roi_percentage,
            "payback_period_days": self.payback_period_days,
            "status": self.status.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class BreakevenMetrics:
    """Métriques de point mort."""
    user_id: UUID
    total_costs: Decimal
    total_revenue: Decimal
    daily_breakeven: Decimal
    monthly_breakeven: Decimal
    yearly_breakeven: Decimal
    current_profit: Decimal
    projected_profit: Decimal
    days_to_breakeven: int
    breakeven_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "total_costs": str(self.total_costs),
            "total_revenue": str(self.total_revenue),
            "daily_breakeven": str(self.daily_breakeven),
            "monthly_breakeven": str(self.monthly_breakeven),
            "yearly_breakeven": str(self.yearly_breakeven),
            "current_profit": str(self.current_profit),
            "projected_profit": str(self.projected_profit),
            "days_to_breakeven": self.days_to_breakeven,
            "breakeven_date": self.breakeven_date.isoformat() if self.breakeven_date else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE BREAKEVEN MANAGER
# ============================================================================

class BreakevenManager:
    """
    Gestionnaire de point mort avancé.
    """

    # Coûts opérationnels par défaut
    DEFAULT_OPERATIONAL_COSTS = {
        "server": {"amount": 100, "frequency": "monthly", "type": "fixed"},
        "api": {"amount": 50, "frequency": "monthly", "type": "variable"},
        "maintenance": {"amount": 25, "frequency": "monthly", "type": "semi_variable"}
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de point mort.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Cache
        self._cost_cache: Dict[UUID, CostItem] = {}
        self._revenue_cache: Dict[UUID, RevenueItem] = {}
        self._analysis_cache: Dict[UUID, BreakevenAnalysis] = {}
        self._metrics_cache: Dict[UUID, BreakevenMetrics] = {}
        
        # Métriques
        self._metrics = {
            "total_analyses": 0,
            "total_costs": 0,
            "total_revenue": Decimal("0"),
            "average_breakeven": Decimal("0"),
            "by_status": {},
            "last_analysis": None
        }

        logger.info("BreakevenManager initialisé avec succès")

    # ========================================================================
    # GESTION DES COÛTS
    # ========================================================================

    async def add_cost(
        self,
        name: str,
        cost_type: CostType,
        amount: Decimal,
        currency: str,
        frequency: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> CostItem:
        """
        Ajoute un coût.

        Args:
            name: Nom du coût
            cost_type: Type de coût
            amount: Montant
            currency: Devise
            frequency: Fréquence
            start_date: Date de début
            end_date: Date de fin
            metadata: Métadonnées

        Returns:
            Élément de coût
        """
        try:
            cost = CostItem(
                cost_id=uuid4(),
                name=name,
                cost_type=cost_type,
                amount=amount,
                currency=currency,
                frequency=frequency,
                start_date=start_date or datetime.now(),
                end_date=end_date,
                metadata=metadata or {}
            )

            self._cost_cache[cost.cost_id] = cost
            self._metrics["total_costs"] += 1

            return cost

        except Exception as e:
            logger.error(f"Erreur d'ajout de coût: {e}")
            raise

    async def add_revenue(
        self,
        name: str,
        amount: Decimal,
        currency: str,
        frequency: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> RevenueItem:
        """
        Ajoute un revenu.

        Args:
            name: Nom du revenu
            amount: Montant
            currency: Devise
            frequency: Fréquence
            start_date: Date de début
            end_date: Date de fin
            metadata: Métadonnées

        Returns:
            Élément de revenu
        """
        try:
            revenue = RevenueItem(
                revenue_id=uuid4(),
                name=name,
                amount=amount,
                currency=currency,
                frequency=frequency,
                start_date=start_date or datetime.now(),
                end_date=end_date,
                metadata=metadata or {}
            )

            self._revenue_cache[revenue.revenue_id] = revenue
            self._metrics["total_revenue"] += amount

            return revenue

        except Exception as e:
            logger.error(f"Erreur d'ajout de revenu: {e}")
            raise

    # ========================================================================
    # ANALYSE DU POINT MORT
    # ========================================================================

    async def analyze(
        self,
        user_id: UUID,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        include_operational: bool = True,
        metadata: Optional[Dict] = None
    ) -> BreakevenAnalysis:
        """
        Analyse le point mort.

        Args:
            user_id: ID de l'utilisateur
            period_start: Date de début
            period_end: Date de fin
            include_operational: Inclure les coûts opérationnels
            metadata: Métadonnées

        Returns:
            Analyse de point mort
        """
        try:
            analysis_id = uuid4()
            now = datetime.now()
            period_start = period_start or (now - timedelta(days=30))
            period_end = period_end or now

            # Récupération des coûts et revenus
            costs = list(self._cost_cache.values())
            revenues = list(self._revenue_cache.values())

            # Filtrage par période
            costs = [c for c in costs if c.start_date <= period_end and (c.end_date is None or c.end_date >= period_start)]
            revenues = [r for r in revenues if r.start_date <= period_end and (r.end_date is None or r.end_date >= period_start)]

            # Calcul des coûts
            total_fixed = Decimal("0")
            total_variable = Decimal("0")
            total_operational = Decimal("0")
            total_cost = Decimal("0")

            for cost in costs:
                amount = await self._calculate_amount_for_period(cost, period_start, period_end)
                total_cost += amount

                if cost.cost_type == CostType.FIXED:
                    total_fixed += amount
                elif cost.cost_type == CostType.VARIABLE:
                    total_variable += amount
                elif cost.cost_type in [CostType.OPERATIONAL, CostType.MAINTENANCE]:
                    total_operational += amount

            # Calcul des revenus
            total_revenue = Decimal("0")
            for revenue in revenues:
                amount = await self._calculate_amount_for_period(revenue, period_start, period_end)
                total_revenue += amount

            # Calculs du point mort
            net_profit = total_revenue - total_cost
            contribution_margin = total_revenue - total_variable
            contribution_margin_ratio = float(contribution_margin / total_revenue) if total_revenue > 0 else 0
            breakeven_point = total_fixed / Decimal(str(contribution_margin_ratio)) if contribution_margin_ratio > 0 else Decimal("0")

            # Marge de sécurité
            margin_of_safety = float((total_revenue - breakeven_point) / total_revenue) if total_revenue > 0 else 0

            # Levier opérationnel
            operating_leverage = float(contribution_margin / net_profit) if net_profit > 0 else 0

            # ROI
            roi_percentage = float(net_profit / total_cost * 100) if total_cost > 0 else 0

            # Période de récupération
            payback_period = 0
            if net_profit > 0:
                daily_profit = net_profit / 30
                payback_period = int(total_cost / daily_profit) if daily_profit > 0 else 0

            # Statut
            status = BreakevenStatus.NOT_ACHIEVED
            if net_profit > 0 and net_profit >= breakeven_point:
                status = BreakevenStatus.ACHIEVED
            elif net_profit > breakeven_point * 2:
                status = BreakevenStatus.EXCEDED
            elif net_profit > 0:
                status = BreakevenStatus.MAINTAINED

            analysis = BreakevenAnalysis(
                analysis_id=analysis_id,
                user_id=user_id,
                total_fixed_costs=total_fixed,
                total_variable_costs=total_variable,
                total_operational_costs=total_operational,
                total_revenue=total_revenue,
                total_cost=total_cost,
                net_profit=net_profit,
                breakeven_point=breakeven_point,
                margin_of_safety=margin_of_safety,
                contribution_margin=contribution_margin,
                contribution_margin_ratio=contribution_margin_ratio,
                operating_leverage=operating_leverage,
                roi_percentage=roi_percentage,
                payback_period_days=payback_period,
                status=status,
                period_start=period_start,
                period_end=period_end,
                metadata=metadata or {}
            )

            self._analysis_cache[analysis_id] = analysis
            self._metrics["total_analyses"] += 1
            self._metrics["average_breakeven"] = (
                (self._metrics["average_breakeven"] * (self._metrics["total_analyses"] - 1) + breakeven_point)
                / self._metrics["total_analyses"]
            )
            self._metrics["last_analysis"] = now.isoformat()

            status_key = status.value
            if status_key not in self._metrics["by_status"]:
                self._metrics["by_status"][status_key] = 0
            self._metrics["by_status"][status_key] += 1

            return analysis

        except Exception as e:
            logger.error(f"Erreur d'analyse du point mort: {e}")
            raise

    async def _calculate_amount_for_period(
        self,
        item: Union[CostItem, RevenueItem],
        start_date: datetime,
        end_date: datetime
    ) -> Decimal:
        """
        Calcule le montant pour une période.

        Args:
            item: Élément
            start_date: Date de début
            end_date: Date de fin

        Returns:
            Montant
        """
        try:
            # Période de l'élément
            item_start = max(item.start_date, start_date)
            item_end = item.end_date or end_date
            item_end = min(item_end, end_date)

            if item_start >= item_end:
                return Decimal("0")

            # Calcul en fonction de la fréquence
            if item.frequency == "one_time":
                return item.amount

            # Calcul du nombre de périodes
            days = (item_end - item_start).days + 1
            periods = 1

            if item.frequency == "daily":
                periods = days
            elif item.frequency == "weekly":
                periods = days / 7
            elif item.frequency == "monthly":
                periods = days / 30.44
            elif item.frequency == "yearly":
                periods = days / 365.25

            return item.amount * Decimal(str(periods))

        except Exception as e:
            logger.error(f"Erreur de calcul du montant: {e}")
            return Decimal("0")

    # ========================================================================
    # MÉTRIQUES DE POINT MORT
    # ========================================================================

    async def get_metrics(
        self,
        user_id: UUID,
        period_days: int = 30
    ) -> BreakevenMetrics:
        """
        Récupère les métriques de point mort.

        Args:
            user_id: ID de l'utilisateur
            period_days: Période en jours

        Returns:
            Métriques de point mort
        """
        try:
            now = datetime.now()
            period_start = now - timedelta(days=period_days)

            # Analyse
            analysis = await self.analyze(
                user_id=user_id,
                period_start=period_start,
                period_end=now
            )

            # Calcul des métriques
            daily_breakeven = analysis.breakeven_point / Decimal(str(period_days))
            monthly_breakeven = daily_breakeven * Decimal("30.44")
            yearly_breakeven = daily_breakeven * Decimal("365.25")

            # Projection de profit
            daily_profit = analysis.net_profit / Decimal(str(period_days))
            projected_profit = daily_profit * Decimal("365.25")

            # Jours jusqu'au point mort
            days_to_breakeven = 0
            breakeven_date = None

            if analysis.net_profit < 0 and analysis.breakeven_point > 0:
                daily_loss = abs(analysis.net_profit) / Decimal(str(period_days))
                if daily_loss > 0:
                    days_to_breakeven = int(analysis.total_cost / daily_loss)
                    breakeven_date = now + timedelta(days=days_to_breakeven)

            return BreakevenMetrics(
                user_id=user_id,
                total_costs=analysis.total_cost,
                total_revenue=analysis.total_revenue,
                daily_breakeven=daily_breakeven,
                monthly_breakeven=monthly_breakeven,
                yearly_breakeven=yearly_breakeven,
                current_profit=analysis.net_profit,
                projected_profit=projected_profit,
                days_to_breakeven=days_to_breakeven,
                breakeven_date=breakeven_date
            )

        except Exception as e:
            logger.error(f"Erreur de récupération des métriques: {e}")
            return BreakevenMetrics(user_id=user_id)

    # ========================================================================
    # RECOMMANDATIONS
    # ========================================================================

    async def get_recommendations(
        self,
        user_id: UUID,
        analysis_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Récupère des recommandations.

        Args:
            user_id: ID de l'utilisateur
            analysis_id: ID de l'analyse

        Returns:
            Liste des recommandations
        """
        try:
            analysis = self._analysis_cache.get(analysis_id)
            if not analysis:
                return []

            recommendations = []

            if analysis.net_profit < 0:
                recommendations.append({
                    "type": "reduce_costs",
                    "message": "Réduisez les coûts pour atteindre le point mort",
                    "priority": "high",
                    "suggestions": [
                        "Réduire les coûts fixes",
                        "Optimiser les coûts variables",
                        "Renégocier les contrats"
                    ]
                })

            if analysis.contribution_margin_ratio < 0.3:
                recommendations.append({
                    "type": "increase_margin",
                    "message": "Augmentez la marge de contribution",
                    "priority": "medium",
                    "suggestions": [
                        "Augmenter les prix",
                        "Réduire les coûts variables",
                        "Améliorer l'efficacité"
                    ]
                })

            if analysis.margin_of_safety < 0.2:
                recommendations.append({
                    "type": "increase_safety",
                    "message": "Améliorez la marge de sécurité",
                    "priority": "medium",
                    "suggestions": [
                        "Diversifier les revenus",
                        "Réduire les coûts fixes",
                        "Augmenter le volume"
                    ]
                })

            if analysis.roi_percentage < 10:
                recommendations.append({
                    "type": "improve_roi",
                    "message": "Améliorez le retour sur investissement",
                    "priority": "low",
                    "suggestions": [
                        "Optimiser les investissements",
                        "Augmenter l'efficacité",
                        "Réduire le temps de récupération"
                    ]
                })

            return recommendations

        except Exception as e:
            logger.error(f"Erreur de récupération des recommandations: {e}")
            return []

    # ========================================================================
    # RAPPORTS
    # ========================================================================

    async def generate_report(
        self,
        user_id: UUID,
        period_days: int = 30,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Génère un rapport de point mort.

        Args:
            user_id: ID de l'utilisateur
            period_days: Période en jours
            format: Format de sortie

        Returns:
            Rapport
        """
        try:
            now = datetime.now()
            period_start = now - timedelta(days=period_days)

            analysis = await self.analyze(
                user_id=user_id,
                period_start=period_start,
                period_end=now
            )

            metrics = await self.get_metrics(user_id, period_days)
            recommendations = await self.get_recommendations(user_id, analysis.analysis_id)

            report = {
                "period": {
                    "start": period_start.isoformat(),
                    "end": now.isoformat(),
                    "days": period_days
                },
                "analysis": analysis.to_dict(),
                "metrics": metrics.to_dict(),
                "recommendations": recommendations,
                "summary": {
                    "status": analysis.status.value,
                    "daily_breakeven": str(metrics.daily_breakeven),
                    "current_profit": str(analysis.net_profit),
                    "roi": f"{analysis.roi_percentage:.2f}%",
                    "days_to_breakeven": metrics.days_to_breakeven
                },
                "generated_at": datetime.now().isoformat()
            }

            return report

        except Exception as e:
            logger.error(f"Erreur de génération du rapport: {e}")
            return {"error": str(e)}

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_cost(
        self,
        cost_id: UUID
    ) -> Optional[CostItem]:
        """
        Récupère un coût.

        Args:
            cost_id: ID du coût

        Returns:
            Coût ou None
        """
        return self._cost_cache.get(cost_id)

    async def get_revenue(
        self,
        revenue_id: UUID
    ) -> Optional[RevenueItem]:
        """
        Récupère un revenu.

        Args:
            revenue_id: ID du revenu

        Returns:
            Revenu ou None
        """
        return self._revenue_cache.get(revenue_id)

    async def get_analysis(
        self,
        analysis_id: UUID
    ) -> Optional[BreakevenAnalysis]:
        """
        Récupère une analyse.

        Args:
            analysis_id: ID de l'analyse

        Returns:
            Analyse ou None
        """
        return self._analysis_cache.get(analysis_id)

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
                "total_costs": self._metrics["total_costs"],
                "total_revenue": str(self._metrics["total_revenue"]),
                "average_breakeven": str(self._metrics["average_breakeven"]),
                "by_status": self._metrics["by_status"],
                "last_analysis": self._metrics["last_analysis"],
                "cached_costs": len(self._cost_cache),
                "cached_revenues": len(self._revenue_cache),
                "cached_analyses": len(self._analysis_cache),
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
        logger.info("Fermeture de BreakevenManager...")
        self._cost_cache.clear()
        self._revenue_cache.clear()
        self._analysis_cache.clear()
        self._metrics_cache.clear()
        logger.info("BreakevenManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_breakeven_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> BreakevenManager:
    """
    Crée une instance de BreakevenManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de BreakevenManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return BreakevenManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "CostType",
    "BreakevenStatus",
    "CostItem",
    "RevenueItem",
    "BreakevenAnalysis",
    "BreakevenMetrics",
    "BreakevenManager",
    "create_breakeven_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du BreakevenManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT BREAKEVEN MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    breakeven = create_breakeven_manager()

    print(f"\n✅ BreakevenManager initialisé")

    # Ajout de coûts
    print(f"\n💰 Ajout de coûts...")
    
    cost1 = await breakeven.add_cost(
        name="Serveur AWS",
        cost_type=CostType.FIXED,
        amount=Decimal("100"),
        currency="USD",
        frequency="monthly"
    )
    print(f"   Coût fixe: {cost1.name} - ${cost1.amount}")

    cost2 = await breakeven.add_cost(
        name="API Trading",
        cost_type=CostType.VARIABLE,
        amount=Decimal("0.01"),
        currency="USD",
        frequency="daily"
    )
    print(f"   Coût variable: {cost2.name} - ${cost2.amount}")

    # Ajout de revenus
    print(f"\n📈 Ajout de revenus...")
    
    revenue1 = await breakeven.add_revenue(
        name="Abonnements",
        amount=Decimal("500"),
        currency="USD",
        frequency="monthly"
    )
    print(f"   Revenu: {revenue1.name} - ${revenue1.amount}")

    revenue2 = await breakeven.add_revenue(
        name="Frais de trading",
        amount=Decimal("0.05"),
        currency="USD",
        frequency="daily"
    )
    print(f"   Revenu: {revenue2.name} - ${revenue2.amount}")

    # Analyse du point mort
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Analyse du point mort...")
    
    analysis = await breakeven.analyze(
        user_id=user_id,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now()
    )

    print(f"   Revenus totaux: ${analysis.total_revenue}")
    print(f"   Coûts totaux: ${analysis.total_cost}")
    print(f"   Profit net: ${analysis.net_profit}")
    print(f"   Point mort: ${analysis.breakeven_point}")
    print(f"   ROI: {analysis.roi_percentage:.2f}%")
    print(f"   Statut: {analysis.status.value}")

    # Métriques
    print(f"\n📈 Métriques de point mort:")
    metrics = await breakeven.get_metrics(user_id, period_days=30)
    print(f"   Point mort quotidien: ${metrics.daily_breakeven}")
    print(f"   Point mort mensuel: ${metrics.monthly_breakeven}")
    print(f"   Profit projeté: ${metrics.projected_profit}")
    print(f"   Jours jusqu'au point mort: {metrics.days_to_breakeven}")

    # Recommandations
    print(f"\n💡 Recommandations:")
    recommendations = await breakeven.get_recommendations(user_id, analysis.analysis_id)
    for rec in recommendations:
        print(f"   {rec['type']}: {rec['message']}")

    # Rapport
    print(f"\n📄 Génération du rapport...")
    report = await breakeven.generate_report(user_id, period_days=30)
    print(f"   Statut: {report['summary']['status']}")
    print(f"   ROI: {report['summary']['roi']}")

    # Santé du service
    health = await breakeven.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Analyses: {health['total_analyses']}")
    print(f"   Coûts: {health['total_costs']}")
    print(f"   Revenus: ${health['total_revenue']}")

    # Fermeture
    await breakeven.close()

    print("\n" + "=" * 60)
    print("BreakevenManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
