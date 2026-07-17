# blockchain/nodes/node_websocket.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node WebSocket - Gestion des WebSockets pour les Nœuds

Ce module implémente un système complet de gestion des WebSockets pour
les nœuds blockchain, supportant les connexions, les souscriptions,
les événements, et la réconnection automatique.

Fonctionnalités principales:
- Connexion WebSocket
- Gestion des souscriptions
- Écoute des événements
- Réconnection automatique
- Gestion des erreurs
- Support multi-protocoles
- Streaming de données
- Heartbeat et ping
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

import websockets
from websockets import WebSocketClientProtocol

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, WebSocketError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, WebSocketError
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

class WebSocketEventType(Enum):
    """Types d'événements WebSocket"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class WebSocketSubscription:
    """Souscription WebSocket"""
    subscription_id: str
    endpoint: str
    channel: str
    params: Dict[str, Any]
    callback: Callable
    created_at: datetime
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "subscription_id": self.subscription_id,
            "endpoint": self.endpoint,
            "channel": self.channel,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "active": self.active,
            "metadata": self.metadata,
        }


@dataclass
class WebSocketConnection:
    """Connexion WebSocket"""
    connection_id: str
    endpoint: str
    ws: Optional[WebSocketClientProtocol] = None
    status: str = "disconnected"
    subscriptions: List[str] = field(default_factory=list)
    connected_at: Optional[datetime] = None
    last_message: Optional[datetime] = None
    reconnect_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "connection_id": self.connection_id,
            "endpoint": self.endpoint,
            "status": self.status,
            "subscriptions": self.subscriptions,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_message": self.last_message.isoformat() if self.last_message else None,
            "reconnect_attempts": self.reconnect_attempts,
            "metadata": self.metadata,
        }


@dataclass
class WebSocketMessage:
    """Message WebSocket"""
    message_id: str
    connection_id: str
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "message_id": self.message_id,
            "connection_id": self.connection_id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class WebSocketStats:
    """Statistiques WebSocket"""
    total_connections: int
    active_connections: int
    total_subscriptions: int
    active_subscriptions: int
    messages_received: int
    messages_sent: int
    reconnections: int
    average_latency: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "total_subscriptions": self.total_subscriptions,
            "active_subscriptions": self.active_subscriptions,
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "reconnections": self.reconnections,
            "average_latency": self.average_latency,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeWebSocketManager:
    """
    Gestionnaire de WebSockets pour les nœuds blockchain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de WebSockets

        Args:
            config: Configuration
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._connections: Dict[str, WebSocketConnection] = {}
        self._subscriptions: Dict[str, WebSocketSubscription] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        self._listener_tasks: Dict[str, asyncio.Task] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Statistiques
        self._stats = WebSocketStats(
            total_connections=0,
            active_connections=0,
            total_subscriptions=0,
            active_subscriptions=0,
            messages_received=0,
            messages_sent=0,
            reconnections=0,
            average_latency=0.0,
        )

        # Alertes
        self._alert_callbacks: List[Callable] = []

        logger.info("NodeWebSocketManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def connect(
        self,
        endpoint: str,
        protocols: Optional[List[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> WebSocketConnection:
        """
        Établit une connexion WebSocket

        Args:
            endpoint: Endpoint WebSocket
            protocols: Protocoles supportés
            extra_headers: Headers supplémentaires

        Returns:
            Connexion WebSocket
        """
        connection_id = f"ws_{uuid.uuid4().hex[:12]}"
        logger.info(f"Connexion WebSocket {connection_id} à {endpoint}")

        try:
            ws = await websockets.connect(
                endpoint,
                subprotocols=protocols,
                extra_headers=extra_headers or {},
                ping_interval=self.config.get("ping_interval", 30),
                ping_timeout=self.config.get("ping_timeout", 10),
            )

            connection = WebSocketConnection(
                connection_id=connection_id,
                endpoint=endpoint,
                ws=ws,
                status="connected",
                connected_at=datetime.now(),
                last_message=datetime.now(),
            )

            self._connections[connection_id] = connection
            self._stats.total_connections += 1
            self._stats.active_connections += 1

            # Démarrage du listener
            task = asyncio.create_task(self._message_listener(connection_id))
            self._listener_tasks[connection_id] = task

            self.metrics.record_increment(
                "websocket_connection",
                1,
                {"endpoint": endpoint[:30], "status": "connected"},
            )

            logger.info(f"WebSocket connecté: {connection_id}")
            return connection

        except Exception as e:
            logger.error(f"Erreur de connexion WebSocket: {e}")

            connection = WebSocketConnection(
                connection_id=connection_id,
                endpoint=endpoint,
                status="failed",
            )
            self._connections[connection_id] = connection

            raise WebSocketError(f"Erreur de connexion WebSocket: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def disconnect(self, connection_id: str) -> bool:
        """
        Ferme une connexion WebSocket

        Args:
            connection_id: ID de la connexion

        Returns:
            True si déconnecté avec succès
        """
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        logger.info(f"Déconnexion WebSocket {connection_id}")

        # Annulation du listener
        if connection_id in self._listener_tasks:
            self._listener_tasks[connection_id].cancel()
            del self._listener_tasks[connection_id]

        # Annulation des tâches de reconnexion
        if connection_id in self._reconnect_tasks:
            self._reconnect_tasks[connection_id].cancel()
            del self._reconnect_tasks[connection_id]

        # Fermeture de la connexion
        if connection.ws:
            await connection.ws.close()

        connection.status = "disconnected"
        self._stats.active_connections = max(0, self._stats.active_connections - 1)

        self.metrics.record_increment(
            "websocket_disconnection",
            1,
            {"endpoint": connection.endpoint[:30]},
        )

        return True

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def subscribe(
        self,
        connection_id: str,
        channel: str,
        callback: Callable,
        params: Optional[Dict[str, Any]] = None,
    ) -> WebSocketSubscription:
        """
        S'abonne à un canal

        Args:
            connection_id: ID de la connexion
            channel: Canal
            callback: Fonction callback
            params: Paramètres de souscription

        Returns:
            Souscription WebSocket
        """
        connection = self._connections.get(connection_id)
        if not connection or connection.status != "connected":
            raise WebSocketError("Connexion WebSocket non active")

        subscription_id = f"sub_{uuid.uuid4().hex[:12]}"

        subscription = WebSocketSubscription(
            subscription_id=subscription_id,
            endpoint=connection.endpoint,
            channel=channel,
            params=params or {},
            callback=callback,
            created_at=datetime.now(),
        )

        # Construction du message de souscription
        sub_message = {
            "jsonrpc": "2.0",
            "method": "eth_subscribe",
            "params": [channel, params or {}],
            "id": subscription_id,
        }

        # Envoi de la souscription
        await self.send_message(connection_id, sub_message)

        self._subscriptions[subscription_id] = subscription
        connection.subscriptions.append(subscription_id)
        self._stats.total_subscriptions += 1
        self._stats.active_subscriptions += 1

        self.metrics.record_increment(
            "websocket_subscription",
                1,
                {"channel": channel},
        )

        logger.info(f"Souscription {subscription_id} au canal {channel}")
        return subscription

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Se désabonne d'un canal

        Args:
            subscription_id: ID de la souscription

        Returns:
            True si désabonné avec succès
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False

        # Construction du message de désabonnement
        unsub_message = {
            "jsonrpc": "2.0",
            "method": "eth_unsubscribe",
            "params": [subscription_id],
            "id": subscription_id,
        }

        # Envoi du désabonnement
        # On cherche la connexion associée
        for connection in self._connections.values():
            if subscription_id in connection.subscriptions:
                await self.send_message(connection.connection_id, unsub_message)
                connection.subscriptions.remove(subscription_id)
                break

        subscription.active = False
        self._stats.active_subscriptions = max(0, self._stats.active_subscriptions - 1)

        self.metrics.record_increment(
            "websocket_unsubscription",
            1,
            {"channel": subscription.channel},
        )

        logger.info(f"Désabonnement {subscription_id}")
        return True

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def send_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> bool:
        """
        Envoie un message WebSocket

        Args:
            connection_id: ID de la connexion
            message: Message à envoyer

        Returns:
            True si envoyé avec succès
        """
        connection = self._connections.get(connection_id)
        if not connection or not connection.ws:
            return False

        try:
            await connection.ws.send(json.dumps(message))
            connection.last_message = datetime.now()
            self._stats.messages_sent += 1

            self.metrics.record_increment(
                "websocket_message_sent",
                1,
                {"endpoint": connection.endpoint[:30]},
            )

            return True

        except Exception as e:
            logger.warning(f"Erreur d'envoi de message: {e}")
            return False

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_connection(self, connection_id: str) -> Optional[WebSocketConnection]:
        """
        Obtient une connexion

        Args:
            connection_id: ID de la connexion

        Returns:
            Connexion ou None
        """
        return self._connections.get(connection_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_subscription(self, subscription_id: str) -> Optional[WebSocketSubscription]:
        """
        Obtient une souscription

        Args:
            subscription_id: ID de la souscription

        Returns:
            Souscription ou None
        """
        return self._subscriptions.get(subscription_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_stats(self) -> WebSocketStats:
        """
        Obtient les statistiques

        Returns:
            Statistiques WebSocket
        """
        return self._stats

    # ============================================================
    # MÉTHODES DE LISTENER
    # ============================================================

    async def _message_listener(self, connection_id: str) -> None:
        """Listene les messages WebSocket"""
        connection = self._connections.get(connection_id)
        if not connection or not connection.ws:
            return

        logger.info(f"Démarrage du listener pour {connection_id}")

        try:
            async for message in connection.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(connection_id, data)
                    connection.last_message = datetime.now()
                    self._stats.messages_received += 1

                except json.JSONDecodeError as e:
                    logger.warning(f"Message JSON invalide: {e}")

                except Exception as e:
                    logger.error(f"Erreur de traitement du message: {e}")

        except websockets.ConnectionClosed:
            logger.warning(f"Connexion WebSocket fermée: {connection_id}")
            await self._handle_disconnection(connection_id)

        except Exception as e:
            logger.error(f"Erreur du listener: {e}")
            await self._handle_disconnection(connection_id)

    async def _handle_message(
        self,
        connection_id: str,
        data: Dict[str, Any],
    ) -> None:
        """Traite un message WebSocket"""
        # Vérification du type de message
        if "method" in data:
            # Notification
            if data.get("method") == "eth_subscription":
                params = data.get("params", {})
                subscription_id = params.get("subscription")

                if subscription_id in self._subscriptions:
                    subscription = self._subscriptions[subscription_id]
                    if subscription.callback:
                        try:
                            if asyncio.iscoroutinefunction(subscription.callback):
                                await subscription.callback(params.get("result"))
                            else:
                                subscription.callback(params.get("result"))
                        except Exception as e:
                            logger.error(f"Erreur de callback: {e}")

        # Métriques
        self.metrics.record_increment(
            "websocket_message_received",
            1,
            {"connection_id": connection_id[:8]},
        )

    async def _handle_disconnection(self, connection_id: str) -> None:
        """Gère une déconnexion"""
        connection = self._connections.get(connection_id)
        if not connection:
            return

        connection.status = "disconnected"
        self._stats.active_connections = max(0, self._stats.active_connections - 1)

        # Tentative de reconnexion
        if self.config.get("auto_reconnect", True):
            reconnect_delay = min(
                self.config.get("reconnect_delay", 5) * (connection.reconnect_attempts + 1),
                self.config.get("max_reconnect_delay", 60),
            )

            logger.info(f"Reconnexion dans {reconnect_delay}s pour {connection_id}")

            # Création d'une tâche de reconnexion
            task = asyncio.create_task(
                self._reconnect_task(connection_id, reconnect_delay)
            )
            self._reconnect_tasks[connection_id] = task

        self.metrics.record_increment(
            "websocket_disconnection",
            1,
            {"connection_id": connection_id[:8]},
        )

    # ============================================================
    # MÉTHODES DE RECONNEXION
    # ============================================================

    async def _reconnect_task(self, connection_id: str, delay: float) -> None:
        """Tâche de reconnexion"""
        await asyncio.sleep(delay)

        connection = self._connections.get(connection_id)
        if not connection or connection.status == "connected":
            return

        try:
            logger.info(f"Tentative de reconnexion {connection_id}")

            connection.reconnect_attempts += 1
            self._stats.reconnections += 1

            # Reconnexion
            ws = await websockets.connect(
                connection.endpoint,
                ping_interval=self.config.get("ping_interval", 30),
                ping_timeout=self.config.get("ping_timeout", 10),
            )

            connection.ws = ws
            connection.status = "connected"
            connection.connected_at = datetime.now()
            self._stats.active_connections += 1

            # Redémarrage du listener
            task = asyncio.create_task(self._message_listener(connection_id))
            self._listener_tasks[connection_id] = task

            # Rétablissement des souscriptions
            for subscription_id in connection.subscriptions:
                subscription = self._subscriptions.get(subscription_id)
                if subscription and subscription.active:
                    sub_message = {
                        "jsonrpc": "2.0",
                        "method": "eth_subscribe",
                        "params": [subscription.channel, subscription.params],
                        "id": subscription_id,
                    }
                    await self.send_message(connection_id, sub_message)

            self.metrics.record_increment(
                "websocket_reconnected",
                1,
                {"connection_id": connection_id[:8]},
            )

            logger.info(f"Reconnexion réussie: {connection_id}")

        except Exception as e:
            logger.warning(f"Échec de reconnexion: {e}")

            # Nouvel essai avec délai plus long
            new_delay = min(delay * 2, self.config.get("max_reconnect_delay", 60))
            asyncio.create_task(self._reconnect_task(connection_id, new_delay))

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "connections": len(self._connections),
            "active_connections": sum(1 for c in self._connections.values() if c.status == "connected"),
            "subscriptions": len(self._subscriptions),
            "active_subscriptions": sum(1 for s in self._subscriptions.values() if s.active),
            "listener_tasks": len(self._listener_tasks),
            "reconnect_tasks": len(self._reconnect_tasks),
            "stats": self._stats.to_dict(),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeWebSocketManager...")

        # Fermeture de toutes les connexions
        for connection_id in list(self._connections.keys()):
            await self.disconnect(connection_id)

        # Attente de la fin des tâches
        if self._listener_tasks:
            await asyncio.gather(*self._listener_tasks.values(), return_exceptions=True)

        if self._reconnect_tasks:
            await asyncio.gather(*self._reconnect_tasks.values(), return_exceptions=True)

        self._connections.clear()
        self._subscriptions.clear()
        self._listener_tasks.clear()
        self._reconnect_tasks.clear()
        self._message_handlers.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_websocket_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeWebSocketManager:
    """
    Crée une instance de NodeWebSocketManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeWebSocketManager
    """
    return NodeWebSocketManager(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeWebSocketManager"""
    # Configuration
    config = {
        "ping_interval": 30,
        "ping_timeout": 10,
        "auto_reconnect": True,
        "reconnect_delay": 5,
        "max_reconnect_delay": 60,
    }

    # Création du gestionnaire
    ws_manager = create_node_websocket_manager(config=config)

    # Connexion
    connection = await ws_manager.connect(
        endpoint="wss://mainnet.infura.io/ws/v3/YOUR_KEY",
    )

    print(f"Connecté: {connection.connection_id}")

    # Souscription aux nouveaux blocs
    async def on_new_block(data):
        print(f"Nouveau bloc: {data}")

    subscription = await ws_manager.subscribe(
        connection_id=connection.connection_id,
        channel="newHeads",
        callback=on_new_block,
    )

    print(f"Souscription: {subscription.subscription_id}")

    # Attendre quelques messages
    await asyncio.sleep(10)

    # Désabonnement
    await ws_manager.unsubscribe(subscription.subscription_id)

    # Statistiques
    stats = await ws_manager.get_stats()
    print(f"Statistiques: {stats.to_dict()}")

    # Déconnexion
    await ws_manager.disconnect(connection.connection_id)

    # Nettoyage
    await ws_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
