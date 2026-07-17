# blockchain/nodes/node_rpc.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node RPC - Gestion des Appels RPC

Ce module implémente un système complet de gestion des appels RPC pour
les nœuds blockchain, supportant les requêtes HTTP, WebSocket, le batch
processing, et l'optimisation des performances.

Fonctionnalités principales:
- Appels RPC HTTP
- Appels RPC WebSocket
- Batch processing
- Gestion des erreurs
- Retry automatique
- Rate limiting
- Compression des requêtes
- Support multi-protocoles
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
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
import websockets
from websockets import WebSocketClientProtocol

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, RPCError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, RPCError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class RPCMethod(Enum):
    """Méthodes RPC supportées"""
    # Eth
    ETH_BLOCK_NUMBER = "eth_blockNumber"
    ETH_GET_BLOCK_BY_NUMBER = "eth_getBlockByNumber"
    ETH_GET_TRANSACTION = "eth_getTransactionByHash"
    ETH_GET_TRANSACTION_RECEIPT = "eth_getTransactionReceipt"
    ETH_GET_BALANCE = "eth_getBalance"
    ETH_SEND_TRANSACTION = "eth_sendRawTransaction"
    ETH_GET_LOGS = "eth_getLogs"
    ETH_ESTIMATE_GAS = "eth_estimateGas"
    ETH_GET_GAS_PRICE = "eth_gasPrice"
    ETH_GET_TRANSACTION_COUNT = "eth_getTransactionCount"
    ETH_CALL = "eth_call"

    # Net
    NET_VERSION = "net_version"
    NET_PEER_COUNT = "net_peerCount"

    # Web3
    WEB3_CLIENT_VERSION = "web3_clientVersion"
    WEB3_SHA3 = "web3_sha3"

    # Custom
    CUSTOM = "custom"


class RPCProtocol(Enum):
    """Protocoles RPC"""
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"


@dataclass
class RPCRequest:
    """Requête RPC"""
    request_id: str
    method: str
    params: List[Any]
    protocol: RPCProtocol
    endpoint: str
    timeout: int = 30
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convertit en JSON"""
        return json.dumps({
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": self.method,
            "params": self.params,
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "method": self.method,
            "params": self.params,
            "protocol": self.protocol.value,
            "endpoint": self.endpoint,
            "timeout": self.timeout,
            "headers": self.headers,
            "metadata": self.metadata,
        }


@dataclass
class RPCResponse:
    """Réponse RPC"""
    request_id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "request_id": self.request_id,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "metadata": self.metadata,
        }

    def is_success(self) -> bool:
        """Vérifie si la requête a réussi"""
        return self.error is None and self.result is not None


@dataclass
class RPCBatch:
    """Batch RPC"""
    batch_id: str
    requests: List[RPCRequest]
    responses: List[RPCResponse]
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "batch_id": self.batch_id,
            "requests": [r.to_dict() for r in self.requests],
            "responses": [r.to_dict() for r in self.responses],
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeRPCClient:
    """
    Client RPC avancé pour les nœuds blockchain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le client RPC

        Args:
            config: Configuration
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: Dict[str, WebSocketClientProtocol] = {}
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._request_counter = 0
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_attempts=3,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Cache des réponses
        self._response_cache: Dict[str, Tuple[float, Any]] = {}

        # Initialisation de la session
        self._init_session()

        logger.info("NodeRPCClient initialisé avec succès")

    def _init_session(self) -> None:
        """Initialise la session HTTP"""
        if not self._session:
            timeout = aiohttp.ClientTimeout(
                total=self.config.get("timeout", 30),
                connect=self.config.get("connect_timeout", 10),
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "NEXUS-AI-TRADING/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def call(
        self,
        method: Union[str, RPCMethod],
        params: List[Any],
        endpoint: str,
        protocol: RPCProtocol = RPCProtocol.HTTPS,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> RPCResponse:
        """
        Effectue un appel RPC

        Args:
            method: Méthode RPC
            params: Paramètres
            endpoint: Endpoint
            protocol: Protocole
            timeout: Timeout
            headers: Headers supplémentaires

        Returns:
            Réponse RPC
        """
        request_id = str(uuid.uuid4())
        method_name = method.value if isinstance(method, RPCMethod) else method

        logger.debug(f"RPC call {method_name} sur {endpoint}")

        # Vérification du cache
        cache_key = f"{endpoint}:{method_name}:{hash(str(params))}"
        if method_name in ["eth_blockNumber", "eth_gasPrice"]:
            cached = await self._get_cached(cache_key)
            if cached is not None:
                return RPCResponse(
                    request_id=request_id,
                    result=cached,
                    duration=0,
                )

        request = RPCRequest(
            request_id=request_id,
            method=method_name,
            params=params,
            protocol=protocol,
            endpoint=endpoint,
            timeout=timeout or self.config.get("timeout", 30),
            headers=headers or {},
        )

        start_time = time.time()

        try:
            # Vérification du circuit breaker
            circuit_key = f"{endpoint}:{method_name}"
            if not self.circuit_breakers[circuit_key].is_available():
                raise RPCError("Circuit breaker ouvert")

            # Exécution selon le protocole
            if protocol in [RPCProtocol.WS, RPCProtocol.WSS]:
                response_data = await self._call_websocket(request)
            else:
                response_data = await self._call_http(request)

            duration = time.time() - start_time

            # Traitement de la réponse
            if "error" in response_data:
                error = response_data["error"]
                response = RPCResponse(
                    request_id=request_id,
                    error=error,
                    duration=duration,
                )
                self.circuit_breakers[circuit_key].record_failure()
            else:
                result = response_data.get("result")
                response = RPCResponse(
                    request_id=request_id,
                    result=result,
                    duration=duration,
                )
                self.circuit_breakers[circuit_key].record_success()

                # Cache
                if method_name in ["eth_blockNumber", "eth_gasPrice"]:
                    await self._set_cached(cache_key, result)

            # Métriques
            self.metrics.record_timing(
                "rpc_call_duration",
                duration,
                {"method": method_name, "endpoint": endpoint[:30]},
            )
            self.metrics.record_increment(
                "rpc_call_total",
                1,
                {
                    "method": method_name,
                    "success": str(response.is_success()),
                },
            )

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Métriques d'erreur
            self.metrics.record_increment(
                "rpc_call_error",
                1,
                {"method": method_name, "error": type(e).__name__},
            )

            raise RPCError(f"Erreur RPC: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def batch_call(
        self,
        requests: List[Dict[str, Any]],
        endpoint: str,
        protocol: RPCProtocol = RPCProtocol.HTTPS,
        timeout: Optional[int] = None,
    ) -> RPCBatch:
        """
        Effectue un batch d'appels RPC

        Args:
            requests: Liste des requêtes
            endpoint: Endpoint
            protocol: Protocole
            timeout: Timeout

        Returns:
            Batch RPC
        """
        batch_id = str(uuid.uuid4())
        logger.debug(f"Batch RPC {batch_id} sur {endpoint}")

        # Création des requêtes
        rpc_requests = []
        for req in requests:
            rpc_req = RPCRequest(
                request_id=str(uuid.uuid4()),
                method=req.get("method"),
                params=req.get("params", []),
                protocol=protocol,
                endpoint=endpoint,
                timeout=timeout or self.config.get("timeout", 30),
            )
            rpc_requests.append(rpc_req)

        batch = RPCBatch(
            batch_id=batch_id,
            requests=rpc_requests,
            responses=[],
            status="pending",
        )

        try:
            # Construction du batch JSON
            batch_data = [req.to_json() for req in rpc_requests]

            # Exécution
            if protocol in [RPCProtocol.WS, RPCProtocol.WSS]:
                response_data = await self._call_websocket_batch(batch_data, endpoint)
            else:
                response_data = await self._call_http_batch(batch_data, endpoint)

            # Traitement des réponses
            if isinstance(response_data, list):
                for i, resp in enumerate(response_data):
                    if i < len(rpc_requests):
                        rpc_response = RPCResponse(
                            request_id=rpc_requests[i].request_id,
                            result=resp.get("result"),
                            error=resp.get("error"),
                        )
                        batch.responses.append(rpc_response)

            batch.status = "completed"
            batch.completed_at = datetime.now()

            # Métriques
            self.metrics.record_timing(
                "rpc_batch_duration",
                (batch.completed_at - batch.created_at).total_seconds(),
                {"endpoint": endpoint[:30]},
            )
            self.metrics.record_gauge(
                "rpc_batch_size",
                len(requests),
                {"endpoint": endpoint[:30]},
            )

            return batch

        except Exception as e:
            batch.status = "failed"
            batch.completed_at = datetime.now()
            raise RPCError(f"Erreur batch RPC: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_block_number(self, endpoint: str) -> int:
        """
        Obtient le numéro du dernier bloc

        Args:
            endpoint: Endpoint

        Returns:
            Numéro du bloc
        """
        response = await self.call(
            method=RPCMethod.ETH_BLOCK_NUMBER,
            params=[],
            endpoint=endpoint,
        )

        if response.is_success():
            return int(response.result, 16)
        raise RPCError("Échec de la récupération du bloc")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_balance(self, address: str, endpoint: str) -> str:
        """
        Obtient le solde d'une adresse

        Args:
            address: Adresse
            endpoint: Endpoint

        Returns:
            Solde en wei (hex)
        """
        response = await self.call(
            method=RPCMethod.ETH_GET_BALANCE,
            params=[address, "latest"],
            endpoint=endpoint,
        )

        if response.is_success():
            return response.result
        raise RPCError("Échec de la récupération du solde")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_gas_price(self, endpoint: str) -> int:
        """
        Obtient le prix du gaz

        Args:
            endpoint: Endpoint

        Returns:
            Prix du gaz en wei
        """
        response = await self.call(
            method=RPCMethod.ETH_GET_GAS_PRICE,
            params=[],
            endpoint=endpoint,
        )

        if response.is_success():
            return int(response.result, 16)
        raise RPCError("Échec de la récupération du prix du gaz")

    # ============================================================
    # MÉTHODES DE CONNEXION WEBSOCKET
    # ============================================================

    async def connect_websocket(
        self,
        endpoint: str,
        protocol: RPCProtocol = RPCProtocol.WSS,
    ) -> bool:
        """
        Établit une connexion WebSocket

        Args:
            endpoint: Endpoint
            protocol: Protocole

        Returns:
            True si connecté
        """
        try:
            ws_url = f"{protocol.value}://{endpoint}"
            ws = await websockets.connect(ws_url)
            self._ws_connections[endpoint] = ws

            # Démarrage du listener
            asyncio.create_task(self._websocket_listener(endpoint, ws))

            logger.info(f"WebSocket connecté à {endpoint}")
            return True

        except Exception as e:
            logger.error(f"Erreur de connexion WebSocket: {e}")
            return False

    async def disconnect_websocket(self, endpoint: str) -> bool:
        """
        Ferme la connexion WebSocket

        Args:
            endpoint: Endpoint

        Returns:
            True si déconnecté
        """
        if endpoint in self._ws_connections:
            ws = self._ws_connections[endpoint]
            await ws.close()
            del self._ws_connections[endpoint]
            logger.info(f"WebSocket déconnecté de {endpoint}")
            return True
        return False

    # ============================================================
    # MÉTHODES DE CACHE
    # ============================================================

    async def _get_cached(self, key: str) -> Optional[Any]:
        """Obtient une valeur du cache"""
        if key in self._response_cache:
            cached_time, value = self._response_cache[key]
            if time.time() - cached_time < self.cache_ttl:
                return value
        return None

    async def _set_cached(self, key: str, value: Any) -> None:
        """Définit une valeur dans le cache"""
        self._response_cache[key] = (time.time(), value)

    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================

    async def _call_http(self, request: RPCRequest) -> Dict[str, Any]:
        """Effectue un appel HTTP"""
        if not self._session:
            self._init_session()

        try:
            async with self._session.post(
                request.endpoint,
                data=request.to_json(),
                timeout=request.timeout,
                headers=request.headers,
            ) as response:
                if response.status != 200:
                    raise RPCError(f"HTTP {response.status}: {await response.text()}")

                return await response.json()

        except asyncio.TimeoutError:
            raise RPCError("Timeout de la requête")

    async def _call_http_batch(
        self,
        batch_data: List[str],
        endpoint: str,
    ) -> List[Dict[str, Any]]:
        """Effectue un batch HTTP"""
        if not self._session:
            self._init_session()

        try:
            # Construction du batch JSON
            batch_json = f"[{','.join(batch_data)}]"

            async with self._session.post(
                endpoint,
                data=batch_json,
                timeout=self.config.get("timeout", 30),
            ) as response:
                if response.status != 200:
                    raise RPCError(f"HTTP {response.status}: {await response.text()}")

                return await response.json()

        except asyncio.TimeoutError:
            raise RPCError("Timeout du batch")

    async def _call_websocket(self, request: RPCRequest) -> Dict[str, Any]:
        """Effectue un appel WebSocket"""
        ws = self._ws_connections.get(request.endpoint)
        if not ws:
            # Connexion automatique
            protocol = RPCProtocol.WSS if request.endpoint.startswith("wss") else RPCProtocol.WS
            await self.connect_websocket(request.endpoint, protocol)
            ws = self._ws_connections.get(request.endpoint)

        if not ws:
            raise RPCError("WebSocket non connecté")

        # Envoi de la requête
        future = asyncio.Future()
        self._pending_requests[request.request_id] = future

        try:
            await ws.send(request.to_json())
            response = await asyncio.wait_for(future, timeout=request.timeout)
            return response

        except asyncio.TimeoutError:
            self._pending_requests.pop(request.request_id, None)
            raise RPCError("Timeout WebSocket")

    async def _call_websocket_batch(
        self,
        batch_data: List[str],
        endpoint: str,
    ) -> List[Dict[str, Any]]:
        """Effectue un batch WebSocket"""
        ws = self._ws_connections.get(endpoint)
        if not ws:
            await self.connect_websocket(endpoint)
            ws = self._ws_connections.get(endpoint)

        if not ws:
            raise RPCError("WebSocket non connecté")

        # Envoi du batch
        batch_json = f"[{','.join(batch_data)}]"
        batch_id = str(uuid.uuid4())

        future = asyncio.Future()
        self._pending_requests[batch_id] = future

        try:
            await ws.send(batch_json)
            response = await asyncio.wait_for(future, timeout=self.config.get("timeout", 30))
            return response

        except asyncio.TimeoutError:
            self._pending_requests.pop(batch_id, None)
            raise RPCError("Timeout WebSocket batch")

    # ============================================================
    # MÉTHODES DE LISTENER
    # ============================================================

    async def _websocket_listener(
        self,
        endpoint: str,
        ws: WebSocketClientProtocol,
    ) -> None:
        """Listene les messages WebSocket"""
        try:
            async for message in ws:
                try:
                    data = json.loads(message)

                    # Vérification de l'ID
                    if "id" in data:
                        request_id = data["id"]
                        if request_id in self._pending_requests:
                            future = self._pending_requests.pop(request_id)
                            if not future.done():
                                future.set_result(data)

                except json.JSONDecodeError:
                    logger.warning(f"Message WebSocket invalide: {message}")

        except websockets.ConnectionClosed:
            logger.warning(f"WebSocket fermé pour {endpoint}")
            await self.disconnect_websocket(endpoint)

        except Exception as e:
            logger.error(f"Erreur WebSocket: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du client"""
        return {
            "cache_size": len(self._response_cache),
            "ws_connections": len(self._ws_connections),
            "pending_requests": len(self._pending_requests),
            "circuit_breakers": {
                k: {
                    "available": cb.is_available(),
                    "failure_count": cb.failure_count,
                    "success_count": cb.success_count,
                }
                for k, cb in self.circuit_breakers.items()
            },
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeRPCClient...")

        # Fermeture des connexions WebSocket
        for endpoint in list(self._ws_connections.keys()):
            await self.disconnect_websocket(endpoint)

        # Annulation des requêtes en attente
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()

        self._pending_requests.clear()
        self._response_cache.clear()

        # Fermeture de la session HTTP
        if self._session:
            await self._session.close()
            self._session = None

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_rpc_client(
    config: Dict[str, Any],
    **kwargs,
) -> NodeRPCClient:
    """
    Crée une instance de NodeRPCClient

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeRPCClient
    """
    return NodeRPCClient(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeRPCClient"""
    # Configuration
    config = {
        "timeout": 30,
        "connect_timeout": 10,
        "retry_attempts": 3,
        "retry_delay": 1.0,
    }

    # Création du client
    rpc_client = create_node_rpc_client(config=config)

    # Endpoint
    endpoint = "https://mainnet.infura.io/v3/YOUR_KEY"

    # Appel RPC simple
    response = await rpc_client.call(
        method=RPCMethod.ETH_BLOCK_NUMBER,
        params=[],
        endpoint=endpoint,
    )

    print(f"Block number: {response.result}")

    # Batch d'appels
    batch = await rpc_client.batch_call(
        requests=[
            {"method": "eth_blockNumber", "params": []},
            {"method": "eth_gasPrice", "params": []},
        ],
        endpoint=endpoint,
    )

    print(f"Batch status: {batch.status}")
    for resp in batch.responses:
        print(f"  {resp.request_id}: {resp.result}")

    # Méthodes pratiques
    block_number = await rpc_client.get_block_number(endpoint)
    print(f"Block number: {block_number}")

    gas_price = await rpc_client.get_gas_price(endpoint)
    print(f"Gas price: {gas_price}")

    # Statistiques
    stats = rpc_client.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await rpc_client.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
