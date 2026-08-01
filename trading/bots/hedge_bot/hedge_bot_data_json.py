# trading/bots/hedge_bot/hedge_bot_data_json.py
# Advanced JSON Data Management & Schema Validation Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot JSON Data Module - Module avancé de gestion des données JSON et de validation de schéma
pour le Hedge Bot. Gère le stockage JSON, la validation de schéma, la transformation,
le querying avancé, la compression et l'optimisation des données.
"""

import asyncio
import json
import jsonschema
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import zlib
import base64
import threading
import concurrent.futures
import hashlib
import re
from collections import defaultdict, deque
import pandas as pd
import numpy as np

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_json")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class JSONSchemaVersion(Enum):
    """Versions de schéma JSON."""
    DRAFT_4 = "http://json-schema.org/draft-04/schema#"
    DRAFT_6 = "http://json-schema.org/draft-06/schema#"
    DRAFT_7 = "http://json-schema.org/draft-07/schema#"
    DRAFT_2019_09 = "https://json-schema.org/draft/2019-09/schema#"
    DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema#"


class JSONPathType(Enum):
    """Types de chemin JSON."""
    DOT = "dot"          # $.property.subproperty
    BRACKET = "bracket"  # $['property']['subproperty']
    MIXED = "mixed"      # Mixte
    RECURSIVE = "recursive"  # Recursif (..)


class JSONCompression(Enum):
    """Méthodes de compression JSON."""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZMA = "lzma"
    ZSTD = "zstd"


# ============== DATA MODELS ==============

@dataclass
class JSONSchema:
    """Schéma JSON."""
    schema_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: JSONSchemaVersion = JSONSchemaVersion.DRAFT_7
    schema: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    definitions: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "schema_id": self.schema_id,
            "name": self.name,
            "description": self.description,
            "version": self.version.value,
            "schema": self.schema,
            "required": self.required,
            "definitions": self.definitions,
            "examples": self.examples,
            "metadata": self.metadata,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "active": self.active
        }


@dataclass
class JSONDocument:
    """Document JSON."""
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    collection: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    schema_id: Optional[str] = None
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    compressed: bool = False
    size_bytes: int = 0
    hash: Optional[str] = None


@dataclass
class JSONQuery:
    """Requête JSON."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    collection: str = ""
    path: str = ""
    path_type: JSONPathType = JSONPathType.DOT
    value: Any = None
    operator: str = "eq"  # eq, ne, gt, gte, lt, lte, in, nin, contains, regex
    filter: Dict[str, Any] = field(default_factory=dict)
    sort: List[Tuple[str, str]] = field(default_factory=list)
    limit: int = 100
    offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class JSONEngineInterface(ABC):
    """Interface abstraite pour le moteur JSON."""
    
    @abstractmethod
    async def create_schema(self, schema: JSONSchema) -> str:
        """Crée un schéma JSON."""
        pass
    
    @abstractmethod
    async def validate(self, data: Dict[str, Any], schema_id: str) -> bool:
        """Valide des données contre un schéma."""
        pass
    
    @abstractmethod
    async def insert(self, document: JSONDocument) -> str:
        """Insère un document JSON."""
        pass
    
    @abstractmethod
    async def query(self, query: JSONQuery) -> List[JSONDocument]:
        """Exécute une requête JSON."""
        pass


# ============== IMPLÉMENTATION ==============

class JSONEngine(JSONEngineInterface):
    """
    Moteur JSON avancé pour le Hedge Bot.
    Gère le stockage JSON, la validation de schéma et les requêtes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des schémas
        self._schemas: Dict[str, JSONSchema] = {}
        self._schemas_lock = threading.RLock()
        
        # Gestion des collections
        self._collections: Dict[str, List[JSONDocument]] = {}
        self._collections_lock = threading.RLock()
        
        # Index des collections
        self._indexes: Dict[str, Dict[str, Set[str]]] = {}
        self._indexes_lock = threading.RLock()
        
        # Cache des validations
        self._validation_cache: Dict[str, bool] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "schemas_created": 0,
            "documents_inserted": 0,
            "queries_executed": 0,
            "validations_performed": 0,
            "validations_passed": 0,
            "validations_failed": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("JSONEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_schema_version": JSONSchemaVersion.DRAFT_7,
            "max_document_size": 10 * 1024 * 1024,  # 10 MB
            "enable_validation": True,
            "enable_compression": True,
            "compression_threshold": 1024,  # 1 KB
            "default_compression": JSONCompression.ZLIB,
            "enable_indexing": True,
            "enable_caching": True,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "max_query_results": 1000,
            "default_collection": "default"
        }
    
    async def start(self) -> None:
        """Démarre le moteur JSON."""
        logger.info("JSONEngine starting...")
        self._is_running = True
        
        # Chargement des schémas existants
        await self._load_schemas()
        
        # Chargement des collections existantes
        await self._load_collections()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("JSONEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur JSON."""
        logger.info("JSONEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des données
        await self._save_data()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("JSONEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def create_schema(self, schema: JSONSchema) -> str:
        """Crée un schéma JSON."""
        # Validation du schéma
        try:
            jsonschema.Draft7Validator(schema.schema)
        except Exception as e:
            raise ValueError(f"Invalid JSON schema: {e}")
        
        with self._schemas_lock:
            self._schemas[schema.schema_id] = schema
            self._stats["schemas_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"json:schema:{schema.schema_id}",
                schema.to_dict(),
                DataType.SCHEMA
            )
        
        logger.info(f"JSON schema created: {schema.name} (id={schema.schema_id})")
        return schema.schema_id
    
    async def validate(self, data: Dict[str, Any], schema_id: str) -> bool:
        """Valide des données contre un schéma."""
        self._stats["validations_performed"] += 1
        
        # Vérification du cache
        cache_key = self._compute_validation_cache_key(data, schema_id)
        if self.config["enable_caching"] and cache_key in self._validation_cache:
            self._stats["cache_hits"] += 1
            return self._validation_cache[cache_key]
        
        self._stats["cache_misses"] += 1
        
        # Récupération du schéma
        with self._schemas_lock:
            schema = self._schemas.get(schema_id)
            if not schema:
                raise ValueError(f"Schema {schema_id} not found")
        
        try:
            # Validation
            validator = jsonschema.Draft7Validator(schema.schema)
            validator.validate(data)
            
            self._stats["validations_passed"] += 1
            
            # Mise en cache
            if self.config["enable_caching"]:
                with self._cache_lock:
                    if len(self._validation_cache) < self.config["cache_size"]:
                        self._validation_cache[cache_key] = True
            
            return True
            
        except jsonschema.ValidationError as e:
            self._stats["validations_failed"] += 1
            logger.debug(f"Validation error: {e}")
            
            # Mise en cache négative
            if self.config["enable_caching"]:
                with self._cache_lock:
                    if len(self._validation_cache) < self.config["cache_size"]:
                        self._validation_cache[cache_key] = False
            
            return False
    
    async def insert(self, document: JSONDocument) -> str:
        """Insère un document JSON."""
        # Validation
        if document.schema_id:
            valid = await self.validate(document.data, document.schema_id)
            if not valid:
                raise ValueError("Document validation failed")
        
        # Compression
        if self.config["enable_compression"]:
            doc_size = len(json.dumps(document.data))
            if doc_size > self.config["compression_threshold"]:
                document.compressed = True
                document.data = self._compress(document.data)
        
        # Hachage
        document.hash = hashlib.md5(json.dumps(document.data).encode()).hexdigest()
        document.size_bytes = len(json.dumps(document.data))
        
        # Insertion
        collection = document.collection or self.config["default_collection"]
        
        with self._collections_lock:
            if collection not in self._collections:
                self._collections[collection] = []
            self._collections[collection].append(document)
            self._stats["documents_inserted"] += 1
        
        # Indexation
        if self.config["enable_indexing"]:
            await self._index_document(collection, document)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"json:doc:{document.document_id}",
                document.to_dict(),
                DataType.DOCUMENT
            )
        
        logger.debug(f"Document inserted: {document.document_id} collection={collection}")
        return document.document_id
    
    async def query(self, query: JSONQuery) -> List[JSONDocument]:
        """Exécute une requête JSON."""
        self._stats["queries_executed"] += 1
        
        collection = query.collection or self.config["default_collection"]
        results = []
        
        with self._collections_lock:
            docs = self._collections.get(collection, [])
        
        # Filtrage
        for doc in docs:
            if self._match_document(doc, query):
                results.append(doc)
        
        # Tri
        if query.sort:
            for field, direction in reversed(query.sort):
                reverse = direction.lower() == "desc"
                results.sort(key=lambda d: self._get_json_value(d.data, field), reverse=reverse)
        
        # Limitation
        if query.limit > 0:
            results = results[query.offset:query.offset + query.limit]
        elif query.limit == 0:
            results = results[query.offset:]
        
        return results
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _compress(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compresse des données JSON."""
        json_str = json.dumps(data)
        compressed = zlib.compress(json_str.encode())
        return {
            "__compressed": True,
            "__data": base64.b64encode(compressed).decode()
        }
    
    def _decompress(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Décompresse des données JSON."""
        if data.get("__compressed"):
            compressed = base64.b64decode(data["__data"])
            decompressed = zlib.decompress(compressed)
            return json.loads(decompressed.decode())
        return data
    
    def _get_json_value(self, data: Dict[str, Any], path: str) -> Any:
        """Récupère une valeur par chemin JSON."""
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _match_document(self, doc: JSONDocument, query: JSONQuery) -> bool:
        """Vérifie si un document correspond à une requête."""
        data = self._decompress(doc.data) if doc.compressed else doc.data
        
        # Filtrage par valeur
        if query.path:
            value = self._get_json_value(data, query.path)
            
            if query.operator == "eq":
                return value == query.value
            elif query.operator == "ne":
                return value != query.value
            elif query.operator == "gt":
                return value > query.value
            elif query.operator == "gte":
                return value >= query.value
            elif query.operator == "lt":
                return value < query.value
            elif query.operator == "lte":
                return value <= query.value
            elif query.operator == "in":
                return value in query.value
            elif query.operator == "nin":
                return value not in query.value
            elif query.operator == "contains":
                return query.value in str(value)
            elif query.operator == "regex":
                return bool(re.search(query.value, str(value)))
        
        # Filtrage par schéma
        if query.filter:
            for key, value in query.filter.items():
                doc_value = self._get_json_value(data, key)
                if doc_value != value:
                    return False
        
        return True
    
    def _compute_validation_cache_key(self, data: Dict[str, Any], schema_id: str) -> str:
        """Calcule une clé de cache de validation."""
        data_hash = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        return f"{schema_id}:{data_hash}"
    
    async def _index_document(self, collection: str, doc: JSONDocument) -> None:
        """Indexe un document."""
        data = self._decompress(doc.data) if doc.compressed else doc.data
        
        with self._indexes_lock:
            if collection not in self._indexes:
                self._indexes[collection] = {}
            
            # Indexation des champs simples
            for key, value in data.items():
                if isinstance(value, (str, int, float, bool)):
                    if key not in self._indexes[collection]:
                        self._indexes[collection][key] = set()
                    
                    index_key = f"{key}:{str(value)}"
                    self._indexes[collection][key].add(index_key)
    
    # ========== MÉTHODES PRIVÉES - CHARGEMENT ==========
    
    async def _load_schemas(self) -> None:
        """Charge les schémas existants."""
        try:
            if self.data_manager:
                schemas_data = await self.data_manager.retrieve(
                    "json:schemas",
                    DataType.SCHEMA
                )
                
                if schemas_data:
                    for schema_dict in schemas_data:
                        schema = self._deserialize_schema(schema_dict)
                        if schema:
                            with self._schemas_lock:
                                self._schemas[schema.schema_id] = schema
            
            logger.info(f"Loaded {len(self._schemas)} JSON schemas")
            
        except Exception as e:
            logger.error(f"Load schemas error: {e}")
    
    async def _load_collections(self) -> None:
        """Charge les collections existantes."""
        try:
            if self.data_manager:
                docs_data = await self.data_manager.retrieve(
                    "json:documents",
                    DataType.DOCUMENT
                )
                
                if docs_data:
                    for doc_dict in docs_data:
                        doc = self._deserialize_document(doc_dict)
                        if doc:
                            collection = doc.collection or self.config["default_collection"]
                            with self._collections_lock:
                                if collection not in self._collections:
                                    self._collections[collection] = []
                                self._collections[collection].append(doc)
            
            logger.info(f"Loaded {sum(len(v) for v in self._collections.values())} documents")
            
        except Exception as e:
            logger.error(f"Load collections error: {e}")
    
    def _deserialize_schema(self, data: Dict) -> Optional[JSONSchema]:
        """Désérialise un schéma."""
        try:
            return JSONSchema(
                schema_id=data.get("schema_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                description=data.get("description", ""),
                version=JSONSchemaVersion(data.get("version", JSONSchemaVersion.DRAFT_7.value)),
                schema=data.get("schema", {}),
                required=data.get("required", []),
                definitions=data.get("definitions", {}),
                examples=data.get("examples", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing schema: {e}")
            return None
    
    def _deserialize_document(self, data: Dict) -> Optional[JSONDocument]:
        """Désérialise un document."""
        try:
            return JSONDocument(
                document_id=data.get("document_id", str(uuid.uuid4())),
                collection=data.get("collection", ""),
                data=data.get("data", {}),
                schema_id=data.get("schema_id"),
                version=data.get("version", 1),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                compressed=data.get("compressed", False),
                size_bytes=data.get("size_bytes", 0),
                hash=data.get("hash")
            )
        except Exception as e:
            logger.error(f"Error deserializing document: {e}")
            return None
    
    async def _save_data(self) -> None:
        """Sauvegarde les données."""
        try:
            if self.data_manager:
                # Sauvegarde des schémas
                with self._schemas_lock:
                    for schema in self._schemas.values():
                        await self.data_manager.store(
                            f"json:schema:{schema.schema_id}",
                            schema.to_dict(),
                            DataType.SCHEMA
                        )
                
                # Sauvegarde des documents
                with self._collections_lock:
                    for docs in self._collections.values():
                        for doc in docs:
                            await self.data_manager.store(
                                f"json:doc:{doc.document_id}",
                                doc.to_dict(),
                                DataType.DOCUMENT
                            )
            
            logger.info("Data saved")
            
        except Exception as e:
            logger.error(f"Save data error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._validation_cache) > self.config["cache_size"]:
                        keys = list(self._validation_cache.keys())
                        for key in keys[:len(self._validation_cache) - self.config["cache_size"]]:
                            del self._validation_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._schemas_lock:
                    self._stats["total_schemas"] = len(self._schemas)
                with self._collections_lock:
                    self._stats["total_documents"] = sum(len(v) for v in self._collections.values())
                    self._stats["collections"] = len(self._collections)
                with self._indexes_lock:
                    self._stats["indexes"] = sum(len(v) for v in self._indexes.values())
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "json:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_schema(self, schema_id: str) -> Optional[JSONSchema]:
        """Récupère un schéma."""
        with self._schemas_lock:
            return self._schemas.get(schema_id)
    
    async def get_schemas(self) -> List[JSONSchema]:
        """Récupère les schémas."""
        with self._schemas_lock:
            return list(self._schemas.values())
    
    async def get_document(self, document_id: str) -> Optional[JSONDocument]:
        """Récupère un document."""
        with self._collections_lock:
            for docs in self._collections.values():
                for doc in docs:
                    if doc.document_id == document_id:
                        return doc
        return None
    
    async def get_collections(self) -> List[str]:
        """Récupère les collections."""
        with self._collections_lock:
            return list(self._collections.keys())
    
    async def delete_document(self, document_id: str) -> bool:
        """Supprime un document."""
        with self._collections_lock:
            for collection, docs in self._collections.items():
                for i, doc in enumerate(docs):
                    if doc.document_id == document_id:
                        docs.pop(i)
                        return True
        return False
    
    async def delete_collection(self, collection: str) -> bool:
        """Supprime une collection."""
        with self._collections_lock:
            if collection in self._collections:
                del self._collections[collection]
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._schemas_lock:
            self._stats["schemas"] = len(self._schemas)
        with self._collections_lock:
            self._stats["documents"] = sum(len(v) for v in self._collections.values())
        
        return self._stats.copy()


# ============== JSON PATH UTILITY ==============

class JSONPathUtility:
    """
    Utilitaires pour les chemins JSON.
    Gère les requêtes et transformations de chemins JSON.
    """
    
    @staticmethod
    def get_value(data: Dict[str, Any], path: str, path_type: JSONPathType = JSONPathType.DOT) -> Any:
        """Récupère une valeur par chemin JSON."""
        if path_type == JSONPathType.DOT:
            return JSONPathUtility._get_dot_path(data, path)
        elif path_type == JSONPathType.BRACKET:
            return JSONPathUtility._get_bracket_path(data, path)
        else:
            return JSONPathUtility._get_dot_path(data, path)
    
    @staticmethod
    def _get_dot_path(data: Dict[str, Any], path: str) -> Any:
        """Récupère une valeur par chemin en notation pointée."""
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    @staticmethod
    def _get_bracket_path(data: Dict[str, Any], path: str) -> Any:
        """Récupère une valeur par chemin en notation crochets."""
        import re
        pattern = r"\['([^']+)'\]|\[\"([^\"]+)\"\]"
        parts = re.findall(pattern, path)
        
        current = data
        for part_tuple in parts:
            part = part_tuple[0] or part_tuple[1]
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    @staticmethod
    def set_value(data: Dict[str, Any], path: str, value: Any, path_type: JSONPathType = JSONPathType.DOT) -> None:
        """Définit une valeur par chemin JSON."""
        if path_type == JSONPathType.DOT:
            JSONPathUtility._set_dot_path(data, path, value)
        else:
            JSONPathUtility._set_dot_path(data, path, value)
    
    @staticmethod
    def _set_dot_path(data: Dict[str, Any], path: str, value: Any) -> None:
        """Définit une valeur par chemin en notation pointée."""
        parts = path.split(".")
        current = data
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    @staticmethod
    def exists(data: Dict[str, Any], path: str, path_type: JSONPathType = JSONPathType.DOT) -> bool:
        """Vérifie si un chemin existe."""
        return JSONPathUtility.get_value(data, path, path_type) is not None


# ============== FACTORY ==============

class JSONFactory:
    """Factory pour créer des composants JSON."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> JSONEngine:
        """Crée un moteur JSON."""
        engine = JSONEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "JSONSchemaVersion",
    "JSONPathType",
    "JSONCompression",
    "JSONSchema",
    "JSONDocument",
    "JSONQuery",
    "JSONEngineInterface",
    "JSONEngine",
    "JSONPathUtility",
    "JSONFactory"
]
