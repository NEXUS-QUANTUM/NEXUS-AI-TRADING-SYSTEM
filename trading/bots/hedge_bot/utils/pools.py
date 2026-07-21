"""
NEXUS AI TRADING SYSTEM - HEDGE BOT POOLS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des pools pour le Hedge Bot.
Support des pools de connexions, de threads, de processus, et d'objets.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import logging
import queue
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union
from uuid import UUID, uuid4

import aioredis
import asyncpg
import aiohttp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class PoolType(Enum):
    """Types de pools."""
    CONNECTION = "connection"       # Pool de connexions
    THREAD = "thread"              # Pool de threads
    PROCESS = "process"            # Pool de processus
    OBJECT = "object"              # Pool d'objets
    ASYNC = "async"                # Pool asynchrone
    RESOURCE = "resource"          # Pool de ressources
    TASK = "task"                  # Pool de tâches


class PoolStatus(Enum):
    """Statuts de pool."""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class PoolItem:
    """Élément de pool."""
    item_id: UUID
    item: Any
    created_at: datetime
    last_used: datetime
    in_use: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "item_id": str(self.item_id),
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "in_use": self.in_use,
            "metadata": self.metadata
        }


@dataclass
class PoolStats:
    """Statistiques de pool."""
    pool_id: UUID
    name: str
    pool_type: PoolType
    total_items: int
    available_items: int
    in_use_items: int
    total_created: int
    total_destroyed: int
    total_acquires: int
    total_releases: int
    total_timeouts: int
    total_errors: int
    average_acquire_time: float
    maximum_acquire_time: float
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "pool_id": str(self.pool_id),
            "name": self.name,
            "pool_type": self.pool_type.value,
            "total_items": self.total_items,
            "available_items": self.available_items,
            "in_use_items": self.in_use_items,
            "total_created": self.total_created,
            "total_destroyed": self.total_destroyed,
            "total_acquires": self.total_acquires,
            "total_releases": self.total_releases,
            "total_timeouts": self.total_timeouts,
            "total_errors": self.total_errors,
            "average_acquire_time": self.average_acquire_time,
            "maximum_acquire_time": self.maximum_acquire_time,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class PoolConfig:
    """Configuration de pool."""
    name: str
    pool_type: PoolType
    min_size: int = 1
    max_size: int = 10
    max_idle_time: int = 300  # secondes
    acquire_timeout: int = 30  # secondes
    max_lifetime: int = 3600  # secondes
    validation_interval: int = 60  # secondes
    prefill: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# CLASSE DE BASE DES POOLS
# ============================================================================

class BasePool:
    """
    Classe de base pour tous les pools.
    """

    def __init__(self, config: PoolConfig):
        """
        Initialise le pool.

        Args:
            config: Configuration du pool
        """
        self.config = config
        self._pool_id = uuid4()
        self._items: Dict[UUID, PoolItem] = {}
        self._available: queue.Queue = queue.Queue()
        self._lock = asyncio.Lock()
        self._status = PoolStatus.INITIALIZING
        self._stats = PoolStats(
            pool_id=self._pool_id,
            name=config.name,
            pool_type=config.pool_type,
            total_items=0,
            available_items=0,
            in_use_items=0,
            total_created=0,
            total_destroyed=0,
            total_acquires=0,
            total_releases=0,
            total_timeouts=0,
            total_errors=0,
            average_acquire_time=0.0,
            maximum_acquire_time=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = True

        logger.info(f"Pool {config.name} initialisé (ID: {self._pool_id})")

    async def initialize(self) -> None:
        """Initialise le pool."""
        self._status = PoolStatus.RUNNING
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        if self.config.prefill:
            await self._prefill()

        logger.info(f"Pool {self.config.name} démarré")

    async def close(self) -> None:
        """Ferme le pool."""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        await self._destroy_all()
        self._status = PoolStatus.STOPPED
        logger.info(f"Pool {self.config.name} fermé")

    async def _prefill(self) -> None:
        """Remplit le pool avec des éléments."""
        for _ in range(self.config.min_size):
            await self._create_item()

    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage."""
        try:
            while self._running:
                await asyncio.sleep(self.config.validation_interval)
                await self._cleanup()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Erreur dans la boucle de nettoyage: {e}")

    async def _cleanup(self) -> None:
        """Nettoie le pool."""
        async with self._lock:
            now = datetime.now()
            to_remove = []

            for item_id, item in self._items.items():
                # Vérification de l'expiration
                if item.in_use:
                    continue
                
                age = (now - item.created_at).total_seconds()
                idle = (now - item.last_used).total_seconds()
                
                if age > self.config.max_lifetime:
                    to_remove.append(item_id)
                elif idle > self.config.max_idle_time and len(self._items) > self.config.min_size:
                    to_remove.append(item_id)

            for item_id in to_remove:
                await self._destroy_item(item_id)

    async def _create_item(self) -> UUID:
        """
        Crée un nouvel élément.

        Returns:
            ID de l'élément
        """
        raise NotImplementedError

    async def _destroy_item(self, item_id: UUID) -> None:
        """
        Détruit un élément.

        Args:
            item_id: ID de l'élément
        """
        raise NotImplementedError

    async def _destroy_all(self) -> None:
        """Détruit tous les éléments."""
        for item_id in list(self._items.keys()):
            await self._destroy_item(item_id)

    async def _validate_item(self, item: Any) -> bool:
        """
        Valide un élément.

        Args:
            item: Élément à valider

        Returns:
            True si valide
        """
        return True

    async def acquire(self, timeout: Optional[int] = None) -> Any:
        """
        Acquiert un élément du pool.

        Args:
            timeout: Timeout

        Returns:
            Élément acquis
        """
        start_time = time.time()
        timeout = timeout or self.config.acquire_timeout

        while True:
            try:
                item_id = self._available.get(block=False)
                item = self._items.get(item_id)

                if not item:
                    continue

                if not await self._validate_item(item.item):
                    await self._destroy_item(item_id)
                    continue

                item.in_use = True
                item.last_used = datetime.now()

                self._stats.total_acquires += 1
                self._stats.in_use_items += 1
                self._stats.available_items -= 1

                acquire_time = time.time() - start_time
                self._stats.average_acquire_time = (
                    (self._stats.average_acquire_time * (self._stats.total_acquires - 1) + acquire_time)
                    / self._stats.total_acquires
                )
                if acquire_time > self._stats.maximum_acquire_time:
                    self._stats.maximum_acquire_time = acquire_time

                self._stats.updated_at = datetime.now()

                return item.item

            except queue.Empty:
                if len(self._items) < self.config.max_size:
                    try:
                        new_id = await self._create_item()
                        # Récupération immédiate du nouvel élément
                        new_item = self._items.get(new_id)
                        if new_item:
                            new_item.in_use = True
                            self._stats.total_acquires += 1
                            self._stats.in_use_items += 1
                            self._stats.updated_at = datetime.now()
                            return new_item.item
                    except Exception as e:
                        logger.error(f"Erreur lors de la création d'un élément: {e}")
                        self._stats.total_errors += 1

                # Attente
                try:
                    await asyncio.wait_for(
                        self._wait_for_available(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    self._stats.total_timeouts += 1
                    raise TimeoutError(f"Timeout lors de l'acquisition d'un élément du pool {self.config.name}")

    async def _wait_for_available(self) -> None:
        """Attend qu'un élément soit disponible."""
        while True:
            if not self._available.empty():
                return
            await asyncio.sleep(0.1)

    async def release(self, item: Any) -> None:
        """
        Libère un élément dans le pool.

        Args:
            item: Élément à libérer
        """
        async with self._lock:
            for item_id, pool_item in self._items.items():
                if pool_item.item == item and pool_item.in_use:
                    pool_item.in_use = False
                    pool_item.last_used = datetime.now()
                    self._available.put(item_id)
                    self._stats.total_releases += 1
                    self._stats.in_use_items -= 1
                    self._stats.available_items += 1
                    self._stats.updated_at = datetime.now()
                    return

        logger.warning(f"Élément non trouvé dans le pool {self.config.name}")

    @asynccontextmanager
    async def use(self, timeout: Optional[int] = None) -> AsyncGenerator[Any, None]:
        """
        Context manager pour l'utilisation d'un élément du pool.

        Args:
            timeout: Timeout

        Yields:
            Élément du pool
        """
        item = await self.acquire(timeout)
        try:
            yield item
        finally:
            await self.release(item)

    def get_stats(self) -> PoolStats:
        """
        Récupère les statistiques du pool.

        Returns:
            Statistiques du pool
        """
        return self._stats


# ============================================================================
# POOL DE CONNEXIONS
# ============================================================================

class ConnectionPool(BasePool):
    """
    Pool de connexions asynchrones.
    """

    def __init__(
        self,
        config: PoolConfig,
        connection_factory: Callable[[], Any],
        validator: Optional[Callable[[Any], bool]] = None
    ):
        """
        Initialise le pool de connexions.

        Args:
            config: Configuration du pool
            connection_factory: Fonction de création de connexion
            validator: Fonction de validation
        """
        super().__init__(config)
        self._connection_factory = connection_factory
        self._validator = validator

    async def _create_item(self) -> UUID:
        """Crée une nouvelle connexion."""
        try:
            conn = self._connection_factory()
            
            # Si c'est une connexion asynchrone, l'initialiser
            if asyncio.iscoroutine(conn):
                conn = await conn

            item_id = uuid4()
            pool_item = PoolItem(
                item_id=item_id,
                item=conn,
                created_at=datetime.now(),
                last_used=datetime.now(),
                in_use=False
            )

            self._items[item_id] = pool_item
            self._available.put(item_id)

            self._stats.total_items += 1
            self._stats.total_created += 1
            self._stats.available_items += 1
            self._stats.updated_at = datetime.now()

            return item_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de la connexion: {e}")
            raise

    async def _destroy_item(self, item_id: UUID) -> None:
        """Détruit une connexion."""
        if item_id in self._items:
            item = self._items[item_id]
            
            try:
                # Fermeture de la connexion
                if hasattr(item.item, 'close'):
                    if asyncio.iscoroutine(item.item.close()):
                        await item.item.close()
                    else:
                        item.item.close()
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture de la connexion: {e}")

            del self._items[item_id]
            
            self._stats.total_items -= 1
            self._stats.total_destroyed += 1
            self._stats.updated_at = datetime.now()

    async def _validate_item(self, item: Any) -> bool:
        """Valide une connexion."""
        if self._validator:
            try:
                result = self._validator(item)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return False
        return True


# ============================================================================
# POOL D'OBJETS
# ============================================================================

class ObjectPool(BasePool):
    """
    Pool d'objets génériques.
    """

    def __init__(
        self,
        config: PoolConfig,
        object_factory: Callable[[], Any],
        reset_func: Optional[Callable[[Any], Any]] = None,
        validator: Optional[Callable[[Any], bool]] = None
    ):
        """
        Initialise le pool d'objets.

        Args:
            config: Configuration du pool
            object_factory: Fonction de création d'objet
            reset_func: Fonction de réinitialisation
            validator: Fonction de validation
        """
        super().__init__(config)
        self._object_factory = object_factory
        self._reset_func = reset_func
        self._validator = validator

    async def _create_item(self) -> UUID:
        """Crée un nouvel objet."""
        try:
            obj = self._object_factory()
            
            if asyncio.iscoroutine(obj):
                obj = await obj

            item_id = uuid4()
            pool_item = PoolItem(
                item_id=item_id,
                item=obj,
                created_at=datetime.now(),
                last_used=datetime.now(),
                in_use=False
            )

            self._items[item_id] = pool_item
            self._available.put(item_id)

            self._stats.total_items += 1
            self._stats.total_created += 1
            self._stats.available_items += 1
            self._stats.updated_at = datetime.now()

            return item_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de l'objet: {e}")
            raise

    async def _destroy_item(self, item_id: UUID) -> None:
        """Détruit un objet."""
        if item_id in self._items:
            item = self._items[item_id]
            
            try:
                if hasattr(item.item, 'close'):
                    if asyncio.iscoroutine(item.item.close()):
                        await item.item.close()
                    else:
                        item.item.close()
            except Exception as e:
                logger.error(f"Erreur lors de la destruction de l'objet: {e}")

            del self._items[item_id]
            
            self._stats.total_items -= 1
            self._stats.total_destroyed += 1
            self._stats.updated_at = datetime.now()

    async def _validate_item(self, item: Any) -> bool:
        """Valide un objet."""
        if self._validator:
            try:
                result = self._validator(item)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return False
        return True

    async def release(self, item: Any) -> None:
        """Libère un objet dans le pool."""
        await super().release(item)
        
        # Réinitialisation de l'objet
        if self._reset_func and not self._running:
            try:
                result = self._reset_func(item)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Erreur lors de la réinitialisation de l'objet: {e}")


# ============================================================================
# POOL DE TÂCHES
# ============================================================================

class TaskPool(BasePool):
    """
    Pool de tâches asynchrones.
    """

    def __init__(
        self,
        config: PoolConfig,
        task_factory: Callable[[], Any]
    ):
        """
        Initialise le pool de tâches.

        Args:
            config: Configuration du pool
            task_factory: Fonction de création de tâche
        """
        super().__init__(config)
        self._task_factory = task_factory
        self._running_tasks: Set[asyncio.Task] = set()

    async def _create_item(self) -> UUID:
        """Crée une nouvelle tâche."""
        try:
            task = self._task_factory()
            
            if asyncio.iscoroutine(task):
                task = asyncio.create_task(task)

            item_id = uuid4()
            pool_item = PoolItem(
                item_id=item_id,
                item=task,
                created_at=datetime.now(),
                last_used=datetime.now(),
                in_use=False
            )

            self._items[item_id] = pool_item
            self._available.put(item_id)
            self._running_tasks.add(task)

            self._stats.total_items += 1
            self._stats.total_created += 1
            self._stats.available_items += 1
            self._stats.updated_at = datetime.now()

            return item_id

        except Exception as e:
            logger.error(f"Erreur lors de la création de la tâche: {e}")
            raise

    async def _destroy_item(self, item_id: UUID) -> None:
        """Détruit une tâche."""
        if item_id in self._items:
            item = self._items[item_id]
            
            try:
                if not item.item.done():
                    item.item.cancel()
                    try:
                        await item.item
                    except asyncio.CancelledError:
                        pass
                
                if item.item in self._running_tasks:
                    self._running_tasks.remove(item.item)
                    
            except Exception as e:
                logger.error(f"Erreur lors de la destruction de la tâche: {e}")

            del self._items[item_id]
            
            self._stats.total_items -= 1
            self._stats.total_destroyed += 1
            self._stats.updated_at = datetime.now()

    async def wait_all(self) -> None:
        """Attend que toutes les tâches soient terminées."""
        if self._running_tasks:
            await asyncio.gather(*self._running_tasks, return_exceptions=True)


# ============================================================================
# FACTORY DES POOLS
# ============================================================================

class PoolFactory:
    """
    Factory pour créer des pools.
    """

    @staticmethod
    def create_connection_pool(
        name: str,
        connection_factory: Callable[[], Any],
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: int = 300,
        acquire_timeout: int = 30,
        validator: Optional[Callable[[Any], bool]] = None
    ) -> ConnectionPool:
        """
        Crée un pool de connexions.

        Args:
            name: Nom du pool
            connection_factory: Fonction de création de connexion
            min_size: Taille minimale
            max_size: Taille maximale
            max_idle_time: Temps d'inactivité maximum
            acquire_timeout: Timeout d'acquisition
            validator: Fonction de validation

        Returns:
            Pool de connexions
        """
        config = PoolConfig(
            name=name,
            pool_type=PoolType.CONNECTION,
            min_size=min_size,
            max_size=max_size,
            max_idle_time=max_idle_time,
            acquire_timeout=acquire_timeout
        )
        return ConnectionPool(config, connection_factory, validator)

    @staticmethod
    def create_object_pool(
        name: str,
        object_factory: Callable[[], Any],
        min_size: int = 1,
        max_size: int = 10,
        max_idle_time: int = 300,
        acquire_timeout: int = 30,
        reset_func: Optional[Callable[[Any], Any]] = None,
        validator: Optional[Callable[[Any], bool]] = None
    ) -> ObjectPool:
        """
        Crée un pool d'objets.

        Args:
            name: Nom du pool
            object_factory: Fonction de création d'objet
            min_size: Taille minimale
            max_size: Taille maximale
            max_idle_time: Temps d'inactivité maximum
            acquire_timeout: Timeout d'acquisition
            reset_func: Fonction de réinitialisation
            validator: Fonction de validation

        Returns:
            Pool d'objets
        """
        config = PoolConfig(
            name=name,
            pool_type=PoolType.OBJECT,
            min_size=min_size,
            max_size=max_size,
            max_idle_time=max_idle_time,
            acquire_timeout=acquire_timeout
        )
        return ObjectPool(config, object_factory, reset_func, validator)

    @staticmethod
    def create_task_pool(
        name: str,
        task_factory: Callable[[], Any],
        max_size: int = 10
    ) -> TaskPool:
        """
        Crée un pool de tâches.

        Args:
            name: Nom du pool
            task_factory: Fonction de création de tâche
            max_size: Taille maximale

        Returns:
            Pool de tâches
        """
        config = PoolConfig(
            name=name,
            pool_type=PoolType.TASK,
            min_size=0,
            max_size=max_size
        )
        return TaskPool(config, task_factory)

    @staticmethod
    def create_redis_pool(
        name: str,
        redis_url: str,
        min_size: int = 1,
        max_size: int = 10,
        **kwargs
    ) -> ConnectionPool:
        """
        Crée un pool de connexions Redis.

        Args:
            name: Nom du pool
            redis_url: URL de connexion
            min_size: Taille minimale
            max_size: Taille maximale
            **kwargs: Arguments supplémentaires

        Returns:
            Pool de connexions Redis
        """
        async def redis_factory():
            return await aioredis.from_url(redis_url, **kwargs)

        return PoolFactory.create_connection_pool(
            name=name,
            connection_factory=redis_factory,
            min_size=min_size,
            max_size=max_size
        )

    @staticmethod
    def create_postgres_pool(
        name: str,
        dsn: str,
        min_size: int = 1,
        max_size: int = 10,
        **kwargs
    ) -> ConnectionPool:
        """
        Crée un pool de connexions PostgreSQL.

        Args:
            name: Nom du pool
            dsn: DSN de connexion
            min_size: Taille minimale
            max_size: Taille maximale
            **kwargs: Arguments supplémentaires

        Returns:
            Pool de connexions PostgreSQL
        """
        async def postgres_factory():
            return await asyncpg.create_pool(dsn, **kwargs)

        return PoolFactory.create_connection_pool(
            name=name,
            connection_factory=postgres_factory,
            min_size=min_size,
            max_size=max_size
        )

    @staticmethod
    def create_http_session_pool(
        name: str,
        min_size: int = 1,
        max_size: int = 10,
        **kwargs
    ) -> ObjectPool:
        """
        Crée un pool de sessions HTTP.

        Args:
            name: Nom du pool
            min_size: Taille minimale
            max_size: Taille maximale
            **kwargs: Arguments supplémentaires

        Returns:
            Pool de sessions HTTP
        """
        def session_factory():
            return aiohttp.ClientSession(**kwargs)

        def reset_session(session):
            if not session.closed:
                session.close()

        return PoolFactory.create_object_pool(
            name=name,
            object_factory=session_factory,
            min_size=min_size,
            max_size=max_size,
            reset_func=reset_session
        )


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_pool(
    name: str,
    pool_type: PoolType,
    min_size: int = 1,
    max_size: int = 10,
    **kwargs
) -> BasePool:
    """
    Crée un pool générique.

    Args:
        name: Nom du pool
        pool_type: Type de pool
        min_size: Taille minimale
        max_size: Taille maximale
        **kwargs: Arguments supplémentaires

    Returns:
        Pool créé
    """
    config = PoolConfig(
        name=name,
        pool_type=pool_type,
        min_size=min_size,
        max_size=max_size,
        **kwargs
    )
    
    if pool_type == PoolType.CONNECTION:
        return ConnectionPool(config, kwargs.get("connection_factory"))
    elif pool_type == PoolType.OBJECT:
        return ObjectPool(config, kwargs.get("object_factory"))
    elif pool_type == PoolType.TASK:
        return TaskPool(config, kwargs.get("task_factory"))
    else:
        raise ValueError(f"Type de pool non supporté: {pool_type}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PoolType",
    "PoolStatus",
    "PoolItem",
    "PoolStats",
    "PoolConfig",
    "BasePool",
    "ConnectionPool",
    "ObjectPool",
    "TaskPool",
    "PoolFactory",
    "create_pool"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation des pools."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT POOLS")
    print("=" * 60)

    # Pool d'objets
    print(f"\n📦 Création d'un pool d'objets...")
    
    class CustomObject:
        def __init__(self, value):
            self.value = value
            self.created_at = datetime.now()
        
        def close(self):
            pass

    object_pool = PoolFactory.create_object_pool(
        name="Test Object Pool",
        object_factory=lambda: CustomObject(42),
        min_size=2,
        max_size=5,
        max_idle_time=60
    )

    await object_pool.initialize()
    print(f"   Pool initialisé: {object_pool.config.name}")

    # Utilisation du pool
    print(f"\n🔧 Utilisation du pool...")
    async with object_pool.use() as obj:
        print(f"   Objet acquis: value={obj.value}, created_at={obj.created_at}")
        await asyncio.sleep(0.5)

    # Statistiques
    stats = object_pool.get_stats()
    print(f"\n📊 Statistiques du pool:")
    print(f"   Total items: {stats.total_items}")
    print(f"   Available: {stats.available_items}")
    print(f"   In use: {stats.in_use_items}")
    print(f"   Total acquires: {stats.total_acquires}")
    print(f"   Avg acquire time: {stats.average_acquire_time:.3f}s")

    # Pool de tâches
    print(f"\n⚡ Création d'un pool de tâches...")
    
    async def sample_task(value):
        await asyncio.sleep(1)
        return value * 2

    task_pool = PoolFactory.create_task_pool(
        name="Test Task Pool",
        task_factory=lambda: sample_task(21),
        max_size=3
    )

    await task_pool.initialize()
    
    # Exécution des tâches
    tasks = []
    for _ in range(3):
        async with task_pool.use() as task:
            tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    print(f"   Résultats: {results}")

    # Santé du pool
    print(f"\n❤️ Santé du pool:")
    print(f"   Statut: {object_pool._status.value}")
    print(f"   Taille: {len(object_pool._items)}")
    print(f"   Disponible: {object_pool._available.qsize()}")

    # Fermeture
    await object_pool.close()
    await task_pool.close()

    print("\n" + "=" * 60)
    print("Pools NEXUS opérationnels ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
