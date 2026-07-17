# blockchain/nodes/eth_node.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module ETH Node - Intégration du Nœud Ethereum

Ce module implémente un nœud complet pour Ethereum,
supportant les opérations RPC, WebSocket, la gestion des transactions,
le monitoring avancé, et les fonctionnalités spécifiques à Ethereum.

Fonctionnalités principales:
- Connexion RPC/WebSocket à Ethereum
- Gestion des transactions
- Monitoring des blocs
- Gestion des tokens ERC-20
- Support des contrats
- Gestion des événements
- Support des logs
- Monitoring des validateurs (post-merge)
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
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
from eth_typing import Address, ChecksumAddress, HexStr
from hexbytes import HexBytes
from eth_utils import to_checksum_address, is_address, to_hex

# Import des modules internes
try:
    from ..configs.blockchain_config import BlockchainConfig
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.ethereum_wallet import EthereumWallet
    from .base_node import BaseNode, NodeConfig, NodeType, NodeProtocol, NodeHealth, NodeStatus
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
    from ..wallets.ethereum_wallet import EthereumWallet
    from .base_node import BaseNode, NodeConfig, NodeType, NodeProtocol, NodeHealth, NodeStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class ETHNodeType(Enum):
    """Types de nœuds Ethereum"""
    MAINNET = "mainnet"
    GOERLI = "goerli"
    SEPOLIA = "sepolia"
    HOLESKY = "holesky"
    ARCHIVE = "archive"
    LIGHT = "light"


class ETHSyncMode(Enum):
    """Modes de synchronisation"""
    FULL = "full"
    SNAP = "snap"
    LIGHT = "light"
    ARCHIVE = "archive"


@dataclass
class ETHBlock:
    """Bloc Ethereum"""
    number: int
    hash: str
    parent_hash: str
    timestamp: datetime
    transactions: List[str]
    miner: str
    gas_used: int
    gas_limit: int
    base_fee_per_gas: int
    size: int
    difficulty: int
    total_difficulty: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "number": self.number,
            "hash": self.hash,
            "parent_hash": self.parent_hash,
            "timestamp": self.timestamp.isoformat(),
            "transactions": self.transactions,
            "miner": self.miner,
            "gas_used": self.gas_used,
            "gas_limit": self.gas_limit,
            "base_fee_per_gas": self.base_fee_per_gas,
            "size": self.size,
            "difficulty": self.difficulty,
            "total_difficulty": self.total_difficulty,
            "metadata": self.metadata,
        }


@dataclass
class ETHTransaction:
    """Transaction Ethereum"""
    hash: str
    from_address: str
    to_address: str
    value: Decimal
    gas: int
    gas_price: int
    nonce: int
    input_data: str
    transaction_type: str
    max_fee_per_gas: Optional[int] = None
    max_priority_fee_per_gas: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "hash": self.hash,
            "from": self.from_address,
            "to": self.to_address,
            "value": str(self.value),
            "gas": self.gas,
            "gas_price": self.gas_price,
            "nonce": self.nonce,
            "input_data": self.input_data,
            "transaction_type": self.transaction_type,
            "max_fee_per_gas": self.max_fee_per_gas,
            "max_priority_fee_per_gas": self.max_priority_fee_per_gas,
            "metadata": self.metadata,
        }


@dataclass
class ETHLog:
    """Log Ethereum"""
    address: str
    topics: List[str]
    data: str
    block_number: int
    transaction_hash: str
    log_index: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "topics": self.topics,
            "data": self.data,
            "block_number": self.block_number,
            "transaction_hash": self.transaction_hash,
            "log_index": self.log_index,
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES DES CONTRATS ETHEREUM
# ============================================================

ETH_CONTRACT_ADDRESSES = {
    "weth": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    "usdc": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "usdt": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "dai": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
    "wbtc": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
    "uni": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    "aave": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
    "maker": "0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2",
    "chainlink": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
}


# ============================================================
# ABI POUR ETHEREUM
# ============================================================

ETH_RPC_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "chainId",
        "outputs": [{"name": "", "type": "uint256"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "blockNumber", "type": "uint256"}],
        "name": "getBlockByNumber",
        "outputs": [
            {"name": "block", "type": "tuple"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class ETHNode(BaseNode):
    """
    Nœud Ethereum avancé avec support complet
    """

    def __init__(
        self,
        config: NodeConfig,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le nœud Ethereum

        Args:
            config: Configuration du nœud
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, metrics_collector, cache_ttl)

        self.eth_provider: Optional[Web3] = None
        self._contracts: Dict[str, Contract] = {}
        self._subscriptions: Dict[str, Callable] = {}
        self._log_filters: Dict[str, Dict[str, Any]] = {}

        # Synchronisation
        self._sync_status: Dict[str, Any] = {}
        self._last_block = 0

        # Chargement des contrats
        self._load_contracts()

        logger.info(f"ETHNode {config.node_id} initialisé")

    def _load_contracts(self) -> None:
        """Charge les contrats Ethereum"""
        try:
            if self.eth_provider:
                for name, address in ETH_CONTRACT_ADDRESSES.items():
                    self._contracts[name] = self.eth_provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=[],
                    )

            logger.info(f"Contrats Ethereum chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur de chargement des contrats: {e}")
            raise NodeError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES DE CONNEXION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def connect(self) -> bool:
        """
        Établit la connexion au nœud Ethereum

        Returns:
            True si connecté avec succès
        """
        try:
            logger.info(f"Connexion au nœud Ethereum {self.config.endpoint}")

            # Connexion RPC
            self.eth_provider = Web3(Web3.HTTPProvider(self.config.endpoint))

            # Vérification de la connexion
            if not self.eth_provider.is_connected():
                raise ConnectionError("Impossible de se connecter au nœud Ethereum")

            # Récupération du chain ID
            chain_id = await self.get_chain_id()
            logger.info(f"Connecté à Ethereum (chain_id: {chain_id})")

            self._is_connected = True
            self._status = NodeStatus.ONLINE

            # Connexion WebSocket si configurée
            if self.config.ws_endpoint:
                await self._connect_websocket()

            # Récupération du dernier bloc
            block = await self.get_block("latest")
            self._last_block = block.number

            return True

        except Exception as e:
            logger.error(f"Erreur de connexion: {e}")
            self._is_connected = False
            self._status = NodeStatus.OFFLINE
            raise ConnectionError(f"Erreur de connexion: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def disconnect(self) -> bool:
        """
        Ferme la connexion au nœud Ethereum

        Returns:
            True si déconnecté avec succès
        """
        try:
            logger.info(f"Déconnexion du nœud Ethereum {self.config.node_id}")

            # Fermeture de la connexion WebSocket
            if self._ws_connection:
                await self._disconnect_websocket()

            # Nettoyage des filtres de logs
            self._log_filters.clear()

            self.eth_provider = None
            self._is_connected = False
            self._status = NodeStatus.OFFLINE

            logger.info("Déconnexion réussie")
            return True

        except Exception as e:
            logger.error(f"Erreur de déconnexion: {e}")
            return False

    # ============================================================
    # MÉTHODES DE CONNEXION WEBSOCKET
    # ============================================================

    async def _connect_websocket(self) -> bool:
        """Établit la connexion WebSocket"""
        try:
            if not self.config.ws_endpoint:
                return False

            logger.info(f"Connexion WebSocket à {self.config.ws_endpoint}")

            # Simulé - dans la réalité, on utiliserait websockets
            self._ws_connection = True

            # Démarrage du listener WebSocket
            asyncio.create_task(self._websocket_listener())

            return True

        except Exception as e:
            logger.error(f"Erreur de connexion WebSocket: {e}")
            return False

    async def _disconnect_websocket(self) -> None:
        """Ferme la connexion WebSocket"""
        try:
            if self._ws_connection:
                self._ws_connection = None
                logger.info("WebSocket déconnecté")

        except Exception as e:
            logger.warning(f"Erreur de déconnexion WebSocket: {e}")

    async def _websocket_listener(self) -> None:
        """Listene les événements WebSocket"""
        while self._ws_connection:
            try:
                # Simulé - dans la réalité, on recevrait des messages
                await asyncio.sleep(1)

            except Exception as e:
                logger.warning(f"Erreur de WebSocket: {e}")
                await asyncio.sleep(5)

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_chain_id(self) -> int:
        """
        Obtient l'ID de la chaîne Ethereum

        Returns:
            ID de la chaîne
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            return await self.eth_provider.eth.chain_id

        except Exception as e:
            raise NodeError(f"Erreur de récupération du chain ID: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_block(
        self,
        block_number: Union[int, str] = "latest",
    ) -> ETHBlock:
        """
        Obtient un bloc Ethereum

        Args:
            block_number: Numéro du bloc

        Returns:
            Bloc Ethereum
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            block = await self.eth_provider.eth.get_block(block_number)

            return ETHBlock(
                number=block.get("number", 0),
                hash=block.get("hash", "").hex(),
                parent_hash=block.get("parentHash", "").hex(),
                timestamp=datetime.fromtimestamp(block.get("timestamp", 0)),
                transactions=[tx.hex() for tx in block.get("transactions", [])],
                miner=block.get("miner", "0x"),
                gas_used=block.get("gasUsed", 0),
                gas_limit=block.get("gasLimit", 0),
                base_fee_per_gas=block.get("baseFeePerGas", 0),
                size=block.get("size", 0),
                difficulty=block.get("difficulty", 0),
                total_difficulty=block.get("totalDifficulty", 0),
            )

        except Exception as e:
            raise NodeError(f"Erreur de récupération du bloc: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_transaction(self, tx_hash: str) -> ETHTransaction:
        """
        Obtient une transaction Ethereum

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Transaction Ethereum
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            tx = await self.eth_provider.eth.get_transaction(
                HexBytes(tx_hash)
            )

            # Détection du type de transaction
            tx_type = "legacy"
            if tx.get("type") == 0:
                tx_type = "legacy"
            elif tx.get("type") == 1:
                tx_type = "access_list"
            elif tx.get("type") == 2:
                tx_type = "eip1559"

            return ETHTransaction(
                hash=tx_hash,
                from_address=tx.get("from", "0x"),
                to_address=tx.get("to", "0x"),
                value=Decimal(str(tx.get("value", 0))) / Decimal(1e18),
                gas=tx.get("gas", 0),
                gas_price=tx.get("gasPrice", 0),
                nonce=tx.get("nonce", 0),
                input_data=tx.get("input", "").hex(),
                transaction_type=tx_type,
                max_fee_per_gas=tx.get("maxFeePerGas"),
                max_priority_fee_per_gas=tx.get("maxPriorityFeePerGas"),
            )

        except Exception as e:
            raise NodeError(f"Erreur de récupération de la transaction: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_transaction_receipt(self, tx_hash: str) -> Dict[str, Any]:
        """
        Obtient le reçu d'une transaction

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Reçu de la transaction
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            receipt = await self.eth_provider.eth.get_transaction_receipt(
                HexBytes(tx_hash)
            )

            return {
                "status": receipt.get("status", 0),
                "block_number": receipt.get("blockNumber", 0),
                "transaction_hash": receipt.get("transactionHash", "").hex(),
                "gas_used": receipt.get("gasUsed", 0),
                "cumulative_gas_used": receipt.get("cumulativeGasUsed", 0),
                "contract_address": receipt.get("contractAddress", ""),
                "logs": [
                    {
                        "address": log.get("address", ""),
                        "data": log.get("data", "").hex(),
                        "topics": [t.hex() for t in log.get("topics", [])],
                    }
                    for log in receipt.get("logs", [])
                ],
            }

        except Exception as e:
            raise NodeError(f"Erreur de récupération du reçu: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_balance(self, address: str) -> Decimal:
        """
        Obtient le solde ETH d'une adresse

        Args:
            address: Adresse

        Returns:
            Solde en ETH
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            balance = await self.eth_provider.eth.get_balance(
                to_checksum_address(address)
            )
            return Decimal(str(balance)) / Decimal(1e18)

        except Exception as e:
            raise NodeError(f"Erreur de récupération du solde: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_token_balance(
        self,
        token_address: str,
        wallet_address: str,
    ) -> Decimal:
        """
        Obtient le solde d'un token ERC-20

        Args:
            token_address: Adresse du token
            wallet_address: Adresse du wallet

        Returns:
            Solde du token
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            # ABI ERC-20
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function",
                },
            ]

            token_contract = self.eth_provider.eth.contract(
                address=to_checksum_address(token_address),
                abi=erc20_abi,
            )

            balance = await token_contract.functions.balanceOf(
                to_checksum_address(wallet_address)
            ).call()

            decimals = await token_contract.functions.decimals().call()

            return Decimal(str(balance)) / Decimal(10 ** decimals)

        except Exception as e:
            raise NodeError(f"Erreur de récupération du solde du token: {e}")

    # ============================================================
    # MÉTHODES DE LOGS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_logs(
        self,
        from_block: Union[int, str] = "latest",
        to_block: Union[int, str] = "latest",
        address: Optional[str] = None,
        topics: Optional[List[str]] = None,
    ) -> List[ETHLog]:
        """
        Récupère les logs

        Args:
            from_block: Bloc de début
            to_block: Bloc de fin
            address: Adresse du contrat
            topics: Topics à filtrer

        Returns:
            Liste des logs
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            filter_params = {
                "fromBlock": from_block,
                "toBlock": to_block,
            }

            if address:
                filter_params["address"] = to_checksum_address(address)

            if topics:
                filter_params["topics"] = topics

            logs = await self.eth_provider.eth.get_logs(filter_params)

            return [
                ETHLog(
                    address=log.get("address", ""),
                    topics=[t.hex() for t in log.get("topics", [])],
                    data=log.get("data", "").hex(),
                    block_number=log.get("blockNumber", 0),
                    transaction_hash=log.get("transactionHash", "").hex(),
                    log_index=log.get("logIndex", 0),
                )
                for log in logs
            ]

        except Exception as e:
            raise NodeError(f"Erreur de récupération des logs: {e}")

    # ============================================================
    # MÉTHODES DE TRANSACTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def send_transaction(self, signed_tx: Any) -> str:
        """
        Envoie une transaction signée sur Ethereum

        Args:
            signed_tx: Transaction signée

        Returns:
            Hash de la transaction
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            tx_hash = await self.eth_provider.eth.send_raw_transaction(
                signed_tx
            )

            logger.info(f"Transaction envoyée: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            raise NodeError(f"Erreur d'envoi de transaction: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Attend la confirmation d'une transaction

        Args:
            tx_hash: Hash de la transaction
            timeout: Timeout en secondes

        Returns:
            Reçu de la transaction
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            start_time = time.time()

            while time.time() - start_time < timeout:
                receipt = await self.eth_provider.eth.get_transaction_receipt(
                    HexBytes(tx_hash)
                )

                if receipt:
                    return {
                        "status": receipt.get("status", 0),
                        "block_number": receipt.get("blockNumber", 0),
                        "gas_used": receipt.get("gasUsed", 0),
                        "transaction_hash": receipt.get("transactionHash", "").hex(),
                    }

                await asyncio.sleep(2)

            raise TimeoutError(f"Timeout de transaction: {tx_hash}")

        except Exception as e:
            raise NodeError(f"Erreur d'attente de transaction: {e}")

    # ============================================================
    # MÉTHODES DE GAS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_gas_price(self) -> int:
        """
        Obtient le prix du gaz Ethereum

        Returns:
            Prix du gaz
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            return await self.eth_provider.eth.gas_price

        except Exception as e:
            raise NodeError(f"Erreur de récupération du prix du gaz: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_priority_fee(self) -> int:
        """
        Obtient le frais de priorité (EIP-1559)

        Returns:
            Frais de priorité
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            # Simulé - dans la réalité, on utiliserait fee_history
            return 1000000000  # 1 Gwei

        except Exception as e:
            raise NodeError(f"Erreur de récupération du frais de priorité: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """
        Estime le gaz d'une transaction

        Args:
            tx: Transaction

        Returns:
            Estimation du gaz
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            return await self.eth_provider.eth.estimate_gas(tx)

        except Exception as e:
            raise NodeError(f"Erreur d'estimation du gaz: {e}")

    # ============================================================
    # MÉTHODES DE SYNC
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_sync_status(self) -> Dict[str, Any]:
        """
        Obtient le statut de synchronisation

        Returns:
            Statut de synchronisation
        """
        if not self.eth_provider:
            raise NodeError("Nœud Ethereum non connecté")

        try:
            status = await self.eth_provider.eth.syncing

            if isinstance(status, bool):
                return {"is_syncing": False}

            return {
                "is_syncing": True,
                "current_block": status.get("currentBlock", 0),
                "highest_block": status.get("highestBlock", 0),
                "starting_block": status.get("startingBlock", 0),
            }

        except Exception as e:
            raise NodeError(f"Erreur de récupération du statut de sync: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_health(self) -> NodeHealth:
        """
        Obtient l'état de santé du nœud Ethereum

        Returns:
            État de santé
        """
        try:
            if not self.eth_provider:
                raise NodeError("Nœud Ethereum non connecté")

            # Récupération du dernier bloc
            block = await self.get_block("latest")

            # Temps de réponse simulé
            response_time = 0.1

            # Statut de synchronisation
            sync_status = await self.get_sync_status()

            return NodeHealth(
                node_id=self.config.node_id,
                status=NodeStatus.ONLINE,
                block_height=block.number,
                peer_count=50,  # Simulé
                response_time=response_time,
                last_block_time=block.timestamp,
                uptime=3600.0,
                memory_usage=0.5,
                cpu_usage=0.3,
                network_latency=0.05,
                metadata={
                    "chain_id": await self.get_chain_id(),
                    "gas_price": await self.get_gas_price(),
                    "is_syncing": sync_status.get("is_syncing", False),
                },
            )

        except Exception as e:
            logger.error(f"Erreur de récupération de la santé: {e}")
            return NodeHealth(
                node_id=self.config.node_id,
                status=NodeStatus.ERROR,
                block_height=0,
                peer_count=0,
                response_time=0,
                last_block_time=datetime.now(),
                uptime=0,
                memory_usage=0,
                cpu_usage=0,
                network_latency=0,
                metadata={"error": str(e)},
            )

    # ============================================================
    # MÉTHODES DE SUBSCRIPTION
    # ============================================================

    async def subscribe_to_blocks(self, callback: Callable) -> str:
        """
        S'abonne aux nouveaux blocs

        Args:
            callback: Fonction à appeler pour chaque nouveau bloc

        Returns:
            ID de la souscription
        """
        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
        self._subscriptions[subscription_id] = callback

        logger.info(f"Abonnement aux blocs: {subscription_id}")
        return subscription_id

    async def subscribe_to_logs(
        self,
        filter_params: Dict[str, Any],
        callback: Callable,
    ) -> str:
        """
        S'abonne aux logs

        Args:
            filter_params: Paramètres du filtre
            callback: Fonction à appeler pour chaque log

        Returns:
            ID de la souscription
        """
        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
        self._subscriptions[subscription_id] = callback
        self._log_filters[subscription_id] = filter_params

        logger.info(f"Abonnement aux logs: {subscription_id}")
        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Se désabonne d'un événement

        Args:
            subscription_id: ID de la souscription

        Returns:
            True si désabonné avec succès
        """
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            self._log_filters.pop(subscription_id, None)
            logger.info(f"Désabonnement: {subscription_id}")
            return True

        return False

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques du nœud Ethereum

        Returns:
            Statistiques
        """
        stats = super().get_statistics()

        stats.update({
            "chain_id": self.config.chain_id,
            "contracts_loaded": len(self._contracts),
            "subscriptions": len(self._subscriptions),
            "log_filters": len(self._log_filters),
            "last_block": self._last_block,
        })

        return stats

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info(f"Nettoyage du nœud Ethereum {self.config.node_id}")

        # Nettoyage des souscriptions
        self._subscriptions.clear()
        self._log_filters.clear()

        # Nettoyage des contrats
        self._contracts.clear()

        # Nettoyage de la connexion WebSocket
        await self._disconnect_websocket()

        # Appel de la méthode parent
        await super().cleanup()

        logger.info(f"Nœud Ethereum {self.config.node_id} nettoyé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_eth_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: ETHNodeType = ETHNodeType.MAINNET,
    **kwargs,
) -> ETHNode:
    """
    Crée une instance de ETHNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de ETHNode
    """
    node_id = node_id or f"eth_{uuid.uuid4().hex[:8]}"

    config = NodeConfig(
        node_id=node_id,
        protocol=NodeProtocol.ETHEREUM,
        node_type=NodeType(node_type.value),
        endpoint=endpoint,
        **kwargs,
    )

    return ETHNode(config)


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de ETHNode"""
    # Création du nœud
    node = create_eth_node(
        endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
        node_type=ETHNodeType.MAINNET,
        ws_endpoint="wss://mainnet.infura.io/ws/v3/YOUR_KEY",
        chain_id=1,
    )

    # Connexion
    await node.connect()

    # Récupération d'un bloc
    block = await node.get_block("latest")
    print(f"Dernier bloc: {block.number} - {block.hash}")
    print(f"Transactions: {len(block.transactions)}")
    print(f"Base fee: {block.base_fee_per_gas}")

    # Récupération d'une transaction
    tx = await node.get_transaction("0x...")
    print(f"Transaction: {tx.hash}")
    print(f"Valeur: {tx.value} ETH")

    # Récupération du solde
    balance = await node.get_balance("0x0000000000000000000000000000000000000000")
    print(f"Solde du burn address: {balance} ETH")

    # Récupération du solde d'un token
    token_balance = await node.get_token_balance(
        token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        wallet_address="0x0000000000000000000000000000000000000000",
    )
    print(f"Solde USDC du burn address: {token_balance}")

    # Souscription aux blocs
    async def on_new_block(block):
        print(f"Nouveau bloc: {block.number}")

    sub_id = await node.subscribe_to_blocks(on_new_block)
    print(f"Souscription créée: {sub_id}")

    # Désabonnement
    await node.unsubscribe(sub_id)

    # Statistiques
    stats = node.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await node.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
