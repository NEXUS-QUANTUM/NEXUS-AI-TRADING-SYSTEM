"""
NEXUS AI TRADING SYSTEM - HEDGE BOT LOCKS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des verrous pour le Hedge Bot.
Support des verrous distribués, temporisés, hiérarchiques, et plus.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class LockType(Enum):
    """Types de verrous."""
    MUTEX = "mutex"              # Verrou mutex simple
    SEMAPHORE = "semaphore"      # Sémaphore
    READ_WRITE = "read_write"    # Verrou lecture/écriture
    HIERARCHICAL = "hierarchical" # Verrou hiérarchique
    TIMED = "timed"              # Verrou temporisé
    DISTRIBUTED = "distributed"  # Verrou distribué
    FAIR = "fair"                # Verrou équitable
    REENTRANT = "reentrant"      # Verrou réentrant


class LockStatus(Enum):
    """Statuts de verrou."""
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    WAITING = "waiting"
    EXPIRED = "expired"
    RELEASED = "released"
    TIMEOUT = "timeout"


@dataclass
class LockInfo:
    """Informations sur un verrou."""
    lock_id: UUID
    name: str
    lock_type: LockType
    owner: str
    resource: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None
    timeout_seconds: Optional[int] = None
    status: LockStatus = LockStatus.LOCKED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "lock_id": str(self.lock_id),
            "name": self.name,
            "lock_type": self.lock_type.value,
            "owner": self.owner,
            "resource": self.resource,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "timeout_seconds": self.timeout_seconds,
            "status": self.status.value,
            "metadata": self.metadata
        }


@dataclass
class LockRequest:
    """Requête de verrou."""
    request_id: UUID
    lock_name: str
    owner: str
    timeout_seconds: int
    created_at: datetime
    acquired_at: Optional[datetime] = None
    acquired_lock_id: Optional[UUID] = None
    status: str = "pending"  # pending, acquired, rejected, timed_out
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LockStats:
    """Statistiques de verrou."""
    total_acquires: int = 0
    total_releases: int = 0
    total_timeouts: int = 0
    total_errors: int = 0
    current_locks: int = 0
    max_locks: int = 0
    avg_hold_time: float = 0.0
    total_hold_time: float = 0.0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_resource: Dict[str, int] = field(default_factory=dict)
    last_acquire: Optional[datetime] = None
    last_release: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "total_acquires": self.total_acquires,
            "total_releases": self.total_releases,
            "total_timeouts": self.total_timeouts,
            "total_errors": self.total_errors,
            "current_locks": self.current_locks,
            "max_locks": self.max_locks,
            "avg_hold_time": self.avg_hold_time,
            "total_hold_time": self.total_hold_time,
            "by_type": self.by_type,
            "by_resource": self.by_resource,
            "last_acquire": self.last_acquire.isoformat() if self.last_acquire else None,
            "last_release": self.last_release.isoformat() if self.last_release else None
        }


# ============================================================================
# CLASSE LOCK MANAGER
# ============================================================================

class LockManager:
    """
    Gestionnaire de verrous distribué.
    """

    # Préfixe Redis
    REDIS_PREFIX = "nexus:lock:"
    
    # TTL par défaut pour les verrous Redis
    DEFAULT_REDIS_TTL = 300  # 5 minutes
    
    # Nombre maximum de verrous par ressource
    MAX_LOCKS_PER_RESOURCE = 1000

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        redis_url: str = "redis://localhost:6379/0",
        default_timeout: int = 30,
        cleanup_interval: int = 60
    ):
        """
        Initialise le gestionnaire de verrous.

        Args:
            redis_client: Client Redis (optionnel)
            redis_url: URL de connexion Redis
            default_timeout: Timeout par défaut en secondes
            cleanup_interval: Intervalle de nettoyage en secondes
        """
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis.from_url(redis_url)
        
        self.default_timeout = default_timeout
        self.cleanup_interval = cleanup_interval
        
        # Cache local
        self._local_locks: Dict[str, asyncio.Lock] = {}
        self._lock_info: Dict[str, LockInfo] = {}
        self._lock_queue: Dict[str, asyncio.Queue] = {}
        self._lock_stats: Dict[str, LockStats] = {}
        
        # Tâches de nettoyage
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running: bool = True
        
        # Métriques
        self._metrics = {
            "total_locks": 0,
            "active_locks": 0,
            "by_type": {},
            "by_status": {},
            "last_cleanup": None
        }

        # Démarrage du nettoyage
        self._start_cleanup()

        logger.info("LockManager initialisé avec succès")

    def _start_cleanup(self) -> None:
        """Démarre la tâche de nettoyage."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage des verrous."""
        try:
            while self._running:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_locks()
                self._metrics["last_cleanup"] = datetime.now().isoformat()
        except asyncio.CancelledError:
            logger.info("Tâche de nettoyage annulée")
        except Exception as e:
            logger.error(f"Erreur dans la boucle de nettoyage: {e}")

    async def _cleanup_expired_locks(self) -> None:
        """Nettoie les verrous expirés."""
        try:
            # Nettoyage des verrous Redis
            pattern = f"{self.REDIS_PREFIX}*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                lock_data = await self.redis.get(key)
                if lock_data:
                    lock_info = json.loads(lock_data)
                    expires_at = lock_info.get("expires_at")
                    
                    if expires_at:
                        expires_dt = datetime.fromisoformat(expires_at)
                        if datetime.now() > expires_dt:
                            await self._release_redis_lock(key.decode())
            
            # Nettoyage des verrous locaux
            expired_names = []
            for name, info in self._lock_info.items():
                if info.expires_at and datetime.now() > info.expires_at:
                    expired_names.append(name)
            
            for name in expired_names:
                await self.release(name, force=True)
                
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des verrous: {e}")

    # ========================================================================
    # MÉTHODES D'ACQUISITION
    # ========================================================================

    async def acquire(
        self,
        name: str,
        timeout: Optional[int] = None,
        lock_type: LockType = LockType.MUTEX,
        owner: Optional[str] = None,
        resource: Optional[str] = None,
        wait: bool = True,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Acquiert un verrou.

        Args:
            name: Nom du verrou
            timeout: Timeout en secondes
            lock_type: Type de verrou
            owner: Propriétaire
            resource: Ressource
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        try:
            lock_id = uuid4()
            owner = owner or f"unknown-{uuid4().hex[:8]}"
            resource = resource or name
            timeout = timeout or self.default_timeout
            expires_at = datetime.now() + timedelta(seconds=timeout)

            # Vérification du type de verrou
            if lock_type == LockType.DISTRIBUTED:
                return await self._acquire_distributed(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            elif lock_type == LockType.SEMAPHORE:
                return await self._acquire_semaphore(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            elif lock_type == LockType.READ_WRITE:
                return await self._acquire_read_write(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            elif lock_type == LockType.HIERARCHICAL:
                return await self._acquire_hierarchical(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
            )
            elif lock_type == LockType.FAIR:
                return await self._acquire_fair(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            else:
                # Mutex par défaut
                return await self._acquire_mutex(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du verrou {name}: {e}")
            self._update_stats(name, error=True)
            return False

    async def _acquire_mutex(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un verrou mutex.

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        try:
            # Vérification du verrou existant
            if name in self._lock_info:
                info = self._lock_info[name]
                if info.status == LockStatus.LOCKED:
                    if wait:
                        # Attente du verrou
                        if name not in self._lock_queue:
                            self._lock_queue[name] = asyncio.Queue()
                        
                        try:
                            await asyncio.wait_for(
                                self._lock_queue[name].get(),
                                timeout=timeout
                            )
                        except asyncio.TimeoutError:
                            self._update_stats(name, timeout=True)
                            return False
                    else:
                        return False

            # Acquisition du verrou
            info = LockInfo(
                lock_id=lock_id,
                name=name,
                lock_type=LockType.MUTEX,
                owner=owner,
                resource=resource,
                acquired_at=datetime.now(),
                expires_at=expires_at,
                timeout_seconds=timeout,
                status=LockStatus.LOCKED,
                metadata=metadata or {}
            )

            self._lock_info[name] = info
            
            # Sauvegarde dans Redis pour les verrous distribués
            await self._save_lock_info(name, info)

            # Mise à jour des métriques
            self._update_stats(name, acquired=True)
            self._metrics["total_locks"] += 1
            self._metrics["active_locks"] += 1
            
            if "mutex" not in self._metrics["by_type"]:
                self._metrics["by_type"]["mutex"] = 0
            self._metrics["by_type"]["mutex"] += 1

            logger.info(f"Verrou {name} acquis par {owner}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du mutex: {e}")
            return False

    async def _acquire_distributed(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un verrou distribué (Redis).

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        try:
            redis_key = f"{self.REDIS_PREFIX}{name}"
            redis_value = json.dumps({
                "lock_id": str(lock_id),
                "owner": owner,
                "resource": resource,
                "acquired_at": datetime.now().isoformat(),
                "expires_at": expires_at.isoformat(),
                "metadata": metadata or {}
            })

            # Tentative d'acquisition
            acquired = await self.redis.set(
                redis_key,
                redis_value,
                nx=True,
                ex=timeout
            )

            if acquired:
                # Verrou acquis
                info = LockInfo(
                    lock_id=lock_id,
                    name=name,
                    lock_type=LockType.DISTRIBUTED,
                    owner=owner,
                    resource=resource,
                    acquired_at=datetime.now(),
                    expires_at=expires_at,
                    timeout_seconds=timeout,
                    status=LockStatus.LOCKED,
                    metadata=metadata or {}
                )
                self._lock_info[name] = info
                self._update_stats(name, acquired=True)
                logger.info(f"Verrou distribué {name} acquis par {owner}")
                return True
            elif wait:
                # Attente du verrou
                attempts = 0
                while attempts < timeout:
                    await asyncio.sleep(0.5)
                    acquired = await self.redis.set(
                        redis_key,
                        redis_value,
                        nx=True,
                        ex=timeout
                    )
                    if acquired:
                        info = LockInfo(
                            lock_id=lock_id,
                            name=name,
                            lock_type=LockType.DISTRIBUTED,
                            owner=owner,
                            resource=resource,
                            acquired_at=datetime.now(),
                            expires_at=expires_at,
                            timeout_seconds=timeout,
                            status=LockStatus.LOCKED,
                            metadata=metadata or {}
                        )
                        self._lock_info[name] = info
                        self._update_stats(name, acquired=True)
                        logger.info(f"Verrou distribué {name} acquis par {owner} après attente")
                        return True
                    attempts += 1
                
                self._update_stats(name, timeout=True)
                return False
            else:
                return False

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du verrou distribué: {e}")
            return False

    async def _acquire_semaphore(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un sémaphore.

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        # Implémentation simplifiée du sémaphore
        # Dans une version complète, utiliser Redis pour le compteur
        try:
            key = f"semaphore:{name}"
            max_permits = metadata.get("max_permits", 10) if metadata else 10
            
            # Récupération du nombre de permits actifs
            current = await self.redis.get(key)
            current = int(current) if current else 0
            
            if current < max_permits:
                # Incrémenter le compteur
                await self.redis.incr(key)
                await self.redis.expire(key, timeout)
                
                info = LockInfo(
                    lock_id=lock_id,
                    name=name,
                    lock_type=LockType.SEMAPHORE,
                    owner=owner,
                    resource=resource,
                    acquired_at=datetime.now(),
                    expires_at=expires_at,
                    timeout_seconds=timeout,
                    status=LockStatus.LOCKED,
                    metadata=metadata or {}
                )
                self._lock_info[name] = info
                self._update_stats(name, acquired=True)
                logger.info(f"Sémaphore {name} acquis par {owner}")
                return True
            elif wait:
                # Attente d'un permit
                attempts = 0
                while attempts < timeout:
                    await asyncio.sleep(0.5)
                    current = await self.redis.get(key)
                    current = int(current) if current else 0
                    if current < max_permits:
                        await self.redis.incr(key)
                        await self.redis.expire(key, timeout)
                        info = LockInfo(
                            lock_id=lock_id,
                            name=name,
                            lock_type=LockType.SEMAPHORE,
                            owner=owner,
                            resource=resource,
                            acquired_at=datetime.now(),
                            expires_at=expires_at,
                            timeout_seconds=timeout,
                            status=LockStatus.LOCKED,
                            metadata=metadata or {}
                        )
                        self._lock_info[name] = info
                        self._update_stats(name, acquired=True)
                        logger.info(f"Sémaphore {name} acquis par {owner} après attente")
                        return True
                    attempts += 1
                
                self._update_stats(name, timeout=True)
                return False
            else:
                return False

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du sémaphore: {e}")
            return False

    async def _acquire_read_write(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un verrou lecture/écriture.

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        mode = metadata.get("mode", "write") if metadata else "write"
        key_read = f"rw_read:{name}"
        key_write = f"rw_write:{name}"
        
        try:
            if mode == "read":
                # Verrou lecture
                # Vérifier s'il y a un verrou écriture
                write_lock = await self.redis.get(key_write)
                if write_lock:
                    if wait:
                        # Attendre la fin du verrou écriture
                        attempts = 0
                        while attempts < timeout:
                            await asyncio.sleep(0.5)
                            write_lock = await self.redis.get(key_write)
                            if not write_lock:
                                break
                            attempts += 1
                        if write_lock:
                            return False
                    else:
                        return False
                
                # Incrémenter le compteur de lecture
                await self.redis.incr(key_read)
                await self.redis.expire(key_read, timeout)
                
                info = LockInfo(
                    lock_id=lock_id,
                    name=name,
                    lock_type=LockType.READ_WRITE,
                    owner=owner,
                    resource=resource,
                    acquired_at=datetime.now(),
                    expires_at=expires_at,
                    timeout_seconds=timeout,
                    status=LockStatus.LOCKED,
                    metadata={"mode": "read", **metadata or {}}
                )
                self._lock_info[name] = info
                self._update_stats(name, acquired=True)
                logger.info(f"Verrou lecture {name} acquis par {owner}")
                return True
                
            else:
                # Verrou écriture
                # Vérifier s'il y a des verrous lecture ou écriture
                read_count = await self.redis.get(key_read)
                read_count = int(read_count) if read_count else 0
                write_lock = await self.redis.get(key_write)
                
                if read_count > 0 or write_lock:
                    if wait:
                        # Attendre la libération de tous les verrous
                        attempts = 0
                        while attempts < timeout:
                            await asyncio.sleep(0.5)
                            read_count = await self.redis.get(key_read)
                            read_count = int(read_count) if read_count else 0
                            write_lock = await self.redis.get(key_write)
                            if read_count == 0 and not write_lock:
                                break
                            attempts += 1
                        if read_count > 0 or write_lock:
                            return False
                    else:
                        return False
                
                # Acquérir le verrou écriture
                await self.redis.set(key_write, owner, ex=timeout)
                
                info = LockInfo(
                    lock_id=lock_id,
                    name=name,
                    lock_type=LockType.READ_WRITE,
                    owner=owner,
                    resource=resource,
                    acquired_at=datetime.now(),
                    expires_at=expires_at,
                    timeout_seconds=timeout,
                    status=LockStatus.LOCKED,
                    metadata={"mode": "write", **metadata or {}}
                )
                self._lock_info[name] = info
                self._update_stats(name, acquired=True)
                logger.info(f"Verrou écriture {name} acquis par {owner}")
                return True

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du verrou lecture/écriture: {e}")
            return False

    async def _acquire_hierarchical(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un verrou hiérarchique.

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        # Implémentation simplifiée des verrous hiérarchiques
        hierarchy = metadata.get("hierarchy", []) if metadata else []
        hierarchy.append(name)
        
        # Acquérir les verrous en cascade
        for level in hierarchy:
            acquired = await self._acquire_mutex(
                level,
                uuid4(),
                owner,
                f"{resource}:{level}",
                timeout,
                expires_at,
                wait,
                metadata
            )
            if not acquired:
                # Relâcher les verrous acquis
                for lvl in hierarchy[:hierarchy.index(level)]:
                    await self.release(lvl)
                return False
        
        return True

    async def _acquire_fair(
        self,
        name: str,
        lock_id: UUID,
        owner: str,
        resource: str,
        timeout: int,
        expires_at: datetime,
        wait: bool,
        metadata: Optional[Dict]
    ) -> bool:
        """
        Acquiert un verrou équitable.

        Args:
            name: Nom du verrou
            lock_id: ID du verrou
            owner: Propriétaire
            resource: Ressource
            timeout: Timeout
            expires_at: Date d'expiration
            wait: Attendre
            metadata: Métadonnées

        Returns:
            True si le verrou a été acquis
        """
        # Implémentation simplifiée des verrous équitables
        # Utilisation d'une file d'attente FIFO
        key_queue = f"fair_queue:{name}"
        
        try:
            if name not in self._lock_queue:
                self._lock_queue[name] = asyncio.Queue()
            
            # Si le verrou est libre
            if name not in self._lock_info or self._lock_info[name].status == LockStatus.UNLOCKED:
                return await self._acquire_mutex(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            
            # Ajout à la file d'attente
            queue_item = {
                "owner": owner,
                "lock_id": str(lock_id),
                "timestamp": datetime.now().isoformat()
            }
            await self._lock_queue[name].put(queue_item)
            
            # Attente de son tour
            try:
                await asyncio.wait_for(
                    self._lock_queue[name].get(),
                    timeout=timeout
                )
                return await self._acquire_mutex(
                    name, lock_id, owner, resource, timeout, expires_at, wait, metadata
                )
            except asyncio.TimeoutError:
                self._update_stats(name, timeout=True)
                return False

        except Exception as e:
            logger.error(f"Erreur lors de l'acquisition du verrou équitable: {e}")
            return False

    # ========================================================================
    # MÉTHODES DE LIBÉRATION
    # ========================================================================

    async def release(
        self,
        name: str,
        force: bool = False,
        owner: Optional[str] = None
    ) -> bool:
        """
        Libère un verrou.

        Args:
            name: Nom du verrou
            force: Forcer la libération
            owner: Propriétaire (optionnel)

        Returns:
            True si le verrou a été libéré
        """
        try:
            info = self._lock_info.get(name)
            if not info:
                logger.warning(f"Verrou {name} non trouvé")
                return False

            # Vérification du propriétaire
            if owner and info.owner != owner:
                if not force:
                    logger.warning(f"Propriétaire invalide pour le verrou {name}")
                    return False

            # Libération du verrou
            if info.lock_type == LockType.DISTRIBUTED:
                await self._release_redis_lock(name)
            elif info.lock_type == LockType.SEMAPHORE:
                await self._release_semaphore(name)
            elif info.lock_type == LockType.READ_WRITE:
                await self._release_read_write(name)
            elif info.lock_type == LockType.HIERARCHICAL:
                await self._release_hierarchical(name)
            
            # Mise à jour du statut
            info.status = LockStatus.RELEASED
            self._lock_info[name] = info

            # Notification de la file d'attente
            if name in self._lock_queue and not self._lock_queue[name].empty():
                try:
                    await self._lock_queue[name].put(None)
                except Exception:
                    pass

            # Mise à jour des métriques
            self._update_stats(name, released=True)
            self._metrics["active_locks"] -= 1

            logger.info(f"Verrou {name} libéré par {info.owner}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la libération du verrou {name}: {e}")
            return False

    async def _release_redis_lock(self, name: str) -> None:
        """
        Libère un verrou Redis.

        Args:
            name: Nom du verrou
        """
        try:
            key = f"{self.REDIS_PREFIX}{name}"
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Erreur lors de la libération du verrou Redis: {e}")

    async def _release_semaphore(self, name: str) -> None:
        """
        Libère un sémaphore.

        Args:
            name: Nom du verrou
        """
        try:
            key = f"semaphore:{name}"
            await self.redis.decr(key)
            # Nettoyer si le compteur est à 0
            current = await self.redis.get(key)
            if current and int(current) <= 0:
                await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Erreur lors de la libération du sémaphore: {e}")

    async def _release_read_write(self, name: str) -> None:
        """
        Libère un verrou lecture/écriture.

        Args:
            name: Nom du verrou
        """
        try:
            info = self._lock_info.get(name)
            if info and info.metadata.get("mode") == "read":
                key = f"rw_read:{name}"
                await self.redis.decr(key)
                # Nettoyer si le compteur est à 0
                current = await self.redis.get(key)
                if current and int(current) <= 0:
                    await self.redis.delete(key)
            else:
                key = f"rw_write:{name}"
                await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Erreur lors de la libération du verrou lecture/écriture: {e}")

    async def _release_hierarchical(self, name: str) -> None:
        """
        Libère un verrou hiérarchique.

        Args:
            name: Nom du verrou
        """
        try:
            # Récupérer la hiérarchie depuis les métadonnées
            info = self._lock_info.get(name)
            if info and info.metadata.get("hierarchy"):
                hierarchy = info.metadata["hierarchy"]
                for level in reversed(hierarchy):
                    await self._release_mutex(level)
        except Exception as e:
            logger.error(f"Erreur lors de la libération du verrou hiérarchique: {e}")

    async def _release_mutex(self, name: str) -> None:
        """
        Libère un mutex.

        Args:
            name: Nom du verrou
        """
        try:
            if name in self._lock_info:
                del self._lock_info[name]
        except Exception as e:
            logger.error(f"Erreur lors de la libération du mutex: {e}")

    # ========================================================================
    # MÉTHODES DE RECHERCHE
    # ========================================================================

    async def is_locked(self, name: str) -> bool:
        """
        Vérifie si un verrou est verrouillé.

        Args:
            name: Nom du verrou

        Returns:
            True si verrouillé
        """
        info = self._lock_info.get(name)
        if info:
            return info.status == LockStatus.LOCKED
        
        # Vérification Redis
        redis_key = f"{self.REDIS_PREFIX}{name}"
        exists = await self.redis.exists(redis_key)
        return bool(exists)

    async def get_lock_info(self, name: str) -> Optional[LockInfo]:
        """
        Récupère les informations d'un verrou.

        Args:
            name: Nom du verrou

        Returns:
            Informations du verrou
        """
        info = self._lock_info.get(name)
        if info:
            return info
        
        # Récupération depuis Redis
        redis_key = f"{self.REDIS_PREFIX}{name}"
        data = await self.redis.get(redis_key)
        if data:
            lock_data = json.loads(data)
            return LockInfo(
                lock_id=UUID(lock_data["lock_id"]),
                name=name,
                lock_type=LockType(lock_data["lock_type"]),
                owner=lock_data["owner"],
                resource=lock_data["resource"],
                acquired_at=datetime.fromisoformat(lock_data["acquired_at"]),
                expires_at=datetime.fromisoformat(lock_data["expires_at"]) if lock_data.get("expires_at") else None,
                timeout_seconds=lock_data.get("timeout_seconds"),
                status=LockStatus(lock_data.get("status", "locked")),
                metadata=lock_data.get("metadata", {})
            )
        
        return None

    async def get_all_locks(self) -> List[LockInfo]:
        """
        Récupère tous les verrous.

        Returns:
            Liste des verrous
        """
        locks = list(self._lock_info.values())
        
        # Récupération depuis Redis
        pattern = f"{self.REDIS_PREFIX}*"
        keys = await self.redis.keys(pattern)
        for key in keys:
            data = await self.redis.get(key)
            if data:
                lock_data = json.loads(data)
                name = key.decode().replace(self.REDIS_PREFIX, "")
                if name not in self._lock_info:
                    lock = LockInfo(
                        lock_id=UUID(lock_data["lock_id"]),
                        name=name,
                        lock_type=LockType(lock_data["lock_type"]),
                        owner=lock_data["owner"],
                        resource=lock_data["resource"],
                        acquired_at=datetime.fromisoformat(lock_data["acquired_at"]),
                        expires_at=datetime.fromisoformat(lock_data["expires_at"]) if lock_data.get("expires_at") else None,
                        timeout_seconds=lock_data.get("timeout_seconds"),
                        status=LockStatus(lock_data.get("status", "locked")),
                        metadata=lock_data.get("metadata", {})
                    )
                    locks.append(lock)
        
        return locks

    # ========================================================================
    # MÉTHODES DE SAUVEGARDE
    # ========================================================================

    async def _save_lock_info(self, name: str, info: LockInfo) -> None:
        """
        Sauvegarde les informations d'un verrou dans Redis.

        Args:
            name: Nom du verrou
            info: Informations du verrou
        """
        try:
            key = f"{self.REDIS_PREFIX}{name}"
            await self.redis.setex(
                key,
                info.timeout_seconds or self.DEFAULT_REDIS_TTL,
                json.dumps(info.to_dict())
            )
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des informations du verrou: {e}")

    # ========================================================================
    # MÉTHODES DE STATISTIQUES
    # ========================================================================

    def _update_stats(
        self,
        name: str,
        acquired: bool = False,
        released: bool = False,
        timeout: bool = False,
        error: bool = False
    ) -> None:
        """
        Met à jour les statistiques.

        Args:
            name: Nom du verrou
            acquired: Acquisition
            released: Libération
            timeout: Timeout
            error: Erreur
        """
        if name not in self._lock_stats:
            self._lock_stats[name] = LockStats()
        
        stats = self._lock_stats[name]
        
        if acquired:
            stats.total_acquires += 1
            stats.current_locks += 1
            if stats.current_locks > stats.max_locks:
                stats.max_locks = stats.current_locks
            stats.last_acquire = datetime.now()
            
            # Mise à jour par type
            info = self._lock_info.get(name)
            if info:
                lock_type = info.lock_type.value
                if lock_type not in stats.by_type:
                    stats.by_type[lock_type] = 0
                stats.by_type[lock_type] += 1
                
                resource = info.resource
                if resource not in stats.by_resource:
                    stats.by_resource[resource] = 0
                stats.by_resource[resource] += 1
        
        if released:
            stats.total_releases += 1
            stats.current_locks -= 1
            stats.last_release = datetime.now()
            
            # Calcul du temps de détention
            info = self._lock_info.get(name)
            if info:
                hold_time = (datetime.now() - info.acquired_at).total_seconds()
                stats.total_hold_time += hold_time
                stats.avg_hold_time = stats.total_hold_time / stats.total_acquires if stats.total_acquires > 0 else 0
        
        if timeout:
            stats.total_timeouts += 1
        
        if error:
            stats.total_errors += 1

    async def get_stats(self, name: Optional[str] = None) -> Union[LockStats, Dict[str, LockStats]]:
        """
        Récupère les statistiques.

        Args:
            name: Nom du verrou (optionnel)

        Returns:
            Statistiques
        """
        if name:
            return self._lock_stats.get(name, LockStats())
        return self._lock_stats

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_locks": self._metrics["total_locks"],
                "active_locks": self._metrics["active_locks"],
                "by_type": self._metrics["by_type"],
                "by_status": self._metrics["by_status"],
                "last_cleanup": self._metrics["last_cleanup"],
                "cached_locks": len(self._lock_info),
                "pending_queues": len(self._lock_queue),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le gestionnaire."""
        logger.info("Fermeture de LockManager...")
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._lock_info.clear()
        self._lock_queue.clear()
        self._lock_stats.clear()
        
        logger.info("LockManager fermé")


# ============================================================================
# CONTEXT MANAGER
# ============================================================================

@asynccontextmanager
async def lock_context(
    lock_manager: LockManager,
    name: str,
    timeout: Optional[int] = None,
    lock_type: LockType = LockType.MUTEX,
    owner: Optional[str] = None,
    resource: Optional[str] = None,
    wait: bool = True,
    metadata: Optional[Dict] = None
) -> AsyncGenerator[bool, None]:
    """
    Context manager pour les verrous.

    Args:
        lock_manager: Gestionnaire de verrous
        name: Nom du verrou
        timeout: Timeout
        lock_type: Type de verrou
        owner: Propriétaire
        resource: Ressource
        wait: Attendre
        metadata: Métadonnées

    Yields:
        True si le verrou a été acquis
    """
    acquired = await lock_manager.acquire(
        name=name,
        timeout=timeout,
        lock_type=lock_type,
        owner=owner,
        resource=resource,
        wait=wait,
        metadata=metadata
    )
    
    try:
        yield acquired
    finally:
        if acquired:
            await lock_manager.release(name)


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_lock_manager(
    redis_url: str = "redis://localhost:6379/0",
    default_timeout: int = 30,
    cleanup_interval: int = 60
) -> LockManager:
    """
    Crée une instance de LockManager.

    Args:
        redis_url: URL de connexion Redis
        default_timeout: Timeout par défaut
        cleanup_interval: Intervalle de nettoyage

    Returns:
        Instance de LockManager
    """
    return LockManager(
        redis_url=redis_url,
        default_timeout=default_timeout,
        cleanup_interval=cleanup_interval
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "LockType",
    "LockStatus",
    "LockInfo",
    "LockRequest",
    "LockStats",
    "LockManager",
    "lock_context",
    "create_lock_manager"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du LockManager."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT LOCKS")
    print("=" * 60)

    # Création du gestionnaire
    lock_manager = create_lock_manager()

    print(f"\n✅ LockManager initialisé")

    # Acquisition d'un verrou
    print(f"\n🔒 Acquisition d'un verrou...")
    acquired = await lock_manager.acquire(
        name="test_lock",
        timeout=10,
        owner="test_user",
        resource="test_resource",
        metadata={"purpose": "testing"}
    )
    print(f"   Verrou acquis: {acquired}")

    # Vérification du verrou
    is_locked = await lock_manager.is_locked("test_lock")
    print(f"   Verrouillé: {is_locked}")

    # Récupération des informations
    info = await lock_manager.get_lock_info("test_lock")
    if info:
        print(f"   Propriétaire: {info.owner}")
        print(f"   Type: {info.lock_type.value}")
        print(f"   Expire: {info.expires_at}")

    # Utilisation du context manager
    print(f"\n🔄 Utilisation du context manager...")
    async with lock_context(lock_manager, "context_lock", timeout=5) as acquired_ctx:
        if acquired_ctx:
            print("   Verrou acquis via context manager")
            # Simuler un travail
            await asyncio.sleep(0.5)
        else:
            print("   Échec de l'acquisition du verrou")

    # Statistiques
    stats = await lock_manager.get_stats()
    print(f"\n📊 Statistiques:")
    print(f"   Total acquises: {stats.get('test_lock', {}).total_acquires}")
    print(f"   Verrous actuels: {stats.get('test_lock', {}).current_locks}")

    # Santé du service
    health = await lock_manager.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Statut: {health['status']}")
    print(f"   Verrous actifs: {health['active_locks']}")
    print(f"   Total verrous: {health['total_locks']}")

    # Fermeture
    await lock_manager.close()

    print("\n" + "=" * 60)
    print("LockManager NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
