# trading/bots/hedge_bot/hedge_bot_real_time_data.py
# Advanced Real-Time Data Processing & Streaming Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Real-Time Data Module - Module avancé de traitement et streaming de données en temps réel
pour le Hedge Bot. Gère les données en temps réel, les flux de marché, la latence ultra-basse,
le traitement événementiel et la synchronisation des données pour le système de hedging.
"""

import asyncio
import json
import time
import queue
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import numpy as np
import pandas as pd
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_real_time_data")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class RealTimeSource(Enum):
    """Sources de données en temps réel."""
    WEBSOCKET = "websocket"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS_PUBSUB = "redis_pubsub"
    GRPC_STREAM = "grpc_stream"
    HTTP_STREAM = "http_stream"
    SOCKET = "socket"
    CUSTOM = "custom"


class RealTimePriority(Enum):
    """Priorités des données en temps réel."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class RealTimeLatency(Enum):
    """Niveaux de latence."""
    ULTRA_LOW = "ultra_low"           # < 1ms
    VERY_LOW = "very_low"              # < 10ms
    LOW = "low"                       # < 100ms
    MEDIUM = "medium"                 # < 500ms
    HIGH = "high"                     # < 1s


# ============== DATA MODELS ==============

@dataclass
class RealTimeEvent:
    """Événement en temps réel."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: RealTimeSource = RealTimeSource.WEBSOCKET
    priority: RealTimePriority = RealTimePriority.MEDIUM
    data_type: DataType = DataType.MARKET
    symbol: str = ""
    data: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    processed: bool = False


@dataclass
class RealTimeStream:
    """Flux en temps réel."""
    stream_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    source: RealTimeSource = RealTimeSource.WEBSOCKET
    endpoint: str = ""
    symbols: List[str] = field(default_factory=list)
    data_types: List[DataType] = field(default_factory=list)
    priority: RealTimePriority = RealTimePriority.MEDIUM
    latency_target: RealTimeLatency = RealTimeLatency.LOW
    buffer_size: int = 10000
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RealTimeBuffer:
    """Buffer de données en temps réel."""
    buffer_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stream_id: str = ""
    data: deque = field(default_factory=deque)
    max_size: int = 10000
    current_size: int = 0
    total_events: int = 0
    dropped_events: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class RealTimeEngineInterface(ABC):
    """Interface abstraite pour le moteur en temps réel."""
    
    @abstractmethod
    async def create_stream(self, stream: RealTimeStream) -> str:
        """Crée un flux en temps réel."""
        pass
    
    @abstractmethod
    async def publish_event(self, event: RealTimeEvent) -> bool:
        """Publie un événement en temps réel."""
        pass
    
    @abstractmethod
    async def subscribe(self, stream_id: str, callback: Callable) -> bool:
        """S'abonne à un flux en temps réel."""
        pass
    
    @abstractmethod
    async def get_events(self, stream_id: str, limit: int = 100) -> List[RealTimeEvent]:
        """Récupère les événements récents."""
        pass


# ============== IMPLÉMENTATION ==============

class RealTimeEngine(RealTimeEngineInterface):
    """
    Moteur de données en temps réel avancé pour le Hedge Bot.
    Gère le streaming, la latence ultra-basse et le traitement événementiel.
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
        
        # Gestion des flux
        self._streams: Dict[str, RealTimeStream] = {}
        self._streams_lock = threading.RLock()
        
        # Gestion des buffers
        self._buffers: Dict[str, RealTimeBuffer] = {}
        self._buffers_lock = threading.RLock()
        
        # Gestion des abonnements
        self._subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self._sub_lock = threading.RLock()
        
        # Gestion des événements
        self._events: Dict[str, List[RealTimeEvent]] = defaultdict(list)
        self._events_lock = threading.RLock()
        
        # Queue de traitement
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=100000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "streams_created": 0,
            "events_published": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "subscriptions_active": 0,
            "avg_latency_ms": 0.0,
            "throughput": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("RealTimeEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "buffer_size": 10000,
            "max_latency_ms": 100,
            "throughput_window": 60,
            "enable_batching": True,
            "batch_size": 100,
            "flush_interval": 0.1,
            "enable_dedup": True,
            "dedup_window": 5,
            "max_event_size": 1024 * 1024,
            "default_priority": RealTimePriority.MEDIUM,
            "auto_create_buffer": True,
            "enable_statistics": True,
            "metrics_interval": 60
        }
    
    async def start(self) -> None:
        """Démarre le moteur en temps réel."""
        logger.info("RealTimeEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._event_processor())
        asyncio.create_task(self._buffer_manager())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._latency_monitor())
        
        logger.info("RealTimeEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur en temps réel."""
        logger.info("RealTimeEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("RealTimeEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_stream(self, stream: RealTimeStream) -> str:
        """Crée un flux en temps réel."""
        with self._streams_lock:
            self._streams[stream.stream_id] = stream
            self._stats["streams_created"] += 1
        
        # Création du buffer
        if self.config["auto_create_buffer"]:
            buffer = RealTimeBuffer(
                stream_id=stream.stream_id,
                max_size=stream.buffer_size
            )
            with self._buffers_lock:
                self._buffers[stream.stream_id] = buffer
        
        logger.info(f"Real-time stream created: {stream.name} (id={stream.stream_id})")
        return stream.stream_id
    
    async def publish_event(self, event: RealTimeEvent) -> bool:
        """Publie un événement en temps réel."""
        start_time = time.time()
        self._stats["events_published"] += 1
        
        # Vérification de la taille
        event_size = len(str(event.data).encode())
        if event_size > self.config["max_event_size"]:
            logger.warning(f"Event too large: {event_size} bytes")
            return False
        
        # Déduplication
        if self.config["enable_dedup"]:
            if await self._is_duplicate(event):
                self._stats["events_dropped"] += 1
                return False
        
        # Enregistrement de la latence
        event.latency_ms = (time.time() - start_time) * 1000
        
        # Mise en queue
        await self._event_queue.put(event)
        
        # Mise à jour du buffer
        await self._update_buffer(event)
        
        return True
    
    async def subscribe(self, stream_id: str, callback: Callable) -> bool:
        """S'abonne à un flux en temps réel."""
        with self._streams_lock:
            if stream_id not in self._streams:
                return False
        
        with self._sub_lock:
            self._subscriptions[stream_id].append(callback)
            self._stats["subscriptions_active"] = len(self._subscriptions[stream_id])
        
        logger.info(f"Subscription added to stream {stream_id}")
        return True
    
    async def get_events(self, stream_id: str, limit: int = 100) -> List[RealTimeEvent]:
        """Récupère les événements récents."""
        with self._events_lock:
            events = self._events.get(stream_id, [])
            return events[-limit:]
    
    # ========== MÉTHODES PRIVÉES - TRAITEMENT ==========
    
    async def _event_processor(self) -> None:
        """Traite les événements en queue."""
        batch = []
        last_flush = time.time()
        
        while self._is_running:
            try:
                # Collecte des événements
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=self.config["flush_interval"]
                    )
                    batch.append(event)
                except asyncio.TimeoutError:
                    pass
                
                # Flush du batch
                if (len(batch) >= self.config["batch_size"] or
                    (time.time() - last_flush) >= self.config["flush_interval"]):
                    
                    if batch:
                        await self._process_batch(batch)
                        batch = []
                        last_flush = time.time()
                
            except Exception as e:
                logger.error(f"Event processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_batch(self, batch: List[RealTimeEvent]) -> None:
        """Traite un batch d'événements."""
        for event in batch:
            try:
                # Traitement de l'événement
                await self._process_event(event)
                
                # Mise à jour des statistiques
                self._stats["events_processed"] += 1
                self._stats["avg_latency_ms"] = (
                    self._stats["avg_latency_ms"] * 0.9 + event.latency_ms * 0.1
                )
                
                # Notification des abonnés
                await self._notify_subscribers(event)
                
            except Exception as e:
                logger.error(f"Event processing error: {e}")
                self._stats["events_dropped"] += 1
    
    async def _process_event(self, event: RealTimeEvent) -> None:
        """Traite un événement individuel."""
        # Enrichissement de l'événement
        event.processed = True
        
        # Stockage dans l'historique
        with self._events_lock:
            self._events[event.stream_id].append(event)
            
            # Limitation de l'historique
            if len(self._events[event.stream_id]) > 10000:
                self._events[event.stream_id] = self._events[event.stream_id][-10000:]
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"realtime:event:{event.event_id}",
                event.to_dict(),
                DataType.EVENT
            )
    
    async def _notify_subscribers(self, event: RealTimeEvent) -> None:
        """Notifie les abonnés d'un événement."""
        with self._sub_lock:
            callbacks = self._subscriptions.get(event.stream_id, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")
    
    # ========== MÉTHODES PRIVÉES - BUFFER ==========
    
    async def _update_buffer(self, event: RealTimeEvent) -> None:
        """Met à jour le buffer."""
        with self._buffers_lock:
            buffer = self._buffers.get(event.stream_id)
            if not buffer:
                return
            
            buffer.data.append(event)
            buffer.current_size = len(buffer.data)
            buffer.total_events += 1
            
            # Limitation du buffer
            if buffer.current_size > buffer.max_size:
                dropped = buffer.current_size - buffer.max_size
                for _ in range(dropped):
                    buffer.data.popleft()
                buffer.dropped_events += dropped
                self._stats["events_dropped"] += dropped
            
            buffer.updated_at = datetime.now(timezone.utc)
    
    async def _buffer_manager(self) -> None:
        """Gère les buffers périodiquement."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                with self._buffers_lock:
                    for buffer in self._buffers.values():
                        # Vérification des buffers trop grands
                        if buffer.current_size > buffer.max_size * 0.9:
                            logger.warning(f"Buffer {buffer.buffer_id} is near capacity")
                
            except Exception as e:
                logger.error(f"Buffer manager error: {e}")
    
    # ========== MÉTHODES PRIVÉES - DÉDUPLICATION ==========
    
    async def _is_duplicate(self, event: RealTimeEvent) -> bool:
        """Vérifie si un événement est un doublon."""
        # Vérification basée sur le contenu et le timestamp
        with self._events_lock:
            recent = self._events.get(event.stream_id, [])
            if not recent:
                return False
            
            # Comparaison avec les événements récents
            for e in recent[-10:]:  # Vérification des 10 derniers
                if (e.data == event.data and
                    e.symbol == event.symbol and
                    abs((e.timestamp - event.timestamp).total_seconds()) < self.config["dedup_window"]):
                    return True
        
        return False
    
    # ========== MÉTHODES PRIVÉES - LATENCE ==========
    
    async def _latency_monitor(self) -> None:
        """Monitor la latence des événements."""
        while self._is_running:
            await asyncio.sleep(5)
            
            try:
                # Calcul de la latence moyenne
                with self._events_lock:
                    recent = []
                    for events in self._events.values():
                        recent.extend(events[-100:])
                    
                    if recent:
                        avg_latency = sum(e.latency_ms for e in recent) / len(recent)
                        self._stats["avg_latency_ms"] = avg_latency
                        
                        if avg_latency > self.config["max_latency_ms"]:
                            logger.warning(f"High latency detected: {avg_latency:.2f}ms")
                
            except Exception as e:
                logger.error(f"Latency monitor error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'événements."""
        while not self._event_queue.empty():
            try:
                event = await self._event_queue.get()
                event.processed = False
            except Exception:
                break
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        throughput_counter = 0
        last_throughput_time = time.time()
        
        while self._is_running:
            await asyncio.sleep(self.config["metrics_interval"])
            
            try:
                # Calcul du throughput
                current_time = time.time()
                elapsed = current_time - last_throughput_time
                if elapsed > 0:
                    self._stats["throughput"] = throughput_counter / elapsed
                    throughput_counter = 0
                    last_throughput_time = current_time
                
                # Mise à jour des statistiques
                with self._streams_lock:
                    self._stats["total_streams"] = len(self._streams)
                    active_streams = len([s for s in self._streams.values() if s.active])
                    self._stats["active_streams"] = active_streams
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "realtime:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
                # Incrément du compteur
                throughput_counter += self._stats["events_processed"]
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_stream(self, stream_id: str) -> Optional[RealTimeStream]:
        """Récupère un flux."""
        with self._streams_lock:
            return self._streams.get(stream_id)
    
    async def get_streams(self) -> List[RealTimeStream]:
        """Récupère les flux."""
        with self._streams_lock:
            return list(self._streams.values())
    
    async def get_buffer(self, stream_id: str) -> Optional[RealTimeBuffer]:
        """Récupère un buffer."""
        with self._buffers_lock:
            return self._buffers.get(stream_id)
    
    async def get_buffers(self) -> List[RealTimeBuffer]:
        """Récupère les buffers."""
        with self._buffers_lock:
            return list(self._buffers.values())
    
    async def get_latest_event(self, stream_id: str) -> Optional[RealTimeEvent]:
        """Récupère le dernier événement d'un flux."""
        with self._events_lock:
            events = self._events.get(stream_id, [])
            return events[-1] if events else None
    
    async def flush_buffer(self, stream_id: str) -> int:
        """Vide le buffer d'un flux."""
        with self._buffers_lock:
            buffer = self._buffers.get(stream_id)
            if not buffer:
                return 0
            
            flushed = buffer.current_size
            buffer.data.clear()
            buffer.current_size = 0
            return flushed
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._streams_lock:
            self._stats["total_streams"] = len(self._streams)
        with self._buffers_lock:
            self._stats["total_buffers"] = len(self._buffers)
        with self._sub_lock:
            self._stats["total_subscriptions"] = sum(len(cb) for cb in self._subscriptions.values())
        
        return self._stats.copy()


# ============== REAL-TIME EVENT BUILDER ==============

class RealTimeEventBuilder:
    """
    Constructeur d'événements en temps réel.
    Facilite la création d'événements en temps réel.
    """
    
    def __init__(self):
        self._event = RealTimeEvent()
    
    def source(self, source: RealTimeSource) -> 'RealTimeEventBuilder':
        """Définit la source."""
        self._event.source = source
        return self
    
    def priority(self, priority: RealTimePriority) -> 'RealTimeEventBuilder':
        """Définit la priorité."""
        self._event.priority = priority
        return self
    
    def data_type(self, data_type: DataType) -> 'RealTimeEventBuilder':
        """Définit le type de données."""
        self._event.data_type = data_type
        return self
    
    def symbol(self, symbol: str) -> 'RealTimeEventBuilder':
        """Définit le symbole."""
        self._event.symbol = symbol
        return self
    
    def data(self, data: Any) -> 'RealTimeEventBuilder':
        """Définit les données."""
        self._event.data = data
        return self
    
    def timestamp(self, timestamp: datetime) -> 'RealTimeEventBuilder':
        """Définit le timestamp."""
        self._event.timestamp = timestamp
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'RealTimeEventBuilder':
        """Définit les métadonnées."""
        self._event.metadata = metadata
        return self
    
    def tags(self, tags: List[str]) -> 'RealTimeEventBuilder':
        """Définit les tags."""
        self._event.tags = tags
        return self
    
    def build(self) -> RealTimeEvent:
        """Construit l'événement."""
        if not self._event.data:
            raise ValueError("Event data is required")
        return self._event


# ============== FACTORY ==============

class RealTimeFactory:
    """Factory pour créer des composants en temps réel."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> RealTimeEngine:
        """Crée un moteur en temps réel."""
        engine = RealTimeEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_event_builder() -> RealTimeEventBuilder:
        """Crée un constructeur d'événements."""
        return RealTimeEventBuilder()


# ============== EXPORT ==============

__all__ = [
    "RealTimeSource",
    "RealTimePriority",
    "RealTimeLatency",
    "RealTimeEvent",
    "RealTimeStream",
    "RealTimeBuffer",
    "RealTimeEngineInterface",
    "RealTimeEngine",
    "RealTimeEventBuilder",
    "RealTimeFactory"
]
