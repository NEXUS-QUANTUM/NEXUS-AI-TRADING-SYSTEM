# blockchain/nodes/base_node.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Base Node - Classe de Base pour les Nœuds Blockchain

Ce module définit la classe de base abstraite pour tous les nœuds blockchain,
fournissant l'interface commune, les fonctionnalités partagées, et les
mécanismes de base pour l'interaction avec les nœuds.

Fonctionnalités principales:
- Interface unifiée pour tous les nœuds blockchain
- Gestion des connexions RPC
- Monitoring des nœuds
- Gestion des erreurs
- Support multi-protocoles
- Gestion des clés
- Gestion des transactions
"""

import asyncio
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
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
from functools import wraps

import aiohttp
import web3
from web3 import Web3
from web3.middleware import geth_poa_middleware
from eth_account import Account

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..wallets.base_wallet import BaseWallet

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NodeType(Enum):
    """Types de nœuds"""
    FULL = "full"
    LIGHT = "light"
    ARCHIVE = "archive"
    VALIDATOR = "validator"
    RELAY = "relay"
    RPC = "rpc"
    WEBSOCKET = "websocket"


class NodeStatus(Enum):
    """Statuts des nœuds"""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class NodeProtocol(Enum):
    """Protocoles supportés"""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    SOLANA = "solana"
    BITCOIN = "bitcoin"


@dataclass
class NodeHealth:
    """État de santé d'un nœud"""
    node_id: str
    status: NodeStatus
    block_height: int
    peer_count: int
    response_time: float
    last_block_time: datetime
    uptime: float
    memory_usage: float
    cpu_usage: float
    network_latency: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "block_height": self.block_height,
            "peer_count": self.peer_count,
            "response_time": self.response_time,
            "last_block_time": self.last_block_time.isoformat(),
            "uptime": self.uptime,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "network_latency": self.network_latency,
            "metadata": self.metadata,
        }


@dataclass
class NodeConfig:
    """Configuration d'un nœud"""
    node_id: str
    protocol: NodeProtocol
    node_type: NodeType
    endpoint: str
    backup_endpoints: List[str] = field(default_factory=list)
    ws_endpoint: Optional[str] = None
    chain_id: Optional[int] = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "protocol": self.protocol.value,
            "node_type": self.node_type.value,
            "endpoint": self.endpoint,
            "backup_endpoints": self.backup_endpoints,
            "ws_endpoint": self.ws_endpoint,
            "chain_id": self.chain_id,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE DE BASE ABSTRAITE
# ============================================================

class BaseNode(ABC):
    """
    Classe de base abstraite pour tous les nœuds blockchain
    """

    def __init__(
        self,
        config: NodeConfig,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le nœud de base

        Args:
            config: Configuration du nœud
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # État interne
        self._status = NodeStatus.UNKNOWN
        self._health: Optional[NodeHealth] = None
        self._connection: Optional[Any] = None
        self._ws_connection: Optional[Any] = None
        self._is_connected = False
        self._last_activity = datetime.now()
        self._active_requests: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=config.max_retries,
            initial_delay=config.retry_delay,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            half_open_attempts=3,
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache
        self._cache: Dict[str, Tuple[float, Any]] = {}

        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None

        # Métriques
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._total_response_time = 0.0

        # Initialisation de la session
        self._init_session()

        logger.info(f"BaseNode {config.node_id} initialisé")

    def _init_session(self) -> None:
        """Initialise la session HTTP"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers={
                    "User-Agent": "NEXUS-AI-TRADING/1.0",
                    "Content-Type": "application/json",
                },
            )

    # ============================================================
    # MÉTHODES ABSTRAITES (À IMPLÉMENTER)
    # ============================================================

    @abstractmethod
    async def connect(self) -> bool:
        """
        Établit la connexion au nœud

        Returns:
            True si connecté avec succès
        """
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Ferme la connexion au nœud

        Returns:
            True si déconnecté avec succès
        """
        pass

    @abstractmethod
    async def get_block(self, block_number: int) -> Dict[str, Any]:
        """
        Obtient un bloc par son numéro

        Args:
            block_number: Numéro du bloc

        Returns:
            Données du bloc
        """
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """
        Obtient une transaction par son hash

        Args:
            tx_hash: Hash de la transaction

        Returns:
            Données de la transaction
        """
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> Decimal:
        """
        Obtient le solde d'une adresse

        Args:
            address: Adresse

        Returns:
            Solde
        """
        pass

    @abstractmethod
    async def send_transaction(self, signed_tx: Any) -> str:
        """
        Envoie une transaction signée

        Args:
            signed_tx: Transaction signée

        Returns:
            Hash de la transaction
        """
        pass

    @abstractmethod
    async def get_health(self) -> NodeHealth:
        """
        Obtient l'état de santé du nœud

        Returns:
            État de santé
        """
        pass

    # ============================================================
    # MÉTHODES DE BASE COMMUNES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def check_connection(self) -> bool:
        """
        Vérifie la connexion au nœud

        Returns:
            True si connecté
        """
        try:
            if not self._connection:
                return await self.connect()

            # Test de connexion
            await self.get_health()
            return True

        except Exception as e:
            logger.warning(f"Erreur de connexion: {e}")
            return False

    async def get_status(self) -> NodeStatus:
        """
        Obtient le statut du nœud

        Returns:
            Statut du nœud
        """
        try:
            health = await self.get_health()
            self._status = health.status
            return self._status

        except Exception:
            self._status = NodeStatus.OFFLINE
            return self._status

    async def is_healthy(self) -> bool:
        """
        Vérifie si le nœud est sain

        Returns:
            True si sain
        """
        try:
            health = await self.get_health()
            return health.status == NodeStatus.ONLINE

        except Exception:
            return False

    async def wait_for_block(
        self,
        target_block: int,
        timeout: int = 300,
        interval: int = 5,
    ) -> bool:
        """
        Attend qu'un bloc soit atteint

        Args:
            target_block: Bloc cible
            timeout: Timeout en secondes
            interval: Intervalle de vérification

        Returns:
            True si atteint
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                current_block = await self.get_block("latest")
                if current_block.get("number", 0) >= target_block:
                    return True

                await asyncio.sleep(interval)

            except Exception as e:
                logger.warning(f"Erreur d'attente de bloc: {e}")
                await asyncio.sleep(interval)

        return False

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """
        Obtient les statistiques du nœud

        Returns:
            Statistiques
        """
        total_requests = self._request_count
        success_rate = self._success_count / max(1, total_requests)
        avg_response_time = self._total_response_time / max(1, total_requests)

        return {
            "node_id": self.config.node_id,
            "protocol": self.config.protocol.value,
            "status": self._status.value,
            "total_requests": total_requests,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "is_connected": self._is_connected,
            "active_requests": len(self._active_requests),
            "cache_size": len(self._cache),
            "circuit_breaker": {
                "is_available": self.circuit_breaker.is_available(),
                "failure_count": self.circuit_breaker.failure_count,
                "success_count": self.circuit_breaker.success_count,
            },
        }

    def get_config(self) -> NodeConfig:
        """
        Obtient la configuration du nœud

        Returns:
            Configuration
        """
        return self.config

    # ============================================================
    # MÉTHODES UTILITAIRES PROTÉGÉES
    # ============================================================

    def _generate_request_id(self) -> str:
        """Génère un ID de requête unique"""
        return f"req_{uuid.uuid4().hex[:12]}"

    def _get_cache_key(self, *args, **kwargs) -> str:
        """Génère une clé de cache"""
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
        return hashlib.sha256(":".join(key_parts).encode()).hexdigest()

    async def _cache_get(self, key: str) -> Optional[Any]:
        """Obtient une valeur du cache"""
        if key in self._cache:
            cached_time, value = self._cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return value
        return None

    async def _cache_set(self, key: str, value: Any) -> None:
        """Définit une valeur dans le cache"""
        self._cache[key] = (time.time(), value)

    def _update_metrics(self, success: bool, response_time: float) -> None:
        """Met à jour les métriques"""
        self._request_count += 1
        if success:
            self._success_count += 1
        else:
            self._failure_count += 1
        self._total_response_time += response_time

    async def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Gère une erreur"""
        error_info = {
            "node_id": self.config.node_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
        }

        logger.error(f"Erreur de nœud: {error_info}")

        # Métriques
        self.metrics.record_increment(
            "node_error",
            1,
            {
                "node_id": self.config.node_id,
                "protocol": self.config.protocol.value,
                "error_type": type(error).__name__,
            },
        )

        return error_info

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """
        Nettoie les ressources

        Cette méthode doit être appelée lors de l'arrêt
        """
        logger.info(f"Nettoyage du nœud {self.config.node_id}")

        # Déconnexion
        await self.disconnect()

        # Fermeture de la session
        if self._session:
            await self._session.close()
            self._session = None

        # Nettoyage du cache
        self._cache.clear()

        # Nettoyage des requêtes actives
        for request_id in list(self._active_requests.keys()):
            try:
                self._active_requests[request_id]["status"] = "cancelled"
            except Exception as e:
                logger.warning(f"Erreur d'annulation de {request_id}: {e}")

        # Fermeture du thread pool
        self._executor.shutdown(wait=True)

        logger.info(f"Nœud {self.config.node_id} nettoyé")

    # ============================================================
    # MÉTHODES DE CONTEXTE
    # ============================================================

    async def __aenter__(self):
        """Support du contexte async"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support du contexte async"""
        await self.cleanup()


# ============================================================
# DÉCORATEURS UTILITAIRES
# ============================================================

def measure_time():
    """
    Décorateur pour mesurer le temps d'exécution
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()

            try:
                result = await func(self, *args, **kwargs)
                elapsed = time.time() - start_time

                # Métriques
                self.metrics.record_timing(
                    f"node_{func.__name__}_time",
                    elapsed,
                    {"node_id": self.config.node_id},
                )
                self._update_metrics(True, elapsed)

                return result

            except Exception as e:
                elapsed = time.time() - start_time
                self._update_metrics(False, elapsed)
                logger.debug(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
                raise

        return wrapper
    return decorator


def with_retry(max_attempts: int = 3):
    """
    Décorateur pour retry avec backoff
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            attempt = 0
            last_error = None

            while attempt < max_attempts:
                try:
                    return await func(self, *args, **kwargs)

                except (ConnectionError, TimeoutError) as e:
                    last_error = e
                    attempt += 1

                    if attempt < max_attempts:
                        delay = 2 ** attempt
                        logger.warning(
                            f"Tentative {attempt}/{max_attempts} échouée, "
                            f"nouvel essai dans {delay}s: {e}"
                        )
                        await asyncio.sleep(delay)

            raise last_error or Exception("Max retries exceeded")

        return wrapper
    return decorator


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de la classe de base"""
    # Configuration
    config = NodeConfig(
        node_id="mainnet_1",
        protocol=NodeProtocol.ETHEREUM,
        node_type=NodeType.FULL,
        endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
        backup_endpoints=[
            "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY",
        ],
        ws_endpoint="wss://mainnet.infura.io/ws/v3/YOUR_KEY",
        chain_id=1,
        timeout=30,
        max_retries=3,
        retry_delay=1.0,
    )

    # Création d'une implémentation de test
    class TestNode(BaseNode):
        async def connect(self):
            self._is_connected = True
            self._status = NodeStatus.ONLINE
            return True

        async def disconnect(self):
            self._is_connected = False
            self._status = NodeStatus.OFFLINE
            return True

        async def get_block(self, block_number):
            return {"number": block_number, "hash": "0x..."}

        async def get_transaction(self, tx_hash):
            return {"hash": tx_hash, "from": "0x...", "to": "0x..."}

        async def get_balance(self, address):
            return Decimal("1.5")

        async def send_transaction(self, signed_tx):
            return "0x..."

        async def get_health(self):
            return NodeHealth(
                node_id=self.config.node_id,
                status=NodeStatus.ONLINE,
                block_height=10000000,
                peer_count=50,
                response_time=0.1,
                last_block_time=datetime.now(),
                uptime=3600.0,
                memory_usage=0.5,
                cpu_usage=0.3,
                network_latency=0.05,
            )

    # Utilisation
    node = TestNode(config)

    # Connexion
    connected = await node.connect()
    print(f"Connecté: {connected}")

    # Récupération d'un bloc
    block = await node.get_block(10000000)
    print(f"Bloc: {block}")

    # Récupération d'une transaction
    tx = await node.get_transaction("0x...")
    print(f"Transaction: {tx}")

    # Récupération du solde
    balance = await node.get_balance("0x...")
    print(f"Solde: {balance}")

    # Statistiques
    stats = node.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await node.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
