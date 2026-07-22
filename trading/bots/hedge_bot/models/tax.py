"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TAX MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données fiscales pour le Hedge Bot.
Définition des entités fiscales, événements, rapports, et métriques.

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
    DIVIDEND = "dividend"
    INTEREST = "interest"


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
    TRANSFER = "transfer"
    GIFT = "gift"
    INHERITANCE = "inheritance"


class TaxStatus(Enum):
    """Statuts de taxe."""
    CALCULATED = "calculated"
    REPORTED = "reported"
    PAID = "paid"
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    ADJUSTED = "adjusted"
    EXEMPT = "exempt"
    DEFERRED = "deferred"


class TaxJurisdiction(Enum):
    """Juridictions fiscales."""
    US_FEDERAL = "us_federal"
    US_STATE = "us_state"
    US_LOCAL = "us_local"
    EU = "eu"
    UK = "uk"
    FR = "fr"
    DE = "de"
    CH = "ch"
    SG = "sg"
    HK = "hk"
    JP = "jp"
    AU = "au"
    CA = "ca"
    OTHER = "other"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class TaxEventModel(Base):
    """Modèle d'événement fiscal."""
    __tablename__ = "tax_events"

    event_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    trade_id = Column(String(36), nullable=True)
    event_type = Column(SQLEnum(TaxEventType), nullable=False)
    tax_type = Column(SQLEnum(TaxType), nullable=False)
    jurisdiction = Column(SQLEnum(TaxJurisdiction), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    asset = Column(String(50), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    fee = Column(Numeric(20, 8), nullable=False)
    fee_currency = Column(String(10), nullable=True)
    tax_amount = Column(Numeric(20, 8), nullable=False)
    tax_rate = Column(Float, nullable=False)
    tax_currency = Column(String(10), nullable=False)
    status = Column(SQLEnum(TaxStatus), nullable=False)
    metadata = Column(JSON, nullable=True)
    reported_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_tax_events_user_id", "user_id"),
        Index("idx_tax_events_trade_id", "trade_id"),
        Index("idx_tax_events_type", "event_type"),
        Index("idx_tax_events_tax_type", "tax_type"),
        Index("idx_tax_events_jurisdiction", "jurisdiction"),
        Index("idx_tax_events_status", "status"),
        Index("idx_tax_events_timestamp", "timestamp"),
    )


class TaxReportModel(Base):
    """Modèle de rapport fiscal."""
    __tablename__ = "tax_reports"

    report_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    tax_type = Column(SQLEnum(TaxType), nullable=False)
    jurisdiction = Column(SQLEnum(TaxJurisdiction), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_income = Column(Numeric(20, 8), nullable=False)
    total_expenses = Column(Numeric(20, 8), nullable=False)
    total_taxable = Column(Numeric(20, 8), nullable=False)
    total_tax = Column(Numeric(20, 8), nullable=False)
    tax_rate = Column(Float, nullable=False)
    status = Column(SQLEnum(TaxStatus), nullable=False)
    metadata = Column(JSON, nullable=True)
    generated_at = Column(DateTime, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_tax_reports_user_id", "user_id"),
        Index("idx_tax_reports_tax_type", "tax_type"),
        Index("idx_tax_reports_jurisdiction", "jurisdiction"),
        Index("idx_tax_reports_period", "period_start", "period_end"),
        Index("idx_tax_reports_status", "status"),
    )


class TaxDeductionModel(Base):
    """Modèle de déduction fiscale."""
    __tablename__ = "tax_deductions"

    deduction_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tax_type = Column(SQLEnum(TaxType), nullable=False)
    jurisdiction = Column(SQLEnum(TaxJurisdiction), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    year = Column(Integer, nullable=False)
    is_recurring = Column(Boolean, default=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_tax_deductions_user_id", "user_id"),
        Index("idx_tax_deductions_tax_type", "tax_type"),
        Index("idx_tax_deductions_jurisdiction", "jurisdiction"),
        Index("idx_tax_deductions_year", "year"),
    )


class TaxLossHarvestModel(Base):
    """Modèle de harvest de pertes fiscales."""
    __tablename__ = "tax_loss_harvests"

    harvest_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    symbol = Column(String(50), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    buy_price = Column(Numeric(20, 8), nullable=False)
    sell_price = Column(Numeric(20, 8), nullable=False)
    loss_amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    tax_saved = Column(Numeric(20, 8), nullable=False)
    tax_rate = Column(Float, nullable=False)
    executed_at = Column(DateTime, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_tax_loss_harvests_user_id", "user_id"),
        Index("idx_tax_loss_harvests_symbol", "symbol"),
        Index("idx_tax_loss_harvests_executed_at", "executed_at"),
    )


class TaxMetricsModel(Base):
    """Modèle de métriques fiscales."""
    __tablename__ = "tax_metrics"

    metric_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    year = Column(Integer, nullable=False)
    total_tax_paid = Column(Numeric(20, 8), nullable=False)
    total_tax_owed = Column(Numeric(20, 8), nullable=False)
    tax_efficiency = Column(Float, nullable=False)
    effective_tax_rate = Column(Float, nullable=False)
    marginal_tax_rate = Column(Float, nullable=False)
    tax_loss_harvesting = Column(Numeric(20, 8), nullable=False)
    tax_liability = Column(Numeric(20, 8), nullable=False)
    metadata = Column(JSON, nullable=True)
    calculated_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_tax_metrics_user_id", "user_id"),
        Index("idx_tax_metrics_year", "year"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class TaxEvent:
    """Événement fiscal."""
    event_id: UUID
    user_id: UUID
    trade_id: Optional[UUID]
    event_type: TaxEventType
    tax_type: TaxType
    jurisdiction: TaxJurisdiction
    timestamp: datetime
    asset: str
    quantity: Decimal
    price: Decimal
    amount: Decimal
    currency: str
    fee: Decimal
    fee_currency: Optional[str]
    tax_amount: Decimal
    tax_rate: float
    tax_currency: str
    status: TaxStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    reported_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "event_id": str(self.event_id),
            "user_id": str(self.user_id),
            "trade_id": str(self.trade_id) if self.trade_id else None,
            "event_type": self.event_type.value,
            "tax_type": self.tax_type.value,
            "jurisdiction": self.jurisdiction.value,
            "timestamp": self.timestamp.isoformat(),
            "asset": self.asset,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "amount": str(self.amount),
            "currency": self.currency,
            "fee": str(self.fee),
            "fee_currency": self.fee_currency,
            "tax_amount": str(self.tax_amount),
            "tax_rate": self.tax_rate,
            "tax_currency": self.tax_currency,
            "status": self.status.value,
            "metadata": self.metadata,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class TaxReport:
    """Rapport fiscal."""
    report_id: UUID
    user_id: UUID
    tax_type: TaxType
    jurisdiction: TaxJurisdiction
    period_start: datetime
    period_end: datetime
    total_income: Decimal
    total_expenses: Decimal
    total_taxable: Decimal
    total_tax: Decimal
    tax_rate: float
    status: TaxStatus
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "report_id": str(self.report_id),
            "user_id": str(self.user_id),
            "tax_type": self.tax_type.value,
            "jurisdiction": self.jurisdiction.value,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_income": str(self.total_income),
            "total_expenses": str(self.total_expenses),
            "total_taxable": str(self.total_taxable),
            "total_tax": str(self.total_tax),
            "tax_rate": self.tax_rate,
            "status": self.status.value,
            "metadata": self.metadata,
            "generated_at": self.generated_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TaxDeduction:
    """Déduction fiscale."""
    deduction_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    tax_type: TaxType
    jurisdiction: TaxJurisdiction
    amount: Decimal
    currency: str
    year: int
    is_recurring: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "deduction_id": str(self.deduction_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "description": self.description,
            "tax_type": self.tax_type.value,
            "jurisdiction": self.jurisdiction.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "year": self.year,
            "is_recurring": self.is_recurring,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class TaxLossHarvest:
    """Harvest de pertes fiscales."""
    harvest_id: UUID
    user_id: UUID
    symbol: str
    quantity: Decimal
    buy_price: Decimal
    sell_price: Decimal
    loss_amount: Decimal
    currency: str
    tax_saved: Decimal
    tax_rate: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "harvest_id": str(self.harvest_id),
            "user_id": str(self.user_id),
            "symbol": self.symbol,
            "quantity": str(self.quantity),
            "buy_price": str(self.buy_price),
            "sell_price": str(self.sell_price),
            "loss_amount": str(self.loss_amount),
            "currency": self.currency,
            "tax_saved": str(self.tax_saved),
            "tax_rate": self.tax_rate,
            "metadata": self.metadata,
            "executed_at": self.executed_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TaxMetrics:
    """Métriques fiscales."""
    metric_id: UUID
    user_id: UUID
    year: int
    total_tax_paid: Decimal
    total_tax_owed: Decimal
    tax_efficiency: float
    effective_tax_rate: float
    marginal_tax_rate: float
    tax_loss_harvesting: Decimal
    tax_liability: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "metric_id": str(self.metric_id),
            "user_id": str(self.user_id),
            "year": self.year,
            "total_tax_paid": str(self.total_tax_paid),
            "total_tax_owed": str(self.total_tax_owed),
            "tax_efficiency": self.tax_efficiency,
            "effective_tax_rate": self.effective_tax_rate,
            "marginal_tax_rate": self.marginal_tax_rate,
            "tax_loss_harvesting": str(self.tax_loss_harvesting),
            "tax_liability": str(self.tax_liability),
            "metadata": self.metadata,
            "calculated_at": self.calculated_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_tax_event(
    user_id: UUID,
    event_type: TaxEventType,
    tax_type: TaxType,
    jurisdiction: TaxJurisdiction,
    timestamp: datetime,
    asset: str,
    quantity: Decimal,
    price: Decimal,
    amount: Decimal,
    currency: str,
    fee: Decimal = Decimal("0"),
    fee_currency: Optional[str] = None,
    tax_amount: Optional[Decimal] = None,
    tax_rate: Optional[float] = None,
    trade_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> TaxEvent:
    """
    Crée un événement fiscal.

    Args:
        user_id: ID de l'utilisateur
        event_type: Type d'événement
        tax_type: Type de taxe
        jurisdiction: Juridiction
        timestamp: Date/heure
        asset: Actif
        quantity: Quantité
        price: Prix
        amount: Montant
        currency: Devise
        fee: Frais
        fee_currency: Devise des frais
        tax_amount: Montant de la taxe
        tax_rate: Taux de taxe
        trade_id: ID du trade
        metadata: Métadonnées

    Returns:
        Événement fiscal
    """
    if tax_amount is None:
        tax_rate = tax_rate or 0.0
        tax_amount = amount * Decimal(str(tax_rate))

    return TaxEvent(
        event_id=uuid4(),
        user_id=user_id,
        trade_id=trade_id,
        event_type=event_type,
        tax_type=tax_type,
        jurisdiction=jurisdiction,
        timestamp=timestamp,
        asset=asset,
        quantity=quantity,
        price=price,
        amount=amount,
        currency=currency,
        fee=fee,
        fee_currency=fee_currency or currency,
        tax_amount=tax_amount,
        tax_rate=tax_rate or 0.0,
        tax_currency=currency,
        status=TaxStatus.CALCULATED,
        metadata=metadata or {}
    )


def create_tax_deduction(
    user_id: UUID,
    name: str,
    tax_type: TaxType,
    jurisdiction: TaxJurisdiction,
    amount: Decimal,
    currency: str,
    year: int,
    description: Optional[str] = None,
    is_recurring: bool = False,
    metadata: Optional[Dict] = None
) -> TaxDeduction:
    """
    Crée une déduction fiscale.

    Args:
        user_id: ID de l'utilisateur
        name: Nom
        tax_type: Type de taxe
        jurisdiction: Juridiction
        amount: Montant
        currency: Devise
        year: Année
        description: Description
        is_recurring: Récurrent
        metadata: Métadonnées

    Returns:
        Déduction fiscale
    """
    return TaxDeduction(
        deduction_id=uuid4(),
        user_id=user_id,
        name=name,
        description=description,
        tax_type=tax_type,
        jurisdiction=jurisdiction,
        amount=amount,
        currency=currency,
        year=year,
        is_recurring=is_recurring,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TaxType",
    "TaxEventType",
    "TaxStatus",
    "TaxJurisdiction",
    "TaxEventModel",
    "TaxReportModel",
    "TaxDeductionModel",
    "TaxLossHarvestModel",
    "TaxMetricsModel",
    "TaxEvent",
    "TaxReport",
    "TaxDeduction",
    "TaxLossHarvest",
    "TaxMetrics",
    "create_tax_event",
    "create_tax_deduction"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles fiscaux."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TAX MODELS")
    print("=" * 60)

    # Création d'un événement fiscal
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📝 Création d'un événement fiscal...")
    
    event = create_tax_event(
        user_id=user_id,
        event_type=TaxEventType.SELL,
        tax_type=TaxType.CAPITAL_GAINS,
        jurisdiction=TaxJurisdiction.FR,
        timestamp=datetime.now(),
        asset="BTC",
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        amount=Decimal("25000"),
        currency="EUR",
        fee=Decimal("25"),
        tax_rate=0.30,
        metadata={"strategy": "scalping"}
    )

    print(f"   ID: {event.event_id}")
    print(f"   Type: {event.event_type.value}")
    print(f"   Actif: {event.asset}")
    print(f"   Montant: ${event.amount}")
    print(f"   Taxe: ${event.tax_amount}")
    print(f"   Taux: {event.tax_rate*100:.1f}%")

    # Création d'une déduction fiscale
    print(f"\n📋 Création d'une déduction fiscale...")
    
    deduction = create_tax_deduction(
        user_id=user_id,
        name="Frais de trading",
        tax_type=TaxType.INCOME,
        jurisdiction=TaxJurisdiction.FR,
        amount=Decimal("500"),
        currency="EUR",
        year=2026,
        description="Frais de trading déductibles"
    )

    print(f"   ID: {deduction.deduction_id}")
    print(f"   Nom: {deduction.name}")
    print(f"   Montant: ${deduction.amount}")
    print(f"   Année: {deduction.year}")

    # Création d'un harvest de pertes
    print(f"\n🌾 Création d'un harvest de pertes...")
    
    harvest = TaxLossHarvest(
        harvest_id=uuid4(),
        user_id=user_id,
        symbol="ETH",
        quantity=Decimal("2"),
        buy_price=Decimal("3000"),
        sell_price=Decimal("2800"),
        loss_amount=Decimal("400"),
        currency="EUR",
        tax_saved=Decimal("120"),
        tax_rate=0.30,
        executed_at=datetime.now()
    )

    print(f"   ID: {harvest.harvest_id}")
    print(f"   Symbole: {harvest.symbol}")
    print(f"   Perte: ${harvest.loss_amount}")
    print(f"   Taxe économisée: ${harvest.tax_saved}")

    # Métriques fiscales
    print(f"\n📊 Métriques fiscales:")
    
    metrics = TaxMetrics(
        metric_id=uuid4(),
        user_id=user_id,
        year=2026,
        total_tax_paid=Decimal("1500"),
        total_tax_owed=Decimal("1800"),
        tax_efficiency=0.75,
        effective_tax_rate=0.28,
        marginal_tax_rate=0.30,
        tax_loss_harvesting=Decimal("400"),
        tax_liability=Decimal("300")
    )

    print(f"   Taxe payée: ${metrics.total_tax_paid}")
    print(f"   Efficacité fiscale: {metrics.tax_efficiency*100:.1f}%")
    print(f"   Taux effectif: {metrics.effective_tax_rate*100:.1f}%")
    print(f"   Tax loss harvesting: ${metrics.tax_loss_harvesting}")

    print("\n" + "=" * 60)
    print("Tax Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
