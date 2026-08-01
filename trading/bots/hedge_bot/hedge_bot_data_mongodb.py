# trading/bots/hedge_bot/hedge_bot_data_mongodb.py
# Advanced MongoDB Integration & Document Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot MongoDB Integration Module - Module d'intégration avancé avec MongoDB pour le Hedge Bot.
Gère le stockage de documents, les collections, les index, les agrégations,
les transactions et les requêtes performantes pour les données de hedging.
"""

import asyncio
import json
import time
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
import motor.motor_asyncio
import pymongo
from bson import ObjectId, json_util
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT, GEOSPHERE

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_mongodb")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class MongoDBIndexType(Enum):
    """Types d'index MongoDB."""
    SINGLE = "single"
    COMPOUND = "compound"
    TEXT = "text"
    GEOSPATIAL = "geospatial"
    HASHED = "hashed"
    WILDCARD = "wildcard"


class MongoDBCollectionType(Enum):
    """Types de collections MongoDB."""
    TIME_SERIES = "time_series"
    STANDARD = "standard"
    VIEW = "view"
    CAPPED = "capped"


class MongoDBReadPreference(Enum):
    """Préférences de lecture MongoDB."""
    PRIMARY = "primary"
    PRIMARY_PREFERRED = "primaryPreferred"
    SECONDARY = "secondary"
    SECONDARY_PREFERRED = "secondaryPreferred"
    NEAREST = "nearest"


# ============== DATA MODELS ==============

@dataclass
class MongoDBCollection:
    """Collection MongoDB."""
    collection_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    database: str = "nexus"
    collection_type: MongoDBCollectionType = MongoDBCollectionType.STANDARD
    indexes: List[Dict[str, Any]] = field(default_factory=list)
    schema: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    document_count: int = 0
    size_bytes: int = 0
    avg_document_size: int = 0


@dataclass
class MongoDBQuery:
    """Requête MongoDB."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    collection: str = ""
    database: str = "nexus"
    filter: Dict[str, Any] = field(default_factory=dict)
    projection: Optional[Dict[str, Any]] = None
    sort: List[Tuple[str, int]] = field(default_factory=list)
    limit: int = 100
    skip: int = 0
    read_preference: MongoDBReadPreference = MongoDBReadPreference.PRIMARY
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class MongoDBResult:
    """Résultat de requête MongoDB."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    query_id: str = ""
    documents: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0
    total_count: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class MongoDBEngineInterface(ABC):
    """Interface abstraite pour le moteur MongoDB."""
    
    @abstractmethod
    async def create_collection(self, collection: MongoDBCollection) -> bool:
        """Crée une collection MongoDB."""
        pass
    
    @abstractmethod
    async def insert_one(self, collection: str, document: Dict) -> str:
        """Insère un document."""
        pass
    
    @abstractmethod
    async def find(self, query: MongoDBQuery) -> MongoDBResult:
        """Recherche des documents."""
        pass
    
    @abstractmethod
    async def aggregate(self, collection: str, pipeline: List[Dict]) -> MongoDBResult:
        """Exécute une agrégation."""
        pass


# ============== IMPLÉMENTATION ==============

class MongoDBEngine(MongoDBEngineInterface):
    """
    Moteur MongoDB avancé pour le Hedge Bot.
    Gère le stockage de documents, les index, les agrégations et les transactions.
    """
    
    def __init__(
        self,
        connection_string: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.connection_string = connection_string
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Client MongoDB
        self._client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        
        # Gestion des collections
        self._collections: Dict[str, MongoDBCollection] = {}
        self._collections_lock = threading.RLock()
        
        # Cache des index
        self._index_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_lock = threading.RLock()
        
        # Sessions pour transactions
        self._session: Optional[motor.motor_asyncio.AsyncIOMotorClientSession] = None
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "collections_created": 0,
            "documents_inserted": 0,
            "documents_found": 0,
            "aggregations_executed": 0,
            "transactions_committed": 0,
            "avg_query_time_ms": 0.0,
            "avg_insert_time_ms": 0.0,
            "avg_aggregation_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("MongoDBEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_database": "nexus",
            "max_pool_size": 100,
            "min_pool_size": 10,
            "max_idle_time_ms": 60000,
            "retry_writes": True,
            "retry_reads": True,
            "w": 1,  # Write concern
            "j": False,  # Journal
            "read_preference": MongoDBReadPreference.PRIMARY.value,
            "enable_indexing": True,
            "enable_schema_validation": False,
            "auto_create_collections": True,
            "query_timeout": 30000,
            "batch_size": 1000,
            "max_document_size": 16 * 1024 * 1024  # 16 MB
        }
    
    async def start(self) -> None:
        """Démarre le moteur MongoDB."""
        logger.info("MongoDBEngine starting...")
        self._is_running = True
        
        # Connexion à MongoDB
        self._client = motor.motor_asyncio.AsyncIOMotorClient(
            self.connection_string,
            maxPoolSize=self.config["max_pool_size"],
            minPoolSize=self.config["min_pool_size"],
            maxIdleTimeMS=self.config["max_idle_time_ms"],
            retryWrites=self.config["retry_writes"],
            retryReads=self.config["retry_reads"],
            w=self.config["w"],
            journal=self.config["j"],
            readPreference=self.config["read_preference"]
        )
        
        # Vérification de la connexion
        await self._client.admin.command("ping")
        logger.info("Connected to MongoDB")
        
        # Chargement des collections existantes
        await self._load_collections()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._index_manager())
        asyncio.create_task(self._stats_collector())
        asyncio.create_task(self._cache_cleaner())
        
        logger.info("MongoDBEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur MongoDB."""
        logger.info("MongoDBEngine stopping...")
        self._is_running = False
        
        # Fermeture du client
        if self._client:
            self._client.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MongoDBEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_collection(self, collection: MongoDBCollection) -> bool:
        """Crée une collection MongoDB."""
        with self._collections_lock:
            self._collections[collection.collection_id] = collection
            self._stats["collections_created"] += 1
        
        try:
            # Obtention de la base de données
            db = self._client[collection.database]
            
            # Création de la collection
            await db.create_collection(
                collection.name,
                **self._get_collection_options(collection)
            )
            
            # Création des index
            if self.config["enable_indexing"] and collection.indexes:
                await self._create_indexes(collection)
            
            # Validation du schéma
            if self.config["enable_schema_validation"] and collection.validation:
                await self._set_validation(collection)
            
            logger.info(f"Collection created: {collection.database}.{collection.name}")
            return True
            
        except Exception as e:
            logger.error(f"Collection creation error: {e}")
            return False
    
    async def insert_one(self, collection: str, document: Dict) -> str:
        """Insère un document."""
        start_time = time.time()
        self._stats["documents_inserted"] += 1
        
        try:
            # Obtention de la collection
            coll = await self._get_collection(collection)
            
            # Insertion
            result = await coll.insert_one(document)
            
            # Mise à jour des statistiques
            insert_time = (time.time() - start_time) * 1000
            self._stats["avg_insert_time_ms"] = (
                self._stats["avg_insert_time_ms"] * 0.9 + insert_time * 0.1
            )
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Insert error: {e}")
            raise
    
    async def find(self, query: MongoDBQuery) -> MongoDBResult:
        """Recherche des documents."""
        start_time = time.time()
        self._stats["documents_found"] += 1
        
        try:
            # Obtention de la collection
            coll = await self._get_collection(query.collection)
            
            # Construction de la requête
            cursor = coll.find(
                query.filter,
                projection=query.projection,
                limit=query.limit,
                skip=query.skip,
                sort=query.sort,
                read_preference=query.read_preference.value
            )
            
            # Exécution
            documents = await cursor.to_list(length=query.limit)
            
            # Comptage total
            total_count = await coll.count_documents(query.filter)
            
            # Création du résultat
            result = MongoDBResult(
                query_id=query.query_id,
                documents=documents,
                count=len(documents),
                total_count=total_count,
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
            # Mise à jour des statistiques
            self._stats["avg_query_time_ms"] = (
                self._stats["avg_query_time_ms"] * 0.9 + result.execution_time_ms * 0.1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Find error: {e}")
            return MongoDBResult(
                query_id=query.query_id,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def aggregate(self, collection: str, pipeline: List[Dict]) -> MongoDBResult:
        """Exécute une agrégation."""
        start_time = time.time()
        self._stats["aggregations_executed"] += 1
        
        try:
            # Obtention de la collection
            coll = await self._get_collection(collection)
            
            # Exécution de l'agrégation
            cursor = coll.aggregate(pipeline)
            documents = await cursor.to_list(length=None)
            
            # Création du résultat
            result = MongoDBResult(
                query_id=str(uuid.uuid4()),
                documents=documents,
                count=len(documents),
                total_count=len(documents),
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
            # Mise à jour des statistiques
            self._stats["avg_aggregation_time_ms"] = (
                self._stats["avg_aggregation_time_ms"] * 0.9 + result.execution_time_ms * 0.1
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Aggregation error: {e}")
            return MongoDBResult(
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    # ========== MÉTHODES PRIVÉES - COLLECTIONS ==========
    
    async def _get_collection(self, name: str) -> motor.motor_asyncio.AsyncIOMotorCollection:
        """Obtient une collection."""
        db = self._client[self.config["default_database"]]
        return db[name]
    
    def _get_collection_options(self, collection: MongoDBCollection) -> Dict[str, Any]:
        """Obtient les options de création de collection."""
        options = {}
        
        if collection.collection_type == MongoDBCollectionType.TIME_SERIES:
            options["timeseries"] = {
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "seconds"
            }
        
        elif collection.collection_type == MongoDBCollectionType.CAPPED:
            options["capped"] = True
            options["size"] = self.config.get("capped_size", 10 * 1024 * 1024)
            options["max"] = self.config.get("capped_max", 10000)
        
        elif collection.collection_type == MongoDBCollectionType.VIEW:
            options["viewOn"] = collection.metadata.get("view_on", "")
            options["pipeline"] = collection.metadata.get("pipeline", [])
        
        return options
    
    async def _create_indexes(self, collection: MongoDBCollection) -> None:
        """Crée les index d'une collection."""
        try:
            coll = await self._get_collection(collection.name)
            
            index_models = []
            for index_spec in collection.indexes:
                keys = index_spec.get("keys", {})
                options = index_spec.get("options", {})
                
                # Construction de l'index
                index_model = IndexModel(keys, **options)
                index_models.append(index_model)
            
            if index_models:
                await coll.create_indexes(index_models)
                logger.info(f"Indexes created for {collection.name}: {len(index_models)}")
            
        except Exception as e:
            logger.error(f"Index creation error: {e}")
    
    async def _set_validation(self, collection: MongoDBCollection) -> None:
        """Définit la validation de schéma."""
        try:
            db = self._client[collection.database]
            await db.command({
                "collMod": collection.name,
                "validator": collection.validation,
                "validationLevel": "strict",
                "validationAction": "error"
            })
            
            logger.info(f"Validation set for {collection.name}")
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
    
    # ========== MÉTHODES PRIVÉES - TRANSACTIONS ==========
    
    async def start_transaction(self) -> None:
        """Démarre une transaction."""
        self._session = await self._client.start_session()
        self._session.start_transaction()
        logger.debug("Transaction started")
    
    async def commit_transaction(self) -> None:
        """Valide une transaction."""
        if self._session:
            await self._session.commit_transaction()
            self._stats["transactions_committed"] += 1
            logger.debug("Transaction committed")
            self._session = None
    
    async def abort_transaction(self) -> None:
        """Annule une transaction."""
        if self._session:
            await self._session.abort_transaction()
            logger.debug("Transaction aborted")
            self._session = None
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _index_manager(self) -> None:
        """Gère les index périodiquement."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Vérification des index pour toutes les collections
                with self._collections_lock:
                    for collection in self._collections.values():
                        if self.config["enable_indexing"] and collection.indexes:
                            await self._ensure_indexes(collection)
                
            except Exception as e:
                logger.error(f"Index manager error: {e}")
    
    async def _ensure_indexes(self, collection: MongoDBCollection) -> None:
        """Vérifie et recrée les index si nécessaire."""
        try:
            coll = await self._get_collection(collection.name)
            
            # Récupération des index existants
            existing_indexes = await coll.index_information()
            existing_names = set(existing_indexes.keys())
            
            # Index requis
            required_indexes = [idx.get("options", {}).get("name") for idx in collection.indexes]
            required_names = set(required_indexes) - {"_id_"}
            
            # Suppression des index obsolètes
            for name in existing_names - required_names:
                if name != "_id_":
                    await coll.drop_index(name)
                    logger.debug(f"Dropped index: {name}")
            
            # Création des index manquants
            await self._create_indexes(collection)
            
        except Exception as e:
            logger.error(f"Ensure indexes error: {e}")
    
    async def _stats_collector(self) -> None:
        """Collecte les statistiques des collections."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                for collection in self._collections.values():
                    coll = await self._get_collection(collection.name)
                    
                    # Statistiques de la collection
                    stats = await coll.aggregate([
                        {"$collStats": {"storageStats": {}}}
                    ]).to_list(length=1)
                    
                    if stats:
                        storage = stats[0].get("storageStats", {})
                        collection.document_count = storage.get("count", 0)
                        collection.size_bytes = storage.get("size", 0)
                        collection.avg_document_size = storage.get("avgObjSize", 0)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "mongodb:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Stats collector error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    # Nettoyage du cache des index
                    if len(self._index_cache) > 100:
                        keys = list(self._index_cache.keys())
                        for key in keys[:len(self._index_cache) - 100]:
                            del self._index_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_collections(self) -> None:
        """Charge les collections existantes."""
        try:
            db = self._client[self.config["default_database"]]
            
            # Liste des collections
            collection_names = await db.list_collection_names()
            
            for name in collection_names:
                # Création d'un objet collection
                collection = MongoDBCollection(
                    name=name,
                    database=self.config["default_database"],
                    collection_type=MongoDBCollectionType.STANDARD
                )
                
                # Récupération des index
                if self.config["enable_indexing"]:
                    coll = db[name]
                    index_info = await coll.index_information()
                    collection.indexes = [
                        {"keys": info.get("key", {}), "options": info}
                        for info in index_info.values()
                    ]
                
                with self._collections_lock:
                    self._collections[collection.collection_id] = collection
                self._stats["collections_created"] += 1
            
            logger.info(f"Loaded {len(collection_names)} collections")
            
        except Exception as e:
            logger.error(f"Load collections error: {e}")
    
    # ========== MÉTHODES UTILITAIRES ==========
    
    def _format_object_id(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Formate un ObjectId MongoDB en chaîne."""
        if "_id" in doc and isinstance(doc["_id"], ObjectId):
            doc["_id"] = str(doc["_id"])
        return doc
    
    async def create_ttl_index(self, collection: str, field: str, ttl_seconds: int) -> bool:
        """Crée un index TTL."""
        try:
            coll = await self._get_collection(collection)
            await coll.create_index(
                [(field, ASCENDING)],
                expireAfterSeconds=ttl_seconds
            )
            logger.info(f"TTL index created on {collection}.{field} ({ttl_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"TTL index error: {e}")
            return False
    
    async def create_text_index(self, collection: str, fields: List[str]) -> bool:
        """Crée un index text."""
        try:
            coll = await self._get_collection(collection)
            await coll.create_index([(field, TEXT) for field in fields])
            logger.info(f"Text index created on {collection}: {fields}")
            return True
        except Exception as e:
            logger.error(f"Text index error: {e}")
            return False
    
    async def create_geospatial_index(self, collection: str, field: str) -> bool:
        """Crée un index géospatial."""
        try:
            coll = await self._get_collection(collection)
            await coll.create_index([(field, GEOSPHERE)])
            logger.info(f"Geospatial index created on {collection}.{field}")
            return True
        except Exception as e:
            logger.error(f"Geospatial index error: {e}")
            return False
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_collection(self, collection_id: str) -> Optional[MongoDBCollection]:
        """Récupère une collection."""
        with self._collections_lock:
            return self._collections.get(collection_id)
    
    async def get_collections(self) -> List[MongoDBCollection]:
        """Récupère les collections."""
        with self._collections_lock:
            return list(self._collections.values())
    
    async def find_one(self, collection: str, filter: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Trouve un document."""
        try:
            coll = await self._get_collection(collection)
            doc = await coll.find_one(filter)
            if doc:
                return self._format_object_id(doc)
            return None
        except Exception as e:
            logger.error(f"Find one error: {e}")
            return None
    
    async def update_one(self, collection: str, filter: Dict, update: Dict) -> int:
        """Met à jour un document."""
        try:
            coll = await self._get_collection(collection)
            result = await coll.update_one(filter, update)
            return result.modified_count
        except Exception as e:
            logger.error(f"Update error: {e}")
            return 0
    
    async def delete_one(self, collection: str, filter: Dict) -> int:
        """Supprime un document."""
        try:
            coll = await self._get_collection(collection)
            result = await coll.delete_one(filter)
            return result.deleted_count
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return 0
    
    async def bulk_insert(self, collection: str, documents: List[Dict]) -> int:
        """Insertion en masse."""
        try:
            coll = await self._get_collection(collection)
            result = await coll.insert_many(documents)
            self._stats["documents_inserted"] += len(result.inserted_ids)
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"Bulk insert error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._collections_lock:
            self._stats["total_collections"] = len(self._collections)
        
        return self._stats.copy()


# ============== MONGO QUERY BUILDER ==============

class MongoQueryBuilder:
    """
    Constructeur de requêtes MongoDB.
    Facilite la création de requêtes complexes.
    """
    
    def __init__(self):
        self._query = {}
        self._projection = {}
        self._sort = []
        self._limit = 0
        self._skip = 0
    
    def filter(self, filter: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Définit le filtre."""
        self._query = filter
        return self
    
    def eq(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute une égalité."""
        self._query[field] = value
        return self
    
    def ne(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute une inégalité."""
        self._query[field] = {"$ne": value}
        return self
    
    def gt(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute un supérieur à."""
        self._query[field] = {"$gt": value}
        return self
    
    def gte(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute un supérieur ou égal."""
        self._query[field] = {"$gte": value}
        return self
    
    def lt(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute un inférieur à."""
        self._query[field] = {"$lt": value}
        return self
    
    def lte(self, field: str, value: Any) -> 'MongoQueryBuilder':
        """Ajoute un inférieur ou égal."""
        self._query[field] = {"$lte": value}
        return self
    
    def in_(self, field: str, values: List[Any]) -> 'MongoQueryBuilder':
        """Ajoute un IN."""
        self._query[field] = {"$in": values}
        return self
    
    def nin(self, field: str, values: List[Any]) -> 'MongoQueryBuilder':
        """Ajoute un NOT IN."""
        self._query[field] = {"$nin": values}
        return self
    
    def exists(self, field: str, exists: bool = True) -> 'MongoQueryBuilder':
        """Ajoute un EXISTS."""
        self._query[field] = {"$exists": exists}
        return self
    
    def regex(self, field: str, pattern: str) -> 'MongoQueryBuilder':
        """Ajoute une expression régulière."""
        self._query[field] = {"$regex": pattern}
        return self
    
    def between(self, field: str, min_val: Any, max_val: Any) -> 'MongoQueryBuilder':
        """Ajoute un BETWEEN."""
        self._query[field] = {"$gte": min_val, "$lte": max_val}
        return self
    
    def projection(self, fields: Dict[str, int]) -> 'MongoQueryBuilder':
        """Définit la projection."""
        self._projection = fields
        return self
    
    def include(self, *fields: str) -> 'MongoQueryBuilder':
        """Inclut des champs."""
        for field in fields:
            self._projection[field] = 1
        return self
    
    def exclude(self, *fields: str) -> 'MongoQueryBuilder':
        """Exclut des champs."""
        for field in fields:
            self._projection[field] = 0
        return self
    
    def sort(self, field: str, direction: int = ASCENDING) -> 'MongoQueryBuilder':
        """Définit le tri."""
        self._sort.append((field, direction))
        return self
    
    def limit(self, limit: int) -> 'MongoQueryBuilder':
        """Définit la limite."""
        self._limit = limit
        return self
    
    def skip(self, skip: int) -> 'MongoQueryBuilder':
        """Définit le skip."""
        self._skip = skip
        return self
    
    def build(self) -> Dict[str, Any]:
        """Construit la requête."""
        return {
            "filter": self._query,
            "projection": self._projection,
            "sort": self._sort,
            "limit": self._limit,
            "skip": self._skip
        }


# ============== FACTORY ==============

class MongoDBFactory:
    """Factory pour créer des composants MongoDB."""
    
    @staticmethod
    async def create_engine(
        connection_string: str,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MongoDBEngine:
        """Crée un moteur MongoDB."""
        engine = MongoDBEngine(
            connection_string=connection_string,
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_query_builder() -> MongoQueryBuilder:
        """Crée un constructeur de requêtes."""
        return MongoQueryBuilder()


# ============== EXPORT ==============

__all__ = [
    "MongoDBIndexType",
    "MongoDBCollectionType",
    "MongoDBReadPreference",
    "MongoDBCollection",
    "MongoDBQuery",
    "MongoDBResult",
    "MongoDBEngineInterface",
    "MongoDBEngine",
    "MongoQueryBuilder",
    "MongoDBFactory"
]
