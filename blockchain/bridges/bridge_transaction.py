# blockchain/bridges/bridge_transaction.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Gestion des Transactions Bridge

Ce module implémente un système complet de gestion des transactions pour les
opérations de bridge cross-chain, incluant la construction, la signature,
l'envoi, le suivi, et la gestion des erreurs des transactions blockchain.

Fonctionnalités principales:
- Construction de transactions de bridge
- Gestion des signatures multi-clés
- Suivi en temps réel des transactions
- Gestion des erreurs et des retries
- Optimisation des frais de gaz
- Support de multiples protocoles de bridge
- Monitoring et alertes
- Historique des transactions
- Analyse des performances
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from functools import lru_cache, wraps

import aiohttp
import web3
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex, keccak
from eth_abi import encode_single, decode_single

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, BridgeError, ValidationError, TransactionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge
    from .bridge_manager import BridgeManager
    from .bridge_validator import BridgeValidator
    from ..wallets.base_wallet import BaseWallet
    from ..security.encryption import EncryptionManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class TransactionStatus(Enum):
    """Statuts d'une transaction"""
    PENDING = "pending"
    SIGNING = "signing"
    BROADCASTING = "broadcasting"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"
    REPLACED = "replaced"
    EXPIRED = "expired"
    RETRYING = "retrying"


class TransactionType(Enum):
    """Types de transactions"""
    BRIDGE = "bridge"
    APPROVAL = "approval"
    SWAP = "swap"
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    CLAIM = "claim"
    RELAY = "relay"


class GasStrategy(Enum):
    """Stratégies de gaz"""
    STANDARD = "standard"
    FAST = "fast"
    RAPID = "rapid"
    CUSTOM = "custom"
    EIP1559 = "eip1559"
    LEGACY = "legacy"


@dataclass
class BridgeTransaction:
    """Transaction de bridge"""
    tx_id: str
    bridge_id: str
    protocol: str
    chain: str
    tx_type: TransactionType
    status: TransactionStatus
    from_address: str
    to_address: str
    value: Decimal
    token: Optional[str] = None
    gas_limit: Optional[int] = None
    gas_price: Optional[int] = None
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    nonce: Optional[int] = None
    tx_hash: Optional[str] = None
    signed_tx: Optional[str] = None
    raw_tx: Optional[str] = None
    data: Optional[str] = None
    confirmations: int = 0
    target_confirmations: int = 12
    block_number: Optional[int] = None
    block_hash: Optional[str] = None
    gas_used: Optional[int] = None
    effective_gas_price: Optional[int] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "tx_id": self.tx_id,
            "bridge_id": self.bridge_id,
            "protocol": self.protocol,
            "chain": self.chain,
            "tx_type": self.tx_type.value,
            "status": self.status.value,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "value": str(self.value),
            "token": self.token,
            "gas_limit": self.gas_limit,
            "gas_price": self.gas_price,
            "max_fee_per_gas": self.max_fee_per_gas,
            "max_priority_fee_per_gas": self.max_priority_fee_per_gas,
            "nonce": self.nonce,
            "tx_hash": self.tx_hash,
            "confirmations": self.confirmations,
            "target_confirmations": self.target_confirmations,
            "block_number": self.block_number,
            "gas_used": self.gas_used,
            "effective_gas_price": self.effective_gas_price,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def is_completed(self) -> bool:
        """Vérifie si la transaction est terminée"""
        return self.status in [
            TransactionStatus.COMPLETED,
            TransactionStatus.FAILED,
            TransactionStatus.REVERTED,
            TransactionStatus.EXPIRED,
        ]

    def is_successful(self) -> bool:
        """Vérifie si la transaction a réussi"""
        return self.status == TransactionStatus.COMPLETED


@dataclass
class TransactionReceipt:
    """Reçu de transaction"""
    tx_hash: str
    block_number: int
    block_hash: str
    transaction_index: int
    from_address: str
    to_address: str
    gas_used: int
    cumulative_gas_used: int
    effective_gas_price: int
    status: int  # 1 = success, 0 = failure
    logs: List[Dict[str, Any]]
    logs_bloom: str
    contract_address: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "transaction_index": self.transaction_index,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "gas_used": self.gas_used,
            "cumulative_gas_used": self.cumulative_gas_used,
            "effective_gas_price": self.effective_gas_price,
            "status": self.status,
            "logs": self.logs,
            "contract_address": self.contract_address,
            "events": self.events,
        }

    def is_success(self) -> bool:
        """Vérifie si la transaction a réussi"""
        return self.status == 1


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeTransactionManager:
    """
    Gestionnaire avancé des transactions de bridge
    """

    def __init__(
        self,
        config: Dict[str, Any],
        web3_providers: Dict[str, Web3],
        wallet_manager: Any,
        bridge_manager: BridgeManager,
        validator: Optional[BridgeValidator] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        encryption_manager: Optional[EncryptionManager] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de transactions

        Args:
            config: Configuration
            web3_providers: Providers Web3 par chaîne
            wallet_manager: Gestionnaire de wallets
            bridge_manager: Gestionnaire de bridges
            validator: Validateur de bridge
            metrics_collector: Collecteur de métriques
            encryption_manager: Gestionnaire de chiffrement
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.web3_providers = web3_providers
        self.wallet_manager = wallet_manager
        self.bridge_manager = bridge_manager
        self.validator = validator
        self.metrics = metrics_collector or MetricsCollector()
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.cache_ttl = cache_ttl

        # États internes
        self._transactions: Dict[str, BridgeTransaction] = {}
        self._pending_transactions: Dict[str, BridgeTransaction] = {}
        self._transaction_history: List[BridgeTransaction] = []
        self._receipt_cache: Dict[str, Tuple[float, TransactionReceipt]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
            backoff=2.0,
        )

        # Circuit breaker par chaîne
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            chain: CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_attempts=3,
            )
            for chain in web3_providers.keys()
        }

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des nonces
        self._nonce_cache: Dict[str, Dict[str, int]] = defaultdict(dict)

        # Statistiques
        self._tx_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        logger.info("BridgeTransactionManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def create_transaction(
        self,
        bridge_id: str,
        protocol: str,
        chain: str,
        tx_type: TransactionType,
        from_address: str,
        to_address: str,
        value: Decimal,
        token: Optional[str] = None,
        data: Optional[str] = None,
        gas_limit: Optional[int] = None,
        gas_price: Optional[int] = None,
        gas_strategy: GasStrategy = GasStrategy.STANDARD,
        **kwargs,
    ) -> BridgeTransaction:
        """
        Crée une nouvelle transaction de bridge

        Args:
            bridge_id: ID du bridge
            protocol: Protocole
            chain: Chaîne
            tx_type: Type de transaction
            from_address: Adresse source
            to_address: Adresse destination
            value: Montant
            token: Adresse du token (optionnel)
            data: Données de la transaction
            gas_limit: Limite de gaz (optionnel)
            gas_price: Prix du gaz (optionnel)
            gas_strategy: Stratégie de gaz
            **kwargs: Arguments additionnels

        Returns:
            Transaction créée
        """
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        logger.info(f"Création de la transaction {tx_id} pour {bridge_id}")

        try:
            # Vérification du wallet
            wallet = await self.wallet_manager.get_wallet(from_address)
            if not wallet:
                raise TransactionError(f"Wallet non trouvé: {from_address}")

            # Obtention du nonce
            nonce = await self._get_nonce(chain, from_address)

            # Calcul du gaz
            if gas_limit is None:
                gas_limit = await self._estimate_gas(
                    chain=chain,
                    to_address=to_address,
                    value=value,
                    data=data,
                    token=token,
                )

            if gas_price is None:
                gas_price = await self._calculate_gas_price(chain, gas_strategy)

            # Création de la transaction
            transaction = BridgeTransaction(
                tx_id=tx_id,
                bridge_id=bridge_id,
                protocol=protocol,
                chain=chain,
                tx_type=tx_type,
                status=TransactionStatus.PENDING,
                from_address=from_address,
                to_address=to_address,
                value=value,
                token=token,
                data=data,
                gas_limit=gas_limit,
                gas_price=gas_price,
                nonce=nonce,
                metadata=kwargs,
            )

            # Stockage
            self._transactions[tx_id] = transaction
            self._pending_transactions[tx_id] = transaction

            # Métriques
            self.metrics.record_increment(
                "bridge_transaction_created",
                {
                    "protocol": protocol,
                    "chain": chain,
                    "tx_type": tx_type.value,
                },
            )

            logger.info(f"Transaction {tx_id} créée avec succès")
            return transaction

        except Exception as e:
            logger.error(f"Erreur de création de transaction: {e}")
            raise TransactionError(f"Erreur de création: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def sign_transaction(
        self,
        tx_id: str,
        wallet_address: Optional[str] = None,
    ) -> BridgeTransaction:
        """
        Signe une transaction

        Args:
            tx_id: ID de la transaction
            wallet_address: Adresse du wallet (optionnel)

        Returns:
            Transaction signée
        """
        logger.info(f"Signature de la transaction {tx_id}")

        async with self._locks[tx_id]:
            transaction = await self.get_transaction(tx_id)
            if not transaction:
                raise TransactionError(f"Transaction non trouvée: {tx_id}")

            if transaction.status == TransactionStatus.COMPLETED:
                raise TransactionError("Transaction déjà terminée")

            wallet_address = wallet_address or transaction.from_address
            wallet = await self.wallet_manager.get_wallet(wallet_address)
            if not wallet:
                raise TransactionError(f"Wallet non trouvé: {wallet_address}")

            try:
                transaction.status = TransactionStatus.SIGNING

                # Construction de la transaction
                tx_data = await self._build_transaction_data(transaction)

                # Signature
                signed_tx = wallet.sign_transaction(tx_data)
                transaction.signed_tx = signed_tx.hex()
                transaction.raw_tx = tx_data.hex() if hasattr(tx_data, 'hex') else str(tx_data)
                transaction.status = TransactionStatus.PENDING_CONFIRMATION

                # Mise à jour
                transaction.updated_at = datetime.now()
                self._transactions[tx_id] = transaction
                self._pending_transactions[tx_id] = transaction

                logger.info(f"Transaction {tx_id} signée avec succès")
                return transaction

            except Exception as e:
                logger.error(f"Erreur de signature: {e}")
                transaction.status = TransactionStatus.FAILED
                transaction.error_message = str(e)
                transaction.updated_at = datetime.now()
                self._transactions[tx_id] = transaction
                raise TransactionError(f"Erreur de signature: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def broadcast_transaction(
        self,
        tx_id: str,
    ) -> BridgeTransaction:
        """
        Diffuse une transaction sur le réseau

        Args:
            tx_id: ID de la transaction

        Returns:
            Transaction diffusée
        """
        logger.info(f"Diffusion de la transaction {tx_id}")

        async with self._locks[tx_id]:
            transaction = await self.get_transaction(tx_id)
            if not transaction:
                raise TransactionError(f"Transaction non trouvée: {tx_id}")

            if transaction.status != TransactionStatus.PENDING_CONFIRMATION:
                raise TransactionError(f"Transaction non signée: {tx_id}")

            try:
                transaction.status = TransactionStatus.BROADCASTING

                # Récupération du provider
                provider = self.web3_providers.get(transaction.chain)
                if not provider:
                    raise TransactionError(f"Provider non trouvé: {transaction.chain}")

                # Diffusion
                signed_tx = HexBytes(transaction.signed_tx)
                tx_hash = await provider.eth.send_raw_transaction(signed_tx)

                transaction.tx_hash = tx_hash.hex()
                transaction.status = TransactionStatus.PENDING_CONFIRMATION
                transaction.updated_at = datetime.now()

                # Mise à jour
                self._transactions[tx_id] = transaction
                self._pending_transactions[tx_id] = transaction

                logger.info(f"Transaction {tx_id} diffusée: {tx_hash.hex()}")
                return transaction

            except Exception as e:
                logger.error(f"Erreur de diffusion: {e}")
                transaction.status = TransactionStatus.FAILED
                transaction.error_message = str(e)
                transaction.updated_at = datetime.now()
                self._transactions[tx_id] = transaction
                raise TransactionError(f"Erreur de diffusion: {e}")

    @async_retry(max_attempts=5, initial_delay=1.0)
    async def wait_for_confirmation(
        self,
        tx_id: str,
        target_confirmations: Optional[int] = None,
        timeout: int = 3600,
        poll_interval: int = 5,
    ) -> BridgeTransaction:
        """
        Attend la confirmation d'une transaction

        Args:
            tx_id: ID de la transaction
            target_confirmations: Nombre de confirmations cible
            timeout: Timeout en secondes
            poll_interval: Intervalle de polling

        Returns:
            Transaction confirmée
        """
        logger.info(f"Attente de confirmation pour {tx_id}")

        start_time = time.time()
        transaction = await self.get_transaction(tx_id)

        if not transaction:
            raise TransactionError(f"Transaction non trouvée: {tx_id}")

        if transaction.status == TransactionStatus.COMPLETED:
            return transaction

        target = target_confirmations or transaction.target_confirmations

        while time.time() - start_time < timeout:
            try:
                # Vérification du statut
                updated_tx = await self.update_transaction_status(tx_id)
                transaction = updated_tx or transaction

                if transaction.tx_hash:
                    confirmations = await self._get_confirmations(
                        transaction.chain,
                        transaction.tx_hash,
                    )
                    transaction.confirmations = confirmations

                    if confirmations >= target:
                        # Vérification du reçu
                        receipt = await self._get_transaction_receipt(
                            transaction.chain,
                            transaction.tx_hash,
                        )
                        if receipt and receipt.is_success():
                            transaction.status = TransactionStatus.COMPLETED
                            transaction.completed_at = datetime.now()
                            self._transactions[tx_id] = transaction
                            self._pending_transactions.pop(tx_id, None)

                            logger.info(
                                f"Transaction {tx_id} confirmée avec {confirmations} confirmations"
                            )

                            # Métriques
                            self.metrics.record_timing(
                                "bridge_transaction_confirmation_time",
                                time.time() - start_time,
                                {
                                    "protocol": transaction.protocol,
                                    "chain": transaction.chain,
                                    "tx_type": transaction.tx_type.value,
                                },
                            )

                            return transaction
                        elif receipt and not receipt.is_success():
                            transaction.status = TransactionStatus.REVERTED
                            transaction.error_message = "Transaction reverted"
                            transaction.completed_at = datetime.now()
                            self._transactions[tx_id] = transaction
                            self._pending_transactions.pop(tx_id, None)

                            raise TransactionError("Transaction reverted")

            except Exception as e:
                logger.warning(f"Erreur de vérification: {e}")

            await asyncio.sleep(poll_interval)

        # Timeout
        transaction.status = TransactionStatus.EXPIRED
        transaction.error_message = f"Timeout après {timeout} secondes"
        transaction.updated_at = datetime.now()
        self._transactions[tx_id] = transaction
        self._pending_transactions.pop(tx_id, None)

        raise TransactionError(f"Timeout de confirmation: {tx_id}")

    async def update_transaction_status(
        self,
        tx_id: str,
    ) -> Optional[BridgeTransaction]:
        """
        Met à jour le statut d'une transaction

        Args:
            tx_id: ID de la transaction

        Returns:
            Transaction mise à jour
        """
        transaction = await self.get_transaction(tx_id)
        if not transaction or not transaction.tx_hash:
            return transaction

        try:
            receipt = await self._get_transaction_receipt(
                transaction.chain,
                transaction.tx_hash,
            )

            if receipt:
                if receipt.is_success():
                    transaction.status = TransactionStatus.COMPLETED
                    transaction.completed_at = datetime.now()
                    self._pending_transactions.pop(tx_id, None)
                else:
                    transaction.status = TransactionStatus.REVERTED
                    transaction.error_message = "Transaction reverted"
                    self._pending_transactions.pop(tx_id, None)

                transaction.block_number = receipt.block_number
                transaction.block_hash = receipt.block_hash
                transaction.gas_used = receipt.gas_used
                transaction.effective_gas_price = receipt.effective_gas_price
                transaction.status_code = receipt.status
                transaction.updated_at = datetime.now()

                self._transactions[tx_id] = transaction
                return transaction

            # Vérification de la transaction
            provider = self.web3_providers.get(transaction.chain)
            if provider:
                tx = await provider.eth.get_transaction(HexBytes(transaction.tx_hash))
                if tx:
                    transaction.nonce = tx.get("nonce")
                    transaction.updated_at = datetime.now()
                    self._transactions[tx_id] = transaction

        except Exception as e:
            logger.warning(f"Erreur de mise à jour du statut: {e}")

        return transaction

    async def get_transaction(self, tx_id: str) -> Optional[BridgeTransaction]:
        """Obtient une transaction par son ID"""
        return self._transactions.get(tx_id)

    async def get_transaction_by_hash(
        self,
        tx_hash: str,
        chain: str,
    ) -> Optional[BridgeTransaction]:
        """Obtient une transaction par son hash"""
        for tx in self._transactions.values():
            if tx.tx_hash == tx_hash and tx.chain == chain:
                return tx
        return None

    async def get_pending_transactions(
        self,
        chain: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> List[BridgeTransaction]:
        """Obtient les transactions en attente"""
        pending = list(self._pending_transactions.values())

        if chain:
            pending = [tx for tx in pending if tx.chain == chain]

        if protocol:
            pending = [tx for tx in pending if tx.protocol == protocol]

        return pending

    async def get_transaction_history(
        self,
        limit: int = 100,
        chain: Optional[str] = None,
        protocol: Optional[str] = None,
        status: Optional[TransactionStatus] = None,
    ) -> List[BridgeTransaction]:
        """Obtient l'historique des transactions"""
        transactions = list(self._transactions.values())

        if chain:
            transactions = [tx for tx in transactions if tx.chain == chain]

        if protocol:
            transactions = [tx for tx in transactions if tx.protocol == protocol]

        if status:
            transactions = [tx for tx in transactions if tx.status == status]

        # Tri par date de création (plus récent en premier)
        transactions.sort(key=lambda x: x.created_at, reverse=True)

        return transactions[:limit]

    async def retry_transaction(
        self,
        tx_id: str,
        increase_gas: bool = True,
    ) -> BridgeTransaction:
        """
        Réessaie une transaction échouée

        Args:
            tx_id: ID de la transaction
            increase_gas: Augmenter le prix du gaz

        Returns:
            Nouvelle transaction
        """
        logger.info(f"Réessai de la transaction {tx_id}")

        transaction = await self.get_transaction(tx_id)
        if not transaction:
            raise TransactionError(f"Transaction non trouvée: {tx_id}")

        if transaction.status not in [TransactionStatus.FAILED, TransactionStatus.EXPIRED]:
            raise TransactionError("Seules les transactions échouées peuvent être réessayées")

        if transaction.retry_count >= self.retry_config.max_attempts:
            raise TransactionError("Nombre maximum de réessais atteint")

        try:
            # Création d'une nouvelle transaction avec les mêmes paramètres
            new_tx = await self.create_transaction(
                bridge_id=transaction.bridge_id,
                protocol=transaction.protocol,
                chain=transaction.chain,
                tx_type=transaction.tx_type,
                from_address=transaction.from_address,
                to_address=transaction.to_address,
                value=transaction.value,
                token=transaction.token,
                data=transaction.data,
                gas_limit=transaction.gas_limit,
                gas_strategy=GasStrategy.FAST if increase_gas else GasStrategy.STANDARD,
                retry_count=transaction.retry_count + 1,
            )

            # Copie des métadonnées
            new_tx.metadata = {**transaction.metadata, "retry_of": transaction.tx_id}

            # Marquage de l'ancienne transaction
            transaction.status = TransactionStatus.REPLACED
            transaction.error_message = f"Replaced by {new_tx.tx_id}"
            transaction.updated_at = datetime.now()
            self._transactions[tx_id] = transaction
            self._pending_transactions.pop(tx_id, None)

            logger.info(f"Nouvelle transaction {new_tx.tx_id} créée pour le réessai")
            return new_tx

        except Exception as e:
            logger.error(f"Erreur de réessai: {e}")
            raise TransactionError(f"Erreur de réessai: {e}")

    # ============================================================
    # MÉTHODES DE CONSTRUCTION DE TRANSACTIONS
    # ============================================================

    async def _build_transaction_data(
        self,
        transaction: BridgeTransaction,
    ) -> Dict[str, Any]:
        """Construit les données de la transaction"""
        provider = self.web3_providers.get(transaction.chain)
        if not provider:
            raise TransactionError(f"Provider non trouvé: {transaction.chain}")

        # Construction de base
        tx_data = {
            "from": to_checksum_address(transaction.from_address),
            "to": to_checksum_address(transaction.to_address),
            "value": int(transaction.value * Decimal(1e18)) if transaction.value else 0,
            "nonce": transaction.nonce,
            "gas": transaction.gas_limit,
        }

        # Ajout du data
        if transaction.data:
            tx_data["data"] = transaction.data

        # Gestion du prix du gaz (EIP-1559 vs Legacy)
        if transaction.max_fee_per_gas and transaction.max_priority_fee_per_gas:
            tx_data["maxFeePerGas"] = transaction.max_fee_per_gas
            tx_data["maxPriorityFeePerGas"] = transaction.max_priority_fee_per_gas
            tx_data["type"] = 2  # EIP-1559
        else:
            tx_data["gasPrice"] = transaction.gas_price

        # Ajout des métadonnées de la chaîne
        chain_config = self.config.get("chains", {}).get(transaction.chain, {})
        if chain_config.get("chain_id"):
            tx_data["chainId"] = chain_config["chain_id"]

        return tx_data

    async def _estimate_gas(
        self,
        chain: str,
        to_address: str,
        value: Decimal,
        data: Optional[str] = None,
        token: Optional[str] = None,
    ) -> int:
        """Estime le gaz nécessaire pour une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 100000  # Valeur par défaut

            # Construction de la transaction d'estimation
            tx = {
                "to": to_checksum_address(to_address),
                "from": to_checksum_address(self.config.get("from_address", "0x")),
                "value": int(value * Decimal(1e18)) if value else 0,
            }

            if data:
                tx["data"] = data

            # Estimation
            gas_estimate = await provider.eth.estimate_gas(tx)

            # Ajout d'une marge de sécurité
            return int(gas_estimate * 1.2)  # 20% de marge

        except Exception as e:
            logger.warning(f"Erreur d'estimation de gaz: {e}")
            return 200000  # Valeur par défaut

    async def _calculate_gas_price(
        self,
        chain: str,
        strategy: GasStrategy,
    ) -> int:
        """Calcule le prix du gaz selon la stratégie"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 1000000000  # 1 Gwei par défaut

            # Récupération du prix du gaz
            if strategy in [GasStrategy.EIP1559, GasStrategy.FAST, GasStrategy.RAPID]:
                # EIP-1559
                fee_history = await provider.eth.fee_history(5, "latest", [25, 50, 75])
                base_fee = fee_history.get("baseFeePerGas", [0])[-1]

                if strategy == GasStrategy.RAPID:
                    priority_fee = int(base_fee * 0.3)
                elif strategy == GasStrategy.FAST:
                    priority_fee = int(base_fee * 0.2)
                else:
                    priority_fee = int(base_fee * 0.1)

                return priority_fee

            else:
                # Legacy gas price
                gas_price = await provider.eth.gas_price

                if strategy == GasStrategy.FAST:
                    gas_price = int(gas_price * 1.2)
                elif strategy == GasStrategy.RAPID:
                    gas_price = int(gas_price * 1.5)

                return gas_price

        except Exception as e:
            logger.warning(f"Erreur de calcul du gaz: {e}")
            return 1000000000

    async def _get_nonce(self, chain: str, address: str) -> int:
        """Obtient le nonce pour une adresse"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 0

            # Vérification du cache
            cache_key = f"{chain}:{address}"
            if cache_key in self._nonce_cache:
                nonce = self._nonce_cache[cache_key].get("nonce", 0)
                timestamp = self._nonce_cache[cache_key].get("timestamp", 0)

                # Cache valide pour 30 secondes
                if time.time() - timestamp < 30:
                    return nonce

            # Obtention du nonce
            nonce = await provider.eth.get_transaction_count(address)

            # Mise en cache
            self._nonce_cache[cache_key] = {
                "nonce": nonce,
                "timestamp": time.time(),
            }

            return nonce

        except Exception as e:
            logger.warning(f"Erreur d'obtention du nonce: {e}")
            return 0

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE RECU
    # ============================================================

    async def _get_transaction_receipt(
        self,
        chain: str,
        tx_hash: str,
    ) -> Optional[TransactionReceipt]:
        """Obtient le reçu d'une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return None

            # Vérification du cache
            cache_key = f"{chain}:{tx_hash}"
            if cache_key in self._receipt_cache:
                cached_time, cached_receipt = self._receipt_cache[cache_key]
                if time.time() - cached_time < self.cache_ttl:
                    return cached_receipt

            # Obtention du reçu
            receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
            if not receipt:
                return None

            # Obtention de la transaction pour les détails
            tx = await provider.eth.get_transaction(HexBytes(tx_hash))

            # Construction du reçu
            tx_receipt = TransactionReceipt(
                tx_hash=tx_hash,
                block_number=receipt.get("blockNumber", 0),
                block_hash=receipt.get("blockHash", "0x").hex(),
                transaction_index=receipt.get("transactionIndex", 0),
                from_address=tx.get("from", "0x") if tx else "0x",
                to_address=tx.get("to", "0x") if tx else "0x",
                gas_used=receipt.get("gasUsed", 0),
                cumulative_gas_used=receipt.get("cumulativeGasUsed", 0),
                effective_gas_price=receipt.get("effectiveGasPrice", 0),
                status=receipt.get("status", 0),
                logs=receipt.get("logs", []),
                logs_bloom=receipt.get("logsBloom", "0x"),
                contract_address=receipt.get("contractAddress"),
            )

            # Extraction des événements
            tx_receipt.events = await self._extract_events(
                chain,
                receipt.get("logs", []),
            )

            # Mise en cache
            self._receipt_cache[cache_key] = (time.time(), tx_receipt)

            return tx_receipt

        except Exception as e:
            logger.warning(f"Erreur d'obtention du reçu: {e}")
            return None

    async def _get_confirmations(self, chain: str, tx_hash: str) -> int:
        """Obtient le nombre de confirmations d'une transaction"""
        try:
            provider = self.web3_providers.get(chain)
            if not provider:
                return 0

            receipt = await provider.eth.get_transaction_receipt(HexBytes(tx_hash))
            if not receipt:
                return 0

            block_number = receipt.get("blockNumber", 0)
            current_block = await provider.eth.block_number

            return current_block - block_number + 1

        except Exception:
            return 0

    async def _extract_events(
        self,
        chain: str,
        logs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extrait les événements des logs"""
        events = []

        for log in logs:
            try:
                # Tentative de décodage des événements courants
                # Transfer
                if log.get("topics", []) and len(log.get("topics", [])) >= 3:
                    event = {
                        "address": log.get("address", "0x"),
                        "transaction_hash": log.get("transactionHash", "0x"),
                        "block_number": log.get("blockNumber", 0),
                        "data": log.get("data", "0x"),
                    }

                    # Extraction des topics
                    topics = log.get("topics", [])
                    if topics:
                        event["topics"] = [t.hex() if hasattr(t, 'hex') else t for t in topics]

                        # Tentative de décodage Transfer
                        if topics[0] == keccak(text="Transfer(address,address,uint256)").hex():
                            try:
                                from_address = topics[1][-40:]
                                to_address = topics[2][-40:]
                                value = int(log.get("data", "0x"), 16) if log.get("data") else 0

                                event["name"] = "Transfer"
                                event["args"] = {
                                    "from": f"0x{from_address}",
                                    "to": f"0x{to_address}",
                                    "value": value,
                                }
                            except Exception:
                                pass

                    events.append(event)

            except Exception as e:
                logger.debug(f"Erreur d'extraction d'événement: {e}")

        return events

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques des transactions"""
        total_transactions = len(self._transactions)
        pending_count = len(self._pending_transactions)

        completed = sum(
            1 for tx in self._transactions.values()
            if tx.status == TransactionStatus.COMPLETED
        )

        failed = sum(
            1 for tx in self._transactions.values()
            if tx.status in [TransactionStatus.FAILED, TransactionStatus.REVERTED]
        )

        return {
            "total_transactions": total_transactions,
            "pending_transactions": pending_count,
            "completed_transactions": completed,
            "failed_transactions": failed,
            "success_rate": completed / max(1, total_transactions),
            "avg_confirmations": self._calculate_avg_confirmations(),
            "avg_gas_used": self._calculate_avg_gas_used(),
            "protocol_stats": self._get_protocol_stats(),
            "chain_stats": self._get_chain_stats(),
            "tx_type_stats": self._get_tx_type_stats(),
        }

    def _calculate_avg_confirmations(self) -> float:
        """Calcule le nombre moyen de confirmations"""
        confirmed = [
            tx for tx in self._transactions.values()
            if tx.status == TransactionStatus.COMPLETED
        ]

        if not confirmed:
            return 0.0

        total_confirmations = sum(tx.confirmations for tx in confirmed)
        return total_confirmations / len(confirmed)

    def _calculate_avg_gas_used(self) -> int:
        """Calcule le gaz moyen utilisé"""
        completed = [
            tx for tx in self._transactions.values()
            if tx.status == TransactionStatus.COMPLETED and tx.gas_used
        ]

        if not completed:
            return 0

        total_gas = sum(tx.gas_used for tx in completed)
        return int(total_gas / len(completed))

    def _get_protocol_stats(self) -> Dict[str, Dict[str, int]]:
        """Obtient les statistiques par protocole"""
        stats = defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0})

        for tx in self._transactions.values():
            stats[tx.protocol]["total"] += 1
            if tx.status == TransactionStatus.COMPLETED:
                stats[tx.protocol]["completed"] += 1
            elif tx.status in [TransactionStatus.FAILED, TransactionStatus.REVERTED]:
                stats[tx.protocol]["failed"] += 1

        return dict(stats)

    def _get_chain_stats(self) -> Dict[str, Dict[str, int]]:
        """Obtient les statistiques par chaîne"""
        stats = defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0})

        for tx in self._transactions.values():
            stats[tx.chain]["total"] += 1
            if tx.status == TransactionStatus.COMPLETED:
                stats[tx.chain]["completed"] += 1
            elif tx.status in [TransactionStatus.FAILED, TransactionStatus.REVERTED]:
                stats[tx.chain]["failed"] += 1

        return dict(stats)

    def _get_tx_type_stats(self) -> Dict[str, Dict[str, int]]:
        """Obtient les statistiques par type de transaction"""
        stats = defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0})

        for tx in self._transactions.values():
            stats[tx.tx_type.value]["total"] += 1
            if tx.status == TransactionStatus.COMPLETED:
                stats[tx.tx_type.value]["completed"] += 1
            elif tx.status in [TransactionStatus.FAILED, TransactionStatus.REVERTED]:
                stats[tx.tx_type.value]["failed"] += 1

        return dict(stats)

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeTransactionManager...")

        # Nettoyage des caches
        self._receipt_cache.clear()
        self._nonce_cache.clear()

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_transaction_manager(
    config: Dict[str, Any],
    web3_providers: Dict[str, Web3],
    wallet_manager: Any,
    bridge_manager: BridgeManager,
    **kwargs,
) -> BridgeTransactionManager:
    """
    Crée une instance de BridgeTransactionManager

    Args:
        config: Configuration
        web3_providers: Providers Web3
        wallet_manager: Gestionnaire de wallets
        bridge_manager: Gestionnaire de bridges
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeTransactionManager
    """
    return BridgeTransactionManager(
        config=config,
        web3_providers=web3_providers,
        wallet_manager=wallet_manager,
        bridge_manager=bridge_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeTransactionManager"""
    # Configuration
    config = {
        "chains": {
            "ethereum": {
                "chain_id": 1,
                "rpc_url": "https://mainnet.infura.io/v3/YOUR_KEY",
            },
            "arbitrum": {
                "chain_id": 42161,
                "rpc_url": "https://arb1.arbitrum.io/rpc",
            },
        },
        "default_gas_limit": 200000,
        "min_confirmations": {
            "ethereum": 12,
            "arbitrum": 5,
        },
    }

    # Web3 providers
    web3_providers = {
        "ethereum": Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY")),
        "arbitrum": Web3(Web3.HTTPProvider("https://arb1.arbitrum.io/rpc")),
    }

    # Wallet manager (simplifié)
    class SimpleWalletManager:
        async def get_wallet(self, address):
            return None

    wallet_manager = SimpleWalletManager()

    # Bridge manager (simplifié)
    class SimpleBridgeManager:
        pass

    bridge_manager = SimpleBridgeManager()

    # Création du gestionnaire de transactions
    tx_manager = create_bridge_transaction_manager(
        config=config,
        web3_providers=web3_providers,
        wallet_manager=wallet_manager,
        bridge_manager=bridge_manager,
    )

    # Création d'une transaction
    transaction = await tx_manager.create_transaction(
        bridge_id="bridge_123",
        protocol="layerzero",
        chain="ethereum",
        tx_type=TransactionType.BRIDGE,
        from_address="0x...",
        to_address="0x...",
        value=Decimal("0.1"),
        gas_strategy=GasStrategy.FAST,
    )

    print(f"Transaction créée: {transaction.to_dict()}")

    # Statistiques
    stats = tx_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await tx_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main_example())
