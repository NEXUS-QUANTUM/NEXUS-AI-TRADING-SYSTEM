"""
NEXUS AI TRADING SYSTEM - Hedge Bot Async Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires asynchrones pour le bot de couverture
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
    Set,
    Awaitable
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


@asynccontextmanager
async def async_timeout_context(seconds: float):
    """
    Context manager pour un timeout asynchrone
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Yields:
        None
    """
    try:
        yield await asyncio.wait_for(asyncio.sleep(0), timeout=seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Timeout after {seconds} seconds")


@asynccontextmanager
async def async_ignore_errors(*exceptions):
    """
    Context manager pour ignorer les erreurs
    
    Args:
        exceptions: Exceptions à ignorer
        
    Yields:
        None
    """
    try:
        yield
    except exceptions:
        pass


@asynccontextmanager
async def async_log_errors(logger_instance=None, message: str = "Error occurred"):
    """
    Context manager pour logger les erreurs
    
    Args:
        logger_instance: Instance de logger
        message: Message de log
        
    Yields:
        None
    """
    try:
        yield
    except Exception as e:
        logger_instance = logger_instance or logger
        logger_instance.error(f"{message}: {e}", exc_info=True)
        raise


@asynccontextmanager
async def async_retry_context(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Context manager pour réessayer avec backoff
    
    Args:
        max_attempts: Nombre maximum de tentatives
        delay: Délai initial
        backoff: Multiplicateur de backoff
        exceptions: Exceptions à capturer
        
    Yields:
        None
    """
    current_delay = delay
    attempt = 0
    
    while True:
        try:
            yield
            break
        except exceptions as e:
            attempt += 1
            if attempt >= max_attempts:
                raise
            
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {e}, retrying in {current_delay}s"
            )
            await sleep(current_delay)
            current_delay *= backoff


# ============================================================
# TASK MANAGEMENT
# ============================================================

@dataclass
class TaskInfo:
    """Informations sur une tâche"""
    id: str
    name: str
    task: asyncio.Task
    status: str
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[Exception] = None


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
        self.tasks: Dict[str, TaskInfo] = {}
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None
        self.lock = asyncio.Lock()
        self.event = asyncio.Event()
        self._task_id_counter = 0
        self._is_running = False
        self._is_stopped = False
        
        # Statistiques
        self.stats = {
            'total_created': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0,
            'active': 0,
            'pending': 0,
        }
    
    def _generate_task_id(self) -> str:
        """Génère un ID de tâche unique"""
        self._task_id_counter += 1
        return f"task_{self._task_id_counter}_{int(time.time())}"
    
    async def create_task(
        self,
        coro: Coroutine,
        name: Optional[str] = None,
        task_id: Optional[str] = None,
        priority: int = 0
    ) -> str:
        """
        Crée une nouvelle tâche
        
        Args:
            coro: Coroutine à exécuter
            name: Nom de la tâche
            task_id: ID de la tâche
            priority: Priorité
            
        Returns:
            str: ID de la tâche
        """
        if self._is_stopped:
            raise RuntimeError("TaskManager is stopped")
        
        task_id = task_id or self._generate_task_id()
        name = name or f"Task-{task_id}"
        
        async with self.lock:
            if task_id in self.tasks:
                raise ValueError(f"Task {task_id} already exists")
            
            task_info = TaskInfo(
                id=task_id,
                name=name,
                task=None,
                status='pending',
                created_at=time.time()
            )
            self.tasks[task_id] = task_info
            self.stats['total_created'] += 1
            self.stats['pending'] += 1
        
        # Créer la tâche
        task = asyncio.create_task(self._run_task(coro, task_id))
        task_info.task = task
        self.tasks[task_id] = task_info
        
        return task_id
    
    async def _run_task(self, coro: Coroutine, task_id: str):
        """
        Exécute une tâche
        
        Args:
            coro: Coroutine à exécuter
            task_id: ID de la tâche
        """
        if self.semaphore:
            await self.semaphore.acquire()
        
        try:
            task_info = self.tasks.get(task_id)
            if task_info:
                task_info.status = 'running'
                task_info.started_at = time.time()
                self.stats['active'] += 1
                self.stats['pending'] -= 1
            
            result = await coro
            
            if task_info:
                task_info.status = 'completed'
                task_info.completed_at = time.time()
                task_info.result = result
                self.stats['total_completed'] += 1
                self.stats['active'] -= 1
            
            logger.debug(f"Task {task_id} completed successfully")
            
        except asyncio.CancelledError:
            if task_info:
                task_info.status = 'cancelled'
                task_info.completed_at = time.time()
                self.stats['total_cancelled'] += 1
                self.stats['active'] -= 1
            logger.debug(f"Task {task_id} cancelled")
            raise
            
        except Exception as e:
            if task_info:
                task_info.status = 'failed'
                task_info.completed_at = time.time()
                task_info.error = e
                self.stats['total_failed'] += 1
                self.stats['active'] -= 1
            logger.error(f"Task {task_id} failed: {e}")
            raise
            
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
        """
        async with self.lock:
            if task_id not in self.tasks:
                raise KeyError(f"Task {task_id} not found")
            
            task_info = self.tasks[task_id]
            task = task_info.task
        
        try:
            if timeout is not None:
                result = await asyncio.wait_for(task, timeout=timeout)
            else:
                result = await task
            
            return result
            
        except asyncio.TimeoutError:
            raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
    
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
            for task_info in self.tasks.values():
                if task_info.task and not task_info.task.done():
                    tasks.append(task_info.task)
        
        if timeout is not None:
            await asyncio.wait(tasks, timeout=timeout)
        else:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        results = {}
        async with self.lock:
            for task_id, task_info in self.tasks.items():
                if task_info.task and task_info.task.done():
                    try:
                        results[task_id] = task_info.task.result()
                    except Exception as e:
                        results[task_id] = e
        
        return results
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Annule une tâche
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            bool: True si annulée
        """
        async with self.lock:
            if task_id not in self.tasks:
                return False
            
            task_info = self.tasks[task_id]
            if not task_info.task or task_info.task.done():
                return False
            
            task_info.task.cancel()
            task_info.status = 'cancelling'
            return True
    
    async def cancel_all(self) -> List[str]:
        """
        Annule toutes les tâches
        
        Returns:
            List[str]: IDs des tâches annulées
        """
        cancelled = []
        async with self.lock:
            for task_id, task_info in self.tasks.items():
                if task_info.task and not task_info.task.done():
                    task_info.task.cancel()
                    task_info.status = 'cancelling'
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
        task_info = self.tasks.get(task_id)
        return task_info.status if task_info else None
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'une tâche
        
        Args:
            task_id: ID de la tâche
            
        Returns:
            Optional[Dict[str, Any]]: Informations de la tâche
        """
        task_info = self.tasks.get(task_id)
        if not task_info:
            return None
        
        return {
            'id': task_info.id,
            'name': task_info.name,
            'status': task_info.status,
            'created_at': task_info.created_at,
            'started_at': task_info.started_at,
            'completed_at': task_info.completed_at,
            'duration': (task_info.completed_at or time.time()) - task_info.created_at,
            'result': task_info.result,
            'error': str(task_info.error) if task_info.error else None
        }
    
    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Récupère toutes les tâches
        
        Returns:
            List[Dict[str, Any]]: Informations des tâches
        """
        return [self.get_task_info(task_id) for task_id in self.tasks]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        active = 0
        pending = 0
        completed = 0
        failed = 0
        cancelled = 0
        
        for task_info in self.tasks.values():
            if task_info.status == 'running':
                active += 1
            elif task_info.status == 'pending':
                pending += 1
            elif task_info.status == 'completed':
                completed += 1
            elif task_info.status == 'failed':
                failed += 1
            elif task_info.status == 'cancelled':
                cancelled += 1
        
        return {
            'total_created': self.stats['total_created'],
            'total_completed': self.stats['total_completed'],
            'total_failed': self.stats['total_failed'],
            'total_cancelled': self.stats['total_cancelled'],
            'active': active,
            'pending': pending,
            'completed': completed,
            'failed': failed,
            'cancelled': cancelled,
            'success_rate': self.stats['total_completed'] / self.stats['total_created'] if self.stats['total_created'] > 0 else 0,
        }
    
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
        
        logger.info("TaskManager stopped")


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
        self._consumers = 0
        self._items_processed = 0
    
    @property
    def qsize(self) -> int:
        """Taille de la file"""
        if self._use_priority:
            return self._priority_queue.qsize()
        return self._queue.qsize()
    
    @property
    def empty(self) -> bool:
        """Vérifie si la file est vide"""
        return self.qsize == 0
    
    @property
    def full(self) -> bool:
        """Vérifie si la file est pleine"""
        if self._use_priority:
            return self._priority_queue.full()
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
        Ajoute un élément sans attendre
        
        Args:
            item: Élément à ajouter
            priority: Priorité
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
            
            self._items_processed += 1
            return item_with_priority[1]
        else:
            if timeout is not None:
                item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
            else:
                item = await self._queue.get()
            
            self._items_processed += 1
            return item
    
    def get_nowait(self) -> T:
        """
        Récupère un élément sans attendre
        
        Returns:
            T: Élément récupéré
        """
        if self._use_priority:
            item_with_priority = self._priority_queue.get_nowait()
            self._items_processed += 1
            return item_with_priority[1]
        else:
            item = self._queue.get_nowait()
            self._items_processed += 1
            return item
    
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
        if self._use_priority:
            while not self._priority_queue.empty():
                try:
                    self._priority_queue.get_nowait()
                    self._priority_queue.task_done()
                except:
                    break
        else:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except:
                    break
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'size': self.qsize,
            'maxsize': self._queue.maxsize,
            'closed': self._closed,
            'use_priority': self._use_priority,
            'items_processed': self._items_processed,
            'consumers': self._consumers,
        }


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
        self._total_tasks = 0
        self._completed_tasks = 0
    
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
        self._total_tasks += 1
    
    async def submit_coro(self, coro: Coroutine):
        """
        Soumet une coroutine au pool
        
        Args:
            coro: Coroutine à exécuter
        """
        if not self._is_running:
            raise RuntimeError("Pool is not running")
        
        await self._task_queue.put(('coro', coro))
        self._total_tasks += 1
    
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
                    item = await asyncio.wait_for(
                        self._task_queue.get(),
                        timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue
                except:
                    break
                
                # Exécuter la tâche
                try:
                    if item[0] == 'coro':
                        result = await item[1]
                    else:
                        func, args, kwargs = item
                        result = func(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                    
                    self._results.append(result)
                    self._completed_tasks += 1
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
            "total_tasks": self._total_tasks,
            "completed_tasks": self._completed_tasks,
            "results_count": len(self._results),
            "errors_count": len(self._errors),
            "is_running": self._is_running,
            "success_rate": self._completed_tasks / self._total_tasks if self._total_tasks > 0 else 0,
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
    
    def run_coroutine(self, coro: Coroutine) -> Any:
        """
        Exécute une coroutine dans le bon contexte
        
        Args:
            coro: Coroutine à exécuter
            
        Returns:
            Any: Résultat de la coroutine
        """
        return self.run(coro)
    
    def run_coroutine_sync(self, coro: Coroutine) -> Any:
        """
        Exécute une coroutine de manière synchrone
        
        Args:
            coro: Coroutine à exécuter
            
        Returns:
            Any: Résultat de la coroutine
        """
        return self.run(coro)


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
    'async_timeout_context',
    'async_ignore_errors',
    'async_log_errors',
    'async_retry_context',
    
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
