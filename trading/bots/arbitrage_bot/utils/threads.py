"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Threads Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de threads pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import threading
import queue
import time
import logging
import sys
import traceback
import signal
import os
import uuid
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
    ContextManager,
    Coroutine
)
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future, wait, as_completed
from contextlib import contextmanager
import weakref
import gc

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
# ENUMS
# ============================================================

class ThreadStatus(Enum):
    """Statuts de thread"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class ThreadPriority(Enum):
    """Priorités de thread"""
    LOW = 1
    NORMAL = 5
    HIGH = 9
    CRITICAL = 10

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ThreadInfo:
    """Informations sur un thread"""
    id: str
    name: str
    thread: threading.Thread
    status: ThreadStatus
    created_at: float
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    last_activity: Optional[float] = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# BASE THREAD
# ============================================================

class BaseThread(threading.Thread):
    """
    Thread de base avec fonctionnalités avancées
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        daemon: bool = True,
        priority: ThreadPriority = ThreadPriority.NORMAL,
        target: Optional[Callable] = None,
        args: tuple = (),
        kwargs: dict = None,
        max_tasks: Optional[int] = None,
        idle_timeout: Optional[float] = None,
        max_errors: Optional[int] = None
    ):
        """
        Initialise le thread
        
        Args:
            name: Nom du thread
            daemon: Thread daemon
            priority: Priorité
            target: Fonction cible
            args: Arguments positionnels
            kwargs: Arguments nommés
            max_tasks: Nombre maximum de tâches
            idle_timeout: Timeout d'inactivité
            max_errors: Nombre maximum d'erreurs
        """
        self.thread_id = str(uuid.uuid4())[:8]
        self.thread_name = name or f"Thread-{self.thread_id}"
        self.priority = priority
        self.target = target
        self.args = args
        self.kwargs = kwargs or {}
        self.max_tasks = max_tasks
        self.idle_timeout = idle_timeout
        self.max_errors = max_errors
        
        self._status = ThreadStatus.IDLE
        self._task_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._lock = threading.RLock()
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._errors: List[str] = []
        self._created_at = time.time()
        self._started_at = None
        self._stopped_at = None
        self._last_activity = None
        
        super().__init__(
            name=self.thread_name,
            daemon=daemon,
            target=self._run
        )
        
        logger.debug(f"Thread '{self.thread_name}' initialized")
    
    def _run(self):
        """Boucle principale du thread"""
        self._started_at = time.time()
        self._status = ThreadStatus.RUNNING
        
        try:
            while not self._stop_event.is_set():
                # Vérifier l'état de pause
                if self._pause_event.is_set():
                    time.sleep(0.1)
                    continue
                
                # Vérifier les limites
                if self.max_tasks and self._tasks_completed >= self.max_tasks:
                    self._status = ThreadStatus.STOPPING
                    break
                
                if self.max_errors and len(self._errors) >= self.max_errors:
                    self._status = ThreadStatus.STOPPING
                    break
                
                # Récupérer une tâche
                try:
                    task = self._task_queue.get(timeout=1.0)
                except queue.Empty:
                    # Vérifier le timeout d'inactivité
                    if self.idle_timeout and self._last_activity:
                        if time.time() - self._last_activity > self.idle_timeout:
                            self._status = ThreadStatus.STOPPING
                            break
                    continue
                
                # Exécuter la tâche
                try:
                    self._last_activity = time.time()
                    
                    if self.target:
                        self.target(*self.args, **self.kwargs)
                    else:
                        task()
                    
                    self._tasks_completed += 1
                    logger.debug(f"Thread '{self.thread_name}' completed task {self._tasks_completed}")
                    
                except Exception as e:
                    self._tasks_failed += 1
                    error_msg = f"Task failed: {e}\n{traceback.format_exc()}"
                    self._errors.append(error_msg)
                    logger.error(f"Thread '{self.thread_name}' task error: {e}")
                
                self._task_queue.task_done()
            
        except Exception as e:
            self._status = ThreadStatus.ERROR
            logger.error(f"Thread '{self.thread_name}' error: {e}")
        
        finally:
            self._stopped_at = time.time()
            self._status = ThreadStatus.STOPPED
            logger.info(f"Thread '{self.thread_name}' stopped")
    
    def submit(self, task: Callable, *args, **kwargs):
        """
        Soumet une tâche au thread
        
        Args:
            task: Tâche à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
        """
        if self._status in [ThreadStatus.STOPPING, ThreadStatus.STOPPED]:
            raise RuntimeError(f"Thread '{self.thread_name}' is {self._status.value}")
        
        def wrapper():
            task(*args, **kwargs)
        
        self._task_queue.put(wrapper)
    
    def pause(self):
        """Met en pause le thread"""
        self._pause_event.set()
        self._status = ThreadStatus.PAUSED
        logger.debug(f"Thread '{self.thread_name}' paused")
    
    def resume(self):
        """Reprend le thread"""
        self._pause_event.clear()
        self._status = ThreadStatus.RUNNING
        logger.debug(f"Thread '{self.thread_name}' resumed")
    
    def stop(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Arrête le thread
        
        Args:
            wait: Attendre la fin
            timeout: Timeout
        """
        self._status = ThreadStatus.STOPPING
        self._stop_event.set()
        
        if wait:
            self.join(timeout)
    
    def get_status(self) -> ThreadStatus:
        """Récupère le statut du thread"""
        return self._status
    
    def get_info(self) -> ThreadInfo:
        """Récupère les informations du thread"""
        with self._lock:
            return ThreadInfo(
                id=self.thread_id,
                name=self.thread_name,
                thread=self,
                status=self._status,
                created_at=self._created_at,
                started_at=self._started_at,
                stopped_at=self._stopped_at,
                last_activity=self._last_activity,
                tasks_completed=self._tasks_completed,
                tasks_failed=self._tasks_failed,
                errors=self._errors.copy()
            )
    
    def is_alive(self) -> bool:
        """Vérifie si le thread est vivant"""
        return self._status not in [ThreadStatus.STOPPED, ThreadStatus.ERROR]

# ============================================================
# THREAD POOL
# ============================================================

class ThreadPool:
    """
    Pool de threads
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        min_workers: int = 0,
        name: Optional[str] = None,
        daemon: bool = True,
        priority: ThreadPriority = ThreadPriority.NORMAL,
        max_tasks_per_thread: Optional[int] = None,
        idle_timeout: Optional[float] = None,
        max_errors_per_thread: Optional[int] = None,
        queue_size: int = 0,
        expand_timeout: float = 0.5,
        shrink_timeout: float = 5.0
    ):
        """
        Initialise le pool de threads
        
        Args:
            max_workers: Nombre maximum de workers
            min_workers: Nombre minimum de workers
            name: Nom du pool
            daemon: Threads daemon
            priority: Priorité par défaut
            max_tasks_per_thread: Tâches max par thread
            idle_timeout: Timeout d'inactivité
            max_errors_per_thread: Erreurs max par thread
            queue_size: Taille de la file d'attente
            expand_timeout: Timeout d'expansion
            shrink_timeout: Timeout de réduction
        """
        self.name = name or str(uuid.uuid4())[:8]
        self.max_workers = max_workers
        self.min_workers = min_workers
        self.daemon = daemon
        self.priority = priority
        self.max_tasks_per_thread = max_tasks_per_thread
        self.idle_timeout = idle_timeout
        self.max_errors_per_thread = max_errors_per_thread
        self.expand_timeout = expand_timeout
        self.shrink_timeout = shrink_timeout
        
        self._task_queue = queue.Queue(maxsize=queue_size) if queue_size > 0 else queue.Queue()
        self._threads: Dict[str, BaseThread] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._manager_thread = None
        self._stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
            'active_workers': 0,
            'idle_workers': 0,
            'queue_size': 0,
        }
        
        self._start_manager()
        self._init_workers()
        
        logger.info(f"ThreadPool '{self.name}' initialized (max={max_workers}, min={min_workers})")
    
    def _start_manager(self):
        """Démarre le thread manager"""
        def manager_loop():
            while not self._stop_event.is_set():
                try:
                    self._manage_workers()
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Manager error: {e}")
        
        self._manager_thread = threading.Thread(target=manager_loop, daemon=True)
        self._manager_thread.start()
    
    def _init_workers(self):
        """Initialise les workers"""
        for _ in range(self.min_workers):
            self._create_worker()
    
    def _manage_workers(self):
        """Gère les workers"""
        with self._lock:
            active_count = len([t for t in self._threads.values() if t.is_alive()])
            idle_count = len([t for t in self._threads.values() if t.get_status() == ThreadStatus.IDLE])
            queue_size = self._task_queue.qsize()
            
            # Mettre à jour les statistiques
            self._stats['active_workers'] = active_count
            self._stats['idle_workers'] = idle_count
            self._stats['queue_size'] = queue_size
            
            # Ajouter des workers si nécessaire
            if queue_size > 0 and idle_count == 0 and active_count < self.max_workers:
                self._create_worker()
            
            # Supprimer des workers si nécessaire
            if idle_count > 1 and active_count > self.min_workers:
                for thread_id, thread in list(self._threads.items()):
                    if thread.get_status() == ThreadStatus.IDLE:
                        if active_count > self.min_workers:
                            thread.stop(wait=True, timeout=1)
                            del self._threads[thread_id]
                            active_count -= 1
                            break
    
    def _create_worker(self) -> BaseThread:
        """Crée un worker"""
        worker = BaseThread(
            name=f"{self.name}-worker-{len(self._threads) + 1}",
            daemon=self.daemon,
            priority=self.priority,
            max_tasks=self.max_tasks_per_thread,
            idle_timeout=self.idle_timeout,
            max_errors=self.max_errors_per_thread
        )
        
        with self._lock:
            self._threads[worker.thread_id] = worker
        
        worker.start()
        logger.debug(f"Worker {worker.thread_name} created")
        return worker
    
    def submit(self, task: Callable, *args, **kwargs) -> Future:
        """
        Soumet une tâche au pool
        
        Args:
            task: Tâche à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
            
        Returns:
            Future: Future de la tâche
        """
        if self._stop_event.is_set():
            raise RuntimeError(f"ThreadPool '{self.name}' is stopped")
        
        future = Future()
        
        def wrapper():
            try:
                result = task(*args, **kwargs)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
        
        self._task_queue.put(wrapper)
        self._stats['submitted'] += 1
        return future
    
    def submit_batch(self, tasks: List[Callable]) -> List[Future]:
        """
        Soumet un lot de tâches
        
        Args:
            tasks: Liste des tâches
            
        Returns:
            List[Future]: Futures des tâches
        """
        futures = []
        for task in tasks:
            futures.append(self.submit(task))
        return futures
    
    def wait_completion(self, timeout: Optional[float] = None):
        """
        Attend la fin de toutes les tâches
        
        Args:
            timeout: Timeout
        """
        self._task_queue.join()
    
    def stop(self, wait: bool = True, timeout: Optional[float] = None):
        """
        Arrête le pool
        
        Args:
            wait: Attendre la fin
            timeout: Timeout
        """
        self._stop_event.set()
        
        for thread in self._threads.values():
            thread.stop(wait=wait, timeout=timeout)
        
        if wait:
            self._task_queue.join()
        
        logger.info(f"ThreadPool '{self.name}' stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'name': self.name,
                'total_workers': len(self._threads),
                'active_workers': self._stats['active_workers'],
                'idle_workers': self._stats['idle_workers'],
                'queue_size': self._stats['queue_size'],
                'max_workers': self.max_workers,
                'min_workers': self.min_workers,
            }
    
    def get_workers(self) -> List[ThreadInfo]:
        """Récupère les informations des workers"""
        with self._lock:
            return [t.get_info() for t in self._threads.values()]

# ============================================================
# THREAD MANAGER
# ============================================================

class ThreadManager:
    """
    Gestionnaire de threads
    """
    
    def __init__(self):
        self._threads: Dict[str, BaseThread] = {}
        self._pools: Dict[str, ThreadPool] = {}
        self._lock = threading.RLock()
        self._stats = {
            'total_threads': 0,
            'total_pools': 0,
            'active_threads': 0,
            'idle_threads': 0,
        }
        
        logger.info("ThreadManager initialized")
    
    def create_thread(
        self,
        name: Optional[str] = None,
        daemon: bool = True,
        priority: ThreadPriority = ThreadPriority.NORMAL,
        target: Optional[Callable] = None,
        **kwargs
    ) -> BaseThread:
        """
        Crée un thread
        
        Args:
            name: Nom du thread
            daemon: Thread daemon
            priority: Priorité
            target: Fonction cible
            **kwargs: Arguments supplémentaires
            
        Returns:
            BaseThread: Thread créé
        """
        thread = BaseThread(
            name=name,
            daemon=daemon,
            priority=priority,
            target=target,
            **kwargs
        )
        
        with self._lock:
            self._threads[thread.thread_id] = thread
            self._stats['total_threads'] += 1
        
        thread.start()
        logger.info(f"Thread '{thread.thread_name}' created")
        return thread
    
    def create_pool(
        self,
        max_workers: int = 10,
        min_workers: int = 0,
        name: Optional[str] = None,
        **kwargs
    ) -> ThreadPool:
        """
        Crée un pool de threads
        
        Args:
            max_workers: Nombre maximum de workers
            min_workers: Nombre minimum de workers
            name: Nom du pool
            **kwargs: Arguments supplémentaires
            
        Returns:
            ThreadPool: Pool créé
        """
        pool = ThreadPool(
            max_workers=max_workers,
            min_workers=min_workers,
            name=name,
            **kwargs
        )
        
        with self._lock:
            self._pools[pool.name] = pool
            self._stats['total_pools'] += 1
        
        logger.info(f"ThreadPool '{pool.name}' created")
        return pool
    
    def get_thread(self, thread_id: str) -> Optional[BaseThread]:
        """Récupère un thread"""
        with self._lock:
            return self._threads.get(thread_id)
    
    def get_pool(self, pool_name: str) -> Optional[ThreadPool]:
        """Récupère un pool"""
        with self._lock:
            return self._pools.get(pool_name)
    
    def stop_thread(self, thread_id: str, wait: bool = True):
        """Arrête un thread"""
        thread = self.get_thread(thread_id)
        if thread:
            thread.stop(wait=wait)
            with self._lock:
                if thread_id in self._threads:
                    del self._threads[thread_id]
    
    def stop_pool(self, pool_name: str, wait: bool = True):
        """Arrête un pool"""
        pool = self.get_pool(pool_name)
        if pool:
            pool.stop(wait=wait)
            with self._lock:
                if pool_name in self._pools:
                    del self._pools[pool_name]
    
    def stop_all(self, wait: bool = True):
        """Arrête tous les threads et pools"""
        with self._lock:
            for pool in self._pools.values():
                pool.stop(wait=wait)
            for thread in self._threads.values():
                thread.stop(wait=wait)
            
            self._threads.clear()
            self._pools.clear()
            self._stats['total_threads'] = 0
            self._stats['total_pools'] = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'threads': len(self._threads),
                'pools': len(self._pools),
                'pool_stats': {
                    name: pool.get_stats()
                    for name, pool in self._pools.items()
                }
            }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_thread_manager: Optional[ThreadManager] = None

def get_thread_manager() -> ThreadManager:
    """Récupère le gestionnaire de threads (singleton)"""
    global _thread_manager
    if _thread_manager is None:
        _thread_manager = ThreadManager()
    return _thread_manager

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'ThreadStatus',
    'ThreadPriority',
    
    # Data Classes
    'ThreadInfo',
    
    # Classes
    'BaseThread',
    'ThreadPool',
    'ThreadManager',
    
    # Fonctions
    'get_thread_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Threads utilities module initialized")
