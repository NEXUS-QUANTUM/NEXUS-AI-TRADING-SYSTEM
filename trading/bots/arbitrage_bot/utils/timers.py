"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Timers Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires de temporisation pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import time
import threading
import logging
import uuid
import heapq
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
import weakref
import functools
import signal

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

class TimerType(Enum):
    """Types de temporisateurs"""
    ONESHOT = "oneshot"  # Une seule fois
    PERIODIC = "periodic"  # Périodique
    DELAYED = "delayed"  # Avec délai
    COUNTDOWN = "countdown"  # Compte à rebours
    STOPWATCH = "stopwatch"  # Chronomètre
    SCHEDULED = "scheduled"  # Planifié

class TimerStatus(Enum):
    """Statuts de temporisateur"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class TimerInfo:
    """Informations sur un temporisateur"""
    id: str
    name: str
    type: TimerType
    status: TimerStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    duration: float = 0.0
    remaining: float = 0.0
    elapsed: float = 0.0
    interval: float = 0.0
    count: int = 0
    max_count: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

# ============================================================
# BASE TIMER
# ============================================================

class BaseTimer:
    """
    Temporisateur de base
    
    Gère les temporisations avec différentes stratégies
    """
    
    def __init__(
        self,
        name: Optional[str] = None,
        timer_type: TimerType = TimerType.ONESHOT,
        duration: float = 1.0,
        interval: float = 1.0,
        max_count: Optional[int] = None,
        callback: Optional[Callable] = None,
        args: tuple = (),
        kwargs: dict = None,
        auto_start: bool = False
    ):
        """
        Initialise le temporisateur
        
        Args:
            name: Nom du temporisateur
            timer_type: Type de temporisateur
            duration: Durée en secondes
            interval: Intervalle en secondes
            max_count: Nombre maximum de répétitions
            callback: Fonction de callback
            args: Arguments positionnels
            kwargs: Arguments nommés
            auto_start: Démarrer automatiquement
        """
        self.id = str(uuid.uuid4())[:8]
        self.name = name or f"Timer-{self.id}"
        self.type = timer_type
        self.duration = duration
        self.interval = interval
        self.max_count = max_count
        self.callback = callback
        self.args = args
        self.kwargs = kwargs or {}
        
        self._status = TimerStatus.IDLE
        self._created_at = time.time()
        self._started_at = None
        self._completed_at = None
        self._cancelled_at = None
        self._elapsed = 0.0
        self._remaining = duration
        self._count = 0
        self._running = False
        self._paused = False
        self._lock = threading.RLock()
        self._timer_thread = None
        self._stop_event = threading.Event()
        
        if auto_start:
            self.start()
        
        logger.debug(f"Timer '{self.name}' initialized")
    
    def start(self):
        """Démarre le temporisateur"""
        with self._lock:
            if self._status == TimerStatus.RUNNING:
                return
            
            self._status = TimerStatus.RUNNING
            self._started_at = time.time()
            self._running = True
            self._stop_event.clear()
            
            self._timer_thread = threading.Thread(
                target=self._run,
                daemon=True,
                name=f"{self.name}-thread"
            )
            self._timer_thread.start()
            
            logger.debug(f"Timer '{self.name}' started")
    
    def _run(self):
        """Boucle principale du temporisateur"""
        try:
            if self.type == TimerType.ONESHOT:
                self._run_oneshot()
            elif self.type == TimerType.PERIODIC:
                self._run_periodic()
            elif self.type == TimerType.COUNTDOWN:
                self._run_countdown()
            elif self.type == TimerType.DELAYED:
                self._run_delayed()
            else:
                self._run_oneshot()
                
        except Exception as e:
            self._status = TimerStatus.ERROR
            logger.error(f"Timer '{self.name}' error: {e}")
    
    def _run_oneshot(self):
        """Exécution unique"""
        if self._wait(self.duration):
            self._execute_callback()
            self._complete()
    
    def _run_periodic(self):
        """Exécution périodique"""
        count = 0
        while not self._stop_event.is_set():
            if self._wait(self.interval):
                if self._execute_callback():
                    count += 1
                    self._count = count
                    
                    if self.max_count and count >= self.max_count:
                        break
            else:
                break
        
        self._complete()
    
    def _run_countdown(self):
        """Compte à rebours"""
        remaining = self.duration
        while remaining > 0 and not self._stop_event.is_set():
            if self._wait(min(1.0, remaining)):
                remaining -= 1.0
                self._remaining = remaining
                self._elapsed = self.duration - remaining
                
                if self.callback:
                    self._execute_callback()
            else:
                break
        
        self._complete()
    
    def _run_delayed(self):
        """Exécution avec délai"""
        if self._wait(self.duration):
            self._execute_callback()
            self._complete()
    
    def _wait(self, seconds: float) -> bool:
        """
        Attend un certain temps
        
        Args:
            seconds: Temps à attendre
            
        Returns:
            bool: True si le temps est écoulé
        """
        start = time.time()
        while time.time() - start < seconds:
            if self._stop_event.wait(0.1):
                return False
            if self._paused:
                self._stop_event.wait(0.1)
                continue
        return True
    
    def _execute_callback(self) -> bool:
        """
        Exécute le callback
        
        Returns:
            bool: True si l'exécution a réussi
        """
        if not self.callback:
            return True
        
        try:
            if asyncio.iscoroutinefunction(self.callback):
                # Exécution asynchrone
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.callback(*self.args, **self.kwargs)
                )
                loop.close()
            else:
                self.callback(*self.args, **self.kwargs)
            return True
            
        except Exception as e:
            logger.error(f"Timer callback error: {e}")
            return False
    
    def _complete(self):
        """Marque le temporisateur comme terminé"""
        with self._lock:
            self._status = TimerStatus.COMPLETED
            self._completed_at = time.time()
            self._running = False
            self._remaining = 0.0
            self._elapsed = self.duration
        
        logger.debug(f"Timer '{self.name}' completed")
    
    def pause(self):
        """Met en pause le temporisateur"""
        with self._lock:
            if self._status != TimerStatus.RUNNING:
                return
            
            self._status = TimerStatus.PAUSED
            self._paused = True
            
            logger.debug(f"Timer '{self.name}' paused")
    
    def resume(self):
        """Reprend le temporisateur"""
        with self._lock:
            if self._status != TimerStatus.PAUSED:
                return
            
            self._status = TimerStatus.RUNNING
            self._paused = False
            
            logger.debug(f"Timer '{self.name}' resumed")
    
    def cancel(self):
        """Annule le temporisateur"""
        with self._lock:
            if self._status in [TimerStatus.COMPLETED, TimerStatus.CANCELLED]:
                return
            
            self._status = TimerStatus.CANCELLED
            self._cancelled_at = time.time()
            self._running = False
            self._stop_event.set()
            
            logger.debug(f"Timer '{self.name}' cancelled")
    
    def reset(self):
        """Réinitialise le temporisateur"""
        with self._lock:
            self._status = TimerStatus.IDLE
            self._started_at = None
            self._completed_at = None
            self._cancelled_at = None
            self._elapsed = 0.0
            self._remaining = self.duration
            self._count = 0
            self._running = False
            self._paused = False
            self._stop_event.clear()
            
            logger.debug(f"Timer '{self.name}' reset")
    
    def get_status(self) -> TimerStatus:
        """Récupère le statut du temporisateur"""
        return self._status
    
    def get_info(self) -> TimerInfo:
        """Récupère les informations du temporisateur"""
        with self._lock:
            return TimerInfo(
                id=self.id,
                name=self.name,
                type=self.type,
                status=self._status,
                created_at=self._created_at,
                started_at=self._started_at,
                completed_at=self._completed_at,
                cancelled_at=self._cancelled_at,
                duration=self.duration,
                remaining=self._remaining,
                elapsed=self._elapsed,
                interval=self.interval,
                count=self._count,
                max_count=self.max_count
            )
    
    def is_running(self) -> bool:
        """Vérifie si le temporisateur est en cours d'exécution"""
        return self._status == TimerStatus.RUNNING

# ============================================================
# STOPWATCH
# ============================================================

class Stopwatch:
    """
    Chronomètre
    
    Mesure le temps écoulé avec précision
    """
    
    def __init__(self, name: Optional[str] = None, auto_start: bool = True):
        """
        Initialise le chronomètre
        
        Args:
            name: Nom du chronomètre
            auto_start: Démarrer automatiquement
        """
        self.id = str(uuid.uuid4())[:8]
        self.name = name or f"Stopwatch-{self.id}"
        self._start_time = None
        self._stop_time = None
        self._running = False
        self._laps = []
        self._lock = threading.RLock()
        
        if auto_start:
            self.start()
        
        logger.debug(f"Stopwatch '{self.name}' initialized")
    
    def start(self):
        """Démarre le chronomètre"""
        with self._lock:
            if self._running:
                return
            
            self._start_time = time.perf_counter()
            self._running = True
            self._stop_time = None
            
            logger.debug(f"Stopwatch '{self.name}' started")
    
    def stop(self) -> float:
        """
        Arrête le chronomètre
        
        Returns:
            float: Temps écoulé
        """
        with self._lock:
            if not self._running:
                return 0.0
            
            self._stop_time = time.perf_counter()
            self._running = False
            elapsed = self._stop_time - self._start_time
            
            logger.debug(f"Stopwatch '{self.name}' stopped: {elapsed:.3f}s")
            return elapsed
    
    def lap(self) -> float:
        """
        Enregistre un tour
        
        Returns:
            float: Temps du tour
        """
        with self._lock:
            if not self._running:
                return 0.0
            
            now = time.perf_counter()
            last_time = self._laps[-1]['time'] if self._laps else self._start_time
            lap_time = now - last_time
            
            self._laps.append({
                'time': now,
                'lap': len(self._laps) + 1,
                'duration': lap_time,
                'total': now - self._start_time
            })
            
            logger.debug(f"Stopwatch '{self.name}' lap {len(self._laps)}: {lap_time:.3f}s")
            return lap_time
    
    def reset(self):
        """Réinitialise le chronomètre"""
        with self._lock:
            self._start_time = None
            self._stop_time = None
            self._running = False
            self._laps = []
            
            logger.debug(f"Stopwatch '{self.name}' reset")
    
    def elapsed(self) -> float:
        """
        Récupère le temps écoulé
        
        Returns:
            float: Temps écoulé en secondes
        """
        with self._lock:
            if self._running:
                return time.perf_counter() - self._start_time
            elif self._stop_time and self._start_time:
                return self._stop_time - self._start_time
            return 0.0
    
    def get_laps(self) -> List[Dict[str, Any]]:
        """Récupère les tours"""
        with self._lock:
            return self._laps.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                'name': self.name,
                'running': self._running,
                'elapsed': self.elapsed(),
                'laps': len(self._laps),
                'lap_times': [l['duration'] for l in self._laps],
                'avg_lap': sum(l['duration'] for l in self._laps) / len(self._laps) if self._laps else 0,
            }

# ============================================================
# TIMER MANAGER
# ============================================================

class TimerManager:
    """
    Gestionnaire de temporisateurs
    """
    
    def __init__(self):
        self._timers: Dict[str, BaseTimer] = {}
        self._stopwatches: Dict[str, Stopwatch] = {}
        self._lock = threading.RLock()
        self._stats = {
            'total_timers': 0,
            'active_timers': 0,
            'completed_timers': 0,
            'cancelled_timers': 0,
        }
        
        logger.info("TimerManager initialized")
    
    def create_timer(
        self,
        name: Optional[str] = None,
        timer_type: TimerType = TimerType.ONESHOT,
        duration: float = 1.0,
        interval: float = 1.0,
        max_count: Optional[int] = None,
        callback: Optional[Callable] = None,
        auto_start: bool = False,
        **kwargs
    ) -> BaseTimer:
        """
        Crée un temporisateur
        
        Args:
            name: Nom du temporisateur
            timer_type: Type de temporisateur
            duration: Durée en secondes
            interval: Intervalle en secondes
            max_count: Nombre maximum de répétitions
            callback: Fonction de callback
            auto_start: Démarrer automatiquement
            **kwargs: Arguments supplémentaires
            
        Returns:
            BaseTimer: Temporisateur créé
        """
        timer = BaseTimer(
            name=name,
            timer_type=timer_type,
            duration=duration,
            interval=interval,
            max_count=max_count,
            callback=callback,
            auto_start=auto_start,
            **kwargs
        )
        
        with self._lock:
            self._timers[timer.id] = timer
            self._stats['total_timers'] += 1
            
            if timer.is_running():
                self._stats['active_timers'] += 1
        
        logger.info(f"Timer '{timer.name}' created")
        return timer
    
    def create_stopwatch(self, name: Optional[str] = None, auto_start: bool = True) -> Stopwatch:
        """
        Crée un chronomètre
        
        Args:
            name: Nom du chronomètre
            auto_start: Démarrer automatiquement
            
        Returns:
            Stopwatch: Chronomètre créé
        """
        stopwatch = Stopwatch(name=name, auto_start=auto_start)
        
        with self._lock:
            self._stopwatches[stopwatch.id] = stopwatch
        
        logger.info(f"Stopwatch '{stopwatch.name}' created")
        return stopwatch
    
    def get_timer(self, timer_id: str) -> Optional[BaseTimer]:
        """Récupère un temporisateur"""
        with self._lock:
            return self._timers.get(timer_id)
    
    def get_stopwatch(self, stopwatch_id: str) -> Optional[Stopwatch]:
        """Récupère un chronomètre"""
        with self._lock:
            return self._stopwatches.get(stopwatch_id)
    
    def cancel_timer(self, timer_id: str):
        """Annule un temporisateur"""
        timer = self.get_timer(timer_id)
        if timer:
            timer.cancel()
            with self._lock:
                if timer_id in self._timers:
                    del self._timers[timer_id]
                    self._stats['cancelled_timers'] += 1
                    if timer.is_running():
                        self._stats['active_timers'] -= 1
    
    def get_all_timers(self) -> Dict[str, BaseTimer]:
        """Récupère tous les temporisateurs"""
        with self._lock:
            return self._timers.copy()
    
    def get_all_stopwatches(self) -> Dict[str, Stopwatch]:
        """Récupère tous les chronomètres"""
        with self._lock:
            return self._stopwatches.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            active_timers = sum(1 for t in self._timers.values() if t.is_running())
            
            return {
                **self._stats,
                'active_timers': active_timers,
                'timers': len(self._timers),
                'stopwatches': len(self._stopwatches),
                'timer_stats': {
                    timer_id: timer.get_info()
                    for timer_id, timer in self._timers.items()
                }
            }

# ============================================================
# SINGLETON INSTANCE
# ============================================================

_timer_manager: Optional[TimerManager] = None

def get_timer_manager() -> TimerManager:
    """Récupère le gestionnaire de temporisateurs (singleton)"""
    global _timer_manager
    if _timer_manager is None:
        _timer_manager = TimerManager()
    return _timer_manager

# ============================================================
# DECORATORS
# ============================================================

def timeout(seconds: float) -> Callable:
    """
    Décorateur pour ajouter un timeout à une fonction
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
            
            # Sauvegarder le handler existant
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            
            try:
                signal.alarm(int(seconds))
                result = func(*args, **kwargs)
                signal.alarm(0)
                return result
            finally:
                signal.signal(signal.SIGALRM, old_handler)
                signal.alarm(0)
        
        return wrapper
    
    return decorator

def async_timeout(seconds: float) -> Callable:
    """
    Décorateur asynchrone pour ajouter un timeout
    
    Args:
        seconds: Nombre de secondes avant timeout
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, R]]) -> Callable[..., Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> R:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
        
        return wrapper
    
    return decorator

def retry_with_timeout(
    max_attempts: int = 3,
    timeout: float = 30.0,
    delay: float = 1.0,
    backoff: float = 2.0
) -> Callable:
    """
    Décorateur pour réessayer avec timeout
    
    Args:
        max_attempts: Nombre maximum de tentatives
        timeout: Timeout par tentative
        delay: Délai entre les tentatives
        backoff: Multiplicateur de délai
        
    Returns:
        Callable: Décorateur
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            current_delay = delay
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    timer = BaseTimer(
                        duration=timeout,
                        timer_type=TimerType.ONESHOT,
                        auto_start=True
                    )
                    
                    result = func(*args, **kwargs)
                    timer.cancel()
                    return result
                    
                except TimeoutError as e:
                    last_error = e
                    if attempt == max_attempts - 1:
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} timed out: {e}"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            raise last_error
        
        return wrapper
    
    return decorator

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'TimerType',
    'TimerStatus',
    
    # Data Classes
    'TimerInfo',
    
    # Classes
    'BaseTimer',
    'Stopwatch',
    'TimerManager',
    
    # Décorateurs
    'timeout',
    'async_timeout',
    'retry_with_timeout',
    
    # Fonctions
    'get_timer_manager',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Timers utilities module initialized")
