"""
NEXUS AI TRADING SYSTEM - HEDGE BOT TIMERS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des temporisateurs pour le Hedge Bot.
Support des timers, chronomètres, horloges, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import functools
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import schedule
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_ADDED, EVENT_JOB_REMOVED

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class TimerType(Enum):
    """Types de temporisateurs."""
    ONESHOT = "oneshot"          # Une seule fois
    INTERVAL = "interval"        # Intervalle régulier
    CRON = "cron"                # Expression CRON
    COUNTDOWN = "countdown"      # Compte à rebours
    STOPWATCH = "stopwatch"      # Chronomètre
    DEADLINE = "deadline"        # Date limite
    RECURRING = "recurring"      # Récurrent


class TimerStatus(Enum):
    """Statuts de temporisateur."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TimerInfo:
    """Informations de temporisateur."""
    timer_id: UUID
    name: str
    timer_type: TimerType
    status: TimerStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    remaining_seconds: float = 0.0
    trigger_time: Optional[datetime] = None
    last_trigger: Optional[datetime] = None
    next_trigger: Optional[datetime] = None
    total_ticks: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "timer_id": str(self.timer_id),
            "name": self.name,
            "timer_type": self.timer_type.value,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "elapsed_seconds": self.elapsed_seconds,
            "remaining_seconds": self.remaining_seconds,
            "trigger_time": self.trigger_time.isoformat() if self.trigger_time else None,
            "last_trigger": self.last_trigger.isoformat() if self.last_trigger else None,
            "next_trigger": self.next_trigger.isoformat() if self.next_trigger else None,
            "total_ticks": self.total_ticks,
            "metadata": self.metadata
        }


@dataclass
class TimerStats:
    """Statistiques de temporisateur."""
    timer_id: UUID
    total_executions: int
    successful_executions: int
    failed_executions: int
    total_duration: float
    average_duration: float
    max_duration: float
    min_duration: float
    last_execution: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "timer_id": str(self.timer_id),
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_duration": self.total_duration,
            "average_duration": self.average_duration,
            "max_duration": self.max_duration,
            "min_duration": self.min_duration,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE TIMER MANAGER
# ============================================================================

class TimerManager:
    """
    Gestionnaire de temporisateurs avancé.
    """

    def __init__(
        self,
        default_timezone: str = "UTC",
        max_workers: int = 10,
        catch_exceptions: bool = True
    ):
        """
        Initialise le gestionnaire de temporisateurs.

        Args:
            default_timezone: Fuseau horaire par défaut
            max_workers: Nombre maximum de workers
            catch_exceptions: Capturer les exceptions
        """
        self.default_timezone = default_timezone
        self.max_workers = max_workers
        self.catch_exceptions = catch_exceptions
        
        # Scheduler
        self._scheduler = AsyncIOScheduler(timezone=default_timezone)
        self._scheduler.start()
        
        # Timers
        self._timers: Dict[UUID, TimerInfo] = {}
        self._timer_functions: Dict[UUID, Callable] = {}
        self._timer_stats: Dict[UUID, TimerStats] = {}
        self._timer_jobs: Dict[UUID, str] = {}
        
        # Stopwatches
        self._stopwatches: Dict[UUID, Dict] = {}
        
        # Métriques
        self._metrics = {
            "total_timers": 0,
            "active_timers": 0,
            "completed_timers": 0,
            "by_type": {},
            "by_status": {},
            "last_timer": None
        }

        # Event listeners
        self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self._scheduler.add_listener(self._on_job_added, EVENT_JOB_ADDED)
        self._scheduler.add_listener(self._on_job_removed, EVENT_JOB_REMOVED)

        logger.info("TimerManager initialisé avec succès")

    # ========================================================================
    # CRÉATION DE TIMERS
    # ========================================================================

    async def create_timer(
        self,
        name: str,
        timer_type: TimerType,
        interval: Optional[float] = None,
        cron: Optional[str] = None,
        delay: Optional[float] = None,
        deadline: Optional[datetime] = None,
        countdown: Optional[float] = None,
        callback: Optional[Callable] = None,
        args: Tuple = (),
        kwargs: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> UUID:
        """
        Crée un temporisateur.

        Args:
            name: Nom du temporisateur
            timer_type: Type de temporisateur
            interval: Intervalle en secondes
            cron: Expression CRON
            delay: Délai en secondes
            deadline: Date limite
            countdown: Compte à rebours en secondes
            callback: Fonction de callback
            args: Arguments
            kwargs: Arguments nommés
            metadata: Métadonnées

        Returns:
            ID du temporisateur
        """
        timer_id = uuid4()
        kwargs = kwargs or {}

        # Création du trigger
        trigger = None
        if timer_type == TimerType.INTERVAL and interval:
            trigger = IntervalTrigger(seconds=interval, timezone=self.default_timezone)
        elif timer_type == TimerType.CRON and cron:
            trigger = CronTrigger.from_crontab(cron, timezone=self.default_timezone)
        elif timer_type == TimerType.ONESHOT and delay:
            trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=delay))
        elif timer_type == TimerType.DEADLINE and deadline:
            trigger = DateTrigger(run_date=deadline)
        elif timer_type == TimerType.COUNTDOWN and countdown:
            trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=countdown))

        if not trigger:
            raise ValueError(f"Configuration invalide pour le timer {timer_type.value}")

        # Création de l'info
        timer_info = TimerInfo(
            timer_id=timer_id,
            name=name,
            timer_type=timer_type,
            status=TimerStatus.IDLE,
            trigger_time=trigger.run_date if hasattr(trigger, 'run_date') else None,
            metadata=metadata or {}
        )

        # Création du job
        if callback:
            async def wrapper():
                try:
                    await callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Erreur dans le timer {name}: {e}")
                    if not self.catch_exceptions:
                        raise

            job = self._scheduler.add_job(
                wrapper,
                trigger,
                id=str(timer_id),
                name=name,
                replace_existing=True
            )
        else:
            job = self._scheduler.add_job(
                self._timer_tick,
                trigger,
                id=str(timer_id),
                name=name,
                args=(timer_id,),
                replace_existing=True
            )

        self._timer_jobs[timer_id] = job.id
        self._timers[timer_id] = timer_info
        self._timer_functions[timer_id] = callback
        self._timer_stats[timer_id] = TimerStats(
            timer_id=timer_id,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
            total_duration=0.0,
            average_duration=0.0,
            max_duration=0.0,
            min_duration=0.0
        )

        # Mise à jour des métriques
        self._metrics["total_timers"] += 1
        self._metrics["active_timers"] += 1
        
        timer_type_key = timer_type.value
        if timer_type_key not in self._metrics["by_type"]:
            self._metrics["by_type"][timer_type_key] = 0
        self._metrics["by_type"][timer_type_key] += 1

        logger.info(f"Timer {name} créé (ID: {timer_id})")
        return timer_id

    async def _timer_tick(self, timer_id: UUID) -> None:
        """
        Exécute un tick de timer.

        Args:
            timer_id: ID du timer
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return

        timer_info.total_ticks += 1
        timer_info.last_trigger = datetime.now()
        timer_info.status = TimerStatus.RUNNING

        # Mise à jour des statistiques
        stats = self._timer_stats.get(timer_id)
        if stats:
            stats.total_executions += 1
            stats.last_execution = datetime.now()

        logger.debug(f"Tick du timer {timer_info.name} ({timer_info.total_ticks})")

        # Mise à jour du prochain trigger
        next_run = self._scheduler.get_job(str(timer_id))
        if next_run:
            timer_info.next_trigger = next_run.next_run_time

    def _on_job_executed(self, event) -> None:
        """Callback d'exécution de job."""
        timer_id = UUID(event.job_id)
        timer_info = self._timers.get(timer_id)
        if timer_info:
            timer_info.status = TimerStatus.COMPLETED
            
            stats = self._timer_stats.get(timer_id)
            if stats:
                stats.successful_executions += 1

    def _on_job_error(self, event) -> None:
        """Callback d'erreur de job."""
        timer_id = UUID(event.job_id)
        timer_info = self._timers.get(timer_id)
        if timer_info:
            timer_info.status = TimerStatus.ERROR
            
            stats = self._timer_stats.get(timer_id)
            if stats:
                stats.failed_executions += 1

    def _on_job_added(self, event) -> None:
        """Callback d'ajout de job."""
        timer_id = UUID(event.job_id)
        timer_info = self._timers.get(timer_id)
        if timer_info:
            timer_info.status = TimerStatus.RUNNING

    def _on_job_removed(self, event) -> None:
        """Callback de suppression de job."""
        timer_id = UUID(event.job_id)
        timer_info = self._timers.get(timer_id)
        if timer_info:
            timer_info.status = TimerStatus.CANCELLED

    # ========================================================================
    # GESTION DES TIMERS
    # ========================================================================

    async def start_timer(self, timer_id: UUID) -> bool:
        """
        Démarre un timer.

        Args:
            timer_id: ID du timer

        Returns:
            True si démarré
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return False

        job = self._scheduler.get_job(str(timer_id))
        if not job:
            return False

        timer_info.status = TimerStatus.RUNNING
        timer_info.start_time = datetime.now()
        
        job.resume()
        return True

    async def pause_timer(self, timer_id: UUID) -> bool:
        """
        Met un timer en pause.

        Args:
            timer_id: ID du timer

        Returns:
            True si mis en pause
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return False

        job = self._scheduler.get_job(str(timer_id))
        if not job:
            return False

        timer_info.status = TimerStatus.PAUSED
        job.pause()
        return True

    async def resume_timer(self, timer_id: UUID) -> bool:
        """
        Reprend un timer.

        Args:
            timer_id: ID du timer

        Returns:
            True si repris
        """
        return await self.start_timer(timer_id)

    async def cancel_timer(self, timer_id: UUID) -> bool:
        """
        Annule un timer.

        Args:
            timer_id: ID du timer

        Returns:
            True si annulé
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return False

        self._scheduler.remove_job(str(timer_id))
        timer_info.status = TimerStatus.CANCELLED
        timer_info.end_time = datetime.now()

        self._metrics["active_timers"] -= 1
        self._metrics["completed_timers"] += 1

        return True

    async def reset_timer(self, timer_id: UUID) -> bool:
        """
        Réinitialise un timer.

        Args:
            timer_id: ID du timer

        Returns:
            True si réinitialisé
        """
        timer_info = self._timers.get(timer_id)
        if not timer_info:
            return False

        timer_info.status = TimerStatus.IDLE
        timer_info.start_time = None
        timer_info.end_time = None
        timer_info.elapsed_seconds = 0.0
        timer_info.remaining_seconds = 0.0
        timer_info.total_ticks = 0

        return True

    # ========================================================================
    # STOPWATCH
    # ========================================================================

    def start_stopwatch(self, name: str, metadata: Optional[Dict] = None) -> UUID:
        """
        Démarre un chronomètre.

        Args:
            name: Nom du chronomètre
            metadata: Métadonnées

        Returns:
            ID du chronomètre
        """
        stopwatch_id = uuid4()
        self._stopwatches[stopwatch_id] = {
            "name": name,
            "start_time": time.time(),
            "last_lap": time.time(),
            "laps": [],
            "running": True,
            "metadata": metadata or {}
        }
        return stopwatch_id

    def stop_stopwatch(self, stopwatch_id: UUID) -> Optional[float]:
        """
        Arrête un chronomètre.

        Args:
            stopwatch_id: ID du chronomètre

        Returns:
            Temps total
        """
        stopwatch = self._stopwatches.get(stopwatch_id)
        if not stopwatch:
            return None

        stopwatch["running"] = False
        total_time = time.time() - stopwatch["start_time"]
        return total_time

    def lap_stopwatch(self, stopwatch_id: UUID) -> Optional[float]:
        """
        Enregistre un tour de chronomètre.

        Args:
            stopwatch_id: ID du chronomètre

        Returns:
            Temps du tour
        """
        stopwatch = self._stopwatches.get(stopwatch_id)
        if not stopwatch:
            return None

        now = time.time()
        lap_time = now - stopwatch["last_lap"]
        stopwatch["laps"].append(lap_time)
        stopwatch["last_lap"] = now
        return lap_time

    def get_stopwatch_time(self, stopwatch_id: UUID) -> Optional[float]:
        """
        Récupère le temps d'un chronomètre.

        Args:
            stopwatch_id: ID du chronomètre

        Returns:
            Temps écoulé
        """
        stopwatch = self._stopwatches.get(stopwatch_id)
        if not stopwatch:
            return None

        if stopwatch["running"]:
            return time.time() - stopwatch["start_time"]
        return stopwatch.get("total_time", 0.0)

    def get_stopwatch_laps(self, stopwatch_id: UUID) -> Optional[List[float]]:
        """
        Récupère les tours d'un chronomètre.

        Args:
            stopwatch_id: ID du chronomètre

        Returns:
            Liste des temps des tours
        """
        stopwatch = self._stopwatches.get(stopwatch_id)
        if not stopwatch:
            return None
        return stopwatch["laps"]

    # ========================================================================
    # UTILITAIRES
    # ========================================================================

    async def sleep(self, seconds: float, check_interval: float = 0.1) -> None:
        """
        Dormit avec vérification d'arrêt.

        Args:
            seconds: Durée en secondes
            check_interval: Intervalle de vérification
        """
        elapsed = 0.0
        while elapsed < seconds:
            await asyncio.sleep(min(check_interval, seconds - elapsed))
            elapsed += check_interval

    def schedule_once(
        self,
        callback: Callable,
        delay: float,
        *args,
        **kwargs
    ) -> UUID:
        """
        Planifie une exécution unique.

        Args:
            callback: Fonction à exécuter
            delay: Délai en secondes
            *args: Arguments
            **kwargs: Arguments nommés

        Returns:
            ID du timer
        """
        loop = asyncio.get_event_loop()
        
        async def wrapper():
            await asyncio.sleep(delay)
            if asyncio.iscoroutinefunction(callback):
                await callback(*args, **kwargs)
            else:
                loop.run_in_executor(None, callback, *args, **kwargs)

        timer_id = uuid4()
        asyncio.create_task(wrapper())
        return timer_id

    def schedule_interval(
        self,
        callback: Callable,
        interval: float,
        *args,
        **kwargs
    ) -> UUID:
        """
        Planifie une exécution récurrente.

        Args:
            callback: Fonction à exécuter
            interval: Intervalle en secondes
            *args: Arguments
            **kwargs: Arguments nommés

        Returns:
            ID du timer
        """
        loop = asyncio.get_event_loop()
        
        async def wrapper():
            while True:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        loop.run_in_executor(None, callback, *args, **kwargs)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Erreur dans schedule_interval: {e}")
                
                await asyncio.sleep(interval)

        timer_id = uuid4()
        task = asyncio.create_task(wrapper())
        self._timer_functions[timer_id] = task.cancel
        return timer_id

    def cancel_scheduled(self, timer_id: UUID) -> bool:
        """
        Annule une tâche planifiée.

        Args:
            timer_id: ID du timer

        Returns:
            True si annulée
        """
        cancel_func = self._timer_functions.get(timer_id)
        if cancel_func:
            cancel_func()
            del self._timer_functions[timer_id]
            return True
        return False

    # ========================================================================
    # RÉCUPÉRATION
    # ========================================================================

    def get_timer_info(self, timer_id: UUID) -> Optional[TimerInfo]:
        """
        Récupère les informations d'un timer.

        Args:
            timer_id: ID du timer

        Returns:
            Informations du timer
        """
        return self._timers.get(timer_id)

    def get_all_timers(self) -> List[TimerInfo]:
        """
        Récupère tous les timers.

        Returns:
            Liste des timers
        """
        return list(self._timers.values())

    def get_active_timers(self) -> List[TimerInfo]:
        """
        Récupère les timers actifs.

        Returns:
            Liste des timers actifs
        """
        return [t for t in self._timers.values() if t.status == TimerStatus.RUNNING]

    def get_timer_stats(self, timer_id: UUID) -> Optional[TimerStats]:
        """
        Récupère les statistiques d'un timer.

        Args:
            timer_id: ID du timer

        Returns:
            Statistiques du timer
        """
        return self._timer_stats.get(timer_id)

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_timers": self._metrics["total_timers"],
                "active_timers": self._metrics["active_timers"],
                "completed_timers": self._metrics["completed_timers"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_timer": self._metrics["last_timer"],
                "stopwatches": len(self._stopwatches),
                "scheduler_jobs": len(self._scheduler.get_jobs()),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de TimerManager...")
        
        self._scheduler.shutdown(wait=True)
        
        # Annulation des tâches planifiées
        for timer_id in list(self._timer_functions.keys()):
            self.cancel_scheduled(timer_id)
        
        self._timers.clear()
        self._timer_functions.clear()
        self._timer_stats.clear()
        self._timer_jobs.clear()
        self._stopwatches.clear()
        
        logger.info("TimerManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_timer_manager(
    default_timezone: str = "UTC",
    max_workers: int = 10
) -> TimerManager:
    """
    Crée une instance de TimerManager.

    Args:
        default_timezone: Fuseau horaire par défaut
        max_workers: Nombre maximum de workers

    Returns:
        Instance de TimerManager
    """
    return TimerManager(
        default_timezone=default_timezone,
        max_workers=max_workers
    )


def format_duration(seconds: float) -> str:
    """
    Formate une durée.

    Args:
        seconds: Durée en secondes

    Returns:
        Durée formatée
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.2f}h"
    else:
        days = seconds / 86400
        return f"{days:.2f}d"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "TimerType",
    "TimerStatus",
    "TimerInfo",
    "TimerStats",
    "TimerManager",
    "create_timer_manager",
    "format_duration"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire de timers."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT TIMERS")
    print("=" * 60)

    # Création du gestionnaire
    timer_manager = create_timer_manager()

    print(f"\n✅ TimerManager initialisé")

    # Fonction de callback
    async def timer_callback(name: str):
        print(f"   Timer {name} déclenché à {datetime.now().strftime('%H:%M:%S')}")

    # Création d'un timer intervalle
    print(f"\n⏰ Création d'un timer intervalle...")
    timer_id = await timer_manager.create_timer(
        name="IntervalTimer",
        timer_type=TimerType.INTERVAL,
        interval=2.0,
        callback=timer_callback,
        args=("Interval",)
    )
    print(f"   ID: {timer_id}")

    # Démarrer le timer
    await timer_manager.start_timer(timer_id)
    print("   Timer démarré")

    # Attendre quelques ticks
    await asyncio.sleep(5)

    # Pause
    print("\n⏸️ Pause du timer...")
    await timer_manager.pause_timer(timer_id)

    # Reprise
    print("\n▶️ Reprise du timer...")
    await timer_manager.resume_timer(timer_id)

    # Attendre encore
    await asyncio.sleep(3)

    # Annulation
    print("\n❌ Annulation du timer...")
    await timer_manager.cancel_timer(timer_id)

    # Statistiques
    stats = timer_manager.get_timer_stats(timer_id)
    if stats:
        print(f"\n📊 Statistiques:")
        print(f"   Exécutions: {stats.total_executions}")
        print(f"   Succès: {stats.successful_executions}")
        print(f"   Échecs: {stats.failed_executions}")

    # Stopwatch
    print(f"\n⏱️ Démarrage d'un chronomètre...")
    sw_id = timer_manager.start_stopwatch("TestStopwatch")
    
    await asyncio.sleep(2)
    lap1 = timer_manager.lap_stopwatch(sw_id)
    print(f"   Tour 1: {format_duration(lap1)}")
    
    await asyncio.sleep(1)
    lap2 = timer_manager.lap_stopwatch(sw_id)
    print(f"   Tour 2: {format_duration(lap2)}")

    total = timer_manager.stop_stopwatch(sw_id)
    print(f"   Total: {format_duration(total)}")

    # Timer one-shot
    print(f"\n🎯 Création d'un timer one-shot...")
    oneshot_id = await timer_manager.create_timer(
        name="OneShotTimer",
        timer_type=TimerType.ONESHOT,
        delay=1.0,
        callback=timer_callback,
        args=("OneShot",)
    )
    await timer_manager.start_timer(oneshot_id)

    # Santé du service
    health = await timer_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Timers: {health['total_timers']}")
    print(f"   Actifs: {health['active_timers']}")
    print(f"   Chronomètres: {health['stopwatches']}")

    # Fermeture
    await timer_manager.close()

    print("\n" + "=" * 60)
    print("TimerManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
