"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Queues Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de files d'attente pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import threading
import queue
import time
import uuid
import heapq
import logging
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic,
    Iterator,
    AsyncIterator,
    ContextManager,
    AsyncContextManager,
    Coroutine,
    Awaitable
)
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import weakref
import random

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')
K = TypeVar('K')
V = TypeVar('V')

# ============================================================
# ENUMS
# ============================================================

class QueueType(Enum):
    """Types de files d'attente"""
    FIFO = "fifo"
    LIFO = "lifo"
    PRIORITY = "priority"
    DELAYED = "delayed"
    SCHEDULED = "scheduled"
    CIRCULAR = "circular"
    BATCH = "batch"

class QueueStatus(Enum):
    """Statuts de file d'attente"""
    ACTIVE = "active"
    PAUSED = "paused"
    DRAINING = "draining"
    CLOSED = "closed"

# ============================================================
# BASE QUEUE
# ============================================================

class BaseQueue(Generic[T]):
    """
    File d'attente de base avec fonctionnalités avancées
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        max_size: int = 0,
        queue_type: QueueType = QueueType.FIFO,
        timeout: Optional[float] = None,
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        batch_size: int = 10,
        batch_timeout: float = 5.0
    ):
        """
        Initialise la file d'attente
        
        Args:
            name: Nom de la file
            max_size: Taille maximale (0 = illimitée)
            queue_type: Type de file
            timeout: Timeout par défaut
            retry_attempts: Nombre de tentatives
            retry_delay: Délai entre les tentatives
            batch_size: Taille des lots
            batch_timeout: Timeout des lots
        """
        self.name = name or str(uuid.uuid4())[:8]
        self.max_size = max_size
        self.queue_type = queue_type
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        self._queue = self._create_queue()
        self._status = QueueStatus.ACTIVE
        self._lock = threading.RLock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._stats = {
            'enqueued': 0,
            'dequeued': 0,
            'failed': 0,
            'retried': 0,
            'size': 0,
            'max_size': max_size,
        }
        
        logger.info(f"Queue '{self.name}' initialized (type={queue_type.value}, max_size={max_size})")
    
    def _create_queue(self):
        """Crée la structure de file d'attente appropriée"""
        if self.queue_type == QueueType.FIFO:
            return deque()
        elif self.queue_type == QueueType.LIFO:
            return deque()
        elif self.queue_type == QueueType.PRIORITY:
            return []
        elif self.queue_type == QueueType.CIRCULAR:
            return deque(maxlen=self.max_size if self.max_size > 0 else None)
        else:
            return deque()
    
    def _push(self, item: T, priority: Optional[int] = None):
        """Ajoute un élément à la file"""
        if self.queue_type == QueueType.PRIORITY:
            if priority is None:
                priority = 0
            heapq.heappush(self._queue, (priority, item))
        elif self.queue_type == QueueType.LIFO:
            self._queue.append(item)
        else:  # FIFO
            self._queue.append(item)
    
    def _pop(self) -> T:
        """Retire un élément de la file"""
        if self.queue_type == QueueType.PRIORITY:
            return heapq.heappop(self._queue)[1]
        elif self.queue_type == QueueType.LIFO:
            return self._queue.pop()
        else:  # FIFO
            return self._queue.popleft()
    
    def _peek(self) -> Optional[T]:
        """Regarde le prochain élément sans le retirer"""
        if not self._queue:
            return None
        
        if self.queue_type == QueueType.PRIORITY:
            return self._queue[0][1]
        elif self.queue_type == QueueType.LIFO:
            return self._queue[-1]
        else:  # FIFO
            return self._queue[0]
    
    def _is_empty(self) -> bool:
        """Vérifie si la file est vide"""
        return len(self._queue) == 0
    
    def _size(self) -> int:
        """Taille de la file"""
        return len(self._queue)
    
    def put(self, item: T, priority: Optional[int] = None, timeout: Optional[float] = None) -> bool:
        """
        Ajoute un élément à la file
        
        Args:
            item: Élément à ajouter
            priority: Priorité (pour priority queue)
            timeout: Timeout en secondes
            
        Returns:
            bool: True si ajouté
            
        Raises:
            QueueFull: Si la file est pleine
            TimeoutError: Si le timeout est dépassé
        """
        if self._status in [QueueStatus.DRAINING, QueueStatus.CLOSED]:
            raise RuntimeError(f"Queue '{self.name}' is {self._status.value}")
        
        start_time = time.time()
        
        with self._not_full:
            while self.max_size > 0 and self._size() >= self.max_size:
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise TimeoutError(f"Queue '{self.name}' full, timeout after {timeout}s")
                    self._not_full.wait(timeout - elapsed)
                else:
                    self._not_full.wait()
            
            self._push(item, priority)
            self._stats['enqueued'] += 1
            self._stats['size'] = self._size()
            self._not_empty.notify()
            return True
    
    def put_nowait(self, item: T, priority: Optional[int] = None) -> bool:
        """
        Ajoute un élément sans attendre
        
        Args:
            item: Élément à ajouter
            priority: Priorité (pour priority queue)
            
        Returns:
            bool: True si ajouté
            
        Raises:
            QueueFull: Si la file est pleine
        """
        if self._status in [QueueStatus.DRAINING, QueueStatus.CLOSED]:
            raise RuntimeError(f"Queue '{self.name}' is {self._status.value}")
        
        with self._not_full:
            if self.max_size > 0 and self._size() >= self.max_size:
                raise queue.Full(f"Queue '{self.name}' is full")
            
            self._push(item, priority)
            self._stats['enqueued'] += 1
            self._stats['size'] = self._size()
            self._not_empty.notify()
            return True
    
    def get(self, timeout: Optional[float] = None) -> T:
        """
        Récupère un élément de la file
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            T: Élément récupéré
            
        Raises:
            TimeoutError: Si le timeout est dépassé
        """
        if self._status == QueueStatus.CLOSED:
            raise RuntimeError(f"Queue '{self.name}' is closed")
        
        start_time = time.time()
        
        with self._not_empty:
            while self._is_empty():
                if self._status == QueueStatus.DRAINING and self._is_empty():
                    raise queue.Empty(f"Queue '{self.name}' is draining")
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise TimeoutError(f"Queue '{self.name}' empty, timeout after {timeout}s")
                    self._not_empty.wait(timeout - elapsed)
                else:
                    self._not_empty.wait()
            
            item = self._pop()
            self._stats['dequeued'] += 1
            self._stats['size'] = self._size()
            self._not_full.notify()
            return item
    
    def get_nowait(self) -> T:
        """
        Récupère un élément sans attendre
        
        Returns:
            T: Élément récupéré
            
        Raises:
            queue.Empty: Si la file est vide
        """
        if self._status == QueueStatus.CLOSED:
            raise RuntimeError(f"Queue '{self.name}' is closed")
        
        with self._not_empty:
            if self._is_empty():
                if self._status == QueueStatus.DRAINING:
                    raise queue.Empty(f"Queue '{self.name}' is draining")
                raise queue.Empty(f"Queue '{self.name}' is empty")
            
            item = self._pop()
            self._stats['dequeued'] += 1
            self._stats['size'] = self._size()
            self._not_full.notify()
            return item
    
    def peek(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Regarde le prochain élément sans le retirer
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            Optional[T]: Prochain élément
        """
        if self._status == QueueStatus.CLOSED:
            raise RuntimeError(f"Queue '{self.name}' is closed")
        
        start_time = time.time()
        
        with self._not_empty:
            while self._is_empty():
                if self._status == QueueStatus.DRAINING and self._is_empty():
                    return None
                
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return None
                    self._not_empty.wait(timeout - elapsed)
                else:
                    self._not_empty.wait()
            
            return self._peek()
    
    def clear(self):
        """Vide la file d'attente"""
        with self._lock:
            self._queue.clear()
            self._stats['size'] = 0
            self._not_empty.notify_all()
            self._not_full.notify_all()
    
    def size(self) -> int:
        """Taille de la file"""
        with self._lock:
            return self._size()
    
    def is_empty(self) -> bool:
        """Vérifie si la file est vide"""
        with self._lock:
            return self._is_empty()
    
    def is_full(self) -> bool:
        """Vérifie si la file est pleine"""
        if self.max_size == 0:
            return False
        with self._lock:
            return self._size() >= self.max_size
    
    def pause(self):
        """Met en pause la file"""
        with self._lock:
            self._status = QueueStatus.PAUSED
    
    def resume(self):
        """Reprend la file"""
        with self._lock:
            self._status = QueueStatus.ACTIVE
            self._not_empty.notify_all()
            self._not_full.notify_all()
    
    def drain(self):
        """Vide progressivement la file"""
        with self._lock:
            self._status = QueueStatus.DRAINING
            self._not_empty.notify_all()
    
    def close(self):
        """Ferme la file"""
        with self._lock:
            self._status = QueueStatus.CLOSED
            self._queue.clear()
            self._stats['size'] = 0
            self._not_empty.notify_all()
            self._not_full.notify_all()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'name': self.name,
                'type': self.queue_type.value,
                'status': self._status.value,
                'size': self._size(),
                'is_empty': self._is_empty(),
                'is_full': self.is_full(),
                'max_size': self.max_size,
            }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# ============================================================
# DELAYED QUEUE
# ============================================================

@dataclass
class DelayedItem(Generic[T]):
    """Élément avec délai"""
    item: T
    delay: float
    scheduled_time: float = field(default_factory=time.time)
    retry_count: int = 0
    priority: int = 0

class DelayedQueue(BaseQueue[T]):
    """
    File d'attente avec délai
    
    Les éléments sont disponibles après un délai spécifié
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        max_size: int = 0,
        default_delay: float = 0.0,
        **kwargs
    ):
        """
        Initialise la file avec délai
        
        Args:
            name: Nom de la file
            max_size: Taille maximale
            default_delay: Délai par défaut
            **kwargs: Arguments supplémentaires
        """
        super().__init__(name=name, max_size=max_size, queue_type=QueueType.PRIORITY, **kwargs)
        self.default_delay = default_delay
        self._delayed_items: List[DelayedItem[T]] = []
        self._processing_items: Dict[str, T] = {}
        self._processing_task = None
        self._start_processing()
    
    def _start_processing(self):
        """Démarre le traitement des éléments différés"""
        def process_loop():
            while self._status != QueueStatus.CLOSED:
                try:
                    self._process_delayed()
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Processing error: {e}")
        
        self._processing_task = threading.Thread(target=process_loop, daemon=True)
        self._processing_task.start()
    
    def _process_delayed(self):
        """Traite les éléments différés"""
        now = time.time()
        items_to_move = []
        
        with self._lock:
            # Trouver les éléments prêts
            for i, delayed_item in enumerate(self._delayed_items):
                if now >= delayed_item.scheduled_time + delayed_item.delay:
                    items_to_move.append(i)
            
            # Déplacer les éléments prêts
            for i in reversed(items_to_move):
                delayed_item = self._delayed_items.pop(i)
                self._push(delayed_item.item, delayed_item.priority)
                self._stats['enqueued'] += 1
                self._stats['size'] = self._size()
                self._not_empty.notify()
    
    def put(
        self,
        item: T,
        delay: Optional[float] = None,
        priority: int = 0,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Ajoute un élément avec délai
        
        Args:
            item: Élément à ajouter
            delay: Délai en secondes
            priority: Priorité
            timeout: Timeout
            
        Returns:
            bool: True si ajouté
        """
        if self._status in [QueueStatus.DRAINING, QueueStatus.CLOSED]:
            raise RuntimeError(f"Queue '{self.name}' is {self._status.value}")
        
        delay = delay or self.default_delay
        
        with self._not_full:
            while self.max_size > 0 and len(self._delayed_items) + self._size() >= self.max_size:
                if timeout is not None:
                    self._not_full.wait(timeout)
                else:
                    self._not_full.wait()
            
            delayed_item = DelayedItem(
                item=item,
                delay=delay,
                priority=priority
            )
            self._delayed_items.append(delayed_item)
            self._stats['enqueued'] += 1
            self._stats['size'] = self._size()
            return True
    
    def put_nowait(self, item: T, delay: Optional[float] = None, priority: int = 0) -> bool:
        """Ajoute un élément sans attendre"""
        return self.put(item, delay, priority, timeout=0)
    
    def size(self) -> int:
        """Taille de la file (incluant les éléments différés)"""
        with self._lock:
            return self._size() + len(self._delayed_items)

# ============================================================
# SCHEDULED QUEUE
# ============================================================

@dataclass
class ScheduledItem(Generic[T]):
    """Élément planifié"""
    item: T
    schedule_time: float
    cron_expression: Optional[str] = None
    interval: Optional[float] = None
    recurring: bool = False
    priority: int = 0

class ScheduledQueue(BaseQueue[T]):
    """
    File d'attente planifiée
    
    Les éléments sont disponibles à des moments spécifiques
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        max_size: int = 0,
        **kwargs
    ):
        """
        Initialise la file planifiée
        
        Args:
            name: Nom de la file
            max_size: Taille maximale
            **kwargs: Arguments supplémentaires
        """
        super().__init__(name=name, max_size=max_size, queue_type=QueueType.PRIORITY, **kwargs)
        self._scheduled_items: List[ScheduledItem[T]] = []
        self._processing_task = None
        self._start_processing()
    
    def _start_processing(self):
        """Démarre le traitement des éléments planifiés"""
        def process_loop():
            while self._status != QueueStatus.CLOSED:
                try:
                    self._process_scheduled()
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Processing error: {e}")
        
        self._processing_task = threading.Thread(target=process_loop, daemon=True)
        self._processing_task.start()
    
    def _process_scheduled(self):
        """Traite les éléments planifiés"""
        now = time.time()
        items_to_move = []
        
        with self._lock:
            # Trouver les éléments prêts
            for i, scheduled_item in enumerate(self._scheduled_items):
                if now >= scheduled_item.schedule_time:
                    items_to_move.append(i)
            
            # Déplacer les éléments prêts
            for i in reversed(items_to_move):
                scheduled_item = self._scheduled_items.pop(i)
                self._push(scheduled_item.item, scheduled_item.priority)
                self._stats['enqueued'] += 1
                self._stats['size'] = self._size()
                self._not_empty.notify()
                
                # Récurrence
                if scheduled_item.recurring:
                    if scheduled_item.interval:
                        scheduled_item.schedule_time = now + scheduled_item.interval
                        self._scheduled_items.append(scheduled_item)
    
    def put(
        self,
        item: T,
        schedule_time: Optional[float] = None,
        cron_expression: Optional[str] = None,
        interval: Optional[float] = None,
        recurring: bool = False,
        priority: int = 0,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Ajoute un élément planifié
        
        Args:
            item: Élément à ajouter
            schedule_time: Moment de planification
            cron_expression: Expression Cron
            interval: Intervalle de récurrence
            recurring: Récurrent
            priority: Priorité
            timeout: Timeout
            
        Returns:
            bool: True si ajouté
        """
        if self._status in [QueueStatus.DRAINING, QueueStatus.CLOSED]:
            raise RuntimeError(f"Queue '{self.name}' is {self._status.value}")
        
        if schedule_time is None:
            schedule_time = time.time()
        
        with self._not_full:
            while self.max_size > 0 and len(self._scheduled_items) + self._size() >= self.max_size:
                if timeout is not None:
                    self._not_full.wait(timeout)
                else:
                    self._not_full.wait()
            
            scheduled_item = ScheduledItem(
                item=item,
                schedule_time=schedule_time,
                cron_expression=cron_expression,
                interval=interval,
                recurring=recurring,
                priority=priority
            )
            self._scheduled_items.append(scheduled_item)
            self._stats['enqueued'] += 1
            self._stats['size'] = self._size()
            return True

# ============================================================
# BATCH QUEUE
# ============================================================

class BatchQueue(BaseQueue[T]):
    """
    File d'attente par lots
    
    Regroupe les éléments en lots pour un traitement par lot
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        max_size: int = 0,
        batch_size: int = 10,
        batch_timeout: float = 5.0,
        **kwargs
    ):
        """
        Initialise la file par lots
        
        Args:
            name: Nom de la file
            max_size: Taille maximale
            batch_size: Taille des lots
            batch_timeout: Timeout des lots
            **kwargs: Arguments supplémentaires
        """
        super().__init__(
            name=name,
            max_size=max_size,
            batch_size=batch_size,
            batch_timeout=batch_timeout,
            **kwargs
        )
        self._batch_buffer: List[T] = []
        self._batch_task = None
        self._start_batch_processing()
    
    def _start_batch_processing(self):
        """Démarre le traitement par lots"""
        def batch_loop():
            while self._status != QueueStatus.CLOSED:
                try:
                    self._process_batch()
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Batch processing error: {e}")
        
        self._batch_task = threading.Thread(target=batch_loop, daemon=True)
        self._batch_task.start()
    
    def _process_batch(self):
        """Traite un lot"""
        if len(self._batch_buffer) >= self.batch_size:
            batch = self._batch_buffer[:self.batch_size]
            self._batch_buffer = self._batch_buffer[self.batch_size:]
            self._push(batch, 0)
            self._stats['enqueued'] += len(batch)
            self._stats['size'] = self._size()
            self._not_empty.notify()
    
    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """
        Ajoute un élément au lot
        
        Args:
            item: Élément à ajouter
            timeout: Timeout
            
        Returns:
            bool: True si ajouté
        """
        if self._status in [QueueStatus.DRAINING, QueueStatus.CLOSED]:
            raise RuntimeError(f"Queue '{self.name}' is {self._status.value}")
        
        with self._lock:
            self._batch_buffer.append(item)
            self._stats['enqueued'] += 1
            return True
    
    def get_batch(self, timeout: Optional[float] = None) -> List[T]:
        """
        Récupère un lot
        
        Args:
            timeout: Timeout
            
        Returns:
            List[T]: Lot d'éléments
        """
        return self.get(timeout)

# ============================================================
# QUEUE MANAGER
# ============================================================

class QueueManager:
    """Gestionnaire de files d'attente"""
    
    def __init__(self):
        self._queues: Dict[str, BaseQueue] = {}
        self._lock = threading.RLock()
        self._stats = {
            'total_queues': 0,
            'total_items': 0,
        }
        
        logger.info("QueueManager initialized")
    
    def register_queue(self, name: str, queue: BaseQueue):
        """
        Enregistre une file d'attente
        
        Args:
            name: Nom de la file
            queue: File à enregistrer
        """
        with self._lock:
            self._queues[name] = queue
            self._stats['total_queues'] += 1
            logger.info(f"Queue '{name}' registered")
    
    def get_queue(self, name: str) -> Optional[BaseQueue]:
        """
        Récupère une file d'attente
        
        Args:
            name: Nom de la file
            
        Returns:
            Optional[BaseQueue]: File trouvée
        """
        with self._lock:
            return self._queues.get(name)
    
    def remove_queue(self, name: str):
        """
        Supprime une file d'attente
        
        Args:
            name: Nom de la file
        """
        with self._lock:
            if name in self._queues:
                queue = self._queues.pop(name)
                queue.close()
                self._stats['total_queues'] -= 1
                logger.info(f"Queue '{name}' removed")
    
    def get_all_queues(self) -> Dict[str, BaseQueue]:
        """
        Récupère toutes les files d'attente
        
        Returns:
            Dict[str, BaseQueue]: Files d'attente
        """
        with self._lock:
            return self._queues.copy()
    
    def close_all(self):
        """Ferme toutes les files d'attente"""
        with self._lock:
            for name, queue in self._queues.items():
                try:
                    queue.close()
                    logger.info(f"Queue '{name}' closed")
                except Exception as e:
                    logger.error(f"Error closing queue '{name}': {e}")
            self._queues.clear()
            self._stats['total_queues'] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            total_items = sum(queue.size() for queue in self._queues.values())
            
            return {
                **self._stats,
                'total_items': total_items,
                'queues': {
                    name: queue.get_stats()
                    for name, queue in self._queues.items()
                }
            }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_queue_manager: Optional[QueueManager] = None

def get_queue_manager() -> QueueManager:
    """Récupère le gestionnaire de files d'attente (singleton)"""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'QueueType',
    'QueueStatus',
    
    # Classes
    'BaseQueue',
    'DelayedQueue',
    'ScheduledQueue',
    'BatchQueue',
    'QueueManager',
    
    # Fonctions
    'get_queue_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Queues utilities module initialized")
