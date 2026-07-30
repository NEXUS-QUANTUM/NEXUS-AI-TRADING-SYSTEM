# trading/bots/hedge_bot/hedge_bot_billing.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Billing Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Billing Module

This module provides comprehensive billing and subscription management
capabilities for the NEXUS Hedge Bot system. It handles subscriptions,
invoicing, payments, and billing analytics.

The module covers:
- Subscription Management
- Plan Management
- Invoicing
- Payment Processing
- Billing Analytics
- Revenue Tracking
- Usage Billing
- Discount Management
- Tax Calculation
- Invoice Generation
- Payment Reconciliation
- Billing Reports
"""

import os
import sys
import json
import time
import math
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
from decimal import Decimal, getcontext

logger = logging.getLogger(__name__)


# ============================================================
# BILLING ENUMS
# ============================================================

class BillingStatus(Enum):
    """Billing status"""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"
    TRIAL = "trial"
    SUSPENDED = "suspended"


class InvoiceStatus(Enum):
    """Invoice status"""
    DRAFT = "draft"
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(Enum):
    """Payment methods"""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"
    PAYPAL = "paypal"
    STRIPE = "stripe"


class PlanType(Enum):
    """Plan types"""
    FREE = "free"
    BASIC = "basic"
    STANDARD = "standard"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


# ============================================================
# BILLING DATACLASSES
# ============================================================

@dataclass
class SubscriptionPlan:
    """Subscription plan"""
    id: str
    name: str
    type: PlanType
    price_monthly: float
    price_annual: float
    features: List[str]
    limits: Dict[str, Any]
    trial_days: int = 0
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "price_monthly": self.price_monthly,
            "price_annual": self.price_annual,
            "features": self.features,
            "limits": self.limits,
            "trial_days": self.trial_days,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Subscription:
    """User subscription"""
    id: str
    user_id: str
    plan_id: str
    status: BillingStatus
    start_date: datetime
    end_date: datetime
    auto_renew: bool = True
    trial_end: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    payment_method: Optional[PaymentMethod] = None
    payment_token: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_id": self.plan_id,
            "status": self.status.value,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "auto_renew": self.auto_renew,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Invoice:
    """Invoice"""
    id: str
    subscription_id: str
    user_id: str
    invoice_number: str
    amount: float
    tax: float
    total: float
    currency: str
    status: InvoiceStatus
    due_date: datetime
    paid_date: Optional[datetime] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    payment_method: Optional[PaymentMethod] = None
    payment_transaction_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "invoice_number": self.invoice_number,
            "amount": self.amount,
            "tax": self.tax,
            "total": self.total,
            "currency": self.currency,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "items": self.items,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "payment_transaction_id": self.payment_transaction_id,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PaymentTransaction:
    """Payment transaction"""
    id: str
    user_id: str
    subscription_id: str
    invoice_id: str
    amount: float
    currency: str
    payment_method: PaymentMethod
    transaction_id: str
    status: str
    gateway_response: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "subscription_id": self.subscription_id,
            "invoice_id": self.invoice_id,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method.value,
            "transaction_id": self.transaction_id,
            "status": self.status,
            "gateway_response": self.gateway_response,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BillingAnalytics:
    """Billing analytics"""
    total_revenue: float
    monthly_recurring_revenue: float
    annual_recurring_revenue: float
    average_revenue_per_user: float
    customer_churn_rate: float
    revenue_churn_rate: float
    active_subscriptions: int
    new_subscriptions: int
    cancelled_subscriptions: int
    period_start: datetime
    period_end: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_revenue": self.total_revenue,
            "monthly_recurring_revenue": self.monthly_recurring_revenue,
            "annual_recurring_revenue": self.annual_recurring_revenue,
            "average_revenue_per_user": self.average_revenue_per_user,
            "customer_churn_rate": self.customer_churn_rate,
            "revenue_churn_rate": self.revenue_churn_rate,
            "active_subscriptions": self.active_subscriptions,
            "new_subscriptions": self.new_subscriptions,
            "cancelled_subscriptions": self.cancelled_subscriptions,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


# ============================================================
# BILLING ENGINE
# ============================================================

class BillingEngine:
    """
    Comprehensive billing engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the billing engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.currency = self.config.get("currency", "USD")
        self.tax_rate = self.config.get("tax_rate", 0.20)
        self.default_plan = self.config.get("default_plan", "free")
        
        # State
        self.plans: Dict[str, SubscriptionPlan] = {}
        self.subscriptions: Dict[str, Subscription] = {}
        self.invoices: Dict[str, Invoice] = {}
        self.transactions: Dict[str, PaymentTransaction] = {}
        
        # Initialize default plans
        self._init_default_plans()
        
        logger.info("Billing engine initialized")
    
    # ============================================================
    # PLAN MANAGEMENT
    # ============================================================
    
    def _init_default_plans(self) -> None:
        """Initialize default subscription plans"""
        plans = [
            SubscriptionPlan(
                id="plan_free",
                name="Free",
                type=PlanType.FREE,
                price_monthly=0.0,
                price_annual=0.0,
                features=["Basic trading", "Paper trading", "Basic charts"],
                limits={"bots": 1, "trades_per_day": 10, "positions": 5},
                trial_days=0,
            ),
            SubscriptionPlan(
                id="plan_basic",
                name="Basic",
                type=PlanType.BASIC,
                price_monthly=29.99,
                price_annual=299.99,
                features=["Basic trading", "Live trading", "Advanced charts", "Email support"],
                limits={"bots": 3, "trades_per_day": 50, "positions": 20},
                trial_days=7,
            ),
            SubscriptionPlan(
                id="plan_standard",
                name="Standard",
                type=PlanType.STANDARD,
                price_monthly=79.99,
                price_annual=799.99,
                features=["Advanced trading", "Live trading", "Premium charts", "Priority support",
                         "AI signals", "Risk management", "Portfolio analytics"],
                limits={"bots": 10, "trades_per_day": 200, "positions": 50},
                trial_days=7,
            ),
            SubscriptionPlan(
                id="plan_professional",
                name="Professional",
                type=PlanType.PROFESSIONAL,
                price_monthly=199.99,
                price_annual=1999.99,
                features=["Professional trading", "Live trading", "Premium charts", "24/7 support",
                         "AI signals", "Advanced risk management", "Portfolio optimization",
                         "API access", "Custom strategies", "Webhook integration"],
                limits={"bots": 25, "trades_per_day": 1000, "positions": 100},
                trial_days=14,
            ),
            SubscriptionPlan(
                id="plan_enterprise",
                name="Enterprise",
                type=PlanType.ENTERPRISE,
                price_monthly=499.99,
                price_annual=4999.99,
                features=["Enterprise trading", "Live trading", "Premium charts", "Dedicated support",
                         "AI signals", "Advanced risk management", "Portfolio optimization",
                         "API access", "Custom strategies", "Webhook integration",
                         "White label", "Dedicated infrastructure", "SLA guarantee"],
                limits={"bots": 100, "trades_per_day": 10000, "positions": 500},
                trial_days=30,
            ),
        ]
        
        for plan in plans:
            self.plans[plan.id] = plan
        
        logger.info(f"Initialized {len(plans)} subscription plans")
    
    def create_plan(
        self,
        name: str,
        plan_type: PlanType,
        price_monthly: float,
        price_annual: float,
        features: List[str],
        limits: Dict[str, Any],
        trial_days: int = 0
    ) -> SubscriptionPlan:
        """
        Create a new subscription plan
        
        Args:
            name: Plan name
            plan_type: Plan type
            price_monthly: Monthly price
            price_annual: Annual price
            features: List of features
            limits: Plan limits
            trial_days: Trial period in days
            
        Returns:
            SubscriptionPlan
        """
        plan = SubscriptionPlan(
            id=f"plan_{int(time.time())}_{len(self.plans)}",
            name=name,
            type=plan_type,
            price_monthly=price_monthly,
            price_annual=price_annual,
            features=features,
            limits=limits,
            trial_days=trial_days,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.plans[plan.id] = plan
        logger.info(f"Created plan: {name}")
        return plan
    
    def update_plan(self, plan_id: str, updates: Dict[str, Any]) -> Optional[SubscriptionPlan]:
        """
        Update a subscription plan
        
        Args:
            plan_id: Plan ID
            updates: Updates to apply
            
        Returns:
            Updated plan or None
        """
        plan = self.plans.get(plan_id)
        if not plan:
            return None
        
        for key, value in updates.items():
            if hasattr(plan, key):
                setattr(plan, key, value)
        
        plan.updated_at = datetime.now()
        logger.info(f"Updated plan: {plan.name}")
        return plan
    
    def delete_plan(self, plan_id: str) -> bool:
        """
        Delete a subscription plan
        
        Args:
            plan_id: Plan ID
            
        Returns:
            True if deleted
        """
        if plan_id in self.plans:
            del self.plans[plan_id]
            logger.info(f"Deleted plan: {plan_id}")
            return True
        return False
    
    def get_plan(self, plan_id: str) -> Optional[SubscriptionPlan]:
        """
        Get a subscription plan
        
        Args:
            plan_id: Plan ID
            
        Returns:
            SubscriptionPlan or None
        """
        return self.plans.get(plan_id)
    
    def get_plans(self) -> List[SubscriptionPlan]:
        """
        Get all subscription plans
        
        Returns:
            List of subscription plans
        """
        return list(self.plans.values())
    
    # ============================================================
    # SUBSCRIPTION MANAGEMENT
    # ============================================================
    
    def create_subscription(
        self,
        user_id: str,
        plan_id: str,
        auto_renew: bool = True,
        payment_method: Optional[PaymentMethod] = None,
        payment_token: Optional[str] = None
    ) -> Subscription:
        """
        Create a new subscription
        
        Args:
            user_id: User ID
            plan_id: Plan ID
            auto_renew: Auto-renew
            payment_method: Payment method
            payment_token: Payment token
            
        Returns:
            Subscription
        """
        plan = self.plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")
        
        # Check existing subscription
        existing = self.get_user_subscription(user_id)
        if existing and existing.status in [BillingStatus.ACTIVE, BillingStatus.TRIAL]:
            raise ValueError(f"User already has an active subscription")
        
        # Calculate dates
        start_date = datetime.now()
        end_date = start_date + timedelta(days=30)  # Monthly by default
        
        trial_end = None
        if plan.trial_days > 0:
            trial_end = start_date + timedelta(days=plan.trial_days)
            status = BillingStatus.TRIAL
        else:
            status = BillingStatus.ACTIVE
        
        subscription = Subscription(
            id=f"sub_{int(time.time())}_{len(self.subscriptions)}",
            user_id=user_id,
            plan_id=plan_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            auto_renew=auto_renew,
            trial_end=trial_end,
            payment_method=payment_method,
            payment_token=payment_token,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.subscriptions[subscription.id] = subscription
        logger.info(f"Created subscription for user {user_id}")
        
        # Generate first invoice
        self._generate_invoice(subscription)
        
        return subscription
    
    def update_subscription(
        self,
        subscription_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Subscription]:
        """
        Update a subscription
        
        Args:
            subscription_id: Subscription ID
            updates: Updates to apply
            
        Returns:
            Updated subscription or None
        """
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return None
        
        for key, value in updates.items():
            if hasattr(subscription, key):
                setattr(subscription, key, value)
        
        subscription.updated_at = datetime.now()
        logger.info(f"Updated subscription: {subscription_id}")
        return subscription
    
    def cancel_subscription(self, subscription_id: str) -> bool:
        """
        Cancel a subscription
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if cancelled
        """
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return False
        
        subscription.status = BillingStatus.CANCELLED
        subscription.cancelled_at = datetime.now()
        subscription.updated_at = datetime.now()
        
        logger.info(f"Cancelled subscription: {subscription_id}")
        return True
    
    def renew_subscription(self, subscription_id: str) -> bool:
        """
        Renew a subscription
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            True if renewed
        """
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return False
        
        if subscription.status not in [BillingStatus.ACTIVE, BillingStatus.TRIAL]:
            return False
        
        # Extend end date
        subscription.end_date = subscription.end_date + timedelta(days=30)
        subscription.updated_at = datetime.now()
        
        # Generate new invoice
        self._generate_invoice(subscription)
        
        logger.info(f"Renewed subscription: {subscription_id}")
        return True
    
    def get_subscription(self, subscription_id: str) -> Optional[Subscription]:
        """
        Get a subscription
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            Subscription or None
        """
        return self.subscriptions.get(subscription_id)
    
    def get_user_subscription(self, user_id: str) -> Optional[Subscription]:
        """
        Get a user's subscription
        
        Args:
            user_id: User ID
            
        Returns:
            Subscription or None
        """
        for subscription in self.subscriptions.values():
            if subscription.user_id == user_id:
                return subscription
        return None
    
    def get_subscriptions(
        self,
        status: Optional[BillingStatus] = None
    ) -> List[Subscription]:
        """
        Get subscriptions
        
        Args:
            status: Filter by status
            
        Returns:
            List of subscriptions
        """
        subscriptions = list(self.subscriptions.values())
        if status:
            subscriptions = [s for s in subscriptions if s.status == status]
        return subscriptions
    
    # ============================================================
    # INVOICE MANAGEMENT
    # ============================================================
    
    def _generate_invoice(self, subscription: Subscription) -> Invoice:
        """
        Generate an invoice
        
        Args:
            subscription: Subscription
            
        Returns:
            Invoice
        """
        plan = self.plans.get(subscription.plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {subscription.plan_id}")
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m')}-{len(self.invoices) + 1:04d}"
        
        # Calculate amount
        amount = plan.price_monthly
        tax = amount * self.tax_rate
        total = amount + tax
        
        invoice = Invoice(
            id=f"inv_{int(time.time())}_{len(self.invoices)}",
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            invoice_number=invoice_number,
            amount=amount,
            tax=tax,
            total=total,
            currency=self.currency,
            status=InvoiceStatus.PENDING,
            due_date=datetime.now() + timedelta(days=14),
            items=[
                {
                    "description": f"Subscription: {plan.name} (Monthly)",
                    "quantity": 1,
                    "unit_price": amount,
                    "total": amount,
                },
                {
                    "description": "Tax",
                    "quantity": 1,
                    "unit_price": tax,
                    "total": tax,
                },
            ],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.invoices[invoice.id] = invoice
        logger.info(f"Generated invoice: {invoice_number}")
        return invoice
    
    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """
        Get an invoice
        
        Args:
            invoice_id: Invoice ID
            
        Returns:
            Invoice or None
        """
        return self.invoices.get(invoice_id)
    
    def get_invoices(
        self,
        user_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None
    ) -> List[Invoice]:
        """
        Get invoices
        
        Args:
            user_id: Filter by user
            status: Filter by status
            
        Returns:
            List of invoices
        """
        invoices = list(self.invoices.values())
        if user_id:
            invoices = [i for i in invoices if i.user_id == user_id]
        if status:
            invoices = [i for i in invoices if i.status == status]
        return invoices
    
    def mark_invoice_paid(
        self,
        invoice_id: str,
        payment_method: PaymentMethod,
        transaction_id: str
    ) -> bool:
        """
        Mark an invoice as paid
        
        Args:
            invoice_id: Invoice ID
            payment_method: Payment method
            transaction_id: Transaction ID
            
        Returns:
            True if marked paid
        """
        invoice = self.invoices.get(invoice_id)
        if not invoice:
            return False
        
        invoice.status = InvoiceStatus.PAID
        invoice.paid_date = datetime.now()
        invoice.payment_method = payment_method
        invoice.payment_transaction_id = transaction_id
        invoice.updated_at = datetime.now()
        
        # Record transaction
        transaction = PaymentTransaction(
            id=f"txn_{int(time.time())}_{len(self.transactions)}",
            user_id=invoice.user_id,
            subscription_id=invoice.subscription_id,
            invoice_id=invoice.id,
            amount=invoice.total,
            currency=invoice.currency,
            payment_method=payment_method,
            transaction_id=transaction_id,
            status="completed",
            created_at=datetime.now(),
        )
        self.transactions[transaction.id] = transaction
        
        logger.info(f"Invoice paid: {invoice.invoice_number}")
        return True
    
    # ============================================================
    # PAYMENT PROCESSING
    # ============================================================
    
    def process_payment(
        self,
        invoice_id: str,
        payment_method: PaymentMethod,
        payment_token: str
    ) -> PaymentTransaction:
        """
        Process a payment
        
        Args:
            invoice_id: Invoice ID
            payment_method: Payment method
            payment_token: Payment token
            
        Returns:
            PaymentTransaction
        """
        invoice = self.invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice not found: {invoice_id}")
        
        if invoice.status == InvoiceStatus.PAID:
            raise ValueError(f"Invoice already paid: {invoice_id}")
        
        # Process payment (mock)
        transaction_id = f"txn_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Mark invoice paid
        self.mark_invoice_paid(invoice_id, payment_method, transaction_id)
        
        # Get transaction
        transaction = self.transactions.get(f"txn_{int(time.time())}_{len(self.transactions)}")
        
        logger.info(f"Payment processed for invoice: {invoice.invoice_number}")
        return transaction
    
    # ============================================================
    # BILLING ANALYTICS
    # ============================================================
    
    def get_analytics(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> BillingAnalytics:
        """
        Get billing analytics
        
        Args:
            period_start: Period start
            period_end: Period end
            
        Returns:
            BillingAnalytics
        """
        if period_start is None:
            period_start = datetime.now() - timedelta(days=30)
        if period_end is None:
            period_end = datetime.now()
        
        # Get invoices in period
        period_invoices = [
            i for i in self.invoices.values()
            if period_start <= i.created_at <= period_end
        ]
        
        # Calculate revenue
        total_revenue = sum(i.total for i in period_invoices if i.status == InvoiceStatus.PAID)
        
        # Calculate MRR
        active_subscriptions = [
            s for s in self.subscriptions.values()
            if s.status in [BillingStatus.ACTIVE, BillingStatus.TRIAL]
        ]
        mrr = sum(
            self.plans.get(s.plan_id, self.plans.get("plan_free", SubscriptionPlan(
                id="plan_free", name="Free", type=PlanType.FREE,
                price_monthly=0.0, price_annual=0.0, features=[], limits={}
            ))).price_monthly
            for s in active_subscriptions
        )
        
        # Calculate ARR
        arr = mrr * 12
        
        # Calculate ARPU
        total_users = len(set(s.user_id for s in active_subscriptions))
        arpu = mrr / total_users if total_users > 0 else 0
        
        # Calculate churn
        cancelled = [
            s for s in self.subscriptions.values()
            if s.status == BillingStatus.CANCELLED
            and period_start <= s.cancelled_at <= period_end
        ]
        churn_rate = len(cancelled) / len(active_subscriptions) if active_subscriptions else 0
        
        return BillingAnalytics(
            total_revenue=total_revenue,
            monthly_recurring_revenue=mrr,
            annual_recurring_revenue=arr,
            average_revenue_per_user=arpu,
            customer_churn_rate=churn_rate,
            revenue_churn_rate=churn_rate,
            active_subscriptions=len(active_subscriptions),
            new_subscriptions=len([s for s in period_invoices if s.status == InvoiceStatus.PAID]),
            cancelled_subscriptions=len(cancelled),
            period_start=period_start,
            period_end=period_end,
        )
    
    # ============================================================
    # EXPORT
    # ============================================================
    
    def export_data(self) -> Dict[str, Any]:
        """
        Export billing data
        
        Returns:
            Billing data
        """
        return {
            "plans": [p.to_dict() for p in self.plans.values()],
            "subscriptions": [s.to_dict() for s in self.subscriptions.values()],
            "invoices": [i.to_dict() for i in self.invoices.values()],
            "transactions": [t.to_dict() for t in self.transactions.values()],
            "analytics": self.get_analytics().to_dict(),
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get billing statistics
        
        Returns:
            Statistics dictionary
        """
        active = len([s for s in self.subscriptions.values() if s.status == BillingStatus.ACTIVE])
        trial = len([s for s in self.subscriptions.values() if s.status == BillingStatus.TRIAL])
        cancelled = len([s for s in self.subscriptions.values() if s.status == BillingStatus.CANCELLED])
        
        total_revenue = sum(i.total for i in self.invoices.values() if i.status == InvoiceStatus.PAID)
        
        return {
            "total_subscriptions": len(self.subscriptions),
            "active_subscriptions": active,
            "trial_subscriptions": trial,
            "cancelled_subscriptions": cancelled,
            "total_invoices": len(self.invoices),
            "paid_invoices": len([i for i in self.invoices.values() if i.status == InvoiceStatus.PAID]),
            "total_revenue": total_revenue,
            "total_plans": len(self.plans),
            "total_transactions": len(self.transactions),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BillingStatus",
    "InvoiceStatus",
    "PaymentMethod",
    "PlanType",
    
    # Dataclasses
    "SubscriptionPlan",
    "Subscription",
    "Invoice",
    "PaymentTransaction",
    "BillingAnalytics",
    
    # Classes
    "BillingEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
