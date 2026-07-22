"""
NEXUS AI TRADING SYSTEM - HEDGE BOT SUBSCRIPTION MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données d'abonnement pour le Hedge Bot.
Définition des entités d'abonnement, plans, facturation, et métriques.

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

from sqlalchemy import (
    Column, String, DateTime, Numeric, Integer, Boolean, 
    ForeignKey, Text, JSON, Enum as SQLEnum, Index, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils.helpers import safe_decimal, safe_float

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class PlanType(Enum):
    """Types de plans."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(Enum):
    """Statuts d'abonnement."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"
    PENDING = "pending"
    SUSPENDED = "suspended"
    GRACE_PERIOD = "grace_period"


class BillingPeriod(Enum):
    """Périodes de facturation."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    BIENNIAL = "biennial"
    LIFETIME = "lifetime"


class PaymentMethod(Enum):
    """Méthodes de paiement."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CRYPTO = "crypto"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    BANK_TRANSFER = "bank_transfer"
    WIRE = "wire"
    CRYPTO_STABLE = "crypto_stable"


class PaymentStatus(Enum):
    """Statuts de paiement."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    PARTIALLY_REFUNDED = "partially_refunded"


class InvoiceStatus(Enum):
    """Statuts de facture."""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class PlanModel(Base):
    """Modèle de plan d'abonnement."""
    __tablename__ = "plans"

    plan_id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    plan_type = Column(SQLEnum(PlanType), nullable=False)
    billing_period = Column(SQLEnum(BillingPeriod), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    features = Column(JSON, nullable=False)
    max_users = Column(Integer, nullable=False)
    max_bots = Column(Integer, nullable=False)
    max_trades_per_day = Column(Integer, nullable=False)
    max_volume_per_day = Column(Numeric(20, 8), nullable=False)
    max_positions = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_plans_type", "plan_type"),
        Index("idx_plans_billing_period", "billing_period"),
        Index("idx_plans_price", "price"),
        Index("idx_plans_is_active", "is_active"),
    )


class SubscriptionModel(Base):
    """Modèle d'abonnement."""
    __tablename__ = "subscriptions"

    subscription_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    plan_id = Column(String(36), ForeignKey("plans.plan_id"), nullable=False)
    status = Column(SQLEnum(SubscriptionStatus), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    auto_renew = Column(Boolean, default=True)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=True)
    payment_id = Column(String(255), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    plan = relationship("PlanModel")

    __table_args__ = (
        Index("idx_subscriptions_user_id", "user_id"),
        Index("idx_subscriptions_plan_id", "plan_id"),
        Index("idx_subscriptions_status", "status"),
        Index("idx_subscriptions_start_date", "start_date"),
        Index("idx_subscriptions_end_date", "end_date"),
    )


class InvoiceModel(Base):
    """Modèle de facture."""
    __tablename__ = "invoices"

    invoice_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    subscription_id = Column(String(36), ForeignKey("subscriptions.subscription_id"), nullable=False)
    invoice_number = Column(String(50), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(SQLEnum(InvoiceStatus), nullable=False)
    due_date = Column(DateTime, nullable=False)
    paid_date = Column(DateTime, nullable=True)
    items = Column(JSON, nullable=False)
    discount = Column(Numeric(20, 8), nullable=False)
    tax = Column(Numeric(20, 8), nullable=False)
    total = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    subscription = relationship("SubscriptionModel")

    __table_args__ = (
        Index("idx_invoices_user_id", "user_id"),
        Index("idx_invoices_subscription_id", "subscription_id"),
        Index("idx_invoices_status", "status"),
        Index("idx_invoices_due_date", "due_date"),
        Index("idx_invoices_invoice_number", "invoice_number"),
    )


class PaymentModel(Base):
    """Modèle de paiement."""
    __tablename__ = "payments"

    payment_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    invoice_id = Column(String(36), ForeignKey("invoices.invoice_id"), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=False)
    status = Column(SQLEnum(PaymentStatus), nullable=False)
    transaction_id = Column(String(255), nullable=True)
    metadata = Column(JSON, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    invoice = relationship("InvoiceModel")

    __table_args__ = (
        Index("idx_payments_user_id", "user_id"),
        Index("idx_payments_invoice_id", "invoice_id"),
        Index("idx_payments_status", "status"),
        Index("idx_payments_processed_at", "processed_at"),
    )


class SubscriptionMetricsModel(Base):
    """Modèle de métriques d'abonnement."""
    __tablename__ = "subscription_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    total_plans = Column(Integer, nullable=False)
    active_subscriptions = Column(Integer, nullable=False)
    total_revenue = Column(Numeric(20, 8), nullable=False)
    monthly_revenue = Column(Numeric(20, 8), nullable=False)
    yearly_revenue = Column(Numeric(20, 8), nullable=False)
    churn_rate = Column(Float, nullable=False)
    retention_rate = Column(Float, nullable=False)
    average_lifetime = Column(Float, nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_subscription_metrics_user_id", "user_id"),
        Index("idx_subscription_metrics_calculated_at", "calculated_at"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Plan:
    """Plan d'abonnement."""
    plan_id: UUID
    name: str
    description: Optional[str]
    plan_type: PlanType
    billing_period: BillingPeriod
    price: Decimal
    currency: str
    features: List[str]
    max_users: int
    max_bots: int
    max_trades_per_day: int
    max_volume_per_day: Decimal
    max_positions: int
    is_active: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "plan_id": str(self.plan_id),
            "name": self.name,
            "description": self.description,
            "plan_type": self.plan_type.value,
            "billing_period": self.billing_period.value,
            "price": str(self.price),
            "currency": self.currency,
            "features": self.features,
            "max_users": self.max_users,
            "max_bots": self.max_bots,
            "max_trades_per_day": self.max_trades_per_day,
            "max_volume_per_day": str(self.max_volume_per_day),
            "max_positions": self.max_positions,
            "is_active": self.is_active,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Subscription:
    """Abonnement."""
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime]
    trial_end_date: Optional[datetime]
    cancelled_at: Optional[datetime]
    auto_renew: bool
    payment_method: Optional[PaymentMethod]
    payment_id: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "subscription_id": str(self.subscription_id),
            "user_id": str(self.user_id),
            "plan_id": str(self.plan_id),
            "status": self.status.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "trial_end_date": self.trial_end_date.isoformat() if self.trial_end_date else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "auto_renew": self.auto_renew,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "payment_id": self.payment_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Invoice:
    """Facture."""
    invoice_id: UUID
    user_id: UUID
    subscription_id: UUID
    invoice_number: str
    amount: Decimal
    currency: str
    status: InvoiceStatus
    due_date: datetime
    paid_date: Optional[datetime]
    items: List[Dict[str, Any]]
    discount: Decimal
    tax: Decimal
    total: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "invoice_id": str(self.invoice_id),
            "user_id": str(self.user_id),
            "subscription_id": str(self.subscription_id),
            "invoice_number": self.invoice_number,
            "amount": str(self.amount),
            "currency": self.currency,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "items": self.items,
            "discount": str(self.discount),
            "tax": str(self.tax),
            "total": str(self.total),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Payment:
    """Paiement."""
    payment_id: UUID
    user_id: UUID
    invoice_id: UUID
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    status: PaymentStatus
    transaction_id: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "payment_id": str(self.payment_id),
            "user_id": str(self.user_id),
            "invoice_id": str(self.invoice_id),
            "amount": str(self.amount),
            "currency": self.currency,
            "payment_method": self.payment_method.value,
            "status": self.status.value,
            "transaction_id": self.transaction_id,
            "metadata": self.metadata,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SubscriptionMetrics:
    """Métriques d'abonnement."""
    metric_id: UUID
    user_id: UUID
    total_plans: int
    active_subscriptions: int
    total_revenue: Decimal
    monthly_revenue: Decimal
    yearly_revenue: Decimal
    churn_rate: float
    retention_rate: float
    average_lifetime: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "total_plans": self.total_plans,
            "active_subscriptions": self.active_subscriptions,
            "total_revenue": str(self.total_revenue),
            "monthly_revenue": str(self.monthly_revenue),
            "yearly_revenue": str(self.yearly_revenue),
            "churn_rate": self.churn_rate,
            "retention_rate": self.retention_rate,
            "average_lifetime": self.average_lifetime,
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_plan(
    name: str,
    plan_type: PlanType,
    billing_period: BillingPeriod,
    price: Decimal,
    currency: str,
    features: List[str],
    max_users: int = 1,
    max_bots: int = 1,
    max_trades_per_day: int = 100,
    max_volume_per_day: Decimal = Decimal("10000"),
    max_positions: int = 10,
    description: Optional[str] = None,
    is_active: bool = True,
    metadata: Optional[Dict] = None
) -> Plan:
    """
    Crée un plan d'abonnement.

    Args:
        name: Nom du plan
        plan_type: Type de plan
        billing_period: Période de facturation
        price: Prix
        currency: Devise
        features: Fonctionnalités
        max_users: Nombre max d'utilisateurs
        max_bots: Nombre max de bots
        max_trades_per_day: Trades max par jour
        max_volume_per_day: Volume max par jour
        max_positions: Positions max
        description: Description
        is_active: Plan actif
        metadata: Métadonnées

    Returns:
        Plan créé
    """
    return Plan(
        plan_id=uuid4(),
        name=name,
        description=description,
        plan_type=plan_type,
        billing_period=billing_period,
        price=price,
        currency=currency,
        features=features,
        max_users=max_users,
        max_bots=max_bots,
        max_trades_per_day=max_trades_per_day,
        max_volume_per_day=max_volume_per_day,
        max_positions=max_positions,
        is_active=is_active,
        metadata=metadata or {}
    )


def create_subscription(
    user_id: UUID,
    plan_id: UUID,
    status: SubscriptionStatus = SubscriptionStatus.PENDING,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    trial_end_date: Optional[datetime] = None,
    auto_renew: bool = True,
    payment_method: Optional[PaymentMethod] = None,
    payment_id: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Subscription:
    """
    Crée un abonnement.

    Args:
        user_id: ID de l'utilisateur
        plan_id: ID du plan
        status: Statut
        start_date: Date de début
        end_date: Date de fin
        trial_end_date: Date de fin d'essai
        auto_renew: Renouvellement automatique
        payment_method: Méthode de paiement
        payment_id: ID de paiement
        metadata: Métadonnées

    Returns:
        Abonnement créé
    """
    now = datetime.now()
    return Subscription(
        subscription_id=uuid4(),
        user_id=user_id,
        plan_id=plan_id,
        status=status,
        start_date=start_date or now,
        end_date=end_date,
        trial_end_date=trial_end_date,
        cancelled_at=None,
        auto_renew=auto_renew,
        payment_method=payment_method,
        payment_id=payment_id,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PlanType",
    "SubscriptionStatus",
    "BillingPeriod",
    "PaymentMethod",
    "PaymentStatus",
    "InvoiceStatus",
    "PlanModel",
    "SubscriptionModel",
    "InvoiceModel",
    "PaymentModel",
    "SubscriptionMetricsModel",
    "Plan",
    "Subscription",
    "Invoice",
    "Payment",
    "SubscriptionMetrics",
    "create_plan",
    "create_subscription"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles d'abonnement."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT SUBSCRIPTION MODELS")
    print("=" * 60)

    # Création d'un plan
    print(f"\n📋 Création d'un plan...")
    
    plan = create_plan(
        name="Pro Plan",
        plan_type=PlanType.PRO,
        billing_period=BillingPeriod.MONTHLY,
        price=Decimal("199"),
        currency="USD",
        features=[
            "Unlimited bots",
            "1000 trades/day",
            "Real-time analytics",
            "Priority support",
            "API access"
        ],
        max_users=5,
        max_bots=999,
        max_trades_per_day=1000,
        max_volume_per_day=Decimal("1000000"),
        max_positions=100,
        description="Plan professionnel pour traders avancés"
    )

    print(f"   ID: {plan.plan_id}")
    print(f"   Nom: {plan.name}")
    print(f"   Prix: ${plan.price}/{plan.billing_period.value}")
    print(f"   Fonctionnalités: {len(plan.features)}")

    # Création d'un abonnement
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📦 Création d'un abonnement...")
    
    subscription = create_subscription(
        user_id=user_id,
        plan_id=plan.plan_id,
        status=SubscriptionStatus.ACTIVE,
        trial_end_date=datetime.now() + timedelta(days=7),
        auto_renew=True,
        payment_method=PaymentMethod.STRIPE,
        payment_id="sub_123456"
    )

    print(f"   ID: {subscription.subscription_id}")
    print(f"   Statut: {subscription.status.value}")
    print(f"   Début: {subscription.start_date}")
    print(f"   Fin d'essai: {subscription.trial_end_date}")

    # Création d'une facture
    print(f"\n🧾 Création d'une facture...")
    
    invoice = Invoice(
        invoice_id=uuid4(),
        user_id=user_id,
        subscription_id=subscription.subscription_id,
        invoice_number="INV-2026-001",
        amount=Decimal("199"),
        currency="USD",
        status=InvoiceStatus.SENT,
        due_date=datetime.now() + timedelta(days=14),
        items=[
            {"description": "Pro Plan - Monthly", "amount": 199, "quantity": 1}
        ],
        discount=Decimal("0"),
        tax=Decimal("39.80"),
        total=Decimal("238.80")
    )

    print(f"   ID: {invoice.invoice_id}")
    print(f"   Numéro: {invoice.invoice_number}")
    print(f"   Montant: ${invoice.total}")
    print(f"   Échéance: {invoice.due_date}")

    # Métriques
    print(f"\n📊 Métriques d'abonnement:")
    
    metrics = SubscriptionMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        total_plans=3,
        active_subscriptions=2,
        total_revenue=Decimal("5000"),
        monthly_revenue=Decimal("398"),
        yearly_revenue=Decimal("4776"),
        churn_rate=0.05,
        retention_rate=0.95,
        average_lifetime=18.5
    )

    print(f"   Plans actifs: {metrics.total_plans}")
    print(f"   Abonnements actifs: {metrics.active_subscriptions}")
    print(f"   Revenu mensuel: ${metrics.monthly_revenue}")
    print(f"   Taux de rétention: {metrics.retention_rate*100:.1f}%")

    print("\n" + "=" * 60)
    print("Subscription Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
