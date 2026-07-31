# trading/bots/hedge_bot/hedge_bot_state.py
# Advanced State Management & Persistence Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot State Module - Module avancé de gestion d'état et de persistance pour le Hedge Bot.
Gère l'état du système, la persistance des données, la récupération après panne,
les checkpoints, et la synchronisation d'état pour l'ensemble du système de hedging.
"""

import asyncio
import json
import pickle
import time
import hashlib
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import zlib
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_state")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class StateScope(Enum):
    """Portées de l'état."""
    GLOBAL = "global"                  # État global
    SESSION = "session"                # État de session
    USER = "user"                      # État utilisateur
    BOT = "bot"                        # État du bot
    POSITION = "position"              # État de position
    SYSTEM = "system"                  # État système
    TRANSIENT = "transient"            # État transitoire


class StatePersistence(Enum):
    """Niveaux de persistance."""
    NONE = "none"                      # Pas de persistance
    MEMORY = "memory"                  # Persistance mémoire
    DISK = "disk"                      # Persistance disque
    DATABASE = "database"              # Persistance base de données
    DISTRIBUTED = "distributed"        # Persistance distribuée
    HYBRID = "hybrid"                  # Persistance hybride


class StateConsistency(Enum):
    """Niveaux de cohérence d'état."""
    EVENTUAL = "eventual"              # Cohérence éventuelle
    STRONG = "strong"                  # Cohérence forte
    SESSION = "session"                # Cohérence de session
    MONOTONIC = "monotonic"            # Cohérence monotone


class StateEventType(Enum):
    """Types d'événements d'état."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SNAPSHOT = "snapshot"
    RESTORE = "restore"
    ROLLBACK = "rollback"
    SYNC = "sync"
    CHECKPOINT = "checkpoint"


# ============== DATA MODELS ==============

@dataclass
class StateEntry:
    """Entrée d'état."""
    state_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    value: Any = None
    scope: StateScope = StateScope.SYSTEM
    persistence: StatePersistence = StatePersistence.DATABASE
    consistency: StateConsistency = StateConsistency.STRONG
    version: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    parent_state_id: Optional[str] = None
    hash: Optional[str] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "state_id": self.state_id,
            "key": self.key,
            "value": self.value,
            "scope": self.scope.value,
            "persistence": self.persistence.value,
            "consistency": self.consistency.value,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata,
            "tags": self.tags,
            "parent_state_id": self.parent_state_id,
            "hash": self.hash,
            "signature": self.signature
        }


@dataclass
class StateSnapshot:
    """Snapshot d'état."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    states: List[StateEntry] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0.0"
    checksum: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    compressed: bool = False
    size_bytes: int = 0


@dataclass
class StateTransition:
    """Transition d'état."""
    transition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state_id: str = ""
    from_state: Optional[Any] = None
    to_state: Any = None
    event_type: StateEventType = StateEventType.UPDATE
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateCheckpoint:
    """Checkpoint d'état."""
    checkpoint_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    snapshot: StateSnapshot = field(default_factory=StateSnapshot)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class StateEngineInterface(ABC):
    """Interface abstraite pour le moteur d'état."""
    
    @abstractmethod
    async def set_state(self, key: str, value: Any, scope: StateScope) -> StateEntry:
        """Définit une valeur d'état."""
        pass
    
    @abstractmethod
    async def get_state(self, key: str) -> Optional[StateEntry]:
        """Récupère une valeur d'état."""
        pass
    
    @abstractmethod
    async def delete_state(self, key: str) -> bool:
        """Supprime une valeur d'état."""
        pass
    
    @abstractmethod
    async def snapshot(self, name: str) -> StateSnapshot:
        """Crée un snapshot d'état."""
        pass
    
    @abstractmethod
    async def restore(self, snapshot_id: str) -> bool:
        """Restaure un snapshot d'état."""
        pass


# ============== IMPLÉMENTATION ==============

class StateEngine(StateEngineInterface):
    """
    Moteur d'état avancé pour le Hedge Bot.
    Gère l'état du système, la persistance, les snapshots et la récupération.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des états
        self._states: Dict[str, StateEntry] = {}
        self._states_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: Dict[str, StateSnapshot] = {}
        self._snapshots_lock = threading.RLock()
        
        # Gestion des checkpoints
        self._checkpoints: Dict[str, StateCheckpoint] = {}
        self._checkpoints_lock = threading.RLock()
        
        # Gestion des transitions
        self._transitions: deque = deque(maxlen=10000)
        self._transitions_lock = threading.RLock()
        
        # Cache des états
        self._state_cache: Dict[str, StateEntry] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "states_set": 0,
            "states_get": 0,
            "states_deleted": 0,
            "snapshots_created": 0,
            "snapshots_restored": 0,
            "checkpoints_created": 0,
            "transitions_recorded": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("StateEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_persistence": StatePersistence.DATABASE,
            "default_consistency": StateConsistency.STRONG,
            "cache_size": 10000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "enable_encryption": True,
            "auto_snapshot_interval": 3600,
            "max_snapshots": 100,
            "checkpoint_interval": 300,
            "state_retention_days": 30,
            "compression_threshold": 1024,
            "signature_required": False
        }
    
    async def start(self) -> None:
        """Démarre le moteur d'état."""
        logger.info("StateEngine starting...")
        self._is_running = True
        
        # Chargement des états persistants
        await self._load_persistent_states()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._snapshot_loop())
        asyncio.create_task(self._checkpoint_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("StateEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur d'état."""
        logger.info("StateEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des états
        await self._save_persistent_states()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("StateEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def set_state(
        self,
        key: str,
        value: Any,
        scope: StateScope = StateScope.SYSTEM,
        persistence: Optional[StatePersistence] = None,
        consistency: Optional[StateConsistency] = None,
        ttl: Optional[int] = None
    ) -> StateEntry:
        """Définit une valeur d'état."""
        self._stats["states_set"] += 1
        
        # Création de l'entrée d'état
        state = StateEntry(
            key=key,
            value=value,
            scope=scope,
            persistence=persistence or self.config["default_persistence"],
            consistency=consistency or self.config["default_consistency"],
            version=1,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl else None,
            metadata={"set_by": "state_engine"}
        )
        
        # Vérification de l'existant
        existing = await self._get_state_internal(key)
        if existing:
            state.version = existing.version + 1
            state.parent_state_id = existing.state_id
        
        # Hachage et signature
        if self.encryption_engine and self.config["enable_encryption"]:
            state.hash = self._compute_hash(state)
            if self.config["signature_required"]:
                state.signature = await self._sign_state(state)
        
        # Stockage en mémoire
        with self._states_lock:
            self._states[key] = state
        
        # Stockage en cache
        if self.config["enable_cache"]:
            with self._cache_lock:
                self._state_cache[key] = state
        
        # Persistance
        if state.persistence != StatePersistence.NONE:
            await self._persist_state(state)
        
        # Enregistrement de la transition
        await self._record_transition(state, StateEventType.UPDATE)
        
        logger.debug(f"State set: {key} scope={scope.value} version={state.version}")
        return state
    
    async def get_state(self, key: str) -> Optional[StateEntry]:
        """Récupère une valeur d'état."""
        self._stats["states_get"] += 1
        
        # Vérification du cache
        if self.config["enable_cache"]:
            with self._cache_lock:
                if key in self._state_cache:
                    state = self._state_cache[key]
                    # Vérification de l'expiration
                    if state.expires_at and datetime.now(timezone.utc) > state.expires_at:
                        del self._state_cache[key]
                        return None
                    return state
        
        # Récupération depuis le stockage
        state = await self._get_state_internal(key)
        
        if state:
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    self._state_cache[key] = state
        
        return state
    
    async def delete_state(self, key: str) -> bool:
        """Supprime une valeur d'état."""
        self._stats["states_deleted"] += 1
        
        with self._states_lock:
            if key in self._states:
                del self._states[key]
                
                # Suppression du cache
                if self.config["enable_cache"]:
                    with self._cache_lock:
                        if key in self._state_cache:
                            del self._state_cache[key]
                
                # Suppression persistante
                await self._delete_persistent_state(key)
                
                return True
        
        return False
    
    async def snapshot(self, name: str) -> StateSnapshot:
        """Crée un snapshot d'état."""
        self._stats["snapshots_created"] += 1
        
        # Collecte des états
        states = []
        with self._states_lock:
            for state in self._states.values():
                if state.persistence != StatePersistence.NONE:
                    states.append(state)
        
        # Création du snapshot
        snapshot = StateSnapshot(
            name=name,
            states=states,
            metadata={
                "state_count": len(states),
                "created_by": "state_engine"
            }
        )
        
        # Compression
        if len(pickle.dumps(snapshot)) > self.config["compression_threshold"]:
            snapshot.compressed = True
        
        # Stockage du snapshot
        with self._snapshots_lock:
            self._snapshots[snapshot.snapshot_id] = snapshot
            
            # Limitation du nombre de snapshots
            if len(self._snapshots) > self.config["max_snapshots"]:
                oldest = min(self._snapshots.keys())
                del self._snapshots[oldest]
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"state:snapshot:{snapshot.snapshot_id}",
                snapshot.to_dict(),
                DataType.SNAPSHOT
            )
        
        logger.info(f"Snapshot created: {name} with {len(states)} states")
        return snapshot
    
    async def restore(self, snapshot_id: str) -> bool:
        """Restaure un snapshot d'état."""
        self._stats["snapshots_restored"] += 1
        
        # Récupération du snapshot
        with self._snapshots_lock:
            snapshot = self._snapshots.get(snapshot_id)
        
        if not snapshot:
            # Recherche dans le stockage persistant
            if self.data_manager:
                data = await self.data_manager.retrieve(
                    f"state:snapshot:{snapshot_id}",
                    DataType.SNAPSHOT
                )
                if data:
                    snapshot = self._deserialize_snapshot(data)
        
        if not snapshot:
            logger.error(f"Snapshot not found: {snapshot_id}")
            return False
        
        # Restauration des états
        restored_count = 0
        
        with self._states_lock:
            for state in snapshot.states:
                self._states[state.key] = state
                
                # Mise à jour du cache
                if self.config["enable_cache"]:
                    with self._cache_lock:
                        self._state_cache[state.key] = state
                
                # Persistance
                await self._persist_state(state)
                
                restored_count += 1
        
        # Enregistrement de la transition
        await self._record_transition(None, StateEventType.RESTORE, 
                                    metadata={"snapshot_id": snapshot_id, "restored": restored_count})
        
        logger.info(f"Snapshot restored: {snapshot_id} with {restored_count} states")
        return True
    
    # ========== MÉTHODES PRIVÉES - INTERNE ==========
    
    async def _get_state_internal(self, key: str) -> Optional[StateEntry]:
        """Récupère un état en interne."""
        with self._states_lock:
            if key in self._states:
                state = self._states[key]
                # Vérification de l'expiration
                if state.expires_at and datetime.now(timezone.utc) > state.expires_at:
                    del self._states[key]
                    return None
                return state
        
        # Récupération persistante
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"state:{key}",
                DataType.STATE
            )
            if data:
                state = self._deserialize_state(data)
                if state:
                    with self._states_lock:
                        self._states[key] = state
                    return state
        
        return None
    
    async def _persist_state(self, state: StateEntry) -> None:
        """Persiste un état."""
        if not self.data_manager:
            return
        
        if state.persistence == StatePersistence.DATABASE or state.persistence == StatePersistence.DISTRIBUTED:
            await self.data_manager.store(
                f"state:{state.key}",
                state.to_dict(),
                DataType.STATE
            )
        elif state.persistence == StatePersistence.DISK:
            # Stockage sur disque
            import os
            state_dir = "./states"
            os.makedirs(state_dir, exist_ok=True)
            with open(f"{state_dir}/{state.key}.state", 'wb') as f:
                pickle.dump(state, f)
    
    async def _delete_persistent_state(self, key: str) -> None:
        """Supprime un état persistant."""
        if self.data_manager:
            await self.data_manager.delete(
                f"state:{key}",
                DataType.STATE
            )
        
        # Suppression du disque
        import os
        state_path = f"./states/{key}.state"
        if os.path.exists(state_path):
            os.remove(state_path)
    
    async def _record_transition(
        self,
        state: Optional[StateEntry],
        event_type: StateEventType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Enregistre une transition d'état."""
        transition = StateTransition(
            state_id=state.state_id if state else "",
            from_state=state.value if state else None,
            to_state=state.value if state else None,
            event_type=event_type,
            metadata=metadata or {}
        )
        
        with self._transitions_lock:
            self._transitions.append(transition)
            self._stats["transitions_recorded"] += 1
    
    def _compute_hash(self, state: StateEntry) -> str:
        """Calcule le hachage d'un état."""
        data = f"{state.key}{state.value}{state.version}{state.timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    async def _sign_state(self, state: StateEntry) -> str:
        """Signe un état."""
        if self.encryption_engine:
            signature = await self.encryption_engine.sign(
                state.hash.encode(),
                "state_signing_key"
            )
            return base64.b64encode(signature).decode()
        return ""
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_persistent_states(self) -> None:
        """Charge les états persistants."""
        try:
            if self.data_manager:
                # Récupération de tous les états
                states_data = await self.data_manager.retrieve_all(DataType.STATE)
                
                for data in states_data:
                    if data.value:
                        state = self._deserialize_state(data.value)
                        if state:
                            with self._states_lock:
                                self._states[state.key] = state
            
            # Chargement des états depuis le disque
            import os
            state_dir = "./states"
            if os.path.exists(state_dir):
                for file in os.listdir(state_dir):
                    if file.endswith(".state"):
                        try:
                            with open(f"{state_dir}/{file}", 'rb') as f:
                                state = pickle.load(f)
                            with self._states_lock:
                                self._states[state.key] = state
                        except Exception as e:
                            logger.error(f"Error loading state file {file}: {e}")
            
            logger.info(f"Loaded {len(self._states)} persistent states")
            
        except Exception as e:
            logger.error(f"Load persistent states error: {e}")
    
    async def _save_persistent_states(self) -> None:
        """Sauvegarde les états persistants."""
        try:
            with self._states_lock:
                for state in self._states.values():
                    if state.persistence in [StatePersistence.DATABASE, StatePersistence.DISTRIBUTED]:
                        await self._persist_state(state)
            
            logger.info(f"Saved {len(self._states)} persistent states")
            
        except Exception as e:
            logger.error(f"Save persistent states error: {e}")
    
    # ========== MÉTHODES PRIVÉES - BOUCLES ==========
    
    async def _snapshot_loop(self) -> None:
        """Boucle de snapshot automatique."""
        while self._is_running:
            await asyncio.sleep(self.config["auto_snapshot_interval"])
            
            try:
                # Création d'un snapshot automatique
                name = f"auto_snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                await self.snapshot(name)
                
                # Nettoyage des anciens snapshots
                with self._snapshots_lock:
                    if len(self._snapshots) > self.config["max_snapshots"]:
                        keys = sorted(self._snapshots.keys())
                        for key in keys[:len(self._snapshots) - self.config["max_snapshots"]]:
                            del self._snapshots[key]
                
                logger.debug("Auto snapshot created")
                
            except Exception as e:
                logger.error(f"Snapshot loop error: {e}")
    
    async def _checkpoint_loop(self) -> None:
        """Boucle de checkpoint."""
        while self._is_running:
            await asyncio.sleep(self.config["checkpoint_interval"])
            
            try:
                # Création d'un checkpoint
                snapshot = await self.snapshot(f"checkpoint_{int(time.time())}")
                
                checkpoint = StateCheckpoint(
                    name=f"checkpoint_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                    snapshot=snapshot
                )
                
                with self._checkpoints_lock:
                    self._checkpoints[checkpoint.checkpoint_id] = checkpoint
                    self._stats["checkpoints_created"] += 1
                
                logger.debug("Checkpoint created")
                
            except Exception as e:
                logger.error(f"Checkpoint loop error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._state_cache) > self.config["cache_size"]:
                        keys = list(self._state_cache.keys())
                        for key in keys[:len(self._state_cache) - self.config["cache_size"]]:
                            del self._state_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._states_lock:
                    self._stats["total_states"] = len(self._states)
                with self._snapshots_lock:
                    self._stats["total_snapshots"] = len(self._snapshots)
                with self._checkpoints_lock:
                    self._stats["total_checkpoints"] = len(self._checkpoints)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "state:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE DÉSÉRIALISATION ==========
    
    def _deserialize_state(self, data: Dict) -> Optional[StateEntry]:
        """Désérialise un état."""
        try:
            return StateEntry(
                state_id=data.get("state_id", str(uuid.uuid4())),
                key=data.get("key", ""),
                value=data.get("value"),
                scope=StateScope(data.get("scope", "system")),
                persistence=StatePersistence(data.get("persistence", "database")),
                consistency=StateConsistency(data.get("consistency", "strong")),
                version=data.get("version", 0),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                parent_state_id=data.get("parent_state_id"),
                hash=data.get("hash"),
                signature=data.get("signature")
            )
        except Exception as e:
            logger.error(f"Error deserializing state: {e}")
            return None
    
    def _deserialize_snapshot(self, data: Dict) -> Optional[StateSnapshot]:
        """Désérialise un snapshot."""
        try:
            states = []
            for state_data in data.get("states", []):
                state = self._deserialize_state(state_data)
                if state:
                    states.append(state)
            
            return StateSnapshot(
                snapshot_id=data.get("snapshot_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                states=states,
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                version=data.get("version", "1.0.0"),
                checksum=data.get("checksum"),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                compressed=data.get("compressed", False),
                size_bytes=data.get("size_bytes", 0)
            )
        except Exception as e:
            logger.error(f"Error deserializing snapshot: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Récupère un snapshot."""
        with self._snapshots_lock:
            return self._snapshots.get(snapshot_id)
    
    async def get_snapshots(self) -> List[StateSnapshot]:
        """Récupère les snapshots."""
        with self._snapshots_lock:
            return list(self._snapshots.values())
    
    async def get_checkpoint(self, checkpoint_id: str) -> Optional[StateCheckpoint]:
        """Récupère un checkpoint."""
        with self._checkpoints_lock:
            return self._checkpoints.get(checkpoint_id)
    
    async def get_checkpoints(self) -> List[StateCheckpoint]:
        """Récupère les checkpoints."""
        with self._checkpoints_lock:
            return list(self._checkpoints.values())
    
    async def get_transitions(self, limit: int = 100) -> List[StateTransition]:
        """Récupère les transitions récentes."""
        with self._transitions_lock:
            return list(self._transitions)[-limit:]
    
    async def rollback_to_checkpoint(self, checkpoint_id: str) -> bool:
        """Restaure un checkpoint."""
        with self._checkpoints_lock:
            checkpoint = self._checkpoints.get(checkpoint_id)
            if not checkpoint:
                return False
        
        return await self.restore(checkpoint.snapshot.snapshot_id)
    
    async def export_state(self, key: str, format: str = "json") -> str:
        """Exporte un état."""
        state = await self.get_state(key)
        if not state:
            return ""
        
        if format == "json":
            return json.dumps(state.to_dict(), indent=2)
        elif format == "pickle":
            return base64.b64encode(pickle.dumps(state)).decode()
        else:
            return str(state.value)
    
    async def import_state(self, key: str, data: str, format: str = "json") -> bool:
        """Importe un état."""
        try:
            if format == "json":
                state_dict = json.loads(data)
                state = self._deserialize_state(state_dict)
                if state:
                    await self.set_state(key, state.value, state.scope)
                    return True
            elif format == "pickle":
                state = pickle.loads(base64.b64decode(data))
                if isinstance(state, StateEntry):
                    await self.set_state(key, state.value, state.scope)
                    return True
            return False
        except Exception as e:
            logger.error(f"Import state error: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._states_lock:
            self._stats["total_states"] = len(self._states)
        with self._snapshots_lock:
            self._stats["total_snapshots"] = len(self._snapshots)
        with self._checkpoints_lock:
            self._stats["total_checkpoints"] = len(self._checkpoints)
        
        return self._stats.copy()


# ============== STATE CONTEXT MANAGER ==============

class StateContext:
    """
    Context manager pour les opérations d'état.
    Gère les transactions d'état et les rollbacks automatiques.
    """
    
    def __init__(self, engine: StateEngine, scope: StateScope = StateScope.SESSION):
        self.engine = engine
        self.scope = scope
        self._changes: List[Dict[str, Any]] = []
        self._committed = False
    
    async def __aenter__(self):
        return self
    
    async def set(self, key: str, value: Any) -> None:
        """Définit une valeur dans le contexte."""
        self._changes.append({
            "key": key,
            "value": value,
            "old_value": await self.engine.get_state(key)
        })
    
    async def commit(self) -> None:
        """Valide les changements."""
        for change in self._changes:
            await self.engine.set_state(
                change["key"],
                change["value"],
                self.scope
            )
        self._committed = True
    
    async def rollback(self) -> None:
        """Annule les changements."""
        for change in reversed(self._changes):
            if change["old_value"]:
                await self.engine.set_state(
                    change["key"],
                    change["old_value"].value,
                    self.scope
                )
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self._committed:
            await self.commit()
        elif exc_type is not None:
            await self.rollback()


# ============== FACTORY ==============

class StateFactory:
    """Factory pour créer des composants d'état."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> StateEngine:
        """Crée un moteur d'état."""
        engine = StateEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_context(engine: StateEngine, scope: StateScope = StateScope.SESSION) -> StateContext:
        """Crée un context manager d'état."""
        return StateContext(engine, scope)


# ============== EXPORT ==============

__all__ = [
    "StateScope",
    "StatePersistence",
    "StateConsistency",
    "StateEventType",
    "StateEntry",
    "StateSnapshot",
    "StateTransition",
    "StateCheckpoint",
    "StateEngineInterface",
    "StateEngine",
    "StateContext",
    "StateFactory"
]
