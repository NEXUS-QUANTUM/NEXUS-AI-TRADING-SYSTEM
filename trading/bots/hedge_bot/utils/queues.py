"""
NEXUS AI TRADING SYSTEM - HEDGE BOT QUEUES MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des files d'attente pour le Hedge Bot.
Support des queues prioritaires, distribuées, persistantes, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import pickle
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union
from uuid import UUID, uuid4

import aiofiles
import aioredis
import redis.asyncio as redis

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class QueueType(Enum):
    """Types de files d'attente."""
    FIFO = "fifo"               # First In First Out
    LIFO = "lifo"               # Last In First Out
    PRIORITY = "priority"       # File prioritaire
    DELAYED = "delayed"         # File différée
    SCHEDULED = "scheduled"     # File planifiée
    CIRCULAR = "circular"       # File circulaire
    DISTRIBUTED = "distributed" # File distribuée
    PERSISTENT = "persistent"   # File persistante


class QueueStatus(Enum):
    """Statuts de file."""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class QueueItem:
    """Élément de file d'attente."""
    item_id: UUID
    data: Any
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    status: str = "pending"  # pending, processing, completed, failed
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "item_id": str(self.item_id),
            "data": self.data,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "status": self.status,
            "metadata": self.metadata,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }


@dataclass
class QueueStats:
    """Statistiques de file."""
    queue_id: UUID
    name: str
    queue_type: QueueType
    total_enqueued: int
    total_dequeued: int
    total_completed: int
    total_failed: int
    current_size: int
    max_size: int
    average_wait_time: float
    maximum_wait_time: float
    average_processing_time: float
    maximum_processing_time: float
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "queue_id": str(self.queue_id),
            "name": self.name,
            "queue_type": self.queue_type.value,
            "total_enqueued": self.total_enqueued,
            "total_dequeued": self.total_dequeued,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "average_wait_time": self.average_wait_time,
            "maximum_wait_time": self.maximum_wait_time,
            "average_processing_time": self.average_processing_time,
            "maximum_processing_time": self.maximum_processing_time,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE DE BASE DES FILES
# ============================================================================

class BaseQueue:
    """
    Classe de base pour toutes les files d'attente.
    """

    def __init__(
        self,
        name: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ):
        """
        Initialise la file d'attente.

        Args:
            name: Nom de la file
            queue_type: Type de file
            max_size: Taille maximale (0 = illimitée)
            ttl: Durée de vie des éléments
            processor: Fonction de traitement
        """
        self.queue_id = uuid4()
        self.name = name
        self.queue_type = queue_type
        self.max_size = max_size
        self.ttl = ttl
        self.processor = processor
        
        self._queue: deque = deque()
        self._items: Dict[UUID, QueueItem] = {}
        self._lock = asyncio.Lock()
        self._status = QueueStatus.ACTIVE
        self._stats = QueueStats(
            queue_id=self.queue_id,
            name=name,
            queue_type=queue_type,
            total_enqueued=0,
            total_dequeued=0,
            total_completed=0,
            total_failed=0,
            current_size=0,
            max_size=0,
            average_wait_time=0.0,
            maximum_wait_time=0.0,
            average_processing_time=0.0,
            maximum_processing_time=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self._processing_tasks: Set[asyncio.Task] = set()
        self._workers: List[asyncio.Task] = []
        self._running = True

        logger.info(f"Queue {name} initialisée (ID: {self.queue_id})")

    # ========================================================================
    # OPÉRATIONS DE BASE
    # ========================================================================

    async def enqueue(
        self,
        data: Any,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        max_attempts: int = 3,
        metadata: Optional[Dict] = None
    ) -> UUID:
        """
        Ajoute un élément à la file.

        Args:
            data: Données
            priority: Priorité
            scheduled_at: Date de planification
            expires_at: Date d'expiration
            max_attempts: Nombre maximum de tentatives
            metadata: Métadonnées

        Returns:
            ID de l'élément
        """
        if self.max_size > 0 and len(self._queue) >= self.max_size:
            raise QueueFullError(f"File {self.name} pleine")

        if self._status not in [QueueStatus.ACTIVE, QueueStatus.PAUSED]:
            raise QueueClosedError(f"File {self.name} fermée")

        item = QueueItem(
            item_id=uuid4(),
            data=data,
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            max_attempts=max_attempts,
            metadata=metadata or {}
        )

        async with self._lock:
            self._items[item.item_id] = item
            self._queue.append(item.item_id)
            self._stats.total_enqueued += 1
            self._stats.current_size += 1
            if self._stats.current_size > self._stats.max_size:
                self._stats.max_size = self._stats.current_size
            self._stats.updated_at = datetime.now()

        # Notification de nouvel élément
        self._on_enqueue(item)

        logger.debug(f"Élément {item.item_id} ajouté à {self.name}")
        return item.item_id

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[QueueItem]:
        """
        Récupère un élément de la file.

        Args:
            timeout: Timeout

        Returns:
            Élément ou None
        """
        if self._status == QueueStatus.STOPPED:
            raise QueueClosedError(f"File {self.name} fermée")

        start_time = time.time()

        while True:
            async with self._lock:
                if self._queue:
                    item_id = self._get_next_item()
                    if item_id:
                        item = self._items.get(item_id)
                        if item:
                            # Vérification de l'expiration
                            if item.expires_at and datetime.now() > item.expires_at:
                                self._remove_item(item_id)
                                self._stats.total_failed += 1
                                continue

                            # Vérification de la planification
                            if item.scheduled_at and datetime.now() < item.scheduled_at:
                                continue

                            item.status = "processing"
                            item.attempts += 1
                            self._stats.total_dequeued += 1
                            self._stats.current_size -= 1
                            self._stats.updated_at = datetime.now()
                            
                            # Calcul du temps d'attente
                            wait_time = time.time() - start_time
                            self._update_wait_stats(wait_time)

                            return item

            if timeout is not None:
                if time.time() - start_time > timeout:
                    return None

            await asyncio.sleep(0.01)

    def _get_next_item(self) -> Optional[UUID]:
        """
        Récupère le prochain élément selon le type de file.

        Returns:
            ID de l'élément ou None
        """
        if not self._queue:
            return None

        if self.queue_type == QueueType.LIFO:
            return self._queue.pop()
        elif self.queue_type == QueueType.PRIORITY:
            # Trouver l'élément avec la plus haute priorité
            max_priority = -1
            max_item_id = None
            for item_id in self._queue:
                item = self._items.get(item_id)
                if item and item.priority > max_priority:
                    max_priority = item.priority
                    max_item_id = item_id
            if max_item_id:
                self._queue.remove(max_item_id)
                return max_item_id
            return self._queue.popleft()
        else:  # FIFO par défaut
            return self._queue.popleft()

    async def complete(self, item_id: UUID, result: Any = None) -> None:
        """
        Marque un élément comme terminé.

        Args:
            item_id: ID de l'élément
            result: Résultat du traitement
        """
        async with self._lock:
            if item_id not in self._items:
                return

            item = self._items[item_id]
            item.status = "completed"
            item.completed_at = datetime.now()
            item.metadata["result"] = result

            self._stats.total_completed += 1
            self._stats.updated_at = datetime.now()

            # Calcul du temps de traitement
            if "processing_start" in item.metadata:
                process_time = (datetime.now() - item.metadata["processing_start"]).total_seconds()
                self._update_process_stats(process_time)

            self._on_complete(item)
            self._remove_item(item_id)

    async def fail(self, item_id: UUID, error: Exception) -> None:
        """
        Marque un élément comme échoué.

        Args:
            item_id: ID de l'élément
            error: Erreur
        """
        async with self._lock:
            if item_id not in self._items:
                return

            item = self._items[item_id]
            item.attempts += 1
            item.error_message = str(error)

            if item.attempts >= item.max_attempts:
                item.status = "failed"
                self._stats.total_failed += 1
                self._on_fail(item)
                self._remove_item(item_id)
            else:
                # Réessayer plus tard
                item.status = "pending"
                self._queue.append(item_id)
                self._stats.current_size += 1
                self._stats.updated_at = datetime.now()

    async def ack(self, item_id: UUID) -> None:
        """
        Acquitte un élément (supprime de la file).

        Args:
            item_id: ID de l'élément
        """
        async with self._lock:
            if item_id in self._items:
                self._remove_item(item_id)

    def _remove_item(self, item_id: UUID) -> None:
        """
        Supprime un élément de la file.

        Args:
            item_id: ID de l'élément
        """
        if item_id in self._items:
            del self._items[item_id]

    # ========================================================================
    # TRAITEMENT
    # ========================================================================

    async def process(self, worker_count: int = 1) -> None:
        """
        Lance le traitement des éléments.

        Args:
            worker_count: Nombre de workers
        """
        if not self.processor:
            raise ValueError(f"Aucun processeur défini pour la file {self.name}")

        self._workers = []
        for i in range(worker_count):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)

        await asyncio.gather(*self._workers)

    async def _worker_loop(self, worker_id: int) -> None:
        """
        Boucle d'un worker.

        Args:
            worker_id: ID du worker
        """
        logger.info(f"Worker {worker_id} démarré pour {self.name}")

        while self._running and self._status != QueueStatus.STOPPED:
            try:
                if self._status == QueueStatus.PAUSED:
                    await asyncio.sleep(1)
                    continue

                item = await self.dequeue(timeout=1)
                if not item:
                    continue

                try:
                    item.metadata["processing_start"] = datetime.now()
                    
                    if asyncio.iscoroutinefunction(self.processor):
                        result = await self.processor(item.data)
                    else:
                        result = self.processor(item.data)

                    await self.complete(item.item_id, result)

                except Exception as e:
                    logger.error(f"Erreur de traitement pour {item.item_id}: {e}")
                    await self.fail(item.item_id, e)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker {worker_id}: {e}")
                await asyncio.sleep(1)

        logger.info(f"Worker {worker_id} arrêté pour {self.name}")

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    def _on_enqueue(self, item: QueueItem) -> None:
        """Callback lors de l'ajout d'un élément."""
        pass

    def _on_complete(self, item: QueueItem) -> None:
        """Callback lors de la complétion d'un élément."""
        pass

    def _on_fail(self, item: QueueItem) -> None:
        """Callback lors de l'échec d'un élément."""
        pass

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def _update_wait_stats(self, wait_time: float) -> None:
        """Met à jour les statistiques d'attente."""
        self._stats.average_wait_time = (
            (self._stats.average_wait_time * (self._stats.total_dequeued - 1) + wait_time)
            / self._stats.total_dequeued
        )
        if wait_time > self._stats.maximum_wait_time:
            self._stats.maximum_wait_time = wait_time

    def _update_process_stats(self, process_time: float) -> None:
        """Met à jour les statistiques de traitement."""
        total = self._stats.total_completed
        self._stats.average_processing_time = (
            (self._stats.average_processing_time * (total - 1) + process_time)
            / total
        )
        if process_time > self._stats.maximum_processing_time:
            self._stats.maximum_processing_time = process_time

    def get_stats(self) -> QueueStats:
        """
        Récupère les statistiques de la file.

        Returns:
            Statistiques de la file
        """
        return self._stats

    # ========================================================================
    # GESTION
    # ========================================================================

    async def pause(self) -> None:
        """Met la file en pause."""
        self._status = QueueStatus.PAUSED
        logger.info(f"File {self.name} mise en pause")

    async def resume(self) -> None:
        """Reprend la file."""
        self._status = QueueStatus.ACTIVE
        logger.info(f"File {self.name} reprise")

    async def drain(self) -> None:
        """Vide la file."""
        self._status = QueueStatus.DRAINING
        while self._queue:
            item_id = self._queue.popleft()
            if item_id in self._items:
                del self._items[item_id]
                self._stats.current_size -= 1
        logger.info(f"File {self.name} vidée")

    async def close(self) -> None:
        """Ferme la file."""
        self._running = False
        self._status = QueueStatus.STOPPED
        
        # Annulation des workers
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        
        self._queue.clear()
        self._items.clear()
        logger.info(f"File {self.name} fermée")

    def size(self) -> int:
        """
        Récupère la taille de la file.

        Returns:
            Taille de la file
        """
        return len(self._queue)

    def is_empty(self) -> bool:
        """
        Vérifie si la file est vide.

        Returns:
            True si vide
        """
        return len(self._queue) == 0

    def is_full(self) -> bool:
        """
        Vérifie si la file est pleine.

        Returns:
            True si pleine
        """
        return self.max_size > 0 and len(self._queue) >= self.max_size


# ============================================================================
# FILE DISTRIBUÉE AVEC REDIS
# ============================================================================

class DistributedQueue(BaseQueue):
    """
    File d'attente distribuée avec Redis.
    """

    def __init__(
        self,
        name: str,
        redis_client: redis.Redis,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ):
        """
        Initialise la file distribuée.

        Args:
            name: Nom de la file
            redis_client: Client Redis
            queue_type: Type de file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement
        """
        super().__init__(name, queue_type, max_size, ttl, processor)
        self.redis = redis_client
        self._key = f"queue:{name}:items"
        self._metadata_key = f"queue:{name}:metadata"
        self._processing_key = f"queue:{name}:processing"

    async def enqueue(
        self,
        data: Any,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        max_attempts: int = 3,
        metadata: Optional[Dict] = None
    ) -> UUID:
        """
        Ajoute un élément à la file distribuée.

        Args:
            data: Données
            priority: Priorité
            scheduled_at: Date de planification
            expires_at: Date d'expiration
            max_attempts: Nombre maximum de tentatives
            metadata: Métadonnées

        Returns:
            ID de l'élément
        """
        item = QueueItem(
            item_id=uuid4(),
            data=data,
            priority=priority,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            max_attempts=max_attempts,
            metadata=metadata or {}
        )

        item_data = pickle.dumps(item.to_dict())
        
        if self.queue_type == QueueType.PRIORITY:
            await self.redis.zadd(self._key, {item_data: -priority})
        else:
            await self.redis.rpush(self._key, item_data)

        if self.ttl:
            await self.redis.expire(self._key, self.ttl)

        self._stats.total_enqueued += 1
        self._stats.current_size += 1
        self._stats.updated_at = datetime.now()

        return item.item_id

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[QueueItem]:
        """
        Récupère un élément de la file distribuée.

        Args:
            timeout: Timeout

        Returns:
            Élément ou None
        """
        start_time = time.time()

        while True:
            if self.queue_type == QueueType.PRIORITY:
                result = await self.redis.zpopmin(self._key)
                if result:
                    item_data = result[0][0]
                else:
                    item_data = None
            else:
                item_data = await self.redis.lpop(self._key)

            if item_data:
                try:
                    item_dict = pickle.loads(item_data)
                    item = QueueItem(**item_dict)
                    
                    # Vérification de l'expiration
                    if item.expires_at and datetime.now() > item.expires_at:
                        self._stats.total_failed += 1
                        continue

                    # Vérification de la planification
                    if item.scheduled_at and datetime.now() < item.scheduled_at:
                        # Remettre dans la file
                        await self.enqueue(
                            item.data,
                            item.priority,
                            item.scheduled_at,
                            item.expires_at,
                            item.max_attempts,
                            item.metadata
                        )
                        continue

                    item.status = "processing"
                    item.attempts += 1
                    self._stats.total_dequeued += 1
                    self._stats.current_size -= 1
                    self._stats.updated_at = datetime.now()

                    # Ajout à la liste de traitement
                    await self.redis.sadd(self._processing_key, str(item.item_id))

                    # Calcul du temps d'attente
                    wait_time = time.time() - start_time
                    self._update_wait_stats(wait_time)

                    return item

                except Exception as e:
                    logger.error(f"Erreur de désérialisation: {e}")
                    continue

            if timeout is not None and time.time() - start_time > timeout:
                return None

            await asyncio.sleep(0.1)

    async def complete(self, item_id: UUID, result: Any = None) -> None:
        """
        Marque un élément comme terminé.

        Args:
            item_id: ID de l'élément
            result: Résultat
        """
        await self.redis.srem(self._processing_key, str(item_id))
        await super().complete(item_id, result)

    async def fail(self, item_id: UUID, error: Exception) -> None:
        """
        Marque un élément comme échoué.

        Args:
            item_id: ID de l'élément
            error: Erreur
        """
        await self.redis.srem(self._processing_key, str(item_id))
        await super().fail(item_id, error)

    async def get_processing_items(self) -> List[UUID]:
        """
        Récupère les éléments en cours de traitement.

        Returns:
            Liste des IDs
        """
        items = await self.redis.smembers(self._processing_key)
        return [UUID(item.decode()) for item in items]


# ========================================================================
# FILE PERSISTANTE
# ========================================================================

class PersistentQueue(BaseQueue):
    """
    File d'attente persistante sur disque.
    """

    def __init__(
        self,
        name: str,
        file_path: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None,
        flush_interval: int = 60
    ):
        """
        Initialise la file persistante.

        Args:
            name: Nom de la file
            file_path: Chemin du fichier
            queue_type: Type de file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement
            flush_interval: Intervalle de sauvegarde
        """
        super().__init__(name, queue_type, max_size, ttl, processor)
        self.file_path = file_path
        self.flush_interval = flush_interval
        self._dirty = False
        self._flush_task: Optional[asyncio.Task] = None

        # Chargement des données
        self._load()

        # Démarrage du flush périodique
        self._start_flush_task()

    def _load(self) -> None:
        """Charge les données depuis le fichier."""
        try:
            with open(self.file_path, 'rb') as f:
                data = pickle.load(f)
                self._queue = deque(data.get("queue", []))
                self._items = data.get("items", {})
                self._stats = QueueStats(**data.get("stats", {}))
                logger.info(f"File {self.name} chargée: {len(self._queue)} éléments")
        except FileNotFoundError:
            logger.info(f"Fichier {self.file_path} non trouvé, création d'une nouvelle file")
        except Exception as e:
            logger.error(f"Erreur de chargement de la file: {e}")

    async def _save(self) -> None:
        """Sauvegarde les données sur le disque."""
        try:
            data = {
                "queue": list(self._queue),
                "items": self._items,
                "stats": self._stats.__dict__
            }
            async with aiofiles.open(self.file_path, 'wb') as f:
                await f.write(pickle.dumps(data))
            self._dirty = False
        except Exception as e:
            logger.error(f"Erreur de sauvegarde de la file: {e}")

    def _start_flush_task(self) -> None:
        """Démarre la tâche de sauvegarde périodique."""
        if self.flush_interval > 0:
            self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        """Boucle de sauvegarde périodique."""
        try:
            while self._running:
                await asyncio.sleep(self.flush_interval)
                if self._dirty:
                    await self._save()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erreur dans la boucle de sauvegarde: {e}")

    async def enqueue(
        self,
        data: Any,
        priority: int = 0,
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        max_attempts: int = 3,
        metadata: Optional[Dict] = None
    ) -> UUID:
        """
        Ajoute un élément à la file persistante.

        Args:
            data: Données
            priority: Priorité
            scheduled_at: Date de planification
            expires_at: Date d'expiration
            max_attempts: Nombre maximum de tentatives
            metadata: Métadonnées

        Returns:
            ID de l'élément
        """
        item_id = await super().enqueue(
            data, priority, scheduled_at, expires_at, max_attempts, metadata
        )
        self._dirty = True
        return item_id

    async def dequeue(self, timeout: Optional[float] = None) -> Optional[QueueItem]:
        """
        Récupère un élément de la file persistante.

        Args:
            timeout: Timeout

        Returns:
            Élément ou None
        """
        item = await super().dequeue(timeout)
        if item:
            self._dirty = True
        return item

    async def close(self) -> None:
        """Ferme la file et sauvegarde."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        await self._save()
        await super().close()


# ========================================================================
# FILE PRIORITAIRE
# ========================================================================

class PriorityQueue(BaseQueue):
    """
    File d'attente prioritaire.
    """

    def __init__(
        self,
        name: str,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ):
        """
        Initialise la file prioritaire.

        Args:
            name: Nom de la file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement
        """
        super().__init__(name, QueueType.PRIORITY, max_size, ttl, processor)
        self._priority_levels = {}


# ========================================================================
# EXCEPTIONS
# ========================================================================

class QueueError(Exception):
    """Exception de base pour les files."""
    pass


class QueueFullError(QueueError):
    """Exception lorsque la file est pleine."""
    pass


class QueueEmptyError(QueueError):
    """Exception lorsque la file est vide."""
    pass


class QueueClosedError(QueueError):
    """Exception lorsque la file est fermée."""
    pass


# ========================================================================
# FACTORY DES FILES
# ========================================================================

class QueueFactory:
    """
    Factory pour créer des files d'attente.
    """

    @staticmethod
    def create_queue(
        name: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ) -> BaseQueue:
        """
        Crée une file d'attente.

        Args:
            name: Nom de la file
            queue_type: Type de file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement

        Returns:
            File d'attente
        """
        return BaseQueue(name, queue_type, max_size, ttl, processor)

    @staticmethod
    def create_distributed_queue(
        name: str,
        redis_client: redis.Redis,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ) -> DistributedQueue:
        """
        Crée une file distribuée.

        Args:
            name: Nom de la file
            redis_client: Client Redis
            queue_type: Type de file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement

        Returns:
            File distribuée
        """
        return DistributedQueue(name, redis_client, queue_type, max_size, ttl, processor)

    @staticmethod
    def create_persistent_queue(
        name: str,
        file_path: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None,
        flush_interval: int = 60
    ) -> PersistentQueue:
        """
        Crée une file persistante.

        Args:
            name: Nom de la file
            file_path: Chemin du fichier
            queue_type: Type de file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement
            flush_interval: Intervalle de sauvegarde

        Returns:
            File persistante
        """
        return PersistentQueue(name, file_path, queue_type, max_size, ttl, processor, flush_interval)

    @staticmethod
    def create_priority_queue(
        name: str,
        max_size: int = 0,
        ttl: Optional[int] = None,
        processor: Optional[Callable] = None
    ) -> PriorityQueue:
        """
        Crée une file prioritaire.

        Args:
            name: Nom de la file
            max_size: Taille maximale
            ttl: Durée de vie
            processor: Fonction de traitement

        Returns:
            File prioritaire
        """
        return PriorityQueue(name, max_size, ttl, processor)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_queue(
    name: str,
    queue_type: QueueType = QueueType.FIFO,
    max_size: int = 0,
    ttl: Optional[int] = None,
    processor: Optional[Callable] = None
) -> BaseQueue:
    """
    Crée une file d'attente.

    Args:
        name: Nom de la file
        queue_type: Type de file
        max_size: Taille maximale
        ttl: Durée de vie
        processor: Fonction de traitement

    Returns:
        File d'attente
    """
    return QueueFactory.create_queue(name, queue_type, max_size, ttl, processor)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "QueueType",
    "QueueStatus",
    "QueueItem",
    "QueueStats",
    "BaseQueue",
    "DistributedQueue",
    "PersistentQueue",
    "PriorityQueue",
    "QueueFactory",
    "QueueError",
    "QueueFullError",
    "QueueEmptyError",
    "QueueClosedError",
    "create_queue"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des files d'attente."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT QUEUES")
    print("=" * 60)

    # File simple
    print(f"\n📦 Création d'une file simple...")
    queue = create_queue(
        name="Test Queue",
        queue_type=QueueType.FIFO,
        processor=lambda x: x * 2
    )

    print(f"   Queue créée: {queue.name} (ID: {queue.queue_id})")

    # Ajout d'éléments
    print(f"\n📥 Ajout d'éléments...")
    for i in range(5):
        item_id = await queue.enqueue(i, priority=5 - i)
        print(f"   Ajouté: {i} (ID: {str(item_id)[:8]})")

    print(f"   Taille: {queue.size()}")

    # Récupération d'éléments
    print(f"\n📤 Récupération d'éléments...")
    while not queue.is_empty():
        item = await queue.dequeue()
        if item:
            print(f"   Récupéré: {item.data} (priorité: {item.priority})")
            await queue.complete(item.item_id, item.data * 2)

    # Statistiques
    stats = queue.get_stats()
    print(f"\n📊 Statistiques:")
    print(f"   Total enqueued: {stats.total_enqueued}")
    print(f"   Total dequeued: {stats.total_dequeued}")
    print(f"   Total completed: {stats.total_completed}")
    print(f"   Average wait time: {stats.average_wait_time:.3f}s")

    # File avec processeur
    print(f"\n⚡ File avec processeur...")
    
    async def processor(data):
        await asyncio.sleep(0.5)
        return data ** 2

    queue_with_processor = create_queue(
        name="Processor Queue",
        processor=processor
    )

    for i in range(3):
        await queue_with_processor.enqueue(i)

    # Lancement du traitement (dans une tâche séparée)
    async def run_processor():
        try:
            await queue_with_processor.process(worker_count=2)
        except asyncio.CancelledError:
            pass

    processor_task = asyncio.create_task(run_processor())
    await asyncio.sleep(2)
    processor_task.cancel()

    # Santé de la file
    print(f"\n❤️ Santé de la file:")
    print(f"   Statut: {queue._status.value}")
    print(f"   Taille: {queue.size()}")
    print(f"   Pleine: {queue.is_full()}")

    # Fermeture
    await queue.close()

    print("\n" + "=" * 60)
    print("Queues NEXUS opérationnelles ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
