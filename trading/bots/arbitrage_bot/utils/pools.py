"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Pools Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de pools pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import threading
import queue
import time
import uuid
import weakref
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
    Coroutine
)
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import heapq
import random
from contextlib import contextmanager, asynccontextmanager

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

class PoolType(Enum):
    """Types de pools"""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    CACHED = "cached"
    THREADED = "threaded"
    ASYNC = "async"
    CONNECTION = "connection"
    OBJECT = "object"

class PoolStatus(Enum):
    """Statuts de pool"""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"

# ============================================================
# BASE POOL
# ============================================================

class BasePool(Generic[T]):
    """
    Pool de base avec fonctionnalités avancées
    
    Gère un ensemble d'objets réutilisables
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        max_size: int = 10,
        min_size: int = 0,
        max_idle: int = 5,
        idle_timeout: float = 60.0,
        max_lifetime: float = 3600.0,
        create_func: Optional[Callable[[], T]] = None,
        destroy_func: Optional[Callable[[T], None]] = None,
        validate_func: Optional[Callable[[T], bool]] = None,
        prefill: bool = True
    ):
        """
        Initialise le pool
        
        Args:
            name: Nom du pool
            max_size: Taille maximale
            min_size: Taille minimale
            max_idle: Nombre maximum d'objets inactifs
            idle_timeout: Timeout d'inactivité
            max_lifetime: Durée de vie maximale
            create_func: Fonction de création
            destroy_func: Fonction de destruction
            validate_func: Fonction de validation
            prefill: Pré-remplir le pool
        """
        self.name = name or str(uuid.uuid4())[:8]
        self.max_size = max_size
        self.min_size = min_size
        self.max_idle = max_idle
        self.idle_timeout = idle_timeout
        self.max_lifetime = max_lifetime
        self.create_func = create_func
        self.destroy_func = destroy_func
        self.validate_func = validate_func
        
        self._pool: Dict[str, T] = {}
        self._idle: deque = deque()
        self._active: Dict[str, T] = {}
        self._created_count = 0
        self._destroyed_count = 0
        self._stats = {
            'hits': 0,
            'misses': 0,
            'creates': 0,
            'destroys': 0,
            'timeouts': 0,
        }
        self._status = PoolStatus.ACTIVE
        self._lock = threading.RLock()
        self._cleanup_task = None
        
        if prefill and min_size > 0:
            self._prefill()
        
        self._start_cleanup()
        
        logger.info(f"Pool '{self.name}' initialized (max={max_size}, min={min_size})")
    
    def _prefill(self):
        """Pré-remplit le pool"""
        for _ in range(self.min_size):
            try:
                obj = self._create_object()
                obj_id = str(uuid.uuid4())
                self._pool[obj_id] = obj
                self._idle.append(obj_id)
                self._created_count += 1
                self._stats['creates'] += 1
            except Exception as e:
                logger.error(f"Failed to prefill pool: {e}")
    
    def _start_cleanup(self):
        """Démarre le nettoyage automatique"""
        def cleanup_loop():
            while self._status != PoolStatus.CLOSED:
                try:
                    time.sleep(30)
                    self._cleanup()
                except Exception as e:
                    logger.error(f"Cleanup error: {e}")
        
        self._cleanup_task = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_task.start()
    
    def _cleanup(self):
        """Nettoie les objets expirés"""
        with self._lock:
            if self._status == PoolStatus.CLOSED:
                return
            
            now = time.time()
            to_remove = []
            
            # Nettoyer les objets inactifs
            for obj_id in list(self._idle):
                obj_info = self._get_object_info(obj_id)
                if not obj_info:
                    continue
                
                # Vérifier la durée de vie
                if now - obj_info['created_at'] > self.max_lifetime:
                    to_remove.append(obj_id)
                    continue
                
                # Vérifier l'inactivité
                if len(self._idle) > self.max_idle:
                    to_remove.append(obj_id)
                    continue
                
                if now - obj_info['last_used'] > self.idle_timeout:
                    to_remove.append(obj_id)
            
            for obj_id in to_remove:
                self._destroy_object(obj_id)
            
            # Ajouter des objets si nécessaire
            current_size = len(self._pool)
            if current_size < self.min_size:
                for _ in range(self.min_size - current_size):
                    try:
                        obj = self._create_object()
                        obj_id = str(uuid.uuid4())
                        self._pool[obj_id] = obj
                        self._idle.append(obj_id)
                        self._created_count += 1
                        self._stats['creates'] += 1
                    except Exception as e:
                        logger.error(f"Failed to create object during cleanup: {e}")
    
    def _create_object(self) -> T:
        """
        Crée un nouvel objet
        
        Returns:
            T: Objet créé
        """
        if self.create_func:
            return self.create_func()
        raise NotImplementedError("create_func must be provided")
    
    def _destroy_object(self, obj_id: str):
        """
        Détruit un objet
        
        Args:
            obj_id: ID de l'objet
        """
        if obj_id in self._pool:
            obj = self._pool.pop(obj_id)
            if self.destroy_func:
                try:
                    self.destroy_func(obj)
                except Exception as e:
                    logger.error(f"Destroy error: {e}")
            self._destroyed_count += 1
            self._stats['destroys'] += 1
        
        if obj_id in self._idle:
            self._idle.remove(obj_id)
    
    def _get_object_info(self, obj_id: str) -> Optional[Dict[str, Any]]:
        """Récupère les informations d'un objet"""
        # Cette méthode peut être surchargée pour stocker plus d'informations
        return {
            'id': obj_id,
            'created_at': time.time(),
            'last_used': time.time(),
        }
    
    def acquire(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Acquiert un objet du pool
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            Optional[T]: Objet acquis
            
        Raises:
            TimeoutError: Si le timeout est dépassé
        """
        if self._status == PoolStatus.CLOSED:
            raise RuntimeError(f"Pool '{self.name}' is closed")
        
        start_time = time.time()
        
        while True:
            with self._lock:
                # Trouver un objet inactif valide
                for obj_id in list(self._idle):
                    obj = self._pool.get(obj_id)
                    if obj is None:
                        self._idle.remove(obj_id)
                        continue
                    
                    # Valider l'objet
                    if self.validate_func and not self.validate_func(obj):
                        self._destroy_object(obj_id)
                        continue
                    
                    # Vérifier la durée de vie
                    obj_info = self._get_object_info(obj_id)
                    if obj_info and time.time() - obj_info['created_at'] > self.max_lifetime:
                        self._destroy_object(obj_id)
                        continue
                    
                    # Acquérir l'objet
                    self._idle.remove(obj_id)
                    self._active[obj_id] = obj
                    self._stats['hits'] += 1
                    return obj
                
                # Créer un nouvel objet si possible
                if len(self._pool) < self.max_size:
                    try:
                        obj = self._create_object()
                        obj_id = str(uuid.uuid4())
                        self._pool[obj_id] = obj
                        self._active[obj_id] = obj
                        self._created_count += 1
                        self._stats['creates'] += 1
                        self._stats['misses'] += 1
                        return obj
                    except Exception as e:
                        logger.error(f"Failed to create object: {e}")
                        raise
            
            # Attendre qu'un objet soit disponible
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    self._stats['timeouts'] += 1
                    raise TimeoutError(f"Pool '{self.name}' acquisition timeout after {timeout}s")
            
            time.sleep(0.1)
    
    def release(self, obj: T):
        """
        Libère un objet dans le pool
        
        Args:
            obj: Objet à libérer
        """
        with self._lock:
            if self._status == PoolStatus.CLOSED:
                return
            
            # Trouver l'ID de l'objet
            obj_id = None
            for oid, o in self._active.items():
                if o is obj:
                    obj_id = oid
                    break
            
            if obj_id is None:
                logger.warning(f"Object not found in active pool")
                return
            
            # Déplacer vers idle
            self._active.pop(obj_id, None)
            
            # Valider l'objet avant de le remettre
            if self.validate_func and not self.validate_func(obj):
                self._destroy_object(obj_id)
                return
            
            # Vérifier la durée de vie
            obj_info = self._get_object_info(obj_id)
            if obj_info and time.time() - obj_info['created_at'] > self.max_lifetime:
                self._destroy_object(obj_id)
                return
            
            self._idle.append(obj_id)
    
    def discard(self, obj: T):
        """
        Supprime un objet du pool
        
        Args:
            obj: Objet à supprimer
        """
        with self._lock:
            # Trouver l'ID de l'objet
            obj_id = None
            for oid, o in list(self._pool.items()):
                if o is obj:
                    obj_id = oid
                    break
            
            if obj_id:
                self._destroy_object(obj_id)
    
    def close(self):
        """Ferme le pool"""
        with self._lock:
            self._status = PoolStatus.CLOSED
            
            # Détruire tous les objets
            for obj_id in list(self._pool.keys()):
                self._destroy_object(obj_id)
            
            self._idle.clear()
            self._active.clear()
        
        logger.info(f"Pool '{self.name}' closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'name': self.name,
                'status': self._status.value,
                'size': len(self._pool),
                'idle': len(self._idle),
                'active': len(self._active),
                'created_total': self._created_count,
                'destroyed_total': self._destroyed_count,
                'max_size': self.max_size,
                'min_size': self.min_size,
                'max_idle': self.max_idle,
            }
    
    @contextmanager
    def get(self, timeout: Optional[float] = None) -> Iterator[T]:
        """
        Context manager pour acquérir et libérer un objet
        
        Args:
            timeout: Timeout en secondes
            
        Yields:
            T: Objet acquis
        """
        obj = self.acquire(timeout)
        try:
            yield obj
        finally:
            self.release(obj)

# ============================================================
# THREAD POOL
# ============================================================

class ThreadPool(BasePool):
    """Pool de threads"""
    
    def __init__(
        self,
        max_workers: int = 10,
        min_workers: int = 0,
        name: Optional[str] = None,
        thread_name_prefix: str = "pool-thread",
        daemon: bool = True
    ):
        """
        Initialise le pool de threads
        
        Args:
            max_workers: Nombre maximum de workers
            min_workers: Nombre minimum de workers
            name: Nom du pool
            thread_name_prefix: Préfixe du nom des threads
            daemon: Threads daemon
        """
        self.thread_name_prefix = thread_name_prefix
        self.daemon = daemon
        self._thread_counter = 0
        self._task_queue = queue.Queue()
        self._workers = []
        
        super().__init__(
            name=name,
            max_size=max_workers,
            min_size=min_workers,
            create_func=self._create_thread,
            destroy_func=self._destroy_thread
        )
    
    def _create_thread(self) -> threading.Thread:
        """Crée un thread"""
        self._thread_counter += 1
        thread = threading.Thread(
            target=self._worker_loop,
            name=f"{self.thread_name_prefix}-{self._thread_counter}",
            daemon=self.daemon
        )
        thread.start()
        return thread
    
    def _destroy_thread(self, thread: threading.Thread):
        """Détruit un thread"""
        # Les threads ne peuvent pas être détruits directement
        pass
    
    def _worker_loop(self):
        """Boucle du worker"""
        while True:
            try:
                task, args, kwargs = self._task_queue.get(timeout=1)
                try:
                    task(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Task error: {e}")
                self._task_queue.task_done()
            except queue.Empty:
                # Vérifier si le pool est en cours d'arrêt
                if self._status == PoolStatus.CLOSED:
                    break
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    def submit(self, task: Callable, *args, **kwargs):
        """
        Soumet une tâche au pool
        
        Args:
            task: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
        """
        if self._status == PoolStatus.CLOSED:
            raise RuntimeError(f"Pool '{self.name}' is closed")
        
        self._task_queue.put((task, args, kwargs))
    
    def close(self):
        """Ferme le pool et attend la fin des tâches"""
        self._task_queue.join()
        super().close()

# ============================================================
# ASYNC POOL
# ============================================================

class AsyncPool(BasePool):
    """Pool asynchrone"""
    
    def __init__(
        self,
        max_workers: int = 10,
        min_workers: int = 0,
        name: Optional[str] = None
    ):
        """
        Initialise le pool asynchrone
        
        Args:
            max_workers: Nombre maximum de workers
            min_workers: Nombre minimum de workers
            name: Nom du pool
        """
        self._task_queue = asyncio.Queue()
        self._workers = []
        
        super().__init__(
            name=name,
            max_size=max_workers,
            min_size=min_workers,
            create_func=self._create_worker,
            destroy_func=self._destroy_worker
        )
    
    def _create_worker(self) -> asyncio.Task:
        """Crée un worker"""
        worker = asyncio.create_task(self._worker_loop())
        return worker
    
    def _destroy_worker(self, worker: asyncio.Task):
        """Détruit un worker"""
        worker.cancel()
    
    async def _worker_loop(self):
        """Boucle du worker asynchrone"""
        while True:
            try:
                coro = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                try:
                    await coro
                except Exception as e:
                    logger.error(f"Task error: {e}")
                self._task_queue.task_done()
            except asyncio.TimeoutError:
                if self._status == PoolStatus.CLOSED:
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    async def submit(self, coro: Coroutine):
        """
        Soumet une coroutine au pool
        
        Args:
            coro: Coroutine à exécuter
        """
        if self._status == PoolStatus.CLOSED:
            raise RuntimeError(f"Pool '{self.name}' is closed")
        
        await self._task_queue.put(coro)
    
    async def close(self):
        """Ferme le pool et attend la fin des tâches"""
        await self._task_queue.join()
        self._status = PoolStatus.CLOSED
        for worker in self._workers:
            worker.cancel()
        
        if self._workers:
            await asyncio.wait(self._workers)

# ============================================================
# CONNECTION POOL
# ============================================================

class ConnectionPool(BasePool):
    """Pool de connexions"""
    
    def __init__(
        self,
        create_connection: Callable[[], Any],
        max_connections: int = 10,
        min_connections: int = 0,
        max_idle: int = 5,
        idle_timeout: float = 60.0,
        max_lifetime: float = 3600.0,
        name: Optional[str] = None,
        validate_connection: Optional[Callable[[Any], bool]] = None,
        close_connection: Optional[Callable[[Any], None]] = None
    ):
        """
        Initialise le pool de connexions
        
        Args:
            create_connection: Fonction de création de connexion
            max_connections: Nombre maximum de connexions
            min_connections: Nombre minimum de connexions
            max_idle: Nombre maximum de connexions inactives
            idle_timeout: Timeout d'inactivité
            max_lifetime: Durée de vie maximale
            name: Nom du pool
            validate_connection: Fonction de validation de connexion
            close_connection: Fonction de fermeture de connexion
        """
        self._connection_id_counter = 0
        self._connection_info: Dict[str, Dict[str, Any]] = {}
        
        super().__init__(
            name=name or "connection-pool",
            max_size=max_connections,
            min_size=min_connections,
            max_idle=max_idle,
            idle_timeout=idle_timeout,
            max_lifetime=max_lifetime,
            create_func=create_connection,
            destroy_func=close_connection,
            validate_func=validate_connection
        )
    
    def _get_object_info(self, obj_id: str) -> Dict[str, Any]:
        """Récupère les informations d'une connexion"""
        return self._connection_info.get(obj_id, {
            'id': obj_id,
            'created_at': time.time(),
            'last_used': time.time(),
        })
    
    def acquire(self, timeout: Optional[float] = None) -> Any:
        """
        Acquiert une connexion
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            Any: Connexion acquise
        """
        conn = super().acquire(timeout)
        
        # Mettre à jour les informations
        with self._lock:
            for obj_id, obj in self._active.items():
                if obj is conn:
                    if obj_id not in self._connection_info:
                        self._connection_info[obj_id] = {
                            'id': obj_id,
                            'created_at': time.time(),
                            'last_used': time.time(),
                        }
                    self._connection_info[obj_id]['last_used'] = time.time()
                    break
        
        return conn
    
    def release(self, conn: Any):
        """Libère une connexion"""
        with self._lock:
            for obj_id, obj in self._active.items():
                if obj is conn:
                    if obj_id in self._connection_info:
                        self._connection_info[obj_id]['last_used'] = time.time()
                    break
        
        super().release(conn)

# ============================================================
# POOL MANAGER
# ============================================================

class PoolManager:
    """Gestionnaire de pools"""
    
    def __init__(self):
        self._pools: Dict[str, BasePool] = {}
        self._lock = threading.RLock()
        self._stats = {
            'total_pools': 0,
            'total_objects': 0,
            'total_acquires': 0,
            'total_releases': 0,
        }
        
        logger.info("PoolManager initialized")
    
    def register_pool(self, name: str, pool: BasePool):
        """
        Enregistre un pool
        
        Args:
            name: Nom du pool
            pool: Pool à enregistrer
        """
        with self._lock:
            self._pools[name] = pool
            self._stats['total_pools'] += 1
            logger.info(f"Pool '{name}' registered")
    
    def get_pool(self, name: str) -> Optional[BasePool]:
        """
        Récupère un pool
        
        Args:
            name: Nom du pool
            
        Returns:
            Optional[BasePool]: Pool trouvé
        """
        with self._lock:
            return self._pools.get(name)
    
    def remove_pool(self, name: str):
        """
        Supprime un pool
        
        Args:
            name: Nom du pool
        """
        with self._lock:
            if name in self._pools:
                pool = self._pools.pop(name)
                pool.close()
                self._stats['total_pools'] -= 1
                logger.info(f"Pool '{name}' removed")
    
    def get_all_pools(self) -> Dict[str, BasePool]:
        """
        Récupère tous les pools
        
        Returns:
            Dict[str, BasePool]: Pools
        """
        with self._lock:
            return self._pools.copy()
    
    def close_all(self):
        """Ferme tous les pools"""
        with self._lock:
            for name, pool in self._pools.items():
                try:
                    pool.close()
                    logger.info(f"Pool '{name}' closed")
                except Exception as e:
                    logger.error(f"Error closing pool '{name}': {e}")
            self._pools.clear()
            self._stats['total_pools'] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            total_objects = sum(pool.get_stats()['size'] for pool in self._pools.values())
            
            return {
                **self._stats,
                'total_objects': total_objects,
                'pools': {
                    name: pool.get_stats()
                    for name, pool in self._pools.items()
                }
            }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_pool_manager: Optional[PoolManager] = None

def get_pool_manager() -> PoolManager:
    """Récupère le gestionnaire de pools (singleton)"""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager()
    return _pool_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'PoolType',
    'PoolStatus',
    
    # Classes
    'BasePool',
    'ThreadPool',
    'AsyncPool',
    'ConnectionPool',
    'PoolManager',
    
    # Fonctions
    'get_pool_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Pools utilities module initialized")
