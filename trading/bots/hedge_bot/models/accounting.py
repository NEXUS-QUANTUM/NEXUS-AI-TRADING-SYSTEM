"""
NEXUS AI TRADING SYSTEM - HEDGE BOT ACCOUNTING MODELS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Modèles de données comptables pour le Hedge Bot.
Définition des entités comptables, transactions, et états financiers.

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
    ForeignKey, Text, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from ..utils.helpers import safe_decimal, safe_float

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class AccountType(Enum):
    """Types de comptes comptables."""
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"
    GAIN = "gain"
    LOSS = "loss"


class AccountCategory(Enum):
    """Catégories de comptes."""
    CASH = "cash"
    BANK = "bank"
    RECEIVABLE = "receivable"
    PAYABLE = "payable"
    TRADING = "trading"
    HEDGE = "hedge"
    FEE = "fee"
    TAX = "tax"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    CAPITAL = "capital"
    RETAINED_EARNINGS = "retained_earnings"


class TransactionDirection(Enum):
    """Directions de transaction."""
    DEBIT = "debit"
    CREDIT = "credit"


class JournalEntryType(Enum):
    """Types d'écritures comptables."""
    STANDARD = "standard"
    ADJUSTMENT = "adjustment"
    REVERSING = "reversing"
    CLOSING = "closing"
    OPENING = "opening"
    INTERNAL = "internal"


class AccountingPeriod(Enum):
    """Périodes comptables."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class AccountModel(Base):
    """Modèle de compte comptable."""
    __tablename__ = "accounts"

    account_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    account_type = Column(SQLEnum(AccountType), nullable=False)
    category = Column(SQLEnum(AccountCategory), nullable=False)
    currency = Column(String(10), nullable=False)
    balance = Column(Numeric(20, 8), nullable=False, default=0)
    available_balance = Column(Numeric(20, 8), nullable=False, default=0)
    frozen_balance = Column(Numeric(20, 8), nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    parent_account_id = Column(String(36), ForeignKey("accounts.account_id"), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    # Relations
    parent = relationship("AccountModel", remote_side=[account_id])
    children = relationship("AccountModel", back_populates="parent")
    journal_entries = relationship("JournalEntryModel", back_populates="account")

    __table_args__ = (
        Index("idx_accounts_user_id", "user_id"),
        Index("idx_accounts_type", "account_type"),
        Index("idx_accounts_category", "category"),
        Index("idx_accounts_parent", "parent_account_id"),
    )


class JournalEntryModel(Base):
    """Modèle d'écriture comptable."""
    __tablename__ = "journal_entries"

    entry_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.account_id"), nullable=False)
    transaction_id = Column(String(36), nullable=True)
    entry_type = Column(SQLEnum(JournalEntryType), nullable=False)
    direction = Column(SQLEnum(TransactionDirection), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    balance_before = Column(Numeric(20, 8), nullable=False)
    balance_after = Column(Numeric(20, 8), nullable=False)
    description = Column(Text, nullable=True)
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(50), nullable=True)
    metadata = Column(JSON, nullable=True)
    posted_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)

    # Relations
    account = relationship("AccountModel", back_populates="journal_entries")

    __table_args__ = (
        Index("idx_journal_entries_user_id", "user_id"),
        Index("idx_journal_entries_account_id", "account_id"),
        Index("idx_journal_entries_transaction_id", "transaction_id"),
        Index("idx_journal_entries_posted_at", "posted_at"),
    )


class TrialBalanceModel(Base):
    """Modèle de balance de vérification."""
    __tablename__ = "trial_balances"

    trial_balance_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(SQLEnum(AccountingPeriod), nullable=False)
    total_debits = Column(Numeric(20, 8), nullable=False)
    total_credits = Column(Numeric(20, 8), nullable=False)
    is_balanced = Column(Boolean, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_trial_balances_user_id", "user_id"),
        Index("idx_trial_balances_period", "period_start", "period_end"),
    )


class FinancialStatementModel(Base):
    """Modèle d'état financier."""
    __tablename__ = "financial_statements"

    statement_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    statement_type = Column(String(50), nullable=False)  # balance_sheet, income_statement, cash_flow
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    period_type = Column(SQLEnum(AccountingPeriod), nullable=False)
    content = Column(JSON, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_financial_statements_user_id", "user_id"),
        Index("idx_financial_statements_type", "statement_type"),
        Index("idx_financial_statements_period", "period_start", "period_end"),
    )


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class Account:
    """Compte comptable."""
    account_id: UUID
    user_id: UUID
    name: str
    account_type: AccountType
    category: AccountCategory
    currency: str
    balance: Decimal
    available_balance: Decimal
    frozen_balance: Decimal
    is_active: bool
    parent_account_id: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "account_id": str(self.account_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "account_type": self.account_type.value,
            "category": self.category.value,
            "currency": self.currency,
            "balance": str(self.balance),
            "available_balance": str(self.available_balance),
            "frozen_balance": str(self.frozen_balance),
            "is_active": self.is_active,
            "parent_account_id": str(self.parent_account_id) if self.parent_account_id else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class JournalEntry:
    """Écriture comptable."""
    entry_id: UUID
    user_id: UUID
    account_id: UUID
    transaction_id: Optional[UUID]
    entry_type: JournalEntryType
    direction: TransactionDirection
    amount: Decimal
    currency: str
    balance_before: Decimal
    balance_after: Decimal
    description: Optional[str]
    reference_id: Optional[UUID]
    reference_type: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    posted_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "entry_id": str(self.entry_id),
            "user_id": str(self.user_id),
            "account_id": str(self.account_id),
            "transaction_id": str(self.transaction_id) if self.transaction_id else None,
            "entry_type": self.entry_type.value,
            "direction": self.direction.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "balance_before": str(self.balance_before),
            "balance_after": str(self.balance_after),
            "description": self.description,
            "reference_id": str(self.reference_id) if self.reference_id else None,
            "reference_type": self.reference_type,
            "metadata": self.metadata,
            "posted_at": self.posted_at.isoformat(),
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TrialBalance:
    """Balance de vérification."""
    trial_balance_id: UUID
    user_id: UUID
    period_start: datetime
    period_end: datetime
    period_type: AccountingPeriod
    total_debits: Decimal
    total_credits: Decimal
    is_balanced: bool
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "trial_balance_id": str(self.trial_balance_id),
            "user_id": str(self.user_id),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_type": self.period_type.value,
            "total_debits": str(self.total_debits),
            "total_credits": str(self.total_credits),
            "is_balanced": self.is_balanced,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class FinancialStatement:
    """État financier."""
    statement_id: UUID
    user_id: UUID
    statement_type: str
    period_start: datetime
    period_end: datetime
    period_type: AccountingPeriod
    content: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "statement_id": str(self.statement_id),
            "user_id": str(self.user_id),
            "statement_type": self.statement_type,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "period_type": self.period_type.value,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class BalanceSheet:
    """Bilan comptable."""
    assets: Dict[str, Decimal]
    liabilities: Dict[str, Decimal]
    equity: Dict[str, Decimal]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "assets": {k: str(v) for k, v in self.assets.items()},
            "liabilities": {k: str(v) for k, v in self.liabilities.items()},
            "equity": {k: str(v) for k, v in self.equity.items()},
            "total_assets": str(self.total_assets),
            "total_liabilities": str(self.total_liabilities),
            "total_equity": str(self.total_equity),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class IncomeStatement:
    """Compte de résultat."""
    revenue: Dict[str, Decimal]
    expenses: Dict[str, Decimal]
    total_revenue: Decimal
    total_expenses: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "revenue": {k: str(v) for k, v in self.revenue.items()},
            "expenses": {k: str(v) for k, v in self.expenses.items()},
            "total_revenue": str(self.total_revenue),
            "total_expenses": str(self.total_expenses),
            "gross_profit": str(self.gross_profit),
            "net_profit": str(self.net_profit),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CashFlowStatement:
    """Tableau des flux de trésorerie."""
    operating_activities: Dict[str, Decimal]
    investing_activities: Dict[str, Decimal]
    financing_activities: Dict[str, Decimal]
    net_cash_from_operating: Decimal
    net_cash_from_investing: Decimal
    net_cash_from_financing: Decimal
    net_change_in_cash: Decimal
    beginning_cash: Decimal
    ending_cash: Decimal
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "operating_activities": {k: str(v) for k, v in self.operating_activities.items()},
            "investing_activities": {k: str(v) for k, v in self.investing_activities.items()},
            "financing_activities": {k: str(v) for k, v in self.financing_activities.items()},
            "net_cash_from_operating": str(self.net_cash_from_operating),
            "net_cash_from_investing": str(self.net_cash_from_investing),
            "net_cash_from_financing": str(self.net_cash_from_financing),
            "net_change_in_cash": str(self.net_change_in_cash),
            "beginning_cash": str(self.beginning_cash),
            "ending_cash": str(self.ending_cash),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_account(
    user_id: UUID,
    name: str,
    account_type: AccountType,
    category: AccountCategory,
    currency: str = "USD",
    initial_balance: Decimal = Decimal("0"),
    parent_account_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None
) -> Account:
    """
    Crée un compte comptable.

    Args:
        user_id: ID de l'utilisateur
        name: Nom du compte
        account_type: Type de compte
        category: Catégorie
        currency: Devise
        initial_balance: Solde initial
        parent_account_id: ID du compte parent
        metadata: Métadonnées

    Returns:
        Compte créé
    """
    return Account(
        account_id=uuid4(),
        user_id=user_id,
        name=name,
        account_type=account_type,
        category=category,
        currency=currency,
        balance=initial_balance,
        available_balance=initial_balance,
        frozen_balance=Decimal("0"),
        is_active=True,
        parent_account_id=parent_account_id,
        metadata=metadata or {}
    )


def create_journal_entry(
    user_id: UUID,
    account_id: UUID,
    direction: TransactionDirection,
    amount: Decimal,
    currency: str,
    balance_before: Decimal,
    balance_after: Decimal,
    entry_type: JournalEntryType = JournalEntryType.STANDARD,
    description: Optional[str] = None,
    reference_id: Optional[UUID] = None,
    reference_type: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> JournalEntry:
    """
    Crée une écriture comptable.

    Args:
        user_id: ID de l'utilisateur
        account_id: ID du compte
        direction: Direction
        amount: Montant
        currency: Devise
        balance_before: Solde avant
        balance_after: Solde après
        entry_type: Type d'écriture
        description: Description
        reference_id: ID de référence
        reference_type: Type de référence
        metadata: Métadonnées

    Returns:
        Écriture comptable
    """
    return JournalEntry(
        entry_id=uuid4(),
        user_id=user_id,
        account_id=account_id,
        transaction_id=uuid4(),
        entry_type=entry_type,
        direction=direction,
        amount=amount,
        currency=currency,
        balance_before=balance_before,
        balance_after=balance_after,
        description=description,
        reference_id=reference_id,
        reference_type=reference_type,
        metadata=metadata or {}
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AccountType",
    "AccountCategory",
    "TransactionDirection",
    "JournalEntryType",
    "AccountingPeriod",
    "AccountModel",
    "JournalEntryModel",
    "TrialBalanceModel",
    "FinancialStatementModel",
    "Account",
    "JournalEntry",
    "TrialBalance",
    "FinancialStatement",
    "BalanceSheet",
    "IncomeStatement",
    "CashFlowStatement",
    "create_account",
    "create_journal_entry"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des modèles comptables."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT ACCOUNTING MODELS")
    print("=" * 60)

    # Création d'un compte
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    print(f"\n📊 Création d'un compte...")
    
    account = create_account(
        user_id=user_id,
        name="Trading Account",
        account_type=AccountType.ASSET,
        category=AccountCategory.TRADING,
        currency="USD",
        initial_balance=Decimal("10000")
    )

    print(f"   ID: {account.account_id}")
    print(f"   Nom: {account.name}")
    print(f"   Solde: ${account.balance}")

    # Création d'une écriture comptable
    print(f"\n📝 Création d'une écriture comptable...")
    
    entry = create_journal_entry(
        user_id=user_id,
        account_id=account.account_id,
        direction=TransactionDirection.DEBIT,
        amount=Decimal("500"),
        currency="USD",
        balance_before=account.balance,
        balance_after=account.balance + Decimal("500"),
        description="Dépôt de fonds",
        metadata={"source": "bank_transfer"}
    )

    print(f"   ID: {entry.entry_id}")
    print(f"   Direction: {entry.direction.value}")
    print(f"   Montant: ${entry.amount}")
    print(f"   Solde après: ${entry.balance_after}")

    # Mise à jour du compte
    account.balance = entry.balance_after
    account.available_balance = entry.balance_after

    # Affichage du bilan
    print(f"\n📊 Bilan simplifié:")
    print(f"   Actif: ${account.balance}")
    print(f"   Passif: $0")
    print(f"   Capitaux: ${account.balance}")

    print("\n" + "=" * 60)
    print("Accounting Models NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
