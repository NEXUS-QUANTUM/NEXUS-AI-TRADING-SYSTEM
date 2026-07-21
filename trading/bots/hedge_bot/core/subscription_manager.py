"""
NEXUS AI TRADING SYSTEM - Hedge Bot Subscription Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire d'abonnements pour le bot de couverture
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class SubscriptionType(Enum):
    """Types d'abonnements"""
    PREMIUM = "premium"
    STANDARD = "standard"
    BASIC = "basic"
    TRIAL = "trial"
    CUSTOM = "custom"

class SubscriptionStatus(Enum):
    """Statuts d'abonnement"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    TRIAL = "trial"
    PENDING = "pending"
    FAILED = "failed"

class SubscriptionTier(Enum):
    """Niveaux d'abonnement"""
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"
    TIER_4 = "tier_4"
    CUSTOM = "custom"

class PaymentMethod(Enum):
    """Méthodes de paiement"""
    CREDIT_CARD = "credit_card"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    COINBASE = "coinbase"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class SubscriptionPlan:
    """Plan d'abonnement"""
    id: str
    name: str
    type: SubscriptionType
    tier: SubscriptionTier
    price: float
    currency: str
    interval: str  # monthly, quarterly, yearly
    features: List[str] = field(default_factory=list)
    limits: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Subscription:
    """Abonnement"""
    id: str
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime] = None
    auto_renew: bool = True
    payment_method: Optional[PaymentMethod] = None
    last_payment: Optional[datetime] = None
    next_payment: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SubscriptionFeature:
    """Fonctionnalité d'abonnement"""
    id: str
    name: str
    description: str
    tier: SubscriptionTier
    enabled: bool = True
    limits: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SubscriptionUsage:
    """Utilisation d'abonnement"""
    subscription_id: str
    feature_id: str
    used: float = 0.0
    limit: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# SUBSCRIPTION MANAGER
# ============================================================

class SubscriptionManager:
    """
    Gestionnaire d'abonnements pour le bot de couverture
    
    Gère les plans, abonnements et fonctionnalités
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        check_interval: int = 3600,
        enable_auto_renew: bool = True
    ):
        """
        Initialise le gestionnaire d'abonnements
        
        Args:
            config: Configuration
            check_interval: Intervalle de vérification
            enable_auto_renew: Activer le renouvellement automatique
        """
        self.config = config or {}
        self.check_interval = check_interval
        self.enable_auto_renew = enable_auto_renew
        
        # Plans
        self.plans: Dict[str, SubscriptionPlan] = {}
        self.default_plans: Dict[str, SubscriptionPlan] = {}
        
        # Abonnements
        self.subscriptions: Dict[str, Subscription] = {}
        self.active_subscriptions: Dict[str, Subscription] = {}
        
        # Fonctionnalités
        self.features: Dict[str, SubscriptionFeature] = {}
        self.feature_by_tier: Dict[SubscriptionTier, List[SubscriptionFeature]] = defaultdict(list)
        
        # Utilisation
        self.usage: Dict[str, SubscriptionUsage] = {}
        self.usage_by_subscription: Dict[str, List[SubscriptionUsage]] = defaultdict(list)
        
        # Statistiques
        self.stats = {
            'total_plans': 0,
            'total_subscriptions': 0,
            'active_subscriptions': 0,
            'by_type': {},
            'by_tier': {},
            'by_status': {},
            'revenue': 0.0,
            'churn_rate': 0.0,
            'retention_rate': 0.0,
        }
        
        # Historique
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Événements
        self.events: List[Dict[str, Any]] = []
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._check_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'created': [],
            'updated': [],
            'expired': [],
            'cancelled': [],
            'renewed': [],
        }
        
        # Charger les plans par défaut
        self._load_default_plans()
        self._load_default_features()
        
        logger.info("SubscriptionManager initialized")
    
    # ============================================================
    # PLAN MANAGEMENT
    # ============================================================
    
    def _load_default_plans(self):
        """Charge les plans par défaut"""
        default_plans = [
            SubscriptionPlan(
                id="plan_basic",
                name="Basic Plan",
                type=SubscriptionType.BASIC,
                tier=SubscriptionTier.TIER_1,
                price=0.0,
                currency="USD",
                interval="monthly",
                features=["basic_trading", "up_to_5_positions"],
                limits={"max_positions": 5, "max_trades_per_day": 10}
            ),
            SubscriptionPlan(
                id="plan_standard",
                name="Standard Plan",
                type=SubscriptionType.STANDARD,
                tier=SubscriptionTier.TIER_2,
                price=99.99,
                currency="USD",
                interval="monthly",
                features=["advanced_trading", "up_to_20_positions", "risk_management"],
                limits={"max_positions": 20, "max_trades_per_day": 50}
            ),
            SubscriptionPlan(
                id="plan_premium",
                name="Premium Plan",
                type=SubscriptionType.PREMIUM,
                tier=SubscriptionTier.TIER_3,
                price=299.99,
                currency="USD",
                interval="monthly",
                features=["professional_trading", "unlimited_positions", "ai_optimization", "priority_support"],
                limits={"max_positions": 100, "max_trades_per_day": 500}
            ),
        ]
        
        for plan in default_plans:
            self.add_plan(plan)
            self.default_plans[plan.id] = plan
    
    def _load_default_features(self):
        """Charge les fonctionnalités par défaut"""
        default_features = [
            SubscriptionFeature(
                id="basic_trading",
                name="Basic Trading",
                description="Trading de base avec ordres limités",
                tier=SubscriptionTier.TIER_1,
                enabled=True,
                limits={"max_trades_per_day": 10}
            ),
            SubscriptionFeature(
                id="advanced_trading",
                name="Advanced Trading",
                description="Trading avancé avec toutes les fonctionnalités",
                tier=SubscriptionTier.TIER_2,
                enabled=True,
                limits={"max_trades_per_day": 50}
            ),
            SubscriptionFeature(
                id="professional_trading",
                name="Professional Trading",
                description="Trading professionnel avec fonctionnalités complètes",
                tier=SubscriptionTier.TIER_3,
                enabled=True,
                limits={"max_trades_per_day": 500}
            ),
            SubscriptionFeature(
                id="risk_management",
                name="Risk Management",
                description="Gestion des risques avancée",
                tier=SubscriptionTier.TIER_2,
                enabled=True,
                limits={}
            ),
            SubscriptionFeature(
                id="ai_optimization",
                name="AI Optimization",
                description="Optimisation par IA des stratégies",
                tier=SubscriptionTier.TIER_3,
                enabled=True,
                limits={}
            ),
            SubscriptionFeature(
                id="priority_support",
                name="Priority Support",
                description="Support prioritaire 24/7",
                tier=SubscriptionTier.TIER_3,
                enabled=True,
                limits={}
            ),
        ]
        
        for feature in default_features:
            self.add_feature(feature)
    
    def add_plan(self, plan: SubscriptionPlan):
        """
        Ajoute un plan d'abonnement
        
        Args:
            plan: Plan à ajouter
        """
        with self._lock:
            self.plans[plan.id] = plan
            self.stats['total_plans'] = len(self.plans)
            logger.info(f"Subscription plan added: {plan.name}")
    
    def remove_plan(self, plan_id: str):
        """
        Supprime un plan d'abonnement
        
        Args:
            plan_id: ID du plan
        """
        with self._lock:
            if plan_id in self.plans:
                del self.plans[plan_id]
                self.stats['total_plans'] = len(self.plans)
    
    def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """
        Récupère un plan d'abonnement
        
        Args:
            plan_id: ID du plan
            
        Returns:
            Optional[SubscriptionPlan]: Plan
        """
        return self.plans.get(plan_id)
    
    def get_plans(self, tier: Optional[SubscriptionTier] = None) -> List[SubscriptionPlan]:
        """
        Récupère les plans d'abonnement
        
        Args:
            tier: Niveau
            
        Returns:
            List[SubscriptionPlan]: Plans
        """
        plans = list(self.plans.values())
        if tier:
            plans = [p for p in plans if p.tier == tier]
        return plans
    
    # ============================================================
    # FEATURE MANAGEMENT
    # ============================================================
    
    def add_feature(self, feature: SubscriptionFeature):
        """
        Ajoute une fonctionnalité
        
        Args:
            feature: Fonctionnalité à ajouter
        """
        with self._lock:
            self.features[feature.id] = feature
            self.feature_by_tier[feature.tier].append(feature)
            logger.info(f"Subscription feature added: {feature.name}")
    
    def remove_feature(self, feature_id: str):
        """
        Supprime une fonctionnalité
        
        Args:
            feature_id: ID de la fonctionnalité
        """
        with self._lock:
            if feature_id in self.features:
                feature = self.features.pop(feature_id)
                self.feature_by_tier[feature.tier] = [
                    f for f in self.feature_by_tier.get(feature.tier, [])
                    if f.id != feature_id
                ]
    
    def get_feature(self, feature_id: str) -> Optional[SubscriptionFeature]:
        """
        Récupère une fonctionnalité
        
        Args:
            feature_id: ID de la fonctionnalité
            
        Returns:
            Optional[SubscriptionFeature]: Fonctionnalité
        """
        return self.features.get(feature_id)
    
    def get_features_by_tier(self, tier: SubscriptionTier) -> List[SubscriptionFeature]:
        """
        Récupère les fonctionnalités par niveau
        
        Args:
            tier: Niveau
            
        Returns:
            List[SubscriptionFeature]: Fonctionnalités
        """
        return self.feature_by_tier.get(tier, [])
    
    # ============================================================
    # SUBSCRIPTION MANAGEMENT
    # ============================================================
    
    def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        payment_method: Optional[PaymentMethod] = None,
        auto_renew: bool = True,
        trial_period: Optional[int] = None
    ) -> Subscription:
        """
        Crée un abonnement
        
        Args:
            user_id: ID de l'utilisateur
            plan_id: ID du plan
            payment_method: Méthode de paiement
            auto_renew: Renouvellement automatique
            trial_period: Période d'essai en jours
            
        Returns:
            Subscription: Abonnement créé
        """
        with self._lock:
            plan = self.get_plan(plan_id)
            if not plan:
                raise ValueError(f"Plan not found: {plan_id}")
            
            subscription = Subscription(
                id=f"sub_{uuid.uuid4().hex[:8]}",
                user_id=user_id,
                plan_id=plan_id,
                status=SubscriptionStatus.TRIAL if trial_period else SubscriptionStatus.ACTIVE,
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=trial_period or 30),
                auto_renew=auto_renew,
                payment_method=payment_method,
                metadata={'plan': plan.__dict__}
            )
            
            self.subscriptions[subscription.id] = subscription
            self.active_subscriptions[subscription.id] = subscription
            self.stats['total_subscriptions'] = len(self.subscriptions)
            self.stats['active_subscriptions'] = len(self.active_subscriptions)
            
            self._update_stats()
            self._trigger_event('created', subscription)
            
            logger.info(f"Subscription created: {subscription.id} for user {user_id}")
            return subscription
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """
        Annule un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            
        Returns:
            bool: True si annulé
        """
        with self._lock:
            subscription = self.subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.auto_renew = False
            
            self.active_subscriptions.pop(subscription_id, None)
            self.stats['active_subscriptions'] = len(self.active_subscriptions)
            
            self._update_stats()
            self._trigger_event('cancelled', subscription)
            
            logger.info(f"Subscription cancelled: {subscription_id}")
            return True
    
    def pause_subscription(self, subscription_id: str) -> bool:
        """
        Met en pause un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            
        Returns:
            bool: True si mis en pause
        """
        with self._lock:
            subscription = self.subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.status = SubscriptionStatus.PAUSED
            self._update_stats()
            logger.info(f"Subscription paused: {subscription_id}")
            return True
    
    def resume_subscription(self, subscription_id: str) -> bool:
        """
        Reprend un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            
        Returns:
            bool: True si repris
        """
        with self._lock:
            subscription = self.subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.status = SubscriptionStatus.ACTIVE
            self.active_subscriptions[subscription.id] = subscription
            self.stats['active_subscriptions'] = len(self.active_subscriptions)
            
            self._update_stats()
            logger.info(f"Subscription resumed: {subscription_id}")
            return True
    
    def renew_subscription(self, subscription_id: str) -> bool:
        """
        Renouvelle un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            
        Returns:
            bool: True si renouvelé
        """
        with self._lock:
            subscription = self.subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            # Calculer la nouvelle date de fin
            plan = self.get_plan(subscription.plan_id)
            if not plan:
                return False
            
            if plan.interval == 'monthly':
                delta = timedelta(days=30)
            elif plan.interval == 'quarterly':
                delta = timedelta(days=90)
            elif plan.interval == 'yearly':
                delta = timedelta(days=365)
            else:
                delta = timedelta(days=30)
            
            subscription.end_date = (subscription.end_date or datetime.now()) + delta
            subscription.last_payment = datetime.now()
            subscription.next_payment = subscription.end_date
            subscription.status = SubscriptionStatus.ACTIVE
            
            self.active_subscriptions[subscription.id] = subscription
            self.stats['active_subscriptions'] = len(self.active_subscriptions)
            
            # Mettre à jour le revenu
            self.stats['revenue'] += plan.price
            
            self._update_stats()
            self._trigger_event('renewed', subscription)
            
            logger.info(f"Subscription renewed: {subscription_id}")
            return True
    
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        Récupère un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            
        Returns:
            Optional[Subscription]: Abonnement
        """
        return self.subscriptions.get(subscription_id)
    
    def get_user_subscriptions(self, user_id: str) -> List[Subscription]:
        """
        Récupère les abonnements d'un utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            List[Subscription]: Abonnements
        """
        return [s for s in self.subscriptions.values() if s.user_id == user_id]
    
    def get_active_subscriptions(self) -> List[Subscription]:
        """
        Récupère les abonnements actifs
        
        Returns:
            List[Subscription]: Abonnements actifs
        """
        return list(self.active_subscriptions.values())
    
    # ============================================================
    # USAGE MANAGEMENT
    # ============================================================
    
    def track_usage(
        self,
        subscription_id: str,
        feature_id: str,
        amount: float = 1.0
    ) -> bool:
        """
        Enregistre l'utilisation d'une fonctionnalité
        
        Args:
            subscription_id: ID de l'abonnement
            feature_id: ID de la fonctionnalité
            amount: Montant utilisé
            
        Returns:
            bool: True si enregistré
        """
        with self._lock:
            subscription = self.subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            # Vérifier si l'abonnement est actif
            if subscription.status != SubscriptionStatus.ACTIVE:
                return False
            
            # Récupérer la fonctionnalité
            feature = self.features.get(feature_id)
            if not feature:
                return False
            
            # Vérifier si la fonctionnalité est accessible
            plan = self.get_plan(subscription.plan_id)
            if not plan:
                return False
            
            if feature_id not in plan.features:
                return False
            
            # Mettre à jour l'utilisation
            usage_key = f"{subscription_id}_{feature_id}"
            if usage_key not in self.usage:
                self.usage[usage_key] = SubscriptionUsage(
                    subscription_id=subscription_id,
                    feature_id=feature_id,
                    limit=feature.limits.get('max_usage', float('inf'))
                )
            
            usage = self.usage[usage_key]
            usage.used += amount
            
            # Vérifier les limites
            if usage.used > usage.limit:
                logger.warning(f"Usage limit exceeded: {subscription_id} - {feature_id}")
                return False
            
            # Ajouter à l'historique
            self.usage_by_subscription[subscription_id].append(usage)
            
            return True
    
    def get_usage(
        self,
        subscription_id: str,
        feature_id: Optional[str] = None
    ) -> List[SubscriptionUsage]:
        """
        Récupère l'utilisation d'un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            feature_id: ID de la fonctionnalité
            
        Returns:
            List[SubscriptionUsage]: Utilisation
        """
        usages = self.usage_by_subscription.get(subscription_id, [])
        if feature_id:
            usages = [u for u in usages if u.feature_id == feature_id]
        return usages
    
    def reset_usage(self, subscription_id: str, feature_id: Optional[str] = None):
        """
        Réinitialise l'utilisation d'un abonnement
        
        Args:
            subscription_id: ID de l'abonnement
            feature_id: ID de la fonctionnalité
        """
        with self._lock:
            if feature_id:
                usage_key = f"{subscription_id}_{feature_id}"
                if usage_key in self.usage:
                    self.usage[usage_key].used = 0
                    self.usage[usage_key].last_reset = datetime.now()
            else:
                for key, usage in self.usage.items():
                    if usage.subscription_id == subscription_id:
                        usage.used = 0
                        usage.last_reset = datetime.now()
    
    # ============================================================
    # FEATURE ACCESS
    # ============================================================
    
    def has_feature(self, subscription_id: str, feature_id: str) -> bool:
        """
        Vérifie si une fonctionnalité est accessible
        
        Args:
            subscription_id: ID de l'abonnement
            feature_id: ID de la fonctionnalité
            
        Returns:
            bool: True si accessible
        """
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return False
        
        if subscription.status != SubscriptionStatus.ACTIVE:
            return False
        
        plan = self.get_plan(subscription.plan_id)
        if not plan:
            return False
        
        return feature_id in plan.features
    
    def check_feature_limit(
        self,
        subscription_id: str,
        feature_id: str,
        required: float = 1.0
    ) -> bool:
        """
        Vérifie si une fonctionnalité a des limites disponibles
        
        Args:
            subscription_id: ID de l'abonnement
            feature_id: ID de la fonctionnalité
            required: Montant requis
            
        Returns:
            bool: True si disponible
        """
        if not self.has_feature(subscription_id, feature_id):
            return False
        
        usage_key = f"{subscription_id}_{feature_id}"
        if usage_key not in self.usage:
            return True
        
        usage = self.usage[usage_key]
        return usage.used + required <= usage.limit
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback pour un événement
        
        Args:
            event: Événement ('created', 'updated', 'expired', 'cancelled', 'renewed')
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, subscription: Subscription):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            subscription: Abonnement
        """
        event_data = {
            'event': event,
            'subscription': subscription.__dict__,
            'timestamp': datetime.now().isoformat()
        }
        self.events.append(event_data)
        
        for callback in self._callbacks.get(event, []):
            try:
                callback(subscription)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        with self._lock:
            # Par type
            by_type = {}
            for sub in self.subscriptions.values():
                plan = self.get_plan(sub.plan_id)
                if plan:
                    type_key = plan.type.value
                    by_type[type_key] = by_type.get(type_key, 0) + 1
            self.stats['by_type'] = by_type
            
            # Par tier
            by_tier = {}
            for sub in self.subscriptions.values():
                plan = self.get_plan(sub.plan_id)
                if plan:
                    tier_key = plan.tier.value
                    by_tier[tier_key] = by_tier.get(tier_key, 0) + 1
            self.stats['by_tier'] = by_tier
            
            # Par statut
            by_status = {}
            for sub in self.subscriptions.values():
                status_key = sub.status.value
                by_status[status_key] = by_status.get(status_key, 0) + 1
            self.stats['by_status'] = by_status
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return self.stats.copy()
    
    def get_report(self) -> Dict[str, Any]:
        """
        Récupère un rapport
        
        Returns:
            Dict[str, Any]: Rapport
        """
        return {
            'timestamp': time.time(),
            'stats': self.get_stats(),
            'plans': [
                {
                    'id': p.id,
                    'name': p.name,
                    'type': p.type.value,
                    'tier': p.tier.value,
                    'price': p.price,
                    'interval': p.interval,
                    'features': p.features,
                    'subscribers': sum(1 for s in self.subscriptions.values() if s.plan_id == p.id)
                }
                for p in self.plans.values()
            ],
            'subscriptions': [
                {
                    'id': s.id,
                    'user_id': s.user_id,
                    'plan_id': s.plan_id,
                    'status': s.status.value,
                    'start_date': s.start_date.isoformat(),
                    'end_date': s.end_date.isoformat() if s.end_date else None,
                    'auto_renew': s.auto_renew,
                }
                for s in self.subscriptions.values()
            ],
            'events': self.events[-20:],
        }
    
    # ============================================================
    # MONITORING
    # ============================================================
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            return
        
        self._running = True
        self._check_task = threading.Thread(target=self._check_loop, daemon=True)
        self._check_task.start()
        
        logger.info("SubscriptionManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._check_task:
            self._check_task.join(timeout=2)
        
        logger.info("SubscriptionManager monitoring stopped")
    
    def _check_loop(self):
        """Boucle de vérification"""
        while self._running:
            try:
                self._check_expiring()
                self._check_expired()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Check error: {e}")
                time.sleep(self.check_interval)
    
    def _check_expiring(self):
        """Vérifie les abonnements expirant"""
        now = datetime.now()
        for subscription in self.subscriptions.values():
            if subscription.end_date:
                days_until_expiry = (subscription.end_date - now).days
                if days_until_expiry <= 7 and days_until_expiry > 0:
                    logger.info(f"Subscription expiring soon: {subscription.id} ({days_until_expiry} days)")
    
    def _check_expired(self):
        """Vérifie les abonnements expirés"""
        now = datetime.now()
        for subscription in list(self.subscriptions.values()):
            if subscription.end_date and now > subscription.end_date:
                if subscription.status == SubscriptionStatus.ACTIVE:
                    if self.enable_auto_renew and subscription.auto_renew:
                        self.renew_subscription(subscription.id)
                    else:
                        subscription.status = SubscriptionStatus.EXPIRED
                        self.active_subscriptions.pop(subscription.id, None)
                        self.stats['active_subscriptions'] = len(self.active_subscriptions)
                        self._update_stats()
                        self._trigger_event('expired', subscription)
                        logger.info(f"Subscription expired: {subscription.id}")

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_subscription_manager: Optional[SubscriptionManager] = None

def get_subscription_manager(
    config: Optional[Dict[str, Any]] = None
) -> SubscriptionManager:
    """
    Récupère le gestionnaire d'abonnements (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        SubscriptionManager: Gestionnaire d'abonnements
    """
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager(config)
    return _subscription_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'SubscriptionType',
    'SubscriptionStatus',
    'SubscriptionTier',
    'PaymentMethod',
    'SubscriptionPlan',
    'Subscription',
    'SubscriptionFeature',
    'SubscriptionUsage',
    'SubscriptionManager',
    'get_subscription_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Subscription manager module initialized")
