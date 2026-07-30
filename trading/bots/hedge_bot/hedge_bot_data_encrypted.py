# trading/bots/hedge_bot/hedge_bot_data_encrypted.py
# Secure Encrypted Data Layer for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Encrypted Data Layer - Couche de données chiffrées sécurisée pour le Hedge Bot.
Fournit une interface transparente pour le stockage et la récupération de données chiffrées
avec gestion automatique des clés, audit et conformité.
"""

import asyncio
import json
import base64
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import pickle
import zlib
import threading
from collections import defaultdict, deque

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_encrypted")

# Import des modules de sécurité
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine,
    KeyManagementService,
    SecurityContext,
    EncryptionAlgorithm,
    EncryptionKey,
    EncryptedData,
    DataClass,
    EncryptionScope,
    EncryptionFactory
)

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DataQueryResult,
    DistributedDataManager, DistributedDataNode, DataConsistency
)


# ============== ENUMS & TYPES ==============

class EncryptedDataType(Enum):
    """Types de données chiffrées."""
    SENSITIVE = "sensitive"
    PII = "pii"
    FINANCIAL = "financial"
    CREDENTIALS = "credentials"
    TRADING_SIGNALS = "trading_signals"
    POSITION_DATA = "position_data"
    ACCOUNT_DATA = "account_data"
    API_KEYS = "api_keys"
    PRIVATE_KEYS = "private_keys"
    TRANSACTION_DATA = "transaction_data"
    USER_DATA = "user_data"
    SYSTEM_CONFIG = "system_config"
    AUDIT_DATA = "audit_data"
    COMPLIANCE_DATA = "compliance_data"


# ============== DATA MODELS ==============

@dataclass
class EncryptedRecord:
    """Enregistrement chiffré avec métadonnées."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    data_type: EncryptedDataType = EncryptedDataType.SENSITIVE
    encrypted_data: EncryptedData = field(default_factory=EncryptedData)
    data_class: DataClass = DataClass.CONFIDENTIAL
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    version: int = 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner: str = ""
    access_count: int = 0
    last_access: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "record_id": self.record_id,
            "key": self.key,
            "data_type": self.data_type.value,
            "encrypted_data": self.encrypted_data.to_dict(),
            "data_class": self.data_class.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
            "tags": self.tags,
            "metadata": self.metadata,
            "owner": self.owner,
            "access_count": self.access_count,
            "last_access": self.last_access.isoformat() if self.last_access else None
        }


@dataclass
class EncryptedQuery:
    """Requête pour les données chiffrées."""
    query_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data_type: Optional[EncryptedDataType] = None
    data_class: Optional[DataClass] = None
    keys: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    owner: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    security_context: Optional[SecurityContext] = None


@dataclass
class EncryptedQueryResult:
    """Résultat d'une requête de données chiffrées."""
    query_id: str
    records: List[EncryptedRecord]
    total_count: int
    execution_time: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class EncryptedDataLayerInterface(ABC):
    """Interface abstraite pour la couche de données chiffrées."""
    
    @abstractmethod
    async def put(
        self,
        key: str,
        data: Any,
        data_type: EncryptedDataType = EncryptedDataType.SENSITIVE,
        data_class: DataClass = DataClass.CONFIDENTIAL,
        ttl: Optional[int] = None,
        security_context: Optional[SecurityContext] = None
    ) -> EncryptedRecord:
        """Stocke une donnée chiffrée."""
        pass
    
    @abstractmethod
    async def get(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> Optional[Any]:
        """Récupère une donnée déchiffrée."""
        pass
    
    @abstractmethod
    async def get_encrypted(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> Optional[EncryptedRecord]:
        """Récupère un enregistrement chiffré."""
        pass
    
    @abstractmethod
    async def delete(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> bool:
        """Supprime un enregistrement."""
        pass
    
    @abstractmethod
    async def query(self, query: EncryptedQuery) -> EncryptedQueryResult:
        """Exécute une requête."""
        pass


# ============== IMPLÉMENTATION ==============

class EncryptedDataLayer(EncryptedDataLayerInterface):
    """
    Couche de données chiffrées sécurisée.
    Fournit un stockage transparent avec chiffrement, contrôle d'accès et audit.
    """
    
    def __init__(
        self,
        encryption_engine: EncryptionEngine,
        key_manager: KeyManagementService,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.encryption_engine = encryption_engine
        self.key_manager = key_manager
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Cache local
        self._cache: Dict[str, EncryptedRecord] = {}
        self._cache_lock = threading.RLock()
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Métriques
        self._stats: Dict[str, Any] = {
            "puts": 0,
            "gets": 0,
            "deletes": 0,
            "queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0
        }
        
        # Index pour les requêtes
        self._indices: Dict[str, Set[str]] = {}
        self._indices_lock = threading.RLock()
        
        logger.info("EncryptedDataLayer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "cache_size": 1000,
            "cache_ttl": 3600,  # 1 heure
            "enable_caching": True,
            "enable_compression": True,
            "compression_threshold": 1024,
            "default_data_type": EncryptedDataType.SENSITIVE,
            "default_data_class": DataClass.CONFIDENTIAL,
            "audit_enabled": True,
            "auto_delete_expired": True,
            "delete_check_interval": 3600,
            "max_query_limit": 1000
        }
    
    async def start(self) -> None:
        """Démarre la couche de données chiffrées."""
        logger.info("EncryptedDataLayer starting...")
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._metrics_loop())
        
        logger.info("EncryptedDataLayer started")
    
    async def stop(self) -> None:
        """Arrête la couche de données chiffrées."""
        logger.info("EncryptedDataLayer stopping...")
        # Sauvegarde du cache
        await self._flush_cache()
        logger.info("EncryptedDataLayer stopped")
    
    async def put(
        self,
        key: str,
        data: Any,
        data_type: EncryptedDataType = EncryptedDataType.SENSITIVE,
        data_class: DataClass = DataClass.CONFIDENTIAL,
        ttl: Optional[int] = None,
        security_context: Optional[SecurityContext] = None
    ) -> EncryptedRecord:
        """Stocke une donnée chiffrée."""
        start_time = time.time()
        self._stats["puts"] += 1
        
        try:
            # Vérification des permissions
            if security_context and not security_context.can_access(data_class):
                raise PermissionError(f"Access denied for data class {data_class.value}")
            
            # Sérialisation des données
            serialized_data = self._serialize_data(data)
            
            # Compression
            if self.config["enable_compression"] and len(serialized_data) > self.config["compression_threshold"]:
                serialized_data = zlib.compress(serialized_data)
            
            # Chiffrement
            encrypted_data = await self.encryption_engine.encrypt(
                serialized_data,
                self._get_key_id_for_class(data_class)
            )
            
            # Création de l'enregistrement
            record = EncryptedRecord(
                key=key,
                data_type=data_type,
                encrypted_data=encrypted_data,
                data_class=data_class,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl else None,
                tags=[data_type.value, data_class.value],
                owner=security_context.user_id if security_context else "",
                metadata={
                    "original_size": len(serialized_data),
                    "encrypted_size": len(encrypted_data.ciphertext),
                    "encryption_time_ms": encrypted_data.metadata.get("encryption_time_ms", 0)
                }
            )
            
            # Stockage dans le gestionnaire de données
            if self.data_manager:
                await self.data_manager.store(
                    f"encrypted:{key}",
                    record.to_dict(),
                    DataType.METADATA
                )
            
            # Mise en cache
            await self._cache_record(record)
            
            # Indexation
            await self._index_record(record)
            
            # Log d'audit
            if self.config["audit_enabled"] and security_context:
                security_context.log_audit(
                    "PUT",
                    "encrypted_record",
                    key,
                    {"data_type": data_type.value, "data_class": data_class.value},
                    True
                )
            
            logger.info(f"Record stored: key={key}, type={data_type.value}, "
                       f"size={len(serialized_data)} bytes")
            
            return record
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error storing record {key}: {e}")
            raise
    
    async def get(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> Optional[Any]:
        """Récupère une donnée déchiffrée."""
        self._stats["gets"] += 1
        
        # Vérification du cache
        cache_key = f"decoded:{key}"
        if self.config["enable_caching"] and cache_key in self._cache:
            self._stats["cache_hits"] += 1
            record = self._cache[cache_key]
            
            # Vérification de l'expiration
            if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
                await self.delete(key, security_context)
                return None
            
            return self._deserialize_data(record)
        
        self._stats["cache_misses"] += 1
        
        # Récupération de l'enregistrement
        record = await self.get_encrypted(key, security_context)
        if not record:
            return None
        
        # Vérification des permissions
        if security_context and not security_context.can_access(record.data_class):
            raise PermissionError(f"Access denied for data class {record.data_class.value}")
        
        # Déchiffrement
        decrypted_data = await self.encryption_engine.decrypt(record.encrypted_data)
        
        # Décompression
        try:
            decrypted_data = zlib.decompress(decrypted_data)
        except zlib.error:
            # Pas compressé
            pass
        
        # Désérialisation
        data = self._deserialize_data(decrypted_data)
        
        # Mise à jour des accès
        record.access_count += 1
        record.last_access = datetime.now(timezone.utc)
        
        # Mise en cache
        if self.config["enable_caching"]:
            await self._cache_record(record)
        
        # Log d'audit
        if self.config["audit_enabled"] and security_context:
            security_context.log_audit(
                "GET",
                "encrypted_record",
                key,
                {"data_type": record.data_type.value, "size": len(decrypted_data)},
                True
            )
        
        logger.debug(f"Record retrieved: key={key}, type={record.data_type.value}")
        
        return data
    
    async def get_encrypted(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> Optional[EncryptedRecord]:
        """Récupère un enregistrement chiffré."""
        # Vérification du cache
        if self.config["enable_caching"]:
            with self._cache_lock:
                if key in self._cache:
                    record = self._cache[key]
                    # Vérification de l'expiration
                    if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
                        await self.delete(key, security_context)
                        return None
                    self._stats["cache_hits"] += 1
                    return record
        
        self._stats["cache_misses"] += 1
        
        try:
            # Récupération depuis le gestionnaire de données
            if self.data_manager:
                record_data = await self.data_manager.retrieve(
                    f"encrypted:{key}",
                    DataType.METADATA
                )
                
                if record_data:
                    record = self._deserialize_record(record_data)
                    if record:
                        # Vérification de l'expiration
                        if record.expires_at and datetime.now(timezone.utc) > record.expires_at:
                            await self.delete(key, security_context)
                            return None
                        
                        # Mise en cache
                        await self._cache_record(record)
                        return record
            
            return None
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error retrieving record {key}: {e}")
            return None
    
    async def delete(
        self,
        key: str,
        security_context: Optional[SecurityContext] = None
    ) -> bool:
        """Supprime un enregistrement."""
        self._stats["deletes"] += 1
        
        try:
            # Récupération de l'enregistrement
            record = await self.get_encrypted(key, security_context)
            if not record:
                return False
            
            # Vérification des permissions
            if security_context and not security_context.can_access(record.data_class):
                raise PermissionError(f"Access denied for data class {record.data_class.value}")
            
            # Suppression du gestionnaire de données
            if self.data_manager:
                await self.data_manager.delete(
                    f"encrypted:{key}",
                    DataType.METADATA
                )
            
            # Suppression du cache
            with self._cache_lock:
                if key in self._cache:
                    del self._cache[key]
            
            # Suppression des index
            await self._remove_from_index(key)
            
            # Log d'audit
            if self.config["audit_enabled"] and security_context:
                security_context.log_audit(
                    "DELETE",
                    "encrypted_record",
                    key,
                    {"data_type": record.data_type.value},
                    True
                )
            
            logger.info(f"Record deleted: key={key}")
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error deleting record {key}: {e}")
            return False
    
    async def query(self, query: EncryptedQuery) -> EncryptedQueryResult:
        """Exécute une requête."""
        start_time = time.time()
        self._stats["queries"] += 1
        
        try:
            records = []
            total_count = 0
            
            # Récupération des enregistrements
            if self.data_manager:
                # Utilisation des index pour filtrer
                keys = await self._search_indices(query)
                
                # Récupération des enregistrements
                for key in keys:
                    record = await self.get_encrypted(key, query.security_context)
                    if record:
                        # Filtrage supplémentaire
                        if self._matches_query(record, query):
                            records.append(record)
                
                total_count = len(records)
                
                # Pagination
                if query.limit:
                    start = query.offset
                    end = start + min(query.limit, self.config["max_query_limit"])
                    records = records[start:end]
            
            result = EncryptedQueryResult(
                query_id=query.query_id,
                records=records,
                total_count=total_count,
                execution_time=time.time() - start_time
            )
            
            logger.debug(f"Query executed: {query.query_id}, found {total_count} records")
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error executing query: {e}")
            return EncryptedQueryResult(
                query_id=query.query_id,
                records=[],
                total_count=0,
                execution_time=time.time() - start_time,
                error=str(e)
            )
    
    # ========== MÉTHODES PRIVÉES - SÉRIALISATION ==========
    
    def _serialize_data(self, data: Any) -> bytes:
        """Sérialise des données."""
        if isinstance(data, (str, bytes)):
            return data.encode() if isinstance(data, str) else data
        return pickle.dumps(data)
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Désérialise des données."""
        try:
            return pickle.loads(data)
        except (pickle.UnpicklingError, EOFError):
            # Peut être du texte brut
            try:
                return data.decode()
            except UnicodeDecodeError:
                return data
    
    def _deserialize_record(self, data: Any) -> Optional[EncryptedRecord]:
        """Désérialise un enregistrement."""
        try:
            if isinstance(data, dict):
                encrypted_data_dict = data.get("encrypted_data", {})
                encrypted_data = EncryptedData(
                    encrypted_id=encrypted_data_dict.get("encrypted_id", str(uuid.uuid4())),
                    key_id=encrypted_data_dict.get("key_id", ""),
                    algorithm=EncryptionAlgorithm(encrypted_data_dict.get("algorithm", "aes-256-gcm")),
                    ciphertext=base64.b64decode(encrypted_data_dict.get("ciphertext", "")),
                    iv=base64.b64decode(encrypted_data_dict.get("iv", "")) if encrypted_data_dict.get("iv") else None,
                    salt=base64.b64decode(encrypted_data_dict.get("salt", "")) if encrypted_data_dict.get("salt") else None,
                    tag=base64.b64decode(encrypted_data_dict.get("tag", "")) if encrypted_data_dict.get("tag") else None,
                    data_class=DataClass(encrypted_data_dict.get("data_class", "confidential")),
                    scope=EncryptionScope(encrypted_data_dict.get("scope", "both")),
                    created_at=datetime.fromisoformat(encrypted_data_dict.get("created_at", datetime.now(timezone.utc).isoformat())),
                    expires_at=datetime.fromisoformat(encrypted_data_dict.get("expires_at")) if encrypted_data_dict.get("expires_at") else None,
                    metadata=encrypted_data_dict.get("metadata", {}),
                    signature=base64.b64decode(encrypted_data_dict.get("signature", "")) if encrypted_data_dict.get("signature") else None,
                    signer_id=encrypted_data_dict.get("signer_id"),
                    integrity_hash=encrypted_data_dict.get("integrity_hash"),
                    version=encrypted_data_dict.get("version", 1)
                )
                
                return EncryptedRecord(
                    record_id=data.get("record_id", str(uuid.uuid4())),
                    key=data.get("key", ""),
                    data_type=EncryptedDataType(data.get("data_type", "sensitive")),
                    encrypted_data=encrypted_data,
                    data_class=DataClass(data.get("data_class", "confidential")),
                    created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                    updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
                    expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None,
                    version=data.get("version", 1),
                    tags=data.get("tags", []),
                    metadata=data.get("metadata", {}),
                    owner=data.get("owner", ""),
                    access_count=data.get("access_count", 0),
                    last_access=datetime.fromisoformat(data.get("last_access")) if data.get("last_access") else None
                )
            return None
        except Exception as e:
            logger.error(f"Error deserializing record: {e}")
            return None
    
    # ========== MÉTHODES PRIVÉES - CACHE ==========
    
    async def _cache_record(self, record: EncryptedRecord) -> None:
        """Cache un enregistrement."""
        if not self.config["enable_caching"]:
            return
        
        with self._cache_lock:
            # Éviction LRU si besoin
            if len(self._cache) >= self.config["cache_size"]:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[record.key] = record
            self._cache[f"decoded:{record.key}"] = record
    
    async def _flush_cache(self) -> None:
        """Vide le cache."""
        with self._cache_lock:
            self._cache.clear()
    
    # ========== MÉTHODES PRIVÉES - INDEX ==========
    
    async def _index_record(self, record: EncryptedRecord) -> None:
        """Indexe un enregistrement."""
        with self._indices_lock:
            # Index par type
            if record.data_type.value not in self._indices:
                self._indices[record.data_type.value] = set()
            self._indices[record.data_type.value].add(record.key)
            
            # Index par classe
            if record.data_class.value not in self._indices:
                self._indices[record.data_class.value] = set()
            self._indices[record.data_class.value].add(record.key)
            
            # Index par tags
            for tag in record.tags:
                if tag not in self._indices:
                    self._indices[tag] = set()
                self._indices[tag].add(record.key)
    
    async def _remove_from_index(self, key: str) -> None:
        """Supprime un enregistrement des index."""
        with self._indices_lock:
            for index_set in self._indices.values():
                index_set.discard(key)
    
    async def _search_indices(self, query: EncryptedQuery) -> List[str]:
        """Recherche dans les index."""
        with self._indices_lock:
            keys = None
            
            # Filtrage par type
            if query.data_type:
                type_keys = self._indices.get(query.data_type.value, set())
                keys = type_keys if keys is None else keys & type_keys
            
            # Filtrage par classe
            if query.data_class:
                class_keys = self._indices.get(query.data_class.value, set())
                keys = class_keys if keys is None else keys & class_keys
            
            # Filtrage par tags
            for tag in query.tags:
                tag_keys = self._indices.get(tag, set())
                keys = tag_keys if keys is None else keys & tag_keys
            
            return list(keys or set())
    
    def _matches_query(self, record: EncryptedRecord, query: EncryptedQuery) -> bool:
        """Vérifie si un enregistrement correspond à une requête."""
        # Filtrage par propriétaire
        if query.owner and record.owner != query.owner:
            return False
        
        # Filtrage par date de création
        if query.created_after and record.created_at < query.created_after:
            return False
        if query.created_before and record.created_at > query.created_before:
            return False
        
        # Filtrage par métadonnées
        for key, value in query.metadata.items():
            if record.metadata.get(key) != value:
                return False
        
        return True
    
    # ========== MÉTHODES PRIVÉES - GESTION DES CLÉS ==========
    
    def _get_key_id_for_class(self, data_class: DataClass) -> str:
        """Obtient l'ID de clé approprié pour une classification."""
        # Stratégie de clé basée sur la classification
        key_map = {
            DataClass.PUBLIC: "key_public",
            DataClass.INTERNAL: "key_internal",
            DataClass.CONFIDENTIAL: "key_confidential",
            DataClass.SECRET: "key_secret",
            DataClass.TOP_SECRET: "key_top_secret",
            DataClass.RESTRICTED: "key_restricted"
        }
        
        return key_map.get(data_class, "key_default")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cleanup_loop(self) -> None:
        """Boucle de nettoyage des enregistrements expirés."""
        if not self.config["auto_delete_expired"]:
            return
        
        while True:
            await asyncio.sleep(self.config["delete_check_interval"])
            
            try:
                now = datetime.now(timezone.utc)
                
                # Nettoyage du cache
                with self._cache_lock:
                    expired_keys = []
                    for key, record in self._cache.items():
                        if record.expires_at and record.expires_at <= now:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        del self._cache[key]
                
                # Nettoyage des enregistrements expirés
                if self.data_manager:
                    # Recherche des enregistrements expirés
                    # Note: Dans un système réel, on utiliserait une requête plus sophistiquée
                    pass
                
                logger.debug(f"Cleaned up {len(expired_keys)} expired records")
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _metrics_loop(self) -> None:
        """Boucle de collecte des métriques."""
        while True:
            await asyncio.sleep(60)
            
            try:
                self._stats["cache_hits"] = self._stats.get("cache_hits", 0) + self._cache_hits
                self._stats["cache_misses"] = self._stats.get("cache_misses", 0) + self._cache_misses
                
                logger.debug(f"EncryptedDataLayer stats: {self._stats}")
                
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
    
    # ========== MÉTHODES PUBLIQUES - STATS ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._cache_lock:
            self._stats["cache_size"] = len(self._cache)
        
        return self._stats
    
    async def clear_cache(self) -> None:
        """Vide le cache."""
        await self._flush_cache()
        logger.info("Cache cleared")


# ============== CONTEXT MANAGER ==============

class EncryptedDataContext:
    """Context manager pour les opérations de données chiffrées."""
    
    def __init__(
        self,
        data_layer: EncryptedDataLayer,
        security_context: SecurityContext,
        key: str,
        data_type: EncryptedDataType = EncryptedDataType.SENSITIVE,
        data_class: DataClass = DataClass.CONFIDENTIAL
    ):
        self.data_layer = data_layer
        self.security_context = security_context
        self.key = key
        self.data_type = data_type
        self.data_class = data_class
        self.record: Optional[EncryptedRecord] = None
    
    async def __aenter__(self):
        # Récupération de l'enregistrement existant
        self.record = await self.data_layer.get_encrypted(
            self.key,
            self.security_context
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Sauvegarde si modifié
        if self.record:
            # Mise à jour
            await self.data_layer.put(
                self.key,
                self.record,
                self.data_type,
                self.data_class,
                security_context=self.security_context
            )
    
    async def read(self) -> Optional[Any]:
        """Lit les données."""
        if self.record:
            data = await self.data_layer.get(self.key, self.security_context)
            return data
        return None
    
    async def write(self, data: Any) -> None:
        """Écrit des données."""
        self.record = await self.data_layer.put(
            self.key,
            data,
            self.data_type,
            self.data_class,
            security_context=self.security_context
        )


# ============== FACTORY ==============

class EncryptedDataLayerFactory:
    """Factory pour créer la couche de données chiffrées."""
    
    @staticmethod
    async def create_layer(
        encryption_engine: Optional[EncryptionEngine] = None,
        key_manager: Optional[KeyManagementService] = None,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> EncryptedDataLayer:
        """Crée une couche de données chiffrées."""
        # Création des composants si non fournis
        if not encryption_engine:
            if not key_manager:
                key_manager = await EncryptionFactory.create_key_manager(
                    data_manager=data_manager
                )
            encryption_engine = await EncryptionFactory.create_engine(
                key_manager=key_manager,
                data_manager=data_manager
            )
        
        layer = EncryptedDataLayer(
            encryption_engine=encryption_engine,
            key_manager=key_manager,
            data_manager=data_manager,
            config=config
        )
        await layer.start()
        return layer


# ============== EXPORT ==============

__all__ = [
    "EncryptedDataType",
    "EncryptedRecord",
    "EncryptedQuery",
    "EncryptedQueryResult",
    "EncryptedDataLayerInterface",
    "EncryptedDataLayer",
    "EncryptedDataContext",
    "EncryptedDataLayerFactory"
]
