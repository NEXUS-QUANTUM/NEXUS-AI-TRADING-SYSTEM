"""
NEXUS AI TRADING SYSTEM - Hedge Bot Invoicing Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Gestionnaire de facturation pour le bot de couverture
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
from typing import Dict, Any, List, Optional, Union, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import uuid
import hashlib

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class InvoiceStatus(Enum):
    """Statuts de facture"""
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIAL = "partial"

class InvoiceType(Enum):
    """Types de facture"""
    SUBSCRIPTION = "subscription"
    USAGE = "usage"
    SERVICE = "service"
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    CREDIT = "credit"
    DEBIT = "debit"

class PaymentMethod(Enum):
    """Méthodes de paiement"""
    CREDIT_CARD = "credit_card"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    COINBASE = "coinbase"

class PaymentStatus(Enum):
    """Statuts de paiement"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class InvoiceItem:
    """Ligne de facture"""
    id: str
    description: str
    quantity: float
    unit_price: float
    total: float
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    discount: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Invoice:
    """Facture"""
    id: str
    number: str
    type: InvoiceType
    status: InvoiceStatus
    user_id: str
    items: List[InvoiceItem]
    subtotal: float
    tax_total: float
    discount_total: float
    total: float
    currency: str = "USD"
    issued_date: datetime = field(default_factory=datetime.now)
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    payment_method: Optional[PaymentMethod] = None
    payment_status: Optional[PaymentStatus] = None
    payment_id: Optional[str] = None
    notes: str = ""

@dataclass
class PaymentTransaction:
    """Transaction de paiement"""
    id: str
    invoice_id: str
    amount: float
    currency: str
    method: PaymentMethod
    status: PaymentStatus
    timestamp: datetime
    reference: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BillingConfig:
    """Configuration de facturation"""
    enabled: bool = True
    currency: str = "USD"
    tax_rate: float = 0.0
    payment_grace_period: int = 7  # days
    invoice_prefix: str = "INV"
    auto_generate: bool = True
    auto_send: bool = True
    payment_methods: List[PaymentMethod] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# INVOICING MANAGER
# ============================================================

class InvoicingManager:
    """
    Gestionnaire de facturation pour le bot de couverture
    
    Gère les factures, paiements et abonnements
    """
    
    def __init__(
        self,
        config: Optional[BillingConfig] = None,
        check_interval: int = 3600,
        enable_auto_payment: bool = True
    ):
        """
        Initialise le gestionnaire de facturation
        
        Args:
            config: Configuration de facturation
            check_interval: Intervalle de vérification
            enable_auto_payment: Activer les paiements automatiques
        """
        self.config = config or BillingConfig()
        self.check_interval = check_interval
        self.enable_auto_payment = enable_auto_payment
        
        # Factures
        self.invoices: Dict[str, Invoice] = {}
        self.pending_invoices: Dict[str, Invoice] = {}
        self.overdue_invoices: Dict[str, Invoice] = {}
        self.paid_invoices: Dict[str, Invoice] = {}
        
        # Paiements
        self.transactions: Dict[str, PaymentTransaction] = {}
        self.pending_transactions: Dict[str, PaymentTransaction] = {}
        
        # Statistiques
        self.stats = {
            'total_invoices': 0,
            'pending_invoices': 0,
            'paid_invoices': 0,
            'overdue_invoices': 0,
            'total_amount': 0.0,
            'paid_amount': 0.0,
            'pending_amount': 0.0,
            'overdue_amount': 0.0,
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
        }
        
        # Verrous
        self._lock = threading.RLock()
        self._running = False
        self._check_task = None
        
        # Callbacks
        self._callbacks: Dict[str, List[Callable]] = {
            'invoice_created': [],
            'invoice_paid': [],
            'invoice_overdue': [],
            'payment_completed': [],
            'payment_failed': [],
        }
        
        # Alertes
        self.alerts: List[Dict[str, Any]] = []
        
        # Compteur de factures
        self._invoice_counter = 0
        
        logger.info("InvoicingManager initialized")
    
    # ============================================================
    # INVOICE MANAGEMENT
    # ============================================================
    
    def create_invoice(
        self,
        user_id: str,
        items: List[InvoiceItem],
        type: InvoiceType = InvoiceType.ONE_TIME,
        currency: str = "USD",
        due_days: Optional[int] = None,
        notes: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Invoice:
        """
        Crée une facture
        
        Args:
            user_id: ID de l'utilisateur
            items: Lignes de facture
            type: Type de facture
            currency: Devise
            due_days: Jours avant échéance
            notes: Notes
            metadata: Métadonnées
            
        Returns:
            Invoice: Facture créée
        """
        with self._lock:
            # Calculer les totaux
            subtotal = sum(item.total for item in items)
            tax_total = sum(item.tax_amount for item in items)
            discount_total = sum(item.discount for item in items)
            total = subtotal + tax_total - discount_total
            
            # Générer le numéro de facture
            self._invoice_counter += 1
            invoice_number = f"{self.config.invoice_prefix}{datetime.now().strftime('%Y%m')}{self._invoice_counter:04d}"
            
            # Calculer la date d'échéance
            due_days = due_days or self.config.payment_grace_period
            due_date = datetime.now() + timedelta(days=due_days)
            
            invoice = Invoice(
                id=f"inv_{uuid.uuid4().hex[:8]}",
                number=invoice_number,
                type=type,
                status=InvoiceStatus.PENDING,
                user_id=user_id,
                items=items,
                subtotal=subtotal,
                tax_total=tax_total,
                discount_total=discount_total,
                total=total,
                currency=currency,
                issued_date=datetime.now(),
                due_date=due_date,
                notes=notes,
                metadata=metadata or {}
            )
            
            self.invoices[invoice.id] = invoice
            self.pending_invoices[invoice.id] = invoice
            self.stats['total_invoices'] += 1
            self.stats['pending_invoices'] = len(self.pending_invoices)
            self.stats['pending_amount'] += total
            
            self._update_stats()
            self._trigger_event('invoice_created', invoice)
            
            logger.info(f"Invoice created: {invoice.number} for user {user_id} - ${total:.2f}")
            
            # Envoyer automatiquement
            if self.config.auto_send:
                self._send_invoice(invoice)
            
            return invoice
    
    def update_invoice_status(
        self,
        invoice_id: str,
        status: InvoiceStatus
    ) -> bool:
        """
        Met à jour le statut d'une facture
        
        Args:
            invoice_id: ID de la facture
            status: Nouveau statut
            
        Returns:
            bool: True si mis à jour
        """
        with self._lock:
            invoice = self.invoices.get(invoice_id)
            if not invoice:
                return False
            
            old_status = invoice.status
            invoice.status = status
            
            if status == InvoiceStatus.PAID:
                self.pending_invoices.pop(invoice_id, None)
                self.paid_invoices[invoice_id] = invoice
                self.stats['paid_invoices'] = len(self.paid_invoices)
                self.stats['paid_amount'] += invoice.total
                self.stats['pending_amount'] -= invoice.total
                self._trigger_event('invoice_paid', invoice)
            
            elif status == InvoiceStatus.OVERDUE:
                self.overdue_invoices[invoice_id] = invoice
                self.stats['overdue_invoices'] = len(self.overdue_invoices)
                self.stats['overdue_amount'] += invoice.total
                self._trigger_event('invoice_overdue', invoice)
            
            elif status == InvoiceStatus.CANCELLED:
                self.pending_invoices.pop(invoice_id, None)
                self.stats['pending_invoices'] = len(self.pending_invoices)
            
            self._update_stats()
            
            logger.info(f"Invoice status updated: {invoice.number} - {old_status.value} -> {status.value}")
            return True
    
    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """
        Récupère une facture
        
        Args:
            invoice_id: ID de la facture
            
        Returns:
            Optional[Invoice]: Facture
        """
        return self.invoices.get(invoice_id)
    
    def get_invoices_by_user(self, user_id: str) -> List[Invoice]:
        """
        Récupère les factures d'un utilisateur
        
        Args:
            user_id: ID de l'utilisateur
            
        Returns:
            List[Invoice]: Factures
        """
        return [i for i in self.invoices.values() if i.user_id == user_id]
    
    def get_pending_invoices(self) -> List[Invoice]:
        """
        Récupère les factures en attente
        
        Returns:
            List[Invoice]: Factures en attente
        """
        return list(self.pending_invoices.values())
    
    # ============================================================
    # PAYMENT MANAGEMENT
    # ============================================================
    
    def process_payment(
        self,
        invoice_id: str,
        amount: float,
        method: PaymentMethod,
        reference: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PaymentTransaction:
        """
        Traite un paiement
        
        Args:
            invoice_id: ID de la facture
            amount: Montant
            method: Méthode de paiement
            reference: Référence
            metadata: Métadonnées
            
        Returns:
            PaymentTransaction: Transaction de paiement
        """
        with self._lock:
            invoice = self.invoices.get(invoice_id)
            if not invoice:
                raise ValueError(f"Invoice not found: {invoice_id}")
            
            # Créer la transaction
            transaction = PaymentTransaction(
                id=f"pay_{uuid.uuid4().hex[:8]}",
                invoice_id=invoice_id,
                amount=amount,
                currency=invoice.currency,
                method=method,
                status=PaymentStatus.PENDING,
                timestamp=datetime.now(),
                reference=reference,
                metadata=metadata or {}
            )
            
            self.transactions[transaction.id] = transaction
            self.pending_transactions[transaction.id] = transaction
            self.stats['total_transactions'] += 1
            
            # Simuler le traitement du paiement
            success = self._process_payment_simulation(transaction)
            
            if success:
                transaction.status = PaymentStatus.COMPLETED
                self.pending_transactions.pop(transaction.id, None)
                self.stats['successful_transactions'] += 1
                
                # Mettre à jour la facture
                invoice.paid_date = datetime.now()
                invoice.payment_method = method
                invoice.payment_status = PaymentStatus.COMPLETED
                invoice.payment_id = transaction.id
                self.update_invoice_status(invoice_id, InvoiceStatus.PAID)
                
                self._trigger_event('payment_completed', transaction)
                self._add_alert(f"Payment completed: {invoice.number} - ${amount:.2f}", "success")
            else:
                transaction.status = PaymentStatus.FAILED
                self.pending_transactions.pop(transaction.id, None)
                self.stats['failed_transactions'] += 1
                self._trigger_event('payment_failed', transaction)
                self._add_alert(f"Payment failed: {invoice.number} - ${amount:.2f}", "error")
            
            self._update_stats()
            
            logger.info(f"Payment processed: {transaction.id} - {method.value} - {success}")
            return transaction
    
    def _process_payment_simulation(self, transaction: PaymentTransaction) -> bool:
        """
        Simule le traitement d'un paiement
        
        Args:
            transaction: Transaction de paiement
            
        Returns:
            bool: True si réussi
        """
        # Simulation de paiement (90% de succès)
        import random
        return random.random() < 0.9
    
    def get_transaction(self, transaction_id: str) -> Optional[PaymentTransaction]:
        """
        Récupère une transaction de paiement
        
        Args:
            transaction_id: ID de la transaction
            
        Returns:
            Optional[PaymentTransaction]: Transaction
        """
        return self.transactions.get(transaction_id)
    
    def get_transactions_by_invoice(self, invoice_id: str) -> List[PaymentTransaction]:
        """
        Récupère les transactions d'une facture
        
        Args:
            invoice_id: ID de la facture
            
        Returns:
            List[PaymentTransaction]: Transactions
        """
        return [t for t in self.transactions.values() if t.invoice_id == invoice_id]
    
    # ============================================================
    # SUBSCRIPTION BILLING
    # ============================================================
    
    def generate_subscription_invoice(
        self,
        user_id: str,
        plan_name: str,
        amount: float,
        period: str,
        subscription_id: str
    ) -> Invoice:
        """
        Génère une facture d'abonnement
        
        Args:
            user_id: ID de l'utilisateur
            plan_name: Nom du plan
            amount: Montant
            period: Période
            subscription_id: ID de l'abonnement
            
        Returns:
            Invoice: Facture générée
        """
        item = InvoiceItem(
            id=f"item_{uuid.uuid4().hex[:8]}",
            description=f"Subscription {plan_name} - {period}",
            quantity=1,
            unit_price=amount,
            total=amount,
            tax_rate=self.config.tax_rate,
            tax_amount=amount * self.config.tax_rate,
            metadata={'subscription_id': subscription_id, 'period': period}
        )
        
        return self.create_invoice(
            user_id=user_id,
            items=[item],
            type=InvoiceType.SUBSCRIPTION,
            metadata={'subscription_id': subscription_id}
        )
    
    # ============================================================
    # CALLBACKS
    # ============================================================
    
    def on(self, event: str, callback: Callable):
        """
        Enregistre un callback
        
        Args:
            event: Événement
            callback: Fonction de callback
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _trigger_event(self, event: str, data: Any):
        """
        Déclenche un événement
        
        Args:
            event: Événement
            data: Données
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    # ============================================================
    # NOTIFICATIONS
    # ============================================================
    
    def _send_invoice(self, invoice: Invoice):
        """
        Envoie une facture
        
        Args:
            invoice: Facture à envoyer
        """
        # Simuler l'envoi
        logger.info(f"Invoice sent: {invoice.number} to user {invoice.user_id}")
    
    def _add_alert(self, message: str, severity: str = "info"):
        """
        Ajoute une alerte
        
        Args:
            message: Message
            severity: Sévérité
        """
        alert = {
            'timestamp': time.time(),
            'severity': severity,
            'message': message,
        }
        self.alerts.append(alert)
        
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        with self._lock:
            self.stats['pending_invoices'] = len(self.pending_invoices)
            self.stats['paid_invoices'] = len(self.paid_invoices)
            self.stats['overdue_invoices'] = len(self.overdue_invoices)
            self.stats['pending_amount'] = sum(i.total for i in self.pending_invoices.values())
            self.stats['paid_amount'] = sum(i.total for i in self.paid_invoices.values())
            self.stats['overdue_amount'] = sum(i.total for i in self.overdue_invoices.values())
    
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
            'invoices': [
                {
                    'id': i.id,
                    'number': i.number,
                    'type': i.type.value,
                    'status': i.status.value,
                    'user_id': i.user_id,
                    'total': i.total,
                    'currency': i.currency,
                    'issued_date': i.issued_date.isoformat(),
                    'due_date': i.due_date.isoformat() if i.due_date else None,
                }
                for i in self.invoices.values()
            ],
            'recent_transactions': [
                {
                    'id': t.id,
                    'invoice_id': t.invoice_id,
                    'amount': t.amount,
                    'currency': t.currency,
                    'method': t.method.value,
                    'status': t.status.value,
                    'timestamp': t.timestamp.isoformat(),
                }
                for t in list(self.transactions.values())[-10:]
            ],
            'alerts': self.alerts[-10:],
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
        
        logger.info("InvoicingManager monitoring started")
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            return
        
        self._running = False
        if self._check_task:
            self._check_task.join(timeout=2)
        
        logger.info("InvoicingManager monitoring stopped")
    
    def _check_loop(self):
        """Boucle de vérification"""
        while self._running:
            try:
                self._check_overdue()
                self._check_pending_payments()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Check error: {e}")
                time.sleep(self.check_interval)
    
    def _check_overdue(self):
        """Vérifie les factures en retard"""
        now = datetime.now()
        for invoice in self.pending_invoices.values():
            if invoice.due_date and now > invoice.due_date:
                self.update_invoice_status(invoice.id, InvoiceStatus.OVERDUE)
                self._add_alert(
                    f"Invoice overdue: {invoice.number} - ${invoice.total:.2f}",
                    "warning"
                )
    
    def _check_pending_payments(self):
        """Vérifie les paiements en attente"""
        # Simuler la vérification des paiements
        for transaction in self.pending_transactions.values():
            if (datetime.now() - transaction.timestamp).seconds > 300:  # 5 minutes
                # Simuler un échec après timeout
                transaction.status = PaymentStatus.FAILED
                self.pending_transactions.pop(transaction.id, None)
                self.stats['failed_transactions'] += 1
                self._add_alert(
                    f"Payment timeout: {transaction.id} - ${transaction.amount:.2f}",
                    "error"
                )

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_invoicing_manager: Optional[InvoicingManager] = None

def get_invoicing_manager(
    config: Optional[BillingConfig] = None
) -> InvoicingManager:
    """
    Récupère le gestionnaire de facturation (singleton)
    
    Args:
        config: Configuration
        
    Returns:
        InvoicingManager: Gestionnaire de facturation
    """
    global _invoicing_manager
    if _invoicing_manager is None:
        _invoicing_manager = InvoicingManager(config)
    return _invoicing_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'InvoiceStatus',
    'InvoiceType',
    'PaymentMethod',
    'PaymentStatus',
    'InvoiceItem',
    'Invoice',
    'PaymentTransaction',
    'BillingConfig',
    'InvoicingManager',
    'get_invoicing_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Invoicing manager module initialized")
