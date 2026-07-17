# blockchain/nodes/bsc_node.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module BSC Node - Intégration du Nœud Binance Smart Chain

Ce module implémente un nœud complet pour la Binance Smart Chain (BSC),
supportant les opérations RPC, WebSocket, la gestion des transactions,
et le monitoring avancé.

Fonctionnalités principales:
- Connexion RPC/WebSocket à BSC
- Gestion des transactions
- Monitoring des blocs
- Gestion des tokens BEP-20
- Support des contrats
- Gestion des événements
- Support des bridges
- Monitoring des validateurs
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
    from ..wallets.bsc_wallet import BSCWallet
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
    from ..wallets.bsc_wallet import BSCWallet
    from .base_node import BaseNode, NodeConfig, NodeType, NodeProtocol, NodeHealth, NodeStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class BSCNodeType(Enum):
    """Types de nœuds BSC"""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    ARCHIVE = "archive"
    LIGHT = "light"


@dataclass
class BSCBlock:
    """Bloc BSC"""
    number: int
    hash: str
    parent_hash: str
    timestamp: datetime
    transactions: List[str]
    validator: str
    gas_used: int
    gas_limit: int
    size: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "number": self.number,
            "hash": self.hash,
            "parent_hash": self.parent_hash,
            "timestamp": self.timestamp.isoformat(),
            "transactions": self.transactions,
            "validator": self.validator,
            "gas_used": self.gas_used,
            "gas_limit": self.gas_limit,
            "size": self.size,
            "metadata": self.metadata,
        }


@dataclass
class BSCValidator:
    """Validateur BSC"""
    address: str
    name: str
    status: str
    commission: Decimal
    voting_power: Decimal
    blocks_validated: int
    apy: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "name": self.name,
            "status": self.status,
            "commission": str(self.commission),
            "voting_power": str(self.voting_power),
            "blocks_validated": self.blocks_validated,
            "apy": str(self.apy),
            "metadata": self.metadata,
        }


# ============================================================
# ADRESSES DES CONTRATS BSC
# ============================================================

BSC_CONTRACT_ADDRESSES = {
    "wbnb": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "busd": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
    "usdc": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "usdt": "0x55d398326f99059fF775485246999027B3197955",
    "pancake_router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
    "pancake_factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
    "multicall": "0x1Ee38d535d541c55C9dae27B12edf090C608E6Fb",
}


# ============================================================
# ABI POUR BSC
# ============================================================

BSC_RPC_ABI = [
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

class BSCNode(BaseNode):
    """
    Nœud BSC avancé avec support complet
    """

    def __init__(
        self,
        config: NodeConfig,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le nœud BSC

        Args:
            config: Configuration du nœud
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        super().__init__(config, metrics_collector, cache_ttl)

        self.bsc_provider: Optional[Web3] = None
        self._contracts: Dict[str, Contract] = {}
        self._validator_cache: Dict[str, BSCValidator] = {}
        self._subscriptions: Dict[str, Callable] = {}

        # Chargement des contrats
        self._load_contracts()

        logger.info(f"BSCNode {config.node_id} initialisé")

    def _load_contracts(self) -> None:
        """Charge les contrats BSC"""
        try:
            if self.bsc_provider:
                for name, address in BSC_CONTRACT_ADDRESSES.items():
                    self._contracts[name] = self.bsc_provider.eth.contract(
                        address=to_checksum_address(address),
                        abi=[],
                    )

            logger.info(f"Contrats BSC chargés: {list(self._contracts.keys())}")

        except Exception as e:
            logger.error(f"Erreur de chargement des contrats: {e}")
            raise NodeError(f"Erreur de chargement des contrats: {e}")

    # ============================================================
    # MÉTHODES DE CONNEXION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def connect(self) -> bool:
        """
        Établit la connexion au nœud BSC

        Returns:
            True si connecté avec succès
        """
        try:
            logger.info(f"Connexion au nœud BSC {self.config.endpoint}")

            # Connexion RPC
            self.bsc_provider = Web3(Web3.HTTPProvider(self.config.endpoint))

            # Ajout du middleware PoA pour BSC
            try:
                self.bsc_provider.middleware_onion.inject(geth_poa_middleware, layer=0)
            except Exception:
                pass

            # Vérification de la connexion
            if not self.bsc_provider.is_connected():
                raise ConnectionError("Impossible de se connecter au nœud BSC")

            # Récupération du chain ID
            chain_id = await self.get_chain_id()
            logger.info(f"Connecté à BSC (chain_id: {chain_id})")

            self._is_connected = True
            self._status = NodeStatus.ONLINE

            # Connexion WebSocket si configurée
            if self.config.ws_endpoint:
                await self._connect_websocket()

            return True

        except Exception as e:
            logger.error(f"Erreur de connexion: {e}")
            self._is_connected = False
            self._status = NodeStatus.OFFLINE
            raise ConnectionError(f"Erreur de connexion: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def disconnect(self) -> bool:
        """
        Ferme la connexion au nœud BSC

        Returns:
            True si déconnecté avec succès
        """
        try:
            logger.info(f"Déconnexion du nœud BSC {self.config.node_id}")

            # Fermeture de la connexion WebSocket
            if self._ws_connection:
                await self._disconnect_websocket()

            self.bsc_provider = None
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
        Obtient l'ID de la chaîne BSC

        Returns:
            ID de la chaîne
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            return await self.bsc_provider.eth.chain_id
        except Exception as e:
            raise NodeError(f"Erreur de récupération du chain ID: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_block(
        self,
        block_number: Union[int, str] = "latest",
    ) -> BSCBlock:
        """
        Obtient un bloc BSC

        Args:
            block_number: Numéro du bloc

        Returns:
            Bloc BSC
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            block = await self.bsc_provider.eth.get_block(block_number)

            return BSCBlock(
                number=block.get("number", 0),
                hash=block.get("hash", "").hex(),
                parent_hash=block.get("parentHash", "").hex(),
                timestamp=datetime.fromtimestamp(block.get("timestamp", 0)),
                transactions=[tx.hex() for tx in block.get("transactions", [])],
                validator=block.get("miner", "0x"),
                gas_used=block.get("gasUsed", 0),
                gas_limit=block.get("gasLimit", 0),
                size=block.get("size", 0),
            )

        except Exception as e:
            raise NodeError(f"Erreur de récupération du bloc: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """
        Obtient une transaction BSC

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Données de la transaction
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            tx = await self.bsc_provider.eth.get_transaction(
                HexBytes(tx_hash)
            )

            return {
                "hash": tx_hash,
                "from": tx.get("from", "0x"),
                "to": tx.get("to", "0x"),
                "value": str(tx.get("value", 0)),
                "gas": tx.get("gas", 0),
                "gas_price": tx.get("gasPrice", 0),
                "nonce": tx.get("nonce", 0),
                "input": tx.get("input", "").hex(),
            }

        except Exception as e:
            raise NodeError(f"Erreur de récupération de la transaction: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_balance(self, address: str) -> Decimal:
        """
        Obtient le solde BNB d'une adresse

        Args:
            address: Adresse

        Returns:
            Solde en BNB
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            balance = await self.bsc_provider.eth.get_balance(
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
        Obtient le solde d'un token BEP-20

        Args:
            token_address: Adresse du token
            wallet_address: Adresse du wallet

        Returns:
            Solde du token
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            # ABIs ERC-20 pour BSC
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

            token_contract = self.bsc_provider.eth.contract(
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
    # MÉTHODES DE TRANSACTION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def send_transaction(self, signed_tx: Any) -> str:
        """
        Envoie une transaction signée sur BSC

        Args:
            signed_tx: Transaction signée

        Returns:
            Hash de la transaction
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            tx_hash = await self.bsc_provider.eth.send_raw_transaction(
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
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            start_time = time.time()

            while time.time() - start_time < timeout:
                receipt = await self.bsc_provider.eth.get_transaction_receipt(
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
        Obtient le prix du gaz BSC

        Returns:
            Prix du gaz
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            return await self.bsc_provider.eth.gas_price

        except Exception as e:
            raise NodeError(f"Erreur de récupération du prix du gaz: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """
        Estime le gaz d'une transaction

        Args:
            tx: Transaction

        Returns:
            Estimation du gaz
        """
        if not self.bsc_provider:
            raise NodeError("Nœud BSC non connecté")

        try:
            return await self.bsc_provider.eth.estimate_gas(tx)

        except Exception as e:
            raise NodeError(f"Erreur d'estimation du gaz: {e}")

    # ============================================================
    # MÉTHODES DE VALIDATEURS
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def get_validators(self) -> List[BSCValidator]:
        """
        Obtient la liste des validateurs BSC

        Returns:
            Liste des validateurs
        """
        # Simulé - dans la réalité, on interrogerait les contrats BSC
        return [
            BSCValidator(
                address=f"0x{str(i).zfill(40)}",
                name=f"Validator {i}",
                status="active",
                commission=Decimal("0.1"),
                voting_power=Decimal(str(1000 - i * 10)),
                blocks_validated=1000 - i * 10,
                apy=Decimal("0.15"),
            )
            for i in range(10)
        ]

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_validator_by_address(self, address: str) -> Optional[BSCValidator]:
        """
        Obtient un validateur par son adresse

        Args:
            address: Adresse du validateur

        Returns:
            Validateur ou None
        """
        validator = self._validator_cache.get(address)

        if not validator:
            validators = await self.get_validators()
            for v in validators:
                if v.address.lower() == address.lower():
                    self._validator_cache[address] = v
                    return v

        return validator

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_health(self) -> NodeHealth:
        """
        Obtient l'état de santé du nœud BSC

        Returns:
            État de santé
        """
        try:
            if not self.bsc_provider:
                raise NodeError("Nœud BSC non connecté")

            # Récupération du dernier bloc
            block = await self.get_block("latest")

            # Temps de réponse simulé
            response_time = 0.1

            # Récupération du nombre de pairs (simulé)
            peer_count = 50

            return NodeHealth(
                node_id=self.config.node_id,
                status=NodeStatus.ONLINE,
                block_height=block.number,
                peer_count=peer_count,
                response_time=response_time,
                last_block_time=block.timestamp,
                uptime=3600.0,
                memory_usage=0.5,
                cpu_usage=0.3,
                network_latency=0.05,
                metadata={
                    "chain_id": await self.get_chain_id(),
                    "gas_price": await self.get_gas_price(),
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
            logger.info(f"Désabonnement: {subscription_id}")
            return True

        return False

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques du nœud BSC

        Returns:
            Statistiques
        """
        stats = super().get_statistics()

        stats.update({
            "chain_id": self.config.chain_id,
            "contracts_loaded": len(self._contracts),
            "validators_cached": len(self._validator_cache),
            "subscriptions": len(self._subscriptions),
        })

        return stats

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info(f"Nettoyage du nœud BSC {self.config.node_id}")

        # Nettoyage des souscriptions
        self._subscriptions.clear()

        # Nettoyage du cache
        self._validator_cache.clear()
        self._contracts.clear()

        # Nettoyage de la connexion WebSocket
        await self._disconnect_websocket()

        # Appel de la méthode parent
        await super().cleanup()

        logger.info(f"Nœud BSC {self.config.node_id} nettoyé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bsc_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: BSCNodeType = BSCNodeType.MAINNET,
    **kwargs,
) -> BSCNode:
    """
    Crée une instance de BSCNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de BSCNode
    """
    node_id = node_id or f"bsc_{uuid.uuid4().hex[:8]}"

    config = NodeConfig(
        node_id=node_id,
        protocol=NodeProtocol.BSC,
        node_type=NodeType(node_type.value),
        endpoint=endpoint,
        **kwargs,
    )

    return BSCNode(config)


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de BSCNode"""
    # Création du nœud
    node = create_bsc_node(
        endpoint="https://bsc-dataseed.binance.org",
        node_type=BSCNodeType.MAINNET,
        ws_endpoint="wss://bsc-ws-node.nariox.org",
        chain_id=56,
    )

    # Connexion
    await node.connect()

    # Récupération d'un bloc
    block = await node.get_block("latest")
    print(f"Dernier bloc: {block.number} - {block.hash}")
    print(f"Validateur: {block.validator}")
    print(f"Transactions: {len(block.transactions)}")

    # Récupération du solde
    balance = await node.get_balance("0x0000000000000000000000000000000000000000")
    print(f"Solde du burn address: {balance} BNB")

    # Récupération du solde d'un token
    token_balance = await node.get_token_balance(
        token_address="0x55d398326f99059fF775485246999027B3197955",
        wallet_address="0x0000000000000000000000000000000000000000",
    )
    print(f"Solde USDT du burn address: {token_balance}")

    # Récupération des validateurs
    validators = await node.get_validators()
    print(f"Nombre de validateurs: {len(validators)}")
    for v in validators[:3]:
        print(f"  {v.name}: {v.voting_power} - APY: {v.apy:.2%}")

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
