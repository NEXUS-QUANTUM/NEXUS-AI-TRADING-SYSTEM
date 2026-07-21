"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Locks Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de verrous pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import threading
import time
import uuid
import contextlib
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
    Set,
    Iterator,
    AsyncIterator,
    ContextManager,
    AsyncContextManager,
    Coroutine
)
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import heapq
import weakref

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# LOCK TYPES
# ============================================================

class LockType(Enum):
    """Types de verrous"""
    MUTEX = "mutex"
    SEMAPHORE = "semaphore"
    RW = "rw"  # Read-Write
    STRIPED = "striped"
    FAIR = "fair"
    REENTRANT = "reentrant"

class LockAcquireResult(Enum):
    """Résultats d'acquisition de verrou"""
    ACQUIRED = "acquired"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    FAILED = "failed"

# ============================================================
# BASE LOCK
# ============================================================

class BaseLock(Generic[T]):
    """
    Verrou de base avec fonctionnalités avancées
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        timeout: Optional[float] = None,
        retry_attempts: int = 3,
        retry_delay: float = 0.1,
        max_waiters: Optional[int] = None
    ):
        """
        Initialise le verrou
        
        Args:
            name: Nom du verrou
            timeout: Timeout par défaut
            retry_attempts: Nombre de tentatives
            retry_delay: Délai entre les tentatives
            max_waiters: Nombre maximum de waiters
        """
        self.name = name or str(uuid.uuid4())[:8]
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.max_waiters = max_waiters
        
        self._lock = threading.RLock() if self._is_reentrant() else threading.Lock()
        self._owner = None
        self._recursion_count = 0
        self._waiters: Dict[str, threading.Event] = {}
        self._acquired_count = 0
        self._released_count = 0
        self._created_at = time.time()
        self._last_acquired = None
        self._last_released = None
        self._stats = {
            'acquires': 0,
            'releases': 0,
            'contention': 0,
            'max_wait_time': 0,
            'avg_wait_time': 0,
            'total_wait_time': 0,
        }
        
        logger.debug(f"Lock '{self.name}' initialized")
    
    def _is_reentrant(self) -> bool:
        """Vérifie si le verrou est réentrant"""
        return False
    
    def acquire(
        self,
        blocking: bool = True,
        timeout: Optional[float] = None,
        timeout_raise: bool = False
    ) -> bool:
        """
        Acquiert le verrou
        
        Args:
            blocking: Bloquer jusqu'à acquisition
            timeout: Timeout en secondes
            timeout_raise: Lever une exception en cas de timeout
            
        Returns:
            bool: True si acquis
            
        Raises:
            TimeoutError: Si timeout_raise est True et timeout dépassé
        """
        if not blocking:
            return self._acquire_non_blocking()
        
        start_time = time.perf_counter()
        wait_time = 0
        
        try:
            # Tentatives avec retry
            for attempt in range(self.retry_attempts):
                if self._try_acquire(timeout):
                    self._stats['acquires'] += 1
                    self._last_acquired = time.time()
                    
                    if wait_time > 0:
                        self._stats['total_wait_time'] += wait_time
                        self._stats['avg_wait_time'] = (
                            self._stats['total_wait_time'] / self._stats['acquires']
                        )
                        self._stats['max_wait_time'] = max(
                            self._stats['max_wait_time'],
                            wait_time
                        )
                    
                    return True
                
                wait_time = time.perf_counter() - start_time
                
                if timeout is not None and wait_time >= timeout:
                    if timeout_raise:
                        raise TimeoutError(f"Lock '{self.name}' acquisition timeout after {timeout}s")
                    return False
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    self._stats['contention'] += 1
        
        except Exception as e:
            logger.error(f"Lock '{self.name}' acquisition error: {e}")
            raise
        
        return False
    
    def _acquire_non_blocking(self) -> bool:
        """Acquisition non bloquante"""
        return self._try_acquire(0)
    
    def _try_acquire(self, timeout: Optional[float]) -> bool:
        """
        Tentative d'acquisition
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            bool: True si acquis
        """
        # Vérifier le nombre maximum de waiters
        if self.max_waiters is not None:
            with self._lock:
                if len(self._waiters) >= self.max_waiters:
                    return False
        
        # Tentative d'acquisition
        acquired = self._lock.acquire(timeout=timeout)
        
        if acquired:
            self._owner = threading.current_thread()
            self._recursion_count += 1
            self._acquired_count += 1
            
            # Notifier les waiters
            with self._lock:
                for waiter_id, event in list(self._waiters.items()):
                    if event.is_set():
                        del self._waiters[waiter_id]
        
        return acquired
    
    def release(self):
        """Libère le verrou"""
        if self._lock.locked():
            self._lock.release()
            self._recursion_count = max(0, self._recursion_count - 1)
            if self._recursion_count == 0:
                self._owner = None
            self._released_count += 1
            self._last_released = time.time()
            self._stats['releases'] += 1
    
    def locked(self) -> bool:
        """Vérifie si le verrou est verrouillé"""
        return self._lock.locked()
    
    def get_owner(self) -> Optional[threading.Thread]:
        """Récupère le propriétaire du verrou"""
        return self._owner
    
    def get_waiters(self) -> int:
        """Récupère le nombre de waiters"""
        with self._lock:
            return len(self._waiters)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        return {
            **self._stats,
            'name': self.name,
            'locked': self.locked(),
            'owner': self._owner.name if self._owner else None,
            'recursion_count': self._recursion_count,
            'waiters': self.get_waiters(),
            'acquired_count': self._acquired_count,
            'released_count': self._released_count,
            'created_at': self._created_at,
            'last_acquired': self._last_acquired,
            'last_released': self._last_released,
            'age': time.time() - self._created_at,
        }
    
    def __enter__(self):
        """Context manager entry"""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name='{self.name}' "
            f"locked={self.locked()} owner={self._owner.name if self._owner else 'None'}>"
        )

# ============================================================
# REENTRANT LOCK
# ============================================================

class ReentrantLock(BaseLock):
    """Verrou réentrant"""
    
    def _is_reentrant(self) -> bool:
        return True

# ============================================================
# READ-WRITE LOCK
# ============================================================

class ReadWriteLock:
    """
    Verrou lecture-écriture
    
    Permet plusieurs lecteurs simultanés ou un unique écrivain
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialise le verrou lecture-écriture
        
        Args:
            name: Nom du verrou
        """
        self.name = name or str(uuid.uuid4())[:8]
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._readers = 0
        self._writers = 0
        self._waiting_writers = 0
        self._stats = {
            'read_acquires': 0,
            'write_acquires': 0,
            'read_releases': 0,
            'write_releases': 0,
            'max_readers': 0,
        }
        self._created_at = time.time()
        
        logger.debug(f"ReadWriteLock '{self.name}' initialized")
    
    def acquire_read(self, blocking: bool = True) -> bool:
        """
        Acquiert un verrou de lecture
        
        Args:
            blocking: Bloquer jusqu'à acquisition
            
        Returns:
            bool: True si acquis
        """
        if not blocking:
            return self._acquire_read_non_blocking()
        
        with self._read_lock:
            while self._writers > 0 or self._waiting_writers > 0:
                self._read_lock.wait()
            
            self._readers += 1
            self._stats['read_acquires'] += 1
            self._stats['max_readers'] = max(self._stats['max_readers'], self._readers)
            return True
    
    def _acquire_read_non_blocking(self) -> bool:
        """Acquisition de lecture non bloquante"""
        with self._read_lock:
            if self._writers > 0 or self._waiting_writers > 0:
                return False
            
            self._readers += 1
            self._stats['read_acquires'] += 1
            self._stats['max_readers'] = max(self._stats['max_readers'], self._readers)
            return True
    
    def release_read(self):
        """Libère un verrou de lecture"""
        with self._read_lock:
            self._readers -= 1
            self._stats['read_releases'] += 1
            if self._readers == 0:
                self._read_lock.notify_all()
    
    def acquire_write(self, blocking: bool = True) -> bool:
        """
        Acquiert un verrou d'écriture
        
        Args:
            blocking: Bloquer jusqu'à acquisition
            
        Returns:
            bool: True si acquis
        """
        if not blocking:
            return self._acquire_write_non_blocking()
        
        with self._write_lock:
            self._waiting_writers += 1
            
            while self._readers > 0 or self._writers > 0:
                self._write_lock.wait()
            
            self._waiting_writers -= 1
            self._writers += 1
            self._stats['write_acquires'] += 1
            return True
    
    def _acquire_write_non_blocking(self) -> bool:
        """Acquisition d'écriture non bloquante"""
        with self._write_lock:
            if self._readers > 0 or self._writers > 0:
                return False
            
            self._writers += 1
            self._stats['write_acquires'] += 1
            return True
    
    def release_write(self):
        """Libère un verrou d'écriture"""
        with self._write_lock:
            self._writers -= 1
            self._stats['write_releases'] += 1
            self._write_lock.notify_all()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        return {
            **self._stats,
            'name': self.name,
            'readers': self._readers,
            'writers': self._writers,
            'waiting_writers': self._waiting_writers,
            'created_at': self._created_at,
            'age': time.time() - self._created_at,
        }
    
    @contextlib.contextmanager
    def read(self):
        """Context manager pour la lecture"""
        self.acquire_read()
        try:
            yield
        finally:
            self.release_read()
    
    @contextlib.contextmanager
    def write(self):
        """Context manager pour l'écriture"""
        self.acquire_write()
        try:
            yield
        finally:
            self.release_write()

# ============================================================
# STRIPED LOCK
# ============================================================

class StripedLock:
    """
    Verrou strié
    
    Partitionne les verrous en un ensemble de verrous plus petits
    pour réduire la contention
    """
    
    def __init__(
        self,
        stripes: int = 16,
        name: Optional[str] = None,
        lock_class: type = BaseLock
    ):
        """
        Initialise le verrou strié
        
        Args:
            stripes: Nombre de bandes
            name: Nom du verrou
            lock_class: Classe de verrou à utiliser
        """
        self.name = name or str(uuid.uuid4())[:8]
        self.stripes = stripes
        self.lock_class = lock_class
        self._locks = [lock_class(f"{name or ''}_{i}") for i in range(stripes)]
        self._stats = {
            'total_acquires': 0,
            'total_releases': 0,
            'contention': 0,
        }
        self._created_at = time.time()
        
        logger.debug(f"StripedLock '{self.name}' initialized with {stripes} stripes")
    
    def _get_lock(self, key: Any) -> BaseLock:
        """Récupère le verrou pour une clé"""
        if isinstance(key, (int, str)):
            hash_value = hash(key)
        else:
            hash_value = id(key)
        
        index = hash_value % self.stripes
        return self._locks[index]
    
    def acquire(
        self,
        key: Any,
        blocking: bool = True,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Acquiert un verrou pour une clé
        
        Args:
            key: Clé
            blocking: Bloquer jusqu'à acquisition
            timeout: Timeout en secondes
            
        Returns:
            bool: True si acquis
        """
        lock = self._get_lock(key)
        acquired = lock.acquire(blocking, timeout)
        
        if acquired:
            self._stats['total_acquires'] += 1
        
        return acquired
    
    def release(self, key: Any):
        """
        Libère un verrou pour une clé
        
        Args:
            key: Clé
        """
        lock = self._get_lock(key)
        lock.release()
        self._stats['total_releases'] += 1
    
    def locked(self, key: Any) -> bool:
        """
        Vérifie si le verrou est verrouillé pour une clé
        
        Args:
            key: Clé
            
        Returns:
            bool: True si verrouillé
        """
        lock = self._get_lock(key)
        return lock.locked()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        locks_stats = [lock.get_stats() for lock in self._locks]
        
        return {
            **self._stats,
            'name': self.name,
            'stripes': self.stripes,
            'locks': locks_stats,
            'created_at': self._created_at,
            'age': time.time() - self._created_at,
        }
    
    @contextlib.contextmanager
    def lock(self, key: Any):
        """
        Context manager pour une clé
        
        Args:
            key: Clé
            
        Yields:
            None
        """
        self.acquire(key)
        try:
            yield
        finally:
            self.release(key)

# ============================================================
# FAIR LOCK
# ============================================================

class FairLock:
    """
    Verrou équitable
    
    Garantit l'ordre d'acquisition FIFO
    """
    
    def __init__(self, name: Optional[str] = None):
        """
        Initialise le verrou équitable
        
        Args:
            name: Nom du verrou
        """
        self.name = name or str(uuid.uuid4())[:8]
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._queue: List[threading.Thread] = []
        self._owner: Optional[threading.Thread] = None
        self._recursion_count = 0
        self._stats = {
            'acquires': 0,
            'releases': 0,
            'queue_length': 0,
            'max_queue_length': 0,
        }
        self._created_at = time.time()
        
        logger.debug(f"FairLock '{self.name}' initialized")
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquiert le verrou
        
        Args:
            blocking: Bloquer jusqu'à acquisition
            
        Returns:
            bool: True si acquis
        """
        current_thread = threading.current_thread()
        
        # Réentrance
        if self._owner == current_thread:
            self._recursion_count += 1
            return True
        
        if not blocking:
            return self._acquire_non_blocking(current_thread)
        
        with self._condition:
            self._queue.append(current_thread)
            self._stats['queue_length'] = len(self._queue)
            self._stats['max_queue_length'] = max(
                self._stats['max_queue_length'],
                len(self._queue)
            )
            
            while self._owner is not None or self._queue[0] != current_thread:
                self._condition.wait()
            
            self._queue.pop(0)
            self._owner = current_thread
            self._recursion_count = 1
            self._stats['acquires'] += 1
            
            return True
    
    def _acquire_non_blocking(self, thread: threading.Thread) -> bool:
        """Acquisition non bloquante"""
        with self._condition:
            if self._owner is None:
                self._owner = thread
                self._recursion_count = 1
                self._stats['acquires'] += 1
                return True
            return False
    
    def release(self):
        """Libère le verrou"""
        current_thread = threading.current_thread()
        
        if self._owner != current_thread:
            raise RuntimeError("Cannot release lock owned by another thread")
        
        with self._condition:
            self._recursion_count -= 1
            
            if self._recursion_count == 0:
                self._owner = None
                self._stats['releases'] += 1
                self._condition.notify_all()
    
    def locked(self) -> bool:
        """Vérifie si le verrou est verrouillé"""
        return self._owner is not None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._condition:
            return {
                **self._stats,
                'name': self.name,
                'locked': self.locked(),
                'owner': self._owner.name if self._owner else None,
                'queue_length': len(self._queue),
                'created_at': self._created_at,
                'age': time.time() - self._created_at,
            }
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

# ============================================================
# LOCK MANAGER
# ============================================================

class LockManager:
    """
    Gestionnaire de verrous
    
    Gère un pool de verrous et fournit des méthodes pour les acquérir
    """
    
    def __init__(self):
        self._locks: Dict[str, BaseLock] = {}
        self._rw_locks: Dict[str, ReadWriteLock] = {}
        self._striped_locks: Dict[str, StripedLock] = {}
        self._fair_locks: Dict[str, FairLock] = {}
        self._lock = threading.RLock()
        self._stats = {
            'total_locks': 0,
            'total_acquires': 0,
            'total_releases': 0,
            'contention': 0,
        }
        self._created_at = time.time()
        
        logger.info("LockManager initialized")
    
    def get_lock(
        self,
        name: str,
        lock_type: LockType = LockType.MUTEX,
        **kwargs
    ) -> BaseLock:
        """
        Récupère ou crée un verrou
        
        Args:
            name: Nom du verrou
            lock_type: Type de verrou
            **kwargs: Arguments supplémentaires
            
        Returns:
            BaseLock: Verrou
        """
        with self._lock:
            if lock_type == LockType.MUTEX:
                if name not in self._locks:
                    self._locks[name] = BaseLock(name, **kwargs)
                    self._stats['total_locks'] += 1
                return self._locks[name]
            
            elif lock_type == LockType.REENTRANT:
                if name not in self._locks:
                    self._locks[name] = ReentrantLock(name, **kwargs)
                    self._stats['total_locks'] += 1
                return self._locks[name]
            
            elif lock_type == LockType.RW:
                if name not in self._rw_locks:
                    self._rw_locks[name] = ReadWriteLock(name)
                    self._stats['total_locks'] += 1
                return self._rw_locks[name]
            
            elif lock_type == LockType.STRIPED:
                if name not in self._striped_locks:
                    stripes = kwargs.get('stripes', 16)
                    lock_class = kwargs.get('lock_class', BaseLock)
                    self._striped_locks[name] = StripedLock(
                        stripes=stripes,
                        name=name,
                        lock_class=lock_class
                    )
                    self._stats['total_locks'] += 1
                return self._striped_locks[name]
            
            elif lock_type == LockType.FAIR:
                if name not in self._fair_locks:
                    self._fair_locks[name] = FairLock(name)
                    self._stats['total_locks'] += 1
                return self._fair_locks[name]
            
            else:
                raise ValueError(f"Unsupported lock type: {lock_type}")
    
    def get_locks(self) -> Dict[str, Dict[str, Any]]:
        """
        Récupère tous les verrous
        
        Returns:
            Dict[str, Dict[str, Any]]: Verrous par type
        """
        with self._lock:
            return {
                'mutex': {name: lock.get_stats() for name, lock in self._locks.items()},
                'rw': {name: lock.get_stats() for name, lock in self._rw_locks.items()},
                'striped': {name: lock.get_stats() for name, lock in self._striped_locks.items()},
                'fair': {name: lock.get_stats() for name, lock in self._fair_locks.items()},
            }
    
    def clear_locks(self):
        """Supprime tous les verrous"""
        with self._lock:
            self._locks.clear()
            self._rw_locks.clear()
            self._striped_locks.clear()
            self._fair_locks.clear()
            self._stats['total_locks'] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'mutex_locks': len(self._locks),
                'rw_locks': len(self._rw_locks),
                'striped_locks': len(self._striped_locks),
                'fair_locks': len(self._fair_locks),
                'total_locks': self._stats['total_locks'],
                'created_at': self._created_at,
                'age': time.time() - self._created_at,
            }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_lock_manager: Optional[LockManager] = None

def get_lock_manager() -> LockManager:
    """Récupère le gestionnaire de verrous (singleton)"""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = LockManager()
    return _lock_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'LockType',
    'LockAcquireResult',
    
    # Classes
    'BaseLock',
    'ReentrantLock',
    'ReadWriteLock',
    'StripedLock',
    'FairLock',
    'LockManager',
    
    # Fonctions
    'get_lock_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Locks utilities module initialized")
