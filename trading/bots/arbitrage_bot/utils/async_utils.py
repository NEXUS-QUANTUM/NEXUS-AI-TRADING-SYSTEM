"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Async Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires asynchrones pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import functools
import time
import signal
import threading
import concurrent.futures
from typing import (
    Any, 
    Callable, 
    Dict, 
    List, 
    Optional, 
    TypeVar, 
    Union, 
    Coroutine,
    AsyncContextManager,
    Generic,
    Tuple,
    Set
)
from contextlib import asynccontextmanager
from asyncio import (
    get_event_loop,
    new_event_loop,
    set_event_loop,
    sleep,
    gather,
    wait,
    shield,
    timeout,
    create_task,
    ensure_future,
    Queue,
    PriorityQueue,
    Lock,
    Semaphore,
    Event,
    Condition,
    BoundedSemaphore,
)
from dataclasses import dataclass, field
from collections import defaultdict
import logging

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
# ASYNC UTILITIES
# ============================================================

def async_to_sync(func: Callable[..., Coroutine]) -> Callable[..., Any]:
    """
    Convertit une fonction asynchrone en fonction synchrone
    
    Args:
        func: Fonction asynchrone à convertir
        
    Returns:
        Callable: Fonction synchrone
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            return asyncio.create_task(func(*args, **kwargs))
        else:
            return loop.run_until_complete(func(*args, **kwargs))
    
    return wrapper


def sync_to_async(func: Callable[..., Any]) -> Callable[..., Coroutine]:
    """
    Convertit une fonction synchrone en fonction asynchrone
    
    Args:
        func: Fonction synchrone à convertir
        
    Returns:
        Callable: Fonction asynchrone
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
    
    return wrapper


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Décorateur pour réessayer une fonction asynchrone
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial entre les tentatives
        backoff: Multiplicateur de délai exponentiel
        exceptions: Exceptions à capturer
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    
                    await sleep(current_delay)
                    current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    
    return decorator


def async_timeout(seconds: float) -> Callable:
    """
    Décorateur pour ajouter un timeout à une fonction asynchrone
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Function {func.__name__} timed out after {seconds} seconds"
                )
        
        return wrapper
    
    return decorator


@asynccontextmanager
async def async_lock(lock: asyncio.Lock, timeout: Optional[float] = None):
    """
    Context manager pour un verrou asynchrone avec timeout
    
    Args:
        lock: Verrou asynchrone
        timeout: Timeout optionnel
        
    Yields:
        None: Le verrou est acquis
    """
    if timeout is not None:
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Could not acquire lock within {timeout} seconds")
    else:
        await lock.acquire()
    
    try:
        yield
    finally:
        lock.release()


@asynccontextmanager
async def async_semaphore(semaphore: asyncio.Semaphore):
    """
    Context manager pour un sémaphore asynchrone
    
    Args:
        semaphore: Sémaphore asynchrone
        
    Yields:
        None: Le sémaphore est acquis
    """
    await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release()


# ============================================================
# TASK MANAGEMENT
# ============================================================

class TaskManager:
    """
    Gestionnaire de tâches asynchrones
    
    Permet de créer, exécuter et surveiller des tâches asynchrones
    """
    
    def __init__(self, max_concurrent: Optional[int] = None):
        """
        Initialise le gestionnaire de tâches
        
        Args:
            max_concurrent: Nombre maximum de tâches concurrentes
        """
        self.tasks: Dict[str, asyncio.Task] = {}
        self.results: Dict[str, Any] = {}
        self.errors: Dict[str, Exception] = {}
        self.status: Dict[str, str] = {}
        
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None
        
        self.lock = asyncio.Lock()
        self.event = asyncio.Event()
        
        self._is_running = False
        self._is_stopped = False
        
        self._task_id_counter = 0
    
    def _generate_task_id(self) -> str:
        """Génère un ID de tâche unique"""
        self._task_id_counter += 1
        return f"task_{self._task_id_counter}_{int(time.time())}"
    
    async def add_task(
        self,
        coro: Coroutine,
        task_id: Optional[str] = None,
        name: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """
        Ajoute une tâche
        
        Args:
            coro: Coroutine à exécuter
            task_id: ID de la tâche (auto-généré si non fourni)
            name: Nom de la tâche
            priority: Priorité (0 = plus haute)
            
        Returns:
            str: ID de la tâche
        """
        if self._is_stopped:
            raise RuntimeError("TaskManager is stopped")
        
        if task_id is None:
            task_id = self._generate_task_id()
        
        async with self.lock:
            if task_id in self.tasks:
                raise ValueError(f"Task {task_id} already exists")
            
            self.status[task_id] = "pending"
            self.tasks[task_id] = None  # Placeholder
        
        # Créer la tâche
        task = asyncio.create_task(self._run_task(coro, task_id, name))
        
        async with self.lock:
            self.tasks[task_id] = task
        
        return task_id
    
    async def _run_task(self, coro: Coroutine, task_id: str, name: Optional[str] = None):
        """
        Exécute une tâche
        
        Args:
            coro: Coroutine à exécuter
            task_id: ID de la tâche
            name: Nom de la tâche
        """
        # Acquérir le sémaphore si nécessaire
        if self.semaphore:
            await self.semaphore.acquire()
        
        try:
            self.status[task_id] = "running"
            
            try:
                result = await coro
                self.results[task_id] = result
                self.status[task_id] = "completed"
                logger.debug(f"Task {task_id} completed successfully")
            except Exception as e:
                self.errors[task_id] = e
                self.status[task_id] = "failed"
                logger.error(f"Task {task_id} failed: {e}")
        
        finally:
            if self.semaphore:
                self.semaphore.release()
            
            self.event.set()
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Attend la fin d'une tâche
        
        Args:
            task_id: ID de la tâche
            timeout: Timeout en secondes
            
        Returns:
            Any: Résultat de la tâche
            
        Raises:
            KeyError: Si la tâche n'existe pas
            TimeoutError: Si le timeout est dépassé
        """
        async with self.lock:
            if task_id not in self.tasks:
                raise KeyError(f"Task {task_id} not found")
            
            task = self.tasks[task_id]
        
        try:
            if timeout is not None:
                result = await asyncio.wait_for(task, timeout=timeout)
            else:
                result = await task
            
            return result
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")
    
    async def wait_for_all(self, timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Attend la fin de toutes les tâches
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            Dict[str, Any]: Résultats par ID de tâche
        """
        tasks = []
        async with self.lock:
            tasks = [task for task in self.tasks.values() if task is not None]
        
        if timeout is not None:
            await asyncio.wait(tasks, timeout=timeout)
        else:
            await asyncio.gather(*tasks)
        
        return self.results.copy()
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Annule une tâche
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            bool: True si la tâche a été annulée, False sinon
        """
        async with self.lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task is None:
                return False
            
            if task.done():
                return False
            
            task.cancel()
            self.status[task_id] = "cancelled"
            return True
    
    async def cancel_all(self) -> List[str]:
        """
        Annule toutes les tâches
        
        Returns:
            List[str]: IDs des tâches annulées
        """
        cancelled = []
        async with self.lock:
            for task_id, task in self.tasks.items():
                if task is not None and not task.done():
                    task.cancel()
                    self.status[task_id] = "cancelled"
                    cancelled.append(task_id)
        
        return cancelled
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        Récupère le statut d'une tâche
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Optional[str]: Statut de la tâche
        """
        return self.status.get(task_id)
    
    def get_all_status(self) -> Dict[str, str]:
        """
        Récupère les statuts de toutes les tâches
        
        Returns:
            Dict[str, str]: Statuts par ID de tâche
        """
        return self.status.copy()
    
    def get_results(self) -> Dict[str, Any]:
        """
        Récupère les résultats des tâches
        
        Returns:
            Dict[str, Any]: Résultats par ID de tâche
        """
        return self.results.copy()
    
    def get_errors(self) -> Dict[str, Exception]:
        """
        Récupère les erreurs des tâches
        
        Returns:
            Dict[str, Exception]: Erreurs par ID de tâche
        """
        return self.errors.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        total = len(self.tasks)
        completed = sum(1 for s in self.status.values() if s == "completed")
        failed = sum(1 for s in self.status.values() if s == "failed")
        pending = sum(1 for s in self.status.values() if s == "pending")
        running = sum(1 for s in self.status.values() if s == "running")
        cancelled = sum(1 for s in self.status.values() if s == "cancelled")
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "cancelled": cancelled,
            "success_rate": completed / total if total > 0 else 0,
        }
    
    def clear(self):
        """Nettoie les résultats et erreurs"""
        self.results.clear()
        self.errors.clear()
    
    async def stop(self, cancel_pending: bool = True):
        """
        Arrête le gestionnaire
        
        Args:
            cancel_pending: Annuler les tâches en attente
        """
        self._is_stopped = True
        
        if cancel_pending:
            await self.cancel_all()
        
        await self.wait_for_all(timeout=5.0)


# ============================================================
# ASYNC QUEUE
# ============================================================

class AsyncQueue(Generic[T]):
    """
    File d'attente asynchrone avec fonctionnalités avancées
    """
    
    def __init__(self, maxsize: int = 0):
        """
        Initialise la file d'attente
        
        Args:
            maxsize: Taille maximale (0 = illimitée)
        """
        self._queue = Queue(maxsize=maxsize)
        self._priority_queue = PriorityQueue(maxsize=maxsize)
        self._use_priority = False
        self._lock = asyncio.Lock()
        self._closed = False
    
    @property
    def qsize(self) -> int:
        """Taille de la file"""
        return self._queue.qsize()
    
    @property
    def empty(self) -> bool:
        """Vérifie si la file est vide"""
        return self._queue.empty()
    
    @property
    def full(self) -> bool:
        """Vérifie si la file est pleine"""
        return self._queue.full()
    
    @property
    def closed(self) -> bool:
        """Vérifie si la file est fermée"""
        return self._closed
    
    def enable_priority(self):
        """Active le mode prioritaire"""
        self._use_priority = True
    
    def disable_priority(self):
        """Désactive le mode prioritaire"""
        self._use_priority = False
    
    async def put(self, item: T, priority: int = 0, timeout: Optional[float] = None):
        """
        Ajoute un élément à la file
        
        Args:
            item: Élément à ajouter
            priority: Priorité (plus petit = plus prioritaire)
            timeout: Timeout en secondes
        """
        if self._closed:
            raise RuntimeError("Queue is closed")
        
        if self._use_priority:
            item_with_priority = (priority, item)
            if timeout is not None:
                await asyncio.wait_for(
                    self._priority_queue.put(item_with_priority),
                    timeout=timeout
                )
            else:
                await self._priority_queue.put(item_with_priority)
        else:
            if timeout is not None:
                await asyncio.wait_for(self._queue.put(item), timeout=timeout)
            else:
                await self._queue.put(item)
    
    def put_nowait(self, item: T, priority: int = 0):
        """
        Ajoute un élément à la file sans attendre
        
        Args:
            item: Élément à ajouter
            priority: Priorité (plus petit = plus prioritaire)
        """
        if self._closed:
            raise RuntimeError("Queue is closed")
        
        if self._use_priority:
            self._priority_queue.put_nowait((priority, item))
        else:
            self._queue.put_nowait(item)
    
    async def get(self, timeout: Optional[float] = None) -> T:
        """
        Récupère un élément de la file
        
        Args:
            timeout: Timeout en secondes
            
        Returns:
            T: Élément récupéré
        """
        if self._use_priority:
            if timeout is not None:
                item_with_priority = await asyncio.wait_for(
                    self._priority_queue.get(),
                    timeout=timeout
                )
            else:
                item_with_priority = await self._priority_queue.get()
            return item_with_priority[1]  # Ignorer la priorité
        else:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                return await self._queue.get()
    
    def get_nowait(self) -> T:
        """
        Récupère un élément de la file sans attendre
        
        Returns:
            T: Élément récupéré
        """
        if self._use_priority:
            item_with_priority = self._priority_queue.get_nowait()
            return item_with_priority[1]  # Ignorer la priorité
        else:
            return self._queue.get_nowait()
    
    def task_done(self):
        """Marque une tâche comme terminée"""
        if self._use_priority:
            self._priority_queue.task_done()
        else:
            self._queue.task_done()
    
    async def join(self):
        """Attend que toutes les tâches soient terminées"""
        if self._use_priority:
            await self._priority_queue.join()
        else:
            await self._queue.join()
    
    def close(self):
        """Ferme la file d'attente"""
        self._closed = True
    
    def clear(self):
        """Vide la file d'attente"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except:
                break


# ============================================================
# ASYNC POOL
# ============================================================

class AsyncPool:
    """
    Pool d'exécution asynchrone
    
    Gère un ensemble de workers pour exécuter des tâches en parallèle
    """
    
    def __init__(self, max_workers: int = 4, name: str = "async_pool"):
        """
        Initialise le pool
        
        Args:
            max_workers: Nombre maximum de workers
            name: Nom du pool
        """
        self.max_workers = max_workers
        self.name = name
        self._workers: Set[asyncio.Task] = set()
        self._task_queue = AsyncQueue()
        self._is_running = False
        self._lock = asyncio.Lock()
        self._results: List[Any] = []
        self._errors: List[Exception] = []
    
    async def start(self):
        """Démarre le pool"""
        async with self._lock:
            if self._is_running:
                return
            
            self._is_running = True
            
            for i in range(self.max_workers):
                worker = asyncio.create_task(self._worker_loop(f"worker_{i}"))
                self._workers.add(worker)
    
    async def stop(self, timeout: float = 5.0):
        """
        Arrête le pool
        
        Args:
            timeout: Timeout pour l'arrêt
        """
        async with self._lock:
            if not self._is_running:
                return
            
            self._is_running = False
        
        # Attendre que les workers se terminent
        if self._workers:
            await asyncio.wait(self._workers, timeout=timeout)
        
        self._task_queue.close()
    
    async def submit(self, func: Callable, *args, **kwargs):
        """
        Soumet une tâche au pool
        
        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
        """
        if not self._is_running:
            raise RuntimeError("Pool is not running")
        
        await self._task_queue.put((func, args, kwargs))
    
    async def _worker_loop(self, worker_name: str):
        """
        Boucle d'un worker
        
        Args:
            worker_name: Nom du worker
        """
        logger.debug(f"Worker {worker_name} started")
        
        while self._is_running:
            try:
                # Récupérer une tâche
                try:
                    func, args, kwargs = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue
                except:
                    break
                
                # Exécuter la tâche
                try:
                    result = func(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    
                    self._results.append(result)
                    logger.debug(f"Worker {worker_name} completed task")
                except Exception as e:
                    self._errors.append(e)
                    logger.error(f"Worker {worker_name} task failed: {e}")
                
                self._task_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
        
        logger.debug(f"Worker {worker_name} stopped")
        self._workers.discard(asyncio.current_task())
    
    def get_results(self) -> List[Any]:
        """
        Récupère les résultats
        
        Returns:
            List[Any]: Résultats
        """
        return self._results.copy()
    
    def get_errors(self) -> List[Exception]:
        """
        Récupère les erreurs
        
        Returns:
            List[Exception]: Erreurs
        """
        return self._errors.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            "max_workers": self.max_workers,
            "active_workers": len(self._workers),
            "queue_size": self._task_queue.qsize,
            "results_count": len(self._results),
            "errors_count": len(self._errors),
            "is_running": self._is_running,
        }


# ============================================================
# EVENT LOOP UTILITIES
# ============================================================

class EventLoopManager:
    """
    Gestionnaire de boucle d'événements
    """
    
    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()
    
    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Récupère la boucle d'événements"""
        if self._loop is None:
            with self._lock:
                if self._loop is None:
                    try:
                        self._loop = asyncio.get_event_loop()
                    except RuntimeError:
                        self._loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(self._loop)
        
        return self._loop
    
    def run(self, coro: Coroutine) -> Any:
        """
        Exécute une coroutine
        
        Args:
            coro: Coroutine à exécuter
            
        Returns:
            Any: Résultat de la coroutine
        """
        loop = self.loop
        
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        else:
            return loop.run_until_complete(coro)
    
    def run_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Exécute une fonction de manière asynchrone
        
        Args:
            func: Fonction à exécuter
            *args: Arguments positionnels
            **kwargs: Arguments nommés
            
        Returns:
            Any: Résultat de la fonction
        """
        loop = self.loop
        
        def wrapper():
            return func(*args, **kwargs)
        
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(
                asyncio.to_thread(wrapper),
                loop
            ).result()
        else:
            return loop.run_in_executor(None, wrapper)
    
    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """
        Crée une tâche
        
        Args:
            coro: Coroutine à exécuter
            
        Returns:
            asyncio.Task: Tâche créée
        """
        return self.loop.create_task(coro)
    
    def ensure_future(self, coro: Coroutine) -> asyncio.Future:
        """
        Assure qu'une coroutine devient une Future
        
        Args:
            coro: Coroutine à convertir
            
        Returns:
            asyncio.Future: Future résultante
        """
        return asyncio.ensure_future(coro, loop=self.loop)

# ============================================================
# SINGLETON INSTANCES
# ============================================================

_loop_manager: Optional[EventLoopManager] = None

def get_event_loop_manager() -> EventLoopManager:
    """Récupère le gestionnaire de boucle d'événements"""
    global _loop_manager
    if _loop_manager is None:
        _loop_manager = EventLoopManager()
    return _loop_manager


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Décorateurs
    'async_to_sync',
    'sync_to_async',
    'async_retry',
    'async_timeout',
    
    # Context managers
    'async_lock',
    'async_semaphore',
    
    # Classes
    'TaskManager',
    'AsyncQueue',
    'AsyncPool',
    'EventLoopManager',
    
    # Fonctions
    'get_event_loop_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Async utilities module initialized")
