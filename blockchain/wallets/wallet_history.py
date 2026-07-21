"""
NEXUS AI TRADING SYSTEM - WALLET HISTORY MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion de l'historique des transactions pour wallets multi-blockchain.
Support du suivi, filtrage, analyse et export des transactions.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import csv
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import aiofiles
import pandas as pd
from web3 import Web3

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class HistoryFilter(Enum):
    """Filtres pour l'historique."""
    ALL = "all"
    SENT = "sent"
    RECEIVED = "received"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    STAKING = "staking"
    SWAP = "swap"
    BRIDGE = "bridge"
    APPROVAL = "approval"
    DEPLOY = "deploy"


class HistorySort(Enum):
    """Tris pour l'historique."""
    NEWEST = "newest"
    OLDEST = "oldest"
    HIGHEST_AMOUNT = "highest_amount"
    LOWEST_AMOUNT = "lowest_amount"
    HIGHEST_FEE = "highest_fee"
    LOWEST_FEE = "lowest_fee"


@dataclass
class TransactionSummary:
    """Résumé d'une transaction."""
    tx_hash: str
    chain: str
    network: str
    type: TransactionType
    from_address: str
    to_address: str
    amount: Decimal
    amount_usd: Decimal
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    fee: Decimal = Decimal("0")
    fee_usd: Decimal = Decimal("0")
    status: TransactionStatus = TransactionStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.now)
    block_number: Optional[int] = None
    confirmations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "tx_hash": self.tx_hash,
            "chain": self.chain,
            "network": self.network,
            "type": self.type.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "token_symbol": self.token_symbol,
            "token_address": self.token_address,
            "fee": str(self.fee),
            "fee_usd": str(self.fee_usd),
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "block_number": self.block_number,
            "confirmations": self.confirmations,
            "metadata": self.metadata
        }


@dataclass
class TransactionGroup:
    """Groupe de transactions."""
    group_id: UUID
    name: str
    transactions: List[TransactionSummary]
    total_amount: Decimal
    total_amount_usd: Decimal
    total_fees: Decimal
    total_fees_usd: Decimal
    count: int
    start_date: datetime
    end_date: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "group_id": str(self.group_id),
            "name": self.name,
            "transactions": [t.to_dict() for t in self.transactions],
            "total_amount": str(self.total_amount),
            "total_amount_usd": str(self.total_amount_usd),
            "total_fees": str(self.total_fees),
            "total_fees_usd": str(self.total_fees_usd),
            "count": self.count,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class HistoryStats:
    """Statistiques d'historique."""
    total_transactions: int
    total_sent: Decimal
    total_sent_usd: Decimal
    total_received: Decimal
    total_received_usd: Decimal
    total_fees: Decimal
    total_fees_usd: Decimal
    net_flow: Decimal
    net_flow_usd: Decimal
    average_tx_value: Decimal
    average_tx_value_usd: Decimal
    largest_tx: Decimal
    largest_tx_usd: Decimal
    most_active_day: datetime
    daily_average: Decimal
    daily_average_usd: Decimal
    by_type: Dict[str, Dict]
    by_day: List[Dict]
    by_token: Dict[str, Dict]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "total_transactions": self.total_transactions,
            "total_sent": str(self.total_sent),
            "total_sent_usd": str(self.total_sent_usd),
            "total_received": str(self.total_received),
            "total_received_usd": str(self.total_received_usd),
            "total_fees": str(self.total_fees),
            "total_fees_usd": str(self.total_fees_usd),
            "net_flow": str(self.net_flow),
            "net_flow_usd": str(self.net_flow_usd),
            "average_tx_value": str(self.average_tx_value),
            "average_tx_value_usd": str(self.average_tx_value_usd),
            "largest_tx": str(self.largest_tx),
            "largest_tx_usd": str(self.largest_tx_usd),
            "most_active_day": self.most_active_day.isoformat(),
            "daily_average": str(self.daily_average),
            "daily_average_usd": str(self.daily_average_usd),
            "by_type": self.by_type,
            "by_day": self.by_day,
            "by_token": self.by_token,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET HISTORY SERVICE
# ============================================================================

class WalletHistoryService:
    """
    Service de gestion de l'historique des transactions.
    """

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service d'historique.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._transaction_cache: Dict[str, TransactionSummary] = {}
        self._history_cache: Dict[UUID, List[TransactionSummary]] = {}
        self._group_cache: Dict[UUID, TransactionGroup] = {}
        self._stats_cache: Dict[UUID, HistoryStats] = {}
        
        # Métriques
        self._metrics = {
            "total_transactions_indexed": 0,
            "total_groups_created": 0,
            "last_index": None,
            "last_export": None
        }

        logger.info("WalletHistoryService initialisé avec succès")

    # ========================================================================
    # INDEXATION DES TRANSACTIONS
    # ========================================================================

    async def index_transaction(
        self,
        wallet: BaseWallet,
        tx: Transaction
    ) -> TransactionSummary:
        """
        Indexe une transaction dans l'historique.

        Args:
            wallet: Wallet
            tx: Transaction à indexer

        Returns:
            Résumé de la transaction
        """
        try:
            # Création du résumé
            summary = TransactionSummary(
                tx_hash=tx.tx_hash or "",
                chain=wallet.config.blockchain,
                network=wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                type=tx.tx_type,
                from_address=tx.from_address,
                to_address=tx.to_address,
                amount=tx.amount,
                amount_usd=tx.amount_usd,
                token_symbol=tx.token_symbol,
                token_address=tx.token_address,
                fee=Decimal(str(tx.gas_used or 0)) * (tx.gas_price or Decimal("0")),
                fee_usd=Decimal("0"),  # À calculer avec le prix
                status=tx.status,
                timestamp=tx.timestamp,
                block_number=tx.block_number,
                confirmations=tx.confirmations,
                metadata=tx.metadata
            )

            # Calcul du fee en USD
            if tx.gas_price and tx.gas_used:
                fee_amount = Decimal(str(tx.gas_used)) * tx.gas_price
                summary.fee = fee_amount
                
                # Estimation du prix du token natif
                try:
                    native_price = await self._get_native_price(wallet.config.blockchain)
                    summary.fee_usd = fee_amount * Decimal(str(native_price))
                except Exception:
                    summary.fee_usd = Decimal("0")

            # Mise en cache
            cache_key = f"{wallet.config.wallet_id}:{tx.tx_hash}"
            self._transaction_cache[cache_key] = summary
            
            # Ajout à l'historique du wallet
            if wallet.config.wallet_id not in self._history_cache:
                self._history_cache[wallet.config.wallet_id] = []
            
            self._history_cache[wallet.config.wallet_id].append(summary)
            
            # Mise à jour des métriques
            self._metrics["total_transactions_indexed"] += 1
            self._metrics["last_index"] = datetime.now().isoformat()

            return summary

        except Exception as e:
            logger.error(f"Erreur lors de l'indexation de la transaction: {e}")
            raise

    async def index_transactions(
        self,
        wallet: BaseWallet,
        transactions: List[Transaction]
    ) -> List[TransactionSummary]:
        """
        Indexe plusieurs transactions.

        Args:
            wallet: Wallet
            transactions: Liste des transactions

        Returns:
            Liste des résumés
        """
        summaries = []
        for tx in transactions:
            try:
                summary = await self.index_transaction(wallet, tx)
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Erreur lors de l'indexation: {e}")
        
        return summaries

    # ========================================================================
    # RÉCUPÉRATION DE L'HISTORIQUE
    # ========================================================================

    async def get_history(
        self,
        wallet_id: UUID,
        filter_type: Optional[HistoryFilter] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        token_address: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort: HistorySort = HistorySort.NEWEST
    ) -> List[TransactionSummary]:
        """
        Récupère l'historique des transactions.

        Args:
            wallet_id: ID du wallet
            filter_type: Filtre de type
            from_date: Date de début
            to_date: Date de fin
            token_address: Filtre par token
            limit: Nombre de transactions
            offset: Décalage
            sort: Tri

        Returns:
            Liste des résumés de transactions
        """
        try:
            # Récupération de l'historique
            history = self._history_cache.get(wallet_id, [])
            
            # Filtrage
            if filter_type and filter_type != HistoryFilter.ALL:
                if filter_type == HistoryFilter.SENT:
                    history = [t for t in history if t.type == TransactionType.SEND]
                elif filter_type == HistoryFilter.RECEIVED:
                    history = [t for t in history if t.type == TransactionType.RECEIVE]
                elif filter_type == HistoryFilter.PENDING:
                    history = [t for t in history if t.status == TransactionStatus.PENDING]
                elif filter_type == HistoryFilter.CONFIRMED:
                    history = [t for t in history if t.status == TransactionStatus.CONFIRMED]
                elif filter_type == HistoryFilter.FAILED:
                    history = [t for t in history if t.status == TransactionStatus.FAILED]
                elif filter_type == HistoryFilter.STAKING:
                    history = [t for t in history if t.type == TransactionType.STAKING]
                elif filter_type == HistoryFilter.SWAP:
                    history = [t for t in history if t.type == TransactionType.SWAP]
                elif filter_type == HistoryFilter.BRIDGE:
                    history = [t for t in history if t.type == TransactionType.BRIDGE]
                elif filter_type == HistoryFilter.APPROVAL:
                    history = [t for t in history if t.type == TransactionType.APPROVAL]
                elif filter_type == HistoryFilter.DEPLOY:
                    history = [t for t in history if t.type == TransactionType.DEPLOY]

            # Filtrage par date
            if from_date:
                history = [t for t in history if t.timestamp >= from_date]
            if to_date:
                history = [t for t in history if t.timestamp <= to_date]

            # Filtrage par token
            if token_address:
                history = [t for t in history if t.token_address == token_address]

            # Tri
            if sort == HistorySort.NEWEST:
                history.sort(key=lambda x: x.timestamp, reverse=True)
            elif sort == HistorySort.OLDEST:
                history.sort(key=lambda x: x.timestamp)
            elif sort == HistorySort.HIGHEST_AMOUNT:
                history.sort(key=lambda x: x.amount, reverse=True)
            elif sort == HistorySort.LOWEST_AMOUNT:
                history.sort(key=lambda x: x.amount)
            elif sort == HistorySort.HIGHEST_FEE:
                history.sort(key=lambda x: x.fee, reverse=True)
            elif sort == HistorySort.LOWEST_FEE:
                history.sort(key=lambda x: x.fee)

            # Pagination
            return history[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []

    async def get_transaction(
        self,
        wallet_id: UUID,
        tx_hash: str
    ) -> Optional[TransactionSummary]:
        """
        Récupère une transaction par son hash.

        Args:
            wallet_id: ID du wallet
            tx_hash: Hash de la transaction

        Returns:
            Résumé de la transaction
        """
        try:
            cache_key = f"{wallet_id}:{tx_hash}"
            return self._transaction_cache.get(cache_key)

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la transaction: {e}")
            return None

    # ========================================================================
    # ANALYSE DE L'HISTORIQUE
    # ========================================================================

    async def get_stats(
        self,
        wallet_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> HistoryStats:
        """
        Récupère les statistiques de l'historique.

        Args:
            wallet_id: ID du wallet
            from_date: Date de début
            to_date: Date de fin

        Returns:
            Statistiques de l'historique
        """
        try:
            # Récupération de l'historique
            history = await self.get_history(
                wallet_id,
                from_date=from_date,
                to_date=to_date,
                limit=999999
            )

            if not history:
                return HistoryStats(
                    total_transactions=0,
                    total_sent=Decimal("0"),
                    total_sent_usd=Decimal("0"),
                    total_received=Decimal("0"),
                    total_received_usd=Decimal("0"),
                    total_fees=Decimal("0"),
                    total_fees_usd=Decimal("0"),
                    net_flow=Decimal("0"),
                    net_flow_usd=Decimal("0"),
                    average_tx_value=Decimal("0"),
                    average_tx_value_usd=Decimal("0"),
                    largest_tx=Decimal("0"),
                    largest_tx_usd=Decimal("0"),
                    most_active_day=datetime.now(),
                    daily_average=Decimal("0"),
                    daily_average_usd=Decimal("0"),
                    by_type={},
                    by_day=[],
                    by_token={}
                )

            # Calcul des statistiques
            total_sent = sum(t.amount for t in history if t.type == TransactionType.SEND)
            total_received = sum(t.amount for t in history if t.type == TransactionType.RECEIVE)
            total_sent_usd = sum(t.amount_usd for t in history if t.type == TransactionType.SEND)
            total_received_usd = sum(t.amount_usd for t in history if t.type == TransactionType.RECEIVE)
            total_fees = sum(t.fee for t in history)
            total_fees_usd = sum(t.fee_usd for t in history)
            
            net_flow = total_received - total_sent
            net_flow_usd = total_received_usd - total_sent_usd

            # Par type
            by_type = {}
            for tx_type in TransactionType:
                type_txs = [t for t in history if t.type == tx_type]
                if type_txs:
                    by_type[tx_type.value] = {
                        "count": len(type_txs),
                        "total_amount": str(sum(t.amount for t in type_txs)),
                        "total_amount_usd": str(sum(t.amount_usd for t in type_txs)),
                        "total_fees": str(sum(t.fee for t in type_txs)),
                        "total_fees_usd": str(sum(t.fee_usd for t in type_txs))
                    }

            # Par jour
            by_day = []
            days = {}
            for tx in history:
                day_key = tx.timestamp.date().isoformat()
                if day_key not in days:
                    days[day_key] = []
                days[day_key].append(tx)
            
            for day, txs in days.items():
                by_day.append({
                    "date": day,
                    "count": len(txs),
                    "total_amount": str(sum(t.amount for t in txs)),
                    "total_amount_usd": str(sum(t.amount_usd for t in txs)),
                    "total_fees": str(sum(t.fee for t in txs))
                })

            # Par token
            by_token = {}
            for tx in history:
                if tx.token_symbol:
                    if tx.token_symbol not in by_token:
                        by_token[tx.token_symbol] = {
                            "count": 0,
                            "total_amount": Decimal("0"),
                            "total_amount_usd": Decimal("0")
                        }
                    by_token[tx.token_symbol]["count"] += 1
                    by_token[tx.token_symbol]["total_amount"] += tx.amount
                    by_token[tx.token_symbol]["total_amount_usd"] += tx.amount_usd

            # Conversion en str pour le dictionnaire
            by_token = {
                k: {
                    "count": v["count"],
                    "total_amount": str(v["total_amount"]),
                    "total_amount_usd": str(v["total_amount_usd"])
                }
                for k, v in by_token.items()
            }

            # Plus grand montant
            largest_tx = max((t.amount for t in history), default=Decimal("0"))
            largest_tx_usd = max((t.amount_usd for t in history), default=Decimal("0"))

            # Jour le plus actif
            most_active_day = max(days.keys(), key=lambda d: len(days[d])) if days else datetime.now()
            most_active_day = datetime.fromisoformat(most_active_day) if isinstance(most_active_day, str) else most_active_day

            # Moyennes
            avg_tx_value = sum(t.amount for t in history) / len(history) if history else Decimal("0")
            avg_tx_value_usd = sum(t.amount_usd for t in history) / len(history) if history else Decimal("0")
            
            # Moyenne quotidienne
            days_count = len(days) if days else 1
            daily_average = sum(t.amount for t in history) / days_count
            daily_average_usd = sum(t.amount_usd for t in history) / days_count

            return HistoryStats(
                total_transactions=len(history),
                total_sent=total_sent,
                total_sent_usd=total_sent_usd,
                total_received=total_received,
                total_received_usd=total_received_usd,
                total_fees=total_fees,
                total_fees_usd=total_fees_usd,
                net_flow=net_flow,
                net_flow_usd=net_flow_usd,
                average_tx_value=avg_tx_value,
                average_tx_value_usd=avg_tx_value_usd,
                largest_tx=largest_tx,
                largest_tx_usd=largest_tx_usd,
                most_active_day=most_active_day,
                daily_average=daily_average,
                daily_average_usd=daily_average_usd,
                by_type=by_type,
                by_day=by_day,
                by_token=by_token
            )

        except Exception as e:
            logger.error(f"Erreur lors du calcul des statistiques: {e}")
            return HistoryStats(
                total_transactions=0,
                total_sent=Decimal("0"),
                total_sent_usd=Decimal("0"),
                total_received=Decimal("0"),
                total_received_usd=Decimal("0"),
                total_fees=Decimal("0"),
                total_fees_usd=Decimal("0"),
                net_flow=Decimal("0"),
                net_flow_usd=Decimal("0"),
                average_tx_value=Decimal("0"),
                average_tx_value_usd=Decimal("0"),
                largest_tx=Decimal("0"),
                largest_tx_usd=Decimal("0"),
                most_active_day=datetime.now(),
                daily_average=Decimal("0"),
                daily_average_usd=Decimal("0"),
                by_type={},
                by_day=[],
                by_token={}
            )

    # ========================================================================
    # GROUPES DE TRANSACTIONS
    # ========================================================================

    async def create_group(
        self,
        wallet_id: UUID,
        name: str,
        transaction_hashes: List[str],
        metadata: Optional[Dict] = None
    ) -> TransactionGroup:
        """
        Crée un groupe de transactions.

        Args:
            wallet_id: ID du wallet
            name: Nom du groupe
            transaction_hashes: Liste des hashs de transactions
            metadata: Métadonnées

        Returns:
            Groupe de transactions
        """
        try:
            transactions = []
            total_amount = Decimal("0")
            total_amount_usd = Decimal("0")
            total_fees = Decimal("0")
            total_fees_usd = Decimal("0")

            for tx_hash in transaction_hashes:
                tx = await self.get_transaction(wallet_id, tx_hash)
                if tx:
                    transactions.append(tx)
                    total_amount += tx.amount
                    total_amount_usd += tx.amount_usd
                    total_fees += tx.fee
                    total_fees_usd += tx.fee_usd

            if not transactions:
                raise ValueError("Aucune transaction trouvée")

            group = TransactionGroup(
                group_id=uuid4(),
                name=name,
                transactions=transactions,
                total_amount=total_amount,
                total_amount_usd=total_amount_usd,
                total_fees=total_fees,
                total_fees_usd=total_fees_usd,
                count=len(transactions),
                start_date=min(t.timestamp for t in transactions),
                end_date=max(t.timestamp for t in transactions),
                metadata=metadata or {}
            )

            self._group_cache[group.group_id] = group
            self._metrics["total_groups_created"] += 1

            return group

        except Exception as e:
            logger.error(f"Erreur lors de la création du groupe: {e}")
            raise

    async def get_group(
        self,
        group_id: UUID
    ) -> Optional[TransactionGroup]:
        """
        Récupère un groupe de transactions.

        Args:
            group_id: ID du groupe

        Returns:
            Groupe de transactions
        """
        return self._group_cache.get(group_id)

    async def get_groups(
        self,
        wallet_id: UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[TransactionGroup]:
        """
        Récupère les groupes d'un wallet.

        Args:
            wallet_id: ID du wallet
            limit: Nombre de groupes
            offset: Décalage

        Returns:
            Liste des groupes
        """
        groups = [
            g for g in self._group_cache.values()
            if any(t.tx_hash in g.transactions[0].tx_hash for t in g.transactions)
        ]
        return groups[offset:offset + limit]

    # ========================================================================
    # EXPORT DE L'HISTORIQUE
    # ========================================================================

    async def export_history(
        self,
        wallet_id: UUID,
        format: str = "csv",
        filter_type: Optional[HistoryFilter] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        token_address: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Union[str, Dict]:
        """
        Exporte l'historique des transactions.

        Args:
            wallet_id: ID du wallet
            format: Format d'export (csv, json, excel)
            filter_type: Filtre de type
            from_date: Date de début
            to_date: Date de fin
            token_address: Filtre par token
            file_path: Chemin du fichier (optionnel)

        Returns:
            Données exportées ou chemin du fichier
        """
        try:
            # Récupération de l'historique
            history = await self.get_history(
                wallet_id,
                filter_type=filter_type,
                from_date=from_date,
                to_date=to_date,
                token_address=token_address,
                limit=999999
            )

            if not history:
                return {"error": "Aucune transaction trouvée"}

            # Conversion en dictionnaires
            data = [t.to_dict() for t in history]

            # Export selon le format
            if format == "csv":
                if file_path:
                    await self._export_csv(data, file_path)
                    return file_path
                return data

            elif format == "json":
                if file_path:
                    await self._export_json(data, file_path)
                    return file_path
                return data

            elif format == "excel":
                if file_path:
                    await self._export_excel(data, file_path)
                    return file_path
                return data

            else:
                raise ValueError(f"Format non supporté: {format}")

        except Exception as e:
            logger.error(f"Erreur lors de l'export: {e}")
            return {"error": str(e)}

    async def _export_csv(self, data: List[Dict], file_path: str) -> None:
        """
        Exporte en CSV.

        Args:
            data: Données à exporter
            file_path: Chemin du fichier
        """
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            df.to_csv(file_path, index=False)
            self._metrics["last_export"] = datetime.now().isoformat()
            logger.info(f"Export CSV: {file_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'export CSV: {e}")
            raise

    async def _export_json(self, data: List[Dict], file_path: str) -> None:
        """
        Exporte en JSON.

        Args:
            data: Données à exporter
            file_path: Chemin du fichier
        """
        try:
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(json.dumps(data, indent=2))
            self._metrics["last_export"] = datetime.now().isoformat()
            logger.info(f"Export JSON: {file_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'export JSON: {e}")
            raise

    async def _export_excel(self, data: List[Dict], file_path: str) -> None:
        """
        Exporte en Excel.

        Args:
            data: Données à exporter
            file_path: Chemin du fichier
        """
        try:
            import pandas as pd
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
            self._metrics["last_export"] = datetime.now().isoformat()
            logger.info(f"Export Excel: {file_path}")

        except Exception as e:
            logger.error(f"Erreur lors de l'export Excel: {e}")
            raise

    # ========================================================================
    # MÉTHODES PRIVÉES
    # ========================================================================

    async def _get_native_price(self, blockchain: str) -> float:
        """
        Récupère le prix du token natif.

        Args:
            blockchain: Blockchain

        Returns:
            Prix en USD
        """
        try:
            symbol_map = {
                "ethereum": "ethereum",
                "bsc": "binancecoin",
                "polygon": "polygon",
                "solana": "solana",
                "avalanche": "avalanche-2",
                "tron": "tron",
                "arbitrum": "arbitrum",
                "optimism": "optimism"
            }
            
            symbol = symbol_map.get(blockchain, "ethereum")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price",
                    params={
                        "ids": symbol,
                        "vs_currencies": "usd"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get(symbol, {}).get("usd", 0)
            
            return 0

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix: {e}")
            return 0

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
                "total_transactions_indexed": self._metrics["total_transactions_indexed"],
                "total_groups_created": self._metrics["total_groups_created"],
                "last_index": self._metrics["last_index"],
                "last_export": self._metrics["last_export"],
                "cached_transactions": len(self._transaction_cache),
                "cached_history": len(self._history_cache),
                "cached_groups": len(self._group_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def clear_history(
        self,
        wallet_id: UUID,
        older_than: Optional[datetime] = None
    ) -> int:
        """
        Nettoie l'historique d'un wallet.

        Args:
            wallet_id: ID du wallet
            older_than: Supprimer les transactions plus anciennes

        Returns:
            Nombre de transactions supprimées
        """
        try:
            history = self._history_cache.get(wallet_id, [])
            initial_count = len(history)

            if older_than:
                history = [t for t in history if t.timestamp >= older_than]
            else:
                history = []

            self._history_cache[wallet_id] = history
            removed = initial_count - len(history)

            logger.info(f"Historique nettoyé pour {wallet_id}: {removed} transactions supprimées")
            return removed

        except Exception as e:
            logger.error(f"Erreur lors du nettoyage de l'historique: {e}")
            return 0

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de WalletHistoryService...")
        self._transaction_cache.clear()
        self._history_cache.clear()
        self._group_cache.clear()
        self._stats_cache.clear()
        logger.info("WalletHistoryService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_history_service(
    api_keys: Optional[Dict[str, str]] = None,
    redis_url: str = "redis://localhost:6379/0"
) -> WalletHistoryService:
    """
    Crée une instance du service d'historique.

    Args:
        api_keys: Clés API pour les services externes
        redis_url: URL de connexion Redis

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletHistoryService(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "HistoryFilter",
    "HistorySort",
    "TransactionSummary",
    "TransactionGroup",
    "HistoryStats",
    "WalletHistoryService",
    "create_wallet_history_service"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service d'historique."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET HISTORY MODULE")
    print("=" * 60)

    # Création du service
    history_service = create_wallet_history_service()

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="History Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Indexation des transactions (simulées)
    print(f"\n📝 Indexation des transactions...")
    
    # Simulation de transactions
    for i in range(10):
        tx = Transaction(
            tx_id=uuid4(),
            wallet_id=wallet.config.wallet_id,
            user_id=user_id,
            blockchain="ethereum",
            network=BlockchainNetwork.ETHEREUM_MAINNET,
            tx_type=TransactionType.SEND if i % 2 == 0 else TransactionType.RECEIVE,
            from_address=wallet.config.address,
            to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            amount=Decimal(str(0.1 * (i + 1))),
            amount_usd=Decimal(str(30 * (i + 1))),
            tx_hash=hashlib.sha256(f"tx_{i}".encode()).hexdigest()[:66],
            status=TransactionStatus.CONFIRMED if i % 3 != 0 else TransactionStatus.PENDING,
            gas_used=21000 + i * 1000,
            gas_price=Decimal("30"),
            gas_currency="ETH",
            timestamp=datetime.now() - timedelta(days=i)
        )
        await history_service.index_transaction(wallet, tx)

    print(f"   {10} transactions indexées")

    # Récupération de l'historique
    history = await history_service.get_history(
        wallet.config.wallet_id,
        limit=5,
        sort=HistorySort.NEWEST
    )
    
    print(f"\n📋 Historique des transactions:")
    for tx in history[:5]:
        print(f"   [{tx.timestamp.strftime('%Y-%m-%d %H:%M')}] {tx.type.value.upper()}: "
              f"{tx.amount:.4f} ETH (${tx.amount_usd:.2f})")

    # Statistiques
    stats = await history_service.get_stats(wallet.config.wallet_id)
    
    print(f"\n📊 Statistiques:")
    print(f"   Total transactions: {stats.total_transactions}")
    print(f"   Total envoyé: {stats.total_sent:.4f} ETH (${stats.total_sent_usd:.2f})")
    print(f"   Total reçu: {stats.total_received:.4f} ETH (${stats.total_received_usd:.2f})")
    print(f"   Total frais: {stats.total_fees:.6f} ETH (${stats.total_fees_usd:.2f})")
    print(f"   Net flow: {stats.net_flow:.4f} ETH (${stats.net_flow_usd:.2f})")

    # Par type
    print(f"\n📈 Par type:")
    for tx_type, data in stats.by_type.items():
        print(f"   {tx_type}: {data['count']} transactions")

    # Export CSV
    csv_file = "./history_export.csv"
    result = await history_service.export_history(
        wallet.config.wallet_id,
        format="csv",
        file_path=csv_file
    )
    print(f"\n💾 Export CSV: {result}")

    # Santé du service
    health = await history_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Transactions indexées: {health['total_transactions_indexed']}")
    print(f"   Groupes créés: {health['total_groups_created']}")
    print(f"   Historique en cache: {len(health.get('cached_history', {}))} wallets")

    # Fermeture
    await history_service.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletHistoryService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import hashlib
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
