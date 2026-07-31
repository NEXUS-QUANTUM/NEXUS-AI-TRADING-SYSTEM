# trading/bots/hedge_bot/hedge_bot_subscription.py
# Advanced Subscription & Tier Management System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Subscription Module - Module avancé de gestion des abonnements et des tiers pour le Hedge Bot.
Gère les plans d'abonnement, les niveaux de service, le billing, les quotas d'utilisation,
l'authentification des utilisateurs et le contrôle d'accès basé sur les tiers.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
from collections import defaultdict, deque
import threading
import concurrent.futures
import hashlib
import hmac
import base64

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_subscription")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext, DataClass
)


# ============== ENUMS & TYPES ==============

class SubscriptionTier(Enum):
    """Niveaux d'abonnement disponibles."""
    FREE = "free"                    # Gratuit
    BASIC = "basic"                  # Basique
    PREMIUM = "premium"              # Premium
    PROFESSIONAL = "professional"    # Professionnel
    ENTERPRISE = "enterprise"        # Entreprise
    ULTIMATE = "ultimate"            # Ultime


class SubscriptionStatus(Enum):
    """Statuts d'abonnement."""
    ACTIVE = "active"                # Actif
    PENDING = "pending"              # En attente
    EXPIRED = "expired"              # Expiré
    CANCELLED = "cancelled"          # Annulé
    SUSPENDED = "suspended"          # Suspendu
    TRIAL = "trial"                  # Période d'essai
    GRACE_PERIOD = "grace_period"    # Période de grâce


class BillingPeriod(Enum):
    """Périodes de facturation."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    BIENNIAL = "biennial"


class PaymentMethod(Enum):
    """Méthodes de paiement."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"
    INVOICE = "invoice"


class FeatureAccess(Enum):
    """Niveaux d'accès aux fonctionnalités."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


# ============== DATA MODELS ==============

@dataclass
class SubscriptionPlan:
    """Plan d'abonnement."""
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    tier: SubscriptionTier = SubscriptionTier.BASIC
    description: str = ""
    price: float = 0.0
    currency: str = "USD"
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    features: Dict[str, FeatureAccess] = field(default_factory=dict)
    quotas: Dict[str, float] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)
    trial_days: int = 0
    grace_period_days: int = 7
    max_users: int = 1
    max_bots: int = 1
    max_strategies: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserSubscription:
    """Abonnement utilisateur."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    plan_id: str = ""
    tier: SubscriptionTier = SubscriptionTier.FREE
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    trial_end: Optional[datetime] = None
    grace_end: Optional[datetime] = None
    auto_renew: bool = True
    payment_method: Optional[PaymentMethod] = None
    payment_token: Optional[str] = None
    features: Dict[str, FeatureAccess] = field(default_factory=dict)
    usage: Dict[str, float] = field(default_factory=dict)
    quotas: Dict[str, float] = field(default_factory=dict)
    limits: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cancelled_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    last_billing_date: Optional[datetime] = None
    next_billing_date: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "tier": self.tier.value,
            "status": self.status.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "grace_end": self.grace_end.isoformat() if self.grace_end else None,
            "auto_renew": self.auto_renew,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "payment_token": self.payment_token,
            "features": self.features,
            "usage": self.usage,
            "quotas": self.quotas,
            "limits": self.limits,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
            "last_billing_date": self.last_billing_date.isoformat() if self.last_billing_date else None,
            "next_billing_date": self.next_billing_date.isoformat() if self.next_billing_date else None
        }


@dataclass
class SubscriptionInvoice:
    """Facture d'abonnement."""
    invoice_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscription_id: str = ""
    user_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    status: str = "pending"  # pending, paid, failed, refunded
    due_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=14))
    paid_date: Optional[datetime] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    tax: float = 0.0
    total: float = 0.0
    payment_method: Optional[PaymentMethod] = None
    transaction_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SubscriptionUsage:
    """Utilisation de l'abonnement."""
    usage_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subscription_id: str = ""
    user_id: str = ""
    metric: str = ""  # api_calls, bots, strategies, trades, data_points, etc.
    value: float = 0.0
    unit: str = "count"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class SubscriptionEngineInterface(ABC):
    """Interface abstraite pour le moteur d'abonnement."""
    
    @abstractmethod
    async def create_subscription(self, user_id: str, plan_id: str) -> UserSubscription:
        """Crée un abonnement."""
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Optional[UserSubscription]:
        """Récupère un abonnement."""
        pass
    
    @abstractmethod
    async def check_access(self, user_id: str, feature: str) -> FeatureAccess:
        """Vérifie l'accès à une fonctionnalité."""
        pass
    
    @abstractmethod
    async def track_usage(self, user_id: str, metric: str, value: float) -> None:
        """Enregistre l'utilisation."""
        pass


# ============== IMPLÉMENTATION ==============

class SubscriptionEngine(SubscriptionEngineInterface):
    """
    Moteur d'abonnement avancé pour le Hedge Bot.
    Gère les plans, les abonnements, le billing, les quotas et les accès.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des plans
        self._plans: Dict[str, SubscriptionPlan] = {}
        self._plans_lock = threading.RLock()
        
        # Gestion des abonnements
        self._subscriptions: Dict[str, UserSubscription] = {}
        self._subs_lock = threading.RLock()
        
        # Gestion des factures
        self._invoices: Dict[str, SubscriptionInvoice] = {}
        self._inv_lock = threading.RLock()
        
        # Gestion de l'utilisation
        self._usage: Dict[str, List[SubscriptionUsage]] = defaultdict(list)
        self._usage_lock = threading.RLock()
        
        # Cache des accès
        self._access_cache: Dict[str, FeatureAccess] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "plans_created": 0,
            "subscriptions_created": 0,
            "subscriptions_active": 0,
            "invoices_generated": 0,
            "invoices_paid": 0,
            "total_revenue": 0.0,
            "monthly_recurring_revenue": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("SubscriptionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_tier": SubscriptionTier.FREE,
            "free_plan": {
                "name": "Free",
                "max_users": 1,
                "max_bots": 1,
                "max_strategies": 3,
                "features": {
                    "market_data": FeatureAccess.READ,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.READ
                }
            },
            "currency": "USD",
            "tax_rate": 0.0,
            "grace_period_days": 7,
            "trial_days": 14,
            "billing_interval": 3600,
            "cache_ttl": 300,
            "enable_caching": True,
            "auto_billing": True,
            "payment_gateway": "stripe",
            "stripe_secret_key": "",
            "stripe_webhook_secret": ""
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'abonnement."""
        logger.info("SubscriptionEngine starting...")
        self._is_running = True
        
        # Création des plans par défaut
        await self._create_default_plans()
        
        # Chargement des abonnements existants
        await self._load_subscriptions()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._billing_loop())
        asyncio.create_task(self._expiration_check_loop())
        asyncio.create_task(self._usage_aggregation_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SubscriptionEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'abonnement."""
        logger.info("SubscriptionEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("SubscriptionEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_subscription(self, user_id: str, plan_id: str) -> UserSubscription:
        """Crée un abonnement."""
        with self._plans_lock:
            plan = self._plans.get(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
        
        # Vérification des abonnements existants
        existing = await self.get_user_subscription(user_id)
        if existing:
            # Annulation de l'ancien abonnement
            await self.cancel_subscription(existing.subscription_id)
        
        # Création du nouvel abonnement
        now = datetime.now(timezone.utc)
        end_date = now + self._get_billing_duration(plan.billing_period)
        
        subscription = UserSubscription(
            user_id=user_id,
            plan_id=plan_id,
            tier=plan.tier,
            status=SubscriptionStatus.PENDING,
            start_date=now,
            end_date=end_date,
            trial_end=now + timedelta(days=plan.trial_days) if plan.trial_days > 0 else None,
            grace_end=now + timedelta(days=plan.grace_period_days),
            auto_renew=True,
            features=plan.features.copy(),
            quotas=plan.quotas.copy(),
            limits=plan.limits.copy(),
            next_billing_date=end_date if plan.billing_period != BillingPeriod.MONTHLY else now + timedelta(days=30)
        )
        
        # Activation si pas de paiement requis
        if plan.price == 0:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.start_date = now
            subscription.end_date = now + timedelta(days=365 * 10)  # 10 ans pour gratuit
        
        with self._subs_lock:
            self._subscriptions[subscription.subscription_id] = subscription
            self._stats["subscriptions_created"] += 1
            if subscription.status == SubscriptionStatus.ACTIVE:
                self._stats["subscriptions_active"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"subscription:{subscription.subscription_id}",
                subscription.to_dict(),
                DataType.SUBSCRIPTION
            )
        
        logger.info(f"Subscription created: {subscription.subscription_id} "
                   f"user={user_id} plan={plan_id} tier={plan.tier.value}")
        
        return subscription
    
    async def get_subscription(self, subscription_id: str) -> Optional[UserSubscription]:
        """Récupère un abonnement."""
        with self._subs_lock:
            return self._subscriptions.get(subscription_id)
    
    async def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Récupère l'abonnement d'un utilisateur."""
        with self._subs_lock:
            for sub in self._subscriptions.values():
                if sub.user_id == user_id and sub.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL, SubscriptionStatus.GRACE_PERIOD]:
                    return sub
        return None
    
    async def check_access(self, user_id: str, feature: str) -> FeatureAccess:
        """Vérifie l'accès à une fonctionnalité."""
        # Vérification du cache
        cache_key = f"{user_id}:{feature}"
        with self._cache_lock:
            if cache_key in self._access_cache:
                return self._access_cache[cache_key]
        
        # Récupération de l'abonnement
        subscription = await self.get_user_subscription(user_id)
        
        if not subscription:
            return FeatureAccess.NONE
        
        # Vérification du statut
        if subscription.status not in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]:
            return FeatureAccess.NONE
        
        # Vérification de la fonctionnalité
        access = subscription.features.get(feature, FeatureAccess.NONE)
        
        # Mise en cache
        if self.config["enable_caching"]:
            with self._cache_lock:
                self._access_cache[cache_key] = access
        
        return access
    
    async def track_usage(self, user_id: str, metric: str, value: float) -> None:
        """Enregistre l'utilisation."""
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            logger.warning(f"No subscription found for user {user_id}")
            return
        
        # Création de l'enregistrement d'utilisation
        usage = SubscriptionUsage(
            subscription_id=subscription.subscription_id,
            user_id=user_id,
            metric=metric,
            value=value,
            period_start=subscription.start_date,
            period_end=subscription.end_date
        )
        
        with self._usage_lock:
            self._usage[subscription.subscription_id].append(usage)
        
        # Mise à jour des quotas
        with self._subs_lock:
            if subscription.subscription_id in self._subscriptions:
                sub = self._subscriptions[subscription.subscription_id]
                sub.usage[metric] = sub.usage.get(metric, 0) + value
        
        # Vérification des limites
        await self._check_limits(subscription, metric, value)
        
        logger.debug(f"Usage tracked: user={user_id} metric={metric} value={value}")
    
    # ========== MÉTHODES PRIVÉES - PLANS ==========
    
    async def _create_default_plans(self) -> None:
        """Crée les plans par défaut."""
        default_plans = [
            SubscriptionPlan(
                name="Free",
                tier=SubscriptionTier.FREE,
                description="Free plan with basic features",
                price=0.0,
                features={
                    "market_data": FeatureAccess.READ,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.READ,
                    "backtesting": FeatureAccess.READ
                },
                max_users=1,
                max_bots=1,
                max_strategies=3
            ),
            SubscriptionPlan(
                name="Basic",
                tier=SubscriptionTier.BASIC,
                description="Basic plan for individual traders",
                price=29.99,
                features={
                    "market_data": FeatureAccess.READ,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.READ,
                    "backtesting": FeatureAccess.EXECUTE,
                    "live_trading": FeatureAccess.EXECUTE
                },
                max_users=1,
                max_bots=3,
                max_strategies=10
            ),
            SubscriptionPlan(
                name="Premium",
                tier=SubscriptionTier.PREMIUM,
                description="Premium plan for serious traders",
                price=99.99,
                features={
                    "market_data": FeatureAccess.READ,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.WRITE,
                    "backtesting": FeatureAccess.EXECUTE,
                    "live_trading": FeatureAccess.EXECUTE,
                    "ai_signals": FeatureAccess.READ,
                    "hedging": FeatureAccess.EXECUTE
                },
                max_users=1,
                max_bots=10,
                max_strategies=25
            ),
            SubscriptionPlan(
                name="Professional",
                tier=SubscriptionTier.PROFESSIONAL,
                description="Professional plan for active traders",
                price=299.99,
                features={
                    "market_data": FeatureAccess.READ,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.WRITE,
                    "backtesting": FeatureAccess.EXECUTE,
                    "live_trading": FeatureAccess.EXECUTE,
                    "ai_signals": FeatureAccess.WRITE,
                    "hedging": FeatureAccess.EXECUTE,
                    "risk_management": FeatureAccess.EXECUTE
                },
                max_users=3,
                max_bots=25,
                max_strategies=50
            ),
            SubscriptionPlan(
                name="Enterprise",
                tier=SubscriptionTier.ENTERPRISE,
                description="Enterprise plan for organizations",
                price=999.99,
                features={
                    "market_data": FeatureAccess.WRITE,
                    "paper_trading": FeatureAccess.EXECUTE,
                    "reports": FeatureAccess.WRITE,
                    "backtesting": FeatureAccess.EXECUTE,
                    "live_trading": FeatureAccess.EXECUTE,
                    "ai_signals": FeatureAccess.WRITE,
                    "hedging": FeatureAccess.EXECUTE,
                    "risk_management": FeatureAccess.EXECUTE,
                    "api_access": FeatureAccess.EXECUTE
                },
                max_users=10,
                max_bots=100,
                max_strategies=200
            )
        ]
        
        for plan in default_plans:
            with self._plans_lock:
                self._plans[plan.plan_id] = plan
                self._stats["plans_created"] += 1
        
        logger.info(f"Created {len(default_plans)} default plans")
    
    async def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """Récupère un plan."""
        with self._plans_lock:
            return self._plans.get(plan_id)
    
    async def get_plans(self, active_only: bool = True) -> List[SubscriptionPlan]:
        """Récupère les plans."""
        with self._plans_lock:
            plans = list(self._plans.values())
            if active_only:
                plans = [p for p in plans if p.active]
            return sorted(plans, key=lambda p: p.price)
    
    # ========== MÉTHODES PRIVÉES - BILLING ==========
    
    async def _billing_loop(self) -> None:
        """Boucle de facturation."""
        while self._is_running:
            await asyncio.sleep(self.config["billing_interval"])
            
            try:
                with self._subs_lock:
                    now = datetime.now(timezone.utc)
                    for subscription in self._subscriptions.values():
                        if subscription.status == SubscriptionStatus.ACTIVE and subscription.auto_renew:
                            # Vérification de la date de facturation
                            if subscription.next_billing_date and subscription.next_billing_date <= now:
                                await self._process_billing(subscription)
                
            except Exception as e:
                logger.error(f"Billing loop error: {e}")
    
    async def _process_billing(self, subscription: UserSubscription) -> None:
        """Traite la facturation d'un abonnement."""
        try:
            # Récupération du plan
            plan = await self.get_plan(subscription.plan_id)
            if not plan:
                return
            
            # Création de la facture
            invoice = SubscriptionInvoice(
                subscription_id=subscription.subscription_id,
                user_id=subscription.user_id,
                amount=plan.price,
                currency=self.config["currency"],
                tax=plan.price * self.config["tax_rate"],
                total=plan.price * (1 + self.config["tax_rate"]),
                payment_method=subscription.payment_method,
                items=[{
                    "description": f"{plan.name} Plan - {plan.billing_period.value}",
                    "amount": plan.price,
                    "quantity": 1
                }]
            )
            
            with self._inv_lock:
                self._invoices[invoice.invoice_id] = invoice
                self._stats["invoices_generated"] += 1
            
            # Simulation de paiement
            # Dans un système réel, on utiliserait Stripe, PayPal, etc.
            if plan.price > 0:
                # Simulation de paiement réussi
                invoice.status = "paid"
                invoice.paid_date = datetime.now(timezone.utc)
                self._stats["invoices_paid"] += 1
                self._stats["total_revenue"] += invoice.total
                
                # Mise à jour de la date de fin
                subscription.end_date += self._get_billing_duration(plan.billing_period)
                subscription.next_billing_date = subscription.end_date + timedelta(days=1)
                subscription.updated_at = datetime.now(timezone.utc)
            else:
                # Plan gratuit
                subscription.end_date = datetime.now(timezone.utc) + timedelta(days=365 * 10)
            
            # Stockage de la facture
            if self.data_manager:
                await self.data_manager.store(
                    f"invoice:{invoice.invoice_id}",
                    invoice.to_dict(),
                    DataType.INVOICE
                )
            
            logger.info(f"Billing processed: {subscription.subscription_id} amount={invoice.total}")
            
        except Exception as e:
            logger.error(f"Billing processing error: {e}")
    
    # ========== MÉTHODES PRIVÉES - EXPIRATION ==========
    
    async def _expiration_check_loop(self) -> None:
        """Vérifie les abonnements expirés."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._subs_lock:
                    for subscription in self._subscriptions.values():
                        if subscription.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL, SubscriptionStatus.GRACE_PERIOD]:
                            # Vérification de la date de fin
                            if subscription.end_date and subscription.end_date <= now:
                                # Vérification de la période de grâce
                                if subscription.grace_end and subscription.grace_end > now:
                                    subscription.status = SubscriptionStatus.GRACE_PERIOD
                                else:
                                    subscription.status = SubscriptionStatus.EXPIRED
                                    self._stats["subscriptions_active"] -= 1
                                    logger.info(f"Subscription expired: {subscription.subscription_id}")
                
            except Exception as e:
                logger.error(f"Expiration check error: {e}")
    
    # ========== MÉTHODES PRIVÉES - USAGE ==========
    
    async def _check_limits(self, subscription: UserSubscription, metric: str, value: float) -> None:
        """Vérifie les limites d'utilisation."""
        limit = subscription.limits.get(metric)
        if limit:
            current = subscription.usage.get(metric, 0)
            if current > limit:
                logger.warning(f"Usage limit exceeded for {subscription.subscription_id}: "
                             f"{metric}={current}/{limit}")
                # Envoi d'une alerte
                if self.data_manager:
                    await self.data_manager.store(
                        f"alert:usage:{subscription.subscription_id}",
                        {
                            "metric": metric,
                            "current": current,
                            "limit": limit,
                            "user_id": subscription.user_id
                        },
                        DataType.ALERT
                    )
    
    async def _usage_aggregation_loop(self) -> None:
        """Agrège les données d'utilisation."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                # Agrégation de l'utilisation
                with self._usage_lock:
                    for sub_id, usage_list in self._usage.items():
                        if len(usage_list) > 100:
                            # Résumé des données
                            self._usage[sub_id] = usage_list[-100:]
                
            except Exception as e:
                logger.error(f"Usage aggregation error: {e}")
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _get_billing_duration(self, period: BillingPeriod) -> timedelta:
        """Obtient la durée de facturation."""
        if period == BillingPeriod.MONTHLY:
            return timedelta(days=30)
        elif period == BillingPeriod.QUARTERLY:
            return timedelta(days=90)
        elif period == BillingPeriod.SEMI_ANNUAL:
            return timedelta(days=180)
        elif period == BillingPeriod.ANNUAL:
            return timedelta(days=365)
        elif period == BillingPeriod.BIENNIAL:
            return timedelta(days=730)
        else:
            return timedelta(days=30)
    
    async def _load_subscriptions(self) -> None:
        """Charge les abonnements existants."""
        try:
            if self.data_manager:
                subs_data = await self.data_manager.retrieve(
                    "subscriptions:all",
                    DataType.SUBSCRIPTION
                )
                
                if subs_data:
                    for sub_dict in subs_data:
                        subscription = self._deserialize_subscription(sub_dict)
                        if subscription:
                            with self._subs_lock:
                                self._subscriptions[subscription.subscription_id] = subscription
                                if subscription.status == SubscriptionStatus.ACTIVE:
                                    self._stats["subscriptions_active"] += 1
            
            logger.info(f"Loaded {len(self._subscriptions)} subscriptions")
            
        except Exception as e:
            logger.error(f"Load subscriptions error: {e}")
    
    def _deserialize_subscription(self, data: Dict) -> Optional[UserSubscription]:
        """Désérialise un abonnement."""
        try:
            return UserSubscription(
                subscription_id=data.get("subscription_id", str(uuid.uuid4())),
                user_id=data.get("user_id", ""),
                plan_id=data.get("plan_id", ""),
                tier=SubscriptionTier(data.get("tier", "free")),
                status=SubscriptionStatus(data.get("status", "pending")),
                start_date=datetime.fromisoformat(data.get("start_date", datetime.now(timezone.utc).isoformat())),
                end_date=datetime.fromisoformat(data.get("end_date", datetime.now(timezone.utc).isoformat())),
                trial_end=datetime.fromisoformat(data.get("trial_end")) if data.get("trial_end") else None,
                grace_end=datetime.fromisoformat(data.get("grace_end")) if data.get("grace_end") else None,
                auto_renew=data.get("auto_renew", True),
                payment_method=PaymentMethod(data.get("payment_method")) if data.get("payment_method") else None,
                payment_token=data.get("payment_token"),
                features=data.get("features", {}),
                usage=data.get("usage", {}),
                quotas=data.get("quotas", {}),
                limits=data.get("limits", {}),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                cancelled_at=datetime.fromisoformat(data.get("cancelled_at")) if data.get("cancelled_at") else None,
                suspended_at=datetime.fromisoformat(data.get("suspended_at")) if data.get("suspended_at") else None,
                last_billing_date=datetime.fromisoformat(data.get("last_billing_date")) if data.get("last_billing_date") else None,
                next_billing_date=datetime.fromisoformat(data.get("next_billing_date")) if data.get("next_billing_date") else None
            )
        except Exception as e:
            logger.error(f"Error deserializing subscription: {e}")
            return None
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._subs_lock:
                    self._stats["total_subscriptions"] = len(self._subscriptions)
                    self._stats["active_subscriptions"] = len([
                        s for s in self._subscriptions.values()
                        if s.status == SubscriptionStatus.ACTIVE
                    ])
                    self._stats["trial_subscriptions"] = len([
                        s for s in self._subscriptions.values()
                        if s.status == SubscriptionStatus.TRIAL
                    ])
                
                # Calcul du MRR
                total_mrr = 0.0
                with self._subs_lock:
                    for sub in self._subscriptions.values():
                        if sub.status == SubscriptionStatus.ACTIVE:
                            plan = await self.get_plan(sub.plan_id)
                            if plan:
                                if plan.billing_period == BillingPeriod.MONTHLY:
                                    total_mrr += plan.price
                                elif plan.billing_period == BillingPeriod.QUARTERLY:
                                    total_mrr += plan.price / 3
                                elif plan.billing_period == BillingPeriod.ANNUAL:
                                    total_mrr += plan.price / 12
                
                self._stats["monthly_recurring_revenue"] = total_mrr
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "subscription:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Annule un abonnement."""
        with self._subs_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            if subscription.status in [SubscriptionStatus.CANCELLED, SubscriptionStatus.EXPIRED]:
                return True
            
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.now(timezone.utc)
            subscription.updated_at = datetime.now(timezone.utc)
            
            if subscription.status == SubscriptionStatus.ACTIVE:
                self._stats["subscriptions_active"] -= 1
            
            # Stockage persistant
            if self.data_manager:
                await self.data_manager.store(
                    f"subscription:{subscription.subscription_id}",
                    subscription.to_dict(),
                    DataType.SUBSCRIPTION
                )
            
            logger.info(f"Subscription cancelled: {subscription_id}")
            return True
    
    async def upgrade_subscription(self, subscription_id: str, new_plan_id: str) -> Optional[UserSubscription]:
        """Met à niveau un abonnement."""
        with self._subs_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return None
        
        # Récupération du nouveau plan
        with self._plans_lock:
            new_plan = self._plans.get(new_plan_id)
            if not new_plan:
                return None
        
        # Mise à jour de l'abonnement
        subscription.plan_id = new_plan_id
        subscription.tier = new_plan.tier
        subscription.features = new_plan.features.copy()
        subscription.quotas = new_plan.quotas.copy()
        subscription.limits = new_plan.limits.copy()
        subscription.updated_at = datetime.now(timezone.utc)
        
        # Prorata du prix
        if subscription.status == SubscriptionStatus.ACTIVE:
            old_plan = await self.get_plan(subscription.plan_id)
            if old_plan and new_plan.price > old_plan.price:
                # Calcul du prorata
                days_left = (subscription.end_date - datetime.now(timezone.utc)).days
                if days_left > 0:
                    prorata = (new_plan.price - old_plan.price) * (days_left / 30)
                    # Création d'une facture pour le prorata
                    invoice = SubscriptionInvoice(
                        subscription_id=subscription_id,
                        user_id=subscription.user_id,
                        amount=prorata,
                        status="paid",
                        items=[{
                            "description": f"Prorata upgrade from {old_plan.name} to {new_plan.name}",
                            "amount": prorata,
                            "quantity": 1
                        }]
                    )
                    with self._inv_lock:
                        self._invoices[invoice.invoice_id] = invoice
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"subscription:{subscription.subscription_id}",
                subscription.to_dict(),
                DataType.SUBSCRIPTION
            )
        
        logger.info(f"Subscription upgraded: {subscription_id} -> {new_plan_id}")
        return subscription
    
    async def get_invoices(self, user_id: str) -> List[SubscriptionInvoice]:
        """Récupère les factures d'un utilisateur."""
        with self._inv_lock:
            return [inv for inv in self._inv.values() if inv.user_id == user_id]
    
    async def get_usage(self, user_id: str, metric: Optional[str] = None) -> Dict[str, float]:
        """Récupère l'utilisation d'un utilisateur."""
        subscription = await self.get_user_subscription(user_id)
        if not subscription:
            return {}
        
        with self._subs_lock:
            if subscription.subscription_id in self._subscriptions:
                sub = self._subscriptions[subscription.subscription_id]
                if metric:
                    return {metric: sub.usage.get(metric, 0)}
                return sub.usage
        
        return {}
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._plans_lock:
            self._stats["total_plans"] = len(self._plans)
        with self._subs_lock:
            self._stats["total_subscriptions"] = len(self._subscriptions)
        with self._inv_lock:
            self._stats["total_invoices"] = len(self._invoices)
        
        return self._stats.copy()


# ============== SUBSCRIPTION AUTHENTICATOR ==============

class SubscriptionAuthenticator:
    """
    Authenticator pour les abonnements.
    Gère l'authentification et l'autorisation basée sur les abonnements.
    """
    
    def __init__(self, engine: SubscriptionEngine):
        self.engine = engine
        self._auth_cache: Dict[str, bool] = {}
        self._cache_lock = threading.RLock()
    
    async def authenticate(self, user_id: str, feature: str) -> bool:
        """Authentifie un utilisateur pour une fonctionnalité."""
        access = await self.engine.check_access(user_id, feature)
        return access != FeatureAccess.NONE
    
    async def authorize(self, user_id: str, feature: str, required_level: FeatureAccess) -> bool:
        """Autorise un utilisateur pour une fonctionnalité."""
        access = await self.engine.check_access(user_id, feature)
        return access == required_level
    
    async def can_execute(self, user_id: str, feature: str) -> bool:
        """Vérifie si l'utilisateur peut exécuter une fonctionnalité."""
        access = await self.engine.check_access(user_id, feature)
        return access in [FeatureAccess.EXECUTE, FeatureAccess.ADMIN]
    
    async def can_write(self, user_id: str, feature: str) -> bool:
        """Vérifie si l'utilisateur peut écrire sur une fonctionnalité."""
        access = await self.engine.check_access(user_id, feature)
        return access in [FeatureAccess.WRITE, FeatureAccess.ADMIN]
    
    async def can_read(self, user_id: str, feature: str) -> bool:
        """Vérifie si l'utilisateur peut lire une fonctionnalité."""
        access = await self.engine.check_access(user_id, feature)
        return access in [FeatureAccess.READ, FeatureAccess.WRITE, FeatureAccess.EXECUTE, FeatureAccess.ADMIN]


# ============== FACTORY ==============

class SubscriptionFactory:
    """Factory pour créer des composants d'abonnement."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SubscriptionEngine:
        """Crée un moteur d'abonnement."""
        engine = SubscriptionEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_authenticator(engine: SubscriptionEngine) -> SubscriptionAuthenticator:
        """Crée un authenticator."""
        return SubscriptionAuthenticator(engine)


# ============== EXPORT ==============

__all__ = [
    "SubscriptionTier",
    "SubscriptionStatus",
    "BillingPeriod",
    "PaymentMethod",
    "FeatureAccess",
    "SubscriptionPlan",
    "UserSubscription",
    "SubscriptionInvoice",
    "SubscriptionUsage",
    "SubscriptionEngineInterface",
    "SubscriptionEngine",
    "SubscriptionAuthenticator",
    "SubscriptionFactory"
]
