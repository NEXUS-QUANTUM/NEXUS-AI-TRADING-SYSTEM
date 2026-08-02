# trading/bots/hedge_bot/hedge_bot_invoicing.py

import asyncio
import json
import logging
import time
import uuid
import hashlib
import hmac
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN
from collections import defaultdict
import pandas as pd
import numpy as np

try:
    import qrcode
    from qrcode.image.pil import PilImage
    import qrcode.constants
except ImportError:
    qrcode = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.lib.units import inch, mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
    from reportlab.pdfgen import canvas
    from reportlab.lib import utils
except ImportError:
    reportlab = None

try:
    import barcode
    from barcode.writer import ImageWriter
    from barcode import Code128, EAN13, EAN8, UPCA, QR
except ImportError:
    barcode = None

logger = logging.getLogger(__name__)


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    SENT = "sent"
    VIEWED = "viewed"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    DISPUTED = "disputed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    VOID = "void"
    COLLECTION = "collection"
    WRITTEN_OFF = "written_off"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    STRIPE = "stripe"
    CRYPTO = "crypto"
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    SOLANA = "solana"
    USDC = "usdc"
    USDT = "usdt"
    WIRE_TRANSFER = "wire_transfer"
    ACH = "ach"
    CHECK = "check"
    CASH = "cash"
    INTERNAL = "internal"
    OTHER = "other"


class InvoiceType(str, Enum):
    SUBSCRIPTION = "subscription"
    SERVICE = "service"
    PRODUCT = "product"
    TRADING_FEE = "trading_fee"
    COMMISSION = "commission"
    ROYALTY = "royalty"
    LICENSE = "license"
    MAINTENANCE = "maintenance"
    SUPPORT = "support"
    CONSULTING = "consulting"
    TRAINING = "training"
    CUSTOM = "custom"
    REFUND = "refund"
    CREDIT_NOTE = "credit_note"
    DEBIT_NOTE = "debit_note"
    PROFORMA = "proforma"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNY = "CNY"
    HKD = "HKD"
    SGD = "SGD"
    BTC = "BTC"
    ETH = "ETH"
    USDC = "USDC"
    USDT = "USDT"


class TaxType(str, Enum):
    VAT = "vat"
    GST = "gst"
    HST = "hst"
    PST = "pst"
    QST = "qst"
    SALES_TAX = "sales_tax"
    INCOME_TAX = "income_tax"
    CORPORATE_TAX = "corporate_tax"
    CAPITAL_GAINS = "capital_gains"
    WITHHOLDING = "withholding"
    EXEMPT = "exempt"
    ZERO_RATED = "zero_rated"


class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    BULK = "bulk"
    VOLUME = "volume"
    EARLY_PAYMENT = "early_payment"
    SEASONAL = "seasonal"
    PROMOTIONAL = "promotional"
    LOYALTY = "loyalty"
    REFERRAL = "referral"
    CUSTOM = "custom"


@dataclass
class InvoiceLineItem:
    id: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal('0')
    tax_rate: Decimal = Decimal('0')
    tax_amount: Decimal = Decimal('0')
    total: Decimal = Decimal('0')
    metadata: Dict[str, Any] = field(default_factory=dict)
    product_id: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class InvoicePayment:
    id: str
    amount: Decimal
    method: PaymentMethod
    status: str
    transaction_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    gateway_response: Optional[Dict[str, Any]] = None
    confirmation_blocks: Optional[int] = None
    network_fee: Optional[Decimal] = None


@dataclass
class InvoiceTax:
    id: str
    type: TaxType
    rate: Decimal
    amount: Decimal
    jurisdiction: Optional[str] = None
    registration_number: Optional[str] = None
    exempt_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvoiceDiscount:
    id: str
    type: DiscountType
    value: Decimal
    amount: Decimal
    code: Optional[str] = None
    valid_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Invoice:
    id: str
    number: str
    type: InvoiceType
    status: InvoiceStatus
    currency: Currency
    issuer_id: str
    issuer_name: str
    issuer_address: str
    issuer_tax_id: Optional[str] = None
    issuer_registration: Optional[str] = None
    issuer_vat_number: Optional[str] = None
    client_id: str
    client_name: str
    client_address: str
    client_email: str
    client_tax_id: Optional[str] = None
    client_vat_number: Optional[str] = None
    issue_date: datetime = field(default_factory=datetime.now)
    due_date: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=30))
    paid_date: Optional[datetime] = None
    items: List[InvoiceLineItem] = field(default_factory=list)
    taxes: List[InvoiceTax] = field(default_factory=list)
    discounts: List[InvoiceDiscount] = field(default_factory=list)
    payments: List[InvoicePayment] = field(default_factory=list)
    subtotal: Decimal = Decimal('0')
    total_discount: Decimal = Decimal('0')
    total_tax: Decimal = Decimal('0')
    total: Decimal = Decimal('0')
    amount_paid: Decimal = Decimal('0')
    amount_due: Decimal = Decimal('0')
    balance: Decimal = Decimal('0')
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    po_number: Optional[str] = None
    project_code: Optional[str] = None
    reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    locked: bool = False


@dataclass
class InvoiceTemplate:
    id: str
    name: str
    description: Optional[str] = None
    header: Optional[str] = None
    footer: Optional[str] = None
    styles: Dict[str, Any] = field(default_factory=dict)
    layout: Dict[str, Any] = field(default_factory=dict)
    fields: List[str] = field(default_factory=list)
    logo: Optional[bytes] = None
    watermark: Optional[bytes] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class InvoiceRecurrence:
    id: str
    invoice_id: str
    frequency: str
    interval: int
    next_date: datetime
    end_date: Optional[datetime] = None
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class InvoiceReport:
    id: str
    name: str
    start_date: datetime
    end_date: datetime
    total_invoices: int
    total_amount: Decimal
    total_paid: Decimal
    total_due: Decimal
    total_overdue: Decimal
    total_tax: Decimal
    total_discount: Decimal
    average_invoice: Decimal
    median_invoice: Decimal
    min_invoice: Decimal
    max_invoice: Decimal
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    by_payment_method: Dict[str, int]
    payment_collection_rate: Decimal
    average_payment_days: int
    dso: Decimal
    overdue_rate: Decimal
    write_off_rate: Decimal
    created_at: datetime = field(default_factory=datetime.now)


class InvoiceGenerator:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._invoices: Dict[str, Invoice] = {}
        self._templates: Dict[str, InvoiceTemplate] = {}
        self._recurrences: Dict[str, InvoiceRecurrence] = {}
        self._reports: Dict[str, InvoiceReport] = {}
        self._counters: Dict[str, int] = defaultdict(int)
        self._payment_processors: Dict[PaymentMethod, Callable] = {}
        self._observers: List[Callable] = []
        self._last_invoice_number = 0
        
        self._initialize_defaults()
        self._initialize_templates()

    def _initialize_defaults(self) -> None:
        self.config.setdefault("currency", Currency.USD.value)
        self.config.setdefault("issuer_name", "NEXUS QUANTUM LTD")
        self.config.setdefault("issuer_address", "Suite 1001, 10th Floor, One Commercial Centre, 54 Jermyn Street, London SW1Y 6LX, United Kingdom")
        self.config.setdefault("issuer_tax_id", "GB 123 4567 89")
        self.config.setdefault("issuer_registration", "14567890")
        self.config.setdefault("issuer_vat_number", "GB 123 4567 89")
        self.config.setdefault("invoice_prefix", "NEXUS-INV-")
        self.config.setdefault("payment_terms", "Payment due within 30 days")
        self.config.setdefault("terms_and_conditions", "Please refer to our terms and conditions for payment details.")
        self.config.setdefault("tax_rate", "0.00")
        self.config.setdefault("tax_type", TaxType.VAT.value)
        self.config.setdefault("default_discount", "0.00")
        self.config.setdefault("default_payment_method", PaymentMethod.BANK_TRANSFER.value)

    def _initialize_templates(self) -> None:
        default_template = InvoiceTemplate(
            id="default",
            name="Default Invoice Template",
            description="Standard invoice template for all invoices",
            fields=["id", "number", "type", "status", "currency", "issuer_name", "client_name", "client_email"],
            layout={
                "header": {"font": "Helvetica-Bold", "size": 18, "color": "#1a1a2e"},
                "body": {"font": "Helvetica", "size": 11, "color": "#333333"},
                "footer": {"font": "Helvetica-Oblique", "size": 9, "color": "#666666"},
                "colors": {"primary": "#1a1a2e", "secondary": "#16213e", "accent": "#0f3460", "highlight": "#e94560"}
            },
            styles={
                "title": {"fontSize": 24, "fontWeight": "bold", "textAlign": "center"},
                "section": {"fontSize": 14, "fontWeight": "bold", "marginTop": 16, "marginBottom": 8},
                "label": {"fontSize": 11, "fontWeight": "bold", "color": "#666666"},
                "value": {"fontSize": 11, "color": "#333333"},
                "total": {"fontSize": 16, "fontWeight": "bold", "color": "#1a1a2e"},
                "table": {"fontSize": 10, "headerColor": "#1a1a2e", "headerTextColor": "#ffffff"}
            }
        )
        self._templates[default_template.id] = default_template

    async def create_invoice(
        self,
        client_id: str,
        client_name: str,
        client_address: str,
        client_email: str,
        items: List[Dict[str, Any]],
        invoice_type: InvoiceType = InvoiceType.SERVICE,
        currency: Currency = Currency.USD,
        due_days: int = 30,
        client_tax_id: Optional[str] = None,
        client_vat_number: Optional[str] = None,
        payment_terms: Optional[str] = None,
        notes: Optional[str] = None,
        po_number: Optional[str] = None,
        project_code: Optional[str] = None,
        reference: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Invoice:
        async with self._lock:
            invoice_id = str(uuid.uuid4())
            invoice_number = self._generate_invoice_number()
            issue_date = datetime.now()
            due_date = issue_date + timedelta(days=due_days)
            
            line_items = []
            subtotal = Decimal('0')
            
            for item_data in items:
                item = InvoiceLineItem(
                    id=str(uuid.uuid4()),
                    description=item_data.get("description", ""),
                    quantity=Decimal(str(item_data.get("quantity", 1))),
                    unit_price=Decimal(str(item_data.get("unit_price", 0))),
                    discount=Decimal(str(item_data.get("discount", 0))),
                    tax_rate=Decimal(str(item_data.get("tax_rate", 0))),
                    product_id=item_data.get("product_id"),
                    sku=item_data.get("sku"),
                    category=item_data.get("category"),
                    start_date=item_data.get("start_date"),
                    end_date=item_data.get("end_date"),
                    metadata=item_data.get("metadata", {})
                )
                
                item_total = item.quantity * item.unit_price
                if item.discount > 0:
                    item_total = item_total * (1 - item.discount / 100)
                
                item.tax_amount = item_total * (item.tax_rate / 100)
                item.total = item_total + item.tax_amount
                
                subtotal += item_total
                line_items.append(item)
            
            taxes = []
            discount_amount = Decimal('0')
            
            tax_rate = Decimal(str(self.config.get("tax_rate", 0)))
            if tax_rate > 0:
                tax = InvoiceTax(
                    id=str(uuid.uuid4()),
                    type=TaxType(self.config.get("tax_type", TaxType.VAT.value)),
                    rate=tax_rate,
                    amount=subtotal * (tax_rate / 100),
                    jurisdiction=metadata.get("tax_jurisdiction") if metadata else None,
                    registration_number=self.config.get("issuer_vat_number")
                )
                taxes.append(tax)
            
            discounts = []
            default_discount = Decimal(str(self.config.get("default_discount", 0)))
            if default_discount > 0:
                discount = InvoiceDiscount(
                    id=str(uuid.uuid4()),
                    type=DiscountType.CUSTOM,
                    value=default_discount,
                    amount=subtotal * (default_discount / 100),
                    code=metadata.get("discount_code") if metadata else None,
                    valid_until=metadata.get("discount_valid_until") if metadata else None
                )
                discounts.append(discount)
                discount_amount = discount.amount
            
            total_tax = sum(t.amount for t in taxes)
            total = subtotal - discount_amount + total_tax
            
            invoice = Invoice(
                id=invoice_id,
                number=invoice_number,
                type=invoice_type,
                status=InvoiceStatus.DRAFT,
                currency=currency,
                issuer_id=self.config.get("issuer_id", "nexus_quantum_ltd"),
                issuer_name=self.config.get("issuer_name", "NEXUS QUANTUM LTD"),
                issuer_address=self.config.get("issuer_address", ""),
                issuer_tax_id=self.config.get("issuer_tax_id"),
                issuer_registration=self.config.get("issuer_registration"),
                issuer_vat_number=self.config.get("issuer_vat_number"),
                client_id=client_id,
                client_name=client_name,
                client_address=client_address,
                client_email=client_email,
                client_tax_id=client_tax_id,
                client_vat_number=client_vat_number,
                issue_date=issue_date,
                due_date=due_date,
                items=line_items,
                taxes=taxes,
                discounts=discounts,
                subtotal=subtotal,
                total_discount=discount_amount,
                total_tax=total_tax,
                total=total,
                amount_paid=Decimal('0'),
                amount_due=total,
                balance=total,
                payment_terms=payment_terms or self.config.get("payment_terms"),
                notes=notes,
                terms_and_conditions=self.config.get("terms_and_conditions"),
                po_number=po_number,
                project_code=project_code,
                reference=reference,
                metadata=metadata or {},
                version=1,
                locked=False
            )
            
            self._invoices[invoice_id] = invoice
            await self._notify_observers("invoice_created", invoice)
            
            return invoice

    async def update_invoice(
        self,
        invoice_id: str,
        status: Optional[InvoiceStatus] = None,
        notes: Optional[str] = None,
        payment_terms: Optional[str] = None,
        po_number: Optional[str] = None,
        project_code: Optional[str] = None,
        reference: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Invoice]:
        async with self._lock:
            if invoice_id not in self._invoices:
                return None
            
            invoice = self._invoices[invoice_id]
            
            if invoice.locked and not force:
                raise ValueError(f"Invoice {invoice_id} is locked")
            
            if status:
                old_status = invoice.status
                invoice.status = status
                if status == InvoiceStatus.PAID:
                    invoice.paid_date = datetime.now()
                await self._notify_observers("invoice_status_changed", invoice, old_status)
            
            if notes is not None:
                invoice.notes = notes
            if payment_terms is not None:
                invoice.payment_terms = payment_terms
            if po_number is not None:
                invoice.po_number = po_number
            if project_code is not None:
                invoice.project_code = project_code
            if reference is not None:
                invoice.reference = reference
            if metadata:
                invoice.metadata.update(metadata)
            
            invoice.updated_at = datetime.now()
            invoice.version += 1
            
            await self._notify_observers("invoice_updated", invoice)
            return invoice

    async def add_payment(
        self,
        invoice_id: str,
        amount: Decimal,
        method: PaymentMethod,
        transaction_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Invoice]:
        async with self._lock:
            if invoice_id not in self._invoices:
                return None
            
            invoice = self._invoices[invoice_id]
            
            if invoice.locked:
                raise ValueError(f"Invoice {invoice_id} is locked")
            
            if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]:
                raise ValueError(f"Invoice {invoice_id} is {invoice.status.value}")
            
            payment = InvoicePayment(
                id=str(uuid.uuid4()),
                amount=amount,
                method=method,
                status="completed",
                transaction_id=transaction_id,
                timestamp=datetime.now(),
                metadata=metadata or {}
            )
            
            invoice.payments.append(payment)
            invoice.amount_paid += amount
            invoice.balance = invoice.total - invoice.amount_paid
            invoice.amount_due = max(Decimal('0'), invoice.balance)
            
            if invoice.amount_paid >= invoice.total:
                invoice.status = InvoiceStatus.PAID
                invoice.paid_date = datetime.now()
            elif invoice.amount_paid > 0:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            
            invoice.updated_at = datetime.now()
            invoice.version += 1
            
            await self._notify_observers("payment_added", invoice, payment)
            return invoice

    async def apply_discount(
        self,
        invoice_id: str,
        discount_type: DiscountType,
        value: Decimal,
        code: Optional[str] = None,
        valid_until: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Invoice]:
        async with self._lock:
            if invoice_id not in self._invoices:
                return None
            
            invoice = self._invoices[invoice_id]
            
            if invoice.locked:
                raise ValueError(f"Invoice {invoice_id} is locked")
            
            if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]:
                raise ValueError(f"Invoice {invoice_id} is {invoice.status.value}")
            
            if discount_type == DiscountType.PERCENTAGE:
                discount_amount = invoice.subtotal * (value / 100)
            elif discount_type == DiscountType.FIXED:
                discount_amount = min(value, invoice.subtotal)
            else:
                discount_amount = Decimal('0')
            
            discount = InvoiceDiscount(
                id=str(uuid.uuid4()),
                type=discount_type,
                value=value,
                amount=discount_amount,
                code=code,
                valid_until=valid_until,
                metadata=metadata or {}
            )
            
            invoice.discounts.append(discount)
            invoice.total_discount += discount_amount
            
            invoice.total = invoice.subtotal - invoice.total_discount + invoice.total_tax
            invoice.balance = invoice.total - invoice.amount_paid
            invoice.amount_due = max(Decimal('0'), invoice.balance)
            
            invoice.updated_at = datetime.now()
            invoice.version += 1
            
            await self._notify_observers("discount_applied", invoice, discount)
            return invoice

    async def cancel_invoice(self, invoice_id: str, reason: Optional[str] = None) -> Optional[Invoice]:
        async with self._lock:
            if invoice_id not in self._invoices:
                return None
            
            invoice = self._invoices[invoice_id]
            
            if invoice.locked:
                raise ValueError(f"Invoice {invoice_id} is locked")
            
            if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]:
                raise ValueError(f"Invoice {invoice_id} is {invoice.status.value}")
            
            invoice.status = InvoiceStatus.CANCELLED
            invoice.metadata["cancellation_reason"] = reason
            invoice.updated_at = datetime.now()
            invoice.version += 1
            
            await self._notify_observers("invoice_cancelled", invoice)
            return invoice

    async def refund_invoice(
        self,
        invoice_id: str,
        amount: Optional[Decimal] = None,
        reason: Optional[str] = None
    ) -> Optional[Invoice]:
        async with self._lock:
            if invoice_id not in self._invoices:
                return None
            
            invoice = self._invoices[invoice_id]
            
            if invoice.locked:
                raise ValueError(f"Invoice {invoice_id} is locked")
            
            if invoice.status not in [InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID]:
                raise ValueError(f"Invoice {invoice_id} is not paid")
            
            refund_amount = amount or invoice.amount_paid
            
            if refund_amount > invoice.amount_paid:
                raise ValueError(f"Refund amount exceeds paid amount")
            
            invoice.amount_paid -= refund_amount
            invoice.balance = invoice.total - invoice.amount_paid
            invoice.amount_due = max(Decimal('0'), invoice.balance)
            
            if invoice.amount_paid == 0:
                invoice.status = InvoiceStatus.REFUNDED
            else:
                invoice.status = InvoiceStatus.PARTIALLY_PAID
            
            invoice.metadata["refund_reason"] = reason
            invoice.metadata["refund_amount"] = str(refund_amount)
            invoice.updated_at = datetime.now()
            invoice.version += 1
            
            await self._notify_observers("invoice_refunded", invoice)
            return invoice

    async def generate_invoice_pdf(
        self,
        invoice_id: str,
        template_id: str = "default",
        include_qr: bool = True,
        include_barcode: bool = True
    ) -> Optional[bytes]:
        if invoice_id not in self._invoices:
            return None
        
        invoice = self._invoices[invoice_id]
        template = self._templates.get(template_id, self._templates["default"])
        
        if reportlab is None:
            logger.warning("reportlab not installed, cannot generate PDF")
            return None
        
        try:
            from io import BytesIO
            buffer = BytesIO()
            
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            styles = getSampleStyleSheet()
            story = []
            
            story.append(Spacer(1, 0.25 * inch))
            
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1a1a2e'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            story.append(Paragraph(f"INVOICE", title_style))
            
            story.append(Spacer(1, 0.25 * inch))
            
            header_data = [
                [f"Invoice #{invoice.number}", f"Date: {invoice.issue_date.strftime('%Y-%m-%d')}"],
                [f"Due Date: {invoice.due_date.strftime('%Y-%m-%d')}", f"Status: {invoice.status.value.upper()}"],
                [f"PO Number: {invoice.po_number or 'N/A'}", f"Project: {invoice.project_code or 'N/A'}"]
            ]
            
            header_table = Table(header_data, colWidths=[4 * inch, 2.5 * inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey)
            ]))
            story.append(header_table)
            
            story.append(Spacer(1, 0.25 * inch))
            
            address_data = [
                ["Issuer:", "Client:"],
                [invoice.issuer_name, invoice.client_name],
                [invoice.issuer_address, invoice.client_address],
                [f"Tax ID: {invoice.issuer_tax_id or 'N/A'}", f"Tax ID: {invoice.client_tax_id or 'N/A'}"],
                [f"VAT: {invoice.issuer_vat_number or 'N/A'}", f"VAT: {invoice.client_vat_number or 'N/A'}"]
            ]
            
            address_table = Table(address_data, colWidths=[3.25 * inch, 3.25 * inch])
            address_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
            ]))
            story.append(address_table)
            
            story.append(Spacer(1, 0.25 * inch))
            
            item_data = [
                ["Item", "Description", "Quantity", "Unit Price", "Discount", "Tax", "Total"]
            ]
            
            for item in invoice.items:
                item_data.append([
                    item.sku or item.product_id or item.id[:8],
                    item.description[:40] + ("..." if len(item.description) > 40 else ""),
                    str(item.quantity),
                    f"{invoice.currency.value} {item.unit_price:.2f}",
                    f"{item.discount:.2f}%",
                    f"{item.tax_rate:.2f}%",
                    f"{invoice.currency.value} {item.total:.2f}"
                ])
            
            item_table = Table(item_data, colWidths=[0.75 * inch, 2 * inch, 0.75 * inch, 1 * inch, 0.75 * inch, 0.75 * inch, 1 * inch])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (2, 1), (6, -1), 'RIGHT'),
            ]))
            story.append(item_table)
            
            story.append(Spacer(1, 0.25 * inch))
            
            total_data = [
                ["Subtotal:", f"{invoice.currency.value} {invoice.subtotal:.2f}"],
                ["Discount:", f"{invoice.currency.value} {invoice.total_discount:.2f}"],
                ["Tax:", f"{invoice.currency.value} {invoice.total_tax:.2f}"],
                ["Total:", f"{invoice.currency.value} {invoice.total:.2f}"],
                ["Amount Paid:", f"{invoice.currency.value} {invoice.amount_paid:.2f}"],
                ["Balance Due:", f"{invoice.currency.value} {invoice.balance:.2f}"]
            ]
            
            total_table = Table(total_data, colWidths=[4 * inch, 2.5 * inch])
            total_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 5), (-1, 5), 12),
                ('TEXTCOLOR', (0, 5), (-1, 5), colors.HexColor('#1a1a2e')),
                ('BACKGROUND', (0, 5), (-1, 5), colors.whitesmoke),
            ]))
            story.append(total_table)
            
            if invoice.notes:
                story.append(Spacer(1, 0.25 * inch))
                notes_style = ParagraphStyle('Notes', parent=styles['Normal'], fontSize=10)
                story.append(Paragraph(f"<b>Notes:</b> {invoice.notes}", notes_style))
            
            if invoice.payment_terms:
                story.append(Spacer(1, 0.1 * inch))
                terms_style = ParagraphStyle('Terms', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
                story.append(Paragraph(f"<b>Payment Terms:</b> {invoice.payment_terms}", terms_style))
            
            if invoice.terms_and_conditions:
                story.append(Spacer(1, 0.1 * inch))
                tcs_style = ParagraphStyle('TC', parent=styles['Normal'], fontSize=9, textColor=colors.grey)
                story.append(Paragraph(f"<b>Terms & Conditions:</b> {invoice.terms_and_conditions}", tcs_style))
            
            if include_qr and qrcode:
                try:
                    qr_data = {
                        "invoice": invoice.number,
                        "amount": str(invoice.total),
                        "currency": invoice.currency.value,
                        "client": invoice.client_name,
                        "reference": invoice.reference or invoice.id
                    }
                    
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=4,
                        border=2,
                    )
                    qr.add_data(json.dumps(qr_data))
                    qr.make(fit=True)
                    
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    qr_buffer = BytesIO()
                    qr_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
                    
                    img = utils.ImageReader(qr_buffer)
                    story.append(Spacer(1, 0.25 * inch))
                    story.append(Image(img, width=2 * inch, height=2 * inch))
                except Exception as e:
                    logger.warning(f"Error generating QR code: {e}")
            
            if include_barcode and barcode:
                try:
                    barcode_buffer = BytesIO()
                    code128 = barcode.get_barcode_class('code128')
                    code128(f"{invoice.number[:10]}", writer=ImageWriter()).write(barcode_buffer)
                    barcode_buffer.seek(0)
                    
                    img = utils.ImageReader(barcode_buffer)
                    story.append(Spacer(1, 0.1 * inch))
                    story.append(Image(img, width=4 * inch, height=0.75 * inch))
                except Exception as e:
                    logger.warning(f"Error generating barcode: {e}")
            
            doc.build(story)
            
            buffer.seek(0)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return None

    async def generate_invoice_number_sequence(
        self,
        invoice_id: str,
        format: str = "{prefix}{year}{month}{seq:06d}"
    ) -> str:
        invoice = self._invoices.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        prefix = self.config.get("invoice_prefix", "NEXUS-INV-")
        year = datetime.now().year
        month = datetime.now().month
        
        counter_key = f"{year}_{month}"
        self._counters[counter_key] = self._counters.get(counter_key, 0) + 1
        seq = self._counters[counter_key]
        
        invoice_number = format.format(
            prefix=prefix,
            year=str(year),
            month=f"{month:02d}",
            seq=seq
        )
        
        invoice.number = invoice_number
        return invoice_number

    def _generate_invoice_number(self) -> str:
        self._last_invoice_number += 1
        prefix = self.config.get("invoice_prefix", "NEXUS-INV-")
        year = datetime.now().strftime("%Y")
        month = datetime.now().strftime("%m")
        seq = f"{self._last_invoice_number:06d}"
        return f"{prefix}{year}{month}{seq}"

    async def register_payment_processor(
        self,
        method: PaymentMethod,
        processor: Callable
    ) -> None:
        self._payment_processors[method] = processor

    async def process_payment(
        self,
        invoice_id: str,
        method: PaymentMethod,
        payment_data: Dict[str, Any]
    ) -> Optional[Invoice]:
        if method not in self._payment_processors:
            raise ValueError(f"No processor registered for {method.value}")
        
        processor = self._payment_processors[method]
        result = await processor(invoice_id, payment_data)
        
        if result.get("success"):
            invoice = await self.add_payment(
                invoice_id=invoice_id,
                amount=Decimal(str(result.get("amount", 0))),
                method=method,
                transaction_id=result.get("transaction_id"),
                metadata=result.get("metadata")
            )
            return invoice
        
        return None

    async def register_observer(self, callback: Callable) -> None:
        self._observers.append(callback)

    async def _notify_observers(self, event: str, *args, **kwargs) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args, **kwargs)
                else:
                    observer(event, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in observer: {e}")

    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        return self._invoices.get(invoice_id)

    async def get_invoice_by_number(self, number: str) -> Optional[Invoice]:
        for invoice in self._invoices.values():
            if invoice.number == number:
                return invoice
        return None

    async def get_invoices_by_client(self, client_id: str) -> List[Invoice]:
        return [i for i in self._invoices.values() if i.client_id == client_id]

    async def get_invoices_by_status(self, status: InvoiceStatus) -> List[Invoice]:
        return [i for i in self._invoices.values() if i.status == status]

    async def get_invoices_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Invoice]:
        return [
            i for i in self._invoices.values()
            if start_date <= i.issue_date <= end_date
        ]

    async def get_overdue_invoices(self) -> List[Invoice]:
        now = datetime.now()
        return [
            i for i in self._invoices.values()
            if i.status in [InvoiceStatus.PENDING, InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID]
            and i.due_date < now
            and i.balance > 0
        ]

    async def generate_report(
        self,
        start_date: datetime,
        end_date: datetime,
        name: Optional[str] = None
    ) -> InvoiceReport:
        invoices = await self.get_invoices_by_date_range(start_date, end_date)
        
        total_invoices = len(invoices)
        total_amount = sum(i.total for i in invoices)
        total_paid = sum(i.amount_paid for i in invoices)
        total_due = sum(i.balance for i in invoices)
        
        by_status = defaultdict(int)
        by_type = defaultdict(int)
        by_payment_method = defaultdict(int)
        
        total_paid_invoices = 0
        payment_days = []
        
        for invoice in invoices:
            by_status[invoice.status.value] += 1
            by_type[invoice.type.value] += 1
            
            if invoice.status == InvoiceStatus.PAID and invoice.paid_date:
                days = (invoice.paid_date - invoice.issue_date).days
                if days >= 0:
                    payment_days.append(days)
                total_paid_invoices += 1
            
            for payment in invoice.payments:
                by_payment_method[payment.method.value] += 1
        
        total_overdue = sum(
            i.balance for i in invoices
            if i.status in [InvoiceStatus.PENDING, InvoiceStatus.SENT, InvoiceStatus.VIEWED, InvoiceStatus.PARTIALLY_PAID]
            and i.due_date < datetime.now()
        )
        
        amounts = [i.total for i in invoices]
        
        if amounts:
            avg_invoice = sum(amounts) / len(amounts)
            sorted_amounts = sorted(amounts)
            median_invoice = sorted_amounts[len(sorted_amounts) // 2]
            min_invoice = min(amounts)
            max_invoice = max(amounts)
        else:
            avg_invoice = Decimal('0')
            median_invoice = Decimal('0')
            min_invoice = Decimal('0')
            max_invoice = Decimal('0')
        
        payment_collection_rate = (total_paid_invoices / total_invoices * 100) if total_invoices > 0 else 0
        
        avg_payment_days = int(sum(payment_days) / len(payment_days)) if payment_days else 0
        
        dso = (total_due / (total_amount / 365)) if total_amount > 0 else Decimal('0')
        overdue_rate = (total_overdue / total_amount * 100) if total_amount > 0 else 0
        
        total_written_off = sum(
            i.total for i in invoices
            if i.status == InvoiceStatus.WRITTEN_OFF
        )
        write_off_rate = (total_written_off / total_amount * 100) if total_amount > 0 else 0
        
        report = InvoiceReport(
            id=str(uuid.uuid4()),
            name=name or f"Invoice Report {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            start_date=start_date,
            end_date=end_date,
            total_invoices=total_invoices,
            total_amount=total_amount,
            total_paid=total_paid,
            total_due=total_due,
            total_overdue=total_overdue,
            total_tax=sum(i.total_tax for i in invoices),
            total_discount=sum(i.total_discount for i in invoices),
            average_invoice=avg_invoice,
            median_invoice=median_invoice,
            min_invoice=min_invoice,
            max_invoice=max_invoice,
            by_status=dict(by_status),
            by_type=dict(by_type),
            by_payment_method=dict(by_payment_method),
            payment_collection_rate=payment_collection_rate,
            average_payment_days=avg_payment_days,
            dso=dso,
            overdue_rate=overdue_rate,
            write_off_rate=write_off_rate,
            created_at=datetime.now()
        )
        
        self._reports[report.id] = report
        return report

    async def get_report(self, report_id: str) -> Optional[InvoiceReport]:
        return self._reports.get(report_id)

    async def get_reports_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[InvoiceReport]:
        return [
            r for r in self._reports.values()
            if start_date <= r.created_at <= end_date
        ]

    async def create_recurring_invoice(
        self,
        invoice_id: str,
        frequency: str,
        interval: int,
        end_date: Optional[datetime] = None
    ) -> Optional[InvoiceRecurrence]:
        if invoice_id not in self._invoices:
            return None
        
        recurrence = InvoiceRecurrence(
            id=str(uuid.uuid4()),
            invoice_id=invoice_id,
            frequency=frequency,
            interval=interval,
            next_date=datetime.now() + self._get_timedelta(frequency, interval),
            end_date=end_date,
            active=True
        )
        
        self._recurrences[recurrence.id] = recurrence
        return recurrence

    def _get_timedelta(self, frequency: str, interval: int) -> timedelta:
        if frequency == "daily":
            return timedelta(days=interval)
        elif frequency == "weekly":
            return timedelta(weeks=interval)
        elif frequency == "monthly":
            return timedelta(days=30 * interval)
        elif frequency == "quarterly":
            return timedelta(days=90 * interval)
        elif frequency == "yearly":
            return timedelta(days=365 * interval)
        else:
            return timedelta(days=30 * interval)

    async def process_recurring(self) -> None:
        now = datetime.now()
        for recurrence in self._recurrences.values():
            if not recurrence.active:
                continue
            
            if recurrence.next_date > now:
                continue
            
            invoice = self._invoices.get(recurrence.invoice_id)
            if not invoice:
                continue
            
            new_invoice = await self.create_invoice(
                client_id=invoice.client_id,
                client_name=invoice.client_name,
                client_address=invoice.client_address,
                client_email=invoice.client_email,
                items=[{
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "discount": item.discount,
                    "tax_rate": item.tax_rate,
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "category": item.category
                } for item in invoice.items],
                invoice_type=invoice.type,
                currency=invoice.currency,
                due_days=(invoice.due_date - invoice.issue_date).days,
                client_tax_id=invoice.client_tax_id,
                client_vat_number=invoice.client_vat_number,
                payment_terms=invoice.payment_terms,
                notes=invoice.notes,
                po_number=invoice.po_number,
                project_code=invoice.project_code,
                reference=invoice.reference,
                metadata=invoice.metadata
            )
            
            recurrence.next_date = now + self._get_timedelta(recurrence.frequency, recurrence.interval)
            
            if recurrence.end_date and recurrence.next_date > recurrence.end_date:
                recurrence.active = False
            
            await self._notify_observers("recurring_invoice_created", new_invoice, recurrence)

    async def get_recurrence(self, recurrence_id: str) -> Optional[InvoiceRecurrence]:
        return self._recurrences.get(recurrence_id)

    async def get_recurrences_by_invoice(self, invoice_id: str) -> List[InvoiceRecurrence]:
        return [
            r for r in self._recurrences.values()
            if r.invoice_id == invoice_id
        ]

    async def pause_recurrence(self, recurrence_id: str) -> bool:
        if recurrence_id not in self._recurrences:
            return False
        
        self._recurrences[recurrence_id].active = False
        return True

    async def resume_recurrence(self, recurrence_id: str) -> bool:
        if recurrence_id not in self._recurrences:
            return False
        
        self._recurrences[recurrence_id].active = True
        return True

    async def delete_recurrence(self, recurrence_id: str) -> bool:
        if recurrence_id in self._recurrences:
            del self._recurrences[recurrence_id]
            return True
        return False

    async def create_template(
        self,
        name: str,
        layout: Dict[str, Any],
        styles: Dict[str, Any],
        description: Optional[str] = None,
        header: Optional[str] = None,
        footer: Optional[str] = None,
        fields: Optional[List[str]] = None,
        logo: Optional[bytes] = None,
        watermark: Optional[bytes] = None
    ) -> InvoiceTemplate:
        template = InvoiceTemplate(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            header=header,
            footer=footer,
            styles=styles,
            layout=layout,
            fields=fields or [],
            logo=logo,
            watermark=watermark
        )
        
        self._templates[template.id] = template
        return template

    async def get_template(self, template_id: str) -> Optional[InvoiceTemplate]:
        return self._templates.get(template_id)

    async def get_templates(self) -> List[InvoiceTemplate]:
        return list(self._templates.values())

    async def update_template(
        self,
        template_id: str,
        **kwargs
    ) -> Optional[InvoiceTemplate]:
        if template_id not in self._templates:
            return None
        
        template = self._templates[template_id]
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        template.updated_at = datetime.now()
        return template

    async def delete_template(self, template_id: str) -> bool:
        if template_id in self._templates and template_id != "default":
            del self._templates[template_id]
            return True
        return False

    async def lock_invoice(self, invoice_id: str) -> bool:
        if invoice_id not in self._invoices:
            return False
        
        self._invoices[invoice_id].locked = True
        return True

    async def unlock_invoice(self, invoice_id: str) -> bool:
        if invoice_id not in self._invoices:
            return False
        
        self._invoices[invoice_id].locked = False
        return True

    def get_stats(self) -> Dict[str, Any]:
        total_invoices = len(self._invoices)
        total_draft = len([i for i in self._invoices.values() if i.status == InvoiceStatus.DRAFT])
        total_pending = len([i for i in self._invoices.values() if i.status == InvoiceStatus.PENDING])
        total_paid = len([i for i in self._invoices.values() if i.status == InvoiceStatus.PAID])
        total_overdue = len([i for i in self._invoices.values() if i.status == InvoiceStatus.OVERDUE])
        total_cancelled = len([i for i in self._invoices.values() if i.status == InvoiceStatus.CANCELLED])
        
        total_amount = sum(i.total for i in self._invoices.values())
        total_paid_amount = sum(i.amount_paid for i in self._invoices.values())
        total_due_amount = sum(i.balance for i in self._invoices.values())
        
        return {
            "total_invoices": total_invoices,
            "draft": total_draft,
            "pending": total_pending,
            "paid": total_paid,
            "overdue": total_overdue,
            "cancelled": total_cancelled,
            "total_amount": float(total_amount),
            "total_paid": float(total_paid_amount),
            "total_due": float(total_due_amount),
            "templates": len(self._templates),
            "recurrences": len(self._recurrences),
            "reports": len(self._reports),
            "payment_processors": len(self._payment_processors)
        }

    def clear_old_invoices(self, days: int = 365) -> int:
        cutoff = datetime.now() - timedelta(days=days)
        to_remove = [
            iid for iid, inv in self._invoices.items()
            if inv.created_at < cutoff and inv.status in [InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.VOID]
        ]
        
        for iid in to_remove:
            del self._invoices[iid]
        
        return len(to_remove)

    async def export_invoice_data(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = "json"
    ) -> Optional[Union[str, bytes]]:
        invoices = await self.get_invoices_by_date_range(start_date, end_date)
        
        if format == "json":
            data = []
            for invoice in invoices:
                data.append({
                    "id": invoice.id,
                    "number": invoice.number,
                    "type": invoice.type.value,
                    "status": invoice.status.value,
                    "currency": invoice.currency.value,
                    "client_name": invoice.client_name,
                    "client_email": invoice.client_email,
                    "issue_date": invoice.issue_date.isoformat(),
                    "due_date": invoice.due_date.isoformat(),
                    "subtotal": str(invoice.subtotal),
                    "total": str(invoice.total),
                    "amount_paid": str(invoice.amount_paid),
                    "balance": str(invoice.balance),
                    "items": [
                        {
                            "description": item.description,
                            "quantity": str(item.quantity),
                            "unit_price": str(item.unit_price),
                            "total": str(item.total)
                        }
                        for item in invoice.items
                    ]
                })
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            
            writer.writerow([
                "Invoice Number", "Client", "Status", "Issue Date", "Due Date",
                "Currency", "Subtotal", "Total", "Amount Paid", "Balance"
            ])
            
            for invoice in invoices:
                writer.writerow([
                    invoice.number,
                    invoice.client_name,
                    invoice.status.value,
                    invoice.issue_date.strftime("%Y-%m-%d"),
                    invoice.due_date.strftime("%Y-%m-%d"),
                    invoice.currency.value,
                    str(invoice.subtotal),
                    str(invoice.total),
                    str(invoice.amount_paid),
                    str(invoice.balance)
                ])
            
            return output.getvalue().encode('utf-8')
        
        return None


__all__ = [
    "InvoiceStatus",
    "PaymentMethod",
    "InvoiceType",
    "Currency",
    "TaxType",
    "DiscountType",
    "InvoiceLineItem",
    "InvoicePayment",
    "InvoiceTax",
    "InvoiceDiscount",
    "Invoice",
    "InvoiceTemplate",
    "InvoiceRecurrence",
    "InvoiceReport",
    "InvoiceGenerator"
]
