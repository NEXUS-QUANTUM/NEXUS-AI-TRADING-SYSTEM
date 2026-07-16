
# blockchain/bridges/bridge_transaction.py
"""
NEXUS AI TRADING SYSTEM - Bridge Transaction Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import time
import json
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Statuts de transaction"""
    PENDING = "pending"
    PROCESSING = "processing"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TransactionType(Enum):
    """Types de transaction"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    APPROVAL = "approval"


@dataclass
class BridgeTransaction:
    """Transaction de bridge"""
    id: str
    type: TransactionType
    bridge_name: str
    from_address: str
    to_address: str
    amount: float
    token: str
    status: TransactionStatus
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price: Optional[float] = None
    fee: Optional[float] = None
    confirmations: int = 0
    required_confirmations: int = 12
    timestamp: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type.value,
            'bridge_name': self.bridge_name,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'amount': self.amount,
            'token': self.token,
            'status': self.status.value,
            'tx_hash': self.tx_hash,
            'block_number': self.block_number,
            'gas_used': self.gas_used,
            'gas_price': self.gas_price,
            'fee': self.fee,
            'confirmations': self.confirmations,
            'required_confirmations': self.required_confirmations,
            'timestamp': self.timestamp.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error': self.error,
            'metadata': self.metadata,
        }


@dataclass
class TransactionReceipt:
    """Reçu de transaction"""
    tx_hash: str
    block_number: int
    status: bool
    gas_used: int
    cumulative_gas_used: int
    logs: List[Dict[str, Any]]
    contract_address: Optional[str] = None
    logs_bloom: Optional[str] = None
    transaction_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tx_hash': self.tx_hash,
            'block_number': self.block_number,
            'status': self.status,
            'gas_used': self.gas_used,
            'cumulative_gas_used': self.cumulative_gas_used,
            'logs': self.logs,
            'contract_address': self.contract_address,
            'logs_bloom': self.logs_bloom,
            'transaction_index': self.transaction_index,
        }


class BridgeTransactionManager:
    """
    Gestionnaire de transactions de bridge.

    Features:
    - Création de transactions
    - Suivi des transactions
    - Confirmation des transactions
    - Réessai automatique
    - Historique des transactions

    Example:
        ```python
        manager = BridgeTransactionManager()

        # Créer une transaction
        tx = manager.create_transaction(
            bridge_name='arbitrum',
            from_address='0x...',
            to_address='0x...',
            amount=1.0,
            token='ETH'
        )

        # Suivre la transaction
        manager.track_transaction(tx.id)
        ```
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if not WEB3_AVAILABLE:
            raise ImportError("Web3 n'est pas installé")

        self.config = config or {}
        self.transactions: Dict[str, BridgeTransaction] = {}
        self.receipts: Dict[str, TransactionReceipt] = {}
        self.w3 = Web3()

        logger.info(f"BridgeTransactionManager initialisé")

    def create_transaction(
        self,
        bridge_name: str,
        from_address: str,
        to_address: str,
        amount: float,
        token: str,
        tx_type: TransactionType = TransactionType.DEPOSIT,
        required_confirmations: int = 12,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BridgeTransaction:
        """
        Crée une nouvelle transaction.

        Args:
            bridge_name: Nom du bridge
            from_address: Adresse source
            to_address: Adresse destination
            amount: Montant
            token: Symbole du token
            tx_type: Type de transaction
            required_confirmations: Confirmations requises
            metadata: Métadonnées

        Returns:
            BridgeTransaction: Transaction créée
        """
        import uuid
        tx_id = str(uuid.uuid4())

        transaction = BridgeTransaction(
            id=tx_id,
            type=tx_type,
            bridge_name=bridge_name,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            token=token,
            status=TransactionStatus.PENDING,
            required_confirmations=required_confirmations,
            metadata=metadata or {},
        )

        self.transactions[tx_id] = transaction

        logger.info(f"Transaction créée: {tx_id}")
        return transaction

    def update_transaction(
        self,
        tx_id: str,
        status: Optional[TransactionStatus] = None,
        tx_hash: Optional[str] = None,
        block_number: Optional[int] = None,
        gas_used: Optional[int] = None,
        gas_price: Optional[float] = None,
        fee: Optional[float] = None,
        confirmations: Optional[int] = None,
        error: Optional[str] = None
    ) -> Optional[BridgeTransaction]:
        """
        Met à jour une transaction.

        Args:
            tx_id: ID de la transaction
            status: Nouveau statut
            tx_hash: Hash de la transaction
            block_number: Numéro de block
            gas_used: Gaz utilisé
            gas_price: Prix du gaz
            fee: Frais
            confirmations: Confirmations
            error: Erreur

        Returns:
            Optional[BridgeTransaction]: Transaction mise à jour
        """
        transaction = self.transactions.get(tx_id)
        if not transaction:
            logger.warning(f"Transaction non trouvée: {tx_id}")
            return None

        if status:
            transaction.status = status
        if tx_hash:
            transaction.tx_hash = tx_hash
        if block_number:
            transaction.block_number = block_number
        if gas_used is not None:
            transaction.gas_used = gas_used
        if gas_price is not None:
            transaction.gas_price = gas_price
        if fee is not None:
            transaction.fee = fee
        if confirmations is not None:
            transaction.confirmations = confirmations
        if error:
            transaction.error = error

        transaction.updated_at = datetime.now()

        logger.info(f"Transaction mise à jour: {tx_id} -> {transaction.status.value}")
        return transaction

    def track_transaction(
        self,
        tx_id: str,
        timeout: int = 300,
        check_interval: int = 5
    ) -> Optional[BridgeTransaction]:
        """
        Suit une transaction jusqu'à sa confirmation.

        Args:
            tx_id: ID de la transaction
            timeout: Timeout en secondes
            check_interval: Intervalle de vérification

        Returns:
            Optional[BridgeTransaction]: Transaction suivie
        """
        transaction = self.transactions.get(tx_id)
        if not transaction:
            logger.warning(f"Transaction non trouvée: {tx_id}")
            return None

        if not transaction.tx_hash:
            logger.error(f"Hash manquant pour la transaction: {tx_id}")
            return None

        start_time = time.time()
        w3 = self.w3

        while time.time() - start_time < timeout:
            try:
                receipt = w3.eth.get_transaction_receipt(transaction.tx_hash)

                if receipt:
                    # Mise à jour du reçu
                    tx_receipt = TransactionReceipt(
                        tx_hash=receipt.transactionHash.hex(),
                        block_number=receipt.blockNumber,
                        status=receipt.status == 1,
                        gas_used=receipt.gasUsed,
                        cumulative_gas_used=receipt.cumulativeGasUsed,
                        logs=receipt.logs,
                        contract_address=receipt.contractAddress,
                        logs_bloom=receipt.logsBloom.hex() if receipt.logsBloom else None,
                        transaction_index=receipt.transactionIndex,
                    )
                    self.receipts[transaction.tx_hash] = tx_receipt

                    # Mise à jour de la transaction
                    if receipt.status == 1:
                        transaction.status = TransactionStatus.CONFIRMED
                    else:
                        transaction.status = TransactionStatus.FAILED
                        transaction.error = "Transaction failed"

                    transaction.block_number = receipt.blockNumber
                    transaction.gas_used = receipt.gasUsed
                    transaction.updated_at = datetime.now()

                    # Vérification des confirmations
                    current_block = w3.eth.block_number
                    confirmations = current_block - receipt.blockNumber + 1
                    transaction.confirmations = confirmations

                    if confirmations >= transaction.required_confirmations:
                        transaction.status = TransactionStatus.COMPLETED
                        logger.info(f"Transaction complétée: {tx_id}")
                        return transaction

            except Exception as e:
                logger.debug(f"Erreur de suivi: {e}")

            time.sleep(check_interval)

        transaction.status = TransactionStatus.TIMEOUT
        transaction.error = "Transaction timeout"
        logger.warning(f"Transaction timeout: {tx_id}")
        return transaction

    def cancel_transaction(self, tx_id: str) -> bool:
        """
        Annule une transaction.

        Args:
            tx_id: ID de la transaction

        Returns:
            bool: True si annulée
        """
        transaction = self.transactions.get(tx_id)
        if not transaction:
            return False

        if transaction.status in [TransactionStatus.COMPLETED, TransactionStatus.CONFIRMED]:
            logger.warning(f"Impossible d'annuler une transaction terminée: {tx_id}")
            return False

        transaction.status = TransactionStatus.CANCELLED
        transaction.updated_at = datetime.now()

        logger.info(f"Transaction annulée: {tx_id}")
        return True

    def get_transaction(self, tx_id: str) -> Optional[BridgeTransaction]:
        """
        Récupère une transaction.

        Args:
            tx_id: ID de la transaction

        Returns:
            Optional[BridgeTransaction]: Transaction
        """
        return self.transactions.get(tx_id)

    def get_transactions_by_status(
        self,
        status: TransactionStatus
    ) -> List[BridgeTransaction]:
        """
        Récupère les transactions par statut.

        Args:
            status: Statut

        Returns:
            List[BridgeTransaction]: Transactions
        """
        return [tx for tx in self.transactions.values() if tx.status == status]

    def get_transactions_by_bridge(
        self,
        bridge_name: str
    ) -> List[BridgeTransaction]:
        """
        Récupère les transactions par bridge.

        Args:
            bridge_name: Nom du bridge

        Returns:
            List[BridgeTransaction]: Transactions
        """
        return [tx for tx in self.transactions.values() if tx.bridge_name == bridge_name]

    def get_transaction_receipt(self, tx_hash: str) -> Optional[TransactionReceipt]:
        """
        Récupère un reçu de transaction.

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Optional[TransactionReceipt]: Reçu
        """
        return self.receipts.get(tx_hash)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retourne les statistiques des transactions.

        Returns:
            Dict[str, Any]: Statistiques
        """
        stats = {
            'total_transactions': len(self.transactions),
            'pending': len(self.get_transactions_by_status(TransactionStatus.PENDING)),
            'processing': len(self.get_transactions_by_status(TransactionStatus.PROCESSING)),
            'confirmed': len(self.get_transactions_by_status(TransactionStatus.CONFIRMED)),
            'completed': len(self.get_transactions_by_status(TransactionStatus.COMPLETED)),
            'failed': len(self.get_transactions_by_status(TransactionStatus.FAILED)),
            'cancelled': len(self.get_transactions_by_status(TransactionStatus.CANCELLED)),
            'timeout': len(self.get_transactions_by_status(TransactionStatus.TIMEOUT)),
        }

        # Volume total
        total_volume = sum(tx.amount for tx in self.transactions.values())
        stats['total_volume'] = total_volume

        # Par type
        for tx_type in TransactionType:
            count = sum(1 for tx in self.transactions.values() if tx.type == tx_type)
            stats[f'{tx_type.value}_count'] = count

        return stats

    def clear_completed(self) -> int:
        """
        Supprime les transactions complétées.

        Returns:
            int: Nombre de transactions supprimées
        """
        completed_ids = [
            tx_id for tx_id, tx in self.transactions.items()
            if tx.status in [TransactionStatus.COMPLETED, TransactionStatus.CANCELLED]
        ]

        for tx_id in completed_ids:
            del self.transactions[tx_id]

        logger.info(f"Transactions complétées supprimées: {len(completed_ids)}")
        return len(completed_ids)


def create_bridge_transaction_manager(
    **kwargs
) -> BridgeTransactionManager:
    """
    Factory pour créer un gestionnaire de transactions de bridge.

    Args:
        **kwargs: Arguments de configuration

    Returns:
        BridgeTransactionManager: Gestionnaire
    """
    return BridgeTransactionManager(kwargs)


__all__ = [
    'BridgeTransactionManager',
    'BridgeTransaction',
    'TransactionReceipt',
    'TransactionStatus',
    'TransactionType',
    'create_bridge_transaction_manager',
]
