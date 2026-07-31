# trading/bots/hedge_bot/hedge_bot_streaming_data.py
# Advanced Real-Time Data Streaming Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Streaming Data Module - Module avancé de streaming de données en temps réel pour le Hedge Bot.
Gère les flux de données en temps réel, les WebSockets, les événements market data,
la latence ultra-basse et le traitement distribué des streams.
"""

import asyncio
import json
import time
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator, AsyncGenerator
)
import uuid
import threading
import concurrent.futures
import asyncio
import websockets
import websockets.client
import websockets.exceptions
import aiohttp
import aiohttp.client_exceptions
from collections import defaultdict, deque
import hashlib
import hmac

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_streaming_data")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager, DataConsistency
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class StreamProvider(Enum):
    """Fournisseurs de streaming."""
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"
    BYBIT = "bybit"
    OKX = "okx"
    ALPACA = "alpaca"
    IBKR = "ibkr"
    OANDA = "oanda"
    CUSTOM = "custom"
    AGGREGATOR = "aggregator"


class StreamType(Enum):
    """Types de streams."""
    MARKET_DATA = "market_data"
    ORDER_BOOK = "order_book"
    TRADES = "trades"
    OHLCV = "ohlcv"
    TICKER = "ticker"
    POSITIONS = "positions"
    ORDERS = "orders"
    BALANCES = "balances"
    SYSTEM = "system"
    DECISIONS = "decisions"
    RISK = "risk"
    PERFORMANCE = "performance"


class StreamStatus(Enum):
    """Statuts des streams."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    AUTHENTICATED = "authenticated"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    STREAMING = "streaming"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"
    PAUSED = "paused"


class StreamPriority(Enum):
    """Priorités des streams."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


# ============== DATA MODELS ==============

@dataclass
class StreamSubscription:
    """Abonnement à un stream."""
    subscription_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str = ""
    symbol: str = ""
    stream_type: StreamType = StreamType.MARKET_DATA
    channels: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    priority: StreamPriority = StreamPriority.MEDIUM
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    callback: Optional[Callable] = None
    batch_size: int = 1
    max_latency_ms: float = 100.0


@dataclass
class StreamMessage:
    """Message de stream."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str = ""
    subscription_id: str = ""
    stream_type: StreamType = StreamType.MARKET_DATA
    symbol: str = ""
    data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0
    latency_ms: float = 0.0
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[str] = None
    compressed: bool = False
    size_bytes: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "stream_id": self.stream_id,
            "subscription_id": self.subscription_id,
            "stream_type": self.stream_type.value,
            "symbol": self.symbol,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "latency_ms": self.latency_ms,
            "source": self.source,
            "metadata": self.metadata,
            "signature": self.signature,
            "compressed": self.compressed,
            "size_bytes": self.size_bytes
        }


@dataclass
class StreamConnection:
    """Connexion de streaming."""
    connection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str = ""
    provider: StreamProvider = StreamProvider.CUSTOM
    endpoint: str = ""
    status: StreamStatus = StreamStatus.DISCONNECTED
    subscriptions: List[str] = field(default_factory=list)
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    last_message: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    disconnected_at: Optional[datetime] = None
    reconnect_attempts: int = 0
    max_reconnect_attempts: int = 10
    ping_interval: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "connection_id": self.connection_id,
            "stream_id": self.stream_id,
            "provider": self.provider.value,
            "endpoint": self.endpoint,
            "status": self.status.value,
            "subscriptions": self.subscriptions,
            "messages_received": self.messages_received,
            "messages_sent": self.messages_sent,
            "errors": self.errors,
            "last_message": self.last_message.isoformat() if self.last_message else None,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "disconnected_at": self.disconnected_at.isoformat() if self.disconnected_at else None,
            "reconnect_attempts": self.reconnect_attempts,
            "max_reconnect_attempts": self.max_reconnect_attempts,
            "ping_interval": self.ping_interval,
            "metadata": self.metadata,
            "tags": self.tags
        }


# ============== INTERFACES ==============

class StreamingEngineInterface(ABC):
    """Interface abstraite pour le moteur de streaming."""
    
    @abstractmethod
    async def connect(self, connection: StreamConnection) -> bool:
        """Connecte un stream."""
        pass
    
    @abstractmethod
    async def subscribe(self, subscription: StreamSubscription) -> bool:
        """Souscrit à un stream."""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Se désabonne d'un stream."""
        pass
    
    @abstractmethod
    async def send_message(self, message: StreamMessage) -> bool:
        """Envoie un message sur un stream."""
        pass


# ============== IMPLÉMENTATION ==============

class StreamingEngine(StreamingEngineInterface):
    """
    Moteur de streaming avancé pour le Hedge Bot.
    Gère les flux de données en temps réel avec latence ultra-basse.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des connexions
        self._connections: Dict[str, StreamConnection] = {}
        self._connections_lock = threading.RLock()
        
        # Gestion des subscriptions
        self._subscriptions: Dict[str, StreamSubscription] = {}
        self._subscriptions_lock = threading.RLock()
        
        # Gestion des messages
        self._messages: deque = deque(maxlen=100000)
        self._messages_lock = threading.RLock()
        
        # WebSocket clients
        self._ws_clients: Dict[str, websockets.client.WebSocketClientProtocol] = {}
        self._ws_lock = threading.RLock()
        
        # Queues de messages
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=100000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "connections": 0,
            "subscriptions": 0,
            "messages_received": 0,
            "messages_sent": 0,
            "errors": 0,
            "reconnections": 0,
            "avg_latency_ms": 0.0,
            "throughput": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Session HTTP (pour les fallbacks REST)
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiters
        self._rate_limiters: Dict[str, asyncio.Semaphore] = {}
        
        logger.info("StreamingEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_connections": 100,
            "max_subscriptions_per_connection": 100,
            "heartbeat_interval": 30,
            "reconnect_delay": 1.0,
            "max_reconnect_attempts": 10,
            "message_timeout": 60,
            "buffer_size": 100000,
            "enable_compression": True,
            "enable_encryption": False,
            "enable_persistent_cache": True,
            "cache_ttl": 3600,
            "latency_threshold_ms": 100,
            "throughput_sample_interval": 10,
            "max_message_size": 1024 * 1024,  # 1 MB
            "default_providers": {
                "binance": {
                    "websocket": "wss://stream.binance.com:9443/ws",
                    "ping_interval": 30
                },
                "coinbase": {
                    "websocket": "wss://ws-feed.pro.coinbase.com",
                    "ping_interval": 30
                },
                "kraken": {
                    "websocket": "wss://ws.kraken.com",
                    "ping_interval": 30
                },
                "bybit": {
                    "websocket": "wss://stream.bybit.com/v5/public/spot",
                    "ping_interval": 30
                }
            },
            "rate_limits": {
                "binance": {"messages_per_second": 100, "connections": 1},
                "coinbase": {"messages_per_second": 50, "connections": 1},
                "kraken": {"messages_per_second": 50, "connections": 1}
            }
        }
    
    async def start(self) -> None:
        """Démarre le moteur de streaming."""
        logger.info("StreamingEngine starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession()
        
        # Initialisation des rate limiters
        for provider, config in self.config.get("rate_limits", {}).items():
            self._rate_limiters[provider] = asyncio.Semaphore(
                config.get("connections", 1)
            )
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._message_processor())
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._reconnection_monitor())
        
        logger.info("StreamingEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de streaming."""
        logger.info("StreamingEngine stopping...")
        self._is_running = False
        
        # Fermeture des connexions WebSocket
        with self._ws_lock:
            for ws in self._ws_clients.values():
                try:
                    await ws.close()
                except:
                    pass
            self._ws_clients.clear()
        
        # Fermeture de la session HTTP
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("StreamingEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def connect(self, connection: StreamConnection) -> bool:
        """Connecte un stream."""
        with self._connections_lock:
            self._connections[connection.connection_id] = connection
            self._stats["connections"] += 1
        
        # Configuration du provider
        provider_config = self.config["default_providers"].get(
            connection.provider.value,
            {"websocket": connection.endpoint}
        )
        
        endpoint = connection.endpoint or provider_config.get("websocket")
        connection.endpoint = endpoint
        connection.ping_interval = provider_config.get("ping_interval", 30)
        
        # Établissement de la connexion
        await self._establish_connection(connection)
        
        logger.info(f"Stream connection established: {connection.connection_id} "
                   f"provider={connection.provider.value}")
        return True
    
    async def subscribe(self, subscription: StreamSubscription) -> bool:
        """Souscrit à un stream."""
        with self._subscriptions_lock:
            self._subscriptions[subscription.subscription_id] = subscription
            self._stats["subscriptions"] += 1
        
        # Trouver la connexion appropriée
        connection = await self._get_connection_for_stream(
            subscription.stream_id
        )
        
        if not connection:
            # Création d'une nouvelle connexion
            connection = await self._create_connection_for_stream(subscription)
            await self.connect(connection)
        
        # Ajout de la subscription
        with self._connections_lock:
            if connection.connection_id in self._connections:
                self._connections[connection.connection_id].subscriptions.append(
                    subscription.subscription_id
                )
        
        # Envoi de la demande de souscription
        await self._send_subscription_request(connection, subscription)
        
        logger.info(f"Subscription created: {subscription.subscription_id} "
                   f"symbol={subscription.symbol} type={subscription.stream_type.value}")
        return True
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Se désabonne d'un stream."""
        with self._subscriptions_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return False
            
            subscription.active = False
        
        # Trouver la connexion associée
        connection = await self._get_connection_for_subscription(subscription_id)
        if connection:
            # Envoi de la demande de désabonnement
            await self._send_unsubscription_request(connection, subscription_id)
            
            # Suppression de la subscription
            with self._connections_lock:
                if connection.connection_id in self._connections:
                    conn = self._connections[connection.connection_id]
                    if subscription_id in conn.subscriptions:
                        conn.subscriptions.remove(subscription_id)
        
        logger.info(f"Subscription removed: {subscription_id}")
        return True
    
    async def send_message(self, message: StreamMessage) -> bool:
        """Envoie un message sur un stream."""
        try:
            # Enrichissement du message
            message.message_id = message.message_id or str(uuid.uuid4())
            message.timestamp = message.timestamp or datetime.now(timezone.utc)
            
            # Compression
            if self.config["enable_compression"]:
                message.compressed = True
                if isinstance(message.data, dict):
                    message.data = zlib.compress(
                        json.dumps(message.data).encode()
                    )
            
            # Mise en queue
            await self._message_queue.put(message)
            
            # Mise à jour des statistiques
            self._stats["messages_sent"] += 1
            
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Send message error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - CONNEXION ==========
    
    async def _establish_connection(self, connection: StreamConnection) -> None:
        """Établit une connexion WebSocket."""
        try:
            connection.status = StreamStatus.CONNECTING
            
            # Rate limiting
            provider = connection.provider.value
            if provider in self._rate_limiters:
                await self._rate_limiters[provider].acquire()
            
            # Connexion WebSocket
            ws = await websockets.connect(
                connection.endpoint,
                ping_interval=connection.ping_interval,
                ping_timeout=10,
                close_timeout=10
            )
            
            with self._ws_lock:
                self._ws_clients[connection.connection_id] = ws
            
            connection.status = StreamStatus.CONNECTED
            connection.connected_at = datetime.now(timezone.utc)
            connection.reconnect_attempts = 0
            
            # Démarrage du récepteur
            asyncio.create_task(self._receive_messages(connection, ws))
            
            logger.info(f"WebSocket connection established: {connection.connection_id}")
            
        except Exception as e:
            connection.status = StreamStatus.ERROR
            connection.errors += 1
            logger.error(f"Connection error: {e}")
            raise
    
    async def _receive_messages(
        self,
        connection: StreamConnection,
        ws: websockets.client.WebSocketClientProtocol
    ) -> None:
        """Reçoit les messages du WebSocket."""
        try:
            async for message in ws:
                # Traitement du message
                await self._process_message(connection, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket connection closed: {connection.connection_id}")
            await self._handle_disconnection(connection)
            
        except Exception as e:
            logger.error(f"Receive error: {connection.connection_id} - {e}")
            await self._handle_disconnection(connection)
    
    async def _process_message(
        self,
        connection: StreamConnection,
        message: Union[str, bytes]
    ) -> None:
        """Traite un message reçu."""
        start_time = time.time()
        
        try:
            # Décodage
            if isinstance(message, bytes):
                # Vérification de la compression
                try:
                    # Essai de décompression
                    decoded = zlib.decompress(message).decode('utf-8')
                except zlib.error:
                    decoded = message.decode('utf-8')
            else:
                decoded = message
            
            # Parsing JSON
            data = json.loads(decoded)
            
            # Création du message
            stream_message = StreamMessage(
                stream_id=connection.stream_id,
                stream_type=StreamType.MARKET_DATA,
                data=data,
                source=connection.provider.value,
                latency_ms=(time.time() - start_time) * 1000,
                size_bytes=len(decoded) if isinstance(decoded, str) else len(message)
            )
            
            # Mise à jour de la connexion
            connection.messages_received += 1
            connection.last_message = stream_message.timestamp
            
            # Mise à jour des statistiques
            self._stats["messages_received"] += 1
            self._stats["avg_latency_ms"] = (
                self._stats["avg_latency_ms"] * 0.9 +
                stream_message.latency_ms * 0.1
            )
            
            # Stockage dans la queue
            with self._messages_lock:
                self._messages.append(stream_message)
            
            # Vérification des subscriptions
            await self._route_message(stream_message)
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _route_message(self, message: StreamMessage) -> None:
        """Route un message vers les subscriptions appropriées."""
        with self._subscriptions_lock:
            for subscription in self._subscriptions.values():
                if not subscription.active:
                    continue
                
                # Vérification du symbole
                if subscription.symbol and message.symbol:
                    if subscription.symbol != message.symbol:
                        continue
                
                # Vérification du type
                if subscription.stream_type != message.stream_type:
                    continue
                
                # Vérification des filtres
                if subscription.filters:
                    match = True
                    for key, value in subscription.filters.items():
                        if isinstance(message.data, dict):
                            if message.data.get(key) != value:
                                match = False
                                break
                    if not match:
                        continue
                
                # Appel du callback
                if subscription.callback:
                    try:
                        if asyncio.iscoroutinefunction(subscription.callback):
                            await subscription.callback(message)
                        else:
                            subscription.callback(message)
                    except Exception as e:
                        logger.error(f"Callback error for {subscription.subscription_id}: {e}")
    
    async def _handle_disconnection(self, connection: StreamConnection) -> None:
        """Gère une déconnexion."""
        connection.status = StreamStatus.DISCONNECTED
        connection.disconnected_at = datetime.now(timezone.utc)
        
        # Nettoyage
        with self._ws_lock:
            if connection.connection_id in self._ws_clients:
                del self._ws_clients[connection.connection_id]
        
        # Tentative de reconnexion
        if connection.reconnect_attempts < connection.max_reconnect_attempts:
            connection.reconnect_attempts += 1
            self._stats["reconnections"] += 1
            
            logger.info(f"Reconnecting {connection.connection_id} "
                       f"attempt {connection.reconnect_attempts}")
            
            # Attente avant reconnexion
            await asyncio.sleep(
                self.config["reconnect_delay"] * connection.reconnect_attempts
            )
            
            try:
                await self._establish_connection(connection)
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
    
    async def _create_connection_for_stream(
        self,
        subscription: StreamSubscription
    ) -> StreamConnection:
        """Crée une connexion pour un stream."""
        provider = self._detect_provider(subscription)
        
        connection = StreamConnection(
            stream_id=subscription.stream_id,
            provider=provider,
            max_reconnect_attempts=self.config["max_reconnect_attempts"]
        )
        
        return connection
    
    async def _get_connection_for_stream(self, stream_id: str) -> Optional[StreamConnection]:
        """Trouve une connexion pour un stream."""
        with self._connections_lock:
            for connection in self._connections.values():
                if connection.stream_id == stream_id:
                    return connection
        return None
    
    async def _get_connection_for_subscription(
        self,
        subscription_id: str
    ) -> Optional[StreamConnection]:
        """Trouve la connexion associée à une subscription."""
        with self._connections_lock:
            for connection in self._connections.values():
                if subscription_id in connection.subscriptions:
                    return connection
        return None
    
    def _detect_provider(self, subscription: StreamSubscription) -> StreamProvider:
        """Détecte le fournisseur à partir du symbole ou de la configuration."""
        # Vérification des tags
        if subscription.tags:
            for tag in subscription.tags:
                try:
                    return StreamProvider(tag)
                except ValueError:
                    pass
        
        # Détection par symbole
        symbol = subscription.symbol.lower()
        if "btc" in symbol or "eth" in symbol or "usdt" in symbol:
            return StreamProvider.BINANCE
        elif "eur" in symbol or "gbp" in symbol:
            return StreamProvider.OANDA
        elif "stock" in subscription.tags or "equity" in subscription.tags:
            return StreamProvider.ALPACA
        
        return StreamProvider.CUSTOM
    
    def _get_provider_endpoint(self, provider: StreamProvider) -> str:
        """Récupère l'endpoint du provider."""
        return self.config["default_providers"].get(
            provider.value, {}
        ).get("websocket", "")
    
    # ========== MÉTHODES PRIVÉES - SUBSCRIPTION ==========
    
    async def _send_subscription_request(
        self,
        connection: StreamConnection,
        subscription: StreamSubscription
    ) -> None:
        """Envoie une demande de souscription."""
        with self._ws_lock:
            ws = self._ws_clients.get(connection.connection_id)
            if not ws:
                return
        
        # Construction de la demande selon le provider
        if connection.provider == StreamProvider.BINANCE:
            payload = {
                "method": "SUBSCRIBE",
                "params": [
                    f"{subscription.symbol.lower()}@trade",
                    f"{subscription.symbol.lower()}@bookTicker"
                ],
                "id": 1
            }
        elif connection.provider == StreamProvider.COINBASE:
            payload = {
                "type": "subscribe",
                "product_ids": [subscription.symbol],
                "channels": ["matches", "level2"]
            }
        elif connection.provider == StreamProvider.KRAKEN:
            payload = {
                "event": "subscribe",
                "subscription": {"name": "ticker"},
                "pair": [subscription.symbol]
            }
        elif connection.provider == StreamProvider.BYBIT:
            payload = {
                "op": "subscribe",
                "args": [f"tickers.{subscription.symbol}"]
            }
        else:
            # Format générique
            payload = {
                "action": "subscribe",
                "symbol": subscription.symbol,
                "type": subscription.stream_type.value,
                "channels": subscription.channels
            }
        
        # Envoi
        await ws.send(json.dumps(payload))
        connection.messages_sent += 1
        
        # Mise à jour du statut
        connection.status = StreamStatus.SUBSCRIBED
        
        logger.debug(f"Subscription request sent: {subscription.subscription_id}")
    
    async def _send_unsubscription_request(
        self,
        connection: StreamConnection,
        subscription_id: str
    ) -> None:
        """Envoie une demande de désabonnement."""
        with self._ws_lock:
            ws = self._ws_clients.get(connection.connection_id)
            if not ws:
                return
        
        with self._subscriptions_lock:
            subscription = self._subscriptions.get(subscription_id)
            if not subscription:
                return
        
        # Construction de la demande selon le provider
        if connection.provider == StreamProvider.BINANCE:
            payload = {
                "method": "UNSUBSCRIBE",
                "params": [
                    f"{subscription.symbol.lower()}@trade"
                ],
                "id": 2
            }
        elif connection.provider == StreamProvider.COINBASE:
            payload = {
                "type": "unsubscribe",
                "product_ids": [subscription.symbol],
                "channels": ["matches"]
            }
        else:
            # Format générique
            payload = {
                "action": "unsubscribe",
                "symbol": subscription.symbol,
                "type": subscription.stream_type.value
            }
        
        # Envoi
        await ws.send(json.dumps(payload))
        connection.messages_sent += 1
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _message_processor(self) -> None:
        """Traite les messages en queue."""
        while self._is_running:
            try:
                message = await self._message_queue.get()
                
                # Traitement du message
                # Dans un système réel, on traiterait le message
                # (stockage, analyse, etc.)
                
                # Vérification de la latence
                if message.latency_ms > self.config["latency_threshold_ms"]:
                    logger.warning(f"High latency: {message.latency_ms:.2f}ms")
                
            except Exception as e:
                logger.error(f"Message processor error: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Boucle de heartbeat."""
        while self._is_running:
            await asyncio.sleep(self.config["heartbeat_interval"])
            
            try:
                # Ping des connexions
                with self._ws_lock:
                    for conn_id, ws in self._ws_clients.items():
                        try:
                            # Ping pour garder la connexion active
                            pong = await ws.ping()
                            await asyncio.wait_for(pong, timeout=5)
                        except Exception as e:
                            logger.warning(f"Heartbeat failed for {conn_id}: {e}")
                
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
    
    async def _reconnection_monitor(self) -> None:
        """Monitor les reconnexions."""
        while self._is_running:
            await asyncio.sleep(30)
            
            try:
                with self._connections_lock:
                    for connection in self._connections.values():
                        if connection.status in [StreamStatus.ERROR, StreamStatus.DISCONNECTED]:
                            if connection.reconnect_attempts < connection.max_reconnect_attempts:
                                logger.info(f"Monitoring triggered reconnection for {connection.connection_id}")
                                await self._establish_connection(connection)
                
            except Exception as e:
                logger.error(f"Reconnection monitor error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        throughput_counter = 0
        last_throughput_time = time.time()
        
        while self._is_running:
            await asyncio.sleep(self.config["throughput_sample_interval"])
            
            try:
                # Calcul du throughput
                current_time = time.time()
                elapsed = current_time - last_throughput_time
                if elapsed > 0:
                    self._stats["throughput"] = throughput_counter / elapsed
                
                throughput_counter = 0
                last_throughput_time = current_time
                
                # Mise à jour des statistiques
                with self._connections_lock:
                    self._stats["active_connections"] = len([
                        c for c in self._connections.values()
                        if c.status == StreamStatus.CONNECTED
                    ])
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "streaming:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
                # Incrément du compteur pour le prochain cycle
                throughput_counter += self._stats["messages_received"]
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_connection(self, connection_id: str) -> Optional[StreamConnection]:
        """Récupère une connexion."""
        with self._connections_lock:
            return self._connections.get(connection_id)
    
    async def get_connections(self, status: Optional[StreamStatus] = None) -> List[StreamConnection]:
        """Récupère les connexions."""
        with self._connections_lock:
            connections = list(self._connections.values())
            if status:
                connections = [c for c in connections if c.status == status]
            return connections
    
    async def get_subscription(self, subscription_id: str) -> Optional[StreamSubscription]:
        """Récupère une subscription."""
        with self._subscriptions_lock:
            return self._subscriptions.get(subscription_id)
    
    async def get_subscriptions(
        self,
        symbol: Optional[str] = None
    ) -> List[StreamSubscription]:
        """Récupère les subscriptions."""
        with self._subscriptions_lock:
            subscriptions = list(self._subscriptions.values())
            if symbol:
                subscriptions = [s for s in subscriptions if s.symbol == symbol]
            return subscriptions
    
    async def get_messages(self, limit: int = 100) -> List[StreamMessage]:
        """Récupère les messages récents."""
        with self._messages_lock:
            return list(self._messages)[-limit:]
    
    async def pause_stream(self, stream_id: str) -> bool:
        """Met en pause un stream."""
        with self._connections_lock:
            for connection in self._connections.values():
                if connection.stream_id == stream_id:
                    connection.status = StreamStatus.PAUSED
                    return True
        return False
    
    async def resume_stream(self, stream_id: str) -> bool:
        """Reprend un stream."""
        with self._connections_lock:
            for connection in self._connections.values():
                if connection.stream_id == stream_id and connection.status == StreamStatus.PAUSED:
                    connection.status = StreamStatus.CONNECTED
                    return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._connections_lock:
            self._stats["total_connections"] = len(self._connections)
        with self._subscriptions_lock:
            self._stats["total_subscriptions"] = len(self._subscriptions)
        with self._messages_lock:
            self._stats["buffered_messages"] = len(self._messages)
        
        return self._stats.copy()


# ============== STREAM AGGREGATOR ==============

class StreamAggregator:
    """
    Agrégateur de streams.
    Combine plusieurs streams en un seul flux agrégé.
    """
    
    def __init__(self, engine: StreamingEngine):
        self.engine = engine
        self._aggregators: Dict[str, Dict[str, Any]] = {}
        self._agg_lock = threading.RLock()
        self._is_running = False
        
        logger.info("StreamAggregator initialized")
    
    async def start(self) -> None:
        """Démarre l'agrégateur."""
        self._is_running = True
        asyncio.create_task(self._aggregation_loop())
        logger.info("StreamAggregator started")
    
    async def stop(self) -> None:
        """Arrête l'agrégateur."""
        self._is_running = False
        logger.info("StreamAggregator stopped")
    
    async def create_aggregator(
        self,
        name: str,
        sources: List[str],
        aggregation_type: str = "merge"
    ) -> str:
        """Crée un agrégateur."""
        aggregator_id = str(uuid.uuid4())
        
        with self._agg_lock:
            self._aggregators[aggregator_id] = {
                "name": name,
                "sources": sources,
                "type": aggregation_type,
                "active": True,
                "messages": deque(maxlen=10000)
            }
        
        logger.info(f"Aggregator created: {name} (id={aggregator_id})")
        return aggregator_id
    
    async def get_aggregated_data(self, aggregator_id: str) -> List[Dict[str, Any]]:
        """Récupère les données agrégées."""
        with self._agg_lock:
            aggregator = self._aggregators.get(aggregator_id)
            if not aggregator:
                return []
            return list(aggregator["messages"])
    
    async def _aggregation_loop(self) -> None:
        """Boucle d'agrégation."""
        while self._is_running:
            await asyncio.sleep(0.1)
            
            try:
                with self._agg_lock:
                    for agg_id, aggregator in self._aggregators.items():
                        if not aggregator["active"]:
                            continue
                        
                        # Récupération des messages des sources
                        for source_id in aggregator["sources"]:
                            subscription = await self.engine.get_subscription(source_id)
                            if subscription:
                                # Dans un système réel, on récupérerait les messages
                                # du stream associé
                                pass
                
            except Exception as e:
                logger.error(f"Aggregation loop error: {e}")


# ============== FACTORY ==============

class StreamingFactory:
    """Factory pour créer des composants de streaming."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> StreamingEngine:
        """Crée un moteur de streaming."""
        engine = StreamingEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    async def create_aggregator(engine: StreamingEngine) -> StreamAggregator:
        """Crée un agrégateur de streams."""
        aggregator = StreamAggregator(engine)
        await aggregator.start()
        return aggregator


# ============== EXPORT ==============

__all__ = [
    "StreamProvider",
    "StreamType",
    "StreamStatus",
    "StreamPriority",
    "StreamSubscription",
    "StreamMessage",
    "StreamConnection",
    "StreamingEngineInterface",
    "StreamingEngine",
    "StreamAggregator",
    "StreamingFactory"
]
