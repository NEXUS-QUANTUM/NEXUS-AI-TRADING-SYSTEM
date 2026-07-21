"""
NEXUS AI TRADING SYSTEM - HEDGE BOT ACCOUNTING MANAGER MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion comptable pour le Hedge Bot.
Gestion des comptes, transactions, soldes, et reporting financier.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import create_engine, Column, String, DateTime, Numeric, Integer, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from ..utils.helpers import safe_decimal, safe_float
from ..utils.formatters import Formatters, create_formatters

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class AccountType(Enum):
    """Types de comptes."""
    MASTER = "master"
    SUB = "sub"
    EXCHANGE = "exchange"
    WALLET = "wallet"
    TRADING = "trading"
    HEDGE = "hedge"
    FEE = "fee"
    PROFIT = "profit"
    LOSS = "loss"


class AccountStatus(Enum):
    """Statuts de compte."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FROZEN = "frozen"
    CLOSED = "closed"
    PENDING = "pending"


class TransactionCategory(Enum):
    """Catégories de transactions."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE = "trade"
    FEE = "fee"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    ADJUSTMENT = "adjustment"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    PROFIT = "profit"
    LOSS = "loss"
    OTHER = "other"


@dataclass
class Account:
    """Compte."""
    account_id: UUID
    user_id: UUID
    name: str
    account_type: AccountType
    currency: str
    balance: Decimal
    available_balance: Decimal
    frozen_balance: Decimal
    status: AccountStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "account_id": str(self.account_id),
            "user_id": str(self.user_id),
            "name": self.name,
            "account_type": self.account_type.value,
            "currency": self.currency,
            "balance": str(self.balance),
            "available_balance": str(self.available_balance),
            "frozen_balance": str(self.frozen_balance),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class Transaction:
    """Transaction comptable."""
    transaction_id: UUID
    account_id: UUID
    user_id: UUID
    category: TransactionCategory
    amount: Decimal
    currency: str
    balance_before: Decimal
    balance_after: Decimal
    description: str
    reference_id: Optional[UUID] = None
    reference_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "transaction_id": str(self.transaction_id),
            "account_id": str(self.account_id),
            "user_id": str(self.user_id),
            "category": self.category.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "balance_before": str(self.balance_before),
            "balance_after": str(self.balance_after),
            "description": self.description,
            "reference_id": str(self.reference_id) if self.reference_id else None,
            "reference_type": self.reference_type,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class AccountSummary:
    """Résumé de compte."""
    account_id: UUID
    user_id: UUID
    total_balance: Decimal
    total_available: Decimal
    total_frozen: Decimal
    total_deposits: Decimal
    total_withdrawals: Decimal
    total_trades: Decimal
    total_fees: Decimal
    total_profit: Decimal
    total_loss: Decimal
    net_profit: Decimal
    roi_percentage: float
    transaction_count: int
    period_start: datetime
    period_end: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "account_id": str(self.account_id),
            "user_id": str(self.user_id),
            "total_balance": str(self.total_balance),
            "total_available": str(self.total_available),
            "total_frozen": str(self.total_frozen),
            "total_deposits": str(self.total_deposits),
            "total_withdrawals": str(self.total_withdrawals),
            "total_trades": str(self.total_trades),
            "total_fees": str(self.total_fees),
            "total_profit": str(self.total_profit),
            "total_loss": str(self.total_loss),
            "net_profit": str(self.net_profit),
            "roi_percentage": self.roi_percentage,
            "transaction_count": self.transaction_count,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE ACCOUNTING MANAGER
# ============================================================================

class AccountingManager:
    """
    Gestionnaire comptable pour le Hedge Bot.
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le gestionnaire comptable.

        Args:
            database_url: URL de la base de données
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.database_url = database_url
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Formateurs
        self.formatters = create_formatters()
        
        # Cache
        self._account_cache: Dict[UUID, Account] = {}
        self._transaction_cache: Dict[UUID, List[Transaction]] = {}
        self._summary_cache: Dict[UUID, AccountSummary] = {}
        
        # Session DB
        self._engine = None
        self._session_factory = None
        
        # Métriques
        self._metrics = {
            "total_accounts": 0,
            "total_transactions": 0,
            "total_volume": Decimal("0"),
            "total_fees": Decimal("0"),
            "total_profit": Decimal("0"),
            "by_category": {},
            "last_transaction": None
        }

        # Initialisation de la base de données
        if database_url:
            self._init_database()

        logger.info("AccountingManager initialisé avec succès")

    def _init_database(self) -> None:
        """Initialise la base de données."""
        try:
            self._engine = create_engine(self.database_url)
            Base.metadata.create_all(self._engine)
            self._session_factory = sessionmaker(bind=self._engine)
            logger.info("Base de données comptable initialisée")
        except Exception as e:
            logger.error(f"Erreur d'initialisation de la base de données: {e}")

    # ========================================================================
    # GESTION DES COMPTES
    # ========================================================================

    async def create_account(
        self,
        user_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str = "USD",
        initial_balance: Decimal = Decimal("0"),
        metadata: Optional[Dict] = None
    ) -> Account:
        """
        Crée un compte.

        Args:
            user_id: ID de l'utilisateur
            name: Nom du compte
            account_type: Type de compte
            currency: Devise
            initial_balance: Solde initial
            metadata: Métadonnées

        Returns:
            Compte créé
        """
        try:
            account_id = uuid4()
            now = datetime.now()

            account = Account(
                account_id=account_id,
                user_id=user_id,
                name=name,
                account_type=account_type,
                currency=currency,
                balance=initial_balance,
                available_balance=initial_balance,
                frozen_balance=Decimal("0"),
                status=AccountStatus.ACTIVE,
                created_at=now,
                updated_at=now,
                metadata=metadata or {}
            )

            # Mise en cache
            self._account_cache[account_id] = account
            self._metrics["total_accounts"] += 1

            # Sauvegarde en base de données
            if self._session_factory:
                # Logique de sauvegarde DB
                pass

            # Sauvegarde Redis
            if self.redis:
                await self._save_account(account)

            logger.info(f"Compte créé: {account_id} - {name}")
            return account

        except Exception as e:
            logger.error(f"Erreur lors de la création du compte: {e}")
            raise

    async def get_account(
        self,
        account_id: UUID
    ) -> Optional[Account]:
        """
        Récupère un compte.

        Args:
            account_id: ID du compte

        Returns:
            Compte ou None
        """
        try:
            # Vérification du cache
            if account_id in self._account_cache:
                return self._account_cache[account_id]

            # Récupération depuis Redis
            if self.redis:
                account = await self._load_account(account_id)
                if account:
                    self._account_cache[account_id] = account
                    return account

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du compte: {e}")
            return None

    async def get_accounts(
        self,
        user_id: UUID,
        account_type: Optional[AccountType] = None,
        status: Optional[AccountStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Account]:
        """
        Récupère les comptes d'un utilisateur.

        Args:
            user_id: ID de l'utilisateur
            account_type: Filtrer par type
            status: Filtrer par statut
            limit: Nombre de comptes
            offset: Décalage

        Returns:
            Liste des comptes
        """
        try:
            accounts = list(self._account_cache.values())
            
            accounts = [a for a in accounts if a.user_id == user_id]
            
            if account_type:
                accounts = [a for a in accounts if a.account_type == account_type]
            if status:
                accounts = [a for a in accounts if a.status == status]
            
            accounts.sort(key=lambda x: x.created_at, reverse=True)
            
            return accounts[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des comptes: {e}")
            return []

    async def update_balance(
        self,
        account_id: UUID,
        amount: Decimal,
        operation: str = "add"
    ) -> bool:
        """
        Met à jour le solde d'un compte.

        Args:
            account_id: ID du compte
            amount: Montant
            operation: "add" ou "subtract"

        Returns:
            True si la mise à jour a réussi
        """
        try:
            account = await self.get_account(account_id)
            if not account:
                return False

            if operation == "add":
                account.balance += amount
                account.available_balance += amount
            else:
                account.balance -= amount
                account.available_balance -= amount

            account.updated_at = datetime.now()
            
            self._account_cache[account_id] = account

            # Sauvegarde
            if self.redis:
                await self._save_account(account)

            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du solde: {e}")
            return False

    # ========================================================================
    # GESTION DES TRANSACTIONS
    # ========================================================================

    async def add_transaction(
        self,
        account_id: UUID,
        user_id: UUID,
        category: TransactionCategory,
        amount: Decimal,
        description: str,
        reference_id: Optional[UUID] = None,
        reference_type: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Transaction:
        """
        Ajoute une transaction.

        Args:
            account_id: ID du compte
            user_id: ID de l'utilisateur
            category: Catégorie
            amount: Montant
            description: Description
            reference_id: ID de référence
            reference_type: Type de référence
            metadata: Métadonnées

        Returns:
            Transaction créée
        """
        try:
            account = await self.get_account(account_id)
            if not account:
                raise ValueError(f"Compte {account_id} non trouvé")

            balance_before = account.balance
            balance_after = balance_before + amount

            # Vérification du solde
            if amount < 0 and abs(amount) > account.available_balance:
                raise ValueError(f"Solde insuffisant: {account.available_balance}")

            transaction = Transaction(
                transaction_id=uuid4(),
                account_id=account_id,
                user_id=user_id,
                category=category,
                amount=amount,
                currency=account.currency,
                balance_before=balance_before,
                balance_after=balance_after,
                description=description,
                reference_id=reference_id,
                reference_type=reference_type,
                metadata=metadata or {}
            )

            # Mise à jour du compte
            account.balance = balance_after
            account.available_balance = balance_after - account.frozen_balance
            account.updated_at = datetime.now()

            # Stockage
            if account_id not in self._transaction_cache:
                self._transaction_cache[account_id] = []
            self._transaction_cache[account_id].append(transaction)

            # Mise à jour des métriques
            self._metrics["total_transactions"] += 1
            self._metrics["total_volume"] += abs(amount)
            self._metrics["last_transaction"] = datetime.now().isoformat()

            category_key = category.value
            if category_key not in self._metrics["by_category"]:
                self._metrics["by_category"][category_key] = 0
            self._metrics["by_category"][category_key] += 1

            logger.info(f"Transaction ajoutée: {transaction.transaction_id} - {amount} {account.currency}")
            return transaction

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de la transaction: {e}")
            raise

    async def get_transactions(
        self,
        account_id: UUID,
        category: Optional[TransactionCategory] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Récupère les transactions d'un compte.

        Args:
            account_id: ID du compte
            category: Filtrer par catégorie
            from_date: Date de début
            to_date: Date de fin
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des transactions
        """
        try:
            transactions = self._transaction_cache.get(account_id, [])
            
            if category:
                transactions = [t for t in transactions if t.category == category]
            if from_date:
                transactions = [t for t in transactions if t.created_at >= from_date]
            if to_date:
                transactions = [t for t in transactions if t.created_at <= to_date]
            
            transactions.sort(key=lambda x: x.created_at, reverse=True)
            
            return transactions[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des transactions: {e}")
            return []

    # ========================================================================
    # RAPPORTS ET RÉSUMÉS
    # ========================================================================

    async def get_account_summary(
        self,
        account_id: UUID,
        period_days: int = 30
    ) -> AccountSummary:
        """
        Récupère le résumé d'un compte.

        Args:
            account_id: ID du compte
            period_days: Période en jours

        Returns:
            Résumé du compte
        """
        try:
            account = await self.get_account(account_id)
            if not account:
                raise ValueError(f"Compte {account_id} non trouvé")

            now = datetime.now()
            period_start = now - timedelta(days=period_days)

            transactions = await self.get_transactions(
                account_id=account_id,
                from_date=period_start
            )

            total_deposits = Decimal("0")
            total_withdrawals = Decimal("0")
            total_trades = Decimal("0")
            total_fees = Decimal("0")
            total_profit = Decimal("0")
            total_loss = Decimal("0")

            for tx in transactions:
                if tx.category == TransactionCategory.DEPOSIT:
                    total_deposits += tx.amount
                elif tx.category == TransactionCategory.WITHDRAWAL:
                    total_withdrawals += abs(tx.amount)
                elif tx.category == TransactionCategory.TRADE:
                    total_trades += tx.amount
                elif tx.category == TransactionCategory.FEE:
                    total_fees += abs(tx.amount)
                elif tx.category == TransactionCategory.PROFIT:
                    total_profit += tx.amount
                elif tx.category == TransactionCategory.LOSS:
                    total_loss += abs(tx.amount)

            net_profit = total_profit - total_loss
            initial_balance = account.balance - sum(t.amount for t in transactions)
            
            roi = (net_profit / initial_balance * 100) if initial_balance > 0 else 0

            summary = AccountSummary(
                account_id=account_id,
                user_id=account.user_id,
                total_balance=account.balance,
                total_available=account.available_balance,
                total_frozen=account.frozen_balance,
                total_deposits=total_deposits,
                total_withdrawals=total_withdrawals,
                total_trades=total_trades,
                total_fees=total_fees,
                total_profit=total_profit,
                total_loss=total_loss,
                net_profit=net_profit,
                roi_percentage=float(roi),
                transaction_count=len(transactions),
                period_start=period_start,
                period_end=now
            )

            self._summary_cache[account_id] = summary
            return summary

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du résumé: {e}")
            return AccountSummary(
                account_id=account_id,
                user_id=UUID("00000000-0000-0000-0000-000000000000"),
                total_balance=Decimal("0"),
                total_available=Decimal("0"),
                total_frozen=Decimal("0"),
                total_deposits=Decimal("0"),
                total_withdrawals=Decimal("0"),
                total_trades=Decimal("0"),
                total_fees=Decimal("0"),
                total_profit=Decimal("0"),
                total_loss=Decimal("0"),
                net_profit=Decimal("0"),
                roi_percentage=0.0,
                transaction_count=0,
                period_start=datetime.now(),
                period_end=datetime.now()
            )

    async def generate_report(
        self,
        user_id: UUID,
        report_type: str = "summary",
        period_days: int = 30,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Génère un rapport comptable.

        Args:
            user_id: ID de l'utilisateur
            report_type: Type de rapport (summary, detailed, performance)
            period_days: Période en jours
            format: Format de sortie (json, csv, excel)

        Returns:
            Rapport généré
        """
        try:
            accounts = await self.get_accounts(user_id)
            
            if report_type == "summary":
                report = await self._generate_summary_report(accounts, period_days)
            elif report_type == "detailed":
                report = await self._generate_detailed_report(accounts, period_days)
            elif report_type == "performance":
                report = await self._generate_performance_report(accounts, period_days)
            else:
                raise ValueError(f"Type de rapport non supporté: {report_type}")

            if format == "csv":
                return self._to_csv(report)
            elif format == "excel":
                return self._to_excel(report)
            else:
                return report

        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport: {e}")
            return {"error": str(e)}

    async def _generate_summary_report(
        self,
        accounts: List[Account],
        period_days: int
    ) -> Dict[str, Any]:
        """
        Génère un rapport résumé.

        Args:
            accounts: Liste des comptes
            period_days: Période en jours

        Returns:
            Rapport résumé
        """
        summaries = []
        total_balance = Decimal("0")
        total_profit = Decimal("0")
        total_fees = Decimal("0")

        for account in accounts:
            summary = await self.get_account_summary(account.account_id, period_days)
            summaries.append(summary.to_dict())
            total_balance += summary.total_balance
            total_profit += summary.net_profit
            total_fees += summary.total_fees

        return {
            "period_days": period_days,
            "generated_at": datetime.now().isoformat(),
            "total_balance": str(total_balance),
            "total_profit": str(total_profit),
            "total_fees": str(total_fees),
            "accounts": summaries
        }

    async def _generate_detailed_report(
        self,
        accounts: List[Account],
        period_days: int
    ) -> Dict[str, Any]:
        """
        Génère un rapport détaillé.

        Args:
            accounts: Liste des comptes
            period_days: Période en jours

        Returns:
            Rapport détaillé
        """
        report = await self._generate_summary_report(accounts, period_days)
        
        for account in accounts:
            transactions = await self.get_transactions(
                account.account_id,
                from_date=datetime.now() - timedelta(days=period_days)
            )
            
            for account_data in report["accounts"]:
                if UUID(account_data["account_id"]) == account.account_id:
                    account_data["transactions"] = [t.to_dict() for t in transactions]
                    break

        return report

    async def _generate_performance_report(
        self,
        accounts: List[Account],
        period_days: int
    ) -> Dict[str, Any]:
        """
        Génère un rapport de performance.

        Args:
            accounts: Liste des comptes
            period_days: Période en jours

        Returns:
            Rapport de performance
        """
        report = await self._generate_summary_report(accounts, period_days)
        
        # Ajout des métriques de performance
        performance_metrics = {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0
        }

        # Calcul des métriques (à implémenter avec les transactions)
        report["performance"] = performance_metrics

        return report

    # ========================================================================
    # FORMATAGE
    # ========================================================================

    def _to_csv(self, data: Dict[str, Any]) -> str:
        """
        Convertit des données en CSV.

        Args:
            data: Données à convertir

        Returns:
            CSV
        """
        try:
            df = pd.DataFrame(data)
            return df.to_csv(index=False)
        except Exception as e:
            logger.error(f"Erreur de conversion CSV: {e}")
            return ""

    def _to_excel(self, data: Dict[str, Any]) -> bytes:
        """
        Convertit des données en Excel.

        Args:
            data: Données à convertir

        Returns:
            Excel
        """
        try:
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()
        except Exception as e:
            logger.error(f"Erreur de conversion Excel: {e}")
            return b""

    # ========================================================================
    # STOCKAGE
    # ========================================================================

    async def _save_account(self, account: Account) -> None:
        """
        Sauvegarde un compte dans Redis.

        Args:
            account: Compte à sauvegarder
        """
        try:
            key = f"account:{account.account_id}"
            await self.redis.setex(
                key,
                86400 * 30,  # 30 jours
                json.dumps(account.to_dict())
            )
        except Exception as e:
            logger.error(f"Erreur de sauvegarde du compte: {e}")

    async def _load_account(self, account_id: UUID) -> Optional[Account]:
        """
        Charge un compte depuis Redis.

        Args:
            account_id: ID du compte

        Returns:
            Compte chargé
        """
        try:
            key = f"account:{account_id}"
            data = await self.redis.get(key)
            if data:
                account_dict = json.loads(data)
                return Account(
                    account_id=UUID(account_dict["account_id"]),
                    user_id=UUID(account_dict["user_id"]),
                    name=account_dict["name"],
                    account_type=AccountType(account_dict["account_type"]),
                    currency=account_dict["currency"],
                    balance=Decimal(account_dict["balance"]),
                    available_balance=Decimal(account_dict["available_balance"]),
                    frozen_balance=Decimal(account_dict["frozen_balance"]),
                    status=AccountStatus(account_dict["status"]),
                    created_at=datetime.fromisoformat(account_dict["created_at"]),
                    updated_at=datetime.fromisoformat(account_dict["updated_at"]),
                    metadata=account_dict.get("metadata", {})
                )
            return None

        except Exception as e:
            logger.error(f"Erreur de chargement du compte: {e}")
            return None

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
                "total_accounts": self._metrics["total_accounts"],
                "total_transactions": self._metrics["total_transactions"],
                "total_volume": str(self._metrics["total_volume"]),
                "total_fees": str(self._metrics["total_fees"]),
                "total_profit": str(self._metrics["total_profit"]),
                "by_category": self._metrics["by_category"],
                "last_transaction": self._metrics["last_transaction"],
                "cached_accounts": len(self._account_cache),
                "cached_transactions": len(self._transaction_cache),
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
        logger.info("Fermeture de AccountingManager...")
        self._account_cache.clear()
        self._transaction_cache.clear()
        self._summary_cache.clear()
        logger.info("AccountingManager fermé")


# ============================================================================
# MODÈLES SQLALCHEMY
# ============================================================================

class AccountModel(Base):
    """Modèle SQLAlchemy pour les comptes."""
    __tablename__ = "accounts"

    account_id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=False)
    currency = Column(String(10), nullable=False)
    balance = Column(Numeric(20, 8), nullable=False, default=0)
    available_balance = Column(Numeric(20, 8), nullable=False, default=0)
    frozen_balance = Column(Numeric(20, 8), nullable=False, default=0)
    status = Column(String(20), nullable=False)
    metadata = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class TransactionModel(Base):
    """Modèle SQLAlchemy pour les transactions."""
    __tablename__ = "transactions"

    transaction_id = Column(String(36), primary_key=True)
    account_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    category = Column(String(50), nullable=False)
    amount = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False)
    balance_before = Column(Numeric(20, 8), nullable=False)
    balance_after = Column(Numeric(20, 8), nullable=False)
    description = Column(String(500), nullable=True)
    reference_id = Column(String(36), nullable=True)
    reference_type = Column(String(50), nullable=True)
    metadata = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_accounting_manager(
    database_url: Optional[str] = None,
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> AccountingManager:
    """
    Crée une instance de AccountingManager.

    Args:
        database_url: URL de la base de données
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance de AccountingManager
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return AccountingManager(
        database_url=database_url,
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "AccountType",
    "AccountStatus",
    "TransactionCategory",
    "Account",
    "Transaction",
    "AccountSummary",
    "AccountingManager",
    "create_accounting_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire comptable."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT ACCOUNTING MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    accounting = create_accounting_manager()

    print(f"\n✅ AccountingManager initialisé")

    # Création d'un compte
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    
    print(f"\n📊 Création d'un compte...")
    account = await accounting.create_account(
        user_id=user_id,
        name="Main Trading Account",
        account_type=AccountType.TRADING,
        currency="USD",
        initial_balance=Decimal("10000")
    )

    print(f"   ID: {account.account_id}")
    print(f"   Nom: {account.name}")
    print(f"   Solde: {account.balance} {account.currency}")

    # Ajout de transactions
    print(f"\n💸 Ajout de transactions...")
    
    # Dépôt
    tx1 = await accounting.add_transaction(
        account_id=account.account_id,
        user_id=user_id,
        category=TransactionCategory.DEPOSIT,
        amount=Decimal("5000"),
        description="Dépôt initial"
    )
    print(f"   Dépôt: {tx1.amount} {tx1.currency}")

    # Transaction de trading
    tx2 = await accounting.add_transaction(
        account_id=account.account_id,
        user_id=user_id,
        category=TransactionCategory.TRADE,
        amount=Decimal("1500"),
        description="Trade BTC/USDT"
    )
    print(f"   Trade: {tx2.amount} {tx2.currency}")

    # Frais
    tx3 = await accounting.add_transaction(
        account_id=account.account_id,
        user_id=user_id,
        category=TransactionCategory.FEE,
        amount=Decimal("-15"),
        description="Frais de trading"
    )
    print(f"   Frais: {tx3.amount} {tx3.currency}")

    # Profit
    tx4 = await accounting.add_transaction(
        account_id=account.account_id,
        user_id=user_id,
        category=TransactionCategory.PROFIT,
        amount=Decimal("500"),
        description="Profit réalisé"
    )
    print(f"   Profit: {tx4.amount} {tx4.currency}")

    # Récupération du solde
    updated_account = await accounting.get_account(account.account_id)
    print(f"\n💰 Solde final: {updated_account.balance} {updated_account.currency}")

    # Résumé du compte
    print(f"\n📈 Résumé du compte (30 jours):")
    summary = await accounting.get_account_summary(account.account_id)
    print(f"   Solde total: {summary.total_balance} {account.currency}")
    print(f"   Dépôts: {summary.total_deposits} {account.currency}")
    print(f"   Retraits: {summary.total_withdrawals} {account.currency}")
    print(f"   Profit net: {summary.net_profit} {account.currency}")
    print(f"   ROI: {summary.roi_percentage:.2f}%")
    print(f"   Transactions: {summary.transaction_count}")

    # Transactions
    print(f"\n📋 Dernières transactions:")
    transactions = await accounting.get_transactions(account.account_id, limit=5)
    for tx in transactions:
        print(f"   {tx.created_at.strftime('%Y-%m-%d %H:%M')}: {tx.category.value} - {tx.amount} {tx.currency}")

    # Santé du service
    health = await accounting.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Comptes: {health['total_accounts']}")
    print(f"   Transactions: {health['total_transactions']}")
    print(f"   Volume total: ${health['total_volume']}")

    # Fermeture
    await accounting.close()

    print("\n" + "=" * 60)
    print("AccountingManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import io
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
