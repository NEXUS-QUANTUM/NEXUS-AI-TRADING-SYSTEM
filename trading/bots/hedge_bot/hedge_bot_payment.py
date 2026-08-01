# trading/bots/hedge_bot/hedge_bot_payment.py
# Advanced Payment Processing & Billing Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Payment Module - Module avancé de traitement des paiements et de gestion de la facturation
pour le Hedge Bot. Gère les paiements, les abonnements, les factures, les remboursements,
les passerelles de paiement, et la gestion des revenus pour le système de hedging.
"""

import asyncio
import json
import time
import hmac
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import aiohttp
import aiohttp.client_exceptions
import stripe
from stripe import StripeError

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_payment")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class PaymentMethod(Enum):
    """Méthodes de paiement."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"
    INVOICE = "invoice"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class PaymentStatus(Enum):
    """Statuts des paiements."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"


class PaymentGateway(Enum):
    """Passerelles de paiement."""
    STRIPE = "stripe"
    PAYPAL = "paypal"
    COINBASE = "coinbase"
    BINANCE = "binance"
    CUSTOM = "custom"


class BillingPeriod(Enum):
    """Périodes de facturation."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    BIENNIAL = "biennial"


# ============== DATA MODELS ==============

@dataclass
class Payment:
    """Modèle de paiement."""
    payment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    method: PaymentMethod = PaymentMethod.CREDIT_CARD
    gateway: PaymentGateway = PaymentGateway.STRIPE
    status: PaymentStatus = PaymentStatus.PENDING
    transaction_id: str = ""
    invoice_id: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class Invoice:
    """Modèle de facture."""
    invoice_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    number: str = ""
    amount: float = 0.0
    currency: str = "USD"
    tax: float = 0.0
    total: float = 0.0
    status: PaymentStatus = PaymentStatus.PENDING
    items: List[Dict[str, Any]] = field(default_factory=list)
    due_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=14))
    paid_date: Optional[datetime] = None
    payment_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Subscription:
    """Modèle d'abonnement."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    plan_id: str = ""
    plan_name: str = ""
    amount: float = 0.0
    currency: str = "USD"
    billing_period: BillingPeriod = BillingPeriod.MONTHLY
    status: str = "active"  # active, cancelled, expired, paused
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30))
    auto_renew: bool = True
    payment_method: Optional[PaymentMethod] = None
    payment_gateway: Optional[PaymentGateway] = None
    last_payment_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class PaymentEngineInterface(ABC):
    """Interface abstraite pour le moteur de paiement."""
    
    @abstractmethod
    async def process_payment(self, payment: Payment) -> Payment:
        """Traite un paiement."""
        pass
    
    @abstractmethod
    async def refund_payment(self, payment_id: str) -> Payment:
        """Rembourse un paiement."""
        pass
    
    @abstractmethod
    async def create_invoice(self, invoice: Invoice) -> Invoice:
        """Crée une facture."""
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Récupère un abonnement."""
        pass


# ============== IMPLÉMENTATION ==============

class PaymentEngine(PaymentEngineInterface):
    """
    Moteur de paiement avancé pour le Hedge Bot.
    Gère les paiements, les factures et les abonnements.
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
        
        # Gestion des paiements
        self._payments: Dict[str, Payment] = {}
        self._payments_lock = threading.RLock()
        
        # Gestion des factures
        self._invoices: Dict[str, Invoice] = {}
        self._invoices_lock = threading.RLock()
        
        # Gestion des abonnements
        self._subscriptions: Dict[str, Subscription] = {}
        self._subscriptions_lock = threading.RLock()
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Stripe
        self._stripe = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "payments_processed": 0,
            "payments_refunded": 0,
            "invoices_created": 0,
            "subscriptions_active": 0,
            "total_revenue": 0.0,
            "total_refunds": 0.0,
            "monthly_recurring_revenue": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("PaymentEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_currency": "USD",
            "default_gateway": PaymentGateway.STRIPE,
            "stripe_secret_key": "",
            "stripe_webhook_secret": "",
            "paypal_client_id": "",
            "paypal_client_secret": "",
            "coinbase_api_key": "",
            "invoice_prefix": "INV-",
            "tax_rate": 0.0,
            "max_retries": 3,
            "retry_delay": 1.0,
            "timeout": 30,
            "enable_webhooks": True,
            "webhook_url": "",
            "subscription_check_interval": 3600
        }
    
    async def start(self) -> None:
        """Démarre le moteur de paiement."""
        logger.info("PaymentEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
        )
        
        # Configuration Stripe
        if self.config["stripe_secret_key"]:
            stripe.api_key = self.config["stripe_secret_key"]
            self._stripe = stripe
        
        # Chargement des paiements
        await self._load_payments()
        
        # Chargement des factures
        await self._load_invoices()
        
        # Chargement des abonnements
        await self._load_subscriptions()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._subscription_checker())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._cleanup_loop())
        
        logger.info("PaymentEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de paiement."""
        logger.info("PaymentEngine stopping...")
        self._is_running = False
        
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("PaymentEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def process_payment(self, payment: Payment) -> Payment:
        """Traite un paiement."""
        self._stats["payments_processed"] += 1
        
        payment.status = PaymentStatus.PROCESSING
        
        try:
            # Traitement selon la passerelle
            if payment.gateway == PaymentGateway.STRIPE:
                result = await self._process_stripe_payment(payment)
            elif payment.gateway == PaymentGateway.PAYPAL:
                result = await self._process_paypal_payment(payment)
            elif payment.gateway == PaymentGateway.COINBASE:
                result = await self._process_coinbase_payment(payment)
            else:
                result = await self._process_custom_payment(payment)
            
            if result:
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.now(timezone.utc)
                self._stats["total_revenue"] += payment.amount
            else:
                payment.status = PaymentStatus.FAILED
            
        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.error = str(e)
            logger.error(f"Payment processing error: {e}")
        
        payment.updated_at = datetime.now(timezone.utc)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"payment:{payment.payment_id}",
                payment.to_dict(),
                DataType.PAYMENT
            )
        
        logger.info(f"Payment processed: {payment.payment_id} status={payment.status.value}")
        return payment
    
    async def refund_payment(self, payment_id: str) -> Payment:
        """Rembourse un paiement."""
        with self._payments_lock:
            payment = self._payments.get(payment_id)
            if not payment:
                raise ValueError(f"Payment {payment_id} not found")
        
        try:
            # Remboursement selon la passerelle
            if payment.gateway == PaymentGateway.STRIPE:
                result = await self._refund_stripe_payment(payment)
            elif payment.gateway == PaymentGateway.PAYPAL:
                result = await self._refund_paypal_payment(payment)
            else:
                result = await self._refund_custom_payment(payment)
            
            if result:
                payment.status = PaymentStatus.REFUNDED
                payment.refunded_at = datetime.now(timezone.utc)
                self._stats["payments_refunded"] += 1
                self._stats["total_refunds"] += payment.amount
        
        except Exception as e:
            logger.error(f"Refund error: {e}")
            raise
        
        payment.updated_at = datetime.now(timezone.utc)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"payment:{payment.payment_id}",
                payment.to_dict(),
                DataType.PAYMENT
            )
        
        logger.info(f"Payment refunded: {payment.payment_id}")
        return payment
    
    async def create_invoice(self, invoice: Invoice) -> Invoice:
        """Crée une facture."""
        self._stats["invoices_created"] += 1
        
        # Génération du numéro
        if not invoice.number:
            invoice.number = f"{self.config['invoice_prefix']}{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        # Calcul du total
        invoice.total = invoice.amount + invoice.tax
        
        with self._invoices_lock:
            self._invoices[invoice.invoice_id] = invoice
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"invoice:{invoice.invoice_id}",
                invoice.to_dict(),
                DataType.INVOICE
            )
        
        logger.info(f"Invoice created: {invoice.number}")
        return invoice
    
    async def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """Récupère un abonnement."""
        with self._subscriptions_lock:
            return self._subscriptions.get(subscription_id)
    
    # ========== MÉTHODES PRIVÉES - PASSERELLES ==========
    
    async def _process_stripe_payment(self, payment: Payment) -> bool:
        """Traite un paiement Stripe."""
        if not self._stripe:
            raise ValueError("Stripe not configured")
        
        try:
            # Création du paiement Stripe
            intent = self._stripe.PaymentIntent.create(
                amount=int(payment.amount * 100),
                currency=payment.currency.lower(),
                payment_method_types=["card"],
                metadata={
                    "payment_id": payment.payment_id,
                    "user_id": payment.user_id
                }
            )
            
            payment.transaction_id = intent.id
            
            # Dans un système réel, on confirmerait le paiement
            # confirmation = self._stripe.PaymentIntent.confirm(intent.id)
            
            return True
            
        except StripeError as e:
            logger.error(f"Stripe error: {e}")
            return False
    
    async def _refund_stripe_payment(self, payment: Payment) -> bool:
        """Rembourse un paiement Stripe."""
        if not self._stripe:
            raise ValueError("Stripe not configured")
        
        try:
            refund = self._stripe.Refund.create(
                payment_intent=payment.transaction_id
            )
            return True
        except StripeError as e:
            logger.error(f"Stripe refund error: {e}")
            return False
    
    async def _process_paypal_payment(self, payment: Payment) -> bool:
        """Traite un paiement PayPal."""
        # Dans un système réel, on utiliserait l'API PayPal
        return True
    
    async def _refund_paypal_payment(self, payment: Payment) -> bool:
        """Rembourse un paiement PayPal."""
        # Dans un système réel, on utiliserait l'API PayPal
        return True
    
    async def _process_coinbase_payment(self, payment: Payment) -> bool:
        """Traite un paiement Coinbase."""
        # Dans un système réel, on utiliserait l'API Coinbase
        return True
    
    async def _process_custom_payment(self, payment: Payment) -> bool:
        """Traite un paiement personnalisé."""
        # Simulation de paiement
        return True
    
    async def _refund_custom_payment(self, payment: Payment) -> bool:
        """Rembourse un paiement personnalisé."""
        # Simulation de remboursement
        return True
    
    # ========== MÉTHODES PRIVÉES - ABONNEMENTS ==========
    
    async def _subscription_checker(self) -> None:
        """Vérifie les abonnements périodiquement."""
        while self._is_running:
            await asyncio.sleep(self.config["subscription_check_interval"])
            
            try:
                now = datetime.now(timezone.utc)
                
                with self._subscriptions_lock:
                    for subscription in self._subscriptions.values():
                        if subscription.status != "active":
                            continue
                        
                        # Vérification de l'expiration
                        if subscription.end_date <= now:
                            if subscription.auto_renew:
                                # Renouvellement automatique
                                await self._renew_subscription(subscription)
                            else:
                                subscription.status = "expired"
                
            except Exception as e:
                logger.error(f"Subscription checker error: {e}")
    
    async def _renew_subscription(self, subscription: Subscription) -> None:
        """Renouvelle un abonnement."""
        # Création du paiement
        payment = Payment(
            user_id=subscription.user_id,
            amount=subscription.amount,
            currency=subscription.currency,
            method=subscription.payment_method or PaymentMethod.CREDIT_CARD,
            gateway=subscription.payment_gateway or PaymentGateway.STRIPE,
            description=f"Renewal of {subscription.plan_name}"
        )
        
        result = await self.process_payment(payment)
        
        if result.status == PaymentStatus.COMPLETED:
            # Mise à jour de l'abonnement
            subscription.end_date = datetime.now(timezone.utc) + self._get_billing_duration(subscription.billing_period)
            subscription.last_payment_id = payment.payment_id
            subscription.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Subscription renewed: {subscription.subscription_id}")
        else:
            logger.warning(f"Subscription renewal failed: {subscription.subscription_id}")
    
    def _get_billing_duration(self, period: BillingPeriod) -> timedelta:
        """Obtient la durée de facturation."""
        durations = {
            BillingPeriod.MONTHLY: timedelta(days=30),
            BillingPeriod.QUARTERLY: timedelta(days=90),
            BillingPeriod.SEMI_ANNUAL: timedelta(days=180),
            BillingPeriod.ANNUAL: timedelta(days=365),
            BillingPeriod.BIENNIAL: timedelta(days=730)
        }
        return durations.get(period, timedelta(days=30))
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_payments(self) -> None:
        """Charge les paiements existants."""
        try:
            if self.data_manager:
                payments_data = await self.data_manager.retrieve(
                    "payments:all",
                    DataType.PAYMENT
                )
                
                if payments_data:
                    for p_dict in payments_data:
                        payment = self._deserialize_payment(p_dict)
                        if payment:
                            with self._payments_lock:
                                self._payments[payment.payment_id] = payment
            
            logger.info(f"Loaded {len(self._payments)} payments")
            
        except Exception as e:
            logger.error(f"Load payments error: {e}")
    
    async def _load_invoices(self) -> None:
        """Charge les factures existantes."""
        try:
            if self.data_manager:
                invoices_data = await self.data_manager.retrieve(
                    "invoices:all",
                    DataType.INVOICE
                )
                
                if invoices_data:
                    for i_dict in invoices_data:
                        invoice = self._deserialize_invoice(i_dict)
                        if invoice:
                            with self._invoices_lock:
                                self._invoices[invoice.invoice_id] = invoice
            
            logger.info(f"Loaded {len(self._invoices)} invoices")
            
        except Exception as e:
            logger.error(f"Load invoices error: {e}")
    
    async def _load_subscriptions(self) -> None:
        """Charge les abonnements existants."""
        try:
            if self.data_manager:
                subs_data = await self.data_manager.retrieve(
                    "subscriptions:all",
                    DataType.SUBSCRIPTION
                )
                
                if subs_data:
                    for s_dict in subs_data:
                        sub = self._deserialize_subscription(s_dict)
                        if sub:
                            with self._subscriptions_lock:
                                self._subscriptions[sub.subscription_id] = sub
            
            logger.info(f"Loaded {len(self._subscriptions)} subscriptions")
            
        except Exception as e:
            logger.error(f"Load subscriptions error: {e}")
    
    def _deserialize_payment(self, data: Dict) -> Optional[Payment]:
        """Désérialise un paiement."""
        try:
            return Payment(
                payment_id=data.get("payment_id", str(uuid.uuid4())),
                user_id=data.get("user_id", ""),
                amount=data.get("amount", 0.0),
                currency=data.get("currency", "USD"),
                method=PaymentMethod(data.get("method", "credit_card")),
                gateway=PaymentGateway(data.get("gateway", "stripe")),
                status=PaymentStatus(data.get("status", "pending")),
                transaction_id=data.get("transaction_id", ""),
                invoice_id=data.get("invoice_id", ""),
                description=data.get("description", ""),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                completed_at=datetime.fromisoformat(data.get("completed_at")) if data.get("completed_at") else None,
                refunded_at=datetime.fromisoformat(data.get("refunded_at")) if data.get("refunded_at") else None,
                error=data.get("error")
            )
        except Exception as e:
            logger.error(f"Error deserializing payment: {e}")
            return None
    
    def _deserialize_invoice(self, data: Dict) -> Optional[Invoice]:
        """Désérialise une facture."""
        try:
            return Invoice(
                invoice_id=data.get("invoice_id", str(uuid.uuid4())),
                user_id=data.get("user_id", ""),
                number=data.get("number", ""),
                amount=data.get("amount", 0.0),
                currency=data.get("currency", "USD"),
                tax=data.get("tax", 0.0),
                total=data.get("total", 0.0),
                status=PaymentStatus(data.get("status", "pending")),
                items=data.get("items", []),
                due_date=datetime.fromisoformat(data.get("due_date", datetime.now(timezone.utc).isoformat())),
                paid_date=datetime.fromisoformat(data.get("paid_date")) if data.get("paid_date") else None,
                payment_id=data.get("payment_id"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing invoice: {e}")
            return None
    
    def _deserialize_subscription(self, data: Dict) -> Optional[Subscription]:
        """Désérialise un abonnement."""
        try:
            return Subscription(
                subscription_id=data.get("subscription_id", str(uuid.uuid4())),
                user_id=data.get("user_id", ""),
                plan_id=data.get("plan_id", ""),
                plan_name=data.get("plan_name", ""),
                amount=data.get("amount", 0.0),
                currency=data.get("currency", "USD"),
                billing_period=BillingPeriod(data.get("billing_period", "monthly")),
                status=data.get("status", "active"),
                start_date=datetime.fromisoformat(data.get("start_date", datetime.now(timezone.utc).isoformat())),
                end_date=datetime.fromisoformat(data.get("end_date", datetime.now(timezone.utc).isoformat())),
                auto_renew=data.get("auto_renew", True),
                payment_method=PaymentMethod(data.get("payment_method")) if data.get("payment_method") else None,
                payment_gateway=PaymentGateway(data.get("payment_gateway")) if data.get("payment_gateway") else None,
                last_payment_id=data.get("last_payment_id"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing subscription: {e}")
            return None
    
    async def _cleanup_loop(self) -> None:
        """Nettoie les données anciennes."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=365)
                
                # Nettoyage des paiements
                with self._payments_lock:
                    old_payments = [
                        pid for pid, p in self._payments.items()
                        if p.created_at < cutoff
                    ]
                    for pid in old_payments:
                        del self._payments[pid]
                
                # Nettoyage des factures
                with self._invoices_lock:
                    old_invoices = [
                        iid for iid, i in self._invoices.items()
                        if i.created_at < cutoff
                    ]
                    for iid in old_invoices:
                        del self._invoices[iid]
                
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._subscriptions_lock:
                    active_subs = len([s for s in self._subscriptions.values() if s.status == "active"])
                    self._stats["subscriptions_active"] = active_subs
                    
                    # Calcul du MRR
                    mrr = sum(s.amount for s in self._subscriptions.values() if s.status == "active" and s.billing_period == BillingPeriod.MONTHLY)
                    mrr += sum(s.amount / 3 for s in self._subscriptions.values() if s.status == "active" and s.billing_period == BillingPeriod.QUARTERLY)
                    mrr += sum(s.amount / 12 for s in self._subscriptions.values() if s.status == "active" and s.billing_period == BillingPeriod.ANNUAL)
                    self._stats["monthly_recurring_revenue"] = mrr
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "payment:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Récupère un paiement."""
        with self._payments_lock:
            return self._payments.get(payment_id)
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Récupère une facture."""
        with self._invoices_lock:
            return self._invoices.get(invoice_id)
    
    async def create_subscription(self, subscription: Subscription) -> str:
        """Crée un abonnement."""
        with self._subscriptions_lock:
            self._subscriptions[subscription.subscription_id] = subscription
        
        if self.data_manager:
            await self.data_manager.store(
                f"subscription:{subscription.subscription_id}",
                subscription.to_dict(),
                DataType.SUBSCRIPTION
            )
        
        logger.info(f"Subscription created: {subscription.subscription_id}")
        return subscription.subscription_id
    
    async def cancel_subscription(self, subscription_id: str) -> bool:
        """Annule un abonnement."""
        with self._subscriptions_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.status = "cancelled"
            subscription.auto_renew = False
            subscription.updated_at = datetime.now(timezone.utc)
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._subscriptions_lock:
            self._stats["active_subscriptions"] = len([s for s in self._subscriptions.values() if s.status == "active"])
        
        return self._stats.copy()


# ============== PAYMENT WEBHOOK HANDLER ==============

class PaymentWebhookHandler:
    """
    Handler de webhooks de paiement.
    Gère les webhooks des passerelles de paiement.
    """
    
    def __init__(self, engine: PaymentEngine):
        self.engine = engine
    
    async def handle_stripe_webhook(self, payload: bytes, sig_header: str) -> bool:
        """Traite un webhook Stripe."""
        try:
            # Vérification de la signature
            webhook_secret = self.engine.config["stripe_webhook_secret"]
            if webhook_secret:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, webhook_secret
                )
            else:
                event = json.loads(payload)
            
            # Traitement selon l'événement
            if event["type"] == "payment_intent.succeeded":
                await self._handle_payment_success(event)
            elif event["type"] == "payment_intent.failed":
                await self._handle_payment_failure(event)
            
            return True
            
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return False
    
    async def _handle_payment_success(self, event: Dict[str, Any]) -> None:
        """Gère un paiement réussi."""
        logger.info(f"Payment succeeded: {event['data']['object']['id']}")
    
    async def _handle_payment_failure(self, event: Dict[str, Any]) -> None:
        """Gère un paiement échoué."""
        logger.warning(f"Payment failed: {event['data']['object']['id']}")


# ============== FACTORY ==============

class PaymentFactory:
    """Factory pour créer des composants de paiement."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PaymentEngine:
        """Crée un moteur de paiement."""
        engine = PaymentEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_webhook_handler(engine: PaymentEngine) -> PaymentWebhookHandler:
        """Crée un handler de webhooks."""
        return PaymentWebhookHandler(engine)


# ============== EXPORT ==============

__all__ = [
    "PaymentMethod",
    "PaymentStatus",
    "PaymentGateway",
    "BillingPeriod",
    "Payment",
    "Invoice",
    "Subscription",
    "PaymentEngineInterface",
    "PaymentEngine",
    "PaymentWebhookHandler",
    "PaymentFactory"
]
