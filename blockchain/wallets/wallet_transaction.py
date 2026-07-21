"""
NEXUS AI TRADING SYSTEM - WALLET TRANSACTION MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des transactions pour wallets multi-blockchain.
Support de la création, suivi, annulation, et analyse des transactions.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
from web3 import Web3
from web3.auto import w3
from eth_account import Account

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

class TransactionPriority(Enum):
    """Priorités de transaction."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TransactionCategory(Enum):
    """Catégories de transaction."""
    TRANSFER = "transfer"
    SWAP = "swap"
    STAKING = "staking"
    UNSTAKING = "unstaking"
    CLAIM_REWARDS = "claim_rewards"
    APPROVAL = "approval"
    DEPLOY = "deploy"
    BRIDGE = "bridge"
    MULTISIG = "multisig"
    OTHER = "other"


@dataclass
class TransactionBuilder:
    """Constructeur de transaction."""
    tx_id: UUID
    wallet_id: UUID
    user_id: UUID
    chain: str
    network: str
    from_address: str
    to_address: str
    amount: Decimal
    amount_usd: Decimal
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    tx_type: TransactionType = TransactionType.SEND
    category: TransactionCategory = TransactionCategory.TRANSFER
    priority: TransactionPriority = TransactionPriority.MEDIUM
    gas_price: Optional[Decimal] = None
    gas_limit: Optional[int] = None
    max_gas_price: Optional[Decimal] = None
    max_fee_per_gas: Optional[Decimal] = None
    data: Optional[str] = None
    nonce: Optional[int] = None
    deadline: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "tx_id": str(self.tx_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "chain": self.chain,
            "network": self.network,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "amount": str(self.amount),
            "amount_usd": str(self.amount_usd),
            "token_address": self.token_address,
            "token_symbol": self.token_symbol,
            "tx_type": self.tx_type.value,
            "category": self.category.value,
            "priority": self.priority.value,
            "gas_price": str(self.gas_price) if self.gas_price else None,
            "gas_limit": self.gas_limit,
            "max_gas_price": str(self.max_gas_price) if self.max_gas_price else None,
            "max_fee_per_gas": str(self.max_fee_per_gas) if self.max_fee_per_gas else None,
            "data": self.data,
            "nonce": self.nonce,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class TransactionReceipt:
    """Reçu de transaction."""
    tx_hash: str
    wallet_id: UUID
    user_id: UUID
    chain: str
    network: str
    status: TransactionStatus
    block_number: Optional[int] = None
    block_hash: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[Decimal] = None
    effective_gas_price: Optional[Decimal] = None
    cumulative_gas_used: Optional[int] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)
    logs_bloom: Optional[str] = None
    contract_address: Optional[str] = None
    transaction_index: Optional[int] = None
    confirmations: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "tx_hash": self.tx_hash,
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "chain": self.chain,
            "network": self.network,
            "status": self.status.value,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "gas_used": self.gas_used,
            "gas_price": str(self.gas_price) if self.gas_price else None,
            "effective_gas_price": str(self.effective_gas_price) if self.effective_gas_price else None,
            "cumulative_gas_used": self.cumulative_gas_used,
            "logs": self.logs,
            "logs_bloom": self.logs_bloom,
            "contract_address": self.contract_address,
            "transaction_index": self.transaction_index,
            "confirmations": self.confirmations,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class TransactionBatch:
    """Lot de transactions."""
    batch_id: UUID
    wallet_id: UUID
    user_id: UUID
    chain: str
    network: str
    transactions: List[TransactionBuilder]
    status: str = "pending"  # pending, processing, completed, failed
    total_amount: Decimal = Decimal("0")
    total_amount_usd: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")
    total_fees_usd: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "batch_id": str(self.batch_id),
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "chain": self.chain,
            "network": self.network,
            "transactions": [t.to_dict() for t in self.transactions],
            "status": self.status,
            "total_amount": str(self.total_amount),
            "total_amount_usd": str(self.total_amount_usd),
            "total_fees": str(self.total_fees),
            "total_fees_usd": str(self.total_fees_usd),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE WALLET TRANSACTION SERVICE
# ============================================================================

class WalletTransactionService:
    """
    Service de gestion des transactions multi-blockchain.
    """

    # Seuils de gas par blockchain
    GAS_THRESHOLDS = {
        "ethereum": {"low": 20, "medium": 50, "high": 100, "urgent": 200},
        "bsc": {"low": 3, "medium": 5, "high": 10, "urgent": 20},
        "polygon": {"low": 30, "medium": 50, "high": 100, "urgent": 200},
        "avalanche": {"low": 25, "medium": 50, "high": 100, "urgent": 200},
        "arbitrum": {"low": 0.1, "medium": 0.5, "high": 1, "urgent": 2},
        "optimism": {"low": 0.1, "medium": 0.5, "high": 1, "urgent": 2},
        "solana": {"low": 0.000005, "medium": 0.00001, "high": 0.00005, "urgent": 0.0001},
        "tron": {"low": 0.00001, "medium": 0.00002, "high": 0.00005, "urgent": 0.0001}
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de transactions.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Cache
        self._transaction_cache: Dict[str, TransactionReceipt] = {}
        self._batch_cache: Dict[UUID, TransactionBatch] = {}
        self._pending_transactions: Dict[str, TransactionBuilder] = {}
        
        # Métriques
        self._metrics = {
            "total_transactions": 0,
            "total_batches": 0,
            "total_failed": 0,
            "total_completed": 0,
            "total_volume_usd": Decimal("0"),
            "total_fees_usd": Decimal("0"),
            "by_type": {},
            "by_category": {},
            "by_status": {},
            "last_transaction": None
        }

        logger.info("WalletTransactionService initialisé avec succès")

    # ========================================================================
    # CRÉATION DE TRANSACTIONS
    # ========================================================================

    async def create_transaction(
        self,
        wallet: BaseWallet,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        tx_type: TransactionType = TransactionType.SEND,
        category: TransactionCategory = TransactionCategory.TRANSFER,
        priority: TransactionPriority = TransactionPriority.MEDIUM,
        data: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> TransactionBuilder:
        """
        Crée une transaction.

        Args:
            wallet: Wallet
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token (optionnel)
            tx_type: Type de transaction
            category: Catégorie
            priority: Priorité
            data: Données supplémentaires
            metadata: Métadonnées

        Returns:
            TransactionBuilder
        """
        try:
            chain = wallet.config.blockchain.lower()
            
            # Validation du solde
            balance = await wallet.get_balance()
            if token_address:
                token_balance = balance.token_balances.get(token_address, Decimal("0"))
                if token_balance < amount:
                    raise ValueError(f"Solde insuffisant: {token_balance} < {amount}")
            else:
                if balance.native_balance < amount:
                    raise ValueError(f"Solde insuffisant: {balance.native_balance} < {amount}")

            # Estimation du gas
            gas_price = await self._estimate_gas_price(chain, priority)
            gas_limit = await self._estimate_gas_limit(
                wallet,
                to_address,
                amount,
                token_address,
                data
            )

            # Création du builder
            builder = TransactionBuilder(
                tx_id=uuid4(),
                wallet_id=wallet.config.wallet_id,
                user_id=wallet.config.user_id,
                chain=chain,
                network=wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                from_address=wallet.config.address,
                to_address=to_address,
                amount=amount,
                amount_usd=amount * await self._get_token_price(chain, token_address),
                token_address=token_address,
                token_symbol=await self._get_token_symbol(chain, token_address),
                tx_type=tx_type,
                category=category,
                priority=priority,
                gas_price=gas_price,
                gas_limit=gas_limit,
                data=data,
                metadata=metadata or {}
            )

            # Stockage
            self._pending_transactions[str(builder.tx_id)] = builder
            
            # Mise à jour des métriques
            self._metrics["total_transactions"] += 1
            tx_type_key = tx_type.value
            if tx_type_key not in self._metrics["by_type"]:
                self._metrics["by_type"][tx_type_key] = 0
            self._metrics["by_type"][tx_type_key] += 1

            return builder

        except Exception as e:
            logger.error(f"Erreur lors de la création de la transaction: {e}")
            raise

    async def _estimate_gas_price(
        self,
        chain: str,
        priority: TransactionPriority
    ) -> Decimal:
        """
        Estime le prix du gaz.

        Args:
            chain: Blockchain
            priority: Priorité

        Returns:
            Prix du gaz estimé
        """
        try:
            thresholds = self.GAS_THRESHOLDS.get(chain, self.GAS_THRESHOLDS["ethereum"])
            base_price = thresholds.get(priority.value, thresholds["medium"])
            
            # Récupération du prix actuel
            current_price = await self._get_current_gas_price(chain)
            
            # Ajustement selon la priorité
            multiplier = {
                TransactionPriority.LOW: 0.8,
                TransactionPriority.MEDIUM: 1.0,
                TransactionPriority.HIGH: 1.5,
                TransactionPriority.URGENT: 2.0
            }.get(priority, 1.0)
            
            estimated_price = current_price * Decimal(str(multiplier))
            
            # Plafonnement
            max_price = Decimal(str(base_price * 3))
            min_price = Decimal(str(base_price * 0.5))
            
            if estimated_price > max_price:
                estimated_price = max_price
            elif estimated_price < min_price:
                estimated_price = min_price
            
            return estimated_price

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation du prix du gaz: {e}")
            return Decimal(str(self.GAS_THRESHOLDS.get(chain, {}).get("medium", 50)))

    async def _get_current_gas_price(self, chain: str) -> Decimal:
        """
        Récupère le prix actuel du gaz.

        Args:
            chain: Blockchain

        Returns:
            Prix actuel du gaz
        """
        try:
            if chain in ["ethereum", "bsc", "polygon", "avalanche", "arbitrum", "optimism"]:
                # Utilisation de l'API Etherscan ou similaire
                api_key = self.api_keys.get("etherscan")
                if api_key:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://api.etherscan.io/api",
                            params={
                                "module": "gastracker",
                                "action": "gasoracle",
                                "apikey": api_key
                            }
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                if data.get("status") == "1":
                                    return Decimal(data.get("result", {}).get("ProposeGasPrice", 50))
                
                # Fallback
                return Decimal("50")

            elif chain == "solana":
                return Decimal("0.00001")
            
            elif chain == "tron":
                return Decimal("0.00001")
            
            return Decimal("50")

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix du gaz: {e}")
            return Decimal("50")

    async def _estimate_gas_limit(
        self,
        wallet: BaseWallet,
        to_address: str,
        amount: Decimal,
        token_address: Optional[str],
        data: Optional[str]
    ) -> int:
        """
        Estime la limite de gaz.

        Args:
            wallet: Wallet
            to_address: Adresse du destinataire
            amount: Montant
            token_address: Adresse du token
            data: Données

        Returns:
            Limite de gaz estimée
        """
        try:
            if token_address:
                # Transfert de token
                return 200000
            elif data:
                # Transaction avec données
                return 500000
            else:
                # Transfert simple
                return 21000

        except Exception as e:
            logger.error(f"Erreur lors de l'estimation de la limite de gaz: {e}")
            return 21000

    # ========================================================================
    # EXÉCUTION DES TRANSACTIONS
    # ========================================================================

    async def execute_transaction(
        self,
        wallet: BaseWallet,
        builder: TransactionBuilder,
        wait_for_confirmation: bool = True,
        timeout_seconds: int = 120
    ) -> TransactionReceipt:
        """
        Exécute une transaction.

        Args:
            wallet: Wallet
            builder: Constructeur de transaction
            wait_for_confirmation: Attendre la confirmation
            timeout_seconds: Délai d'attente

        Returns:
            Reçu de transaction
        """
        try:
            # Envoi de la transaction
            tx = await wallet.send_transaction(
                to_address=builder.to_address,
                amount=builder.amount,
                token_address=builder.token_address,
                data=builder.data,
                gas_price=builder.gas_price,
                gas_limit=builder.gas_limit,
                metadata=builder.metadata
            )

            # Attente de la confirmation
            if wait_for_confirmation:
                tx = await self._wait_for_confirmation(
                    wallet,
                    tx.tx_hash,
                    timeout_seconds
                )

            # Création du reçu
            receipt = TransactionReceipt(
                tx_hash=tx.tx_hash,
                wallet_id=builder.wallet_id,
                user_id=builder.user_id,
                chain=builder.chain,
                network=builder.network,
                status=tx.status,
                gas_used=tx.gas_used,
                gas_price=tx.gas_price,
                timestamp=tx.timestamp,
                confirmations=tx.confirmations,
                metadata=tx.metadata
            )

            # Stockage
            self._transaction_cache[tx.tx_hash] = receipt
            
            # Mise à jour des métriques
            self._metrics["total_completed"] += 1
            self._metrics["total_volume_usd"] += builder.amount_usd
            self._metrics["last_transaction"] = datetime.now().isoformat()

            # Suppression de la transaction en attente
            if str(builder.tx_id) in self._pending_transactions:
                del self._pending_transactions[str(builder.tx_id)]

            return receipt

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la transaction: {e}")
            self._metrics["total_failed"] += 1
            
            # Création d'un reçu d'échec
            return TransactionReceipt(
                tx_hash=tx.tx_hash if 'tx' in locals() else "",
                wallet_id=builder.wallet_id,
                user_id=builder.user_id,
                chain=builder.chain,
                network=builder.network,
                status=TransactionStatus.FAILED,
                metadata={"error": str(e)}
            )

    async def _wait_for_confirmation(
        self,
        wallet: BaseWallet,
        tx_hash: str,
        timeout_seconds: int
    ) -> Transaction:
        """
        Attend la confirmation d'une transaction.

        Args:
            wallet: Wallet
            tx_hash: Hash de la transaction
            timeout_seconds: Délai d'attente

        Returns:
            Transaction confirmée
        """
        try:
            start_time = datetime.now()
            while (datetime.now() - start_time).seconds < timeout_seconds:
                tx = await wallet.get_transaction(tx_hash)
                if tx and tx.status == TransactionStatus.CONFIRMED:
                    return tx
                await asyncio.sleep(2)
            
            # Timeout
            if tx:
                tx.status = TransactionStatus.TIMEOUT
                return tx
            else:
                raise TimeoutError("Délai d'attente dépassé")

        except Exception as e:
            logger.error(f"Erreur lors de l'attente de confirmation: {e}")
            raise

    # ========================================================================
    # GESTION DES LOTS DE TRANSACTIONS
    # ========================================================================

    async def create_batch(
        self,
        wallet: BaseWallet,
        transactions: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> TransactionBatch:
        """
        Crée un lot de transactions.

        Args:
            wallet: Wallet
            transactions: Liste des transactions
            metadata: Métadonnées

        Returns:
            Lot de transactions
        """
        try:
            batch_id = uuid4()
            builders = []
            total_amount = Decimal("0")
            total_amount_usd = Decimal("0")

            for tx_data in transactions:
                builder = await self.create_transaction(
                    wallet=wallet,
                    to_address=tx_data["to_address"],
                    amount=tx_data["amount"],
                    token_address=tx_data.get("token_address"),
                    tx_type=TransactionType(tx_data.get("tx_type", "send")),
                    category=TransactionCategory(tx_data.get("category", "transfer")),
                    priority=TransactionPriority(tx_data.get("priority", "medium")),
                    data=tx_data.get("data"),
                    metadata=tx_data.get("metadata")
                )
                builders.append(builder)
                total_amount += builder.amount
                total_amount_usd += builder.amount_usd

            batch = TransactionBatch(
                batch_id=batch_id,
                wallet_id=wallet.config.wallet_id,
                user_id=wallet.config.user_id,
                chain=wallet.config.blockchain.lower(),
                network=wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
                transactions=builders,
                total_amount=total_amount,
                total_amount_usd=total_amount_usd,
                metadata=metadata or {}
            )

            self._batch_cache[batch_id] = batch
            self._metrics["total_batches"] += 1

            return batch

        except Exception as e:
            logger.error(f"Erreur lors de la création du lot: {e}")
            raise

    async def execute_batch(
        self,
        wallet: BaseWallet,
        batch_id: UUID,
        wait_for_confirmation: bool = True
    ) -> List[TransactionReceipt]:
        """
        Exécute un lot de transactions.

        Args:
            wallet: Wallet
            batch_id: ID du lot
            wait_for_confirmation: Attendre la confirmation

        Returns:
            Liste des reçus de transaction
        """
        try:
            batch = self._batch_cache.get(batch_id)
            if not batch:
                raise ValueError(f"Lot {batch_id} non trouvé")

            batch.status = "processing"
            receipts = []
            total_fees = Decimal("0")
            total_fees_usd = Decimal("0")

            for builder in batch.transactions:
                receipt = await self.execute_transaction(
                    wallet,
                    builder,
                    wait_for_confirmation
                )
                receipts.append(receipt)
                
                if receipt.gas_used and receipt.gas_price:
                    fee = Decimal(str(receipt.gas_used)) * receipt.gas_price
                    total_fees += fee
                    # Estimation du fee en USD
                    fee_usd = fee * await self._get_token_price(batch.chain, None)
                    total_fees_usd += fee_usd

            batch.status = "completed"
            batch.completed_at = datetime.now()
            batch.total_fees = total_fees
            batch.total_fees_usd = total_fees_usd

            self._metrics["total_fees_usd"] += total_fees_usd

            return receipts

        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du lot: {e}")
            if batch:
                batch.status = "failed"
            raise

    # ========================================================================
    # SUIVI DES TRANSACTIONS
    # ========================================================================

    async def get_transaction(
        self,
        tx_hash: str
    ) -> Optional[TransactionReceipt]:
        """
        Récupère une transaction.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Reçu de transaction ou None
        """
        return self._transaction_cache.get(tx_hash)

    async def get_transaction_history(
        self,
        wallet_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        tx_type: Optional[TransactionType] = None,
        category: Optional[TransactionCategory] = None,
        status: Optional[TransactionStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[TransactionReceipt]:
        """
        Récupère l'historique des transactions.

        Args:
            wallet_id: ID du wallet
            from_date: Date de début
            to_date: Date de fin
            tx_type: Filtrer par type
            category: Filtrer par catégorie
            status: Filtrer par statut
            limit: Nombre de transactions
            offset: Décalage

        Returns:
            Liste des reçus de transaction
        """
        try:
            # Récupération depuis Redis si disponible
            if self.redis:
                key = f"transaction:history:{wallet_id}"
                data = await self.redis.get(key)
                if data:
                    history = json.loads(data)
                    receipts = []
                    for tx_data in history:
                        receipt = TransactionReceipt(**tx_data)
                        receipts.append(receipt)
                    
                    # Filtrage
                    if from_date:
                        receipts = [r for r in receipts if r.timestamp >= from_date]
                    if to_date:
                        receipts = [r for r in receipts if r.timestamp <= to_date]
                    if tx_type:
                        receipts = [r for r in receipts if r.metadata.get("tx_type") == tx_type.value]
                    if category:
                        receipts = [r for r in receipts if r.metadata.get("category") == category.value]
                    if status:
                        receipts = [r for r in receipts if r.status == status]
                    
                    receipts.sort(key=lambda x: x.timestamp, reverse=True)
                    return receipts[offset:offset + limit]

            return []

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []

    async def get_pending_transactions(
        self,
        wallet_id: UUID
    ) -> List[TransactionBuilder]:
        """
        Récupère les transactions en attente.

        Args:
            wallet_id: ID du wallet

        Returns:
            Liste des transactions en attente
        """
        pending = [
            t for t in self._pending_transactions.values()
            if t.wallet_id == wallet_id
        ]
        return pending

    # ========================================================================
    # ANNULATION ET REPLACEMENT
    # ========================================================================

    async def cancel_transaction(
        self,
        wallet: BaseWallet,
        tx_hash: str,
        new_gas_price: Optional[Decimal] = None
    ) -> bool:
        """
        Annule une transaction en attente.

        Args:
            wallet: Wallet
            tx_hash: Hash de la transaction
            new_gas_price: Nouveau prix du gaz

        Returns:
            True si l'annulation a réussi
        """
        try:
            # Récupération de la transaction
            tx = await wallet.get_transaction(tx_hash)
            if not tx:
                return False

            if tx.status != TransactionStatus.PENDING:
                return False

            # Envoi d'une transaction d'annulation
            # (0 ETH vers soi-même avec un gas plus élevé)
            cancel_tx = await wallet.send_transaction(
                to_address=wallet.config.address,
                amount=Decimal("0"),
                gas_price=new_gas_price or tx.gas_price * Decimal("1.1"),
                gas_limit=21000,
                metadata={"cancel": True, "original_tx": tx_hash}
            )

            # Attente de confirmation
            await self._wait_for_confirmation(wallet, cancel_tx.tx_hash, 60)
            
            # Mise à jour du statut
            if tx_hash in self._transaction_cache:
                self._transaction_cache[tx_hash].status = TransactionStatus.CANCELLED

            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'annulation de la transaction: {e}")
            return False

    async def replace_transaction(
        self,
        wallet: BaseWallet,
        tx_hash: str,
        new_amount: Decimal,
        new_gas_price: Optional[Decimal] = None
    ) -> Optional[TransactionReceipt]:
        """
        Remplace une transaction en attente.

        Args:
            wallet: Wallet
            tx_hash: Hash de la transaction
            new_amount: Nouveau montant
            new_gas_price: Nouveau prix du gaz

        Returns:
            Reçu de la nouvelle transaction ou None
        """
        try:
            # Récupération de la transaction
            tx = await wallet.get_transaction(tx_hash)
            if not tx:
                return None

            if tx.status != TransactionStatus.PENDING:
                return None

            # Annulation de l'ancienne transaction
            await self.cancel_transaction(wallet, tx_hash, new_gas_price)

            # Création de la nouvelle transaction
            builder = await self.create_transaction(
                wallet=wallet,
                to_address=tx.to_address,
                amount=new_amount,
                token_address=tx.token_address,
                tx_type=tx.tx_type,
                category=TransactionCategory(tx.metadata.get("category", "transfer")),
                priority=TransactionPriority.HIGH,
                data=tx.metadata.get("data"),
                metadata={"replacement": True, "original_tx": tx_hash}
            )

            # Exécution de la nouvelle transaction
            return await self.execute_transaction(wallet, builder)

        except Exception as e:
            logger.error(f"Erreur lors du remplacement de la transaction: {e}")
            return None

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    async def _get_token_price(
        self,
        chain: str,
        token_address: Optional[str]
    ) -> Decimal:
        """
        Récupère le prix d'un token.

        Args:
            chain: Blockchain
            token_address: Adresse du token

        Returns:
            Prix du token
        """
        try:
            async with aiohttp.ClientSession() as session:
                if token_address:
                    # Récupération du prix du token
                    symbol = await self._get_token_symbol(chain, token_address)
                    async with session.get(
                        "https://api.coingecko.com/api/v3/simple/price",
                        params={
                            "ids": symbol.lower(),
                            "vs_currencies": "usd"
                        }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return Decimal(str(data.get(symbol.lower(), {}).get("usd", 0)))
                else:
                    # Récupération du prix du token natif
                    chain_map = {
                        "ethereum": "ethereum",
                        "bsc": "binancecoin",
                        "polygon": "polygon",
                        "solana": "solana",
                        "avalanche": "avalanche-2",
                        "arbitrum": "arbitrum",
                        "optimism": "optimism",
                        "tron": "tron"
                    }
                    symbol = chain_map.get(chain, "ethereum")
                    async with session.get(
                        "https://api.coingecko.com/api/v3/simple/price",
                        params={
                            "ids": symbol,
                            "vs_currencies": "usd"
                        }
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return Decimal(str(data.get(symbol, {}).get("usd", 0)))
            
            return Decimal("0")

        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prix: {e}")
            return Decimal("0")

    async def _get_token_symbol(
        self,
        chain: str,
        token_address: Optional[str]
    ) -> str:
        """
        Récupère le symbole d'un token.

        Args:
            chain: Blockchain
            token_address: Adresse du token

        Returns:
            Symbole du token
        """
        if not token_address:
            # Token natif
            symbols = {
                "ethereum": "ETH",
                "bsc": "BNB",
                "polygon": "MATIC",
                "solana": "SOL",
                "avalanche": "AVAX",
                "arbitrum": "ETH",
                "optimism": "ETH",
                "tron": "TRX"
            }
            return symbols.get(chain, "ETH")
        
        # Pour les tokens, on retourne un symbole par défaut
        # En production, utiliser les APIs de tokens
        return "UNKNOWN"

    # ========================================================================
    # ANALYSE DES TRANSACTIONS
    # ========================================================================

    async def analyze_transactions(
        self,
        wallet_id: UUID,
        period: str = "30d"
    ) -> Dict[str, Any]:
        """
        Analyse les transactions d'un wallet.

        Args:
            wallet_id: ID du wallet
            period: Période d'analyse

        Returns:
            Analyse des transactions
        """
        try:
            # Récupération de l'historique
            history = await self.get_transaction_history(wallet_id)
            
            # Filtrage par période
            days = int(period.replace('d', ''))
            cutoff = datetime.now() - timedelta(days=days)
            history = [t for t in history if t.timestamp >= cutoff]

            if not history:
                return {"error": "Aucune transaction trouvée"}

            # Statistiques
            total_tx = len(history)
            total_volume = sum(Decimal(str(t.metadata.get("amount_usd", 0))) for t in history)
            total_fees = sum(Decimal(str(t.gas_price or 0)) * (t.gas_used or 0) for t in history)
            
            # Par type
            by_type = {}
            for tx in history:
                tx_type = tx.metadata.get("tx_type", "unknown")
                if tx_type not in by_type:
                    by_type[tx_type] = {"count": 0, "volume": Decimal("0")}
                by_type[tx_type]["count"] += 1
                by_type[tx_type]["volume"] += Decimal(str(tx.metadata.get("amount_usd", 0)))

            # Par jour
            by_day = {}
            for tx in history:
                day_key = tx.timestamp.date().isoformat()
                if day_key not in by_day:
                    by_day[day_key] = {"count": 0, "volume": Decimal("0")}
                by_day[day_key]["count"] += 1
                by_day[day_key]["volume"] += Decimal(str(tx.metadata.get("amount_usd", 0)))

            return {
                "period": period,
                "total_transactions": total_tx,
                "total_volume_usd": float(total_volume),
                "total_fees_usd": float(total_fees),
                "average_tx_value_usd": float(total_volume / total_tx) if total_tx > 0 else 0,
                "by_type": {k: {"count": v["count"], "volume": float(v["volume"])} for k, v in by_type.items()},
                "by_day": {k: {"count": v["count"], "volume": float(v["volume"])} for k, v in by_day.items()},
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des transactions: {e}")
            return {"error": str(e)}

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
                "total_transactions": self._metrics["total_transactions"],
                "total_batches": self._metrics["total_batches"],
                "total_completed": self._metrics["total_completed"],
                "total_failed": self._metrics["total_failed"],
                "total_volume_usd": float(self._metrics["total_volume_usd"]),
                "total_fees_usd": float(self._metrics["total_fees_usd"]),
                "pending_transactions": len(self._pending_transactions),
                "last_transaction": self._metrics["last_transaction"],
                "by_type": self._metrics["by_type"],
                "by_category": self._metrics["by_category"],
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
        logger.info("Fermeture de WalletTransactionService...")
        self._transaction_cache.clear()
        self._batch_cache.clear()
        self._pending_transactions.clear()
        logger.info("WalletTransactionService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_transaction_service(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> WalletTransactionService:
    """
    Crée une instance du service de transactions.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletTransactionService(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TransactionPriority",
    "TransactionCategory",
    "TransactionBuilder",
    "TransactionReceipt",
    "TransactionBatch",
    "WalletTransactionService",
    "create_wallet_transaction_service"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de transactions."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET TRANSACTION MODULE")
    print("=" * 60)

    # Création du service
    tx_service = create_wallet_transaction_service(
        api_keys={"etherscan": "YOUR_ETHERSCAN_API_KEY"}
    )

    # Création d'un wallet exemple
    from .ethereum_wallet import create_ethereum_wallet
    from uuid import UUID
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet = create_ethereum_wallet(
        user_id=user_id,
        name="Transaction Wallet"
    )
    
    await wallet.initialize()

    print(f"\n✅ Wallet créé:")
    print(f"   Adresse: {wallet.config.address}")

    # Création d'une transaction
    builder = await tx_service.create_transaction(
        wallet=wallet,
        to_address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        amount=Decimal("0.01"),
        priority=TransactionPriority.MEDIUM,
        metadata={"purpose": "test_transaction"}
    )
    print(f"\n📝 Transaction créée:")
    print(f"   ID: {builder.tx_id}")
    print(f"   Montant: {builder.amount} ETH")
    print(f"   Gas Price: {builder.gas_price} GWEI")
    print(f"   Gas Limit: {builder.gas_limit}")

    # Exécution de la transaction
    receipt = await tx_service.execute_transaction(wallet, builder)
    print(f"\n✅ Transaction exécutée:")
    print(f"   Hash: {receipt.tx_hash}")
    print(f"   Statut: {receipt.status.value}")
    print(f"   Gas utilisé: {receipt.gas_used}")

    # Création d'un lot de transactions
    transactions = [
        {
            "to_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "amount": Decimal("0.005"),
            "priority": "low"
        },
        {
            "to_address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "amount": Decimal("0.005"),
            "priority": "low"
        }
    ]
    
    batch = await tx_service.create_batch(wallet, transactions)
    print(f"\n📦 Lot de transactions créé:")
    print(f"   ID: {batch.batch_id}")
    print(f"   Transactions: {len(batch.transactions)}")
    print(f"   Montant total: {batch.total_amount} ETH")

    # Analyse des transactions
    analysis = await tx_service.analyze_transactions(wallet.config.wallet_id)
    print(f"\n📊 Analyse des transactions:")
    print(f"   Période: {analysis.get('period', 'N/A')}")
    print(f"   Transactions: {analysis.get('total_transactions', 0)}")
    print(f"   Volume total: ${analysis.get('total_volume_usd', 0):.2f}")

    # Santé du service
    health = await tx_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Transactions: {health['total_transactions']}")
    print(f"   Lots: {health['total_batches']}")
    print(f"   En attente: {health['pending_transactions']}")

    # Fermeture
    await tx_service.close()
    await wallet.close()

    print("\n" + "=" * 60)
    print("WalletTransactionService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
