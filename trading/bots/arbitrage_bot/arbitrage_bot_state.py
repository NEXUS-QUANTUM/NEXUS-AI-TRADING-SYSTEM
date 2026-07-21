"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT STATE MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion d'état pour le bot d'arbitrage.
Gestion des états, transitions, persistance, et récupération.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import pickle
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import redis.asyncio as redis

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType,
    ArbitrageStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class BotState(Enum):
    """États du bot."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    RECOVERING = "recovering"


class StateTransition(Enum):
    """Transitions d'état."""
    START = "start"
    STOP = "stop"
    PAUSE = "pause"
    RESUME = "resume"
    SCAN = "scan"
    ANALYZE = "analyze"
    EXECUTE = "execute"
    MONITOR = "monitor"
    ERROR = "error"
    RECOVER = "recover"
    COMPLETE = "complete"


@dataclass
class StateHistory:
    """Historique d'état."""
    state_id: UUID
    bot_id: UUID
    previous_state: BotState
    current_state: BotState
    transition: StateTransition
    timestamp: datetime
    duration_seconds: float
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "state_id": str(self.state_id),
            "bot_id": str(self.bot_id),
            "previous_state": self.previous_state.value,
            "current_state": self.current_state.value,
            "transition": self.transition.value,
            "timestamp": self.timestamp.isoformat(),
            "duration_seconds": self.duration_seconds,
            "reason": self.reason,
            "metadata": self.metadata
        }


@dataclass
class BotSnapshot:
    """Snapshot du bot."""
    snapshot_id: UUID
    bot_id: UUID
    state: BotState
    timestamp: datetime
    config: Dict[str, Any]
    metrics: Dict[str, Any]
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]
    performance: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "snapshot_id": str(self.snapshot_id),
            "bot_id": str(self.bot_id),
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "config": self.config,
            "metrics": self.metrics,
            "positions": self.positions,
            "orders": self.orders,
            "opportunities": self.opportunities,
            "performance": self.performance,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE STATE MANAGER
# ============================================================================

class ArbitrageBotStateManager:
    """
    Gestionnaire d'état pour le bot d'arbitrage.
    """

    # Timeout par défaut pour les états
    STATE_TIMEOUTS = {
        BotState.INITIALIZING: 30,
        BotState.IDLE: 300,
        BotState.SCANNING: 60,
        BotState.ANALYZING: 30,
        BotState.EXECUTING: 120,
        BotState.MONITORING: 300,
        BotState.PAUSED: 3600,
        BotState.STOPPING: 30,
        BotState.RECOVERING: 60
    }

    # Transitions valides
    VALID_TRANSITIONS = {
        BotState.INITIALIZING: [BotState.IDLE, BotState.ERROR],
        BotState.IDLE: [BotState.SCANNING, BotState.PAUSED, BotState.STOPPING],
        BotState.SCANNING: [BotState.ANALYZING, BotState.IDLE, BotState.ERROR],
        BotState.ANALYZING: [BotState.EXECUTING, BotState.IDLE, BotState.ERROR],
        BotState.EXECUTING: [BotState.MONITORING, BotState.IDLE, BotState.ERROR],
        BotState.MONITORING: [BotState.IDLE, BotState.SCANNING, BotState.ERROR],
        BotState.PAUSED: [BotState.IDLE, BotState.STOPPING],
        BotState.STOPPING: [BotState.STOPPED, BotState.ERROR],
        BotState.STOPPED: [BotState.INITIALIZING],
        BotState.ERROR: [BotState.RECOVERING, BotState.STOPPING],
        BotState.RECOVERING: [BotState.IDLE, BotState.ERROR]
    }

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le gestionnaire d'état.

        Args:
            redis_client: Client Redis pour la persistance
            api_keys: Clés API pour les services externes
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # État actuel
        self._states: Dict[UUID, BotState] = {}
        self._previous_states: Dict[UUID, BotState] = {}
        self._state_timers: Dict[UUID, datetime] = {}
        self._state_histories: Dict[UUID, List[StateHistory]] = {}
        self._snapshots: Dict[UUID, List[BotSnapshot]] = {}
        
        # Callbacks
        self._state_change_callbacks: Dict[UUID, List[callable]] = {}
        self._state_timeout_callbacks: Dict[UUID, List[callable]] = {}
        
        # Tâches de monitoring
        self._monitoring_tasks: Dict[UUID, asyncio.Task] = {}
        
        # Métriques
        self._metrics = {
            "total_transitions": 0,
            "current_states": {},
            "state_durations": {},
            "error_count": 0,
            "recovery_count": 0,
            "last_transition": None
        }

        logger.info("ArbitrageBotStateManager initialisé avec succès")

    # ========================================================================
    # GESTION DES ÉTATS
    # ========================================================================

    async def set_state(
        self,
        bot_id: UUID,
        new_state: BotState,
        transition: StateTransition = StateTransition.START,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Définit l'état d'un bot.

        Args:
            bot_id: ID du bot
            new_state: Nouvel état
            transition: Transition
            reason: Raison du changement
            metadata: Métadonnées

        Returns:
            True si l'état a été changé
        """
        try:
            current_state = self._states.get(bot_id, BotState.INITIALIZING)
            
            # Vérification de la transition
            if current_state != new_state:
                if new_state not in self.VALID_TRANSITIONS.get(current_state, []):
                    logger.warning(f"Transition invalide: {current_state} -> {new_state}")
                    return False

            # Sauvegarde de l'état précédent
            previous_state = current_state
            
            # Mise à jour de l'état
            self._states[bot_id] = new_state
            self._previous_states[bot_id] = previous_state
            self._state_timers[bot_id] = datetime.now()

            # Enregistrement de l'historique
            await self._record_state_history(
                bot_id=bot_id,
                previous_state=previous_state,
                current_state=new_state,
                transition=transition,
                reason=reason,
                metadata=metadata
            )

            # Mise à jour des métriques
            self._metrics["total_transitions"] += 1
            self._metrics["last_transition"] = datetime.now().isoformat()
            
            if current_state.value not in self._metrics["current_states"]:
                self._metrics["current_states"][current_state.value] = 0
            self._metrics["current_states"][current_state.value] -= 1
            
            if new_state.value not in self._metrics["current_states"]:
                self._metrics["current_states"][new_state.value] = 0
            self._metrics["current_states"][new_state.value] += 1

            if new_state == BotState.ERROR:
                self._metrics["error_count"] += 1
            elif new_state == BotState.RECOVERING:
                self._metrics["recovery_count"] += 1

            # Persistance
            if self.redis:
                await self._save_state(bot_id)

            # Callbacks
            await self._trigger_callbacks(bot_id, previous_state, new_state)

            # Démarrage du monitoring
            if new_state in self.STATE_TIMEOUTS:
                await self._start_monitoring(bot_id, new_state)

            logger.info(f"État changé: {bot_id} {previous_state} -> {new_state} ({transition.value})")
            return True

        except Exception as e:
            logger.error(f"Erreur lors du changement d'état: {e}")
            return False

    async def get_state(
        self,
        bot_id: UUID
    ) -> BotState:
        """
        Récupère l'état d'un bot.

        Args:
            bot_id: ID du bot

        Returns:
            État du bot
        """
        try:
            # Vérification du cache
            if bot_id in self._states:
                return self._states[bot_id]

            # Chargement depuis Redis
            if self.redis:
                state = await self._load_state(bot_id)
                if state:
                    self._states[bot_id] = state
                    return state

            # État par défaut
            return BotState.INITIALIZING

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'état: {e}")
            return BotState.ERROR

    async def is_state(
        self,
        bot_id: UUID,
        state: BotState
    ) -> bool:
        """
        Vérifie si un bot est dans un état donné.

        Args:
            bot_id: ID du bot
            state: État à vérifier

        Returns:
            True si le bot est dans l'état donné
        """
        current_state = await self.get_state(bot_id)
        return current_state == state

    async def is_active(
        self,
        bot_id: UUID
    ) -> bool:
        """
        Vérifie si un bot est actif.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot est actif
        """
        active_states = [
            BotState.SCANNING,
            BotState.ANALYZING,
            BotState.EXECUTING,
            BotState.MONITORING
        ]
        current_state = await self.get_state(bot_id)
        return current_state in active_states

    # ========================================================================
    # TRANSITIONS D'ÉTAT
    # ========================================================================

    async def start(self, bot_id: UUID) -> bool:
        """
        Démarre un bot.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot a été démarré
        """
        current_state = await self.get_state(bot_id)
        
        if current_state in [BotState.IDLE, BotState.PAUSED, BotState.STOPPED]:
            return await self.set_state(
                bot_id=bot_id,
                new_state=BotState.SCANNING,
                transition=StateTransition.START,
                reason="Bot démarré"
            )
        
        return False

    async def pause(self, bot_id: UUID) -> bool:
        """
        Met en pause un bot.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot a été mis en pause
        """
        current_state = await self.get_state(bot_id)
        
        if current_state in [
            BotState.SCANNING,
            BotState.ANALYZING,
            BotState.EXECUTING,
            BotState.MONITORING
        ]:
            return await self.set_state(
                bot_id=bot_id,
                new_state=BotState.PAUSED,
                transition=StateTransition.PAUSE,
                reason="Bot mis en pause"
            )
        
        return False

    async def resume(self, bot_id: UUID) -> bool:
        """
        Reprend un bot en pause.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot a été repris
        """
        current_state = await self.get_state(bot_id)
        
        if current_state == BotState.PAUSED:
            return await self.set_state(
                bot_id=bot_id,
                new_state=BotState.SCANNING,
                transition=StateTransition.RESUME,
                reason="Bot repris"
            )
        
        return False

    async def stop(self, bot_id: UUID) -> bool:
        """
        Arrête un bot.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot a été arrêté
        """
        current_state = await self.get_state(bot_id)
        
        if current_state != BotState.STOPPED:
            return await self.set_state(
                bot_id=bot_id,
                new_state=BotState.STOPPING,
                transition=StateTransition.STOP,
                reason="Bot arrêté"
            )
        
        return False

    async def error(self, bot_id: UUID, reason: str) -> bool:
        """
        Met un bot en état d'erreur.

        Args:
            bot_id: ID du bot
            reason: Raison de l'erreur

        Returns:
            True si le bot a été mis en erreur
        """
        return await self.set_state(
            bot_id=bot_id,
            new_state=BotState.ERROR,
            transition=StateTransition.ERROR,
            reason=reason
        )

    async def recover(self, bot_id: UUID) -> bool:
        """
        Récupère un bot en erreur.

        Args:
            bot_id: ID du bot

        Returns:
            True si le bot a été récupéré
        """
        current_state = await self.get_state(bot_id)
        
        if current_state == BotState.ERROR:
            return await self.set_state(
                bot_id=bot_id,
                new_state=BotState.RECOVERING,
                transition=StateTransition.RECOVER,
                reason="Récupération en cours"
            )
        
        return False

    # ========================================================================
    # HISTORIQUE ET SNAPSHOTS
    # ========================================================================

    async def _record_state_history(
        self,
        bot_id: UUID,
        previous_state: BotState,
        current_state: BotState,
        transition: StateTransition,
        reason: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Enregistre l'historique d'état.

        Args:
            bot_id: ID du bot
            previous_state: État précédent
            current_state: État actuel
            transition: Transition
            reason: Raison
            metadata: Métadonnées
        """
        try:
            duration = 0.0
            if bot_id in self._state_timers:
                duration = (datetime.now() - self._state_timers[bot_id]).total_seconds()
            
            history = StateHistory(
                state_id=uuid4(),
                bot_id=bot_id,
                previous_state=previous_state,
                current_state=current_state,
                transition=transition,
                timestamp=datetime.now(),
                duration_seconds=duration,
                reason=reason,
                metadata=metadata or {}
            )

            if bot_id not in self._state_histories:
                self._state_histories[bot_id] = []
            
            self._state_histories[bot_id].append(history)

            # Limite à 1000 historiques
            if len(self._state_histories[bot_id]) > 1000:
                self._state_histories[bot_id] = self._state_histories[bot_id][-1000:]

            # Persistance
            if self.redis:
                await self._save_history(bot_id, history)

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de l'historique: {e}")

    async def create_snapshot(
        self,
        bot: ArbitrageBot,
        metadata: Optional[Dict] = None
    ) -> BotSnapshot:
        """
        Crée un snapshot du bot.

        Args:
            bot: Bot
            metadata: Métadonnées

        Returns:
            Snapshot du bot
        """
        try:
            bot_id = bot.config.bot_id
            state = await self.get_state(bot_id)

            snapshot = BotSnapshot(
                snapshot_id=uuid4(),
                bot_id=bot_id,
                state=state,
                timestamp=datetime.now(),
                config=bot.config.__dict__,
                metrics=bot.get_metrics(),
                positions=bot.get_positions(),
                orders=bot.get_orders(),
                opportunities=bot.get_opportunities(),
                performance=bot.get_performance(),
                metadata=metadata or {}
            )

            if bot_id not in self._snapshots:
                self._snapshots[bot_id] = []
            
            self._snapshots[bot_id].append(snapshot)

            # Limite à 100 snapshots
            if len(self._snapshots[bot_id]) > 100:
                self._snapshots[bot_id] = self._snapshots[bot_id][-100:]

            # Persistance
            if self.redis:
                await self._save_snapshot(bot_id, snapshot)

            logger.info(f"Snapshot créé pour {bot_id}")
            return snapshot

        except Exception as e:
            logger.error(f"Erreur lors de la création du snapshot: {e}")
            raise

    async def get_history(
        self,
        bot_id: UUID,
        limit: int = 100,
        offset: int = 0,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[StateHistory]:
        """
        Récupère l'historique d'état d'un bot.

        Args:
            bot_id: ID du bot
            limit: Nombre d'entrées
            offset: Décalage
            from_date: Date de début
            to_date: Date de fin

        Returns:
            Historique d'état
        """
        try:
            history = self._state_histories.get(bot_id, [])
            
            if from_date:
                history = [h for h in history if h.timestamp >= from_date]
            if to_date:
                history = [h for h in history if h.timestamp <= to_date]
            
            history.sort(key=lambda x: x.timestamp, reverse=True)
            return history[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'historique: {e}")
            return []

    async def get_snapshots(
        self,
        bot_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[BotSnapshot]:
        """
        Récupère les snapshots d'un bot.

        Args:
            bot_id: ID du bot
            limit: Nombre de snapshots
            offset: Décalage

        Returns:
            Snapshots du bot
        """
        try:
            snapshots = self._snapshots.get(bot_id, [])
            snapshots.sort(key=lambda x: x.timestamp, reverse=True)
            return snapshots[offset:offset + limit]

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des snapshots: {e}")
            return []

    # ========================================================================
    # MONITORING ET TIMEOUTS
    # ========================================================================

    async def _start_monitoring(
        self,
        bot_id: UUID,
        state: BotState
    ) -> None:
        """
        Démarre le monitoring d'un état.

        Args:
            bot_id: ID du bot
            state: État à surveiller
        """
        try:
            # Arrêt du monitoring existant
            if bot_id in self._monitoring_tasks:
                self._monitoring_tasks[bot_id].cancel()

            timeout = self.STATE_TIMEOUTS.get(state)
            if timeout:
                self._monitoring_tasks[bot_id] = asyncio.create_task(
                    self._monitor_state(bot_id, state, timeout)
                )

        except Exception as e:
            logger.error(f"Erreur lors du démarrage du monitoring: {e}")

    async def _monitor_state(
        self,
        bot_id: UUID,
        state: BotState,
        timeout: int
    ) -> None:
        """
        Surveille un état.

        Args:
            bot_id: ID du bot
            state: État à surveiller
            timeout: Timeout en secondes
        """
        try:
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                current_state = await self.get_state(bot_id)
                if current_state != state:
                    break
                await asyncio.sleep(1)

            # Vérification du timeout
            current_state = await self.get_state(bot_id)
            if current_state == state:
                logger.warning(f"Timeout de l'état {state.value} pour {bot_id}")
                await self.set_state(
                    bot_id=bot_id,
                    new_state=BotState.ERROR,
                    transition=StateTransition.ERROR,
                    reason=f"Timeout de l'état {state.value}"
                )
                await self._trigger_timeout_callbacks(bot_id, state)

        except asyncio.CancelledError:
            logger.info(f"Monitoring de l'état {state.value} annulé pour {bot_id}")
        except Exception as e:
            logger.error(f"Erreur lors du monitoring de l'état: {e}")

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    async def register_state_change_callback(
        self,
        bot_id: UUID,
        callback: callable
    ) -> None:
        """
        Enregistre un callback pour les changements d'état.

        Args:
            bot_id: ID du bot
            callback: Fonction de callback
        """
        if bot_id not in self._state_change_callbacks:
            self._state_change_callbacks[bot_id] = []
        self._state_change_callbacks[bot_id].append(callback)

    async def register_timeout_callback(
        self,
        bot_id: UUID,
        callback: callable
    ) -> None:
        """
        Enregistre un callback pour les timeouts.

        Args:
            bot_id: ID du bot
            callback: Fonction de callback
        """
        if bot_id not in self._state_timeout_callbacks:
            self._state_timeout_callbacks[bot_id] = []
        self._state_timeout_callbacks[bot_id].append(callback)

    async def _trigger_callbacks(
        self,
        bot_id: UUID,
        previous_state: BotState,
        new_state: BotState
    ) -> None:
        """
        Déclenche les callbacks de changement d'état.

        Args:
            bot_id: ID du bot
            previous_state: État précédent
            new_state: Nouvel état
        """
        try:
            if bot_id in self._state_change_callbacks:
                for callback in self._state_change_callbacks[bot_id]:
                    try:
                        await callback(bot_id, previous_state, new_state)
                    except Exception as e:
                        logger.error(f"Erreur dans le callback: {e}")

        except Exception as e:
            logger.error(f"Erreur lors du déclenchement des callbacks: {e}")

    async def _trigger_timeout_callbacks(
        self,
        bot_id: UUID,
        state: BotState
    ) -> None:
        """
        Déclenche les callbacks de timeout.

        Args:
            bot_id: ID du bot
            state: État en timeout
        """
        try:
            if bot_id in self._state_timeout_callbacks:
                for callback in self._state_timeout_callbacks[bot_id]:
                    try:
                        await callback(bot_id, state)
                    except Exception as e:
                        logger.error(f"Erreur dans le callback de timeout: {e}")

        except Exception as e:
            logger.error(f"Erreur lors du déclenchement des callbacks de timeout: {e}")

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _save_state(self, bot_id: UUID) -> None:
        """
        Sauvegarde l'état dans Redis.

        Args:
            bot_id: ID du bot
        """
        try:
            state = self._states.get(bot_id)
            if state:
                key = f"state:bot:{bot_id}"
                await self.redis.setex(
                    key,
                    86400 * 7,  # 7 jours
                    state.value
                )

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'état: {e}")

    async def _load_state(self, bot_id: UUID) -> Optional[BotState]:
        """
        Charge l'état depuis Redis.

        Args:
            bot_id: ID du bot

        Returns:
            État du bot
        """
        try:
            key = f"state:bot:{bot_id}"
            data = await self.redis.get(key)
            if data:
                return BotState(data.decode())
            return None

        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'état: {e}")
            return None

    async def _save_history(
        self,
        bot_id: UUID,
        history: StateHistory
    ) -> None:
        """
        Sauvegarde l'historique dans Redis.

        Args:
            bot_id: ID du bot
            history: Historique à sauvegarder
        """
        try:
            key = f"state:history:{bot_id}"
            await self.redis.lpush(
                key,
                json.dumps(history.to_dict())
            )
            await self.redis.ltrim(key, 0, 999)  # Garder les 1000 derniers

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de l'historique: {e}")

    async def _save_snapshot(
        self,
        bot_id: UUID,
        snapshot: BotSnapshot
    ) -> None:
        """
        Sauvegarde un snapshot dans Redis.

        Args:
            bot_id: ID du bot
            snapshot: Snapshot à sauvegarder
        """
        try:
            key = f"state:snapshot:{bot_id}"
            await self.redis.lpush(
                key,
                json.dumps(snapshot.to_dict())
            )
            await self.redis.ltrim(key, 0, 99)  # Garder les 100 derniers

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du snapshot: {e}")

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
                "total_transitions": self._metrics["total_transitions"],
                "current_states": self._metrics["current_states"],
                "state_durations": self._metrics["state_durations"],
                "error_count": self._metrics["error_count"],
                "recovery_count": self._metrics["recovery_count"],
                "last_transition": self._metrics["last_transition"],
                "active_bots": len(self._states),
                "monitoring_tasks": len(self._monitoring_tasks),
                "cached_histories": len(self._state_histories),
                "cached_snapshots": len(self._snapshots),
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
        logger.info("Fermeture de ArbitrageBotStateManager...")
        
        # Annulation des tâches de monitoring
        for task in self._monitoring_tasks.values():
            task.cancel()
        
        self._states.clear()
        self._previous_states.clear()
        self._state_timers.clear()
        self._state_histories.clear()
        self._snapshots.clear()
        self._state_change_callbacks.clear()
        self._state_timeout_callbacks.clear()
        self._monitoring_tasks.clear()
        
        logger.info("ArbitrageBotStateManager fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_state_manager(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None
) -> ArbitrageBotStateManager:
    """
    Crée une instance du gestionnaire d'état.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API

    Returns:
        Instance du gestionnaire
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotStateManager(
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "BotState",
    "StateTransition",
    "StateHistory",
    "BotSnapshot",
    "ArbitrageBotStateManager",
    "create_arbitrage_bot_state_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du gestionnaire d'état."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT STATE MANAGER")
    print("=" * 60)

    # Création du gestionnaire
    state_manager = create_arbitrage_bot_state_manager()

    # Création d'un bot exemple
    bot_id = uuid4()
    print(f"\n✅ Bot ID: {bot_id}")

    # Changement d'état
    print(f"\n🔄 Changement d'état...")
    
    await state_manager.set_state(
        bot_id=bot_id,
        new_state=BotState.IDLE,
        transition=StateTransition.START,
        reason="Bot initialisé"
    )
    state = await state_manager.get_state(bot_id)
    print(f"   État actuel: {state.value}")

    # Démarrage du bot
    await state_manager.start(bot_id)
    state = await state_manager.get_state(bot_id)
    print(f"   Après démarrage: {state.value}")

    # Pause
    await state_manager.pause(bot_id)
    state = await state_manager.get_state(bot_id)
    print(f"   Après pause: {state.value}")

    # Reprise
    await state_manager.resume(bot_id)
    state = await state_manager.get_state(bot_id)
    print(f"   Après reprise: {state.value}")

    # Erreur
    await state_manager.error(bot_id, "Erreur de test")
    state = await state_manager.get_state(bot_id)
    print(f"   Après erreur: {state.value}")

    # Récupération
    await state_manager.recover(bot_id)
    state = await state_manager.get_state(bot_id)
    print(f"   Après récupération: {state.value}")

    # Arrêt
    await state_manager.stop(bot_id)
    state = await state_manager.get_state(bot_id)
    print(f"   Après arrêt: {state.value}")

    # Historique
    history = await state_manager.get_history(bot_id, limit=10)
    print(f"\n📋 Historique des états ({len(history)} entrées):")
    for h in history[:5]:
        print(f"   {h.timestamp.strftime('%H:%M:%S')}: {h.previous_state.value} -> {h.current_state.value} ({h.transition.value})")

    # Statistiques
    health = await state_manager.get_health()
    print(f"\n📊 Statistiques:")
    print(f"   Transitions: {health['total_transitions']}")
    print(f"   Erreurs: {health['error_count']}")
    print(f"   Récupérations: {health['recovery_count']}")
    print(f"   Bots actifs: {health['active_bots']}")

    # Fermeture
    await state_manager.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotStateManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
