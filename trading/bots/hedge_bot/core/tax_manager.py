"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TAX MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion fiscale pour le Hedge Bot.
Calcul des taxes, déclarations, optimisation fiscale, et reporting.

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

class TaxType(Enum):
    """Types de taxes."""
    CAPITAL_GAINS = "capital_gains"
    INCOME = "income"
    VAT = "vat"
    WITHHOLDING = "withholding"
    STAMP_DUTY = "stamp_duty"
    TRANSFER = "transfer"
    EXCISE = "excise"
    PROPERTY = "property"
    CORPORATE = "corporate"
    PERSONAL = "personal"


class TaxEventType(Enum):
    """Types d'événements fiscaux."""
    BUY = "buy"
    SELL = "sell"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    LOSS = "loss"
    GAIN = "gain"
    STAKING = "staking"
    MINING = "mining"
    AIRDROP = "airdrop"
    TRADE = "trade"


class TaxStatus(Enum):
    """Statuts de taxe."""
    CALCULATED = "calculated"
    REPORTED = "reported"
    PAID = "paid"
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    ADJUSTED = "adjusted"


@dataclass
class TaxEvent:
    """Événement fiscal."""
    event_id: UUID
    user_id: UUID
    event_type: TaxEventType
    timestamp: datetime
    asset: str
    quantity: Decimal
    price: Decimal
    amount: Decimal
    currency: str
    fee: Decimal
    fee_currency: str
    tax_type: TaxType
    tax_amount: Decimal
    tax_rate: float
    tax_currency: str
    status: TaxStatus
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "user_id": str(self.user_id),
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "asset": self.asset,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "amount": str(self.amount),
            "currency": self.currency,
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "tax_type": self.tax_type.value,
            "tax_amount": str(self.tax_amount),
            "tax_rate": self.tax_rate,
            "tax_currency": self.tax_currency,
            "status": self.status.value,
            "metadata": self.metadata
        }


@dataclass
class TaxReport:
    """Rapport fiscal."""
    report_id: UUID
    user_id: UUID
    tax_type: TaxType
    period_start: datetime
    period_end: datetime
    total_income: Decimal
    total_expenses: Decimal
    total_taxable: Decimal
    total_tax: Decimal
    tax_rate: float
    events: List[TaxEvent]
    status: TaxStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "tax_type": self.tax_type.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_income": str(self.total_income),
            "total_expenses": str(self.total_expenses),
            "total_taxable": str(self.total_taxable),
            "total_tax": str(self.total_tax),
            "tax_rate": self.tax_rate,
            "events": [e.to_dict() for e in self.events],
            "status": self.status.value,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat()
        }


@dataclass
class TaxMetrics:
    """Métriques fiscales."""
    user_id: UUID
    total_tax_paid: Decimal
    total_tax_owed: Decimal
    tax_efficiency: float
    effective_tax_rate: float
    marginal_tax_rate: float
    tax_loss_harvesting: Decimal
    tax_liability: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "total_tax_paid": str(self.total_tax_paid),
            "total_tax_owed": str(self.total_tax_owed),
            "tax_efficiency": self.tax_efficiency,
            "effective_tax_rate": self.effective_tax_rate,
            "marginal_tax_rate": self.marginal_tax_rate,
            "tax_loss_harvesting": str(self.tax_loss_harvesting),
            "tax_liability": str(self.tax_liability),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE TAX MANAGER
# ============================================================================

class TaxManager:
    """
    Gestionnaire fiscal avancé.
    """

    # Taux d'imposition par défaut (France)
    DEFAULT_TAX_RATES = {
        "capital_gains": 0.30,  # 30% (PFU)
        "income": 0.40,         # 40% (tranche haute)
        "vat": 0.20,            # 20%
        "withholding": 0.15,    # 15%
        "transfer": 0.005,      # 0.5%
        "corporate": 0.25       # 25%
    }

    # Seuils d'exemption
    EXEMPTION_THRESHOLDS = {
        "capital_gains": 300,   # 300€
        "dividends": 500,       # 500€
        "interest": 500,        # 500€
        "income": 10000         # 10000€
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire fiscal.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Taux d'imposition
        self.tax_rates = self.config.get("tax_rates", self.DEFAULT_TAX_RATES)
        self.exemptions = self.config.get("exemptions", self.EXEMPTION_THRESHOLDS)
        
        # Cache
        self._event_cache: Dict[UUID, TaxEvent] = {}
        self._report_cache: Dict[UUID, TaxReport] = {}
        self._metrics_cache: Dict[UUID, TaxMetrics] = {}
        
        # Métriques
        self._metrics = {
            "total_events": 0,
            "total_reports": 0,
            "total_tax": Decimal("0"),
            "by_type": {},
            "by_status": {},
            "last_report": None
        }

        logger.info("TaxManager initialisé avec succès")

    # ========================================================================
    # ENREGISTREMENT DES ÉVÉNEMENTS FISCAUX
    # ========================================================================

    async def record_event(
        self,
        user_id: UUID,
        event_type: TaxEventType,
        asset: str,
        quantity: Decimal,
        price: Decimal,
        amount: Decimal,
        currency: str,
        fee: Decimal = Decimal("0"),
        fee_currency: Optional[str] = None,
        tax_type: Optional[TaxType] = None,
        metadata: Optional[Dict] = None
    ) -> TaxEvent:
        """
        Enregistre un événement fiscal.

        Args:
            user_id: ID de l'utilisateur
            event_type: Type d'événement
            asset: Actif
            quantity: Quantité
            price: Prix
            amount: Montant
            currency: Devise
            fee: Frais
            fee_currency: Devise des frais
            tax_type: Type de taxe
            metadata: Métadonnées

        Returns:
            Événement fiscal
        """
        try:
            event_id = uuid4()
            now = datetime.now()

            # Détermination du type de taxe
            if tax_type is None:
                tax_type = self._determine_tax_type(event_type)

            # Calcul de la taxe
            tax_rate = self.tax_rates.get(tax_type.value, 0.0)
            tax_amount = amount * Decimal(str(tax_rate))

            # Vérification des exemptions
            tax_amount = await self._apply_exemptions(
                event_type,
                tax_amount,
                amount
            )

            event = TaxEvent(
                event_id=event_id,
                user_id=user_id,
                event_type=event_type,
                timestamp=now,
                asset=asset,
                quantity=quantity,
                price=price,
                amount=amount,
                currency=currency,
                fee=fee,
                fee_currency=fee_currency or currency,
                tax_type=tax_type,
                tax_amount=tax_amount,
                tax_rate=tax_rate,
                tax_currency=currency,
                status=TaxStatus.CALCULATED,
                metadata=metadata or {}
            )

            self._event_cache[event_id] = event
            self._metrics["total_events"] += 1
            self._metrics["total_tax"] += tax_amount

            event_type_key = event_type.value
            if event_type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][event_type_key] = 0
            self._metrics["by_type"][event_type_key] += 1

            return event

        except Exception as e:
            logger.error(f"Erreur d'enregistrement de l'événement: {e}")
            raise

    def _determine_tax_type(self, event_type: TaxEventType) -> TaxType:
        """
        Détermine le type de taxe.

        Args:
            event_type: Type d'événement

        Returns:
            Type de taxe
        """
        mapping = {
            TaxEventType.BUY: TaxType.TRANSFER,
            TaxEventType.SELL: TaxType.CAPITAL_GAINS,
            TaxEventType.DIVIDEND: TaxType.INCOME,
            TaxEventType.INTEREST: TaxType.INCOME,
            TaxEventType.STAKING: TaxType.INCOME,
            TaxEventType.MINING: TaxType.INCOME,
            TaxEventType.AIRDROP: TaxType.INCOME,
            TaxEventType.TRADE: TaxType.CAPITAL_GAINS
        }
        return mapping.get(event_type, TaxType.CAPITAL_GAINS)

    async def _apply_exemptions(
        self,
        event_type: TaxEventType,
        tax_amount: Decimal,
        amount: Decimal
    ) -> Decimal:
        """
        Applique les exemptions fiscales.

        Args:
            event_type: Type d'événement
            tax_amount: Montant de la taxe
            amount: Montant de l'opération

        Returns:
            Montant de la taxe après exemptions
        """
        threshold = self.exemptions.get(event_type.value, 0)
        if amount <= Decimal(str(threshold)):
            return Decimal("0")
        return tax_amount

    # ========================================================================
    # GÉNÉRATION DE RAPPORTS FISCAUX
    # ========================================================================

    async def generate_report(
        self,
        user_id: UUID,
        tax_type: TaxType,
        period_start: datetime,
        period_end: datetime,
        metadata: Optional[Dict] = None
    ) -> TaxReport:
        """
        Génère un rapport fiscal.

        Args:
            user_id: ID de l'utilisateur
            tax_type: Type de taxe
            period_start: Date de début
            period_end: Date de fin
            metadata: Métadonnées

        Returns:
            Rapport fiscal
        """
        try:
            report_id = uuid4()
            now = datetime.now()

            # Récupération des événements
            events = [
                e for e in self._event_cache.values()
                if e.user_id == user_id
                and e.tax_type == tax_type
                and period_start <= e.timestamp <= period_end
            ]

            # Calcul des totaux
            total_income = sum(e.amount for e in events if e.event_type in [
                TaxEventType.DIVIDEND,
                TaxEventType.INTEREST,
                TaxEventType.STAKING,
                TaxEventType.MINING,
                TaxEventType.AIRDROP
            ])

            total_expenses = sum(e.fee for e in events)
            total_taxable = total_income - total_expenses
            total_tax = sum(e.tax_amount for e in events)

            # Taux effectif
            tax_rate = float(total_tax / total_income) if total_income > 0 else 0

            report = TaxReport(
                report_id=report_id,
                user_id=user_id,
                tax_type=tax_type,
                period_start=period_start,
                period_end=period_end,
                total_income=total_income,
                total_expenses=total_expenses,
                total_taxable=total_taxable,
                total_tax=total_tax,
                tax_rate=tax_rate,
                events=events,
                status=TaxStatus.CALCULATED,
                metadata=metadata or {}
            )

            self._report_cache[report_id] = report
            self._metrics["total_reports"] += 1
            self._metrics["last_report"] = now.isoformat()

            status_key = TaxStatus.CALCULATED.value
            if status_key not in self._metrics["by_status"]:
                self._metrics["by_status"][status_key] = 0
            self._metrics["by_status"][status_key] += 1

            return report

        except Exception as e:
            logger.error(f"Erreur de génération du rapport: {e}")
            raise

    # ========================================================================
    # OPTIMISATION FISCALE
    # ========================================================================

    async def optimize_taxes(
        self,
        user_id: UUID,
        events: List[TaxEvent],
        strategy: str = "loss_harvesting",
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Optimise la fiscalité.

        Args:
            user_id: ID de l'utilisateur
            events: Liste des événements
            strategy: Stratégie d'optimisation
            metadata: Métadonnées

        Returns:
            Optimisation fiscale
        """
        try:
            if strategy == "loss_harvesting":
                return await self._loss_harvesting(user_id, events)
            elif strategy == "gain_deferral":
                return await self._gain_deferral(user_id, events)
            elif strategy == "tax_efficient":
                return await self._tax_efficient_allocation(user_id, events)
            else:
                return {"error": f"Stratégie {strategy} non supportée"}

        except Exception as e:
            logger.error(f"Erreur d'optimisation fiscale: {e}")
            return {"error": str(e)}

    async def _loss_harvesting(
        self,
        user_id: UUID,
        events: List[TaxEvent]
    ) -> Dict[str, Any]:
        """
        Stratégie de harvesting de pertes.

        Args:
            user_id: ID de l'utilisateur
            events: Liste des événements

        Returns:
            Recommandations
        """
        try:
            # Identification des pertes
            losses = [
                e for e in events
                if e.event_type == TaxEventType.SELL
                and e.amount < 0
            ]

            # Identification des gains
            gains = [
                e for e in events
                if e.event_type == TaxEventType.SELL
                and e.amount > 0
            ]

            recommendations = []

            if losses and gains:
                # Répartition des pertes
                total_loss = sum(abs(e.amount) for e in losses)
                total_gain = sum(e.amount for e in gains)

                if total_loss > total_gain:
                    recommendations.append({
                        "action": "use_losses",
                        "amount": total_gain,
                        "remaining_loss": total_loss - total_gain,
                        "suggestion": "Utiliser les pertes pour compenser les gains"
                    })
                else:
                    recommendations.append({
                        "action": "harvest_losses",
                        "amount": total_loss,
                        "remaining_gain": total_gain - total_loss,
                        "suggestion": "Harvester les pertes disponibles"
                    })

            return {
                "strategy": "loss_harvesting",
                "losses": len(losses),
                "gains": len(gains),
                "total_loss": str(total_loss) if losses else "0",
                "total_gain": str(total_gain) if gains else "0",
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur de loss harvesting: {e}")
            return {"error": str(e)}

    async def _gain_deferral(
        self,
        user_id: UUID,
        events: List[TaxEvent]
    ) -> Dict[str, Any]:
        """
        Stratégie de report des gains.

        Args:
            user_id: ID de l'utilisateur
            events: Liste des événements

        Returns:
            Recommandations
        """
        return {
            "strategy": "gain_deferral",
            "deferrable_gains": 0,
            "recommendations": [
                "Reporter les gains sur l'année suivante",
                "Utiliser des structures fiscales adaptées"
            ],
            "timestamp": datetime.now().isoformat()
        }

    async def _tax_efficient_allocation(
        self,
        user_id: UUID,
        events: List[TaxEvent]
    ) -> Dict[str, Any]:
        """
        Allocation fiscalement efficace.

        Args:
            user_id: ID de l'utilisateur
            events: Liste des événements

        Returns:
            Recommandations
        """
        return {
            "strategy": "tax_efficient_allocation",
            "current_assets": len(set(e.asset for e in events)),
            "recommendations": [
                "Placer les actifs à fort rendement dans des enveloppes fiscales",
                "Utiliser les produits défiscalisés",
                "Optimiser le timing des transactions"
            ],
            "timestamp": datetime.now().isoformat()
        }

    # ========================================================================
    # MÉTRIQUES FISCALES
    # ========================================================================

    async def get_tax_metrics(
        self,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime
    ) -> TaxMetrics:
        """
        Calcule les métriques fiscales.

        Args:
            user_id: ID de l'utilisateur
            period_start: Date de début
            period_end: Date de fin

        Returns:
            Métriques fiscales
        """
        try:
            events = [
                e for e in self._event_cache.values()
                if e.user_id == user_id
                and period_start <= e.timestamp <= period_end
            ]

            total_tax = sum(e.tax_amount for e in events)
            total_income = sum(
                e.amount for e in events
                if e.event_type in [TaxEventType.DIVIDEND, TaxEventType.INTEREST]
            )

            # Efficacité fiscale
            tax_efficiency = 1 - (total_tax / total_income) if total_income > 0 else 0

            # Taux effectif
            effective_tax_rate = float(total_tax / total_income) if total_income > 0 else 0

            # Taux marginal (simulé)
            marginal_tax_rate = self.tax_rates.get("income", 0.4)

            # Tax loss harvesting
            losses = sum(
                abs(e.amount) for e in events
                if e.event_type == TaxEventType.SELL and e.amount < 0
            )

            # Tax liability
            tax_liability = total_tax - sum(
                e.tax_amount for e in events
                if e.status == TaxStatus.PAID
            )

            metrics = TaxMetrics(
                user_id=user_id,
                total_tax_paid=total_tax,
                total_tax_owed=total_tax,
                tax_efficiency=float(tax_efficiency),
                effective_tax_rate=effective_tax_rate,
                marginal_tax_rate=marginal_tax_rate,
                tax_loss_harvesting=losses,
                tax_liability=tax_liability
            )

            self._metrics_cache[user_id] = metrics
            return metrics

        except Exception as e:
            logger.error(f"Erreur de calcul des métriques fiscales: {e}")
            return TaxMetrics(user_id=user_id)

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_event(
        self,
        event_id: UUID
    ) -> Optional[TaxEvent]:
        """
        Récupère un événement fiscal.

        Args:
            event_id: ID de l'événement

        Returns:
            Événement fiscal ou None
        """
        return self._event_cache.get(event_id)

    async def get_report(
        self,
        report_id: UUID
    ) -> Optional[TaxReport]:
        """
        Récupère un rapport fiscal.

        Args:
            report_id: ID du rapport

        Returns:
            Rapport fiscal ou None
        """
        return self._report_cache.get(report_id)

    async def get_metrics(
        self,
        user_id: UUID
    ) -> Optional[TaxMetrics]:
        """
        Récupère les métriques fiscales.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Métriques fiscales ou None
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
                "total_events": self._metrics["total_events"],
                "total_reports": self._metrics["total_reports"],
                "total_tax": str(self._metrics["total_tax"]),
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_report": self._metrics["last_report"],
                "cached_events": len(self._event_cache),
                "cached_reports": len(self._report_cache),
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
        logger.info("Fermeture de TaxManager...")
        self._event_cache.clear()
        self._report_cache.clear()
        self._metrics_cache.clear()
        logger.info("TaxManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_tax_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> TaxManager:
    """
    Crée une instance de TaxManager.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de TaxManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return TaxManager(
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TaxType",
    "TaxEventType",
    "TaxStatus",
    "TaxEvent",
    "TaxReport",
    "TaxMetrics",
    "TaxManager",
    "create_tax_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du TaxManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TAX MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    tax_manager = create_tax_manager()

    print(f"\n✅ TaxManager initialisé")

    # Enregistrement d'événements
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📝 Enregistrement d'événements fiscaux...")
    
    event1 = await tax_manager.record_event(
        user_id=user_id,
        event_type=TaxEventType.SELL,
        asset="BTC",
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        amount=Decimal("25000"),
        currency="USD",
        fee=Decimal("25"),
        metadata={"trade_id": "12345"}
    )
    print(f"   Event 1: {event1.event_type.value} - Tax: ${event1.tax_amount}")

    event2 = await tax_manager.record_event(
        user_id=user_id,
        event_type=TaxEventType.DIVIDEND,
        asset="ETH",
        quantity=Decimal("0.1"),
        price=Decimal("3000"),
        amount=Decimal("300"),
        currency="USD",
        metadata={"source": "staking"}
    )
    print(f"   Event 2: {event2.event_type.value} - Tax: ${event2.tax_amount}")

    # Génération d'un rapport
    print(f"\n📊 Génération d'un rapport fiscal...")
    report = await tax_manager.generate_report(
        user_id=user_id,
        tax_type=TaxType.CAPITAL_GAINS,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now()
    )

    print(f"   Revenus totaux: ${report.total_income}")
    print(f"   Dépenses: ${report.total_expenses}")
    print(f"   Taxable: ${report.total_taxable}")
    print(f"   Taxe totale: ${report.total_tax}")
    print(f"   Taux effectif: {report.tax_rate*100:.1f}%")

    # Métriques fiscales
    print(f"\n📈 Métriques fiscales:")
    metrics = await tax_manager.get_tax_metrics(
        user_id=user_id,
        period_start=datetime.now() - timedelta(days=30),
        period_end=datetime.now()
    )

    print(f"   Taxe payée: ${metrics.total_tax_paid}")
    print(f"   Efficacité fiscale: {metrics.tax_efficiency*100:.1f}%")
    print(f"   Taux effectif: {metrics.effective_tax_rate*100:.1f}%")
    print(f"   Tax loss harvesting: ${metrics.tax_loss_harvesting}")

    # Optimisation fiscale
    print(f"\n🎯 Optimisation fiscale...")
    events = await tax_manager.get_events(user_id)
    optimization = await tax_manager.optimize_taxes(
        user_id=user_id,
        events=events,
        strategy="loss_harvesting"
    )

    print(f"   Stratégie: {optimization.get('strategy')}")
    print(f"   Pertes: {optimization.get('losses', 0)}")
    print(f"   Gains: {optimization.get('gains', 0)}")
    recommendations = optimization.get('recommendations', [])
    for rec in recommendations:
        print(f"   💡 {rec.get('suggestion', '')}")

    # Santé du service
    health = await tax_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Événements: {health['total_events']}")
    print(f"   Rapports: {health['total_reports']}")
    print(f"   Taxe totale: ${health['total_tax']}")

    # Fermeture
    await tax_manager.close()

    print("\n" + "=" * 60)
    print("TaxManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
