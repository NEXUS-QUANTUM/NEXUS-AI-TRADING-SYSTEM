"""
NEXUS AI TRADING SYSTEM - HEDGE BOT BILLING MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion de facturation pour le Hedge Bot.
Gestion des abonnements, factures, paiements, et métriques de facturation.

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

import aiohttp
import stripe
from crypte import Crypte

from ..utils.helpers import safe_decimal, safe_float, safe_int

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class PlanType(Enum):
    """Types de plans."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class BillingPeriod(Enum):
    """Périodes de facturation."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
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


class PaymentStatus(Enum):
    """Statuts de paiement."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    PARTIALLY_REFUNDED = "partially_refunded"


class SubscriptionStatus(Enum):
    """Statuts d'abonnement."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"
    PENDING = "pending"


@dataclass
class Plan:
    """Plan d'abonnement."""
    plan_id: UUID
    name: str
    plan_type: PlanType
    billing_period: BillingPeriod
    price: Decimal
    currency: str
    features: List[str]
    max_users: int = 1
    max_bots: int = 1
    max_trades_per_day: int = 100
    max_volume_per_day: Decimal = Decimal("10000")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "plan_id": str(self.plan_id),
            "name": self.name,
            "plan_type": self.plan_type.value,
            "billing_period": self.billing_period.value,
            "price": str(self.price),
            "currency": self.currency,
            "features": self.features,
            "max_users": self.max_users,
            "max_bots": self.max_bots,
            "max_trades_per_day": self.max_trades_per_day,
            "max_volume_per_day": str(self.max_volume_per_day),
            "metadata": self.metadata
        }


@dataclass
class Subscription:
    """Abonnement."""
    subscription_id: UUID
    user_id: UUID
    plan_id: UUID
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime] = None
    trial_end_date: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    auto_renew: bool = True
    payment_method: Optional[PaymentMethod] = None
    payment_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

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
            "metadata": self.metadata
        }


@dataclass
class Invoice:
    """Facture."""
    invoice_id: UUID
    user_id: UUID
    subscription_id: UUID
    amount: Decimal
    currency: str
    status: PaymentStatus
    due_date: datetime
    paid_date: Optional[datetime] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    discount: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "invoice_id": str(self.invoice_id),
            "user_id": str(self.user_id),
            "subscription_id": str(self.subscription_id),
            "amount": str(self.amount),
            "currency": self.currency,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "items": self.items,
            "discount": str(self.discount),
            "tax": str(self.tax),
            "total": str(self.total),
            "metadata": self.metadata
        }


@dataclass
class BillingMetrics:
    """Métriques de facturation."""
    user_id: UUID
    total_spent: Decimal
    current_month_spent: Decimal
    last_invoice_date: Optional[datetime] = None
    next_invoice_date: Optional[datetime] = None
    subscription_status: SubscriptionStatus = SubscriptionStatus.INACTIVE
    active_plan: Optional[str] = None
    total_invoices: int = 0
    failed_payments: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "user_id": str(self.user_id),
            "total_spent": str(self.total_spent),
            "current_month_spent": str(self.current_month_spent),
            "last_invoice_date": self.last_invoice_date.isoformat() if self.last_invoice_date else None,
            "next_invoice_date": self.next_invoice_date.isoformat() if self.next_invoice_date else None,
            "subscription_status": self.subscription_status.value,
            "active_plan": self.active_plan,
            "total_invoices": self.total_invoices,
            "failed_payments": self.failed_payments,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE BILLING MANAGER
# ============================================================================

class BillingManager:
    """
    Gestionnaire de facturation avancé.
    """

    # TVA par défaut
    DEFAULT_TAX_RATE = Decimal("0.20")

    def __init__(
        self,
        stripe_api_key: Optional[str] = None,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialise le gestionnaire de facturation.

        Args:
            stripe_api_key: Clé API Stripe
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            config: Configuration
        """
        self.stripe_api_key = stripe_api_key
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.config = config or {}
        
        # Initialisation Stripe
        if stripe_api_key:
            stripe.api_key = stripe_api_key
        
        # Cache
        self._plan_cache: Dict[UUID, Plan] = {}
        self._subscription_cache: Dict[UUID, Subscription] = {}
        self._invoice_cache: Dict[UUID, Invoice] = {}
        self._metrics_cache: Dict[UUID, BillingMetrics] = {}
        
        # Plans par défaut
        self._default_plans = self._init_default_plans()
        
        # Métriques
        self._metrics = {
            "total_subscriptions": 0,
            "total_invoices": 0,
            "total_revenue": Decimal("0"),
            "active_subscriptions": 0,
            "by_plan": {},
            "by_status": {},
            "last_invoice": None
        }

        logger.info("BillingManager initialisé avec succès")

    def _init_default_plans(self) -> Dict[str, Plan]:
        """
        Initialise les plans par défaut.

        Returns:
            Plans par défaut
        """
        return {
            "free": Plan(
                plan_id=uuid4(),
                name="Free",
                plan_type=PlanType.FREE,
                billing_period=BillingPeriod.MONTHLY,
                price=Decimal("0"),
                currency="USD",
                features=["1 bot", "10 trades/day", "Basic analytics"],
                max_bots=1,
                max_trades_per_day=10
            ),
            "basic": Plan(
                plan_id=uuid4(),
                name="Basic",
                plan_type=PlanType.BASIC,
                billing_period=BillingPeriod.MONTHLY,
                price=Decimal("49"),
                currency="USD",
                features=["5 bots", "100 trades/day", "Advanced analytics", "Email support"],
                max_bots=5,
                max_trades_per_day=100
            ),
            "pro": Plan(
                plan_id=uuid4(),
                name="Pro",
                plan_type=PlanType.PRO,
                billing_period=BillingPeriod.MONTHLY,
                price=Decimal("199"),
                currency="USD",
                features=["Unlimited bots", "1000 trades/day", "Real-time analytics", "Priority support", "API access"],
                max_bots=999,
                max_trades_per_day=1000
            ),
            "enterprise": Plan(
                plan_id=uuid4(),
                name="Enterprise",
                plan_type=PlanType.ENTERPRISE,
                billing_period=BillingPeriod.MONTHLY,
                price=Decimal("999"),
                currency="USD",
                features=["Custom bots", "Unlimited trades", "Custom analytics", "24/7 support", "Dedicated account manager"],
                max_bots=9999,
                max_trades_per_day=9999
            )
        }

    # ========================================================================
    # GESTION DES PLANS
    # ========================================================================

    async def get_plan(
        self,
        plan_id: UUID
    ) -> Optional[Plan]:
        """
        Récupère un plan.

        Args:
            plan_id: ID du plan

        Returns:
            Plan ou None
        """
        return self._plan_cache.get(plan_id)

    async def get_plans(
        self,
        plan_type: Optional[PlanType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Plan]:
        """
        Récupère les plans.

        Args:
            plan_type: Filtrer par type
            limit: Nombre de plans
            offset: Décalage

        Returns:
            Liste des plans
        """
        plans = list(self._plan_cache.values())
        
        if plan_type:
            plans = [p for p in plans if p.plan_type == plan_type]
        
        plans.sort(key=lambda x: x.price)
        return plans[offset:offset + limit]

    async def create_plan(
        self,
        name: str,
        plan_type: PlanType,
        billing_period: BillingPeriod,
        price: Decimal,
        currency: str,
        features: List[str],
        **kwargs
    ) -> Plan:
        """
        Crée un plan.

        Args:
            name: Nom du plan
            plan_type: Type de plan
            billing_period: Période de facturation
            price: Prix
            currency: Devise
            features: Fonctionnalités
            **kwargs: Arguments supplémentaires

        Returns:
            Plan créé
        """
        try:
            plan = Plan(
                plan_id=uuid4(),
                name=name,
                plan_type=plan_type,
                billing_period=billing_period,
                price=price,
                currency=currency,
                features=features,
                **kwargs
            )

            self._plan_cache[plan.plan_id] = plan
            return plan

        except Exception as e:
            logger.error(f"Erreur de création de plan: {e}")
            raise

    # ========================================================================
    # GESTION DES ABONNEMENTS
    # ========================================================================

    async def create_subscription(
        self,
        user_id: UUID,
        plan_id: UUID,
        payment_method: Optional[PaymentMethod] = None,
        auto_renew: bool = True,
        trial_days: int = 0,
        metadata: Optional[Dict] = None
    ) -> Subscription:
        """
        Crée un abonnement.

        Args:
            user_id: ID de l'utilisateur
            plan_id: ID du plan
            payment_method: Méthode de paiement
            auto_renew: Renouvellement automatique
            trial_days: Jours d'essai
            metadata: Métadonnées

        Returns:
            Abonnement créé
        """
        try:
            plan = await self.get_plan(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} non trouvé")

            subscription_id = uuid4()
            now = datetime.now()
            
            start_date = now
            end_date = start_date + self._get_period_delta(plan.billing_period)
            trial_end_date = start_date + timedelta(days=trial_days) if trial_days > 0 else None

            subscription = Subscription(
                subscription_id=subscription_id,
                user_id=user_id,
                plan_id=plan_id,
                status=SubscriptionStatus.TRIAL if trial_days > 0 else SubscriptionStatus.ACTIVE,
                start_date=start_date,
                end_date=end_date,
                trial_end_date=trial_end_date,
                auto_renew=auto_renew,
                payment_method=payment_method,
                metadata=metadata or {}
            )

            self._subscription_cache[subscription_id] = subscription
            self._metrics["total_subscriptions"] += 1
            self._metrics["active_subscriptions"] += 1

            plan_type_key = plan.plan_type.value
            if plan_type_key not in self._metrics["by_plan"]:
                self._metrics["by_plan"][plan_type_key] = 0
            self._metrics["by_plan"][plan_type_key] += 1

            return subscription

        except Exception as e:
            logger.error(f"Erreur de création d'abonnement: {e}")
            raise

    async def cancel_subscription(
        self,
        subscription_id: UUID,
        immediate: bool = False
    ) -> bool:
        """
        Annule un abonnement.

        Args:
            subscription_id: ID de l'abonnement
            immediate: Annulation immédiate

        Returns:
            True si annulé
        """
        try:
            subscription = self._subscription_cache.get(subscription_id)
            if not subscription:
                return False

            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.now()

            if immediate:
                subscription.end_date = datetime.now()
                self._metrics["active_subscriptions"] -= 1

            return True

        except Exception as e:
            logger.error(f"Erreur d'annulation d'abonnement: {e}")
            return False

    async def renew_subscription(
        self,
        subscription_id: UUID
    ) -> bool:
        """
        Renouvelle un abonnement.

        Args:
            subscription_id: ID de l'abonnement

        Returns:
            True si renouvelé
        """
        try:
            subscription = self._subscription_cache.get(subscription_id)
            if not subscription:
                return False

            if subscription.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE]:
                return False

            plan = await self.get_plan(subscription.plan_id)
            if not plan:
                return False

            subscription.start_date = datetime.now()
            subscription.end_date = subscription.start_date + self._get_period_delta(plan.billing_period)
            subscription.status = SubscriptionStatus.ACTIVE

            return True

        except Exception as e:
            logger.error(f"Erreur de renouvellement d'abonnement: {e}")
            return False

    # ========================================================================
    # GESTION DES FACTURES
    # ========================================================================

    async def create_invoice(
        self,
        subscription_id: UUID,
        items: Optional[List[Dict[str, Any]]] = None,
        discount: Decimal = Decimal("0"),
        tax: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> Invoice:
        """
        Crée une facture.

        Args:
            subscription_id: ID de l'abonnement
            items: Articles
            discount: Réduction
            tax: TVA
            metadata: Métadonnées

        Returns:
            Facture créée
        """
        try:
            subscription = self._subscription_cache.get(subscription_id)
            if not subscription:
                raise ValueError(f"Abonnement {subscription_id} non trouvé")

            plan = await self.get_plan(subscription.plan_id)
            if not plan:
                raise ValueError(f"Plan non trouvé")

            invoice_id = uuid4()
            now = datetime.now()

            if items is None:
                items = [
                    {
                        "description": f"{plan.name} - {plan.billing_period.value}",
                        "amount": str(plan.price),
                        "currency": plan.currency
                    }
                ]

            total_amount = Decimal("0")
            for item in items:
                total_amount += Decimal(str(item.get("amount", 0)))

            tax_rate = tax or self.DEFAULT_TAX_RATE
            tax_amount = total_amount * tax_rate
            discount_amount = total_amount * discount

            invoice = Invoice(
                invoice_id=invoice_id,
                user_id=subscription.user_id,
                subscription_id=subscription_id,
                amount=total_amount,
                currency=plan.currency,
                status=PaymentStatus.PENDING,
                due_date=now + timedelta(days=14),
                items=items,
                discount=discount_amount,
                tax=tax_amount,
                total=total_amount + tax_amount - discount_amount,
                metadata=metadata or {}
            )

            self._invoice_cache[invoice_id] = invoice
            self._metrics["total_invoices"] += 1
            self._metrics["total_revenue"] += invoice.total
            self._metrics["last_invoice"] = now.isoformat()

            return invoice

        except Exception as e:
            logger.error(f"Erreur de création de facture: {e}")
            raise

    async def pay_invoice(
        self,
        invoice_id: UUID,
        payment_method: PaymentMethod,
        payment_details: Dict[str, Any]
    ) -> bool:
        """
        Paie une facture.

        Args:
            invoice_id: ID de la facture
            payment_method: Méthode de paiement
            payment_details: Détails du paiement

        Returns:
            True si payé
        """
        try:
            invoice = self._invoice_cache.get(invoice_id)
            if not invoice:
                return False

            # Traitement du paiement
            if payment_method == PaymentMethod.STRIPE:
                success = await self._process_stripe_payment(invoice, payment_details)
            elif payment_method == PaymentMethod.CRYPTO:
                success = await self._process_crypto_payment(invoice, payment_details)
            elif payment_method == PaymentMethod.PAYPAL:
                success = await self._process_paypal_payment(invoice, payment_details)
            else:
                success = await self._process_other_payment(invoice, payment_details)

            if success:
                invoice.status = PaymentStatus.COMPLETED
                invoice.paid_date = datetime.now()
                
                # Mise à jour de l'abonnement
                subscription = self._subscription_cache.get(invoice.subscription_id)
                if subscription:
                    subscription.status = SubscriptionStatus.ACTIVE
                
                return True

            invoice.status = PaymentStatus.FAILED
            return False

        except Exception as e:
            logger.error(f"Erreur de paiement: {e}")
            return False

    async def _process_stripe_payment(
        self,
        invoice: Invoice,
        payment_details: Dict[str, Any]
    ) -> bool:
        """
        Traite un paiement Stripe.

        Args:
            invoice: Facture
            payment_details: Détails du paiement

        Returns:
            True si réussi
        """
        try:
            if not self.stripe_api_key:
                logger.warning("Clé API Stripe non configurée")
                return False

            # Création d'un PaymentIntent
            intent = stripe.PaymentIntent.create(
                amount=int(float(invoice.total) * 100),
                currency=invoice.currency.lower(),
                payment_method=payment_details.get("payment_method_id"),
                confirmation_method="manual",
                confirm=True,
                metadata={
                    "invoice_id": str(invoice.invoice_id),
                    "user_id": str(invoice.user_id)
                }
            )

            return intent.status == "succeeded"

        except Exception as e:
            logger.error(f"Erreur Stripe: {e}")
            return False

    async def _process_crypto_payment(
        self,
        invoice: Invoice,
        payment_details: Dict[str, Any]
    ) -> bool:
        """
        Traite un paiement crypto.

        Args:
            invoice: Facture
            payment_details: Détails du paiement

        Returns:
            True si réussi
        """
        # Simulation de paiement crypto
        return True

    async def _process_paypal_payment(
        self,
        invoice: Invoice,
        payment_details: Dict[str, Any]
    ) -> bool:
        """
        Traite un paiement PayPal.

        Args:
            invoice: Facture
            payment_details: Détails du paiement

        Returns:
            True si réussi
        """
        # Simulation de paiement PayPal
        return True

    async def _process_other_payment(
        self,
        invoice: Invoice,
        payment_details: Dict[str, Any]
    ) -> bool:
        """
        Traite un autre type de paiement.

        Args:
            invoice: Facture
            payment_details: Détails du paiement

        Returns:
            True si réussi
        """
        return True

    # ========================================================================
    # MÉTRIQUES
    # ========================================================================

    async def get_billing_metrics(
        self,
        user_id: UUID
    ) -> BillingMetrics:
        """
        Récupère les métriques de facturation.

        Args:
            user_id: ID de l'utilisateur

        Returns:
            Métriques de facturation
        """
        try:
            # Recherche des abonnements
            subscriptions = [
                s for s in self._subscription_cache.values()
                if s.user_id == user_id
            ]

            # Recherche des factures
            invoices = [
                i for i in self._invoice_cache.values()
                if i.user_id == user_id
            ]

            total_spent = sum(i.total for i in invoices if i.status == PaymentStatus.COMPLETED)
            current_month = datetime.now().month
            current_month_spent = sum(
                i.total for i in invoices
                if i.status == PaymentStatus.COMPLETED and i.paid_date and i.paid_date.month == current_month
            )

            active_subscription = next(
                (s for s in subscriptions if s.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
                None
            )

            last_invoice = max(
                (i for i in invoices if i.status == PaymentStatus.COMPLETED),
                key=lambda x: x.paid_date,
                default=None
            )

            failed_payments = len([i for i in invoices if i.status == PaymentStatus.FAILED])

            return BillingMetrics(
                user_id=user_id,
                total_spent=total_spent,
                current_month_spent=current_month_spent,
                last_invoice_date=last_invoice.paid_date if last_invoice else None,
                next_invoice_date=active_subscription.end_date if active_subscription else None,
                subscription_status=active_subscription.status if active_subscription else SubscriptionStatus.INACTIVE,
                active_plan=await self._get_plan_name(active_subscription.plan_id) if active_subscription else None,
                total_invoices=len(invoices),
                failed_payments=failed_payments
            )

        except Exception as e:
            logger.error(f"Erreur de récupération des métriques: {e}")
            return BillingMetrics(user_id=user_id)

    async def _get_plan_name(self, plan_id: UUID) -> Optional[str]:
        """
        Récupère le nom d'un plan.

        Args:
            plan_id: ID du plan

        Returns:
            Nom du plan
        """
        plan = await self.get_plan(plan_id)
        return plan.name if plan else None

    def _get_period_delta(self, billing_period: BillingPeriod) -> timedelta:
        """
        Récupère le delta de période.

        Args:
            billing_period: Période de facturation

        Returns:
            Delta
        """
        if billing_period == BillingPeriod.MONTHLY:
            return timedelta(days=30)
        elif billing_period == BillingPeriod.QUARTERLY:
            return timedelta(days=90)
        elif billing_period == BillingPeriod.SEMI_ANNUAL:
            return timedelta(days=180)
        elif billing_period == BillingPeriod.ANNUAL:
            return timedelta(days=365)
        else:
            return timedelta(days=30)

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_subscription(
        self,
        subscription_id: UUID
    ) -> Optional[Subscription]:
        """
        Récupère un abonnement.

        Args:
            subscription_id: ID de l'abonnement

        Returns:
            Abonnement ou None
        """
        return self._subscription_cache.get(subscription_id)

    async def get_subscriptions(
        self,
        user_id: UUID,
        status: Optional[SubscriptionStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Subscription]:
        """
        Récupère les abonnements d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            status: Filtrer par statut
            limit: Nombre d'abonnements
            offset: Décalage

        Returns:
            Liste des abonnements
        """
        subscriptions = [
            s for s in self._subscription_cache.values()
            if s.user_id == user_id
        ]

        if status:
            subscriptions = [s for s in subscriptions if s.status == status]

        subscriptions.sort(key=lambda x: x.start_date, reverse=True)
        return subscriptions[offset:offset + limit]

    async def get_invoice(
        self,
        invoice_id: UUID
    ) -> Optional[Invoice]:
        """
        Récupère une facture.

        Args:
            invoice_id: ID de la facture

        Returns:
            Facture ou None
        """
        return self._invoice_cache.get(invoice_id)

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
                "total_subscriptions": self._metrics["total_subscriptions"],
                "total_invoices": self._metrics["total_invoices"],
                "total_revenue": str(self._metrics["total_revenue"]),
                "active_subscriptions": self._metrics["active_subscriptions"],
                "by_plan": self._metrics["by_plan"],
                "by_status": self._metrics["by_status"],
                "last_invoice": self._metrics["last_invoice"],
                "cached_plans": len(self._plan_cache),
                "cached_subscriptions": len(self._subscription_cache),
                "cached_invoices": len(self._invoice_cache),
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
        logger.info("Fermeture de BillingManager...")
        self._plan_cache.clear()
        self._subscription_cache.clear()
        self._invoice_cache.clear()
        self._metrics_cache.clear()
        logger.info("BillingManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_billing_manager(
    stripe_api_key: Optional[str] = None,
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> BillingManager:
    """
    Crée une instance de BillingManager.

    Args:
        stripe_api_key: Clé API Stripe
        redis_url: URL de connexion Redis
        api_keys: Clés API
        config: Configuration

    Returns:
        Instance de BillingManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return BillingManager(
        stripe_api_key=stripe_api_key,
        redis_client=redis_client,
        api_keys=api_keys,
        config=config
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PlanType",
    "BillingPeriod",
    "PaymentMethod",
    "PaymentStatus",
    "SubscriptionStatus",
    "Plan",
    "Subscription",
    "Invoice",
    "BillingMetrics",
    "BillingManager",
    "create_billing_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du BillingManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT BILLING MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    billing = create_billing_manager()

    print(f"\n✅ BillingManager initialisé")

    # Création d'un plan
    print(f"\n📋 Création d'un plan...")
    plan = await billing.create_plan(
        name="Pro Plan",
        plan_type=PlanType.PRO,
        billing_period=BillingPeriod.MONTHLY,
        price=Decimal("199"),
        currency="USD",
        features=["Unlimited bots", "Advanced analytics", "Priority support"],
        max_bots=10,
        max_trades_per_day=1000
    )

    print(f"   Plan: {plan.name} - ${plan.price}/{plan.billing_period.value}")

    # Création d'un abonnement
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📦 Création d'un abonnement...")
    
    subscription = await billing.create_subscription(
        user_id=user_id,
        plan_id=plan.plan_id,
        auto_renew=True,
        trial_days=7
    )

    print(f"   ID: {subscription.subscription_id}")
    print(f"   Statut: {subscription.status.value}")
    print(f"   Fin d'essai: {subscription.trial_end_date}")

    # Création d'une facture
    print(f"\n🧾 Création d'une facture...")
    invoice = await billing.create_invoice(
        subscription_id=subscription.subscription_id,
        metadata={"period": "monthly"}
    )

    print(f"   ID: {invoice.invoice_id}")
    print(f"   Montant: ${invoice.total}")
    print(f"   Échéance: {invoice.due_date}")

    # Simulation de paiement
    print(f"\n💳 Simulation de paiement...")
    payment_success = await billing.pay_invoice(
        invoice_id=invoice.invoice_id,
        payment_method=PaymentMethod.STRIPE,
        payment_details={"payment_method_id": "pm_test_123"}
    )

    print(f"   Paiement réussi: {payment_success}")

    # Métriques de facturation
    print(f"\n📊 Métriques de facturation:")
    metrics = await billing.get_billing_metrics(user_id)
    print(f"   Total dépensé: ${metrics.total_spent}")
    print(f"   Mois en cours: ${metrics.current_month_spent}")
    print(f"   Statut abonnement: {metrics.subscription_status.value}")
    print(f"   Plan actif: {metrics.active_plan}")
    print(f"   Factures: {metrics.total_invoices}")

    # Santé du service
    health = await billing.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Abonnements: {health['total_subscriptions']}")
    print(f"   Factures: {health['total_invoices']}")
    print(f"   Revenus: ${health['total_revenue']}")

    # Fermeture
    await billing.close()

    print("\n" + "=" * 60)
    print("BillingManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
